"""
Regression tests for plot workspace wiring across plot modes.
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

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from data_loader import GrainSizeData
from gui.plot_workspace import PlotWorkspace


APP = QApplication.instance() or QApplication([])


def build_dataset(name: str = 'Sample A') -> GrainSizeData:
    return GrainSizeData(
        sample_name=name,
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
        percent_passing=[100.0, 95.0, 82.0, 61.0, 38.0, 14.0, 4.0],
    )


class TestPlotWorkspaceWiring(unittest.TestCase):
    def setUp(self):
        self.workspace = PlotWorkspace(build_dataset())
        self.workspace.resize(1200, 800)
        self.workspace.show()
        APP.processEvents()

    def tearDown(self):
        self.workspace.hide()
        self.workspace.deleteLater()

    def test_k_value_plot_becomes_active_axis_and_respects_grid_legend_toggles(self):
        self.workspace.add_k_results({'Hazen': 1.0e-4, 'Beyer': 1.5e-4})
        self.workspace.current_plot_type = 'k-values'
        self.workspace.show_grid = False
        self.workspace.show_legend = False

        self.workspace.refresh_plot()

        ax = self.workspace.plot_widget.current_ax
        self.assertIs(self.workspace.plot_widget.k_value_ax, ax)
        self.assertIsNone(self.workspace.plot_widget.grain_size_ax)
        self.assertEqual(self.workspace.plot_widget.active_axes, [ax])
        self.assertIsNone(ax.get_legend())
        self.assertFalse(any(line.get_visible() for line in ax.yaxis.get_gridlines()))

    def test_combined_plot_honors_d_line_toggle(self):
        self.workspace.add_k_results({'Hazen': 1.0e-4, 'Beyer': 1.5e-4})
        self.workspace.current_plot_type = 'combined'

        self.workspace.show_dlines = False
        self.workspace.refresh_plot()
        labels_without = self.workspace.plot_widget.grain_size_ax.get_legend_handles_labels()[1]

        self.workspace.show_dlines = True
        self.workspace.refresh_plot()
        labels_with = self.workspace.plot_widget.grain_size_ax.get_legend_handles_labels()[1]

        self.assertFalse(any(label.startswith('D10') for label in labels_without))
        self.assertTrue(any(label.startswith('D10') for label in labels_with))
        self.assertTrue(any(label.startswith('D30') for label in labels_with))
        self.assertTrue(any(label.startswith('D60') for label in labels_with))

    def test_zoom_in_uses_current_active_axis(self):
        self.workspace.add_k_results({'Hazen': 1.0e-4, 'Beyer': 1.5e-4})
        self.workspace.current_plot_type = 'k-values'
        self.workspace.refresh_plot()

        before_xlim = self.workspace.plot_widget.current_ax.get_xlim()
        before_ylim = self.workspace.plot_widget.current_ax.get_ylim()
        self.workspace.zoom_in()
        after_xlim = self.workspace.plot_widget.current_ax.get_xlim()
        after_ylim = self.workspace.plot_widget.current_ax.get_ylim()

        self.assertNotEqual(before_xlim, after_xlim)
        self.assertNotEqual(before_ylim, after_ylim)

    def test_distribution_reset_view_adds_curve_headroom(self):
        self.workspace.current_plot_type = 'distribution'
        self.workspace.refresh_plot()

        ax = self.workspace.plot_widget.current_ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        self.assertLess(xlim[0], min(self.workspace.dataset.particle_sizes) * 0.5)
        self.assertGreater(xlim[1], max(self.workspace.dataset.particle_sizes) * 2)
        self.assertGreater(ylim[1], 100.0)

    def test_distribution_zoom_preserves_positive_log_limits(self):
        self.workspace.current_plot_type = 'distribution'
        self.workspace.refresh_plot()

        before_xlim = self.workspace.plot_widget.current_ax.get_xlim()
        self.workspace.zoom_in()
        after_xlim = self.workspace.plot_widget.current_ax.get_xlim()

        self.assertNotEqual(before_xlim, after_xlim)
        self.assertGreater(after_xlim[0], 0.0)
        self.assertGreater(after_xlim[1], after_xlim[0])

    def test_distribution_wheel_zoom_updates_axis_inputs(self):
        self.workspace.current_plot_type = 'distribution'
        self.workspace.refresh_plot()

        ax = self.workspace.plot_widget.current_ax
        before_xlim = ax.get_xlim()

        self.workspace.plot_widget.interactions.on_scroll(SimpleNamespace(inaxes=ax, step=1))

        after_xlim = ax.get_xlim()
        self.assertNotEqual(before_xlim, after_xlim)
        self.assertEqual(self.workspace._in_xmin.text(), f"{after_xlim[0]:.6g}")
        self.assertEqual(self.workspace._in_xmax.text(), f"{after_xlim[1]:.6g}")

    def test_plot_widget_canvas_registers_shared_interaction_callbacks(self):
        callbacks = self.workspace.plot_widget.canvas.callbacks.callbacks

        self.assertTrue(callbacks.get('button_press_event'))
        self.assertTrue(callbacks.get('scroll_event'))
        self.assertTrue(callbacks.get('motion_notify_event'))
        self.assertTrue(callbacks.get('button_release_event'))

    def test_toolbar_sidebar_toggle_sits_with_left_side_controls(self):
        self.assertLess(self.workspace._tb_sidebar_btn.x(), self.workspace._chk_grid.x())

    def test_legend_outside_bottom_reserves_margin(self):
        loc_idx = self.workspace._legend_loc_combo.findText('Outside bottom - center')
        layout_idx = self.workspace._legend_layout_combo.findText('Vertical (1 column)')

        self.workspace._legend_loc_combo.setCurrentIndex(loc_idx)
        self.workspace._legend_layout_combo.setCurrentIndex(layout_idx)
        self.workspace.refresh_plot()

        legend = self.workspace.plot_widget.current_ax.get_legend()

        self.assertEqual(self.workspace._effective_style().legend_loc, 'upper center')
        self.assertEqual(
            self.workspace._effective_style().legend_bbox_to_anchor,
            (0.5, -0.22),
        )
        self.assertEqual(getattr(legend, '_ncols', None), 1)
        self.assertGreaterEqual(self.workspace.plot_widget.figure.subplotpars.bottom, 0.24)

    def test_more_plots_dropdown_uses_dedicated_toolbar_style(self):
        self.assertEqual(self.workspace._more_plots.objectName(), 'pw-more-plots-sel')
        self.assertEqual(self.workspace._more_plots.maxVisibleItems(), 6)
        self.assertNotEqual(
            self.workspace._more_plots.objectName(),
            self.workspace._style_sel.objectName(),
        )

    def test_floating_handle_stays_visible_on_chart_edge(self):
        self.workspace._position_toggle_handle()
        collapsed_x = self.workspace._toggle_handle.x()

        self.workspace._sidebar_anim.stop()
        self.workspace._sidebar.setMaximumWidth(220)
        self.workspace._position_toggle_handle()
        expanded_x = self.workspace._toggle_handle.x()

        self.assertEqual(collapsed_x, 0)
        self.assertEqual(expanded_x, 0)

    def test_histogram_uses_retained_percentages(self):
        self.workspace.current_plot_type = 'histogram'
        self.workspace.refresh_plot()

        ax = self.workspace.plot_widget.current_ax
        heights = [patch.get_height() for patch in ax.patches]

        self.assertTrue(all(height >= 0 for height in heights))
        self.assertAlmostEqual(sum(heights), 100.0, places=6)
        self.assertEqual(ax.get_ylabel(), 'Weight (%)')
        tick_labels = [tick.get_text() for tick in ax.get_xticklabels()]
        self.assertTrue(any('sand' in label.lower() for label in tick_labels))
        self.assertTrue(any('gravel' in label.lower() for label in tick_labels))

    def test_histogram_export_data_writes_fraction_weight_rows(self):
        self.workspace.current_plot_type = 'histogram'
        self.workspace.refresh_plot()

        original_dialog = QFileDialog.getSaveFileName
        original_info = QMessageBox.information
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / 'histogram_export'
            QFileDialog.getSaveFileName = staticmethod(
                lambda *args, **kwargs: (str(out_path), 'CSV Files (*.csv)')
            )
            QMessageBox.information = staticmethod(lambda *args, **kwargs: None)
            try:
                self.workspace.export_data()
            finally:
                QFileDialog.getSaveFileName = original_dialog
                QMessageBox.information = original_info

            written = out_path.with_suffix('.csv')
            with written.open(newline='') as handle:
                rows = list(csv.reader(handle))

        self.assertEqual(
            rows[0],
            [
                'Particle-size fraction',
                'Lower size (mm)',
                'Upper size (mm)',
                'Interval',
                'Weight (%)',
            ],
        )
        self.assertTrue(any('sand' in row[0].lower() for row in rows[1:]))
        self.assertAlmostEqual(sum(float(row[4]) for row in rows[1:]), 100.0, places=6)

    def test_k_value_sidebar_context_hides_distribution_specific_controls(self):
        self.workspace.add_k_results({'Hazen': 1.0e-4, 'Beyer': 1.5e-4})
        self.workspace.current_plot_type = 'k-values'

        self.workspace.refresh_plot()

        self.assertTrue(self.workspace._row_xmin.isHidden())
        self.assertTrue(self.workspace._row_xmax.isHidden())
        self.assertFalse(self.workspace._row_units.isHidden())
        self.assertTrue(self.workspace._row_zones.isHidden())
        self.assertTrue(self.workspace._row_dlines.isHidden())
        self.assertTrue(self.workspace._row_fill.isHidden())
        self.assertTrue(self.workspace._row_markers.isHidden())
        self.assertEqual(self.workspace._lbl_ymin.text(), 'Y min (m/d)')
        self.assertEqual(self.workspace._lbl_ymax.text(), 'Y max (m/d)')

    def test_distribution_sidebar_context_hides_k_value_units(self):
        self.workspace.current_plot_type = 'distribution'

        self.workspace.refresh_plot()

        self.assertFalse(self.workspace._row_xmin.isHidden())
        self.assertFalse(self.workspace._row_xmax.isHidden())
        self.assertTrue(self.workspace._row_units.isHidden())
        self.assertFalse(self.workspace._row_zones.isHidden())
        self.assertFalse(self.workspace._row_dlines.isHidden())
        self.assertFalse(self.workspace._row_fill.isHidden())
        self.assertFalse(self.workspace._row_markers.isHidden())
        self.assertEqual(self.workspace._lbl_xmin.text(), 'X min (mm)')
        self.assertEqual(self.workspace._lbl_ymax.text(), 'Y max (%)')

    def test_k_value_plot_shows_grid_and_warning_hatch(self):
        self.workspace.add_k_results(
            {'Hazen': 1.0e-4, 'Beyer': 1.5e-4},
            flagged_methods={'Beyer'},
        )
        self.workspace.current_plot_type = 'k-values'
        self.workspace.show_grid = True
        self.workspace.refresh_plot()

        ax = self.workspace.plot_widget.current_ax
        hatches = [patch.get_hatch() for patch in ax.patches]

        self.assertTrue(any(line.get_visible() for line in ax.yaxis.get_gridlines()))
        self.assertIn('////', hatches)

    def test_k_value_plot_legend_clarifies_arithmetic_and_geometric_means(self):
        self.workspace.add_k_results({'Hazen': 1.0e-4, 'Beyer': 1.6e-4})
        self.workspace.current_plot_type = 'k-values'

        self.workspace.refresh_plot()

        labels = self.workspace.plot_widget.current_ax.get_legend_handles_labels()[1]
        self.assertTrue(any(label.startswith('Arithmetic mean:') for label in labels))
        self.assertTrue(any(label.startswith('Geometric mean:') for label in labels))

    def test_k_value_label_toggle_hides_bar_value_labels(self):
        self.workspace.add_k_results({'Hazen': 1.0e-4, 'Beyer': 1.5e-4})
        self.workspace.current_plot_type = 'k-values'

        self.workspace._sw_k_labels.setChecked(False, animate=False)
        self.workspace._on_sidebar_toggle_changed(False)

        ax = self.workspace.plot_widget.current_ax
        self.assertEqual(len(ax.texts), 0)

    def test_k_value_plot_places_value_labels_close_to_bar_tops(self):
        self.workspace.add_k_results({'Hazen': 1.0e-4, 'Beyer': 1.5e-4})
        self.workspace.current_plot_type = 'k-values'

        self.workspace.refresh_plot()

        ax = self.workspace.plot_widget.current_ax
        bars = ax.patches
        self.assertEqual(len(ax.texts), len(bars))

        for bar, text in zip(bars, ax.texts):
            ratio = text.get_position()[1] / bar.get_height()
            self.assertGreater(ratio, 1.0)
            self.assertLess(ratio, 1.05)

    def test_svg_export_adds_extension_and_uses_requested_format(self):
        self.workspace.current_plot_type = 'distribution'
        self.workspace.refresh_plot()

        original_dialog = QFileDialog.getSaveFileName
        original_info = QMessageBox.information
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / 'plot_without_extension'
            exported = []
            self.workspace.plot_exported.connect(exported.append)
            QFileDialog.getSaveFileName = staticmethod(
                lambda *args, **kwargs: (str(out_path), 'SVG Files (*.svg)')
            )
            QMessageBox.information = staticmethod(lambda *args, **kwargs: None)
            try:
                self.workspace.export_plot('svg')
            finally:
                QFileDialog.getSaveFileName = original_dialog
                QMessageBox.information = original_info

            written = out_path.with_suffix('.svg')
            content = written.read_text(encoding='utf-8', errors='ignore')

        self.assertEqual(exported, [str(written)])
        self.assertIn('<svg', content[:200].lower())

    def test_cumulative_plot_respects_marker_toggle(self):
        self.workspace.current_plot_type = 'cumulative'
        self.workspace.show_markers = False

        self.workspace.refresh_plot()
        ax = self.workspace.plot_widget.current_ax
        self.assertEqual(ax.lines[0].get_marker(), 'None')

        self.workspace.show_markers = True
        self.workspace.refresh_plot()
        ax = self.workspace.plot_widget.current_ax
        self.assertNotEqual(ax.lines[0].get_marker(), 'None')

    def test_combined_plot_shows_k_side_legend(self):
        self.workspace.add_k_results({'Hazen': 1.0e-4, 'Beyer': 1.5e-4})
        self.workspace.current_plot_type = 'combined'
        self.workspace.show_legend = True
        self.workspace.refresh_plot()

        self.assertIsNotNone(self.workspace.plot_widget.k_value_ax)
        self.assertIsNotNone(self.workspace.plot_widget.k_value_ax.get_legend())

    def test_combined_plot_click_selects_right_subplot_for_toolbar_zoom(self):
        self.workspace.add_k_results({'Hazen': 1.0e-4, 'Beyer': 1.5e-4})
        self.workspace.current_plot_type = 'combined'
        self.workspace.refresh_plot()

        left_ax = self.workspace.plot_widget.grain_size_ax
        right_ax = self.workspace.plot_widget.k_value_ax
        left_xlim_before = left_ax.get_xlim()
        right_xlim_before = right_ax.get_xlim()

        self.workspace.plot_widget.interactions.on_click(
            SimpleNamespace(inaxes=right_ax, dblclick=False, button=1, key=None)
        )
        self.workspace.zoom_in()

        self.assertEqual(left_ax.get_xlim(), left_xlim_before)
        self.assertNotEqual(right_ax.get_xlim(), right_xlim_before)
        self.assertIs(self.workspace.plot_widget.current_ax, right_ax)

    def test_distribution_refresh_only_requests_one_canvas_draw(self):
        draw_calls = 0
        original_draw = self.workspace.plot_widget.canvas.draw

        def counted_draw(*args, **kwargs):
            nonlocal draw_calls
            draw_calls += 1
            return original_draw(*args, **kwargs)

        self.workspace.plot_widget.canvas.draw = counted_draw
        self.workspace.current_plot_type = 'distribution'

        self.workspace.refresh_plot()

        self.assertEqual(draw_calls, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
