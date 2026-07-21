"""
Statistics tab — per-sample descriptive summary ("Sample Summary", Concept A).

A read-only summary of everything computed for one dataset that the Results tab
does not already present method-by-method:

  * metric strip          — sample, soil class, D50, Cu, K geometric mean
  * key grain distribution — D-facts, percentile "used by" table, full grid
  * detailed classification — subdivided bar + ISO 14688 11-band table,
                              plus Cu / Cc / sorting / span
  * hydraulic conductivity — aggregate K summary (geo/arith/median/range/spread)
  * interpretation         — short factual read of the numbers
  * data support           — gradation-curve coverage checks
  * calculation context    — temperature, porosity, permeability class
  * calculation internals  — collapsible: physical constants, effective
                              diameters, phi / Folk-Ward, porosity functions

Everything respects the active classification scheme (stratigraphy) supplied via
set_scheme(); detailed fractions come from grain_classification so the plot,
this tab and the report/export builders share one definition.
"""

from __future__ import annotations

import math
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from data_loader import GrainSizeData
from k_calculations import KCalculationResult, KCalculator
from k_aggregation import build_k_result_summary, AggregateStats
from calculation_internals import (
    compute_calculation_internals,
    TITLE_CONSTANTS,
    TITLE_DIAMETERS,
    TITLE_SORTING,
    TITLE_POROSITY,
)
from grain_classification import (
    ISO14688,
    permeability_class as _perm_class,
    sedimentology_descriptor,
)
from .theme import C, F
from .collapsible_section import CollapsibleSection


# Standard percentiles shown in the full grid (ascending).
_STD_PERCENTILES = [5, 10, 15, 16, 17, 20, 25, 30, 40, 50, 60, 70, 75, 80, 84, 85, 90, 95]
_KEY_PERCENTILES = {10, 30, 50, 60}

# Which characteristic diameters drive which methods (compact reference).
_PCT_USED_BY = [
    (5, "Barr"),
    (10, "Most K methods"),
    (50, "Median · Shepherd · Kruger"),
    (60, "Cu · Beyer · Barr"),
    (95, "Span · Krumbein-Monk"),
]


def _band_color(label: str) -> str:
    """Fill colour for a detailed sub-class band, shaded fine→coarse."""
    low = label.lower()
    if "clay" in low:
        return "#7a9bbd"
    if "silt" in low:
        return "#b09870"
    if "sand" in low:
        if "fine" in low:
            return "#e6d099"
        if "coarse" in low:
            return "#bda154"
        return "#d4b86a"
    if "gravel" in low:
        return "#a89a86"
    if "cobble" in low:
        return "#8d7660"
    return "#cccccc"


def _fmt_mm(value: Optional[float]) -> str:
    return f"{value:.3f}" if value else "—"


def _fmt_sci(value: Optional[float]) -> str:
    return f"{value:.2e}" if value else "—"


# ─────────────────────────────────────────────────────────────────────────────
# Small reusable building blocks
# ─────────────────────────────────────────────────────────────────────────────

class _Card(QFrame):
    """A titled surface card with a header strip and a content body."""

    def __init__(self, title: str, meta: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"_Card {{ background: #fffdf8; border: 1px solid {C.BORDER};"
            f" border-radius: 6px; }}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setStyleSheet(
            f"QFrame {{ background: {C.BG_RAISED}; border: none;"
            f" border-bottom: 1px solid {C.BORDER};"
            f" border-top-left-radius: 6px; border-top-right-radius: 6px; }}"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 5, 10, 5)
        hl.setSpacing(8)
        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet(
            f"color: {C.TEXT_MID}; font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f" font-weight: 800; letter-spacing: 0.7px; background: transparent;"
        )
        hl.addWidget(title_lbl)
        hl.addStretch()
        self._meta_label = QLabel(meta)
        self._meta_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}';"
            f" font-size: {F.SZ_SM}pt; background: transparent;"
        )
        hl.addWidget(self._meta_label)
        root.addWidget(header)

        body_host = QWidget()
        self.body = QVBoxLayout(body_host)
        self.body.setContentsMargins(10, 10, 10, 10)
        self.body.setSpacing(8)
        root.addWidget(body_host)

    def add(self, widget: QWidget) -> None:
        self.body.addWidget(widget)

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)

    def set_meta(self, text: str) -> None:
        self._meta_label.setText(text)


