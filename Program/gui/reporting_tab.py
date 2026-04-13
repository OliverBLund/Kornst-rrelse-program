"""Reporting tab — accordion composer matching design_concepts/08_reports_composer.html."""
from __future__ import annotations

from html import escape
import os
import re
from typing import List, Optional

from PyQt6.QtCore import Qt, QSettings, QSize, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QPageLayout, QPageSize, QCursor, QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import QMarginsF

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
    WEBENGINE_IMPORT_ERROR = ""
except ImportError as exc:
    HAS_WEBENGINE = False
    WEBENGINE_IMPORT_ERROR = str(exc)

from .theme import C, F, icon as theme_icon
from .report_brand import ReportBrand
from report_generator import ReportGenerator
from grain_classification import ISO14688


# ═══════════════════════════════════════════════════════════════
# DESIGN TOKENS (local, derived from 08_reports_composer.html)
# ═══════════════════════════════════════════════════════════════

PANEL_W         = 360       # composer panel width
ACC_HDR_H       = 32        # accordion header height
TOGGLE_W        = 28
TOGGLE_H        = 15
SAMPLE_COLS     = 3
GEN_BTN_H       = 33


# ═══════════════════════════════════════════════════════════════
# TOGGLE PILL — custom painted on/off switch (28×15)
# ═══════════════════════════════════════════════════════════════

class _TogglePill(QWidget):
    """Small painted toggle switch matching .rpt-toggle in the concept."""

    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._on = bool(checked)
        self.setFixedSize(TOGGLE_W, TOGGLE_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._on

    def setChecked(self, value: bool) -> None:
        value = bool(value)
        if value == self._on:
            return
        self._on = value
        self.update()
        self.toggled.emit(self._on)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._on)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        bg = QColor(C.OLIVE) if self._on else QColor(C.BORDER)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(rect, TOGGLE_H / 2, TOGGLE_H / 2)

        knob_d = TOGGLE_H - 4
        knob_x = (TOGGLE_W - knob_d - 2) if self._on else 2
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QRect(knob_x, 2, knob_d, knob_d))


# ═══════════════════════════════════════════════════════════════
# ACCORDION SECTION — header + collapsible body
# ═══════════════════════════════════════════════════════════════

class _AccordionSection(QWidget):
    """Collapsible section with icon + title + meta pill + chevron."""

    CHEVRON_DOWN = "\u25BE"    # ▾
    CHEVRON_RIGHT = "\u25B8"   # ▸

    def __init__(self, icon_text: str, title: str, parent=None):
        super().__init__(parent)
        self._open = False
        self.setObjectName("accSection")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header row
        self._hdr = QWidget(self)
        self._hdr.setObjectName("accHdr")
        self._hdr.setFixedHeight(ACC_HDR_H)
        self._hdr.setCursor(Qt.CursorShape.PointingHandCursor)

        hlay = QHBoxLayout(self._hdr)
        hlay.setContentsMargins(12, 0, 13, 0)
        hlay.setSpacing(8)

        self._icon_lbl = QLabel(icon_text)
        self._icon_lbl.setObjectName("accIcon")
        self._icon_lbl.setFixedWidth(14)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("accTitle")

        self._meta_lbl = QLabel("")
        self._meta_lbl.setObjectName("accMeta")
        self._meta_lbl.setMinimumHeight(18)
        self._meta_lbl.setMaximumWidth(180)

        self._chev_lbl = QLabel(self.CHEVRON_RIGHT)
        self._chev_lbl.setObjectName("accChev")
        self._chev_lbl.setFixedWidth(12)
        self._chev_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hlay.addWidget(self._icon_lbl)
        hlay.addWidget(self._title_lbl)
        hlay.addStretch()
        hlay.addWidget(self._meta_lbl)
        hlay.addWidget(self._chev_lbl)

        # Body container (hidden by default)
        self._body = QWidget(self)
        self._body.setObjectName("accBody")
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(0, 0, 0, 0)
        self._body_lay.setSpacing(0)
        self._body.setVisible(False)

        # Bottom border line
        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.Shape.HLine)
        self._sep.setFixedHeight(1)
        self._sep.setStyleSheet(f"background:{C.BORDER}; color:{C.BORDER};")

        root.addWidget(self._hdr)
        root.addWidget(self._body)
        root.addWidget(self._sep)

        self._apply_header_style()
        # Install click handler on header
        self._hdr.mousePressEvent = self._on_header_clicked  # type: ignore[assignment]

    # ── Public API ────────────────────────────────────────────
    def body_layout(self) -> QVBoxLayout:
        return self._body_lay

    def set_open(self, value: bool) -> None:
        value = bool(value)
        if value == self._open:
            return
        self._open = value
        self._body.setVisible(value)
        self._chev_lbl.setText(self.CHEVRON_DOWN if value else self.CHEVRON_RIGHT)
        self._meta_lbl.setVisible(not value)
        self._apply_header_style()

    def is_open(self) -> bool:
        return self._open

    def set_meta(self, text: str) -> None:
        self._meta_lbl.setText(text)

    # ── Internals ─────────────────────────────────────────────
    def _on_header_clicked(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_open(not self._open)
            event.accept()

    def _apply_header_style(self) -> None:
        bg = C.BG_RAISED if self._open else C.BG_LOW
        icon_col = C.OLIVE_DK if self._open else C.TEXT_MUTED
        chev_col = C.OLIVE if self._open else C.TEXT_MUTED
        title_col = C.TEXT if self._open else C.TEXT_MID
        self._hdr.setStyleSheet(f"""
            QWidget#accHdr {{
                background: {bg};
            }}
            QWidget#accHdr:hover {{
                background: {C.BG_RAISED};
            }}
            QLabel#accIcon {{
                color: {icon_col};
                font-size: {F.SZ_SM}pt;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#accTitle {{
                color: {title_col};
                font-family: "{F.UI}";
                font-size: {F.SZ_MD}pt;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#accChev {{
                color: {chev_col};
                font-size: {F.SZ_MD}pt;
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


# ═══════════════════════════════════════════════════════════════
# REPORT TYPE CARD (Section 1)
# ═══════════════════════════════════════════════════════════════

class _TypeCard(QFrame):
    """2×2 grid card for selecting report type."""

    clicked = pyqtSignal(int)

    def __init__(self, card_id: int, icon_text: str, label: str, desc: str, parent=None):
        super().__init__(parent)
        self._id = card_id
        self._on = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 9)
        lay.setSpacing(4)

        self._icon = QLabel(icon_text)
        self._icon.setObjectName("tcIcon")
        self._icon.setFixedSize(24, 24)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._lbl = QLabel(label)
        self._lbl.setObjectName("tcLbl")
        self._lbl.setWordWrap(True)

        self._desc = QLabel(desc)
        self._desc.setObjectName("tcDesc")
        self._desc.setWordWrap(True)

        self._check = QLabel("\u2713")
        self._check.setObjectName("tcCheck")
        self._check.setParent(self)
        self._check.setFixedSize(12, 12)
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(self._icon)
        lay.addWidget(self._lbl)
        lay.addWidget(self._desc)
        lay.addStretch()

        self._apply_style()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._check.move(self.width() - 18, 7)

    def is_on(self) -> bool:
        return self._on

    def set_on(self, value: bool) -> None:
        self._on = bool(value)
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._id)
            event.accept()
            return
        super().mousePressEvent(event)

    def _apply_style(self) -> None:
        if self._on:
            bg      = "rgba(107,142,35,0.08)"
            border  = C.OLIVE
            icon_bg = "rgba(107,142,35,0.15)"
            icon_c  = C.OLIVE
            icon_bd = C.OLIVE
        else:
            bg      = "rgba(255,255,255,0.4)"
            border  = C.BORDER
            icon_bg = C.BG_LOW
            icon_c  = C.TEXT_MUTED
            icon_bd = C.BORDER

        self.setStyleSheet(f"""
            _TypeCard {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 6px;
            }}
            QLabel#tcIcon {{
                background: {icon_bg};
                border: 1px solid {icon_bd};
                border-radius: 4px;
                color: {icon_c};
                font-family: "{F.UI}";
                font-size: {F.SZ_LG}pt;
                font-weight: 700;
            }}
            QLabel#tcLbl {{
                color: {C.TEXT};
                font-family: "{F.UI}";
                font-size: {F.SZ_MD}pt;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#tcDesc {{
                color: {C.TEXT_MUTED};
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                background: transparent;
            }}
            QLabel#tcCheck {{
                color: {"white" if self._on else "transparent"};
                background: {C.OLIVE if self._on else "transparent"};
                border-radius: 6px;
                font-family: "{F.UI}";
                font-size: {F.SZ_XS}pt;
                font-weight: 700;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# SAMPLE CARD (Section 2)
# ═══════════════════════════════════════════════════════════════

