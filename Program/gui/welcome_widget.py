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

from PyQt6.QtCore import QRect, QSettings, QSize, Qt, pyqtSignal
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
_CARD_W = 740


class WelcomeWidget(QWidget):
    """Welcome screen shown in the first dataset tab."""

    load_files_requested       = pyqtSignal()
    load_sample_data_requested = pyqtSignal()
    open_recent_file_requested = pyqtSignal(str)
    open_help_topic_requested  = pyqtSignal(str)
    dont_show_again_changed    = pyqtSignal(bool)
    clear_sessions_requested   = pyqtSignal()

    def __init__(self, recent_files: List[str] = None, parent=None):
        super().__init__(parent)
        self.recent_files = recent_files or []
        self.setAutoFillBackground(False)
        self._bg_pixmap = self._load_bg_pixmap()
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
        lay.setContentsMargins(20, 22, 20, 14)
        lay.setSpacing(14)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        lay.addWidget(self._build_title_card(), 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._build_main_card(),  0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._build_footer(),     0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    # ── Title card ───────────────────────────────────────────────

    def _build_title_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("wlc-title")
        card.setStyleSheet("""
            QFrame#wlc-title {
                background: rgba(255,255,255,64);
                border: 1.5px solid rgba(255,255,255,110);
                border-radius: 12px;
            }
        """)
        card.setMaximumWidth(_CARD_W)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 20, 28, 18)
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
            f"color: {C.TEXT_MID}; font-size: {F.SZ_LG}pt; font-weight: 400;"
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
                    background: rgba(107,142,35,30);
                    border: 1px solid rgba(107,142,35,70);
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
                f"color: {C.OLIVE}; font-size: {F.SZ_XS}pt; font-weight: 600;"
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
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: transparent;"
        )
        lay.addWidget(ver)
        return card

    # ── Main card ────────────────────────────────────────────────

    def _build_main_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("wlc-card")
        card.setStyleSheet("""
            QFrame#wlc-card {
                background: rgba(255,255,255,247);
                border: 1.5px solid rgba(180,160,130,64);
                border-radius: 10px;
            }
        """)
        card.setMaximumWidth(_CARD_W)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        grid = QGridLayout(card)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setSpacing(8)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        grid.addWidget(
            self._build_section("fa6s.folder-open", "Recent Sessions",
                                self._build_recent(), clear_btn=True), 0, 0
        )
        grid.addWidget(
            self._build_section("fa6s.file-lines", "What's New",
                                self._build_whats_new()), 0, 1
        )
        grid.addWidget(
            self._build_section("fa6s.book", "Quick Help",
                                self._build_help()), 1, 0
        )
        grid.addWidget(
            self._build_section("fa6s.rocket", "Quick Actions",
                                self._build_actions()), 1, 1
        )
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        # Equal row stretch so sections share space proportionally
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 0)
        return card

    # ── Section box ──────────────────────────────────────────────

    def _build_section(self, icon_name: str, title: str, content: QWidget,
                       clear_btn: bool = False) -> QFrame:
        sec = QFrame()
        sec.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sec.setStyleSheet(f"""
            QFrame {{
                background: #f8f6f2;
                border: 1px solid {C.BORDER};
                border-radius: 6px;
            }}
        """)

        lay = QVBoxLayout(sec)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(7)

        # Header row
        hdr = QWidget()
        hdr.setStyleSheet("background: transparent; border: none;")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(0, 0, 0, 0)
        hdr_lay.setSpacing(6)

        ico_lbl = QLabel()
        ico_lbl.setPixmap(icon(icon_name, C.EARTH).pixmap(QSize(13, 13)))
        ico_lbl.setStyleSheet("background: transparent; border: none;")

        ttl_lbl = QLabel(title)
        ttl_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_LG}pt; font-weight: 600;"
            " background: transparent; border: none;"
        )

        hdr_lay.addWidget(ico_lbl)
        hdr_lay.addWidget(ttl_lbl)
        hdr_lay.addStretch()

        if clear_btn:
            clr = QPushButton("Clear")
            clr.setFixedHeight(22)
            clr.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            clr.setStyleSheet("""
                QPushButton { background: #dc3545; color: white; border: none;
                              border-radius: 3px; padding: 0 8px; font-size: 9pt; }
                QPushButton:hover { background: #c82333; }
            """)
            clr.clicked.connect(self.clear_sessions_requested.emit)
            hdr_lay.addWidget(clr)

        lay.addWidget(hdr)
        lay.addWidget(content)
        lay.addStretch()   # push header+content to top when section is stretched tall
        return sec

    # ── Recent Sessions ──────────────────────────────────────────

    def _build_recent(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)

        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        sessions = settings.value("recent_sessions", [])
        if not isinstance(sessions, list):
            sessions = []

        if sessions:
            for s in sessions[:4]:
                lay.addWidget(self._build_session_row(s))
        else:
            empty = QLabel("No recent sessions")
            empty.setStyleSheet(
                f"color: {C.TEXT_MUTED}; font-style: italic; font-size: {F.SZ_BASE}pt;"
                " background: transparent; border: none; padding: 12px 6px;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(empty)

        return w

    def _build_session_row(self, s: dict) -> QFrame:
        """One session entry — card-style with left earth accent."""
        files = s.get("files", [])
        date  = s.get("date", "")
        name  = s.get("name", "Unnamed Session")
        n     = len(files)

        row = QFrame()
        row.setObjectName("rec-row")
        row.setStyleSheet(f"""
            QFrame#rec-row {{
                background: rgba(255,255,255,180);
                border: 1px solid rgba(212,196,168,0.7);
                border-left: 3px solid {C.EARTH};
                border-radius: 4px;
            }}
        """)
        row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(10, 8, 10, 8)
        row_lay.setSpacing(9)

        # Folder icon
        ico = QLabel()
        ico.setPixmap(icon("fa6s.folder-open", C.EARTH).pixmap(QSize(14, 14)))
        ico.setStyleSheet("background: transparent; border: none;")
        ico.setFixedWidth(16)
        ico.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)

        # Text block
        tx = QWidget()
        tx.setStyleSheet("background: transparent; border: none;")
        tx_lay = QVBoxLayout(tx)
        tx_lay.setContentsMargins(0, 0, 0, 0)
        tx_lay.setSpacing(2)

        nm_lbl = QLabel(name)
        nm_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_BASE}pt; font-weight: 600;"
            " background: transparent; border: none;"
        )

        meta_parts = [f"{n} file{'s' if n != 1 else ''}"]
        if date:
            meta_parts.append(date)
        meta_lbl = QLabel("  ·  ".join(meta_parts))
        meta_lbl.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: transparent; border: none;"
        )

        tx_lay.addWidget(nm_lbl)
        tx_lay.addWidget(meta_lbl)

        # Chevron
        chev = QLabel()
        chev.setPixmap(icon("fa6s.chevron-right", C.TEXT_MUTED).pixmap(QSize(8, 8)))
        chev.setStyleSheet("background: transparent; border: none;")
        chev.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        row_lay.addWidget(ico)
        row_lay.addWidget(tx, 1)
        row_lay.addWidget(chev)

        row.mousePressEvent = lambda e, f=files: self._load_session_files(f)
        return row

    # ── What's New ───────────────────────────────────────────────

    def _build_whats_new(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(148)
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

        for v in [
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
        ]:
            blk = QWidget()
            blk.setStyleSheet("background: transparent; border: none;")
            blk_lay = QVBoxLayout(blk)
            blk_lay.setContentsMargins(0, 0, 0, 0)
            blk_lay.setSpacing(1)

            hdr_row = QWidget()
            hdr_row.setStyleSheet("background: transparent; border: none;")
            hr_lay = QHBoxLayout(hdr_row)
            hr_lay.setContentsMargins(0, 0, 0, 0)
            hr_lay.setSpacing(5)

            d_ico = QLabel()
            d_ico.setPixmap(icon("fa6s.diamond", C.OLIVE).pixmap(QSize(9, 9)))
            d_ico.setStyleSheet("background: transparent; border: none;")

            ver_lbl = QLabel(v["version"])
            ver_lbl.setStyleSheet(
                f"color: {C.TEXT}; font-size: {F.SZ_BASE}pt; font-weight: 600;"
                " background: transparent; border: none;"
            )
            date_lbl = QLabel(f"({v['date']})")
            date_lbl.setStyleSheet(
                f"color: {C.TEXT_MUTED}; font-size: {F.SZ_XS}pt;"
                " background: transparent; border: none;"
            )

            hr_lay.addWidget(d_ico)
            hr_lay.addWidget(ver_lbl)
            hr_lay.addWidget(date_lbl)
            hr_lay.addStretch()
            blk_lay.addWidget(hdr_row)

            for ch in v["changes"]:
                ch_lbl = QLabel(f"• {ch}")
                ch_lbl.setStyleSheet(
                    f"color: #555; font-size: {F.SZ_SM}pt; padding-left: 12px;"
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
                background: transparent;
                border: 1px solid rgba(107,142,35,87);
                border-radius: 3px;
                color: {C.OLIVE};
                font-size: {F.SZ_SM}pt;
                padding: 4px 10px;
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

        for (name, file), (r, c) in zip(
            [
                ("Getting Started", "getting_started.html"),
                ("File Formats",    "file_formats.html"),
                ("Methods",         "methods_overview.html"),
                ("Troubleshoot",    "troubleshooting.html"),
            ],
            [(0, 0), (0, 1), (1, 0), (1, 1)],
        ):
            btn = QPushButton(name)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(28)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid rgba(107,142,35,87);
                    border-radius: 3px;
                    color: {C.OLIVE};
                    font-size: {F.SZ_SM}pt;
                    padding: 5px 6px;
                }}
                QPushButton:hover {{ background: rgba(107,142,35,20); }}
            """)
            btn.clicked.connect(lambda ch, f=file: self.open_help_topic_requested.emit(f))
            grid.addWidget(btn, r, c)

        return w

    # ── Quick Actions ────────────────────────────────────────────

    def _build_actions(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        load_btn = QPushButton("Load Batch Files")
        load_btn.setIcon(icon("fa6s.folder-open", "#ffffff"))
        load_btn.setMinimumHeight(36)
        load_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        load_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        load_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.OLIVE};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 9px 18px;
                font-size: {F.SZ_LG}pt;
                font-weight: 600;
            }}
            QPushButton:hover   {{ background: {C.OLIVE_H}; }}
            QPushButton:pressed {{ background: {C.OLIVE_DK}; }}
        """)
        load_btn.clicked.connect(self.load_files_requested.emit)
        lay.addWidget(load_btn)

        resume_btn = QPushButton("Resume Recent Session")
        resume_btn.setIcon(icon("fa6s.clock-rotate-left", C.TEXT_MID))
        resume_btn.setMinimumHeight(36)
        resume_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        resume_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        resume_btn.setStyleSheet(f"""
            QPushButton {{
                background: white;
                color: {C.TEXT_MID};
                border: 1.5px solid {C.BORDER_DK};
                border-radius: 5px;
                padding: 7px 18px;
                font-size: {F.SZ_LG}pt;
            }}
            QPushButton:hover {{
                border-color: {C.EARTH};
                color: {C.EARTH};
                background: rgba(210,180,140,46);
            }}
        """)
        resume_btn.clicked.connect(self.load_files_requested.emit)
        lay.addWidget(resume_btn)

        note = QLabel(
            "Open one file or many. The sidebar becomes the batch inventory, "
            "while comparison and export operate on the selected subset."
        )
        note.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_XS}pt;"
            " background: transparent; border: none;"
        )
        note.setWordWrap(True)
        lay.addWidget(note)
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
            f"color: rgba(80,60,30,191); font-size: {F.SZ_BASE}pt; background: transparent;"
        )
        self.dont_show_checkbox.stateChanged.connect(
            lambda state: self.dont_show_again_changed.emit(
                state == Qt.CheckState.Checked.value
            )
        )
        lay.addWidget(self.dont_show_checkbox)
        lay.addStretch()

        attr = QLabel("Batch import · compare selected · export chosen scope")
        attr.setStyleSheet(
            f"color: rgba(80,60,30,140); font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: rgba(255,255,255,140); padding: 2px 8px; border-radius: 3px;"
        )
        lay.addWidget(attr)
        return w

    # ── Helpers ──────────────────────────────────────────────────

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


class _ClearWidget(QWidget):
    """QWidget that never paints its own background.

    Overriding paintEvent to skip super() prevents the global QSS rule
    ``QWidget { background-color: C.BG }`` from drawing a solid fill that
    would cover the parent WelcomeWidget's painted soil-image background.
    Child widgets (cards) still paint themselves normally on top.
    """

    def paintEvent(self, event: QPaintEvent):  # noqa: N802
        pass  # intentionally empty — parent's painted background shows through
