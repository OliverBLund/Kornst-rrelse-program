"""
Regression tests for shared dialog entrance motion.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout

from qt_chrome.frameless_dialog_base import FramelessDialogBase


APP = QApplication.instance() or QApplication([])


class _TestDialog(FramelessDialogBase):
    def __init__(self):
        super().__init__(default_mode="native")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Dialog"))


class TestDialogMotion(unittest.TestCase):
    def test_dialog_show_primes_entrance_animation(self):
        dialog = _TestDialog()
        dialog.resize(240, 120)
        dialog.show()
        APP.processEvents()

        self.assertIsNotNone(dialog._entrance_animation)
        self.assertEqual(dialog._entrance_animation.duration(), 170)

        dialog.hide()
        APP.processEvents()
        self.assertAlmostEqual(dialog.windowOpacity(), 1.0, places=2)
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
