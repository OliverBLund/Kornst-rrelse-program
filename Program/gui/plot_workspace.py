"""
Plot workspace with collapsible sidebar and compact toolbar
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QFrame,
    QGroupBox, QComboBox, QCheckBox, QPushButton, QLabel,
    QSpinBox, QSlider, QFileDialog, QMessageBox, QToolBar,
    QToolButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QRect
from PyQt6.QtGui import QAction
from typing import Optional, Dict, List
import numpy as np

from data_loader import GrainSizeData
from .plot_widget import PlotWidget


class PlotWorkspace(QWidget):
    """
    The plot workspace with collapsible sidebar and main plot area
    """
    
    # Signals
    plot_exported = pyqtSignal(str)  # Emitted when plot is exported
    
    def __init__(self, dataset: GrainSizeData, parent=None):
        super().__init__(parent)
        self.dataset = dataset
        self.plot_widget = None
        self.k_results = {}
        self.sidebar_visible = False  # Start with sidebar hidden
        
        # Plot settings
        self.current_plot_type = "distribution"
        self.show_grid = True
        self.show_legend = True
        self.show_markers = False
        self.log_x_scale = True
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)
        
        # Create compact toolbar at the top
        toolbar = self.create_compact_toolbar()
        main_layout.addWidget(toolbar)
        
        # Create horizontal layout for sidebar and plot
        content_layout = QHBoxLayout()
        content_layout.setSpacing(2)
        
        # Create collapsible sidebar
        self.sidebar = self.create_sidebar()
        self.sidebar.setMaximumWidth(250)
        self.sidebar.setVisible(False)  # Hidden by default
        
        # Main plot area using existing PlotWidget
        self.plot_widget = PlotWidget()
        
        # Add to layout
        content_layout.addWidget(self.sidebar)
        content_layout.addWidget(self.plot_widget)
        
        main_layout.addLayout(content_layout)
    
    def create_compact_toolbar(self):
        """Create a compact toolbar with essential controls"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #f5f5f0;
                border: 1px solid #d4c4a8;
                padding: 2px;
                spacing: 2px;
            }
            QToolButton {
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
        """)
        
        # Toggle sidebar button
        self.toggle_sidebar_btn = QToolButton()
        self.toggle_sidebar_btn.setText("☰")
        self.toggle_sidebar_btn.setToolTip("Toggle Sidebar")
        self.toggle_sidebar_btn.clicked.connect(self.toggle_sidebar)
        toolbar.addWidget(self.toggle_sidebar_btn)
        
        toolbar.addSeparator()
        
        # Plot type selector
        plot_label = QLabel("Plot:")
        plot_label.setStyleSheet("font-size: 9px; padding: 0 4px;")
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
        self.plot_selector.currentTextChanged.connect(self.on_plot_type_changed_toolbar)
        toolbar.addWidget(self.plot_selector)
        
        toolbar.addSeparator()
        
        # Quick options
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
        
        toolbar.addSeparator()
        
        # Export button
        export_btn = QToolButton()
        export_btn.setText("💾")
        export_btn.setToolTip("Export Plot")
        export_btn.clicked.connect(lambda: self.export_plot("png"))
        toolbar.addWidget(export_btn)
        
        # Add stretch to push everything to the left
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy(), spacer.sizePolicy().verticalPolicy())
        toolbar.addWidget(spacer)
        
        return toolbar
    
    def create_sidebar(self):
        """Create the collapsible sidebar with plot controls"""
        sidebar = QFrame()
        sidebar.setFrameStyle(QFrame.Shape.Box)
        sidebar.setStyleSheet("""
            QFrame { 
                background-color: #f5f5f0;
                border: 1px solid #d4c4a8;
            }
            QGroupBox {
                font-size: 9px;
                padding-top: 15px;
                margin-top: 10px;
            }
            QGroupBox::title {
                font-size: 9px;
                padding: 2px;
            }
            QLabel {
                font-size: 9px;
            }
            QComboBox, QSpinBox, QPushButton, QCheckBox {
                font-size: 9px;
                padding: 2px;
                max-height: 20px;
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title = QLabel("Advanced Options")
        title.setStyleSheet("font-weight: bold; font-size: 10px;")
        layout.addWidget(title)
        
        # Axis Controls
        axis_group = QGroupBox("Axis Controls")
        axis_layout = QVBoxLayout(axis_group)
        
        axis_layout.addWidget(QLabel("X-Axis Scale:"))
        self.x_scale_combo = QComboBox()
        self.x_scale_combo.addItems(["Linear", "Logarithmic"])
        self.x_scale_combo.setCurrentText("Logarithmic")
        self.x_scale_combo.currentTextChanged.connect(self.update_axis_scale)
        axis_layout.addWidget(self.x_scale_combo)
        
        axis_layout.addWidget(QLabel("Y-Axis Range:"))
        y_range_layout = QHBoxLayout()
        self.y_min_spin = QSpinBox()
        self.y_min_spin.setRange(0, 100)
        self.y_min_spin.setValue(0)
        self.y_min_spin.valueChanged.connect(self.update_axis_range)
        y_range_layout.addWidget(self.y_min_spin)
        
        y_range_layout.addWidget(QLabel("to"))
        
        self.y_max_spin = QSpinBox()
        self.y_max_spin.setRange(0, 100)
        self.y_max_spin.setValue(100)
        self.y_max_spin.valueChanged.connect(self.update_axis_range)
        y_range_layout.addWidget(self.y_max_spin)
        
        axis_layout.addLayout(y_range_layout)
        
        # Display Options
        display_group = QGroupBox("Display Options")
        display_layout = QVBoxLayout(display_group)
        
        self.markers_check = QCheckBox("Show Data Points")
        self.markers_check.setChecked(False)
        self.markers_check.stateChanged.connect(self.update_display_options)
        display_layout.addWidget(self.markers_check)
        
        # Export Controls
        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout(export_group)
        
        self.export_svg_btn = QPushButton("Export as SVG")
        self.export_svg_btn.clicked.connect(lambda: self.export_plot("svg"))
        
        self.export_data_btn = QPushButton("Export Data")
        self.export_data_btn.clicked.connect(self.export_data)
        
        export_layout.addWidget(self.export_svg_btn)
        export_layout.addWidget(self.export_data_btn)
        
        # Add all groups to sidebar
        layout.addWidget(axis_group)
        layout.addWidget(display_group)
        layout.addWidget(export_group)
        layout.addStretch()
        
        return sidebar
    
    def toggle_sidebar(self):
        """Toggle sidebar visibility"""
        self.sidebar_visible = not self.sidebar_visible
        self.sidebar.setVisible(self.sidebar_visible)
        self.toggle_sidebar_btn.setText("✕" if self.sidebar_visible else "☰")
    
    def on_plot_type_changed_toolbar(self, text: str):
        """Handle plot type change from toolbar"""
        plot_map = {
            "Distribution": "distribution",
            "K-Values": "k-values",
            "Combined": "combined",
            "Cumulative": "cumulative",
            "Histogram": "histogram"
        }
        
        self.current_plot_type = plot_map.get(text, "distribution")
        self.refresh_plot()
    
    def zoom_in(self):
        """Zoom in on the plot"""
        if self.plot_widget and self.plot_widget.grain_size_ax:
            xlim = self.plot_widget.grain_size_ax.get_xlim()
            ylim = self.plot_widget.grain_size_ax.get_ylim()
            
            # Zoom in by 20%
            x_center = (xlim[0] + xlim[1]) / 2
            y_center = (ylim[0] + ylim[1]) / 2
            x_range = (xlim[1] - xlim[0]) * 0.4
            y_range = (ylim[1] - ylim[0]) * 0.4
            
            self.plot_widget.grain_size_ax.set_xlim(x_center - x_range, x_center + x_range)
            self.plot_widget.grain_size_ax.set_ylim(y_center - y_range, y_center + y_range)
            self.plot_widget.canvas.draw()
    
    def zoom_out(self):
        """Zoom out on the plot"""
        if self.plot_widget and self.plot_widget.grain_size_ax:
            xlim = self.plot_widget.grain_size_ax.get_xlim()
            ylim = self.plot_widget.grain_size_ax.get_ylim()
            
            # Zoom out by 20%
            x_center = (xlim[0] + xlim[1]) / 2
            y_center = (ylim[0] + ylim[1]) / 2
            x_range = (xlim[1] - xlim[0]) * 0.6
            y_range = (ylim[1] - ylim[0]) * 0.6
            
            self.plot_widget.grain_size_ax.set_xlim(x_center - x_range, x_center + x_range)
            self.plot_widget.grain_size_ax.set_ylim(y_center - y_range, y_center + y_range)
            self.plot_widget.canvas.draw()
    
    def reset_view(self):
        """Reset the plot view"""
        if self.plot_widget:
            self.plot_widget.reset_view()
    
    def update_display_options(self):
        """Update display options"""
        self.show_grid = self.grid_check.isChecked()
        self.show_legend = self.legend_check.isChecked()
        self.show_markers = self.markers_check.isChecked() if hasattr(self, 'markers_check') else False
        self.refresh_plot()
    
    def update_axis_scale(self, text: str):
        """Update axis scale"""
        self.log_x_scale = (text == "Logarithmic")
        self.refresh_plot()
    
    def update_axis_range(self):
        """Update axis range"""
        y_min = self.y_min_spin.value()
        y_max = self.y_max_spin.value()
        
        if self.plot_widget and self.plot_widget.grain_size_ax:
            self.plot_widget.grain_size_ax.set_ylim(y_min, y_max)
            self.plot_widget.canvas.draw()
    
    def refresh_plot(self):
        """Refresh the plot based on current settings"""
        if not self.plot_widget:
            return
        
        # Clear and recreate plot based on type
        if self.current_plot_type == "distribution":
            self.plot_widget.update_plot(
                self.dataset.particle_sizes,
                self.dataset.percent_passing,
                self.dataset.sample_name
            )
        elif self.current_plot_type == "k-values":
            if self.k_results:
                self.plot_widget.plot_k_values_only(self.k_results)
            else:
                # Show message that K-values need to be calculated
                self.plot_widget.figure.clear()
                ax = self.plot_widget.figure.add_subplot(1, 1, 1)
                ax.text(0.5, 0.5, 'Please calculate K-values first\n(Go to Results tab and click Recalculate)',
                       transform=ax.transAxes, ha='center', va='center',
                       fontsize=12, color='gray')
                ax.set_xticks([])
                ax.set_yticks([])
                self.plot_widget.canvas.draw()
        elif self.current_plot_type == "combined":
            # First ensure grain data is loaded
            self.plot_widget.update_plot(
                self.dataset.particle_sizes,
                self.dataset.percent_passing,
                self.dataset.sample_name
            )
            # Then show combined view
            self.plot_widget.plot_combined_view(self.k_results)
        elif self.current_plot_type == "cumulative":
            self.plot_cumulative_distribution()
        elif self.current_plot_type == "histogram":
            self.plot_histogram()
        
        # Apply display settings
        if self.plot_widget.grain_size_ax:
            self.plot_widget.grain_size_ax.grid(self.show_grid, which='both', alpha=0.3)
            if hasattr(self.plot_widget.grain_size_ax, 'legend_'):
                legend = self.plot_widget.grain_size_ax.legend_
                if legend:
                    legend.set_visible(self.show_legend)
        
        self.plot_widget.canvas.draw()
    
    def plot_cumulative_distribution(self):
        """Plot cumulative distribution"""
        if not self.plot_widget:
            return
        
        self.plot_widget.figure.clear()
        ax = self.plot_widget.figure.add_subplot(111)
        
        # Create cumulative distribution
        cumulative = np.array(self.dataset.percent_passing)
        sizes = np.array(self.dataset.particle_sizes)
        
        ax.plot(sizes, cumulative, 'g-', linewidth=2, label=self.dataset.sample_name)
        ax.set_xlabel('Grain Size (mm)')
        ax.set_ylabel('Cumulative Percent Passing (%)')
        ax.set_title(f'Cumulative Distribution - {self.dataset.sample_name}')
        
        if self.log_x_scale:
            ax.set_xscale('log')
        
        ax.grid(self.show_grid, which='both', alpha=0.3)
        if self.show_legend:
            ax.legend()
        
        self.plot_widget.grain_size_ax = ax
        self.plot_widget.figure.tight_layout()
        self.plot_widget.canvas.draw()
    
    def plot_histogram(self):
        """Plot histogram of grain sizes"""
        if not self.plot_widget:
            return
        
        self.plot_widget.figure.clear()
        ax = self.plot_widget.figure.add_subplot(111)
        
        # Create histogram data
        sizes = np.array(self.dataset.particle_sizes)
        passing = np.array(self.dataset.percent_passing)
        
        # Calculate frequency for each size class
        freq = np.diff(passing, prepend=0)
        
        # Create bar plot
        ax.bar(range(len(sizes)), freq, tick_label=[f"{s:.3f}" for s in sizes])
        ax.set_xlabel('Grain Size (mm)')
        ax.set_ylabel('Frequency (%)')
        ax.set_title(f'Grain Size Histogram - {self.dataset.sample_name}')
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
        
        ax.grid(self.show_grid, alpha=0.3)
        
        self.plot_widget.grain_size_ax = ax
        self.plot_widget.figure.tight_layout()
        self.plot_widget.canvas.draw()
    
    def update_plot(self, particle_sizes, percent_passing, sample_name):
        """Update the plot with new data"""
        if self.plot_widget:
            self.plot_widget.update_plot(particle_sizes, percent_passing, sample_name)
            self.refresh_plot()
    
    def add_k_results(self, k_results: Dict[str, float]):
        """Add K-calculation results to the plot"""
        self.k_results = k_results
        if self.current_plot_type in ["combined", "k-values"]:
            self.refresh_plot()
    
    def export_plot(self, format: str):
        """Export the plot to file"""
        if not self.plot_widget:
            return
        
        file_filter = {
            "png": "PNG Files (*.png)",
            "svg": "SVG Files (*.svg)"
        }
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export Plot as {format.upper()}",
            f"{self.dataset.sample_name}_plot.{format}",
            file_filter.get(format, "All Files (*)")
        )
        
        if file_path:
            try:
                self.plot_widget.figure.savefig(file_path, dpi=300, bbox_inches='tight')
                self.plot_exported.emit(file_path)
                QMessageBox.information(self, "Export Successful", 
                                      f"Plot exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", 
                                   f"Failed to export plot:\n{str(e)}")
    
    def export_data(self):
        """Export the plot data to CSV"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data as CSV",
            f"{self.dataset.sample_name}_data.csv",
            "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Grain Size (mm)", "Percent Passing (%)"])
                    for size, passing in zip(self.dataset.particle_sizes, 
                                           self.dataset.percent_passing):
                        writer.writerow([size, passing])
                
                QMessageBox.information(self, "Export Successful", 
                                      f"Data exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", 
                                   f"Failed to export data:\n{str(e)}")