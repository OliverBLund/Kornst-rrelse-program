"""
Dataset selection dialog for comparison tab when many datasets are loaded
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QCheckBox,
    QDialogButtonBox, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from typing import List


class DatasetSelectionDialog(QDialog):
    """Dialog for selecting datasets to compare when many datasets are available"""

    def __init__(self, dataset_tabs: List, currently_selected: List = None, parent=None):
        super().__init__(parent)
        self.dataset_tabs = dataset_tabs
        self.currently_selected = currently_selected or []
        self.selected_tabs = []

        self.setWindowTitle("Select Datasets to Compare")
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
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
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
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #8b7355;
                border-radius: 4px;
                selection-background-color: #d2b48c;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #e0e0e0;
            }
            QListWidget::item:selected {
                background-color: #d2b48c;
                color: #2f2f2f;
            }
            QListWidget::item:hover {
                background-color: #e6d7c3;
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
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #8b7355;
                border-radius: 3px;
                padding: 4px;
            }
            QLineEdit:focus {
                border-color: #5d4e37;
                border-width: 2px;
            }
        """)

        self.setup_ui()
        self.populate_datasets()

    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header info
        info_label = QLabel(f"Select datasets to compare from {len(self.dataset_tabs)} loaded datasets:")
        info_label.setStyleSheet("font-weight: bold; color: #5d4e37; margin-bottom: 6px;")
        layout.addWidget(info_label)

        # Search and filter section
        search_group = QGroupBox("🔍 Search & Filter")
        search_layout = QVBoxLayout(search_group)
        search_layout.setSpacing(8)

        # Search box
        search_layout_h = QHBoxLayout()
        search_layout_h.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Type to filter dataset names...")
        self.search_box.textChanged.connect(self.filter_datasets)
        search_layout_h.addWidget(self.search_box)
        search_layout.addLayout(search_layout_h)

        # Quick selection buttons
        quick_buttons_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.clicked.connect(self.select_none)
        self.invert_btn = QPushButton("Invert Selection")
        self.invert_btn.clicked.connect(self.invert_selection)

        quick_buttons_layout.addWidget(self.select_all_btn)
        quick_buttons_layout.addWidget(self.select_none_btn)
        quick_buttons_layout.addWidget(self.invert_btn)
        quick_buttons_layout.addStretch()

        search_layout.addLayout(quick_buttons_layout)
        layout.addWidget(search_group)

        # Dataset list
        datasets_group = QGroupBox("📊 Available Datasets")
        datasets_layout = QVBoxLayout(datasets_group)

        self.dataset_list = QListWidget()
        self.dataset_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        datasets_layout.addWidget(self.dataset_list)

        # Selection count
        self.selection_label = QLabel("0 datasets selected")
        self.selection_label.setStyleSheet("color: #666; font-style: italic; margin-top: 4px;")
        datasets_layout.addWidget(self.selection_label)

        layout.addWidget(datasets_group)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # Add validation to OK button
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)  # Start disabled

        layout.addWidget(button_box)

        # Connect selection change to update validation
        self.dataset_list.itemSelectionChanged.connect(self.update_selection_info)

    def populate_datasets(self):
        """Populate the dataset list"""
        for tab in self.dataset_tabs:
            item = QListWidgetItem(tab.get_dataset_name())
            item.setData(Qt.ItemDataRole.UserRole, tab)  # Store tab reference
            self.dataset_list.addItem(item)

            # Check if this tab was previously selected
            if tab in self.currently_selected:
                item.setSelected(True)

        self.update_selection_info()

    def filter_datasets(self, search_text: str):
        """Filter datasets based on search text"""
        search_text = search_text.lower()

        for i in range(self.dataset_list.count()):
            item = self.dataset_list.item(i)
            tab = item.data(Qt.ItemDataRole.UserRole)
            dataset_name = tab.get_dataset_name().lower()

            # Show/hide based on search match
            item.setHidden(search_text not in dataset_name)

    def select_all(self):
        """Select all visible datasets"""
        for i in range(self.dataset_list.count()):
            item = self.dataset_list.item(i)
            if not item.isHidden():
                item.setSelected(True)

    def select_none(self):
        """Deselect all datasets"""
        self.dataset_list.clearSelection()

    def invert_selection(self):
        """Invert the current selection"""
        for i in range(self.dataset_list.count()):
            item = self.dataset_list.item(i)
            if not item.isHidden():
                item.setSelected(not item.isSelected())

    def update_selection_info(self):
        """Update selection count and validation"""
        selected_count = len(self.dataset_list.selectedItems())

        # Update label
        if selected_count == 0:
            self.selection_label.setText("No datasets selected")
            self.selection_label.setStyleSheet("color: #d32f2f; font-style: italic; margin-top: 4px;")
        elif selected_count == 1:
            self.selection_label.setText("1 dataset selected (need at least 2 to compare)")
            self.selection_label.setStyleSheet("color: #ff9800; font-style: italic; margin-top: 4px;")
        else:
            self.selection_label.setText(f"{selected_count} datasets selected")
            self.selection_label.setStyleSheet("color: #4caf50; font-style: italic; margin-top: 4px;")

        # Enable/disable OK button
        self.ok_button.setEnabled(selected_count >= 2)

    def accept(self):
        """Accept dialog and store selected tabs"""
        selected_items = self.dataset_list.selectedItems()

        if len(selected_items) < 2:
            QMessageBox.warning(
                self,
                "Invalid Selection",
                "Please select at least 2 datasets to compare."
            )
            return

        # Store selected tabs
        self.selected_tabs = []
        for item in selected_items:
            tab = item.data(Qt.ItemDataRole.UserRole)
            self.selected_tabs.append(tab)

        super().accept()

    def get_selected_tabs(self) -> List:
        """Get the selected dataset tabs"""
        return self.selected_tabs