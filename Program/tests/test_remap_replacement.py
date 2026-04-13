"""
Regression tests for correcting/remapping files after an initial bad load.
"""

import csv
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QDialog, QStackedWidget, QWidget

from gui import column_mapper as column_mapper_module
from gui import error_tab as error_tab_module
from gui import sheet_selector as sheet_selector_module
from gui.column_mapper import ColumnMapperDialog
from gui.control_panel import ControlPanel
from gui.error_tab import ErrorTab
from gui.main_window import MainWindow


APP = QApplication.instance() or QApplication([])


class _SignalRecorder:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class _Label:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _FileList:
    def __init__(self):
        self.meta = {}

    def update_card_meta(self, file_path, d50="", k_val=""):
        self.meta[file_path] = (d50, k_val)


class _ControlPanelHarness:
    _remove_loaded_entries_for_file = ControlPanel._remove_loaded_entries_for_file
    _split_sheet_key = ControlPanel._split_sheet_key
    _format_file_display_name = ControlPanel._format_file_display_name
    register_external_file = ControlPanel.register_external_file

    def __init__(self):
        self.loaded_samples = {}
        self.file_statuses = {}
        self.file_mapping_states = {}
        self.dataset_loaded_successfully = _SignalRecorder()
        self.sample_info_label = _Label()
        self._file_list = _FileList()
        self.added_rows = []

    def update_file_in_table(self, file_path, status):
        self.last_table_update = (file_path, status)

    def add_file_to_table(self, file_path, status, display_name=None):
        self.added_rows.append((file_path, status, display_name))

    def _push_card_meta(self, file_path):
        self.last_card_meta = file_path

    def _update_inventory_bar(self):
        self.inventory_updated = True


class _BatchExcelHarness:
    handle_batch_multisheet_excel = ControlPanel.handle_batch_multisheet_excel

    def handle_multisheet_excel(self, file_path):
        raise AssertionError("The batch sheet selector should handle grouped workbooks")


class _FakeTabWidget:
    def __init__(self, widgets):
        self.widgets = list(widgets)

    def count(self):
        return len(self.widgets)

    def widget(self, index):
        return self.widgets[index]

    def removeTab(self, index):
        self.widgets.pop(index)


class _MainWindowHarness:
    _remove_tabs_for_file = MainWindow._remove_tabs_for_file

    def __init__(self, widgets, dataset_tabs):
        self.dataset_tabs_widget = _FakeTabWidget(widgets)
        self.dataset_tabs = list(dataset_tabs)
        self.reporting_tab = SimpleNamespace(set_dataset_tabs=lambda tabs: setattr(self, "reported_tabs", list(tabs)))
        self.refreshes = []
        self.welcome_shown = False

    def _refresh_dataset_tab_icons(self):
        self.refreshes.append("icons")

    def _sync_comparison_dataset_state(self):
        self.refreshes.append("comparison")

    def _update_export_tab(self):
        self.refreshes.append("export")

    def _refresh_dataset_status_segments(self, sample_name=None):
        self.refreshes.append("status")

    def _show_welcome(self):
        self.welcome_shown = True


class _SessionHarness:
    _split_source_key = MainWindow._split_source_key
    _normalize_file_key = MainWindow._normalize_file_key
    _file_key_exists = MainWindow._file_key_exists
    _source_file_key = MainWindow._source_file_key
    _source_actual_path = MainWindow._source_actual_path
    _source_exists = MainWindow._source_exists
    _normalize_session_source = MainWindow._normalize_session_source
    _normalize_session_sources = MainWindow._normalize_session_sources
    _source_display_name = MainWindow._source_display_name
    _normalize_session_files = MainWindow._normalize_session_files
    _normalize_session_entry = MainWindow._normalize_session_entry
    _session_match_key = MainWindow._session_match_key
    _build_dataset_source_descriptor = MainWindow._build_dataset_source_descriptor

    def __init__(self):
        self.control_panel = SimpleNamespace(file_mapping_states={})


