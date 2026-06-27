"""
Control panel widget for data import and analysis controls
"""

from collections import deque
from collections.abc import Mapping
import sys
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QGroupBox,
                            QPushButton, QLabel, QLineEdit, QComboBox,
                            QTableWidget, QTableWidgetItem, QTextEdit,
                            QProgressBar, QCheckBox, QSpinBox, QDoubleSpinBox,
                            QListWidget, QListWidgetItem, QSplitter, QWidget,
                            QFileDialog, QMessageBox, QHeaderView, QApplication,
                            QMenu, QDialog, QDialogButtonBox, QScrollArea,
                            QToolButton, QSizePolicy, QTabWidget, QToolTip)
import multiprocessing as mp
import queue
from PyQt6.QtCore import QTimer, QSettings
from data_loader import DataLoader
from gui.column_mapper import ColumnMapperDialog
from gui.dataset_inspector_dialog import DataInspectorDialog
import os
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRectF, QPoint
from PyQt6.QtGui import (QIcon, QFont, QAction, QPainter, QColor,
                         QLinearGradient, QBrush, QPixmap, QPen, QFontMetrics)
from gui.loading_dialog import LoadingDialog
from gui.theme import C, F, SZ, icon
from qt_chrome.frameless_dialog_base import FramelessDialogBase
from load_process_worker import run_batch_import
from import_resolver import manual_mapping_provenance
from grain_classification import (
    ISO14688, GrainClassificationScheme, ClassificationResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR HELPER WIDGETS
# ─────────────────────────────────────────────────────────────────────────────

class _LogoCard(QWidget):
    """Branded logo card — matches _shared.css .sb-logo.

    54px tall, diagonal gradient (160deg), icon container box,
    Playfair Display title, JetBrains Mono subtitle.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(11)

        # Icon container — .logo-mark in CSS
        icon_box = QWidget()
        icon_box.setFixedSize(32, 32)
        icon_box.setStyleSheet(
            "background: rgba(255,255,255,0.13); "
            "border: 1px solid rgba(255,255,255,0.22); "
            f"border-radius: {SZ.BORDER_RADIUS}px;")
        icon_inner = QHBoxLayout(icon_box)
        icon_inner.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel()
        try:
            icon_lbl.setPixmap(
                icon('fa6s.layer-group', C.LOGO_TEXT).pixmap(14, 14))
        except Exception:
            icon_lbl.setText("\u229e")
            icon_lbl.setStyleSheet(f"color: {C.LOGO_TEXT}; font-size: 14px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent;")
        icon_inner.addWidget(icon_lbl)
        row.addWidget(icon_box)

        # Title + subtitle — vertically centered, tightly packed (gap: 2px)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        title = QLabel("GrainSize")
        title.setFont(QFont(F.DISP, F.SZ_2XL, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color: {C.LOGO_TEXT}; background: transparent; "
            "letter-spacing: 0.01em;")
        subtitle = QLabel("ANALYSIS \u00b7 v0.9-\u03b2")
        subtitle.setFont(QFont(F.MONO, F.SZ_XS - 1))
        subtitle.setStyleSheet(
            f"color: {C.LOGO_SUB}; background: transparent; "
            "letter-spacing: 0.06em;")
        text_col.addStretch(1)
        text_col.addWidget(title)
        text_col.addSpacing(2)
        text_col.addWidget(subtitle)
        text_col.addStretch(1)
        row.addLayout(text_col)
        row.addStretch()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Diagonal gradient matching CSS: linear-gradient(160deg, ...)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w * 0.3, h)
        grad.setColorAt(0.0, QColor(C.LOGO_BG_TOP))
        grad.setColorAt(1.0, QColor(C.LOGO_BG))
        painter.fillRect(self.rect(), QBrush(grad))
        painter.end()


class _SectionHeader(QWidget):
    """Section header band — matches _shared.css .sb-sect.

    Uppercase label, optional right-side button.
    """

    def __init__(self, text: str, btn_text: str | None = None,
                 btn_icon: str | None = None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(
            f"background: {C.SB_UP}; "
            f"border-bottom: 1px solid {C.SB_BDR}; "
            f"border-top: 1px solid rgba(255,255,255,0.45);")
        row = QHBoxLayout(self)
        row.setContentsMargins(13, 0, 10, 0)
        lbl = QLabel(text.upper())
        lbl.setFont(QFont(F.UI, 7, QFont.Weight.DemiBold))
        lbl.setStyleSheet(
            f"color: {C.SB_MUTED}; background: transparent; "
            "letter-spacing: 0.09em;")
        row.addWidget(lbl)
        row.addStretch()

        self.action_btn = None
        if btn_text:
            self.action_btn = QPushButton(btn_text)
            if btn_icon:
                try:
                    self.action_btn.setIcon(icon(btn_icon, C.SB_MID))
                except Exception:
                    pass
            self.action_btn.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.35); "
                f"border: 1px solid {C.SB_BDR}; border-radius: {SZ.BORDER_RADIUS}px; "
                f"padding: 2px 7px; font-size: 8pt; color: {C.SB_MID}; }}"
                f"QPushButton:hover {{ background: rgba(255,255,255,0.6); "
                f"border-color: {C.BORDER_DK}; color: {C.SB_TEXT}; }}")
            self.action_btn.setFixedHeight(20)
            self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(self.action_btn)


class _SampleCard(QWidget):
    """Expandable sample card — matches _shared.css .s-item.

    Two states: collapsed (main row only) / expanded (row + detail section).
    Row: icon container + name/meta + status LED + included toggle + expand chevron.
    Active card: sb-act background + 3px olive left accent bar.
    """

    sig_clicked = pyqtSignal(str)          # file_path
    sig_ctx = pyqtSignal(str, object)      # file_path, QPoint (global)
    sig_selected = pyqtSignal(str, bool)   # file_path, is_included
    sig_inspect = pyqtSignal(str)          # file_path
    sig_remap = pyqtSignal(str)            # file_path
    sig_log = pyqtSignal(str)              # file_path
    sig_props = pyqtSignal(str)            # file_path
    sig_remove = pyqtSignal(str)           # file_path

    _STATUS_DOT = {
        'pending': C.SB_MUTED,
        'mapping': C.OLIVE,
        'failed':  C.LED_ERR,
        'review':  C.LED_WARN,
        'loaded':  C.OLIVE,
    }

    def __init__(self, file_path: str, display_name: str, status: str,
                 d50: str = "", k_val: str = "", parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.file_path = file_path
        self._display_name = display_name
        self._status = status
        self._active = False
        self._selected = False
        self._expanded = False
        self._d50 = d50
        self._k_val = k_val
        self._group_name = ""

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.sig_ctx.emit(self.file_path, self.mapToGlobal(pos)))

        main_v = QVBoxLayout(self)
        main_v.setContentsMargins(0, 0, 0, 0)
        main_v.setSpacing(0)

        # ── Main row (always visible) ──
        self._main_row = QWidget()
        row = QHBoxLayout(self._main_row)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(8)

        # Icon container — .s-ic in CSS
        self._icon_box = QWidget()
        self._icon_box.setFixedSize(26, 26)
        self._icon_box.setStyleSheet(
            f"background: rgba(255,255,255,0.3); "
            f"border: 1px solid {C.SB_BDR}; border-radius: 3px;")
        icon_inner = QHBoxLayout(self._icon_box)
        icon_inner.setContentsMargins(0, 0, 0, 0)
        self._icon_lbl = QLabel()
        try:
            self._icon_lbl.setPixmap(
                icon('fa6s.vial', C.SB_MID).pixmap(11, 11))
        except Exception:
            self._icon_lbl.setText("\u2B24")
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet("background: transparent;")
        icon_inner.addWidget(self._icon_lbl)
        row.addWidget(self._icon_box)

        # Name + meta column
        info_host = QWidget()
        info_host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        info_host.setMinimumWidth(0)
        info_col = QVBoxLayout(info_host)
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(1)
        self._name = QLabel(display_name)
        self._name.setTextFormat(Qt.TextFormat.PlainText)
        self._name.setWordWrap(True)
        self._name.setFont(QFont(F.UI, F.SZ_SM, QFont.Weight.Medium))
        self._name.setStyleSheet(f"color: {C.SB_TEXT}; background: transparent;")
        self._name.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._name.setMinimumWidth(0)
        info_col.addWidget(self._name)

        # Meta row (D50, K value)
        self._meta = QLabel()
        self._meta.setFont(QFont(F.MONO, F.SZ_XS))
        self._meta.setStyleSheet(f"color: {C.SB_MUTED}; background: transparent;")
        self._meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._meta.setMinimumWidth(0)
        self._update_meta_text()
        info_col.addWidget(self._meta)
        row.addWidget(info_host, 1)

        # Status LED  — .s-led in CSS
        self._led = QLabel()
        self._led.setFixedSize(6, 6)
        row.addWidget(self._led)

        # Selected toggle — .s-pick-btn in CSS
        self._sel_btn = QPushButton()
        self._sel_btn.setObjectName("card-pick")
        self._sel_btn.setFixedSize(20, 20)
        self._sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sel_btn.setToolTip("Included in comparison/export scope")
        self._sel_btn.clicked.connect(self._toggle_selected)
        row.addWidget(self._sel_btn)

        # Expand chevron — .s-expand-btn in CSS
        self._expand_btn = QPushButton()
        self._expand_btn.setObjectName("card-expand")
        self._expand_btn.setFixedSize(18, 18)
        self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_btn.setToolTip("Expand details")
        try:
            self._expand_btn.setIcon(icon('fa6s.chevron-right', C.SB_MUTED))
            self._expand_btn.setIconSize(QSize(10, 10))
        except Exception:
            self._expand_btn.setText("\u25B8")
        self._expand_btn.setStyleSheet(
            f"QPushButton#card-expand {{ background: transparent; border: none; "
            f"padding: 0; border-radius: 3px; color: {C.SB_MUTED}; }}"
            f"QPushButton#card-expand:hover {{ background: rgba(0,0,0,0.07); color: {C.SB_TEXT}; }}")
        self._expand_btn.clicked.connect(self._toggle_expand)
        row.addWidget(self._expand_btn)

        main_v.addWidget(self._main_row)

        # ── Detail section (hidden by default) — .s-detail in CSS ──
        self._detail = QWidget()
        self._detail.setVisible(False)
        detail_v = QVBoxLayout(self._detail)
        detail_v.setContentsMargins(8, 0, 8, 7)
        detail_v.setSpacing(5)

        # Status line
        self._status_line = QLabel()
        self._status_line.setFont(QFont(F.MONO, F.SZ_BASE))
        self._status_line.setStyleSheet(
            f"background: rgba(255,255,255,0.35); color: {C.SB_MID}; "
            f"padding: 3px 7px; border-radius: 3px; font-size: 8pt;")
        detail_v.addWidget(self._status_line)

        # Action buttons rows — keeps expanded cards inside narrow sidebars.
        self._action_buttons: dict[str, QPushButton] = {}
        primary_row = QHBoxLayout()
        primary_row.setContentsMargins(0, 0, 0, 0)
        primary_row.setSpacing(4)
        utility_row = QHBoxLayout()
        utility_row.setContentsMargins(0, 0, 0, 0)
        utility_row.setSpacing(4)
        for btn_text, btn_icon_name, is_danger, sig_attr in [
            ("Inspect", "fa6s.magnifying-glass", False, "sig_inspect"),
            ("Remap",   "fa6s.table-columns",    False, "sig_remap"),
            ("Log",     "fa6s.clipboard-list",   False, "sig_log"),
            ("Props",   "fa6s.sliders",           False, "sig_props"),
            ("Remove",  "fa6s.trash",             True,  "sig_remove"),
        ]:
            btn = QPushButton(btn_text)
            btn.setObjectName("card-action")
            btn.setFixedHeight(24)
            btn.setMinimumWidth(0)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            try:
                btn.setIcon(icon(btn_icon_name,
                                 "#a03020" if is_danger else C.SB_MID))
                btn.setIconSize(QSize(10, 10))
            except Exception:
                pass
            danger_ss = (f"color: #a03020; border-color: rgba(160,48,32,0.28);"
                         if is_danger else "")
            btn.setStyleSheet(
                f"QPushButton#card-action {{ background: rgba(255,255,255,0.38); "
                f"border: 1px solid {C.SB_BDR}; border-radius: 3px; "
                f"padding: 0 7px; font-size: 8pt; color: {C.SB_MID}; {danger_ss} }}"
                f"QPushButton#card-action:hover {{ background: rgba(255,255,255,0.7); "
                f"color: {C.SB_TEXT}; }}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # Wire to the matching signal — capture sig_attr by value
            _sig = getattr(self, sig_attr)
            btn.clicked.connect(lambda _checked, s=_sig: s.emit(self.file_path))
            self._action_buttons[btn_text] = btn
            if btn_text in {"Inspect", "Remap"}:
                primary_row.addWidget(btn)
            else:
                utility_row.addWidget(btn)
        detail_v.addLayout(primary_row)
        detail_v.addLayout(utility_row)

        main_v.addWidget(self._detail)

        self._refresh()

    def set_status(self, status: str):
        self._status = status
        self._refresh()

    def set_active(self, active: bool):
        self._active = active
        self._refresh()

    @property
    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool):
        self._selected = selected
        self._refresh_sel_btn()

    def set_meta(self, d50: str = "", k_val: str = ""):
        self._d50 = d50
        self._k_val = k_val
        self._update_meta_text()

    def set_group(self, group_name: str = ""):
        self._group_name = group_name or ""
        self._update_meta_text()

    def _update_meta_text(self):
        parts = []
        if self._group_name and self._group_name != "Ungrouped":
            parts.append(f"Group: {self._group_name}")
        if self._d50:
            parts.append(f"D50: {self._d50}")
        if self._k_val:
            parts.append(f"K: {self._k_val}")
        self._meta.setText(" \u00b7 ".join(parts) if parts else "")
        self._meta.setVisible(bool(parts))

    def _toggle_selected(self):
        self._selected = not self._selected
        self._refresh_sel_btn()
        self.sig_selected.emit(self.file_path, self._selected)

    def _toggle_expand(self):
        self._expanded = not self._expanded
        self._detail.setVisible(self._expanded)
        try:
            chevron = 'fa6s.chevron-down' if self._expanded else 'fa6s.chevron-right'
            self._expand_btn.setIcon(icon(chevron, C.SB_MID if self._expanded else C.SB_MUTED))
            self._expand_btn.setIconSize(QSize(10, 10))
        except Exception:
            pass

    def _refresh_sel_btn(self):
        if self._selected:
            self._sel_btn.setToolTip("Included in comparison/export scope")
            self._sel_btn.setStyleSheet(
                f"QPushButton#card-pick {{ background: rgba(107,142,35,0.12); "
                f"border: 1px solid rgba(107,142,35,0.34); border-radius: 4px; "
                f"padding: 0; color: {C.OLIVE}; font-size: 9px; }}")
            try:
                self._sel_btn.setIcon(icon('fa6s.check', C.OLIVE))
                self._sel_btn.setIconSize(QSize(10, 10))
            except Exception:
                self._sel_btn.setText("\u2713")
        else:
            self._sel_btn.setToolTip("Excluded from comparison/export scope")
            self._sel_btn.setStyleSheet(
                f"QPushButton#card-pick {{ background: rgba(255,255,255,0.42); "
                f"border: 1px solid {C.SB_BDR}; border-radius: 4px; padding: 0; }}"
                f"QPushButton#card-pick:hover {{ border-color: {C.BORDER_DK}; "
                f"background: rgba(255,255,255,0.72); }}")
            self._sel_btn.setIcon(QIcon())
            self._sel_btn.setText("")

    def _refresh(self):
        led_color = self._STATUS_DOT.get(self._status, C.SB_MUTED)

        # Card background and border
        if self._active:
            self.setStyleSheet(
                f"_SampleCard {{ background: {C.SB_ACT}; "
                f"border: 1px solid {C.SB_BDR}; "
                f"border-radius: {SZ.BORDER_RADIUS}px; }}")
            self._icon_box.setStyleSheet(
                f"background: rgba(107,142,35,0.15); "
                f"border: 1px solid rgba(107,142,35,0.3); border-radius: 3px;")
            try:
                self._icon_lbl.setPixmap(
                    icon('fa6s.vial', C.OLIVE).pixmap(11, 11))
            except Exception:
                pass
        else:
            self.setStyleSheet(
                f"_SampleCard {{ background: transparent; "
                f"border: 1px solid transparent; "
                f"border-radius: {SZ.BORDER_RADIUS}px; }}"
                f"_SampleCard:hover {{ background: rgba(255,255,255,0.4); }}")
            self._icon_box.setStyleSheet(
                f"background: rgba(255,255,255,0.3); "
                f"border: 1px solid {C.SB_BDR}; border-radius: 3px;")
            try:
                self._icon_lbl.setPixmap(
                    icon('fa6s.vial', C.SB_MID).pixmap(11, 11))
            except Exception:
                pass

        # LED
        self._led.setStyleSheet(
            f"background: {led_color}; border-radius: 3px;")

        # Name color
        name_color = C.SB_TEXT if self._active else C.SB_TEXT
        self._name.setStyleSheet(f"color: {name_color}; background: transparent;")

        # Selection button
        self._refresh_sel_btn()

        # Status line text
        status_text = {
            'pending': '\u23f3 Loading...',
            'mapping': 'Mapping required',
            'failed': '\u274c Load failed',
            'review': '\u26a0 Needs review',
            'loaded': '\u2705 Loaded successfully',
        }.get(self._status, self._status)
        self._status_line.setText(status_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.sig_clicked.emit(self.file_path)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        """Paint the olive left accent bar when active."""
        super().paintEvent(event)
        if self._active:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(C.OLIVE))
            painter.setPen(Qt.PenStyle.NoPen)
            # 3px wide bar on the left, vertically centered
            bar_h = 16
            y = (self.height() - bar_h) // 2
            painter.drawRoundedRect(0, y, 3, bar_h, 1.5, 1.5)
            painter.end()


class _FileListWidget(QScrollArea):
    """Scrollable container of _SampleCard widgets — matches _shared.css .s-list."""

    card_clicked = pyqtSignal(str)         # file_path
    card_ctx = pyqtSignal(str, object)     # file_path, QPoint (global)
    selection_changed = pyqtSignal()       # emitted when any card's selected state changes
    card_inspect = pyqtSignal(str)         # file_path
    card_remap = pyqtSignal(str)           # file_path
    card_log = pyqtSignal(str)             # file_path
    card_props = pyqtSignal(str)           # file_path
    card_remove = pyqtSignal(str)          # file_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, _SampleCard] = {}
        self._active_path: str | None = None

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
            f"QScrollBar:vertical {{ width: 5px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {C.SB_BDR};"
            f"  border-radius: 2px; min-height: 16px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical"
            f"  {{ height: 0; }}"
        )

        container = QWidget()
        container.setStyleSheet(f"background: {C.SB};")
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(6, 4, 4, 4)
        self._layout.setSpacing(1)
        self._layout.addStretch()
        self.setWidget(container)

    def add_card(self, file_path: str, display_name: str, status: str):
        if file_path in self._cards:
            return
        card = _SampleCard(file_path, display_name, status)
        card.set_selected(True)
        card.sig_clicked.connect(self._on_card_clicked)
        card.sig_ctx.connect(self.card_ctx)
        card.sig_selected.connect(self._on_card_selected)
        card.sig_inspect.connect(self.card_inspect)
        card.sig_remap.connect(self.card_remap)
        card.sig_log.connect(self.card_log)
        card.sig_props.connect(self.card_props)
        card.sig_remove.connect(self.card_remove)
        count = self._layout.count()
        self._layout.insertWidget(count - 1, card)
        self._cards[file_path] = card

    def update_card_status(self, file_path: str, status: str):
        if file_path in self._cards:
            self._cards[file_path].set_status(status)

    def update_card_meta(self, file_path: str, d50: str = "", k_val: str = ""):
        if file_path in self._cards:
            self._cards[file_path].set_meta(d50, k_val)

    def update_card_group(self, file_path: str, group_name: str = ""):
        if file_path in self._cards:
            self._cards[file_path].set_group(group_name)

    def remove_card(self, file_path: str):
        if file_path in self._cards:
            card = self._cards.pop(file_path)
            card.setParent(None)
            card.deleteLater()
        if self._active_path == file_path:
            self._active_path = None

    def clear_cards(self):
        for card in list(self._cards.values()):
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        self._active_path = None

    def set_active(self, file_path: str | None):
        if self._active_path and self._active_path in self._cards:
            self._cards[self._active_path].set_active(False)
        self._active_path = file_path
        if file_path and file_path in self._cards:
            self._cards[file_path].set_active(True)

    def get_active_path(self) -> str | None:
        """Return the file path of the currently active (clicked) card, or None."""
        return self._active_path

    def get_selected_paths(self) -> list[str]:
        """Return file paths of all included cards."""
        return [fp for fp, card in self._cards.items() if card.is_selected]

    def set_selected_paths(self, file_paths: list[str], *, emit_signal: bool = True):
        """Apply a sidebar selection state programmatically."""
        path_set = set(file_paths)
        changed = False
        for file_path, card in self._cards.items():
            should_select = file_path in path_set
            if card.is_selected != should_select:
                card.set_selected(should_select)
                changed = True
        if changed and emit_signal:
            self.selection_changed.emit()

    def get_loaded_count(self) -> int:
        return len(self._cards)

    def get_selected_count(self) -> int:
        return sum(1 for card in self._cards.values() if card.is_selected)

    def get_warning_count(self) -> int:
        return sum(1 for card in self._cards.values()
                   if card._status in ('mapping', 'review', 'failed'))

    def apply_filter(self, filter_type: str):
        """Show/hide cards based on filter: 'all', 'selected', 'warnings'."""
        for card in self._cards.values():
            if filter_type == 'all':
                card.setVisible(True)
            elif filter_type == 'selected':
                card.setVisible(card.is_selected)
            elif filter_type == 'warnings':
                card.setVisible(card._status in ('mapping', 'review', 'failed'))

    def _on_card_clicked(self, file_path: str):
        self.set_active(file_path)
        self.card_clicked.emit(file_path)

    def _on_card_selected(self, file_path: str, selected: bool):
        self.selection_changed.emit()


# ─────────────────────────────────────────────────────────────────────────────


class PorosityDialog(FramelessDialogBase):
    """
    Dialog for managing porosity settings across all datasets
    Each dataset can have its own porosity value
    """

    porosity_updated = pyqtSignal(str, float)  # dataset_name, new_porosity

    def __init__(self, main_window, parent=None):
        super().__init__(parent, default_mode="auto")
        self.main_window = main_window
        self.setWindowTitle("Porosity Settings - Per Dataset")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        self.init_ui()
        self.load_dataset_porosity_values()

    def init_ui(self):
        """Initialize dialog UI."""
        from gui.dialog_chrome import make_dialog_header, make_dialog_footer
        from gui.theme import C, F

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header_widget = make_dialog_header(
            "Manage Porosity",
            "Per-dataset porosity values | affects all K calculations",
            fa_icon="fa6s.circle-nodes",
            close_fn=self.accept,
        )
        root.addWidget(self._header_widget)

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(14, 14, 14, 14)
        body_lay.setSpacing(12)

        self.summary_strip = QFrame()
        self.summary_strip.setStyleSheet(
            f"QFrame {{ background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; border-radius: 6px; }}"
        )
        summary_lay = QHBoxLayout(self.summary_strip)
        summary_lay.setContentsMargins(14, 10, 14, 10)
        summary_lay.setSpacing(10)
        self.summary_label = QLabel("No datasets loaded")
        self.summary_label.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_LG}pt; font-weight: 600; background: transparent;"
        )
        self.summary_meta_label = QLabel("")
        self.summary_meta_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; background: transparent;"
        )
        summary_lay.addWidget(self.summary_label)
        summary_lay.addStretch()
        summary_lay.addWidget(self.summary_meta_label)
        body_lay.addWidget(self.summary_strip)

        self.porosity_table = QTableWidget(0, 5)
        self.porosity_table.setHorizontalHeaderLabels([
            "Dataset", "Auto Value", "Current", "Set Value", ""
        ])
        self.porosity_table.setAlternatingRowColors(True)
        self.porosity_table.verticalHeader().setVisible(False)
        self.porosity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.porosity_table.setShowGrid(False)
        self.porosity_table.setFrameShape(QFrame.Shape.NoFrame)
        self.porosity_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        header = self.porosity_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.porosity_table.setColumnWidth(3, 140)
        self.porosity_table.setColumnWidth(4, 170)

        self.porosity_table.setStyleSheet(
            f"QTableWidget {{ background: white; border: 1px solid {C.BORDER}; border-radius: 6px; "
            f"alternate-background-color: rgba(238,232,220,0.55); font-size: {F.SZ_MD}pt; }}"
            f"QTableWidget::item {{ padding: 8px 10px; border-bottom: 1px solid rgba(212,196,168,0.45); }}"
            f"QHeaderView::section {{ background: {C.BG_LOW}; padding: 7px 12px; "
            f"border: none; border-bottom: 1px solid {C.BORDER}; "
            f"font-size: {F.SZ_SM}pt; font-weight: 600; letter-spacing: .06em; "
            f"text-transform: uppercase; color: {C.TEXT_MUTED}; }}"
        )
        body_lay.addWidget(self.porosity_table, 1)

        self.info_label = QLabel(
            "Edit a dataset directly, use Reset to return to the calculated value, or apply all pending changes at once."
        )
        self.info_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; padding: 2px 2px 0 2px; background: transparent;"
        )
        self.info_label.setWordWrap(True)
        body_lay.addWidget(self.info_label)

        root.addWidget(body, 1)
        root.addWidget(make_dialog_footer([
            ("Close", self.accept, "secondary"),
            ("Apply All Changes", self.apply_all_changes, "primary"),
        ]))

        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )

    def load_dataset_porosity_values(self):
        """Load all datasets and their current porosity values."""
        self.porosity_table.setRowCount(0)

        if not hasattr(self.main_window, 'dataset_tabs_widget'):
            self.summary_label.setText("Unable to access datasets")
            self.summary_meta_label.setText("")
            self.info_label.setText("Could not access dataset tabs from the main window.")
            return

        tab_count = self.main_window.dataset_tabs_widget.count()
        dataset_count = 0
        auto_count = 0
        manual_count = 0

        for i in range(tab_count):
            tab = self.main_window.dataset_tabs_widget.widget(i)
            if not hasattr(tab, 'dataset'):
                continue

            dataset_count += 1
            dataset = tab.dataset
            dataset_name = dataset.sample_name
            calculated_porosity = getattr(dataset, 'calculated_porosity', None)
            current_porosity = getattr(dataset, 'current_porosity', None)
            mode_label = (
                dataset.calculated_porosity_mode_label()
                if hasattr(dataset, 'calculated_porosity_mode_label')
                else "Simple formula"
            )

            if current_porosity is None:
                current_porosity = calculated_porosity if calculated_porosity else 0.40

            is_manual = (
                calculated_porosity is None
                or abs(current_porosity - calculated_porosity) > 0.0001
            )
            if is_manual:
                manual_count += 1
            else:
                auto_count += 1

            row = self.porosity_table.rowCount()
            self.porosity_table.insertRow(row)
            self.porosity_table.setRowHeight(row, 56)

            summary_widget = QWidget()
            summary_layout = QVBoxLayout(summary_widget)
            summary_layout.setContentsMargins(0, 0, 0, 0)
            summary_layout.setSpacing(2)

            name_label = QLabel(dataset_name)
            name_label.setStyleSheet(
                f"color: {C.TEXT}; font-size: {F.SZ_LG}pt; font-weight: 600; background: transparent;"
            )
            summary_layout.addWidget(name_label)

            badge_label = QLabel("Manual override" if is_manual else f"Auto: {mode_label}")
            if hasattr(dataset, 'porosity_source_label'):
                badge_label.setToolTip(dataset.porosity_source_label())
            badge_label.setStyleSheet(
                f"QLabel {{ padding: 1px 7px; border-radius: 99px; font-size: {F.SZ_XS}pt; "
                f"font-weight: 600; color: {'#8f3525' if is_manual else C.OLIVE}; "
                f"background: {'rgba(192,56,40,0.08)' if is_manual else 'rgba(107,142,35,0.10)'}; "
                f"border: 1px solid {'rgba(192,56,40,0.22)' if is_manual else 'rgba(107,142,35,0.24)'}; }}"
            )
            summary_layout.addWidget(badge_label, 0, Qt.AlignmentFlag.AlignLeft)
            self.porosity_table.setCellWidget(row, 0, summary_widget)

            if calculated_porosity:
                calc_item = QTableWidgetItem(f"{calculated_porosity:.4f}")
                calc_item.setToolTip(f"Automatic value from {mode_label}.")
            else:
                calc_item = QTableWidgetItem("N/A")
                calc_item.setToolTip("No automatic porosity value is available.")
            calc_item.setFlags(calc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            calc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            calc_item.setFont(QFont(F.MONO, F.SZ_MD))
            self.porosity_table.setItem(row, 1, calc_item)

            current_item = QTableWidgetItem(f"{current_porosity:.4f}")
            current_item.setFlags(current_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            current_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            current_item.setFont(QFont(F.MONO, F.SZ_MD))
            self.porosity_table.setItem(row, 2, current_item)

            edit_field = QLineEdit()
            edit_field.setText(f"{current_porosity:.4f}")
            edit_field.setProperty("dataset_name", dataset_name)
            edit_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit_field.setStyleSheet(
                f"QLineEdit {{ padding: 5px 6px; border: 1px solid {C.BORDER}; border-radius: 4px; "
                f"background: white; color: {C.TEXT}; font-family: '{F.MONO}'; font-size: {F.SZ_MD}pt; }}"
                f"QLineEdit:focus {{ border-color: {C.OLIVE}; }}"
            )
            self.porosity_table.setCellWidget(row, 3, edit_field)

            action_widget = QWidget()
            action_widget.setProperty("dataset_name", dataset_name)
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(6)

            update_btn = QPushButton("Update")
            update_btn.setStyleSheet(
                f"QPushButton {{ background: {C.OLIVE}; color: white; padding: 5px 10px; "
                f"font-size: {F.SZ_SM}pt; font-weight: 600; border: 1px solid {C.OLIVE_DK}; border-radius: 4px; }}"
                f"QPushButton:hover {{ background: {C.OLIVE_H}; }}"
            )
            update_btn.clicked.connect(lambda checked, r=row: self.update_single_dataset(r))

            reset_btn = QPushButton("Reset")
            reset_btn.setStyleSheet(
                f"QPushButton {{ background: {C.BG}; color: {C.TEXT_MID}; padding: 5px 10px; "
                f"font-size: {F.SZ_SM}pt; border: 1px solid {C.BORDER_DK}; border-radius: 4px; }}"
                f"QPushButton:hover {{ background: {C.BG_RAISED}; color: {C.TEXT}; }}"
                f"QPushButton:disabled {{ color: {C.TEXT_MUTED}; border-color: {C.BORDER}; }}"
            )
            reset_btn.clicked.connect(lambda checked, r=row: self.reset_single_dataset(r))

            if calculated_porosity is None:
                reset_btn.setEnabled(False)

            action_layout.addWidget(update_btn)
            action_layout.addWidget(reset_btn)
            self.porosity_table.setCellWidget(row, 4, action_widget)

        if dataset_count == 0:
            self.summary_label.setText("No datasets loaded")
            self.summary_meta_label.setText("")
            self.info_label.setText("Load sample data first to manage per-dataset porosity values.")
        else:
            self.summary_label.setText(f"{dataset_count} dataset{'s' if dataset_count != 1 else ''} in workspace")
            self.summary_meta_label.setText(
                f"{auto_count} automatic | {manual_count} manual override{'s' if manual_count != 1 else ''}"
            )
            self.info_label.setText(
                "Edit a row directly, use Reset to return to the calculated value, or apply all pending changes at once."
            )

    def update_single_dataset(self, row: int):
        """Update porosity for a single dataset"""
        edit_field = self.porosity_table.cellWidget(row, 3)
        dataset_name = edit_field.property("dataset_name")

        try:
            new_porosity = float(edit_field.text())

            if not (0.1 <= new_porosity <= 0.8):
                QMessageBox.warning(
                    self,
                    "Invalid Porosity",
                    "Porosity must be between 0.1 and 0.8"
                )
                return

            # Find the tab and update
            for i in range(self.main_window.dataset_tabs_widget.count()):
                tab = self.main_window.dataset_tabs_widget.widget(i)
                if hasattr(tab, 'dataset') and tab.dataset.sample_name == dataset_name:
                    # Update dataset porosity
                    tab.dataset.current_porosity = new_porosity
                    tab.dataset.porosity = new_porosity
                    tab.porosity = new_porosity

                    # Update statistics tab if it exists
                    if hasattr(tab, 'statistics_tab'):
                        tab.statistics_tab.porosity = new_porosity
                        tab.statistics_tab.update_display()

                    # Recalculate K-values
                    if hasattr(tab, 'calculate_k_values') and hasattr(tab, 'current_results') and tab.current_results:
                        tab.calculate_k_values()

                    break

            # Update table display
            current_item = self.porosity_table.item(row, 2)
            current_item.setText(f"{new_porosity:.4f}")

            self.info_label.setText(f"✅ Updated {dataset_name} to porosity {new_porosity:.4f}")

        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number")

    def reset_single_dataset(self, row: int):
        """Reset porosity to calculated value for a single dataset"""
        edit_field = self.porosity_table.cellWidget(row, 3)
        dataset_name = edit_field.property("dataset_name")
        calc_item = self.porosity_table.item(row, 1)

        if calc_item.text() == "N/A":
            QMessageBox.information(
                self,
                "No Calculated Value",
                "This dataset doesn't have a calculated porosity value."
            )
            return

        calculated_porosity = float(calc_item.text())

        # Update the tab
        for i in range(self.main_window.dataset_tabs_widget.count()):
            tab = self.main_window.dataset_tabs_widget.widget(i)
            if hasattr(tab, 'dataset') and tab.dataset.sample_name == dataset_name:
                tab.dataset.current_porosity = calculated_porosity
                tab.dataset.porosity = calculated_porosity
                tab.porosity = calculated_porosity

                # Update statistics tab
                if hasattr(tab, 'statistics_tab'):
                    tab.statistics_tab.porosity = calculated_porosity
                    tab.statistics_tab.update_display()

                # Recalculate K-values
                if hasattr(tab, 'calculate_k_values') and hasattr(tab, 'current_results') and tab.current_results:
                    tab.calculate_k_values()

                break

        # Update table display
        edit_field.setText(f"{calculated_porosity:.4f}")

        current_item = self.porosity_table.item(row, 2)
        current_item.setText(f"{calculated_porosity:.4f}")

        self.info_label.setText(f"✅ Reset {dataset_name} to calculated value {calculated_porosity:.4f}")

    def apply_all_changes(self):
        """Apply all porosity changes at once"""
        changes_made = 0

        for row in range(self.porosity_table.rowCount()):
            edit_field = self.porosity_table.cellWidget(row, 3)
            dataset_name = edit_field.property("dataset_name")
            current_item = self.porosity_table.item(row, 2)

            try:
                new_porosity = float(edit_field.text())
                current_porosity = float(current_item.text())

                # Only update if changed
                if abs(new_porosity - current_porosity) > 0.0001:
                    if not (0.1 <= new_porosity <= 0.8):
                        QMessageBox.warning(
                            self,
                            "Invalid Porosity",
                            f"Porosity for {dataset_name} must be between 0.1 and 0.8"
                        )
                        continue

                    # Update the tab
                    for i in range(self.main_window.dataset_tabs_widget.count()):
                        tab = self.main_window.dataset_tabs_widget.widget(i)
                        if hasattr(tab, 'dataset') and tab.dataset.sample_name == dataset_name:
                            tab.dataset.current_porosity = new_porosity
                            tab.dataset.porosity = new_porosity
                            tab.porosity = new_porosity

                            # Update statistics tab
                            if hasattr(tab, 'statistics_tab'):
                                tab.statistics_tab.porosity = new_porosity
                                tab.statistics_tab.update_display()

                            # Recalculate K-values
                            if hasattr(tab, 'calculate_k_values') and hasattr(tab, 'current_results') and tab.current_results:
                                tab.calculate_k_values()

                            changes_made += 1
                            break

                    # Update table
                    current_item.setText(f"{new_porosity:.4f}")

            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    f"Invalid porosity value for {dataset_name}"
                )
                continue

        if changes_made > 0:
            QMessageBox.information(
                self,
                "Changes Applied",
                f"Updated porosity for {changes_made} dataset(s).\nK-values have been recalculated."
            )
            self.accept()
        else:
            self.info_label.setText("ℹ️ No changes detected")


class _FractionBar(QWidget):
    """Stacked horizontal fraction bar drawn with QPainter.

    - 28 px tall, rounded corners, inset highlight at top
    - Each segment filled with grain-class color; inline text when wide enough
    - Mouse tracking → per-segment QToolTip on hover
    - No-data state: dashed border + centred placeholder text
    """

    _COLORS = [C.GC_CLAY, C.GC_SILT, C.GC_SAND, C.GC_GRAVEL, C.GC_COBBLE]
    _LABELS = ["Clay",    "Silt",    "Sand",    "Gravel",    "Cobble"]
    # Text colour per segment (sand is dark-on-light, others white-on-dark)
    _TEXT_C = ["#ffffff", "#ffffff", "#5a3800", "#ffffff",   "#ffffff"]

    # Minimum pixel widths for showing text in a segment
    _MIN_W_FULL  = 52   # "Sand · 74%"
    _MIN_W_SHORT = 26   # "Gvl"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fractions: list[float] = []
        self._seg_rects: list[tuple[int, int, str, str]] = []  # (x, w, name, pct_str)
        self.setMouseTracking(True)

    def set_fractions(self, result: ClassificationResult | None):
        if result is None:
            self._fractions = []
            self.setToolTip("")
        else:
            f = result.fractions
            self._fractions = [
                f.clay_pct, f.silt_pct, f.sand_pct, f.gravel_pct, f.cobble_pct,
            ]
            parts = []
            for label, pct in zip(self._LABELS, self._fractions):
                if pct > 0:
                    parts.append(f"{label} {pct:.1f}%")
            self.setToolTip(" · ".join(parts))
        self.update()

    def _build_seg_rects(self, w: int) -> list:
        """Return list of (x, seg_w, color, label, pct, text_color) for non-zero segs."""
        if not self._fractions:
            return []
        total = sum(self._fractions)
        if total == 0:
            return []
        segs = []
        x = 0
        non_zero = [(i, p) for i, p in enumerate(self._fractions) if p > 0]
        for idx, (i, pct) in enumerate(non_zero):
            seg_w = int(round(pct / total * w))
            if idx == len(non_zero) - 1:
                seg_w = w - x
            segs.append((x, seg_w, self._COLORS[i], self._LABELS[i],
                         pct, self._TEXT_C[i]))
            x += seg_w
        return segs

    def mouseMoveEvent(self, event):
        segs = self._build_seg_rects(self.width())
        mx = event.position().x()
        for x, seg_w, _c, label, pct, _tc in segs:
            if x <= mx < x + seg_w:
                tip = f"{label}: {pct:.1f}%"
                QToolTip.showText(event.globalPosition().toPoint(), tip, self)
                return
        QToolTip.hideText()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = 4.0

        segs = self._build_seg_rects(w)

        if not segs:
            # ── No-data: dashed border + centred text ────────────────────
            pen = QPen(QColor(C.SB_BDR))
            pen.setWidth(1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), r, r)
            painter.setPen(QColor(C.SB_MUTED))
            font = QFont(F.MONO, 8)
            painter.setFont(font)
            painter.drawText(QRectF(0, 0, w, h),
                             Qt.AlignmentFlag.AlignCenter, "No data loaded")
            painter.end()
            return

        # ── Draw filled segments ──────────────────────────────────────────
        # Clip entire bar to rounded rect so segments inherit the shape
        from PyQt6.QtGui import QPainterPath
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        painter.setClipPath(clip_path)

        font = QFont(F.MONO, 8)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        fm = QFontMetrics(font)

        for x, seg_w, color_hex, label, pct, text_color in segs:
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(x, 0, seg_w, h))

            # Inline text if segment is wide enough
            if seg_w >= self._MIN_W_FULL:
                text = f"{label} · {pct:.0f}%"
            elif seg_w >= self._MIN_W_SHORT:
                text = label[:3]
            else:
                text = ""

            if text:
                painter.setPen(QColor(text_color))
                painter.drawText(
                    QRectF(x, 0, seg_w, h),
                    Qt.AlignmentFlag.AlignCenter,
                    text,
                )

        painter.setClipping(False)

        # ── Border overlay ────────────────────────────────────────────────
        pen = QPen(QColor(C.SB_BDR))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), r, r)

        # ── Inset highlight: 1px white line at top ────────────────────────
        painter.setPen(QPen(QColor(255, 255, 255, 90)))
        painter.drawLine(QRectF(r, 1, w - 2 * r, 0).topLeft().toPoint(),
                         QRectF(r, 1, w - 2 * r, 0).topRight().toPoint())

        painter.end()


class _StratigraphyWidget(QWidget):
    """Sidebar stratigraphy widget — clean, no nested boxes.

    Layout (top→bottom):
      • _FractionBar   28 px QPainter bar with per-segment tooltip
      • Fractions line  compact single row  ● 90% Sand · ● 9% Silt …
      • Result row      label left  |  scheme pill right  (no box)
      • Perm line       droplet icon + olive value  (no box)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result: ClassificationResult | None = None
        self._setup_ui()

    # ── Public API ────────────────────────────────────────────────────────────

    def update_result(self, result: ClassificationResult | None):
        self._result = result
        self._refresh()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 4, 10, 8)
        root.setSpacing(5)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(f"background: {C.SB};")

        # ── Fraction bar ──────────────────────────────────────────────────
        self._bar = _FractionBar(self)
        self._bar.setFixedHeight(28)
        root.addWidget(self._bar)

        # ── Compact fractions line ────────────────────────────────────────
        # Custom painter widget: ● 90% Sand · ● 9% Silt  (only significant)
        self._frac_line = _FractionsLine(self)
        self._frac_line.setFixedHeight(16)
        root.addWidget(self._frac_line)

        # ── Result row (no box — just text on sidebar bg) ─────────────────
        result_row = QWidget()
        result_row.setStyleSheet("background: transparent;")
        result_h = QHBoxLayout(result_row)
        result_h.setContentsMargins(0, 0, 0, 0)
        result_h.setSpacing(6)

        self._result_lbl = QLabel("No data loaded")
        self._result_lbl.setFont(QFont(F.UI, F.SZ_SM, QFont.Weight.Medium))
        self._result_lbl.setStyleSheet(f"color: {C.SB_MUTED}; background: transparent;")
        result_h.addWidget(self._result_lbl, 1)

        self._scheme_badge = QLabel("")
        self._scheme_badge.setFont(QFont(F.MONO, 7))
        self._scheme_badge.setStyleSheet(
            f"background: {C.SB_UP}; border: 1px solid {C.SB_BDR};"
            f" border-radius: 99px; padding: 1px 6px; color: {C.SB_MUTED};"
        )
        self._scheme_badge.setVisible(False)
        result_h.addWidget(self._scheme_badge, 0)

        root.addWidget(result_row)

        # ── Permeability line (no box) ────────────────────────────────────
        perm_row = QWidget()
        perm_row.setStyleSheet("background: transparent;")
        perm_h = QHBoxLayout(perm_row)
        perm_h.setContentsMargins(0, 0, 0, 0)
        perm_h.setSpacing(5)

        try:
            _perm_icon = QLabel()
            _perm_icon.setPixmap(icon("fa6s.droplet", C.SB_MUTED).pixmap(8, 8))
            _perm_icon.setStyleSheet("background: transparent;")
            perm_h.addWidget(_perm_icon)
        except Exception:
            pass

        self._perm_lbl = QLabel("—")
        self._perm_lbl.setFont(QFont(F.MONO, 8))
        self._perm_lbl.setStyleSheet(f"color: {C.SB_MUTED}; background: transparent;")
        perm_h.addWidget(self._perm_lbl, 1)

        root.addWidget(perm_row)

    def _refresh(self):
        r = self._result
        self._bar.set_fractions(r)
        self._frac_line.set_fractions(r)

        if r is None:
            self._result_lbl.setText("No data loaded")
            self._result_lbl.setStyleSheet(f"color: {C.SB_MUTED}; background: transparent;")
            self._scheme_badge.setVisible(False)
            self._perm_lbl.setText("—")
            self._perm_lbl.setStyleSheet(f"color: {C.SB_MUTED}; background: transparent;")
            self._perm_lbl.setToolTip("")
            return

        # Classification label
        self._result_lbl.setText(r.label.title())
        self._result_lbl.setStyleSheet(f"color: {C.SB_TEXT}; background: transparent;")

        # Scheme pill
        scheme_short = (r.scheme.key.upper()
                        .replace("ISO14688", "ISO 14688")
                        .replace("CUSTOM", "Custom"))
        self._scheme_badge.setText(scheme_short)
        self._scheme_badge.setVisible(True)

        # Permeability — olive colour, full text as tooltip
        perm = r.permeability_class
        self._perm_lbl.setText(perm)
        self._perm_lbl.setStyleSheet(f"color: {C.OLIVE}; background: transparent;")
        self._perm_lbl.setToolTip(perm)


