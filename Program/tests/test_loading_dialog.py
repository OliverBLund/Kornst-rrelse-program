"""
Regression tests for loading dialog live-state behavior.
"""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, 'Program')

from PyQt6.QtWidgets import QApplication

from gui.loading_dialog import LoadingDialog


APP = QApplication.instance() or QApplication([])


class TestLoadingDialog(unittest.TestCase):
    def setUp(self):
        self.dialog = LoadingDialog(
            "Importing Datasets",
            "Reading selected files",
            cancellable=False,
        )

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()

    def test_update_progress_updates_live_labels(self):
        self.dialog.update_progress(2, 5, "Reading datasets", "sample_b.csv")

        self.assertEqual(self.dialog._stage_label.text(), "Reading datasets")
        self.assertEqual(self.dialog._detail_label.text(), "sample_b.csv")
        self.assertEqual(self.dialog._count_chip.text(), "2 of 5 items")
        self.assertEqual(self.dialog._activity_label.text(), "Processing item 2 of 5.")
        self.assertTrue(self.dialog._footer_status.text().startswith("Loading"))

    def test_set_activity_updates_guidance_copy(self):
        message = "Large files can take a moment."
        self.dialog.set_activity(message)
        self.assertEqual(self.dialog._note_label.text(), message)

    def test_update_progress_accepts_custom_labels(self):
        self.dialog.update_progress(
            3,
            5,
            "Integrating workspace",
            "Adding loaded items to the workspace.",
            count_label="3 of 5 items",
            activity_label="Integrating item 3 of 5.",
        )

        self.assertEqual(self.dialog._count_chip.text(), "3 of 5 items")
        self.assertEqual(self.dialog._activity_label.text(), "Integrating item 3 of 5.")

    def test_mark_finished_stops_live_animation_and_enables_close(self):
        self.dialog.update_progress(1, 3, "Reading datasets", "sample_a.csv")
        self.dialog.mark_finished("Files loaded", "3 files loaded successfully.", ok=True)

        self.assertTrue(self.dialog._finished)
        self.assertFalse(self.dialog._progress._timer.isActive())
        self.assertFalse(self.dialog._live_timer.isActive())
        self.assertEqual(self.dialog._footer_status.text(), "Done")
        self.assertEqual(self.dialog._footer_button.text(), "Close")

    def test_progress_rail_renders_without_rect_type_error(self):
        self.dialog.resize(520, self.dialog.height())
        self.dialog.update_progress(2, 5, "Reading datasets", "sample_b.csv")
        self.dialog.show()
        APP.processEvents()

        pixmap = self.dialog._progress.grab()

        self.assertFalse(pixmap.isNull())


if __name__ == '__main__':
    unittest.main(verbosity=2)
