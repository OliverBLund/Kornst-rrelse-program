import math
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from analysis.comparison_snapshot import (
    ComparisonSnapshotOptions,
    DatasetAnalysisInput,
    build_comparison_snapshot,
)
from data_loader import GrainSizeData
from k_aggregation import KAggregationOptions
from k_calculations_v2 import CalculationStatus, KCalculationResult


def k_result(method: str, value: float, status=CalculationStatus.OK, conditions_met: bool = True):
    return KCalculationResult(
        method_name=method,
        k_value=value,
        formula_used="",
        status=status,
        status_message="",
        conditions_met=conditions_met,
        temperature=20.0,
        porosity=0.35,
        grain_size_used="D10",
    )


def dataset(name: str, group: str) -> GrainSizeData:
    return GrainSizeData(
        sample_name=name,
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[2.0, 1.0, 0.5, 0.25, 0.063],
        percent_passing=[100.0, 76.0, 48.0, 22.0, 5.0],
        group_name=group,
    )


class TestComparisonSnapshot(unittest.TestCase):
    def setUp(self):
        self.inputs = (
            DatasetAnalysisInput(
                label="Sample A",
                dataset=dataset("Sample A", "Layer 1"),
                group_name="Layer 1",
                k_results=(
                    k_result("Hazen", 1.0e-4),
                    k_result("Beyer", 1.0e-3, CalculationStatus.WARNING, conditions_met=False),
                ),
            ),
            DatasetAnalysisInput(
                label="Sample B",
                dataset=dataset("Sample B", "Layer 2"),
                group_name="Layer 2",
                k_results=(
                    k_result("Hazen", 4.0e-4),
                    k_result("Beyer", 1.0e-2),
                ),
            ),
        )

    def test_snapshot_combines_k_and_grain_aggregates(self):
        snapshot = build_comparison_snapshot(self.inputs)

        self.assertEqual(snapshot.dataset_count, 2)
        self.assertEqual(snapshot.group_names, ("Layer 1", "Layer 2"))
        self.assertEqual(snapshot.k.overall.included_count, 3)
        expected_k_geo = math.exp(sum(math.log(v) for v in [1.0e-4, 4.0e-4, 1.0e-2]) / 3)
        self.assertAlmostEqual(snapshot.k.overall.geometric_mean_m_s, expected_k_geo)
        self.assertEqual(snapshot.grain.overall.dataset_count, 2)
        self.assertEqual(snapshot.grain.overall.metrics["Dmean"].value_count, 2)
        self.assertIn("Layer 1", snapshot.grain.by_group)

    def test_snapshot_options_control_k_filtering_globally(self):
        snapshot = build_comparison_snapshot(
            self.inputs,
            ComparisonSnapshotOptions(
                k_options=KAggregationOptions(include_warnings=True),
            ),
        )

        self.assertEqual(snapshot.k.overall.included_count, 4)
        self.assertEqual(snapshot.k.by_method["Beyer"].value_count, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
