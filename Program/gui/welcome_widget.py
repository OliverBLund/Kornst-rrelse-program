"""
Welcome Widget — styled to match design_concepts/05_welcome.html.

Background: soil_layers.png scaled to fill (KeepAspectRatioByExpanding),
with rgba(255,255,255,0.38) overlay. Scroll content is fully transparent
so the painted background shows through at every screen size.
"""

import os
import sys
from pathlib import Path
from typing import List

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QLinearGradient, QPainter, QPaintEvent, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import C, F, icon

# Max width of the centred cards (px)
_CARD_W = 712


class WelcomeWidget(QWidget):
    """Welcome screen shown in the first dataset tab."""

    load_files_requested       = pyqtSignal()
    load_sample_data_requested = pyqtSignal()
    open_recent_file_requested = pyqtSignal(str)
    open_recent_session_requested = pyqtSignal(dict)
    open_help_topic_requested  = pyqtSignal(str)
    dont_show_again_changed    = pyqtSignal(bool)
    clear_sessions_requested   = pyqtSignal()

    def __init__(self, recent_files: List[str] = None, recent_sessions: List[dict] = None, parent=None):
        super().__init__(parent)
        self.recent_files = recent_files or []
        self.recent_sessions = recent_sessions or []
        self.setAutoFillBackground(False)
        self._bg_pixmap = self._load_bg_pixmap()
        self._title_card = None
        self._main_card = None
        self._footer = None
        self._footer_attr = None
        self._resume_btn = None
        self._resume_hint = None
        self._setup_ui()

    @staticmethod
    def _load_bg_pixmap() -> QPixmap:
        if getattr(sys, "frozen", False):
            img = Path(sys._MEIPASS) / "Program" / "resources" / "soil_layers.png"  # type: ignore[attr-defined]
        else:
            img = Path(__file__).resolve().parent.parent / "resources" / "soil_layers.png"
        if img.exists():
            px = QPixmap(str(img))
            if not px.isNull():
                return px
        return QPixmap()

    # ── Background painting ──────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_card_widths()
        self.update()   # repaint soil image whenever widget resizes

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        w, h = self.width(), self.height()

        if not self._bg_pixmap.isNull():
            # Stretch to fill — slight distortion is invisible under the overlay
            painter.drawPixmap(self.rect(), self._bg_pixmap)
        else:
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0.00, QColor("#b5a080"))
            grad.setColorAt(0.45, QColor("#a0826d"))
            grad.setColorAt(1.00, QColor("#6a94a8"))
            painter.fillRect(self.rect(), grad)

        # rgba(255,255,255,0.38) white overlay
        painter.fillRect(self.rect(), QColor(255, 255, 255, 97))
        painter.end()

    # ── UI Setup ─────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAutoFillBackground(False)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        # Use custom no-paint widgets for viewport and content so the global
        # QSS "QWidget { background-color: C.BG }" cannot paint over our soil image.
        scroll.setViewport(_ClearWidget())

        content = _ClearWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 26, 24, 18)
        lay.setSpacing(16)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._title_card = self._build_title_card()
        self._main_card = self._build_main_card()
        self._footer = self._build_footer()

        lay.addWidget(self._title_card, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._main_card,  0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._footer,     0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self._sync_card_widths()

    # ── Title card ───────────────────────────────────────────────

    def _build_title_card(self) -> QFrame:
        return self._build_title_card_concept_v2()

    def _build_title_card_concept(self) -> QFrame:
        card = QFrame()
        card.setObjectName("wlc-title")
        card.setStyleSheet("""
            QFrame#wlc-title {
                background: rgba(255,255,255,56);
                border: 1px solid rgba(255,255,255,97);
                border-radius: 8px;
            }
        """)
        card.setMaximumWidth(_CARD_W)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(22, 13, 22, 11)
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # ── Logo mark ──────────────────────────────────────────────
        mark = QFrame()
        mark.setObjectName("wlc-mark")
        mark.setFixedSize(42, 42)
        mark.setStyleSheet("""
            QFrame#wlc-mark {
                background: rgba(107,142,35,180);
                border: 1.5px solid rgba(107,142,35,220);
                border-radius: 10px;
            }
        """)
        m_lay = QHBoxLayout(mark)
        m_lay.setContentsMargins(0, 0, 0, 0)
        m_ico = QLabel()
        m_ico.setPixmap(icon("fa6s.layer-group", "#ffffff").pixmap(QSize(18, 18)))
        m_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        m_ico.setStyleSheet("background: transparent; border: none;")
        m_lay.addWidget(m_ico, 0, Qt.AlignmentFlag.AlignCenter)

        mark_wrap = QWidget()
        mark_wrap.setStyleSheet("background: transparent; border: none;")
        mw_lay = QHBoxLayout(mark_wrap)
        mw_lay.setContentsMargins(0, 0, 0, 0)
        mw_lay.addStretch()
        mw_lay.addWidget(mark)
        mw_lay.addStretch()
        lay.addWidget(mark_wrap)
        lay.addSpacing(12)

        # ── Title ──────────────────────────────────────────────────
        title = QLabel("Grain Size Analysis")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f'color: {C.TEXT}; font-family: "{F.DISP}"; font-size: {F.SZ_2XL}pt;'
            ' font-weight: 700; letter-spacing: 0.02em; background: transparent;'
        )
        lay.addWidget(title)
        lay.addSpacing(4)

        sub = QLabel("Hydraulic Conductivity Calculator")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_LG}pt; font-weight: 600;"
            " background: transparent;"
        )
        lay.addWidget(sub)
        lay.addSpacing(14)

        # ── Divider ────────────────────────────────────────────────
        div = QFrame()
        div.setObjectName("wlc-div")
        div.setFixedHeight(1)
        div.setStyleSheet("QFrame#wlc-div { background: rgba(139,115,85,50); border: none; }")
        lay.addWidget(div)
        lay.addSpacing(12)

        # ── Feature chips ──────────────────────────────────────────
        chips_w = QWidget()
        chips_w.setStyleSheet("background: transparent; border: none;")
        chips_lay = QHBoxLayout(chips_w)
        chips_lay.setContentsMargins(0, 0, 0, 0)
        chips_lay.setSpacing(8)
        chips_lay.addStretch()

        for chip_ico, chip_txt in [
            ("fa6s.vial",        "16 K-Methods"),
            ("fa6s.chart-line",  "D-values & Gradation"),
            ("fa6s.file-export", "Batch Export"),
        ]:
            chip = QWidget()
            chip.setObjectName("wlc-chip")
            chip.setStyleSheet("""
                QWidget#wlc-chip {
                    background: rgba(107,142,35,55);
                    border: 1px solid rgba(107,142,35,130);
                    border-radius: 99px;
                }
            """)
            c_lay = QHBoxLayout(chip)
            c_lay.setContentsMargins(9, 4, 9, 4)
            c_lay.setSpacing(5)

            c_ico = QLabel()
            c_ico.setPixmap(icon(chip_ico, C.OLIVE).pixmap(QSize(10, 10)))
            c_ico.setStyleSheet("background: transparent; border: none;")

            c_txt = QLabel(chip_txt)
            c_txt.setStyleSheet(
                f"color: {C.OLIVE_DK}; font-size: {F.SZ_XS}pt; font-weight: 700;"
                " background: transparent; border: none;"
            )
            c_lay.addWidget(c_ico)
            c_lay.addWidget(c_txt)
            chips_lay.addWidget(chip)

        chips_lay.addStretch()
        lay.addWidget(chips_w)
        lay.addSpacing(10)

        # ── Version ────────────────────────────────────────────────
        ver = QLabel("v0.9.0-beta")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(
            f"color: {C.TEXT_MID}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: transparent;"
        )
        lay.addWidget(ver)
        return card

    # ── Main card ────────────────────────────────────────────────

    def _build_title_card_concept_v2(self) -> QFrame:
        card = QFrame()
        card.setObjectName("wlc-title-concept")
        card.setStyleSheet("""
            QFrame#wlc-title-concept {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(252,250,245,196),
                    stop:1 rgba(247,242,233,176)
                );
                border: 1px solid rgba(255,255,255,132);
                border-radius: 12px;
            }
        """)
        card.setMaximumWidth(_CARD_W)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 18, 24, 16)
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignmentFlag.AlignLeft)

        meta_row = QWidget()
        meta_row.setStyleSheet("background: transparent; border: none;")
        meta_lay = QHBoxLayout(meta_row)
        meta_lay.setContentsMargins(0, 0, 0, 0)
        meta_lay.setSpacing(8)

        eyebrow = QLabel("BATCH WORKSPACE")
        eyebrow.setStyleSheet(
            f"color: {C.OLIVE_DK}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " font-weight: 700; letter-spacing: 0.16em; background: transparent; border: none;"
        )
        meta_lay.addWidget(eyebrow)
        meta_lay.addStretch()

        ver = QLabel("v0.9.0-beta")
        ver.setStyleSheet(
            f"color: {C.TEXT_MID}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: rgba(255,255,255,122); border: 1px solid rgba(120,95,60,36);"
            " border-radius: 99px; padding: 2px 8px;"
        )
        meta_lay.addWidget(ver)
        lay.addWidget(meta_row)
        lay.addSpacing(9)

        title = QLabel("Grain Size Analysis")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title.setStyleSheet(
            f'color: {C.TEXT}; font-family: "{F.DISP}"; font-size: 23pt;'
            ' font-weight: 700; letter-spacing: 0.01em; background: transparent; border: none;'
        )
        lay.addWidget(title)
        lay.addSpacing(2)

        sub = QLabel("Hydraulic Conductivity Calculator")
        sub.setAlignment(Qt.AlignmentFlag.AlignLeft)
        sub.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_MD}pt; font-weight: 600;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sub)
        lay.addSpacing(10)

        desc = QLabel(
            "Load batches, return to recent workspaces, compare selected datasets, and export the chosen scope."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt; line-height: 1.35;"
            " background: transparent; border: none;"
        )
        lay.addWidget(desc)
        lay.addSpacing(12)

        attr = QLabel("Batch import  ·  session restore  ·  selected-scope export")
        attr.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: transparent; border: none;"
        )
        lay.addWidget(attr)
        lay.addSpacing(10)

        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background: rgba(107,142,35,72); border: none;")
        lay.addWidget(rule)
        return card

    def _build_main_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("wlc-card")
        card.setStyleSheet("""
            QFrame#wlc-card {
                background: rgba(249,246,240,245);
                border: 1px solid rgba(180,160,130,86);
                border-radius: 12px;
            }
        """)
        card.setMaximumWidth(_CARD_W)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        grid = QGridLayout(card)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        grid.addWidget(
            self._build_section("fa6s.bolt", "Quick Actions",
                                self._build_actions(),
                                accent=C.OLIVE), 0, 0, 1, 2
        )
        grid.addWidget(
            self._build_section("fa6s.clock-rotate-left", "Recent Sessions",
                                self._build_recent(), clear_btn=True,
                                accent=C.EARTH), 1, 0
        )
        grid.addWidget(
            self._build_section("fa6s.seedling", "What's New",
                                self._build_whats_new(),
                                accent=C.OLIVE), 1, 1
        )
        grid.addWidget(
            self._build_section("fa6s.book-open", "Guides",
                                self._build_help(),
                                accent=C.AMBER), 2, 0, 1, 2
        )
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        return card

    # ── Section box ──────────────────────────────────────────────

    def _build_section(self, icon_name: str, title: str, content: QWidget,
                       clear_btn: bool = False, accent: str = None) -> QFrame:
        return self._build_section_concept_v3(
            icon_name=icon_name,
            title=title,
            content=content,
            clear_btn=clear_btn,
            accent=accent,
        )

    def _build_section_concept_v2(self, icon_name: str, title: str, content: QWidget,
                                  clear_btn: bool = False, accent: str = None) -> QFrame:
        _accent = accent or C.BORDER
        sec = QFrame()
        sec.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sec.setStyleSheet(f"""
            QFrame {{
                background: #f9f7f3;
                border: 1px solid {C.BORDER};
                border-top: 3px solid {_accent};
                border-radius: 6px;
            }}
        """)

        lay = QVBoxLayout(sec)
        lay.setContentsMargins(0, 0, 0, 10)
        lay.setSpacing(8)

        # ── Header band ────────────────────────────────────────────
        hdr_band = QWidget()
        hdr_band.setStyleSheet(
            f"background: rgba(180,160,130,14); border: none; border-radius: 0px;"
        )
        hdr_band_lay = QHBoxLayout(hdr_band)
        hdr_band_lay.setContentsMargins(10, 8, 10, 8)
        hdr_band_lay.setSpacing(8)

        # Coloured icon pill
        ico_pill = QFrame()
        ico_pill.setFixedSize(22, 22)
        ico_pill.setStyleSheet(f"""
            QFrame {{
                background: {_accent};
                border-radius: 5px;
                border: none;
            }}
        """)
        ico_pill_lay = QHBoxLayout(ico_pill)
        ico_pill_lay.setContentsMargins(0, 0, 0, 0)
        ico_lbl = QLabel()
        ico_lbl.setPixmap(icon(icon_name, "#ffffff").pixmap(QSize(11, 11)))
        ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico_lbl.setStyleSheet("background: transparent; border: none;")
        ico_pill_lay.addWidget(ico_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        ttl_lbl = QLabel(title)
        ttl_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_LG}pt; font-weight: 700;"
            f" letter-spacing: 0.02em; background: transparent; border: none;"
        )

        hdr_band_lay.addWidget(ico_pill)
        hdr_band_lay.addWidget(ttl_lbl)
        hdr_band_lay.addStretch()

        if clear_btn:
            clr = QPushButton("Clear")
            clr.setIcon(icon("fa6s.trash-can", C.EARTH))
            clr.setFixedHeight(22)
            clr.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            clr.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(139,115,85,28);
                    color: {C.EARTH};
                    border: 1px solid rgba(139,115,85,90);
                    border-radius: 3px;
                    padding: 0 8px;
                    font-size: 9pt;
                }}
                QPushButton:hover {{
                    background: rgba(139,115,85,55);
                    color: {C.TEXT_MID};
                }}
            """)
            clr.clicked.connect(self.clear_sessions_requested.emit)
            hdr_band_lay.addWidget(clr)

        lay.addWidget(hdr_band)

        # Content with side padding
        content_wrap = QWidget()
        content_wrap.setStyleSheet("background: transparent; border: none;")
        cw_lay = QVBoxLayout(content_wrap)
        cw_lay.setContentsMargins(10, 0, 10, 0)
        cw_lay.setSpacing(0)
        cw_lay.addWidget(content, 1)

        lay.addWidget(content_wrap, 1)
        return sec

    # ── Recent Sessions ──────────────────────────────────────────

    def _build_section_concept_v3(self, icon_name: str, title: str, content: QWidget,
                                  clear_btn: bool = False, accent: str = None) -> QFrame:
        _accent = accent or C.BORDER
        sec = QFrame()
        sec.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sec.setStyleSheet(f"""
            QFrame {{
                background: rgba(255,255,255,126);
                border: 1px solid rgba(210,196,172,0.92);
                border-radius: 10px;
            }}
        """)

        lay = QVBoxLayout(sec)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(9)

        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(8)

        ico_tile = QFrame()
        ico_tile.setFixedSize(24, 24)
        ico_tile.setStyleSheet(
            "background: rgba(255,255,255,148); border: 1px solid rgba(0,0,0,0); border-radius: 7px;"
        )
        ico_tile_lay = QHBoxLayout(ico_tile)
        ico_tile_lay.setContentsMargins(0, 0, 0, 0)

        ico_lbl = QLabel()
        ico_lbl.setPixmap(icon(icon_name, _accent).pixmap(QSize(12, 12)))
        ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico_lbl.setStyleSheet("background: transparent; border: none;")
        ico_tile_lay.addWidget(ico_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        ttl_lbl = QLabel(title)
        ttl_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_MD}pt; font-weight: 700;"
            " background: transparent; border: none;"
        )

        header_lay.addWidget(ico_tile)
        header_lay.addWidget(ttl_lbl)
        header_lay.addStretch()

        if clear_btn:
            clr = QPushButton("Clear")
            clr.setIcon(icon("fa6s.trash-can", C.EARTH))
            clr.setFixedHeight(22)
            clr.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            clr.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(139,115,85,22);
                    color: {C.EARTH};
                    border: 1px solid rgba(139,115,85,84);
                    border-radius: 99px;
                    padding: 0 8px;
                    font-size: {F.SZ_XS}pt;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: rgba(139,115,85,40);
                    color: {C.TEXT};
                }}
            """)
            clr.clicked.connect(self.clear_sessions_requested.emit)
            header_lay.addWidget(clr)

        lay.addWidget(header)
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: rgba(212,196,168,0.65); border: none;")
        lay.addWidget(divider)
        lay.addWidget(content, 0, Qt.AlignmentFlag.AlignTop)
        lay.addStretch(1)
        return sec

    def _build_recent(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        if self.recent_sessions:
            for index, s in enumerate(self.recent_sessions[:4]):
                lay.addWidget(self._build_session_row(s, is_latest=index == 0))
        else:
            empty = QLabel("No saved sessions yet")
            empty.setStyleSheet(
                f"color: {C.TEXT_MUTED}; font-size: {F.SZ_BASE}pt;"
                " background: transparent; border: none; padding: 14px 6px;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(empty)

            hint = QLabel("Load a batch once and it will appear here for quick return.")
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(
                f"color: {C.TEXT_MUTED}; font-size: {F.SZ_XS}pt;"
                " background: transparent; border: none; padding: 0 16px 8px 16px;"
            )
            lay.addWidget(hint)

        return w

    def _build_session_row(self, s: dict, is_latest: bool = False) -> QFrame:
        """One recent-session entry with stronger hierarchy and hover feedback."""
        files = s.get("files", [])
        date  = s.get("date", "")
        name  = s.get("name", "Unnamed Session")
        n     = len(files)

        row = _HoverFrame()
        row.setObjectName("rec-row")
        row.setStyleSheet(f"""
            QFrame#rec-row {{
                background: rgba(255,255,255,186);
                border: 1px solid rgba(212,196,168,0.82);
                border-left: 3px solid {C.EARTH};
                border-radius: 8px;
            }}
            QFrame#rec-row[hovered="true"] {{
                background: rgba(255,255,255,232);
                border-color: rgba(160,138,108,0.92);
            }}
        """)
        row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        row.setProperty("hovered", False)

        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(12, 10, 12, 10)
        row_lay.setSpacing(10)

        ico_tile = QFrame()
        ico_tile.setFixedSize(28, 28)
        ico_tile.setStyleSheet(
            f"background: rgba(139,115,85,20); border: 1px solid rgba(139,115,85,50); border-radius: 8px;"
        )
        ico_lay = QHBoxLayout(ico_tile)
        ico_lay.setContentsMargins(0, 0, 0, 0)

        ico = QLabel()
        ico.setPixmap(icon("fa6s.folder-open", C.EARTH).pixmap(QSize(14, 14)))
        ico.setStyleSheet("background: transparent; border: none;")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico_lay.addWidget(ico, 0, Qt.AlignmentFlag.AlignCenter)

        tx = QWidget()
        tx.setStyleSheet("background: transparent; border: none;")
        tx_lay = QVBoxLayout(tx)
        tx_lay.setContentsMargins(0, 0, 0, 0)
        tx_lay.setSpacing(3)

        title_row = QWidget()
        title_row.setStyleSheet("background: transparent; border: none;")
        tr_lay = QHBoxLayout(title_row)
        tr_lay.setContentsMargins(0, 0, 0, 0)
        tr_lay.setSpacing(6)

        nm_lbl = QLabel(name)
        nm_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_BASE}pt; font-weight: 700;"
            " background: transparent; border: none;"
        )
        tr_lay.addWidget(nm_lbl)

        if is_latest:
            latest = QLabel("Latest")
            latest.setStyleSheet(
                f"color: {C.OLIVE_DK}; background: rgba(107,142,35,20);"
                " border: 1px solid rgba(107,142,35,70); border-radius: 99px;"
                f" padding: 1px 6px; font-family: '{F.MONO}'; font-size: {F.SZ_XS - 1}pt; font-weight: 700;"
            )
            tr_lay.addWidget(latest)
        tr_lay.addStretch()

        meta_parts = [f"{n} dataset{'s' if n != 1 else ''}"]
        if date:
            meta_parts.append(date)
        meta_lbl = QLabel("  ·  ".join(meta_parts))
        meta_lbl.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: transparent; border: none;"
        )

        tx_lay.addWidget(title_row)
        tx_lay.addWidget(meta_lbl)

        chev = QLabel()
        chev.setPixmap(icon("fa6s.chevron-right", C.TEXT_MUTED).pixmap(QSize(9, 9)))
        chev.setStyleSheet("background: transparent; border: none;")
        chev.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        row_lay.addWidget(ico_tile)
        row_lay.addWidget(tx, 1)
        row_lay.addWidget(chev)

        row.clicked.connect(lambda session=dict(s): self.open_recent_session_requested.emit(session))
        return row

    # ── What's New ───────────────────────────────────────────────

    def _build_whats_new(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(176)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 5px; }}
            QScrollBar::handle:vertical {{ background: {C.BORDER}; border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        sc = QWidget()
        sc.setStyleSheet("background: transparent;")
        sc_lay = QVBoxLayout(sc)
        sc_lay.setContentsMargins(0, 0, 3, 0)
        sc_lay.setSpacing(9)

        for index, v in enumerate([
            {"version": "v0.9.0-beta",  "date": "2025-01-15", "changes": [
                "New batch export flow with scope selection",
                "Wide format CSV export for statistical analysis",
                "Enhanced welcome screen with recent sessions",
            ]},
            {"version": "v0.8.0-alpha", "date": "2024-12-20", "changes": [
                "Added comparison tab for multiple datasets",
                "Improved calculation methods validation",
                "Bug fixes for column mapping",
            ]},
            {"version": "v0.7.0-alpha", "date": "2024-11-30", "changes": [
                "New help system with comprehensive guides",
                "Enhanced reporting tab with templates",
                "Performance improvements for large datasets",
            ]},
            {"version": "v0.6.0-alpha", "date": "2024-11-10", "changes": [
                "Added statistics tab with grain analysis",
                "Improved porosity calculation methods",
                "New plot customization options",
            ]},
        ]):
            blk = QFrame()
            blk.setStyleSheet(
                "background: transparent; border: none;"
                if index else
                f"background: rgba(107,142,35,14); border: 1px solid rgba(107,142,35,45); border-radius: 8px;"
            )
            blk_lay = QVBoxLayout(blk)
            blk_lay.setContentsMargins(8 if index == 0 else 0, 8 if index == 0 else 0, 8 if index == 0 else 0, 8 if index == 0 else 0)
            blk_lay.setSpacing(2)

            hdr_row = QWidget()
            hdr_row.setStyleSheet("background: transparent; border: none;")
            hr_lay = QHBoxLayout(hdr_row)
            hr_lay.setContentsMargins(0, 0, 0, 0)
            hr_lay.setSpacing(5)

            ver_pill = QLabel(v["version"])
            ver_pill.setStyleSheet(
                f"color: white; background: {C.OLIVE}; font-size: {F.SZ_XS}pt;"
                f" font-weight: 700; padding: 1px 7px; border-radius: 99px; border: none;"
            )
            date_lbl = QLabel(v["date"])
            date_lbl.setStyleSheet(
                f"color: {C.TEXT_MUTED}; font-size: {F.SZ_XS}pt;"
                " background: transparent; border: none;"
            )

            hr_lay.addWidget(ver_pill)
            hr_lay.addWidget(date_lbl)
            hr_lay.addStretch()
            blk_lay.addWidget(hdr_row)

            for ch in v["changes"]:
                ch_lbl = QLabel(f"• {ch}")
                ch_lbl.setStyleSheet(
                    f"color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt; padding-left: 10px;"
                    " background: transparent; border: none;"
                )
                ch_lbl.setWordWrap(True)
                blk_lay.addWidget(ch_lbl)

            sc_lay.addWidget(blk)

        sc_lay.addStretch()
        scroll.setWidget(sc)
        lay.addWidget(scroll, 1)

        btn = QPushButton("View Full Changelog")
        btn.setIcon(icon("fa6s.book-open", C.OLIVE))
        btn.setFixedHeight(28)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,122);
                border: 1px solid rgba(107,142,35,87);
                border-radius: 99px;
                color: {C.OLIVE};
                font-size: {F.SZ_SM}pt;
                padding: 4px 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: rgba(107,142,35,20); }}
        """)
        btn.clicked.connect(self._open_full_changelog)
        lay.addWidget(btn)
        return w

    # ── Quick Help ───────────────────────────────────────────────

    def _build_help(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        grid = QGridLayout(w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(5)

        for (name, file, ico_name), (r, c) in zip(
            [
                ("Getting Started", "getting_started.html",  "fa6s.circle-play"),
                ("File Formats",    "file_formats.html",     "fa6s.file-csv"),
                ("Methods",         "methods_overview.html", "fa6s.flask"),
                ("Troubleshoot",    "troubleshooting.html",  "fa6s.screwdriver-wrench"),
            ],
            [(0, 0), (0, 1), (1, 0), (1, 1)],
        ):
            btn = QPushButton(name)
            btn.setIcon(icon(ico_name, C.AMBER))
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(30)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,114);
                    border: 1px solid rgba(196,165,116,100);
                    border-radius: 8px;
                    color: {C.TEXT_MID};
                    font-size: {F.SZ_SM}pt;
                    font-weight: 500;
                    padding: 6px 8px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: rgba(196,165,116,24);
                    border-color: rgba(196,165,116,160);
                    color: {C.TEXT};
                }}
            """)
            btn.clicked.connect(lambda ch, f=file: self.open_help_topic_requested.emit(f))
            grid.addWidget(btn, r, c)

        return w

    # ── Quick Actions ────────────────────────────────────────────

    def _build_actions(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QGridLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(8)
        lay.setVerticalSpacing(8)

        load_btn = QPushButton("Load Batch Files")
        load_btn.setIcon(icon("fa6s.folder-open", "#ffffff"))
        load_btn.setMinimumHeight(38)
        load_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        load_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        load_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.OLIVE};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 9px 18px;
                font-size: {F.SZ_LG}pt;
                font-weight: 600;
            }}
            QPushButton:hover   {{ background: {C.OLIVE_H}; }}
            QPushButton:pressed {{ background: {C.OLIVE_DK}; }}
        """)
        load_btn.clicked.connect(self.load_files_requested.emit)
        lay.addWidget(load_btn, 0, 0, 1, 2)

        resume_btn = QPushButton("Resume Latest Session")
        resume_btn.setIcon(icon("fa6s.clock-rotate-left", C.TEXT_MID))
        resume_btn.setMinimumHeight(34)
        resume_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        resume_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        resume_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,170);
                color: {C.TEXT_MID};
                border: 1.5px solid {C.BORDER_DK};
                border-radius: 8px;
                padding: 7px 18px;
                font-size: {F.SZ_BASE}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {C.EARTH};
                color: {C.EARTH};
                background: rgba(210,180,140,46);
            }}
            QPushButton:disabled {{
                color: {C.TEXT_MUTED};
                border-color: rgba(212,196,168,0.65);
                background: rgba(255,255,255,120);
            }}
        """)
        resume_btn.setEnabled(bool(self.recent_sessions))
        resume_btn.clicked.connect(self._resume_latest_session)
        self._resume_btn = resume_btn
        lay.addWidget(resume_btn, 1, 0)

        demo_btn = QPushButton("Open Demo Sample")
        demo_btn.setIcon(icon("fa6s.vial", C.OLIVE_DK))
        demo_btn.setMinimumHeight(34)
        demo_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        demo_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        demo_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,142);
                color: {C.TEXT_MID};
                border: 1px solid rgba(107,142,35,88);
                border-radius: 8px;
                padding: 7px 16px;
                font-size: {F.SZ_BASE}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(107,142,35,18);
                color: {C.OLIVE_DK};
                border-color: rgba(107,142,35,132);
            }}
        """)
        demo_btn.clicked.connect(self.load_sample_data_requested.emit)
        lay.addWidget(demo_btn, 1, 1)

        latest_name = self.recent_sessions[0].get("name", "Latest session") if self.recent_sessions else "No saved session yet"
        note = QLabel(
            f"Latest workspace: {latest_name}" if self.recent_sessions
            else "No saved workspace yet. Load files or open the demo sample to begin."
        )
        note.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: transparent; border: none;"
        )
        note.setWordWrap(True)
        self._resume_hint = note
        lay.addWidget(note, 2, 0, 1, 2)
        return w

    # ── Footer ───────────────────────────────────────────────────

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        w.setMaximumWidth(_CARD_W)
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)

        self.dont_show_checkbox = QCheckBox(
            "Don't show this welcome screen on startup"
        )
        self.dont_show_checkbox.setStyleSheet(
            f"color: rgba(80,60,30,191); font-size: {F.SZ_SM}pt; background: transparent;"
        )
        self.dont_show_checkbox.stateChanged.connect(
            lambda state: self.dont_show_again_changed.emit(
                state == Qt.CheckState.Checked.value
            )
        )
        lay.addWidget(self.dont_show_checkbox)
        lay.addStretch()

        self._footer_attr = QLabel("Batch import · compare selected · export chosen scope")
        self._footer_attr.setStyleSheet(
            f"color: rgba(80,60,30,140); font-family: '{F.MONO}'; font-size: {F.SZ_XS - 1}pt;"
            " background: rgba(255,255,255,140); padding: 2px 8px; border-radius: 3px;"
        )
        lay.addWidget(self._footer_attr)
        return w

    # ── Helpers ──────────────────────────────────────────────────

    def _sync_card_widths(self):
        if self.width() <= 0:
            return

        target = min(_CARD_W, max(280, self.width() - 40))
        for widget in (self._title_card, self._main_card, self._footer):
            if widget is not None:
                widget.setFixedWidth(target)

        if self._footer_attr is not None:
            if target < 620:
                self._footer_attr.setText("Batch import · compare · export")
            else:
                self._footer_attr.setText("Batch import · compare selected · export chosen scope")

    def _resume_latest_session(self):
        if self.recent_sessions:
            self.open_recent_session_requested.emit(dict(self.recent_sessions[0]))
        else:
            self.load_files_requested.emit()

    def _load_session_files(self, files: List[str]):
        for f in files:
            if os.path.exists(f):
                self.open_recent_file_requested.emit(f)

    def _open_full_changelog(self):
        changelog_path = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
        if changelog_path.exists():
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(changelog_path)))
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Changelog",
                f"Changelog will be at:\n{changelog_path}\n\nCurrently in development.",
            )

    def update_recent_files(self, recent_files: List[str]):
        """Called by main_window; full refresh is handled by _refresh_welcome_widget."""
        self.recent_files = recent_files

    def update_recent_sessions(self, recent_sessions: List[dict]):
        """Called by main_window; full refresh is handled by _refresh_welcome_widget."""
        self.recent_sessions = recent_sessions


class _ClearWidget(QWidget):
    """QWidget that never paints its own background.

    Overriding paintEvent to skip super() prevents the global QSS rule
    ``QWidget { background-color: C.BG }`` from drawing a solid fill that
    would cover the parent WelcomeWidget's painted soil-image background.
    Child widgets (cards) still paint themselves normally on top.
    """

    def paintEvent(self, event: QPaintEvent):  # noqa: N802
        pass  # intentionally empty — parent's painted background shows through


class _HoverFrame(QFrame):
    """Hover-aware frame for interactive welcome-screen rows."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def enterEvent(self, event):
        self.setProperty("hovered", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