class _FractionsLine(QWidget):
    """Single-line compact fractions summary drawn with QPainter.

    Renders:  ● 90% Sand  ·  ● 9% Silt  ·  ● 1% Gravel
    Only shows fractions ≥ 0.5%.  Fractions sorted by value descending.
    """

    _DEFS = [
        ("Clay",   C.GC_CLAY),
        ("Silt",   C.GC_SILT),
        ("Sand",   C.GC_SAND),
        ("Gravel", C.GC_GRAVEL),
        ("Cobble", C.GC_COBBLE),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fractions: list[tuple[str, float, str]] = []  # (name, pct, color)

    def set_fractions(self, result: ClassificationResult | None):
        if result is None:
            self._fractions = []
        else:
            f = result.fractions
            raw = [
                (name, pct, col)
                for (name, col), pct in zip(
                    [(d[0], d[1]) for d in self._DEFS],
                    [f.clay_pct, f.silt_pct, f.sand_pct, f.gravel_pct, f.cobble_pct]
                )
                if pct >= 0.5
            ]
            # Sort descending so dominant fraction appears first
            self._fractions = sorted(raw, key=lambda t: t[1], reverse=True)
        self.update()

    def paintEvent(self, event):
        if not self._fractions:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        dot_sz   = 6
        dot_gap  = 4   # gap between dot and text
        sep_gap  = 8   # gap each side of separator "·"
        cy       = h // 2

        font_main = QFont(F.MONO, 8)
        font_sep  = QFont(F.UI, 8)
        painter.setFont(font_main)
        fm = QFontMetrics(font_main)

        x = 0
        for i, (name, pct, color_hex) in enumerate(self._fractions):
            # Separator
            if i > 0:
                painter.setFont(font_sep)
                sep_w = QFontMetrics(font_sep).horizontalAdvance("·")
                painter.setPen(QColor(C.SB_MUTED))
                painter.drawText(
                    QRectF(x + sep_gap, 0, sep_w, h),
                    Qt.AlignmentFlag.AlignCenter, "·"
                )
                x += sep_w + sep_gap * 2
                painter.setFont(font_main)

            # Colored dot
            dot_y = cy - dot_sz // 2
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, dot_y, dot_sz, dot_sz), 1.5, 1.5)
            x += dot_sz + dot_gap

            # Text: "90% Sand"
            text = f"{pct:.0f}% {name}"
            text_w = fm.horizontalAdvance(text)
            painter.setPen(QColor(C.SB_MID))
            painter.drawText(
                QRectF(x, 0, text_w, h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                text,
            )
            x += text_w

            if x > w:
                break

        painter.end()


class ApplicationSettingsDialog(FramelessDialogBase):
    """Small application settings dialog for persisted UI preferences."""

    def __init__(self, show_welcome_on_startup: bool, parent=None):
        super().__init__(parent, default_mode="auto")
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self.setMaximumWidth(640)
        self._show_welcome_on_startup = bool(show_welcome_on_startup)
        self.init_ui()

    def init_ui(self):
        """Build the settings dialog UI."""
        from gui.dialog_chrome import make_dialog_header, make_dialog_footer

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header_widget = make_dialog_header(
            "Settings",
            "Application preferences and startup behavior",
            fa_icon="fa6s.gear",
            close_fn=self.reject,
        )
        root.addWidget(self._header_widget)

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(14, 14, 14, 14)
        body_lay.setSpacing(12)

        section_card = QFrame()
        section_card.setStyleSheet(
            f"QFrame {{ background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; "
            f"border-radius: 6px; }}"
        )
        section_lay = QVBoxLayout(section_card)
        section_lay.setContentsMargins(14, 12, 14, 12)
        section_lay.setSpacing(8)

        section_title = QLabel("Startup")
        section_title.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_LG}pt; font-weight: 600; background: transparent;"
        )
        section_lay.addWidget(section_title)

        section_note = QLabel(
            "Control whether the welcome screen is shown when the program launches."
        )
        section_note.setWordWrap(True)
        section_note.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; background: transparent;"
        )
        section_lay.addWidget(section_note)

        self.show_welcome_checkbox = QCheckBox("Show welcome screen on startup")
        self.show_welcome_checkbox.setChecked(self._show_welcome_on_startup)
        self.show_welcome_checkbox.setStyleSheet(
            f"QCheckBox {{ color: {C.TEXT}; font-size: {F.SZ_MD}pt; spacing: 8px; background: transparent; }}"
            f"QCheckBox::indicator {{ width: 16px; height: 16px; }}"
        )
        section_lay.addWidget(self.show_welcome_checkbox)

        help_text = QLabel(
            "This affects startup only. It does not interrupt an active session or overwrite recent-session data."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; background: transparent;"
        )
        section_lay.addWidget(help_text)

        body_lay.addWidget(section_card)
        body_lay.addStretch(1)

        root.addWidget(body, 1)
        root.addWidget(make_dialog_footer([
            ("Cancel", self.reject, "secondary"),
            ("Save", self.accept, "primary"),
        ]))

        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )

    def show_welcome_on_startup(self) -> bool:
        """Return the current welcome-screen startup preference."""
        return bool(self.show_welcome_checkbox.isChecked())


