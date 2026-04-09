"""
Control panel widget for data import and analysis controls
"""

from collections import deque
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
from PyQt6.QtCore import QTimer
from data_loader import DataLoader
from gui.column_mapper import ColumnMapperDialog
from gui.data_inspector_dialog import DataInspectorDialog
import os
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRectF, QPoint
from PyQt6.QtGui import (QIcon, QFont, QAction, QPainter, QColor,
                         QLinearGradient, QBrush, QPixmap, QPen, QFontMetrics)
from gui.loading_dialog import LoadingDialog
from gui.theme import C, F, SZ, icon
from qt_chrome.frameless_dialog_base import FramelessDialogBase
from load_process_worker import run_batch_import
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
    Row: icon container + name/meta + status LED + selected toggle + expand chevron.
    Active card: sb-act background + 3px olive left accent bar.
    """

    sig_clicked = pyqtSignal(str)          # file_path
    sig_ctx = pyqtSignal(str, object)      # file_path, QPoint (global)
    sig_selected = pyqtSignal(str, bool)   # file_path, is_selected
    sig_inspect = pyqtSignal(str)          # file_path
    sig_log = pyqtSignal(str)              # file_path
    sig_props = pyqtSignal(str)            # file_path
    sig_remove = pyqtSignal(str)           # file_path

    _STATUS_DOT = {
        'pending': C.SB_MUTED,
        'failed':  C.LED_ERR,
        'review':  C.LED_WARN,
        'loaded':  C.OLIVE,
    }

    def __init__(self, file_path: str, display_name: str, status: str,
                 d50: str = "", k_val: str = "", parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._display_name = display_name
        self._status = status
        self._active = False
        self._selected = False
        self._expanded = False
        self._d50 = d50
        self._k_val = k_val

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
        info_col = QVBoxLayout()
        info_col.setSpacing(1)
        self._name = QLabel(display_name)
        self._name.setTextFormat(Qt.TextFormat.PlainText)
        self._name.setFont(QFont(F.UI, F.SZ_SM, QFont.Weight.Medium))
        self._name.setStyleSheet(f"color: {C.SB_TEXT}; background: transparent;")
        self._name.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_col.addWidget(self._name)

        # Meta row (D50, K value)
        self._meta = QLabel()
        self._meta.setFont(QFont(F.MONO, 7))
        self._meta.setStyleSheet(f"color: {C.SB_MUTED}; background: transparent;")
        self._update_meta_text()
        info_col.addWidget(self._meta)
        row.addLayout(info_col, 1)

        # Status LED  — .s-led in CSS
        self._led = QLabel()
        self._led.setFixedSize(6, 6)
        row.addWidget(self._led)

        # Selected toggle — .s-pick-btn in CSS
        self._sel_btn = QPushButton()
        self._sel_btn.setObjectName("card-pick")
        self._sel_btn.setFixedSize(18, 18)
        self._sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sel_btn.setToolTip("Toggle selection")
        self._sel_btn.clicked.connect(self._toggle_selected)
        row.addWidget(self._sel_btn)

        # Expand chevron — .s-expand-btn in CSS
        self._expand_btn = QPushButton()
        self._expand_btn.setObjectName("card-expand")
        self._expand_btn.setFixedSize(16, 16)
        self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_btn.setToolTip("Expand details")
        try:
            self._expand_btn.setIcon(icon('fa6s.chevron-right', C.SB_MUTED))
            self._expand_btn.setIconSize(QSize(9, 9))
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

        # Action buttons row — .s-act-row in CSS
        act_row = QHBoxLayout()
        act_row.setSpacing(3)
        for btn_text, btn_icon_name, is_danger, sig_attr in [
            ("Inspect", "fa6s.magnifying-glass", False, "sig_inspect"),
            ("Log",     "fa6s.clipboard-list",   False, "sig_log"),
            ("Props",   "fa6s.sliders",           False, "sig_props"),
            ("Remove",  "fa6s.trash",             True,  "sig_remove"),
        ]:
            btn = QPushButton(btn_text)
            btn.setObjectName("card-action")
            btn.setFixedHeight(22)
            try:
                btn.setIcon(icon(btn_icon_name,
                                 "#a03020" if is_danger else C.SB_MID))
                btn.setIconSize(QSize(9, 9))
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
            act_row.addWidget(btn)
        act_row.addStretch()
        detail_v.addLayout(act_row)

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

    def _update_meta_text(self):
        parts = []
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
            self._expand_btn.setIconSize(QSize(9, 9))
        except Exception:
            pass

    def _refresh_sel_btn(self):
        if self._selected:
            self._sel_btn.setStyleSheet(
                f"QPushButton#card-pick {{ background: rgba(107,142,35,0.12); "
                f"border: 1px solid rgba(107,142,35,0.34); border-radius: 4px; "
                f"padding: 0; color: {C.OLIVE}; font-size: 9px; }}")
            try:
                self._sel_btn.setIcon(icon('fa6s.check', C.OLIVE))
                self._sel_btn.setIconSize(QSize(9, 9))
            except Exception:
                self._sel_btn.setText("\u2713")
        else:
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
        card.sig_clicked.connect(self._on_card_clicked)
        card.sig_ctx.connect(self.card_ctx)
        card.sig_selected.connect(self._on_card_selected)
        card.sig_inspect.connect(self.card_inspect)
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
        """Return file paths of all selected cards."""
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
                   if card._status in ('review', 'failed'))

    def apply_filter(self, filter_type: str):
        """Show/hide cards based on filter: 'all', 'selected', 'warnings'."""
        for card in self._cards.values():
            if filter_type == 'all':
                card.setVisible(True)
            elif filter_type == 'selected':
                card.setVisible(card.is_selected)
            elif filter_type == 'warnings':
                card.setVisible(card._status in ('review', 'failed'))

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
        """Initialize dialog UI"""
        from gui.dialog_chrome import make_dialog_header, make_dialog_footer
        from gui.theme import C, F, SZ

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header_widget = make_dialog_header(
            "Manage Porosity",
            "Per-dataset porosity values · affects all K calculations",
            fa_icon="fa6s.circle-nodes",
            close_fn=self.accept,
        )
        root.addWidget(self._header_widget)

        # Body wrapper
        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # Table showing all datasets and their porosity values
        self.porosity_table = QTableWidget(0, 5)
        self.porosity_table.setHorizontalHeaderLabels([
            "Dataset", "Calculated Porosity", "Current Porosity", "Edit", "Actions"
        ])

        # Configure table
        self.porosity_table.setAlternatingRowColors(True)
        self.porosity_table.verticalHeader().setVisible(False)
        self.porosity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # Set column widths
        header = self.porosity_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.porosity_table.setColumnWidth(3, 180)
        self.porosity_table.setColumnWidth(4, 200)

        self.porosity_table.setStyleSheet(
            f"QTableWidget {{ gridline-color: {C.BORDER}; font-size: {F.SZ_MD}pt; "
            f"background-color: white; border: none; }}"
            f"QTableWidget::item {{ padding: 6px; }}"
            f"QTableWidget::item:alternate {{ background: {C.BG_LOW}; }}"
            f"QHeaderView::section {{ background: {C.BG_RAISED}; padding: 5px 12px; "
            f"border: none; border-bottom: 1px solid {C.BORDER}; "
            f"font-size: {F.SZ_SM}pt; font-weight: 600; letter-spacing: .06em; "
            f"text-transform: uppercase; color: {C.TEXT_MUTED}; }}"
        )

        body_lay.addWidget(self.porosity_table, 1)

        # Info label at bottom
        self.info_label = QLabel(
            "Use 'Update' to apply changes to individual datasets, "
            "or 'Apply All' to save all changes at once."
        )
        self.info_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; "
            f"padding: 6px 14px; background: transparent;"
        )
        self.info_label.setWordWrap(True)
        body_lay.addWidget(self.info_label)

        root.addWidget(body, 1)

        # Footer
        root.addWidget(make_dialog_footer([
            ("Close",            self.accept,           "secondary"),
            ("Apply All Changes", self.apply_all_changes, "primary"),
        ]))

        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )

    def load_dataset_porosity_values(self):
        """Load all datasets and their current porosity values"""
        self.porosity_table.setRowCount(0)

        if not hasattr(self.main_window, 'dataset_tabs_widget'):
            print(f"DEBUG: main_window does not have dataset_tabs_widget attribute")
            self.info_label.setText("⚠️ Error: Could not access dataset tabs")
            return

        tab_count = self.main_window.dataset_tabs_widget.count()
        print(f"DEBUG: Found {tab_count} tabs in main window")
        dataset_count = 0

        # Iterate through all tabs
        for i in range(tab_count):
            tab = self.main_window.dataset_tabs_widget.widget(i)

            # Skip non-dataset tabs
            if not hasattr(tab, 'dataset'):
                print(f"DEBUG: Tab {i} does not have dataset attribute (type: {type(tab).__name__})")
                continue

            dataset_count += 1
            print(f"DEBUG: Found dataset tab {dataset_count}: {tab.dataset.sample_name}")

            dataset = tab.dataset
            dataset_name = dataset.sample_name

            # Get porosity values
            calculated_porosity = getattr(dataset, 'calculated_porosity', None)
            current_porosity = getattr(dataset, 'current_porosity', None)

            if current_porosity is None:
                current_porosity = calculated_porosity if calculated_porosity else 0.40

            # Add row to table
            row = self.porosity_table.rowCount()
            self.porosity_table.insertRow(row)

            # Dataset name
            name_item = QTableWidgetItem(dataset_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.porosity_table.setItem(row, 0, name_item)

            # Calculated porosity
            if calculated_porosity:
                calc_item = QTableWidgetItem(f"{calculated_porosity:.4f}")
            else:
                calc_item = QTableWidgetItem("N/A")
            calc_item.setFlags(calc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            calc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.porosity_table.setItem(row, 1, calc_item)

            # Current porosity
            current_item = QTableWidgetItem(f"{current_porosity:.4f}")
            current_item.setFlags(current_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            current_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.porosity_table.setItem(row, 2, current_item)

            # Edit field
            edit_field = QLineEdit()
            edit_field.setText(f"{current_porosity:.4f}")
            edit_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit_field.setStyleSheet("""
                QLineEdit {
                    padding: 4px;
                    border: 1px solid #c0c0c0;
                    border-radius: 3px;
                    font-family: 'Consolas', monospace;
                }
            """)
            self.porosity_table.setCellWidget(row, 3, edit_field)

            # Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(4)

            update_btn = QPushButton("Update")
            update_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6b8e23;
                    color: white;
                    padding: 4px 8px;
                    font-size: 9pt;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #7fa02d;
                }
            """)
            update_btn.clicked.connect(lambda checked, r=row: self.update_single_dataset(r))

            reset_btn = QPushButton("Reset")
            reset_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d2b48c;
                    padding: 4px 8px;
                    font-size: 9pt;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #ddbf94;
                }
            """)
            reset_btn.clicked.connect(lambda checked, r=row: self.reset_single_dataset(r))

            if calculated_porosity is None:
                reset_btn.setEnabled(False)

            action_layout.addWidget(update_btn)
            action_layout.addWidget(reset_btn)

            self.porosity_table.setCellWidget(row, 4, action_widget)

        # Update info label with summary
        if dataset_count == 0:
            self.info_label.setText("⚠️ No datasets found. Please load some data files first.")
        else:
            self.info_label.setText(f"📊 Loaded {dataset_count} dataset(s). Edit porosity values and click 'Update' or 'Apply All'.")

    def update_single_dataset(self, row: int):
        """Update porosity for a single dataset"""
        dataset_name = self.porosity_table.item(row, 0).text()
        edit_field = self.porosity_table.cellWidget(row, 3)

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
        dataset_name = self.porosity_table.item(row, 0).text()
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
        edit_field = self.porosity_table.cellWidget(row, 3)
        edit_field.setText(f"{calculated_porosity:.4f}")

        current_item = self.porosity_table.item(row, 2)
        current_item.setText(f"{calculated_porosity:.4f}")

        self.info_label.setText(f"✅ Reset {dataset_name} to calculated value {calculated_porosity:.4f}")

    def apply_all_changes(self):
        """Apply all porosity changes at once"""
        changes_made = 0

        for row in range(self.porosity_table.rowCount()):
            dataset_name = self.porosity_table.item(row, 0).text()
            edit_field = self.porosity_table.cellWidget(row, 3)
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


class ControlPanel(QFrame):
    # Signals for communication with main window
    analysis_requested = pyqtSignal(dict)  # Emitted when analysis is requested
    sample_selected = pyqtSignal(str)  # Emitted when a sample is selected
    error_dataset = pyqtSignal(str, str)  # Emitted when dataset fails to load (file_path, error_message)
    dataset_loaded_successfully = pyqtSignal(object, str)  # Emitted when dataset loads successfully (dataset, file_path)
    update_error_tab_message = pyqtSignal(str, str)  # Update existing error tab with new message
    dataset_fix_requested = pyqtSignal(str)  # Emitted when user wants to fix/remap a dataset (file_path)
    dataset_integration_started = pyqtSignal()  # Batched dataset UI integration starts
    dataset_integration_finished = pyqtSignal()  # Batched dataset UI integration finished
    selection_changed = pyqtSignal()  # Emitted when card selected-toggle state changes
    scheme_changed = pyqtSignal(object)  # GrainClassificationScheme — emitted when user picks a new scheme

    def __init__(self):
        super().__init__()
        self.loaded_samples = {}  # Dictionary to store sample data
        self.validation_errors = []  # Track validation issues
        self.data_loader = DataLoader()  # Data loading engine
        self.file_statuses = {}  # Track file loading status: 'pending', 'failed', 'review', 'loaded'
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
        """Return file paths of all sidebar-selected sample cards."""
        return self._file_list.get_selected_paths()

    def set_selected_paths(self, file_paths: list[str], *, emit_signal: bool = True):
        """Set sidebar-selected sample cards from an external controller."""
        self._file_list.set_selected_paths(file_paths, emit_signal=emit_signal)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(('.csv', '.xlsx', '.xls', '.txt'))
                   for u in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        file_paths = [u.toLocalFile() for u in urls
                      if u.toLocalFile().lower().endswith(('.csv', '.xlsx', '.xls', '.txt'))]
        if file_paths:
            self._handle_dropped_files(file_paths)
            event.acceptProposedAction()

    def _handle_dropped_files(self, file_paths: list):
        """Process files dropped onto the sidebar — same pipeline as add_files."""
        expanded_files = []
        already_added = []
        excel_files = [f for f in file_paths if f.endswith(('.xlsx', '.xls')) and f not in self.file_statuses]
        other_files = [f for f in file_paths if not f.endswith(('.xlsx', '.xls')) and f not in self.file_statuses]
        already_added = [os.path.basename(f) for f in file_paths if f in self.file_statuses]

        if excel_files:
            excel_expanded = self.handle_batch_multisheet_excel(excel_files)
            if excel_expanded is None:
                return
            expanded_files.extend(excel_expanded)
        expanded_files.extend(other_files)

        if expanded_files:
            for file_entry in expanded_files:
                if isinstance(file_entry, tuple):
                    file_path, sheet_name = file_entry
                    sheet_key = f"{file_path}:::{sheet_name}"
                    self.file_statuses[sheet_key] = 'pending'
                else:
                    self.file_statuses[file_entry] = 'pending'

            for file_entry in expanded_files:
                if isinstance(file_entry, tuple):
                    file_path, sheet_name = file_entry
                    sheet_key = f"{file_path}:::{sheet_name}"
                    self.add_file_to_table(sheet_key, 'pending',
                                           display_name=f"{os.path.basename(file_path)} [{sheet_name}]")
                else:
                    self.add_file_to_table(file_entry, 'pending')

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
        self._drop_zone.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drop_zone.setMinimumHeight(70)
        self._drop_zone.setStyleSheet(
            f"QFrame {{ border: 1.5px dashed {C.SB_BDR}; border-radius: 5px;"
            f"  background: rgba(255,255,255,0.25); }}"
            f"QFrame:hover {{ border-color: {C.OLIVE};"
            f"  background: rgba(107,142,35,0.07); }}")
        self._drop_zone.mousePressEvent = lambda e: self.add_files()

        dz_v = QVBoxLayout(self._drop_zone)
        dz_v.setContentsMargins(10, 11, 10, 11)
        dz_v.setSpacing(4)
        dz_v.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dz_icon = QLabel()
        try:
            dz_icon.setPixmap(icon('fa6s.cloud-arrow-up', C.SB_MUTED).pixmap(17, 17))
        except Exception:
            dz_icon.setText("\u2B06")
        dz_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_icon.setStyleSheet("background: transparent; border: none;")
        dz_v.addWidget(dz_icon)

        dz_text = QLabel("Drop files or click to browse")
        dz_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_text.setStyleSheet(
            f"font-size: 11px; color: {C.SB_MID};"
            f"  background: transparent; border: none;")
        dz_v.addWidget(dz_text)

        dz_formats = QLabel("CSV \u00b7 XLSX \u00b7 TXT")
        dz_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_formats.setStyleSheet(
            f"font-size: 9.5px; color: {C.SB_MUTED};"
            f"  background: transparent; border: none;")
        dz_v.addWidget(dz_formats)

        drop_wrap = QWidget()
        drop_wrap.setStyleSheet(f"background: {C.SB};")
        drop_wrap_v = QHBoxLayout(drop_wrap)
        drop_wrap_v.setContentsMargins(10, 8, 10, 4)
        drop_wrap_v.addWidget(self._drop_zone)
        body_v.addWidget(drop_wrap)

        # ── 2a. SAMPLES section header ────────────────────────────────
        body_v.addWidget(_SectionHeader("SAMPLES", btn_text="+ Add",
                                        btn_icon="fa6s.plus"))

        # Connect the "+ Add" button in section header to add_files
        samples_hdr = body_v.itemAt(body_v.count() - 1).widget()
        if hasattr(samples_hdr, 'action_btn') and samples_hdr.action_btn:
            samples_hdr.action_btn.clicked.connect(self.add_files)

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
        self._pill_sel = QPushButton("Selected")
        self._pill_sel.setCheckable(True)
        self._pill_sel.setStyleSheet(_PILL)
        self._pill_rev = QPushButton("\u26a0 Review")
        self._pill_rev.setCheckable(True)
        self._pill_rev.setStyleSheet(_PILL)

        # Exclusive pill logic
        self._pill_all.clicked.connect(lambda: self._set_filter("all"))
        self._pill_sel.clicked.connect(lambda: self._set_filter("selected"))
        self._pill_rev.clicked.connect(lambda: self._set_filter("warnings"))

        pills_h.addWidget(self._pill_all)
        pills_h.addWidget(self._pill_sel)
        pills_h.addWidget(self._pill_rev)
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

        self._chip_loaded = QLabel("0 loaded")
        self._chip_loaded.setStyleSheet(_CHIP)
        self._chip_selected = QLabel("0 selected")
        self._chip_selected.setStyleSheet(_CHIP_SEL)
        self._chip_warnings = QLabel("")
        self._chip_warnings.setStyleSheet(_CHIP_WARN)
        self._chip_warnings.setVisible(False)

        stats_row.addWidget(self._chip_loaded)
        stats_row.addWidget(self._chip_selected)
        stats_row.addWidget(self._chip_warnings)
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
        self.review_failed_btn.setToolTip("Review files needing manual mapping")
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
        body_v.addWidget(batch_outer)

        # ── 2d. PARAMETERS section ────────────────────────────────────
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setFixedHeight(1)
        div1.setStyleSheet(f"background: {C.SB_BDR};")
        body_v.addWidget(div1)
        body_v.addWidget(_SectionHeader("PARAMETERS"))

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
        por_lbl = QLabel("Porosity Method")
        por_lbl.setStyleSheet(_LBL)
        self.porosity_mode_combo = QComboBox()
        self.porosity_mode_combo.addItems([
            "Simple Formula (Excel Compatible)",
            "Urumovic Polynomial (Research)"
        ])
        self.porosity_mode_combo.setCurrentIndex(0)
        self.porosity_mode_combo.setToolTip(
            "Simple: n = 0.255 x (1 + 0.83^U)\n"
            "Urumovic: polynomial based on grain size distribution")
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
        body_v.addWidget(strata_outer)

        # ── 3. DTU box — matches .dtu-box in CSS ────────────────────────
        dtu_w = QWidget()
        dtu_w.setStyleSheet(
            f"background: {C.SB_DN}; border-top: 1px solid {C.SB_BDR};")
        dtu_h = QHBoxLayout(dtu_w)
        dtu_h.setContentsMargins(13, 9, 13, 8)
        dtu_h.setSpacing(10)

        # DTU red pill label — .dtu-logo in CSS
        dtu_pill = QLabel("DTU")
        dtu_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dtu_pill.setStyleSheet(
            f"background: {C.DTU_RED}; color: #fff;"
            f"  font-family: '{F.UI}'; font-size: 13px; font-weight: 700;"
            f"  letter-spacing: 0.04em; padding: 3px 6px 2px;"
            f"  border-radius: 2px; line-height: 1.2;")
        dtu_pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        dtu_h.addWidget(dtu_pill)

        # Info column — .dtu-info in CSS
        dtu_info = QVBoxLayout()
        dtu_info.setSpacing(1)
        dtu_prog = QLabel("Grain Size Analysis")
        dtu_prog.setStyleSheet(
            f"font-size: 10.5px; font-weight: 600; color: {C.SB_TEXT};"
            f"  background: transparent;")
        dtu_dept = QLabel("DTU Environment \u00b7 Oliver Lund")
        dtu_dept.setFont(QFont(F.MONO, 7))
        dtu_dept.setStyleSheet(
            f"color: {C.SB_MUTED}; background: transparent;"
            f"  letter-spacing: 0.01em;")
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
            ("Settings", "fa6s.gear", None),
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

        if status == 'review':
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
        for row in range(self.samples_table.rowCount()):
            item = self.samples_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == file_path:
                self.remove_file_at_row(row)
                return

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
        warnings = sum(1 for s in self.file_statuses.values()
                       if s in ('review', 'failed'))

        self._chip_loaded.setText(f"{total} loaded" if total else "0 loaded")
        self._chip_selected.setText(f"{selected} selected")
        if warnings > 0:
            self._chip_warnings.setText(f"\u26a0 {warnings}")
            self._chip_warnings.setVisible(True)
        else:
            self._chip_warnings.setVisible(False)

    def _push_card_meta(self, file_path: str):
        """Extract D50/K from loaded dataset and update the card."""
        sample_name = self.extract_sample_name(file_path)
        entry = self.loaded_samples.get(sample_name)
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
        # Also refresh the stratigraphy widget for the active card
        self._refresh_stratigraphy(file_path)

    # ── Classification / Stratigraphy ─────────────────────────────────────────

    def _open_classification_dialog(self):
        """Open the Classification System dialog and connect its signal."""
        from gui.classification_dialog import ClassificationDialog
        dlg = ClassificationDialog(current_scheme=self._active_scheme, parent=self.window())
        dlg.scheme_selected.connect(self._on_scheme_changed)
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

        sample_name = self.extract_sample_name(file_path)
        entry = self.loaded_samples.get(sample_name)
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

    def add_files(self):
        """Add multiple files for batch processing"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Grain Size Data Files",
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
                # Add files to tracking
                for file_entry in expanded_files:
                    if isinstance(file_entry, tuple):
                        file_path, sheet_name = file_entry
                        sheet_key = f"{file_path}:::{sheet_name}"
                        self.file_statuses[sheet_key] = 'pending'
                    else:
                        file_path = file_entry
                        self.file_statuses[file_path] = 'pending'

                # Add files to table
                for file_entry in expanded_files:
                    if isinstance(file_entry, tuple):
                        file_path, sheet_name = file_entry
                        sheet_key = f"{file_path}:::{sheet_name}"
                        self.add_file_to_table(sheet_key, 'pending', display_name=f"{os.path.basename(file_path)} [{sheet_name}]")
                    else:
                        self.add_file_to_table(file_entry, 'pending')

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

    def handle_batch_multisheet_excel(self, excel_files: list):
        """
        Smart batch handler for Excel files with multiple sheets.
        Groups files by sheet structure and shows one dialog per group.
        Returns: List of file entries (paths or tuples), or None if cancelled
        """
        import pandas as pd
        from collections import defaultdict

        # Group files by their sheet structure
        sheet_structure_groups = defaultdict(list)
        single_sheet_files = []
        error_files = []

        for file_path in excel_files:
            try:
                excel_file = pd.ExcelFile(file_path)
                sheet_names = tuple(excel_file.sheet_names)  # Tuple for hashability

                if len(sheet_names) == 1:
                    single_sheet_files.append(file_path)
                else:
                    sheet_structure_groups[sheet_names].append(file_path)
            except Exception as e:
                error_files.append(file_path)

        expanded_files = []

        # Handle single-sheet files (no dialog needed)
        expanded_files.extend(single_sheet_files)

        # Handle each group of multi-sheet files
        for sheet_names, group_files in sheet_structure_groups.items():
            if len(group_files) == 1:
                # Only one file with this structure - use individual dialog
                result = self.handle_multisheet_excel(group_files[0])
                if result is None:
                    expanded_files.append(group_files[0])
                elif result:
                    expanded_files.extend(result)
                else:  # User cancelled
                    return None
            else:
                # Multiple files with same structure - show batch dialog
                from gui.sheet_selector import SheetSelectorDialog

                # Create dialog with info about the batch
                first_file = group_files[0]
                dialog = SheetSelectorDialog(first_file, self)
                dialog.setWindowTitle(f"Select Sheets for {len(group_files)} Similar Workbooks")

                # Update info label to show batch context
                dialog.info_label.setText(
                    f"📊 Found {len(group_files)} workbooks with identical sheet structure.\n"
                    f"Sheets: {', '.join(sheet_names)}\n\n"
                    f"💡 Select which sheets to import from ALL {len(group_files)} workbooks.\n"
                    f"This selection will apply to all files in this batch."
                )

                if dialog.exec() == QDialog.DialogCode.Accepted:
                    selected_sheets = dialog.get_selected_sheets()
                    if not selected_sheets:
                        return None  # User cancelled

                    # Apply selection to all files in this group
                    for file_path in group_files:
                        for sheet in selected_sheets:
                            expanded_files.append((file_path, sheet))
                else:
                    return None  # User cancelled

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
            sheet_names = excel_file.sheet_names

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
        file_name = display_name or os.path.basename(file_path)
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
            'pending': '🔄 Processing...',
            'failed': '❌ Failed',
            'review': '⚠️ Needs Review',
            'loaded': '📄 Loaded'
        }
        return status_map.get(status, '❓ Unknown')

    def get_status_tooltip(self, status: str) -> str:
        """Get tooltip text for status"""
        tooltip_map = {
            'pending': 'File is being processed',
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
        if status == 'review':
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
            # Get file path
            file_item = self.samples_table.item(row, 0)
            file_path = file_item.data(Qt.ItemDataRole.UserRole)

            # Remove from tracking
            if file_path in self.file_statuses:
                del self.file_statuses[file_path]

            # Remove from loaded samples
            sample_name = self.extract_sample_name(file_path)
            if sample_name in self.loaded_samples:
                del self.loaded_samples[sample_name]

            # Remove from card list
            self._file_list.remove_card(file_path)

            # Remove from table
            self.samples_table.removeRow(row)

            self.update_ui_state()
            self.sample_info_label.setText(f"Removed: {os.path.basename(file_path)}")

    def edit_file_mapping(self, file_path: str):
        """Open column mapping dialog for a specific file"""
        try:
            actual_file_path, sheet_name = self._split_sheet_key(file_path)
            dialog = ColumnMapperDialog(actual_file_path, self, self.window(), sheet_name=sheet_name)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                mapping_results = dialog.get_mapping_results()
                if not mapping_results:
                    QMessageBox.warning(self, "No Data", "No sheet data was extracted.")
                    return
                self._apply_mapping_results(file_path, mapping_results, forced_sheet_name=sheet_name)

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
        sample_name = self.extract_sample_name(file_path)
        if sample_name not in self.loaded_samples:
            QMessageBox.information(self, "Inspect", "Dataset not yet loaded.")
            return

        dataset = self.loaded_samples[sample_name]['data']
        dlg = DataInspectorDialog(
            dataset=dataset,
            scheme=self._active_scheme,
            file_path=file_path,
            parent=self,
        )
        dlg.exec()

    def show_file_log(self, file_path: str):
        """Show the load-time validation log for a dataset."""
        sample_name = self.extract_sample_name(file_path)
        if sample_name not in self.loaded_samples:
            QMessageBox.information(self, "Log", "Dataset not yet loaded.")
            return

        dataset = self.loaded_samples[sample_name]['data']
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
        sample_name = self.extract_sample_name(file_path)
        if sample_name not in self.loaded_samples:
            QMessageBox.information(self, "Props", "Dataset not yet loaded.")
            return

        dataset = self.loaded_samples[sample_name]['data']

        # Find the dataset tab so we can push recalculation
        ds_tab = None
        if hasattr(self, 'main_window') and hasattr(self.main_window, 'dataset_tabs_widget'):
            for i in range(self.main_window.dataset_tabs_widget.count()):
                tab = self.main_window.dataset_tabs_widget.widget(i)
                if hasattr(tab, 'dataset') and tab.dataset is dataset:
                    ds_tab = tab
                    break

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
            hint = QLabel(f"Calculated (Urumovic): {calc_por:.4f}")
            hint.setStyleSheet(f"font-size: {F.SZ_XS}pt; color: {C.SB_MUTED};")
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
        # Check if already in the list
        if file_path in self.file_statuses:
            # Already tracked, just update status
            self.file_statuses[file_path] = 'loaded'
            self.update_file_in_table(file_path, 'loaded')
        else:
            # New file, add to tracking
            self.file_statuses[file_path] = 'loaded'
            sample_name = self.extract_sample_name(file_path)
            self.loaded_samples[sample_name] = {
                'file_path': file_path,
                'data': dataset,
                'datasets': [dataset],
                'status': 'loaded'
            }
            # Add to table
            self.add_file_to_table(file_path, 'loaded')

        self._push_card_meta(file_path)
        self._update_inventory_bar()
        self.update_ui_state()
        self.sample_info_label.setText(f"{len(self.loaded_samples)} sample(s) loaded")

    def review_failed_files(self):
        """Open manual column mapping for files that need review"""
        review_files = [path for path, status in self.file_statuses.items() if status == 'review']

        for file_path in review_files:
            try:
                actual_file_path, sheet_name = self._split_sheet_key(file_path)
                dialog = ColumnMapperDialog(actual_file_path, self, self.window(), sheet_name=sheet_name)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    mapping_results = dialog.get_mapping_results()
                    if not mapping_results:
                        continue
                    self._apply_mapping_results(file_path, mapping_results, forced_sheet_name=sheet_name)

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
            # Get file path
            file_item = self.samples_table.item(current_row, 0)
            file_path = file_item.data(Qt.ItemDataRole.UserRole)

            # Remove from tracking
            if file_path in self.file_statuses:
                del self.file_statuses[file_path]

            # Remove from loaded samples
            sample_name = self.extract_sample_name(file_path)
            if sample_name in self.loaded_samples:
                del self.loaded_samples[sample_name]

            # Remove from card list
            self._file_list.remove_card(file_path)

            # Remove from table
            self.samples_table.removeRow(current_row)

            self.update_ui_state()
            self.sample_info_label.setText(f"Removed: {os.path.basename(file_path)}")
        else:
            self.remove_file_btn.setEnabled(False)

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
            sample_name = self.extract_sample_name(file_path)
            if sample_name in self.loaded_samples and status == 'loaded':
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

    def _split_sheet_key(self, file_path: str):
        if ":::" in file_path:
            return file_path.split(":::", 1)
        return file_path, None

    def _apply_mapping_results(self, file_path: str, mapping_results: list, *, forced_sheet_name: str | None = None):
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
            created_datasets.append(dataset)

        if not created_datasets:
            return

        sample_key = created_datasets[0].sample_name
        sheet_names = [(mapping.get('sheet_name') or forced_sheet_name or '') for mapping in mapping_results]
        entry = {
            'file_path': file_path,
            'data': created_datasets[0],
            'datasets': created_datasets,
            'status': 'loaded',
            'sheet_names': sheet_names
        }
        self.loaded_samples[sample_key] = entry

        self.file_statuses[file_path] = 'loaded'
        self.update_file_in_table(file_path, 'loaded')
        self._push_card_meta(file_path)
        self._update_inventory_bar()

        for dataset in created_datasets:
            self.dataset_loaded_successfully.emit(dataset, file_path)

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
        loaded_count = sum(1 for status in self.file_statuses.values() if status == 'loaded')

        # Update batch action buttons
        self.review_failed_btn.setEnabled(review_count > 0)

        # Basic UI state
        self.remove_file_btn.setEnabled(has_selection)

        # If no manual status update, show file counts
        if has_files and not hasattr(self, '_manual_status_update'):
            if loaded_count > 0:
                summary = f"📊 {loaded_count} ready"
                if review_count > 0:
                    summary += f", {review_count} need review"
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
        """Handle porosity calculation mode change and recalculate K values"""
        # Determine which calculation mode is selected
        use_simple_formula = "Simple Formula" in mode_text

        # Update all loaded datasets to use the new porosity calculation mode
        if hasattr(self.parent(), 'dataset_tabs_widget'):
            main_window = self.parent()
            recalculated_count = 0

            for i in range(main_window.dataset_tabs_widget.count()):
                tab = main_window.dataset_tabs_widget.widget(i)
                if hasattr(tab, 'dataset') and hasattr(tab.dataset, 'recalculate_porosity'):
                    # Recalculate porosity using the selected method
                    if use_simple_formula:
                        new_porosity = tab.dataset._calculate_simple_porosity()
                    else:
                        new_porosity = tab.dataset._calculate_urumovic_porosity()

                    if new_porosity is not None:
                        tab.dataset.current_porosity = new_porosity
                        tab.porosity = new_porosity

                        # Update the dataset tab UI if it has porosity controls
                        if hasattr(tab, 'update_grain_statistics'):
                            tab.update_grain_statistics()
                        if hasattr(tab, 'statistics_tab'):
                            tab.statistics_tab.porosity = new_porosity
                            tab.statistics_tab.update_display()

                        # Recalculate K-values if they've been calculated before
                        if hasattr(tab, 'calculate_k_values') and hasattr(tab, 'current_results') and tab.current_results:
                            tab.calculate_k_values()
                            recalculated_count += 1

            if recalculated_count > 0:
                mode_name = "Simple Formula" if use_simple_formula else "Urumovic Polynomial"
                self.sample_info_label.setText(f"🕳️ Porosity mode changed to {mode_name} - {recalculated_count} dataset(s) recalculated")

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

    def process_files_with_immediate_tabs(self, file_entries: list):
        """Process files by creating tabs immediately, then attempting to load data

        Args:
            file_entries: List of file paths or (file_path, sheet_name) tuples
        """
        return self._process_files_with_loading_dialog(file_entries)

    def _process_files_with_loading_dialog(self, file_entries: list):
        if not file_entries:
            return
        if self._import_process is not None:
            if self._import_dialog is not None:
                self._import_dialog.raise_()
                self._import_dialog.activateWindow()
            return

        self.dataset_integration_started.emit()

        for file_entry in file_entries:
            if isinstance(file_entry, tuple):
                file_path, sheet_name = file_entry
                file_key = f"{file_path}:::{sheet_name}"
            else:
                file_key = file_entry
            self.error_dataset.emit(file_key, "Loading...")

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
            count_label=f"0 of {len(file_entries)} files",
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
                count_label=f"{current} of {total} files",
                activity_label=f"Processing file {current} of {total}.",
            )

    def _update_import_integration_progress(self):
        if self._import_dialog is None or self._import_ui_total <= 0:
            return

        current = max(0, min(self._import_ui_processed, self._import_ui_total))
        noun = "dataset" if self._import_ui_total == 1 else "datasets"
        overall_total = max(1, self._import_ui_total * 2)
        activity = (
            "Preparing workspace integration."
            if current <= 0
            else f"Integrating dataset {current} of {self._import_ui_total}."
        )
        self._import_dialog.update_progress(
            self._import_ui_total + current,
            overall_total,
            "Integrating datasets",
            "Adding loaded datasets to the workspace.",
            count_label=f"{current} of {self._import_ui_total} {noun}",
            activity_label=activity,
        )

    def _on_import_worker_loaded(self, file_key: str, dataset, status: str, sample_name: str):
        self.file_statuses[file_key] = status
        self.loaded_samples[sample_name] = {
            'file_path': file_key,
            'data': dataset,
            'datasets': [dataset],
            'status': status
        }
        self.dataset_loaded_successfully.emit(dataset, file_key)
        self.update_file_in_table(file_key, status)
        self._push_card_meta(file_key)
        self._update_inventory_bar()

    def _on_import_worker_validation_failed(self, file_key: str, dataset, sample_name: str, detail: str):
        self.file_statuses[file_key] = 'failed'
        self.loaded_samples[sample_name] = {
            'file_path': file_key,
            'data': dataset,
            'datasets': [dataset],
            'status': 'failed'
        }
        self.update_file_in_table(file_key, 'failed')
        self.update_error_tab_message.emit(file_key, detail)
        self._push_card_meta(file_key)
        self._update_inventory_bar()

    def _on_import_worker_failed(self, file_key: str, detail: str):
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
        from gui.help_dialog import HelpDialog
        help_dialog = HelpDialog(self.parent())
        help_dialog.exec()

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
            DTU Environment</p>

            <p><b>Supervised by:</b><br>
            Prof. Poul Løgstrup Bjerg</p>

            <p>© 2025 - DTU Environment</p>
            <p><em>Press F1 for detailed help topics</em></p>""")
