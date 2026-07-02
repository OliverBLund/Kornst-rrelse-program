"""
Regression tests for shared theme helpers that affect rendering quality.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication

from gui.theme import (
    build_stylesheet,
    default_matplotlib_font_families,
    default_ui_font_families,
    default_ui_font_family,
    icon,
)


APP = QApplication.instance() or QApplication([])


class TestTheme(unittest.TestCase):
    def test_default_ui_font_family_prefers_native_windows_font(self):
        self.assertEqual(default_ui_font_family("win32"), "Segoe UI")
        self.assertEqual(default_ui_font_family("linux"), "Source Sans 3")

    def test_default_ui_font_families_keep_source_sans_as_fallback(self):
        self.assertEqual(
            default_ui_font_families("win32"),
            ["Segoe UI", "Source Sans 3", "DejaVu Sans"],
        )

    def test_default_matplotlib_font_families_avoid_variable_ui_font(self):
        self.assertEqual(
            default_matplotlib_font_families("win32"),
            ["DejaVu Sans", "Segoe UI"],
        )
        self.assertEqual(default_matplotlib_font_families("linux"), ["DejaVu Sans"])

    def test_icon_helper_renders_requested_small_pixmap(self):
        pixmap = icon("fa6s.chevron-right", "#333333", size=8).pixmap(8, 8)
        self.assertFalse(pixmap.isNull())

    def test_stylesheet_includes_pressed_feedback_for_shared_controls(self):
        stylesheet = build_stylesheet()
        self.assertIn('QWidget#app-toolbar QPushButton[toolaction="true"]:pressed', stylesheet)
        self.assertIn('QPushButton[filterpill="true"]:pressed', stylesheet)
        self.assertIn('QPushButton[sbaction="true"]:pressed', stylesheet)

    def test_stylesheet_uses_readable_tooltips(self):
        stylesheet = build_stylesheet()

        self.assertIn("QToolTip", stylesheet)
        self.assertIn("background: #fffdf7;", stylesheet)
        self.assertIn("color: #2f2f2f;", stylesheet)


if __name__ == "__main__":
    unittest.main(verbosity=2)
