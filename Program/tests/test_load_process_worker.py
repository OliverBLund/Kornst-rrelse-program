"""
Regression tests for background dataset preparation.
"""

import sys
import tempfile
import unittest
import os

sys.path.insert(0, "Program")

from data_loader import GrainSizeData
from load_process_worker import _friendly_load_error, _load_mapped_source, prepare_dataset_for_ui


def build_dataset(name: str = "Sample A") -> GrainSizeData:
    return GrainSizeData(
        sample_name=name,
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
        percent_passing=[100.0, 95.0, 82.0, 61.0, 38.0, 14.0, 4.0],
    )


class TestLoadProcessWorker(unittest.TestCase):
    def test_friendly_load_error_rephrases_missing_xlrd_for_packaged_builds(self):
        message = _friendly_load_error(
            "Import xlrd failed. Install xlrd >= 2.0.1 for xls Excel support"
        )

        self.assertEqual(
            message,
            "Legacy Excel (.xls) support is unavailable in this build. Rebuild with xlrd included or convert the file to .xlsx/.csv.",
        )

    def test_prepare_dataset_for_ui_attaches_precomputed_results(self):
        dataset = build_dataset()

        prepare_dataset_for_ui(dataset, temperature=12.5)

        self.assertEqual(dataset.temperature, 12.5)
        self.assertEqual(dataset._precomputed_k_temperature, 12.5)
        self.assertEqual(dataset._precomputed_k_porosity, dataset.current_porosity)
        self.assertTrue(dataset._precomputed_k_results)
        self.assertTrue(all(result.temperature == 12.5 for result in dataset._precomputed_k_results))

    def test_mapped_cell_range_source_can_be_restored_without_dialog(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "mapped.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("size,passing\n")
                handle.write("2.0,100\n")
                handle.write("1.0,60\n")
                handle.write("0.5,20\n")

            source = {
                "file_key": csv_path,
                "file_path": csv_path,
                "sample_name": "Restored mapped sample",
                "temperature": 12.0,
                "porosity": 0.31,
                "mapping_state": {
                    "raw_sieve_mode": False,
                    "calculated_selection_mode": "range",
                    "selected_size_range": [[1, 0], [2, 0], [3, 0]],
                    "selected_percent_range": [[1, 1], [2, 1], [3, 1]],
                },
            }

            dataset = _load_mapped_source(source)

        self.assertEqual(dataset.sample_name, "Restored mapped sample")
        self.assertEqual(dataset.file_path, csv_path)
        self.assertEqual(dataset.temperature, 12.0)
        self.assertEqual(dataset.porosity, 0.31)
        self.assertEqual(dataset.particle_sizes, [2.0, 1.0, 0.5])
        self.assertEqual(dataset.percent_passing, [100.0, 60.0, 20.0])
        self.assertEqual(dataset._source_mapping_state["calculated_selection_mode"], "range")


if __name__ == "__main__":
    unittest.main(verbosity=2)
