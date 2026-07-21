"""Regression tests for Samples sidebar batch selection and removal."""

import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from gui.control_panel import ControlPanel


APP = QApplication.instance() or QApplication(["codex-test"])


class _WorkspaceHost:
    def __init__(self):
        self.removed_paths = []
        self.batch_calls = 0

    def _remove_tabs_for_file(self, file_path):
        self.removed_paths.append(file_path)
        return 1

    def _remove_tabs_for_files(self, file_paths):
        self.batch_calls += 1
        self.removed_paths.extend(file_paths)
        return len(file_paths)


class _PanelHarness(ControlPanel):
    def __init__(self):
        self._host_override = None
        super().__init__()

    def window(self):
        if self._host_override is not None:
            return self._host_override
        return super().window()


class TestControlPanelBatchSelection(unittest.TestCase):
    def setUp(self):
        self.panel = _PanelHarness()
        self.panel.resize(318, 900)
        self.panel.show()
        APP.processEvents()
        self.paths = [
            os.path.normpath(rf"C:\temp\sample_{index}.csv")
            for index in range(4)
        ]
        for index, file_path in enumerate(self.paths):
            self.panel.file_statuses[file_path] = "loaded"
            self.panel.add_file_to_table(
                file_path,
                "loaded",
                display_name=f"Sample {index}",
            )
        self.panel._update_inventory_bar()
        APP.processEvents()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        APP.processEvents()

    def test_plain_ctrl_and_shift_selection_do_not_change_included_scope(self):
        file_list = self.panel._file_list

        file_list._on_card_clicked(
            self.paths[0],
            Qt.KeyboardModifier.NoModifier,
        )
        file_list._on_card_clicked(
            self.paths[2],
            Qt.KeyboardModifier.ControlModifier,
        )
        self.assertEqual(
            file_list.get_batch_selected_paths(),
            [self.paths[0], self.paths[2]],
        )

        file_list._on_card_clicked(
            self.paths[3],
            Qt.KeyboardModifier.ShiftModifier,
        )

        self.assertEqual(
            file_list.get_batch_selected_paths(),
            [self.paths[2], self.paths[3]],
        )
        self.assertEqual(file_list.get_active_path(), self.paths[3])
        self.assertEqual(self.panel.get_selected_paths(), self.paths)
        self.assertEqual(self.panel._chip_selected.text(), "4 included")
        self.assertEqual(self.panel._batch_selected_label.text(), "2 selected")

    def test_ctrl_shift_adds_visible_range_to_existing_selection(self):
        file_list = self.panel._file_list
        file_list._on_card_clicked(
            self.paths[0],
            Qt.KeyboardModifier.NoModifier,
        )
        file_list._on_card_clicked(
            self.paths[3],
            Qt.KeyboardModifier.ControlModifier,
        )
        file_list._on_card_clicked(
            self.paths[1],
            (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.ShiftModifier
            ),
        )

        self.assertEqual(
            file_list.get_batch_selected_paths(),
            self.paths,
        )

    def test_select_all_visible_respects_current_filter(self):
        self.panel.set_selected_paths(
            [self.paths[0], self.paths[2]],
            emit_signal=False,
        )
        self.panel._set_filter("selected")

        self.panel._file_list.select_all_visible()

        self.assertEqual(
            self.panel._file_list.get_batch_selected_paths(),
            [self.paths[0], self.paths[2]],
        )
        self.assertEqual(self.panel._batch_selected_label.text(), "2 selected")

    def test_remove_selected_confirms_once_and_syncs_workspace(self):
        host = _WorkspaceHost()
        self.panel._host_override = host
        self.panel._file_list.set_batch_selected_paths(
            [self.paths[0], self.paths[2]]
        )

        with mock.patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as question:
            self.panel.remove_batch_selected_files()

        question.assert_called_once()
        self.assertEqual(host.batch_calls, 1)
        self.assertEqual(host.removed_paths, [self.paths[0], self.paths[2]])
        self.assertEqual(
            list(self.panel.file_statuses),
            [self.paths[1], self.paths[3]],
        )
        self.assertEqual(
            self.panel._file_list.get_batch_selected_paths(),
            [],
        )
        self.assertEqual(self.panel.samples_table.rowCount(), 2)

    def test_clear_all_confirms_once_and_syncs_every_workspace_tab(self):
        host = _WorkspaceHost()
        self.panel._host_override = host

        with (
            mock.patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ) as question,
            mock.patch.object(
                self.panel,
                "update_ui_state",
                wraps=self.panel.update_ui_state,
            ) as update_ui_state,
        ):
            self.panel.clear_all_files()

        question.assert_called_once()
        update_ui_state.assert_called_once()
        self.assertEqual(host.batch_calls, 1)
        self.assertEqual(host.removed_paths, self.paths)
        self.assertEqual(self.panel.file_statuses, {})
        self.assertEqual(self.panel._file_list.get_loaded_count(), 0)
        self.assertEqual(self.panel.samples_table.rowCount(), 0)

    def test_header_and_batch_actions_fit_the_minimum_sidebar_width(self):
        controls = [
            self.panel._batch_selected_label,
            self.panel._pill_all,
            self.panel._pill_sel,
            self.panel._pill_rev,
            self.panel._manage_samples_btn,
            self.panel._select_visible_btn,
            self.panel._clear_batch_selection_btn,
            self.panel._remove_selected_btn,
            self.panel._clear_all_samples_btn,
        ]

        for control in controls:
            top_left = control.mapTo(self.panel, control.rect().topLeft())
            self.assertGreaterEqual(top_left.x(), 0)
            self.assertLessEqual(
                top_left.x() + control.width(),
                self.panel.width(),
                control.text(),
            )

        filter_y = self.panel._pill_all.mapTo(
            self.panel,
            self.panel._pill_all.rect().topLeft(),
        ).y()
        self.assertEqual(
            self.panel._manage_samples_btn.mapTo(
                self.panel,
                self.panel._manage_samples_btn.rect().topLeft(),
            ).y(),
            filter_y,
        )
        button_texts = [
            button.text()
            for button in self.panel.findChildren(type(self.panel._pill_all))
        ]
        self.assertIn("Add", button_texts)
        self.assertNotIn("+ Add", button_texts)

    def test_filter_labels_have_stable_width_and_sidebar_tooltips_use_theme(self):
        for button, label in (
            (self.panel._pill_all, "All"),
            (self.panel._pill_sel, "Included"),
            (self.panel._pill_rev, "Review"),
            (self.panel._manage_samples_btn, "Scope & Groups"),
        ):
            text_width = button.fontMetrics().horizontalAdvance(label)
            self.assertGreater(button.width(), text_width)

        stylesheet = self.panel.styleSheet()
        self.assertIn("QToolTip", stylesheet)
        self.assertIn("background: #fffdf7", stylesheet)
        self.assertIn(f"border: 1px solid #6b8e23", stylesheet)
        self.assertIn("color: #2f2f2f", stylesheet)

        tooltip_controls = (
            self.panel._manage_samples_btn,
            self.panel._select_visible_btn,
            self.panel._clear_batch_selection_btn,
            self.panel._remove_selected_btn,
            self.panel._clear_all_samples_btn,
        )
        for control in tooltip_controls:
            local_stylesheet = control.styleSheet()
            self.assertIn("QToolTip", local_stylesheet, control.toolTip())
            self.assertIn("background: #fffdf7", local_stylesheet)
            self.assertIn("border: 1px solid #6b8e23", local_stylesheet)
            self.assertIn("color: #2f2f2f", local_stylesheet)


if __name__ == "__main__":
    unittest.main(verbosity=2)
