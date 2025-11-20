"""
Paper-Style Welcome Screen for DataMerger (v2) - PRODUCTION READY
Uses QWebEngineView with architect/engineering drawing aesthetic
Optimized for .exe builds with embedded SVG support
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl
import datetime
import tempfile
import os
import sys


class _WelcomeBridge(QObject):
    """Bridge object exposed to JavaScript via QWebChannel."""

    def __init__(self, screen):
        super().__init__(screen)
        self._screen = screen

    @pyqtSlot(str)
    def triggerAction(self, action):
        """Handle action requests coming from the web view."""
        self._screen.dispatch_action(action)


class PaperWelcomeScreen(QWidget):
    """Paper-style welcome screen with blueprint/architect aesthetic"""

    # Signals for main app integration (same as original)
    load_data_requested = pyqtSignal()
    load_sample_data_requested = pyqtSignal()
    load_secondary_data_requested = pyqtSignal()
    open_documentation_requested = pyqtSignal()
    tutorial_requested = pyqtSignal(str)
    merge_tutorial_requested = pyqtSignal()
    new_workspace_requested = pyqtSignal()
    open_workspace_requested = pyqtSignal(str)
    remove_recent_workspace_requested = pyqtSignal(str)

    def __init__(self, parent=None, workspace_manager=None):
        super().__init__(parent)
        self.temp_file = None
        self.recent_projects = []
        self.workspace_manager = workspace_manager
        self.bridge = _WelcomeBridge(self)
        self._web_channel = None
        self.setup_ui()

    def load_welcome_chart_svg(self):
        """Load matplotlib xkcd-style line plot SVG"""
        try:
            # Try loading matplotlib-generated xkcd plot first
            if getattr(sys, "frozen", False):
                base_path = sys._MEIPASS
                svg_path = os.path.join(base_path, "line_plot_xkcd.svg")
            else:
                base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                svg_path = os.path.join(base_path, "svg_generation", "line_plot_xkcd.svg")

            with open(svg_path, "r", encoding="utf-8") as f:
                svg_content = f.read()

            # Extract just the SVG tag content (remove XML declaration)
            if "<?xml" in svg_content:
                svg_content = svg_content[svg_content.find("<svg") :]

            return svg_content

        except FileNotFoundError:
            print(f"Warning: Matplotlib xkcd plot not found at {svg_path}, using fallback")
            return self._generate_fallback_svg()
        except Exception as e:
            print(f"Error loading matplotlib xkcd plot: {e}")
            return self._generate_fallback_svg()

    def load_welcome_map_svg(self):
        """Load pre-generated map illustration SVG from assets"""
        return self._load_svg_asset("welcome_map.svg", self._generate_fallback_map_svg)

    def load_welcome_barchart_svg(self):
        """Load matplotlib xkcd-style bar chart SVG"""
        try:
            if getattr(sys, "frozen", False):
                base_path = sys._MEIPASS
                svg_path = os.path.join(base_path, "bar_chart_xkcd.svg")
            else:
                base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                svg_path = os.path.join(base_path, "svg_generation", "bar_chart_xkcd.svg")

            with open(svg_path, "r", encoding="utf-8") as f:
                svg_content = f.read()

            if "<?xml" in svg_content:
                svg_content = svg_content[svg_content.find("<svg") :]

            return svg_content

        except FileNotFoundError:
            print(f"Warning: Matplotlib xkcd bar chart not found at {svg_path}, using fallback")
            return self._generate_fallback_barchart_svg()
        except Exception as e:
            print(f"Error loading matplotlib xkcd bar chart: {e}")
            return self._generate_fallback_barchart_svg()

    def load_row1_merge_svg(self):
        """Load row 1: Data merge workflow SVG"""
        return self._load_xkcd_svg("row1_merge.svg")

    def load_row2_stats_svg(self):
        """Load row 2A: Statistical histogram SVG"""
        return self._load_xkcd_svg("row2_stats.svg")

    def load_row2_map_svg(self):
        """Load row 2B: Geospatial map SVG"""
        return self._load_xkcd_svg("row2_map.svg")

    def load_row3_dashboard_svg(self):
        """Load row 3: Results dashboard SVG"""
        return self._load_xkcd_svg("row3_dashboard.svg")

    def load_denmark_map_svg(self):
        """Load Denmark map background SVG"""
        return self._load_xkcd_svg("denmark_map_sketch.svg")

    def load_workflow_checklist_svg(self):
        """Load workflow checklist SVG"""
        return self._load_xkcd_svg("workflow_checklist.svg")

    def _load_xkcd_svg(self, filename):
        """Generic loader for xkcd-style SVG files from svg_generation directory"""
        try:
            if getattr(sys, "frozen", False):
                base_path = sys._MEIPASS
                svg_path = os.path.join(base_path, filename)
            else:
                # Look in svg_generation directory (sibling to src/)
                base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                svg_path = os.path.join(base_path, "svg_generation", filename)

            with open(svg_path, "r", encoding="utf-8") as f:
                svg_content = f.read()

            if "<?xml" in svg_content:
                svg_content = svg_content[svg_content.find("<svg") :]

            return svg_content

        except FileNotFoundError:
            print(f"Warning: {filename} not found at {svg_path}, using fallback")
            return self._generate_fallback_svg()
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return self._generate_fallback_svg()

    def _load_svg_asset(self, filename, fallback_func):
        """Generic method to load SVG assets with fallback"""
        try:
            # Determine the path to the SVG file
            if getattr(sys, "frozen", False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.dirname(__file__))

            svg_path = os.path.join(base_path, "assets", filename)

            # Read the SVG
            with open(svg_path, "r", encoding="utf-8") as f:
                svg_content = f.read()

            # Extract just the SVG tag content
            if "<?xml" in svg_content:
                svg_content = svg_content[svg_content.find("<svg") :]

            return svg_content

        except FileNotFoundError:
            print(f"Warning: {filename} not found, using fallback")
            return fallback_func()
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return fallback_func()

    def _generate_fallback_svg(self):
        """Generate a simple fallback SVG for line chart"""
        return """<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg">
            <line x1="40" y1="20" x2="40" y2="170" stroke="#333" stroke-width="2"/>
            <line x1="40" y1="170" x2="280" y2="170" stroke="#333" stroke-width="2"/>
            <path d="M 50,155 L 80,145 L 110,148 L 140,130 L 170,120 L 200,122 L 230,100 L 250,85 L 270,70"
                  fill="none" stroke="#2196F3" stroke-width="2.5"/>
            <path d="M 50,160 L 80,155 L 110,150 L 140,140 L 170,130 L 200,120 L 230,110 L 250,95 L 270,85"
                  fill="none" stroke="#27ae60" stroke-width="2.5"/>
            <path d="M 50,150 L 80,140 L 110,135 L 140,115 L 170,125 L 200,110 L 230,115 L 250,95 L 270,80"
                  fill="none" stroke="#e74c3c" stroke-width="2.5"/>
        </svg>"""

    def _generate_fallback_map_svg(self):
        """Generate a simple fallback SVG for map"""
        return """<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg">
            <circle cx="150" cy="100" r="60" fill="none" stroke="#27ae60" stroke-width="2.5"/>
            <circle cx="120" cy="80" r="5" fill="#e74c3c"/>
            <circle cx="180" cy="90" r="5" fill="#2196F3"/>
            <circle cx="150" cy="130" r="5" fill="#f39c12"/>
        </svg>"""

    def _generate_fallback_barchart_svg(self):
        """Generate a simple fallback SVG for bar chart"""
        return """<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg">
            <line x1="40" y1="20" x2="40" y2="170" stroke="#333" stroke-width="2"/>
            <line x1="40" y1="170" x2="280" y2="170" stroke="#333" stroke-width="2"/>
            <rect x="50" y="80" width="30" height="90" fill="#2196F3"/>
            <rect x="95" y="50" width="30" height="120" fill="#27ae60"/>
            <rect x="140" y="100" width="30" height="70" fill="#e74c3c"/>
            <rect x="185" y="40" width="30" height="130" fill="#f39c12"/>
            <rect x="230" y="70" width="30" height="100" fill="#9b59b6"/>
        </svg>"""

    def setup_ui(self):
        """Setup the paper-style welcome screen UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create QWebEngineView
        self.web_view = QWebEngineView()

        # Set up web channel bridge for robust JS <-> Python communication
        channel = QWebChannel(self.web_view.page())
        channel.registerObject("AppBridge", self.bridge)
        self.web_view.page().setWebChannel(channel)
        self._web_channel = channel

        # Keep title change handler as a fallback transport
        self.web_view.page().titleChanged.connect(self.handle_title_change)

        # Load the HTML content
        self.load_welcome_html()

        layout.addWidget(self.web_view)

    def handle_title_change(self, title):
        """Handle title changes for JavaScript -> Python communication"""
        if title.startswith("action:"):
            action = title.replace("action:", "")
            self.dispatch_action(action)

    def dispatch_action(self, action: str):
        """Route actions triggered from the embedded web view."""
        if action == "load_data":
            self.load_data_requested.emit()
        elif action == "load_sample":
            self.load_sample_data_requested.emit()
        elif action == "merge_data":
            self.load_secondary_data_requested.emit()
        elif action == "documentation":
            self.open_documentation_requested.emit()
        elif action == "new_workspace":
            self.new_workspace_requested.emit()
        elif action.startswith("open_workspace_b64:"):
            import base64

            encoded_path = action.replace("open_workspace_b64:", "")
            try:
                workspace_path = base64.b64decode(
                    encoded_path.encode("ascii")
                ).decode("utf-8")
                self.open_workspace_requested.emit(workspace_path)
            except Exception as exc:
                print(f"Failed to decode workspace path: {encoded_path} ({exc})")
        elif action.startswith("open_workspace:"):
            workspace_path = action.replace("open_workspace:", "")
            if workspace_path == "browse":
                self.open_workspace_requested.emit("")
            else:
                self.open_workspace_requested.emit(workspace_path)
        elif action.startswith("remove_recent_b64:"):
            import base64

            encoded_path = action.replace("remove_recent_b64:", "")
            try:
                workspace_path = base64.b64decode(
                    encoded_path.encode("ascii")
                ).decode("utf-8")
                self.remove_recent_workspace_requested.emit(workspace_path)
            except Exception as exc:
                print(
                    f"Failed to decode workspace path for removal: {encoded_path} ({exc})"
                )

    def load_welcome_html(self):
        """Load the paper-style welcome HTML content"""
        html_content = self.get_welcome_html()

        # Create temporary file
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        )
        self.temp_file.write(html_content)
        self.temp_file.close()

        # Load the HTML file
        self.web_view.load(QUrl.fromLocalFile(self.temp_file.name))

    def get_welcome_html(self):
        """Generate production-ready paper-style welcome HTML content"""
        current_month = datetime.datetime.now().strftime("%B %Y")

        # Load SVGs for decorations
        denmark_map_svg = self.load_denmark_map_svg()
        row1_merge_svg = self.load_row1_merge_svg()
        row2_stats_svg = self.load_row2_stats_svg()
        workflow_checklist_svg = self.load_workflow_checklist_svg()

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DataMerger - Welcome</title>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        html {{
            font-size: 16px;
        }}

        body {{
            width: 100vw;
            min-height: 100vh;
            overflow-x: hidden;
            overflow-y: auto;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #2c3e50;
            line-height: 1.6;
            background: #ffffff;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 50px 30px;
        }}

        /* Left side: Graph paper */
        body::after {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 50%;
            height: 100%;
            background: #ffffff;
            background-image:
                linear-gradient(rgba(52, 152, 219, 0.06) 1px, transparent 1px),
                linear-gradient(90deg, rgba(52, 152, 219, 0.06) 1px, transparent 1px),
                linear-gradient(rgba(52, 152, 219, 0.12) 1.5px, transparent 1.5px),
                linear-gradient(90deg, rgba(52, 152, 219, 0.12) 1.5px, transparent 1.5px);
            background-size:
                10px 10px,
                10px 10px,
                100px 100px,
                100px 100px;
            pointer-events: none;
            z-index: 0;
        }}

        /* Right side: Lined notebook paper */
        .right-paper {{
            position: fixed;
            top: 0;
            right: 0;
            width: 50%;
            height: 100%;
            background: #ffffff;
            background-image:
                linear-gradient(90deg,
                    transparent 0,
                    transparent 40px,
                    rgba(231, 76, 60, 0.25) 40px,
                    rgba(231, 76, 60, 0.25) 42px,
                    transparent 42px
                ),
                repeating-linear-gradient(
                    0deg,
                    transparent 0,
                    transparent 31px,
                    rgba(52, 152, 219, 0.1) 31px,
                    rgba(52, 152, 219, 0.1) 32px
                );
            pointer-events: none;
            z-index: 0;
        }}

        body::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.005);
            pointer-events: none;
            z-index: 1;
        }}

        .paper-content {{
            max-width: 1100px;
            width: 100%;
            padding: 35px;
            position: relative;
            z-index: 10;
            margin: auto;
            display: flex;
            flex-direction: column;
            gap: 28px;
        }}

        .content-box {{
            position: relative;
            padding: 32px;
            background: linear-gradient(145deg, #ffffff 0%, #fefefe 100%);
            box-shadow:
                0 16px 48px rgba(0, 0, 0, 0.08),
                0 6px 18px rgba(0, 0, 0, 0.04),
                inset 0 1px 0 rgba(255, 255, 255, 0.92);
            border-radius: 8px;
            border: 1px solid rgba(120, 100, 80, 0.12);
        }}

        .content-box::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border: 2.5px solid #2c3e50;
            border-radius: 8px;
            pointer-events: none;
            z-index: 1;
            clip-path: polygon(
                0% 0.5%, 0.5% 0%, 99.5% 0%, 100% 0.5%,
                100% 99.5%, 99.5% 100%, 0.5% 100%, 0% 99.5%
            );
        }}

        .content-box::after {{
            content: '';
            position: absolute;
            top: -8px;
            left: -8px;
            right: -8px;
            bottom: -8px;
            background: linear-gradient(135deg,
                rgba(255, 248, 235, 0.3) 0%,
                rgba(240, 235, 220, 0.15) 50%,
                rgba(255, 248, 235, 0.3) 100%);
            border-radius: 8px;
            z-index: -1;
            filter: blur(12px);
            opacity: 0.5;
            pointer-events: none;
        }}

        .header {{
            text-align: center;
            margin: 0 auto 32px;
            position: relative;
            padding: 28px 35px;
            background: linear-gradient(145deg, #ffffff 0%, #fefefe 100%);
            box-shadow:
                0 16px 48px rgba(0, 0, 0, 0.08),
                0 6px 18px rgba(0, 0, 0, 0.04),
                inset 0 1px 0 rgba(255, 255, 255, 0.9);
            border-radius: 8px;
            border: 1px solid rgba(120, 100, 80, 0.12);
            display: inline-flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            align-self: center;
            max-width: 550px;
            width: 100%;
        }}

        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border: 2px solid #2c3e50;
            border-radius: 8px;
            pointer-events: none;
            z-index: 1;
            clip-path: polygon(
                0% 0.8%, 1% 0%, 99% 0%, 100% 0.8%,
                100% 99.2%, 99% 100%, 1% 100%, 0% 99.2%
            );
        }}

        .header::after {{
            content: '';
            position: absolute;
            top: -6px;
            left: -6px;
            right: -6px;
            bottom: -6px;
            background: linear-gradient(135deg,
                rgba(255, 248, 235, 0.3) 0%,
                rgba(240, 235, 220, 0.15) 50%,
                rgba(255, 248, 235, 0.3) 100%);
            border-radius: 8px;
            z-index: -1;
            filter: blur(12px);
            opacity: 0.5;
            pointer-events: none;
        }}

        .header h1 {{
            font-family: 'Courier New', monospace;
            font-size: 2.5rem;
            font-weight: 600;
            color: #2c3e50;
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-bottom: 10px;
            position: relative;
            display: inline-block;
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            z-index: 2;
        }}

        .header h1::after {{
            content: '';
            position: absolute;
            bottom: -10px;
            left: 50%;
            transform: translateX(-50%);
            width: 65%;
            height: 2.5px;
            background: linear-gradient(90deg,
                transparent 0%,
                rgba(231, 76, 60, 0.6) 20%,
                rgba(52, 152, 219, 0.6) 50%,
                rgba(46, 204, 113, 0.6) 80%,
                transparent 100%);
            opacity: 0.6;
        }}

        .header .version {{
            font-family: 'Courier New', monospace;
            font-size: 0.95rem;
            color: #666;
            margin-top: 8px;
            position: relative;
            z-index: 2;
        }}

        .header .tagline {{
            font-family: 'Courier New', monospace;
            font-size: 1.05rem;
            color: #555;
            margin-top: 8px;
            font-style: italic;
            position: relative;
            z-index: 2;
        }}

        .content-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 28px;
            margin-bottom: 0;
        }}

        .section {{
            position: relative;
            z-index: 2;
        }}

        .section-title {{
            font-family: 'Courier New', monospace;
            font-size: 1.25rem;
            font-weight: 600;
            color: #34495e;
            margin-bottom: 18px;
            padding-bottom: 12px;
            border-bottom: 2.5px solid rgba(52, 152, 219, 0.2);
            position: relative;
        }}

        .section-title::before {{
            content: '';
            position: absolute;
            bottom: -2.5px;
            left: 0;
            width: 70px;
            height: 2.5px;
            background: linear-gradient(90deg, #3498db, #2ecc71);
        }}

        .actions-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 18px;
            margin-bottom: 22px;
        }}

        .sketch-button {{
            position: relative;
            padding: 16px 20px;
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border: 1.5px solid rgba(52, 152, 219, 0.22);
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            text-align: center;
            font-family: 'Courier New', monospace;
            min-height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow:
                0 2px 6px rgba(0, 0, 0, 0.04),
                0 1px 2px rgba(0, 0, 0, 0.06);
            overflow: hidden;
        }}

        .sketch-button::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg,
                transparent,
                rgba(52, 152, 219, 0.1),
                transparent);
            transition: left 0.5s ease;
        }}

        .sketch-button:hover {{
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-color: rgba(52, 152, 219, 0.4);
            transform: translateY(-2px);
            box-shadow:
                0 8px 16px rgba(0, 0, 0, 0.08),
                0 3px 6px rgba(0, 0, 0, 0.1),
                inset 0 1px 0 rgba(255, 255, 255, 0.8);
        }}

        .sketch-button:hover::before {{
            left: 100%;
        }}

        .sketch-button:active {{
            transform: translateY(0);
            box-shadow:
                0 2px 4px rgba(0, 0, 0, 0.08),
                0 1px 2px rgba(0, 0, 0, 0.1);
        }}

        .sketch-button .label {{
            font-size: 0.95rem;
            font-weight: 600;
            color: #34495e;
            letter-spacing: 0.5px;
            position: relative;
            z-index: 1;
        }}

        .projects-list {{
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.65) 0%, rgba(248, 249, 250, 0.6) 100%);
            padding: 18px;
            position: relative;
            border-radius: 6px;
            border: 1px solid rgba(52, 152, 219, 0.12);
            max-height: 350px;
            overflow-y: auto;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.02);
        }}

        .projects-list::-webkit-scrollbar {{
            width: 10px;
        }}

        .projects-list::-webkit-scrollbar-track {{
            background: rgba(0, 0, 0, 0.02);
            border-radius: 6px;
        }}

        .projects-list::-webkit-scrollbar-thumb {{
            background: rgba(52, 152, 219, 0.3);
            border-radius: 6px;
        }}

        .projects-list::-webkit-scrollbar-thumb:hover {{
            background: rgba(52, 152, 219, 0.5);
        }}

        .project-item {{
            padding: 14px 16px;
            margin-bottom: 12px;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.82) 0%, rgba(248, 249, 250, 0.78) 100%);
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            position: relative;
            border-left: 3px solid transparent;
            border-radius: 6px;
            border: 1px solid rgba(52, 152, 219, 0.1);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
        }}

        .project-item:hover {{
            background: linear-gradient(135deg, rgba(52, 152, 219, 0.08) 0%, rgba(46, 204, 113, 0.05) 100%);
            transform: translateX(5px);
            border-left-color: #3498db;
            box-shadow:
                0 4px 12px rgba(0, 0, 0, 0.06),
                0 2px 4px rgba(0, 0, 0, 0.04);
        }}

        .project-item::before {{
            content: '->';
            position: absolute;
            left: -20px;
            color: #3498db;
            font-size: 1.3rem;
            opacity: 0;
            transition: all 0.3s ease;
        }}

        .project-item:hover::before {{
            opacity: 1;
            left: -16px;
        }}

        .project-name {{
            font-weight: 600;
            color: #1a252f;
            font-size: 0.95rem;
            margin-bottom: 6px;
        }}

        .project-meta {{
            font-size: 0.82rem;
            color: #666;
            line-height: 1.5;
        }}

        .no-projects {{
            text-align: center;
            padding: 40px 28px;
            font-family: 'Courier New', monospace;
            font-size: 1rem;
            color: #7f8c8d;
            line-height: 1.8;
        }}

        .features-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}

        .features-list li {{
            padding: 10px 0 10px 26px;
            margin-bottom: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            color: #34495e;
            position: relative;
            line-height: 1.7;
            transition: all 0.2s ease;
        }}

        .features-list li:hover {{
            color: #2c3e50;
            transform: translateX(5px);
        }}

        .features-list li::before {{
            content: '';
            position: absolute;
            left: 10px;
            top: 50%;
            transform: translateY(-50%);
            width: 7px;
            height: 7px;
            background: linear-gradient(135deg, #3498db, #2ecc71);
            border-radius: 50%;
            opacity: 0.7;
            transition: all 0.2s ease;
        }}

        .features-list li:hover::before {{
            opacity: 1;
            transform: translateY(-50%) scale(1.3);
        }}

        svg {{
            width: 100%;
            height: 100%;
        }}

        /* IMPROVED SVG DECORATIONS - LARGER AND MORE VISIBLE */

        /* Large background map decoration */
        .background-map {{
            position: fixed;
            bottom: -100px;
            left: 20px;
            width: clamp(600px, 50vw, 1000px);
            height: auto;
            pointer-events: none;
            z-index: 1;
            opacity: 0.28;
            transform: rotate(-3deg);
        }}

        .background-map svg {{
            width: 100%;
            height: auto;
            filter: none;
        }}

        /* Top-right: Workflow checklist */
        .checklist-decoration {{
            position: fixed;
            top: 25px;
            right: 25px;
            width: clamp(280px, 24vw, 420px);
            pointer-events: none;
            z-index: 2;
            opacity: 0.45;
            transform: rotate(1deg);
        }}

        .checklist-decoration svg {{
            width: 100%;
            height: auto;
            filter: none;
        }}

        /* Top-left: Merge diagram */
        .merge-decoration {{
            position: fixed;
            top: 40px;
            left: 25px;
            width: clamp(240px, 20vw, 350px);
            pointer-events: none;
            z-index: 2;
            opacity: 0.4;
            transform: rotate(-2deg);
        }}

        .merge-decoration svg {{
            width: 100%;
            height: auto;
            filter: none;
        }}

        /* Bottom-right: Stats plot */
        .plot-decoration {{
            position: fixed;
            bottom: 25px;
            right: 25px;
            width: clamp(280px, 24vw, 400px);
            pointer-events: none;
            z-index: 2;
            opacity: 0.4;
            transform: rotate(1deg);
        }}

        .plot-decoration svg {{
            width: 100%;
            height: auto;
            filter: none;
        }}

        /* RESPONSIVE BREAKPOINTS */

        @media (max-width: 1400px) {{
            /* Slightly reduce decoration opacity on smaller desktops */
            .background-map {{
                opacity: 0.22;
            }}
            .checklist-decoration,
            .merge-decoration,
            .plot-decoration {{
                opacity: 0.35;
            }}
        }}

        @media (max-width: 1100px) {{
            /* Reduce decoration opacity at medium sizes to avoid overlap */
            .background-map,
            .checklist-decoration,
            .merge-decoration,
            .plot-decoration {{
                opacity: 0.18;
            }}

            .header h1 {{
                font-size: 2.2rem;
            }}
        }}

        @media (max-width: 900px) {{
            html {{
                font-size: 15px;
            }}

            .paper-content {{
                padding: 22px;
            }}

            .content-box {{
                padding: 24px;
            }}

            .header {{
                padding: 24px 28px;
                max-width: 100%;
            }}

            .header h1 {{
                font-size: 1.9rem;
                letter-spacing: 3px;
            }}

            .content-grid {{
                grid-template-columns: 1fr;
                gap: 22px;
            }}

            .actions-grid {{
                grid-template-columns: repeat(2, 1fr);
                gap: 14px;
            }}

            /* Hide split paper effect and decorations on tablets */
            body::after,
            .right-paper {{
                display: none;
            }}

            body {{
                background: #ffffff;
                padding: 25px 18px;
            }}

            .background-map,
            .checklist-decoration,
            .merge-decoration,
            .plot-decoration {{
                display: none !important;
            }}
        }}

        @media (max-width: 600px) {{
            html {{
                font-size: 14px;
            }}

            .actions-grid {{
                grid-template-columns: 1fr;
            }}

            .header h1 {{
                font-size: 1.6rem;
                letter-spacing: 2px;
            }}

            .sketch-button {{
                min-height: 55px;
            }}
        }}

        /* ANIMATIONS */

        .fade-in {{
            animation: fadeIn 0.6s ease-out forwards;
        }}

        @keyframes fadeIn {{
            from {{
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .sketch-button {{
            animation: fadeIn 0.5s ease-out forwards;
        }}

        .sketch-button:nth-child(1) {{ animation-delay: 0.1s; opacity: 0; }}
        .sketch-button:nth-child(2) {{ animation-delay: 0.2s; opacity: 0; }}
        .sketch-button:nth-child(3) {{ animation-delay: 0.3s; opacity: 0; }}
        .sketch-button:nth-child(4) {{ animation-delay: 0.4s; opacity: 0; }}
    </style>
</head>
<body>
    <!-- Split paper background -->
    <div class="right-paper"></div>

    <!-- Large background map (bottom-left area, behind content) -->
    <div class="background-map">
        {denmark_map_svg}
    </div>

    <!-- Top-right: Workflow checklist -->
    <div class="checklist-decoration">
        {workflow_checklist_svg}
    </div>

    <!-- Top-left: Merge diagram -->
    <div class="merge-decoration">
        {row1_merge_svg}
    </div>

    <!-- Bottom-right: Stats plot -->
    <div class="plot-decoration">
        {row2_stats_svg}
    </div>

    <div class="paper-content">
        <header class="header">
            <h1>DATAMERGER</h1>
            <p class="version">Version 0.7.0 | {current_month}</p>
            <p class="tagline">Advanced Data Analysis & Visualization</p>
        </header>

        <div class="content-box">
            <div class="section">
                <h2 class="section-title">Quick Actions</h2>
                <div class="actions-grid">
                    <button class="sketch-button" onclick="triggerAction('load_data')" data-action="load_data">
                        <span class="label">Load Data</span>
                    </button>

                    <button class="sketch-button" onclick="triggerAction('merge_data')" data-action="merge_data">
                        <span class="label">Merge Data</span>
                    </button>

                    <button class="sketch-button" onclick="triggerAction('load_sample')" data-action="load_sample">
                        <span class="label">Try Samples</span>
                    </button>

                    <button class="sketch-button" onclick="triggerAction('documentation')" data-action="documentation">
                        <span class="label">Documentation</span>
                    </button>
                </div>
            </div>

            <div class="content-grid">
                <div class="section">
                    <h2 class="section-title">Recent Projects</h2>
                    {self.get_recent_projects_html()}
                </div>

                <div class="section">
                    <h2 class="section-title">Key Features</h2>
                    <ul class="features-list">
                        <li>Multi-source data loading (CSV, Excel, JSON, SQL)</li>
                        <li>Intelligent data merging and joining</li>
                        <li>Advanced filtering and batch operations</li>
                        <li>Statistical analysis and visualizations</li>
                        <li>Interactive charts and geographic mapping</li>
                        <li>Time series analysis and forecasting</li>
                        <li>Custom Python scripting support</li>
                        <li>QGIS integration for GIS workflows</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>

    <script>
        let appBridge = null;

        // Initialize web channel bridge
        window.addEventListener('DOMContentLoaded', function() {{
            if (window.qt && window.qt.webChannelTransport) {{
                new QWebChannel(window.qt.webChannelTransport, function(channel) {{
                    appBridge = channel.objects.AppBridge || null;
                }});
            }}
        }});

        function triggerAction(action) {{
            if (appBridge && typeof appBridge.triggerAction === 'function') {{
                appBridge.triggerAction(action);
            }} else {{
                document.title = 'action:' + action;
                if (window.parent && window.parent !== window) {{
                    window.parent.postMessage({{action: action}}, '*');
                }}
            }}
        }}

        // Adjust for viewport resize
        let resizeTimer;
        window.addEventListener('resize', function() {{
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {{
                const width = window.innerWidth;
                if (width < 900) {{
                    document.querySelectorAll('.illustration').forEach(ill => {{
                        ill.style.display = 'none';
                    }});
                }} else {{
                    document.querySelectorAll('.illustration').forEach(ill => {{
                        ill.style.display = 'block';
                    }});
                }}
            }}, 250);
        }});
    </script>
</body>
</html>
"""

    def get_recent_projects_html(self):
        """Generate HTML for recent projects section"""
        if not self.recent_projects:
            return """
                <div class="no-projects">
                    No recent projects yet.<br>Create your first workspace!
                    <div style="margin-top: 12px;">
                        <button class="sketch-button" onclick="triggerAction('new_workspace')" data-action="new_workspace" style="width: 100%;">
                            <span class="label">+ New Workspace</span>
                        </button>
                    </div>
                </div>
            """

        projects_html = ""
        for project in self.recent_projects[:8]:  # Show max 8 recent projects
            import base64

            project_path_raw = project.get("path", "")
            project_path_encoded = base64.b64encode(
                project_path_raw.encode("utf-8")
            ).decode("ascii")
            project_name = (
                project.get("name", "Untitled")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            modified_text = (
                self.format_time_ago(project.get("modified", ""))
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

            # Get workspace preview with rich metadata
            meta_parts = []

            # Try to get rich workspace metadata
            preview = None
            if self.workspace_manager and os.path.exists(project_path_raw):
                try:
                    preview = self.workspace_manager.get_workspace_preview(project_path_raw)
                except Exception as e:
                    print(f"Warning: Could not get workspace preview: {e}")

            # Build metadata string
            if preview and preview.get("exists"):
                # Show dataset count
                datasets_count = preview.get("datasets", 0)
                if datasets_count > 0:
                    meta_parts.append(f"{datasets_count} dataset{'s' if datasets_count != 1 else ''}")

                # Show operations count
                ops_count = preview.get("operations", 0)
                if ops_count > 0:
                    meta_parts.append(f"{ops_count} operation{'s' if ops_count != 1 else ''}")

                # Show plots count
                plots_count = preview.get("plots", 0)
                if plots_count > 0:
                    meta_parts.append(f"{plots_count} plot{'s' if plots_count != 1 else ''}")

                # Add modification time if available
                if modified_text != "Unknown":
                    meta_parts.append(f"({modified_text})")
            else:
                # Fallback to file size and date if preview not available
                file_size = "Unknown size"
                file_date = ""
                if os.path.exists(project_path_raw):
                    try:
                        size_bytes = os.path.getsize(project_path_raw)
                        if size_bytes < 1024:
                            file_size = f"{size_bytes} B"
                        elif size_bytes < 1024 * 1024:
                            file_size = f"{size_bytes / 1024:.1f} KB"
                        else:
                            file_size = f"{size_bytes / (1024 * 1024):.1f} MB"

                        # Get file modification date
                        from datetime import datetime

                        mod_time = os.path.getmtime(project_path_raw)
                        mod_datetime = datetime.fromtimestamp(mod_time)
                        file_date = mod_datetime.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass

                if file_date:
                    meta_parts.append(file_date)
                meta_parts.append(file_size)
                if modified_text != "Unknown":
                    meta_parts.append(f"({modified_text})")

            meta_info = " | ".join(meta_parts) if meta_parts else "No details available"

            projects_html += f"""
            <div class="project-item" onclick="triggerAction('open_workspace_b64:{project_path_encoded}')" title="{project_path_raw}">
                <div class="project-name">{project_name}</div>
                <div class="project-meta">{meta_info}</div>
            </div>
            """

        return f"""
            <div class="projects-list">
                {projects_html}
            </div>
            <div style="margin-top: 10px;">
                <button class="sketch-button" onclick="triggerAction('new_workspace')" data-action="new_workspace" style="width: 100%;">
                    <span class="label">+ New Workspace</span>
                </button>
            </div>
        """

    def format_time_ago(self, timestamp_str):
        """Format timestamp as 'time ago' text"""
        if not timestamp_str:
            return "Unknown"

        try:
            from datetime import datetime

            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            now = datetime.now(timestamp.tzinfo)
            diff = now - timestamp

            if diff.days > 0:
                return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            else:
                return "Just now"
        except:
            return "Unknown"

    def update_recent_projects(self, recent_projects):
        """Update recent projects and refresh the welcome screen"""
        self.recent_projects = recent_projects
        self.refresh_welcome_screen()

    def refresh_welcome_screen(self):
        """Refresh the welcome screen with updated recent projects"""
        self.load_welcome_html()

    def __del__(self):
        """Clean up temporary file"""
        if self.temp_file and os.path.exists(self.temp_file.name):
            try:
                os.unlink(self.temp_file.name)
            except:
                pass


# Alias for easy import
WelcomeScreenV2 = PaperWelcomeScreen
