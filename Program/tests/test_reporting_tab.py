"""
Regression tests for report-generation pre-flight validation.
"""

import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from gui.reporting_tab import ReportingTab


def _state(type_id: int, selected: list[bool], dataset_count: int):
    return SimpleNamespace(
        dataset_tabs=[object()] * dataset_count,
        _sample_selected=selected,
        _selected_type=type_id,
        TYPE_INDIVIDUAL=ReportingTab.TYPE_INDIVIDUAL,
        TYPE_COMPARISON=ReportingTab.TYPE_COMPARISON,
        TYPE_KFOCUS=ReportingTab.TYPE_KFOCUS,
    )


class TestReportingTabValidation(unittest.TestCase):
    def test_comparison_report_requires_two_selected_samples(self):
        state = _state(ReportingTab.TYPE_COMPARISON, [True], 1)

        title, message = ReportingTab._generation_validation_error(state)

        self.assertEqual(title, "Select At Least Two Samples")
        self.assertIn("two or more samples", message)

    def test_individual_report_accepts_one_selected_sample(self):
        state = _state(ReportingTab.TYPE_INDIVIDUAL, [True], 1)

        self.assertIsNone(ReportingTab._generation_validation_error(state))


if __name__ == "__main__":
    unittest.main(verbosity=2)
