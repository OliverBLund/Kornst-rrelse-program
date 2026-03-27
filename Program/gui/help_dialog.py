"""
Help dialog with navigation and HTML content browser
"""

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTextBrowser,
    QPushButton, QLineEdit, QWidget, QLabel
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QDesktopServices
import os
from gui.dialog_chrome import make_dialog_header, make_dialog_footer
from gui.theme import C, F, SZ, icon as _icon
from qt_chrome.frameless_dialog_base import FramelessDialogBase


class HelpDialog(FramelessDialogBase):
    """Professional help dialog with navigation and rich HTML content"""

    def __init__(self, parent=None):
        super().__init__(parent, default_mode="auto")
        self.setWindowTitle("Grain Size Analysis - Help & Documentation")
        self.resize(1000, 700)

        # Center on screen
        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - 1000) // 2
            y = parent_geo.y() + (parent_geo.height() - 700) // 2
            self.move(x, y)

        # Get help content directory (works for both dev and PyInstaller)
        import sys
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
            self.help_dir = os.path.join(base_path, "Program", "help_content")
        except AttributeError:
            # In dev mode
            self.help_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "help_content")

        self.setup_ui()
        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=8,
        )
        self.load_help_topics()

        # Show getting started by default
        self.show_help_page("getting_started.html")

    def setup_ui(self):
        """Setup the help dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tree + browser inherit global stylesheet; only patch specifics
        self.setStyleSheet(
            f"QTreeWidget {{ background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; "
            f"font-size: {F.SZ_MD}pt; padding: 4px; }}"
            f"QTreeWidget::item {{ padding: 5px; border-radius: {SZ.BORDER_RADIUS}px; }}"
            f"QTreeWidget::item:selected {{ background: {C.OLIVE}; color: white; }}"
            f"QTreeWidget::item:hover {{ background: {C.BG_LOW}; }}"
            f"QTextBrowser {{ background: white; border: 1px solid {C.BORDER}; "
            f"padding: 20px; font-size: {F.SZ_MD}pt; }}"
        )

        # ── Header ────────────────────────────────────────────────────────
        # The header also hosts the search box in an extra row below
        header_outer = QWidget()
        header_outer.setObjectName("helpHeaderOuter")
        header_outer.setStyleSheet(
            f"QWidget#helpHeaderOuter {{ background: {C.BG_RAISED}; "
            f"border-bottom: 1px solid {C.BORDER}; }}"
        )
        ho_lay = QVBoxLayout(header_outer)
        ho_lay.setContentsMargins(0, 0, 0, 0)
        ho_lay.setSpacing(0)

        _inner_header = make_dialog_header(
            "Help & Documentation",
            "Grain-size analysis · K-calculation methods · reference guide",
            fa_icon="fa6s.circle-question",
            close_fn=self.accept,
        )
        _inner_header.setStyleSheet("")   # let outer widget supply bg
        ho_lay.addWidget(_inner_header)
        # Expose outer container as header for drag purposes
        self._header_widget = header_outer

        # Search strip below title row
        search_strip = QWidget()
        search_strip.setStyleSheet(
            f"background: {C.BG_LOW}; border-top: 1px solid {C.BORDER};"
        )
        ss_lay = QHBoxLayout(search_strip)
        ss_lay.setContentsMargins(14, 6, 14, 6)
        ss_lay.setSpacing(6)

        srch_ic = QLabel()
        try:
            srch_ic.setPixmap(_icon("fa6s.magnifying-glass", C.TEXT_MUTED).pixmap(11, 11))
        except Exception:
            srch_ic.setText("🔍")
        srch_ic.setStyleSheet("background: transparent;")
        ss_lay.addWidget(srch_ic)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search help topics…")
        self.search_box.setFixedHeight(26)
        self.search_box.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,255,255,.7); border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; font-size: {F.SZ_MD}pt; "
            f"color: {C.TEXT}; padding: 0 8px; }}"
            f"QLineEdit:focus {{ border-color: {C.OLIVE}; background: white; }}"
        )
        self.search_box.textChanged.connect(self.on_search_text_changed)
        ss_lay.addWidget(self.search_box, 1)

        self.clear_search_btn = QPushButton("Clear")
        self.clear_search_btn.setFixedHeight(26)
        self.clear_search_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
            f"background: {C.BG}; color: {C.TEXT_MID}; padding: 0 10px; "
            f"font-size: {F.SZ_SM}pt; }}"
            f"QPushButton:hover {{ background: {C.BG_RAISED}; border-color: {C.BORDER_DK}; }}"
        )
        self.clear_search_btn.clicked.connect(self.clear_search)
        ss_lay.addWidget(self.clear_search_btn)

        ho_lay.addWidget(search_strip)
        layout.addWidget(header_outer)

        # ── Main content area ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.nav_tree = QTreeWidget()
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setMaximumWidth(300)
        self.nav_tree.setMinimumWidth(250)
        self.nav_tree.itemClicked.connect(self.on_topic_clicked)

        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(False)
        self.content_browser.anchorClicked.connect(self.on_link_clicked)
        self.content_browser.setSearchPaths([self.help_dir, os.path.join(self.help_dir, "images")])

        splitter.addWidget(self.nav_tree)
        splitter.addWidget(self.content_browser)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

        # ── Footer ────────────────────────────────────────────────────────
        layout.addWidget(make_dialog_footer([
            ("Close", self.accept, "secondary"),
        ]))

    def load_help_topics(self):
        """Populate the navigation tree with help topics"""
        # Getting Started
        getting_started = QTreeWidgetItem(self.nav_tree, ["Getting Started"])
        getting_started.setData(0, Qt.ItemDataRole.UserRole, "getting_started.html")

        # File Formats
        file_formats = QTreeWidgetItem(self.nav_tree, ["File Formats"])
        file_formats.setData(0, Qt.ItemDataRole.UserRole, "file_formats.html")

        # Parameters Guide
        parameters = QTreeWidgetItem(self.nav_tree, ["Parameters Guide"])
        parameters.setData(0, Qt.ItemDataRole.UserRole, "parameters.html")

        # K-Calculation Methods
        methods = QTreeWidgetItem(self.nav_tree, ["K-Calculation Methods"])
        methods.setData(0, Qt.ItemDataRole.UserRole, "methods_overview.html")

        # Add individual methods as children
        method_list = [
            ("Hazen", "method_hazen.html"),
            ("Terzaghi", "method_terzaghi.html"),
            ("Beyer", "method_beyer.html"),
            ("Slichter", "method_slichter.html"),
            ("Kozeny-Carman", "method_kozeny_carman.html"),
            ("Shepherd", "method_shepherd.html"),
            ("USBR", "method_usbr.html"),
            ("Zunker", "method_zunker.html"),
            ("Zamarin", "method_zamarin.html"),
            ("Sauerbrei", "method_sauerbrei.html"),
            ("Kruger", "method_kruger.html"),
            ("Barr", "method_barr.html"),
            ("Alyamani-Sen", "method_alyamani_sen.html"),
            ("Chapuis", "method_chapuis.html"),
        ]

        for method_name, file_name in method_list:
            child = QTreeWidgetItem(methods, [f"  • {method_name}"])
            child.setData(0, Qt.ItemDataRole.UserRole, file_name)

        methods.setExpanded(False)  # Collapsed by default

        # Understanding Results
        results = QTreeWidgetItem(self.nav_tree, ["Understanding Results"])
        results.setData(0, Qt.ItemDataRole.UserRole, "results.html")

        # Troubleshooting
        troubleshooting = QTreeWidgetItem(self.nav_tree, ["Troubleshooting"])
        troubleshooting.setData(0, Qt.ItemDataRole.UserRole, "troubleshooting.html")

        # About
        about = QTreeWidgetItem(self.nav_tree, ["About & References"])
        about.setData(0, Qt.ItemDataRole.UserRole, "about.html")

        # Select first item
        self.nav_tree.setCurrentItem(getting_started)

    def on_topic_clicked(self, item, column):
        """Handle topic selection in navigation tree"""
        file_name = item.data(0, Qt.ItemDataRole.UserRole)
        if file_name:
            self.show_help_page(file_name)

    def on_link_clicked(self, url):
        """Handle internal and external links"""
        url_str = url.toString()

        if url_str.startswith("http://") or url_str.startswith("https://"):
            # External link - open in browser
            QDesktopServices.openUrl(url)
        elif url_str.endswith(".html"):
            # Internal help page link
            self.show_help_page(url_str)
        else:
            # Anchor within page
            self.content_browser.setSource(url)

    def show_help_page(self, file_name):
        """Load and display a help page"""
        file_path = os.path.join(self.help_dir, file_name)

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()

                # Apply consistent styling
                styled_html = self.apply_help_styling(html_content)
                self.content_browser.setHtml(styled_html)

            except Exception as e:
                self.show_error_page(f"Error loading help page: {str(e)}")
        else:
            # Page doesn't exist yet - show placeholder
            self.show_placeholder_page(file_name)

    def apply_help_styling(self, html_content):
        """Apply consistent CSS styling to help content"""
        css = """
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
            }
            h1 {
                color: #5d4e37;
                border-bottom: 3px solid #6b8e23;
                padding-bottom: 10px;
                margin-top: 20px;
            }
            h2 {
                color: #6b8e23;
                margin-top: 30px;
                border-left: 4px solid #6b8e23;
                padding-left: 12px;
            }
            h3 {
                color: #8b7355;
                margin-top: 20px;
            }
            code {
                background-color: #f5f5f0;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
            }
            pre {
                background-color: #f5f5f0;
                border: 1px solid #d4c4a8;
                border-radius: 4px;
                padding: 12px;
                overflow-x: auto;
            }
            pre code {
                background-color: transparent;
                padding: 0;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
            }
            th {
                background-color: #6b8e23;
                color: white;
                padding: 10px;
                text-align: left;
                font-weight: bold;
            }
            td {
                border: 1px solid #d4c4a8;
                padding: 8px;
            }
            tr:nth-child(even) {
                background-color: #fafaf7;
            }
            .note {
                background-color: #fffbcc;
                border-left: 4px solid #f39c12;
                padding: 12px;
                margin: 20px 0;
            }
            .warning {
                background-color: #ffe6e6;
                border-left: 4px solid #e74c3c;
                padding: 12px;
                margin: 20px 0;
            }
            .tip {
                background-color: #e6f7ff;
                border-left: 4px solid #2196F3;
                padding: 12px;
                margin: 20px 0;
            }
            a {
                color: #6b8e23;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            ul {
                line-height: 1.8;
            }
            .formula {
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                padding: 15px;
                margin: 15px 0;
                font-family: 'Courier New', monospace;
                text-align: center;
                font-size: 1.1em;
            }
        </style>
        """

        return css + html_content

    def show_placeholder_page(self, file_name):
        """Show placeholder for help pages that don't exist yet"""
        html = f"""
        <h1>📝 Coming Soon</h1>
        <p>This help page (<code>{file_name}</code>) is currently being written.</p>
        <p>In the meantime, you can:</p>
        <ul>
            <li>Check the <a href="getting_started.html">Getting Started</a> guide</li>
            <li>Refer to the README.md in the program directory</li>
            <li>Contact support for assistance</li>
        </ul>
        """
        self.content_browser.setHtml(self.apply_help_styling(html))

    def show_error_page(self, error_message):
        """Show error page when content can't be loaded"""
        html = f"""
        <h1>⚠️ Error Loading Help</h1>
        <p>{error_message}</p>
        <p>Please check that the help files are installed correctly.</p>
        """
        self.content_browser.setHtml(self.apply_help_styling(html))

    def on_search_text_changed(self, text):
        """Handle search text changes"""
        if not text or len(text) < 2:
            # Clear search highlighting
            return

        # Perform search
        self.search_help_content(text)

    def search_help_content(self, search_text):
        """Search through all help files and show results"""
        if not search_text or len(search_text) < 2:
            return

        search_text = search_text.lower()
        results = []

        # Define all help files to search
        help_files = {
            "Getting Started": "getting_started.html",
            "File Formats": "file_formats.html",
            "Parameters Guide": "parameters.html",
            "K-Calculation Methods": "methods_overview.html",
            "Understanding Results": "results.html",
            "Troubleshooting": "troubleshooting.html",
            "About & References": "about.html",
        }

        # Search through each file
        for title, filename in help_files.items():
            file_path = os.path.join(self.help_dir, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Remove HTML tags for searching
                    import re
                    text_content = re.sub('<[^<]+?>', '', content).lower()

                    if search_text in text_content:
                        # Find context around match
                        index = text_content.find(search_text)
                        start = max(0, index - 50)
                        end = min(len(text_content), index + len(search_text) + 50)
                        context = text_content[start:end].strip()

                        results.append({
                            'title': title,
                            'filename': filename,
                            'context': context
                        })
                except Exception:
                    continue

        # Show search results
        self.show_search_results(search_text, results)

    def show_search_results(self, search_text, results):
        """Display search results in content browser"""
        if not results:
            html = f"""
            <h1>Search Results</h1>
            <p>No results found for "<strong>{search_text}</strong>"</p>
            <p>Try:</p>
            <ul>
                <li>Using different keywords</li>
                <li>Checking spelling</li>
                <li>Using fewer or more general terms</li>
            </ul>
            """
        else:
            html = f"""
            <h1>Search Results</h1>
            <p>Found <strong>{len(results)}</strong> result(s) for "<strong>{search_text}</strong>"</p>
            """

            for result in results:
                html += f"""
                <div style="margin: 20px 0; padding: 15px; background-color: #fafaf7; border-left: 4px solid #6b8e23;">
                    <h3 style="margin-top: 0;">
                        <a href="{result['filename']}" style="color: #6b8e23; text-decoration: none;">
                            {result['title']}
                        </a>
                    </h3>
                    <p style="color: #666; font-size: 0.9em;">...{result['context']}...</p>
                </div>
                """

        self.content_browser.setHtml(self.apply_help_styling(html))

    def clear_search(self):
        """Clear search and return to current topic"""
        self.search_box.clear()
        # Return to currently selected topic
        current_item = self.nav_tree.currentItem()
        if current_item:
            file_name = current_item.data(0, Qt.ItemDataRole.UserRole)
            if file_name:
                self.show_help_page(file_name)
