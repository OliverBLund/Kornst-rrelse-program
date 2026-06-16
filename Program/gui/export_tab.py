"""
Export Tab - Unified export interface for grain size analysis results
"""

from PyQt6.QtWidgets import (
    QWidget, QApplication, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QCheckBox, QComboBox, QLabel, QPushButton, QFileDialog,
    QLineEdit, QSpinBox, QMessageBox, QScrollArea, QButtonGroup,
    QProgressDialog, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QHeaderView, QSplitter, QFrame, QTreeWidget, QTreeWidgetItem,
    QToolButton, QSizePolicy, QGridLayout, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QColor
from typing import Any, Dict, List, Optional
import os
from datetime import datetime

from data_loader import GrainSizeData
from k_calculations_v2 import KCalculationResult
from grain_classification import ISO14688
from .matplotlib_canvas import FigureCanvas
from .accordion_section import AccordionSection
from .export_manager import ExportManager
from .loading_dialog import LoadingDialog
from .stack_fade import TabFadeInController
from .theme import C, icon


class ExportProgressAdapter:
    """Adapter exposing the old progress API through the styled loading dialog."""

    def __init__(self, dialog: LoadingDialog):
        self.dialog = dialog
        self.total = 1

    def setMaximum(self, total: int) -> None:
        self.total = max(1, total)
        self.dialog.update_progress(
            0,
            self.total,
            "Preparing export",
            "Building the export package.",
            count_label=f"0 of {self.total} files",
            activity_label="Preparing folders and export settings.",
        )
        QApplication.processEvents()

    def setValue(self, current: int) -> None:
        current = max(0, min(current, self.total))
        self.dialog.update_progress(
            current,
            self.total,
            "Exporting files",
            "Writing selected tables, workbooks, and plot files.",
            count_label=f"{current} of {self.total} files",
            activity_label=f"Written {current} of {self.total} files.",
        )
        QApplication.processEvents()


class ExportTab(QWidget):
    """Unified export interface for all data formats"""

    # Signal emitted when export is started/completed
    export_started = pyqtSignal()
    export_completed = pyqtSignal(str)  # Export path
    jump_to_dataset_requested = pyqtSignal(str)
    dataset_selection_requested = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scheme = ISO14688
        self.datasets = []  # List of (name, GrainSizeData, List[KCalculationResult])
        self.plot_figures: List[Any] = []
        self.plot_contexts: List[Dict[str, Any]] = []
        self.dataset_tabs: List[Any] = []
        self.selected_dataset_keys: set[str] = set()
        self._plot_preview_canvas = None
        self._plot_preview_canvas_layout = None
        self._plot_preview_table = None
        self._plot_preview_records: List[Dict[str, Any]] = []
        self._selected_plot_preview_row = 0

        # Selected formats (for card-based selection)
        self.selected_formats = {
            'csv_long': True,
            'csv_wide': True,
            'excel': False,
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

    @staticmethod
    def _make_icon_label(icon_name: str, text: str, *, size: int = 14, bold: bool = False) -> QWidget:
        """Create a compact icon+text label using the shared qtawesome theme."""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        icon_label = QLabel()
        icon_label.setFixedWidth(size + 4)
        icon_label.setPixmap(icon(icon_name, C.TEXT_MUTED, size).pixmap(QSize(size, size)))
        icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(icon_label)

        text_label = QLabel(text)
        text_label.setFont(QFont("Segoe UI", 10 if bold else 9, QFont.Weight.Bold if bold else QFont.Weight.Normal))
        text_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(text_label)
        layout.addStretch()
        return widget

    @staticmethod
    def _set_tree_icon(item: QTreeWidgetItem, icon_name: str, color: str = C.TEXT_MUTED) -> None:
        item.setIcon(0, icon(icon_name, color, 13))

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
                    'k_value_bar': False,
                    'applicability_heatmap': False,
                    'distribution_overlay': False,
                    'k_value_comparison': False,
                    'statistical_boxplots': False,
                    'reliability_matrix': False,
                    'include_legend': True,
                    'include_grid': True,
                }
            }
        }

    def _create_format_card(self, format_key: str, title: str, description: str, icon_name: str) -> QPushButton:
        """Create a compact clickable format selection card"""
        card = QPushButton()
        card.setCheckable(True)
        card.setChecked(self.selected_formats.get(format_key, False))
        card.setObjectName(f"format_card_{format_key}")
        card.setMinimumHeight(44)
        card.setMaximumHeight(48)
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        # Store format key as property
        card.setProperty("format_key", format_key)

        # Create layout for card contents
        card_layout = QHBoxLayout(card)
        card_layout.setSpacing(7)
        card_layout.setContentsMargins(7, 4, 7, 4)

        # Icon
        icon_label = QLabel()
        icon_label.setPixmap(icon(icon_name, C.TEXT_MUTED, 14).pixmap(QSize(14, 14)))
        icon_label.setFixedWidth(20)
        icon_label.setStyleSheet("background: transparent; border: none;")
        card_layout.addWidget(icon_label)

        text_stack = QWidget()
        text_stack.setStyleSheet("background: transparent; border: none;")
        text_layout = QVBoxLayout(text_stack)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title_label.setStyleSheet("background: transparent; border: none;")
        text_layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setFont(QFont("Segoe UI", 7))
        desc_label.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent; border: none;")
        desc_label.setWordWrap(False)
        text_layout.addWidget(desc_label)

        card_layout.addWidget(text_stack, 1)
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
            card.setStyleSheet(f"""
                QPushButton {{
                    background-color: #eef5de;
                    border: 1px solid {C.OLIVE_DK};
                    border-radius: 5px;
                    text-align: left;
                    padding-left: 0px;
                    color: {C.TEXT};
                }}
                QPushButton:hover {{
                    background-color: #e5f0cf;
                    border-color: {C.OLIVE};
                }}
                QPushButton:pressed {{
                    background-color: #d9e8ba;
                }}
                QLabel {{
                    background: transparent;
                    border: none;
                }}
            """)
        else:
            card.setStyleSheet(f"""
                QPushButton {{
                    background-color: #fbf8f1;
                    border: 1px solid {C.BORDER_DK};
                    border-radius: 5px;
                    text-align: left;
                    padding-left: 0px;
                    color: {C.TEXT_MID};
                }}
                QPushButton:hover {{
                    background-color: #fffaf0;
                    border-color: {C.EARTH};
                    color: {C.TEXT};
                }}
                QPushButton:pressed {{
                    background-color: {C.BG_LOW};
                }}
                QLabel {{
                    background: transparent;
                    border: none;
                }}
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
        self._update_format_section_meta()
        self.update_preview()

    def _selected_plot_formats(self) -> List[str]:
        """Return selected plot file formats in display/export order."""
        formats = []
        if self.selected_formats.get('png'):
            formats.append('png')
        if self.selected_formats.get('svg'):
            formats.append('svg')
        if self.selected_formats.get('pdf'):
            formats.append('pdf')
        return formats

    def _selected_plot_types(self) -> List[str]:
        """Return selected plot types in display/export order."""
        plots = self.content_selection.get('plots', {})
        items = plots.get('items', {})
        ordered = (
            'grain_size_curve',
            'k_value_bar',
            'applicability_heatmap',
            'distribution_overlay',
            'k_value_comparison',
            'statistical_boxplots',
            'reliability_matrix',
        )
        return [plot_type for plot_type in ordered if items.get(plot_type, False)]

    def _selected_single_plot_types(self) -> List[str]:
        single_types = {'grain_size_curve', 'k_value_bar', 'applicability_heatmap'}
        return [plot_type for plot_type in self._selected_plot_types() if plot_type in single_types]

    def _selected_collection_plot_types(self) -> List[str]:
        collection_types = {
            'distribution_overlay',
            'k_value_comparison',
            'statistical_boxplots',
            'reliability_matrix',
        }
        return [plot_type for plot_type in self._selected_plot_types() if plot_type in collection_types]

    def _plot_type_label(self, plot_type: str) -> str:
        labels = {
            'grain_size_curve': 'Grain size curve',
            'k_value_bar': 'K-value bar chart',
            'applicability_heatmap': 'Applicability heatmap',
            'distribution_overlay': 'Distribution overlay',
            'k_value_comparison': 'K-value comparison',
            'statistical_boxplots': 'K-value boxplot',
            'reliability_matrix': 'Reliability matrix',
        }
        return labels.get(plot_type, plot_type.replace('_', ' ').title())

    def _plot_data_source_label(self, plot_type: str) -> str:
        labels = {
            'grain_size_curve': 'Curve data: particle size + percent passing',
            'k_value_bar': 'K table: method, K value, warning status',
            'applicability_heatmap': 'Method status table',
            'distribution_overlay': 'Curve data from all selected datasets',
            'k_value_comparison': 'K table from all selected datasets',
            'statistical_boxplots': 'K-value distributions by dataset',
            'reliability_matrix': 'Method status matrix',
        }
        return labels.get(plot_type, 'Plot source data')

    def _plot_file_suffix(self, plot_type: str) -> str:
        suffixes = {
            'grain_size_curve': 'plot',
            'k_value_bar': 'k_values',
            'applicability_heatmap': 'applicability',
            'distribution_overlay': 'distribution_overlay',
            'k_value_comparison': 'k_value_comparison',
            'statistical_boxplots': 'k_value_boxplot',
            'reliability_matrix': 'reliability_matrix',
        }
        return suffixes.get(plot_type, plot_type)

    def _plot_exports_enabled(self) -> bool:
        """Return whether plot files will actually be exported."""
        plots = self.content_selection.get('plots', {})
        return bool(
            plots.get('enabled', True)
            and self._selected_plot_types()
            and self._selected_plot_formats()
        )

    def update_file_tree(self):
        """Update the file tree showing exact files that will be created"""
        if not hasattr(self, 'file_tree'):
            return

        self.file_tree.clear()
        self._update_scope_labels()

        datasets_to_export = self._get_datasets_to_export()
        if not datasets_to_export:
            item = QTreeWidgetItem(["No datasets selected", ""])
            self.file_tree.addTopLevelItem(item)
            if hasattr(self, "file_tree_section"):
                self.file_tree_section.set_meta("0 files")
            return

        # CSV Files
        if self.selected_formats.get('csv_long') or self.selected_formats.get('csv_wide'):
            csv_folder = QTreeWidgetItem(["tables/csv", "CSV"])
            self._set_tree_icon(csv_folder, "fa6s.folder")
            csv_folder.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))

            if self.selected_formats.get('csv_long'):
                long_item = QTreeWidgetItem(["combined_all_datasets.csv", "long"])
                self._set_tree_icon(long_item, "fa6s.file-lines")
                csv_folder.addChild(long_item)

            if self.selected_formats.get('csv_wide'):
                wide_item = QTreeWidgetItem(["wide_format_all_datasets.csv", "wide"])
                self._set_tree_icon(wide_item, "fa6s.file-lines")
                csv_folder.addChild(wide_item)

            self.file_tree.addTopLevelItem(csv_folder)
            csv_folder.setExpanded(True)

        # Excel Files
        if self.selected_formats.get('excel'):
            excel_folder = QTreeWidgetItem(["workbooks", "Excel"])
            self._set_tree_icon(excel_folder, "fa6s.folder")
            excel_folder.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))

            for name, _, _ in datasets_to_export:
                excel_item = QTreeWidgetItem([f"{name}.xlsx", "workbook"])
                self._set_tree_icon(excel_item, "fa6s.file-excel")
                excel_folder.addChild(excel_item)

            self.file_tree.addTopLevelItem(excel_folder)
            excel_folder.setExpanded(True)

        # Plot Files
        if self._plot_exports_enabled():
            plots_folder = QTreeWidgetItem(["plots", "figures"])
            self._set_tree_icon(plots_folder, "fa6s.folder")
            plots_folder.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))

            labels = {'png': 'PNG', 'svg': 'SVG', 'pdf': 'PDF'}
            single_plot_types = self._selected_single_plot_types()
            collection_plot_types = self._selected_collection_plot_types()
            for name, _, _ in datasets_to_export:
                if not single_plot_types:
                    continue
                dataset_folder = QTreeWidgetItem([name, f"{len(single_plot_types) * len(self._selected_plot_formats())} files"])
                self._set_tree_icon(dataset_folder, "fa6s.vial")
                dataset_folder.setFont(0, QFont("Segoe UI", 9, QFont.Weight.Bold))
                plots_folder.addChild(dataset_folder)
                for fmt in self._selected_plot_formats():
                    for plot_type in single_plot_types:
                        plot_item = QTreeWidgetItem([
                            f"{self._plot_file_suffix(plot_type)}.{fmt}",
                            f"{labels[fmt]}",
                        ])
                        self._set_tree_icon(plot_item, "fa6s.image")
                        plot_item.setData(0, Qt.ItemDataRole.UserRole, {
                            "kind": "plot",
                            "dataset_name": name,
                        })
                        plot_item.setToolTip(0, "Double-click to open this dataset")
                        dataset_folder.addChild(plot_item)
                dataset_folder.setExpanded(True)

            collection_name = self._collection_sample_name()
            if collection_plot_types:
                collection_folder = QTreeWidgetItem([
                    collection_name,
                    f"{len(collection_plot_types) * len(self._selected_plot_formats())} files",
                ])
                self._set_tree_icon(collection_folder, "fa6s.layer-group")
                collection_folder.setFont(0, QFont("Segoe UI", 9, QFont.Weight.Bold))
                plots_folder.addChild(collection_folder)
                for plot_type in collection_plot_types:
                    for fmt in self._selected_plot_formats():
                        plot_item = QTreeWidgetItem([
                            f"{self._plot_file_suffix(plot_type)}.{fmt}",
                            f"{labels[fmt]}",
                        ])
                        self._set_tree_icon(plot_item, "fa6s.images")
                        collection_folder.addChild(plot_item)
                collection_folder.setExpanded(True)

            self.file_tree.addTopLevelItem(plots_folder)
            plots_folder.setExpanded(True)

        if hasattr(self, "file_tree_section"):
            self.file_tree_section.set_meta(f"{self._estimate_export_file_count()} files")

    def _on_file_tree_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, dict) and data.get("kind") == "plot":
            dataset_name = data.get("dataset_name")
            if dataset_name:
                self.jump_to_dataset_requested.emit(dataset_name)

    def _estimate_export_file_count(self) -> int:
        datasets_to_export = self._get_datasets_to_export()
        dataset_count = len(datasets_to_export)
        file_count = 0

        if self.selected_formats.get('csv_long'):
            file_count += 1
        if self.selected_formats.get('csv_wide'):
            file_count += 1
        if self.selected_formats.get('excel'):
            file_count += dataset_count

        plot_formats = len(self._selected_plot_formats()) if self._plot_exports_enabled() else 0
        single_plot_types = len(self._selected_single_plot_types()) if self._plot_exports_enabled() else 0
        collection_plot_types = len(self._selected_collection_plot_types()) if self._plot_exports_enabled() else 0
        if plot_formats > 0 and (single_plot_types or collection_plot_types):
            file_count += ((dataset_count * single_plot_types) + collection_plot_types) * plot_formats

        return file_count

    def update_summary_card(self):
        """Update the summary card showing export overview"""
        if not hasattr(self, 'summary_files_label'):
            return

        datasets_to_export = self._get_datasets_to_export()
        dataset_count = len(datasets_to_export)
        file_count = self._estimate_export_file_count()
        format_count = self._selected_format_count()

        self.summary_files_label.setText(
            f"{file_count} files - {dataset_count} dataset{'s' if dataset_count != 1 else ''} - {format_count} formats"
        )

        estimated_size = file_count * 50  # Rough estimate: 50 KB average
        if estimated_size < 1024:
            size_str = f"{estimated_size} KB"
        else:
            size_str = f"{estimated_size / 1024:.1f} MB"

        self.summary_size_label.setText(f"~{size_str} estimated - ready")
        if hasattr(self, "export_btn"):
            label = f"Export {file_count} File" if file_count == 1 else f"Export {file_count} Files"
            self.export_btn.setText(label)
            self.export_btn.setEnabled(bool(dataset_count and file_count))
        if hasattr(self, "file_tree_section"):
            self.file_tree_section.set_meta(f"{file_count} files")

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
        """Create the scrollable, collapsible included-content section."""
        section = AccordionSection("fa6s.sliders", "Included Content")
        section.set_meta("testing package")
        section.set_open(True)

        self.content_area = QWidget()
        self.content_area.setStyleSheet(f"""
            QWidget {{
                background: {C.BG_RAISED};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QPushButton {{
                background: #fbf8f1;
                border: 1px solid {C.BORDER_DK};
                border-radius: 4px;
                padding: 2px 8px;
                color: {C.TEXT_MID};
            }}
            QPushButton:hover {{
                background: #fffaf0;
                border-color: {C.EARTH};
                color: {C.TEXT};
            }}
            QPushButton:pressed {{
                background: {C.BG_LOW};
                border-color: {C.EARTH};
            }}
        """)
        content_area_layout = QVBoxLayout(self.content_area)
        content_area_layout.setContentsMargins(8, 8, 8, 8)
        content_area_layout.setSpacing(7)

        content_area_layout.addWidget(self._create_content_preset_bar())

        # === GRAIN SIZE DATA ===
        grain_size_group = self._create_grain_size_category()
        content_area_layout.addWidget(grain_size_group)

        # === K-VALUE RESULTS ===
        k_values_group = self._create_content_category(
            "K-Value Results",
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
            "Statistical Summaries",
            [
                ("k_value_stats", "K-value statistics (mean, median, std, etc.)"),
                ("grain_size_stats", "Grain size summary")
            ],
            'statistics'
        )
        content_area_layout.addWidget(stats_group)

        # === METADATA ===
        metadata_group = self._create_content_category(
            "Metadata",
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
            "Plots/Figures",
            [
                ("grain_size_curve", "Grain size distribution curve"),
                ("k_value_bar", "K-value bar chart"),
                ("applicability_heatmap", "Method applicability heatmap"),
                ("distribution_overlay", "Distribution comparison overlay"),
                ("k_value_comparison", "K-value comparison chart"),
                ("statistical_boxplots", "K-value statistical boxplots"),
                ("reliability_matrix", "Method reliability matrix"),
                ("include_legend", "Include legend"),
                ("include_grid", "Include grid lines")
            ],
            'plots'
        )
        content_area_layout.addWidget(plots_group)

        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_scroll.setMinimumHeight(185)
        content_scroll.setMaximumHeight(320)
        content_scroll.setWidget(self.content_area)
        content_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {C.BG_RAISED};
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 9px;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {C.AMBER};
                min-height: 28px;
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

        section.body_layout().addWidget(content_scroll)
        self.content_section = section
        return section

    def _create_content_preset_bar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("contentPresetBar")
        panel.setStyleSheet(f"""
            QFrame#contentPresetBar {{
                background: {C.BG_LOW};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
            }}
            QFrame#contentPresetBar QLabel {{
                background: transparent;
                border: none;
                color: {C.TEXT_MID};
            }}
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(7, 6, 7, 6)
        layout.setSpacing(5)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        preset_label = QLabel("Preset")
        preset_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        preset_row.addWidget(preset_label)

        preset_specs = [
            ("Minimal", "fa6s.list", "Essential data only", lambda: self._apply_preset('minimal')),
            ("Full", "fa6s.layer-group", "All available data", lambda: self._apply_preset('full')),
            ("Stats", "fa6s.chart-simple", "Statistical analysis package", lambda: self._apply_preset('statistical')),
            ("Default", "fa6s.rotate-left", "Restore testing defaults", self._reset_content_defaults),
        ]
        for text, icon_name, tooltip, callback in preset_specs:
            btn = QPushButton(text)
            btn.setIcon(icon(icon_name, C.TEXT_MID, 11))
            btn.setMaximumHeight(24)
            btn.setFont(QFont("Segoe UI", 8))
            btn.setToolTip(tooltip)
            btn.clicked.connect(callback)
            preset_row.addWidget(btn)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        selection_row = QHBoxLayout()
        selection_row.setSpacing(4)
        for text, icon_name, callback in (
            ("All", "fa6s.check-double", self._select_all_content),
            ("None", "fa6s.xmark", self._deselect_all_content),
        ):
            btn = QPushButton(text)
            btn.setIcon(icon(icon_name, C.TEXT_MID, 11))
            btn.setMaximumHeight(22)
            btn.setFont(QFont("Segoe UI", 8))
            btn.clicked.connect(callback)
            selection_row.addWidget(btn)
        selection_row.addStretch()
        layout.addLayout(selection_row)

        return panel

    def _create_grain_size_category(self) -> QWidget:
        """Create grain size data category with expandable percentile grid"""
        section = AccordionSection("fa6s.ruler-horizontal", "Grain Size Data")
        section.set_meta("curve")
        section.set_open(True)

        group = QFrame()
        group.setStyleSheet(f"""
            QFrame {{
                background-color: {C.BG_RAISED};
                border: none;
            }}
            QCheckBox,
            QLabel,
            QToolButton {{
                background: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        # Category header
        header_cb = QCheckBox("Include grain size data")
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
        self.percentiles_expand_btn.setIcon(icon("fa6s.chevron-right", C.TEXT_MUTED, 8))
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

        section.body_layout().addWidget(group)
        return section

    def _toggle_percentiles_expand(self):
        """Toggle percentile grid visibility"""
        if self.percentiles_grid_widget.isVisible():
            self.percentiles_grid_widget.setVisible(False)
            self.percentiles_expand_btn.setIcon(icon("fa6s.chevron-right", C.TEXT_MUTED, 8))
        else:
            self.percentiles_grid_widget.setVisible(True)
            self.percentiles_expand_btn.setIcon(icon("fa6s.chevron-down", C.TEXT_MUTED, 8))

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
        self.update_preview()

    def _update_percentile(self, percentile_key: str, checked: bool):
        """Update individual percentile selection"""
        self.content_selection['grain_size']['items']['percentiles']['items'][percentile_key] = checked
        # Check dependencies
        self._check_percentile_dependencies()
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def _select_common_percentiles(self):
        """Select commonly used percentiles (D10, D20, D30, D50, D60)"""
        common = ['d10', 'd20', 'd30', 'd50', 'd60']
        for p_key in self.content_selection['grain_size']['items']['percentiles']['items'].keys():
            is_common = p_key in common
            self.content_selection['grain_size']['items']['percentiles']['items'][p_key] = is_common
            cb = self.content_checkboxes.get(f'percentile_{p_key}')
            if cb:
                cb.setChecked(is_common)
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def _select_all_percentiles(self):
        """Select all percentiles"""
        for p_key in self.content_selection['grain_size']['items']['percentiles']['items'].keys():
            self.content_selection['grain_size']['items']['percentiles']['items'][p_key] = True
            cb = self.content_checkboxes.get(f'percentile_{p_key}')
            if cb:
                cb.setChecked(True)
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def _deselect_all_percentiles(self):
        """Deselect all percentiles"""
        for p_key in self.content_selection['grain_size']['items']['percentiles']['items'].keys():
            self.content_selection['grain_size']['items']['percentiles']['items'][p_key] = False
            cb = self.content_checkboxes.get(f'percentile_{p_key}')
            if cb:
                cb.setChecked(False)
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def _update_grain_size_item(self, item_key: str, checked: bool):
        """Update grain size item selection"""
        self.content_selection['grain_size']['items'][item_key] = checked
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def _toggle_gradation(self, enabled: bool):
        """Toggle gradation parameters"""
        self.content_selection['grain_size']['items']['gradation']['enabled'] = enabled
        # If gradation is enabled, ensure required percentiles are selected
        if enabled:
            self._check_percentile_dependencies()
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

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
        icon_map = {
            'k_values': "fa6s.droplet",
            'statistics': "fa6s.chart-simple",
            'metadata': "fa6s.circle-info",
            'plots': "fa6s.chart-line",
        }
        section = AccordionSection(icon_map.get(category_key, "fa6s.list-check"), title)
        section.set_meta(f"{len(items)} items")
        section.set_open(True)

        group = QFrame()
        group.setStyleSheet(f"""
            QFrame {{
                background-color: {C.BG_RAISED};
                border: none;
            }}
            QCheckBox,
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        # Category header
        header_cb = QCheckBox(f"Include {title.lower()}")
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
            item_cb.setChecked(self._content_item_checked(category_key, item_key))
            item_cb.stateChanged.connect(
                lambda state, cat=category_key, key=item_key:
                self._toggle_content_item(cat, key, state == 2)
            )
            items_layout.addWidget(item_cb)
            self.content_checkboxes[f'{category_key}_{item_key}'] = item_cb

        layout.addLayout(items_layout)

        section.body_layout().addWidget(group)
        return section

    def _content_item_checked(self, category_key: str, item_key: str) -> bool:
        """Return the stored checked state for a generic content checkbox."""
        category = self.content_selection.get(category_key, {})
        items = category.get('items')
        if isinstance(items, dict) and item_key in items:
            value = items[item_key]
            if isinstance(value, dict):
                return bool(value.get('enabled', False))
            return bool(value)
        if item_key in category:
            return bool(category[item_key])
        if category_key == 'k_values':
            if item_key == 'all_methods':
                return category.get('filter_mode') == 'all'
            if item_key == 'units_group':
                return any(category.get('units', {}).values())
        return False

    def _toggle_content_panel_collapse(self):
        """Toggle content panel collapse/expand"""
        if not hasattr(self, 'content_collapse_btn'):
            return
        if self.content_area.isVisible():
            self.content_area.setVisible(False)
            self.content_collapse_btn.setIcon(icon("fa6s.chevron-right", C.TEXT_MUTED, 10))
        else:
            self.content_area.setVisible(True)
            self.content_collapse_btn.setIcon(icon("fa6s.chevron-down", C.TEXT_MUTED, 10))

    def _toggle_category(self, category_key: str, enabled: bool):
        """Toggle entire content category"""
        self.content_selection[category_key]['enabled'] = enabled
        legacy_key = {
            'grain_size': 'grain_data',
            'k_values': 'k_values',
            'statistics': 'statistics',
            'plots': 'plots',
        }.get(category_key)
        if legacy_key:
            self.content_enabled[legacy_key] = enabled
        # Update all items in category
        for key, cb in self.content_checkboxes.items():
            if key.startswith(f'{category_key}_') and key != f'{category_key}_header':
                cb.setEnabled(enabled)
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def _toggle_content_item(self, category_key: str, item_key: str, enabled: bool):
        """Toggle individual content item"""
        category = self.content_selection.get(category_key)
        if not category:
            return

        items = category.get('items')
        if isinstance(items, dict) and item_key in items:
            value = items[item_key]
            if isinstance(value, dict) and 'enabled' in value:
                value['enabled'] = enabled
            else:
                items[item_key] = enabled
        elif item_key in category:
            category[item_key] = enabled
        elif category_key == 'k_values':
            if item_key == 'all_methods':
                category['filter_mode'] = 'all' if enabled else 'individual'
                if not enabled:
                    for method in category['individual_methods']:
                        category['individual_methods'][method] = False
            elif item_key == 'units_group':
                for unit_key in category['units']:
                    category['units'][unit_key] = enabled

        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

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
        self._update_all_checkboxes()
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

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
        self.update_preview()

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

        # Update generic category items
        for category_key in ('k_values', 'statistics', 'metadata', 'plots'):
            for checkbox_key, cb in self.content_checkboxes.items():
                prefix = f'{category_key}_'
                if checkbox_key.startswith(prefix) and checkbox_key != f'{category_key}_header':
                    item_key = checkbox_key[len(prefix):]
                    cb.setChecked(self._content_item_checked(category_key, item_key))

    def setup_ui(self):
        """Setup the export tab as a three-pane preview/export workspace."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(5)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {C.BORDER};
            }}
            QSplitter::handle:hover {{
                background: {C.AMBER};
            }}
        """)

        left_column = self._create_left_sidebar()
        center_column = self._create_preview_area()
        right_column = self._create_right_sidebar()

        splitter.addWidget(left_column)
        splitter.addWidget(center_column)
        splitter.addWidget(right_column)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([360, 900, 340])

        main_layout.addWidget(splitter, 1)
        self._export_splitter = splitter

        self._connect_scope_signals()
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def _create_left_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("exportLeftPanel")
        panel.setMinimumWidth(330)
        panel.setMaximumWidth(440)
        panel.setStyleSheet(f"""
            QFrame#exportLeftPanel {{
                background: {C.BG};
                border-right: 1px solid {C.BORDER};
            }}
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._create_dataset_scope_section())
        layout.addWidget(self._create_format_section())
        layout.addWidget(self._create_content_selection_panel())
        layout.addWidget(self._create_plot_queue_section(), 1)

        summary = QFrame()
        summary.setObjectName("exportSummaryStrip")
        summary.setFixedHeight(42)
        summary.setStyleSheet(f"""
            QFrame#exportSummaryStrip {{
                background: {C.BG_LOW};
                border-top: 1px solid {C.BORDER};
            }}
            QFrame#exportSummaryStrip QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(10, 4, 10, 4)
        summary_layout.setSpacing(1)
        self.summary_files_label = QLabel("0 files - 0 datasets - 0 formats")
        self.summary_files_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.summary_files_label.setStyleSheet(f"color: {C.TEXT};")
        self.summary_size_label = QLabel("ready")
        self.summary_size_label.setFont(QFont("Segoe UI", 8))
        self.summary_size_label.setStyleSheet(f"color: {C.TEXT_MUTED};")
        summary_layout.addWidget(self.summary_files_label)
        summary_layout.addWidget(self.summary_size_label)
        layout.addWidget(summary)

        return panel

    def _create_dataset_scope_section(self) -> QWidget:
        section = AccordionSection("fa6s.vials", "Dataset Scope")
        section.set_open(True)

        body = QWidget()
        body.setStyleSheet(f"""
            QWidget {{
                background: {C.BG_RAISED};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        self.scope_group = QButtonGroup(self)
        self.scope_group.setExclusive(True)

        seg_frame = QFrame()
        seg_frame.setObjectName("exportScopeSegment")
        seg_frame.setStyleSheet(f"""
            QFrame#exportScopeSegment {{
                background: #fbf8f1;
                border: 1px solid {C.BORDER_DK};
                border-radius: 4px;
                max-height: 25px;
            }}
            QFrame#exportScopeSegment QPushButton[exportScopeSeg="true"] {{
                background: #fbf8f1;
                border: none;
                border-right: 1px solid {C.BORDER};
                border-radius: 0px;
                min-height: 23px;
                max-height: 23px;
                padding: 0 8px;
                color: {C.TEXT_MID};
                font-size: 8pt;
            }}
            QFrame#exportScopeSegment QPushButton[exportScopeSeg="true"]:hover {{
                background: #fffaf0;
                color: {C.TEXT};
            }}
            QFrame#exportScopeSegment QPushButton[exportScopeSeg="true"][active="true"] {{
                background: #e8f0d5;
                color: {C.OLIVE_DK};
                font-weight: 700;
                border-bottom: 2px solid {C.OLIVE};
            }}
            QFrame#exportScopeSegment QPushButton[exportScopeSeg="true"]:disabled {{
                background: {C.BG_LOW};
                color: {C.TEXT_MUTED};
            }}
        """)
        self.scope_segment_frame = seg_frame
        seg_layout = QHBoxLayout(seg_frame)
        seg_layout.setContentsMargins(0, 0, 0, 0)
        seg_layout.setSpacing(0)

        self.scope_all = self._create_scope_segment("All", "fa6s.layer-group", True)
        self.scope_current = self._create_scope_segment("Current", "fa6s.vial", False)
        self.scope_selected = self._create_scope_segment("Selected", "fa6s.list-check", False)
        for idx, button in enumerate((self.scope_all, self.scope_current, self.scope_selected)):
            self.scope_group.addButton(button, idx)
            seg_layout.addWidget(button)
        self.scope_all.setChecked(True)
        self.scope_group.idToggled.connect(self._on_scope_segment_toggled)
        layout.addWidget(seg_frame)

        all_row = QHBoxLayout()
        all_row.setSpacing(6)
        scope_source_label = QLabel("Export source")
        scope_source_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        scope_source_label.setStyleSheet(f"color: {C.TEXT_MID}; background: transparent; border: none;")
        all_row.addWidget(scope_source_label)
        self.all_datasets_label = QLabel("0 datasets")
        self.all_datasets_label.setFont(QFont("Segoe UI", 8))
        self.all_datasets_label.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent; border: none;")
        all_row.addStretch()
        all_row.addWidget(self.all_datasets_label)
        layout.addLayout(all_row)

        current_row = QHBoxLayout()
        current_row.setSpacing(6)
        self.current_dataset_combo = QComboBox()
        self.current_dataset_combo.setMinimumHeight(26)
        self.current_dataset_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.current_dataset_combo.setFont(QFont("Segoe UI", 8))
        current_row.addWidget(self.current_dataset_combo, 1)
        layout.addLayout(current_row)

        selected_row = QHBoxLayout()
        selected_row.setSpacing(6)
        self.selected_scope_label = QLabel("sidebar/comparison selection")
        self.selected_scope_label.setFont(QFont("Segoe UI", 8))
        self.selected_scope_label.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent; border: none;")
        selected_row.addWidget(self.selected_scope_label)
        selected_row.addStretch()
        layout.addLayout(selected_row)

        self.manage_datasets_btn = QPushButton("Manage")
        self.manage_datasets_btn.setIcon(icon("fa6s.list-check", C.TEXT_MID, 12))
        self.manage_datasets_btn.setMinimumHeight(28)
        self.manage_datasets_btn.setStyleSheet(f"""
            QPushButton {{
                background: #fbf8f1;
                border: 1px solid {C.BORDER_DK};
                border-radius: 4px;
                color: {C.TEXT_MID};
                padding: 3px 8px;
            }}
            QPushButton:hover {{
                background: #fffaf0;
                border-color: {C.EARTH};
                color: {C.TEXT};
            }}
            QPushButton:pressed {{
                background: {C.BG_LOW};
                border-color: {C.EARTH};
            }}
            QPushButton:disabled {{
                background: {C.BG_LOW};
                color: {C.TEXT_MUTED};
                border-color: {C.BORDER};
            }}
        """)
        self.manage_datasets_btn.clicked.connect(self._on_manage_export_datasets)
        layout.addWidget(self.manage_datasets_btn)

        section.body_layout().addWidget(body)
        self.dataset_scope_section = section
        return section

    def _create_scope_segment(self, text: str, icon_name: str, checked: bool) -> QPushButton:
        button = QPushButton(f"  {text}")
        button.setIcon(icon(icon_name, C.TEXT if checked else C.TEXT_MID, 12))
        button.setIconSize(QSize(12, 12))
        button.setProperty("exportScopeSeg", True)
        button.setProperty("active", checked)
        button.setProperty("scope_icon", icon_name)
        button.setCheckable(True)
        button.setChecked(checked)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _on_scope_segment_toggled(self, _button_id: int, checked: bool) -> None:
        if not checked:
            return
        for button in (self.scope_all, self.scope_current, self.scope_selected):
            active = button.isChecked()
            button.setProperty("active", active)
            icon_name = button.property("scope_icon")
            if icon_name:
                button.setIcon(icon(icon_name, C.TEXT if active else C.TEXT_MID, 12))
            button.style().unpolish(button)
            button.style().polish(button)

    def _create_format_section(self) -> QWidget:
        section = AccordionSection("fa6s.file-export", "Output Formats")
        section.set_open(True)

        body = QWidget()
        body.setStyleSheet(f"""
            QWidget {{
                background: {C.BG_RAISED};
            }}
        """)
        self.formats_layout = QGridLayout(body)
        self.formats_layout.setContentsMargins(10, 8, 10, 10)
        self.formats_layout.setSpacing(6)

        cards = [
            ('csv_long', 'CSV Long', 'One row per K-value result', 'fa6s.table-columns'),
            ('csv_wide', 'CSV Wide', 'For statistical analysis', 'fa6s.table-cells'),
            ('excel', 'Excel', 'Multi-sheet workbooks', 'fa6s.file-excel'),
            ('png', 'PNG', 'High-resolution images', 'fa6s.image'),
            ('svg', 'SVG', 'Vector graphics', 'fa6s.pen-nib'),
            ('pdf', 'PDF', 'Publication-ready plots', 'fa6s.file-pdf'),
        ]
        for index, args in enumerate(cards):
            card = self._create_format_card(*args)
            self.formats_layout.addWidget(card, index // 2, index % 2)

        section.body_layout().addWidget(body)
        self.format_section = section
        return section

    def _create_plot_queue_section(self) -> QWidget:
        section = AccordionSection("fa6s.chart-line", "Selected Plots")
        section.set_open(True)

        self.plot_queue_tree = QTreeWidget()
        self.plot_queue_tree.setHeaderHidden(True)
        self.plot_queue_tree.setRootIsDecorated(True)
        self.plot_queue_tree.setAlternatingRowColors(True)
        self.plot_queue_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.plot_queue_tree.setMinimumHeight(150)
        self.plot_queue_tree.itemSelectionChanged.connect(self._on_plot_queue_selection_changed)
        self.plot_queue_tree.itemActivated.connect(lambda _item, _col: self._open_selected_plot_dataset())
        self.plot_queue_tree.setStyleSheet(f"""
            QTreeWidget {{
                border: none;
                font-size: 9px;
                background: {C.BG};
            }}
            QTreeWidget::item {{
                min-height: 28px;
            }}
        """)
        section.body_layout().addWidget(self.plot_queue_tree)
        self.plot_queue_section = section
        return section

    def _create_preview_area(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("exportPreviewPanel")
        panel.setStyleSheet(f"""
            QFrame#exportPreviewPanel {{
                background: {C.BG_RAISED};
            }}
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.preview_tabs = QTabWidget()
        self.preview_tabs.setDocumentMode(True)
        self.preview_tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 5px 10px;
                font-size: 9px;
            }
        """)
        self._preview_tabs_fader = TabFadeInController(
            self.preview_tabs,
            self,
            duration_ms=95,
        )
        layout.addWidget(self.preview_tabs, 1)
        return panel

    def _create_right_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("exportRightPanel")
        panel.setMinimumWidth(320)
        panel.setMaximumWidth(430)
        panel.setStyleSheet(f"""
            QFrame#exportRightPanel {{
                background: {C.BG};
                border-left: 1px solid {C.BORDER};
            }}
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._create_output_folder_section())
        layout.addWidget(self._create_file_tree_section(), 1)
        layout.addWidget(self._create_export_actions())
        return panel

    def _create_output_folder_section(self) -> QWidget:
        section = AccordionSection("fa6s.folder-open", "Output Folder")
        section.set_open(True)

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        layout = QHBoxLayout(body)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        self.output_dir = QLineEdit()
        self.output_dir.setText(os.path.expanduser("~/Desktop"))
        self.output_dir.setReadOnly(True)
        self.output_dir.setMinimumHeight(28)
        self.output_dir.setFont(QFont("Consolas", 8))
        layout.addWidget(self.output_dir, 1)

        browse_btn = QPushButton("...")
        browse_btn.setMaximumWidth(34)
        browse_btn.setMinimumHeight(28)
        browse_btn.setToolTip("Browse for output directory")
        browse_btn.clicked.connect(self.browse_output_dir)
        layout.addWidget(browse_btn)

        section.body_layout().addWidget(body)
        self.output_folder_section = section
        return section

    def _create_file_tree_section(self) -> QWidget:
        section = AccordionSection("fa6s.folder-tree", "Files to Create")
        section.set_open(True)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["File", "Info"])
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setRootIsDecorated(True)
        self.file_tree.setMinimumHeight(260)
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.file_tree.itemActivated.connect(self._on_file_tree_item_activated)
        self.file_tree.setStyleSheet("""
            QTreeWidget {
                border: none;
                font-size: 9px;
            }
            QHeaderView::section {
                font-size: 9px;
                padding: 3px 4px;
            }
            QTreeWidget::item {
                min-height: 25px;
            }
        """)

        section.body_layout().addWidget(self.file_tree)
        self.file_tree_section = section
        return section

    def _create_export_actions(self) -> QWidget:
        footer = QFrame()
        footer.setObjectName("exportActions")
        footer.setFixedHeight(124)
        footer.setStyleSheet(f"""
            QFrame#exportActions {{
                background: {C.BG_RAISED};
                border-top: 1px solid {C.BORDER};
            }}
        """)
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(7)

        self.open_dataset_btn = QPushButton("Open Dataset")
        self.open_dataset_btn.setIcon(icon("fa6s.arrow-up-right-from-square", C.TEXT_MID, 12))
        self.open_dataset_btn.setMinimumHeight(28)
        self.open_dataset_btn.clicked.connect(self._open_selected_plot_dataset)
        layout.addWidget(self.open_dataset_btn)

        self.plot_options_btn = QPushButton("Plot Options")
        self.plot_options_btn.setIcon(icon("fa6s.sliders", C.TEXT_MID, 12))
        self.plot_options_btn.setMinimumHeight(28)
        self.plot_options_btn.clicked.connect(self._open_selected_plot_dataset)
        layout.addWidget(self.plot_options_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.setIcon(icon("fa6s.file-export", "#ffffff", 13))
        self.export_btn.setMinimumHeight(34)
        self.export_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
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
            QPushButton:disabled {
                background-color: #a8a8a8;
                color: #f0f0f0;
            }
        """)
        self.export_btn.clicked.connect(self.export_now)
        layout.addWidget(self.export_btn)

        return footer

    def _connect_scope_signals(self) -> None:
        for radio in (self.scope_all, self.scope_current, self.scope_selected):
            radio.toggled.connect(self._refresh_export_surface)
        self.current_dataset_combo.currentIndexChanged.connect(self._refresh_export_surface)

    def _refresh_export_surface(self) -> None:
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def _selected_format_count(self) -> int:
        return sum(1 for enabled in self.selected_formats.values() if enabled)

    def _dataset_key(self, name: str, dataset: Any) -> str:
        return str(getattr(dataset, "file_path", None) or name)

    def _dataset_key_from_tab(self, tab: Any) -> str:
        dataset = tab.get_dataset() if hasattr(tab, "get_dataset") else getattr(tab, "dataset", None)
        name = tab.get_dataset_name() if hasattr(tab, "get_dataset_name") else getattr(dataset, "sample_name", "")
        return self._dataset_key(name, dataset)

    def _set_selected_tabs(self, selected_tabs: Optional[List[Any]]) -> None:
        if selected_tabs is None:
            return
        self.selected_dataset_keys = {
            self._dataset_key_from_tab(tab)
            for tab in selected_tabs
            if self._dataset_key_from_tab(tab)
        }

    def _selected_dataset_indices(self) -> List[int]:
        if self.scope_current.isChecked():
            idx = self.current_dataset_combo.currentIndex()
            return [idx] if 0 <= idx < len(self.datasets) else []

        if self.scope_selected.isChecked():
            if not self.selected_dataset_keys:
                return []
            return [
                idx for idx, (name, dataset, _results) in enumerate(self.datasets)
                if self._dataset_key(name, dataset) in self.selected_dataset_keys
            ]

        return list(range(len(self.datasets)))

    def _collection_sample_name(self) -> str:
        return "selected_datasets" if self.scope_selected.isChecked() else "all_datasets"

    def _update_scope_labels(self) -> None:
        if not hasattr(self, "all_datasets_label"):
            return
        count = len(self.datasets)
        selected_count = len([
            1 for name, dataset, _results in self.datasets
            if self._dataset_key(name, dataset) in self.selected_dataset_keys
        ])
        self.all_datasets_label.setText(f"{count} dataset{'s' if count != 1 else ''}")
        self.selected_scope_label.setText(
            f"{selected_count} selected" if selected_count else "sidebar/comparison selection"
        )
        if hasattr(self, "dataset_scope_section"):
            active_count = len(self._get_datasets_to_export())
            self.dataset_scope_section.set_meta(f"{active_count}/{count}")

    def _update_format_section_meta(self) -> None:
        if hasattr(self, "format_section"):
            self.format_section.set_meta(f"{self._selected_format_count()} formats")

    def _on_manage_export_datasets(self) -> None:
        if not self.dataset_tabs:
            return

        from .dataset_selection_dialog import DatasetSelectionDialog

        current_tabs = [
            tab for tab in self.dataset_tabs
            if self._dataset_key_from_tab(tab) in self.selected_dataset_keys
        ] or list(self.dataset_tabs)

        dialog = DatasetSelectionDialog(
            self.dataset_tabs,
            currently_selected=current_tabs,
            title="Export Scope & Groups",
            subtitle="Choose which samples to export and assign group labels if needed",
            action_text="Use Selected",
            action_icon="fa6s.check",
            minimum_selection=1,
            allow_grouping=True,
            parent=self,
        )
        if dialog.exec():
            if hasattr(dialog, "get_group_assignments"):
                for tab, group_name in dialog.get_group_assignments().items():
                    try:
                        tab.get_dataset().group_name = group_name
                    except Exception:
                        pass
            selected_tabs = dialog.get_selected_tabs()
            self._set_selected_tabs(selected_tabs)
            self.scope_selected.setChecked(True)
            self.dataset_selection_requested.emit(self._dataset_paths(selected_tabs))
            self._refresh_export_surface()

    @staticmethod
    def _dataset_paths(dataset_tabs: List[Any]) -> list[str]:
        paths: list[str] = []
        for tab in dataset_tabs:
            dataset = tab.get_dataset() if hasattr(tab, "get_dataset") else getattr(tab, "dataset", None)
            file_path = getattr(dataset, "file_path", "") if dataset is not None else ""
            if file_path:
                paths.append(file_path)
        return paths

    def update_preview(self):
        """Update preview tabs based on selected formats"""
        # Clear all tabs
        self.preview_tabs.clear()
        self._plot_preview_canvas = None
        self._plot_preview_canvas_layout = None
        if self._plot_preview_table is not None:
            self._plot_preview_table.deleteLater()
        self._plot_preview_table = None
        self._plot_preview_records = []
        self._selected_plot_preview_row = 0

        datasets_to_export = self._get_datasets_to_export()
        self._update_scope_labels()
        self._update_format_section_meta()

        # Add tabs only for selected formats
        if self.selected_formats.get('csv_long'):
            self._add_csv_long_preview_tab(datasets_to_export)

        if self.selected_formats.get('csv_wide'):
            self._add_csv_wide_preview_tab(datasets_to_export)

        if self.selected_formats.get('excel'):
            self._add_excel_preview_tab(datasets_to_export)

        # Add plot preview if any plot format is selected
        if self._plot_exports_enabled():
            self._add_plot_preview_tab(datasets_to_export)
        else:
            self._populate_plot_queue([])
            if hasattr(self, "open_dataset_btn"):
                self.open_dataset_btn.setEnabled(False)
            if hasattr(self, "plot_options_btn"):
                self.plot_options_btn.setEnabled(False)

        # If no formats selected, show help
        if self.preview_tabs.count() == 0:
            self._add_help_tab()

    def _add_csv_long_preview_tab(self, datasets_to_export):
        """Add CSV Long preview using the same rows as the export writer."""
        preview = QTableWidget()
        preview.setAlternatingRowColors(True)
        preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        manager = ExportManager()
        manager.set_scheme(self._scheme)
        rows = manager.build_csv_long_table(datasets_to_export, self._build_export_config(), max_data_rows=50)
        headers = rows[0] if rows else []
        data_rows = rows[1:]

        preview.setColumnCount(len(headers))
        preview.setHorizontalHeaderLabels([str(header) for header in headers])
        preview.setRowCount(len(data_rows))
        for row, values in enumerate(data_rows):
            for column, value in enumerate(values):
                preview.setItem(row, column, QTableWidgetItem("" if value is None else str(value)))

        preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        preview.horizontalHeader().setStretchLastSection(False)

        label = "CSV Long (50 rows)" if len(data_rows) == 50 else "CSV Long"
        self.preview_tabs.addTab(preview, icon("fa6s.table-columns", C.TEXT_MUTED, 12), label)
        return

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

        label = f"CSV Long ({max_preview_rows} rows)" if total_rows > max_preview_rows else "CSV Long"
        self.preview_tabs.addTab(preview, icon("fa6s.table-columns", C.TEXT_MUTED, 12), label)

    def _add_csv_wide_preview_tab(self, datasets_to_export):
        """Add CSV Wide preview using the same rows as the export writer."""
        preview = QTableWidget()
        preview.setAlternatingRowColors(True)
        preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        manager = ExportManager()
        manager.set_scheme(self._scheme)
        rows = manager.build_csv_wide_table(datasets_to_export, self._build_export_config(), max_data_rows=20)
        headers = rows[0] if rows else []
        data_rows = rows[1:]

        preview.setColumnCount(len(headers))
        preview.setHorizontalHeaderLabels([str(header) for header in headers])
        preview.setRowCount(len(data_rows))
        for row, values in enumerate(data_rows):
            for column, value in enumerate(values):
                preview.setItem(row, column, QTableWidgetItem("" if value is None else str(value)))

        preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        preview.horizontalHeader().setStretchLastSection(False)

        label = "CSV Wide (20 datasets)" if len(data_rows) == 20 and len(datasets_to_export) > 20 else "CSV Wide"
        self.preview_tabs.addTab(preview, icon("fa6s.chart-simple", C.TEXT_MUTED, 12), label)
        return

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

        label = f"CSV Wide ({max_preview_rows} datasets)" if len(datasets_to_export) > max_preview_rows else "CSV Wide"
        self.preview_tabs.addTab(preview, icon("fa6s.chart-simple", C.TEXT_MUTED, 12), label)

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
            text.append("  - Summary - Dataset overview and key parameters")
            text.append("  - Grain_Size_Data - Particle size distribution")
            text.append("  - Percentiles - D10, D20, D30, D50, D60, etc.")
            text.append("  - K_Values - All calculation methods and results")
            text.append("  - Statistics - Summary statistics")
            text.append("")
            text.append(f"Total workbooks to create: {len(datasets_to_export)}")

        preview.setPlainText("\n".join(text))
        self.preview_tabs.addTab(preview, icon("fa6s.file-excel", C.TEXT_MUTED, 12), "Excel")

    def _add_plot_preview_tab(self, datasets_to_export):
        """Add a real plot preview tab backed by the export renderer."""
        preview = QWidget()
        layout = QVBoxLayout(preview)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        single_plot_types = self._selected_single_plot_types()
        collection_plot_types = self._selected_collection_plot_types()
        preview_rows = [
            {
                "scope": "single",
                "dataset_index": dataset_index,
                "dataset_name": name,
                "plot_type": plot_type,
            }
            for dataset_index, (name, _dataset, _results) in enumerate(datasets_to_export)
            for plot_type in single_plot_types
        ]
        preview_rows.extend(
            {
                "scope": "collection",
                "dataset_index": -1,
                "dataset_name": "All datasets",
                "plot_type": plot_type,
            }
            for plot_type in collection_plot_types
        )
        self._plot_preview_records = preview_rows
        self._populate_plot_preview_table(preview_rows)
        self._populate_plot_queue(preview_rows)

        canvas_host = QFrame()
        canvas_host.setFrameShape(QFrame.Shape.StyledPanel)
        canvas_host.setStyleSheet("QFrame { background: white; border: 1px solid #d8d8d8; border-radius: 4px; }")
        self._plot_preview_canvas_layout = QVBoxLayout(canvas_host)
        self._plot_preview_canvas_layout.setContentsMargins(6, 6, 6, 6)
        self._plot_preview_canvas_layout.setSpacing(0)
        layout.addWidget(canvas_host, 1)

        if preview_rows:
            self._selected_plot_preview_row = min(self._selected_plot_preview_row, len(preview_rows) - 1)
            self._plot_preview_table.selectRow(self._selected_plot_preview_row)
            self._select_plot_queue_row(self._selected_plot_preview_row)
            self._render_selected_plot_preview()

        self.preview_tabs.addTab(preview, icon("fa6s.chart-line", C.TEXT_MUTED, 12), "Plots")

    def _populate_plot_preview_table(self, preview_rows: List[Dict[str, Any]]) -> None:
        """Maintain a lightweight hidden table for tests and legacy helpers."""
        self._plot_preview_table = QTableWidget(self)
        self._plot_preview_table.setColumnCount(4)
        self._plot_preview_table.setHorizontalHeaderLabels(["Dataset", "Plot", "Formats", "Data used"])
        self._plot_preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._plot_preview_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._plot_preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._plot_preview_table.setRowCount(len(preview_rows))

        format_label = ", ".join(fmt.upper() for fmt in self._selected_plot_formats())
        for row, record in enumerate(preview_rows):
            name_item = QTableWidgetItem(record["dataset_name"])
            name_item.setData(Qt.ItemDataRole.UserRole, record)
            self._plot_preview_table.setItem(row, 0, name_item)
            self._plot_preview_table.setItem(row, 1, QTableWidgetItem(self._plot_type_label(record["plot_type"])))
            self._plot_preview_table.setItem(row, 2, QTableWidgetItem(format_label))
            self._plot_preview_table.setItem(row, 3, QTableWidgetItem(self._plot_data_source_label(record["plot_type"])))
        self._plot_preview_table.itemSelectionChanged.connect(self._on_hidden_plot_table_selection_changed)

    def _populate_plot_queue(self, preview_rows: List[Dict[str, Any]]) -> None:
        tree = getattr(self, "plot_queue_tree", None)
        if tree is None:
            return
        tree.blockSignals(True)
        tree.clear()

        format_label = ", ".join(fmt.upper() for fmt in self._selected_plot_formats())
        dataset_folders: Dict[str, QTreeWidgetItem] = {}
        collection_folder: Optional[QTreeWidgetItem] = None

        def folder_for_record(record: Dict[str, Any]) -> QTreeWidgetItem:
            nonlocal collection_folder
            if record["scope"] == "single":
                dataset_name = record["dataset_name"]
                if dataset_name not in dataset_folders:
                    folder = QTreeWidgetItem([dataset_name])
                    folder.setIcon(0, icon("fa6s.vial", C.TEXT_MUTED, 12))
                    folder.setFont(0, QFont("Segoe UI", 8, QFont.Weight.Bold))
                    tree.addTopLevelItem(folder)
                    folder.setExpanded(True)
                    dataset_folders[dataset_name] = folder
                return dataset_folders[dataset_name]

            if collection_folder is None:
                collection_folder = QTreeWidgetItem([record["dataset_name"]])
                collection_folder.setIcon(0, icon("fa6s.layer-group", C.TEXT_MUTED, 12))
                collection_folder.setFont(0, QFont("Segoe UI", 8, QFont.Weight.Bold))
                tree.addTopLevelItem(collection_folder)
                collection_folder.setExpanded(True)
            return collection_folder

        for row, record in enumerate(preview_rows):
            label = self._plot_type_label(record["plot_type"])
            if record["scope"] == "single":
                text = f"{label} - {format_label}"
                icon_name = "fa6s.chart-line"
            else:
                text = f"{label} - {format_label}"
                icon_name = "fa6s.layer-group"
            item = QTreeWidgetItem([text])
            item.setIcon(0, icon(icon_name, C.TEXT_MUTED, 12))
            item.setData(0, Qt.ItemDataRole.UserRole, row)
            item.setToolTip(
                0,
                f"{self._plot_data_source_label(record['plot_type'])}\n"
                "Select to preview; double-click single-dataset plots to open the source tab",
            )
            folder_for_record(record).addChild(item)

        if hasattr(self, "plot_queue_section"):
            self.plot_queue_section.set_meta(f"{len(preview_rows)} plots")
        tree.blockSignals(False)
        if preview_rows:
            self._select_plot_queue_row(min(self._selected_plot_preview_row, len(preview_rows) - 1))

    def _select_plot_queue_row(self, row: int) -> None:
        tree = getattr(self, "plot_queue_tree", None)
        if tree is None or row < 0:
            return

        def find_item(parent: QTreeWidgetItem) -> Optional[QTreeWidgetItem]:
            if parent.data(0, Qt.ItemDataRole.UserRole) == row:
                return parent
            for child_index in range(parent.childCount()):
                found = find_item(parent.child(child_index))
                if found is not None:
                    return found
            return None

        target = None
        for index in range(tree.topLevelItemCount()):
            target = find_item(tree.topLevelItem(index))
            if target is not None:
                break
        if target is None:
            return
        self._selected_plot_preview_row = row
        table = getattr(self, "_plot_preview_table", None)
        if table is not None and 0 <= row < table.rowCount():
            table.blockSignals(True)
            table.selectRow(row)
            table.blockSignals(False)
        tree.blockSignals(True)
        tree.setCurrentItem(target)
        tree.blockSignals(False)

    def _on_hidden_plot_table_selection_changed(self) -> None:
        table = getattr(self, "_plot_preview_table", None)
        if table is None:
            return
        row = table.currentRow()
        if row >= 0:
            self._selected_plot_preview_row = row

    def _on_plot_queue_selection_changed(self) -> None:
        tree = getattr(self, "plot_queue_tree", None)
        if tree is None:
            return
        item = tree.currentItem()
        if item is None:
            return
        row = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(row, int):
            return
        self._selected_plot_preview_row = row
        table = getattr(self, "_plot_preview_table", None)
        if table is not None and 0 <= row < table.rowCount():
            table.blockSignals(True)
            table.selectRow(row)
            table.blockSignals(False)
        for index in range(self.preview_tabs.count()):
            if self.preview_tabs.tabText(index).startswith("Plots"):
                self.preview_tabs.setCurrentIndex(index)
                break
        self._render_selected_plot_preview()

    def _selected_plot_export_index(self) -> int:
        if not self._plot_preview_records:
            return -1
        row = self._selected_plot_preview_row
        return row if 0 <= row < len(self._plot_preview_records) else 0

    def _plot_context_for_export_index(self, export_index: int) -> Dict[str, Any]:
        contexts = self._get_plot_contexts_to_export()
        if 0 <= export_index < len(contexts):
            return dict(contexts[export_index])
        return {}

    def _selected_plot_preview_record(self) -> Optional[Dict[str, Any]]:
        row = self._selected_plot_export_index()
        if row < 0:
            return None
        record = self._plot_preview_records[row]
        return record if isinstance(record, dict) else None

    def _render_selected_plot_preview(self) -> None:
        if self._plot_preview_canvas_layout is None:
            return

        datasets_to_export = self._get_datasets_to_export()
        record = self._selected_plot_preview_record()
        if not record:
            return
        is_single_record = record.get("scope") == "single"
        if hasattr(self, "open_dataset_btn"):
            self.open_dataset_btn.setEnabled(is_single_record)
        if hasattr(self, "plot_options_btn"):
            self.plot_options_btn.setEnabled(is_single_record)

        if self._plot_preview_canvas is not None:
            self._plot_preview_canvas.setParent(None)
            self._plot_preview_canvas.deleteLater()
            self._plot_preview_canvas = None

        config = self._build_export_config()
        config["plot_figsize"] = (8, 5)

        from gui.export_manager import ExportManager

        manager = ExportManager()
        manager.set_scheme(self._scheme)
        if record["scope"] == "collection":
            context = self._plot_context_for_export_index(0)
            figure = manager._build_collection_plot_figure(
                record["plot_type"], datasets_to_export, config, context,
            )
        else:
            export_index = record["dataset_index"]
            if not (0 <= export_index < len(datasets_to_export)):
                return
            name, dataset, results = datasets_to_export[export_index]
            context = self._plot_context_for_export_index(export_index)
            figure = manager._build_single_sample_plot_figure(
                record["plot_type"], name, dataset, results, config, context,
            )
        self._plot_preview_canvas = FigureCanvas(figure)
        self._plot_preview_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._plot_preview_canvas_layout.addWidget(self._plot_preview_canvas)
        self._plot_preview_canvas.draw()

    def _open_selected_plot_dataset(self) -> None:
        record = self._selected_plot_preview_record()
        if record and record.get("scope") == "single":
            dataset_name = record.get("dataset_name")
            if dataset_name:
                self.jump_to_dataset_requested.emit(dataset_name)

    def _add_help_tab(self):
        """Add help tab when no formats are selected"""
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setFont(QFont("Segoe UI", 10))

        text = []
        text.append("Select export formats from the cards on the left")
        text.append("")
        text.append("Available formats:")
        text.append("")
        text.append("  CSV Long - One row per K-value result")
        text.append("     Best for: Data analysis, importing into other tools")
        text.append("")
        text.append("  CSV Wide - One row per dataset, columns for each method")
        text.append("     Best for: Statistical analysis, method comparison")
        text.append("")
        text.append("  Excel - Multi-sheet workbooks (one per dataset)")
        text.append("     Best for: Comprehensive reports, sharing results")
        text.append("")
        text.append("  PNG - High-resolution plot images")
        text.append("     Best for: Presentations, reports")
        text.append("")
        text.append("  SVG - Vector graphics plots")
        text.append("     Best for: Scalable graphics, editing")
        text.append("")
        text.append("  PDF - Publication-ready plots")
        text.append("     Best for: Documents, archiving")

        preview.setPlainText("\n".join(text))
        self.preview_tabs.addTab(preview, icon("fa6s.circle-info", C.TEXT_MUTED, 12), "Help")

    def set_scheme(self, scheme) -> None:
        """Set the active classification scheme used for all exports."""
        self._scheme = scheme

    def update_datasets(
        self,
        datasets: List[tuple],
        plot_figures: Optional[List[Any]] = None,
        plot_contexts: Optional[List[Dict[str, Any]]] = None,
        dataset_tabs: Optional[List[Any]] = None,
        selected_tabs: Optional[List[Any]] = None,
    ):
        """
        Update the list of available datasets

        Args:
            datasets: List of (name, GrainSizeData, List[KCalculationResult]) tuples
            plot_figures: Optional list of matplotlib Figure objects aligned with datasets
            plot_contexts: Optional list of live plot style/state dictionaries aligned with datasets
            dataset_tabs: Optional dataset tab objects used by the shared selection dialog
            selected_tabs: Optional sidebar/comparison-selected dataset tab subset
        """
        self.datasets = datasets
        if dataset_tabs is not None:
            self.dataset_tabs = list(dataset_tabs)
        elif not self.dataset_tabs:
            self.dataset_tabs = []
        previous_keys = set(self.selected_dataset_keys)
        if selected_tabs is not None:
            self._set_selected_tabs(list(selected_tabs))
        else:
            valid_keys = {self._dataset_key(name, dataset) for name, dataset, _ in datasets}
            self.selected_dataset_keys = previous_keys & valid_keys
            if not self.selected_dataset_keys and datasets:
                self.selected_dataset_keys = set(valid_keys)

        if plot_figures is None:
            self.plot_figures = [None] * len(datasets)
        else:
            figures = list(plot_figures[:len(datasets)])
            if len(figures) < len(datasets):
                figures.extend([None] * (len(datasets) - len(figures)))
            self.plot_figures = figures
        if plot_contexts is None:
            self.plot_contexts = [{} for _ in datasets]
        else:
            contexts = list(plot_contexts[:len(datasets)])
            if len(contexts) < len(datasets):
                contexts.extend({} for _ in range(len(datasets) - len(contexts)))
            self.plot_contexts = contexts
        # Update current dataset combo
        self.current_dataset_combo.blockSignals(True)
        self.current_dataset_combo.clear()
        for name, _, _ in datasets:
            self.current_dataset_combo.addItem(name)
        self.current_dataset_combo.blockSignals(False)

        # Update count label
        count = len(datasets)
        self._update_scope_labels()

        # Enable/disable scope options
        has_datasets = count > 0
        self.scope_current.setEnabled(has_datasets)
        self.scope_all.setEnabled(has_datasets)
        self.scope_selected.setEnabled(has_datasets)
        self.current_dataset_combo.setEnabled(has_datasets)
        self.manage_datasets_btn.setEnabled(has_datasets and bool(self.dataset_tabs))
        self.export_btn.setEnabled(has_datasets)

        # Update preview and summary
        self.update_file_tree()
        self.update_summary_card()
        self.update_preview()

    def set_dataset_selection_state(
        self,
        dataset_tabs: Optional[List[Any]] = None,
        selected_tabs: Optional[List[Any]] = None,
    ) -> None:
        """Update only the selectable dataset subset without rebuilding dataset data."""
        if dataset_tabs is not None:
            self.dataset_tabs = list(dataset_tabs)
        if selected_tabs is not None:
            self._set_selected_tabs(list(selected_tabs))
        self._refresh_export_surface()

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

        # Show plot formats preview if selected
        labels = {'png': 'PNG', 'svg': 'SVG', 'pdf': 'PDF'}
        plot_formats = [labels[fmt] for fmt in self._selected_plot_formats()] if self._plot_exports_enabled() else []

        if plot_formats:
            if preview_text:
                preview_text.append("")
                preview_text.append("=" * 60)
                preview_text.append("")

            preview_text.append(f"=== PLOT FILES ({', '.join(plot_formats)}) ===")
            preview_text.append("")
            preview_text.append("Plot files export figures. Numeric data behind the active plot can be exported from that plot's table drawer.")
            preview_text.append("")
            preview_text.append("Queued plot types:")
            for plot_type in self._selected_single_plot_types() + self._selected_collection_plot_types():
                preview_text.append(
                    f"  - {self._plot_type_label(plot_type)} - {self._plot_data_source_label(plot_type)}"
                )
            preview_text.append("")
            total_plots = (
                len(datasets_to_export) * len(self._selected_single_plot_types())
                + len(self._selected_collection_plot_types())
            ) * len(plot_formats)
            preview_text.append(f"Total: {total_plots} plot file(s) will be created")
            preview_text.append(f"  ({len(datasets_to_export)} datasets × {len(plot_formats)} format(s))")

        if not preview_text:
            preview_text.append("Click format cards on the left to select what to export")
            preview_text.append("")
            preview_text.append("Available formats:")
            preview_text.append("  CSV Long - One row per K-value result")
            preview_text.append("  CSV Wide - Statistical analysis format")
            preview_text.append("  Excel - Multi-sheet workbooks")
            preview_text.append("  PNG - High-resolution plots")
            preview_text.append("  SVG - Vector plots")
            preview_text.append("  PDF - Publication-ready plots")

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
        preview_lines.append("EXPORT PREVIEW")
        preview_lines.append("=" * 60)
        preview_lines.append("")

        # Analyze datasets
        total_datasets = len(datasets_to_export)
        datasets_with_k_results = 0
        total_k_results = 0

        preview_lines.append(f"DATASETS ({total_datasets} total)")
        preview_lines.append("-" * 60)

        for name, dataset, results in datasets_to_export:
            k_count = len(results) if results else 0
            if k_count > 0:
                datasets_with_k_results += 1
                total_k_results += k_count

            # Get key grain sizes
            d10 = dataset.get_d10() if hasattr(dataset, 'get_d10') else None
            d50 = dataset.get_d50() if hasattr(dataset, 'get_d50') else None

            status = "OK" if k_count > 0 else "MISSING"
            preview_lines.append(f"  {status} {name}")
            if d10 and d50:
                preview_lines.append(f"      D10={d10:.3f}mm, D50={d50:.3f}mm")
            if k_count > 0:
                preview_lines.append(f"      {k_count} K-calculation results available")
            else:
                preview_lines.append("      No K-calculation results - run calculations first")

        preview_lines.append("")
        preview_lines.append(f"Summary: {datasets_with_k_results}/{total_datasets} datasets have K-results")
        preview_lines.append(f"Total K-calculations: {total_k_results}")
        preview_lines.append("")

        # Estimate files to be created
        preview_lines.append("FILES TO BE CREATED")
        preview_lines.append("-" * 60)

        file_count = 0

        # Use new selected_formats dict
        if self.selected_formats.get('csv_long'):
            preview_lines.append("  - CSV Long Format: 1 file")
            file_count += 1
        if self.selected_formats.get('csv_wide'):
            preview_lines.append("  - CSV Wide Format: 1 file")
            file_count += 1

        if self.selected_formats.get('excel'):
            preview_lines.append(f"  - Excel workbooks: {total_datasets} files (one per dataset)")
            file_count += total_datasets

        if self._plot_exports_enabled():
            plot_formats = len(self._selected_plot_formats())
            count = (
                total_datasets * len(self._selected_single_plot_types())
                + len(self._selected_collection_plot_types())
            ) * plot_formats
            preview_lines.append(f"  - Plot files: ~{count} files ({plot_formats} formats × {total_datasets} datasets)")
            for plot_type in self._selected_single_plot_types() + self._selected_collection_plot_types():
                preview_lines.append(
                    f"      {self._plot_type_label(plot_type)} - {self._plot_data_source_label(plot_type)}"
                )
            file_count += count

        preview_lines.append("")
        preview_lines.append(f"Total estimated files: ~{file_count}")
        preview_lines.append("")

        # Output settings
        preview_lines.append("OUTPUT SETTINGS")
        preview_lines.append("-" * 60)
        preview_lines.append(f"Directory: {self.output_dir.text()}")

        preview_lines.append("")

        # Content selection - use new content_enabled dict
        preview_lines.append("CONTENT INCLUDED")
        preview_lines.append("-" * 60)
        content_items = []
        if self.content_enabled.get('grain_data', True):
            content_items.append("Grain size distribution data")
        if self.content_selection['k_values']['enabled']:
            content_items.append("K-value results (all methods)")
        if self.content_enabled.get('statistics', True):
            content_items.append("Statistical summaries")
        if self._plot_exports_enabled():
            content_items.append("Plots/figures (figure files; active plot data exports from plot table drawers)")

        for item in content_items:
            preview_lines.append(f"  - {item}")

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
        if self.content_selection['k_values']['enabled']:
            datasets_without_k = []
            for name, dataset, results in datasets_to_export:
                if not results or len(results) == 0:
                    datasets_without_k.append(name)

            if datasets_without_k:
                warning_msg = "Some datasets don't have K-calculation results yet:\n\n"
                for name in datasets_without_k[:5]:  # Show first 5
                    warning_msg += f"  - {name}\n"
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

        progress_dialog = LoadingDialog(
            "Exporting results",
            "Writing selected grain-size outputs to a structured export folder.",
            self,
            cancellable=False,
        )
        progress_dialog.set_activity("Creating tables, workbooks, and report-ready plot files.")
        progress = ExportProgressAdapter(progress_dialog)
        progress_dialog.show()
        QApplication.processEvents()

        try:
            self.export_started.emit()

            # Perform export
            exported_files = manager.export(datasets_to_export, config, progress)

            progress_dialog.mark_finished(
                "Export complete",
                f"{len(exported_files)} files written to the selected export folder.",
                ok=True,
            )
            QApplication.processEvents()
            progress_dialog.close()

            # Show success message
            file_list = "\n".join([
                f"  - {os.path.relpath(f, output_dir)}"
                for f in exported_files[:10]
            ])
            if len(exported_files) > 10:
                file_list += f"\n  ... and {len(exported_files) - 10} more"

            QMessageBox.information(
                self,
                "Export Successful",
                f"Successfully exported {len(exported_files)} file(s) to:\n{output_dir}\n\nFiles:\n{file_list}"
            )

            self.export_completed.emit(output_dir)

        except Exception as e:
            progress_dialog.mark_finished("Export failed", str(e), ok=False)
            QApplication.processEvents()
            progress_dialog.close()
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
        return [
            self.datasets[idx]
            for idx in self._selected_dataset_indices()
            if 0 <= idx < len(self.datasets)
        ]

    def _get_plot_figures_to_export(self) -> List[Any]:
        """Return plot figures aligned to the dataset export selection."""
        return [
            self.plot_figures[idx]
            for idx in self._selected_dataset_indices()
            if 0 <= idx < len(self.plot_figures)
        ]

    def _get_plot_contexts_to_export(self) -> List[Dict[str, Any]]:
        """Return plot contexts aligned to the dataset export selection."""
        return [
            self.plot_contexts[idx]
            for idx in self._selected_dataset_indices()
            if 0 <= idx < len(self.plot_contexts)
        ]

    def _build_export_config(self) -> Dict:
        """Build export configuration dictionary"""
        grain_size_config = self.content_selection['grain_size']
        grain_size_items = grain_size_config['items']
        grain_size_enabled = grain_size_config['enabled']
        percentiles_config = grain_size_items['percentiles']
        percentiles_enabled = grain_size_enabled and percentiles_config['enabled']
        gradation_config = grain_size_items['gradation']

        k_values_config = self.content_selection['k_values']
        k_values_enabled = k_values_config['enabled']

        statistics_config = self.content_selection['statistics']
        statistics_items = statistics_config['items']
        statistics_enabled = statistics_config['enabled']
        k_value_stats_config = statistics_items['k_value_stats']
        k_value_stats_enabled = statistics_enabled and k_value_stats_config['enabled']

        metadata_config = self.content_selection['metadata']
        metadata_items = metadata_config['items']
        metadata_enabled = metadata_config['enabled']

        plots_config = self.content_selection['plots']
        plots_items = plots_config['items']
        plots_enabled = (
            plots_config['enabled']
            and bool(self._selected_plot_types())
        )
        config = {
            # Formats - using new selected_formats dict
            'csv': self.selected_formats.get('csv_long') or self.selected_formats.get('csv_wide'),
            'csv_mode': 'combined',  # Always combined in new design
            'csv_long': self.selected_formats.get('csv_long', False),
            'csv_wide': self.selected_formats.get('csv_wide', False),

            'excel': self.selected_formats.get('excel', False),
            'excel_mode': 'per_dataset',  # Default mode

            'json': False,

            'png': self.selected_formats.get('png', False),
            'png_dpi': 300,  # Default DPI

            'svg': self.selected_formats.get('svg', False),
            'pdf_plot': self.selected_formats.get('pdf', False),

            # Content - using granular content_selection structure
            'grain_distribution': grain_size_enabled and grain_size_items['raw_distribution'],
            'percentiles': percentiles_enabled,
            'gradation': grain_size_enabled and gradation_config['enabled'],
            'classification': grain_size_enabled and grain_size_items['classification'],
            'k_values': k_values_enabled,
            'statistics': statistics_enabled,
            'plots': plots_enabled,
            'selected_plot_types': self._selected_plot_types(),
            'plot_include_legend': plots_items.get('include_legend', True),
            'plot_include_grid': plots_items.get('include_grid', True),
            'formulas': k_values_enabled and k_values_config['include_formulas'],
            'validation': k_values_enabled and k_values_config['include_validation'],

            # Granular selections (NEW)
            'k_filter_mode': k_values_config['filter_mode'],
            'selected_k_categories': dict(k_values_config['categories']) if k_values_enabled else {},
            'selected_percentiles': [
                p for p, enabled in percentiles_config['items'].items()
                if percentiles_enabled and enabled
            ],
            'selected_k_methods': [
                method for method, enabled in k_values_config['individual_methods'].items()
                if k_values_enabled and enabled
            ] if k_values_config['filter_mode'] == 'individual' else None,
            'k_units': {
                'm_s': k_values_config['units']['m_s'],
                'cm_s': k_values_config['units']['cm_s'],
                'm_d': k_values_config['units']['m_d'],
            },
            'selected_statistics': [
                stat for stat, enabled in k_value_stats_config['items'].items()
                if enabled
            ] if k_value_stats_enabled else [],
            'include_grain_size_stats': grain_size_enabled and statistics_enabled and statistics_items['grain_size_stats'],
            'include_metadata': {
                'sample_info': metadata_enabled and metadata_items['sample_info'],
                'environmental': metadata_enabled and metadata_items['environmental'],
                'export_timestamp': metadata_enabled and metadata_items['export_timestamp'],
            },

            # Output
            'output_dir': self.output_dir.text(),
            'filename_template': '{sample_name}_results_{date}',  # Default template
            'collection_sample_name': self._collection_sample_name(),
            'enforce_folder_structure': True,
            'expected_file_count': self._estimate_export_file_count(),
        }

        if self._plot_exports_enabled():
            config['plot_figures'] = self._get_plot_figures_to_export()
            config['plot_contexts'] = self._get_plot_contexts_to_export()

        return config
