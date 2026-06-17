import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QDialog

from gui.control_panel import ControlPanel


APP = QApplication.instance() or QApplication(["codex-test"])


class _FakeHost:
    def __init__(self, enabled=True):
        self.enabled = bool(enabled)
        self.saved_values = []

    def is_welcome_screen_enabled(self):
        return self.enabled

    def set_welcome_screen_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        self.saved_values.append(bool(enabled))


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

    def __init__(self, show_welcome_on_startup, parent=None):
        self.initial_value = bool(show_welcome_on_startup)
        self.parent = parent
        type(self).created.append(self)

    def exec(self):
        return QDialog.DialogCode.Accepted

    def show_welcome_on_startup(self):
        return False


class _RejectedDialog:
    created = []

    def __init__(self, show_welcome_on_startup, parent=None):
        self.initial_value = bool(show_welcome_on_startup)
        self.parent = parent
        type(self).created.append(self)

    def exec(self):
        return QDialog.DialogCode.Rejected

    def show_welcome_on_startup(self):
        return False


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

    def test_show_settings_does_not_write_when_cancelled(self):
        host = _FakeHost(enabled=False)
        self.panel._host_override = host
        _RejectedDialog.created = []

        with mock.patch("gui.control_panel.ApplicationSettingsDialog", _RejectedDialog):
            self.panel.show_settings()

        self.assertEqual(len(_RejectedDialog.created), 1)
        self.assertFalse(_RejectedDialog.created[0].initial_value)
        self.assertEqual(host.saved_values, [])

    def test_new_sample_cards_start_included_in_shared_scope(self):
        file_path = os.path.normpath(r"C:\temp\sample.csv")

        self.panel.file_statuses[file_path] = "loaded"
        self.panel.add_file_to_table(file_path, "loaded", display_name="Sample")
        self.panel._update_inventory_bar()

        self.assertEqual(self.panel.get_selected_paths(), [file_path])
        self.assertEqual(self.panel._chip_selected.text(), "1 included")
        self.assertEqual(self.panel.get_scope_card_count(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
