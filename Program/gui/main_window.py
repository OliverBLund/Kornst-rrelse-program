"""
Main window for the Grain Size Analysis application.
"""

from __future__ import annotations

from collections import deque
import multiprocessing as mp
import os
import queue
import time

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStatusBar, QStackedWidget, QTabWidget, QMessageBox,
    QProgressBar, QLabel, QFrame, QFileDialog,
    QPushButton, QSizePolicy, QToolButton, QMenu, QSplitter,
    QGraphicsOpacityEffect, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QSize, QTimer, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QAction, QColor, QFont
from typing import Any, Callable, List, Mapping, Optional

from gui.control_panel import ControlPanel
from gui.dataset_tab import DatasetTab
from gui.dataset_selection_dialog import DatasetSelectionDialog
from gui.comparison_tab import ComparisonTab
from gui.reporting_tab import ReportingTab
from gui.export_tab import ExportTab
from gui.error_tab import ErrorTab
from gui.loading_dialog import LoadingDialog
from gui.method_selection_dialog import MethodSelectionDialog
from gui.log_overlay import (
    InAppLogStore,
    LogDropdownPanel,
    install_in_app_logging,
    uninstall_in_app_logging,
)
from gui.stack_fade import StackFadeController, TabFadeInController
from gui.startup_tour import StartupTourOverlay, TourStep
from gui.welcome_widget import WelcomeWidget
from gui.theme import C, F, SZ, build_stylesheet, icon, apply_matplotlib_style, apply_tooltip_style, set_font_bump
from gui.plot_context import build_plot_context_from_tab
from qt_chrome import FramelessMainWindowMixin
from data_loader import DataLoader, GrainSizeData, get_test_data_files
from k_calculations import KCalculator
from method_registry import normalize_method_selection
from grain_classification import ISO14688
from load_process_worker import run_external_load


# ─────────────────────────────────────────────────────────────────────
# _AppToolbar  — matches _shared.css .tb
# ─────────────────────────────────────────────────────────────────────

WELCOME_SCREEN_PREF_REVISION = 2
UI_FONT_BUMP_DEFAULT = 1
UI_FONT_BUMP_KEY = "display/font_bump"


def _normalise_ui_font_bump(value) -> int:
    try:
        bump = int(value)
    except (TypeError, ValueError):
        bump = UI_FONT_BUMP_DEFAULT
    return max(0, min(1, bump))


def _read_ui_font_bump(settings) -> int:
    """Read the saved display-size preset."""
    return _normalise_ui_font_bump(
        settings.value(UI_FONT_BUMP_KEY, UI_FONT_BUMP_DEFAULT)
    )


def _save_ui_font_bump(settings, bump) -> int:
    """Persist the display-size preset and return the normalised value."""
    normalised = _normalise_ui_font_bump(bump)
    settings.setValue(UI_FONT_BUMP_KEY, normalised)
    return normalised


def _effective_welcome_dont_show(settings) -> bool:
    """Ignore stale welcome opt-out flags from older UI revisions."""
    stored_revision = settings.value("welcome_screen/revision", 0, type=int)
    dont_show = settings.value("welcome_screen/dont_show", False, type=bool)
    return bool(dont_show) and int(stored_revision) >= WELCOME_SCREEN_PREF_REVISION


def _save_welcome_preference(settings, dont_show: bool) -> None:
    settings.setValue("welcome_screen/dont_show", bool(dont_show))
    settings.setValue("welcome_screen/revision", WELCOME_SCREEN_PREF_REVISION)


