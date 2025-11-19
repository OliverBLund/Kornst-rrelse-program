"""
Control panel widget for data import and analysis controls
"""

from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QGroupBox,
                            QPushButton, QLabel, QLineEdit, QComboBox,
                            QTableWidget, QTableWidgetItem, QTextEdit,
                            QProgressBar, QCheckBox, QSpinBox, QDoubleSpinBox,
                            QListWidget, QListWidgetItem, QSplitter, QWidget,
                            QFileDialog, QMessageBox, QHeaderView, QApplication,
                            QMenu, QDialog, QDialogButtonBox)
from PyQt6.QtCore import QThread, QTimer
from data_loader import DataLoader
from gui.column_mapper import ColumnMapperDialog
import os
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QAction


class PorosityDialog(QDialog):
    """
    Dialog for managing porosity settings across all datasets
    Each dataset can have its own porosity value
    """

    porosity_updated = pyqtSignal(str, float)  # dataset_name, new_porosity

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Porosity Settings - Per Dataset")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        self.init_ui()
        self.load_dataset_porosity_values()

    def init_ui(self):
        """Initialize dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header with instructions
        header_label = QLabel(
            "<b>Manage Porosity for Each Dataset</b><br>"
            "Porosity affects K-value calculations. Each dataset can have its own porosity value."
        )
        header_label.setStyleSheet("""
            QLabel {
                font-size: 11pt;
                color: #2c5530;
                padding: 10px;
                background-color: #f5f5f0;
                border: 1px solid #d4c4a8;
                border-radius: 4px;
            }
        """)
        header_label.setWordWrap(True)
        layout.addWidget(header_label)

        # Table showing all datasets and their porosity values
        self.porosity_table = QTableWidget(0, 5)
        self.porosity_table.setHorizontalHeaderLabels([
            "Dataset", "Calculated Porosity", "Current Porosity", "Edit", "Actions"
        ])

        # Configure table
        self.porosity_table.setAlternatingRowColors(True)
        self.porosity_table.verticalHeader().setVisible(False)
        self.porosity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # Set column widths
        header = self.porosity_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Dataset name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Calculated
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Current
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # Edit field
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # Actions
        self.porosity_table.setColumnWidth(3, 180)  # Increased from 120 for better input widget display
        self.porosity_table.setColumnWidth(4, 200)  # Increased from 150 for button spacing

        self.porosity_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                font-size: 10pt;
                background-color: white;
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
        """)

        layout.addWidget(self.porosity_table)

        # Info label at bottom
        self.info_label = QLabel("💡 Tip: Use 'Update' to apply changes to individual datasets, or 'Apply All' to save all changes at once.")
        self.info_label.setStyleSheet("""
            QLabel {
                font-size: 9pt;
                color: #666;
                font-style: italic;
                padding: 6px;
            }
        """)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # Dialog buttons
        button_box = QDialogButtonBox()

        apply_all_btn = QPushButton("Apply All Changes")
        apply_all_btn.clicked.connect(self.apply_all_changes)
        apply_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b8e23;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7fa02d;
            }
        """)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #d2b48c;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ddbf94;
            }
        """)

        button_box.addButton(apply_all_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)

        layout.addWidget(button_box)

    def load_dataset_porosity_values(self):
        """Load all datasets and their current porosity values"""
        self.porosity_table.setRowCount(0)

        if not hasattr(self.main_window, 'dataset_tabs_widget'):
            print(f"DEBUG: main_window does not have dataset_tabs_widget attribute")
            self.info_label.setText("⚠️ Error: Could not access dataset tabs")
            return

        tab_count = self.main_window.dataset_tabs_widget.count()
        print(f"DEBUG: Found {tab_count} tabs in main window")
        dataset_count = 0

        # Iterate through all tabs
        for i in range(tab_count):
            tab = self.main_window.dataset_tabs_widget.widget(i)

            # Skip non-dataset tabs
            if not hasattr(tab, 'dataset'):
                print(f"DEBUG: Tab {i} does not have dataset attribute (type: {type(tab).__name__})")
                continue

            dataset_count += 1
            print(f"DEBUG: Found dataset tab {dataset_count}: {tab.dataset.sample_name}")

            dataset = tab.dataset
            dataset_name = dataset.sample_name

            # Get porosity values
            calculated_porosity = getattr(dataset, 'calculated_porosity', None)
            current_porosity = getattr(dataset, 'current_porosity', None)

            if current_porosity is None:
                current_porosity = calculated_porosity if calculated_porosity else 0.40

            # Add row to table
            row = self.porosity_table.rowCount()
            self.porosity_table.insertRow(row)

            # Dataset name
            name_item = QTableWidgetItem(dataset_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.porosity_table.setItem(row, 0, name_item)

            # Calculated porosity
            if calculated_porosity:
                calc_item = QTableWidgetItem(f"{calculated_porosity:.4f}")
            else:
                calc_item = QTableWidgetItem("N/A")
            calc_item.setFlags(calc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            calc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.porosity_table.setItem(row, 1, calc_item)

            # Current porosity
            current_item = QTableWidgetItem(f"{current_porosity:.4f}")
            current_item.setFlags(current_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            current_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.porosity_table.setItem(row, 2, current_item)

            # Edit field
            edit_field = QLineEdit()
            edit_field.setText(f"{current_porosity:.4f}")
            edit_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit_field.setStyleSheet("""
                QLineEdit {
                    padding: 4px;
                    border: 1px solid #c0c0c0;
                    border-radius: 3px;
                    font-family: 'Consolas', monospace;
                }
            """)
            self.porosity_table.setCellWidget(row, 3, edit_field)

            # Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(4)

            update_btn = QPushButton("Update")
            update_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6b8e23;
                    color: white;
                    padding: 4px 8px;
                    font-size: 9pt;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #7fa02d;
                }
            """)
            update_btn.clicked.connect(lambda checked, r=row: self.update_single_dataset(r))

            reset_btn = QPushButton("Reset")
            reset_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d2b48c;
                    padding: 4px 8px;
                    font-size: 9pt;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #ddbf94;
                }
            """)
            reset_btn.clicked.connect(lambda checked, r=row: self.reset_single_dataset(r))

            if calculated_porosity is None:
                reset_btn.setEnabled(False)

            action_layout.addWidget(update_btn)
            action_layout.addWidget(reset_btn)

            self.porosity_table.setCellWidget(row, 4, action_widget)

        # Update info label with summary
        if dataset_count == 0:
            self.info_label.setText("⚠️ No datasets found. Please load some data files first.")
        else:
            self.info_label.setText(f"📊 Loaded {dataset_count} dataset(s). Edit porosity values and click 'Update' or 'Apply All'.")

    def update_single_dataset(self, row: int):
        """Update porosity for a single dataset"""
        dataset_name = self.porosity_table.item(row, 0).text()
        edit_field = self.porosity_table.cellWidget(row, 3)

        try:
            new_porosity = float(edit_field.text())

            if not (0.1 <= new_porosity <= 0.8):
                QMessageBox.warning(
                    self,
                    "Invalid Porosity",
                    "Porosity must be between 0.1 and 0.8"
                )
                return

            # Find the tab and update
            for i in range(self.main_window.dataset_tabs_widget.count()):
                tab = self.main_window.dataset_tabs_widget.widget(i)
                if hasattr(tab, 'dataset') and tab.dataset.sample_name == dataset_name:
                    # Update dataset porosity
                    tab.dataset.current_porosity = new_porosity
                    tab.porosity = new_porosity

                    # Update statistics tab if it exists
                    if hasattr(tab, 'statistics_tab'):
                        tab.statistics_tab.porosity = new_porosity
                        tab.statistics_tab.update_display()

                    # Recalculate K-values
                    if hasattr(tab, 'calculate_k_values') and hasattr(tab, 'current_results') and tab.current_results:
                        tab.calculate_k_values()

                    break

            # Update table display
            current_item = self.porosity_table.item(row, 2)
            current_item.setText(f"{new_porosity:.4f}")

            self.info_label.setText(f"✅ Updated {dataset_name} to porosity {new_porosity:.4f}")

        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number")

    def reset_single_dataset(self, row: int):
        """Reset porosity to calculated value for a single dataset"""
        dataset_name = self.porosity_table.item(row, 0).text()
        calc_item = self.porosity_table.item(row, 1)

        if calc_item.text() == "N/A":
            QMessageBox.information(
                self,
                "No Calculated Value",
                "This dataset doesn't have a calculated porosity value."
            )
            return

        calculated_porosity = float(calc_item.text())

        # Update the tab
        for i in range(self.main_window.dataset_tabs_widget.count()):
            tab = self.main_window.dataset_tabs_widget.widget(i)
            if hasattr(tab, 'dataset') and tab.dataset.sample_name == dataset_name:
                tab.dataset.current_porosity = calculated_porosity
                tab.porosity = calculated_porosity

                # Update statistics tab
                if hasattr(tab, 'statistics_tab'):
                    tab.statistics_tab.porosity = calculated_porosity
                    tab.statistics_tab.update_display()

                # Recalculate K-values
                if hasattr(tab, 'calculate_k_values') and hasattr(tab, 'current_results') and tab.current_results:
                    tab.calculate_k_values()

                break

        # Update table display
        edit_field = self.porosity_table.cellWidget(row, 3)
        edit_field.setText(f"{calculated_porosity:.4f}")

        current_item = self.porosity_table.item(row, 2)
        current_item.setText(f"{calculated_porosity:.4f}")

        self.info_label.setText(f"✅ Reset {dataset_name} to calculated value {calculated_porosity:.4f}")

    def apply_all_changes(self):
        """Apply all porosity changes at once"""
        changes_made = 0

        for row in range(self.porosity_table.rowCount()):
            dataset_name = self.porosity_table.item(row, 0).text()
            edit_field = self.porosity_table.cellWidget(row, 3)
            current_item = self.porosity_table.item(row, 2)

            try:
                new_porosity = float(edit_field.text())
                current_porosity = float(current_item.text())

                # Only update if changed
                if abs(new_porosity - current_porosity) > 0.0001:
                    if not (0.1 <= new_porosity <= 0.8):
                        QMessageBox.warning(
                            self,
                            "Invalid Porosity",
                            f"Porosity for {dataset_name} must be between 0.1 and 0.8"
                        )
                        continue

                    # Update the tab
                    for i in range(self.main_window.dataset_tabs_widget.count()):
                        tab = self.main_window.dataset_tabs_widget.widget(i)
                        if hasattr(tab, 'dataset') and tab.dataset.sample_name == dataset_name:
                            tab.dataset.current_porosity = new_porosity
                            tab.porosity = new_porosity

                            # Update statistics tab
                            if hasattr(tab, 'statistics_tab'):
                                tab.statistics_tab.porosity = new_porosity
                                tab.statistics_tab.update_display()

                            # Recalculate K-values
                            if hasattr(tab, 'calculate_k_values') and hasattr(tab, 'current_results') and tab.current_results:
                                tab.calculate_k_values()

                            changes_made += 1
                            break

                    # Update table
                    current_item.setText(f"{new_porosity:.4f}")

            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    f"Invalid porosity value for {dataset_name}"
                )
                continue

        if changes_made > 0:
            QMessageBox.information(
                self,
                "Changes Applied",
                f"Updated porosity for {changes_made} dataset(s).\nK-values have been recalculated."
            )
            self.accept()
        else:
            self.info_label.setText("ℹ️ No changes detected")


