from __future__ import annotations

import csv
import io
import os

from PyQt6.QtCore import QSize, QTimer, Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QAbstractItemView, QButtonGroup, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from delimited_text import DELIMITED_TEXT_EXTENSIONS, read_delimited_rows
from gui.column_mapper import ColumnMapperDialog
from gui.dialog_chrome import make_dialog_footer, make_dialog_header, style_dialog_button
from gui.theme import C, F, SZ, icon as _icon
from qt_chrome.frameless_dialog_base import FramelessDialogBase


def _split_file_key(file_key: str) -> tuple[str, str | None]:
    return file_key.split(":::", 1) if ":::" in file_key else (file_key, None)


def _ro(item: QTableWidgetItem) -> QTableWidgetItem:
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _item(text: str, align: Qt.AlignmentFlag, font: QFont | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(int(align))
    if font:
        item.setFont(font)
    return item


def _fmt_mm(v: float | None) -> str:
    if v is None:
        return "N/A"
    if v >= 10:
        return f"{v:.1f} mm"
    if v >= 1:
        return f"{v:.2f} mm"
    if v >= 0.1:
        return f"{v:.3f} mm"
    return f"{v:.4f} mm"


def _fmt_edit(v: float) -> str:
    return f"{float(v):.6g}"


def _fmt_mass(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.1f}" if abs(v) >= 10 else f"{v:.2f}"


def _extract_mass_values(dataset):
    for attr in ("mass_values", "mass_grams", "fraction_masses", "retained_masses",
                 "retained_mass_grams", "retained_weights", "weights_g"):
        values = getattr(dataset, attr, None)
        if isinstance(values, (list, tuple)) and len(values) == len(getattr(dataset, "particle_sizes", [])):
            try:
                return [float(v) if v is not None else None for v in values]
            except (TypeError, ValueError):
                pass
    return None


def _extract_total_mass(dataset):
    for attr in ("sample_mass", "total_mass", "mass_total", "total_weight"):
        value = getattr(dataset, attr, None)
        try:
            if value is not None and float(value) > 0:
                return float(value)
        except (TypeError, ValueError):
            pass
    return None


def _derive_mass_values(sizes: list[float], passing: list[float], total_mass: float) -> list[float]:
    indexed = sorted(enumerate(zip(sizes, passing)), key=lambda item: item[1][0])
    masses = [0.0] * len(indexed)
    prev = 0.0
    for i, (orig, (_, pct)) in enumerate(indexed):
        current = max(prev, min(100.0, float(pct)))
        frac = max(0.0, 100.0 - prev) if i == len(indexed) - 1 else max(0.0, current - prev)
        masses[orig] = frac / 100.0 * total_mass
        prev = current
    return masses


class _Bar(QWidget):
    def __init__(self, value: float, parent=None):
        super().__init__(parent)
        self.value = max(0.0, min(100.0, float(value)))
        self.setMinimumHeight(18)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(232, 225, 210))
        p.drawRoundedRect(rect, 5, 5)
        width = rect.width() * (self.value / 100.0)
        if width > 0:
            fill = QRectF(rect.left(), rect.top(), width, rect.height())
            p.setBrush(QColor(C.OLIVE))
            p.drawRoundedRect(fill, min(5.0, fill.width() / 2.0), min(5.0, fill.height() / 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 25)))
        p.drawRoundedRect(rect, 5, 5)
        p.end()


