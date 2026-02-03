"""
Sheet selection dialog for multi-sheet Excel workbooks
Shows before column mapper to let user select which sheets to import
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QPushButton, QListWidget, QListWidgetItem,
                            QDialogButtonBox, QGroupBox)
from PyQt6.QtCore import Qt
from typing import List
import pandas as pd


class SheetSelectorDialog(QDialog):
    """Dialog for selecting sheets from a multi-sheet Excel workbook"""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.selected_sheets = []

        self.setWindowTitle(f"Select Sheets to Import")
        self.setModal(True)
        self.resize(500, 400)

        # Apply professional styling
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f0;
            }
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
            QLabel {
                color: #2f2f2f;
                font-size: 11px;
            }
            QPushButton {
                background-color: #8b7355;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6d5a42;
            }
            QPushButton:pressed {
                background-color: #5a4835;
            }
            QListWidget {
                background-color: white;
                border: 1px solid #8b7355;
                border-radius: 3px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e0e0e0;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #d4e8d4;
                color: #2f2f2f;
            }
        """)

        self.setup_ui()
        self.load_sheets()

    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)

        # Header label
        header = QLabel(
            f"<b>Multiple sheets detected in workbook</b><br>"
            f"Select which sheets contain grain size data to import.<br>"
            f"Each sheet will be imported as a separate sample."
        )
        header.setWordWrap(True)
        header.setStyleSheet("font-size: 12px; color: #2c5530; padding: 10px;")
        layout.addWidget(header)

        # Sheet list group
        sheet_group = QGroupBox("Available Sheets")
        sheet_layout = QVBoxLayout(sheet_group)

        self.sheet_list = QListWidget()
        self.sheet_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        sheet_layout.addWidget(self.sheet_list)

        # Quick selection buttons
        button_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self.set_all_checks(True))
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(lambda: self.set_all_checks(False))
        button_row.addWidget(select_all_btn)
        button_row.addWidget(clear_btn)
        button_row.addStretch()
        sheet_layout.addLayout(button_row)

        layout.addWidget(sheet_group)

        # Info label
        self.info_label = QLabel(
            "💡 Tip: You can then use 'Apply Pattern to Batch' to map all selected sheets at once."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(self.info_label)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def load_sheets(self):
        """Load sheet names from the Excel file"""
        try:
            excel_file = pd.ExcelFile(self.file_path)
            sheet_names = excel_file.sheet_names

            for sheet_name in sheet_names:
                item = QListWidgetItem(sheet_name)
                item.setCheckState(Qt.CheckState.Checked)  # Default: all checked
                item.setFlags(
                    item.flags() |
                    Qt.ItemFlag.ItemIsUserCheckable |
                    Qt.ItemFlag.ItemIsEnabled
                )
                self.sheet_list.addItem(item)

            # Update info label
            if len(sheet_names) == 1:
                self.info_label.setText("ℹ️ This workbook has only one sheet.")
            else:
                self.info_label.setText(
                    f"📊 Found {len(sheet_names)} sheets. "
                    f"💡 Tip: You can use 'Apply Pattern to Batch' to map them all at once."
                )

        except Exception as e:
            self.info_label.setText(f"⚠️ Error reading workbook: {str(e)}")
            self.info_label.setStyleSheet("color: #d32f2f; font-weight: bold; padding: 5px;")

    def set_all_checks(self, checked: bool):
        """Check or uncheck all sheet items"""
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.sheet_list.count()):
            item = self.sheet_list.item(i)
            item.setCheckState(state)

    def get_selected_sheets(self) -> List[str]:
        """Get list of selected sheet names"""
        selected = []
        for i in range(self.sheet_list.count()):
            item = self.sheet_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected

    def accept(self):
        """Override accept to validate selection"""
        self.selected_sheets = self.get_selected_sheets()
        if not self.selected_sheets:
            self.info_label.setText("⚠️ Please select at least one sheet to import.")
            self.info_label.setStyleSheet("color: #d32f2f; font-weight: bold; padding: 5px;")
            return
        super().accept()
