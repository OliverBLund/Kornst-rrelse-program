"""
Main window for the Grain Size Analysis application.
"""

from __future__ import annotations

from collections import deque
import multiprocessing as mp
import os
import queue

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStatusBar, QStackedWidget, QTabWidget, QMessageBox,
    QProgressBar, QLabel, QFrame, QFileDialog,
    QPushButton, QSizePolicy, QToolButton, QMenu, QSplitter,
    QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QSize, QTimer, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QAction, QColor, QFont
from typing import Any, Callable, List, Mapping, Optional

from gui.control_panel import ControlPanel
from gui.dataset_tab import DatasetTab
from gui.comparison_tab import ComparisonTab
from gui.reporting_tab import ReportingTab
from gui.export_tab import ExportTab
from gui.error_tab import ErrorTab
from gui.loading_dialog import LoadingDialog
from gui.stack_fade import StackFadeController, TabFadeInController
from gui.welcome_widget import WelcomeWidget
from gui.theme import C, F, SZ, build_stylesheet, icon, apply_matplotlib_style
from gui.plot_context import build_plot_context_from_tab
from qt_chrome import FramelessMainWindowMixin
from data_loader import DataLoader, GrainSizeData
from k_calculations import KCalculator
from grain_classification import ISO14688
from load_process_worker import run_external_load


# ─────────────────────────────────────────────────────────────────────
# _AppToolbar  — matches _shared.css .tb
# ─────────────────────────────────────────────────────────────────────

