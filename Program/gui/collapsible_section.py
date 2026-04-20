"""
Collapsible section widget with a colored icon tile, title, and chevron.

Drop-in container for sidebar sections that shrink to a single header row
when collapsed. Modeled on design_concepts/plot_settings.py._SettingsSection
but wired up with the project's theme.py tokens.

Usage:
    section = CollapsibleSection("Axis Controls", "fa6s.ruler",
                                  CollapsibleSection.BLUE)
    section.add_widget(axis_row)
    section.add_widget(other_row)
    parent_layout.addWidget(section)
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from .theme import C, F, icon


class CollapsibleSection(QWidget):
    """A compact, togglable group with icon + title header and a body."""

    # Icon color presets: (icon_color, background_tint)
    BLUE   = ("#3a7ea0", "rgba(58, 126, 160, 0.14)")
    OLIVE  = (C.OLIVE,   "rgba(107, 142, 35, 0.14)")
    AMBER  = ("#b46428", "rgba(180, 100, 40, 0.14)")
    PURPLE = ("#8b4580", "rgba(139, 69, 128, 0.14)")
    EARTH  = (C.EARTH,   "rgba(139, 115, 85, 0.16)")
    RED    = (C.DTU_RED, "rgba(200, 0, 42, 0.12)")

    def __init__(self, title: str, icon_name: str, color_preset: tuple,
                 expanded: bool = True, parent=None):
        super().__init__(parent)
        self._expanded = expanded
        self._icon_color, self._icon_bg = color_preset

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──
        self._header = QPushButton()
        self._header.setProperty("cs-header", True)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setFixedHeight(34)
        self._header.setStyleSheet(self._header_qss())

        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(10, 0, 10, 0)
        hl.setSpacing(8)

        self._icon_tile = QLabel()
        self._icon_tile.setFixedSize(22, 22)
        self._icon_tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_tile.setPixmap(
            icon(icon_name, self._icon_color, 12).pixmap(QSize(12, 12))
        )
        self._icon_tile.setStyleSheet(
            f"background-color: {self._icon_bg}; border-radius: 5px; border: none;"
        )
        hl.addWidget(self._icon_tile)

        self._title = QLabel(title)
        self._title.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_SM}pt; "
            f"font-weight: 600; background: transparent; border: none;"
        )
        hl.addWidget(self._title, 1)

        self._chevron = QLabel()
        self._chevron.setFixedSize(14, 14)
        self._chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chevron.setStyleSheet("background: transparent; border: none;")
        self._refresh_chevron()
        hl.addWidget(self._chevron)

        self._header.clicked.connect(self._toggle)
        root.addWidget(self._header)

        # ── Body ──
        self._body = QWidget()
        self._body.setProperty("cs-body", True)
        body_lay = QVBoxLayout(self._body)
        body_lay.setContentsMargins(0, 0, 0, 4)
        body_lay.setSpacing(0)
        self._body_layout = body_lay
        root.addWidget(self._body)

        self._body.setVisible(self._expanded)

    # ── Public API ─────────────────────────────────────────────

    def add_widget(self, widget: QWidget) -> None:
        """Append a widget (e.g. a pre-built row) to the body."""
        self._body_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._body_layout.addLayout(layout)

    def body_layout(self) -> QVBoxLayout:
        return self._body_layout

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self._body.setVisible(expanded)
        self._refresh_chevron()

    # ── Internals ──────────────────────────────────────────────

    def _toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def _refresh_chevron(self) -> None:
        name = "fa6s.chevron-down" if self._expanded else "fa6s.chevron-right"
        self._chevron.setPixmap(icon(name, C.TEXT_MUTED, 10).pixmap(QSize(10, 10)))

    @staticmethod
    def _header_qss() -> str:
        return (
            "QPushButton[cs-header=\"true\"] {"
            f"  background: #F1ECE3;"
            f"  border: none;"
            f"  border-bottom: 1px solid {C.BORDER};"
            f"  border-top: 1px solid rgba(212,196,168,0.35);"
            f"  text-align: left;"
            f"  padding: 0;"
            "}"
            "QPushButton[cs-header=\"true\"]:hover {"
            f"  background: #F6F2EA;"
            "}"
            "QPushButton[cs-header=\"true\"]:pressed {"
            f"  background: {C.BG_LOW};"
            "}"
        )
