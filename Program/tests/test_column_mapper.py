"""
Regression tests for column-mapper mode switching and pathway guidance.
"""

import os
import sys
import tempfile
import unittest

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QFormLayout, QTableWidgetSelectionRange

from gui.column_mapper import ColumnMapperDialog


APP = QApplication.instance() or QApplication([])


class TestColumnMapperDialog(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.excel_path = os.path.join(self._tempdir.name, "grain_data.xlsx")

        with pd.ExcelWriter(self.excel_path) as writer:
            pd.DataFrame(
                {
                    "Size mm": [4.75, 2.0, 1.0],
                    "% Passing": [100.0, 84.0, 55.0],
                    "% Retained": [0.0, 16.0, 45.0],
                }
            ).to_excel(writer, sheet_name="Calculated", index=False)
            pd.DataFrame(
                {
                    "Sieve Size": [4.75, 2.0, 1.0],
                    "Empty Sieve": [100.0, 101.0, 102.0],
                    "Sieve + Sample": [110.0, 107.5, 104.0],
                }
            ).to_excel(writer, sheet_name="Raw", index=False)

        self.dialog = ColumnMapperDialog(self.excel_path)
        APP.processEvents()

    def _write_nbal_style_workbook(self, filename: str = "nbal_like.xlsx") -> str:
        path = os.path.join(self._tempdir.name, filename)
        rows = [["" for _ in range(7)] for _ in range(60)]
        rows[0][0] = "Particle-size analysis"
        rows[6] = ["Mash size", "sieve+fraction", "sieve", "weight in", "mass", "", "Cumulative mass"]
        rows[7] = ["d mmm", "(g)", "(g)", "sieve (g)", "procentages", "on curve", "procentages"]

        data_rows = [
            [2, 137.23, 135.97, 1.26, 1.864181, "", 100.0],
            [1, 133.33, 118.71, 14.62, 21.630419, 2, 98.1358189081225],
            [0.6, 137.97, 117.21, 20.76, 30.714603, 1, 76.50540020713122],
            [0.355, 120.6, 106.85, 13.75, 20.343246, 0.6, 45.79079745524485],
            [0.25, 116.55, 105.56, 10.99, 16.259802, 0.355, 25.447551412930903],
            [0.18, 107.85, 104.25, 3.6, 5.326232, 0.25, 9.187749667110527],
            [0.125, 104.91, 103.56, 1.35, 1.997337, 0.18, 3.861517976031976],
            [0.09, 102.78, 102.41, 0.37, 0.547418, 0.125, 1.8641810918775248],
            [0.063, 104.18, 104.02, 0.16, 0.236721, 0.09, 1.3167628347388882],
            ["Pan", 75.31, 74.58, 0.73, 1.080041, 0.063, 1.0800414262464917],
        ]
        for row_index, row in enumerate(data_rows, start=11):
            rows[row_index] = row
        rows[52][0] = "Hidden below old 50-row preview"

        with pd.ExcelWriter(path) as writer:
            pd.DataFrame(rows).to_excel(writer, sheet_name="English", header=False, index=False)
        return path

    def _write_raw_metadata_workbook(self, filename: str = "raw_metadata.xlsx") -> str:
        path = os.path.join(self._tempdir.name, filename)
        rows = [
            ["Proeve vaegt", "", "341.73", "gram"],
            ["Sigtetab %", "-1.603051583802746", "", ""],
            ["Maskevidde-", "Sigte + fraktion", "sigte tom", "vaegt af"],
            ["d mmm", "(g)", "(g)", "fraktion (g)"],
            ["", "", "", ""],
            ["", "", "", "0"],
            ["", "", "", "0"],
            [2.0, 381.26, 343.59, 37.67],
            [1.0, 370.47, 308.41, 62.06],
            [0.5, 363.29, 274.22, 89.07],
            [0.25, 350.0, 300.0, 50.0],
        ]
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame(rows).to_excel(writer, sheet_name="English", header=False, index=False)
        return path

    def tearDown(self):
        excel_file = getattr(self.dialog, "_excel_file", None)
        if excel_file is not None and hasattr(excel_file, "close"):
            excel_file.close()
        self.dialog.close()
        self.dialog.deleteLater()
        APP.processEvents()
        self._tempdir.cleanup()

    def test_default_excel_mode_starts_in_calculated_column_mapping(self):
        self.assertFalse(self.dialog.raw_sieve_mode)
        self.assertEqual(self.dialog.calculated_selection_mode, "column")
        self.assertFalse(self.dialog.mapping_group.isHidden())
        self.assertTrue(self.dialog.range_tools_group.isHidden())
        self.assertTrue(self.dialog.raw_sieve_group.isHidden())
        self.assertIsNotNone(self.dialog._mapping_splitter)
        self.assertIn("Processed Curve -> Columns", self.dialog.pathway_summary_label.text())
        self.assertIn("Check the sheets you want to import", self.dialog.sheet_info_label.text())
        self.assertLess(self.dialog.sizeHint().height(), 900)

    def test_switching_back_from_raw_restores_previous_calculated_selection_method(self):
        self.dialog.switch_to_range_mode()
        APP.processEvents()
        self.assertEqual(self.dialog.calculated_selection_mode, "range")
        self.assertFalse(self.dialog.range_tools_group.isHidden())

        self.dialog.switch_to_raw_sieve_mode()
        APP.processEvents()
        self.assertTrue(self.dialog.raw_sieve_mode)
        self.assertFalse(self.dialog.raw_sieve_group.isHidden())
        self.assertTrue(self.dialog.mapping_group.isHidden())
        self.assertTrue(self.dialog.range_tools_group.isHidden())
        self.assertFalse(self.dialog.column_mode_btn.isEnabled())
        self.assertFalse(self.dialog.range_mode_btn.isEnabled())
        self.assertIn("Raw Sieve -> Columns", self.dialog.pathway_summary_label.text())

        self.dialog.switch_to_calculated_mode()
        APP.processEvents()
        self.assertFalse(self.dialog.raw_sieve_mode)
        self.assertEqual(self.dialog.calculated_selection_mode, "range")
        self.assertTrue(self.dialog.mapping_group.isHidden())
        self.assertFalse(self.dialog.range_tools_group.isHidden())

    def test_sheet_guidance_updates_for_single_sheet_range_limitation(self):
        self.dialog.switch_to_range_mode()
        APP.processEvents()
        self.assertIn("one sheet at a time", self.dialog.sheet_info_label.text())

        self.dialog.switch_to_raw_sieve_mode()
        APP.processEvents()
        self.assertIn("same raw sieve column mapping", self.dialog.sheet_info_label.text())

    def test_mapper_inspector_keeps_readable_control_width(self):
        self.assertIsNotNone(self.dialog._mapping_splitter)
        controls = self.dialog._mapping_splitter.widget(0)
        self.assertGreaterEqual(controls.minimumWidth(), 390)
        self.assertEqual(
            self.dialog.mapping_group.layout().rowWrapPolicy(),
            QFormLayout.RowWrapPolicy.WrapAllRows,
        )

    def test_processed_mapping_requires_cumulative_passing_and_hides_retained_role(self):
        mapping_form = self.dialog.mapping_group.layout()
        passing_label = mapping_form.labelForField(self.dialog.passing_combo)

        self.assertEqual(
            passing_label.text(),
            "Cumulative Percent Passing (0-100): *",
        )
        self.assertIsNone(mapping_form.labelForField(self.dialog.retained_combo))
        self.assertTrue(self.dialog.retained_combo.isHidden())
        self.assertEqual(self.dialog.retained_combo.currentIndex(), 0)

    def test_range_mode_can_mark_selected_size_and_passing_cells(self):
        self.dialog.switch_to_range_mode()
        APP.processEvents()

        self.dialog.preview_table.setRangeSelected(
            QTableWidgetSelectionRange(1, 0, 3, 0),
            True,
        )
        self.dialog._mark_current_selection("size")

        self.dialog.preview_table.setRangeSelected(
            QTableWidgetSelectionRange(1, 1, 3, 1),
            True,
        )
        self.dialog._mark_current_selection("percent")

        self.assertEqual(len(self.dialog.selected_size_range), 3)
        self.assertEqual(len(self.dialog.selected_percent_range), 3)
        self.assertIn("3 size cells", self.dialog.size_range_count_label.text())
        self.assertIn("3 passing cells", self.dialog.percent_range_count_label.text())

    def test_excel_preview_uses_full_sheet_and_applies_detected_curve(self):
        path = self._write_nbal_style_workbook()
        dialog = ColumnMapperDialog(path, sheet_name="English")
        APP.processEvents()
        try:
            self.assertEqual(len(dialog.sample_data), 53)
            self.assertEqual(dialog.sample_data[52][0], "Hidden below old 50-row preview")
            self.assertEqual(dialog.calculated_selection_mode, "range")
            self.assertFalse(dialog.raw_sieve_mode)
            self.assertEqual(len(dialog.selected_size_range), 9)
            self.assertEqual(len(dialog.selected_percent_range), 9)
            self.assertEqual(dialog.selected_size_range[0], (12, 5))
            self.assertEqual(dialog.selected_percent_range[0], (12, 6))

            sizes, passing = dialog.extract_data()
            self.assertEqual(sizes[:3], [2.0, 1.0, 0.6])
            self.assertAlmostEqual(passing[0], 98.1358189081225)
        finally:
            dialog.close()
            dialog.deleteLater()
            APP.processEvents()

    def test_raw_sieve_detection_includes_pan_mass(self):
        path = self._write_nbal_style_workbook("nbal_raw_like.xlsx")
        dialog = ColumnMapperDialog(path, sheet_name="English", initial_state={"raw_sieve_mode": True})
        APP.processEvents()
        try:
            self.assertTrue(dialog.raw_sieve_mode)
            self.assertEqual(dialog.raw_size_combo.currentIndex(), 1)
            self.assertEqual(dialog.sieve_sample_combo.currentIndex(), 2)
            self.assertEqual(dialog.empty_sieve_combo.currentIndex(), 3)

            sizes, passing = dialog.extract_data()
            self.assertEqual(len(sizes), 9)
            self.assertAlmostEqual(passing[0], 98.135819, places=5)
            self.assertAlmostEqual(passing[-1], 1.080041, places=5)
        finally:
            dialog.close()
            dialog.deleteLater()
            APP.processEvents()

    def test_raw_sieve_detection_refreshes_dropdown_labels_to_detected_header_row(self):
        path = self._write_raw_metadata_workbook()
        dialog = ColumnMapperDialog(path, sheet_name="English", initial_state={"raw_sieve_mode": True})
        APP.processEvents()
        try:
            self.assertTrue(dialog.raw_sieve_mode)
            self.assertEqual(dialog.header_row, 2)
            self.assertEqual(dialog.raw_size_combo.currentText(), "Maskevidde-")
            self.assertEqual(dialog.sieve_sample_combo.currentText(), "Sigte + fraktion")
            self.assertEqual(dialog.empty_sieve_combo.currentText(), "sigte tom")
            self.assertNotIn("Sigtetab", dialog.raw_size_combo.currentText())

            sizes, passing = dialog.extract_data()
            self.assertEqual(sizes[:3], [2.0, 1.0, 0.5])
            self.assertEqual(len(passing), 4)
        finally:
            dialog.close()
            dialog.deleteLater()
            APP.processEvents()

    def test_raw_sieve_mapping_rejects_duplicate_role_columns(self):
        dialog = ColumnMapperDialog(self.excel_path, sheet_name="Raw", initial_state={"raw_sieve_mode": True})
        APP.processEvents()
        try:
            dialog.raw_size_combo.setCurrentIndex(1)
            dialog.empty_sieve_combo.setCurrentIndex(1)
            dialog.sieve_sample_combo.setCurrentIndex(3)

            with self.assertRaisesRegex(ValueError, "three different columns"):
                dialog.extract_data()
        finally:
            dialog.close()
            dialog.deleteLater()
            APP.processEvents()


if __name__ == "__main__":
    unittest.main(verbosity=2)
