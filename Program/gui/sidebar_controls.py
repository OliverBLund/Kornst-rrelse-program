"""Shared sidebar row builders for the plot workspaces.

Both the Individual Samples (plot_workspace) and Batch Comparison
(comparison_plot_widget) sidebars use the same row patterns — label + control
with a 1px sandy bottom border. Keeping these builders free functions in one
module avoids duplication and guarantees the two sidebars stay visually in sync.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from .theme import combo_popup_qss
from .toggle_switch import ToggleSwitch
from .collapsible_section import CollapsibleSection
from .plot_styles import PlotStyle


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
    (0, "Auto (fit and wrap)"),
    (1, "1 column"),
    (2, "2 columns"),
    (3, "3 columns"),
    (4, "4 columns"),
]

MARKER_MODES: list[tuple[str, Optional[bool]]] = [
    ("Preset behavior", None),
    ("Show", True),
    ("Hide", False),
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


class PlotStyleControlSections(QWidget):
    """Shared typography, line/marker, and legend accordion controls."""

    style_changed = pyqtSignal(dict)
    reset_requested = pyqtSignal()

    def __init__(
        self,
        style: PlotStyle,
        *,
        include_reset: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self.typography_section = CollapsibleSection(
            "Typography", "fa6s.text-height",
            CollapsibleSection.AMBER, expanded=False,
        )
        self.row_title_size, self.title_size_spin = make_spin_row(
            "Title size", 6, 36
        )
        self.row_label_size, self.label_size_spin = make_spin_row(
            "Axis label size", 6, 36
        )
        self.row_tick_size, self.tick_size_spin = make_spin_row(
            "Tick size", 5, 24
        )
        for row in (
            self.row_title_size,
            self.row_label_size,
            self.row_tick_size,
        ):
            self.typography_section.add_widget(row)
        root.addWidget(self.typography_section)

        self.lines_markers_section = CollapsibleSection(
            "Lines & Markers", "fa6s.chart-line",
            CollapsibleSection.BLUE, expanded=True,
        )
        self.row_curve_width, self.curve_width_spin = make_dspin_row(
            "Curve width", 0.5, 6.0, 0.25, 2
        )
        self.lines_markers_section.add_widget(self.row_curve_width)
        self.row_marker_mode, self.marker_mode_combo = make_combo_row(
            "Markers", [label for label, _value in MARKER_MODES]
        )
        self.lines_markers_section.add_widget(self.row_marker_mode)
        self.row_marker_size, self.marker_size_spin = make_dspin_row(
            "Marker size", 0.0, 14.0, 0.5, 1
        )
        self.lines_markers_section.add_widget(self.row_marker_size)
        root.addWidget(self.lines_markers_section)

        self.legend_section = CollapsibleSection(
            "Legend", "fa6s.list",
            CollapsibleSection.EARTH, expanded=False,
        )
        self.row_legend_loc, self.legend_loc_combo = make_combo_row(
            "Legend position", [label for _loc, _bbox, label in LEGEND_LOCATIONS]
        )
        self.legend_section.add_widget(self.row_legend_loc)
        self.row_legend_layout, self.legend_layout_combo = make_combo_row(
            "Legend columns", [label for _ncol, label in LEGEND_LAYOUTS]
        )
        self.legend_section.add_widget(self.row_legend_layout)
        self.row_legend_alpha, self.legend_alpha_spin = make_dspin_row(
            "Legend opacity", 0.0, 1.0, 0.05, 2
        )
        self.legend_section.add_widget(self.row_legend_alpha)
        self.row_legend_size, self.legend_size_spin = make_spin_row(
            "Legend size", 5, 24
        )
        self.legend_section.add_widget(self.row_legend_size)
        root.addWidget(self.legend_section)

        self.reset_button = None
        if include_reset:
            reset_row = QWidget()
            reset_layout = QHBoxLayout(reset_row)
            reset_layout.setContentsMargins(10, 6, 10, 6)
            self.reset_button = QPushButton("Reset to preset")
            self.reset_button.setProperty("pw-btn", True)
            self.reset_button.setEnabled(False)
            self.reset_button.setToolTip(
                "Discard presentation overrides and revert to the selected preset"
            )
            self.reset_button.clicked.connect(self.reset_requested.emit)
            reset_layout.addWidget(self.reset_button)
            root.addWidget(reset_row)

        self.sync_style(style)
        self.title_size_spin.valueChanged.connect(
            lambda value: self.style_changed.emit({"title_fontsize": int(value)})
        )
        self.label_size_spin.valueChanged.connect(
            lambda value: self.style_changed.emit({"label_fontsize": int(value)})
        )
        self.tick_size_spin.valueChanged.connect(
            lambda value: self.style_changed.emit({"tick_fontsize": int(value)})
        )
        self.curve_width_spin.valueChanged.connect(
            lambda value: self.style_changed.emit({"curve_linewidth": float(value)})
        )
        self.marker_mode_combo.currentIndexChanged.connect(
            self._on_marker_mode_changed
        )
        self.marker_size_spin.valueChanged.connect(
            lambda value: self.style_changed.emit({"curve_markersize": float(value)})
        )
        self.legend_loc_combo.currentIndexChanged.connect(
            self._on_legend_location_changed
        )
        self.legend_layout_combo.currentIndexChanged.connect(
            self._on_legend_layout_changed
        )
        self.legend_alpha_spin.valueChanged.connect(
            lambda value: self.style_changed.emit({"legend_framealpha": float(value)})
        )
        self.legend_size_spin.valueChanged.connect(
            lambda value: self.style_changed.emit({"legend_fontsize": int(value)})
        )

    def _on_marker_mode_changed(self, index: int) -> None:
        marker_mode = MARKER_MODES[index][1]
        self.marker_size_spin.setEnabled(marker_mode is not False)
        if marker_mode is True and self.marker_size_spin.value() <= 0:
            self.marker_size_spin.setValue(4.0)
        self.style_changed.emit({"curve_markers_visible": marker_mode})

    def set_lines_markers_visible(self, visible: bool) -> None:
        """Show the curve controls only when the active chart draws curves."""
        self.lines_markers_section.setVisible(visible)

    def _on_legend_location_changed(self, index: int) -> None:
        loc, bbox, _label = LEGEND_LOCATIONS[index]
        self.style_changed.emit({
            "legend_loc": loc,
            "legend_bbox_to_anchor": bbox,
        })

    def _on_legend_layout_changed(self, index: int) -> None:
        ncol, _label = LEGEND_LAYOUTS[index]
        self.style_changed.emit({"legend_ncol": ncol})

    def values(self) -> dict:
        loc, bbox, _label = LEGEND_LOCATIONS[self.legend_loc_combo.currentIndex()]
        ncol, _label = LEGEND_LAYOUTS[self.legend_layout_combo.currentIndex()]
        marker_mode = MARKER_MODES[self.marker_mode_combo.currentIndex()][1]
        return {
            "title_fontsize": self.title_size_spin.value(),
            "label_fontsize": self.label_size_spin.value(),
            "tick_fontsize": self.tick_size_spin.value(),
            "curve_linewidth": self.curve_width_spin.value(),
            "curve_markers_visible": marker_mode,
            "curve_markersize": self.marker_size_spin.value(),
            "legend_loc": loc,
            "legend_bbox_to_anchor": bbox,
            "legend_ncol": ncol,
            "legend_framealpha": self.legend_alpha_spin.value(),
            "legend_fontsize": self.legend_size_spin.value(),
        }

    def sync_style(self, style: PlotStyle) -> None:
        widgets = [
            self.title_size_spin,
            self.label_size_spin,
            self.tick_size_spin,
            self.curve_width_spin,
            self.marker_mode_combo,
            self.marker_size_spin,
            self.legend_loc_combo,
            self.legend_layout_combo,
            self.legend_alpha_spin,
            self.legend_size_spin,
        ]
        for widget in widgets:
            widget.blockSignals(True)

        self.title_size_spin.setValue(int(style.title_fontsize))
        self.label_size_spin.setValue(int(style.label_fontsize))
        self.tick_size_spin.setValue(int(style.tick_fontsize))
        self.curve_width_spin.setValue(float(style.curve_linewidth))
        marker_mode = getattr(style, "curve_markers_visible", None)
        marker_index = next(
            (
                index
                for index, (_label, value) in enumerate(MARKER_MODES)
                if value is marker_mode
            ),
            0,
        )
        self.marker_mode_combo.setCurrentIndex(marker_index)
        self.marker_size_spin.setValue(float(style.curve_markersize))
        self.marker_size_spin.setEnabled(marker_mode is not False)

        loc_index = next(
            (
                index
                for index, (loc, bbox, _label) in enumerate(LEGEND_LOCATIONS)
                if loc == style.legend_loc
                and bbox == style.legend_bbox_to_anchor
            ),
            0,
        )
        self.legend_loc_combo.setCurrentIndex(loc_index)
        layout_index = next(
            (
                index
                for index, (ncol, _label) in enumerate(LEGEND_LAYOUTS)
                if ncol == getattr(style, "legend_ncol", 1)
            ),
            0,
        )
        self.legend_layout_combo.setCurrentIndex(layout_index)
        self.legend_alpha_spin.setValue(float(style.legend_framealpha))
        self.legend_size_spin.setValue(int(style.legend_fontsize))

        for widget in widgets:
            widget.blockSignals(False)

    def set_reset_enabled(self, enabled: bool) -> None:
        if self.reset_button is not None:
            self.reset_button.setEnabled(enabled)


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
