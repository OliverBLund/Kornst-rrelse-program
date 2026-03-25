"""
Main window for the Grain Size Analysis application.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStatusBar, QStackedWidget, QTabWidget, QMessageBox,
    QProgressBar, QLabel, QFrame, QFileDialog, QDialog,
    QPushButton, QSizePolicy, QToolButton, QMenu, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QSize, QTimer
from PyQt6.QtGui import QAction, QColor, QFont
from typing import List, Optional
import os

from gui.control_panel import ControlPanel
from gui.dataset_tab import DatasetTab
from gui.comparison_tab import ComparisonTab
from gui.reporting_tab import ReportingTab
from gui.export_tab import ExportTab
from gui.error_tab import ErrorTab
from gui.welcome_widget import WelcomeWidget
from gui.theme import C, F, SZ, build_stylesheet, icon, apply_matplotlib_style
from qt_chrome import FramelessMainWindowMixin
from data_loader import DataLoader, GrainSizeData
from k_calculations import KCalculator


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
    calculate_clicked = pyqtSignal()
    help_clicked = pyqtSignal()

    _TABS = [
        ("fa6s.chart-area",    "Individual Samples"),
        ("fa6s.code-compare",  "Comparison"),
        ("fa6s.file-contract", "Reports"),
        ("fa6s.file-export",   "Export"),
    ]

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
            badge_font = QFont(F.MONO)
            badge_font.setPixelSize(9)
            badge_font.setWeight(QFont.Weight.Bold)
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
        self._add_btn = QPushButton(" Add Files")
        self._add_btn.setObjectName("tb-add")
        self._add_btn.setProperty("toolaction", True)
        try:
            self._add_btn.setIcon(icon("fa6s.folder-open", C.TEXT_MID))
            self._add_btn.setIconSize(QSize(11, 11))
        except Exception:
            pass
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.clicked.connect(self.add_files_clicked)
        layout.addWidget(self._add_btn)
        layout.addSpacing(4)

        # ── Primary button — .tb-btn.go ──────────────────────────────
        self._calc_btn = QPushButton(" Calculate K")
        self._calc_btn.setObjectName("tb-calc")
        self._calc_btn.setProperty("toolprimary", True)
        try:
            self._calc_btn.setIcon(icon("fa6s.bolt", "#ffffff"))
            self._calc_btn.setIconSize(QSize(11, 11))
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
            self._help_btn.setIconSize(QSize(11, 11))
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

    def _position_badge(self, btn: QPushButton, badge: QLabel) -> None:
        badge.setFixedWidth(self._badge_width(badge))
        fm = btn.fontMetrics()
        text_w = fm.horizontalAdvance(btn.text()) + 26  # icon + padding
        bx = text_w + 4
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
                btn.setIconSize(QSize(11, 11))
            except Exception:
                pass

            # Badge pill styling — olive-tinted when active, neutral otherwise
            badge = self._badge_lbls[i]
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
        layout.addWidget(self._led)
        layout.addSpacing(5)

        # Status text (e.g. "Ready")
        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(
            f"color: #a0d070; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;")
        layout.addWidget(self._status_lbl)

        # Segments: SAMPLE · D50 · K̄ · TEMP · METHODS · DATASETS
        self._seg_vals: dict[str, QLabel] = {}
        for key in ("SAMPLE", "D50", "K\u0304", "TEMP", "METHODS", "DATASETS"):
            layout.addWidget(self._vline())
            lbl_k = QLabel(f" {key} ")
            lbl_k.setStyleSheet(
                f"color: {C.ST_DIM}; font-family: '{F.MONO}'; font-size: 7pt;")
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
            f"color: {C.ST_DIM}; font-family: '{F.MONO}'; font-size: 7pt; "
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
        opacity = "1.0" if self._led_visible else "0.35"
        shadow = "0 0 5px rgba(125,208,80,0.5)" if self._led_visible else "none"
        self._led.setStyleSheet(
            f"background: {C.LED_OK_ST}; border-radius: 3px; opacity: {opacity};")

    def set_status(self, text: str, ok: bool = True) -> None:
        self._status_lbl.setText(text)
        self._led_ok = ok
        color = C.LED_OK_ST if ok else C.LED_WARN
        text_color = "#a0d070" if ok else C.LED_WARN
        self._led.setStyleSheet(f"background: {color}; border-radius: 3px;")
        self._status_lbl.setStyleSheet(
            f"color: {text_color}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;")

    def set_segment(self, key: str, value: str) -> None:
        if key in self._seg_vals:
            self._seg_vals[key].setText(value)


# ─────────────────────────────────────────────────────────────────────
# MainWindow
# ─────────────────────────────────────────────────────────────────────

class MainWindow(FramelessMainWindowMixin, QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
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
        apply_matplotlib_style()

        # Data structures
        self.data_loader = DataLoader()
        self.k_calculator = KCalculator()
        self.dataset_tabs: List[DatasetTab] = []
        self.dataset_counter = 0

        # Global stylesheet
        self.setStyleSheet(build_stylesheet())

        self.setup_ui()
        self.setup_menus()
        self.setup_statusbar()

        self._show_status_message("Ready")

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
        self.control_panel.files_loaded.connect(self.on_files_loaded)
        self.control_panel.error_dataset.connect(self.add_error_tab)
        self.control_panel.dataset_loaded_successfully.connect(self.replace_error_tab_with_dataset)
        self.control_panel.update_error_tab_message.connect(self.update_error_tab_message)
        self.control_panel.sample_selected.connect(self._on_sidebar_sample_selected)
        self.control_panel.selection_changed.connect(self._on_sidebar_selection_changed)

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
        self.app_toolbar.calculate_clicked.connect(self.calculate_all_k_values)
        self.app_toolbar.help_clicked.connect(self.show_help)
        main_layout.addWidget(self.app_toolbar)

        # Content stack (one page per top-level tab)
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack)

        # Page 0 — Individual Samples
        samples_container = QWidget()
        sc_layout = QVBoxLayout(samples_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)
        sc_layout.setSpacing(0)

        self.dataset_tabs_widget = QTabWidget()
        self.dataset_tabs_widget.setDocumentMode(True)
        self.dataset_tabs_widget.setIconSize(QSize(10, 10))
        self.dataset_tabs_widget.setTabsClosable(True)
        self.dataset_tabs_widget.tabCloseRequested.connect(self.close_dataset_tab)
        self._configure_dataset_tab_bar()
        # Tab styling handled by global QSS in theme.build_stylesheet()

        recent_files = self._load_recent_files()
        self.welcome_widget = WelcomeWidget(recent_files=recent_files)
        self._connect_welcome_signals()

        # Inner stack: index 0 = welcome (full-area, no tab chrome),
        #              index 1 = dataset_tabs_widget
        self._samples_stack = QStackedWidget()
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
        self.content_stack.addWidget(self.comparison_tab)

        # Page 2 — Reports
        self.reporting_tab = ReportingTab()
        self.content_stack.addWidget(self.reporting_tab)

        # Page 3 — Export
        self.export_tab = ExportTab()
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
        open_action = QAction("&Open Files\u2026", self)
        open_action.setShortcut("Ctrl+O")
        open_action.setIcon(icon("fa6s.folder-open", C.TEXT_MUTED))
        open_action.triggered.connect(self.control_panel.add_files)
        file_menu.addAction(open_action)
        self.addAction(open_action)

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
            btn.setIconSize(QSize(10, 10))

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
        self.content_stack.setCurrentIndex(index)
        self.app_toolbar.activate_tab(index)
        self._on_nav_tab_changed(index, _internal=True)

    def _on_nav_tab_changed(self, index: int, _internal: bool = False) -> None:
        """Respond to top-level tab change (from toolbar or programmatic)."""
        if not _internal:
            self.content_stack.setCurrentIndex(index)
        if index == 1:  # Comparison
            if len(self.dataset_tabs) >= 2:
                self.comparison_tab.update_comparison()
        elif index == 2:  # Reports
            self.reporting_tab.set_dataset_tabs(self.dataset_tabs)

    def _on_sidebar_sample_selected(self, sample_name: str) -> None:
        """When a sidebar card is clicked, switch to that dataset's tab."""
        # Also make sure we're on the Individual Samples page
        if self.content_stack.currentIndex() != 0:
            self.content_stack.setCurrentIndex(0)
            self.app_toolbar.activate_tab(0)
        self._hide_welcome()
        for i in range(self.dataset_tabs_widget.count()):
            tab = self.dataset_tabs_widget.widget(i)
            if hasattr(tab, 'dataset') and tab.dataset.sample_name == sample_name:
                self.dataset_tabs_widget.setCurrentIndex(i)
                return

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
        self.welcome_widget.load_sample_data_requested.connect(self.on_welcome_load_sample)
        self.welcome_widget.open_recent_file_requested.connect(self.on_welcome_open_recent)
        self.welcome_widget.open_help_topic_requested.connect(self.on_welcome_open_help)
        self.welcome_widget.dont_show_again_changed.connect(self.on_welcome_dont_show_again)
        self.welcome_widget.clear_sessions_requested.connect(self.on_clear_sessions)

    def on_welcome_load_files(self):
        self.control_panel.add_files()
        self._show_status_message("Select files to load\u2026")

    def on_welcome_load_sample(self):
        import os
        test_data_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_data")
        if os.path.exists(test_data_folder):
            for file in os.listdir(test_data_folder):
                if file.endswith('.csv'):
                    sample_path = os.path.join(test_data_folder, file)
                    try:
                        dataset = self.data_loader.load_file(sample_path)
                        self.add_dataset_tab(dataset)
                        self._save_recent_file(sample_path)
                        self._update_welcome_recent_files()
                        self._show_status_message(f"Loaded sample data: {file}")
                        return
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to load sample data:\n{str(e)}")
                        return
        QMessageBox.information(
            self, "No Sample Data",
            "No sample data files found. Use \u2018Add Files\u2019 to load your own data."
        )

    def on_welcome_open_recent(self, file_path: str):
        try:
            if os.path.exists(file_path):
                dataset = self.data_loader.load_file(file_path)
                dataset.file_path = file_path
                self.add_dataset_tab(dataset)
                self.control_panel.register_external_file(file_path, dataset)
                self._save_recent_file(file_path)
                self._update_welcome_recent_files()
                self._show_status_message(f"Opened: {os.path.basename(file_path)}")
            else:
                QMessageBox.warning(self, "File Not Found",
                                    f"The file no longer exists:\n{file_path}")
                self._remove_recent_file(file_path)
                self._update_welcome_recent_files()
        except Exception as e:
            QMessageBox.critical(self, "Error Loading File", f"Failed to load file:\n{str(e)}")

    def on_welcome_open_help(self, topic_file: str):
        from gui.help_dialog import HelpDialog
        help_dialog = HelpDialog(self)
        help_dialog.show_help_page(topic_file)
        help_dialog.exec()

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
            settings = QSettings("GrainSizeAnalysis", "MainWindow")
            settings.setValue("recent_sessions", [])
            self._refresh_welcome_widget()
            self._show_status_message("All sessions cleared")

    # ──────────────────────────────────────────────────────────────────
    # RECENT FILES / SESSIONS
    # ──────────────────────────────────────────────────────────────────

    def _load_recent_files(self) -> List[str]:
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        recent = settings.value("recent_files", [])
        if isinstance(recent, str):
            return [recent] if recent else []
        return recent if recent else []

    def _save_recent_file(self, file_path: str):
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        recent = self._load_recent_files()
        if file_path in recent:
            recent.remove(file_path)
        recent.insert(0, file_path)
        recent = recent[:10]
        settings.setValue("recent_files", recent)

    def _save_current_session(self):
        if not self.dataset_tabs:
            return
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        current_files = []
        for tab in self.dataset_tabs:
            dataset = tab.get_dataset()
            if hasattr(dataset, 'file_path') and dataset.file_path:
                current_files.append(dataset.file_path)
        if not current_files:
            return
        from datetime import datetime
        session = {
            'name': f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            'date': datetime.now().strftime('%Y-%m-%d'),
            'files': current_files,
            'timestamp': datetime.now().isoformat(),
        }
        recent_sessions = settings.value("recent_sessions", [])
        if not isinstance(recent_sessions, list):
            recent_sessions = []
        if not any(set(s.get('files', [])) == set(current_files) for s in recent_sessions):
            recent_sessions.insert(0, session)
            recent_sessions = recent_sessions[:10]
            settings.setValue("recent_sessions", recent_sessions)
            self._update_welcome_recent_files()

    def _remove_recent_file(self, file_path: str):
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        recent = self._load_recent_files()
        if file_path in recent:
            recent.remove(file_path)
            settings.setValue("recent_files", recent)

    def _update_welcome_recent_files(self):
        self.welcome_widget.update_recent_files(self._load_recent_files())

    def _refresh_welcome_widget(self):
        recent_files = self._load_recent_files()
        self._samples_stack.removeWidget(self.welcome_widget)
        self.welcome_widget = WelcomeWidget(recent_files=recent_files)
        self._connect_welcome_signals()
        self._samples_stack.insertWidget(0, self.welcome_widget)
        self._show_welcome()
        self._refresh_dataset_tab_icons()

    # ──────────────────────────────────────────────────────────────────
    # DATASET MANAGEMENT
    # ──────────────────────────────────────────────────────────────────

    def on_files_loaded(self, sample_names: List[str]):
        try:
            loaded_samples = self.control_panel.get_loaded_samples()
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(len(sample_names))
            self.progress_bar.setValue(0)

            for i, sample_name in enumerate(sample_names):
                if sample_name in loaded_samples:
                    file_path = loaded_samples[sample_name]['file_path']
                    try:
                        dataset = self.data_loader.load_file(file_path)
                        self.add_dataset_tab(dataset)
                        self.control_panel.set_sample_status(sample_name, "\u2705 Loaded")
                    except Exception as e:
                        print(f"Failed to load {file_path}: {e}")
                        datasets = self.load_file_with_mapper(file_path)
                        if datasets:
                            for dataset in datasets:
                                self.add_dataset_tab(dataset)
                            self.control_panel.set_sample_status(sample_name, "\u2705 Loaded")
                        else:
                            self.control_panel.set_sample_status(sample_name, "\u274c Failed")
                self.progress_bar.setValue(i + 1)

            self._show_status_message(f"Loaded {len(sample_names)} dataset(s)")

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Error loading files:\n{str(e)}")
            self._show_status_message("Error loading files", ok=False)
        finally:
            self.progress_bar.setVisible(False)

    def load_file_with_mapper(self, file_path: str) -> List[GrainSizeData]:
        from gui.column_mapper import ColumnMapperDialog
        dialog = ColumnMapperDialog(file_path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                mapping_results = dialog.get_mapping_results()
                datasets: List[GrainSizeData] = []
                for mapping in mapping_results:
                    dataset = GrainSizeData(
                        sample_name=mapping['sample_name'],
                        particle_sizes=mapping['particle_sizes'],
                        percent_passing=mapping['percent_passing'],
                        temperature=mapping.get('temperature', 20.0),
                        porosity=mapping.get('porosity', 0.4),
                        file_path=file_path,
                    )
                    datasets.append(dataset)
                return datasets
            except Exception as e:
                QMessageBox.critical(self, "Mapping Error", f"Error creating dataset:\n{str(e)}")
        return []

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

    def _on_sidebar_selection_changed(self):
        """Push the current selected-tab subset to the comparison tab."""
        self.comparison_tab.set_dataset_tabs(self._get_selected_dataset_tabs())

    def add_dataset_tab(self, dataset: GrainSizeData):
        self.dataset_counter += 1
        self._hide_welcome()
        dataset_tab = DatasetTab(dataset)

        temperature = self.control_panel.temp_spinbox.value()
        dataset_tab.set_parameters(temperature)
        dataset_tab.calculation_complete.connect(self._on_calculation_complete)

        tab_label = dataset.sample_name
        tab_index = self.dataset_tabs_widget.addTab(dataset_tab, tab_label)
        self.dataset_tabs_widget.setTabToolTip(tab_index, dataset.sample_name)
        self.dataset_tabs.append(dataset_tab)
        self.dataset_tabs_widget.setCurrentIndex(self.dataset_tabs_widget.count() - 1)
        self._refresh_dataset_tab_icons()

        self.comparison_tab.set_dataset_tabs(self._get_selected_dataset_tabs())
        self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
        self._update_export_tab()

        if hasattr(dataset, 'file_path') and dataset.file_path:
            self._save_recent_file(dataset.file_path)

        # Auto-calculate K values
        selected_methods = self.k_calculator.get_all_method_names()
        dataset_tab.calculate_k_values(selected_methods)

        # Update status bar segments
        n = len(self.dataset_tabs)
        self.rich_status_bar.set_segment("DATASETS", str(n))
        self.rich_status_bar.set_segment("SAMPLE", dataset.sample_name[:24])
        temp = self.control_panel.temp_spinbox.value()
        self.rich_status_bar.set_segment("TEMP", f"{temp}\u00b0C")
        self.rich_status_bar.set_segment("METHODS", str(len(self.k_calculator.get_all_method_names())))
        # Update Individual Samples badge with dataset count
        self.app_toolbar.set_badge(0, n)
        self._show_status_message(f"Loaded: {dataset.sample_name}")

    def add_error_tab(self, file_path: str, error_message: str):
        error_tab = ErrorTab(file_path, error_message, self)
        error_tab.dataset_fixed.connect(self.on_dataset_fixed)
        file_name = os.path.basename(file_path)
        index = self.dataset_tabs_widget.addTab(error_tab, file_name)
        self.dataset_tabs_widget.setTabToolTip(index, file_name)
        self.dataset_tabs_widget.tabBar().setTabTextColor(index, QColor(211, 47, 47))
        self.dataset_tabs_widget.setCurrentIndex(index)
        self._refresh_dataset_tab_icons()
        self._show_status_message(f"Error loading: {file_name} \u2014 click tab to fix", ok=False)

    def _remove_error_tab(self, file_path: str) -> bool:
        for i in range(self.dataset_tabs_widget.count()):
            widget = self.dataset_tabs_widget.widget(i)
            if isinstance(widget, ErrorTab) and widget.file_path == file_path:
                self.dataset_tabs_widget.removeTab(i)
                return True
        return False

    def _ensure_dataset_list(self, dataset_input) -> List[GrainSizeData]:
        if isinstance(dataset_input, list):
            return dataset_input
        return [dataset_input]

    def on_dataset_fixed(self, dataset_input, original_file_path: str):
        datasets = self._ensure_dataset_list(dataset_input)
        self._remove_error_tab(original_file_path)
        for dataset in datasets:
            self.add_dataset_tab(dataset)
        name = datasets[0].sample_name if len(datasets) == 1 else f"{len(datasets)} datasets"
        self._show_status_message(f"Fixed and loaded: {name}")

    def replace_error_tab_with_dataset(self, dataset_input, file_path: str):
        datasets = self._ensure_dataset_list(dataset_input)
        self._remove_error_tab(file_path)
        for dataset in datasets:
            self.add_dataset_tab(dataset)

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
                break

    def close_dataset_tab(self, index: int):
        dataset_index = index
        if 0 <= dataset_index < len(self.dataset_tabs):
            self.dataset_tabs.pop(dataset_index)
        self.dataset_tabs_widget.removeTab(index)
        self._refresh_dataset_tab_icons()
        if not self.dataset_tabs:
            self._show_welcome()
        self.comparison_tab.set_dataset_tabs(self._get_selected_dataset_tabs())
        self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
        self._update_export_tab()
        n = len(self.dataset_tabs)
        self.rich_status_bar.set_segment("DATASETS", str(n) if n else "\u2014")
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

    def export_current(self):
        current = self.content_stack.currentIndex()
        if current == 0:
            idx = self.dataset_tabs_widget.currentIndex() - 1
            if 0 <= idx < len(self.dataset_tabs):
                try:
                    self.dataset_tabs[idx].export_results()
                except Exception:
                    self.dataset_tabs[idx].plot_workspace.export_plot("png")
        else:
            self.comparison_tab.export_comparison()

    def export_results(self):
        current = self.content_stack.currentIndex()
        if current == 0:
            idx = self.dataset_tabs_widget.currentIndex() - 1
            if 0 <= idx < len(self.dataset_tabs):
                self.dataset_tabs[idx].export_results()
        else:
            self.comparison_tab.export_comparison()

    def export_plot(self):
        current = self.content_stack.currentIndex()
        if current == 0:
            idx = self.dataset_tabs_widget.currentIndex() - 1
            if 0 <= idx < len(self.dataset_tabs):
                self.dataset_tabs[idx].plot_workspace.export_plot("png")
        else:
            self.comparison_tab.export_comparison()

    # ──────────────────────────────────────────────────────────────────
    # DIALOGS
    # ──────────────────────────────────────────────────────────────────

    def show_help(self):
        from gui.help_dialog import HelpDialog
        HelpDialog(self).exec()

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
        self._update_export_tab()
        # Update K̄ segment with current tab's result
        if results:
            try:
                vals = [v for v in results.values() if v and v > 0]
                if vals:
                    import math
                    gmean = math.exp(sum(math.log(v) for v in vals) / len(vals))
                    self.rich_status_bar.set_segment("K\u0304", f"{gmean:.2f} m/d")
            except Exception:
                pass

    def _update_export_tab(self):
        datasets = []
        plot_figures = []
        for tab in self.dataset_tabs:
            datasets.append((tab.get_dataset_name(), tab.get_dataset(), tab.get_results()))
            figure = None
            try:
                figure = tab.plot_workspace.plot_widget.figure
            except Exception:
                figure = None
            plot_figures.append(figure)
        self.export_tab.update_datasets(datasets, plot_figures=plot_figures)

    def closeEvent(self, event):
        if self.dataset_tabs:
            self._save_current_session()
        event.accept()
