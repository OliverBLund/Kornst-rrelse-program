"""
Dataset selection dialog for comparison tab when many datasets are loaded.
"""

from __future__ import annotations

import math
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.dialog_chrome import make_dialog_footer, make_dialog_header
from gui.theme import C, F, SZ, icon as _icon
from k_aggregation import dataset_group_name, normalize_group_name
from qt_chrome.frameless_dialog_base import FramelessDialogBase


class DatasetSelectionDialog(FramelessDialogBase):
    """Dialog for selecting datasets to compare when many datasets are available."""

    def __init__(
        self,
        dataset_tabs: List,
        currently_selected: Optional[List] = None,
        *,
        title: str = "Select Datasets for Comparison",
        subtitle: str = "Choose which samples to include in the comparison view",
        action_text: str = "Compare Selected",
        action_icon: str = "fa6s.code-compare",
        minimum_selection: int = 2,
        allow_grouping: bool = False,
        parent=None,
    ):
        super().__init__(parent, default_mode="auto")
        self.dataset_tabs = dataset_tabs
        self.currently_selected = currently_selected or []
        self.selected_tabs: List = []
        self._rows: list[_DatasetRow] = []
        self._title = title
        self._subtitle = subtitle
        self._action_text = action_text
        self._action_icon = action_icon
        self._minimum_selection = max(1, int(minimum_selection))
        self._allow_grouping = bool(allow_grouping)

        self.setWindowTitle(self._title)
        self.setModal(True)
        self.resize(680 if self._allow_grouping else 540, 500)
        self.setMinimumWidth(640 if self._allow_grouping else 540)

        self._build_ui()
        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )
        self._populate()

    # ── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header_widget = make_dialog_header(
            self._title,
            self._subtitle,
            fa_icon="fa6s.list-check",
            close_fn=self.reject,
        )
        root.addWidget(self._header_widget)

        # ── Toolbar (search + quick buttons) ──────────────────────────────
        toolbar = QWidget()
        toolbar.setStyleSheet(
            f"background: {C.BG_LOW}; border-bottom: 1px solid {C.BORDER};"
        )
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(12, 8, 12, 8)
        tb_lay.setSpacing(8)

        # Search field with icon
        search_wrap = QWidget()
        search_wrap.setStyleSheet("background: transparent;")
        sw_lay = QHBoxLayout(search_wrap)
        sw_lay.setContentsMargins(0, 0, 0, 0)
        sw_lay.setSpacing(0)

        srch_ic = QLabel()
        try:
            srch_ic.setPixmap(_icon("fa6s.magnifying-glass", C.TEXT_MUTED).pixmap(11, 11))
        except Exception:
            srch_ic.setText("🔍")
        srch_ic.setStyleSheet("background: transparent; padding: 0 4px;")

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Filter by name, D50, K...")
        self._search_box.setFixedHeight(28)
        self._search_box.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,255,255,.7); border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; font-family: '{F.UI}'; "
            f"font-size: {F.SZ_MD}pt; color: {C.TEXT}; padding: 0 8px; }}"
            f"QLineEdit:focus {{ border-color: {C.OLIVE}; background: white; }}"
        )
        self._search_box.textChanged.connect(self._filter)

        sw_lay.addWidget(srch_ic)
        sw_lay.addWidget(self._search_box)
        tb_lay.addWidget(search_wrap, 1)

        # Quick selection buttons
        for label, fn in [("All", self._select_all), ("None", self._select_none),
                          ("Invert", self._invert)]:
            btn = _qs_btn(label, fn)
            tb_lay.addWidget(btn)

        root.addWidget(toolbar)

        # ── Dataset list ──────────────────────────────────────────────────
        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._list_scroll.setStyleSheet(
            f"QScrollArea {{ background: {C.BG}; border: none; }}"
            f"QScrollBar:vertical {{ background: transparent; width: 10px; margin: 6px 2px; }}"
            f"QScrollBar::handle:vertical {{ background: {C.AMBER}; min-height: 28px; border-radius: 4px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
        )
        self._list_host = QWidget()
        self._list_host.setStyleSheet(f"background: {C.BG};")
        self._rows_layout = QVBoxLayout(self._list_host)
        self._rows_layout.setContentsMargins(0, 4, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch(1)
        self._list_scroll.setWidget(self._list_host)
        root.addWidget(self._list_scroll, 1)

        # ── Selection bar ─────────────────────────────────────────────────
        sel_bar = QWidget()
        sel_bar.setStyleSheet(
            f"background: {C.BG_RAISED}; border-top: 1px solid {C.BORDER};"
        )
        sb_lay = QHBoxLayout(sel_bar)
        sb_lay.setContentsMargins(14, 7, 14, 7)
        sb_lay.setSpacing(8)

        self._sel_count_badge = QLabel("0 selected")
        self._sel_count_badge.setStyleSheet(
            f"background: rgba(107,142,35,.1); color: {C.OLIVE}; "
            f"border: 1px solid rgba(107,142,35,.25); border-radius: 99px; "
            f"padding: 2px 8px; font-family: '{F.MONO}'; font-size: {F.SZ_SM}pt; "
            "font-weight: 500;"
        )
        sb_lay.addWidget(self._sel_count_badge)

        self._sel_hint = QLabel(f"of {len(self.dataset_tabs)} datasets")
        self._sel_hint.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; background: transparent;"
        )
        sb_lay.addWidget(self._sel_hint)
        sb_lay.addStretch(1)

        root.addWidget(sel_bar)

        # ── Footer ────────────────────────────────────────────────────────
        self._footer_widget = make_dialog_footer([
            ("Cancel", self.reject, "secondary"),
            (self._action_text, self.accept, "primary"),
        ])
        btns = self._footer_widget.findChildren(QPushButton)
        self._compare_btn = next(
            (b for b in btns if b.text() == self._action_text),
            None,
        )
        if self._compare_btn:
            try:
                self._compare_btn.setIcon(_icon(self._action_icon, "#ffffff"))
            except Exception:
                pass
            self._compare_btn.setEnabled(False)

        root.addWidget(self._footer_widget)

    # ── Population ──────────────────────────────────────────────────────────

    def _populate(self):
        for tab in self.dataset_tabs:
            row = _DatasetRow(tab, checked=tab in self.currently_selected, allow_grouping=self._allow_grouping)
            row.toggled.connect(self._on_selection_changed)
            self._rows.append(row)
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
        self._on_selection_changed()

    # ── Filtering ───────────────────────────────────────────────────────────

    def _filter(self, text: str):
        text = text.lower().strip()
        for row in self._rows:
            row.setVisible(row.matches_filter(text))

    # ── Selection helpers ───────────────────────────────────────────────────

    def _select_all(self):
        for row in self._rows:
            if row.isVisible():
                row.set_checked(True, emit_signal=False)
        self._on_selection_changed()

    def _select_none(self):
        for row in self._rows:
            if row.isVisible():
                row.set_checked(False, emit_signal=False)
        self._on_selection_changed()

    def _invert(self):
        for row in self._rows:
            if row.isVisible():
                row.set_checked(not row.is_checked(), emit_signal=False)
        self._on_selection_changed()

    def _on_selection_changed(self):
        count = len([row for row in self._rows if row.is_checked()])
        self._sel_count_badge.setText(f"{count} selected")
        if self._compare_btn:
            self._compare_btn.setEnabled(count >= self._minimum_selection)

    # ── Accept / reject ─────────────────────────────────────────────────────

    def accept(self):
        selected_rows = [row for row in self._rows if row.is_checked()]
        if len(selected_rows) < self._minimum_selection:
            noun = "dataset" if self._minimum_selection == 1 else "datasets"
            QMessageBox.warning(
                self, "Invalid Selection",
                f"Please select at least {self._minimum_selection} {noun}."
            )
            return
        self.selected_tabs = [row.tab for row in selected_rows]
        super().accept()

    def get_selected_tabs(self) -> List:
        return self.selected_tabs

    def get_group_assignments(self) -> dict:
        return {row.tab: row.group_name() for row in self._rows}