class _AppToolbar(QWidget):
    """
    Global toolbar: navigation tabs (left) + log/help actions (right).
    Styled entirely via QSS properties defined in theme.build_stylesheet().
    """
    tab_changed = pyqtSignal(int)   # emits 0=Individual, 1=Comparison, 2=Reports, 3=Export
    log_clicked = pyqtSignal()
    help_clicked = pyqtSignal()

    _TABS = [
        ("fa6s.chart-area",    "Individual Samples"),
        ("fa6s.code-compare",  "Comparison"),
        ("fa6s.file-contract", "Reports"),
        ("fa6s.file-export",   "Export"),
    ]
    _CHROME_ICON_SIZE = QSize(13, 13)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("app-toolbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(SZ.TOOLBAR_H)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 8, 0)
        layout.setSpacing(0)

        self._active_index = 0
        self._nav_btns: list[QPushButton] = []
        self._badge_lbls: list[QLabel] = []

        # ── Nav tab buttons ──────────────────────────────────────────
        # Each tab is a QPushButton with a badge QLabel as a child widget
        # positioned via a layout inside the button. The badge is a styled
        # pill matching CSS: .t-badge { font:700 9px 'JetBrains Mono';
        #   padding:1px 5px; border-radius:99px; }
        for i, (fa, label) in enumerate(self._TABS):
            btn = QPushButton()
            btn.setObjectName(f"navtab-{i}")
            btn.setProperty("navtab", True)
            btn.setFixedHeight(SZ.TOOLBAR_H)
            btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setText(f"  {label}")
            btn.clicked.connect(lambda checked, idx=i: self._activate(idx))
            self._nav_btns.append(btn)
            layout.addWidget(btn)

            # Badge pill — child QLabel inside a layout on the button
            badge = QLabel(btn)
            badge.setObjectName("toolbar-badge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            badge_font = QFont(F.MONO, F.SZ_XS, QFont.Weight.Bold)
            badge.setFont(badge_font)
            badge.setFixedHeight(16)
            badge.setMinimumWidth(16)
            badge.hide()
            self._badge_lbls.append(badge)

        layout.addStretch()

        self._log_btn = QPushButton(" Log")
        self._log_btn.setObjectName("tb-log")
        self._log_btn.setProperty("toolaction", True)
        self._log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            self._log_btn.setIcon(icon("fa6s.clipboard-list", C.TEXT_MID))
            self._log_btn.setIconSize(self._CHROME_ICON_SIZE)
        except Exception:
            pass
        self._log_btn.clicked.connect(self.log_clicked)
        layout.addWidget(self._log_btn)
        layout.addSpacing(4)

        self._log_badge = QLabel(self._log_btn)
        self._log_badge.setObjectName("toolbar-badge")
        self._log_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._log_badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._log_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._log_badge.setFont(QFont(F.MONO, F.SZ_XS, QFont.Weight.Bold))
        self._log_badge.setFixedHeight(16)
        self._log_badge.setMinimumWidth(16)
        self._log_badge.hide()

        # ── Help — .tb-btn ───────────────────────────────────────────
        self._help_btn = QPushButton(" Help")
        self._help_btn.setObjectName("tb-help")
        self._help_btn.setProperty("toolaction", True)
        try:
            self._help_btn.setIcon(icon("fa6s.book", C.TEXT_MID))
            self._help_btn.setIconSize(self._CHROME_ICON_SIZE)
        except Exception:
            pass
        self._help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._help_btn.clicked.connect(self.help_clicked)
        layout.addWidget(self._help_btn)

        self._refresh_nav_styles()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Reposition badge pills when toolbar resizes
        self._reposition_badges()

    def _reposition_badges(self) -> None:
        """Move badge pills to correct position relative to button text."""
        for i, btn in enumerate(self._nav_btns):
            badge = self._badge_lbls[i]
            if badge.isVisible():
                self._position_badge(btn, badge)
        self._position_log_badge()

    @staticmethod
    def _badge_width(badge: QLabel) -> int:
        """Compute the pill width explicitly so QSS padding quirks do not flatten the badge."""
        return max(16, badge.fontMetrics().horizontalAdvance(badge.text()) + 10)

    def _nav_button_min_width(self, btn: QPushButton, badge: QLabel) -> int:
        """Keep badge pills inside the owning tab button instead of spilling into the next tab."""
        text_w = btn.fontMetrics().horizontalAdvance(btn.text())
        icon_w = btn.iconSize().width() + 8 if not btn.icon().isNull() else 0
        side_padding = 34
        badge_w = self._badge_width(badge) + 14 if badge.isVisible() else 0
        return text_w + icon_w + side_padding + badge_w

    def _update_nav_button_width(self, index: int) -> None:
        btn = self._nav_btns[index]
        badge = self._badge_lbls[index]
        btn.setMinimumWidth(self._nav_button_min_width(btn, badge))
        btn.updateGeometry()

    def _position_badge(self, btn: QPushButton, badge: QLabel) -> None:
        badge.setFixedWidth(self._badge_width(badge))
        bx = max(8, btn.width() - badge.width() - 10)
        by = (btn.height() - badge.height()) // 2
        badge.move(bx, by)

    @staticmethod
    def _badge_stylesheet(active: bool) -> str:
        bg = "rgba(107,142,35,0.10)" if active else C.BG_LOW
        fg = C.OLIVE if active else C.TEXT_MUTED
        border = "rgba(107,142,35,0.30)" if active else C.BORDER
        return (
            f"background: {bg}; color: {fg}; "
            "border-radius: 8px; "
            f"border: 1px solid {border};"
        )

    def _activate(self, index: int) -> None:
        if self._active_index == index:
            return
        self._active_index = index
        self._refresh_nav_styles()
        self.tab_changed.emit(index)

    def activate_tab(self, index: int) -> None:
        """Set active tab without emitting tab_changed (for programmatic switches)."""
        self._active_index = index
        self._refresh_nav_styles()

    def set_badge(self, tab_index: int, count: int | None) -> None:
        """Set or hide a badge on a nav tab (e.g., dataset count)."""
        if 0 <= tab_index < len(self._badge_lbls):
            badge = self._badge_lbls[tab_index]
            if count is not None and count > 0:
                badge.setText(str(count))
                badge.show()
            else:
                badge.setText("")
                badge.hide()
            self._update_nav_button_width(tab_index)
            self._refresh_nav_styles()

    def log_button(self) -> QPushButton:
        return self._log_btn

    def set_log_badge(self, count: int | None) -> None:
        if count is not None and count > 0:
            self._log_badge.setText(str(count))
            self._log_badge.setStyleSheet(
                f"background: rgba(208,128,32,0.18); color: {C.LED_WARN}; "
                "border: 1px solid rgba(208,128,32,0.42); border-radius: 8px;"
            )
            self._log_badge.show()
        else:
            self._log_badge.setText("")
            self._log_badge.hide()
        self._position_log_badge()

    def set_log_active(self, active: bool) -> None:
        self._log_btn.setProperty("active", bool(active))
        self._log_btn.style().unpolish(self._log_btn)
        self._log_btn.style().polish(self._log_btn)

    def _position_log_badge(self) -> None:
        if not hasattr(self, "_log_badge") or not self._log_badge.isVisible():
            return
        self._log_badge.setFixedWidth(self._badge_width(self._log_badge))
        bx = max(6, self._log_btn.width() - self._log_badge.width() - 5)
        self._log_badge.move(bx, 2)

    def _refresh_nav_styles(self) -> None:
        for i, btn in enumerate(self._nav_btns):
            active = i == self._active_index
            btn.setProperty("active", active)

            # Force style refresh — unpolish + polish
            btn.style().unpolish(btn)
            btn.style().polish(btn)

            # Icon color
            try:
                btn.setIcon(icon(
                    self._TABS[i][0],
                    C.OLIVE if active else C.TEXT_MUTED,
                ))
                btn.setIconSize(self._CHROME_ICON_SIZE)
            except Exception:
                pass

            # Badge pill styling — olive-tinted when active, neutral otherwise
            badge = self._badge_lbls[i]
            self._update_nav_button_width(i)
            if badge.isVisible():
                badge.setStyleSheet(self._badge_stylesheet(active))
                self._position_badge(btn, badge)


# ─────────────────────────────────────────────────────────────────────
# _RichStatusBar  — matches _shared.css .st
# ─────────────────────────────────────────────────────────────────────

class _RichStatusBar(QStatusBar):
    """
    Custom status bar with LED indicator + dataset info segments.
    Segments: SAMPLE · D50 · K̄ · TEMP · METHODS · DATASETS
    LED blinks on a 4s cycle (opacity 1.0 ↔ 0.35).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("app-statusbar")
        self.setSizeGripEnabled(False)
        self.setFixedHeight(SZ.STATUS_H)
        self._label_effects: dict[QLabel, QGraphicsOpacityEffect] = {}
        self._label_animations: dict[QLabel, QPropertyAnimation] = {}

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        # LED dot — status pill area
        self._led = QLabel()
        self._led.setFixedSize(6, 6)
        self._led_ok = True
        self._led_visible = True
        self._led.setStyleSheet(
            f"background: {C.LED_OK_ST}; border-radius: 3px;")
        self._led_effect = QGraphicsOpacityEffect(self._led)
        self._led_effect.setOpacity(1.0)
        self._led.setGraphicsEffect(self._led_effect)
        layout.addWidget(self._led)
        layout.addSpacing(5)

        # Status text (e.g. "Ready")
        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(
            f"color: #a0d070; font-family: '{F.MONO}'; font-size: {F.SZ_SM}pt;")
        self._status_effect = QGraphicsOpacityEffect(self._status_lbl)
        self._status_effect.setOpacity(1.0)
        self._status_lbl.setGraphicsEffect(self._status_effect)
        self._label_effects[self._status_lbl] = self._status_effect
        layout.addWidget(self._status_lbl)

        # Segments: SAMPLE · D50 · K̄ · TEMP · METHODS · DATASETS
        self._seg_vals: dict[str, QLabel] = {}
        for key in ("SAMPLE", "D50", "K\u0304", "TEMP", "METHODS", "DATASETS"):
            layout.addWidget(self._vline())
            lbl_k = QLabel(f" {key} ")
            lbl_k.setStyleSheet(
                f"color: {C.ST_DIM}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;")
            lbl_v = QLabel("\u2014")
            lbl_v.setStyleSheet(
                f"color: {C.ST_TEXT}; font-family: '{F.MONO}'; "
                f"font-size: {F.SZ_SM}pt; margin-right: 2px;")
            layout.addWidget(lbl_k)
            layout.addWidget(lbl_v)
            self._seg_vals[key] = lbl_v

        layout.addStretch()
        self.addWidget(container, 1)

        # Progress bar (right side)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(180)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setVisible(False)
        self.addPermanentWidget(self.progress_bar)

        # Version label (right side) — JetBrains Mono, st-dim color
        ver = QLabel("v0.9-beta ")
        ver.setStyleSheet(
            f"color: {C.ST_DIM}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; "
            f"padding-left: 10px; border-left: 1px solid rgba(255,255,255,0.15);")
        self.addPermanentWidget(ver)

        # LED blink timer (4 second cycle)
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(2000)  # toggle every 2s (full cycle = 4s)
        self._blink_timer.timeout.connect(self._toggle_led)
        self._blink_timer.start()

    def _vline(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setFixedSize(1, 12)
        f.setStyleSheet("background: rgba(255,255,255,0.15); margin: 0 8px;")
        return f

    def _toggle_led(self) -> None:
        """Blink the LED between full and dim opacity."""
        if not self._led_ok:
            return  # don't blink when in warning/error state
        self._led_visible = not self._led_visible
        self._led_effect.setOpacity(1.0 if self._led_visible else 0.4)

    def set_status(self, text: str, ok: bool = True) -> None:
        changed = text != self._status_lbl.text() or ok != self._led_ok
        self._status_lbl.setText(text)
        self._led_ok = ok
        self._led_visible = True
        color = C.LED_OK_ST if ok else C.LED_WARN
        text_color = "#a0d070" if ok else C.LED_WARN
        self._led.setStyleSheet(f"background: {color}; border-radius: 3px;")
        self._led_effect.setOpacity(1.0)
        self._status_lbl.setStyleSheet(
            f"color: {text_color}; font-family: '{F.MONO}'; font-size: {F.SZ_SM}pt;")
        if changed:
            self._pulse_label(self._status_lbl, low_opacity=0.58, duration_ms=170)

    def set_segment(self, key: str, value: str) -> None:
        if key in self._seg_vals:
            label = self._seg_vals[key]
            if label.text() != value:
                label.setText(value)
                self._pulse_label(label, low_opacity=0.68, duration_ms=150)

    def _pulse_label(
        self,
        label: QLabel,
        *,
        low_opacity: float,
        duration_ms: int,
    ) -> None:
        effect = self._label_effects.get(label)
        if effect is None:
            effect = QGraphicsOpacityEffect(label)
            effect.setOpacity(1.0)
            label.setGraphicsEffect(effect)
            self._label_effects[label] = effect

        animation = self._label_animations.get(label)
        if animation is None:
            animation = QPropertyAnimation(effect, b"opacity", self)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._label_animations[label] = animation
        else:
            animation.stop()

        effect.setOpacity(low_opacity)
        animation.setDuration(duration_ms)
        animation.setStartValue(low_opacity)
        animation.setEndValue(1.0)
        animation.start()


# ─────────────────────────────────────────────────────────────────────
# MainWindow
# ─────────────────────────────────────────────────────────────────────

class MainWindow(FramelessMainWindowMixin, QMainWindow):
    """Main application window."""

    def __init__(
        self,
        startup_progress_callback: Callable[[int, str, str], None] | None = None,
    ):
        super().__init__()
        self._startup_progress_callback = startup_progress_callback

        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        self._ui_font_bump = _read_ui_font_bump(settings)
        set_font_bump(self._ui_font_bump)

        self.setWindowTitle("Grain Size Analysis \u2014 Hydraulic Conductivity Calculator")
        self.init_frameless_window_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=8,
            top_resize_margin=2,
            corner_radius_px=10,
            enable_edge_resize=True,
            enable_windows_snap_styles=False,
        )

        # Apply matplotlib styling before any plots are created
        self._emit_startup_progress(
            82,
            "Configuring plot styles",
            "Applying plot defaults and typography.",
        )
        apply_matplotlib_style()

        # Data structures
        self.data_loader = DataLoader()
        self.k_calculator = KCalculator()
        self.available_method_names = tuple(self.k_calculator.get_all_method_names())
        self.active_method_names = normalize_method_selection(
            None, available_methods=self.available_method_names
        )
        self.dataset_tabs: List[DatasetTab] = []
        self.dataset_counter = 0
        self.active_scheme = ISO14688
        self._bulk_dataset_add_depth = 0
        self._bulk_dataset_add_dirty = False
        self._bulk_dataset_add_last_index = None
        self._bulk_dataset_add_last_label = ""
        self._external_load_process = None
        self._external_load_queue = None
        self._external_load_finished_received = False
        self._external_load_finalize_summary = None
        self._pending_external_ui_events = deque()
        self._external_ui_total = 0
        self._external_ui_processed = 0
        self._external_load_dialog = None
        self._external_load_context = None
        self._dataset_group_manager_active = False
        self._dataset_group_manager_last_closed_at = 0.0
        self._help_dialog = None
        self._startup_tour = None
        self._suppress_calculation_refresh_depth = 0
        self._external_load_poll_timer = QTimer(self)
        self._external_load_poll_timer.setInterval(25)
        self._external_load_poll_timer.timeout.connect(self._poll_external_load_process)
        self._external_load_ui_timer = QTimer(self)
        self._external_load_ui_timer.setInterval(0)
        self._external_load_ui_timer.timeout.connect(self._process_external_load_ui_slice)
        self.log_store = InAppLogStore(self)
        self._qt_log_handler = install_in_app_logging(self.log_store)
        self._log_overlay = None

        # Global stylesheet
        self._emit_startup_progress(
            85,
            "Applying interface theme",
            "Styling the application shell and controls.",
        )
        stylesheet = build_stylesheet()
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet)
            apply_tooltip_style(app)
        self.setStyleSheet(stylesheet)

        self._emit_startup_progress(
            88,
            "Building workspace shell",
            "Creating the sidebar, tabs, and startup views.",
        )
        self.setup_ui()
        self._emit_startup_progress(
            92,
            "Building navigation",
            "Preparing menus, toolbar actions, and window chrome.",
        )
        self.setup_menus()
        self._emit_startup_progress(
            95,
            "Preparing status panels",
            "Connecting the status bar and welcome workspace.",
        )
        self.setup_statusbar()

        self._show_status_message("Ready")
        self._emit_startup_progress(
            97,
            "Workspace assembled",
            "Final startup checks are complete.",
        )

    def _emit_startup_progress(self, percent: int, stage: str, detail: str) -> None:
        """Forward startup milestones to the splash when one is active."""
        if self._startup_progress_callback is not None:
            self._startup_progress_callback(percent, stage, detail)

    # ──────────────────────────────────────────────────────────────────
    # UI SETUP
    # ──────────────────────────────────────────────────────────────────

    def setup_ui(self):
        """Build the application layout."""
        central = QWidget()
        central.setObjectName("central-widget")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar (resizable via splitter) ───────────────────────
        self.control_panel = ControlPanel()
        self.control_panel.setMinimumWidth(318)
        self.control_panel.error_dataset.connect(self.add_error_tab)
        self.control_panel.mapping_required.connect(self.add_mapping_required_tab)
        self.control_panel.dataset_loaded_successfully.connect(self.replace_error_tab_with_dataset)
        self.control_panel.update_error_tab_message.connect(self.update_error_tab_message)
        self.control_panel.dataset_integration_started.connect(self._begin_bulk_dataset_add)
        self.control_panel.dataset_integration_finished.connect(self._end_bulk_dataset_add)
        self.control_panel.sample_selected.connect(self._on_sidebar_sample_selected)
        self.control_panel.selection_changed.connect(self._on_sidebar_selection_changed)
        self.control_panel.manage_datasets_requested.connect(self._open_dataset_group_manager)
        self.control_panel.scheme_changed.connect(self._on_scheme_changed)

        # ── Main area ──────────────────────────────────────────────
        main_widget = QWidget()
        main_widget.setObjectName("main-area")
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Global toolbar
        self.app_toolbar = _AppToolbar()
        self.app_toolbar.tab_changed.connect(self._on_nav_tab_changed)
        self.app_toolbar.log_clicked.connect(self.toggle_log_overlay)
        self.app_toolbar.help_clicked.connect(self.show_help)
        main_layout.addWidget(self.app_toolbar)

        self._log_overlay = LogDropdownPanel(self.log_store, self)
        self._log_overlay.closed.connect(lambda: self.app_toolbar.set_log_active(False))
        self.log_store.unread_changed.connect(self.app_toolbar.set_log_badge)

        # Content stack (one page per top-level tab)
        self.content_stack = QStackedWidget()
        self._content_stack_fader = StackFadeController(
            self.content_stack,
            self,
            fade_out_ms=90,
            fade_in_ms=120,
        )
        main_layout.addWidget(self.content_stack)

        # Page 0 — Individual Samples
        samples_container = QWidget()
        sc_layout = QVBoxLayout(samples_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)
        sc_layout.setSpacing(0)

        self.dataset_tabs_widget = QTabWidget()
        self.dataset_tabs_widget.setDocumentMode(True)
        self.dataset_tabs_widget.setIconSize(QSize(12, 12))
        self.dataset_tabs_widget.setTabsClosable(True)
        self.dataset_tabs_widget.tabCloseRequested.connect(self.close_dataset_tab)
        self._dataset_tab_fader = TabFadeInController(
            self.dataset_tabs_widget,
            self,
            duration_ms=105,
        )
        self._configure_dataset_tab_bar()
        # Tab styling handled by global QSS in theme.build_stylesheet()

        recent_files = self._load_recent_files()
        recent_sessions = self._load_recent_sessions()
        self.welcome_widget = WelcomeWidget(
            recent_files=recent_files,
            recent_sessions=recent_sessions,
        )
        self._connect_welcome_signals()

        # Inner stack: index 0 = welcome (full-area, no tab chrome),
        #              index 1 = dataset_tabs_widget
        self._samples_stack = QStackedWidget()
        self._samples_stack_fader = StackFadeController(
            self._samples_stack,
            self,
            fade_out_ms=80,
            fade_in_ms=110,
        )
        self._samples_stack.addWidget(self.welcome_widget)
        self._samples_stack.addWidget(self.dataset_tabs_widget)

        settings_tmp = QSettings("GrainSizeAnalysis", "MainWindow")
        dont_show = _effective_welcome_dont_show(settings_tmp)
        self._samples_stack.setCurrentIndex(0 if not dont_show else 1)
        # Sidebar is only visible when datasets are shown
        self.control_panel.setVisible(dont_show)
        self._sync_welcome_preference_state()

        self.dataset_tabs_widget.currentChanged.connect(self._on_dataset_tab_changed)
        self._refresh_dataset_tab_icons()
        sc_layout.addWidget(self._samples_stack)
        self.content_stack.addWidget(samples_container)

        # Page 1 — Comparison
        self.comparison_tab = ComparisonTab()
        self.comparison_tab.dataset_selection_requested.connect(
            self._on_comparison_selection_requested
        )
        self.comparison_tab.method_selection_requested.connect(self.choose_k_methods)
        self.content_stack.addWidget(self.comparison_tab)

        # Page 2 — Reports
        self.reporting_tab = ReportingTab()
        self.content_stack.addWidget(self.reporting_tab)

        # Page 3 — Export
        self.export_tab = ExportTab()
        self.export_tab.jump_to_dataset_requested.connect(self._on_export_dataset_requested)
        self.export_tab.dataset_selection_requested.connect(self._on_export_selection_requested)
        self.content_stack.addWidget(self.export_tab)

        shell_splitter = QSplitter(Qt.Orientation.Horizontal)
        shell_splitter.setObjectName("shell-splitter")
        shell_splitter.setChildrenCollapsible(False)
        shell_splitter.setHandleWidth(6)
        shell_splitter.addWidget(self.control_panel)
        shell_splitter.addWidget(main_widget)
        shell_splitter.setStretchFactor(0, 0)
        shell_splitter.setStretchFactor(1, 1)
        shell_splitter.setSizes([max(SZ.SIDEBAR_W, 330), 1200])
        self._shell_splitter = shell_splitter

        root.addWidget(shell_splitter)

    def setup_menus(self):
        """Build the menu bar."""
        menu_widget = QWidget()
        menu_widget.setObjectName("app-menubar")
        menu_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        menu_widget.setFixedHeight(SZ.MENUBAR_H)
        menu_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        menu_layout = QHBoxLayout(menu_widget)
        menu_layout.setContentsMargins(6, 0, 4, 0)
        menu_layout.setSpacing(0)

        # File
        file_menu = QMenu("File", self)
        open_processed_action = QAction("&Open Processed Sieve Data\u2026", self)
        open_processed_action.setShortcut("Ctrl+O")
        open_processed_action.setIcon(icon("fa6s.folder-open", C.TEXT_MUTED))
        open_processed_action.triggered.connect(lambda _checked=False: self.control_panel.add_files("processed"))
        file_menu.addAction(open_processed_action)
        self.addAction(open_processed_action)

        open_raw_action = QAction("Open &Raw Sieve Weighings\u2026", self)
        open_raw_action.setIcon(icon("fa6s.table-columns", C.TEXT_MUTED))
        open_raw_action.triggered.connect(lambda _checked=False: self.control_panel.add_files("raw_sieve"))
        file_menu.addAction(open_raw_action)

        file_menu.addSeparator()

        export_results_action = QAction("Export &Results\u2026", self)
        export_results_action.setShortcut("Ctrl+E")
        export_results_action.setIcon(icon("fa6s.file-export", C.TEXT_MUTED))
        export_results_action.triggered.connect(self.export_results)
        file_menu.addAction(export_results_action)
        self.addAction(export_results_action)

        export_plot_action = QAction("Export &Plot\u2026", self)
        export_plot_action.setIcon(icon("fa6s.image", C.TEXT_MUTED))
        export_plot_action.triggered.connect(self.export_plot)
        file_menu.addAction(export_plot_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setIcon(icon("fa6s.right-from-bracket", C.TEXT_MUTED))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        self.addAction(exit_action)
        menu_layout.addWidget(self._make_menu_button("File", file_menu))

        # Analysis
        analysis_menu = QMenu("Analysis", self)

        analysis_settings_action = QAction("&Analysis Settings...", self)
        analysis_settings_action.setIcon(icon("fa6s.sliders", C.TEXT_MUTED))
        analysis_settings_action.triggered.connect(
            self.control_panel.open_analysis_settings_dialog
        )
        analysis_menu.addAction(analysis_settings_action)

        porosity_settings_action = QAction("&Dataset Porosity...", self)
        porosity_settings_action.setIcon(icon("fa6s.water", C.TEXT_MUTED))
        porosity_settings_action.triggered.connect(self.control_panel.open_porosity_dialog)
        analysis_menu.addAction(porosity_settings_action)

        classification_action = QAction("&Classification Scheme...", self)
        classification_action.setIcon(icon("fa6s.layer-group", C.TEXT_MUTED))
        classification_action.triggered.connect(
            self.control_panel.open_classification_dialog
        )
        analysis_menu.addAction(classification_action)

        analysis_menu.addSeparator()

        calculate_action = QAction("&Recalculate K Values", self)
        calculate_action.setShortcut("Ctrl+K")
        calculate_action.setIcon(icon("fa6s.bolt", C.TEXT_MUTED))
        calculate_action.triggered.connect(self.calculate_all_k_values)
        analysis_menu.addAction(calculate_action)
        self.addAction(calculate_action)

        choose_methods_action = QAction("Choose &K Methods\u2026", self)
        choose_methods_action.setIcon(icon("fa6s.sliders", C.TEXT_MUTED))
        choose_methods_action.triggered.connect(self.choose_k_methods)
        analysis_menu.addAction(choose_methods_action)

        analysis_menu.addSeparator()

        update_comparison_action = QAction("&Update Comparison", self)
        update_comparison_action.setIcon(icon("fa6s.rotate", C.TEXT_MUTED))
        update_comparison_action.triggered.connect(self.update_comparison)
        analysis_menu.addAction(update_comparison_action)
        self._analysis_menu_btn = self._make_menu_button("Analysis", analysis_menu)
        menu_layout.addWidget(self._analysis_menu_btn)

        # View
        view_menu = QMenu("View", self)

        ind_action = QAction("Individual Samples", self)
        ind_action.setShortcut("Ctrl+1")
        ind_action.setIcon(icon("fa6s.chart-area", C.TEXT_MUTED))
        ind_action.triggered.connect(lambda: self._switch_to_tab(0))
        view_menu.addAction(ind_action)
        self.addAction(ind_action)

        cmp_action = QAction("Comparison", self)
        cmp_action.setShortcut("Ctrl+2")
        cmp_action.setIcon(icon("fa6s.code-compare", C.TEXT_MUTED))
        cmp_action.triggered.connect(lambda: self._switch_to_tab(1))
        view_menu.addAction(cmp_action)
        self.addAction(cmp_action)

        rep_action = QAction("Reports", self)
        rep_action.setShortcut("Ctrl+3")
        rep_action.setIcon(icon("fa6s.file-contract", C.TEXT_MUTED))
        rep_action.triggered.connect(lambda: self._switch_to_tab(2))
        view_menu.addAction(rep_action)
        self.addAction(rep_action)

        exp_action = QAction("Export", self)
        exp_action.setShortcut("Ctrl+4")
        exp_action.setIcon(icon("fa6s.file-export", C.TEXT_MUTED))
        exp_action.triggered.connect(lambda: self._switch_to_tab(3))
        view_menu.addAction(exp_action)
        self.addAction(exp_action)
        menu_layout.addWidget(self._make_menu_button("View", view_menu))

        # Help
        help_menu = QMenu("Help", self)

        startup_guide_action = QAction("&Startup Guide", self)
        startup_guide_action.setIcon(icon("fa6s.route", C.TEXT_MUTED))
        startup_guide_action.triggered.connect(self.show_startup_guide)
        help_menu.addAction(startup_guide_action)

        individual_guide_action = QAction("Guide &Individual Samples", self)
        individual_guide_action.setIcon(icon("fa6s.chart-area", C.TEXT_MUTED))
        individual_guide_action.triggered.connect(self.show_individual_samples_guide)
        help_menu.addAction(individual_guide_action)

        comparison_guide_action = QAction("Guide &Comparison", self)
        comparison_guide_action.setIcon(icon("fa6s.code-compare", C.TEXT_MUTED))
        comparison_guide_action.triggered.connect(self.show_comparison_guide)
        help_menu.addAction(comparison_guide_action)

        reports_guide_action = QAction("Guide &Reports", self)
        reports_guide_action.setIcon(icon("fa6s.file-contract", C.TEXT_MUTED))
        reports_guide_action.triggered.connect(self.show_reports_guide)
        help_menu.addAction(reports_guide_action)

        export_guide_action = QAction("Guide &Export", self)
        export_guide_action.setIcon(icon("fa6s.file-export", C.TEXT_MUTED))
        export_guide_action.triggered.connect(self.show_export_guide)
        help_menu.addAction(export_guide_action)

        help_menu.addSeparator()

        help_action = QAction("&Help Topics", self)
        help_action.setShortcut("F1")
        help_action.setIcon(icon("fa6s.book", C.TEXT_MUTED))
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
        self.addAction(help_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.setIcon(icon("fa6s.circle-info", C.TEXT_MUTED))
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        menu_layout.addWidget(self._make_menu_button("Help", help_menu))

        spacer = QWidget()
        spacer.setObjectName("menubar-spacer")
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        menu_layout.addWidget(spacer)

        title_label = QLabel("Grain Size Analysis — Hydraulic Conductivity Calculator")
        title_label.setObjectName("menubar-title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        menu_layout.addWidget(title_label)

        controls = QWidget()
        controls.setObjectName("window-controls")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 0, 0, 0)
        controls_layout.setSpacing(0)

        self._win_min_btn = self._make_window_control_button("minimize")
        self._win_min_btn.clicked.connect(self.showMinimized)
        controls_layout.addWidget(self._win_min_btn)

        self._win_max_btn = self._make_window_control_button("maximize")
        self._win_max_btn.clicked.connect(self.toggle_window_maximize)
        controls_layout.addWidget(self._win_max_btn)

        self._win_close_btn = self._make_window_control_button("close")
        self._win_close_btn.clicked.connect(self.close)
        controls_layout.addWidget(self._win_close_btn)
        menu_layout.addWidget(controls)

        self.setMenuWidget(menu_widget)
        self._chrome_menu_widget = menu_widget
        self._chrome_drag_spacer = spacer
        self._chrome_controls = controls
        self._chrome_title_label = title_label
        # Header blank areas behave like a title bar: drag on hold/move,
        # double-click to maximize/restore. Buttons remain normal controls.
        self.bind_frameless_drag_widget(menu_widget, allow_double_click_maximize=True, include_children=False)
        self.bind_frameless_drag_widget(spacer, allow_double_click_maximize=True, include_children=False)
        self.on_window_chrome_state_changed(self._is_frameless_mode(), self.is_window_effectively_maximized())

    def _make_menu_button(self, label: str, menu: QMenu) -> QToolButton:
        """Create a concept-style top menu button backed by a QMenu."""
        btn = QToolButton(self)
        btn.setObjectName(f"menu-btn-{label.lower()}")
        btn.setProperty("menubaritem", True)
        btn.setText(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setMenu(menu)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setAutoRaise(True)
        btn.setFixedHeight(SZ.MENUBAR_H)
        return btn

    def _make_window_control_button(self, role: str) -> QToolButton:
        """Create a frameless-window caption control."""
        btn = QToolButton(self)
        btn.setObjectName(f"window-control-{role}")
        btn.setProperty("windowcontrol", True)
        btn.setProperty("controlrole", role)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setAutoRaise(True)
        btn.setFixedSize(34, SZ.MENUBAR_H)
        return btn

    def _refresh_window_control_icons(self, is_maximized: bool) -> None:
        """Update caption control icons to match the current window state."""
        if not hasattr(self, "_win_min_btn"):
            return
        self._win_min_btn.setIcon(icon("fa6s.minus", C.TEXT_MID))
        max_icon = "fa6s.clone" if is_maximized else "fa6s.square"
        self._win_max_btn.setIcon(icon(max_icon, C.TEXT_MID))
        self._win_close_btn.setIcon(icon("fa6s.xmark", C.TEXT_MID))
        for btn in (self._win_min_btn, self._win_max_btn, self._win_close_btn):
            btn.setIconSize(QSize(12, 12))

    def on_window_chrome_state_changed(self, is_frameless: bool, is_maximized: bool) -> None:
        """Sync custom caption controls with the active chrome mode."""
        if hasattr(self, "_chrome_controls"):
            self._chrome_controls.setVisible(is_frameless)
        if hasattr(self, "_chrome_menu_widget"):
            self._chrome_menu_widget.setProperty("frameless", is_frameless)
            self._chrome_menu_widget.style().unpolish(self._chrome_menu_widget)
            self._chrome_menu_widget.style().polish(self._chrome_menu_widget)
        self._refresh_window_control_icons(is_maximized)

    def _configure_dataset_tab_bar(self) -> None:
        """Keep dataset pages in a tab widget while the sidebar owns navigation."""
        tab_bar = self.dataset_tabs_widget.tabBar()
        tab_bar.setExpanding(False)
        tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        tab_bar.setDrawBase(False)
        tab_bar.hide()

    def _show_welcome(self) -> None:
        """Show the welcome panel (hide dataset tabs and sidebar)."""
        self._samples_stack.setCurrentIndex(0)
        self.control_panel.setVisible(False)

    def _hide_welcome(self) -> None:
        """Show the dataset tabs (restore sidebar)."""
        self._samples_stack.setCurrentIndex(1)
        self.control_panel.setVisible(True)

    def _dataset_tab_icon(self, widget: QWidget, active: bool):
        """Return the appropriate qtawesome icon for each dataset sub-tab."""
        color = C.TEXT if active else C.TEXT_MUTED
        if isinstance(widget, ErrorTab):
            if getattr(widget, "issue_variant", "") == "mapping_required":
                return icon("fa6s.table-columns", C.OLIVE if not active else C.OLIVE_DK)
            return icon("fa6s.triangle-exclamation", C.LED_ERR if not active else "#b03a2e")
        return icon("fa6s.vial", color)

    def _refresh_dataset_tab_icons(self) -> None:
        """Keep sub-tab icons in sync with the selected state."""
        current_index = self.dataset_tabs_widget.currentIndex()
        for i in range(self.dataset_tabs_widget.count()):
            widget = self.dataset_tabs_widget.widget(i)
            if widget is None:
                continue
            self.dataset_tabs_widget.setTabIcon(i, self._dataset_tab_icon(widget, i == current_index))
            self.dataset_tabs_widget.setTabToolTip(i, self.dataset_tabs_widget.tabText(i))

    def setup_statusbar(self):
        """Install the rich status bar."""
        self.rich_status_bar = _RichStatusBar()
        self.setStatusBar(self.rich_status_bar)
        # Keep a reference to the progress bar for existing code
        self.progress_bar = self.rich_status_bar.progress_bar

    # ──────────────────────────────────────────────────────────────────
    # NAVIGATION HELPERS
    # ──────────────────────────────────────────────────────────────────

    def _switch_to_tab(self, index: int) -> None:
        """Switch to a top-level tab and keep toolbar in sync."""
        self.app_toolbar.activate_tab(index)
        self._switch_content_page(index)

    def _on_nav_tab_changed(self, index: int) -> None:
        """Respond to top-level tab changes emitted by the toolbar."""
        self._switch_content_page(index)

    def _switch_content_page(self, index: int) -> None:
        """Animate a top-level page switch, then run the page-specific refresh."""
        self._content_stack_fader.switch_to(
            index,
            after_switch=lambda idx=index: self._post_nav_tab_switch(idx),
        )

    def _post_nav_tab_switch(self, index: int) -> None:
        """Run lightweight page-entry sync after the top-level view changes."""
        if index == 1 and len(self.dataset_tabs) >= 2:
            self.comparison_tab.update_comparison()
        elif index == 2:
            self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
        elif index == 3:
            self._update_export_tab()

    def _on_sidebar_sample_selected(self, sample_name: str) -> None:
        """When a sidebar card is clicked, switch to that dataset's tab."""
        # Also make sure we're on the Individual Samples page
        if self.content_stack.currentIndex() != 0:
            self._switch_to_tab(0)
        self._hide_welcome()
        for i in range(self.dataset_tabs_widget.count()):
            tab = self.dataset_tabs_widget.widget(i)
            if hasattr(tab, 'dataset') and tab.dataset.sample_name == sample_name:
                self.dataset_tabs_widget.setCurrentIndex(i)
                return

    def _on_export_dataset_requested(self, sample_name: str) -> None:
        """Open a dataset tab requested from the Export page."""
        self._on_sidebar_sample_selected(sample_name)

    def _on_dataset_tab_changed(self, index: int) -> None:
        """When a dataset tab is clicked, highlight the corresponding sidebar card."""
        self._refresh_dataset_tab_icons()
        tab = self.dataset_tabs_widget.widget(index)
        if tab and hasattr(tab, 'dataset'):
            # Find the file_path for this dataset in the sidebar
            for fp, status in self.control_panel.file_statuses.items():
                sample_name = self.control_panel.extract_sample_name(fp)
                if sample_name == tab.dataset.sample_name or fp.endswith(tab.dataset.sample_name):
                    self.control_panel._file_list.set_active(fp)
                    return
            # Fallback: try matching by dataset.sample_name in loaded_samples
            for sname, entry in self.control_panel.loaded_samples.items():
                if entry.get('data') and entry['data'].sample_name == tab.dataset.sample_name:
                    fp = entry.get('file_path', '')
                    if fp:
                        self.control_panel._file_list.set_active(fp)
                    return
        else:
            # Non-dataset tab — deselect sidebar
            self.control_panel._file_list.set_active(None)

    # ──────────────────────────────────────────────────────────────────
    # WELCOME WIDGET HELPERS
    # ──────────────────────────────────────────────────────────────────

    def _connect_welcome_signals(self):
        self.welcome_widget.load_files_requested.connect(self.on_welcome_load_files)
        self.welcome_widget.load_files_with_mode_requested.connect(self.on_welcome_load_files)
        self.welcome_widget.load_sample_data_requested.connect(self.on_welcome_load_sample)
        self.welcome_widget.open_recent_file_requested.connect(self.on_welcome_open_recent)
        self.welcome_widget.open_recent_session_requested.connect(self.on_welcome_open_session)
        self.welcome_widget.open_help_topic_requested.connect(self.on_welcome_open_help)
        self.welcome_widget.dont_show_again_changed.connect(self.on_welcome_dont_show_again)
        self.welcome_widget.clear_sessions_requested.connect(self.on_clear_sessions)

    def on_welcome_load_files(self, data_mode: str = "processed"):
        self.control_panel.add_files(data_mode)
        if data_mode == "raw_sieve":
            self._show_status_message("Select raw sieve weighing files\u2026")
        else:
            self._show_status_message("Select processed sieve data files\u2026")

    def on_welcome_load_sample(self):
        demo_files = [self._normalize_file_key(path) for path in get_test_data_files()]
        if demo_files:
            open_paths = self._get_open_file_paths()
            missing_files = [path for path in demo_files if path not in open_paths]

            if not missing_files:
                for file_path in demo_files:
                    self._save_recent_file(file_path)
                self._update_welcome_recents()
                self._switch_to_tab(0)
                self._hide_welcome()
                self._show_status_message("Bundled demo datasets are already open")
                return

            self._start_external_load(
                missing_files,
                title="Loading Demo Data",
                subtitle=f"Opening {len(missing_files)} bundled demo dataset{'s' if len(missing_files) != 1 else ''}",
                stage_title="Loading demo data",
                context={
                    "mode": "sample",
                    "missing_files": [],
                    "skipped_count": 0,
                    "session": None,
                    "requested_label": "Bundled demo datasets",
                    "failed_files": [],
                },
            )
            return
        QMessageBox.information(
            self, "No Sample Data",
            "No built-in demo datasets were found. Use 'Add Files' to load your own data."
        )

    def on_welcome_open_recent(self, file_path: str):
        normalized_path = self._normalize_file_key(file_path)
        actual_path, _ = self._split_source_key(normalized_path)
        if not os.path.exists(actual_path):
            QMessageBox.warning(self, "File Not Found",
                                f"The file no longer exists:\n{file_path}")
            self._remove_recent_file(file_path)
            self._update_welcome_recents()
            return

        if normalized_path in self._get_open_file_paths():
            self._save_recent_file(normalized_path)
            self._update_welcome_recents()
            self._show_status_message(f"Already open: {os.path.basename(normalized_path)}")
            return

        self._start_external_load(
            [normalized_path],
            title="Opening Dataset",
            subtitle="Loading a recent file into the current workspace",
            stage_title="Opening recent file",
            context={
                "mode": "recent",
                "missing_files": [],
                "skipped_count": 0,
                "session": None,
                "requested_label": self._source_display_name(normalized_path),
                "failed_files": [],
            },
        )

    def on_welcome_open_session(self, session_data: dict):
        session = self._normalize_session_entry(session_data)
        if session is None:
            return

        valid_sources = [source for source in session.get("sources", []) if self._source_exists(source)]
        missing_sources = [source for source in session.get("sources", []) if not self._source_exists(source)]
        valid_files = [source["file_key"] for source in valid_sources]
        missing_files = [self._source_display_name(source) for source in missing_sources]

        if not valid_sources:
            QMessageBox.warning(
                self,
                "Session Unavailable",
                "None of the files in this saved session still exist.",
            )
            self._remove_recent_session(session)
            self._update_welcome_recents()
            return

        open_paths = self._get_open_file_paths()
        skipped_count = 0
        files_to_load = []

        for source in valid_sources:
            source_key = source["file_key"]
            if source_key in open_paths:
                if not source.get("mapping_state"):
                    self._save_recent_file(source_key)
                skipped_count += 1
                continue
            files_to_load.append(source)

        cleaned_session = dict(session)
        cleaned_session["files"] = valid_files
        cleaned_session["sources"] = valid_sources

        if not files_to_load:
            self._upsert_recent_session(cleaned_session)
            self._update_welcome_recents()
            if skipped_count:
                self._switch_to_tab(0)
                self._hide_welcome()
                self._show_status_message(
                    f"Session already open ({skipped_count} file{'s' if skipped_count != 1 else ''})"
                )
            if missing_files:
                missing_lines = "\n".join(os.path.basename(path) for path in missing_files[:6])
                QMessageBox.warning(self, "Session Partially Restored", "Missing files:\n" + missing_lines)
            return

        self._start_external_load(
            files_to_load,
            title="Restoring Session",
            subtitle="Loading saved datasets into the current workspace",
            stage_title="Restoring saved session",
            context={
                "mode": "session",
                "missing_files": missing_files,
                "skipped_count": skipped_count,
                "session": cleaned_session,
                "requested_label": cleaned_session.get("name", "Session"),
                "failed_files": [],
            },
        )

    def on_welcome_open_help(self, topic_file: str):
        self.open_help_dialog(topic_file)

    def is_welcome_screen_enabled(self) -> bool:
        """Return whether the welcome screen should be shown on startup."""
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        return not _effective_welcome_dont_show(settings)

    def set_welcome_screen_enabled(self, enabled: bool):
        """Persist the startup welcome-screen preference and sync UI state."""
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        _save_welcome_preference(settings, not bool(enabled))
        self._sync_welcome_preference_state()

    def ui_font_bump(self) -> int:
        """Return the active display-size preset."""
        return self._ui_font_bump

    def set_ui_font_bump(self, bump) -> bool:
        """Persist the display-size preset. Full UI refresh happens on restart."""
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        normalised = _save_ui_font_bump(settings, bump)
        changed = normalised != self._ui_font_bump
        self._ui_font_bump = normalised
        set_font_bump(normalised)
        if changed:
            self._show_status_message("Display size saved. Restart Grain Size Analysis to apply it everywhere.")
        return changed

    def on_welcome_dont_show_again(self, dont_show: bool):
        self.set_welcome_screen_enabled(not bool(dont_show))

    def on_clear_sessions(self):
        reply = QMessageBox.question(
            self, "Clear Sessions",
            "Are you sure you want to clear all saved sessions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._save_recent_sessions([])
            self._update_welcome_recents()
            self._show_status_message("All sessions cleared")

    # ──────────────────────────────────────────────────────────────────
    # RECENT FILES / SESSIONS
    # ──────────────────────────────────────────────────────────────────

    def _split_source_key(self, file_key: str) -> tuple[str, str | None]:
        if ":::" in file_key:
            return file_key.split(":::", 1)
        return file_key, None

    def _normalize_file_key(self, file_key: str) -> str:
        actual_path, sheet_name = self._split_source_key(str(file_key))
        normalized = os.path.normpath(actual_path)
        return f"{normalized}:::{sheet_name}" if sheet_name else normalized

    def _file_key_exists(self, file_key: str) -> bool:
        actual_path, _ = self._split_source_key(file_key)
        return os.path.exists(actual_path)

    def _source_file_key(self, source: object) -> str:
        if isinstance(source, Mapping):
            file_key = source.get("file_key")
            if isinstance(file_key, str) and file_key:
                return self._normalize_file_key(file_key)
            file_path = str(source.get("file_path") or "")
            sheet_name = source.get("sheet_name")
            if sheet_name:
                return self._normalize_file_key(f"{file_path}:::{sheet_name}")
            return self._normalize_file_key(file_path)
        return self._normalize_file_key(str(source))

    def _source_actual_path(self, source: object) -> str:
        file_key = self._source_file_key(source)
        actual_path, _ = self._split_source_key(file_key)
        return actual_path

    def _source_exists(self, source: object) -> bool:
        return os.path.exists(self._source_actual_path(source))

    def _normalize_session_source(self, source: object) -> Optional[dict]:
        if isinstance(source, Mapping):
            file_key = str(source.get("file_key") or "")
            file_path = str(source.get("file_path") or "")
            sheet_name = source.get("sheet_name")

            if file_key and not file_path:
                file_path, sheet_from_key = self._split_source_key(file_key)
                sheet_name = sheet_name or sheet_from_key
            if not file_path:
                return None

            normalized_file_path = os.path.normpath(file_path)
            normalized_key = self._normalize_file_key(
                f"{normalized_file_path}:::{sheet_name}" if sheet_name else normalized_file_path
            )
            mapping_state = source.get("mapping_state")
            if not isinstance(mapping_state, Mapping):
                mapping_state = None

            descriptor = {
                "file_key": normalized_key,
                "file_path": normalized_file_path,
                "sheet_name": str(sheet_name) if sheet_name else None,
            }
            for key in ("sample_name", "temperature", "porosity", "group_name", "data_type", "selection_method"):
                if source.get(key) is not None:
                    descriptor[key] = source.get(key)
            if mapping_state:
                descriptor["mapping_state"] = dict(mapping_state)
                descriptor.setdefault(
                    "data_type",
                    "raw_sieve" if mapping_state.get("raw_sieve_mode") else "calculated",
                )
                descriptor.setdefault(
                    "selection_method",
                    "column" if mapping_state.get("raw_sieve_mode") else mapping_state.get("calculated_selection_mode", "column"),
                )
            return descriptor

        if isinstance(source, str) and source.strip():
            file_key = self._normalize_file_key(source)
            file_path, sheet_name = self._split_source_key(file_key)
            return {
                "file_key": file_key,
                "file_path": file_path,
                "sheet_name": sheet_name,
            }
        return None

    def _normalize_session_sources(self, session_data: Mapping[str, Any]) -> List[dict]:
        raw_sources = session_data.get("sources", [])
        if isinstance(raw_sources, Mapping):
            raw_sources = [raw_sources]
        elif not isinstance(raw_sources, list):
            raw_sources = []

        if not raw_sources:
            raw_sources = session_data.get("files", [])
            if isinstance(raw_sources, str):
                raw_sources = [raw_sources]
            elif not isinstance(raw_sources, list):
                raw_sources = []

        sources: List[dict] = []
        seen = set()
        for raw_source in raw_sources:
            source = self._normalize_session_source(raw_source)
            if source is None:
                continue
            key = source["file_key"]
            if key in seen:
                continue
            seen.add(key)
            sources.append(source)
        return sources

    def _source_display_name(self, source: object) -> str:
        if isinstance(source, Mapping):
            sample_name = source.get("sample_name")
            if isinstance(sample_name, str) and sample_name:
                return sample_name
        file_key = self._source_file_key(source)
        actual_path, sheet_name = self._split_source_key(file_key)
        if sheet_name:
            return f"{os.path.basename(actual_path)} [{sheet_name}]"
        return os.path.basename(actual_path)

    def _load_recent_files(self) -> List[str]:
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        recent = settings.value("recent_files", [])
        if isinstance(recent, str):
            recent = [recent] if recent else []
        elif not isinstance(recent, list):
            recent = []

        cleaned: List[str] = []
        seen = set()
        changed = False
        for file_path in recent:
            if not isinstance(file_path, str) or not file_path.strip():
                changed = True
                continue
            normalized = self._normalize_file_key(file_path)
            if normalized in seen:
                changed = True
                continue
            if not self._file_key_exists(normalized):
                changed = True
                continue
            seen.add(normalized)
            cleaned.append(normalized)

        cleaned = cleaned[:10]
        if changed or cleaned != recent:
            settings.setValue("recent_files", cleaned)
        return cleaned

    def _save_recent_file(self, file_path: str):
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        recent = self._load_recent_files()
        normalized = self._normalize_file_key(file_path)
        if normalized in recent:
            recent.remove(normalized)
        recent.insert(0, normalized)
        recent = recent[:10]
        settings.setValue("recent_files", recent)

    def _normalize_session_files(self, file_paths) -> List[str]:
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        if not isinstance(file_paths, list):
            return []

        cleaned: List[str] = []
        seen = set()
        for file_path in file_paths:
            if not isinstance(file_path, str) or not file_path.strip():
                continue
            normalized = self._normalize_file_key(file_path)
            if normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(normalized)
        return cleaned

    def _normalize_session_entry(self, session_data) -> Optional[dict]:
        if not isinstance(session_data, dict):
            return None

        sources = self._normalize_session_sources(session_data)
        if not sources:
            return None
        files = [source["file_key"] for source in sources]

        timestamp = str(session_data.get("timestamp") or "")
        date = str(session_data.get("date") or "")
        if not date and "T" in timestamp:
            date = timestamp.split("T", 1)[0]

        sample_names = session_data.get("samples", [])
        if isinstance(sample_names, str):
            sample_names = [sample_names]
        elif not isinstance(sample_names, list):
            sample_names = []

        cleaned_samples = []
        seen_samples = set()
        for sample_name in sample_names:
            if not isinstance(sample_name, str):
                continue
            sample_name = sample_name.strip()
            if not sample_name or sample_name in seen_samples:
                continue
            seen_samples.add(sample_name)
            cleaned_samples.append(sample_name)

        name = str(session_data.get("name") or "").strip()
        if not name:
            name = f"Session {timestamp[:16].replace('T', ' ')}" if timestamp else "Session"

        return {
            "name": name,
            "date": date,
            "files": files,
            "timestamp": timestamp,
            "samples": cleaned_samples,
            "sources": sources,
        }

    def _session_match_key(self, session_data: dict) -> tuple[str, ...]:
        sources = session_data.get("sources")
        if sources:
            return tuple(sorted(self._source_file_key(source) for source in sources))
        return tuple(sorted(self._normalize_session_files(session_data.get("files", []))))

    def _load_recent_sessions(self) -> List[dict]:
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        raw_sessions = settings.value("recent_sessions", [])
        if isinstance(raw_sessions, dict):
            raw_sessions = [raw_sessions]
        elif not isinstance(raw_sessions, list):
            raw_sessions = []

        cleaned_sessions: List[dict] = []
        seen_keys = set()
        changed = False

        for raw_session in raw_sessions:
            session = self._normalize_session_entry(raw_session)
            if session is None:
                changed = True
                continue

            existing_sources = [source for source in session.get("sources", []) if self._source_exists(source)]
            existing_files = [source["file_key"] for source in existing_sources]
            if existing_files != session["files"]:
                changed = True
                session["files"] = existing_files
                session["sources"] = existing_sources
            if not session["files"]:
                changed = True
                continue

            key = self._session_match_key(session)
            if key in seen_keys:
                changed = True
                continue
            seen_keys.add(key)
            cleaned_sessions.append(session)

        cleaned_sessions = cleaned_sessions[:10]
        if changed or cleaned_sessions != raw_sessions:
            settings.setValue("recent_sessions", cleaned_sessions)
        return cleaned_sessions

    def _save_recent_sessions(self, sessions: List[dict]):
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        settings.setValue("recent_sessions", sessions[:10])

    def _build_dataset_source_descriptor(self, dataset: GrainSizeData) -> Optional[dict]:
        file_path = getattr(dataset, "file_path", "")
        if not file_path:
            return None

        file_key = self._normalize_file_key(file_path)
        actual_path, sheet_name = self._split_source_key(file_key)
        mapping_state = getattr(dataset, "_source_mapping_state", None)
        if not mapping_state:
            mapping_state = self.control_panel.file_mapping_states.get(file_key)

        descriptor = {
            "file_key": file_key,
            "file_path": actual_path,
            "sheet_name": sheet_name,
            "sample_name": getattr(dataset, "sample_name", ""),
            "temperature": getattr(dataset, "temperature", None),
            "porosity": getattr(dataset, "porosity", None),
            "group_name": getattr(dataset, "group_name", "Ungrouped"),
        }
        if mapping_state:
            descriptor["mapping_state"] = dict(mapping_state)
            descriptor["data_type"] = "raw_sieve" if mapping_state.get("raw_sieve_mode") else "calculated"
            descriptor["selection_method"] = (
                "column"
                if mapping_state.get("raw_sieve_mode")
                else mapping_state.get("calculated_selection_mode", "column")
            )
        provenance = getattr(dataset, "_source_import_provenance", None)
        if provenance:
            descriptor["import_provenance"] = dict(provenance)
        return descriptor

    def _build_current_session(self) -> Optional[dict]:
        if not self.dataset_tabs:
            return None

        current_files: List[str] = []
        current_sources: List[dict] = []
        sample_names: List[str] = []
        seen_files = set()
        seen_samples = set()
        for tab in self.dataset_tabs:
            dataset = tab.get_dataset()
            source = self._build_dataset_source_descriptor(dataset)
            if source:
                normalized = source["file_key"]
                if normalized not in seen_files:
                    seen_files.add(normalized)
                    current_files.append(normalized)
                    current_sources.append(source)

            sample_name = getattr(dataset, "sample_name", "")
            if sample_name and sample_name not in seen_samples:
                seen_samples.add(sample_name)
                sample_names.append(sample_name)

        if not current_files:
            return None

        from datetime import datetime

        now = datetime.now()
        return {
            "name": f"Session {now.strftime('%Y-%m-%d %H:%M')}",
            "date": now.strftime('%Y-%m-%d'),
            "files": current_files,
            "timestamp": now.isoformat(),
            "samples": sample_names,
            "sources": current_sources,
        }

    def _upsert_recent_session(self, session: dict):
        normalized = self._normalize_session_entry(session)
        if normalized is None:
            return

        key = self._session_match_key(normalized)
        sessions = [
            existing
            for existing in self._load_recent_sessions()
            if self._session_match_key(existing) != key
        ]
        sessions.insert(0, normalized)
        self._save_recent_sessions(sessions)

    def _remove_recent_session(self, session: dict):
        key = self._session_match_key(session)
        sessions = [
            existing
            for existing in self._load_recent_sessions()
            if self._session_match_key(existing) != key
        ]
        self._save_recent_sessions(sessions)

    def _save_current_session(self):
        session = self._build_current_session()
        if session is None:
            return
        self._upsert_recent_session(session)
        self._update_welcome_recents()

    def _remove_recent_file(self, file_path: str):
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        recent = self._load_recent_files()
        normalized = self._normalize_file_key(file_path)
        if normalized in recent:
            recent.remove(normalized)
            settings.setValue("recent_files", recent)

    def _get_open_file_paths(self) -> set[str]:
        open_paths = set()
        for tab in self.dataset_tabs:
            dataset = tab.get_dataset()
            file_path = getattr(dataset, "file_path", "")
            if file_path:
                open_paths.add(self._normalize_file_key(file_path))
        return open_paths

    def _start_external_load(
        self,
        file_paths: List[str],
        *,
        title: str,
        subtitle: str,
        stage_title: str,
        context: dict,
    ):
        if not file_paths:
            return
        if self._external_load_process is not None:
            if self._external_load_dialog is not None:
                self._external_load_dialog.raise_()
                self._external_load_dialog.activateWindow()
            return

        self._external_load_context = dict(context)
        self._external_load_dialog = LoadingDialog(
            title,
            subtitle,
            parent=self,
            cancellable=False,
        )
        progress_total = max(1, len(file_paths) * 2)
        self._external_load_dialog.update_progress(
            0,
            progress_total,
            "Preparing files",
            "Starting the background loader and checking the selected paths.",
            count_label=f"0 of {len(file_paths)} items",
            activity_label="Starting the background loader.",
        )
        self._external_load_dialog.set_activity(
            "Recent files are being reopened in the background. This window will close automatically when loading is complete."
        )
        self._external_load_dialog.open()
        self._begin_bulk_dataset_add()

        ctx = mp.get_context("spawn")
        self._external_load_finished_received = False
        self._external_load_finalize_summary = None
        self._pending_external_ui_events.clear()
        self._external_ui_total = 0
        self._external_ui_processed = 0
        self._external_load_queue = ctx.Queue()
        self._external_load_process = ctx.Process(
            target=run_external_load,
            kwargs={
                "file_paths": file_paths,
                "stage_title": stage_title,
                "result_queue": self._external_load_queue,
                "temperature": self.control_panel.temp_spinbox.value(),
            },
            daemon=True,
        )
        self._external_load_process.start()
        self._external_load_poll_timer.start()

    def _poll_external_load_process(self):
        if self._external_load_queue is None:
            return

        for _ in range(32):
            try:
                event = self._external_load_queue.get_nowait()
            except queue.Empty:
                break

            kind = event[0]
            payload = event[1:]

            if kind == "progress":
                self._on_external_load_progress(*payload)
            elif kind == "log_event":
                self.record_log_event(payload[0])
            elif kind == "file_loaded":
                self._external_ui_total += 1
                self._pending_external_ui_events.append((self._on_external_load_file_loaded, payload))
            elif kind == "file_failed":
                self._external_ui_total += 1
                self._pending_external_ui_events.append((self._on_external_load_file_failed, payload))
            elif kind == "finished":
                self._external_load_finished_received = True
                self._external_load_finalize_summary = payload[0]
                if self._external_load_dialog is not None and self._pending_external_ui_events:
                    self._external_load_dialog.set_activity(
                        "Integrating loaded datasets into the workspace."
                    )
                    self._update_external_integration_progress()
            elif kind == "process_error":
                self._external_load_finished_received = True
                self._external_load_finalize_summary = (
                    {
                        "total": 0,
                        "loaded": 0,
                        "failed": 1,
                        "canceled": False,
                    }
                )
                if self._external_load_dialog is not None:
                    self._external_load_dialog.set_activity(payload[0])

        if self._pending_external_ui_events and not self._external_load_ui_timer.isActive():
            self._external_load_ui_timer.start()

        self._finalize_external_load_if_ready()

    def _process_external_load_ui_slice(self):
        if not self._pending_external_ui_events:
            self._external_load_ui_timer.stop()
            self._finalize_external_load_if_ready()
            return

        handler, payload = self._pending_external_ui_events.popleft()
        handler(*payload)
        self._external_ui_processed += 1
        if self._external_load_finished_received:
            self._update_external_integration_progress()

        if not self._pending_external_ui_events:
            self._external_load_ui_timer.stop()
            self._finalize_external_load_if_ready()

    def _finalize_external_load_if_ready(self):
        if self._pending_external_ui_events:
            return

        if self._external_load_finalize_summary is not None:
            summary = self._external_load_finalize_summary
            self._external_load_finalize_summary = None
            self._on_external_load_finished(summary)

        if (
            self._external_load_finished_received
            and self._external_load_process is not None
            and not self._external_load_process.is_alive()
        ):
            self._cleanup_external_load_process()

    def _on_external_load_progress(self, current: int, total: int, stage: str, detail: str):
        if self._external_load_dialog is not None:
            overall_total = max(1, total * 2)
            self._external_load_dialog.update_progress(
                current,
                overall_total,
                stage,
                detail,
                count_label=f"{current} of {total} items",
                activity_label=f"Processing item {current} of {total}.",
            )

    def _update_external_integration_progress(self) -> None:
        if self._external_load_dialog is None or self._external_ui_total <= 0:
            return

        current = max(0, min(self._external_ui_processed, self._external_ui_total))
        overall_total = max(1, self._external_ui_total * 2)
        activity = (
            "Preparing workspace integration."
            if current <= 0
            else f"Integrating item {current} of {self._external_ui_total}."
        )
        self._external_load_dialog.update_progress(
            self._external_ui_total + current,
            overall_total,
            "Integrating workspace",
            "Adding loaded items to the workspace.",
            count_label=f"{self._external_ui_total} items processed",
            activity_label=activity,
        )

    def _on_external_load_file_loaded(self, file_path: str, dataset):
        dataset.file_path = file_path
        mapping_state = getattr(dataset, "_source_mapping_state", None)
        if mapping_state:
            self.control_panel.file_mapping_states[file_path] = mapping_state
        self.add_dataset_tab(dataset)
        self.control_panel.register_external_file(file_path, dataset)
        if not mapping_state:
            self._save_recent_file(file_path)

    def _on_external_load_file_failed(self, file_path: str, detail: str):
        self.control_panel.register_external_issue(file_path, detail, status="review")
        self.update_error_tab_message(file_path, detail)

        if self._external_load_context is None:
            return

        self._external_load_context.setdefault("failed_files", []).append(
            f"{os.path.basename(file_path)}: {detail}"
        )

    def _on_external_load_finished(self, summary: dict):
        self._end_bulk_dataset_add()
        context = self._external_load_context or {}
        mode = context.get("mode", "recent")
        loaded = summary.get("loaded", 0)
        canceled = summary.get("canceled", False)
        failed_files = context.get("failed_files", [])
        missing_files = context.get("missing_files", [])
        skipped_count = context.get("skipped_count", 0)

        if mode == "session":
            session = context.get("session")
            if session:
                self._upsert_recent_session(session)

        self._update_welcome_recents()

        if loaded or skipped_count:
            self._switch_to_tab(0)
            self._hide_welcome()

        if mode == "session":
            details = []
            if missing_files:
                details.append(f"{len(missing_files)} missing")
            if skipped_count:
                details.append(f"{skipped_count} already open")
            if failed_files:
                details.append(f"{len(failed_files)} failed")
            headline = "Session restored" if not failed_files and not missing_files else "Session restore complete"
            detail = f"{loaded} loaded"
            if details:
                detail = f"{detail} ({', '.join(details)})"
            ok = not failed_files and not missing_files and not canceled
            status = f"Resumed session: {detail}"
        else:
            requested_label = context.get("requested_label", "dataset")
            headline = "Dataset opened" if not failed_files and not canceled else "Open complete"
            detail = f"{loaded} loaded"
            ok = not failed_files and not canceled
            status = f"Opened: {requested_label}" if ok else f"Open complete: {detail}"

        self._show_status_message(status, ok=ok)

        if self._external_load_dialog is not None:
            dialog = self._external_load_dialog
            dialog.mark_finished(headline, detail, ok=ok)
            QTimer.singleShot(420, lambda d=dialog: self._dismiss_external_load_dialog(d))

        if missing_files or failed_files:
            missing_lines = "\n".join(os.path.basename(path) for path in missing_files[:6])
            failed_lines = "\n".join(failed_files[:6])
            parts = []
            if missing_files:
                parts.append("Missing files:\n" + missing_lines)
            if failed_files:
                parts.append("Failed to load:\n" + failed_lines)
            QMessageBox.warning(self, "Load Completed With Issues", "\n\n".join(parts))

    def _cleanup_external_load_process(self):
        self._external_load_poll_timer.stop()
        self._external_load_ui_timer.stop()

        if self._external_load_process is not None:
            self._external_load_process.join(timeout=0.1)
            if self._external_load_process.is_alive():
                self._external_load_process.terminate()
                self._external_load_process.join(timeout=0.1)

        if self._external_load_queue is not None:
            self._external_load_queue.close()
            self._external_load_queue = None

        self._external_load_process = None
        self._external_load_finished_received = False
        self._external_load_finalize_summary = None
        self._pending_external_ui_events.clear()
        self._external_ui_total = 0
        self._external_ui_processed = 0
        self._external_load_context = None

    def _dismiss_external_load_dialog(self, dialog):
        if dialog is not None:
            dialog.accept()
            dialog.deleteLater()
        if self._external_load_dialog is dialog:
            self._external_load_dialog = None

    def _update_welcome_recents(self):
        self._refresh_welcome_widget(preserve_visibility=True)

    def _sync_welcome_preference_state(self):
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        dont_show = _effective_welcome_dont_show(settings)
        checkbox = getattr(self.welcome_widget, "dont_show_checkbox", None)
        if checkbox is not None:
            checkbox.blockSignals(True)
            checkbox.setChecked(dont_show)
            checkbox.blockSignals(False)

    def _refresh_welcome_widget(self, preserve_visibility: bool = True):
        current_index = self._samples_stack.currentIndex()
        if preserve_visibility and self.dataset_tabs:
            # Keep the dataset workspace visible even if a fade-to-tabs request is
            # still in flight when the welcome widget gets rebuilt.
            current_index = 1
        sidebar_visible = self.control_panel.isVisible()
        recent_files = self._load_recent_files()
        recent_sessions = self._load_recent_sessions()
        old_widget = self.welcome_widget
        self._samples_stack.removeWidget(self.welcome_widget)
        self.welcome_widget = WelcomeWidget(
            recent_files=recent_files,
            recent_sessions=recent_sessions,
        )
        self._connect_welcome_signals()
        self._samples_stack.insertWidget(0, self.welcome_widget)
        self._sync_welcome_preference_state()
        if preserve_visibility:
            self._samples_stack.setCurrentIndex(current_index)
            self.control_panel.setVisible(sidebar_visible)
        else:
            self._show_welcome()
        self._refresh_dataset_tab_icons()
        old_widget.deleteLater()

    # ──────────────────────────────────────────────────────────────────
    # DATASET MANAGEMENT
    # ──────────────────────────────────────────────────────────────────

    def _get_selected_dataset_tabs(self) -> List[DatasetTab]:
        """Return dataset tabs included by sidebar scope, or all tabs if no scope exists."""
        selected_paths = self.control_panel.get_selected_paths()
        if not selected_paths:
            card_count = (
                self.control_panel.get_scope_card_count()
                if hasattr(self.control_panel, "get_scope_card_count")
                else 0
            )
            if card_count:
                return []
            return self.dataset_tabs
        path_set = set(selected_paths)
        filtered = [t for t in self.dataset_tabs
                    if hasattr(t, 'dataset') and hasattr(t.dataset, 'file_path')
                    and t.dataset.file_path in path_set]
        return filtered if filtered else self.dataset_tabs

    def _dataset_paths_for_tabs(self, dataset_tabs) -> list[str]:
        """Return sidebar file-path keys for dataset tabs."""
        paths: list[str] = []
        for tab in dataset_tabs:
            dataset = tab.get_dataset() if hasattr(tab, "get_dataset") else getattr(tab, "dataset", None)
            file_path = getattr(dataset, "file_path", "") if dataset is not None else ""
            if file_path:
                paths.append(file_path)
        return paths

    def _refresh_sidebar_group_labels(self) -> None:
        """Refresh sample-card group labels from the current dataset objects."""
        if not hasattr(self.control_panel, "update_sample_group"):
            return
        for tab in self.dataset_tabs:
            dataset = tab.get_dataset() if hasattr(tab, "get_dataset") else getattr(tab, "dataset", None)
            if dataset is None:
                continue
            file_path = getattr(dataset, "file_path", "")
            if file_path:
                self.control_panel.update_sample_group(
                    file_path,
                    getattr(dataset, "group_name", "Ungrouped"),
                )

    def _apply_group_assignments(self, group_assignments: Mapping[object, str]) -> None:
        """Apply group labels to dataset objects and sidebar cards."""
        for tab, group_name in group_assignments.items():
            try:
                dataset = tab.get_dataset()
            except Exception:
                dataset = getattr(tab, "dataset", None)
            if dataset is None:
                continue
            try:
                dataset.group_name = group_name
            except Exception:
                pass
        self._refresh_sidebar_group_labels()

    def _sync_scope_outputs(self) -> None:
        """Push current loaded/selected/group state into comparison, reports, and export."""
        self._sync_comparison_dataset_state()
        if hasattr(self, "reporting_tab"):
            self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
        if hasattr(self, "export_tab"):
            self._update_export_tab()

    def _open_dataset_group_manager(self) -> None:
        """Open the shared sidebar Dataset & Group Manager."""
        if not self.dataset_tabs:
            self._show_status_message("Load datasets before managing scope and groups", ok=False)
            return
        now = time.monotonic()
        if (
            self._dataset_group_manager_active
            or now - self._dataset_group_manager_last_closed_at < 0.35
        ):
            return

        self._dataset_group_manager_active = True
        try:
            selected_tabs = self._get_selected_dataset_tabs()
            dialog = DatasetSelectionDialog(
                self.dataset_tabs,
                currently_selected=selected_tabs,
                title="Dataset & Group Manager",
                subtitle="Choose included samples, assign groups, and apply the shared workspace scope",
                action_text="Apply",
                action_icon="fa6s.check",
                minimum_selection=1,
                allow_grouping=True,
                parent=self,
            )
            if not dialog.exec():
                return

            self._apply_group_assignments(dialog.get_group_assignments())
            selected_tabs = dialog.get_selected_tabs()
            selected_paths = self._dataset_paths_for_tabs(selected_tabs)
            self.control_panel.set_selected_paths(selected_paths, emit_signal=False)
            self._sync_scope_outputs()
            self._show_status_message(f"Dataset scope updated: {len(selected_tabs)} included")
        finally:
            self._dataset_group_manager_active = False
            self._dataset_group_manager_last_closed_at = time.monotonic()

    def _sync_comparison_dataset_state(self) -> None:
        """Keep comparison loaded/selected dataset state aligned with the sidebar."""
        self.comparison_tab.set_dataset_state(
            self.dataset_tabs,
            selected_tabs=self._get_selected_dataset_tabs(),
        )

    def _on_sidebar_selection_changed(self):
        """Push the current selected-tab subset to the comparison tab."""
        self._sync_scope_outputs()

    def _on_comparison_selection_requested(self, file_paths: list[str]) -> None:
        """Apply comparison-dialog selections back onto the sidebar cards."""
        self._refresh_sidebar_group_labels()
        self.control_panel.set_selected_paths(file_paths, emit_signal=False)
        self._sync_scope_outputs()

    def _on_export_selection_requested(self, file_paths: list[str]) -> None:
        """Apply export-dialog selections back onto the sidebar cards."""
        self._refresh_sidebar_group_labels()
        self.control_panel.set_selected_paths(file_paths, emit_signal=False)
        self._sync_scope_outputs()

    def _on_scheme_changed(self, scheme):
        """Propagate a new classification scheme to all open dataset tabs and output tabs."""
        self.active_scheme = scheme
        for tab in self.dataset_tabs:
            if hasattr(tab, 'set_scheme'):
                tab.set_scheme(scheme)
        if hasattr(self, 'comparison_tab'):
            self.comparison_tab.set_scheme(scheme)
        self.export_tab.set_scheme(scheme)
        if hasattr(self, 'reporting_tab'):
            self.reporting_tab.set_scheme(scheme)

    def _begin_bulk_dataset_add(self) -> None:
        self._bulk_dataset_add_depth += 1
        if self._bulk_dataset_add_depth != 1:
            return
        self._bulk_dataset_add_dirty = False
        self._bulk_dataset_add_last_index = None
        self._bulk_dataset_add_last_label = ""
        if hasattr(self, "dataset_tabs_widget"):
            self.dataset_tabs_widget.setUpdatesEnabled(False)

    def _end_bulk_dataset_add(self) -> None:
        if self._bulk_dataset_add_depth == 0:
            return
        self._bulk_dataset_add_depth -= 1
        if self._bulk_dataset_add_depth != 0:
            return

        if hasattr(self, "dataset_tabs_widget"):
            self.dataset_tabs_widget.setUpdatesEnabled(True)

        if not self._bulk_dataset_add_dirty:
            return

        if (
            self._bulk_dataset_add_last_index is not None
            and 0 <= self._bulk_dataset_add_last_index < self.dataset_tabs_widget.count()
        ):
            self.dataset_tabs_widget.setCurrentIndex(self._bulk_dataset_add_last_index)

        self._refresh_dataset_tab_icons()
        self._sync_comparison_dataset_state()
        self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
        self._update_export_tab()
        self._refresh_dataset_status_segments(self._bulk_dataset_add_last_label)
        self.dataset_tabs_widget.update()
        self._bulk_dataset_add_dirty = False
        self._bulk_dataset_add_last_index = None
        self._bulk_dataset_add_last_label = ""

    def _refresh_dataset_status_segments(self, sample_name: str | None = None) -> None:
        n = len(self.dataset_tabs)
        temp = self.control_panel.temp_spinbox.value()
        sample_label = sample_name or (self.dataset_tabs[-1].get_dataset_name() if self.dataset_tabs else "—")

        self.rich_status_bar.set_segment("DATASETS", str(n) if n else "—")
        self.rich_status_bar.set_segment("SAMPLE", sample_label[:24] if sample_label else "—")
        self.rich_status_bar.set_segment("TEMP", f"{temp}°C")
        self.rich_status_bar.set_segment(
            "METHODS",
            f"{len(self.active_method_names)} / {len(self.available_method_names)}",
        )
        self.app_toolbar.set_badge(0, n)

    def add_dataset_tab(self, dataset: GrainSizeData):
        bulk_mode = self._bulk_dataset_add_depth > 0
        self.dataset_counter += 1
        self._hide_welcome()
        dataset_tab = DatasetTab(dataset)
        dataset_tab.set_active_methods(self.active_method_names, refresh=False)

        temperature = self.control_panel.temp_spinbox.value()
        dataset_tab.set_parameters(temperature)
        dataset_tab.calculation_complete.connect(self._on_calculation_complete)
        dataset_tab.data_updated.connect(self._on_dataset_data_updated)

        tab_label = dataset.sample_name
        tab_index = self.dataset_tabs_widget.addTab(dataset_tab, tab_label)
        self.dataset_tabs_widget.setTabToolTip(tab_index, dataset.sample_name)
        self.dataset_tabs.append(dataset_tab)
        if bulk_mode:
            self._bulk_dataset_add_dirty = True
            self._bulk_dataset_add_last_index = tab_index
            self._bulk_dataset_add_last_label = dataset.sample_name
        else:
            self.dataset_tabs_widget.setCurrentIndex(self.dataset_tabs_widget.count() - 1)
            self._refresh_dataset_tab_icons()
            self._sync_comparison_dataset_state()
            self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
            self._update_export_tab()

        if hasattr(dataset, 'file_path') and dataset.file_path:
            self._save_recent_file(dataset.file_path)

        precomputed_results = getattr(dataset, "_precomputed_k_results", None)
        precomputed_temperature = getattr(dataset, "_precomputed_k_temperature", None)
        precomputed_porosity = getattr(dataset, "_precomputed_k_porosity", None)
        if (
            precomputed_results is not None
            and precomputed_temperature == dataset_tab.temperature
            and precomputed_porosity == dataset_tab.porosity
        ):
            dataset_tab.apply_precomputed_results(precomputed_results)
        else:
            dataset_tab.calculate_k_values(self.active_method_names)

        if not bulk_mode:
            self._refresh_dataset_status_segments(dataset.sample_name)
            self._show_status_message(f"Loaded: {dataset.sample_name}")

    def add_error_tab(self, file_path: str, error_message: str):
        bulk_mode = self._bulk_dataset_add_depth > 0
        self._hide_welcome()
        error_tab = ErrorTab(file_path, error_message, self)
        error_tab.dataset_fixed.connect(self.on_dataset_fixed)
        file_name = os.path.basename(file_path)
        index = self.dataset_tabs_widget.addTab(error_tab, file_name)
        self.dataset_tabs_widget.setTabToolTip(index, file_name)
        self.dataset_tabs_widget.tabBar().setTabTextColor(index, QColor(211, 47, 47))
        if bulk_mode:
            self._bulk_dataset_add_dirty = True
            self._bulk_dataset_add_last_index = index
            self._bulk_dataset_add_last_label = file_name
        else:
            self.dataset_tabs_widget.setCurrentIndex(index)
            self._refresh_dataset_tab_icons()
            self._show_status_message(f"Error loading: {file_name} \u2014 click tab to fix", ok=False)

    def add_mapping_required_tab(self, file_path: str, message: str):
        bulk_mode = self._bulk_dataset_add_depth > 0
        self._hide_welcome()
        mapping_tab = ErrorTab(file_path, message, self, issue_variant="mapping_required")
        mapping_tab.dataset_fixed.connect(self.on_dataset_fixed)
        file_name = os.path.basename(file_path)
        index = self.dataset_tabs_widget.addTab(mapping_tab, file_name)
        self.dataset_tabs_widget.setTabToolTip(index, file_name)
        self.dataset_tabs_widget.tabBar().setTabTextColor(index, QColor(C.OLIVE_DK))
        if bulk_mode:
            self._bulk_dataset_add_dirty = True
            self._bulk_dataset_add_last_index = index
            self._bulk_dataset_add_last_label = file_name
        else:
            self.dataset_tabs_widget.setCurrentIndex(index)
            self._refresh_dataset_tab_icons()
            self._show_status_message(f"Mapping required: {file_name}")

    def _remove_error_tab(self, file_path: str) -> bool:
        for i in range(self.dataset_tabs_widget.count()):
            widget = self.dataset_tabs_widget.widget(i)
            if isinstance(widget, ErrorTab) and widget.file_path == file_path:
                self.dataset_tabs_widget.removeTab(i)
                return True
        return False

    def _remove_tabs_for_file(self, file_path: str) -> int:
        """Remove stale error/dataset tabs for a file before adding corrected data."""
        removed = 0
        for i in range(self.dataset_tabs_widget.count() - 1, -1, -1):
            widget = self.dataset_tabs_widget.widget(i)
            tab_file_path = getattr(widget, "file_path", None)
            dataset = getattr(widget, "dataset", None)
            if dataset is not None:
                tab_file_path = getattr(dataset, "file_path", tab_file_path)

            if tab_file_path != file_path:
                continue

            if widget in self.dataset_tabs:
                self.dataset_tabs.remove(widget)
            self.dataset_tabs_widget.removeTab(i)
            if hasattr(widget, "deleteLater"):
                widget.deleteLater()
            removed += 1

        if removed:
            self._refresh_dataset_tab_icons()
            self._sync_comparison_dataset_state()
            self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
            self._update_export_tab()
            self._refresh_dataset_status_segments()
            if self.dataset_tabs_widget.count() == 0:
                self._show_welcome()

        return removed

    def _tab_file_path(self, widget) -> str | None:
        tab_file_path = getattr(widget, "file_path", None)
        dataset = getattr(widget, "dataset", None)
        if dataset is not None:
            tab_file_path = getattr(dataset, "file_path", tab_file_path)
        return tab_file_path

    def _has_open_tabs_for_file(self, file_path: str) -> bool:
        if not file_path:
            return False
        for i in range(self.dataset_tabs_widget.count()):
            widget = self.dataset_tabs_widget.widget(i)
            if self._tab_file_path(widget) == file_path:
                return True
        return False

    def remove_workspace_file(self, file_path: str) -> bool:
        removed_tabs = self._remove_tabs_for_file(file_path)
        removed_sidebar = self.control_panel.remove_file_by_path(
            file_path,
            sync_workspace=False,
            announce=False,
        )
        if removed_tabs or removed_sidebar:
            file_name = self.control_panel._format_file_display_name(file_path)
            self._show_status_message(f"Removed: {file_name}")
        return bool(removed_tabs or removed_sidebar)

    def _ensure_dataset_list(self, dataset_input) -> List[GrainSizeData]:
        if isinstance(dataset_input, list):
            return dataset_input
        return [dataset_input]

    def on_dataset_fixed(self, dataset_input, original_file_path: str):
        datasets = self._ensure_dataset_list(dataset_input)
        self._remove_tabs_for_file(original_file_path)
        bulk = len(datasets) > 1
        if bulk:
            self._begin_bulk_dataset_add()
        try:
            for dataset in datasets:
                self.add_dataset_tab(dataset)
        finally:
            if bulk:
                self._end_bulk_dataset_add()
        name = datasets[0].sample_name if len(datasets) == 1 else f"{len(datasets)} datasets"
        self._show_status_message(f"Fixed and loaded: {name}")

    def replace_error_tab_with_dataset(self, dataset_input, file_path: str):
        datasets = self._ensure_dataset_list(dataset_input)
        self._remove_tabs_for_file(file_path)
        bulk = len(datasets) > 1
        if bulk:
            self._begin_bulk_dataset_add()
        try:
            for dataset in datasets:
                self.add_dataset_tab(dataset)
        finally:
            if bulk:
                self._end_bulk_dataset_add()

    def update_error_tab_message(self, file_path: str, error_message: str):
        for i in range(self.dataset_tabs_widget.count()):
            widget = self.dataset_tabs_widget.widget(i)
            if isinstance(widget, ErrorTab) and widget.file_path == file_path:
                widget.update_error_message(error_message)
                widget.load_file_preview()
                file_name = os.path.basename(file_path)
                self.dataset_tabs_widget.setTabText(i, file_name)
                self.dataset_tabs_widget.setTabToolTip(i, file_name)
                self.dataset_tabs_widget.tabBar().setTabTextColor(i, QColor(211, 47, 47))
                self._refresh_dataset_tab_icons()
                return

        self.add_error_tab(file_path, error_message)

    def close_dataset_tab(self, index: int):
        widget = self.dataset_tabs_widget.widget(index)
        file_path = self._tab_file_path(widget)

        if widget in self.dataset_tabs:
            self.dataset_tabs.remove(widget)

        self.dataset_tabs_widget.removeTab(index)
        self._refresh_dataset_tab_icons()

        if self.dataset_tabs_widget.count() == 0:
            self._show_welcome()

        self._sync_comparison_dataset_state()
        self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
        self._update_export_tab()
        self._refresh_dataset_status_segments()
        if file_path and not self._has_open_tabs_for_file(file_path):
            self.control_panel.remove_file_by_path(
                file_path,
                sync_workspace=False,
                announce=False,
            )
        self._show_status_message("Dataset closed")

    # ──────────────────────────────────────────────────────────────────
    # CALCULATIONS
    # ──────────────────────────────────────────────────────────────────

    def choose_k_methods(self):
        """Open the workspace K-method selector."""
        dialog = MethodSelectionDialog(
            selected_methods=self.active_method_names,
            available_methods=self.available_method_names,
            parent=self,
        )
        if dialog.exec():
            self.set_active_k_methods(dialog.selected_methods())

    def set_active_k_methods(self, method_names) -> None:
        """Apply a workspace-wide K-method filter to all result surfaces."""
        next_methods = normalize_method_selection(
            method_names,
            available_methods=self.available_method_names,
        )
        if next_methods == self.active_method_names:
            return

        self.active_method_names = next_methods
        self._suppress_calculation_refresh_depth += 1
        try:
            for dataset_tab in self.dataset_tabs:
                dataset_tab.set_active_methods(self.active_method_names)
        finally:
            self._suppress_calculation_refresh_depth = max(
                0, self._suppress_calculation_refresh_depth - 1
            )

        if len(self.dataset_tabs) >= 2:
            self.comparison_tab.update_comparison()
        self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
        self._update_export_tab()
        self._refresh_dataset_status_segments()
        self._show_status_message(
            f"Active K methods: {len(self.active_method_names)} / {len(self.available_method_names)}"
        )

    def calculate_all_k_values(self):
        if not self.dataset_tabs:
            QMessageBox.information(self, "No Data", "Please load datasets first.")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.dataset_tabs))
        self.progress_bar.setValue(0)

        try:
            temperature = self.control_panel.temp_spinbox.value()
            for i, dataset_tab in enumerate(self.dataset_tabs):
                dataset_tab.set_parameters(temperature)
                dataset_tab.calculate_k_values(self.active_method_names)
                self.progress_bar.setValue(i + 1)

            self._show_status_message(
                f"K values recalculated for {len(self.dataset_tabs)} dataset(s)"
            )
            if self.content_stack.currentIndex() == 1:
                self.comparison_tab.update_comparison()

        except Exception as e:
            QMessageBox.critical(self, "Calculation Error",
                                 f"Error during calculations:\n{str(e)}")
            self._show_status_message("Calculation error", ok=False)
        finally:
            self.progress_bar.setVisible(False)

    def update_comparison(self):
        if len(self.dataset_tabs) < 2:
            QMessageBox.information(self, "Insufficient Data",
                                    "Load at least 2 datasets to compare.")
            return
        self._switch_to_tab(1)
        self.comparison_tab.update_comparison()

    # ──────────────────────────────────────────────────────────────────
    # EXPORT
    # ──────────────────────────────────────────────────────────────────

    def _current_dataset_tab(self):
        """Return the selected dataset tab, ignoring error/review tabs."""
        widget = None
        if hasattr(self.dataset_tabs_widget, "currentWidget"):
            widget = self.dataset_tabs_widget.currentWidget()
        elif hasattr(self.dataset_tabs_widget, "currentIndex"):
            index = self.dataset_tabs_widget.currentIndex()
            if index is not None and index >= 0:
                widget = self.dataset_tabs_widget.widget(index)

        if widget in self.dataset_tabs or isinstance(widget, DatasetTab):
            return widget
        return None

    def export_current(self):
        current = self.content_stack.currentIndex()
        if current == 0:
            dataset_tab = self._current_dataset_tab()
            if dataset_tab is not None:
                try:
                    dataset_tab.export_results()
                except Exception:
                    dataset_tab.plot_workspace.export_plot("png")
        else:
            self.comparison_tab.export_comparison()

    def export_results(self):
        current = self.content_stack.currentIndex()
        if current == 0:
            dataset_tab = self._current_dataset_tab()
            if dataset_tab is not None:
                dataset_tab.export_results()
        else:
            self.comparison_tab.export_comparison()

    def export_plot(self):
        current = self.content_stack.currentIndex()
        if current == 0:
            dataset_tab = self._current_dataset_tab()
            if dataset_tab is not None:
                dataset_tab.plot_workspace.export_plot("png")
        else:
            self.comparison_tab.export_comparison()

    # ──────────────────────────────────────────────────────────────────
    # DIALOGS
    # ──────────────────────────────────────────────────────────────────

    def show_help(self):
        self.open_help_dialog()

    def show_startup_guide(self):
        """Open the guided startup tour proof of concept."""
        self._start_tour_overlay(
            self._global_tour_steps(),
            reveal_sidebar=True,
            show_startup_checkbox=True,
        )

    def _start_tour_overlay(
        self,
        steps: list[TourStep],
        *,
        reveal_sidebar: bool = False,
        show_startup_checkbox: bool = True,
    ) -> None:
        """Open a guided tour overlay with consistent cleanup."""
        if self._log_overlay is not None and self._log_overlay.isVisible():
            self._log_overlay.hide()
            self.app_toolbar.set_log_active(False)

        if reveal_sidebar and hasattr(self, "control_panel") and not self.control_panel.isVisible():
            self.control_panel.setVisible(True)

        if self._startup_tour is not None:
            self._startup_tour.hide()
            self._startup_tour.deleteLater()

        self._startup_tour = StartupTourOverlay(
            self,
            steps,
            show_startup_checkbox=show_startup_checkbox,
        )
        self._startup_tour.finished.connect(self._on_startup_tour_finished)
        self._startup_tour.start()

    def _on_startup_tour_finished(self, _dont_show_on_startup: bool = False) -> None:
        tour = self._startup_tour
        self._startup_tour = None
        if tour is not None:
            tour.deleteLater()

    def _global_tour_steps(self) -> list[TourStep]:
        """Return the shell-level tour used by the startup guide overlay."""
        return [
            TourStep(
                title="Start in the sidebar",
                body=(
                    "Use the import box in the main sidebar to drop files or choose "
                    "the import path. This is the primary entry point for processed "
                    "sieve data and raw sieve weighings."
                ),
                target=lambda: getattr(self.control_panel, "_drop_zone", self.control_panel),
                tips=(
                    "Processed sieve data means size plus percent passing.",
                    "Raw sieve weighings means retained weights are converted first.",
                    "Use this instead of a separate top-toolbar import button.",
                ),
            ),
            TourStep(
                title="Loaded samples live here",
                body=(
                    "After loading, each dataset appears as a sample card. The sidebar "
                    "is the everyday navigation point for opening, inspecting, remapping, "
                    "including, or excluding datasets."
                ),
                target=lambda: getattr(self.control_panel, "_file_list", self.control_panel),
                tips=(
                    "Click a sample to open it.",
                    "Checked samples are included in comparison, reports, and export.",
                    "Use a sample card's context actions for inspect, remap, log, and remove.",
                ),
            ),
            TourStep(
                title="Manage scope and groups",
                body=(
                    "Use Manage when several datasets need group names or included-scope "
                    "changes. Groups feed aggregate tables, comparison plots, report "
                    "tables, and export outputs."
                ),
                target=lambda: getattr(self.control_panel, "_manage_samples_btn", self.control_panel),
                tips=(
                    "Rows can be selected like a spreadsheet before applying a group.",
                    "Group-level visibility is handled in the comparison plot sidebar.",
                ),
            ),
            TourStep(
                title="Check calculation inputs",
                body=(
                    "Use the Analysis menu for global calculation settings: temperature, "
                    "porosity mode, classification scheme, K-method selection, and manual "
                    "recalculation."
                ),
                target=lambda: getattr(self, "_analysis_menu_btn", self.control_panel),
                tips=(
                    "Temperature affects water density and viscosity.",
                    "Dataset porosity can be managed separately when needed.",
                    "The sidebar stays focused on importing and navigating samples.",
                ),
            ),
            TourStep(
                title="Classification context",
                body=(
                    "Classification scheme and stratigraphy-related settings are part "
                    "of the Analysis menu so reports, exports, plots, and tables share "
                    "the same global context."
                ),
                target=lambda: getattr(self, "_analysis_menu_btn", self.control_panel),
                tips=(
                    "Use Analysis > Classification Scheme to change the scheme.",
                    "Plots such as the grain-size histogram should follow the selected scheme.",
                ),
            ),
            TourStep(
                title="Individual Samples",
                body=(
                    "Use Individual Samples for one dataset at a time: distribution plots, "
                    "histograms, method results, warnings, and detailed per-sample tables."
                ),
                target=lambda: self.app_toolbar._nav_btns[0],
                tips=("The Samples sidebar is the dataset switcher for this workspace.",),
            ),
            TourStep(
                title="Comparison",
                body=(
                    "Use Comparison to work across datasets. This is where groups, aggregate "
                    "statistics, group-aware plots, and method inclusion choices matter most."
                ),
                target=lambda: self.app_toolbar._nav_btns[1],
                tips=(
                    "The plot sidebar controls visible samples and groups.",
                    "Details and Statistics summarize individual and aggregate results.",
                ),
            ),
            TourStep(
                title="Reports",
                body=(
                    "Use Reports for generated documents and report tables. The goal is that "
                    "reported tables use the same calculation backend as the live results."
                ),
                target=lambda: self.app_toolbar._nav_btns[2],
                tips=("Report layout and plot parity remain part of final QA.",),
            ),
            TourStep(
                title="Export",
                body=(
                    "Use Export for full data dumps and visible plot/table data. This is the "
                    "place for reproducible CSV, Excel, and figure outputs."
                ),
                target=lambda: self.app_toolbar._nav_btns[3],
                tips=("Drawer tables should export the same data they display.",),
            ),
            TourStep(
                title="Activity log",
                body=(
                    "The Log button opens in-program messages for data loading and validation. "
                    "Use it to check skipped rows, wrong-mode detection, and future warnings."
                ),
                target=self.app_toolbar.log_button,
                tips=(
                    "Warnings should be visible without requiring the terminal.",
                    "This becomes more important during batch imports.",
                ),
            ),
            TourStep(
                title="Status line",
                body=(
                    "The bottom status line summarizes the active sample, D50, K mean, "
                    "temperature, method count, and dataset count."
                ),
                target=lambda: self.rich_status_bar,
                tips=("This stays visible while moving between tabs.",),
            ),
            TourStep(
                title="Help and guides",
                body=(
                    "The Help button opens the guide library. The startup guide is for "
                    "orientation; detailed explanations belong in the help pages."
                ),
                target=lambda: self.app_toolbar._help_btn,
                tips=("The same overlay can later be reused for tab-specific tours.",),
            ),
        ]

    def show_individual_samples_guide(self):
        """Open a guided tour for the active Individual Samples dataset."""
        dataset_tab = self._current_dataset_tab()
        if dataset_tab is None and self.dataset_tabs:
            dataset_tab = self.dataset_tabs[0]
            tab_index = self.dataset_tabs_widget.indexOf(dataset_tab)
            if tab_index >= 0:
                self.dataset_tabs_widget.setCurrentIndex(tab_index)

        if dataset_tab is None:
            QMessageBox.information(
                self,
                "No Dataset Loaded",
                "Load at least one dataset before starting the Individual Samples guide.",
            )
            return

        self._switch_to_tab(0)
        QApplication.processEvents()
        self._start_tour_overlay(
            self._individual_samples_tour_steps(dataset_tab),
            show_startup_checkbox=False,
        )

    def _show_individual_tour_subtab(self, dataset_tab: DatasetTab, subtab_index: int) -> None:
        """Switch to a dataset subtab before a focused tour step is positioned."""
        self._switch_to_tab(0)
        tab_index = self.dataset_tabs_widget.indexOf(dataset_tab)
        if tab_index >= 0:
            self.dataset_tabs_widget.setCurrentIndex(tab_index)

        if hasattr(dataset_tab, "nested_tabs"):
            dataset_tab.nested_tabs.setCurrentIndex(subtab_index)

        if subtab_index == 1 and hasattr(dataset_tab, "results_table"):
            table = dataset_tab.results_table
            if table.rowCount() > 0 and not table.selectedItems():
                table.selectRow(0)

    def _first_tour_target(self, *widgets: QWidget | None) -> QWidget | None:
        """Return the first currently visible tour target, then the first existing target."""
        for widget in widgets:
            if widget is None:
                continue
            try:
                if widget.isVisibleTo(self):
                    return widget
            except RuntimeError:
                continue
        for widget in widgets:
            if widget is not None:
                return widget
        return self

    def _individual_samples_tour_steps(self, dataset_tab: DatasetTab) -> list[TourStep]:
        """Return a focused tour that walks Plot, Results, and Statistics automatically."""
        plot = dataset_tab.plot_workspace
        stats = dataset_tab.statistics_tab

        plot_step = lambda: self._show_individual_tour_subtab(dataset_tab, 0)
        results_step = lambda: self._show_individual_tour_subtab(dataset_tab, 1)
        stats_step = lambda: self._show_individual_tour_subtab(dataset_tab, 2)

        def stats_internals_step() -> None:
            stats_step()
            section = getattr(stats, "internals_section", None)
            if section is not None:
                section.set_expanded(True)

        return [
            TourStep(
                title="Individual Samples workspace",
                body=(
                    "This workspace follows one loaded dataset at a time. The guide will "
                    "switch through Plot, Results, and Statistics so the full per-sample "
                    "workflow is visible in one pass."
                ),
                target=lambda: self._first_tour_target(
                    dataset_tab.nested_tabs.tabBar(),
                    dataset_tab.nested_tabs,
                ),
                tips=(
                    "Use the main Samples sidebar to change which dataset is active.",
                    "The nested subtabs are only for the active dataset.",
                ),
                kicker="Individual Samples",
                before_step=plot_step,
            ),
            TourStep(
                title="Plot: choose the plot type",
                body=(
                    "Pick what to draw from the toolbar:\n"
                    "• Dist. Curve — the cumulative grain-size distribution.\n"
                    "• K-Values — a bar chart of hydraulic conductivity per method.\n"
                    "• More Plots — Combined (curve + K bars side by side) and Histogram "
                    "(mass retained per size fraction).\n"
                    "Quick toolbar toggles add the Classification zones (shaded size bands) "
                    "and the D10/D50/D60 reference lines."
                ),
                target=lambda: self._first_tour_target(
                    getattr(plot, "_seg_dist", None),
                    getattr(plot, "_more_plots", None),
                    plot,
                ),
                tips=(
                    "The histogram and zones follow the active stratigraphy scheme.",
                    "Each plot type has its own relevant sidebar controls.",
                ),
                kicker="Plot",
                before_step=plot_step,
            ),
            TourStep(
                title="Plot: the Controls sidebar",
                body=(
                    "The Controls button opens the settings sidebar, grouped into sections:\n"
                    "• Display options — grid, classification zones, D-lines, Fill curve "
                    "area and its Zone % in fill labels, point markers, K-value labels, and "
                    "a log K axis.\n"
                    "• Sample color — the colour of this sample's curve/series; click the "
                    "swatch to change it.\n"
                    "• Axis controls — fix the X and Y min/max instead of auto-ranging.\n"
                    "• Units — choose the K unit (on K-value plots).\n"
                    "• Legend & Typography — legend placement and font sizes."
                ),
                target=lambda: self._first_tour_target(
                    getattr(plot, "_tb_sidebar_btn", None),
                    plot,
                ),
                tips=(
                    "Only the sections relevant to the active plot type are shown.",
                    "Quick toggles stay in the toolbar; detailed settings in the sidebar.",
                ),
                kicker="Plot",
                before_step=plot_step,
            ),
            TourStep(
                title="Plot: chart, data drawer & export",
                body=(
                    "The chart is the visual result. The Table button opens a drawer "
                    "beneath it with the exact rows behind the active plot — the same rows "
                    "you can export to CSV. The figure itself exports as PNG (or other "
                    "image formats) from the toolbar."
                ),
                target=lambda: self._first_tour_target(
                    getattr(plot, "plot_widget", None),
                    getattr(plot, "_tb_drawer_btn", None),
                    plot,
                ),
                tips=(
                    "PNG export saves the figure; the drawer's CSV saves the plotted data.",
                    "What you see here is what reports and exports reproduce.",
                ),
                kicker="Plot",
                before_step=plot_step,
            ),
            TourStep(
                title="Results: the K-method table",
                body=(
                    "The Results subtab is the per-sample K-value table: one row per method, "
                    "with K shown in m/s, cm/s and m/d, plus a status — OK, warning, or "
                    "excluded. Click a column header to sort (e.g. by K value). Warnings and "
                    "failed applicability conditions are flagged here, never silently "
                    "averaged into the means."
                ),
                target=lambda: self._first_tour_target(
                    getattr(dataset_tab, "results_table", None),
                    getattr(dataset_tab, "results_widget", None),
                ),
                tips=(
                    "Which methods are active is set via Analysis > method selection.",
                    "Manual recalculation lives in Analysis > Recalculate K Values.",
                ),
                kicker="Results",
                before_step=results_step,
            ),
            TourStep(
                title="Results: method detail panel",
                body=(
                    "Selecting a method row fills the detail panel on the right with that "
                    "method's formula, the parameter values it used (D-sizes, porosity, "
                    "temperature), its applicability range, an explanation of the status, "
                    "and the literature reference — so you can see exactly why a method is "
                    "included or excluded from the means."
                ),
                target=lambda: self._first_tour_target(
                    getattr(dataset_tab, "detail_panel", None),
                    getattr(dataset_tab, "results_table", None),
                ),
                tips=(
                    "This is the place to understand and resolve method-specific warnings.",
                ),
                kicker="Results",
                before_step=results_step,
            ),
            TourStep(
                title="Results: summary cards & export",
                body=(
                    "The cards across the top summarize the sample: geometric and arithmetic "
                    "K means (m/d, from the included OK methods), the included-method count, "
                    "D50, and the temperature used. The Export and Copy buttons send the "
                    "table to a file or the clipboard. These per-sample values are what feed "
                    "the Comparison, Reports and Export views."
                ),
                target=lambda: self._first_tour_target(
                    getattr(dataset_tab, "res_bar", None),
                    getattr(dataset_tab, "results_widget", None),
                ),
                tips=(
                    "Means use only included OK methods — excluded ones are left out.",
                    "Temperature and porosity are set in the controls sidebar / Analysis.",
                ),
                kicker="Results",
                before_step=results_step,
            ),
            TourStep(
                title="Statistics: the sample at a glance",
                body=(
                    "Statistics is a read-only summary of everything computed for the "
                    "active sample that the Results table does not already list. The strip "
                    "along the top is the headline: sample name and point count, the soil "
                    "class, D50, the uniformity coefficient Cu, and the geometric-mean K "
                    "with how many methods were included."
                ),
                target=lambda: self._first_tour_target(
                    getattr(stats, "info_bar", None),
                    stats,
                ),
                tips=(
                    "Everything here is descriptive — it never changes your K results.",
                    "All values honour the classification scheme set in Stratigraphy.",
                ),
                kicker="Statistics",
                before_step=stats_step,
            ),
            TourStep(
                title="Statistics: grain-size distribution",
                body=(
                    "The Key Grain Distribution card lists the characteristic diameters "
                    "(D10/D50/D60/D90), a full percentile grid (D5–D95 by interpolation), "
                    "and a 'used by' column showing which K methods each diameter feeds. "
                    "These are read straight off the loaded gradation curve."
                ),
                target=lambda: self._first_tour_target(
                    getattr(stats, "distribution_card", None),
                    stats,
                ),
                tips=(
                    "Critical percentiles (D10/D30/D50/D60) are highlighted.",
                    "Values stay consistent with the plot labels and report tables.",
                ),
                kicker="Statistics",
                before_step=stats_step,
            ),
            TourStep(
                title="Statistics: classification & fractions",
                body=(
                    "This card is the detailed classification. The bar and table break the "
                    "sample into the full ISO 14688 sub-classes (fine/medium/coarse sand, "
                    "etc.) for the active scheme, with the dominant class highlighted. Above "
                    "them sit the standard label (e.g. 'Poorly-graded sand') and a plain-"
                    "language descriptor (e.g. 'Moderately well sorted sand'). Cu, Cc, "
                    "sorting and span are shown at the bottom."
                ),
                target=lambda: self._first_tour_target(
                    getattr(stats, "classification_card", None),
                    stats,
                ),
                tips=(
                    "Switch the scheme in Stratigraphy (ISO/USCS) to change these bands.",
                    "The same label and descriptor appear in reports and exports.",
                ),
                kicker="Statistics",
                before_step=stats_step,
            ),
            TourStep(
                title="Statistics: hydraulic conductivity",
                body=(
                    "The K summary aggregates the included methods into geometric mean, "
                    "arithmetic mean, median, range and the ln(K) spread, in m/s, cm/s and "
                    "m/d. The geometric mean is the primary value because K is "
                    "log-distributed. The Interpretation note beside it states the result "
                    "in words; Data Support and Calculation Context list the curve "
                    "coverage, temperature, porosity and permeability class."
                ),
                target=lambda: self._first_tour_target(
                    getattr(stats, "k_summary_card", None),
                    stats,
                ),
                tips=(
                    "Excluded methods (warnings/errors) are counted, not silently averaged.",
                    "Calculate K values first if this card is empty.",
                ),
                kicker="Statistics",
                before_step=stats_step,
            ),
            TourStep(
                title="Statistics: calculation internals",
                body=(
                    "Expanded at the bottom is Calculation Internals — the intermediate "
                    "values behind the K methods: water physical constants at the sample "
                    "temperature (ρ, μ, ρg/μ, τ), the per-method effective diameters, the "
                    "φ-unit Folk-Ward sorting that feeds Krumbein-Monk, and the porosity "
                    "functions. It is collapsed by default; open it when you need to audit "
                    "a number."
                ),
                target=lambda: self._first_tour_target(
                    getattr(stats, "internals_section", None),
                    stats,
                ),
                tips=(
                    "These echo the engine exactly — useful for checking a method by hand.",
                    "Reports and exports can include this same block.",
                ),
                kicker="Statistics",
                before_step=stats_internals_step,
            ),
        ]

    def show_comparison_guide(self):
        """Open a guided tour for the Comparison tab."""
        if len(self.dataset_tabs) < 2:
            QMessageBox.information(
                self,
                "Need Two Samples",
                "Load at least two datasets before starting the Comparison guide.",
            )
            return
        self._switch_to_tab(1)
        QApplication.processEvents()
        self._start_tour_overlay(
            self._comparison_tour_steps(),
            show_startup_checkbox=False,
        )

    def _show_comparison_subtab(self, index: int) -> None:
        """Switch to the Comparison tab and a given subtab before a tour step."""
        self._switch_to_tab(1)
        tabs = getattr(self.comparison_tab, "_tabs", None)
        if tabs is not None and 0 <= index < tabs.count():
            tabs.setCurrentIndex(index)
        QApplication.processEvents()

    def _comparison_tour_steps(self) -> list[TourStep]:
        """Return a focused tour that walks the Comparison Plot/Details/Statistics."""
        cmp = self.comparison_tab
        plot_step = lambda: self._show_comparison_subtab(0)
        details_step = lambda: self._show_comparison_subtab(1)
        stats_step = lambda: self._show_comparison_subtab(2)

        return [
            TourStep(
                title="Comparison workspace",
                body=(
                    "The Comparison tab puts two or more loaded samples side by side. Start "
                    "with 'Scope & Groups' to choose which datasets are included and how "
                    "they are grouped; 'Export Selected' saves the current view. The "
                    "comparison refreshes automatically when you enter the tab — 'Update' "
                    "is a manual rebuild if you need it."
                ),
                target=lambda: self._first_tour_target(
                    getattr(cmp, "_manage_btn", None),
                    getattr(cmp, "_update_btn", None),
                    cmp,
                ),
                tips=(
                    "You need at least two datasets loaded for a comparison.",
                    "Scope & Groups is where you control what is being compared.",
                ),
                kicker="Comparison",
                before_step=plot_step,
            ),
            TourStep(
                title="Comparison: three views",
                body=(
                    "The subtabs give three angles on the same selection: Plot (a visual "
                    "overlay of the curves or K bars), Details (cross-sample data tables), "
                    "and Statistics (aggregated K across scopes and methods). The guide "
                    "walks each in turn."
                ),
                target=lambda: self._first_tour_target(
                    cmp._tabs.tabBar() if getattr(cmp, "_tabs", None) is not None else None,
                    getattr(cmp, "_tabs", None),
                    cmp,
                ),
                tips=("All three views reflect the current Scope & Groups selection.",),
                kicker="Comparison",
                before_step=plot_step,
            ),
            TourStep(
                title="Plot: choose what to compare",
                body=(
                    "The toolbar above the chart controls the visual comparison:\n"
                    "• Plot type — Distribution (overlaid grain-size curves), K-Values "
                    "(a bar per method/sample), K Distribution (the spread of K), Combined, "
                    "or Histogram.\n"
                    "• Layout — Overlay draws every sample on one set of axes; Grid gives "
                    "each its own small chart (small multiples).\n"
                    "• Breakdown — Per dataset shows one series per sample; Per group "
                    "aggregates into one series per named group (it appears only once you "
                    "have defined groups in Scope & Groups)."
                ),
                target=lambda: self._first_tour_target(
                    getattr(getattr(cmp, "_plot_widget", None), "plot_selector", None),
                    getattr(cmp, "_plot_widget", None),
                    cmp,
                ),
                tips=(
                    "Each dataset (or group) keeps its own colour across all views.",
                    "Plot style (preset and palette) is shared with the Export tab.",
                ),
                kicker="Comparison",
                before_step=plot_step,
            ),
            TourStep(
                title="Plot: visibility & underlying data",
                body=(
                    "The 'Plot Visibility' rail on the right lists each dataset with a "
                    "show/hide toggle, so you can focus on a subset without changing the "
                    "scope; 'Show all' clears any focus or hidden datasets. To change which "
                    "datasets and groups are compared, use 'Scope & Groups' in the header "
                    "above. The collapsible Table drawer beneath the chart holds the exact "
                    "data behind the active plot and can export it to CSV."
                ),
                target=lambda: self._first_tour_target(
                    getattr(cmp, "_pin_list_widget", None),
                    getattr(cmp, "_plot_show_all_btn", None),
                    cmp,
                ),
                tips=(
                    "Hiding a dataset here only affects the plot, not Details or Statistics.",
                    "The drawer's CSV holds exactly what is plotted.",
                ),
                kicker="Comparison",
                before_step=plot_step,
            ),
            TourStep(
                title="Details: shaping the table",
                body=(
                    "Details is a standalone cross-sample table (not the data behind a "
                    "plot — that is the Plot drawer). The control bar shapes it:\n"
                    "• View — Individual puts one column per sample; Aggregate shows "
                    "group/overall summary columns.\n"
                    "• Mode — Grain shows size metrics (percentiles, Cu, Cc…); K-values "
                    "shows hydraulic conductivity per method.\n"
                    "• Rows — Summary keeps the key rows, All rows shows everything, "
                    "Classification adds fraction & gradation context.\n"
                    "• Status — include or exclude warning/error method results.\n"
                    "• Unit sets the K unit; Heat-map shades cells to reveal high/low "
                    "values across samples."
                ),
                target=lambda: self._first_tour_target(
                    getattr(cmp, "_details_view_individual_btn", None),
                    getattr(cmp, "_k_table", None),
                    cmp,
                ),
                tips=("This table is what the Export tab writes for comparison data.",),
                kicker="Comparison",
                before_step=details_step,
            ),
            TourStep(
                title="Statistics: aggregated K",
                body=(
                    "The Statistics subtab summarizes hydraulic conductivity two ways. The "
                    "scope table aggregates K overall and per group (mean, range, and how "
                    "many method results were included). The method table shows how each "
                    "method behaves across all selected samples, including the ln(K) spread "
                    "so you can see where methods agree or diverge."
                ),
                target=lambda: self._first_tour_target(
                    getattr(cmp, "_stats_scope_table", None),
                    getattr(cmp, "_stats_method_table", None),
                    cmp,
                ),
                tips=("Warnings and errors are reported, not silently averaged in.",),
                kicker="Comparison",
                before_step=stats_step,
            ),
            TourStep(
                title="Statistics: mean type and units",
                body=(
                    "Choose how the aggregates are summarized here: geometric mean (the "
                    "default, since K is log-distributed) or arithmetic mean, and the K unit "
                    "for the tables. These controls affect the Statistics view only."
                ),
                target=lambda: self._first_tour_target(
                    getattr(cmp, "_stats_metric_geo_btn", None),
                    getattr(cmp, "_stats_unit_combo", None),
                    cmp,
                ),
                tips=("Geometric mean is recommended for reporting a single K value.",),
                kicker="Comparison",
                before_step=stats_step,
            ),
        ]


    def show_reports_guide(self):
        """Open a guided tour for the Reports tab."""
        self._switch_to_tab(2)
        QApplication.processEvents()
        self._start_tour_overlay(
            self._reports_tour_steps(),
            show_startup_checkbox=False,
        )

    def show_export_guide(self):
        """Open a guided tour for the Export tab."""
        self._switch_to_tab(3)
        QApplication.processEvents()
        self._start_tour_overlay(
            self._export_tour_steps(),
            show_startup_checkbox=False,
        )

    def _ensure_tour_target_visible(self, widget: QWidget | None) -> None:
        """Ask a containing scroll area to reveal a tour target before spotlighting."""
        if widget is None:
            return

        current = widget.parentWidget()
        while current is not None:
            ensure = getattr(current, "ensureWidgetVisible", None)
            if callable(ensure):
                try:
                    ensure(widget, 18, 18)
                    QApplication.processEvents()
                except RuntimeError:
                    pass
                return
            current = current.parentWidget()

    def _prepare_reports_tour_step(
        self,
        *open_sections: str,
        target: Callable[[], QWidget | None] | None = None,
    ) -> None:
        """Switch to Reports, open the relevant accordion, and reveal a target."""
        self._switch_to_tab(2)
        tab = self.reporting_tab
        sections = {
            "_acc_type": getattr(tab, "_acc_type", None),
            "_acc_samples": getattr(tab, "_acc_samples", None),
            "_acc_sects": getattr(tab, "_acc_sects", None),
            "_acc_details": getattr(tab, "_acc_details", None),
        }
        if open_sections:
            wanted = set(open_sections)
            for name, section in sections.items():
                if section is not None and hasattr(section, "set_open"):
                    section.set_open(name in wanted)
        QApplication.processEvents()
        if target is not None:
            self._ensure_tour_target_visible(target())

    def _prepare_export_tour_step(
        self,
        *,
        inspector_index: int = 0,
        content_index: int | None = None,
        open_sections: tuple[str, ...] = (),
        target: Callable[[], QWidget | None] | None = None,
    ) -> None:
        """Switch to Export and put the inspector in the state a tour step needs."""
        self._switch_to_tab(3)
        tab = self.export_tab

        inspector_tabs = getattr(tab, "export_inspector_tabs", None)
        if inspector_tabs is not None:
            inspector_tabs.setCurrentIndex(inspector_index)

        sections = {
            "dataset_scope_section": getattr(tab, "dataset_scope_section", None),
            "format_section": getattr(tab, "format_section", None),
            "content_section": getattr(tab, "content_section", None),
            "output_folder_section": getattr(tab, "output_folder_section", None),
            "file_tree_section": getattr(tab, "file_tree_section", None),
            "plot_queue_section": getattr(tab, "plot_queue_section", None),
        }
        if open_sections:
            wanted = set(open_sections)
            for name, section in sections.items():
                if section is not None and hasattr(section, "set_open"):
                    section.set_open(name in wanted)

        content_tabs = self._export_content_tabs()
        if content_tabs is not None and content_index is not None:
            content_tabs.setCurrentIndex(content_index)

        QApplication.processEvents()
        if target is not None:
            self._ensure_tour_target_visible(target())

    def _report_plot_tour_target(self) -> QWidget | None:
        rows = getattr(self.reporting_tab, "_plot_rows", {})
        for scope in ("collection", "single"):
            for row in rows.get(scope, {}).values():
                return row
        return getattr(self.reporting_tab, "_acc_sects", self.reporting_tab)

    def _export_format_card(self, format_key: str) -> QWidget | None:
        return self.export_tab.findChild(QPushButton, f"format_card_{format_key}")

    def _export_content_tabs(self) -> QTabWidget | None:
        area = getattr(self.export_tab, "content_area", None)
        if area is None:
            return None
        return area.findChild(QTabWidget)

    def _export_content_checkbox(self, key: str) -> QWidget | None:
        return getattr(self.export_tab, "content_checkboxes", {}).get(key)

    def _export_first_plot_breakdown_combo(self) -> QWidget | None:
        combos = getattr(self.export_tab, "plot_breakdown_combos", {})
        for combo in combos.values():
            return combo
        return None

    def _reports_tour_steps(self) -> list[TourStep]:
        """Return a detailed tour for the Reports workflow."""
        return [
            TourStep(
                title="Reports workspace",
                body=(
                    "Reports turns the loaded analysis state into a readable document. "
                    "Use it when the deliverable is a report with narrative sections, "
                    "tables, figures, project metadata, and a controlled preview."
                ),
                target=lambda: self._first_tour_target(
                    self.app_toolbar._nav_btns[2],
                    self.reporting_tab,
                ),
                tips=(
                    "Use Reports for formal documents and review packages.",
                    "Use Export when you need raw tables, workbooks, or batches of figure files.",
                ),
                kicker="Reports",
                before_step=lambda: self._prepare_reports_tour_step(),
            ),
            TourStep(
                title="Choose the report type",
                body=(
                    "The report type controls the default scope and section preset. "
                    "Changing type is more than a label: it updates which samples are expected, "
                    "which tables are emphasized, and which plots are selected by default."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.reporting_tab, "_acc_type", None),
                    self.reporting_tab,
                ),
                tips=(
                    "Individual: exactly one sample, with detailed grain-size and K-method context.",
                    "Comparison: two or more selected samples, with group and overall summaries.",
                    "Full summary: every loaded sample, including appendices by default.",
                    "K focus: K tables and K plots first, with grain-size detail reduced.",
                ),
                kicker="Reports",
                before_step=lambda: self._prepare_reports_tour_step(
                    "_acc_type",
                    target=lambda: getattr(self.reporting_tab, "_acc_type", None),
                ),
            ),
            TourStep(
                title="Pick the output format",
                body=(
                    "The output format sets what the Save action will write after the report "
                    "has been generated. The preview is always built first, then the chosen "
                    "format is exported from that report state."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.reporting_tab, "_format_combo", None),
                    getattr(self.reporting_tab, "_acc_type", None),
                ),
                tips=(
                    "PDF is fixed and static: best for print, archiving, and sending a version that should not change.",
                    "Word (.docx) is editable: best when text, table layout, captions, or branding will be adjusted after export.",
                    "HTML is useful for browser review, quick sharing, and debugging the generated report structure.",
                    "The companion Excel appendix keeps large tables usable without overloading the report body.",
                ),
                kicker="Reports",
                before_step=lambda: self._prepare_reports_tour_step(
                    "_acc_type",
                    target=lambda: getattr(self.reporting_tab, "_format_combo", None),
                ),
            ),
            TourStep(
                title="Select the samples",
                body=(
                    "The Samples section decides which loaded datasets feed the report. "
                    "The table follows the report type: single selection for an Individual "
                    "report, multiple selection for Comparison and K focus, and locked all-sample "
                    "scope for a Full summary."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.reporting_tab, "_samp_table", None),
                    getattr(self.reporting_tab, "_acc_samples", None),
                ),
                tips=(
                    "Checked samples are the source for report tables, figures, aggregate statistics, and appendices.",
                    "Group names on datasets are reused in group summaries and group-based plots.",
                    "If the Generate button is disabled, the current sample count probably does not match the report type.",
                ),
                kicker="Reports",
                before_step=lambda: self._prepare_reports_tour_step(
                    "_acc_samples",
                    target=lambda: getattr(self.reporting_tab, "_samp_table", None),
                ),
            ),
            TourStep(
                title="Decide what the document contains",
                body=(
                    "Sections and appendices are the report outline. Main sections control "
                    "what appears in the document body; appendices add larger backup material "
                    "such as raw sieve data, full-size plots, and method detail."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.reporting_tab, "_acc_sects", None),
                    self.reporting_tab,
                ),
                tips=(
                    "Cover Page is required for report types that need formal front matter.",
                    "Sample & Grain Tables, K + Aggregate Tables, and Grain Statistics pull from the same calculated values as the live tabs.",
                    "Grain Statistics includes the detailed ISO sub-class breakdown, the plain-language descriptor, and the calculation internals.",
                    "Method References documents which K methods were used and why results may be included or excluded.",
                    "The outline updates so the user can see the expected document structure before generating.",
                ),
                kicker="Reports",
                before_step=lambda: self._prepare_reports_tour_step(
                    "_acc_sects",
                    target=lambda: getattr(self.reporting_tab, "_acc_sects", None),
                ),
            ),
            TourStep(
                title="Choose report plots",
                body=(
                    "Plot rows decide which figures are embedded in the report. Single-sample "
                    "plots are used for individual dataset detail; comparison plots summarize "
                    "multiple datasets and can break out by group or by dataset when that makes the figure clearer."
                ),
                target=lambda: self._first_tour_target(
                    self._report_plot_tour_target(),
                    getattr(self.reporting_tab, "_acc_sects", None),
                ),
                tips=(
                    "Distribution plots explain the grain-size curve; K plots explain method spread and comparison.",
                    "Breakdowns such as per group create separate figures instead of forcing every dataset into one crowded plot.",
                    "Reports and Export share the same plot vocabulary so the same plot choice means the same thing in both places.",
                ),
                kicker="Reports",
                before_step=lambda: self._prepare_reports_tour_step(
                    "_acc_sects",
                    target=self._report_plot_tour_target,
                ),
            ),
            TourStep(
                title="Set report and export plot style",
                body=(
                    "The Plot Style controls are global for Reports and Export. The preset "
                    "sets typography and figure density, the palette sets the data colors, "
                    "and Customize stores detailed overrides for future generated output."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.reporting_tab, "_style_controls", None),
                    getattr(self.reporting_tab, "_acc_sects", None),
                ),
                tips=(
                    "Change style here once when report figures and exported plot files should match.",
                    "Screen styling inside Individual Samples is separate; this control is for generated deliverables.",
                ),
                kicker="Reports",
                before_step=lambda: self._prepare_reports_tour_step(
                    "_acc_sects",
                    target=lambda: getattr(self.reporting_tab, "_style_controls", None),
                ),
            ),
            TourStep(
                title="Fill in details and branding",
                body=(
                    "Details & Branding adds project metadata, client/analyst fields, a report "
                    "accent color, an optional logo, and notes. These fields do not change the "
                    "calculations; they make the generated report traceable and presentable."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.reporting_tab, "project_name_edit", None),
                    getattr(self.reporting_tab, "_acc_details", None),
                ),
                tips=(
                    "Project name, number, date, analyst, and client appear in report front matter or headers.",
                    "Word export is the best option when the final branding or wording will be customized after generation.",
                    "PDF is better when the branded result should be locked for delivery.",
                ),
                kicker="Reports",
                before_step=lambda: self._prepare_reports_tour_step(
                    "_acc_details",
                    target=lambda: getattr(self.reporting_tab, "project_name_edit", None),
                ),
            ),
            TourStep(
                title="Generate the report state",
                body=(
                    "Generate captures the selected samples, result tables, plot settings, "
                    "metadata, and section choices, then renders the report in the background. "
                    "Export buttons stay tied to this generated state so stale content is not saved by accident."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.reporting_tab, "generate_btn", None),
                    self.reporting_tab,
                ),
                tips=(
                    "Generation validates the selected report type before starting.",
                    "If content changes after generation, use Refresh or Generate again before saving.",
                    "Long reports can take time because plots and appendices are rendered into the document.",
                ),
                kicker="Reports",
                before_step=lambda: self._prepare_reports_tour_step(
                    target=lambda: getattr(self.reporting_tab, "generate_btn", None),
                ),
            ),
            TourStep(
                title="Preview, print, and save",
                body=(
                    "The preview is the document you are about to export. Refresh rebuilds it, "
                    "Print sends the loaded preview to the printer workflow, and Save writes "
                    "the selected PDF, HTML, or Word file."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.reporting_tab, "btn_save", None),
                    getattr(self.reporting_tab, "web_view", None),
                    self.reporting_tab,
                ),
                tips=(
                    "PDF export waits for the preview engine to finish layout so page breaks and embedded plots are correct.",
                    "Word export is intentionally more flexible after export, but final formatting can depend on the word processor.",
                    "HTML keeps the generated report structure visible and is useful for checking what the backend produced.",
                ),
                kicker="Reports",
                before_step=lambda: self._prepare_reports_tour_step(
                    target=lambda: getattr(self.reporting_tab, "btn_save", None),
                ),
            ),
        ]

    def _export_tour_steps(self) -> list[TourStep]:
        """Return a detailed tour for the Export workflow."""
        return [
            TourStep(
                title="Export workspace",
                body=(
                    "Export writes structured data files and figure files. Use it when the "
                    "deliverable is machine-readable tables, a workbook, or a batch of plots "
                    "rather than a formatted narrative report."
                ),
                target=lambda: self._first_tour_target(
                    self.app_toolbar._nav_btns[3],
                    self.export_tab,
                ),
                tips=(
                    "Export is for reusable outputs: CSV, Excel, PNG, SVG, and plot PDFs.",
                    "Reports is for a document; Export is for the underlying files and figures.",
                ),
                kicker="Export",
                before_step=lambda: self._prepare_export_tour_step(),
            ),
            TourStep(
                title="Set the dataset scope",
                body=(
                    "Dataset Scope decides which loaded datasets are included before any files "
                    "are created. This scope affects table rows, aggregate statistics, plot batches, "
                    "file counts, and the output preview."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.export_tab, "scope_segment_frame", None),
                    getattr(self.export_tab, "dataset_scope_section", None),
                ),
                tips=(
                    "All exports every loaded dataset.",
                    "Current exports only the dataset selected in the source combo.",
                    "Selected exports the sidebar/comparison selection and can be managed from the Manage button.",
                    "Group labels matter because group-aware statistics and comparison plots use them.",
                ),
                kicker="Export",
                before_step=lambda: self._prepare_export_tour_step(
                    inspector_index=0,
                    open_sections=("dataset_scope_section",),
                    target=lambda: getattr(self.export_tab, "scope_segment_frame", None),
                ),
            ),
            TourStep(
                title="Choose table formats",
                body=(
                    "Format cards are independent toggles. CSV and Excel options write numeric "
                    "tables; they are the best outputs when another tool or reviewer needs to "
                    "filter, calculate, compare, or reuse the results."
                ),
                target=lambda: self._first_tour_target(
                    self._export_format_card("csv_long"),
                    getattr(self.export_tab, "format_section", None),
                ),
                tips=(
                    "CSV Long is tidy: one row per K-value result, good for R, Python, databases, and filtered analysis.",
                    "CSV Wide is comparison-oriented: one row per dataset with method columns, good for spreadsheets and statistics.",
                    "Excel creates one combined workbook with separate sheets and numeric cells, good for review and manual follow-up.",
                ),
                kicker="Export",
                before_step=lambda: self._prepare_export_tour_step(
                    inspector_index=0,
                    open_sections=("format_section",),
                    target=lambda: self._export_format_card("csv_long"),
                ),
            ),
            TourStep(
                title="Choose plot file formats",
                body=(
                    "PNG, SVG, and PDF create figure files for the selected plot types. "
                    "They export the visual figure, not the full report document and not a hidden data dump."
                ),
                target=lambda: self._first_tour_target(
                    self._export_format_card("png"),
                    getattr(self.export_tab, "format_section", None),
                ),
                tips=(
                    "PNG is a raster image: easy for slides, email, and quick insertion, but fixed resolution.",
                    "SVG is vector graphics: best for scaling and editing later in tools such as Inkscape or Illustrator.",
                    "PDF plot output is static and print-ready: good for publication-style figures and controlled sharing.",
                ),
                kicker="Export",
                before_step=lambda: self._prepare_export_tour_step(
                    inspector_index=0,
                    open_sections=("format_section",),
                    target=lambda: self._export_format_card("png"),
                ),
            ),
            TourStep(
                title="Select data table content",
                body=(
                    "Included Content controls which categories are written inside the selected "
                    "table formats. The Data tables tab covers grain-size distribution data, "
                    "K-value results, statistics, and sample metadata."
                ),
                target=lambda: self._first_tour_target(
                    self._export_content_tabs(),
                    getattr(self.export_tab, "content_section", None),
                ),
                tips=(
                    "Grain-size rows are the measured or interpolated curve values.",
                    "K-value rows come from the same calculation results shown in the Results tab.",
                    "Soil Classification adds the label, descriptor, detailed sub-class fractions, and calculation internals (Excel/JSON); CSV gets the descriptor column.",
                    "Statistics and metadata add context so files can be understood outside the application.",
                ),
                kicker="Export",
                before_step=lambda: self._prepare_export_tour_step(
                    inspector_index=0,
                    content_index=0,
                    open_sections=("content_section",),
                    target=self._export_content_tabs,
                ),
            ),
            TourStep(
                title="Select individual plot exports",
                body=(
                    "The Individual plots tab controls figures created once per exported dataset. "
                    "Use these when each sample needs its own grain-size curve, K-value figure, "
                    "or other per-sample visual output."
                ),
                target=lambda: self._first_tour_target(
                    self._export_content_checkbox("plot_scope_single_header"),
                    self._export_content_tabs(),
                    getattr(self.export_tab, "content_section", None),
                ),
                tips=(
                    "Per-sample plot counts multiply by dataset count and by every selected plot file format.",
                    "Plot file options such as legend and grid apply to generated figure files.",
                    "Plot Style (the shared footer below the tabs) sets the preset and palette for every exported plot — individual and comparison — and matches Reports.",
                ),
                kicker="Export",
                before_step=lambda: self._prepare_export_tour_step(
                    inspector_index=0,
                    content_index=1,
                    open_sections=("content_section",),
                    target=lambda: self._export_content_checkbox("plot_scope_single_header"),
                ),
            ),
            TourStep(
                title="Select comparison plot exports",
                body=(
                    "The Comparison plots tab controls figures built across the export scope. "
                    "These plots are used for overlays, K-value comparisons, distributions, "
                    "and other summary views where multiple datasets belong in one visual family."
                ),
                target=lambda: self._first_tour_target(
                    self._export_first_plot_breakdown_combo(),
                    self._export_content_checkbox("plot_scope_collection_header"),
                    self._export_content_tabs(),
                ),
                tips=(
                    "Per group creates one variant per group when group labels are available.",
                    "Per dataset creates dataset-specific variants when a combined plot would be too crowded.",
                    "The file tree updates immediately so the user sees how a breakdown changes the batch size.",
                ),
                kicker="Export",
                before_step=lambda: self._prepare_export_tour_step(
                    inspector_index=0,
                    content_index=2,
                    open_sections=("content_section",),
                    target=lambda: self._export_first_plot_breakdown_combo()
                    or self._export_content_checkbox("plot_scope_collection_header"),
                ),
            ),
            TourStep(
                title="Choose the output folder",
                body=(
                    "The Output tab shows where files will be written and what the batch will contain. "
                    "The folder path is the root; Export creates the structured subfolders underneath it."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.export_tab, "output_dir", None),
                    getattr(self.export_tab, "output_folder_section", None),
                ),
                tips=(
                    "Use a project-specific folder when exporting many datasets or many plot variants.",
                    "The app writes tables, workbooks, and plots into predictable grouped folders.",
                    "Changing scope, content, or formats updates the planned file set before anything is written.",
                ),
                kicker="Export",
                before_step=lambda: self._prepare_export_tour_step(
                    inspector_index=1,
                    open_sections=("output_folder_section",),
                    target=lambda: getattr(self.export_tab, "output_dir", None),
                ),
            ),
            TourStep(
                title="Review files to create",
                body=(
                    "Files to Create is the export manifest. It shows the folders and files that "
                    "will be produced from the current scope, format cards, content switches, "
                    "and plot breakdown choices."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.export_tab, "file_tree", None),
                    getattr(self.export_tab, "file_tree_section", None),
                ),
                tips=(
                    "CSV files are grouped under tables/csv.",
                    "Excel workbooks are grouped under workbooks.",
                    "Plot files are grouped by dataset and by collection plot family.",
                    "If the manifest looks wrong, adjust scope/content before exporting.",
                ),
                kicker="Export",
                before_step=lambda: self._prepare_export_tour_step(
                    inspector_index=1,
                    open_sections=("file_tree_section",),
                    target=lambda: getattr(self.export_tab, "file_tree", None),
                ),
            ),
            TourStep(
                title="Use the plot queue and preview",
                body=(
                    "Selected Plots lists the plot records that can be previewed on the right. "
                    "Selecting a plot switches the preview to the Plots tab and renders the same "
                    "figure backend that the export worker will use."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.export_tab, "plot_queue_tree", None),
                    getattr(self.export_tab, "preview_tabs", None),
                    self.export_tab,
                ),
                tips=(
                    "Open Source Sample is only enabled for single-sample plots, because collection plots do not belong to one dataset.",
                    "CSV and Excel previews show representative table structure; plot preview shows the actual figure renderer.",
                    "Preview is for checking the batch before committing files to disk.",
                ),
                kicker="Export",
                before_step=lambda: self._prepare_export_tour_step(
                    inspector_index=1,
                    open_sections=("plot_queue_section",),
                    target=lambda: getattr(self.export_tab, "plot_queue_tree", None),
                ),
            ),
            TourStep(
                title="Run the export",
                body=(
                    "The Export button builds one backend configuration from the selected scope, "
                    "formats, content switches, plot choices, output folder, and style settings, "
                    "then writes the files in a background worker."
                ),
                target=lambda: self._first_tour_target(
                    getattr(self.export_tab, "export_btn", None),
                    self.export_tab,
                ),
                tips=(
                    "The button label and bottom summary show the estimated file count before running.",
                    "The worker writes only the selected outputs; it does not silently include report files or hidden JSON.",
                    "After completion, check the output folder and open a few representative CSV, Excel, and plot files.",
                ),
                kicker="Export",
                before_step=lambda: self._prepare_export_tour_step(
                    target=lambda: getattr(self.export_tab, "export_btn", None),
                ),
            ),
        ]

    def open_help_dialog(self, topic_file: str | None = None):
        """Open the shared help dialog without blocking the main window."""
        from gui.help_dialog import HelpDialog

        dialog = self._help_dialog
        if dialog is None:
            dialog = HelpDialog(self)
            dialog.setModal(False)
            dialog.setWindowModality(Qt.WindowModality.NonModal)
            dialog.destroyed.connect(lambda *_args: setattr(self, "_help_dialog", None))
            self._help_dialog = dialog

        if topic_file:
            dialog.show_help_page(topic_file)

        if dialog.isMinimized():
            dialog.showNormal()
        else:
            dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def show_about(self):
        QMessageBox.about(
            self, "About",
            "<h3>Grain Size Analysis Tool</h3>"
            "<p>Version 0.9.0-\u03b2</p>"
            "<p>Grain size distribution analysis and hydraulic conductivity calculations.</p>"
            "<p>16 K-calculation methods \u00b7 batch import \u00b7 comparison \u00b7 export</p>"
            "<p>\u00a9 2024 \u2014 DTU Geotechnical Analysis Suite</p>",
        )

    # ──────────────────────────────────────────────────────────────────
    # STATUS BAR HELPERS
    # ──────────────────────────────────────────────────────────────────

    def record_log_event(self, event: Mapping[str, Any] | str, **kwargs) -> None:
        if isinstance(event, Mapping):
            self.log_store.add_event(event)
        else:
            self.log_store.add_event(message=event, **kwargs)

    def toggle_log_overlay(self) -> None:
        if self._log_overlay is not None and self._log_overlay.isVisible():
            self._log_overlay.hide()
            self.app_toolbar.set_log_active(False)
            return
        self.show_log_overlay()

    def show_log_overlay(self, *, file_key: str | None = None) -> None:
        if self._log_overlay is None:
            return
        self._log_overlay.show_near(self.app_toolbar.log_button(), file_key=file_key)
        self.app_toolbar.set_log_active(True)
        self.app_toolbar.set_log_badge(self.log_store.unread_important_count)

    def _show_status_message(self, message: str, ok: bool = True, timeout: int = 0):
        self.rich_status_bar.set_status(message, ok=ok)

    # ──────────────────────────────────────────────────────────────────
    # INTERNAL
    # ──────────────────────────────────────────────────────────────────

    def _on_calculation_complete(self, sample_name: str, results):
        if self._suppress_calculation_refresh_depth > 0:
            return
        if self._bulk_dataset_add_depth > 0:
            self._bulk_dataset_add_dirty = True
            if sample_name:
                self._bulk_dataset_add_last_label = sample_name
            return

        self._update_export_tab()
        # Update K̄ segment with current tab's result
        if results:
            try:
                vals = [
                    result.k_value
                    for result in results
                    if getattr(result, "k_value", None) is not None and result.k_value > 0
                ]
                if vals:
                    import math
                    gmean = math.exp(sum(math.log(v) for v in vals) / len(vals))
                    self.rich_status_bar.set_segment("K\u0304", f"{gmean:.2f} m/d")
            except Exception:
                pass

    def _on_dataset_data_updated(self, sample_name: str) -> None:
        self._update_export_tab()
        sender = self.sender()
        file_path = getattr(getattr(sender, "dataset", None), "file_path", None)
        if file_path:
            try:
                self.control_panel._push_card_meta(file_path)
            except Exception:
                pass
        self._refresh_dataset_status_segments(sample_name)
        self._show_status_message(f"Updated data: {sample_name}")

    def _update_export_tab(self):
        datasets = []
        plot_figures = []
        plot_contexts = []
        for tab in self.dataset_tabs:
            datasets.append((tab.get_dataset_name(), tab.get_dataset(), tab.get_results()))
            figure = None
            context = {}
            try:
                figure = tab.plot_workspace.plot_widget.figure
            except Exception:
                figure = None
            context = build_plot_context_from_tab(
                tab,
                getattr(self, "active_scheme", ISO14688),
            )
            plot_figures.append(figure)
            plot_contexts.append(context)
        self.export_tab.update_datasets(
            datasets,
            plot_figures=plot_figures,
            plot_contexts=plot_contexts,
            dataset_tabs=self.dataset_tabs,
            selected_tabs=self._get_selected_dataset_tabs(),
        )

    def closeEvent(self, event):
        if self.dataset_tabs:
            self._save_current_session()
        uninstall_in_app_logging(getattr(self, "_qt_log_handler", None))
        event.accept()
