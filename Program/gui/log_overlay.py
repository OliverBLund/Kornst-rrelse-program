"""Reusable in-app activity log surface."""

from __future__ import annotations

from collections import deque
from datetime import datetime
import logging
import os
from typing import Any, Mapping

from PyQt6.QtCore import QObject, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.theme import C, F, icon


IMPORTANT_LEVELS = {"WARNING", "ERROR", "CRITICAL"}


def _normalize_level(level: object) -> str:
    text = str(level or "INFO").upper()
    if text == "WARN":
        return "WARNING"
    return text


def _event_matches_file(event: Mapping[str, Any], file_key: str | None) -> bool:
    if not file_key:
        return True
    context = event.get("context")
    if not isinstance(context, Mapping):
        context = {}
    candidates = {
        str(event.get("file_key") or ""),
        str(context.get("file_key") or ""),
        str(context.get("file_path") or ""),
    }
    return file_key in candidates


def _short_file_label(file_key: object) -> str:
    if not file_key:
        return ""
    text = str(file_key)
    if ":::" in text:
        file_path, sheet_name = text.split(":::", 1)
        return f"{os.path.basename(file_path)} [{sheet_name}]"
    return os.path.basename(text)


def _human_value(value: object) -> str:
    return str(value).replace("_", " ")


class InAppLogStore(QObject):
    """Small ring buffer for UI-visible application activity."""

    event_added = pyqtSignal(dict)
    events_changed = pyqtSignal()
    unread_changed = pyqtSignal(int)

    def __init__(self, parent: QObject | None = None, *, max_events: int = 300) -> None:
        super().__init__(parent)
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._unread_important = 0

    @property
    def unread_important_count(self) -> int:
        return self._unread_important

    def add_event(
        self,
        event: Mapping[str, Any] | None = None,
        *,
        level: object = "INFO",
        source: object = "app",
        message: object = "",
        context: Mapping[str, Any] | None = None,
        file_key: object = None,
    ) -> dict[str, Any] | None:
        payload = dict(event or {})
        payload.setdefault("level", level)
        payload.setdefault("source", source)
        payload.setdefault("message", message)
        if context is not None:
            payload["context"] = dict(context)
        payload["level"] = _normalize_level(payload.get("level"))
        payload["source"] = str(payload.get("source") or "app")
        payload["message"] = str(payload.get("message") or "").strip()
        if file_key is not None:
            payload["file_key"] = str(file_key)

        if not payload["message"]:
            return None

        if not isinstance(payload.get("context"), Mapping):
            payload["context"] = {}
        else:
            payload["context"] = dict(payload["context"])

        if "file_key" not in payload and payload["context"].get("file_key"):
            payload["file_key"] = str(payload["context"]["file_key"])
        payload.setdefault("time", datetime.now().strftime("%H:%M:%S"))

        self._events.append(payload)
        if payload["level"] in IMPORTANT_LEVELS:
            self._unread_important += 1
            self.unread_changed.emit(self._unread_important)
        self.event_added.emit(dict(payload))
        self.events_changed.emit()
        return payload

    def events(self, *, file_key: str | None = None) -> list[dict[str, Any]]:
        return [dict(event) for event in self._events if _event_matches_file(event, file_key)]

    def clear(self) -> None:
        self._events.clear()
        self._unread_important = 0
        self.unread_changed.emit(0)
        self.events_changed.emit()

    def mark_read(self) -> None:
        if self._unread_important:
            self._unread_important = 0
            self.unread_changed.emit(0)


class QtLogHandler(logging.Handler):
    """Forward Python logging records into an InAppLogStore."""

    def __init__(self, store: InAppLogStore) -> None:
        super().__init__(logging.WARNING)
        self.store = store

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.store.add_event(
                level=record.levelname,
                source=record.name,
                message=record.getMessage(),
                file_key=getattr(record, "file_key", None),
            )
        except Exception:
            pass


_INSTALLED_HANDLER: QtLogHandler | None = None


def install_in_app_logging(store: InAppLogStore, *, level: int = logging.WARNING) -> QtLogHandler:
    """Install one root logging handler for the active main window."""

    global _INSTALLED_HANDLER
    root_logger = logging.getLogger()
    if _INSTALLED_HANDLER is not None:
        try:
            root_logger.removeHandler(_INSTALLED_HANDLER)
        except Exception:
            pass
    handler = QtLogHandler(store)
    handler.setLevel(level)
    root_logger.addHandler(handler)
    _INSTALLED_HANDLER = handler
    return handler


def uninstall_in_app_logging(handler: QtLogHandler | None = None) -> None:
    global _INSTALLED_HANDLER
    target = handler or _INSTALLED_HANDLER
    if target is None:
        return
    try:
        logging.getLogger().removeHandler(target)
    except Exception:
        pass
    if _INSTALLED_HANDLER is target:
        _INSTALLED_HANDLER = None


def _level_color(level: str) -> str:
    if level in {"ERROR", "CRITICAL"}:
        return C.LED_ERR
    if level == "WARNING":
        return C.LED_WARN
    return C.K_BLUE