class _DatasetRow(QFrame):
    """Concept-style dataset row used in the comparison selection dialog."""

    toggled = pyqtSignal()

    def __init__(self, tab, checked: bool = False, *, allow_grouping: bool = False, parent=None):
        super().__init__(parent)
        self.tab = tab
        self._checked = False
        self._allow_grouping = bool(allow_grouping)
        self._group_edit = None
        self._status_color = _dataset_status_color(tab)
        self._build_ui()
        self._search_text = (
            f"{self._label.text()} {self._meta.text()} {self.group_name()}".strip().lower()
        )
        self._sync_styles()
        if checked:
            self.set_checked(True, emit_signal=False)

    def _build_ui(self):
        self.setObjectName("datasetSelectionRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 7, 14, 7)
        lay.setSpacing(10)

        self._checkbox = QFrame()
        self._checkbox.setFixedSize(15, 15)
        cb_lay = QHBoxLayout(self._checkbox)
        cb_lay.setContentsMargins(0, 0, 0, 0)
        self._checkmark = QLabel("✓")
        self._checkmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._checkmark.setFont(QFont(F.UI, F.SZ_XS))
        cb_lay.addWidget(self._checkmark)
        lay.addWidget(self._checkbox, 0, Qt.AlignmentFlag.AlignVCenter)

        self._icon_box = QFrame()
        self._icon_box.setFixedSize(26, 26)
        icon_lay = QHBoxLayout(self._icon_box)
        icon_lay.setContentsMargins(0, 0, 0, 0)
        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lay.addWidget(self._icon_label)
        lay.addWidget(self._icon_box, 0, Qt.AlignmentFlag.AlignVCenter)

        name_col = QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(1)

        self._label = QLabel(self.tab.get_dataset_name())
        self._label.setFont(QFont(F.UI, F.SZ_MD))
        self._label.setStyleSheet("background: transparent; font-weight: 500;")
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        name_col.addWidget(self._label)

        self._meta = QLabel(_dataset_meta_text(self.tab))
        self._meta.setFont(QFont(F.MONO, F.SZ_XS))
        self._meta.setStyleSheet(
            f"color: {C.TEXT_MUTED}; background: transparent;"
        )
        self._meta.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        name_col.addWidget(self._meta)
        lay.addLayout(name_col, 1)

        if self._allow_grouping:
            self._group_edit = QLineEdit()
            self._group_edit.setPlaceholderText("Group")
            self._group_edit.setText(dataset_group_name(self.tab.get_dataset()))
            self._group_edit.setFixedWidth(130)
            self._group_edit.setFixedHeight(26)
            self._group_edit.setStyleSheet(
                f"QLineEdit {{ background: rgba(255,255,255,.70); border: 1px solid {C.BORDER}; "
                f"border-radius: {SZ.BORDER_RADIUS}px; font-family: '{F.UI}'; "
                f"font-size: {F.SZ_SM}pt; color: {C.TEXT}; padding: 0 7px; }}"
                f"QLineEdit:focus {{ border-color: {C.OLIVE}; background: white; }}"
            )
            lay.addWidget(self._group_edit, 0, Qt.AlignmentFlag.AlignVCenter)

        self._status_dot = QLabel()
        self._status_dot.setFixedSize(7, 7)
        self._status_dot.setStyleSheet(
            f"background: {self._status_color}; border-radius: 3px;"
        )
        lay.addWidget(self._status_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        for widget in (
            self._checkbox,
            self._checkmark,
            self._icon_box,
            self._icon_label,
            self._label,
            self._meta,
            self._status_dot,
        ):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        if self._group_edit is not None:
            self._group_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def matches_filter(self, text: str) -> bool:
        return not text or text in self._search_text

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool, *, emit_signal: bool = True):
        checked = bool(checked)
        if self._checked == checked:
            return
        self._checked = checked
        self._sync_styles()
        if emit_signal:
            self.toggled.emit()

    def group_name(self) -> str:
        if self._group_edit is None:
            return dataset_group_name(self.tab.get_dataset())
        return normalize_group_name(self._group_edit.text())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_checked(not self._checked)
            event.accept()
            return
        super().mousePressEvent(event)

    def _sync_styles(self):
        row_bg = "rgba(107,142,35,.05)" if self._checked else "transparent"
        row_hover = "rgba(107,142,35,.07)" if self._checked else "rgba(107,142,35,.04)"
        self.setStyleSheet(
            f"QFrame#datasetSelectionRow {{"
            f"background: {row_bg};"
            "border: none;"
            "border-bottom: 1px solid rgba(212,196,168,.35);"
            "}"
            f"QFrame#datasetSelectionRow:hover {{ background: {row_hover}; }}"
        )

        check_bg = C.OLIVE if self._checked else "rgba(255,255,255,.5)"
        check_border = C.OLIVE_DK if self._checked else C.BORDER
        self._checkbox.setStyleSheet(
            f"background: {check_bg}; border: 1.5px solid {check_border}; border-radius: 3px;"
        )
        self._checkmark.setVisible(self._checked)
        self._checkmark.setStyleSheet(
            "background: transparent; color: white; font-weight: 700;"
        )

        icon_bg = "rgba(107,142,35,.12)" if self._checked else "rgba(255,255,255,.4)"
        icon_border = "rgba(107,142,35,.3)" if self._checked else C.BORDER
        icon_color = C.OLIVE if self._checked else C.TEXT_MUTED
        self._icon_box.setStyleSheet(
            f"background: {icon_bg}; border: 1px solid {icon_border}; border-radius: 3px;"
        )
        try:
            self._icon_label.setPixmap(_icon("fa6s.vial", icon_color).pixmap(10, 10))
            self._icon_label.setText("")
        except Exception:
            self._icon_label.setPixmap(None)
            self._icon_label.setText("•")
            self._icon_label.setStyleSheet(
                f"background: transparent; color: {icon_color};"
            )


def _dataset_meta_text(tab) -> str:
    dataset = tab.get_dataset() if hasattr(tab, "get_dataset") else getattr(tab, "dataset", None)
    parts: list[str] = []

    if dataset is not None and hasattr(dataset, "get_d50"):
        d50 = dataset.get_d50()
        if d50 is not None:
            parts.append(f"D50 {d50:.3f} mm")

    k_md = _dataset_k_mean_md(tab)
    if k_md is not None:
        parts.append(f"K̄ {_format_md_value(k_md)} m/d")

    fractions = len(getattr(dataset, "particle_sizes", []) or [])
    if fractions:
        parts.append(f"{fractions} fractions")

    return " · ".join(parts) if parts else "Loaded dataset"


def _dataset_status_color(tab) -> str:
    results = tab.get_results() if hasattr(tab, "get_results") else getattr(tab, "current_results", None)
    if isinstance(results, dict):
        results = list(results.values())
    if not results:
        return C.LED_OK

    for result in results:
        status = getattr(getattr(result, "status", None), "value", getattr(result, "status", ""))
        if "OK" not in str(status) or not getattr(result, "conditions_met", True):
            return C.LED_WARN
    return C.LED_OK


def _dataset_k_mean_md(tab) -> float | None:
    results = tab.get_results() if hasattr(tab, "get_results") else getattr(tab, "current_results", None)
    if isinstance(results, dict):
        results = list(results.values())
    if not results:
        return None

    values: list[float] = []
    for result in results:
        k_value = getattr(result, "k_value", None)
        if k_value is not None and k_value > 0:
            values.append(k_value * 86400.0)

    if not values:
        return None
    return math.exp(sum(math.log(v) for v in values) / len(values))


def _format_md_value(value: float) -> str:
    if value >= 100:
        return f"{value:.0f}"
    if value >= 1:
        return f"{value:.1f}"
    return f"{value:.2f}"


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────────────────────────────────────

def _qs_btn(label: str, fn) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(24)
    btn.setStyleSheet(
        f"QPushButton {{ border: 1px solid {C.BORDER}; "
        f"border-radius: {SZ.BORDER_RADIUS}px; background: transparent; "
        f"color: {C.TEXT_MUTED}; padding: 3px 8px; font-size: {F.SZ_SM}pt; }}"
        f"QPushButton:hover {{ background: {C.BG_RAISED}; border-color: {C.BORDER_DK}; "
        f"color: {C.TEXT}; }}"
    )
    btn.clicked.connect(fn)
    return btn
