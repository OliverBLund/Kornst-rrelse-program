"""
Regression tests for comparison plot widget behavior.
"""

import math
import os
import sys
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, 'Program')

from matplotlib.figure import Figure
from matplotlib.colors import to_hex
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from data_loader import GrainSizeData
from grain_classification import USCS
from gui.comparison_plot_widget import ComparisonPlotWidget
from gui.plot_renderers import render_k_boxplot, render_k_histogram
from gui.group_styles import (
    clear_dataset_line_style,
    clear_group_color,
    set_dataset_line_style,
    set_group_color,
)
from gui.theme import SZ
from k_calculations_v2 import CalculationStatus, KCalculationResult
from unit_conversions import HydraulicConductivityUnit


APP = QApplication.instance() or QApplication([])


def build_dataset(name: str) -> GrainSizeData:
    return GrainSizeData(
        sample_name=name,
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
        percent_passing=[100.0, 95.0, 82.0, 61.0, 38.0, 14.0, 4.0],
    )


def build_results(scale: float, flagged_method: str | None = None) -> list[KCalculationResult]:
    return [
        KCalculationResult(
            method_name='Hazen',
            k_value=1.0e-4 * scale,
            formula_used='',
            status=CalculationStatus.WARNING if flagged_method == 'Hazen' else CalculationStatus.OK,
            status_message='',
            conditions_met=flagged_method != 'Hazen',
            temperature=20.0,
            porosity=0.35,
            grain_size_used='D10',
        ),
        KCalculationResult(
            method_name='Beyer',
            k_value=1.5e-4 * scale,
            formula_used='',
            status=CalculationStatus.WARNING if flagged_method == 'Beyer' else CalculationStatus.OK,
            status_message='',
            conditions_met=flagged_method != 'Beyer',
            temperature=20.0,
            porosity=0.35,
            grain_size_used='D10',
        ),
    ]


class DummyDatasetTab:
    def __init__(
        self,
        name: str,
        scale: float,
        flagged_method: str | None = None,
        group: str = 'Ungrouped',
    ):
        self._dataset = build_dataset(name)
        self._dataset.group_name = group
        self._results = build_results(scale, flagged_method=flagged_method)

    def get_dataset(self):
        return self._dataset

    def get_results(self):
        return self._results


