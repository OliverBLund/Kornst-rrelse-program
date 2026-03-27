"""
Concept-aligned data inspector dialog for loaded datasets.
"""

from __future__ import annotations

import csv
import io
from typing import Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.dialog_chrome import make_dialog_footer, make_dialog_header
from gui.theme import C, F, SZ, icon as _icon
from qt_chrome.frameless_dialog_base import FramelessDialogBase


class DataInspectorDialog(FramelessDialogBase):
    """Inspect a loaded grain-size dataset using the 04_dialogs concept layout."""

    _MODE_PASSING = "passing"
    _MODE_MASS = "mass"
    _MODE_BOTH = "both"

    def __init__(self, dataset, scheme=None, file_path: str | None = None, parent=None):
        super().__init__(parent, default_mode="auto")
        self.dataset = dataset
        self.scheme = scheme
        self.file_path = file_path or getattr(dataset, "file_path", None)
        self._mass_source = "derived"
        self._mass_basis_total = 100.0
        self._rows = self._build_rows()
        self._mass_values = [row["mass"] for row in self._rows]
        self._has_mass_data = any(value is not None for value in self._mass_values)
        self._mode = self._MODE_PASSING
        self._status_default = ""

        self.setWindowTitle(f"Data Inspector - {self.dataset.sample_name}")
        self.setModal(True)
        self.resize(760, 560)
        self.setMinimumSize(680, 460)

        self._build_ui()
        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )
        self._populate_table()
        self._set_mode(self._MODE_PASSING)

    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"QTableWidget {{ background: {C.BG}; border: none; gridline-color: {C.BORDER}; "
            f"selection-background-color: rgba(107,142,35,.08); selection-color: {C.TEXT}; }}"
            f"QHeaderView::section {{ background: {C.BG_RAISED}; border: none; border-bottom: 1px solid {C.BORDER}; "
            f"padding: 8px 10px; color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt; font-weight: 600; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header_widget = make_dialog_header(
            "Data Inspector",
            f"{self.dataset.sample_name} · {len(self._rows)} sieve fractions",
            fa_icon="fa6s.table",
            close_fn=self.accept,
        )
        root.addWidget(self._header_widget)

        toolbar = QWidget()
        toolbar.setStyleSheet(
            f"background: {C.BG_LOW}; border-bottom: 1px solid {C.BORDER};"
        )
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(14, 10, 14, 10)
        tb_lay.setSpacing(8)

        tb_lay.addWidget(self._make_metric_chip("D10", _format_mm(self.dataset.get_d10())))
        tb_lay.addWidget(self._make_metric_chip("D50", _format_mm(self.dataset.get_d50())))
        tb_lay.addWidget(self._make_metric_chip("D60", _format_mm(self.dataset.get_d60())))
        tb_lay.addWidget(self._make_metric_chip("Cu", _format_ratio(self.dataset.get_uniformity_coefficient())))
        tb_lay.addStretch(1)

        mode_wrap = QWidget()
        mode_wrap.setObjectName("diModeGroup")
        mode_wrap.setFixedHeight(28)
        mode_wrap.setStyleSheet(
            f"QWidget#diModeGroup {{ background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; }}"
        )
        mode_lay = QHBoxLayout(mode_wrap)
        mode_lay.setContentsMargins(0, 0, 0, 0)
        mode_lay.setSpacing(0)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_buttons: dict[str, QPushButton] = {}

        self._mode_buttons[self._MODE_PASSING] = self._make_mode_button("% Passing", self._MODE_PASSING)
        self._mode_buttons[self._MODE_MASS] = self._make_mode_button("Mass (g)", self._MODE_MASS, with_divider=True)
        self._mode_buttons[self._MODE_BOTH] = self._make_mode_button("Both", self._MODE_BOTH, with_divider=True)

        for idx, mode in enumerate((self._MODE_PASSING, self._MODE_MASS, self._MODE_BOTH)):
            btn = self._mode_buttons[mode]
            mode_lay.addWidget(btn)

        tb_lay.addWidget(mode_wrap)
        root.addWidget(toolbar)

        table_wrap = QWidget()
        table_wrap.setStyleSheet(f"background: {C.BG};")
        tw_lay = QVBoxLayout(table_wrap)
        tw_lay.setContentsMargins(12, 12, 12, 12)
        tw_lay.setSpacing(0)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["#", "Sieve (mm)", "% Passing", "Mass (g)", "Distribution"]
        )
        self._table.horizontalHeaderItem(4).setToolTip(
            "Relative share of total material in this sieve fraction"
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.setFrameShape(QFrame.Shape.NoFrame)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setFont(QFont(F.MONO, F.SZ_SM))
        self._table.setStyleSheet(
            self._table.styleSheet()
            + f"QTableWidget::item {{ padding: 6px 8px; border-bottom: 1px solid rgba(0,0,0,.04); }}"
            + f"QTableWidget::item:alternate {{ background: rgba(255,255,255,.45); }}"
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        tw_lay.addWidget(self._table)
        root.addWidget(table_wrap, 1)

        self._status_widget, self._status_label = self._build_status_widget()
        footer = make_dialog_footer(
            [
                ("Copy CSV", self._copy_csv, "secondary"),
                ("Close", self.accept, "primary"),
            ],
            left_widget=self._status_widget,
        )
        for button in footer.findChildren(QPushButton):
            if button.text() == "Copy CSV":
                try:
                    button.setIcon(_icon("fa6s.copy", C.TEXT_MID))
                except Exception:
                    pass
            elif button.text() == "Close":
                try:
                    button.setIcon(_icon("fa6s.xmark", "#ffffff"))
                except Exception:
                    pass
        root.addWidget(footer)

    def _make_metric_chip(self, label: str, value: str) -> QWidget:
        chip = QWidget()
        chip.setObjectName("diMetricChip")
        chip.setFixedHeight(28)
        chip.setStyleSheet(
            f"QWidget#diMetricChip {{ background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; }}"
        )
        lay = QHBoxLayout(chip)
        lay.setContentsMargins(9, 4, 9, 4)
        lay.setSpacing(6)

        dot = QLabel()
        dot.setObjectName("diMetricIcon")
        try:
            dot.setPixmap(_icon("fa6s.circle-dot", C.TEXT_MUTED).pixmap(9, 9))
        except Exception:
            dot.setText("•")
            dot.setStyleSheet(f"color: {C.TEXT_MUTED}; border: none; background: transparent;")
        else:
            dot.setStyleSheet("border: none; background: transparent;")
        lay.addWidget(dot)

        name_lbl = QLabel(label)
        name_lbl.setObjectName("diMetricKey")
        name_lbl.setStyleSheet(
            f"background: transparent; border: none; padding: 0px; margin: 0px; "
            f"color: {C.TEXT_MID}; font-size: {F.SZ_XS}pt;"
        )
        value_lbl = QLabel(value)
        value_lbl.setObjectName("diMetricValue")
        value_lbl.setFont(QFont(F.MONO, F.SZ_SM))
        value_lbl.setStyleSheet(
            f"background: transparent; border: none; padding: 0px; margin: 0px; "
            f"color: {C.TEXT}; font-weight: 500;"
        )
        lay.addWidget(name_lbl)
        lay.addWidget(value_lbl)
        return chip

    def _make_mode_button(self, label: str, mode: str, with_divider: bool = False) -> QPushButton:
        button = QPushButton(label)
        button.setCheckable(True)
        button.setProperty("modeBtn", True)
        button.setFixedHeight(28)
        divider = f"border-left: 1px solid {C.BORDER};" if with_divider else ""
        button.setStyleSheet(
            f"QPushButton {{ background: {C.BG_RAISED}; border: none; border-radius: 0px; "
            f"padding: 3px 10px; color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; min-width: 0; {divider} }}"
            f"QPushButton:hover:!checked {{ background: {C.BG_LOW}; color: {C.TEXT}; }}"
            f"QPushButton:checked {{ background: {C.SB_ACT}; color: {C.SB_TEXT}; }}"
            f"QPushButton:pressed {{ background: {C.SB_ACT}; color: {C.SB_TEXT}; }}"
        )
        button.clicked.connect(lambda checked=False, m=mode: self._set_mode(m))
        self._mode_group.addButton(button)
        return button

    def _build_status_widget(self) -> tuple[QWidget, QLabel]:
        widget = QWidget()
        widget.setObjectName("diStatusWidget")
        widget.setFixedHeight(18)
        lay = QHBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._status_icon = QLabel()
        self._status_icon.setFixedSize(10, 10)
        self._status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_icon.setStyleSheet("background: transparent;")
        lay.addWidget(self._status_icon)

        label = QLabel()
        label.setFont(QFont(F.MONO, F.SZ_XS))
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        label.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
        lay.addWidget(label)

        self._status_label = label
        return widget, label

    def _status_text(self) -> str:
        messages = getattr(self.dataset, "validation_messages", []) or []
        warnings = sum(1 for msg in messages if getattr(msg, "severity", None) and msg.severity.name == "WARNING")
        errors = sum(1 for msg in messages if getattr(msg, "severity", None) and msg.severity.name == "ERROR")
        total_mass = sum(value for value in self._mass_values if value is not None)

        if errors:
            detail = f"{errors} error(s)"
            if warnings:
                detail += f", {warnings} warning(s)"
            return f"Validation issues present · {detail}"
        if warnings:
            return f"Validation warnings present · {warnings} warning(s)"
        if self._mass_source == "actual":
            return f"All fractions valid · Total mass {total_mass:.1f} g"
        if self._mode in (self._MODE_MASS, self._MODE_BOTH):
            return f"All fractions valid · Mass derived from % passing ({self._mass_basis_total:.0f} g basis)"
        return "All fractions valid"

    def _status_icon_spec(self) -> tuple[str, str]:
        messages = getattr(self.dataset, "validation_messages", []) or []
        if any(getattr(msg, "severity", None) and msg.severity.name == "ERROR" for msg in messages):
            return "fa6s.triangle-exclamation", "#a03020"
        if any(getattr(msg, "severity", None) and msg.severity.name == "WARNING" for msg in messages):
            return "fa6s.triangle-exclamation", C.AMBER
        return "fa6s.circle-check", C.OLIVE

    def _set_status(self, text: str, icon_name: str, color: str) -> None:
        try:
            self._status_icon.setPixmap(_icon(icon_name, color).pixmap(10, 10))
        except Exception:
            self._status_icon.setText("•")
            self._status_icon.setStyleSheet(f"color: {color}; background: transparent;")
        self._status_label.setText(text)

    def _refresh_status(self) -> None:
        self._status_default = self._status_text()
        self._set_status(self._status_default, *self._status_icon_spec())

    def _build_rows(self) -> list[dict[str, float | int | None]]:
        particle_sizes = list(getattr(self.dataset, "particle_sizes", []))
        percent_passing = list(getattr(self.dataset, "percent_passing", []))
        mass_values = _extract_mass_values(self.dataset)
        if mass_values is not None:
            self._mass_source = "actual"
            self._mass_basis_total = sum(value for value in mass_values if value is not None)
        else:
            self._mass_source = "derived"
            self._mass_basis_total = _extract_total_mass(self.dataset) or 100.0
            mass_values = _derive_mass_values(
                particle_sizes,
                percent_passing,
                self._mass_basis_total,
            )
        rows = []
        paired = list(
            zip(
                particle_sizes,
                percent_passing,
                mass_values or [None] * len(particle_sizes),
            )
        )
        for idx, (size, passing, mass) in enumerate(sorted(paired, key=lambda item: item[0]), start=1):
            distribution = 0.0
            if mass is not None and self._mass_basis_total > 0:
                distribution = max(0.0, float(mass) / self._mass_basis_total * 100.0)
            rows.append(
                {
                    "index": idx,
                    "size": float(size),
                    "passing": float(passing),
                    "mass": float(mass) if mass is not None else None,
                    "distribution": distribution,
                }
            )
        return rows

    def _populate_table(self) -> None:
        total_rows = len(self._rows) + 1
        self._table.setRowCount(total_rows)

        for row_index, row in enumerate(self._rows):
            self._table.setItem(row_index, 0, _make_item(str(row["index"]), Qt.AlignmentFlag.AlignCenter))
            self._table.setItem(row_index, 1, _make_item(_format_mm_value(row["size"]), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft))
            self._table.setItem(row_index, 2, _make_item(f"{row['passing']:.1f}", Qt.AlignmentFlag.AlignCenter))
            self._table.setItem(
                row_index,
                3,
                _make_item(
                    f"{row['mass']:.2f}" if row["mass"] is not None else "—",
                    Qt.AlignmentFlag.AlignCenter,
                ),
            )
            dist_widget = _DistributionCell(
                mass=row["mass"],
                distribution_pct=row["distribution"],
                parent=self._table,
            )
            self._table.setCellWidget(row_index, 4, dist_widget)
            self._table.setRowHeight(row_index, 32)

        total_row = total_rows - 1
        total_font = QFont(F.MONO, F.SZ_SM)
        total_font.setWeight(QFont.Weight.DemiBold)
        self._table.setItem(total_row, 0, _make_item("Σ", Qt.AlignmentFlag.AlignCenter, total_font))
        self._table.setItem(total_row, 1, _make_item("Total", Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, total_font))
        self._table.setItem(total_row, 2, _make_item("100.0", Qt.AlignmentFlag.AlignCenter, total_font))
        self._table.setItem(
            total_row,
            3,
            _make_item(
                f"{sum(value for value in self._mass_values if value is not None):.1f}" if self._has_mass_data else "—",
                Qt.AlignmentFlag.AlignCenter,
                total_font,
            ),
        )
        self._table.setItem(total_row, 4, _make_item("", Qt.AlignmentFlag.AlignCenter, total_font))
        self._table.setRowHeight(total_row, 34)

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        button = self._mode_buttons[mode]
        if not button.isChecked():
            button.setChecked(True)

        show_passing = mode in (self._MODE_PASSING, self._MODE_BOTH)
        show_mass = mode in (self._MODE_MASS, self._MODE_BOTH)
        self._table.setColumnHidden(2, not show_passing)
        self._table.setColumnHidden(3, not show_mass)
        self._refresh_status()

    def _copy_csv(self) -> None:
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        headers = ["Sieve (mm)"]
        if self._mode in (self._MODE_PASSING, self._MODE_BOTH):
            headers.append("% Passing")
        if self._mode in (self._MODE_MASS, self._MODE_BOTH):
            headers.append("Mass (g)")
        writer.writerow(headers)

        for row in self._rows:
            csv_row = [_format_mm_value(row["size"])]
            if self._mode in (self._MODE_PASSING, self._MODE_BOTH):
                csv_row.append(f"{row['passing']:.4f}")
            if self._mode in (self._MODE_MASS, self._MODE_BOTH):
                csv_row.append(f"{row['mass']:.4f}" if row["mass"] is not None else "")
            writer.writerow(csv_row)

        QApplication.clipboard().setText(buffer.getvalue().strip())
        self._set_status(
            f"Copied {len(self._rows)} rows to clipboard",
            "fa6s.copy",
            C.OLIVE,
        )
        QTimer.singleShot(
            1800,
            self._refresh_status,
        )


class _InlineBar(QWidget):
    """Simple distribution bar used in the inspector table."""

    def __init__(self, value: float, parent=None):
        super().__init__(parent)
        self._value = max(0.0, min(100.0, float(value)))
        self.setMinimumHeight(18)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(232, 225, 210))
        painter.drawRoundedRect(rect, 5, 5)

        fill_width = rect.width() * (self._value / 100.0)
        if fill_width > 0:
            fill_rect = QRectF(rect.left(), rect.top(), fill_width, rect.height())
            painter.setBrush(QColor(C.OLIVE))
            radius = min(5.0, fill_rect.height() / 2.0, fill_rect.width() / 2.0)
            painter.drawRoundedRect(fill_rect, radius, radius)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(0, 0, 0, 25)))
        painter.drawRoundedRect(rect, 5, 5)
        painter.end()


