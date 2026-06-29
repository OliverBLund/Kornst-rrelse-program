"""
Enhanced plot widget for comparison tab with multiple display modes
"""

import dataclasses
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton,
    QComboBox, QLabel, QButtonGroup, QSizePolicy, QScrollArea,
    QColorDialog, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFontMetrics
from matplotlib.figure import Figure
import numpy as np
from typing import List, Dict, Optional
from .collapsible_section import CollapsibleSection
from .matplotlib_canvas import FigureCanvas
from .plot_interactions import AxesInteractionController
from .plot_constants import METHOD_COLORS, DATASET_COLORS, DEFAULT_METHOD_ORDER, ordered_methods
from .plot_renderers import (
    _distribution_limits,
    _interp_passing_on_grid,
    apply_legend_aware_layout,
)
from .plot_styles import PlotStyle, PROFESSIONAL_STYLE, get_style, get_available_style_names
from . import comparison_plot_spec as cps
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
    set_dataset_line_style,
    set_group_color,
)
from .theme import C, SZ, apply_matplotlib_style, icon
from analysis.comparison_snapshot import ComparisonSnapshotOptions, build_comparison_snapshot
from grain_classification import ISO14688
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
    # Fixed height (px) given to each grid row; the canvas scroll area scrolls
    # when the total exceeds the viewport instead of squishing the subplots.
    GRID_ROW_HEIGHT = 260
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Plot settings
        self.current_plot_type = "distribution"
        self.display_mode = "overlay"  # overlay, grid, grouped
        # Render-only breakdown: "dataset" vs "group". Defaults to "group" when
        # the loaded datasets carry named groups (set in set_datasets). Group
        # membership itself is owned by the Scope & Groups dialog, not here.
        self.breakdown = "dataset"
        # K Distribution sub-view: "histogram" (Poul's lognormal PDF, default) or
        # "cdf" (empirical CDF + lognormal fit). Histogram x-axis: "k" or "lnk".
        # Histogram bins: "auto" / "off" / a digit string ("5".."30").
        # y-mode: "frequency" (per-bin counts, default) or "density".
        # show_n: count labels atop bars; drop_empty: collapse all-empty bins.
        self.k_dist_view = "histogram"
        self.k_hist_axis = "lnk"
        self.k_hist_bins = "auto"
        self.k_hist_y_mode = "frequency"
        self.k_hist_show_n = True
        self.k_hist_drop_empty = True
        self.grid_layout = (2, 2)  # Default grid size
        self.show_grid = True
        self.show_legend = True
        self.sidebar_visible = False
        self.display_unit: HydraulicConductivityUnit = get_default_plot_unit()
        self.log_k_y_scale = False
        self.k_group_aggregation = "geometric"
        self._scheme = ISO14688

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

        # Scrollable viewport: grid layouts grow tall (a fixed height per row)
        # and scroll, instead of squishing every subplot into the visible area.
        self._canvas_scroll = QScrollArea()
        self._canvas_scroll.setObjectName("cmp-canvas-scroll")
        self._canvas_scroll.setWidgetResizable(True)
        self._canvas_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._canvas_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._canvas_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._canvas_scroll.setStyleSheet("background: transparent;")
        self._canvas_scroll.setWidget(self.canvas)
        chart_lay.addWidget(self._canvas_scroll, 1)

        self._drawer = self._build_data_drawer()
        chart_lay.addWidget(self._drawer, 0)

        # Interaction hint — a slim footer under the plot, not in the toolbar.
        self._interaction_hint = QLabel(
            "<b>Plot controls:</b> Wheel zoom  ·  Shift-drag pan  ·  Double-click reset"
        )
        self._interaction_hint.setObjectName("cmp-interaction-hint")
        self._interaction_hint.setTextFormat(Qt.TextFormat.RichText)
        self._interaction_hint.setStyleSheet(
            "color: #8a816f; font-size: 10px; padding: 2px 8px; background: transparent;"
        )
        self._interaction_hint.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        chart_lay.addWidget(self._interaction_hint, 0)

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

        # NOTE: the interaction hint moved out of the toolbar into a slim footer
        # below the plot (see init_ui) so it no longer competes for toolbar space.

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
            "Chart", ["Lognormal histogram", "Empirical CDF"])
        self._kdist_view_combo.currentIndexChanged.connect(
            lambda idx: self._on_kdist_view_changed("cdf" if idx == 1 else "histogram"))
        self._row_kdist_view.setToolTip(
            "K is pooled across the comparison scope.\n"
            "Per dataset = one pooled (Overall) distribution; "
            "Per group = one distribution per group."
        )
        self._sect_kdist.add_widget(self._row_kdist_view)

        self._row_kdist_yaxis, self._kdist_yaxis_combo = make_combo_row(
            "Histogram y-axis", ["Frequency (count)", "Probability density"])
        self._kdist_yaxis_combo.currentIndexChanged.connect(
            lambda idx: self._on_kdist_ymode_changed("density" if idx == 1 else "frequency"))
        self._row_kdist_yaxis.setToolTip(
            "Frequency counts how many K-values fall in each bin (default); "
            "Probability density normalises so the fitted lognormal integrates to 1."
        )
        self._sect_kdist.add_widget(self._row_kdist_yaxis)

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

        self._row_kdist_dropempty, self._sw_kdist_dropempty = make_toggle_row(
            "Drop empty bins", self.k_hist_drop_empty)
        self._sw_kdist_dropempty.toggled.connect(self._on_kdist_drop_empty_toggled)
        self._row_kdist_dropempty.setToolTip(
            "Collapse all-empty interior bins so populated bars sit adjacent "
            "(no gaps). Turn off to keep the true K axis with the fitted curve."
        )
        self._sect_kdist.add_widget(self._row_kdist_dropempty)

        self._row_kdist_shown, self._sw_kdist_shown = make_toggle_row(
            "Show N labels", self.k_hist_show_n)
        self._sw_kdist_shown.toggled.connect(self._on_kdist_show_n_toggled)
        self._row_kdist_shown.setToolTip("Print the sample count above each bar.")
        self._sect_kdist.add_widget(self._row_kdist_shown)

        self._sect_kdist.setVisible(False)
        lay.addWidget(self._sect_kdist)

        # K-Value Aggregation
        self._sect_k_group_agg = CollapsibleSection(
            "K-Value Aggregation", "fa6s.calculator",
            CollapsibleSection.EARTH, expanded=True,
        )
        self._row_k_group_agg, self._k_group_agg_combo = make_combo_row(
            "Group method bars", ["Geo. mean", "Arith. mean"])
        self._k_group_agg_combo.currentIndexChanged.connect(
            self._on_k_group_aggregation_changed)
        self._row_k_group_agg.setToolTip(
            "Controls how grouped K-value method bars summarize datasets "
            "inside each group."
        )
        self._sect_k_group_agg.add_widget(self._row_k_group_agg)
        self._sect_k_group_agg.setVisible(False)
        lay.addWidget(self._sect_k_group_agg)

        # Series Appearance
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

    def _on_k_group_aggregation_changed(self, index: int) -> None:
        mode = "arithmetic" if index == 1 else "geometric"
        if self.k_group_aggregation == mode:
            return
        self.k_group_aggregation = mode
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

    # ── Comparison "what to draw" helpers ───────────────────────────
    # The orchestration itself lives in gui/comparison_plot_spec.py (shared by
    # the GUI, reports and exports). These thin wrappers build a spec from the
    # live widget state so external callers/tests keep a stable surface.

    def _group_overlay_inputs(
        self,
    ) -> tuple[Dict[str, Dict[str, float]], List[str], Dict[str, set]]:
        """Per-group method-mean K aggregates for the K-Values overlay (in m/s)."""
        return cps.group_overlay_inputs(self._build_spec())

    def _histogram_units(self) -> list[dict]:
        """Faceting units for the grain histogram (per dataset or per group)."""
        return cps.histogram_units(self._build_spec())

    def _combined_facets(self) -> list[dict]:
        """Faceting units for the combined view: distribution + K per unit."""
        return cps.combined_facets(self._build_spec())

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
        self._sync_contextual_sidebar_sections()
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

    def _on_kdist_ymode_changed(self, mode: str) -> None:
        if self.k_hist_y_mode == mode:
            return
        self.k_hist_y_mode = mode
        self.refresh_plot()

    def _on_kdist_show_n_toggled(self, checked: bool) -> None:
        if self.k_hist_show_n == checked:
            return
        self.k_hist_show_n = checked
        self.refresh_plot()

    def _on_kdist_drop_empty_toggled(self, checked: bool) -> None:
        if self.k_hist_drop_empty == checked:
            return
        self.k_hist_drop_empty = checked
        self.refresh_plot()

    def _sync_kdist_controls(self) -> None:
        """Show K-distribution chart/axis sidebar rows only for that plot type."""
        if not hasattr(self, "_sect_kdist"):
            return
        is_kdist = self.current_plot_type == "k-distribution"
        self._sect_kdist.setVisible(is_kdist)
        # The histogram-only rows (y-axis, x-axis, bins, drop-empty, N labels)
        # are meaningless for the empirical-CDF view.
        histogram = is_kdist and self.k_dist_view == "histogram"
        for attr in (
            "_row_kdist_yaxis", "_row_kdist_axis", "_row_kdist_bins",
            "_row_kdist_dropempty", "_row_kdist_shown",
        ):
            row = getattr(self, attr, None)
            if row is not None:
                row.setVisible(histogram)

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
        """Return ``(rows, cols, shown, hidden)`` fitting *count* faceted panels."""
        return cps.facet_dims(self._build_spec(), count)

    def _grow_canvas_for_rows(self, rows: int) -> None:
        """Give each grid row a fixed height so the scroll area scrolls when the
        total exceeds the viewport, rather than squishing every subplot."""
        if hasattr(self, "canvas"):
            self.canvas.setMinimumHeight(max(1, rows) * self.GRID_ROW_HEIGHT)

    def _reset_canvas_height(self) -> None:
        """Let the canvas fill the viewport (single/overlay plots, no scroll)."""
        if hasattr(self, "canvas"):
            self.canvas.setMinimumHeight(220)

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
        show_group_agg = (
            self.current_plot_type in {"k-values", "combined"}
            and self._use_group_breakdown()
        )
        if hasattr(self, "_sect_k_group_agg"):
            self._sect_k_group_agg.setVisible(show_group_agg)
        if hasattr(self, "_row_k_group_agg"):
            self._row_k_group_agg.setVisible(show_group_agg)

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

    def _convert_k_value(self, value_m_s: Optional[float]) -> Optional[float]:
        if value_m_s is None:
            return None
        return HydraulicConductivityConverter.convert_from_m_per_s(
            value_m_s, self.display_unit
        )

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


    def set_scheme(self, scheme) -> None:
        """Set the classification scheme used by grain-size histograms."""
        self._scheme = scheme or ISO14688

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
                ),
                classification_scheme=self._scheme,
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
        self._sync_contextual_sidebar_sections()
        self._rebuild_dataset_color_rows()

    def _build_spec(self) -> cps.ComparisonPlotSpec:
        """Capture the live, resolved plot state into a widget-free render spec.

        All Qt/``group_styles``/``QSettings`` lookups happen here so the shared
        ``render_comparison`` pipeline (GUI + reports + exports) is a pure
        function of the returned spec.
        """
        colors = self._effective_dataset_colors()
        color_by_name = {
            ds.sample_name: colors[i] for i, ds in enumerate(self.datasets)
        }
        return cps.ComparisonPlotSpec(
            datasets=list(self.datasets),
            k_results_dict=self.k_results_dict,
            flagged_methods_dict=self.flagged_methods_dict,
            comparison_snapshot=self._comparison_snapshot,
            current_plot_type=self.current_plot_type,
            display_mode=self.display_mode,
            use_group_breakdown=self._use_group_breakdown(),
            grid_cols=self.grid_layout[1],
            max_facet_panels=self.MAX_FACET_PANELS,
            dataset_groups=dict(self._dataset_groups),
            group_color_map=dict(self._group_color_map),
            effective_colors=colors,
            color_by_name=color_by_name,
            dataset_linestyles={
                ds.sample_name: self._dataset_linestyles.get(ds.sample_name, "-")
                for ds in self.datasets
            },
            palette=list(self.dataset_colors),
            known_dataset_order=list(self._known_dataset_order),
            known_group_order=list(self._known_group_order),
            known_dataset_group=dict(self._known_dataset_group),
            style=self.current_style,
            show_grid=self.show_grid,
            show_legend=self.show_legend,
            log_k_y_scale=self.log_k_y_scale,
            display_unit=self.display_unit,
            k_group_aggregation=self.k_group_aggregation,
            classification_scheme=self._scheme,
            k_dist_view=self.k_dist_view,
            k_hist_axis=self.k_hist_axis,
            k_hist_bins=self.k_hist_bins,
            k_hist_y_mode=self.k_hist_y_mode,
            k_hist_show_n=self.k_hist_show_n,
            k_hist_drop_empty=self.k_hist_drop_empty,
        )

    def refresh_plot(self):
        """Refresh the plot based on current settings"""
        if not self.datasets:
            self.show_empty_state()
            return

        # Default to a viewport-filling canvas; grid plots grow it per row.
        self._reset_canvas_height()

        # The shared spec pipeline owns the figure drawing; the widget keeps the
        # interactions, drawer, sidebar and canvas height around it.
        rows_used = cps.render_comparison(self.figure, self._build_spec())
        if rows_used:
            self._grow_canvas_for_rows(rows_used)

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

        spec = self._build_spec()
        if self.current_plot_type == "k-distribution":
            title, headers, rows = self._k_distribution_drawer_rows(spec)
        elif self.current_plot_type == "k-values":
            title, headers, rows = self._k_values_drawer_rows(spec)
        elif self.current_plot_type == "distribution":
            title, headers, rows = self._distribution_drawer_rows(spec)
        elif self.current_plot_type == "histogram":
            title, headers, rows = self._histogram_drawer_rows(spec)
        elif self.current_plot_type == "combined":
            title, headers, rows = self._combined_drawer_rows(spec)
        else:
            headers, rows = self._grain_drawer_rows()
            title = "Grain summary"
        self._set_drawer_rows(title, headers, rows)

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

    def _distribution_drawer_rows(self, spec: cps.ComparisonPlotSpec) -> tuple[str, list[str], list[tuple]]:
        if spec.display_mode == "overlay" and not spec.use_group_breakdown:
            headers, rows = self._raw_distribution_drawer_rows()
            return "Distribution curve data", headers, rows

        units = self._shown_plot_units(spec, self._named_distribution_units(spec))
        axis_indices = list(range(len(units))) if spec.display_mode == "grid" else [0] * len(units)
        headers, rows = self._distribution_curve_rows(units, axis_indices)
        return "Distribution plotted curve data", headers, rows

    def _raw_distribution_drawer_rows(self) -> tuple[list[str], list[tuple]]:
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

    def _histogram_drawer_rows(self, spec: cps.ComparisonPlotSpec) -> tuple[str, list[str], list[tuple]]:
        scheme_label = cps._scheme_short_name(spec.classification_scheme)
        headers = [
            "Scope",
            f"Fraction ({scheme_label})",
            "Lower size (mm)",
            "Upper size (mm)",
            "Weight (%)",
        ]
        rows: list[tuple] = []
        for unit in self._shown_plot_units(spec, cps.histogram_units(spec)):
            labels = unit.get("class_labels", [])
            lower_values = unit.get("lower", [])
            upper_values = unit.get("upper", [])
            weights = unit.get("freq", [])
            for label, lower, upper, weight in zip(
                labels,
                lower_values,
                upper_values,
                weights,
            ):
                rows.append((
                    unit.get("label", "Scope"),
                    label,
                    self._fmt_number(lower, decimals=6),
                    self._fmt_number(upper, decimals=6),
                    self._fmt_number(weight, decimals=4),
                ))
        return "Histogram classification-fraction data", headers, rows

    def _k_distribution_drawer_rows(
        self, spec: cps.ComparisonPlotSpec
    ) -> tuple[str, list[str], list[tuple]]:
        unit = self._unit_symbol()
        is_histogram = self.k_dist_view == "histogram"
        headers = ["Scope", "Dataset", "Group", "Method", f"K ({unit})", "ln K"]
        if not is_histogram:
            headers.append("CDF probability (%)")

        scope_labels = self._k_distribution_scope_labels(spec)
        rows: list[tuple] = []
        for scope_label in scope_labels:
            records = self._k_distribution_records_for_scope(scope_label)
            n = len(records)
            for index, record in enumerate(records):
                converted = self._convert_k_value(record.positive_value)
                if converted is None or converted <= 0:
                    continue
                base = (
                    scope_label,
                    record.dataset_name,
                    record.group_name,
                    record.method_name,
                    self._fmt_k(record.positive_value),
                    self._fmt_number(np.log(converted), decimals=6),
                )
                if is_histogram:
                    rows.append(base)
                else:
                    probability = ((index + 1 - 0.5) / n) * 100.0 if n else None
                    rows.append(base + (self._fmt_number(probability, decimals=4),))

        title = (
            "K distribution histogram observations - OK only"
            if is_histogram
            else "K distribution CDF points - OK only"
        )
        return title, headers, rows

    def _k_values_drawer_rows(
        self, spec: cps.ComparisonPlotSpec
    ) -> tuple[str, list[str], list[tuple]]:
        headers = [
            "Scope", "Method", f"K ({self._unit_symbol()})", "Status", "Value type",
        ]
        rows: list[tuple] = []
        k_results_m_s, flagged_by_scope, value_type_by_scope = self._plotted_k_scope_values(spec)

        for scope_name, k_dict in k_results_m_s.items():
            flagged = flagged_by_scope.get(scope_name, set())
            value_type = value_type_by_scope.get(scope_name, "Dataset value")
            for method_name in self._ordered_methods(k_dict.keys()):
                status = "Warning" if method_name in flagged else "OK"
                rows.append((
                    scope_name,
                    method_name,
                    self._fmt_k(k_dict[method_name]),
                    status,
                    value_type,
                ))
        return "K-value plotted bars", headers, rows

    def _combined_drawer_rows(
        self, spec: cps.ComparisonPlotSpec
    ) -> tuple[str, list[str], list[tuple]]:
        headers = [
            "Scope", "Panel", "Curve or method", "Particle size (mm)",
            "Percent passing (%)", f"K ({self._unit_symbol()})", "Status",
        ]
        rows: list[tuple] = []
        facets = self._shown_plot_units(spec, cps.combined_facets(spec))

        for facet_index, facet in enumerate(facets):
            _headers, dist_rows = self._distribution_curve_rows(
                [{
                    "label": facet["label"],
                    "members": self._named_members_for_facet(spec, facet["label"]),
                }],
                [facet_index * 2],
            )
            for scope, curve, size, passing in dist_rows:
                rows.append((scope, "Distribution", curve, size, passing, "", ""))

            k_dict = facet.get("k", {})
            flagged = facet.get("flagged", set())
            for method_name in self._ordered_methods(k_dict.keys())[:5]:
                rows.append((
                    facet["label"],
                    "K values",
                    method_name,
                    "",
                    "",
                    self._fmt_k(k_dict[method_name]),
                    "Warning" if method_name in flagged else "OK",
                ))

        return "Combined plotted data", headers, rows

    def _shown_plot_units(self, spec: cps.ComparisonPlotSpec, units: list[dict]) -> list[dict]:
        if spec.display_mode != "grid":
            return list(units)
        _rows, _cols, shown, _hidden = cps.facet_dims(spec, len(units))
        return list(units[:shown])

    def _named_distribution_units(self, spec: cps.ComparisonPlotSpec) -> list[dict]:
        def make_member(dataset) -> dict:
            return {
                "name": dataset.sample_name,
                "sizes": list(getattr(dataset, "particle_sizes", []) or []),
                "passing": list(getattr(dataset, "percent_passing", []) or []),
            }

        if not spec.use_group_breakdown:
            return [
                {"label": dataset.sample_name, "members": [make_member(dataset)]}
                for dataset in self.datasets
            ]

        units: list[dict] = []
        for group_name in cps.group_order(spec):
            members = [
                dataset for dataset in self.datasets
                if spec.dataset_groups.get(dataset.sample_name, UNGROUPED_LABEL) == group_name
            ]
            if group_name == UNGROUPED_LABEL:
                units.extend(
                    {"label": dataset.sample_name, "members": [make_member(dataset)]}
                    for dataset in members
                )
                continue
            units.append({
                "label": group_name,
                "members": [make_member(dataset) for dataset in members],
            })
        return units

    def _named_members_for_facet(
        self, spec: cps.ComparisonPlotSpec, label: str
    ) -> list[dict]:
        for unit in self._named_distribution_units(spec):
            if unit["label"] == label:
                return unit["members"]
        return []

    def _distribution_curve_rows(
        self, units: list[dict], axis_indices: list[int]
    ) -> tuple[list[str], list[tuple]]:
        headers = ["Scope", "Curve", "Particle size (mm)", "Percent passing (%)"]
        rows: list[tuple] = []

        for unit_index, unit in enumerate(units):
            members = unit.get("members", [])
            xlim = self._distribution_xlim_for_members(
                members,
                axis_indices[unit_index] if unit_index < len(axis_indices) else None,
            )
            if xlim is None:
                continue
            grid = np.logspace(np.log10(xlim[0]), np.log10(xlim[1]), 60)
            curves: list[tuple[str, np.ndarray]] = []
            for member in members:
                curve = _interp_passing_on_grid(
                    member.get("sizes", []),
                    member.get("passing", []),
                    grid,
                )
                if curve is not None:
                    curves.append((member.get("name", "Member"), curve))
            if not curves:
                continue

            stacked = np.vstack([curve for _name, curve in curves])
            self._append_distribution_curve_rows(
                rows,
                unit.get("label", "Scope"),
                "Aggregate" if len(curves) > 1 else "Curve",
                grid,
                np.nanmean(stacked, axis=0),
            )
            if len(curves) > 1:
                self._append_distribution_curve_rows(
                    rows,
                    unit.get("label", "Scope"),
                    "Band min",
                    grid,
                    np.nanmin(stacked, axis=0),
                )
                self._append_distribution_curve_rows(
                    rows,
                    unit.get("label", "Scope"),
                    "Band max",
                    grid,
                    np.nanmax(stacked, axis=0),
                )
                for member_name, curve in curves:
                    self._append_distribution_curve_rows(
                        rows,
                        unit.get("label", "Scope"),
                        f"Member: {member_name}",
                        grid,
                        curve,
                    )

        return headers, rows

    def _distribution_xlim_for_members(
        self, members: list[dict], axis_index: Optional[int]
    ) -> Optional[tuple[float, float]]:
        axes = list(getattr(self.figure, "axes", []) or [])
        if axis_index is not None and 0 <= axis_index < len(axes):
            lo, hi = axes[axis_index].get_xlim()
            if lo > 0 and hi > lo:
                return float(lo), float(hi)

        sizes: list[float] = []
        passing: list[float] = []
        for member in members:
            for size, pct in zip(member.get("sizes", []), member.get("passing", [])):
                if size is None or pct is None:
                    continue
                try:
                    size_f = float(size)
                    pct_f = float(pct)
                except (TypeError, ValueError):
                    continue
                if size_f > 0:
                    sizes.append(size_f)
                    passing.append(pct_f)
        if not sizes:
            return None
        lo, hi, _ymin, _ymax = _distribution_limits(sizes, passing)
        return float(lo), float(hi)

    def _append_distribution_curve_rows(
        self,
        rows: list[tuple],
        scope: str,
        curve_label: str,
        grid: np.ndarray,
        values: np.ndarray,
    ) -> None:
        for size, passing in zip(grid, values):
            rows.append((
                scope,
                curve_label,
                self._fmt_number(size, decimals=6),
                self._fmt_number(passing, decimals=4),
            ))

    def _k_distribution_scope_labels(self, spec: cps.ComparisonPlotSpec) -> list[str]:
        scopes = cps.k_distribution_scopes(spec)
        if self.k_dist_view == "histogram":
            if spec.use_group_breakdown:
                scopes = [scope for scope in scopes if not scope.get("is_overall")] or scopes
            else:
                scopes = [scope for scope in scopes if scope.get("is_overall")] or scopes
        return [scope.get("label", "Scope") for scope in scopes]

    def _k_distribution_records_for_scope(self, scope_label: str) -> list:
        records = [
            record for record in self._comparison_snapshot.k.included_records
            if record.positive_value is not None
            and (
                scope_label == "Overall"
                or record.group_name == scope_label
                or record.dataset_name == scope_label
            )
        ]
        return sorted(
            records,
            key=lambda record: self._convert_k_value(record.positive_value) or 0.0,
        )

    def _plotted_k_scope_values(
        self, spec: cps.ComparisonPlotSpec
    ) -> tuple[Dict[str, Dict[str, float]], Dict[str, set], Dict[str, str]]:
        if spec.use_group_breakdown:
            k_results_m_s, _colors, flagged = cps.group_overlay_inputs(spec)
            named_groups = {
                group for group in spec.dataset_groups.values()
                if group and group != UNGROUPED_LABEL
            }
            mean_name = (
                "arithmetic"
                if spec.k_group_aggregation == "arithmetic"
                else "geometric"
            )
            value_types = {
                scope: (
                    f"Group method {mean_name} mean (OK only)"
                    if scope in named_groups
                    else "Dataset value"
                )
                for scope in k_results_m_s
            }
            return k_results_m_s, flagged, value_types

        value_types = {scope: "Dataset value" for scope in spec.k_results_dict}
        return spec.k_results_dict, spec.flagged_methods_dict, value_types

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
