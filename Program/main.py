#!/usr/bin/env python3
"""
Grain Size Analysis Program - PyQt6 Prototype
Main application entry point
"""

import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Grain Size Analysis")
    app.setApplicationVersion("0.1.0")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
