"""
Enhanced plot widget for comparison tab with multiple display modes
"""

import dataclasses
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton,
    QComboBox, QLabel, QButtonGroup, QSizePolicy, QScrollArea,
    QColorDialog, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor
from matplotlib.figure import Figure
from matplotlib.patches import Patch
import numpy as np
from typing import List, Dict, Optional
from .collapsible_section import CollapsibleSection
from .k_plot_helpers import annotate_log_bars, apply_log_bar_limits, format_method_label
from .matplotlib_canvas import FigureCanvas
from .plot_interactions import AxesInteractionController
from .plot_constants import METHOD_COLORS, DATASET_COLORS, DEFAULT_METHOD_ORDER, ordered_methods
from .plot_renderers import (
    apply_legend_aware_layout,
    build_legend_kwargs,
    render_distribution_overlay,
    render_k_overlay,
    _style_k_bar_simple,
    _add_flagged_legend_handle,
)
from .plot_styles import PlotStyle, PROFESSIONAL_STYLE, get_style, get_available_style_names
from .sidebar_controls import (
    LEGEND_LOCATIONS as _CMP_LEGEND_LOCATIONS,
    LEGEND_LAYOUTS as _CMP_LEGEND_LAYOUTS,
    make_color_row, make_combo_row, make_dspin_row,
    make_spin_row, make_toggle_row, set_swatch_color,
)
from .theme import C, SZ, apply_matplotlib_style, icon
from k_aggregation import UNGROUPED_LABEL, dataset_group_name


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
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Plot settings
        self.current_plot_type = "distribution"
        self.display_mode = "overlay"  # overlay, grid, grouped
        self.grid_layout = (2, 2)  # Default grid size
        self.show_grid = True
        self.show_legend = True
        self.sidebar_visible = False

        # Active style — swapped by set_style(). Starts at the Professional preset
        # so the comparison view now honors the preset selector (previously it was
        # hardcoded to PROFESSIONAL_STYLE at every render call).
        self.current_style: PlotStyle = PROFESSIONAL_STYLE
        self._style_is_custom: bool = False

        # Data storage
        self.datasets = []
        self.k_results_dict = {}  # dataset_name -> k_results
        self.flagged_methods_dict = {}  # dataset_name -> set(method_name)
        self._dataset_groups: Dict[str, str] = {}
        self._group_color_map: Dict[str, str] = {}
        self._dataset_linestyles: Dict[str, str] = {}
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
        chart_lay.addWidget(self.canvas, 1)

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

        layout.addWidget(body, 1)

        # Seed sidebar style widgets with the initial preset's values.
        self._sync_sidebar_style_widgets(self.current_style)
    
    def create_toolbar(self):
        """Create the toolbar with plot controls."""
        toolbar = QWidget()
        toolbar.setObjectName("pw-toolbar")
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(4)

        plot_label = QLabel("Plot")
        plot_label.setStyleSheet("color: #6a6254;")
        row.addWidget(plot_label)

        self.plot_selector = QComboBox()
        self.plot_selector.setObjectName("pw-style-sel")
        self.plot_selector.addItems([
            "Distribution",
            "K-Values",
            "Combined",
            "Cumulative",
            "Histogram",
        ])
        self.plot_selector.setMaximumWidth(118)
        self.plot_selector.currentTextChanged.connect(self.on_plot_type_changed)
        row.addWidget(self.plot_selector)

        row.addWidget(_cmp_sep())

        mode_label = QLabel("View")
        mode_label.setStyleSheet("color: #6a6254;")
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

        self.grouped_radio = QPushButton("Grouped")
        self.grouped_radio.setProperty("pw-seg", True)
        self.grouped_radio.setProperty("active", False)
        self.grouped_radio.setCheckable(True)
        self.grouped_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.grouped_radio.toggled.connect(lambda on: _sync_cmp_seg(self.grouped_radio, on))
        self.grouped_radio.toggled.connect(lambda checked: self._on_mode_toggled(checked, "grouped"))
        self._mode_group.addButton(self.grouped_radio)
        self.grouped_radio.setVisible(False)
        mode_row.addWidget(self.grouped_radio)

        row.addWidget(mode_frame)
        row.addWidget(_cmp_sep())

        self.grid_label = QLabel("Layout")
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
        row.addWidget(style_label)

        self.style_selector = QComboBox()
        self.style_selector.setObjectName("pw-style-sel")
        self.style_selector.addItems(get_available_style_names())
        self.style_selector.setCurrentText(self.current_style.name)
        self.style_selector.setMaximumWidth(118)
        self.style_selector.setToolTip("Plot style preset")
        self.style_selector.currentTextChanged.connect(self._on_style_preset_changed)
        row.addWidget(self.style_selector)

        row.addWidget(_cmp_sep())

        self._tb_sidebar_btn = _cmp_chk(
            " Controls", "Toggle controls panel", False, "fa6s.sliders"
        )
        self._tb_sidebar_btn.clicked.connect(self._toggle_sidebar)
        row.addWidget(self._tb_sidebar_btn)

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

    def _position_toggle_handle(self) -> None:
        if not hasattr(self, "_toggle_handle") or not hasattr(self, "_chart_area"):
            return
        handle_w = 16
        handle_h = 40
        y = max(0, (self._chart_area.height() - handle_h) // 2)
        self._toggle_handle.setGeometry(0, y, handle_w, handle_h)

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
        lay.addWidget(self._sect_display)

        # ── Dataset Colors ──
        self._sect_dataset_colors = CollapsibleSection(
            "Dataset Colors", "fa6s.palette",
            CollapsibleSection.PURPLE, expanded=False,
        )
        self._color_container = QWidget()
        self._color_container_lay = QVBoxLayout(self._color_container)
        self._color_container_lay.setContentsMargins(0, 0, 0, 0)
        self._color_container_lay.setSpacing(0)
        self._empty_colors_hint = QLabel("  Add datasets to see per-sample colors.")
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
        return sidebar

    # ── Sidebar handlers ───────────────────────────────────────────

    def _on_sidebar_grid_toggled(self, on: bool) -> None:
        self.show_grid = on
        self.refresh_plot()

    def _on_sidebar_legend_toggled(self, on: bool) -> None:
        self.show_legend = on
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
        """Refresh the Dataset Colors section when datasets change."""
        if not hasattr(self, '_color_container_lay'):
            return
        while self._color_container_lay.count():
            item = self._color_container_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._dataset_color_rows.clear()

        if not self.datasets:
            self._color_container_lay.addWidget(self._empty_colors_hint)
            self._empty_colors_hint.show()
            return

        self._empty_colors_hint.hide()
        for i, ds in enumerate(self.datasets):
            color = self._effective_color_for(ds.sample_name, i)
            row, dot = make_color_row(ds.sample_name, color)
            dot.mousePressEvent = (
                lambda _event, name=ds.sample_name, swatch=dot:
                self._pick_dataset_color(name, swatch)
            )
            self._color_container_lay.addWidget(row)
            self._dataset_color_rows[ds.sample_name] = dot

    def _effective_color_for(self, sample_name: str, index: int) -> str:
        override = self._dataset_color_overrides.get(sample_name)
        if override:
            return override
        group_name = self._dataset_groups.get(sample_name, UNGROUPED_LABEL)
        if group_name != UNGROUPED_LABEL and group_name in self._group_color_map:
            return self._group_color_map[group_name]
        return self.dataset_colors[index % len(self.dataset_colors)]

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

    def _rebuild_group_style_maps(self) -> None:
        line_cycle = ["-", "--", ":", "-."]
        group_order: list[str] = []
        group_member_counts: dict[str, int] = {}
        self._dataset_groups = {}
        self._group_color_map = {}
        self._dataset_linestyles = {}

        for dataset in self.datasets:
            group_name = dataset_group_name(dataset)
            self._dataset_groups[dataset.sample_name] = group_name
            if group_name != UNGROUPED_LABEL and group_name not in group_order:
                group_order.append(group_name)

        self._group_color_map = {
            group_name: self.dataset_colors[i % len(self.dataset_colors)]
            for i, group_name in enumerate(group_order)
        }

        for i, dataset in enumerate(self.datasets):
            group_name = self._dataset_groups.get(dataset.sample_name, UNGROUPED_LABEL)
            if group_name == UNGROUPED_LABEL:
                self._dataset_linestyles[dataset.sample_name] = "-"
                continue
            member_index = group_member_counts.get(group_name, 0)
            group_member_counts[group_name] = member_index + 1
            self._dataset_linestyles[dataset.sample_name] = line_cycle[member_index % len(line_cycle)]

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
            self.figure.savefig(path, dpi=200, bbox_inches="tight")
        except Exception as exc:  # pragma: no cover — user-facing dialog
            QMessageBox.warning(self, "Export failed", str(exc))

    def on_plot_type_changed(self, text: str):
        """Handle plot type change"""
        plot_map = {
            "Distribution": "distribution",
            "K-Values": "k-values",
            "Combined": "combined",
            "Cumulative": "cumulative",
            "Histogram": "histogram"
        }
        
        self.current_plot_type = plot_map.get(text, "distribution")
        self._normalize_display_mode_for_plot_type()
        self.refresh_plot()

    def _on_mode_toggled(self, checked: bool, mode: str):
        """Apply mode changes only for the newly checked radio button."""
        if checked:
            self.set_display_mode(mode)
    
    def set_display_mode(self, mode: str):
        """Set the display mode"""
        self.display_mode = mode
        self._normalize_display_mode_for_plot_type()

        # Show/hide grid selector
        show_grid_selector = (self.display_mode == "grid")
        self.grid_label.setVisible(show_grid_selector)
        self.grid_selector.setVisible(show_grid_selector)
        
        self.refresh_plot()

    def _normalize_display_mode_for_plot_type(self):
        """Keep the display mode consistent with the selected plot type."""
        supports_grouped = self.current_plot_type == "k-values"
        self.grouped_radio.setVisible(supports_grouped)

        if self.display_mode == "grouped" and not supports_grouped:
            self.display_mode = "grid" if self.current_plot_type in ["combined", "histogram"] else "overlay"

        if self.current_plot_type in ["combined", "histogram"] and self.display_mode == "overlay":
            self.display_mode = "grid"

        self._sync_mode_radios()

    def _sync_mode_radios(self):
        """Reflect the active display mode in the radio buttons without re-entering."""
        buttons = [
            (self.overlay_radio, "overlay"),
            (self.grid_radio, "grid"),
            (self.grouped_radio, "grouped"),
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
        elif self.current_plot_type == "combined":
            self.plot_combined()
        elif self.current_plot_type == "cumulative":
            self.plot_cumulative()
        elif self.current_plot_type == "histogram":
            self.plot_histogram()
        
        self._prime_current_ax()
        self._capture_default_limits()
        self._apply_active_axes_styling()
        self._apply_figure_layout()
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
            self.plot_distribution_overlay(ax)
        else:  # grid mode
            self.plot_distribution_grid()
    
    def plot_distribution_overlay(self, ax):
        """Plot all distributions on single axes via shared renderer."""
        render_distribution_overlay(
            ax, self.datasets,
            colors=self._effective_dataset_colors(),
            linestyles=self._effective_dataset_linestyles(),
            style=self.current_style,
            show_grid=self.show_grid,
            show_legend=self.show_legend,
        )
    
    def plot_distribution_grid(self):
        """Plot distributions in grid layout"""
        rows, cols = self.grid_layout
        dataset_colors = self._effective_dataset_colors()
        linestyles = self._effective_dataset_linestyles()

        for i, dataset in enumerate(self.datasets):
            if i >= rows * cols:
                break

            ax = self.figure.add_subplot(rows, cols, i + 1)
            color = dataset_colors[i % len(dataset_colors)]
            linestyle = linestyles[i % len(linestyles)] if linestyles else "-"
            
            ax.semilogx(dataset.particle_sizes, dataset.percent_passing,
                       linewidth=2, color=color, linestyle=linestyle,
                       marker='o' if len(dataset.particle_sizes) < 20 else None,
                       markersize=3)
            
            ax.set_title(dataset.sample_name, fontsize=9, fontweight='bold')
            ax.set_xlabel('Size (mm)', fontsize=8)
            ax.set_ylabel('% Passing', fontsize=8)
            ax.set_xlim(0.001, 100)
            ax.set_ylim(0, 100)
            ax.tick_params(labelsize=7)
            
            if self.show_grid:
                ax.grid(True, which='both', alpha=0.3)
    
    def plot_k_values(self):
        """Plot K-values comparison"""
        if not self.k_results_dict:
            self.show_empty_state("No K-values calculated")
            return
        
        if self.display_mode == "overlay":
            self.plot_k_values_overlay()
        elif self.display_mode == "grouped":
            self.plot_k_values_grouped()
        else:  # grid
            self.plot_k_values_grid()
    
    def plot_k_values_overlay(self):
        """Plot K-values as grouped bars via shared renderer."""
        ax = self.figure.add_subplot(1, 1, 1)

        render_k_overlay(
            ax, self.k_results_dict,
            flagged_methods_dict=self.flagged_methods_dict,
            colors=self._effective_dataset_colors(),
            style=self.current_style,
            show_grid=self.show_grid,
            show_legend=self.show_legend,
            show_value_labels=True,
        )
    
    def plot_k_values_grouped(self):
        """Plot K-values grouped by dataset"""
        ax = self.figure.add_subplot(1, 1, 1)
        ax.set_axisbelow(True)
        
        datasets = list(self.k_results_dict.keys())
        n_datasets = len(datasets)
        
        # Get all methods for each dataset
        all_methods = set()
        for k_dict in self.k_results_dict.values():
            all_methods.update(k_dict.keys())
        methods = self._ordered_methods(all_methods)
        
        bar_width = 0.8 / len(methods)
        positive_values = []
        
        # Plot grouped by dataset
        has_flagged = False
        for i, method in enumerate(methods):
            values = [self.k_results_dict[ds].get(method, 0) for ds in datasets]
            positions = np.arange(n_datasets) + i * bar_width
            color = self.method_colors.get(method, '#888888')
            
            bars = ax.bar(positions, values, bar_width, label=method,
                          color=color, alpha=0.8, edgecolor='black', linewidth=0.5)
            for bar, dataset_name in zip(bars, datasets):
                flagged = method in self.flagged_methods_dict.get(dataset_name, set())
                has_flagged = has_flagged or flagged
                self._style_k_bar(bar, color, flagged)
            positive_values.extend(value for value in values if value > 0)
        
        ax.set_xlabel('Dataset', fontsize=10)
        ax.set_ylabel('K (m/s)', fontsize=10)
        ax.set_title('K-Values by Dataset', fontsize=12, fontweight='bold')
        ax.set_xticks(np.arange(n_datasets) + bar_width * (len(methods) - 1) / 2)
        ax.set_xticklabels(datasets, rotation=45, ha='right', fontsize=8)
        apply_log_bar_limits(ax, positive_values)
        
        if self.show_grid:
            ax.grid(True, axis='y', alpha=0.3)
        if self.show_legend:
            if has_flagged:
                self._add_flagged_legend_handle(ax)
            else:
                handles, labels = ax.get_legend_handles_labels()
                ax.legend(handles, labels, **self._legend_kwargs(len(labels)))
    
    def plot_k_values_grid(self):
        """Plot K-values in grid layout"""
        rows, cols = self.grid_layout
        
        for i, (name, k_dict) in enumerate(self.k_results_dict.items()):
            if i >= rows * cols:
                break
            
            ax = self.figure.add_subplot(rows, cols, i + 1)
            
            methods = self._ordered_methods(k_dict.keys())
            values = [k_dict[m] for m in methods]
            colors = [self.method_colors.get(m, '#888888') for m in methods]
            flagged_methods = self.flagged_methods_dict.get(name, set())
            
            bars = ax.bar(range(len(methods)), values, color=colors, 
                         alpha=0.8, edgecolor='black', linewidth=0.5)
            ax.set_axisbelow(True)
            for bar, method, color in zip(bars, methods, colors):
                self._style_k_bar(bar, color, method in flagged_methods)
            
            ax.set_title(name, fontsize=9, fontweight='bold')
            ax.set_xlabel('Method', fontsize=8)
            ax.set_ylabel('K (m/s)', fontsize=8)
            ax.set_xticks(range(len(methods)))
            ax.set_xticklabels(
                [format_method_label(method, tiny=True) for method in methods],
                rotation=45,
                ha='right',
                fontsize=6,
            )
            apply_log_bar_limits(ax, values)
            ax.tick_params(labelsize=7)
            
            if self.show_grid:
                ax.grid(True, axis='y', alpha=0.3)
    
    def plot_combined(self):
        """Plot combined view"""
        rows, cols = self.grid_layout
        dataset_colors = self._effective_dataset_colors()
        linestyles = self._effective_dataset_linestyles()

        for i, dataset in enumerate(self.datasets):
            if i >= rows * cols:
                break
            
            # Create two subplots for each dataset
            ax1 = self.figure.add_subplot(rows, cols*2, i*2 + 1)
            ax2 = self.figure.add_subplot(rows, cols*2, i*2 + 2)
            
            color = dataset_colors[i % len(dataset_colors)]
            linestyle = linestyles[i % len(linestyles)] if linestyles else "-"
            
            # Plot distribution
            ax1.semilogx(dataset.particle_sizes, dataset.percent_passing,
                        linewidth=1.5, color=color, linestyle=linestyle, markersize=2)
            ax1.set_title(f'{dataset.sample_name} - Dist', fontsize=8)
            ax1.set_xlabel('Size (mm)', fontsize=7)
            ax1.set_ylabel('% Pass', fontsize=7)
            ax1.tick_params(labelsize=6)
            if self.show_grid:
                ax1.grid(True, alpha=0.3)
            
            # Plot K-values if available
            if dataset.sample_name in self.k_results_dict:
                k_dict = self.k_results_dict[dataset.sample_name]
                methods = self._ordered_methods(k_dict.keys())[:5]  # Limit to 5 methods for space
                values = [k_dict[m] for m in methods]
                flagged_methods = self.flagged_methods_dict.get(dataset.sample_name, set())
                
                bars = ax2.bar(range(len(methods)), values, alpha=0.8)
                ax2.set_axisbelow(True)
                for bar, method in zip(bars, methods):
                    self._style_k_bar(bar, self.method_colors.get(method, '#888888'), method in flagged_methods)
                ax2.set_title(f'{dataset.sample_name} - K', fontsize=8)
                ax2.set_xticks(range(len(methods)))
                ax2.set_xticklabels(
                    [format_method_label(method, tiny=True) for method in methods],
                    rotation=45,
                    fontsize=6,
                )
                apply_log_bar_limits(ax2, values)
                ax2.tick_params(labelsize=6)
                if self.show_grid:
                    ax2.grid(True, axis='y', alpha=0.3)
            else:
                ax2.text(0.5, 0.5, 'No K-values', transform=ax2.transAxes,
                        ha='center', va='center', fontsize=8)
                ax2.set_xticks([])
                ax2.set_yticks([])
    
    def plot_cumulative(self):
        """Plot cumulative distribution (same as distribution but different style)"""
        self.plot_distribution()  # For now, same as distribution
    
    def plot_histogram(self):
        """Plot histogram comparison"""
        rows, cols = self.grid_layout
        dataset_colors = self._effective_dataset_colors()

        for i, dataset in enumerate(self.datasets):
            if i >= rows * cols:
                break

            ax = self.figure.add_subplot(rows, cols, i + 1)
            color = dataset_colors[i % len(dataset_colors)]
            
            # Calculate retained frequency for each size class from cumulative passing
            sizes, freq = self._calculate_histogram_frequencies(
                dataset.particle_sizes,
                dataset.percent_passing,
            )
            
            bars = ax.bar(range(len(sizes)), freq, color=color, alpha=0.8)
            
            ax.set_title(dataset.sample_name, fontsize=9, fontweight='bold')
            ax.set_xlabel('Size class', fontsize=8)
            ax.set_ylabel('Frequency (%)', fontsize=8)
            ax.set_xticks(range(0, len(sizes), max(1, len(sizes)//5)))
            ax.set_xticklabels([f'{s:.2f}' for s in sizes[::max(1, len(sizes)//5)]], 
                              rotation=45, ha='right', fontsize=6)
            ax.tick_params(labelsize=7)
            
            if self.show_grid:
                ax.grid(True, axis='y', alpha=0.3)
    
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
        self.canvas.draw()
    
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
