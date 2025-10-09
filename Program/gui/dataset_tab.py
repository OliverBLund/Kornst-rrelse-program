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
from k_calculations import KCalculator, KCalculationResult, CalculationStatus


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
        # Use dataset-specific values instead of global defaults
        self.temperature = dataset.temperature
        base_porosity = (
            dataset.current_porosity
            if dataset.current_porosity is not None
            else dataset.calculated_porosity
            if dataset.calculated_porosity is not None
            else dataset.porosity
        )
        if base_porosity is None:
            base_porosity = 0.40
        if dataset.current_porosity is None:
            dataset.current_porosity = base_porosity
        self.porosity = base_porosity
        
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
        
        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(["Method", "K (cm/s)", "K (m/s)", "K (m/d)", "Formula", "Status"])
        
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

        # Porosity control section
        porosity_group = QGroupBox("Porosity Settings")
        porosity_layout = QVBoxLayout(porosity_group)

        # Porosity display and edit controls
        porosity_controls_layout = QHBoxLayout()

        # Show calculated vs current porosity
        from PyQt6.QtWidgets import QLabel, QLineEdit, QPushButton
        calculated_porosity = self.dataset.calculated_porosity
        current_text = f"{self.porosity:.4f}" if self.porosity is not None else "N/A"
        if calculated_porosity is not None:
            porosity_info = QLabel(f"Calculated: {calculated_porosity:.4f} | Current: {current_text}")
        else:
            porosity_info = QLabel(f"Current: {current_text} [Manual]")

        # Add edit capability
        self.porosity_edit = QLineEdit()
        self.porosity_edit.setText(current_text)
        self.porosity_edit.setMaximumWidth(100)

        update_porosity_btn = QPushButton("Update")
        update_porosity_btn.clicked.connect(self._update_porosity)

        reset_porosity_btn = QPushButton("Reset to Calculated")
        reset_porosity_btn.clicked.connect(self._reset_porosity)
        if self.dataset.calculated_porosity is None:
            reset_porosity_btn.setEnabled(False)

        porosity_controls_layout.addWidget(porosity_info)
        porosity_controls_layout.addWidget(QLabel("Edit:"))
        porosity_controls_layout.addWidget(self.porosity_edit)
        porosity_controls_layout.addWidget(update_porosity_btn)
        porosity_controls_layout.addWidget(reset_porosity_btn)
        porosity_controls_layout.addStretch()

        porosity_layout.addLayout(porosity_controls_layout)
        layout.addWidget(porosity_group)

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

        # Porosity display - show both calculated and current
        calculated_porosity = self.dataset.calculated_porosity
        current_porosity = self.porosity
        if calculated_porosity is not None:
            stats_text += f"Porosity (Calculated): {calculated_porosity:.4f}\n"
            if current_porosity is not None:
                stats_text += f"Porosity (Current): {current_porosity:.4f}"
                if abs(calculated_porosity - current_porosity) > 0.001:
                    stats_text += " [Modified]\n"
                else:
                    stats_text += "\n"
            else:
                stats_text += "Porosity (Current): N/A [Missing]\n"
        else:
            current_text = f"{current_porosity:.4f}" if current_porosity is not None else "N/A"
            stats_text += f"Porosity: {current_text} [Manual]\n"

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
        
        # Calculate uniformity coefficient and add Urumovic info
        if d10 and d60:
            cu = d60 / d10
            stats_text += f"\nUniformity Coefficient (Cu): {cu:.2f}\n"

            # Add geometric mean for Urumovic calculation
            dgeom = self.dataset._calculate_geometric_mean_grain_size()
            if dgeom:
                stats_text += f"Geometric Mean (dgeom): {dgeom:.3f} mm\n"

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
    
    def set_parameters(self, temperature: float):
        """Update calculation parameters"""
        self.temperature = temperature
        self.dataset.temperature = temperature
        self.update_grain_statistics()
    
    def calculate_k_values(self, selected_methods: Optional[List[str]] = None):
        """Calculate K values for this dataset"""
        if selected_methods is None:
            # Get all available methods from calculator
            selected_methods = self.k_calculator.get_all_method_names()
        
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

        # Provide full grain size distribution for methods that need fraction data
        grain_data['particle_sizes'] = list(self.dataset.particle_sizes)
        grain_data['percent_passing'] = list(self.dataset.percent_passing)

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
            k_dict = {}
            flagged_methods = set()
            for result in self.current_results:
                if result.k_value is not None and result.k_value > 0:
                    k_dict[result.method_name] = result.k_value
                if result.status != CalculationStatus.OK or not result.conditions_met:
                    flagged_methods.add(result.method_name)
            self.plot_workspace.add_k_results(k_dict, flagged_methods)
        
        # Emit signal
        self.calculation_complete.emit(self.dataset.sample_name, self.current_results)
    
    def update_results_table(self):
        """Update the results table with calculation results"""
        self.results_table.setRowCount(len(self.current_results))
        
        for row, result in enumerate(self.current_results):
            # Method name
            self.results_table.setItem(row, 0, QTableWidgetItem(result.method_name))

            # K values in different units
            if result.k_value is not None and result.k_value > 0:
                k_m_s = result.k_value

                # Convert to different units
                k_cm_s = k_m_s * 100.0  # m/s to cm/s
                k_m_d = k_m_s * 86400.0  # m/s to m/d

                # K (cm/s) column
                cm_s_item = QTableWidgetItem(f"{k_cm_s:.3e}")
                self.results_table.setItem(row, 1, cm_s_item)

                # K (m/s) column
                m_s_item = QTableWidgetItem(f"{k_m_s:.2e}")
                self.results_table.setItem(row, 2, m_s_item)

                # K (m/d) column
                m_d_item = QTableWidgetItem(f"{k_m_d:.1f}")
                self.results_table.setItem(row, 3, m_d_item)
            else:
                # N/A for all unit columns
                for col in [1, 2, 3]:
                    self.results_table.setItem(row, col, QTableWidgetItem("N/A"))

            # Formula (column 4)
            self.results_table.setItem(row, 4, QTableWidgetItem(result.formula_used))

            # Status with color coding (column 5)
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
            
            self.results_table.setItem(row, 5, status_item)
        
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

    def _update_porosity(self):
        """Update porosity from user input"""
        try:
            new_porosity = float(self.porosity_edit.text())

            # Validate porosity range
            if new_porosity < 0.01 or new_porosity > 0.99:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Invalid Porosity",
                                  "Porosity must be between 0.01 and 0.99")
                return

            # Update values
            self.porosity = new_porosity
            self.dataset.current_porosity = new_porosity

            # Refresh displays
            self.update_grain_statistics()

            # Show success message
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Porosity Updated",
                                  f"Porosity updated to {new_porosity:.4f}")

        except ValueError:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid Input",
                              "Please enter a valid number for porosity")

    def _reset_porosity(self):
        """Reset porosity to calculated value"""
        if self.dataset.calculated_porosity is not None:
            self.porosity = self.dataset.calculated_porosity
            self.dataset.current_porosity = self.dataset.calculated_porosity
            self.porosity_edit.setText(f"{self.porosity:.4f}")

            # Refresh displays
            self.update_grain_statistics()

            # Show success message
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Porosity Reset",
                                  f"Porosity reset to calculated value: {self.porosity:.4f}")