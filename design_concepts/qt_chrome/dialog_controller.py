"""Frameless dialog drag/resize controller."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PyQt6.QtWidgets import QApplication, QWidget


class FramelessDialogChromeController(QObject):
    """Handles drag/move/resize behavior for a frameless dialog window."""

    def __init__(self, dialog: QWidget, resize_margin: int = 6):
        super().__init__(dialog)
        self.dialog = dialog
        self._enabled = False
        self._resize_margin = max(2, int(resize_margin))

        self._header_widget: Optional[QWidget] = None
        self._drag_widgets: list[QWidget] = []
        self._chrome_event_targets: list[QWidget] = []

        self._cursor_shape = None
        self._resize_edges: set[str] = set()
        self._resize_press_pos: Optional[QPoint] = None
        self._resize_press_geom: Optional[QRect] = None
        self._drag_offset: Optional[QPoint] = None

        self._installed_app = None
        self._install_global_filter_on_show = False

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if not self._enabled:
            self.cleanup(detach_targets=True)
            self.dialog.clearMask()

    def configure(
        self,
        *,
        header_widget: Optional[QWidget],
        resize_widgets: Optional[list[QWidget]] = None,
        drag_widgets: Optional[list[QWidget]] = None,
        resize_margin: int = 6,
    ) -> None:
        self._header_widget = header_widget if isinstance(header_widget, QWidget) else None
        self._drag_widgets = [w for w in (drag_widgets or []) if isinstance(w, QWidget)]
        self._resize_margin = max(2, int(resize_margin))

        self._detach_target_filters()
        self._clear_drag_resize_state()

        if not self._enabled:
            return

        self._install_global_filter_on_show = True

        targets = [self.dialog]
        if isinstance(self._header_widget, QWidget):
            targets.append(self._header_widget)
        for widget in resize_widgets or []:
            if isinstance(widget, QWidget):
                targets.append(widget)
        targets.extend(self._drag_widgets)

        seen = set()
        unique_targets: list[QWidget] = []
        for widget in targets:
            marker = id(widget)
            if marker in seen:
                continue
            seen.add(marker)
            unique_targets.append(widget)

        self._chrome_event_targets = unique_targets
        for target in self._chrome_event_targets:
            target.setMouseTracking(True)
            target.installEventFilter(self)

    def on_show(self) -> None:
        if not self._enabled:
            return
        if self._install_global_filter_on_show and self._installed_app is None:
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)
                self._installed_app = app

    def cleanup(self, detach_targets: bool = False) -> None:
        if detach_targets:
            self._detach_target_filters()
            self._install_global_filter_on_show = False
        self._clear_drag_resize_state()
        self._reset_cursor()
        if self._installed_app is not None:
            try:
                self._installed_app.removeEventFilter(self)
            except Exception:
                pass
            self._installed_app = None

    def _detach_target_filters(self) -> None:
        for target in self._chrome_event_targets:
            try:
                target.removeEventFilter(self)
            except Exception:
                pass
        self._chrome_event_targets = []

    def _event_pos_in_dialog(self, watched, event) -> QPoint:
        if not hasattr(event, "position"):
            return QPoint()
        pos = event.position().toPoint()
        if watched is self.dialog:
            return pos
        if isinstance(watched, QWidget):
            return watched.mapTo(self.dialog, pos)
        return pos

    def _edges_at(self, pos: QPoint) -> set[str]:
        rect = self.dialog.rect()
        edges = set()
        if pos.x() <= self._resize_margin:
            edges.add("left")
        elif pos.x() >= rect.width() - self._resize_margin:
            edges.add("right")
        if pos.y() <= self._resize_margin:
            edges.add("top")
        elif pos.y() >= rect.height() - self._resize_margin:
            edges.add("bottom")
        return edges

    def _cursor_for_edges(self, edges: set[str]):
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

    def _update_resize_cursor(self, pos: QPoint):
        if self.dialog.isMaximized() or self.dialog.isFullScreen():
            self._reset_cursor()
            return
        edges = self._edges_at(pos)
        cursor = self._cursor_for_edges(edges)
        if cursor is None:
            self._reset_cursor()
            return
        if self._cursor_shape != cursor:
            self.dialog.setCursor(cursor)
            self._cursor_shape = cursor

    def _reset_cursor(self) -> None:
        if self._cursor_shape is not None:
            self.dialog.unsetCursor()
            self._cursor_shape = None

    def _is_drag_region(self, widget) -> bool:
        if widget is None:
            return False
        drag_roots = []
        if isinstance(self._header_widget, QWidget):
            drag_roots.append(self._header_widget)
        drag_roots.extend([w for w in self._drag_widgets if isinstance(w, QWidget)])
        if not drag_roots:
            return False

        in_drag_area = False
        for root in drag_roots:
            if widget is root or root.isAncestorOf(widget):
                in_drag_area = True
                break
        if not in_drag_area:
            return False

        while widget and widget is not self.dialog:
            if widget.inherits("QAbstractButton"):
                return False
            if widget.inherits("QLineEdit") or widget.inherits("QComboBox"):
                return False
            if widget.inherits("QSpinBox") or widget.inherits("QDoubleSpinBox"):
                return False
            if widget.inherits("QCheckBox"):
                return False
            for root in drag_roots:
                if widget is root:
                    return True
            widget = widget.parentWidget()
        return False

    def _start_system_move(self) -> bool:
        handle = self.dialog.windowHandle()
        if handle is None:
            return False
        try:
            return bool(handle.startSystemMove())
        except Exception:
            return False

    def _start_system_resize(self, edges: set[str]) -> bool:
        handle = self.dialog.windowHandle()
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

    def _apply_manual_resize(self, global_pos: QPoint):
        if not self._resize_edges or self._resize_press_pos is None or self._resize_press_geom is None:
            return
        delta = global_pos - self._resize_press_pos
        geom = QRect(self._resize_press_geom)
        x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
        min_w = max(200, self.dialog.minimumWidth())
        min_h = max(140, self.dialog.minimumHeight())

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

        self.dialog.setGeometry(x, y, w, h)

    def _clear_drag_resize_state(self):
        self._resize_edges = set()
        self._resize_press_pos = None
        self._resize_press_geom = None
        self._drag_offset = None

    def eventFilter(self, watched, event):
        try:
            if not self._enabled:
                return False
            if not isinstance(watched, QWidget):
                return False
            host_window = watched.window()
            if host_window is not self.dialog:
                return False
        except RuntimeError:
            # QWidget may be deleted while the app-level event filter is still active.
            return False
        except Exception:
            return False

        etype = event.type()
        if etype == QEvent.Type.MouseButtonPress and hasattr(event, "button"):
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            local_pos = self._event_pos_in_dialog(watched, event)
            global_pos = (
                event.globalPosition().toPoint()
                if hasattr(event, "globalPosition")
                else QPoint()
            )

            if not self.dialog.isMaximized() and not self.dialog.isFullScreen():
                edges = self._edges_at(local_pos)
                if edges:
                    if self._start_system_resize(edges):
                        event.accept()
                        return True
                    self._resize_edges = edges
                    self._resize_press_pos = global_pos
                    self._resize_press_geom = self.dialog.geometry()
                    event.accept()
                    return True

            child = self.dialog.childAt(local_pos)
            if self._is_drag_region(child):
                if self._start_system_move():
                    event.accept()
                    return True
                self._drag_offset = global_pos - self.dialog.frameGeometry().topLeft()
                event.accept()
                return True

            return False

        if etype == QEvent.Type.MouseMove:
            local_pos = self._event_pos_in_dialog(watched, event)
            global_pos = (
                event.globalPosition().toPoint()
                if hasattr(event, "globalPosition")
                else QPoint()
            )
            left_pressed = bool(
                hasattr(event, "buttons")
                and (event.buttons() & Qt.MouseButton.LeftButton)
            )

            if self._resize_edges:
                if left_pressed:
                    self._apply_manual_resize(global_pos)
                    event.accept()
                    return True
                self._resize_edges = set()

            if self._drag_offset is not None:
                if left_pressed:
                    self.dialog.move(global_pos - self._drag_offset)
                    event.accept()
                    return True
                self._drag_offset = None

            self._update_resize_cursor(local_pos)
            return False

        if etype == QEvent.Type.MouseButtonRelease and hasattr(event, "button"):
            if event.button() == Qt.MouseButton.LeftButton:
                was_active = bool(self._resize_edges or self._drag_offset is not None)
                self._clear_drag_resize_state()
                self._update_resize_cursor(self._event_pos_in_dialog(watched, event))
                if was_active:
                    event.accept()
                    return True
            return False

        if etype in (QEvent.Type.Leave, QEvent.Type.WindowDeactivate):
            if self._cursor_shape is not None and not self._resize_edges:
                self.dialog.unsetCursor()
                self._cursor_shape = None

        return False
