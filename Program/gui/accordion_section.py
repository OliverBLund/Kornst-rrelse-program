"""Shared collapsible section widget for dense sidebar controls."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import C, F, icon


class AccordionSection(QWidget):
    """Collapsible section with a themed icon, title, meta label, and chevron."""

    def __init__(self, fa_name: str, title: str, parent=None):
        super().__init__(parent)
        self._open = False
        self._fa_name = fa_name
        self.setObjectName("accSection")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._hdr = QWidget(self)
        self._hdr.setObjectName("accHdr")
        self._hdr.setFixedHeight(32)
        self._hdr.setCursor(Qt.CursorShape.PointingHandCursor)

        header_layout = QHBoxLayout(self._hdr)
        header_layout.setContentsMargins(10, 0, 10, 0)
        header_layout.setSpacing(8)

        self._icon_lbl = QLabel()
        self._icon_lbl.setObjectName("accIcon")
        self._icon_lbl.setFixedSize(18, 18)

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("accTitle")

        self._meta_lbl = QLabel("")
        self._meta_lbl.setObjectName("accMeta")
        self._meta_lbl.setMinimumHeight(18)
        self._meta_lbl.setMaximumWidth(145)
        self._meta_lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        self._chev_lbl = QLabel()
        self._chev_lbl.setObjectName("accChev")
        self._chev_lbl.setFixedSize(14, 14)

        header_layout.addWidget(self._icon_lbl)
        header_layout.addWidget(self._title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self._meta_lbl)
        header_layout.addWidget(self._chev_lbl)

        self._body = QWidget(self)
        self._body.setObjectName("accBody")
        self._body.setStyleSheet(f"QWidget#accBody {{ background: {C.BG}; }}")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
        self._body.setVisible(False)

        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.Shape.HLine)
        self._sep.setFixedHeight(1)
        self._sep.setStyleSheet(f"background:{C.BORDER}; color:{C.BORDER};")

        root.addWidget(self._hdr)
        root.addWidget(self._body)
        root.addWidget(self._sep)

        self._hdr.mousePressEvent = self._on_header_clicked  # type: ignore[assignment]
        self._apply_header_style()

    def body_layout(self) -> QVBoxLayout:
        return self._body_layout

    def set_open(self, value: bool) -> None:
        value = bool(value)
        if value == self._open:
            return
        self._open = value
        self._body.setVisible(value)
        self._meta_lbl.setVisible(not value and bool(self._meta_lbl.text()))
        self._apply_header_style()

    def is_open(self) -> bool:
        return self._open

    def set_meta(self, text: str) -> None:
        self._meta_lbl.setText(text)
        self._meta_lbl.setVisible(bool(text) and not self._open)

    def _on_header_clicked(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_open(not self._open)
            event.accept()

    def _apply_header_style(self) -> None:
        bg = C.BG_RAISED if self._open else C.BG_LOW
        icon_col = C.OLIVE_DK if self._open else C.TEXT_MUTED
        title_col = C.TEXT if self._open else C.TEXT_MID
        chev_name = "fa6s.chevron-down" if self._open else "fa6s.chevron-right"
        chev_col = C.OLIVE if self._open else C.TEXT_MUTED

        self._icon_lbl.setPixmap(icon(self._fa_name, icon_col, 14).pixmap(QSize(14, 14)))
        self._chev_lbl.setPixmap(icon(chev_name, chev_col, 10).pixmap(QSize(10, 10)))
        self._hdr.setStyleSheet(f"""
            QWidget#accHdr {{
                background: {bg};
            }}
            QWidget#accHdr:hover {{
                background: {C.BG_RAISED};
            }}
            QLabel#accIcon,
            QLabel#accChev {{
                background: transparent;
                border: none;
            }}
            QLabel#accTitle {{
                color: {title_col};
                font-family: "{F.UI}";
                font-size: {F.SZ_MD}pt;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#accMeta {{
                color: {C.TEXT_MUTED};
                background: {C.BG};
                border: 1px solid {C.BORDER};
                border-radius: 9px;
                padding: 1px 7px;
                font-family: "{F.MONO}";
                font-size: {F.SZ_XS}pt;
            }}
        """)
