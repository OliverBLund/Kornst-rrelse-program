import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget

from gui.main_window import MainWindow


APP = QApplication.instance() or QApplication(["workspace-clear-test"])


class _ScopeControlPanel:
    def __init__(self, selected_paths, card_count):
        self._selected_paths = list(selected_paths)
        self._card_count = int(card_count)

    def get_selected_paths(self):
        return list(self._selected_paths)

    def get_scope_card_count(self):
        return self._card_count


class _DatasetTab:
    def __init__(self, file_path):
        self.dataset = SimpleNamespace(file_path=file_path)


class _BatchRemovalHarness:
    _remove_tabs_for_files = MainWindow._remove_tabs_for_files
    _tab_file_path = MainWindow._tab_file_path

    def __init__(self):
        self.dataset_tabs_widget = QTabWidget()
        self.dataset_tabs = []
        for file_path in ("A.csv", "B.csv", "C.csv"):
            tab = QWidget()
            tab.dataset = SimpleNamespace(file_path=file_path)
            self.dataset_tabs.append(tab)
            self.dataset_tabs_widget.addTab(tab, file_path)

        self.calls = {
            "icons": 0,
            "comparison": 0,
            "reports": 0,
            "export": 0,
            "status": 0,
            "home": 0,
        }
        self.reporting_tab = SimpleNamespace(
            set_dataset_tabs=lambda tabs: self._record("reports")
        )

    def _record(self, name):
        self.calls[name] += 1

    def _refresh_dataset_tab_icons(self):
        self._record("icons")

    def _sync_comparison_dataset_state(self):
        self._record("comparison")

    def _update_export_tab(self):
        self._record("export")

    def _refresh_dataset_status_segments(self):
        self._record("status")

    def _show_welcome(self):
        self._record("home")


class TestMainWindowScope(unittest.TestCase):
    def test_no_included_paths_with_sidebar_cards_returns_empty_scope(self):
        harness = SimpleNamespace(
            control_panel=_ScopeControlPanel([], 2),
            dataset_tabs=[_DatasetTab("A.csv"), _DatasetTab("B.csv")],
        )

        self.assertEqual(MainWindow._get_selected_dataset_tabs(harness), [])

    def test_no_included_paths_without_sidebar_cards_preserves_legacy_all_scope(self):
        tabs = [_DatasetTab("A.csv"), _DatasetTab("B.csv")]
        harness = SimpleNamespace(
            control_panel=_ScopeControlPanel([], 0),
            dataset_tabs=tabs,
        )

        self.assertEqual(MainWindow._get_selected_dataset_tabs(harness), tabs)

    def test_included_paths_filter_dataset_tabs(self):
        tabs = [_DatasetTab("A.csv"), _DatasetTab("B.csv")]
        harness = SimpleNamespace(
            control_panel=_ScopeControlPanel(["B.csv"], 2),
            dataset_tabs=tabs,
        )

        self.assertEqual(MainWindow._get_selected_dataset_tabs(harness), [tabs[1]])

    def test_workspace_batch_removal_synchronizes_dependent_views_once(self):
        harness = _BatchRemovalHarness()

        removed = harness._remove_tabs_for_files(["A.csv", "B.csv", "C.csv"])
        APP.processEvents()

        self.assertEqual(removed, 3)
        self.assertEqual(harness.dataset_tabs, [])
        self.assertEqual(harness.dataset_tabs_widget.count(), 0)
        self.assertEqual(
            harness.calls,
            {
                "icons": 1,
                "comparison": 1,
                "reports": 1,
                "export": 1,
                "status": 1,
                "home": 1,
            },
        )

    def test_calculation_status_uses_ok_only_geometric_mean_in_m_per_s(self):
        segments = {}
        harness = SimpleNamespace(
            _suppress_calculation_refresh_depth=0,
            _bulk_dataset_add_depth=0,
            _update_export_tab=lambda: None,
            rich_status_bar=SimpleNamespace(
                set_segment=lambda key, value: segments.__setitem__(key, value)
            ),
        )
        results = [
            SimpleNamespace(
                method_name="Hazen",
                k_value=1.0e-4,
                status="OK",
                conditions_met=True,
                status_message="",
            ),
            SimpleNamespace(
                method_name="Beyer",
                k_value=9.0e-4,
                status="Warning",
                conditions_met=False,
                status_message="Outside range",
            ),
            SimpleNamespace(
                method_name="Sauerbrei",
                k_value=4.0e-4,
                status="OK",
                conditions_met=True,
                status_message="",
            ),
        ]

        MainWindow._on_calculation_complete(harness, "Sample A", results)

        self.assertEqual(segments["K̄"], "2.00e-04 m/s")

    def test_status_segments_follow_selected_dataset_not_preferred_or_last(self):
        segments = {}

        def dataset(name, d50, temperature):
            return SimpleNamespace(
                sample_name=name,
                temperature=temperature,
                get_d50=lambda: d50,
            )

        first = SimpleNamespace(
            dataset=dataset("First sample", 0.12, 8.0),
            temperature=8.0,
            current_results=[],
        )
        second = SimpleNamespace(
            dataset=dataset("Selected sample", 0.42, 17.5),
            temperature=17.5,
            current_results=[
                SimpleNamespace(
                    method_name="Hazen",
                    k_value=4.0e-4,
                    status="OK",
                    conditions_met=True,
                    status_message="",
                )
            ],
        )
        harness = SimpleNamespace(
            dataset_tabs=[first, second],
            dataset_tabs_widget=SimpleNamespace(currentWidget=lambda: second),
            rich_status_bar=SimpleNamespace(
                set_segment=lambda key, value: segments.__setitem__(key, value)
            ),
            active_method_names=["Hazen"],
            available_method_names=["Hazen", "Beyer"],
            app_toolbar=SimpleNamespace(set_badge=lambda *_args: None),
        )
        harness._status_dataset_tab = lambda preferred=None: MainWindow._status_dataset_tab(
            harness, preferred
        )

        MainWindow._refresh_dataset_status_segments(harness, "First sample")

        self.assertEqual(segments["SAMPLE"], "Selected sample")
        self.assertEqual(segments["D50"], "0.42 mm")
        self.assertEqual(segments["K̄"], "4.00e-04 m/s")
        self.assertEqual(segments["TEMP"], "17.5 °C")
        self.assertEqual(segments["DATASETS"], "2")


if __name__ == "__main__":
    unittest.main()
