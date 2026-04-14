"""
Plot widget with real matplotlib integration for grain size distribution visualization
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from matplotlib.figure import Figure
from matplotlib.patches import Patch
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional, List, Dict
from unit_conversions import HydraulicConductivityConverter, HydraulicConductivityUnit, get_default_plot_unit
from .plot_styles import PlotStyle, PROFESSIONAL_STYLE
from .matplotlib_canvas import FigureCanvas, NavigationToolbar
from .k_plot_helpers import annotate_log_bars, apply_log_bar_limits, format_method_label
from .plot_interactions import AxesInteractionController
from .theme import C, apply_matplotlib_style
from grain_classification import ISO14688, interpolate_at as _gc_interpolate_at


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
        self.show_d_lines = False
        self.show_markers = False
        self.fill_curve = False

        # Style system
        self.current_style = PROFESSIONAL_STYLE

        # Method colors for consistency
        self.method_colors = {
            "Hazen": "#b71c1c",        # Deep red
            "Terzaghi": "#2e7d32",      # Forest green
            "Beyer": "#1565c0",         # Deep blue
            "Slichter": "#ef6c00",      # Deep orange
            "Kozeny-Carman": "#7b1fa2", # Deep purple
            "Shepherd": "#c2185b",      # Deep pink
            "Zunker": "#00acc1",        # Teal
            "Zamarin": "#fbc02d",       # Golden yellow
            "USBR": "#6d4c41",          # Earth brown
            "Sauerbrei": "#546e7a",     # Blue gray
            "Hazen_1892": "#d84315",    # Deep orange red
            "Kruger": "#4527a0",        # Deep indigo
            "Barr": "#8d6e63",          # Medium brown
            "Alyamani-Sen": "#5d4037",  # Dark brown
            "Chapuis": "#ff5722",       # Deep orange-red
            "Krumbein-Monk": "#9c27b0", # Purple
        }
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the matplotlib widget layout"""
        # Apply theme-consistent rcParams (fonts, colors, grid) before any figure is created
        apply_matplotlib_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create matplotlib figure
        self.figure = Figure(figsize=(12, 8), tight_layout=True)
        self.figure.patch.set_facecolor(C.BG)

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

        layout.addWidget(self.canvas)

        # Initialize empty plots
        self.setup_plots()

    def set_style(self, style: PlotStyle):
        """Apply a new plot style and redraw."""
        self.current_style = style
        self.figure.patch.set_facecolor(style.figure_facecolor)

    def setup_plots(self):
        """Setup initial empty plot area."""
        self.figure.clear()
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
        ax.set_facecolor('#ffffff')
        ax.grid(True, which='major', linestyle='-',
                color='#d4c4a8', linewidth=0.5, alpha=0.6)

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

    def _distribution_limits(self, diameters, cumulative) -> tuple[float, float, float, float]:
        """Compute padded distribution-plot limits with slight headroom."""
        s = self._scheme
        sorted_pairs = sorted(zip(diameters, cumulative))
        x_min = sorted_pairs[0][0] / self._DIST_X_PADDING_FACTOR
        last_x = sorted_pairs[-1][0]
        pct_at_largest = sorted_pairs[-1][1]
        x_max = last_x * self._DIST_X_PADDING_FACTOR
        if pct_at_largest > 1.0:
            # Keep a little space to the right when retained material exists above
            # the largest measured sieve, so the curve does not terminate on the edge.
            if last_x < s.sand_max:
                x_max = max(x_max, s.sand_max * 1.35)
            elif last_x < s.gravel_max:
                x_max = max(x_max, s.gravel_max * 1.35)
            else:
                x_max = max(x_max, last_x * 3.5)
        return x_min, x_max, 0.0, self._DIST_Y_MAX

    def _draw_characteristic_lines(self, ax, diameters, cumulative, grain_size_data, style: PlotStyle):
        """Draw D10/D30/D60 guide lines when enabled."""
        if not self.show_d_lines:
            return

        if grain_size_data is not None:
            d_values = [
                grain_size_data.get_d10(),
                grain_size_data.get_d30(),
                grain_size_data.get_d60(),
            ]
        else:
            d_values = []
            if len(diameters) > 0 and len(cumulative) > 0:
                for percentile in (10, 30, 60):
                    if min(cumulative) <= percentile <= max(cumulative):
                        d_values.append(np.interp(percentile, cumulative, diameters))
                    else:
                        d_values.append(None)

        characteristic_percentiles = [10, 30, 60]
        characteristic_colors = [style.d10_color, style.d30_color, style.d60_color]
        characteristic_linestyles = [style.d10_line_style, style.d30_line_style, style.d60_line_style]
        characteristic_names = ['D10', 'D30', 'D60']

        for d_value, perc, color, linestyle, name in zip(
            d_values,
            characteristic_percentiles,
            characteristic_colors,
            characteristic_linestyles,
            characteristic_names,
        ):
            if d_value is None:
                continue

            ax.axvline(
                x=d_value,
                color=color,
                linestyle=linestyle,
                linewidth=style.d_line_width,
                alpha=style.d_line_alpha,
                label=f'{name} = {d_value:.3f} mm'
            )
            ax.axhline(
                y=perc,
                color=color,
                linestyle=':',
                alpha=style.d_line_alpha * 0.7,
            )

    def _style_k_bar(self, bar, method: str, color: str, flagged: set[str]):
        """Apply warning styling to flagged K-value bars."""
        if method in flagged:
            bar.set_facecolor('none')
            bar.set_edgecolor(color)
            bar.set_linewidth(2.0)
            bar.set_hatch('////')
            bar.set_alpha(1.0)
        else:
            bar.set_edgecolor('black')
            bar.set_linewidth(1.0)

    def _add_k_reference_lines(self, ax, k_values, style: PlotStyle):
        """Add mean/min/max reference lines to a K-value axis."""
        if not k_values:
            return

        mean_k = np.mean(k_values)
        min_k = min(k_values)
        max_k = max(k_values)

        unit_symbol = HydraulicConductivityConverter.UNIT_SYMBOLS[self.display_unit]
        format_str = HydraulicConductivityConverter.DISPLAY_FORMATS[self.display_unit]

        ax.axhline(
            y=mean_k,
            color='red',
            linestyle='-',
            alpha=0.5,
            label=f'Mean: {format_str.format(mean_k)} {unit_symbol}',
        )
        ax.axhline(
            y=min_k,
            color='blue',
            linestyle=':',
            alpha=0.5,
            label=f'Min: {format_str.format(min_k)} {unit_symbol}',
        )
        ax.axhline(
            y=max_k,
            color='green',
            linestyle=':',
            alpha=0.5,
            label=f'Max: {format_str.format(max_k)} {unit_symbol}',
        )

    def _add_k_status_legend(self, ax, flagged: set[str]):
        handles, labels = ax.get_legend_handles_labels()
        if flagged:
            handles = handles + [
                Patch(
                    facecolor='none',
                    edgecolor=self.current_style.k_bar_flagged_color,
                    hatch='////',
                    label='Flagged / Warning',
                )
            ]
            labels = labels + ['Flagged / Warning']
        if handles:
            ax.legend(handles, labels, loc='upper right', fontsize=8)

    def _annotate_k_value_bars(self, ax, bars, methods, values, *, fontsize: float = 7.0):
        labels = [
            self._format_k_value(values[method]).split()[0]
            for method in methods
        ]
        annotate_log_bars(ax, bars, labels, fontsize=fontsize)

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

    def draw_fill_zone_labels(self, ax, diameters, cumulative):
        """Draw grain fraction % labels centred inside the filled area for each zone."""
        import math
        if not self.grain_size_data:
            return
        try:
            result = self.grain_size_data.classify(scheme=self._scheme)
            fracs = result.fractions
        except Exception:
            return

        s = self._scheme
        zone_fracs = [
            ('Clay',   0.0001,       s.clay_max,   fracs.clay_pct),
            ('Silt',   s.clay_max,   s.silt_max,   fracs.silt_pct),
            ('Sand',   s.silt_max,   s.sand_max,   fracs.sand_pct),
            ('Gravel', s.sand_max,   s.gravel_max, fracs.gravel_pct),
            ('Cobble', s.gravel_max, 200.0,        fracs.cobble_pct),
        ]
        for name, lo, hi, frac in zone_fracs:
            if frac < 2.0:
                continue
            x_mid = math.sqrt(lo * hi)
            y_at_mid = _gc_interpolate_at(list(diameters), list(cumulative), x_mid)
            if y_at_mid is None or y_at_mid < 6.0:
                continue
            ax.text(x_mid, y_at_mid / 2.0,
                    f"{frac:.0f}%\n{name}",
                    ha='center', va='center',
                    fontsize=7.5, fontweight='bold',
                    color='#3a2e1c', alpha=0.72,
                    zorder=3)

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

        # Compute axis limits up-front so zone drawing can use the correct x range.
        x_min, x_max, y_min, y_max = self._distribution_limits(diameters, cumulative)
        self.current_ax.set_xlim(x_min, x_max)
        self.current_ax.set_ylim(y_min, y_max)

        # Draw classification zones if enabled (must be after xlim is set so labels
        # are clamped to the visible range correctly)
        if self.show_classification_zones:
            self.draw_classification_zones(self.current_ax)

        # Plot the grain size distribution curve using current style
        style = self.current_style
        self.current_ax.semilogx(
            diameters, cumulative,
            color=style.curve_color,
            linewidth=style.curve_linewidth,
            label=f'{sample_name}',
            marker=self._get_curve_marker(style),
            markersize=style.curve_markersize,
            markeredgecolor=style.curve_markeredgecolor,
            markeredgewidth=style.curve_markeredgewidth
        )
        if self.fill_curve:
            self.current_ax.fill_between(diameters, cumulative, 0, color=style.curve_color, alpha=0.12)
            if self.fill_zone_labels:
                self.draw_fill_zone_labels(self.current_ax, diameters, cumulative)

        self._draw_characteristic_lines(self.current_ax, diameters, cumulative, grain_size_data, style)
        
        # Setup plot formatting using current style
        self.current_ax.set_xlabel(
            'Grain Diameter (mm)',
            fontsize=style.label_fontsize,
            fontfamily=style.font_family
        )
        self.current_ax.set_ylabel(
            'Cumulative % Passing',
            fontsize=style.label_fontsize,
            fontfamily=style.font_family
        )
        self.current_ax.set_title(
            f'Grain Size Distribution: {sample_name}',
            fontsize=style.title_fontsize,
            fontweight=style.title_fontweight,
            fontfamily=style.font_family
        )

        # Apply grid styling
        if self.show_grid and style.grid_show:
            self.current_ax.grid(
                True,
                alpha=style.grid_alpha,
                which='major',
                linestyle=style.grid_linestyle,
                color=style.grid_color,
                linewidth=style.grid_linewidth
            )
            if style.show_minor_grid:
                self.current_ax.grid(
                    True,
                    alpha=style.minor_grid_alpha,
                    which='minor',
                    linestyle=':',
                    color=style.grid_color,
                    linewidth=style.grid_linewidth * 0.5
                )

        # Set axis properties
        self.current_ax.set_facecolor(style.axes_facecolor)
        self.current_ax.tick_params(labelsize=style.tick_fontsize)
        # xlim/ylim already set at the top of update_plot before zone drawing

        # Apply legend styling
        if self.show_legend:
            self.current_ax.legend(
                loc=style.legend_loc,
                fontsize=style.legend_fontsize,
                framealpha=style.legend_framealpha,
                edgecolor=style.legend_edgecolor
            )
        
        self.figure.tight_layout()
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
            
        # Use stored k_results if not provided
        if k_results:
            self.k_results = k_results
        
        # Clear figure and create two subplots side by side
        self.figure.clear()
        
        # Create two subplots horizontally
        ax1 = self.figure.add_subplot(1, 2, 1)
        ax2 = self.figure.add_subplot(1, 2, 2)

        # Draw classification zones if enabled
        if self.show_classification_zones:
            self.draw_classification_zones(ax1)

        # Plot grain size distribution on left using current style
        style = self.current_style
        diameters, cumulative = self.grain_data
        ax1.semilogx(
            diameters, cumulative,
            color=style.curve_color,
            linewidth=style.curve_linewidth,
            label=f'{self.sample_name}',
            marker=self._get_curve_marker(style),
            markersize=style.curve_markersize * 0.8,  # Slightly smaller for combined view
            markeredgecolor=style.curve_markeredgecolor,
            markeredgewidth=style.curve_markeredgewidth
        )
        if self.fill_curve:
            ax1.fill_between(diameters, cumulative, 0, color=style.curve_color, alpha=0.12)
        self._draw_characteristic_lines(ax1, diameters, cumulative, self.grain_size_data, style)

        # Apply styling
        ax1.set_xlabel('Grain Diameter (mm)', fontsize=style.label_fontsize - 1, fontfamily=style.font_family)
        ax1.set_ylabel('Cumulative % Passing', fontsize=style.label_fontsize - 1, fontfamily=style.font_family)
        ax1.set_title('Grain Size Distribution', fontsize=style.title_fontsize - 2, fontweight=style.title_fontweight, fontfamily=style.font_family)

        if self.show_grid and style.grid_show:
            ax1.grid(True, alpha=style.grid_alpha, which='major', linestyle=style.grid_linestyle, color=style.grid_color, linewidth=style.grid_linewidth)

        ax1.set_facecolor(style.axes_facecolor)
        ax1.tick_params(labelsize=style.tick_fontsize - 1)
        x_min, x_max, y_min, y_max = self._distribution_limits(diameters, cumulative)
        ax1.set_xlim(x_min, x_max)
        ax1.set_ylim(y_min, y_max)
        if self.show_legend:
            ax1.legend(loc=style.legend_loc, fontsize=style.legend_fontsize - 1, framealpha=style.legend_framealpha, edgecolor=style.legend_edgecolor)
        
        # Plot K-values on right if available
        if self.k_results:
            methods = list(self.k_results.keys())
            k_values_display = self._convert_k_values_for_display(self.k_results)
            k_values = list(k_values_display.values())
            flagged = getattr(self, 'flagged_methods', set())

            # Get colors for each method based on current style
            if style.use_method_specific_colors:
                # Use colorful method-specific colors
                colors = [self.method_colors.get(method, '#888888') for method in methods]
            else:
                # Use unified colors: one for valid, one for flagged
                colors = [style.k_bar_flagged_color if method in flagged else style.k_bar_valid_color
                         for method in methods]

            x_pos = np.arange(len(methods))
            bars = ax2.bar(x_pos, k_values, color=colors, alpha=0.8)
            ax2.set_axisbelow(True)

            for bar, method, color in zip(bars, methods, colors):
                self._style_k_bar(bar, method, color, flagged)

            # Apply styling to K-values plot
            ax2.set_xlabel('Method', fontsize=style.label_fontsize - 1, fontfamily=style.font_family)
            ax2.set_ylabel(self._get_k_axis_label(), fontsize=style.label_fontsize - 1, fontfamily=style.font_family)
            ax2.set_title('Hydraulic Conductivity', fontsize=style.title_fontsize - 2, fontweight=style.title_fontweight, fontfamily=style.font_family)
            ax2.set_xticks(x_pos)
            ax2.set_xticklabels(
                [format_method_label(method, compact=True) for method in methods],
                rotation=45,
                ha='right',
                fontsize=style.tick_fontsize - 1,
            )
            ax2.set_facecolor(style.axes_facecolor)
            ax2.tick_params(labelsize=style.tick_fontsize - 1)
            apply_log_bar_limits(ax2, k_values)
            if self.show_grid and style.grid_show:
                ax2.grid(True, alpha=style.grid_alpha, axis='y', linestyle=style.grid_linestyle, color=style.grid_color, linewidth=style.grid_linewidth)
            self._add_k_reference_lines(ax2, k_values, style)
            self._annotate_k_value_bars(ax2, bars, methods, k_values_display, fontsize=7.0)
            if self.show_legend:
                self._add_k_status_legend(ax2, flagged)
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
        
        self.figure.tight_layout()
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
        
        # Prepare data for bar chart with unit conversion
        methods = list(k_results.keys())
        k_values_display = self._convert_k_values_for_display(k_results)
        k_values = list(k_values_display.values())
        flagged = getattr(self, 'flagged_methods', set())

        # Get colors for each method based on current style
        style = self.current_style
        if style.use_method_specific_colors:
            # Use colorful method-specific colors
            colors = [self.method_colors.get(method, '#888888') for method in methods]
        else:
            # Use unified colors: one for valid, one for flagged
            colors = [style.k_bar_flagged_color if method in flagged else style.k_bar_valid_color
                     for method in methods]

        # Create bar chart
        x_pos = np.arange(len(methods))
        bars = self.current_ax.bar(x_pos, k_values, color=colors, alpha=0.8)
        self.current_ax.set_axisbelow(True)

        for bar, method, color in zip(bars, methods, colors):
            self._style_k_bar(bar, method, color, flagged)

        # Setup plot formatting using current style
        style = self.current_style
        self.current_ax.set_xlabel('Calculation Method', fontsize=style.label_fontsize, fontfamily=style.font_family)
        self.current_ax.set_ylabel(self._get_k_axis_label(), fontsize=style.label_fontsize, fontfamily=style.font_family)
        self.current_ax.set_title(f'K-Value Comparison: {self.sample_name}',
                                 fontsize=style.title_fontsize, fontweight=style.title_fontweight, fontfamily=style.font_family)
        self.current_ax.set_xticks(x_pos)
        self.current_ax.set_xticklabels(methods, rotation=45, ha='right', fontsize=style.tick_fontsize)
        self.current_ax.set_facecolor(style.axes_facecolor)
        self.current_ax.tick_params(labelsize=style.tick_fontsize)
        apply_log_bar_limits(self.current_ax, k_values)
        if self.show_grid and style.grid_show:
            self.current_ax.grid(True, alpha=style.grid_alpha, axis='y', linestyle=style.grid_linestyle,
                               color=style.grid_color, linewidth=style.grid_linewidth)
        
        self._add_k_reference_lines(self.current_ax, k_values, style)
        self._annotate_k_value_bars(self.current_ax, bars, methods, k_values_display, fontsize=8.0)
        if self.show_legend:
            self._add_k_status_legend(self.current_ax, flagged)
        
        # Adjust layout and redraw
        self.figure.tight_layout()
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
