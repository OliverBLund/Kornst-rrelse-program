#!/usr/bin/env python3
"""
Grain Size Analysis Program - PyQt6 entry point with startup splash screen.
"""

import multiprocessing as mp
import sys
import traceback
from datetime import datetime
from pathlib import Path
import tempfile

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QRectF, QCoreApplication
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPixmap

# Must be set before QApplication is created.
# PassThrough lets Qt (and matplotlib's canvas) use the exact fractional
# device-pixel ratio (e.g. 1.25 for 125% Windows scaling) so matplotlib
# renders at full physical resolution instead of being upscaled → no blur.
QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

from Splash.simple_splash import SimpleSplash
from version import VERSION
# MainWindow imported later to speed up splash appearance


APP_USER_MODEL_ID = "DTU.GrainSizeAnalysis.Desktop"


def _prime_qt_webengine() -> None:
    """
    Import Qt WebEngine before QApplication is created.

    ReportingTab is imported later during lazy startup, and that import path pulls in
    QWebEngineView. If Qt WebEngine is first imported after QApplication exists,
    Qt can disable WebEngine with the exact error the user reported.
    """
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    except Exception as exc:
        _log_startup_error("QtWebEngine preload", exc)


def _startup_font_base_dir() -> Path:
    """Return bundled font path without importing the full theme module."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        candidates = [
            base / "Program" / "resources" / "fonts",
            base / "resources" / "fonts",
        ]
        for candidate in candidates:
            if candidate.is_dir():
                return candidate
        return candidates[0]
    return Path(__file__).resolve().parent / "resources" / "fonts"


def _startup_resource_file(name: str) -> Path:
    """Return a bundled startup resource path for dev and frozen builds."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        candidates = [
            base / "Program" / "resources" / name,
            base / "resources" / name,
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return candidates[0]
    return Path(__file__).resolve().parent / "resources" / name


