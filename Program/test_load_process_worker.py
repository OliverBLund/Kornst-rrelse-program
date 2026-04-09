"""
Regression tests for background dataset preparation.
"""

import sys
import unittest

sys.path.insert(0, "Program")

from data_loader import GrainSizeData
from load_process_worker import prepare_dataset_for_ui


def build_dataset(name: str = "Sample A") -> GrainSizeData:
    return GrainSizeData(
        sample_name=name,
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
        percent_passing=[100.0, 95.0, 82.0, 61.0, 38.0, 14.0, 4.0],
    )


class TestLoadProcessWorker(unittest.TestCase):
    def test_prepare_dataset_for_ui_attaches_precomputed_results(self):
        dataset = build_dataset()

        prepare_dataset_for_ui(dataset, temperature=12.5)

        self.assertEqual(dataset.temperature, 12.5)
        self.assertEqual(dataset._precomputed_k_temperature, 12.5)
        self.assertEqual(dataset._precomputed_k_porosity, dataset.current_porosity)
        self.assertTrue(dataset._precomputed_k_results)
        self.assertTrue(all(result.temperature == 12.5 for result in dataset._precomputed_k_results))


if __name__ == "__main__":
    unittest.main(verbosity=2)