class ControlPanel(QFrame):
    # Signals for communication with main window
    files_loaded = pyqtSignal(list)  # Emitted when files are loaded
    analysis_requested = pyqtSignal(dict)  # Emitted when analysis is requested
    sample_selected = pyqtSignal(str)  # Emitted when a sample is selected
    error_dataset = pyqtSignal(str, str)  # Emitted when dataset fails to load (file_path, error_message)
    dataset_loaded_successfully = pyqtSignal(object, str)  # Emitted when dataset loads successfully (dataset, file_path)
    update_error_tab_message = pyqtSignal(str, str)  # Update existing error tab with new message
    dataset_fix_requested = pyqtSignal(str)  # Emitted when user wants to fix/remap a dataset (file_path)

    def __init__(self):
        super().__init__()
        self.loaded_samples = {}  # Dictionary to store sample data
        self.validation_errors = []  # Track validation issues
        self.data_loader = DataLoader()  # Data loading engine
        self.file_statuses = {}  # Track file loading status: 'pending', 'auto', 'failed', 'review', 'loaded'
        self.setup_ui()
        self.setup_validation()

    def setup_validation(self):
        """Setup input validation for parameters"""
        # Connect validation to parameter changes
        self.temp_spinbox.valueChanged.connect(self.validate_temperature)
        self.porosity_mode_combo.currentTextChanged.connect(self.on_porosity_mode_changed)

    def setup_ui(self):
        """Setup the control panel layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(10, 10, 10, 10)

        # Apply professional geotechnical styling
        self.setStyleSheet("""
            QFrame {
                background-color: #f5f5f0;
                border: 1px solid #d4c4a8;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #8b7355;
                border-radius: 8px;
                margin-top: 18px;
                padding-top: 18px;
                padding-left: 10px;
                padding-right: 10px;
                padding-bottom: 10px;
                background-color: #fafaf7;
                font-size: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 18px;
                top: 4px;
                padding: 4px 10px 4px 10px;
                color: #5d4e37;
                background-color: #fafaf7;
                border: 1px solid #8b7355;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton {
                background-color: #d2b48c;
                border: 1px solid #8b7355;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                color: #2f2f2f;
            }
            QPushButton:hover {
                background-color: #ddbf94;
                border-color: #6b5b47;
            }
            QPushButton:pressed {
                background-color: #c4a574;
            }
            QPushButton:disabled {
                background-color: #e8e8e5;
                color: #999999;
                border-color: #cccccc;
            }
            QListWidget, QTableWidget {
                background-color: #ffffff;
                border: 1px solid #8b7355;
                border-radius: 4px;
                selection-background-color: #d2b48c;
                gridline-color: #e0e0e0;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #d2b48c;
                color: #2f2f2f;
            }
            QHeaderView::section {
                background-color: #f0f0ed;
                color: #5d4e37;
                padding: 4px 6px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
                font-size: 10px;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                background-color: #ffffff;
                border: 1px solid #8b7355;
                border-radius: 3px;
                padding: 4px;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
                border-color: #5d4e37;
                border-width: 2px;
            }
            QProgressBar {
                border: 1px solid #8b7355;
                border-radius: 4px;
                background-color: #f0f0ed;
            }
            QProgressBar::chunk {
                background-color: #6b8e23;
                border-radius: 3px;
            }
            QCheckBox {
                color: #2f2f2f;
            }
            QCheckBox::indicator:checked {
                background-color: #6b8e23;
                border: 1px solid #5d4e37;
            }
        """)

        # === SAMPLE MANAGEMENT SECTION ===
        samples_group = QGroupBox("📁 Sample Management")
        samples_layout = QVBoxLayout(samples_group)
        samples_layout.setSpacing(8)
        samples_layout.setContentsMargins(8, 8, 8, 8)

        # File operation buttons - Primary action prominent
        primary_button_layout = QHBoxLayout()
        primary_button_layout.setSpacing(8)

        self.add_files_btn = QPushButton("➕ Add Files")
        self.add_files_btn.clicked.connect(self.add_files)
        self.add_files_btn.setToolTip("Add one or more grain size data files")
        self.add_files_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b8e23;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #7ba428;
            }
            QPushButton:pressed {
                background-color: #5a7a1e;
            }
        """)

        # Secondary actions - smaller and less prominent
        secondary_buttons_layout = QHBoxLayout()
        secondary_buttons_layout.setSpacing(4)

        self.remove_file_btn = QPushButton("🗑️ Remove")
        self.remove_file_btn.clicked.connect(self.remove_selected_file)
        self.remove_file_btn.setEnabled(False)
        self.remove_file_btn.setStyleSheet("font-size: 10px; padding: 4px 8px;")

        self.clear_all_btn = QPushButton("🧹 Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all_files)
        self.clear_all_btn.setStyleSheet("font-size: 10px; padding: 4px 8px;")

        secondary_buttons_layout.addWidget(self.remove_file_btn)
        secondary_buttons_layout.addWidget(self.clear_all_btn)
        secondary_buttons_layout.addStretch()

        primary_button_layout.addWidget(self.add_files_btn, 1)

        samples_layout.addLayout(primary_button_layout)
        samples_layout.addLayout(secondary_buttons_layout)

        # Sample table with status tracking - SIMPLIFIED to 2 columns
        self.samples_table = QTableWidget()
        self.samples_table.setColumnCount(2)
        self.samples_table.setHorizontalHeaderLabels(["Sample File", "Status"])
        self.samples_table.setMinimumHeight(200)
        self.samples_table.setMaximumHeight(400)
        self.samples_table.setAlternatingRowColors(True)
        self.samples_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.samples_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        # Enable context menu
        self.samples_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.samples_table.customContextMenuRequested.connect(self.show_context_menu)

        # Set column widths
        header = self.samples_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # File name - stretch to fill
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Status - fit content

        self.samples_table.itemSelectionChanged.connect(self.on_sample_selection_changed)
        self.samples_table.setToolTip("Right-click on a file for options")

        # Sample info display
        self.sample_info_label = QLabel("No samples loaded")
        self.sample_info_label.setStyleSheet("""
            color: #666666;
            font-style: italic;
            font-size: 10px;
            padding: 4px;
            background-color: #f8f8f6;
            border: 1px solid #e0e0e0;
            border-radius: 3px;
            margin-top: 4px;
        """)

        samples_layout.addWidget(self.samples_table)

        # Batch action buttons - Organized by purpose
        batch_buttons_layout = QVBoxLayout()
        batch_buttons_layout.setSpacing(4)

        self.load_auto_btn = QPushButton("✅ Load All Auto-Detected Files")
        self.load_auto_btn.clicked.connect(self.load_auto_files)
        self.load_auto_btn.setEnabled(False)
        self.load_auto_btn.setToolTip("Load all files that were automatically detected and validated")
        self.load_auto_btn.setStyleSheet("""
            QPushButton {
                font-size: 10px;
                padding: 6px 12px;
                background-color: #5a9;
                color: white;
            }
            QPushButton:hover {
                background-color: #6ba;
            }
            QPushButton:disabled {
                background-color: #e8e8e5;
                color: #999999;
            }
        """)

        self.review_failed_btn = QPushButton("⚠️ Review Files Needing Attention")
        self.review_failed_btn.clicked.connect(self.review_failed_files)
        self.review_failed_btn.setEnabled(False)
        self.review_failed_btn.setToolTip("Review and manually map files that failed auto-loading")
        self.review_failed_btn.setStyleSheet("""
            QPushButton {
                font-size: 10px;
                padding: 6px 12px;
                background-color: #f39c12;
                color: white;
            }
            QPushButton:hover {
                background-color: #f5ab35;
            }
            QPushButton:disabled {
                background-color: #e8e8e5;
                color: #999999;
            }
        """)

        batch_buttons_layout.addWidget(self.load_auto_btn)
        batch_buttons_layout.addWidget(self.review_failed_btn)

        samples_layout.addLayout(batch_buttons_layout)
        samples_layout.addWidget(self.sample_info_label)

        # === ANALYSIS PARAMETERS (Collapsible) ===
        params_group = QGroupBox("⚙️ Analysis Parameters")
        params_group.setCheckable(True)
        params_group.setChecked(False)  # Collapsed by default
        params_layout = QVBoxLayout(params_group)
        params_layout.setSpacing(8)
        params_layout.setContentsMargins(8, 8, 8, 8)

        # Global parameters (apply to all samples)
        global_params_label = QLabel("Global Parameters (applied to all samples):")
        global_params_label.setFont(QFont("", 9, QFont.Weight.Bold))
        global_params_label.setStyleSheet("color: #5d4e37; margin-bottom: 6px;")
        params_layout.addWidget(global_params_label)

        # Temperature for viscosity calculations
        temp_layout = QHBoxLayout()
        temp_layout.setSpacing(8)
        temp_label = QLabel("🌡️ Temperature:")
        temp_label.setMinimumWidth(90)
        temp_layout.addWidget(temp_label)
        self.temp_spinbox = QDoubleSpinBox()
        self.temp_spinbox.setRange(0, 50)
        self.temp_spinbox.setValue(20)
        self.temp_spinbox.setSuffix(" °C")
        self.temp_spinbox.setToolTip("Temperature affects water viscosity in calculations")
        self.temp_spinbox.setMinimumWidth(80)
        temp_layout.addWidget(self.temp_spinbox)
        temp_layout.addStretch()

        # Porosity Calculation Mode
        porosity_layout = QHBoxLayout()
        porosity_layout.setSpacing(8)
        porosity_label = QLabel("🕳️ Porosity Mode:")
        porosity_label.setMinimumWidth(90)
        porosity_layout.addWidget(porosity_label)
        self.porosity_mode_combo = QComboBox()
        self.porosity_mode_combo.addItems([
            "Simple Formula (Excel Compatible)",
            "Urumovic Polynomial (Research)"
        ])
        self.porosity_mode_combo.setCurrentIndex(0)  # Default to Excel compatible
        self.porosity_mode_combo.setToolTip("Choose porosity calculation method:\nSimple: n = 0.255 * (1 + 0.83^U)\nUrumovic: Complex polynomial based on grain size distribution")
        porosity_layout.addWidget(self.porosity_mode_combo)
        porosity_layout.addStretch()

        params_layout.addLayout(temp_layout)
        params_layout.addLayout(porosity_layout)

        # Porosity Settings Button
        porosity_settings_layout = QHBoxLayout()
        porosity_settings_layout.setSpacing(8)

        self.porosity_settings_btn = QPushButton("🕳️ Manage Dataset Porosity...")
        self.porosity_settings_btn.clicked.connect(self.open_porosity_dialog)
        self.porosity_settings_btn.setToolTip("Edit porosity values for each dataset individually")
        self.porosity_settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b8e23;
                color: white;
                padding: 8px 12px;
                font-size: 10pt;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7fa02d;
            }
        """)
        porosity_settings_layout.addWidget(self.porosity_settings_btn)
        porosity_settings_layout.addStretch()

        params_layout.addLayout(porosity_settings_layout)

        # Optional: auto-export toggle used by analysis_complete()
        params_layout.addSpacing(6)
        self.export_results_cb = QCheckBox("📤 Auto-export results after analysis")
        self.export_results_cb.setChecked(False)
        self.export_results_cb.setToolTip("If enabled, results will be exported automatically after analysis")
        self.export_results_cb.setStyleSheet("font-size: 10px; color: #5d4e37;")
        params_layout.addWidget(self.export_results_cb)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)

        # Add all groups to main layout
        layout.addWidget(samples_group)
        layout.addWidget(params_group)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        layout.addStretch()  # Push everything to top

    def add_files(self):
        """Add multiple files for batch processing"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Grain Size Data Files",
            "",
            "All Supported (*.csv *.xlsx *.xls);;CSV files (*.csv);;Excel files (*.xlsx *.xls);;All files (*.*)"
        )

        if file_paths:
            newly_added = []
            already_added = []

            for file_path in file_paths:
                if file_path not in self.file_statuses:
                    # Add to file tracking
                    self.file_statuses[file_path] = 'pending'
                    newly_added.append(file_path)
                else:
                    already_added.append(os.path.basename(file_path))

            if newly_added:
                # Add files to table
                for file_path in newly_added:
                    self.add_file_to_table(file_path, 'pending')

                # Create tabs immediately for all files, then try to load them
                self.process_files_with_immediate_tabs(newly_added)

                self.update_ui_state()

                # Provide feedback on what was processed
                message = f"Processing {len(newly_added)} new file(s)..."
                if already_added:
                    if len(already_added) <= 3:
                        message += f" (Skipped: {', '.join(already_added)})"
                    else:
                        message += f" (Skipped {len(already_added)} duplicate files)"

                self.sample_info_label.setText(message)
            else:
                if len(already_added) == 1:
                    QMessageBox.information(self, "No New Files", f"'{already_added[0]}' is already in the list.")
                else:
                    QMessageBox.information(self, "No New Files", f"All {len(already_added)} selected files are already in the list.")

    def add_file_to_table(self, file_path: str, status: str):
        """Add a file to the samples table"""
        row = self.samples_table.rowCount()
        self.samples_table.insertRow(row)

        # File name
        file_name = os.path.basename(file_path)
        file_item = QTableWidgetItem(file_name)
        file_item.setData(Qt.ItemDataRole.UserRole, file_path)  # Store full path
        file_item.setToolTip(file_path)
        self.samples_table.setItem(row, 0, file_item)

        # Status with icon and text
        status_text = self.get_status_text(status)
        status_item = QTableWidgetItem(status_text)
        status_item.setData(Qt.ItemDataRole.UserRole, status)
        status_item.setToolTip(self.get_status_tooltip(status))
        self.samples_table.setItem(row, 1, status_item)

    def get_status_icon(self, status: str) -> str:
        """Get icon for file status"""
        icons = {
            'pending': '🔄',
            'auto': '✅',
            'failed': '❌',
            'review': '⚠️',
            'loaded': '📄'
        }
        return icons.get(status, '❓')

    def get_status_text(self, status: str) -> str:
        """Get descriptive status text with icon"""
        status_map = {
            'pending': '🔄 Processing...',
            'auto': '✅ Auto-loaded',
            'failed': '❌ Failed',
            'review': '⚠️ Needs Review',
            'loaded': '📄 Loaded'
        }
        return status_map.get(status, '❓ Unknown')

    def get_status_tooltip(self, status: str) -> str:
        """Get tooltip text for status"""
        tooltip_map = {
            'pending': 'File is being processed',
            'auto': 'File was automatically loaded and validated',
            'failed': 'File failed validation - contains errors',
            'review': 'File needs manual column mapping',
            'loaded': 'File successfully loaded and ready for analysis'
        }
        return tooltip_map.get(status, 'Unknown status')

    def show_context_menu(self, position):
        """Show context menu for file operations"""
        # Get the selected row
        item = self.samples_table.itemAt(position)
        if item is None:
            return

        row = item.row()
        file_item = self.samples_table.item(row, 0)
        status_item = self.samples_table.item(row, 1)

        if not file_item or not status_item:
            return

        file_path = file_item.data(Qt.ItemDataRole.UserRole)
        status = status_item.data(Qt.ItemDataRole.UserRole)

        # Create context menu
        menu = QMenu(self)

        # Add actions based on status
        if status == 'review':
            map_action = QAction("🗺️ Map Columns...", self)
            map_action.triggered.connect(lambda: self.edit_file_mapping(file_path))
            menu.addAction(map_action)

        elif status in ['auto', 'loaded']:
            info_action = QAction("ℹ️ Show Info...", self)
            info_action.triggered.connect(lambda: self.show_file_info(file_path))
            menu.addAction(info_action)

            menu.addSeparator()

            edit_action = QAction("✏️ Edit Mapping...", self)
            edit_action.triggered.connect(lambda: self.edit_file_mapping(file_path))
            menu.addAction(edit_action)

        elif status == 'failed':
            fix_action = QAction("🔧 Fix/Remap...", self)
            fix_action.triggered.connect(lambda: self.edit_file_mapping(file_path))
            menu.addAction(fix_action)

        # Always show remove option
        menu.addSeparator()
        remove_action = QAction("🗑️ Remove from List", self)
        remove_action.triggered.connect(lambda: self.remove_file_at_row(row))
        menu.addAction(remove_action)

        # Show menu at cursor position
        menu.exec(self.samples_table.viewport().mapToGlobal(position))

    def remove_file_at_row(self, row: int):
        """Remove a file at a specific row"""
        if row >= 0:
            # Get file path
            file_item = self.samples_table.item(row, 0)
            file_path = file_item.data(Qt.ItemDataRole.UserRole)

            # Remove from tracking
            if file_path in self.file_statuses:
                del self.file_statuses[file_path]

            # Remove from loaded samples
            sample_name = self.extract_sample_name(file_path)
            if sample_name in self.loaded_samples:
                del self.loaded_samples[sample_name]

            # Remove from table
            self.samples_table.removeRow(row)

            self.update_ui_state()
            self.sample_info_label.setText(f"🗑️ Removed: {os.path.basename(file_path)}")

    def edit_file_mapping(self, file_path: str):
        """Open column mapping dialog for a specific file"""
        try:
            dialog = ColumnMapperDialog(file_path, self)
            if dialog.exec() == QMessageBox.StandardButton.Ok.value:
                # Get mapped data
                result = dialog.get_mapping_result()

                # Create dataset
                from data_loader import GrainSizeData
                dataset = GrainSizeData(
                    sample_name=result['sample_name'],
                    temperature=result['temperature'],
                    porosity=result['porosity'],
                    particle_sizes=result['particle_sizes'],
                    percent_passing=result['percent_passing'],
                    file_path=file_path
                )

                # Store as loaded
                sample_name = result['sample_name']
                self.loaded_samples[sample_name] = {
                    'file_path': file_path,
                    'data': dataset,
                    'status': 'loaded'
                }

                # Update status
                self.file_statuses[file_path] = 'loaded'
                self.update_file_in_table(file_path, 'loaded')

                self.sample_info_label.setText(f"✅ Updated: {os.path.basename(file_path)}")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to edit {os.path.basename(file_path)}:\n{str(e)}")

    def show_file_info(self, file_path: str):
        """Show detailed information about a loaded file"""
        sample_name = self.extract_sample_name(file_path)
        if sample_name in self.loaded_samples:
            dataset = self.loaded_samples[sample_name]['data']

            d10 = dataset.get_d10()
            d30 = dataset.get_d30()
            d50 = dataset.get_d50()
            d60 = dataset.get_d60()
            cu = dataset.get_uniformity_coefficient()

            def fmt(value, fmt_str):
                return format(value, fmt_str) if value is not None else 'N/A'

            # Create comprehensive file information
            info_text = f"""File Analysis Report
{'='*40}

📄 File: {os.path.basename(file_path)}
🏷️  Sample: {dataset.sample_name}
🌡️ Temperature: {dataset.temperature}°C
🕳️ Porosity: {dataset.porosity}
📊 Data Points: {len(dataset.particle_sizes)}

Grain Size Range:
  Largest: {max(dataset.particle_sizes):.3f} mm
  Smallest: {min(dataset.particle_sizes):.3f} mm

Characteristic Sizes:
  D10: {fmt(d10, '.3f')} mm (Used by: Hazen, Terzaghi, Beyer, etc.)
  D30: {fmt(d30, '.3f')} mm (Used for uniformity calculations)
  D50: {fmt(d50, '.3f')} mm (Median grain size)
  D60: {fmt(d60, '.3f')} mm (Used for uniformity coefficient)

Soil Classification: {dataset.classify_soil()}
Uniformity Coefficient (Cu): {fmt(cu, '.2f')}

{'='*40}
{dataset.get_detailed_validation_report()}"""

            # Show in a dialog
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(f"File Information - {sample_name}")
            msg_box.setText(info_text)
            msg_box.setFont(QFont("Courier", 8))  # Monospace font for alignment
            msg_box.resize(600, 400)  # Make dialog larger
            msg_box.exec()

    def batch_auto_load(self, file_paths: list):
        """Attempt to auto-load all files in the list"""
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setMaximum(len(file_paths) * 3)  # 3 steps per file

        auto_loaded = 0
        failed_files = 0

        for i, file_path in enumerate(file_paths):
            base_progress = i * 3
            file_name = os.path.basename(file_path)

            # Step 1: Detecting format
            self.progress_bar.setValue(base_progress)
            self.progress_label.setText(f"🔍 Analyzing {file_name}...")
            QApplication.processEvents()  # Update UI

            try:
                # Step 2: Loading data
                self.progress_bar.setValue(base_progress + 1)
                self.progress_label.setText(f"📊 Loading {file_name}...")
                QApplication.processEvents()  # Update UI
                # Attempt to auto-load
                dataset = self.data_loader.load_file(file_path)

                # Step 3: Validating and processing
                self.progress_bar.setValue(base_progress + 2)
                self.progress_label.setText(f"✅ Validating {file_name}...")
                QApplication.processEvents()  # Update UI

                # Success - mark as auto-loaded, but check for validation issues
                sample_name = self.extract_sample_name(file_path)

                # Determine status based on validation messages
                if dataset.has_errors():
                    status = 'failed'
                    failed_files += 1
                elif dataset.has_warnings():
                    status = 'auto'  # Still usable, but with warnings
                    auto_loaded += 1
                else:
                    status = 'auto'
                    auto_loaded += 1

                self.file_statuses[file_path] = status
                self.loaded_samples[sample_name] = {
                    'file_path': file_path,
                    'data': dataset,
                    'status': status
                }

                # Update table with detailed info
                self.update_file_in_table(file_path, status)

            except Exception as e:
                # Failed - mark for review with specific error info
                self.file_statuses[file_path] = 'review'

                # Create user-friendly error message
                error_str = str(e)
                if "could not parse" in error_str.lower():
                    detailed_error = "Could not auto-detect column format"
                elif "no valid" in error_str.lower():
                    detailed_error = "No valid grain size data found in file"
                elif "delimiter" in error_str.lower():
                    detailed_error = "Could not determine file delimiter format"
                else:
                    detailed_error = str(e)

                # Update table for sidebar status
                self.update_file_in_table(file_path, 'review')

                # Emit signal to create error tab
                self.error_dataset.emit(file_path, detailed_error)

                failed_files += 1

        # Final progress update
        self.progress_bar.setValue(len(file_paths) * 3)
        self.progress_label.setText("🎉 Batch processing complete!")
        QApplication.processEvents()

        # Small delay to show completion
        QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))
        QTimer.singleShot(1000, lambda: self.progress_label.setVisible(False))

        # Update summary with detailed feedback
        if auto_loaded > 0 and failed_files == 0:
            summary = f"🎉 Successfully loaded all {auto_loaded} file{'s' if auto_loaded != 1 else ''}!"
        elif auto_loaded > 0 and failed_files > 0:
            summary = f"✅ {auto_loaded} loaded successfully, ⚠️ {failed_files} need review"
        elif failed_files > 0:
            summary = f"⚠️ {failed_files} file{'s' if failed_files != 1 else ''} need manual mapping"
        else:
            summary = "No files processed"

        self.sample_info_label.setText(summary)
        self.update_ui_state()

    def update_file_in_table(self, file_path: str, status: str):
        """Update file status in table"""
        for row in range(self.samples_table.rowCount()):
            file_item = self.samples_table.item(row, 0)
            if file_item and file_item.data(Qt.ItemDataRole.UserRole) == file_path:
                # Update status
                status_item = self.samples_table.item(row, 1)
                status_item.setText(self.get_status_text(status))
                status_item.setData(Qt.ItemDataRole.UserRole, status)
                status_item.setToolTip(self.get_status_tooltip(status))
                break

    def load_auto_files(self):
        """Load all successfully auto-processed files into the analysis"""
        auto_files = [path for path, status in self.file_statuses.items() if status == 'auto']
        if auto_files:
            loaded_datasets = []
            for file_path in auto_files:
                sample_name = self.extract_sample_name(file_path)
                if sample_name in self.loaded_samples:
                    loaded_datasets.append(self.loaded_samples[sample_name]['data'])

            if loaded_datasets:
                self.files_loaded.emit([ds.sample_name for ds in loaded_datasets])
                self.sample_info_label.setText(f"✅ Loaded {len(loaded_datasets)} dataset(s) for analysis")

    def review_failed_files(self):
        """Open manual column mapping for files that need review"""
        review_files = [path for path, status in self.file_statuses.items() if status == 'review']

        for file_path in review_files:
            try:
                # Open column mapper dialog
                dialog = ColumnMapperDialog(file_path, self)
                if dialog.exec() == QMessageBox.StandardButton.Ok.value:
                    # Get mapped data
                    result = dialog.get_mapping_result()

                    # Create dataset
                    from data_loader import GrainSizeData
                    dataset = GrainSizeData(
                        sample_name=result['sample_name'],
                        temperature=result['temperature'],
                        porosity=result['porosity'],
                        particle_sizes=result['particle_sizes'],
                        percent_passing=result['percent_passing'],
                        file_path=file_path
                    )

                    # Store as loaded
                    sample_name = result['sample_name']
                    self.loaded_samples[sample_name] = {
                        'file_path': file_path,
                        'data': dataset,
                        'status': 'loaded'
                    }

                    # Update status
                    self.file_statuses[file_path] = 'loaded'
                    self.update_file_in_table(file_path, 'loaded')

            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to process {os.path.basename(file_path)}:\n{str(e)}")

        self.update_ui_state()

    def remove_selected_file(self):
        """Remove selected file from the table"""
        current_row = self.samples_table.currentRow()
        if current_row >= 0:
            # Get file path
            file_item = self.samples_table.item(current_row, 0)
            file_path = file_item.data(Qt.ItemDataRole.UserRole)

            # Remove from tracking
            if file_path in self.file_statuses:
                del self.file_statuses[file_path]

            # Remove from loaded samples
            sample_name = self.extract_sample_name(file_path)
            if sample_name in self.loaded_samples:
                del self.loaded_samples[sample_name]

            # Remove from table
            self.samples_table.removeRow(current_row)

            self.update_ui_state()
            self.sample_info_label.setText(f"🗑️ Removed: {os.path.basename(file_path)}")
        else:
            self.remove_file_btn.setEnabled(False)

    def clear_all_files(self):
        """Clear all loaded files"""
        total_files = len(self.file_statuses)
        if total_files > 0:
            reply = QMessageBox.question(
                self, "Clear All",
                f"Remove all {total_files} files?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.loaded_samples.clear()
                self.file_statuses.clear()
                self.samples_table.setRowCount(0)
                self.update_ui_state()
                self.sample_info_label.setText("🧹 All files cleared")

    def on_sample_selection_changed(self):
        """Handle sample selection change"""
        current_row = self.samples_table.currentRow()
        if current_row >= 0:
            file_item = self.samples_table.item(current_row, 0)
            file_path = file_item.data(Qt.ItemDataRole.UserRole)
            status_item = self.samples_table.item(current_row, 1)
            status = status_item.data(Qt.ItemDataRole.UserRole)

            # Update sample info
            file_name = os.path.basename(file_path)
            self.sample_info_label.setText(f"Selected: {file_name} ({status})")

            # Update UI state
            self.remove_file_btn.setEnabled(True)

            # If this is a loaded dataset, emit signal
            sample_name = self.extract_sample_name(file_path)
            if sample_name in self.loaded_samples and status in ['auto', 'loaded']:
                self.sample_selected.emit(sample_name)
        else:
            self.remove_file_btn.setEnabled(False)


    def extract_sample_name(self, file_path):
        """Extract a clean sample name from file path"""
        import os
        base_name = os.path.basename(file_path)
        # Remove extension
        name = os.path.splitext(base_name)[0]
        # Clean up common prefixes/suffixes
        name = name.replace('_grainsize', '').replace('_sieve', '').replace('_data', '')
        return name if name else base_name

    def update_ui_state(self):
        """Update UI state based on loaded samples and file statuses"""
        has_files = len(self.file_statuses) > 0
        has_selection = self.samples_table.currentRow() >= 0

        # Count files by status
        auto_count = sum(1 for status in self.file_statuses.values() if status == 'auto')
        review_count = sum(1 for status in self.file_statuses.values() if status == 'review')
        loaded_count = sum(1 for status in self.file_statuses.values() if status == 'loaded')

        # Update batch action buttons
        self.load_auto_btn.setEnabled(auto_count > 0)
        self.review_failed_btn.setEnabled(review_count > 0)

        # Basic UI state
        self.remove_file_btn.setEnabled(has_selection)

        # If no manual status update, show file counts
        if has_files and not hasattr(self, '_manual_status_update'):
            if auto_count > 0 or loaded_count > 0:
                summary = f"📊 {auto_count + loaded_count} ready"
                if review_count > 0:
                    summary += f", {review_count} need review"
            else:
                summary = f"{len(self.file_statuses)} file(s) added"

            if not self.sample_info_label.text().startswith(("Processing", "✅", "⚠️", "🗑️", "🧹")):
                self.sample_info_label.setText(summary)

        # Trigger validation to determine if analysis buttons should be enabled
        self.perform_full_validation()



    def _is_numeric(self, value: str) -> bool:
        """Check if a string represents a number"""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def update_analysis_progress(self, current, total, current_sample=""):
        """Update progress bar during analysis"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)

            if current_sample:
                self.progress_label.setText(f"🔄 Analyzing: {current_sample} ({current}/{total})")
            else:
                self.progress_label.setText(f"🔄 Processing... ({current}/{total})")

    def analysis_complete(self, results):
        """Called when analysis is complete"""
        self.show_progress(False)

        # Update sample statuses
        for sample_name in results:
            if sample_name in self.loaded_samples:
                self.loaded_samples[sample_name]['status'] = 'Analyzed'

        # Update UI
        success_count = len(results)
        self.progress_label.setText(f"✅ Analysis complete! {success_count} sample(s) processed")

        # Auto-export if enabled
        if self.export_results_cb.isChecked():
            self.progress_label.setText(f"✅ Analysis complete! Results exported for {success_count} sample(s)")

    def get_analysis_parameters(self):
        """Get current analysis parameters"""
        return {
            'temperature': self.temp_spinbox.value(),
            'porosity_mode': self.porosity_mode_combo.currentText(),
            'auto_export': self.export_results_cb.isChecked()
        }

    def get_loaded_samples(self):
        """Get dictionary of loaded samples"""
        return self.loaded_samples.copy()

    def set_sample_status(self, sample_name, status):
        """Update the status of a specific sample"""
        if sample_name in self.loaded_samples:
            self.loaded_samples[sample_name]['status'] = status
            file_path = self.loaded_samples[sample_name]['file_path']

            # Update file status tracking and table
            if file_path in self.file_statuses:
                self.file_statuses[file_path] = status
                self.update_file_in_table(file_path, status)

    def show_progress(self, show=True):
        """Show/hide progress bar"""
        self.progress_bar.setVisible(show)

    def set_progress(self, value):
        """Set progress bar value (0-100)"""
        self.progress_bar.setValue(value)

    # ================================
    # VALIDATION METHODS
    # ================================

    def validate_temperature(self, value):
        """Validate temperature input"""
        self.validation_errors = [err for err in self.validation_errors if 'Temperature' not in err]

        if value < 0 or value > 50:
            self.validation_errors.append("🌡️ Temperature should be between 0-50°C for realistic conditions")
        elif value < 5:
            self.validation_errors.append("⚠️ Temperature below 5°C may affect viscosity calculations")
        elif value > 35:
            self.validation_errors.append("⚠️ Temperature above 35°C is unusual for groundwater")

        self.update_validation_display()

    def on_porosity_mode_changed(self, mode_text):
        """Handle porosity calculation mode change"""
        # Determine which calculation mode is selected
        use_simple_formula = "Simple Formula" in mode_text

        # Update all loaded datasets to use the new porosity calculation mode
        if hasattr(self.parent(), 'dataset_tabs_widget'):
            main_window = self.parent()
            for i in range(main_window.dataset_tabs_widget.count()):
                tab = main_window.dataset_tabs_widget.widget(i)
                if hasattr(tab, 'dataset') and hasattr(tab.dataset, 'recalculate_porosity'):
                    # Recalculate porosity using the selected method
                    if use_simple_formula:
                        new_porosity = tab.dataset._calculate_simple_porosity()
                    else:
                        new_porosity = tab.dataset._calculate_urumovic_porosity()

                    if new_porosity is not None:
                        tab.dataset.current_porosity = new_porosity
                        # Update the dataset tab UI if it has porosity controls
                        if hasattr(tab, 'update_grain_statistics'):
                            tab.update_grain_statistics()
                        if hasattr(tab, 'porosity_edit'):
                            tab.porosity_edit.setText(f"{new_porosity:.3f}")
                            tab.porosity = new_porosity

    def validate_porosity_mode(self):
        """Validate porosity calculation mode selection"""
        self.validation_errors = [err for err in self.validation_errors if 'Porosity' not in err]

        current_mode = self.porosity_mode_combo.currentText()
        if not current_mode or current_mode not in ["Simple Formula (Excel Compatible)", "Urumovic Polynomial (Research)"]:
            self.validation_errors.append("🕳️ Please select a valid porosity calculation mode")

        self.update_validation_display()

    def validate_column_mapping(self):
        """Column mapping validation - simplified since we auto-detect"""
        pass

    def validate_samples(self):
        """Validate that samples are loaded and ready"""
        self.validation_errors = [err for err in self.validation_errors if 'Sample' not in err]

        if not self.loaded_samples:
            self.validation_errors.append("📁 Samples: No samples loaded - please add data files")
        else:
            for sample_name, sample_data in self.loaded_samples.items():
                if sample_data['status'] == 'Error':
                    self.validation_errors.append(f"❌ Sample '{sample_name}': Failed to load properly")

        self.update_validation_display()

    def update_validation_display(self):
        """Update the validation status display"""
        if not self.validation_errors:
            pass  # Validation passed

            # Enable analysis if we have samples
            if self.loaded_samples:
                pass  # Samples ready
                if self.samples_table.currentRow() >= 0:
                    pass  # Sample selected
        else:
            # Show the most critical errors (limit to 3)
            display_errors = self.validation_errors[:3]
            error_text = "\n".join(display_errors)
            if len(self.validation_errors) > 3:
                error_text += f"\n... and {len(self.validation_errors) - 3} more issues"

            pass  # Show validation errors in status bar if needed

            # Disable analysis if there are critical errors
            critical_errors = [err for err in self.validation_errors if '❌' in err or 'should be' in err]
            if critical_errors:
                pass  # No samples
                pass  # No sample selected

    def perform_full_validation(self):
        """Perform complete validation of all parameters"""
        self.validation_errors.clear()

        # Validate all components
        self.validate_temperature(self.temp_spinbox.value())
        self.validate_porosity_mode()
        self.validate_samples()

        return len([err for err in self.validation_errors if '❌' in err or 'should be' in err]) == 0

    def open_porosity_dialog(self):
        """Open the porosity management dialog"""
        # Get reference to main window - traverse up to find the actual main window
        main_window = self.window()

        # Debug: Check if we found the right window
        if not hasattr(main_window, 'dataset_tabs_widget'):
            print(f"Warning: Could not find main window with dataset_tabs_widget. Found: {type(main_window)}")
            QMessageBox.warning(
                self,
                "No Datasets",
                "No datasets are currently loaded. Please load some data files first."
            )
            return

        # Create and show dialog
        dialog = PorosityDialog(main_window, self)
        dialog.exec()

    # ================================
    # FILE PREVIEW / VALIDATION
    # ================================
    def load_file_preview(self, file_path: str) -> None:
        """Validate the given file and update UI/sample status.

        This provides a lightweight preview/validation step after adding files.
        """
        try:
            # Lazy import to avoid any potential import cycles
            from data_loader import DataLoader
            data_loader = DataLoader()
            is_valid, message = data_loader.validate_file_format(file_path)

            # Find the corresponding sample name
            sample_name = None
            for name, info in self.loaded_samples.items():
                if info.get('file_path') == file_path:
                    sample_name = name
                    break

            if is_valid:
                if sample_name:
                    self.set_sample_status(sample_name, f"✅ {message}")
                self.sample_info_label.setText(f"Preview OK: {sample_name or file_path}\n{message}")
            else:
                if sample_name:
                    self.set_sample_status(sample_name, f"❌ {message}")
                self.sample_info_label.setText(f"Preview Error: {sample_name or file_path}\n{message}")
        except Exception as e:
            # Best-effort UI update on unexpected errors
            self.sample_info_label.setText(f"Preview failed: {e}")

    def process_files_with_immediate_tabs(self, file_paths: list):
        """Process files by creating tabs immediately, then attempting to load data"""
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setMaximum(len(file_paths))

        for i, file_path in enumerate(file_paths):
            file_name = os.path.basename(file_path)

            # Update progress
            self.progress_bar.setValue(i)
            self.progress_label.setText(f"Processing {file_name}...")
            QApplication.processEvents()  # Update UI

            # Step 1: Create tab immediately for visual feedback
            self.error_dataset.emit(file_path, "Loading...")

            # Step 2: Try to load the data
            try:
                dataset = self.data_loader.load_file(file_path)

                # Success! Replace error tab with dataset tab
                sample_name = self.extract_sample_name(file_path)

                # Determine status based on validation messages
                if dataset.has_errors():
                    status = 'failed'
                    # Keep as error tab but with validation info
                    detailed_error = f"Data loaded but has validation errors"
                    self.update_error_tab_message.emit(file_path, detailed_error)
                else:
                    status = 'auto'
                    # Replace error tab with normal dataset tab
                    self.dataset_loaded_successfully.emit(dataset, file_path)

                self.file_statuses[file_path] = status
                self.loaded_samples[sample_name] = {
                    'file_path': file_path,
                    'data': dataset,
                    'status': status
                }
                self.update_file_in_table(file_path, status)

            except Exception as e:
                # Failed - update error tab with real error message
                self.file_statuses[file_path] = 'review'

                error_str = str(e)
                if "could not parse" in error_str.lower():
                    detailed_error = "Could not auto-detect column format"
                elif "no valid" in error_str.lower():
                    detailed_error = "No valid grain size data found in file"
                elif "delimiter" in error_str.lower():
                    detailed_error = "Could not determine file delimiter format"
                else:
                    detailed_error = str(e)

                self.update_file_in_table(file_path, 'review')
                # Update the existing error tab with real error
                self.update_error_tab_message.emit(file_path, detailed_error)

        # Final progress update
        self.progress_bar.setValue(len(file_paths))
        self.progress_label.setText("🎉 Processing complete!")

        # Hide progress indicators
        import time
        time.sleep(0.5)  # Brief pause to show completion
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