class _DistributionCell(QWidget):
    """Inline distribution summary with value text plus bar."""

    def __init__(self, mass: float | None, distribution_pct: float, parent=None):
        super().__init__(parent)
        self._mass = mass
        self._distribution_pct = max(0.0, distribution_pct)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)

        self._label = QLabel(_format_distribution_label(mass, distribution_pct))
        self._label.setFont(QFont(F.MONO, F.SZ_XS))
        self._label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; background: transparent; border: none;"
        )
        self._label.setFixedWidth(128)
        self._label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._label)

        self._bar = _InlineBar(distribution_pct, self)
        layout.addWidget(self._bar, 1)

        tooltip = _distribution_tooltip(mass, distribution_pct)
        self.setToolTip(tooltip)
        self._label.setToolTip(tooltip)
        self._bar.setToolTip(tooltip)


def _extract_mass_values(dataset) -> Optional[list[float]]:
    for attr in (
        "mass_values",
        "mass_grams",
        "fraction_masses",
        "retained_masses",
        "retained_mass_grams",
        "retained_weights",
        "weights_g",
    ):
        values = getattr(dataset, attr, None)
        if isinstance(values, (list, tuple)) and len(values) == len(getattr(dataset, "particle_sizes", [])):
            try:
                return [float(value) if value is not None else None for value in values]
            except (TypeError, ValueError):
                continue
    return None


