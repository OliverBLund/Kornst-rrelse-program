"""
Enhanced Welcome Widget for Grain Size Analysis
Features recent files, quick help, changelog, and beautiful gradient background
"""

import os
from pathlib import Path
from typing import List

from PyQt6.QtCore import QRect, QSettings, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPalette,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class WelcomeWidget(QWidget):
    """Enhanced welcome screen with recent files, help links, and changelog"""

    # Signals
    load_files_requested = pyqtSignal()
    load_sample_data_requested = pyqtSignal()
    open_recent_file_requested = pyqtSignal(str)  # file_path
    open_help_topic_requested = pyqtSignal(str)  # topic name
    dont_show_again_changed = pyqtSignal(bool)
    clear_sessions_requested = pyqtSignal()

    def __init__(self, recent_files: List[str] = None, parent=None):
        super().__init__(parent)
        self.recent_files = recent_files or []
        self.setup_ui()

    def paintEvent(self, event: QPaintEvent):
        """Custom paint event to draw background image or gradient"""
        painter = QPainter(self)

        # Try to load background image
        import os
        import sys

        # Get resource path (works for both script and PyInstaller bundle)
        def get_resource_path(relative_path):
            """Get absolute path to resource, works for dev and for PyInstaller"""
            try:
                # PyInstaller creates a temp folder and stores path in _MEIPASS
                base_path = sys._MEIPASS
            except AttributeError:
                # In dev mode, go up from gui/ to Program/
                base_path = os.path.dirname(os.path.dirname(__file__))
            return os.path.join(base_path, relative_path)

        # In PyInstaller: sys._MEIPASS/Program/resources/soil_layers.png
        # In dev mode: Program/resources/soil_layers.png
        if hasattr(sys, '_MEIPASS'):
            image_path = get_resource_path(os.path.join("Program", "resources", "soil_layers.png"))
        else:
            image_path = get_resource_path(os.path.join("resources", "soil_layers.png"))

        if os.path.exists(image_path):
            # Load and draw background image (scaled to fit)
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Scale the image to fit within the widget without cropping
                scaled_pixmap = pixmap.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

                # Center the scaled image
                x = (self.width() - scaled_pixmap.width()) // 2
                y = (self.height() - scaled_pixmap.height()) // 2
                painter.drawPixmap(x, y, scaled_pixmap)

                # Add a stronger semi-transparent overlay for better text readability
                overlay = QColor(255, 255, 255, 120)  # White with 120/255 opacity
                painter.fillRect(self.rect(), overlay)
            else:
                # Image failed to load, use gradient
                self._draw_gradient_background(painter)
        else:
            # No image found, use gradient
            self._draw_gradient_background(painter)

        super().paintEvent(event)

    def _draw_gradient_background(self, painter: QPainter):
        """Draw gradient background (soil-brown to water-blue)"""
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor("#8B7355"))  # Soil brown (top)
        gradient.setColorAt(0.5, QColor("#A0826D"))  # Transition
        gradient.setColorAt(1.0, QColor("#4A90A4"))  # Water blue (bottom)
        painter.fillRect(self.rect(), gradient)

    def setup_ui(self):
        """Setup enhanced welcome screen with background image and gradient overlay"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Image attribution label (bottom left corner)
        attribution_label = QLabel("Background generated using Sora from OpenAI")
        attribution_label.setStyleSheet("""
            QLabel {
                font-size: 9px;
                color: rgba(80, 80, 80, 200);
                background-color: rgba(255, 255, 255, 140);
                padding: 5px 10px;
                border-radius: 4px;
            }
        """)
        attribution_label.setFixedHeight(22)
        attribution_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

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

        title_label = QLabel("Grain Size Analysis")
        title_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: black;")
        title_box_layout.addWidget(title_label)

        subtitle_label = QLabel("Hydraulic Conductivity Calculator")
        subtitle_label.setFont(QFont("Segoe UI", 13))
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: black;")
        title_box_layout.addWidget(subtitle_label)

        version_label = QLabel("Version 0.9.0-beta")
        version_label.setFont(QFont("Segoe UI", 9))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: black;")
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
            "📂 Recent Sessions",
            self._create_recent_files_content(),
            show_clear_button=True,  # Add clear button for sessions
        )
        grid_layout.addWidget(recent_section, 0, 0)

        whats_new_section = self._create_section_box(
            "📝 What's New", self._create_whats_new_content()
        )
        grid_layout.addWidget(whats_new_section, 0, 1)

        # Row 2: Quick Help | Quick Actions
        help_section = self._create_section_box(
            "📚 Quick Help", self._create_quick_help_content()
        )
        grid_layout.addWidget(help_section, 1, 0)

        actions_section = self._create_section_box(
            "🚀 Quick Actions", self._create_quick_actions_content()
        )
        grid_layout.addWidget(actions_section, 1, 1)

        card_layout.addLayout(grid_layout)

        # Don't show again checkbox
        self.dont_show_checkbox = QCheckBox("Don't show this welcome screen on startup")
        self.dont_show_checkbox.setFont(QFont("Segoe UI", 9))
        self.dont_show_checkbox.setStyleSheet("color: #777777; margin-top: 10px;")
        self.dont_show_checkbox.stateChanged.connect(
            lambda state: self.dont_show_again_changed.emit(
                state == Qt.CheckState.Checked.value
            )
        )
        card_layout.addWidget(self.dont_show_checkbox)

        center_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)

        # Add center container to main layout
        main_layout.addStretch()
        main_layout.addWidget(center_container)
        main_layout.addStretch()

        # Add attribution at bottom left
        attribution_container = QWidget()
        attribution_container.setStyleSheet("background-color: transparent;")
        attribution_layout = QHBoxLayout(attribution_container)
        attribution_layout.setContentsMargins(10, 0, 0, 10)
        attribution_layout.addWidget(attribution_label)
        attribution_layout.addStretch()

        main_layout.addWidget(attribution_container)

    def _create_section_box(
        self, title: str, content_widget: QWidget, show_clear_button: bool = False
    ) -> QFrame:
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

        # Title row (with optional clear button)
        title_row = QWidget()
        title_row.setStyleSheet("background: transparent; border: none;")
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.setSpacing(8)

        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_label.setStyleSheet(
            "color: #333333; background: transparent; border: none;"
        )
        title_row_layout.addWidget(title_label)
        title_row_layout.addStretch()

        # Add clear button if requested
        if show_clear_button:
            clear_btn = QPushButton("Clear")
            clear_btn.setFont(QFont("Segoe UI", 8))
            clear_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    padding: 2px 8px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
            """)
            clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            clear_btn.clicked.connect(self.clear_sessions_requested.emit)
            title_row_layout.addWidget(clear_btn)

        section_layout.addWidget(title_row)

        # Content
        section_layout.addWidget(content_widget)

        return section

    def _create_recent_files_content(self) -> QWidget:
        """Create recent sessions content (groups of files loaded together)"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Load recent sessions from settings
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        recent_sessions = settings.value("recent_sessions", [])

        if not isinstance(recent_sessions, list):
            recent_sessions = []

        if recent_sessions:
            for session in recent_sessions[:5]:  # Show max 5 sessions
                # Create a container for each session
                session_container = QWidget()
                session_container.setStyleSheet("""
                    QWidget {
                        background: transparent;
                        border: none;
                    }
                    QWidget:hover {
                        background-color: rgba(0, 120, 212, 0.08);
                        border-radius: 3px;
                    }
                """)
                session_container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

                session_layout = QVBoxLayout(session_container)
                session_layout.setContentsMargins(8, 6, 8, 6)
                session_layout.setSpacing(2)

                # Session name/date
                session_name = session.get("name", "Unnamed Session")
                session_date = session.get("date", "")
                session_files = session.get("files", [])

                session_name_label = QLabel(f"📁 {session_name}")
                session_name_label.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
                session_name_label.setStyleSheet(
                    "color: #0078d4; background: transparent; border: none;"
                )
                session_layout.addWidget(session_name_label)

                # Session info (file count + date)
                file_count = len(session_files)
                info_text = f"{file_count} file{'s' if file_count != 1 else ''}"
                if session_date:
                    info_text += f" • {session_date}"

                session_info_label = QLabel(info_text)
                session_info_label.setFont(QFont("Segoe UI", 8))
                session_info_label.setStyleSheet(
                    "color: #666666; background: transparent; border: none;"
                )
                session_layout.addWidget(session_info_label)

                # Make clickable - emit files list
                session_container.mousePressEvent = (
                    lambda event, files=session_files: self._load_session_files(files)
                )

                layout.addWidget(session_container)
        else:
            no_sessions = QLabel("No recent sessions")
            no_sessions.setFont(QFont("Segoe UI", 9))
            no_sessions.setStyleSheet(
                "color: #999999; font-style: italic; background: transparent; border: none; padding: 10px;"
            )
            no_sessions.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_sessions)

        layout.addStretch()
        return widget

    def _load_session_files(self, files: List[str]):
        """Load all files from a session"""
        for file_path in files:
            if os.path.exists(file_path):
                self.open_recent_file_requested.emit(file_path)

    def _create_quick_help_content(self) -> QWidget:
        """Create quick help content with 2x2 grid for better spacing"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QGridLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        help_topics = [
            ("Getting Started", "getting_started.html"),
            ("File Formats", "file_formats.html"),
            ("Methods Overview", "methods_overview.html"),
            ("Troubleshooting", "troubleshooting.html"),
        ]

        # Arrange in 2x2 grid
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]

        for (topic_name, topic_file), (row, col) in zip(help_topics, positions):
            topic_btn = QPushButton(topic_name)
            topic_btn.setFont(QFont("Segoe UI", 8))
            topic_btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            topic_btn.setMinimumHeight(28)
            topic_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            topic_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #0078d4;
                    border-radius: 3px;
                    padding: 4px 8px;
                    color: #0078d4;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: rgba(0, 120, 212, 0.08);
                }
            """)
            topic_btn.clicked.connect(
                lambda checked, tf=topic_file: self.open_help_topic_requested.emit(tf)
            )
            layout.addWidget(topic_btn, row, col)

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
        """Create what's new content with scrollable changelog"""
        from PyQt6.QtWidgets import QScrollArea

        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Scrollable area for changelog - takes all available space
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
        """)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(5, 0, 5, 0)
        scroll_layout.setSpacing(10)

        # Version entries (fake data for now)
        versions = [
            {
                "version": "v0.9.0-beta",
                "date": "2025-01-15",
                "changes": [
                    "New export tab with live data preview",
                    "Wide format CSV export for statistical analysis",
                    "Enhanced welcome screen with recent files",
                ],
            },
            {
                "version": "v1.9.0-alpha",
                "date": "2024-12-20",
                "changes": [
                    "Added comparison tab for multiple datasets",
                    "Improved calculation methods validation",
                    "Bug fixes for column mapping",
                ],
            },
            {
                "version": "v1.8.0-alpha",
                "date": "2024-11-30",
                "changes": [
                    "New help system with comprehensive guides",
                    "Enhanced reporting tab with templates",
                    "Performance improvements for large datasets",
                ],
            },
            {
                "version": "v1.7.0-alpha",
                "date": "2024-11-10",
                "changes": [
                    "Added statistics tab with grain analysis",
                    "Improved porosity calculation methods",
                    "New plot customization options",
                ],
            },
            {
                "version": "v1.6.0-alpha",
                "date": "2024-10-25",
                "changes": [
                    "Initial K-calculation implementation",
                    "Support for multiple empirical methods",
                    "Basic data import and visualization",
                ],
            },
        ]

        for ver in versions:
            # Version header
            version_header = QLabel(f"🔹 {ver['version']} ({ver['date']})")
            version_header.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            version_header.setStyleSheet(
                "color: #2c3e50; background: transparent; border: none;"
            )
            scroll_layout.addWidget(version_header)

            # Changes
            for change in ver["changes"]:
                change_label = QLabel(f"    • {change}")
                change_label.setFont(QFont("Segoe UI", 8))
                change_label.setStyleSheet(
                    "color: #555555; background: transparent; border: none;"
                )
                change_label.setWordWrap(True)
                scroll_layout.addWidget(change_label)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)  # Stretch factor 1 - takes all available space

        # Full changelog button - fixed size
        changelog_btn = QPushButton("📖 View Full Changelog")
        changelog_btn.setFont(QFont("Segoe UI", 8))
        changelog_btn.setFixedHeight(28)
        changelog_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        changelog_btn.setStyleSheet("""
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
        changelog_btn.clicked.connect(self._open_full_changelog)
        main_layout.addWidget(changelog_btn, 0)  # Stretch factor 0 - fixed size

        return widget

    def _open_full_changelog(self):
        """Open the full changelog file"""
        import os

        # Try to find CHANGELOG.md
        changelog_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "CHANGELOG.md"
        )

        if os.path.exists(changelog_path):
            # Open in default text editor
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl.fromLocalFile(changelog_path))
        else:
            # Show message with changelog location info
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "Changelog",
                f"Full changelog will be available at:\n{changelog_path}\n\nCurrently in development.",
            )

    def update_recent_files(self, recent_files: List[str]):
        """Update the recent files list - just store them, don't rebuild UI"""
        self.recent_files = recent_files
        # Don't rebuild the entire UI - it causes QLayout errors
        # The welcome screen will refresh when it's shown next time
