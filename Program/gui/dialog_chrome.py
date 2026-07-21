"""
dialog_chrome.py
================
Shared factory functions for the standard dialog header and footer,
matching the pattern established in ClassificationDialog and the
design spec (design_concepts/04_dialogs.html).

Usage
-----
from gui.dialog_chrome import make_dialog_header, make_dialog_footer

# In a FramelessDialogBase subclass __init__:
root = QVBoxLayout(self)
root.setContentsMargins(0, 0, 0, 0)
root.setSpacing(0)

self._header_widget = make_dialog_header(
    "Sheet Selector", "Choose which sheets to import",
    fa_icon="fa6s.file-excel", close_fn=self.reject,
)
root.addWidget(self._header_widget)

# ... body widgets ...

root.addWidget(make_dialog_footer([
    ("Cancel",         self.reject, "secondary"),
    ("Import Sheets",  self.accept, "primary"),
]))

self.install_chrome_behavior(
    header_widget=self._header_widget, corner_radius=8, resize_margin=6,
)
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.theme import C, F, SZ, icon as _icon


def style_dialog_button(button: QPushButton, style: str = "secondary") -> None:
    """Apply the standard dialog action treatment to an existing button."""
    button.setFixedHeight(28)
    if style == "primary":
        button.setStyleSheet(
            f"QPushButton {{ background: {C.OLIVE}; border: 1px solid {C.OLIVE_DK}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; color: white; font-weight: 600; "
            f"padding: 0 14px; font-size: {F.SZ_LG}pt; }}"
            f"QPushButton:hover {{ background: {C.OLIVE_H}; }}"
            f"QPushButton:pressed {{ background: {C.OLIVE_DK}; border-color: {C.OLIVE_DK}; }}"
            f"QPushButton:disabled {{ background: {C.BORDER}; border-color: {C.BORDER_DK}; "
            f"color: {C.TEXT_MUTED}; }}"
        )
    elif style == "danger":
        button.setStyleSheet(
            f"QPushButton {{ border: 1px solid rgba(160,48,32,.35); "
            f"border-radius: {SZ.BORDER_RADIUS}px; color: #a03020; "
            f"background: transparent; padding: 0 14px; font-size: {F.SZ_LG}pt; }}"
            f"QPushButton:hover {{ background: rgba(160,48,32,.06); }}"
            f"QPushButton:pressed {{ background: rgba(160,48,32,.12); "
            f"border-color: rgba(160,48,32,.50); }}"
        )
    else:
        button.setStyleSheet(
            f"QPushButton {{ border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; background: {C.BG}; "
            f"color: {C.TEXT_MID}; padding: 0 14px; font-size: {F.SZ_LG}pt; }}"
            f"QPushButton:hover {{ background: {C.BG_RAISED}; "
            f"border-color: {C.BORDER_DK}; color: {C.TEXT}; }}"
            f"QPushButton:pressed {{ background: {C.BG_LOW}; "
            f"border-color: {C.EARTH}; color: {C.TEXT}; }}"
            f"QPushButton:disabled {{ background: {C.BG_LOW}; "
            f"border-color: {C.BORDER}; color: {C.TEXT_MUTED}; }}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────

def make_dialog_header(
    title: str,
    subtitle: str,
    fa_icon: str,
    close_fn: Callable,
    parent: Optional[QWidget] = None,
) -> QWidget:
    """Return a standard dialog header widget (matches .dh in 04_dialogs.html).

    Structure: [icon-badge] [title / subtitle] [close ✕]

    Parameters
    ----------
    title     : Primary title text (Playfair Display).
    subtitle  : Muted subtitle / description line (JetBrains Mono).
    fa_icon   : Font-Awesome 6 icon name, e.g. ``'fa6s.file-excel'``.
    close_fn  : Callable connected to the close button's clicked signal.
    parent    : Optional parent widget.
    """
    w = QWidget(parent)
    w.setObjectName("dialogHeader")
    w.setStyleSheet(
        f"QWidget#dialogHeader {{ background: {C.BG_RAISED}; "
        f"border-bottom: 1px solid {C.BORDER}; }}"
    )
    lay = QHBoxLayout(w)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(10)

    # Icon badge
    icon_box = QWidget()
    icon_box.setFixedSize(30, 30)
    icon_box.setStyleSheet(
        "background: rgba(107,142,35,.12); border: 1px solid rgba(107,142,35,.25); "
        f"border-radius: {SZ.BORDER_RADIUS}px;"
    )
    ib_lay = QHBoxLayout(icon_box)
    ib_lay.setContentsMargins(0, 0, 0, 0)
    ic = QLabel()
    try:
        ic.setPixmap(_icon(fa_icon, C.OLIVE).pixmap(13, 13))
    except Exception:
        ic.setText("⊞")
        ic.setStyleSheet(f"color: {C.OLIVE};")
    ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ic.setStyleSheet("background: transparent;")
    ib_lay.addWidget(ic)
    lay.addWidget(icon_box)

    # Title + subtitle column
    tx = QVBoxLayout()
    tx.setSpacing(1)
    title_lbl = QLabel(title)
    title_lbl.setFont(QFont(F.DISP, F.SZ_XL))
    title_lbl.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
    sub_lbl = QLabel(subtitle)
    sub_lbl.setFont(QFont(F.MONO, F.SZ_XS))
    sub_lbl.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
    tx.addWidget(title_lbl)
    tx.addWidget(sub_lbl)
    lay.addLayout(tx, 1)

    # Close button
    close_btn = QPushButton()
    close_btn.setFixedSize(26, 26)
    close_btn.setObjectName("dialogCloseBtn")
    try:
        close_btn.setIcon(_icon("fa6s.xmark", C.TEXT_MUTED))
    except Exception:
        close_btn.setText("✕")
    close_btn.setStyleSheet(
        "QPushButton#dialogCloseBtn { background: transparent; border: none; border-radius: 3px; }"
        "QPushButton#dialogCloseBtn:hover { background: rgba(180,48,32,.1); color: #a03020; }"
        "QPushButton#dialogCloseBtn:pressed { background: rgba(180,48,32,.18); color: #7f2418; }"
    )
    close_btn.setToolTip("Close")
    close_btn.clicked.connect(close_fn)
    lay.addWidget(close_btn)

    return w


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────

def make_dialog_footer(
    buttons: list[tuple[str, Callable, str]],
    left_widget: Optional[QWidget] = None,
    parent: Optional[QWidget] = None,
) -> QWidget:
    """Return a standard dialog footer widget (matches .df in 04_dialogs.html).

    Parameters
    ----------
    buttons     : List of ``(label, callback, style)`` tuples, left-to-right.
                  ``style`` is one of ``'primary'``, ``'secondary'``, ``'danger'``.
                  Primary gets the olive fill; secondary gets the neutral border;
                  danger gets the red-tinted border.
    left_widget : Optional widget placed on the far left (e.g. a status label).
    parent      : Optional parent widget.
    """
    w = QWidget(parent)
    w.setObjectName("dialogFooter")
    w.setStyleSheet(
        f"QWidget#dialogFooter {{ background: {C.BG_RAISED}; "
        f"border-top: 1px solid {C.BORDER}; }}"
    )
    lay = QHBoxLayout(w)
    lay.setContentsMargins(14, 8, 14, 8)
    lay.setSpacing(7)

    if left_widget is not None:
        lay.addWidget(left_widget)
    lay.addStretch(1)

    for label, callback, style in buttons:
        btn = QPushButton(label)
        style_dialog_button(btn, style)
        btn.clicked.connect(callback)
        lay.addWidget(btn)

    return w