def _extract_total_mass(dataset) -> Optional[float]:
    for attr in ("sample_mass", "total_mass", "mass_total", "total_weight"):
        value = getattr(dataset, attr, None)
        try:
            if value is not None and float(value) > 0:
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _derive_mass_values(
    particle_sizes: list[float],
    percent_passing: list[float],
    total_mass: float,
) -> list[float]:
    """Derive per-fraction mass from cumulative percent passing on a fixed basis."""
    indexed_pairs = sorted(
        enumerate(zip(particle_sizes, percent_passing)),
        key=lambda item: item[1][0],
    )
    masses: list[float] = [0.0] * len(indexed_pairs)
    previous_passing = 0.0

    for pair_index, (original_index, (_, passing)) in enumerate(indexed_pairs):
        current_passing = max(previous_passing, min(100.0, float(passing)))
        if pair_index == len(indexed_pairs) - 1:
            # Let the largest listed sieve absorb any coarser remainder so displayed masses sum to the basis.
            fraction_pct = max(0.0, 100.0 - previous_passing)
        else:
            fraction_pct = max(0.0, current_passing - previous_passing)
        masses[original_index] = fraction_pct / 100.0 * total_mass
        previous_passing = current_passing

    return masses


def _make_item(text: str, alignment: Qt.AlignmentFlag, font: QFont | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(int(alignment))
    if font is not None:
        item.setFont(font)
    return item


def _format_ratio(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "N/A"


def _format_mm(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{_format_mm_value(value)} mm"


def _format_mm_value(value: float) -> str:
    if value >= 10:
        return f"{value:.1f}"
    if value >= 1:
        return f"{value:.2f}"
    if value >= 0.1:
        return f"{value:.3f}"
    return f"{value:.4f}"


def _format_mass_value(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _format_distribution_label(mass: float | None, distribution_pct: float) -> str:
    return f"{_format_mass_value(mass)} g | {distribution_pct:.1f}%"


def _distribution_tooltip(mass: float | None, distribution_pct: float) -> str:
    if mass is None:
        return f"{distribution_pct:.1f}% of total material in this fraction"
    return f"{_format_mass_value(mass)} g retained in this fraction ({distribution_pct:.1f}% of total)"
