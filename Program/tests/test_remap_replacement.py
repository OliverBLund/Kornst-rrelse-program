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

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui import column_mapper as column_mapper_module
from gui import control_panel as control_panel_module
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
        self.removed = []

    def update_card_meta(self, file_path, d50="", k_val=""):
        self.meta[file_path] = (d50, k_val)

    def remove_card(self, file_path):
        self.removed.append(file_path)

    def add_card(self, file_path, display_name, status):
        self.meta.setdefault(file_path, (display_name, status))


class _FakeTableItem:
    def __init__(self, value):
        self.value = value

    def data(self, _role):
        return self.value


class _FakeTable:
    def __init__(self, file_paths):
        self.rows = list(file_paths)
        self.current = 0 if self.rows else -1

    def rowCount(self):
        return len(self.rows)

    def item(self, row, column):
        if column != 0 or not (0 <= row < len(self.rows)):
            return None
        return _FakeTableItem(self.rows[row])

    def removeRow(self, row):
        self.rows.pop(row)
        if not self.rows:
            self.current = -1
        elif self.current >= len(self.rows):
            self.current = len(self.rows) - 1

    def currentRow(self):
        return self.current


class _ControlPanelHarness:
    _file_entry_parts = ControlPanel._file_entry_parts
    _file_entry_key = ControlPanel._file_entry_key
    _file_entry_display_name = ControlPanel._file_entry_display_name
    _find_loaded_entry_by_file = ControlPanel._find_loaded_entry_by_file
    _find_loaded_entry_by_card = ControlPanel._find_loaded_entry_by_card
    _find_dataset_tab_for_dataset = ControlPanel._find_dataset_tab_for_dataset
    _remove_loaded_entries_for_file = ControlPanel._remove_loaded_entries_for_file
    _split_sheet_key = ControlPanel._split_sheet_key
    _format_file_display_name = ControlPanel._format_file_display_name
    _find_table_row_for_file = ControlPanel._find_table_row_for_file
    remove_file_by_path = ControlPanel.remove_file_by_path
    register_external_file = ControlPanel.register_external_file
    register_external_issue = ControlPanel.register_external_issue
    _queue_raw_sieve_files_for_mapping = ControlPanel._queue_raw_sieve_files_for_mapping

    def __init__(self):
        self.loaded_samples = {}
        self.file_statuses = {}
        self.file_mapping_states = {}
        self._card_sources = {}
        self._card_samples = {}
        self.dataset_loaded_successfully = _SignalRecorder()
        self.error_dataset = _SignalRecorder()
        self.mapping_required = _SignalRecorder()
        self.sample_info_label = _Label()
        self._file_list = _FileList()
        self.samples_table = _FakeTable([])
        self.added_rows = []
        self.update_calls = 0
        self._window = self

    def update_file_in_table(self, file_path, status):
        self.last_table_update = (file_path, status)

    def add_file_to_table(self, file_path, status, display_name=None):
        self.added_rows.append((file_path, status, display_name))

    def _push_card_meta(self, file_path):
        self.last_card_meta = file_path

    def _update_inventory_bar(self):
        self.inventory_updated = True

    def update_ui_state(self):
        self.update_calls += 1

    def window(self):
        return self._window


class _BatchExcelHarness:
    handle_batch_multisheet_excel = ControlPanel.handle_batch_multisheet_excel

    def handle_multisheet_excel(self, file_path):
        raise AssertionError("The batch sheet selector should handle grouped workbooks")


class _FakeTabWidget:
    def __init__(self, widgets, current=0):
        self.widgets = list(widgets)
        self.current = current if self.widgets else -1

    def count(self):
        return len(self.widgets)

    def widget(self, index):
        return self.widgets[index]

    def currentIndex(self):
        return self.current

    def currentWidget(self):
        if 0 <= self.current < len(self.widgets):
            return self.widgets[self.current]
        return None

    def setCurrentIndex(self, index):
        self.current = index

    def removeTab(self, index):
        self.widgets.pop(index)
        if not self.widgets:
            self.current = -1
        elif self.current >= len(self.widgets):
            self.current = len(self.widgets) - 1

    def updatesEnabled(self):
        return True

    def setUpdatesEnabled(self, _enabled):
        pass

    def blockSignals(self, _blocked):
        return False

    def update(self):
        pass


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