class _AppToolbar(QWidget):
    """
    Global toolbar: navigation tabs (left) + action buttons (middle) + help (right).
    Styled entirely via QSS properties defined in theme.build_stylesheet().
    """
    tab_changed = pyqtSignal(int)   # emits 0=Individual, 1=Comparison, 2=Reports, 3=Export
    add_files_clicked = pyqtSignal()
    add_files_mode_clicked = pyqtSignal(str)
    calculate_clicked = pyqtSignal()
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

        # ── Separator — .tb-sep ──────────────────────────────────────
        sep = QWidget()
        sep.setFixedSize(1, 20)
        sep.setStyleSheet(f"background: {C.TB_BDR};")
        layout.addWidget(sep)
        layout.addSpacing(6)

        # ── Action buttons — .tb-btn ─────────────────────────────────
        self._add_btn = QPushButton(" Add Data")
        self._add_btn.setObjectName("tb-add")
        self._add_btn.setProperty("toolaction", True)
        try:
            self._add_btn.setIcon(icon("fa6s.folder-open", C.TEXT_MID))
            self._add_btn.setIconSize(self._CHROME_ICON_SIZE)
        except Exception:
            pass
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_menu = QMenu(self._add_btn)
        processed_action = add_menu.addAction("Processed Curve Data...")
        processed_action.triggered.connect(lambda _checked=False: self.add_files_mode_clicked.emit("processed"))
        raw_action = add_menu.addAction("Raw Sieve Weighings...")
        raw_action.triggered.connect(lambda _checked=False: self.add_files_mode_clicked.emit("raw_sieve"))
        self._add_btn.setMenu(add_menu)
        layout.addWidget(self._add_btn)
        layout.addSpacing(4)

        # ── Primary button — .tb-btn.go ──────────────────────────────
        self._calc_btn = QPushButton(" Calculate K")
        self._calc_btn.setObjectName("tb-calc")
        self._calc_btn.setProperty("toolprimary", True)
        try:
            self._calc_btn.setIcon(icon("fa6s.bolt", "#ffffff"))
            self._calc_btn.setIconSize(self._CHROME_ICON_SIZE)
        except Exception:
            pass
        self._calc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._calc_btn.clicked.connect(self.calculate_clicked)
        layout.addWidget(self._calc_btn)

        layout.addStretch()

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
        self.setWindowTitle("Grain Size Analysis \u2014 Hydraulic Conductivity Calculator")
        self.init_frameless_window_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=8,
            top_resize_margin=6,
            corner_radius_px=10,
            enable_edge_resize=True,
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
        self._help_dialog = None
        self._external_load_poll_timer = QTimer(self)
        self._external_load_poll_timer.setInterval(25)
        self._external_load_poll_timer.timeout.connect(self._poll_external_load_process)
        self._external_load_ui_timer = QTimer(self)
        self._external_load_ui_timer.setInterval(0)
        self._external_load_ui_timer.timeout.connect(self._process_external_load_ui_slice)

        # Global stylesheet
        self._emit_startup_progress(
            85,
            "Applying interface theme",
            "Styling the application shell and controls.",
        )
        self.setStyleSheet(build_stylesheet())

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
        self.control_panel.setMinimumWidth(280)
        self.control_panel.error_dataset.connect(self.add_error_tab)
        self.control_panel.mapping_required.connect(self.add_mapping_required_tab)
        self.control_panel.dataset_loaded_successfully.connect(self.replace_error_tab_with_dataset)
        self.control_panel.update_error_tab_message.connect(self.update_error_tab_message)
        self.control_panel.dataset_integration_started.connect(self._begin_bulk_dataset_add)
        self.control_panel.dataset_integration_finished.connect(self._end_bulk_dataset_add)
        self.control_panel.sample_selected.connect(self._on_sidebar_sample_selected)
        self.control_panel.selection_changed.connect(self._on_sidebar_selection_changed)
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
        self.app_toolbar.add_files_clicked.connect(self.control_panel.add_files)
        self.app_toolbar.add_files_mode_clicked.connect(self.control_panel.add_files)
        self.app_toolbar.calculate_clicked.connect(self.calculate_all_k_values)
        self.app_toolbar.help_clicked.connect(self.show_help)
        main_layout.addWidget(self.app_toolbar)

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
        dont_show = settings_tmp.value("welcome_screen/dont_show", False, type=bool)
        self._samples_stack.setCurrentIndex(0 if not dont_show else 1)
        # Sidebar is only visible when datasets are shown
        self.control_panel.setVisible(dont_show)

        self.dataset_tabs_widget.currentChanged.connect(self._on_dataset_tab_changed)
        self._refresh_dataset_tab_icons()
        sc_layout.addWidget(self._samples_stack)
        self.content_stack.addWidget(samples_container)

        # Page 1 — Comparison
        self.comparison_tab = ComparisonTab()
        self.comparison_tab.dataset_selection_requested.connect(
            self._on_comparison_selection_requested
        )
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
        shell_splitter.setSizes([SZ.SIDEBAR_W, 1200])
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
        open_processed_action = QAction("&Open Processed Curve Data\u2026", self)
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

        calculate_action = QAction("&Calculate K Values", self)
        calculate_action.setShortcut("Ctrl+K")
        calculate_action.setIcon(icon("fa6s.bolt", C.TEXT_MUTED))
        calculate_action.triggered.connect(self.calculate_all_k_values)
        analysis_menu.addAction(calculate_action)
        self.addAction(calculate_action)

        analysis_menu.addSeparator()

        update_comparison_action = QAction("&Update Comparison", self)
        update_comparison_action.setIcon(icon("fa6s.rotate", C.TEXT_MUTED))
        update_comparison_action.triggered.connect(self.update_comparison)
        analysis_menu.addAction(update_comparison_action)
        menu_layout.addWidget(self._make_menu_button("Analysis", analysis_menu))

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
        self._chrome_controls = controls
        self._chrome_title_label = title_label
        self.bind_frameless_drag_widget(menu_widget, allow_double_click_maximize=True, include_children=True)
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
        """Tune the dataset tab bar to behave more like the concept's compact strip."""
        tab_bar = self.dataset_tabs_widget.tabBar()
        tab_bar.setExpanding(False)
        tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        tab_bar.setDrawBase(False)

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
            self._show_status_message("Select processed curve files\u2026")

    def on_welcome_load_sample(self):
        test_data_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_data")
        if os.path.exists(test_data_folder):
            for file in os.listdir(test_data_folder):
                if file.endswith('.csv'):
                    sample_path = os.path.normpath(os.path.join(test_data_folder, file))
                    if sample_path in self._get_open_file_paths():
                        self._save_recent_file(sample_path)
                        self._update_welcome_recents()
                        self._switch_to_tab(0)
                        self._hide_welcome()
                        self._show_status_message(f"Already open: {file}")
                        return
                    self._start_external_load(
                        [sample_path],
                        title="Loading Sample Data",
                        subtitle="Opening the bundled demo dataset",
                        stage_title="Loading sample data",
                        context={
                            "mode": "sample",
                            "missing_files": [],
                            "skipped_count": 0,
                            "session": None,
                            "requested_label": file,
                            "failed_files": [],
                        },
                    )
                    return
        QMessageBox.information(
            self, "No Sample Data",
            "No sample data files found. Use \u2018Add Files\u2019 to load your own data."
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

    def on_welcome_dont_show_again(self, dont_show: bool):
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        settings.setValue("welcome_screen/dont_show", dont_show)

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
            for key in ("sample_name", "temperature", "porosity", "data_type", "selection_method"):
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
        }
        if mapping_state:
            descriptor["mapping_state"] = dict(mapping_state)
            descriptor["data_type"] = "raw_sieve" if mapping_state.get("raw_sieve_mode") else "calculated"
            descriptor["selection_method"] = (
                "column"
                if mapping_state.get("raw_sieve_mode")
                else mapping_state.get("calculated_selection_mode", "column")
            )
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
        """Return dataset tabs for sidebar-selected cards, or all tabs if none selected."""
        selected_paths = self.control_panel.get_selected_paths()
        if not selected_paths:
            return self.dataset_tabs
        path_set = set(selected_paths)
        filtered = [t for t in self.dataset_tabs
                    if hasattr(t, 'dataset') and hasattr(t.dataset, 'file_path')
                    and t.dataset.file_path in path_set]
        return filtered if filtered else self.dataset_tabs

    def _sync_comparison_dataset_state(self) -> None:
        """Keep comparison loaded/selected dataset state aligned with the sidebar."""
        self.comparison_tab.set_dataset_state(
            self.dataset_tabs,
            selected_tabs=self._get_selected_dataset_tabs(),
        )

    def _on_sidebar_selection_changed(self):
        """Push the current selected-tab subset to the comparison tab."""
        self._sync_comparison_dataset_state()
        if hasattr(self, "export_tab"):
            self.export_tab.set_dataset_selection_state(
                self.dataset_tabs,
                selected_tabs=self._get_selected_dataset_tabs(),
            )

    def _on_comparison_selection_requested(self, file_paths: list[str]) -> None:
        """Apply comparison-dialog selections back onto the sidebar cards."""
        self.control_panel.set_selected_paths(file_paths)

    def _on_export_selection_requested(self, file_paths: list[str]) -> None:
        """Apply export-dialog selections back onto the sidebar cards."""
        self.control_panel.set_selected_paths(file_paths)

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
        self.rich_status_bar.set_segment("METHODS", str(len(self.k_calculator.get_all_method_names())))
        self.app_toolbar.set_badge(0, n)

    def add_dataset_tab(self, dataset: GrainSizeData):
        bulk_mode = self._bulk_dataset_add_depth > 0
        self.dataset_counter += 1
        self._hide_welcome()
        dataset_tab = DatasetTab(dataset)

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
            selected_methods = self.k_calculator.get_all_method_names()
            dataset_tab.calculate_k_values(selected_methods)

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

    def calculate_all_k_values(self):
        if not self.dataset_tabs:
            QMessageBox.information(self, "No Data", "Please load datasets first.")
            return

        from k_calculations import KCalculator
        calculator = KCalculator()
        selected_methods = calculator.get_all_method_names()

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.dataset_tabs))
        self.progress_bar.setValue(0)

        try:
            temperature = self.control_panel.temp_spinbox.value()
            for i, dataset_tab in enumerate(self.dataset_tabs):
                dataset_tab.set_parameters(temperature)
                dataset_tab.calculate_k_values(selected_methods)
                self.progress_bar.setValue(i + 1)

            self._show_status_message(
                f"K values calculated for {len(self.dataset_tabs)} dataset(s)"
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
            "<p>14+ K-calculation methods \u00b7 batch import \u00b7 comparison \u00b7 export</p>"
            "<p>\u00a9 2024 \u2014 DTU Geotechnical Analysis Suite</p>",
        )

    # ──────────────────────────────────────────────────────────────────
    # STATUS BAR HELPERS
    # ──────────────────────────────────────────────────────────────────

    def _show_status_message(self, message: str, ok: bool = True, timeout: int = 0):
        self.rich_status_bar.set_status(message, ok=ok)

    # ──────────────────────────────────────────────────────────────────
    # INTERNAL
    # ──────────────────────────────────────────────────────────────────

    def _on_calculation_complete(self, sample_name: str, results):
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
        event.accept()
