"""
Regression tests for the redesigned dataset error tab.
"""

import csv
import os
import sys
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from gui.error_tab import ErrorTab
from gui.theme import C


APP = QApplication.instance() or QApplication(["codex-test"])


def _pump_events(milliseconds: int) -> None:
    deadline = time.monotonic() + (milliseconds / 1000.0)
    while time.monotonic() < deadline:
        APP.processEvents()
        time.sleep(0.01)


class TestErrorTabDesign(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.csv_path = os.path.join(self.tempdir.name, "bad.csv")
        with open(self.csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Sieve Size", "Passing %", "Comment"])
            writer.writerow([4.75, 100, "Top fraction"])
            writer.writerow([2.0, 84, ""])
            writer.writerow([1.0, 61, ""])

        self.tab = ErrorTab(self.csv_path, "Missing percent column")
        self.tab.resize(1280, 820)
        self.tab.show()
        APP.processEvents()

    def tearDown(self):
        self.tab.hide()
        self.tab.deleteLater()
        APP.processEvents()
        self.tempdir.cleanup()

    def test_primary_and_danger_actions_match_concept_hierarchy(self):
        self.assertEqual(self.tab.fix_button.text(), "Open Mapper")
        self.assertEqual(self.tab.remove_button.text(), "Remove")
        self.assertTrue(self.tab.fix_button.property("primary"))
        self.assertTrue(self.tab.remove_button.property("danger"))
        self.assertIn(f"background: {C.OLIVE}", self.tab.fix_button.styleSheet())
        self.assertIn("color: white", self.tab.fix_button.styleSheet())
        self.assertEqual(self.tab.fix_button.height(), 28)
        self.assertTrue(self.tab.fix_button.isEnabled())

    def test_detail_drawer_starts_collapsed_and_expands(self):
        self.assertEqual(self.tab.details_toggle.text(), "Show raw message")
        self.assertEqual(self.tab.details_container.maximumHeight(), 0)

        self.tab.toggle_details()
        _pump_events(250)

        self.assertEqual(self.tab.details_toggle.text(), "Hide raw message")
        self.assertGreater(self.tab.details_container.maximumHeight(), 0)

    def test_preview_surface_loads_rows_and_highlights_numeric_cells(self):
        self.assertGreaterEqual(self.tab.preview_table.rowCount(), 2)
        self.assertGreaterEqual(self.tab.preview_table.columnCount(), 2)
        self.assertGreaterEqual(self.tab.preview_table.minimumHeight(), 220)
        self.assertFalse(self.tab.preview_table.showGrid())
        self.assertEqual(self.tab.preview_table.frameShape(), self.tab.preview_table.Shape.NoFrame)
        self.assertEqual(
            self.tab.preview_table.horizontalHeaderItem(0).text(),
            "Sieve Size",
        )
        self.assertNotEqual(
            self.tab.preview_table.horizontalHeaderItem(0).text(),
            "Preview Error",
        )

        numeric_item = self.tab.preview_table.item(1, 0)
        self.assertIsNotNone(numeric_item)
        self.assertEqual(numeric_item.background().color().name().lower(), "#edf3e6")

    def test_source_strip_uses_clear_mapping_status(self):
        metadata = self.tab.findChildren(QLabel, "ev-strip-meta")

        self.assertEqual([label.text() for label in metadata], ["CSV", "Needs mapping"])
        self.assertTrue(metadata[-1].property("state"))

    def test_layout_stays_compact_and_constrains_auxiliary_column(self):
        side = self.tab.findChild(QWidget, "ev-side")

        self.assertIsNotNone(side)
        self.assertEqual(side.minimumWidth(), 300)
        self.assertEqual(side.maximumWidth(), 330)
        self.assertLessEqual(self.tab.minimumSizeHint().height(), 680)

        visible_copy = {label.text() for label in self.tab.findChildren(QLabel)}
        self.assertNotIn("Keep the decision surface small and obvious.", visible_copy)

    def test_update_error_message_refreshes_fault_line_and_raw_text(self):
        self.tab.update_error_message("Column header mismatch")

        self.assertEqual(self.tab.error_label.text(), "column layout needs manual confirmation")
        self.assertEqual(self.tab.details_text.toPlainText(), "Column header mismatch")


if __name__ == "__main__":
    unittest.main(verbosity=2)
