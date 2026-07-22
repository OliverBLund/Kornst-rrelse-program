"""
comparison_tab.py — Multi-dataset comparison tab for Grain Size Analyser.

Provides side-by-side comparison of grain size parameters, hydraulic
conductivity estimates, and statistical summaries for 2+ datasets.

Layout:
    ┌─ Header bar (44px) ───────────────────────────────────────────┐
    │  "Batch Comparison"   N selected / loaded datasets              │
    └───────────────────────────────────────────────────────────────┘
    ┌─ QTabWidget ──────────────────────────────────────────────────┐
    │  [Plot] [Details] [Statistics]                                 │
    └───────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import math
import os
from typing import List, Optional

import numpy as np
from analysis.comparison_snapshot import (
    ComparisonSnapshotOptions,
    build_comparison_snapshot,
)
from grain_classification import (
    ISO14688,
)
from grain_classification import (
    cu_label as _gc_cu_label,
)
from grain_classification import (
    interpolate_at as _interpolate_at,
)
from grain_classification import (
    permeability_class as _gc_perm_class,
)
from method_registry import DEFAULT_METHOD_ORDER
from exporting.table_model import ExportTable
from k_aggregation import UNGROUPED_LABEL, KAggregationOptions, dataset_group_name, normalize_group_name
from k_calculations_v2 import CalculationStatus
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from PyQt6.QtCore import QMimeData, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QDrag, QFont, QFontMetrics, QIcon, QPainter, QPixmap

# ── PyQt6 ─────────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from .table_export_dialog import export_table_dialog
from unit_conversions import (
    HydraulicConductivityConverter,
    HydraulicConductivityUnit,
    get_default_plot_unit,
)

from .comparison_plot_widget import ComparisonPlotWidget
from .group_styles import (
    dataset_line_style,
    dataset_series_key,
    default_line_style,
    group_color_map,
    line_style_label,
)
from .sidebar_controls import LineStylePreview

# ── Internal ──────────────────────────────────────────────────────────────────
from .matplotlib_canvas import FigureCanvas
from .stack_fade import TabFadeInController
from .theme import C, F
from .theme import icon as theme_icon


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


def _sync_segment_button(btn: QPushButton, on: bool) -> None:
    """Refresh stylesheet/icon state for small segmented toolbar buttons."""
    btn.setProperty("active", on)
    icon_name = btn.property("iconName")
    if icon_name:
        btn.setIcon(theme_icon(str(icon_name), C.OLIVE if on else C.TEXT_MID, size=12))
    btn.style().unpolish(btn)
    btn.style().polish(btn)


_SORT_VALUE_ROLE = Qt.ItemDataRole.UserRole
_SORT_GROUP_ROLE = Qt.ItemDataRole.UserRole.value + 1
_SORT_PINNED_ORDER_ROLE = Qt.ItemDataRole.UserRole.value + 2

_SEGMENT_TOOLTIPS = {
    "Individual": "Show one row per selected dataset.",
    "Aggregate": "Show statistics aggregated across the selected datasets and groups.",
    "Grain": "Show grain-size distribution and classification fields.",
    "K-values": "Show hydraulic-conductivity results and method summaries.",
    "Summary": "Show the compact set of key result rows.",
    "All rows": "Show every available detail row for the current data type.",
    "Classification": "Show classification and interpretation context rows.",
    "Aggregate rows": "Show aggregate summary rows rather than method-by-method rows.",
    "K spread": "Compare the distribution and agreement of included K values.",
    "Coverage": "Show where active K methods are OK, warned, or unavailable.",
    "Geo. mean": "Use the geometric mean of positive included K values; recommended for log-distributed K data.",
    "Arith. mean": "Use the ordinary arithmetic average of positive included K values.",
    "Median": "Use the middle positive included K value.",
    "All active": "Consider every workspace-active K method; the status filter still controls which values contribute.",
    "Valid in all": "Keep only methods with an includable result for every selected dataset.",
    "Choose": "Choose the workspace-wide active K methods used in Results, plots, comparison, reports, and exports.",
    "OK only": "Include only positive K results with OK status and satisfied applicability conditions.",
    "Warnings": "Also include positive warning-status K results; errors remain excluded.",
}
_DETAILS_ROW_HEADER_WIDTH = 210
_DETAILS_ROW_HEIGHT = 48
_DETAILS_SUMMARY_ROW_HEIGHT = 50
_PLOT_DATASET_MIME = 'application/x-grainsize-plot-dataset'


class _PlotGroupDropArea(QFrame):
    """Full Plot Visibility group area used as a drop target."""

    datasets_dropped = pyqtSignal(object, str)

    def __init__(self, group_name: str, parent=None):
        super().__init__(parent)
        self.group_name = group_name
        self.setObjectName('plotGroupDropArea')
        self.setAcceptDrops(True)
        self.setToolTip(f'Drop a sample anywhere here to move it to {group_name}.')
        self._set_drop_active(False)

    def _set_drop_active(self, active: bool) -> None:
        self.setStyleSheet(
            'QFrame#plotGroupDropArea {'
            f'background: {"rgba(107,142,35,0.12)" if active else "transparent"};'
            f'border: {"2px" if active else "1px"} solid '
            f'{C.OLIVE if active else C.BORDER}; border-radius: 6px;'
            '}'
        )

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(_PLOT_DATASET_MIME):
            self._set_drop_active(True)
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(_PLOT_DATASET_MIME):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_drop_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._set_drop_active(False)
        payload = bytes(event.mimeData().data(_PLOT_DATASET_MIME)).decode('utf-8').strip()
        try:
            decoded = json.loads(payload)
            names = decoded if isinstance(decoded, list) else [decoded]
        except (json.JSONDecodeError, TypeError):
            names = [payload]
        names = [str(name).strip() for name in names if str(name).strip()]
        if not names:
            event.ignore()
            return
        self.datasets_dropped.emit(names, self.group_name)
        event.acceptProposedAction()


class _PlotDatasetDragRow(QFrame):
    """Dataset row whose body starts a group-assignment drag."""

    selection_requested = pyqtSignal(str, object)
    drag_requested = pyqtSignal(object)

    def __init__(self, dataset_name: str, parent=None):
        super().__init__(parent)
        self.dataset_name = dataset_name
        self._drag_start_position: QPoint | None = None
        self._base_background = 'transparent'
        self.setObjectName('plotDatasetDragRow')
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(
            'Click to select. Ctrl-click or Shift-click selects multiple samples; '
            'drag the selection into any group area.'
        )

    def set_selection_style(self, selected: bool, base_background: str | None = None) -> None:
        if base_background is not None:
            self._base_background = base_background
        background = 'rgba(107,142,35,0.15)' if selected else self._base_background
        border = f'1px solid {C.OLIVE}' if selected else '1px solid transparent'
        self.setStyleSheet(
            'QFrame#plotDatasetDragRow {'
            f'background: {background}; border: {border}; border-radius: 4px;'
            '}'
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.position().toPoint()
            self.selection_requested.emit(self.dataset_name, event.modifiers())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            self._drag_start_position is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._drag_start_position).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            self._drag_start_position = None
            self.drag_requested.emit(self)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start_position = None
        super().mouseReleaseEvent(event)


class _SortableTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem with explicit sort-role precedence."""

    def __lt__(self, other):
        lhs_group = self.data(_SORT_GROUP_ROLE)
        rhs_group = other.data(_SORT_GROUP_ROLE) if other is not None else None
        if lhs_group is not None and rhs_group is not None and lhs_group != rhs_group:
            table = self.tableWidget()
            order = (
                table.horizontalHeader().sortIndicatorOrder()
                if table is not None
                else Qt.SortOrder.AscendingOrder
            )
            # Keep numeric/method rows above classification/summary rows in both sort directions.
            return (
                lhs_group > rhs_group
                if order == Qt.SortOrder.DescendingOrder
                else lhs_group < rhs_group
            )

        lhs_pinned = self.data(_SORT_PINNED_ORDER_ROLE)
        rhs_pinned = other.data(_SORT_PINNED_ORDER_ROLE) if other is not None else None
        if (
            lhs_group not in (None, 0)
            and lhs_pinned is not None
            and rhs_pinned is not None
        ):
            table = self.tableWidget()
            order = (
                table.horizontalHeader().sortIndicatorOrder()
                if table is not None
                else Qt.SortOrder.AscendingOrder
            )
            return (
                lhs_pinned > rhs_pinned
                if order == Qt.SortOrder.DescendingOrder
                else lhs_pinned < rhs_pinned
            )

        lhs = self.data(Qt.ItemDataRole.UserRole)
        rhs = other.data(Qt.ItemDataRole.UserRole) if other is not None else None
        if lhs is not None and rhs is not None:
            try:
                return lhs < rhs
            except TypeError:
                return str(lhs) < str(rhs)
        return super().__lt__(other)


