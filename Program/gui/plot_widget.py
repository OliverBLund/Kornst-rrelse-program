"""
Plot widget with real matplotlib integration for grain size distribution visualization
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from matplotlib.figure import Figure
import numpy as np
from typing import Optional, List, Dict
from unit_conversions import HydraulicConductivityConverter, HydraulicConductivityUnit, get_default_plot_unit
from .plot_styles import PlotStyle, PROFESSIONAL_STYLE
from .matplotlib_canvas import FigureCanvas, NavigationToolbar
from .plot_interactions import AxesInteractionController
from .plot_constants import METHOD_COLORS
from .plot_renderers import (
    apply_grid_style,
    apply_legend_aware_layout,
    render_grain_size_distribution,
    render_k_bar_chart,
)
from .plot_text_options import PlotTextOptions, plot_text_options_to_renderer_kwargs
from .theme import C, apply_matplotlib_style
from grain_classification import ISO14688


class PlotWidget(QWidget):
    axes_view_changed = pyqtSignal(object)
    _DIST_X_PADDING_FACTOR = 2.5
    _DIST_Y_MAX = 102.0

    def __init__(self):
        super().__init__()
        self.figure = None
        self.canvas = None
        self.toolbar = None
        self.grain_size_ax = None
        self.k_value_ax = None
        self.active_axes = []
        self.current_ax = None
        
        # Data storage
        self.grain_data = None
        self.grain_size_data = None
        self.k_results = {}
        self.flagged_methods: set[str] = set()
        self.sample_name = "No data"

        # Unit display settings
        self.display_unit = get_default_plot_unit()  # Default to m/d as specified

        # Display options
        self.show_grid = True
        self.show_legend = True
        self.show_classification_zones = False
        self.fill_zone_labels = False
        self._scheme = ISO14688
        self.show_d_lines = True
        self.show_markers = False
        self.fill_curve = False
        self.curve_color_override = None  # per-sample colour from the sidebar
        self.show_k_value_labels = True
        self.k_value_label_fontsize = 8
        self.log_k_y_scale = False

        # Style system
        self.current_style = PROFESSIONAL_STYLE
        self.plot_text_options = PlotTextOptions()

        # Method colors — shared across app + reports
        self.method_colors = METHOD_COLORS
        
        self.setup_ui()

    def _reference_k_values_for_display(
        self,
        methods: list[str],
        k_values_display: list[float],
    ) -> list[float]:
        """Return displayed K values that are included in OK-only K means."""
        flagged = set(getattr(self, "flagged_methods", set()) or set())
        return [
            value
            for method, value in zip(methods, k_values_display)
            if method not in flagged and value is not None and value > 0
        ]
        
    def setup_ui(self):
        """Setup the matplotlib widget layout"""
        # Apply theme-consistent rcParams (fonts, colors, grid) before any figure is created
        apply_matplotlib_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create matplotlib figure
        self.figure = Figure(figsize=(12, 8), tight_layout=True)
        self.figure.patch.set_facecolor(self.current_style.figure_facecolor)

        # Create canvas
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background: transparent;")

        # Hide matplotlib toolbar (replaced by our custom pw-toolbar)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setVisible(False)

        self.interactions = AxesInteractionController(
            figure=self.figure,
            canvas=self.canvas,
            get_current_ax=lambda: self.current_ax,
            set_current_ax=lambda ax: setattr(self, "current_ax", ax),
            get_active_axes=lambda: self.active_axes,
            on_view_changed=lambda ax: self.axes_view_changed.emit(ax),
        )
        self.canvas.mpl_connect("button_press_event", self.interactions.on_click)
        self.canvas.mpl_connect("scroll_event", self.interactions.on_scroll)
        self.canvas.mpl_connect("motion_notify_event", self.interactions.on_motion)
        self.canvas.mpl_connect("button_release_event", self.interactions.on_release)

        layout.addWidget(self.canvas)

        # Initialize empty plots
        self.setup_plots()

    def set_style(self, style: PlotStyle):
        """Apply a new plot style and redraw."""
        self.current_style = style
        self.figure.patch.set_facecolor(style.figure_facecolor)

    def setup_plots(self):
        """Setup initial empty plot area."""
        style = self.current_style
        self.figure.clear()
        self.figure.patch.set_facecolor(style.figure_facecolor)
        ax = self.figure.add_subplot(1, 1, 1)
        self.current_ax = ax
        self.grain_size_ax = ax
        self.k_value_ax = None
        self.active_axes = [ax]

        ax.set_xlabel('Grain Diameter (mm)')
        ax.set_ylabel('Cumulative % Passing')
        ax.set_title('Grain Size Distribution Curve')
        ax.set_xscale('log')
        ax.set_xlim(0.001, 100)
        ax.set_ylim(0, self._DIST_Y_MAX)
        ax.set_facecolor(style.axes_facecolor)
        apply_grid_style(ax, style, True)

        ax.text(
            0.5, 0.5, 'Load grain size data to view distribution curve',
            transform=ax.transAxes,
            ha='center', va='center', fontsize=11,
            color=C.TEXT_MUTED, fontstyle='italic',
        )

        self.interactions.prime_current_ax()
        self.interactions.capture_default_limits()
        self.interactions.apply_active_axes_styling()
        self.canvas.draw()

    def _get_curve_marker(self, style: PlotStyle):
        """Return the configured curve marker or disable markers entirely."""
        return style.curve_marker if self.show_markers else None

    def set_scheme(self, scheme):
        """Set the classification scheme and trigger a redraw if zones are visible."""
        self._scheme = scheme
        if self.show_classification_zones and self.grain_data:
            diameters, cumulative = self.grain_data
            self.update_plot(diameters, cumulative,
                             self.sample_name, self.grain_size_data)

    def draw_classification_zones(self, ax):
        """Draw grain size classification zones as background bands using active scheme."""
        s = self._scheme
        x_min, x_max = ax.get_xlim()
        zones = [
            {'name': 'Clay',   'min': 0.0001,        'max': s.clay_max,   'color': C.GC_CLAY},
            {'name': 'Silt',   'min': s.clay_max,    'max': s.silt_max,   'color': C.GC_SILT},
            {'name': 'Sand',   'min': s.silt_max,    'max': s.sand_max,   'color': C.GC_SAND},
            {'name': 'Gravel', 'min': s.sand_max,    'max': s.gravel_max, 'color': C.GC_GRAVEL},
            {'name': 'Cobble', 'min': s.gravel_max,  'max': 300,          'color': C.GC_COBBLE},
        ]

        for zone in zones:
            # Skip zones entirely outside the visible range
            if zone['max'] <= x_min or zone['min'] >= x_max:
                continue

            ax.axvspan(zone['min'], zone['max'],
                      color=zone['color'], alpha=0.18,
                      zorder=0)

            # Label at geometric-mean of the VISIBLE portion — clamped to x range
            lo_vis = max(zone['min'], x_min)
            hi_vis = min(zone['max'], x_max)
            mid_point = np.sqrt(lo_vis * hi_vis)
            ax.text(mid_point, 95, zone['name'],
                   ha='center', va='top', fontsize=8,
                   color='#5a4a3a', fontweight='bold', alpha=0.6)

    def update_plot(self, diameters: Optional[List[float]] = None,
                   cumulative: Optional[List[float]] = None,
                   sample_name: str = "Sample",
                   grain_size_data=None):
        """Update grain size distribution plot with real data"""
        if diameters is None or cumulative is None:
            return

        self.grain_data = (diameters, cumulative)
        self.grain_size_data = grain_size_data
        self.sample_name = sample_name

        # Clear figure and create grain size plot
        self.figure.clear()
        self.current_ax = self.figure.add_subplot(1, 1, 1)
        self.grain_size_ax = self.current_ax
        self.k_value_ax = None
        self.active_axes = [self.current_ax]

        # Delegate all drawing to the shared renderer
        render_grain_size_distribution(
            self.current_ax,
            diameters,
            cumulative,
            sample_name=sample_name,
            grain_size_data=grain_size_data,
            style=self.current_style,
            show_d_lines=self.show_d_lines,
            show_markers=self.show_markers,
            show_grid=self.show_grid,
            show_legend=self.show_legend,
            show_classification_zones=self.show_classification_zones,
            classification_scheme=self._scheme,
            fill_curve=self.fill_curve,
            fill_zone_labels=self.fill_zone_labels,
            curve_color=self.curve_color_override,
            **plot_text_options_to_renderer_kwargs(self.plot_text_options),
        )

        apply_legend_aware_layout(self.figure, self.current_style)
        self.interactions.prime_current_ax()
        self.interactions.capture_default_limits()
        self.interactions.apply_active_axes_styling()
        self.canvas.draw()
        
    def add_k_calculation_results(self, k_results: Dict[str, float]):
        """Add K calculation results to existing grain size plot (for combined view)"""
        if not k_results:
            return
            
        self.k_results = k_results
        
        # This method assumes grain size plot exists and adds K-values as secondary info
        # For combined view, we could add a text box or secondary axis
        # For now, just store the results - they'll be displayed when switching to K-values view
        
    def plot_combined_view(self, k_results: Dict[str, float] = None):
        """Display combined grain size and K-values in a single view"""
        if not self.grain_data:
            return

        if k_results:
            self.k_results = k_results

        self.figure.clear()
        ax1 = self.figure.add_subplot(1, 2, 1)
        ax2 = self.figure.add_subplot(1, 2, 2)

        # Left — grain-size distribution via shared renderer
        diameters, cumulative = self.grain_data
        render_grain_size_distribution(
            ax1, diameters, cumulative,
            sample_name=self.sample_name,
            grain_size_data=self.grain_size_data,
            style=self.current_style,
            show_d_lines=self.show_d_lines,
            show_markers=self.show_markers,
            show_grid=self.show_grid,
            show_legend=self.show_legend,
            show_classification_zones=self.show_classification_zones,
            classification_scheme=self._scheme,
            fill_curve=self.fill_curve,
            fill_zone_labels=self.fill_zone_labels,
            curve_color=self.curve_color_override,
            title="Grain Size Distribution",
        )

        # Right — K-value bar chart via shared renderer
        if self.k_results:
            methods = list(self.k_results.keys())
            k_values_display = self._convert_k_values_for_display(self.k_results)
            k_values = list(k_values_display.values())
            flagged = getattr(self, 'flagged_methods', set())

            render_k_bar_chart(
                ax2, methods, k_values,
                flagged_methods=flagged,
                reference_values=self._reference_k_values_for_display(methods, k_values),
                style=self.current_style,
                show_grid=self.show_grid,
                show_legend=self.show_legend,
                show_reference_lines=True,
                show_value_labels=self.show_k_value_labels,
                log_y_scale=self.log_k_y_scale,
                title="Hydraulic Conductivity",
                y_label=self._get_k_axis_label(),
                sample_name=self.sample_name,
                value_label_fontsize=max(5.0, float(self.k_value_label_fontsize) - 1.0),
            )
        else:
            ax2.text(0.5, 0.5, 'Calculate K values\nto view comparison',
                    transform=ax2.transAxes, ha='center', va='center',
                    fontsize=10, color='gray')
            ax2.set_xticks([])
            ax2.set_yticks([])

        # Store references
        self.current_ax = ax1
        self.grain_size_ax = ax1
        self.k_value_ax = ax2 if self.k_results else None
        self.active_axes = [ax1, ax2]

        apply_legend_aware_layout(self.figure, self.current_style)
        self.interactions.prime_current_ax()
        self.interactions.capture_default_limits()
        self.interactions.apply_active_axes_styling()
        self.canvas.draw()
    
    def plot_k_values_only(self, k_results: Dict[str, float]):
        """Display only K-values as a bar chart"""
        if not k_results:
            return

        self.k_results = k_results

        # Clear figure and create K-value plot
        self.figure.clear()
        self.current_ax = self.figure.add_subplot(1, 1, 1)
        self.grain_size_ax = None
        self.k_value_ax = self.current_ax
        self.active_axes = [self.current_ax]

        # Prepare data with unit conversion
        methods = list(k_results.keys())
        k_values_display = self._convert_k_values_for_display(k_results)
        k_values = list(k_values_display.values())
        flagged = getattr(self, 'flagged_methods', set())

        # Delegate all drawing to the shared renderer
        render_k_bar_chart(
            self.current_ax,
            methods,
            k_values,
            flagged_methods=flagged,
            reference_values=self._reference_k_values_for_display(methods, k_values),
            style=self.current_style,
            show_grid=self.show_grid,
            show_legend=self.show_legend,
            show_reference_lines=True,
            show_value_labels=self.show_k_value_labels,
            log_y_scale=self.log_k_y_scale,
            y_label=self._get_k_axis_label(),
            sample_name=self.sample_name,
            value_label_fontsize=float(self.k_value_label_fontsize),
        )

        # Adjust layout and redraw
        apply_legend_aware_layout(self.figure, self.current_style)
        self.interactions.prime_current_ax()
        self.interactions.capture_default_limits()
        self.interactions.apply_active_axes_styling()
        self.canvas.draw()

    def set_display_unit(self, unit: HydraulicConductivityUnit):
        """Set the unit for K-value display and refresh plots"""
        self.display_unit = unit

        # Refresh current plot if K-values are displayed
        if self.k_results:
            if self.k_value_ax == self.current_ax:
                # K-values only plot
                self.plot_k_values_only(self.k_results)
            elif self.k_value_ax is not None:
                # Combined plot
                self.plot_combined_view(self.k_results)

    def _convert_k_values_for_display(self, k_values_m_s: Dict[str, float]) -> Dict[str, float]:
        """Convert K-values from m/s to current display unit"""
        converted = {}
        for method, k_m_s in k_values_m_s.items():
            k_display = HydraulicConductivityConverter.convert_from_m_per_s(k_m_s, self.display_unit)
            converted[method] = k_display
        return converted

    def _format_k_value(self, k_value_display_units: float) -> str:
        """Format K-value for display with appropriate precision"""
        return HydraulicConductivityConverter.format_value(k_value_display_units, self.display_unit)

    def _get_k_axis_label(self) -> str:
        """Get the appropriate axis label for current display unit"""
        unit_symbol = HydraulicConductivityConverter.UNIT_SYMBOLS[self.display_unit]
        return f'Hydraulic Conductivity K ({unit_symbol})'

    def reset_view(self):
        """Reset plot view to default zoom"""
        self.interactions.reset_current_axes()
        
    def clear_plots(self):
        """Clear all plot data"""
        self.grain_data = None
        self.k_results = {}
        self.flagged_methods = set()
        self.sample_name = "No data"
        self.setup_plots()
        
    def export_plot(self, filename: str, dpi: int = 300):
        """Export current plot to file"""
        try:
            self.figure.savefig(filename, dpi=dpi, bbox_inches='tight')
            return True
        except Exception as e:
            print(f"Error exporting plot: {e}")
            return False
