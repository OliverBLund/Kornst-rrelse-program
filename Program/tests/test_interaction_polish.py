"""
Regression tests for motion and interaction polish helpers.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton, QToolButton, QToolTip

from gui.control_panel import _SampleCard
from gui.main_window import _RichStatusBar
from gui.theme import apply_tooltip_style
from gui.welcome_widget import WelcomeWidget, _HoverFrame


APP = QApplication.instance() or QApplication([])


class TestGlobalTooltipStyle(unittest.TestCase):
    def test_popup_overrides_dark_source_widget_palette_at_show_time(self):
        apply_tooltip_style(APP)
        source = QPushButton('Pin')
        palette = source.palette()
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor('#000000'))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor('#000000'))
        source.setPalette(palette)
        source.show()

        QToolTip.showText(source.mapToGlobal(QPoint(2, 2)), 'Pin this dataset', source)
        APP.processEvents()
        popup = next(
            widget for widget in APP.topLevelWidgets()
            if widget.metaObject().className() == 'QTipLabel'
        )

        self.assertEqual(popup.palette().color(QPalette.ColorRole.Window).name(), '#fffdf7')
        self.assertEqual(popup.palette().color(QPalette.ColorRole.WindowText).name(), '#2f2f2f')
        self.assertIn('background-color: #fffdf7', popup.styleSheet())

        # Qt may reuse QTipLabel while moving between controls. Exercise a
        # second source with conflicting local styling and reacquire the popup
        # because some platform plugins replace the private label instead.
        second_source = QPushButton('Group')
        second_palette = second_source.palette()
        second_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor('#000000'))
        second_palette.setColor(QPalette.ColorRole.ToolTipText, QColor('#ffffff'))
        second_source.setPalette(second_palette)
        second_source.setStyleSheet('QToolTip { background: #000000; color: #ffffff; }')
        second_source.show()
        QToolTip.showText(
            second_source.mapToGlobal(QPoint(2, 2)),
            'Layer 1',
            second_source,
        )
        APP.processEvents()
        popup = next(
            widget for widget in APP.topLevelWidgets()
            if widget.metaObject().className() == 'QTipLabel'
        )

        self.assertEqual(popup.palette().color(QPalette.ColorRole.Window).name(), '#fffdf7')
        self.assertEqual(popup.palette().color(QPalette.ColorRole.WindowText).name(), '#2f2f2f')
        self.assertIn('background-color: #fffdf7', popup.styleSheet())
        QToolTip.hideText()
        source.deleteLater()
        second_source.deleteLater()


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

    def test_workspace_row_menu_emits_management_requests(self):
        session = {
            "workspace_id": "workspace-1",
            "name": "North Core Batch",
            "date": "2026-04-09",
            "files": ["a.csv"],
        }
        widget = WelcomeWidget(recent_files=[], recent_sessions=[session])
        renamed = []
        removed = []
        pinned = []
        widget.rename_workspace_requested.connect(renamed.append)
        widget.remove_workspace_requested.connect(removed.append)
        widget.toggle_workspace_pin_requested.connect(pinned.append)

        menu_button = widget.findChild(QToolButton, "workspace-menu")
        self.assertIsNotNone(menu_button)
        self.assertIn("background-color: #fffdf7", menu_button.styleSheet())
        self.assertTrue(menu_button.menu().testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        self.assertIn("QMenu", menu_button.menu().styleSheet())
        actions = {action.text(): action for action in menu_button.menu().actions() if action.text()}
        actions["Rename..."].trigger()
        actions["Keep at top"].trigger()
        actions["Remove from list"].trigger()

        self.assertEqual(renamed[0]["workspace_id"], "workspace-1")
        self.assertEqual(pinned[0]["workspace_id"], "workspace-1")
        self.assertEqual(removed[0]["workspace_id"], "workspace-1")
        widget.deleteLater()

    def test_pinned_workspace_does_not_replace_latest_resume_target(self):
        sessions = [
            {
                "workspace_id": "kept-old",
                "name": "Kept old",
                "timestamp": "2026-04-01T08:00:00",
                "files": ["old.csv"],
                "pinned": True,
            },
            {
                "workspace_id": "recent-new",
                "name": "Recent new",
                "timestamp": "2026-04-09T08:00:00",
                "files": ["new.csv"],
            },
        ]
        widget = WelcomeWidget(recent_files=[], recent_sessions=sessions)
        opened = []
        widget.open_recent_session_requested.connect(opened.append)

        widget._resume_latest_session()

        self.assertEqual(opened[0]["workspace_id"], "recent-new")
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

    def test_expanded_sample_actions_wrap_into_two_rows(self):
        card = _SampleCard(
            "sample.csv",
            "Sample With Enough Words To Exercise The Sidebar Width",
            "loaded",
        )
        card.resize(220, 150)
        card.show()
        APP.processEvents()

        try:
            card._toggle_expand()
            card.resize(220, card.sizeHint().height())
            APP.processEvents()

            self.assertTrue(card._detail.isVisible())
            buttons = card._action_buttons
            self.assertEqual(
                set(buttons),
                {"Inspect", "Remap", "Log", "Props", "Remove"},
            )

            row_tops = {
                button.mapTo(card, button.rect().topLeft()).y()
                for button in buttons.values()
            }
            self.assertEqual(len(row_tops), 2)
            for button in buttons.values():
                right_edge = button.mapTo(card, button.rect().bottomRight()).x()
                self.assertLessEqual(right_edge, card.rect().right())
        finally:
            card.hide()
            card.deleteLater()
            APP.processEvents()


if __name__ == "__main__":
    unittest.main(verbosity=2)