class TestComparisonPlotWidget(unittest.TestCase):
    def setUp(self):
        self.widget = ComparisonPlotWidget()
        self.widget.set_datasets([
            DummyDatasetTab('Sample A', 1.0, flagged_method='Beyer'),
            DummyDatasetTab('Sample B', 2.0),
        ])

    def tearDown(self):
        self.widget.deleteLater()

    @staticmethod
    def _legend_handle_for(ax, name):
        """Return the legend handle whose label matches *name* (ignoring the
        indentation added by the group-structured legend)."""
        legend = ax.get_legend()
        handles = getattr(legend, 'legend_handles', getattr(legend, 'legendHandles', []))
        labels = [t.get_text() for t in legend.get_texts()]
        for handle, label in zip(handles, labels):
            if label.strip() == name:
                return handle
        raise AssertionError(f"No legend entry for {name!r} in {labels}")

    def test_plot_type_change_normalizes_layout_mode(self):
        # Combined is grid-only; switching to it forces grid layout and disables
        # the Overlay option.
        self.widget.on_plot_type_changed('Combined')
        self.assertEqual(self.widget.display_mode, 'grid')
        self.assertTrue(self.widget.grid_radio.isChecked())
        self.assertFalse(self.widget.overlay_radio.isEnabled())

        # K-Values supports both layouts; Overlay becomes available and active.
        self.widget.on_plot_type_changed('K-Values')
        self.widget.set_display_mode('overlay')
        self.assertEqual(self.widget.display_mode, 'overlay')
        self.assertTrue(self.widget.overlay_radio.isEnabled())
        self.assertTrue(self.widget.overlay_radio.isChecked())

        # K Distribution is overlay-only; Grid is disabled.
        self.widget.on_plot_type_changed('K Distribution')
        self.assertEqual(self.widget.display_mode, 'overlay')
        self.assertFalse(self.widget.grid_radio.isEnabled())

    def test_breakdown_defaults_to_group_when_groups_exist(self):
        self.widget.set_datasets([
            DummyDatasetTab('Layer A-1', 1.0, group='Layer A'),
            DummyDatasetTab('Layer A-2', 1.5, group='Layer A'),
            DummyDatasetTab('Layer B-1', 3.0, group='Layer B'),
        ])
        self.assertEqual(self.widget.breakdown, 'group')
        self.assertTrue(self.widget._use_group_breakdown())
        self.assertFalse(self.widget._breakdown_frame.isHidden())

        # Ungrouped scope falls back to per-dataset and hides the control.
        self.widget.set_datasets([
            DummyDatasetTab('Sample A', 1.0),
            DummyDatasetTab('Sample B', 2.0),
        ])
        self.assertEqual(self.widget.breakdown, 'dataset')
        self.assertFalse(self.widget._use_group_breakdown())

    def test_k_values_overlay_aggregates_one_bar_per_group(self):
        self.widget.set_datasets([
            DummyDatasetTab('Layer A-1', 1.0, group='Layer A'),
            DummyDatasetTab('Layer A-2', 1.5, group='Layer A'),
            DummyDatasetTab('Layer B-1', 3.0, group='Layer B'),
        ])
        self.widget.on_plot_type_changed('K-Values')
        self.widget.set_display_mode('overlay')
        self.widget.refresh_plot()

        results_m_s, colors, flagged = self.widget._group_overlay_inputs()
        # Two named groups -> two aggregated bar series, no ungrouped expansion.
        self.assertEqual(set(results_m_s.keys()), {'Layer A', 'Layer B'})
        self.assertEqual(len(colors), 2)
        self.assertTrue(all(not flag for flag in flagged.values()))
        self.assertAlmostEqual(
            results_m_s['Layer A']['Hazen'],
            math.sqrt(1.0e-4 * 1.5e-4),
        )
        self.assertEqual(self.widget.figure.axes[0].get_title(), 'Hydraulic Conductivity by Group')
        self.assertEqual(self.widget._drawer_title.text(), 'K-value plotted bars')
        self.assertEqual({row[0] for row in self.widget._drawer_rows}, {'Layer A', 'Layer B'})
        self.assertTrue(
            all(row[4] == 'Group method geometric mean (OK only)' for row in self.widget._drawer_rows)
        )

    def test_k_values_group_bars_can_use_arithmetic_mean(self):
        self.widget.set_datasets([
            DummyDatasetTab('Layer A-1', 1.0, group='Layer A'),
            DummyDatasetTab('Layer A-2', 4.0, group='Layer A'),
            DummyDatasetTab('Layer B-1', 9.0, group='Layer B'),
        ])
        self.widget.on_plot_type_changed('K-Values')
        self.widget.set_display_mode('overlay')
        self.widget._k_group_agg_combo.setCurrentIndex(1)

        results_m_s, _colors, _flagged = self.widget._group_overlay_inputs()

        self.assertEqual(self.widget.k_group_aggregation, 'arithmetic')
        self.assertFalse(self.widget._sect_k_group_agg.isHidden())
        self.assertAlmostEqual(results_m_s['Layer A']['Hazen'], 2.5e-4)
        self.assertAlmostEqual(results_m_s['Layer A']['Beyer'], 3.75e-4)
        title = self.widget.figure.axes[0].get_title().lower()
        self.assertNotIn('arithmetic', title)
        self.assertNotIn('geometric', title)
        self.assertTrue(
            all(row[4] == 'Group method arithmetic mean (OK only)' for row in self.widget._drawer_rows)
        )

    def test_histogram_facets_by_group_when_grouped(self):
        self.widget.set_datasets([
            DummyDatasetTab('Layer A-1', 1.0, group='Layer A'),
            DummyDatasetTab('Layer A-2', 1.5, group='Layer A'),
            DummyDatasetTab('Layer B-1', 3.0, group='Layer B'),
        ])
        self.widget.on_plot_type_changed('Histogram')
        self.widget.refresh_plot()

        units = self.widget._histogram_units()
        self.assertEqual([u['label'] for u in units], ['Layer A', 'Layer B'])
        # One panel per group, and the aggregate stays a valid mass distribution.
        self.assertEqual(len(self.widget.figure.axes), 2)
        heights = [patch.get_height() for patch in self.widget.figure.axes[0].patches]
        self.assertTrue(all(height >= 0 for height in heights))
        self.assertEqual(self.widget._drawer_title.text(), 'Histogram classification-fraction data')
        self.assertEqual({row[0] for row in self.widget._drawer_rows}, {'Layer A', 'Layer B'})

    def test_combined_facets_use_group_geomean_when_grouped(self):
        self.widget.set_datasets([
            DummyDatasetTab('Layer A-1', 1.0, group='Layer A'),
            DummyDatasetTab('Layer A-2', 1.5, group='Layer A'),
            DummyDatasetTab('Layer B-1', 3.0, group='Layer B'),
        ])
        self.widget.on_plot_type_changed('Combined')
        self.widget.refresh_plot()

        facets = self.widget._combined_facets()
        self.assertEqual([f['label'] for f in facets], ['Layer A', 'Layer B'])
        self.assertTrue(all(f['k'] for f in facets))
        self.assertEqual(self.widget._drawer_title.text(), 'Combined plotted data')
        self.assertIn('Distribution', {row[1] for row in self.widget._drawer_rows})
        self.assertIn('K values', {row[1] for row in self.widget._drawer_rows})

    def test_k_distribution_controls_visible_only_for_that_type(self):
        self.widget.on_plot_type_changed('K Distribution')
        self.assertTrue(self.widget._sect_kdist.isVisibleTo(self.widget))
        self.widget.on_plot_type_changed('Distribution')
        self.assertFalse(self.widget._sect_kdist.isVisibleTo(self.widget))

    def test_k_distribution_defaults_to_lognormal_histogram_frequency(self):
        # The lognormal histogram with a frequency axis is the default view now;
        # bars are drawn (not the empirical CDF) with no manual selection.
        self.widget.on_plot_type_changed('K Distribution')
        self.widget.refresh_plot()

        self.assertEqual(self.widget.k_dist_view, 'histogram')
        self.assertEqual(self.widget.k_hist_y_mode, 'frequency')
        self.assertTrue(self.widget.k_hist_show_n)
        self.assertTrue(self.widget.k_hist_drop_empty)

        ax = self.widget.figure.axes[0]
        self.assertEqual(ax.get_ylabel(), 'Frequency (count)')
        self.assertGreater(len(ax.patches), 0)
        # N labels are on by default — the count annotation appears atop a bar.
        self.assertTrue(any(t.get_text().isdigit() for t in ax.texts))

    def test_k_distribution_histogram_density_toggle_changes_axis(self):
        self.widget.on_plot_type_changed('K Distribution')
        self.widget._on_kdist_ymode_changed('density')
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        self.assertEqual(ax.get_ylabel(), 'Probability density')

    def test_k_distribution_show_n_toggle_removes_count_labels(self):
        self.widget.on_plot_type_changed('K Distribution')
        self.widget._on_kdist_show_n_toggled(False)
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        self.assertFalse(any(t.get_text().isdigit() for t in ax.texts))

    def test_k_distribution_histogram_lnk_view_annotates_sigma(self):
        self.widget.on_plot_type_changed('K Distribution')
        self.widget._on_kdist_view_changed('histogram')
        self.widget._on_kdist_axis_changed('lnk')

        ax = self.widget.figure.axes[0]
        self.assertIn('ln K', ax.get_xlabel())
        self.assertTrue(self.widget._row_kdist_axis.isVisibleTo(self.widget._sect_kdist))
        texts = [t.get_text() for t in ax.texts]
        self.assertTrue(any('lnK' in text for text in texts))

    def test_k_distribution_histogram_grouped_auto_draws_bars(self):
        self.widget.set_datasets([
            DummyDatasetTab('Layer A-1', 1.0, group='Layer A'),
            DummyDatasetTab('Layer A-2', 1.5, group='Layer A'),
            DummyDatasetTab('Layer B-1', 3.0, group='Layer B'),
            DummyDatasetTab('Layer B-2', 5.0, group='Layer B'),
        ])
        self.widget.on_plot_type_changed('K Distribution')
        self.widget._on_kdist_view_changed('histogram')
        # Auto now draws (dodged) bars for groups too.
        self.assertEqual(self.widget.k_hist_bins, 'auto')
        ax = self.widget.figure.axes[0]
        self.assertGreater(len(ax.patches), 0)

        # 'Off' shows fitted curves only — no bars.
        idx = self.widget._kdist_bin_options.index('Off')
        self.widget._kdist_bins_combo.setCurrentIndex(idx)
        self.assertEqual(self.widget.k_hist_bins, 'off')
        ax = self.widget.figure.axes[0]
        self.assertEqual(len(ax.patches), 0)

    def test_k_distribution_histogram_k_axis_uses_conductivity_label(self):
        self.widget.on_plot_type_changed('K Distribution')
        self.widget.k_dist_view = 'histogram'
        self.widget.k_hist_axis = 'k'
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        self.assertIn('Hydraulic Conductivity', ax.get_xlabel())

    def test_histogram_uses_non_negative_retained_frequencies(self):
        self.widget.on_plot_type_changed('Histogram')
        self.widget.refresh_plot()

        first_ax = self.widget.figure.axes[0]
        heights = [patch.get_height() for patch in first_ax.patches]

        self.assertTrue(all(height >= 0 for height in heights))
        self.assertAlmostEqual(sum(heights), 100.0, places=6)
        self.assertEqual(first_ax.get_ylabel(), 'Weight (%)')
        self.assertEqual(first_ax.get_xlabel(), 'Grain-size class (ISO 14688)')
        tick_labels = [tick.get_text() for tick in first_ax.get_xticklabels()]
        self.assertEqual(tick_labels.count('Coarse sand'), 1)
        self.assertEqual(self.widget.display_mode, 'grid')
        self.assertTrue(self.widget.grid_radio.isChecked())

    def test_group_colors_stable_across_hide_and_show(self):
        tabs = [
            DummyDatasetTab('A', 1.0, group='G1'),
            DummyDatasetTab('B', 1.5, group='G1'),
            DummyDatasetTab('C', 2.0, group='G2'),
        ]
        self.widget.set_datasets(tabs)
        g1, g2 = self.widget._group_color_map['G1'], self.widget._group_color_map['G2']

        # Hide G1 (only C/G2 remains) — G2 keeps its colour.
        self.widget.set_datasets([tabs[2]])
        self.assertEqual(self.widget._group_color_map['G2'], g2)

        # Re-show everything — both groups keep their original colours.
        self.widget.set_datasets(tabs)
        self.assertEqual(self.widget._group_color_map['G1'], g1)
        self.assertEqual(self.widget._group_color_map['G2'], g2)

    def test_breakdown_choice_survives_visibility_toggle(self):
        tabs = [
            DummyDatasetTab('A', 1.0, group='G1'),
            DummyDatasetTab('B', 1.5, group='G2'),
        ]
        self.widget.set_datasets(tabs)
        self.assertEqual(self.widget.breakdown, 'group')  # default with groups

        self.widget._on_breakdown_toggled(True, 'dataset')  # user picks per-dataset
        self.assertEqual(self.widget.breakdown, 'dataset')

        # A visibility toggle re-enters set_datasets with a subset — keep choice.
        self.widget.set_datasets([tabs[0]])
        self.assertEqual(self.widget.breakdown, 'dataset')

        # A genuine scope change resets to the group default.
        self.widget.reset_presentation_state()
        self.widget.set_datasets(tabs)
        self.assertEqual(self.widget.breakdown, 'group')

    def test_k_value_overlay_hatches_flagged_methods_and_shows_grid(self):
        self.widget.on_plot_type_changed('K-Values')
        self.widget.set_display_mode('overlay')
        self.widget.show_grid = True
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        hatches = [patch.get_hatch() for patch in ax.patches]

        self.assertIn('////', hatches)
        self.assertTrue(any(line.get_visible() for line in ax.yaxis.get_gridlines()))

    def test_k_value_comparison_uses_linear_axis_by_default_and_log_when_enabled(self):
        self.widget.on_plot_type_changed('K-Values')
        self.widget.set_display_mode('overlay')
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        self.assertEqual(ax.get_yscale(), 'linear')
        self.assertFalse(self.widget._row_k_log.isHidden())

        self.widget._sw_k_log.setChecked(True, animate=False)
        self.widget._on_sidebar_log_k_toggled(True)

        self.assertEqual(self.widget.figure.axes[0].get_yscale(), 'log')

    def test_k_distribution_plots_overall_and_group_cdfs(self):
        self.widget.set_datasets([
            DummyDatasetTab('Layer A-1', 1.0, group='Layer A'),
            DummyDatasetTab('Layer A-2', 1.5, group='Layer A'),
            DummyDatasetTab('Layer B-1', 3.0, group='Layer B'),
        ])

        self.widget.on_plot_type_changed('K Distribution')
        # Histogram is the default view now; this test covers the empirical CDF.
        self.widget._on_kdist_view_changed('cdf')
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        labels = [line.get_label() for line in ax.lines]

        self.assertEqual(self.widget.current_plot_type, 'k-distribution')
        self.assertEqual(ax.get_xscale(), 'log')
        self.assertIn('Overall', labels)
        self.assertIn('Layer A', labels)
        self.assertIn('Layer B', labels)
        self.assertIn('Overall Kgeo', labels)

    def test_k_boxplot_renderer_excludes_warning_results(self):
        figure = Figure()
        ax = figure.add_subplot(1, 1, 1)
        captured = {}
        results = [
            build_results(1.0, flagged_method='Beyer')[0],
            build_results(100.0, flagged_method='Beyer')[1],
        ]

        def capture_boxplot(data, *args, **kwargs):
            captured['data'] = data
            return {}

        with patch.object(ax, 'boxplot', side_effect=capture_boxplot):
            render_k_boxplot(ax, {'Sample A': results})

        self.assertEqual(captured['data'], [[1.0e-4]])

    def test_group_color_override_drives_grouped_dataset_colors(self):
        clear_group_color('Layer A')
        try:
            set_group_color('Layer A', '#123456')
            self.widget.set_datasets([
                DummyDatasetTab('Layer A-1', 1.0, group='Layer A'),
                DummyDatasetTab('Layer A-2', 1.5, group='Layer A'),
                DummyDatasetTab('Sample C', 2.0),
            ])

            colors = self.widget._effective_dataset_colors()

            self.assertEqual(colors[0], '#123456')
            self.assertEqual(colors[1], '#123456')
            self.assertIn('Layer A', self.widget._group_color_rows)
            self.assertNotIn('Layer A-1', self.widget._dataset_color_rows)
            self.assertIn('Sample C', self.widget._dataset_color_rows)
        finally:
            clear_group_color('Layer A')

    def test_grouped_dataset_line_style_override_is_respected(self):
        clear_dataset_line_style('Layer A-2')
        try:
            set_dataset_line_style('Layer A-2', ':')
            self.widget.set_datasets([
                DummyDatasetTab('Layer A-1', 1.0, group='Layer A'),
                DummyDatasetTab('Layer A-2', 1.5, group='Layer A'),
            ])

            self.assertEqual(self.widget._effective_dataset_colors()[0], self.widget._effective_dataset_colors()[1])
            self.assertEqual(self.widget._effective_dataset_linestyles(), ['-', ':'])
            self.assertIn('Layer A-2', self.widget._dataset_line_style_rows)
            self.widget.on_plot_type_changed('Distribution')
            self.widget.set_display_mode('overlay')
            self.widget.breakdown = 'dataset'
            self.widget.refresh_plot()

            ax = self.widget.figure.axes[0]
            handle = self._legend_handle_for(ax, 'Layer A-2')
            self.assertEqual(ax.lines[1].get_linestyle(), ':')
            self.assertEqual(handle.get_linestyle(), ':')
        finally:
            clear_dataset_line_style('Layer A-2')

    def test_grouped_dataset_marker_style_is_used_in_plot_and_legend(self):
        clear_dataset_line_style('Layer A-2')
        try:
            set_dataset_line_style('Layer A-2', '--|s')
            self.widget.set_datasets([
                DummyDatasetTab('Layer A-1', 1.0, group='Layer A'),
                DummyDatasetTab('Layer A-2', 1.5, group='Layer A'),
            ])

            combo = self.widget._dataset_line_style_rows['Layer A-2']
            self.assertLessEqual(combo.maximumWidth(), 72)
            self.assertEqual(combo.currentData(), '--|s')

            self.widget.on_plot_type_changed('Distribution')
            self.widget.set_display_mode('overlay')
            self.widget.breakdown = 'dataset'
            self.widget.refresh_plot()

            ax = self.widget.figure.axes[0]
            handle = self._legend_handle_for(ax, 'Layer A-2')
            self.assertEqual(ax.lines[1].get_linestyle(), '--')
            self.assertEqual(ax.lines[1].get_marker(), 's')
            self.assertEqual(handle.get_linestyle(), '--')
            self.assertEqual(handle.get_marker(), 's')
        finally:
            clear_dataset_line_style('Layer A-2')

    def test_data_drawer_updates_for_k_distribution(self):
        self.widget.on_plot_type_changed('K Distribution')
        # Histogram is the default view now; this test covers the CDF drawer.
        self.widget._on_kdist_view_changed('cdf')
        self.widget.refresh_plot()

        headers = [
            self.widget._drawer_table.horizontalHeaderItem(col).text()
            for col in range(self.widget._drawer_table.columnCount())
        ]

        self.assertEqual(self.widget._drawer_title.text(), 'K distribution CDF points - OK only')
        self.assertIn('CDF probability (%)', headers)
        self.assertGreaterEqual(self.widget._drawer_table.rowCount(), 1)
        self.assertEqual(self.widget._drawer_table.verticalHeader().defaultSectionSize(), 24)
        self.assertEqual(self.widget._drawer_table.rowHeight(0), 24)

        self.widget._set_drawer_visible(True)
        self.widget._drawer_anim.setCurrentTime(self.widget._drawer_anim.duration())
        APP.processEvents()

        self.assertTrue(self.widget.drawer_visible)
        self.assertFalse(self.widget._drawer_table.isHidden())
        self.assertLessEqual(self.widget._drawer.maximumHeight(), 260)

    def test_distribution_drawer_contains_visible_curve_points(self):
        self.widget.on_plot_type_changed('Distribution')
        self.widget.refresh_plot()

        self.assertEqual(self.widget._drawer_title.text(), 'Distribution curve data')
        self.assertEqual(
            self.widget._drawer_headers,
            ['Dataset', 'Particle size (mm)', 'Percent passing (%)'],
        )
        self.assertEqual(len(self.widget._drawer_rows), 14)
        self.assertEqual(self.widget._drawer_rows[0], ('Sample A', '4.750000', '100.0000'))
        self.assertEqual(self.widget._drawer_rows[7][0], 'Sample B')

    def test_histogram_drawer_contains_visible_class_fraction_weights(self):
        self.widget.on_plot_type_changed('Histogram')
        self.widget.refresh_plot()

        self.assertEqual(self.widget._drawer_title.text(), 'Histogram classification-fraction data')
        self.assertEqual(
            self.widget._drawer_headers,
            [
                'Scope',
                'Fraction (ISO 14688)',
                'Lower size (mm)',
                'Upper size (mm)',
                'Weight (%)',
            ],
        )
        sample_a_rows = [
            row
            for row in self.widget._drawer_rows
            if row[0] == 'Sample A'
        ]
        sample_a_weights = [float(row[4]) for row in sample_a_rows]

        self.assertEqual(len(sample_a_rows), 11)
        self.assertEqual([row[1] for row in sample_a_rows].count('Coarse sand'), 1)
        self.assertAlmostEqual(sum(sample_a_weights), 100.0, places=6)

    def test_histogram_uses_active_classification_scheme(self):
        self.widget.set_scheme(USCS)
        self.widget.on_plot_type_changed('Histogram')
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        tick_labels = [tick.get_text() for tick in ax.get_xticklabels()]

        self.assertEqual(ax.get_xlabel(), 'Grain-size class (USCS)')
        self.assertEqual(tick_labels, ['Clay', 'Silt', 'Sand', 'Gravel', 'Cobble'])
        self.assertEqual(
            self.widget._drawer_headers,
            [
                'Scope',
                'Fraction (USCS)',
                'Lower size (mm)',
                'Upper size (mm)',
                'Weight (%)',
            ],
        )

    def test_comparison_drawer_exports_current_rows(self):
        self.widget.on_plot_type_changed('K-Values')
        self.widget.refresh_plot()

        original_dialog = QFileDialog.getSaveFileName
        original_info = QMessageBox.information
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / 'comparison_drawer'
            QFileDialog.getSaveFileName = staticmethod(
                lambda *args, **kwargs: (str(out_path), 'CSV Files (*.csv)')
            )
            QMessageBox.information = staticmethod(lambda *args, **kwargs: None)
            try:
                self.widget._export_drawer_data()
            finally:
                QFileDialog.getSaveFileName = original_dialog
                QMessageBox.information = original_info

            with out_path.with_suffix('.csv').open(newline='') as handle:
                rows = list(csv.reader(handle))

        headers = [
            self.widget._drawer_table.horizontalHeaderItem(col).text()
            for col in range(self.widget._drawer_table.columnCount())
        ]
        self.assertEqual(rows[0], headers)
        self.assertGreater(len(rows), 1)

    def test_comparison_k_units_use_sidebar_control_and_convert_axis(self):
        self.assertTrue(hasattr(self.widget, '_sect_units'))
        self.assertTrue(self.widget._sect_units.isHidden())

        self.widget.on_plot_type_changed('K-Values')
        self.widget.set_display_unit(HydraulicConductivityUnit.M_PER_DAY)
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        self.assertFalse(self.widget._sect_units.isHidden())
        self.assertIn('m/d', ax.get_ylabel())

        headers = [
            self.widget._drawer_table.horizontalHeaderItem(col).text()
            for col in range(self.widget._drawer_table.columnCount())
        ]
        self.assertIn('K (m/d)', headers)

    def test_k_value_overlay_staggers_value_labels_between_datasets(self):
        self.widget.on_plot_type_changed('K-Values')
        self.widget.set_display_mode('overlay')
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        self.assertEqual(len(ax.texts), len(ax.patches))

        ratios = [
            round(text.get_position()[1] / bar.get_height(), 4)
            for bar, text in zip(ax.patches, ax.texts)
            if bar.get_height() > 0
        ]

        self.assertGreater(len(set(ratios)), 1)

    def test_reset_view_rebuilds_default_k_value_limits(self):
        self.widget.on_plot_type_changed('K-Values')
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        original_ylim = ax.get_ylim()
        self.widget.zoom_in()
        zoomed_ylim = ax.get_ylim()

        self.assertNotEqual(original_ylim, zoomed_ylim)

        self.widget.reset_view()
        reset_ax = self.widget.figure.axes[0]

        self.assertEqual(reset_ax.get_ylim(), original_ylim)

    def test_combined_plot_respects_grid_toggle(self):
        self.widget.on_plot_type_changed('Combined')
        self.widget.show_grid = False
        self.widget.refresh_plot()

        self.assertTrue(self.widget.figure.axes)
        self.assertFalse(any(
            line.get_visible()
            for ax in self.widget.figure.axes
            for line in ax.yaxis.get_gridlines()
        ))

    def test_zoom_targets_clicked_subplot_in_grid_mode(self):
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('grid')
        self.widget.refresh_plot()

        first_ax, second_ax = self.widget.figure.axes[:2]
        first_xlim_before = first_ax.get_xlim()
        second_xlim_before = second_ax.get_xlim()

        self.widget._on_canvas_click(SimpleNamespace(inaxes=second_ax))
        self.widget.zoom_in()

        self.assertEqual(first_ax.get_xlim(), first_xlim_before)
        self.assertNotEqual(second_ax.get_xlim(), second_xlim_before)
        self.assertIs(self.widget.current_ax, second_ax)

    def test_zoom_falls_back_to_first_subplot_when_none_selected(self):
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('grid')
        self.widget.refresh_plot()

        first_ax, second_ax = self.widget.figure.axes[:2]
        first_xlim_before = first_ax.get_xlim()
        second_xlim_before = second_ax.get_xlim()
        self.widget.current_ax = None

        self.widget.zoom_in()

        self.assertNotEqual(first_ax.get_xlim(), first_xlim_before)
        self.assertEqual(second_ax.get_xlim(), second_xlim_before)
        self.assertIs(self.widget.current_ax, first_ax)

    def test_toolbar_uses_plot_workspace_style_language(self):
        toolbar = self.widget.create_toolbar()

        self.assertEqual(toolbar.objectName(), 'pw-toolbar')
        self.assertEqual(self.widget.plot_selector.objectName(), 'pw-style-sel')
        self.assertTrue(self.widget.zoom_in_btn.property('pw-btn'))
        self.assertTrue(self.widget._tb_sidebar_btn.property('pw-chk'))
        self.assertTrue(hasattr(self.widget, '_sw_grid'))
        self.assertTrue(hasattr(self.widget, '_sw_legend'))
        self.assertGreaterEqual(
            self.widget._legend_loc_combo.findText('Outside top - right'),
            0,
        )
        self.assertGreaterEqual(
            self.widget._legend_layout_combo.findText('Vertical (1 column)'),
            0,
        )

        toolbar.deleteLater()

    def test_outside_top_right_legend_can_be_vertical_and_gets_margin(self):
        loc_idx = self.widget._legend_loc_combo.findText('Outside top - right')
        layout_idx = self.widget._legend_layout_combo.findText('Vertical (1 column)')

        self.widget._legend_loc_combo.setCurrentIndex(loc_idx)
        self.widget._legend_layout_combo.setCurrentIndex(layout_idx)
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('overlay')
        self.widget.refresh_plot()

        legend = self.widget.figure.axes[0].get_legend()

        self.assertEqual(self.widget.current_style.legend_loc, 'lower right')
        self.assertEqual(self.widget.current_style.legend_bbox_to_anchor, (1.0, 1.12))
        self.assertEqual(getattr(legend, '_ncols', None), 1)
        self.assertLessEqual(self.widget.figure.subplotpars.top, 0.72)

    def test_legend_layout_can_be_horizontal_when_requested(self):
        layout_idx = self.widget._legend_layout_combo.findText('Horizontal (fit)')

        self.widget._legend_layout_combo.setCurrentIndex(layout_idx)
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('overlay')
        self.widget.refresh_plot()

        legend = self.widget.figure.axes[0].get_legend()

        self.assertEqual(self.widget.current_style.legend_ncol, 0)
        self.assertEqual(getattr(legend, '_ncols', None), 2)

    def test_distribution_overlay_legend_is_group_structured(self):
        self.widget.set_datasets([
            DummyDatasetTab('A-1', 1.0, group='Layer A'),
            DummyDatasetTab('A-2', 1.5, group='Layer A'),
            DummyDatasetTab('B-1', 3.0, group='Layer B'),
        ])
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('overlay')
        self.widget.breakdown = 'dataset'  # members drawn individually
        self.widget.refresh_plot()

        legend = self.widget.figure.axes[0].get_legend()
        labels = [t.get_text() for t in legend.get_texts()]
        # Bold group headers with their (left-aligned, un-indented) members.
        self.assertIn('Layer A', labels)
        self.assertIn('Layer B', labels)
        self.assertIn('A-1', labels)
        self.assertIn('B-1', labels)
        header_weights = [
            t.get_fontweight() for t in legend.get_texts()
            if t.get_text() in ('Layer A', 'Layer B')
        ]
        self.assertTrue(all(weight == 'bold' for weight in header_weights))

    def test_grid_mode_grows_canvas_height_for_scrolling(self):
        self.widget.set_datasets([
            DummyDatasetTab(f'S{i}', 1.0 + i) for i in range(5)
        ])
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('grid')
        self.widget.refresh_plot()

        rows = self.widget._facet_dims(5)[0]
        self.assertEqual(
            self.widget.canvas.minimumHeight(), rows * self.widget.GRID_ROW_HEIGHT
        )

        # Overlay fills the viewport again (no forced scroll height).
        self.widget.set_display_mode('overlay')
        self.widget.refresh_plot()
        self.assertEqual(self.widget.canvas.minimumHeight(), 220)

    def test_tick_size_applies_to_distribution_overlay(self):
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('overlay')
        self.widget._update_style_field('tick_fontsize', 18)

        ax = self.widget.figure.axes[0]
        sizes = [t.get_fontsize() for t in ax.get_xticklabels()]
        self.assertTrue(any(abs(size - 18) < 0.5 for size in sizes))

    def test_tick_size_applies_to_k_value_x_axis_in_both_layouts(self):
        self.widget.on_plot_type_changed('K-Values')
        self.widget.set_display_mode('overlay')
        self.widget._update_style_field('tick_fontsize', 18)

        overlay_ax = self.widget.figure.axes[0]
        self.assertTrue(overlay_ax.get_xticklabels())
        self.assertTrue(all(
            abs(tick.get_fontsize() - 18) < 0.5
            for tick in overlay_ax.get_xticklabels()
        ))

        self.widget.set_display_mode('grid')

        self.assertTrue(self.widget.figure.axes)
        for ax in self.widget.figure.axes:
            self.assertTrue(ax.get_xticklabels())
            self.assertTrue(all(
                abs(tick.get_fontsize() - 18) < 0.5
                for tick in ax.get_xticklabels()
            ))

    def test_sidebar_can_toggle_open_and_closed(self):
        self.widget.resize(1000, 600)
        self.widget.show()
        APP.processEvents()

        self.assertFalse(self.widget.sidebar_visible)
        self.assertEqual(self.widget._sidebar.width(), 0)
        self.assertEqual(self.widget._sidebar.maximumWidth(), 0)
        self.assertFalse(self.widget._tb_sidebar_btn.isChecked())
        self.assertEqual(self.widget._toggle_handle.objectName(), 'pw-toggle-handle')

        self.widget._toggle_sidebar()
        self.widget._sidebar_anim.setCurrentTime(self.widget._sidebar_anim.duration())
        APP.processEvents()

        self.assertTrue(self.widget.sidebar_visible)
        self.assertTrue(self.widget._tb_sidebar_btn.isChecked())
        self.assertTrue(self.widget._tb_sidebar_btn.property('active'))
        self.assertEqual(self.widget._sidebar.width(), SZ.PLOT_SIDEBAR_W)
        self.assertEqual(self.widget._sidebar.minimumWidth(), SZ.PLOT_SIDEBAR_W)
        self.assertEqual(self.widget._sidebar.maximumWidth(), SZ.PLOT_SIDEBAR_W)

        self.widget._toggle_sidebar()
        self.widget._sidebar_anim.setCurrentTime(self.widget._sidebar_anim.duration())
        APP.processEvents()

        self.assertFalse(self.widget.sidebar_visible)
        self.assertFalse(self.widget._tb_sidebar_btn.isChecked())
        self.assertFalse(self.widget._tb_sidebar_btn.property('active'))
        self.assertEqual(self.widget._sidebar.width(), 0)
        self.assertEqual(self.widget._sidebar.minimumWidth(), 0)
        self.assertEqual(self.widget._sidebar.maximumWidth(), 0)

    def test_dataset_color_rows_rebuild_when_datasets_change(self):
        self.assertEqual(
            set(self.widget._dataset_color_rows),
            {'Sample A', 'Sample B'},
        )

        self.widget.set_datasets([DummyDatasetTab('Sample C', 1.0)])

        self.assertEqual(set(self.widget._dataset_color_rows), {'Sample C'})

    def test_distribution_uses_dataset_color_override(self):
        self.widget._dataset_color_overrides['Sample A'] = '#123456'
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('overlay')
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        self.assertEqual(ax.lines[0].get_color().lower(), '#123456')

    def test_distribution_uses_group_color_and_distinct_line_styles(self):
        self.widget.set_datasets([
            DummyDatasetTab('Layer A-1', 1.0, group='Layer A'),
            DummyDatasetTab('Layer A-2', 1.1, group='Layer A'),
            DummyDatasetTab('Layer B-1', 1.2, group='Layer B'),
        ])
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('overlay')
        # Per-dataset breakdown keeps group color + distinct member line styles
        # (the per-group breakdown instead aggregates to one curve per group).
        self.widget.breakdown = 'dataset'
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        self.assertEqual(ax.lines[0].get_color(), ax.lines[1].get_color())
        self.assertNotEqual(ax.lines[0].get_linestyle(), ax.lines[1].get_linestyle())
        self.assertNotEqual(ax.lines[0].get_color(), ax.lines[2].get_color())
        legend = ax.get_legend()
        handles = getattr(legend, 'legend_handles', getattr(legend, 'legendHandles', []))
        self.assertNotEqual(handles[0].get_linestyle(), handles[1].get_linestyle())

    def test_k_overlay_uses_dataset_color_override(self):
        self.widget._dataset_color_overrides['Sample A'] = '#123456'
        self.widget.on_plot_type_changed('K-Values')
        self.widget.set_display_mode('overlay')
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        self.assertEqual(to_hex(ax.patches[0].get_facecolor()).lower(), '#123456')

    def test_wheel_zoom_targets_hovered_subplot(self):
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('grid')
        self.widget.refresh_plot()

        first_ax, second_ax = self.widget.figure.axes[:2]
        first_xlim_before = first_ax.get_xlim()
        second_xlim_before = second_ax.get_xlim()

        self.widget._on_canvas_scroll(SimpleNamespace(inaxes=second_ax, step=1))

        self.assertEqual(first_ax.get_xlim(), first_xlim_before)
        self.assertNotEqual(second_ax.get_xlim(), second_xlim_before)
        self.assertIs(self.widget.current_ax, second_ax)

    def test_double_click_resets_only_active_subplot(self):
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('grid')
        self.widget.refresh_plot()

        first_ax, second_ax = self.widget.figure.axes[:2]
        first_xlim_before = first_ax.get_xlim()
        second_xlim_before = second_ax.get_xlim()
        self.widget._on_canvas_scroll(SimpleNamespace(inaxes=second_ax, step=1))

        self.assertNotEqual(second_ax.get_xlim(), second_xlim_before)

        self.widget._on_canvas_click(SimpleNamespace(inaxes=second_ax, dblclick=True, button=1, key=None))

        self.assertEqual(first_ax.get_xlim(), first_xlim_before)
        self.assertEqual(second_ax.get_xlim(), second_xlim_before)

    def test_shift_drag_pans_only_active_subplot(self):
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('grid')
        self.widget.refresh_plot()

        first_ax, second_ax = self.widget.figure.axes[:2]
        first_xlim_before = first_ax.get_xlim()
        second_xlim_before = second_ax.get_xlim()

        self.widget._on_canvas_click(
            SimpleNamespace(inaxes=second_ax, dblclick=False, button=1, key='shift', xdata=1.0, ydata=50.0)
        )
        self.widget._on_canvas_motion(SimpleNamespace(inaxes=second_ax, xdata=2.0, ydata=60.0))
        self.widget._on_canvas_release(SimpleNamespace(inaxes=second_ax))

        self.assertEqual(first_ax.get_xlim(), first_xlim_before)
        self.assertNotEqual(second_ax.get_xlim(), second_xlim_before)

    def test_active_subplot_highlight_moves_with_selection(self):
        self.widget.on_plot_type_changed('Distribution')
        self.widget.set_display_mode('grid')
        self.widget.refresh_plot()

        first_ax, second_ax = self.widget.figure.axes[:2]
        self.assertGreater(first_ax.spines['left'].get_linewidth(), second_ax.spines['left'].get_linewidth())

        self.widget._on_canvas_click(SimpleNamespace(inaxes=second_ax, dblclick=False, button=1, key=None))

        self.assertGreater(second_ax.spines['left'].get_linewidth(), first_ax.spines['left'].get_linewidth())