# ── Dataset color palette (warm-earth, consistent with design spec) ────────────
# Single source of truth lives in plot_constants so the Comparison tab, the plot
# widget and the headless report/export spec builder all share one palette and
# their colours match. Re-exported here under the original name for the existing
# references in this module.
from .plot_constants import DATASET_COLORS


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
    "Very High (Gravel)": "#2e7d32",  # dark green
    "High (Clean Sand)": "#558b2f",  # olive green
    "Moderate (Fine Sand)": "#f57f17",  # amber
    "Low (Silt)": "#e65100",  # deep orange
    "Very Low (Clay-Silt)": "#b71c1c",  # dark red
    "Practically Impermeable (Clay)": "#7b1fa2",  # deep purple
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
            f"background: {C.BG_LOW};border-bottom: 2px solid {C.BORDER_DK};"
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
    # Emitted by method-scope shortcut buttons.
    method_selection_requested = pyqtSignal()
    group_assignments_changed = pyqtSignal(dict)

    # ── Grain parameter definitions ──────────────────────────────────────────
    # (label, tooltip, bold, olive-highlight)
    _GRAIN_ROWS = [
        ("D10", "Effective size (mm)", True, True),
        ("D16", "16th percentile (mm)", False, False),
        ("D30", "30th percentile (mm)", True, True),
        ("D50", "Median (mm)", True, True),
        ("Dmean", "Arithmetic mean size (mm)", False, False),
        ("D60", "60th percentile (mm)", True, True),
        ("D84", "84th percentile (mm)", False, False),
        ("D90", "90th percentile (mm)", False, False),
        ("D95", "95th percentile (mm)", False, False),
        ("Cu", "Uniformity coeff. D60/D10", True, True),
        ("Cc", "Curvature coeff.", True, True),
        ("σ", "Sorting coeff. √(D84/D16)", False, False),
        ("Fines%", "% passing 0.063 mm", False, False),
        ("Classif.", "Soil classification (active scheme)", False, False),
        ("Class", "Gradation class", False, False),
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
    _K_METHOD_ORDER = list(DEFAULT_METHOD_ORDER)
    _PLOT_VISIBILITY_NAME_WIDTH = 86

    def __init__(self, parent=None):
        super().__init__(parent)

        self.dataset_tabs: list = []
        self.selected_datasets: list = []
        self._plot_hidden: set[str] = set()
        self._plot_group_selection: set[str] = set()
        self._plot_group_selection_anchor: str | None = None
        self._heat_on: bool = False
        self._active_scheme = ISO14688
        self._details_mode: str = "grain"
        self._details_view_mode: str = "individual"
        self._details_grain_preset: str = "core"
        self._details_k_preset: str = "all"
        self._details_preset: str = self._details_grain_preset
        self._details_k_unit: HydraulicConductivityUnit = get_default_plot_unit()
        self._stats_k_unit: HydraulicConductivityUnit = get_default_plot_unit()
        self._stats_view_mode: str = "spread"
        self._stats_metric: str = "geometric"
        self._stats_include_warnings: bool = False
        self._stats_common_methods_only: bool = False
        self._stats_method_scope: str = "all"

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
            (self._build_plot_tab(), "Plot", "fa6s.chart-area"),
            (self._build_details_tab_v2(), "Details", "fa6s.table"),
            (self._build_statistics_tab(), "Statistics", "fa6s.chart-bar"),
        ]:
            try:
                self._tabs.addTab(page, theme_icon(fa_name, C.TEXT_MUTED), label)
            except Exception:
                self._tabs.addTab(page, label)
        self._tabs.setIconSize(QSize(12, 12))
        self._tabs.currentChanged.connect(self._on_comparison_subtab_changed)
        self._tabs_fader = TabFadeInController(
            self._tabs,
            self,
            duration_ms=100,
        )

    def _on_comparison_subtab_changed(self, index: int) -> None:
        if self._tabs.tabText(index) == "Details":
            self._set_details_heat_enabled(False)

    def _build_header(self) -> QWidget:
        """Top header with comparison title and a concise scope summary."""
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
        return bar

    # ── Plot tab ──────────────────────────────────────────────────────────────

    def _build_plot_tab(self) -> QWidget:
        """Plot tab: canvas on left, plot-visibility sidebar on right."""
        page = QWidget()
        h = QHBoxLayout(page)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Main plot widget
        self._plot_widget = ComparisonPlotWidget()
        self._plot_widget.dataset_colors = DATASET_COLORS
        self._plot_widget.plot_updated.connect(self._sync_plot_visibility_panel)
        h.addWidget(self._plot_widget, 1)

        # Right sidebar: plot-only visibility and group reassignment controls.
        sidebar = QFrame()
        sidebar.setObjectName('plotVisibilitySidebar')
        sidebar.setFixedWidth(252)
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sidebar.setStyleSheet(
            'QFrame#plotVisibilitySidebar {'
            f'background: {C.BG_RAISED}; border-left: 1px solid {C.BORDER};'
            '}'
        )
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(0, 0, 0, 0)
        sb_lay.setSpacing(0)

        hdr = QLabel("PLOT VISIBILITY")
        hdr.setFixedHeight(30)
        hdr.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        hdr.setStyleSheet(
            f"padding-left: 10px; font-size: {F.SZ_XS}pt; font-weight: 700;"
            f"letter-spacing: 0.10em; color: {C.TEXT_MUTED};"
            f"background: {C.BG_LOW}; border: none;"
        )
        sb_lay.addWidget(hdr)

        self._plot_visibility_scope_label = QLabel("All selected datasets")
        self._plot_visibility_scope_label.setWordWrap(True)
        self._plot_visibility_scope_label.setToolTip(
            "Drag a sample row anywhere into another group area to reassign it. "
            "Drop it in Ungrouped to remove its group."
        )
        self._plot_visibility_scope_label.setFixedHeight(54)
        self._plot_visibility_scope_label.setStyleSheet(
            f"padding: 6px 10px; font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED};"
            f"background: {C.BG}; border: none;"
        )
        sb_lay.addWidget(self._plot_visibility_scope_label)

        actions = QWidget()
        actions.setStyleSheet(f"background: {C.BG}; border: none;")
        actions_lay = QHBoxLayout(actions)
        actions_lay.setContentsMargins(8, 6, 8, 6)
        actions_lay.setSpacing(6)

        # Scope & Groups lives in the always-visible main sidebar; this panel only needs
        # the plot-local "Show all" to restore hidden datasets.
        self._plot_show_all_btn = QPushButton("Show all")
        self._plot_show_all_btn.setToolTip("Show every dataset in the current plot scope")
        self._plot_show_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._plot_show_all_btn.clicked.connect(self._show_all_plot_datasets)
        self._plot_show_all_btn.setFixedHeight(24)
        self._plot_show_all_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.48); border: 1px solid {C.BORDER}; "
            f"border-radius: 4px; color: {C.TEXT_MID}; font-size: {F.SZ_XS}pt; padding: 2px 7px; }}"
            f"QPushButton:hover {{ background: rgba(107,142,35,0.08); color: {C.TEXT}; }}"
            f"QPushButton:disabled {{ color: {C.TEXT_MUTED}; background: transparent; }}"
        )
        try:
            self._plot_show_all_btn.setIcon(theme_icon("fa6s.eye", C.TEXT_MID, size=10))
            self._plot_show_all_btn.setIconSize(QSize(10, 10))
        except Exception:
            pass
        actions_lay.addWidget(self._plot_show_all_btn)
        actions_lay.addStretch(1)
        sb_lay.addWidget(actions)

        # Scrollable visibility list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._plot_visibility_list_widget = QWidget()
        self._plot_visibility_list_layout = QVBoxLayout(
            self._plot_visibility_list_widget
        )
        scrollbar_gutter = scroll.verticalScrollBar().sizeHint().width()
        self._plot_visibility_list_layout.setContentsMargins(
            8,
            4,
            8 + scrollbar_gutter + 4,
            0,
        )
        self._plot_visibility_list_layout.setSpacing(2)
        self._plot_visibility_list_layout.addStretch(1)
        scroll.setWidget(self._plot_visibility_list_widget)
        sb_lay.addWidget(scroll, 1)

        h.addWidget(sidebar)
        return page

    def _sync_plot_visibility_panel(self) -> None:
        """Refresh the plot visibility rail after plot-side presentation changes."""
        if not hasattr(self, "_plot_visibility_list_layout"):
            return
        self._refresh_plot_visibility_list()
        self._update_header_count()

    def _plot_widget_presentation(self) -> tuple[dict[str, str], dict[str, str]]:
        """Return live ``sample_name -> color/style`` maps from the plot widget."""
        colors: dict[str, str] = {}
        line_styles: dict[str, str] = {}
        plot_widget = getattr(self, "_plot_widget", None)
        if plot_widget is None:
            return colors, line_styles

        datasets = list(getattr(plot_widget, "datasets", []) or [])
        for index, dataset in enumerate(datasets):
            name = str(getattr(dataset, "sample_name", "") or "")
            if not name:
                continue
            effective_color = getattr(plot_widget, "_effective_color_for", None)
            if callable(effective_color):
                colors[name] = effective_color(name, index)
            line_styles[name] = getattr(plot_widget, "_dataset_linestyles", {}).get(
                name,
                "-",
            )
        return colors, line_styles

    def _refresh_plot_visibility_list(self) -> None:
        """Rebuild plot-only visibility controls from selected datasets."""
        while self._plot_visibility_list_layout.count() > 1:
            item = self._plot_visibility_list_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        plot_tabs = self._plot_dataset_tabs()
        plotted_names = {tab.get_dataset_name() for tab in plot_tabs}
        grouped_tabs = self._plot_grouped_selected_tabs()
        named_groups = [
            group for group, _tabs in grouped_tabs if group != UNGROUPED_LABEL
        ]
        group_colors = self._group_color_map(named_groups)
        live_colors, live_line_styles = self._plot_widget_presentation()

        if hasattr(self, "_plot_visibility_scope_label"):
            total = len(self.selected_datasets)
            visible = len(plot_tabs)
            group_text = f" | {len(named_groups)} groups" if named_groups else ""
            if self._plot_hidden:
                visibility_text = f"Visible: {visible} of {total} scoped{group_text}"
            else:
                visibility_text = f"All scoped datasets visible: {total}{group_text}"
            self._plot_visibility_scope_label.setText(visibility_text)

        if not self.selected_datasets:
            hint = QLabel("No datasets in comparison scope.")
            hint.setWordWrap(True)
            hint.setStyleSheet(
                f"padding: 12px 10px; color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt;"
                "background: transparent;"
            )
            self._plot_visibility_list_layout.insertWidget(
                self._plot_visibility_list_layout.count() - 1,
                hint,
            )
            return

        group_member_counts: dict[str, int] = {}
        for group_index, (group_name, tabs) in enumerate(grouped_tabs):
            group_area = _PlotGroupDropArea(
                group_name,
                self._plot_visibility_list_widget,
            )
            group_area.datasets_dropped.connect(self._move_plot_datasets_to_group)
            group_layout = QVBoxLayout(group_area)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(2)
            names = [tab.get_dataset_name() for tab in tabs]
            color = (
                live_colors.get(names[0], "")
                if group_name != UNGROUPED_LABEL and names
                else ""
            ) or group_colors.get(
                group_name, DATASET_COLORS[group_index % len(DATASET_COLORS)]
            )
            visible_count = sum(1 for name in names if name in plotted_names)
            hidden_all = bool(names) and all(
                name in self._plot_hidden for name in names
            )
            group_row = self._make_plot_group_row(
                group_name=group_name,
                color=color,
                dataset_count=len(tabs),
                visible_count=visible_count,
                hidden=hidden_all,
            )
            group_layout.addWidget(group_row)

            for tab in tabs:
                name = tab.get_dataset_name()
                hidden = name in self._plot_hidden
                plotted = name in plotted_names
                dataset_color = live_colors.get(name, color)
                line_style = live_line_styles.get(name, "-")
                if group_name != UNGROUPED_LABEL:
                    member_index = group_member_counts.get(group_name, 0)
                    group_member_counts[group_name] = member_index + 1
                    line_style = live_line_styles.get(
                        name,
                        dataset_line_style(
                            dataset_series_key(tab.get_dataset()),
                            default_line_style(member_index),
                        ),
                    )
                row = self._make_plot_dataset_row(
                    name=name,
                    group_name=group_name,
                    color=dataset_color,
                    line_style=line_style,
                    hidden=hidden,
                    plotted=plotted,
                )
                group_layout.addWidget(row)
            self._plot_visibility_list_layout.insertWidget(
                self._plot_visibility_list_layout.count() - 1,
                group_area,
            )

    def _move_plot_dataset_to_group(self, dataset_name: str, group_name: str) -> None:
        """Compatibility wrapper for moving one Plot Visibility dataset."""
        self._move_plot_datasets_to_group([dataset_name], group_name)

    def _move_plot_datasets_to_group(
        self,
        dataset_names: list[str],
        group_name: str,
    ) -> None:
        """Apply one multi-row drop to the shared dataset group assignments."""
        target_group = normalize_group_name(group_name)
        requested = set(dataset_names)
        changes = {}
        for tab in self.selected_datasets:
            if tab.get_dataset_name() not in requested:
                continue
            dataset = tab.get_dataset()
            if dataset_group_name(dataset) == target_group:
                continue
            dataset.group_name = target_group
            changes[tab] = target_group
        if not changes:
            return
        self._plot_group_selection.difference_update(requested)
        if self._plot_group_selection_anchor in requested:
            self._plot_group_selection_anchor = None
        self.group_assignments_changed.emit(changes)
        if hasattr(self._plot_widget, 'reset_presentation_state'):
            self._plot_widget.reset_presentation_state()
        self.update_comparison()

    def _on_plot_group_selection_requested(self, name: str, modifiers) -> None:
        """Mirror file-list selection semantics without toggling the visibility eye."""
        ordered_names = [tab.get_dataset_name() for tab in self.selected_datasets]
        if name not in ordered_names:
            return
        control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if shift and self._plot_group_selection_anchor in ordered_names:
            start = ordered_names.index(self._plot_group_selection_anchor)
            end = ordered_names.index(name)
            range_names = set(ordered_names[min(start, end):max(start, end) + 1])
            self._plot_group_selection = (
                self._plot_group_selection | range_names if control else range_names
            )
        elif control:
            if name in self._plot_group_selection:
                self._plot_group_selection.remove(name)
            else:
                self._plot_group_selection.add(name)
            self._plot_group_selection_anchor = name
        elif name not in self._plot_group_selection:
            self._plot_group_selection = {name}
            self._plot_group_selection_anchor = name
        elif not self._plot_group_selection_anchor:
            self._plot_group_selection_anchor = name
        self._sync_plot_group_selection_styles()

    def _sync_plot_group_selection_styles(self) -> None:
        if not hasattr(self, '_plot_visibility_list_widget'):
            return
        for row in self._plot_visibility_list_widget.findChildren(
            _PlotDatasetDragRow
        ):
            row.set_selection_style(row.dataset_name in self._plot_group_selection)

    def _start_plot_dataset_drag(self, row: _PlotDatasetDragRow) -> None:
        name = row.dataset_name
        if name not in self._plot_group_selection:
            self._plot_group_selection = {name}
            self._plot_group_selection_anchor = name
            self._sync_plot_group_selection_styles()
        names = [
            tab.get_dataset_name()
            for tab in self.selected_datasets
            if tab.get_dataset_name() in self._plot_group_selection
        ]
        if not names:
            return
        mime = QMimeData()
        mime.setData(_PLOT_DATASET_MIME, json.dumps(names).encode('utf-8'))
        drag = QDrag(row)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def _plot_grouped_selected_tabs(self) -> list[tuple[str, list]]:
        grouped: dict[str, list] = {}
        for tab in self.selected_datasets:
            group_name = dataset_group_name(tab.get_dataset())
            grouped.setdefault(group_name, []).append(tab)
        if UNGROUPED_LABEL not in grouped:
            grouped[UNGROUPED_LABEL] = []
        return list(grouped.items())

    def _make_plot_action_button(
        self,
        icon_name: str,
        tooltip: str,
        *,
        active: bool = False,
        color: str | None = None,
    ) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(24, 24)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tint = color or (C.OLIVE if active else C.TEXT_MUTED)
        btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 4px; padding: 0;"
            f"  background: {'rgba(107,142,35,0.15)' if active else 'transparent'}; }}"
            f"QPushButton:hover {{ background: rgba(107,142,35,0.10); }}"
        )
        try:
            btn.setIcon(theme_icon(icon_name, tint, size=10))
            btn.setIconSize(QSize(10, 10))
        except Exception:
            btn.setText("*" if active else "")
        return btn

    def _make_plot_group_row(
        self,
        *,
        group_name: str,
        color: str,
        dataset_count: int,
        visible_count: int,
        hidden: bool,
    ) -> QWidget:
        row = QWidget()
        row.setFixedHeight(40)
        row.setStyleSheet(f"background: {C.BG_LOW}; border: none; border-radius: 4px;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(7, 0, 6, 0)
        layout.setSpacing(6)

        swatch = QFrame()
        swatch.setFixedSize(8, 18)
        swatch.setStyleSheet(f"background: {color}; border-radius: 3px; border: none;")
        layout.addWidget(swatch, 0, Qt.AlignmentFlag.AlignVCenter)

        text_box = QWidget()
        text_lay = QVBoxLayout(text_box)
        text_lay.setContentsMargins(0, 2, 0, 2)
        text_lay.setSpacing(0)
        title = "Ungrouped" if group_name == UNGROUPED_LABEL else group_name
        title_lbl = QLabel(
            self._short_dataset_name(title, self._PLOT_VISIBILITY_NAME_WIDTH)
        )
        title_lbl.setToolTip(title)
        title_lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; font-weight: 700; color: {C.TEXT}; background: transparent;"
        )
        meta_lbl = QLabel(f"{visible_count}/{dataset_count} visible")
        meta_lbl.setStyleSheet(
            f"font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED}; background: transparent;"
        )
        text_lay.addWidget(title_lbl)
        text_lay.addWidget(meta_lbl)
        layout.addWidget(text_box, 1)

        visible_btn = self._make_plot_action_button(
            "fa6s.eye-slash" if hidden else "fa6s.eye",
            "Show group in plot" if hidden else "Hide group in plot",
            active=not hidden,
            color=color if not hidden else C.TEXT_MUTED,
        )
        visible_btn.clicked.connect(
            lambda _checked=False, g=group_name: self._toggle_group_visibility(g)
        )
        layout.addWidget(visible_btn)
        return row

    def _make_plot_dataset_row(
        self,
        *,
        name: str,
        group_name: str,
        color: str,
        line_style: str,
        hidden: bool,
        plotted: bool,
    ) -> QWidget:
        row = _PlotDatasetDragRow(name)
        row.setFixedHeight(38 if hidden else 34)
        row.set_selection_style(
            name in self._plot_group_selection,
            base_background='transparent',
        )
        row.selection_requested.connect(self._on_plot_group_selection_requested)
        row.drag_requested.connect(self._start_plot_dataset_drag)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 0, 6, 0)
        layout.setSpacing(6)

        plot_type = getattr(self._plot_widget, 'current_plot_type', 'distribution')
        if plot_type in {'distribution', 'combined'}:
            series_preview = LineStylePreview(
                color if not hidden else C.TEXT_MUTED,
                line_style,
                muted=hidden,
                width=28,
                height=14,
            )
            series_preview.setToolTip(
                f"Line style: {line_style_label(line_style)}"
            )
        else:
            # Non-curve plots still benefit from a stable group/dataset colour
            # cue, but dashed lines and markers would imply controls that the
            # active chart does not use.
            series_preview = QWidget()
            series_preview.setObjectName('plotVisibilityColorCue')
            series_preview.setFixedSize(28, 14)
            cue_layout = QHBoxLayout(series_preview)
            cue_layout.setContentsMargins(8, 2, 8, 2)
            cue_layout.setSpacing(0)
            cue = QFrame()
            cue.setFixedSize(10, 10)
            cue_color = color if not hidden else C.TEXT_MUTED
            cue.setStyleSheet(
                f'background: {cue_color}; border: none; border-radius: 3px;'
            )
            cue.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            cue_layout.addWidget(cue)
            series_preview.setToolTip('Dataset or group identity colour')
        series_preview.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        layout.addWidget(series_preview, 0, Qt.AlignmentFlag.AlignVCenter)

        text_box = QWidget()
        text_box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_lay = QVBoxLayout(text_box)
        text_lay.setContentsMargins(0, 2, 0, 2)
        text_lay.setSpacing(0)
        lbl = QLabel(
            self._short_dataset_name(name, self._PLOT_VISIBILITY_NAME_WIDTH)
        )
        lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; color: {C.TEXT if plotted else C.TEXT_MUTED};"
            "background: transparent; border: none;"
        )
        lbl.setToolTip(name)
        text_lay.addWidget(lbl)
        status_text = "Hidden" if hidden else ""
        if status_text:
            status_lbl = QLabel(status_text)
            status_lbl.setStyleSheet(
                f"font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED}; background: transparent; border: none;"
            )
            status_lbl.setToolTip(
                group_name if group_name != UNGROUPED_LABEL else "No group"
            )
            text_lay.addWidget(status_lbl)
        layout.addWidget(text_box, 1)

        visible_btn = self._make_plot_action_button(
            "fa6s.eye-slash" if hidden else "fa6s.eye",
            "Show dataset in plot" if hidden else "Hide dataset in plot",
            active=not hidden,
            color=color if not hidden else C.TEXT_MUTED,
        )
        visible_btn.clicked.connect(
            lambda _checked=False, n=name: self._toggle_plot_visibility(n)
        )
        layout.addWidget(visible_btn)
        return row

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

        view_frame, view_buttons = self._make_details_segmented_control(
            [
                (
                    "Individual",
                    "fa6s.table-columns",
                    True,
                    lambda: self._set_details_view_mode("individual"),
                ),
                (
                    "Aggregate",
                    "fa6s.chart-simple",
                    False,
                    lambda: self._set_details_view_mode("aggregate"),
                ),
            ]
        )
        self._details_view_individual_btn, self._details_view_aggregate_btn = (
            view_buttons
        )
        self._stabilize_segment_group(
            view_buttons, ["Individual", "Aggregate"], min_width=96
        )
        tb.addWidget(view_frame)

        mode_frame, mode_buttons = self._make_details_segmented_control(
            [
                (
                    "Grain",
                    "fa6s.wheat-awn",
                    True,
                    lambda: self._set_details_mode("grain"),
                ),
                ("K-values", "fa6s.water", False, lambda: self._set_details_mode("k")),
            ]
        )
        self._details_mode_frame = mode_frame
        self._details_mode_grain_btn, self._details_mode_k_btn = mode_buttons
        self._stabilize_segment_group(mode_buttons, ["Grain", "K-values"], min_width=88)
        tb.addWidget(mode_frame)

        preset_frame, preset_buttons = self._make_details_segmented_control(
            [
                (
                    "Summary",
                    "fa6s.circle-check",
                    True,
                    lambda: self._on_details_preset_clicked("core"),
                ),
                (
                    "All rows",
                    "fa6s.list",
                    False,
                    lambda: self._on_details_preset_clicked("all"),
                ),
                (
                    "Classification",
                    "fa6s.sliders",
                    False,
                    lambda: self._on_details_preset_clicked("context"),
                ),
            ]
        )
        (
            self._details_preset_core_btn,
            self._details_preset_all_btn,
            self._details_preset_context_btn,
        ) = preset_buttons
        self._stabilize_segment_group(
            preset_buttons,
            [
                "Summary",
                "All rows",
                "Classification",
                "All active",
                "Valid in all",
                "Choose",
                "Aggregate rows",
            ],
            min_width=116,
        )
        tb.addWidget(preset_frame)

        status_frame, status_buttons = self._make_details_segmented_control(
            [
                (
                    "OK only",
                    "fa6s.circle-check",
                    not self._stats_include_warnings,
                    lambda: self._set_details_warning_scope(False),
                ),
                (
                    "Warnings",
                    "fa6s.triangle-exclamation",
                    self._stats_include_warnings,
                    lambda: self._set_details_warning_scope(True),
                ),
            ]
        )
        self._details_status_ok_btn, self._details_status_warn_btn = status_buttons
        self._stabilize_segment_group(
            status_buttons, ["OK only", "Warnings"], min_width=90
        )
        tb.addWidget(status_frame)
        # Scope & Groups is reachable from the always-visible main sidebar, so the
        # Details bar no longer duplicates it here.
        tb.addStretch(1)

        self._details_unit_lbl = QLabel("Unit")
        self._details_unit_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f"color: {C.TEXT_MUTED}; background: transparent; border: none;"
        )
        tb.addWidget(self._details_unit_lbl)

        self._details_unit_combo = QComboBox()
        self._details_unit_combo.setToolTip(
            "Choose the display unit for K values in Details; calculations remain in m/s."
        )
        self._details_unit_combo.setObjectName("pw-style-sel")
        for unit, symbol in HydraulicConductivityConverter.get_all_units().items():
            self._details_unit_combo.addItem(symbol, unit)
        default_index = list(
            HydraulicConductivityConverter.get_all_units().keys()
        ).index(self._details_k_unit)
        self._details_unit_combo.setCurrentIndex(default_index)
        self._stabilize_unit_combo(self._details_unit_combo)
        self._details_unit_combo.currentIndexChanged.connect(
            self._on_details_unit_changed
        )
        tb.addWidget(self._details_unit_combo)

        heat_lbl = QLabel("Heat")
        heat_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f"color: {C.TEXT_MUTED}; background: transparent; border: none;"
        )
        tb.addWidget(heat_lbl)

        self._heat_btn = QPushButton("On" if self._heat_on else "Off")
        self._heat_btn.setCheckable(True)
        self._heat_btn.setChecked(self._heat_on)
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
        self._details_context.setMinimumWidth(0)
        self._details_context.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self._details_context.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            f"color: {C.TEXT_MUTED}; background: transparent; border: none;"
        )
        tb.addWidget(self._details_context)

        self._details_export_btn = QPushButton("Export Table…")
        self._details_export_btn.setProperty("pw-btn", True)
        self._details_export_btn.setFixedHeight(26)
        self._details_export_btn.setToolTip(
            "Export the currently visible Details rows and columns as CSV or Excel."
        )
        self._details_export_btn.clicked.connect(lambda: self._export_details())
        tb.addWidget(self._details_export_btn)
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

        self._aggregate_table = QTableWidget()
        self._style_details_table(self._aggregate_table)
        self._aggregate_table.horizontalHeader().setSectionsClickable(False)
        self._aggregate_table.horizontalHeader().setSortIndicatorShown(False)
        self._details_stack.addWidget(self._aggregate_table)

        bh.addWidget(self._details_stack, 1)
        bh.addWidget(self._build_details_rail())
        v.addWidget(body, 1)

        self._sync_details_mode_ui()
        return page

    def _make_details_segmented_control(
        self,
        specs: list[tuple[str, str, bool, object]],
    ) -> tuple[QFrame, list[QPushButton]]:
        frame = QFrame()
        frame.setObjectName("pw-seg")
        row = QHBoxLayout(frame)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        group = QButtonGroup(frame)
        group.setExclusive(True)
        buttons: list[QPushButton] = []
        for text, icon_name, active, callback in specs:
            btn = QPushButton(text)
            btn.setProperty("pw-seg", True)
            btn.setProperty("active", active)
            btn.setProperty("iconName", icon_name)
            btn.setCheckable(True)
            btn.setChecked(active)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tooltip = _SEGMENT_TOOLTIPS.get(text)
            if tooltip:
                btn.setToolTip(tooltip)
            btn.setIcon(
                theme_icon(icon_name, C.OLIVE if active else C.TEXT_MID, size=12)
            )
            btn.setIconSize(QSize(12, 12))
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.toggled.connect(lambda on, b=btn: _sync_segment_button(b, on))
            btn.clicked.connect(lambda _checked=False, cb=callback: cb())
            group.addButton(btn)
            row.addWidget(btn)
            buttons.append(btn)
        return frame, buttons

    def _stabilize_segment_group(
        self,
        buttons: list[QPushButton],
        labels: list[str] | None = None,
        *,
        min_width: int = 78,
    ) -> None:
        """Give segmented toolbar buttons stable widths across checked/text states."""
        if not buttons:
            return
        font = QFont(F.UI, F.SZ_SM, QFont.Weight.Bold)
        metrics = QFontMetrics(font)
        candidates = labels or [button.text() for button in buttons]
        width = max(
            min_width,
            max(metrics.horizontalAdvance(str(text)) for text in candidates) + 38,
        )
        for button in buttons:
            button.setFixedWidth(width)
        frame = buttons[0].parentWidget()
        if frame is not None:
            frame.setFixedWidth(width * len(buttons) + 2)
            frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _stabilize_unit_combo(self, combo: QComboBox, *, min_width: int = 74) -> None:
        metrics = QFontMetrics(combo.font())
        symbols = list(HydraulicConductivityConverter.UNIT_SYMBOLS.values())
        width = max(
            min_width, max(metrics.horizontalAdvance(symbol) for symbol in symbols) + 34
        )
        combo.setFixedWidth(width)
        combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _set_segment_checked(self, btn: QPushButton, checked: bool) -> None:
        btn.setChecked(checked)
        _sync_segment_button(btn, checked)

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
        wrap.setStyleSheet(
            f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER};"
        )
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
        rail.setFixedWidth(360)
        rail.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        rail.setStyleSheet(
            f"background: {C.BG_RAISED}; border-left: 1px solid {C.BORDER};"
        )
        v = QVBoxLayout(rail)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        (
            header,
            self._details_rail_title,
            self._details_rail_subtitle,
            self._details_rail_badge,
        ) = self._build_compact_rail_header(
            "Details Summary", "No datasets selected", "0 / 0"
        )
        v.addWidget(header)

        rail_scroll = QScrollArea()
        rail_scroll.setWidgetResizable(True)
        rail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        rail_scroll.setStyleSheet("background: transparent; border: none;")
        rail_content = QWidget()
        rail_content.setStyleSheet("background: transparent;")
        rail_content_layout = QVBoxLayout(rail_content)
        rail_content_layout.setContentsMargins(12, 10, 12, 12)
        rail_content_layout.setSpacing(12)

        self._details_focus_section, self._details_focus_layout = (
            self._build_compact_rail_section("Scope")
        )
        rail_content_layout.addWidget(self._details_focus_section)

        self._details_insight_section, self._details_insights_layout = (
            self._build_compact_rail_section("Filters")
        )
        rail_content_layout.addWidget(self._details_insight_section)

        self._details_status_section, self._details_status_layout = (
            self._build_compact_rail_section("K Summary")
        )
        rail_content_layout.addWidget(self._details_status_section)

        self._details_grain_summary_section, self._details_grain_summary_layout = (
            self._build_compact_rail_section("Grain Summary")
        )
        rail_content_layout.addWidget(self._details_grain_summary_section)

        self._details_groups_section, self._details_groups_layout = (
            self._build_compact_rail_section("Groups")
        )
        rail_content_layout.addWidget(self._details_groups_section)

        self._details_legend_section, legend_layout = self._build_compact_rail_section(
            "Heat Legend"
        )
        legend_layout.addWidget(
            self._make_rail_legend_row(
                [
                    ("low", _heat_color(0.0).name()),
                    ("mid", _heat_color(0.5).name()),
                    ("high", _heat_color(1.0).name()),
                ]
            )
        )
        rail_content_layout.addWidget(self._details_legend_section)
        rail_content_layout.addStretch(1)
        rail_scroll.setWidget(rail_content)
        v.addWidget(rail_scroll, 1)
        return rail

    def _sync_details_mode_ui(self) -> None:
        grain_mode = self._details_mode == "grain"
        aggregate_mode = self._details_view_mode == "aggregate"
        active_preset = (
            self._details_grain_preset if grain_mode else self._details_k_preset
        )
        active_toolbar_preset = (
            "all"
            if (
                aggregate_mode
                and (
                    self._stats_common_methods_only
                    or self._stats_method_scope == "valid_all"
                )
            )
            else ("core" if aggregate_mode else active_preset)
        )
        self._details_preset = active_preset
        self._set_segment_checked(self._details_view_individual_btn, not aggregate_mode)
        self._set_segment_checked(self._details_view_aggregate_btn, aggregate_mode)
        self._set_segment_checked(self._details_mode_grain_btn, grain_mode)
        self._set_segment_checked(self._details_mode_k_btn, not grain_mode)
        self._set_segment_checked(
            self._details_preset_core_btn, active_toolbar_preset == "core"
        )
        self._set_segment_checked(
            self._details_preset_all_btn, active_toolbar_preset == "all"
        )
        self._set_segment_checked(
            self._details_preset_context_btn, active_toolbar_preset == "context"
        )
        self._set_segment_checked(
            self._details_status_ok_btn, not self._stats_include_warnings
        )
        self._set_segment_checked(
            self._details_status_warn_btn, self._stats_include_warnings
        )
        self._details_mode_frame.setVisible(not aggregate_mode)
        for btn in (self._details_mode_grain_btn, self._details_mode_k_btn):
            btn.setEnabled(not aggregate_mode)
            btn.setToolTip(
                "Aggregate view combines grain and K summaries in one table."
                if aggregate_mode
                else ""
            )
        self._details_preset_context_btn.setEnabled(True)
        if aggregate_mode:
            self._details_preset_core_btn.setText("All active")
            self._details_preset_all_btn.setText("Valid in all")
            self._details_preset_context_btn.setText("Choose")
            self._details_preset_context_btn.setToolTip(
                "Choose the workspace K methods used across the program"
            )
        elif not grain_mode:
            self._details_preset_core_btn.setText("All active")
            self._details_preset_all_btn.setText("Valid in all")
            self._details_preset_context_btn.setText("Aggregate rows")
            self._details_preset_context_btn.setToolTip("")
        else:
            self._details_preset_core_btn.setText("Summary")
            self._details_preset_all_btn.setText("All rows")
            self._details_preset_context_btn.setText("Classification")
            self._details_preset_context_btn.setToolTip("")
        for button in (
            self._details_preset_core_btn,
            self._details_preset_all_btn,
            self._details_preset_context_btn,
        ):
            button.setToolTip(_SEGMENT_TOOLTIPS.get(button.text(), ""))
        if aggregate_mode:
            self._details_stack.setCurrentWidget(self._aggregate_table)
        else:
            self._details_stack.setCurrentWidget(
                self._grain_table if grain_mode else self._k_table
            )
        self._details_unit_lbl.setVisible(aggregate_mode or not grain_mode)
        self._details_unit_combo.setVisible(aggregate_mode or not grain_mode)
        if aggregate_mode:
            context_suffix = f"Aggregate - {HydraulicConductivityConverter.UNIT_SYMBOLS[self._details_k_unit]}"
        else:
            context_suffix = (
                "Grain"
                if grain_mode
                else f"K-Values - {HydraulicConductivityConverter.UNIT_SYMBOLS[self._details_k_unit]}"
            )
        self._details_context.setText(f"{self._scheme_label()} · {context_suffix}")
        self._details_status_section.setVisible(True)

    def _set_details_view_mode(self, mode: str) -> None:
        if mode == self._details_view_mode:
            return
        self._details_view_mode = mode
        self._sync_details_mode_ui()
        self._refresh_details_views()

    def _set_details_warning_scope(self, include_warnings: bool) -> None:
        if self._stats_include_warnings == include_warnings:
            return
        self._stats_include_warnings = include_warnings
        self._sync_details_mode_ui()
        if self.selected_datasets:
            self._refresh_comparison_surfaces(include_plot=False)

    def _on_details_preset_clicked(self, preset: str) -> None:
        if self._details_view_mode == "aggregate":
            if preset == "core":
                self._set_details_method_scope(valid_in_all=False)
            elif preset == "all":
                self._set_details_method_scope(valid_in_all=True)
            else:
                self.method_selection_requested.emit()
            return
        self._set_details_preset(preset)

    def _set_details_method_scope(self, *, valid_in_all: bool) -> None:
        target_scope = "valid_all" if valid_in_all else "all"
        if (
            self._stats_method_scope == target_scope
            and self._stats_common_methods_only == valid_in_all
        ):
            return
        self._stats_method_scope = target_scope
        self._stats_common_methods_only = valid_in_all
        self._sync_details_mode_ui()
        if self.selected_datasets:
            self._refresh_comparison_surfaces(include_plot=False)

    def _set_details_mode(self, mode: str) -> None:
        if mode == self._details_mode:
            return
        self._details_mode = mode
        self._sync_details_mode_ui()
        self._refresh_details_views()

    def _set_details_preset(self, preset: str) -> None:
        active_preset = (
            self._details_grain_preset
            if self._details_mode == "grain"
            else self._details_k_preset
        )
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

    def _selected_names_for_group(self, group_name: str) -> list[str]:
        """Return selected dataset names for a comparison group."""
        names: list[str] = []
        for tab in self.selected_datasets:
            if dataset_group_name(tab.get_dataset()) == group_name:
                names.append(tab.get_dataset_name())
        return names

    def _toggle_plot_visibility(self, name: str) -> None:
        """Hide/show one selected dataset in the plot without changing scope."""
        if name in self._plot_hidden:
            self._plot_hidden.discard(name)
        else:
            self._plot_hidden.add(name)
        self._refresh_plot_visibility_list()
        self._update_plot()
        self._update_header_count()

    def _toggle_group_visibility(self, group_name: str) -> None:
        """Hide/show a whole selected group in the plot without changing scope."""
        names = self._selected_names_for_group(group_name)
        if not names:
            return
        if all(name in self._plot_hidden for name in names):
            self._plot_hidden.difference_update(names)
        else:
            self._plot_hidden.update(names)
        self._refresh_plot_visibility_list()
        self._update_plot()
        self._update_header_count()

    def _show_all_plot_datasets(self) -> None:
        """Restore all scoped datasets to the plot."""
        if not self._plot_hidden:
            return
        self._plot_hidden.clear()
        self._refresh_plot_visibility_list()
        self._update_plot()
        self._update_header_count()

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
        t.setViewportMargins(0, 0, 0, 8)
        t.horizontalHeader().setSectionsClickable(True)
        t.horizontalHeader().setSortIndicatorShown(True)
        t.horizontalHeader().setMinimumSectionSize(72)
        t.verticalHeader().setDefaultSectionSize(_DETAILS_ROW_HEIGHT)
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
            QScrollBar:horizontal {{
                height: 8px; background: transparent;
            }}
            QScrollBar::handle:horizontal {{
                background: {C.BORDER}; border-radius: 3px; min-width: 18px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
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

        self._heat_btn = QPushButton("On" if self._heat_on else "Off")
        self._heat_btn.setCheckable(True)
        self._heat_btn.setChecked(self._heat_on)
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
        self._set_details_heat_enabled(checked)

    def _set_details_heat_enabled(self, checked: bool) -> None:
        """Set Details heat coloring without relying on toggle signal side effects."""
        checked = bool(checked)
        if self._heat_on == checked:
            button = getattr(self, "_heat_btn", None)
            if button is not None:
                button.setText("On" if checked else "Off")
            return

        self._heat_on = checked
        button = getattr(self, "_heat_btn", None)
        if button is not None:
            was_blocked = button.blockSignals(True)
            button.setChecked(checked)
            button.setText("On" if checked else "Off")
            button.blockSignals(was_blocked)
        if hasattr(self, "_grain_table"):
            self._refresh_details_views()

    def _scheme_label(self) -> str:
        return getattr(
            self._active_scheme, "name", None
        ) or self._active_scheme.__class__.__name__.replace("_", " ")

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

    def _make_dataset_chip(
        self, name: str, color: str, group_name: str | None = None
    ) -> QWidget:
        chip = QWidget()
        group_name = group_name or "Ungrouped"
        chip.setToolTip(f"{name}\nGroup: {group_name}")
        h = QHBoxLayout(chip)
        h.setContentsMargins(2, 0, 8, 0)
        h.setSpacing(6)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {color}; background: transparent; font-size: {F.SZ_SM + 1}pt; font-weight: 700;"
        )
        label = name if group_name == "Ungrouped" else f"{name} ({group_name})"
        name_lbl = QLabel(self._short_dataset_name(label))
        name_lbl.setStyleSheet(
            f"color: {C.TEXT_MID}; background: transparent; font-size: {F.SZ_SM}pt; font-weight: 600;"
        )
        h.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(name_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        return chip

    def _make_group_chip(
        self, group_name: str, color: str, dataset_count: int, members: list[str]
    ) -> QWidget:
        chip = QWidget()
        member_preview = "\n".join(members[:8])
        if len(members) > 8:
            member_preview += f"\n+ {len(members) - 8} more"
        chip.setToolTip(
            f"{group_name}\n{dataset_count} datasets\n{member_preview}".strip()
        )
        h = QHBoxLayout(chip)
        h.setContentsMargins(2, 0, 8, 0)
        h.setSpacing(6)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {color}; background: transparent; border: none; font-size: {F.SZ_SM + 1}pt; font-weight: 700;"
        )
        name_lbl = QLabel(
            self._short_dataset_name(f"{group_name} ({dataset_count})", max_width=145)
        )
        name_lbl.setStyleSheet(
            f"color: {C.TEXT_MID}; background: transparent; border: none; font-size: {F.SZ_SM}pt; font-weight: 700;"
        )
        h.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(name_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        return chip

    def _make_overall_scope_chip(self, dataset_count: int) -> QWidget:
        chip = QWidget()
        chip.setToolTip(f"Overall\n{dataset_count} selected datasets")
        h = QHBoxLayout(chip)
        h.setContentsMargins(2, 0, 8, 0)
        h.setSpacing(6)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {C.EARTH}; background: transparent; border: none; font-size: {F.SZ_SM + 1}pt; font-weight: 700;"
        )
        name_lbl = QLabel(f"Overall ({dataset_count})")
        name_lbl.setStyleSheet(
            f"color: {C.EARTH}; background: transparent; border: none; font-size: {F.SZ_SM}pt; font-weight: 700;"
        )
        h.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(name_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        return chip

    def _short_dataset_name(self, name: str, max_width: int = 118) -> str:
        metrics = QFontMetrics(QFont(F.UI, F.SZ_SM))
        return metrics.elidedText(name, Qt.TextElideMode.ElideRight, max_width)

    def _group_color_map(self, group_names: list[str]) -> dict[str, str]:
        return group_color_map(group_names, palette=DATASET_COLORS)

    def _dataset_colors_for_tabs(self, tabs: list) -> list[str]:
        group_names = [
            dataset_group_name(tab.get_dataset())
            for tab in tabs
        ]
        colors_by_group = self._group_color_map(group_names)
        colors: list[str] = []
        for index, tab in enumerate(tabs):
            group_name = dataset_group_name(tab.get_dataset())
            if group_name != UNGROUPED_LABEL:
                colors.append(
                    colors_by_group.get(
                        group_name,
                        DATASET_COLORS[index % len(DATASET_COLORS)],
                    )
                )
            else:
                colors.append(DATASET_COLORS[index % len(DATASET_COLORS)])
        return colors

    def _stats_uses_group_scope(self) -> bool:
        return any(
            dataset_group_name(tab.get_dataset()) != UNGROUPED_LABEL
            for tab in self.selected_datasets
        )

    def _stats_group_members(self) -> dict[str, list[str]]:
        members: dict[str, list[str]] = {}
        for tab in self.selected_datasets:
            group_name = dataset_group_name(tab.get_dataset())
            members.setdefault(group_name, []).append(tab.get_dataset_name())
        return members

    def _refresh_details_dataset_strip(self) -> None:
        layout = self._details_dataset_chips_layout
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if self._details_view_mode == "aggregate" and self.selected_datasets:
            self._details_dataset_strip.setVisible(True)
            snapshot = self._build_comparison_snapshot()
            groups = list(snapshot.k.group_names)
            group_colors = self._group_color_map(groups)
            members_by_group: dict[str, list[str]] = {group: [] for group in groups}
            for tab in self.selected_datasets:
                group_name = dataset_group_name(tab.get_dataset())
                members_by_group.setdefault(group_name, []).append(
                    tab.get_dataset_name()
                )
            for group_name in groups:
                members = members_by_group.get(group_name, [])
                chip = self._make_group_chip(
                    group_name,
                    group_colors.get(group_name, C.TEXT_MID),
                    len(members),
                    members,
                )
                layout.insertWidget(layout.count() - 1, chip)
            return

        self._details_dataset_strip.setVisible(False)

    def _refresh_details_views(self) -> None:
        self._sync_details_mode_ui()
        if self.selected_datasets:
            self._refresh_grain_table()
            self._refresh_k_table()
            self._refresh_aggregate_table()
        self._refresh_details_dataset_strip()
        self._refresh_details_rail()

    def _refresh_details_rail(self) -> None:
        self._reset_layout(self._details_focus_layout)
        self._reset_layout(self._details_insights_layout)
        self._reset_layout(self._details_status_layout)
        if hasattr(self, "_details_grain_summary_layout"):
            self._reset_layout(self._details_grain_summary_layout)
        if hasattr(self, "_details_groups_layout"):
            self._reset_layout(self._details_groups_layout)

        snapshot = self._build_comparison_snapshot() if self.selected_datasets else None
        aggregation = snapshot.k if snapshot is not None else None
        grain = snapshot.grain if snapshot is not None else None

        if aggregation is None or grain is None:
            self._set_compact_rail_header(
                self._details_rail_title,
                self._details_rail_subtitle,
                self._details_rail_badge,
                title="Details Summary",
                subtitle="No datasets selected",
                badge="0 / 0",
            )
            self._details_focus_layout.addWidget(
                self._make_rail_status_line(
                    "Select datasets to populate details.", tone="warn"
                )
            )
            self._details_status_section.setVisible(False)
            self._details_grain_summary_section.setVisible(False)
            self._details_groups_section.setVisible(False)
            self._details_focus_strip.setText("")
            self._details_legend_section.setVisible(self._heat_on)
            return

        preset_label = {
            ("grain", "core"): "Summary rows",
            ("grain", "all"): "All grain rows",
            ("grain", "context"): "Classification rows",
            ("k", "core"): "All active K methods",
            ("k", "all"): "Methods valid in all datasets",
            ("k", "context"): "Aggregate K rows",
        }[(self._details_mode, self._details_preset)]
        dataset_count = len(self.selected_datasets)
        group_count = len(aggregation.group_names) if aggregation is not None else 0
        method_count = len(aggregation.method_names) if aggregation is not None else 0
        included = aggregation.overall.included_count if aggregation is not None else 0
        total = aggregation.overall.total_cells if aggregation is not None else 0
        warnings = aggregation.overall.warning_count if aggregation is not None else 0
        warnings_excluded = warnings if not self._stats_include_warnings else 0

        self._set_compact_rail_header(
            self._details_rail_title,
            self._details_rail_subtitle,
            self._details_rail_badge,
            title="Aggregate Summary"
            if self._details_view_mode == "aggregate"
            else "Details Summary",
            subtitle=f"{dataset_count} datasets - {group_count} groups - {'OK + warnings' if self._stats_include_warnings else 'OK only'}",
            badge=f"{included} / {total}" if total else "0 / 0",
        )

        self._details_focus_layout.addWidget(
            self._make_rail_chip_group(
                [
                    (f"{dataset_count} datasets", "neutral"),
                    (f"{group_count} groups", "neutral"),
                    (f"{method_count} methods", "neutral"),
                    (f"{included} / {total} K cells", "ok" if included else "warn"),
                    (
                        f"{warnings_excluded} warnings excluded",
                        "warn" if warnings_excluded else "neutral",
                    ),
                ]
            )
        )

        status_text = "OK + warnings" if self._stats_include_warnings else "OK only"
        method_text = (
            "Valid in all"
            if self._stats_method_scope == "valid_all"
            or self._stats_common_methods_only
            else "All active"
        )
        unit_text = (
            f"{self._details_unit_symbol()} + mm/%"
            if self._details_view_mode == "aggregate"
            else (self._details_unit_symbol() if self._details_mode == "k" else "mm/%")
        )
        self._details_insights_layout.addWidget(
            self._make_rail_chip_group(
                [
                    (
                        "Aggregate"
                        if self._details_view_mode == "aggregate"
                        else ("Grain" if self._details_mode == "grain" else "K-values"),
                        "ok",
                    ),
                    (preset_label, "neutral"),
                    (method_text, "neutral"),
                    (status_text, "ok" if not self._stats_include_warnings else "warn"),
                    (unit_text, "neutral"),
                ]
            )
        )

        if aggregation is not None:
            k_stats = aggregation.overall
            k_range = "-"
            if k_stats.min_m_s is not None and k_stats.max_m_s is not None:
                k_range = f"{self._format_k_value(k_stats.min_m_s)} - {self._format_k_value(k_stats.max_m_s)}"
            geo_text = (
                self._format_k_value(k_stats.geometric_mean_m_s)
                if k_stats.geometric_mean_m_s is not None
                else "-"
            )
            perm_class = (
                _perm_class(k_stats.geometric_mean_m_s)
                if k_stats.geometric_mean_m_s is not None
                else "-"
            )
            self._details_status_layout.addWidget(
                self._make_rail_headline(
                    "Geometric mean", "primary aggregate K", geo_text
                )
            )
            self._add_rail_metric_grid(
                self._details_status_layout,
                [
                    (
                        "Arithmetic",
                        self._format_k_value(k_stats.arithmetic_mean_m_s)
                        if k_stats.arithmetic_mean_m_s is not None
                        else "-",
                    ),
                    (
                        "Median",
                        self._format_k_value(k_stats.median_m_s)
                        if k_stats.median_m_s is not None
                        else "-",
                    ),
                    ("Range", k_range),
                    (
                        "Class",
                        perm_class.split(" (", 1)[0] if perm_class != "-" else "-",
                    ),
                ],
            )
            self._details_status_layout.addWidget(
                self._make_rail_status_line(
                    perm_class
                    if perm_class != "-"
                    else "No included K values for this scope.",
                    tone="ok" if geo_text != "-" else "warn",
                )
            )

        if grain is not None and hasattr(self, "_details_grain_summary_layout"):
            g_stats = grain.overall
            metrics = g_stats.metrics
            d50_metric = metrics.get("D50")
            d50_text = self._format_grain_summary_value(
                d50_metric.median if d50_metric is not None else None,
                " mm",
            )
            self._details_grain_summary_layout.addWidget(
                self._make_rail_headline(
                    "D50 median", "across included datasets", d50_text
                )
            )
            self._add_rail_metric_grid(
                self._details_grain_summary_layout,
                [
                    (
                        "Mean grain size",
                        self._grain_metric_text(g_stats, "Dmean", " mm"),
                    ),
                    ("Cu median", self._grain_metric_text(g_stats, "Cu")),
                    ("Fines median", self._grain_metric_text(g_stats, "Fines%", "%")),
                    ("Dominant class", g_stats.dominant_class),
                ],
            )

        show_group_breakdown = len(aggregation.group_names) > 1 or any(
            group != UNGROUPED_LABEL for group in aggregation.group_names
        )
        self._details_groups_section.setVisible(show_group_breakdown)
        if (
            show_group_breakdown
            and aggregation is not None
            and grain is not None
            and hasattr(self, "_details_groups_layout")
        ):
            group_colors = self._group_color_map(list(aggregation.group_names))
            for group_name in aggregation.group_names:
                k_group = aggregation.by_group.get(group_name)
                g_group = grain.by_group.get(group_name)
                k_text = "-"
                if k_group is not None and k_group.geometric_mean_m_s is not None:
                    k_text = self._format_k_value(k_group.geometric_mean_m_s)
                d50_text = "-"
                ds_count = 0
                if g_group is not None:
                    ds_count = g_group.dataset_count
                    d50_metric = g_group.metrics.get("D50")
                    if d50_metric is not None and d50_metric.median is not None:
                        d50_text = f"D50 {d50_metric.median:.3g} mm"
                included_text = "0 / 0"
                if k_group is not None:
                    included_text = f"{k_group.included_count} / {k_group.total_cells}"
                self._details_groups_layout.addWidget(
                    self._make_rail_group_row(
                        group_name,
                        f"{ds_count} datasets - {included_text} K cells",
                        f"K {k_text}\n{d50_text}",
                        group_colors.get(group_name, C.TEXT_MID),
                    )
                )

        self._details_status_section.setVisible(True)
        self._details_grain_summary_section.setVisible(True)

        focus_bits = [
            f"{len(self.selected_datasets)} datasets",
            self._scheme_label(),
            "heat on" if self._heat_on else "heat off",
        ]
        if self._details_mode == "k" or self._details_view_mode == "aggregate":
            focus_bits.insert(2, self._details_unit_symbol())
        self._details_focus_strip.setText("  -  ".join(focus_bits))
        self._details_legend_section.setVisible(self._heat_on)

    @staticmethod
    def _format_grain_summary_value(value: Optional[float], suffix: str = "") -> str:
        if value is None:
            return "-"
        if suffix == "%":
            return f"{value:.1f}%"
        if suffix.strip() == "mm":
            return f"{value:.3g} mm"
        return f"{value:.3g}{suffix}"

    def _build_detail_insights(self) -> list[tuple[str, str]]:
        tabs = self.selected_datasets
        if not tabs:
            return [
                (
                    "No comparison data",
                    "Load at least two datasets to populate details.",
                )
            ]

        if self._details_mode == "grain":
            tracked = ["D50", "Cu", "Fines%"]
            insights = []
            spreads = []
            for label in tracked:
                values = [
                    self._get_grain_value(tab.get_dataset(), label) for tab in tabs
                ]
                valid = [value for value in values if value is not None]
                if len(valid) >= 2:
                    spreads.append(
                        (max(valid) - min(valid), label, min(valid), max(valid))
                    )
            if spreads:
                spreads.sort(reverse=True)
                _, label, low, high = spreads[0]
                insights.append(
                    (
                        f"Largest {label} spread",
                        f"{low:.4g} to {high:.4g} across the selected set.",
                    )
                )
            insights.append(
                (
                    "Classification context",
                    f"Labels follow the active scheme: {self._scheme_label()}.",
                )
            )
            return insights[:3]

        valid_per_dataset = []
        for tab in tabs:
            vals = [
                r.k_value
                for r in tab.get_results()
                if r.k_value is not None and r.k_value > 0
            ]
            if vals:
                valid_per_dataset.append(
                    (tab.get_dataset_name(), float(np.exp(np.mean(np.log(vals)))))
                )
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
                counts.setdefault(result.method_name, {"ok": 0, "warn": 0, "na": 0})[
                    state
                ] += 1

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

        view_frame, view_buttons = self._make_details_segmented_control(
            [
                (
                    "K spread",
                    "fa6s.chart-column",
                    True,
                    lambda: self._set_stats_view_mode("spread"),
                ),
                (
                    "Coverage",
                    "fa6s.border-all",
                    False,
                    lambda: self._set_stats_view_mode("coverage"),
                ),
            ]
        )
        self._stats_view_spread_btn, self._stats_view_coverage_btn = view_buttons
        self._stabilize_segment_group(
            view_buttons, ["K spread", "Coverage"], min_width=94
        )
        tb.addWidget(view_frame, 0)

        metric_frame, metric_buttons = self._make_details_segmented_control(
            [
                (
                    "Geo. mean",
                    "fa6s.chart-line",
                    self._stats_metric == "geometric",
                    lambda: self._on_stats_metric_changed("geometric"),
                ),
                (
                    "Arith. mean",
                    "fa6s.calculator",
                    self._stats_metric == "arithmetic",
                    lambda: self._on_stats_metric_changed("arithmetic"),
                ),
                (
                    "Median",
                    "fa6s.align-center",
                    self._stats_metric == "median",
                    lambda: self._on_stats_metric_changed("median"),
                ),
            ]
        )
        (
            self._stats_metric_geo_btn,
            self._stats_metric_arith_btn,
            self._stats_metric_med_btn,
        ) = metric_buttons
        self._stabilize_segment_group(
            metric_buttons,
            ["Geo. mean", "Arith. mean", "Median"],
            min_width=100,
        )
        tb.addWidget(metric_frame, 0)

        unit_lbl = QLabel("Unit")
        unit_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED};"
        )
        tb.addWidget(unit_lbl, 0)

        self._stats_unit_combo = QComboBox()
        self._stats_unit_combo.setToolTip(
            "Choose the display unit for Statistics; calculations and filtering are unchanged."
        )
        self._stats_unit_combo.setObjectName("pw-style-sel")
        for unit, symbol in HydraulicConductivityConverter.get_all_units().items():
            self._stats_unit_combo.addItem(symbol, unit)
        default_index = self._stats_unit_combo.findData(self._stats_k_unit)
        if default_index >= 0:
            self._stats_unit_combo.setCurrentIndex(default_index)
        self._stabilize_unit_combo(self._stats_unit_combo)
        self._stats_unit_combo.currentIndexChanged.connect(self._on_stats_unit_changed)
        tb.addWidget(self._stats_unit_combo, 0)

        method_frame, method_buttons = self._make_details_segmented_control(
            [
                (
                    "All active",
                    "fa6s.table-list",
                    True,
                    lambda: self._set_stats_method_scope(valid_in_all=False),
                ),
                (
                    "Valid in all",
                    "fa6s.circle-check",
                    False,
                    lambda: self._set_stats_method_scope(valid_in_all=True),
                ),
                ("Choose", "fa6s.sliders", False, self.method_selection_requested.emit),
            ]
        )
        (
            self._stats_methods_all_btn,
            self._stats_methods_valid_all_btn,
            self._stats_methods_choose_btn,
        ) = method_buttons
        self._stabilize_segment_group(
            method_buttons,
            ["All active", "Valid in all", "Choose"],
            min_width=112,
        )
        self._stats_methods_valid_all_btn.setToolTip(
            _SEGMENT_TOOLTIPS["Valid in all"]
        )
        self._stats_methods_choose_btn.setEnabled(True)
        self._stats_methods_choose_btn.setToolTip(_SEGMENT_TOOLTIPS["Choose"])
        tb.addWidget(method_frame, 0)

        status_frame, status_buttons = self._make_details_segmented_control(
            [
                (
                    "OK only",
                    "fa6s.circle-check",
                    not self._stats_include_warnings,
                    lambda: self._set_stats_warning_scope(False),
                ),
                (
                    "Warnings",
                    "fa6s.triangle-exclamation",
                    self._stats_include_warnings,
                    lambda: self._set_stats_warning_scope(True),
                ),
            ]
        )
        self._stats_ok_only_btn, self._stats_warnings_btn = status_buttons
        self._stabilize_segment_group(
            status_buttons, ["OK only", "Warnings"], min_width=90
        )
        tb.addWidget(status_frame, 0)
        # Scope & Groups is reachable from the always-visible main sidebar (no per-subtab
        # duplicate here).

        self._stats_context = QLabel("")
        self._stats_context.setMinimumWidth(0)
        self._stats_context.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self._stats_context.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED}; background: transparent;"
        )
        tb.addStretch(1)
        tb.addWidget(self._stats_context, 0)

        self._stats_export_btn = QPushButton("Export Table…")
        self._stats_export_btn.setProperty("pw-btn", True)
        self._stats_export_btn.setFixedHeight(26)
        self._stats_export_btn.setToolTip(
            "Export the currently visible Statistics rows and columns as CSV or Excel."
        )
        self._stats_export_btn.clicked.connect(lambda: self._export_statistics())
        tb.addWidget(self._stats_export_btn)
        root.addWidget(toolbar)

        root.addWidget(self._build_stats_dataset_strip())

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        bh = QHBoxLayout(body)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(0)

        main = QWidget()
        main.setMinimumWidth(0)
        main.setStyleSheet(f"background: {C.BG}; border: none;")
        mv = QVBoxLayout(main)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(0)

        fc = C.BG
        self._box_fig = Figure(figsize=(8, 5), facecolor=fc, tight_layout=True)
        self._box_canvas = FigureCanvas(self._box_fig)
        self._box_canvas.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
        )
        self._box_canvas.setMinimumSize(0, 0)
        self._heat_fig = Figure(figsize=(8, 5), facecolor=fc, tight_layout=True)
        self._heat_canvas = FigureCanvas(self._heat_fig)
        self._heat_canvas.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
        )
        self._heat_canvas.setMinimumSize(0, 0)

        self._stats_stack = QStackedWidget()
        self._stats_stack.setMinimumSize(0, 0)
        self._stats_scope_table = QTableWidget()
        self._style_stats_table(self._stats_scope_table)
        self._stats_method_table = QTableWidget()
        self._style_stats_table(self._stats_method_table)
        self._stats_spread_panel = self._build_stats_panel(
            "K-value spread across selected datasets",
            self._box_canvas,
            meta_attr="_stats_dist_meta",
            table=self._stats_scope_table,
            table_title="Scope statistics",
        )
        self._stats_coverage_panel = self._build_stats_panel(
            "Method agreement and applicability",
            self._heat_canvas,
            meta_attr="_stats_agreement_meta",
            table=self._stats_method_table,
            table_title="Method statistics",
        )
        self._stats_stack.addWidget(self._stats_spread_panel)
        self._stats_stack.addWidget(self._stats_coverage_panel)
        mv.addWidget(self._stats_stack, 1)

        rail = QFrame()
        rail.setFixedWidth(360)
        rail.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        rail.setStyleSheet(
            f"background: {C.BG_RAISED}; border-left: 1px solid {C.BORDER};"
        )
        rv = QVBoxLayout(rail)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        (
            header,
            self._stats_rail_title,
            self._stats_rail_subtitle,
            self._stats_rail_badge,
        ) = self._build_compact_rail_header(
            "Statistics Summary", "No datasets selected", "0 / 0"
        )
        rv.addWidget(header)

        rail_scroll = QScrollArea()
        rail_scroll.setWidgetResizable(True)
        rail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        rail_scroll.setStyleSheet("background: transparent; border: none;")
        rail_content = QWidget()
        rail_content.setStyleSheet("background: transparent;")
        rail_content.setMinimumWidth(0)
        rail_content_layout = QVBoxLayout(rail_content)
        rail_content_layout.setContentsMargins(12, 10, 12, 12)
        rail_content_layout.setSpacing(12)

        self._stats_scope_section, self._stats_scope_layout = (
            self._build_compact_rail_section("Scope")
        )
        rail_content_layout.addWidget(self._stats_scope_section)
        self._stats_filter_section, self._stats_filter_layout = (
            self._build_compact_rail_section("Filters")
        )
        rail_content_layout.addWidget(self._stats_filter_section)
        self._stats_insight_section, self._stats_insights_layout = (
            self._build_compact_rail_section("K Distribution")
        )
        rail_content_layout.addWidget(self._stats_insight_section)
        self._stats_summary_section, self._stats_summary_layout = (
            self._build_compact_rail_section("Coverage")
        )
        rail_content_layout.addWidget(self._stats_summary_section)
        self._stats_group_section, self._stats_group_layout = (
            self._build_compact_rail_section("Groups")
        )
        rail_content_layout.addWidget(self._stats_group_section)
        self._stats_visible_table_section, self._stats_visible_table_layout = (
            self._build_compact_rail_section("Visible Table")
        )
        rail_content_layout.addWidget(self._stats_visible_table_section)
        self._stats_status_legend_section, self._stats_status_legend_layout = (
            self._build_compact_rail_section("Status Legend")
        )
        self._stats_status_legend_layout.addWidget(
            self._make_rail_legend_row(
                [
                    ("included", C.OLIVE),
                    ("warned", C.LED_WARN),
                    ("missing", C.TEXT_MUTED),
                ]
            )
        )
        rail_content_layout.addWidget(self._stats_status_legend_section)
        rail_content_layout.addStretch(1)
        rail_scroll.setWidget(rail_content)
        rv.addWidget(rail_scroll, 1)

        bh.addWidget(main, 1)
        bh.addWidget(rail, 0)
        root.addWidget(body, 1)
        self._refresh_stats_workspace()
        return page

    def _build_stats_panel(
        self,
        title: str,
        canvas: FigureCanvas,
        *,
        meta_attr: str,
        table: QTableWidget | None = None,
        table_title: str = "",
    ) -> QWidget:
        panel = QWidget()
        panel.setMinimumSize(0, 0)
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
        if table is None:
            v.addWidget(canvas, 1)
        else:
            splitter = QSplitter(Qt.Orientation.Vertical)
            splitter.setChildrenCollapsible(False)
            splitter.setHandleWidth(5)
            splitter.setStyleSheet(f"""
                QSplitter::handle {{
                    background: rgba(188,169,142,0.42);
                    border-radius: 2px;
                }}
            """)
            canvas_wrap = QWidget()
            canvas_wrap.setMinimumSize(0, 0)
            canvas_layout = QVBoxLayout(canvas_wrap)
            canvas_layout.setContentsMargins(0, 0, 0, 0)
            canvas_layout.setSpacing(0)
            canvas_layout.addWidget(canvas)
            splitter.addWidget(canvas_wrap)
            table_wrap = QWidget()
            table_wrap.setMinimumSize(0, 0)
            table_layout = QVBoxLayout(table_wrap)
            table_layout.setContentsMargins(0, 0, 0, 0)
            table_layout.setSpacing(6)
            if table_title:
                table_lbl = QLabel(table_title)
                table_lbl.setStyleSheet(
                    f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; font-weight: 800;"
                    f"letter-spacing: 0.08em; color: {C.TEXT_MUTED}; background: transparent;"
                )
                table_layout.addWidget(table_lbl, 0)
            table_layout.addWidget(table, 1)
            splitter.addWidget(table_wrap)
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 2)
            splitter.setSizes([420, 240])
            v.addWidget(splitter, 1)
        return panel

    @staticmethod
    def _style_stats_table(table: QTableWidget) -> None:
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.setSortingEnabled(False)
        table.horizontalHeader().setSectionsClickable(False)
        table.horizontalHeader().setSortIndicatorShown(False)
        table.horizontalHeader().setMinimumSectionSize(72)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setMinimumWidth(0)
        table.setMinimumHeight(180)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        table.setStyleSheet(f"""
            QTableWidget {{
                background: rgba(255,255,255,0.30);
                border: 1px solid rgba(188,169,142,0.64);
                border-radius: 8px;
            }}
            QTableWidget::item {{
                border-bottom: 1px solid rgba(215,203,184,0.50);
                padding: 4px 8px;
            }}
            QHeaderView::section {{
                background: {C.BG_RAISED};
                border: none;
                border-bottom: 1px solid {C.BORDER_DK};
                border-right: 1px solid rgba(212,196,168,0.45);
                padding: 5px 8px;
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                font-weight: 700;
                color: {C.TEXT_MID};
            }}
            QScrollBar:vertical {{
                width: 6px; background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER}; border-radius: 3px; min-height: 18px;
            }}
            QScrollBar:horizontal {{
                height: 8px; background: transparent;
            }}
            QScrollBar::handle:horizontal {{
                background: {C.BORDER}; border-radius: 3px; min-width: 18px;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
        """)

    def _build_stats_dataset_strip(self) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet(
            f"background: rgba(255,255,255,0.34); border-bottom: 1px solid {C.BORDER};"
        )
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

    def _sync_stats_controls(self) -> None:
        if not hasattr(self, "_stats_view_spread_btn"):
            return
        self._set_segment_checked(
            self._stats_view_spread_btn, self._stats_view_mode == "spread"
        )
        self._set_segment_checked(
            self._stats_view_coverage_btn, self._stats_view_mode == "coverage"
        )
        self._set_segment_checked(
            self._stats_metric_geo_btn, self._stats_metric == "geometric"
        )
        self._set_segment_checked(
            self._stats_metric_arith_btn, self._stats_metric == "arithmetic"
        )
        self._set_segment_checked(
            self._stats_metric_med_btn, self._stats_metric == "median"
        )
        valid_in_all = (
            self._stats_common_methods_only or self._stats_method_scope == "valid_all"
        )
        self._set_segment_checked(self._stats_methods_all_btn, not valid_in_all)
        self._set_segment_checked(self._stats_methods_valid_all_btn, valid_in_all)
        self._set_segment_checked(self._stats_methods_choose_btn, False)
        self._stats_methods_choose_btn.setEnabled(True)
        self._set_segment_checked(
            self._stats_ok_only_btn, not self._stats_include_warnings
        )
        self._set_segment_checked(
            self._stats_warnings_btn, self._stats_include_warnings
        )
        if hasattr(self, "_stats_stack"):
            self._stats_stack.setCurrentWidget(
                self._stats_coverage_panel
                if self._stats_view_mode == "coverage"
                else self._stats_spread_panel
            )

    def _set_stats_view_mode(self, mode: str) -> None:
        if mode == self._stats_view_mode:
            return
        self._stats_view_mode = mode
        self._sync_stats_controls()
        self._refresh_stats_workspace()

    def _set_stats_method_scope(self, *, valid_in_all: bool) -> None:
        target_scope = "valid_all" if valid_in_all else "all"
        if (
            self._stats_method_scope == target_scope
            and self._stats_common_methods_only == valid_in_all
        ):
            return
        self._stats_method_scope = target_scope
        self._stats_common_methods_only = valid_in_all
        self._sync_stats_controls()
        if self.selected_datasets:
            self._refresh_comparison_surfaces(include_plot=False)
        else:
            self._refresh_stats_workspace()

    def _set_stats_warning_scope(self, include_warnings: bool) -> None:
        if self._stats_include_warnings == include_warnings:
            return
        self._stats_include_warnings = include_warnings
        self._sync_stats_controls()
        if self.selected_datasets:
            self._refresh_comparison_surfaces(include_plot=False)
        else:
            self._refresh_stats_workspace()

    def _on_stats_metric_changed(self, metric: str) -> None:
        if metric == self._stats_metric:
            return
        self._stats_metric = metric
        self._sync_stats_controls()
        if self.selected_datasets:
            self._refresh_stats()
        else:
            self._refresh_stats_workspace()

    def _on_stats_method_scope_changed(self) -> None:
        if not hasattr(self, "_stats_method_combo"):
            return
        scope = self._stats_method_combo.currentData()
        if not scope or scope == self._stats_method_scope:
            return
        self._stats_method_scope = str(scope)
        if self.selected_datasets:
            self._refresh_comparison_surfaces(include_plot=False)

    def _on_stats_ok_only_changed(self, checked: bool) -> None:
        self._stats_include_warnings = not bool(checked)
        self._sync_stats_controls()
        if self.selected_datasets:
            self._refresh_comparison_surfaces(include_plot=False)

    def _on_stats_common_methods_changed(self, checked: bool) -> None:
        self._stats_common_methods_only = bool(checked)
        self._stats_method_scope = "valid_all" if checked else "all"
        self._sync_stats_controls()
        if self.selected_datasets:
            self._refresh_comparison_surfaces(include_plot=False)

    def _stats_unit_symbol(self) -> str:
        return HydraulicConductivityConverter.UNIT_SYMBOLS[self._stats_k_unit]

    def _format_stats_k_value(self, value_m_s: float) -> str:
        converted = HydraulicConductivityConverter.convert_from_m_per_s(
            value_m_s, self._stats_k_unit
        )
        return HydraulicConductivityConverter.DISPLAY_FORMATS[
            self._stats_k_unit
        ].format(converted)

    def _stats_metric_label(self) -> str:
        return {
            "geometric": "Geo. mean",
            "arithmetic": "Arith. mean",
            "median": "Median",
        }.get(self._stats_metric, "Geo. mean")

    def _stats_metric_value(self, stats) -> Optional[float]:
        if stats is None:
            return None
        if self._stats_metric == "arithmetic":
            return stats.arithmetic_mean_m_s
        if self._stats_metric == "median":
            return stats.median_m_s
        return stats.geometric_mean_m_s

    def _aggregation_options(self) -> KAggregationOptions:
        selected_methods = None
        return KAggregationOptions.from_methods(
            selected_methods,
            include_warnings=self._stats_include_warnings,
            include_errors=False,
            require_methods_in_all_datasets=(
                self._stats_common_methods_only
                or self._stats_method_scope == "valid_all"
            ),
            method_order=tuple(self._K_METHOD_ORDER),
        )

    def _snapshot_options(self) -> ComparisonSnapshotOptions:
        return ComparisonSnapshotOptions(
            k_options=self._aggregation_options(),
            classification_scheme=self._active_scheme,
        )

    def _build_comparison_snapshot(self):
        return build_comparison_snapshot(
            self.selected_datasets, self._snapshot_options()
        )

    def _build_k_aggregation(self):
        return self._build_comparison_snapshot().k

    def _ordered_k_methods(self, method_names) -> list[str]:
        seen = set(method_names)
        ordered = [name for name in self._K_METHOD_ORDER if name in seen]
        extras = sorted(seen.difference(self._K_METHOD_ORDER))
        return ordered + extras

    def _make_stats_summary_row(self, label: str, value: str) -> QWidget:
        row = QWidget()
        row.setObjectName("statsSummaryRow")
        row.setStyleSheet(
            "QWidget#statsSummaryRow { background: transparent; border: none; }"
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 3, 0, 3)
        h.setSpacing(10)
        key_lbl = QLabel(label)
        key_lbl.setMinimumWidth(0)
        key_lbl.setMaximumWidth(132)
        key_lbl.setWordWrap(True)
        key_lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; color: {C.TEXT_MUTED}; background: transparent; border: none; font-weight: 600;"
        )
        val_lbl = QLabel(value)
        val_lbl.setMinimumWidth(0)
        val_lbl.setMaximumWidth(188)
        val_lbl.setWordWrap(True)
        val_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        val_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_SM}pt; color: {C.TEXT_MID}; background: transparent; border: none; font-weight: 600;"
        )
        h.addWidget(key_lbl, 1)
        h.addWidget(val_lbl, 1, Qt.AlignmentFlag.AlignRight)
        return row

    def _build_compact_rail_header(self, title: str, subtitle: str, badge: str):
        head = QFrame()
        head.setObjectName("compactRailHeader")
        head.setFixedHeight(42)
        head.setStyleSheet(
            f"""
            QFrame#compactRailHeader {{
                background: {C.BG_RAISED};
                border: none;
                border-bottom: 1px solid {C.BORDER};
            }}
            QFrame#compactRailHeader QLabel {{ border: none; background: transparent; }}
            """
        )
        h = QHBoxLayout(head)
        h.setContentsMargins(12, 0, 12, 0)
        h.setSpacing(8)

        copy = QWidget()
        copy.setStyleSheet("background: transparent; border: none;")
        cv = QVBoxLayout(copy)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(1)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size: {F.SZ_BASE}pt; font-weight: 700; color: {C.TEXT};"
        )
        subtitle_lbl = QLabel(subtitle)
        subtitle_lbl.setMinimumWidth(0)
        subtitle_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        subtitle_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; font-weight: 600;"
            f"color: {C.TEXT_MUTED};"
        )
        cv.addWidget(title_lbl)
        cv.addWidget(subtitle_lbl)

        badge_lbl = QLabel(badge)
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_lbl.setStyleSheet(
            f"padding: 2px 8px; border: 1px solid rgba(107,142,35,0.25);"
            f"border-radius: 999px; background: rgba(107,142,35,0.08);"
            f"color: {C.OLIVE_DK}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            f"font-weight: 800;"
        )

        h.addWidget(copy, 1)
        h.addWidget(badge_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        return head, title_lbl, subtitle_lbl, badge_lbl

    def _set_compact_rail_header(
        self,
        title_lbl: QLabel,
        subtitle_lbl: QLabel,
        badge_lbl: QLabel,
        *,
        title: str,
        subtitle: str,
        badge: str,
    ) -> None:
        title_lbl.setText(title)
        subtitle_lbl.setText(subtitle)
        badge_lbl.setText(badge)

    def _build_compact_rail_section(self, title: str):
        section = QWidget()
        section.setObjectName("compactRailSection")
        section.setStyleSheet(
            "QWidget#compactRailSection { background: transparent; border: none; }"
            "QWidget#compactRailSection QLabel { border: none; }"
        )
        v = QVBoxLayout(section)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(7)

        hdr = QLabel(title.upper())
        hdr.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; font-weight: 800;"
            f"letter-spacing: 0.08em; color: {C.TEXT_MUTED}; background: transparent;"
        )
        v.addWidget(hdr)

        content = QVBoxLayout()
        content.setSpacing(7)
        content.setContentsMargins(0, 0, 0, 0)
        v.addLayout(content)
        return section, content

    def _make_rail_chip(self, text: str, *, tone: str = "neutral") -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(False)
        if tone == "ok":
            bg, fg, border = (
                "rgba(107,142,35,0.08)",
                C.OLIVE_DK,
                "rgba(107,142,35,0.23)",
            )
        elif tone == "warn":
            bg, fg, border = "rgba(196,165,116,0.13)", C.EARTH, "rgba(196,165,116,0.36)"
        else:
            bg, fg, border = (
                "rgba(255,255,255,0.44)",
                C.TEXT_MID,
                "rgba(212,196,168,0.82)",
            )
        lbl.setStyleSheet(
            f"padding: 3px 7px; border: 1px solid {border}; border-radius: 999px;"
            f"background: {bg}; color: {fg}; font-size: {F.SZ_XS + 1}pt; font-weight: 700;"
        )
        return lbl

    def _make_rail_chip_group(self, chips: list[tuple[str, str]]) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent; border: none;")
        grid = QGridLayout(wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for idx, (text, tone) in enumerate(chips):
            grid.addWidget(self._make_rail_chip(text, tone=tone), idx // 2, idx % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        return wrap

    def _make_rail_headline(self, label: str, subtext: str, value: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent; border: none;")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        copy = QWidget()
        copy.setStyleSheet("background: transparent; border: none;")
        cv = QVBoxLayout(copy)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(1)
        label_lbl = QLabel(label)
        label_lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; font-weight: 800; color: {C.TEXT_MID};"
            f"background: transparent;"
        )
        sub_lbl = QLabel(subtext)
        sub_lbl.setMinimumWidth(0)
        sub_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        sub_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; font-weight: 600;"
            f"color: {C.TEXT_MUTED}; background: transparent;"
        )
        cv.addWidget(label_lbl)
        cv.addWidget(sub_lbl)

        value_lbl = QLabel(value)
        value_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom
        )
        value_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_BASE + 5}pt; font-weight: 800;"
            f"color: {C.TEXT}; background: transparent;"
        )
        h.addWidget(copy, 1)
        h.addWidget(value_lbl, 0)
        return row

    def _make_rail_metric(self, label: str, value: str) -> QWidget:
        metric = QFrame()
        metric.setObjectName("compactRailMetric")
        metric.setStyleSheet(
            f"""
            QFrame#compactRailMetric {{
                background: rgba(255,255,255,0.32);
                border: 1px solid rgba(212,196,168,0.62);
                border-radius: 4px;
            }}
            QFrame#compactRailMetric QLabel {{ border: none; background: transparent; }}
            """
        )
        v = QVBoxLayout(metric)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(2)
        key = QLabel(label)
        key.setMinimumWidth(0)
        key.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        key.setStyleSheet(
            f"font-size: {F.SZ_XS + 1}pt; font-weight: 700; color: {C.TEXT_MUTED};"
        )
        val = QLabel(value)
        val.setMinimumWidth(0)
        val.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        val.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_SM}pt; font-weight: 800;"
            f"color: {C.TEXT};"
        )
        v.addWidget(key)
        v.addWidget(val)
        return metric

    def _add_rail_metric_grid(
        self, layout: QVBoxLayout, metrics: list[tuple[str, str]]
    ) -> None:
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent; border: none;")
        grid = QGridLayout(wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for idx, (label, value) in enumerate(metrics):
            grid.addWidget(self._make_rail_metric(label, value), idx // 2, idx % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(wrap)

    def _make_rail_status_line(self, text: str, *, tone: str = "ok") -> QWidget:
        row = QFrame()
        row.setObjectName("compactRailStatus")
        if tone == "warn":
            bg, fg, border = "rgba(196,165,116,0.14)", C.EARTH, "rgba(196,165,116,0.34)"
        else:
            bg, fg, border = (
                "rgba(107,142,35,0.07)",
                C.OLIVE_DK,
                "rgba(107,142,35,0.22)",
            )
        row.setStyleSheet(
            f"""
            QFrame#compactRailStatus {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 4px;
            }}
            QFrame#compactRailStatus QLabel {{ border: none; background: transparent; }}
            """
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 6, 8, 6)
        h.setSpacing(6)
        mark = QLabel("OK" if tone != "warn" else "WARN")
        mark.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; font-weight: 800;"
            f"color: {fg};"
        )
        body = QLabel(text)
        body.setWordWrap(True)
        body.setStyleSheet(f"font-size: {F.SZ_SM}pt; font-weight: 700; color: {fg};")
        h.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        h.addWidget(body, 1)
        return row

    def _make_rail_group_row(
        self, name: str, meta: str, value: str, color: str
    ) -> QWidget:
        row = QFrame()
        row.setObjectName("compactRailGroupRow")
        row.setStyleSheet(
            f"""
            QFrame#compactRailGroupRow {{
                background: rgba(255,255,255,0.30);
                border: 1px solid rgba(212,196,168,0.62);
                border-radius: 4px;
            }}
            QFrame#compactRailGroupRow QLabel {{ border: none; background: transparent; }}
            """
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 7, 8, 7)
        h.setSpacing(8)

        swatch = QFrame()
        swatch.setFixedSize(8, 34)
        swatch.setStyleSheet(f"background: {color}; border: none; border-radius: 3px;")

        copy = QWidget()
        copy.setStyleSheet("background: transparent; border: none;")
        cv = QVBoxLayout(copy)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(1)
        name_lbl = QLabel(name)
        name_lbl.setMinimumWidth(0)
        name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        name_lbl.setStyleSheet(
            f"font-size: {F.SZ_SM}pt; font-weight: 800; color: {C.TEXT};"
        )
        meta_lbl = QLabel(meta)
        meta_lbl.setMinimumWidth(0)
        meta_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        meta_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; font-weight: 600;"
            f"color: {C.TEXT_MUTED};"
        )
        cv.addWidget(name_lbl)
        cv.addWidget(meta_lbl)

        value_lbl = QLabel(value)
        value_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        value_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS + 1}pt; font-weight: 800;"
            f"color: {C.TEXT};"
        )
        h.addWidget(swatch)
        h.addWidget(copy, 1)
        h.addWidget(value_lbl, 0)
        return row

    def _make_rail_legend_row(self, entries: list[tuple[str, str]]) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent; border: none;")
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        for label, color in entries:
            pill = QWidget()
            pill.setObjectName("compactLegendPill")
            pill.setStyleSheet(
                f"""
                QWidget#compactLegendPill {{
                    background: rgba(255,255,255,0.28);
                    border: 1px solid rgba(212,196,168,0.76);
                    border-radius: 999px;
                }}
                QWidget#compactLegendPill QLabel {{ border: none; background: transparent; }}
                """
            )
            ph = QHBoxLayout(pill)
            ph.setContentsMargins(7, 3, 7, 3)
            ph.setSpacing(5)
            dot = QFrame()
            dot.setFixedSize(16, 16)
            dot.setStyleSheet(
                f"background: {color}; border: 1px solid rgba(92,78,61,0.28); border-radius: 4px;"
            )
            text = QLabel(label)
            text.setStyleSheet(
                f"font-size: {F.SZ_XS + 1}pt; font-weight: 700; color: {C.TEXT_MID};"
            )
            ph.addWidget(dot)
            ph.addWidget(text)
            h.addWidget(pill)
        h.addStretch(1)
        return wrap

    def _clear_stats_tables(self) -> None:
        for table in (
            getattr(self, "_stats_scope_table", None),
            getattr(self, "_stats_method_table", None),
        ):
            if table is None:
                continue
            table.clearContents()
            table.setRowCount(0)
            table.setColumnCount(0)

    def _set_stats_table_item(
        self,
        table: QTableWidget,
        row: int,
        col: int,
        text: str,
        *,
        color: str = C.TEXT_MID,
        bold: bool = False,
        align_right: bool = True,
        background: str | None = None,
    ) -> None:
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setForeground(QBrush(QColor(color)))
        if background:
            item.setBackground(QBrush(QColor(background)))
        font = QFont(F.MONO if align_right else F.UI, F.SZ_SM)
        font.setBold(bold)
        item.setFont(font)
        item.setTextAlignment(
            (Qt.AlignmentFlag.AlignRight if align_right else Qt.AlignmentFlag.AlignLeft)
            | Qt.AlignmentFlag.AlignVCenter
        )
        table.setItem(row, col, item)

    def _stats_k_range_text(self, stats) -> str:
        if stats is None or stats.min_m_s is None or stats.max_m_s is None:
            return "-"
        return f"{self._format_stats_k_value(stats.min_m_s)} - {self._format_stats_k_value(stats.max_m_s)}"

    def _stats_k_text(self, value: Optional[float]) -> str:
        return self._format_stats_k_value(value) if value is not None else "-"

    def _grain_metric_text(self, grain_stats, metric_key: str, suffix: str = "") -> str:
        if grain_stats is None:
            return "-"
        metric = grain_stats.metrics.get(metric_key)
        value = metric.median if metric is not None else None
        return self._format_grain_summary_value(value, suffix)

    def _refresh_stats_scope_table(self, snapshot) -> None:
        table = self._stats_scope_table
        headers = [
            "Scope",
            "Datasets",
            "Included K",
            f"Geo. mean K ({self._stats_unit_symbol()})",
            f"Arith. mean K ({self._stats_unit_symbol()})",
            f"Median K ({self._stats_unit_symbol()})",
            f"K range ({self._stats_unit_symbol()})",
            "Log spread",
            "D50 median",
            "Mean grain size",
            "Cu median",
            "Fines median",
            "Dominant class",
        ]
        table.setSortingEnabled(False)
        table.clearContents()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        aggregation = snapshot.k
        grain = snapshot.grain
        grouped = self._stats_uses_group_scope()
        rows = [
            (
                "Overall",
                "all selected datasets",
                aggregation.overall,
                grain.overall,
                C.EARTH,
            )
        ]
        if grouped:
            group_colors = self._group_color_map(list(aggregation.group_names))
            for group_name in aggregation.group_names:
                rows.append(
                    (
                        group_name,
                        "group aggregate",
                        aggregation.by_group.get(group_name),
                        grain.by_group.get(group_name),
                        group_colors.get(group_name, C.TEXT_MID),
                    )
                )
        else:
            for idx, dataset_name in enumerate(aggregation.dataset_names):
                rows.append(
                    (
                        dataset_name,
                        "dataset",
                        aggregation.by_dataset.get(dataset_name),
                        grain.by_dataset.get(dataset_name),
                        DATASET_COLORS[idx % len(DATASET_COLORS)],
                    )
                )

        table.setRowCount(len(rows))
        for row_i, (scope_name, subtitle, k_stats, grain_stats, color) in enumerate(
            rows
        ):
            scope_text = f"{scope_name}\n{subtitle}" if subtitle else scope_name
            self._set_stats_table_item(
                table, row_i, 0, scope_text, color=color, bold=True, align_right=False
            )
            self._set_stats_table_item(
                table, row_i, 1, str(getattr(k_stats, "dataset_count", 0))
            )
            included = f"{getattr(k_stats, 'included_count', 0)} / {getattr(k_stats, 'total_cells', 0)}"
            self._set_stats_table_item(table, row_i, 2, included)
            self._set_stats_table_item(
                table,
                row_i,
                3,
                self._stats_k_text(getattr(k_stats, "geometric_mean_m_s", None)),
            )
            self._set_stats_table_item(
                table,
                row_i,
                4,
                self._stats_k_text(getattr(k_stats, "arithmetic_mean_m_s", None)),
            )
            self._set_stats_table_item(
                table,
                row_i,
                5,
                self._stats_k_text(getattr(k_stats, "median_m_s", None)),
            )
            self._set_stats_table_item(
                table, row_i, 6, self._stats_k_range_text(k_stats)
            )
            log_spread = getattr(k_stats, "log10_std_dev", None)
            self._set_stats_table_item(
                table, row_i, 7, f"{log_spread:.2f}" if log_spread is not None else "-"
            )
            self._set_stats_table_item(
                table, row_i, 8, self._grain_metric_text(grain_stats, "D50", " mm")
            )
            self._set_stats_table_item(
                table, row_i, 9, self._grain_metric_text(grain_stats, "Dmean", " mm")
            )
            self._set_stats_table_item(
                table, row_i, 10, self._grain_metric_text(grain_stats, "Cu")
            )
            self._set_stats_table_item(
                table, row_i, 11, self._grain_metric_text(grain_stats, "Fines%", "%")
            )
            self._set_stats_table_item(
                table,
                row_i,
                12,
                getattr(grain_stats, "dominant_class", "N/A")
                if grain_stats is not None
                else "N/A",
                align_right=False,
            )
            table.setRowHeight(row_i, 42)

        table.resizeColumnsToContents()
        table.setColumnWidth(0, max(165, table.columnWidth(0)))
        table.horizontalHeader().setStretchLastSection(False)

    def _refresh_stats_method_table(self, snapshot) -> None:
        table = self._stats_method_table
        headers = [
            "Method",
            "Included",
            "Warnings",
            "Missing / excluded",
            "Valid all datasets",
            "Valid groups",
            f"Geo. mean K ({self._stats_unit_symbol()})",
            f"Median K ({self._stats_unit_symbol()})",
            f"K range ({self._stats_unit_symbol()})",
            "Status",
        ]
        table.setSortingEnabled(False)
        table.clearContents()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        aggregation = snapshot.k
        groups = list(aggregation.group_names)
        dataset_count_by_group = {
            group: aggregation.by_group[group].dataset_count
            for group in groups
            if group in aggregation.by_group
        }
        records_by_method = {
            method: [
                record for record in aggregation.records if record.method_name == method
            ]
            for method in aggregation.method_names
        }

        table.setRowCount(len(aggregation.method_names))
        for row_i, method_name in enumerate(aggregation.method_names):
            method_stats = aggregation.by_method.get(method_name)
            records = records_by_method.get(method_name, [])
            valid_group_count = 0
            for group_name in groups:
                group_records = [
                    record for record in records if record.group_name == group_name
                ]
                included_count = sum(1 for record in group_records if record.included)
                if (
                    dataset_count_by_group.get(group_name, 0)
                    and included_count == dataset_count_by_group[group_name]
                ):
                    valid_group_count += 1

            included = f"{getattr(method_stats, 'included_count', 0)} / {getattr(method_stats, 'total_cells', 0)}"
            missing_excluded = getattr(method_stats, "missing_count", 0) + getattr(
                method_stats, "excluded_count", 0
            )
            warning_count = getattr(method_stats, "warning_count", 0)
            valid_all = "Yes" if method_name in aggregation.complete_methods else "No"
            if getattr(method_stats, "included_count", 0) == 0:
                status, status_color, bg = "Sparse", C.TEXT_MUTED, "#f3eee4"
            elif warning_count or missing_excluded:
                status, status_color, bg = "Warn", C.LED_WARN, "#f8eedb"
            else:
                status, status_color, bg = "OK", C.OLIVE, "#eef5e2"

            self._set_stats_table_item(
                table, row_i, 0, method_name, bold=True, align_right=False
            )
            self._set_stats_table_item(table, row_i, 1, included)
            self._set_stats_table_item(
                table,
                row_i,
                2,
                str(warning_count),
                color=C.LED_WARN if warning_count else C.TEXT_MID,
            )
            self._set_stats_table_item(
                table,
                row_i,
                3,
                str(missing_excluded),
                color=C.TEXT_MUTED if missing_excluded else C.TEXT_MID,
            )
            self._set_stats_table_item(
                table,
                row_i,
                4,
                valid_all,
                color=C.OLIVE if valid_all == "Yes" else C.TEXT_MUTED,
            )
            self._set_stats_table_item(
                table, row_i, 5, f"{valid_group_count} / {len(groups)}"
            )
            self._set_stats_table_item(
                table,
                row_i,
                6,
                self._stats_k_text(getattr(method_stats, "geometric_mean_m_s", None)),
            )
            self._set_stats_table_item(
                table,
                row_i,
                7,
                self._stats_k_text(getattr(method_stats, "median_m_s", None)),
            )
            self._set_stats_table_item(
                table, row_i, 8, self._stats_k_range_text(method_stats)
            )
            self._set_stats_table_item(
                table, row_i, 9, status, color=status_color, bold=True, background=bg
            )
            table.setRowHeight(row_i, 36)

        table.resizeColumnsToContents()
        table.setColumnWidth(0, max(150, table.columnWidth(0)))
        table.horizontalHeader().setStretchLastSection(False)

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
        if hasattr(self._plot_widget, "set_scheme"):
            self._plot_widget.set_scheme(scheme)
        if len(self.selected_datasets) >= 2:
            self.update_comparison()

    def _set_selected_datasets(self, selected_tabs) -> None:
        """Apply a selected subset while preserving dataset order and visibility."""
        selected_names = {tab.get_dataset_name() for tab in selected_tabs}
        self.selected_datasets = [
            tab for tab in self.dataset_tabs if tab.get_dataset_name() in selected_names
        ]
        if not self.selected_datasets and self.dataset_tabs:
            self.selected_datasets = list(self.dataset_tabs)

        active_names = {tab.get_dataset_name() for tab in self.selected_datasets}
        self._plot_hidden = {name for name in self._plot_hidden if name in active_names}
        self._plot_group_selection.intersection_update(active_names)
        if self._plot_group_selection_anchor not in active_names:
            self._plot_group_selection_anchor = None

        if len(self.selected_datasets) < 2:
            self._clear_views()
        self._refresh_plot_visibility_list()
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
                tab
                for tab in self.dataset_tabs
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
            self._clear_views()
            self._update_header_count()
            return
        self._refresh_comparison_surfaces(include_plot=True)
        self.comparison_updated.emit()

    def _refresh_comparison_surfaces(self, *, include_plot: bool = True) -> None:
        """Rebuild every comparison surface from the current selected datasets."""
        if len(self.selected_datasets) < 2:
            self._clear_views()
            self._update_header_count()
            return
        if include_plot:
            self._update_plot()
        self._refresh_details_views()
        self._refresh_stats()
        self._update_header_count()

    # ── Internal update helpers ───────────────────────────────────────────────

    def _update_header_count(self) -> None:
        n_loaded = len(self.dataset_tabs)
        n_selected = len(self.selected_datasets)
        n_plotted = len(self._plot_dataset_tabs()) if self.selected_datasets else 0
        if not self.selected_datasets:
            plot_scope = "no plot scope"
        elif self._plot_hidden:
            plot_scope = f"{n_plotted} visible in plot"
        else:
            plot_scope = "all scoped visible"
        self._count_label.setText(
            "Load datasets to compare"
            if n_loaded == 0
            else f"{n_selected} selected  ·  {n_loaded} loaded  ·  {plot_scope}"
        )
        if hasattr(self, "_plot_show_all_btn"):
            self._plot_show_all_btn.setEnabled(bool(self._plot_hidden))

    def _plot_dataset_tabs(self) -> list:
        """Return the selected datasets currently visible in the plot."""
        return [
            tab
            for tab in self.selected_datasets
            if tab.get_dataset_name() not in self._plot_hidden
        ]

    def _update_plot(self) -> None:
        """Push datasets into the comparison plot widget."""
        if not self.selected_datasets:
            if hasattr(self._plot_widget, "show_empty_state"):
                self._plot_widget.show_empty_state(
                    "Select at least 2 datasets in Scope & Groups"
                )
            return
        plot_tabs = self._plot_dataset_tabs()
        if hasattr(self._plot_widget, "set_scheme"):
            self._plot_widget.set_scheme(self._active_scheme)
        if not plot_tabs:
            self._plot_widget.set_datasets([])
            if hasattr(self._plot_widget, "show_empty_state"):
                self._plot_widget.show_empty_state("No datasets visible in this plot")
            return
        self._plot_widget.set_datasets(plot_tabs)
        if hasattr(self._plot_widget, "refresh_plot"):
            self._plot_widget.refresh_plot()

    def _clear_views(self) -> None:
        """Clear stale comparison output when fewer than two datasets are selected."""
        if hasattr(self._plot_widget, "show_empty_state"):
            self._plot_widget.show_empty_state("Select at least 2 datasets to compare")

        for table in (self._grain_table, self._k_table, self._aggregate_table):
            table.clearContents()
            table.setRowCount(0)
            table.setColumnCount(0)

        if hasattr(self, "_details_dataset_chips_layout"):
            self._refresh_details_views()

        for fig, canvas, message in [
            (self._box_fig, self._box_canvas, "Select at least 2 datasets to compare"),
            (
                self._heat_fig,
                self._heat_canvas,
                "Select at least 2 datasets to compare",
            ),
        ]:
            fig.clear()
            ax = fig.add_subplot(1, 1, 1)
            ax.text(
                0.5,
                0.5,
                message,
                transform=ax.transAxes,
                ha="center",
                va="center",
                fontsize=11,
                color=C.TEXT_MUTED,
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
        if label == "Dmean":
            if hasattr(dataset, "get_arithmetic_mean_grain_size"):
                return dataset.get_arithmetic_mean_grain_size()
            return None
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

    def _make_param_cell(
        self,
        label: str,
        description: str,
        olive: bool,
        *,
        summary: bool = False,
    ) -> QWidget:
        """Build a two-line parameter cell widget (name + description)."""
        w = QWidget()
        w.setObjectName("detailParamCell")
        w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        bg = C.BG_LOW if summary else C.BG
        border = (
            "2px solid rgba(139,117,84,0.30)"
            if summary
            else "1px solid rgba(212,196,168,0.45)"
        )
        w.setStyleSheet(
            f"QWidget#detailParamCell {{ background: {bg}; border-bottom: {border}; }}"
            "QWidget#detailParamCell QLabel { border: none; }"
        )
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 5, 10, 5)
        lay.setSpacing(1)
        name_lbl = QLabel(label)
        name_lbl.setWordWrap(False)
        name_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_BASE}pt; font-weight: 600;"
            f"color: {C.OLIVE if olive else C.TEXT_MID}; background: transparent; border: none;"
        )
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(False)
        desc_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: 8pt;"
            f"color: {C.TEXT_MUTED}; background: transparent; border: none;"
        )
        lay.addWidget(name_lbl)
        lay.addWidget(desc_lbl)
        return w

    def _make_value_cell(
        self,
        text: str,
        color: str,
        background: str,
        *,
        bold: bool = False,
        summary: bool = False,
    ) -> QWidget:
        """Build an explicit value surface so heat fills render reliably."""
        w = QWidget()
        w.setObjectName("detailValueCell")
        w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        border = (
            "2px solid rgba(139,117,84,0.30)"
            if summary
            else "1px solid rgba(212,196,168,0.45)"
        )
        w.setStyleSheet(
            f"QWidget#detailValueCell {{ background: {background}; border-bottom: {border}; }}"
            "QWidget#detailValueCell QLabel { border: none; }"
        )
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 0, 10, 0)
        lay.setSpacing(0)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        weight = 700 if bold else 500
        lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_SM}pt;"
            f"font-weight: {weight}; color: {color}; background: transparent; border: none;"
        )
        lay.addWidget(lbl)
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
        converted = HydraulicConductivityConverter.convert_from_m_per_s(
            value_m_s, self._details_k_unit
        )
        return HydraulicConductivityConverter.DISPLAY_FORMATS[
            self._details_k_unit
        ].format(converted)

    def _configure_details_columns(
        self, table: QTableWidget, column_count: int
    ) -> None:
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, _DETAILS_ROW_HEADER_WIDTH)
        data_resize_mode = (
            QHeaderView.ResizeMode.Stretch
            if column_count <= 8
            else QHeaderView.ResizeMode.ResizeToContents
        )
        for c in range(1, column_count):
            header.setSectionResizeMode(c, data_resize_mode)
            if data_resize_mode == QHeaderView.ResizeMode.ResizeToContents:
                table.setColumnWidth(c, max(120, table.columnWidth(c)))

    def _apply_grain_row_preset(self) -> None:
        allowed = self._GRAIN_PRESETS[self._details_preset]
        for row_i, (label, *_rest) in enumerate(self._GRAIN_ROWS):
            self._grain_table.setRowHidden(
                row_i, allowed is not None and label not in allowed
            )

    def _apply_k_row_preset(
        self, method_names: list[str], summary_rows: list[tuple[str, str]]
    ) -> None:
        if self._details_preset == "core":
            allowed_methods = None
            allowed_summaries = None
        elif self._details_preset == "all":
            allowed_methods = set(self._build_k_aggregation().complete_methods)
            allowed_summaries = None
        else:
            allowed_methods = set()
            allowed_summaries = self._K_SUMMARY_LABELS

        for row_i, method in enumerate(method_names):
            self._k_table.setRowHidden(
                row_i, allowed_methods is not None and method not in allowed_methods
            )
        offset = len(method_names)
        for idx, (label, _desc) in enumerate(summary_rows):
            self._k_table.setRowHidden(
                offset + idx,
                allowed_summaries is not None and label not in allowed_summaries,
            )

    def _refresh_aggregate_table(self) -> None:
        """Rebuild the snapshot-backed aggregate details table."""
        snapshot = self._build_comparison_snapshot()
        k_report = snapshot.k
        grain_report = snapshot.grain
        groups = list(k_report.group_names)
        group_colors = self._group_color_map(groups)
        headers = ["Result", "Overall", *groups, "Included", "Status"]
        self._aggregate_table.setSortingEnabled(False)
        self._aggregate_table.clearSpans()
        self._aggregate_table.setColumnCount(len(headers))
        for col_i, label in enumerate(headers):
            header = QTableWidgetItem(label)
            header.setFont(QFont(F.UI, F.SZ_SM, QFont.Weight.Bold))
            if 2 <= col_i < 2 + len(groups):
                color = group_colors.get(groups[col_i - 2], C.TEXT_MID)
                header.setIcon(_dot_icon(color))
                header.setForeground(QBrush(QColor(color)))
                header.setToolTip(f"Group: {label}")
            elif col_i == 1:
                header.setForeground(QBrush(QColor(C.EARTH)))
            else:
                header.setForeground(QBrush(QColor(C.TEXT_MID)))
            self._aggregate_table.setHorizontalHeaderItem(col_i, header)

        rows: list[dict] = []

        def add_section(title: str) -> None:
            rows.append({"section": title})

        def add_row(
            label: str,
            desc: str,
            overall: str,
            group_values: list[str],
            included: str,
            status: str,
        ) -> None:
            rows.append(
                {
                    "label": label,
                    "desc": desc,
                    "overall": overall,
                    "groups": group_values,
                    "included": included,
                    "status": status,
                }
            )

        def k_range(stats) -> str:
            if stats is None or stats.min_m_s is None or stats.max_m_s is None:
                return "-"
            return f"{self._format_k_value(stats.min_m_s)} - {self._format_k_value(stats.max_m_s)}"

        def k_value(stats, attr: str) -> str:
            value = getattr(stats, attr, None) if stats is not None else None
            return self._format_k_value(value) if value is not None else "-"

        def k_group_values(attr: str) -> list[str]:
            return [k_value(k_report.by_group.get(group), attr) for group in groups]

        add_section("K aggregate summaries")
        overall = k_report.overall
        add_row(
            "K geometric mean",
            "Included methods across selected datasets",
            k_value(overall, "geometric_mean_m_s"),
            k_group_values("geometric_mean_m_s"),
            f"{overall.included_count} / {overall.total_cells}",
            self._aggregate_status(overall),
        )
        add_row(
            "K median",
            "Robust center across included values",
            k_value(overall, "median_m_s"),
            k_group_values("median_m_s"),
            f"{overall.included_count} / {overall.total_cells}",
            self._aggregate_status(overall),
        )
        add_row(
            "K arithmetic mean",
            "Linear average of included values",
            k_value(overall, "arithmetic_mean_m_s"),
            k_group_values("arithmetic_mean_m_s"),
            f"{overall.included_count} / {overall.total_cells}",
            self._aggregate_status(overall),
        )
        add_row(
            "K range",
            "Minimum to maximum included value",
            k_range(overall),
            [k_range(k_report.by_group.get(group)) for group in groups],
            f"{overall.included_count} / {overall.total_cells}",
            self._aggregate_status(overall),
        )
        add_row(
            "Permeability class",
            "Class from aggregate geometric mean",
            _perm_class(overall.geometric_mean_m_s)
            if overall.geometric_mean_m_s is not None
            else "-",
            [
                _perm_class(k_report.by_group[group].geometric_mean_m_s)
                if k_report.by_group.get(group) is not None
                and k_report.by_group[group].geometric_mean_m_s is not None
                else "-"
                for group in groups
            ],
            f"{overall.dataset_count} / {overall.dataset_count}",
            "OK" if overall.geometric_mean_m_s is not None else "N/A",
        )

        if k_report.method_names:
            add_section("Method aggregates")
            for method in k_report.method_names:
                method_stats = k_report.by_method.get(method)
                group_values = [
                    self._format_k_value(
                        self._method_group_geometric_mean(k_report, method, group)
                    )
                    if self._method_group_geometric_mean(k_report, method, group)
                    is not None
                    else "-"
                    for group in groups
                ]
                add_row(
                    method,
                    "Geometric mean per scope",
                    k_value(method_stats, "geometric_mean_m_s"),
                    group_values,
                    f"{method_stats.included_count if method_stats is not None else 0} / {method_stats.total_cells if method_stats is not None else 0}",
                    self._aggregate_status(method_stats),
                )

        add_section("Grain aggregate context")
        grain_rows = [
            ("D50 median", "Median diameter per scope", "D50", "median", " mm"),
            (
                "Mean grain size",
                "Arithmetic mean of distribution",
                "Dmean",
                "median",
                " mm",
            ),
            (
                "Fines percent median",
                "Passing at active fines boundary",
                "Fines%",
                "median",
                "%",
            ),
            ("Cu median", "Uniformity coefficient", "Cu", "median", ""),
        ]
        for label, desc, metric_key, attr, suffix in grain_rows:
            metric = grain_report.overall.metrics.get(metric_key)
            overall_value = self._format_grain_summary_value(
                getattr(metric, attr, None) if metric is not None else None, suffix
            )
            group_values = []
            for group in groups:
                group_stats = grain_report.by_group.get(group)
                group_metric = (
                    group_stats.metrics.get(metric_key)
                    if group_stats is not None
                    else None
                )
                group_values.append(
                    self._format_grain_summary_value(
                        getattr(group_metric, attr, None)
                        if group_metric is not None
                        else None,
                        suffix,
                    )
                )
            add_row(
                label,
                desc,
                overall_value,
                group_values,
                f"{metric.value_count if metric is not None else 0} / {grain_report.overall.dataset_count}",
                "OK" if metric is not None and metric.value_count else "N/A",
            )
        add_row(
            "Dominant class",
            "Most common classification label",
            grain_report.overall.dominant_class,
            [
                grain_report.by_group[group].dominant_class
                if group in grain_report.by_group
                else "-"
                for group in groups
            ],
            f"{grain_report.overall.dataset_count} / {grain_report.overall.dataset_count}",
            "OK" if grain_report.overall.dominant_class != "N/A" else "N/A",
        )

        self._aggregate_table.setRowCount(len(rows))
        for row_i, row in enumerate(rows):
            if "section" in row:
                item = QTableWidgetItem(row["section"])
                item.setForeground(QBrush(QColor(C.TEXT_MUTED)))
                item.setBackground(QBrush(QColor(C.BG_LOW)))
                item.setFont(QFont(F.MONO, F.SZ_XS, QFont.Weight.Bold))
                self._aggregate_table.setItem(row_i, 0, item)
                self._aggregate_table.setSpan(row_i, 0, 1, len(headers))
                self._aggregate_table.setRowHeight(row_i, 30)
                continue

            self._aggregate_table.setCellWidget(
                row_i,
                0,
                self._make_param_cell(
                    row["label"], row["desc"], olive=False, summary=False
                ),
            )
            values = [row["overall"], *row["groups"], row["included"], row["status"]]
            for col_i, text in enumerate(values, start=1):
                if 2 <= col_i < 2 + len(groups):
                    text_color = group_colors.get(groups[col_i - 2], C.TEXT_MID)
                elif col_i == len(headers) - 1 and str(text) == "OK":
                    text_color = C.OLIVE
                elif col_i == len(headers) - 1 and str(text) == "Warn":
                    text_color = C.LED_WARN
                else:
                    text_color = C.TEXT_MID
                item = _SortableTableWidgetItem(str(text))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                item.setFont(QFont(F.MONO, F.SZ_SM))
                item.setForeground(QBrush(QColor(text_color)))
                self._aggregate_table.setItem(row_i, col_i, item)
                self._aggregate_table.setCellWidget(
                    row_i,
                    col_i,
                    self._make_value_cell(str(text), text_color, C.BG),
                )
            self._aggregate_table.setRowHeight(row_i, _DETAILS_ROW_HEIGHT)

        self._configure_details_columns(self._aggregate_table, len(headers))
        self._aggregate_table.setSortingEnabled(False)

    @staticmethod
    def _method_group_geometric_mean(
        k_report, method_name: str, group_name: str
    ) -> Optional[float]:
        values = [
            record.k_value
            for record in k_report.included_records
            if record.method_name == method_name
            and record.group_name == group_name
            and record.k_value is not None
            and record.k_value > 0
        ]
        if not values:
            return None
        return float(np.exp(np.mean(np.log(values))))

    @staticmethod
    def _aggregate_status(stats) -> str:
        if stats is None or not getattr(stats, "included_count", 0):
            return "N/A"
        if getattr(stats, "warning_count", 0) or getattr(stats, "excluded_count", 0):
            return "Warn"
        return "OK"

    def _refresh_grain_table(self) -> None:
        """Rebuild the grain parameters table."""
        tabs = self.selected_datasets
        n_ds = len(tabs)
        n_rows = len(self._GRAIN_ROWS)
        dataset_colors = self._dataset_colors_for_tabs(tabs)
        self._grain_table.setSortingEnabled(False)

        # Column layout: Parameter | DS0 | DS1 | …
        self._grain_table.setRowCount(n_rows)
        self._grain_table.setColumnCount(1 + n_ds)

        # ── Column headers ────────────────────────────────────────────────────
        self._grain_table.setHorizontalHeaderItem(0, QTableWidgetItem("Parameter"))
        for col_i, tab in enumerate(tabs):
            name = tab.get_dataset_name()
            color = dataset_colors[col_i]
            hdr_item = self._make_dataset_header_item(name, color)
            self._grain_table.setHorizontalHeaderItem(1 + col_i, hdr_item)

        self._configure_details_columns(self._grain_table, 1 + n_ds)

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
            pinned_order = 0 if label == "Classif." else 1

            # Column 0: two-line param cell widget
            summary_row = is_text
            label_item = _SortableTableWidgetItem("")
            label_item.setData(Qt.ItemDataRole.UserRole, label.lower())
            label_item.setData(_SORT_GROUP_ROLE, 1 if summary_row else 0)
            if summary_row:
                label_item.setData(_SORT_PINNED_ORDER_ROLE, pinned_order)
            self._grain_table.setItem(row_i, 0, label_item)
            self._grain_table.setCellWidget(
                row_i,
                0,
                self._make_param_cell(label, tooltip, olive, summary=summary_row),
            )
            self._grain_table.setRowHeight(
                row_i,
                _DETAILS_SUMMARY_ROW_HEIGHT if summary_row else _DETAILS_ROW_HEIGHT,
            )

            if is_text:
                if label == "Classif.":
                    for col_i, tab in enumerate(tabs):
                        val_str = (
                            tab.get_dataset().classify(scheme=self._active_scheme).label
                            or "—"
                        )
                        color = dataset_colors[col_i]
                        item = _SortableTableWidgetItem(val_str)
                        item.setData(Qt.ItemDataRole.UserRole, val_str.lower())
                        item.setData(_SORT_GROUP_ROLE, 1)
                        item.setData(_SORT_PINNED_ORDER_ROLE, pinned_order)
                        item.setForeground(QBrush(QColor(color)))
                        item.setFont(QFont(F.MONO, F.SZ_SM))
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                        self._grain_table.setItem(row_i, 1 + col_i, item)
                        self._grain_table.setCellWidget(
                            row_i,
                            1 + col_i,
                            self._make_value_cell(
                                val_str, color, C.BG_LOW, summary=True
                            ),
                        )
                elif label == "Class":
                    for col_i, tab in enumerate(tabs):
                        val_str = self._gradation_class(tab.get_dataset())
                        color = dataset_colors[col_i]
                        item = _SortableTableWidgetItem(val_str)
                        item.setData(Qt.ItemDataRole.UserRole, val_str.lower())
                        item.setData(_SORT_GROUP_ROLE, 1)
                        item.setData(_SORT_PINNED_ORDER_ROLE, pinned_order)
                        item.setForeground(QBrush(QColor(color)))
                        item.setFont(QFont(F.MONO, F.SZ_SM))
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                        self._grain_table.setItem(row_i, 1 + col_i, item)
                        self._grain_table.setCellWidget(
                            row_i,
                            1 + col_i,
                            self._make_value_cell(
                                val_str, color, C.BG_LOW, summary=True
                            ),
                        )
                continue

            # Numeric row — heat range
            valid_vals = [v for v in vals if v is not None]
            v_min = min(valid_vals) if valid_vals else 0.0
            v_max = max(valid_vals) if valid_vals else 1.0
            v_range = v_max - v_min if v_max != v_min else 1.0

            for col_i, val in enumerate(vals):
                color = dataset_colors[col_i]
                if val is None:
                    item = _SortableTableWidgetItem("—")
                    item.setData(Qt.ItemDataRole.UserRole, float("inf"))
                    item.setData(_SORT_GROUP_ROLE, 0)
                    item.setForeground(QBrush(QColor(C.TEXT_MUTED)))
                else:
                    item = _SortableTableWidgetItem(f"{val:.4g}")
                    item.setData(Qt.ItemDataRole.UserRole, float(val))
                    item.setData(_SORT_GROUP_ROLE, 0)
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
                bg = item.data(Qt.ItemDataRole.BackgroundRole)
                bg_color = bg.name() if isinstance(bg, QColor) else C.BG
                self._grain_table.setCellWidget(
                    row_i,
                    1 + col_i,
                    self._make_value_cell(
                        item.text(),
                        color if val is not None else C.TEXT_MUTED,
                        bg_color,
                    ),
                )

        self._grain_table.resizeColumnsToContents()
        self._configure_details_columns(self._grain_table, 1 + n_ds)
        self._apply_grain_row_preset()
        self._grain_table.setSortingEnabled(True)

    # ── Hydraulic conductivity table ──────────────────────────────────────────

    # ── K-value descriptions (method name → short description) ───────────────
    _K_DESCS: dict = {
        "Hazen": "based on D10",
        "Kozeny-Carman": "pore structure",
        "USBR": "Bureau of Reclamation",
        "Terzaghi": "sandy soils",
        "Slichter": "uniform sands",
        "Beyer": "non-uniform sands",
        "Seelheim": "D10 based",
        "Pavchich": "coarse sands",
    }

    def _refresh_k_table(self) -> None:
        """Rebuild the hydraulic conductivity comparison table."""
        tabs = self.selected_datasets
        n_ds = len(tabs)
        dataset_colors = self._dataset_colors_for_tabs(tabs)
        self._k_table.setSortingEnabled(False)
        snapshot = self._build_comparison_snapshot()
        aggregation = snapshot.k

        # Collect all results per dataset
        results_by_tab = [tab.get_results() for tab in tabs]

        method_names: list[str] = list(aggregation.method_names)

        # Summary rows appended at the bottom
        SUMMARY_ROWS = [
            ("K̄ geometric", "All active"),
            ("K̄ arithmetic", "All active"),
            ("K median", "All active"),
            ("K std. dev.", "Spread across methods"),
            ("Perm. class", "Classification"),
        ]

        n_method = len(method_names)
        n_rows = n_method + len(SUMMARY_ROWS)

        self._k_table.setRowCount(n_rows)
        self._k_table.setColumnCount(1 + n_ds)

        # ── Column headers ────────────────────────────────────────────────────
        self._k_table.setHorizontalHeaderItem(0, QTableWidgetItem("Method"))
        for col_i, tab in enumerate(tabs):
            name = tab.get_dataset_name()
            color = dataset_colors[col_i]
            hdr_item = self._make_dataset_header_item(name, color)
            self._k_table.setHorizontalHeaderItem(1 + col_i, hdr_item)

        self._configure_details_columns(self._k_table, 1 + n_ds)

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
            method_item = _SortableTableWidgetItem("")
            method_item.setData(Qt.ItemDataRole.UserRole, method.lower())
            method_item.setData(_SORT_GROUP_ROLE, 0)
            self._k_table.setItem(row_i, 0, method_item)
            self._k_table.setCellWidget(
                row_i, 0, self._make_param_cell(method, desc, olive=False)
            )
            self._k_table.setRowHeight(row_i, _DETAILS_ROW_HEIGHT)

            # Heat range (log scale across row)
            if valid_vals:
                log_vals = [math.log10(v) for v in valid_vals]
                v_min = min(log_vals)
                v_max = max(log_vals)
                v_range = v_max - v_min if v_max != v_min else 1.0
            else:
                v_min = v_max = v_range = 0.0

            for col_i, val in enumerate(vals):
                color = dataset_colors[col_i]
                if val is None or val <= 0:
                    item = _SortableTableWidgetItem("—")
                    item.setData(Qt.ItemDataRole.UserRole, float("inf"))
                    item.setData(_SORT_GROUP_ROLE, 0)
                    item.setForeground(QBrush(QColor(C.TEXT_MUTED)))
                else:
                    item = _SortableTableWidgetItem(self._format_k_value(val))
                    item.setData(Qt.ItemDataRole.UserRole, float(val))
                    item.setData(_SORT_GROUP_ROLE, 0)
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
                bg = item.data(Qt.ItemDataRole.BackgroundRole)
                bg_color = bg.name() if isinstance(bg, QColor) else C.BG
                text_color = color if val is not None and val > 0 else C.TEXT_MUTED
                self._k_table.setCellWidget(
                    row_i,
                    1 + col_i,
                    self._make_value_cell(item.text(), text_color, bg_color),
                )

        # ── Build per-dataset valid K lists ───────────────────────────────────
        dataset_k_stats = [
            aggregation.by_dataset.get(tab.get_dataset_name())
            for tab in tabs
        ]

        # ── Summary rows ──────────────────────────────────────────────────────
        summary_bg = QColor(C.BG_LOW)
        summary_bg.setAlpha(200)

        for si, (s_label, s_desc) in enumerate(SUMMARY_ROWS):
            row_i = n_method + si
            self._k_table.setRowHeight(row_i, _DETAILS_SUMMARY_ROW_HEIGHT)

            is_geom = s_label == "K̄ geometric"
            detail = (
                s_desc
                if s_label == "Perm. class"
                else f"{s_desc} · {self._details_unit_symbol()}"
            )
            # Two-line summary label, olive-highlighted for K̄ geometric
            summary_item = _SortableTableWidgetItem("")
            summary_item.setData(Qt.ItemDataRole.UserRole, s_label.lower())
            summary_item.setData(_SORT_GROUP_ROLE, 1)
            summary_item.setData(_SORT_PINNED_ORDER_ROLE, si)
            self._k_table.setItem(row_i, 0, summary_item)
            self._k_table.setCellWidget(
                row_i,
                0,
                self._make_param_cell(s_label, detail, olive=is_geom, summary=True),
            )

            for col_i, stats in enumerate(dataset_k_stats):
                color = dataset_colors[col_i]
                if "geometric" in s_label:
                    value = getattr(stats, "geometric_mean_m_s", None)
                elif "arithmetic" in s_label:
                    value = getattr(stats, "arithmetic_mean_m_s", None)
                elif s_label == "K median":
                    value = getattr(stats, "median_m_s", None)
                elif s_label == "K std. dev.":
                    value = getattr(stats, "std_dev_m_s", None)
                elif s_label == "Perm. class":
                    value = getattr(stats, "geometric_mean_m_s", None)
                else:
                    value = None
                if s_label == "K̄ geometric":
                    txt = self._format_k_value(value) if value is not None else "—"
                elif s_label == "K̄ arithmetic":
                    txt = self._format_k_value(value) if value is not None else "—"
                elif s_label == "K median":
                    txt = self._format_k_value(value) if value is not None else "—"
                elif s_label == "K std. dev.":
                    txt = self._format_k_value(value) if value is not None else "—"
                elif s_label == "Perm. class":
                    txt = _perm_class(value) if value is not None else "—"
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
                    cell.setData(_SORT_GROUP_ROLE, 1)
                    cell.setData(_SORT_PINNED_ORDER_ROLE, si)
                elif value is not None:
                    sort_val = float(value)
                    cell.setData(Qt.ItemDataRole.UserRole, sort_val)
                    cell.setData(_SORT_GROUP_ROLE, 1)
                    cell.setData(_SORT_PINNED_ORDER_ROLE, si)
                else:
                    cell.setData(Qt.ItemDataRole.UserRole, float("inf"))
                    cell.setData(_SORT_GROUP_ROLE, 1)
                    cell.setData(_SORT_PINNED_ORDER_ROLE, si)
                if s_label == "Perm. class" and value is not None:
                    cell.setForeground(
                        QBrush(QColor(_PERM_CLASS_COLOR.get(txt, C.TEXT_MID)))
                    )
                elif is_geom and value is not None:
                    # Bold colored dataset value for K̄ geometric
                    cell.setForeground(QBrush(QColor(color)))
                    bold_f = QFont(F.MONO, F.SZ_SM)
                    bold_f.setBold(True)
                    cell.setFont(bold_f)
                else:
                    cell.setForeground(QBrush(QColor(C.TEXT_MID)))
                self._k_table.setItem(row_i, 1 + col_i, cell)
                if s_label == "Perm. class" and value is not None:
                    text_color = _PERM_CLASS_COLOR.get(txt, C.TEXT_MID)
                    bold_value = False
                elif is_geom and value is not None:
                    text_color = color
                    bold_value = True
                else:
                    text_color = C.TEXT_MID
                    bold_value = False
                self._k_table.setCellWidget(
                    row_i,
                    1 + col_i,
                    self._make_value_cell(
                        cell.text(),
                        text_color,
                        summary_bg.name(),
                        bold=bold_value,
                        summary=True,
                    ),
                )

        self._k_table.resizeColumnsToContents()
        self._configure_details_columns(self._k_table, 1 + n_ds)
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

        if self.selected_datasets and self._stats_uses_group_scope():
            snapshot = self._build_comparison_snapshot()
            groups = list(snapshot.k.group_names)
            group_colors = self._group_color_map(groups)
            members_by_group = self._stats_group_members()
            layout.insertWidget(
                layout.count() - 1,
                self._make_overall_scope_chip(len(self.selected_datasets)),
            )
            for group_name in groups:
                members = members_by_group.get(group_name, [])
                chip = self._make_group_chip(
                    group_name,
                    group_colors.get(group_name, C.TEXT_MID),
                    len(members),
                    members,
                )
                layout.insertWidget(layout.count() - 1, chip)
            return

        dataset_colors = self._dataset_colors_for_tabs(self.selected_datasets)
        for i, tab in enumerate(self.selected_datasets):
            name = tab.get_dataset_name()
            color = dataset_colors[i]
            chip = self._make_dataset_chip(
                name, color, dataset_group_name(tab.get_dataset())
            )
            layout.insertWidget(layout.count() - 1, chip)

    def _build_stats_insights(self) -> list[tuple[str, str]]:
        tabs = self.selected_datasets
        if not tabs:
            return [
                (
                    "No comparison data",
                    "Select at least two datasets to populate comparison statistics.",
                )
            ]

        snapshot = self._build_comparison_snapshot()
        aggregation = snapshot.k
        spread_stats = []
        method_names = list(aggregation.method_names)
        issue_counts = {method: 0 for method in method_names}

        for tab in tabs:
            dataset_name = tab.get_dataset_name()
            vals = [
                record.k_value
                for record in aggregation.included_records
                if record.dataset_name == dataset_name
                and record.k_value is not None
                and record.k_value > 0
            ]
            if len(vals) >= 2:
                spread = math.log10(max(vals)) - math.log10(min(vals))
                spread_stats.append((spread, dataset_name, min(vals), max(vals)))

            result_map = {
                record.method_name: record
                for record in aggregation.records
                if record.dataset_name == dataset_name
            }
            for method in method_names:
                result = result_map.get(method)
                if result is None:
                    issue_counts[method] += 1
                elif not result.included:
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
            caution_method, issue_count = max(
                issue_counts.items(), key=lambda item: item[1]
            )
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
        self._sync_stats_controls()

        metric_label = self._stats_metric_label()
        if not self.selected_datasets:
            self._stats_context.setText("Select at least 2 datasets to compare")
            self._stats_dist_meta.setText("")
            self._stats_agreement_meta.setText("")
            self._set_compact_rail_header(
                self._stats_rail_title,
                self._stats_rail_subtitle,
                self._stats_rail_badge,
                title="Statistics Summary",
                subtitle="No datasets selected",
                badge="0 / 0",
            )
            if hasattr(self, "_stats_group_section"):
                self._stats_group_section.setVisible(False)
            if hasattr(self, "_stats_visible_table_section"):
                self._stats_visible_table_section.setVisible(False)
            if hasattr(self, "_stats_scope_layout"):
                self._reset_layout(self._stats_scope_layout)
            if hasattr(self, "_stats_filter_layout"):
                self._reset_layout(self._stats_filter_layout)
            if hasattr(self, "_stats_group_layout"):
                self._reset_layout(self._stats_group_layout)
            if hasattr(self, "_stats_visible_table_layout"):
                self._reset_layout(self._stats_visible_table_layout)
            self._clear_stats_tables()
            self._reset_layout(self._stats_insights_layout)
            self._stats_insights_layout.addWidget(
                self._make_rail_status_line(
                    "Select at least two datasets to populate comparison statistics.",
                    tone="warn",
                )
            )
            self._reset_layout(self._stats_summary_layout)
            self._add_rail_metric_grid(
                self._stats_summary_layout,
                [
                    ("Selected metric", metric_label),
                    ("Unit", self._stats_unit_symbol()),
                ],
            )
            return

        snapshot = self._build_comparison_snapshot()
        aggregation = snapshot.k
        stats = aggregation.overall
        filter_bits = ["OK + warnings" if self._stats_include_warnings else "OK only"]
        if self._stats_common_methods_only:
            filter_bits.append("valid for every dataset")
        if self._stats_method_scope == "valid_all":
            filter_bits.append("valid in all")
        filter_label = " / ".join(filter_bits)
        method_names = aggregation.method_names
        total_cells = stats.total_cells
        valid_count = stats.included_count
        warning_count = stats.warning_count
        missing_count = stats.missing_count + stats.excluded_count

        self._stats_context.setText(
            f"{len(self.selected_datasets)} datasets - {len(aggregation.group_names)} groups - "
            f"{self._stats_unit_symbol()} - {metric_label} - {filter_label}"
        )
        self._set_compact_rail_header(
            self._stats_rail_title,
            self._stats_rail_subtitle,
            self._stats_rail_badge,
            title="Statistics Summary",
            subtitle=f"{len(self.selected_datasets)} datasets - {len(aggregation.group_names)} groups - {'OK + warnings' if self._stats_include_warnings else 'OK only'}",
            badge=f"{valid_count} / {total_cells}" if total_cells else "0 / 0",
        )
        scope_label = (
            "overall + groups" if self._stats_uses_group_scope() else "datasets"
        )
        self._stats_dist_meta.setText(f"{metric_label} - {scope_label}")
        self._stats_agreement_meta.setText(
            f"{len(method_names)} methods - {scope_label}"
        )
        self._refresh_stats_scope_table(snapshot)
        self._refresh_stats_method_table(snapshot)

        if hasattr(self, "_stats_scope_layout"):
            self._reset_layout(self._stats_scope_layout)
            warnings_excluded = warning_count if not self._stats_include_warnings else 0
            self._stats_scope_layout.addWidget(
                self._make_rail_chip_group(
                    [
                        (f"{len(self.selected_datasets)} datasets", "neutral"),
                        (f"{len(aggregation.group_names)} groups", "neutral"),
                        (f"{len(method_names)} methods", "neutral"),
                        (
                            f"{valid_count} / {total_cells} K cells",
                            "ok" if valid_count else "warn",
                        ),
                        (
                            f"{warnings_excluded} warnings excluded",
                            "warn" if warnings_excluded else "neutral",
                        ),
                    ]
                )
            )

        if hasattr(self, "_stats_filter_layout"):
            self._reset_layout(self._stats_filter_layout)
            method_text = (
                "Valid in all"
                if self._stats_common_methods_only
                or self._stats_method_scope == "valid_all"
                else "All active"
            )
            status_text = "OK + warnings" if self._stats_include_warnings else "OK only"
            self._stats_filter_layout.addWidget(
                self._make_rail_chip_group(
                    [
                        (
                            "Coverage"
                            if self._stats_view_mode == "coverage"
                            else "K spread",
                            "ok",
                        ),
                        (metric_label, "neutral"),
                        (method_text, "neutral"),
                        (
                            status_text,
                            "ok" if not self._stats_include_warnings else "warn",
                        ),
                        (self._stats_unit_symbol(), "neutral"),
                    ]
                )
            )

        self._reset_layout(self._stats_insights_layout)
        k_range = "-"
        if stats.min_m_s is not None and stats.max_m_s is not None:
            k_range = f"{self._format_stats_k_value(stats.min_m_s)} - {self._format_stats_k_value(stats.max_m_s)}"
        geo_text = (
            self._format_stats_k_value(stats.geometric_mean_m_s)
            if stats.geometric_mean_m_s is not None
            else "-"
        )
        self._stats_insights_layout.addWidget(
            self._make_rail_headline(
                "Geometric mean", "overall selected scope", geo_text
            )
        )
        self._add_rail_metric_grid(
            self._stats_insights_layout,
            [
                (
                    "Arithmetic",
                    self._format_stats_k_value(stats.arithmetic_mean_m_s)
                    if stats.arithmetic_mean_m_s is not None
                    else "-",
                ),
                (
                    "Median",
                    self._format_stats_k_value(stats.median_m_s)
                    if stats.median_m_s is not None
                    else "-",
                ),
                ("Range", k_range),
                (
                    "ln(K) std.",
                    f"{stats.ln_std_dev:.2f}" if stats.ln_std_dev is not None else "-",
                ),
            ],
        )
        self._stats_insights_layout.addWidget(
            self._make_rail_status_line(
                "Moderate K heterogeneity for the active scope"
                if stats.ln_std_dev is not None and stats.ln_std_dev < 1
                else "High K heterogeneity in the active scope",
                tone="ok"
                if stats.ln_std_dev is not None and stats.ln_std_dev < 1
                else "warn",
            )
        )

        self._reset_layout(self._stats_summary_layout)
        coverage_pct = (
            int(round((valid_count / total_cells) * 100)) if total_cells else 0
        )
        self._stats_summary_layout.addWidget(
            self._make_rail_headline(
                "Included K cells",
                "after method and status filters",
                f"{coverage_pct}%",
            )
        )
        self._add_rail_metric_grid(
            self._stats_summary_layout,
            [
                ("Methods available", str(len(method_names))),
                ("Valid in all", str(len(aggregation.complete_methods))),
                (
                    "Values included",
                    f"{valid_count} / {total_cells}" if total_cells else "0",
                ),
                ("With warnings", str(warning_count)),
                ("Excluded cells", str(stats.excluded_count)),
                ("Missing cells", str(stats.missing_count)),
            ],
        )

        show_group_breakdown = len(aggregation.group_names) > 1 or any(
            group != UNGROUPED_LABEL for group in aggregation.group_names
        )
        if hasattr(self, "_stats_group_layout"):
            self._reset_layout(self._stats_group_layout)
        if hasattr(self, "_stats_group_section"):
            self._stats_group_section.setVisible(show_group_breakdown)
        if show_group_breakdown and hasattr(self, "_stats_group_layout"):
            grain = snapshot.grain
            group_colors = self._group_color_map(list(aggregation.group_names))
            for group_name in aggregation.group_names:
                group_stats = aggregation.by_group.get(group_name)
                grain_stats = grain.by_group.get(group_name)
                metric_value = (
                    self._stats_metric_value(group_stats)
                    if group_stats is not None
                    else None
                )
                k_text = (
                    self._format_stats_k_value(metric_value)
                    if metric_value is not None
                    else "-"
                )
                d50_text = "-"
                dataset_count = 0
                if grain_stats is not None:
                    dataset_count = grain_stats.dataset_count
                    d50_metric = grain_stats.metrics.get("D50")
                    if d50_metric is not None and d50_metric.median is not None:
                        d50_text = f"{d50_metric.median:.3g} mm"
                included_text = "0 / 0"
                if group_stats is not None:
                    included_text = (
                        f"{group_stats.included_count} / {group_stats.total_cells}"
                    )
                self._stats_group_layout.addWidget(
                    self._make_rail_group_row(
                        group_name,
                        f"{dataset_count} datasets - {included_text} K cells",
                        f"K {k_text}\nD50 {d50_text}",
                        group_colors.get(group_name, C.TEXT_MID),
                    )
                )

        if hasattr(self, "_stats_visible_table_layout"):
            self._reset_layout(self._stats_visible_table_layout)
            active_rows = (
                self._stats_method_table.rowCount()
                if self._stats_view_mode == "coverage"
                else self._stats_scope_table.rowCount()
            )
            active_cols = (
                self._stats_method_table.columnCount()
                if self._stats_view_mode == "coverage"
                else self._stats_scope_table.columnCount()
            )
            self._add_rail_metric_grid(
                self._stats_visible_table_layout,
                [
                    ("Rows", str(active_rows)),
                    ("Columns", str(active_cols)),
                    ("Export", "visible table"),
                    ("Plot", "PNG/SVG"),
                ],
            )
            self._stats_visible_table_section.setVisible(True)

    def _refresh_stats(self) -> None:
        """Redraw both matplotlib statistics figures."""
        self._refresh_stats_workspace()
        self._draw_boxplot()
        self._draw_heatmap()

    def _draw_boxplot(self) -> None:
        """K-value box plots — one box per dataset, log y-axis."""
        foreground = "#000000"
        self._box_fig.clear()
        ax = self._box_fig.add_subplot(111)
        ax.set_facecolor("#ffffff")

        tabs = self.selected_datasets
        aggregation = self._build_k_aggregation()
        data_per_ds = []
        labels = []
        colors = []

        if self._stats_uses_group_scope():
            groups = list(aggregation.group_names)
            group_colors = self._group_color_map(groups)
            scope_defs = [("Overall", None, C.EARTH)] + [
                (group_name, group_name, group_colors.get(group_name, C.TEXT_MID))
                for group_name in groups
            ]
            for label, group_name, color in scope_defs:
                vals_m_s = [
                    record.k_value
                    for record in aggregation.included_records
                    if record.k_value is not None
                    and record.k_value > 0
                    and (group_name is None or record.group_name == group_name)
                ]
                vals = [
                    HydraulicConductivityConverter.convert_from_m_per_s(
                        v, self._stats_k_unit
                    )
                    for v in vals_m_s
                ]
                data_per_ds.append(vals)
                labels.append(self._short_dataset_name(label, max_width=88))
                colors.append(color)
        else:
            dataset_colors = self._dataset_colors_for_tabs(tabs)
            for i, tab in enumerate(tabs):
                dataset_name = tab.get_dataset_name()
                vals_m_s = [
                    record.k_value
                    for record in aggregation.included_records
                    if record.dataset_name == dataset_name
                    and record.k_value is not None
                    and record.k_value > 0
                ]
                vals = [
                    HydraulicConductivityConverter.convert_from_m_per_s(
                        v, self._stats_k_unit
                    )
                    for v in vals_m_s
                ]
                data_per_ds.append(vals)
                labels.append(self._short_dataset_name(dataset_name, max_width=88))
                colors.append(dataset_colors[i])

        if not any(data_per_ds):
            ax.text(
                0.5,
                0.5,
                "No K data available",
                ha="center",
                va="center",
                transform=ax.transAxes,
                color=foreground,
                fontsize=11,
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
            medianprops={"color": foreground, "linewidth": 1.5},
            whiskerprops={"color": foreground, "linewidth": 1.0},
            capprops={"color": foreground, "linewidth": 1.0},
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
            if self._stats_metric == "arithmetic":
                marker_values.append(float(np.mean(vals)))
            elif self._stats_metric == "median":
                marker_values.append(float(np.median(vals)))
            else:
                marker_values.append(float(np.exp(np.mean(np.log(vals)))))
        x_positions = list(range(1, len(p_data) + 1))
        ax.scatter(
            x_positions,
            marker_values,
            marker="D",
            s=34,
            color=foreground,
            edgecolors="white",
            linewidths=0.8,
            zorder=4,
        )

        ax.set_yscale("log")
        ax.set_ylabel(f"K ({self._stats_unit_symbol()})", color=foreground, fontsize=10)
        ax.set_title(
            "K-value Distribution by Group"
            if self._stats_uses_group_scope()
            else "K-value Distribution by Dataset",
            color=foreground,
            fontsize=11,
            fontweight="600",
        )
        many_scopes = len(p_labels) > 6
        ax.tick_params(
            axis="x",
            labelrotation=18 if many_scopes else 0,
            labelsize=7 if many_scopes else 8,
            colors=foreground,
        )
        ax.tick_params(axis="y", labelsize=8, colors=foreground)
        for idx, tick_lbl in enumerate(ax.get_xticklabels()):
            tick_lbl.set_color(foreground)
            tick_lbl.set_ha("right" if many_scopes else "center")
        ax.grid(True, which="both", linestyle="--", alpha=0.18, color=foreground)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(foreground)
        ax.spines["bottom"].set_color(foreground)
        ax.text(
            0.99,
            0.98,
            f"Marker: {self._stats_metric_label()}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color=foreground,
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
        foreground = "#000000"
        self._heat_fig.clear()
        ax = self._heat_fig.add_subplot(111)
        ax.set_facecolor("#ffffff")

        tabs = self.selected_datasets
        aggregation = self._build_k_aggregation()
        method_names = list(aggregation.method_names)
        use_group_scope = self._stats_uses_group_scope()
        if use_group_scope:
            groups = list(aggregation.group_names)
            members_by_group = self._stats_group_members()
            scope_names = ["Overall", *groups]
            scope_dataset_counts = [
                len(tabs),
                *[len(members_by_group.get(group, [])) for group in groups],
            ]
        else:
            scope_names = [
                self._short_dataset_name(tab.get_dataset_name(), max_width=84)
                for tab in tabs
            ]
            scope_dataset_counts = [1 for _tab in tabs]

        if not method_names or not scope_names:
            ax.text(
                0.5,
                0.5,
                "No method data available",
                ha="center",
                va="center",
                transform=ax.transAxes,
                color=foreground,
            )
            self._heat_canvas.draw()
            return

        # Build status matrix: 2=OK, 1=WARNING, 0=N/A
        matrix = np.zeros((len(method_names), len(scope_names)))
        overlay_text = [["" for _ in scope_names] for _ in method_names]
        records_by_cell = {
            (record.dataset_name, record.method_name): record
            for record in aggregation.records
        }
        if use_group_scope:
            records_by_method = {
                method: [
                    record
                    for record in aggregation.records
                    if record.method_name == method
                ]
                for method in method_names
            }
            for ci, scope_name in enumerate(scope_names):
                dataset_count = scope_dataset_counts[ci]
                for ri, method in enumerate(method_names):
                    method_records = records_by_method.get(method, [])
                    if scope_name != "Overall":
                        method_records = [
                            record
                            for record in method_records
                            if record.group_name == scope_name
                        ]
                    included = sum(1 for record in method_records if record.included)
                    warnings = sum(
                        1 for record in method_records if record.status == "Warning"
                    )
                    if dataset_count and included == dataset_count and warnings == 0:
                        matrix[ri, ci] = 2.0
                    elif included > 0 or warnings > 0:
                        matrix[ri, ci] = 1.0
                    overlay_text[ri][ci] = (
                        f"{included}/{dataset_count}" if dataset_count else "-"
                    )
        else:
            for ci, tab in enumerate(tabs):
                dataset_name = tab.get_dataset_name()
                for ri, method in enumerate(method_names):
                    record = records_by_cell.get((dataset_name, method))
                    if record is None:
                        continue
                    if record.included and record.status == "OK":
                        matrix[ri, ci] = 2.0
                    elif record.status == "Warning":
                        matrix[ri, ci] = 1.0
                    # ERROR/excluded OK stays 0.0

        def _hex_to_rgba(hex_color: str, alpha: float) -> tuple:
            qc = QColor(hex_color)
            return (qc.red() / 255, qc.green() / 255, qc.blue() / 255, alpha)

        ok_rgba = _hex_to_rgba("#dbe8c0", 1.0)
        warn_rgba = _hex_to_rgba("#d99a3a", 1.0)
        absent_rgba = _hex_to_rgba("#ece5da", 1.0)

        cmap_data = np.zeros((*matrix.shape, 4))
        for ri in range(len(method_names)):
            for ci in range(len(scope_names)):
                v = matrix[ri, ci]
                if v >= 2.0:
                    cmap_data[ri, ci] = ok_rgba
                elif v >= 1.0:
                    cmap_data[ri, ci] = warn_rgba
                else:
                    cmap_data[ri, ci] = absent_rgba

        ax.imshow(cmap_data, aspect="auto", interpolation="nearest", origin="upper")

        ax.set_xticks(range(len(scope_names)))
        ax.set_xticklabels(scope_names, rotation=18, ha="right", fontsize=8)
        ax.set_yticks(range(len(method_names)))
        ax.set_yticklabels(method_names, fontsize=8)
        ax.set_title(
            "Method Coverage by Group"
            if use_group_scope
            else "Method Agreement & Applicability",
            color=foreground,
            fontsize=11,
            fontweight="600",
            pad=28,
        )
        legend = ax.legend(
            handles=[
                Patch(facecolor="#dbe8c0", edgecolor=foreground, label="Included"),
                Patch(facecolor="#d99a3a", edgecolor=foreground, label="Warning"),
                Patch(facecolor="#ece5da", edgecolor=foreground, label="Unavailable"),
            ],
            loc="upper center",
            bbox_to_anchor=(0.5, 1.10),
            ncol=3,
            frameon=False,
            fontsize=8,
            handlelength=1.1,
            columnspacing=1.3,
            borderaxespad=0,
        )
        for text in legend.get_texts():
            text.set_color(foreground)

        # Add crisp cell separators so the matrix reads as a table, not a color slab.
        ax.set_xticks(np.arange(-0.5, len(scope_names), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(method_names), 1), minor=True)
        ax.grid(which="minor", color=foreground, alpha=0.12, linestyle="-", linewidth=1.0)
        ax.tick_params(which="minor", bottom=False, left=False)

        # Overlay compact coverage counts for grouped scopes; per-dataset cells stay icon-like.
        for ri in range(len(method_names)):
            for ci in range(len(scope_names)):
                v = matrix[ri, ci]
                if use_group_scope:
                    ax.text(
                        ci,
                        ri,
                        overlay_text[ri][ci],
                        ha="center",
                        va="center",
                        fontsize=7,
                        fontweight="700",
                        color=foreground,
                    )
                    continue
                if v >= 2.0:
                    continue
                if v >= 1.0:
                    ax.text(
                        ci,
                        ri,
                        "!",
                        ha="center",
                        va="center",
                        fontsize=9,
                        fontweight="700",
                        color=foreground,
                    )
                else:
                    ax.text(
                        ci,
                        ri,
                        "—",
                        ha="center",
                        va="center",
                        fontsize=9,
                        color=foreground,
                    )

        for tick_lbl in ax.get_xticklabels():
            tick_lbl.set_color(foreground)
        for tick_lbl in ax.get_yticklabels():
            tick_lbl.set_color(foreground)

        ax.spines[:].set_visible(False)
        ax.tick_params(length=0, colors=foreground)
        ax.tick_params(axis="x", pad=6)
        ax.tick_params(axis="y", pad=4)

        self._heat_canvas.draw()

    # ── Export ────────────────────────────────────────────────────────────────

    @staticmethod
    def _ensure_export_extension(
        path: str,
        selected_filter: str,
        allowed: tuple[str, ...],
        default: str,
    ) -> tuple[str, str]:
        extension = os.path.splitext(path)[1].lower().lstrip('.')
        if extension not in allowed:
            extension = next(
                (candidate for candidate in allowed
                 if candidate.upper() in selected_filter.upper()),
                default,
            )
            path = f'{path}.{extension}'
        return path, extension

    @staticmethod
    def _table_widget_text(widget: QWidget | None) -> str:
        if widget is None:
            return ''
        labels = [
            label.text().strip()
            for label in widget.findChildren(QLabel)
            if label.text().strip()
        ]
        return labels[0] if labels else ''

    def _visible_table_model(self, table: QTableWidget, name: str) -> ExportTable:
        columns = [
            column for column in range(table.columnCount())
            if not table.isColumnHidden(column)
        ]
        headers = []
        for column in columns:
            item = table.horizontalHeaderItem(column)
            if item is None:
                headers.append(f'Column {column + 1}')
            else:
                headers.append(item.toolTip().strip() or item.text().strip())

        rows = []
        for row in range(table.rowCount()):
            if table.isRowHidden(row):
                continue
            values = []
            for column in columns:
                item = table.item(row, column)
                text = item.text().strip() if item is not None else ''
                if not text:
                    text = self._table_widget_text(table.cellWidget(row, column))
                values.append(text)
            rows.append(values)
        return ExportTable.from_rows(name, headers, rows)

    def _export_table_model(self, table: ExportTable, default_name: str) -> None:
        export_table_dialog(
            self,
            dialog_title="Export Comparison Table",
            default_stem=default_name,
            table=table,
            success_label="Comparison table",
            file_dialog=QFileDialog,
            message_box=QMessageBox,
        )

    def _export_details(self) -> None:
        table = self._details_stack.currentWidget()
        if not isinstance(table, QTableWidget):
            return
        if self._details_view_mode == 'aggregate':
            stem = 'comparison_details_aggregate'
            table_name = 'Details Aggregate'
        elif self._details_mode == 'k':
            stem = 'comparison_details_k_values'
            table_name = 'Details K Values'
        else:
            stem = 'comparison_details_grain'
            table_name = 'Details Grain'
        self._export_table_model(
            self._visible_table_model(table, table_name),
            stem,
        )

    def _export_statistics(self) -> None:
        if self._stats_view_mode == 'coverage':
            table = self._stats_method_table
            stem = 'comparison_statistics_methods'
            table_name = 'Method Statistics'
        else:
            table = self._stats_scope_table
            stem = 'comparison_statistics_scopes'
            table_name = 'Scope Statistics'
        self._export_table_model(
            self._visible_table_model(table, table_name),
            stem,
        )

    def _export_plot(self) -> None:
        """Save the comparison plot as a raster or vector figure."""
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Comparison Plot",
            "comparison.png",
            "PNG Image (*.png);;SVG Vector (*.svg);;PDF Figure (*.pdf)",
        )
        if not path:
            return
        path, extension = self._ensure_export_extension(
            path,
            selected_filter,
            ('png', 'svg', 'pdf'),
            'png',
        )
        try:
            if hasattr(self._plot_widget, "figure"):
                self._plot_widget.figure.savefig(
                    path,
                    format=extension,
                    dpi=300,
                    bbox_inches="tight",
                    facecolor="white",
                    edgecolor="white",
                    transparent=False,
                )
            elif hasattr(self._plot_widget, "_fig"):
                self._plot_widget._fig.savefig(
                    path,
                    format=extension,
                    dpi=300,
                    bbox_inches="tight",
                    facecolor="white",
                    edgecolor="white",
                    transparent=False,
                )
            elif hasattr(self._plot_widget, "canvas") and hasattr(
                self._plot_widget.canvas, "figure"
            ):
                self._plot_widget.canvas.figure.savefig(
                    path,
                    format=extension,
                    dpi=300,
                    bbox_inches="tight",
                    facecolor="white",
                    edgecolor="white",
                    transparent=False,
                )
            QMessageBox.information(
                self,
                'Export Successful',
                f'Comparison plot exported to:\n{path}',
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Export Failed",
                f"Could not save plot:\n{exc}",
            )

    def export_comparison(self) -> None:
        """Public alias kept for main_window.py compatibility."""
        self._export_plot()
