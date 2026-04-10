"""
Regression tests for the custom splash title layout.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtWidgets import QApplication

from Splash.simple_splash import SimpleSplash


APP = QApplication.instance() or QApplication([])


class TestSimpleSplash(unittest.TestCase):
    def setUp(self):
        self.splash = SimpleSplash()

    def tearDown(self):
        self.splash.close()
        self.splash.deleteLater()

    def test_title_layout_keeps_title_stack_tight(self):
        title_font, grain_pos, analysis_pos = self.splash._title_layout()
        metrics = QFontMetricsF(title_font)
        grain_height = metrics.tightBoundingRect("Grain Size").height()
        grain_top = grain_pos.y() - metrics.ascent()
        grain_bottom = grain_top + grain_height
        analysis_top = analysis_pos.y() - metrics.ascent()
        gap = analysis_top - grain_bottom

        self.assertGreaterEqual(gap, 0.0)
        self.assertLessEqual(gap, 4.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
