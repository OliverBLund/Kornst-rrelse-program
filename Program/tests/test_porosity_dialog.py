"""
Regression tests for the redesigned porosity dialog.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication

from data_loader import GrainSizeData
from gui.control_panel import PorosityDialog


APP = QApplication.instance() or QApplication(["codex-test"])


class _FakeStats:
    def __init__(self):
        self.porosity = None
        self.updated = 0

    def update_display(self):
        self.updated += 1


class _FakeDatasetTab:
    def __init__(self, dataset):
        self.dataset = dataset
        self.porosity = dataset.current_porosity
        self.statistics_tab = _FakeStats()
        self.current_results = [object()]
        self.recalc_count = 0

    def calculate_k_values(self):
        self.recalc_count += 1


class _FakeTabWidget:
    def __init__(self, widgets):
        self._widgets = list(widgets)

    def count(self):
        return len(self._widgets)

    def widget(self, index):
        return self._widgets[index]


class _FakeMainWindow:
    def __init__(self, widgets):
        self.dataset_tabs_widget = _FakeTabWidget(widgets)


def _build_dataset(name: str, calc: float, current: float) -> GrainSizeData:
    dataset = GrainSizeData(
        sample_name=name,
        temperature=20.0,
        porosity=current,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25],
        percent_passing=[100.0, 84.0, 55.0, 28.0, 10.0],
        file_path=f"{name}.csv",
    )
    dataset.calculated_porosity = calc
    dataset.current_porosity = current
    return dataset


class TestPorosityDialog(unittest.TestCase):
    def setUp(self):
        auto_tab = _FakeDatasetTab(_build_dataset("Auto Sample", 0.3210, 0.3210))
        manual_tab = _FakeDatasetTab(_build_dataset("Manual Sample", 0.2875, 0.4500))
        self.tabs = [auto_tab, manual_tab]
        self.dialog = PorosityDialog(_FakeMainWindow(self.tabs))
        self.dialog.resize(1000, 720)
        self.dialog.show()
        APP.processEvents()

    def tearDown(self):
        self.dialog.hide()
        self.dialog.deleteLater()
        APP.processEvents()

    def test_summary_strip_reports_auto_and_manual_counts(self):
        self.assertEqual(self.dialog.porosity_table.rowCount(), 2)
        self.assertEqual(self.dialog.summary_label.text(), "2 datasets in workspace")
        self.assertIn("1 automatic", self.dialog.summary_meta_label.text())
        self.assertIn("1 manual override", self.dialog.summary_meta_label.text())

    def test_update_single_dataset_uses_widget_backed_dataset_name(self):
        edit_field = self.dialog.porosity_table.cellWidget(1, 3)
        self.assertEqual(edit_field.property("dataset_name"), "Manual Sample")

        edit_field.setText("0.5000")
        self.dialog.update_single_dataset(1)

        self.assertEqual(self.tabs[1].dataset.current_porosity, 0.5)
        self.assertEqual(self.tabs[1].porosity, 0.5)
        self.assertEqual(self.tabs[1].statistics_tab.porosity, 0.5)
        self.assertEqual(self.tabs[1].recalc_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
