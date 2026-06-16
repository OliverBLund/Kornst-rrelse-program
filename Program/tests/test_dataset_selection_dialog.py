import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QPushButton

from gui.dataset_selection_dialog import DatasetSelectionDialog


APP = QApplication.instance() or QApplication([])


class DummyDatasetTab:
    def __init__(self, name: str, file_key: str, group: str = "Ungrouped"):
        self.dataset = SimpleNamespace(
            sample_name=name,
            file_path=file_key,
            group_name=group,
            particle_sizes=[2.0, 1.0, 0.5],
        )

    def get_dataset(self):
        return self.dataset

    def get_dataset_name(self):
        return self.dataset.sample_name

    def get_results(self):
        return []


class TestDatasetSelectionDialog(unittest.TestCase):
    def test_checked_rows_can_be_assigned_to_group_in_bulk(self):
        tabs = [
            DummyDatasetTab("Sample A", "A.csv"),
            DummyDatasetTab("Sample B", "B.csv"),
            DummyDatasetTab("Sample C", "C.csv"),
        ]
        dialog = DatasetSelectionDialog(
            tabs,
            currently_selected=tabs[:2],
            minimum_selection=1,
            allow_grouping=True,
        )
        try:
            dialog._group_box.setText("Layer A")
            dialog._assign_group_to_checked()

            assignments = dialog.get_group_assignments()
            self.assertEqual(assignments[tabs[0]], "Layer A")
            self.assertEqual(assignments[tabs[1]], "Layer A")
            self.assertEqual(assignments[tabs[2]], "Ungrouped")
            self.assertIn("2 groups", dialog._sel_hint.text())
        finally:
            dialog.deleteLater()

    def test_group_edit_updates_filter_text(self):
        tabs = [
            DummyDatasetTab("Sample A", "A.csv"),
            DummyDatasetTab("Sample B", "B.csv"),
        ]
        dialog = DatasetSelectionDialog(
            tabs,
            currently_selected=tabs,
            minimum_selection=1,
            allow_grouping=True,
        )
        try:
            dialog._rows[1].set_group_name("Layer B")
            dialog._rows[1]._on_group_edit_finished()
            dialog._filter("Layer B")

            visible_names = [row.tab.get_dataset_name() for row in dialog._visible_rows()]
            self.assertEqual(visible_names, ["Sample B"])
        finally:
            dialog.deleteLater()

    def test_apply_group_button_does_not_cascade_after_row_edit_focus(self):
        tabs = [
            DummyDatasetTab("Sample A", "A.csv"),
            DummyDatasetTab("Sample B", "B.csv"),
            DummyDatasetTab("Sample C", "C.csv"),
            DummyDatasetTab("Sample D", "D.csv"),
        ]
        dialog = DatasetSelectionDialog(
            tabs,
            currently_selected=tabs[:3],
            minimum_selection=1,
            allow_grouping=True,
        )
        try:
            rebuilds = {"count": 0}
            original_rebuild = dialog._rebuild_rows_layout

            def wrapped_rebuild():
                rebuilds["count"] += 1
                original_rebuild()

            dialog._rebuild_rows_layout = wrapped_rebuild
            dialog._rows[0]._group_edit.setFocus()
            dialog._rows[0].set_group_name("Temporary")
            dialog._group_box.setText("Layer A")

            button = [
                child for child in dialog.findChildren(QPushButton)
                if child.text() == "Apply Group"
            ][0]
            button.click()

            assignments = dialog.get_group_assignments()
            self.assertEqual(assignments[tabs[0]], "Layer A")
            self.assertEqual(assignments[tabs[1]], "Layer A")
            self.assertEqual(assignments[tabs[2]], "Layer A")
            self.assertEqual(assignments[tabs[3]], "Ungrouped")
            self.assertLessEqual(rebuilds["count"], 3)
        finally:
            dialog.deleteLater()

    def test_rebuild_does_not_detach_dataset_rows_as_windows(self):
        tabs = [
            DummyDatasetTab("Sample A", "A.csv"),
            DummyDatasetTab("Sample B", "B.csv"),
        ]
        dialog = DatasetSelectionDialog(
            tabs,
            currently_selected=tabs,
            minimum_selection=1,
            allow_grouping=True,
        )
        try:
            dialog._clear_rows_layout()

            for row in dialog._rows:
                self.assertIs(row.parent(), dialog._list_host)
                self.assertFalse(row.isWindow())
                self.assertFalse(row.isVisible())
        finally:
            dialog.deleteLater()

    def test_initial_grouped_dialog_does_not_create_row_windows(self):
        tabs = [
            DummyDatasetTab("Sample A", "A.csv", "Layer A"),
            DummyDatasetTab("Sample B", "B.csv", "Layer B"),
            DummyDatasetTab("Sample C", "C.csv", "Layer B"),
        ]
        dialog = DatasetSelectionDialog(
            tabs,
            currently_selected=tabs,
            minimum_selection=1,
            allow_grouping=True,
        )
        try:
            for row in dialog._rows:
                self.assertIs(row.parent(), dialog._list_host)
                self.assertFalse(row.isWindow())
            for header in dialog._group_headers:
                self.assertIs(header.parent(), dialog._list_host)
                self.assertFalse(header.isWindow())
        finally:
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
