"""
Regression tests for dataset-tab results table behavior and sizing.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QLabel, QFrame, QHeaderView

from data_loader import GrainSizeData
from gui.dataset_tab import DatasetTab, _format_formula_html
from k_calculations import CalculationStatus, KCalculationResult
from method_registry import normalize_method_selection


APP = QApplication.instance() or QApplication([])


class TestFormulaFormatting(unittest.TestCase):
    def test_formula_formatter_handles_ascii_and_unicode_powers(self):
        formatted = _format_formula_html(
            "K = (μ/ρg) * 10^{1.291e-0.6435} * D10^2 * n³·²⁸⁷"
        )

        self.assertIn("10<sup>1.291e-0.6435</sup>", formatted)
        self.assertIn("D<sub>10</sub><sup>2</sup>", formatted)
        self.assertIn("n<sup>3.287</sup>", formatted)


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
    formula: str = "",
):
    return KCalculationResult(
        method_name=method,
        k_value=value,
        formula_used=formula,
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

    def test_method_detail_panel_is_wider_without_stacked_divider_chrome(self):
        self.assertGreaterEqual(self.tab.detail_panel.minimumWidth(), 300)
        self.assertGreaterEqual(self.tab.detail_panel.maximumWidth(), 440)

        formula = "K = (ρg/μ) * 8.3×10⁻³ * n³/(1-n)² * dₑ²"
        self.tab._update_detail_panel(_k_result("Kozeny-Carman", 7.2e-5, formula=formula))
        APP.processEvents()

        header = self.tab._detail_layout.itemAt(0).widget()
        self.assertEqual(header.objectName(), "detail-header")
        self.assertNotIn("border-bottom", header.styleSheet())
        self.assertEqual(
            len(header.findChildren(QFrame, "detail-param-table")),
            0,
        )
        self.assertEqual(
            len(header.findChildren(QLabel, "detail-k-block")),
            0,
        )
        self.assertEqual(len(header.findChildren(QFrame, "detail-k-block")), 1)

        detail_sections = [
            self.tab._detail_layout.itemAt(index).widget()
            for index in range(self.tab._detail_layout.count())
            if self.tab._detail_layout.itemAt(index).widget() is not None
            and self.tab._detail_layout.itemAt(index).widget().objectName() == "detail-section"
        ]
        self.assertGreaterEqual(len(detail_sections), 3)
        for section in detail_sections:
            self.assertNotIn("border-bottom", section.styleSheet())
            self.assertIn("border: none", section.styleSheet())

        param_tables = self.tab._detail_content.findChildren(QFrame, "detail-param-table")
        self.assertEqual(len(param_tables), 1)
        header_labels = [
            label.text()
            for label in param_tables[0].findChildren(QLabel)
            if label.text() in {"Parameter", "Value"}
        ]
        self.assertEqual(header_labels, ["Parameter", "Value"])
        self.assertGreaterEqual(
            len(param_tables[0].findChildren(QFrame, "detail-param-row")),
            4,
        )

        label_texts = [label.text() for label in self.tab._detail_content.findChildren(QLabel)]
        joined = "\n".join(label_texts)

        self.assertIn("&middot;", joined)
        self.assertIn("10<sup>-3</sup>", joined)
        self.assertIn("n<sup>3</sup>/(1-n)<sup>2</sup>", joined)
        self.assertIn("d<sub>e</sub><sup>2</sup>", joined)

    def test_statistics_tab_does_not_force_tall_minimum_height(self):
        self.assertLessEqual(self.tab.statistics_widget.minimumSizeHint().height(), 120)
        self.assertLessEqual(self.tab.minimumSizeHint().height(), 520)

    def test_statistics_data_support_reports_curve_coverage(self):
        table = self.tab.statistics_tab._support_table
        labels = [table.item(r, 0).text() for r in range(table.rowCount())]

        self.assertIn("Particle-size range", labels)
        self.assertIn("Point count", labels)
        self.assertIn("Validation messages", labels)
        # "Monotonicity" was intentionally removed as ambiguous jargon.
        self.assertNotIn("Monotonicity", " ".join(labels))

    def test_statistics_tab_exposes_summary_sections(self):
        stats = self.tab.statistics_tab

        for attr in ("info_bar", "distribution_card", "classification_card",
                     "k_summary_card", "quality_card", "context_card",
                     "internals_section"):
            self.assertTrue(hasattr(stats, attr), attr)
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
