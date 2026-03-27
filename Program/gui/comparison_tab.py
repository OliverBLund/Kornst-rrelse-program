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
    QScrollArea, QSizePolicy, QFileDialog, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QFont, QBrush, QPixmap, QPainter, QIcon

# ── Internal ──────────────────────────────────────────────────────────────────
from .matplotlib_canvas import FigureCanvas
from .comparison_plot_widget import ComparisonPlotWidget
from .theme import C, F, icon as theme_icon
from k_calculations_v2 import CalculationStatus
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
    """Map norm ∈ [0, 1] to a semi-transparent heat color (alpha=70).

    0.0  → green  (0, 180, 80)
    0.5  → yellow (220, 180, 80)
    1.0  → red    (220, 0, 80)
    """
    norm = max(0.0, min(1.0, norm))
    if norm <= 0.5:
        t = norm / 0.5          # 0→1
        r = int(0 + t * 220)    # 0 → 220
        g = 180
        b = 80
    else:
        t = (norm - 0.5) / 0.5  # 0→1
        r = 220
        g = int(180 - t * 180)  # 180 → 0
        b = 80
    return QColor(r, g, b, 70)


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

    def __init__(self, parent=None):
        super().__init__(parent)

        self.dataset_tabs: list = []
        self.selected_datasets: list = []
        self._pinned: set[str] = set()
        self._heat_on: bool = True
        self._active_scheme = ISO14688

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
            (self._build_details_tab(),    "Details",    "fa6s.table"),
            (self._build_statistics_tab(), "Statistics", "fa6s.chart-bar"),
        ]:
            try:
                self._tabs.addTab(page, theme_icon(fa_name, C.TEXT_MUTED), label)
            except Exception:
                self._tabs.addTab(page, label)
        self._tabs.setIconSize(QSize(12, 12))

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

        # Manage Datasets button (placeholder)
        self._manage_btn = QPushButton("Manage Datasets")
        self._manage_btn.setFixedHeight(28)
        try:
            self._manage_btn.setIcon(theme_icon("fa6s.list-check", C.TEXT_MID))
            self._manage_btn.setIconSize(QSize(11, 11))
        except Exception:
            pass
        self._manage_btn.setEnabled(False)
        self._manage_btn.setToolTip("Coming soon — manage which datasets appear in comparison")
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
        """Rebuild the pin-list rows from self.dataset_tabs."""
        # Remove all except the trailing stretch
        while self._pin_list_layout.count() > 1:
            item = self._pin_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, tab in enumerate(self.dataset_tabs):
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

    # ── Statistics tab ────────────────────────────────────────────────────────

    def _build_statistics_tab(self) -> QWidget:
        """Statistics tab: two matplotlib figures side-by-side."""
        page = QWidget()
        h = QHBoxLayout(page)
        h.setContentsMargins(12, 12, 12, 12)
        h.setSpacing(12)

        fc = C.BG  # figure facecolor

        # K-value box plot
        self._box_fig = Figure(figsize=(8, 5), facecolor=fc, tight_layout=True)
        self._box_canvas = FigureCanvas(self._box_fig)
        self._box_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Method heatmap
        self._heat_fig = Figure(figsize=(8, 5), facecolor=fc, tight_layout=True)
        self._heat_canvas = FigureCanvas(self._heat_fig)
        self._heat_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        h.addWidget(self._box_canvas, 1)
        h.addWidget(self._heat_canvas, 1)
        return page

    # ── Data wiring ───────────────────────────────────────────────────────────

    def set_scheme(self, scheme) -> None:
        """Update active classification scheme and refresh if data present."""
        self._active_scheme = scheme
        if len(self.dataset_tabs) >= 2:
            self.update_comparison()

    def set_dataset_tabs(self, dataset_tabs) -> None:
        """Called by main_window whenever the dataset tab list changes.

        Args:
            dataset_tabs: list of dataset tab objects exposing
                          get_dataset(), get_dataset_name(), get_results()
        """
        self.dataset_tabs = dataset_tabs
        self.selected_datasets = list(dataset_tabs)
        self._pinned = {t.get_dataset_name() for t in dataset_tabs}
        self._refresh_pin_list()
        self._update_header_count()

        enabled = len(dataset_tabs) >= 2
        self._update_btn.setEnabled(enabled)
        self._export_btn.setEnabled(enabled)

        if enabled:
            self.update_comparison()

    def update_comparison(self) -> None:
        """Refresh all views from current dataset_tabs.  Public API."""
        self.selected_datasets = list(self.dataset_tabs)
        if len(self.selected_datasets) < 2:
            return
        self._update_plot()
        self._refresh_grain_table()
        self._refresh_k_table()
        self._refresh_stats()
        self._update_header_count()
        self.comparison_updated.emit()

    # ── Internal update helpers ───────────────────────────────────────────────

    def _update_header_count(self) -> None:
        n = len(self.dataset_tabs)
        n_pinned = len(self._pinned)
        if n == 0:
            self._count_label.setText("Load datasets to compare")
        else:
            self._count_label.setText(
                f"{n} selected  ·  {n_pinned} pinned in view  ·  pin/unpin in the dataset panel"
            )
        self._manage_btn.setEnabled(n >= 1)

    def _on_manage_datasets(self) -> None:
        """Placeholder — will open a dataset manager dialog."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Coming Soon",
            "Dataset manager — select which loaded datasets to include "
            "in the comparison.\n\nFor now, use the sidebar toggle (☑) on each "
            "sample card to control what appears here."
        )

    def _update_plot(self) -> None:
        """Push datasets into the comparison plot widget."""
        if not self.selected_datasets:
            if hasattr(self._plot_widget, "show_empty_state"):
                self._plot_widget.show_empty_state("Select datasets and click Update")
            return
        self._plot_widget.set_datasets(self.selected_datasets)
        if hasattr(self._plot_widget, "refresh_plot"):
            self._plot_widget.refresh_plot()

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
        """Classify gradation as Uniform / Moderately graded / Well-graded from Cu."""
        cu = dataset.get_uniformity_coefficient()
        return _gc_cu_label(cu)

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

    def _refresh_grain_table(self) -> None:
        """Rebuild the grain parameters table."""
        tabs = self.selected_datasets
        n_ds = len(tabs)
        n_rows = len(self._GRAIN_ROWS)

        # Column layout: Parameter | DS0 | DS1 | …
        self._grain_table.setRowCount(n_rows)
        self._grain_table.setColumnCount(1 + n_ds)

        # ── Column headers ────────────────────────────────────────────────────
        self._grain_table.setHorizontalHeaderItem(0, QTableWidgetItem("Parameter"))
        for col_i, tab in enumerate(tabs):
            name = tab.get_dataset_name()
            color = DATASET_COLORS[col_i % len(DATASET_COLORS)]
            hdr_item = QTableWidgetItem(name)
            hdr_item.setIcon(_dot_icon(color))
            hdr_item.setForeground(QBrush(QColor(color)))
            font = QFont(F.UI, F.SZ_SM)
            font.setBold(True)
            hdr_item.setFont(font)
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
            self._grain_table.setCellWidget(
                row_i, 0, self._make_param_cell(label, tooltip, olive)
            )
            self._grain_table.setRowHeight(row_i, 42)

            if is_text:
                if label == "Classif.":
                    for col_i, tab in enumerate(tabs):
                        val_str = tab.get_dataset().classify(scheme=self._active_scheme).label or "—"
                        color = DATASET_COLORS[col_i % len(DATASET_COLORS)]
                        item = QTableWidgetItem(val_str)
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
                        item = QTableWidgetItem(val_str)
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
                    item = QTableWidgetItem("—")
                    item.setForeground(QBrush(QColor(C.TEXT_MUTED)))
                else:
                    item = QTableWidgetItem(f"{val:.4g}")
                    item.setForeground(QBrush(QColor(color)))
                    if self._heat_on and v_range > 0:
                        norm = (val - v_min) / v_range
                        item.setBackground(QBrush(_heat_color(norm)))
                item.setFont(QFont(F.MONO, F.SZ_SM))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self._grain_table.setItem(row_i, 1 + col_i, item)

        self._grain_table.resizeColumnsToContents()
        self._grain_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )

    # ── Hydraulic conductivity table ──────────────────────────────────────────

    # ── K-value descriptions (method name → short description) ───────────────
    _K_DESCS: dict = {
        "Hazen":         "K (m/s)  ·  based on D10",
        "Kozeny-Carman": "K (m/s)  ·  pore structure",
        "USBR":          "K (m/s)  ·  Bureau of Reclamation",
        "Terzaghi":      "K (m/s)  ·  sandy soils",
        "Slichter":      "K (m/s)  ·  uniform sands",
        "Beyer":         "K (m/s)  ·  non-uniform sands",
        "Seelheim":      "K (m/s)  ·  D10 based",
        "Pavchich":      "K (m/s)  ·  coarse sands",
    }

    def _refresh_k_table(self) -> None:
        """Rebuild the hydraulic conductivity comparison table."""
        tabs = self.selected_datasets
        n_ds = len(tabs)

        # Collect all results per dataset
        results_by_tab = [tab.get_results() for tab in tabs]

        # Gather unique method names (sorted alphabetically)
        method_names: list[str] = sorted(
            {r.method_name for results in results_by_tab for r in results}
        )

        # Summary rows appended at the bottom
        SUMMARY_ROWS = [
            ("K̄ geometric",  "All methods · m/s"),
            ("K̄ arithmetic", "All methods · m/s"),
            ("K median",      "All methods · m/s"),
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
            hdr_item = QTableWidgetItem(name)
            hdr_item.setIcon(_dot_icon(color))
            hdr_item.setForeground(QBrush(QColor(color)))
            font = QFont(F.UI, F.SZ_SM)
            font.setBold(True)
            hdr_item.setFont(font)
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
            desc = self._K_DESCS.get(method, "K (m/s)")
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
                    item = QTableWidgetItem("—")
                    item.setForeground(QBrush(QColor(C.TEXT_MUTED)))
                else:
                    item = QTableWidgetItem(f"{val:.2e}")
                    item.setForeground(QBrush(QColor(color)))
                    if self._heat_on and v_range > 0:
                        norm = (math.log10(val) - v_min) / v_range
                        item.setBackground(QBrush(_heat_color(norm)))
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
            # Two-line summary label, olive-highlighted for K̄ geometric
            self._k_table.setCellWidget(
                row_i, 0, self._make_param_cell(s_label, s_desc, olive=is_geom)
            )

            for col_i, vk in enumerate(valid_k_per_ds):
                color = DATASET_COLORS[col_i % len(DATASET_COLORS)]
                if s_label == "K̄ geometric":
                    txt = f"{float(np.exp(np.mean(np.log(vk)))):.2e}" if vk else "—"
                elif s_label == "K̄ arithmetic":
                    txt = f"{float(np.mean(vk)):.2e}" if vk else "—"
                elif s_label == "K median":
                    txt = f"{float(np.median(vk)):.2e}" if vk else "—"
                elif s_label == "K std. dev.":
                    txt = f"{float(np.std(vk)):.2e}" if vk else "—"
                elif s_label == "Perm. class":
                    txt = _perm_class(float(np.exp(np.mean(np.log(vk))))) if vk else "—"
                else:
                    txt = "—"

                cell = QTableWidgetItem(txt)
                cell.setBackground(QBrush(summary_bg))
                cell.setFont(QFont(F.MONO, F.SZ_SM))
                cell.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
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

    # ── Statistics tab figures ────────────────────────────────────────────────

    def _refresh_stats(self) -> None:
        """Redraw both matplotlib statistics figures."""
        self._draw_boxplot()
        self._draw_heatmap()

    def _draw_boxplot(self) -> None:
        """K-value box plots — one box per dataset, log y-axis."""
        self._box_fig.clear()
        ax = self._box_fig.add_subplot(111)
        ax.set_facecolor("#ffffff")

        tabs = self.selected_datasets
        data_per_ds = []
        labels = []
        colors = []

        for i, tab in enumerate(tabs):
            results = tab.get_results()
            vals = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]
            data_per_ds.append(vals)
            labels.append(tab.get_dataset_name())
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
            labels=p_labels,
            patch_artist=True,
            medianprops={"color": C.TEXT, "linewidth": 1.5},
            whiskerprops={"color": C.BORDER_DK, "linewidth": 1.0},
            capprops={"color": C.BORDER_DK, "linewidth": 1.0},
            flierprops={"marker": "o", "markersize": 4, "alpha": 0.6},
        )
        for patch, color in zip(bp["boxes"], p_colors):
            qc = QColor(color)
            patch.set_facecolor(
                (qc.red() / 255, qc.green() / 255, qc.blue() / 255, 0.30)
            )
            patch.set_edgecolor(color)

        ax.set_yscale("log")
        ax.set_ylabel("K (m/s)", color=C.TEXT_MID, fontsize=10)
        ax.set_title("K-value Distribution", color=C.TEXT_MID, fontsize=11, fontweight="600")
        ax.tick_params(axis="x", labelrotation=20, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(True, which="both", linestyle="--", alpha=0.5, color=C.BORDER)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        self._box_canvas.draw()

    def _draw_heatmap(self) -> None:
        """Method applicability heatmap (methods × datasets).

        Three cell states driven by CalculationStatus:
          OK      (2) — olive green  — valid K result
          WARNING (1) — amber        — K result outside applicability range
          N/A     (0) — light beige  — method not applicable / failed
        """
        self._heat_fig.clear()
        ax = self._heat_fig.add_subplot(111)
        ax.set_facecolor("#ffffff")

        tabs = self.selected_datasets
        results_by_tab = [tab.get_results() for tab in tabs]
        method_names = sorted(
            {r.method_name for results in results_by_tab for r in results}
        )
        ds_names = [tab.get_dataset_name() for tab in tabs]

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

        # Precompute RGBAs
        def _hex_to_rgba(hex_color: str, alpha: float) -> tuple:
            qc = QColor(hex_color)
            return (qc.red() / 255, qc.green() / 255, qc.blue() / 255, alpha)

        ok_rgba      = _hex_to_rgba(C.OLIVE,    0.85)
        warn_rgba    = _hex_to_rgba(C.LED_WARN, 0.85)
        absent_rgba  = (0.90, 0.89, 0.87, 0.45)

        # Build RGBA image
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

        ax.imshow(cmap_data, aspect="auto", interpolation="nearest")

        ax.set_xticks(range(len(ds_names)))
        ax.set_xticklabels(ds_names, rotation=25, ha="right", fontsize=8)
        ax.set_yticks(range(len(method_names)))
        ax.set_yticklabels(method_names, fontsize=8)
        ax.set_title(
            "Method Applicability", color=C.TEXT_MID, fontsize=11, fontweight="600"
        )

        # Overlay status symbols
        symbols   = {2.0: "✓", 1.0: "⚠", 0.0: "—"}
        txt_colors = {2.0: "white", 1.0: "white", 0.0: C.TEXT_MUTED}
        for ri in range(len(method_names)):
            for ci in range(len(ds_names)):
                v = matrix[ri, ci]
                key = 2.0 if v >= 2.0 else (1.0 if v >= 1.0 else 0.0)
                ax.text(ci, ri, symbols[key], ha="center", va="center",
                        fontsize=9, color=txt_colors[key])

        # Color x-tick labels per dataset color
        for ci, tick_lbl in enumerate(ax.get_xticklabels()):
            tick_lbl.set_color(DATASET_COLORS[ci % len(DATASET_COLORS)])

        ax.spines[:].set_visible(False)
        ax.tick_params(length=0)

        # Legend
        import matplotlib.patches as mpatches
        legend_patches = [
            mpatches.Patch(color=C.OLIVE,    alpha=0.85, label="OK"),
            mpatches.Patch(color=C.LED_WARN, alpha=0.85, label="Warning"),
            mpatches.Patch(color="#e5e1db",  alpha=0.80, label="N/A"),
        ]
        ax.legend(
            handles=legend_patches, loc="upper right",
            fontsize=7, framealpha=0.9,
            edgecolor=C.BORDER, facecolor=C.BG_RAISED,
        )

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
