"""Tests for unified workspace settings and dataset-input routes."""

import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QComboBox, QDoubleSpinBox, QLabel

from gui.analysis_settings_dialog import AnalysisSettingsDialog
from gui.control_panel import ControlPanel
from gui.main_window import MainWindow


APP = QApplication.instance() or QApplication(["codex-test"])


class _Control:
    def __init__(self):
        self.temp_spinbox = QDoubleSpinBox()
        self.temp_spinbox.setRange(0.0, 50.0)
        self.temp_spinbox.setDecimals(1)
        self.temp_spinbox.setValue(20.0)
        self.porosity_mode_combo = QComboBox()
        self.porosity_mode_combo.addItems(["Simple", "Urumovic"])
        self._active_scheme = SimpleNamespace(name="ISO 14688")
        self.sample_info_label = QLabel()
        self.dataset_inputs_opened = 0

    def analysis_settings_summary(self):
        return "summary"

    def open_dataset_inputs_dialog(self):
        self.dataset_inputs_opened += 1

    def _open_classification_dialog(self):
        self._active_scheme = SimpleNamespace(name="Custom scheme")

    def _on_scheme_changed(self, scheme):
        self._active_scheme = scheme


class _Main:
    def __init__(self):
        self.active_method_names = ["A", "B"]
        self.available_method_names = ["A", "B", "C"]

    def choose_k_methods(self):
        self.active_method_names = ["A"]

    def set_active_k_methods(self, methods):
        self.active_method_names = list(methods)


class _Progress:
    def setVisible(self, _value):
        pass

    def setMaximum(self, _value):
        pass

    def setValue(self, _value):
        pass


class _DatasetTab:
    def __init__(self, temperature):
        self.temperature = temperature
        self.calls = []

    def set_parameters(self, _temperature):
        raise AssertionError("Manual recalculation must preserve dataset inputs")

    def calculate_k_values(self, methods):
        self.calls.append(list(methods))


class TestAnalysisSettingsUnification(unittest.TestCase):
    def test_workspace_dialog_exposes_shared_selectors_and_applies_defaults(self):
        control = _Control()
        main = _Main()
        dialog = AnalysisSettingsDialog(control, main)
        dialog.temperature.setValue(12.5)
        dialog.porosity_mode.setCurrentText("Urumovic")

        self.assertIn("background: white", dialog.temperature.styleSheet())
        self.assertIn("background: white", dialog.porosity_mode.styleSheet())

        dialog._scheme = SimpleNamespace(name="Custom scheme")
        dialog._method_names = ["A"]
        dialog._refresh_workspace_labels()
        dialog._apply()

        self.assertEqual(control.temp_spinbox.value(), 12.5)
        self.assertEqual(control.porosity_mode_combo.currentText(), "Urumovic")
        self.assertEqual(dialog.scheme_value.text(), "Custom scheme")
        self.assertEqual(dialog.methods_value.text(), "1 of 3 methods active")
        dialog.deleteLater()

    def test_props_routes_to_dataset_inputs_focused_on_dataset(self):
        dataset = SimpleNamespace(sample_name="Focused sample")

        class Harness:
            show_file_props = ControlPanel.show_file_props

            def _find_loaded_entry_by_card(self, _file_path):
                return "key", {"data": dataset}

            def open_dataset_inputs_dialog(self, *, focus_dataset_name=None):
                self.focus = focus_dataset_name

        harness = Harness()
        harness.show_file_props("sample.csv")
        self.assertEqual(harness.focus, "Focused sample")

    def test_manual_recalculation_preserves_per_dataset_temperatures(self):
        tabs = [_DatasetTab(8.0), _DatasetTab(21.5)]

        class Harness:
            calculate_all_k_values = MainWindow.calculate_all_k_values

            def __init__(self):
                self.dataset_tabs = tabs
                self.active_method_names = ["Hazen", "Beyer"]
                self.progress_bar = _Progress()
                self.content_stack = SimpleNamespace(currentIndex=lambda: -1)
                self.comparison_tab = SimpleNamespace(update_comparison=lambda: None)

            def _show_status_message(self, _message, ok=True):
                pass

        Harness().calculate_all_k_values()

        self.assertEqual([tab.temperature for tab in tabs], [8.0, 21.5])
        self.assertEqual(tabs[0].calls, [["Hazen", "Beyer"]])
        self.assertEqual(tabs[1].calls, [["Hazen", "Beyer"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
