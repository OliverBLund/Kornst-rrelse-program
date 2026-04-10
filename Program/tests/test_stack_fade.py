"""
Regression tests for stacked-page fade transitions.
"""

import os
import sys
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, 'Program')

from PyQt6.QtWidgets import QApplication, QLabel, QStackedWidget, QTabWidget

from gui.stack_fade import StackFadeController, TabFadeInController


APP = QApplication.instance() or QApplication([])


def _pump_events(milliseconds: int) -> None:
    deadline = time.monotonic() + (milliseconds / 1000.0)
    while time.monotonic() < deadline:
        APP.processEvents()
        time.sleep(0.01)


def _wait_for(predicate, milliseconds: int) -> bool:
    deadline = time.monotonic() + (milliseconds / 1000.0)
    while time.monotonic() < deadline:
        APP.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    APP.processEvents()
    return predicate()


class TestStackFadeController(unittest.TestCase):
    def setUp(self):
        self.stack = QStackedWidget()
        self.stack.addWidget(QLabel("One"))
        self.stack.addWidget(QLabel("Two"))
        self.stack.addWidget(QLabel("Three"))
        self.controller = StackFadeController(
            self.stack,
            fade_out_ms=40,
            fade_in_ms=60,
        )

    def tearDown(self):
        self.stack.hide()
        self.stack.deleteLater()

    def test_hidden_stack_switches_immediately(self):
        switched = []

        self.controller.switch_to(1, after_switch=lambda: switched.append(self.stack.currentIndex()))
        APP.processEvents()

        self.assertEqual(self.stack.currentIndex(), 1)
        self.assertEqual(switched, [1])
        self.assertFalse(self.controller.is_animating)

    def test_visible_stack_honors_latest_queued_request(self):
        self.stack.resize(320, 180)
        self.stack.show()
        APP.processEvents()

        self.controller.switch_to(1)
        self.controller.switch_to(2)
        finished = _wait_for(
            lambda: self.stack.currentIndex() == 2 and not self.controller.is_animating,
            800,
        )

        self.assertTrue(finished)
        self.assertEqual(self.stack.currentIndex(), 2)
        self.assertFalse(self.controller.is_animating)
        self.assertIsNone(self.stack.currentWidget().graphicsEffect())


class TestTabFadeInController(unittest.TestCase):
    def setUp(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(QLabel("Plot"), "Plot")
        self.tabs.addTab(QLabel("Results"), "Results")
        self.tabs.addTab(QLabel("Statistics"), "Statistics")
        self.controller = TabFadeInController(
            self.tabs,
            duration_ms=40,
        )

    def tearDown(self):
        self.tabs.hide()
        self.tabs.deleteLater()

    def test_hidden_tab_switches_without_animation(self):
        self.tabs.setCurrentIndex(1)
        APP.processEvents()

        self.assertEqual(self.tabs.currentIndex(), 1)
        self.assertFalse(self.controller.is_animating)
        self.assertIsNone(self.tabs.currentWidget().graphicsEffect())

    def test_visible_tab_switch_cleans_up_effect(self):
        self.tabs.resize(320, 180)
        self.tabs.show()
        APP.processEvents()

        self.tabs.setCurrentIndex(1)
        finished = _wait_for(
            lambda: self.tabs.currentIndex() == 1 and not self.controller.is_animating,
            600,
        )

        self.assertTrue(finished)
        self.assertEqual(self.tabs.currentIndex(), 1)
        self.assertFalse(self.controller.is_animating)
        self.assertIsNone(self.tabs.currentWidget().graphicsEffect())


if __name__ == '__main__':
    unittest.main(verbosity=2)
