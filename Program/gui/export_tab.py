"""
Export Tab - Unified export interface for grain size analysis results
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QCheckBox, QComboBox, QLabel, QPushButton, QFileDialog,
    QLineEdit, QSpinBox, QMessageBox, QScrollArea, QButtonGroup,
    QProgressDialog, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QHeaderView, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from typing import List, Dict, Optional
import os
from datetime import datetime

from data_loader import GrainSizeData
from k_calculations_v2 import KCalculationResult


class ExportTab(QWidget):
    """Unified export interface for all data formats"""

    # Signal emitted when export is started/completed
    export_started = pyqtSignal()
    export_completed = pyqtSignal(str)  # Export path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.datasets = []  # List of (name, GrainSizeData, List[KCalculationResult])
        self.setup_ui()

    def setup_ui(self):
        """Setup the export tab UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Create splitter for settings and preview (SIDE BY SIDE)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # === LEFT: Export Settings ===
        settings_widget = QWidget()
        settings_main_layout = QVBoxLayout(settings_widget)
        settings_main_layout.setSpacing(5)
        settings_main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area for the settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)

        # === EXPORT SCOPE ===
        scope_group = QGroupBox("Export Scope")
        scope_layout = QVBoxLayout()

        self.scope_group = QButtonGroup(self)

        self.scope_current = QRadioButton("Current Dataset")
        self.scope_current.setChecked(True)
        self.current_dataset_combo = QComboBox()
        self.current_dataset_combo.setMinimumWidth(200)

        current_layout = QHBoxLayout()
        current_layout.addWidget(self.scope_current)
        current_layout.addWidget(self.current_dataset_combo)
        current_layout.addStretch()

        self.scope_all = QRadioButton("All Loaded Datasets")
        self.all_datasets_label = QLabel("(0 datasets loaded)")

        all_layout = QHBoxLayout()
        all_layout.addWidget(self.scope_all)
        all_layout.addWidget(self.all_datasets_label)
        all_layout.addStretch()

        self.scope_selected = QRadioButton("Selected Datasets")
        self.select_datasets_btn = QPushButton("Select...")
        self.select_datasets_btn.setMaximumWidth(100)
        self.select_datasets_btn.clicked.connect(self.select_datasets)

        selected_layout = QHBoxLayout()
        selected_layout.addWidget(self.scope_selected)
        selected_layout.addWidget(self.select_datasets_btn)
        selected_layout.addStretch()

        self.scope_group.addButton(self.scope_current)
        self.scope_group.addButton(self.scope_all)
        self.scope_group.addButton(self.scope_selected)

        scope_layout.addLayout(current_layout)
        scope_layout.addLayout(all_layout)
        scope_layout.addLayout(selected_layout)
        scope_group.setLayout(scope_layout)

        # === EXPORT FORMAT ===
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout()

        # Data Formats
        data_label = QLabel("<b>Data Formats:</b>")
        self.format_csv = QCheckBox("CSV - Simple tables")
        self.format_csv.setChecked(True)

        csv_options_layout = QHBoxLayout()
        csv_options_layout.setContentsMargins(30, 0, 0, 0)

        self.csv_option_group = QButtonGroup(self)
        self.csv_separate = QRadioButton("One file per dataset")
        self.csv_separate.setChecked(True)
        self.csv_combined = QRadioButton("Combined single file")

        self.csv_option_group.addButton(self.csv_separate)
        self.csv_option_group.addButton(self.csv_combined)

        csv_options_layout.addWidget(self.csv_separate)
        csv_options_layout.addWidget(self.csv_combined)
        csv_options_layout.addStretch()

        self.format_excel = QCheckBox("Excel (.xlsx) - Formatted workbooks")

        excel_options_layout = QHBoxLayout()
        excel_options_layout.setContentsMargins(30, 0, 0, 0)

        self.excel_option_group = QButtonGroup(self)
        self.excel_per_dataset = QRadioButton("One workbook per dataset (multi-sheet)")
        self.excel_per_dataset.setChecked(True)
        self.excel_combined = QRadioButton("Single combined workbook (all datasets)")
        self.excel_method_organized = QRadioButton("Method-organized (compare all datasets)")

        self.excel_option_group.addButton(self.excel_per_dataset)
        self.excel_option_group.addButton(self.excel_combined)
        self.excel_option_group.addButton(self.excel_method_organized)

        excel_options_layout.addWidget(self.excel_per_dataset)
        excel_options_layout.addWidget(self.excel_combined)
        excel_options_layout.addStretch()

        excel_options_layout2 = QHBoxLayout()
        excel_options_layout2.setContentsMargins(30, 0, 0, 0)
        excel_options_layout2.addWidget(self.excel_method_organized)
        excel_options_layout2.addStretch()

        self.format_json = QCheckBox("JSON - Structured data")

        format_layout.addWidget(data_label)
        format_layout.addWidget(self.format_csv)
        format_layout.addLayout(csv_options_layout)
        format_layout.addSpacing(5)
        format_layout.addWidget(self.format_excel)
        format_layout.addLayout(excel_options_layout)
        format_layout.addLayout(excel_options_layout2)
        format_layout.addSpacing(5)
        format_layout.addWidget(self.format_json)

        # Plot Formats
        format_layout.addSpacing(10)
        plot_label = QLabel("<b>Plots:</b>")

        self.format_png = QCheckBox("PNG (raster)")
        self.format_png.setChecked(True)
        self.png_dpi_label = QLabel("DPI:")
        self.png_dpi = QSpinBox()
        self.png_dpi.setRange(72, 600)
        self.png_dpi.setValue(300)
        self.png_dpi.setSingleStep(50)

        png_layout = QHBoxLayout()
        png_layout.setContentsMargins(30, 0, 0, 0)
        png_layout.addWidget(self.format_png)
        png_layout.addWidget(self.png_dpi_label)
        png_layout.addWidget(self.png_dpi)
        png_layout.addStretch()

        self.format_svg = QCheckBox("SVG (vector)")
        self.format_pdf_plot = QCheckBox("PDF (vector)")

        format_layout.addWidget(plot_label)
        format_layout.addLayout(png_layout)
        format_layout.addWidget(self.format_svg)
        format_layout.addWidget(self.format_pdf_plot)

        format_group.setLayout(format_layout)

        # === CONTENT SELECTION ===
        content_group = QGroupBox("Content Selection")
        content_sel_layout = QVBoxLayout()

        self.content_grain_dist = QCheckBox("Raw grain size distribution")
        self.content_grain_dist.setChecked(True)

        self.content_percentiles = QCheckBox("Characteristic grain sizes (D10, D50, etc.)")
        self.content_percentiles.setChecked(True)

        self.content_gradation = QCheckBox("Gradation parameters (Cu, Cc)")
        self.content_gradation.setChecked(True)

        self.content_classification = QCheckBox("Soil classification")
        self.content_classification.setChecked(True)

        self.content_k_values = QCheckBox("K-value results (all methods)")
        self.content_k_values.setChecked(True)

        self.content_statistics = QCheckBox("Statistical summaries")
        self.content_statistics.setChecked(True)

        self.content_plots = QCheckBox("Plots/figures")
        self.content_plots.setChecked(True)

        self.content_formulas = QCheckBox("Include formulas and methodology")
        self.content_formulas.setChecked(False)

        self.content_validation = QCheckBox("Include validation messages")
        self.content_validation.setChecked(False)

        content_sel_layout.addWidget(self.content_grain_dist)
        content_sel_layout.addWidget(self.content_percentiles)
        content_sel_layout.addWidget(self.content_gradation)
        content_sel_layout.addWidget(self.content_classification)
        content_sel_layout.addWidget(self.content_k_values)
        content_sel_layout.addWidget(self.content_statistics)
        content_sel_layout.addWidget(self.content_plots)
        content_sel_layout.addWidget(self.content_formulas)
        content_sel_layout.addWidget(self.content_validation)

        content_group.setLayout(content_sel_layout)

        # === OUTPUT OPTIONS ===
        output_group = QGroupBox("Output Options")
        output_layout = QVBoxLayout()

        # Output directory
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Output Directory:")
        self.output_dir = QLineEdit()
        self.output_dir.setText(os.path.expanduser("~/Desktop"))
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_output_dir)

        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.output_dir)
        dir_layout.addWidget(self.browse_btn)

        # Filename template
        template_layout = QHBoxLayout()
        template_label = QLabel("Filename Template:")
        self.filename_template = QLineEdit()
        self.filename_template.setText("{sample_name}_results_{date}")

        template_layout.addWidget(template_label)
        template_layout.addWidget(self.filename_template)

        # Template help
        help_label = QLabel(
            "<small>Available variables: {sample_name}, {date}, {time}, {project}, {method}</small>"
        )
        help_label.setWordWrap(True)

        output_layout.addLayout(dir_layout)
        output_layout.addLayout(template_layout)
        output_layout.addWidget(help_label)

        output_group.setLayout(output_layout)

        # === ACTION BUTTONS ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.preview_btn = QPushButton("Preview Export")
        self.preview_btn.clicked.connect(self.preview_export)

        self.export_btn = QPushButton("Export Now")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b8e23;
                color: white;
                font-weight: bold;
                padding: 8px 24px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7ca02a;
            }
        """)
        self.export_btn.clicked.connect(self.export_now)

        self.save_config_btn = QPushButton("Save Export Config")
        self.save_config_btn.clicked.connect(self.save_export_config)

        button_layout.addWidget(self.preview_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.save_config_btn)

        # Add all groups to content layout
        content_layout.addWidget(scope_group)
        content_layout.addWidget(format_group)
        content_layout.addWidget(content_group)
        content_layout.addWidget(output_group)
        content_layout.addStretch()

        scroll.setWidget(content_widget)

        settings_main_layout.addWidget(scroll)
        settings_main_layout.addLayout(button_layout)

        # === RIGHT: Preview Tabs ===
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(5, 0, 0, 0)
        preview_layout.setSpacing(5)

        preview_label = QLabel("📊 Data Preview")
        preview_label.setStyleSheet("font-weight: bold; font-size: 13pt; padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        preview_layout.addWidget(preview_label)

        self.preview_tabs = QTabWidget()
        self.preview_tabs.setDocumentMode(True)

        # K-Results Preview Tab
        self.k_results_preview = QTableWidget()
        self.k_results_preview.setAlternatingRowColors(True)
        self.k_results_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.k_results_preview.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.preview_tabs.addTab(self.k_results_preview, "K-Results")

        # Grain Data Preview Tab
        self.grain_data_preview = QTableWidget()
        self.grain_data_preview.setAlternatingRowColors(True)
        self.grain_data_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_tabs.addTab(self.grain_data_preview, "Grain Size Data")

        # Export Format Preview Tab
        self.format_preview = QTextEdit()
        self.format_preview.setReadOnly(True)
        self.format_preview.setFont(QFont("Courier", 9))
        self.preview_tabs.addTab(self.format_preview, "Export Format Preview")

        # Files Preview Tab
        self.files_preview = QTableWidget()
        self.files_preview.setAlternatingRowColors(True)
        self.files_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_tabs.addTab(self.files_preview, "Files to Export")

        preview_layout.addWidget(self.preview_tabs)

        # Add to splitter
        splitter.addWidget(settings_widget)
        splitter.addWidget(preview_widget)

        # Set initial sizes: Settings ~400px, Preview gets the rest
        splitter.setSizes([400, 800])
        splitter.setStretchFactor(0, 0)  # Settings: fixed-ish
        splitter.setStretchFactor(1, 1)  # Preview: stretches

        main_layout.addWidget(splitter)

        # Connect signals
        self.format_csv.toggled.connect(self.update_format_options)
        self.format_excel.toggled.connect(self.update_format_options)
        self.format_png.toggled.connect(self.update_format_options)

        # Connect signals for preview updates
        self.scope_current.toggled.connect(self.update_preview)
        self.scope_all.toggled.connect(self.update_preview)
        self.scope_selected.toggled.connect(self.update_preview)
        self.current_dataset_combo.currentIndexChanged.connect(self.update_preview)
        self.format_csv.toggled.connect(self.update_preview)
        self.format_excel.toggled.connect(self.update_preview)
        self.csv_separate.toggled.connect(self.update_preview)
        self.csv_combined.toggled.connect(self.update_preview)

        self.update_format_options()
        self.update_preview()

    def update_datasets(self, datasets: List[tuple]):
        """
        Update the list of available datasets

        Args:
            datasets: List of (name, GrainSizeData, List[KCalculationResult]) tuples
        """
        print(f"[DEBUG] ExportTab.update_datasets called with {len(datasets)} datasets")
        for idx, (name, dataset, results) in enumerate(datasets):
            print(f"[DEBUG]   Dataset {idx}: {name}, results={len(results) if results else 0}")
        self.datasets = datasets

        # Update current dataset combo
        self.current_dataset_combo.clear()
        for name, _, _ in datasets:
            self.current_dataset_combo.addItem(name)

        # Update count label
        count = len(datasets)
        self.all_datasets_label.setText(f"({count} dataset{'s' if count != 1 else ''} loaded)")

        # Enable/disable scope options
        has_datasets = count > 0
        self.scope_current.setEnabled(has_datasets)
        self.scope_all.setEnabled(has_datasets)
        self.scope_selected.setEnabled(has_datasets and count > 1)
        self.current_dataset_combo.setEnabled(has_datasets)
        self.select_datasets_btn.setEnabled(has_datasets and count > 1)
        self.export_btn.setEnabled(has_datasets)

        # Update preview
        self.update_preview()

    def update_format_options(self):
        """Enable/disable format options based on selections"""
        # CSV options
        csv_enabled = self.format_csv.isChecked()
        self.csv_separate.setEnabled(csv_enabled)
        self.csv_combined.setEnabled(csv_enabled)

        # Excel options
        excel_enabled = self.format_excel.isChecked()
        self.excel_per_dataset.setEnabled(excel_enabled)
        self.excel_combined.setEnabled(excel_enabled)
        self.excel_method_organized.setEnabled(excel_enabled)

        # PNG DPI
        png_enabled = self.format_png.isChecked()
        self.png_dpi_label.setEnabled(png_enabled)
        self.png_dpi.setEnabled(png_enabled)

    def browse_output_dir(self):
        """Browse for output directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_dir.text()
        )
        if dir_path:
            self.output_dir.setText(dir_path)

    def select_datasets(self):
        """Show dialog to select specific datasets"""
        # TODO: Implement multi-select dialog
        QMessageBox.information(
            self,
            "Select Datasets",
            "Multi-dataset selection dialog will be implemented"
        )

    def update_preview(self):
        """Update all preview tabs based on current selections"""
        self._update_k_results_preview()
        self._update_grain_data_preview()
        self._update_format_preview()
        self._update_files_preview()

    def _update_k_results_preview(self):
        """Update K-Results preview table"""
        datasets_to_export = self._get_datasets_to_export()

        # Configure table
        self.k_results_preview.clear()
        headers = ["Dataset", "Method", "K (m/s)", "K (cm/s)", "K (m/d)", "Status", "D10 (mm)", "Porosity"]
        self.k_results_preview.setColumnCount(len(headers))
        self.k_results_preview.setHorizontalHeaderLabels(headers)

        # Count total results
        total_results = 0
        for _, _, results in datasets_to_export:
            if results:
                total_results += len(results)

        self.k_results_preview.setRowCount(total_results)

        # Populate table
        row = 0
        for name, dataset, results in datasets_to_export:
            if results:
                for result in results:
                    if result.k_value is not None:
                        # Dataset name
                        self.k_results_preview.setItem(row, 0, QTableWidgetItem(name))

                        # Method
                        self.k_results_preview.setItem(row, 1, QTableWidgetItem(result.method_name))

                        # K-values in different units
                        self.k_results_preview.setItem(row, 2, QTableWidgetItem(f"{result.k_value:.3e}"))
                        self.k_results_preview.setItem(row, 3, QTableWidgetItem(f"{result.k_value * 100:.3e}"))
                        self.k_results_preview.setItem(row, 4, QTableWidgetItem(f"{result.k_value * 86400:.2f}"))

                        # Status
                        status_text = result.status.value if hasattr(result.status, 'value') else str(result.status)
                        self.k_results_preview.setItem(row, 5, QTableWidgetItem(status_text))

                        # D10
                        d10 = dataset.get_d10() if hasattr(dataset, 'get_d10') else None
                        self.k_results_preview.setItem(row, 6, QTableWidgetItem(f"{d10:.4f}" if d10 else "N/A"))

                        # Porosity
                        self.k_results_preview.setItem(row, 7, QTableWidgetItem(f"{result.porosity:.3f}"))

                        row += 1

        # Auto-resize columns
        self.k_results_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.k_results_preview.horizontalHeader().setStretchLastSection(True)

    def _update_grain_data_preview(self):
        """Update grain size data preview table"""
        datasets_to_export = self._get_datasets_to_export()

        if not datasets_to_export:
            self.grain_data_preview.clear()
            self.grain_data_preview.setRowCount(0)
            self.grain_data_preview.setColumnCount(0)
            return

        # Show summary of grain size data
        headers = ["Dataset", "D10 (mm)", "D20 (mm)", "D30 (mm)", "D50 (mm)", "D60 (mm)", "Cu", "Cc", "Data Points"]
        self.grain_data_preview.setColumnCount(len(headers))
        self.grain_data_preview.setHorizontalHeaderLabels(headers)
        self.grain_data_preview.setRowCount(len(datasets_to_export))

        for row, (name, dataset, _) in enumerate(datasets_to_export):
            # Dataset name
            self.grain_data_preview.setItem(row, 0, QTableWidgetItem(name))

            # Percentiles
            d10 = dataset.get_d10() if hasattr(dataset, 'get_d10') else None
            d20 = dataset.get_d20() if hasattr(dataset, 'get_d20') else None
            d30 = dataset.get_d30() if hasattr(dataset, 'get_d30') else None
            d50 = dataset.get_d50() if hasattr(dataset, 'get_d50') else None
            d60 = dataset.get_d60() if hasattr(dataset, 'get_d60') else None

            self.grain_data_preview.setItem(row, 1, QTableWidgetItem(f"{d10:.4f}" if d10 else "N/A"))
            self.grain_data_preview.setItem(row, 2, QTableWidgetItem(f"{d20:.4f}" if d20 else "N/A"))
            self.grain_data_preview.setItem(row, 3, QTableWidgetItem(f"{d30:.4f}" if d30 else "N/A"))
            self.grain_data_preview.setItem(row, 4, QTableWidgetItem(f"{d50:.4f}" if d50 else "N/A"))
            self.grain_data_preview.setItem(row, 5, QTableWidgetItem(f"{d60:.4f}" if d60 else "N/A"))

            # Gradation parameters
            cu = dataset.get_uniformity_coefficient() if hasattr(dataset, 'get_uniformity_coefficient') else None
            cc = dataset.get_coefficient_of_curvature() if hasattr(dataset, 'get_coefficient_of_curvature') else None

            self.grain_data_preview.setItem(row, 6, QTableWidgetItem(f"{cu:.2f}" if cu else "N/A"))
            self.grain_data_preview.setItem(row, 7, QTableWidgetItem(f"{cc:.2f}" if cc else "N/A"))

            # Number of data points
            data_points = len(dataset.particle_sizes) if hasattr(dataset, 'particle_sizes') else 0
            self.grain_data_preview.setItem(row, 8, QTableWidgetItem(str(data_points)))

        # Auto-resize columns
        self.grain_data_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.grain_data_preview.horizontalHeader().setStretchLastSection(True)

    def _update_format_preview(self):
        """Update export format preview showing what CSV/Excel will look like"""
        datasets_to_export = self._get_datasets_to_export()

        if not datasets_to_export:
            self.format_preview.setPlainText("No datasets selected for export")
            return

        preview_text = []

        # Show CSV preview if selected
        if self.format_csv.isChecked():
            if self.csv_combined.isChecked():
                # LONG FORMAT (combined)
                preview_text.append("=== CSV LONG FORMAT (combined_all_datasets.csv) ===")
                preview_text.append("")
                preview_text.append("Sample Name,Method,K (m/s),K (cm/s),K (m/d),Status,D10 (mm),D50 (mm),D60 (mm),Cu,Cc")

                # Show first 10 rows
                row_count = 0
                for name, dataset, results in datasets_to_export[:3]:  # First 3 datasets
                    if results:
                        for result in results[:5]:  # First 5 methods per dataset
                            if result.k_value is not None:
                                d10 = dataset.get_d10() if hasattr(dataset, 'get_d10') else 0
                                d50 = dataset.get_d50() if hasattr(dataset, 'get_d50') else 0
                                d60 = dataset.get_d60() if hasattr(dataset, 'get_d60') else 0
                                cu = dataset.get_uniformity_coefficient() if hasattr(dataset, 'get_uniformity_coefficient') else 0
                                cc = dataset.get_coefficient_of_curvature() if hasattr(dataset, 'get_coefficient_of_curvature') else 0

                                status = result.status.value if hasattr(result.status, 'value') else str(result.status)

                                preview_text.append(
                                    f"{name},{result.method_name},{result.k_value:.3e},"
                                    f"{result.k_value * 100:.3e},{result.k_value * 86400:.2f},"
                                    f"{status},{d10:.4f},{d50:.4f},{d60:.4f},{cu:.2f},{cc:.2f}"
                                )
                                row_count += 1
                                if row_count >= 10:
                                    break
                    if row_count >= 10:
                        break

                if row_count >= 10:
                    preview_text.append("... (showing first 10 rows)")

                # WIDE FORMAT (for statistical analysis)
                preview_text.append("")
                preview_text.append("=" * 60)
                preview_text.append("")
                preview_text.append("=== CSV WIDE FORMAT (wide_format_all_datasets.csv) ===")
                preview_text.append("(One row per dataset, one column per method)")
                preview_text.append("")

                # Get unique methods from first dataset
                method_names = []
                if datasets_to_export and datasets_to_export[0][2]:
                    method_names = [r.method_name for r in datasets_to_export[0][2][:6]]  # First 6 methods

                # Build header - simplified for preview
                header_parts = ["Sample_Name", "Temperature_C", "Porosity", "D10_mm", "D50_mm", "D60_mm", "Cu", "Cc"]
                for method in method_names:
                    safe_name = method.replace('-', '_').replace(' ', '_')
                    header_parts.append(f"K_{safe_name}_m/s")

                preview_text.append(",".join(header_parts))

                # Show first 3 datasets
                for name, dataset, results in datasets_to_export[:3]:
                    row_parts = []
                    row_parts.append(name)
                    row_parts.append(str(dataset.temperature))
                    row_parts.append(f"{dataset.current_porosity or dataset.porosity:.3f}")

                    d10 = dataset.get_d10() if hasattr(dataset, 'get_d10') else 0
                    d50 = dataset.get_d50() if hasattr(dataset, 'get_d50') else 0
                    d60 = dataset.get_d60() if hasattr(dataset, 'get_d60') else 0
                    cu = dataset.get_uniformity_coefficient() if hasattr(dataset, 'get_uniformity_coefficient') else 0
                    cc = dataset.get_coefficient_of_curvature() if hasattr(dataset, 'get_coefficient_of_curvature') else 0

                    row_parts.extend([f"{d10:.4f}", f"{d50:.4f}", f"{d60:.4f}", f"{cu:.2f}", f"{cc:.2f}"])

                    # Add K-values for each method
                    method_dict = {r.method_name: r for r in results} if results else {}
                    for method in method_names:
                        if method in method_dict and method_dict[method].k_value:
                            row_parts.append(f"{method_dict[method].k_value:.3e}")
                        else:
                            row_parts.append("")

                    preview_text.append(",".join(row_parts))

                if len(datasets_to_export) > 3:
                    preview_text.append(f"... (showing first 3 of {len(datasets_to_export)} datasets)")

                preview_text.append("")
                preview_text.append("NOTE: Full wide format includes ALL methods in multiple units (m/s, cm/s, m/d)")

            else:
                preview_text.append("=== CSV SEPARATE FILES PREVIEW ===")
                preview_text.append("")
                if datasets_to_export:
                    name, dataset, results = datasets_to_export[0]
                    preview_text.append(f"Example: {name}_k_values.csv")
                    preview_text.append("")
                    preview_text.append("Method,K (m/s),K (cm/s),K (m/d),Status")

                    if results:
                        for result in results[:10]:
                            if result.k_value is not None:
                                status = result.status.value if hasattr(result.status, 'value') else str(result.status)
                                preview_text.append(
                                    f"{result.method_name},{result.k_value:.3e},"
                                    f"{result.k_value * 100:.3e},{result.k_value * 86400:.2f},{status}"
                                )

        # Show Excel preview if selected
        if self.format_excel.isChecked():
            if preview_text:
                preview_text.append("")
                preview_text.append("=" * 60)
                preview_text.append("")

            mode = "per dataset" if self.excel_per_dataset.isChecked() else "combined" if self.excel_combined.isChecked() else "method-organized"
            preview_text.append(f"=== EXCEL WORKBOOK ({mode.upper()}) ===")
            preview_text.append("")

            if self.excel_per_dataset.isChecked():
                if datasets_to_export:
                    name, dataset, results = datasets_to_export[0]
                    preview_text.append(f"Example workbook: {name}.xlsx")
                    preview_text.append("  Sheets:")
                    preview_text.append("    - Summary")
                    preview_text.append("    - Grain_Size_Data")
                    preview_text.append("    - Percentiles")
                    preview_text.append("    - K_Values")
                    preview_text.append("    - Statistics")
            elif self.excel_combined.isChecked():
                preview_text.append("Workbook: combined_all_datasets.xlsx")
                preview_text.append("  Sheets:")
                preview_text.append("    - All_Datasets_Summary")
                for name, _, _ in datasets_to_export[:5]:
                    preview_text.append(f"    - {name}")
                if len(datasets_to_export) > 5:
                    preview_text.append(f"    ... and {len(datasets_to_export) - 5} more")

        if not preview_text:
            preview_text.append("Select CSV or Excel format to see preview")

        self.format_preview.setPlainText("\n".join(preview_text))

    def _update_files_preview(self):
        """Update files preview showing what files will be created"""
        datasets_to_export = self._get_datasets_to_export()
        config = self._build_export_config()

        headers = ["Filename", "Type", "Size Estimate", "Description"]
        self.files_preview.setColumnCount(len(headers))
        self.files_preview.setHorizontalHeaderLabels(headers)

        files = []

        # CSV files
        if config.get('csv', False):
            if config.get('csv_mode') == 'separate':
                for name, _, _ in datasets_to_export:
                    base = self._format_filename(config['filename_template'], name, '')
                    if config.get('grain_distribution'):
                        files.append((f"{base}_grain_size.csv", "CSV", "~5-50 KB", "Grain size distribution"))
                    if config.get('k_values'):
                        files.append((f"{base}_k_values.csv", "CSV", "~2-10 KB", "K-value results"))
                    if config.get('statistics'):
                        files.append((f"{base}_statistics.csv", "CSV", "~1-5 KB", "Statistical summary"))
            else:
                files.append(("combined_all_datasets.csv", "CSV", "~10-100 KB", "All K-values combined"))
                files.append(("wide_format_all_datasets.csv", "CSV", "~10-100 KB", "Wide format for analysis"))

        # Excel files
        if config.get('excel', False):
            mode = config.get('excel_mode', 'per_dataset')
            if mode == 'per_dataset':
                for name, _, _ in datasets_to_export:
                    base = self._format_filename(config['filename_template'], name, '.xlsx')
                    files.append((base, "Excel", "~50-200 KB", "Complete dataset workbook"))
            elif mode == 'combined':
                files.append(("combined_all_datasets.xlsx", "Excel", "~100-500 KB", "All datasets combined"))
            else:
                files.append(("method_comparison.xlsx", "Excel", "~50-200 KB", "Method-organized comparison"))

        # JSON files
        if config.get('json', False):
            for name, _, _ in datasets_to_export:
                base = self._format_filename(config['filename_template'], name, '.json')
                files.append((base, "JSON", "~10-50 KB", "Structured data export"))

        self.files_preview.setRowCount(len(files))

        for row, (filename, file_type, size, description) in enumerate(files):
            self.files_preview.setItem(row, 0, QTableWidgetItem(filename))
            self.files_preview.setItem(row, 1, QTableWidgetItem(file_type))
            self.files_preview.setItem(row, 2, QTableWidgetItem(size))
            self.files_preview.setItem(row, 3, QTableWidgetItem(description))

        # Auto-resize columns
        self.files_preview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.files_preview.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.files_preview.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.files_preview.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

    def _format_filename(self, template: str, name: str, extension: str = "") -> str:
        """Format filename from template (helper method)"""
        now = datetime.now()

        replacements = {
            '{sample_name}': name,
            '{date}': now.strftime('%Y%m%d'),
            '{time}': now.strftime('%H%M%S'),
            '{project}': 'grain_analysis',
            '{method}': 'all'
        }

        filename = template
        for key, value in replacements.items():
            filename = filename.replace(key, value)

        # Remove invalid chars
        invalid_chars = '<>:"|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        if extension and not filename.endswith(extension):
            filename += extension

        return filename

    def preview_export(self):
        """Preview what will be exported with detailed data availability"""
        # Get selected datasets
        datasets_to_export = self._get_datasets_to_export()

        if not datasets_to_export:
            QMessageBox.warning(
                self,
                "No Datasets",
                "No datasets available for export"
            )
            return

        # Build preview text
        preview_lines = []
        preview_lines.append(f"📊 EXPORT PREVIEW")
        preview_lines.append("=" * 60)
        preview_lines.append("")

        # Analyze datasets
        total_datasets = len(datasets_to_export)
        datasets_with_k_results = 0
        total_k_results = 0

        preview_lines.append(f"📁 DATASETS ({total_datasets} total)")
        preview_lines.append("-" * 60)

        for name, dataset, results in datasets_to_export:
            k_count = len(results) if results else 0
            if k_count > 0:
                datasets_with_k_results += 1
                total_k_results += k_count

            # Get key grain sizes
            d10 = dataset.get_d10() if hasattr(dataset, 'get_d10') else None
            d50 = dataset.get_d50() if hasattr(dataset, 'get_d50') else None

            status = "✓" if k_count > 0 else "✗"
            preview_lines.append(f"  {status} {name}")
            if d10 and d50:
                preview_lines.append(f"      D10={d10:.3f}mm, D50={d50:.3f}mm")
            if k_count > 0:
                preview_lines.append(f"      {k_count} K-calculation results available")
            else:
                preview_lines.append(f"      ⚠️  No K-calculation results - run calculations first!")

        preview_lines.append("")
        preview_lines.append(f"Summary: {datasets_with_k_results}/{total_datasets} datasets have K-results")
        preview_lines.append(f"Total K-calculations: {total_k_results}")
        preview_lines.append("")

        # Estimate files to be created
        preview_lines.append("📄 FILES TO BE CREATED")
        preview_lines.append("-" * 60)

        file_count = 0

        if self.format_csv.isChecked():
            if self.csv_separate.isChecked():
                count = total_datasets * 3  # grain_size, k_values, statistics per dataset
                preview_lines.append(f"  • CSV files: ~{count} files (separate per dataset)")
                file_count += count
            else:
                preview_lines.append(f"  • CSV files: 2 files (combined + wide format)")
                file_count += 2

        if self.format_excel.isChecked():
            if self.excel_per_dataset.isChecked():
                preview_lines.append(f"  • Excel workbooks: {total_datasets} files (one per dataset)")
                file_count += total_datasets
            elif self.excel_combined.isChecked():
                preview_lines.append(f"  • Excel workbooks: 1 file (all datasets combined)")
                file_count += 1
            else:
                preview_lines.append(f"  • Excel workbooks: 1 file (method-organized)")
                file_count += 1

        if self.format_json.isChecked():
            preview_lines.append(f"  • JSON files: {total_datasets} files")
            file_count += total_datasets

        if self.content_plots.isChecked():
            plot_formats = sum([
                self.format_png.isChecked(),
                self.format_svg.isChecked(),
                self.format_pdf_plot.isChecked()
            ])
            if plot_formats > 0:
                count = total_datasets * plot_formats
                preview_lines.append(f"  • Plot files: ~{count} files ({plot_formats} formats × {total_datasets} datasets)")
                file_count += count

        preview_lines.append("")
        preview_lines.append(f"Total estimated files: ~{file_count}")
        preview_lines.append("")

        # Output settings
        preview_lines.append("⚙️  OUTPUT SETTINGS")
        preview_lines.append("-" * 60)
        preview_lines.append(f"Directory: {self.output_dir.text()}")
        preview_lines.append(f"Template: {self.filename_template.text()}")

        # Show example filenames
        if datasets_to_export:
            example_name = datasets_to_export[0][0]
            now = datetime.now()
            example_filename = self.filename_template.text()
            example_filename = example_filename.replace('{sample_name}', example_name)
            example_filename = example_filename.replace('{date}', now.strftime('%Y%m%d'))
            example_filename = example_filename.replace('{time}', now.strftime('%H%M%S'))
            preview_lines.append(f"Example: {example_filename}_k_values.csv")

        preview_lines.append("")

        # Content selection
        preview_lines.append("📋 CONTENT INCLUDED")
        preview_lines.append("-" * 60)
        content_items = []
        if self.content_grain_dist.isChecked():
            content_items.append("Raw grain size distribution")
        if self.content_percentiles.isChecked():
            content_items.append("Characteristic grain sizes")
        if self.content_gradation.isChecked():
            content_items.append("Gradation parameters")
        if self.content_classification.isChecked():
            content_items.append("Soil classification")
        if self.content_k_values.isChecked():
            content_items.append("K-value results (all methods)")
        if self.content_statistics.isChecked():
            content_items.append("Statistical summaries")
        if self.content_plots.isChecked():
            content_items.append("Plots/figures")
        if self.content_formulas.isChecked():
            content_items.append("Formulas and methodology")
        if self.content_validation.isChecked():
            content_items.append("Validation messages")

        for item in content_items:
            preview_lines.append(f"  ✓ {item}")

        preview_text = "\n".join(preview_lines)

        # Create a scrollable message box for long preview
        msg = QMessageBox(self)
        msg.setWindowTitle("Export Preview")
        msg.setText(preview_text)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setStyleSheet("QLabel{min-width: 600px; font-family: monospace;}")
        msg.exec()

    def export_now(self):
        """Execute the export operation"""
        from gui.export_manager import ExportManager

        # Get selected datasets
        datasets_to_export = self._get_datasets_to_export()

        if not datasets_to_export:
            QMessageBox.warning(
                self,
                "No Datasets",
                "No datasets available for export"
            )
            return

        # Check if K-values are requested but not available
        if self.content_k_values.isChecked():
            datasets_without_k = []
            for name, dataset, results in datasets_to_export:
                if not results or len(results) == 0:
                    datasets_without_k.append(name)

            if datasets_without_k:
                warning_msg = "⚠️  Some datasets don't have K-calculation results yet:\n\n"
                for name in datasets_without_k[:5]:  # Show first 5
                    warning_msg += f"  • {name}\n"
                if len(datasets_without_k) > 5:
                    warning_msg += f"  ... and {len(datasets_without_k) - 5} more\n"
                warning_msg += "\nRun K-calculations first to include them in the export.\n\n"
                warning_msg += "Do you want to continue exporting without these results?"

                reply = QMessageBox.question(
                    self,
                    "Missing K-Calculations",
                    warning_msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.No:
                    return

        # Verify output directory exists
        output_dir = self.output_dir.text()
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Could not create output directory:\n{e}"
                )
                return

        # Build export configuration
        config = self._build_export_config()

        # Create export manager
        manager = ExportManager()

        # Show progress dialog
        progress = QProgressDialog(
            "Exporting data...",
            "Cancel",
            0,
            100,
            self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        try:
            self.export_started.emit()

            # Perform export
            exported_files = manager.export(datasets_to_export, config, progress)

            progress.close()

            # Show success message
            file_list = "\n".join([f"  • {os.path.basename(f)}" for f in exported_files[:10]])
            if len(exported_files) > 10:
                file_list += f"\n  ... and {len(exported_files) - 10} more"

            QMessageBox.information(
                self,
                "Export Successful",
                f"Successfully exported {len(exported_files)} file(s) to:\n{output_dir}\n\nFiles:\n{file_list}"
            )

            self.export_completed.emit(output_dir)

        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self,
                "Export Error",
                f"An error occurred during export:\n{str(e)}"
            )

    def save_export_config(self):
        """Save current export configuration"""
        # TODO: Implement config save/load
        QMessageBox.information(
            self,
            "Save Config",
            "Export configuration save/load will be implemented"
        )

    def _get_datasets_to_export(self) -> List[tuple]:
        """Get the list of datasets to export based on scope selection"""
        if self.scope_current.isChecked():
            # Export current dataset only
            idx = self.current_dataset_combo.currentIndex()
            if 0 <= idx < len(self.datasets):
                return [self.datasets[idx]]
            return []

        elif self.scope_all.isChecked():
            # Export all datasets
            return self.datasets

        elif self.scope_selected.isChecked():
            # TODO: Get selected datasets from selection dialog
            return self.datasets

        return []

    def _build_export_config(self) -> Dict:
        """Build export configuration dictionary"""
        config = {
            # Formats
            'csv': self.format_csv.isChecked(),
            'csv_mode': 'separate' if self.csv_separate.isChecked() else 'combined',

            'excel': self.format_excel.isChecked(),
            'excel_mode': 'per_dataset' if self.excel_per_dataset.isChecked()
                         else 'combined' if self.excel_combined.isChecked()
                         else 'method_organized',

            'json': self.format_json.isChecked(),

            'png': self.format_png.isChecked(),
            'png_dpi': self.png_dpi.value(),

            'svg': self.format_svg.isChecked(),
            'pdf_plot': self.format_pdf_plot.isChecked(),

            # Content
            'grain_distribution': self.content_grain_dist.isChecked(),
            'percentiles': self.content_percentiles.isChecked(),
            'gradation': self.content_gradation.isChecked(),
            'classification': self.content_classification.isChecked(),
            'k_values': self.content_k_values.isChecked(),
            'statistics': self.content_statistics.isChecked(),
            'plots': self.content_plots.isChecked(),
            'formulas': self.content_formulas.isChecked(),
            'validation': self.content_validation.isChecked(),

            # Output
            'output_dir': self.output_dir.text(),
            'filename_template': self.filename_template.text(),
        }

        return config