class _DistCell(QWidget):
    def __init__(self, mass: float | None, pct: float, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(8)
        label = QLabel(f"{_fmt_mass(mass)} g | {pct:.1f}%")
        label.setFont(QFont(F.MONO, F.SZ_XS))
        label.setFixedWidth(128)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
        bar = _Bar(pct, self)
        lay.addWidget(label)
        lay.addWidget(bar, 1)


class DataInspectorDialog(FramelessDialogBase):
    _MODE_PASSING = "passing"
    _MODE_MASS = "mass"
    _MODE_BOTH = "both"

    def __init__(self, dataset, scheme=None, file_path: str | None = None, *, dataset_tab=None, mapping_state: dict | None = None, parent=None):
        super().__init__(parent, default_mode="auto")
        self.dataset = dataset
        self.scheme = scheme
        self.file_path = file_path or getattr(dataset, "file_path", None)
        self.dataset_tab = dataset_tab
        self.mapping_state = dict(mapping_state or getattr(dataset, "_source_mapping_state", None) or {})
        self._actual_file_path, self._sheet_name = _split_file_key(self.file_path or "")
        self._mode = self._MODE_PASSING
        self._dirty = False
        self._updating = False
        self._source_rows, self._source_error = [], None
        self._rows = []
        self._mass_values = []
        self._mass_source = "derived"
        self._mass_basis_total = 100.0
        self._load_source_rows()
        self.setWindowTitle(f"Data Inspector - {dataset.sample_name}")
        self.setModal(True)
        self.resize(980, 720)
        self.setMinimumSize(820, 560)
        self._build_ui()
        self.install_chrome_behavior(header_widget=self._header_widget, corner_radius=8, resize_margin=6)
        self._refresh_from_dataset()
        self._populate_source_table()
        self._set_mode(self._MODE_PASSING)

    def _build_ui(self):
        self.setStyleSheet(
            f"QTableWidget {{ background: {C.BG}; border: none; gridline-color: {C.BORDER}; selection-background-color: rgba(107,142,35,.08); selection-color: {C.TEXT}; }}"
            f"QHeaderView::section {{ background: {C.BG_RAISED}; border: none; border-bottom: 1px solid {C.BORDER}; padding: 8px 10px; color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt; font-weight: 600; }}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._header_widget = make_dialog_header("Data Inspector", f"{self.dataset.sample_name} · source + extracted rows", fa_icon="fa6s.table", close_fn=self.accept)
        root.addWidget(self._header_widget)

        toolbar = QWidget()
        toolbar.setObjectName("inspectorToolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 8, 14, 8)
        tb.setSpacing(10)
        toolbar.setStyleSheet(
            f"QWidget#inspectorToolbar {{ background: {C.BG_LOW}; "
            f"border-bottom: 1px solid {C.BORDER}; }}"
        )

        metric_strip = QWidget()
        metric_strip.setObjectName("inspectorMetricStrip")
        metrics_layout = QHBoxLayout(metric_strip)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(0)
        metric_strip.setStyleSheet(
            "QWidget#inspectorMetricStrip, QWidget#inspectorMetricCell {"
            " background: transparent; border: none; }"
            f"QLabel#inspectorMetricLabel {{ color: {C.TEXT_MUTED};"
            f" font-size: {F.SZ_XS}pt; background: transparent; border: none; }}"
            f"QLabel#inspectorMetricValue {{ color: {C.TEXT};"
            f" font-size: {F.SZ_SM}pt; background: transparent; border: none; }}"
            f"QFrame#inspectorMetricDivider {{ background: {C.BORDER_DK};"
            " border: none; }"
        )
        self._metric = {}
        metrics = (("d10", "D10"), ("d50", "D50"), ("d60", "D60"), ("cu", "Cu"))
        for index, (key, label) in enumerate(metrics):
            cell = QWidget()
            cell.setObjectName("inspectorMetricCell")
            cell.setMinimumWidth(76 if key == "cu" else 96)
            lay = QVBoxLayout(cell)
            lay.setContentsMargins(10 if index else 0, 1, 10, 1)
            lay.setSpacing(1)
            caption = QLabel(label)
            caption.setObjectName("inspectorMetricLabel")
            caption.setFont(QFont(F.UI, F.SZ_XS, QFont.Weight.DemiBold))
            value = QLabel("—")
            value.setObjectName("inspectorMetricValue")
            value.setFont(QFont(F.MONO, F.SZ_SM))
            self._metric[key] = value
            lay.addWidget(caption)
            lay.addWidget(value)
            metrics_layout.addWidget(cell)
            if index < len(metrics) - 1:
                divider = QFrame()
                divider.setObjectName("inspectorMetricDivider")
                divider.setFrameShape(QFrame.Shape.NoFrame)
                divider.setFixedWidth(1)
                divider.setMinimumHeight(30)
                metrics_layout.addWidget(divider)
        tb.addWidget(metric_strip)
        tb.addStretch(1)
        view_label = QLabel("View")
        view_label.setFont(QFont(F.UI, F.SZ_SM, QFont.Weight.DemiBold))
        view_label.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent; border: none;")
        tb.addWidget(view_label)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_btns = {}
        mode_wrap = QFrame()
        mode_wrap.setObjectName("inspectorViewSwitch")
        mode_wrap.setStyleSheet(
            f"QFrame#inspectorViewSwitch {{ background: {C.BG}; "
            f"border: 1px solid {C.BORDER_DK}; border-radius: {SZ.BORDER_RADIUS}px; }}"
            "QFrame#inspectorViewSwitch QPushButton[inspectorView=\"true\"] {"
            f" background: transparent; border: none; border-right: 1px solid {C.BORDER};"
            f" border-radius: 0; color: {C.TEXT_MID}; padding: 0 11px;"
            f" min-height: 27px; font-size: {F.SZ_SM}pt; }}"
            "QFrame#inspectorViewSwitch QPushButton[segmentEdge=\"first\"] {"
            f" border-top-left-radius: {SZ.BORDER_RADIUS - 1}px;"
            f" border-bottom-left-radius: {SZ.BORDER_RADIUS - 1}px; }}"
            "QFrame#inspectorViewSwitch QPushButton[segmentEdge=\"last\"] {"
            f" border-right: none; border-top-right-radius: {SZ.BORDER_RADIUS - 1}px;"
            f" border-bottom-right-radius: {SZ.BORDER_RADIUS - 1}px; }}"
            "QFrame#inspectorViewSwitch QPushButton[inspectorView=\"true\"]:hover:!checked {"
            f" background: {C.BG_LOW}; color: {C.TEXT}; }}"
            "QFrame#inspectorViewSwitch QPushButton[inspectorView=\"true\"]:checked {"
            f" background: {C.OLIVE}; color: white; font-weight: 700; }}"
            "QFrame#inspectorViewSwitch QPushButton[inspectorView=\"true\"]:checked:hover {"
            f" background: {C.OLIVE_H}; }}"
        )
        ml = QHBoxLayout(mode_wrap)
        ml.setContentsMargins(1, 1, 1, 1)
        ml.setSpacing(0)
        modes = (("% Passing", self._MODE_PASSING), ("Mass (g)", self._MODE_MASS), ("Both", self._MODE_BOTH))
        for index, (text, mode) in enumerate(modes):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setProperty("inspectorView", True)
            if index == 0:
                btn.setProperty("segmentEdge", "first")
            elif index == len(modes) - 1:
                btn.setProperty("segmentEdge", "last")
            btn.clicked.connect(lambda _=False, m=mode: self._set_mode(m))
            self._mode_group.addButton(btn)
            self._mode_btns[mode] = btn
            ml.addWidget(btn)
        tb.addWidget(mode_wrap)
        root.addWidget(toolbar)

        self._tabs = QTabWidget()
        page1 = QWidget(); v1 = QVBoxLayout(page1); v1.setContentsMargins(0, 0, 0, 0); v1.setSpacing(0)
        top = QFrame(); tl = QHBoxLayout(top); tl.setContentsMargins(14, 10, 14, 10); tl.setSpacing(10); top.setStyleSheet(f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER};")
        top.setObjectName("inspectorEditBar")
        top.setStyleSheet(
            f"QFrame#inspectorEditBar {{ background: {C.BG_RAISED}; "
            f"border-bottom: 1px solid {C.BORDER}; }}"
        )
        info = QWidget(); il = QVBoxLayout(info); il.setContentsMargins(0, 0, 0, 0); il.setSpacing(2)
        self._extract_summary = QLabel(""); self._extract_summary.setFont(QFont(F.MONO, F.SZ_SM))
        self._extract_hint = QLabel(""); self._extract_hint.setWordWrap(True); self._extract_hint.setStyleSheet(f"color: {C.TEXT_MUTED};")
        il.addWidget(self._extract_summary); il.addWidget(self._extract_hint); tl.addWidget(info, 1)
        self._add_btn = QPushButton("Add Row"); self._remove_btn = QPushButton("Remove Row"); self._reset_btn = QPushButton("Reset"); self._apply_btn = QPushButton("Apply")
        edit_actions = (
            (self._add_btn, "secondary", "fa6s.plus"),
            (self._remove_btn, "secondary", "fa6s.minus"),
            (self._reset_btn, "secondary", "fa6s.rotate-left"),
            (self._apply_btn, "primary", "fa6s.check"),
        )
        for btn, style, icon_name in edit_actions:
            style_dialog_button(btn, style)
            btn.setIconSize(QSize(12, 12))
            try:
                btn.setIcon(_icon(icon_name, "white" if style == "primary" else C.TEXT_MID))
            except Exception:
                pass
            tl.addWidget(btn)
        self._add_btn.clicked.connect(self._add_row); self._remove_btn.clicked.connect(self._remove_rows); self._reset_btn.clicked.connect(self._reset_table); self._apply_btn.clicked.connect(self._apply_rows)
        v1.addWidget(top)
        self._table = QTableWidget(0, 5); self._table.setHorizontalHeaderLabels(["#", "Sieve (mm)", "% Passing", "Mass (g)", "Distribution"])
        self._table.verticalHeader().setVisible(False); self._table.setAlternatingRowColors(True); self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self._table.setFrameShape(QFrame.Shape.NoFrame)
        hh = self._table.horizontalHeader(); hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents); hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents); hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents); hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.itemChanged.connect(self._on_item_changed); self._table.itemSelectionChanged.connect(self._update_action_state); v1.addWidget(self._table, 1)
        self._tabs.addTab(page1, "Extracted")

        page2 = QWidget(); v2 = QVBoxLayout(page2); v2.setContentsMargins(0, 0, 0, 0); v2.setSpacing(0)
        src_top = QFrame(); sl = QVBoxLayout(src_top); sl.setContentsMargins(14, 10, 14, 10); sl.setSpacing(3); src_top.setStyleSheet(f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER};")
        self._source_meta = QLabel(""); self._source_meta.setFont(QFont(F.MONO, F.SZ_SM)); self._source_map = QLabel(""); self._source_map.setWordWrap(True); self._source_map.setStyleSheet(f"color: {C.TEXT_MUTED};")
        sl.addWidget(self._source_meta); sl.addWidget(self._source_map); v2.addWidget(src_top)
        self._source_table = QTableWidget(0, 0); self._source_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self._source_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems); self._source_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self._source_table.setFrameShape(QFrame.Shape.NoFrame); self._source_table.verticalHeader().setVisible(False)
        v2.addWidget(self._source_table, 1); self._tabs.addTab(page2, "Source")
        root.addWidget(self._tabs, 1)

        self._status_icon = QLabel()
        self._status_icon.setFixedSize(14, 14)
        self._status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status = QLabel()
        self._status.setFont(QFont(F.UI, F.SZ_SM))
        self._status.setStyleSheet(f"color: {C.TEXT_MID}; background: transparent; border: none;")
        status_wrap = QWidget()
        status_wrap.setObjectName("inspectorStatus")
        status_wrap.setMinimumHeight(28)
        status_wrap.setStyleSheet("QWidget#inspectorStatus { background: transparent; border: none; }")
        sw = QHBoxLayout(status_wrap)
        sw.setContentsMargins(2, 2, 12, 2)
        sw.setSpacing(7)
        sw.addWidget(self._status_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        sw.addWidget(self._status, 0, Qt.AlignmentFlag.AlignVCenter)
        buttons = []
        if self._can_open_mapper(): buttons.append(("Open Mapper", self._open_mapper, "secondary"))
        buttons.extend([("Copy CSV", self._copy_csv, "secondary"), ("Close", self.accept, "primary")])
        root.addWidget(make_dialog_footer(buttons, left_widget=status_wrap))

    def _refresh_from_dataset(self):
        sizes = list(getattr(self.dataset, "particle_sizes", [])); passing = list(getattr(self.dataset, "percent_passing", []))
        mass = _extract_mass_values(self.dataset)
        if mass is None:
            self._mass_source = "derived"; self._mass_basis_total = _extract_total_mass(self.dataset) or 100.0; mass = _derive_mass_values(sizes, passing, self._mass_basis_total)
        else:
            self._mass_source = "actual"; self._mass_basis_total = sum(v for v in mass if v is not None)
        self._rows = []
        for i, (size, pct, grams) in enumerate(sorted(zip(sizes, passing, mass), key=lambda item: item[0], reverse=True), start=1):
            share = 0.0 if grams is None or self._mass_basis_total <= 0 else max(0.0, float(grams) / self._mass_basis_total * 100.0)
            self._rows.append({"index": i, "size": float(size), "passing": float(pct), "mass": float(grams) if grams is not None else None, "share": share})
        self._mass_values = [row["mass"] for row in self._rows]
        self._metric["d10"].setText(_fmt_mm(self.dataset.get_d10())); self._metric["d50"].setText(_fmt_mm(self.dataset.get_d50())); self._metric["d60"].setText(_fmt_mm(self.dataset.get_d60())); self._metric["cu"].setText(f"{self.dataset.get_uniformity_coefficient():.2f}" if self.dataset.get_uniformity_coefficient() is not None else "N/A")
        self._populate_extract_table()
        d50 = self.dataset.get_d50(); cu = self.dataset.get_uniformity_coefficient()
        parts = [f"{len(self._rows)} rows", self.dataset.get_validation_summary()]
        if d50 is not None: parts.insert(1, f"D50 {_fmt_mm(d50).replace(' mm', '')} mm")
        if cu is not None: parts.insert(2 if d50 is not None else 1, f"Cu {cu:.2f}")
        self._extract_summary.setText("  ·  ".join(parts))
        self._extract_hint.setText("Edit extracted rows here, or open the mapper to change how the source file is interpreted." if self.dataset_tab else "Read-only: no live dataset tab is attached to this inspector.")
        self._refresh_source_summary()
        self._refresh_status()

    def _populate_extract_table(self):
        self._updating = True
        try:
            self._table.clearContents(); self._table.setRowCount(len(self._rows) + 1)
            for r, row in enumerate(self._rows):
                self._table.setItem(r, 0, _ro(_item(str(row["index"]), Qt.AlignmentFlag.AlignCenter)))
                self._table.setItem(r, 1, _item(_fmt_edit(row["size"]), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                self._table.setItem(r, 2, _item(f'{row["passing"]:.4f}'.rstrip("0").rstrip("."), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                self._table.setItem(r, 3, _ro(_item(_fmt_mass(row["mass"]), Qt.AlignmentFlag.AlignCenter)))
                self._table.setCellWidget(r, 4, _DistCell(row["mass"], row["share"], self._table))
            total = len(self._rows); font = QFont(F.MONO, F.SZ_SM); font.setWeight(QFont.Weight.DemiBold)
            self._table.setItem(total, 0, _ro(_item("Σ", Qt.AlignmentFlag.AlignCenter, font))); self._table.setItem(total, 1, _ro(_item("Total", Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, font))); self._table.setItem(total, 2, _ro(_item("100.0", Qt.AlignmentFlag.AlignCenter, font))); self._table.setItem(total, 3, _ro(_item(_fmt_mass(sum(v for v in self._mass_values if v is not None)) if self._mass_values else "—", Qt.AlignmentFlag.AlignCenter, font))); self._table.setItem(total, 4, _ro(_item("", Qt.AlignmentFlag.AlignCenter, font)))
        finally:
            self._updating = False
        self._dirty = False; self._update_action_state()

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._updating or item.row() >= self._table.rowCount() - 1 or item.column() not in (1, 2): return
        for r in range(max(0, self._table.rowCount() - 1)):
            self._table.item(r, 0).setText(str(r + 1))
        self._dirty = True; self._update_action_state(); self._set_status("Unsaved edits in extracted dataset rows.", C.AMBER, "fa6s.pen")

    def _update_action_state(self):
        can_edit = self.dataset_tab is not None
        selected = []
        if self._table.selectionModel(): selected = [i.row() for i in self._table.selectionModel().selectedRows()]
        has_data_row = any(r < self._table.rowCount() - 1 for r in selected)
        self._add_btn.setEnabled(can_edit)
        self._remove_btn.setEnabled(can_edit and has_data_row)
        self._reset_btn.setEnabled(can_edit and self._dirty)
        self._apply_btn.setEnabled(can_edit and self._dirty)
        if not can_edit:
            unavailable = "Editing is unavailable because this sample is not attached to a live dataset tab."
            for btn in (self._add_btn, self._remove_btn, self._reset_btn, self._apply_btn):
                btn.setToolTip(unavailable)
            return
        self._add_btn.setToolTip("Add a blank data row above the total.")
        self._remove_btn.setToolTip("Remove the selected data row." if has_data_row else "Select a data row to remove it.")
        self._reset_btn.setToolTip("Discard the current unsaved edits." if self._dirty else "There are no unsaved edits to reset.")
        self._apply_btn.setToolTip("Apply the edited rows to this sample." if self._dirty else "Make a change before applying.")

    def _add_row(self):
        if not self.dataset_tab: return
        r = max(0, self._table.rowCount() - 1); self._updating = True
        try:
            self._table.insertRow(r); self._table.setItem(r, 0, _ro(_item(str(r + 1), Qt.AlignmentFlag.AlignCenter))); self._table.setItem(r, 1, _item("", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)); self._table.setItem(r, 2, _item("", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)); self._table.setItem(r, 3, _ro(_item("—", Qt.AlignmentFlag.AlignCenter))); self._table.setItem(r, 4, _ro(_item("", Qt.AlignmentFlag.AlignCenter)))
        finally:
            self._updating = False
        self._dirty = True; self._update_action_state(); self._table.setCurrentCell(r, 1); self._table.editItem(self._table.item(r, 1)); self._set_status("Added a new editable row.", C.AMBER, "fa6s.plus")

    def _remove_rows(self):
        if not self.dataset_tab or not self._table.selectionModel(): return
        rows = sorted({i.row() for i in self._table.selectionModel().selectedRows() if i.row() < self._table.rowCount() - 1}, reverse=True)
        if not rows: return
        self._updating = True
        try:
            for row in rows: self._table.removeRow(row)
        finally:
            self._updating = False
        for r in range(max(0, self._table.rowCount() - 1)):
            self._table.item(r, 0).setText(str(r + 1))
        self._dirty = True; self._update_action_state(); self._set_status(f"Removed {len(rows)} row{'s' if len(rows) != 1 else ''}.", C.AMBER, "fa6s.minus")

    def _reset_table(self):
        self._refresh_from_dataset(); self._set_status("Reverted unsaved edits.", C.TEXT_MID, "fa6s.rotate-left"); QTimer.singleShot(1800, self._refresh_status)

    def _collect_rows(self, allow_partial: bool = False):
        rows = []
        for r in range(max(0, self._table.rowCount() - 1)):
            size = self._table.item(r, 1).text().strip() if self._table.item(r, 1) else ""
            pct = self._table.item(r, 2).text().strip() if self._table.item(r, 2) else ""
            if not size and not pct: continue
            if not size or not pct:
                if allow_partial: continue
                raise ValueError(f"Row {r + 1} is incomplete. Fill both editable columns or clear the row.")
            try: size_val = float(size.replace(",", "."))
            except ValueError as exc: raise ValueError(f"Row {r + 1} has an invalid sieve size.") from exc
            try: pct_val = float(pct.replace(",", "."))
            except ValueError as exc: raise ValueError(f"Row {r + 1} has an invalid % passing value.") from exc
            rows.append((size_val, pct_val))
        if len(rows) < 3: raise ValueError("At least 3 complete rows are required to rebuild the dataset.")
        return sorted(rows, key=lambda item: item[0], reverse=True)

    def _apply_rows(self):
        if not self.dataset_tab: return
        try:
            rows = self._collect_rows()
            self.dataset_tab.apply_distribution_rows(rows)
        except Exception as exc:
            self._set_status(str(exc), C.LED_ERR, "fa6s.triangle-exclamation"); return
        self._refresh_from_dataset(); self._set_status(f"Applied {len(rows)} extracted rows to {self.dataset.sample_name}.", C.OLIVE, "fa6s.circle-check"); QTimer.singleShot(1800, self._refresh_status)

    def _copy_csv(self):
        try: rows = self._collect_rows(True) if self._dirty else [(row["size"], row["passing"]) for row in self._rows]
        except Exception: rows = [(row["size"], row["passing"]) for row in self._rows]
        buf = io.StringIO(); writer = csv.writer(buf); hdr = ["Sieve (mm)"]
        if self._mode in (self._MODE_PASSING, self._MODE_BOTH): hdr.append("% Passing")
        if self._mode in (self._MODE_MASS, self._MODE_BOTH): hdr.append("Mass (g)")
        writer.writerow(hdr); mass_lookup = {row["size"]: row["mass"] for row in self._rows}
        for size, pct in rows:
            line = [_fmt_mm(size).replace(" mm", "")]
            if self._mode in (self._MODE_PASSING, self._MODE_BOTH): line.append(f"{pct:.4f}")
            if self._mode in (self._MODE_MASS, self._MODE_BOTH):
                m = mass_lookup.get(size); line.append(f"{m:.4f}" if m is not None else "")
            writer.writerow(line)
        QApplication.clipboard().setText(buf.getvalue().strip()); self._set_status(f"Copied {len(rows)} extracted row{'s' if len(rows) != 1 else ''} to clipboard.", C.OLIVE, "fa6s.copy"); QTimer.singleShot(1800, self._refresh_status)

    def _set_mode(self, mode: str):
        self._mode = mode
        if not self._mode_btns[mode].isChecked(): self._mode_btns[mode].setChecked(True)
        self._table.setColumnHidden(2, mode not in (self._MODE_PASSING, self._MODE_BOTH))
        self._table.setColumnHidden(3, mode not in (self._MODE_MASS, self._MODE_BOTH))
        self._refresh_status()

    def _refresh_status(self):
        msgs = getattr(self.dataset, "validation_messages", []) or []
        errors = sum(1 for m in msgs if getattr(m, "severity", None) and m.severity.name == "ERROR")
        warns = sum(1 for m in msgs if getattr(m, "severity", None) and m.severity.name == "WARNING")
        if errors: self._set_status(f"Validation issues present · {errors} error(s){', ' + str(warns) + ' warning(s)' if warns else ''}", "#a03020", "fa6s.triangle-exclamation"); return
        if warns: self._set_status(f"Validation warnings present · {warns} warning(s)", C.AMBER, "fa6s.triangle-exclamation"); return
        total = sum(v for v in self._mass_values if v is not None); text = f"All fractions valid · Total mass {total:.1f} g" if self._mass_source == "actual" else ("All fractions valid · Mass derived from % passing" if self._mode in (self._MODE_MASS, self._MODE_BOTH) else "All fractions valid")
        self._set_status(text, C.OLIVE, "fa6s.circle-check")

    def _set_status(self, text: str, color: str, icon_name: str):
        try: self._status_icon.setPixmap(_icon(icon_name, color).pixmap(13, 13))
        except Exception: self._status_icon.setText("•"); self._status_icon.setStyleSheet(f"color: {color};")
        self._status.setText(text)

    def _can_open_mapper(self):
        parent = self.parent()
        return bool(self.file_path and parent is not None and hasattr(parent, "edit_file_mapping"))

    def _open_mapper(self):
        parent = self.parent()
        if not self._can_open_mapper():
            QMessageBox.information(self, "Mapper", "Column mapping is not available for this dataset."); return
        self.accept(); parent.edit_file_mapping(self.file_path)

    def _load_source_rows(self):
        if not self._actual_file_path: self._source_error = "This dataset is not linked to a source file."; return
        if not os.path.exists(self._actual_file_path): self._source_error = f"Source file not found: {self._actual_file_path}"; return
        ext = os.path.splitext(self._actual_file_path)[1].lower()
        try:
            if ext in DELIMITED_TEXT_EXTENSIONS:
                self._source_rows, _delimiter, _encoding = read_delimited_rows(
                    self._actual_file_path
                )
            elif ext in {".xlsx", ".xls"}:
                import pandas as pd
                excel_file = pd.ExcelFile(self._actual_file_path)
                try: sheet_name = self._sheet_name or (excel_file.sheet_names[0] if excel_file.sheet_names else None)
                finally: excel_file.close()
                df = pd.read_excel(self._actual_file_path, sheet_name=sheet_name, header=None)
                self._source_rows = [[str(c) if pd.notna(c) else "" for c in row] for row in df.values.tolist()]
            else:
                self._source_error = f"Source preview is not available for {ext or 'this file type'}."
        except Exception as exc:
            self._source_error = str(exc)

    def _refresh_source_summary(self):
        if self._actual_file_path:
            meta = [os.path.basename(self._actual_file_path)]
            if self._sheet_name: meta.append(f"Sheet {self._sheet_name}")
            if self._source_rows: meta.extend([f"{len(self._source_rows)} rows", f"{max(len(r) for r in self._source_rows)} columns"])
            self._source_meta.setText("  ·  ".join(meta))
        else:
            self._source_meta.setText("No source file is attached to this dataset.")
        self._source_map.setText(self._mapping_summary())

    def _populate_source_table(self):
        if self._source_rows:
            headers = [f"Col {i + 1}" for i in range(max(len(r) for r in self._source_rows))]
            ColumnMapperDialog.populate_preview_table(self._source_table, self._source_rows, headers)
            self._source_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self._source_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems); self._source_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self._highlight_mapping(); return
        self._source_table.clear(); self._source_table.setRowCount(1); self._source_table.setColumnCount(1); self._source_table.setHorizontalHeaderLabels(["Source"]); self._source_table.setItem(0, 0, _ro(QTableWidgetItem(self._source_error or "No source data available.")))

    def _highlight_mapping(self):
        cols = _mapped_cols(self.mapping_state); cells = _mapped_cells(self.mapping_state)
        for col, (label, color_name) in cols.items():
            if 0 <= col < self._source_table.columnCount():
                hdr = self._source_table.horizontalHeaderItem(col)
                if hdr: _tint(hdr, color_name, 46); hdr.setToolTip(label)
                for row in range(self._source_table.rowCount()):
                    item = self._source_table.item(row, col)
                    if item: _tint(item, color_name, 34); item.setToolTip(label)
        for (row, col), (label, color_name) in cells.items():
            if 0 <= row < self._source_table.rowCount() and 0 <= col < self._source_table.columnCount():
                item = self._source_table.item(row, col)
                if item: _tint(item, color_name, 64); item.setToolTip(label)

    def _mapping_summary(self):
        if not self.mapping_state:
            return "Source view shows the original file contents. This dataset was loaded without a saved manual mapping state."
        if self.mapping_state.get("raw_sieve_mode"):
            cols = self.mapping_state.get("column_indices") or {}
            return f"Derived from raw sieve weights. Size col {cols.get('raw_size', '—')}, empty-sieve col {cols.get('empty_sieve', '—')}, loaded-sieve col {cols.get('sieve_sample', '—')}."
        if self.mapping_state.get("calculated_selection_mode") == "range":
            size_n = len(self.mapping_state.get("selected_size_range") or []); pct_n = len(self.mapping_state.get("selected_percent_range") or [])
            return f"Derived from selected source-cell ranges. {size_n} size cell{'s' if size_n != 1 else ''} and {pct_n} percent cell{'s' if pct_n != 1 else ''} are highlighted."
        cols = self.mapping_state.get("column_indices") or {}
        pct_label = f"retained col {cols.get('retained')}" if cols.get("retained") else f"passing col {cols.get('passing', '—')}"
        return f"Derived from mapped source columns. Size col {cols.get('size', '—')}, {pct_label}."


def _tint(item: QTableWidgetItem, color_name: str, alpha: int):
    color = QColor(color_name); color.setAlpha(alpha); item.setBackground(color)


def _mapped_cols(state: dict):
    roles = {}
    cols = state.get("column_indices") or {}
    if state.get("raw_sieve_mode"):
        role_map = {"raw_size": ("Mapped raw sieve size column", C.OLIVE), "empty_sieve": ("Mapped empty sieve mass column", "#8f7d69"), "sieve_sample": ("Mapped loaded sieve mass column", C.K_BLUE)}
    else:
        role_map = {"size": ("Mapped sieve size column", C.OLIVE), "passing": ("Mapped percent passing column", C.K_BLUE), "retained": ("Mapped percent retained column", C.AMBER)}
    for key, spec in role_map.items():
        value = cols.get(key)
        if value: roles[int(value) - 1] = spec
    return roles


def _mapped_cells(state: dict):
    roles = {}
    if state.get("calculated_selection_mode") != "range": return roles
    for row, col in state.get("selected_size_range") or []: roles[(int(row), int(col))] = ("Mapped sieve size cell", C.OLIVE)
    for row, col in state.get("selected_percent_range") or []: roles[(int(row), int(col))] = ("Mapped percent cell", C.K_BLUE)
    return roles
