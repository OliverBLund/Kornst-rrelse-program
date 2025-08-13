"""
Plot widget with real matplotlib integration for grain size distribution visualization
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional, List, Dict


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
        self.sample_name = "No data"
        
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
            "Kruger": "#4527a0"         # Deep indigo
        }
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the matplotlib widget layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Create matplotlib figure with subplots
        self.figure = Figure(figsize=(12, 8), tight_layout=True)
        self.figure.patch.set_facecolor('#fafaf7')
        
        # Create canvas
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color: #ffffff;")
        
        # Hide matplotlib toolbar to save space
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setVisible(False)
        
        # Add only canvas to layout (no toolbar)
        layout.addWidget(self.canvas)
        
        # Initialize empty plots
        self.setup_plots()
        
    def setup_plots(self):
        """Setup initial single plot area"""
        self.figure.clear()
        
        # Create single axes for current plot
        self.current_ax = self.figure.add_subplot(1, 1, 1)
        
        # Setup default grain size distribution plot
        self.current_ax.set_xlabel('Grain Diameter (mm)', fontsize=10)
        self.current_ax.set_ylabel('Cumulative % Passing', fontsize=10)
        self.current_ax.set_title('Grain Size Distribution Curve', fontsize=12, fontweight='bold')
        self.current_ax.grid(True, alpha=0.3, linestyle='--')
        self.current_ax.set_xscale('log')
        self.current_ax.set_xlim(0.001, 100)
        self.current_ax.set_ylim(0, 100)
        
        # Add empty state message
        self.current_ax.text(0.5, 0.5, 'Load grain size data to view distribution curve',
                            transform=self.current_ax.transAxes,
                            ha='center', va='center', fontsize=12, color='gray')
        
        # Store reference for compatibility
        self.grain_size_ax = self.current_ax
        self.k_value_ax = None
        
        self.canvas.draw()
        
    def update_plot(self, diameters: Optional[List[float]] = None, 
                   cumulative: Optional[List[float]] = None, 
                   sample_name: str = "Sample"):
        """Update grain size distribution plot with real data"""
        if diameters is None or cumulative is None:
            return
            
        self.grain_data = (diameters, cumulative)
        self.sample_name = sample_name
        
        # Clear figure and create grain size plot
        self.figure.clear()
        self.current_ax = self.figure.add_subplot(1, 1, 1)
        self.grain_size_ax = self.current_ax
        
        # Plot the grain size distribution curve
        self.current_ax.semilogx(diameters, cumulative, 'b-', linewidth=2, 
                                 label=f'{sample_name}', marker='o', markersize=4)
        
        # Add characteristic grain size lines
        if len(diameters) > 0 and len(cumulative) > 0:
            # Find D10, D30, D60 by interpolation
            characteristic_percentiles = [10, 30, 60]
            characteristic_colors = ['red', 'green', 'purple']
            characteristic_names = ['D10', 'D30', 'D60']
            
            for perc, color, name in zip(characteristic_percentiles, characteristic_colors, characteristic_names):
                # Interpolate to find diameter at percentile
                if min(cumulative) <= perc <= max(cumulative):
                    d_value = np.interp(perc, cumulative, diameters)
                    
                    # Draw vertical line at diameter
                    self.current_ax.axvline(x=d_value, color=color, linestyle='--', 
                                           alpha=0.7, label=f'{name} = {d_value:.3f} mm')
                    
                    # Draw horizontal line at percentile
                    self.current_ax.axhline(y=perc, color=color, linestyle=':', alpha=0.5)
        
        # Setup plot formatting
        self.current_ax.set_xlabel('Grain Diameter (mm)', fontsize=10)
        self.current_ax.set_ylabel('Cumulative % Passing', fontsize=10)
        self.current_ax.set_title(f'Grain Size Distribution: {sample_name}', fontsize=12, fontweight='bold')
        self.current_ax.grid(True, alpha=0.3, which='both', linestyle='--')
        self.current_ax.set_xlim(min(diameters)*0.5, max(diameters)*2)
        self.current_ax.set_ylim(0, 100)
        self.current_ax.legend(loc='best', fontsize=9)
        
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
        
        # Plot grain size distribution on left
        diameters, cumulative = self.grain_data
        ax1.semilogx(diameters, cumulative, 'b-', linewidth=2, 
                     label=f'{self.sample_name}', marker='o', markersize=4)
        ax1.set_xlabel('Grain Diameter (mm)', fontsize=9)
        ax1.set_ylabel('Cumulative % Passing', fontsize=9)
        ax1.set_title('Grain Size Distribution', fontsize=10, fontweight='bold')
        ax1.grid(True, alpha=0.3, which='both', linestyle='--')
        ax1.set_xlim(min(diameters)*0.5, max(diameters)*2)
        ax1.set_ylim(0, 100)
        ax1.legend(loc='best', fontsize=8)
        
        # Plot K-values on right if available
        if self.k_results:
            methods = list(self.k_results.keys())
            k_values = list(self.k_results.values())
            colors = [self.method_colors.get(method, '#888888') for method in methods]
            
            x_pos = np.arange(len(methods))
            bars = ax2.bar(x_pos, k_values, color=colors, alpha=0.8, edgecolor='black', linewidth=1)
            
            # Add value labels on bars
            for bar, k_val in zip(bars, k_values):
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height*1.1,
                        f'{k_val:.2e}', ha='center', va='bottom', fontsize=7)
            
            ax2.set_xlabel('Method', fontsize=9)
            ax2.set_ylabel('K (m/s)', fontsize=9)
            ax2.set_title('Hydraulic Conductivity', fontsize=10, fontweight='bold')
            ax2.set_xticks(x_pos)
            ax2.set_xticklabels([m[:6] for m in methods], rotation=45, ha='right', fontsize=8)
            ax2.set_yscale('log')
            ax2.grid(True, alpha=0.3, axis='y', linestyle='--')
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
        
        # Prepare data for bar chart
        methods = list(k_results.keys())
        k_values = list(k_results.values())
        
        # Get colors for each method
        colors = [self.method_colors.get(method, '#888888') for method in methods]
        
        # Create bar chart
        x_pos = np.arange(len(methods))
        bars = self.current_ax.bar(x_pos, k_values, color=colors, alpha=0.8, edgecolor='black', linewidth=1)
        
        # Add value labels on bars
        for bar, k_val in zip(bars, k_values):
            height = bar.get_height()
            self.current_ax.text(bar.get_x() + bar.get_width()/2., height*1.1,
                                f'{k_val:.2e}', ha='center', va='bottom', fontsize=8)
        
        # Setup plot formatting
        self.current_ax.set_xlabel('Calculation Method', fontsize=10)
        self.current_ax.set_ylabel('Hydraulic Conductivity K (m/s)', fontsize=10)
        self.current_ax.set_title(f'K-Value Comparison: {self.sample_name}', fontsize=12, fontweight='bold')
        self.current_ax.set_xticks(x_pos)
        self.current_ax.set_xticklabels(methods, rotation=45, ha='right')
        self.current_ax.set_yscale('log')
        self.current_ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # Add min/max/mean lines
        if k_values:
            mean_k = np.mean(k_values)
            min_k = min(k_values)
            max_k = max(k_values)
            
            self.current_ax.axhline(y=mean_k, color='red', linestyle='-', alpha=0.5, 
                                   label=f'Mean: {mean_k:.2e} m/s')
            self.current_ax.axhline(y=min_k, color='blue', linestyle=':', alpha=0.5,
                                   label=f'Min: {min_k:.2e} m/s')
            self.current_ax.axhline(y=max_k, color='green', linestyle=':', alpha=0.5,
                                   label=f'Max: {max_k:.2e} m/s')
            
            self.current_ax.legend(loc='upper right', fontsize=8)
        
        # Adjust layout and redraw
        self.figure.tight_layout()
        self.canvas.draw()
        
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
            # K-value plot
            k_values = list(self.k_results.values())
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