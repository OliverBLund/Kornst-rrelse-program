"""
Regression tests for motion and interaction polish helpers.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from gui.control_panel import _SampleCard
from gui.main_window import _RichStatusBar
from gui.welcome_widget import WelcomeWidget, _HoverFrame


APP = QApplication.instance() or QApplication([])


class TestRichStatusBarPolish(unittest.TestCase):
    def setUp(self):
        self.bar = _RichStatusBar()
        self.bar.show()
        APP.processEvents()

    def tearDown(self):
        self.bar.hide()
        self.bar.deleteLater()

    def test_led_blink_uses_real_opacity_effect(self):
        self.assertIsNotNone(self.bar._led.graphicsEffect())
        self.assertAlmostEqual(self.bar._led_effect.opacity(), 1.0, places=2)

        self.bar._toggle_led()
        APP.processEvents()
        self.assertLess(self.bar._led_effect.opacity(), 1.0)

        self.bar.set_status("Import warning", ok=False)
        previous = self.bar._led_effect.opacity()
        self.bar._toggle_led()
        APP.processEvents()
        self.assertEqual(self.bar._led_effect.opacity(), previous)

    def test_segment_update_attaches_pulse_effect(self):
        self.bar.set_segment("DATASETS", "5")
        APP.processEvents()

        label = self.bar._seg_vals["DATASETS"]
        self.assertEqual(label.text(), "5")
        self.assertIsNotNone(label.graphicsEffect())


class TestWelcomePolish(unittest.TestCase):
    def test_recent_session_row_click_still_opens_session(self):
        sessions = [
            {"name": "North Core Batch", "date": "2026-04-09", "files": ["a.csv", "b.csv"]},
        ]
        widget = WelcomeWidget(recent_files=[], recent_sessions=sessions)
        widget.resize(1100, 800)
        widget.show()
        APP.processEvents()

        opened = []
        widget.open_recent_session_requested.connect(opened.append)

        rows = widget.findChildren(_HoverFrame, "rec-row")
        self.assertEqual(len(rows), 1)

        QTest.mouseClick(rows[0], Qt.MouseButton.LeftButton)
        APP.processEvents()

        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0]["name"], "North Core Batch")
        self.assertFalse(rows[0]._pressed)
        widget.deleteLater()


class TestSidebarSampleCards(unittest.TestCase):
    def test_long_dataset_names_wrap_without_pushing_controls_outside_card(self):
        card = _SampleCard(
            "long.xlsx:::Sheet with very long name",
            "Extremely Long Dataset Name With Many Words To Force Wrapping Across The Sidebar",
            "loaded",
        )
        card.resize(260, 96)
        card.show()
        APP.processEvents()

        try:
            self.assertEqual(card.width(), 260)
            self.assertTrue(card._name.wordWrap())
            self.assertGreater(card._name.height(), card._name.fontMetrics().lineSpacing())
            self.assertLess(card._name.geometry().right(), card._sel_btn.geometry().left())
            self.assertLessEqual(card._expand_btn.geometry().right(), card.rect().right())
        finally:
            card.hide()
            card.deleteLater()
            APP.processEvents()


if __name__ == "__main__":
    unittest.main(verbosity=2)
