from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
import polars as pl

from components.ui.frameless_dialog_base import FramelessDialogBase


class DropEmptyRowsDialog(FramelessDialogBase):
    def __init__(self, parent, columns, df):
        super().__init__(parent, default_mode="auto")
        self.columns = columns
        self.df = df
        self.setWindowTitle("Drop Empty Rows")
        self.setup_ui()

    def _chrome_tokens(self) -> dict:
        return {
            "bg_elevated": "#f8fafc",
            "border_default": "#e5e7eb",
            "text_primary": "#111827",
            "text_tertiary": "#6b7280",
            "text_muted": "#6b7280",
            "accent_ghost": "#fee2e2",
            "accent_light": "#dc2626",
            "r_md": "8px",
            "r_sm": "6px",
        }

    def setup_ui(self):
        root_layout = QVBoxLayout(self)
        layout = root_layout
        chrome_header = None
        resize_targets = []

        if self._is_frameless_active():
            root_layout.setSpacing(0)
            root_layout.setContentsMargins(1, 1, 1, 1)
            chrome_header = self.build_chrome_titlebar(
                tokens=self._chrome_tokens(),
                title="Drop Empty Rows",
                subtitle="Remove rows with null values in selected columns",
                icon_name="trash",
                icon_text="D",
                on_close=self.reject,
            )
            root_layout.addWidget(chrome_header)

            content = QFrame()
            content.setStyleSheet("background: white;")
            layout = QVBoxLayout(content)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(10)
            root_layout.addWidget(content, 1)
            resize_targets = [content]
        else:
            root_layout.setContentsMargins(12, 12, 12, 12)
            root_layout.setSpacing(10)

        # Columns selection
        self.columns_list = QListWidget()
        self.columns_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.columns_list.addItems(self.columns)
        layout.addWidget(QLabel("Select columns to check for empty rows:"))
        layout.addWidget(self.columns_list)

        # Select All and Clear All buttons
        buttons_layout = QHBoxLayout()
        select_all_button = QPushButton("Select All")
        select_all_button.clicked.connect(self.select_all)
        clear_all_button = QPushButton("Clear All")
        clear_all_button.clicked.connect(self.clear_all)
        buttons_layout.addWidget(select_all_button)
        buttons_layout.addWidget(clear_all_button)
        layout.addLayout(buttons_layout)

        # Drop condition
        self.condition_combo = QComboBox()
        self.condition_combo.addItems(["All selected columns are empty", "Any selected column is empty"])
        layout.addWidget(QLabel("Drop condition:"))
        layout.addWidget(self.condition_combo)

        # Preview button
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self.show_preview)
        layout.addWidget(self.preview_button)

        # OK and Cancel buttons
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        dialog_buttons.accepted.connect(self.validate_and_accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

        self.install_chrome_behavior(
            header_widget=chrome_header,
            resize_widgets=resize_targets,
            corner_radius=10,
            resize_margin=8,
        )

    def select_all(self):
        for index in range(self.columns_list.count()):
            item = self.columns_list.item(index)
            item.setSelected(True)

    def clear_all(self):
        self.columns_list.clearSelection()

    def show_preview(self):
        selected_columns = self.get_selected_columns()
        if not selected_columns:
            QMessageBox.warning(self, "No Columns Selected", "Please select at least one column.")
            return

        condition = 'all' if self.condition_combo.currentIndex() == 0 else 'any'
        
        # Polars version of checking for null values    
        null_mask = self.df.select([pl.col(col).is_null() for col in selected_columns])
        
        try:
            if condition == 'all':
                rows_to_drop = null_mask.select(pl.all_horizontal()).to_series()
            else:  # 'any'
                rows_to_drop = null_mask.select(pl.any_horizontal()).to_series()

            total_rows = len(self.df)
            rows_dropped = rows_to_drop.sum()
            remaining_rows = total_rows - rows_dropped

        except pl.ComputeError:
            # This occurs when there are no rows that meet the condition
            total_rows = len(self.df)
            rows_dropped = 0
            remaining_rows = total_rows

        QMessageBox.information(self, "Preview", 
                                f"Total rows: {total_rows}\n"
                                f"Rows to be dropped: {rows_dropped}\n"
                                f"Remaining rows: {remaining_rows}")

    def validate_and_accept(self):
        if not self.columns_list.selectedItems():
            QMessageBox.warning(self, "No Columns Selected", "Please select at least one column.")
            return
        self.accept()

    def get_selected_columns(self):
        return [item.text() for item in self.columns_list.selectedItems()]

    def get_selections(self):
        return {
            'columns': self.get_selected_columns(),
            'condition': 'all' if self.condition_combo.currentIndex() == 0 else 'any'
        } 
