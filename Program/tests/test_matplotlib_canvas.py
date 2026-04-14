"""
Regression tests for embedded matplotlib canvas sizing.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QSizePolicy

from gui.comparison_plot_widget import ComparisonPlotWidget
from gui.plot_widget import PlotWidget


APP = QApplication.instance() or QApplication([])


class TestMatplotlibCanvasSizing(unittest.TestCase):
    def test_plot_widget_canvas_uses_capped_embedded_size_hint(self):
        widget = PlotWidget()
        try:
            hint = widget.canvas.sizeHint()
            self.assertLessEqual(hint.width(), 960)
            self.assertLessEqual(hint.height(), 560)
            self.assertEqual(
                widget.canvas.sizePolicy().verticalPolicy(),
                QSizePolicy.Policy.Expanding,
            )
        finally:
            widget.deleteLater()

    def test_comparison_plot_canvas_uses_capped_embedded_size_hint(self):
        widget = ComparisonPlotWidget()
        try:
            hint = widget.canvas.sizeHint()
            self.assertLessEqual(hint.width(), 960)
            self.assertLessEqual(hint.height(), 560)
            self.assertEqual(
                widget.canvas.sizePolicy().horizontalPolicy(),
                QSizePolicy.Policy.Expanding,
            )
        finally:
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