def _make_table(headers: List[str]) -> QTableWidget:
    """A compact, non-interactive table that grows to fit its rows."""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setShowGrid(False)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setStyleSheet(
        f"QTableWidget {{ background: transparent; border: none;"
        f" font-family: '{F.MONO}'; font-size: {F.SZ_MD}pt; color: {C.TEXT_MID};"
        f" alternate-background-color: rgba(212,196,168,0.12); }}"
        f"QHeaderView::section {{ background: {C.BG_RAISED}; border: none;"
        f" border-bottom: 1px solid {C.BORDER}; padding: 3px 6px;"
        f" font-family: '{F.UI}'; font-size: {F.SZ_SM}pt; font-weight: 800;"
        f" color: {C.TEXT_MUTED}; }}"
    )
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    # Key/label columns size to their (short) content; the LAST column stretches to
    # fill the container so a long value can never push the table wider than its box.
    # Over-long values elide instead — the full text is still available as a tooltip.
    last_col = len(headers) - 1
    for col in range(len(headers)):
        mode = (
            QHeaderView.ResizeMode.Stretch if col == last_col
            else QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(col, mode)
    return table


def _fit_table_height(table: QTableWidget) -> None:
    """Size a table to its contents so it never scrolls inside the page."""
    height = table.horizontalHeader().height()
    for row in range(table.rowCount()):
        height += table.rowHeight(row)
    height += 2
    table.setFixedHeight(height)


def _cell(text: str, *, align_right: bool = False, key: bool = False,
          muted: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setToolTip(text)
    flag = Qt.AlignmentFlag.AlignVCenter
    flag |= Qt.AlignmentFlag.AlignRight if align_right else Qt.AlignmentFlag.AlignLeft
    item.setTextAlignment(flag)
    if key:
        item.setForeground(QColor(C.OLIVE_DK))
    elif muted:
        item.setForeground(QColor(C.TEXT_MUTED))
    return item


class _FractionBar(QFrame):
    """Horizontal stacked bar of detailed sub-class segments."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setStyleSheet(
            f"_FractionBar {{ background: {C.BG_LOW};"
            f" border: 1px solid {C.BORDER_DK}; border-radius: 6px; }}"
        )
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(1, 1, 1, 1)
        self._lay.setSpacing(1)

    def set_fractions(self, items: List[tuple]) -> None:
        # items: list of (label, pct)
        while self._lay.count():
            child = self._lay.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

        present = [(lbl, pct) for lbl, pct in items if pct > 0.05]
        for lbl, pct in present:
            seg = QLabel(f"{lbl} {pct:.0f}%" if pct >= 8 else "")
            seg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            seg.setToolTip(f"{lbl}: {pct:.1f}%")
            seg.setStyleSheet(
                f"QLabel {{ background: {_band_color(lbl)}; color: #3a2e1c;"
                f" font-family: '{F.UI}'; font-size: {F.SZ_SM}pt; font-weight: 800; }}"
            )
            self._lay.addWidget(seg, max(1, int(round(pct * 10))))


# ─────────────────────────────────────────────────────────────────────────────
# Metric strip
# ─────────────────────────────────────────────────────────────────────────────

class _MetricStrip(QFrame):
    """Top strip of headline metrics (sample, soil, D50, Cu, K geo. mean)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"_MetricStrip {{ background: {C.BG_RAISED};"
            f" border: 1px solid {C.BORDER}; border-radius: 6px; }}"
        )
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        self._values: dict[str, QLabel] = {}
        self._subs: dict[str, QLabel] = {}
        for spec_key, label, grow in (
            ("sample", "Sample", True),
            ("soil", "Soil", False),
            ("d50", "D50", False),
            ("cu", "Cu", False),
            ("k", "K geo. mean", False),
        ):
            self._lay.addWidget(self._make_cell(spec_key, label, grow))

    def _make_cell(self, spec_key: str, label: str, grow: bool) -> QWidget:
        cell = QFrame()
        cell.setStyleSheet(f"QFrame {{ border: none; border-right: 1px solid {C.BORDER}; }}")
        v = QVBoxLayout(cell)
        v.setContentsMargins(12, 7, 12, 7)
        v.setSpacing(1)
        cap = QLabel(label.upper())
        cap.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f" font-weight: 800; letter-spacing: 0.6px; border: none;"
        )
        value = QLabel("—")
        value.setStyleSheet(
            f"color: {C.TEXT}; font-family: '{F.MONO}'; font-size: {F.SZ_LG}pt;"
            f" font-weight: 700; border: none;"
        )
        sub = QLabel("")
        sub.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}'; font-size: {F.SZ_SM}pt;"
            f" border: none;"
        )
        v.addWidget(cap)
        v.addWidget(value)
        v.addWidget(sub)
        self._values[spec_key] = value
        self._subs[spec_key] = sub
        if grow:
            cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return cell

    def update_metric(self, key: str, value: str, sub: str = "",
                      color: Optional[str] = None) -> None:
        if key not in self._values:
            return
        self._values[key].setText(value)
        if color:
            self._values[key].setStyleSheet(
                f"color: {color}; font-family: '{F.MONO}'; font-size: {F.SZ_LG}pt;"
                f" font-weight: 700; border: none;"
            )
        self._subs[key].setText(sub)


