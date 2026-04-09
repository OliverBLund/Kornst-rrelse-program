"""
Sheet selection dialog for multi-sheet Excel workbooks.
Shows before the column mapper so the user can choose which sheets to import.
"""

from __future__ import annotations

from typing import List

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget,
)

from gui.dialog_chrome import make_dialog_header, make_dialog_footer
from gui.theme import C, F, SZ, icon as _icon
from qt_chrome.frameless_dialog_base import FramelessDialogBase


class SheetSelectorDialog(FramelessDialogBase):
    """Dialog for selecting sheets from a multi-sheet Excel workbook."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent, default_mode="auto")
        self.file_path = file_path
        self.selected_sheets: List[str] = []

        self.setWindowTitle("Select Sheets to Import")
        self.setModal(True)
        self.resize(500, 420)

        self._build_ui()
        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )
        self._load_sheets()

    # ── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        import os
        fname = os.path.basename(self.file_path)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header_widget = make_dialog_header(
            "Sheet Selector",
            f"{fname} · choose sheets to import",
            fa_icon="fa6s.file-excel",
            close_fn=self.reject,
        )
        root.addWidget(self._header_widget)

        # Body
        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(14, 12, 14, 10)
        body_lay.setSpacing(10)

        # File info row
        file_row = QWidget()
        file_row.setStyleSheet(
            f"background: {C.BG_LOW}; border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px;"
        )
        fr_lay = QHBoxLayout(file_row)
        fr_lay.setContentsMargins(10, 7, 10, 7)
        fr_lay.setSpacing(8)
        file_ic = QLabel()
        try:
            file_ic.setPixmap(_icon("fa6s.file-excel", "#1d7a4a").pixmap(14, 14))
        except Exception:
            file_ic.setText("📄")
        file_ic.setStyleSheet("background: transparent;")
        fr_lay.addWidget(file_ic)
        fname_lbl = QLabel(fname)
        fname_lbl.setStyleSheet(
            f"font-weight: 600; color: {C.TEXT}; background: transparent; font-size: {F.SZ_MD}pt;"
        )
        fr_lay.addWidget(fname_lbl)
        fr_lay.addStretch()

        import os
        try:
            sz = os.path.getsize(self.file_path)
            sz_str = f"{sz // 1024} KB" if sz >= 1024 else f"{sz} B"
        except Exception:
            sz_str = ""
        if sz_str:
            sz_lbl = QLabel(sz_str)
            sz_lbl.setStyleSheet(
                f"color: {C.TEXT_MUTED}; background: transparent; font-size: {F.SZ_SM}pt;"
            )
            fr_lay.addWidget(sz_lbl)
        body_lay.addWidget(file_row)

        # Section header
        sec_hdr = QLabel("AVAILABLE SHEETS")
        sec_hdr.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; font-weight: 600; "
            "letter-spacing: 0.08em; background: transparent;"
        )
        body_lay.addWidget(sec_hdr)

        # Sheet list
        self._sheet_list = QListWidget()
        self.sheet_list = self._sheet_list
        self._sheet_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._sheet_list.setStyleSheet(
            f"QListWidget {{ background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; font-size: {F.SZ_MD}pt; }}"
            f"QListWidget::item {{ padding: 6px 8px; border-bottom: 1px solid {C.BORDER}; }}"
            f"QListWidget::item:last {{ border-bottom: none; }}"
            f"QListWidget::item:hover {{ background: rgba(107,142,35,.04); }}"
            f"QListWidget::item:selected {{ background: rgba(107,142,35,.08); "
            f"color: {C.TEXT}; }}"
        )
        body_lay.addWidget(self._sheet_list, 1)

        # Quick-select buttons row
        qs_row = QHBoxLayout()
        qs_row.setSpacing(6)
        for label, fn in [("Select All", lambda: self._set_all(True)),
                          ("Clear All",  lambda: self._set_all(False))]:
            btn = _make_inline_btn(label, fn)
            qs_row.addWidget(btn)
        qs_row.addStretch()
        body_lay.addLayout(qs_row)

        # Info label
        self._info_label = QLabel("")
        self.info_label = self._info_label
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; background: transparent;"
        )
        body_lay.addWidget(self._info_label)

        root.addWidget(body, 1)

        # Footer — OK button stored so we can control its enabled state
        self._ok_btn_ref = None
        footer = make_dialog_footer([
            ("Cancel",         self.reject, "secondary"),
            ("Import Sheets",  self.accept, "primary"),
        ])
        # Grab the primary button to allow disabling it
        for child in footer.findChildren(type(footer.layout().itemAt(0))):
            pass
        root.addWidget(footer)

    # ── Sheet loading ───────────────────────────────────────────────────────

    def _load_sheets(self):
        try:
            excel_file = pd.ExcelFile(self.file_path)
            sheet_names = excel_file.sheet_names
        except Exception as e:
            self._info_label.setText(f"Error reading workbook: {e}")
            self._info_label.setStyleSheet(
                f"color: {C.LED_ERR}; font-size: {F.SZ_SM}pt; background: transparent;"
            )
            return

        for name in sheet_names:
            item = QListWidgetItem(name)
            item.setCheckState(Qt.CheckState.Checked)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            self._sheet_list.addItem(item)

        n = len(sheet_names)
        if n == 1:
            self._info_label.setText("This workbook has only one sheet.")
        else:
            self._info_label.setText(
                f"{n} sheets found. Use 'Apply Pattern to Batch' after import "
                "to map all sheets at once."
            )

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _set_all(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self._sheet_list.count()):
            self._sheet_list.item(i).setCheckState(state)

    def get_selected_sheets(self) -> List[str]:
        return [
            self._sheet_list.item(i).text()
            for i in range(self._sheet_list.count())
            if self._sheet_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    # ── Accept / reject ─────────────────────────────────────────────────────

    def accept(self):
        self.selected_sheets = self.get_selected_sheets()
        if not self.selected_sheets:
            self._info_label.setText("Please select at least one sheet to import.")
            self._info_label.setStyleSheet(
                f"color: {C.LED_ERR}; font-size: {F.SZ_SM}pt; background: transparent;"
            )
            return
        super().accept()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────────────────────────────────────

def _make_inline_btn(label: str, fn):
    from PyQt6.QtWidgets import QPushButton
    btn = QPushButton(label)
    btn.setFixedHeight(24)
    btn.setStyleSheet(
        f"QPushButton {{ border: 1px solid {C.BORDER}; "
        f"border-radius: {SZ.BORDER_RADIUS}px; background: transparent; "
        f"color: {C.TEXT_MID}; padding: 0 10px; font-size: {F.SZ_SM}pt; }}"
        f"QPushButton:hover {{ background: {C.BG_RAISED}; border-color: {C.BORDER_DK}; "
        f"color: {C.TEXT}; }}"
    )
    btn.clicked.connect(fn)
    return btn
