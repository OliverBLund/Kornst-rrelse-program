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
from PyQt6.QtCore import Qt

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

    def _write_multi_sample_workbook(self, filename: str = "multi_sample.xlsx") -> str:
        path = os.path.join(self._tempdir.name, filename)
        rows = [
            ["", "Sample A", "Sample B"],
            ["Particle Size (mm)", "Percent Passing", "Percent Passing"],
            [0.063, 5.0, 8.0],
            [0.125, 18.0, 24.0],
            [0.25, 42.0, 50.0],
            [0.5, 70.0, 76.0],
            [1.0, 92.0, 95.0],
            [2.0, 100.0, 100.0],
        ]
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame(rows).to_excel(
                writer, sheet_name="Data", header=False, index=False
            )
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
        self.assertGreaterEqual(self.dialog.sizeHint().width(), 1300)

    def test_range_workflow_adapts_between_processed_and_raw_input_types(self):
        self.dialog.switch_to_range_mode()
        APP.processEvents()
        self.assertEqual(self.dialog.calculated_selection_mode, "range")
        self.assertFalse(self.dialog.range_tools_group.isHidden())

        self.dialog.switch_to_raw_sieve_mode()
        APP.processEvents()
        self.assertTrue(self.dialog.raw_sieve_mode)
        self.assertTrue(self.dialog.raw_sieve_group.isHidden())
        self.assertTrue(self.dialog.mapping_group.isHidden())
        self.assertFalse(self.dialog.range_tools_group.isHidden())
        self.assertTrue(self.dialog._header_section.isHidden())
        self.assertIn("Raw Sieve -> Cell Ranges", self.dialog.pathway_summary_label.text())
        self.assertIn("Step 1 of 3", self.dialog.range_step_label.text())

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
        self.assertIn("raw-sieve range pattern", self.dialog.sheet_info_label.text())

    def test_mapper_inspector_keeps_readable_control_width(self):
        self.assertIsNotNone(self.dialog._mapping_splitter)
        controls = self.dialog._mapping_splitter.widget(0)
        self.assertGreaterEqual(controls.minimumWidth(), 330)
        self.assertEqual(
            self.dialog.mapping_group.layout().rowWrapPolicy(),
            QFormLayout.RowWrapPolicy.WrapAllRows,
        )

    def test_processed_mapping_requires_cumulative_passing_and_hides_retained_role(self):
        mapping_form = self.dialog.mapping_group.layout()
        passing_label = mapping_form.labelForField(self.dialog.passing_combo)

        self.assertEqual(
            passing_label.text(),
            "Cumulative percent passing (0-100):",
        )
        self.assertIsNone(mapping_form.labelForField(self.dialog.retained_combo))
        self.assertTrue(self.dialog.retained_combo.isHidden())
        self.assertEqual(self.dialog.retained_combo.currentIndex(), 0)

    def test_header_row_change_preserves_deliberate_column_positions(self):
        self.dialog.size_combo.setCurrentIndex(3)
        self.dialog.passing_combo.setCurrentIndex(1)

        self.dialog.update_headers(1)

        self.assertEqual(self.dialog.header_row, 1)
        self.assertEqual(self.dialog.size_combo.currentIndex(), 3)
        self.assertEqual(self.dialog.passing_combo.currentIndex(), 1)

    def test_header_row_control_uses_visible_spreadsheet_row_numbers(self):
        self.dialog.header_row_spin.setValue(2)

        self.assertEqual(self.dialog.header_row, 1)
        self.assertEqual(self.dialog.header_row_spin.value(), 2)

    def test_column_labels_include_spreadsheet_letters(self):
        labels = self.dialog._labeled_column_headers(["Value", "Value", "Passing"])

        self.assertEqual(labels, ["A - Value", "B - Value", "C - Passing"])

    def test_retained_guidance_is_contextual(self):
        self.assertFalse(self.dialog.retained_guidance_label.isHidden())

        self.dialog.switch_to_range_mode()
        APP.processEvents()

        self.assertTrue(self.dialog.retained_guidance_label.isHidden())
        self.assertTrue(self.dialog._header_section.isHidden())

    def test_header_row_change_auto_detects_only_unmapped_roles(self):
        path = os.path.join(self._tempdir.name, "two_header_rows.xlsx")
        rows = [
            ["Size old", "% Passing old", "Manual choice"],
            ["Diameter", "Finer", "Other"],
            [4.75, 100.0, 10.0],
            [2.0, 84.0, 20.0],
            [1.0, 55.0, 30.0],
        ]
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame(rows).to_excel(
                writer, sheet_name="Data", header=False, index=False
            )

        dialog = ColumnMapperDialog(path, sheet_name="Data")
        APP.processEvents()
        try:
            dialog.size_combo.setCurrentIndex(3)
            dialog.passing_combo.setCurrentIndex(0)

            dialog.update_headers(1)

            self.assertEqual(dialog.size_combo.currentIndex(), 3)
            self.assertEqual(dialog.passing_combo.currentIndex(), 2)
            self.assertEqual(dialog.size_combo.currentText(), "C - Other")
            self.assertEqual(dialog.passing_combo.currentText(), "B - Finer")
        finally:
            dialog.close()
            dialog.deleteLater()
            APP.processEvents()

    def test_range_mode_can_mark_selected_size_and_passing_cells(self):
        self.dialog.switch_to_range_mode()
        APP.processEvents()

        self.dialog.preview_table.setRangeSelected(
            QTableWidgetSelectionRange(1, 0, 3, 0),
            True,
        )
        APP.processEvents()
        self.assertIn("A2:A4", self.dialog.active_range_label.text())
        self.assertTrue(self.dialog.confirm_range_btn.isEnabled())
        self.assertIn(
            "selection-background-color: #9fc0dc",
            self.dialog.preview_table.styleSheet(),
        )
        self.dialog._confirm_guided_range_selection()

        self.dialog.preview_table.setRangeSelected(
            QTableWidgetSelectionRange(1, 1, 3, 1),
            True,
        )
        self.dialog._confirm_guided_range_selection()

        self.assertEqual(len(self.dialog.selected_size_range), 3)
        self.assertEqual(len(self.dialog.selected_percent_range), 3)
        self.assertIn("Particle size: A2:A4", self.dialog.size_range_count_label.text())
        self.assertIn("Passing: B2:B4", self.dialog.percent_range_count_label.text())

    def test_import_action_tracks_mapping_validation(self):
        self.dialog.size_combo.setCurrentIndex(0)
        self.dialog.passing_combo.setCurrentIndex(0)
        self.dialog._refresh_result_preview()

        self.assertFalse(self.dialog.import_button.isEnabled())
        self.assertEqual(self.dialog.result_status_label.text(), "Mapping incomplete")
        self.assertTrue(self.dialog.checks_title.isHidden())

        self.dialog.size_combo.setCurrentIndex(1)
        self.dialog.passing_combo.setCurrentIndex(2)
        self.dialog._refresh_result_preview()

        self.assertTrue(self.dialog.import_button.isEnabled())
        self.assertEqual(self.dialog.result_status_label.text(), "Ready to import")
        self.assertFalse(self.dialog.checks_title.isHidden())

    def test_multi_sample_confirmation_returns_selected_curves(self):
        path = self._write_multi_sample_workbook()
        dialog = ColumnMapperDialog(
            path,
            sheet_name="Data",
            multi_sample_mode=True,
        )
        APP.processEvents()
        try:
            self.assertTrue(dialog._is_multi_sample_mode())
            self.assertEqual(dialog.multi_sample_list.count(), 2)
            self.assertFalse(dialog._multi_sample_section.isHidden())
            self.assertFalse(dialog.multi_sample_group.isHidden())
            self.assertFalse(dialog.multi_sample_list.isHidden())
            self.assertTrue(dialog._mapping_section.isHidden())
            self.assertEqual(dialog.import_button.text(), "Import 2 samples")
            self.assertEqual(dialog.result_status_label.text(), "Sample A")

            second = dialog.multi_sample_list.item(1)
            second.setCheckState(Qt.CheckState.Unchecked)
            APP.processEvents()
            self.assertEqual(dialog.import_button.text(), "Import 1 sample")

            results = dialog.get_mapping_results()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["sample_name"], "Sample A")
            self.assertEqual(results[0]["percent_passing"][:2], [5.0, 18.0])
            self.assertEqual(
                results[0]["mapping_state"]["selected_percent_range"][0],
                [2, 1],
            )
        finally:
            dialog.close()
            dialog.deleteLater()
            APP.processEvents()

    def test_guided_processed_range_flow_exposes_one_role_at_a_time(self):
        self.dialog.switch_to_range_mode()
        APP.processEvents()
        self.assertIn("Step 1 of 2", self.dialog.range_step_label.text())

        self.dialog.preview_table.setRangeSelected(
            QTableWidgetSelectionRange(1, 0, 3, 0), True
        )
        self.dialog._confirm_guided_range_selection()
        self.assertIn("Step 2 of 2", self.dialog.range_step_label.text())

        self.dialog.preview_table.setRangeSelected(
            QTableWidgetSelectionRange(1, 1, 3, 1), True
        )
        self.dialog._confirm_guided_range_selection()
        self.assertIn("Ranges ready", self.dialog.range_step_label.text())
        self.assertEqual(len(self.dialog.selected_size_range), 3)
        self.assertEqual(len(self.dialog.selected_percent_range), 3)

    def test_guided_raw_ranges_extract_and_restore_three_roles(self):
        self.dialog.reload_sheet("Raw")
        self.dialog.switch_to_raw_sieve_mode()
        self.dialog._toggle_range_workflow()
        APP.processEvents()

        for column in range(3):
            self.dialog.preview_table.setRangeSelected(
                QTableWidgetSelectionRange(1, column, 3, column), True
            )
            self.dialog._confirm_guided_range_selection()

        sizes, passing = self.dialog.extract_data()
        self.assertEqual(len(sizes), 3)
        self.assertEqual(len(passing), 3)
        self.assertIn("Ranges ready", self.dialog.range_step_label.text())

        state = self.dialog.get_mapping_state()
        self.assertTrue(state["raw_sieve_mode"])
        self.assertEqual(state["calculated_selection_mode"], "range")
        self.assertEqual(len(state["selected_empty_range"]), 3)
        self.assertEqual(len(state["selected_full_range"]), 3)

        pattern = self.dialog.learn_pattern_from_selection()
        self.assertEqual(pattern["data_type"], "raw_sieve")
        propagated = self.dialog.apply_pattern_to_file(
            f"{self.excel_path}:::Raw"
        )
        self.assertEqual(len(propagated["particle_sizes"]), 3)
        self.assertEqual(len(propagated["percent_passing"]), 3)

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
            self.assertEqual(dialog.raw_size_combo.currentText(), "A - Maskevidde-")
            self.assertEqual(dialog.sieve_sample_combo.currentText(), "B - Sigte + fraktion")
            self.assertEqual(dialog.empty_sieve_combo.currentText(), "C - sigte tom")
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