class _WelcomeRefreshHarness:
    _refresh_welcome_widget = MainWindow._refresh_welcome_widget

    def __init__(self):
        self.dataset_tabs = [object()]
        self.control_panel = SimpleNamespace(isVisible=lambda: True, setVisible=lambda visible: setattr(self, "sidebar_visible", visible))
        self._samples_stack = QStackedWidget()
        self.welcome_widget = QWidget()
        self.dataset_widget = QWidget()
        self._samples_stack.addWidget(self.welcome_widget)
        self._samples_stack.addWidget(self.dataset_widget)
        self._samples_stack.setCurrentIndex(0)
        self.sidebar_visible = True
        self.signals_connected = 0
        self.show_welcome_called = False

    def _load_recent_files(self):
        return []

    def _load_recent_sessions(self):
        return []

    def _connect_welcome_signals(self):
        self.signals_connected += 1

    def _show_welcome(self):
        self.show_welcome_called = True

    def _refresh_dataset_tab_icons(self):
        self.icons_refreshed = True


class _ProgressDialogRecorder:
    def __init__(self):
        self.calls = []

    def update_progress(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class _ExternalProgressHarness:
    _update_external_integration_progress = MainWindow._update_external_integration_progress

    def __init__(self):
        self._external_load_dialog = _ProgressDialogRecorder()
        self._external_ui_total = 5
        self._external_ui_processed = 2


class _MainWindowWidget(QWidget):
    def __init__(self, control_panel):
        super().__init__()
        self.dataset_tabs_widget = object()
        self.control_panel = control_panel


class _ApplyRecorder:
    def __init__(self):
        self.file_mapping_states = {}
        self.calls = []

    def _apply_mapping_results(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class _PatternFileHarness:
    apply_pattern_to_file = ColumnMapperDialog.apply_pattern_to_file

    def __init__(self, pattern):
        self.learned_pattern = pattern

    def is_numeric(self, value):
        return ColumnMapperDialog.is_numeric(self, value)


class _BatchPatternHarness:
    apply_pattern_to_batch = ColumnMapperDialog.apply_pattern_to_batch

    def __init__(self, main_window, file_path, *, forced_sheet_name=None):
        self.selected_size_range = [(1, 0)]
        self.selected_percent_range = [(1, 1)]
        self.main_window = main_window
        self.file_path = file_path
        self.forced_sheet_name = forced_sheet_name
        self.applied = []

    def learn_pattern_from_selection(self):
        return {
            "size_header": "Size",
            "percent_header": "Passing",
            "data_offset": 1,
        }

    def apply_pattern_to_file(self, file_path):
        self.applied.append(file_path)
        sheet_name = file_path.split(":::", 1)[1] if ":::" in file_path else None
        return {
            "sample_name": "fixed sample",
            "temperature": 20.0,
            "porosity": 0.35,
            "particle_sizes": [2.0, 1.0, 0.5],
            "percent_passing": [100.0, 60.0, 15.0],
            "sheet_name": sheet_name,
        }

    def get_mapping_state(self):
        return {"calculated_selection_mode": "range"}


class _Tab:
    def __init__(self, *, file_path=None, dataset=None):
        self.file_path = file_path
        self.dataset = dataset
        self.deleted = False

    def deleteLater(self):
        self.deleted = True


class TestRemapReplacement(unittest.TestCase):
    def test_column_mapper_can_reopen_in_raw_sieve_mode(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "raw_sieve.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["mm sieve", "empty g", "full g"])
                writer.writerow([0.5, 100.0, 110.0])
                writer.writerow([0.25, 101.0, 106.0])

            dialog = ColumnMapperDialog(
                csv_path,
                initial_state={
                    "raw_sieve_mode": True,
                    "calculated_selection_mode": "column",
                    "column_indices": {
                        "raw_size": 1,
                        "empty_sieve": 2,
                        "sieve_sample": 3,
                    },
                },
            )
            try:
                APP.processEvents()
                self.assertTrue(dialog.raw_sieve_mode)
                self.assertFalse(dialog.raw_sieve_group.isHidden())
                self.assertEqual(dialog.raw_size_combo.currentIndex(), 1)
                self.assertEqual(dialog.empty_sieve_combo.currentIndex(), 2)
                self.assertEqual(dialog.sieve_sample_combo.currentIndex(), 3)
                self.assertTrue(dialog.get_mapping_state()["raw_sieve_mode"])
            finally:
                dialog.close()
                dialog.deleteLater()
                APP.processEvents()

    def test_apply_mapping_results_replaces_loaded_entry_for_same_file(self):
        file_path = "bad_then_fixed.xlsx:::Ark1"
        panel = _ControlPanelHarness()
        panel.loaded_samples = {
            "old sample name": {
                "file_path": file_path,
                "data": object(),
                "datasets": [object()],
                "status": "failed",
            },
            "other sample": {
                "file_path": "other.csv",
                "data": object(),
                "datasets": [object()],
                "status": "loaded",
            },
        }

        mapping_results = [
            {
                "sample_name": "Fixed sample A",
                "temperature": 20.0,
                "porosity": 0.35,
                "particle_sizes": [2.0, 1.0, 0.5],
                "percent_passing": [100.0, 55.0, 10.0],
                "sheet_name": "A",
            },
            {
                "sample_name": "Fixed sample B",
                "temperature": 20.0,
                "porosity": 0.35,
                "particle_sizes": [2.0, 1.0, 0.5],
                "percent_passing": [100.0, 60.0, 15.0],
                "sheet_name": "B",
            },
        ]

        ControlPanel._apply_mapping_results(
            panel,
            file_path,
            mapping_results,
            mapping_state={"raw_sieve_mode": True},
        )

        self.assertNotIn("old sample name", panel.loaded_samples)
        self.assertIn("other sample", panel.loaded_samples)
        fixed_entry = panel.loaded_samples["Fixed sample A [A]"]
        self.assertEqual(len(fixed_entry["datasets"]), 2)
        self.assertTrue(panel.file_mapping_states[file_path]["raw_sieve_mode"])
        self.assertEqual(panel.file_statuses[file_path], "loaded")
        self.assertEqual(len(panel.dataset_loaded_successfully.calls), 1)
        emitted_datasets, emitted_path = panel.dataset_loaded_successfully.calls[0]
        self.assertEqual(emitted_path, file_path)
        self.assertEqual(len(emitted_datasets), 2)

    def test_register_external_file_formats_sheet_keys_for_display(self):
        panel = ControlPanel()
        panel.show()
        APP.processEvents()

        try:
            file_key = os.path.normpath(r"C:\temp\restored.xlsx:::Sheet A")
            dataset = SimpleNamespace(sample_name="Restored sample [Sheet A]")

            panel.register_external_file(file_key, dataset)
            APP.processEvents()

            self.assertEqual(panel.file_statuses[file_key], "loaded")
            self.assertIn("Restored sample [Sheet A]", panel.loaded_samples)
            self.assertEqual(panel.samples_table.rowCount(), 1)
            self.assertEqual(panel.samples_table.item(0, 0).text(), "restored.xlsx [Sheet A]")
            self.assertEqual(panel._format_file_display_name(file_key), "restored.xlsx [Sheet A]")
        finally:
            panel.close()
            panel.deleteLater()
            APP.processEvents()

    def test_main_window_removes_error_and_dataset_tabs_for_file(self):
        file_path = "remapped.xlsx:::Sheet1"
        stale_error = _Tab(file_path=file_path)
        stale_dataset = _Tab(dataset=SimpleNamespace(file_path=file_path))
        other_dataset = _Tab(dataset=SimpleNamespace(file_path="other.csv"))
        harness = _MainWindowHarness(
            widgets=[stale_error, stale_dataset, other_dataset],
            dataset_tabs=[stale_dataset, other_dataset],
        )

        removed = MainWindow._remove_tabs_for_file(harness, file_path)

        self.assertEqual(removed, 2)
        self.assertTrue(stale_error.deleted)
        self.assertTrue(stale_dataset.deleted)
        self.assertEqual(harness.dataset_tabs, [other_dataset])
        self.assertEqual(harness.dataset_tabs_widget.widgets, [other_dataset])
        self.assertEqual(harness.reported_tabs, [other_dataset])
        self.assertFalse(harness.welcome_shown)

    def test_error_tab_fix_routes_through_control_panel(self):
        control_panel = _ApplyRecorder()
        parent = _MainWindowWidget(control_panel)

        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "bad.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["size", "passing"])
                writer.writerow([1.0, 80.0])
            control_panel.file_mapping_states[csv_path] = {"calculated_selection_mode": "range"}

            class _FakeMapper:
                created = None

                def __init__(self, *args, **kwargs):
                    self.args = args
                    self.kwargs = kwargs
                    _FakeMapper.created = self

                def exec(self):
                    return QDialog.DialogCode.Accepted

                def get_mapping_results(self):
                    return [
                        {
                            "sample_name": "fixed",
                            "temperature": 20.0,
                            "porosity": 0.35,
                            "particle_sizes": [2.0, 1.0, 0.5],
                            "percent_passing": [100.0, 60.0, 20.0],
                            "sheet_name": None,
                        }
                    ]

                def get_mapping_state(self):
                    return {"raw_sieve_mode": False, "calculated_selection_mode": "range"}

            original_mapper = error_tab_module.ColumnMapperDialog
            error_tab_module.ColumnMapperDialog = _FakeMapper
            try:
                tab = ErrorTab(csv_path, "needs mapping", parent=parent)
                tab.fix_dataset()
            finally:
                error_tab_module.ColumnMapperDialog = original_mapper
                parent.close()
                parent.deleteLater()
                APP.processEvents()

            self.assertEqual(len(control_panel.calls), 1)
            args, kwargs = control_panel.calls[0]
            self.assertEqual(args[0], csv_path)
            self.assertEqual(args[1][0]["sample_name"], "fixed")
            self.assertEqual(kwargs["mapping_state"]["calculated_selection_mode"], "range")
            self.assertEqual(
                _FakeMapper.created.kwargs["initial_state"],
                control_panel.file_mapping_states[csv_path],
            )

    def test_session_normalization_preserves_excel_sheet_source_descriptor(self):
        harness = _SessionHarness()

        with tempfile.TemporaryDirectory() as tempdir:
            xlsx_path = os.path.join(tempdir, "two_language.xlsx")
            with open(xlsx_path, "w", encoding="utf-8") as handle:
                handle.write("placeholder")

            file_key = f"{xlsx_path}:::English"
            session = MainWindow._normalize_session_entry(
                harness,
                {
                    "name": "Fixed session",
                    "files": [file_key],
                    "samples": ["Fixed sample"],
                },
            )

        self.assertIsNotNone(session)
        self.assertEqual(session["files"], [file_key])
        self.assertEqual(session["sources"][0]["file_path"], xlsx_path)
        self.assertEqual(session["sources"][0]["sheet_name"], "English")
        self.assertEqual(session["sources"][0]["file_key"], file_key)

    def test_session_descriptor_includes_mapping_state_for_fixed_dataset(self):
        harness = _SessionHarness()
        file_key = os.path.normpath("fixed.xlsx:::English")
        harness.control_panel.file_mapping_states[file_key] = {
            "raw_sieve_mode": False,
            "calculated_selection_mode": "range",
            "selected_size_range": [[1, 0]],
            "selected_percent_range": [[1, 1]],
        }
        dataset = SimpleNamespace(
            file_path=file_key,
            sample_name="Fixed English",
            temperature=14.0,
            porosity=0.33,
        )

        descriptor = MainWindow._build_dataset_source_descriptor(harness, dataset)

        self.assertEqual(descriptor["file_key"], file_key)
        self.assertEqual(descriptor["sheet_name"], "English")
        self.assertEqual(descriptor["sample_name"], "Fixed English")
        self.assertEqual(descriptor["data_type"], "calculated")
        self.assertEqual(descriptor["selection_method"], "range")
        self.assertEqual(descriptor["mapping_state"]["selected_size_range"], [[1, 0]])

    def test_refresh_welcome_widget_keeps_dataset_view_visible_when_tabs_exist(self):
        harness = _WelcomeRefreshHarness()

        old_welcome = harness.welcome_widget
        harness._refresh_welcome_widget(preserve_visibility=True)
        APP.processEvents()

        self.assertEqual(harness._samples_stack.currentIndex(), 1)
        self.assertTrue(harness.sidebar_visible)
        self.assertEqual(harness.signals_connected, 1)
        self.assertIsNot(harness.welcome_widget, old_welcome)
        self.assertFalse(harness.show_welcome_called)

    def test_external_integration_progress_keeps_processed_count_stable(self):
        harness = _ExternalProgressHarness()

        harness._update_external_integration_progress()

        self.assertEqual(len(harness._external_load_dialog.calls), 1)
        args, kwargs = harness._external_load_dialog.calls[0]
        self.assertEqual(args[0], 7)
        self.assertEqual(args[1], 10)
        self.assertEqual(args[2], "Integrating workspace")
        self.assertEqual(kwargs["count_label"], "5 items processed")
        self.assertEqual(kwargs["activity_label"], "Integrating item 2 of 5.")

    def test_batch_multisheet_selection_applies_once_across_sheet_order_variants(self):
        with tempfile.TemporaryDirectory() as tempdir:
            first = os.path.join(tempdir, "first.xlsx")
            second = os.path.join(tempdir, "second.xlsx")
            with pd.ExcelWriter(first) as writer:
                pd.DataFrame({"x": [1]}).to_excel(writer, sheet_name="Danish", index=False)
                pd.DataFrame({"x": [2]}).to_excel(writer, sheet_name="English", index=False)
            with pd.ExcelWriter(second) as writer:
                pd.DataFrame({"x": [2]}).to_excel(writer, sheet_name="English", index=False)
                pd.DataFrame({"x": [1]}).to_excel(writer, sheet_name="Danish", index=False)

            class _InfoLabel:
                def setText(self, text):
                    self.text = text

            class _FakeSheetSelector:
                calls = []

                def __init__(self, file_path, parent=None):
                    self.file_path = file_path
                    self.parent = parent
                    self.info_label = _InfoLabel()
                    _FakeSheetSelector.calls.append(file_path)

                def setWindowTitle(self, title):
                    self.title = title

                def exec(self):
                    return QDialog.DialogCode.Accepted

                def get_selected_sheets(self):
                    return ["English"]

            original_selector = sheet_selector_module.SheetSelectorDialog
            sheet_selector_module.SheetSelectorDialog = _FakeSheetSelector
            try:
                result = ControlPanel.handle_batch_multisheet_excel(
                    _BatchExcelHarness(),
                    [first, second],
                )
            finally:
                sheet_selector_module.SheetSelectorDialog = original_selector

        self.assertEqual(_FakeSheetSelector.calls, [first])
        self.assertEqual(result, [(first, "English"), (second, "English")])

    def test_apply_pattern_to_file_reads_sheet_qualified_excel_key(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workbook = os.path.join(tempdir, "batch.xlsx")
            with pd.ExcelWriter(workbook) as writer:
                pd.DataFrame({"ignore": [1]}).to_excel(writer, sheet_name="Ignore", header=False, index=False)
                pd.DataFrame(
                    [["Size", "Passing"], [2.0, 100.0], [1.0, 60.0], [0.5, 15.0]]
                ).to_excel(writer, sheet_name="Mapped", header=False, index=False)

            harness = _PatternFileHarness(
                {
                    "size_header": "Size",
                    "percent_header": "Passing",
                    "data_offset": 1,
                }
            )

            result = harness.apply_pattern_to_file(f"{workbook}:::Mapped")

        self.assertEqual(result["sheet_name"], "Mapped")
        self.assertEqual(result["sample_name"], "batch")
        self.assertEqual(result["particle_sizes"], [2.0, 1.0, 0.5])
        self.assertEqual(result["percent_passing"], [100.0, 60.0, 15.0])

    def test_apply_pattern_to_batch_updates_sheet_specific_error_tabs_via_control_panel(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workbook = os.path.join(tempdir, "multisheet.xlsx")
            with pd.ExcelWriter(workbook) as writer:
                pd.DataFrame({"x": [1]}).to_excel(writer, sheet_name="Sheet1", index=False)
                pd.DataFrame({"x": [2]}).to_excel(writer, sheet_name="Sheet2", index=False)

            current_tab = ErrorTab(f"{workbook}:::Sheet1", "needs mapping")
            other_tab = ErrorTab(f"{workbook}:::Sheet2", "needs mapping")
            recorder = _ApplyRecorder()
            main_window = SimpleNamespace(
                dataset_tabs_widget=_FakeTabWidget([current_tab, other_tab]),
                control_panel=recorder,
            )
            harness = _BatchPatternHarness(main_window, workbook, forced_sheet_name="Sheet1")

            original_question = column_mapper_module.QMessageBox.question
            original_information = column_mapper_module.QMessageBox.information
            column_mapper_module.QMessageBox.question = lambda *args, **kwargs: column_mapper_module.QMessageBox.StandardButton.Yes
            column_mapper_module.QMessageBox.information = lambda *args, **kwargs: None
            try:
                harness.apply_pattern_to_batch()
            finally:
                column_mapper_module.QMessageBox.question = original_question
                column_mapper_module.QMessageBox.information = original_information
                current_tab.close()
                other_tab.close()
                current_tab.deleteLater()
                other_tab.deleteLater()
                APP.processEvents()

        self.assertEqual(harness.applied, [f"{workbook}:::Sheet2"])
        self.assertEqual(len(recorder.calls), 1)
        args, kwargs = recorder.calls[0]
        self.assertEqual(args[0], f"{workbook}:::Sheet2")
        self.assertEqual(args[1][0]["sheet_name"], "Sheet2")
        self.assertEqual(kwargs["forced_sheet_name"], "Sheet2")
        self.assertEqual(kwargs["mapping_state"]["calculated_selection_mode"], "range")


if __name__ == "__main__":
    unittest.main(verbosity=2)
