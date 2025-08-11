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
        
        # Create navigation toolbar
        toolbar_container = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_container)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.toolbar = NavigationToolbar(self.canvas, self)
        toolbar_layout.addWidget(self.toolbar)
        
        # Add custom buttons
        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(self.reset_view)
        toolbar_layout.addWidget(reset_btn)
        
        clear_btn = QPushButton("Clear Plots") 
        clear_btn.clicked.connect(self.clear_plots)
        toolbar_layout.addWidget(clear_btn)
        
        toolbar_layout.addStretch()
        
        # Add widgets to layout
        layout.addWidget(toolbar_container)
        layout.addWidget(self.canvas)
        
        # Initialize empty plots
        self.setup_plots()
        
    def setup_plots(self):
        """Setup the two subplot areas"""
        self.figure.clear()
        
        # Create subplots
        self.grain_size_ax = self.figure.add_subplot(2, 1, 1)
        self.k_value_ax = self.figure.add_subplot(2, 1, 2)
        
        # Setup grain size distribution plot
        self.grain_size_ax.set_xlabel('Grain Diameter (mm)', fontsize=10)
        self.grain_size_ax.set_ylabel('Cumulative % Passing', fontsize=10)
        self.grain_size_ax.set_title('Grain Size Distribution Curve', fontsize=12, fontweight='bold')
        self.grain_size_ax.grid(True, alpha=0.3, linestyle='--')
        self.grain_size_ax.set_xscale('log')
        self.grain_size_ax.set_xlim(0.001, 100)
        self.grain_size_ax.set_ylim(0, 100)
        
        # Setup K-value bar chart
        self.k_value_ax.set_xlabel('Calculation Method', fontsize=10)
        self.k_value_ax.set_ylabel('Hydraulic Conductivity K (m/s)', fontsize=10)
        self.k_value_ax.set_title('K-Value Comparison by Method', fontsize=12, fontweight='bold')
        self.k_value_ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        self.k_value_ax.set_yscale('log')
        
        # Add empty state messages
        self.grain_size_ax.text(0.5, 0.5, 'Load grain size data to view distribution curve',
                               transform=self.grain_size_ax.transAxes,
                               ha='center', va='center', fontsize=12, color='gray')
        
        self.k_value_ax.text(0.5, 0.5, 'Calculate K values to view method comparison',
                            transform=self.k_value_ax.transAxes, 
                            ha='center', va='center', fontsize=12, color='gray')
        
        self.canvas.draw()
        
    def update_plot(self, diameters: Optional[List[float]] = None, 
                   cumulative: Optional[List[float]] = None, 
                   sample_name: str = "Sample"):
        """Update grain size distribution plot with real data"""
        if diameters is None or cumulative is None:
            return
            
        self.grain_data = (diameters, cumulative)
        self.sample_name = sample_name
        
        # Clear and redraw grain size plot
        self.grain_size_ax.clear()
        
        # Plot the grain size distribution curve
        self.grain_size_ax.semilogx(diameters, cumulative, 'b-', linewidth=2, 
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
                    self.grain_size_ax.axvline(x=d_value, color=color, linestyle='--', 
                                              alpha=0.7, label=f'{name} = {d_value:.3f} mm')
                    
                    # Draw horizontal line at percentile
                    self.grain_size_ax.axhline(y=perc, color=color, linestyle=':', alpha=0.5)
        
        # Setup plot formatting
        self.grain_size_ax.set_xlabel('Grain Diameter (mm)', fontsize=10)
        self.grain_size_ax.set_ylabel('Cumulative % Passing', fontsize=10)
        self.grain_size_ax.set_title(f'Grain Size Distribution: {sample_name}', fontsize=12, fontweight='bold')
        self.grain_size_ax.grid(True, alpha=0.3, which='both', linestyle='--')
        self.grain_size_ax.set_xlim(min(diameters)*0.5, max(diameters)*2)
        self.grain_size_ax.set_ylim(0, 100)
        self.grain_size_ax.legend(loc='best', fontsize=9)
        
        self.canvas.draw()
        
    def add_k_calculation_results(self, k_results: Dict[str, float]):
        """Add K calculation results and display as bar chart"""
        if not k_results:
            return
            
        self.k_results = k_results
        
        # Clear and redraw K-value plot
        self.k_value_ax.clear()
        
        # Prepare data for bar chart
        methods = list(k_results.keys())
        k_values = list(k_results.values())
        
        # Get colors for each method
        colors = [self.method_colors.get(method, '#888888') for method in methods]
        
        # Create bar chart
        x_pos = np.arange(len(methods))
        bars = self.k_value_ax.bar(x_pos, k_values, color=colors, alpha=0.8, edgecolor='black', linewidth=1)
        
        # Add value labels on bars
        for bar, k_val in zip(bars, k_values):
            height = bar.get_height()
            self.k_value_ax.text(bar.get_x() + bar.get_width()/2., height*1.1,
                                f'{k_val:.2e}', ha='center', va='bottom', fontsize=8)
        
        # Setup plot formatting
        self.k_value_ax.set_xlabel('Calculation Method', fontsize=10)
        self.k_value_ax.set_ylabel('Hydraulic Conductivity K (m/s)', fontsize=10)
        self.k_value_ax.set_title(f'K-Value Comparison: {self.sample_name}', fontsize=12, fontweight='bold')
        self.k_value_ax.set_xticks(x_pos)
        self.k_value_ax.set_xticklabels(methods, rotation=45, ha='right')
        self.k_value_ax.set_yscale('log')
        self.k_value_ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # Add min/max/mean lines
        if k_values:
            mean_k = np.mean(k_values)
            min_k = min(k_values)
            max_k = max(k_values)
            
            self.k_value_ax.axhline(y=mean_k, color='red', linestyle='-', alpha=0.5, 
                                   label=f'Mean: {mean_k:.2e} m/s')
            self.k_value_ax.axhline(y=min_k, color='blue', linestyle=':', alpha=0.5,
                                   label=f'Min: {min_k:.2e} m/s')
            self.k_value_ax.axhline(y=max_k, color='green', linestyle=':', alpha=0.5,
                                   label=f'Max: {max_k:.2e} m/s')
            
            self.k_value_ax.legend(loc='upper right', fontsize=8)
        
        # Adjust layout and redraw
        self.figure.tight_layout()
        self.canvas.draw()
        
    def reset_view(self):
        """Reset plot view to default zoom"""
        if self.grain_data:
            diameters, cumulative = self.grain_data
            self.grain_size_ax.set_xlim(min(diameters)*0.5, max(diameters)*2)
            self.grain_size_ax.set_ylim(0, 100)
        else:
            self.grain_size_ax.set_xlim(0.001, 100)
            self.grain_size_ax.set_ylim(0, 100)
            
        if self.k_results:
            k_values = list(self.k_results.values())
            self.k_value_ax.set_ylim(min(k_values)*0.1, max(k_values)*10)
        
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