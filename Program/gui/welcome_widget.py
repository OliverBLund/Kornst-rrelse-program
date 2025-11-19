"""
Enhanced Welcome Widget for Grain Size Analysis
Features recent files, quick help, changelog, and beautiful gradient background
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QCheckBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QFont, QPalette, QLinearGradient, QColor, QBrush, QCursor
from pathlib import Path
from typing import List
import os


class WelcomeWidget(QWidget):
    """Enhanced welcome screen with recent files, help links, and changelog"""

    # Signals
    load_files_requested = pyqtSignal()
    load_sample_data_requested = pyqtSignal()
    open_recent_file_requested = pyqtSignal(str)  # file_path
    open_help_topic_requested = pyqtSignal(str)  # topic name
    dont_show_again_changed = pyqtSignal(bool)

    def __init__(self, recent_files: List[str] = None, parent=None):
        super().__init__(parent)
        self.recent_files = recent_files or []
        self.setup_ui()

    def setup_ui(self):
        """Setup enhanced welcome screen with gradient background"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Set gradient background (soil-brown to water-blue)
        # NOTE: To add visual elements later (particles, textures, images),
        # override paintEvent() and draw them on top of this gradient
        self.setAutoFillBackground(True)
        palette = self.palette()

        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor("#8B7355"))   # Soil brown (top)
        gradient.setColorAt(0.5, QColor("#A0826D"))   # Transition
        gradient.setColorAt(1.0, QColor("#4A90A4"))   # Water blue (bottom)

        palette.setBrush(QPalette.ColorRole.Window, QBrush(gradient))
        self.setPalette(palette)

        # Center container - this will center everything
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.setSpacing(15)

        # === TITLE BOX ===
        title_box = QFrame()
        title_box.setObjectName("titleBox")
        title_box.setStyleSheet("""
            #titleBox {
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                border: 2px solid rgba(255, 255, 255, 0.3);
            }
        """)
        title_box.setMaximumWidth(700)
        title_box_layout = QVBoxLayout(title_box)
        title_box_layout.setContentsMargins(20, 15, 20, 15)
        title_box_layout.setSpacing(5)

        title_label = QLabel("🌾 Grain Size Analysis 🌊")
        title_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: white;")
        title_box_layout.addWidget(title_label)

        subtitle_label = QLabel("Hydraulic Conductivity Calculator")
        subtitle_label.setFont(QFont("Segoe UI", 13))
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: rgba(255,255,255,0.95);")
        title_box_layout.addWidget(subtitle_label)

        version_label = QLabel("Version 2.0.0")
        version_label.setFont(QFont("Segoe UI", 9))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: rgba(255,255,255,0.8);")
        title_box_layout.addWidget(version_label)

        center_layout.addWidget(title_box, 0, Qt.AlignmentFlag.AlignCenter)

        # === MAIN CONTENT CARD ===
        card = QFrame()
        card.setObjectName("mainCard")
        card.setStyleSheet("""
            #mainCard {
                background-color: rgba(255, 255, 255, 0.97);
                border-radius: 10px;
                border: 2px solid rgba(150, 150, 150, 0.2);
            }
        """)
        card.setMaximumWidth(700)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(10)

        # === Grid Layout for sections (2x2) ===
        from PyQt6.QtWidgets import QGridLayout

        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        # Row 1: Recent Files | What's New
        recent_section = self._create_section_box(
            "📂 Recent Files",
            self._create_recent_files_content()
        )
        grid_layout.addWidget(recent_section, 0, 0)

        whats_new_section = self._create_section_box(
            "📝 What's New",
            self._create_whats_new_content()
        )
        grid_layout.addWidget(whats_new_section, 0, 1)

        # Row 2: Quick Help | Quick Actions
        help_section = self._create_section_box(
            "📚 Quick Help",
            self._create_quick_help_content()
        )
        grid_layout.addWidget(help_section, 1, 0)

        actions_section = self._create_section_box(
            "🚀 Quick Actions",
            self._create_quick_actions_content()
        )
        grid_layout.addWidget(actions_section, 1, 1)

        card_layout.addLayout(grid_layout)

        # Don't show again checkbox
        self.dont_show_checkbox = QCheckBox("Don't show this welcome screen on startup")
        self.dont_show_checkbox.setFont(QFont("Segoe UI", 9))
        self.dont_show_checkbox.setStyleSheet("color: #777777; margin-top: 10px;")
        self.dont_show_checkbox.stateChanged.connect(
            lambda state: self.dont_show_again_changed.emit(state == Qt.CheckState.Checked.value)
        )
        card_layout.addWidget(self.dont_show_checkbox)

        center_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)

        # Add center container to main layout
        main_layout.addStretch()
        main_layout.addWidget(center_container)
        main_layout.addStretch()

    def _create_section_box(self, title: str, content_widget: QWidget) -> QFrame:
        """Create a visually separated section box"""
        section = QFrame()
        section.setStyleSheet("""
            QFrame {
                background-color: #f8f8f8;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-bottom: 8px;
            }
        """)
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(12, 10, 12, 10)
        section_layout.setSpacing(8)

        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #333333; background: transparent; border: none;")
        section_layout.addWidget(title_label)

        # Content
        section_layout.addWidget(content_widget)

        return section

    def _create_recent_files_content(self) -> QWidget:
        """Create recent files content"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if self.recent_files:
            for file_path in self.recent_files[:5]:
                # Create a container for each file
                file_container = QWidget()
                file_container.setStyleSheet("""
                    QWidget {
                        background: transparent;
                        border: none;
                    }
                    QWidget:hover {
                        background-color: rgba(0, 120, 212, 0.08);
                        border-radius: 3px;
                    }
                """)
                file_container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

                file_layout = QVBoxLayout(file_container)
                file_layout.setContentsMargins(8, 6, 8, 6)
                file_layout.setSpacing(2)

                # File name
                file_name_label = QLabel(f"📄 {Path(file_path).name}")
                file_name_label.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
                file_name_label.setStyleSheet("color: #0078d4; background: transparent; border: none;")
                file_layout.addWidget(file_name_label)

                # File path (smaller, gray)
                file_path_label = QLabel(str(Path(file_path).parent))
                file_path_label.setFont(QFont("Segoe UI", 8))
                file_path_label.setStyleSheet("color: #666666; background: transparent; border: none;")
                file_path_label.setWordWrap(False)
                file_path_label.setMaximumWidth(250)
                from PyQt6.QtCore import Qt as QtCore
                file_path_label.setTextFormat(QtCore.TextFormat.PlainText)
                # Truncate if too long
                if len(str(Path(file_path).parent)) > 40:
                    truncated = "..." + str(Path(file_path).parent)[-37:]
                    file_path_label.setText(truncated)
                file_layout.addWidget(file_path_label)

                # Make clickable
                file_container.mousePressEvent = lambda event, fp=file_path: self.open_recent_file_requested.emit(fp)

                layout.addWidget(file_container)
        else:
            no_files = QLabel("No recent files")
            no_files.setFont(QFont("Segoe UI", 9))
            no_files.setStyleSheet("color: #999999; font-style: italic; background: transparent; border: none; padding: 10px;")
            no_files.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_files)

        layout.addStretch()
        return widget

    def _create_quick_help_content(self) -> QWidget:
        """Create quick help content"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        help_topics = [
            ("Getting Started", "getting_started.html"),
            ("File Formats", "file_formats.html"),
            ("Methods Overview", "methods_overview.html"),
            ("Troubleshooting", "troubleshooting.html")
        ]

        for topic_name, topic_file in help_topics:
            topic_btn = QPushButton(topic_name)
            topic_btn.setFont(QFont("Segoe UI", 9))
            topic_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            topic_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #0078d4;
                    border-radius: 3px;
                    padding: 4px 10px;
                    color: #0078d4;
                }
                QPushButton:hover {
                    background-color: rgba(0, 120, 212, 0.08);
                }
            """)
            topic_btn.clicked.connect(lambda checked, tf=topic_file: self.open_help_topic_requested.emit(tf))
            layout.addWidget(topic_btn)

        layout.addStretch()
        return widget

    def _create_quick_actions_content(self) -> QWidget:
        """Create quick actions content"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Load Files button
        load_btn = QPushButton("📁 Load Files")
        load_btn.setMinimumHeight(40)
        load_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        load_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        load_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #006cc1;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        load_btn.clicked.connect(self.load_files_requested.emit)
        layout.addWidget(load_btn)

        # Load Sample button
        sample_btn = QPushButton("📊 Load Sample Data")
        sample_btn.setMinimumHeight(40)
        sample_btn.setFont(QFont("Segoe UI", 10))
        sample_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        sample_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #333333;
                border: 2px solid #cccccc;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                border-color: #0078d4;
                color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #f0f0f0;
            }
        """)
        sample_btn.clicked.connect(self.load_sample_data_requested.emit)
        layout.addWidget(sample_btn)

        return widget

    def _create_whats_new_content(self) -> QWidget:
        """Create what's new content"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        changelog_items = [
            "New export tab with live data preview",
            "Wide format CSV export for statistical analysis",
            "Enhanced calculation methods"
        ]

        for item in changelog_items:
            item_label = QLabel(f"  • {item}")
            item_label.setFont(QFont("Segoe UI", 9))
            item_label.setStyleSheet("color: #555555; background: transparent; border: none;")
            item_label.setWordWrap(True)
            layout.addWidget(item_label)

        return widget


    def update_recent_files(self, recent_files: List[str]):
        """Update the recent files list"""
        self.recent_files = recent_files
        # Rebuild UI to refresh the list
        # Clear and rebuild
        while self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.setup_ui()
