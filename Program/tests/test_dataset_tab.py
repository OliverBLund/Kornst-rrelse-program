"""
Regression tests for dataset-tab results table behavior and sizing.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QLabel, QHeaderView

from data_loader import GrainSizeData
from gui.dataset_tab import DatasetTab
from k_calculations import CalculationStatus, KCalculationResult


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


def _k_result(
    method: str,
    value: float,
    status=CalculationStatus.OK,
    conditions_met: bool = True,
    status_message: str = "",
):
    return KCalculationResult(
        method_name=method,
        k_value=value,
        formula_used="",
        status=status,
        status_message=status_message,
        conditions_met=conditions_met,
        temperature=20.0,
        porosity=0.35,
        grain_size_used="D10",
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

    def test_statistics_tab_does_not_force_tall_minimum_height(self):
        self.assertLessEqual(self.tab.statistics_widget.minimumSizeHint().height(), 120)
        self.assertLessEqual(self.tab.minimumSizeHint().height(), 520)

    def test_statistics_quality_box_explains_assessment_basis(self):
        text = self.tab.statistics_tab.quality_widget.quality_text.toPlainText()

        self.assertIn("Based on the loaded gradation curve only", text)
        self.assertIn("Monotonicity:", text)
        self.assertIn("Point density:", text)

    def test_results_bottom_summary_surfaces_ok_only_geometric_and_arithmetic_means(self):
        self.tab.apply_precomputed_results([
            _k_result("Hazen", 1.0e-4),
            _k_result("Beyer", 1.0e-3, CalculationStatus.WARNING, conditions_met=False),
            _k_result("Sauerbrei", 4.0e-4),
        ])

        self.assertFalse(self.tab._mean_summary_bar.isHidden())
        self.assertEqual(self.tab._mean_geo_value.text(), "17.28 m/d")
        self.assertEqual(self.tab._mean_geo_sub.text(), "2.00e-04 m/s")
        self.assertEqual(self.tab._mean_arith_value.text(), "21.60 m/d")
        self.assertEqual(self.tab._mean_arith_sub.text(), "2.50e-04 m/s")
        self.assertEqual(self.tab._mean_included_value.text(), "2 / 3")
        self.assertEqual(self.tab._stat_valid.text(), "2 / 3")

    def test_detail_panel_explains_warning_exclusion_even_when_conditions_met(self):
        result = _k_result(
            "Beyer",
            1.0e-3,
            CalculationStatus.WARNING,
            conditions_met=True,
            status_message="outside recommended range",
        )

        self.tab._update_detail_panel(result)
        texts = [label.text() for label in self.tab._detail_content.findChildren(QLabel)]
        joined = "\n".join(texts)

        self.assertIn("Excluded from K means: outside recommended range", joined)
        self.assertIn("Excluded from K mean calculations", joined)
        self.assertIn("Applicability conditions met", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
