"""
Regression tests for help topic routing and bundled page coverage.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from gui.help_dialog import HelpDialog, VIRTUAL_HELP_TOPICS


APP = QApplication.instance() or QApplication([])


class TestHelpDialog(unittest.TestCase):
    def setUp(self):
        self.dialog = HelpDialog()
        APP.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        APP.processEvents()

    def test_all_configured_help_topics_exist_on_disk(self):
        missing = []
        for _title, filename, _icon_name in self.dialog._all_topics():
            if filename in VIRTUAL_HELP_TOPICS:
                continue
            file_path = os.path.join(self.dialog.help_dir, filename)
            if not os.path.exists(file_path):
                missing.append(filename)

        self.assertEqual(missing, [])

    def test_changelog_virtual_topic_loads_markdown_source(self):
        self.dialog.show_help_page("changelog.html")
        APP.processEvents()

        self.assertEqual(self.dialog.current_help_page, "changelog.html")
        text = self.dialog.content_browser.toPlainText()
        self.assertIn("Changelog", text)
        self.assertIn("0.9.6", text)
        self.assertIn("Manual QA Checklist", text)
        self.assertIn("plot data drawers", text)

    def test_dialog_defaults_to_modeless(self):
        self.assertFalse(self.dialog.isModal())
        self.assertEqual(self.dialog.windowModality(), Qt.WindowModality.NonModal)

    def test_legacy_page_request_routes_to_new_start_page(self):
        self.dialog.show_help_page("getting_started.html")
        APP.processEvents()

        self.assertEqual(self.dialog.current_help_page, "start_here.html")
        current_item = self.dialog.nav_tree.currentItem()
        self.assertIsNotNone(current_item)
        self.assertEqual(
            current_item.data(0, Qt.ItemDataRole.UserRole),
            "start_here.html",
        )

    def test_data_files_puts_examples_before_reference_material(self):
        self.dialog.show_help_page("data_files.html")
        APP.processEvents()

        text = self.dialog.content_browser.toPlainText()
        example_headings = (
            "1. Processed CSV",
            "2. Processed Excel Worksheet",
            "3. Raw Sieve Weighings in CSV",
            "4. Raw Sieve Weighings in Excel",
        )

        positions = [text.index(heading) for heading in example_headings]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(positions[-1], text.index("Choose the Correct Import"))
        self.assertIn("Particle Size (mm),Percent Passing (%)", text)
        self.assertIn(
            "Sieve Size (mm),Weight of Empty Sieve (g),"
            "Weight of Sieve + Sample (g)",
            text,
        )
        self.assertEqual(text.count("This works because:"), 5)
        irregular_position = text.index("5. Irregular Excel: Automatic or Mapper")
        self.assertGreater(irregular_position, positions[-1])
        self.assertLess(irregular_position, text.index("Choose the Correct Import"))
        experimental_position = text.index(
            "Experimental: Multiple Samples in One File"
        )
        self.assertGreater(experimental_position, irregular_position)
        self.assertLess(experimental_position, text.index("Choose the Correct Import"))
        self.assertIn("Why a gibberish header may still load", text)
        self.assertIn("uncertain sheets open the mapper", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
