"""Regression tests for shell-level About and Settings dialogs."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QLabel

from gui.about_dialog import AboutDialog
from gui.application_settings_dialog import ApplicationSettingsDialog
from gui.main_window import MainWindow


APP = QApplication.instance() or QApplication(["shell-dialog-test"])


class TestAboutAndApplicationSettings(unittest.TestCase):
    def test_about_uses_correct_project_and_original_tool_attribution(self):
        dialog = AboutDialog()
        text = "\n".join(label.text() for label in dialog.findChildren(QLabel))

        self.assertIn("Version 0.9.7", text)
        self.assertIn("Released 22 July 2026", text)
        self.assertIn("Made in collaboration with", text)
        self.assertIn("Poul Løgstrup Bjerg", text)
        self.assertIn("HydrogeoSieveXL", text)
        self.assertIn("J. F. Devlin", text)
        self.assertIn("jfdevlin.github.io/DevlinWebPages/Software.html", text)
        self.assertIn("10.1007/s10040-015-1255-0", text)
        self.assertEqual(dialog._article_button.text(), "Open cited article (PDF)")
        self.assertNotIn("Supervised by", text)
        dialog.deleteLater()

    def test_settings_uses_plain_sections_and_explicit_restart_behavior(self):
        dialog = ApplicationSettingsDialog(
            show_welcome_on_startup=True,
            ui_font_bump=0,
        )

        self.assertEqual(dialog.text_size_combo.currentText(), "Normal")
        self.assertIn("background: white", dialog.text_size_combo.styleSheet())
        self.assertIn("standard compact", dialog.display_detail_label.text())
        dialog.text_size_combo.setCurrentIndex(1)
        self.assertEqual(dialog.ui_font_bump(), 1)
        self.assertIn("one point", dialog.display_detail_label.text())
        self.assertTrue(dialog.show_welcome_on_startup())
        dialog.deleteLater()

    def test_display_size_save_does_not_partially_mutate_live_font_tokens(self):
        messages = []
        harness = SimpleNamespace(
            _ui_font_bump=0,
            _show_status_message=messages.append,
        )
        with (
            mock.patch("gui.main_window.QSettings"),
            mock.patch("gui.main_window._save_ui_font_bump", return_value=1),
            mock.patch("gui.main_window.set_font_bump") as apply_live,
        ):
            changed = MainWindow.set_ui_font_bump(harness, 1)

        self.assertTrue(changed)
        apply_live.assert_not_called()
        self.assertIn("restart", messages[0].lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
