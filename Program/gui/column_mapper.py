"""
Column mapping dialog for CSV files with unknown formats
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
                            QDialogButtonBox, QGroupBox, QFormLayout, QSpinBox,
                            QDoubleSpinBox, QTextEdit, QWidget,
                            QMessageBox, QCheckBox, QListWidget, QListWidgetItem,
                            QScrollArea, QSplitter, QFrame, QSizePolicy,
                            QAbstractScrollArea, QGridLayout, QHeaderView,
                            QStyledItemDelegate, QApplication)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QBrush, QPainter, QPen, QPainterPath
import csv
from typing import Dict, List, Optional, Tuple
import os
from data_loader import GrainSizeData
from excel_import_detection import (
    ImportCandidate,
    detect_multi_sample_candidates,
    extract_candidate_curve,
    find_best_import_candidate,
)
from import_resolver import resolve_excel_import
from import_preview import (
    detect_headers as detect_preview_headers,
    headers_from_row as preview_headers_from_row,
    is_numeric as is_preview_numeric,
    load_preview_rows as load_shared_preview_rows,
)
from gui.dialog_chrome import make_dialog_header, make_dialog_footer
from gui.theme import C, F, SZ, icon as _icon
from qt_chrome.frameless_dialog_base import FramelessDialogBase


class _PreviewColorDelegate(QStyledItemDelegate):
    """Paint explicit cell backgrounds before Qt draws table text."""

    def paint(self, painter, option, index):
        bg = index.data(Qt.ItemDataRole.BackgroundRole)
        if isinstance(bg, QBrush) and bg.style() != Qt.BrushStyle.NoBrush:
            painter.save()
            painter.fillRect(option.rect, bg)
            painter.restore()
        super().paint(painter, option, index)


class _CurvePreviewWidget(QWidget):
    """Small dependency-free preview of the interpreted cumulative curve."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sizes: List[float] = []
        self._passing: List[float] = []
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_curve(self, sizes: List[float], passing: List[float]) -> None:
        pairs = sorted(
            (float(size), float(value))
            for size, value in zip(sizes, passing)
            if float(size) > 0
        )
        self._sizes = [pair[0] for pair in pairs]
        self._passing = [pair[1] for pair in pairs]
        self.update()

    def clear_curve(self) -> None:
        self._sizes = []
        self._passing = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            bounds = self.rect().adjusted(34, 12, -12, -24)
            painter.fillRect(self.rect(), QColor("#fbfaf6"))

            grid_pen = QPen(QColor("#e1dacd"), 1)
            painter.setPen(grid_pen)
            for step in range(5):
                y = bounds.bottom() - (bounds.height() * step / 4)
                painter.drawLine(bounds.left(), int(y), bounds.right(), int(y))
            for step in range(4):
                x = bounds.left() + (bounds.width() * step / 3)
                painter.drawLine(int(x), bounds.top(), int(x), bounds.bottom())

            painter.setPen(QPen(QColor(C.TEXT_MUTED), 1))
            painter.drawLine(bounds.bottomLeft(), bounds.bottomRight())
            painter.drawLine(bounds.bottomLeft(), bounds.topLeft())

            if len(self._sizes) < 2:
                painter.setPen(QColor(C.TEXT_MUTED))
                painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, "Confirm the mapping to preview the curve")
                return

            import math
            logs = [math.log10(value) for value in self._sizes]
            lo, hi = min(logs), max(logs)
            if hi == lo:
                hi = lo + 1.0

            path = QPainterPath()
            for index, (log_size, passing) in enumerate(zip(logs, self._passing)):
                x = bounds.left() + (log_size - lo) / (hi - lo) * bounds.width()
                y = bounds.bottom() - max(0.0, min(100.0, passing)) / 100.0 * bounds.height()
                if index == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.setPen(QPen(QColor(C.OLIVE), 2.2))
            painter.drawPath(path)
        finally:
            painter.end()