class _LogEventRow(QFrame):
    def __init__(self, event: Mapping[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("app-log-row")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        level = _normalize_level(event.get("level"))
        color = _level_color(level)
        self.setStyleSheet(
            "QFrame#app-log-row {"
            f"background: #FAF8F3; border: 1px solid {C.BORDER}; "
            f"border-left: 3px solid {color}; border-radius: 5px;"
            "}"
            "QLabel { background: transparent; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(9, 7, 9, 8)
        root.setSpacing(5)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)

        level_label = QLabel(level)
        level_label.setFont(QFont(F.MONO, F.SZ_XS, QFont.Weight.Bold))
        level_label.setStyleSheet(
            f"color: {color}; background: rgba(255,255,255,0.55); "
            f"border: 1px solid {color}; border-radius: 6px; padding: 1px 5px;"
        )
        top.addWidget(level_label)

        time_label = QLabel(str(event.get("time") or ""))
        time_label.setFont(QFont(F.MONO, F.SZ_XS))
        time_label.setStyleSheet(f"color: {C.TEXT_MUTED};")
        top.addWidget(time_label)

        source = str(event.get("source") or "app")
        source_label = QLabel(source)
        source_label.setFont(QFont(F.MONO, F.SZ_XS))
        source_label.setStyleSheet(f"color: {C.TEXT_MUTED};")
        top.addWidget(source_label)
        top.addStretch(1)
        root.addLayout(top)

        message_label = QLabel(str(event.get("message") or ""))
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        message_label.setFont(QFont(F.UI, F.SZ_BASE))
        message_label.setStyleSheet(f"color: {C.TEXT};")
        root.addWidget(message_label)

        detail = self._detail_text(event)
        if detail:
            detail_label = QLabel(detail)
            detail_label.setWordWrap(True)
            detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            detail_label.setFont(QFont(F.MONO, F.SZ_XS))
            detail_label.setStyleSheet(f"color: {C.TEXT_MUTED};")
            root.addWidget(detail_label)

    @staticmethod
    def _detail_text(event: Mapping[str, Any]) -> str:
        context = event.get("context")
        if not isinstance(context, Mapping):
            context = {}

        parts: list[str] = []
        file_label = _short_file_label(event.get("file_key") or context.get("file_key"))
        if file_label:
            parts.append(file_label)

        labels = [
            ("pathway", "Path"),
            ("data_type", "Loaded as"),
            ("intent", "Requested"),
            ("selection_method", "Mapping"),
        ]
        for key, label in labels:
            value = context.get(key)
            if value:
                parts.append(f"{label}: {_human_value(value)}")
        return " | ".join(parts)


class LogDropdownPanel(QFrame):
    """Floating dropdown for the application activity log."""

    closed = pyqtSignal()

    def __init__(self, store: InAppLogStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self._filter_file_key: str | None = None

        self.setObjectName("app-log-overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            "QFrame#app-log-overlay {"
            f"background: {C.BG_RAISED}; border: 1px solid {C.BORDER_DK}; "
            "border-radius: 6px;"
            "}"
            "QFrame#app-log-overlay QLabel { background: transparent; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 9, 10, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(7)

        self._title = QLabel("Activity Log")
        self._title.setFont(QFont(F.UI, F.SZ_LG, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {C.TEXT};")
        header.addWidget(self._title)

        self._summary = QLabel("")
        self._summary.setFont(QFont(F.MONO, F.SZ_XS))
        self._summary.setStyleSheet(f"color: {C.TEXT_MUTED};")
        header.addWidget(self._summary)
        header.addStretch(1)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self.store.clear)
        header.addWidget(self._clear_btn)

        self._close_btn = QPushButton()
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("Close activity log")
        try:
            self._close_btn.setIcon(icon("fa6s.xmark", C.TEXT_MUTED))
        except Exception:
            self._close_btn.setText("X")
        self._close_btn.clicked.connect(self.hide)
        header.addWidget(self._close_btn)
        root.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list_widget)
        root.addWidget(self._scroll, 1)

        self.hide()
        self.store.events_changed.connect(self.refresh)

    def set_filter_file_key(self, file_key: str | None) -> None:
        self._filter_file_key = file_key
        self.refresh()

    def refresh(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        events = self.store.events(file_key=self._filter_file_key)
        if self._filter_file_key:
            self._title.setText("File Log")
        else:
            self._title.setText("Activity Log")
        self._summary.setText(f"{len(events)} event{'s' if len(events) != 1 else ''}")

        if not events:
            empty = QLabel("No activity yet")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFont(QFont(F.UI, F.SZ_BASE))
            empty.setStyleSheet(f"color: {C.TEXT_MUTED}; padding: 28px;")
            self._list_layout.addWidget(empty)
        else:
            for event in reversed(events[-120:]):
                self._list_layout.addWidget(_LogEventRow(event))
        self._list_layout.addStretch(1)

    def show_near(self, anchor: QWidget, *, file_key: str | None = None) -> None:
        parent = self.parentWidget()
        if parent is None:
            return

        self.set_filter_file_key(file_key)
        width = max(300, min(520, parent.width() - 24))
        height = max(240, min(430, parent.height() - 84))
        self.setFixedSize(width, height)

        anchor_bottom = parent.mapFromGlobal(anchor.mapToGlobal(QPoint(anchor.width(), anchor.height())))
        x = anchor_bottom.x() - self.width()
        y = anchor_bottom.y() + 6
        x = max(8, min(x, parent.width() - self.width() - 8))
        y = max(8, min(y, parent.height() - self.height() - 8))
        self.move(x, y)
        self.show()
        self.raise_()
        self.store.mark_read()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.closed.emit()
