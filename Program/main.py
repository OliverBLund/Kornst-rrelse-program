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
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from Splash.simple_splash import SimpleSplash
# MainWindow imported later to speed up splash appearance


def _log_startup_error(source: str, exc: Exception) -> None:
    """Write startup exceptions to a temp file for debugging packaged builds."""
    try:
        log_path = Path(tempfile.gettempdir()) / "grain_startup_error.log"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {source}: {exc}\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            f.write("\n")
    except Exception:
        # Best-effort only
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
    app = QApplication(sys.argv)
    app.setApplicationName("Grain Size Analysis")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Geotechnical Engineering")
    app.setOrganizationDomain("grainsize.app")

    # Set a modern default font to avoid DirectWrite warnings with legacy fonts like "MS Sans Serif"
    # This prevents Qt from falling back to problematic legacy Windows fonts
    default_font = QFont("Segoe UI", 9)
    if not default_font.exactMatch():
        # Fallback to other modern fonts if Segoe UI is not available
        for fallback in ["Arial", "Helvetica", "Sans Serif"]:
            default_font = QFont(fallback, 9)
            if default_font.exactMatch():
                break
    app.setFont(default_font)

    # Create and show splash screen IMMEDIATELY (before heavy imports)
    splash = SimpleSplash()
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
            # Show window maximized (fullscreen)
            window.showMaximized()
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
