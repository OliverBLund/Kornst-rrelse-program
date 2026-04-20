"""Styled error tab for datasets that failed to load."""

from __future__ import annotations

import os

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from data_loader import GrainSizeData
from gui.column_mapper import ColumnMapperDialog
from gui.theme import C, F, icon


class ErrorTab(QWidget):
    """Tab widget for failed datasets and neutral mapping-required states."""

    dataset_fixed = pyqtSignal(object, str)

    def __init__(self, file_path: str, error_message: str, parent=None, *, issue_variant: str = "error"):
        super().__init__(parent)
        self.file_path = file_path
        self.error_message = error_message
        self.issue_variant = issue_variant
        self._details_expanded = False
        self._entry_animated = False
        self._entry_effect = None
        self._entry_animation = None
        self._details_animation = None

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
        """Build the error workspace to match the approved concept."""
        self.setObjectName("error-tab")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        is_mapping = self.issue_variant == "mapping_required"
        accent_top = C.OLIVE if is_mapping else "#bf543e"
        accent_bottom = C.OLIVE_DK if is_mapping else "#8f3525"
        accent_rgba = "107,142,35" if is_mapping else "192,56,40"
        accent_text = C.OLIVE if is_mapping else "#8f3525"
        self._mark_icon = "fa6s.table-columns" if is_mapping else "fa6s.triangle-exclamation"
        self._mark_color = C.OLIVE if is_mapping else C.LED_ERR
        self.setStyleSheet(
            f"""
            QWidget#error-tab {{
                background:
                    qradialgradient(cx:1.05, cy:-0.15, radius:0.6,
                                    fx:1.05, fy:-0.15,
                                    stop:0 rgba({accent_rgba},18),
                                    stop:1 rgba({accent_rgba},0)),
                    {C.BG};
            }}
            QFrame#ev-strip {{
                background: {C.BG_LOW};
                border-bottom: 1px solid {C.BORDER};
            }}
            QLabel#ev-strip-name {{
                color: {C.TEXT};
                font-family: "{F.MONO}";
                font-size: {F.SZ_SM}pt;
                font-weight: 500;
            }}
            QLabel#ev-strip-meta {{
                color: {C.TEXT_MUTED};
                font-family: "{F.MONO}";
                font-size: {F.SZ_SM}pt;
            }}
            QFrame#ev-hero {{
                background:
                    qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 rgba(255,255,255,115),
                                    stop:0.52 rgba(255,255,255,0),
                                    stop:1 rgba(255,255,255,0)),
                    qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(238,232,220,242),
                                    stop:1 rgba(245,245,240,250));
                border: 1px solid {C.BORDER};
                border-radius: 8px;
            }}
            QFrame#ev-hero-accent {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                            stop:0 {accent_top},
                                            stop:1 {accent_bottom});
                border: none;
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
            }}
            QFrame#ev-hero-mark {{
                background: rgba({accent_rgba},0.10);
                border: 1px solid rgba({accent_rgba},0.22);
                border-radius: 6px;
            }}
            QLabel#ev-eyebrow {{
                color: {C.TEXT_MUTED};
                font-size: {F.SZ_SM}pt;
                font-weight: 600;
                letter-spacing: 0.12em;
                text-transform: uppercase;
            }}
            QLabel#ev-title {{
                color: {C.TEXT};
                font-size: {F.SZ_3XL}pt;
                font-weight: 700;
            }}
            QLabel#ev-subtitle {{
                color: {C.TEXT_MID};
                font-size: {F.SZ_LG}pt;
            }}
            QLabel#ev-fault {{
                color: {accent_text};
                font-family: "{F.MONO}";
                font-size: {F.SZ_SM}pt;
                background: rgba({accent_rgba},0.08);
                border: 1px solid rgba({accent_rgba},0.22);
                border-radius: 999px;
                padding: 5px 9px;
            }}
            QFrame#ev-pane {{
                background: {C.BG_RAISED};
                border: 1px solid {C.BORDER};
                border-radius: 7px;
            }}
            QFrame#ev-pane-header {{
                background: rgba(255,255,255,0.18);
                border-bottom: 1px solid {C.BORDER};
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
            }}
            QLabel#ev-pane-k {{
                color: {C.TEXT_MUTED};
                font-size: {F.SZ_XS}pt;
                font-weight: 600;
                letter-spacing: 0.1em;
                text-transform: uppercase;
            }}
            QLabel#ev-pane-title {{
                color: {C.TEXT};
                font-size: {F.SZ_XL}pt;
                font-weight: 600;
            }}
            QLabel#ev-pane-subtitle {{
                color: {C.TEXT_MUTED};
                font-size: {F.SZ_MD}pt;
            }}
            QLabel#ev-note {{
                color: {C.TEXT_MID};
                font-size: {F.SZ_MD}pt;
            }}
            QFrame#ev-summary-row {{
                background: rgba(255,255,255,0.32);
                border: 1px solid rgba(212,196,168,0.9);
                border-radius: 5px;
            }}
            QLabel#ev-summary-label {{
                color: {C.TEXT_MUTED};
                font-size: {F.SZ_XS}pt;
                font-weight: 600;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }}
            QLabel#ev-summary-value {{
                color: {C.TEXT};
                font-size: {F.SZ_LG}pt;
            }}
            QPushButton#ev-action {{
                background: {C.BG};
                border: 1px solid {C.BORDER_DK};
                border-radius: 4px;
                color: {C.TEXT_MID};
                font-size: {F.SZ_LG}pt;
                padding: 0 14px;
                min-height: 31px;
            }}
            QPushButton#ev-action:hover {{
                background: {C.BG_RAISED};
                color: {C.TEXT};
            }}
            QPushButton#ev-action[primary="true"] {{
                background: {C.OLIVE};
                border-color: {C.OLIVE_DK};
                color: white;
                font-weight: 600;
            }}
            QPushButton#ev-action[primary="true"]:hover {{
                background: {C.OLIVE_H};
            }}
            QPushButton#ev-action[danger="true"] {{
                color: #9d3a2a;
                border-color: rgba(160,48,32,0.28);
            }}
            QPushButton#ev-action[danger="true"]:hover {{
                background: rgba(160,48,32,0.06);
            }}
            QToolButton#ev-toggle {{
                border: none;
                background: transparent;
                color: {C.TEXT_MUTED};
                font-size: {F.SZ_SM}pt;
                font-weight: 600;
                padding: 0;
            }}
            QToolButton#ev-toggle:hover {{
                color: {C.TEXT};
            }}
            QTextEdit#ev-raw {{
                background: white;
                border: 1px solid {C.BORDER};
                border-radius: 5px;
                color: {C.TEXT_MID};
                padding: 10px 11px;
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_strip())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 20, 20, 20)
        body_layout.setSpacing(18)

        main_col = QVBoxLayout()
        main_col.setSpacing(16)
        main_col.addWidget(self._build_hero())

        split_row = QHBoxLayout()
        split_row.setSpacing(16)
        split_row.addWidget(self._build_preview_pane(), 1)

        side_col = QVBoxLayout()
        side_col.setSpacing(16)
        side_col.addWidget(self._build_status_pane())
        side_col.addWidget(self._build_detail_pane())
        side_col.addStretch()

        split_row.addLayout(side_col, 0)
        main_col.addLayout(split_row, 1)

        body_layout.addLayout(main_col, 1)
        root.addWidget(body, 1)

    def _build_strip(self) -> QWidget:
        strip = QFrame()
        strip.setObjectName("ev-strip")
        strip.setFixedHeight(38)

        layout = QHBoxLayout(strip)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(10)

        icon_label = QLabel()
        strip_icon = "fa6s.table-columns" if self.issue_variant == "mapping_required" else "fa6s.file-circle-exclamation"
        icon_label.setPixmap(icon(strip_icon, C.EARTH, 13).pixmap(16, 16))
        icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(icon_label)

        name_label = QLabel(self.file_name)
        name_label.setObjectName("ev-strip-name")
        name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(name_label, 1)

        for chunk in self._source_meta_chunks():
            meta = QLabel(chunk)
            meta.setObjectName("ev-strip-meta")
            layout.addWidget(meta)

        return strip

    def _build_hero(self) -> QWidget:
        hero = QFrame()
        hero.setObjectName("ev-hero")

        outer = QHBoxLayout(hero)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        accent = QFrame()
        accent.setObjectName("ev-hero-accent")
        accent.setFixedWidth(4)
        outer.addWidget(accent)

        inner = QWidget()
        outer.addWidget(inner, 1)

        layout = QHBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        mark = QFrame()
        mark.setObjectName("ev-hero-mark")
        mark.setFixedSize(48, 48)
        mark_layout = QVBoxLayout(mark)
        mark_layout.setContentsMargins(0, 0, 0, 0)
        mark_layout.setSpacing(0)
        mark_icon = QLabel()
        mark_icon.setPixmap(icon(self._mark_icon, self._mark_color, 18).pixmap(20, 20))
        mark_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark_icon.setStyleSheet("background: transparent;")
        mark_layout.addStretch()
        mark_layout.addWidget(mark_icon)
        mark_layout.addStretch()
        layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)

        copy = QWidget()
        copy_layout = QVBoxLayout(copy)
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(0)

        eyebrow = QLabel("Mapping Required" if self.issue_variant == "mapping_required" else "Dataset Issue")
        eyebrow.setObjectName("ev-eyebrow")
        copy_layout.addWidget(eyebrow)

        self.title_label = QLabel(
            "Raw sieve columns need mapping"
            if self.issue_variant == "mapping_required"
            else "Column mapping needs confirmation"
        )
        self.title_label.setObjectName("ev-title")
        self.title_label.setWordWrap(True)
        self.title_label.setContentsMargins(0, 4, 0, 0)
        copy_layout.addWidget(self.title_label)

        subtitle = QLabel(
            "The file has been added as raw sieve weighings. Map the size and weighing columns before analysis."
            if self.issue_variant == "mapping_required"
            else "The workbook is in the workspace, but this sheet needs a manual column check before it can be analysed."
        )
        subtitle.setObjectName("ev-subtitle")
        subtitle.setWordWrap(True)
        subtitle.setContentsMargins(0, 8, 0, 0)
        copy_layout.addWidget(subtitle)

        self.error_label = QLabel(self._fault_line_text())
        self.error_label.setObjectName("ev-fault")
        self.error_label.setWordWrap(False)
        self.error_label.setContentsMargins(0, 12, 0, 0)
        copy_layout.addWidget(self.error_label, 0, Qt.AlignmentFlag.AlignLeft)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 16, 0, 0)
        actions.setSpacing(8)

        self.fix_button = self._action_button(
            "Open Mapper",
            "fa6s.wand-magic-sparkles",
            "#ffffff",
            primary=True,
        )
        self.fix_button.clicked.connect(self.fix_dataset)
        actions.addWidget(self.fix_button)

        self.remove_button = self._action_button(
            "Remove",
            "fa6s.trash",
            "#9d3a2a",
            danger=True,
        )
        self.remove_button.clicked.connect(self.remove_dataset)
        actions.addWidget(self.remove_button)
        actions.addStretch()

        copy_layout.addLayout(actions)
        layout.addWidget(copy, 1)
        return hero

    def _build_preview_pane(self) -> QWidget:
        pane = self._pane_shell(
            kind="Preview",
            title="Source rows",
            subtitle=(
                "Use this preview to identify sieve size, empty sieve, and sieve + sample columns."
                if self.issue_variant == "mapping_required"
                else "Enough context to spot the grain-size and percent columns quickly."
            ),
        )
        body = pane.layout().itemAt(1).widget()
        body_layout = body.layout()

        note = QLabel(
            "Numeric cells are softly marked so likely measurement columns stand out without overwhelming the preview."
        )
        note.setObjectName("ev-note")
        note.setWordWrap(True)
        body_layout.addWidget(note)

        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(False)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.preview_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.preview_table.setShowGrid(False)
        self.preview_table.setFrameShape(QFrame.Shape.NoFrame)
        self.preview_table.setWordWrap(False)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.verticalHeader().setDefaultSectionSize(26)
        header = self.preview_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self.preview_table.setMinimumHeight(340)
        self.preview_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body_layout.addWidget(self.preview_table, 1)

        return pane

    def _build_status_pane(self) -> QWidget:
        pane = self._pane_shell(
            kind="Status",
            title="Next step",
            subtitle=(
                "No import error occurred. This raw pathway always needs column mapping first."
                if self.issue_variant == "mapping_required"
                else "Keep the decision surface small and obvious."
            ),
        )
        body = pane.layout().itemAt(1).widget()
        layout = body.layout()

        layout.addWidget(self._summary_row("fa6s.file-excel", "Source", self._source_kind_label()))
        layout.addWidget(self._summary_row("fa6s.table-cells-large", "Sheet", self.sheet_name or "Single sheet"))
        layout.addWidget(self._summary_row("fa6s.arrow-right", "Next step", "Open the mapper"))

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 12, 0, 0)
        buttons.setSpacing(7)

        preview_btn = self._mini_button("Keep Preview", "fa6s.eye")
        preview_btn.setEnabled(False)
        buttons.addWidget(preview_btn)

        retry_btn = self._mini_button("Retry Later", "fa6s.clock-rotate-left")
        retry_btn.setEnabled(False)
        buttons.addWidget(retry_btn)
        buttons.addStretch()

        layout.addLayout(buttons)
        return pane

    def _build_detail_pane(self) -> QWidget:
        pane = self._pane_shell(
            kind="Detail",
            title="Import note" if self.issue_variant == "mapping_required" else "Raw loader message",
            subtitle=(
                "Visible if you need to confirm why mapping is required."
                if self.issue_variant == "mapping_required"
                else "Visible on demand, not forced into the first read."
            ),
        )
        body = pane.layout().itemAt(1).widget()
        layout = body.layout()

        hint = QLabel(
            "Raw sieve weighings need explicit size and weight columns before the program can calculate percent passing."
            if self.issue_variant == "mapping_required"
            else "The loader could not match the incoming columns to a valid grain-size / percent-passing pair."
        )
        hint.setObjectName("ev-note")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.details_toggle = QToolButton()
        self.details_toggle.setObjectName("ev-toggle")
        self.details_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.details_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.details_toggle.setText(
            "Show import note" if self.issue_variant == "mapping_required" else "Show raw message"
        )
        self.details_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.details_toggle.clicked.connect(self.toggle_details)
        layout.addWidget(self.details_toggle, 0, Qt.AlignmentFlag.AlignLeft)

        self.details_container = QWidget()
        self.details_container.setMaximumHeight(0)
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 10, 0, 0)
        details_layout.setSpacing(0)

        self.details_text = QTextEdit()
        self.details_text.setObjectName("ev-raw")
        self.details_text.setReadOnly(True)
        details_font = QFont(F.MONO)
        details_font.setPointSize(F.SZ_MD)
        self.details_text.setFont(details_font)
        self.details_text.setPlainText(self.error_message)
        self.details_text.setMinimumHeight(120)
        details_layout.addWidget(self.details_text)
        layout.addWidget(self.details_container)
        return pane

    def _pane_shell(self, *, kind: str, title: str, subtitle: str) -> QFrame:
        pane = QFrame()
        pane.setObjectName("ev-pane")
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("ev-pane-header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 11, 14, 10)
        header_layout.setSpacing(0)

        kind_label = QLabel(kind)
        kind_label.setObjectName("ev-pane-k")
        header_layout.addWidget(kind_label)

        title_label = QLabel(title)
        title_label.setObjectName("ev-pane-title")
        title_label.setContentsMargins(0, 2, 0, 0)
        header_layout.addWidget(title_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("ev-pane-subtitle")
        subtitle_label.setWordWrap(True)
        subtitle_label.setContentsMargins(0, 2, 0, 0)
        header_layout.addWidget(subtitle_label)
        layout.addWidget(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(14, 12, 14, 14)
        body_layout.setSpacing(0)
        layout.addWidget(body, 1)
        return pane

    def _summary_row(self, icon_name: str, label: str, value: str) -> QWidget:
        row = QFrame()
        row.setObjectName("ev-summary-row")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(9, 8, 9, 8)
        layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setPixmap(icon(icon_name, C.TEXT_MUTED, 11).pixmap(14, 14))
        icon_label.setStyleSheet("background: transparent;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        copy = QWidget()
        copy_layout = QVBoxLayout(copy)
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(0)

        label_widget = QLabel(label)
        label_widget.setObjectName("ev-summary-label")
        copy_layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setObjectName("ev-summary-value")
        value_widget.setContentsMargins(0, 2, 0, 0)
        copy_layout.addWidget(value_widget)

        layout.addWidget(copy, 1)
        return row

    def _action_button(self, text: str, icon_name: str, color: str, *, primary: bool = False, danger: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("ev-action")
        button.setProperty("primary", primary)
        button.setProperty("danger", danger)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(icon(icon_name, color, 11))
        button.style().unpolish(button)
        button.style().polish(button)
        return button

    def _mini_button(self, text: str, icon_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(icon(icon_name, C.TEXT_MID, 10))
        button.setMinimumHeight(27)
        button.setStyleSheet(
            f"""
            QPushButton {{
                background: rgba(255,255,255,0.4);
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                color: {C.TEXT_MID};
                font-size: {F.SZ_MD}pt;
                padding: 0 11px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.7);
                color: {C.TEXT};
            }}
            QPushButton:disabled {{
                color: {C.TEXT_MUTED};
            }}
            """
        )
        return button

    def _source_meta_chunks(self) -> list[str]:
        chunks = []
        ext = os.path.splitext(self.actual_file_path)[1].lower().lstrip(".")
        if ext:
            chunks.append(ext.upper())
        if self.sheet_name:
            chunks.append(self.sheet_name)
        chunks.append("Mapping required" if self.issue_variant == "mapping_required" else "Load failed")
        return chunks

    def _source_kind_label(self) -> str:
        ext = os.path.splitext(self.actual_file_path)[1].lower()
        if ext in (".xlsx", ".xls"):
            return "Excel workbook"
        if ext == ".csv":
            return "CSV file"
        if ext == ".txt":
            return "Text file"
        return "Source file"

    def _fault_line_text(self) -> str:
        if self.issue_variant == "mapping_required":
            return "waiting for raw sieve column mapping"
        lowered = self.error_message.lower()
        if "percent" in lowered:
            return "percent-passing column was not recognized"
        if "column" in lowered or "header" in lowered:
            return "column layout needs manual confirmation"
        return "loader could not recognize the incoming structure"

    def showEvent(self, event):
        super().showEvent(event)
        if not self._entry_animated:
            self._entry_animated = True

    def _play_entry_animation(self) -> None:
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(0.0)
        self.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _handle_finished(*_args) -> None:
            self._clear_entry_effect(effect)

        animation.finished.connect(_handle_finished)
        animation.start()

        self._entry_effect = effect
        self._entry_animation = animation

    def _clear_entry_effect(self, effect: QGraphicsOpacityEffect) -> None:
        if self.graphicsEffect() is effect:
            self.setGraphicsEffect(None)

    def toggle_details(self):
        self._details_expanded = not self._details_expanded
        self.details_toggle.setArrowType(
            Qt.ArrowType.DownArrow if self._details_expanded else Qt.ArrowType.RightArrow
        )
        if self.issue_variant == "mapping_required":
            self.details_toggle.setText("Hide import note" if self._details_expanded else "Show import note")
        else:
            self.details_toggle.setText("Hide raw message" if self._details_expanded else "Show raw message")

        target_height = self.details_text.sizeHint().height() + 10 if self._details_expanded else 0
        animation = QPropertyAnimation(self.details_container, b"maximumHeight", self)
        animation.setDuration(160)
        animation.setStartValue(self.details_container.maximumHeight())
        animation.setEndValue(target_height)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        animation.start()
        self._details_animation = animation

    def update_error_message(self, new_error_message: str):
        """Update the visible error state without rebuilding the widget."""
        self.error_message = new_error_message
        self.error_label.setText(self._fault_line_text())
        self.details_text.setPlainText(self.error_message)

    def load_file_preview(self):
        """Load the first few rows of the file for preview."""
        try:
            rows, _, _ = ColumnMapperDialog.load_preview_rows(
                self.actual_file_path,
                sheet_name=self.sheet_name,
            )
            headers = ColumnMapperDialog.detect_headers(self, rows)
            ColumnMapperDialog.populate_preview_table(self.preview_table, rows[:50], headers)

        except Exception as exc:
            self.preview_table.setRowCount(1)
            self.preview_table.setColumnCount(1)
            self.preview_table.setHorizontalHeaderLabels(["Preview Error"])
            self.preview_table.setItem(0, 0, QTableWidgetItem(f"Preview error: {str(exc)}"))

    def fix_dataset(self):
        """Open column mapping dialog to fix the dataset."""
        try:
            main_window = self.parent()
            while main_window and not hasattr(main_window, "dataset_tabs_widget"):
                main_window = main_window.parent()
            control_panel = getattr(main_window, "control_panel", None) if main_window else None
            mapping_state = None
            if control_panel is not None and hasattr(control_panel, "file_mapping_states"):
                mapping_state = control_panel.file_mapping_states.get(self.file_path)

            dialog = ColumnMapperDialog(
                self.actual_file_path,
                self,
                main_window,
                sheet_name=self.sheet_name,
                initial_state=mapping_state,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                mapping_results = dialog.get_mapping_results()
                if not mapping_results:
                    QMessageBox.warning(self, "No Data", "No sheet data was extracted.")
                    return

                if control_panel is not None and hasattr(control_panel, "_apply_mapping_results"):
                    control_panel._apply_mapping_results(
                        self.file_path,
                        mapping_results,
                        forced_sheet_name=self.sheet_name,
                        mapping_state=dialog.get_mapping_state(),
                    )
                    return

                datasets = []
                for mapping in mapping_results:
                    sample_name = mapping["sample_name"]
                    if self.sheet_name and f"[{self.sheet_name}]" not in sample_name:
                        sample_name = f"{sample_name} [{self.sheet_name}]"

                    dataset = GrainSizeData(
                        sample_name=sample_name,
                        temperature=mapping["temperature"],
                        porosity=mapping["porosity"],
                        particle_sizes=mapping["particle_sizes"],
                        percent_passing=mapping["percent_passing"],
                        file_path=self.file_path,
                    )
                    datasets.append(dataset)

                payload = datasets[0] if len(datasets) == 1 else datasets
                self.dataset_fixed.emit(payload, self.file_path)

        except Exception as exc:
            QMessageBox.critical(self, "Fix Error", f"Could not fix dataset:\n{str(exc)}")

    def remove_dataset(self):
        """Remove this dataset from the interface."""
        reply = QMessageBox.question(
            self,
            "Remove Dataset",
            f"Remove {self.file_name} from the analysis?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            host_window = self.window()
            if host_window and hasattr(host_window, "remove_workspace_file"):
                if host_window.remove_workspace_file(self.file_path):
                    return
            parent_tab_widget = self.parent()
            if parent_tab_widget and hasattr(parent_tab_widget, "removeTab"):
                index = parent_tab_widget.indexOf(self)
                if index >= 0:
                    parent_tab_widget.removeTab(index)
