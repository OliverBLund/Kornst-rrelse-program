"""
Regression tests for welcome widget action state and session resume behavior.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtWidgets import QApplication

from gui.welcome_widget import WelcomeWidget


APP = QApplication.instance() or QApplication([])


class TestWelcomeWidget(unittest.TestCase):
    def test_resume_button_disabled_without_recent_sessions(self):
        widget = WelcomeWidget(recent_files=[], recent_sessions=[])
        self.assertFalse(widget._resume_btn.isEnabled())
        widget.deleteLater()

    def test_resume_latest_session_emits_first_saved_session(self):
        sessions = [
            {"name": "North Core Batch", "date": "2026-04-09", "files": ["a.csv", "b.csv"]},
            {"name": "Older Batch", "date": "2026-03-18", "files": ["c.csv"]},
        ]
        widget = WelcomeWidget(recent_files=[], recent_sessions=sessions)
        opened = []
        widget.open_recent_session_requested.connect(opened.append)

        widget._resume_latest_session()

        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0]["name"], "North Core Batch")
        widget.deleteLater()

    def test_welcome_screen_fits_720p_without_outer_scroll(self):
        sessions = [
            {"name": "North Core Batch", "date": "2026-04-09", "files": ["a.csv", "b.csv"]},
            {"name": "Older Batch", "date": "2026-03-18", "files": ["c.csv"]},
            {"name": "Third Batch", "date": "2026-03-01", "files": ["d.csv"]},
            {"name": "Fourth Batch", "date": "2026-02-11", "files": ["e.csv"]},
        ]
        widget = WelcomeWidget(recent_files=[], recent_sessions=sessions)
        widget.resize(1280, 720)
        widget.show()
        APP.processEvents()

        self.assertEqual(widget._outer_scroll.verticalScrollBar().maximum(), 0)
        self.assertFalse(widget._title_desc.isVisible())
        self.assertFalse(widget._title_attr.isVisible())
        self.assertFalse(widget._footer_attr.isVisible())

        widget.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
