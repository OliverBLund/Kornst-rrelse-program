"""
Enhanced plot widget for comparison tab with multiple display modes
"""

import dataclasses
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton,
    QComboBox, QLabel, QButtonGroup, QSizePolicy, QScrollArea,
    QColorDialog, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFontMetrics
from matplotlib.figure import Figure
from matplotlib.patches import Patch
import numpy as np
from typing import List, Dict, Optional
from .collapsible_section import CollapsibleSection
from .k_plot_helpers import apply_linear_bar_limits, apply_log_bar_limits, format_method_label
from .matplotlib_canvas import FigureCanvas
from .plot_interactions import AxesInteractionController
from .plot_constants import METHOD_COLORS, DATASET_COLORS, DEFAULT_METHOD_ORDER, ordered_methods
from .plot_renderers import (
    apply_legend_aware_layout,
    build_legend_kwargs,
    render_distribution_groups,
    render_distribution_overlay,
    render_k_distribution_function,
    render_k_histogram,
    render_k_overlay,
    _style_k_bar_simple,
    _add_flagged_legend_handle,
)
from .plot_styles import PlotStyle, PROFESSIONAL_STYLE, get_style, get_available_style_names
from .sidebar_controls import (
    LEGEND_LOCATIONS as _CMP_LEGEND_LOCATIONS,
    LEGEND_LAYOUTS as _CMP_LEGEND_LAYOUTS,
    LineStylePreview,
    make_color_row, make_combo_row, make_dspin_row,
    make_spin_row, make_toggle_row, set_swatch_color,
)
from .group_styles import (
    LINE_STYLE_OPTIONS,
    dataset_line_style,
    dataset_series_key,
    group_color_map,
    line_style_label,
    series_style_parts,
    set_dataset_line_style,
    set_group_color,
)
from .theme import C, SZ, apply_matplotlib_style, icon
from analysis.comparison_snapshot import ComparisonSnapshotOptions, build_comparison_snapshot
from k_aggregation import KAggregationOptions, UNGROUPED_LABEL, dataset_group_name
from unit_conversions import HydraulicConductivityConverter, HydraulicConductivityUnit, get_default_plot_unit


def _cmp_sep() -> QFrame:
    """Vertical separator matching the plot workspace toolbar language."""
    sep = QFrame()
    sep.setObjectName("pw-sep")
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFixedSize(1, 16)
    return sep


def _cmp_btn(text: str = "", tooltip: str = "", icon_name: str = "") -> QPushButton:
    """Small comparison-toolbar action button."""
    btn = QPushButton(text)
    btn.setProperty("pw-btn", True)
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_name:
        btn.setIcon(icon(icon_name, C.TEXT_MID))
        btn.setIconSize(QSize(12, 12))
    return btn


def _cmp_chk(text: str, tooltip: str = "", checked: bool = False, icon_name: str = "") -> QPushButton:
    """Toggle button styled through the shared plot toolbar rules."""
    btn = QPushButton(text)
    btn.setProperty("pw-chk", True)
    btn.setProperty("active", checked)
    btn.setCheckable(True)
    btn.setChecked(checked)
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_name:
        btn._cmp_icon_name = icon_name
        btn.setIcon(icon(icon_name, C.OLIVE if checked else C.TEXT_MID))
        btn.setIconSize(QSize(12, 12))
    btn.toggled.connect(lambda on, b=btn: _sync_cmp_chk(b, on))
    return btn


def _sync_cmp_chk(btn: QPushButton, on: bool) -> None:
    btn.setProperty("active", on)
    btn.style().unpolish(btn)
    btn.style().polish(btn)
    icon_name = getattr(btn, "_cmp_icon_name", None)
    if icon_name:
        btn.setIcon(icon(icon_name, C.OLIVE if on else C.TEXT_MID))


def _sync_cmp_seg(btn: QPushButton, on: bool) -> None:
    btn.setProperty("active", on)
    btn.style().unpolish(btn)
    btn.style().polish(btn)


