"""Reporting tab — accordion composer matching design_concepts/08_reports_composer.html."""
from __future__ import annotations

from html import escape
import os
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
from .plot_context import build_plot_context_from_tab
from report_generator import ReportGenerator
from grain_classification import ISO14688


# ═══════════════════════════════════════════════════════════════
# DESIGN TOKENS (local, derived from 08_reports_composer.html)
# ═══════════════════════════════════════════════════════════════

PANEL_W         = 360       # composer panel width
ACC_HDR_H       = 32        # accordion header height
TOGGLE_W        = 28
TOGGLE_H        = 15
GEN_BTN_H       = 33


# ─── icon helper ──────────────────────────────────────────────
def _icon_pixmap(fa_name: str, color: str, px: int) -> QPixmap:
    """Return a pixmap rendered from a qtawesome icon."""
    return theme_icon(fa_name, color=color, size=px).pixmap(QSize(px, px))


def _make_icon_label(fa_name: str, color: str, px: int = 14) -> QLabel:
    """QLabel pre-loaded with a qtawesome icon pixmap."""
    lbl = QLabel()
    lbl.setFixedSize(px, px)
    lbl.setPixmap(_icon_pixmap(fa_name, color, px))
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("background: transparent;")
    return lbl


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

    def __init__(self, fa_name: str, title: str, parent=None):
        super().__init__(parent)
        self._open = False
        self._fa_name = fa_name
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

        self._icon_lbl = _make_icon_label(fa_name, C.TEXT_MUTED, 14)
        self._icon_lbl.setObjectName("accIcon")

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("accTitle")

        self._meta_lbl = QLabel("")
        self._meta_lbl.setObjectName("accMeta")
        self._meta_lbl.setMinimumHeight(18)
        self._meta_lbl.setMaximumWidth(120)
        self._meta_lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        self._chev_lbl = _make_icon_label("fa6s.chevron-right", C.TEXT_MUTED, 11)
        self._chev_lbl.setObjectName("accChev")

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
        chev_name = "fa6s.chevron-down" if value else "fa6s.chevron-right"
        self._chev_lbl.setPixmap(_icon_pixmap(chev_name, C.OLIVE if value else C.TEXT_MUTED, 11))
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
        title_col = C.TEXT if self._open else C.TEXT_MID
        # Refresh the icon pixmap to reflect open/closed colour
        self._icon_lbl.setPixmap(_icon_pixmap(self._fa_name, icon_col, 14))
        self._hdr.setStyleSheet(f"""
            QWidget#accHdr {{
                background: {bg};
            }}
            QWidget#accHdr:hover {{
                background: {C.BG_RAISED};
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


# ═══════════════════════════════════════════════════════════════
# REPORT TYPE CARD (Section 1)
# ═══════════════════════════════════════════════════════════════

class _TypeCard(QFrame):
    """2×2 grid card for selecting report type."""

    clicked = pyqtSignal(int)

    def __init__(self, card_id: int, fa_name: str, label: str, desc: str, parent=None):
        super().__init__(parent)
        self._id = card_id
        self._on = False
        self._fa_name = fa_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{label} — {desc}")
        self.setFixedHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)

        self._icon = QLabel()
        self._icon.setObjectName("tcIcon")
        self._icon.setFixedSize(26, 26)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setPixmap(_icon_pixmap(fa_name, C.TEXT_MUTED, 15))

        self._lbl = QLabel(label)
        self._lbl.setObjectName("tcLbl")
        self._lbl.setWordWrap(True)
        self._lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        lay.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._lbl, 1, Qt.AlignmentFlag.AlignVCenter)

        self._apply_style()

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

        # Refresh icon pixmap to reflect selection colour
        self._icon.setPixmap(_icon_pixmap(self._fa_name, icon_c, 15))

        self.setStyleSheet(f"""
            _TypeCard {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 5px;
            }}
            QLabel#tcIcon {{
                background: {icon_bg};
                border: 1px solid {icon_bd};
                border-radius: 4px;
            }}
            QLabel#tcLbl {{
                color: {C.TEXT if self._on else C.TEXT_MID};
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                font-weight: 700;
                background: transparent;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# SECTION ROW (Section 3)