# ─────────────────────────────────────────────────────────────────────────────
# Statistics tab
# ─────────────────────────────────────────────────────────────────────────────

class StatisticsTab(QWidget):
    """Per-sample descriptive statistics summary (read-only)."""

    statistics_updated = pyqtSignal()

    def __init__(self, dataset: GrainSizeData, parent=None):
        super().__init__(parent)
        self.dataset = dataset
        self.k_results: Optional[List[KCalculationResult]] = None
        self._scheme = ISO14688
        self._calc = KCalculator()

        self.temperature = dataset.temperature
        self.porosity = (
            dataset.current_porosity
            if getattr(dataset, "current_porosity", None) is not None
            else dataset.porosity
        )

        self._build_ui()
        self.update_display()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(8, 8, 8, 8)
        col.setSpacing(8)

        # 1. Metric strip
        self.info_bar = _MetricStrip()
        col.addWidget(self.info_bar)

        # 2. Key grain distribution
        self.distribution_card = self._build_distribution_card()
        col.addWidget(self.distribution_card)

        # 3. Classification & fractions
        self.classification_card = self._build_classification_card()
        col.addWidget(self.classification_card)

        # 4. Hydraulic conductivity summary
        self.k_summary_card = self._build_k_summary_card()
        col.addWidget(self.k_summary_card)

        # 5. Interpretation + data support + context (three columns)
        col.addLayout(self._build_lower_row())

        # 6. Calculation internals (collapsed by default)
        self.internals_section = self._build_internals_section()
        col.addWidget(self.internals_section)

        col.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _build_distribution_card(self) -> _Card:
        card = _Card("Key Grain Distribution", "mm")

        # D-facts (D10/D50/D60/D90)
        facts = QHBoxLayout()
        facts.setSpacing(8)
        self._fact_labels: dict[int, QLabel] = {}
        for p, sub in ((10, "effective size"), (50, "median size"),
                       (60, "uniformity basis"), (90, "coarse tail")):
            facts.addWidget(self._make_fact(p, sub))
        card.add_layout(facts)

        # "Used by" table
        self._used_by_table = _make_table(["Percentile", "Size", "Used by"])
        card.add(self._used_by_table)

        # Full percentile grid
        grid_host = QWidget()
        self._pct_grid = QGridLayout(grid_host)
        self._pct_grid.setContentsMargins(0, 0, 0, 0)
        self._pct_grid.setSpacing(1)
        self._pct_value_labels: dict[int, QLabel] = {}
        for idx, p in enumerate(_STD_PERCENTILES):
            r, c = divmod(idx, 6)
            self._pct_grid.addWidget(self._make_pct_cell(p), r, c)
        card.add(grid_host)
        return card

    def _make_fact(self, percentile: int, sub: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {C.BG}; border: 1px solid {C.BORDER};"
            f" border-radius: 6px; }}"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(9, 8, 9, 8)
        v.setSpacing(1)
        cap = QLabel(f"D{percentile}")
        cap.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f" font-weight: 800; border: none;"
        )
        value = QLabel("—")
        value.setStyleSheet(
            f"color: {C.TEXT}; font-family: '{F.MONO}'; font-size: 16pt;"
            f" font-weight: 700; border: none;"
        )
        sublbl = QLabel(sub)
        sublbl.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f" border: none;"
        )
        v.addWidget(cap)
        v.addWidget(value)
        v.addWidget(sublbl)
        self._fact_labels[percentile] = value
        return frame

    def _make_pct_cell(self, percentile: int) -> QFrame:
        is_key = percentile in _KEY_PERCENTILES
        frame = QFrame()
        bg = "rgba(107,142,35,0.06)" if is_key else "#fffdf8"
        frame.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {C.BORDER}; }}"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(7, 5, 7, 5)
        v.setSpacing(2)
        cap = QLabel(f"D{percentile}")
        cap.setStyleSheet(
            f"color: {C.OLIVE_DK if is_key else C.TEXT_MUTED};"
            f" font-family: '{F.MONO}'; font-size: {F.SZ_SM}pt; font-weight: 800;"
            f" border: none;"
        )
        value = QLabel("—")
        value.setStyleSheet(
            f"color: {C.TEXT}; font-family: '{F.MONO}'; font-size: {F.SZ_MD}pt;"
            f" font-weight: 600; border: none;"
        )
        v.addWidget(cap)
        v.addWidget(value)
        self._pct_value_labels[percentile] = value
        return frame

    def _build_classification_card(self) -> _Card:
        card = _Card("Classification & Fractions", "")

        self._class_label = self._make_def_row("Label")
        self._descriptor_label = self._make_def_row("Descriptor")
        card.add(self._class_label["row"])
        card.add(self._descriptor_label["row"])

        self._fraction_bar = _FractionBar()
        card.add(self._fraction_bar)

        self._detail_table = _make_table(["Sub-class", "Range (mm)", "%"])
        card.add(self._detail_table)

        # Cu / Cc / sorting / span strip
        strip = QHBoxLayout()
        strip.setSpacing(8)
        self._grad_labels: dict[str, QLabel] = {}
        self._grad_subs: dict[str, QLabel] = {}
        for key, label in (("cu", "Cu"), ("cc", "Cc"),
                           ("sorting", "Sorting"), ("span", "Span")):
            strip.addWidget(self._make_grad_stat(key, label))
        card.add_layout(strip)
        return card

    def _make_def_row(self, caption: str) -> dict:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        cap = QLabel(caption)
        cap.setFixedWidth(90)
        cap.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f" font-weight: 800; letter-spacing: 0.4px;"
        )
        value = QLabel("—")
        value.setWordWrap(True)
        value.setStyleSheet(
            f"color: {C.TEXT}; font-family: '{F.UI}'; font-size: {F.SZ_MD}pt;"
            f" font-weight: 600;"
        )
        h.addWidget(cap)
        h.addWidget(value, 1)
        return {"row": row, "caption": cap, "value": value}

    def _make_grad_stat(self, key: str, label: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {C.BG}; border: 1px solid {C.BORDER};"
            f" border-radius: 6px; }}"
        )
        h = QHBoxLayout(frame)
        h.setContentsMargins(10, 6, 10, 6)
        h.setSpacing(8)
        left = QVBoxLayout()
        left.setSpacing(1)
        cap = QLabel(label)
        cap.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f" font-weight: 800; border: none;"
        )
        sub = QLabel("")
        sub.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f" border: none;"
        )
        left.addWidget(cap)
        left.addWidget(sub)
        value = QLabel("—")
        value.setStyleSheet(
            f"color: {C.TEXT}; font-family: '{F.MONO}'; font-size: 15px;"
            f" font-weight: 700; border: none;"
        )
        h.addLayout(left)
        h.addStretch()
        h.addWidget(value)
        self._grad_labels[key] = value
        self._grad_subs[key] = sub
        return frame

    def _build_k_summary_card(self) -> _Card:
        card = _Card("Hydraulic Conductivity Summary", "All active / OK only")
        self._k_table = _make_table(["Statistic", "m/s", "cm/s", "m/d"])
        self._k_table.setToolTip(
            "Statistics use positive OK results from the active workspace K methods."
        )
        card.add(self._k_table)
        self._k_note = QLabel("Calculate K-values to see the aggregate summary.")
        self._k_note.setWordWrap(True)
        self._k_note.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f" font-style: italic;"
        )
        card.add(self._k_note)
        return card

    def _build_lower_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        # Interpretation
        self.interpretation_card = _Card("Interpretation", "")
        self._interp_host = QVBoxLayout()
        self._interp_host.setSpacing(6)
        self.interpretation_card.add_layout(self._interp_host)
        row.addWidget(self.interpretation_card, 5)

        # Data support
        self.quality_card = _Card("Data Support", "curve coverage")
        self._support_table = _make_table(["Check", "Value"])
        self.quality_card.add(self._support_table)
        row.addWidget(self.quality_card, 3)

        # Calculation context
        self.context_card = _Card("Calculation Context", "")
        self._context_table = _make_table(["Parameter", "Value"])
        self.context_card.add(self._context_table)
        row.addWidget(self.context_card, 3)
        return row

    def _build_internals_section(self) -> CollapsibleSection:
        section = CollapsibleSection(
            "Calculation Internals", "fa6s.gears",
            CollapsibleSection.EARTH, expanded=False,
        )
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 6, 0, 0)
        grid.setSpacing(8)

        self._const_table = _make_table(["Physical constant", "Value"])
        self._diam_table = _make_table(["Effective diameter", "Value"])
        self._phi_table = _make_table(["Sorting / φ", "Value"])
        self._poro_table = _make_table(["Porosity function", "Value"])

        grid.addWidget(self._wrap_subcard(TITLE_CONSTANTS, self._const_table), 0, 0)
        grid.addWidget(self._wrap_subcard(TITLE_DIAMETERS, self._diam_table), 0, 1)
        grid.addWidget(self._wrap_subcard(TITLE_SORTING, self._phi_table), 1, 0)
        grid.addWidget(self._wrap_subcard(TITLE_POROSITY, self._poro_table), 1, 1)
        section.add_widget(grid_host)
        return section

    def _wrap_subcard(self, title: str, table: QTableWidget) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: #fffdf8; border: 1px solid {C.BORDER};"
            f" border-radius: 6px; }}"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(8, 6, 8, 8)
        v.setSpacing(4)
        cap = QLabel(title.upper())
        cap.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.UI}'; font-size: {F.SZ_SM}pt;"
            f" font-weight: 800; letter-spacing: 0.5px; border: none;"
        )
        v.addWidget(cap)
        v.addWidget(table)
        return frame

    # ── Data plumbing ──────────────────────────────────────────────────────

    def _grain_data(self) -> dict:
        return {
            "particle_sizes": list(self.dataset.particle_sizes or []),
            "percent_passing": list(self.dataset.percent_passing or []),
        }

    def _percentiles(self, grain_data: dict) -> dict:
        out: dict[int, float] = {}
        for p in _STD_PERCENTILES:
            value = self._calc._interpolate_percentile(grain_data, float(p))
            if value:
                out[p] = value
        return out

    def _k_summary(self) -> Optional[AggregateStats]:
        if not self.k_results:
            return None
        summary = build_k_result_summary(
            self.k_results,
            dataset_name=self.dataset.sample_name,
            group_name=getattr(self.dataset, "group_name", "Ungrouped"),
        )
        if summary.geometric_mean_m_s is None:
            return None
        return summary

    # ── Public API (kept stable for callers) ───────────────────────────────

    def set_scheme(self, scheme) -> None:
        self._scheme = scheme
        self.update_display()

    def set_k_results(self, results: List[KCalculationResult]) -> None:
        self.k_results = results
        self.update_display()

    def update_display(self) -> None:
        grain_data = self._grain_data()
        percentiles = self._percentiles(grain_data)
        result = self.dataset.classify(scheme=self._scheme)
        summary = self._k_summary()

        self._update_metric_strip(percentiles, result, summary)
        self._update_distribution(percentiles)
        self._update_classification(result, percentiles)
        self._update_k_summary(summary)
        self._update_interpretation(result, summary)
        self._update_data_support()
        self._update_context(summary)
        self._update_internals()

        self.statistics_updated.emit()

    # ── Section updates ────────────────────────────────────────────────────

    def _update_metric_strip(self, percentiles, result, summary) -> None:
        n_points = len(self.dataset.particle_sizes or [])
        self.info_bar.update_metric(
            "sample", self.dataset.sample_name, f"{n_points} gradation points")
        soil_sub = result.detailed_class.lower() if result.detailed_class != "—" else result.scheme.name
        self.info_bar.update_metric("soil", result.label or "—", soil_sub, color=C.OLIVE_DK)

        d50 = percentiles.get(50)
        self.info_bar.update_metric("d50", f"{d50:.3f} mm" if d50 else "—",
                                    result.detailed_class.lower() if result.detailed_class != "—" else "")

        d10, d60 = percentiles.get(10), percentiles.get(60)
        cu = d60 / d10 if d10 and d60 else None
        self.info_bar.update_metric("cu", f"{cu:.2f}" if cu else "—",
                                    result.cu_label if cu else "")

        if summary:
            self.info_bar.update_metric(
                "k", _fmt_sci(summary.geometric_mean_m_s),
                f"m/s · {summary.included_count} OK methods", color=C.K_BLUE)
        else:
            self.info_bar.update_metric("k", "—", "not calculated")

    def _update_distribution(self, percentiles) -> None:
        for p, lbl in self._fact_labels.items():
            value = percentiles.get(p)
            lbl.setText(f"{value:.3f}" if value else "—")

        self._used_by_table.setRowCount(0)
        for p, used_by in _PCT_USED_BY:
            value = percentiles.get(p)
            row = self._used_by_table.rowCount()
            self._used_by_table.insertRow(row)
            is_key = p in _KEY_PERCENTILES
            self._used_by_table.setItem(row, 0, _cell(f"D{p}", key=is_key))
            self._used_by_table.setItem(
                row, 1, _cell(f"{value:.3f} mm" if value else "—", align_right=True, key=is_key))
            self._used_by_table.setItem(row, 2, _cell(used_by, align_right=True))
        _fit_table_height(self._used_by_table)

        for p, lbl in self._pct_value_labels.items():
            value = percentiles.get(p)
            lbl.setText(f"{value:.3f}" if value else "—")

    def _update_classification(self, result, percentiles) -> None:
        detailed = result.detailed_fractions or ()

        self.classification_card.set_meta(self._scheme_short_name(result.scheme))
        self._class_label["value"].setText(result.label or "—")

        d50 = percentiles.get(50)
        d10 = percentiles.get(10)
        d60 = percentiles.get(60)
        cu = d60 / d10 if d10 and d60 else None
        descriptor = sedimentology_descriptor(result.fractions, d50, cu, self._scheme)
        self._descriptor_label["value"].setText(descriptor or "—")

        self._fraction_bar.set_fractions([(d.label, d.pct) for d in detailed])

        self._detail_table.setRowCount(0)
        for d in detailed:
            row = self._detail_table.rowCount()
            self._detail_table.insertRow(row)
            is_dom = d.label == result.detailed_class
            zero = d.pct <= 0.0
            self._detail_table.setItem(row, 0, _cell(d.label, key=is_dom, muted=zero))
            self._detail_table.setItem(
                row, 1, _cell(self._range_text(d), align_right=True, muted=True))
            self._detail_table.setItem(
                row, 2, _cell(f"{d.pct:.1f}", align_right=True, key=is_dom, muted=zero))
        _fit_table_height(self._detail_table)

        d5 = percentiles.get(5)
        d16 = percentiles.get(16)
        d30 = percentiles.get(30)
        d84 = percentiles.get(84)
        d95 = percentiles.get(95)

        cc = (d30 * d30) / (d10 * d60) if d10 and d30 and d60 else None
        sorting = math.sqrt(d84 / d16) if d16 and d84 and d16 > 0 else None
        span = d95 / d5 if d5 and d95 and d5 > 0 else None

        self._set_grad("cu", cu, result.cu_label)
        self._set_grad("cc", cc, result.cc_label)
        self._set_grad("sorting", sorting, self._sorting_label(sorting))
        self._set_grad("span", span, "D95/D5")

    @staticmethod
    def _scheme_short_name(scheme) -> str:
        key = getattr(scheme, "key", "")
        if key == "iso14688":
            return "ISO 14688"
        if key == "uscs":
            return "USCS"
        return getattr(scheme, "name", "scheme")

    @staticmethod
    def _range_text(d) -> str:
        if d.lower_mm <= 0:
            return f"< {d.upper_mm:g}"
        return f"{d.lower_mm:g}–{d.upper_mm:g}"

    @staticmethod
    def _sorting_label(sigma: Optional[float]) -> str:
        if sigma is None:
            return ""
        if sigma < 2:
            return "well sorted"
        if sigma < 4:
            return "moderately sorted"
        return "poorly sorted"

    def _set_grad(self, key: str, value: Optional[float], sub: str) -> None:
        self._grad_labels[key].setText(f"{value:.2f}" if value else "—")
        self._grad_subs[key].setText(sub if value else "")

    def _update_k_summary(self, summary) -> None:
        self._k_table.setRowCount(0)
        self.k_summary_card.set_meta("All active / OK only")
        if not summary:
            self._k_table.hide()
            self._k_note.setText(
                "Calculate K-values to see the OK-only aggregate summary. "
                "The active method set is controlled under Analysis > Choose K Methods."
            )
            self._k_note.show()
            return
        self._k_note.setText(
            f"Uses {summary.included_count} of {summary.total_cells} active methods: "
            "positive OK results only. Warnings and errors are excluded. "
            "Change the active set under Analysis > Choose K Methods."
        )
        self._k_note.show()
        self._k_table.show()

        rows = [
            ("Geometric mean", summary.geometric_mean_m_s, True),
            ("Arithmetic mean", summary.arithmetic_mean_m_s, False),
            ("Median", summary.median_m_s, False),
        ]
        for name, value, key in rows:
            if value is None:
                continue
            r = self._k_table.rowCount()
            self._k_table.insertRow(r)
            self._k_table.setItem(r, 0, _cell(name, key=key))
            self._k_table.setItem(r, 1, _cell(_fmt_sci(value), align_right=True, key=key))
            self._k_table.setItem(r, 2, _cell(_fmt_sci(value * 100), align_right=True))
            self._k_table.setItem(r, 3, _cell(f"{value * 86400:.2f}", align_right=True))

        if summary.min_m_s is not None and summary.max_m_s is not None:
            r = self._k_table.rowCount()
            self._k_table.insertRow(r)
            self._k_table.setItem(r, 0, _cell("Range"))
            self._k_table.setItem(
                r, 1, _cell(f"{summary.min_m_s:.2e} – {summary.max_m_s:.2e}", align_right=True))
            self._k_table.setItem(
                r, 2, _cell(f"{summary.min_m_s * 100:.2e} – {summary.max_m_s * 100:.2e}", align_right=True))
            self._k_table.setItem(
                r, 3, _cell(f"{summary.min_m_s * 86400:.1f} – {summary.max_m_s * 86400:.1f}", align_right=True))

        if summary.ln_std_dev is not None:
            r = self._k_table.rowCount()
            self._k_table.insertRow(r)
            self._k_table.setItem(r, 0, _cell("ln(K) std. dev."))
            self._k_table.setItem(r, 1, _cell(f"{summary.ln_std_dev:.2f}", align_right=True))
            self._k_table.setItem(r, 2, _cell("log spread", align_right=True, muted=True))
            self._k_table.setItem(r, 3, _cell("dimensionless", align_right=True, muted=True))

        r = self._k_table.rowCount()
        self._k_table.insertRow(r)
        excluded = summary.warning_count + summary.error_count
        self._k_table.setItem(r, 0, _cell("Included OK methods"))
        self._k_table.setItem(
            r, 1, _cell(f"{summary.included_count} / {summary.total_cells}", align_right=True))
        self._k_table.setItem(
            r, 2, _cell(f"{summary.warning_count} warnings", align_right=True, muted=True))
        self._k_table.setItem(
            r, 3, _cell(f"{summary.error_count} errors", align_right=True, muted=True))
        _fit_table_height(self._k_table)

    def _update_interpretation(self, result, summary) -> None:
        while self._interp_host.count():
            child = self._interp_host.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

        f = result.fractions
        insights: List[tuple] = []
        if result.label and result.label != "Insufficient data for classification":
            insights.append((
                "Composition",
                f"{result.label}. Sand {f.sand_pct:.0f}%, fines {f.fines_pct:.0f}%, "
                f"gravel {f.gravel_pct:.0f}%.",
            ))
        if summary and summary.ln_std_dev is not None and summary.included_count:
            spread = ("narrow" if summary.ln_std_dev < 0.5
                      else "moderate" if summary.ln_std_dev < 1.0 else "wide")
            insights.append((
                "Method spread",
                f"ln(K) spread is {summary.ln_std_dev:.2f} ({spread}) across "
                f"{summary.included_count} included methods. The geometric mean is "
                f"the primary aggregate.",
            ))
            excluded = summary.warning_count + summary.error_count
            if excluded:
                insights.append((
                    "Excluded methods",
                    f"{excluded} method(s) excluded from the means — see the Results "
                    f"tab for the reason per method.",
                ))
        elif not summary:
            insights.append((
                "Hydraulic conductivity",
                "Calculate K-values to see the aggregate summary and method spread.",
            ))

        for title, body in insights:
            self._interp_host.addWidget(self._make_insight(title, body))

    def _make_insight(self, title: str, body: str) -> QWidget:
        host = QWidget()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-family: '{F.UI}'; font-size: {F.SZ_MD}pt;"
            f" font-weight: 800;"
        )
        body_lbl = QLabel(body)
        body_lbl.setWordWrap(True)
        body_lbl.setStyleSheet(
            f"color: {C.TEXT_MID}; font-family: '{F.UI}'; font-size: {F.SZ_MD}pt;"
        )
        v.addWidget(title_lbl)
        v.addWidget(body_lbl)
        return host

    def _update_data_support(self) -> None:
        sizes = [float(v) for v in (self.dataset.particle_sizes or []) if v is not None]
        passing = [float(v) for v in (self.dataset.percent_passing or []) if v is not None]
        messages = getattr(self.dataset, "validation_messages", []) or []
        errors = sum(1 for m in messages
                     if getattr(getattr(m, "severity", None), "value", "") == "error")

        rows = []
        if sizes:
            rows.append(("Particle-size range", f"{min(sizes):.4g} – {max(sizes):.4g} mm"))
        else:
            rows.append(("Particle-size range", "—"))
        if passing:
            rows.append(("Percent-passing range", f"{min(passing):.1f} – {max(passing):.1f} %"))
        else:
            rows.append(("Percent-passing range", "—"))
        rows.append(("Point count", str(len(sizes))))
        rows.append(("Validation messages",
                     f"{errors} error{'s' if errors != 1 else ''}" if errors
                     else f"{len(messages)} note{'s' if len(messages) != 1 else ''}"))

        self._fill_kv(self._support_table, rows)

    def _update_context(self, summary) -> None:
        effective_porosity = (
            self.dataset.effective_porosity()
            if hasattr(self.dataset, "effective_porosity")
            else self.porosity
        )
        if effective_porosity is not None:
            self.porosity = effective_porosity

        rows = [("Temperature", f"{self.temperature:.1f} °C")]
        if effective_porosity is None:
            rows.append(("Porosity", "—"))
        else:
            rows.append(("Porosity", f"{effective_porosity:.4f}"))
        if hasattr(self.dataset, "porosity_source_label"):
            rows.append(("Porosity source", self.dataset.porosity_source_label()))
        if summary:
            rows.append(("Permeability class", _perm_class(summary.geometric_mean_m_s)))
        else:
            rows.append(("Permeability class", "Not calculated"))

        self._fill_kv(self._context_table, rows)

    def _update_internals(self) -> None:
        internals = compute_calculation_internals(
            self.dataset.particle_sizes,
            self.dataset.percent_passing,
            self.temperature,
            self.porosity,
        )
        self._fill_kv(self._const_table, list(internals.physical_constants.rows))
        self._fill_kv(self._diam_table, list(internals.effective_diameters.rows))
        self._fill_kv(self._phi_table, list(internals.phi_folk_ward.rows))
        self._fill_kv(self._poro_table, list(internals.porosity_functions.rows))

    def _fill_kv(self, table: QTableWidget, rows: List[tuple]) -> None:
        table.setRowCount(0)
        for name, value in rows:
            r = table.rowCount()
            table.insertRow(r)
            table.setItem(r, 0, _cell(name))
            table.setItem(r, 1, _cell(value, align_right=True))
        _fit_table_height(table)
