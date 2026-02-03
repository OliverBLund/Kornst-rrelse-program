"""
Error tab widget for datasets that failed to load
Provides fix functionality and data preview
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit, QGroupBox,
    QMessageBox, QFrame, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import csv
import os
from typing import Optional
from gui.column_mapper import ColumnMapperDialog
from data_loader import GrainSizeData


class ErrorTab(QWidget):
    """Tab widget for datasets that failed to load"""

    # Signal emitted when dataset is successfully fixed
    dataset_fixed = pyqtSignal(object, str)  # dataset or list of datasets, original_file_path

    def __init__(self, file_path: str, error_message: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path  # May be "path:::sheet_name" format
        self.error_message = error_message

        # Parse file path and sheet name if present
        if ":::" in file_path:
            actual_path, self.sheet_name = file_path.split(":::", 1)
            self.actual_file_path = actual_path
            self.file_name = f"{os.path.basename(actual_path)} [{self.sheet_name}]"
        else:
            self.actual_file_path = file_path
            self.sheet_name = None
            self.file_name = os.path.basename(file_path)

        self.setup_ui()
        self.load_file_preview()

    def setup_ui(self):
        """Setup the error tab UI"""
        layout = QVBoxLayout(self)

        # Error header
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #ffebee;
                border: 1px solid #f44336;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)

        # Error title
        title_label = QLabel(f"ERROR: {self.file_name}")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #d32f2f;
                background: none;
                border: none;
            }
        """)
        header_layout.addWidget(title_label)

        # Error message
        error_label = QLabel(f"Problem: {self.error_message}")
        error_label.setWordWrap(True)
        error_label.setStyleSheet("""
            QLabel {
                color: #666;
                background: none;
                border: none;
                margin: 5px 0;
            }
        """)
        header_layout.addWidget(error_label)

        layout.addWidget(header_frame)

        # Action buttons
        button_layout = QHBoxLayout()

        self.fix_button = QPushButton("Fix Column Mapping")
        self.fix_button.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """)
        self.fix_button.clicked.connect(self.fix_dataset)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.remove_button.clicked.connect(self.remove_dataset)

        button_layout.addWidget(self.fix_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # Data preview section
        preview_group = QGroupBox("File Preview")
        preview_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #8b7355;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fafaf7;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: #f5f5f0;
            }
        """)
        preview_layout = QVBoxLayout(preview_group)

        # Preview table
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(200)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Instructions
        instructions = QLabel("""
Instructions:
• Click "Fix Column Mapping" to manually map the columns to grain size data
• The preview shows the first few rows of your file to help identify columns
• Click "Remove" if this file is not needed
        """)
        instructions.setWordWrap(True)
        instructions.setStyleSheet("""
            QLabel {
                color: #666;
                font-style: italic;
                margin: 10px;
                background-color: #f9f9f9;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        layout.addWidget(instructions)

        layout.addStretch()

        # Store references to UI elements that might need updates
        self.title_label = title_label
        self.error_label = error_label

    def update_error_message(self, new_error_message: str):
        """Update the error message without recreating the entire UI"""
        self.error_message = new_error_message
        self.error_label.setText(f"Problem: {self.error_message}")

    def load_file_preview(self):
        """Load first few rows of the file for preview"""
        try:
            file_ext = os.path.splitext(self.actual_file_path)[1].lower()
            rows = []

            if file_ext == '.csv':
                # Try different delimiters to find the best one
                delimiters = [',', ';', '\t', '|']
                best_rows = []
                max_cols = 0

                for delimiter in delimiters:
                    try:
                        with open(self.actual_file_path, 'r', encoding='utf-8') as file:
                            reader = csv.reader(file, delimiter=delimiter)
                            test_rows = []
                            for i, row in enumerate(reader):
                                if i >= 5:  # Only first 5 rows
                                    break
                                test_rows.append(row)

                            # Score this delimiter by average column count
                            if test_rows:
                                avg_cols = sum(len(row) for row in test_rows) / len(test_rows)
                                if avg_cols > max_cols:
                                    max_cols = avg_cols
                                    best_rows = test_rows
                    except:
                        continue

                rows = best_rows

            elif file_ext in ['.xlsx', '.xls']:
                try:
                    import pandas as pd
                    # Load specific sheet if sheet_name is provided
                    if self.sheet_name:
                        df = pd.read_excel(self.actual_file_path, sheet_name=self.sheet_name, nrows=5, header=None)
                    else:
                        df = pd.read_excel(self.actual_file_path, nrows=5)
                    rows = [df.columns.tolist()] + df.values.tolist()
                    rows = [[str(cell) for cell in row] for row in rows]
                except ImportError:
                    rows = [["Excel file detected", "pandas required", "to preview"]]

            if not rows:
                rows = [["No", "preview", "available"]]

            # Setup table
            max_cols = max(len(row) for row in rows) if rows else 3
            self.preview_table.setRowCount(len(rows))
            self.preview_table.setColumnCount(max_cols)

            # Set headers
            headers = [f"Column {i+1}" for i in range(max_cols)]
            self.preview_table.setHorizontalHeaderLabels(headers)

            # Fill data
            for i, row in enumerate(rows):
                for j in range(max_cols):
                    cell_value = str(row[j]) if j < len(row) else ""
                    item = QTableWidgetItem(cell_value)

                    # Highlight numeric data
                    try:
                        float(cell_value)
                        item.setBackground(QColor(200, 255, 200))  # Light green
                    except (ValueError, TypeError):
                        pass

                    self.preview_table.setItem(i, j, item)

            # Adjust column widths
            self.preview_table.resizeColumnsToContents()

        except Exception as e:
            # Show error in preview
            self.preview_table.setRowCount(1)
            self.preview_table.setColumnCount(1)
            self.preview_table.setHorizontalHeaderLabels(["Error"])
            self.preview_table.setItem(0, 0, QTableWidgetItem(f"Preview error: {str(e)}"))

    def fix_dataset(self):
        """Open column mapping dialog to fix the dataset"""
        try:
            # Find main window to pass to column mapper
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'dataset_tabs_widget'):
                main_window = main_window.parent()

            # Pass actual file path and optional sheet name to column mapper
            dialog = ColumnMapperDialog(self.actual_file_path, self, main_window,
                                       sheet_name=self.sheet_name)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                mapping_results = dialog.get_mapping_results()
                if not mapping_results:
                    QMessageBox.warning(self, "No Data", "No sheet data was extracted.")
                    return

                datasets = []
                for mapping in mapping_results:
                    # Use sheet-specific sample name if we have a sheet
                    sample_name = mapping['sample_name']
                    if self.sheet_name and not f"[{self.sheet_name}]" in sample_name:
                        sample_name = f"{sample_name} [{self.sheet_name}]"

                    dataset = GrainSizeData(
                        sample_name=sample_name,
                        temperature=mapping['temperature'],
                        porosity=mapping['porosity'],
                        particle_sizes=mapping['particle_sizes'],
                        percent_passing=mapping['percent_passing'],
                        file_path=self.file_path  # Use original file_path key
                    )
                    datasets.append(dataset)

                payload = datasets[0] if len(datasets) == 1 else datasets

                # Emit signal that dataset(s) were fixed
                self.dataset_fixed.emit(payload, self.file_path)

        except Exception as e:
            QMessageBox.critical(self, "Fix Error", f"Could not fix dataset:\n{str(e)}")

    def remove_dataset(self):
        """Remove this dataset from the interface"""
        reply = QMessageBox.question(
            self,
            "Remove Dataset",
            f"Remove {self.file_name} from the analysis?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Find and remove this tab
            parent_tab_widget = self.parent()
            if parent_tab_widget and hasattr(parent_tab_widget, 'removeTab'):
                index = parent_tab_widget.indexOf(self)
                if index >= 0:
                    parent_tab_widget.removeTab(index)
