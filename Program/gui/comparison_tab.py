"""
comparison_tab.py — Multi-dataset comparison tab for Grain Size Analyser.

Provides side-by-side comparison of grain size parameters, hydraulic
conductivity estimates, and statistical summaries for 2+ datasets.

Layout:
    ┌─ Header bar (44px) ───────────────────────────────────────────┐
    │  "Comparison"   N datasets   [spacer]  [Update]  [Export…]    │
    └───────────────────────────────────────────────────────────────┘
    ┌─ QTabWidget ──────────────────────────────────────────────────┐
    │  [Plot] [Details] [Statistics]                                 │
    └───────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import math
import numpy as np
from typing import Optional, List

from matplotlib.figure import Figure

# ── PyQt6 ─────────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QSizePolicy, QFileDialog, QFrame, QStackedWidget, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QFont, QBrush, QPixmap, QPainter, QIcon, QFontMetrics

# ── Internal ──────────────────────────────────────────────────────────────────
from .matplotlib_canvas import FigureCanvas
from .comparison_plot_widget import ComparisonPlotWidget
from .dataset_selection_dialog import DatasetSelectionDialog
from .stack_fade import TabFadeInController
from .theme import C, F, icon as theme_icon
from k_calculations_v2 import CalculationStatus
from unit_conversions import HydraulicConductivityUnit, HydraulicConductivityConverter, get_default_plot_unit
from grain_classification import (
    ISO14688,
    interpolate_at as _interpolate_at,
    cu_label as _gc_cu_label,
    permeability_class as _gc_perm_class,
)


def _dot_icon(color_hex: str, size: int = 8) -> QIcon:
    """Create a small filled-circle QIcon in the given hex color."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color_hex))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.end()
    return QIcon(pix)


class _SortableTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem with explicit sort-role precedence."""

    def __lt__(self, other):
        lhs = self.data(Qt.ItemDataRole.UserRole)
        rhs = other.data(Qt.ItemDataRole.UserRole) if other is not None else None
        if lhs is not None and rhs is not None:
            try:
                return lhs < rhs
            except TypeError:
                return str(lhs) < str(rhs)
        return super().__lt__(other)


# ── Dataset color palette (warm-earth, consistent with design spec) ────────────
DATASET_COLORS: List[str] = [
    '#3a7ea0', '#6b8e23', '#b46428', '#2a9d8f',
    '#8b4513', '#c45c2e', '#4a6fa5', '#5e7b1a',
    '#8b6914', '#2e6b7d',
]


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────

def _get_fines_pct(dataset, scheme=None) -> Optional[float]:
    """Return % passing at scheme.silt_max (default ISO 0.063 mm) via log-linear interpolation.

    Uses grain_classification.interpolate_at for the shared algorithm.
    Returns None if there are fewer than 2 data points.
    """
    sizes = list(dataset.particle_sizes)
    pcts = list(dataset.percent_passing)
    target = scheme.silt_max if scheme is not None else ISO14688.silt_max
    return _interpolate_at(sizes, pcts, target)


def _heat_color(norm: float) -> QColor:
    """Map norm in [0, 1] to a clear 3-band heat color used by Details."""
    norm = max(0.0, min(1.0, norm))
    if norm < 0.34:
        return QColor("#DCE7BF")
    if norm < 0.67:
        return QColor("#E2BB69")
    return QColor("#C98752")


def _perm_class(mean_k: float) -> str:
    """Return a human-readable permeability classification for mean_k (m/s)."""
    return _gc_perm_class(mean_k)


_PERM_CLASS_COLOR = {
    "Very High (Gravel)":           "#2e7d32",  # dark green
    "High (Clean Sand)":            "#558b2f",  # olive green
    "Moderate (Fine Sand)":         "#f57f17",  # amber
    "Low (Silt)":                   "#e65100",  # deep orange
    "Very Low (Clay-Silt)":         "#b71c1c",  # dark red
    "Practically Impermeable (Clay)":"#7b1fa2", # deep purple
}

def _perm_color(valid_k_list: list) -> str:
    """Return hex color for the permeability class based on geometric mean."""
    if not valid_k_list:
        return C.TEXT_MUTED
    mean_k = float(np.exp(np.mean(np.log(valid_k_list))))
    cls = _gc_perm_class(mean_k)
    return _PERM_CLASS_COLOR.get(cls, C.TEXT_MUTED)


# ─────────────────────────────────────────────────────────────────────────────
# Details tab panel header
# ─────────────────────────────────────────────────────────────────────────────

class _DetailsPanelHeader(QWidget):
    """Header band for the two side-by-side panels in the Details tab.

    Matches .cmp-panel-head from design concept: warm low background,
    icon + bold label.
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(
            f"background: {C.BG_LOW};"
            f"border-bottom: 2px solid {C.BORDER_DK};"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(6)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_SM}pt; font-weight: 600;"
            f"letter-spacing: 0.04em; color: {C.TEXT_MID};"
            f"background: transparent; border: none;"
        )
        lay.addWidget(lbl)
        lay.addStretch()


# ─────────────────────────────────────────────────────────────────────────────
# ComparisonTab
# ─────────────────────────────────────────────────────────────────────────────