class ControlPanel(QFrame):
    # Signals for communication with main window
    analysis_requested = pyqtSignal(dict)  # Emitted when analysis is requested
    sample_selected = pyqtSignal(str)  # Emitted when a sample is selected
    error_dataset = pyqtSignal(str, str)  # Emitted when dataset fails to load (file_path, error_message)
    mapping_required = pyqtSignal(str, str)  # Emitted when a valid import path needs user mapping
    dataset_loaded_successfully = pyqtSignal(object, str)  # Emitted when dataset loads successfully (dataset, file_path)
    update_error_tab_message = pyqtSignal(str, str)  # Update existing error tab with new message
    dataset_fix_requested = pyqtSignal(str)  # Emitted when user wants to fix/remap a dataset (file_path)
    dataset_integration_started = pyqtSignal()  # Batched dataset UI integration starts
    dataset_integration_finished = pyqtSignal()  # Batched dataset UI integration finished
    selection_changed = pyqtSignal()  # Emitted when card selected-toggle state changes
    manage_datasets_requested = pyqtSignal()  # Emitted when the sidebar manager is requested
    scheme_changed = pyqtSignal(object)  # GrainClassificationScheme — emitted when user picks a new scheme

    def __init__(self):
        super().__init__()
        self.loaded_samples = {}  # Dictionary to store sample data
        self.file_mapping_states = {}  # Remember mapper path and column choices per file
        self.validation_errors = []  # Track validation issues
        self.data_loader = DataLoader()  # Data loading engine
        self.file_statuses = {}  # Track status: 'pending', 'mapping', 'failed', 'review', 'loaded'
        self._active_scheme: GrainClassificationScheme = ISO14688
        self._import_process = None
        self._import_queue = None
        self._import_finished_received = False
        self._import_finalize_summary = None
        self._pending_import_ui_events = deque()
        self._import_ui_total = 0
        self._import_ui_processed = 0
        self._import_dialog = None
        self._import_poll_timer = QTimer(self)
        self._import_poll_timer.setInterval(25)
        self._import_poll_timer.timeout.connect(self._poll_import_process)
        self._import_ui_timer = QTimer(self)
        self._import_ui_timer.setInterval(0)
        self._import_ui_timer.timeout.connect(self._process_import_ui_slice)

        # Temperature change debouncing timer
        self.temp_change_timer = QTimer()
        self.temp_change_timer.setSingleShot(True)
        self.temp_change_timer.timeout.connect(self._apply_temperature_change)
        self.pending_temperature = None

        self.setAcceptDrops(True)
        self.setup_ui()
        self.setup_validation()

    def get_selected_paths(self) -> list[str]:
        """Return file paths of all sidebar-included sample cards."""
        return self._file_list.get_selected_paths()

    def set_selected_paths(self, file_paths: list[str], *, emit_signal: bool = True):
        """Set sidebar-included sample cards from an external controller."""
        self._file_list.set_selected_paths(file_paths, emit_signal=emit_signal)
        self._update_inventory_bar()

    def get_scope_card_count(self) -> int:
        """Return the number of sample cards that can express included scope."""
        return self._file_list.get_loaded_count()

    def _request_dataset_manager(self, _checked: bool = False) -> None:
        """Emit a clean zero-argument request from the sidebar Manage button."""
        self.manage_datasets_requested.emit()

    @staticmethod
    def _resource_file(filename: str) -> str:
        """Return a bundled resource path that works in source and frozen builds."""
        if getattr(sys, "frozen", False):
            bundle_root = getattr(sys, "_MEIPASS", "")
            candidates = [
                os.path.join(bundle_root, "Program", "resources", filename),
                os.path.join(bundle_root, "resources", filename),
            ]
        else:
            candidates = [
                os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "resources",
                    filename,
                )
            ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return candidates[0] if candidates else filename

    @staticmethod
    def _supported_drop_paths_from_mime(mime_data) -> list[str]:
        if not mime_data or not mime_data.hasUrls():
            return []
        supported = ('.csv', '.xlsx', '.xls', '.txt')
        paths = []
        for url in mime_data.urls():
            local_path = url.toLocalFile()
            if local_path and local_path.lower().endswith(supported):
                paths.append(local_path)
        return paths

    def _drop_zone_stylesheet(self, active: bool = False) -> str:
        border = C.OLIVE if active else C.SB_BDR
        bg = "rgba(107,142,35,0.13)" if active else "rgba(255,255,255,0.25)"
        return (
            f"QFrame#import-drop-zone {{ border: 1.5px dashed {border};"
            f" border-radius: 5px; background: {bg}; }}"
            f"QFrame#import-drop-zone:hover {{ border-color: {C.OLIVE};"
            f" background: rgba(107,142,35,0.07); }}"
        )

    def _set_drop_zone_active(self, active: bool) -> None:
        if hasattr(self, "_drop_zone"):
            self._drop_zone.setStyleSheet(self._drop_zone_stylesheet(active))

    def _accept_supported_drop(self, event) -> bool:
        if self._supported_drop_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return True
        event.ignore()
        return False

    def dragEnterEvent(self, event):
        if self._accept_supported_drop(event):
            self._set_drop_zone_active(True)

    def dropEvent(self, event):
        self._set_drop_zone_active(False)
        file_paths = self._supported_drop_paths_from_mime(event.mimeData())
        if file_paths:
            self._handle_dropped_files(file_paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self._accept_supported_drop(event)

    def dragLeaveEvent(self, event):
        self._set_drop_zone_active(False)
        event.accept()

    def _drop_zone_drag_enter(self, event):
        if self._accept_supported_drop(event):
            self._set_drop_zone_active(True)

    def _drop_zone_drag_move(self, event):
        self._accept_supported_drop(event)

    def _drop_zone_drag_leave(self, event):
        self._set_drop_zone_active(False)
        event.accept()

    def _drop_zone_drop(self, event):
        self.dropEvent(event)

    def _file_entry_parts(self, file_entry) -> tuple[str, str | None, str]:
        """Return actual path, sheet name, and stable file key for an import entry."""
        if isinstance(file_entry, Mapping):
            file_key = str(file_entry.get("file_key") or "")
            file_path = str(file_entry.get("file_path") or "")
            sheet_name = file_entry.get("sheet_name")
            if not file_path and file_key:
                file_path, sheet_from_key = self._split_sheet_key(file_key)
                sheet_name = sheet_name or sheet_from_key
            if not file_key and file_path:
                file_key = f"{file_path}:::{sheet_name}" if sheet_name else file_path
            return file_path, sheet_name, file_key
        if isinstance(file_entry, tuple):
            file_path, sheet_name = file_entry
            return str(file_path), str(sheet_name), f"{file_path}:::{sheet_name}"
        file_path = str(file_entry)
        return file_path, None, file_path

    def _file_entry_key(self, file_entry) -> str:
        return self._file_entry_parts(file_entry)[2]

    def _file_entry_display_name(self, file_entry) -> str | None:
        file_path, sheet_name, _ = self._file_entry_parts(file_entry)
        if sheet_name:
            return f"{os.path.basename(file_path)} [{sheet_name}]"
        return None

    def _file_entry_is_excel(self, file_entry) -> bool:
        file_path, _, _ = self._file_entry_parts(file_entry)
        return file_path.lower().endswith((".xlsx", ".xls"))

    def _with_import_intent(self, file_entry, import_intent: str):
        if not self._file_entry_is_excel(file_entry):
            return file_entry
        file_path, sheet_name, file_key = self._file_entry_parts(file_entry)
        return {
            "file_key": file_key,
            "file_path": file_path,
            "sheet_name": sheet_name,
            "import_intent": import_intent,
        }

    def _track_pending_file_entries(self, file_entries: list) -> None:
        for file_entry in file_entries:
            file_key = self._file_entry_key(file_entry)
            self.file_statuses[file_key] = 'pending'

        for file_entry in file_entries:
            file_key = self._file_entry_key(file_entry)
            self.add_file_to_table(
                file_key,
                'pending',
                display_name=self._file_entry_display_name(file_entry),
            )

    def _handle_dropped_files(self, file_paths: list):
        """Process files dropped onto the sidebar — same pipeline as add_files."""
        expanded_files = []
        already_added = []
        excel_files = [f for f in file_paths if f.lower().endswith(('.xlsx', '.xls')) and f not in self.file_statuses]
        other_files = [f for f in file_paths if not f.lower().endswith(('.xlsx', '.xls')) and f not in self.file_statuses]
        already_added = [os.path.basename(f) for f in file_paths if f in self.file_statuses]

        if excel_files:
            excel_expanded = self.handle_batch_multisheet_excel(excel_files)
            if excel_expanded is None:
                return
            expanded_files.extend(excel_expanded)
        expanded_files.extend(other_files)

        if expanded_files:
            self._track_pending_file_entries(expanded_files)
            self.process_files_with_immediate_tabs(expanded_files)
            self.update_ui_state()

    def setup_validation(self):
        """Setup input validation for parameters"""
        # Connect validation to parameter changes
        self.temp_spinbox.valueChanged.connect(self.validate_temperature)
        self.porosity_mode_combo.currentTextChanged.connect(self.on_porosity_mode_changed)

    def setup_ui(self):
        """Setup the control panel layout — new themed sidebar design."""
        import sys

        self.setStyleSheet(f"QFrame {{ background: {C.SB}; border: none; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 1. Logo card ──────────────────────────────────────────────
        root.addWidget(_LogoCard())

        # ── 2. Scrollable body ────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {C.SB}; border: none; }}"
            f"QScrollBar:vertical {{ width: 5px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {C.SB_BDR};"
            f"  border-radius: 2px; min-height: 16px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical"
            f"  {{ height: 0; }}"
        )

        body = QWidget()
        body.setStyleSheet(f"background: {C.SB};")
        body_v = QVBoxLayout(body)
        body_v.setContentsMargins(0, 0, 0, 0)
        body_v.setSpacing(0)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # ── Drop zone — matches .drop in CSS ─────────────────────────
        self._drop_zone = QFrame()
        self._drop_zone.setObjectName("import-drop-zone")
        self._drop_zone.setAcceptDrops(True)
        self._drop_zone.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drop_zone.setMinimumHeight(48)
        self._drop_zone.setMaximumHeight(58)
        self._drop_zone.setStyleSheet(self._drop_zone_stylesheet(False))
        self._drop_zone.mousePressEvent = self._show_add_data_menu_for_drop_zone
        self._drop_zone.dragEnterEvent = self._drop_zone_drag_enter
        self._drop_zone.dragMoveEvent = self._drop_zone_drag_move
        self._drop_zone.dragLeaveEvent = self._drop_zone_drag_leave
        self._drop_zone.dropEvent = self._drop_zone_drop
        self._drop_zone.setToolTip(
            "Drop CSV/Excel/TXT files here. Click to choose processed or raw sieve import."
        )

        dz_v = QVBoxLayout(self._drop_zone)
        dz_v.setContentsMargins(8, 6, 8, 6)
        dz_v.setSpacing(2)
        dz_v.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dz_icon = QLabel()
        try:
            dz_icon.setPixmap(icon('fa6s.cloud-arrow-up', C.SB_MUTED).pixmap(14, 14))
        except Exception:
            dz_icon.setText("\u2B06")
        dz_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_icon.setStyleSheet("background: transparent; border: none;")
        dz_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        dz_v.addWidget(dz_icon)

        dz_text = QLabel("Drop files here")
        dz_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_text.setStyleSheet(
            f"font-size: 10px; color: {C.SB_MID};"
            f"  background: transparent; border: none;")
        dz_text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        dz_v.addWidget(dz_text)

        dz_formats = QLabel("Click for processed/raw import")
        dz_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_formats.setStyleSheet(
            f"font-size: 8.5px; color: {C.SB_MUTED};"
            f"  background: transparent; border: none;")
        dz_formats.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        dz_v.addWidget(dz_formats)

        for drop_child in (dz_icon, dz_text, dz_formats):
            drop_child.setAcceptDrops(True)
            drop_child.dragEnterEvent = self._drop_zone_drag_enter
            drop_child.dragMoveEvent = self._drop_zone_drag_move
            drop_child.dragLeaveEvent = self._drop_zone_drag_leave
            drop_child.dropEvent = self._drop_zone_drop

        drop_wrap = QWidget()
        drop_wrap.setStyleSheet(f"background: {C.SB};")
        drop_wrap_v = QHBoxLayout(drop_wrap)
        drop_wrap_v.setContentsMargins(10, 7, 10, 3)
        drop_wrap_v.addWidget(self._drop_zone)
        body_v.addWidget(drop_wrap)

        # ── 2a. SAMPLES section header ────────────────────────────────
        body_v.addWidget(_SectionHeader("SAMPLES", btn_text="+ Add",
                                        btn_icon="fa6s.plus"))

        # Connect the "+ Add" button in section header to add_files
        samples_hdr = body_v.itemAt(body_v.count() - 1).widget()
        if hasattr(samples_hdr, 'action_btn') and samples_hdr.action_btn:
            self._install_add_data_menu(samples_hdr.action_btn)

        summary_w = QWidget()
        summary_w.setFixedHeight(26)
        summary_w.setStyleSheet(f"background: {C.SB};")
        summary_h = QHBoxLayout(summary_w)
        summary_h.setContentsMargins(10, 4, 10, 0)
        summary_h.setSpacing(4)

        _CHIP = (
            f"QLabel {{ padding: 2px 7px; border-radius: 99px;"
            f"  border: 1px solid {C.BORDER}; background: rgba(255,255,255,0.42);"
            f"  font-family: '{F.MONO}'; font-size: 8.5px; color: {C.SB_MID}; }}"
        )
        _CHIP_WARN = (
            f"QLabel {{ padding: 2px 7px; border-radius: 99px;"
            f"  border: 1px solid rgba(208,128,32,0.28); background: rgba(208,128,32,0.08);"
            f"  font-family: '{F.MONO}'; font-size: 8.5px; color: #7a5010; }}"
        )
        _CHIP_SEL = (
            f"QLabel {{ padding: 2px 7px; border-radius: 99px;"
            f"  border: 1px solid rgba(107,142,35,0.26); background: rgba(107,142,35,0.08);"
            f"  font-family: '{F.MONO}'; font-size: 8.5px; color: {C.OLIVE}; }}"
        )
        self._chip_loaded = QLabel("0 loaded")
        self._chip_loaded.setStyleSheet(_CHIP)
        self._chip_selected = QLabel("0 included")
        self._chip_selected.setStyleSheet(_CHIP_SEL)
        self._chip_warnings = QLabel("")
        self._chip_warnings.setStyleSheet(_CHIP_WARN)
        self._chip_warnings.setVisible(False)
        summary_h.addWidget(self._chip_loaded)
        summary_h.addWidget(self._chip_selected)
        summary_h.addWidget(self._chip_warnings)
        summary_h.addStretch()
        body_v.addWidget(summary_w)

        # Filter pills row — matches .s-filter-row in CSS
        pills_w = QWidget()
        pills_w.setFixedHeight(30)
        pills_w.setStyleSheet(f"background: {C.SB};")
        pills_h = QHBoxLayout(pills_w)
        pills_h.setContentsMargins(10, 4, 10, 0)
        pills_h.setSpacing(4)

        _PILL = (
            f"QPushButton {{ height: 22px; padding: 0 9px;"
            f"  border: 1px solid {C.SB_BDR}; border-radius: 99px;"
            f"  background: rgba(255,255,255,0.32);"
            f"  font-family: '{F.UI}'; font-size: 10px; color: {C.SB_MID}; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.55);"
            f"  border-color: {C.BORDER_DK}; color: {C.SB_TEXT}; }}"
            f"QPushButton:checked {{ background: {C.SB_ACT}; border-color: {C.SB_BDR};"
            f"  color: {C.SB_TEXT}; font-weight: 600; }}"
        )
        self._pill_all = QPushButton("All")
        self._pill_all.setCheckable(True)
        self._pill_all.setChecked(True)
        self._pill_all.setStyleSheet(_PILL)
        self._pill_sel = QPushButton("Included")
        self._pill_sel.setCheckable(True)
        self._pill_sel.setStyleSheet(_PILL)
        self._pill_rev = QPushButton("\u26a0 Review")
        self._pill_rev.setCheckable(True)
        self._pill_rev.setStyleSheet(_PILL)
        self._manage_samples_btn = QPushButton("Manage")
        self._manage_samples_btn.setStyleSheet(_PILL)
        self._manage_samples_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._manage_samples_btn.setToolTip("Choose included samples and assign groups")
        self._manage_samples_btn.setEnabled(False)
        self._manage_samples_btn.clicked.connect(self._request_dataset_manager)

        # Exclusive pill logic
        self._pill_all.clicked.connect(lambda: self._set_filter("all"))
        self._pill_sel.clicked.connect(lambda: self._set_filter("selected"))
        self._pill_rev.clicked.connect(lambda: self._set_filter("warnings"))

        pills_h.addWidget(self._pill_all)
        pills_h.addWidget(self._pill_sel)
        pills_h.addWidget(self._pill_rev)
        pills_h.addWidget(self._manage_samples_btn)
        pills_h.addStretch()
        body_v.addWidget(pills_w)

        # Hidden add_files_btn kept for backward compat
        self.add_files_btn = QPushButton("+ Add Files")
        self.add_files_btn.setVisible(False)
        self.add_files_btn.clicked.connect(self.add_files)

        # ── 2b. Card list ─────────────────────────────────────────────
        self._file_list = _FileListWidget()
        self._file_list.setMinimumHeight(80)
        self._file_list.card_clicked.connect(self._on_card_clicked)
        self._file_list.card_ctx.connect(self._on_card_context_menu)
        self._file_list.selection_changed.connect(self._update_inventory_bar)
        self._file_list.selection_changed.connect(self.selection_changed)
        self._file_list.card_inspect.connect(self.show_file_info)
        self._file_list.card_remap.connect(self.edit_file_mapping)
        self._file_list.card_log.connect(self.show_file_log)
        self._file_list.card_props.connect(self.show_file_props)
        self._file_list.card_remove.connect(self._remove_card_by_path)
        body_v.addWidget(self._file_list, 1)

        # ── 2c. Batch box — matches .sb-batch in CSS ─────────────────
        batch_box = QWidget()
        batch_box.setStyleSheet(
            f"background: rgba(255,255,255,0.32);"
            f"border: 1px solid {C.SB_BDR}; border-radius: 5px;")
        batch_box.setContentsMargins(0, 0, 0, 0)
        batch_v = QVBoxLayout(batch_box)
        batch_v.setContentsMargins(8, 8, 8, 8)
        batch_v.setSpacing(7)

        # Stat chips row — .sb-batch-stats
        stats_row = QHBoxLayout()
        stats_row.setSpacing(4)

        _CHIP = (
            f"QLabel {{ padding: 2px 7px; border-radius: 99px;"
            f"  border: 1px solid {C.BORDER}; background: rgba(255,255,255,0.42);"
            f"  font-family: '{F.MONO}'; font-size: 9px; color: {C.SB_MID}; }}"
        )
        _CHIP_WARN = (
            f"QLabel {{ padding: 2px 7px; border-radius: 99px;"
            f"  border: 1px solid rgba(208,128,32,0.28); background: rgba(208,128,32,0.08);"
            f"  font-family: '{F.MONO}'; font-size: 9px; color: #7a5010; }}"
        )
        _CHIP_SEL = (
            f"QLabel {{ padding: 2px 7px; border-radius: 99px;"
            f"  border: 1px solid rgba(107,142,35,0.26); background: rgba(107,142,35,0.08);"
            f"  font-family: '{F.MONO}'; font-size: 9px; color: {C.OLIVE}; }}"
        )

        batch_chip_loaded = QLabel("0 loaded")
        batch_chip_loaded.setStyleSheet(_CHIP)
        batch_chip_selected = QLabel("0 included")
        batch_chip_selected.setStyleSheet(_CHIP_SEL)
        batch_chip_warnings = QLabel("")
        batch_chip_warnings.setStyleSheet(_CHIP_WARN)
        batch_chip_warnings.setVisible(False)

        stats_row.addWidget(batch_chip_loaded)
        stats_row.addWidget(batch_chip_selected)
        stats_row.addWidget(batch_chip_warnings)
        stats_row.addStretch()
        batch_v.addLayout(stats_row)

        # Mini action buttons row — .sb-mini-actions
        _MINI_BTN = (
            f"QPushButton {{ height: 24px; padding: 0 8px;"
            f"  border: 1px solid {C.SB_BDR}; border-radius: 4px;"
            f"  background: rgba(255,255,255,0.48);"
            f"  font-size: 10.5px; color: {C.SB_MID}; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.75);"
            f"  border-color: {C.BORDER_DK}; color: {C.SB_TEXT}; }}"
            f"QPushButton:disabled {{ color: {C.SB_MUTED}; border-color: transparent;"
            f"  background: rgba(255,255,255,0.2); }}"
        )

        mini_btns = QHBoxLayout()
        mini_btns.setSpacing(5)

        self.review_failed_btn = QPushButton("\u26a0 Review")
        self.review_failed_btn.clicked.connect(self.review_failed_files)
        self.review_failed_btn.setEnabled(False)
        self.review_failed_btn.setToolTip("Open files waiting for mapping or manual review")
        self.review_failed_btn.setStyleSheet(_MINI_BTN)

        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all_files)
        self.clear_all_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f"  color: {C.SB_MUTED}; font-size: 9px;"
            f"  font-family: '{F.UI}'; padding: 2px 4px; }}"
            f"QPushButton:hover {{ color: {C.LED_ERR}; }}"
        )

        mini_btns.addWidget(self.review_failed_btn, 1)
        mini_btns.addStretch()
        mini_btns.addWidget(self.clear_all_btn)
        batch_v.addLayout(mini_btns)

        batch_outer = QWidget()
        batch_outer.setStyleSheet(f"background: {C.SB};")
        batch_outer_v = QHBoxLayout(batch_outer)
        batch_outer_v.setContentsMargins(10, 6, 10, 2)
        batch_outer_v.addWidget(batch_box)
        batch_outer.setVisible(False)
        body_v.addWidget(batch_outer)

        # ── 2d. PARAMETERS section ────────────────────────────────────
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setFixedHeight(1)
        div1.setStyleSheet(f"background: {C.SB_BDR};")
        body_v.addWidget(div1)
        params_header = _SectionHeader("PARAMETERS")
        body_v.addWidget(params_header)

        params_inner = QWidget()
        params_inner.setStyleSheet(f"background: {C.SB};")
        params_v = QVBoxLayout(params_inner)
        params_v.setContentsMargins(12, 8, 12, 10)
        params_v.setSpacing(8)

        _LBL = (f"color: {C.SB_MID}; font-family: '{F.UI}';"
                f"font-size: {F.SZ_SM}pt;")

        # Temperature row
        temp_row = QHBoxLayout()
        temp_lbl = QLabel("Temperature")
        temp_lbl.setStyleSheet(_LBL)
        self.temp_spinbox = QDoubleSpinBox()
        self.temp_spinbox.setRange(0, 50)
        self.temp_spinbox.setValue(20)
        self.temp_spinbox.setSuffix(" \u00b0C")
        self.temp_spinbox.setFixedWidth(82)
        self.temp_spinbox.setToolTip(
            "Temperature affects water density and viscosity in K calculations\n"
            "(Vukovic & Soro, 1992)")
        temp_row.addWidget(temp_lbl)
        temp_row.addStretch()
        temp_row.addWidget(self.temp_spinbox)
        params_v.addLayout(temp_row)

        # Porosity mode
        por_lbl = QLabel("Calculated Porosity")
        por_lbl.setStyleSheet(_LBL)
        self.porosity_mode_combo = QComboBox()
        self.porosity_mode_combo.addItems([
            "Simple Formula (Excel Compatible)",
            "Urumovic Polynomial (Research)"
        ])
        self.porosity_mode_combo.setCurrentIndex(0)
        self.porosity_mode_combo.setToolTip(
            "Controls how automatic porosity is estimated for datasets that are not manually overridden.\n"
            "Simple: n = 0.255 x (1 + 0.83^U)\n"
            "Urumovic: research polynomial based on grain size distribution")
        params_v.addWidget(por_lbl)
        params_v.addWidget(self.porosity_mode_combo)

        # Manage porosity button
        self.porosity_settings_btn = QPushButton("Manage Dataset Porosity\u2026")
        self.porosity_settings_btn.clicked.connect(self.open_porosity_dialog)
        self.porosity_settings_btn.setToolTip(
            "Edit porosity values for each dataset individually")
        self.porosity_settings_btn.setStyleSheet(
            f"QPushButton {{ background: {C.SB_UP}; border: 1px solid {C.SB_BDR};"
            f"  border-radius: 3px; padding: 4px 10px;"
            f"  font-family: '{F.UI}'; font-size: {F.SZ_SM}pt; color: {C.SB_MID}; }}"
            f"QPushButton:hover {{ background: {C.SB_ACT}; }}"
        )
        params_v.addWidget(self.porosity_settings_btn)
        div1.setVisible(False)
        params_header.setVisible(False)
        params_inner.setVisible(False)
        body_v.addWidget(params_inner)

        # ── 2e. STRATIGRAPHY section ──────────────────────────────────
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setFixedHeight(1)
        div2.setStyleSheet(f"background: {C.SB_BDR};")
        body_v.addWidget(div2)

        strata_header = _SectionHeader("STRATIGRAPHY",
                                        btn_text="Scheme", btn_icon="fa6s.sliders")
        strata_header.action_btn.clicked.connect(self._open_classification_dialog)
        body_v.addWidget(strata_header)

        strata_outer = QWidget()
        strata_outer.setStyleSheet(f"background: {C.SB};")
        strata_outer_v = QVBoxLayout(strata_outer)
        strata_outer_v.setContentsMargins(0, 0, 0, 0)
        strata_outer_v.setSpacing(0)
        self._strata_widget = _StratigraphyWidget()
        strata_outer_v.addWidget(self._strata_widget)
        div2.setVisible(False)
        strata_header.setVisible(False)
        strata_outer.setVisible(False)
        body_v.addWidget(strata_outer)

        # ── 3. DTU box — matches .dtu-box in CSS ────────────────────────
        dtu_w = QWidget()
        dtu_w.setObjectName("sidebar-credit-box")
        dtu_w.setStyleSheet(
            f"background: {C.SB_DN}; border-top: 1px solid {C.SB_BDR};")
        dtu_h = QHBoxLayout(dtu_w)
        dtu_h.setContentsMargins(13, 9, 13, 8)
        dtu_h.setSpacing(10)

        # DTU red pill label — .dtu-logo in CSS
        dtu_pill = QLabel("DTU")
        self._sidebar_credit_logo = dtu_pill
        dtu_pill.setObjectName("sidebar-credit-logo")
        dtu_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dtu_pill.setStyleSheet(
            "background: transparent; border-radius: 3px; border: 1px solid rgba(0,0,0,0.16);")
        logo_px = QPixmap(self._resource_file("DTU_logo.png"))
        if not logo_px.isNull():
            dtu_pill.setText("")
            dtu_pill.setPixmap(
                logo_px.scaled(
                    40,
                    40,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            dtu_pill.setStyleSheet(
                f"background: {C.DTU_RED}; color: #fff;"
                f"  font-family: '{F.UI}'; font-size: 13px; font-weight: 700;"
                f"  letter-spacing: 0.04em; padding: 3px 6px 2px;"
                f"  border-radius: 2px; line-height: 1.2;")
        dtu_pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        dtu_pill.setFixedSize(44, 44)
        dtu_h.addWidget(dtu_pill)

        # Info column — .dtu-info in CSS
        dtu_info = QVBoxLayout()
        dtu_info.setSpacing(1)
        dtu_prog = QLabel("Grain Size Analysis")
        dtu_prog.setStyleSheet(
            f"font-size: 10.5px; font-weight: 600; color: {C.SB_TEXT};"
            f"  background: transparent;")
        dtu_dept = QLabel(
            "Developed by Oliver Lund\n"
            "Inspired by HydrogeoSieveXL by J.F Devlin\n"
            "Made in collaboration with Poul Løgstrup Bjerg\n"
            "DTU Sustain"
        )
        self._sidebar_credit_text = dtu_dept
        dtu_dept.setObjectName("sidebar-credit-text")
        dtu_dept.setTextFormat(Qt.TextFormat.PlainText)
        dtu_dept.setWordWrap(True)
        dtu_dept.setFont(QFont(F.UI, 7))
        dtu_dept.setStyleSheet(
            f"color: {C.SB_MUTED}; background: transparent;"
            f"  line-height: 1.2;")
        dtu_info.addWidget(dtu_prog)
        dtu_info.addWidget(dtu_dept)
        dtu_h.addLayout(dtu_info, 1)
        root.addWidget(dtu_w)

        # ── 4. Footer bar — matches .sb-foot in CSS ──────────────────
        footer = QWidget()
        footer.setStyleSheet(
            f"background: {C.SB_DN}; border-top: 1px solid {C.SB_BDR};")
        foot_h = QHBoxLayout(footer)
        foot_h.setContentsMargins(6, 5, 6, 5)
        foot_h.setSpacing(2)

        _SF_BTN = (
            f"QPushButton {{ background: transparent; border: none;"
            f"  border-radius: {SZ.BORDER_RADIUS}px; padding: 5px 4px;"
            f"  font-size: 9.5px; color: {C.SB_MUTED}; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.5);"
            f"  color: {C.SB_TEXT}; }}"
        )

        for btn_label, btn_icon_name, btn_slot in [
            ("Help", "fa6s.circle-question", self.show_help),
            ("About", "fa6s.circle-info", self.show_about),
            ("Settings", "fa6s.gear", self.show_settings),
        ]:
            btn = QPushButton(btn_label)
            btn.setStyleSheet(_SF_BTN)
            try:
                btn.setIcon(icon(btn_icon_name, C.SB_MUTED))
            except Exception:
                pass
            if btn_slot:
                btn.clicked.connect(btn_slot)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            foot_h.addWidget(btn)

        root.addWidget(footer)

        # ── Hidden data model: QTableWidget ──────────────────────────
        # Business logic reads/writes here; _file_list cards are the visual layer.
        self.samples_table = QTableWidget()
        self.samples_table.setColumnCount(2)
        self.samples_table.setHorizontalHeaderLabels(["Sample File", "Status"])
        self.samples_table.setVisible(False)
        self.samples_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.samples_table.customContextMenuRequested.connect(
            self.show_context_menu)
        hdr = self.samples_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.samples_table.itemSelectionChanged.connect(
            self.on_sample_selection_changed)
        root.addWidget(self.samples_table)

        # ── Hidden legacy widgets kept for business logic ─────────────
        self.remove_file_btn = QPushButton()
        self.remove_file_btn.setVisible(False)
        self.remove_file_btn.clicked.connect(self.remove_selected_file)

        self.sample_info_label = QLabel()
        self.sample_info_label.setVisible(False)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        self.progress_label = QLabel()
        self.progress_label.setVisible(False)

        self.export_results_cb = QCheckBox()   # used by get_analysis_parameters()
        self.export_results_cb.setVisible(False)

        self.sensitivity_analysis_btn = QPushButton()
        self.sensitivity_analysis_btn.setVisible(False)
        self.sensitivity_analysis_btn.clicked.connect(
            self.show_sensitivity_placeholder)

        for _w in (self.remove_file_btn, self.sample_info_label,
                   self.progress_bar, self.progress_label,
                   self.export_results_cb, self.sensitivity_analysis_btn):
            root.addWidget(_w)


    # ─────────────────────────────────────────────────────────────────────────
    # CARD LIST SYNC METHODS
    # ─────────────────────────────────────────────────────────────────────────

    def _on_card_clicked(self, file_path: str):
        """Sync card click to the hidden table selection."""
        for row in range(self.samples_table.rowCount()):
            item = self.samples_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == file_path:
                self.samples_table.selectRow(row)
                break
        self._refresh_stratigraphy(file_path)

    def _on_card_context_menu(self, file_path: str, global_pos):
        """Show context menu triggered from a _SampleCard right-click."""
        status = self.file_statuses.get(file_path, 'pending')
        menu = QMenu(self)

        if status in ('mapping', 'review'):
            act = QAction("Map Columns\u2026", self)
            act.triggered.connect(lambda: self.edit_file_mapping(file_path))
            menu.addAction(act)
        elif status == 'loaded':
            act = QAction("Show Info\u2026", self)
            act.triggered.connect(lambda: self.show_file_info(file_path))
            menu.addAction(act)
            menu.addSeparator()
            act2 = QAction("Edit Mapping\u2026", self)
            act2.triggered.connect(lambda: self.edit_file_mapping(file_path))
            menu.addAction(act2)
        elif status == 'failed':
            act = QAction("Fix / Remap\u2026", self)
            act.triggered.connect(lambda: self.edit_file_mapping(file_path))
            menu.addAction(act)

        menu.addSeparator()
        rem = QAction("Remove", self)
        rem.triggered.connect(lambda: self._remove_card_by_path(file_path))
        menu.addAction(rem)
        menu.exec(global_pos)

    def _remove_card_by_path(self, file_path: str):
        """Remove a file by path — called from card context menu."""
        self.remove_file_by_path(file_path)

    def _set_filter(self, filter_type: str):
        """Toggle filter pills (exclusive) and apply to file list."""
        pills = {
            "all": self._pill_all,
            "selected": self._pill_sel,
            "warnings": self._pill_rev,
        }
        for key, pill in pills.items():
            pill.setChecked(key == filter_type)
        self._file_list.apply_filter(filter_type)

    def _update_inventory_bar(self):
        """Refresh stat chips from current file_statuses and card state."""
        total = len(self.file_statuses)
        selected = self._file_list.get_selected_count()
        loaded = sum(1 for s in self.file_statuses.values() if s == 'loaded')
        warnings = sum(1 for s in self.file_statuses.values()
                       if s in ('mapping', 'review', 'failed'))

        self._chip_loaded.setText(f"{loaded} loaded" if total else "0 loaded")
        self._chip_selected.setText(f"{selected} included")
        if hasattr(self, "_manage_samples_btn"):
            self._manage_samples_btn.setEnabled(total > 0)
        if warnings > 0:
            self._chip_warnings.setText(f"\u26a0 {warnings}")
            self._chip_warnings.setVisible(True)
        else:
            self._chip_warnings.setVisible(False)

    def _push_card_meta(self, file_path: str):
        """Extract D50/K from loaded dataset and update the card."""
        _, entry = self._find_loaded_entry_by_file(file_path)
        if not entry:
            return
        dataset = entry.get('data')
        if not dataset:
            return
        # D50 — always available from the grain size curve
        d50_str = ""
        try:
            d50 = dataset.get_d50()
            if d50 is not None:
                d50_str = f"{d50:.2f} mm" if d50 >= 0.01 else f"{d50:.4f} mm"
        except Exception:
            pass
        # K value — try the dataset tab's current_results first, then dataset attr
        k_str = ""
        try:
            # Look for the tab widget that holds computed K-values
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'dataset_tabs_widget'):
                for i in range(self.main_window.dataset_tabs_widget.count()):
                    tab = self.main_window.dataset_tabs_widget.widget(i)
                    if (hasattr(tab, 'dataset') and tab.dataset is dataset
                            and hasattr(tab, 'current_results') and tab.current_results):
                        k_vals = [v for v in tab.current_results.values()
                                  if v is not None and isinstance(v, (int, float)) and v > 0]
                        if k_vals:
                            from statistics import geometric_mean
                            k_mean = geometric_mean(k_vals)
                            k_str = f"{k_mean:.1f} m/d" if k_mean >= 0.1 else f"{k_mean:.2e} m/d"
                        break
        except Exception:
            pass
        self._file_list.update_card_meta(file_path, d50_str, k_str)
        self._file_list.update_card_group(
            file_path,
            getattr(dataset, "group_name", "Ungrouped"),
        )
        # Also refresh the stratigraphy widget for the active card
        self._refresh_stratigraphy(file_path)

    def update_sample_group(self, file_path: str, group_name: str = "Ungrouped") -> None:
        """Refresh the visible group label for a loaded sample card."""
        self._file_list.update_card_group(file_path, group_name)
        _, entry = self._find_loaded_entry_by_file(file_path)
        dataset = entry.get("data") if entry else None
        if dataset is not None:
            try:
                dataset.group_name = group_name
            except Exception:
                pass

    # ── Classification / Stratigraphy ─────────────────────────────────────────

    def _open_classification_dialog(self):
        """Open the Classification System dialog and connect its signal."""
        from gui.classification_dialog import ClassificationDialog
        dlg = ClassificationDialog(current_scheme=self._active_scheme, parent=self.window())
        dlg.scheme_selected.connect(self._on_scheme_changed)
        dlg.exec()

    def open_classification_dialog(self):
        """Public Analysis-menu entry point for classification scheme settings."""
        self._open_classification_dialog()

    def analysis_settings_summary(self) -> str:
        """Compact description of the active global analysis settings."""
        scheme_name = getattr(self._active_scheme, "name", "Classification scheme")
        return (
            f"{self.temp_spinbox.value():.1f} C | "
            f"{self.porosity_mode_combo.currentText()} | {scheme_name}"
        )

    def open_analysis_settings_dialog(self):
        """Open global analysis settings from the top Analysis menu."""
        dlg = QDialog(self.window())
        dlg.setWindowTitle("Analysis Settings")
        dlg.setMinimumWidth(420)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        title = QLabel("Analysis Settings")
        title.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: 14px; font-weight: 700;"
            f" color: {C.TEXT};"
        )
        root.addWidget(title)

        intro = QLabel(
            "These settings affect hydraulic conductivity calculations and "
            "classification across loaded datasets."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 11px;")
        root.addWidget(intro)

        fields = QWidget()
        fields_lay = QVBoxLayout(fields)
        fields_lay.setContentsMargins(0, 2, 0, 0)
        fields_lay.setSpacing(8)

        row_style = (
            f"QLabel {{ color: {C.TEXT_MID}; font-size: 11px; }}"
            f"QComboBox, QDoubleSpinBox {{ background: rgba(255,255,255,0.55);"
            f" border: 1px solid {C.BORDER}; border-radius: 4px;"
            f" padding: 3px 6px; color: {C.TEXT}; }}"
        )

        temp_row = QWidget()
        temp_row.setStyleSheet(row_style)
        temp_lay = QHBoxLayout(temp_row)
        temp_lay.setContentsMargins(0, 0, 0, 0)
        temp_lbl = QLabel("Temperature")
        temp = QDoubleSpinBox()
        temp.setRange(self.temp_spinbox.minimum(), self.temp_spinbox.maximum())
        temp.setDecimals(self.temp_spinbox.decimals())
        temp.setSingleStep(self.temp_spinbox.singleStep())
        temp.setSuffix(" \u00b0C")
        temp.setValue(self.temp_spinbox.value())
        temp.setFixedWidth(100)
        temp_lay.addWidget(temp_lbl)
        temp_lay.addStretch()
        temp_lay.addWidget(temp)
        fields_lay.addWidget(temp_row)

        porosity_row = QWidget()
        porosity_row.setStyleSheet(row_style)
        porosity_lay = QVBoxLayout(porosity_row)
        porosity_lay.setContentsMargins(0, 0, 0, 0)
        porosity_lay.setSpacing(4)
        porosity_lay.addWidget(QLabel("Calculated porosity mode"))
        porosity_combo = QComboBox()
        for i in range(self.porosity_mode_combo.count()):
            porosity_combo.addItem(self.porosity_mode_combo.itemText(i))
        porosity_combo.setCurrentText(self.porosity_mode_combo.currentText())
        porosity_lay.addWidget(porosity_combo)
        fields_lay.addWidget(porosity_row)

        scheme_row = QWidget()
        scheme_row.setStyleSheet(row_style)
        scheme_lay = QHBoxLayout(scheme_row)
        scheme_lay.setContentsMargins(0, 0, 0, 0)
        scheme_lay.setSpacing(8)
        scheme_lbl = QLabel("Classification scheme")
        scheme_value = QLabel(getattr(self._active_scheme, "name", "Current scheme"))
        scheme_value.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: 9px; color: {C.TEXT_MUTED};"
        )
        scheme_lay.addWidget(scheme_lbl)
        scheme_lay.addWidget(scheme_value, 1)
        fields_lay.addWidget(scheme_row)
        root.addWidget(fields)

        actions = QWidget()
        actions_lay = QHBoxLayout(actions)
        actions_lay.setContentsMargins(0, 0, 0, 0)
        actions_lay.setSpacing(6)
        porosity_btn = QPushButton("Dataset Porosity...")
        scheme_btn = QPushButton("Classification Scheme...")
        for btn in (porosity_btn, scheme_btn):
            btn.setStyleSheet(
                f"QPushButton {{ background: {C.BG_RAISED}; border: 1px solid {C.BORDER};"
                f" border-radius: 4px; padding: 5px 9px; color: {C.TEXT_MID}; }}"
                f"QPushButton:hover {{ background: {C.BG_LOW}; color: {C.TEXT}; }}"
            )
        actions_lay.addWidget(porosity_btn)
        actions_lay.addWidget(scheme_btn)
        actions_lay.addStretch()
        root.addWidget(actions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        root.addWidget(buttons)

        def apply_state() -> None:
            self.temp_spinbox.setValue(temp.value())
            idx = self.porosity_mode_combo.findText(porosity_combo.currentText())
            if idx >= 0:
                self.porosity_mode_combo.setCurrentIndex(idx)
            self.sample_info_label.setText(
                f"Analysis settings updated: {self.analysis_settings_summary()}"
            )

        def apply_and_accept() -> None:
            apply_state()
            dlg.accept()

        def open_dataset_porosity() -> None:
            apply_state()
            self.open_porosity_dialog()

        def open_scheme() -> None:
            apply_state()
            self._open_classification_dialog()
            scheme_value.setText(getattr(self._active_scheme, "name", "Current scheme"))

        porosity_btn.clicked.connect(open_dataset_porosity)
        scheme_btn.clicked.connect(open_scheme)
        buttons.accepted.connect(apply_and_accept)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()

    def _on_scheme_changed(self, scheme: GrainClassificationScheme):
        """Store the new active scheme, refresh stratigraphy, emit to main window."""
        self._active_scheme = scheme
        self._refresh_stratigraphy()
        self.scheme_changed.emit(scheme)

    def _refresh_stratigraphy(self, file_path: str | None = None):
        """Classify the active dataset and update the stratigraphy widget.

        If file_path is None, uses the currently active card path.
        """
        # Determine the active file path
        if file_path is None:
            # Use the currently selected / active card
            active = self._file_list.get_active_path()
            if active is None:
                self._strata_widget.update_result(None)
                return
            file_path = active

        _, entry = self._find_loaded_entry_by_file(file_path)
        if not entry:
            self._strata_widget.update_result(None)
            return

        dataset = entry.get('data')
        if not dataset or not hasattr(dataset, 'classify'):
            self._strata_widget.update_result(None)
            return

        # Try to get k_mean for permeability class
        k_mean_ms = None
        try:
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'dataset_tabs_widget'):
                for i in range(self.main_window.dataset_tabs_widget.count()):
                    tab = self.main_window.dataset_tabs_widget.widget(i)
                    if (hasattr(tab, 'dataset') and tab.dataset is dataset
                            and hasattr(tab, 'current_results') and tab.current_results):
                        from statistics import geometric_mean
                        k_vals = [v for v in tab.current_results.values()
                                  if isinstance(v, (int, float)) and v > 0]
                        if k_vals:
                            # Convert from m/day to m/s (÷86400)
                            k_mean_ms = geometric_mean(k_vals) / 86400.0
                        break
        except Exception:
            pass

        try:
            result = dataset.classify(scheme=self._active_scheme, k_mean_ms=k_mean_ms)
            self._strata_widget.update_result(result)
        except Exception:
            self._strata_widget.update_result(None)

    def _build_add_data_menu(self, parent=None) -> QMenu:
        """Create the shared import-path menu used by sidebar entry points."""
        menu = QMenu(parent or self)
        processed_action = QAction("Processed Sieve Data...", menu)
        processed_action.triggered.connect(lambda _checked=False: self.add_files("processed"))
        menu.addAction(processed_action)

        raw_action = QAction("Raw Sieve Weighings...", menu)
        raw_action.triggered.connect(lambda _checked=False: self.add_files("raw_sieve"))
        menu.addAction(raw_action)
        return menu

    def _install_add_data_menu(self, button: QPushButton) -> None:
        button.setMenu(self._build_add_data_menu(button))
        button.setToolTip("Choose whether the files contain processed sieve data or raw sieve weighings")

    def _show_add_data_menu_for_drop_zone(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        menu = self._build_add_data_menu(self)
        global_pos = (
            event.globalPosition().toPoint()
            if hasattr(event, "globalPosition")
            else event.globalPos()
        )
        menu.exec(global_pos)

    def add_files(self, data_mode: str = "processed"):
        """Add multiple files for batch processing"""
        if data_mode not in {"processed", "raw_sieve"}:
            data_mode = "processed"

        title = (
            "Add Raw Sieve Weighing Files"
            if data_mode == "raw_sieve"
            else "Add Processed Sieve Data Files"
        )
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            title,
            "",
            "All Supported (*.csv *.xlsx *.xls);;CSV files (*.csv);;Excel files (*.xlsx *.xls);;All files (*.*)"
        )

        if file_paths:
            # Expand Excel files with multiple sheets
            expanded_files = []
            already_added = []

            # Separate Excel files from others for batch processing
            excel_files = [f for f in file_paths if f.endswith(('.xlsx', '.xls')) and f not in self.file_statuses]
            other_files = [f for f in file_paths if not f.endswith(('.xlsx', '.xls')) and f not in self.file_statuses]
            already_added = [os.path.basename(f) for f in file_paths if f in self.file_statuses]

            # Handle Excel files with smart batch detection
            if excel_files:
                excel_expanded = self.handle_batch_multisheet_excel(excel_files)
                if excel_expanded is None:  # User cancelled entire batch
                    return
                expanded_files.extend(excel_expanded)

            # Add other files directly
            expanded_files.extend(other_files)

            if expanded_files:
                if data_mode == "raw_sieve":
                    auto_entries = [
                        entry for entry in expanded_files
                        if self._file_entry_is_excel(entry)
                    ]
                    mapping_entries = [
                        entry for entry in expanded_files
                        if not self._file_entry_is_excel(entry)
                    ]
                    if mapping_entries:
                        self._queue_raw_sieve_files_for_mapping(mapping_entries, already_added)
                    if auto_entries:
                        self._track_pending_file_entries(auto_entries)
                        self.process_files_with_immediate_tabs(auto_entries, import_intent="raw_sieve")
                        self.update_ui_state()
                        message = f"Processing {len(auto_entries)} raw Excel sheet(s)..."
                        if mapping_entries:
                            message += f" {len(mapping_entries)} non-Excel item(s) queued for mapping."
                        self.sample_info_label.setText(message)
                    return

                self._track_pending_file_entries(expanded_files)

                # Create tabs immediately for all files, then try to load them
                self.process_files_with_immediate_tabs(expanded_files)

                self.update_ui_state()

                # Provide feedback on what was processed
                message = f"Processing {len(expanded_files)} file(s)/sheet(s)..."
                if already_added:
                    if len(already_added) <= 3:
                        message += f" (Skipped: {', '.join(already_added)})"
                    else:
                        message += f" (Skipped {len(already_added)} duplicate files)"

                self.sample_info_label.setText(message)
            else:
                if len(already_added) == 1:
                    QMessageBox.information(self, "No New Files", f"'{already_added[0]}' is already in the list.")
                elif already_added:
                    QMessageBox.information(self, "No New Files", f"All {len(already_added)} selected files are already in the list.")

    def _queue_raw_sieve_files_for_mapping(self, file_entries: list, already_added: list | None = None):
        """Register raw-weighing files as neutral mapping-required items."""
        already_added = already_added or []
        mapping_message = (
            "Raw sieve weighing data is ready for column mapping. Map Sieve Size, "
            "Weight of Empty Sieve, and Weight of Sieve + Sample."
        )

        for file_entry in file_entries:
            file_key = self._file_entry_key(file_entry)
            display_name = self._file_entry_display_name(file_entry)
            _, sheet_name, _ = self._file_entry_parts(file_entry)
            mapping_state = {
                "raw_sieve_mode": True,
                "calculated_selection_mode": "column",
                "current_sheet": sheet_name,
                "checked_sheets": [sheet_name] if sheet_name else [],
                "import_intent": "raw_sieve",
            }
            mapping_state["import_provenance"] = manual_mapping_provenance(mapping_state)

            self.file_statuses[file_key] = 'mapping'
            self.file_mapping_states[file_key] = mapping_state
            self.add_file_to_table(file_key, 'mapping', display_name=display_name)
            self.mapping_required.emit(file_key, mapping_message)

        self.update_ui_state()
        message = f"{len(file_entries)} raw weighing item(s) queued for mapping"
        if already_added:
            message += f" ({len(already_added)} duplicate skipped)"
        self.sample_info_label.setText(message)

    def handle_batch_multisheet_excel(self, excel_files: list):
        """
        Smart batch handler for Excel files with multiple sheets.
        For multi-file batches, choose sheet names once and apply those names
        to every workbook that contains them.
        Returns: List of file entries (paths or tuples), or None if cancelled
        """
        import pandas as pd

        def sheet_key(name: str) -> str:
            return str(name).strip().casefold()

        file_sheet_names = {}
        single_sheet_files = []
        multi_sheet_files = []
        error_files = []

        for file_path in excel_files:
            try:
                excel_file = pd.ExcelFile(file_path)
                try:
                    sheet_names = list(excel_file.sheet_names)
                finally:
                    excel_file.close()
                file_sheet_names[file_path] = sheet_names

                if len(sheet_names) == 1:
                    single_sheet_files.append(file_path)
                elif len(sheet_names) > 1:
                    multi_sheet_files.append(file_path)
                else:
                    error_files.append(file_path)
            except Exception as e:
                error_files.append(file_path)

        expanded_files = []

        # Handle single-sheet files (no dialog needed)
        expanded_files.extend(single_sheet_files)

        if len(multi_sheet_files) == 1:
            result = self.handle_multisheet_excel(multi_sheet_files[0])
            if result is None:
                expanded_files.append(multi_sheet_files[0])
            elif result:
                expanded_files.extend(result)
            else:
                return None

        elif len(multi_sheet_files) > 1:
            from gui.sheet_selector import SheetSelectorDialog

            sheet_labels = {}
            sheet_order = []
            sheet_counts = {}
            file_sheet_lookup = {}

            for file_path in multi_sheet_files:
                lookup = {}
                seen_in_file = set()
                for sheet_name in file_sheet_names.get(file_path, []):
                    key = sheet_key(sheet_name)
                    if key not in lookup:
                        lookup[key] = sheet_name
                    if key not in sheet_labels:
                        sheet_labels[key] = sheet_name
                        sheet_order.append(key)
                    if key not in seen_in_file:
                        sheet_counts[key] = sheet_counts.get(key, 0) + 1
                        seen_in_file.add(key)
                file_sheet_lookup[file_path] = lookup

            shared_keys = {
                key for key, count in sheet_counts.items()
                if count == len(multi_sheet_files)
            }
            ordered_keys = (
                [key for key in sheet_order if key in shared_keys]
                + [key for key in sheet_order if key not in shared_keys]
            )
            batch_sheet_names = [sheet_labels[key] for key in ordered_keys]
            checked_sheet_names = [
                sheet_labels[key] for key in ordered_keys if key in shared_keys
            ]

            first_file = multi_sheet_files[0]
            dialog = SheetSelectorDialog(first_file, self)
            dialog.setWindowTitle(f"Select Sheets for {len(multi_sheet_files)} Workbooks")

            set_batch_options = getattr(dialog, "set_batch_sheet_options", None)
            if callable(set_batch_options):
                set_batch_options(
                    batch_sheet_names,
                    sheet_counts,
                    len(multi_sheet_files),
                    checked_sheet_names,
                )
            elif hasattr(dialog, "info_label"):
                dialog.info_label.setText(
                    f"Select sheet names to import from {len(multi_sheet_files)} workbooks."
                )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_sheets = dialog.get_selected_sheets()
                if not selected_sheets:
                    return None

                selected_keys = [sheet_key(sheet) for sheet in selected_sheets]
                for file_path in multi_sheet_files:
                    lookup = file_sheet_lookup.get(file_path, {})
                    for key in selected_keys:
                        sheet = lookup.get(key)
                        if sheet:
                            expanded_files.append((file_path, sheet))
            else:
                return None

        # Handle error files (treat as normal)
        expanded_files.extend(error_files)

        return expanded_files

    def handle_multisheet_excel(self, file_path: str):
        """
        Handle single multi-sheet Excel file by letting user select sheets.
        Returns: List of (file_path, sheet_name) tuples, or None for single sheet, or [] for cancelled
        """
        try:
            import pandas as pd
            excel_file = pd.ExcelFile(file_path)
            try:
                sheet_names = list(excel_file.sheet_names)
            finally:
                excel_file.close()

            # If only one sheet, treat as normal file
            if len(sheet_names) == 1:
                return None  # Signal to treat as normal file

            # Multiple sheets - show selector dialog
            from gui.sheet_selector import SheetSelectorDialog
            dialog = SheetSelectorDialog(file_path, self)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_sheets = dialog.get_selected_sheets()
                if not selected_sheets:
                    return []  # User cancelled or selected none

                # Return list of (file_path, sheet_name) tuples
                return [(file_path, sheet) for sheet in selected_sheets]
            else:
                return []  # User cancelled

        except Exception as e:
            # Error reading Excel file, treat as normal file
            return None

    def add_file_to_table(self, file_path: str, status: str, display_name: str = None):
        """Add a file to the samples table"""
        row = self.samples_table.rowCount()
        self.samples_table.insertRow(row)

        # File name (use custom display name if provided)
        file_name = display_name or self._format_file_display_name(file_path)
        file_item = QTableWidgetItem(file_name)
        file_item.setData(Qt.ItemDataRole.UserRole, file_path)  # Store full path/key
        file_item.setToolTip(file_path)
        self.samples_table.setItem(row, 0, file_item)

        # Status with icon and text
        status_text = self.get_status_text(status)
        status_item = QTableWidgetItem(status_text)
        status_item.setData(Qt.ItemDataRole.UserRole, status)
        status_item.setToolTip(self.get_status_tooltip(status))
        self.samples_table.setItem(row, 1, status_item)

        # Update visual card list
        self._file_list.add_card(file_path, file_name, status)

    def get_status_text(self, status: str) -> str:
        """Get descriptive status text with icon"""
        status_map = {
            'pending': 'Processing...',
            'mapping': 'Map Columns',
            'failed': 'Failed',
            'review': 'Needs Review',
            'loaded': 'Loaded'
        }
        return status_map.get(status, 'Unknown')

    def get_status_tooltip(self, status: str) -> str:
        """Get tooltip text for status"""
        tooltip_map = {
            'pending': 'File is being processed',
            'mapping': 'Raw sieve weighing file is waiting for column mapping',
            'failed': 'File failed validation - contains errors',
            'review': 'File needs manual column mapping',
            'loaded': 'File successfully loaded and ready for analysis'
        }
        return tooltip_map.get(status, 'Unknown status')

    def show_context_menu(self, position):
        """Show context menu for file operations"""
        # Get the selected row
        item = self.samples_table.itemAt(position)
        if item is None:
            return

        row = item.row()
        file_item = self.samples_table.item(row, 0)
        status_item = self.samples_table.item(row, 1)

        if not file_item or not status_item:
            return

        file_path = file_item.data(Qt.ItemDataRole.UserRole)
        status = status_item.data(Qt.ItemDataRole.UserRole)

        # Create context menu
        menu = QMenu(self)

        # Add actions based on status
        if status in ('mapping', 'review'):
            map_action = QAction("🗺️ Map Columns...", self)
            map_action.triggered.connect(lambda: self.edit_file_mapping(file_path))
            menu.addAction(map_action)

        elif status == 'loaded':
            info_action = QAction("ℹ️ Show Info...", self)
            info_action.triggered.connect(lambda: self.show_file_info(file_path))
            menu.addAction(info_action)

            menu.addSeparator()

            edit_action = QAction("✏️ Edit Mapping...", self)
            edit_action.triggered.connect(lambda: self.edit_file_mapping(file_path))
            menu.addAction(edit_action)

        elif status == 'failed':
            fix_action = QAction("🔧 Fix/Remap...", self)
            fix_action.triggered.connect(lambda: self.edit_file_mapping(file_path))
            menu.addAction(fix_action)

        # Always show remove option
        menu.addSeparator()
        remove_action = QAction("🗑️ Remove from List", self)
        remove_action.triggered.connect(lambda: self.remove_file_at_row(row))
        menu.addAction(remove_action)

        # Show menu at cursor position
        menu.exec(self.samples_table.viewport().mapToGlobal(position))

    def remove_file_at_row(self, row: int):
        """Remove a file at a specific row"""
        if row >= 0:
            file_item = self.samples_table.item(row, 0)
            if file_item is not None:
                self.remove_file_by_path(file_item.data(Qt.ItemDataRole.UserRole))

    def edit_file_mapping(self, file_path: str):
        """Open column mapping dialog for a specific file"""
        try:
            actual_file_path, sheet_name = self._split_sheet_key(file_path)
            dialog = ColumnMapperDialog(
                actual_file_path,
                self,
                self.window(),
                sheet_name=sheet_name,
                initial_state=self.file_mapping_states.get(file_path),
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                if getattr(dialog, "_batch_apply_committed", False):
                    return
                mapping_results = dialog.get_mapping_results()
                if not mapping_results:
                    QMessageBox.warning(self, "No Data", "No sheet data was extracted.")
                    return
                self._apply_mapping_results(
                    file_path,
                    mapping_results,
                    forced_sheet_name=sheet_name,
                    mapping_state=dialog.get_mapping_state(),
                )

        except Exception as e:
            actual_file_path, sheet_name = self._split_sheet_key(file_path)
            file_name = os.path.basename(actual_file_path)
            if sheet_name:
                file_name = f"{file_name} [{sheet_name}]"
            QMessageBox.warning(self, "Error", f"Failed to edit {file_name}:\n{str(e)}")

    def show_file_info(self, file_path: str):
        """Show tabbed inspector: Stats + Raw Data."""
        sample_name = self.extract_sample_name(file_path)
        if sample_name not in self.loaded_samples:
            QMessageBox.information(self, "Inspect", "Dataset not yet loaded.")
            return

        dataset = self.loaded_samples[sample_name]['data']

        def fmt(v, f):
            return format(v, f) if v is not None else 'N/A'

        d10 = dataset.get_d10()
        d30 = dataset.get_d30()
        d50 = dataset.get_d50()
        d60 = dataset.get_d60()
        cu  = dataset.get_uniformity_coefficient()

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Inspect — {dataset.sample_name}")
        dlg.resize(560, 480)
        dlg_v = QVBoxLayout(dlg)
        dlg_v.setContentsMargins(12, 12, 12, 12)
        dlg_v.setSpacing(10)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # ── Tab 1: Stats ──────────────────────────────────────────────
        stats_text = (
            f"File:        {os.path.basename(file_path)}\n"
            f"Sample:      {dataset.sample_name}\n"
            f"Temperature: {dataset.temperature} °C\n"
            f"Porosity:    {dataset.porosity}\n"
            f"Data Points: {len(dataset.particle_sizes)}\n"
            f"\n"
            f"Grain Size Range\n"
            f"  Largest:   {max(dataset.particle_sizes):.4f} mm\n"
            f"  Smallest:  {min(dataset.particle_sizes):.4f} mm\n"
            f"\n"
            f"Characteristic Sizes\n"
            f"  D10: {fmt(d10, '.4f')} mm\n"
            f"  D30: {fmt(d30, '.4f')} mm\n"
            f"  D50: {fmt(d50, '.4f')} mm  (median)\n"
            f"  D60: {fmt(d60, '.4f')} mm\n"
            f"\n"
            f"Soil Classification:        {dataset.classify(scheme=self._active_scheme).label}\n"
            f"Uniformity Coefficient Cu:  {fmt(cu, '.3f')}\n"
        )
        stats_edit = QTextEdit()
        stats_edit.setReadOnly(True)
        stats_edit.setFont(QFont(F.MONO, F.SZ_SM))
        stats_edit.setPlainText(stats_text)
        stats_edit.setFrameShape(QFrame.Shape.NoFrame)
        tabs.addTab(stats_edit, "Stats")

        # ── Tab 2: Raw Data ───────────────────────────────────────────
        raw_tbl = QTableWidget(len(dataset.particle_sizes), 2)
        raw_tbl.setHorizontalHeaderLabels(["Grain Size (mm)", "% Passing"])
        raw_tbl.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        raw_tbl.verticalHeader().setVisible(False)
        raw_tbl.setAlternatingRowColors(True)
        raw_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        raw_tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        raw_tbl.setFont(QFont(F.MONO, F.SZ_SM))
        for i, (gs, pp) in enumerate(
                zip(dataset.particle_sizes, dataset.percent_passing)):
            raw_tbl.setItem(i, 0, QTableWidgetItem(f"{gs:.6g}"))
            raw_tbl.setItem(i, 1, QTableWidgetItem(f"{pp:.4g}"))
        tabs.addTab(raw_tbl, f"Raw Data  ({len(dataset.particle_sizes)} pts)")

        dlg_v.addWidget(tabs)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dlg.reject)
        dlg_v.addWidget(btn_box)
        dlg.exec()

    def show_file_info(self, file_path: str):
        """Show concept-aligned data inspector for a loaded dataset."""
        _, entry = self._find_loaded_entry_by_file(file_path)
        if not entry:
            QMessageBox.information(self, "Inspect", "Dataset not yet loaded.")
            return

        dataset = entry['data']
        ds_tab = self._find_dataset_tab_for_dataset(dataset)
        mapping_state = (
            entry.get('mapping_state')
            or getattr(dataset, '_source_mapping_state', None)
            or self.file_mapping_states.get(file_path)
        )
        dlg = DataInspectorDialog(
            dataset=dataset,
            scheme=self._active_scheme,
            file_path=file_path,
            dataset_tab=ds_tab,
            mapping_state=mapping_state,
            parent=self,
        )
        dlg.exec()

    def show_file_log(self, file_path: str):
        """Show the load-time validation log for a dataset."""
        host_window = self.window()
        if host_window is not None and hasattr(host_window, "show_log_overlay"):
            host_window.show_log_overlay(file_key=file_path)
            return

        _, entry = self._find_loaded_entry_by_file(file_path)
        if not entry:
            QMessageBox.information(self, "Log", "Dataset not yet loaded.")
            return

        dataset = entry['data']
        msgs = getattr(dataset, 'validation_messages', [])

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Load Log — {dataset.sample_name}")
        dlg.resize(500, 340)
        dlg_v = QVBoxLayout(dlg)
        dlg_v.setContentsMargins(12, 12, 12, 12)
        dlg_v.setSpacing(10)

        log_edit = QTextEdit()
        log_edit.setReadOnly(True)
        log_edit.setFont(QFont(F.MONO, F.SZ_SM))
        log_edit.setFrameShape(QFrame.Shape.NoFrame)

        if not msgs:
            log_edit.setPlainText("No validation messages — dataset loaded cleanly.")
        else:
            lines = []
            for m in msgs:
                severity = getattr(m, 'severity', None)
                sev_str = severity.name if severity is not None else "INFO"
                title   = getattr(m, 'title', '')
                message = getattr(m, 'message', '')
                lines.append(f"[{sev_str}]  {title}")
                if message:
                    lines.append(f"        {message}")
                lines.append("")
            log_edit.setPlainText("\n".join(lines).strip())

        dlg_v.addWidget(log_edit)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dlg.reject)
        dlg_v.addWidget(btn_box)
        dlg.exec()

    def show_file_props(self, file_path: str):
        """Per-dataset properties editor: temperature + porosity override."""
        _, entry = self._find_loaded_entry_by_file(file_path)
        if not entry:
            QMessageBox.information(self, "Props", "Dataset not yet loaded.")
            return

        dataset = entry['data']

        # Find the dataset tab so we can push recalculation
        ds_tab = self._find_dataset_tab_for_dataset(dataset)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Properties — {dataset.sample_name}")
        dlg.setFixedWidth(340)
        dlg_v = QVBoxLayout(dlg)
        dlg_v.setContentsMargins(16, 16, 16, 12)
        dlg_v.setSpacing(12)

        _LBL_SS = f"font-size: {F.SZ_SM}pt; color: {C.TEXT_MID};"

        # Temperature
        temp_row = QHBoxLayout()
        temp_lbl = QLabel("Temperature")
        temp_lbl.setStyleSheet(_LBL_SS)
        temp_spin = QDoubleSpinBox()
        temp_spin.setRange(0, 50)
        temp_spin.setSuffix(" °C")
        temp_spin.setDecimals(1)
        temp_spin.setValue(float(getattr(dataset, 'temperature', 20)))
        temp_spin.setFixedWidth(90)
        temp_row.addWidget(temp_lbl)
        temp_row.addStretch()
        temp_row.addWidget(temp_spin)
        dlg_v.addLayout(temp_row)

        # Porosity
        por_row = QHBoxLayout()
        por_lbl = QLabel("Porosity")
        por_lbl.setStyleSheet(_LBL_SS)
        por_spin = QDoubleSpinBox()
        por_spin.setRange(0.10, 0.80)
        por_spin.setSingleStep(0.01)
        por_spin.setDecimals(4)
        current_por = float(getattr(dataset, 'current_porosity', None)
                            or getattr(dataset, 'porosity', 0.3))
        por_spin.setValue(current_por)
        por_spin.setFixedWidth(90)
        por_row.addWidget(por_lbl)
        por_row.addStretch()
        por_row.addWidget(por_spin)
        dlg_v.addLayout(por_row)

        # Calculated porosity hint
        calc_por = getattr(dataset, 'calculated_porosity', None)
        if calc_por is not None:
            mode_label = (
                dataset.calculated_porosity_mode_label()
                if hasattr(dataset, 'calculated_porosity_mode_label')
                else "Simple formula"
            )
            source_label = (
                dataset.porosity_source_label()
                if hasattr(dataset, 'porosity_source_label')
                else f"Calculated ({mode_label})"
            )
            hint = QLabel(f"Auto ({mode_label}): {calc_por:.4f}\nUsing: {source_label}")
            hint.setStyleSheet(f"font-size: {F.SZ_XS}pt; color: {C.SB_MUTED};")
            hint.setWordWrap(True)
            dlg_v.addWidget(hint)

        dlg_v.addSpacing(4)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply |
            QDialogButtonBox.StandardButton.Close)
        apply_btn = btn_box.button(QDialogButtonBox.StandardButton.Apply)

        def _apply():
            dataset.temperature = temp_spin.value()
            new_por = por_spin.value()
            dataset.current_porosity = new_por
            dataset.porosity = new_por
            if ds_tab is not None:
                if hasattr(ds_tab, 'porosity'):
                    ds_tab.porosity = new_por
                if hasattr(ds_tab, 'statistics_tab'):
                    ds_tab.statistics_tab.porosity = new_por
                    ds_tab.statistics_tab.update_display()
                if hasattr(ds_tab, 'calculate_k_values') and \
                        hasattr(ds_tab, 'current_results') and ds_tab.current_results:
                    ds_tab.calculate_k_values()
            self._push_card_meta(file_path)

        apply_btn.clicked.connect(_apply)
        btn_box.rejected.connect(dlg.reject)
        dlg_v.addWidget(btn_box)
        dlg.exec()

    def update_file_in_table(self, file_path: str, status: str):
        """Update file status in table"""
        for row in range(self.samples_table.rowCount()):
            file_item = self.samples_table.item(row, 0)
            if file_item and file_item.data(Qt.ItemDataRole.UserRole) == file_path:
                # Update status
                status_item = self.samples_table.item(row, 1)
                status_item.setText(self.get_status_text(status))
                status_item.setData(Qt.ItemDataRole.UserRole, status)
                status_item.setToolTip(self.get_status_tooltip(status))
                break
        # Update visual card
        self._file_list.update_card_status(file_path, status)

    def register_external_file(self, file_path: str, dataset):
        """Register a file that was loaded externally (e.g., from recent files/sessions)"""
        self._remove_loaded_entries_for_file(file_path)
        mapping_state = getattr(dataset, "_source_mapping_state", None) or self.file_mapping_states.get(file_path)
        if mapping_state:
            self.file_mapping_states[file_path] = dict(mapping_state)
        provenance = getattr(dataset, "_source_import_provenance", None)
        # Check if already in the list
        if file_path in self.file_statuses:
            # Already tracked, just update status
            self.file_statuses[file_path] = 'loaded'
            self.update_file_in_table(file_path, 'loaded')
            sample_name = dataset.sample_name
        else:
            # New file, add to tracking
            self.file_statuses[file_path] = 'loaded'
            sample_name = dataset.sample_name
            # Add to table
            self.add_file_to_table(file_path, 'loaded')

        self.loaded_samples[sample_name] = {
            'file_path': file_path,
            'data': dataset,
            'datasets': [dataset],
            'status': 'loaded',
            'mapping_state': self.file_mapping_states.get(file_path),
            'import_provenance': provenance,
        }

        self._push_card_meta(file_path)
        self._update_inventory_bar()
        self.update_ui_state()
        self.sample_info_label.setText(f"{len(self.loaded_samples)} sample(s) loaded")

    def register_external_issue(self, file_path: str, detail: str, *, status: str = 'review'):
        """Track a file opened outside the sidebar import flow that still needs user attention."""
        self._remove_loaded_entries_for_file(file_path)
        self.file_statuses[file_path] = status

        if self._find_table_row_for_file(file_path) >= 0:
            self.update_file_in_table(file_path, status)
        else:
            self.add_file_to_table(file_path, status)

        self._file_list.update_card_meta(file_path, "", "")
        self._update_inventory_bar()
        self.update_ui_state()

        file_name = self._format_file_display_name(file_path)
        if status == 'failed':
            self.sample_info_label.setText(f"Needs fixing: {file_name}")
        else:
            self.sample_info_label.setText(f"Needs review: {file_name}")

    def review_failed_files(self):
        """Open manual column mapping for files that need review"""
        review_files = [
            path for path, status in self.file_statuses.items()
            if status in ('mapping', 'review')
        ]

        for file_path in review_files:
            try:
                actual_file_path, sheet_name = self._split_sheet_key(file_path)
                dialog = ColumnMapperDialog(
                    actual_file_path,
                    self,
                    self.window(),
                    sheet_name=sheet_name,
                    initial_state=self.file_mapping_states.get(file_path),
                )
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    if getattr(dialog, "_batch_apply_committed", False):
                        continue
                    mapping_results = dialog.get_mapping_results()
                    if not mapping_results:
                        continue
                    self._apply_mapping_results(
                        file_path,
                        mapping_results,
                        forced_sheet_name=sheet_name,
                        mapping_state=dialog.get_mapping_state(),
                    )

            except Exception as e:
                actual_file_path, sheet_name = self._split_sheet_key(file_path)
                file_name = os.path.basename(actual_file_path)
                if sheet_name:
                    file_name = f"{file_name} [{sheet_name}]"
                QMessageBox.warning(self, "Error", f"Failed to process {file_name}:\n{str(e)}")

        self.update_ui_state()

    def remove_selected_file(self):
        """Remove selected file from the table"""
        current_row = self.samples_table.currentRow()
        if current_row >= 0:
            file_item = self.samples_table.item(current_row, 0)
            if file_item is not None:
                self.remove_file_by_path(file_item.data(Qt.ItemDataRole.UserRole))
        else:
            self.remove_file_btn.setEnabled(False)

    def _find_table_row_for_file(self, file_path: str) -> int:
        for row in range(self.samples_table.rowCount()):
            item = self.samples_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == file_path:
                return row
        return -1

    def remove_file_by_path(
        self,
        file_path: str,
        *,
        sync_workspace: bool = True,
        announce: bool = True,
    ) -> bool:
        """Remove a file from the sidebar inventory and optionally its open tabs."""
        if not file_path:
            return False

        if sync_workspace:
            host_window = self.window()
            if host_window and host_window is not self and hasattr(host_window, "_remove_tabs_for_file"):
                host_window._remove_tabs_for_file(file_path)

        row = self._find_table_row_for_file(file_path)
        had_tracking = file_path in self.file_statuses
        had_mapping = file_path in self.file_mapping_states
        removed_entries = self._remove_loaded_entries_for_file(file_path)

        self.file_statuses.pop(file_path, None)
        self.file_mapping_states.pop(file_path, None)
        self._file_list.remove_card(file_path)

        if row >= 0:
            self.samples_table.removeRow(row)

        removed = row >= 0 or had_tracking or had_mapping or bool(removed_entries)
        if removed:
            self.update_ui_state()
            if announce:
                self.sample_info_label.setText(f"Removed: {self._format_file_display_name(file_path)}")

        return removed

    def clear_all_files(self):
        """Clear all loaded files"""
        total_files = len(self.file_statuses)
        if total_files > 0:
            reply = QMessageBox.question(
                self, "Clear All",
                f"Remove all {total_files} files?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.loaded_samples.clear()
                self.file_mapping_states.clear()
                self.file_statuses.clear()
                self.samples_table.setRowCount(0)
                self._file_list.clear_cards()
                self.update_ui_state()
                self.sample_info_label.setText("All files cleared")

    def on_sample_selection_changed(self):
        """Handle sample selection change"""
        current_row = self.samples_table.currentRow()
        if current_row >= 0:
            file_item = self.samples_table.item(current_row, 0)
            file_path = file_item.data(Qt.ItemDataRole.UserRole)
            status_item = self.samples_table.item(current_row, 1)
            status = status_item.data(Qt.ItemDataRole.UserRole)

            # Highlight the active card
            self._file_list.set_active(file_path)

            # Update sample info
            file_name = os.path.basename(file_path)
            self.sample_info_label.setText(f"Selected: {file_name} ({status})")

            # Update UI state
            self.remove_file_btn.setEnabled(True)

            # If this is a loaded dataset, emit signal
            sample_name, _ = self._find_loaded_entry_by_file(file_path)
            if sample_name and status == 'loaded':
                self.sample_selected.emit(sample_name)
        else:
            self._file_list.set_active(None)
            self.remove_file_btn.setEnabled(False)


    def extract_sample_name(self, file_path):
        """Extract a clean sample name from file path"""
        import os
        actual_path, sheet_name = self._split_sheet_key(file_path)
        base_name = os.path.basename(actual_path)
        # Remove extension
        name = os.path.splitext(base_name)[0]
        # Clean up common prefixes/suffixes
        name = name.replace('_grainsize', '').replace('_sieve', '').replace('_data', '')
        if sheet_name:
            name = f"{name} [{sheet_name}]"
        return name if name else base_name

    def _format_file_display_name(self, file_path: str) -> str:
        actual_path, sheet_name = self._split_sheet_key(file_path)
        file_name = os.path.basename(actual_path)
        if sheet_name:
            return f"{file_name} [{sheet_name}]"
        return file_name

    def _split_sheet_key(self, file_path: str):
        if ":::" in file_path:
            return file_path.split(":::", 1)
        return file_path, None

    def _find_loaded_entry_by_file(self, file_path: str):
        for sample_name, entry in self.loaded_samples.items():
            if entry.get('file_path') == file_path:
                return sample_name, entry
        return None, None

    def _record_log_event(self, event: Mapping) -> None:
        host_window = self.window()
        if host_window is not None and hasattr(host_window, "record_log_event"):
            host_window.record_log_event(event)

    def _record_manual_import_event(self, file_path: str, dataset) -> None:
        provenance = getattr(dataset, "_source_import_provenance", None) or {}
        data_type = provenance.get("data_type") or "processed_curve"
        data_label = "raw sieve weights" if data_type == "raw_sieve" else "processed curve"
        context = dict(provenance)
        context.update(
            {
                "file_key": file_path,
                "sample_name": getattr(dataset, "sample_name", ""),
                "pathway": "manual mapping",
                "data_type": data_type,
            }
        )
        self._record_log_event(
            {
                "level": "INFO",
                "source": "data_loader",
                "message": f"Loaded {dataset.sample_name} as {data_label} via manual mapping.",
                "file_key": file_path,
                "context": context,
            }
        )

    def _find_dataset_tab_for_dataset(self, dataset):
        if not hasattr(self, 'main_window') or not hasattr(self.main_window, 'dataset_tabs_widget'):
            return None

        for i in range(self.main_window.dataset_tabs_widget.count()):
            tab = self.main_window.dataset_tabs_widget.widget(i)
            if hasattr(tab, 'dataset') and tab.dataset is dataset:
                return tab
        return None

    def _remove_loaded_entries_for_file(self, file_path: str):
        removed = []
        for sample_name, entry in list(self.loaded_samples.items()):
            if entry.get('file_path') == file_path:
                removed.append((sample_name, entry))
                del self.loaded_samples[sample_name]
        return removed

    def _apply_mapping_results(
        self,
        file_path: str,
        mapping_results: list,
        *,
        forced_sheet_name: str | None = None,
        mapping_state: dict | None = None,
    ):
        from data_loader import GrainSizeData

        created_datasets = []
        for mapping in mapping_results:
            sample_name = mapping['sample_name']
            sheet_name = mapping.get('sheet_name') or forced_sheet_name
            if sheet_name and f"[{sheet_name}]" not in sample_name:
                sample_name = f"{sample_name} [{sheet_name}]"

            dataset = GrainSizeData(
                sample_name=sample_name,
                temperature=mapping['temperature'],
                porosity=mapping['porosity'],
                particle_sizes=mapping['particle_sizes'],
                percent_passing=mapping['percent_passing'],
                file_path=file_path
            )
            source_mapping_state = dict(mapping_state or {})
            if source_mapping_state and not source_mapping_state.get("import_provenance"):
                source_mapping_state["import_provenance"] = manual_mapping_provenance(source_mapping_state)
            provenance = (
                source_mapping_state.get("import_provenance")
                if source_mapping_state
                else manual_mapping_provenance({"current_sheet": sheet_name})
            )
            dataset._source_mapping_state = source_mapping_state
            dataset._source_import_provenance = dict(provenance)
            created_datasets.append(dataset)

        if not created_datasets:
            return

        self._remove_loaded_entries_for_file(file_path)
        if created_datasets[0]._source_mapping_state:
            self.file_mapping_states[file_path] = created_datasets[0]._source_mapping_state

        sample_key = created_datasets[0].sample_name
        sheet_names = [(mapping.get('sheet_name') or forced_sheet_name or '') for mapping in mapping_results]
        entry = {
            'file_path': file_path,
            'data': created_datasets[0],
            'datasets': created_datasets,
            'status': 'loaded',
            'sheet_names': sheet_names,
            'mapping_state': self.file_mapping_states.get(file_path),
            'import_provenance': getattr(created_datasets[0], '_source_import_provenance', None),
        }
        self.loaded_samples[sample_key] = entry

        self.file_statuses[file_path] = 'loaded'
        self.update_file_in_table(file_path, 'loaded')
        self._push_card_meta(file_path)
        self._update_inventory_bar()

        self.dataset_loaded_successfully.emit(created_datasets, file_path)
        record_manual_import = getattr(self, "_record_manual_import_event", None)
        if callable(record_manual_import):
            for dataset in created_datasets:
                record_manual_import(file_path, dataset)

        if any(sheet_names):
            summary = ", ".join(name for name in sheet_names if name)
            self.sample_info_label.setText(f"\u2705 Loaded {len(created_datasets)} sheet(s): {summary}")
        else:
            self.sample_info_label.setText(f"\u2705 Loaded {len(created_datasets)} sheet(s)")

    def update_ui_state(self):
        """Update UI state based on loaded samples and file statuses"""
        has_files = len(self.file_statuses) > 0
        has_selection = self.samples_table.currentRow() >= 0

        # Count files by status
        review_count = sum(1 for status in self.file_statuses.values() if status == 'review')
        mapping_count = sum(1 for status in self.file_statuses.values() if status == 'mapping')
        action_count = review_count + mapping_count
        loaded_count = sum(1 for status in self.file_statuses.values() if status == 'loaded')

        # Update batch action buttons
        self.review_failed_btn.setEnabled(action_count > 0)

        # Basic UI state
        self.remove_file_btn.setEnabled(has_selection)

        # If no manual status update, show file counts
        if has_files and not hasattr(self, '_manual_status_update'):
            if loaded_count > 0:
                summary = f"📊 {loaded_count} ready"
                if mapping_count > 0:
                    summary += f", {mapping_count} need mapping"
                if review_count > 0:
                    summary += f", {review_count} need review"
            elif mapping_count > 0:
                summary = f"{mapping_count} need mapping"
                if review_count > 0:
                    summary += f", {review_count} need review"
            elif review_count > 0:
                summary = f"{review_count} need review"
            else:
                summary = f"{len(self.file_statuses)} file(s) added"

            if not self.sample_info_label.text().startswith(("Processing", "✅", "⚠️", "🗑️", "🧹")):
                self.sample_info_label.setText(summary)

        # Update inventory summary bar
        self._update_inventory_bar()

        # Trigger validation to determine if analysis buttons should be enabled
        self.perform_full_validation()



    def _is_numeric(self, value: str) -> bool:
        """Check if a string represents a number"""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def update_analysis_progress(self, current, total, current_sample=""):
        """Update progress bar during analysis"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)

            if current_sample:
                self.progress_label.setText(f"🔄 Analyzing: {current_sample} ({current}/{total})")
            else:
                self.progress_label.setText(f"🔄 Processing... ({current}/{total})")

    def analysis_complete(self, results):
        """Called when analysis is complete"""
        self.show_progress(False)

        # Update sample statuses
        for sample_name in results:
            if sample_name in self.loaded_samples:
                self.loaded_samples[sample_name]['status'] = 'Analyzed'

        # Update UI
        success_count = len(results)
        self.progress_label.setText(f"✅ Analysis complete! {success_count} sample(s) processed")

        # Auto-export if enabled
        if self.export_results_cb.isChecked():
            self.progress_label.setText(f"✅ Analysis complete! Results exported for {success_count} sample(s)")

    def get_analysis_parameters(self):
        """Get current analysis parameters"""
        return {
            'temperature': self.temp_spinbox.value(),
            'porosity_mode': self.porosity_mode_combo.currentText(),
            'auto_export': self.export_results_cb.isChecked()
        }

    def get_loaded_samples(self):
        """Get dictionary of loaded samples"""
        return self.loaded_samples.copy()

    def set_sample_status(self, sample_name, status):
        """Update the status of a specific sample"""
        if sample_name in self.loaded_samples:
            self.loaded_samples[sample_name]['status'] = status
            file_path = self.loaded_samples[sample_name]['file_path']

            # Update file status tracking and table
            if file_path in self.file_statuses:
                self.file_statuses[file_path] = status
                self.update_file_in_table(file_path, status)

    def show_progress(self, show=True):
        """Show/hide progress bar"""
        self.progress_bar.setVisible(show)

    def set_progress(self, value):
        """Set progress bar value (0-100)"""
        self.progress_bar.setValue(value)

    # ================================
    # VALIDATION METHODS
    # ================================

    def validate_temperature(self, value):
        """Validate temperature input and recalculate K values"""
        self.validation_errors = [err for err in self.validation_errors if 'Temperature' not in err]

        if value < 0 or value > 50:
            self.validation_errors.append("🌡️ Temperature should be between 0-50°C for realistic conditions")
        elif value < 5:
            self.validation_errors.append("⚠️ Temperature below 5°C may affect viscosity calculations")
        elif value > 35:
            self.validation_errors.append("⚠️ Temperature above 35°C is unusual for groundwater")

        self.update_validation_display()

        # Debounce: only recalculate after user stops changing value for 500ms
        self.pending_temperature = value
        self.temp_change_timer.stop()
        self.temp_change_timer.start(500)  # 500ms delay

    def _apply_temperature_change(self):
        """Apply temperature change after debounce delay"""
        if self.pending_temperature is not None:
            self.on_temperature_changed(self.pending_temperature)
            self.pending_temperature = None

    def on_temperature_changed(self, new_temperature):
        """Handle temperature change and recalculate K values for all datasets"""
        if hasattr(self.parent(), 'dataset_tabs_widget'):
            main_window = self.parent()
            recalculated_count = 0

            for i in range(main_window.dataset_tabs_widget.count()):
                tab = main_window.dataset_tabs_widget.widget(i)
                if hasattr(tab, 'dataset') and hasattr(tab, 'calculate_k_values'):
                    # Update temperature in the dataset tab
                    tab.temperature = new_temperature
                    tab.dataset.temperature = new_temperature

                    # Recalculate K-values if they've been calculated before
                    if hasattr(tab, 'current_results') and tab.current_results:
                        tab.calculate_k_values()
                        recalculated_count += 1

            if recalculated_count > 0:
                self.sample_info_label.setText(f"🌡️ Temperature updated to {new_temperature}°C - {recalculated_count} dataset(s) recalculated")

    def on_porosity_mode_changed(self, mode_text):
        """Handle calculated-porosity mode changes across loaded datasets."""
        mode_key = "simple" if "Simple Formula" in mode_text else "urumovic"
        mode_name = "Simple Formula" if mode_key == "simple" else "Urumovic Polynomial"

        if hasattr(self.parent(), 'dataset_tabs_widget'):
            main_window = self.parent()
            recalculated_count = 0
            updated_count = 0
            preserved_overrides = 0

            for i in range(main_window.dataset_tabs_widget.count()):
                tab = main_window.dataset_tabs_widget.widget(i)
                if not hasattr(tab, 'dataset'):
                    continue

                dataset = tab.dataset
                if not hasattr(dataset, 'recalculate_porosity'):
                    continue

                previous_current = getattr(dataset, 'current_porosity', None)
                new_porosity = dataset.recalculate_porosity(mode_key, preserve_manual_override=True)
                current_porosity = getattr(dataset, 'current_porosity', None)

                if new_porosity is not None:
                    updated_count += 1

                if current_porosity is not None and current_porosity != previous_current:
                    tab.porosity = current_porosity
                elif previous_current is not None and current_porosity == previous_current:
                    preserved_overrides += 1

                if hasattr(tab, 'update_grain_statistics'):
                    tab.update_grain_statistics()
                if hasattr(tab, 'statistics_tab'):
                    tab.statistics_tab.porosity = (
                        current_porosity if current_porosity is not None else getattr(dataset, 'porosity', 0.40)
                    )
                    tab.statistics_tab.update_display()

                if (
                    hasattr(tab, 'calculate_k_values')
                    and hasattr(tab, 'current_results')
                    and tab.current_results
                    and current_porosity is not None
                ):
                    tab.calculate_k_values()
                    recalculated_count += 1

            if updated_count > 0 or recalculated_count > 0:
                message = f"Calculated porosity set to {mode_name} for {updated_count} dataset(s)"
                if preserved_overrides > 0:
                    message += f" | preserved {preserved_overrides} manual override(s)"
                if recalculated_count > 0:
                    message += f" | recalculated {recalculated_count} dataset(s)"
                self.sample_info_label.setText(message)

    def validate_porosity_mode(self):
        """Validate porosity calculation mode selection"""
        self.validation_errors = [err for err in self.validation_errors if 'Porosity' not in err]

        current_mode = self.porosity_mode_combo.currentText()
        if not current_mode or current_mode not in ["Simple Formula (Excel Compatible)", "Urumovic Polynomial (Research)"]:
            self.validation_errors.append("🕳️ Please select a valid porosity calculation mode")

        self.update_validation_display()

    def validate_column_mapping(self):
        """Column mapping validation - simplified since we auto-detect"""
        pass

    def validate_samples(self):
        """Validate that samples are loaded and ready"""
        self.validation_errors = [err for err in self.validation_errors if 'Sample' not in err]

        if not self.loaded_samples:
            self.validation_errors.append("📁 Samples: No samples loaded - please add data files")
        else:
            for sample_name, sample_data in self.loaded_samples.items():
                if sample_data['status'] == 'Error':
                    self.validation_errors.append(f"❌ Sample '{sample_name}': Failed to load properly")

        self.update_validation_display()

    def update_validation_display(self):
        """Update the validation status display"""
        if not self.validation_errors:
            pass  # Validation passed

            # Enable analysis if we have samples
            if self.loaded_samples:
                pass  # Samples ready
                if self.samples_table.currentRow() >= 0:
                    pass  # Sample selected
        else:
            # Show the most critical errors (limit to 3)
            display_errors = self.validation_errors[:3]
            error_text = "\n".join(display_errors)
            if len(self.validation_errors) > 3:
                error_text += f"\n... and {len(self.validation_errors) - 3} more issues"

            pass  # Show validation errors in status bar if needed

            # Disable analysis if there are critical errors
            critical_errors = [err for err in self.validation_errors if '❌' in err or 'should be' in err]
            if critical_errors:
                pass  # No samples
                pass  # No sample selected

    def perform_full_validation(self):
        """Perform complete validation of all parameters"""
        self.validation_errors.clear()

        # Validate all components
        self.validate_temperature(self.temp_spinbox.value())
        self.validate_porosity_mode()
        self.validate_samples()

        return len([err for err in self.validation_errors if '❌' in err or 'should be' in err]) == 0

    def open_porosity_dialog(self):
        """Open the porosity management dialog"""
        # Get reference to main window - traverse up to find the actual main window
        main_window = self.window()

        # Debug: Check if we found the right window
        if not hasattr(main_window, 'dataset_tabs_widget'):
            print(f"Warning: Could not find main window with dataset_tabs_widget. Found: {type(main_window)}")
            QMessageBox.warning(
                self,
                "No Datasets",
                "No datasets are currently loaded. Please load some data files first."
            )
            return

        # Create and show dialog
        dialog = PorosityDialog(main_window, self)
        dialog.exec()

    def process_files_with_immediate_tabs(self, file_entries: list, import_intent: str = "processed"):
        """Process files by creating tabs immediately, then attempting to load data

        Args:
            file_entries: List of file paths, (file_path, sheet_name) tuples, or source dicts
        """
        worker_entries = [
            self._with_import_intent(entry, import_intent)
            for entry in file_entries
        ]
        return self._process_files_with_loading_dialog(worker_entries)

    def _process_files_with_loading_dialog(self, file_entries: list):
        if not file_entries:
            return
        if self._import_process is not None:
            if self._import_dialog is not None:
                self._import_dialog.raise_()
                self._import_dialog.activateWindow()
            return

        self.dataset_integration_started.emit()

        self._import_dialog = LoadingDialog(
            "Importing Datasets",
            "Reading selected files and building sample tabs",
            parent=self.window(),
            cancellable=False,
        )
        progress_total = max(1, len(file_entries) * 2)
        self._import_dialog.update_progress(
            0,
            progress_total,
            "Preparing import",
            "Creating placeholder tabs and starting the background loader.",
            count_label=f"0 of {len(file_entries)} items",
            activity_label="Starting the background loader.",
        )
        self._import_dialog.set_activity(
            "Large files can take a moment. This window will close automatically when the import is complete."
        )
        self._import_dialog.open()

        ctx = mp.get_context("spawn")
        self._import_finished_received = False
        self._import_finalize_summary = None
        self._pending_import_ui_events.clear()
        self._import_ui_total = 0
        self._import_ui_processed = 0
        self._import_queue = ctx.Queue()
        self._import_process = ctx.Process(
            target=run_batch_import,
            args=(file_entries, self._import_queue),
            kwargs={"temperature": self.temp_spinbox.value()},
            daemon=True,
        )
        self._import_process.start()
        self._import_poll_timer.start()

    def _poll_import_process(self):
        if self._import_queue is None:
            return

        for _ in range(32):
            try:
                event = self._import_queue.get_nowait()
            except queue.Empty:
                break

            kind = event[0]
            payload = event[1:]

            if kind == 'progress':
                self._on_import_worker_progress(*payload)
            elif kind == 'log_event':
                self._record_log_event(payload[0])
            elif kind == 'item_loaded':
                self._import_ui_total += 1
                self._pending_import_ui_events.append((self._on_import_worker_loaded, payload))
            elif kind == 'item_validation_failed':
                self._import_ui_total += 1
                self._pending_import_ui_events.append((self._on_import_worker_validation_failed, payload))
            elif kind == 'item_failed':
                self._import_ui_total += 1
                self._pending_import_ui_events.append((self._on_import_worker_failed, payload))
            elif kind == 'finished':
                self._import_finished_received = True
                self._import_finalize_summary = payload[0]
                if self._import_dialog is not None and self._pending_import_ui_events:
                    self._import_dialog.set_activity(
                        "Integrating loaded datasets into the workspace."
                    )
                    self._update_import_integration_progress()
            elif kind == 'process_error':
                self._import_finished_received = True
                self._import_finalize_summary = (
                    {
                        'total': 0,
                        'loaded': 0,
                        'review': 1,
                        'failed': 0,
                        'canceled': False,
                    }
                )
                if self._import_dialog is not None:
                    self._import_dialog.set_activity(payload[0])

        if self._pending_import_ui_events and not self._import_ui_timer.isActive():
            self._import_ui_timer.start()

        self._finalize_import_if_ready()

    def _process_import_ui_slice(self):
        if not self._pending_import_ui_events:
            self._import_ui_timer.stop()
            self._finalize_import_if_ready()
            return

        handler, payload = self._pending_import_ui_events.popleft()
        handler(*payload)
        self._import_ui_processed += 1
        if self._import_finished_received:
            self._update_import_integration_progress()

        if not self._pending_import_ui_events:
            self._import_ui_timer.stop()
            self._finalize_import_if_ready()

    def _finalize_import_if_ready(self):
        if self._pending_import_ui_events:
            return

        if self._import_finalize_summary is not None:
            summary = self._import_finalize_summary
            self._import_finalize_summary = None
            self._on_import_worker_finished(summary)

        if self._import_finished_received and self._import_process is not None and not self._import_process.is_alive():
            self._cleanup_import_process()

    def _on_import_worker_progress(self, current: int, total: int, stage: str, detail: str):
        if self._import_dialog is not None:
            overall_total = max(1, total * 2)
            self._import_dialog.update_progress(
                current,
                overall_total,
                stage,
                detail,
                count_label=f"{current} of {total} items",
                activity_label=f"Processing item {current} of {total}.",
            )

    def _update_import_integration_progress(self):
        if self._import_dialog is None or self._import_ui_total <= 0:
            return

        current = max(0, min(self._import_ui_processed, self._import_ui_total))
        overall_total = max(1, self._import_ui_total * 2)
        activity = (
            "Preparing workspace integration."
            if current <= 0
            else f"Integrating item {current} of {self._import_ui_total}."
        )
        self._import_dialog.update_progress(
            self._import_ui_total + current,
            overall_total,
            "Integrating workspace",
            "Adding loaded items to the workspace.",
            count_label=f"{self._import_ui_total} items processed",
            activity_label=activity,
        )

    def _on_import_worker_loaded(self, file_key: str, dataset, status: str, sample_name: str):
        self._remove_loaded_entries_for_file(file_key)
        mapping_state = getattr(dataset, "_source_mapping_state", None)
        if mapping_state:
            self.file_mapping_states[file_key] = dict(mapping_state)
        provenance = getattr(dataset, "_source_import_provenance", None)
        self.file_statuses[file_key] = status
        self.loaded_samples[sample_name] = {
            'file_path': file_key,
            'data': dataset,
            'datasets': [dataset],
            'status': status,
            'mapping_state': self.file_mapping_states.get(file_key),
            'import_provenance': provenance,
        }
        self.dataset_loaded_successfully.emit(dataset, file_key)
        self.update_file_in_table(file_key, status)
        self._push_card_meta(file_key)
        self._update_inventory_bar()

    def _on_import_worker_validation_failed(self, file_key: str, dataset, sample_name: str, detail: str):
        self._remove_loaded_entries_for_file(file_key)
        mapping_state = getattr(dataset, "_source_mapping_state", None)
        if mapping_state:
            self.file_mapping_states[file_key] = dict(mapping_state)
        provenance = getattr(dataset, "_source_import_provenance", None)
        self.file_statuses[file_key] = 'failed'
        self.loaded_samples[sample_name] = {
            'file_path': file_key,
            'data': dataset,
            'datasets': [dataset],
            'status': 'failed',
            'mapping_state': self.file_mapping_states.get(file_key),
            'import_provenance': provenance,
        }
        self.update_file_in_table(file_key, 'failed')
        self.update_error_tab_message.emit(file_key, detail)
        self._push_card_meta(file_key)
        self._update_inventory_bar()

    def _on_import_worker_failed(self, file_key: str, detail: str):
        self._remove_loaded_entries_for_file(file_key)
        self._file_list.update_card_meta(file_key, "", "")
        self.file_statuses[file_key] = 'review'
        self.update_file_in_table(file_key, 'review')
        self.update_error_tab_message.emit(file_key, detail)
        self._update_inventory_bar()

    def _on_import_worker_finished(self, summary: dict):
        loaded = summary.get('loaded', 0)
        review = summary.get('review', 0)
        failed = summary.get('failed', 0)
        canceled = summary.get('canceled', False)

        if canceled:
            headline = "Import canceled"
            detail = f"{loaded} loaded before cancellation"
            ok = False
            summary_text = detail
        elif loaded and not review and not failed:
            headline = "Files loaded"
            detail = f"{loaded} file{'s' if loaded != 1 else ''} loaded successfully."
            ok = True
            summary_text = f"Loaded {loaded} file{'s' if loaded != 1 else ''}"
        else:
            parts = []
            if loaded:
                parts.append(f"{loaded} loaded")
            if review:
                parts.append(f"{review} need review")
            if failed:
                parts.append(f"{failed} invalid")
            headline = "Import complete"
            detail = " · ".join(parts) if parts else "No files were processed."
            ok = not review and not failed
            summary_text = detail

        if self._import_dialog is not None:
            self.dataset_integration_finished.emit()
            dialog = self._import_dialog
            dialog.mark_finished(headline, detail, ok=ok)
            QTimer.singleShot(420, lambda d=dialog: self._dismiss_import_dialog(d))
        else:
            self.dataset_integration_finished.emit()

        self.sample_info_label.setText(summary_text)
        self.update_ui_state()

    def _dismiss_import_dialog(self, dialog):
        if dialog is not None:
            dialog.accept()
            dialog.deleteLater()
        if self._import_dialog is dialog:
            self._import_dialog = None

    def _cleanup_import_process(self):
        self._import_poll_timer.stop()
        self._import_ui_timer.stop()

        if self._import_process is not None:
            self._import_process.join(timeout=0.1)
            if self._import_process.is_alive():
                self._import_process.terminate()
                self._import_process.join(timeout=0.1)

        if self._import_queue is not None:
            self._import_queue.close()
            self._import_queue = None

        self._import_process = None
        self._import_finished_received = False
        self._import_finalize_summary = None
        self._pending_import_ui_events.clear()
        self._import_ui_total = 0
        self._import_ui_processed = 0

    # ================================
    # SENSITIVITY ANALYSIS
    # ================================

    def show_sensitivity_placeholder(self):
        """Show placeholder dialog for sensitivity analysis feature"""
        QMessageBox.information(
            self,
            "Sensitivity Analysis - Coming Soon",
            """<h3>🔬 Sensitivity Analysis Feature</h3>

            <p>This feature will allow you to:</p>
            <ul>
            <li><b>Vary Temperature:</b> Run calculations across a range of temperatures (e.g., 5-30°C)</li>
            <li><b>Vary Porosity:</b> Test different porosity values or calculation methods</li>
            <li><b>Multiple Parameters:</b> Combine temperature and porosity variations</li>
            <li><b>Visualize Results:</b> See how K values change with parameter variations</li>
            <li><b>Export Analysis:</b> Export sensitivity analysis results to Excel/CSV</li>
            </ul>

            <p><b>Use Cases:</b></p>
            <ul>
            <li>Understand uncertainty in K calculations due to parameter variations</li>
            <li>Identify which parameters have the most influence on results</li>
            <li>Generate confidence intervals for K value predictions</li>
            </ul>

            <p><i>This feature is planned for a future release.</i></p>"""
        )

    # ================================
    # HELP & ABOUT METHODS
    # ================================

    def show_help(self):
        """Show comprehensive help dialog"""
        host_window = self.window()
        if host_window is not None and hasattr(host_window, "open_help_dialog"):
            host_window.open_help_dialog()
            return

        from gui.help_dialog import HelpDialog

        help_dialog = getattr(self, "_help_dialog", None)
        if help_dialog is None:
            help_dialog = HelpDialog(self.parent())
            help_dialog.setModal(False)
            help_dialog.setWindowModality(Qt.WindowModality.NonModal)
            help_dialog.destroyed.connect(lambda *_args: setattr(self, "_help_dialog", None))
            self._help_dialog = help_dialog

        if help_dialog.isMinimized():
            help_dialog.showNormal()
        else:
            help_dialog.show()
        help_dialog.raise_()
        help_dialog.activateWindow()

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About Grain Size Analysis Tool",
            """<h3>Grain Size Analysis Tool</h3>
            <p><b>Version 0.9.0-beta</b></p>
            <p>Released: January 2025</p>

            <p>A comprehensive tool for grain size distribution analysis
            and hydraulic conductivity calculations.</p>

            <p><b>Features:</b></p>
            <ul>
            <li>Multiple dataset management</li>
            <li>14+ K-calculation methods</li>
            <li>Interactive plots with controls</li>
            <li>Dataset comparison tools</li>
            <li>Statistical analysis</li>
            <li>Comprehensive help system</li>
            </ul>

            <p><b>Developed by:</b><br>
            Oliver Lund<br>
            DTU Sustain</p>

            <p><b>Supervised by:</b><br>
            Prof. Poul Løgstrup Bjerg</p>

            <p>© 2025 - DTU Sustain</p>
            <p><em>Press F1 for detailed help topics</em></p>""")

    def _read_welcome_screen_enabled(self) -> bool:
        """Read the effective startup preference for the welcome screen."""
        host_window = self.window()
        if host_window is not None and hasattr(host_window, "is_welcome_screen_enabled"):
            return bool(host_window.is_welcome_screen_enabled())

        from gui.main_window import _effective_welcome_dont_show

        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        return not _effective_welcome_dont_show(settings)

    def _write_welcome_screen_enabled(self, enabled: bool) -> None:
        """Persist the startup preference for the welcome screen."""
        host_window = self.window()
        if host_window is not None and hasattr(host_window, "set_welcome_screen_enabled"):
            host_window.set_welcome_screen_enabled(bool(enabled))
            return

        from gui.main_window import _save_welcome_preference

        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        _save_welcome_preference(settings, not bool(enabled))

    def show_settings(self):
        """Show application settings dialog."""
        host_window = self.window()
        dialog_parent = host_window if isinstance(host_window, QWidget) else self
        dialog = ApplicationSettingsDialog(
            show_welcome_on_startup=self._read_welcome_screen_enabled(),
            parent=dialog_parent,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._write_welcome_screen_enabled(dialog.show_welcome_on_startup())