class _ExternalIssueRecorder:
    def __init__(self):
        self.calls = []

    def register_external_issue(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class _ErrorTabHost(QWidget):
    add_error_tab = MainWindow.add_error_tab
    add_mapping_required_tab = MainWindow.add_mapping_required_tab
    add_multi_sample_confirmation_tab = MainWindow.add_multi_sample_confirmation_tab
    update_error_tab_message = MainWindow.update_error_tab_message
    _on_external_load_file_failed = MainWindow._on_external_load_file_failed

    def __init__(self, control_panel=None):
        super().__init__()
        self.dataset_tabs_widget = QTabWidget(self)
        self.dataset_tabs = []
        self.control_panel = control_panel or _ExternalIssueRecorder()
        self._bulk_dataset_add_depth = 0
        self._bulk_dataset_add_dirty = False
        self._bulk_dataset_add_last_index = None
        self._bulk_dataset_add_last_label = ""
        self._external_load_context = {"failed_files": []}
        self.hide_welcome_calls = 0
        self.icon_refreshes = 0
        self.messages = []

    def _hide_welcome(self):
        self.hide_welcome_calls += 1

    def _refresh_dataset_tab_icons(self):
        self.icon_refreshes += 1

    def _show_status_message(self, message, ok=True):
        self.messages.append((message, ok))

    def on_dataset_fixed(self, dataset_input, original_file_path):
        self.fixed = (dataset_input, original_file_path)


class _SidebarRemovalRecorder:
    def __init__(self):
        self.calls = []

    def remove_file_by_path(self, file_path, *, sync_workspace=True, announce=True):
        self.calls.append((file_path, sync_workspace, announce))
        return True


class _CloseDatasetHarness:
    _tab_file_path = MainWindow._tab_file_path
    _has_open_tabs_for_file = MainWindow._has_open_tabs_for_file
    close_dataset_tab = MainWindow.close_dataset_tab

    def __init__(self, widgets, dataset_tabs):
        self.dataset_tabs_widget = _FakeTabWidget(widgets)
        self.dataset_tabs = list(dataset_tabs)
        self.control_panel = _SidebarRemovalRecorder()
        self.reporting_tab = SimpleNamespace(set_dataset_tabs=lambda tabs: setattr(self, "reported_tabs", list(tabs)))
        self.refreshes = []
        self.messages = []
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

    def _show_status_message(self, message, ok=True):
        self.messages.append((message, ok))


class _ExportPlotWorkspace:
    def __init__(self):
        self.plot_exports = []

    def export_plot(self, fmt):
        self.plot_exports.append(fmt)


class _ExportDatasetTab:
    def __init__(self, name):
        self.name = name
        self.result_exports = 0
        self.plot_workspace = _ExportPlotWorkspace()

    def export_results(self):
        self.result_exports += 1


class _ExportHarness:
    _current_dataset_tab = MainWindow._current_dataset_tab
    export_current = MainWindow.export_current
    export_results = MainWindow.export_results
    export_plot = MainWindow.export_plot

    def __init__(self, widgets, dataset_tabs, *, current=0):
        self.dataset_tabs_widget = _FakeTabWidget(widgets, current=current)
        self.dataset_tabs = list(dataset_tabs)
        self.content_stack = SimpleNamespace(currentIndex=lambda: 0)
        self.comparison_exports = 0
        self.comparison_tab = SimpleNamespace(
            export_comparison=lambda: setattr(
                self, "comparison_exports", self.comparison_exports + 1
            )
        )


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
        self.content_stack = QStackedWidget()
        self.home_page = QWidget()
        self._home_layout = QVBoxLayout(self.home_page)
        self.welcome_widget = QWidget()
        self.dataset_widget = QWidget()
        self._home_layout.addWidget(self.welcome_widget)
        self.content_stack.addWidget(self.home_page)
        self.content_stack.addWidget(self.dataset_widget)
        self.content_stack.setCurrentIndex(1)
        self.activated_tab = None
        self.app_toolbar = SimpleNamespace(
            activate_tab=lambda index: setattr(self, "activated_tab", index)
        )
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

    def _sync_welcome_preference_state(self):
        pass

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
        self.accepted = False
        self._batch_apply_committed = False

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

    def accept(self):
        self.accepted = True


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
        first_entry = panel.loaded_samples["Fixed sample A [A]"]
        second_entry = panel.loaded_samples["Fixed sample B [B]"]
        self.assertEqual(len(first_entry["datasets"]), 1)
        self.assertEqual(len(second_entry["datasets"]), 1)
        self.assertEqual(len(panel._card_sources), 2)
        self.assertNotEqual(
            first_entry["data"]._workspace_key,
            second_entry["data"]._workspace_key,
        )
        self.assertTrue(panel.file_mapping_states[file_path]["raw_sieve_mode"])
        self.assertEqual(panel.file_statuses[file_path], "loaded")
        self.assertEqual(len(panel.dataset_loaded_successfully.calls), 1)
        emitted_datasets, emitted_path = panel.dataset_loaded_successfully.calls[0]
        self.assertEqual(emitted_path, file_path)
        self.assertEqual(len(emitted_datasets), 2)

        first_card = first_entry["data"]._workspace_key
        second_card = second_entry["data"]._workspace_key
        removed = panel.remove_file_by_path(
            first_card,
            sync_workspace=False,
            announce=False,
        )
        self.assertTrue(removed)
        self.assertNotIn("Fixed sample A [A]", panel.loaded_samples)
        self.assertIn("Fixed sample B [B]", panel.loaded_samples)
        self.assertIn(second_card, panel._card_sources)
        self.assertEqual(panel.file_statuses[file_path], "loaded")

    def test_raw_sieve_path_queues_files_for_mapping_with_raw_mode_state(self):
        panel = _ControlPanelHarness()
        file_path = os.path.normpath(r"C:\temp\raw_sieve.csv")

        ControlPanel._queue_raw_sieve_files_for_mapping(panel, [file_path])

        self.assertEqual(panel.file_statuses[file_path], "mapping")
        self.assertTrue(panel.file_mapping_states[file_path]["raw_sieve_mode"])
        self.assertEqual(panel.added_rows, [(file_path, "mapping", None)])
        self.assertEqual(panel.error_dataset.calls, [])
        self.assertEqual(len(panel.mapping_required.calls), 1)
        emitted_path, message = panel.mapping_required.calls[0]
        self.assertEqual(emitted_path, file_path)
        self.assertIn("Raw sieve weighing data is ready for column mapping", message)
        self.assertIn("queued for mapping", panel.sample_info_label.text)

    def test_mapping_required_tab_is_neutral_not_error_colored(self):
        host = _ErrorTabHost()
        try:
            file_path = os.path.normpath(r"C:\temp\raw_sieve.csv")
            host.add_mapping_required_tab(file_path, "Raw sieve weighing data is ready for column mapping.")
            APP.processEvents()

            self.assertEqual(host.dataset_tabs_widget.count(), 1)
            tab = host.dataset_tabs_widget.widget(0)
            self.assertIsInstance(tab, ErrorTab)
            self.assertEqual(tab.issue_variant, "mapping_required")
            self.assertIn(("Mapping required: raw_sieve.csv", True), host.messages)
        finally:
            host.close()
            host.deleteLater()
            APP.processEvents()

    def test_multi_sample_confirmation_is_not_presented_as_manual_mapping(self):
        host = _ErrorTabHost()
        try:
            file_path = os.path.normpath(r"C:\temp\multi_sample.xlsx")
            host.add_multi_sample_confirmation_tab(
                file_path,
                "3 sample candidates require confirmation",
            )
            APP.processEvents()

            tab = host.dataset_tabs_widget.widget(0)
            self.assertIsInstance(tab, ErrorTab)
            self.assertEqual(tab.issue_variant, "multi_sample_confirmation")
            self.assertEqual(tab.title_label.text(), "Review detected samples")
            self.assertEqual(tab.fix_button.text(), "Review Samples")
            self.assertIn(("Review detected samples: multi_sample.xlsx", True), host.messages)
        finally:
            host.close()
            host.deleteLater()
            APP.processEvents()

    def test_multi_sample_worker_result_uses_confirmation_status(self):
        panel = _ControlPanelHarness()
        panel._multi_sample_confirmation_count = 0
        panel.multi_sample_confirmation = _SignalRecorder()
        file_path = os.path.normpath(r"C:\temp\multi_sample.xlsx")

        ControlPanel._on_import_worker_failed(
            panel,
            file_path,
            "3 sample candidates require confirmation",
        )

        self.assertEqual(panel.file_statuses[file_path], "confirmation")
        self.assertEqual(panel._multi_sample_confirmation_count, 1)
        self.assertEqual(
            panel.multi_sample_confirmation.calls,
            [(file_path, "3 sample candidates require confirmation")],
        )

    def test_experimental_multi_sample_import_requires_explicit_command(self):
        panel = ControlPanel()
        panel.show()
        APP.processEvents()

        with tempfile.TemporaryDirectory() as tempdir:
            file_path = os.path.join(tempdir, "multi.csv")
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write("placeholder")

            class _FakeMultiMapper:
                created = None

                def __init__(self, *args, **kwargs):
                    self.args = args
                    self.kwargs = kwargs
                    _FakeMultiMapper.created = self

                def _is_multi_sample_mode(self):
                    return True

                def exec(self):
                    return QDialog.DialogCode.Accepted

                def get_mapping_results(self):
                    return [
                        {
                            "sample_name": sample_name,
                            "temperature": 20.0,
                            "porosity": 0.35,
                            "particle_sizes": [2.0, 1.0, 0.5],
                            "percent_passing": passing,
                            "mapping_state": {
                                "multi_sample_mode": True,
                                "multi_sample_candidate_key": candidate_key,
                            },
                        }
                        for sample_name, passing, candidate_key in (
                            ("Sample A", [100.0, 60.0, 20.0], "wide:0:1"),
                            ("Sample B", [100.0, 55.0, 15.0], "wide:0:2"),
                        )
                    ]

                def get_mapping_state(self):
                    return {
                        "multi_sample_mode": True,
                        "selected_multi_sample_keys": ["wide:0:1", "wide:0:2"],
                    }

            original_picker = control_panel_module.QFileDialog.getOpenFileName
            original_mapper = control_panel_module.ColumnMapperDialog
            control_panel_module.QFileDialog.getOpenFileName = staticmethod(
                lambda *args, **kwargs: (file_path, "CSV files (*.csv)")
            )
            control_panel_module.ColumnMapperDialog = _FakeMultiMapper
            try:
                panel.add_multi_sample_file()
                APP.processEvents()
            finally:
                control_panel_module.QFileDialog.getOpenFileName = original_picker
                control_panel_module.ColumnMapperDialog = original_mapper

        try:
            self.assertTrue(_FakeMultiMapper.created.kwargs["multi_sample_mode"])
            self.assertEqual(panel.file_statuses[file_path], "loaded")
            self.assertEqual(
                [entry["data"].sample_name for entry in panel.loaded_samples.values()],
                ["Sample A", "Sample B"],
            )
            self.assertEqual(len(panel._card_sources), 2)
            menu_labels = [action.text() for action in panel._build_add_data_menu().actions()]
            self.assertIn(
                "Multiple Samples in One File (Experimental)...",
                menu_labels,
            )
        finally:
            panel.close()
            panel.deleteLater()
            APP.processEvents()

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

    def test_register_external_issue_tracks_review_file_for_sidebar_recovery(self):
        file_key = os.path.normpath(r"C:\temp\review.xlsx:::Sheet A")
        panel = _ControlPanelHarness()

        panel.register_external_issue(file_key, "Needs manual mapping", status="review")

        self.assertEqual(panel.file_statuses[file_key], "review")
        self.assertEqual(panel.added_rows, [(file_key, "review", None)])
        self.assertEqual(panel.sample_info_label.text, "Needs review: review.xlsx [Sheet A]")
        self.assertTrue(panel.inventory_updated)
        self.assertEqual(panel.update_calls, 1)

    def test_sidebar_inspect_uses_live_dataset_tab_and_mapping_state(self):
        file_key = "mapped.xlsx:::Sheet1"
        dataset = SimpleNamespace(sample_name="Mapped sample", file_path=file_key)
        mapping_state = {
            "raw_sieve_mode": False,
            "column_indices": {"size": 1, "passing": 2},
        }
        dataset_tab = _Tab(dataset=dataset)
        panel = _ControlPanelHarness()
        panel._active_scheme = object()
        panel.main_window = SimpleNamespace(
            dataset_tabs_widget=_FakeTabWidget([dataset_tab]),
        )
        panel.loaded_samples["Mapped sample"] = {
            "file_path": file_key,
            "data": dataset,
            "mapping_state": mapping_state,
        }

        class _FakeInspectorDialog:
            created = None

            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.exec_called = False
                _FakeInspectorDialog.created = self

            def exec(self):
                self.exec_called = True
                return QDialog.DialogCode.Accepted

        original_dialog = control_panel_module.DataInspectorDialog
        control_panel_module.DataInspectorDialog = _FakeInspectorDialog
        try:
            ControlPanel.show_file_info(panel, file_key)
        finally:
            control_panel_module.DataInspectorDialog = original_dialog

        self.assertIsNotNone(_FakeInspectorDialog.created)
        self.assertTrue(_FakeInspectorDialog.created.exec_called)
        self.assertIs(_FakeInspectorDialog.created.kwargs["dataset"], dataset)
        self.assertIs(_FakeInspectorDialog.created.kwargs["dataset_tab"], dataset_tab)
        self.assertEqual(_FakeInspectorDialog.created.kwargs["mapping_state"], mapping_state)
        self.assertIs(_FakeInspectorDialog.created.kwargs["scheme"], panel._active_scheme)

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

    def test_sidebar_removal_requests_main_window_tab_cleanup(self):
        file_path = "remove-me.xlsx:::Sheet1"
        host = SimpleNamespace(removed_files=[])

        def _remove_tabs_for_file(target):
            host.removed_files.append(target)
            return 1

        host._remove_tabs_for_file = _remove_tabs_for_file

        panel = _ControlPanelHarness()
        panel._window = host
        panel.samples_table = _FakeTable([file_path])
        panel.file_statuses[file_path] = "loaded"
        panel.file_mapping_states[file_path] = {"raw_sieve_mode": False}
        panel.loaded_samples["Remove Me [Sheet1]"] = {"file_path": file_path}

        removed = ControlPanel.remove_file_by_path(panel, file_path)

        self.assertTrue(removed)
        self.assertEqual(host.removed_files, [file_path])
        self.assertEqual(panel.samples_table.rows, [])
        self.assertNotIn(file_path, panel.file_statuses)
        self.assertNotIn(file_path, panel.file_mapping_states)
        self.assertEqual(panel._file_list.removed, [file_path])
        self.assertEqual(panel.sample_info_label.text, "Removed: remove-me.xlsx [Sheet1]")

    def test_closing_last_dataset_tab_removes_sidebar_entry(self):
        file_path = "solo.xlsx:::A"
        only_tab = _Tab(dataset=SimpleNamespace(file_path=file_path))
        harness = _CloseDatasetHarness([only_tab], [only_tab])

        MainWindow.close_dataset_tab(harness, 0)

        self.assertEqual(
            harness.control_panel.calls,
            [(file_path, False, False)],
        )
        self.assertTrue(harness.welcome_shown)
        self.assertEqual(harness.messages[-1][0], "Dataset closed")

    def test_closing_one_of_multiple_tabs_keeps_sidebar_entry(self):
        file_path = "shared.xlsx:::A"
        first_tab = _Tab(dataset=SimpleNamespace(file_path=file_path))
        second_tab = _Tab(dataset=SimpleNamespace(file_path=file_path))
        harness = _CloseDatasetHarness([first_tab, second_tab], [first_tab, second_tab])

        MainWindow.close_dataset_tab(harness, 0)

        self.assertEqual(harness.control_panel.calls, [])
        self.assertEqual(harness.dataset_tabs_widget.widgets, [second_tab])

    def test_closing_error_tab_does_not_remove_loaded_dataset(self):
        error_path = "bad.xlsx:::NeedsMapping"
        dataset_path = "good.csv"
        error_tab = _Tab(file_path=error_path)
        dataset_tab = _Tab(dataset=SimpleNamespace(file_path=dataset_path))
        harness = _CloseDatasetHarness([error_tab, dataset_tab], [dataset_tab])

        MainWindow.close_dataset_tab(harness, 0)

        self.assertEqual(harness.dataset_tabs, [dataset_tab])
        self.assertEqual(harness.dataset_tabs_widget.widgets, [dataset_tab])
        self.assertFalse(harness.welcome_shown)
        self.assertEqual(
            harness.control_panel.calls,
            [(error_path, False, False)],
        )

    def test_closing_last_loaded_dataset_keeps_error_tab_visible(self):
        error_tab = _Tab(file_path="bad.xlsx:::NeedsMapping")
        dataset_tab = _Tab(dataset=SimpleNamespace(file_path="good.csv"))
        harness = _CloseDatasetHarness([error_tab, dataset_tab], [dataset_tab])

        MainWindow.close_dataset_tab(harness, 1)

        self.assertEqual(harness.dataset_tabs, [])
        self.assertEqual(harness.dataset_tabs_widget.widgets, [error_tab])
        self.assertFalse(harness.welcome_shown)

    def test_export_results_uses_current_dataset_widget_without_welcome_offset(self):
        first = _ExportDatasetTab("first")
        second = _ExportDatasetTab("second")
        harness = _ExportHarness([first, second], [first, second], current=0)

        MainWindow.export_results(harness)

        self.assertEqual(first.result_exports, 1)
        self.assertEqual(second.result_exports, 0)

    def test_export_ignores_current_error_tab(self):
        error_tab = _Tab(file_path="bad.csv")
        dataset_tab = _ExportDatasetTab("dataset")
        harness = _ExportHarness([error_tab, dataset_tab], [dataset_tab], current=0)

        MainWindow.export_results(harness)
        MainWindow.export_plot(harness)

        self.assertEqual(dataset_tab.result_exports, 0)
        self.assertEqual(dataset_tab.plot_workspace.plot_exports, [])

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

    def test_session_normalization_preserves_candidates_from_one_source(self):
        harness = _SessionHarness()
        file_key = os.path.normpath("multi_sample.xlsx")
        sources = []
        for sample_name, candidate_key in (("BH-01", "wide:1"), ("BH-02", "wide:2")):
            sources.append({
                "file_key": file_key,
                "file_path": file_key,
                "sample_name": sample_name,
                "mapping_state": {
                    "multi_sample_mode": True,
                    "multi_sample_candidate_key": candidate_key,
                    "selected_size_range": [[1, 0]],
                    "selected_percent_range": [[1, 1]],
                },
            })

        session = MainWindow._normalize_session_entry(
            harness,
            {"name": "Multi-sample", "sources": sources},
        )

        self.assertEqual(session["files"], [file_key])
        self.assertEqual(len(session["sources"]), 2)
        self.assertEqual(
            [
                source["mapping_state"]["multi_sample_candidate_key"]
                for source in session["sources"]
            ],
            ["wide:1", "wide:2"],
        )

    def test_sidebar_scope_uses_per_sample_workspace_keys(self):
        source_path = os.path.normpath("multi_sample.xlsx")
        first = _Tab(dataset=SimpleNamespace(
            file_path=source_path,
            _workspace_key=f"{source_path}::sample::wide:0:1",
        ))
        second = _Tab(dataset=SimpleNamespace(
            file_path=source_path,
            _workspace_key=f"{source_path}::sample::wide:0:2",
        ))
        control_panel = SimpleNamespace(
            get_selected_paths=lambda: [second.dataset._workspace_key],
            get_scope_card_count=lambda: 2,
        )
        harness = SimpleNamespace(
            control_panel=control_panel,
            dataset_tabs=[first, second],
        )

        selected = MainWindow._get_selected_dataset_tabs(harness)
        selected_paths = MainWindow._dataset_paths_for_tabs(harness, selected)

        self.assertEqual(selected, [second])
        self.assertEqual(selected_paths, [second.dataset._workspace_key])

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

    def test_refresh_welcome_widget_preserves_the_current_top_level_page(self):
        harness = _WelcomeRefreshHarness()

        old_welcome = harness.welcome_widget
        harness._refresh_welcome_widget(preserve_visibility=True)
        APP.processEvents()

        self.assertEqual(harness.content_stack.currentIndex(), 1)
        self.assertEqual(harness.activated_tab, 1)
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

    def test_update_error_tab_message_creates_missing_error_tab(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "bad.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["size", "passing"])
                writer.writerow([1.0, 80.0])

            host = _ErrorTabHost()
            try:
                host.update_error_tab_message(csv_path, "Needs manual mapping")
                APP.processEvents()

                self.assertEqual(host.dataset_tabs_widget.count(), 1)
                tab = host.dataset_tabs_widget.widget(0)
                self.assertIsInstance(tab, ErrorTab)
                self.assertEqual(tab.file_path, csv_path)
                self.assertEqual(tab.error_message, "Needs manual mapping")
                self.assertEqual(host.hide_welcome_calls, 1)
            finally:
                host.close()
                host.deleteLater()
                APP.processEvents()

    def test_external_load_failure_opens_error_tab_and_registers_review_state(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "bad.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["size", "passing"])
                writer.writerow([1.0, 80.0])

            recorder = _ExternalIssueRecorder()
            host = _ErrorTabHost(control_panel=recorder)
            try:
                host._on_external_load_file_failed(
                    csv_path,
                    "Excel sheet requires manual column mapping",
                )
                APP.processEvents()

                self.assertEqual(len(recorder.calls), 1)
                args, kwargs = recorder.calls[0]
                self.assertEqual(
                    args,
                    (csv_path, "Excel sheet requires manual column mapping"),
                )
                self.assertEqual(kwargs["status"], "review")
                self.assertEqual(host.dataset_tabs_widget.count(), 1)
                self.assertEqual(
                    host._external_load_context["failed_files"],
                    ["bad.csv: Excel sheet requires manual column mapping"],
                )
            finally:
                host.close()
                host.deleteLater()
                APP.processEvents()

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

    def test_sample_card_exposes_visible_remap_action(self):
        card = control_panel_module._SampleCard("sample.csv", "Sample", "loaded")
        emitted = []
        card.sig_remap.connect(emitted.append)
        try:
            remap_buttons = [
                button for button in card.findChildren(QPushButton)
                if button.text() == "Remap"
            ]
            self.assertEqual(len(remap_buttons), 1)
            remap_buttons[0].click()
            self.assertEqual(emitted, ["sample.csv"])
        finally:
            card.close()
            card.deleteLater()
            APP.processEvents()

    def test_batch_multisheet_selection_applies_sheet_name_across_mixed_workbooks(self):
        with tempfile.TemporaryDirectory() as tempdir:
            first = os.path.join(tempdir, "first.xlsx")
            second = os.path.join(tempdir, "second.xlsx")
            third = os.path.join(tempdir, "third.xlsx")
            with pd.ExcelWriter(first) as writer:
                pd.DataFrame({"x": [1]}).to_excel(writer, sheet_name="English", index=False)
                pd.DataFrame({"x": [2]}).to_excel(writer, sheet_name="Danish", index=False)
            with pd.ExcelWriter(second) as writer:
                pd.DataFrame({"x": [3]}).to_excel(writer, sheet_name="Notes", index=False)
                pd.DataFrame({"x": [4]}).to_excel(writer, sheet_name="English", index=False)
                pd.DataFrame({"x": [5]}).to_excel(writer, sheet_name="Results", index=False)
            with pd.ExcelWriter(third) as writer:
                pd.DataFrame({"x": [6]}).to_excel(writer, sheet_name="QC", index=False)
                pd.DataFrame({"x": [7]}).to_excel(writer, sheet_name="English", index=False)

            class _InfoLabel:
                def setText(self, text):
                    self.text = text

            class _FakeSheetSelector:
                calls = []
                batch_options = []

                def __init__(self, file_path, parent=None):
                    self.file_path = file_path
                    self.parent = parent
                    self.info_label = _InfoLabel()
                    _FakeSheetSelector.calls.append(file_path)

                def setWindowTitle(self, title):
                    self.title = title

                def set_batch_sheet_options(
                    self,
                    sheet_names,
                    sheet_counts,
                    file_count,
                    checked_sheet_names,
                ):
                    _FakeSheetSelector.batch_options.append(
                        (sheet_names, sheet_counts, file_count, checked_sheet_names)
                    )

                def exec(self):
                    return QDialog.DialogCode.Accepted

                def get_selected_sheets(self):
                    return ["English"]

            original_selector = sheet_selector_module.SheetSelectorDialog
            sheet_selector_module.SheetSelectorDialog = _FakeSheetSelector
            try:
                result = ControlPanel.handle_batch_multisheet_excel(
                    _BatchExcelHarness(),
                    [first, second, third],
                )
            finally:
                sheet_selector_module.SheetSelectorDialog = original_selector

        self.assertEqual(_FakeSheetSelector.calls, [first])
        self.assertEqual(result, [(first, "English"), (second, "English"), (third, "English")])
        sheet_names, sheet_counts, file_count, checked_sheet_names = _FakeSheetSelector.batch_options[0]
        self.assertEqual(file_count, 3)
        self.assertIn("English", sheet_names)
        self.assertEqual(sheet_counts["english"], 3)
        self.assertIn("English", checked_sheet_names)

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

    def test_apply_pattern_to_batch_updates_current_and_sheet_specific_error_tabs_via_control_panel(self):
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

        self.assertEqual(harness.applied, [f"{workbook}:::Sheet1", f"{workbook}:::Sheet2"])
        self.assertEqual(len(recorder.calls), 2)

        current_args, current_kwargs = recorder.calls[0]
        self.assertEqual(current_args[0], f"{workbook}:::Sheet1")
        self.assertEqual(current_args[1][0]["sheet_name"], "Sheet1")
        self.assertEqual(current_kwargs["forced_sheet_name"], "Sheet1")

        other_args, other_kwargs = recorder.calls[1]
        self.assertEqual(other_args[0], f"{workbook}:::Sheet2")
        self.assertEqual(other_args[1][0]["sheet_name"], "Sheet2")
        self.assertEqual(other_kwargs["forced_sheet_name"], "Sheet2")
        self.assertEqual(other_kwargs["mapping_state"]["calculated_selection_mode"], "range")
        self.assertTrue(harness.accepted)
        self.assertTrue(harness._batch_apply_committed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
