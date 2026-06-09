import math
import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from k_aggregation import (
    KAggregationOptions,
    build_k_aggregation,
    build_k_result_summary,
    dataset_group_name,
)
from k_calculations_v2 import CalculationStatus, KCalculationResult


def result(method: str, k_value: float, status=CalculationStatus.OK, conditions_met: bool = True):
    return KCalculationResult(
        method_name=method,
        k_value=k_value,
        formula_used="",
        status=status,
        status_message="",
        conditions_met=conditions_met,
        temperature=20.0,
        porosity=0.35,
        grain_size_used="D10",
    )


class DummyTab:
    def __init__(self, name: str, group: str, results):
        self.dataset = SimpleNamespace(sample_name=name, group_name=group)
        self._results = list(results)

    def get_dataset(self):
        return self.dataset

    def get_dataset_name(self):
        return self.dataset.sample_name

    def get_results(self):
        return self._results


class TestKAggregation(unittest.TestCase):
    def setUp(self):
        self.tabs = [
            DummyTab(
                "Sample A",
                "Layer 1",
                [
                    result("Hazen", 1.0e-4),
                    result("Beyer", 1.0e-3, CalculationStatus.WARNING, conditions_met=False),
                ],
            ),
            DummyTab(
                "Sample B",
                "Layer 2",
                [
                    result("Hazen", 4.0e-4),
                    result("Beyer", 1.0e-2),
                ],
            ),
        ]

    def test_default_aggregation_excludes_warning_results(self):
        report = build_k_aggregation(self.tabs)

        self.assertEqual(report.overall.included_count, 3)
        self.assertEqual(report.overall.warning_count, 1)
        self.assertEqual(report.overall.excluded_count, 1)
        expected_geo = math.exp(sum(math.log(v) for v in [1.0e-4, 4.0e-4, 1.0e-2]) / 3)
        expected_arithmetic = sum([1.0e-4, 4.0e-4, 1.0e-2]) / 3
        self.assertAlmostEqual(report.overall.geometric_mean_m_s, expected_geo)
        self.assertAlmostEqual(report.overall.arithmetic_mean_m_s, expected_arithmetic)

    def test_warning_results_can_be_included_explicitly(self):
        report = build_k_aggregation(
            self.tabs,
            KAggregationOptions(include_warnings=True),
        )

        self.assertEqual(report.overall.included_count, 4)
        self.assertEqual(report.overall.excluded_count, 0)
        self.assertEqual(report.by_method["Beyer"].value_count, 2)

    def test_complete_case_filter_keeps_only_methods_valid_for_every_dataset(self):
        report = build_k_aggregation(
            self.tabs,
            KAggregationOptions(require_methods_in_all_datasets=True),
        )

        self.assertEqual(report.complete_methods, frozenset({"Hazen"}))
        self.assertEqual(report.overall.included_count, 2)
        self.assertEqual(report.by_method["Beyer"].value_count, 0)

    def test_selected_methods_limit_the_aggregation_population(self):
        report = build_k_aggregation(
            self.tabs,
            KAggregationOptions.from_methods(["Beyer"], include_warnings=True),
        )

        self.assertEqual(report.method_names, ("Beyer",))
        self.assertEqual(report.overall.included_count, 2)
        self.assertNotIn("Hazen", report.by_method)

    def test_group_stats_are_built_from_dataset_group_metadata(self):
        report = build_k_aggregation(self.tabs)

        self.assertEqual(report.group_names, ("Layer 1", "Layer 2"))
        self.assertEqual(report.by_group["Layer 1"].included_count, 1)
        self.assertEqual(report.by_group["Layer 2"].included_count, 2)
        self.assertEqual(dataset_group_name(SimpleNamespace()), "Ungrouped")

    def test_single_result_summary_uses_same_ok_only_policy(self):
        results = [
            result("Hazen", 1.0e-4),
            result("Beyer", 1.0e-2, CalculationStatus.WARNING, conditions_met=False),
            result("USBR", 4.0e-4),
        ]

        summary = build_k_result_summary(results)

        self.assertEqual(summary.included_count, 2)
        self.assertEqual(summary.total_cells, 3)
        self.assertEqual(summary.warning_count, 1)
        self.assertAlmostEqual(summary.geometric_mean_m_s, 2.0e-4)
        self.assertAlmostEqual(summary.arithmetic_mean_m_s, 2.5e-4)

        with_warnings = build_k_result_summary(
            results,
            KAggregationOptions(include_warnings=True),
        )
        self.assertEqual(with_warnings.included_count, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
