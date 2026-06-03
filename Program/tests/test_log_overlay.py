"""
Regression tests for the reusable in-app activity log.
"""

import logging
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from gui.log_overlay import InAppLogStore, LogDropdownPanel, QtLogHandler


APP = QApplication.instance() or QApplication([])


class TestInAppLogStore(unittest.TestCase):
    def setUp(self):
        self.store = InAppLogStore(max_events=5)

    def tearDown(self):
        self.store.deleteLater()

    def test_warning_events_increment_unread_badge_count(self):
        self.store.add_event(level="INFO", source="loader", message="Loaded sample")
        self.assertEqual(self.store.unread_important_count, 0)

        self.store.add_event(level="WARNING", source="data_loader", message="Negative retained weight")

        self.assertEqual(self.store.unread_important_count, 1)
        self.store.mark_read()
        self.assertEqual(self.store.unread_important_count, 0)

    def test_events_can_be_filtered_by_file_key(self):
        self.store.add_event(
            level="INFO",
            source="data_loader",
            message="Loaded A",
            file_key="a.xlsx:::English",
        )
        self.store.add_event(
            {
                "level": "WARNING",
                "source": "data_loader",
                "message": "Loaded B with warning",
                "context": {"file_key": "b.xlsx:::English"},
            }
        )

        events = self.store.events(file_key="b.xlsx:::English")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["message"], "Loaded B with warning")

    def test_qt_log_handler_forwards_warning_record(self):
        handler = QtLogHandler(self.store)
        record = logging.LogRecord(
            "data_loader",
            logging.WARNING,
            __file__,
            10,
            "Negative retained weight (-0.2000 g)",
            (),
            None,
        )

        handler.emit(record)

        events = self.store.events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "data_loader")
        self.assertIn("Negative retained weight", events[0]["message"])


class TestLogDropdownPanel(unittest.TestCase):
    def test_panel_opens_near_anchor_and_marks_warnings_read(self):
        parent = QWidget()
        parent.resize(720, 460)
        anchor = QPushButton("Log", parent)
        anchor.move(650, 8)
        parent.show()
        store = InAppLogStore(parent)
        panel = LogDropdownPanel(store, parent)
        store.add_event(level="WARNING", source="data_loader", message="Needs review")

        panel.show_near(anchor)
        APP.processEvents()

        try:
            self.assertTrue(panel.isVisible())
            self.assertEqual(store.unread_important_count, 0)
            self.assertGreaterEqual(panel.x(), 8)
            self.assertLessEqual(panel.x() + panel.width(), parent.width() - 8)
        finally:
            panel.hide()
            parent.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