class ComparisonPlotWidget(QWidget):
    """
    Enhanced plot widget for comparing multiple datasets with various display modes
    """
    
    # Signals
    plot_updated = pyqtSignal()
    DEFAULT_METHOD_ORDER = DEFAULT_METHOD_ORDER  # from plot_constants
    # Soft cap on faceted subplots; beyond this we surface an overflow note
    # rather than silently dropping datasets/groups.
    MAX_FACET_PANELS = 16
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Plot settings
        self.current_plot_type = "distribution"
        self.display_mode = "overlay"  # overlay, grid, grouped
        # Render-only breakdown: "dataset" vs "group". Defaults to "group" when
        # the loaded datasets carry named groups (set in set_datasets). Group
        # membership itself is owned by the Scope & Groups dialog, not here.
        self.breakdown = "dataset"
        # K Distribution sub-view: "cdf" (empirical CDF + lognormal fit) or
        # "histogram" (Poul's lognormal PDF). Histogram x-axis: "k" or "lnk".
        # Histogram bins: "auto" / "off" / a digit string ("5".."30").
        self.k_dist_view = "cdf"
        self.k_hist_axis = "lnk"
        self.k_hist_bins = "auto"
        self.grid_layout = (2, 2)  # Default grid size
        self.show_grid = True
        self.show_legend = True
        self.sidebar_visible = False
        self.display_unit: HydraulicConductivityUnit = get_default_plot_unit()
        self.log_k_y_scale = False

        # Active style — swapped by set_style(). Starts at the Professional preset
        # so the comparison view now honors the preset selector (previously it was
        # hardcoded to PROFESSIONAL_STYLE at every render call).
        self.current_style: PlotStyle = PROFESSIONAL_STYLE
        self._style_is_custom: bool = False

        # Data storage
        self.datasets = []
        self.k_results_dict = {}  # dataset_name -> k_results
        self.flagged_methods_dict = {}  # dataset_name -> set(method_name)
        self._comparison_snapshot = None
        self._dataset_groups: Dict[str, str] = {}
        self._dataset_style_keys: Dict[str, str] = {}
        self._group_color_map: Dict[str, str] = {}
        self._dataset_linestyles: Dict[str, str] = {}
        # First-seen order of groups/datasets, accumulated across set_datasets so
        # colors stay stable when datasets are hidden/re-shown (only reset when
        # the comparison scope itself changes).
        self._known_group_order: list[str] = []
        self._known_dataset_order: list[str] = []
        self._known_dataset_group: Dict[str, str] = {}
        # True once the user picks a Breakdown explicitly — stops set_datasets
        # from re-defaulting it on every visibility toggle.
        self._breakdown_explicit = False
        self.drawer_visible = False
        self._drawer_headers: list[str] = []
        self._drawer_rows: list[tuple] = []
        self._drawer_title_text = "Plot data"
        self.current_ax = None
        self._default_limits = {}
        self._pan_state = None

        # Shared color schemes from plot_constants
        self.dataset_colors = DATASET_COLORS
        self.method_colors = METHOD_COLORS

        self.init_ui()

    def set_style(self, style: PlotStyle) -> None:
        """Swap the active PlotStyle and re-render."""
        self.current_style = style
        if hasattr(self, "figure"):
            self.figure.patch.set_facecolor(style.figure_facecolor)
        self._sync_sidebar_style_widgets(style)
        self._sync_reset_button()
        self.refresh_plot()

    def init_ui(self):
        """Initialize the UI"""
        apply_matplotlib_style()

        # Per-dataset color overrides (sample_name -> hex). None = use default.
        self._dataset_color_overrides: Dict[str, str] = {}
        # Live handles to the color swatch widgets, keyed by sample name.
        self._dataset_color_rows: Dict[str, QLabel] = {}
        # Live handles to group color swatches, keyed by group name.
        self._group_color_rows: Dict[str, QLabel] = {}
        self._dataset_line_style_rows: Dict[str, QComboBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Toolbar row (plot type, view mode, zoom, style preset).
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)

        # Body row: collapsible sidebar + canvas side-by-side.
        body = QWidget()
        body_row = QHBoxLayout(body)
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.setSpacing(0)

        self._sidebar = self._build_sidebar()
        self._sidebar.setMaximumWidth(0)
        body_row.addWidget(self._sidebar)

        self._chart_area = QWidget()
        chart_lay = QVBoxLayout(self._chart_area)
        chart_lay.setContentsMargins(10, 0, 0, 0)
        chart_lay.setSpacing(0)

        # Create matplotlib figure and canvas.
        self.figure = Figure(figsize=(12, 8))
        self.figure.patch.set_facecolor(C.BG)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background: transparent;")
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._interactions = AxesInteractionController(
            figure=self.figure,
            canvas=self.canvas,
            get_current_ax=lambda: self.current_ax,
            set_current_ax=lambda ax: setattr(self, "current_ax", ax),
            get_active_axes=lambda: list(self.figure.axes),
        )
        self.canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self.canvas.mpl_connect("scroll_event", self._on_canvas_scroll)
        self.canvas.mpl_connect("motion_notify_event", self._on_canvas_motion)
        self.canvas.mpl_connect("button_release_event", self._on_canvas_release)
        self.canvas.setMinimumHeight(220)
        chart_lay.addWidget(self.canvas, 1)

        self._drawer = self._build_data_drawer()
        chart_lay.addWidget(self._drawer, 0)

        self._toggle_handle = QPushButton(self._chart_area)
        self._toggle_handle.setObjectName("pw-toggle-handle")
        self._toggle_handle.setIcon(icon("fa6s.chevron-right", C.TEXT_MID, 8))
        self._toggle_handle.setIconSize(QSize(8, 8))
        self._toggle_handle.setToolTip("Toggle sidebar")
        self._toggle_handle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_handle.clicked.connect(self._toggle_sidebar)
        self._toggle_handle.raise_()

        body_row.addWidget(self._chart_area, 1)

        self._sidebar_anim = QPropertyAnimation(self._sidebar, b"maximumWidth")
        self._sidebar_anim.setDuration(200)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._sidebar_anim.valueChanged.connect(self._on_sidebar_width_changed)

        self._drawer_anim = QPropertyAnimation(self._drawer, b"maximumHeight")
        self._drawer_anim.setDuration(180)
        self._drawer_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        layout.addWidget(body, 1)

        # Seed sidebar style widgets with the initial preset's values.
        self._sync_sidebar_style_widgets(self.current_style)

    def _build_data_drawer(self) -> QFrame:
        """Collapsible table drawer for the data behind the active plot."""
        drawer = QFrame()
        drawer.setObjectName("cmp-data-drawer")
        drawer.setMaximumHeight(32)
        drawer.setMinimumHeight(0)
        drawer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        drawer.setStyleSheet(f"""
            QFrame#cmp-data-drawer {{
                background: {C.BG_RAISED};
                border-top: 1px solid {C.BORDER};
            }}
            QTableWidget#cmp-drawer-table {{
                background: {C.BG};
                border: none;
                gridline-color: transparent;
                color: {C.TEXT};
                font-size: 10px;
            }}
            QTableWidget#cmp-drawer-table::item {{
                border-bottom: 1px solid rgba(212,196,168,0.35);
                padding: 2px 7px;
            }}
            QHeaderView::section {{
                background: {C.BG_LOW};
                color: {C.TEXT_MID};
                border: none;
                border-bottom: 1px solid {C.BORDER};
                padding: 3px 7px;
                font-weight: 600;
                font-size: 10px;
            }}
        """)

        lay = QVBoxLayout(drawer)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(32)
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(8, 3, 8, 3)
        header_lay.setSpacing(6)

        self._drawer_toggle_btn = _cmp_chk(
            " Table", "Show data for the active plot", False, "fa6s.table"
        )
        self._drawer_toggle_btn.clicked.connect(self._toggle_drawer)
        header_lay.addWidget(self._drawer_toggle_btn)

        self._drawer_title = QLabel("Plot data")
        self._drawer_title.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: 10px; background: transparent;"
        )
        header_lay.addWidget(self._drawer_title, 1)

        self._drawer_count = QLabel("")
        self._drawer_count.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: 10px; background: transparent;"
        )
        header_lay.addWidget(self._drawer_count)

        self._drawer_export_btn = QPushButton("Export CSV")
        self._drawer_export_btn.setProperty("pw-btn", True)
        self._drawer_export_btn.clicked.connect(self._export_drawer_data)
        header_lay.addWidget(self._drawer_export_btn)
        lay.addWidget(header)

        self._drawer_table = QTableWidget()
        self._drawer_table.setObjectName("cmp-drawer-table")
        self._drawer_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._drawer_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._drawer_table.setAlternatingRowColors(False)
        self._drawer_table.setShowGrid(False)
        self._drawer_table.setWordWrap(False)
        self._drawer_table.verticalHeader().setVisible(False)
        self._drawer_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self._drawer_table.verticalHeader().setDefaultSectionSize(24)
        self._drawer_table.horizontalHeader().setStretchLastSection(True)
        self._drawer_table.horizontalHeader().setMinimumSectionSize(72)
        self._drawer_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._drawer_table.horizontalHeader().setFixedHeight(25)
        self._drawer_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._drawer_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._drawer_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._drawer_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._drawer_table.setVisible(False)
        lay.addWidget(self._drawer_table, 1)

        return drawer
    
    def create_toolbar(self):
        """Create the toolbar with plot controls."""
        toolbar = QWidget()
        toolbar.setObjectName("pw-toolbar")
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(4)

        plot_label = QLabel("Plot")
        plot_label.setStyleSheet("color: #6a6254;")
        self._tb_plot_label = plot_label
        row.addWidget(plot_label)

        self.plot_selector = QComboBox()
        self.plot_selector.setObjectName("pw-style-sel")
        self.plot_selector.addItems([
            "Distribution",
            "K-Values",
            "K Distribution",
            "Combined",
            "Histogram",
        ])
        self.plot_selector.setMaximumWidth(134)
        self.plot_selector.currentTextChanged.connect(self.on_plot_type_changed)
        row.addWidget(self.plot_selector)

        row.addWidget(_cmp_sep())

        mode_label = QLabel("Layout")
        mode_label.setStyleSheet("color: #6a6254;")
        self._tb_mode_label = mode_label
        row.addWidget(mode_label)

        mode_frame = QFrame()
        mode_frame.setObjectName("pw-seg")
        mode_row = QHBoxLayout(mode_frame)
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(0)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)

        self.overlay_radio = QPushButton("Overlay")
        self.overlay_radio.setProperty("pw-seg", True)
        self.overlay_radio.setProperty("active", True)
        self.overlay_radio.setCheckable(True)
        self.overlay_radio.setChecked(True)
        self.overlay_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.overlay_radio.toggled.connect(lambda on: _sync_cmp_seg(self.overlay_radio, on))
        self.overlay_radio.toggled.connect(lambda checked: self._on_mode_toggled(checked, "overlay"))
        self._mode_group.addButton(self.overlay_radio)
        mode_row.addWidget(self.overlay_radio)

        self.grid_radio = QPushButton("Grid")
        self.grid_radio.setProperty("pw-seg", True)
        self.grid_radio.setProperty("active", False)
        self.grid_radio.setCheckable(True)
        self.grid_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.grid_radio.toggled.connect(lambda on: _sync_cmp_seg(self.grid_radio, on))
        self.grid_radio.toggled.connect(lambda checked: self._on_mode_toggled(checked, "grid"))
        self._mode_group.addButton(self.grid_radio)
        mode_row.addWidget(self.grid_radio)

        row.addWidget(mode_frame)
        row.addWidget(_cmp_sep())

        # Breakdown — render per dataset or per group. Reads the groups the
        # Scope & Groups dialog defined; it does not manage groups. Shown only
        # when at least one named group exists.
        self._tb_breakdown_label = QLabel("Breakdown")
        self._tb_breakdown_label.setStyleSheet("color: #6a6254;")
        row.addWidget(self._tb_breakdown_label)

        breakdown_frame = QFrame()
        breakdown_frame.setObjectName("pw-seg")
        breakdown_row = QHBoxLayout(breakdown_frame)
        breakdown_row.setContentsMargins(0, 0, 0, 0)
        breakdown_row.setSpacing(0)
        self._breakdown_frame = breakdown_frame

        self._breakdown_group = QButtonGroup(self)
        self._breakdown_group.setExclusive(True)

        self.bd_dataset_btn = QPushButton("Per dataset")
        self.bd_dataset_btn.setProperty("pw-seg", True)
        self.bd_dataset_btn.setProperty("active", True)
        self.bd_dataset_btn.setCheckable(True)
        self.bd_dataset_btn.setChecked(True)
        self.bd_dataset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bd_dataset_btn.toggled.connect(lambda on: _sync_cmp_seg(self.bd_dataset_btn, on))
        self.bd_dataset_btn.toggled.connect(lambda checked: self._on_breakdown_toggled(checked, "dataset"))
        self._breakdown_group.addButton(self.bd_dataset_btn)
        breakdown_row.addWidget(self.bd_dataset_btn)

        self.bd_group_btn = QPushButton("Per group")
        self.bd_group_btn.setProperty("pw-seg", True)
        self.bd_group_btn.setProperty("active", False)
        self.bd_group_btn.setCheckable(True)
        self.bd_group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bd_group_btn.toggled.connect(lambda on: _sync_cmp_seg(self.bd_group_btn, on))
        self.bd_group_btn.toggled.connect(lambda checked: self._on_breakdown_toggled(checked, "group"))
        self._breakdown_group.addButton(self.bd_group_btn)
        breakdown_row.addWidget(self.bd_group_btn)

        row.addWidget(breakdown_frame)
        self._breakdown_sep = _cmp_sep()
        row.addWidget(self._breakdown_sep)

        self.grid_label = QLabel("Columns")
        self.grid_label.setStyleSheet("color: #6a6254;")
        self.grid_label.setVisible(False)
        row.addWidget(self.grid_label)

        self.grid_selector = QComboBox()
        self.grid_selector.setObjectName("pw-style-sel")
        self.grid_selector.addItems(["2x2", "3x2", "3x3", "4x3"])
        self.grid_selector.setMaximumWidth(68)
        self.grid_selector.setVisible(False)
        self.grid_selector.currentTextChanged.connect(self.on_grid_layout_changed)
        row.addWidget(self.grid_selector)

        row.addWidget(_cmp_sep())

        # Style preset — drives the PlotStyle used by every render call.
        style_label = QLabel("Style")
        style_label.setStyleSheet("color: #6a6254;")
        self._tb_style_label = style_label
        row.addWidget(style_label)

        self.style_selector = QComboBox()
        self.style_selector.setObjectName("pw-style-sel")
        self.style_selector.addItems(get_available_style_names())
        self.style_selector.setCurrentText(self.current_style.name)
        self.style_selector.setMaximumWidth(118)
        self.style_selector.setToolTip("Plot style preset")
        self.style_selector.currentTextChanged.connect(self._on_style_preset_changed)
        row.addWidget(self.style_selector)

        self._tb_sidebar_btn = _cmp_chk(
            " Controls", "Toggle controls panel", False, "fa6s.sliders"
        )
        self._tb_sidebar_btn.clicked.connect(self._toggle_sidebar)
        row.addWidget(self._tb_sidebar_btn)

        self._tb_drawer_btn = _cmp_chk(
            " Table", "Toggle active plot data drawer", False, "fa6s.table"
        )
        self._tb_drawer_btn.clicked.connect(self._toggle_drawer)
        row.addWidget(self._tb_drawer_btn)

        row.addWidget(_cmp_sep())

        self.zoom_in_btn = _cmp_btn("", "Zoom in", "fa6s.magnifying-glass-plus")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        row.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = _cmp_btn("", "Zoom out", "fa6s.magnifying-glass-minus")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        row.addWidget(self.zoom_out_btn)

        self.reset_btn = _cmp_btn(" Fit", "Reset active plot", "fa6s.arrows-to-circle")
        self.reset_btn.clicked.connect(self.reset_view)
        row.addWidget(self.reset_btn)

        row.addWidget(_cmp_sep())

        self._interaction_hint = QLabel("Wheel zoom  |  Shift-drag pan  |  Double-click reset")
        self._interaction_hint.setStyleSheet("color: #8a816f; font-size: 10px;")
        row.addWidget(self._interaction_hint)

        row.addStretch(1)
        return toolbar

    def resizeEvent(self, event):
        """Keep the sidebar toggle handle aligned to the chart edge."""
        super().resizeEvent(event)
        self._position_toggle_handle()
        self._update_responsive_chrome()
        if self.drawer_visible and hasattr(self, "_drawer"):
            self._drawer.setMaximumHeight(self._drawer_open_height())

    def _update_responsive_chrome(self) -> None:
        width = self.width()
        if hasattr(self, "_interaction_hint"):
            self._interaction_hint.setVisible(width >= 900)
        for label_name in ("_tb_plot_label", "_tb_mode_label", "_tb_style_label"):
            label = getattr(self, label_name, None)
            if label is not None:
                label.setVisible(width >= 760)
        # Breakdown label is also contextual (only when named groups exist).
        bd_label = getattr(self, "_tb_breakdown_label", None)
        if bd_label is not None:
            bd_label.setVisible(width >= 760 and self._has_named_groups())
        if hasattr(self, "style_selector"):
            self.style_selector.setMaximumWidth(118 if width >= 820 else 96)
        if hasattr(self, "plot_selector"):
            self.plot_selector.setMaximumWidth(134 if width >= 820 else 114)

    def _position_toggle_handle(self) -> None:
        if not hasattr(self, "_toggle_handle") or not hasattr(self, "_chart_area"):
            return
        handle_w = 16
        handle_h = 40
        y = max(0, (self._chart_area.height() - handle_h) // 2)
        self._toggle_handle.setGeometry(0, y, handle_w, handle_h)

    def _toggle_drawer(self) -> None:
        self._set_drawer_visible(not self.drawer_visible)

    def _set_drawer_visible(self, visible: bool) -> None:
        self.drawer_visible = bool(visible)
        target = self._drawer_open_height() if self.drawer_visible else 32
        self._drawer_table.setVisible(self.drawer_visible)
        self._drawer_anim.stop()
        self._drawer_anim.setStartValue(self._drawer.height())
        self._drawer_anim.setEndValue(target)
        self._drawer_anim.start()

        for button in (
            getattr(self, "_tb_drawer_btn", None),
            getattr(self, "_drawer_toggle_btn", None),
        ):
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(self.drawer_visible)
            button.blockSignals(False)
            _sync_cmp_chk(button, self.drawer_visible)

    def _drawer_open_height(self) -> int:
        available = max(360, self.height())
        return min(260, max(130, int(available * 0.34)))

    def _toggle_sidebar(self) -> None:
        self.sidebar_visible = not self.sidebar_visible
        target = SZ.PLOT_SIDEBAR_W if self.sidebar_visible else 0
        self._sidebar_anim.stop()
        current_width = self._sidebar.width()
        self._sidebar.setMinimumWidth(current_width)
        self._sidebar.setMaximumWidth(current_width)
        self._sidebar_anim.setStartValue(current_width)
        self._sidebar_anim.setEndValue(target)
        self._sidebar_anim.start()

        self._tb_sidebar_btn.blockSignals(True)
        self._tb_sidebar_btn.setChecked(self.sidebar_visible)
        self._tb_sidebar_btn.blockSignals(False)
        _sync_cmp_chk(self._tb_sidebar_btn, self.sidebar_visible)

        chevron = "fa6s.chevron-left" if self.sidebar_visible else "fa6s.chevron-right"
        self._toggle_handle.setIcon(icon(chevron, C.TEXT_MID, 8))

    def _on_sidebar_width_changed(self, value) -> None:
        width = int(value)
        self._sidebar.setMinimumWidth(width)
        self._position_toggle_handle()

    # ═══════════════════════════════════════════════════════════════════
    # Sidebar
    # ═══════════════════════════════════════════════════════════════════

    def _build_sidebar(self) -> QFrame:
        """Sidebar matching the Individual Samples tab layout.

        Uses the same CollapsibleSection widgets and row builders so both tabs
        stay visually in sync — any tweak to sidebar_controls ripples here too.
        """
        sidebar = QFrame()
        sidebar.setObjectName("pw-sidebar")
        sidebar.setMinimumWidth(0)
        sidebar.setMinimumHeight(0)
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(sidebar)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("pw-sidebar-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(scroll)

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        scroll.setWidget(content)

        # ── Display Options ──
        self._sect_display = CollapsibleSection(
            "Display Options", "fa6s.eye",
            CollapsibleSection.OLIVE, expanded=True,
        )
        row_grid, self._sw_grid = make_toggle_row("Show grid lines", self.show_grid)
        self._sw_grid.toggled.connect(self._on_sidebar_grid_toggled)
        self._sect_display.add_widget(row_grid)

        row_legend, self._sw_legend = make_toggle_row("Show legend", self.show_legend)
        self._sw_legend.toggled.connect(self._on_sidebar_legend_toggled)
        self._sect_display.add_widget(row_legend)

        self._row_k_log, self._sw_k_log = make_toggle_row("Log K axis", self.log_k_y_scale)
        self._sw_k_log.toggled.connect(self._on_sidebar_log_k_toggled)
        self._sect_display.add_widget(self._row_k_log)
        lay.addWidget(self._sect_display)

        # ── K Distribution (contextual — only shown for that plot type) ──
        self._sect_kdist = CollapsibleSection(
            "K Distribution", "fa6s.chart-area",
            CollapsibleSection.OLIVE, expanded=True,
        )
        self._row_kdist_view, self._kdist_view_combo = make_combo_row(
            "Chart", ["Empirical CDF", "Lognormal histogram"])
        self._kdist_view_combo.currentIndexChanged.connect(
            lambda idx: self._on_kdist_view_changed("histogram" if idx == 1 else "cdf"))
        self._row_kdist_view.setToolTip(
            "K is pooled across the comparison scope.\n"
            "Per dataset = one pooled (Overall) distribution; "
            "Per group = one distribution per group."
        )
        self._sect_kdist.add_widget(self._row_kdist_view)

        self._row_kdist_axis, self._kdist_axis_combo = make_combo_row(
            "Histogram x-axis", ["ln K", "K"])
        self._kdist_axis_combo.currentIndexChanged.connect(
            lambda idx: self._on_kdist_axis_changed("k" if idx == 1 else "lnk"))
        self._sect_kdist.add_widget(self._row_kdist_axis)

        self._kdist_bin_options = ["Auto", "Off", "5", "10", "15", "20", "30"]
        self._row_kdist_bins, self._kdist_bins_combo = make_combo_row(
            "Histogram bins", self._kdist_bin_options)
        self._kdist_bins_combo.currentIndexChanged.connect(self._on_kdist_bins_changed)
        self._row_kdist_bins.setToolTip(
            "Auto sizes bars to the data (groups are drawn side-by-side). "
            "Off shows fitted curves only; a number sets a fixed bin count."
        )
        self._sect_kdist.add_widget(self._row_kdist_bins)
        self._sect_kdist.setVisible(False)
        lay.addWidget(self._sect_kdist)

        # ── Series Appearance ──
        self._sect_dataset_colors = CollapsibleSection(
            "Series Appearance", "fa6s.palette",
            CollapsibleSection.PURPLE, expanded=False,
        )
        self._color_container = QWidget()
        self._color_container_lay = QVBoxLayout(self._color_container)
        self._color_container_lay.setContentsMargins(0, 0, 0, 0)
        self._color_container_lay.setSpacing(0)
        self._empty_colors_hint = QLabel("  Add datasets to see color controls.")
        self._empty_colors_hint.setStyleSheet(
            f"color: #8a816f; padding: 10px; font-size: 10px;"
        )
        self._color_container_lay.addWidget(self._empty_colors_hint)
        self._sect_dataset_colors.add_widget(self._color_container)
        lay.addWidget(self._sect_dataset_colors)

        # ── Legend & Typography ──
        self._sect_advanced = CollapsibleSection(
            "Legend & Typography", "fa6s.text-height",
            CollapsibleSection.AMBER, expanded=False,
        )

        self._row_legend_loc, self._legend_loc_combo = make_combo_row(
            "Legend position", [label for _, _, label in _CMP_LEGEND_LOCATIONS])
        self._legend_loc_combo.currentIndexChanged.connect(self._on_legend_loc_changed)
        self._sect_advanced.add_widget(self._row_legend_loc)

        self._row_legend_layout, self._legend_layout_combo = make_combo_row(
            "Legend layout", [label for _, label in _CMP_LEGEND_LAYOUTS])
        self._legend_layout_combo.currentIndexChanged.connect(
            self._on_legend_layout_changed)
        self._sect_advanced.add_widget(self._row_legend_layout)

        self._row_legend_alpha, self._legend_alpha_spin = make_dspin_row(
            "Legend opacity", 0.0, 1.0, 0.05, 2)
        self._legend_alpha_spin.valueChanged.connect(
            lambda v: self._update_style_field("legend_framealpha", float(v)))
        self._sect_advanced.add_widget(self._row_legend_alpha)

        self._row_title_size, self._title_size_spin = make_spin_row(
            "Title size", 6, 36)
        self._title_size_spin.valueChanged.connect(
            lambda v: self._update_style_field("title_fontsize", int(v)))
        self._sect_advanced.add_widget(self._row_title_size)

        self._row_label_size, self._label_size_spin = make_spin_row(
            "Axis label size", 6, 36)
        self._label_size_spin.valueChanged.connect(
            lambda v: self._update_style_field("label_fontsize", int(v)))
        self._sect_advanced.add_widget(self._row_label_size)

        self._row_tick_size, self._tick_size_spin = make_spin_row(
            "Tick size", 5, 24)
        self._tick_size_spin.valueChanged.connect(
            lambda v: self._update_style_field("tick_fontsize", int(v)))
        self._sect_advanced.add_widget(self._row_tick_size)

        self._row_legend_size, self._legend_size_spin = make_spin_row(
            "Legend size", 5, 24)
        self._legend_size_spin.valueChanged.connect(
            lambda v: self._update_style_field("legend_fontsize", int(v)))
        self._sect_advanced.add_widget(self._row_legend_size)

        reset_row = QWidget()
        reset_lay = QHBoxLayout(reset_row)
        reset_lay.setContentsMargins(10, 6, 10, 6)
        self._style_reset_btn = QPushButton("Reset to preset")
        self._style_reset_btn.setProperty("pw-btn", True)
        self._style_reset_btn.setEnabled(False)
        self._style_reset_btn.setToolTip(
            "Discard legend/typography overrides and revert to the selected preset")
        self._style_reset_btn.clicked.connect(self._on_reset_custom_style)
        reset_lay.addWidget(self._style_reset_btn)
        self._sect_advanced.add_widget(reset_row)
        lay.addWidget(self._sect_advanced)

        self._sect_units = CollapsibleSection(
            "K-Value Units", "fa6s.scale-balanced",
            CollapsibleSection.EARTH, expanded=False,
        )
        self._unit_combo = QComboBox()
        self._unit_combo.setObjectName("pw-style-sel")
        all_units = HydraulicConductivityConverter.get_all_units()
        for unit, symbol in all_units.items():
            self._unit_combo.addItem(symbol, unit)
        default_index = self._unit_combo.findData(self.display_unit)
        if default_index >= 0:
            self._unit_combo.setCurrentIndex(default_index)
        self._unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        self._row_units = QWidget()
        unit_lay = QHBoxLayout(self._row_units)
        unit_lay.setContentsMargins(10, 5, 10, 5)
        unit_lay.addWidget(self._unit_combo)
        self._sect_units.add_widget(self._row_units)
        lay.addWidget(self._sect_units)

        # ── Export ──
        self._sect_export = CollapsibleSection(
            "Export", "fa6s.download",
            CollapsibleSection.RED, expanded=False,
        )
        export_w = QWidget()
        export_lay = QVBoxLayout(export_w)
        export_lay.setContentsMargins(10, 5, 10, 8)
        export_lay.setSpacing(4)
        btn_png = QPushButton("Export as PNG")
        btn_png.setProperty("pw-btn", True)
        btn_png.clicked.connect(lambda: self._export_figure("png"))
        btn_svg = QPushButton("Export as SVG")
        btn_svg.setProperty("pw-btn", True)
        btn_svg.clicked.connect(lambda: self._export_figure("svg"))
        export_lay.addWidget(btn_png)
        export_lay.addWidget(btn_svg)
        self._sect_export.add_widget(export_w)
        lay.addWidget(self._sect_export)

        lay.addStretch(1)
        self._sync_contextual_sidebar_sections()
        return sidebar

    # ── Sidebar handlers ───────────────────────────────────────────

    def _on_sidebar_grid_toggled(self, on: bool) -> None:
        self.show_grid = on
        self.refresh_plot()

    def _on_sidebar_legend_toggled(self, on: bool) -> None:
        self.show_legend = on
        self.refresh_plot()

    def _on_sidebar_log_k_toggled(self, on: bool) -> None:
        self.log_k_y_scale = bool(on)
        self.refresh_plot()

    def _update_style_field(self, field: str, value) -> None:
        """Override a single PlotStyle field, cloning the preset on first edit."""
        self._update_style_fields(**{field: value})

    def _update_style_fields(self, **changes) -> None:
        """Override one or more PlotStyle fields on the active custom style."""
        dirty = {
            k: v for k, v in changes.items()
            if getattr(self.current_style, k) != v
        }
        if not dirty:
            return
        self.current_style = dataclasses.replace(self.current_style, **dirty)
        self._style_is_custom = True
        self._sync_reset_button()
        self.refresh_plot()

    def _sync_sidebar_style_widgets(self, style: PlotStyle) -> None:
        """Push the given style into the sidebar spinboxes/combos without firing."""
        widgets = [
            getattr(self, '_legend_loc_combo', None),
            getattr(self, '_legend_layout_combo', None),
            getattr(self, '_legend_alpha_spin', None),
            getattr(self, '_title_size_spin', None),
            getattr(self, '_label_size_spin', None),
            getattr(self, '_tick_size_spin', None),
            getattr(self, '_legend_size_spin', None),
        ]
        if not all(widgets):
            return
        for w in widgets:
            w.blockSignals(True)
        loc_idx = next(
            (
                i for i, (loc, bbox, _label) in enumerate(_CMP_LEGEND_LOCATIONS)
                if loc == style.legend_loc
                and bbox == style.legend_bbox_to_anchor
            ),
            0,
        )
        layout_idx = next(
            (
                i for i, (ncol, _label) in enumerate(_CMP_LEGEND_LAYOUTS)
                if ncol == getattr(style, 'legend_ncol', 1)
            ),
            0,
        )
        self._legend_loc_combo.setCurrentIndex(loc_idx)
        self._legend_layout_combo.setCurrentIndex(layout_idx)
        self._legend_alpha_spin.setValue(float(style.legend_framealpha))
        self._title_size_spin.setValue(int(style.title_fontsize))
        self._label_size_spin.setValue(int(style.label_fontsize))
        self._tick_size_spin.setValue(int(style.tick_fontsize))
        self._legend_size_spin.setValue(int(style.legend_fontsize))
        for w in widgets:
            w.blockSignals(False)

    def _sync_reset_button(self) -> None:
        btn = getattr(self, '_style_reset_btn', None)
        if btn is not None:
            btn.setEnabled(self._style_is_custom)

    def _on_reset_custom_style(self) -> None:
        """Revert to the selected preset, discarding per-field overrides."""
        if not self._style_is_custom:
            return
        preset = get_style(self.style_selector.currentText())
        self.current_style = preset
        self._style_is_custom = False
        self.figure.patch.set_facecolor(preset.figure_facecolor)
        self._sync_sidebar_style_widgets(preset)
        self._sync_reset_button()
        self.refresh_plot()

    def _rebuild_dataset_color_rows(self) -> None:
        """Refresh color controls when datasets or groups change."""
        if not hasattr(self, '_color_container_lay'):
            return
        while self._color_container_lay.count():
            item = self._color_container_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._dataset_color_rows.clear()
        self._group_color_rows.clear()
        self._dataset_line_style_rows.clear()

        if not self.datasets:
            self._color_container_lay.addWidget(self._empty_colors_hint)
            self._empty_colors_hint.show()
            return

        self._empty_colors_hint.hide()

        group_order: list[str] = []
        grouped_datasets: dict[str, list[object]] = {}
        ungrouped_datasets: list[tuple[int, object]] = []
        for i, ds in enumerate(self.datasets):
            group_name = self._dataset_groups.get(ds.sample_name, UNGROUPED_LABEL)
            if group_name == UNGROUPED_LABEL:
                ungrouped_datasets.append((i, ds))
                continue
            if group_name not in group_order:
                group_order.append(group_name)
            grouped_datasets.setdefault(group_name, []).append(ds)

        for group_name in group_order:
            color = self._group_color_map.get(group_name, self.dataset_colors[0])
            row, dot = make_color_row(group_name, color)
            row.setToolTip(
                "Group color. Datasets in this group use this color with different line styles."
            )
            dot.mousePressEvent = (
                lambda _event, name=group_name, swatch=dot:
                self._pick_group_color(name, swatch)
            )
            self._color_container_lay.addWidget(row)
            self._group_color_rows[group_name] = dot
            for ds in grouped_datasets.get(group_name, []):
                key = self._dataset_style_keys.get(ds.sample_name, ds.sample_name)
                line_style = self._dataset_linestyles.get(ds.sample_name, "-")
                line_row, combo = self._make_line_style_row(
                    ds.sample_name,
                    key,
                    line_style,
                    color,
                )
                self._color_container_lay.addWidget(line_row)
                self._dataset_line_style_rows[key] = combo

        for i, ds in ungrouped_datasets:
            color = self._effective_color_for(ds.sample_name, i)
            row, dot = make_color_row(ds.sample_name, color)
            row.setToolTip("Ungrouped dataset color.")
            dot.mousePressEvent = (
                lambda _event, name=ds.sample_name, swatch=dot:
                self._pick_dataset_color(name, swatch)
            )
            self._color_container_lay.addWidget(row)
            self._dataset_color_rows[ds.sample_name] = dot

    def _make_line_style_row(
        self,
        sample_name: str,
        dataset_key: str,
        line_style: str,
        color: str,
    ) -> tuple[QWidget, QComboBox]:
        row = QFrame()
        row.setObjectName("series-line-style-row")
        row.setStyleSheet(
            "QFrame#series-line-style-row {"
            "  border-bottom: 1px solid rgba(212,196,168,0.35);"
            "  background: transparent;"
            "}"
            "QFrame#series-line-style-row QLabel {"
            "  border: none;"
            "  background: transparent;"
            "}"
            "QFrame#series-line-style-row QComboBox {"
            "  min-width: 64px;"
            "  max-width: 68px;"
            "}"
        )
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 4, 6, 5)
        lay.setSpacing(4)

        preview = LineStylePreview(color, line_style, width=32, height=14)
        preview.setToolTip(f"{sample_name}\nLine style: {line_style_label(line_style)}")

        lbl = QLabel()
        lbl.setProperty("pws-lbl", True)
        lbl.setToolTip(sample_name)
        lbl.setMinimumWidth(0)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lbl.setText(QFontMetrics(lbl.font()).elidedText(
            sample_name,
            Qt.TextElideMode.ElideRight,
            72,
        ))

        combo = QComboBox()
        combo.setObjectName("pw-style-sel")
        combo.setToolTip("Line style for this dataset inside its group")
        short_labels = {
            "-": "Solid",
            "--": "Dash",
            ":": "Dot",
            "-.": "Dash-dot",
            "-|o": "Line o",
            "--|s": "Dash s",
            ":|^": "Dot ^",
            "-.|D": "Ddot D",
        }
        for style, label in LINE_STYLE_OPTIONS:
            combo.addItem(short_labels.get(style, label), style)
            combo.setItemData(combo.count() - 1, label, Qt.ItemDataRole.ToolTipRole)
        current_index = combo.findData(line_style)
        combo.setCurrentIndex(current_index if current_index >= 0 else 0)
        combo.currentIndexChanged.connect(
            lambda _idx, key=dataset_key, name=sample_name, box=combo, view=preview:
            self._on_dataset_line_style_changed(key, name, box.currentData(), view)
        )
        combo.setFixedWidth(68)

        lay.addWidget(preview, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(lbl, 1)
        lay.addWidget(combo, 0)
        return row, combo

    def _short_label(self, text: str, max_chars: int = 36) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max(1, max_chars - 3)] + "..."

    def _effective_color_for(self, sample_name: str, index: int) -> str:
        group_name = self._dataset_groups.get(sample_name, UNGROUPED_LABEL)
        if group_name != UNGROUPED_LABEL and group_name in self._group_color_map:
            return self._group_color_map[group_name]
        override = self._dataset_color_overrides.get(sample_name)
        if override:
            return override
        # Use the dataset's stable first-seen position so ungrouped colors don't
        # shift when other datasets are hidden/re-shown.
        stable_index = (
            self._known_dataset_order.index(sample_name)
            if sample_name in self._known_dataset_order
            else index
        )
        return self.dataset_colors[stable_index % len(self.dataset_colors)]

    def _pick_dataset_color(self, sample_name: str, swatch: QLabel) -> None:
        dataset_index = next(
            (
                i for i, dataset in enumerate(self.datasets)
                if dataset.sample_name == sample_name
            ),
            0,
        )
        current = self._dataset_color_overrides.get(
            sample_name,
            self._effective_color_for(sample_name, dataset_index),
        )
        chosen = QColorDialog.getColor(
            QColor(current), self, f"Color for {sample_name}"
        )
        if not chosen.isValid():
            return
        hex_color = chosen.name()
        self._dataset_color_overrides[sample_name] = hex_color
        set_swatch_color(swatch, hex_color)
        self.refresh_plot()

    def _pick_group_color(self, group_name: str, swatch: QLabel) -> None:
        current = self._group_color_map.get(group_name, self.dataset_colors[0])
        chosen = QColorDialog.getColor(
            QColor(current), self, f"Color for {group_name}"
        )
        if not chosen.isValid():
            return
        hex_color = set_group_color(group_name, chosen.name())
        set_swatch_color(swatch, hex_color)
        self._rebuild_group_style_maps()
        self._rebuild_dataset_color_rows()
        self.refresh_plot()

    def _on_dataset_line_style_changed(
        self,
        dataset_key: str,
        sample_name: str,
        line_style: str,
        preview: Optional[LineStylePreview] = None,
    ) -> None:
        if not line_style:
            return
        stored = set_dataset_line_style(dataset_key, line_style)
        self._dataset_linestyles[sample_name] = stored
        if preview is not None:
            preview.set_line_style(stored)
            preview.setToolTip(
                f"{sample_name}\nLine style: {line_style_label(stored)}"
            )
        self.refresh_plot()

    def _effective_dataset_colors(self) -> List[str]:
        """Dataset-color list honouring any per-sample overrides."""
        return [
            self._effective_color_for(ds.sample_name, i)
            for i, ds in enumerate(self.datasets)
        ]

    def _effective_dataset_linestyles(self) -> List[str]:
        return [
            self._dataset_linestyles.get(ds.sample_name, "-")
            for ds in self.datasets
        ]

    def _effective_dataset_plot_styles(self) -> tuple[List[str], List[Optional[str]]]:
        line_styles: list[str] = []
        markers: list[Optional[str]] = []
        for style_key in self._effective_dataset_linestyles():
            line_style, marker = series_style_parts(style_key)
            line_styles.append(line_style)
            markers.append(marker)
        return line_styles, markers

    # ── Group breakdown & faceting ──────────────────────────────────

    def _has_named_groups(self) -> bool:
        """True when at least one plotted dataset carries a real group label."""
        return any(
            group != UNGROUPED_LABEL for group in self._dataset_groups.values()
        )

    def _use_group_breakdown(self) -> bool:
        """Whether comparison plots aggregate per group instead of per dataset.

        Group membership is owned by the Scope & Groups dialog; this only picks
        how to *render* it. Group rendering needs at least one named group.
        """
        return self.breakdown == "group" and self._has_named_groups()

    def _group_overlay_inputs(
        self,
    ) -> tuple[Dict[str, Dict[str, float]], List[str], Dict[str, set]]:
        """Per-group K aggregates for the K-Values overlay (in m/s).

        Named groups collapse to one geometric-mean series each (OK-only, from
        the comparison snapshot); ungrouped datasets stay individual so no scope
        is dropped. Returns parallel ``(results_m_s, colors, flagged_by_scope)``.
        """
        results: Dict[str, Dict[str, float]] = {}
        colors: List[str] = []
        flagged: Dict[str, set] = {}

        snapshot = self._comparison_snapshot
        buckets: Dict[str, Dict[str, list]] = {}
        if snapshot is not None:
            for record in snapshot.k.included_records:
                if record.group_name == UNGROUPED_LABEL or record.positive_value is None:
                    continue
                buckets.setdefault(record.group_name, {}).setdefault(
                    record.method_name, []
                ).append(record.positive_value)

        dataset_index = {ds.sample_name: i for i, ds in enumerate(self.datasets)}
        group_order = list(snapshot.k.group_names) if snapshot is not None else []

        def emit_group(group_name: str) -> None:
            method_means = {
                method: math.exp(sum(map(math.log, values)) / len(values))
                for method, values in buckets.get(group_name, {}).items()
                if values
            }
            if not method_means:
                return
            results[group_name] = method_means
            colors.append(self._group_color_map.get(group_name, self.dataset_colors[0]))
            flagged[group_name] = set()

        for group_name in group_order:
            if group_name != UNGROUPED_LABEL:
                emit_group(group_name)
                continue
            # Expand Ungrouped into its member datasets so each keeps identity.
            for ds in self.datasets:
                name = ds.sample_name
                if self._dataset_groups.get(name, UNGROUPED_LABEL) != UNGROUPED_LABEL:
                    continue
                k_dict = self.k_results_dict.get(name)
                if not k_dict:
                    continue
                results[name] = dict(k_dict)
                colors.append(
                    self._effective_color_for(name, dataset_index.get(name, 0))
                )
                flagged[name] = set(self.flagged_methods_dict.get(name, set()))

        return results, colors, flagged

    def _group_order(self) -> List[str]:
        """Group labels in first-seen dataset order (named groups + Ungrouped)."""
        order: list[str] = []
        for ds in self.datasets:
            group = self._dataset_groups.get(ds.sample_name, UNGROUPED_LABEL)
            if group not in order:
                order.append(group)
        return order

    def _distribution_units(self) -> list[dict]:
        """Faceting units for distribution plots.

        Per dataset → one single-member unit each. Per group → one multi-member
        unit per named group (members feed the aggregate curve + band), with
        ungrouped datasets kept as individual single-member units.
        """
        colors = self._effective_dataset_colors()
        color_by_name = {
            ds.sample_name: colors[i] for i, ds in enumerate(self.datasets)
        }

        def member(ds) -> tuple:
            return (ds.particle_sizes, ds.percent_passing)

        if not self._use_group_breakdown():
            return [
                {
                    "label": ds.sample_name,
                    "color": color_by_name.get(ds.sample_name, self.dataset_colors[0]),
                    "members": [member(ds)],
                }
                for ds in self.datasets
            ]

        units: list[dict] = []
        for group_name in self._group_order():
            members = [
                ds for ds in self.datasets
                if self._dataset_groups.get(ds.sample_name, UNGROUPED_LABEL) == group_name
            ]
            if group_name == UNGROUPED_LABEL:
                units.extend(
                    {
                        "label": ds.sample_name,
                        "color": color_by_name.get(ds.sample_name, self.dataset_colors[0]),
                        "members": [member(ds)],
                    }
                    for ds in members
                )
            else:
                units.append({
                    "label": group_name,
                    "color": self._group_color_map.get(group_name, self.dataset_colors[0]),
                    "members": [member(ds) for ds in members],
                })
        return units

    def _k_grid_units(self) -> tuple[Dict[str, Dict[str, float]], Dict[str, set]]:
        """Return ``(display_results, flagged_by_scope)`` for K grid facets.

        Honours the breakdown: per-dataset cells use raw per-dataset results;
        per-group cells use the group geometric-mean aggregates.
        """
        if self._use_group_breakdown():
            results_m_s, _colors, flagged = self._group_overlay_inputs()
            display = {
                name: self._convert_k_dict(k_dict)
                for name, k_dict in results_m_s.items()
            }
            return display, flagged
        return self._display_k_results_dict(), self.flagged_methods_dict

    def _group_mean_passing(self, members) -> tuple[list, list]:
        """Mean % passing across group members on the union of their sizes.

        Each member is interpolated (log-x) onto the shared size union and
        averaged, giving a monotonic aggregate curve whose retained
        differences stay non-negative — safe to feed the histogram helper.
        """
        sizes_set = {
            float(size)
            for sizes, _pcts in members
            for size in sizes
            if size is not None and float(size) > 0
        }
        union = sorted(sizes_set)
        if not union:
            return [], []
        log_grid = np.log10(union)
        stacked = []
        for sizes, pcts in members:
            pairs = sorted(
                (float(s), float(p))
                for s, p in zip(sizes, pcts)
                if s is not None and float(s) > 0 and p is not None
            )
            if len(pairs) < 2:
                continue
            xs = np.log10([s for s, _ in pairs])
            ys = np.array([p for _, p in pairs], dtype=float)
            stacked.append(np.interp(log_grid, xs, ys))
        if not stacked:
            return [], []
        mean_passing = np.mean(np.vstack(stacked), axis=0)
        return union, mean_passing.tolist()

    def _histogram_units(self) -> list[dict]:
        """Faceting units for the grain histogram (per dataset or per group)."""
        colors = self._effective_dataset_colors()
        color_by_name = {
            ds.sample_name: colors[i] for i, ds in enumerate(self.datasets)
        }

        def dataset_unit(ds) -> dict:
            sizes, freq = self._calculate_histogram_frequencies(
                ds.particle_sizes, ds.percent_passing
            )
            return {
                "label": ds.sample_name,
                "color": color_by_name.get(ds.sample_name, self.dataset_colors[0]),
                "sizes": sizes,
                "freq": freq,
            }

        if not self._use_group_breakdown():
            return [dataset_unit(ds) for ds in self.datasets]

        units: list[dict] = []
        for group_name in self._group_order():
            members = [
                ds for ds in self.datasets
                if self._dataset_groups.get(ds.sample_name, UNGROUPED_LABEL) == group_name
            ]
            if group_name == UNGROUPED_LABEL:
                units.extend(dataset_unit(ds) for ds in members)
                continue
            usizes, mean_passing = self._group_mean_passing(
                [(ds.particle_sizes, ds.percent_passing) for ds in members]
            )
            sizes, freq = self._calculate_histogram_frequencies(usizes, mean_passing)
            units.append({
                "label": group_name,
                "color": self._group_color_map.get(group_name, self.dataset_colors[0]),
                "sizes": sizes,
                "freq": freq,
            })
        return units

    def _combined_facets(self) -> list[dict]:
        """Faceting units for the combined view: distribution + K per unit.

        Joins each distribution unit to its K values by label — group geo-mean
        aggregates per group, or raw per-dataset results otherwise.
        """
        if self._use_group_breakdown():
            k_results_m_s, _colors, flagged_by_scope = self._group_overlay_inputs()
        else:
            k_results_m_s = self.k_results_dict
            flagged_by_scope = self.flagged_methods_dict

        facets: list[dict] = []
        for unit in self._distribution_units():
            label = unit["label"]
            facets.append({
                "label": label,
                "color": unit["color"],
                "members": unit["members"],
                "k": k_results_m_s.get(label, {}),
                "flagged": flagged_by_scope.get(label, set()),
            })
        return facets

    def reset_presentation_state(self) -> None:
        """Forget accumulated color/style ordering and the breakdown choice.

        Call this on a genuine comparison-scope change (Scope & Groups), not on
        visibility toggles — those must keep colors and the breakdown stable.
        """
        self._known_group_order = []
        self._known_dataset_order = []
        self._known_dataset_group = {}
        self._breakdown_explicit = False

    def _on_breakdown_toggled(self, checked: bool, mode: str) -> None:
        if not checked or self.breakdown == mode:
            return
        self.breakdown = mode
        self._breakdown_explicit = True
        self.refresh_plot()

    def _on_kdist_view_changed(self, view: str) -> None:
        if self.k_dist_view == view:
            return
        self.k_dist_view = view
        self._sync_kdist_controls()
        self.refresh_plot()

    def _on_kdist_axis_changed(self, axis: str) -> None:
        if self.k_hist_axis == axis:
            return
        self.k_hist_axis = axis
        self.refresh_plot()

    def _on_kdist_bins_changed(self, index: int) -> None:
        label = self._kdist_bin_options[index] if 0 <= index < len(self._kdist_bin_options) else "Auto"
        value = label.lower() if label in ("Auto", "Off") else label
        if self.k_hist_bins == value:
            return
        self.k_hist_bins = value
        self.refresh_plot()

    def _sync_kdist_controls(self) -> None:
        """Show K-distribution chart/axis sidebar rows only for that plot type."""
        if not hasattr(self, "_sect_kdist"):
            return
        is_kdist = self.current_plot_type == "k-distribution"
        self._sect_kdist.setVisible(is_kdist)
        # The axis + bins rows are only meaningful for the histogram view.
        histogram = is_kdist and self.k_dist_view == "histogram"
        if hasattr(self, "_row_kdist_axis"):
            self._row_kdist_axis.setVisible(histogram)
        if hasattr(self, "_row_kdist_bins"):
            self._row_kdist_bins.setVisible(histogram)

    def _sync_breakdown_controls(self) -> None:
        """Show the Breakdown control only when named groups exist; sync buttons."""
        if not hasattr(self, "_breakdown_frame"):
            return
        has_groups = self._has_named_groups()
        for widget in (self._tb_breakdown_label, self._breakdown_frame, self._breakdown_sep):
            widget.setVisible(has_groups)
        if not has_groups and self.breakdown == "group":
            self.breakdown = "dataset"
        is_group = self.breakdown == "group"
        for button, on in ((self.bd_dataset_btn, not is_group), (self.bd_group_btn, is_group)):
            button.blockSignals(True)
            button.setChecked(on)
            button.blockSignals(False)
            _sync_cmp_seg(button, on)

    def _facet_dims(self, count: int) -> tuple[int, int, int, int]:
        """Return ``(rows, cols, shown, hidden)`` fitting *count* faceted panels.

        Columns follow the layout selector; rows expand to fit every unit so
        nothing is silently dropped. A soft cap keeps pathological counts
        readable, surfacing the remainder through an overflow note.
        """
        cols = max(1, self.grid_layout[1])
        shown = max(0, min(count, self.MAX_FACET_PANELS))
        hidden = max(0, count - shown)
        rows = max(1, math.ceil(max(shown, 1) / cols))
        return rows, cols, shown, hidden

    def _draw_facet_overflow_note(self, hidden: int) -> None:
        """Annotate the figure when the soft panel cap hid some units."""
        if hidden <= 0:
            return
        self.figure.text(
            0.5, 0.005,
            f"+{hidden} more not shown — narrow the comparison scope to see them",
            ha="center", va="bottom",
            fontsize=8, color=C.TEXT_MUTED, fontstyle="italic",
        )

    def _rebuild_group_style_maps(self) -> None:
        self._dataset_groups = {}
        self._dataset_style_keys = {}
        self._dataset_linestyles = {}

        for dataset in self.datasets:
            name = dataset.sample_name
            group_name = dataset_group_name(dataset)
            self._dataset_groups[name] = group_name
            self._dataset_style_keys[name] = dataset_series_key(dataset)
            self._known_dataset_group[name] = group_name
            if name not in self._known_dataset_order:
                self._known_dataset_order.append(name)
            if group_name != UNGROUPED_LABEL and group_name not in self._known_group_order:
                self._known_group_order.append(group_name)

        # Stable colors: assign by first-seen group order across the session so
        # hiding/re-showing a group never re-shuffles colors.
        self._group_color_map = group_color_map(
            self._known_group_order,
            palette=self.dataset_colors,
            include_ungrouped=False,
        )

        for dataset in self.datasets:
            name = dataset.sample_name
            group_name = self._dataset_groups.get(name, UNGROUPED_LABEL)
            if group_name == UNGROUPED_LABEL:
                self._dataset_linestyles[name] = "-"
                continue
            # Stable member index = position among all known members of this
            # group, so hiding one member doesn't restyle the others.
            members = [
                n for n in self._known_dataset_order
                if self._known_dataset_group.get(n) == group_name
            ]
            member_index = members.index(name) if name in members else 0
            default_style = LINE_STYLE_OPTIONS[member_index % len(LINE_STYLE_OPTIONS)][0]
            dataset_key = self._dataset_style_keys.get(name, name)
            self._dataset_linestyles[name] = dataset_line_style(dataset_key, default_style)

    def _export_figure(self, fmt: str) -> None:
        """Save the current comparison figure to disk."""
        if self.figure is None:
            return
        ext_filter = {"png": "PNG (*.png)", "svg": "SVG (*.svg)"}.get(fmt, "All Files (*)")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export plot", f"comparison.{fmt}", ext_filter,
        )
        if not path:
            return
        try:
            path = self._with_extension(path, fmt)
            self.figure.savefig(path, format=fmt, dpi=200, bbox_inches="tight")
            QMessageBox.information(
                self, "Export Successful", f"Plot exported to:\n{path}"
            )
        except Exception as exc:  # pragma: no cover — user-facing dialog
            QMessageBox.warning(self, "Export failed", str(exc))

    def on_plot_type_changed(self, text: str):
        """Handle plot type change"""
        plot_map = {
            "Distribution": "distribution",
            "K-Values": "k-values",
            "K Distribution": "k-distribution",
            "Combined": "combined",
            "Histogram": "histogram",
        }

        self.current_plot_type = plot_map.get(text, "distribution")
        self._normalize_display_mode_for_plot_type()
        self.refresh_plot()

    def _on_mode_toggled(self, checked: bool, mode: str):
        """Apply layout changes only for the newly checked radio button."""
        if checked:
            self.set_display_mode(mode)

    def set_display_mode(self, mode: str):
        """Set the layout mode (overlay | grid)."""
        if mode == "grouped":  # legacy guard — the 'grouped' mode was removed
            mode = "overlay"
        self.display_mode = mode
        self._normalize_display_mode_for_plot_type()

        # Show/hide grid selector
        show_grid_selector = (self.display_mode == "grid")
        self.grid_label.setVisible(show_grid_selector)
        self.grid_selector.setVisible(show_grid_selector)

        self.refresh_plot()

    def _normalize_display_mode_for_plot_type(self):
        """Keep the layout mode consistent with the selected plot type.

        combined/histogram are inherently faceted (grid only); k-distribution is
        a single shared axes (overlay only); distribution/k-values allow both.
        """
        grid_only = self.current_plot_type in ("combined", "histogram")
        overlay_only = self.current_plot_type in ("k-distribution",)

        if grid_only:
            self.display_mode = "grid"
        elif overlay_only:
            self.display_mode = "overlay"
        elif self.display_mode not in ("overlay", "grid"):
            self.display_mode = "overlay"

        self.overlay_radio.setEnabled(not grid_only)
        self.grid_radio.setEnabled(not overlay_only)

        self._sync_mode_radios()
        self._sync_breakdown_controls()
        self._sync_kdist_controls()
        self._sync_contextual_sidebar_sections()

    def _sync_contextual_sidebar_sections(self) -> None:
        if not hasattr(self, "_sect_units"):
            return
        show_units = self.current_plot_type in {"k-values", "k-distribution", "combined"}
        self._sect_units.setVisible(show_units)
        if hasattr(self, "_row_units"):
            self._row_units.setVisible(show_units)
        show_log_axis = self.current_plot_type in {"k-values", "combined"}
        if hasattr(self, "_row_k_log"):
            self._row_k_log.setVisible(show_log_axis)

    def _sync_mode_radios(self):
        """Reflect the active layout mode in the radio buttons without re-entering."""
        buttons = [
            (self.overlay_radio, "overlay"),
            (self.grid_radio, "grid"),
        ]
        for button, mode in buttons:
            button.blockSignals(True)
            button.setChecked(self.display_mode == mode)
            button.blockSignals(False)
            _sync_cmp_seg(button, self.display_mode == mode)

    def _ordered_methods(self, method_names) -> List[str]:
        """Return K-methods in a stable, domain-specific order."""
        return ordered_methods(method_names)

    def _calculate_histogram_frequencies(self, particle_sizes, percent_passing):
        """Convert cumulative percent passing to retained fractions per size class."""
        pairs = sorted(zip(particle_sizes, percent_passing), key=lambda pair: pair[0], reverse=True)
        if not pairs:
            return np.array([]), np.array([])

        sizes = np.array([size for size, _ in pairs], dtype=float)
        passing = np.array([passing for _, passing in pairs], dtype=float)
        next_passing = np.append(passing[1:], 0.0)
        freq = np.maximum(0.0, passing - next_passing)
        return sizes, freq

    def _style_k_bar(self, bar, color: str, flagged: bool):
        """Apply warning styling to flagged K-value bars."""
        if flagged:
            bar.set_facecolor('none')
            bar.set_edgecolor(color)
            bar.set_linewidth(2.0)
            bar.set_hatch('////')
            bar.set_alpha(1.0)
        else:
            bar.set_edgecolor('black')
            bar.set_linewidth(0.5)

    def _legend_kwargs(self, label_count: Optional[int] = None) -> dict:
        """Build legend kwargs from the active PlotStyle so loc/bbox/fontsize are honoured."""
        return build_legend_kwargs(self.current_style, label_count)

    def _add_flagged_legend_handle(self, ax):
        """Append a warning-state legend entry when flagged methods are present."""
        handles, labels = ax.get_legend_handles_labels()
        handles = handles + [
            Patch(
                facecolor='none',
                edgecolor=C.TEXT,
                hatch='////',
                label='Flagged / Warning',
            )
        ]
        labels = labels + ['Flagged / Warning']
        ax.legend(handles, labels, **self._legend_kwargs(len(labels)))

    def on_grid_layout_changed(self, text: str):
        """Handle grid layout change"""
        layouts = {
            "2x2": (2, 2),
            "3x2": (3, 2),
            "3x3": (3, 3),
            "4x3": (4, 3)
        }
        self.grid_layout = layouts.get(text, (2, 2))
        self.refresh_plot()
    
    def update_display_options(self):
        """Update display options from the sidebar controls."""
        if hasattr(self, "_sw_grid"):
            self.show_grid = self._sw_grid.isChecked()
        if hasattr(self, "_sw_legend"):
            self.show_legend = self._sw_legend.isChecked()
        self.refresh_plot()

    def _on_style_preset_changed(self, preset_name: str) -> None:
        # Picking a preset discards any legend-location override — the preset's
        # own legend_loc becomes authoritative again. Matches the single-tab
        # "Reset to preset" semantics.
        self._style_is_custom = False
        self.set_style(get_style(preset_name))

    def _on_unit_changed(self) -> None:
        selected_unit = self._unit_combo.currentData() if hasattr(self, "_unit_combo") else None
        if selected_unit:
            self.set_display_unit(selected_unit)

    def set_display_unit(self, unit: HydraulicConductivityUnit) -> None:
        """Set K-value display unit and refresh K-bearing comparison plots."""
        self.display_unit = unit
        if hasattr(self, "_unit_combo"):
            idx = self._unit_combo.findData(unit)
            if idx >= 0 and idx != self._unit_combo.currentIndex():
                self._unit_combo.blockSignals(True)
                self._unit_combo.setCurrentIndex(idx)
                self._unit_combo.blockSignals(False)
        self.refresh_plot()

    def _unit_symbol(self) -> str:
        return HydraulicConductivityConverter.UNIT_SYMBOLS[self.display_unit]

    def _k_axis_label(self) -> str:
        return f"Hydraulic Conductivity K ({self._unit_symbol()})"

    def _convert_k_value(self, value_m_s: Optional[float]) -> Optional[float]:
        if value_m_s is None:
            return None
        return HydraulicConductivityConverter.convert_from_m_per_s(
            value_m_s, self.display_unit
        )

    def _convert_k_dict(self, k_dict: Dict[str, float]) -> Dict[str, float]:
        converted: Dict[str, float] = {}
        for method, value in k_dict.items():
            display_value = self._convert_k_value(value)
            if display_value is not None:
                converted[method] = display_value
        return converted

    def _display_k_results_dict(self) -> Dict[str, Dict[str, float]]:
        return {
            name: self._convert_k_dict(k_dict)
            for name, k_dict in self.k_results_dict.items()
        }

    def _on_legend_loc_changed(self, index: int) -> None:
        if index < 0 or index >= len(_CMP_LEGEND_LOCATIONS):
            return
        new_loc, new_bbox, _label = _CMP_LEGEND_LOCATIONS[index]
        if (self.current_style.legend_loc == new_loc
                and self.current_style.legend_bbox_to_anchor == new_bbox):
            return
        # Clone the active style with the new legend placement so we don't mutate
        # the shared preset instance.
        self.current_style = dataclasses.replace(
            self.current_style,
            legend_loc=new_loc,
            legend_bbox_to_anchor=new_bbox,
        )
        self._style_is_custom = True
        self._sync_reset_button()
        self.refresh_plot()

    def _on_legend_layout_changed(self, index: int) -> None:
        if index < 0 or index >= len(_CMP_LEGEND_LAYOUTS):
            return
        ncol, _label = _CMP_LEGEND_LAYOUTS[index]
        if getattr(self.current_style, 'legend_ncol', 1) == ncol:
            return
        self.current_style = dataclasses.replace(
            self.current_style,
            legend_ncol=ncol,
        )
        self._style_is_custom = True
        self._sync_reset_button()
        self.refresh_plot()

    def _sync_legend_loc_selector(self) -> None:
        """Point the legend-loc dropdown at the active style's value, silently."""
        selector = getattr(self, '_legend_loc_combo', None)
        if selector is None:
            return
        idx = next(
            (
                i for i, (loc, bbox, _label) in enumerate(_CMP_LEGEND_LOCATIONS)
                if loc == self.current_style.legend_loc
                and bbox == self.current_style.legend_bbox_to_anchor
            ),
            0,
        )
        selector.blockSignals(True)
        selector.setCurrentIndex(idx)
        selector.blockSignals(False)


    def set_datasets(self, dataset_tabs: List):
        """Set the datasets to compare"""
        self.datasets = []
        self.k_results_dict = {}
        self.flagged_methods_dict = {}
        self._comparison_snapshot = build_comparison_snapshot(
            dataset_tabs,
            ComparisonSnapshotOptions(
                k_options=KAggregationOptions(
                    include_warnings=False,
                    include_errors=False,
                    method_order=tuple(DEFAULT_METHOD_ORDER),
                )
            ),
        )
        
        for tab in dataset_tabs:
            dataset = tab.get_dataset()
            self.datasets.append(dataset)
            
            # Get K-results if available
            results = tab.get_results()
            if results:
                k_dict = {}
                flagged_methods = set()
                for r in results:
                    if r.k_value is not None and r.k_value > 0:
                        k_dict[r.method_name] = r.k_value
                    status_value = getattr(r.status, 'value', str(r.status))
                    if status_value != 'OK' or not getattr(r, 'conditions_met', True):
                        flagged_methods.add(r.method_name)
                if k_dict:
                    self.k_results_dict[dataset.sample_name] = k_dict
                    self.flagged_methods_dict[dataset.sample_name] = flagged_methods

        active_names = {dataset.sample_name for dataset in self.datasets}
        self._dataset_color_overrides = {
            name: color
            for name, color in self._dataset_color_overrides.items()
            if name in active_names
        }
        self._rebuild_group_style_maps()
        # Default to per-group rendering when the loaded scope carries named
        # groups; otherwise per-dataset. Honour an explicit user choice so
        # visibility toggles (which re-enter set_datasets) don't reset it.
        if not self._breakdown_explicit:
            self.breakdown = "group" if self._has_named_groups() else "dataset"
        self._sync_breakdown_controls()
        self._rebuild_dataset_color_rows()

    def refresh_plot(self):
        """Refresh the plot based on current settings"""
        if not self.datasets:
            self.show_empty_state()
            return
        
        self.figure.clear()
        
        if self.current_plot_type == "distribution":
            self.plot_distribution()
        elif self.current_plot_type == "k-values":
            self.plot_k_values()
        elif self.current_plot_type == "k-distribution":
            self.plot_k_distribution()
        elif self.current_plot_type == "combined":
            self.plot_combined()
        elif self.current_plot_type == "histogram":
            self.plot_histogram()
        
        self._prime_current_ax()
        self._capture_default_limits()
        self._apply_active_axes_styling()
        self._apply_figure_layout()
        self._refresh_drawer()
        self.canvas.draw()
        self.plot_updated.emit()

    def _apply_figure_layout(self):
        """Keep labels visible without letting tight_layout warnings spill into the console."""
        apply_legend_aware_layout(
            self.figure,
            self.current_style,
            pad=0.9,
            fallback=dict(
                left=0.08,
                right=0.98,
                top=0.94,
                bottom=0.16,
                wspace=0.28,
                hspace=0.34,
            ),
        )

    def _on_canvas_click(self, event) -> None:
        self._interactions.on_click(event)

    def _set_current_ax(self, ax) -> None:
        self._interactions.set_current_ax(ax)

    def _prime_current_ax(self) -> None:
        self._interactions.prime_current_ax()

    @staticmethod
    def _zoom_axis_limits(limits, scale: str, factor: float) -> tuple[float, float]:
        return AxesInteractionController.zoom_axis_limits(limits, scale, factor)

    def _zoom_target_axes(self):
        return self._interactions.zoom_target_axes()

    @staticmethod
    def _event_has_shift(event) -> bool:
        return AxesInteractionController._event_has_shift(event)

    def _capture_default_limits(self) -> None:
        self._interactions.capture_default_limits()

    def _apply_active_axes_styling(self) -> None:
        self._interactions.apply_active_axes_styling()

    def _reset_axes_view(self, ax) -> None:
        self._interactions.reset_axes_view(ax)

    def _start_pan(self, ax, event) -> None:
        self._interactions.on_click(event)

    @staticmethod
    def _pan_axis_limits(limits, scale: str, start_data: float, current_data: float) -> tuple[float, float]:
        return AxesInteractionController.pan_axis_limits(limits, scale, start_data, current_data)

    def _on_canvas_scroll(self, event) -> None:
        self._interactions.on_scroll(event)

    def _on_canvas_motion(self, event) -> None:
        self._interactions.on_motion(event)

    def _on_canvas_release(self, _event) -> None:
        self._interactions.on_release(_event)
    
    def plot_distribution(self):
        """Plot grain size distribution"""
        if self.display_mode == "overlay":
            ax = self.figure.add_subplot(1, 1, 1)
            if self._use_group_breakdown():
                self.plot_distribution_overlay_groups(ax)
            else:
                self.plot_distribution_overlay(ax)
        else:  # grid mode
            self.plot_distribution_grid()

    def plot_distribution_overlay(self, ax):
        """Plot all distributions on single axes via shared renderer."""
        linestyles, markers = self._effective_dataset_plot_styles()
        render_distribution_overlay(
            ax, self.datasets,
            colors=self._effective_dataset_colors(),
            linestyles=linestyles,
            markers=markers,
            style=self.current_style,
            show_grid=self.show_grid,
            show_legend=self.show_legend,
        )

    def plot_distribution_overlay_groups(self, ax):
        """Overlay one aggregate curve + spread band + faint members per group."""
        render_distribution_groups(
            ax, self._distribution_units(),
            style=self.current_style,
            show_grid=self.show_grid,
            show_legend=self.show_legend,
            title="Grain Size Distribution by Group",
        )

    def plot_distribution_grid(self):
        """Plot distributions in a grid — one panel per dataset or per group."""
        units = self._distribution_units()
        rows, cols, shown, hidden = self._facet_dims(len(units))

        for i, unit in enumerate(units[:shown]):
            ax = self.figure.add_subplot(rows, cols, i + 1)
            render_distribution_groups(
                ax, [unit],
                style=self.current_style,
                show_grid=self.show_grid,
                show_legend=False,
                title=unit["label"],
            )
            ax.title.set_fontsize(9)
            ax.set_xlabel('Size (mm)', fontsize=8)
            ax.set_ylabel('% Passing', fontsize=8)
            ax.tick_params(labelsize=7)
        self._draw_facet_overflow_note(hidden)

    def plot_k_values(self):
        """Plot K-values comparison"""
        if not self.k_results_dict:
            self.show_empty_state("No K-values calculated")
            return

        if self.display_mode == "overlay":
            self.plot_k_values_overlay()
        else:  # grid
            self.plot_k_values_grid()
    
    def plot_k_values_overlay(self):
        """Plot K-values as grouped bars via shared renderer.

        When dataset groups exist, each named group collapses to a single
        geometric-mean bar series (one bar per group per method) so same-group
        members no longer render as indistinguishable same-colour bars.
        """
        ax = self.figure.add_subplot(1, 1, 1)

        if self._use_group_breakdown():
            results_m_s, colors, flagged = self._group_overlay_inputs()
            display = {
                name: self._convert_k_dict(k_dict)
                for name, k_dict in results_m_s.items()
            }
            render_k_overlay(
                ax, display,
                flagged_methods_dict=flagged,
                colors=colors,
                style=self.current_style,
                show_grid=self.show_grid,
                show_legend=self.show_legend,
                show_value_labels=True,
                log_y_scale=self.log_k_y_scale,
                y_label=f"K ({self._unit_symbol()})",
                title="Hydraulic Conductivity by Group (geometric mean)",
            )
            return

        render_k_overlay(
            ax, self._display_k_results_dict(),
            flagged_methods_dict=self.flagged_methods_dict,
            colors=self._effective_dataset_colors(),
            style=self.current_style,
            show_grid=self.show_grid,
            show_legend=self.show_legend,
            show_value_labels=True,
            log_y_scale=self.log_k_y_scale,
            y_label=f"K ({self._unit_symbol()})",
        )

    def plot_k_values_grid(self):
        """Plot K-values in a grid — one panel per dataset or per group."""
        display, flagged_by_scope = self._k_grid_units()
        rows, cols, shown, hidden = self._facet_dims(len(display))

        for i, (name, k_dict) in enumerate(display.items()):
            if i >= shown:
                break

            ax = self.figure.add_subplot(rows, cols, i + 1)

            methods = self._ordered_methods(k_dict.keys())
            values = [k_dict[m] for m in methods]
            colors = [self.method_colors.get(m, '#888888') for m in methods]
            flagged_methods = flagged_by_scope.get(name, set())
            
            bars = ax.bar(range(len(methods)), values, color=colors, 
                         alpha=0.8, edgecolor='black', linewidth=0.5)
            ax.set_axisbelow(True)
            for bar, method, color in zip(bars, methods, colors):
                self._style_k_bar(bar, color, method in flagged_methods)
            
            ax.set_title(name, fontsize=9, fontweight='bold')
            ax.set_xlabel('Method', fontsize=8)
            ax.set_ylabel(f"K ({self._unit_symbol()})", fontsize=8)
            ax.set_xticks(range(len(methods)))
            ax.set_xticklabels(
                [format_method_label(method, tiny=True) for method in methods],
                rotation=45,
                ha='right',
                fontsize=6,
            )
            if self.log_k_y_scale:
                apply_log_bar_limits(ax, values)
            else:
                apply_linear_bar_limits(ax, values)
            ax.tick_params(labelsize=7)

            if self.show_grid:
                ax.grid(True, axis='y', alpha=0.3)
        self._draw_facet_overflow_note(hidden)

    def plot_k_distribution(self):
        """Plot aggregate/group empirical distribution functions for K."""
        if not self._comparison_snapshot or not self._comparison_snapshot.k.included_records:
            self.show_empty_state("No K-values available for K distribution")
            return

        scopes = self._k_distribution_scopes()
        if not scopes:
            self.show_empty_state("No positive K-values available for K distribution")
            return

        ax = self.figure.add_subplot(1, 1, 1)
        if self.k_dist_view == "histogram":
            if self._use_group_breakdown():
                hist_scopes = [s for s in scopes if not s.get("is_overall")] or scopes
            else:
                hist_scopes = [s for s in scopes if s.get("is_overall")] or scopes
            render_k_histogram(
                ax,
                hist_scopes,
                axis=self.k_hist_axis,
                bins=self.k_hist_bins,
                unit_symbol=self._unit_symbol(),
                style=self.current_style,
                show_grid=self.show_grid,
                show_legend=self.show_legend,
                title="K Distribution (lognormal)",
            )
            return

        render_k_distribution_function(
            ax,
            scopes,
            style=self.current_style,
            show_grid=self.show_grid,
            show_legend=self.show_legend,
            x_label=self._k_axis_label(),
            title="K Distribution Function",
        )

    def _k_distribution_scopes(self) -> list[dict]:
        snapshot = self._comparison_snapshot
        if snapshot is None:
            return []

        records = [
            record for record in snapshot.k.included_records
            if record.positive_value is not None
        ]
        if not records:
            return []

        scopes: list[dict] = [{
            "label": "Overall",
            "values": [self._convert_k_value(record.positive_value) for record in records],
            "color": "#3d4a1f",
            "linestyle": "-",
            "is_overall": True,
        }]

        named_groups = [
            group for group in snapshot.k.group_names
            if group and group != UNGROUPED_LABEL
        ]
        for index, group_name in enumerate(named_groups):
            values = [
                self._convert_k_value(record.positive_value)
                for record in records
                if record.group_name == group_name and record.positive_value is not None
            ]
            if not values:
                continue
            scopes.append({
                "label": group_name,
                "values": values,
                "color": self._group_color_map.get(
                    group_name,
                    self.dataset_colors[index % len(self.dataset_colors)],
                ),
                "linestyle": "-",
                "is_overall": False,
            })
        return scopes
    
    def plot_combined(self):
        """Plot combined distribution + K view, faceted per dataset or per group."""
        facets = self._combined_facets()
        rows, cols, shown, hidden = self._facet_dims(len(facets))

        for i, facet in enumerate(facets[:shown]):
            ax1 = self.figure.add_subplot(rows, cols * 2, i * 2 + 1)
            ax2 = self.figure.add_subplot(rows, cols * 2, i * 2 + 2)

            # Left — distribution (aggregate + band + faint members for groups).
            render_distribution_groups(
                ax1,
                [{"label": facet["label"], "color": facet["color"], "members": facet["members"]}],
                style=self.current_style,
                show_grid=self.show_grid,
                show_legend=False,
                title=f'{facet["label"]} - Dist',
            )
            ax1.title.set_fontsize(8)
            ax1.set_xlabel('Size (mm)', fontsize=7)
            ax1.set_ylabel('% Pass', fontsize=7)
            ax1.tick_params(labelsize=6)

            # Right — K-values (group geo-mean or per-dataset).
            k_dict = self._convert_k_dict(facet["k"])
            if k_dict:
                methods = self._ordered_methods(k_dict.keys())[:5]  # cap for space
                values = [k_dict[m] for m in methods]
                flagged_methods = facet["flagged"]

                bars = ax2.bar(range(len(methods)), values, alpha=0.8)
                ax2.set_axisbelow(True)
                for bar, method in zip(bars, methods):
                    self._style_k_bar(
                        bar, self.method_colors.get(method, '#888888'),
                        method in flagged_methods,
                    )
                ax2.set_title(f'{facet["label"]} - K', fontsize=8)
                ax2.set_xticks(range(len(methods)))
                ax2.set_xticklabels(
                    [format_method_label(method, tiny=True) for method in methods],
                    rotation=45,
                    fontsize=6,
                )
                ax2.set_ylabel(f"K ({self._unit_symbol()})", fontsize=7)
                if self.log_k_y_scale:
                    apply_log_bar_limits(ax2, values)
                else:
                    apply_linear_bar_limits(ax2, values)
                ax2.tick_params(labelsize=6)
                if self.show_grid:
                    ax2.grid(True, axis='y', alpha=0.3)
            else:
                ax2.text(0.5, 0.5, 'No K-values', transform=ax2.transAxes,
                        ha='center', va='center', fontsize=8)
                ax2.set_xticks([])
                ax2.set_yticks([])
        self._draw_facet_overflow_note(hidden)

    def plot_histogram(self):
        """Plot grain histogram, faceted per dataset or per group (mean retained)."""
        units = self._histogram_units()
        rows, cols, shown, hidden = self._facet_dims(len(units))

        for i, unit in enumerate(units[:shown]):
            ax = self.figure.add_subplot(rows, cols, i + 1)
            sizes, freq = unit["sizes"], unit["freq"]

            ax.bar(range(len(sizes)), freq, color=unit["color"], alpha=0.8)

            ax.set_title(unit["label"], fontsize=9, fontweight='bold')
            ax.set_xlabel('Size class', fontsize=8)
            ax.set_ylabel('Weight (%)', fontsize=8)
            if len(sizes):
                step = max(1, len(sizes) // 5)
                ax.set_xticks(range(0, len(sizes), step))
                ax.set_xticklabels(
                    [f'{s:.2f}' for s in sizes[::step]],
                    rotation=45, ha='right', fontsize=6,
                )
            ax.tick_params(labelsize=7)

            if self.show_grid:
                ax.grid(True, axis='y', alpha=0.3)
        self._draw_facet_overflow_note(hidden)

    def show_empty_state(self, message: str = "No datasets to compare"):
        """Show empty state message"""
        self.figure.clear()
        ax = self.figure.add_subplot(1, 1, 1)
        self._set_current_ax(ax)
        ax.text(0.5, 0.5, message, transform=ax.transAxes,
               ha='center', va='center', fontsize=12, color='gray')
        ax.set_xticks([])
        ax.set_yticks([])
        self._capture_default_limits()
        self._apply_active_axes_styling()
        if hasattr(self, "_drawer_table"):
            self._set_drawer_rows("Plot data", ["Status"], [(message,)])
        self.canvas.draw()

    def _refresh_drawer(self) -> None:
        snapshot = self._comparison_snapshot
        if snapshot is None:
            self._set_drawer_rows("Plot data", ["Status"], [("No datasets to compare",)])
            return

        if self.current_plot_type == "k-distribution":
            headers, rows = self._k_scope_drawer_rows()
            self._set_drawer_rows("K distribution summary - OK only", headers, rows)
        elif self.current_plot_type == "k-values":
            headers, rows = self._k_method_drawer_rows()
            self._set_drawer_rows("K method summary - OK only", headers, rows)
        elif self.current_plot_type == "distribution":
            headers, rows = self._distribution_drawer_rows()
            self._set_drawer_rows("Distribution curve data", headers, rows)
        elif self.current_plot_type == "histogram":
            headers, rows = self._histogram_drawer_rows()
            self._set_drawer_rows("Histogram size-class data", headers, rows)
        else:
            headers, rows = self._grain_drawer_rows()
            self._set_drawer_rows("Grain summary", headers, rows)

    def _set_drawer_rows(self, title: str, headers: list[str], rows: list[tuple]) -> None:
        self._drawer_title_text = title
        self._drawer_headers = list(headers)
        self._drawer_rows = [tuple(row) for row in rows]
        self._drawer_title.setText(title)
        self._drawer_count.setText(f"{len(rows)} rows" if rows else "No rows")
        self._drawer_table.clear()
        self._drawer_table.setColumnCount(len(headers))
        self._drawer_table.setRowCount(len(rows))
        self._drawer_table.setHorizontalHeaderLabels(headers)

        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                if col_index > 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._drawer_table.setItem(row_index, col_index, item)
            self._drawer_table.setRowHeight(row_index, 24)

        self._drawer_table.resizeColumnsToContents()
        self._drawer_table.verticalHeader().setDefaultSectionSize(24)

    @staticmethod
    def _with_extension(file_path: str, extension: str) -> str:
        suffix = f".{extension.lower().lstrip('.')}"
        return file_path if file_path.lower().endswith(suffix) else f"{file_path}{suffix}"

    def _export_drawer_data(self) -> None:
        self._refresh_drawer()
        title = self._drawer_title_text or "Plot data"
        safe_title = "".join(
            ch if ch.isalnum() else "_" for ch in title.lower()
        ).strip("_") or "plot_data"
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {title} as CSV",
            f"comparison_{safe_title}.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        try:
            import csv
            path = self._with_extension(path, "csv")
            with open(path, "w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(self._drawer_headers)
                writer.writerows(self._drawer_rows)
            QMessageBox.information(
                self, "Export Successful", f"{title} exported to:\n{path}"
            )
        except Exception as exc:  # pragma: no cover - user-facing dialog
            QMessageBox.warning(self, "Export failed", str(exc))

    def _grain_drawer_rows(self) -> tuple[list[str], list[tuple]]:
        grain = self._comparison_snapshot.grain
        headers = [
            "Scope", "Datasets", "D50", "Mean size", "Cu", "Fines", "Class",
        ]
        rows: list[tuple] = []

        def add_row(label: str, stats) -> None:
            rows.append((
                label,
                str(stats.dataset_count),
                self._fmt_mm(self._grain_metric(stats, "D50", "median")),
                self._fmt_mm(self._grain_metric(stats, "Dmean", "arithmetic_mean")),
                self._fmt_number(self._grain_metric(stats, "Cu", "median"), decimals=2),
                self._fmt_percent(self._grain_metric(stats, "Fines%", "median")),
                stats.dominant_class,
            ))

        add_row("Overall", grain.overall)
        for group_name in grain.group_names:
            if group_name in grain.by_group and group_name != UNGROUPED_LABEL:
                add_row(group_name, grain.by_group[group_name])
        for dataset_name in grain.dataset_names:
            if dataset_name in grain.by_dataset:
                add_row(dataset_name, grain.by_dataset[dataset_name])
        return headers, rows

    def _distribution_drawer_rows(self) -> tuple[list[str], list[tuple]]:
        headers = ["Dataset", "Particle size (mm)", "Percent passing (%)"]
        rows: list[tuple] = []
        for dataset in self.datasets:
            for size, passing in zip(dataset.particle_sizes, dataset.percent_passing):
                rows.append((
                    dataset.sample_name,
                    self._fmt_number(size, decimals=6),
                    self._fmt_number(passing, decimals=4),
                ))
        return headers, rows

    def _histogram_drawer_rows(self) -> tuple[list[str], list[tuple]]:
        headers = ["Dataset", "Size class", "Particle size (mm)", "Weight (%)"]
        rows: list[tuple] = []
        for dataset in self.datasets:
            sizes, weights = self._calculate_histogram_frequencies(
                dataset.particle_sizes,
                dataset.percent_passing,
            )
            for index, (size, weight) in enumerate(zip(sizes, weights), start=1):
                rows.append((
                    dataset.sample_name,
                    str(index),
                    self._fmt_number(size, decimals=6),
                    self._fmt_number(weight, decimals=4),
                ))
        return headers, rows

    def _k_scope_drawer_rows(self) -> tuple[list[str], list[tuple]]:
        k_report = self._comparison_snapshot.k
        unit = self._unit_symbol()
        headers = [
            "Scope", "Datasets", f"Kgeo ({unit})", f"Arithmetic ({unit})", f"Median ({unit})",
            "sigma lnK", "Var lnK", "Included", "Warnings",
        ]
        rows: list[tuple] = []

        def add_row(label: str, stats) -> None:
            rows.append((
                label,
                str(stats.dataset_count),
                self._fmt_k(stats.geometric_mean_m_s),
                self._fmt_k(stats.arithmetic_mean_m_s),
                self._fmt_k(stats.median_m_s),
                self._fmt_number(stats.ln_std_dev, decimals=2),
                self._fmt_number(stats.ln_variance, decimals=2),
                f"{stats.included_count} / {stats.total_cells}",
                str(stats.warning_count),
            ))

        add_row("Overall", k_report.overall)
        for group_name in k_report.group_names:
            if group_name in k_report.by_group and group_name != UNGROUPED_LABEL:
                add_row(group_name, k_report.by_group[group_name])
        return headers, rows

    def _k_method_drawer_rows(self) -> tuple[list[str], list[tuple]]:
        k_report = self._comparison_snapshot.k
        unit = self._unit_symbol()
        headers = [
            "Method", "Included", "OK", "Warnings", f"Kgeo ({unit})", f"Median ({unit})", f"Range ({unit})",
        ]
        rows: list[tuple] = []
        for method_name in self._ordered_methods(k_report.by_method.keys()):
            stats = k_report.by_method[method_name]
            rows.append((
                method_name,
                f"{stats.included_count} / {stats.total_cells}",
                str(stats.ok_count),
                str(stats.warning_count),
                self._fmt_k(stats.geometric_mean_m_s),
                self._fmt_k(stats.median_m_s),
                self._fmt_range(stats.min_m_s, stats.max_m_s),
            ))
        return headers, rows

    @staticmethod
    def _grain_metric(stats, metric_name: str, attr_name: str) -> Optional[float]:
        metric = stats.metrics.get(metric_name) if stats else None
        return getattr(metric, attr_name, None) if metric else None

    @staticmethod
    def _fmt_number(value: Optional[float], *, decimals: int = 2) -> str:
        if value is None:
            return "-"
        return f"{float(value):.{decimals}f}"

    @staticmethod
    def _fmt_mm(value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"{float(value):.3g} mm"

    @staticmethod
    def _fmt_percent(value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"{float(value):.1f}%"

    def _fmt_k(self, value: Optional[float]) -> str:
        if value is None:
            return "-"
        converted = self._convert_k_value(value)
        if converted is None:
            return "-"
        return HydraulicConductivityConverter.DISPLAY_FORMATS[self.display_unit].format(converted)

    def _fmt_range(self, low: Optional[float], high: Optional[float]) -> str:
        if low is None or high is None:
            return "-"
        return f"{self._fmt_k(low)} - {self._fmt_k(high)}"
    
    def zoom_in(self):
        """Zoom in on the active axes."""
        for ax in self._zoom_target_axes():
            ax.set_xlim(*self._zoom_axis_limits(ax.get_xlim(), ax.get_xscale(), 0.8))
            ax.set_ylim(*self._zoom_axis_limits(ax.get_ylim(), ax.get_yscale(), 0.8))
        
        self.canvas.draw()
    
    def zoom_out(self):
        """Zoom out on the active axes."""
        for ax in self._zoom_target_axes():
            ax.set_xlim(*self._zoom_axis_limits(ax.get_xlim(), ax.get_xscale(), 1.2))
            ax.set_ylim(*self._zoom_axis_limits(ax.get_ylim(), ax.get_yscale(), 1.2))
        
        self.canvas.draw()
    
    def reset_view(self):
        """Reset the active subplot, or rebuild defaults when no subplot is active."""
        targets = self._zoom_target_axes()
        if not targets:
            self.refresh_plot()
            return
        for ax in targets:
            self._reset_axes_view(ax)
        self.canvas.draw()
