"""
Regression tests for startup splash progress behavior.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication

from Splash.simple_splash import SimpleSplash


APP = QApplication.instance() or QApplication([])


class TestSimpleSplash(unittest.TestCase):
    def setUp(self):
        self.splash = SimpleSplash()

    def tearDown(self):
        self.splash.close()
        self.splash.deleteLater()

    def test_progress_target_does_not_regress(self):
        self.splash.set_progress(40, "Loading data models", "Preparing file loaders.")
        first_target = self.splash._target_progress

        self.splash.set_progress(32, "Loading calculation methods", "Preparing equations.")

        self.assertEqual(first_target, 40)
        self.assertEqual(self.splash._target_progress, 40)


if __name__ == "__main__":
    unittest.main(verbosity=2)
