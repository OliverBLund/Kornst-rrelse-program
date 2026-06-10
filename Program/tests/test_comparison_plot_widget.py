"""
Regression tests for comparison plot widget behavior.
"""

import os
import sys
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, 'Program')

from matplotlib.colors import to_hex
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from data_loader import GrainSizeData
from gui.comparison_plot_widget import ComparisonPlotWidget
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

    def test_plot_type_change_normalizes_grouped_mode(self):
        self.widget.on_plot_type_changed('K-Values')
        self.widget.set_display_mode('grouped')
        self.assertEqual(self.widget.display_mode, 'grouped')
        self.assertFalse(self.widget.grouped_radio.isHidden())

        self.widget.on_plot_type_changed('Distribution')

        self.assertEqual(self.widget.display_mode, 'overlay')
        self.assertTrue(self.widget.grouped_radio.isHidden())
        self.assertTrue(self.widget.overlay_radio.isChecked())

    def test_histogram_uses_non_negative_retained_frequencies(self):
        self.widget.on_plot_type_changed('Histogram')
        self.widget.refresh_plot()

        first_ax = self.widget.figure.axes[0]
        heights = [patch.get_height() for patch in first_ax.patches]

        self.assertTrue(all(height >= 0 for height in heights))
        self.assertAlmostEqual(sum(heights), 100.0, places=6)
        self.assertEqual(first_ax.get_ylabel(), 'Weight (%)')
        self.assertEqual(self.widget.display_mode, 'grid')
        self.assertTrue(self.widget.grid_radio.isChecked())

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
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        labels = [line.get_label() for line in ax.lines]

        self.assertEqual(self.widget.current_plot_type, 'k-distribution')
        self.assertEqual(ax.get_xscale(), 'log')
        self.assertIn('Overall', labels)
        self.assertIn('Layer A', labels)
        self.assertIn('Layer B', labels)
        self.assertIn('Overall Kgeo', labels)

    def test_data_drawer_updates_for_k_distribution(self):
        self.widget.on_plot_type_changed('K Distribution')
        self.widget.refresh_plot()

        headers = [
            self.widget._drawer_table.horizontalHeaderItem(col).text()
            for col in range(self.widget._drawer_table.columnCount())
        ]

        self.assertEqual(self.widget._drawer_title.text(), 'K distribution summary - OK only')
        self.assertIn('sigma lnK', headers)
        self.assertGreaterEqual(self.widget._drawer_table.rowCount(), 1)

        self.widget._set_drawer_visible(True)
        self.widget._drawer_anim.setCurrentTime(self.widget._drawer_anim.duration())
        APP.processEvents()

        self.assertTrue(self.widget.drawer_visible)
        self.assertFalse(self.widget._drawer_table.isHidden())
        self.assertLessEqual(self.widget._drawer.maximumHeight(), 260)

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
        self.assertIn('Kgeo (m/d)', headers)

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
        self.widget.refresh_plot()

        ax = self.widget.figure.axes[0]
        self.assertEqual(ax.lines[0].get_color(), ax.lines[1].get_color())
        self.assertNotEqual(ax.lines[0].get_linestyle(), ax.lines[1].get_linestyle())
        self.assertNotEqual(ax.lines[0].get_color(), ax.lines[2].get_color())

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
