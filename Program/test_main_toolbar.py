"""
Regression tests for the top-level application toolbar.
"""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, 'Program')

from PyQt6.QtWidgets import QApplication

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
        self.assertEqual(self.toolbar._add_btn.iconSize().width(), 13)
        self.assertEqual(self.toolbar._calc_btn.iconSize().width(), 13)
        self.assertEqual(self.toolbar._help_btn.iconSize().width(), 13)
        self.assertEqual(self.toolbar._nav_btns[0].iconSize().width(), 13)


if __name__ == '__main__':
    unittest.main(verbosity=2)