class ColumnMapperDialog(FramelessDialogBase):
    """Dialog for mapping CSV columns to grain size data"""

    def sizeHint(self):
        return QSize(1380, 820)

    def minimumSizeHint(self):
        return QSize(980, 660)

    def __init__(
        self,
        file_path: str,
        parent=None,
        main_window=None,
        sheet_name: str = None,
        initial_state: Optional[Dict] = None,
        multi_sample_mode: bool = False,
    ):
        super().__init__(parent, default_mode="auto")
        self.file_path = file_path
        self.main_window = main_window  # Direct reference to main window
        self.forced_sheet_name = sheet_name  # If provided, only work with this specific sheet
        self._initial_state = initial_state or {}
        self._multi_sample_requested = bool(
            multi_sample_mode or self._initial_state.get("multi_sample_mode")
        )
        self.column_mapping = {}
        self.sample_data = []
        self.headers = []
        self.detected_import_candidate: Optional[ImportCandidate] = None
        self.multi_sample_candidates: Tuple[ImportCandidate, ...] = ()
        self.multi_sample_list = None
        self._multi_sample_section = None
        self.excel_sheets = []  # Available Excel sheets
        self.sheet_list = None  # Multi-sheet selection widget
        self._excel_file = None  # Cached ExcelFile reference
        self.current_sheet = None
        self.header_row = 0  # Detected header row
        self.cell_range_mode = False  # False = column mapping, True = cell range selection
        self.raw_sieve_mode = False  # True = user provides raw sieve weighings instead of pre-calculated % passing
        self.calculated_selection_mode = "column"
        self.selected_size_range = []  # List of (row, col) tuples for size data
        self.selected_percent_range = []  # List of (row, col) tuples for percent data
        self.selected_empty_range = []  # Raw sieve: empty-sieve weights
        self.selected_full_range = []  # Raw sieve: sieve + sample weights
        self.selected_headers = []  # Compatibility state used by batch range reuse
        self.learned_pattern = None  # Stores pattern for batch processing
        self._batch_apply_committed = False
        self.pathway_summary_label = None
        self.sheet_info_label = None
        self.preview_hint_label = None
        self.preview_footer_status_label = None
        self._file_meta_label = None
        self._file_mapping_status_label = None
        self._file_header_label = None
        self._footer_status_label = None
        self._mapping_splitter = None
        self._sheet_group = None
        self._import_section = None
        self._header_section = None
        self._method_section = None
        self._mapping_section = None
        self._range_section = None
        self._raw_section = None
        self._sheet_section = None
        self.input_format_group = None
        self.range_step = 0
        self.result_curve = None
        self.result_status_label = None
        self.result_metrics_label = None
        self.batch_status_label = None
        self.batch_review_btn = None
        self.import_button = None
        self.active_range_label = None
        self._footer_status_icon = None

        # Update window title to show sheet if provided
        if sheet_name:
            self.setWindowTitle(f"Map Columns - {os.path.basename(file_path)} [{sheet_name}]")
        else:
            self.setWindowTitle(f"Map Columns - {os.path.basename(file_path)}")
        self.setModal(True)
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry().size() if screen is not None else QSize(1440, 900)
        initial_width = max(980, min(1380, int(available.width() * 0.94)))
        initial_height = max(660, min(820, int(available.height() * 0.90)))
        self.resize(initial_width, initial_height)
        self.setMinimumSize(980, 660)

        # Styling — body inherits global QSS; patch specifics here
        self.setStyleSheet(
            f"QGroupBox {{ font-weight: 700; border: none; "
            f"margin-top: 0px; padding-top: 0px; background: transparent; "
            f"font-size: {F.SZ_SM}pt; color: {C.TEXT_MUTED}; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 0px; "
            f"padding: 0; color: transparent; background: transparent; }}"
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
        self.sample_data = rows
        self.detected_import_candidate = None
        self.multi_sample_candidates = ()
        if (
            self._multi_sample_requested
            and not self._initial_state.get("raw_sieve_mode")
        ):
            self.multi_sample_candidates = detect_multi_sample_candidates(
                self.sample_data,
                sheet_name=self.current_sheet,
            )
        if os.path.splitext(self.file_path)[1].lower() in ['.xlsx', '.xls']:
            self.detected_import_candidate = find_best_import_candidate(
                self.sample_data,
                sheet_name=self.current_sheet,
            )

    @staticmethod
    def load_preview_rows(
        file_path: str,
        *,
        sheet_name: Optional[str] = None,
        excel_sheets: Optional[List[str]] = None,
    ) -> tuple[List[List[str]], List[str], Optional[str]]:
        """Load raw preview rows using the same strategy across preview surfaces."""
        return load_shared_preview_rows(
            file_path,
            sheet_name=sheet_name,
            excel_sheets=excel_sheets,
        )

    @staticmethod
    def headers_from_row(rows: List[List[str]], row_index: int) -> List[str]:
        return preview_headers_from_row(rows, row_index)

    def detect_headers(self, rows: List[List[str]]) -> List[str]:
        """Try to detect which row contains headers"""
        headers, header_row = detect_preview_headers(rows)
        self.header_row = header_row
        return headers

    @staticmethod
    def is_numeric(value_or_self, value: Optional[str] = None) -> bool:
        """Check if a string represents a number"""
        raw_value = value_or_self if value is None else value
        return is_preview_numeric(raw_value)

    def _style_mode_button(self, button: QPushButton, fa_name: str) -> None:
        button.setCheckable(True)
        button.setMinimumHeight(46)
        button.setMinimumWidth(0)
        button.setIconSize(QSize(14, 14))
        button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        try:
            button.setIcon(_icon(fa_name, C.TEXT_MUTED))
        except Exception:
            pass
        button.setStyleSheet(
            f"QPushButton {{ border: 1px solid {C.BORDER}; border-radius: 6px; "
            f"border-left: 3px solid transparent; "
            f"background: rgba(255,255,255,.28); color: {C.TEXT_MID}; "
            f"padding: 7px 10px; text-align: left; font-weight: 600; font-size: {F.SZ_SM}pt; }}"
            f"QPushButton:hover {{ background: {C.BG_LOW}; border-color: {C.BORDER_DK}; color: {C.TEXT}; }}"
            f"QPushButton:checked {{ background: rgba(107,142,35,.08); "
            f"border-color: rgba(107,142,35,.34); border-left: 3px solid {C.OLIVE}; color: {C.TEXT}; }}"
            f"QPushButton:disabled {{ background: rgba(255,255,255,.12); color: {C.TEXT_MUTED}; }}"
        )

    def _style_tool_button(self, button: QPushButton, fa_name: str = "", *, primary: bool = False) -> None:
        button.setMinimumHeight(44)
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

    def _style_preview_action_button(self, button: QPushButton, fa_name: str = "") -> None:
        button.setFixedHeight(26)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if fa_name:
            try:
                button.setIcon(_icon(fa_name, C.TEXT_MID, 12))
            except Exception:
                pass
        button.setStyleSheet(
            f"QPushButton {{ border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
            f"background: {C.BG_RAISED}; color: {C.TEXT_MID}; padding: 0 9px; "
            f"font-size: {F.SZ_SM}pt; }}"
            f"QPushButton:hover {{ background: {C.BG_LOW}; border-color: {C.BORDER_DK}; color: {C.TEXT}; }}"
        )

    def _style_plain_group(self, group: QGroupBox) -> None:
        group.setTitle("")
        group.setStyleSheet(
            "QGroupBox { border: none; margin: 0; padding: 0; background: transparent; }"
            "QGroupBox::title { color: transparent; padding: 0; margin: 0; height: 0; }"
            "QGroupBox QLabel { background: transparent; }"
        )

    def _make_inspector_section(self, title: str, fa_name: str, content: QWidget) -> QFrame:
        if isinstance(content, QGroupBox):
            self._style_plain_group(content)

        card = QFrame()
        card.setObjectName("columnMapperSection")
        card.setStyleSheet(
            f"QFrame#columnMapperSection {{ border: 1px solid {C.BORDER}; border-radius: 6px; "
            f"background: rgba(255,255,255,.34); }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("columnMapperSectionHeader")
        header.setStyleSheet(
            f"QWidget#columnMapperSectionHeader {{ background: {C.BG_RAISED}; "
            f"border-bottom: 1px solid {C.BORDER}; border-top-left-radius: 6px; "
            f"border-top-right-radius: 6px; }}"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 7, 12, 7)
        header_layout.setSpacing(8)

        icon_label = QLabel()
        try:
            icon_label.setPixmap(_icon(fa_name, C.OLIVE, 12).pixmap(12, 12))
        except Exception:
            icon_label.setText("")
        icon_label.setStyleSheet("background: transparent; border: none;")
        header_layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setFont(QFont(F.UI, F.SZ_SM, QFont.Weight.DemiBold))
        title_label.setStyleSheet(f"color: {C.TEXT_MID}; background: transparent; border: none;")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        card_layout.addWidget(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(10, 9, 10, 10)
        body_layout.setSpacing(0)
        body_layout.addWidget(content)
        card_layout.addWidget(body)
        return card

    def setup_ui(self):
        """Setup the dialog UI"""
        import os as _os
        fname = _os.path.basename(self.file_path)
        sheet_part = f" [{self.current_sheet}]" if self.current_sheet else ""
        subtitle = f"{fname}{sheet_part} - review the interpreted data before import"

        # Root layout — header / body / footer, no margins
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header_widget = make_dialog_header(
            "Confirm imported data",
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

        mapping_tab = QWidget()
        mapping_layout = QVBoxLayout(mapping_tab)
        mapping_layout.setContentsMargins(0, 0, 0, 0)
        mapping_layout.setSpacing(0)

        file_strip = self._build_file_strip()
        mapping_layout.addWidget(file_strip)

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
        input_format_layout = QVBoxLayout(input_format_group)
        input_format_layout.setContentsMargins(10, 8, 10, 10)
        input_format_layout.setSpacing(6)

        self.calculated_data_btn = QPushButton("Processed curve")
        self.raw_sieve_btn = QPushButton("Raw sieve weighings")

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
        self.pathway_summary_label.setWordWrap(False)
        self.pathway_summary_label.setFixedHeight(32)
        self.pathway_summary_label.setFont(QFont(F.MONO, F.SZ_XS))
        self.pathway_summary_label.setStyleSheet(
            f"QLabel {{ border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
            f"background: {C.BG}; color: {C.TEXT_MID}; padding: 0 9px; }}"
        )
        self.pathway_summary_label.hide()
        # Added to the left inspector below.

        # Preview pane
        preview_group = QWidget()
        preview_group.setObjectName("columnMapperPreview")
        preview_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_group.setStyleSheet(
            f"QWidget#columnMapperPreview {{ background: {C.BG}; border-left: 1px solid {C.BORDER}; }}"
            f"QWidget#columnMapperPreview QLabel {{ background: transparent; }}"
        )
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        preview_head = QWidget()
        preview_head.setObjectName("columnMapperPreviewHead")
        preview_head.setFixedHeight(44)
        preview_head.setStyleSheet(
            f"QWidget#columnMapperPreviewHead {{ background: {C.BG}; border-bottom: 1px solid {C.BORDER}; }}"
        )
        preview_head_layout = QHBoxLayout(preview_head)
        preview_head_layout.setContentsMargins(14, 0, 14, 0)
        preview_head_layout.setSpacing(8)

        preview_icon = QLabel()
        try:
            preview_icon.setPixmap(_icon("fa6s.table", C.EARTH, 13).pixmap(13, 13))
        except Exception:
            preview_icon.setText("")
        preview_head_layout.addWidget(preview_icon)

        preview_title = QLabel("Data Preview")
        preview_title.setStyleSheet(f"font-weight: 700; color: {C.TEXT};")
        preview_head_layout.addWidget(preview_title)
        preview_head_layout.addStretch(1)

        preview_layout.addWidget(preview_head)

        self.preview_hint_label = QLabel(preview_group)
        self.preview_hint_label.setWordWrap(True)
        self.preview_hint_label.hide()

        self.preview_table = QTableWidget()
        self.preview_table.setItemDelegate(_PreviewColorDelegate(self.preview_table))
        self.preview_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_table.setMinimumHeight(0)
        self.preview_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.setup_preview_table()
        preview_layout.addWidget(self.preview_table, 1)

        preview_foot = QWidget()
        preview_foot.setObjectName("columnMapperPreviewFoot")
        preview_foot.setFixedHeight(38)
        preview_foot.setStyleSheet(
            f"QWidget#columnMapperPreviewFoot {{ background: {C.BG}; border-top: 1px solid {C.BORDER}; }}"
        )
        preview_foot_layout = QHBoxLayout(preview_foot)
        preview_foot_layout.setContentsMargins(14, 0, 14, 0)
        preview_foot_layout.setSpacing(7)

        for color, label_text in [
            ("#6884ab", "Particle size"),
            (C.OLIVE, "Cumulative percent passing"),
            ("#a88452", "Header row"),
        ]:
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
            legend_label = QLabel(label_text)
            legend_label.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt;")
            preview_foot_layout.addWidget(dot)
            preview_foot_layout.addWidget(legend_label)

        preview_foot_layout.addStretch(1)
        self.preview_footer_status_label = QLabel()
        self.preview_footer_status_label.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt;")
        preview_foot_layout.addWidget(self.preview_footer_status_label)
        preview_layout.addWidget(preview_foot)

        # Guided selection exposes one role at a time for irregular sheets.
        self.range_tools_group = QGroupBox("Guided cell ranges")
        range_tools_layout = QVBoxLayout(self.range_tools_group)
        range_tools_layout.setContentsMargins(10, 8, 10, 10)
        range_tools_layout.setSpacing(8)

        self.range_step_label = QLabel()
        self.range_step_label.setWordWrap(True)
        self.range_step_label.setStyleSheet(
            f"color: {C.TEXT}; font-weight: 600; background: rgba(107,142,35,.07); "
            f"border-left: 3px solid {C.OLIVE}; padding: 8px;"
        )
        range_tools_layout.addWidget(self.range_step_label)

        self.active_range_label = QLabel("Current selection: none")
        self.active_range_label.setFont(QFont(F.MONO, F.SZ_XS))
        self.active_range_label.setWordWrap(True)
        self.active_range_label.setStyleSheet(
            f"color: {C.TEXT_MID}; background: {C.BG}; border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; padding: 6px 8px;"
        )
        range_tools_layout.addWidget(self.active_range_label)

        self.confirm_range_btn = QPushButton("Use selected cells")
        self.confirm_range_btn.clicked.connect(self._confirm_guided_range_selection)
        self._style_tool_button(self.confirm_range_btn, "fa6s.check", primary=True)
        self.confirm_range_btn.setEnabled(False)
        range_tools_layout.addWidget(self.confirm_range_btn)

        self.clear_ranges_btn = QPushButton("Start over")
        self.clear_ranges_btn.clicked.connect(self.clear_range_selection)
        self._style_tool_button(self.clear_ranges_btn, "fa6s.arrow-rotate-left")
        range_tools_layout.addWidget(self.clear_ranges_btn)

        self.batch_apply_btn = QPushButton("Review batch matches")
        self.batch_apply_btn.clicked.connect(self.apply_pattern_to_batch)
        self.batch_apply_btn.setEnabled(False)
        self.batch_apply_btn.hide()
        self._style_tool_button(self.batch_apply_btn, "fa6s.layer-group")
        range_tools_layout.addWidget(self.batch_apply_btn)

        range_counts = QWidget()
        range_counts_layout = QVBoxLayout(range_counts)
        range_counts_layout.setContentsMargins(0, 0, 0, 0)
        range_counts_layout.setSpacing(6)
        self.size_range_count_label = QLabel("Particle size: not selected")
        self.percent_range_count_label = QLabel("Passing: not selected")
        for label in (self.size_range_count_label, self.percent_range_count_label):
            label.setFont(QFont(F.MONO, F.SZ_XS))
            label.setStyleSheet(
                f"QLabel {{ border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
                f"background: {C.BG}; color: {C.TEXT_MID}; padding: 5px 8px; }}"
            )
            range_counts_layout.addWidget(label)
        range_tools_layout.addWidget(range_counts)

        self.pattern_info_label = QLabel()
        self.pattern_info_label.setWordWrap(True)
        self.pattern_info_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt;"
        )
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
        # Kept as a hidden compatibility field so old mapping-state dictionaries
        # can be opened and rejected with a clear message.
        self.retained_combo = QComboBox(self.mapping_group)
        self.retained_combo.hide()

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

        mapping_form.addRow("Particle size:", self.size_combo)
        mapping_form.addRow("Cumulative percent passing (0-100):", self.passing_combo)

        # Header selection is shared by both input pathways and appears before roles.
        self.header_row_spin = QSpinBox()
        self.header_row_spin.setRange(1, max(1, len(self.sample_data)))
        self.header_row_spin.setValue(self.header_row + 1)
        self.header_row_spin.valueChanged.connect(self._on_header_row_spin_changed)
        header_group = QGroupBox("Locate the table")
        header_form = QFormLayout(header_group)
        header_form.setContentsMargins(10, 8, 10, 10)
        header_form.addRow("Header row:", self.header_row_spin)
        self._header_group = header_group

        # Compact guidance; detailed behavior is handled by validation and preview highlights.
        self.retained_guidance_label = QLabel(
            "Retained values cannot be used as cumulative passing. Convert the "
            "source, or choose Raw sieve weighings for original weights."
        )
        self.retained_guidance_label.setWordWrap(True)
        self.retained_guidance_label.setStyleSheet(
            f"color: #8b4e24; background: #f4e7d9; border-left: 3px solid #b7793d; "
            f"font-size: {F.SZ_SM}pt; padding: 7px;"
        )
        self.retained_guidance_label.hide()
        mapping_form.addRow(self.retained_guidance_label)

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
            "The program derives retained mass and cumulative percent passing."
        )
        raw_sieve_help.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; margin: 4px 6px 2px 6px;")

        self.raw_sieve_group.setVisible(False)
        # Added to the left inspector below.
        self.range_tools_group.setVisible(False)

        self.multi_sample_group = QGroupBox("Samples in this sheet")
        multi_layout = QVBoxLayout(self.multi_sample_group)
        multi_layout.setContentsMargins(10, 8, 10, 10)
        multi_layout.setSpacing(8)
        self.multi_sample_summary_label = QLabel()
        self.multi_sample_summary_label.setWordWrap(True)
        self.multi_sample_summary_label.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt;"
        )
        multi_layout.addWidget(self.multi_sample_summary_label)
        self.multi_sample_list = QListWidget()
        self.multi_sample_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        self.multi_sample_list.setMinimumHeight(150)
        self.multi_sample_list.setMaximumHeight(260)
        self.multi_sample_list.itemChanged.connect(
            self._on_multi_sample_item_changed
        )
        self.multi_sample_list.currentItemChanged.connect(
            self._on_multi_sample_current_changed
        )
        multi_layout.addWidget(self.multi_sample_list)
        self.multi_sample_group.hide()

        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setFrameShape(QFrame.Shape.NoFrame)
        controls_scroll.setStyleSheet(
            f"QScrollArea {{ background: {C.BG_RAISED}; border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background: {C.BG_RAISED}; }}"
        )
        controls_scroll.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls_scroll.setMinimumWidth(370)
        controls_scroll.setMaximumWidth(430)
        controls_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        controls_container = QWidget()
        controls_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        controls_container.setMinimumWidth(0)
        controls_container.setMaximumWidth(410)
        controls_container.setObjectName("columnMapperInspector")
        controls_container.setStyleSheet(
            f"QWidget#columnMapperInspector {{ background: {C.BG_RAISED}; }}"
        )
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(10)
        self._multi_sample_section = self._make_inspector_section(
            "Samples in this sheet", "fa6s.layer-group", self.multi_sample_group
        )
        controls_layout.addWidget(self._multi_sample_section)
        self._multi_sample_section.hide()
        if self.input_format_group is not None:
            self._import_section = self._make_inspector_section(
                "Data in this sheet", "fa6s.route", self.input_format_group
            )
            controls_layout.addWidget(self._import_section)
        self._header_section = self._make_inspector_section(
            "Locate the table", "fa6s.heading", self._header_group
        )
        controls_layout.addWidget(self._header_section)
        self._mapping_section = self._make_inspector_section(
            "Confirm curve columns", "fa6s.list-check", self.mapping_group
        )
        self._range_section = self._make_inspector_section(
            "Select cell ranges", "fa6s.object-group", self.range_tools_group
        )
        self._raw_section = self._make_inspector_section(
            "Confirm weighing columns", "fa6s.scale-balanced", self.raw_sieve_group
        )
        controls_layout.addWidget(self._mapping_section)
        controls_layout.addWidget(self._range_section)
        controls_layout.addWidget(self._raw_section)
        self.range_toggle_btn = QPushButton("Use cell ranges for an irregular sheet")
        self.range_toggle_btn.clicked.connect(self._toggle_range_workflow)
        self._style_tool_button(self.range_toggle_btn, "fa6s.object-group")
        controls_layout.addWidget(self.range_toggle_btn)
        if self._sheet_group is not None:
            self._sheet_section = self._make_inspector_section(
                "Sheets", "fa6s.file-excel", self._sheet_group
            )
            controls_layout.addWidget(self._sheet_section)
        controls_layout.addStretch()
        controls_scroll.setWidget(controls_container)

        result_panel = QWidget()
        result_panel.setObjectName("columnMapperResult")
        result_panel.setMinimumWidth(280)
        result_panel.setMaximumWidth(340)
        result_panel.setStyleSheet(
            f"QWidget#columnMapperResult {{ background: {C.BG}; "
            f"border-left: 1px solid {C.BORDER}; }}"
        )
        result_layout = QVBoxLayout(result_panel)
        result_layout.setContentsMargins(14, 14, 14, 14)
        result_layout.setSpacing(10)

        result_title = QLabel("Interpreted result")
        result_title.setStyleSheet(f"color: {C.TEXT}; font-weight: 700;")
        result_layout.addWidget(result_title)
        result_help = QLabel("This is the curve the program will analyze.")
        result_help.setWordWrap(True)
        result_help.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt;")
        result_layout.addWidget(result_help)

        self.result_status_label = QLabel("Confirm the required roles")
        self.result_status_label.setWordWrap(True)
        self.result_status_label.setStyleSheet(
            f"background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; color: {C.TEXT_MID}; padding: 8px;"
        )
        result_layout.addWidget(self.result_status_label)

        self.result_curve = _CurvePreviewWidget()
        result_layout.addWidget(self.result_curve)

        self.result_metrics_label = QLabel()
        self.result_metrics_label.setWordWrap(True)
        self.result_metrics_label.setFont(QFont(F.MONO, F.SZ_XS))
        self.result_metrics_label.setStyleSheet(
            f"color: {C.TEXT_MID}; border-top: 1px solid {C.BORDER}; padding-top: 8px;"
        )
        result_layout.addWidget(self.result_metrics_label)

        self.checks_title = QLabel("Checks")
        self.checks_title.setStyleSheet(f"color: {C.TEXT}; font-weight: 700; margin-top: 4px;")
        result_layout.addWidget(self.checks_title)
        self.result_checks_label = QLabel()
        self.result_checks_label.setWordWrap(True)
        self.result_checks_label.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt;"
        )
        result_layout.addWidget(self.result_checks_label)

        self.batch_status_label = QLabel()
        self.batch_status_label.setWordWrap(True)
        self.batch_status_label.hide()
        self.batch_status_label.setStyleSheet(
            f"background: rgba(107,142,35,.07); border-left: 3px solid {C.OLIVE}; "
            f"color: {C.TEXT_MID}; padding: 8px;"
        )
        result_layout.addWidget(self.batch_status_label)
        result_layout.addStretch(1)

        self._mapping_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._mapping_splitter.setChildrenCollapsible(False)
        self._mapping_splitter.setHandleWidth(6)
        self._mapping_splitter.setStyleSheet(
            f"QSplitter::handle:horizontal {{ background: {C.BORDER}; margin: 0; }}"
            f"QSplitter::handle:horizontal:hover {{ background: {C.OLIVE}; }}"
        )
        self._mapping_splitter.addWidget(controls_scroll)
        self._mapping_splitter.addWidget(preview_group)
        self._mapping_splitter.addWidget(result_panel)
        self._mapping_splitter.setStretchFactor(0, 0)
        self._mapping_splitter.setStretchFactor(1, 1)
        self._mapping_splitter.setStretchFactor(2, 0)
        self._mapping_splitter.setSizes([390, 680, 310])
        self._mapping_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        mapping_layout.addWidget(self._mapping_splitter, 1)

        params_tab = QWidget()
        params_layout = QVBoxLayout(params_tab)

        params_group = QGroupBox("Sample Parameters")
        params_group.setStyleSheet(
            f"QGroupBox {{ font-weight: 600; border: 1px solid {C.BORDER}; "
            f"border-radius: 6px; margin-top: 8px; padding-top: 10px; "
            f"background: {C.BG}; font-size: {F.SZ_MD}pt; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; "
            f"padding: 0 4px; color: {C.TEXT_MID}; background: {C.BG}; }}"
        )
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
        self.sample_name_label = params_form.labelForField(self.sample_name_edit)

        params_layout.addWidget(params_group)
        params_layout.addStretch()

        self.sample_details_group = params_group
        self.sample_details_group.setParent(controls_container)
        self.sample_details_group.hide()
        self.sample_details_button = QPushButton("Sample details (optional)")
        self.sample_details_button.setCheckable(True)
        self.sample_details_button.clicked.connect(self._toggle_sample_details)
        self._style_tool_button(self.sample_details_button, "fa6s.sliders")
        insert_at = max(0, controls_layout.count() - 1)
        controls_layout.insertWidget(insert_at, self.sample_details_button)
        controls_layout.insertWidget(insert_at + 1, self.sample_details_group)

        # The mapper is one confirmation surface; optional details are disclosed inline.
        layout.addWidget(mapping_tab)
        mapping_tab.setVisible(True)

        footer = make_dialog_footer([
            ("Cancel", self.reject, "secondary"),
            ("Restore detected mapping", self._rerun_auto_detection, "secondary"),
            ("Import sample", self.accept, "primary"),
        ])
        for button in footer.findChildren(QPushButton):
            if button.text() == "Import sample":
                self.import_button = button
            elif button.text() == "Restore detected mapping":
                self.restore_detection_button = button
        self.restore_detection_button.setVisible(self.detected_import_candidate is not None)
        root.addWidget(footer)

        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )
        if not self._initial_state:
            self._apply_detected_import_candidate()
        self._apply_mode_state()
        self._apply_multi_sample_mode()

    def _set_header_row_from_candidate(self, candidate: ImportCandidate) -> None:
        self.header_row = max(0, int(candidate.header_row))
        self._refresh_column_options_for_header_row(self.header_row, preserve_indices=True)
        if hasattr(self, 'header_row_spin'):
            self.header_row_spin.blockSignals(True)
            self.header_row_spin.setRange(1, max(1, len(self.sample_data)))
            self.header_row_spin.setValue(
                min(self.header_row + 1, self.header_row_spin.maximum())
            )
            self.header_row_spin.blockSignals(False)

    def _on_header_row_spin_changed(self, visible_row: int) -> None:
        self.update_headers(max(0, int(visible_row) - 1))

    def _is_multi_sample_mode(self) -> bool:
        return bool(self.multi_sample_candidates) and not self.raw_sieve_mode

    def _populate_multi_sample_list(self) -> None:
        if self.multi_sample_list is None:
            return
        self.multi_sample_list.blockSignals(True)
        self.multi_sample_list.clear()
        for index, candidate in enumerate(self.multi_sample_candidates):
            item = QListWidgetItem(
                f"{candidate.sample_name}\n{candidate.source_label}"
            )
            item.setData(Qt.ItemDataRole.UserRole, index)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(Qt.CheckState.Checked)
            item.setToolTip(
                f"{candidate.sample_name} - {candidate.source_label}"
            )
            self.multi_sample_list.addItem(item)
        self.multi_sample_list.blockSignals(False)
        if self.multi_sample_list.count():
            self.multi_sample_list.setCurrentRow(0)

    def _selected_multi_sample_candidates(self) -> List[ImportCandidate]:
        if self.multi_sample_list is None:
            return []
        selected: List[ImportCandidate] = []
        for row in range(self.multi_sample_list.count()):
            item = self.multi_sample_list.item(row)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            index = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(index, int) and 0 <= index < len(self.multi_sample_candidates):
                selected.append(self.multi_sample_candidates[index])
        return selected

    def _current_multi_sample_candidate(self) -> Optional[ImportCandidate]:
        if self.multi_sample_list is None:
            return None
        item = self.multi_sample_list.currentItem()
        if item is None:
            return None
        index = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(index, int) and 0 <= index < len(self.multi_sample_candidates):
            return self.multi_sample_candidates[index]
        return None

    def _apply_multi_sample_mode(self) -> None:
        active = self._is_multi_sample_mode()
        if self._multi_sample_section is not None:
            self._multi_sample_section.setVisible(active)
        if self.multi_sample_group is not None:
            self.multi_sample_group.setVisible(active)
        if not active:
            if self._import_section is not None:
                self._import_section.show()
            if self._sheet_section is not None:
                self._sheet_section.show()
            self.range_toggle_btn.show()
            self.restore_detection_button.setVisible(
                self.detected_import_candidate is not None
            )
            self.sample_name_edit.show()
            if getattr(self, "sample_name_label", None) is not None:
                self.sample_name_label.show()
            return

        self.raw_sieve_mode = False
        self.calculated_selection_mode = "range"
        self.cell_range_mode = True
        self._populate_multi_sample_list()
        self.multi_sample_summary_label.setText(
            f"{len(self.multi_sample_candidates)} independent curves were detected. "
            "Clear any sample you do not want to import."
        )
        for section in (
            self._import_section,
            self._header_section,
            self._mapping_section,
            self._range_section,
            self._raw_section,
            self._sheet_section,
        ):
            if section is not None:
                section.hide()
        self.range_toggle_btn.hide()
        self.restore_detection_button.hide()
        self.sample_name_edit.hide()
        if getattr(self, "sample_name_label", None) is not None:
            self.sample_name_label.hide()
        self._update_multi_sample_import_state()
        self._preview_multi_sample_candidate(
            self._current_multi_sample_candidate()
        )

    def _on_multi_sample_item_changed(self, _item: QListWidgetItem) -> None:
        self._update_multi_sample_import_state()

    def _on_multi_sample_current_changed(
        self,
        current: Optional[QListWidgetItem],
        _previous: Optional[QListWidgetItem],
    ) -> None:
        candidate = None
        if current is not None:
            index = current.data(Qt.ItemDataRole.UserRole)
            if isinstance(index, int) and 0 <= index < len(self.multi_sample_candidates):
                candidate = self.multi_sample_candidates[index]
        self._preview_multi_sample_candidate(candidate)

    def _update_multi_sample_import_state(self) -> None:
        selected_count = len(self._selected_multi_sample_candidates())
        if self.import_button is not None:
            self.import_button.setEnabled(selected_count > 0)
            self.import_button.setText(
                f"Import {selected_count} "
                f"{'sample' if selected_count == 1 else 'samples'}"
            )
        if self.preview_footer_status_label is not None:
            self.preview_footer_status_label.setText(
                f"{selected_count} of {len(self.multi_sample_candidates)} selected"
            )

    def _highlight_multi_sample_candidate(
        self,
        candidate: ImportCandidate,
    ) -> None:
        if not hasattr(self, "preview_table"):
            return
        size_cells = set(candidate.size_cells)
        passing_cells = set(candidate.passing_cells)
        for row in range(self.preview_table.rowCount()):
            for column in range(self.preview_table.columnCount()):
                item = self.preview_table.item(row, column)
                if item is None:
                    continue
                if row == candidate.header_row:
                    color = QColor("#eadfc9")
                elif (row, column) in size_cells:
                    color = QColor("#c3d7ea")
                elif (row, column) in passing_cells:
                    color = QColor("#cfe3b4")
                elif self.is_numeric(item.text().strip()):
                    color = QColor("#edf3e6")
                else:
                    color = QColor("#ffffff")
                item.setBackground(color)
        self.preview_table.viewport().update()

    def _preview_multi_sample_candidate(
        self,
        candidate: Optional[ImportCandidate],
    ) -> None:
        if not self._is_multi_sample_mode() or candidate is None:
            return
        try:
            sizes, passing = extract_candidate_curve(
                self.sample_data,
                candidate,
            )
            self.result_curve.set_curve(sizes, passing)
            self.result_status_label.setText(candidate.sample_name)
            self.result_status_label.setStyleSheet(
                f"background: rgba(107,142,35,.08); border: 1px solid rgba(107,142,35,.30); "
                f"border-radius: {SZ.BORDER_RADIUS}px; color: {C.OLIVE_DK}; padding: 8px; "
                "font-weight: 600;"
            )
            self.result_metrics_label.setText(
                f"Source: {candidate.source_label}\n"
                f"Valid values: {len(sizes)}\n"
                f"Particle-size range: {min(sizes):.4g}-{max(sizes):.4g} mm\n"
                f"Passing range: {min(passing):.3g}-{max(passing):.3g}%"
            )
            self.checks_title.show()
            self.result_checks_label.setText(
                "Ready - cumulative percent passing is within 0-100 and "
                "the curve direction is valid."
            )
            self._highlight_multi_sample_candidate(candidate)
        except Exception as error:
            self.result_curve.clear_curve()
            self.result_status_label.setText("Candidate needs review")
            self.result_metrics_label.setText(str(error))
            self.result_checks_label.setText("")

    def _refresh_column_options_for_header_row(
        self,
        header_row: int,
        *,
        preserve_indices: bool = True,
    ) -> None:
        self.headers = self.headers_from_row(self.sample_data, header_row)
        column_options = ["(Not Used)"] + self._labeled_column_headers(self.headers)
        combos = [
            getattr(self, 'size_combo', None),
            getattr(self, 'passing_combo', None),
            getattr(self, 'retained_combo', None),
            getattr(self, 'raw_size_combo', None),
            getattr(self, 'empty_sieve_combo', None),
            getattr(self, 'sieve_sample_combo', None),
        ]
        for combo in combos:
            if combo is None:
                continue
            previous_index = combo.currentIndex()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(column_options)
            if preserve_indices and previous_index >= 0:
                combo.setCurrentIndex(
                    previous_index if previous_index < combo.count() else 0
                )
            combo.blockSignals(False)

        if hasattr(self, 'preview_table') and self.preview_table.columnCount() > 0:
            self.preview_table.setHorizontalHeaderLabels(
                self._labeled_column_headers(
                    self.headers, self.preview_table.columnCount()
                )
            )

    def _apply_detected_import_candidate(self, prefer_data_type: str = "processed_curve") -> bool:
        """Apply a backend-detected import candidate to the mapper UI."""
        if self.multi_sample_candidates and prefer_data_type == "processed_curve":
            return False
        if os.path.splitext(self.file_path)[1].lower() not in ['.xlsx', '.xls']:
            return False

        resolution = resolve_excel_import(
            self.sample_data,
            sheet_name=self.current_sheet,
            intent=prefer_data_type,
            allow_multi_sample=self._multi_sample_requested,
        )
        candidate = resolution.candidate
        if candidate is None:
            candidate = self.detected_import_candidate
        if candidate is None:
            candidate = find_best_import_candidate(
                self.sample_data,
                sheet_name=self.current_sheet,
                prefer_data_type=prefer_data_type,
            )

        if candidate is None:
            return False

        self._set_header_row_from_candidate(candidate)

        if candidate.data_type == "processed_curve" and candidate.selection_method == "range":
            self.raw_sieve_mode = False
            self.calculated_selection_mode = "range"
            self.selected_size_range = list(candidate.size_cells)
            self.selected_percent_range = list(candidate.passing_cells)
            if self.sheet_list is not None and self.current_sheet:
                for i in range(self.sheet_list.count()):
                    item = self.sheet_list.item(i)
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if item.text() == self.current_sheet
                        else Qt.CheckState.Unchecked
                    )
            self.learned_pattern = None
            if hasattr(self, 'pattern_info_label'):
                self.pattern_info_label.setText(
                    f"Detected {len(self.selected_size_range)} size cells and "
                    f"{len(self.selected_percent_range)} percent-passing cells. Review or edit before import."
                )
            if hasattr(self, 'batch_apply_btn'):
                self.batch_apply_btn.setEnabled(False)
            self.update_table_colors()
            return True

        if candidate.data_type == "raw_sieve":
            self.raw_sieve_mode = True
            column_indices = candidate.column_indices
            combo_map = {
                'raw_size': getattr(self, 'raw_size_combo', None),
                'empty_sieve': getattr(self, 'empty_sieve_combo', None),
                'sieve_sample': getattr(self, 'sieve_sample_combo', None),
            }
            for key, combo in combo_map.items():
                col_index = column_indices.get(key)
                if combo is not None and isinstance(col_index, int) and 0 <= col_index + 1 < combo.count():
                    combo.setCurrentIndex(col_index + 1)
            return True

        return False

    def _apply_mode_state(self):
        """Synchronize the dialog UI with the active data type + selection method."""
        selection_mode = self.calculated_selection_mode
        self.cell_range_mode = selection_mode == "range"

        self.calculated_data_btn.setChecked(not self.raw_sieve_mode)
        self.raw_sieve_btn.setChecked(self.raw_sieve_mode)

        if hasattr(self, 'mapping_group'):
            self.mapping_group.setVisible(not self.raw_sieve_mode and selection_mode == "column")
        if self._mapping_section is not None:
            self._mapping_section.setVisible(not self.raw_sieve_mode and selection_mode == "column")
        if hasattr(self, 'range_tools_group'):
            self.range_tools_group.setVisible(selection_mode == "range")
        if self._range_section is not None:
            self._range_section.setVisible(selection_mode == "range")
        if hasattr(self, 'raw_sieve_group'):
            self.raw_sieve_group.setVisible(self.raw_sieve_mode and selection_mode == "column")
        if self._raw_section is not None:
            self._raw_section.setVisible(self.raw_sieve_mode and selection_mode == "column")
        if self._header_section is not None:
            self._header_section.setVisible(selection_mode == "column")
        if self._method_section is not None:
            self._method_section.setEnabled(not self.raw_sieve_mode)
        if self._mapping_splitter is not None:
            self._mapping_splitter.setSizes([390, 680, 310])

        if hasattr(self, "range_toggle_btn"):
            self.range_toggle_btn.setText(
                "Use mapped columns instead"
                if self.cell_range_mode
                else "Use cell ranges for an irregular sheet"
            )

        if self.cell_range_mode:
            self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
            self.preview_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        else:
            self.preview_table.clearSelection()
            self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
            self.preview_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self.update_table_colors()
        self._update_range_summary()
        self._update_pathway_summary()
        self._update_sheet_selection_guidance()
        self._update_preview_guidance()
        self.validate_required_fields()
        self._update_retained_guidance()
        self._reset_guided_range_step(keep_ranges=True)
        self._refresh_result_preview()

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

        self._update_file_strip()
        return strip

    def _toggle_sample_details(self, checked: bool) -> None:
        if hasattr(self, "sample_details_group"):
            self.sample_details_group.setVisible(bool(checked))

    def _toggle_range_workflow(self) -> None:
        self.calculated_selection_mode = (
            "column" if self.calculated_selection_mode == "range" else "range"
        )
        self._apply_mode_state()

    def _guided_range_roles(self) -> List[Tuple[str, str]]:
        if self.raw_sieve_mode:
            return [
                ("size", "sieve-size values"),
                ("empty", "empty-sieve weights"),
                ("full", "sieve + sample weights"),
            ]
        return [
            ("size", "particle-size values"),
            ("percent", "cumulative percent-passing values"),
        ]

    def _range_for_role(self, role: str) -> List[Tuple[int, int]]:
        return {
            "size": self.selected_size_range,
            "percent": self.selected_percent_range,
            "empty": self.selected_empty_range,
            "full": self.selected_full_range,
        }[role]

    @staticmethod
    def _spreadsheet_column_name(column: int) -> str:
        """Return a zero-based column index as an Excel-style column name."""
        name = ""
        value = int(column) + 1
        while value > 0:
            value, remainder = divmod(value - 1, 26)
            name = chr(65 + remainder) + name
        return name

    @classmethod
    def _labeled_column_headers(
        cls, headers: List[str], column_count: Optional[int] = None
    ) -> List[str]:
        count = len(headers) if column_count is None else max(0, int(column_count))
        labels: List[str] = []
        for column in range(count):
            header = (
                str(headers[column]).strip()
                if column < len(headers) and str(headers[column]).strip()
                else f"Column {column + 1}"
            )
            labels.append(f"{cls._spreadsheet_column_name(column)} - {header}")
        return labels

    @classmethod
    def _format_cell_range(cls, positions: List[Tuple[int, int]]) -> str:
        """Format selected zero-based cells as a concise spreadsheet address."""
        if not positions:
            return "not selected"
        ordered = sorted(set(positions), key=lambda pos: (pos[0], pos[1]))
        first_row, first_col = ordered[0]
        last_row, last_col = ordered[-1]
        first = f"{cls._spreadsheet_column_name(first_col)}{first_row + 1}"
        last = f"{cls._spreadsheet_column_name(last_col)}{last_row + 1}"
        return first if first == last else f"{first}:{last}"

    @staticmethod
    def _is_contiguous_column_range(positions: List[Tuple[int, int]]) -> bool:
        if not positions:
            return False
        unique = sorted(set(positions), key=lambda pos: (pos[0], pos[1]))
        columns = {column for _, column in unique}
        rows = sorted(row for row, _ in unique)
        return len(columns) == 1 and rows == list(range(rows[0], rows[-1] + 1))

    def _update_active_range_label(self) -> None:
        if self.active_range_label is None or not hasattr(self, "preview_table"):
            return
        selected = sorted(
            {(item.row(), item.column()) for item in self.preview_table.selectedItems()},
            key=lambda pos: (pos[0], pos[1]),
        )
        if not selected:
            self.active_range_label.setText("Current selection: none")
            self.active_range_label.setStyleSheet(
                f"color: {C.TEXT_MID}; background: {C.BG}; border: 1px solid {C.BORDER}; "
                f"border-radius: {SZ.BORDER_RADIUS}px; padding: 6px 8px;"
            )
            if self.range_step < len(self._guided_range_roles()):
                self.confirm_range_btn.setEnabled(False)
            return

        address = self._format_cell_range(selected)
        contiguous = self._is_contiguous_column_range(selected)
        if contiguous:
            self.active_range_label.setText(
                f"Current selection: {address} ({len(selected)} cells)"
            )
            self.active_range_label.setStyleSheet(
                f"color: #284b6e; background: #dce9f4; border: 1px solid #8eb0cd; "
                f"border-radius: {SZ.BORDER_RADIUS}px; padding: 6px 8px;"
            )
        else:
            self.active_range_label.setText(
                f"Current selection: {address} ({len(selected)} cells) - use one column without gaps"
            )
            self.active_range_label.setStyleSheet(
                f"color: #8b4e24; background: #f4e7d9; border: 1px solid #d7ad86; "
                f"border-radius: {SZ.BORDER_RADIUS}px; padding: 6px 8px;"
            )
        self.confirm_range_btn.setEnabled(contiguous)

    def _set_range_for_role(self, role: str, positions: List[Tuple[int, int]]) -> None:
        if role == "size":
            self.selected_size_range = positions
        elif role == "percent":
            self.selected_percent_range = positions
        elif role == "empty":
            self.selected_empty_range = positions
        else:
            self.selected_full_range = positions

    def _reset_guided_range_step(self, *, keep_ranges: bool = False) -> None:
        if not hasattr(self, "range_step_label"):
            return
        if not keep_ranges:
            self.selected_size_range = []
            self.selected_percent_range = []
            self.selected_empty_range = []
            self.selected_full_range = []
            self.learned_pattern = None

        roles = self._guided_range_roles()
        self.range_step = next(
            (index for index, (role, _) in enumerate(roles) if not self._range_for_role(role)),
            len(roles),
        )
        if self.range_step >= len(roles):
            self.range_step_label.setText(
                f"Ranges ready: {len(roles)} of {len(roles)} roles assigned. "
                "Review the interpreted result before importing."
            )
            self.confirm_range_btn.setEnabled(False)
            self._prepare_batch_pattern()
        else:
            _, label = roles[self.range_step]
            self.range_step_label.setText(
                f"Step {self.range_step + 1} of {len(roles)}: select the {label} "
                "in the source preview."
            )
            self.batch_apply_btn.hide()
            if self.batch_status_label is not None:
                self.batch_status_label.hide()
        self._update_active_range_label()
        self._update_range_summary()

    def _confirm_guided_range_selection(self) -> None:
        roles = self._guided_range_roles()
        if self.range_step >= len(roles):
            return
        selected = sorted(
            {(item.row(), item.column()) for item in self.preview_table.selectedItems()},
            key=lambda pos: (pos[0], pos[1]),
        )
        if not selected:
            QMessageBox.warning(
                self, "No cells selected", "Select one contiguous range in the source preview."
            )
            return
        columns = {column for _, column in selected}
        rows = sorted({row for row, _ in selected})
        if len(columns) != 1 or rows != list(range(rows[0], rows[-1] + 1)):
            QMessageBox.warning(
                self,
                "Use one contiguous range",
                "Select cells from one column without gaps, then try again.",
            )
            return

        role, label = roles[self.range_step]
        self._set_range_for_role(role, selected)
        self.pattern_info_label.setText(
            f"Recorded {label}: {self._format_cell_range(selected)} "
            f"({len(selected)} cells)."
        )
        self.preview_table.clearSelection()
        self.update_table_colors()
        self._reset_guided_range_step(keep_ranges=True)
        self._refresh_result_preview()

    def _batch_target_count(self) -> int:
        if not self.main_window or not hasattr(self.main_window, "dataset_tabs_widget"):
            return 0
        tabs = self.main_window.dataset_tabs_widget
        try:
            return sum(
                1
                for index in range(tabs.count())
                if getattr(tabs.widget(index), "file_path", None)
                and getattr(tabs.widget(index), "file_path", None) != self.file_path
            )
        except Exception:
            return 0

    def _prepare_batch_pattern(self) -> None:
        pattern = self.learn_pattern_from_selection()
        target_count = self._batch_target_count() if pattern else 0
        self.batch_apply_btn.setEnabled(bool(pattern and target_count))
        self.batch_apply_btn.setVisible(bool(pattern and target_count))
        if self.batch_status_label is not None:
            self.batch_status_label.setVisible(bool(pattern and target_count))
            if pattern and target_count:
                self.batch_status_label.setText(
                    f"This mapping can be checked against {target_count} waiting "
                    f"dataset{'s' if target_count != 1 else ''}. Each dataset will be validated separately."
                )

    def _refresh_result_preview(self) -> None:
        if self.result_curve is None or self.result_status_label is None:
            return
        try:
            sizes, passing = self.extract_data()
            if not sizes:
                raise ValueError("No valid values")
            self.result_curve.set_curve(sizes, passing)
            self.result_status_label.setText("Ready to import")
            self.result_status_label.setStyleSheet(
                f"background: rgba(107,142,35,.08); border: 1px solid rgba(107,142,35,.30); "
                f"border-radius: {SZ.BORDER_RADIUS}px; color: {C.OLIVE_DK}; padding: 8px; "
                "font-weight: 600;"
            )
            self.result_metrics_label.setText(
                f"Valid values: {len(sizes)}\n"
                f"Particle-size range: {min(sizes):.4g}-{max(sizes):.4g} mm\n"
                f"Passing range: {min(passing):.3g}-{max(passing):.3g}%"
            )
            in_range = all(0.0 <= value <= 100.0 for value in passing)
            ordered = [
                value for _, value in sorted(zip(sizes, passing), key=lambda pair: pair[0])
            ]
            monotonic = all(
                ordered[index] <= ordered[index + 1] + 1e-9
                for index in range(len(ordered) - 1)
            )
            checks = [
                "OK  Values stay within 0-100%" if in_range else "Review  Values leave 0-100%",
                "OK  Passing increases with particle size"
                if monotonic
                else "Review  Passing direction is inconsistent",
            ]
            if self.raw_sieve_mode:
                checks.append("OK  Passing is calculated from the mapped weights")
            self.checks_title.show()
            self.result_checks_label.show()
            self.result_checks_label.setText("\n".join(checks))
            if self.import_button is not None:
                self.import_button.setEnabled(True)
        except Exception as error:
            self.result_curve.clear_curve()
            self.result_status_label.setText("Mapping incomplete")
            self.result_status_label.setStyleSheet(
                f"background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; "
                f"border-radius: {SZ.BORDER_RADIUS}px; color: {C.TEXT_MID}; padding: 8px;"
            )
            self.result_metrics_label.setText(str(error))
            self.checks_title.hide()
            self.result_checks_label.clear()
            self.result_checks_label.hide()
            if self.import_button is not None:
                self.import_button.setEnabled(False)

    def _update_file_strip(self):
        if self._file_meta_label is None:
            return
        row_count = len(self.sample_data)
        column_count = max((len(row) for row in self.sample_data), default=0)
        meta_parts = [f"{row_count} preview rows", f"{column_count} columns"]
        if self.current_sheet:
            meta_parts.append(self.current_sheet)
        self._file_meta_label.setText(" - ".join(meta_parts))

        if self._is_multi_sample_mode():
            selected_count = len(self._selected_multi_sample_candidates())
            total_count = len(self.multi_sample_candidates)
            if self._file_header_label is not None:
                self._file_header_label.setText(f"{total_count} samples found")
            if self._file_mapping_status_label is not None:
                self._file_mapping_status_label.setText(
                    f"{selected_count} / {total_count} selected"
                )
                color = C.OLIVE if selected_count else '#9a6322'
                background = (
                    'rgba(107,142,35,.08)'
                    if selected_count else 'rgba(154,99,34,.07)'
                )
                self._file_mapping_status_label.setStyleSheet(
                    f"QLabel {{ border: 1px solid {color}; border-radius: 10px; "
                    f"background: {background}; color: {color}; padding: 3px 8px; "
                    f"font-size: {F.SZ_XS}pt; }}"
                )
            return

        if self._file_header_label is not None:
            self._file_header_label.setText(f"Header row {self.header_row}")

        if self._file_mapping_status_label is None:
            return

        if self.cell_range_mode:
            ranges = [self.selected_size_range, self.selected_percent_range]
            if self.raw_sieve_mode:
                ranges = [
                    self.selected_size_range,
                    self.selected_empty_range,
                    self.selected_full_range,
                ]
            required_total = len(ranges)
            mapped_count = sum(1 for positions in ranges if positions)
        elif self.raw_sieve_mode:
            combos = [
                getattr(self, "raw_size_combo", None),
                getattr(self, "empty_sieve_combo", None),
                getattr(self, "sieve_sample_combo", None),
            ]
            required_total = 3
            mapped_count = sum(1 for combo in combos if combo is not None and combo.currentIndex() > 0)
        else:
            size_mapped = getattr(self, "size_combo", None) is not None and self.size_combo.currentIndex() > 0
            passing_mapped = (
                getattr(self, "passing_combo", None) is not None and self.passing_combo.currentIndex() > 0
            )
            required_total = 2
            mapped_count = int(size_mapped) + int(passing_mapped)

        if mapped_count >= required_total:
            self._file_mapping_status_label.setText(f"{required_total} required mapped")
            self._file_mapping_status_label.setStyleSheet(
                f"QLabel {{ border: 1px solid rgba(107,142,35,.28); border-radius: 10px; "
                f"background: rgba(107,142,35,.08); color: {C.OLIVE}; padding: 3px 8px; "
                f"font-size: {F.SZ_XS}pt; }}"
            )
        else:
            self._file_mapping_status_label.setText(f"{mapped_count} / {required_total} required")
            self._file_mapping_status_label.setStyleSheet(
                f"QLabel {{ border: 1px solid rgba(154,99,34,.28); border-radius: 10px; "
                f"background: rgba(154,99,34,.07); color: #9a6322; padding: 3px 8px; "
                f"font-size: {F.SZ_XS}pt; }}"
            )

    def _rerun_auto_detection(self):
        applied = self._apply_detected_import_candidate(
            "raw_sieve" if self.raw_sieve_mode else "processed_curve"
        )
        if not applied:
            self.auto_detect_columns()
            self._auto_detect_raw_sieve_columns()
        self._apply_mode_state()
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

    def _mapped_preview_roles(self) -> Dict[int, str]:
        role_by_column: Dict[int, str] = {}
        if not hasattr(self, "preview_table") or self.preview_table.columnCount() == 0:
            return role_by_column

        if self.cell_range_mode:
            combos = []
        elif self.raw_sieve_mode:
            combos = [
                (getattr(self, 'raw_size_combo', None), "size"),
                (getattr(self, 'empty_sieve_combo', None), "retained"),
                (getattr(self, 'sieve_sample_combo', None), "passing"),
            ]
        elif not self.cell_range_mode:
            combos = [
                (getattr(self, 'size_combo', None), "size"),
                (getattr(self, 'passing_combo', None), "passing"),
            ]
        else:
            combos = []

        for combo, role in combos:
            if combo is not None and combo.currentIndex() > 0:
                role_by_column[combo.currentIndex() - 1] = role
        return role_by_column

    def _used_preview_rows(self, role_by_column: Optional[Dict[int, str]] = None) -> set[int]:
        if not hasattr(self, "preview_table"):
            return set()

        if self.cell_range_mode:
            ranges = [self.selected_size_range, self.selected_percent_range]
            if self.raw_sieve_mode:
                ranges = [
                    self.selected_size_range,
                    self.selected_empty_range,
                    self.selected_full_range,
                ]
            return {row for positions in ranges for row, _ in positions}

        role_by_column = self._mapped_preview_roles() if role_by_column is None else role_by_column
        cols_by_role = {role: col for col, role in role_by_column.items()}
        size_col = cols_by_role.get("size")
        passing_col = cols_by_role.get("passing")
        retained_col = cols_by_role.get("retained")

        if size_col is None:
            return set()
        if self.raw_sieve_mode and (passing_col is None or retained_col is None):
            return set()
        if not self.raw_sieve_mode and passing_col is None:
            return set()

        def _numeric_at(row: int, col: Optional[int]) -> bool:
            if col is None:
                return False
            item = self.preview_table.item(row, col)
            return item is not None and self.is_numeric(item.text().strip())

        used_rows: set[int] = set()
        for row in range(self.preview_table.rowCount()):
            if row <= self.header_row:
                continue
            if not _numeric_at(row, size_col):
                continue
            if self.raw_sieve_mode:
                if _numeric_at(row, retained_col) and _numeric_at(row, passing_col):
                    used_rows.add(row)
            elif _numeric_at(row, passing_col):
                used_rows.add(row)
        return used_rows

    def _update_pathway_summary(self):
        if self.pathway_summary_label is None:
            return

        file_ext = os.path.splitext(self.file_path)[1].lower()
        excel_multi_sheet = file_ext in ['.xlsx', '.xls'] and len(self.excel_sheets) > 1
        used_rows_count = len(self._used_preview_rows())

        if self.raw_sieve_mode:
            if self.cell_range_mode:
                text = "Raw Sieve -> Cell Ranges"
                selected_cells = sum(
                    len(positions)
                    for positions in (
                        self.selected_size_range,
                        self.selected_empty_range,
                        self.selected_full_range,
                    )
                )
                count_text = f"{selected_cells} cells used"
            else:
                text = "Raw Sieve -> Columns"
                count_text = f"{used_rows_count} rows used" if used_rows_count else "3 / 3"
            footer_text = "Percent passing will be calculated from the mapped weighings."
            if excel_multi_sheet:
                text += " - multi-sheet"
        elif self.calculated_selection_mode == "range":
            text = "Processed Curve -> Cell Ranges"
            selected_cells = len(self.selected_size_range) + len(self.selected_percent_range)
            count_text = f"{selected_cells} cells used" if selected_cells else "0 cells used"
            footer_text = "Ready to import selected size and percent-passing cells."
            if file_ext in ['.xlsx', '.xls']:
                text += " - one sheet"
        else:
            text = "Processed Curve -> Columns"
            count_text = f"{used_rows_count} rows used" if used_rows_count else "2 / 2"
            footer_text = "Ready to import processed curve data from mapped columns."
            if excel_multi_sheet:
                text += " - multi-sheet"

        self.pathway_summary_label.setText(text)
        if self._footer_status_label is not None:
            self._footer_status_label.setText(footer_text)
        if self.preview_footer_status_label is not None:
            self.preview_footer_status_label.setText(count_text)

    def _update_sheet_selection_guidance(self):
        if self.sheet_info_label is None:
            return

        if self.raw_sieve_mode and self.cell_range_mode:
            text = (
                "Complete one raw-sieve range pattern, then review compatible "
                "matches before applying it to other sheets."
            )
        elif self.raw_sieve_mode:
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
        self.preview_table.horizontalHeader().setFixedHeight(32)
        self.preview_table.verticalHeader().setDefaultSectionSize(31)
        self._update_preview_header_highlights()
        self._update_file_strip()
        self._update_retained_guidance()

    def _update_retained_guidance(self) -> None:
        label = getattr(self, "retained_guidance_label", None)
        if label is None:
            return
        retained_keywords = ("retained", "retain", "tilbageholdt")
        has_retained_header = any(
            any(keyword in str(header).strip().lower() for keyword in retained_keywords)
            for header in self.headers
        )
        label.setVisible(
            has_retained_header
            and not self.raw_sieve_mode
            and self.calculated_selection_mode == "column"
        )

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
        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.setFrameShape(QFrame.Shape.NoFrame)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(True)
        table.verticalHeader().setFixedWidth(44)
        table.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table.setStyleSheet(
            f"QTableWidget {{ background: rgba(255,255,255,.20); border: none; alternate-background-color: rgba(255,255,255,.40); "
            f"selection-background-color: #9fc0dc; selection-color: #182a3a; }}"
            f"QHeaderView::section:horizontal {{ border: none; border-bottom: 1px solid {C.BORDER}; "
            f"padding: 6px 8px; color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt; font-weight: 600; }}"
            f"QHeaderView::section:vertical {{ background: {C.BG}; border: none; border-right: 1px solid {C.BORDER}; "
            f"padding: 0 8px; color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; }}"
            f"QTableWidget::item {{ padding: 4px 8px; border-bottom: 1px solid rgba(0,0,0,.04); }}"
            f"QTableWidget::item:selected {{ background: #9fc0dc; color: #182a3a; "
            f"border-top: 1px solid #486d95; border-bottom: 1px solid #486d95; }}"
        )

        table.setHorizontalHeaderLabels(
            ColumnMapperDialog._labeled_column_headers(headers, max_cols)
        )
        table.setVerticalHeaderLabels([str(i + 1) for i in range(len(sample_data))])

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
            # Processed mode: sieve size + cumulative percent passing.
            if self.size_combo.currentIndex() > 0:
                self.size_combo.setStyleSheet(f"QComboBox {{ {self.required_filled_style} padding: 5px; border-radius: 3px; }}")
            else:
                self.size_combo.setStyleSheet(f"QComboBox {{ {self.required_empty_style} padding: 5px; border-radius: 3px; }}")

            if self.passing_combo.currentIndex() > 0:
                self.passing_combo.setStyleSheet(f"QComboBox {{ {self.required_filled_style} padding: 5px; border-radius: 3px; }}")
            else:
                self.passing_combo.setStyleSheet(f"QComboBox {{ {self.required_empty_style} padding: 5px; border-radius: 3px; }}")

        self._update_preview_header_highlights()
        self._update_file_strip()

    def _update_preview_header_highlights(self):
        if not hasattr(self, 'preview_table') or self.preview_table.columnCount() == 0:
            return

        role_by_column = self._mapped_preview_roles()
        used_rows = self._used_preview_rows(role_by_column)

        role_colors = {
            "size": ("#486d95", "#c3d7ea", "#e1ebf5"),
            "passing": (C.OLIVE, "#cfe3b4", "#e6f0d7"),
            "retained": ("#9a6322", "#e1c5a3", "#f0dfca"),
        }

        for col in range(self.preview_table.columnCount()):
            item = self.preview_table.horizontalHeaderItem(col)
            if item is None:
                continue

            role = role_by_column.get(col)
            font = item.font()
            font.setBold(role is not None)
            item.setFont(font)

            if role is not None:
                accent, fill, _ = role_colors[role]
                item.setForeground(QBrush(QColor(accent)))
                item.setBackground(QBrush(QColor(fill)))
            else:
                item.setForeground(QBrush(QColor(C.TEXT_MID)))
                item.setBackground(QBrush(QColor(C.BG_LOW)))

        for row in range(self.preview_table.rowCount()):
            header_item = self.preview_table.verticalHeaderItem(row)
            if header_item is None:
                header_item = QTableWidgetItem(str(row + 1))
                self.preview_table.setVerticalHeaderItem(row, header_item)

            font = header_item.font()
            if row in used_rows:
                header_item.setBackground(QBrush(QColor("#dce9cf")))
                header_item.setForeground(QBrush(QColor(C.OLIVE_DK)))
                font.setBold(True)
            elif row == self.header_row:
                header_item.setBackground(QBrush(QColor("#eadfc9")))
                header_item.setForeground(QBrush(QColor("#8b5f21")))
                font.setBold(True)
            else:
                header_item.setBackground(QBrush(QColor(C.BG)))
                header_item.setForeground(QBrush(QColor(C.TEXT_MUTED)))
                font.setBold(False)
            header_item.setFont(font)

        if self.cell_range_mode:
            return

        for row in range(self.preview_table.rowCount()):
            for col in range(self.preview_table.columnCount()):
                cell = self.preview_table.item(row, col)
                if cell is None:
                    continue
                font = cell.font()
                font.setWeight(QFont.Weight.Normal)
                cell.setFont(font)
                base = QColor("#edf3e6") if self.is_numeric(cell.text().strip()) else QColor("#ffffff")
                role = role_by_column.get(col)
                if row == self.header_row and role is not None:
                    cell.setBackground(QColor("#eadfc9"))
                    cell.setForeground(QBrush(QColor("#5d4e37")))
                    cell.setToolTip(f"Header used to identify the {role.replace('_', ' ')} column")
                elif role is not None and row in used_rows:
                    accent, fill, _ = role_colors[role]
                    cell.setBackground(QColor(fill))
                    cell.setForeground(QBrush(QColor("#22301f")))
                    font = cell.font()
                    font.setWeight(QFont.Weight.Medium)
                    cell.setFont(font)
                    cell.setToolTip(f"Imported as {role.replace('_', ' ')} data")
                elif role is not None:
                    _, _, soft_fill = role_colors[role]
                    cell.setBackground(QColor(soft_fill))
                    cell.setForeground(QBrush(QColor(C.TEXT_MID)))
                    cell.setToolTip("Mapped column, but this row is not imported")
                else:
                    cell.setBackground(base)
                    cell.setForeground(QBrush(QColor(C.TEXT)))
                    cell.setToolTip("Numeric preview cell" if self.is_numeric(cell.text().strip()) else "")
        self.preview_table.viewport().update()
        self._update_pathway_summary()

    def auto_detect_columns(self, *, only_unmapped: bool = False):
        """Automatically detect processed columns without replacing user choices."""
        if not self.headers:
            return

        size_keywords = ['size', 'diameter', 'grain', 'particle', 'sieve', 'mesh', 'mm', 'd mm', 'd mmm']
        passing_keywords = ['passing', 'pass', 'finer', 'cumulative', 'procentages', 'percentages']
        retained_keywords = ['retained', 'retain', 'tilbageholdt']

        # Track what we've found to prioritize properly
        size_found = only_unmapped and self.size_combo.currentIndex() > 0
        passing_found = only_unmapped and self.passing_combo.currentIndex() > 0

        for i, header in enumerate(self.headers):
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in retained_keywords):
                continue

            # Check for size column (highest priority)
            if any(keyword in header_lower for keyword in size_keywords) and not size_found:
                self.size_combo.setCurrentIndex(i + 1)  # +1 because of "(Not Used)"
                size_found = True

            # Check for passing column (second priority - preferred over retained)
            elif any(keyword in header_lower for keyword in passing_keywords) and not passing_found:
                self.passing_combo.setCurrentIndex(i + 1)
                passing_found = True

    def _auto_detect_raw_sieve_columns(self, *, only_unmapped: bool = False):
        """Detect raw-sieve columns without replacing deliberate mappings."""
        if not self.headers or not hasattr(self, 'raw_size_combo'):
            return

        size_keywords     = ['sieve size', 'size', 'diameter', 'grain', 'particle', 'mesh', 'mash size',
                             'maskevidde', 'd mm', 'd mmm', 'mm sieve']
        empty_keywords    = ['empty', 'tare', 'blank', 'sigte tom', 'tom sieve', 'sieve empty']
        full_keywords     = ['sample', 'total', 'full', 'gross', 'sieve + sample', 'sieve+sample',
                             'sieve and sample', 'filled', 'sieve+fraction', 'sieve + fraction',
                             'sieve and fraction', 'sigte + fraktion', 'fraktion']

        size_found = only_unmapped and self.raw_size_combo.currentIndex() > 0
        empty_found = (
            only_unmapped and self.empty_sieve_combo.currentIndex() > 0
        )
        full_found = (
            only_unmapped and self.sieve_sample_combo.currentIndex() > 0
        )

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
            if self.cell_range_mode:
                return self.extract_data_from_raw_sieve_ranges()
            return self.extract_data_from_raw_sieve()
        elif self.cell_range_mode:
            return self.extract_data_from_ranges()
        else:
            return self.extract_data_from_columns()

    def extract_data_for_sheet(self, sheet_name: Optional[str]) -> Tuple[List[float], List[float]]:
        """Extract data for a specific sheet using the current mapping settings"""
        if self.raw_sieve_mode:
            if self.cell_range_mode:
                if sheet_name and sheet_name != self.current_sheet:
                    raise ValueError(
                        "Cell-range patterns must be reviewed before they are applied to another sheet."
                    )
                return self.extract_data_from_raw_sieve_ranges(sheet_name=sheet_name)
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

        if passing_idx < 0:
            if retained_idx >= 0:
                raise ValueError(
                    "Retained-column mappings are no longer converted automatically. "
                    "Select a cumulative percent-passing column."
                )
            raise ValueError("Please select a Cumulative Percent Passing column (required)")

        particle_sizes = []
        percent_passing = []

        # Load all data (not just preview)
        rows = self._load_rows_for_sheet(sheet_name)

        # Skip header row(s) - use detected header row + 1
        header_row_idx = getattr(self, 'header_row', 0)
        data_rows = rows[header_row_idx + 1:] if len(rows) > header_row_idx + 1 else rows

        for row in data_rows:
            if len(row) <= max(size_idx, passing_idx):
                continue

            try:
                # Extract particle size
                size_str = row[size_idx].strip()
                if not size_str or not self.is_numeric(size_str):
                    continue
                size = float(size_str)

                # Extract percentage
                passing_str = row[passing_idx].strip()
                if not passing_str or not self.is_numeric(passing_str):
                    continue
                passing = float(passing_str)

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
            if self._is_multi_sample_mode():
                selected_candidates = self._selected_multi_sample_candidates()
                if not selected_candidates:
                    raise ValueError("Select at least one sample to import.")
                base_sample_name = os.path.splitext(
                    os.path.basename(self.file_path)
                )[0]
                results: List[Dict] = []
                for candidate in selected_candidates:
                    particle_sizes, percent_passing = extract_candidate_curve(
                        self.sample_data,
                        candidate,
                    )
                    candidate_name = candidate.sample_name.strip()
                    sample_name = (
                        candidate_name
                        if candidate_name and candidate_name != candidate.source_label
                        else f"{base_sample_name} [{candidate.source_label}]"
                    )
                    candidate_state = {
                        "raw_sieve_mode": False,
                        "calculated_selection_mode": "range",
                        "header_row": candidate.header_row,
                        "sample_name": sample_name,
                        "temperature": self.temperature_spin.value(),
                        "porosity": self.porosity_spin.value(),
                        "current_sheet": self.current_sheet,
                        "checked_sheets": (
                            [self.current_sheet] if self.current_sheet else []
                        ),
                        "selected_size_range": [
                            list(position) for position in candidate.size_cells
                        ],
                        "selected_percent_range": [
                            list(position) for position in candidate.passing_cells
                        ],
                        "multi_sample_mode": True,
                        "multi_sample_candidate_key": candidate.candidate_key,
                        "import_provenance": {
                            "source": "manual_mapping",
                            "intent": "processed_curve",
                            "data_type": "processed_curve",
                            "selection_method": "range",
                            "sheet_name": self.current_sheet,
                            "label": "Confirmed multi-sample candidate",
                            "candidate_key": candidate.candidate_key,
                            "source_label": candidate.source_label,
                            "intent_matched": True,
                        },
                    }
                    results.append({
                        "particle_sizes": particle_sizes,
                        "percent_passing": percent_passing,
                        "sample_name": sample_name,
                        "temperature": self.temperature_spin.value(),
                        "porosity": self.porosity_spin.value(),
                        "sheet_name": self.current_sheet,
                        "mapping_state": candidate_state,
                    })
                return results

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
                if idx == 0 and self.cell_range_mode and all(
                    self._range_for_role(role)
                    for role, _ in self._guided_range_roles()
                ):
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
        if self._is_multi_sample_mode():
            return {
                "raw_sieve_mode": False,
                "calculated_selection_mode": "multi_sample",
                "multi_sample_mode": True,
                "selected_multi_sample_keys": [
                    candidate.candidate_key
                    for candidate in self._selected_multi_sample_candidates()
                ],
                "temperature": self.temperature_spin.value(),
                "porosity": self.porosity_spin.value(),
                "current_sheet": self.current_sheet,
                "checked_sheets": (
                    [self.current_sheet] if self.current_sheet else []
                ),
            }

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
        if self.selected_size_range:
            state['selected_size_range'] = [list(pos) for pos in self.selected_size_range]
        if self.selected_percent_range:
            state['selected_percent_range'] = [list(pos) for pos in self.selected_percent_range]
        if self.selected_empty_range:
            state['selected_empty_range'] = [list(pos) for pos in self.selected_empty_range]
        if self.selected_full_range:
            state['selected_full_range'] = [list(pos) for pos in self.selected_full_range]
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
            header_row = max(0, min(header_row, len(self.sample_data) - 1))
            self.header_row_spin.setValue(header_row + 1)

        sample_name = state.get('sample_name')
        if sample_name:
            self.sample_name_edit.setPlainText(sample_name)

        if state.get('temperature') is not None:
            self.temperature_spin.setValue(float(state['temperature']))
        if state.get('porosity') is not None:
            self.porosity_spin.setValue(float(state['porosity']))

        if state.get("multi_sample_mode") and self._is_multi_sample_mode():
            selected_keys = set(state.get("selected_multi_sample_keys") or [])
            if selected_keys and self.multi_sample_list is not None:
                self.multi_sample_list.blockSignals(True)
                for row in range(self.multi_sample_list.count()):
                    item = self.multi_sample_list.item(row)
                    index = item.data(Qt.ItemDataRole.UserRole)
                    candidate = (
                        self.multi_sample_candidates[index]
                        if isinstance(index, int)
                        and 0 <= index < len(self.multi_sample_candidates)
                        else None
                    )
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if candidate is not None
                        and candidate.candidate_key in selected_keys
                        else Qt.CheckState.Unchecked
                    )
                self.multi_sample_list.blockSignals(False)
            self._update_multi_sample_import_state()
            self._preview_multi_sample_candidate(
                self._current_multi_sample_candidate()
            )
            return

        if state.get('raw_sieve_mode'):
            self.calculated_selection_mode = state.get(
                'calculated_selection_mode', 'column'
            )
            self.switch_to_raw_sieve_mode()
        elif state.get('calculated_selection_mode') == 'range':
            self.switch_to_range_mode()
        else:
            self.switch_to_column_mode()

        combo_indices = state.get('column_indices') or {}
        combo_map = {
            'size': self.size_combo,
            'passing': self.passing_combo,
            'raw_size': self.raw_size_combo,
            'empty_sieve': self.empty_sieve_combo,
            'sieve_sample': self.sieve_sample_combo,
        }
        for key, combo in combo_map.items():
            index = combo_indices.get(key)
            if isinstance(index, int) and 0 <= index < combo.count():
                combo.setCurrentIndex(index)
        self.retained_combo.setCurrentIndex(0)

        if self.cell_range_mode:
            self.selected_size_range = [tuple(pos) for pos in state.get('selected_size_range', [])]
            self.selected_percent_range = [tuple(pos) for pos in state.get('selected_percent_range', [])]
            self.selected_empty_range = [tuple(pos) for pos in state.get('selected_empty_range', [])]
            self.selected_full_range = [tuple(pos) for pos in state.get('selected_full_range', [])]
            self.update_table_colors()
            self._reset_guided_range_step(keep_ranges=True)

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
            column_options = ["(Not Used)"] + self._labeled_column_headers(self.headers)
            for combo in [
                self.size_combo,
                self.passing_combo,
                self.retained_combo,
                self.raw_size_combo,
                self.empty_sieve_combo,
                self.sieve_sample_combo,
            ]:
                combo.clear()
                combo.addItems(column_options)

            # Re-run auto detection
            self.auto_detect_columns()
            self._auto_detect_raw_sieve_columns()

            # Update header row spinner if it exists
            if hasattr(self, 'header_row_spin'):
                self.header_row_spin.setRange(1, max(1, len(self.sample_data)))
                self.header_row_spin.setValue(self.header_row + 1)

            # Reset any learned pattern or selections since data changed
            self.selected_size_range = []
            self.selected_percent_range = []
            self.selected_empty_range = []
            self.selected_full_range = []
            self.learned_pattern = None
            if hasattr(self, 'batch_apply_btn'):
                self.batch_apply_btn.setEnabled(False)
            if hasattr(self, 'pattern_info_label'):
                self.pattern_info_label.setText("Select headers and data together, then apply the learned pattern to similar sheets.")
            self._apply_detected_import_candidate(
                "raw_sieve" if self.raw_sieve_mode else "processed_curve"
            )
            self._apply_mode_state()
            self._apply_multi_sample_mode()

        except Exception as e:
            QMessageBox.warning(self, "Sheet Load Error", f"Could not load sheet '{sheet_name}':\n{str(e)}")

    def update_headers(self, new_header_row: int):
        """Update headers when header row changes"""
        if new_header_row == self.header_row:
            return

        self.header_row = new_header_row
        try:
            self._refresh_column_options_for_header_row(
                new_header_row, preserve_indices=True
            )

            # Fill only empty roles; deliberate column positions remain stable.
            self.auto_detect_columns(only_unmapped=True)
            self._auto_detect_raw_sieve_columns(only_unmapped=True)
            self.validate_required_fields()
            self._update_file_strip()

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
        applied = self._apply_detected_import_candidate("raw_sieve")
        if not applied and not all(
            combo.currentIndex() > 0
            for combo in (self.raw_size_combo, self.empty_sieve_combo, self.sieve_sample_combo)
        ):
            self._auto_detect_raw_sieve_columns()
        self._apply_mode_state()

    def switch_to_calculated_mode(self):
        """Switch back to the standard calculated-data input mode."""
        self.raw_sieve_mode = False
        if not self.selected_size_range and not self.selected_percent_range:
            self._apply_detected_import_candidate("processed_curve")
        self._apply_mode_state()

    def _update_range_summary(self) -> None:
        if hasattr(self, "size_range_count_label"):
            size_name = "Sieve size" if self.raw_sieve_mode else "Particle size"
            size_address = self._format_cell_range(self.selected_size_range)
            self.size_range_count_label.setText(
                f"{size_name}: {size_address}"
                + (
                    f" ({len(self.selected_size_range)} cells)"
                    if self.selected_size_range
                    else ""
                )
            )
        if hasattr(self, "percent_range_count_label"):
            if self.raw_sieve_mode:
                empty_address = self._format_cell_range(self.selected_empty_range)
                full_address = self._format_cell_range(self.selected_full_range)
                self.percent_range_count_label.setText(
                    f"Empty sieve: {empty_address}\nSieve + sample: {full_address}"
                )
            else:
                passing_address = self._format_cell_range(self.selected_percent_range)
                self.percent_range_count_label.setText(
                    f"Passing: {passing_address}"
                    + (
                        f" ({len(self.selected_percent_range)} cells)"
                        if self.selected_percent_range
                        else ""
                    )
                )
        if self.cell_range_mode and self.preview_footer_status_label is not None:
            ranges = [self.selected_size_range, self.selected_percent_range]
            if self.raw_sieve_mode:
                ranges = [
                    self.selected_size_range,
                    self.selected_empty_range,
                    self.selected_full_range,
                ]
            self.preview_footer_status_label.setText(
                f"{sum(len(positions) for positions in ranges)} cells"
            )
        if self.cell_range_mode and self.pathway_summary_label is not None:
            self._update_pathway_summary()

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
        if len({size_idx, empty_idx, full_idx}) != 3:
            raise ValueError(
                "Raw sieve mapping requires three different columns: "
                "sieve size, empty sieve, and sieve + sample."
            )

        rows = self._load_rows_for_sheet(sheet_name)
        header_row_idx = getattr(self, 'header_row', 0)
        data_rows = rows[header_row_idx + 1:] if len(rows) > header_row_idx + 1 else rows

        sieve_sizes: List[float]   = []
        empty_weights: List[float] = []
        full_weights: List[float]  = []
        pan_retained_weight = 0.0
        pan_labels = {"pan", "bund", "bottom"}

        max_idx = max(size_idx, empty_idx, full_idx)
        for row in data_rows:
            if len(row) <= max_idx:
                continue
            try:
                size_str  = row[size_idx].strip()
                empty_str = row[empty_idx].strip()
                full_str  = row[full_idx].strip()

                if not empty_str or not self.is_numeric(empty_str):
                    continue
                if not full_str or not self.is_numeric(full_str):
                    continue

                empty = float(empty_str)
                full  = float(full_str)

                if not size_str or not self.is_numeric(size_str):
                    if size_str.strip().lower() in pan_labels and full >= empty:
                        pan_retained_weight += full - empty
                    continue

                size  = float(size_str)

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
        if len(sieve_sizes) < 3:
            raise ValueError(
                f"Raw sieve mapping produced only {len(sieve_sizes)} valid sieve rows. "
                "Check that the mapped columns point to the actual header row and raw weighing table."
            )

        # Delegate all arithmetic to the utility function in data_loader
        from data_loader import calculate_sieve_percent_passing
        return calculate_sieve_percent_passing(
            sieve_sizes,
            empty_weights,
            full_weights,
            pan_retained_weight=pan_retained_weight,
        )

    def extract_data_from_raw_sieve_ranges(
        self, sheet_name: Optional[str] = None
    ) -> Tuple[List[float], List[float]]:
        """Calculate passing from three explicitly selected raw-sieve ranges."""
        ranges = [
            self.selected_size_range,
            self.selected_empty_range,
            self.selected_full_range,
        ]
        if not all(ranges):
            raise ValueError(
                "Select the sieve-size, empty-sieve, and sieve + sample ranges."
            )
        lengths = {len(positions) for positions in ranges}
        if len(lengths) != 1:
            raise ValueError("All three raw-sieve ranges must contain the same number of cells.")

        rows = self._load_rows_for_sheet(sheet_name)
        sorted_ranges = [
            sorted(positions, key=lambda pos: (pos[0], pos[1]))
            for positions in ranges
        ]
        sieve_sizes: List[float] = []
        empty_weights: List[float] = []
        full_weights: List[float] = []
        pan_retained_weight = 0.0
        pan_labels = {"pan", "bund", "bottom"}

        for size_pos, empty_pos, full_pos in zip(*sorted_ranges):
            try:
                size_text = str(rows[size_pos[0]][size_pos[1]]).strip()
                empty_text = str(rows[empty_pos[0]][empty_pos[1]]).strip()
                full_text = str(rows[full_pos[0]][full_pos[1]]).strip()
            except (IndexError, TypeError):
                continue
            if not self.is_numeric(empty_text) or not self.is_numeric(full_text):
                continue
            empty = float(empty_text)
            full = float(full_text)
            if size_text.lower() in pan_labels:
                if full >= empty:
                    pan_retained_weight += full - empty
                continue
            if not self.is_numeric(size_text):
                continue
            size = float(size_text)
            if size <= 0:
                continue
            sieve_sizes.append(size)
            empty_weights.append(empty)
            full_weights.append(full)

        if len(sieve_sizes) < 3:
            raise ValueError(
                "Raw sieve range mapping must contain at least three valid sieve rows."
            )
        from data_loader import calculate_sieve_percent_passing
        return calculate_sieve_percent_passing(
            sieve_sizes,
            empty_weights,
            full_weights,
            pan_retained_weight=pan_retained_weight,
        )

    def clear_range_selection(self):
        """Clear all range selections"""
        self.selected_size_range = []
        self.selected_percent_range = []
        self.selected_empty_range = []
        self.selected_full_range = []
        # Clear visual selection in table
        self.preview_table.clearSelection()
        self.update_table_colors()
        self._reset_guided_range_step(keep_ranges=True)
        self._refresh_result_preview()

    def on_table_selection_changed(self):
        """Handle table selection changes for range selection mode"""
        if not self.cell_range_mode:
            return
        self._update_active_range_label()

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

        # Highlight assigned roles while the guided range workflow is active.
        if self.cell_range_mode:
            for row, col in self.selected_size_range:
                item = self.preview_table.item(row, col)
                if item:
                    item.setBackground(QColor("#c3d7ea"))
                    item.setToolTip("Imported as particle size data")

            for row, col in self.selected_percent_range:
                item = self.preview_table.item(row, col)
                if item:
                    item.setBackground(QColor("#cfe3b4"))
                    item.setToolTip("Imported as percent passing data")
            for row, col in self.selected_empty_range:
                item = self.preview_table.item(row, col)
                if item:
                    item.setBackground(QColor("#e1c5a3"))
                    item.setToolTip("Imported as empty-sieve weight")
            for row, col in self.selected_full_range:
                item = self.preview_table.item(row, col)
                if item:
                    item.setBackground(QColor("#cfe3b4"))
                    item.setToolTip("Imported as sieve + sample weight")
        self._update_range_summary()
        self._update_pathway_summary()

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
                item.setBackground(QColor("#eadfc9"))

        for row, col in self.selected_size_range:
                item = self.preview_table.item(row, col)
                if item:
                    item.setBackground(QColor("#c3d7ea"))

        for row, col in self.selected_percent_range:
            item = self.preview_table.item(row, col)
            if item:
                item.setBackground(QColor("#cfe3b4"))
        self._update_range_summary()
        self._update_pathway_summary()

    def learn_pattern_from_selection(self):
        """Learn a pattern from the current cell range selection for batch processing"""
        if self.raw_sieve_mode:
            raw_ranges = [
                self.selected_size_range,
                self.selected_empty_range,
                self.selected_full_range,
            ]
            if not all(raw_ranges) or len({len(values) for values in raw_ranges}) != 1:
                return None
            columns = [values[0][1] for values in raw_ranges]
            data_start_row = min(row for row, _ in self.selected_size_range)

            def _header_above(column: int) -> Tuple[Optional[str], Optional[int]]:
                for row in range(data_start_row - 1, max(-1, data_start_row - 16), -1):
                    if row < len(self.sample_data) and column < len(self.sample_data[row]):
                        value = str(self.sample_data[row][column]).strip().strip(chr(34)).strip("'")
                        if value and not self.is_numeric(value):
                            return value, row
                return None, None

            header_values = [_header_above(column) for column in columns]
            if any(value is None or row is None for value, row in header_values):
                return None
            header_row = header_values[0][1]
            self.learned_pattern = {
                "data_type": "raw_sieve",
                "size_header": header_values[0][0],
                "empty_header": header_values[1][0],
                "full_header": header_values[2][0],
                "data_offset": data_start_row - header_row,
                "row_count": len(self.selected_size_range),
            }
            return self.learned_pattern

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
            'data_type': 'processed_curve',
            'size_header': size_header,
            'percent_header': percent_header,
            'size_column': size_col,
            'percent_column': percent_col,
            'data_offset': size_offset,
            'header_row': header_row,
            'row_count': len(self.selected_size_range),
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

            if pattern.get("data_type") == "raw_sieve":
                return self._apply_raw_pattern_to_rows(
                    data,
                    pattern,
                    actual_file_path=actual_file_path,
                    sheet_name=sheet_name,
                )

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

    def _apply_raw_pattern_to_rows(
        self,
        data: List[List[str]],
        pattern: Dict,
        *,
        actual_file_path: str,
        sheet_name: Optional[str],
    ) -> Dict:
        """Apply and validate a learned three-range raw-sieve pattern."""
        expected = {
            "size": str(pattern["size_header"]).strip().strip(chr(34)).strip("'"),
            "empty": str(pattern["empty_header"]).strip().strip(chr(34)).strip("'"),
            "full": str(pattern["full_header"]).strip().strip(chr(34)).strip("'"),
        }
        positions: Dict[str, Tuple[int, int]] = {}
        for row_index, row in enumerate(data):
            for column_index, cell in enumerate(row):
                value = str(cell).strip().strip(chr(34)).strip("'")
                for role, header in expected.items():
                    if value == header:
                        positions[role] = (row_index, column_index)
        missing = [role for role in expected if role not in positions]
        if missing:
            raise ValueError(
                "Could not match raw-sieve pattern headers: " + ", ".join(missing)
            )

        start_row = positions["size"][0] + int(pattern.get("data_offset", 1))
        row_count = max(1, int(pattern.get("row_count", 20)))
        size_col = positions["size"][1]
        empty_col = positions["empty"][1]
        full_col = positions["full"][1]
        max_col = max(size_col, empty_col, full_col)
        sieve_sizes: List[float] = []
        empty_weights: List[float] = []
        full_weights: List[float] = []
        pan_retained_weight = 0.0

        for row in data[start_row:start_row + row_count]:
            if len(row) <= max_col:
                continue
            size_text = str(row[size_col]).strip()
            empty_text = str(row[empty_col]).strip()
            full_text = str(row[full_col]).strip()
            if not self.is_numeric(empty_text) or not self.is_numeric(full_text):
                continue
            empty = float(empty_text)
            full = float(full_text)
            if size_text.lower() in {"pan", "bund", "bottom"}:
                if full >= empty:
                    pan_retained_weight += full - empty
                continue
            if not self.is_numeric(size_text):
                continue
            size = float(size_text)
            if size <= 0:
                continue
            sieve_sizes.append(size)
            empty_weights.append(empty)
            full_weights.append(full)

        if len(sieve_sizes) < 3:
            raise ValueError("Raw-sieve pattern produced fewer than three valid sieve rows.")
        from data_loader import calculate_sieve_percent_passing
        particle_sizes, percent_passing = calculate_sieve_percent_passing(
            sieve_sizes,
            empty_weights,
            full_weights,
            pan_retained_weight=pan_retained_weight,
        )
        return {
            "particle_sizes": particle_sizes,
            "percent_passing": percent_passing,
            "sample_name": os.path.splitext(os.path.basename(actual_file_path))[0],
            "temperature": 10.0,
            "porosity": 0.4,
            "sheet_name": sheet_name,
        }

    def has_learned_pattern(self) -> bool:
        """Check if a pattern has been learned"""
        return self.learned_pattern is not None

    def apply_pattern_to_batch(self):
        """Apply the learned pattern to the current workbook and matching Excel error tabs."""
        required_ranges = [self.selected_size_range, self.selected_percent_range]
        if getattr(self, "raw_sieve_mode", False):
            required_ranges = [
                self.selected_size_range,
                self.selected_empty_range,
                self.selected_full_range,
            ]
        if not all(required_ranges):
            QMessageBox.warning(
                self,
                "No Selection",
                "Complete the guided ranges before reviewing batch matches.",
            )
            return

        pattern = self.learn_pattern_from_selection()
        if not pattern:
            QMessageBox.warning(
                self,
                "Cannot reuse this mapping",
                "The selected ranges do not define an arrangement that can be checked against other datasets.",
            )
            return

        if not self.main_window or not hasattr(self.main_window, "dataset_tabs_widget"):
            QMessageBox.warning(self, "Error", "Main application window not available for batch processing.")
            return

        main_window = self.main_window
        control_panel = getattr(main_window, "control_panel", None)
        current_file_key = self.file_path
        if self.forced_sheet_name:
            current_file_key = f"{self.file_path}:::{self.forced_sheet_name}"

        from gui.error_tab import ErrorTab

        error_tabs = []
        for i in range(main_window.dataset_tabs_widget.count()):
            widget = main_window.dataset_tabs_widget.widget(i)
            actual_file_path = getattr(widget, "actual_file_path", getattr(widget, "file_path", ""))
            if isinstance(widget, ErrorTab) and widget.file_path != current_file_key:
                if actual_file_path.endswith(".xls") or actual_file_path.endswith(".xlsx"):
                    error_tabs.append(widget)

        if not error_tabs and (control_panel is None or not hasattr(control_panel, "_apply_mapping_results")):
            QMessageBox.information(self, "No Batch Targets", "No Excel targets were available for batch processing.")
            return

        targets = [(current_file_key, getattr(self, "forced_sheet_name", None), None)]
        targets.extend((tab.file_path, getattr(tab, "sheet_name", None), tab) for tab in error_tabs)

        ready_targets = []
        review_targets = []
        for target_file_key, target_sheet_name, error_tab in targets:
            try:
                result = self.apply_pattern_to_file(target_file_key)
                sizes = list(result.get("particle_sizes") or [])
                passing = list(result.get("percent_passing") or [])
                if len(sizes) < 2 or len(sizes) != len(passing):
                    raise ValueError("No matching particle-size and passing series was found.")
                if any(value < 0.0 or value > 100.0 for value in passing):
                    raise ValueError("Cumulative passing values fall outside 0-100%.")
                ordered = [
                    value for _, value in sorted(zip(sizes, passing), key=lambda pair: pair[0])
                ]
                if any(
                    ordered[index] > ordered[index + 1] + 1e-9
                    for index in range(len(ordered) - 1)
                ):
                    raise ValueError("The interpreted curve has the wrong passing direction.")
                ready_targets.append(
                    (target_file_key, target_sheet_name, error_tab, result)
                )
            except Exception as error:
                review_targets.append((target_file_key, str(error)))

        def _target_label(file_key: str) -> str:
            actual_path, _, sheet = file_key.partition(":::")
            label = os.path.basename(actual_path)
            return f"{label} [{sheet}]" if sheet else label

        review_lines = ["Ready to import"]
        if ready_targets:
            review_lines.extend(
                f"  READY  {_target_label(file_key)}"
                for file_key, _, _, _ in ready_targets
            )
        else:
            review_lines.append("  None")
        review_lines.append("")
        review_lines.append("Needs review")
        if review_targets:
            review_lines.extend(
                f"  REVIEW  {_target_label(file_key)} - {error}"
                for file_key, error in review_targets
            )
        else:
            review_lines.append("  None")

        if not ready_targets:
            QMessageBox.warning(
                self,
                "No datasets ready",
                "\n".join(review_lines),
            )
            return

        ready_count = len(ready_targets)
        reply = QMessageBox.question(
            self,
            "Review mapped datasets",
            "\n".join(review_lines)
            + f"\n\nImport {ready_count} ready "
            + ("sample?" if ready_count == 1 else "samples?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        successful_imports = []
        import_failures = list(review_targets)
        mapping_state = self.get_mapping_state() if hasattr(self, "get_mapping_state") else None
        current_committed = False

        for target_file_key, target_sheet_name, error_tab, result in ready_targets:
            try:
                if control_panel is not None and hasattr(control_panel, "_apply_mapping_results"):
                    control_panel._apply_mapping_results(
                        target_file_key,
                        [result],
                        forced_sheet_name=target_sheet_name,
                        mapping_state=mapping_state,
                    )
                else:
                    if error_tab is None:
                        raise ValueError("Batch processing requires the main control panel for the current workbook.")
                    dataset = GrainSizeData(
                        particle_sizes=result["particle_sizes"],
                        percent_passing=result["percent_passing"],
                        sample_name=result["sample_name"],
                        temperature=result["temperature"],
                        porosity=result["porosity"],
                        file_path=target_file_key,
                    )
                    error_tab.dataset_fixed.emit(dataset, target_file_key)

                successful_imports.append(target_file_key)
                if target_file_key == current_file_key:
                    current_committed = True

            except Exception as error:
                import_failures.append((target_file_key, str(error)))

        result_lines = [
            f"Imported: {len(successful_imports)}",
            f"Needs review: {len(import_failures)}",
        ]
        if import_failures:
            result_lines.append("")
            result_lines.extend(
                f"  REVIEW  {_target_label(file_key)} - {error}"
                for file_key, error in import_failures
            )
        QMessageBox.information(
            self,
            "Import results",
            "\n".join(result_lines),
        )
        if current_committed:
            self._batch_apply_committed = True
            self.accept()
