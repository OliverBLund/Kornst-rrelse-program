"""
Comparison tab for comparing multiple datasets
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QCheckBox, QPushButton, QLabel,
    QGroupBox, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from typing import List, Dict, Optional
import numpy as np

from data_loader import GrainSizeData
from k_calculations import KCalculationResult
from .comparison_plot_widget import ComparisonPlotWidget


class ComparisonTab(QWidget):
    """
    Tab for comparing multiple datasets side by side
    """
    
    # Signals
    comparison_updated = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dataset_tabs = []  # Will be populated by main window
        self.selected_datasets = []
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        
        # Control bar for selecting datasets
        control_bar = self.create_control_bar()
        layout.addLayout(control_bar)
        
        # Content tabs for different comparison views
        self.content_tabs = QTabWidget()
        
        # Overlay plots tab
        self.overlay_widget = self.create_overlay_plots_tab()
        self.content_tabs.addTab(self.overlay_widget, "📊 Overlay Plots")
        
        # Comparison table tab
        self.comparison_table_widget = self.create_comparison_table_tab()
        self.content_tabs.addTab(self.comparison_table_widget, "📋 Comparison Table")
        
        # Statistical analysis tab
        self.stats_widget = self.create_statistical_analysis_tab()
        self.content_tabs.addTab(self.stats_widget, "📈 Statistical Analysis")
        
        layout.addWidget(self.content_tabs)
    
    def create_control_bar(self):
        """Create the control bar for dataset selection"""
        control_layout = QHBoxLayout()
        
        control_layout.addWidget(QLabel("Select Datasets to Compare:"))
        
        # Dataset checkboxes will be added dynamically
        self.dataset_checks_layout = QHBoxLayout()
        control_layout.addLayout(self.dataset_checks_layout)
        
        control_layout.addStretch()
        
        # Update button
        self.update_btn = QPushButton("🔄 Update Comparison")
        self.update_btn.clicked.connect(self.update_comparison)
        control_layout.addWidget(self.update_btn)
        
        # Export button
        self.export_btn = QPushButton("📤 Export Comparison")
        self.export_btn.clicked.connect(self.export_comparison)
        control_layout.addWidget(self.export_btn)
        
        return control_layout
    
    def create_overlay_plots_tab(self):
        """Create the enhanced plots tab with ComparisonPlotWidget"""
        # Use the new ComparisonPlotWidget
        self.comparison_plot_widget = ComparisonPlotWidget()
        return self.comparison_plot_widget
    
    def create_comparison_table_tab(self):
        """Create the comparison table tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Grain size parameters table
        grain_group = QGroupBox("Grain Size Parameters Comparison")
        grain_layout = QVBoxLayout(grain_group)
        
        self.grain_comparison_table = QTableWidget()
        grain_layout.addWidget(self.grain_comparison_table)
        layout.addWidget(grain_group)
        
        # K-values comparison table
        k_group = QGroupBox("K-Values Comparison")
        k_layout = QVBoxLayout(k_group)
        
        self.k_comparison_table = QTableWidget()
        k_layout.addWidget(self.k_comparison_table)
        layout.addWidget(k_group)
        
        return widget
    
    def create_statistical_analysis_tab(self):
        """Create the statistical analysis tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Statistical analysis text
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        
        layout.addWidget(self.stats_text)
        
        return widget
    
    def set_dataset_tabs(self, dataset_tabs: List):
        """Set the available dataset tabs"""
        self.dataset_tabs = dataset_tabs
        self.update_dataset_checkboxes()
    
    def update_dataset_checkboxes(self):
        """Update the dataset selection checkboxes"""
        # Clear existing checkboxes
        while self.dataset_checks_layout.count():
            item = self.dataset_checks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add new checkboxes
        for tab in self.dataset_tabs:
            checkbox = QCheckBox(tab.get_dataset_name())
            checkbox.setChecked(True)
            self.dataset_checks_layout.addWidget(checkbox)
    
    def get_selected_datasets(self) -> List:
        """Get the currently selected datasets"""
        selected = []
        for i in range(self.dataset_checks_layout.count()):
            checkbox = self.dataset_checks_layout.itemAt(i).widget()
            if checkbox and checkbox.isChecked():
                # Find corresponding dataset tab
                for tab in self.dataset_tabs:
                    if tab.get_dataset_name() == checkbox.text():
                        selected.append(tab)
                        break
        return selected
    
    def update_comparison(self):
        """Update all comparison views"""
        self.selected_datasets = self.get_selected_datasets()
        
        if len(self.selected_datasets) < 2:
            QMessageBox.information(self, "Select Datasets", 
                                  "Please select at least 2 datasets to compare")
            return
        
        # Update all views
        self.update_overlay_plot()
        self.update_comparison_tables()
        self.update_statistical_analysis()
        
        self.comparison_updated.emit()
    
    def update_overlay_plot(self):
        """Update the plot widget with selected datasets"""
        if not self.selected_datasets:
            return
        
        # Update the comparison plot widget with selected datasets
        self.comparison_plot_widget.set_datasets(self.selected_datasets)
        self.comparison_plot_widget.refresh_plot()
    
    def update_comparison_tables(self):
        """Update the comparison tables"""
        if not self.selected_datasets:
            return
        
        # Update grain size parameters table
        params = ["D10 (mm)", "D20 (mm)", "D30 (mm)", "D50 (mm)", "D60 (mm)",
                 "Uniformity Coefficient", "Curvature Coefficient", "Classification"]
        
        self.grain_comparison_table.setRowCount(len(params))
        self.grain_comparison_table.setColumnCount(len(self.selected_datasets) + 1)
        
        # Set headers
        headers = ["Parameter"] + [tab.get_dataset_name() for tab in self.selected_datasets]
        self.grain_comparison_table.setHorizontalHeaderLabels(headers)
        
        # Fill data
        for row, param in enumerate(params):
            self.grain_comparison_table.setItem(row, 0, QTableWidgetItem(param))
            
            for col, tab in enumerate(self.selected_datasets, 1):
                dataset = tab.get_dataset()
                value = ""
                
                if param == "D10 (mm)":
                    d10 = dataset.get_d10()
                    value = f"{d10:.3f}" if d10 else "N/A"
                elif param == "D20 (mm)":
                    d20 = dataset.get_d20()
                    value = f"{d20:.3f}" if d20 else "N/A"
                elif param == "D30 (mm)":
                    d30 = dataset.get_d30()
                    value = f"{d30:.3f}" if d30 else "N/A"
                elif param == "D50 (mm)":
                    d50 = dataset.get_d50()
                    value = f"{d50:.3f}" if d50 else "N/A"
                elif param == "D60 (mm)":
                    d60 = dataset.get_d60()
                    value = f"{d60:.3f}" if d60 else "N/A"
                elif param == "Uniformity Coefficient":
                    d10, d60 = dataset.get_d10(), dataset.get_d60()
                    value = f"{d60/d10:.2f}" if d10 and d60 else "N/A"
                elif param == "Curvature Coefficient":
                    d10, d30, d60 = dataset.get_d10(), dataset.get_d30(), dataset.get_d60()
                    value = f"{(d30*d30)/(d10*d60):.2f}" if d10 and d30 and d60 else "N/A"
                elif param == "Classification":
                    value = dataset.classify_soil()
                
                self.grain_comparison_table.setItem(row, col, QTableWidgetItem(value))
        
        # Resize columns
        self.grain_comparison_table.resizeColumnsToContents()
        
        # Update K-values table if calculations exist
        self.update_k_values_table()
    
    def update_k_values_table(self):
        """Update the K-values comparison table"""
        # Get all unique methods from all datasets
        all_methods = set()
        for tab in self.selected_datasets:
            results = tab.get_results()
            for result in results:
                all_methods.add(result.method_name)
        
        if not all_methods:
            self.k_comparison_table.setRowCount(1)
            self.k_comparison_table.setColumnCount(1)
            self.k_comparison_table.setItem(0, 0, 
                QTableWidgetItem("No K-value calculations available"))
            return
        
        methods = sorted(list(all_methods))
        
        self.k_comparison_table.setRowCount(len(methods) + 2)  # +2 for Mean and Range
        self.k_comparison_table.setColumnCount(len(self.selected_datasets) + 1)
        
        # Set headers
        headers = ["Method"] + [tab.get_dataset_name() for tab in self.selected_datasets]
        self.k_comparison_table.setHorizontalHeaderLabels(headers)
        
        # Fill K-values
        for row, method in enumerate(methods):
            self.k_comparison_table.setItem(row, 0, QTableWidgetItem(method))
            
            for col, tab in enumerate(self.selected_datasets, 1):
                results = tab.get_results()
                k_value = None
                
                for result in results:
                    if result.method_name == method:
                        k_value = result.k_value
                        break
                
                value = f"{k_value:.2e}" if k_value else "N/A"
                self.k_comparison_table.setItem(row, col, QTableWidgetItem(value))
        
        # Add mean row
        mean_row = len(methods)
        self.k_comparison_table.setItem(mean_row, 0, QTableWidgetItem("Mean K"))
        
        for col, tab in enumerate(self.selected_datasets, 1):
            results = tab.get_results()
            valid_k = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]
            if valid_k:
                mean_k = np.mean(valid_k)
                self.k_comparison_table.setItem(mean_row, col, 
                    QTableWidgetItem(f"{mean_k:.2e}"))
            else:
                self.k_comparison_table.setItem(mean_row, col, 
                    QTableWidgetItem("N/A"))
        
        # Add range row
        range_row = len(methods) + 1
        self.k_comparison_table.setItem(range_row, 0, QTableWidgetItem("Range"))
        
        for col, tab in enumerate(self.selected_datasets, 1):
            results = tab.get_results()
            valid_k = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]
            if valid_k:
                min_k, max_k = np.min(valid_k), np.max(valid_k)
                self.k_comparison_table.setItem(range_row, col, 
                    QTableWidgetItem(f"{min_k:.1e} - {max_k:.1e}"))
            else:
                self.k_comparison_table.setItem(range_row, col, 
                    QTableWidgetItem("N/A"))
        
        # Resize columns
        self.k_comparison_table.resizeColumnsToContents()
    
    def update_statistical_analysis(self):
        """Update the statistical analysis text"""
        if not self.selected_datasets:
            self.stats_text.setPlainText("Select datasets to compare")
            return
        
        analysis = "Statistical Comparison Analysis\n"
        analysis += "=" * 50 + "\n\n"
        
        # Dataset names
        analysis += "Datasets Compared:\n"
        for tab in self.selected_datasets:
            analysis += f"  • {tab.get_dataset_name()}\n"
        analysis += "\n"
        
        # Grain size statistics
        analysis += "Grain Size Variability:\n"
        analysis += "-" * 30 + "\n"
        
        for tab in self.selected_datasets:
            dataset = tab.get_dataset()
            d10, d60 = dataset.get_d10(), dataset.get_d60()
            if d10 and d60:
                cu = d60 / d10
                analysis += f"{dataset.sample_name}:\n"
                analysis += f"  Cu = {cu:.2f} "
                if cu < 4:
                    analysis += "(Uniform)\n"
                elif cu < 6:
                    analysis += "(Moderately graded)\n"
                else:
                    analysis += "(Well-graded)\n"
        
        analysis += "\n"
        
        # K-value comparison
        analysis += "K-Value Comparison:\n"
        analysis += "-" * 30 + "\n"
        
        all_k_values = {}
        for tab in self.selected_datasets:
            results = tab.get_results()
            valid_k = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]
            if valid_k:
                all_k_values[tab.get_dataset_name()] = valid_k
        
        if all_k_values:
            # Find highest and lowest
            mean_k_values = {name: np.mean(k_list) for name, k_list in all_k_values.items()}
            
            if mean_k_values:
                highest = max(mean_k_values.items(), key=lambda x: x[1])
                lowest = min(mean_k_values.items(), key=lambda x: x[1])
                
                analysis += f"Highest mean K: {highest[0]} ({highest[1]:.2e} m/s)\n"
                analysis += f"Lowest mean K: {lowest[0]} ({lowest[1]:.2e} m/s)\n"
                analysis += f"Variability: {highest[1]/lowest[1]:.1f}x difference\n\n"
        
        # Soil classification summary
        analysis += "Soil Classifications:\n"
        analysis += "-" * 30 + "\n"
        
        classifications = {}
        for tab in self.selected_datasets:
            dataset = tab.get_dataset()
            soil_type = dataset.classify_soil()
            classifications[dataset.sample_name] = soil_type
        
        for name, soil_type in classifications.items():
            analysis += f"{name}: {soil_type}\n"
        
        self.stats_text.setPlainText(analysis)
    
    def export_comparison(self):
        """Export comparison results"""
        from PyQt6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Comparison Plot",
            "comparison_plot.png",
            "PNG Files (*.png);;SVG Files (*.svg)"
        )
        
        if file_path:
            try:
                self.comparison_plot_widget.figure.savefig(file_path, dpi=300, bbox_inches='tight')
                QMessageBox.information(self, "Export Successful", 
                                      f"Plot exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", 
                                   f"Failed to export plot:\n{str(e)}")