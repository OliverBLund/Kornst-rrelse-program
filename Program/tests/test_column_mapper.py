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
        self.assertIn("Processed Curve Data -> Column Mapping", self.dialog.pathway_summary_label.text())
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
        self.assertIn("Raw Sieve Weighings -> Column Mapping", self.dialog.pathway_summary_label.text())

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
