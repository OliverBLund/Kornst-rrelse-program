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

from gui.help_dialog import HelpDialog


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
            file_path = os.path.join(self.dialog.help_dir, filename)
            if not os.path.exists(file_path):
                missing.append(filename)

        self.assertEqual(missing, [])

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
