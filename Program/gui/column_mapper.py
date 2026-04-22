"""
Column mapping dialog for CSV files with unknown formats
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
                            QDialogButtonBox, QGroupBox, QFormLayout, QSpinBox,
                            QDoubleSpinBox, QTextEdit, QTabWidget, QWidget,
                            QMessageBox, QCheckBox, QListWidget, QListWidgetItem,
                            QScrollArea, QSplitter, QFrame, QSizePolicy,
                            QAbstractScrollArea, QGridLayout, QHeaderView)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QBrush
import csv
from typing import Dict, List, Optional, Tuple
import os
from data_loader import GrainSizeData
from gui.dialog_chrome import make_dialog_header, make_dialog_footer
from gui.theme import C, F, SZ, icon as _icon
from qt_chrome.frameless_dialog_base import FramelessDialogBase

class ColumnMapperDialog(FramelessDialogBase):
    """Dialog for mapping CSV columns to grain size data"""

    def sizeHint(self):
        return QSize(1120, 740)

    def minimumSizeHint(self):
        return QSize(900, 620)

    def __init__(
        self,
        file_path: str,
        parent=None,
        main_window=None,
        sheet_name: str = None,
        initial_state: Optional[Dict] = None,
    ):
        super().__init__(parent, default_mode="auto")
        self.file_path = file_path
        self.main_window = main_window  # Direct reference to main window
        self.forced_sheet_name = sheet_name  # If provided, only work with this specific sheet
        self._initial_state = initial_state or {}
        self.column_mapping = {}
        self.sample_data = []
        self.headers = []
        self.excel_sheets = []  # Available Excel sheets
        self.sheet_list = None  # Multi-sheet selection widget
        self._excel_file = None  # Cached ExcelFile reference
        self.current_sheet = None
        self.header_row = 0  # Detected header row
        self.cell_range_mode = False  # False = column mapping, True = cell range selection
        self.smart_selection_mode = False  # Smart selection with automatic analysis
        self.raw_sieve_mode = False  # True = user provides raw sieve weighings instead of pre-calculated % passing
        self.calculated_selection_mode = "column"
        self.selected_size_range = []  # List of (row, col) tuples for size data
        self.selected_percent_range = []  # List of (row, col) tuples for percent data
        self.selected_headers = []  # List of (row, col) tuples for header cells
        self.learned_pattern = None  # Stores pattern for batch processing
        self.selection_mode_group = None
        self.selection_mode_help_label = None
        self.pathway_summary_label = None
        self.sheet_info_label = None
        self.preview_hint_label = None
        self._file_meta_label = None
        self._mapping_splitter = None
        self._sheet_group = None
        self.input_format_group = None
        self.selecting_mode = None

        # Update window title to show sheet if provided
        if sheet_name:
            self.setWindowTitle(f"Map Columns - {os.path.basename(file_path)} [{sheet_name}]")
        else:
            self.setWindowTitle(f"Map Columns - {os.path.basename(file_path)}")
        self.setModal(True)
        self.resize(1120, 740)
        self.setMinimumSize(900, 620)

        # Styling — body inherits global QSS; patch specifics here
        self.setStyleSheet(
            f"QGroupBox {{ font-weight: 600; border: 1px solid {C.BORDER}; "
            f"border-radius: 6px; margin-top: 8px; padding-top: 10px; "
            f"background: {C.BG}; font-size: {F.SZ_MD}pt; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; "
            f"padding: 0 4px; color: {C.TEXT_MID}; background: {C.BG}; }}"
            f"QLabel {{ color: {C.TEXT}; font-size: {F.SZ_MD}pt; }}"
            f"QComboBox, QSpinBox, QDoubleSpinBox {{ padding: 4px 6px; "
            f"border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
            f"background: rgba(255,255,255,.62); font-size: {F.SZ_MD}pt; }}"
            f"QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus "
            f"{{ border-color: {C.OLIVE}; }}"
        )

        try:
            self.load_csv_preview()
            self.setup_ui()
            if self._initial_state:
                self.apply_mapping_state(self._initial_state)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load CSV file:\n{str(e)}")
            self.reject()

    def load_csv_preview(self, sheet_name: Optional[str] = None):
        """Load first few rows of file for preview"""
        target_sheet = None
        if self.forced_sheet_name:
            target_sheet = self.forced_sheet_name
        else:
            target_sheet = sheet_name or self.current_sheet

        rows, excel_sheets, resolved_sheet = self.load_preview_rows(
            self.file_path,
            sheet_name=target_sheet,
            excel_sheets=self.excel_sheets,
        )
        if self.forced_sheet_name:
            self.excel_sheets = [self.forced_sheet_name]
        else:
            self.excel_sheets = excel_sheets
        self.current_sheet = resolved_sheet
        self.headers = self.detect_headers(rows)
        self.sample_data = rows[:50]

    @staticmethod
    def load_preview_rows(
        file_path: str,
        *,
        sheet_name: Optional[str] = None,
        excel_sheets: Optional[List[str]] = None,
    ) -> tuple[List[List[str]], List[str], Optional[str]]:
        """Load raw preview rows using the same strategy across preview surfaces."""
        file_ext = os.path.splitext(file_path)[1].lower()
        rows: List[List[str]] = []
        discovered_sheets = list(excel_sheets or [])
        resolved_sheet = sheet_name

        if file_ext == '.csv':
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                for i, row in enumerate(reader):
                    if i >= 50:
                        break
                    rows.append(row)
        elif file_ext in ['.xlsx', '.xls']:
            import pandas as pd

            if not discovered_sheets:
                excel_file = pd.ExcelFile(file_path)
                try:
                    discovered_sheets = list(excel_file.sheet_names)
                finally:
                    excel_file.close()

            if not resolved_sheet or resolved_sheet not in discovered_sheets:
                resolved_sheet = discovered_sheets[0] if discovered_sheets else None

            df = pd.read_excel(file_path, sheet_name=resolved_sheet, header=None, nrows=100)
            rows = df.values.tolist()
            rows = [[str(cell) if pd.notna(cell) else '' for cell in row] for row in rows]

        if not rows:
            raise ValueError("CSV file is empty")

        return rows, discovered_sheets, resolved_sheet

    def detect_headers(self, rows: List[List[str]]) -> List[str]:
        """Try to detect which row contains headers"""
        best_row = 0
        best_score = 0

        for i, row in enumerate(rows[:8]):  # Check first 8 rows for Excel files
            if len(row) >= 2:
                # Score this row based on header-like characteristics
                score = 0
                non_empty_cells = [cell.strip() for cell in row if cell.strip()]

                if len(non_empty_cells) >= 2:
                    # Check if this row looks like headers
                    text_count = sum(1 for cell in non_empty_cells if not ColumnMapperDialog.is_numeric(cell))

                    # Bonus for having text in most cells
                    if text_count >= len(non_empty_cells) * 0.6:
                        score += 10

                    # Bonus for keywords - enhanced for sieve analysis
                    header_keywords = ['size', 'diameter', 'grain', 'particle', 'sieve', 'mm', 'd mm', 'mesh',
                                     'passing', 'pass', 'finer', 'cumulative', 'retained', '%', 'procentages',
                                     'percentages', 'mass', 'weight', 'curve']
                    keyword_count = sum(1 for cell in non_empty_cells
                                       for keyword in header_keywords
                                       if keyword in cell.lower())
                    score += keyword_count * 5

                    # Penalty for rows with mostly numbers
                    numeric_count = sum(1 for cell in non_empty_cells if ColumnMapperDialog.is_numeric(cell))
                    if numeric_count > len(non_empty_cells) * 0.7:
                        score -= 5

                    if score > best_score:
                        best_score = score
                        best_row = i

        self.header_row = best_row

        if best_row < len(rows) and len(rows[best_row]) >= 2:
            headers = [cell.strip() for cell in rows[best_row]]
            # Filter out empty headers and replace with generic names
            for i, header in enumerate(headers):
                if not header or header.lower() in ['unnamed', 'nan']:
                    headers[i] = f"Column {i+1}"
            return headers

        # If no good headers detected, create generic ones
        max_cols = max(len(row) for row in rows) if rows else 2
        return [f"Column {i+1}" for i in range(max_cols)]

    @staticmethod
    def is_numeric(value_or_self, value: Optional[str] = None) -> bool:
        """Check if a string represents a number"""
        raw_value = value_or_self if value is None else value
        try:
            float(raw_value)
            return True
        except ValueError:
            return False

    def _style_mode_button(self, button: QPushButton, fa_name: str) -> None:
        button.setCheckable(True)
        button.setMinimumHeight(46)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        try:
            button.setIcon(_icon(fa_name, C.TEXT_MUTED))
        except Exception:
            pass
        button.setStyleSheet(
            f"QPushButton {{ border: 1px solid {C.BORDER}; border-radius: 6px; "
            f"background: rgba(255,255,255,.28); color: {C.TEXT_MID}; "
            f"padding: 7px 10px; text-align: left; font-weight: 600; font-size: {F.SZ_SM}pt; }}"
            f"QPushButton:hover {{ background: {C.BG_LOW}; border-color: {C.BORDER_DK}; color: {C.TEXT}; }}"
            f"QPushButton:checked {{ background: rgba(107,142,35,.08); "
            f"border-color: rgba(107,142,35,.34); color: {C.TEXT}; }}"
            f"QPushButton:disabled {{ background: rgba(255,255,255,.12); color: {C.TEXT_MUTED}; }}"
        )

    def _style_tool_button(self, button: QPushButton, fa_name: str = "", *, primary: bool = False) -> None:
        button.setMinimumHeight(30)
        if fa_name:
            try:
                button.setIcon(_icon(fa_name, "#ffffff" if primary else C.TEXT_MID))
            except Exception:
                pass
        if primary:
            button.setStyleSheet(
                f"QPushButton {{ background: {C.OLIVE}; border: 1px solid {C.OLIVE_DK}; "
                f"border-radius: {SZ.BORDER_RADIUS}px; color: white; font-weight: 600; "
                f"padding: 0 12px; }}"
                f"QPushButton:hover {{ background: {C.OLIVE_H}; }}"
                f"QPushButton:disabled {{ background: {C.BORDER}; border-color: {C.BORDER_DK}; "
                f"color: {C.TEXT_MUTED}; }}"
            )
        else:
            button.setStyleSheet(
                f"QPushButton {{ border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
                f"background: {C.BG}; color: {C.TEXT_MID}; padding: 0 12px; }}"
                f"QPushButton:hover {{ background: {C.BG_LOW}; border-color: {C.BORDER_DK}; color: {C.TEXT}; }}"
                f"QPushButton:checked {{ background: rgba(107,142,35,.08); "
                f"border-color: rgba(107,142,35,.34); color: {C.TEXT}; font-weight: 600; }}"
                f"QPushButton:disabled {{ background: {C.BG_RAISED}; color: {C.TEXT_MUTED}; }}"
            )

    def setup_ui(self):
        """Setup the dialog UI"""
        import os as _os
        fname = _os.path.basename(self.file_path)
        sheet_part = f" [{self.current_sheet}]" if self.current_sheet else ""
        subtitle = f"{fname}{sheet_part} - map columns to grain-size data"

        # Root layout — header / body / footer, no margins
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header_widget = make_dialog_header(
            "Column Mapper",
            subtitle,
            fa_icon="fa6s.table-columns",
            close_fn=self.reject,
        )
        root.addWidget(self._header_widget)

        # Body wrapper — tabs live here
        body_wrap = QWidget()
        body_wrap.setStyleSheet(f"background: {C.BG};")
        layout = QVBoxLayout(body_wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        root.addWidget(body_wrap, 1)

        # Create tab widget
        tab_widget = QTabWidget()
        tab_widget.setDocumentMode(True)
        tab_widget.setStyleSheet(
            f"QTabWidget::pane {{ border: none; }}"
            f"QTabBar::tab {{ padding: 7px 14px; min-height: 26px; color: {C.TEXT_MID}; "
            f"background: transparent; border: 1px solid transparent; border-bottom: none; }}"
            f"QTabBar::tab:selected {{ color: {C.TEXT}; background: {C.BG_RAISED}; "
            f"border-color: {C.BORDER}; font-weight: 600; }}"
        )

        # Tab 1: Column Mapping
        mapping_tab = QWidget()
        mapping_layout = QVBoxLayout(mapping_tab)
        mapping_layout.setContentsMargins(0, 0, 0, 0)
        mapping_layout.setSpacing(0)

        file_strip = self._build_file_strip()
        mapping_layout.addWidget(file_strip)

        # Add mode selector for Excel files
        if os.path.splitext(self.file_path)[1].lower() in ['.xlsx', '.xls']:
            self.selection_mode_group = QGroupBox("Selection Method")
            mode_layout = QVBoxLayout(self.selection_mode_group)
            mode_layout.setContentsMargins(10, 8, 10, 10)
            mode_layout.setSpacing(6)

            mode_button_row = QHBoxLayout()
            mode_button_row.setContentsMargins(0, 0, 0, 0)
            mode_button_row.setSpacing(8)

            self.column_mode_btn = QPushButton("Columns")
            self.range_mode_btn = QPushButton("Cell Ranges")

            self.column_mode_btn.setCheckable(True)
            self.range_mode_btn.setCheckable(True)
            self.column_mode_btn.setChecked(True)  # Default mode

            self.column_mode_btn.clicked.connect(self.switch_to_column_mode)
            self.range_mode_btn.clicked.connect(self.switch_to_range_mode)

            mode_button_row.addWidget(self.column_mode_btn)
            mode_button_row.addWidget(self.range_mode_btn)
            mode_button_row.addStretch()
            mode_layout.addLayout(mode_button_row)

            self.selection_mode_help_label = QLabel()
            self.selection_mode_help_label.setWordWrap(True)
            self.selection_mode_help_label.setStyleSheet("color: #666; font-style: italic; margin: 0 4px 2px 4px;")
            mode_layout.addWidget(self.selection_mode_help_label)

            # Added to the left inspector below.

        # Add Excel sheet selector if multiple sheets
        if len(self.excel_sheets) > 1:
            sheet_group = QGroupBox("Excel Sheets in Workbook")
            sheet_layout = QVBoxLayout(sheet_group)

            self.sheet_info_label = QLabel()
            self.sheet_info_label.setStyleSheet("color: #555; font-size: 10px;")
            self.sheet_info_label.setWordWrap(True)
            sheet_layout.addWidget(self.sheet_info_label)

            self.sheet_list = QListWidget()
            self.sheet_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
            for sheet_name in self.excel_sheets:
                item = QListWidgetItem(sheet_name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                item.setCheckState(Qt.CheckState.Checked)
                self.sheet_list.addItem(item)
                if sheet_name == self.current_sheet:
                    self.sheet_list.setCurrentItem(item)
            if self.sheet_list.count() > 0 and not self.sheet_list.currentItem():
                self.sheet_list.setCurrentRow(0)
            self.sheet_list.itemSelectionChanged.connect(self.on_sheet_selection_changed)
            sheet_layout.addWidget(self.sheet_list)

            button_row = QHBoxLayout()
            select_all_btn = QPushButton("Select All")
            select_all_btn.clicked.connect(lambda: self.set_sheet_checks(Qt.CheckState.Checked))
            clear_btn = QPushButton("Select None")
            clear_btn.clicked.connect(lambda: self.set_sheet_checks(Qt.CheckState.Unchecked))
            button_row.addWidget(select_all_btn)
            button_row.addWidget(clear_btn)
            button_row.addStretch()
            sheet_layout.addLayout(button_row)

            self._sheet_group = sheet_group

        # Input format selector (available for all file types)
        input_format_group = QGroupBox("Import Path")
        self.input_format_group = input_format_group
        input_format_layout = QHBoxLayout(input_format_group)
        input_format_layout.setContentsMargins(10, 8, 10, 10)
        input_format_layout.setSpacing(8)

        self.calculated_data_btn = QPushButton("Processed Curve")
        self.raw_sieve_btn = QPushButton("Raw Sieve")

        self.calculated_data_btn.setCheckable(True)
        self.raw_sieve_btn.setCheckable(True)
        self.calculated_data_btn.setChecked(True)

        self.calculated_data_btn.setToolTip(
            "Columns already contain Sieve Size (mm) and Cumulative % Passing"
        )
        self.raw_sieve_btn.setToolTip(
            "Columns contain Sieve Size (mm), Weight of Empty Sieve (g), and "
            "Weight of Sieve + Sample (g) — the program calculates % passing automatically"
        )

        self.calculated_data_btn.clicked.connect(self.switch_to_calculated_mode)
        self.raw_sieve_btn.clicked.connect(self.switch_to_raw_sieve_mode)

        for btn, fa_name in [
            (getattr(self, 'column_mode_btn', None), 'fa6s.table-columns'),
            (getattr(self, 'range_mode_btn', None), 'fa6s.object-group'),
            (self.calculated_data_btn, 'fa6s.chart-line'),
            (self.raw_sieve_btn, 'fa6s.scale-balanced'),
        ]:
            if btn is None:
                continue
            self._style_mode_button(btn, fa_name)

        input_format_layout.addWidget(self.calculated_data_btn)
        input_format_layout.addWidget(self.raw_sieve_btn)
        # Added to the left inspector below.

        self.pathway_summary_label = QLabel()
        self.pathway_summary_label.setWordWrap(True)
        self.pathway_summary_label.setStyleSheet(
            f"QLabel {{ border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
            f"background: {C.BG_RAISED}; color: {C.TEXT_MID}; padding: 8px 10px; }}"
        )
        # Added to the left inspector below.

        # Preview pane
        preview_group = QGroupBox("Data Preview")
        preview_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(10, 8, 10, 10)
        preview_layout.setSpacing(6)

        self.preview_hint_label = QLabel()
        self.preview_hint_label.setWordWrap(True)
        self.preview_hint_label.setStyleSheet("color: #666; font-style: italic; margin: 0 2px 2px 2px;")
        preview_layout.addWidget(self.preview_hint_label)

        self.preview_table = QTableWidget()
        self.preview_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_table.setMinimumHeight(0)
        self.preview_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.setup_preview_table()
        preview_layout.addWidget(self.preview_table, 1)

        # Smart selection controls (used in range mode)
        self.range_tools_group = QGroupBox("Selection Tools")
        range_tools_layout = QVBoxLayout(self.range_tools_group)
        range_tools_layout.setContentsMargins(10, 8, 10, 10)
        range_tools_layout.setSpacing(6)

        range_note = QLabel(
            "Use cell range selection for irregular sheets. Select the size and percent cells "
            "directly from the preview table."
        )
        range_note.setWordWrap(True)
        range_note.setStyleSheet("color: #666; font-style: italic; margin: 0 2px 2px 2px;")
        range_tools_layout.addWidget(range_note)

        self.range_controls = QWidget()
        range_controls_layout = QGridLayout(self.range_controls)
        range_controls_layout.setContentsMargins(0, 0, 0, 0)
        range_controls_layout.setHorizontalSpacing(8)
        range_controls_layout.setVerticalSpacing(8)

        self.mark_size_range_btn = QPushButton("Mark Size Cells")
        self.mark_size_range_btn.clicked.connect(lambda: self._mark_current_selection("size"))
        self._style_tool_button(self.mark_size_range_btn, "fa6s.ruler-horizontal")

        self.mark_percent_range_btn = QPushButton("Mark Passing Cells")
        self.mark_percent_range_btn.clicked.connect(lambda: self._mark_current_selection("percent"))
        self._style_tool_button(self.mark_percent_range_btn, "fa6s.percent")

        self.clear_ranges_btn = QPushButton("Clear")
        self.clear_ranges_btn.clicked.connect(self.clear_range_selection)
        self._style_tool_button(self.clear_ranges_btn, "fa6s.eraser")

        self.smart_selection_btn = QPushButton("Smart Selection")
        self.smart_selection_btn.setCheckable(True)
        self.smart_selection_btn.clicked.connect(self.toggle_smart_selection)
        self._style_tool_button(self.smart_selection_btn, "fa6s.wand-magic-sparkles")

        self.batch_apply_btn = QPushButton("Apply Pattern to Batch")
        self.batch_apply_btn.clicked.connect(self.apply_pattern_to_batch)
        self.batch_apply_btn.setEnabled(False)
        self._style_tool_button(self.batch_apply_btn, "fa6s.bolt", primary=True)

        range_controls_layout.addWidget(self.mark_size_range_btn, 0, 0)
        range_controls_layout.addWidget(self.mark_percent_range_btn, 0, 1)
        range_controls_layout.addWidget(self.smart_selection_btn, 1, 0)
        range_controls_layout.addWidget(self.clear_ranges_btn, 1, 1)
        range_controls_layout.addWidget(self.batch_apply_btn, 2, 0, 1, 2)
        range_tools_layout.addWidget(self.range_controls)

        range_counts = QWidget()
        range_counts_layout = QHBoxLayout(range_counts)
        range_counts_layout.setContentsMargins(0, 0, 0, 0)
        range_counts_layout.setSpacing(8)
        self.size_range_count_label = QLabel("0 size cells")
        self.percent_range_count_label = QLabel("0 passing cells")
        for label in (self.size_range_count_label, self.percent_range_count_label):
            label.setFont(QFont(F.MONO, F.SZ_XS))
            label.setStyleSheet(
                f"QLabel {{ border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
                f"background: {C.BG}; color: {C.TEXT_MID}; padding: 5px 8px; }}"
            )
            range_counts_layout.addWidget(label)
        range_tools_layout.addWidget(range_counts)

        self.pattern_info_label = QLabel("Select cells in the preview, then mark them as size or passing.")
        self.pattern_info_label.setWordWrap(True)
        self.pattern_info_label.setStyleSheet("color: #666; font-style: italic; margin: 0 2px 2px 2px;")
        range_tools_layout.addWidget(self.pattern_info_label)

        # Mapping group (for column mode)
        self.mapping_group = QGroupBox("Processed Curve Columns")
        mapping_form = QFormLayout(self.mapping_group)
        mapping_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        mapping_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        mapping_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        mapping_form.setContentsMargins(10, 10, 10, 10)
        mapping_form.setVerticalSpacing(8)

        # Create combo boxes for mapping
        self.size_combo = QComboBox()
        self.passing_combo = QComboBox()
        self.retained_combo = QComboBox()

        # Store style strings for validation updates
        self.required_empty_style = "border: 1px solid rgba(192,56,40,.45); background-color: rgba(192,56,40,.05);"
        self.required_filled_style = "border: 1px solid rgba(107,142,35,.40); background-color: rgba(107,142,35,.07);"
        self.optional_style = f"border: 1px solid {C.BORDER}; background-color: rgba(255,255,255,.55);"

        # Initial styling (will update after auto-detection)
        self.size_combo.setStyleSheet(f"QComboBox {{ {self.required_empty_style} padding: 5px; border-radius: 3px; }}")
        self.passing_combo.setStyleSheet(f"QComboBox {{ {self.required_empty_style} padding: 5px; border-radius: 3px; }}")
        self.retained_combo.setStyleSheet(f"QComboBox {{ {self.optional_style} padding: 5px; border-radius: 3px; }}")

        # Populate combo boxes
        column_options = ["(Not Used)"] + self.headers
        for combo in [self.size_combo, self.passing_combo, self.retained_combo]:
            combo.addItems(column_options)

        # Connect validation on change
        self.size_combo.currentIndexChanged.connect(self.validate_required_fields)
        self.passing_combo.currentIndexChanged.connect(self.validate_required_fields)
        self.retained_combo.currentIndexChanged.connect(self.validate_required_fields)

        # Try auto-detection
        self.auto_detect_columns()

        # Validate after auto-detection
        self.validate_required_fields()

        mapping_form.addRow("Particle Size (mm): *", self.size_combo)
        mapping_form.addRow("Percent Passing (%): *", self.passing_combo)
        mapping_form.addRow("Percent Retained (%) - Optional:", self.retained_combo)

        # Add header row selector for Excel files
        if os.path.splitext(self.file_path)[1].lower() in ['.xlsx', '.xls']:
            self.header_row_spin = QSpinBox()
            self.header_row_spin.setRange(0, min(10, len(self.sample_data) - 1))
            self.header_row_spin.setValue(self.header_row)
            self.header_row_spin.valueChanged.connect(self.update_headers)
            mapping_form.addRow("Header Row (0-based):", self.header_row_spin)

        # Compact guidance; detailed behavior is handled by validation and preview highlights.
        help_text = QLabel(
            "Required: particle size and percent passing. Percent retained is optional."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666; font-style: italic; margin: 10px;")
        mapping_form.addRow(help_text)
        help_text.setText(
            "Required: particle size and percent passing. Percent retained is optional and is "
            "only used when passing values are unavailable. For Excel files, verify the sheet "
            "and detected header row before importing."
        )
        help_text.setStyleSheet("color: #666; font-style: italic; margin: 4px 6px 2px 6px;")

        # Added to the left inspector below.

        # Raw Sieve Analysis group (hidden by default; visible when "Raw Sieve Weighings" mode is active)
        self.raw_sieve_group = QGroupBox("Raw Sieve Weighing Columns")
        raw_sieve_form = QFormLayout(self.raw_sieve_group)
        raw_sieve_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        raw_sieve_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        raw_sieve_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        raw_sieve_form.setContentsMargins(10, 10, 10, 10)
        raw_sieve_form.setVerticalSpacing(8)

        self.raw_size_combo = QComboBox()
        self.empty_sieve_combo = QComboBox()
        self.sieve_sample_combo = QComboBox()

        for combo in [self.raw_size_combo, self.empty_sieve_combo, self.sieve_sample_combo]:
            combo.setStyleSheet(f"QComboBox {{ {self.required_empty_style} padding: 5px; border-radius: 3px; }}")
            combo.addItems(column_options)
            combo.currentIndexChanged.connect(self.validate_required_fields)

        self._auto_detect_raw_sieve_columns()

        raw_sieve_form.addRow("Sieve Size (mm): *", self.raw_size_combo)
        raw_sieve_form.addRow("Weight of Empty Sieve (g): *", self.empty_sieve_combo)
        raw_sieve_form.addRow("Weight of Sieve + Sample (g): *", self.sieve_sample_combo)

        raw_sieve_help = QLabel(
            "Map the sieve size, empty sieve, and sieve + sample columns."
        )
        raw_sieve_help.setWordWrap(True)
        raw_sieve_help.setStyleSheet("color: #666; font-style: italic; margin: 10px;")
        raw_sieve_form.addRow(raw_sieve_help)
        raw_sieve_help.setText(
            "Map the sieve size, empty sieve, and sieve + sample columns. The program derives "
            "retained mass and cumulative percent passing automatically, and rows with non-positive "
            "retained weight are skipped."
        )
        raw_sieve_help.setStyleSheet("color: #666; font-style: italic; margin: 4px 6px 2px 6px;")

        self.raw_sieve_group.setVisible(False)
        # Added to the left inspector below.
        self.range_tools_group.setVisible(False)

        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setFrameShape(QFrame.Shape.NoFrame)
        controls_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        controls_scroll.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls_scroll.setMinimumWidth(390)
        controls_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        controls_container = QWidget()
        controls_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        controls_container.setMinimumWidth(0)
        controls_container.setObjectName("columnMapperInspector")
        controls_container.setStyleSheet(
            f"QWidget#columnMapperInspector {{ background: {C.BG_RAISED}; }}"
        )
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(10)
        if self.input_format_group is not None:
            controls_layout.addWidget(self.input_format_group)
        if self.selection_mode_group is not None:
            controls_layout.addWidget(self.selection_mode_group)
        controls_layout.addWidget(self.pathway_summary_label)
        controls_layout.addWidget(self.mapping_group)
        controls_layout.addWidget(self.range_tools_group)
        controls_layout.addWidget(self.raw_sieve_group)
        if self._sheet_group is not None:
            controls_layout.addWidget(self._sheet_group)
        controls_layout.addStretch()
        controls_scroll.setWidget(controls_container)

        self._mapping_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._mapping_splitter.setChildrenCollapsible(False)
        self._mapping_splitter.setHandleWidth(6)
        self._mapping_splitter.setStyleSheet(
            f"QSplitter::handle:horizontal {{ background: {C.BORDER}; margin: 0; }}"
            f"QSplitter::handle:horizontal:hover {{ background: {C.OLIVE}; }}"
        )
        self._mapping_splitter.addWidget(controls_scroll)
        self._mapping_splitter.addWidget(preview_group)
        self._mapping_splitter.setStretchFactor(0, 0)
        self._mapping_splitter.setStretchFactor(1, 1)
        self._mapping_splitter.setSizes([410, 710])
        self._mapping_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        mapping_layout.addWidget(self._mapping_splitter, 1)

        tab_widget.addTab(mapping_tab, "Mapping")

        # Tab 2: Sample Parameters
        params_tab = QWidget()
        params_layout = QVBoxLayout(params_tab)

        params_group = QGroupBox("Sample Parameters")
        params_form = QFormLayout(params_group)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0, 50)
        self.temperature_spin.setValue(20.0)
        self.temperature_spin.setSuffix(" °C")

        self.porosity_spin = QDoubleSpinBox()
        self.porosity_spin.setRange(0.1, 0.9)
        self.porosity_spin.setValue(0.40)
        self.porosity_spin.setDecimals(3)

        self.sample_name_edit = QTextEdit()
        self.sample_name_edit.setMaximumHeight(60)
        self.sample_name_edit.setPlainText(os.path.splitext(os.path.basename(self.file_path))[0])

        params_form.addRow("Temperature:", self.temperature_spin)
        params_form.addRow("Porosity:", self.porosity_spin)
        params_form.addRow("Sample Name:", self.sample_name_edit)

        params_layout.addWidget(params_group)
        params_layout.addStretch()

        tab_widget.addTab(params_tab, "Parameters")

        layout.addWidget(tab_widget)

        # Footer (added to root, outside body_wrap so it sticks to bottom)
        preview_btn_widget = QPushButton("Preview Results")
        preview_btn_widget.setFixedHeight(28)
        preview_btn_widget.setStyleSheet(
            f"QPushButton {{ border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; background: {C.BG}; "
            f"color: {C.TEXT_MID}; padding: 0 14px; font-size: {F.SZ_LG}pt; }}"
            f"QPushButton:hover {{ background: {C.BG_RAISED}; border-color: {C.BORDER_DK}; }}"
        )
        preview_btn_widget.clicked.connect(self.preview_mapping)

        footer = make_dialog_footer([
            ("Cancel", self.reject, "secondary"),
            ("Import", self.accept, "primary"),
        ], left_widget=preview_btn_widget)
        root.addWidget(footer)

        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )
        self._apply_mode_state()

    def _apply_mode_state(self):
        """Synchronize the dialog UI with the active data type + selection method."""
        selection_mode = self.calculated_selection_mode
        self.cell_range_mode = (not self.raw_sieve_mode and selection_mode == "range")

        self.calculated_data_btn.setChecked(not self.raw_sieve_mode)
        self.raw_sieve_btn.setChecked(self.raw_sieve_mode)

        if hasattr(self, 'column_mode_btn'):
            self.column_mode_btn.setChecked(selection_mode == "column")
            self.range_mode_btn.setChecked(selection_mode == "range")
            self.column_mode_btn.setEnabled(not self.raw_sieve_mode)
            self.range_mode_btn.setEnabled(not self.raw_sieve_mode)

        if hasattr(self, 'mapping_group'):
            self.mapping_group.setVisible(not self.raw_sieve_mode and selection_mode == "column")
        if hasattr(self, 'range_tools_group'):
            self.range_tools_group.setVisible(not self.raw_sieve_mode and selection_mode == "range")
        if hasattr(self, 'raw_sieve_group'):
            self.raw_sieve_group.setVisible(self.raw_sieve_mode)
        if self._mapping_splitter is not None:
            if self.cell_range_mode:
                self._mapping_splitter.setSizes([390, 730])
            elif self.raw_sieve_mode:
                self._mapping_splitter.setSizes([410, 710])
            else:
                self._mapping_splitter.setSizes([410, 710])

        if self.cell_range_mode:
            self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
            self.preview_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        else:
            self.selecting_mode = None
            self.preview_table.clearSelection()
            self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
            self.preview_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self.update_table_colors()
        self._update_range_summary()
        self._update_selection_mode_help()
        self._update_pathway_summary()
        self._update_sheet_selection_guidance()
        self._update_preview_guidance()
        self.validate_required_fields()

    def _build_file_strip(self) -> QWidget:
        strip = QWidget()
        strip.setObjectName("columnMapperFileStrip")
        strip.setStyleSheet(
            f"QWidget#columnMapperFileStrip {{ background: {C.BG_LOW}; "
            f"border-bottom: 1px solid {C.BORDER}; }}"
        )
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(14, 7, 14, 7)
        layout.setSpacing(8)

        icon_label = QLabel()
        file_ext = os.path.splitext(self.file_path)[1].lower()
        fa_name = "fa6s.file-excel" if file_ext in [".xlsx", ".xls"] else "fa6s.file-csv"
        try:
            icon_label.setPixmap(_icon(fa_name, C.TEXT_MUTED).pixmap(14, 14))
        except Exception:
            icon_label.setText("•")
        icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(icon_label)

        file_name_label = QLabel(os.path.basename(self.file_path))
        file_name_label.setStyleSheet(f"color: {C.TEXT}; font-weight: 600; background: transparent;")
        layout.addWidget(file_name_label)

        self._file_meta_label = QLabel()
        self._file_meta_label.setFont(QFont(F.MONO, F.SZ_XS))
        self._file_meta_label.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
        layout.addWidget(self._file_meta_label)
        layout.addStretch(1)

        auto_detect_btn = QPushButton("Auto-detect")
        auto_detect_btn.setFixedHeight(24)
        auto_detect_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid rgba(107,142,35,.28); border-radius: {SZ.BORDER_RADIUS}px; "
            f"background: rgba(107,142,35,.08); color: {C.OLIVE}; padding: 0 10px; }}"
            f"QPushButton:hover {{ background: rgba(107,142,35,.14); }}"
        )
        try:
            auto_detect_btn.setIcon(_icon("fa6s.wand-magic-sparkles", C.OLIVE))
        except Exception:
            pass
        auto_detect_btn.clicked.connect(self._rerun_auto_detection)
        layout.addWidget(auto_detect_btn)

        self._update_file_strip()
        return strip

    def _update_file_strip(self):
        if self._file_meta_label is None:
            return
        row_count = len(self.sample_data)
        column_count = max((len(row) for row in self.sample_data), default=0)
        meta_parts = [f"{row_count} preview rows", f"{column_count} columns"]
        if self.current_sheet:
            meta_parts.append(self.current_sheet)
        self._file_meta_label.setText(" - ".join(meta_parts))

    def _rerun_auto_detection(self):
        self.auto_detect_columns()
        self._auto_detect_raw_sieve_columns()
        self.validate_required_fields()

    def _update_preview_guidance(self):
        if self.preview_hint_label is None:
            return
        if self.raw_sieve_mode:
            text = (
                "Preview the source weighings here. Numeric cells are highlighted to make the "
                "raw sieve columns easier to confirm before import."
            )
        elif self.calculated_selection_mode == "range":
            text = (
                "Select cells directly in this table. Smart Selection can learn the header and "
                "data pattern for similar sheets."
            )
        else:
            text = (
                "Review the detected source columns here before importing. Numeric cells are "
                "highlighted to make grain-size data easier to scan."
            )
        self.preview_hint_label.setText(text)

    def _update_selection_mode_help(self):
        if self.selection_mode_help_label is None:
            return

        if self.raw_sieve_mode:
            text = "Raw Sieve Weighings uses column mapping."
        elif self.calculated_selection_mode == "range":
            text = "Cell Range Selection maps one sheet at a time."
        else:
            text = "Column Mapping is best for clean tables."

        self.selection_mode_help_label.setText(text)

    def _update_pathway_summary(self):
        if self.pathway_summary_label is None:
            return

        file_ext = os.path.splitext(self.file_path)[1].lower()
        excel_multi_sheet = file_ext in ['.xlsx', '.xls'] and len(self.excel_sheets) > 1

        if self.raw_sieve_mode:
            text = (
                "Raw Sieve Weighings -> Column Mapping. Sieve size + two weight columns."
            )
            if excel_multi_sheet:
                text += " Checked sheets reuse mapping."
        elif self.calculated_selection_mode == "range":
            text = (
                "Processed Curve Data -> Cell Range Selection. Irregular Excel layout."
            )
            if file_ext in ['.xlsx', '.xls']:
                text += " One sheet at a time."
        else:
            text = (
                "Processed Curve Data -> Column Mapping. Size + passing/retained columns."
            )
            if excel_multi_sheet:
                text += " Checked sheets reuse mapping."

        self.pathway_summary_label.setText(text)

    def _update_sheet_selection_guidance(self):
        if self.sheet_info_label is None:
            return

        if self.raw_sieve_mode:
            text = (
                "Check the sheets you want to import. The same raw sieve column mapping will be "
                "applied to each checked sheet."
            )
        elif self.calculated_selection_mode == "range":
            text = (
                "Cell Range Selection works one sheet at a time. Select a single sheet to preview "
                "and import, or switch back to Column Mapping for multi-sheet imports."
            )
        else:
            text = (
                "Check the sheets you want to import. Select a sheet to preview and verify the "
                "mapping before importing."
            )

        self.sheet_info_label.setText(text)

    def set_sheet_checks(self, state: Qt.CheckState):
        """Check or uncheck all sheet items"""
        if not self.sheet_list:
            return
        for i in range(self.sheet_list.count()):
            item = self.sheet_list.item(i)
            item.setCheckState(state)

    def on_sheet_selection_changed(self):
        """Preview the sheet that is currently highlighted in the list"""
        if not self.sheet_list:
            return
        item = self.sheet_list.currentItem()
        if not item:
            return
        sheet_name = item.text()
        if sheet_name != self.current_sheet:
            self.reload_sheet(sheet_name)
        else:
            # Ensure check state at least enabled when user focuses a sheet
            pass

    def _select_sheet_in_list(self, sheet_name: str):
        """Programmatically select a sheet in the checklist"""
        if not self.sheet_list or not sheet_name:
            return
        for i in range(self.sheet_list.count()):
            item = self.sheet_list.item(i)
            if item.text() == sheet_name:
                self.sheet_list.blockSignals(True)
                self.sheet_list.setCurrentItem(item)
                self.sheet_list.blockSignals(False)
                break

    def get_selected_sheet_names(self) -> List[str]:
        """Return list of sheet names that are checked for import"""
        if not self.sheet_list:
            # No multi-sheet UI; fall back to current sheet if any
            if self.current_sheet:
                return [self.current_sheet]
            return []

        selected = []
        for i in range(self.sheet_list.count()):
            item = self.sheet_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())

        if not selected and self.sheet_list.currentItem():
            selected.append(self.sheet_list.currentItem().text())
        elif not selected and self.excel_sheets:
            selected.append(self.excel_sheets[0])

        return selected

    def setup_preview_table(self):
        """Setup the preview table with CSV data"""
        if not self.sample_data:
            return

        self.populate_preview_table(self.preview_table, self.sample_data, self.headers)

        # Connect selection changed signal for range selection
        try:
            self.preview_table.itemSelectionChanged.disconnect(self.on_table_selection_changed)
        except TypeError:
            pass
        self.preview_table.itemSelectionChanged.connect(self.on_table_selection_changed)

        # Adjust column widths
        self.preview_table.resizeColumnsToContents()
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.preview_table.horizontalHeader().setMinimumSectionSize(110)
        self.preview_table.verticalHeader().setDefaultSectionSize(28)
        self._update_preview_header_highlights()
        self._update_file_strip()

    @staticmethod
    def populate_preview_table(
        table: QTableWidget,
        sample_data: List[List[str]],
        headers: List[str],
    ) -> None:
        """Populate a preview table using the mapper preview presentation."""
        table.clear()
        max_cols = max(len(row) for row in sample_data)
        table.setRowCount(len(sample_data))
        table.setColumnCount(max_cols)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setFrameShape(QFrame.Shape.NoFrame)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.setStyleSheet(
            f"QTableWidget {{ background: {C.BG}; border: none; alternate-background-color: rgba(255,255,255,.40); "
            f"selection-background-color: rgba(107,142,35,.10); selection-color: {C.TEXT}; }}"
            f"QHeaderView::section {{ background: {C.BG_LOW}; border: none; border-bottom: 1px solid {C.BORDER}; "
            f"padding: 6px 8px; color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt; font-weight: 600; }}"
            f"QTableWidget::item {{ padding: 4px 8px; border-bottom: 1px solid rgba(0,0,0,.04); }}"
        )

        if len(headers) >= max_cols:
            table.setHorizontalHeaderLabels(headers[:max_cols])
        else:
            derived_headers = headers + [f"Col {i+1}" for i in range(len(headers), max_cols)]
            table.setHorizontalHeaderLabels(derived_headers)

        for i, row in enumerate(sample_data):
            for j, cell in enumerate(row):
                if j < max_cols:
                    item = QTableWidgetItem(str(cell))
                    if ColumnMapperDialog.is_numeric(str(cell).strip()):
                        item.setBackground(QColor("#edf3e6"))
                    table.setItem(i, j, item)

    def validate_required_fields(self):
        """Update styling based on whether required fields are filled"""
        if self.raw_sieve_mode:
            # Raw sieve mode: all three raw-sieve columns are required
            for combo in [
                getattr(self, 'raw_size_combo', None),
                getattr(self, 'empty_sieve_combo', None),
                getattr(self, 'sieve_sample_combo', None),
            ]:
                if combo is None:
                    continue
                if combo.currentIndex() > 0:
                    combo.setStyleSheet(f"QComboBox {{ {self.required_filled_style} padding: 5px; border-radius: 3px; }}")
                else:
                    combo.setStyleSheet(f"QComboBox {{ {self.required_empty_style} padding: 5px; border-radius: 3px; }}")
        else:
            # Calculated mode: sieve size + percent passing (or retained)
            if self.size_combo.currentIndex() > 0:
                self.size_combo.setStyleSheet(f"QComboBox {{ {self.required_filled_style} padding: 5px; border-radius: 3px; }}")
            else:
                self.size_combo.setStyleSheet(f"QComboBox {{ {self.required_empty_style} padding: 5px; border-radius: 3px; }}")

            if self.passing_combo.currentIndex() > 0 or self.retained_combo.currentIndex() > 0:
                self.passing_combo.setStyleSheet(f"QComboBox {{ {self.required_filled_style} padding: 5px; border-radius: 3px; }}")
            else:
                self.passing_combo.setStyleSheet(f"QComboBox {{ {self.required_empty_style} padding: 5px; border-radius: 3px; }}")

        self._update_preview_header_highlights()

    def _update_preview_header_highlights(self):
        if not hasattr(self, 'preview_table') or self.preview_table.columnCount() == 0:
            return

        selected_columns = set()
        if self.raw_sieve_mode:
            for combo in [
                getattr(self, 'raw_size_combo', None),
                getattr(self, 'empty_sieve_combo', None),
                getattr(self, 'sieve_sample_combo', None),
            ]:
                if combo is not None and combo.currentIndex() > 0:
                    selected_columns.add(combo.currentIndex() - 1)
        elif not self.cell_range_mode:
            for combo in [
                getattr(self, 'size_combo', None),
                getattr(self, 'passing_combo', None),
                getattr(self, 'retained_combo', None),
            ]:
                if combo is not None and combo.currentIndex() > 0:
                    selected_columns.add(combo.currentIndex() - 1)

        for col in range(self.preview_table.columnCount()):
            item = self.preview_table.horizontalHeaderItem(col)
            if item is None:
                continue

            font = item.font()
            font.setBold(col in selected_columns)
            item.setFont(font)

            if col in selected_columns:
                item.setForeground(QBrush(QColor(C.OLIVE)))
                item.setBackground(QBrush(QColor(C.BG_RAISED)))
            else:
                item.setForeground(QBrush(QColor(C.TEXT_MID)))
                item.setBackground(QBrush(QColor(C.BG_LOW)))

    def auto_detect_columns(self):
        """Try to automatically detect column types"""
        if not self.headers:
            return

        size_keywords = ['size', 'diameter', 'grain', 'particle', 'sieve', 'mesh', 'mm', 'd mm', 'd mmm']
        passing_keywords = ['passing', 'pass', 'finer', 'cumulative', 'procentages', 'percentages']
        retained_keywords = ['retained', 'retain', 'on curve']

        # Track what we've found to prioritize properly
        size_found = False
        passing_found = False

        for i, header in enumerate(self.headers):
            header_lower = header.lower()

            # Check for size column (highest priority)
            if any(keyword in header_lower for keyword in size_keywords) and not size_found:
                self.size_combo.setCurrentIndex(i + 1)  # +1 because of "(Not Used)"
                size_found = True

            # Check for passing column (second priority - preferred over retained)
            elif any(keyword in header_lower for keyword in passing_keywords) and not passing_found:
                self.passing_combo.setCurrentIndex(i + 1)
                passing_found = True

            # Check for retained column (only if no passing column found)
            elif any(keyword in header_lower for keyword in retained_keywords) and not passing_found:
                self.retained_combo.setCurrentIndex(i + 1)

    def _auto_detect_raw_sieve_columns(self):
        """Try to automatically detect the three raw sieve weighing columns."""
        if not self.headers or not hasattr(self, 'raw_size_combo'):
            return

        size_keywords     = ['sieve', 'size', 'diameter', 'grain', 'particle', 'mesh', 'mm']
        empty_keywords    = ['empty', 'tare', 'blank']
        full_keywords     = ['sample', 'total', 'full', 'gross', 'sieve + sample', 'sieve+sample',
                             'sieve and sample', 'filled']

        size_found  = False
        empty_found = False
        full_found  = False

        for i, header in enumerate(self.headers):
            h = header.lower()

            if not size_found and any(k in h for k in size_keywords):
                self.raw_size_combo.setCurrentIndex(i + 1)
                size_found = True

            elif not empty_found and any(k in h for k in empty_keywords):
                self.empty_sieve_combo.setCurrentIndex(i + 1)
                empty_found = True

            elif not full_found and any(k in h for k in full_keywords):
                self.sieve_sample_combo.setCurrentIndex(i + 1)
                full_found = True

    def preview_mapping(self):
        """Preview the results of the current mapping"""
        try:
            particle_sizes, percent_passing = self.extract_data()

            preview_text = f"Preview Results:\n"
            preview_text += f"Extracted {len(particle_sizes)} data points\n\n"

            if len(particle_sizes) > 0:
                preview_text += f"Size range: {min(particle_sizes):.3f} - {max(particle_sizes):.3f} mm\n"
                preview_text += f"Passing range: {min(percent_passing):.1f}% - {max(percent_passing):.1f}%\n\n"

                preview_text += "First 5 data points:\n"
                for i in range(min(5, len(particle_sizes))):
                    preview_text += f"  {particle_sizes[i]:.3f} mm → {percent_passing[i]:.1f}%\n"

            QMessageBox.information(self, "Preview Results", preview_text)

        except Exception as e:
            QMessageBox.warning(self, "Preview Error", f"Error in mapping:\n{str(e)}")

    def extract_data(self) -> Tuple[List[float], List[float]]:
        """Extract data based on current mode (column mapping, cell range, or raw sieve)"""
        if self.raw_sieve_mode:
            return self.extract_data_from_raw_sieve()
        elif self.cell_range_mode:
            return self.extract_data_from_ranges()
        else:
            return self.extract_data_from_columns()

    def extract_data_for_sheet(self, sheet_name: Optional[str]) -> Tuple[List[float], List[float]]:
        """Extract data for a specific sheet using the current mapping settings"""
        if self.raw_sieve_mode:
            return self.extract_data_from_raw_sieve(sheet_name=sheet_name)
        elif self.cell_range_mode:
            if sheet_name and sheet_name != self.current_sheet:
                raise ValueError("Cell range selection mode currently supports one sheet at a time. Please select a single sheet or switch to column mapping mode.")
            return self.extract_data_from_ranges(sheet_name=sheet_name)
        return self.extract_data_from_columns(sheet_name=sheet_name)

    def _get_preferred_sheet_name(self) -> str:
        """Choose a default sheet when none is explicitly selected"""
        if not self.excel_sheets:
            return "Sheet1"
        lower_name_map = {name.lower(): name for name in self.excel_sheets}
        if 'english' in lower_name_map:
            return lower_name_map['english']
        return self.excel_sheets[0]

    def _load_rows_for_sheet(self, sheet_name: Optional[str] = None) -> List[List[str]]:
        """Load all rows for the specified sheet (or entire CSV)"""
        file_ext = os.path.splitext(self.file_path)[1].lower()
        if file_ext == '.csv':
            with open(self.file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                return list(reader)

        if file_ext in ['.xlsx', '.xls']:
            import pandas as pd
            target_sheet = sheet_name or self.current_sheet
            if not target_sheet or (self.excel_sheets and target_sheet not in self.excel_sheets):
                target_sheet = self._get_preferred_sheet_name()
            df = pd.read_excel(self.file_path, sheet_name=target_sheet, header=None)
            rows = df.values.tolist()
            return [[str(cell) if pd.notna(cell) else '' for cell in row] for row in rows]

        return []

    def extract_data_from_columns(self, sheet_name: Optional[str] = None) -> Tuple[List[float], List[float]]:
        """Extract data using column mapping mode"""
        size_idx = self.size_combo.currentIndex() - 1  # -1 for "(Not Used)"
        passing_idx = self.passing_combo.currentIndex() - 1
        retained_idx = self.retained_combo.currentIndex() - 1

        if size_idx < 0:
            raise ValueError("Please select a Particle Size column (required)")

        if passing_idx < 0 and retained_idx < 0:
            raise ValueError("Please select a Percent Passing column (or Percent Retained if you don't have Passing data)")

        # Prefer passing over retained if both are selected
        if passing_idx >= 0 and retained_idx >= 0:
            retained_idx = -1  # Ignore retained if both are selected

        particle_sizes = []
        percent_passing = []

        # Load all data (not just preview)
        rows = self._load_rows_for_sheet(sheet_name)

        # Skip header row(s) - use detected header row + 1
        header_row_idx = getattr(self, 'header_row', 0)
        data_rows = rows[header_row_idx + 1:] if len(rows) > header_row_idx + 1 else rows

        for row in data_rows:
            if len(row) <= max(size_idx, passing_idx, retained_idx):
                continue

            try:
                # Extract particle size
                size_str = row[size_idx].strip()
                if not size_str or not self.is_numeric(size_str):
                    continue
                size = float(size_str)

                # Extract percentage
                passing = None
                if passing_idx >= 0:
                    passing_str = row[passing_idx].strip()
                    if not passing_str or not self.is_numeric(passing_str):
                        continue
                    passing = float(passing_str)
                elif retained_idx >= 0:
                    retained_str = row[retained_idx].strip()
                    if not retained_str or not self.is_numeric(retained_str):
                        continue
                    retained = float(retained_str)
                    passing = 100.0 - retained  # Convert retained to passing

                if passing is not None:
                    particle_sizes.append(size)
                    percent_passing.append(passing)

            except (ValueError, IndexError):
                continue

        if not particle_sizes:
            raise ValueError("No valid data points extracted")

        return particle_sizes, percent_passing

    def extract_data_from_ranges(self, sheet_name: Optional[str] = None) -> Tuple[List[float], List[float]]:
        """Extract data using cell range selection mode"""
        if not self.selected_size_range or not self.selected_percent_range:
            raise ValueError("Please select both size data range and percent data range")

        if len(self.selected_size_range) != len(self.selected_percent_range):
            raise ValueError(f"Size range ({len(self.selected_size_range)} cells) and percent range ({len(self.selected_percent_range)} cells) must have the same number of cells")

        rows = self._load_rows_for_sheet(sheet_name)

        particle_sizes = []
        percent_passing = []

        # Extract data from selected ranges - sort by row position to maintain order
        size_positions = sorted(self.selected_size_range, key=lambda x: (x[0], x[1]))
        percent_positions = sorted(self.selected_percent_range, key=lambda x: (x[0], x[1]))

        for i, (size_pos, percent_pos) in enumerate(zip(size_positions, percent_positions)):
            try:
                # Extract size value
                size_row, size_col = size_pos
                if size_row < len(rows) and size_col < len(rows[size_row]):
                    size_str = rows[size_row][size_col].strip()
                    if size_str and self.is_numeric(size_str):
                        size = float(size_str)
                    else:
                        continue  # Skip non-numeric cells
                else:
                    continue

                # Extract percent value
                percent_row, percent_col = percent_pos
                if percent_row < len(rows) and percent_col < len(rows[percent_row]):
                    percent_str = rows[percent_row][percent_col].strip()
                    if percent_str and self.is_numeric(percent_str):
                        percent = float(percent_str)
                    else:
                        continue  # Skip non-numeric cells
                else:
                    continue

                particle_sizes.append(size)
                percent_passing.append(percent)

            except (ValueError, IndexError):
                continue  # Skip problematic cells

        if not particle_sizes:
            raise ValueError("No valid numeric data found in selected ranges")

        return particle_sizes, percent_passing

    def get_mapping_results(self) -> List[Dict]:
        """Get mapping results for all selected sheets"""
        try:
            selected_sheets = self.get_selected_sheet_names()
            if not selected_sheets:
                selected_sheets = [self.current_sheet or self._get_preferred_sheet_name()]

            if self.cell_range_mode and len(selected_sheets) > 1:
                raise ValueError("Cell range selection mode only supports one sheet at a time. Please select a single sheet or switch to Column Mapping mode.")

            base_sample_name = self.sample_name_edit.toPlainText().strip()
            if not base_sample_name:
                base_sample_name = os.path.splitext(os.path.basename(self.file_path))[0]

            results: List[Dict] = []

            for idx, sheet_name in enumerate(selected_sheets):
                particle_sizes, percent_passing = self.extract_data_for_sheet(sheet_name)

                # Learn pattern from cell range selection if applicable (only once)
                if idx == 0 and self.cell_range_mode and self.selected_size_range and self.selected_percent_range:
                    self.learn_pattern_from_selection()

                sample_name = base_sample_name
                if len(selected_sheets) > 1:
                    sample_name = f"{base_sample_name} - {sheet_name}"

                results.append({
                    'particle_sizes': particle_sizes,
                    'percent_passing': percent_passing,
                    'sample_name': sample_name,
                    'temperature': self.temperature_spin.value(),
                    'porosity': self.porosity_spin.value(),
                    'sheet_name': sheet_name
                })

            return results
        except Exception as e:
            raise ValueError(f"Mapping failed: {str(e)}")

    def get_mapping_result(self) -> Dict:
        """Backward-compatible helper returning only the first mapping result"""
        results = self.get_mapping_results()
        if not results:
            raise ValueError("No data extracted from the selected sheet(s)")
        return results[0]

    def get_mapping_state(self) -> Dict:
        """Capture the current mapper state so the same file can be reopened cleanly."""
        state = {
            'raw_sieve_mode': self.raw_sieve_mode,
            'calculated_selection_mode': self.calculated_selection_mode,
            'header_row': self.header_row,
            'sample_name': self.sample_name_edit.toPlainText().strip(),
            'temperature': self.temperature_spin.value(),
            'porosity': self.porosity_spin.value(),
            'current_sheet': self.current_sheet,
            'checked_sheets': self.get_selected_sheet_names(),
            'column_indices': {
                'size': self.size_combo.currentIndex(),
                'passing': self.passing_combo.currentIndex(),
                'retained': self.retained_combo.currentIndex(),
                'raw_size': self.raw_size_combo.currentIndex(),
                'empty_sieve': self.empty_sieve_combo.currentIndex(),
                'sieve_sample': self.sieve_sample_combo.currentIndex(),
            },
        }
        if self.selected_size_range and self.selected_percent_range:
            state['selected_size_range'] = [list(pos) for pos in self.selected_size_range]
            state['selected_percent_range'] = [list(pos) for pos in self.selected_percent_range]
        return state

    def apply_mapping_state(self, state: Optional[Dict]) -> None:
        """Restore a previous mapper state for the same file."""
        if not state:
            return

        current_sheet = state.get('current_sheet')
        if current_sheet and current_sheet in self.excel_sheets and current_sheet != self.current_sheet:
            self.reload_sheet(current_sheet)

        if self.sheet_list:
            checked_sheets = set(state.get('checked_sheets') or [])
            if checked_sheets:
                for i in range(self.sheet_list.count()):
                    item = self.sheet_list.item(i)
                    item.setCheckState(
                        Qt.CheckState.Checked if item.text() in checked_sheets else Qt.CheckState.Unchecked
                    )
            if current_sheet:
                self._select_sheet_in_list(current_sheet)

        if hasattr(self, 'header_row_spin') and state.get('header_row') is not None:
            header_row = int(state['header_row'])
            header_row = max(0, min(header_row, self.header_row_spin.maximum()))
            self.header_row_spin.setValue(header_row)

        sample_name = state.get('sample_name')
        if sample_name:
            self.sample_name_edit.setPlainText(sample_name)

        if state.get('temperature') is not None:
            self.temperature_spin.setValue(float(state['temperature']))
        if state.get('porosity') is not None:
            self.porosity_spin.setValue(float(state['porosity']))

        if state.get('raw_sieve_mode'):
            self.switch_to_raw_sieve_mode()
        elif state.get('calculated_selection_mode') == 'range':
            self.switch_to_range_mode()
        else:
            self.switch_to_column_mode()

        combo_indices = state.get('column_indices') or {}
        combo_map = {
            'size': self.size_combo,
            'passing': self.passing_combo,
            'retained': self.retained_combo,
            'raw_size': self.raw_size_combo,
            'empty_sieve': self.empty_sieve_combo,
            'sieve_sample': self.sieve_sample_combo,
        }
        for key, combo in combo_map.items():
            index = combo_indices.get(key)
            if isinstance(index, int) and 0 <= index < combo.count():
                combo.setCurrentIndex(index)

        if self.cell_range_mode and not self.raw_sieve_mode:
            self.selected_size_range = [tuple(pos) for pos in state.get('selected_size_range', [])]
            self.selected_percent_range = [tuple(pos) for pos in state.get('selected_percent_range', [])]
            self.update_table_colors()

        self._update_preview_header_highlights()
        self._update_preview_guidance()

    def reload_sheet(self, sheet_name: str):
        """Reload data when Excel sheet changes"""
        if not sheet_name or sheet_name == self.current_sheet:
            return

        try:
            # Reload the preview with new sheet
            self.load_csv_preview(sheet_name=sheet_name)
            self.setup_preview_table()

            # Update list selection to match
            self._select_sheet_in_list(sheet_name)

            # Update combo boxes
            column_options = ["(Not Used)"] + self.headers
            for combo in [self.size_combo, self.passing_combo, self.retained_combo]:
                combo.clear()
                combo.addItems(column_options)

            # Re-run auto detection
            self.auto_detect_columns()

            # Update header row spinner if it exists
            if hasattr(self, 'header_row_spin'):
                self.header_row_spin.setRange(0, min(10, len(self.sample_data) - 1))
                self.header_row_spin.setValue(self.header_row)

            # Reset any learned pattern or selections since data changed
            self.selected_size_range = []
            self.selected_percent_range = []
            self.selected_headers = []
            self.learned_pattern = None
            if hasattr(self, 'batch_apply_btn'):
                self.batch_apply_btn.setEnabled(False)
            if hasattr(self, 'pattern_info_label'):
                self.pattern_info_label.setText("Select headers and data together, then apply the learned pattern to similar sheets.")
            self._apply_mode_state()

        except Exception as e:
            QMessageBox.warning(self, "Sheet Load Error", f"Could not load sheet '{sheet_name}':\n{str(e)}")

    def update_headers(self, new_header_row: int):
        """Update headers when header row changes"""
        if new_header_row == self.header_row:
            return

        self.header_row = new_header_row
        try:
            # Update headers from the new row
            if new_header_row < len(self.sample_data):
                new_headers = [cell.strip() for cell in self.sample_data[new_header_row]]
                # Filter out empty headers and replace with generic names
                for i, header in enumerate(new_headers):
                    if not header or header.lower() in ['unnamed', 'nan']:
                        new_headers[i] = f"Column {i+1}"
                self.headers = new_headers

                # Update combo boxes
                column_options = ["(Not Used)"] + self.headers
                for combo in [self.size_combo, self.passing_combo, self.retained_combo]:
                    combo.clear()
                    combo.addItems(column_options)

                # Also update raw sieve combo boxes if they exist
                for combo in [
                    getattr(self, 'raw_size_combo', None),
                    getattr(self, 'empty_sieve_combo', None),
                    getattr(self, 'sieve_sample_combo', None),
                ]:
                    if combo is not None:
                        combo.clear()
                        combo.addItems(column_options)

                # Re-run auto detection for both modes
                self.auto_detect_columns()
                self._auto_detect_raw_sieve_columns()

                # Update preview table headers
                if len(self.headers) >= self.preview_table.columnCount():
                    self.preview_table.setHorizontalHeaderLabels(self.headers[:self.preview_table.columnCount()])
                else:
                    headers = self.headers + [f"Col {i+1}" for i in range(len(self.headers), self.preview_table.columnCount())]
                    self.preview_table.setHorizontalHeaderLabels(headers)

        except Exception as e:
            QMessageBox.warning(self, "Header Update Error", f"Could not update headers:\n{str(e)}")

    def switch_to_column_mode(self):
        """Switch to column mapping mode"""
        self.raw_sieve_mode = False
        self.calculated_selection_mode = "column"
        self._apply_mode_state()

    def switch_to_range_mode(self):
        """Switch to cell range selection mode"""
        self.raw_sieve_mode = False
        self.calculated_selection_mode = "range"
        self._apply_mode_state()

    def switch_to_raw_sieve_mode(self):
        """Switch to raw sieve weighings input mode."""
        self.raw_sieve_mode = True
        self._apply_mode_state()

    def switch_to_calculated_mode(self):
        """Switch back to the standard calculated-data input mode."""
        self.raw_sieve_mode = False
        self._apply_mode_state()

    def _mark_current_selection(self, mode: str) -> None:
        """Assign the currently selected preview cells to a range role."""
        selected_items = self.preview_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Select cells in the preview table first.")
            return

        positions = sorted(
            {(item.row(), item.column()) for item in selected_items},
            key=lambda pos: (pos[0], pos[1]),
        )
        if mode == "size":
            self.selected_size_range = positions
            self.pattern_info_label.setText(f"Marked {len(positions)} particle-size cells.")
        else:
            self.selected_percent_range = positions
            self.pattern_info_label.setText(f"Marked {len(positions)} percent-passing cells.")

        self.preview_table.clearSelection()
        self.update_table_colors()
        self._update_range_summary()

    def _update_range_summary(self) -> None:
        if hasattr(self, "size_range_count_label"):
            self.size_range_count_label.setText(f"{len(self.selected_size_range)} size cells")
        if hasattr(self, "percent_range_count_label"):
            self.percent_range_count_label.setText(f"{len(self.selected_percent_range)} passing cells")

    def extract_data_from_raw_sieve(self, sheet_name: Optional[str] = None) -> Tuple[List[float], List[float]]:
        """
        Extract raw sieve weighing columns and compute cumulative % passing.

        Reads the three user-mapped columns (sieve size, empty sieve weight,
        sieve+sample weight), delegates the calculation to
        data_loader.calculate_sieve_percent_passing, and returns the same
        (particle_sizes, percent_passing) tuple that all other extractors
        return — so nothing downstream needs to change.
        """
        size_idx   = self.raw_size_combo.currentIndex() - 1
        empty_idx  = self.empty_sieve_combo.currentIndex() - 1
        full_idx   = self.sieve_sample_combo.currentIndex() - 1

        if size_idx < 0:
            raise ValueError("Please select a Sieve Size column")
        if empty_idx < 0:
            raise ValueError("Please select a Weight of Empty Sieve column")
        if full_idx < 0:
            raise ValueError("Please select a Weight of Sieve + Sample column")

        rows = self._load_rows_for_sheet(sheet_name)
        header_row_idx = getattr(self, 'header_row', 0)
        data_rows = rows[header_row_idx + 1:] if len(rows) > header_row_idx + 1 else rows

        sieve_sizes: List[float]   = []
        empty_weights: List[float] = []
        full_weights: List[float]  = []

        max_idx = max(size_idx, empty_idx, full_idx)
        for row in data_rows:
            if len(row) <= max_idx:
                continue
            try:
                size_str  = row[size_idx].strip()
                empty_str = row[empty_idx].strip()
                full_str  = row[full_idx].strip()

                if not size_str or not self.is_numeric(size_str):
                    continue
                if not empty_str or not self.is_numeric(empty_str):
                    continue
                if not full_str or not self.is_numeric(full_str):
                    continue

                size  = float(size_str)
                empty = float(empty_str)
                full  = float(full_str)

                if size <= 0:
                    continue  # Skip pan / invalid size rows

                sieve_sizes.append(size)
                empty_weights.append(empty)
                full_weights.append(full)

            except (ValueError, IndexError):
                continue

        if not sieve_sizes:
            raise ValueError(
                "No valid data rows found. Make sure the correct columns are selected "
                "and that the Header Row setting points to the actual header row."
            )

        # Delegate all arithmetic to the utility function in data_loader
        from data_loader import calculate_sieve_percent_passing
        return calculate_sieve_percent_passing(sieve_sizes, empty_weights, full_weights)

    def toggle_smart_selection(self):
        """Toggle smart selection mode"""
        self.smart_selection_mode = self.smart_selection_btn.isChecked()

        if self.smart_selection_mode:
            # Enable smart selection
            self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
            self.preview_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
            self.pattern_info_label.setText("Drag to select the headers and data together.")
        else:
            # Clear selection and reset
            self.preview_table.clearSelection()
            self.clear_smart_selection()
            self.pattern_info_label.setText("Select headers and data together, then apply the learned pattern to similar sheets.")

    def clear_smart_selection(self):
        """Clear smart selection data"""
        self.selected_size_range = []
        self.selected_percent_range = []
        self.selected_headers = []
        self.learned_pattern = None
        self.batch_apply_btn.setEnabled(False)
        self._update_range_summary()

        # Reset table colors
        for i in range(self.preview_table.rowCount()):
            for j in range(self.preview_table.columnCount()):
                item = self.preview_table.item(i, j)
                if item:
                    # Reset to numeric highlighting or default
                    if self.is_numeric(item.text().strip()):
                        item.setBackground(QColor("#edf3e6"))
                    else:
                        item.setBackground(QColor("#ffffff"))

    def on_selection_changed(self):
        """Handle selection changes in smart selection mode"""
        if not self.smart_selection_mode:
            return

        selected_items = self.preview_table.selectedItems()
        if not selected_items:
            self.clear_smart_selection()
            return

        # Analyze selection automatically
        self.analyze_smart_selection(selected_items)

    def start_range_selection(self, mode: str):
        """Start selecting a range for size or percent data (legacy method)"""
        # Clear any existing selection
        self.preview_table.clearSelection()

        self.selecting_mode = mode

        # Enable persistent cell selection in table
        self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.preview_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

    def clear_range_selection(self):
        """Clear all range selections"""
        self.selected_size_range = []
        self.selected_percent_range = []
        self.selecting_mode = None

        # Clear visual selection in table
        self.preview_table.clearSelection()
        self.update_table_colors()

    def on_table_selection_changed(self):
        """Handle table selection changes for range selection mode"""
        if self.smart_selection_mode:
            self.on_selection_changed()
            return

        if not self.cell_range_mode or not self.selecting_mode:
            return

        selected_items = self.preview_table.selectedItems()

        # Legacy mode - just track selection count for now
        # (Old button UI has been replaced with smart selection)

    def confirm_range_selection(self, mode: str):
        """Confirm the current selection as the final range"""
        selected_items = self.preview_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select some cells first by dragging in the table.")
            return

        # Get row, col positions of selected items
        selected_positions = [(item.row(), item.column()) for item in selected_items]

        if mode == 'size':
            self.selected_size_range = selected_positions
        else:
            self.selected_percent_range = selected_positions

        # Reset selecting mode
        self.selecting_mode = None

        # Update visual highlighting
        self.update_table_colors()
        self._update_range_summary()

        # Clear table selection to avoid confusion
        self.preview_table.clearSelection()

    def update_table_colors(self):
        """Update table cell colors to show selected ranges"""
        # Reset all backgrounds to default
        for i in range(self.preview_table.rowCount()):
            for j in range(self.preview_table.columnCount()):
                item = self.preview_table.item(i, j)
                if item:
                    # Reset to numeric highlighting or default
                    if self.is_numeric(item.text().strip()):
                        item.setBackground(QColor("#edf3e6"))
                    else:
                        item.setBackground(QColor("#ffffff"))

        # Highlight selected ranges only while range mode is active.
        if self.cell_range_mode and not self.raw_sieve_mode:
            for row, col in self.selected_size_range:
                item = self.preview_table.item(row, col)
                if item:
                    item.setBackground(QColor("#dde8f4"))

            for row, col in self.selected_percent_range:
                item = self.preview_table.item(row, col)
                if item:
                    item.setBackground(QColor("#e1ecd2"))
        self._update_range_summary()

    def analyze_smart_selection(self, selected_items):
        """Analyze the smart selection and classify cells automatically"""
        if not selected_items:
            return

        # Get positions of selected cells
        selected_positions = [(item.row(), item.column()) for item in selected_items]

        # Group all positions by column (including empty cells)
        columns = {}
        headers = []

        for row, col in selected_positions:
            if row < len(self.sample_data) and col < len(self.sample_data[row]):
                cell_value = str(self.sample_data[row][col]).strip().strip("'\"")

                # Check if this is a header (non-numeric text)
                if cell_value and not self.is_numeric(cell_value) and len(cell_value) > 1:
                    headers.append((row, col, cell_value))

                # Group ALL positions by column (numeric and empty)
                if col not in columns:
                    columns[col] = []
                columns[col].append((row, col))

        # Classify columns as size or percent based on their numeric content
        size_column = None
        percent_column = None

        for col, positions in columns.items():
            # Sample numeric values from this column to classify it
            numeric_values = []
            for row, _ in positions:
                if row < len(self.sample_data) and col < len(self.sample_data[row]):
                    cell_value = str(self.sample_data[row][col]).strip().strip("'\"")
                    if cell_value and self.is_numeric(cell_value):
                        numeric_values.append(float(cell_value))

            # Classify based on numeric content (if any)
            if numeric_values:
                avg_value = sum(numeric_values) / len(numeric_values)
                max_value = max(numeric_values)

                # Heuristic: size data typically has smaller values (0.01-10 mm)
                # percent data typically has larger values (0-100%)
                if max_value <= 10 and avg_value <= 5:
                    size_column = col
                elif max_value >= 10 or avg_value >= 10:
                    percent_column = col

        # Assign ALL positions from selected columns (preserving row alignment)
        if size_column is not None and percent_column is not None:
            # Get positions from both columns, sorted by row
            size_positions = sorted([pos for pos in columns[size_column]], key=lambda x: x[0])
            percent_positions = sorted([pos for pos in columns[percent_column]], key=lambda x: x[0])

            # Store all positions (including empty cells) to maintain row alignment
            self.selected_size_range = size_positions
            self.selected_percent_range = percent_positions

        # Store headers (preserve header text for pattern learning)
        self.selected_headers = headers

        # Update visual feedback
        self.update_smart_selection_colors()

        # Try to learn pattern if we have enough data
        if self.selected_size_range and self.selected_percent_range and headers:
            pattern = self.learn_pattern_from_selection()
            if pattern:
                self.batch_apply_btn.setEnabled(True)
                header_names = [name for _, _, name in headers]
                self.pattern_info_label.setText(f"Pattern learned: {', '.join(header_names[:2])}")
            else:
                self.pattern_info_label.setText("Could not learn a repeatable pattern from this selection.")
        else:
            self.pattern_info_label.setText("Select the headers and data together.")
        self._update_range_summary()

    def update_smart_selection_colors(self):
        """Update colors for smart selection"""
        # Reset all backgrounds
        for i in range(self.preview_table.rowCount()):
            for j in range(self.preview_table.columnCount()):
                item = self.preview_table.item(i, j)
                if item:
                    if self.is_numeric(item.text().strip()):
                        item.setBackground(QColor("#edf3e6"))
                    else:
                        item.setBackground(QColor("#ffffff"))

        # Highlight selected elements
        for row, col, _ in self.selected_headers:
            item = self.preview_table.item(row, col)
            if item:
                item.setBackground(QColor("#f1e3b8"))

        for row, col in self.selected_size_range:
            item = self.preview_table.item(row, col)
            if item:
                item.setBackground(QColor("#dde8f4"))

        for row, col in self.selected_percent_range:
            item = self.preview_table.item(row, col)
            if item:
                item.setBackground(QColor("#e1ecd2"))
        self._update_range_summary()

    def learn_pattern_from_selection(self):
        """Learn a pattern from the current cell range selection for batch processing"""
        if not self.selected_size_range or not self.selected_percent_range:
            return None

        # Get column information
        size_col = self.selected_size_range[0][1]  # Column of size data
        percent_col = self.selected_percent_range[0][1]  # Column of percent data

        # Use headers detected during smart selection
        size_header = None
        percent_header = None
        header_row = None

        # Find headers from the detected headers that match our columns
        for row, col, header_text in self.selected_headers:
            if col == size_col:
                size_header = header_text.strip("'\"")
                header_row = row
            elif col == percent_col:
                percent_header = header_text.strip("'\"")
                if header_row is None:
                    header_row = row

        # If no headers found in smart selection, fall back to search method
        if not size_header or not percent_header:
            # Find data bounds for fallback search
            size_rows = [pos[0] for pos in self.selected_size_range]
            percent_rows = [pos[0] for pos in self.selected_percent_range]
            data_start_row = min(min(size_rows), min(percent_rows))

            # Search backwards from data for headers
            for row in range(data_start_row - 1, max(-1, data_start_row - 16), -1):
                if row >= 0 and row < len(self.sample_data):
                    # Check for size column header
                    if not size_header and size_col < len(self.sample_data[row]):
                        cell_value = str(self.sample_data[row][size_col]).strip().strip("'\"")
                        if cell_value and not self.is_numeric(cell_value) and len(cell_value) > 1:
                            size_header = cell_value
                            header_row = row

                    # Check for percent column header
                    if not percent_header and percent_col < len(self.sample_data[row]):
                        cell_value = str(self.sample_data[row][percent_col]).strip().strip("'\"")
                        if cell_value and not self.is_numeric(cell_value) and len(cell_value) > 1:
                            percent_header = cell_value
                            if header_row is None:
                                header_row = row

                    # Stop if we found both headers
                    if size_header and percent_header:
                        break

        if not size_header or not percent_header or header_row is None:
            return None

        # Calculate offset from headers to first numeric data
        data_start_row = None
        for row, col in self.selected_size_range:
            if row < len(self.sample_data) and col < len(self.sample_data[row]):
                cell_value = str(self.sample_data[row][col]).strip().strip("'\"")
                if cell_value and self.is_numeric(cell_value):
                    data_start_row = row
                    break

        if data_start_row is None:
            return None

        size_offset = data_start_row - header_row

        pattern = {
            'size_header': size_header,
            'percent_header': percent_header,
            'size_column': size_col,
            'percent_column': percent_col,
            'data_offset': size_offset,
            'header_row': header_row
        }

        self.learned_pattern = pattern
        return pattern

    def apply_pattern_to_file(self, file_path: str) -> Dict:
        """Apply the learned pattern to extract data from another file"""
        if not self.learned_pattern:
            raise ValueError("No pattern learned yet")

        pattern = self.learned_pattern

        try:
            actual_file_path = file_path
            sheet_name = None
            if ":::" in file_path:
                actual_file_path, sheet_name = file_path.split(":::", 1)

            # Load the new file
            if actual_file_path.endswith('.xlsx') or actual_file_path.endswith('.xls'):
                import pandas as pd
                df = pd.read_excel(actual_file_path, sheet_name=sheet_name, header=None)
                data = df.fillna('').astype(str).values.tolist()
            else:
                # CSV file
                with open(actual_file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    data = list(reader)

            # Find headers in the new file
            size_header_pos = None
            percent_header_pos = None

            # Clean pattern headers (remove quotes if present)
            pattern_size_header = pattern['size_header'].strip("'\"")
            pattern_percent_header = pattern['percent_header'].strip("'\"")

            for row_idx, row in enumerate(data):
                for col_idx, cell in enumerate(row):
                    # Clean cell value (remove quotes, spaces)
                    cell_value = str(cell).strip().strip("'\"")

                    if cell_value == pattern_size_header:
                        size_header_pos = (row_idx, col_idx)
                    if cell_value == pattern_percent_header:
                        percent_header_pos = (row_idx, col_idx)

            if not size_header_pos or not percent_header_pos:
                # More detailed error message
                found_headers = []
                for row_idx, row in enumerate(data[:15]):  # Check first 15 rows
                    for col_idx, cell in enumerate(row):
                        cell_value = str(cell).strip().strip("'\"")
                        if cell_value and not self.is_numeric(cell_value):
                            found_headers.append(f"Row {row_idx}, Col {col_idx}: '{cell_value}'")

                raise ValueError(f"Could not find headers '{pattern_size_header}' or '{pattern_percent_header}' in file.\n"
                               f"Found headers: {found_headers[:10]}")

            # Extract data starting from offset below headers
            size_col = size_header_pos[1]
            percent_col = percent_header_pos[1]
            data_start_row = size_header_pos[0] + pattern['data_offset']

            # Extract data more robustly
            size_data = []
            percent_data = []
            stop_words = ['Pan', 'Sum', 'Total', 'pan', 'sum', 'total']

            # Search for numeric data rows, handling both columns consistently
            for row_idx in range(data_start_row, min(len(data), data_start_row + 20)):
                if row_idx >= len(data):
                    break

                row = data[row_idx]

                # Check if we hit a stop word in the size column
                if size_col < len(row):
                    size_cell = str(row[size_col]).strip().strip("'\"")
                    if size_cell in stop_words:
                        break

                # Extract both values from the same row
                size_value = None
                percent_value = None

                # Get size data
                if size_col < len(row):
                    size_cell = str(row[size_col]).strip().strip("'\"")
                    if size_cell and size_cell.lower() not in ['nan', ''] and self.is_numeric(size_cell):
                        size_value = float(size_cell)

                # Get percent data
                if percent_col < len(row):
                    percent_cell = str(row[percent_col]).strip().strip("'\"")
                    if percent_cell and percent_cell.lower() not in ['nan', ''] and self.is_numeric(percent_cell):
                        percent_value = float(percent_cell)

                # Only add if both values are valid and size > 0
                if size_value is not None and percent_value is not None and size_value > 0:
                    size_data.append(size_value)
                    percent_data.append(percent_value)

            if not size_data or not percent_data or len(size_data) != len(percent_data):
                # Enhanced error message with debug info
                debug_info = f"Extracted {len(size_data)} size values and {len(percent_data)} percent values.\n"
                debug_info += f"Data start row: {data_start_row}, Size col: {size_col}, Percent col: {percent_col}\n"

                if size_data:
                    debug_info += f"Size data sample: {size_data[:5]}\n"
                if percent_data:
                    debug_info += f"Percent data sample: {percent_data[:5]}\n"

                # Show some raw data for debugging
                debug_info += "Raw data rows:\n"
                for i in range(data_start_row, min(len(data), data_start_row + 5)):
                    if i < len(data):
                        row = data[i]
                        size_val = row[size_col] if size_col < len(row) else "N/A"
                        percent_val = row[percent_col] if percent_col < len(row) else "N/A"
                        debug_info += f"  Row {i}: size='{size_val}', percent='{percent_val}'\n"

                raise ValueError(f"Could not extract matching size and percent data using learned pattern.\n{debug_info}")

            return {
                'particle_sizes': size_data,
                'percent_passing': percent_data,
                'sample_name': os.path.splitext(os.path.basename(actual_file_path))[0],
                'temperature': 10.0,
                'porosity': 0.4,
                'sheet_name': sheet_name,
            }

        except Exception as e:
            raise ValueError(f"Pattern application failed: {str(e)}")

    def has_learned_pattern(self) -> bool:
        """Check if a pattern has been learned"""
        return self.learned_pattern is not None

    def apply_pattern_to_batch(self):
        """Apply learned pattern to other error tabs with failed Excel files"""
        # First check if we have ranges selected to learn from
        if not self.selected_size_range or not self.selected_percent_range:
            QMessageBox.warning(self, "No Selection",
                              "Please select size and percent data ranges first before applying to batch.")
            return

        # Learn pattern from current selection
        pattern = self.learn_pattern_from_selection()
        if not pattern:
            QMessageBox.warning(self, "Pattern Learning Failed",
                              "Could not learn pattern from selected ranges. Make sure headers are visible above your data.")
            return

        # Use direct reference to main window
        if not self.main_window or not hasattr(self.main_window, 'dataset_tabs_widget'):
            QMessageBox.warning(self, "Error", "Main application window not available for batch processing.")
            return

        main_window = self.main_window
        current_file_key = self.file_path
        if self.forced_sheet_name:
            current_file_key = f"{self.file_path}:::{self.forced_sheet_name}"

        # Find other error tabs with Excel files
        from gui.error_tab import ErrorTab
        error_tabs = []
        for i in range(main_window.dataset_tabs_widget.count()):
            widget = main_window.dataset_tabs_widget.widget(i)
            actual_file_path = getattr(widget, "actual_file_path", getattr(widget, "file_path", ""))
            if isinstance(widget, ErrorTab) and widget.file_path != current_file_key:
                # Check if it's an Excel file
                if actual_file_path.endswith('.xls') or actual_file_path.endswith('.xlsx'):
                    error_tabs.append(widget)

        if not error_tabs:
            QMessageBox.information(self, "No Error Tabs", "No other Excel error tabs found to apply pattern to.")
            return

        # Show confirmation dialog
        file_list = "\n".join([f"- {os.path.basename(tab.file_path)}" for tab in error_tabs[:5]])
        if len(error_tabs) > 5:
            file_list += f"\n... and {len(error_tabs) - 5} more"

        reply = QMessageBox.question(self, "Batch Fix Error Tabs",
                                   f"Found {len(error_tabs)} Excel error tabs to fix.\n\n"
                                   f"Pattern learned:\n"
                                   f"- Size header: '{pattern['size_header']}'\n"
                                   f"- Percent header: '{pattern['percent_header']}'\n"
                                   f"- Data offset: {pattern['data_offset']} rows below headers\n\n"
                                   f"Files to fix:\n{file_list}\n\n"
                                   f"Apply this pattern to fix these error tabs?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Process each error tab
        successful_fixes = []
        failed_fixes = []
        control_panel = getattr(main_window, "control_panel", None)
        mapping_state = self.get_mapping_state() if hasattr(self, "get_mapping_state") else None

        for error_tab in error_tabs:
            try:
                # Apply pattern to extract data
                result = self.apply_pattern_to_file(error_tab.file_path)

                if control_panel is not None and hasattr(control_panel, "_apply_mapping_results"):
                    control_panel._apply_mapping_results(
                        error_tab.file_path,
                        [result],
                        forced_sheet_name=getattr(error_tab, "sheet_name", None),
                        mapping_state=mapping_state,
                    )
                else:
                    # Fallback for tests or legacy embedding without a control panel.
                    dataset = GrainSizeData(
                        particle_sizes=result['particle_sizes'],
                        percent_passing=result['percent_passing'],
                        sample_name=result['sample_name'],
                        temperature=result['temperature'],
                        porosity=result['porosity'],
                        file_path=error_tab.file_path,
                    )
                    error_tab.dataset_fixed.emit(dataset, error_tab.file_path)
                successful_fixes.append(error_tab.file_path)

            except Exception as e:
                failed_fixes.append((error_tab.file_path, str(e)))

        # Show results
        result_msg = f"Batch fix complete!\n\n"
        result_msg += f"Successfully fixed: {len(successful_fixes)} files\n"
        result_msg += f"Failed to fix: {len(failed_fixes)} files\n\n"

        if successful_fixes:
            result_msg += "Successfully fixed:\n"
            for file_path in successful_fixes[:5]:  # Show first 5
                filename = os.path.basename(file_path)
                result_msg += f"- {filename}\n"
            if len(successful_fixes) > 5:
                result_msg += f"... and {len(successful_fixes) - 5} more\n"

        if failed_fixes:
            result_msg += f"\nFailed to fix:\n"
            for file_path, error in failed_fixes[:3]:  # Show first 3 errors
                filename = os.path.basename(file_path)
                result_msg += f"- {filename}: {error[:50]}...\n"

        QMessageBox.information(self, "Batch Fix Results", result_msg)
