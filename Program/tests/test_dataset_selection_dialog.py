import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QPushButton

from gui.dataset_selection_dialog import DatasetSelectionDialog
from gui.group_styles import clear_group_color, group_color_map


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


class DummyMouseEvent:
    def __init__(
        self,
        x: float,
        modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    ):
        self._x = x
        self._modifiers = modifiers
        self.accepted = False

    def button(self):
        return Qt.MouseButton.LeftButton

    def position(self):
        return SimpleNamespace(x=lambda: self._x)

    def modifiers(self):
        return self._modifiers

    def accept(self):
        self.accepted = True


class TestDatasetSelectionDialog(unittest.TestCase):
    def test_selected_rows_can_be_assigned_to_group_in_bulk(self):
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
            dialog._rows[0].set_selected(True)
            dialog._rows[1].set_selected(True)
            dialog._group_box.setText("Layer A")
            dialog._assign_group_to_selected()

            assignments = dialog.get_group_assignments()
            self.assertEqual(assignments[tabs[0]], "Layer A")
            self.assertEqual(assignments[tabs[1]], "Layer A")
            self.assertEqual(assignments[tabs[2]], "Ungrouped")
            self.assertFalse(dialog._rows[0].is_selected())
            self.assertFalse(dialog._rows[1].is_selected())
            self.assertTrue(dialog._rows[0].is_checked())
            self.assertTrue(dialog._rows[1].is_checked())
            self.assertIn("2 groups", dialog._sel_hint.text())
        finally:
            dialog.deleteLater()

    def test_group_targets_start_unselected_even_when_scope_is_included(self):
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
            self.assertTrue(all(row.is_checked() for row in dialog._rows))
            self.assertFalse(any(row.is_selected() for row in dialog._rows))
            self.assertIn("0 rows selected", dialog._sel_hint.text())
            self.assertEqual(dialog._sel_count_badge.text(), "2 included")
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

    def test_row_body_selects_row_and_checkbox_area_toggles_included_scope(self):
        tabs = [DummyDatasetTab("Sample A", "A.csv")]
        dialog = DatasetSelectionDialog(
            tabs,
            currently_selected=tabs,
            minimum_selection=1,
            allow_grouping=True,
        )
        try:
            row = dialog._rows[0]
            self.assertTrue(row.is_checked())
            self.assertFalse(row.is_selected())

            body_click = DummyMouseEvent(80)
            row.mousePressEvent(body_click)
            self.assertTrue(body_click.accepted)
            self.assertTrue(row.is_checked())
            self.assertTrue(row.is_selected())

            checkbox_click = DummyMouseEvent(10)
            row.mousePressEvent(checkbox_click)
            self.assertTrue(checkbox_click.accepted)
            self.assertFalse(row.is_checked())
            self.assertTrue(row.is_selected())
            self.assertEqual(dialog._sel_count_badge.text(), "0 included")
        finally:
            dialog.deleteLater()

    def test_shift_select_uses_grouped_visible_row_order_without_changing_scope(self):
        tabs = [
            DummyDatasetTab("Sample A", "A.csv", "Layer 1"),
            DummyDatasetTab("Sample B", "B.csv", "Layer 2"),
            DummyDatasetTab("Sample C", "C.csv", "Layer 1"),
            DummyDatasetTab("Sample D", "D.csv", "Layer 2"),
        ]
        dialog = DatasetSelectionDialog(
            tabs,
            currently_selected=tabs,
            minimum_selection=1,
            allow_grouping=True,
        )
        try:
            dialog._rows[0].mousePressEvent(DummyMouseEvent(80))
            dialog._rows[1].mousePressEvent(
                DummyMouseEvent(80, Qt.KeyboardModifier.ShiftModifier)
            )

            self.assertEqual(
                [row.tab.get_dataset_name() for row in dialog._rows if row.is_selected()],
                ["Sample A", "Sample B", "Sample C"],
            )
            self.assertTrue(all(row.is_checked() for row in dialog._rows))
            self.assertIn("3 rows selected", dialog._sel_hint.text())
        finally:
            dialog.deleteLater()

    def test_ctrl_and_ctrl_shift_add_to_row_selection(self):
        tabs = [
            DummyDatasetTab(f"Sample {letter}", f"{letter}.csv")
            for letter in "ABCDE"
        ]
        dialog = DatasetSelectionDialog(
            tabs,
            currently_selected=tabs,
            minimum_selection=1,
            allow_grouping=True,
        )
        try:
            dialog._rows[1].mousePressEvent(DummyMouseEvent(80))
            dialog._rows[3].mousePressEvent(
                DummyMouseEvent(80, Qt.KeyboardModifier.ControlModifier)
            )
            self.assertEqual(
                [index for index, row in enumerate(dialog._rows) if row.is_selected()],
                [1, 3],
            )

            dialog._rows[4].mousePressEvent(
                DummyMouseEvent(
                    80,
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.ShiftModifier,
                )
            )
            self.assertEqual(
                [index for index, row in enumerate(dialog._rows) if row.is_selected()],
                [1, 3, 4],
            )
            self.assertTrue(all(row.is_checked() for row in dialog._rows))
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
            for row in dialog._rows[:3]:
                row.set_selected(True)
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

    def test_grouping_toolbar_omits_select_visible_and_uses_visible_buttons(self):
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
            buttons = dialog.findChildren(QPushButton)
            labels = [button.text() for button in buttons]
            include_all = next(button for button in buttons if button.text() == "Include All")

            self.assertNotIn("Select Visible", labels)
            self.assertIn("Clear Selection", labels)
            self.assertIn("Apply Group", labels)
            self.assertIn("background: #FFFDF8", include_all.styleSheet())
            self.assertNotIn("background: transparent", include_all.styleSheet())
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

    def test_group_header_color_picker_updates_shared_group_color(self):
        clear_group_color("Layer A")
        tabs = [
            DummyDatasetTab("Sample A", "A.csv", "Layer A"),
            DummyDatasetTab("Sample B", "B.csv", "Layer A"),
        ]
        dialog = DatasetSelectionDialog(
            tabs,
            currently_selected=tabs,
            minimum_selection=1,
            allow_grouping=True,
        )
        try:
            with patch(
                "gui.dataset_selection_dialog.QColorDialog.getColor",
                return_value=QColor("#123456"),
            ):
                dialog._pick_group_color("Layer A")

            self.assertEqual(group_color_map(["Layer A"])["Layer A"], "#123456")
        finally:
            dialog.deleteLater()
            clear_group_color("Layer A")


if __name__ == "__main__":
    unittest.main()
