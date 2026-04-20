"""
Plot workspace with styled inner toolbar, collapsible sidebar, and chart area.

Matches the design concept in 02_tabs.html / _shared.css (.pw-* classes).
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QComboBox,
    QPushButton, QLabel, QFileDialog, QMessageBox, QLineEdit,
    QSizePolicy, QButtonGroup, QSpinBox, QDoubleSpinBox, QScrollArea,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize,
)
from typing import Optional, Dict, Set
import dataclasses
import math
import numpy as np

from data_loader import GrainSizeData
from .plot_widget import PlotWidget
from .plot_styles import PlotStyle, get_style, get_available_style_names
from .toggle_switch import ToggleSwitch
from .theme import C, F, SZ, icon
from .collapsible_section import CollapsibleSection
from unit_conversions import HydraulicConductivityUnit, HydraulicConductivityConverter

# Legend placement options exposed in the sidebar.
# Each entry is (matplotlib_loc, bbox_to_anchor_or_None, display_label).
# bbox_to_anchor=None → inside the axes (standard matplotlib loc).
# bbox_to_anchor set → anchored relative to the axes, which puts the legend
# outside the plot. See plot_styles.PlotStyle.legend_bbox_to_anchor.
_LEGEND_LOCATIONS: list[tuple[str, Optional[tuple[float, float]], str]] = [
    ("best",         None,          "Best (auto)"),
    ("upper left",   None,          "Inside — upper left"),
    ("upper right",  None,          "Inside — upper right"),
    ("lower left",   None,          "Inside — lower left"),
    ("lower right",  None,          "Inside — lower right"),
    ("center left",  None,          "Inside — center left"),
    ("center right", None,          "Inside — center right"),
    ("upper center", None,          "Inside — upper center"),
    ("lower center", None,          "Inside — lower center"),
    ("center left",  (1.02, 0.5),   "Outside — right"),
    ("center right", (-0.02, 0.5),  "Outside — left"),
    ("upper center", (0.5, -0.14),  "Outside — below"),
    ("lower center", (0.5, 1.02),   "Outside — above"),
]


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

        # Plot settings
        self.current_plot_type = "distribution"
        self.show_grid = True
        self.show_legend = True
        self.show_markers = False
        self.show_zones = False
        self.show_dlines = False
        self.fill_curve = False
        self.fill_zone_labels = False
        self.log_x_scale = True

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
        self._more_plots.addItems(["More Plots…", "Combined", "Cumulative", "Histogram"])
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
        self._style_sel.setCurrentText("Professional")
        self._style_sel.setToolTip("Plot style")
        self._style_sel.currentTextChanged.connect(self._on_style_changed)
        lay.addWidget(self._style_sel)

        lay.addWidget(_pw_sep())

        # ── Sidebar toggle ──
        self._tb_sidebar_btn = _pw_chk(" Controls", "Toggle controls panel", False, "fa6s.sliders")
        self._tb_sidebar_btn.clicked.connect(self._toggle_sidebar)
        lay.addWidget(self._tb_sidebar_btn)

        lay.addWidget(_pw_sep())

        # ── Toggle checks ──
        self._chk_grid = _pw_chk("Grid", "Toggle grid", True, "fa6s.hashtag")
        self._chk_legend = _pw_chk("Legend", "Toggle legend", True, "fa6s.list")
        self._chk_zones = _pw_chk("Zones", "Toggle soil zones", False, "fa6s.layer-group")
        self._chk_dlines = _pw_chk("D-lines", "Show D-value lines", False, "fa6s.crosshairs")

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
        self.plot_widget.set_display_unit(HydraulicConductivityUnit.M_PER_DAY)
        self.plot_widget.axes_view_changed.connect(self._sync_axis_inputs_from_ax)
        chart_lay.addWidget(self.plot_widget, 1)

        # Toggle handle — absolute overlay at left edge, vertically centered
        self._toggle_handle = QPushButton(self._chart_area)
        self._toggle_handle.setObjectName("pw-toggle-handle")
        self._toggle_handle.setIcon(icon("fa6s.chevron-right", C.TEXT_MID, 8))
        self._toggle_handle.setIconSize(QSize(8, 8))
        self._toggle_handle.setToolTip("Toggle sidebar")
        self._toggle_handle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_handle.clicked.connect(self._toggle_sidebar)
        self._toggle_handle.raise_()  # on top of plot

        body_lay.addWidget(self._sidebar)
        body_lay.addWidget(self._chart_area, 1)

        # Sidebar collapse animation
        self._sidebar_anim = QPropertyAnimation(self._sidebar, b"maximumWidth")
        self._sidebar_anim.setDuration(200)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._sidebar_anim.valueChanged.connect(lambda _value: self._position_toggle_handle())

        return body

    def resizeEvent(self, event):
        """Reposition the toggle handle when the chart area resizes."""
        super().resizeEvent(event)
        self._position_toggle_handle()

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
            ("Show D10 / D30 / D60", False, "_row_dlines",      "_sw_dlines"),
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
        default_index = list(all_units.keys()).index(HydraulicConductivityUnit.M_PER_DAY)
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
        btn_svg = QPushButton("Export as SVG")
        btn_svg.setProperty("pw-btn", True)
        btn_svg.clicked.connect(lambda: self.export_plot("svg"))
        btn_data = QPushButton("Export Data")
        btn_data.setProperty("pw-btn", True)
        btn_data.clicked.connect(self.export_data)
        export_lay.addWidget(btn_svg)
        export_lay.addWidget(btn_data)
        self._sect_export.add_widget(export_w)
        lay.addWidget(self._sect_export)

        lay.addStretch(1)
        self._update_contextual_controls()
        return sidebar

    # ── Sidebar sub-builders ───────────────────────────────────

    def _axis_row(self, label: str, default: str):
        row = QWidget()
        row.setStyleSheet(f"border-bottom: 1px solid rgba(212,196,168,0.4);")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(5)
        lbl = QLabel(label)
        lbl.setProperty("pws-lbl", True)
        inp = QLineEdit(default)
        inp.setProperty("pws-in", True)
        inp.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(lbl, 1)
        lay.addWidget(inp, 0)
        return row, inp, lbl

    def _toggle_row(self, label: str, checked: bool):
        """Return (row_widget, ToggleSwitch) — caller adds to layout."""
        row = QWidget()
        row.setStyleSheet("border-bottom: 1px solid rgba(212,196,168,0.4);")
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(5)
        lbl = QLabel(label)
        lbl.setProperty("pws-lbl", True)
        sw = ToggleSwitch(checked)
        sw.toggled.connect(self._on_sidebar_toggle_changed)
        lay.addWidget(lbl, 1)
        lay.addWidget(sw, 0)
        return row, sw

    def _combo_row(self, label: str, items: list[str]):
        """Row with a label stacked above a full-width QComboBox.

        Stacked because combo items like "Inside — upper left" would overflow
        a narrow sidebar when laid out beside a label.
        """
        row = QWidget()
        row.setStyleSheet("border-bottom: 1px solid rgba(212,196,168,0.4);")
        lay = QVBoxLayout(row)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(3)
        lbl = QLabel(label)
        lbl.setProperty("pws-lbl", True)
        combo = QComboBox()
        combo.setObjectName("pw-style-sel")
        combo.addItems(items)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(lbl)
        lay.addWidget(combo)
        return row, combo

    def _spin_row(self, label: str, minimum: int, maximum: int):
        """Row with a label on the left and a QSpinBox on the right."""
        row = QWidget()
        row.setStyleSheet("border-bottom: 1px solid rgba(212,196,168,0.4);")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(6)
        lbl = QLabel(label)
        lbl.setProperty("pws-lbl", True)
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setFixedWidth(72)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(lbl, 1)
        lay.addWidget(spin, 0)
        return row, spin

    def _dspin_row(self, label: str, minimum: float, maximum: float,
                   step: float, decimals: int):
        """Row with a label on the left and a QDoubleSpinBox on the right."""
        row = QWidget()
        row.setStyleSheet("border-bottom: 1px solid rgba(212,196,168,0.4);")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(6)
        lbl = QLabel(label)
        lbl.setProperty("pws-lbl", True)
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.setFixedWidth(72)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(lbl, 1)
        lay.addWidget(spin, 0)
        return row, spin

    def _add_color_row(self, name: str, color: str):
        row = QWidget()
        row.setStyleSheet(f"border-bottom: 1px solid rgba(212,196,168,0.4);")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(5)
        lbl = QLabel(name)
        lbl.setProperty("pws-lbl", True)
        dot = QLabel()
        dot.setFixedSize(12, 12)
        dot.setStyleSheet(
            f"background: {color}; border-radius: 6px; "
            f"border: 1px solid rgba(0,0,0,0.1);"
        )
        lay.addWidget(lbl, 1)
        lay.addWidget(dot, 0)
        self._color_container_lay.addWidget(row)

    # ── Sidebar toggle ─────────────────────────────────────────

    def _toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        target = SZ.PLOT_SIDEBAR_W if self.sidebar_visible else 0
        self._sidebar_anim.stop()
        self._sidebar_anim.setStartValue(self._sidebar.maximumWidth())
        self._sidebar_anim.setEndValue(target)
        self._sidebar_anim.start()
        self._tb_sidebar_btn.blockSignals(True)
        self._tb_sidebar_btn.setChecked(self.sidebar_visible)
        self._tb_sidebar_btn.blockSignals(False)
        # Update handle chevron direction
        chevron = "fa6s.chevron-left" if self.sidebar_visible else "fa6s.chevron-right"
        self._toggle_handle.setIcon(icon(chevron, C.TEXT_MID, 8))

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
        plot_map = {1: "combined", 2: "cumulative", 3: "histogram"}
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

    def _sync_advanced_style_widgets(self, style: PlotStyle) -> None:
        """Push preset values into the advanced-style widgets without firing signals."""
        widgets = [
            getattr(self, '_legend_loc_combo', None),
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
        self._legend_loc_combo.setCurrentIndex(loc_idx)
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

    def _set_context_visibility(self, widget: QWidget, visible: bool):
        widget.setHidden(not visible)

    def _update_contextual_controls(self):
        """Show only the controls that make sense for the active plot type."""
        plot_type = self.current_plot_type
        is_distribution_like = plot_type in {"distribution", "combined", "cumulative"}
        is_k_plot = plot_type == "k-values"
        supports_k_units = plot_type in {"k-values", "combined"}
        supports_zones = plot_type in {"distribution", "combined", "cumulative"}
        supports_dlines = plot_type in {"distribution", "combined"}
        supports_fill = plot_type in {"distribution", "combined"}
        supports_markers = plot_type in {"distribution", "combined", "cumulative"}

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
            unit = self._unit_combo.currentData() or HydraulicConductivityUnit.M_PER_DAY
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
        elif self.current_plot_type == "cumulative":
            self._plot_cumulative_distribution()
        elif self.current_plot_type == "histogram":
            self._plot_histogram()
        self._sync_axis_inputs_from_ax(getattr(self.plot_widget, 'current_ax', None))

    def _plot_cumulative_distribution(self):
        if not self.plot_widget:
            return
        self.plot_widget.figure.clear()
        ax = self.plot_widget.figure.add_subplot(111)
        if self.show_zones and self.plot_widget:
            self.plot_widget.draw_classification_zones(ax)

        cumulative = np.array(self.dataset.percent_passing)
        sizes = np.array(self.dataset.particle_sizes)
        style = self.plot_widget.current_style if self.plot_widget else None

        if style:
            ax.plot(sizes, cumulative, color=style.curve_color,
                    linewidth=style.curve_linewidth,
                    label=self.dataset.sample_name,
                    marker=self.plot_widget._get_curve_marker(style),
                    markersize=style.curve_markersize,
                    markeredgecolor=style.curve_markeredgecolor,
                    markeredgewidth=style.curve_markeredgewidth)
            ax.set_xlabel('Grain Size (mm)', fontsize=style.label_fontsize,
                          fontfamily=style.font_family)
            ax.set_ylabel('Cumulative Percent Passing (%)',
                          fontsize=style.label_fontsize,
                          fontfamily=style.font_family)
            ax.set_title(f'Cumulative Distribution - {self.dataset.sample_name}',
                         fontsize=style.title_fontsize,
                         fontweight=style.title_fontweight,
                         fontfamily=style.font_family)
            if self.log_x_scale:
                ax.set_xscale('log')
            ax.set_facecolor(style.axes_facecolor)
            ax.tick_params(labelsize=style.tick_fontsize)
            if self.show_grid and style.grid_show:
                ax.grid(True, which='major', alpha=style.grid_alpha,
                        linestyle=style.grid_linestyle,
                        color=style.grid_color, linewidth=style.grid_linewidth)
            if self.show_legend:
                legend_kwargs = dict(
                    loc=style.legend_loc,
                    fontsize=style.legend_fontsize,
                    framealpha=style.legend_framealpha,
                    edgecolor=style.legend_edgecolor,
                )
                if style.legend_bbox_to_anchor is not None:
                    legend_kwargs["bbox_to_anchor"] = style.legend_bbox_to_anchor
                ax.legend(**legend_kwargs)
        else:
            ax.plot(sizes, cumulative, 'g-', linewidth=2,
                    label=self.dataset.sample_name)
            ax.set_xlabel('Grain Size (mm)')
            ax.set_ylabel('Cumulative Percent Passing (%)')
            ax.set_title(
                f'Cumulative Distribution - {self.dataset.sample_name}')
            if self.log_x_scale:
                ax.set_xscale('log')
            ax.grid(self.show_grid, which='both', alpha=0.3)
            if self.show_legend:
                ax.legend()

        self.plot_widget.current_ax = ax
        self.plot_widget.grain_size_ax = ax
        self.plot_widget.k_value_ax = None
        self.plot_widget.active_axes = [ax]
        self.plot_widget.figure.tight_layout()
        self.plot_widget.canvas.draw()
        self._sync_axis_inputs_from_ax(ax)

    def _plot_histogram(self):
        if not self.plot_widget:
            return
        self.plot_widget.figure.clear()
        ax = self.plot_widget.figure.add_subplot(111)
        pairs = sorted(
            zip(self.dataset.particle_sizes, self.dataset.percent_passing),
            key=lambda pair: pair[0],
            reverse=True,
        )
        sizes = np.array([size for size, _ in pairs], dtype=float)
        passing = np.array([passing for _, passing in pairs], dtype=float)
        next_passing = np.append(passing[1:], 0.0)
        freq = np.maximum(0.0, passing - next_passing)
        style = self.plot_widget.current_style if self.plot_widget else None

        if style:
            ax.bar(range(len(sizes)), freq,
                   tick_label=[f"{s:.3f}" for s in sizes],
                   color=style.curve_color, alpha=0.8,
                   edgecolor='black', linewidth=0.8)
            ax.set_xlabel('Grain Size (mm)', fontsize=style.label_fontsize,
                          fontfamily=style.font_family)
            ax.set_ylabel('Frequency (%)', fontsize=style.label_fontsize,
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
            ax.bar(range(len(sizes)), freq,
                   tick_label=[f"{s:.3f}" for s in sizes])
            ax.set_xlabel('Grain Size (mm)')
            ax.set_ylabel('Frequency (%)')
            ax.set_title(
                f'Grain Size Histogram - {self.dataset.sample_name}')
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45,
                               ha='right')
            ax.grid(self.show_grid, alpha=0.3)

        self.plot_widget.current_ax = ax
        self.plot_widget.grain_size_ax = ax
        self.plot_widget.k_value_ax = None
        self.plot_widget.active_axes = [ax]
        self.plot_widget.figure.tight_layout()
        self.plot_widget.canvas.draw()
        self._sync_axis_inputs_from_ax(ax)

    # ── Zoom ───────────────────────────────────────────────────

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

    def set_scheme(self, scheme) -> None:
        """Update classification scheme; redraw via refresh_plot() if zones are visible."""
        if self.plot_widget:
            self.plot_widget._scheme = scheme
        if self.show_zones:
            self.refresh_plot()

    def add_k_results(self, k_results: Dict[str, float],
                      flagged_methods=None):
        self.k_results = k_results
        self.flagged_methods = set(flagged_methods or [])
        if self.plot_widget:
            self.plot_widget.flagged_methods = set(self.flagged_methods)
        if self.current_plot_type in ["combined", "k-values"]:
            self.refresh_plot()

    def export_plot(self, format: str):
        if not self.plot_widget:
            return
        file_filter = {
            "png": "PNG Files (*.png)",
            "svg": "SVG Files (*.svg)",
        }
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export Plot as {format.upper()}",
            f"{self.dataset.sample_name}_plot.{format}",
            file_filter.get(format, "All Files (*)"),
        )
        if file_path:
            try:
                self.plot_widget.figure.savefig(
                    file_path, dpi=300, bbox_inches='tight')
                self.plot_exported.emit(file_path)
                QMessageBox.information(
                    self, "Export Successful",
                    f"Plot exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error",
                    f"Failed to export plot:\n{str(e)}")

    def export_data(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data as CSV",
            f"{self.dataset.sample_name}_data.csv",
            "CSV Files (*.csv)",
        )
        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Grain Size (mm)", "Percent Passing (%)"])
                    for size, passing in zip(
                        self.dataset.particle_sizes,
                        self.dataset.percent_passing,
                    ):
                        writer.writerow([size, passing])
                QMessageBox.information(
                    self, "Export Successful",
                    f"Data exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error",
                    f"Failed to export data:\n{str(e)}")
