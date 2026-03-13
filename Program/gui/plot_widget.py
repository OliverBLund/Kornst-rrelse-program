"""
Plot widget with real matplotlib integration for grain size distribution visualization
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional, List, Dict
from unit_conversions import HydraulicConductivityConverter, HydraulicConductivityUnit, get_default_plot_unit
from .plot_styles import PlotStyle, PROFESSIONAL_STYLE
from .theme import C, apply_matplotlib_style


class PlotWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.figure = None
        self.canvas = None
        self.toolbar = None
        self.grain_size_ax = None
        self.k_value_ax = None
        
        # Data storage
        self.grain_data = None
        self.k_results = {}
        self.flagged_methods: set[str] = set()
        self.sample_name = "No data"

        # Unit display settings
        self.display_unit = get_default_plot_unit()  # Default to m/d as specified

        # Display options
        self.show_classification_zones = False

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

        ax.set_xlabel('Grain Diameter (mm)')
        ax.set_ylabel('Cumulative % Passing')
        ax.set_title('Grain Size Distribution Curve')
        ax.set_xscale('log')
        ax.set_xlim(0.001, 100)
        ax.set_ylim(0, 100)
        ax.set_facecolor('#ffffff')
        ax.grid(True, which='major', linestyle='-',
                color='#d4c4a8', linewidth=0.5, alpha=0.6)

        ax.text(
            0.5, 0.5, 'Load grain size data to view distribution curve',
            transform=ax.transAxes,
            ha='center', va='center', fontsize=11,
            color=C.TEXT_MUTED, fontstyle='italic',
        )

        self.canvas.draw()

    def draw_classification_zones(self, ax):
        """Draw grain size classification zones as background bands"""
        # Standard grain size boundaries (USCS/ASTM)
        # Clay: < 0.002 mm
        # Silt: 0.002 - 0.075 mm
        # Sand: 0.075 - 4.75 mm
        # Gravel: > 4.75 mm

        zones = [
            {'name': 'Clay', 'min': 0.0001, 'max': 0.002, 'color': '#d4a574', 'alpha': 0.15},
            {'name': 'Silt', 'min': 0.002, 'max': 0.075, 'color': '#c2b280', 'alpha': 0.15},
            {'name': 'Sand', 'min': 0.075, 'max': 4.75, 'color': '#f4e4c1', 'alpha': 0.15},
            {'name': 'Gravel', 'min': 4.75, 'max': 100, 'color': '#9c8a7a', 'alpha': 0.15},
        ]

        for zone in zones:
            ax.axvspan(zone['min'], zone['max'],
                      color=zone['color'], alpha=zone['alpha'],
                      zorder=0)  # Draw behind everything else

            # Add zone label at top of plot
            mid_point = np.sqrt(zone['min'] * zone['max'])  # Geometric mean for log scale
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
        self.sample_name = sample_name

        # Clear figure and create grain size plot
        self.figure.clear()
        self.current_ax = self.figure.add_subplot(1, 1, 1)
        self.grain_size_ax = self.current_ax

        # Draw classification zones if enabled (must be before plotting data)
        if self.show_classification_zones:
            self.draw_classification_zones(self.current_ax)

        # Plot the grain size distribution curve using current style
        style = self.current_style
        self.current_ax.semilogx(
            diameters, cumulative,
            color=style.curve_color,
            linewidth=style.curve_linewidth,
            label=f'{sample_name}',
            marker=style.curve_marker,
            markersize=style.curve_markersize,
            markeredgecolor=style.curve_markeredgecolor,
            markeredgewidth=style.curve_markeredgewidth
        )

        # Add characteristic grain size lines using proper GrainSizeData calculations
        if grain_size_data is not None:
            # Use the corrected calculations from GrainSizeData
            d10 = grain_size_data.get_d10()
            d30 = grain_size_data.get_d30()
            d60 = grain_size_data.get_d60()

            d_values = [d10, d30, d60]
            characteristic_percentiles = [10, 30, 60]
            characteristic_colors = [style.d10_color, style.d30_color, style.d60_color]
            characteristic_linestyles = [style.d10_line_style, style.d30_line_style, style.d60_line_style]
            characteristic_names = ['D10', 'D30', 'D60']

            for d_value, perc, color, linestyle, name in zip(d_values, characteristic_percentiles, characteristic_colors, characteristic_linestyles, characteristic_names):
                if d_value is not None:
                    # Draw vertical line at diameter
                    self.current_ax.axvline(
                        x=d_value, color=color,
                        linestyle=linestyle,
                        linewidth=style.d_line_width,
                        alpha=style.d_line_alpha,
                        label=f'{name} = {d_value:.3f} mm'
                    )

                    # Draw horizontal line at percentile
                    self.current_ax.axhline(
                        y=perc, color=color,
                        linestyle=':',
                        alpha=style.d_line_alpha * 0.7
                    )
        elif len(diameters) > 0 and len(cumulative) > 0:
            # Fallback to old interpolation method if no GrainSizeData is provided
            characteristic_percentiles = [10, 30, 60]
            characteristic_colors = [style.d10_color, style.d30_color, style.d60_color]
            characteristic_linestyles = [style.d10_line_style, style.d30_line_style, style.d60_line_style]
            characteristic_names = ['D10', 'D30', 'D60']

            for perc, color, linestyle, name in zip(characteristic_percentiles, characteristic_colors, characteristic_linestyles, characteristic_names):
                # Interpolate to find diameter at percentile
                if min(cumulative) <= perc <= max(cumulative):
                    d_value = np.interp(perc, cumulative, diameters)

                    # Draw vertical line at diameter
                    self.current_ax.axvline(
                        x=d_value, color=color,
                        linestyle=linestyle,
                        linewidth=style.d_line_width,
                        alpha=style.d_line_alpha,
                        label=f'{name} = {d_value:.3f} mm'
                    )

                    # Draw horizontal line at percentile
                    self.current_ax.axhline(
                        y=perc, color=color,
                        linestyle=':',
                        alpha=style.d_line_alpha * 0.7
                    )
        
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
        if style.grid_show:
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
        self.current_ax.set_xlim(min(diameters)*0.5, max(diameters)*2)
        self.current_ax.set_ylim(0, 100)

        # Apply legend styling
        legend = self.current_ax.legend(
            loc=style.legend_loc,
            fontsize=style.legend_fontsize,
            framealpha=style.legend_framealpha,
            edgecolor=style.legend_edgecolor
        )
        
        self.figure.tight_layout()
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
            marker=style.curve_marker,
            markersize=style.curve_markersize * 0.8,  # Slightly smaller for combined view
            markeredgecolor=style.curve_markeredgecolor,
            markeredgewidth=style.curve_markeredgewidth
        )

        # Apply styling
        ax1.set_xlabel('Grain Diameter (mm)', fontsize=style.label_fontsize - 1, fontfamily=style.font_family)
        ax1.set_ylabel('Cumulative % Passing', fontsize=style.label_fontsize - 1, fontfamily=style.font_family)
        ax1.set_title('Grain Size Distribution', fontsize=style.title_fontsize - 2, fontweight=style.title_fontweight, fontfamily=style.font_family)

        if style.grid_show:
            ax1.grid(True, alpha=style.grid_alpha, which='major', linestyle=style.grid_linestyle, color=style.grid_color, linewidth=style.grid_linewidth)

        ax1.set_facecolor(style.axes_facecolor)
        ax1.tick_params(labelsize=style.tick_fontsize - 1)
        ax1.set_xlim(min(diameters)*0.5, max(diameters)*2)
        ax1.set_ylim(0, 100)
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

            # Add value labels on bars with proper formatting
            for bar, method, color in zip(bars, methods, colors):
                if method in flagged:
                    bar.set_facecolor('none')
                    bar.set_edgecolor(color)
                    bar.set_linewidth(2.0)
                    bar.set_hatch('////')
                    bar.set_alpha(1.0)
                else:
                    bar.set_edgecolor('black')
                    bar.set_linewidth(1.0)

                height = bar.get_height()
                formatted_value = self._format_k_value(k_values_display[method])
                ax2.text(bar.get_x() + bar.get_width()/2., height*1.1,
                        formatted_value.split()[0], ha='center', va='bottom', fontsize=7)  # Show only number

            # Apply styling to K-values plot
            ax2.set_xlabel('Method', fontsize=style.label_fontsize - 1, fontfamily=style.font_family)
            ax2.set_ylabel(self._get_k_axis_label(), fontsize=style.label_fontsize - 1, fontfamily=style.font_family)
            ax2.set_title('Hydraulic Conductivity', fontsize=style.title_fontsize - 2, fontweight=style.title_fontweight, fontfamily=style.font_family)
            ax2.set_xticks(x_pos)
            ax2.set_xticklabels([m[:6] for m in methods], rotation=45, ha='right', fontsize=style.tick_fontsize - 1)
            ax2.set_yscale('log')
            ax2.set_facecolor(style.axes_facecolor)
            ax2.tick_params(labelsize=style.tick_fontsize - 1)
            if style.grid_show:
                ax2.grid(True, alpha=style.grid_alpha, axis='y', linestyle=style.grid_linestyle, color=style.grid_color, linewidth=style.grid_linewidth)
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
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def plot_k_values_only(self, k_results: Dict[str, float]):
        """Display only K-values as a bar chart"""
        if not k_results:
            return
            
        self.k_results = k_results
        
        # Clear figure and create K-value plot
        self.figure.clear()
        self.current_ax = self.figure.add_subplot(1, 1, 1)
        self.k_value_ax = self.current_ax
        
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

        # Add value labels on bars with proper formatting
        for bar, method, color in zip(bars, methods, colors):
            if method in flagged:
                bar.set_facecolor('none')
                bar.set_edgecolor(color)
                bar.set_linewidth(2.5)
                bar.set_hatch('////')
                bar.set_alpha(1.0)
            else:
                bar.set_edgecolor('black')
                bar.set_linewidth(1.0)

            height = bar.get_height()
            formatted_value = self._format_k_value(k_values_display[method])
            self.current_ax.text(bar.get_x() + bar.get_width()/2., height*1.1,
                                formatted_value.split()[0], ha='center', va='bottom', fontsize=8)  # Show only number

        # Setup plot formatting using current style
        style = self.current_style
        self.current_ax.set_xlabel('Calculation Method', fontsize=style.label_fontsize, fontfamily=style.font_family)
        self.current_ax.set_ylabel(self._get_k_axis_label(), fontsize=style.label_fontsize, fontfamily=style.font_family)
        self.current_ax.set_title(f'K-Value Comparison: {self.sample_name}',
                                 fontsize=style.title_fontsize, fontweight=style.title_fontweight, fontfamily=style.font_family)
        self.current_ax.set_xticks(x_pos)
        self.current_ax.set_xticklabels(methods, rotation=45, ha='right', fontsize=style.tick_fontsize)
        self.current_ax.set_yscale('log')
        self.current_ax.set_facecolor(style.axes_facecolor)
        self.current_ax.tick_params(labelsize=style.tick_fontsize)
        if style.grid_show:
            self.current_ax.grid(True, alpha=style.grid_alpha, axis='y', linestyle=style.grid_linestyle,
                               color=style.grid_color, linewidth=style.grid_linewidth)
        
        # Add min/max/mean lines with proper unit formatting
        if k_values:
            mean_k = np.mean(k_values)
            min_k = min(k_values)
            max_k = max(k_values)

            unit_symbol = HydraulicConductivityConverter.UNIT_SYMBOLS[self.display_unit]
            format_str = HydraulicConductivityConverter.DISPLAY_FORMATS[self.display_unit]

            self.current_ax.axhline(y=mean_k, color='red', linestyle='-', alpha=0.5,
                                   label=f'Mean: {format_str.format(mean_k)} {unit_symbol}')
            self.current_ax.axhline(y=min_k, color='blue', linestyle=':', alpha=0.5,
                                   label=f'Min: {format_str.format(min_k)} {unit_symbol}')
            self.current_ax.axhline(y=max_k, color='green', linestyle=':', alpha=0.5,
                                   label=f'Max: {format_str.format(max_k)} {unit_symbol}')

            self.current_ax.legend(loc='upper right', fontsize=8)
        
        # Adjust layout and redraw
        self.figure.tight_layout()
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
        if not self.current_ax:
            return
            
        # Reset based on current plot type
        if self.grain_size_ax == self.current_ax and self.grain_data:
            # Grain size plot
            diameters, cumulative = self.grain_data
            self.current_ax.set_xlim(min(diameters)*0.5, max(diameters)*2)
            self.current_ax.set_ylim(0, 100)
        elif self.k_value_ax == self.current_ax and self.k_results:
            # K-value plot - use converted values for proper scaling
            k_values_display = self._convert_k_values_for_display(self.k_results)
            k_values = list(k_values_display.values())
            self.current_ax.set_ylim(min(k_values)*0.1, max(k_values)*10)
        else:
            # Default grain size limits
            if hasattr(self.current_ax, 'get_xscale') and self.current_ax.get_xscale() == 'log':
                self.current_ax.set_xlim(0.001, 100)
            self.current_ax.set_ylim(0, 100)
        
        self.canvas.draw()
        
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
