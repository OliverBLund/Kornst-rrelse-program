"""Frameless window edge resize + cursor behavior helper."""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, QTimer, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QWidget


class FramelessWindowChromeHelper(QObject):
    """Provides draggable/resizable edge behavior for frameless top-level windows."""

    def __init__(
        self,
        window: QWidget,
        margin: int = 12,
        top_margin: int = 5,
        is_effectively_maximized: Optional[Callable[[], bool]] = None,
    ):
        super().__init__(window)
        self.window = window
        self.margin = margin
        self.top_margin = top_margin
        self._is_effectively_maximized_cb = is_effectively_maximized
        self._resize_edges: set[str] = set()
        self._press_pos: Optional[QPoint] = None
        self._press_geom: Optional[QRect] = None
        self._cursor_shape: Optional[Qt.CursorShape] = None

        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(30)
        self._hover_timer.timeout.connect(self._refresh_cursor)
        self._hover_timer.start()

        app = QApplication.instance()
        self._installed_app = app
        if self._installed_app:
            self._installed_app.installEventFilter(self)
        window.destroyed.connect(self._cleanup)

    def _cleanup(self):
        """Remove the global event filter when the window closes."""
        if self._hover_timer.isActive():
            self._hover_timer.stop()
        if self._installed_app:
            self._installed_app.removeEventFilter(self)
            self._installed_app = None

    def _is_window_effectively_maximized(self) -> bool:
        if callable(self._is_effectively_maximized_cb):
            try:
                return bool(self._is_effectively_maximized_cb())
            except Exception:
                pass
        return bool(
            self.window.isMaximized()
            or getattr(self.window, "_frameless_is_maximized", False)
        )

    def eventFilter(self, watched, event):
        if not isinstance(watched, QWidget):
            return False
        if watched.window() is not self.window or not self.window.isVisible():
            return False

        etype = event.type()
        if etype == QEvent.Type.MouseButtonPress:
            return self._handle_mouse_press(event)
        if etype == QEvent.Type.MouseMove:
            if self._handle_mouse_move(event):
                return True
            self._update_cursor(event.globalPosition().toPoint())
            return False
        if etype == QEvent.Type.MouseButtonRelease:
            return self._handle_mouse_release(event)
        if etype in (QEvent.Type.Leave, QEvent.Type.WindowDeactivate):
            self._maybe_reset_cursor()
        return False

    def _handle_mouse_press(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.window.isMinimized():
            return False

        global_pos = event.globalPosition().toPoint()
        local_pos = self.window.mapFromGlobal(global_pos)
        edges = self._edges_at(local_pos)
        if not edges:
            return False

        # Prefer native system resize for smooth OS-integrated behavior.
        if self._start_system_resize(edges):
            event.accept()
            return True

        if self._is_window_effectively_maximized() or self.window.isFullScreen():
            self.window.showNormal()
            self._maybe_reset_cursor()
            event.accept()
            return True

        self._resize_edges = edges
        self._press_pos = global_pos
        self._press_geom = self.window.geometry()
        event.accept()
        return True

    def _handle_mouse_move(self, event):
        if not self._resize_edges:
            return False
        self._apply_resize(event.globalPosition().toPoint())
        event.accept()
        return True

    def _handle_mouse_release(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        if not self._resize_edges:
            return False
        self._resize_edges.clear()
        self._press_pos = None
        self._press_geom = None
        self._refresh_cursor()
        event.accept()
        return True

    def _apply_resize(self, global_pos: QPoint):
        if (
            not self._press_geom
            or not self._press_pos
            or self._is_window_effectively_maximized()
            or self.window.isFullScreen()
        ):
            return

        delta = global_pos - self._press_pos
        geom = QRect(self._press_geom)
        x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
        min_w = self.window.minimumWidth()
        min_h = self.window.minimumHeight()

        if "left" in self._resize_edges:
            new_x = x + delta.x()
            new_w = w - delta.x()
            if new_w < min_w:
                new_x = x + (w - min_w)
                new_w = min_w
            x, w = new_x, new_w
        elif "right" in self._resize_edges:
            w = max(min_w, w + delta.x())

        if "top" in self._resize_edges:
            new_y = y + delta.y()
            new_h = h - delta.y()
            if new_h < min_h:
                new_y = y + (h - min_h)
                new_h = min_h
            y, h = new_y, new_h
        elif "bottom" in self._resize_edges:
            h = max(min_h, h + delta.y())

        self.window.setGeometry(x, y, w, h)

    def _edges_at(self, pos: QPoint) -> set[str]:
        rect = self.window.rect()
        edges = set()
        if pos.x() <= self.margin:
            edges.add("left")
        elif pos.x() >= rect.width() - self.margin:
            edges.add("right")

        if pos.y() <= self.top_margin:
            edges.add("top")
        elif pos.y() >= rect.height() - self.margin:
            edges.add("bottom")
        return edges

    def _cursor_for_edges(self, edges: set[str]) -> Optional[Qt.CursorShape]:
        if not edges:
            return None
        if edges == {"left", "top"} or edges == {"right", "bottom"}:
            return Qt.CursorShape.SizeFDiagCursor
        if edges == {"left", "bottom"} or edges == {"right", "top"}:
            return Qt.CursorShape.SizeBDiagCursor
        if "left" in edges or "right" in edges:
            return Qt.CursorShape.SizeHorCursor
        if "top" in edges or "bottom" in edges:
            return Qt.CursorShape.SizeVerCursor
        return None

    def _update_cursor(self, global_pos: QPoint):
        if not self.window.isVisible() or self._is_window_effectively_maximized():
            self._maybe_reset_cursor()
            return

        if not self.window.geometry().contains(global_pos):
            self._maybe_reset_cursor()
            return

        local_pos = self.window.mapFromGlobal(global_pos)
        edges = self._edges_at(local_pos)
        cursor = self._cursor_for_edges(edges)
        if cursor is None:
            self._maybe_reset_cursor()
            return
        if self._cursor_shape != cursor:
            self.window.setCursor(cursor)
            self._cursor_shape = cursor

    def _refresh_cursor(self):
        """Apply cursor update using the current global pointer position."""
        self._update_cursor(QCursor.pos())

    def _maybe_reset_cursor(self):
        if self._cursor_shape is not None:
            self.window.unsetCursor()
            self._cursor_shape = None

    def _start_system_resize(self, edges: set[str]) -> bool:
        """Use native system resize when available (Qt >= 6.5)."""
        handle = self.window.windowHandle()
        if handle is None:
            return False
        flag = Qt.Edge(0)
        if "left" in edges:
            flag |= Qt.Edge.LeftEdge
        if "right" in edges:
            flag |= Qt.Edge.RightEdge
        if "top" in edges:
            flag |= Qt.Edge.TopEdge
        if "bottom" in edges:
            flag |= Qt.Edge.BottomEdge
        if flag == Qt.Edge(0):
            return False
        try:
            return bool(handle.startSystemResize(flag))
        except Exception:
            return False

