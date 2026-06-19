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
from method_registry import normalize_method_selection


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

    def test_statistics_tab_keeps_current_legacy_summary_panels_bounded(self):
        stats = self.tab.statistics_tab

        self.assertTrue(hasattr(stats, "percentiles_text"))
        self.assertTrue(hasattr(stats, "gradation_text"))
        self.assertTrue(hasattr(stats, "special_diameters_text"))
        self.assertTrue(hasattr(stats, "k_stats_widget"))
        self.assertLessEqual(self.tab.statistics_widget.minimumSizeHint().height(), 520)

    def test_results_cards_surface_ok_only_geometric_and_arithmetic_means(self):
        self.tab.apply_precomputed_results([
            _k_result("Hazen", 1.0e-4),
            _k_result("Beyer", 1.0e-3, CalculationStatus.WARNING, conditions_met=False),
            _k_result("Sauerbrei", 4.0e-4),
        ])

        self.assertFalse(self.tab.res_bar.isHidden())
        self.assertFalse(hasattr(self.tab, "_mean_summary_bar"))
        self.assertEqual(self.tab._stat_k_geo_md.text(), "17.28")
        self.assertEqual(self.tab._stat_k_arith_md.text(), "21.60")
        self.assertEqual(self.tab._stat_valid.text(), "2 / 3")

    def test_active_methods_filter_public_results_without_dropping_full_cache(self):
        self.tab.set_active_methods(["Sauerbrei", "Hazen"], refresh=False)
        self.tab.apply_precomputed_results([
            _k_result("Hazen", 1.0e-4),
            _k_result("Beyer", 2.0e-4),
            _k_result("Sauerbrei", 4.0e-4),
        ])

        self.assertEqual(
            [result.method_name for result in self.tab.get_results()],
            ["Hazen", "Sauerbrei"],
        )
        self.assertEqual(len(self.tab.get_all_results()), 3)
        self.assertEqual(self.tab.results_table.rowCount(), 2)

        self.tab.set_active_methods(["Beyer"])
        self.assertEqual(
            [result.method_name for result in self.tab.get_results()],
            ["Beyer"],
        )
        self.assertEqual(len(self.tab.get_all_results()), 3)

    def test_results_table_can_expand_from_method_subset_back_to_all_methods(self):
        self.tab.nested_tabs.setCurrentIndex(1)
        self.tab.set_active_methods(["Hazen", "Beyer"], refresh=False)
        self.tab.apply_precomputed_results([
            _k_result("Hazen", 1.0e-4),
            _k_result("Beyer", 2.0e-4),
            _k_result("USBR", 3.0e-4),
            _k_result("Sauerbrei", 4.0e-4),
        ])
        self.tab.results_table.selectRow(0)
        APP.processEvents()

        self.tab.set_active_methods(["Hazen", "Beyer", "USBR", "Sauerbrei"])
        APP.processEvents()

        self.assertEqual(self.tab.results_table.rowCount(), 4)
        self.assertEqual(
            [result.method_name for result in self.tab.get_results()],
            ["Hazen", "Beyer", "Sauerbrei", "USBR"],
        )
        self.assertEqual(len(self.tab.get_all_results()), 4)

    def test_method_selection_normalization_keeps_canonical_order(self):
        self.assertEqual(
            normalize_method_selection(["Beyer", "Hazen"], available_methods=("Hazen", "Beyer")),
            ("Hazen", "Beyer"),
        )

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
