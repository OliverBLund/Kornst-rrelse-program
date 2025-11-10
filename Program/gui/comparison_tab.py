"""
Comparison tab for comparing multiple datasets
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QCheckBox, QPushButton, QLabel,
    QGroupBox, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QColor
from typing import List, Dict, Optional
import numpy as np

from data_loader import GrainSizeData
from k_calculations import KCalculationResult
from .comparison_plot_widget import ComparisonPlotWidget
from .dataset_selection_dialog import DatasetSelectionDialog


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

        # Container for selection UI (either checkboxes or dialog button)
        self.selection_container = QHBoxLayout()
        control_layout.addLayout(self.selection_container)

        # Dataset checkboxes layout (for ≤5 datasets)
        self.dataset_checks_layout = QHBoxLayout()

        # Dialog button (for >5 datasets)
        self.dataset_dialog_btn = QPushButton("📋 Select Datasets...")
        self.dataset_dialog_btn.clicked.connect(self.open_dataset_selection_dialog)
        self.dataset_dialog_btn.setToolTip("Open dialog to select from multiple datasets")

        # Selection summary label (for dialog mode)
        self.selection_summary_label = QLabel("No datasets selected")
        self.selection_summary_label.setStyleSheet("color: #666; font-style: italic; margin-left: 8px;")

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
        """Create the enhanced comparison table tab with multiple sections"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Section A: Dataset Overview
        overview_group = QGroupBox("📋 Dataset Overview")
        overview_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #8b7355;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #5d4e37;
            }
        """)
        overview_layout = QVBoxLayout(overview_group)

        self.overview_table = QTableWidget()
        self.overview_table.setStyleSheet(self._get_table_style())
        overview_layout.addWidget(self.overview_table)
        layout.addWidget(overview_group)

        # Section B: Grain Size Parameters
        grain_group = QGroupBox("🔬 Grain Size Parameters")
        grain_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #8b7355;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #5d4e37;
            }
        """)
        grain_layout = QVBoxLayout(grain_group)

        self.grain_comparison_table = QTableWidget()
        self.grain_comparison_table.setStyleSheet(self._get_table_style())
        grain_layout.addWidget(self.grain_comparison_table)
        layout.addWidget(grain_group)

        # Section C: K-values comparison table
        k_group = QGroupBox("💧 Hydraulic Conductivity Comparison")
        k_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #8b7355;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #5d4e37;
            }
        """)
        k_layout = QVBoxLayout(k_group)

        self.k_comparison_table = QTableWidget()
        self.k_comparison_table.setStyleSheet(self._get_table_style())
        k_layout.addWidget(self.k_comparison_table)
        layout.addWidget(k_group)

        # Section D: Permeability Classification
        perm_group = QGroupBox("📊 Permeability Classification")
        perm_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #8b7355;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #5d4e37;
            }
        """)
        perm_layout = QVBoxLayout(perm_group)

        self.permeability_table = QTableWidget()
        self.permeability_table.setStyleSheet(self._get_table_style())
        perm_layout.addWidget(self.permeability_table)
        layout.addWidget(perm_group)

        return widget

    def _get_table_style(self):
        """Get consistent table styling"""
        return """
            QTableWidget {
                gridline-color: #d0d0d0;
                font-size: 10pt;
                background-color: white;
                alternate-background-color: #f9f9f9;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                padding: 6px;
                border: 1px solid #c0c0c0;
                font-weight: bold;
                font-size: 10pt;
            }
        """

    def create_statistical_analysis_tab(self):
        """Create the enhanced visual statistical analysis tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Import matplotlib
        import matplotlib
        matplotlib.use('Qt5Agg')
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure

        # Top section: K-Value Distribution Box Plot
        k_dist_group = QGroupBox("💧 K-Value Distribution Analysis")
        k_dist_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #8b7355;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #5d4e37;
            }
        """)
        k_dist_layout = QVBoxLayout(k_dist_group)

        self.k_boxplot_figure = Figure(figsize=(10, 4))
        self.k_boxplot_figure.patch.set_facecolor('#fafaf7')
        self.k_boxplot_canvas = FigureCanvas(self.k_boxplot_figure)
        k_dist_layout.addWidget(self.k_boxplot_canvas)

        layout.addWidget(k_dist_group)

        # Middle section: Method Performance Heatmap
        method_perf_group = QGroupBox("🎯 Method Applicability Matrix")
        method_perf_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #8b7355;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #5d4e37;
            }
        """)
        method_perf_layout = QVBoxLayout(method_perf_group)

        self.method_heatmap_figure = Figure(figsize=(10, 4))
        self.method_heatmap_figure.patch.set_facecolor('#fafaf7')
        self.method_heatmap_canvas = FigureCanvas(self.method_heatmap_figure)
        method_perf_layout.addWidget(self.method_heatmap_canvas)

        layout.addWidget(method_perf_group)

        # Bottom section: Statistical Summary Text
        summary_group = QGroupBox("📊 Statistical Summary")
        summary_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #8b7355;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #5d4e37;
            }
        """)
        summary_layout = QVBoxLayout(summary_group)

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(200)
        self.stats_text.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #d0d0d0;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
            }
        """)

        summary_layout.addWidget(self.stats_text)
        layout.addWidget(summary_group)

        return widget

    def set_dataset_tabs(self, dataset_tabs: List):
        """Set the available dataset tabs"""
        self.dataset_tabs = dataset_tabs
        self.update_dataset_checkboxes()

    def update_dataset_checkboxes(self):
        """Update the dataset selection UI (checkboxes for ≤5 datasets, dialog for >5)"""
        # Clear existing UI elements
        self.clear_selection_container()

        if len(self.dataset_tabs) <= 5:
            # Use checkboxes for small number of datasets
            self.use_checkbox_mode()
        else:
            # Use dialog button for large number of datasets
            self.use_dialog_mode()

    def clear_selection_container(self):
        """Clear all widgets from the selection container"""
        # Clear checkboxes layout
        while self.dataset_checks_layout.count():
            item = self.dataset_checks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Remove all widgets from selection container
        while self.selection_container.count():
            item = self.selection_container.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                # Remove layout but don't delete it as we might reuse it
                pass

    def use_checkbox_mode(self):
        """Set up UI for checkbox mode (≤5 datasets)"""
        self.selection_container.addLayout(self.dataset_checks_layout)

        # Add checkboxes for each dataset
        for tab in self.dataset_tabs:
            checkbox = QCheckBox(tab.get_dataset_name())
            checkbox.setChecked(True)  # Default to all selected
            self.dataset_checks_layout.addWidget(checkbox)

    def use_dialog_mode(self):
        """Set up UI for dialog mode (>5 datasets)"""
        self.selection_container.addWidget(self.dataset_dialog_btn)
        self.selection_container.addWidget(self.selection_summary_label)

        # Initialize with all datasets selected
        self.selected_datasets = self.dataset_tabs.copy()
        self.update_selection_summary()

    def open_dataset_selection_dialog(self):
        """Open the dataset selection dialog for large numbers of datasets"""
        dialog = DatasetSelectionDialog(
            self.dataset_tabs,
            getattr(self, 'selected_datasets', []),
            self
        )

        if dialog.exec():
            self.selected_datasets = dialog.get_selected_tabs()
            self.update_selection_summary()

    def update_selection_summary(self):
        """Update the selection summary label in dialog mode"""
        if not hasattr(self, 'selected_datasets'):
            self.selected_datasets = []

        count = len(self.selected_datasets)
        if count == 0:
            self.selection_summary_label.setText("No datasets selected")
            self.selection_summary_label.setStyleSheet("color: #d32f2f; font-style: italic; margin-left: 8px;")
        elif count == 1:
            self.selection_summary_label.setText("1 dataset selected (need ≥2)")
            self.selection_summary_label.setStyleSheet("color: #ff9800; font-style: italic; margin-left: 8px;")
        else:
            self.selection_summary_label.setText(f"{count} datasets selected")
            self.selection_summary_label.setStyleSheet("color: #4caf50; font-style: italic; margin-left: 8px;")

    def get_selected_datasets(self) -> List:
        """Get the currently selected datasets"""
        if len(self.dataset_tabs) <= 5:
            # Checkbox mode
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
        else:
            # Dialog mode
            return getattr(self, 'selected_datasets', [])

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
            # Clear plot if no datasets selected
            self.comparison_plot_widget.datasets = []
            self.comparison_plot_widget.show_empty_state("Select datasets and click 'Update Comparison'")
            return

        # Update the comparison plot widget with selected datasets
        self.comparison_plot_widget.set_datasets(self.selected_datasets)
        self.comparison_plot_widget.refresh_plot()

    def update_comparison_tables(self):
        """Update all comparison tables with color-coding"""
        if not self.selected_datasets:
            # Clear all tables if no datasets selected
            self.overview_table.setRowCount(0)
            self.overview_table.setColumnCount(0)
            self.grain_comparison_table.setRowCount(0)
            self.grain_comparison_table.setColumnCount(0)
            self.k_comparison_table.setRowCount(0)
            self.k_comparison_table.setColumnCount(0)
            self.permeability_table.setRowCount(0)
            self.permeability_table.setColumnCount(0)
            return

        # Update all sections
        self.update_overview_table()
        self.update_grain_parameters_table()
        self.update_k_values_table()
        self.update_permeability_classification_table()

    def update_overview_table(self):
        """Update the dataset overview table"""
        overview_params = ["Soil Classification", "Temperature (°C)", "Porosity", "Data Points"]

        self.overview_table.setRowCount(len(overview_params))
        self.overview_table.setColumnCount(len(self.selected_datasets) + 1)
        self.overview_table.setAlternatingRowColors(True)

        # Set headers
        headers = ["Property"] + [tab.get_dataset_name() for tab in self.selected_datasets]
        self.overview_table.setHorizontalHeaderLabels(headers)

        # Fill data
        for row, param in enumerate(overview_params):
            param_item = QTableWidgetItem(param)
            param_item.setFlags(param_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.overview_table.setItem(row, 0, param_item)

            for col, tab in enumerate(self.selected_datasets, 1):
                dataset = tab.get_dataset()
                value = ""

                if param == "Soil Classification":
                    value = dataset.classify_soil()
                elif param == "Temperature (°C)":
                    value = f"{dataset.temperature:.1f}"
                elif param == "Porosity":
                    porosity = getattr(dataset, 'current_porosity', dataset.porosity)
                    value = f"{porosity:.4f}" if porosity else "N/A"
                elif param == "Data Points":
                    value = str(len(dataset.particle_sizes))

                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.overview_table.setItem(row, col, item)

        self.overview_table.resizeColumnsToContents()

    def update_grain_parameters_table(self):
        """Update grain size parameters table with color-coding"""
        params = ["D10 (mm)", "D20 (mm)", "D30 (mm)", "D50 (mm)", "D60 (mm)",
                 "Uniformity Coefficient (Cu)", "Curvature Coefficient (Cc)", "Gradation"]

        self.grain_comparison_table.setRowCount(len(params))
        self.grain_comparison_table.setColumnCount(len(self.selected_datasets) + 2)  # +2 for parameter and mean
        self.grain_comparison_table.setAlternatingRowColors(True)

        # Set headers
        headers = ["Parameter"] + [tab.get_dataset_name() for tab in self.selected_datasets] + ["Mean/Range"]
        self.grain_comparison_table.setHorizontalHeaderLabels(headers)

        # Fill data
        for row, param in enumerate(params):
            param_item = QTableWidgetItem(param)
            param_item.setFlags(param_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.grain_comparison_table.setItem(row, 0, param_item)

            # Collect values for color-coding
            values_for_row = []

            for col, tab in enumerate(self.selected_datasets, 1):
                dataset = tab.get_dataset()
                value = ""
                numeric_value = None

                if param == "D10 (mm)":
                    d10 = dataset.get_d10()
                    value = f"{d10:.3f}" if d10 else "N/A"
                    numeric_value = d10
                elif param == "D20 (mm)":
                    d20 = dataset.get_d20()
                    value = f"{d20:.3f}" if d20 else "N/A"
                    numeric_value = d20
                elif param == "D30 (mm)":
                    d30 = dataset.get_d30()
                    value = f"{d30:.3f}" if d30 else "N/A"
                    numeric_value = d30
                elif param == "D50 (mm)":
                    d50 = dataset.get_d50()
                    value = f"{d50:.3f}" if d50 else "N/A"
                    numeric_value = d50
                elif param == "D60 (mm)":
                    d60 = dataset.get_d60()
                    value = f"{d60:.3f}" if d60 else "N/A"
                    numeric_value = d60
                elif param == "Uniformity Coefficient (Cu)":
                    d10, d60 = dataset.get_d10(), dataset.get_d60()
                    if d10 and d60 and d10 > 0:
                        cu = d60 / d10
                        value = f"{cu:.2f}"
                        numeric_value = cu
                    else:
                        value = "N/A"
                elif param == "Curvature Coefficient (Cc)":
                    d10, d30, d60 = dataset.get_d10(), dataset.get_d30(), dataset.get_d60()
                    if d10 and d30 and d60 and d10 > 0 and d60 > 0:
                        cc = (d30*d30)/(d10*d60)
                        value = f"{cc:.2f}"
                        numeric_value = cc
                    else:
                        value = "N/A"
                elif param == "Gradation":
                    d10, d60 = dataset.get_d10(), dataset.get_d60()
                    if d10 and d60 and d10 > 0:
                        cu = d60 / d10
                        if cu < 4:
                            value = "Uniform"
                        elif cu < 6:
                            value = "Moderate"
                        else:
                            value = "Well-graded"
                    else:
                        value = "N/A"

                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Store numeric value for color-coding
                if numeric_value is not None:
                    item.setData(Qt.ItemDataRole.UserRole, numeric_value)
                    values_for_row.append((col, numeric_value))

                self.grain_comparison_table.setItem(row, col, item)

            # Apply color-coding for numeric params (not Gradation)
            if param != "Gradation" and len(values_for_row) > 1:
                numeric_vals = [v[1] for v in values_for_row]
                min_val = min(numeric_vals)
                max_val = max(numeric_vals)

                for col, val in values_for_row:
                    item = self.grain_comparison_table.item(row, col)
                    normalized = (val - min_val) / (max_val - min_val) if max_val > min_val else 0.5

                    # For Cu, higher is better (well-graded) - reverse colors
                    if param == "Uniformity Coefficient (Cu)":
                        color = self._interpolate_color(normalized, reverse=True)
                    else:
                        color = self._interpolate_color(normalized)

                    item.setBackground(color)

            # Add statistics column
            if values_for_row:
                numeric_vals = [v[1] for v in values_for_row]
                mean_val = np.mean(numeric_vals)
                std_val = np.std(numeric_vals)
                cv = (std_val / mean_val * 100) if mean_val > 0 else 0

                stats_str = f"μ={mean_val:.2f}\nσ={std_val:.2f}\nCV={cv:.1f}%"
                stats_item = QTableWidgetItem(stats_str)
                stats_item.setFlags(stats_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                stats_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                stats_item.setBackground(QColor(240, 240, 240))
                self.grain_comparison_table.setItem(row, len(self.selected_datasets) + 1, stats_item)

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
        """Update the visual statistical analysis with plots and text"""
        if not self.selected_datasets:
            # Clear plots and show empty message
            self.k_boxplot_figure.clear()
            ax1 = self.k_boxplot_figure.add_subplot(1, 1, 1)
            ax1.text(0.5, 0.5, 'Select datasets and click "Update Comparison"',
                    transform=ax1.transAxes, ha='center', va='center',
                    fontsize=12, color='gray')
            ax1.set_xticks([])
            ax1.set_yticks([])
            self.k_boxplot_canvas.draw()

            self.method_heatmap_figure.clear()
            ax2 = self.method_heatmap_figure.add_subplot(1, 1, 1)
            ax2.text(0.5, 0.5, 'Select datasets and click "Update Comparison"',
                    transform=ax2.transAxes, ha='center', va='center',
                    fontsize=12, color='gray')
            ax2.set_xticks([])
            ax2.set_yticks([])
            self.method_heatmap_canvas.draw()

            self.stats_text.setPlainText("Select datasets and click 'Update Comparison' to view statistical analysis")
            return

        # Update visual plots
        self.plot_k_value_boxplots()
        self.plot_method_applicability_heatmap()

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

    def update_permeability_classification_table(self):
        """Update permeability classification table with color-coding"""
        self.permeability_table.setRowCount(1)
        self.permeability_table.setColumnCount(len(self.selected_datasets) + 1)
        self.permeability_table.setAlternatingRowColors(True)

        headers = ["Dataset"] + [tab.get_dataset_name() for tab in self.selected_datasets]
        self.permeability_table.setHorizontalHeaderLabels(headers)

        # Row: Permeability classification
        label_item = QTableWidgetItem("Classification")
        label_item.setFlags(label_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        font = label_item.font()
        font.setBold(True)
        label_item.setFont(font)
        self.permeability_table.setItem(0, 0, label_item)

        for col, tab in enumerate(self.selected_datasets, 1):
            results = tab.get_results()
            valid_k = [r.k_value for r in results if r.k_value and r.k_value > 0]

            if valid_k:
                mean_k = np.mean(valid_k)

                # Classify permeability
                if mean_k > 1e-2:
                    classification = "Very High\n(Gravel)"
                    color = QColor(76, 175, 80, 100)  # Green
                elif mean_k > 1e-4:
                    classification = "High\n(Clean Sand)"
                    color = QColor(139, 195, 74, 100)  # Light green
                elif mean_k > 1e-5:
                    classification = "Moderate\n(Fine Sand)"
                    color = QColor(255, 235, 59, 100)  # Yellow
                elif mean_k > 1e-7:
                    classification = "Low\n(Silt)"
                    color = QColor(255, 152, 0, 100)  # Orange
                else:
                    classification = "Very Low\n(Clay)"
                    color = QColor(244, 67, 54, 100)  # Red

                item = QTableWidgetItem(f"{classification}\n{mean_k:.2e} m/s")
            else:
                classification = "Not Calculated"
                item = QTableWidgetItem(classification)
                color = QColor(200, 200, 200)

            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setBackground(color)
            self.permeability_table.setItem(0, col, item)

        self.permeability_table.resizeColumnsToContents()
        self.permeability_table.resizeRowsToContents()

    def _interpolate_color(self, normalized_value, reverse=False):
        """
        Interpolate color between green and red based on normalized value (0-1)

        Args:
            normalized_value: Value between 0 and 1
            reverse: If True, green=high, red=low. If False, green=low, red=high
        """
        from PyQt6.QtGui import QColor

        if reverse:
            normalized_value = 1 - normalized_value

        # Green (low) -> Yellow (mid) -> Red (high)
        if normalized_value < 0.5:
            # Green to yellow
            r = int(255 * (normalized_value * 2))
            g = 200
            b = 100
        else:
            # Yellow to red
            r = 255
            g = int(200 * (1 - (normalized_value - 0.5) * 2))
            b = 100

        return QColor(r, g, b, 80)  # 80 = semi-transparent

    def plot_k_value_boxplots(self):
        """Create box plots showing K-value distribution for each dataset"""
        self.k_boxplot_figure.clear()

        if not self.selected_datasets:
            ax = self.k_boxplot_figure.add_subplot(1, 1, 1)
            ax.text(0.5, 0.5, 'No datasets selected', transform=ax.transAxes,
                   ha='center', va='center', fontsize=12, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            self.k_boxplot_canvas.draw()
            return

        # Collect K-values for each dataset
        data_for_boxplot = []
        labels = []
        colors = []

        for i, tab in enumerate(self.selected_datasets):
            results = tab.get_results()
            valid_k = [r.k_value for r in results if r.k_value and r.k_value > 0]

            if valid_k:
                data_for_boxplot.append(valid_k)
                labels.append(tab.get_dataset_name())
                # Use color from dataset colors
                color_idx = i % len(self.comparison_plot_widget.dataset_colors) if hasattr(self, 'comparison_plot_widget') else i % 10
                colors.append(['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                             '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'][color_idx])

        if not data_for_boxplot:
            ax = self.k_boxplot_figure.add_subplot(1, 1, 1)
            ax.text(0.5, 0.5, 'No K-values calculated', transform=ax.transAxes,
                   ha='center', va='center', fontsize=12, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            self.k_boxplot_canvas.draw()
            return

        ax = self.k_boxplot_figure.add_subplot(1, 1, 1)

        # Create box plots
        bp = ax.boxplot(data_for_boxplot, labels=labels, patch_artist=True,
                       showmeans=True, meanline=True,
                       boxprops=dict(facecolor='lightblue', alpha=0.7),
                       medianprops=dict(color='red', linewidth=2),
                       meanprops=dict(color='green', linewidth=2, linestyle='--'),
                       whiskerprops=dict(linewidth=1.5),
                       capprops=dict(linewidth=1.5))

        # Color each box
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)

        ax.set_ylabel('Hydraulic Conductivity (m/s)', fontsize=10, fontweight='bold')
        ax.set_title('K-Value Distribution Comparison', fontsize=12, fontweight='bold')
        ax.set_yscale('log')
        ax.grid(True, alpha=0.3, axis='y')
        ax.tick_params(axis='x', rotation=45, labelsize=9)

        # Add legend
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color='red', linewidth=2, label='Median'),
            Line2D([0], [0], color='green', linewidth=2, linestyle='--', label='Mean')
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=8)

        self.k_boxplot_figure.tight_layout()
        self.k_boxplot_canvas.draw()

    def plot_method_applicability_heatmap(self):
        """Create heatmap showing which methods are applicable for each dataset"""
        self.method_heatmap_figure.clear()

        if not self.selected_datasets:
            ax = self.method_heatmap_figure.add_subplot(1, 1, 1)
            ax.text(0.5, 0.5, 'No datasets selected', transform=ax.transAxes,
                   ha='center', va='center', fontsize=12, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            self.method_heatmap_canvas.draw()
            return

        # Collect all methods and their status for each dataset
        all_methods = set()
        for tab in self.selected_datasets:
            results = tab.get_results()
            for result in results:
                all_methods.add(result.method_name)

        if not all_methods:
            ax = self.method_heatmap_figure.add_subplot(1, 1, 1)
            ax.text(0.5, 0.5, 'No K-values calculated', transform=ax.transAxes,
                   ha='center', va='center', fontsize=12, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            self.method_heatmap_canvas.draw()
            return

        methods = sorted(list(all_methods))
        dataset_names = [tab.get_dataset_name() for tab in self.selected_datasets]

        # Create matrix: 0 = N/A, 1 = Error, 2 = Warning, 3 = OK
        matrix = np.zeros((len(methods), len(dataset_names)))

        for j, tab in enumerate(self.selected_datasets):
            results = tab.get_results()
            for i, method in enumerate(methods):
                # Find result for this method
                for result in results:
                    if result.method_name == method:
                        status_str = result.status.value if hasattr(result.status, 'value') else str(result.status)

                        if result.k_value is None or result.k_value <= 0:
                            matrix[i, j] = 0  # N/A / Not calculated
                        elif 'Error' in status_str:
                            matrix[i, j] = 1  # Error
                        elif 'Warning' in status_str:
                            matrix[i, j] = 2  # Warning
                        else:
                            matrix[i, j] = 3  # OK
                        break

        ax = self.method_heatmap_figure.add_subplot(1, 1, 1)

        # Create heatmap with custom colormap
        from matplotlib.colors import ListedColormap
        colors_map = ['#cccccc', '#ff6b6b', '#ffd93d', '#6bcf7f']  # Gray, Red, Yellow, Green
        cmap = ListedColormap(colors_map)

        im = ax.imshow(matrix, cmap=cmap, aspect='auto', vmin=0, vmax=3)

        # Set ticks
        ax.set_xticks(np.arange(len(dataset_names)))
        ax.set_yticks(np.arange(len(methods)))
        ax.set_xticklabels(dataset_names, rotation=45, ha='right', fontsize=9)
        ax.set_yticklabels(methods, fontsize=9)

        ax.set_title('Method Applicability Matrix', fontsize=12, fontweight='bold')
        ax.set_xlabel('Datasets', fontsize=10)
        ax.set_ylabel('Methods', fontsize=10)

        # Add colorbar legend
        cbar = self.method_heatmap_figure.colorbar(im, ax=ax, ticks=[0.375, 1.125, 1.875, 2.625])
        cbar.ax.set_yticklabels(['N/A', 'Error', 'Warning', 'OK'], fontsize=8)

        # Add grid
        ax.set_xticks(np.arange(len(dataset_names))-0.5, minor=True)
        ax.set_yticks(np.arange(len(methods))-0.5, minor=True)
        ax.grid(which='minor', color='white', linestyle='-', linewidth=2)

        self.method_heatmap_figure.tight_layout()
        self.method_heatmap_canvas.draw()