class ComparisonTab(QWidget):
    """Main comparison widget — wires 3 sub-tabs: Plot, Details, Statistics."""

    # Emitted whenever update_comparison() completes successfully
    comparison_updated = pyqtSignal()
    # Emitted when the manage-datasets dialog requests a new comparison subset.
    dataset_selection_requested = pyqtSignal(list)

    # ── Grain parameter definitions ──────────────────────────────────────────
    # (label, tooltip, bold, olive-highlight)
    _GRAIN_ROWS = [
        ("D10",    "Effective size (mm)",           True,  True),
        ("D16",    "16th percentile (mm)",           False, False),
        ("D30",    "30th percentile (mm)",           True,  True),
        ("D50",    "Median (mm)",                    True,  True),
        ("D60",    "60th percentile (mm)",           True,  True),
        ("D84",    "84th percentile (mm)",           False, False),
        ("D90",    "90th percentile (mm)",           False, False),
        ("D95",    "95th percentile (mm)",           False, False),
        ("Cu",     "Uniformity coeff. D60/D10",      True,  True),
        ("Cc",     "Curvature coeff.",               True,  True),
        ("σ",      "Sorting coeff. √(D84/D16)",      False, False),
        ("Fines%", "% passing 0.063 mm",             False, False),
        ("Classif.","Soil classification (active scheme)", False, False),
        ("Class",  "Gradation class",                False, False),
    ]
    _GRAIN_PRESETS = {
        "core": {"D10", "D30", "D50", "D60", "Cu", "Cc", "Fines%", "Classif.", "Class"},
        "all": None,
        "context": {"Fines%", "Cu", "Cc", "Classif.", "Class"},
    }
    _K_SUMMARY_LABELS = {
        "K\u0304 geometric",
        "K\u0304 arithmetic",
        "K median",
        "K std. dev.",
        "Perm. class",
    }
    _K_CORE_METHODS = {"Hazen", "Kozeny-Carman", "Beyer", "USBR"}
    _K_METHOD_ORDER = [
        "Hazen", "Hazen_1892", "Slichter", "Terzaghi",
        "Beyer", "Sauerbrei", "Kruger", "Kozeny-Carman",
        "Zunker", "Zamarin", "USBR", "Barr",
        "Alyamani-Sen", "Chapuis", "Shepherd", "Krumbein-Monk",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.dataset_tabs: list = []
        self.selected_datasets: list = []
        self._pinned: set[str] = set()
        self._heat_on: bool = True
        self._active_scheme = ISO14688
        self._details_mode: str = "grain"
        self._details_grain_preset: str = "core"
        self._details_k_preset: str = "all"
        self._details_preset: str = self._details_grain_preset
        self._details_k_unit: HydraulicConductivityUnit = get_default_plot_unit()
        self._stats_k_unit: HydraulicConductivityUnit = get_default_plot_unit()
        self._stats_metric: str = "geometric"

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"""
            QTabWidget::pane {{
                border: none;
                background: {C.BG};
            }}
            QTabBar {{
                background: {C.BG_RAISED};
                border-bottom: 1px solid {C.BORDER};
            }}
            QTabBar::tab {{
                background: transparent;
                border: 1px solid transparent;
                border-bottom: none;
                border-radius: 3px 3px 0 0;
                padding: 4px 18px;
                margin-right: 1px;
                margin-bottom: -1px;
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                color: {C.TEXT_MUTED};
                min-height: 26px;
            }}
            QTabBar::tab:selected {{
                background: {C.BG};
                border-color: {C.BORDER};
                color: {C.TEXT};
                font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background: {C.BG_LOW};
                color: {C.TEXT_MID};
                border-color: {C.BORDER};
            }}
            """
        )
        root.addWidget(self._tabs, 1)

        for page, label, fa_name in [
            (self._build_plot_tab(),       "Plot",       "fa6s.chart-area"),
            (self._build_details_tab_v2(), "Details",    "fa6s.table"),
            (self._build_statistics_tab(), "Statistics", "fa6s.chart-bar"),
        ]:
            try:
                self._tabs.addTab(page, theme_icon(fa_name, C.TEXT_MUTED), label)
            except Exception:
                self._tabs.addTab(page, label)
        self._tabs.setIconSize(QSize(12, 12))
        self._tabs_fader = TabFadeInController(
            self._tabs,
            self,
            duration_ms=100,
        )

    def _build_header(self) -> QWidget:
        """Top 52 px header bar — title/subtitle block + action buttons."""
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        bar.setStyleSheet(
            f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER_DK};"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 10, 0)
        lay.setSpacing(8)

        # Title + subtitle block
        title_block = QWidget()
        title_block.setStyleSheet("background: transparent;")
        tb_v = QVBoxLayout(title_block)
        tb_v.setContentsMargins(0, 0, 0, 0)
        tb_v.setSpacing(1)

        title = QLabel("Batch Comparison")
        title.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_LG}pt; font-weight: 700;"
            f"color: {C.TEXT}; background: transparent; border: none;"
        )
        tb_v.addWidget(title)

        self._count_label = QLabel("Load datasets to compare")
        self._count_label.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED};"
            f"background: transparent; border: none;"
        )
        tb_v.addWidget(self._count_label)

        lay.addWidget(title_block)
        lay.addStretch(1)

        # Manage Datasets button
        self._manage_btn = QPushButton("Manage Datasets")
        self._manage_btn.setFixedHeight(28)
        try:
            self._manage_btn.setIcon(theme_icon("fa6s.list-check", C.TEXT_MID))
            self._manage_btn.setIconSize(QSize(11, 11))
        except Exception:
            pass
        self._manage_btn.setEnabled(False)
        self._manage_btn.setToolTip("Choose which loaded datasets appear in comparison and sync them with SAMPLES")
        self._manage_btn.clicked.connect(self._on_manage_datasets)

        self._update_btn = QPushButton("Update")
        self._update_btn.setProperty("primary", "true")
        self._update_btn.setFixedHeight(28)
        self._update_btn.setEnabled(False)
        self._update_btn.clicked.connect(self.update_comparison)

        self._export_btn = QPushButton("Export Selected")
        self._export_btn.setFixedHeight(28)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_plot)
        try:
            self._export_btn.setIcon(theme_icon("fa6s.file-export", C.TEXT_MID))
            self._export_btn.setIconSize(QSize(11, 11))
        except Exception:
            pass

        lay.addWidget(self._manage_btn)
        lay.addWidget(self._update_btn)
        lay.addWidget(self._export_btn)
        return bar

    # ── Plot tab ──────────────────────────────────────────────────────────────

    def _build_plot_tab(self) -> QWidget:
        """Plot tab: canvas on left, pinned-dataset sidebar on right."""
        page = QWidget()
        h = QHBoxLayout(page)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Main plot widget
        self._plot_widget = ComparisonPlotWidget()
        self._plot_widget.dataset_colors = DATASET_COLORS
        h.addWidget(self._plot_widget, 1)

        # Right sidebar — fixed 180 px
        sidebar = QFrame()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet(
            f"background: {C.BG_RAISED}; border-left: 1px solid {C.BORDER};"
        )
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(0, 0, 0, 0)
        sb_lay.setSpacing(0)

        # "DATASETS" header band
        hdr = QLabel("DATASETS")
        hdr.setFixedHeight(30)
        hdr.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        hdr.setStyleSheet(
            f"padding-left: 10px; font-size: {F.SZ_XS}pt; font-weight: 700;"
            f"letter-spacing: 0.10em; color: {C.TEXT_MUTED};"
            f"background: {C.BG_LOW}; border-bottom: 1px solid {C.BORDER};"
        )
        sb_lay.addWidget(hdr)

        # Scrollable pin list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._pin_list_widget = QWidget()
        self._pin_list_layout = QVBoxLayout(self._pin_list_widget)
        self._pin_list_layout.setContentsMargins(0, 0, 0, 0)
        self._pin_list_layout.setSpacing(0)
        self._pin_list_layout.addStretch(1)
        scroll.setWidget(self._pin_list_widget)
        sb_lay.addWidget(scroll, 1)

        h.addWidget(sidebar)
        return page

    def _refresh_pin_list(self) -> None:
        """Rebuild the pin-list rows from the currently selected datasets."""
        # Remove all except the trailing stretch
        while self._pin_list_layout.count() > 1:
            item = self._pin_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, tab in enumerate(self.selected_datasets):
            name = tab.get_dataset_name()
            color = DATASET_COLORS[i % len(DATASET_COLORS)]
            pinned = name in self._pinned

            row = QWidget()
            row.setFixedHeight(34)
            row.setStyleSheet(
                f"background: transparent; border-bottom: 1px solid {C.BORDER};"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 0, 6, 0)
            rl.setSpacing(6)

            dot = QLabel("●")
            dot.setStyleSheet(
                f"color: {color}; font-size: 10pt;"
                f"background: transparent; border: none;"
            )
            dot.setFixedWidth(14)
            rl.addWidget(dot)

            lbl = QLabel(name)
            lbl.setStyleSheet(
                f"font-size: {F.SZ_SM}pt; color: {C.TEXT};"
                f"background: transparent; border: none;"
            )
            lbl.setToolTip(name)
            rl.addWidget(lbl, 1)

            pin_btn = QPushButton()
            pin_btn.setFixedSize(22, 22)
            pin_btn.setToolTip("Unpin from view" if pinned else "Pin to view")
            pin_btn.setStyleSheet(
                f"QPushButton {{ border: none; border-radius: 3px; padding: 0;"
                f"  background: {'rgba(107,142,35,0.15)' if pinned else 'transparent'}; }}"
                f"QPushButton:hover {{ background: rgba(0,0,0,0.07); }}"
            )
            try:
                pin_btn.setIcon(theme_icon(
                    "fa6s.thumbtack", color if pinned else C.TEXT_MUTED
                ))
                pin_btn.setIconSize(QSize(10, 10))
            except Exception:
                pin_btn.setText("📌" if pinned else "○")
            pin_btn.clicked.connect(lambda _checked, n=name: self._toggle_pin(n))
            rl.addWidget(pin_btn)

            # Insert before the stretch (last item)
            self._pin_list_layout.insertWidget(
                self._pin_list_layout.count() - 1, row
            )

    def _build_details_tab_v2(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        toolbar = QWidget()
        toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        toolbar.setStyleSheet(
            f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER};"
        )
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.setSpacing(8)

        self._details_mode_grain_btn = self._make_details_toggle("Grain", True)
        self._details_mode_grain_btn.clicked.connect(lambda: self._set_details_mode("grain"))
        tb.addWidget(self._details_mode_grain_btn)

        self._details_mode_k_btn = self._make_details_toggle("K-Values", False)
        self._details_mode_k_btn.clicked.connect(lambda: self._set_details_mode("k"))
        tb.addWidget(self._details_mode_k_btn)

        self._details_preset_core_btn = self._make_details_toggle("Core", True)
        self._details_preset_core_btn.clicked.connect(lambda: self._set_details_preset("core"))
        tb.addWidget(self._details_preset_core_btn)

        self._details_preset_all_btn = self._make_details_toggle("All", False)
        self._details_preset_all_btn.clicked.connect(lambda: self._set_details_preset("all"))
        tb.addWidget(self._details_preset_all_btn)

        self._details_preset_context_btn = self._make_details_toggle("Classification", False)
        self._details_preset_context_btn.clicked.connect(lambda: self._set_details_preset("context"))
        tb.addWidget(self._details_preset_context_btn)
        tb.addStretch(1)

        self._details_unit_lbl = QLabel("Unit")
        self._details_unit_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f"color: {C.TEXT_MUTED}; background: transparent; border: none;"
        )
        tb.addWidget(self._details_unit_lbl)

        self._details_unit_combo = QComboBox()
        self._details_unit_combo.setObjectName("pw-style-sel")
        for unit, symbol in HydraulicConductivityConverter.get_all_units().items():
            self._details_unit_combo.addItem(symbol, unit)
        default_index = list(HydraulicConductivityConverter.get_all_units().keys()).index(self._details_k_unit)
        self._details_unit_combo.setCurrentIndex(default_index)
        self._details_unit_combo.currentIndexChanged.connect(self._on_details_unit_changed)
        tb.addWidget(self._details_unit_combo)

        heat_lbl = QLabel("Heat")
        heat_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f"color: {C.TEXT_MUTED}; background: transparent; border: none;"
        )
        tb.addWidget(heat_lbl)

        self._heat_btn = QPushButton("On")
        self._heat_btn.setCheckable(True)
        self._heat_btn.setChecked(True)
        self._heat_btn.setFixedSize(46, 22)
        self._heat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._heat_btn.setStyleSheet(f"""
            QPushButton {{
                font-family: '{F.MONO}'; font-size: 8pt; font-weight: 600;
                border-radius: 11px;
            }}
            QPushButton:checked {{
                background: {C.OLIVE}; color: white;
                border: 1px solid {C.OLIVE_DK};
            }}
            QPushButton:!checked {{
                background: {C.BG_LOW}; color: {C.TEXT_MUTED};
                border: 1px solid {C.BORDER};
            }}
            QPushButton:checked:hover {{ background: {C.OLIVE_H}; }}
            QPushButton:!checked:hover {{ background: {C.BG}; color: {C.TEXT_MID}; }}
        """)
        self._heat_btn.toggled.connect(self._on_heat_toggle)
        tb.addWidget(self._heat_btn)

        self._details_context = QLabel("")
        self._details_context.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            f"color: {C.TEXT_MUTED}; background: transparent; border: none;"
        )
        tb.addWidget(self._details_context)
        v.addWidget(toolbar)

        self._details_dataset_strip = self._build_details_dataset_strip()
        v.addWidget(self._details_dataset_strip)

        self._details_focus_strip = QLabel("")
        self._details_focus_strip.setWordWrap(True)
        self._details_focus_strip.setStyleSheet(
            f"padding: 8px 12px; background: {C.BG}; border-bottom: 1px solid {C.BORDER};"
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED};"
        )
        v.addWidget(self._details_focus_strip)

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        bh = QHBoxLayout(body)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(0)

        self._details_stack = QStackedWidget()
        self._details_stack.setStyleSheet("background: transparent; border: none;")

        self._grain_table = QTableWidget()
        self._style_details_table(self._grain_table)
        self._details_stack.addWidget(self._grain_table)

        self._k_table = QTableWidget()
        self._style_details_table(self._k_table)
        self._details_stack.addWidget(self._k_table)

        bh.addWidget(self._details_stack, 1)
        bh.addWidget(self._build_details_rail())
        v.addWidget(body, 1)

        self._sync_details_mode_ui()
        return page

    def _make_details_toggle(self, text: str, active: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                min-height: 26px;
                padding: 0 11px;
                border-radius: 11px;
                border: 1px solid {C.BORDER};
                background: {C.BG};
                color: {C.TEXT_MID};
                font-size: {F.SZ_SM}pt;
                font-weight: 600;
            }}
            QPushButton:checked {{
                background: rgba(107,142,35,0.10);
                color: {C.OLIVE};
                border-color: rgba(107,142,35,0.34);
            }}
            QPushButton:hover {{
                background: {C.BG_LOW};
                border-color: {C.BORDER_DK};
            }}
        """)
        return btn

    def _build_details_dataset_strip(self) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet(f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER};")
        root = QHBoxLayout(wrap)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        self._details_dataset_chips_layout = QHBoxLayout(content)
        self._details_dataset_chips_layout.setContentsMargins(12, 8, 12, 8)
        self._details_dataset_chips_layout.setSpacing(8)
        self._details_dataset_chips_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll)
        return wrap

    def _build_details_rail(self) -> QWidget:
        rail = QFrame()
        rail.setFixedWidth(272)
        rail.setStyleSheet(
            f"background: {C.BG_RAISED}; border-left: 1px solid {C.BORDER};"
        )
        v = QVBoxLayout(rail)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._details_focus_section, self._details_focus_layout = self._build_details_rail_section("Focus")
        v.addWidget(self._details_focus_section)

        self._details_insight_section, self._details_insights_layout = self._build_details_rail_section("Insights")
        v.addWidget(self._details_insight_section)

        self._details_status_section, self._details_status_layout = self._build_details_rail_section("Method Status")
        v.addWidget(self._details_status_section)

        self._details_legend_section, legend_layout = self._build_details_rail_section("Heat Legend")
        for label, color in [
            ("Lower range", _heat_color(0.0).name()),
            ("Middle range", _heat_color(0.5).name()),
            ("Higher range", _heat_color(1.0).name()),
        ]:
            legend_layout.addWidget(self._make_stats_legend_row(label, color))
        v.addWidget(self._details_legend_section)
        v.addStretch(1)
        return rail

    def _build_details_rail_section(self, title: str):
        section = QWidget()
        section.setStyleSheet(f"background: transparent; border-bottom: 1px solid {C.BORDER};")
        v = QVBoxLayout(section)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        hdr = QLabel(title.upper())
        hdr.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; font-weight: 700;"
            f"letter-spacing: 0.08em; color: {C.TEXT_MUTED}; background: transparent;"
        )
        v.addWidget(hdr)

        content = QVBoxLayout()
        content.setSpacing(8)
        v.addLayout(content)
        return section, content

    def _sync_details_mode_ui(self) -> None:
        grain_mode = self._details_mode == "grain"
        active_preset = self._details_grain_preset if grain_mode else self._details_k_preset
        self._details_preset = active_preset
        self._details_mode_grain_btn.setChecked(grain_mode)
        self._details_mode_k_btn.setChecked(not grain_mode)
        self._details_preset_core_btn.setChecked(active_preset == "core")
        self._details_preset_all_btn.setChecked(active_preset == "all")
        self._details_preset_context_btn.setChecked(active_preset == "context")
        self._details_preset_context_btn.setText("Classification" if grain_mode else "Summary")
        self._details_stack.setCurrentWidget(self._grain_table if grain_mode else self._k_table)
        self._details_unit_lbl.setVisible(not grain_mode)
        self._details_unit_combo.setVisible(not grain_mode)
        context_suffix = "Grain" if grain_mode else f"K-Values · {HydraulicConductivityConverter.UNIT_SYMBOLS[self._details_k_unit]}"
        self._details_context.setText(f"{self._scheme_label()} · {context_suffix}")
        self._details_status_section.setVisible(not grain_mode)

    def _set_details_mode(self, mode: str) -> None:
        if mode == self._details_mode:
            return
        self._details_mode = mode
        self._sync_details_mode_ui()
        self._refresh_details_views()

    def _set_details_preset(self, preset: str) -> None:
        active_preset = self._details_grain_preset if self._details_mode == "grain" else self._details_k_preset
        if preset == active_preset:
            return
        if self._details_mode == "grain":
            self._details_grain_preset = preset
        else:
            self._details_k_preset = preset
        self._details_preset = preset
        self._sync_details_mode_ui()
        self._refresh_details_views()

    def _on_details_unit_changed(self) -> None:
        unit = self._details_unit_combo.currentData()
        if unit is None or unit == self._details_k_unit:
            return
        self._details_k_unit = unit
        self._sync_details_mode_ui()
        if self.selected_datasets:
            self._refresh_k_table()
            self._refresh_details_rail()

    def _toggle_pin(self, name: str) -> None:
        """Toggle pinned state for the named dataset and refresh."""
        if name in self._pinned:
            self._pinned.discard(name)
        else:
            self._pinned.add(name)
        self._refresh_pin_list()

    # ── Details tab ───────────────────────────────────────────────────────────

    @staticmethod
    def _style_details_table(t: QTableWidget) -> None:
        """Apply clean concept-matching style to a details QTableWidget."""
        t.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(False)
        t.setShowGrid(False)
        t.setSortingEnabled(False)
        t.horizontalHeader().setSectionsClickable(True)
        t.horizontalHeader().setSortIndicatorShown(True)
        t.setStyleSheet(f"""
            QTableWidget {{
                background: {C.BG};
                border: none;
            }}
            QTableWidget::item {{
                border-bottom: 1px solid rgba(212,196,168,0.45);
                padding: 0px;
            }}
            QTableWidget::item:selected {{
                background: rgba(107,142,35,0.08);
            }}
            QHeaderView::section {{
                background: {C.BG_RAISED};
                border: none;
                border-bottom: 2px solid {C.BORDER_DK};
                border-right: 1px solid rgba(212,196,168,0.4);
                padding: 5px 10px;
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                font-weight: 600;
                color: {C.TEXT_MID};
            }}
            QHeaderView::section:last {{
                border-right: none;
            }}
            QScrollBar:vertical {{
                width: 5px; background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER}; border-radius: 2px; min-height: 16px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

    def _build_details_tab(self) -> QWidget:
        """Details tab: two clean side-by-side panels with heat-map toggle."""
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ── Toolbar strip with heat-map toggle ────────────────────────────────
        toolbar = QWidget()
        toolbar.setFixedHeight(32)
        toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        toolbar.setStyleSheet(
            f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER};"
        )
        tb_row = QHBoxLayout(toolbar)
        tb_row.setContentsMargins(12, 0, 12, 0)
        tb_row.setSpacing(8)
        tb_row.addStretch(1)

        heat_lbl = QLabel("Heat map")
        heat_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f"color: {C.TEXT_MUTED}; background: transparent; border: none;"
        )
        tb_row.addWidget(heat_lbl)

        self._heat_btn = QPushButton("On")
        self._heat_btn.setCheckable(True)
        self._heat_btn.setChecked(True)
        self._heat_btn.setFixedSize(46, 22)
        self._heat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._heat_btn.setStyleSheet(f"""
            QPushButton {{
                font-family: '{F.MONO}'; font-size: 8pt; font-weight: 600;
                border-radius: 11px;
            }}
            QPushButton:checked {{
                background: {C.OLIVE}; color: white;
                border: 1px solid {C.OLIVE_DK};
            }}
            QPushButton:!checked {{
                background: {C.BG_LOW}; color: {C.TEXT_MUTED};
                border: 1px solid {C.BORDER};
            }}
            QPushButton:checked:hover {{ background: {C.OLIVE_H}; }}
            QPushButton:!checked:hover {{ background: {C.BG}; color: {C.TEXT_MID}; }}
        """)
        self._heat_btn.toggled.connect(self._on_heat_toggle)
        tb_row.addWidget(self._heat_btn)

        v.addWidget(toolbar)

        # ── Body: two panels side by side ─────────────────────────────────────
        body = QWidget()
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        body.setStyleSheet(f"background: {C.BG};")
        body_h = QHBoxLayout(body)
        body_h.setContentsMargins(0, 0, 0, 0)
        body_h.setSpacing(0)

        # Left: Grain Parameters
        left = QWidget()
        left.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        left.setStyleSheet("background: transparent;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        ll.addWidget(_DetailsPanelHeader("Grain Parameters"))
        self._grain_table = QTableWidget()
        self._style_details_table(self._grain_table)
        ll.addWidget(self._grain_table, 1)

        # Vertical separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {C.BORDER_DK}; border: none;")

        # Right: Hydraulic Conductivity
        right = QWidget()
        right.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        right.setStyleSheet("background: transparent;")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(_DetailsPanelHeader("Hydraulic Conductivity"))
        self._k_table = QTableWidget()
        self._style_details_table(self._k_table)
        rl.addWidget(self._k_table, 1)

        body_h.addWidget(left, 55)
        body_h.addWidget(sep)
        body_h.addWidget(right, 45)

        v.addWidget(body, 1)
        return page

    def _on_heat_toggle(self, checked: bool) -> None:
        """Toggle heat coloring on/off and refresh both tables."""
        self._heat_on = checked
        self._heat_btn.setText("On" if checked else "Off")
        if self.selected_datasets:
            self._refresh_grain_table()
            self._refresh_k_table()
            self._refresh_details_views()

    def _scheme_label(self) -> str:
        return getattr(self._active_scheme, "name", None) or self._active_scheme.__class__.__name__.replace("_", " ")

    def _reset_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._reset_layout(child_layout)

    def _make_rail_line(self, text: str, *, active: bool = False) -> QLabel:
        lbl = QLabel(text)
        bg = "rgba(107,142,35,0.10)" if active else "rgba(255,255,255,0.46)"
        bdr = "rgba(107,142,35,0.28)" if active else "rgba(212,196,168,0.72)"
        fg = C.OLIVE if active else C.TEXT_MID
        lbl.setStyleSheet(
            f"padding: 8px 10px; background: {bg}; border: 1px solid {bdr};"
            f"border-radius: 9px; color: {fg}; font-size: {F.SZ_SM}pt; font-weight: 600;"
        )
        return lbl

    def _make_insight_card(self, title: str, body: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet(
            f"background: rgba(255,255,255,0.52); border: 1px solid rgba(212,196,168,0.76); border-radius: 10px;"
        )
        v = QVBoxLayout(card)
        v.setContentsMargins(11, 10, 11, 10)
        v.setSpacing(5)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        body_lbl = QLabel(body)
        body_lbl.setWordWrap(True)
        body_lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; color: {C.TEXT_MID}; background: transparent; line-height: 1.4;"
        )
        v.addWidget(title_lbl)
        v.addWidget(body_lbl)
        return card

    def _make_status_row(self, method: str, detail: str, state: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet(
            f"background: transparent; border: none; border-bottom: 1px solid rgba(212,196,168,0.55);"
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(2, 6, 2, 7)
        h.setSpacing(8)
        copy = QWidget()
        copy_v = QVBoxLayout(copy)
        copy_v.setContentsMargins(0, 0, 0, 0)
        copy_v.setSpacing(1)
        method_lbl = QLabel(method)
        method_lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        detail_lbl = QLabel(detail)
        detail_lbl.setWordWrap(True)
        detail_lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; color: {C.TEXT_MUTED}; background: transparent;"
        )
        copy_v.addWidget(method_lbl)
        copy_v.addWidget(detail_lbl)
        badge = QLabel(state.upper())
        if state == "ok":
            bg, fg = "rgba(107,142,35,0.10)", C.OLIVE
        elif state == "warn":
            bg, fg = "rgba(196,165,116,0.18)", C.EARTH
        else:
            bg, fg = "rgba(212,196,168,0.25)", C.TEXT_MUTED
        badge.setStyleSheet(
            f"padding: 2px 7px; background: {bg}; border: 1px solid rgba(212,196,168,0.65);"
            f"border-radius: 999px; color: {fg}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; font-weight: 700;"
        )
        h.addWidget(copy, 1)
        h.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        return row

    def _make_dataset_chip(self, name: str, color: str) -> QWidget:
        chip = QWidget()
        chip.setToolTip(name)
        h = QHBoxLayout(chip)
        h.setContentsMargins(2, 0, 8, 0)
        h.setSpacing(6)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {color}; background: transparent; font-size: {F.SZ_SM + 1}pt; font-weight: 700;"
        )
        name_lbl = QLabel(self._short_dataset_name(name))
        name_lbl.setStyleSheet(
            f"color: {C.TEXT_MID}; background: transparent; font-size: {F.SZ_SM}pt; font-weight: 600;"
        )
        h.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(name_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        return chip

    def _short_dataset_name(self, name: str, max_width: int = 118) -> str:
        metrics = QFontMetrics(QFont(F.UI, F.SZ_SM))
        return metrics.elidedText(name, Qt.TextElideMode.ElideRight, max_width)

    def _refresh_details_dataset_strip(self) -> None:
        layout = self._details_dataset_chips_layout
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for i, tab in enumerate(self.selected_datasets):
            name = tab.get_dataset_name()
            color = DATASET_COLORS[i % len(DATASET_COLORS)]
            chip = self._make_dataset_chip(name, color)
            layout.insertWidget(layout.count() - 1, chip)

    def _refresh_details_views(self) -> None:
        self._sync_details_mode_ui()
        if self.selected_datasets:
            self._refresh_grain_table()
            self._refresh_k_table()
        self._refresh_details_dataset_strip()
        self._refresh_details_rail()

    def _refresh_details_rail(self) -> None:
        self._reset_layout(self._details_focus_layout)
        self._reset_layout(self._details_insights_layout)
        self._reset_layout(self._details_status_layout)

        self._details_focus_layout.addWidget(
            self._make_rail_line(
                "Grain parameter matrix" if self._details_mode == "grain" else "K-value matrix",
                active=True,
            )
        )
        preset_label = {
            ("grain", "core"): "Core grain rows",
            ("grain", "all"): "All grain rows",
            ("grain", "context"): "Classification rows",
            ("k", "core"): "Core K methods",
            ("k", "all"): "All K methods",
            ("k", "context"): "K summary rows",
        }[(self._details_mode, self._details_preset)]
        self._details_focus_layout.addWidget(self._make_rail_line(preset_label))
        if len(self.selected_datasets) >= 7:
            self._details_focus_layout.addWidget(self._make_rail_line("High-column count mode"))

        for title, body in self._build_detail_insights():
            self._details_insights_layout.addWidget(self._make_insight_card(title, body))

        if self._details_mode == "k":
            for method, detail, state in self._build_k_status_summary():
                self._details_status_layout.addWidget(self._make_status_row(method, detail, state))

        focus_bits = [
            f"{len(self.selected_datasets)} datasets",
            self._scheme_label(),
            "heat on" if self._heat_on else "heat off",
        ]
        if self._details_mode == "k":
            focus_bits.insert(2, self._details_unit_symbol())
        if len(self.selected_datasets) >= 7 and self._details_preset == "all":
            focus_bits.append("consider Core for readability")
        self._details_focus_strip.setText("  ·  ".join(focus_bits))
        self._details_legend_section.setVisible(self._heat_on)

    def _build_detail_insights(self) -> list[tuple[str, str]]:
        tabs = self.selected_datasets
        if not tabs:
            return [("No comparison data", "Load at least two datasets to populate details.")]

        if self._details_mode == "grain":
            tracked = ["D50", "Cu", "Fines%"]
            insights = []
            spreads = []
            for label in tracked:
                values = [self._get_grain_value(tab.get_dataset(), label) for tab in tabs]
                valid = [value for value in values if value is not None]
                if len(valid) >= 2:
                    spreads.append((max(valid) - min(valid), label, min(valid), max(valid)))
            if spreads:
                spreads.sort(reverse=True)
                _, label, low, high = spreads[0]
                insights.append(
                    (
                        f"Largest {label} spread",
                        f"{low:.4g} to {high:.4g} across the selected set.",
                    )
                )
            if len(tabs) >= 7:
                insights.append(
                    (
                        "Why Core is default",
                        "With many datasets loaded, the core preset keeps the matrix readable without hiding the key engineering rows.",
                    )
                )
            insights.append(("Classification context", f"Labels follow the active scheme: {self._scheme_label()}."))
            return insights[:3]

        valid_per_dataset = []
        for tab in tabs:
            vals = [r.k_value for r in tab.get_results() if r.k_value is not None and r.k_value > 0]
            if vals:
                valid_per_dataset.append((tab.get_dataset_name(), float(np.exp(np.mean(np.log(vals))))))
        insights = []
        if valid_per_dataset:
            valid_per_dataset.sort(key=lambda item: item[1])
            low_name, low_val = valid_per_dataset[0]
            high_name, high_val = valid_per_dataset[-1]
            insights.append(
                (
                    "Largest K contrast",
                    f"{low_name} to {high_name} spans {self._format_k_value(low_val)} to {self._format_k_value(high_val)}.",
                )
            )
        insights.append(
            (
                "Method trust",
                "Use the method-status rail to see which formulas are valid, warned, or unavailable for the current selection.",
            )
        )
        insights.append(
            (
                "Unit context",
                f"K-values in this view are shown in {self._details_unit_symbol()}.",
            )
        )
        return insights[:3]

    def _build_k_status_summary(self) -> list[tuple[str, str, str]]:
        counts: dict[str, dict[str, int]] = {}
        for tab in self.selected_datasets:
            for result in tab.get_results():
                state = "na"
                if result.status == CalculationStatus.OK:
                    state = "ok"
                elif result.status == CalculationStatus.WARNING:
                    state = "warn"
                counts.setdefault(result.method_name, {"ok": 0, "warn": 0, "na": 0})[state] += 1

        rows = []
        total = max(1, len(self.selected_datasets))
        for method, state_counts in sorted(counts.items()):
            if state_counts["warn"] > 0:
                state = "warn"
                detail = f"{state_counts['warn']} warned, {state_counts['ok']} valid"
            elif state_counts["ok"] > 0:
                state = "ok"
                detail = f"{state_counts['ok']} / {total} valid"
            else:
                state = "na"
                detail = "Unavailable for current datasets"
            rows.append((method, detail, state))
        return rows[:4]

    # ── Statistics tab ────────────────────────────────────────────────────────

    def _build_statistics_tab(self) -> QWidget:
        """Statistics tab: distribution-first layout with compact agreement rail."""
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QWidget()
        toolbar.setFixedHeight(42)
        toolbar.setStyleSheet(
            f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER};"
        )
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(14, 0, 14, 0)
        tb.setSpacing(10)

        metric_seg = QWidget()
        metric_seg.setStyleSheet(
            f"background: rgba(255,255,255,0.56); border: 1px solid rgba(154,126,95,0.18); border-radius: 999px;"
        )
        metric_h = QHBoxLayout(metric_seg)
        metric_h.setContentsMargins(4, 4, 4, 4)
        metric_h.setSpacing(4)
        self._stats_metric_geo_btn = self._make_details_toggle("Geo. mean", self._stats_metric == "geometric")
        self._stats_metric_med_btn = self._make_details_toggle("Median", self._stats_metric == "median")
        self._stats_metric_geo_btn.clicked.connect(lambda: self._on_stats_metric_changed("geometric"))
        self._stats_metric_med_btn.clicked.connect(lambda: self._on_stats_metric_changed("median"))
        metric_h.addWidget(self._stats_metric_geo_btn)
        metric_h.addWidget(self._stats_metric_med_btn)
        tb.addWidget(metric_seg, 0)

        unit_lbl = QLabel("Unit")
        unit_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED};"
        )
        tb.addWidget(unit_lbl, 0)

        self._stats_unit_combo = QComboBox()
        self._stats_unit_combo.setObjectName("pw-style-sel")
        for unit, symbol in HydraulicConductivityConverter.get_all_units().items():
            self._stats_unit_combo.addItem(symbol, unit)
        default_index = self._stats_unit_combo.findData(self._stats_k_unit)
        if default_index >= 0:
            self._stats_unit_combo.setCurrentIndex(default_index)
        self._stats_unit_combo.currentIndexChanged.connect(self._on_stats_unit_changed)
        tb.addWidget(self._stats_unit_combo, 0)

        self._stats_context = QLabel("")
        self._stats_context.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED}; background: transparent;"
        )
        tb.addStretch(1)
        tb.addWidget(self._stats_context, 0)
        root.addWidget(toolbar)

        root.addWidget(self._build_stats_dataset_strip())

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        bh = QHBoxLayout(body)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(0)

        main = QWidget()
        main.setStyleSheet(f"background: {C.BG}; border-right: 1px solid {C.BORDER};")
        mv = QVBoxLayout(main)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(0)

        fc = C.BG
        self._box_fig = Figure(figsize=(8, 5), facecolor=fc, tight_layout=True)
        self._box_canvas = FigureCanvas(self._box_fig)
        self._box_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._heat_fig = Figure(figsize=(8, 5), facecolor=fc, tight_layout=True)
        self._heat_canvas = FigureCanvas(self._heat_fig)
        self._heat_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._heat_canvas.setMinimumHeight(250)

        mv.addWidget(self._build_stats_panel(
            "K-value spread across selected datasets",
            self._box_canvas,
            meta_attr="_stats_dist_meta",
        ), 7)
        mv.addWidget(self._build_stats_panel(
            "Method agreement and applicability",
            self._heat_canvas,
            meta_attr="_stats_agreement_meta",
        ), 4)

        rail = QFrame()
        rail.setFixedWidth(286)
        rail.setStyleSheet(
            f"background: {C.BG_RAISED};"
        )
        rv = QVBoxLayout(rail)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        self._stats_insight_section, self._stats_insights_layout = self._build_stats_rail_section("Quick Read")
        rv.addWidget(self._stats_insight_section)
        self._stats_summary_section, self._stats_summary_layout = self._build_stats_rail_section("Summary")
        rv.addWidget(self._stats_summary_section)
        self._stats_legend_section, self._stats_legend_layout = self._build_stats_rail_section("Agreement Legend")
        for text, color in [
            ("Method valid and included in summary", "#dbe8c0"),
            ("Method available, but outside preferred applicability range", "#d99a3a"),
            ("Method unavailable or not meaningful for that dataset", "#ece5da"),
        ]:
            self._stats_legend_layout.addWidget(self._make_stats_legend_row(text, color))
        rv.addWidget(self._stats_legend_section)
        rv.addStretch(1)

        bh.addWidget(main, 1)
        bh.addWidget(rail, 0)
        root.addWidget(body, 1)
        self._refresh_stats_workspace()
        return page

    def _build_stats_panel(self, title: str, canvas: FigureCanvas, *, meta_attr: str) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {C.BG}; border-bottom: 1px solid {C.BORDER};")
        v = QVBoxLayout(panel)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(8)

        head = QWidget()
        h = QHBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size: {F.SZ_BASE + 1}pt; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )

        meta_lbl = QLabel("")
        meta_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED}; background: transparent;"
        )
        setattr(self, meta_attr, meta_lbl)

        h.addWidget(title_lbl, 1)
        h.addWidget(meta_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addWidget(head)
        v.addWidget(canvas, 1)
        return panel

    def _build_stats_rail_section(self, title: str):
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        v = QVBoxLayout(section)
        v.setContentsMargins(14, 12, 14, 6)
        v.setSpacing(8)

        hdr = QLabel(title.upper())
        hdr.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; font-weight: 700;"
            f"letter-spacing: 0.08em; color: {C.TEXT_MUTED}; background: transparent;"
        )
        v.addWidget(hdr)

        content = QVBoxLayout()
        content.setSpacing(4)
        v.addLayout(content)
        return section, content

    def _build_stats_dataset_strip(self) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet(f"background: rgba(255,255,255,0.34); border-bottom: 1px solid {C.BORDER};")
        root = QHBoxLayout(wrap)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        self._stats_dataset_chips_layout = QHBoxLayout(content)
        self._stats_dataset_chips_layout.setContentsMargins(16, 8, 16, 8)
        self._stats_dataset_chips_layout.setSpacing(12)
        self._stats_dataset_chips_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll)
        return wrap

    def _on_stats_unit_changed(self) -> None:
        unit = self._stats_unit_combo.currentData()
        if unit is None or unit == self._stats_k_unit:
            return
        self._stats_k_unit = unit
        if self.selected_datasets:
            self._refresh_stats()
        else:
            self._refresh_stats_workspace()

    def _on_stats_metric_changed(self, metric: str) -> None:
        if metric == self._stats_metric:
            return
        self._stats_metric = metric
        self._stats_metric_geo_btn.setChecked(metric == "geometric")
        self._stats_metric_med_btn.setChecked(metric == "median")
        if self.selected_datasets:
            self._refresh_stats()
        else:
            self._refresh_stats_workspace()

    def _stats_unit_symbol(self) -> str:
        return HydraulicConductivityConverter.UNIT_SYMBOLS[self._stats_k_unit]

    def _format_stats_k_value(self, value_m_s: float) -> str:
        converted = HydraulicConductivityConverter.convert_from_m_per_s(value_m_s, self._stats_k_unit)
        return HydraulicConductivityConverter.DISPLAY_FORMATS[self._stats_k_unit].format(converted)

    def _ordered_k_methods(self, method_names) -> list[str]:
        seen = set(method_names)
        ordered = [name for name in self._K_METHOD_ORDER if name in seen]
        extras = sorted(seen.difference(self._K_METHOD_ORDER))
        return ordered + extras

    def _make_stats_summary_row(self, label: str, value: str) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 4, 0, 4)
        h.setSpacing(8)
        key_lbl = QLabel(label)
        key_lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; color: {C.TEXT_MUTED}; background: transparent; font-weight: 600;"
        )
        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_SM}pt; color: {C.TEXT_MID}; background: transparent; font-weight: 600;"
        )
        h.addWidget(key_lbl, 1)
        h.addWidget(val_lbl, 0, Qt.AlignmentFlag.AlignRight)
        return row

    def _make_stats_insight_row(self, title: str, body: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet(
            f"background: transparent; border: none; border-bottom: 1px solid rgba(212,196,168,0.5);"
        )
        v = QVBoxLayout(row)
        v.setContentsMargins(0, 6, 0, 7)
        v.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        body_lbl = QLabel(body)
        body_lbl.setWordWrap(True)
        body_lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; color: {C.TEXT_MID}; background: transparent;"
        )
        v.addWidget(title_lbl)
        v.addWidget(body_lbl)
        return row

    def _make_stats_legend_row(self, text: str, color: str) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(10)
        swatch = QFrame()
        swatch.setFixedSize(16, 16)
        swatch.setStyleSheet(
            f"background: {color}; border: 1px solid rgba(92,78,61,0.28); border-radius: 4px;"
        )
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; color: {C.TEXT_MID}; background: transparent; line-height: 1.35;"
        )
        h.addWidget(swatch, 0, Qt.AlignmentFlag.AlignTop)
        h.addWidget(lbl, 1)
        return row

    # ── Data wiring ───────────────────────────────────────────────────────────

    def set_scheme(self, scheme) -> None:
        """Update active classification scheme and refresh if data present."""
        self._active_scheme = scheme
        if len(self.selected_datasets) >= 2:
            self.update_comparison()

    def _set_selected_datasets(self, selected_tabs) -> None:
        """Apply a selected subset while preserving dataset order and valid pins."""
        selected_names = {tab.get_dataset_name() for tab in selected_tabs}
        self.selected_datasets = [
            tab for tab in self.dataset_tabs
            if tab.get_dataset_name() in selected_names
        ]
        if not self.selected_datasets and self.dataset_tabs:
            self.selected_datasets = list(self.dataset_tabs)

        active_names = {tab.get_dataset_name() for tab in self.selected_datasets}
        self._pinned = {name for name in self._pinned if name in active_names}
        if not self._pinned and active_names:
            self._pinned = set(active_names)

        enabled = len(self.selected_datasets) >= 2
        self._update_btn.setEnabled(enabled)
        self._export_btn.setEnabled(enabled)
        if not enabled:
            self._clear_views()
        else:
            self._refresh_details_views()
        self._refresh_pin_list()
        self._update_header_count()

    def set_dataset_state(self, dataset_tabs, selected_tabs=None) -> None:
        """Update loaded datasets and the active comparison subset.

        Args:
            dataset_tabs: list of dataset tab objects exposing
                          get_dataset(), get_dataset_name(), get_results()
            selected_tabs: subset sourced from the sidebar selection. If omitted
                           or empty, all loaded datasets are compared.
        """
        self.dataset_tabs = list(dataset_tabs)

        if selected_tabs:
            selected_names = {tab.get_dataset_name() for tab in selected_tabs}
            selected_tabs = [
                tab for tab in self.dataset_tabs
                if tab.get_dataset_name() in selected_names
            ]
        else:
            selected_tabs = list(self.dataset_tabs)

        self._set_selected_datasets(selected_tabs)

        if len(self.selected_datasets) >= 2:
            self.update_comparison()

    def set_dataset_tabs(self, dataset_tabs) -> None:
        """Backward-compatible wrapper: compare the provided tabs directly."""
        self.set_dataset_state(dataset_tabs, selected_tabs=dataset_tabs)

    def update_comparison(self) -> None:
        """Refresh all views from current dataset_tabs.  Public API."""
        if len(self.selected_datasets) < 2:
            return
        self._update_plot()
        self._refresh_grain_table()
        self._refresh_k_table()
        self._refresh_details_views()
        self._refresh_stats()
        self._update_header_count()
        self.comparison_updated.emit()

    # ── Internal update helpers ───────────────────────────────────────────────

    def _update_header_count(self) -> None:
        n_loaded = len(self.dataset_tabs)
        n_selected = len(self.selected_datasets)
        n_pinned = len(self._pinned)
        self._count_label.setText(
            "Load datasets to compare" if n_loaded == 0
            else f"{n_selected} selected  ·  {n_loaded} loaded  ·  {n_pinned} pinned in view"
        )
        self._manage_btn.setEnabled(n_loaded >= 1)

    def _on_manage_datasets(self) -> None:
        """Open dataset-selection dialog and sync the result back to the sidebar."""
        if not self.dataset_tabs:
            return

        dialog = DatasetSelectionDialog(
            self.dataset_tabs,
            currently_selected=self.selected_datasets,
            parent=self,
        )
        if dialog.exec():
            selected_tabs = dialog.get_selected_tabs()
            self._set_selected_datasets(selected_tabs)
            self.dataset_selection_requested.emit(self._dataset_paths(selected_tabs))
            self.update_comparison()

    @staticmethod
    def _dataset_paths(dataset_tabs) -> list[str]:
        """Return file-path keys for a comparison subset."""
        paths: list[str] = []
        for tab in dataset_tabs:
            dataset = tab.get_dataset() if hasattr(tab, "get_dataset") else getattr(tab, "dataset", None)
            file_path = getattr(dataset, "file_path", "") if dataset is not None else ""
            if file_path:
                paths.append(file_path)
        return paths

    def _update_plot(self) -> None:
        """Push datasets into the comparison plot widget."""
        if not self.selected_datasets:
            if hasattr(self._plot_widget, "show_empty_state"):
                self._plot_widget.show_empty_state("Select datasets and click Update")
            return
        self._plot_widget.set_datasets(self.selected_datasets)
        if hasattr(self._plot_widget, "refresh_plot"):
            self._plot_widget.refresh_plot()

    def _clear_views(self) -> None:
        """Clear stale comparison output when fewer than two datasets are selected."""
        if hasattr(self._plot_widget, "show_empty_state"):
            self._plot_widget.show_empty_state("Select at least 2 datasets to compare")

        for table in (self._grain_table, self._k_table):
            table.clearContents()
            table.setRowCount(0)
            table.setColumnCount(0)

        if hasattr(self, "_details_dataset_chips_layout"):
            self._refresh_details_views()

        for fig, canvas, message in [
            (self._box_fig, self._box_canvas, "Select at least 2 datasets to compare"),
            (self._heat_fig, self._heat_canvas, "Select at least 2 datasets to compare"),
        ]:
            fig.clear()
            ax = fig.add_subplot(1, 1, 1)
            ax.text(
                0.5, 0.5, message,
                transform=ax.transAxes,
                ha='center', va='center',
                fontsize=11, color=C.TEXT_MUTED,
            )
            ax.set_xticks([])
            ax.set_yticks([])
            canvas.draw()
        if hasattr(self, "_stats_dataset_chips_layout"):
            self._refresh_stats_workspace()

    # ── Grain parameter table ─────────────────────────────────────────────────

    def _get_grain_value(self, dataset, row_label: str) -> Optional[float]:
        """Retrieve the numeric value for a given parameter row from a dataset."""
        label = row_label
        if label == "D10":
            return dataset.get_d10()
        if label == "D16":
            return dataset._interpolate_grain_size(16.0)
        if label == "D30":
            return dataset.get_d30()
        if label == "D50":
            return dataset.get_d50()
        if label == "D60":
            return dataset.get_d60()
        if label == "D84":
            return dataset._interpolate_grain_size(84.0)
        if label == "D90":
            return dataset._interpolate_grain_size(90.0)
        if label == "D95":
            return dataset._interpolate_grain_size(95.0)
        if label == "Cu":
            return dataset.get_uniformity_coefficient()
        if label == "Cc":
            return dataset.get_coefficient_of_curvature()
        if label == "σ":
            d84 = dataset._interpolate_grain_size(84.0)
            d16 = dataset._interpolate_grain_size(16.0)
            if d84 is not None and d16 is not None and d16 > 0:
                return math.sqrt(d84 / d16)
            return None
        if label == "Fines%":
            return _get_fines_pct(dataset, self._active_scheme)
        return None  # Text rows handled separately

    def _gradation_class(self, dataset) -> str:
        """Return the scheme-aware gradation/class context for the active scheme."""
        try:
            result = dataset.classify(scheme=self._active_scheme)
        except Exception:
            result = None
        if result is None:
            return "—"
        if result.gradation:
            return result.gradation
        return _gc_cu_label(dataset.get_uniformity_coefficient())

    def _make_param_cell(self, label: str, description: str, olive: bool) -> QWidget:
        """Build a two-line parameter cell widget (name + description)."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 5, 8, 5)
        lay.setSpacing(1)
        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_BASE}pt; font-weight: 600;"
            f"color: {C.OLIVE if olive else C.TEXT_MID}; background: transparent;"
        )
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: 8pt;"
            f"color: {C.TEXT_MUTED}; background: transparent;"
        )
        lay.addWidget(name_lbl)
        lay.addWidget(desc_lbl)
        return w

    def _make_dataset_header_item(self, name: str, color: str) -> QTableWidgetItem:
        header = QTableWidgetItem(self._short_dataset_name(name, max_width=110))
        header.setIcon(_dot_icon(color))
        header.setToolTip(name)
        header.setForeground(QBrush(QColor(color)))
        font = QFont(F.UI, F.SZ_SM)
        font.setBold(True)
        header.setFont(font)
        return header

    def _details_unit_symbol(self) -> str:
        return HydraulicConductivityConverter.UNIT_SYMBOLS[self._details_k_unit]

    def _format_k_value(self, value_m_s: float) -> str:
        converted = HydraulicConductivityConverter.convert_from_m_per_s(value_m_s, self._details_k_unit)
        return HydraulicConductivityConverter.DISPLAY_FORMATS[self._details_k_unit].format(converted)

    def _apply_grain_row_preset(self) -> None:
        allowed = self._GRAIN_PRESETS[self._details_preset]
        for row_i, (label, *_rest) in enumerate(self._GRAIN_ROWS):
            self._grain_table.setRowHidden(row_i, allowed is not None and label not in allowed)

    def _apply_k_row_preset(self, method_names: list[str], summary_rows: list[tuple[str, str]]) -> None:
        if self._details_preset == "all":
            allowed_methods = None
            allowed_summaries = None
        elif self._details_preset == "core":
            allowed_methods = self._K_CORE_METHODS
            allowed_summaries = {"K\u0304 geometric", "Perm. class"}
        else:
            allowed_methods = set()
            allowed_summaries = self._K_SUMMARY_LABELS

        for row_i, method in enumerate(method_names):
            self._k_table.setRowHidden(row_i, allowed_methods is not None and method not in allowed_methods)
        offset = len(method_names)
        for idx, (label, _desc) in enumerate(summary_rows):
            self._k_table.setRowHidden(offset + idx, allowed_summaries is not None and label not in allowed_summaries)

    def _refresh_grain_table(self) -> None:
        """Rebuild the grain parameters table."""
        tabs = self.selected_datasets
        n_ds = len(tabs)
        n_rows = len(self._GRAIN_ROWS)
        self._grain_table.setSortingEnabled(False)

        # Column layout: Parameter | DS0 | DS1 | …
        self._grain_table.setRowCount(n_rows)
        self._grain_table.setColumnCount(1 + n_ds)

        # ── Column headers ────────────────────────────────────────────────────
        self._grain_table.setHorizontalHeaderItem(0, QTableWidgetItem("Parameter"))
        for col_i, tab in enumerate(tabs):
            name = tab.get_dataset_name()
            color = DATASET_COLORS[col_i % len(DATASET_COLORS)]
            hdr_item = self._make_dataset_header_item(name, color)
            self._grain_table.setHorizontalHeaderItem(1 + col_i, hdr_item)

        # First column: stretch; data columns: resize-to-contents
        self._grain_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for c in range(1, 1 + n_ds):
            self._grain_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents
            )

        # ── Collect numeric values per row ────────────────────────────────────
        TEXT_ROWS = {"Classif.", "Class"}
        row_values: List[List[Optional[float]]] = []
        for row_def in self._GRAIN_ROWS:
            label = row_def[0]
            if label in TEXT_ROWS:
                row_values.append([])
                continue
            vals = [self._get_grain_value(tab.get_dataset(), label) for tab in tabs]
            row_values.append(vals)

        # ── Populate rows ─────────────────────────────────────────────────────
        for row_i, (label, tooltip, bold, olive) in enumerate(self._GRAIN_ROWS):
            is_text = label in TEXT_ROWS
            vals = row_values[row_i]

            # Column 0: two-line param cell widget
            label_item = _SortableTableWidgetItem(label)
            label_item.setData(Qt.ItemDataRole.UserRole, label.lower())
            self._grain_table.setItem(row_i, 0, label_item)
            self._grain_table.setCellWidget(
                row_i, 0, self._make_param_cell(label, tooltip, olive)
            )
            self._grain_table.setRowHeight(row_i, 42)

            if is_text:
                if label == "Classif.":
                    for col_i, tab in enumerate(tabs):
                        val_str = tab.get_dataset().classify(scheme=self._active_scheme).label or "—"
                        color = DATASET_COLORS[col_i % len(DATASET_COLORS)]
                        item = _SortableTableWidgetItem(val_str)
                        item.setData(Qt.ItemDataRole.UserRole, val_str.lower())
                        item.setForeground(QBrush(QColor(color)))
                        item.setFont(QFont(F.MONO, F.SZ_SM))
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                        self._grain_table.setItem(row_i, 1 + col_i, item)
                elif label == "Class":
                    for col_i, tab in enumerate(tabs):
                        val_str = self._gradation_class(tab.get_dataset())
                        color = DATASET_COLORS[col_i % len(DATASET_COLORS)]
                        item = _SortableTableWidgetItem(val_str)
                        item.setData(Qt.ItemDataRole.UserRole, val_str.lower())
                        item.setForeground(QBrush(QColor(color)))
                        item.setFont(QFont(F.MONO, F.SZ_SM))
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                        self._grain_table.setItem(row_i, 1 + col_i, item)
                continue

            # Numeric row — heat range
            valid_vals = [v for v in vals if v is not None]
            v_min = min(valid_vals) if valid_vals else 0.0
            v_max = max(valid_vals) if valid_vals else 1.0
            v_range = v_max - v_min if v_max != v_min else 1.0

            for col_i, val in enumerate(vals):
                color = DATASET_COLORS[col_i % len(DATASET_COLORS)]
                if val is None:
                    item = _SortableTableWidgetItem("—")
                    item.setData(Qt.ItemDataRole.UserRole, float("inf"))
                    item.setForeground(QBrush(QColor(C.TEXT_MUTED)))
                else:
                    item = _SortableTableWidgetItem(f"{val:.4g}")
                    item.setData(Qt.ItemDataRole.UserRole, float(val))
                    item.setForeground(QBrush(QColor(color)))
                    if self._heat_on and v_range > 0:
                        norm = (val - v_min) / v_range
                        heat = _heat_color(norm)
                        item.setBackground(QBrush(heat))
                        item.setData(Qt.ItemDataRole.BackgroundRole, heat)
                item.setFont(QFont(F.MONO, F.SZ_SM))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self._grain_table.setItem(row_i, 1 + col_i, item)

        self._grain_table.resizeColumnsToContents()
        self._grain_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._apply_grain_row_preset()
        self._grain_table.setSortingEnabled(True)

    # ── Hydraulic conductivity table ──────────────────────────────────────────

    # ── K-value descriptions (method name → short description) ───────────────
    _K_DESCS: dict = {
        "Hazen":         "based on D10",
        "Kozeny-Carman": "pore structure",
        "USBR":          "Bureau of Reclamation",
        "Terzaghi":      "sandy soils",
        "Slichter":      "uniform sands",
        "Beyer":         "non-uniform sands",
        "Seelheim":      "D10 based",
        "Pavchich":      "coarse sands",
    }

    def _refresh_k_table(self) -> None:
        """Rebuild the hydraulic conductivity comparison table."""
        tabs = self.selected_datasets
        n_ds = len(tabs)
        self._k_table.setSortingEnabled(False)

        # Collect all results per dataset
        results_by_tab = [tab.get_results() for tab in tabs]

        # Gather unique method names (sorted alphabetically)
        method_names: list[str] = self._ordered_k_methods(
            {r.method_name for results in results_by_tab for r in results}
        )

        # Summary rows appended at the bottom
        SUMMARY_ROWS = [
            ("K̄ geometric",  "All methods"),
            ("K̄ arithmetic", "All methods"),
            ("K median",      "All methods"),
            ("K std. dev.",   "Spread across methods"),
            ("Perm. class",   "Classification"),
        ]

        n_method = len(method_names)
        n_rows = n_method + len(SUMMARY_ROWS)

        self._k_table.setRowCount(n_rows)
        self._k_table.setColumnCount(1 + n_ds)

        # ── Column headers ────────────────────────────────────────────────────
        self._k_table.setHorizontalHeaderItem(0, QTableWidgetItem("Method"))
        for col_i, tab in enumerate(tabs):
            name = tab.get_dataset_name()
            color = DATASET_COLORS[col_i % len(DATASET_COLORS)]
            hdr_item = self._make_dataset_header_item(name, color)
            self._k_table.setHorizontalHeaderItem(1 + col_i, hdr_item)

        # First column stretch; data columns resize-to-contents
        self._k_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for c in range(1, 1 + n_ds):
            self._k_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents
            )

        # Build k_matrix[method_index][dataset_index] = k_value | None
        k_matrix: List[List[Optional[float]]] = []
        for method in method_names:
            row_vals = []
            for results in results_by_tab:
                match = next(
                    (r.k_value for r in results if r.method_name == method), None
                )
                row_vals.append(match)
            k_matrix.append(row_vals)

        # ── Method rows ───────────────────────────────────────────────────────
        for row_i, method in enumerate(method_names):
            vals = k_matrix[row_i]
            valid_vals = [v for v in vals if v is not None and v > 0]

            # Two-line cell widget for method name
            desc = f"K ({self._details_unit_symbol()}) · {self._K_DESCS.get(method, 'method result')}"
            method_item = _SortableTableWidgetItem(method)
            method_item.setData(Qt.ItemDataRole.UserRole, method.lower())
            self._k_table.setItem(row_i, 0, method_item)
            self._k_table.setCellWidget(
                row_i, 0, self._make_param_cell(method, desc, olive=False)
            )
            self._k_table.setRowHeight(row_i, 42)

            # Heat range (log scale across row)
            if valid_vals:
                log_vals = [math.log10(v) for v in valid_vals]
                v_min = min(log_vals)
                v_max = max(log_vals)
                v_range = v_max - v_min if v_max != v_min else 1.0
            else:
                v_min = v_max = v_range = 0.0

            for col_i, val in enumerate(vals):
                color = DATASET_COLORS[col_i % len(DATASET_COLORS)]
                if val is None or val <= 0:
                    item = _SortableTableWidgetItem("—")
                    item.setData(Qt.ItemDataRole.UserRole, float("inf"))
                    item.setForeground(QBrush(QColor(C.TEXT_MUTED)))
                else:
                    item = _SortableTableWidgetItem(self._format_k_value(val))
                    item.setData(Qt.ItemDataRole.UserRole, float(val))
                    item.setForeground(QBrush(QColor(color)))
                    if self._heat_on and v_range > 0:
                        norm = (math.log10(val) - v_min) / v_range
                        heat = _heat_color(norm)
                        item.setBackground(QBrush(heat))
                        item.setData(Qt.ItemDataRole.BackgroundRole, heat)
                item.setFont(QFont(F.MONO, F.SZ_SM))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self._k_table.setItem(row_i, 1 + col_i, item)

        # ── Build per-dataset valid K lists ───────────────────────────────────
        valid_k_per_ds: List[List[float]] = []
        for col_i in range(n_ds):
            col_vals = [
                k_matrix[ri][col_i]
                for ri in range(n_method)
                if k_matrix[ri][col_i] is not None and k_matrix[ri][col_i] > 0
            ]
            valid_k_per_ds.append(col_vals)

        # ── Summary rows ──────────────────────────────────────────────────────
        summary_bg = QColor(C.BG_LOW)
        summary_bg.setAlpha(200)

        for si, (s_label, s_desc) in enumerate(SUMMARY_ROWS):
            row_i = n_method + si
            self._k_table.setRowHeight(row_i, 42)

            is_geom = s_label == "K̄ geometric"
            detail = s_desc if s_label == "Perm. class" else f"{s_desc} · {self._details_unit_symbol()}"
            # Two-line summary label, olive-highlighted for K̄ geometric
            summary_item = _SortableTableWidgetItem(s_label)
            summary_item.setData(Qt.ItemDataRole.UserRole, s_label.lower())
            self._k_table.setItem(row_i, 0, summary_item)
            self._k_table.setCellWidget(
                row_i, 0, self._make_param_cell(s_label, detail, olive=is_geom)
            )

            for col_i, vk in enumerate(valid_k_per_ds):
                color = DATASET_COLORS[col_i % len(DATASET_COLORS)]
                if s_label == "K̄ geometric":
                    txt = self._format_k_value(float(np.exp(np.mean(np.log(vk))))) if vk else "—"
                elif s_label == "K̄ arithmetic":
                    txt = self._format_k_value(float(np.mean(vk))) if vk else "—"
                elif s_label == "K median":
                    txt = self._format_k_value(float(np.median(vk))) if vk else "—"
                elif s_label == "K std. dev.":
                    txt = self._format_k_value(float(np.std(vk))) if vk else "—"
                elif s_label == "Perm. class":
                    txt = _perm_class(float(np.exp(np.mean(np.log(vk))))) if vk else "—"
                else:
                    txt = "—"

                cell = _SortableTableWidgetItem(txt)
                cell.setBackground(QBrush(summary_bg))
                cell.setFont(QFont(F.MONO, F.SZ_SM))
                cell.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                if s_label == "Perm. class":
                    cell.setData(Qt.ItemDataRole.UserRole, txt.lower())
                elif vk:
                    if s_label == "K̄ geometric":
                        sort_val = float(np.exp(np.mean(np.log(vk))))
                    elif s_label == "K̄ arithmetic":
                        sort_val = float(np.mean(vk))
                    elif s_label == "K median":
                        sort_val = float(np.median(vk))
                    elif s_label == "K std. dev.":
                        sort_val = float(np.std(vk))
                    else:
                        sort_val = float("inf")
                    cell.setData(Qt.ItemDataRole.UserRole, sort_val)
                else:
                    cell.setData(Qt.ItemDataRole.UserRole, float("inf"))
                if s_label == "Perm. class" and vk:
                    cell.setForeground(QBrush(QColor(_perm_color(vk))))
                elif is_geom and vk:
                    # Bold colored dataset value for K̄ geometric
                    cell.setForeground(QBrush(QColor(color)))
                    bold_f = QFont(F.MONO, F.SZ_SM)
                    bold_f.setBold(True)
                    cell.setFont(bold_f)
                else:
                    cell.setForeground(QBrush(QColor(C.TEXT_MID)))
                self._k_table.setItem(row_i, 1 + col_i, cell)

        self._k_table.resizeColumnsToContents()
        self._k_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._apply_k_row_preset(method_names, SUMMARY_ROWS)
        self._k_table.setSortingEnabled(True)

    # ── Statistics tab figures ────────────────────────────────────────────────

    def _refresh_stats_dataset_strip(self) -> None:
        layout = self._stats_dataset_chips_layout
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for i, tab in enumerate(self.selected_datasets):
            name = tab.get_dataset_name()
            color = DATASET_COLORS[i % len(DATASET_COLORS)]
            chip = self._make_dataset_chip(name, color)
            layout.insertWidget(layout.count() - 1, chip)

    def _build_stats_insights(self) -> list[tuple[str, str]]:
        tabs = self.selected_datasets
        if not tabs:
            return [("No comparison data", "Select at least two datasets to populate comparison statistics.")]

        spread_stats = []
        method_names = self._ordered_k_methods(
            {r.method_name for tab in tabs for r in tab.get_results()}
        )
        issue_counts = {method: 0 for method in method_names}

        for tab in tabs:
            results = tab.get_results()
            vals = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]
            if len(vals) >= 2:
                spread = math.log10(max(vals)) - math.log10(min(vals))
                spread_stats.append((spread, tab.get_dataset_name(), min(vals), max(vals)))

            result_map = {r.method_name: r for r in results}
            for method in method_names:
                result = result_map.get(method)
                if result is None:
                    issue_counts[method] += 1
                elif result.status != CalculationStatus.OK or not getattr(result, "conditions_met", True):
                    issue_counts[method] += 1

        insights: list[tuple[str, str]] = []
        if spread_stats:
            widest = max(spread_stats, key=lambda item: item[0])
            insights.append(
                (
                    "Largest spread",
                    f"{widest[1]} spans {self._format_stats_k_value(widest[2])} to {self._format_stats_k_value(widest[3])}.",
                )
            )
            tightest = min(spread_stats, key=lambda item: item[0])
            insights.append(
                (
                    "Tightest cluster",
                    f"{tightest[1]} stays closest together across valid method results.",
                )
            )

        if issue_counts:
            caution_method, issue_count = max(issue_counts.items(), key=lambda item: item[1])
            if issue_count > 0:
                insights.append(
                    (
                        "Method caution",
                        f"{caution_method} is warned or unavailable in {issue_count} of {len(tabs)} datasets.",
                    )
                )
            else:
                insights.append(
                    (
                        "Method coverage",
                        "All represented methods are valid across the current dataset set.",
                    )
                )
        return insights[:3]

    def _refresh_stats_workspace(self) -> None:
        if not hasattr(self, "_stats_dataset_chips_layout"):
            return

        self._refresh_stats_dataset_strip()
        self._stats_metric_geo_btn.setChecked(self._stats_metric == "geometric")
        self._stats_metric_med_btn.setChecked(self._stats_metric == "median")

        metric_label = "Geo. mean" if self._stats_metric == "geometric" else "Median"
        if not self.selected_datasets:
            self._stats_context.setText("Select at least 2 datasets to compare")
            self._stats_dist_meta.setText("")
            self._stats_agreement_meta.setText("")
            self._reset_layout(self._stats_insights_layout)
            self._stats_insights_layout.addWidget(
                self._make_stats_insight_row("No comparison data", "Select at least two datasets to populate comparison statistics.")
            )
            self._reset_layout(self._stats_summary_layout)
            self._stats_summary_layout.addWidget(self._make_stats_summary_row("Selected metric", metric_label))
            self._stats_summary_layout.addWidget(self._make_stats_summary_row("Unit", self._stats_unit_symbol()))
            return

        method_names = self._ordered_k_methods(
            {r.method_name for tab in self.selected_datasets for r in tab.get_results()}
        )
        total_cells = len(self.selected_datasets) * len(method_names)
        valid_count = 0
        warning_count = 0
        missing_count = 0
        for tab in self.selected_datasets:
            result_map = {r.method_name: r for r in tab.get_results()}
            for method in method_names:
                result = result_map.get(method)
                if result is None:
                    missing_count += 1
                elif result.status == CalculationStatus.OK and getattr(result, "k_value", None) is not None and result.k_value > 0:
                    valid_count += 1
                elif result.status == CalculationStatus.WARNING:
                    warning_count += 1
                else:
                    missing_count += 1

        self._stats_context.setText(
            f"{len(self.selected_datasets)} datasets · {self._scheme_label()} · {self._stats_unit_symbol()} · {metric_label}"
        )
        self._stats_dist_meta.setText(metric_label)
        self._stats_agreement_meta.setText(f"{len(method_names)} methods")

        self._reset_layout(self._stats_insights_layout)
        for title, body in self._build_stats_insights():
            self._stats_insights_layout.addWidget(self._make_stats_insight_row(title, body))

        self._reset_layout(self._stats_summary_layout)
        for label, value in [
            ("Selected metric", metric_label),
            ("Unit", self._stats_unit_symbol()),
            ("Methods represented", str(len(method_names))),
            ("Valid coverage", f"{valid_count} / {total_cells}" if total_cells else "0"),
            ("Warned cells", str(warning_count)),
            ("Missing cells", str(missing_count)),
        ]:
            self._stats_summary_layout.addWidget(self._make_stats_summary_row(label, value))

    def _refresh_stats(self) -> None:
        """Redraw both matplotlib statistics figures."""
        self._refresh_stats_workspace()
        self._draw_boxplot()
        self._draw_heatmap()

    def _draw_boxplot(self) -> None:
        """K-value box plots — one box per dataset, log y-axis."""
        self._box_fig.clear()
        ax = self._box_fig.add_subplot(111)
        ax.set_facecolor("#fbf8f2")

        tabs = self.selected_datasets
        data_per_ds = []
        labels = []
        colors = []

        for i, tab in enumerate(tabs):
            results = tab.get_results()
            vals_m_s = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]
            vals = [
                HydraulicConductivityConverter.convert_from_m_per_s(v, self._stats_k_unit)
                for v in vals_m_s
            ]
            data_per_ds.append(vals)
            labels.append(self._short_dataset_name(tab.get_dataset_name(), max_width=88))
            colors.append(DATASET_COLORS[i % len(DATASET_COLORS)])

        if not any(data_per_ds):
            ax.text(
                0.5, 0.5, "No K data available",
                ha="center", va="center", transform=ax.transAxes,
                color=C.TEXT_MUTED, fontsize=11,
            )
            self._box_canvas.draw()
            return

        # Filter to datasets that have data
        plot_data = [(d, l, c) for d, l, c in zip(data_per_ds, labels, colors) if d]
        if not plot_data:
            self._box_canvas.draw()
            return

        p_data, p_labels, p_colors = zip(*plot_data)

        bp = ax.boxplot(
            p_data,
            tick_labels=p_labels,
            patch_artist=True,
            medianprops={"color": C.TEXT, "linewidth": 1.5},
            whiskerprops={"color": C.BORDER_DK, "linewidth": 1.0},
            capprops={"color": C.BORDER_DK, "linewidth": 1.0},
            flierprops={"marker": "o", "markersize": 4, "alpha": 0.6},
        )
        for patch, color in zip(bp["boxes"], p_colors):
            qc = QColor(color)
            patch.set_facecolor(
                (qc.red() / 255, qc.green() / 255, qc.blue() / 255, 0.24)
            )
            patch.set_edgecolor(color)
            patch.set_linewidth(1.2)

        marker_values = []
        for vals in p_data:
            if self._stats_metric == "median":
                marker_values.append(float(np.median(vals)))
            else:
                marker_values.append(float(np.exp(np.mean(np.log(vals)))))
        x_positions = list(range(1, len(p_data) + 1))
        ax.scatter(
            x_positions,
            marker_values,
            marker="D",
            s=34,
            color="#433528",
            edgecolors="white",
            linewidths=0.8,
            zorder=4,
        )

        ax.set_yscale("log")
        ax.set_ylabel(f"K ({self._stats_unit_symbol()})", color=C.TEXT_MID, fontsize=10)
        ax.set_title("K-value Distribution", color=C.TEXT_MID, fontsize=11, fontweight="600")
        ax.tick_params(axis="x", labelrotation=0, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
        for idx, tick_lbl in enumerate(ax.get_xticklabels()):
            tick_lbl.set_color(p_colors[idx % len(p_colors)])
        ax.grid(True, which="both", linestyle="--", alpha=0.38, color=C.BORDER)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.text(
            0.99, 0.98,
            f"Marker: {'Geo. mean' if self._stats_metric == 'geometric' else 'Median'}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color=C.TEXT_MUTED,
            family=F.MONO,
        )

        self._box_canvas.draw()

    def _draw_heatmap(self) -> None:
        """Method applicability heatmap (methods × datasets).

        Three cell states driven by CalculationStatus:
          OK      (2) — pale green   — valid K result
          WARNING (1) — amber        — K result outside applicability range
          N/A     (0) — pale beige   — method not applicable / failed
        """
        self._heat_fig.clear()
        ax = self._heat_fig.add_subplot(111)
        ax.set_facecolor("#fbf8f2")

        tabs = self.selected_datasets
        results_by_tab = [tab.get_results() for tab in tabs]
        method_names = self._ordered_k_methods(
            {r.method_name for results in results_by_tab for r in results}
        )
        ds_names = [self._short_dataset_name(tab.get_dataset_name(), max_width=84) for tab in tabs]

        if not method_names or not ds_names:
            ax.text(
                0.5, 0.5, "No method data available",
                ha="center", va="center", transform=ax.transAxes,
                color=C.TEXT_MUTED,
            )
            self._heat_canvas.draw()
            return

        # Build status matrix: 2=OK, 1=WARNING, 0=N/A
        matrix = np.zeros((len(method_names), len(ds_names)))
        for ci, results in enumerate(results_by_tab):
            result_map = {r.method_name: r for r in results}
            for ri, method in enumerate(method_names):
                if method in result_map:
                    r = result_map[method]
                    if r.status == CalculationStatus.OK:
                        matrix[ri, ci] = 2.0
                    elif r.status == CalculationStatus.WARNING:
                        matrix[ri, ci] = 1.0
                    # ERROR stays 0.0

        def _hex_to_rgba(hex_color: str, alpha: float) -> tuple:
            qc = QColor(hex_color)
            return (qc.red() / 255, qc.green() / 255, qc.blue() / 255, alpha)

        ok_rgba = _hex_to_rgba("#dbe8c0", 1.0)
        warn_rgba = _hex_to_rgba("#d99a3a", 1.0)
        absent_rgba = _hex_to_rgba("#ece5da", 1.0)

        cmap_data = np.zeros((*matrix.shape, 4))
        for ri in range(len(method_names)):
            for ci in range(len(ds_names)):
                v = matrix[ri, ci]
                if v >= 2.0:
                    cmap_data[ri, ci] = ok_rgba
                elif v >= 1.0:
                    cmap_data[ri, ci] = warn_rgba
                else:
                    cmap_data[ri, ci] = absent_rgba

        ax.imshow(cmap_data, aspect="auto", interpolation="nearest", origin="upper")

        ax.set_xticks(range(len(ds_names)))
        ax.set_xticklabels(ds_names, rotation=18, ha="right", fontsize=8)
        ax.set_yticks(range(len(method_names)))
        ax.set_yticklabels(method_names, fontsize=8)
        ax.set_title(
            "Method Agreement & Applicability", color=C.TEXT_MID, fontsize=11, fontweight="600"
        )

        # Add crisp cell separators so the matrix reads as a table, not a color slab.
        ax.set_xticks(np.arange(-0.5, len(ds_names), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(method_names), 1), minor=True)
        ax.grid(which="minor", color="#fbf8f2", linestyle="-", linewidth=1.2)
        ax.tick_params(which="minor", bottom=False, left=False)

        # Overlay only warning / unavailable markers; OK cells stay visually clean.
        for ri in range(len(method_names)):
            for ci in range(len(ds_names)):
                v = matrix[ri, ci]
                if v >= 2.0:
                    continue
                if v >= 1.0:
                    ax.text(
                        ci, ri, "!",
                        ha="center", va="center",
                        fontsize=9, fontweight="700", color="white",
                    )
                else:
                    ax.text(
                        ci, ri, "—",
                        ha="center", va="center",
                        fontsize=9, color="#8e816f",
                    )

        # Color x-tick labels per dataset color
        for ci, tick_lbl in enumerate(ax.get_xticklabels()):
            tick_lbl.set_color(DATASET_COLORS[ci % len(DATASET_COLORS)])

        ax.spines[:].set_visible(False)
        ax.tick_params(length=0)
        ax.tick_params(axis="x", pad=6)
        ax.tick_params(axis="y", pad=4)

        self._heat_canvas.draw()

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_plot(self) -> None:
        """Save the comparison plot (Plot tab canvas) as PNG or SVG."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Comparison Plot",
            "comparison.png",
            "PNG Image (*.png);;SVG Vector (*.svg)",
        )
        if not path:
            return
        try:
            if hasattr(self._plot_widget, "figure"):
                self._plot_widget.figure.savefig(path, dpi=300, bbox_inches="tight")
            elif hasattr(self._plot_widget, "_fig"):
                self._plot_widget._fig.savefig(path, dpi=300, bbox_inches="tight")
            elif hasattr(self._plot_widget, "canvas") and hasattr(
                self._plot_widget.canvas, "figure"
            ):
                self._plot_widget.canvas.figure.savefig(
                    path, dpi=300, bbox_inches="tight"
                )
        except Exception as exc:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Export Failed",
                f"Could not save plot:\n{exc}",
            )

    def export_comparison(self) -> None:
        """Public alias kept for main_window.py compatibility."""
        self._export_plot()