class TestKHistogramRenderer(unittest.TestCase):
    """Direct coverage of render_k_histogram's frequency/N/collapse options."""

    # Two clusters with a wide interior gap: a low band and a high band with no
    # K-values in between, so several middle bins are empty in every scope.
    GAPPED = [
        {'label': 'Low', 'color': '#6b8e23',
         'values': [1e-6, 1.1e-6, 1.2e-6, 1.3e-6, 9e-7, 1.0e-6]},
        {'label': 'High', 'color': '#b46428',
         'values': [2e-4, 2.2e-4, 2.5e-4, 2.8e-4, 3.0e-4]},
    ]

    def test_drop_empty_collapses_interior_bins(self):
        collapsed = Figure().add_subplot(1, 1, 1)
        render_k_histogram(collapsed, self.GAPPED, drop_empty_bins=True)

        full = Figure().add_subplot(1, 1, 1)
        render_k_histogram(full, self.GAPPED, drop_empty_bins=False)

        # Collapsing all-empty interior bins leaves strictly fewer bars than the
        # true-axis view, and uses a categorical x-axis (integer tick positions).
        self.assertGreater(len(full.patches), len(collapsed.patches))
        self.assertEqual(list(collapsed.get_xticks()),
                         list(range(len(collapsed.get_xticks()))))
        # Every retained column carries data in at least one scope (no kept bin
        # is empty across all scopes). Bars are laid out scope-by-scope, so
        # column j is patches[j] + patches[cols + j].
        cols = len(collapsed.get_xticks())
        heights = [p.get_height() for p in collapsed.patches]
        for j in range(cols):
            column_total = sum(heights[j::cols])
            self.assertGreater(column_total, 0)

    def test_frequency_mode_uses_integer_bar_heights(self):
        ax = Figure().add_subplot(1, 1, 1)
        render_k_histogram(ax, self.GAPPED, drop_empty_bins=True, y_mode='frequency')

        self.assertEqual(ax.get_ylabel(), 'Frequency (count)')
        heights = [p.get_height() for p in ax.patches]
        # Counts are whole numbers and account for every value across scopes.
        self.assertTrue(all(abs(h - round(h)) < 1e-9 for h in heights))
        total = sum(len(s['values']) for s in self.GAPPED)
        self.assertEqual(sum(round(h) for h in heights), total)

    def test_show_n_annotations_track_toggle(self):
        on = Figure().add_subplot(1, 1, 1)
        render_k_histogram(on, self.GAPPED, show_n=True)
        self.assertTrue(any(t.get_text().isdigit() for t in on.texts))

        off = Figure().add_subplot(1, 1, 1)
        render_k_histogram(off, self.GAPPED, show_n=False)
        self.assertFalse(any(t.get_text().isdigit() for t in off.texts))


if __name__ == '__main__':
    unittest.main(verbosity=2)
