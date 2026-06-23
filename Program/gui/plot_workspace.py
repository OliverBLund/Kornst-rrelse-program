"""
Plot workspace with styled inner toolbar, collapsible sidebar, and chart area.

Matches the design concept in 02_tabs.html / _shared.css (.pw-* classes).
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QComboBox,
    QPushButton, QLabel, QFileDialog, QMessageBox, QLineEdit,
    QSizePolicy, QButtonGroup, QSpinBox, QDoubleSpinBox, QScrollArea,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize,
)
from typing import Optional, Dict, Set
import dataclasses
import csv
import math
import re
import numpy as np

from data_loader import GrainSizeData
from .plot_widget import PlotWidget
from .plot_styles import PlotStyle, get_style, get_available_style_names
from .toggle_switch import ToggleSwitch
from .theme import C, F, SZ, icon
from .collapsible_section import CollapsibleSection
from .sidebar_controls import (
    LEGEND_LOCATIONS as _LEGEND_LOCATIONS,
    LEGEND_LAYOUTS as _LEGEND_LAYOUTS,
    make_axis_row, make_color_row, make_combo_row, make_dspin_row,
    make_spin_row, make_toggle_row,
)
from .plot_renderers import apply_legend_aware_layout
from .plot_text_options import (
    GlobalPlotStylingPlaceholderDialog,
    PlotTextOptionsDialog,
)
from unit_conversions import (
    HydraulicConductivityUnit,
    HydraulicConductivityConverter,
    get_default_plot_unit,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _pw_sep() -> QFrame:
    """Vertical 1×16 separator for the inner toolbar."""
    sep = QFrame()
    sep.setObjectName("pw-sep")
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFixedSize(1, 16)
    return sep


def _pw_btn(text: str = "", tooltip: str = "", icon_name: str = "") -> QPushButton:
    """Small action button (.pw-btn)."""
    btn = QPushButton(text)
    btn.setProperty("pw-btn", True)
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_name:
        btn.setIcon(icon(icon_name, C.TEXT_MID))
        btn.setIconSize(QSize(12, 12))
    return btn


def _pw_chk(text: str, tooltip: str = "", checked: bool = False,
            icon_name: str = "") -> QPushButton:
    """Toggle check button (.pw-chk)."""
    btn = QPushButton(text)
    btn.setProperty("pw-chk", True)
    btn.setProperty("active", checked)
    btn.setCheckable(True)
    btn.setChecked(checked)
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_name:
        btn._pw_icon_name = icon_name
        btn.setIcon(icon(icon_name, C.OLIVE if checked else C.TEXT_MID))
        btn.setIconSize(QSize(12, 12))
    # Keep the active property in sync with checked state
    btn.toggled.connect(lambda on, b=btn: _sync_chk(b, on))
    return btn


def _sync_chk(btn: QPushButton, on: bool):
    btn.setProperty("active", on)
    btn.style().unpolish(btn)
    btn.style().polish(btn)
    icon_name = getattr(btn, '_pw_icon_name', None)
    if icon_name:
        btn.setIcon(icon(icon_name, C.OLIVE if on else C.TEXT_MID))


# ─────────────────────────────────────────────────────────────
# PlotWorkspace
# ─────────────────────────────────────────────────────────────

_ISO_FRACTION_BANDS = (
    (0.0, 0.002, "Clay"),
    (0.002, 0.0063, "Fine silt"),
    (0.0063, 0.02, "Medium silt"),
    (0.02, 0.063, "Coarse silt"),
    (0.063, 0.2, "Fine sand"),
    (0.2, 0.63, "Medium sand"),
    (0.63, 2.0, "Coarse sand"),
    (2.0, 6.3, "Fine gravel"),
    (6.3, 20.0, "Medium gravel"),
    (20.0, 63.0, "Coarse gravel"),
    (63.0, 200.0, "Cobble"),
)


def _format_mm(value: float) -> str:
    if value == 0:
        return "0"
    return f"{value:.4g}"


def _iso_fraction_label(lower_mm: float, upper_mm: float) -> str:
    if upper_mm <= 0:
        return "Unknown"
    if lower_mm <= 0 and upper_mm <= 0.063:
        return "Silt / clay"
    lower = max(lower_mm, 0.0001)
    midpoint = math.sqrt(lower * upper_mm)
    for lo, hi, label in _ISO_FRACTION_BANDS:
        if lo <= midpoint < hi:
            return label
    return "Coarser material"


def _scheme_fraction_label(lower_mm: float, upper_mm: float, scheme) -> str:
    """Label a retained-size interval using the active classification scheme."""
    if scheme is None or getattr(scheme, "key", "iso14688") == "iso14688":
        return _iso_fraction_label(lower_mm, upper_mm)
    if upper_mm <= 0:
        return "Unknown"

    lower = max(lower_mm, 0.0001)
    midpoint = math.sqrt(lower * upper_mm)
    clay_max = float(getattr(scheme, "clay_max", 0.002))
    silt_max = float(getattr(scheme, "silt_max", 0.063))
    sand_max = float(getattr(scheme, "sand_max", 2.0))
    gravel_max = float(getattr(scheme, "gravel_max", 63.0))
    bands = (
        (0.0, clay_max, "Clay"),
        (clay_max, silt_max, "Silt"),
        (silt_max, sand_max, "Sand"),
        (sand_max, gravel_max, "Gravel"),
        (gravel_max, 300.0, "Cobble"),
    )
    for lo, hi, label in bands:
        if lo <= midpoint < hi:
            return label
    return "Coarser material"


def _scheme_short_name(scheme) -> str:
    name = getattr(scheme, "name", None) or "active scheme"
    if getattr(scheme, "key", "") == "iso14688":
        return "ISO 14688"
    if getattr(scheme, "key", "") == "uscs":
        return "USCS"
    return str(name)


class PlotWorkspace(QWidget):
    """Plot workspace: inner toolbar + collapsible sidebar + matplotlib chart."""

    plot_exported = pyqtSignal(str)

    def __init__(self, dataset: GrainSizeData, parent=None):
        super().__init__(parent)
        self.dataset = dataset
        self.plot_widget: Optional[PlotWidget] = None
        self.k_results: Dict[str, float] = {}
        self.flagged_methods: Set[str] = set()
        self.sidebar_visible = False
        self.drawer_visible = False
        self._drawer_headers: list[str] = []
        self._drawer_rows: list[tuple] = []
        self._drawer_title_text = "Plot data"

        # Plot settings
        self.current_plot_type = "distribution"
        self.show_grid = True
        self.show_legend = True
        self.show_markers = False
        self.show_zones = False
        self.show_dlines = True
        self.fill_curve = False
        self.fill_zone_labels = False
        self.log_x_scale = True
        self.show_k_value_labels = True
        self.k_value_label_fontsize = 8
        self.log_k_y_scale = False

        # Per-workspace custom style — starts as None (preset is authoritative).
        # Populated when the user tweaks any field in the "Legend & Typography"
        # section; cleared when the user picks a different preset or clicks Reset.
        self._custom_style: Optional[PlotStyle] = None

        self._init_ui()

    # ── UI Construction ────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_body(), 1)

    # ── Toolbar ────────────────────────────────────────────────

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("pw-toolbar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(4)

        # ── Segmented control (Dist. Curve / K-Values) ──
        seg_frame = QFrame()
        seg_frame.setObjectName("pw-seg")
        seg_lay = QHBoxLayout(seg_frame)
        seg_lay.setContentsMargins(0, 0, 0, 0)
        seg_lay.setSpacing(0)

        self._seg_group = QButtonGroup(self)
        self._seg_group.setExclusive(True)

        self._seg_dist = QPushButton("  Dist. Curve")
        self._seg_dist.setIcon(icon("fa6s.chart-line", C.TEXT))  # starts active
        self._seg_dist.setProperty("pw-seg", True)
        self._seg_dist.setProperty("active", True)
        self._seg_dist.setCheckable(True)
        self._seg_dist.setChecked(True)
        self._seg_dist.setCursor(Qt.CursorShape.PointingHandCursor)
        self._seg_dist.setIconSize(QSize(12, 12))

        self._seg_kval = QPushButton("  K-Values")
        self._seg_kval.setIcon(icon("fa6s.chart-bar", C.TEXT_MID))
        self._seg_kval.setProperty("pw-seg", True)
        self._seg_kval.setProperty("active", False)
        self._seg_kval.setCheckable(True)
        self._seg_kval.setCursor(Qt.CursorShape.PointingHandCursor)
        self._seg_kval.setIconSize(QSize(12, 12))

        self._seg_group.addButton(self._seg_dist, 0)
        self._seg_group.addButton(self._seg_kval, 1)
        seg_lay.addWidget(self._seg_dist)
        seg_lay.addWidget(self._seg_kval)
        self._seg_group.idToggled.connect(self._on_seg_changed)

        lay.addWidget(seg_frame)
        lay.addWidget(_pw_sep())

        # ── More plot types dropdown ──
        self._more_plots = QComboBox()
        self._more_plots.setObjectName("pw-more-plots-sel")
        self._more_plots.addItems(["More Plots…", "Combined", "Histogram"])
        self._more_plots.setMaxVisibleItems(6)
        self._more_plots.setToolTip("Additional plot types")
        self._more_plots.currentIndexChanged.connect(self._on_more_plot_changed)
        lay.addWidget(self._more_plots)

        lay.addWidget(_pw_sep())

        # ── Style selector ──
        self._style_sel = QComboBox()
        self._style_sel.setObjectName("pw-style-sel")
        from .plot_styles import get_available_style_names
        self._style_sel.addItems(get_available_style_names())
        self._style_sel.setCurrentText("Classic")
        self._style_sel.setToolTip("Plot style")
        self._style_sel.currentTextChanged.connect(self._on_style_changed)
        lay.addWidget(self._style_sel)

        lay.addWidget(_pw_sep())

        # ── Shared plot text settings ──
        self._plot_text_btn = _pw_btn("", "Edit title and axis labels", "fa6s.pen-ruler")
        self._plot_text_btn.clicked.connect(self._open_plot_text_dialog)
        lay.addWidget(self._plot_text_btn)

        self._global_plot_style_btn = _pw_btn(
            "",
            "Global plot styling (planned)",
            "fa6s.brush",
        )
        self._global_plot_style_btn.clicked.connect(
            self._open_global_plot_styling_placeholder
        )
        lay.addWidget(self._global_plot_style_btn)

        lay.addWidget(_pw_sep())

        # ── Sidebar toggle ──
        self._tb_sidebar_btn = _pw_chk(" Controls", "Toggle controls panel", False, "fa6s.sliders")
        self._tb_sidebar_btn.clicked.connect(self._toggle_sidebar)
        lay.addWidget(self._tb_sidebar_btn)

        self._tb_drawer_btn = _pw_chk(" Table", "Toggle active plot data drawer", False, "fa6s.table")
        self._tb_drawer_btn.clicked.connect(self._toggle_drawer)
        lay.addWidget(self._tb_drawer_btn)

        lay.addWidget(_pw_sep())

        # ── Toggle checks ──
        self._chk_grid = _pw_chk("Grid", "Toggle grid", True, "fa6s.hashtag")
        self._chk_legend = _pw_chk("Legend", "Toggle legend", True, "fa6s.list")
        self._chk_zones = _pw_chk("Zones", "Toggle soil zones", False, "fa6s.layer-group")
        self._chk_dlines = _pw_chk("D-lines", "Show D10 / D50 / D60 lines", True, "fa6s.crosshairs")

        for chk in (self._chk_grid, self._chk_legend, self._chk_zones, self._chk_dlines):
            chk.toggled.connect(self._update_display_options)
            lay.addWidget(chk)

        lay.addWidget(_pw_sep())

        # ── Zoom controls ──
        btn_zin = _pw_btn("", "Zoom in", "fa6s.magnifying-glass-plus")
        btn_zout = _pw_btn("", "Zoom out", "fa6s.magnifying-glass-minus")
        btn_fit = _pw_btn(" Fit", "Reset zoom", "fa6s.arrows-to-circle")
        btn_zin.clicked.connect(self.zoom_in)
        btn_zout.clicked.connect(self.zoom_out)
        btn_fit.clicked.connect(self.reset_view)
        lay.addWidget(btn_zin)
        lay.addWidget(btn_zout)
        lay.addWidget(btn_fit)

        lay.addWidget(_pw_sep())

        # ── Export ──
        btn_export = _pw_btn(" Export", "Export plot", "fa6s.download")
        btn_export.clicked.connect(lambda: self.export_plot("png"))
        lay.addWidget(btn_export)

        # ── Spacer ──
        lay.addStretch(1)

        return bar

    # ── Body (sidebar + chart) ─────────────────────────────────

    def _build_body(self) -> QWidget:
        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        self._sidebar = self._build_sidebar()
        self._sidebar.setMaximumWidth(0)  # start collapsed

        # Chart area — plot widget fills the space; toggle handle overlays
        self._chart_area = QWidget()
        chart_lay = QVBoxLayout(self._chart_area)
        chart_lay.setContentsMargins(10, 0, 0, 0)
        chart_lay.setSpacing(0)

        self.plot_widget = PlotWidget()
        self.plot_widget.set_style(self._effective_style())
        self.plot_widget.set_display_unit(get_default_plot_unit())
        self.plot_widget.axes_view_changed.connect(self._sync_axis_inputs_from_ax)
        chart_lay.addWidget(self.plot_widget, 1)

        self._drawer = self._build_data_drawer()
        chart_lay.addWidget(self._drawer, 0)

        # Toggle handle — absolute overlay at left edge, vertically centered
        self._toggle_handle = QPushButton(self._chart_area)
        self._toggle_handle.setObjectName("pw-toggle-handle")
        self._toggle_handle.setIcon(icon("fa6s.chevron-right", C.TEXT_MID, 8))
        self._toggle_handle.setIconSize(QSize(8, 8))
        self._toggle_handle.setToolTip("Toggle sidebar")
        self._toggle_handle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_handle.clicked.connect(self._toggle_sidebar)
        self._toggle_handle.raise_()  # on top of plot

        self._body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._body_splitter.setChildrenCollapsible(True)
        self._body_splitter.setHandleWidth(0)
        self._body_splitter.addWidget(self._sidebar)
        self._body_splitter.addWidget(self._chart_area)
        self._body_splitter.setCollapsible(0, True)
        self._body_splitter.setCollapsible(1, False)
        self._body_splitter.setStretchFactor(0, 0)
        self._body_splitter.setStretchFactor(1, 1)
        self._body_splitter.setSizes([0, 1])
        body_lay.addWidget(self._body_splitter, 1)

        # Sidebar collapse animation
        self._sidebar_anim = QPropertyAnimation(self._sidebar, b"maximumWidth")
        self._sidebar_anim.setDuration(200)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._sidebar_anim.valueChanged.connect(self._on_sidebar_animation_value_changed)
        self._sidebar_anim.finished.connect(self._on_sidebar_animation_finished)

        self._drawer_anim = QPropertyAnimation(self._drawer, b"maximumHeight")
        self._drawer_anim.setDuration(180)
        self._drawer_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        return body

    def resizeEvent(self, event):
        """Reposition the toggle handle when the chart area resizes."""
        super().resizeEvent(event)
        self._position_toggle_handle()
        if self.drawer_visible and hasattr(self, "_drawer"):
            self._drawer.setMaximumHeight(self._drawer_open_height())

    def _position_toggle_handle(self):
        """Place the toggle handle at the chart edge, vertically centered."""
        if not hasattr(self, '_toggle_handle') or not hasattr(self, '_chart_area'):
            return
        h = self._chart_area.height()
        handle_h = 40
        handle_w = 16
        y = max(0, (h - handle_h) // 2)
        x = 0
        self._toggle_handle.setGeometry(x, y, handle_w, handle_h)

    def _build_data_drawer(self) -> QFrame:
        """Collapsible table drawer for the data behind the active plot."""
        drawer = QFrame()
        drawer.setObjectName("pw-data-drawer")
        drawer.setMaximumHeight(32)
        drawer.setMinimumHeight(0)
        drawer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        drawer.setStyleSheet(f"""
            QFrame#pw-data-drawer {{
                background: {C.BG_RAISED};
                border-top: 1px solid {C.BORDER};
            }}
            QTableWidget#pw-drawer-table {{
                background: {C.BG};
                border: none;
                gridline-color: transparent;
                color: {C.TEXT};
                font-size: 10px;
            }}
            QTableWidget#pw-drawer-table::item {{
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

        self._drawer_toggle_btn = _pw_chk(
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
        self._drawer_export_btn.clicked.connect(self.export_data)
        header_lay.addWidget(self._drawer_export_btn)
        lay.addWidget(header)

        self._drawer_table = QTableWidget()
        self._drawer_table.setObjectName("pw-drawer-table")
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
            _sync_chk(button, self.drawer_visible)

    def _drawer_open_height(self) -> int:
        available = max(360, self.height())
        return min(260, max(130, int(available * 0.34)))

    # ── Sidebar ────────────────────────────────────────────────

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("pw-sidebar")
        sidebar.setMinimumWidth(0)
        # minimumHeight=0 plus a QScrollArea wrapper keeps the sidebar from
        # forcing the host tab to grow as new sections are added. Without this,
        # minimumSizeHint sums every row and propagates up to DatasetTab.
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

        # ── Axis Controls ──
        self._sect_axis = CollapsibleSection(
            "Axis Controls", "fa6s.ruler-combined",
            CollapsibleSection.BLUE, expanded=True,
        )
        for label_text, default, row_attr, label_attr, input_attr in [
            ("X min (mm)", "0.001", "_row_xmin", "_lbl_xmin", "_in_xmin"),
            ("X max (mm)", "100",   "_row_xmax", "_lbl_xmax", "_in_xmax"),
            ("Y min (%)",  "0",     "_row_ymin", "_lbl_ymin", "_in_ymin"),
            ("Y max (%)",  "102",   "_row_ymax", "_lbl_ymax", "_in_ymax"),
        ]:
            row, inp, lbl = self._axis_row(label_text, default)
            setattr(self, row_attr, row)
            setattr(self, label_attr, lbl)
            setattr(self, input_attr, inp)
            inp.editingFinished.connect(self._on_axis_changed)
            self._sect_axis.add_widget(row)
        lay.addWidget(self._sect_axis)

        # ── Display Options ──
        self._sect_display = CollapsibleSection(
            "Display Options", "fa6s.eye",
            CollapsibleSection.OLIVE, expanded=True,
        )
        for label_text, checked, row_attr, switch_attr in [
            ("Show grid lines",      True,  "_row_grid",        "_sw_grid"),
            ("Show soil zones",      False, "_row_zones",       "_sw_zones"),
            ("Show D10 / D50 / D60", True,  "_row_dlines",      "_sw_dlines"),
        ]:
            row_w, sw = self._toggle_row(label_text, checked)
            setattr(self, row_attr, row_w)
            setattr(self, switch_attr, sw)
            self._sect_display.add_widget(row_w)

        # Fill curve + sub-option (zone labels)
        self._row_fill, self._sw_fill = self._toggle_row("Fill curve area", False)
        self._sect_display.add_widget(self._row_fill)

        self._row_fill_labels, self._sw_fill_labels = self._toggle_row("  └ Zone % in fill", False)
        self._row_fill_labels.layout().setContentsMargins(22, 4, 10, 4)
        self._row_fill_labels.setStyleSheet(
            f"border-bottom: 1px solid rgba(212,196,168,0.4); background: rgba(0,0,0,0.02);")
        self._sect_display.add_widget(self._row_fill_labels)

        self._row_markers, self._sw_markers = self._toggle_row("Markers on curve", False)
        self._sect_display.add_widget(self._row_markers)

        self._row_k_labels, self._sw_k_labels = self._toggle_row("K value labels", True)
        self._sect_display.add_widget(self._row_k_labels)

        self._row_k_log, self._sw_k_log = self._toggle_row("Log K axis", False)
        self._sect_display.add_widget(self._row_k_log)
        lay.addWidget(self._sect_display)

        # ── Curve Color ──
        self._sect_curve_color = CollapsibleSection(
            "Curve Color", "fa6s.palette",
            CollapsibleSection.PURPLE, expanded=False,
        )
        self._color_container = QWidget()
        self._color_container_lay = QVBoxLayout(self._color_container)
        self._color_container_lay.setContentsMargins(0, 0, 0, 0)
        self._color_container_lay.setSpacing(0)
        # Populate with current dataset
        self._add_color_row(self.dataset.sample_name, C.SAMPLE_COLORS[0])
        self._sect_curve_color.add_widget(self._color_container)
        lay.addWidget(self._sect_curve_color)

        # ── Legend & Typography ──
        self._sect_advanced = CollapsibleSection(
            "Legend & Typography", "fa6s.text-height",
            CollapsibleSection.AMBER, expanded=False,
        )

        self._row_legend_loc, self._legend_loc_combo = self._combo_row(
            "Legend position", [label for _, _, label in _LEGEND_LOCATIONS])
        self._legend_loc_combo.currentIndexChanged.connect(
            self._on_legend_location_changed)
        self._sect_advanced.add_widget(self._row_legend_loc)

        self._row_legend_layout, self._legend_layout_combo = self._combo_row(
            "Legend layout", [label for _, label in _LEGEND_LAYOUTS])
        self._legend_layout_combo.currentIndexChanged.connect(
            self._on_legend_layout_changed)
        self._sect_advanced.add_widget(self._row_legend_layout)

        self._row_legend_alpha, self._legend_alpha_spin = self._dspin_row(
            "Legend opacity", 0.0, 1.0, 0.05, 2)
        self._legend_alpha_spin.valueChanged.connect(
            lambda v: self._update_style_field("legend_framealpha", float(v)))
        self._sect_advanced.add_widget(self._row_legend_alpha)

        self._row_title_size, self._title_size_spin = self._spin_row(
            "Title size", 6, 36)
        self._title_size_spin.valueChanged.connect(
            lambda v: self._update_style_field("title_fontsize", int(v)))
        self._sect_advanced.add_widget(self._row_title_size)

        self._row_label_size, self._label_size_spin = self._spin_row(
            "Axis label size", 6, 36)
        self._label_size_spin.valueChanged.connect(
            lambda v: self._update_style_field("label_fontsize", int(v)))
        self._sect_advanced.add_widget(self._row_label_size)

        self._row_tick_size, self._tick_size_spin = self._spin_row(
            "Tick size", 5, 24)
        self._tick_size_spin.valueChanged.connect(
            lambda v: self._update_style_field("tick_fontsize", int(v)))
        self._sect_advanced.add_widget(self._row_tick_size)

        self._row_legend_size, self._legend_size_spin = self._spin_row(
            "Legend size", 5, 24)
        self._legend_size_spin.valueChanged.connect(
            lambda v: self._update_style_field("legend_fontsize", int(v)))
        self._sect_advanced.add_widget(self._row_legend_size)

        self._row_k_label_size, self._k_label_size_spin = self._spin_row(
            "K value label size", 5, 14)
        self._k_label_size_spin.setValue(self.k_value_label_fontsize)
        self._k_label_size_spin.valueChanged.connect(self._on_k_label_size_changed)
        self._sect_advanced.add_widget(self._row_k_label_size)

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

        # Seed advanced widgets with the initial preset's values.
        self._sync_advanced_style_widgets(get_style(self._style_sel.currentText()))

        # ── K-value unit selector ──
        self._sect_units = CollapsibleSection(
            "K-Value Units", "fa6s.scale-balanced",
            CollapsibleSection.EARTH, expanded=False,
        )
        self._unit_combo = QComboBox()
        self._unit_combo.setObjectName("pw-style-sel")
        all_units = HydraulicConductivityConverter.get_all_units()
        for unit, symbol in all_units.items():
            self._unit_combo.addItem(symbol, unit)
        default_index = list(all_units.keys()).index(get_default_plot_unit())
        self._unit_combo.setCurrentIndex(default_index)
        self._unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        self._row_units = QWidget()
        unit_lay = QHBoxLayout(self._row_units)
        unit_lay.setContentsMargins(10, 5, 10, 5)
        unit_lay.addWidget(self._unit_combo)
        self._sect_units.add_widget(self._row_units)
        lay.addWidget(self._sect_units)

        # ── Export controls ──
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
        btn_png.clicked.connect(lambda: self.export_plot("png"))
        btn_svg = QPushButton("Export as SVG")
        btn_svg.setProperty("pw-btn", True)
        btn_svg.clicked.connect(lambda: self.export_plot("svg"))
        btn_data = QPushButton("Export Data")
        btn_data.setProperty("pw-btn", True)
        btn_data.clicked.connect(self.export_data)
        export_lay.addWidget(btn_png)
        export_lay.addWidget(btn_svg)
        export_lay.addWidget(btn_data)
        self._sect_export.add_widget(export_w)
        lay.addWidget(self._sect_export)

        lay.addStretch(1)
        self._update_contextual_controls()
        return sidebar

    # ── Sidebar sub-builders ───────────────────────────────────

    def _axis_row(self, label: str, default: str):
        return make_axis_row(label, default)

    def _toggle_row(self, label: str, checked: bool):
        row, sw = make_toggle_row(label, checked)
        sw.toggled.connect(self._on_sidebar_toggle_changed)
        return row, sw

    def _combo_row(self, label: str, items: list[str]):
        return make_combo_row(label, items)

    def _spin_row(self, label: str, minimum: int, maximum: int):
        return make_spin_row(label, minimum, maximum)

    def _dspin_row(self, label: str, minimum: float, maximum: float,
                   step: float, decimals: int):
        return make_dspin_row(label, minimum, maximum, step, decimals)

    def _add_color_row(self, name: str, color: str):
        row, _dot = make_color_row(name, color)
        self._color_container_lay.addWidget(row)

    # ── Sidebar toggle ─────────────────────────────────────────

    def _toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        target = self._default_sidebar_width() if self.sidebar_visible else 0
        self._sidebar_anim.stop()
        splitter_sizes = self._body_splitter.sizes() if hasattr(self, "_body_splitter") else []
        splitter_width = splitter_sizes[0] if splitter_sizes else self._sidebar.width()
        if self.sidebar_visible:
            self._body_splitter.setHandleWidth(5)
            self._sidebar.setMinimumWidth(0)
            self._sidebar.setMaximumWidth(self._max_sidebar_width())
            start = max(0, min(splitter_width, self._max_sidebar_width()))
        else:
            self._sidebar.setMinimumWidth(0)
            start = max(0, splitter_width)
            self._sidebar.setMaximumWidth(max(start, self._min_sidebar_width()))
        self._sidebar_anim.setStartValue(start)
        self._sidebar_anim.setEndValue(target)
        self._sidebar_anim.start()
        self._tb_sidebar_btn.blockSignals(True)
        self._tb_sidebar_btn.setChecked(self.sidebar_visible)
        self._tb_sidebar_btn.blockSignals(False)
        # Update handle chevron direction
        chevron = "fa6s.chevron-left" if self.sidebar_visible else "fa6s.chevron-right"
        self._toggle_handle.setIcon(icon(chevron, C.TEXT_MID, 8))

    def _apply_sidebar_splitter_width(self, width: int) -> None:
        if not hasattr(self, "_body_splitter"):
            return
        width = max(0, int(width))
        total = max(1, self._body_splitter.width())
        self._body_splitter.setSizes([width, max(1, total - width)])
        self._body_splitter.setHandleWidth(5 if width > 0 else 0)
        self._position_toggle_handle()

    def _on_sidebar_animation_value_changed(self, value) -> None:
        width = int(value)
        self._sidebar.setMaximumWidth(max(0, width))
        self._apply_sidebar_splitter_width(width)

    def _min_sidebar_width(self) -> int:
        return min(260, max(220, self.width() // 4))

    def _default_sidebar_width(self) -> int:
        return min(self._max_sidebar_width(), max(300, SZ.PLOT_SIDEBAR_W))

    def _max_sidebar_width(self) -> int:
        return min(440, max(320, int(max(self.width(), 1) * 0.38)))

    def _on_sidebar_animation_finished(self) -> None:
        if self.sidebar_visible:
            self._sidebar.setMinimumWidth(self._min_sidebar_width())
            self._sidebar.setMaximumWidth(self._max_sidebar_width())
            self._apply_sidebar_splitter_width(
                max(self._min_sidebar_width(), self._default_sidebar_width())
            )
        else:
            self._sidebar.setMinimumWidth(0)
            self._sidebar.setMaximumWidth(0)
            self._apply_sidebar_splitter_width(0)

    # ── Toolbar callbacks ──────────────────────────────────────

    def _on_seg_changed(self, btn_id: int, checked: bool):
        if not checked:
            return
        # Update active property for styling
        self._seg_dist.setProperty("active", btn_id == 0)
        self._seg_kval.setProperty("active", btn_id == 1)
        self._seg_dist.style().unpolish(self._seg_dist)
        self._seg_dist.style().polish(self._seg_dist)
        self._seg_kval.style().unpolish(self._seg_kval)
        self._seg_kval.style().polish(self._seg_kval)
        # Update icon colors: active seg uses TEXT, inactive uses TEXT_MID
        self._seg_dist.setIcon(icon("fa6s.chart-line", C.TEXT if btn_id == 0 else C.TEXT_MID))
        self._seg_kval.setIcon(icon("fa6s.chart-bar", C.TEXT if btn_id == 1 else C.TEXT_MID))

        self.current_plot_type = "distribution" if btn_id == 0 else "k-values"
        # Reset "More Plots" dropdown
        self._more_plots.blockSignals(True)
        self._more_plots.setCurrentIndex(0)
        self._more_plots.blockSignals(False)
        self._update_contextual_controls()
        self.refresh_plot()

    def _on_more_plot_changed(self, index: int):
        if index == 0:
            return  # "More Plots…" header
        plot_map = {1: "combined", 2: "histogram"}
        self.current_plot_type = plot_map.get(index, "distribution")
        # Deselect segment buttons visually
        self._seg_group.setExclusive(False)
        self._seg_dist.setChecked(False)
        self._seg_kval.setChecked(False)
        self._seg_dist.setProperty("active", False)
        self._seg_kval.setProperty("active", False)
        for btn in (self._seg_dist, self._seg_kval):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._seg_group.setExclusive(True)
        self._update_contextual_controls()
        self.refresh_plot()

    def _on_style_changed(self, style_name: str):
        # Switching presets discards any per-field customizations — the preset
        # becomes authoritative again. The "Legend & Typography" widgets resync
        # to the new preset values below.
        self._custom_style = None
        preset = get_style(style_name)
        if self.plot_widget:
            self.plot_widget.set_style(preset)
        self._sync_advanced_style_widgets(preset)
        self._sync_reset_button()
        self.refresh_plot()

    def _open_plot_text_dialog(self) -> None:
        """Edit shared title and axis-label options for this plot."""
        if not self.plot_widget:
            return
        dialog = PlotTextOptionsDialog(
            self.dataset.sample_name,
            self.plot_widget.plot_text_options,
            self,
        )
        if not dialog.exec():
            return
        self.plot_widget.plot_text_options = dialog.options()
        self.refresh_plot()

    def _open_global_plot_styling_placeholder(self) -> None:
        """Show placeholder for a future cross-dataset styling workflow."""
        dialog = GlobalPlotStylingPlaceholderDialog(self)
        dialog.exec()

    def _effective_style(self) -> PlotStyle:
        """Style currently driving the plot — custom override if any, else the preset."""
        if self._custom_style is not None:
            return self._custom_style
        return get_style(self._style_sel.currentText())

    def _update_style_field(self, field: str, value) -> None:
        """Override a single PlotStyle field, cloning the preset on first edit."""
        self._update_style_fields(**{field: value})

    def _update_style_fields(self, **changes) -> None:
        """Override one or more PlotStyle fields, cloning the preset on first edit."""
        base = self._custom_style or get_style(self._style_sel.currentText())
        dirty = {k: v for k, v in changes.items() if getattr(base, k) != v}
        if not dirty:
            return
        self._custom_style = dataclasses.replace(base, **dirty)
        if self.plot_widget:
            self.plot_widget.set_style(self._custom_style)
        self._sync_reset_button()
        self.refresh_plot()

    def _on_legend_location_changed(self, index: int) -> None:
        """Apply both legend_loc and legend_bbox_to_anchor from the dropdown."""
        if index < 0 or index >= len(_LEGEND_LOCATIONS):
            return
        loc, bbox, _label = _LEGEND_LOCATIONS[index]
        self._update_style_fields(legend_loc=loc, legend_bbox_to_anchor=bbox)

    def _on_legend_layout_changed(self, index: int) -> None:
        """Apply the requested legend column layout."""
        if index < 0 or index >= len(_LEGEND_LAYOUTS):
            return
        ncol, _label = _LEGEND_LAYOUTS[index]
        self._update_style_fields(legend_ncol=ncol)

    def _sync_advanced_style_widgets(self, style: PlotStyle) -> None:
        """Push preset values into the advanced-style widgets without firing signals."""
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
            return  # sidebar not yet built
        for w in widgets:
            w.blockSignals(True)
        loc_idx = next(
            (
                i for i, (loc, bbox, _label) in enumerate(_LEGEND_LOCATIONS)
                if loc == style.legend_loc and bbox == style.legend_bbox_to_anchor
            ),
            0,
        )
        layout_idx = next(
            (
                i for i, (ncol, _label) in enumerate(_LEGEND_LAYOUTS)
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
            btn.setEnabled(self._custom_style is not None)

    def _on_reset_custom_style(self) -> None:
        """Discard per-field overrides and revert to the selected preset."""
        if self._custom_style is None:
            return
        self._custom_style = None
        preset = get_style(self._style_sel.currentText())
        if self.plot_widget:
            self.plot_widget.set_style(preset)
        self._sync_advanced_style_widgets(preset)
        self._sync_reset_button()
        self.refresh_plot()

    def _update_display_options(self):
        self.show_grid = self._chk_grid.isChecked()
        self.show_legend = self._chk_legend.isChecked()
        self.show_zones = self._chk_zones.isChecked()
        self.show_dlines = self._chk_dlines.isChecked()
        # Sync sidebar toggle switches (if visible)
        self._sw_grid.setChecked(self.show_grid, animate=False)
        self._sw_zones.setChecked(self.show_zones, animate=False)
        self._sw_dlines.setChecked(self.show_dlines, animate=False)

        self._apply_plot_options()
        self.refresh_plot()

    def _on_sidebar_toggle_changed(self, _on: bool):
        """Sync sidebar toggle switches back to toolbar checks."""
        self.show_grid = self._sw_grid.isChecked()
        self.show_zones = self._sw_zones.isChecked()
        self.show_dlines = self._sw_dlines.isChecked()
        self.fill_curve = self._sw_fill.isChecked()
        self.fill_zone_labels = self._sw_fill_labels.isChecked()
        self.show_markers = self._sw_markers.isChecked()
        self.show_k_value_labels = self._sw_k_labels.isChecked()
        self.log_k_y_scale = self._sw_k_log.isChecked()

        # Sync toolbar check buttons
        self._chk_grid.blockSignals(True)
        self._chk_grid.setChecked(self.show_grid)
        self._chk_grid.setProperty("active", self.show_grid)
        self._chk_grid.style().unpolish(self._chk_grid)
        self._chk_grid.style().polish(self._chk_grid)
        self._chk_grid.blockSignals(False)

        self._chk_zones.blockSignals(True)
        self._chk_zones.setChecked(self.show_zones)
        self._chk_zones.setProperty("active", self.show_zones)
        self._chk_zones.style().unpolish(self._chk_zones)
        self._chk_zones.style().polish(self._chk_zones)
        self._chk_zones.blockSignals(False)

        self._chk_dlines.blockSignals(True)
        self._chk_dlines.setChecked(self.show_dlines)
        self._chk_dlines.setProperty("active", self.show_dlines)
        self._chk_dlines.style().unpolish(self._chk_dlines)
        self._chk_dlines.style().polish(self._chk_dlines)
        self._chk_dlines.blockSignals(False)

        self._apply_plot_options()
        self.refresh_plot()

    def _on_k_label_size_changed(self, value: int) -> None:
        self.k_value_label_fontsize = int(value)
        self._apply_plot_options()
        self.refresh_plot()

    def _on_axis_changed(self):
        target_ax = self.plot_widget.current_ax if self.plot_widget else None
        if not target_ax:
            return
        try:
            xmin = float(self._in_xmin.text())
            xmax = float(self._in_xmax.text())
            ymin = float(self._in_ymin.text())
            ymax = float(self._in_ymax.text())
            target_ax.set_xlim(xmin, xmax)
            target_ax.set_ylim(ymin, ymax)
            self.plot_widget.canvas.draw()
            self._sync_axis_inputs_from_ax(target_ax)
        except ValueError:
            pass

    def _on_unit_changed(self):
        if not self.plot_widget:
            return
        selected_unit = self._unit_combo.currentData()
        if selected_unit:
            self.plot_widget.set_display_unit(selected_unit)
        self._update_contextual_controls()
        self._sync_axis_inputs_from_ax(getattr(self.plot_widget, 'current_ax', None))
        self._refresh_drawer()

    def _set_context_visibility(self, widget: QWidget, visible: bool):
        widget.setHidden(not visible)

    def _update_contextual_controls(self):
        """Show only the controls that make sense for the active plot type."""
        plot_type = self.current_plot_type
        is_distribution_like = plot_type in {"distribution", "combined"}
        is_k_plot = plot_type == "k-values"
        supports_k_units = plot_type in {"k-values", "combined"}
        supports_zones = plot_type in {"distribution", "combined"}
        supports_dlines = plot_type in {"distribution", "combined"}
        supports_fill = plot_type in {"distribution", "combined"}
        supports_markers = plot_type in {"distribution", "combined"}

        # Toolbar checks
        self._chk_zones.setHidden(not supports_zones)
        self._chk_dlines.setHidden(not supports_dlines)

        # Axis rows
        show_x_axis_rows = is_distribution_like
        self._set_context_visibility(self._row_xmin, show_x_axis_rows)
        self._set_context_visibility(self._row_xmax, show_x_axis_rows)
        self._set_context_visibility(self._row_ymin, True)
        self._set_context_visibility(self._row_ymax, True)

        self._lbl_xmin.setText("X min (mm)" if is_distribution_like else "X min")
        self._lbl_xmax.setText("X max (mm)" if is_distribution_like else "X max")
        if is_k_plot:
            unit = self._unit_combo.currentData() or get_default_plot_unit()
            symbol = HydraulicConductivityConverter.UNIT_SYMBOLS[unit]
            self._lbl_ymin.setText(f"Y min ({symbol})")
            self._lbl_ymax.setText(f"Y max ({symbol})")
        else:
            self._lbl_ymin.setText("Y min (%)")
            self._lbl_ymax.setText("Y max (%)")

        # Sidebar section rows
        self._set_context_visibility(self._row_grid, True)
        self._set_context_visibility(self._row_zones, supports_zones)
        self._set_context_visibility(self._row_dlines, supports_dlines)
        self._set_context_visibility(self._row_fill, supports_fill)
        self._set_context_visibility(self._row_fill_labels, supports_fill)
        self._set_context_visibility(self._row_markers, supports_markers)
        self._set_context_visibility(self._row_k_labels, supports_k_units)
        self._set_context_visibility(self._row_k_log, supports_k_units)
        self._set_context_visibility(self._row_k_label_size, supports_k_units)

        self._set_context_visibility(self._sect_curve_color, not is_k_plot)
        self._set_context_visibility(self._color_container, not is_k_plot)
        self._set_context_visibility(self._sect_units, supports_k_units)
        self._set_context_visibility(self._row_units, supports_k_units)

        display_section_visible = any(
            not row.isHidden()
            for row in (
                self._row_grid,
                self._row_zones,
                self._row_dlines,
                self._row_fill,
                self._row_fill_labels,
                self._row_markers,
                self._row_k_labels,
                self._row_k_log,
            )
        )
        self._set_context_visibility(self._sect_display, display_section_visible)

        axis_section_visible = any(
            not row.isHidden()
            for row in (self._row_xmin, self._row_xmax, self._row_ymin, self._row_ymax)
        )
        self._set_context_visibility(self._sect_axis, axis_section_visible)

    def _apply_plot_options(self):
        """Push workspace toggles into the active plot widget."""
        if not self.plot_widget:
            return
        self.plot_widget.show_grid = self.show_grid
        self.plot_widget.show_legend = self.show_legend
        self.plot_widget.show_classification_zones = self.show_zones
        self.plot_widget.show_d_lines = self.show_dlines
        self.plot_widget.show_markers = self.show_markers
        self.plot_widget.fill_curve = self.fill_curve
        self.plot_widget.fill_zone_labels = self.fill_zone_labels
        self.plot_widget.show_k_value_labels = self.show_k_value_labels
        self.plot_widget.k_value_label_fontsize = self.k_value_label_fontsize
        self.plot_widget.log_k_y_scale = self.log_k_y_scale

    # ── Plot logic (preserved from original) ───────────────────

    def refresh_plot(self):
        if not self.plot_widget:
            return

        self._update_contextual_controls()
        self._apply_plot_options()

        if self.current_plot_type == "distribution":
            self.plot_widget.update_plot(
                self.dataset.particle_sizes,
                self.dataset.percent_passing,
                self.dataset.sample_name,
                grain_size_data=self.dataset,
            )
        elif self.current_plot_type == "k-values":
            if self.k_results:
                self.plot_widget.flagged_methods = set(self.flagged_methods)
                self.plot_widget.plot_k_values_only(self.k_results)
            else:
                self.plot_widget.figure.clear()
                ax = self.plot_widget.figure.add_subplot(1, 1, 1)
                self.plot_widget.current_ax = ax
                self.plot_widget.grain_size_ax = None
                self.plot_widget.k_value_ax = ax
                self.plot_widget.active_axes = [ax]
                ax.text(0.5, 0.5,
                        'Please calculate K-values first\n(Go to Results tab and click Recalculate)',
                        transform=ax.transAxes, ha='center', va='center',
                        fontsize=12, color='gray')
                ax.set_xticks([])
                ax.set_yticks([])
                self.plot_widget.canvas.draw()
        elif self.current_plot_type == "combined":
            self.plot_widget.update_plot(
                self.dataset.particle_sizes,
                self.dataset.percent_passing,
                self.dataset.sample_name,
                grain_size_data=self.dataset,
            )
            self.plot_widget.flagged_methods = set(self.flagged_methods)
            self.plot_widget.plot_combined_view(self.k_results)
        elif self.current_plot_type == "histogram":
            self._plot_histogram()
        self._sync_axis_inputs_from_ax(getattr(self.plot_widget, 'current_ax', None))
        self._refresh_drawer()

    def _histogram_rows(self) -> list[dict[str, float | str]]:
        scheme = getattr(self.plot_widget, "_scheme", None) if self.plot_widget else None
        pairs = sorted(
            zip(self.dataset.particle_sizes, self.dataset.percent_passing),
            key=lambda pair: pair[0],
            reverse=True,
        )
        rows: list[dict[str, float | str]] = []
        for index, (upper_mm, passing) in enumerate(pairs):
            lower_mm = pairs[index + 1][0] if index + 1 < len(pairs) else 0.0
            next_passing = pairs[index + 1][1] if index + 1 < len(pairs) else 0.0
            weight_pct = max(0.0, float(passing) - float(next_passing))
            fraction = _scheme_fraction_label(float(lower_mm), float(upper_mm), scheme)
            if lower_mm <= 0:
                interval = f"<{_format_mm(float(upper_mm))} mm"
            else:
                interval = f"{_format_mm(float(lower_mm))}-{_format_mm(float(upper_mm))} mm"
            rows.append(
                {
                    "fraction": fraction,
                    "lower_mm": float(lower_mm),
                    "upper_mm": float(upper_mm),
                    "interval": interval,
                    "weight_pct": weight_pct,
                    "tick_label": f"{fraction}\n{interval}",
                }
            )
        return rows

    def _plot_histogram(self):
        if not self.plot_widget:
            return
        self.plot_widget.figure.clear()
        ax = self.plot_widget.figure.add_subplot(111)
        rows = self._histogram_rows()
        weights = np.array([row["weight_pct"] for row in rows], dtype=float)
        tick_labels = [str(row["tick_label"]) for row in rows]
        style = self.plot_widget.current_style if self.plot_widget else None

        if style:
            ax.bar(range(len(rows)), weights,
                   tick_label=tick_labels,
                   color=style.curve_color, alpha=0.8,
                   edgecolor='black', linewidth=0.8)
            scheme = getattr(self.plot_widget, "_scheme", None)
            ax.set_xlabel(f'Particle-size fraction ({_scheme_short_name(scheme)})', fontsize=style.label_fontsize,
                          fontfamily=style.font_family)
            ax.set_ylabel('Weight (%)', fontsize=style.label_fontsize,
                          fontfamily=style.font_family)
            ax.set_title(
                f'Grain Size Histogram - {self.dataset.sample_name}',
                fontsize=style.title_fontsize,
                fontweight=style.title_fontweight,
                fontfamily=style.font_family)
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45,
                               ha='right', fontsize=style.tick_fontsize)
            ax.set_facecolor(style.axes_facecolor)
            ax.tick_params(labelsize=style.tick_fontsize)
            if self.show_grid and style.grid_show:
                ax.grid(True, alpha=style.grid_alpha,
                        linestyle=style.grid_linestyle,
                        color=style.grid_color, linewidth=style.grid_linewidth)
        else:
            ax.bar(range(len(rows)), weights,
                   tick_label=tick_labels)
            scheme = getattr(self.plot_widget, "_scheme", None)
            ax.set_xlabel(f'Particle-size fraction ({_scheme_short_name(scheme)})')
            ax.set_ylabel('Weight (%)')
            ax.set_title(
                f'Grain Size Histogram - {self.dataset.sample_name}')
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45,
                               ha='right')
            ax.grid(self.show_grid, alpha=0.3)

        self.plot_widget.current_ax = ax
        self.plot_widget.grain_size_ax = ax
        self.plot_widget.k_value_ax = None
        self.plot_widget.active_axes = [ax]
        if style:
            apply_legend_aware_layout(self.plot_widget.figure, style)
        else:
            self.plot_widget.figure.tight_layout()
        self.plot_widget.canvas.draw()
        self._sync_axis_inputs_from_ax(ax)

    # ── Zoom ───────────────────────────────────────────────────

    def _refresh_drawer(self) -> None:
        if not hasattr(self, "_drawer_table"):
            return
        title, headers, rows = self._active_plot_table()
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

        self._drawer_table.resizeColumnsToContents()
        for row_index in range(len(rows)):
            self._drawer_table.setRowHeight(row_index, 24)

    def _active_plot_table(self) -> tuple[str, list[str], list[tuple]]:
        if self.current_plot_type == "histogram":
            return self._histogram_table()
        if self.current_plot_type == "k-values":
            return self._k_values_table()
        if self.current_plot_type == "combined":
            return self._combined_table()
        return self._distribution_table("Distribution curve data")

    def _distribution_table(self, title: str) -> tuple[str, list[str], list[tuple]]:
        headers = ["Particle size (mm)", "Percent passing (%)"]
        rows = [
            (self._fmt_numeric(size), self._fmt_numeric(passing))
            for size, passing in zip(self.dataset.particle_sizes, self.dataset.percent_passing)
        ]
        return title, headers, rows

    def _histogram_table(self) -> tuple[str, list[str], list[tuple]]:
        scheme = getattr(self.plot_widget, "_scheme", None) if self.plot_widget else None
        headers = [
            f"Fraction ({_scheme_short_name(scheme)})",
            "Lower size (mm)",
            "Upper size (mm)",
            "Interval",
            "Weight (%)",
        ]
        rows = [
            (
                row["fraction"],
                self._fmt_numeric(row["lower_mm"]),
                self._fmt_numeric(row["upper_mm"]),
                row["interval"],
                self._fmt_numeric(row["weight_pct"]),
            )
            for row in self._histogram_rows()
        ]
        return "Grain-size histogram data", headers, rows

    def _k_values_table(self) -> tuple[str, list[str], list[tuple]]:
        unit = self._unit_combo.currentData() or get_default_plot_unit()
        symbol = HydraulicConductivityConverter.UNIT_SYMBOLS[unit]
        headers = ["Method", f"K ({symbol})", "Status"]
        rows: list[tuple] = []
        for method, value_m_s in self.k_results.items():
            display_value = HydraulicConductivityConverter.convert_from_m_per_s(
                value_m_s, unit
            )
            rows.append((
                method,
                HydraulicConductivityConverter.DISPLAY_FORMATS[unit].format(display_value),
                "Warning" if method in self.flagged_methods else "OK",
            ))
        if not rows:
            rows.append(("No K-values calculated", "", ""))
        return "K-value bar chart data", headers, rows

    def _combined_table(self) -> tuple[str, list[str], list[tuple]]:
        unit = self._unit_combo.currentData() or get_default_plot_unit()
        symbol = HydraulicConductivityConverter.UNIT_SYMBOLS[unit]
        headers = [
            "Panel",
            "Item",
            "Particle size (mm)",
            "Percent passing (%)",
            f"K ({symbol})",
            "Status",
        ]
        rows: list[tuple] = [
            (
                "Distribution",
                "",
                self._fmt_numeric(size),
                self._fmt_numeric(passing),
                "",
                "",
            )
            for size, passing in zip(self.dataset.particle_sizes, self.dataset.percent_passing)
        ]
        for method, value_m_s in self.k_results.items():
            display_value = HydraulicConductivityConverter.convert_from_m_per_s(
                value_m_s, unit
            )
            rows.append((
                "K values",
                method,
                "",
                "",
                HydraulicConductivityConverter.DISPLAY_FORMATS[unit].format(display_value),
                "Warning" if method in self.flagged_methods else "OK",
            ))
        return "Combined plot data", headers, rows

    @staticmethod
    def _fmt_numeric(value) -> str:
        try:
            return f"{float(value):.6g}"
        except (TypeError, ValueError):
            return str(value)

    def _sync_axis_inputs_from_ax(self, target_ax) -> None:
        """Reflect the active axes limits in the sidebar controls."""
        if not target_ax:
            return
        xlim = target_ax.get_xlim()
        ylim = target_ax.get_ylim()
        self._in_xmin.setText(f"{xlim[0]:.6g}")
        self._in_xmax.setText(f"{xlim[1]:.6g}")
        self._in_ymin.setText(f"{ylim[0]:.6g}")
        self._in_ymax.setText(f"{ylim[1]:.6g}")

    @staticmethod
    def _zoom_axis_limits(limits, scale: str, factor: float) -> tuple[float, float]:
        """Zoom a linear or log axis around its center by the given factor."""
        lo, hi = limits
        if scale == 'log' and lo > 0 and hi > 0:
            lo_log = math.log10(lo)
            hi_log = math.log10(hi)
            center_log = (lo_log + hi_log) / 2
            half_span = (hi_log - lo_log) * factor / 2
            return 10 ** (center_log - half_span), 10 ** (center_log + half_span)

        center = (lo + hi) / 2
        half_range = (hi - lo) * factor / 2
        new_lo = center - half_range
        new_hi = center + half_range
        if lo >= 0 and new_lo < 0:
            new_lo = 0
        return new_lo, new_hi

    def zoom_in(self):
        if self.plot_widget:
            self.plot_widget.interactions.zoom_current(0.8)

    def zoom_out(self):
        if self.plot_widget:
            self.plot_widget.interactions.zoom_current(1.2)

    def reset_view(self):
        if self.plot_widget:
            self.plot_widget.reset_view()

    # ── Public API (unchanged interface) ───────────────────────

    def update_plot(self, particle_sizes, percent_passing, sample_name):
        if self.plot_widget:
            self.plot_widget.update_plot(
                particle_sizes, percent_passing, sample_name, grain_size_data=self.dataset)
            self._sync_axis_inputs_from_ax(getattr(self.plot_widget, 'current_ax', None))
            self._refresh_drawer()

    def set_scheme(self, scheme) -> None:
        """Update classification scheme; redraw via refresh_plot() if zones are visible."""
        if self.plot_widget:
            self.plot_widget._scheme = scheme
        if self.show_zones or self.current_plot_type == "histogram":
            self.refresh_plot()
        else:
            self._refresh_drawer()

    def add_k_results(self, k_results: Dict[str, float],
                      flagged_methods=None):
        self.k_results = k_results
        self.flagged_methods = set(flagged_methods or [])
        if self.plot_widget:
            self.plot_widget.flagged_methods = set(self.flagged_methods)
        if self.current_plot_type in ["combined", "k-values"]:
            self.refresh_plot()
        else:
            self._refresh_drawer()

    @staticmethod
    def _with_extension(file_path: str, extension: str) -> str:
        suffix = f".{extension.lower().lstrip('.')}"
        return file_path if file_path.lower().endswith(suffix) else f"{file_path}{suffix}"

    def export_plot(self, format: str):
        if not self.plot_widget:
            return
        normalized_format = format.lower().lstrip(".")
        file_filter = {
            "png": "PNG Files (*.png)",
            "svg": "SVG Files (*.svg)",
        }
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export Plot as {normalized_format.upper()}",
            f"{self.dataset.sample_name}_plot.{normalized_format}",
            file_filter.get(normalized_format, "All Files (*)"),
        )
        if file_path:
            try:
                file_path = self._with_extension(file_path, normalized_format)
                self.plot_widget.figure.savefig(
                    file_path,
                    format=normalized_format,
                    dpi=300,
                    bbox_inches='tight',
                    facecolor=self.plot_widget.figure.get_facecolor(),
                )
                self.plot_exported.emit(file_path)
                QMessageBox.information(
                    self, "Export Successful",
                    f"Plot exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error",
                    f"Failed to export plot:\n{str(e)}")

    def export_data(self):
        self._refresh_drawer()
        title = self._drawer_title_text or "Plot data"
        filename_title = re.sub(r"[^A-Za-z0-9_]+", "_", title).strip("_").lower()
        filename_title = filename_title or "plot_data"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {title} as CSV",
            f"{self.dataset.sample_name}_{filename_title}.csv",
            "CSV Files (*.csv)",
        )
        if file_path:
            try:
                file_path = self._with_extension(file_path, "csv")
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(self._drawer_headers)
                    writer.writerows(self._drawer_rows)
                QMessageBox.information(
                    self, "Export Successful",
                    f"{title} exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error",
                    f"Failed to export data:\n{str(e)}")
