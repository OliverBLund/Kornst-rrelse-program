"""
Regression tests for the top-level application toolbar.
"""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, 'Program')

from PyQt6.QtWidgets import QApplication, QPushButton

from gui.main_window import _AppToolbar


APP = QApplication.instance() or QApplication([])


class TestAppToolbar(unittest.TestCase):
    def setUp(self):
        self.toolbar = _AppToolbar()
        self.toolbar.resize(900, self.toolbar.height())
        self.toolbar.show()
        APP.processEvents()

    def tearDown(self):
        self.toolbar.hide()
        self.toolbar.deleteLater()

    def test_badge_stays_inside_individual_samples_tab(self):
        button = self.toolbar._nav_btns[0]
        badge = self.toolbar._badge_lbls[0]

        self.toolbar.set_badge(0, 12)
        APP.processEvents()

        self.assertTrue(badge.isVisible())
        self.assertGreaterEqual(button.width(), button.minimumWidth())
        self.assertLessEqual(badge.x() + badge.width(), button.width())

    def test_toolbar_uses_explicit_chrome_icon_sizes(self):
        self.assertEqual(self.toolbar._log_btn.iconSize().width(), 13)
        self.assertEqual(self.toolbar._help_btn.iconSize().width(), 13)
        self.assertEqual(self.toolbar._nav_btns[0].iconSize().width(), 13)

    def test_log_toolbar_button_emits_and_shows_warning_badge(self):
        emitted = []
        self.toolbar.log_clicked.connect(lambda: emitted.append(True))

        self.toolbar._log_btn.click()
        self.toolbar.set_log_badge(3)
        APP.processEvents()

        self.assertEqual(emitted, [True])
        self.assertTrue(self.toolbar._log_badge.isVisible())
        self.assertLessEqual(
            self.toolbar._log_badge.x() + self.toolbar._log_badge.width(),
            self.toolbar._log_btn.width(),
        )

        self.toolbar.set_log_badge(0)
        self.assertFalse(self.toolbar._log_badge.isVisible())

    def test_toolbar_no_longer_exposes_import_or_calculate_buttons(self):
        self.assertFalse(hasattr(self.toolbar, "_add_btn"))
        self.assertFalse(hasattr(self.toolbar, "add_files_mode_clicked"))
        self.assertFalse(hasattr(self.toolbar, "_calc_btn"))
        self.assertFalse(hasattr(self.toolbar, "calculate_clicked"))

        button_texts = [
            button.text().strip()
            for button in self.toolbar.findChildren(QPushButton)
        ]
        self.assertNotIn("Add Data", button_texts)
        self.assertNotIn("Calculate K", button_texts)

    def test_badge_font_uses_valid_point_size(self):
        badge = self.toolbar._badge_lbls[0]

        self.assertGreater(badge.font().pointSize(), 0)
        self.assertEqual(badge.font().pixelSize(), -1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
