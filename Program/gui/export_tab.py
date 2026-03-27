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
from typing import Any, Dict, List, Optional
import os
from datetime import datetime

from data_loader import GrainSizeData
from k_calculations_v2 import KCalculationResult
from grain_classification import ISO14688


class ExportTab(QWidget):
    """Unified export interface for all data formats"""

    # Signal emitted when export is started/completed
    export_started = pyqtSignal()
    export_completed = pyqtSignal(str)  # Export path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scheme = ISO14688
        self.datasets = []  # List of (name, GrainSizeData, List[KCalculationResult])
        self.plot_figures: List[Any] = []

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

        # Content toggles (legacy - kept for backward compatibility)
        self.content_enabled = {
            'grain_data': True,
            'k_values': True,
            'statistics': True,
            'plots': True
        }

        # Initialize granular content selection
        self._init_content_selection()

        self.setup_ui()

    @staticmethod
    def _fmt(value, fmt: str, dash: str = "-") -> str:
        """Safely format numbers that may be None."""
        try:
            if value is None:
                return dash
            return format(value, fmt)
        except Exception:
            return dash

    def _init_content_selection(self):
        """Initialize granular content selection structure with smart defaults"""
        self.content_selection = {
            # === GRAIN SIZE DATA ===
            'grain_size': {
                'enabled': True,
                'items': {
                    'raw_distribution': True,  # particle_sizes + percent_passing arrays
                    'percentiles': {
                        'enabled': True,
                        'items': {
                            'd5': False,   # Less commonly used
                            'd10': True,   # Essential
                            'd16': False,
                            'd17': False,
                            'd20': True,
                            'd30': True,
                            'd50': True,   # Essential
                            'd60': True,   # Essential
                            'd84': False,
                            'd95': False,
                        }
                    },
                    'gradation': {
                        'enabled': True,
                        'items': {
                            'cu': True,  # Uniformity coefficient
                            'cc': True,  # Coefficient of curvature
                        }
                    },
                    'classification': True,  # USCS soil classification
                }
            },

            # === K-VALUE RESULTS ===
            'k_values': {
                'enabled': True,
                'filter_mode': 'all',  # 'all', 'category', 'individual'
                'categories': {
                    'hazen_based': True,           # Hazen, Hazen_1892
                    'porosity_dependent': True,    # Slichter, Kozeny-Carman, Zunker, Zamarin, Barr
                    'uniformity_dependent': True,  # Beyer
                    'empirical': True,             # USBR, Alyamani-Sen, Chapuis, Shepherd, Terzaghi, Kruger, Krumbein-Monk
                    'temperature_corrected': True, # Sauerbrei
                },
                'individual_methods': {
                    'Hazen': True,
                    'Hazen_1892': True,
                    'Slichter': True,
                    'Terzaghi': True,
                    'Beyer': True,
                    'Sauerbrei': True,
                    'Kruger': True,
                    'Kozeny-Carman': True,
                    'Zunker': True,
                    'Zamarin': True,
                    'USBR': True,
                    'Barr': True,
                    'Alyamani-Sen': True,
                    'Chapuis': True,
                    'Shepherd': True,
                    'Krumbein-Monk': True,
                },
                'include_formulas': False,      # Reduces clutter by default
                'include_validation': False,    # Reduces clutter by default
                'units': {
                    'm_s': True,   # meters/second
                    'cm_s': True,  # centimeters/second
                    'm_d': True,   # meters/day
                }
            },

            # === STATISTICAL SUMMARIES ===
            'statistics': {
                'enabled': True,
                'items': {
                    'k_value_stats': {
                        'enabled': True,
                        'items': {
                            'mean': True,
                            'median': True,
                            'std_dev': True,
                            'min': True,
                            'max': True,
                            'valid_count': True,
                        }
                    },
                    'grain_size_stats': True,  # Summary of percentiles/gradation
                }
            },

            # === METADATA ===
            'metadata': {
                'enabled': True,
                'items': {
                    'sample_info': True,        # name, date
                    'environmental': True,      # temperature, porosity
                    'processing_notes': False,  # comments (often empty)
                    'export_timestamp': True,
                    'software_version': False,  # Not commonly needed
                }
            },

            # === PLOTS/FIGURES ===
            'plots': {
                'enabled': True,
                'items': {
                    'grain_size_curve': True,
                    'k_value_comparison': False,      # Advanced feature
                    'statistical_boxplots': False,    # Advanced feature
                    'include_legend': True,
                    'include_grid': True,
                }
            }
        }

    def _create_format_card(self, format_key: str, title: str, description: str, icon_text: str) -> QPushButton:
        """Create a compact clickable format selection card"""
        card = QPushButton()
        card.setCheckable(True)
        card.setChecked(self.selected_formats.get(format_key, False))
        card.setObjectName(f"format_card_{format_key}")
        card.setMinimumHeight(36)
        card.setMaximumHeight(40)
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        # Store format key as property
        card.setProperty("format_key", format_key)

        # Create layout for card contents
        card_layout = QHBoxLayout(card)
        card_layout.setSpacing(6)
        card_layout.setContentsMargins(6, 4, 6, 4)

        # Icon
        icon_label = QLabel(icon_text)
        icon_label.setFont(QFont("Segoe UI", 12))
        icon_label.setFixedWidth(24)
        card_layout.addWidget(icon_label)

        # Title (no description to save space)
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
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

    def _create_content_selection_panel(self) -> QWidget:
        """Create collapsible content selection panel"""
        # Main container
        content_panel = QFrame()
        content_panel.setFrameShape(QFrame.Shape.StyledPanel)
        content_panel.setStyleSheet("""
            QFrame {
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 4px;
            }
        """)

        panel_layout = QVBoxLayout(content_panel)
        panel_layout.setContentsMargins(6, 6, 6, 6)
        panel_layout.setSpacing(6)

        # Header with collapse button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        header_label = QLabel("📋 Content Selection")
        header_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        self.content_collapse_btn = QToolButton()
        self.content_collapse_btn.setText("▼")
        self.content_collapse_btn.setMaximumSize(20, 20)
        self.content_collapse_btn.setStyleSheet("""
            QToolButton {
                border: none;
                font-size: 10px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
                border-radius: 3px;
            }
        """)
        self.content_collapse_btn.clicked.connect(self._toggle_content_panel_collapse)
        header_layout.addWidget(self.content_collapse_btn)

        panel_layout.addLayout(header_layout)

        # Content area (collapsible)
        self.content_area = QWidget()
        content_area_layout = QVBoxLayout(self.content_area)
        content_area_layout.setContentsMargins(0, 0, 0, 0)
        content_area_layout.setSpacing(8)

        # === GRAIN SIZE DATA ===
        grain_size_group = self._create_grain_size_category()
        content_area_layout.addWidget(grain_size_group)

        # === K-VALUE RESULTS ===
        k_values_group = self._create_content_category(
            "🔢 K-Value Results",
            [
                ("all_methods", "All calculation methods (16)"),
                ("include_formulas", "Include formulas"),
                ("include_validation", "Include validation messages"),
                ("units_group", "Units: m/s, cm/s, m/d")
            ],
            'k_values'
        )
        content_area_layout.addWidget(k_values_group)

        # === STATISTICS ===
        stats_group = self._create_content_category(
            "📊 Statistical Summaries",
            [
                ("k_value_stats", "K-value statistics (mean, median, std, etc.)"),
                ("grain_size_stats", "Grain size summary")
            ],
            'statistics'
        )
        content_area_layout.addWidget(stats_group)

        # === METADATA ===
        metadata_group = self._create_content_category(
            "🏷️ Metadata",
            [
                ("sample_info", "Sample information"),
                ("environmental", "Environmental parameters (T, n)"),
                ("export_timestamp", "Export timestamp")
            ],
            'metadata'
        )
        content_area_layout.addWidget(metadata_group)

        # === PLOTS ===
        plots_group = self._create_content_category(
            "🎨 Plots/Figures",
            [
                ("grain_size_curve", "Grain size distribution curve"),
                ("include_legend", "Include legend"),
                ("include_grid", "Include grid lines")
            ],
            'plots'
        )
        content_area_layout.addWidget(plots_group)

        # Quick actions
        quick_actions = QHBoxLayout()
        quick_actions.setSpacing(4)

        select_all_btn = QPushButton("Select All")
        select_all_btn.setMaximumHeight(24)
        select_all_btn.setFont(QFont("Segoe UI", 8))
        select_all_btn.clicked.connect(self._select_all_content)
        quick_actions.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setMaximumHeight(24)
        deselect_all_btn.setFont(QFont("Segoe UI", 8))
        deselect_all_btn.clicked.connect(self._deselect_all_content)
        quick_actions.addWidget(deselect_all_btn)

        reset_btn = QPushButton("Reset Defaults")
        reset_btn.setMaximumHeight(24)
        reset_btn.setFont(QFont("Segoe UI", 8))
        reset_btn.clicked.connect(self._reset_content_defaults)
        quick_actions.addWidget(reset_btn)

        content_area_layout.addLayout(quick_actions)

        # Add preset buttons
        preset_label = QLabel("Quick Presets:")
        preset_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        content_area_layout.addWidget(preset_label)

        preset_buttons = QHBoxLayout()
        preset_buttons.setSpacing(4)

        minimal_preset_btn = QPushButton("📋 Minimal")
        minimal_preset_btn.setMaximumHeight(22)
        minimal_preset_btn.setFont(QFont("Segoe UI", 7))
        minimal_preset_btn.setToolTip("Essential data only (D10, D50, D60, all K-values)")
        minimal_preset_btn.clicked.connect(lambda: self._apply_preset('minimal'))
        preset_buttons.addWidget(minimal_preset_btn)

        full_preset_btn = QPushButton("📦 Full")
        full_preset_btn.setMaximumHeight(22)
        full_preset_btn.setFont(QFont("Segoe UI", 7))
        full_preset_btn.setToolTip("All available data")
        full_preset_btn.clicked.connect(lambda: self._apply_preset('full'))
        preset_buttons.addWidget(full_preset_btn)

        stats_preset_btn = QPushButton("📊 Stats")
        stats_preset_btn.setMaximumHeight(22)
        stats_preset_btn.setFont(QFont("Segoe UI", 7))
        stats_preset_btn.setToolTip("Optimized for statistical analysis")
        stats_preset_btn.clicked.connect(lambda: self._apply_preset('statistical'))
        preset_buttons.addWidget(stats_preset_btn)

        content_area_layout.addLayout(preset_buttons)

        panel_layout.addWidget(self.content_area)

        # Start collapsed by default to save vertical space on smaller screens
        self.content_area.setVisible(False)
        self.content_collapse_btn.setText("▶")

        return content_panel

    def _create_grain_size_category(self) -> QWidget:
        """Create grain size data category with expandable percentile grid"""
        group = QFrame()
        group.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 4px;
            }
        """)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        # Category header
        header_cb = QCheckBox("📏 Grain Size Data")
        header_cb.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        header_cb.setChecked(self.content_selection['grain_size']['enabled'])
        header_cb.stateChanged.connect(lambda state: self._toggle_category('grain_size', state == 2))
        layout.addWidget(header_cb)

        if not hasattr(self, 'content_checkboxes'):
            self.content_checkboxes = {}
        self.content_checkboxes['grain_size_header'] = header_cb

        # Items container
        items_layout = QVBoxLayout()
        items_layout.setContentsMargins(20, 0, 0, 0)
        items_layout.setSpacing(2)

        # Raw distribution
        raw_cb = QCheckBox("Raw distribution curve")
        raw_cb.setFont(QFont("Segoe UI", 8))
        raw_cb.setChecked(self.content_selection['grain_size']['items']['raw_distribution'])
        raw_cb.stateChanged.connect(lambda state: self._update_grain_size_item('raw_distribution', state == 2))
        items_layout.addWidget(raw_cb)
        self.content_checkboxes['grain_size_raw_distribution'] = raw_cb

        # Percentiles - expandable section
        percentiles_header = QHBoxLayout()
        percentiles_header.setSpacing(4)

        self.percentiles_expand_btn = QToolButton()
        self.percentiles_expand_btn.setText("▶")
        self.percentiles_expand_btn.setMaximumSize(16, 16)
        self.percentiles_expand_btn.setStyleSheet("QToolButton { border: none; font-size: 8px; }")
        self.percentiles_expand_btn.clicked.connect(self._toggle_percentiles_expand)
        percentiles_header.addWidget(self.percentiles_expand_btn)

        percentiles_cb = QCheckBox("Percentiles (D5, D10, D20, ..., D95)")
        percentiles_cb.setFont(QFont("Segoe UI", 8))
        percentiles_cb.setChecked(self.content_selection['grain_size']['items']['percentiles']['enabled'])
        percentiles_cb.stateChanged.connect(lambda state: self._toggle_percentiles_category(state == 2))
        percentiles_header.addWidget(percentiles_cb)
        self.content_checkboxes['grain_size_percentiles'] = percentiles_cb

        percentiles_header.addStretch()
        items_layout.addLayout(percentiles_header)

        # Percentile grid (initially hidden)
        self.percentiles_grid_widget = QWidget()
        percentiles_grid = QGridLayout(self.percentiles_grid_widget)
        percentiles_grid.setContentsMargins(40, 2, 0, 2)
        percentiles_grid.setSpacing(4)

        # Quick actions for percentiles
        select_common_btn = QPushButton("Common (D10,D20,D30,D50,D60)")
        select_common_btn.setMaximumHeight(20)
        select_common_btn.setFont(QFont("Segoe UI", 7))
        select_common_btn.clicked.connect(self._select_common_percentiles)
        percentiles_grid.addWidget(select_common_btn, 0, 0, 1, 4)

        select_all_p_btn = QPushButton("All")
        select_all_p_btn.setMaximumHeight(20)
        select_all_p_btn.setFont(QFont("Segoe UI", 7))
        select_all_p_btn.clicked.connect(self._select_all_percentiles)
        percentiles_grid.addWidget(select_all_p_btn, 0, 4)

        deselect_all_p_btn = QPushButton("None")
        deselect_all_p_btn.setMaximumHeight(20)
        deselect_all_p_btn.setFont(QFont("Segoe UI", 7))
        deselect_all_p_btn.clicked.connect(self._deselect_all_percentiles)
        percentiles_grid.addWidget(deselect_all_p_btn, 0, 5)

        # Percentile checkboxes in grid (2 rows x 5 columns)
        percentiles = ['d5', 'd10', 'd16', 'd17', 'd20', 'd30', 'd50', 'd60', 'd84', 'd95']
        percentile_labels = ['D5', 'D10', 'D16', 'D17', 'D20', 'D30', 'D50', 'D60', 'D84', 'D95']

        for i, (p_key, p_label) in enumerate(zip(percentiles, percentile_labels)):
            row = 1 + (i // 5)
            col = i % 5

            p_cb = QCheckBox(p_label)
            p_cb.setFont(QFont("Segoe UI", 7))
            p_cb.setChecked(self.content_selection['grain_size']['items']['percentiles']['items'][p_key])
            p_cb.stateChanged.connect(
                lambda state, key=p_key: self._update_percentile(key, state == 2)
            )
            percentiles_grid.addWidget(p_cb, row, col)
            self.content_checkboxes[f'percentile_{p_key}'] = p_cb

        self.percentiles_grid_widget.setVisible(False)  # Initially collapsed
        items_layout.addWidget(self.percentiles_grid_widget)

        # Gradation
        gradation_cb = QCheckBox("Gradation (Cu, Cc)")
        gradation_cb.setFont(QFont("Segoe UI", 8))
        gradation_cb.setChecked(self.content_selection['grain_size']['items']['gradation']['enabled'])
        gradation_cb.stateChanged.connect(lambda state: self._toggle_gradation(state == 2))
        items_layout.addWidget(gradation_cb)
        self.content_checkboxes['grain_size_gradation'] = gradation_cb

        # Classification
        classification_cb = QCheckBox("Soil Classification (USCS)")
        classification_cb.setFont(QFont("Segoe UI", 8))
        classification_cb.setChecked(self.content_selection['grain_size']['items']['classification'])
        classification_cb.stateChanged.connect(lambda state: self._update_grain_size_item('classification', state == 2))
        items_layout.addWidget(classification_cb)
        self.content_checkboxes['grain_size_classification'] = classification_cb

        layout.addLayout(items_layout)

        return group

    def _toggle_percentiles_expand(self):
        """Toggle percentile grid visibility"""
        if self.percentiles_grid_widget.isVisible():
            self.percentiles_grid_widget.setVisible(False)
            self.percentiles_expand_btn.setText("▶")
        else:
            self.percentiles_grid_widget.setVisible(True)
            self.percentiles_expand_btn.setText("▼")

    def _toggle_percentiles_category(self, enabled: bool):
        """Toggle all percentiles on/off"""
        self.content_selection['grain_size']['items']['percentiles']['enabled'] = enabled
        # Update all percentile checkboxes
        for p_key in self.content_selection['grain_size']['items']['percentiles']['items'].keys():
            cb = self.content_checkboxes.get(f'percentile_{p_key}')
            if cb:
                cb.setEnabled(enabled)
        self.update_file_tree()
        self.update_summary_card()

    def _update_percentile(self, percentile_key: str, checked: bool):
        """Update individual percentile selection"""
        self.content_selection['grain_size']['items']['percentiles']['items'][percentile_key] = checked
        # Check dependencies
        self._check_percentile_dependencies()
        self.update_file_tree()
        self.update_summary_card()

    def _select_common_percentiles(self):
        """Select commonly used percentiles (D10, D20, D30, D50, D60)"""
        common = ['d10', 'd20', 'd30', 'd50', 'd60']
        for p_key in self.content_selection['grain_size']['items']['percentiles']['items'].keys():
            is_common = p_key in common
            self.content_selection['grain_size']['items']['percentiles']['items'][p_key] = is_common
            cb = self.content_checkboxes.get(f'percentile_{p_key}')
            if cb:
                cb.setChecked(is_common)

    def _select_all_percentiles(self):
        """Select all percentiles"""
        for p_key in self.content_selection['grain_size']['items']['percentiles']['items'].keys():
            self.content_selection['grain_size']['items']['percentiles']['items'][p_key] = True
            cb = self.content_checkboxes.get(f'percentile_{p_key}')
            if cb:
                cb.setChecked(True)
        self.update_file_tree()
        self.update_summary_card()

    def _deselect_all_percentiles(self):
        """Deselect all percentiles"""
        for p_key in self.content_selection['grain_size']['items']['percentiles']['items'].keys():
            self.content_selection['grain_size']['items']['percentiles']['items'][p_key] = False
            cb = self.content_checkboxes.get(f'percentile_{p_key}')
            if cb:
                cb.setChecked(False)
        self.update_file_tree()
        self.update_summary_card()

    def _update_grain_size_item(self, item_key: str, checked: bool):
        """Update grain size item selection"""
        self.content_selection['grain_size']['items'][item_key] = checked
        self.update_file_tree()
        self.update_summary_card()

    def _toggle_gradation(self, enabled: bool):
        """Toggle gradation parameters"""
        self.content_selection['grain_size']['items']['gradation']['enabled'] = enabled
        # If gradation is enabled, ensure required percentiles are selected
        if enabled:
            self._check_percentile_dependencies()
        self.update_file_tree()
        self.update_summary_card()

    def _check_percentile_dependencies(self):
        """Check and auto-enable percentiles required for gradation"""
        gradation = self.content_selection['grain_size']['items']['gradation']
        if gradation['enabled']:
            # Cu requires D10 and D60
            if gradation['items']['cu']:
                for p in ['d10', 'd60']:
                    if not self.content_selection['grain_size']['items']['percentiles']['items'][p]:
                        self.content_selection['grain_size']['items']['percentiles']['items'][p] = True
                        cb = self.content_checkboxes.get(f'percentile_{p}')
                        if cb:
                            cb.setChecked(True)

            # Cc requires D10, D30, and D60
            if gradation['items']['cc']:
                for p in ['d10', 'd30', 'd60']:
                    if not self.content_selection['grain_size']['items']['percentiles']['items'][p]:
                        self.content_selection['grain_size']['items']['percentiles']['items'][p] = True
                        cb = self.content_checkboxes.get(f'percentile_{p}')
                        if cb:
                            cb.setChecked(True)

    def _create_content_category(self, title: str, items: list, category_key: str) -> QWidget:
        """Create a content category group with checkboxes"""
        group = QFrame()
        group.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 4px;
            }
        """)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        # Category header
        header_cb = QCheckBox(title)
        header_cb.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        header_cb.setChecked(self.content_selection[category_key]['enabled'])
        header_cb.stateChanged.connect(lambda state: self._toggle_category(category_key, state == 2))
        layout.addWidget(header_cb)

        # Store reference
        if not hasattr(self, 'content_checkboxes'):
            self.content_checkboxes = {}
        self.content_checkboxes[f'{category_key}_header'] = header_cb

        # Items
        items_layout = QVBoxLayout()
        items_layout.setContentsMargins(20, 0, 0, 0)
        items_layout.setSpacing(2)

        for item_key, item_label in items:
            item_cb = QCheckBox(item_label)
            item_cb.setFont(QFont("Segoe UI", 8))
            item_cb.setChecked(True)  # Default checked
            item_cb.stateChanged.connect(
                lambda state, cat=category_key, key=item_key:
                self._toggle_content_item(cat, key, state == 2)
            )
            items_layout.addWidget(item_cb)
            self.content_checkboxes[f'{category_key}_{item_key}'] = item_cb

        layout.addLayout(items_layout)

        return group

    def _toggle_content_panel_collapse(self):
        """Toggle content panel collapse/expand"""
        if self.content_area.isVisible():
            self.content_area.setVisible(False)
            self.content_collapse_btn.setText("▶")
        else:
            self.content_area.setVisible(True)
            self.content_collapse_btn.setText("▼")

    def _toggle_category(self, category_key: str, enabled: bool):
        """Toggle entire content category"""
        self.content_selection[category_key]['enabled'] = enabled
        # Update all items in category
        for key, cb in self.content_checkboxes.items():
            if key.startswith(f'{category_key}_') and key != f'{category_key}_header':
                cb.setEnabled(enabled)
        self.update_file_tree()
        self.update_summary_card()

    def _toggle_content_item(self, category_key: str, item_key: str, enabled: bool):
        """Toggle individual content item"""
        # This is a simplified version - will be expanded when implementing granular selection
        self.update_file_tree()
        self.update_summary_card()

    def _select_all_content(self):
        """Select all content items"""
        for cb in self.content_checkboxes.values():
            cb.setChecked(True)

    def _deselect_all_content(self):
        """Deselect all content items"""
        for cb in self.content_checkboxes.values():
            cb.setChecked(False)

    def _reset_content_defaults(self):
        """Reset content selection to defaults"""
        self._init_content_selection()
        # Update UI checkboxes to match
        for category_key in self.content_selection.keys():
            header_cb = self.content_checkboxes.get(f'{category_key}_header')
            if header_cb:
                header_cb.setChecked(self.content_selection[category_key]['enabled'])
        self.update_file_tree()
        self.update_summary_card()

    def _apply_preset(self, preset_name: str):
        """Apply a content selection preset"""
        if preset_name == 'minimal':
            # Essential data only
            # Percentiles: D10, D50, D60
            for p_key in ['d5', 'd16', 'd17', 'd20', 'd30', 'd84', 'd95']:
                self.content_selection['grain_size']['items']['percentiles']['items'][p_key] = False
            for p_key in ['d10', 'd50', 'd60']:
                self.content_selection['grain_size']['items']['percentiles']['items'][p_key] = True

            # Keep all K-values, gradation, classification
            self.content_selection['grain_size']['items']['raw_distribution'] = True
            self.content_selection['grain_size']['items']['percentiles']['enabled'] = True
            self.content_selection['grain_size']['items']['gradation']['enabled'] = True
            self.content_selection['grain_size']['items']['classification'] = True
            self.content_selection['k_values']['enabled'] = True
            self.content_selection['statistics']['enabled'] = True
            self.content_selection['metadata']['enabled'] = True
            self.content_selection['plots']['enabled'] = True

        elif preset_name == 'full':
            # All data
            for p_key in self.content_selection['grain_size']['items']['percentiles']['items'].keys():
                self.content_selection['grain_size']['items']['percentiles']['items'][p_key] = True

            self.content_selection['grain_size']['items']['raw_distribution'] = True
            self.content_selection['grain_size']['items']['percentiles']['enabled'] = True
            self.content_selection['grain_size']['items']['gradation']['enabled'] = True
            self.content_selection['grain_size']['items']['classification'] = True
            self.content_selection['k_values']['enabled'] = True
            self.content_selection['k_values']['include_formulas'] = True
            self.content_selection['k_values']['include_validation'] = True
            self.content_selection['statistics']['enabled'] = True
            self.content_selection['metadata']['enabled'] = True
            self.content_selection['metadata']['items']['processing_notes'] = True
            self.content_selection['metadata']['items']['software_version'] = True
            self.content_selection['plots']['enabled'] = True

        elif preset_name == 'statistical':
            # Optimized for statistical analysis (wide CSV format)
            # Common percentiles for stats
            for p_key in ['d5', 'd16', 'd17', 'd84', 'd95']:
                self.content_selection['grain_size']['items']['percentiles']['items'][p_key] = False
            for p_key in ['d10', 'd20', 'd30', 'd50', 'd60']:
                self.content_selection['grain_size']['items']['percentiles']['items'][p_key] = True

            self.content_selection['grain_size']['items']['raw_distribution'] = False  # Not needed for stats
            self.content_selection['grain_size']['items']['percentiles']['enabled'] = True
            self.content_selection['grain_size']['items']['gradation']['enabled'] = True
            self.content_selection['grain_size']['items']['classification'] = True
            self.content_selection['k_values']['enabled'] = True
            self.content_selection['k_values']['include_formulas'] = False
            self.content_selection['k_values']['include_validation'] = False
            self.content_selection['statistics']['enabled'] = True
            self.content_selection['metadata']['enabled'] = True
            self.content_selection['plots']['enabled'] = False  # No plots for statistical export

        # Update all UI checkboxes to reflect preset
        self._update_all_checkboxes()
        self.update_file_tree()
        self.update_summary_card()

    def _update_all_checkboxes(self):
        """Update all UI checkboxes to match content_selection state"""
        # Update category headers
        for category_key in self.content_selection.keys():
            header_cb = self.content_checkboxes.get(f'{category_key}_header')
            if header_cb:
                header_cb.setChecked(self.content_selection[category_key]['enabled'])

        # Update grain size items
        for item_key in ['raw_distribution', 'classification']:
            cb = self.content_checkboxes.get(f'grain_size_{item_key}')
            if cb:
                cb.setChecked(self.content_selection['grain_size']['items'][item_key])

        # Update percentiles
        percentiles_cb = self.content_checkboxes.get('grain_size_percentiles')
        if percentiles_cb:
            percentiles_cb.setChecked(self.content_selection['grain_size']['items']['percentiles']['enabled'])

        for p_key in self.content_selection['grain_size']['items']['percentiles']['items'].keys():
            cb = self.content_checkboxes.get(f'percentile_{p_key}')
            if cb:
                cb.setChecked(self.content_selection['grain_size']['items']['percentiles']['items'][p_key])

        # Update gradation
        gradation_cb = self.content_checkboxes.get('grain_size_gradation')
        if gradation_cb:
            gradation_cb.setChecked(self.content_selection['grain_size']['items']['gradation']['enabled'])

    def setup_ui(self):
        """Setup the export tab UI with 2-column layout, responsive to smaller screens"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # === TOP BAR: Dataset Scope + Output Directory + Export Button ===
        # Use a more compact layout that wraps better on smaller screens
        top_bar = QFrame()
        top_bar.setFrameShape(QFrame.Shape.StyledPanel)
        top_bar.setStyleSheet("background-color: #f0f0f0; padding: 6px; border-radius: 4px;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setSpacing(8)
        top_layout.setContentsMargins(8, 4, 8, 4)

        # Dataset scope - compact layout
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
        self.current_dataset_combo.setMinimumWidth(120)
        self.current_dataset_combo.setMaximumWidth(200)
        self.current_dataset_combo.setMaximumHeight(24)
        self.current_dataset_combo.setFont(QFont("Segoe UI", 9))
        self.current_dataset_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

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
        top_layout.addSpacing(10)

        # Output directory - more compact
        output_container = QFrame()
        output_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)
        output_layout = QHBoxLayout(output_container)
        output_layout.setContentsMargins(4, 2, 4, 2)
        output_layout.setSpacing(6)

        output_label = QLabel("📁")
        output_label.setFont(QFont("Segoe UI", 9))
        output_layout.addWidget(output_label)

        self.output_dir = QLineEdit()
        self.output_dir.setText(os.path.expanduser("~/Desktop"))
        self.output_dir.setReadOnly(True)
        self.output_dir.setMinimumWidth(150)
        self.output_dir.setMaximumHeight(22)
        self.output_dir.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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

        browse_btn = QPushButton("...")
        browse_btn.setMaximumHeight(20)
        browse_btn.setMaximumWidth(30)
        browse_btn.setFont(QFont("Segoe UI", 8))
        browse_btn.setToolTip("Browse for output directory")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #d2b48c;
                border: 1px solid #8b7355;
                border-radius: 3px;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background-color: #ddbf94;
            }
        """)
        browse_btn.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(browse_btn)

        top_layout.addWidget(output_container, 1)  # Allow output container to stretch

        # Export button - slightly more compact
        self.export_btn = QPushButton("🚀 Export")
        self.export_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.export_btn.setMinimumHeight(32)
        self.export_btn.setMinimumWidth(100)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b8e23;
                color: white;
                border-radius: 5px;
                padding: 6px 12px;
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

        # === 2-Column Layout with Splitter for resizability ===
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #d0d0d0;
            }
            QSplitter::handle:hover {
                background-color: #a0a0a0;
            }
        """)

        # === LEFT COLUMN: Formats + Content + Summary + File Tree ===
        # Wrap in scroll area for smaller screens
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #e8e8e8;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(6)

        # Format cards section
        format_label = QLabel("📁 Select Formats")
        format_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        left_layout.addWidget(format_label)

        # Format cards container - use grid for more compact display
        format_container = QWidget()
        self.formats_layout = QVBoxLayout(format_container)
        self.formats_layout.setSpacing(3)
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

        # Content selection panel (starts collapsed for small screens)
        content_panel = self._create_content_selection_panel()
        left_layout.addWidget(content_panel)

        # Summary card - more compact
        summary_card = QFrame()
        summary_card.setFrameShape(QFrame.Shape.StyledPanel)
        summary_card.setStyleSheet("""
            QFrame {
                background-color: #e8f5e9;
                border: 2px solid #6b8e23;
                border-radius: 5px;
                padding: 4px;
            }
        """)
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setSpacing(2)
        summary_layout.setContentsMargins(6, 4, 6, 4)

        self.summary_files_label = QLabel("📦 You will export <b>0 files</b>")
        self.summary_files_label.setFont(QFont("Segoe UI", 9))
        self.summary_size_label = QLabel("Estimated size: ~0 KB")
        self.summary_size_label.setFont(QFont("Segoe UI", 8))
        self.summary_size_label.setStyleSheet("color: #666;")

        summary_layout.addWidget(self.summary_files_label)
        summary_layout.addWidget(self.summary_size_label)

        left_layout.addWidget(summary_card)

        # File tree - with minimum height
        tree_label = QLabel("📄 Files to be Created")
        tree_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        left_layout.addWidget(tree_label)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Filename", "Size", "Description"])
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setRootIsDecorated(True)
        self.file_tree.setMinimumHeight(100)
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.file_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.file_tree.setStyleSheet("""
            QTreeWidget {
                font-size: 9px;
            }
            QHeaderView::section {
                font-size: 9px;
                padding: 2px;
            }
        """)

        left_layout.addWidget(self.file_tree, 1)  # Give file tree stretch factor

        left_scroll.setWidget(left_column)

        # === RIGHT COLUMN: Preview Tabs ===
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(4)

        preview_label = QLabel("📊 Data Preview")
        preview_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        right_layout.addWidget(preview_label)

        self.preview_tabs = QTabWidget()
        self.preview_tabs.setDocumentMode(True)
        self.preview_tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 4px 8px;
                font-size: 9px;
            }
        """)

        # K-Results Preview
        self.k_results_preview = QTableWidget()
        self.k_results_preview.setAlternatingRowColors(True)
        self.k_results_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_tabs.addTab(self.k_results_preview, "K-Values")

        # Format Preview
        self.format_preview = QTextEdit()
        self.format_preview.setReadOnly(True)
        self.format_preview.setFont(QFont("Consolas", 8))
        self.preview_tabs.addTab(self.format_preview, "Format")

        # Grain Data Preview
        self.grain_data_preview = QTableWidget()
        self.grain_data_preview.setAlternatingRowColors(True)
        self.grain_data_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_tabs.addTab(self.grain_data_preview, "Grain Data")

        right_layout.addWidget(self.preview_tabs)

        # Add to splitter
        splitter.addWidget(left_scroll)
        splitter.addWidget(right_column)

        # Set initial splitter proportions (35% / 65%)
        splitter.setSizes([350, 650])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        main_layout.addWidget(splitter, 1)  # Takes most space

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
            preview.setItem(row, 3, QTableWidgetItem(self._fmt(d5, ".4f")))
            preview.setItem(row, 4, QTableWidgetItem(self._fmt(d10, ".4f")))
            preview.setItem(row, 5, QTableWidgetItem(self._fmt(d16, ".4f")))
            preview.setItem(row, 6, QTableWidgetItem(self._fmt(d17, ".4f")))
            preview.setItem(row, 7, QTableWidgetItem(self._fmt(d20, ".4f")))
            preview.setItem(row, 8, QTableWidgetItem(self._fmt(d30, ".4f")))
            preview.setItem(row, 9, QTableWidgetItem(self._fmt(d50, ".4f")))
            preview.setItem(row, 10, QTableWidgetItem(self._fmt(d60, ".4f")))
            preview.setItem(row, 11, QTableWidgetItem(self._fmt(d84, ".4f")))
            preview.setItem(row, 12, QTableWidgetItem(self._fmt(d95, ".4f")))
            preview.setItem(row, 13, QTableWidgetItem(self._fmt(cu, ".2f")))
            preview.setItem(row, 14, QTableWidgetItem(self._fmt(cc, ".2f")))

            # Add K-values for each method (in all 3 units) + status
            method_dict = {r.method_name: r for r in results} if results else {}

            # K-values in m/s
            for col_idx, method in enumerate(method_names):
                if method in method_dict and method_dict[method].k_value:
                    preview.setItem(row, 15 + col_idx, QTableWidgetItem(self._fmt(method_dict[method].k_value, ".3e")))
                else:
                    preview.setItem(row, 15 + col_idx, QTableWidgetItem("-"))

            # K-values in cm/s
            col_offset = 15 + len(method_names)
            for col_idx, method in enumerate(method_names):
                if method in method_dict and method_dict[method].k_value:
                    k_cm_s = method_dict[method].k_value * 100
                    preview.setItem(row, col_offset + col_idx, QTableWidgetItem(self._fmt(k_cm_s, ".3e")))
                else:
                    preview.setItem(row, col_offset + col_idx, QTableWidgetItem("-"))

            # K-values in m/d
            col_offset = 15 + 2 * len(method_names)
            for col_idx, method in enumerate(method_names):
                if method in method_dict and method_dict[method].k_value:
                    k_m_d = method_dict[method].k_value * 86400
                    preview.setItem(row, col_offset + col_idx, QTableWidgetItem(self._fmt(k_m_d, ".2f")))
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
                preview.setItem(row, stats_col_offset + 1, QTableWidgetItem(self._fmt(np.median(valid_k_values), ".3e")))
                preview.setItem(row, stats_col_offset + 2, QTableWidgetItem(self._fmt(np.std(valid_k_values), ".3e")))
                preview.setItem(row, stats_col_offset + 3, QTableWidgetItem(self._fmt(np.min(valid_k_values), ".3e")))
                preview.setItem(row, stats_col_offset + 4, QTableWidgetItem(self._fmt(np.max(valid_k_values), ".3e")))

                # K statistics in cm/s
                valid_k_cm_s = [k * 100 for k in valid_k_values]
                preview.setItem(row, stats_col_offset + 5, QTableWidgetItem(self._fmt(np.mean(valid_k_cm_s), ".3e")))
                preview.setItem(row, stats_col_offset + 6, QTableWidgetItem(self._fmt(np.median(valid_k_cm_s), ".3e")))
                preview.setItem(row, stats_col_offset + 7, QTableWidgetItem(self._fmt(np.min(valid_k_cm_s), ".3e")))
                preview.setItem(row, stats_col_offset + 8, QTableWidgetItem(self._fmt(np.max(valid_k_cm_s), ".3e")))

                # K statistics in m/d
                valid_k_m_d = [k * 86400 for k in valid_k_values]
                preview.setItem(row, stats_col_offset + 9, QTableWidgetItem(self._fmt(np.mean(valid_k_m_d), ".2f")))
                preview.setItem(row, stats_col_offset + 10, QTableWidgetItem(self._fmt(np.median(valid_k_m_d), ".2f")))
                preview.setItem(row, stats_col_offset + 11, QTableWidgetItem(self._fmt(np.min(valid_k_m_d), ".2f")))
                preview.setItem(row, stats_col_offset + 12, QTableWidgetItem(self._fmt(np.max(valid_k_m_d), ".2f")))

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

    def set_scheme(self, scheme) -> None:
        """Set the active classification scheme used for all exports."""
        self._scheme = scheme

    def update_datasets(self, datasets: List[tuple], plot_figures: Optional[List[Any]] = None):
        """
        Update the list of available datasets

        Args:
            datasets: List of (name, GrainSizeData, List[KCalculationResult]) tuples
            plot_figures: Optional list of matplotlib Figure objects aligned with datasets
        """
        self.datasets = datasets
        if plot_figures is None:
            self.plot_figures = [None] * len(datasets)
        else:
            figures = list(plot_figures[:len(datasets)])
            if len(figures) < len(datasets):
                figures.extend([None] * (len(datasets) - len(figures)))
            self.plot_figures = figures

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
        manager.set_scheme(self._scheme)

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

    def _get_plot_figures_to_export(self) -> List[Any]:
        """Return plot figures aligned to the dataset export selection."""
        if self.scope_current.isChecked():
            idx = self.current_dataset_combo.currentIndex()
            if 0 <= idx < len(self.plot_figures):
                return [self.plot_figures[idx]]
            return []

        if self.scope_all.isChecked():
            return list(self.plot_figures)

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

            # Content - using granular content_selection structure
            'grain_distribution': self.content_selection['grain_size']['items']['raw_distribution'],
            'percentiles': self.content_selection['grain_size']['items']['percentiles']['enabled'],
            'gradation': self.content_selection['grain_size']['items']['gradation']['enabled'],
            'classification': self.content_selection['grain_size']['items']['classification'],
            'k_values': self.content_selection['k_values']['enabled'],
            'statistics': self.content_selection['statistics']['enabled'],
            'plots': self.content_selection['plots']['enabled'],
            'formulas': self.content_selection['k_values']['include_formulas'],
            'validation': self.content_selection['k_values']['include_validation'],

            # Granular selections (NEW)
            'k_filter_mode': self.content_selection['k_values']['filter_mode'],
            'selected_k_categories': dict(self.content_selection['k_values']['categories']),
            'selected_percentiles': [
                p for p, enabled in self.content_selection['grain_size']['items']['percentiles']['items'].items()
                if enabled
            ],
            'selected_k_methods': [
                method for method, enabled in self.content_selection['k_values']['individual_methods'].items()
                if enabled
            ] if self.content_selection['k_values']['filter_mode'] == 'individual' else None,
            'k_units': {
                'm_s': self.content_selection['k_values']['units']['m_s'],
                'cm_s': self.content_selection['k_values']['units']['cm_s'],
                'm_d': self.content_selection['k_values']['units']['m_d'],
            },
            'selected_statistics': [
                stat for stat, enabled in self.content_selection['statistics']['items']['k_value_stats']['items'].items()
                if enabled
            ] if self.content_selection['statistics']['items']['k_value_stats']['enabled'] else [],
            'include_grain_size_stats': self.content_selection['statistics']['items']['grain_size_stats'],
            'include_metadata': {
                'sample_info': self.content_selection['metadata']['items']['sample_info'],
                'environmental': self.content_selection['metadata']['items']['environmental'],
                'export_timestamp': self.content_selection['metadata']['items']['export_timestamp'],
            },

            # Output
            'output_dir': self.output_dir.text(),
            'filename_template': '{sample_name}_results_{date}',  # Default template
        }

        if any([
            self.selected_formats.get('png', False),
            self.selected_formats.get('svg', False),
            self.selected_formats.get('pdf', False),
        ]):
            config['plot_figures'] = self._get_plot_figures_to_export()

        return config