def _load_startup_fonts() -> None:
    """Register bundled UI fonts without importing matplotlib or theme helpers."""
    base = _startup_font_base_dir()
    if not base.is_dir():
        return

    for font_file in sorted(base.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id < 0:
            print(f"[startup] WARNING: Failed to load font: {font_file.name}")


def _startup_ui_font_family() -> str:
    """Return the primary UI font for early startup widgets."""
    if sys.platform == "win32":
        return "Segoe UI"
    return "Source Sans 3"


def _startup_ui_font(point_size: int = 9) -> QFont:
    """Build the shared startup UI font with crisp rendering preferences."""
    font = QFont(_startup_ui_font_family(), point_size)
    font.setStyleStrategy(QFont.StyleStrategy.PreferQuality)
    if sys.platform == "win32":
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font


def _startup_app_icon() -> QIcon:
    """Create a lightweight app icon for startup without qtawesome."""
    icon_path = _startup_resource_file("app_icon.ico")
    if icon_path.is_file():
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            return icon

    ico = QIcon()

    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        inset = max(1, size // 16)
        border_w = max(1, size // 32)
        radius = max(4.0, size * 0.22)
        rect = QRectF(inset, inset, size - inset * 2, size - inset * 2)

        painter.setPen(QPen(QColor("#8e6e4a"), border_w))
        painter.setBrush(QColor("#7a5e3e"))
        painter.drawRoundedRect(rect, radius, radius)

        accent_h = max(2.0, size * 0.14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#6b8e23"))
        painter.drawRoundedRect(
            QRectF(rect.left(), rect.bottom() - accent_h, rect.width(), accent_h),
            radius * 0.55,
            radius * 0.55,
        )

        font = QFont("Source Sans 3", max(7, int(size * 0.26)), QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f4ece0"))
        painter.drawText(rect.adjusted(0, -size * 0.04, 0, 0), Qt.AlignmentFlag.AlignCenter, "GS")
        painter.end()

        ico.addPixmap(pix)

    return ico


def _set_windows_app_user_model_id(app_id: str) -> None:
    """Best-effort AppUserModelID for Windows taskbar grouping/icon identity."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
    except Exception:
        pass


def _log_startup_error(source: str, exc: Exception) -> None:
    """Write startup exceptions to a temp file for debugging packaged builds."""
    log_path = Path(tempfile.gettempdir()) / "grain_startup_error.log"
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {source}: {exc}\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            f.write("\n")
    except Exception:
        # Best-effort only
        pass
    try:
        print(f"[startup-error] {source}: {exc}", file=sys.stderr)
        print(f"[startup-error] log: {log_path}", file=sys.stderr)
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
    except Exception:
        pass


class LoaderThread(QThread):
    """Background thread to load heavy modules without freezing the splash"""
    loaded = pyqtSignal(object)               # Sends the MainWindow class when done
    progress = pyqtSignal(int, str, str)      # percent, stage, detail

    def run(self):
        """Load MainWindow in background thread"""
        try:
            self.progress.emit(
                28,
                "Loading data models",
                "Preparing file loaders and dataset structures.",
            )
            import data_loader  # noqa: F401

            self.progress.emit(
                40,
                "Loading calculation methods",
                "Preparing hydraulic conductivity equations and helpers.",
            )
            import k_calculations  # noqa: F401

            self.progress.emit(
                52,
                "Loading plotting stack",
                "Importing matplotlib and plot styling components.",
            )
            import matplotlib  # noqa: F401

            self.progress.emit(
                64,
                "Loading workspace widgets",
                "Importing the main interface modules and dialogs.",
            )
            from gui.main_window import MainWindow

            self.progress.emit(
                78,
                "Preparing workspace",
                "The main window class is ready to be created.",
            )
            self.loaded.emit(MainWindow)
        except Exception as e:
            _log_startup_error("LoaderThread", e)
            self.progress.emit(100, "Startup failed", str(e))
            self.loaded.emit(None)


def main() -> None:
    _set_windows_app_user_model_id(APP_USER_MODEL_ID)
    _prime_qt_webengine()
    app = QApplication(sys.argv)
    app.setApplicationName("Grain Size Analysis")
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("Geotechnical Engineering")
    app.setOrganizationDomain("grainsize.app")

    # Create and show splash screen immediately, before theme/icon/font setup.
    splash = SimpleSplash()
    splash.set_progress(
        6,
        "Starting Grain Size Analysis",
        "Preparing the startup shell.",
    )
    splash.show()
    splash.raise_()
    splash.activateWindow()
    app.processEvents()

    # Create loader thread
    loader = LoaderThread()

    def on_progress(percent: int, stage: str, detail: str):
        """Update splash with progress messages"""
        splash.set_progress(percent, stage, detail)
        app.processEvents()

    def on_loaded(MainWindow):
        """Called when MainWindow class is loaded"""
        if MainWindow is None:
            splash.set_progress(100, "Startup failed", "The application could not finish launching.")
            splash.finish_with_fade("Error")
            QTimer.singleShot(2000, app.quit)
            return

        splash.set_progress(
            80,
            "Finalizing startup",
            "Creating the main workspace and restoring the window.",
        )
        app.processEvents()

        # Create and show main window
        try:
            window = MainWindow(startup_progress_callback=on_progress)
            if not app.windowIcon().isNull():
                window.setWindowIcon(app.windowIcon())
            # Show window first, then maximize after native HWND is ready
            splash.set_progress(
                99,
                "Opening workspace",
                "Showing the main window and restoring its state.",
            )
            app.processEvents()
            window.show()
            QTimer.singleShot(50, window.showMaximized)
            app.processEvents()

            # Close splash with fade
            splash.set_progress(100, "Workspace ready", "The application is ready.")
            splash.finish_with_fade("Ready")

            # Keep references
            window._startup_splash = splash  # type: ignore[attr-defined]
            app._main_window = window  # type: ignore[attr-defined]
        except Exception as e:
            _log_startup_error("MainWindow init", e)
            splash.set_progress(100, "Startup failed", str(e))
            splash.finish_with_fade("Failed")
            QTimer.singleShot(2000, app.quit)

    # Connect signals
    loader.progress.connect(on_progress)
    loader.loaded.connect(on_loaded)

    def begin_startup() -> None:
        """Finish lightweight startup steps after the splash is visible."""
        try:
            splash.set_progress(
                12,
                "Loading interface resources",
                "Loading bundled fonts and application icons.",
            )
            app.processEvents()

            _load_startup_fonts()
            app.setFont(_startup_ui_font(9))

            window_icon = _startup_app_icon()
            if not window_icon.isNull():
                app.setWindowIcon(window_icon)
                splash.setWindowIcon(window_icon)

            splash.set_progress(
                18,
                "Starting Grain Size Analysis",
                "Preparing the analysis workspace.",
            )
            loader.start()
        except Exception as e:
            _log_startup_error("Startup bootstrap", e)
            splash.set_progress(100, "Startup failed", str(e))
            splash.finish_with_fade("Failed")
            QTimer.singleShot(2000, app.quit)

    # Start remaining setup once the event loop is running.
    QTimer.singleShot(0, begin_startup)

    sys.exit(app.exec())


if __name__ == "__main__":
    mp.freeze_support()
    main()
