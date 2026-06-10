"""
Regression tests for welcome widget action state and session resume behavior.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QPushButton

from gui.welcome_widget import WelcomeWidget


APP = QApplication.instance() or QApplication([])


class TestWelcomeWidget(unittest.TestCase):
    def test_load_processed_button_emits_mode_signal_when_clicked(self):
        widget = WelcomeWidget(recent_files=[], recent_sessions=[])
        emitted = []
        widget.load_files_with_mode_requested.connect(emitted.append)

        load_btn = next(
            btn for btn in widget.findChildren(QPushButton)
            if btn.text() == "Processed Sieve Data"
        )
        load_btn.click()
        APP.processEvents()

        self.assertEqual(emitted, ["processed"])
        widget.deleteLater()

    def test_load_raw_sieve_button_emits_mode_signal_when_clicked(self):
        widget = WelcomeWidget(recent_files=[], recent_sessions=[])
        emitted = []
        widget.load_files_with_mode_requested.connect(emitted.append)

        load_btn = next(
            btn for btn in widget.findChildren(QPushButton)
            if btn.text() == "Raw Sieve Weighings"
        )
        load_btn.click()
        APP.processEvents()

        self.assertEqual(emitted, ["raw_sieve"])
        widget.deleteLater()

    def test_demo_button_emits_demo_signal_when_clicked(self):
        widget = WelcomeWidget(recent_files=[], recent_sessions=[])
        emitted = []
        widget.load_sample_data_requested.connect(lambda: emitted.append(True))

        demo_btn = next(
            btn for btn in widget.findChildren(QPushButton)
            if btn.text() == "Open Demo Sample"
        )
        demo_btn.click()
        APP.processEvents()

        self.assertEqual(emitted, [True])
        widget.deleteLater()

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

    def test_quick_help_button_emits_new_onboarding_topic(self):
        widget = WelcomeWidget(recent_files=[], recent_sessions=[])
        emitted = []
        widget.open_help_topic_requested.connect(emitted.append)

        help_btn = next(
            btn for btn in widget.findChildren(QPushButton)
            if btn.text() == "Excel Workbooks"
        )
        help_btn.click()
        APP.processEvents()

        self.assertEqual(emitted, ["excel_workbooks.html"])
        widget.deleteLater()

    def test_full_changelog_button_opens_help_topic(self):
        widget = WelcomeWidget(recent_files=[], recent_sessions=[])
        emitted = []
        widget.open_help_topic_requested.connect(emitted.append)

        widget._open_full_changelog()
        APP.processEvents()

        self.assertEqual(emitted, ["changelog.html"])
        widget.deleteLater()

    def test_welcome_tooltip_style_is_light_and_readable(self):
        widget = WelcomeWidget(recent_files=[], recent_sessions=[])

        stylesheet = widget.styleSheet()
        load_btn = next(
            btn for btn in widget.findChildren(QPushButton)
            if btn.text() == "Processed Sieve Data"
        )

        self.assertIn("QToolTip", stylesheet)
        self.assertIn("background: #fffdf7", stylesheet)
        self.assertIn("background-color: #fffdf7", stylesheet)
        self.assertIn("color:", stylesheet)
        self.assertEqual(
            APP.palette().color(QPalette.ColorRole.ToolTipBase).name().lower(),
            "#fffdf7",
        )
        self.assertEqual(load_btn.toolTip(), "")
        self.assertEqual(
            load_btn.property("welcomeTooltipText"),
            "Use this when files already contain sieve size and cumulative percent passing.",
        )

        widget._show_custom_tooltip(load_btn.property("welcomeTooltipText"))
        APP.processEvents()
        self.assertFalse(widget._custom_tooltip_label.isHidden())
        self.assertEqual(
            widget._custom_tooltip_label.text(),
            load_btn.property("welcomeTooltipText"),
        )
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

    def test_welcome_header_drops_batch_workspace_eyebrow_and_footer_shows_dtu(self):
        widget = WelcomeWidget(recent_files=[], recent_sessions=[])

        labels = [label.text() for label in widget.findChildren(type(widget._footer_dtu_pill))]

        self.assertNotIn("BATCH WORKSPACE", labels)
        self.assertIsNotNone(widget._footer_dtu_pill)
        self.assertEqual(widget._footer_dtu_pill.text(), "DTU")

        widget.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
