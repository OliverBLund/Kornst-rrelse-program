"""Regression tests for the unified per-dataset input editor."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QApplication

from data_loader import GrainSizeData
from gui.dataset_inputs_dialog import DatasetInputsDialog, apply_dataset_inputs


APP = QApplication.instance() or QApplication(["codex-test"])


class _Stats:
    def __init__(self):
        self.temperature = None
        self.porosity = None
        self.updated = 0

    def update_display(self):
        self.updated += 1


class _Tab:
    def __init__(self, dataset):
        self.dataset = dataset
        self.temperature = dataset.temperature
        self.porosity = dataset.current_porosity
        self.statistics_tab = _Stats()
        self.current_results = [object()]
        self.recalculations = 0
        self.summary_updates = 0

    def calculate_k_values(self):
        self.recalculations += 1

    def update_summary_bar(self):
        self.summary_updates += 1


class _Tabs:
    def __init__(self, tabs):
        self.tabs = tabs

    def count(self):
        return len(self.tabs)

    def widget(self, index):
        return self.tabs[index]


class _Window:
    def __init__(self, tabs):
        self.dataset_tabs_widget = _Tabs(tabs)


def _dataset(name, temperature, calculated, current):
    dataset = GrainSizeData(
        sample_name=name,
        temperature=temperature,
        porosity=current,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25],
        percent_passing=[100.0, 84.0, 55.0, 28.0, 10.0],
        file_path=f"{name}.csv",
    )
    dataset.calculated_porosity = calculated
    dataset.current_porosity = current
    dataset.porosity = current
    return dataset


class TestDatasetInputsDialog(unittest.TestCase):
    def setUp(self):
        self.tabs = [
            _Tab(_dataset("Sample A", 20.0, 0.32123456, 0.32123456)),
            _Tab(_dataset("Sample B", 18.0, 0.2875, 0.45)),
            _Tab(_dataset("Sample C", 15.0, 0.31, 0.42)),
        ]
        self.dialog = DatasetInputsDialog(
            _Window(self.tabs),
            focus_dataset_name="Sample B",
        )
        self.dialog.show()
        APP.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        APP.processEvents()

    def test_shared_apply_synchronizes_model_tab_statistics_and_recalculates_once(self):
        tab = self.tabs[0]

        changed = apply_dataset_inputs(tab, temperature=12.5, porosity=0.48)

        self.assertTrue(changed)
        self.assertEqual(tab.dataset.temperature, 12.5)
        self.assertEqual(tab.temperature, 12.5)
        self.assertEqual(tab.statistics_tab.temperature, 12.5)
        self.assertEqual(tab.dataset.current_porosity, 0.48)
        self.assertEqual(tab.dataset.porosity, 0.48)
        self.assertEqual(tab.porosity, 0.48)
        self.assertEqual(tab.statistics_tab.porosity, 0.48)
        self.assertEqual(tab.recalculations, 1)
        self.assertEqual(tab.summary_updates, 1)

    def test_props_focus_selects_the_requested_dataset(self):
        self.assertEqual(self.dialog.inputs_table.currentRow(), 1)
        selected = [index.row() for index in self.dialog.inputs_table.selectionModel().selectedRows()]
        self.assertEqual(selected, [1])

    def test_source_and_automatic_columns_have_room_for_their_labels(self):
        self.assertGreaterEqual(self.dialog.inputs_table.columnWidth(4), 150)
        self.assertGreaterEqual(self.dialog.inputs_table.columnWidth(5), 145)
        self.assertGreaterEqual(
            self.dialog.inputs_table.cellWidget(0, 5).minimumWidth(),
            135,
        )

    def test_bulk_edit_applies_to_multiple_selected_rows_only(self):
        selection = self.dialog.inputs_table.selectionModel()
        selection.clearSelection()
        for row in (0, 2):
            index = self.dialog.inputs_table.model().index(row, 0)
            selection.select(
                index,
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )
        self.dialog.scope_combo.setCurrentIndex(
            self.dialog.scope_combo.findData("selected")
        )
        self.dialog.bulk_temperature.setValue(9.5)
        self.dialog._stage_bulk_temperature()
        self.dialog.apply_changes()

        self.assertEqual(self.tabs[0].temperature, 9.5)
        self.assertEqual(self.tabs[1].temperature, 18.0)
        self.assertEqual(self.tabs[2].temperature, 9.5)
        self.assertEqual(
            self.tabs[0].dataset.current_porosity,
            self.tabs[0].dataset.calculated_porosity,
        )
        self.assertEqual(self.dialog.changes_applied, 2)

    def test_use_automatic_applies_exact_value_not_display_rounding(self):
        expected = self.tabs[0].dataset.calculated_porosity
        self.dialog._stage_row_automatic(0)
        self.dialog.apply_changes()

        self.assertEqual(self.tabs[0].dataset.current_porosity, expected)
        self.assertEqual(self.tabs[0].porosity, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
