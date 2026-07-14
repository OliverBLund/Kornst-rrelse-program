"""
Help dialog with structured navigation and HTML content browser.
"""

from html import escape
import re

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


HELP_TOPIC_SECTIONS = [
    (
        "Start Here",
        [
            ("Getting Started", "start_here.html", "fa6s.circle-play"),
            ("Data Format & Files", "data_files.html", "fa6s.file-lines"),
            ("Excel Workbooks", "excel_workbooks.html", "fa6s.file-excel"),
            ("Mapping & Recovery", "mapping_recovery.html", "fa6s.table-columns"),
        ],
    ),
    (
        "Use The App",
        [
            ("Workspace Tour", "workspace_tour.html", "fa6s.compass"),
            ("Analysis Parameters", "analysis_parameters.html", "fa6s.sliders"),
            ("Common Issues", "common_issues.html", "fa6s.screwdriver-wrench"),
        ],
    ),
    (
        "Tabs & Subtabs",
        [
            ("Individual Samples Tab", "individual_samples_tab.html", "fa6s.chart-area"),
            ("Comparison Tab", "comparison_tab.html", "fa6s.code-compare"),
            ("Reports Tab", "reports_tab.html", "fa6s.file-lines"),
            ("Export Tab", "export_tab.html", "fa6s.file-export"),
        ],
    ),
    (
        "Reference",
        [
            ("Methods Overview", "methods_reference.html", "fa6s.flask"),
            ("Hazen", "method_hazen.html", "fa6s.droplet"),
            ("Terzaghi", "method_terzaghi.html", "fa6s.droplet"),
            ("Beyer", "method_beyer.html", "fa6s.droplet"),
            ("Kozeny-Carman", "method_kozeny_carman.html", "fa6s.droplet"),
            ("Shepherd", "method_shepherd.html", "fa6s.droplet"),
            ("About & References", "about_reference.html", "fa6s.book-open"),
            ("Release Notes", "changelog.html", "fa6s.clock-rotate-left"),
        ],
    ),
]

VIRTUAL_HELP_TOPICS = {"changelog.html"}


