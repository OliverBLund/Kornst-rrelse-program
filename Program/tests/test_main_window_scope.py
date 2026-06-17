import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from gui.main_window import MainWindow


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


if __name__ == "__main__":
    unittest.main()
