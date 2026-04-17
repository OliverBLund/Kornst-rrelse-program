"""
Regression tests for the sidebar data inspector dialog.
"""

import csv
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication

from data_loader import GrainSizeData
from gui.dataset_inspector_dialog import DataInspectorDialog
from gui.dataset_tab import DatasetTab


APP = QApplication.instance() or QApplication(["codex-test"])


def _write_source_csv(path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["size_mm", "passing_pct", "comment"])
        writer.writerow([4.75, 100.0, "top"])
        writer.writerow([2.0, 84.0, "mid"])
        writer.writerow([1.0, 55.0, "low"])


def _build_dataset(file_path: str) -> GrainSizeData:
    dataset = GrainSizeData(
        sample_name="Sample A",
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25],
        percent_passing=[100.0, 84.0, 55.0, 28.0, 10.0],
        file_path=file_path,
    )
    dataset._source_mapping_state = {
        "raw_sieve_mode": False,
        "column_indices": {"size": 1, "passing": 2},
    }
    return dataset


class TestDatasetInspectorDialog(unittest.TestCase):
    def test_source_table_shows_full_csv_contents(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "sample.csv")
            _write_source_csv(csv_path)

            dialog = DataInspectorDialog(
                dataset=_build_dataset(csv_path),
                file_path=csv_path,
            )
            try:
                dialog.show()
                APP.processEvents()

                self.assertEqual(len(dialog._source_rows), 4)
                self.assertEqual(dialog._source_table.rowCount(), 4)
                self.assertEqual(dialog._source_table.columnCount(), 3)
                self.assertEqual(dialog._source_table.item(0, 0).text(), "size_mm")
                self.assertEqual(dialog._source_table.item(3, 2).text(), "low")
            finally:
                dialog.close()
                dialog.deleteLater()
                APP.processEvents()

    def test_apply_updates_attached_dataset_tab(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "sample.csv")
            _write_source_csv(csv_path)

            dataset = _build_dataset(csv_path)
            dataset_tab = DatasetTab(dataset)
            dialog = DataInspectorDialog(
                dataset=dataset,
                file_path=csv_path,
                dataset_tab=dataset_tab,
                mapping_state=dataset._source_mapping_state,
            )
            try:
                dataset_tab.show()
                dialog.show()
                APP.processEvents()

                dialog._table.item(1, 2).setText("82.0")
                APP.processEvents()
                dialog._apply_rows()
                APP.processEvents()

                self.assertAlmostEqual(dataset_tab.dataset.percent_passing[1], 82.0)
                self.assertFalse(dialog._dirty)
            finally:
                dialog.close()
                dialog.deleteLater()
                dataset_tab.close()
                dataset_tab.deleteLater()
                APP.processEvents()


if __name__ == "__main__":
    unittest.main(verbosity=2)
