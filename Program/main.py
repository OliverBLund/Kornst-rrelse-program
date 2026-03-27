#!/usr/bin/env python3
"""
Grain Size Analysis Program - PyQt6 entry point with startup splash screen.
"""

import sys
import traceback
from datetime import datetime
from pathlib import Path
import tempfile

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont

# Must be set before QApplication is created.
# PassThrough lets Qt (and matplotlib's canvas) use the exact fractional
# device-pixel ratio (e.g. 1.25 for 125% Windows scaling) so matplotlib
# renders at full physical resolution instead of being upscaled → no blur.
QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

from Splash.simple_splash import SimpleSplash
from gui.theme import app_icon, load_fonts
# MainWindow imported later to speed up splash appearance


APP_USER_MODEL_ID = "DTU.GrainSizeAnalysis.Desktop"


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
    finished = pyqtSignal(object)  # Sends the MainWindow class when done
    progress = pyqtSignal(str)     # Progress messages

    def run(self):
        """Load MainWindow in background thread"""
        try:
            self.progress.emit("Loading analysis modules...")

            # Import MainWindow here (loads matplotlib, numpy, pandas, etc.)
            from gui.main_window import MainWindow

            self.progress.emit("Building user interface...")
            self.finished.emit(MainWindow)
        except Exception as e:
            _log_startup_error("LoaderThread", e)
            self.progress.emit(f"Error: {e}")
            self.finished.emit(None)


def main() -> None:
    _set_windows_app_user_model_id(APP_USER_MODEL_ID)
    app = QApplication(sys.argv)
    app.setApplicationName("Grain Size Analysis")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Geotechnical Engineering")
    app.setOrganizationDomain("grainsize.app")

    window_icon = app_icon()
    if not window_icon.isNull():
        app.setWindowIcon(window_icon)

    # Load bundled fonts (Source Sans 3, JetBrains Mono, Playfair Display)
    load_fonts()
    app.setFont(QFont("Source Sans 3", 9))

    # Create and show splash screen IMMEDIATELY (before heavy imports)
    splash = SimpleSplash()
    if not app.windowIcon().isNull():
        splash.setWindowIcon(app.windowIcon())
    splash.set_message("Initializing Grain Size Analysis...")
    splash.show()
    app.processEvents()

    # Create loader thread
    loader = LoaderThread()

    def on_progress(message: str):
        """Update splash with progress messages"""
        splash.set_message(message)
        app.processEvents()

    def on_loaded(MainWindow):
        """Called when MainWindow class is loaded"""
        if MainWindow is None:
            splash.set_message("Startup failed!")
            splash.finish_with_fade("Error")
            QTimer.singleShot(2000, app.quit)
            return

        splash.set_message("Finalizing...")
        app.processEvents()

        # Create and show main window
        try:
            window = MainWindow()
            if not app.windowIcon().isNull():
                window.setWindowIcon(app.windowIcon())
            # Show window first, then maximize after native HWND is ready
            window.show()
            QTimer.singleShot(50, window.showMaximized)
            app.processEvents()

            # Close splash with fade
            splash.finish_with_fade("Ready!")

            # Keep references
            window._startup_splash = splash  # type: ignore[attr-defined]
            app._main_window = window  # type: ignore[attr-defined]
        except Exception as e:
            _log_startup_error("MainWindow init", e)
            splash.set_message(f"Error: {e}")
            splash.finish_with_fade("Failed")
            QTimer.singleShot(2000, app.quit)

    # Connect signals
    loader.progress.connect(on_progress)
    loader.finished.connect(on_loaded)

    # Start loading in background
    QTimer.singleShot(100, loader.start)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