class _SampleCard(QFrame):
    """Compact selectable card showing sample id + depth + d50."""

    toggled = pyqtSignal(int, bool)

    def __init__(self, index: int, sample_id: str, depth: str, d50: str, parent=None):
        super().__init__(parent)
        self._index = index
        self._on = True
        self._sample_id = sample_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(7, 7, 7, 6)
        lay.setSpacing(1)

        self._id_lbl = QLabel(sample_id)
        self._id_lbl.setObjectName("scId")
        self._id_lbl.setToolTip(sample_id)

        self._dep_lbl = QLabel(depth)
        self._dep_lbl.setObjectName("scDepth")

        self._d50_lbl = QLabel(d50)
        self._d50_lbl.setObjectName("scD50")

        lay.addWidget(self._id_lbl)
        lay.addWidget(self._dep_lbl)
        lay.addWidget(self._d50_lbl)
        lay.addStretch()

        self._chk = QLabel("\u2713", self)
        self._chk.setObjectName("scChk")
        self._chk.setFixedSize(13, 13)
        self._chk.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._apply_style()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._chk.move(self.width() - 18, 5)

    def sample_id(self) -> str:
        return self._sample_id

    def index(self) -> int:
        return self._index

    def is_on(self) -> bool:
        return self._on

    def set_on(self, value: bool) -> None:
        value = bool(value)
        if value == self._on:
            return
        self._on = value
        self._apply_style()
        self.toggled.emit(self._index, self._on)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_on(not self._on)
            event.accept()
            return
        super().mousePressEvent(event)

    def _apply_style(self):
        if self._on:
            bg_css = "rgba(107,142,35,0.08)"
            bd_css = C.OLIVE
            chk_bg = C.OLIVE
            chk_bd = C.OLIVE
            chk_c  = "white"
        else:
            bg_css = "rgba(255,255,255,0.45)"
            bd_css = C.BORDER
            chk_bg = "white"
            chk_bd = C.BORDER_DK
            chk_c  = "transparent"

        self.setStyleSheet(f"""
            _SampleCard {{
                background: {bg_css};
                border: 1.5px solid {bd_css};
                border-radius: 5px;
            }}
            QLabel#scId {{
                color: {C.TEXT};
                font-family: "{F.MONO}";
                font-size: {F.SZ_SM}pt;
                background: transparent;
            }}
            QLabel#scDepth {{
                color: {C.TEXT_MUTED};
                font-family: "{F.UI}";
                font-size: {F.SZ_XS}pt;
                background: transparent;
            }}
            QLabel#scD50 {{
                color: {C.OLIVE_DK};
                font-family: "{F.UI}";
                font-size: {F.SZ_XS}pt;
                font-weight: 600;
                background: transparent;
            }}
            QLabel#scChk {{
                background: {chk_bg};
                border: 1.5px solid {chk_bd};
                border-radius: 3px;
                color: {chk_c};
                font-family: "{F.UI}";
                font-size: {F.SZ_XS}pt;
                font-weight: 700;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# SECTION ROW (Section 3)
# ═══════════════════════════════════════════════════════════════

class _SectionRow(QFrame):
    """Toggleable section row: icon + label [+ required pill] + toggle."""

    toggled = pyqtSignal(bool)

    def __init__(self, icon_text: str, label: str, required: bool = False, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 0, 9, 0)
        lay.setSpacing(7)

        self._icon = QLabel(icon_text)
        self._icon.setFixedWidth(12)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; background: transparent;"
        )

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            f'color: {C.TEXT_MID}; font-family: "{F.UI}"; font-size: {F.SZ_MD}pt; '
            f'background: transparent;'
        )

        self._pill = QLabel("required") if required else None

        self._toggle = _TogglePill(True)
        self._toggle.toggled.connect(self.toggled.emit)

        lay.addWidget(self._icon)
        lay.addWidget(self._lbl)
        if self._pill is not None:
            self._pill.setStyleSheet(f"""
                QLabel {{
                    color: {C.TEXT_MUTED};
                    background: {C.BG_LOW};
                    border: 1px solid {C.BORDER};
                    border-radius: 7px;
                    padding: 1px 6px;
                    font-family: "{F.UI}";
                    font-size: {F.SZ_XS}pt;
                }}
            """)
            lay.addWidget(self._pill)
        lay.addStretch()
        lay.addWidget(self._toggle)

        self._apply_style(False)

    def is_checked(self) -> bool:
        return self._toggle.isChecked()

    def set_checked(self, value: bool) -> None:
        self._toggle.setChecked(value)

    def mousePressEvent(self, event):
        # Clicking the row (but not directly on the toggle) flips the toggle
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._toggle.geometry().contains(event.pos()):
                self._toggle.setChecked(not self._toggle.isChecked())
                event.accept()
                return
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self._apply_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style(False)
        super().leaveEvent(event)

    def _apply_style(self, hovered: bool) -> None:
        bg = "rgba(255,255,255,0.6)" if hovered else "rgba(255,255,255,0.3)"
        bd = C.BORDER if hovered else "transparent"
        self.setStyleSheet(f"""
            _SectionRow {{
                background: {bg};
                border: 1px solid {bd};
                border-radius: 4px;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# MAIN TAB
# ═══════════════════════════════════════════════════════════════

class ReportingTab(QWidget):
    """Tab for generating and previewing professional reports."""

    # Section key mapping (concept row → backend flag)
    SECTION_KEYS = [
        ("cover",        "\u25A1",  "Cover Page",           True),
        ("executive",    "\u2261",  "Executive Summary",    False),
        ("results",      "\u229E",  "Grain Size Data",      False),
        ("plots",        "\u223F",  "Distribution Plot",    False),
        ("k_stats",      "\u2248",  "K-Values Table",       False),
        ("gradation",    "\u2510",  "Statistics",           False),
        ("methodology",  "\u203B",  "Method References",    False),
    ]
    APPENDIX_KEYS = [
        ("raw",     "\u229E", "A \u2014 Raw Sieve Data"),
        ("interp",  "\u223F", "B \u2014 Full-Size Plots"),
        ("quality", "\u2692", "C \u2014 Method Details"),
    ]
    # Outline page hints (must match order: main sections then appendices)
    OUTLINE_PAGES = [1, 2, 3, 5, 7, 9, 11, 13, 15, 17]

    # Report type card ids
    TYPE_INDIVIDUAL = 0
    TYPE_COMPARISON = 1
    TYPE_FULL       = 2
    TYPE_KFOCUS     = 3

    # Output format options
    FORMATS = ["PDF", "HTML", "Word (.docx)"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report_generator = ReportGenerator()
        self._scheme = ISO14688
        self.dataset_tabs: List = []
        self._sample_contexts: list[dict] = []
        self._sample_cards: list[_SampleCard] = []
        self._section_rows: dict[str, _SectionRow] = {}
        self._outline_items: list[tuple[QLabel, QLabel, bool]] = []  # (label, page, appendix?)
        self.current_report_html = ""
        self.brand = ReportBrand.load()
        self._settings = QSettings("GrainSizeAnalysis", "ReportingTab")
        self._restoring_settings = False
        self._selected_type = self.TYPE_COMPARISON

        self._init_ui()
        self._connect_signals()
        self._load_report_settings()
        self._refresh_meta_pills()
        self._update_outline()

    # ══════════════════════════════════════════════════════════
    # UI construction
    # ══════════════════════════════════════════════════════════

    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)

        # Left composer panel
        left = self._build_composer_panel()
        left.setMinimumWidth(320)
        left.setMaximumWidth(420)

        # Right preview panel
        right = self._build_preview_panel()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([PANEL_W, 900])

        root.addWidget(splitter)

    # ── Composer Panel ────────────────────────────────────────
    def _build_composer_panel(self) -> QWidget:
        wrapper = QWidget()
        wrapper.setObjectName("rptPanel")
        wrapper.setStyleSheet(f"""
            QWidget#rptPanel {{
                background: {C.BG_RAISED};
                border-right: 1px solid {C.BORDER};
            }}
        """)

        wlay = QVBoxLayout(wrapper)
        wlay.setContentsMargins(0, 0, 0, 0)
        wlay.setSpacing(0)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background: {C.BG_RAISED}; border: none; }}")

        body = QWidget()
        body.setObjectName("rptPanelBody")
        body.setStyleSheet(f"QWidget#rptPanelBody {{ background: {C.BG_RAISED}; }}")

        blay = QVBoxLayout(body)
        blay.setContentsMargins(0, 0, 0, 0)
        blay.setSpacing(0)

        # Accordion 1: Report Type
        self._acc_type = _AccordionSection("\u25A4", "Report Type")
        self._build_type_section(self._acc_type.body_layout())
        blay.addWidget(self._acc_type)

        # Accordion 2: Samples
        self._acc_samples = _AccordionSection("\u2699", "Samples")
        self._build_samples_section(self._acc_samples.body_layout())
        blay.addWidget(self._acc_samples)

        # Accordion 3: Sections & Appendices
        self._acc_sects = _AccordionSection("\u2630", "Sections & Appendices")
        self._build_sections_section(self._acc_sects.body_layout())
        blay.addWidget(self._acc_sects)

        # Accordion 4: Details & Branding
        self._acc_details = _AccordionSection("\u270E", "Details & Branding")
        self._build_details_section(self._acc_details.body_layout())
        blay.addWidget(self._acc_details)

        blay.addStretch(1)
        scroll.setWidget(body)

        # Generate footer (always visible)
        footer = self._build_generate_footer()

        wlay.addWidget(scroll, 1)
        wlay.addWidget(footer, 0)

        # Open the first two by default (matches concept)
        self._acc_type.set_open(True)
        self._acc_samples.set_open(True)

        return wrapper

    # ── Section 1: Report Type ────────────────────────────────
    def _build_type_section(self, lay: QVBoxLayout):
        area = QWidget()
        area.setStyleSheet(f"background: {C.BG_RAISED};")
        alay = QVBoxLayout(area)
        alay.setContentsMargins(13, 12, 13, 8)
        alay.setSpacing(8)

        hdr = QLabel("REPORT TYPE")
        hdr.setStyleSheet(self._uc_header_css())
        alay.addWidget(hdr)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(7)

        cards = [
            (self.TYPE_INDIVIDUAL, "\u2B22", "Individual Sample",
             "Full report for one sample \u2014 grain data, plot, K-values, statistics."),
            (self.TYPE_COMPARISON, "\u2B21", "Cross-Sample Comparison",
             "Side-by-side parameters and K-values for selected samples."),
            (self.TYPE_FULL, "\u25A4", "Full Project Summary",
             "All samples, all methods \u2014 complete project documentation."),
            (self.TYPE_KFOCUS, "\u2248", "K-Value Focus",
             "Compact report centred on hydraulic conductivity results."),
        ]
        self._type_cards: list[_TypeCard] = []
        for i, (cid, icon_ch, label, desc) in enumerate(cards):
            card = _TypeCard(cid, icon_ch, label, desc)
            card.clicked.connect(self._on_type_clicked)
            self._type_cards.append(card)
            grid.addWidget(card, i // 2, i % 2)

        alay.addLayout(grid)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C.BORDER}; color:{C.BORDER};")

        # Output options
        form = QWidget()
        flay = QVBoxLayout(form)
        flay.setContentsMargins(13, 10, 13, 13)
        flay.setSpacing(7)

        fhdr = QLabel("OUTPUT OPTIONS")
        fhdr.setStyleSheet(self._uc_header_css())
        flay.addWidget(fhdr)

        self._template_combo = self._make_form_combo()
        self._template_combo.addItems(["Standard", "Detailed", "Minimal", "DTU Official"])
        flay.addLayout(self._form_row("Template", self._template_combo))

        self._format_combo = self._make_form_combo()
        self._format_combo.addItems(self.FORMATS)
        flay.addLayout(self._form_row("Output format", self._format_combo))

        self._language_combo = self._make_form_combo()
        self._language_combo.addItems(["English", "Danish"])
        flay.addLayout(self._form_row("Language", self._language_combo))

        lay.addWidget(area)
        lay.addWidget(sep)
        lay.addWidget(form)

        # Default selection
        self._set_type_selection(self.TYPE_COMPARISON)

    def _form_row(self, label: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setFixedWidth(96)
        lbl.setStyleSheet(
            f'color: {C.TEXT_MID}; font-family: "{F.UI}"; font-size: {F.SZ_MD}pt; background: transparent;'
        )
        row.addWidget(lbl)
        row.addWidget(widget, 1)
        return row

    def _make_form_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setFixedHeight(26)
        combo.setStyleSheet(f"""
            QComboBox {{
                font-family: "{F.UI}";
                font-size: {F.SZ_MD}pt;
                color: {C.TEXT_MID};
                background: rgba(255,255,255,0.6);
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 0 7px;
            }}
            QComboBox:focus {{ border-color: {C.OLIVE}; }}
            QComboBox QAbstractItemView {{
                background: white;
                border: 1px solid {C.BORDER};
                selection-background-color: rgba(107,142,35,0.12);
                selection-color: {C.TEXT};
            }}
        """)
        return combo

    # ── Section 2: Samples ────────────────────────────────────
    def _build_samples_section(self, lay: QVBoxLayout):
        area = QWidget()
        area.setStyleSheet(f"background: {C.BG_RAISED};")
        alay = QVBoxLayout(area)
        alay.setContentsMargins(0, 0, 0, 0)
        alay.setSpacing(0)

        # Toolbar
        tbar = QWidget()
        tbar.setStyleSheet(f"background: rgba(255,255,255,0.2); border-bottom: 1px solid {C.BORDER};")
        tlay = QHBoxLayout(tbar)
        tlay.setContentsMargins(12, 9, 12, 7)
        tlay.setSpacing(6)

        self._samp_search = QLineEdit()
        self._samp_search.setPlaceholderText("Search samples\u2026")
        self._samp_search.setFixedHeight(26)
        self._samp_search.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.7);
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 0 9px;
                font-family: "{F.UI}";
                font-size: {F.SZ_MD}pt;
                color: {C.TEXT};
            }}
            QLineEdit:focus {{ border-color: {C.OLIVE}; }}
        """)
        self._samp_search.textChanged.connect(self._filter_samples)

        self._samp_groupby = QComboBox()
        self._samp_groupby.addItems(["By borehole", "By zone", "By depth"])
        self._samp_groupby.setFixedHeight(26)
        self._samp_groupby.setStyleSheet(f"""
            QComboBox {{
                background: rgba(255,255,255,0.5);
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 0 6px;
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                color: {C.TEXT_MID};
            }}
        """)
        self._samp_groupby.currentIndexChanged.connect(self._rebuild_sample_grid)

        self._samp_count_lbl = QLabel("0 / 0")
        self._samp_count_lbl.setStyleSheet(f"""
            QLabel {{
                background: {C.BG_LOW};
                border: 1px solid {C.BORDER};
                border-radius: 10px;
                padding: 2px 8px;
                font-family: "{F.MONO}";
                font-size: {F.SZ_XS}pt;
                color: {C.TEXT_MUTED};
            }}
        """)

        tlay.addWidget(self._samp_search, 1)
        tlay.addWidget(self._samp_groupby)
        tlay.addWidget(self._samp_count_lbl)

        # Links row
        links = QWidget()
        links.setStyleSheet(f"background: rgba(255,255,255,0.12); border-bottom: 1px solid {C.BORDER};")
        llay = QHBoxLayout(links)
        llay.setContentsMargins(12, 5, 12, 5)
        llay.setSpacing(8)

        def link_btn(text: str, handler):
            b = QPushButton(text)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFlat(True)
            b.setStyleSheet(f"""
                QPushButton {{
                    color: {C.OLIVE};
                    background: transparent;
                    border: none;
                    text-decoration: underline;
                    font-family: "{F.UI}";
                    font-size: {F.SZ_SM}pt;
                    padding: 0;
                }}
                QPushButton:hover {{ color: {C.OLIVE_DK}; }}
            """)
            b.clicked.connect(handler)
            return b

        sep_css = f"color:{C.TEXT_MUTED};"
        llay.addWidget(link_btn("Select all", lambda: self._samp_bulk(True)))
        s1 = QLabel("\u00B7"); s1.setStyleSheet(sep_css); llay.addWidget(s1)
        llay.addWidget(link_btn("Clear", lambda: self._samp_bulk(False)))
        s2 = QLabel("\u00B7"); s2.setStyleSheet(sep_css); llay.addWidget(s2)
        llay.addWidget(link_btn("Invert", self._samp_invert))
        llay.addStretch()

        # Cards host
        self._samp_host = QWidget()
        self._samp_host.setStyleSheet(f"background: {C.BG_RAISED};")
        self._samp_host_lay = QVBoxLayout(self._samp_host)
        self._samp_host_lay.setContentsMargins(10, 8, 10, 12)
        self._samp_host_lay.setSpacing(4)

        alay.addWidget(tbar)
        alay.addWidget(links)
        alay.addWidget(self._samp_host)

        lay.addWidget(area)

        # Initial empty-state
        self._empty_samples_label = QLabel("No samples loaded.")
        self._empty_samples_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_samples_label.setStyleSheet(
            f'color: {C.TEXT_MUTED}; font-family: "{F.UI}"; font-size: {F.SZ_MD}pt; padding: 18px 0;'
        )
        self._samp_host_lay.addWidget(self._empty_samples_label)

    # ── Section 3: Sections & Appendices ──────────────────────
    def _build_sections_section(self, lay: QVBoxLayout):
        area = QWidget()
        area.setStyleSheet(f"background: {C.BG_RAISED};")
        alay = QVBoxLayout(area)
        alay.setContentsMargins(13, 10, 13, 13)
        alay.setSpacing(3)

        # Main sections
        mhdr = QLabel("\u25A4   MAIN SECTIONS")
        mhdr.setStyleSheet(self._uc_header_css(border_bottom=True))
        mhdr.setContentsMargins(0, 0, 0, 4)
        alay.addWidget(mhdr)

        for key, icon_ch, label, required in self.SECTION_KEYS:
            row = _SectionRow(icon_ch, label, required=required)
            row.toggled.connect(lambda _v, k=key: self._on_section_toggled(k))
            self._section_rows[key] = row
            alay.addWidget(row)

        # Appendices
        ahdr = QLabel("\u25B8   APPENDICES")
        ahdr.setStyleSheet(self._uc_header_css(border_bottom=True, top_margin=12))
        ahdr.setContentsMargins(0, 0, 0, 4)
        alay.addWidget(ahdr)

        for key, icon_ch, label in self.APPENDIX_KEYS:
            row = _SectionRow(icon_ch, label)
            row.set_checked(False)  # appendices default off
            row.toggled.connect(lambda _v, k=key: self._on_section_toggled(k))
            self._section_rows[key] = row
            alay.addWidget(row)

        # Live outline box
        outline = QFrame()
        outline.setFrameShape(QFrame.Shape.StyledPanel)
        outline.setStyleSheet(f"""
            QFrame {{
                background: rgba(255,255,255,0.45);
                border: 1px solid {C.BORDER};
                border-radius: 6px;
            }}
        """)
        olay = QVBoxLayout(outline)
        olay.setContentsMargins(0, 0, 0, 0)
        olay.setSpacing(0)

        ohdr = QLabel("\u2261  DOCUMENT OUTLINE")
        ohdr.setStyleSheet(f"""
            QLabel {{
                background: {C.BG_LOW};
                color: {C.TEXT_MUTED};
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                font-weight: 700;
                padding: 6px 10px;
                border-bottom: 1px solid {C.BORDER};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
        """)
        olay.addWidget(ohdr)

        obody = QWidget()
        obody.setStyleSheet("background: transparent;")
        self._outline_body_lay = QVBoxLayout(obody)
        self._outline_body_lay.setContentsMargins(10, 6, 10, 8)
        self._outline_body_lay.setSpacing(2)
        olay.addWidget(obody)

        # Build outline items in order: main sections, then appendices
        all_keys = [(k, l, False) for k, _i, l, _r in self.SECTION_KEYS] + \
                   [(k, l, True)  for k, _i, l in self.APPENDIX_KEYS]
        for i, (key, label, is_app) in enumerate(all_keys):
            item = self._make_outline_item(label, self.OUTLINE_PAGES[i], is_app)
            self._outline_body_lay.addWidget(item["row"])
            self._outline_items.append((item["label"], item["page"], is_app))

        alay.addSpacing(12)
        alay.addWidget(outline)

        lay.addWidget(area)

    def _make_outline_item(self, label: str, page: int, appendix: bool) -> dict:
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(10 if appendix else 0, 1, 0, 1)
        rl.setSpacing(6)

        dot = QLabel("\u2022")
        dot_color = C.TAN if appendix else C.OLIVE
        dot.setStyleSheet(f"color: {dot_color}; font-size: {F.SZ_LG}pt; background: transparent;")
        dot.setFixedWidth(8)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f'color: {C.TEXT_MID}; font-family: "{F.UI}"; '
            f'font-size: {F.SZ_XS if appendix else F.SZ_SM}pt; background: transparent;'
        )

        pg = QLabel(str(page))
        pg.setStyleSheet(
            f'color: {C.TEXT_MUTED}; font-family: "{F.MONO}"; '
            f'font-size: {F.SZ_XS}pt; background: transparent;'
        )

        rl.addWidget(dot)
        rl.addWidget(lbl)
        rl.addStretch()
        rl.addWidget(pg)

        return {"row": row, "label": lbl, "page": pg}

    # ── Section 4: Details & Branding ─────────────────────────
    def _build_details_section(self, lay: QVBoxLayout):
        area = QWidget()
        area.setStyleSheet(f"background: {C.BG_RAISED};")
        alay = QVBoxLayout(area)
        alay.setContentsMargins(13, 12, 13, 14)
        alay.setSpacing(11)

        # Project information
        info = QWidget()
        ilay = QVBoxLayout(info)
        ilay.setContentsMargins(0, 0, 0, 0)
        ilay.setSpacing(7)

        ihdr = QLabel("PROJECT INFORMATION")
        ihdr.setStyleSheet(self._uc_header_css(border_bottom=True))
        ihdr.setContentsMargins(0, 0, 0, 4)
        ilay.addWidget(ihdr)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(7)

        self.project_name_edit = self._make_det_input(placeholder="e.g. Grundvandskortlægning Roskilde 2026")
        self.project_no_edit = self._make_det_input(placeholder="PRJ-2026-041")
        self.date_edit = self._make_det_input(placeholder="2026-04-10")
        self.analyst_edit = self._make_det_input(placeholder="Name")
        self.client_edit = self._make_det_input(placeholder="Client / organisation")
        # Keep for backwards compat with report generator (hidden, loaded from QSettings)
        self.location_edit = QLineEdit()
        self.location_edit.setVisible(False)

        def field(label: str, widget: QWidget, row: int, col: int, col_span: int = 1):
            cell = QWidget()
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(3)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f'color: {C.TEXT_MUTED}; font-family: "{F.UI}"; '
                f'font-size: {F.SZ_SM}pt; background: transparent;'
            )
            cl.addWidget(lbl)
            cl.addWidget(widget)
            grid.addWidget(cell, row, col, 1, col_span)

        field("Project name", self.project_name_edit, 0, 0, 2)
        field("Project no.",  self.project_no_edit,   1, 0)
        field("Date",         self.date_edit,         1, 1)
        field("Analyst",      self.analyst_edit,      2, 0)
        field("Client",       self.client_edit,       2, 1)

        ilay.addLayout(grid)

        # Logo
        logo_wrap = QWidget()
        llay = QVBoxLayout(logo_wrap)
        llay.setContentsMargins(0, 0, 0, 0)
        llay.setSpacing(7)

        lhdr = QLabel("LOGO")
        lhdr.setStyleSheet(self._uc_header_css(border_bottom=True))
        lhdr.setContentsMargins(0, 0, 0, 4)
        llay.addWidget(lhdr)

        self._logo_drop = QPushButton("\u2B07   Upload logo (PNG, SVG) \u2014 click to browse")
        self._logo_drop.setCursor(Qt.CursorShape.PointingHandCursor)
        self._logo_drop.setFixedHeight(58)
        self._logo_drop.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.3);
                border: 1.5px dashed {C.BORDER_DK};
                border-radius: 5px;
                color: {C.TEXT_MUTED};
                font-family: "{F.UI}";
                font-size: {F.SZ_MD}pt;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                border-color: {C.OLIVE};
                color: {C.OLIVE_DK};
                background: rgba(107,142,35,0.04);
            }}
        """)
        self._logo_drop.clicked.connect(self._pick_logo)
        llay.addWidget(self._logo_drop)

        # Notes
        notes_wrap = QWidget()
        nlay = QVBoxLayout(notes_wrap)
        nlay.setContentsMargins(0, 0, 0, 0)
        nlay.setSpacing(7)

        nhdr = QLabel("REPORT NOTES")
        nhdr.setStyleSheet(self._uc_header_css(border_bottom=True))
        nhdr.setContentsMargins(0, 0, 0, 4)
        nlay.addWidget(nhdr)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(
            "Optional notes \u2014 appear in the report footer or cover page\u2026"
        )
        self.notes_edit.setMinimumHeight(72)
        self.notes_edit.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(255,255,255,0.6);
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 6px 8px;
                font-family: "{F.UI}";
                font-size: {F.SZ_LG}pt;
                color: {C.TEXT};
            }}
            QTextEdit:focus {{ border-color: {C.OLIVE}; }}
        """)
        nlay.addWidget(self.notes_edit)

        alay.addWidget(info)
        alay.addWidget(logo_wrap)
        alay.addWidget(notes_wrap)
        lay.addWidget(area)

    def _make_det_input(self, placeholder: str = "") -> QLineEdit:
        edit = QLineEdit()
        edit.setFixedHeight(26)
        edit.setPlaceholderText(placeholder)
        edit.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.6);
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 0 8px;
                font-family: "{F.UI}";
                font-size: {F.SZ_LG}pt;
                color: {C.TEXT};
            }}
            QLineEdit:focus {{ border-color: {C.OLIVE}; background: white; }}
        """)
        return edit

    # ── Generate footer ───────────────────────────────────────
    def _build_generate_footer(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background: {C.BG_LOW}; border-top: 1px solid {C.BORDER};")

        lay = QVBoxLayout(bar)
        lay.setContentsMargins(12, 9, 12, 10)
        lay.setSpacing(7)

        self._gen_summary_lbl = QLabel("")
        self._gen_summary_lbl.setStyleSheet(
            f'color: {C.TEXT_MUTED}; font-family: "{F.MONO}"; font-size: {F.SZ_SM}pt; '
            f'background: transparent;'
        )
        self._gen_summary_lbl.setWordWrap(True)

        self.generate_btn = QPushButton("\u25B6   Generate Report")
        self.generate_btn.setMinimumHeight(GEN_BTN_H)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.OLIVE};
                border: 1px solid {C.OLIVE_DK};
                border-radius: 4px;
                color: white;
                font-family: "{F.UI}";
                font-size: {F.SZ_XL}pt;
                font-weight: 700;
            }}
            QPushButton:hover   {{ background: {C.OLIVE_H}; }}
            QPushButton:pressed {{ background: {C.OLIVE_DK}; }}
            QPushButton:disabled {{
                background: {C.BORDER};
                color: {C.TEXT_MUTED};
                border-color: {C.BORDER};
            }}
        """)
        self.generate_btn.clicked.connect(self._on_generate)
        self.generate_btn.setEnabled(False)

        lay.addWidget(self._gen_summary_lbl)
        lay.addWidget(self.generate_btn)
        return bar

    # ── Right: preview panel ──────────────────────────────────
    def _build_preview_panel(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {C.BG_LOW};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._build_preview_topbar())
        lay.addWidget(self._build_preview_canvas(), 1)
        return w

    def _build_preview_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setStyleSheet(
            f"background: rgba(255,255,255,0.5); border-bottom: 1px solid {C.BORDER};"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(6)

        self._preview_note = QLabel("Preview")
        self._preview_note.setStyleSheet(
            f'color: {C.TEXT_MUTED}; font-family: "{F.UI}"; font-size: {F.SZ_MD}pt; '
            f'background: transparent;'
        )
        lay.addWidget(self._preview_note)
        lay.addStretch()

        def pbtn(label: str, handler):
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(26)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.55);
                    border: 1px solid {C.BORDER};
                    border-radius: 4px;
                    padding: 0 10px;
                    color: {C.TEXT_MID};
                    font-family: "{F.UI}";
                    font-size: {F.SZ_MD}pt;
                }}
                QPushButton:hover {{
                    background: {C.BG};
                    border-color: {C.BORDER_DK};
                    color: {C.TEXT};
                }}
                QPushButton:disabled {{
                    color: {C.TEXT_MUTED};
                    border-color: {C.BORDER};
                }}
            """)
            b.clicked.connect(handler)
            return b

        self.btn_refresh = pbtn("\u21BB  Refresh", self._on_generate)
        self.btn_print   = pbtn("\u2399  Print",   self._on_print)
        self.btn_save    = pbtn("\u2913  Save",    self._on_save_primary)
        lay.addWidget(self.btn_refresh)
        lay.addWidget(self.btn_print)
        lay.addWidget(self.btn_save)

        self.btn_refresh.setEnabled(False)
        self.btn_print.setEnabled(False)
        self.btn_save.setEnabled(False)
        return bar

    def _build_preview_canvas(self) -> QWidget:
        surround = QWidget()
        surround.setStyleSheet(f"background: {C.BG_LOW};")
        lay = QVBoxLayout(surround)
        lay.setContentsMargins(24, 24, 24, 32)

        if HAS_WEBENGINE:
            self.web_view = QWebEngineView()
            self.web_view.setStyleSheet("background: white; border: none;")
            self.web_view.setHtml(self._empty_preview_html())
            self.web_view.page().pdfPrintingFinished.connect(self._on_pdf_done)
            lay.addWidget(self.web_view)
        else:
            self.web_view = QTextEdit()
            self.web_view.setReadOnly(True)
            self.web_view.setHtml(self._empty_preview_html())
            lay.addWidget(self.web_view)
            detail = WEBENGINE_IMPORT_ERROR or "Unknown import error."
            warn = QLabel(
                "WebEngine preview unavailable — PDF export disabled.\n"
                f"Import detail: {detail}"
            )
            warn.setStyleSheet(
                f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; "
                f'font-family: "{F.UI}"; padding: 4px; background: transparent;'
            )
            warn.setWordWrap(True)
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(warn)

        return surround

    # ══════════════════════════════════════════════════════════
    # Styling helpers
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _uc_header_css(border_bottom: bool = False, top_margin: int = 0) -> str:
        bb = f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;" if border_bottom else ""
        mt = f"margin-top: {top_margin}px;" if top_margin else ""
        return f"""
            QLabel {{
                color: {C.TEXT_MUTED};
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                font-weight: 700;
                letter-spacing: 1.5px;
                background: transparent;
                {bb}
                {mt}
            }}
        """

    # ══════════════════════════════════════════════════════════
    # Signal wiring & state sync
    # ══════════════════════════════════════════════════════════

    def _connect_signals(self) -> None:
        self._template_combo.currentTextChanged.connect(self._on_template_changed)
        self._format_combo.currentIndexChanged.connect(
            lambda *_: (self._refresh_meta_pills(), self._refresh_save_btn_label(),
                        self._save_report_settings())
        )
        self._language_combo.currentIndexChanged.connect(
            lambda *_: (self._refresh_meta_pills(), self._save_report_settings())
        )
        for key in list(self._section_rows.keys()):
            self._section_rows[key].toggled.connect(
                lambda *_a: self._save_report_settings()
            )
        for edit in [self.project_name_edit, self.project_no_edit, self.date_edit,
                     self.analyst_edit, self.client_edit]:
            edit.textChanged.connect(self._save_report_settings)
        self.notes_edit.textChanged.connect(self._save_report_settings)

    def _on_type_clicked(self, card_id: int) -> None:
        self._set_type_selection(card_id)
        self._save_report_settings()
        self._refresh_meta_pills()

    def _set_type_selection(self, card_id: int) -> None:
        self._selected_type = card_id
        for card in getattr(self, "_type_cards", []):
            card.set_on(card._id == card_id)

    def _on_template_changed(self, name: str) -> None:
        templates = {
            "Standard": {
                "cover": False, "executive": True, "methodology": True, "results": True,
                "plots": True,  "interp": False, "percentiles": True, "gradation": True,
                "k_stats": True, "quality": False, "raw": False,
            },
            "Detailed": {
                "cover": True,  "executive": True, "methodology": True, "results": True,
                "plots": True,  "interp": True, "percentiles": True, "gradation": True,
                "k_stats": True, "quality": True, "raw": True,
            },
            "Minimal": {
                "cover": False, "executive": True, "methodology": False, "results": True,
                "plots": True,  "interp": False, "percentiles": False, "gradation": True,
                "k_stats": True, "quality": False, "raw": False,
            },
            "DTU Official": {
                "cover": True,  "executive": True, "methodology": True, "results": True,
                "plots": True,  "interp": True, "percentiles": True, "gradation": True,
                "k_stats": True, "quality": False, "raw": False,
            },
        }
        cfg = templates.get(name)
        if not cfg:
            return
        for key, val in cfg.items():
            if key in self._section_rows:
                self._section_rows[key].set_checked(val)
        self._save_report_settings()
        self._refresh_meta_pills()

    def _on_section_toggled(self, _key: str) -> None:
        self._update_outline()
        self._refresh_meta_pills()

    def _update_outline(self) -> None:
        all_keys = [(k, False) for k, _i, _l, _r in self.SECTION_KEYS] + \
                   [(k, True)  for k, _i, _l in self.APPENDIX_KEYS]
        for i, (key, is_app) in enumerate(all_keys):
            if i >= len(self._outline_items):
                break
            lbl, pg, _ = self._outline_items[i]
            on = self._section_rows[key].is_checked() if key in self._section_rows else True
            if on:
                lbl.setStyleSheet(
                    f'color: {C.TEXT_MID}; font-family: "{F.UI}"; '
                    f'font-size: {F.SZ_XS if is_app else F.SZ_SM}pt; background: transparent;'
                )
                pg.setText(str(self.OUTLINE_PAGES[i]))
                pg.setStyleSheet(
                    f'color: {C.TEXT_MUTED}; font-family: "{F.MONO}"; '
                    f'font-size: {F.SZ_XS}pt; background: transparent;'
                )
            else:
                lbl.setStyleSheet(
                    f'color: {C.TEXT_MUTED}; font-family: "{F.UI}"; '
                    f'font-size: {F.SZ_XS if is_app else F.SZ_SM}pt; '
                    f'text-decoration: line-through; background: transparent;'
                )
                pg.setText("—")
                pg.setStyleSheet(
                    f'color: {C.BORDER_DK}; font-family: "{F.MONO}"; '
                    f'font-size: {F.SZ_XS}pt; background: transparent;'
                )

    def _refresh_meta_pills(self) -> None:
        type_name = self._type_short_name(self._selected_type)
        fmt_name = self._format_combo.currentText() if hasattr(self, "_format_combo") else "PDF"
        self._acc_type.set_meta(f"{type_name} · {fmt_name}")

        total = len(self._sample_cards)
        sel   = sum(1 for c in self._sample_cards if c.is_on())
        self._acc_samples.set_meta(f"{sel} / {total} selected" if total else "No samples")
        if hasattr(self, "_samp_count_lbl"):
            self._samp_count_lbl.setText(f"{sel} / {total}")

        main_on = sum(
            1 for k, *_ in self.SECTION_KEYS
            if k in self._section_rows and self._section_rows[k].is_checked()
        )
        app_on = sum(
            1 for k, *_ in self.APPENDIX_KEYS
            if k in self._section_rows and self._section_rows[k].is_checked()
        )
        parts = [f"{main_on} section{'s' if main_on != 1 else ''}"]
        if app_on:
            parts.append(f"{app_on} appendix")
        self._acc_sects.set_meta(" · ".join(parts))

        self._acc_details.set_meta("Project info, logo, notes")

        tmpl = self._template_combo.currentText() if hasattr(self, "_template_combo") else "Standard"
        self._gen_summary_lbl.setText(
            f"{type_name} · {sel} sample{'s' if sel != 1 else ''} · {fmt_name} · {tmpl}"
        )
        if hasattr(self, "_preview_note"):
            self._preview_note.setText(
                f"Preview · {type_name} · {sel} sample{'s' if sel != 1 else ''}"
            )
        self._refresh_save_btn_label()

    def _refresh_save_btn_label(self) -> None:
        if not hasattr(self, "btn_save"):
            return
        fmt = self._format_combo.currentText() if hasattr(self, "_format_combo") else "PDF"
        label = {
            "PDF":          "\u2913  Save PDF",
            "HTML":         "\u2913  Save HTML",
            "Word (.docx)": "\u2913  Save Word",
        }.get(fmt, "\u2913  Save")
        self.btn_save.setText(label)

    @staticmethod
    def _type_short_name(type_id: int) -> str:
        return {
            ReportingTab.TYPE_INDIVIDUAL: "Individual",
            ReportingTab.TYPE_COMPARISON: "Cross-sample",
            ReportingTab.TYPE_FULL:       "Full project",
            ReportingTab.TYPE_KFOCUS:     "K-Value focus",
        }.get(type_id, "Cross-sample")

    # ══════════════════════════════════════════════════════════
    # Data wiring — called by main_window.py
    # ══════════════════════════════════════════════════════════

    def set_scheme(self, scheme) -> None:
        self._scheme = scheme
        self.report_generator.set_scheme(scheme)

    def set_dataset_tabs(self, dataset_tabs: List) -> None:
        self.dataset_tabs = list(dataset_tabs)
        self._refresh_sample_list()

    @staticmethod
    def _build_unique_labels(names: List[str]) -> List[str]:
        totals: dict[str, int] = {}
        for name in names:
            totals[name] = totals.get(name, 0) + 1
        seen: dict[str, int] = {}
        labels: list[str] = []
        for name in names:
            seen[name] = seen.get(name, 0) + 1
            if totals[name] > 1:
                labels.append(f"{name} ({seen[name]})")
            else:
                labels.append(name)
        return labels

    def _refresh_sample_list(self) -> None:
        self._sample_contexts = []
        self._sample_cards = []
        self._clear_report_output()

        if not self.dataset_tabs:
            self._rebuild_sample_grid()
            self.generate_btn.setEnabled(False)
            self._refresh_meta_pills()
            return

        labels = self._build_unique_labels([t.get_dataset_name() for t in self.dataset_tabs])
        for tab, label in zip(self.dataset_tabs, labels):
            context = {
                "label": label,
                "tab": tab,
                "group": self._detect_group(label),
                "depth": self._detect_depth(label),
                "d50":   self._format_d50(tab),
            }
            self._sample_contexts.append(context)

        self._rebuild_sample_grid()
        self.generate_btn.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self._refresh_meta_pills()

    @staticmethod
    def _detect_group(label: str) -> str:
        """Extract a borehole-like prefix from the sample label for grouping."""
        m = re.match(r"([A-Za-z]+[-\s]?\d+)", label)
        if m:
            return m.group(1).replace(" ", "-").upper()
        parts = re.split(r"[\s/_\-]", label, maxsplit=1)
        return parts[0] if parts else label

    @staticmethod
    def _detect_depth(label: str) -> str:
        m = re.search(r"(\d+(?:\.\d+)?)\s*m", label)
        if m:
            return f"{m.group(1)} m b.g."
        return "\u2014"

    @staticmethod
    def _format_d50(tab) -> str:
        try:
            d50 = tab.get_dataset().get_d50()
        except Exception:
            d50 = None
        if d50 is None:
            return "d\u2085\u2080 —"
        return f"d\u2085\u2080 {d50:.2f} mm"

    def _rebuild_sample_grid(self) -> None:
        # Clear existing children
        while self._samp_host_lay.count():
            item = self._samp_host_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._sample_cards = []

        if not self._sample_contexts:
            self._empty_samples_label = QLabel("No samples loaded.")
            self._empty_samples_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._empty_samples_label.setStyleSheet(
                f'color: {C.TEXT_MUTED}; font-family: "{F.UI}"; '
                f'font-size: {F.SZ_MD}pt; padding: 18px 0;'
            )
            self._samp_host_lay.addWidget(self._empty_samples_label)
            self._refresh_meta_pills()
            return

        # Group samples
        groups: dict[str, list[tuple[int, dict]]] = {}
        order: list[str] = []
        for idx, ctx in enumerate(self._sample_contexts):
            gkey = ctx["group"]
            if gkey not in groups:
                groups[gkey] = []
                order.append(gkey)
            groups[gkey].append((idx, ctx))

        for gkey in order:
            items = groups[gkey]
            # Group header
            ghdr = QWidget()
            ghl = QHBoxLayout(ghdr)
            ghl.setContentsMargins(2, 7, 2, 4)
            ghl.setSpacing(5)
            ghdr.setStyleSheet(f"border-bottom: 1px solid {C.BORDER};")
            gname = QLabel(gkey)
            gname.setStyleSheet(
                f'color: {C.TEXT_MUTED}; font-family: "{F.UI}"; '
                f'font-size: {F.SZ_SM}pt; font-weight: 700; '
                f'letter-spacing: 1.2px; background: transparent;'
            )
            gbadge = QLabel(f"{len(items)}/{len(items)}")
            gbadge.setStyleSheet(f"""
                QLabel {{
                    background: {C.BG_LOW};
                    border: 1px solid {C.BORDER};
                    border-radius: 8px;
                    padding: 0 5px;
                    font-family: "{F.MONO}";
                    font-size: 7pt;
                    color: {C.TEXT_MUTED};
                }}
            """)
            ghl.addWidget(gname)
            ghl.addWidget(gbadge)
            ghl.addStretch()

            gall = QPushButton("All")
            gall.setCursor(Qt.CursorShape.PointingHandCursor)
            gall.setFlat(True)
            gall.setStyleSheet(f"""
                QPushButton {{
                    color: {C.OLIVE};
                    background: transparent;
                    border: none;
                    text-decoration: underline;
                    font-family: "{F.UI}";
                    font-size: {F.SZ_SM}pt;
                    font-weight: 700;
                    padding: 0;
                }}
                QPushButton:hover {{ color: {C.OLIVE_DK}; }}
            """)
            gall.clicked.connect(lambda _checked, g=gkey: self._group_toggle_all(g))
            ghl.addWidget(gall)
            self._samp_host_lay.addWidget(ghdr)

            # Cards grid (3 columns)
            grid_host = QWidget()
            grid_lay = QGridLayout(grid_host)
            grid_lay.setContentsMargins(0, 0, 0, 6)
            grid_lay.setHorizontalSpacing(5)
            grid_lay.setVerticalSpacing(5)

            for i, (idx, ctx) in enumerate(items):
                r, c = divmod(i, SAMPLE_COLS)
                card = _SampleCard(idx, ctx["label"], ctx["depth"], ctx["d50"])
                card.toggled.connect(self._on_sample_toggled)
                grid_lay.addWidget(card, r, c)
                self._sample_cards.append(card)
                ctx["group"] = gkey

            # Ensure last row fills evenly
            for c in range(SAMPLE_COLS):
                grid_lay.setColumnStretch(c, 1)

            self._samp_host_lay.addWidget(grid_host)

        # Apply existing search filter
        if hasattr(self, "_samp_search"):
            self._filter_samples(self._samp_search.text())
        self._refresh_meta_pills()

    def _on_sample_toggled(self, _index: int, _on: bool) -> None:
        self._refresh_meta_pills()
        self._save_report_settings()

    def _samp_bulk(self, value: bool) -> None:
        for c in self._sample_cards:
            if c.isVisible():
                c.set_on(value)
        self._refresh_meta_pills()

    def _samp_invert(self) -> None:
        for c in self._sample_cards:
            if c.isVisible():
                c.set_on(not c.is_on())
        self._refresh_meta_pills()

    def _group_toggle_all(self, group_key: str) -> None:
        cards_in_group = [
            c for c in self._sample_cards
            if self._sample_contexts[c.index()]["group"] == group_key
        ]
        all_on = all(c.is_on() for c in cards_in_group) if cards_in_group else False
        for c in cards_in_group:
            c.set_on(not all_on)
        self._refresh_meta_pills()

    def _filter_samples(self, query: str) -> None:
        q = (query or "").strip().lower()
        for c in self._sample_cards:
            show = (not q) or (q in c.sample_id().lower())
            c.setVisible(show)

    # ══════════════════════════════════════════════════════════
    # Brand / logo / metadata
    # ══════════════════════════════════════════════════════════

    def _pick_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo Image", "", "Images (*.png *.jpg *.jpeg *.svg)"
        )
        if path:
            self.brand.logo_path = path
            self.brand.save()
            self._refresh_logo_button()

    def _refresh_logo_button(self) -> None:
        if self.brand.logo_path and os.path.exists(self.brand.logo_path):
            self._logo_drop.setText(f"\u2713  {os.path.basename(self.brand.logo_path)}")
        else:
            self._logo_drop.setText("\u2B07   Upload logo (PNG, SVG) \u2014 click to browse")

    def _collect_brand(self) -> ReportBrand:
        # No in-UI editing of org/color — persist current values
        self.brand.save()
        return self.brand

    def _collect_metadata(self) -> dict:
        return {
            "project_name": self.project_name_edit.text(),
            "project_no":   self.project_no_edit.text(),
            "date":         self.date_edit.text(),
            "location":     self.location_edit.text(),  # hidden, kept for backend compat
            "client":       self.client_edit.text(),
            "analyst":      self.analyst_edit.text(),
            "notes":        self.notes_edit.toPlainText(),
        }

    def _collect_sections(self) -> dict:
        def on(key: str, default: bool = True) -> bool:
            row = self._section_rows.get(key)
            return row.is_checked() if row is not None else default
        return {
            "cover_page":        on("cover", False),
            "executive_summary": on("executive"),
            "methodology":       on("methodology"),
            "results":           on("results"),
            "plots":             on("plots"),
            "interpretation":    on("interp", False),
            "percentiles":       on("gradation"),  # concept merges percentiles under "Statistics"
            "gradation":         on("gradation"),
            "k_statistics":      on("k_stats"),
            "data_quality":      on("quality", False),
            "raw_data":          on("raw", False),
        }

    def _collect_appendix_label_config(self) -> dict:
        """Appendix labels are configured via stored settings only."""
        s = self._settings
        mode = s.value("appendix_labels/mode", "auto")
        layout = s.value("appendix_labels/layout", "separate")
        scheme = s.value("appendix_labels/scheme", "alpha")
        prefix = s.value("appendix_labels/prefix", "Appendix ")
        root = s.value("appendix_labels/alpha_numeric_root", "A")
        single_label = s.value("appendix_labels/single_label", "")

        if scheme in {"alpha", "numeric"} and prefix and not prefix[-1].isspace():
            prefix += " "

        manual_labels = {}
        if layout != "single":
            for src_key, dst_key in [
                ("appendix_labels/manual_percentiles", "grain_percentiles"),
                ("appendix_labels/manual_quality",     "grain_data_quality"),
                ("appendix_labels/manual_raw",         "grain_raw_data"),
            ]:
                val = (s.value(src_key, "") or "").strip()
                if val:
                    manual_labels[dst_key] = val

        return {
            "layout":              layout,
            "mode":                mode,
            "scheme":              scheme,
            "prefix":              prefix,
            "alpha_numeric_root":  (root or "A").strip() or "A",
            "single_label":        single_label,
            "manual_labels":       manual_labels,
        }

    # ══════════════════════════════════════════════════════════
    # Persistence
    # ══════════════════════════════════════════════════════════

    def _save_report_settings(self) -> None:
        if self._restoring_settings:
            return
        s = self._settings
        s.setValue("report/type_id", self._selected_type)
        s.setValue("report/template", self._template_combo.currentText())
        s.setValue("report/format", self._format_combo.currentText())
        s.setValue("report/language", self._language_combo.currentText())
        for key in self._section_rows:
            s.setValue(f"report/section_{key}", self._section_rows[key].is_checked())
        s.setValue("report/project_name", self.project_name_edit.text())
        s.setValue("report/project_no",   self.project_no_edit.text())
        s.setValue("report/date",         self.date_edit.text())
        s.setValue("report/client",       self.client_edit.text())
        s.setValue("report/analyst",      self.analyst_edit.text())
        s.setValue("report/notes",        self.notes_edit.toPlainText())

    def _load_report_settings(self) -> None:
        self._restoring_settings = True
        try:
            s = self._settings
            type_id = int(s.value("report/type_id", self.TYPE_COMPARISON))
            self._set_type_selection(type_id)

            template = s.value("report/template", "Standard")
            idx = self._template_combo.findText(template)
            if idx >= 0:
                self._template_combo.setCurrentIndex(idx)

            fmt = s.value("report/format", "PDF")
            idx = self._format_combo.findText(fmt)
            if idx >= 0:
                self._format_combo.setCurrentIndex(idx)

            lang = s.value("report/language", "English")
            idx = self._language_combo.findText(lang)
            if idx >= 0:
                self._language_combo.setCurrentIndex(idx)

            defaults = {
                "cover": False, "executive": True, "results": True, "plots": True,
                "k_stats": True, "gradation": True, "methodology": True,
                "raw": False, "interp": True, "quality": False,
            }
            for key, row in self._section_rows.items():
                default = defaults.get(key, True)
                row.set_checked(s.value(f"report/section_{key}", default, type=bool))

            self.project_name_edit.setText(s.value("report/project_name", ""))
            self.project_no_edit.setText(s.value("report/project_no", ""))
            self.date_edit.setText(s.value("report/date", ""))
            self.location_edit.setText(s.value("report/location", ""))
            self.client_edit.setText(s.value("report/client", ""))
            self.analyst_edit.setText(s.value("report/analyst", ""))
            self.notes_edit.setPlainText(s.value("report/notes", ""))

            self._refresh_logo_button()
        finally:
            self._restoring_settings = False
        self._refresh_meta_pills()
        self._update_outline()

    # ══════════════════════════════════════════════════════════
    # Preview output wrappers
    # ══════════════════════════════════════════════════════════

    def _set_preview_html(self, html: str) -> None:
        self.web_view.setHtml(html)

    def _set_report_output(self, report_html: str) -> None:
        self.current_report_html = report_html
        self._set_preview_html(self._inject_preview_css(report_html))
        self.btn_refresh.setEnabled(True)
        self.btn_print.setEnabled(HAS_WEBENGINE)
        self.btn_save.setEnabled(True)

    def _clear_report_output(self, message: Optional[str] = None) -> None:
        self.current_report_html = ""
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.setEnabled(bool(self.dataset_tabs))
            self.btn_print.setEnabled(False)
            self.btn_save.setEnabled(False)
        if hasattr(self, "web_view"):
            if message:
                self._set_preview_html(self._error_preview_html(message))
            else:
                self._set_preview_html(self._empty_preview_html())

    def _selected_sample_contexts(self) -> list[dict]:
        return [
            self._sample_contexts[c.index()]
            for c in self._sample_cards
            if c.is_on() and c.index() < len(self._sample_contexts)
        ]

    # ══════════════════════════════════════════════════════════
    # Generate report
    # ══════════════════════════════════════════════════════════

    def _on_generate(self) -> None:
        if not self.dataset_tabs:
            QMessageBox.warning(self, "No Data", "Please load datasets first.")
            return

        brand = self._collect_brand()
        metadata = self._collect_metadata()
        sections = self._collect_sections()
        appendix_cfg = self._collect_appendix_label_config()

        try:
            if self._selected_type == self.TYPE_INDIVIDUAL:
                html = self._gen_individual("Grain Size", brand, metadata, sections, appendix_cfg)
            elif self._selected_type == self.TYPE_KFOCUS:
                html = self._gen_individual("K-Values", brand, metadata, sections, appendix_cfg)
            elif self._selected_type == self.TYPE_FULL:
                html = self._gen_full(brand, metadata, sections)
            else:
                html = self._gen_comparison(brand, metadata, sections)
            self._set_report_output(html)
        except Exception as exc:
            self._clear_report_output(str(exc))
            QMessageBox.critical(self, "Report Error", f"Failed to generate report:\n{exc}")

    def _first_selected_context(self) -> Optional[dict]:
        selected = self._selected_sample_contexts()
        if selected:
            return selected[0]
        if self._sample_contexts:
            return self._sample_contexts[0]
        return None

    def _gen_individual(self, subtype: str, brand, metadata, sections, appendix_cfg) -> str:
        ctx = self._first_selected_context()
        if ctx is None:
            raise ValueError("No sample selected.")
        tab = ctx["tab"]
        dataset = tab.get_dataset()

        if subtype == "K-Values":
            return self.report_generator.generate_k_value_report(
                dataset, tab.get_results(), tab.temperature, tab.porosity,
                metadata=metadata, sections=sections, brand=brand,
            )
        return self.report_generator.generate_grain_size_report(
            dataset, metadata=metadata, sections=sections, brand=brand,
            appendix_label_config=appendix_cfg,
        )

    def _gen_comparison(self, brand, metadata, sections) -> str:
        selected = self._selected_sample_contexts()
        if not selected:
            raise ValueError("Select at least one sample.")

        sample_details = []
        for ctx in selected:
            tab = ctx["tab"]
            sample_details.append({
                "label":       ctx["label"],
                "dataset":     tab.get_dataset(),
                "k_results":   list(tab.get_results() or []),
                "temperature": tab.temperature,
                "porosity":    tab.porosity,
            })

        return self.report_generator.generate_comparison_report(
            [item["dataset"] for item in sample_details],
            metadata=metadata, sections=sections, brand=brand,
            sample_details=sample_details,
        )

    def _gen_full(self, brand, metadata, sections) -> str:
        if not self._sample_contexts:
            raise ValueError("No samples loaded.")
        sample_details = []
        for ctx in self._sample_contexts:
            tab = ctx["tab"]
            sample_details.append({
                "label":       ctx["label"],
                "dataset":     tab.get_dataset(),
                "k_results":   list(tab.get_results() or []),
                "temperature": tab.temperature,
                "porosity":    tab.porosity,
            })
        return self.report_generator.generate_comparison_report(
            [item["dataset"] for item in sample_details],
            metadata=metadata, sections=sections, brand=brand,
            sample_details=sample_details,
        )

    # ══════════════════════════════════════════════════════════
    # Preview-topbar actions
    # ══════════════════════════════════════════════════════════

    def _on_print(self) -> None:
        if not self.current_report_html or not HAS_WEBENGINE:
            return
        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dlg = QPrintDialog(printer, self)
            if dlg.exec() == QPrintDialog.DialogCode.Accepted:
                self.web_view.page().print(printer, lambda _ok: None)
        except Exception as exc:
            QMessageBox.critical(self, "Print Error", f"Failed to print:\n{exc}")

    def _on_save_primary(self) -> None:
        fmt = self._format_combo.currentText()
        if fmt == "PDF":
            self._on_export_pdf()
        elif fmt == "HTML":
            self._on_export_html()
        elif fmt == "Word (.docx)":
            self._on_export_docx()

    # ══════════════════════════════════════════════════════════
    # Export handlers
    # ══════════════════════════════════════════════════════════

    def _default_export_name(self, ext: str) -> str:
        proj = self.project_name_edit.text()
        if proj:
            safe = "".join(c for c in proj if c.isalnum() or c in " -_").strip()
            if safe:
                return f"{safe}_report.{ext}"
        return f"report.{ext}"

    def _on_export_html(self) -> None:
        if not self.current_report_html:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export HTML", self._default_export_name("html"), "HTML (*.html)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.current_report_html)
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    def _on_export_pdf(self) -> None:
        if not self.current_report_html or not HAS_WEBENGINE:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", self._default_export_name("pdf"), "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            layout = QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Portrait,
                QMarginsF(0, 0, 0, 0),
            )
            self.web_view.page().printToPdf(path, layout)
        except Exception as exc:
            QMessageBox.critical(self, "PDF Error", f"Failed to export PDF:\n{exc}")

    def _on_pdf_done(self, path: str, success: bool) -> None:
        if success:
            QMessageBox.information(self, "Exported", f"PDF saved to:\n{path}")
        else:
            QMessageBox.critical(self, "Export Error", "PDF export failed.")

    def _on_export_docx(self) -> None:
        if not self.current_report_html:
            return
        if not self.report_generator.docx_export_available():
            QMessageBox.warning(
                self, "DOCX Export Unavailable",
                "python-docx is not installed, so Word export is unavailable.",
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Word (.docx)", self._default_export_name("docx"),
            "Word Document (*.docx)",
        )
        if not path:
            return
        try:
            docx_bytes = self.report_generator.generate_docx_from_html(
                self.current_report_html, brand=self.brand,
            )
            with open(path, "wb") as fh:
                fh.write(docx_bytes)
        except Exception as exc:
            QMessageBox.critical(self, "DOCX Error", f"Failed to export Word file:\n{exc}")
            return
        QMessageBox.information(self, "Exported", f"Word document saved to:\n{path}")

    # ══════════════════════════════════════════════════════════
    # Preview HTML helpers (unchanged from prior version)
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def _inject_preview_css(html: str) -> str:
        """Inject screen-only CSS + JS that simulates an A4 paper sheet."""
        screen_block = """<style>
@media screen {
    html { background: #c8c4be !important; min-height: 100%; padding: 32px 0 48px 0; }
    body {
        box-shadow: 0 4px 28px rgba(0,0,0,0.22), 0 1.5px 6px rgba(0,0,0,0.10) !important;
        background: white !important;
        min-height: 297mm;
        width: 210mm;
        max-width: 210mm !important;
        margin: 0 auto !important;
        padding: 0 20mm !important;
        box-sizing: border-box !important;
    }
    .report-top-bar {
        margin: 0 -20mm 40px -20mm !important;
    }
    .preview-page-sep {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 40px;
        margin: 0 -20mm;
        background: #c8c4be;
        border-top:    1px solid #b0aba5;
        border-bottom: 1px solid #b0aba5;
        box-shadow: inset 0 4px 8px rgba(0,0,0,0.07),
                    inset 0 -4px 8px rgba(0,0,0,0.07);
        font-family: sans-serif;
        font-size: 9px;
        color: #9a9590;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
}
</style>
<script>
(function () {
    var PAGE_PX = 252 * 96 / 25.4;

    function isBreakCandidate(el) {
        if (!el || el.classList.contains('preview-page-sep')) return false;
        if (el.closest('table, thead, tbody, tr, td, th, ul, ol, li')) return false;
        var style = window.getComputedStyle(el);
        if (style.display === 'none' || style.position === 'fixed') return false;
        if (el.offsetHeight < 12) return false;
        return /^(H1|H2|H3|H4|P|DIV|HR|IMG|FIGURE|TABLE)$/.test(el.tagName);
    }

    function collectBreakCandidates() {
        var bodyTop = document.body.getBoundingClientRect().top;
        var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
        var candidates = [];

        while (walker.nextNode()) {
            var el = walker.currentNode;
            if (!isBreakCandidate(el)) continue;
            candidates.push({
                el: el,
                top: el.getBoundingClientRect().top - bodyTop
            });
        }

        candidates.sort(function (a, b) { return a.top - b.top; });
        return candidates;
    }

    function injectPageBreaks() {
        if (document.querySelector('.preview-page-sep')) return;

        var candidates = collectBreakCandidates();
        var bodyH = document.body.scrollHeight;
        var page = 1;
        var usedTargets = new Set();

        for (var boundary = PAGE_PX; boundary < bodyH; boundary += PAGE_PX) {
            var target = null;
            for (var i = 0; i < candidates.length; i++) {
                if (candidates[i].top >= boundary && !usedTargets.has(candidates[i].el)) {
                    target = candidates[i].el;
                    break;
                }
            }
            if (!target) continue;

            usedTargets.add(target);
            var sep = document.createElement('div');
            sep.className = 'preview-page-sep';
            sep.textContent = 'Page ' + (++page);
            target.insertAdjacentElement('beforebegin', sep);
        }
    }

    if (document.readyState === 'complete') { injectPageBreaks(); }
    else { window.addEventListener('load', injectPageBreaks); }
})();
</script>"""
        if "</head>" in html:
            return html.replace("</head>", screen_block + "\n</head>", 1)
        return screen_block + html

    @staticmethod
    def _empty_preview_html() -> str:
        return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
  body {
    font-family: 'Source Sans 3', 'Calibri', Arial, sans-serif;
    background: white;
    margin: 0;
    padding: 60px 50px;
    color: #9a8c78;
  }
  .center { text-align: center; padding-top: 80px; }
  h2 { font-weight: 300; font-size: 22px; margin-bottom: 12px; color: #5d4e37; }
  p  { font-size: 13px; }
  strong { color: #6b8e23; }
</style></head>
<body>
  <div class="center">
    <h2>No Report Generated</h2>
    <p>
      Configure options on the left, then click
      <strong>Generate Report</strong>.
    </p>
  </div>
</body></html>"""

    @staticmethod
    def _error_preview_html(message: str) -> str:
        safe = escape(message)
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
  body {{
    font-family: 'Source Sans 3', 'Calibri', Arial, sans-serif;
    background: white;
    margin: 0;
    padding: 60px 50px;
    color: #6a6a6a;
  }}
  .center {{ text-align: center; padding-top: 80px; }}
  h2 {{ font-weight: 400; font-size: 22px; margin-bottom: 12px; color: #7b2e2e; }}
  p  {{ font-size: 13px; line-height: 1.5; }}
  strong {{ color: #6b8e23; }}
  .msg {{
    margin: 18px auto 0;
    max-width: 520px;
    padding: 14px 16px;
    background: #faf7f4;
    border: 1px solid #ddd4ca;
    text-align: left;
    white-space: pre-wrap;
  }}
</style></head>
<body>
  <div class="center">
    <h2>Report Generation Failed</h2>
    <p>The preview was cleared so stale content cannot be exported.</p>
    <div class="msg">{safe}</div>
  </div>
</body></html>"""
