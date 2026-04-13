"""
Regression tests for dataset-tab results table behavior and sizing.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QHeaderView

from data_loader import GrainSizeData
from gui.dataset_tab import DatasetTab


APP = QApplication.instance() or QApplication([])


def _build_dataset() -> GrainSizeData:
    return GrainSizeData(
        sample_name="Sample A",
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25],
        percent_passing=[100.0, 84.0, 55.0, 28.0, 10.0],
        file_path="sample_a.csv",
    )


class TestDatasetTabResultsTable(unittest.TestCase):
    def setUp(self):
        self.tab = DatasetTab(_build_dataset())
        self.tab.resize(1100, 760)
        self.tab.show()
        APP.processEvents()

    def tearDown(self):
        self.tab.hide()
        self.tab.deleteLater()
        APP.processEvents()

    def test_results_table_uses_row_highlight_without_per_cell_left_border(self):
        style = self.tab.results_table.styleSheet()
        self.assertIn("QTableWidget::item:selected", style)
        self.assertNotIn("border-left", style)
        self.assertEqual(
            self.tab.results_table.selectionBehavior(),
            self.tab.results_table.SelectionBehavior.SelectRows,
        )

    def test_results_table_stretches_primary_columns(self):
        header = self.tab.results_table.horizontalHeader()
        self.assertEqual(header.sectionResizeMode(0), QHeaderView.ResizeMode.Stretch)
        self.assertEqual(header.sectionResizeMode(1), QHeaderView.ResizeMode.Stretch)
        self.assertEqual(header.sectionResizeMode(5), QHeaderView.ResizeMode.ResizeToContents)


if __name__ == "__main__":
    unittest.main(verbosity=2)
