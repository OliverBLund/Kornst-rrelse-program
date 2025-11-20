"""
Export Tab - Unified export interface for grain size analysis results
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QCheckBox, QComboBox, QLabel, QPushButton, QFileDialog,
    QLineEdit, QSpinBox, QMessageBox, QScrollArea, QButtonGroup,
    QProgressDialog, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QHeaderView, QSplitter, QFrame, QTreeWidget, QTreeWidgetItem,
    QToolButton, QSizePolicy, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QColor
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

        # Selected formats (for card-based selection)
        self.selected_formats = {
            'csv_long': True,
            'csv_wide': True,
            'excel': False,
            'json': False,
            'png': True,
            'svg': False,
            'pdf': False
        }

        # Content toggles
        self.content_enabled = {
            'grain_data': True,
            'k_values': True,
            'statistics': True,
            'plots': True
        }

        self.setup_ui()

    def _create_format_card(self, format_key: str, title: str, description: str, icon_text: str) -> QPushButton:
        """Create a compact clickable format selection card"""
        card = QPushButton()
        card.setCheckable(True)
        card.setChecked(self.selected_formats.get(format_key, False))
        card.setObjectName(f"format_card_{format_key}")
        card.setMinimumHeight(50)
        card.setMaximumHeight(50)
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        # Store format key as property
        card.setProperty("format_key", format_key)

        # Create layout for card contents
        card_layout = QHBoxLayout(card)
        card_layout.setSpacing(8)
        card_layout.setContentsMargins(8, 6, 8, 6)

        # Icon
        icon_label = QLabel(icon_text)
        icon_label.setFont(QFont("Segoe UI", 16))
        icon_label.setFixedWidth(30)
        card_layout.addWidget(icon_label)

        # Title (no description to save space)
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        card_layout.addWidget(title_label)
        card_layout.addStretch()

        # Update card style based on selection
        self._update_card_style(card, format_key)

        # Connect click handler
        card.clicked.connect(lambda: self._toggle_format(format_key))

        return card

    def _update_card_style(self, card: QPushButton, format_key: str):
        """Update card styling based on selection state"""
        is_selected = self.selected_formats.get(format_key, False)

        # Update checked state
        card.setChecked(is_selected)

        if is_selected:
            card.setStyleSheet("""
                QPushButton {
                    background-color: #e8f5e9;
                    border: 2px solid #6b8e23;
                    border-radius: 6px;
                    text-align: left;
                    padding-left: 0px;
                }
                QPushButton:hover {
                    background-color: #dcedc8;
                }
                QPushButton:pressed {
                    background-color: #c8e6c9;
                }
            """)
        else:
            card.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    border: 2px solid #ddd;
                    border-radius: 6px;
                    text-align: left;
                    padding-left: 0px;
                }
                QPushButton:hover {
                    background-color: #eeeeee;
                    border-color: #bbb;
                }
                QPushButton:pressed {
                    background-color: #e0e0e0;
                }
            """)

    def _toggle_format(self, format_key: str):
        """Toggle format selection"""
        self.selected_formats[format_key] = not self.selected_formats.get(format_key, False)

        # Update all cards
        for i in range(self.formats_layout.count()):
            widget = self.formats_layout.itemAt(i).widget()
            if widget and hasattr(widget, 'property'):
                key = widget.property("format_key")
                if key:
                    self._update_card_style(widget, key)

        # Update preview and file tree
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def update_file_tree(self):
        """Update the file tree showing exact files that will be created"""
        if not hasattr(self, 'file_tree'):
            return

        self.file_tree.clear()

        datasets_to_export = self._get_datasets_to_export()
        if not datasets_to_export:
            item = QTreeWidgetItem(["No datasets selected"])
            self.file_tree.addTopLevelItem(item)
            return

        # CSV Files
        if self.selected_formats.get('csv_long') or self.selected_formats.get('csv_wide'):
            csv_folder = QTreeWidgetItem(["📁 CSV Files"])
            csv_folder.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))

            if self.selected_formats.get('csv_long'):
                long_item = QTreeWidgetItem(["📄 combined_all_datasets.csv", "~50 KB", "All K-values (long format)"])
                csv_folder.addChild(long_item)

            if self.selected_formats.get('csv_wide'):
                wide_item = QTreeWidgetItem(["📄 wide_format_all_datasets.csv", "~45 KB", "For statistical analysis"])
                csv_folder.addChild(wide_item)

            self.file_tree.addTopLevelItem(csv_folder)
            csv_folder.setExpanded(True)

        # Excel Files
        if self.selected_formats.get('excel'):
            excel_folder = QTreeWidgetItem(["📁 Excel Workbooks"])
            excel_folder.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))

            for name, _, _ in datasets_to_export[:5]:  # Show first 5
                excel_item = QTreeWidgetItem([f"📊 {name}.xlsx", "~150 KB", "Multi-sheet workbook"])
                excel_folder.addChild(excel_item)

            if len(datasets_to_export) > 5:
                more_item = QTreeWidgetItem([f"... and {len(datasets_to_export) - 5} more", "", ""])
                more_item.setFont(0, QFont("Segoe UI", 9, QFont.Weight.Normal))
                excel_folder.addChild(more_item)

            self.file_tree.addTopLevelItem(excel_folder)
            excel_folder.setExpanded(True)

        # Plot Files
        if any([self.selected_formats.get('png'), self.selected_formats.get('svg'), self.selected_formats.get('pdf')]):
            plots_folder = QTreeWidgetItem(["📁 Plot Files"])
            plots_folder.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))

            plot_count = 0
            for name, _, _ in datasets_to_export[:3]:  # Show first 3
                if self.selected_formats.get('png'):
                    png_item = QTreeWidgetItem([f"🖼️ {name}_plot.png", "~200 KB", "Grain size plot"])
                    plots_folder.addChild(png_item)
                    plot_count += 1

            if len(datasets_to_export) > 3 or plot_count > 3:
                more_item = QTreeWidgetItem([f"... more plot files", "", ""])
                plots_folder.addChild(more_item)

            self.file_tree.addTopLevelItem(plots_folder)
            plots_folder.setExpanded(True)

        # JSON Files
        if self.selected_formats.get('json'):
            json_folder = QTreeWidgetItem(["📁 JSON Files"])
            json_folder.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))

            for name, _, _ in datasets_to_export[:3]:
                json_item = QTreeWidgetItem([f"📋 {name}.json", "~30 KB", "Structured data"])
                json_folder.addChild(json_item)

            if len(datasets_to_export) > 3:
                more_item = QTreeWidgetItem([f"... and {len(datasets_to_export) - 3} more", "", ""])
                json_folder.addChild(more_item)

            self.file_tree.addTopLevelItem(json_folder)
            json_folder.setExpanded(True)

    def update_summary_card(self):
        """Update the summary card showing export overview"""
        if not hasattr(self, 'summary_files_label'):
            return

        datasets_to_export = self._get_datasets_to_export()
        dataset_count = len(datasets_to_export)

        # Count files
        file_count = 0
        format_count = 0

        if self.selected_formats.get('csv_long'):
            file_count += 1
            format_count += 1
        if self.selected_formats.get('csv_wide'):
            file_count += 1
            format_count += 1
        if self.selected_formats.get('excel'):
            file_count += dataset_count
            format_count += 1
        if self.selected_formats.get('json'):
            file_count += dataset_count
            format_count += 1

        # Count plot files
        plot_formats = sum([
            self.selected_formats.get('png', False),
            self.selected_formats.get('svg', False),
            self.selected_formats.get('pdf', False)
        ])
        if plot_formats > 0:
            file_count += dataset_count * plot_formats
            format_count += plot_formats

        # Update summary label
        self.summary_files_label.setText(f"📦 You will export <b>{file_count} files</b> in <b>{format_count} formats</b>")

        # Update size estimate
        estimated_size = file_count * 50  # Rough estimate: 50 KB average
        if estimated_size < 1024:
            size_str = f"{estimated_size} KB"
        else:
            size_str = f"{estimated_size / 1024:.1f} MB"

        self.summary_size_label.setText(f"Estimated size: ~{size_str}")

    def _create_content_toggle(self, content_key: str, icon: str, label: str) -> QPushButton:
        """Create a compact toggle button for content selection"""
        btn = QPushButton(f"{icon} {label}")
        btn.setCheckable(True)
        btn.setChecked(self.content_enabled.get(content_key, True))
        btn.setMinimumHeight(28)
        btn.setMaximumHeight(28)
        btn.setFont(QFont("Segoe UI", 9))

        # Style for toggle button
        btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                border: 2px solid #ddd;
                border-radius: 4px;
                padding: 4px 10px;
                text-align: left;
            }
            QPushButton:checked {
                background-color: #e8f5e9;
                border-color: #6b8e23;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #eeeeee;
            }
        """)

        btn.clicked.connect(lambda checked: self._toggle_content(content_key, checked))

        return btn

    def _toggle_content(self, content_key: str, checked: bool):
        """Handle content toggle"""
        self.content_enabled[content_key] = checked
        self.update_file_tree()
        self.update_summary_card()

    def setup_ui(self):
        """Setup the export tab UI with 2-column layout"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # === TOP BAR: Dataset Scope + Output Directory + Include + Export Button ===
        top_bar = QFrame()
        top_bar.setFrameShape(QFrame.Shape.StyledPanel)
        top_bar.setStyleSheet("background-color: #f0f0f0; padding: 8px; border-radius: 4px;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setSpacing(12)

        # Dataset scope
        scope_label = QLabel("Export:")
        scope_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        top_layout.addWidget(scope_label)

        self.scope_group = QButtonGroup(self)
        self.scope_all = QRadioButton("All")
        self.scope_all.setChecked(True)
        self.scope_all.setFont(QFont("Segoe UI", 9))
        self.scope_current = QRadioButton("Current:")
        self.scope_current.setFont(QFont("Segoe UI", 9))
        self.current_dataset_combo = QComboBox()
        self.current_dataset_combo.setMinimumWidth(160)
        self.current_dataset_combo.setMaximumHeight(24)
        self.current_dataset_combo.setFont(QFont("Segoe UI", 9))

        self.all_datasets_label = QLabel("(0)")
        self.all_datasets_label.setFont(QFont("Segoe UI", 8))
        self.all_datasets_label.setStyleSheet("color: #666;")

        self.scope_group.addButton(self.scope_all)
        self.scope_group.addButton(self.scope_current)

        top_layout.addWidget(self.scope_all)
        top_layout.addWidget(self.all_datasets_label)
        top_layout.addWidget(self.scope_current)
        top_layout.addWidget(self.current_dataset_combo)

        # Add spacing
        top_layout.addSpacing(20)

        # Output directory - redesigned as a clearer section
        output_container = QFrame()
        output_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)
        output_layout = QHBoxLayout(output_container)
        output_layout.setContentsMargins(6, 2, 6, 2)
        output_layout.setSpacing(8)

        output_label = QLabel("📁 Output:")
        output_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        output_layout.addWidget(output_label)

        self.output_dir = QLineEdit()
        self.output_dir.setText(os.path.expanduser("~/Desktop"))
        self.output_dir.setReadOnly(True)
        self.output_dir.setMinimumWidth(250)
        self.output_dir.setMaximumHeight(24)
        self.output_dir.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                color: #333;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9px;
            }
        """)
        output_layout.addWidget(self.output_dir)

        browse_btn = QPushButton("Browse...")
        browse_btn.setMaximumHeight(24)
        browse_btn.setFont(QFont("Segoe UI", 8))
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #d2b48c;
                border: 1px solid #8b7355;
                border-radius: 3px;
                padding: 2px 10px;
            }
            QPushButton:hover {
                background-color: #ddbf94;
            }
        """)
        browse_btn.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(browse_btn)

        top_layout.addWidget(output_container)

        top_layout.addStretch()

        # Export button
        self.export_btn = QPushButton("🚀 Export Now")
        self.export_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.export_btn.setMinimumHeight(36)
        self.export_btn.setMinimumWidth(140)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b8e23;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #7ca02a;
            }
            QPushButton:pressed {
                background-color: #5a7a1e;
            }
        """)
        self.export_btn.clicked.connect(self.export_now)
        top_layout.addWidget(self.export_btn)

        main_layout.addWidget(top_bar)

        # === 2-Column Layout ===
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(8)

        # === LEFT COLUMN: Formats + Summary + File Tree (35%) ===
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Format cards section
        format_label = QLabel("📁 Select Formats")
        format_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        left_layout.addWidget(format_label)

        # Format cards container
        format_container = QWidget()
        self.formats_layout = QVBoxLayout(format_container)
        self.formats_layout.setSpacing(4)
        self.formats_layout.setContentsMargins(0, 0, 0, 0)

        # Add format cards (compact)
        self.formats_layout.addWidget(self._create_format_card(
            'csv_long', 'CSV Long', 'One row per K-value result', '📊'))
        self.formats_layout.addWidget(self._create_format_card(
            'csv_wide', 'CSV Wide', 'For statistical analysis', '📈'))
        self.formats_layout.addWidget(self._create_format_card(
            'excel', 'Excel', 'Multi-sheet per dataset', '📗'))
        self.formats_layout.addWidget(self._create_format_card(
            'json', 'JSON', 'Structured data export', '📋'))
        self.formats_layout.addWidget(self._create_format_card(
            'png', 'PNG', 'High-resolution images', '🖼️'))
        self.formats_layout.addWidget(self._create_format_card(
            'svg', 'SVG', 'Vector graphics', '🎨'))
        self.formats_layout.addWidget(self._create_format_card(
            'pdf', 'PDF', 'Publication ready', '📄'))

        left_layout.addWidget(format_container)

        # Summary card
        summary_card = QFrame()
        summary_card.setFrameShape(QFrame.Shape.StyledPanel)
        summary_card.setStyleSheet("""
            QFrame {
                background-color: #e8f5e9;
                border: 2px solid #6b8e23;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setSpacing(3)
        summary_layout.setContentsMargins(8, 6, 8, 6)

        self.summary_files_label = QLabel("📦 You will export <b>0 files</b>")
        self.summary_files_label.setFont(QFont("Segoe UI", 10))
        self.summary_size_label = QLabel("Estimated size: ~0 KB")
        self.summary_size_label.setFont(QFont("Segoe UI", 9))
        self.summary_size_label.setStyleSheet("color: #666;")

        summary_layout.addWidget(self.summary_files_label)
        summary_layout.addWidget(self.summary_size_label)

        left_layout.addWidget(summary_card)

        # File tree
        tree_label = QLabel("📄 Files to be Created")
        tree_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        left_layout.addWidget(tree_label)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Filename", "Size", "Description"])
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setRootIsDecorated(True)
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.file_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        left_layout.addWidget(self.file_tree, 1)  # Give file tree stretch factor

        # === RIGHT COLUMN: Preview Tabs (65%) ===
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)

        preview_label = QLabel("📊 Data Preview")
        preview_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        right_layout.addWidget(preview_label)

        self.preview_tabs = QTabWidget()
        self.preview_tabs.setDocumentMode(True)

        # K-Results Preview
        self.k_results_preview = QTableWidget()
        self.k_results_preview.setAlternatingRowColors(True)
        self.k_results_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_tabs.addTab(self.k_results_preview, "K-Values Data")

        # Format Preview
        self.format_preview = QTextEdit()
        self.format_preview.setReadOnly(True)
        self.format_preview.setFont(QFont("Courier", 9))
        self.preview_tabs.addTab(self.format_preview, "Export Format")

        # Grain Data Preview
        self.grain_data_preview = QTableWidget()
        self.grain_data_preview.setAlternatingRowColors(True)
        self.grain_data_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_tabs.addTab(self.grain_data_preview, "Grain Size Data")

        right_layout.addWidget(self.preview_tabs)

        # Add columns to layout with proportions
        columns_layout.addWidget(left_column, 35)    # 35%
        columns_layout.addWidget(right_column, 65)   # 65%

        main_layout.addLayout(columns_layout, 1)  # Takes most space

        # Connect scope signals
        self.scope_all.toggled.connect(self.update_file_tree)
        self.scope_all.toggled.connect(self.update_summary_card)
        self.scope_all.toggled.connect(self.update_preview)
        self.scope_current.toggled.connect(self.update_file_tree)
        self.scope_current.toggled.connect(self.update_summary_card)
        self.scope_current.toggled.connect(self.update_preview)
        self.current_dataset_combo.currentIndexChanged.connect(self.update_file_tree)
        self.current_dataset_combo.currentIndexChanged.connect(self.update_summary_card)
        self.current_dataset_combo.currentIndexChanged.connect(self.update_preview)

        # Initial update
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def update_preview(self):
        """Update preview tabs based on selected formats"""
        # Clear all tabs
        self.preview_tabs.clear()

        datasets_to_export = self._get_datasets_to_export()

        # Add tabs only for selected formats
        if self.selected_formats.get('csv_long'):
            self._add_csv_long_preview_tab(datasets_to_export)

        if self.selected_formats.get('csv_wide'):
            self._add_csv_wide_preview_tab(datasets_to_export)

        if self.selected_formats.get('excel'):
            self._add_excel_preview_tab(datasets_to_export)

        if self.selected_formats.get('json'):
            self._add_json_preview_tab(datasets_to_export)

        # Add plot preview if any plot format is selected
        if self.selected_formats.get('png') or self.selected_formats.get('svg') or self.selected_formats.get('pdf'):
            self._add_plot_preview_tab(datasets_to_export)

        # If no formats selected, show help
        if self.preview_tabs.count() == 0:
            self._add_help_tab()

    def _add_csv_long_preview_tab(self, datasets_to_export):
        """Add CSV Long format preview tab"""
        preview = QTableWidget()
        preview.setAlternatingRowColors(True)
        preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Set up columns - match actual CSV export exactly
        headers = [
            "Sample Name", "Method", "K (m/s)", "K (cm/s)", "K (m/d)", "Status", "Formula",
            "Temperature (°C)", "Porosity",
            "D10 (mm)", "D50 (mm)", "D60 (mm)", "Cu", "Cc"
        ]
        preview.setColumnCount(len(headers))
        preview.setHorizontalHeaderLabels(headers)

        # Count total rows
        total_rows = 0
        for name, dataset, results in datasets_to_export:
            if results:
                total_rows += len([r for r in results if r.k_value is not None])

        # Limit to first 50 rows for preview
        max_preview_rows = min(total_rows, 50)
        preview.setRowCount(max_preview_rows)

        # Populate table
        row = 0
        for name, dataset, results in datasets_to_export:
            if results:
                for result in results:
                    if result.k_value is not None and row < max_preview_rows:
                        # Get all grain size parameters
                        d10 = dataset.get_d10() if hasattr(dataset, 'get_d10') else 0
                        d50 = dataset.get_d50() if hasattr(dataset, 'get_d50') else 0
                        d60 = dataset.get_d60() if hasattr(dataset, 'get_d60') else 0
                        cu = dataset.get_uniformity_coefficient() if hasattr(dataset, 'get_uniformity_coefficient') else 0
                        cc = dataset.get_coefficient_of_curvature() if hasattr(dataset, 'get_coefficient_of_curvature') else 0
                        status = result.status.value if hasattr(result.status, 'value') else str(result.status)
                        formula = result.formula if hasattr(result, 'formula') else ""

                        # Sample Name, Method, K values, Status, Formula
                        preview.setItem(row, 0, QTableWidgetItem(name))
                        preview.setItem(row, 1, QTableWidgetItem(result.method_name))
                        preview.setItem(row, 2, QTableWidgetItem(f"{result.k_value:.3e}"))
                        preview.setItem(row, 3, QTableWidgetItem(f"{result.k_value * 100:.3e}"))
                        preview.setItem(row, 4, QTableWidgetItem(f"{result.k_value * 86400:.2f}"))
                        preview.setItem(row, 5, QTableWidgetItem(status))
                        preview.setItem(row, 6, QTableWidgetItem(formula))

                        # Temperature and Porosity
                        preview.setItem(row, 7, QTableWidgetItem(str(dataset.temperature)))
                        preview.setItem(row, 8, QTableWidgetItem(f"{result.porosity:.3f}"))

                        # Grain size parameters
                        preview.setItem(row, 9, QTableWidgetItem(f"{d10:.4f}"))
                        preview.setItem(row, 10, QTableWidgetItem(f"{d50:.4f}"))
                        preview.setItem(row, 11, QTableWidgetItem(f"{d60:.4f}"))
                        preview.setItem(row, 12, QTableWidgetItem(f"{cu:.2f}"))
                        preview.setItem(row, 13, QTableWidgetItem(f"{cc:.2f}"))

                        row += 1

        # Auto-resize columns
        preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        preview.horizontalHeader().setStretchLastSection(False)

        self.preview_tabs.addTab(preview, f"📊 CSV Long ({max_preview_rows} rows)" if total_rows > max_preview_rows else "📊 CSV Long")

    def _add_csv_wide_preview_tab(self, datasets_to_export):
        """Add CSV Wide format preview tab"""
        preview = QTableWidget()
        preview.setAlternatingRowColors(True)
        preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Get unique methods from first dataset
        method_names = []
        if datasets_to_export and datasets_to_export[0][2]:
            method_names = [r.method_name for r in datasets_to_export[0][2]]

        # Build headers - match actual CSV Wide export exactly (92 columns!)
        headers = [
            "Sample Name", "Temp (°C)", "Porosity",
            "D5 (mm)", "D10 (mm)", "D16 (mm)", "D17 (mm)", "D20 (mm)", "D30 (mm)",
            "D50 (mm)", "D60 (mm)", "D84 (mm)", "D95 (mm)",
            "Cu", "Cc"
        ]

        # Add K-values in m/s for all methods
        for method in method_names:
            headers.append(f"K_{method}\n(m/s)")

        # Add K-values in cm/s for all methods
        for method in method_names:
            headers.append(f"K_{method}\n(cm/s)")

        # Add K-values in m/d for all methods
        for method in method_names:
            headers.append(f"K_{method}\n(m/d)")

        # Add status for all methods
        for method in method_names:
            headers.append(f"Status_{method}")

        # Add statistical summaries
        headers.extend([
            "K_Mean (m/s)", "K_Median (m/s)", "K_StdDev (m/s)", "K_Min (m/s)", "K_Max (m/s)",
            "K_Mean (cm/s)", "K_Median (cm/s)", "K_Min (cm/s)", "K_Max (cm/s)",
            "K_Mean (m/d)", "K_Median (m/d)", "K_Min (m/d)", "K_Max (m/d)",
            "Valid Methods"
        ])

        preview.setColumnCount(len(headers))
        preview.setHorizontalHeaderLabels(headers)

        # Limit to first 20 datasets for preview
        max_preview_rows = min(len(datasets_to_export), 20)
        preview.setRowCount(max_preview_rows)

        # Populate table
        for row, (name, dataset, results) in enumerate(datasets_to_export[:max_preview_rows]):
            preview.setItem(row, 0, QTableWidgetItem(name))
            preview.setItem(row, 1, QTableWidgetItem(str(dataset.temperature)))
            preview.setItem(row, 2, QTableWidgetItem(f"{dataset.current_porosity or dataset.porosity:.3f}"))

            # Get ALL percentiles
            d5 = dataset.get_percentile(5) if hasattr(dataset, 'get_percentile') else 0
            d10 = dataset.get_d10() if hasattr(dataset, 'get_d10') else 0
            d16 = dataset.get_percentile(16) if hasattr(dataset, 'get_percentile') else 0
            d17 = dataset.get_percentile(17) if hasattr(dataset, 'get_percentile') else 0
            d20 = dataset.get_d20() if hasattr(dataset, 'get_d20') else 0
            d30 = dataset.get_d30() if hasattr(dataset, 'get_d30') else 0
            d50 = dataset.get_d50() if hasattr(dataset, 'get_d50') else 0
            d60 = dataset.get_d60() if hasattr(dataset, 'get_d60') else 0
            d84 = dataset.get_percentile(84) if hasattr(dataset, 'get_percentile') else 0
            d95 = dataset.get_percentile(95) if hasattr(dataset, 'get_percentile') else 0
            cu = dataset.get_uniformity_coefficient() if hasattr(dataset, 'get_uniformity_coefficient') else 0
            cc = dataset.get_coefficient_of_curvature() if hasattr(dataset, 'get_coefficient_of_curvature') else 0

            # Fill all percentile columns
            preview.setItem(row, 3, QTableWidgetItem(f"{d5:.4f}"))
            preview.setItem(row, 4, QTableWidgetItem(f"{d10:.4f}"))
            preview.setItem(row, 5, QTableWidgetItem(f"{d16:.4f}"))
            preview.setItem(row, 6, QTableWidgetItem(f"{d17:.4f}"))
            preview.setItem(row, 7, QTableWidgetItem(f"{d20:.4f}"))
            preview.setItem(row, 8, QTableWidgetItem(f"{d30:.4f}"))
            preview.setItem(row, 9, QTableWidgetItem(f"{d50:.4f}"))
            preview.setItem(row, 10, QTableWidgetItem(f"{d60:.4f}"))
            preview.setItem(row, 11, QTableWidgetItem(f"{d84:.4f}"))
            preview.setItem(row, 12, QTableWidgetItem(f"{d95:.4f}"))
            preview.setItem(row, 13, QTableWidgetItem(f"{cu:.2f}"))
            preview.setItem(row, 14, QTableWidgetItem(f"{cc:.2f}"))

            # Add K-values for each method (in all 3 units) + status
            method_dict = {r.method_name: r for r in results} if results else {}

            # K-values in m/s
            for col_idx, method in enumerate(method_names):
                if method in method_dict and method_dict[method].k_value:
                    preview.setItem(row, 15 + col_idx, QTableWidgetItem(f"{method_dict[method].k_value:.3e}"))
                else:
                    preview.setItem(row, 15 + col_idx, QTableWidgetItem("-"))

            # K-values in cm/s
            col_offset = 15 + len(method_names)
            for col_idx, method in enumerate(method_names):
                if method in method_dict and method_dict[method].k_value:
                    k_cm_s = method_dict[method].k_value * 100
                    preview.setItem(row, col_offset + col_idx, QTableWidgetItem(f"{k_cm_s:.3e}"))
                else:
                    preview.setItem(row, col_offset + col_idx, QTableWidgetItem("-"))

            # K-values in m/d
            col_offset = 15 + 2 * len(method_names)
            for col_idx, method in enumerate(method_names):
                if method in method_dict and method_dict[method].k_value:
                    k_m_d = method_dict[method].k_value * 86400
                    preview.setItem(row, col_offset + col_idx, QTableWidgetItem(f"{k_m_d:.2f}"))
                else:
                    preview.setItem(row, col_offset + col_idx, QTableWidgetItem("-"))

            # Status flags
            col_offset = 15 + 3 * len(method_names)
            for col_idx, method in enumerate(method_names):
                if method in method_dict:
                    status = method_dict[method].status.value if hasattr(method_dict[method].status, 'value') else str(method_dict[method].status)
                    preview.setItem(row, col_offset + col_idx, QTableWidgetItem(status))
                else:
                    preview.setItem(row, col_offset + col_idx, QTableWidgetItem("-"))

            # Statistical summaries
            import numpy as np
            valid_k_values = [r.k_value for r in results if r.k_value is not None]
            stats_col_offset = 15 + 4 * len(method_names)

            if valid_k_values:
                # K statistics in m/s
                preview.setItem(row, stats_col_offset, QTableWidgetItem(f"{np.mean(valid_k_values):.3e}"))
                preview.setItem(row, stats_col_offset + 1, QTableWidgetItem(f"{np.median(valid_k_values):.3e}"))
                preview.setItem(row, stats_col_offset + 2, QTableWidgetItem(f"{np.std(valid_k_values):.3e}"))
                preview.setItem(row, stats_col_offset + 3, QTableWidgetItem(f"{np.min(valid_k_values):.3e}"))
                preview.setItem(row, stats_col_offset + 4, QTableWidgetItem(f"{np.max(valid_k_values):.3e}"))

                # K statistics in cm/s
                valid_k_cm_s = [k * 100 for k in valid_k_values]
                preview.setItem(row, stats_col_offset + 5, QTableWidgetItem(f"{np.mean(valid_k_cm_s):.3e}"))
                preview.setItem(row, stats_col_offset + 6, QTableWidgetItem(f"{np.median(valid_k_cm_s):.3e}"))
                preview.setItem(row, stats_col_offset + 7, QTableWidgetItem(f"{np.min(valid_k_cm_s):.3e}"))
                preview.setItem(row, stats_col_offset + 8, QTableWidgetItem(f"{np.max(valid_k_cm_s):.3e}"))

                # K statistics in m/d
                valid_k_m_d = [k * 86400 for k in valid_k_values]
                preview.setItem(row, stats_col_offset + 9, QTableWidgetItem(f"{np.mean(valid_k_m_d):.2f}"))
                preview.setItem(row, stats_col_offset + 10, QTableWidgetItem(f"{np.median(valid_k_m_d):.2f}"))
                preview.setItem(row, stats_col_offset + 11, QTableWidgetItem(f"{np.min(valid_k_m_d):.2f}"))
                preview.setItem(row, stats_col_offset + 12, QTableWidgetItem(f"{np.max(valid_k_m_d):.2f}"))

                # Valid methods count
                preview.setItem(row, stats_col_offset + 13, QTableWidgetItem(str(len(valid_k_values))))
            else:
                # Fill with dashes if no valid results
                for i in range(14):
                    preview.setItem(row, stats_col_offset + i, QTableWidgetItem("-"))

        # Auto-resize columns
        preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        preview.horizontalHeader().setStretchLastSection(False)

        self.preview_tabs.addTab(preview, f"📈 CSV Wide ({max_preview_rows} datasets)" if len(datasets_to_export) > max_preview_rows else "📈 CSV Wide")

    def _add_excel_preview_tab(self, datasets_to_export):
        """Add Excel format preview tab"""
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setFont(QFont("Segoe UI", 9))

        text = []
        if datasets_to_export:
            name = datasets_to_export[0][0]
            text.append(f"Example workbook: {name}.xlsx")
            text.append("")
            text.append("Sheets:")
            text.append("  • Summary - Dataset overview and key parameters")
            text.append("  • Grain_Size_Data - Particle size distribution")
            text.append("  • Percentiles - D10, D20, D30, D50, D60, etc.")
            text.append("  • K_Values - All calculation methods and results")
            text.append("  • Statistics - Summary statistics")
            text.append("")
            text.append(f"Total workbooks to create: {len(datasets_to_export)}")

        preview.setPlainText("\n".join(text))
        self.preview_tabs.addTab(preview, "📗 Excel")

    def _add_json_preview_tab(self, datasets_to_export):
        """Add JSON format preview tab"""
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setFont(QFont("Courier", 9))

        text = []
        if datasets_to_export:
            name = datasets_to_export[0][0]
            text.append(f"Example: {name}.json")
            text.append("")
            text.append("{")
            text.append('  "sample_name": "' + name + '",')
            text.append('  "temperature": 10.0,')
            text.append('  "porosity": 0.35,')
            text.append('  "grain_size_data": {')
            text.append('    "particle_sizes": [...],')
            text.append('    "percent_passing": [...]')
            text.append('  },')
            text.append('  "k_values": [')
            text.append('    {')
            text.append('      "method": "Hazen",')
            text.append('      "k_value": 1.23e-4,')
            text.append('      "status": "valid"')
            text.append('    },')
            text.append('    ...')
            text.append('  ],')
            text.append('  "statistics": { ... }')
            text.append("}")
            text.append("")
            text.append(f"Total JSON files to create: {len(datasets_to_export)}")

        preview.setPlainText("\n".join(text))
        self.preview_tabs.addTab(preview, "📋 JSON")

    def _add_plot_preview_tab(self, datasets_to_export):
        """Add plot preview tab"""
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setFont(QFont("Segoe UI", 9))

        text = []
        plot_formats = []
        if self.selected_formats.get('png'):
            plot_formats.append("PNG")
        if self.selected_formats.get('svg'):
            plot_formats.append("SVG")
        if self.selected_formats.get('pdf'):
            plot_formats.append("PDF")

        text.append(f"Format(s): {', '.join(plot_formats)}")
        text.append("")
        text.append("Each plot will show:")
        text.append("  • Cumulative % passing curve")
        text.append("  • Sieve sizes and percentiles marked")
        text.append("  • USCS soil classification")
        text.append("  • Sample name and parameters")
        text.append("")
        total_plots = len(datasets_to_export) * len(plot_formats)
        text.append(f"Total plot files to create: {total_plots}")
        text.append(f"  ({len(datasets_to_export)} datasets × {len(plot_formats)} format(s))")

        preview.setPlainText("\n".join(text))
        self.preview_tabs.addTab(preview, "📈 Plots")

    def _add_help_tab(self):
        """Add help tab when no formats are selected"""
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setFont(QFont("Segoe UI", 10))

        text = []
        text.append("📁 Select export formats from the cards on the left")
        text.append("")
        text.append("Available formats:")
        text.append("")
        text.append("  📊 CSV Long - One row per K-value result")
        text.append("     Best for: Data analysis, importing into other tools")
        text.append("")
        text.append("  📈 CSV Wide - One row per dataset, columns for each method")
        text.append("     Best for: Statistical analysis, method comparison")
        text.append("")
        text.append("  📗 Excel - Multi-sheet workbooks (one per dataset)")
        text.append("     Best for: Comprehensive reports, sharing results")
        text.append("")
        text.append("  📋 JSON - Structured data export")
        text.append("     Best for: API integration, web applications")
        text.append("")
        text.append("  🖼️ PNG - High-resolution plot images")
        text.append("     Best for: Presentations, reports")
        text.append("")
        text.append("  🎨 SVG - Vector graphics plots")
        text.append("     Best for: Scalable graphics, editing")
        text.append("")
        text.append("  📄 PDF - Publication-ready plots")
        text.append("     Best for: Documents, archiving")

        preview.setPlainText("\n".join(text))
        self.preview_tabs.addTab(preview, "ℹ️ Help")

    def _old_setup_ui_backup(self):
        """OLD setup_ui - kept for reference during transition"""
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
        self.all_datasets_label.setText(f"({count} dataset{'s' if count != 1 else ''})")

        # Enable/disable scope options
        has_datasets = count > 0
        self.scope_current.setEnabled(has_datasets)
        self.scope_all.setEnabled(has_datasets)
        self.current_dataset_combo.setEnabled(has_datasets)
        self.export_btn.setEnabled(has_datasets)

        # Update preview and summary
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def update_format_options(self):
        """No longer needed in new design - format cards handle their own state"""
        pass

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
        """No longer needed - using simple All/Current selection"""
        pass

    def _old_update_preview(self):
        """OLD update_preview - no longer used"""
        pass

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

        # Show CSV Long Format preview if selected
        if self.selected_formats.get('csv_long'):
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

        # Show CSV Wide Format preview if selected
        if self.selected_formats.get('csv_wide'):
            if preview_text:  # Add separator if long format was shown
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

        # Show Excel preview if selected
        if self.selected_formats.get('excel'):
            if preview_text:
                preview_text.append("")
                preview_text.append("=" * 60)
                preview_text.append("")

            preview_text.append("=== EXCEL WORKBOOK (PER DATASET) ===")
            preview_text.append("")

            if datasets_to_export:
                name, dataset, results = datasets_to_export[0]
                preview_text.append(f"Example workbook: {name}.xlsx")
                preview_text.append("  Sheets:")
                preview_text.append("    - Summary (overview)")
                preview_text.append("    - Grain_Size_Data (particle distribution)")
                preview_text.append("    - Percentiles (D10, D50, etc.)")
                preview_text.append("    - K_Values (all calculation methods)")
                preview_text.append("    - Statistics (summary stats)")
                preview_text.append("")
                preview_text.append(f"Total: {len(datasets_to_export)} workbook(s) will be created")

        # Show JSON preview if selected
        if self.selected_formats.get('json'):
            if preview_text:
                preview_text.append("")
                preview_text.append("=" * 60)
                preview_text.append("")

            preview_text.append("=== JSON FILES ===")
            preview_text.append("")
            if datasets_to_export:
                name, dataset, results = datasets_to_export[0]
                preview_text.append(f"Example: {name}.json")
                preview_text.append("{")
                preview_text.append('  "sample_name": "' + name + '",')
                preview_text.append('  "grain_size_data": { ... },')
                preview_text.append('  "k_values": [')
                preview_text.append('    { "method": "...", "k_value": ..., "status": "..." },')
                preview_text.append('    ...')
                preview_text.append('  ],')
                preview_text.append('  "statistics": { ... }')
                preview_text.append("}")
                preview_text.append("")
                preview_text.append(f"Total: {len(datasets_to_export)} JSON file(s) will be created")

        # Show plot formats preview if selected
        plot_formats = []
        if self.selected_formats.get('png'):
            plot_formats.append("PNG")
        if self.selected_formats.get('svg'):
            plot_formats.append("SVG")
        if self.selected_formats.get('pdf'):
            plot_formats.append("PDF")

        if plot_formats:
            if preview_text:
                preview_text.append("")
                preview_text.append("=" * 60)
                preview_text.append("")

            preview_text.append(f"=== PLOT FILES ({', '.join(plot_formats)}) ===")
            preview_text.append("")
            preview_text.append("Each dataset will have a grain size distribution plot showing:")
            preview_text.append("  - Cumulative % passing curve")
            preview_text.append("  - Sieve sizes and percentiles marked")
            preview_text.append("  - USCS classification")
            preview_text.append("")
            total_plots = len(datasets_to_export) * len(plot_formats)
            preview_text.append(f"Total: {total_plots} plot file(s) will be created")
            preview_text.append(f"  ({len(datasets_to_export)} datasets × {len(plot_formats)} format(s))")

        if not preview_text:
            preview_text.append("Click format cards on the left to select what to export")
            preview_text.append("")
            preview_text.append("Available formats:")
            preview_text.append("  📊 CSV Long - One row per K-value result")
            preview_text.append("  📈 CSV Wide - Statistical analysis format")
            preview_text.append("  📗 Excel - Multi-sheet workbooks")
            preview_text.append("  📋 JSON - Structured data")
            preview_text.append("  🖼️ PNG - High-resolution plots")
            preview_text.append("  🎨 SVG - Vector plots")
            preview_text.append("  📄 PDF - Publication-ready plots")

        self.format_preview.setPlainText("\n".join(preview_text))

    def _update_files_preview(self):
        """No longer used - file tree in middle column shows this info"""
        pass

    def _old_update_files_preview(self):
        """OLD _update_files_preview - kept for reference"""
        datasets_to_export = self._get_datasets_to_export()
        config = self._build_export_config()

        headers = ["Filename", "Type", "Size Estimate", "Description"]
        # self.files_preview.setColumnCount(len(headers))
        # self.files_preview.setHorizontalHeaderLabels(headers)

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

        # Use new selected_formats dict
        if self.selected_formats.get('csv_long'):
            preview_lines.append(f"  • CSV Long Format: 1 file")
            file_count += 1
        if self.selected_formats.get('csv_wide'):
            preview_lines.append(f"  • CSV Wide Format: 1 file")
            file_count += 1

        if self.selected_formats.get('excel'):
            preview_lines.append(f"  • Excel workbooks: {total_datasets} files (one per dataset)")
            file_count += total_datasets

        if self.selected_formats.get('json'):
            preview_lines.append(f"  • JSON files: {total_datasets} files")
            file_count += total_datasets

        if self.content_enabled.get('plots', True):
            plot_formats = sum([
                self.selected_formats.get('png', False),
                self.selected_formats.get('svg', False),
                self.selected_formats.get('pdf', False)
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

        preview_lines.append("")

        # Content selection - use new content_enabled dict
        preview_lines.append("📋 CONTENT INCLUDED")
        preview_lines.append("-" * 60)
        content_items = []
        if self.content_enabled.get('grain_data', True):
            content_items.append("Grain size distribution data")
        if self.content_enabled.get('k_values', True):
            content_items.append("K-value results (all methods)")
        if self.content_enabled.get('statistics', True):
            content_items.append("Statistical summaries")
        if self.content_enabled.get('plots', True):
            content_items.append("Plots/figures")

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
        if self.content_enabled.get('k_values', True):
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

        return []

    def _build_export_config(self) -> Dict:
        """Build export configuration dictionary"""
        config = {
            # Formats - using new selected_formats dict
            'csv': self.selected_formats.get('csv_long') or self.selected_formats.get('csv_wide'),
            'csv_mode': 'combined',  # Always combined in new design
            'csv_long': self.selected_formats.get('csv_long', False),
            'csv_wide': self.selected_formats.get('csv_wide', False),

            'excel': self.selected_formats.get('excel', False),
            'excel_mode': 'per_dataset',  # Default mode

            'json': self.selected_formats.get('json', False),

            'png': self.selected_formats.get('png', False),
            'png_dpi': 300,  # Default DPI

            'svg': self.selected_formats.get('svg', False),
            'pdf_plot': self.selected_formats.get('pdf', False),

            # Content - using new content_enabled dict
            'grain_distribution': self.content_enabled.get('grain_data', True),
            'percentiles': self.content_enabled.get('grain_data', True),
            'gradation': self.content_enabled.get('grain_data', True),
            'classification': self.content_enabled.get('grain_data', True),
            'k_values': self.content_enabled.get('k_values', True),
            'statistics': self.content_enabled.get('statistics', True),
            'plots': self.content_enabled.get('plots', True),
            'formulas': False,  # Not exposed in new UI
            'validation': False,  # Not exposed in new UI

            # Output
            'output_dir': self.output_dir.text(),
            'filename_template': '{sample_name}_results_{date}',  # Default template
        }

        return config