class HelpDialog(FramelessDialogBase):
    """Professional help dialog with navigation and rich HTML content"""

    def __init__(self, parent=None):
        super().__init__(parent, default_mode="auto")
        self.setWindowTitle("Grain Size Analysis - Help & Documentation")
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(1040, 730)

        # Center on screen
        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - 1040) // 2
            y = parent_geo.y() + (parent_geo.height() - 730) // 2
            self.move(x, y)

        # Get help content directory (works for both dev and PyInstaller)
        import sys
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
            self.program_dir = os.path.join(base_path, "Program")
            self.help_dir = os.path.join(self.program_dir, "help_content")
        except AttributeError:
            # In dev mode
            self.program_dir = os.path.dirname(os.path.dirname(__file__))
            self.help_dir = os.path.join(self.program_dir, "help_content")

        self.topic_items = {}
        self.current_help_page = None

        self.setup_ui()
        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=8,
        )
        self.load_help_topics()

        # Show the getting-started page by default
        self.show_help_page("start_here.html")

    def setup_ui(self):
        """Setup the help dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tree + browser inherit global stylesheet; only patch specifics
        self.setStyleSheet(
            f"QTreeWidget {{ background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; "
            f"font-size: {F.SZ_MD}pt; padding: 6px; }}"
            f"QTreeWidget::item {{ padding: 6px 8px; border-radius: {SZ.BORDER_RADIUS}px; }}"
            f"QTreeWidget::item:selected {{ background: rgba(107,142,35,.10); color: {C.TEXT}; }}"
            f"QTreeWidget::item:hover {{ background: {C.BG_LOW}; }}"
            f"QTextBrowser {{ background: #fcfaf6; border: 1px solid {C.BORDER}; "
            f"padding: 22px; font-size: {F.SZ_MD}pt; }}"
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
        _header_labels = _inner_header.findChildren(QLabel)
        if len(_header_labels) >= 2:
            _header_labels[1].setText(
                "Onboarding, data mapping, workflow guidance, and reference pages"
            )
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
        if srch_ic.pixmap() is None:
            srch_ic.setText("?")
        srch_ic.setStyleSheet("background: transparent;")
        ss_lay.addWidget(srch_ic)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search help pages...")
        self.search_box.setFixedHeight(28)
        self.search_box.setPlaceholderText("Search help topics…")
        self.search_box.setFixedHeight(26)
        self.search_box.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,255,255,.7); border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; font-size: {F.SZ_MD}pt; "
            f"color: {C.TEXT}; padding: 0 8px; }}"
            f"QLineEdit:focus {{ border-color: {C.OLIVE}; background: white; }}"
        )
        self.search_box.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,255,255,.76); border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; font-size: {F.SZ_MD}pt; "
            f"color: {C.TEXT}; padding: 0 8px; }}"
            f"QLineEdit:focus {{ border-color: {C.OLIVE}; background: white; }}"
        )
        self.search_box.setPlaceholderText("Search help pages...")
        self.search_box.setFixedHeight(28)
        self.search_box.textChanged.connect(self.on_search_text_changed)
        ss_lay.addWidget(self.search_box, 1)

        self.clear_search_btn = QPushButton("Clear")
        self.clear_search_btn.setFixedHeight(26)
        self.clear_search_btn.setFixedHeight(28)
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
        self.nav_tree.setMinimumWidth(270)
        self.nav_tree.setMaximumWidth(320)
        self.nav_tree.setIndentation(14)
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

    def _all_topics(self):
        topics = []
        for _, section_topics in HELP_TOPIC_SECTIONS:
            topics.extend(section_topics)
        return topics

    def _select_tree_item_for_file(self, file_name):
        item = self.topic_items.get(file_name)
        if item is None:
            return
        parent = item.parent()
        if parent is not None:
            parent.setExpanded(True)
        if self.nav_tree.currentItem() is not item:
            self.nav_tree.setCurrentItem(item)

    def load_help_topics(self):
        """Populate the navigation tree with structured help topics."""
        self.nav_tree.clear()
        self.topic_items.clear()

        first_topic = None
        for section_title, topics in HELP_TOPIC_SECTIONS:
            section_item = QTreeWidgetItem(self.nav_tree, [section_title])
            section_font = section_item.font(0)
            section_font.setBold(True)
            section_item.setFont(0, section_font)
            section_item.setFlags(section_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

            for title, file_name, icon_name in topics:
                item = QTreeWidgetItem(section_item, [title])
                item.setData(0, Qt.ItemDataRole.UserRole, file_name)
                try:
                    item.setIcon(0, _icon(icon_name, C.TEXT_MUTED))
                except Exception:
                    pass
                self.topic_items[file_name] = item
                if first_topic is None:
                    first_topic = item

            section_item.setExpanded(True)

        if first_topic is not None:
            self.nav_tree.setCurrentItem(first_topic)

    def on_topic_clicked(self, item, column):
        """Handle topic selection in navigation tree."""
        file_name = item.data(0, Qt.ItemDataRole.UserRole)
        if file_name:
            self.show_help_page(file_name)

    def show_help_page(self, file_name):
        """Load and display a help page."""
        legacy_routes = {
            "getting_started.html": "start_here.html",
            "file_formats.html": "data_files.html",
            "parameters.html": "analysis_parameters.html",
            "results.html": "workflow_results.html",
            "troubleshooting.html": "common_issues.html",
            "methods_overview.html": "methods_reference.html",
            "about.html": "about_reference.html",
        }
        file_name = legacy_routes.get(file_name, file_name)
        self.current_help_page = file_name
        self._select_tree_item_for_file(file_name)

        if file_name == "changelog.html":
            self.show_changelog_page()
            return

        file_path = os.path.join(self.help_dir, file_name)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()

                styled_html = self.apply_help_styling(html_content)
                self.content_browser.setHtml(styled_html)
                self.content_browser.verticalScrollBar().setValue(0)

            except Exception as exc:
                self.show_error_page(f"Error loading help page: {exc}")
        else:
            self.show_placeholder_page(file_name)

    def _changelog_path(self) -> str:
        return os.path.join(self.program_dir, "CHANGELOG.md")

    def show_changelog_page(self):
        """Render the project changelog inside the help browser."""
        changelog_path = self._changelog_path()
        if not os.path.exists(changelog_path):
            self.show_error_page(f"Changelog not found at {changelog_path}")
            return

        try:
            with open(changelog_path, "r", encoding="utf-8") as handle:
                markdown = handle.read()
        except Exception as exc:
            self.show_error_page(f"Error loading changelog: {exc}")
            return

        self.content_browser.setHtml(self.apply_help_styling(self._render_changelog_markdown(markdown)))
        self.content_browser.verticalScrollBar().setValue(0)

    def _render_changelog_markdown(self, markdown: str) -> str:
        """Convert the bundled Markdown changelog into restrained help HTML."""
        body: list[str] = ['<div class="page changelog-page">']
        in_list = False

        def close_list() -> None:
            nonlocal in_list
            if in_list:
                body.append("</ul>")
                in_list = False

        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                close_list()
                continue
            if line == "---":
                close_list()
                body.append("<hr>")
                continue
            if line.startswith("# "):
                close_list()
                body.append('<p class="eyebrow">Release Notes</p>')
                body.append(f"<h1>{self._inline_markdown(line[2:])}</h1>")
                continue
            if line.startswith("## "):
                close_list()
                body.append(f'<h2 class="release-heading">{self._inline_markdown(line[3:])}</h2>')
                continue
            if line.startswith("### "):
                close_list()
                body.append(f'<h3 class="change-section">{self._inline_markdown(line[4:])}</h3>')
                continue
            if line.startswith("- "):
                if not in_list:
                    body.append("<ul>")
                    in_list = True
                body.append(f"<li>{self._inline_markdown(line[2:])}</li>")
                continue

            close_list()
            body.append(f"<p>{self._inline_markdown(line)}</p>")

        close_list()
        body.append("</div>")
        return "\n".join(body)

    @staticmethod
    def _inline_markdown(text: str) -> str:
        html = escape(text)
        html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
        html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            lambda match: f'<a href="{escape(match.group(2), quote=True)}">{match.group(1)}</a>',
            html,
        )
        return html

    def apply_help_styling(self, html_content):
        """Apply consistent CSS styling to help content."""
        css = f"""
        <style>
            body {{
                font-family: "{F.UI}", "Source Sans 3", "Segoe UI", sans-serif;
                line-height: 1.58;
                color: #3f3428;
                margin: 0;
                background: #fcfaf6;
            }}
            .page {{
                max-width: 860px;
                margin: 0 auto;
                padding: 2px 4px 28px 4px;
            }}
            .eyebrow {{
                margin: 0 0 8px 0;
                color: #8c7b67;
                font-family: "{F.MONO}", "JetBrains Mono", monospace;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.12em;
                text-transform: uppercase;
            }}
            h1 {{
                margin: 0 0 12px 0;
                color: #403325;
                font-family: "{F.DISP}", "Georgia", serif;
                font-size: 29px;
                line-height: 1.16;
            }}
            h2 {{
                margin: 28px 0 10px 0;
                padding-top: 16px;
                border-top: 1px solid #e3d9ca;
                color: #584836;
                font-size: 19px;
            }}
            h2.release-heading {{
                margin-top: 26px;
                color: {C.OLIVE_DK};
            }}
            h3 {{
                margin: 18px 0 8px 0;
                color: {C.OLIVE_DK};
                font-size: 15px;
            }}
            h3.change-section {{
                color: #6b5b45;
                font-family: "{F.MONO}", "JetBrains Mono", monospace;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }}
            hr {{
                border: none;
                border-top: 1px solid #e3d9ca;
                margin: 22px 0;
            }}
            p {{
                margin: 0 0 12px 0;
            }}
            .lead {{
                margin: 0 0 18px 0;
                color: #5a4b3a;
                font-size: 16px;
            }}
            ul, ol {{
                margin: 0 0 14px 20px;
                padding: 0;
            }}
            li {{
                margin: 0 0 6px 0;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 14px 0 18px 0;
                background: #fffdf9;
                border: 1px solid #ddd1bd;
            }}
            th {{
                background: #ece2d3;
                color: #4c3e2e;
                padding: 9px 10px;
                text-align: left;
                font-weight: 700;
                border-bottom: 1px solid #d8c8b2;
            }}
            td {{
                padding: 8px 10px;
                vertical-align: top;
                border-top: 1px solid #eee4d3;
            }}
            code {{
                background: #f3ede2;
                border: 1px solid #e1d5c0;
                border-radius: 4px;
                padding: 1px 5px;
                font-family: "{F.MONO}", "JetBrains Mono", monospace;
                font-size: 0.95em;
                color: #5a4734;
            }}
            pre {{
                background: #f8f4eb;
                border: 1px solid #e1d5c0;
                border-radius: 8px;
                padding: 12px 14px;
                white-space: pre-wrap;
                font-family: "{F.MONO}", "JetBrains Mono", monospace;
                font-size: 0.95em;
                color: #514133;
            }}
            pre code {{
                background: transparent;
                border: none;
                padding: 0;
            }}
            .callout {{
                margin: 16px 0;
                padding: 12px 14px;
                border-radius: 8px;
                border: 1px solid #d8cbb8;
            }}
            .callout-title {{
                margin: 0 0 6px 0;
                font-family: "{F.MONO}", "JetBrains Mono", monospace;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }}
            .note {{
                background: #f7f2e9;
                border-color: #dccfb9;
            }}
            .note .callout-title {{
                color: #7a6348;
            }}
            .tip {{
                background: #eef6ea;
                border-color: rgba(107,142,35,.30);
            }}
            .tip .callout-title {{
                color: {C.OLIVE_DK};
            }}
            .warning {{
                background: #fbf0eb;
                border-color: rgba(192,56,40,.22);
            }}
            .warning .callout-title {{
                color: #9b3e2e;
            }}
            .muted {{
                color: #7c6a56;
                font-size: 13px;
            }}
            .example-jump {{
                margin: 10px 0 18px 0;
                padding: 10px 12px;
                background: #f7f2e9;
                border-top: 1px solid #dccfb9;
                border-bottom: 1px solid #dccfb9;
            }}
            .example-jump a {{
                display: inline-block;
                margin: 2px 12px 2px 0;
            }}
            .example-meta {{
                margin: -2px 0 8px 0;
                color: #7c6a56;
                font-size: 13px;
            }}
            .example-note {{
                margin: 8px 0 20px 0;
                padding-left: 11px;
                border-left: 3px solid {C.OLIVE};
                color: #5a4b3a;
            }}
            .compact-table {{
                margin-top: 8px;
            }}
            .compact-table th,
            .compact-table td {{
                padding: 6px 8px;
            }}
            .link-list a {{
                display: inline-block;
                margin: 0 14px 8px 0;
            }}
            .search-result {{
                margin: 0 0 14px 0;
                padding: 12px 14px;
                border: 1px solid #ddd1bd;
                border-radius: 8px;
                background: #fffdf9;
            }}
            .search-result h3 {{
                margin-top: 0;
            }}
            a {{
                color: {C.OLIVE_DK};
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            img {{
                max-width: 100%;
            }}
        </style>
        """

        return css + html_content

    def show_placeholder_page(self, file_name):
        """Show placeholder for help pages that don't exist yet."""
        html = f"""
        <div class="page">
            <p class="eyebrow">Help Page</p>
            <h1>Page Not Available</h1>
            <p class="lead">The requested page is not included in this build.</p>
            <div class="callout note">
                <div class="callout-title">Requested file</div>
                <p><code>{escape(file_name)}</code></p>
            </div>
            <p>Use <a href="start_here.html">Getting Started</a> or the navigation tree to open another topic.</p>
        </div>
        """
        self.content_browser.setHtml(self.apply_help_styling(html))

    def show_error_page(self, error_message):
        """Show error page when content can't be loaded."""
        html = f"""
        <div class="page">
            <p class="eyebrow">Help Page</p>
            <h1>Help Could Not Be Loaded</h1>
            <div class="callout warning">
                <div class="callout-title">Load error</div>
                <p>{escape(error_message)}</p>
            </div>
            <p>Check that the help files are installed with the application.</p>
        </div>
        """
        self.content_browser.setHtml(self.apply_help_styling(html))

    def on_search_text_changed(self, text):
        """Handle search text changes."""
        if not text or len(text.strip()) < 2:
            return
        self.search_help_content(text)

    def search_help_content(self, search_text):
        """Search through all configured help files and show results."""
        search_text = search_text.lower().strip()
        if len(search_text) < 2:
            return

        results = []
        for title, filename, _icon_name in self._all_topics():
            try:
                if filename == "changelog.html":
                    changelog_path = self._changelog_path()
                    if not os.path.exists(changelog_path):
                        continue
                    with open(changelog_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                else:
                    file_path = os.path.join(self.help_dir, filename)
                    if not os.path.exists(file_path):
                        continue
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                text_content = re.sub(r'<[^>]+>', ' ', content)
                text_content = re.sub(r'\s+', ' ', text_content).strip()
                lowered = text_content.lower()
                index = lowered.find(search_text)
                if index < 0:
                    continue

                start = max(0, index - 80)
                end = min(len(text_content), index + len(search_text) + 100)
                context = text_content[start:end].strip()

                results.append({
                    'title': title,
                    'filename': filename,
                    'context': context,
                })
            except Exception:
                continue

        self.show_search_results(search_text, results)

    def show_search_results(self, search_text, results):
        """Display search results in the content browser."""
        if not results:
            html = f"""
            <div class="page">
                <p class="eyebrow">Help Search</p>
                <h1>No Matches Found</h1>
                <p class="lead">No help pages matched <code>{escape(search_text)}</code>.</p>
                <div class="callout note">
                    <div class="callout-title">Try this</div>
                    <ul>
                        <li>Use shorter keywords such as <code>sheet</code>, <code>mapping</code>, or <code>export</code>.</li>
                        <li>Open <a href="start_here.html">Getting Started</a> if you are not sure where to begin.</li>
                    </ul>
                </div>
            </div>
            """
        else:
            cards = []
            for result in results:
                cards.append(
                    f"""
                    <div class="search-result">
                        <h3><a href="{escape(result['filename'])}">{escape(result['title'])}</a></h3>
                        <p class="muted">{escape(result['context'])}...</p>
                    </div>
                    """
                )

            html = f"""
            <div class="page">
                <p class="eyebrow">Help Search</p>
                <h1>Search Results</h1>
                <p class="lead">{len(results)} page(s) matched <code>{escape(search_text)}</code>.</p>
                {''.join(cards)}
            </div>
            """

        self.content_browser.setHtml(self.apply_help_styling(html))
        self.content_browser.verticalScrollBar().setValue(0)

    def clear_search(self):
        """Clear search and return to the current topic."""
        self.search_box.clear()
        if self.current_help_page:
            self.show_help_page(self.current_help_page)
