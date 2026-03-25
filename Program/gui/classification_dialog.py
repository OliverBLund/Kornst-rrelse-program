"""
classification_dialog.py
========================
4-tab Classification System dialog matching design_concepts/07_classification.html

Tabs
----
0  Scheme      — card-style scheme picker (ISO 14688 / USCS / Custom)
1  Boundaries  — read-only boundary table + log-scale zone preview
2  Custom      — editable boundaries, import/export JSON
3  References  — static reference tables with standard links

Emits
-----
scheme_selected(GrainClassificationScheme)  when the user clicks Apply
"""
from __future__ import annotations

import json
import math

from PyQt6.QtCore    import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui     import (QColor, QPainter, QBrush, QPen, QFont,
                              QLinearGradient, QDesktopServices)
from PyQt6.QtCore    import QUrl
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QFrame, QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QDoubleSpinBox, QFileDialog,
    QMessageBox, QSizePolicy,
)

from grain_classification import (
    GrainClassificationScheme, ClassificationResult,
    ISO14688, USCS, SCHEMES, make_custom_scheme,
)
from gui.theme import C, F, SZ, icon
from qt_chrome.frameless_dialog_mixin import FramelessDialogMixin


# ─────────────────────────────────────────────────────────────────────────────
# SHARED STYLES
# ─────────────────────────────────────────────────────────────────────────────

_CARD_BASE = (
    f"QWidget#schemeCard {{ background: white; border: 2px solid {C.BORDER}; "
    f"border-radius: 6px; }}"
    f"QWidget#schemeCard:hover {{ border-color: {C.BORDER_DK}; "
    f"background: {C.BG_RAISED}; }}"
)
_CARD_ON = (
    f"QWidget#schemeCard {{ background: rgba(107,142,35,0.04); "
    f"border: 2px solid {C.OLIVE}; border-radius: 6px; }}"
)

_ZONE_COLORS = {
    "Clay":   C.GC_CLAY,
    "Silt":   C.GC_SILT,
    "Sand":   C.GC_SAND,
    "Gravel": C.GC_GRAVEL,
    "Cobble": C.GC_COBBLE,
}
_ZONE_TEXT_DARK = {"Sand"}   # classes that need dark text


# ─────────────────────────────────────────────────────────────────────────────
# ZONE PREVIEW BAR  (QPainter-based, used in Boundaries tab)
# ─────────────────────────────────────────────────────────────────────────────

