import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtCore import QMimeData, QUrl
from PyQt6.QtWidgets import QApplication, QDialog, QLabel

from gui.control_panel import ControlPanel


APP = QApplication.instance() or QApplication(["codex-test"])


class _FakeHost:
    def __init__(self, enabled=True):
        self.enabled = bool(enabled)
        self.saved_values = []
        self.font_bump = 0
        self.saved_font_bumps = []

    def is_welcome_screen_enabled(self):
        return self.enabled

    def set_welcome_screen_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        self.saved_values.append(bool(enabled))

    def ui_font_bump(self):
        return self.font_bump

    def set_ui_font_bump(self, bump):
        changed = int(bump) != self.font_bump
        self.font_bump = int(bump)
        self.saved_font_bumps.append(int(bump))
        return changed


class _SettingsPanelHarness(ControlPanel):
    def __init__(self):
        self._host_override = None
        super().__init__()

    def window(self):
        if self._host_override is not None:
            return self._host_override
        return super().window()


class _AcceptedDialog:
    created = []

    def __init__(self, show_welcome_on_startup, ui_font_bump=0, parent=None):
        self.initial_value = bool(show_welcome_on_startup)
        self.initial_font_bump = int(ui_font_bump)
        self.parent = parent
        type(self).created.append(self)

    def exec(self):
        return QDialog.DialogCode.Accepted

    def show_welcome_on_startup(self):
        return False

    def ui_font_bump(self):
        return self.initial_font_bump


class _RejectedDialog:
    created = []

    def __init__(self, show_welcome_on_startup, ui_font_bump=0, parent=None):
        self.initial_value = bool(show_welcome_on_startup)
        self.initial_font_bump = int(ui_font_bump)
        self.parent = parent
        type(self).created.append(self)

    def exec(self):
        return QDialog.DialogCode.Rejected

    def show_welcome_on_startup(self):
        return False

    def ui_font_bump(self):
        return self.initial_font_bump


class TestControlPanelSettings(unittest.TestCase):
    def setUp(self):
        self.panel = _SettingsPanelHarness()
        self.panel.show()
        APP.processEvents()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        APP.processEvents()

    def test_show_settings_reads_and_writes_welcome_preference_via_host_window(self):
        host = _FakeHost(enabled=True)
        self.panel._host_override = host
        _AcceptedDialog.created = []

        with mock.patch("gui.control_panel.ApplicationSettingsDialog", _AcceptedDialog):
            self.panel.show_settings()

        self.assertEqual(len(_AcceptedDialog.created), 1)
        self.assertTrue(_AcceptedDialog.created[0].initial_value)
        self.assertEqual(host.saved_values, [False])
        self.assertEqual(host.saved_font_bumps, [0])

    def test_show_settings_does_not_write_when_cancelled(self):
        host = _FakeHost(enabled=False)
        self.panel._host_override = host
        _RejectedDialog.created = []

        with mock.patch("gui.control_panel.ApplicationSettingsDialog", _RejectedDialog):
            self.panel.show_settings()

        self.assertEqual(len(_RejectedDialog.created), 1)
        self.assertFalse(_RejectedDialog.created[0].initial_value)
        self.assertEqual(host.saved_values, [])
        self.assertEqual(host.saved_font_bumps, [])

    def test_new_sample_cards_start_included_in_shared_scope(self):
        file_path = os.path.normpath(r"C:\temp\sample.csv")

        self.panel.file_statuses[file_path] = "loaded"
        self.panel.add_file_to_table(file_path, "loaded", display_name="Sample")
        self.panel._update_inventory_bar()

        self.assertEqual(self.panel.get_selected_paths(), [file_path])
        self.assertEqual(self.panel._chip_selected.text(), "1 included")
        self.assertEqual(self.panel.get_scope_card_count(), 1)

    def test_drop_zone_accepts_supported_file_types_on_visible_frame(self):
        mime = QMimeData()
        csv_path = r"C:/temp/sample.CSV"
        ignored_path = r"C:/temp/notes.png"
        mime.setUrls([
            QUrl.fromLocalFile(csv_path),
            QUrl.fromLocalFile(ignored_path),
        ])

        self.assertTrue(self.panel._drop_zone.acceptDrops())
        self.assertEqual(self.panel._drop_zone.objectName(), "import-drop-zone")
        self.assertTrue(
            all(child.acceptDrops() for child in self.panel._drop_zone.findChildren(QLabel))
        )
        self.assertEqual(
            self.panel._supported_drop_paths_from_mime(mime),
            [csv_path],
        )

    def test_sidebar_credit_block_uses_dtu_logo_and_attribution_text(self):
        self.assertEqual(
            self.panel._sidebar_credit_logo.objectName(),
            "sidebar-credit-logo",
        )
        self.assertFalse(self.panel._sidebar_credit_logo.pixmap().isNull())
        logo_style = self.panel._sidebar_credit_logo.styleSheet()
        self.assertIn("background: transparent", logo_style)
        self.assertNotIn("background: #000", logo_style)

        credit_text = self.panel._sidebar_credit_text.text()
        self.assertIn("Oliver Lund", credit_text)
        self.assertIn("with Poul Løgstrup Bjerg", credit_text)
        self.assertIn("Based on HydrogeoSieveXL", credit_text)
        self.assertIn("J. F. Devlin", credit_text)
        self.assertIn("Developed by Oliver Lund", self.panel._sidebar_credit_text.toolTip())


if __name__ == "__main__":
    unittest.main(verbosity=2)
