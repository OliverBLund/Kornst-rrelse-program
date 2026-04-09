"""
Regression tests for plot workspace wiring across plot modes.
"""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, 'Program')

from PyQt6.QtWidgets import QApplication

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

    def tearDown(self):
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

    def test_histogram_uses_retained_percentages(self):
        self.workspace.current_plot_type = 'histogram'
        self.workspace.refresh_plot()

        ax = self.workspace.plot_widget.current_ax
        heights = [patch.get_height() for patch in ax.patches]

        self.assertTrue(all(height >= 0 for height in heights))
        self.assertAlmostEqual(sum(heights), 100.0, places=6)

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

    def test_combined_plot_shows_k_side_legend(self):
        self.workspace.add_k_results({'Hazen': 1.0e-4, 'Beyer': 1.5e-4})
        self.workspace.current_plot_type = 'combined'
        self.workspace.show_legend = True
        self.workspace.refresh_plot()

        self.assertIsNotNone(self.workspace.plot_widget.k_value_ax)
        self.assertIsNotNone(self.workspace.plot_widget.k_value_ax.get_legend())

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
