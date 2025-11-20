#!/usr/bin/env python3
"""
Grain Size Analysis Program - PyQt6 entry point with startup splash screen.
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from Splash.simple_splash import SimpleSplash
from gui.main_window import MainWindow


def main() -> None:
    # Close PyInstaller's native splash screen if present
    try:
        import pyi_splash  # type: ignore
        pyi_splash.close()
    except ImportError:
        pass  # Not running as PyInstaller bundle

    app = QApplication(sys.argv)
    app.setApplicationName("Grain Size Analysis")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Geotechnical Engineering")
    app.setOrganizationDomain("grainsize.app")

    # Create and show splash screen
    splash = SimpleSplash()
    splash.set_message("Initializing Grain Size Analysis...")
    splash.show()
    app.processEvents()

    # Initialize main window in stages with progress updates
    def init_step_1():
        """Load core modules"""
        splash.set_message("Loading analysis modules...")
        app.processEvents()
        QTimer.singleShot(100, init_step_2)

    def init_step_2():
        """Create main window"""
        try:
            splash.set_message("Building user interface...")
            app.processEvents()

            global window
            window = MainWindow()

            QTimer.singleShot(100, init_step_3)
        except Exception as e:
            splash.set_message("Startup failed")
            splash.finish_with_fade("Error")
            raise

    def init_step_3():
        """Finalize and show window"""
        splash.set_message("Finalizing...")
        app.processEvents()

        # Show main window
        window.show()
        app.processEvents()

        # Close splash with fade
        splash.finish_with_fade("Ready!")

        # Keep splash reference to prevent garbage collection during fade
        window._startup_splash = splash  # type: ignore[attr-defined]

    # Start initialization sequence
    QTimer.singleShot(50, init_step_1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
