"""
Dataset tab containing plot workspace, results, and statistics for a single dataset
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QGroupBox, QPushButton, QHBoxLayout, QMessageBox,
    QHeaderView, QLabel, QFrame, QTextBrowser, QSplitter
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

        # Summary statistics bar
        self.summary_frame = QFrame()
        self.summary_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Plain)
        self.summary_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        summary_layout = QHBoxLayout(self.summary_frame)
        summary_layout.setContentsMargins(10, 5, 10, 5)

        # Summary labels
        self.summary_total_label = QLabel("No calculations yet")
        self.summary_total_label.setStyleSheet("font-weight: bold; color: #333;")

        self.summary_valid_label = QLabel("")
        self.summary_valid_label.setStyleSheet("color: #006400;")  # Dark green

        self.summary_warning_label = QLabel("")
        self.summary_warning_label.setStyleSheet("color: #8B6914;")  # Dark yellow

        self.summary_error_label = QLabel("")
        self.summary_error_label.setStyleSheet("color: #8B0000;")  # Dark red

        self.summary_stats_label = QLabel("")
        self.summary_stats_label.setStyleSheet("color: #333; margin-left: 20px;")

        summary_layout.addWidget(self.summary_total_label)
        summary_layout.addWidget(QLabel("|"))
        summary_layout.addWidget(self.summary_valid_label)
        summary_layout.addWidget(self.summary_warning_label)
        summary_layout.addWidget(self.summary_error_label)
        summary_layout.addWidget(QLabel("|"))
        summary_layout.addWidget(self.summary_stats_label)
        summary_layout.addStretch()

        results_layout.addWidget(self.summary_frame)
        self.summary_frame.setVisible(False)  # Hidden until calculations are done

        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(["Method", "K (cm/s)", "K (m/s)", "K (m/d)", "Formula", "Status"])

        # Enable sorting
        self.results_table.setSortingEnabled(True)

        # Set header properties
        header = self.results_table.horizontalHeader()
        if header:
            header.setStretchLastSection(True)

        # Improve table appearance
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)  # Hide row numbers
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                font-size: 10pt;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                padding: 6px;
                border: 1px solid #c0c0c0;
                font-weight: bold;
                font-size: 10pt;
            }
        """)
        
        results_layout.addWidget(self.results_table)

        # Connect row selection to details panel
        self.results_table.itemSelectionChanged.connect(self.on_result_row_selected)

        # Method details panel (collapsible)
        self.details_group = QGroupBox("Method Details")
        self.details_group.setCheckable(True)
        self.details_group.setChecked(False)  # Start collapsed
        self.details_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #c0c0c0;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 5px;
                background-color: #e8e8e8;
            }
        """)
        details_layout = QVBoxLayout(self.details_group)

        self.details_browser = QTextBrowser()
        # Remove fixed height to allow splitter to resize
        self.details_browser.setMinimumHeight(150)  # Set minimum but allow expansion
        self.details_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #fafafa;
                border: 1px solid #d0d0d0;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
            }
        """)
        self.details_browser.setHtml("<p style='color: #999; text-align: center;'>Select a row in the table above to view detailed calculation information</p>")

        details_layout.addWidget(self.details_browser)

        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(results_group)
        splitter.addWidget(self.details_group)
        # Set initial ratio: 60% for results, 40% for details
        splitter.setStretchFactor(0, 60)
        splitter.setStretchFactor(1, 40)
        splitter.setCollapsible(0, False)  # Don't allow results to be collapsed
        splitter.setCollapsible(1, True)   # Allow details to be collapsed

        layout.addWidget(splitter)

        # Control buttons
        button_layout = QHBoxLayout()

        self.recalculate_btn = QPushButton("Recalculate")
        self.recalculate_btn.setToolTip("Recalculate K-values for all methods")
        self.recalculate_btn.clicked.connect(self.calculate_k_values)
        self.recalculate_btn.setMinimumWidth(120)

        self.export_btn = QPushButton("Export Results")
        self.export_btn.setToolTip("Export calculation results to CSV/Excel")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setMinimumWidth(120)

        button_layout.addWidget(self.recalculate_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        # Remove addStretch() to allow splitter to expand and use all available space

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
        # Temporarily disable sorting while populating
        self.results_table.setSortingEnabled(False)

        self.results_table.setRowCount(len(self.current_results))

        for row, result in enumerate(self.current_results):
            # Method name
            method_item = QTableWidgetItem(result.method_name)
            self.results_table.setItem(row, 0, method_item)

            # K values in different units
            if result.k_value is not None and result.k_value > 0:
                k_m_s = result.k_value

                # Convert to different units
                k_cm_s = k_m_s * 100.0  # m/s to cm/s
                k_m_d = k_m_s * 86400.0  # m/s to m/d

                # K (cm/s) column - right aligned with numeric sorting
                cm_s_item = QTableWidgetItem(f"{k_cm_s:.3e}")
                cm_s_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                cm_s_item.setData(Qt.ItemDataRole.UserRole, k_cm_s)  # Store actual number for sorting
                self.results_table.setItem(row, 1, cm_s_item)

                # K (m/s) column - right aligned with numeric sorting
                m_s_item = QTableWidgetItem(f"{k_m_s:.2e}")
                m_s_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                m_s_item.setData(Qt.ItemDataRole.UserRole, k_m_s)  # Store actual number for sorting
                self.results_table.setItem(row, 2, m_s_item)

                # K (m/d) column - right aligned with numeric sorting
                m_d_item = QTableWidgetItem(f"{k_m_d:.1f}")
                m_d_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                m_d_item.setData(Qt.ItemDataRole.UserRole, k_m_d)  # Store actual number for sorting
                self.results_table.setItem(row, 3, m_d_item)
            else:
                # N/A for all unit columns
                for col in [1, 2, 3]:
                    na_item = QTableWidgetItem("N/A")
                    na_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                    na_item.setData(Qt.ItemDataRole.UserRole, -1)  # Sort N/A values to bottom
                    self.results_table.setItem(row, col, na_item)

            # Formula (column 4)
            self.results_table.setItem(row, 4, QTableWidgetItem(result.formula_used))

            # Status with color coding and icons (column 5)
            status = result.status.value if hasattr(result.status, 'value') else str(result.status)

            # Add icon based on status
            if "OK" in status:
                status_icon = "✓"
                status_color = QColor(220, 255, 220)  # Light green
                text_color = QColor(0, 100, 0)  # Dark green
            elif "Warning" in status:
                status_icon = "⚠"
                status_color = QColor(255, 250, 205)  # Light yellow
                text_color = QColor(150, 100, 0)  # Dark orange
            elif "Error" in status:
                status_icon = "✗"
                status_color = QColor(255, 220, 220)  # Light red
                text_color = QColor(150, 0, 0)  # Dark red
            else:
                status_icon = "?"
                status_color = QColor(240, 240, 240)  # Gray
                text_color = QColor(100, 100, 100)

            status_text = f"{status_icon} {status}"
            status_item = QTableWidgetItem(status_text)
            status_item.setBackground(status_color)
            status_item.setForeground(text_color)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

            if result.status_message:
                status_item.setToolTip(result.status_message)

            self.results_table.setItem(row, 5, status_item)

        # Resize columns and re-enable sorting
        self.results_table.resizeColumnsToContents()
        self.results_table.setSortingEnabled(True)

        # Update summary statistics bar
        self.update_summary_bar()

    def update_summary_bar(self):
        """Update the summary statistics bar with calculation overview"""
        if not self.current_results:
            self.summary_frame.setVisible(False)
            return

        self.summary_frame.setVisible(True)

        # Count results by status
        total = len(self.current_results)
        ok_count = sum(1 for r in self.current_results if "OK" in (r.status.value if hasattr(r.status, 'value') else str(r.status)))
        warning_count = sum(1 for r in self.current_results if "Warning" in (r.status.value if hasattr(r.status, 'value') else str(r.status)))
        error_count = sum(1 for r in self.current_results if "Error" in (r.status.value if hasattr(r.status, 'value') else str(r.status)))

        # Get valid K values for statistics
        valid_results = [r for r in self.current_results if r.k_value is not None and r.k_value > 0]

        # Update labels
        self.summary_total_label.setText(f"{total} methods calculated")

        if ok_count > 0:
            self.summary_valid_label.setText(f"✓ {ok_count} valid")
        else:
            self.summary_valid_label.setText("")

        if warning_count > 0:
            self.summary_warning_label.setText(f"⚠ {warning_count} warnings")
        else:
            self.summary_warning_label.setText("")

        if error_count > 0:
            self.summary_error_label.setText(f"✗ {error_count} errors")
        else:
            self.summary_error_label.setText("")

        # Calculate and display mean K-value and range
        if valid_results:
            k_values = [r.k_value for r in valid_results]
            mean_k = np.mean(k_values)
            min_k = np.min(k_values)
            max_k = np.max(k_values)

            self.summary_stats_label.setText(
                f"Mean: {mean_k:.2e} m/s  |  Range: {min_k:.2e} - {max_k:.2e} m/s"
            )
        else:
            self.summary_stats_label.setText("No valid K-values calculated")

    def on_result_row_selected(self):
        """Handle row selection in results table - show method details"""
        selected_rows = self.results_table.selectedItems()
        if not selected_rows or not self.current_results:
            return

        # Get the row number (all selected items will have same row)
        row = selected_rows[0].row()

        # Get the method name from the table (column 0) to handle sorted tables correctly
        method_item = self.results_table.item(row, 0)
        if not method_item:
            return

        method_name = method_item.text()

        # Find the matching result by method name
        result = None
        for r in self.current_results:
            if r.method_name == method_name:
                result = r
                break

        if not result:
            return

        # Generate detailed HTML
        html = self.generate_method_details_html(result)

        # Update details panel
        self.details_browser.setHtml(html)

        # Auto-expand details panel
        if not self.details_group.isChecked():
            self.details_group.setChecked(True)

    def generate_method_details_html(self, result) -> str:
        """Generate detailed HTML for a calculation result with horizontal layout"""
        # Status color
        status = result.status.value if hasattr(result.status, 'value') else str(result.status)
        if "OK" in status:
            status_color = "#006400"
            status_bg = "#d4edda"
            status_icon = "✓"
        elif "Warning" in status:
            status_color = "#856404"
            status_bg = "#fff3cd"
            status_icon = "⚠"
        else:
            status_color = "#721c24"
            status_bg = "#f8d7da"
            status_icon = "✗"

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 8px; font-size: 10pt; }}
                table {{ border-collapse: collapse; width: 100%; }}
                .header-table {{ width: 100%; background-color: #4a5f7f; color: white; margin-bottom: 8px; }}
                .method-name {{ font-size: 13pt; font-weight: bold; padding: 8px; }}
                .status-badge {{ background-color: {status_bg}; color: {status_color}; padding: 4px 10px;
                               font-weight: bold; font-size: 9pt; border-radius: 3px; }}
                .section-title {{ font-weight: bold; color: #495057; font-size: 10pt;
                                 background-color: #e9ecef; padding: 5px 8px; margin-top: 8px; }}
                .k-value-large {{ font-size: 14pt; font-weight: bold; color: #0066cc; padding: 8px; }}
                .formula-text {{ font-family: 'Courier New', monospace; font-size: 9pt;
                               background-color: #f0f8ff; padding: 8px; border-left: 3px solid #0066cc; }}
                .param-table {{ width: 100%; font-size: 9pt; margin-top: 5px; }}
                .param-label {{ font-weight: 600; color: #6c757d; padding: 3px 8px; width: 20%; }}
                .param-value {{ font-family: 'Consolas', monospace; padding: 3px 8px; background-color: #f8f9fa; }}
                .param-value-warn {{ color: #dc3545; font-weight: bold; background-color: #ffe6e6; }}
                .alert-box {{ background-color: {status_bg}; border-left: 4px solid {status_color};
                            padding: 8px; margin: 8px 0; color: {status_color}; font-weight: 500; }}
                .check-ok {{ color: #28a745; font-weight: bold; }}
                .check-fail {{ color: #dc3545; font-weight: bold; }}
            </style>
        </head>
        <body>
        """

        # Header with method name and status
        html += f"""
        <table class="header-table">
            <tr>
                <td class="method-name">{result.method_name}</td>
                <td align="right" style="padding: 8px;">
                    <span class="status-badge">{status_icon} {status}</span>
                </td>
            </tr>
        </table>
        """

        # Status message alert if present
        if result.status_message:
            html += f"""
            <div class="alert-box">
                <strong>{status_icon} Issue:</strong> {result.status_message}
            </div>
            """

        # K-Value and Formula side-by-side
        html += '<table style="margin-top: 8px;"><tr>'

        # Left column: K-Value
        html += '<td style="width: 50%; vertical-align: top; padding-right: 8px;">'
        html += '<div class="section-title">Calculated K-Value</div>'
        if result.k_value is not None and result.k_value > 0:
            k_cm_s = result.k_value * 100.0
            k_m_d = result.k_value * 86400.0
            html += f"""
            <div class="k-value-large">{result.k_value:.2e} m/s</div>
            <div style="padding: 4px 8px; font-size: 9pt; color: #666;">
                <strong>cm/s:</strong> {k_cm_s:.3e}<br>
                <strong>m/d:</strong> {k_m_d:.1f}
            </div>
            """
        else:
            html += '<div style="color: #dc3545; font-weight: bold; padding: 8px;">No valid K-value</div>'
        html += '</td>'

        # Right column: Formula
        html += '<td style="width: 50%; vertical-align: top; padding-left: 8px;">'
        html += '<div class="section-title">Formula Used</div>'
        html += f'<div class="formula-text">{result.formula_used}</div>'
        html += '</td></tr></table>'

        # Input Parameters section
        d10 = self.dataset.get_d10()
        d30 = self.dataset.get_d30()
        d60 = self.dataset.get_d60()
        d50 = self.dataset.get_d50()

        html += '<div class="section-title" style="margin-top: 10px;">Input Parameters</div>'
        html += '<table class="param-table">'

        # Build parameter list
        params = []
        if d10:
            params.append(("D₁₀", f"{d10:.3f} mm", False))
        if d30:
            params.append(("D₃₀", f"{d30:.3f} mm", False))
        if d50:
            params.append(("D₅₀", f"{d50:.3f} mm", False))
        if d60:
            params.append(("D₆₀", f"{d60:.3f} mm", False))

        # Cu and Cc
        if d10 and d60:
            cu = d60 / d10
            params.append(("Cu", f"{cu:.2f}", False))
            if d30:
                cc = (d30 * d30) / (d10 * d60)
                params.append(("Cc", f"{cc:.2f}", False))

        params.append(("Temperature", f"{self.temperature}°C", False))
        params.append(("Porosity", f"{self.porosity:.4f}", False))

        # Render parameters in 4-column table (2 label-value pairs per row)
        for i in range(0, len(params), 2):
            html += '<tr>'

            # First parameter
            label1, value1, warn1 = params[i]
            value_class1 = "param-value param-value-warn" if warn1 else "param-value"
            html += f'<td class="param-label">{label1}:</td>'
            html += f'<td class="{value_class1}">{value1}</td>'

            # Second parameter (if exists)
            if i + 1 < len(params):
                label2, value2, warn2 = params[i + 1]
                value_class2 = "param-value param-value-warn" if warn2 else "param-value"
                html += f'<td class="param-label">{label2}:</td>'
                html += f'<td class="{value_class2}">{value2}</td>'
            else:
                html += '<td></td><td></td>'

            html += '</tr>'

        html += '</table>'

        # Applicability check
        conditions_met = result.conditions_met if hasattr(result, 'conditions_met') else True
        check_symbol = '<span class="check-ok">✓ Conditions Met</span>' if conditions_met else '<span class="check-fail">✗ Conditions NOT Met</span>'

        html += f"""
        <div class="section-title" style="margin-top: 10px;">Applicability</div>
        <div style="padding: 8px;">{check_symbol}</div>
        """

        html += "</body></html>"
        return html

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