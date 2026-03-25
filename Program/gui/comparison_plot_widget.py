"""
Enhanced plot widget for comparison tab with multiple display modes
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QToolButton,
    QComboBox, QLabel, QCheckBox, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Dict, Optional
from .matplotlib_canvas import FigureCanvas
from .theme import C, apply_matplotlib_style


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
        layout.addWidget(self.canvas)
    
    def create_toolbar(self):
        """Create the toolbar with plot controls"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #f5f5f0;
                border: 1px solid #d4c4a8;
                padding: 2px;
                spacing: 2px;
            }
            QToolButton, QRadioButton {
                padding: 2px 4px;
                font-size: 9px;
            }
            QComboBox {
                padding: 2px 4px;
                font-size: 9px;
                max-height: 20px;
            }
            QCheckBox {
                font-size: 9px;
                spacing: 2px;
            }
            QLabel {
                font-size: 9px;
                padding: 0 4px;
            }
        """)
        
        # Plot type selector
        plot_label = QLabel("Plot:")
        toolbar.addWidget(plot_label)
        
        self.plot_selector = QComboBox()
        self.plot_selector.addItems([
            "Distribution",
            "K-Values", 
            "Combined",
            "Cumulative",
            "Histogram"
        ])
        self.plot_selector.setMaximumWidth(100)
        self.plot_selector.currentTextChanged.connect(self.on_plot_type_changed)
        toolbar.addWidget(self.plot_selector)
        
        toolbar.addSeparator()
        
        # Display mode selector
        mode_label = QLabel("Mode:")
        toolbar.addWidget(mode_label)
        
        # Radio buttons for display mode
        self.overlay_radio = QRadioButton("Overlay")
        self.overlay_radio.setChecked(True)
        self.overlay_radio.toggled.connect(lambda checked: self._on_mode_toggled(checked, "overlay"))
        toolbar.addWidget(self.overlay_radio)
        
        self.grid_radio = QRadioButton("Grid")
        self.grid_radio.toggled.connect(lambda checked: self._on_mode_toggled(checked, "grid"))
        toolbar.addWidget(self.grid_radio)
        
        self.grouped_radio = QRadioButton("Grouped")
        self.grouped_radio.toggled.connect(lambda checked: self._on_mode_toggled(checked, "grouped"))
        self.grouped_radio.setVisible(False)  # Only show for bar charts
        toolbar.addWidget(self.grouped_radio)
        
        toolbar.addSeparator()
        
        # Grid layout selector (only visible in grid mode)
        self.grid_label = QLabel("Grid:")
        self.grid_label.setVisible(False)
        toolbar.addWidget(self.grid_label)
        
        self.grid_selector = QComboBox()
        self.grid_selector.addItems(["2x2", "3x2", "3x3", "4x3"])
        self.grid_selector.setMaximumWidth(60)
        self.grid_selector.setVisible(False)
        self.grid_selector.currentTextChanged.connect(self.on_grid_layout_changed)
        toolbar.addWidget(self.grid_selector)
        
        toolbar.addSeparator()
        
        # Display options
        self.grid_check = QCheckBox("Grid")
        self.grid_check.setChecked(True)
        self.grid_check.stateChanged.connect(self.update_display_options)
        toolbar.addWidget(self.grid_check)
        
        self.legend_check = QCheckBox("Legend")
        self.legend_check.setChecked(True)
        self.legend_check.stateChanged.connect(self.update_display_options)
        toolbar.addWidget(self.legend_check)
        
        toolbar.addSeparator()
        
        # Zoom controls
        zoom_in_btn = QToolButton()
        zoom_in_btn.setText("🔍+")
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar.addWidget(zoom_in_btn)
        
        zoom_out_btn = QToolButton()
        zoom_out_btn.setText("🔍-")
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar.addWidget(zoom_out_btn)
        
        reset_btn = QToolButton()
        reset_btn.setText("⟲")
        reset_btn.setToolTip("Reset View")
        reset_btn.clicked.connect(self.reset_view)
        toolbar.addWidget(reset_btn)
        
        # Add stretch
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy(), spacer.sizePolicy().verticalPolicy())
        toolbar.addWidget(spacer)
        
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
        
        for tab in dataset_tabs:
            dataset = tab.get_dataset()
            self.datasets.append(dataset)
            
            # Get K-results if available
            results = tab.get_results()
            if results:
                k_dict = {}
                for r in results:
                    if r.k_value is not None and r.k_value > 0:
                        k_dict[r.method_name] = r.k_value
                if k_dict:
                    self.k_results_dict[dataset.sample_name] = k_dict
    
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
        
        self.figure.tight_layout()
        self.canvas.draw()
        self.plot_updated.emit()
    
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
        
        # Get all unique methods
        all_methods = set()
        for k_dict in self.k_results_dict.values():
            all_methods.update(k_dict.keys())
        methods = self._ordered_methods(all_methods)
        
        # Prepare data
        n_datasets = len(self.k_results_dict)
        n_methods = len(methods)
        bar_width = 0.8 / n_datasets
        
        # Plot bars for each dataset
        for i, (name, k_dict) in enumerate(self.k_results_dict.items()):
            values = [k_dict.get(method, 0) for method in methods]
            positions = np.arange(n_methods) + i * bar_width
            color = self.dataset_colors[i % len(self.dataset_colors)]
            
            bars = ax.bar(positions, values, bar_width, label=name,
                          color=color, alpha=0.8, edgecolor='black', linewidth=0.5)
            
            # Add value labels
            for bar, val in zip(bars, values):
                if val > 0:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2, height*1.05,
                           f'{val:.1e}', ha='center', va='bottom', fontsize=6)
        
        ax.set_xlabel('Method', fontsize=10)
        ax.set_ylabel('K (m/s)', fontsize=10)
        ax.set_title('Hydraulic Conductivity Comparison', fontsize=12, fontweight='bold')
        ax.set_xticks(np.arange(n_methods) + bar_width * (n_datasets - 1) / 2)
        ax.set_xticklabels(methods, rotation=45, ha='right', fontsize=8)
        ax.set_yscale('log')
        
        if self.show_grid:
            ax.grid(True, axis='y', alpha=0.3)
        if self.show_legend:
            ax.legend(loc='best', fontsize=8)
    
    def plot_k_values_grouped(self):
        """Plot K-values grouped by dataset"""
        ax = self.figure.add_subplot(1, 1, 1)
        
        datasets = list(self.k_results_dict.keys())
        n_datasets = len(datasets)
        
        # Get all methods for each dataset
        all_methods = set()
        for k_dict in self.k_results_dict.values():
            all_methods.update(k_dict.keys())
        methods = self._ordered_methods(all_methods)
        
        bar_width = 0.8 / len(methods)
        
        # Plot grouped by dataset
        for i, method in enumerate(methods):
            values = [self.k_results_dict[ds].get(method, 0) for ds in datasets]
            positions = np.arange(n_datasets) + i * bar_width
            color = self.method_colors.get(method, '#888888')
            
            bars = ax.bar(positions, values, bar_width, label=method,
                          color=color, alpha=0.8, edgecolor='black', linewidth=0.5)
        
        ax.set_xlabel('Dataset', fontsize=10)
        ax.set_ylabel('K (m/s)', fontsize=10)
        ax.set_title('K-Values by Dataset', fontsize=12, fontweight='bold')
        ax.set_xticks(np.arange(n_datasets) + bar_width * (len(methods) - 1) / 2)
        ax.set_xticklabels(datasets, rotation=45, ha='right', fontsize=8)
        ax.set_yscale('log')
        
        if self.show_grid:
            ax.grid(True, axis='y', alpha=0.3)
        if self.show_legend:
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
            
            bars = ax.bar(range(len(methods)), values, color=colors, 
                         alpha=0.8, edgecolor='black', linewidth=0.5)
            
            ax.set_title(name, fontsize=9, fontweight='bold')
            ax.set_xlabel('Method', fontsize=8)
            ax.set_ylabel('K (m/s)', fontsize=8)
            ax.set_xticks(range(len(methods)))
            ax.set_xticklabels([m[:4] for m in methods], rotation=45, ha='right', fontsize=6)
            ax.set_yscale('log')
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
                
                bars = ax2.bar(range(len(methods)), values, alpha=0.8)
                ax2.set_title(f'{dataset.sample_name} - K', fontsize=8)
                ax2.set_xticks(range(len(methods)))
                ax2.set_xticklabels([m[:3] for m in methods], rotation=45, fontsize=6)
                ax2.set_yscale('log')
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
        ax.text(0.5, 0.5, message, transform=ax.transAxes,
               ha='center', va='center', fontsize=12, color='gray')
        ax.set_xticks([])
        ax.set_yticks([])
        self.canvas.draw()
    
    def zoom_in(self):
        """Zoom in on all axes"""
        for ax in self.figure.axes:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            
            # Zoom in by 20%
            if ax.get_xscale() == 'log':
                x_center = np.sqrt(xlim[0] * xlim[1])
                x_factor = np.sqrt(0.64)  # 0.8^2 for log scale
                ax.set_xlim(x_center/x_factor, x_center*x_factor)
            else:
                x_center = (xlim[0] + xlim[1]) / 2
                x_range = (xlim[1] - xlim[0]) * 0.4
                ax.set_xlim(x_center - x_range, x_center + x_range)
            
            if ax.get_yscale() == 'log':
                y_center = np.sqrt(ylim[0] * ylim[1])
                y_factor = np.sqrt(0.64)
                ax.set_ylim(y_center/y_factor, y_center*y_factor)
            else:
                y_center = (ylim[0] + ylim[1]) / 2
                y_range = (ylim[1] - ylim[0]) * 0.4
                ax.set_ylim(y_center - y_range, y_center + y_range)
        
        self.canvas.draw()
    
    def zoom_out(self):
        """Zoom out on all axes"""
        for ax in self.figure.axes:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            
            # Zoom out by 20%
            if ax.get_xscale() == 'log':
                x_center = np.sqrt(xlim[0] * xlim[1])
                x_factor = np.sqrt(1.44)  # 1.2^2 for log scale
                ax.set_xlim(x_center/x_factor, x_center*x_factor)
            else:
                x_center = (xlim[0] + xlim[1]) / 2
                x_range = (xlim[1] - xlim[0]) * 0.6
                ax.set_xlim(x_center - x_range, x_center + x_range)
            
            if ax.get_yscale() == 'log':
                y_center = np.sqrt(ylim[0] * ylim[1])
                y_factor = np.sqrt(1.44)
                ax.set_ylim(y_center/y_factor, y_center*y_factor)
            else:
                y_center = (ylim[0] + ylim[1]) / 2
                y_range = (ylim[1] - ylim[0]) * 0.6
                ax.set_ylim(y_center - y_range, y_center + y_range)
        
        self.canvas.draw()
    
    def reset_view(self):
        """Reset view on all axes"""
        self.refresh_plot()
