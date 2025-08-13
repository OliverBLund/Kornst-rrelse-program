"""
Dataset tab containing plot workspace, results, and statistics for a single dataset
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QGroupBox, QPushButton, QHBoxLayout, QMessageBox,
    QHeaderView
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, pyqtSignal
from typing import Optional, List, Dict
import numpy as np

from data_loader import GrainSizeData
from k_calculations import KCalculator, KCalculationResult


class DatasetTab(QWidget):
    """
    A complete dataset tab with nested tabs for plots, results, and statistics
    """
    
    # Signals
    data_updated = pyqtSignal(str)  # Emitted when dataset data changes
    calculation_complete = pyqtSignal(str, list)  # dataset_name, results
    
    def __init__(self, dataset: GrainSizeData, parent=None):
        super().__init__(parent)
        self.dataset = dataset
        self.k_calculator = KCalculator()
        self.current_results: List[KCalculationResult] = []
        self.temperature = 20.0  # Default, will be updated
        self.porosity = 0.4  # Default, will be updated
        
        self.init_ui()
        self.load_dataset_data()
    
    def init_ui(self):
        """Initialize the UI with nested tabs"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)  # Reduce margins
        
        # Create nested tab widget
        self.nested_tabs = QTabWidget()
        
        # Compact styling for nested tabs
        self.nested_tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 2px 8px;
                font-size: 9px;
                min-height: 16px;
                max-height: 20px;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                margin-top: -1px;
            }
        """)
        
        # Import here to avoid circular imports
        from .plot_workspace import PlotWorkspace
        
        # Plot Workspace tab
        self.plot_workspace = PlotWorkspace(self.dataset)
        self.nested_tabs.addTab(self.plot_workspace, "Plot")
        
        # Results tab
        self.results_widget = self.create_results_tab()
        self.nested_tabs.addTab(self.results_widget, "Results")
        
        # Statistics tab
        self.statistics_widget = self.create_statistics_tab()
        self.nested_tabs.addTab(self.statistics_widget, "Stats")
        
        layout.addWidget(self.nested_tabs)
    
    def create_results_tab(self):
        """Create the results tab with K-value calculations"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Results table
        results_group = QGroupBox(f"Hydraulic Conductivity Results - {self.dataset.sample_name}")
        results_layout = QVBoxLayout(results_group)
        
        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Method", "K (m/s)", "Formula", "Status"])
        
        # Set header properties
        header = self.results_table.horizontalHeader()
        if header:
            header.setStretchLastSection(True)
        
        results_layout.addWidget(self.results_table)
        layout.addWidget(results_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.recalculate_btn = QPushButton("🔄 Recalculate")
        self.recalculate_btn.clicked.connect(self.calculate_k_values)
        
        self.export_btn = QPushButton("📤 Export Results")
        self.export_btn.clicked.connect(self.export_results)
        
        button_layout.addWidget(self.recalculate_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        return widget
    
    def create_statistics_tab(self):
        """Create the statistics tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Grain size statistics
        grain_group = QGroupBox(f"Grain Size Statistics - {self.dataset.sample_name}")
        grain_layout = QVBoxLayout(grain_group)
        
        self.grain_stats_text = QTextEdit()
        self.grain_stats_text.setReadOnly(True)
        self.grain_stats_text.setMaximumHeight(250)
        
        grain_layout.addWidget(self.grain_stats_text)
        layout.addWidget(grain_group)
        
        # K-value statistics
        k_group = QGroupBox("Hydraulic Conductivity Statistics")
        k_layout = QVBoxLayout(k_group)
        
        self.k_stats_text = QTextEdit()
        self.k_stats_text.setReadOnly(True)
        self.k_stats_text.setMaximumHeight(250)
        
        k_layout.addWidget(self.k_stats_text)
        layout.addWidget(k_group)
        
        layout.addStretch()
        
        return widget
    
    def load_dataset_data(self):
        """Load and display the dataset data"""
        # Update plot
        self.plot_workspace.update_plot(
            self.dataset.particle_sizes,
            self.dataset.percent_passing,
            self.dataset.sample_name
        )
        
        # Update grain size statistics
        self.update_grain_statistics()
        
        # Clear K statistics (not calculated yet)
        self.k_stats_text.setPlainText("Click 'Recalculate' in the Results tab to compute K values")
    
    def update_grain_statistics(self):
        """Update the grain size statistics display"""
        stats_text = f"Sample: {self.dataset.sample_name}\n"
        stats_text += "=" * 50 + "\n\n"
        
        # Basic info
        stats_text += f"Temperature: {self.temperature}°C\n"
        stats_text += f"Porosity: {self.porosity}\n"
        stats_text += f"Data Points: {len(self.dataset.particle_sizes)}\n\n"
        
        # Grain size statistics
        stats_text += "Characteristic Grain Sizes:\n"
        stats_text += "-" * 30 + "\n"
        
        d10 = self.dataset.get_d10()
        d20 = self.dataset.get_d20()
        d30 = self.dataset.get_d30()
        d50 = self.dataset.get_d50()
        d60 = self.dataset.get_d60()
        
        stats_text += f"D10: {d10:.3f} mm\n" if d10 else "D10: N/A\n"
        stats_text += f"D20: {d20:.3f} mm\n" if d20 else "D20: N/A\n"
        stats_text += f"D30: {d30:.3f} mm\n" if d30 else "D30: N/A\n"
        stats_text += f"D50: {d50:.3f} mm\n" if d50 else "D50: N/A\n"
        stats_text += f"D60: {d60:.3f} mm\n" if d60 else "D60: N/A\n"
        
        # Calculate uniformity coefficient
        if d10 and d60:
            cu = d60 / d10
            stats_text += f"\nUniformity Coefficient (Cu): {cu:.2f}\n"
            
            # Classification based on Cu
            if cu < 4:
                stats_text += "Classification: Uniform\n"
            elif cu < 6:
                stats_text += "Classification: Moderately graded\n"
            else:
                stats_text += "Classification: Well-graded\n"
        
        # Calculate coefficient of curvature
        if d10 and d30 and d60:
            cc = (d30 * d30) / (d10 * d60)
            stats_text += f"Coefficient of Curvature (Cc): {cc:.2f}\n"
        
        # Soil classification
        stats_text += f"\nSoil Type: {self.dataset.classify_soil()}\n"
        
        self.grain_stats_text.setPlainText(stats_text)
    
    def set_parameters(self, temperature: float, porosity: float):
        """Update calculation parameters"""
        self.temperature = temperature
        self.porosity = porosity
        self.update_grain_statistics()
    
    def calculate_k_values(self, selected_methods: Optional[List[str]] = None):
        """Calculate K values for this dataset"""
        if selected_methods is None:
            # Default methods if none specified
            selected_methods = [
                "Hazen", "Terzaghi", "Beyer", "Slichter", 
                "Kozeny-Carman", "Shepherd", "USBR", "Zunker", 
                "Zamarin", "Sauerbrei"
            ]
        
        # Prepare grain data
        grain_data = {}
        for key, value in {
            'D10': self.dataset.get_d10(),
            'D20': self.dataset.get_d20(),
            'D30': self.dataset.get_d30(),
            'D50': self.dataset.get_d50(),
            'D60': self.dataset.get_d60()
        }.items():
            if value is not None:
                grain_data[key] = value
        
        # Calculate K values
        self.current_results = self.k_calculator.calculate_all_methods(
            grain_data,
            temperature=self.temperature,
            porosity=self.porosity,
            selected_methods=selected_methods
        )
        
        # Update results table
        self.update_results_table()
        
        # Update K statistics
        self.update_k_statistics()
        
        # Update plot with K results
        if self.current_results:
            k_dict = {r.method_name: r.k_value for r in self.current_results 
                     if r.k_value is not None and r.k_value > 0}
            self.plot_workspace.add_k_results(k_dict)
        
        # Emit signal
        self.calculation_complete.emit(self.dataset.sample_name, self.current_results)
    
    def update_results_table(self):
        """Update the results table with calculation results"""
        self.results_table.setRowCount(len(self.current_results))
        
        for row, result in enumerate(self.current_results):
            # Method name
            self.results_table.setItem(row, 0, QTableWidgetItem(result.method_name))
            
            # K value
            k_item = QTableWidgetItem()
            if result.k_value is not None and result.k_value > 0:
                k_item.setText(f"{result.k_value:.2e}")
            else:
                k_item.setText("N/A")
            self.results_table.setItem(row, 1, k_item)
            
            # Formula
            self.results_table.setItem(row, 2, QTableWidgetItem(result.formula_used))
            
            # Status with color coding
            status = result.status.value if hasattr(result.status, 'value') else str(result.status)
            status_item = QTableWidgetItem(status)
            
            if result.status_message:
                status_item.setToolTip(result.status_message)
            
            # Color code based on status
            if "OK" in status:
                status_item.setBackground(QColor(200, 255, 200))
            elif "Warning" in status:
                status_item.setBackground(QColor(255, 255, 200))
            elif "Error" in status:
                status_item.setBackground(QColor(255, 200, 200))
            
            self.results_table.setItem(row, 3, status_item)
        
        # Resize columns
        self.results_table.resizeColumnsToContents()
    
    def update_k_statistics(self):
        """Update K-value statistics"""
        if not self.current_results:
            self.k_stats_text.setPlainText("No K-value calculations available")
            return
        
        # Get valid K values
        valid_results = [r for r in self.current_results 
                        if r.k_value is not None and r.k_value > 0]
        
        if not valid_results:
            self.k_stats_text.setPlainText("No valid K-value calculations")
            return
        
        k_values = [r.k_value for r in valid_results]
        
        # Calculate statistics
        mean_k = np.mean(k_values)
        median_k = np.median(k_values)
        std_k = np.std(k_values)
        min_k = np.min(k_values)
        max_k = np.max(k_values)
        
        # Find methods for min/max
        min_method = next(r.method_name for r in valid_results if r.k_value == min_k)
        max_method = next(r.method_name for r in valid_results if r.k_value == max_k)
        
        # Create statistics text
        stats_text = f"""Hydraulic Conductivity Statistics:
{'='*50}

Sample: {self.dataset.sample_name}
Temperature: {self.temperature}°C
Porosity: {self.porosity}

Valid Calculations: {len(valid_results)} / {len(self.current_results)}

Statistical Summary:
Mean K: {mean_k:.2e} m/s
Median K: {median_k:.2e} m/s
Std Dev: {std_k:.2e} m/s
Min K: {min_k:.2e} m/s ({min_method})
Max K: {max_k:.2e} m/s ({max_method})
Variability: {max_k/min_k:.1f}x difference

Permeability Classification:
"""
        # Add permeability classification
        if mean_k > 1e-2:
            stats_text += "Very High Permeability (Gravel)"
        elif mean_k > 1e-4:
            stats_text += "High Permeability (Clean Sand)"
        elif mean_k > 1e-5:
            stats_text += "Moderate Permeability (Fine Sand)"
        elif mean_k > 1e-7:
            stats_text += "Low Permeability (Silt)"
        else:
            stats_text += "Very Low Permeability (Clay)"
        
        self.k_stats_text.setPlainText(stats_text)
    
    def export_results(self):
        """Export results to file"""
        # TODO: Implement export functionality
        QMessageBox.information(self, "Export", 
                              f"Export functionality for {self.dataset.sample_name} will be implemented")
    
    def get_dataset_name(self) -> str:
        """Get the dataset name"""
        return self.dataset.sample_name
    
    def get_dataset(self) -> GrainSizeData:
        """Get the dataset object"""
        return self.dataset
    
    def get_results(self) -> List[KCalculationResult]:
        """Get the current K-calculation results"""
        return self.current_results