# ═══════════════════════════════════════════════════════════════

class _SectionRow(QFrame):
    """Toggleable section row: icon + label [+ required pill] + toggle."""

    toggled = pyqtSignal(bool)

    def __init__(self, fa_name: str, label: str, required: bool = False, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 0, 9, 0)
        lay.setSpacing(7)

        self._icon = _make_icon_label(fa_name, C.TEXT_MUTED, 13)

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
        ("cover",        "fa6s.file-lines",   "Cover Page",          True),
        ("executive",    "fa6s.align-left",   "Executive Summary",   False),
        ("results",      "fa6s.table",        "Sample & Grain Tables", False),
        ("plots",        "fa6s.chart-line",   "Report Plots",        False),
        ("k_stats",      "fa6s.bolt",         "K + Aggregate Tables", False),
        ("gradation",    "fa6s.chart-column", "Grain Statistics",    False),
        ("methodology",  "fa6s.book",         "Method References",   False),
    ]
    APPENDIX_KEYS = [
        ("raw",     "fa6s.table-list", "A \u2014 Raw Sieve Data"),
        ("interp",  "fa6s.chart-area", "B \u2014 Full-Size Plots"),
        ("quality", "fa6s.scroll",     "C \u2014 Method Details"),
    ]
    # Per-plot selection (key, icon, label, default-on). Keys match the export
    # plot-type vocabulary so reports and exports share one set of plot names.
    SINGLE_PLOT_KEYS = [
        ("grain_size_curve",      "fa6s.chart-line",   "Grain size distribution",     True),
        ("k_value_bar",           "fa6s.bolt",         "K-value bar chart",           True),
        ("applicability_heatmap", "fa6s.table-cells",  "Method applicability heatmap", False),
    ]
    COLLECTION_PLOT_KEYS = [
        ("distribution_overlay",  "fa6s.chart-area",   "Grain size comparison",       True),
        ("k_value_comparison",    "fa6s.bolt",         "K-value comparison (bars)",   True),
        ("statistical_boxplots",  "fa6s.chart-column", "K distribution (by scope)",   True),
        ("reliability_matrix",    "fa6s.table-cells",  "Method reliability matrix",   False),
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

    # Canonical presets per report type — defines the default section/appendix
    # state and the sample-table selection mode for each of the four built-in
    # report types. Clicking a type card re-applies this preset.
    TYPE_PRESETS = {
        TYPE_INDIVIDUAL: {
            "selection_mode": "single",
            "hint": "Pick one sample for the report.",
            "sections": {
                "cover": False, "executive": True, "results": True, "plots": True,
                "k_stats": True, "gradation": True, "methodology": True,
            },
            "appendices": {"raw": False, "interp": False, "quality": False},
        },
        TYPE_COMPARISON: {
            "selection_mode": "multi",
            "hint": "Pick two or more samples. Group/overall aggregates are included when K tables are enabled.",
            "sections": {
                "cover": False, "executive": True, "results": True, "plots": True,
                "k_stats": True, "gradation": True, "methodology": True,
            },
            "appendices": {"raw": False, "interp": False, "quality": False},
        },
        TYPE_FULL: {
            "selection_mode": "all",
            "hint": "All loaded samples are included with overall/group aggregate summaries.",
            "sections": {
                "cover": True, "executive": True, "results": True, "plots": True,
                "k_stats": True, "gradation": True, "methodology": True,
            },
            "appendices": {"raw": True, "interp": True, "quality": True},
        },
        TYPE_KFOCUS: {
            "selection_mode": "multi",
            "hint": "Pick samples for K tables, overall/group aggregates, and K distribution plots.",
            "sections": {
                "cover": False, "executive": True, "results": False, "plots": False,
                "k_stats": True, "gradation": True, "methodology": True,
            },
            "appendices": {"raw": False, "interp": False, "quality": False},
        },
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report_generator = ReportGenerator()
        self._scheme = ISO14688
        self.dataset_tabs: List = []
        self._sample_contexts: list[dict] = []
        self._sample_selected: list[bool] = []
        self._section_rows: dict[str, _SectionRow] = {}
        # Per-plot checkbox rows, keyed by scope ("single"/"collection") then key.
        self._plot_rows: dict[str, dict[str, _SectionRow]] = {"single": {}, "collection": {}}
        self._outline_items: list[tuple[QLabel, QLabel, bool]] = []  # (label, page, appendix?)
        self.current_report_html = ""
        self.brand = ReportBrand.load()
        self._settings = QSettings("GrainSizeAnalysis", "ReportingTab")
        self._restoring_settings = False
        self._selected_type = self.TYPE_COMPARISON
        self._selection_mode = "multi"  # "single" / "multi" / "all"

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
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(f"""
            QSplitter::handle:horizontal {{
                background: {C.BORDER};
                border-left: 1px solid {C.BORDER_DK};
                border-right: 1px solid {C.BORDER_DK};
                margin: 0;
            }}
            QSplitter::handle:horizontal:hover {{
                background: {C.OLIVE};
            }}
        """)

        # Left composer panel
        left = self._build_composer_panel()
        left.setMinimumWidth(340)
        left.setMaximumWidth(560)

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
        self._acc_type = _AccordionSection("fa6s.file-contract", "Report Type")
        self._build_type_section(self._acc_type.body_layout())
        blay.addWidget(self._acc_type)

        # Accordion 2: Samples
        self._acc_samples = _AccordionSection("fa6s.vial", "Samples")
        self._build_samples_section(self._acc_samples.body_layout())
        blay.addWidget(self._acc_samples)

        # Accordion 3: Sections & Appendices
        self._acc_sects = _AccordionSection("fa6s.list-check", "Sections & Appendices")
        self._build_sections_section(self._acc_sects.body_layout())
        blay.addWidget(self._acc_sects)

        # Accordion 4: Details & Branding
        self._acc_details = _AccordionSection("fa6s.sliders", "Details & Branding")
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
        alay.setContentsMargins(13, 10, 13, 8)
        alay.setSpacing(6)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        cards = [
            (self.TYPE_INDIVIDUAL, "fa6s.chart-area", "Individual Sample",
             "Full report for one sample \u2014 grain data, plot, K-values, statistics."),
            (self.TYPE_COMPARISON, "fa6s.code-compare", "Cross-Sample Comparison",
             "Side-by-side samples plus overall/group aggregate summaries."),
            (self.TYPE_FULL, "fa6s.book", "Full Project Summary",
             "All samples with aggregate tables, plots, and appendices."),
            (self.TYPE_KFOCUS, "fa6s.bolt", "K-Value Focus",
             "Hydraulic conductivity method tables and group aggregates."),
        ]
        self._type_cards: list[_TypeCard] = []
        for i, (cid, fa, label, desc) in enumerate(cards):
            card = _TypeCard(cid, fa, label, desc)
            card.clicked.connect(self._on_type_clicked)
            self._type_cards.append(card)
            grid.addWidget(card, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

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
        tlay.addWidget(self._samp_count_lbl)

        # Hint strip — shows the preset's sample-selection hint text
        hint_box = QWidget()
        hint_box.setStyleSheet(
            f"background: rgba(255,255,255,0.12); border-bottom: 1px solid {C.BORDER};"
        )
        hlay = QHBoxLayout(hint_box)
        hlay.setContentsMargins(12, 5, 12, 5)
        hlay.setSpacing(6)
        hlay.addWidget(_make_icon_label("fa6s.circle-info", C.TEXT_MUTED, 11))
        self._samp_hint_lbl = QLabel("Pick two or more samples to compare.")
        self._samp_hint_lbl.setStyleSheet(
            f'color: {C.TEXT_MUTED}; font-family: "{F.UI}"; '
            f'font-size: {F.SZ_XS}pt; background: transparent; border: none;'
        )
        hlay.addWidget(self._samp_hint_lbl, 1)

        # Links row
        links = QWidget()
        links.setStyleSheet(f"background: rgba(255,255,255,0.12); border-bottom: 1px solid {C.BORDER};")
        self._samp_links_box = links
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

        # Sample table
        self._samp_table = QTableWidget(0, 3)
        self._samp_table.setHorizontalHeaderLabels(["", "Sample", "d\u2085\u2080"])
        self._samp_table.verticalHeader().setVisible(False)
        self._samp_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._samp_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._samp_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._samp_table.setShowGrid(False)
        self._samp_table.setAlternatingRowColors(True)
        self._samp_table.setMinimumHeight(180)
        self._samp_table.setMaximumHeight(320)
        self._samp_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        hh = self._samp_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._samp_table.setColumnWidth(0, 28)
        self._samp_table.verticalHeader().setDefaultSectionSize(24)

        self._samp_table.setStyleSheet(f"""
            QTableWidget {{
                background: rgba(255,255,255,0.45);
                border: none;
                border-top: 1px solid {C.BORDER};
                gridline-color: {C.BORDER};
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                color: {C.TEXT};
                alternate-background-color: rgba(255,255,255,0.22);
            }}
            QTableWidget::item {{
                padding: 2px 6px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background: rgba(107,142,35,0.18);
                color: {C.TEXT};
            }}
            QHeaderView::section {{
                background: {C.BG_LOW};
                color: {C.TEXT_MUTED};
                font-family: "{F.UI}";
                font-size: {F.SZ_XS}pt;
                font-weight: 700;
                padding: 4px 6px;
                border: none;
                border-bottom: 1px solid {C.BORDER};
            }}
            QTableCornerButton::section {{
                background: {C.BG_LOW};
                border: none;
            }}
        """)
        self._samp_table.itemChanged.connect(self._on_table_item_changed)
        self._table_updating = False

        alay.addWidget(tbar)
        alay.addWidget(hint_box)
        alay.addWidget(links)
        alay.addWidget(self._samp_table)

        lay.addWidget(area)

    # ── Section 3: Sections & Appendices ──────────────────────
    def _build_sections_section(self, lay: QVBoxLayout):
        area = QWidget()
        area.setStyleSheet(f"background: {C.BG_RAISED};")
        alay = QVBoxLayout(area)
        alay.setContentsMargins(13, 10, 13, 13)
        alay.setSpacing(3)

        # Main sections
        alay.addWidget(self._uc_header_with_icon("fa6s.list-ul", "MAIN SECTIONS"))

        for key, fa, label, required in self.SECTION_KEYS:
            row = _SectionRow(fa, label, required=required)
            row.toggled.connect(lambda _v, k=key: self._on_section_toggled(k))
            self._section_rows[key] = row
            alay.addWidget(row)

        # Per-plot selection (contextual: single-sample vs comparison plots)
        self._plots_header = self._uc_header_with_icon(
            "fa6s.images", "PLOTS TO INCLUDE", top_margin=12
        )
        alay.addWidget(self._plots_header)
        for scope, specs in (
            ("single", self.SINGLE_PLOT_KEYS),
            ("collection", self.COLLECTION_PLOT_KEYS),
        ):
            for key, fa, label, default_on in specs:
                row = _SectionRow(fa, label)
                row.set_checked(default_on)
                self._plot_rows[scope][key] = row
                alay.addWidget(row)
        self._sync_plot_rows_visibility()

        # Appendices
        alay.addWidget(self._uc_header_with_icon("fa6s.paperclip", "APPENDICES", top_margin=12))

        for key, fa, label in self.APPENDIX_KEYS:
            row = _SectionRow(fa, label)
            row.set_checked(False)  # appendices default off
            row.toggled.connect(lambda _v, k=key: self._on_section_toggled(k))
            self._section_rows[key] = row
            alay.addWidget(row)

        # Live outline box
        outline = QFrame()
        outline.setObjectName("outlineFrame")
        outline.setFrameShape(QFrame.Shape.StyledPanel)
        outline.setStyleSheet(f"""
            QFrame#outlineFrame {{
                background: rgba(255,255,255,0.45);
                border: 1px solid {C.BORDER};
                border-radius: 6px;
            }}
        """)
        olay = QVBoxLayout(outline)
        olay.setContentsMargins(0, 0, 0, 0)
        olay.setSpacing(0)

        ohdr_box = QWidget()
        ohdr_box.setObjectName("outlineHdr")
        ohdr_box.setStyleSheet(f"""
            QWidget#outlineHdr {{
                background: {C.BG_LOW};
                border-bottom: 1px solid {C.BORDER};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
        """)
        ohlay = QHBoxLayout(ohdr_box)
        ohlay.setContentsMargins(10, 6, 10, 6)
        ohlay.setSpacing(6)
        ohlay.addWidget(_make_icon_label("fa6s.list-ul", C.TEXT_MUTED, 12))
        ohdr_lbl = QLabel("DOCUMENT OUTLINE")
        ohdr_lbl.setStyleSheet(
            f'color: {C.TEXT_MUTED}; font-family: "{F.UI}"; '
            f'font-size: {F.SZ_SM}pt; font-weight: 700; '
            f'letter-spacing: 1.5px; background: transparent; border: none;'
        )
        ohlay.addWidget(ohdr_lbl)
        ohlay.addStretch()
        olay.addWidget(ohdr_box)

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

        self._logo_drop = QPushButton("  Upload logo (PNG, SVG) \u2014 click to browse")
        self._logo_drop.setIcon(theme_icon("fa6s.upload", C.TEXT_MUTED, 14))
        self._logo_drop.setIconSize(QSize(14, 14))
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

        self.generate_btn = QPushButton("  Generate Report")
        self.generate_btn.setIcon(theme_icon("fa6s.bolt", "#ffffff", 14))
        self.generate_btn.setIconSize(QSize(14, 14))
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

        def pbtn(label: str, fa_name: str, handler):
            b = QPushButton(label)
            b.setIcon(theme_icon(fa_name, C.TEXT_MID, 13))
            b.setIconSize(QSize(13, 13))
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

        self.btn_refresh = pbtn(" Refresh", "fa6s.rotate",       self._on_generate)
        self.btn_print   = pbtn(" Print",   "fa6s.print",        self._on_print)
        self.btn_save    = pbtn(" Save",    "fa6s.floppy-disk",  self._on_save_primary)
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
    def _uc_header_with_icon(self, fa_name: str, label: str, top_margin: int = 0) -> QWidget:
        """Uppercase section header with a leading qtawesome icon + bottom border."""
        box = QWidget()
        box.setStyleSheet(
            f"background: transparent; border-bottom: 1px solid {C.BORDER};"
            f"{'margin-top:' + str(top_margin) + 'px;' if top_margin else ''}"
        )
        h = QHBoxLayout(box)
        h.setContentsMargins(0, top_margin, 0, 4)
        h.setSpacing(7)
        h.addWidget(_make_icon_label(fa_name, C.TEXT_MUTED, 12))
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f'color: {C.TEXT_MUTED}; font-family: "{F.UI}"; '
            f'font-size: {F.SZ_SM}pt; font-weight: 700; '
            f'letter-spacing: 1.5px; background: transparent; border: none;'
        )
        h.addWidget(lbl)
        h.addStretch()
        return box

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
        self._apply_type_preset(card_id)
        self._save_report_settings()
        self._refresh_meta_pills()
        self._update_outline()

    def _set_type_selection(self, card_id: int) -> None:
        self._selected_type = card_id
        for card in getattr(self, "_type_cards", []):
            card.set_on(card._id == card_id)
        self._sync_plot_rows_visibility()

    def _sync_plot_rows_visibility(self) -> None:
        """Show single-sample plot rows for an Individual report, comparison
        plot rows for the multi-sample report types."""
        if not getattr(self, "_plot_rows", None):
            return
        single = self._selected_type == self.TYPE_INDIVIDUAL
        for row in self._plot_rows.get("single", {}).values():
            row.setVisible(single)
        for row in self._plot_rows.get("collection", {}).values():
            row.setVisible(not single)

    def _apply_type_preset(self, type_id: int) -> None:
        """Apply the canonical section/appendix state + selection mode for a type."""
        preset = self.TYPE_PRESETS.get(type_id)
        if not preset:
            return

        # Apply sections without triggering save-on-toggle cascade
        self._restoring_settings = True
        try:
            for key, val in preset["sections"].items():
                row = self._section_rows.get(key)
                if row is not None:
                    row.set_checked(val)
            for key, val in preset["appendices"].items():
                row = self._section_rows.get(key)
                if row is not None:
                    row.set_checked(val)
        finally:
            self._restoring_settings = False

        self._apply_selection_mode(preset["selection_mode"])
        if hasattr(self, "_samp_hint_lbl"):
            self._samp_hint_lbl.setText(preset["hint"])

    def _apply_selection_mode(self, mode: str) -> None:
        """Enforce the sample-table behavior for a given selection mode."""
        self._selection_mode = mode
        total = len(self._sample_contexts)

        if mode == "all":
            # Lock every row to checked
            self._sample_selected = [True] * total
        elif mode == "single":
            # Keep first currently-checked row, uncheck the rest
            kept = False
            for i in range(total):
                if self._sample_selected[i] and not kept:
                    kept = True
                else:
                    self._sample_selected[i] = False
            if not kept and total > 0:
                self._sample_selected[0] = True
        # multi: leave as-is

        # Toggle visibility of bulk-action links
        show_links = (mode == "multi")
        if hasattr(self, "_samp_links_box"):
            self._samp_links_box.setVisible(show_links)

        if hasattr(self, "_samp_table"):
            self._rebuild_sample_table()

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

    def _is_modified_from_preset(self) -> bool:
        """True when the current section/appendix state diverges from the
        preset for the currently selected report type."""
        preset = self.TYPE_PRESETS.get(self._selected_type)
        if not preset:
            return False
        for key, expected in preset["sections"].items():
            row = self._section_rows.get(key)
            if row is not None and row.is_checked() != expected:
                return True
        for key, expected in preset["appendices"].items():
            row = self._section_rows.get(key)
            if row is not None and row.is_checked() != expected:
                return True
        return False

    def _refresh_meta_pills(self) -> None:
        type_name = self._type_short_name(self._selected_type)
        fmt_name = self._format_combo.currentText() if hasattr(self, "_format_combo") else "PDF"
        # Compact format label for meta pill
        fmt_short = {"Word (.docx)": "DOCX"}.get(fmt_name, fmt_name)
        is_mod = self._is_modified_from_preset()
        type_pill = f"{type_name}*" if is_mod else type_name
        self._acc_type.set_meta(f"{type_pill} \u00B7 {fmt_short}")

        total = len(self._sample_contexts)
        sel = sum(1 for v in self._sample_selected if v)
        self._acc_samples.set_meta(f"{sel}/{total}" if total else "none")
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
        if app_on:
            self._acc_sects.set_meta(f"{main_on}\u00A0sec \u00B7 {app_on}\u00A0app")
        else:
            self._acc_sects.set_meta(f"{main_on}\u00A0sections")

        self._acc_details.set_meta("Project info")

        modified = " · Modified" if self._is_modified_from_preset() else ""
        self._gen_summary_lbl.setText(
            f"{type_name} · {sel} sample{'s' if sel != 1 else ''} · {fmt_name}{modified}"
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
            "PDF":          " Save PDF",
            "HTML":         " Save HTML",
            "Word (.docx)": " Save Word",
        }.get(fmt, " Save")
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
        self._sample_selected: list[bool] = []
        self._clear_report_output()

        if not self.dataset_tabs:
            self._rebuild_sample_table()
            self.generate_btn.setEnabled(False)
            self._refresh_meta_pills()
            return

        labels = self._build_unique_labels([t.get_dataset_name() for t in self.dataset_tabs])
        for tab, label in zip(self.dataset_tabs, labels):
            context = {
                "label": label,
                "tab": tab,
                "d50":   self._format_d50(tab),
            }
            self._sample_contexts.append(context)
            self._sample_selected.append(True)

        # Honour the active selection-mode for the freshly loaded samples
        self._apply_selection_mode(self._selection_mode)
        self.generate_btn.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self._refresh_meta_pills()

    @staticmethod
    def _format_d50(tab) -> str:
        try:
            d50 = tab.get_dataset().get_d50()
        except Exception:
            d50 = None
        if d50 is None:
            return "d\u2085\u2080 —"
        return f"d\u2085\u2080 {d50:.2f} mm"

    def _rebuild_sample_table(self) -> None:
        self._table_updating = True
        try:
            self._samp_table.clearContents()
            self._samp_table.setRowCount(len(self._sample_contexts))

            locked = (self._selection_mode == "all")

            for row, ctx in enumerate(self._sample_contexts):
                # Column 0 — checkbox
                chk = QTableWidgetItem()
                if locked:
                    # Show as checked but not user-toggleable
                    chk.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    chk.setCheckState(Qt.CheckState.Checked)
                else:
                    chk.setFlags(
                        Qt.ItemFlag.ItemIsUserCheckable
                        | Qt.ItemFlag.ItemIsEnabled
                    )
                    chk.setCheckState(
                        Qt.CheckState.Checked if self._sample_selected[row]
                        else Qt.CheckState.Unchecked
                    )
                chk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._samp_table.setItem(row, 0, chk)

                def _make(text: str, *, mono: bool = False, muted: bool = False) -> QTableWidgetItem:
                    it = QTableWidgetItem(text)
                    it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    if mono:
                        font = it.font()
                        font.setFamily(F.MONO)
                        it.setFont(font)
                    if muted:
                        it.setForeground(QColor(C.TEXT_MUTED))
                    return it

                self._samp_table.setItem(row, 1, _make(ctx["label"], mono=True))
                self._samp_table.setItem(row, 2, _make(ctx["d50"]))

            # Apply existing search filter
            if hasattr(self, "_samp_search"):
                self._filter_samples(self._samp_search.text())
        finally:
            self._table_updating = False
        self._refresh_meta_pills()

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._table_updating or item.column() != 0:
            return
        row = item.row()
        if not (0 <= row < len(self._sample_selected)):
            return
        now_checked = (item.checkState() == Qt.CheckState.Checked)

        if self._selection_mode == "single" and now_checked:
            # Radio-like: unchecking all other rows
            self._table_updating = True
            try:
                for other in range(len(self._sample_selected)):
                    if other == row:
                        self._sample_selected[other] = True
                    else:
                        self._sample_selected[other] = False
                        other_item = self._samp_table.item(other, 0)
                        if other_item is not None and other_item.checkState() != Qt.CheckState.Unchecked:
                            other_item.setCheckState(Qt.CheckState.Unchecked)
            finally:
                self._table_updating = False
        elif self._selection_mode == "single" and not now_checked:
            # In single mode the user cannot deselect the only choice —
            # force the row back on.
            self._table_updating = True
            try:
                item.setCheckState(Qt.CheckState.Checked)
                self._sample_selected[row] = True
            finally:
                self._table_updating = False
        else:
            self._sample_selected[row] = now_checked

        self._refresh_meta_pills()
        self._save_report_settings()

    def _set_row_checked(self, row: int, value: bool) -> None:
        item = self._samp_table.item(row, 0)
        if item is None:
            return
        new_state = Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
        if item.checkState() != new_state:
            item.setCheckState(new_state)
        self._sample_selected[row] = value

    def _samp_bulk(self, value: bool) -> None:
        self._table_updating = True
        try:
            for row in range(self._samp_table.rowCount()):
                if not self._samp_table.isRowHidden(row):
                    self._set_row_checked(row, value)
        finally:
            self._table_updating = False
        self._refresh_meta_pills()
        self._save_report_settings()

    def _samp_invert(self) -> None:
        self._table_updating = True
        try:
            for row in range(self._samp_table.rowCount()):
                if not self._samp_table.isRowHidden(row):
                    self._set_row_checked(row, not self._sample_selected[row])
        finally:
            self._table_updating = False
        self._refresh_meta_pills()
        self._save_report_settings()

    def _filter_samples(self, query: str) -> None:
        q = (query or "").strip().lower()
        for row, ctx in enumerate(self._sample_contexts):
            self._samp_table.setRowHidden(row, bool(q) and q not in ctx["label"].lower())

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
            self._logo_drop.setIcon(theme_icon("fa6s.check", C.OLIVE, 14))
            self._logo_drop.setText(f"  {os.path.basename(self.brand.logo_path)}")
        else:
            self._logo_drop.setIcon(theme_icon("fa6s.upload", C.TEXT_MUTED, 14))
            self._logo_drop.setText("  Upload logo (PNG, SVG) \u2014 click to browse")

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
        # Put the sample table into the mode that matches the loaded type
        preset = self.TYPE_PRESETS.get(self._selected_type)
        if preset is not None:
            self._apply_selection_mode(preset["selection_mode"])
            if hasattr(self, "_samp_hint_lbl"):
                self._samp_hint_lbl.setText(preset["hint"])
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
            ctx for ctx, on in zip(self._sample_contexts, self._sample_selected) if on
        ]

    def _generation_validation_error(self) -> Optional[tuple[str, str]]:
        if not self.dataset_tabs:
            return ("No Data", "Please load datasets first.")

        sel_count = sum(1 for v in self._sample_selected if v)
        type_id = self._selected_type
        if type_id == self.TYPE_INDIVIDUAL and sel_count != 1:
            return (
                "Select One Sample",
                "Individual Sample reports require exactly one selected sample.",
            )
        if type_id == self.TYPE_COMPARISON and sel_count < 2:
            return (
                "Select At Least Two Samples",
                "Cross-Sample Comparison reports need two or more samples selected.",
            )
        if type_id == self.TYPE_KFOCUS and sel_count < 1:
            return (
                "Select A Sample",
                "K-Value Focus reports need at least one sample selected.",
            )
        return None

    # ══════════════════════════════════════════════════════════
    # Generate report
    # ══════════════════════════════════════════════════════════

    def _on_generate(self) -> None:
        validation_error = self._generation_validation_error()
        if validation_error is not None:
            title, message = validation_error
            self._clear_report_output(message)
            QMessageBox.warning(self, title, message)
            return

        type_id = self._selected_type
        brand = self._collect_brand()
        metadata = self._collect_metadata()
        sections = self._collect_sections()
        appendix_cfg = self._collect_appendix_label_config()

        try:
            if type_id == self.TYPE_INDIVIDUAL:
                html = self._gen_individual("Grain Size", brand, metadata, sections, appendix_cfg)
            elif type_id == self.TYPE_KFOCUS:
                # K-Focus is multi-sample → route through the comparison generator
                html = self._gen_comparison(brand, metadata, sections)
            elif type_id == self.TYPE_FULL:
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
        plot_context = build_plot_context_from_tab(tab, self._scheme)
        return self.report_generator.generate_grain_size_report(
            dataset, metadata=metadata, sections=sections, brand=brand,
            appendix_label_config=appendix_cfg,
            plot_context=plot_context,
            k_results=list(tab.get_results() or []),
            selected_plots=self._collect_selected_plots("single"),
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
                "plot_context": build_plot_context_from_tab(tab, self._scheme),
            })

        return self.report_generator.generate_comparison_report(
            [item["dataset"] for item in sample_details],
            metadata=metadata, sections=sections, brand=brand,
            sample_details=sample_details,
            selected_plots=self._collect_selected_plots("collection"),
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
                "plot_context": build_plot_context_from_tab(tab, self._scheme),
            })
        return self.report_generator.generate_comparison_report(
            [item["dataset"] for item in sample_details],
            metadata=metadata, sections=sections, brand=brand,
            sample_details=sample_details,
            selected_plots=self._collect_selected_plots("collection"),
        )

    def _collect_selected_plots(self, scope: str) -> set:
        """Return the chosen plot-type keys for the given report scope.

        Reads the per-plot checkboxes when present; otherwise falls back to the
        defaults (distribution + K/comparison plots ON, heatmap/matrix OFF).
        """
        defaults = {
            "single": {"grain_size_curve", "k_value_bar"},
            "collection": {"distribution_overlay", "k_value_comparison", "statistical_boxplots"},
        }.get(scope, set())
        rows = getattr(self, "_plot_rows", {}).get(scope)
        if not rows:
            return set(defaults)
        return {key for key, row in rows.items() if row.is_checked()}

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
        """Inject screen-only CSS that previews the report on a clean A4 sheet."""
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
}
</style>"""
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