class _ZonePreviewBar(QWidget):
    """Log-scale zone preview bar — drawn with QPainter.

    Pass show_axis=True to draw tick marks and grain-size labels below the bar.
    """

    _LOG_MIN = math.log10(0.0001)
    _LOG_MAX = math.log10(200.0)
    _BAR_H   = 32
    _AXIS_H  = 20   # tick (5px) + gap (2px) + label text (13px)
    _TICK_MM = [0.001, 0.002, 0.010, 0.063, 0.100, 0.500, 2.0, 10.0, 63.0]

    def __init__(self, scheme: GrainClassificationScheme, *,
                 show_axis: bool = False,
                 hide_cobble: bool = False,
                 range_labels: bool = False,
                 parent=None):
        super().__init__(parent)
        self._scheme = scheme
        self._show_axis = show_axis
        self._hide_cobble = hide_cobble
        self._range_labels = range_labels
        if show_axis:
            self.setFixedHeight(self._BAR_H + self._AXIS_H)
        else:
            self.setMinimumHeight(self._BAR_H)
            self.setMaximumHeight(36)

    def set_scheme(self, scheme: GrainClassificationScheme):
        self._scheme = scheme
        self.update()

    def _log_frac(self, mm: float) -> float:
        """Map mm value to [0,1] on log axis."""
        lv = math.log10(max(mm, 1e-6))
        return (lv - self._LOG_MIN) / (self._LOG_MAX - self._LOG_MIN)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self._scheme
        w = self.width()
        bar_h = self._BAR_H

        zones = [
            ("Clay",   0.0001,       s.clay_max,   None,          s.clay_max),
            ("Silt",   s.clay_max,   s.silt_max,   s.clay_max,    s.silt_max),
            ("Sand",   s.silt_max,   s.sand_max,   s.silt_max,    s.sand_max),
            ("Gravel", s.sand_max,   s.gravel_max, s.sand_max,    s.gravel_max),
            ("Cobble", s.gravel_max, 200.0,        s.gravel_max,  None),
        ]

        for i, (name, lo, hi, rng_lo, rng_hi) in enumerate(zones):
            if self._hide_cobble and name == "Cobble":
                # Extend Gravel to the full width instead
                continue
            x0 = self._log_frac(lo) * w
            # For Gravel when hiding Cobble, extend to full width
            if self._hide_cobble and name == "Gravel":
                x1 = float(w)
            else:
                x1 = self._log_frac(hi) * w
            seg_px = x1 - x0
            color = QColor(_ZONE_COLORS.get(name, "#aaaaaa"))
            p.fillRect(int(x0), 0, max(1, int(x1 - x0)), bar_h, color)

            txt_color = QColor("#5a3800") if name in _ZONE_TEXT_DARK else QColor("#ffffff")
            p.setPen(txt_color)

            if self._range_labels and seg_px > 100 and rng_lo is not None and rng_hi is not None:
                # Show "Name (lo–hi mm)"
                p.setFont(QFont(F.MONO, 7))
                label = f"{name} ({rng_lo:g}–{rng_hi:g} mm)"
                p.drawText(QRectF(x0 + 2, 0, seg_px - 4, bar_h),
                           Qt.AlignmentFlag.AlignCenter, label)
            elif seg_px > 28:
                p.setFont(QFont(F.MONO, 8))
                p.drawText(QRectF(x0, 0, seg_px, bar_h),
                           Qt.AlignmentFlag.AlignCenter, name)

        # Bar border
        p.setPen(QPen(QColor(C.BORDER), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(0, 0, w - 1, bar_h - 1, 3, 3)

        # Axis ticks + labels
        if self._show_axis:
            tick_top = bar_h + 2
            tick_bot = tick_top + 5
            p.setFont(QFont(F.MONO, 7))
            for mm in self._TICK_MM:
                x = int(self._log_frac(mm) * w)
                # tick
                p.setPen(QPen(QColor(C.BORDER_DK), 1))
                p.drawLine(x, tick_top, x, tick_bot)
                # label
                if mm < 0.01:
                    lbl = f"{mm:.3f}"
                elif mm < 1.0:
                    lbl = f"{mm:.3f}".rstrip('0')
                elif mm < 10:
                    lbl = f"{mm:.1f}"
                else:
                    lbl = f"{mm:.0f}"
                p.setPen(QColor(C.TEXT_MUTED))
                p.drawText(
                    QRectF(x - 18, tick_bot + 1, 36, 13),
                    Qt.AlignmentFlag.AlignCenter,
                    lbl,
                )

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# SCHEME CARD
# ─────────────────────────────────────────────────────────────────────────────

class _SchemeCard(QFrame):
    """Clickable scheme selection card."""

    clicked = pyqtSignal()

    def __init__(self, scheme: GrainClassificationScheme, selected: bool = False,
                 parent=None):
        super().__init__(parent)
        self._scheme = scheme
        self._selected = selected
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build()
        self._refresh_style()

    @property
    def scheme(self) -> GrainClassificationScheme:
        return self._scheme

    def set_selected(self, val: bool):
        self._selected = val
        self._refresh_style()
        self._check_lbl.setVisible(val)

    def _refresh_style(self):
        is_custom = self._scheme.key == "custom"
        border_style = "dashed" if is_custom else "solid"
        if self._selected:
            self.setStyleSheet(
                f"QFrame {{ background: rgba(107,142,35,0.05); "
                f"border: 2px {border_style} {C.OLIVE}; border-radius: 6px; }}")
        else:
            self.setStyleSheet(
                f"QFrame {{ background: white; border: 2px {border_style} {C.BORDER}; "
                f"border-radius: 6px; }}"
                f"QFrame:hover {{ border-color: {C.BORDER_DK}; "
                f"background: {C.BG_RAISED}; }}")

    def _build(self):
        s = self._scheme
        is_custom = s.key == "custom"

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(6)

        # ── Header row ──
        hdr = QHBoxLayout()
        hdr.setSpacing(10)

        emoji = QLabel("🇪🇺" if s.key == "iso14688" else
                       "🇺🇸" if s.key == "uscs" else "✏️")
        emoji.setFixedSize(38, 38)
        emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emoji.setStyleSheet(
            f"background: {C.BG_LOW}; border: 1px solid {C.BORDER}; "
            f"border-radius: 5px; font-size: 18px;")
        hdr.addWidget(emoji)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        name_lbl = QLabel(s.name)
        name_lbl.setFont(QFont(F.UI, F.SZ_LG, QFont.Weight.DemiBold))
        name_lbl.setStyleSheet(f"color: {C.TEXT}; background: transparent; border: none;")
        title_col.addWidget(name_lbl)

        ref_row = QHBoxLayout()
        ref_row.setSpacing(4)
        ref_row.setContentsMargins(0, 0, 0, 0)
        ref_icon = QLabel()
        try:
            fa_name = 'fa6s.pen-ruler' if is_custom else 'fa6s.link'
            ref_icon.setPixmap(icon(fa_name, C.TEXT_MUTED).pixmap(10, 10))
        except Exception:
            ref_icon.setText("🔗" if not is_custom else "✏")
        ref_icon.setStyleSheet("background: transparent; border: none;")
        ref_row.addWidget(ref_icon)
        ref_lbl = QLabel(s.standard_ref)
        ref_lbl.setFont(QFont(F.MONO, F.SZ_XS))
        ref_lbl.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent; border: none;")
        if s.url:
            ref_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            def _open_ref(ev, u=s.url):
                if ev.button() == Qt.MouseButton.LeftButton:
                    QDesktopServices.openUrl(QUrl(u))
            ref_lbl.mousePressEvent = _open_ref
        ref_row.addWidget(ref_lbl)
        ref_row.addStretch()
        title_col.addLayout(ref_row)
        hdr.addLayout(title_col, 1)

        # Check mark
        self._check_lbl = QLabel()
        try:
            self._check_lbl.setPixmap(icon('fa6s.check', C.OLIVE).pixmap(12, 12))
        except Exception:
            self._check_lbl.setText("✓")
        self._check_lbl.setStyleSheet("background: transparent; border: none;")
        self._check_lbl.setVisible(self._selected)
        hdr.addWidget(self._check_lbl)
        root.addLayout(hdr)

        # ── Description ──
        if is_custom:
            desc = ("Define your own grain-size boundaries. Useful for project-specific "
                    "or non-standard classification. Configure in the Custom tab.")
        elif s.key == "iso14688":
            desc = (f"European and Danish standard. Used with Eurocode 7 and Danish "
                    f"geotechnical practice. Clay &lt; {s.clay_max} mm · "
                    f"Silt {s.clay_max}–{s.silt_max} mm · Sand {s.silt_max}–{s.sand_max} mm · "
                    f"Gravel {s.sand_max}–{s.gravel_max} mm. "
                    f"<b>Recommended primary scheme for this tool.</b>")
        else:
            desc = (f"US standard, widely used internationally and in the empirical "
                    f"K-formula literature (Hazen, Beyer, Terzaghi etc.). "
                    f"Clay &lt; {s.clay_max} mm · Silt {s.clay_max}–{s.silt_max} mm · "
                    f"Sand {s.silt_max}–{s.sand_max} mm · Gravel {s.sand_max}–{s.gravel_max} mm. "
                    f"Provides USCS symbol codes (GW, SP, etc.).")
        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setTextFormat(Qt.TextFormat.RichText)
        desc_lbl.setFont(QFont(F.UI, F.SZ_SM))
        desc_lbl.setStyleSheet(f"color: {C.TEXT_MID}; background: transparent; border: none;")
        root.addWidget(desc_lbl)

        # ── Zone preview bar (4 zones: no Cobble, range labels in wider segments) ──
        if not is_custom:
            bar = _ZonePreviewBar(s, hide_cobble=True, range_labels=True)
            bar.setFixedHeight(22)
            root.addWidget(bar)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFICATION DIALOG
# ─────────────────────────────────────────────────────────────────────────────

class ClassificationDialog(FramelessDialogMixin, QDialog):
    """4-tab Classification System dialog."""

    scheme_selected = pyqtSignal(object)   # GrainClassificationScheme

    def __init__(self, current_scheme: GrainClassificationScheme = None,
                 custom_scheme: GrainClassificationScheme = None,
                 parent=None):
        super().__init__(parent)
        self._current  = current_scheme or ISO14688
        self._pending  = self._current       # scheme being previewed before Apply
        self._custom   = custom_scheme or make_custom_scheme(
            "My Custom Scheme", 0.002, 0.063, 2.0, 63.0)

        self.setWindowTitle("Classification System")
        self.setMinimumWidth(700)
        self.setMinimumHeight(560)
        self.resize(720, 580)
        self.init_frameless_dialog_chrome(corner_radius_px=8)
        self._build()
        self.bind_frameless_drag_widget(self._header_widget)

    # ── Build ──────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header_widget = self._make_header()
        root.addWidget(self._header_widget)

        # Tab bar + pages
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            f"QTabBar::tab {{ padding: 8px 18px; font-size: {F.SZ_LG}pt; "
            f"color: {C.TEXT_MUTED}; border-bottom: 2px solid transparent; "
            f"background: {C.BG_LOW}; border-right: 1px solid {C.BORDER}; }}"
            f"QTabBar::tab:selected {{ color: {C.OLIVE}; "
            f"border-bottom-color: {C.OLIVE}; background: {C.BG}; font-weight: 600; }}"
            f"QTabBar::tab:hover {{ color: {C.TEXT_MID}; background: {C.BG_RAISED}; }}"
            f"QTabWidget::pane {{ border: none; border-top: 1px solid {C.BORDER}; }}"
        )

        try:
            self._tabs.addTab(self._make_scheme_tab(),     icon('fa6s.list-check', C.TEXT_MUTED),     "  Scheme  ")
            self._tabs.addTab(self._make_boundaries_tab(), icon('fa6s.ruler-horizontal', C.TEXT_MUTED), "  Boundaries  ")
            self._tabs.addTab(self._make_custom_tab(),     icon('fa6s.pen-ruler', C.TEXT_MUTED),      "  Custom β  ")
            self._tabs.addTab(self._make_references_tab(), icon('fa6s.book-open', C.TEXT_MUTED),      "  References  ")
        except Exception:
            self._tabs.addTab(self._make_scheme_tab(),     "  Scheme  ")
            self._tabs.addTab(self._make_boundaries_tab(), "  Boundaries  ")
            self._tabs.addTab(self._make_custom_tab(),     "  Custom β  ")
            self._tabs.addTab(self._make_references_tab(), "  References  ")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs, 1)

        # Footer
        root.addWidget(self._make_footer())

    def _make_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        icon_box = QWidget()
        icon_box.setFixedSize(30, 30)
        icon_box.setStyleSheet(
            f"background: rgba(107,142,35,.12); border: 1px solid rgba(107,142,35,.25); "
            f"border-radius: {SZ.BORDER_RADIUS}px;")
        ib_lay = QHBoxLayout(icon_box)
        ib_lay.setContentsMargins(0, 0, 0, 0)
        ic = QLabel()
        try:
            ic.setPixmap(icon('fa6s.layer-group', C.OLIVE).pixmap(13, 13))
        except Exception:
            ic.setText("⊞")
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("background: transparent;")
        ib_lay.addWidget(ic)
        lay.addWidget(icon_box)

        tx = QVBoxLayout()
        tx.setSpacing(1)
        title = QLabel("Classification System")
        title.setFont(QFont(F.DISP, F.SZ_XL))
        title.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        sub = QLabel("Grain-size boundaries · Standard scheme · Custom thresholds")
        sub.setFont(QFont(F.MONO, F.SZ_XS))
        sub.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
        tx.addWidget(title)
        tx.addWidget(sub)
        lay.addLayout(tx, 1)

        close_btn = QPushButton()
        close_btn.setFixedSize(26, 26)
        try:
            close_btn.setIcon(icon('fa6s.xmark', C.TEXT_MUTED))
        except Exception:
            close_btn.setText("✕")
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; border-radius: 3px; }}"
            f"QPushButton:hover {{ background: rgba(180,48,32,.1); color: #a03020; }}")
        close_btn.clicked.connect(self.reject)
        lay.addWidget(close_btn)
        return w

    def _make_footer(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(
            f"background: {C.BG_RAISED}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(7)

        self._footer_active = QLabel()
        self._footer_active.setFont(QFont(F.MONO, F.SZ_XS))
        self._footer_active.setStyleSheet(
            f"color: {C.TEXT_MUTED}; background: transparent;")
        self._update_footer_label()
        lay.addWidget(self._footer_active, 1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(28)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
            f"background: {C.BG}; color: {C.TEXT_MID}; padding: 0 14px; font-size: {F.SZ_LG}pt; }}"
            f"QPushButton:hover {{ background: {C.BG_RAISED}; border-color: {C.BORDER_DK}; }}")
        cancel_btn.clicked.connect(self.reject)
        lay.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply Scheme")
        apply_btn.setFixedHeight(28)
        apply_btn.setStyleSheet(
            f"QPushButton {{ background: {C.OLIVE}; border: 1px solid {C.OLIVE_DK}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; color: white; font-weight: 600; "
            f"padding: 0 14px; font-size: {F.SZ_LG}pt; }}"
            f"QPushButton:hover {{ background: {C.OLIVE_H}; }}")
        try:
            apply_btn.setIcon(icon('fa6s.check', '#ffffff'))
        except Exception:
            pass
        apply_btn.clicked.connect(self._apply)
        lay.addWidget(apply_btn)
        return w

    def _update_footer_label(self):
        self._footer_active.setText(
            f"Active: {self._pending.name}")

    # ── Tab 0: Scheme ──────────────────────────────────────────────────────

    def _make_scheme_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet(f"background: {C.BG};")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self._scheme_cards: list[_SchemeCard] = []

        schemes_to_show = [ISO14688, USCS, self._custom]
        for s in schemes_to_show:
            card = _SchemeCard(s, selected=(s.key == self._pending.key))
            card.clicked.connect(lambda c=card: self._on_card_clicked(c))
            self._scheme_cards.append(card)
            lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(container)
        return scroll

    def _on_card_clicked(self, card: _SchemeCard):
        for c in self._scheme_cards:
            c.set_selected(c is card)
        self._pending = card.scheme
        self._update_footer_label()
        self._refresh_boundaries_tab()

    # ── Tab 1: Boundaries ─────────────────────────────────────────────────

    def _make_boundaries_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {C.BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)

        # Info note (icon + label in a styled container)
        bnd_note_wrap = QWidget()
        bnd_note_wrap.setStyleSheet(
            f"background: rgba(107,142,35,.07); border: 1px solid rgba(107,142,35,.22); "
            f"border-radius: 5px;")
        bnd_note_h = QHBoxLayout(bnd_note_wrap)
        bnd_note_h.setContentsMargins(10, 8, 12, 8)
        bnd_note_h.setSpacing(8)
        bnd_note_icon = QLabel()
        try:
            bnd_note_icon.setPixmap(icon('fa6s.circle-info', C.OLIVE).pixmap(13, 13))
        except Exception:
            bnd_note_icon.setText("ℹ")
        bnd_note_icon.setStyleSheet("background: transparent; border: none;")
        bnd_note_icon.setFixedWidth(14)
        bnd_note_icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        bnd_note_h.addWidget(bnd_note_icon)
        self._bnd_note = QLabel()
        self._bnd_note.setWordWrap(True)
        self._bnd_note.setFont(QFont(F.UI, F.SZ_SM))
        self._bnd_note.setStyleSheet(f"color: {C.TEXT_MID}; background: transparent; border: none;")
        bnd_note_h.addWidget(self._bnd_note, 1)
        lay.addWidget(bnd_note_wrap)

        # Boundary table
        self._bnd_table = QTableWidget(5, 4)
        self._bnd_table.setHorizontalHeaderLabels(["Class", "Range", "Upper (mm)", ""])
        self._bnd_table.verticalHeader().setVisible(False)
        self._bnd_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._bnd_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._bnd_table.setAlternatingRowColors(True)
        self._bnd_table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {C.BORDER}; border-radius: 5px; "
            f"background: white; font-size: {F.SZ_SM}pt; }}"
            f"QHeaderView::section {{ background: {C.BG_RAISED}; padding: 5px 10px; "
            f"font-weight: 600; border-bottom: 1px solid {C.BORDER}; font-size: {F.SZ_SM}pt; }}"
            f"QTableWidget::item {{ padding: 5px 10px; }}"
        )
        hdr = self._bnd_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed);  self._bnd_table.setColumnWidth(0, 90)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed);  self._bnd_table.setColumnWidth(2, 110)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed);  self._bnd_table.setColumnWidth(3, 80)
        lay.addWidget(self._bnd_table)

        # Zone preview bar
        preview_wrap = QFrame()
        preview_wrap.setStyleSheet(
            f"QFrame {{ border: 1px solid {C.BORDER}; border-radius: 5px; "
            f"background: white; }}")
        pw_lay = QVBoxLayout(preview_wrap)
        pw_lay.setContentsMargins(10, 8, 10, 10)
        pw_lay.setSpacing(6)
        hdr_row = QHBoxLayout()
        hdr_lbl = QLabel("Zone preview")
        hdr_lbl.setFont(QFont(F.UI, F.SZ_XS, QFont.Weight.DemiBold))
        hdr_lbl.setStyleSheet(
            f"color: {C.TEXT_MUTED}; background: transparent; "
            "letter-spacing: .06em; text-transform: uppercase;")
        scale_lbl = QLabel("log scale · grain size axis (mm)")
        scale_lbl.setFont(QFont(F.MONO, F.SZ_XS))
        scale_lbl.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()
        hdr_row.addWidget(scale_lbl)
        pw_lay.addLayout(hdr_row)

        self._bnd_preview = _ZonePreviewBar(self._pending, show_axis=True)
        pw_lay.addWidget(self._bnd_preview)
        lay.addWidget(preview_wrap)
        lay.addStretch()

        self._refresh_boundaries_tab()
        return w

    def _refresh_boundaries_tab(self):
        s = self._pending
        is_custom = s.key == "custom"
        locked_txt = "Custom" if is_custom else s.name.split("/")[0].strip()

        self._bnd_note.setText(
            f"Currently showing boundaries for <b>{s.name}</b>. "
            + ("These values are editable — switch to this scheme and adjust in the "
               "Custom tab." if is_custom else
               "These values are locked for standard schemes. Switch to "
               "<em>Custom</em> to define your own."))

        rows = [
            ("Clay",   f"0 – {s.clay_max} mm",             s.clay_max),
            ("Silt",   f"{s.clay_max} – {s.silt_max} mm",  s.silt_max),
            ("Sand",   f"{s.silt_max} – {s.sand_max} mm",  s.sand_max),
            ("Gravel", f"{s.sand_max} – {s.gravel_max} mm", s.gravel_max),
            ("Cobble", f"> {s.gravel_max} mm",              None),
        ]
        for i, (name, rng, upper) in enumerate(rows):
            # Swatch
            swatch = QWidget()
            swatch.setFixedSize(12, 12)
            swatch.setStyleSheet(
                f"background: {_ZONE_COLORS.get(name, '#aaa')}; border-radius: 2px;")
            cell_w = QWidget()
            cell_h = QHBoxLayout(cell_w)
            cell_h.setContentsMargins(8, 0, 0, 0)
            cell_h.addWidget(swatch)
            cell_h.addWidget(QLabel(name))
            cell_h.addStretch()
            self._bnd_table.setCellWidget(i, 0, cell_w)

            self._bnd_table.setItem(i, 1, QTableWidgetItem(rng))
            mm_item = QTableWidgetItem(f"{upper:.4g} mm" if upper is not None else "—")
            mm_item.setFont(QFont(F.MONO, F.SZ_SM))
            mm_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._bnd_table.setItem(i, 2, mm_item)

            lock_item = QTableWidgetItem("" if is_custom else f"🔒 {locked_txt}")
            lock_item.setFont(QFont(F.MONO, F.SZ_XS))
            lock_item.setForeground(QColor(C.TEXT_MUTED))
            self._bnd_table.setItem(i, 3, lock_item)

        if hasattr(self, '_bnd_preview'):
            self._bnd_preview.set_scheme(s)

    # ── Tab 2: Custom ─────────────────────────────────────────────────────

    def _make_custom_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        w = QWidget()
        w.setStyleSheet(f"background: {C.BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)

        # Warning note (icon + label in a styled container)
        warn_wrap = QWidget()
        warn_wrap.setStyleSheet(
            f"background: rgba(196,160,80,.08); border: 1px solid rgba(196,160,80,.28); "
            f"border-radius: 5px;")
        warn_h = QHBoxLayout(warn_wrap)
        warn_h.setContentsMargins(10, 8, 12, 8)
        warn_h.setSpacing(8)
        warn_icon = QLabel()
        try:
            warn_icon.setPixmap(icon('fa6s.triangle-exclamation', '#c4a030').pixmap(13, 13))
        except Exception:
            warn_icon.setText("⚠")
        warn_icon.setStyleSheet("background: transparent; border: none;")
        warn_icon.setFixedWidth(14)
        warn_icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        warn_h.addWidget(warn_icon)
        warn = QLabel(
            "<b>Custom schemes</b> are not tied to any published standard. "
            "Results will be labelled <em>\u201cCustom\u201d</em> in reports and exports. "
            "Use with care in professional deliverables.")
        warn.setWordWrap(True)
        warn.setFont(QFont(F.UI, F.SZ_SM))
        warn.setStyleSheet(f"color: {C.TEXT_MID}; background: transparent; border: none;")
        warn_h.addWidget(warn, 1)
        lay.addWidget(warn_wrap)

        # Name field
        name_row = QHBoxLayout()
        name_lbl = QLabel("Scheme name:")
        name_lbl.setFont(QFont(F.UI, F.SZ_MD))
        name_lbl.setStyleSheet(f"color: {C.TEXT_MID}; background: transparent;")
        self._custom_name = QLineEdit(self._custom.name)
        self._custom_name.setFixedHeight(28)
        self._custom_name.setStyleSheet(
            f"border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
            f"background: white; font-size: {F.SZ_MD}pt; padding: 0 8px;")
        name_row.addWidget(name_lbl)
        name_row.addWidget(self._custom_name, 1)
        lay.addLayout(name_row)

        # Boundary editors
        editor = QFrame()
        editor.setStyleSheet(
            f"QFrame {{ border: 1px solid {C.BORDER}; border-radius: 5px; background: white; }}")
        ed_lay = QVBoxLayout(editor)
        ed_lay.setContentsMargins(0, 0, 0, 0)
        ed_lay.setSpacing(0)

        # Header
        hdr_w = QWidget()
        hdr_w.setStyleSheet(f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER};")
        hdr_h = QHBoxLayout(hdr_w)
        hdr_h.setContentsMargins(14, 7, 14, 7)
        for txt, w_px in [("Class", 80), ("Name", 120), ("Upper boundary (mm)", 0)]:
            l = QLabel(txt)
            l.setFont(QFont(F.UI, F.SZ_XS, QFont.Weight.DemiBold))
            l.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
            if w_px:
                l.setFixedWidth(w_px)
            hdr_h.addWidget(l)
        hdr_h.addStretch()
        ed_lay.addWidget(hdr_w)

        self._custom_spins: dict[str, QDoubleSpinBox] = {}
        self._custom_name_edits: dict[str, QLineEdit] = {}
        defaults = {
            "Clay":   self._custom.clay_max,
            "Silt":   self._custom.silt_max,
            "Sand":   self._custom.sand_max,
            "Gravel": self._custom.gravel_max,
        }
        for row_i, (cls_key, default_val) in enumerate(defaults.items()):
            row_w = QWidget()
            row_w.setStyleSheet(
                f"background: {'white' if row_i % 2 == 0 else C.BG_RAISED}; "
                f"border-bottom: 1px solid {C.BORDER};")
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(14, 7, 14, 7)
            row_h.setSpacing(10)

            swatch = QWidget()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(
                f"background: {_ZONE_COLORS.get(cls_key, '#aaa')}; border-radius: 3px;")
            row_h.addWidget(swatch)

            name_edit = QLineEdit(cls_key)
            name_edit.setFixedSize(110, 24)
            name_edit.setStyleSheet(
                f"border: 1px solid {C.BORDER}; border-radius: 3px; "
                f"background: white; font-size: {F.SZ_SM}pt; padding: 0 5px;")
            self._custom_name_edits[cls_key] = name_edit
            row_h.addWidget(name_edit)

            row_h.addStretch(1)

            spin = QDoubleSpinBox()
            spin.setRange(0.0001, 500.0)
            spin.setSingleStep(0.01)
            spin.setDecimals(4)
            spin.setValue(default_val)
            spin.setFixedWidth(100)
            spin.setSuffix(" mm")
            spin.setStyleSheet(
                f"border: 1px solid {C.BORDER}; border-radius: 3px; "
                f"background: white; font-size: {F.SZ_SM}pt; font-family: '{F.MONO}';")
            self._custom_spins[cls_key] = spin
            row_h.addWidget(spin)
            ed_lay.addWidget(row_w)

        lay.addWidget(editor)

        # Action buttons
        btn_row = QHBoxLayout()
        import_btn = QPushButton("Import from file")
        export_btn = QPushButton("Export scheme")
        try:
            import_btn.setIcon(icon('fa6s.file-import', C.TEXT_MID))
            export_btn.setIcon(icon('fa6s.file-export', C.TEXT_MID))
        except Exception:
            pass
        for b, slot in [(import_btn, self._import_custom), (export_btn, self._export_custom)]:
            b.setFixedHeight(26)
            b.setStyleSheet(
                f"QPushButton {{ border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
                f"background: {C.BG}; color: {C.TEXT_MID}; padding: 0 12px; font-size: {F.SZ_SM}pt; }}"
                f"QPushButton:hover {{ background: {C.BG_RAISED}; }}")
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addStretch()

        scroll.setWidget(w)
        return scroll

    def _build_custom_scheme(self) -> GrainClassificationScheme:
        return make_custom_scheme(
            name       = self._custom_name.text() or "Custom",
            clay_max   = self._custom_spins["Clay"].value(),
            silt_max   = self._custom_spins["Silt"].value(),
            sand_max   = self._custom_spins["Sand"].value(),
            gravel_max = self._custom_spins["Gravel"].value(),
        )

    def _import_custom(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Custom Scheme", "", "JSON files (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self._custom_name.setText(data.get("name", "Imported"))
            for cls_key, spin_key in [("clay_max", "Clay"), ("silt_max", "Silt"),
                                       ("sand_max", "Sand"), ("gravel_max", "Gravel")]:
                if cls_key in data:
                    self._custom_spins[spin_key].setValue(float(data[cls_key]))
        except Exception as exc:
            QMessageBox.warning(self, "Import failed", str(exc))

    def _export_custom(self):
        s = self._build_custom_scheme()
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Custom Scheme", f"{s.name}.json", "JSON files (*.json)")
        if not path:
            return
        data = {
            "name": s.name, "key": "custom",
            "clay_max": s.clay_max, "silt_max": s.silt_max,
            "sand_max": s.sand_max, "gravel_max": s.gravel_max,
        }
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    # ── Tab 3: References ─────────────────────────────────────────────────

    def _make_references_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        w = QWidget()
        w.setStyleSheet(f"background: {C.BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)

        def _make_swatch_cell(color_hex: str) -> QWidget:
            wrap = QWidget()
            wrap.setStyleSheet("background: transparent;")
            h = QHBoxLayout(wrap)
            h.setContentsMargins(6, 0, 2, 0)
            h.setSpacing(0)
            dot = QWidget()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"background: {color_hex}; border-radius: 2px; border: none;")
            h.addWidget(dot)
            h.addStretch()
            return wrap

        def _ref_card(title: str, ref_links: list, desc: str,
                      col_headers: list, rows: list) -> QFrame:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ border: 1px solid {C.BORDER}; border-radius: 6px; "
                f"background: white; }}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)

            # Header
            hdr = QWidget()
            hdr.setStyleSheet(
                f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER}; "
                "border-top-left-radius: 6px; border-top-right-radius: 6px;")
            hh = QHBoxLayout(hdr)
            hh.setContentsMargins(14, 9, 14, 9)
            hh.setSpacing(8)

            book_ic = QLabel()
            try:
                book_ic.setPixmap(icon('fa6s.book', C.OLIVE).pixmap(13, 13))
            except Exception:
                book_ic.setText("📖")
            book_ic.setStyleSheet("background: transparent; border: none;")
            hh.addWidget(book_ic)

            t_lbl = QLabel(title)
            t_lbl.setFont(QFont(F.UI, F.SZ_LG, QFont.Weight.DemiBold))
            t_lbl.setStyleSheet(f"color: {C.TEXT}; background: transparent; border: none;")
            hh.addWidget(t_lbl)
            hh.addStretch()

            if ref_links:
                parts = " · ".join(
                    f'<a href="{u}" style="color:{C.OLIVE};text-decoration:none;">{t}</a>'
                    for t, u in ref_links)
                r_lbl = QLabel(parts)
                r_lbl.setOpenExternalLinks(True)
                r_lbl.setFont(QFont(F.MONO, F.SZ_XS))
                r_lbl.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent; border: none;")
                hh.addWidget(r_lbl)
            cl.addWidget(hdr)

            # Body
            body_w = QWidget()
            body_w.setStyleSheet("background: white;")
            body_lay = QVBoxLayout(body_w)
            body_lay.setContentsMargins(14, 10, 14, 12)
            body_lay.setSpacing(8)

            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setFont(QFont(F.UI, F.SZ_SM))
            desc_lbl.setStyleSheet(
                f"color: {C.TEXT_MID}; background: transparent; border: none;")
            body_lay.addWidget(desc_lbl)

            # Table — swatch + data columns
            n_data_cols = len(col_headers)
            tbl = QTableWidget(len(rows), n_data_cols + 1)
            tbl.setHorizontalHeaderLabels([""] + col_headers)
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            tbl.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
            tbl.setAlternatingRowColors(False)
            tbl.setShowGrid(False)
            tbl.setStyleSheet(
                f"QTableWidget {{ border: 1px solid {C.BORDER}; border-radius: 5px; "
                f"background: white; font-size: {F.SZ_SM}pt; gridline-color: {C.BG_RAISED}; }}"
                f"QHeaderView::section {{ background: {C.BG_RAISED}; padding: 4px 8px; "
                f"font-size: {F.SZ_XS}pt; font-weight: 600; color: {C.TEXT_MID}; "
                f"border-bottom: 1px solid {C.BORDER}; border-right: none; }}"
                f"QTableWidget::item {{ padding: 4px 8px; "
                f"border-bottom: 1px solid {C.BG_RAISED}; }}")

            hv = tbl.horizontalHeader()
            hv.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            tbl.setColumnWidth(0, 22)
            hv.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            for col in range(2, n_data_cols + 1):
                hv.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                tbl.setColumnWidth(col, 88 if col < n_data_cols else 110)

            ROW_H = 26
            tbl.verticalHeader().setDefaultSectionSize(ROW_H)
            tbl.setFixedHeight(
                len(rows) * ROW_H + tbl.horizontalHeader().sizeHint().height() + 4)

            for ri, (color_hex, *cells) in enumerate(rows):
                tbl.setCellWidget(ri, 0, _make_swatch_cell(color_hex))
                for ci, cell_text in enumerate(cells):
                    item = QTableWidgetItem(cell_text)
                    # mm columns (2, 3) use mono font + muted color
                    if 1 <= ci <= 2:
                        item.setFont(QFont(F.MONO, F.SZ_SM))
                        item.setForeground(QColor(C.TEXT_MID))
                    elif ci == 0:
                        item.setFont(QFont(F.UI, F.SZ_SM, QFont.Weight.Medium))
                        item.setForeground(QColor(C.TEXT))
                    else:
                        item.setFont(QFont(F.MONO, F.SZ_SM))
                        item.setForeground(QColor(C.TEXT_MUTED))
                    tbl.setItem(ri, ci + 1, item)

            body_lay.addWidget(tbl)
            cl.addWidget(body_w)
            return card

        # ── ISO 14688 ──
        lay.addWidget(_ref_card(
            "ISO 14688 / DS/EN ISO 14688",
            [("ISO 14688-1:2017", ISO14688.url), ("ISO 14688-2:2017", ISO14688.url)],
            "International standard for geotechnical soil identification and classification. "
            "Adopted as the Danish national standard (DS/EN ISO 14688). "
            "Recommended for European and Danish projects.",
            ["Class", "Lower (mm)", "Upper (mm)", "Note"],
            [
                (C.GC_CLAY,   "Clay (Cl)",   "–",     "0.002", "Fine-grained"),
                (C.GC_SILT,   "Silt (Si)",   "0.002", "0.063", "Fine-grained"),
                (C.GC_SAND,   "Sand (Sa)",   "0.063", "2.0",   "Coarse-grained"),
                (C.GC_GRAVEL, "Gravel (Gr)", "2.0",   "63.0",  "Coarse-grained"),
                (C.GC_COBBLE, "Cobble (Co)", "63.0",  "200",   ""),
            ],
        ))

        # ── USCS ──
        lay.addWidget(_ref_card(
            "USCS — ASTM D2487-17",
            [("ASTM D2487-17", USCS.url)],
            "Unified Soil Classification System. US standard used globally. "
            "The empirical hydraulic conductivity formulas in this program "
            "(Hazen, Beyer, Terzaghi, Kozeny-Carman etc.) originate in this tradition. "
            "Adds gradation symbols GW/GP/GM/GC/SW/SP/SM/SC using Cu and Cc criteria.",
            ["Class", "Lower (mm)", "Upper (mm)", "Cu (well-graded)"],
            [
                (C.GC_CLAY,   "Clay",        "–",     "0.002", "–"),
                (C.GC_SILT,   "Silt (M)",    "0.002", "0.075", "–"),
                (C.GC_SAND,   "Sand (S)",    "0.075", "4.75",  "≥ 6"),
                (C.GC_GRAVEL, "Gravel (G)",  "4.75",  "75.0",  "≥ 4"),
            ],
        ))

        # ── Limitation note ──
        lim_wrap = QWidget()
        lim_wrap.setStyleSheet(
            f"background: rgba(196,160,80,.08); border: 1px solid rgba(196,160,80,.25); "
            f"border-radius: 5px;")
        lim_h = QHBoxLayout(lim_wrap)
        lim_h.setContentsMargins(10, 10, 12, 10)
        lim_h.setSpacing(8)
        lim_icon = QLabel()
        try:
            lim_icon.setPixmap(icon('fa6s.triangle-exclamation', '#a07820').pixmap(13, 13))
        except Exception:
            lim_icon.setText("⚠")
        lim_icon.setStyleSheet("background: transparent; border: none;")
        lim_icon.setFixedWidth(14)
        lim_icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        lim_h.addWidget(lim_icon)
        lim = QLabel(
            "<b>Limitation:</b> Classification of fine-grained soils (silt vs clay) "
            "from grain size data alone is an approximation. A rigorous USCS classification "
            "of fine-grained soils requires Atterberg limit tests (plasticity index, liquid "
            "limit). This program cannot determine ML/MH/CL/CH symbols without that data.")
        lim.setWordWrap(True)
        lim.setFont(QFont(F.UI, F.SZ_SM))
        lim.setStyleSheet(f"color: {C.TEXT_MID}; background: transparent; border: none;")
        lim_h.addWidget(lim, 1)
        lay.addWidget(lim_wrap)
        lay.addStretch()

        scroll.setWidget(w)
        return scroll

    # ── Tab change ─────────────────────────────────────────────────────────

    def _on_tab_changed(self, idx: int):
        if idx == 1:
            self._refresh_boundaries_tab()

    # ── Apply ──────────────────────────────────────────────────────────────

    def _apply(self):
        if self._pending.key == "custom":
            self._pending = self._build_custom_scheme()
            self._custom = self._pending
        self._current = self._pending
        self.scheme_selected.emit(self._current)
        self.accept()

    # ── Public helpers ────────────────────────────────────────────────────

    @property
    def selected_scheme(self) -> GrainClassificationScheme:
        return self._current

    @property
    def custom_scheme(self) -> GrainClassificationScheme:
        return self._custom
