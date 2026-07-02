"""Shared sidebar row builders for the plot workspaces.

Both the Individual Samples (plot_workspace) and Batch Comparison
(comparison_plot_widget) sidebars use the same row patterns — label + control
with a 1px sandy bottom border. Keeping these builders free functions in one
module avoids duplication and guarantees the two sidebars stay visually in sync.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit,
    QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from .theme import combo_popup_qss
from .toggle_switch import ToggleSwitch


# Legend placement options shared by both sidebars.
# Each entry is (matplotlib_loc, bbox_to_anchor_or_None, display_label).
# bbox_to_anchor=None → inside the axes. bbox set → anchored outside the plot.
LEGEND_LOCATIONS: list[tuple[str, Optional[tuple[float, float]], str]] = [
    ("best",         None,           "Best (auto)"),
    ("upper left",   None,           "Inside - upper left"),
    ("upper right",  None,           "Inside - upper right"),
    ("lower left",   None,           "Inside - lower left"),
    ("lower right",  None,           "Inside - lower right"),
    ("center left",  None,           "Inside - center left"),
    ("center right", None,           "Inside - center right"),
    ("upper center", None,           "Inside - upper center"),
    ("lower center", None,           "Inside - lower center"),
    ("upper left",   (1.02, 1.0),    "Outside right - top"),
    ("center left",  (1.02, 0.5),    "Outside right - center"),
    ("lower left",   (1.02, 0.0),    "Outside right - bottom"),
    ("upper right",  (-0.02, 1.0),   "Outside left - top"),
    ("center right", (-0.02, 0.5),   "Outside left - center"),
    ("lower right",  (-0.02, 0.0),   "Outside left - bottom"),
    ("lower left",   (0.0, 1.12),    "Outside top - left"),
    ("lower center", (0.5, 1.12),    "Outside top - center"),
    ("lower right",  (1.0, 1.12),    "Outside top - right"),
    ("upper left",   (0.0, -0.22),   "Outside bottom - left"),
    ("upper center", (0.5, -0.22),   "Outside bottom - center"),
    ("upper right",  (1.0, -0.22),   "Outside bottom - right"),
]


LEGEND_LAYOUTS: list[tuple[int, str]] = [
    (1, "Vertical (1 column)"),
    (2, "Two columns"),
    (0, "Horizontal (fit)"),
]


_ROW_BORDER_QSS = "border-bottom: 1px solid rgba(212,196,168,0.4);"


def _split_series_style(line_style: str) -> tuple[str, str | None]:
    valid_lines = {"-", "--", ":", "-."}
    valid_markers = {"o", "s", "^", "D"}
    text = str(line_style or "-").strip()
    line_part, marker_part = (text.split("|", 1) + [""])[:2]
    line = line_part if line_part in valid_lines else "-"
    marker = marker_part if marker_part in valid_markers else None
    return line, marker


def _normalized_series_style(line_style: str) -> str:
    line, marker = _split_series_style(line_style)
    return f"{line}|{marker}" if marker else line


def _dash_pattern(line_style: str) -> list[float]:
    line, _marker = _split_series_style(line_style)
    return {
        "--": [5.0, 3.0],
        ":": [1.0, 3.0],
        "-.": [5.0, 2.0, 1.0, 2.0],
    }.get(line, [])


class LineStylePreview(QWidget):
    """Small painted preview for matplotlib-style line styles."""

    def __init__(
        self,
        color: str = "#6b8e23",
        line_style: str = "-",
        *,
        muted: bool = False,
        width: int = 30,
        height: int = 14,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._color = color
        self._line_style = _normalized_series_style(line_style)
        self._muted = bool(muted)
        self.setFixedSize(width, height)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setProperty("lineStyle", self._line_style)

    def sizeHint(self) -> QSize:
        return self.size()

    def set_line_style(self, line_style: str) -> None:
        self._line_style = _normalized_series_style(line_style)
        self.setProperty("lineStyle", self._line_style)
        self.update()

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._color)
        if not color.isValid():
            color = QColor("#6b8e23")
        if self._muted:
            color.setAlphaF(0.42)
        pen = QPen(color, 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pattern = _dash_pattern(self._line_style)
        if pattern:
            pen.setDashPattern(pattern)
        painter.setPen(pen)
        y = self.height() // 2
        painter.drawLine(2, y, self.width() - 2, y)
        _line, marker = _split_series_style(self._line_style)
        if marker:
            self._draw_marker(painter, color, marker)
        painter.end()

    def _draw_marker(self, painter: QPainter, color: QColor, marker: str) -> None:
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        radius = 3.2
        marker_pen = QPen(color, 1.3)
        marker_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(marker_pen)
        painter.setBrush(color)

        if marker == "o":
            painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        elif marker == "s":
            painter.drawRect(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        elif marker == "^":
            painter.drawPolygon(QPolygonF([
                QPointF(cx, cy - radius - 0.5),
                QPointF(cx - radius - 0.5, cy + radius),
                QPointF(cx + radius + 0.5, cy + radius),
            ]))
        elif marker == "D":
            painter.drawPolygon(QPolygonF([
                QPointF(cx, cy - radius - 0.7),
                QPointF(cx - radius - 0.7, cy),
                QPointF(cx, cy + radius + 0.7),
                QPointF(cx + radius + 0.7, cy),
            ]))


def _row() -> tuple[QWidget, QHBoxLayout]:
    row = QWidget()
    row.setStyleSheet(_ROW_BORDER_QSS)
    lay = QHBoxLayout(row)
    lay.setContentsMargins(10, 5, 10, 5)
    lay.setSpacing(5)
    return row, lay


def make_axis_row(label: str, default: str):
    """Label on the left, numeric-looking QLineEdit on the right."""
    row, lay = _row()
    lbl = QLabel(label)
    lbl.setProperty("pws-lbl", True)
    inp = QLineEdit(default)
    inp.setProperty("pws-in", True)
    inp.setAlignment(Qt.AlignmentFlag.AlignRight)
    lay.addWidget(lbl, 1)
    lay.addWidget(inp, 0)
    return row, inp, lbl


def make_toggle_row(label: str, checked: bool):
    """Label on the left, a ToggleSwitch on the right. Caller wires the signal."""
    row, lay = _row()
    row.setCursor(Qt.CursorShape.PointingHandCursor)
    lbl = QLabel(label)
    lbl.setProperty("pws-lbl", True)
    sw = ToggleSwitch(checked)
    lay.addWidget(lbl, 1)
    lay.addWidget(sw, 0)
    return row, sw


def make_combo_row(label: str, items: list[str]):
    """Label stacked above a full-width QComboBox.

    Stacked so long items like "Inside — upper left" don't overflow a narrow
    sidebar when laid out beside their label.
    """
    row = QWidget()
    row.setStyleSheet(_ROW_BORDER_QSS)
    lay = QVBoxLayout(row)
    lay.setContentsMargins(10, 6, 10, 6)
    lay.setSpacing(3)
    lbl = QLabel(label)
    lbl.setProperty("pws-lbl", True)
    combo = QComboBox()
    combo.setObjectName("pw-style-sel")
    combo.setStyleSheet(combo_popup_qss())
    combo.addItems(items)
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    lay.addWidget(lbl)
    lay.addWidget(combo)
    return row, combo


def make_spin_row(label: str, minimum: int, maximum: int):
    """Label on the left, fixed-width QSpinBox on the right."""
    row, lay = _row()
    lay.setSpacing(6)
    lbl = QLabel(label)
    lbl.setProperty("pws-lbl", True)
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setFixedWidth(72)
    spin.setAlignment(Qt.AlignmentFlag.AlignRight)
    lay.addWidget(lbl, 1)
    lay.addWidget(spin, 0)
    return row, spin


def make_dspin_row(label: str, minimum: float, maximum: float,
                   step: float, decimals: int):
    """Label on the left, fixed-width QDoubleSpinBox on the right."""
    row, lay = _row()
    lay.setSpacing(6)
    lbl = QLabel(label)
    lbl.setProperty("pws-lbl", True)
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    spin.setDecimals(decimals)
    spin.setFixedWidth(72)
    spin.setAlignment(Qt.AlignmentFlag.AlignRight)
    lay.addWidget(lbl, 1)
    lay.addWidget(spin, 0)
    return row, spin


def make_color_row(name: str, color: str):
    """Label + color swatch. Returns (row, swatch_label) so the caller can update
    the swatch when the underlying color changes."""
    row, lay = _row()
    lbl = QLabel(name)
    lbl.setProperty("pws-lbl", True)
    dot = QLabel()
    dot.setFixedSize(12, 12)
    dot.setCursor(Qt.CursorShape.PointingHandCursor)
    _apply_color_swatch(dot, color)
    lay.addWidget(lbl, 1)
    lay.addWidget(dot, 0)
    return row, dot


def _apply_color_swatch(dot: QLabel, color: str) -> None:
    dot.setStyleSheet(
        f"background: {color}; border-radius: 6px; "
        f"border: 1px solid rgba(0,0,0,0.1);"
    )


def set_swatch_color(dot: QLabel, color: str) -> None:
    """Update an existing color swatch to a new colour."""
    _apply_color_swatch(dot, color)
