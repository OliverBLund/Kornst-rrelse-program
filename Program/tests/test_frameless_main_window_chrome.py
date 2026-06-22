import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QWidget

from qt_chrome.window_helper import FramelessWindowChromeHelper


APP = QApplication.instance() or QApplication([])


class TestFramelessMainWindowChrome(unittest.TestCase):
    def setUp(self):
        self.window = QWidget()
        self.window.resize(640, 420)
        self.window._frameless_is_maximized = True
        self.window.show()
        APP.processEvents()
        self.helper = FramelessWindowChromeHelper(
            self.window,
            margin=8,
            top_margin=2,
            is_effectively_maximized=lambda: True,
        )

    def tearDown(self):
        self.helper._cleanup()
        self.window.hide()
        self.window.deleteLater()
        APP.processEvents()

    def test_maximized_bottom_edge_press_is_not_consumed_as_resize(self):
        pos = QPoint(self.window.width() // 2, self.window.height() - 1)
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(pos),
            QPointF(self.window.mapToGlobal(pos)),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        event.setAccepted(False)

        self.assertFalse(self.helper._handle_mouse_press(event))
        self.assertFalse(event.isAccepted())


if __name__ == "__main__":
    unittest.main(verbosity=2)
