#!/usr/bin/env python3
"""
Grain Size Analysis Program - PyQt6 entry point with startup splash screen.
"""

import sys

from PyQt6.QtWidgets import QApplication

from Splash.simple_splash import SimpleSplash
from gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Grain Size Analysis")
    app.setApplicationVersion("0.1.0")

    splash = SimpleSplash()
    splash.set_message("Loading Grain Size Analysis...")
    splash.show()
    app.processEvents()

    try:
        splash.set_message("Initializing modules...")
        app.processEvents()
        window = MainWindow()
        splash.set_message("Preparing user interface...")
        app.processEvents()
    except Exception:
        splash.set_message("Startup failed")
        splash.finish_with_fade("Error")
        raise

    window.show()
    app.processEvents()
    splash.finish_with_fade("Ready!")

    # Keep the splash alive until the fade-out animation completes.
    window._startup_splash = splash  # type: ignore[attr-defined]

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
