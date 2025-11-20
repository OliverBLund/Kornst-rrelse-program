"""
Dataset tab containing plot workspace, results, and statistics for a single dataset
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QGroupBox,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QHeaderView,
    QLabel,
    QFrame,
    QTextBrowser,
    QSplitter,
    QLineEdit,
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

        # Results group box
        results_group = QGroupBox(
            f"Hydraulic Conductivity Results - {self.dataset.sample_name}"
        )
        results_layout = QVBoxLayout(results_group)

        # Summary statistics bar (top)
        self.summary_frame = QFrame()
        self.summary_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Plain)
        self.summary_frame.setFixedHeight(70)
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
        summary_layout.setSpacing(8)

        # Summary labels
        self.summary_total_label = QLabel("No calculations yet")
        self.summary_total_label.setStyleSheet(
            "font-weight: bold; color: #333; font-size: 10pt;"
        )

        self.summary_valid_label = QLabel("")
        self.summary_valid_label.setStyleSheet("color: #006400; font-size: 10pt;")

        self.summary_warning_label = QLabel("")
        self.summary_warning_label.setStyleSheet("color: #8B6914; font-size: 10pt;")

        self.summary_error_label = QLabel("")
        self.summary_error_label.setStyleSheet("color: #8B0000; font-size: 10pt;")

        self.summary_stats_label = QLabel("")
        self.summary_stats_label.setStyleSheet("color: #333; font-size: 10pt;")

        for label in [
            self.summary_total_label,
            self.summary_valid_label,
            self.summary_warning_label,
            self.summary_error_label,
            self.summary_stats_label,
        ]:
            label.setWordWrap(False)
            label.setMaximumHeight(25)

        separator1 = QLabel("|")
        separator1.setStyleSheet("color: #999; font-size: 10pt;")
        separator1.setMaximumHeight(25)

        separator2 = QLabel("|")
        separator2.setStyleSheet("color: #999; font-size: 10pt;")
        separator2.setMaximumHeight(25)

        summary_layout.addWidget(self.summary_total_label)
        summary_layout.addWidget(separator1)
        summary_layout.addWidget(self.summary_valid_label)
        summary_layout.addWidget(self.summary_warning_label)
        summary_layout.addWidget(self.summary_error_label)
        summary_layout.addWidget(separator2)
        summary_layout.addWidget(self.summary_stats_label)
        summary_layout.addStretch()

        results_layout.addWidget(self.summary_frame)
        self.summary_frame.setVisible(False)

        # Middle row: K-values table (left) and Method Details (right)
        middle_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Results table
        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["Method", "K (cm/s)", "K (m/s)", "K (m/d)", "Status"]
        )
        self.results_table.setSortingEnabled(True)

        header = self.results_table.horizontalHeader()
        if header:
            header.setStretchLastSection(True)

        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
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
        self.results_table.itemSelectionChanged.connect(self.on_result_row_selected)

        # Right: Method details panel
        self.details_group = QGroupBox("Method Details")
        self.details_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #c0c0c0;
                border-radius: 5px;
                margin-top: 8px;
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
        self.details_browser.setMinimumHeight(200)
        self.details_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #fafafa;
                border: 1px solid #d0d0d0;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
            }
        """)
        self.details_browser.setHtml(
            "<p style='color: #999; text-align: center;'>Select a row in the table above to view detailed calculation information</p>"
        )

        details_layout.addWidget(self.details_browser)

        middle_splitter.addWidget(self.results_table)
        middle_splitter.addWidget(self.details_group)
        middle_splitter.setStretchFactor(0, 50)  # 50% for table
        middle_splitter.setStretchFactor(1, 50)  # 50% for method details

        results_layout.addWidget(
            middle_splitter, 1
        )  # Stretch factor 1 to take available space

        layout.addWidget(results_group)

        # Buttons removed - calculations are automatic, export is done via Export tab

        return widget



    # NOTE: Grain analysis panels (percentiles, gradation, special diameters, environmental params)
    # have been moved to the Statistics Tab for better organization.
    # See statistics_tab.py for these components.

    def create_statistics_tab(self):
        """Create the enhanced statistics tab"""
        from .statistics_tab import StatisticsTab

        # Create new modular statistics tab
        self.statistics_tab = StatisticsTab(self.dataset, parent=self)

        return self.statistics_tab

    def load_dataset_data(self):
        """Load and display the dataset data"""
        # Update plot
        self.plot_workspace.update_plot(
            self.dataset.particle_sizes,
            self.dataset.percent_passing,
            self.dataset.sample_name,
        )

        # Update statistics tab with data
        if hasattr(self, "statistics_tab"):
            self.statistics_tab.update_display()

    # Note: update_grain_statistics() is now handled by StatisticsTab
    # This method is kept for backward compatibility but delegates to the new tab
    def update_grain_statistics(self):
        """Update the grain size statistics display"""
        if hasattr(self, "statistics_tab"):
            self.statistics_tab.update_display()

    def set_parameters(self, temperature: float):
        """Update calculation parameters"""
        self.temperature = temperature
        self.dataset.temperature = temperature
        # Update statistics tab
        if hasattr(self, "statistics_tab"):
            self.statistics_tab.temperature = temperature
            self.statistics_tab.update_display()

    def set_porosity(self, porosity: float):
        """Update porosity parameter (called from statistics tab)"""
        self.porosity = porosity
        self.dataset.current_porosity = porosity
        # Recalculate K-values if we have methods selected
        if self.current_results:
            self.calculate_k_values()

    def calculate_k_values(self, selected_methods: Optional[List[str]] = None):
        """Calculate K values for this dataset"""
        if selected_methods is None:
            # Get all available methods from calculator
            selected_methods = self.k_calculator.get_all_method_names()

        # Prepare grain data
        grain_data = {}
        for key, value in {
            "D10": self.dataset.get_d10(),
            "D20": self.dataset.get_d20(),
            "D30": self.dataset.get_d30(),
            "D50": self.dataset.get_d50(),
            "D60": self.dataset.get_d60(),
        }.items():
            if value is not None:
                grain_data[key] = value

        # Provide full grain size distribution for methods that need fraction data
        grain_data["particle_sizes"] = list(self.dataset.particle_sizes)
        grain_data["percent_passing"] = list(self.dataset.percent_passing)

        # Calculate K values
        self.current_results = self.k_calculator.calculate_all_methods(
            grain_data,
            temperature=self.temperature,
            porosity=self.porosity,
            selected_methods=selected_methods,
        )

        # Update results table
        self.update_results_table()

        # Update statistics tab with K-results (now includes grain analysis panels)
        if hasattr(self, "statistics_tab"):
            self.statistics_tab.set_k_results(self.current_results)

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
                cm_s_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                cm_s_item.setData(
                    Qt.ItemDataRole.UserRole, k_cm_s
                )  # Store actual number for sorting
                self.results_table.setItem(row, 1, cm_s_item)

                # K (m/s) column - right aligned with numeric sorting
                m_s_item = QTableWidgetItem(f"{k_m_s:.2e}")
                m_s_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                m_s_item.setData(
                    Qt.ItemDataRole.UserRole, k_m_s
                )  # Store actual number for sorting
                self.results_table.setItem(row, 2, m_s_item)

                # K (m/d) column - right aligned with numeric sorting
                m_d_item = QTableWidgetItem(f"{k_m_d:.1f}")
                m_d_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                m_d_item.setData(
                    Qt.ItemDataRole.UserRole, k_m_d
                )  # Store actual number for sorting
                self.results_table.setItem(row, 3, m_d_item)
            else:
                # N/A for all unit columns
                for col in [1, 2, 3]:
                    na_item = QTableWidgetItem("N/A")
                    na_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                    na_item.setData(
                        Qt.ItemDataRole.UserRole, -1
                    )  # Sort N/A values to bottom
                    self.results_table.setItem(row, col, na_item)

            # Status with color coding and icons (column 4 - Formula column removed)
            status = (
                result.status.value
                if hasattr(result.status, "value")
                else str(result.status)
            )

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
            status_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )

            if result.status_message:
                status_item.setToolTip(result.status_message)

            self.results_table.setItem(row, 4, status_item)

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
        ok_count = sum(
            1
            for r in self.current_results
            if "OK" in (r.status.value if hasattr(r.status, "value") else str(r.status))
        )
        warning_count = sum(
            1
            for r in self.current_results
            if "Warning"
            in (r.status.value if hasattr(r.status, "value") else str(r.status))
        )
        error_count = sum(
            1
            for r in self.current_results
            if "Error"
            in (r.status.value if hasattr(r.status, "value") else str(r.status))
        )

        # Get valid K values for statistics
        valid_results = [
            r for r in self.current_results if r.k_value is not None and r.k_value > 0
        ]

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

    def get_method_specific_values(self, method_name: str) -> dict:
        """Get method-specific calculated values for display"""
        from k_calculations import KCalculator

        calculator = KCalculator()
        grain_data = {
            "particle_sizes": list(self.dataset.particle_sizes),
            "percent_passing": list(self.dataset.percent_passing),
        }

        values = {}

        # Methods with special diameter calculations
        if method_name == "Kruger":
            de_cm = calculator._kruger_diameter_cm(grain_data)
            if de_cm:
                values["Kruger Effective Diameter (dₑ)"] = (
                    f"{de_cm:.4f} cm ({de_cm * 10:.4f} mm)"
                )

        elif method_name == "Kozeny-Carman":
            de_cm = calculator._harmonic_mean_diameter_cm(grain_data)
            if de_cm:
                values["Harmonic Mean Diameter (dₑ)"] = (
                    f"{de_cm:.4f} cm ({de_cm * 10:.4f} mm)"
                )

        elif method_name == "Zunker":
            de_cm = calculator._zunker_diameter_cm(grain_data)
            if de_cm:
                values["Zunker Effective Diameter (dₑ)"] = (
                    f"{de_cm:.4f} cm ({de_cm * 10:.4f} mm)"
                )

        elif method_name == "Zamarin":
            de_cm = calculator._zamarin_diameter_cm(grain_data)
            if de_cm:
                values["Zamarin Effective Diameter (dₑ)"] = (
                    f"{de_cm:.4f} cm ({de_cm * 10:.4f} mm)"
                )

        elif method_name == "Krumbein-Monk":
            d_geom = calculator._calculate_geometric_mean(grain_data)
            if d_geom:
                values["Geometric Mean Diameter (dgeom)"] = f"{d_geom:.4f} mm"
            # Also calculate sorting coefficient (sigma_phi)
            d16 = calculator._interpolate_percentile(grain_data, 16)
            d84 = calculator._interpolate_percentile(grain_data, 84)
            if d16 and d84 and d16 > 0 and d84 > 0:
                import math

                sigma_phi = math.sqrt(d84 / d16)
                values["Sorting Coefficient (σφ)"] = f"{sigma_phi:.4f}"

        # Methods using specific percentiles
        elif method_name in ["Hazen", "Hazen_1892", "Slichter", "Terzaghi", "Chapuis"]:
            d10 = calculator._interpolate_percentile(grain_data, 10)
            if d10:
                values["D₁₀ (Primary)"] = f"{d10:.4f} mm"

        elif method_name == "USBR":
            d20 = calculator._interpolate_percentile(grain_data, 20)
            if d20:
                values["D₂₀ (Primary)"] = f"{d20:.4f} mm"

        elif method_name == "Shepherd":
            d50 = calculator._interpolate_percentile(grain_data, 50)
            if d50:
                values["D₅₀ (Primary)"] = f"{d50:.4f} mm"

        elif method_name == "Sauerbrei":
            d17 = calculator._interpolate_percentile(grain_data, 17)
            if d17:
                values["D₁₇ (Primary)"] = f"{d17:.4f} mm"

        elif method_name == "Alyamani-Sen":
            d10 = calculator._interpolate_percentile(grain_data, 10)
            d50 = calculator._interpolate_percentile(grain_data, 50)
            if d10:
                values["D₁₀"] = f"{d10:.4f} mm"
            if d50:
                values["D₅₀"] = f"{d50:.4f} mm"
            if d10 and d50:
                intercept = 1355.3 * (d50**2) + 1.1892 * (d10**2)
                values["Intercept (I₀)"] = f"{intercept:.2f}"

        elif method_name == "Beyer":
            d10 = calculator._interpolate_percentile(grain_data, 10)
            d60 = calculator._interpolate_percentile(grain_data, 60)
            if d10 and d60:
                cu = d60 / d10
                values["D₁₀"] = f"{d10:.4f} mm"
                values["D₆₀"] = f"{d60:.4f} mm"
                values["Cu (for log₁₀ factor)"] = f"{cu:.2f}"

        elif method_name == "Barr":
            d5 = calculator._interpolate_percentile(grain_data, 5)
            d10 = calculator._interpolate_percentile(grain_data, 10)
            d60 = calculator._interpolate_percentile(grain_data, 60)
            if d5:
                values["D₅"] = f"{d5:.4f} mm"
            if d10:
                values["D₁₀"] = f"{d10:.4f} mm"
            if d60:
                values["D₆₀"] = f"{d60:.4f} mm"

        return values

    def generate_method_details_html(self, result) -> str:
        """Generate detailed HTML for a calculation result with improved formatting"""
        # Status color
        status = (
            result.status.value
            if hasattr(result.status, "value")
            else str(result.status)
        )
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
                body {{
                    font-family: 'Segoe UI', Arial, sans-serif;
                    margin: 10px;
                    font-size: 11pt;
                    background-color: #ffffff;
                }}
                table {{ border-collapse: collapse; width: 100%; }}

                .section-title {{
                    font-weight: bold;
                    color: #2c5282;
                    font-size: 12pt;
                    background-color: #e8f0f8;
                    padding: 8px 10px;
                    margin-top: 8px;
                    margin-bottom: 6px;
                    border-left: 4px solid #4a7fb8;
                }}

                .k-value-large {{
                    font-size: 18pt;
                    font-weight: bold;
                    color: #0066cc;
                    padding: 12px;
                    background-color: #f0f8ff;
                    border-radius: 4px;
                    margin-bottom: 6px;
                }}

                .formula-text {{
                    font-family: 'Courier New', 'Consolas', monospace;
                    font-size: 15pt;
                    background-color: #f8f9fa;
                    padding: 14px 16px;
                    border-left: 4px solid #0066cc;
                    border-radius: 4px;
                    color: #1a1a1a;
                    line-height: 1.7;
                    letter-spacing: 0.3px;
                }}

                .param-table {{
                    width: 100%;
                    font-size: 10pt;
                    margin-top: 6px;
                    border-spacing: 0;
                }}

                .param-label {{
                    font-weight: 600;
                    color: #495057;
                    padding: 6px 10px;
                    width: 25%;
                    background-color: #f8f9fa;
                }}

                .param-value {{
                    font-family: 'Consolas', monospace;
                    padding: 6px 10px;
                    background-color: #ffffff;
                    color: #212529;
                    border-bottom: 1px solid #e9ecef;
                }}

                .param-value-warn {{
                    color: #dc3545;
                    font-weight: bold;
                    background-color: #ffe6e6;
                }}

                .alert-box {{
                    background-color: {status_bg};
                    border-left: 4px solid {status_color};
                    padding: 10px;
                    margin: 10px 0;
                    color: {status_color};
                    font-weight: 500;
                    border-radius: 4px;
                    font-size: 10pt;
                }}

                .check-ok {{
                    color: #28a745;
                    font-weight: bold;
                    font-size: 11pt;
                }}

                .check-fail {{
                    color: #dc3545;
                    font-weight: bold;
                    font-size: 11pt;
                }}
            </style>
        </head>
        <body>
        """

        # Status message alert if present (show at top)
        if result.status_message:
            html += f"""
            <div class="alert-box">
                <strong>{status_icon} Note:</strong> {result.status_message}
            </div>
            """

        # K-Value section (full width)
        html += '<div class="section-title">Calculated K-Value</div>'
        if result.k_value is not None and result.k_value > 0:
            k_cm_s = result.k_value * 100.0
            k_m_d = result.k_value * 86400.0
            html += f"""
            <div class="k-value-large">{result.k_value:.3e} m/s</div>
            <div style="padding: 8px 12px; font-size: 10pt; color: #555; background-color: #f8f9fa;
                        border-radius: 4px; margin-bottom: 8px;">
                <strong>cm/s:</strong> {k_cm_s:.3e} &nbsp;&nbsp;|&nbsp;&nbsp; <strong>m/d:</strong> {k_m_d:.2f}
            </div>
            """
        else:
            html += '<div style="color: #dc3545; font-weight: bold; padding: 12px; margin-bottom: 8px;">No valid K-value</div>'

        # Formula section (full width, on its own row)
        html += '<div class="section-title">Formula Used</div>'
        html += f'<div class="formula-text">{result.formula_used}</div>'

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
            html += "<tr>"

            # First parameter
            label1, value1, warn1 = params[i]
            value_class1 = "param-value param-value-warn" if warn1 else "param-value"
            html += f'<td class="param-label">{label1}:</td>'
            html += f'<td class="{value_class1}">{value1}</td>'

            # Second parameter (if exists)
            if i + 1 < len(params):
                label2, value2, warn2 = params[i + 1]
                value_class2 = (
                    "param-value param-value-warn" if warn2 else "param-value"
                )
                html += f'<td class="param-label">{label2}:</td>'
                html += f'<td class="{value_class2}">{value2}</td>'
            else:
                html += "<td></td><td></td>"

            html += "</tr>"

        html += "</table>"

        # Method-Specific Values section
        method_values = self.get_method_specific_values(result.method_name)
        if method_values:
            html += '<div class="section-title" style="margin-top: 10px;">Method-Specific Values</div>'
            html += '<table class="param-table">'

            # Convert dict to list of tuples for 2-column layout
            values_list = list(method_values.items())
            for i in range(0, len(values_list), 2):
                html += "<tr>"

                # First value
                label1, value1 = values_list[i]
                html += f'<td class="param-label">{label1}:</td>'
                html += f'<td class="param-value" style="color: #0066cc; font-weight: 600;">{value1}</td>'

                # Second value (if exists)
                if i + 1 < len(values_list):
                    label2, value2 = values_list[i + 1]
                    html += f'<td class="param-label">{label2}:</td>'
                    html += f'<td class="param-value" style="color: #0066cc; font-weight: 600;">{value2}</td>'
                else:
                    html += "<td></td><td></td>"

                html += "</tr>"

            html += "</table>"

        # Applicability check
        conditions_met = (
            result.conditions_met if hasattr(result, "conditions_met") else True
        )
        check_symbol = (
            '<span class="check-ok">✓ Conditions Met</span>'
            if conditions_met
            else '<span class="check-fail">✗ Conditions NOT Met</span>'
        )

        html += f"""
        <div class="section-title" style="margin-top: 10px;">Applicability</div>
        <div style="padding: 8px;">{check_symbol}</div>
        """

        html += "</body></html>"
        return html

    # Note: update_k_statistics() is now handled by StatisticsTab
    # This method is kept for backward compatibility but delegates to the new tab
    def update_k_statistics(self):
        """Update K-value statistics"""
        if hasattr(self, "statistics_tab"):
            self.statistics_tab.set_k_results(self.current_results)

    def export_results(self):
        """Export results to file"""
        # TODO: Implement export functionality
        QMessageBox.information(
            self,
            "Export",
            f"Export functionality for {self.dataset.sample_name} will be implemented",
        )

    def get_dataset_name(self) -> str:
        """Get the dataset name"""
        return self.dataset.sample_name

    def get_dataset(self) -> GrainSizeData:
        """Get the dataset object"""
        return self.dataset

    def get_results(self) -> List[KCalculationResult]:
        """Get the current K-calculation results"""
        return self.current_results

    # Note: Porosity management methods are now in StatisticsTab
    # These have been removed to avoid duplication
