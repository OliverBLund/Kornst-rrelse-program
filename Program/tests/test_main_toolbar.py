"""
Regression tests for the top-level application toolbar.
"""

import os
import sys
import unittest
import inspect
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, 'Program')

from PyQt6.QtWidgets import QApplication, QPushButton

from gui.main_window import (
    HOME_TAB,
    INDIVIDUAL_TAB,
    MainWindow,
    _AppToolbar,
)


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
        button = self.toolbar._nav_btns[INDIVIDUAL_TAB]
        badge = self.toolbar._badge_lbls[INDIVIDUAL_TAB]

        self.toolbar.set_badge(INDIVIDUAL_TAB, 12)
        APP.processEvents()

        self.assertTrue(badge.isVisible())
        self.assertGreaterEqual(button.width(), button.minimumWidth())
        self.assertLessEqual(badge.x() + badge.width(), button.width())

    def test_toolbar_uses_explicit_chrome_icon_sizes(self):
        self.assertEqual(self.toolbar._log_btn.iconSize().width(), 13)
        self.assertEqual(self.toolbar._nav_btns[HOME_TAB].iconSize().width(), 13)

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
        self.assertFalse(hasattr(self.toolbar, "_help_btn"))
        self.assertFalse(hasattr(self.toolbar, "help_clicked"))

        button_texts = [
            button.text().strip()
            for button in self.toolbar.findChildren(QPushButton)
        ]
        self.assertNotIn("Add Data", button_texts)
        self.assertNotIn("Calculate K", button_texts)

    def test_badge_font_uses_valid_point_size(self):
        badge = self.toolbar._badge_lbls[INDIVIDUAL_TAB]

        self.assertGreater(badge.font().pointSize(), 0)
        self.assertEqual(badge.font().pixelSize(), -1)

    def test_toolbar_exposes_home_before_the_four_workspace_tabs(self):
        labels = [button.text().strip() for button in self.toolbar._nav_btns]

        self.assertEqual(
            labels,
            ["Home", "Individual Samples", "Comparison", "Reports", "Export"],
        )
        self.assertEqual(self.toolbar._active_index, HOME_TAB)

    def test_welcome_helpers_navigate_without_hiding_the_sidebar(self):
        switched = []
        harness = SimpleNamespace(
            content_stack=SimpleNamespace(currentIndex=lambda: -1),
            _switch_to_tab=lambda index: switched.append(index),
        )

        MainWindow._show_welcome(harness)
        MainWindow._hide_welcome(harness)

        self.assertEqual(switched, [HOME_TAB, INDIVIDUAL_TAB])
        self.assertNotIn("setVisible", inspect.getsource(MainWindow._show_welcome))
        self.assertNotIn("setVisible", inspect.getsource(MainWindow._hide_welcome))

    def test_main_ui_has_no_sidebar_hide_path(self):
        setup_source = inspect.getsource(MainWindow.setup_ui)

        self.assertIn("self.control_panel.setVisible(True)", setup_source)
        self.assertNotIn("self.control_panel.setVisible(False)", setup_source)
        self.assertLess(
            setup_source.index("shell_splitter.addWidget(self.control_panel)"),
            setup_source.index("self.control_panel.setVisible(True)"),
        )

    def test_header_drag_binding_keeps_double_click_on_blank_header_only(self):
        init_source = inspect.getsource(MainWindow.__init__)
        setup_source = inspect.getsource(MainWindow.setup_menus)

        self.assertIn("top_resize_margin=2", init_source)
        self.assertIn("include_children=False", setup_source)
        self.assertIn("_chrome_drag_spacer", setup_source)
        self.assertIn("bind_frameless_drag_widget(spacer", setup_source)
        self.assertIn("allow_double_click_maximize=True", setup_source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
