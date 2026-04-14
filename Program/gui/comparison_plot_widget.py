"""
Enhanced plot widget for comparison tab with multiple display modes
"""

import math

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton,
    QComboBox, QLabel, QButtonGroup, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from matplotlib.figure import Figure
from matplotlib.patches import Patch
import numpy as np
import warnings
from typing import List, Dict
from .k_plot_helpers import annotate_log_bars, apply_log_bar_limits, format_method_label
from .matplotlib_canvas import FigureCanvas
from .plot_interactions import AxesInteractionController
from .theme import C, apply_matplotlib_style, icon


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
    DEFAULT_METHOD_ORDER = [
        'Hazen', 'Hazen_1892', 'Slichter', 'Terzaghi',
        'Beyer', 'Sauerbrei', 'Kruger', 'Kozeny-Carman',
        'Zunker', 'Zamarin', 'USBR', 'Barr',
        'Alyamani-Sen', 'Chapuis', 'Shepherd', 'Krumbein-Monk',
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Plot settings
        self.current_plot_type = "distribution"
        self.display_mode = "overlay"  # overlay, grid, grouped
        self.grid_layout = (2, 2)  # Default grid size
        self.show_grid = True
        self.show_legend = True
        
        # Data storage
        self.datasets = []
        self.k_results_dict = {}  # dataset_name -> k_results
        self.flagged_methods_dict = {}  # dataset_name -> set(method_name)
        self.current_ax = None
        self._default_limits = {}
        self._pan_state = None
        
        # Color scheme for consistency
        self.dataset_colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
        ]
        
        # Method colors (same as PlotWidget)
        self.method_colors = {
            "Hazen": "#b71c1c",
            "Terzaghi": "#2e7d32",
            "Beyer": "#1565c0",
            "Slichter": "#ef6c00",
            "Kozeny-Carman": "#7b1fa2",
            "Shepherd": "#c2185b",
            "Zunker": "#00acc1",
            "Zamarin": "#fbc02d",
            "USBR": "#6d4c41",
            "Sauerbrei": "#546e7a",
            "Hazen_1892": "#d84315",
            "Kruger": "#4527a0",
            "Barr": "#8d6e63",
            "Alyamani-Sen": "#5d4037",
            "Chapuis": "#ff5722",
            "Krumbein-Monk": "#9c27b0",
        }
        
        self.init_ui()

    def init_ui(self):
        """Initialize the UI"""
        apply_matplotlib_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Create toolbar
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)

        # Create matplotlib figure and canvas
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
        layout.addWidget(self.canvas, 1)
    
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

        self.grid_check = _cmp_chk(" Grid", "Toggle grid", True, "fa6s.hashtag")
        self.grid_check.toggled.connect(self.update_display_options)
        row.addWidget(self.grid_check)

        self.legend_check = _cmp_chk(" Legend", "Toggle legend", True, "fa6s.list")
        self.legend_check.toggled.connect(self.update_display_options)
        row.addWidget(self.legend_check)

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
        seen = set(method_names)
        ordered = [name for name in self.DEFAULT_METHOD_ORDER if name in seen]
        extras = sorted(seen.difference(self.DEFAULT_METHOD_ORDER))
        return ordered + extras

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
        ax.legend(handles, labels, loc='best', fontsize=8)

    def _overlay_value_labels_enabled(self, n_methods: int, n_datasets: int) -> bool:
        """Avoid unreadable label walls in dense comparison overlays."""
        return n_datasets <= 4 and (n_methods * n_datasets) <= 36
    
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
        """Update display options"""
        self.show_grid = self.grid_check.isChecked()
        self.show_legend = self.legend_check.isChecked()
        self.refresh_plot()
    
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
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "error",
                    message="Tight layout not applied.*",
                    category=UserWarning,
                )
                self.figure.tight_layout(pad=0.9)
        except UserWarning:
            self.figure.subplots_adjust(
                left=0.08,
                right=0.98,
                top=0.94,
                bottom=0.16,
                wspace=0.28,
                hspace=0.34,
            )

    def _on_canvas_click(self, event) -> None:
        """Track the last axes the user interacted with and handle reset/pan starts."""
        ax = getattr(event, "inaxes", None)
        self._set_current_ax(ax)
        if ax is None:
            return
        if getattr(event, "dblclick", False):
            self._reset_axes_view(ax)
            self.canvas.draw()
            return
        if self._event_has_shift(event) and getattr(event, "button", None) == 1:
            self._start_pan(ax, event)

    def _set_current_ax(self, ax) -> None:
        """Remember the active axes when it belongs to the current figure."""
        new_ax = ax if ax in self.figure.axes else None
        if new_ax is self.current_ax:
            return
        self.current_ax = new_ax
        self._apply_active_axes_styling()
        self.canvas.draw_idle()

    def _prime_current_ax(self) -> None:
        """Default the active axes after a plot rebuild."""
        if self.current_ax not in self.figure.axes:
            self.current_ax = self.figure.axes[0] if self.figure.axes else None

    @staticmethod
    def _zoom_axis_limits(limits, scale: str, factor: float) -> tuple[float, float]:
        """Zoom a linear or log axis around its center by the given factor."""
        lo, hi = limits
        reversed_axis = hi < lo
        if reversed_axis:
            lo, hi = hi, lo

        if scale == 'log' and lo > 0 and hi > 0:
            lo_log = math.log10(lo)
            hi_log = math.log10(hi)
            center_log = (lo_log + hi_log) / 2
            half_span = (hi_log - lo_log) * factor / 2
            new_lo = 10 ** (center_log - half_span)
            new_hi = 10 ** (center_log + half_span)
        else:
            center = (lo + hi) / 2
            half_range = (hi - lo) * factor / 2
            new_lo = center - half_range
            new_hi = center + half_range
            if lo >= 0 and new_lo < 0:
                new_lo = 0

        return (new_hi, new_lo) if reversed_axis else (new_lo, new_hi)

    def _zoom_target_axes(self):
        """Zoom the active subplot when possible, otherwise fall back to the first axes."""
        if self.current_ax in self.figure.axes:
            return [self.current_ax]
        if self.figure.axes:
            self._set_current_ax(self.figure.axes[0])
            return [self.current_ax]
        return []

    @staticmethod
    def _event_has_shift(event) -> bool:
        key = getattr(event, "key", None)
        if isinstance(key, str):
            return "shift" in key.lower().split("+")
        return False

    def _capture_default_limits(self) -> None:
        """Store default limits for per-subplot reset operations."""
        self._default_limits = {
            ax: {"xlim": ax.get_xlim(), "ylim": ax.get_ylim()}
            for ax in self.figure.axes
        }

    def _apply_active_axes_styling(self) -> None:
        """Emphasize the active subplot without overwhelming the chart."""
        for ax in self.figure.axes:
            is_active = ax is self.current_ax
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.6 if is_active else 0.8)
                spine.set_edgecolor(C.OLIVE if is_active else "#cfc5b4")
            title = ax.title
            title.set_color(C.TEXT if is_active else C.TEXT_MID)

    def _reset_axes_view(self, ax) -> None:
        """Reset a single axes to its stored default limits."""
        defaults = self._default_limits.get(ax)
        if not defaults:
            return
        ax.set_xlim(*defaults["xlim"])
        ax.set_ylim(*defaults["ylim"])
        self._set_current_ax(ax)

    def _start_pan(self, ax, event) -> None:
        """Begin a shift-drag pan operation on the active subplot."""
        if event.xdata is None or event.ydata is None:
            return
        self._pan_state = {
            "ax": ax,
            "xdata": event.xdata,
            "ydata": event.ydata,
            "xlim": ax.get_xlim(),
            "ylim": ax.get_ylim(),
        }

    @staticmethod
    def _pan_axis_limits(limits, scale: str, start_data: float, current_data: float) -> tuple[float, float]:
        """Pan a linear or log axis based on pointer movement."""
        lo, hi = limits
        reversed_axis = hi < lo
        if reversed_axis:
            lo, hi = hi, lo

        if scale == 'log' and lo > 0 and hi > 0 and start_data and current_data and start_data > 0 and current_data > 0:
            factor = start_data / current_data
            new_lo = lo * factor
            new_hi = hi * factor
        else:
            delta = start_data - current_data
            new_lo = lo + delta
            new_hi = hi + delta
            if lo >= 0 and new_lo < 0:
                shift = -new_lo
                new_lo += shift
                new_hi += shift

        return (new_hi, new_lo) if reversed_axis else (new_lo, new_hi)

    def _on_canvas_scroll(self, event) -> None:
        """Zoom the hovered subplot with the mouse wheel."""
        ax = getattr(event, "inaxes", None)
        if ax not in self.figure.axes:
            return
        self._set_current_ax(ax)
        step = getattr(event, "step", 0)
        if not step:
            step = 1 if getattr(event, "button", "") == "up" else -1
        factor = 0.88 if step > 0 else 1.14
        ax.set_xlim(*self._zoom_axis_limits(ax.get_xlim(), ax.get_xscale(), factor))
        ax.set_ylim(*self._zoom_axis_limits(ax.get_ylim(), ax.get_yscale(), factor))
        self.canvas.draw()

    def _on_canvas_motion(self, event) -> None:
        """Pan the active subplot while shift-dragging."""
        if not self._pan_state or event.xdata is None or event.ydata is None:
            return
        ax = self._pan_state["ax"]
        if ax not in self.figure.axes:
            self._pan_state = None
            return
        ax.set_xlim(*self._pan_axis_limits(self._pan_state["xlim"], ax.get_xscale(), self._pan_state["xdata"], event.xdata))
        ax.set_ylim(*self._pan_axis_limits(self._pan_state["ylim"], ax.get_yscale(), self._pan_state["ydata"], event.ydata))
        self.canvas.draw_idle()

    def _on_canvas_release(self, _event) -> None:
        """End any active pan gesture."""
        self._pan_state = None
    
    def plot_distribution(self):
        """Plot grain size distribution"""
        if self.display_mode == "overlay":
            ax = self.figure.add_subplot(1, 1, 1)
            self.plot_distribution_overlay(ax)
        else:  # grid mode
            self.plot_distribution_grid()
    
    def plot_distribution_overlay(self, ax):
        """Plot all distributions on single axes"""
        for i, dataset in enumerate(self.datasets):
            color = self.dataset_colors[i % len(self.dataset_colors)]
            ax.semilogx(dataset.particle_sizes, dataset.percent_passing,
                       linewidth=2, label=dataset.sample_name, color=color,
                       marker='o' if len(dataset.particle_sizes) < 20 else None,
                       markersize=4)
        
        ax.set_xlabel('Grain Size (mm)', fontsize=10)
        ax.set_ylabel('Percent Passing (%)', fontsize=10)
        ax.set_title('Grain Size Distribution Comparison', fontsize=12, fontweight='bold')
        ax.set_xlim(0.001, 100)
        ax.set_ylim(0, 100)
        
        if self.show_grid:
            ax.grid(True, which='both', alpha=0.3)
        if self.show_legend:
            ax.legend(loc='best', fontsize=8)
    
    def plot_distribution_grid(self):
        """Plot distributions in grid layout"""
        rows, cols = self.grid_layout
        
        for i, dataset in enumerate(self.datasets):
            if i >= rows * cols:
                break
                
            ax = self.figure.add_subplot(rows, cols, i + 1)
            color = self.dataset_colors[i % len(self.dataset_colors)]
            
            ax.semilogx(dataset.particle_sizes, dataset.percent_passing,
                       linewidth=2, color=color,
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
        """Plot K-values as grouped bars"""
        ax = self.figure.add_subplot(1, 1, 1)
        ax.set_axisbelow(True)
        
        # Get all unique methods
        all_methods = set()
        for k_dict in self.k_results_dict.values():
            all_methods.update(k_dict.keys())
        methods = self._ordered_methods(all_methods)
        
        # Prepare data
        n_datasets = len(self.k_results_dict)
        n_methods = len(methods)
        bar_width = 0.8 / n_datasets
        show_value_labels = self._overlay_value_labels_enabled(n_methods, n_datasets)
        label_bars = []
        label_texts = []
        label_levels = []
        positive_values = []
        
        # Plot bars for each dataset
        has_flagged = False
        for i, (name, k_dict) in enumerate(self.k_results_dict.items()):
            values = [k_dict.get(method, 0) for method in methods]
            positions = np.arange(n_methods) + i * bar_width
            color = self.dataset_colors[i % len(self.dataset_colors)]
            flagged_methods = self.flagged_methods_dict.get(name, set())
            
            bars = ax.bar(positions, values, bar_width, label=name,
                          color=color, alpha=0.8, edgecolor='black', linewidth=0.5)
            
            for bar, method, val in zip(bars, methods, values):
                flagged = method in flagged_methods
                has_flagged = has_flagged or flagged
                self._style_k_bar(bar, color, flagged)
                if val > 0:
                    positive_values.append(val)
                    if show_value_labels:
                        label_bars.append(bar)
                        label_texts.append(f'{val:.1e}')
                        label_levels.append(i)
        
        ax.set_xlabel('Method', fontsize=10)
        ax.set_ylabel('K (m/s)', fontsize=10)
        ax.set_title('Hydraulic Conductivity Comparison', fontsize=12, fontweight='bold')
        ax.set_xticks(np.arange(n_methods) + bar_width * (n_datasets - 1) / 2)
        ax.set_xticklabels(
            [format_method_label(method, compact=True) for method in methods],
            rotation=45,
            ha='right',
            fontsize=8,
        )
        apply_log_bar_limits(ax, positive_values, max_label_level=max(label_levels, default=0))
        if show_value_labels:
            annotate_log_bars(
                ax,
                label_bars,
                label_texts,
                level_indices=label_levels,
                fontsize=5.75 if n_datasets > 2 else 6.0,
                add_bbox=n_datasets > 1,
            )
        
        if self.show_grid:
            ax.grid(True, axis='y', alpha=0.3)
        if self.show_legend:
            if has_flagged:
                self._add_flagged_legend_handle(ax)
            else:
                ax.legend(loc='best', fontsize=8)
    
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
                ax.legend(loc='best', fontsize=7, ncol=2)
    
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
        
        for i, dataset in enumerate(self.datasets):
            if i >= rows * cols:
                break
            
            # Create two subplots for each dataset
            ax1 = self.figure.add_subplot(rows, cols*2, i*2 + 1)
            ax2 = self.figure.add_subplot(rows, cols*2, i*2 + 2)
            
            color = self.dataset_colors[i % len(self.dataset_colors)]
            
            # Plot distribution
            ax1.semilogx(dataset.particle_sizes, dataset.percent_passing,
                        linewidth=1.5, color=color, markersize=2)
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
        
        for i, dataset in enumerate(self.datasets):
            if i >= rows * cols:
                break
            
            ax = self.figure.add_subplot(rows, cols, i + 1)
            color = self.dataset_colors[i % len(self.dataset_colors)]
            
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
