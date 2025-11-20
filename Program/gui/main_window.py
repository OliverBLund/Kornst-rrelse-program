"""
Main window for the Grain Size Analysis application - New Architecture
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QMenuBar, QToolBar, QStatusBar, QSplitter,
    QTabWidget, QMessageBox, QProgressBar,
    QFileDialog, QDialog, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QAction, QColor
from typing import List, Dict, Optional
import os

# Import our modules
from gui.control_panel import ControlPanel
from gui.dataset_tab import DatasetTab
from gui.comparison_tab import ComparisonTab
from gui.reporting_tab import ReportingTab
from gui.export_tab import ExportTab
from gui.error_tab import ErrorTab
from gui.welcome_widget import WelcomeWidget
from data_loader import DataLoader, GrainSizeData
from k_calculations import KCalculator


class MainWindow(QMainWindow):
    """Main application window with new two-level tab architecture"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grain Size Analysis - Hydraulic Conductivity Calculator")

        # Initialize data structures
        self.data_loader = DataLoader()
        self.k_calculator = KCalculator()
        self.dataset_tabs: List[DatasetTab] = []
        self.dataset_counter = 0

        # Apply styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f0;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background: white;
            }
            QTabBar::tab {
                padding: 6px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #6b8e23;
                color: white;
            }
            QTabBar::tab:!selected {
                background: #d2b48c;
            }
            QStatusBar {
                background-color: #f0ebe5;
                border-top: 1px solid #c4a574;
            }
        """)

        self.setup_ui()
        # Toolbar removed - Help and About moved to sidebar
        self.setup_statusbar()

        # Set initial state
        self._show_status_message("Ready - Add files to begin analysis")

    def setup_ui(self):
        """Setup the main UI layout with two-level tabs"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Control panel wrapped in scroll area for small screens
        self.control_panel = ControlPanel()

        # Create scroll area for control panel
        control_scroll = QScrollArea()
        control_scroll.setWidget(self.control_panel)
        control_scroll.setWidgetResizable(True)
        control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        control_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        control_scroll.setMaximumWidth(400)
        control_scroll.setMinimumWidth(350)
        control_scroll.setFrameShape(QFrame.Shape.NoFrame)
        control_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f5f5f0;
            }
            QScrollBar:vertical {
                border: none;
                background: #e8e8e5;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #c4a574;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #b89560;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Connect control panel signals
        self.control_panel.files_loaded.connect(self.on_files_loaded)
        self.control_panel.error_dataset.connect(self.add_error_tab)
        self.control_panel.dataset_loaded_successfully.connect(self.replace_error_tab_with_dataset)
        self.control_panel.update_error_tab_message.connect(self.update_error_tab_message)

        # Top-level tab widget with two main tabs
        self.top_tabs = QTabWidget()

        # === INDIVIDUAL SAMPLES TAB ===
        samples_container = QWidget()
        samples_layout = QVBoxLayout(samples_container)

        # Tab widget for individual datasets
        self.dataset_tabs_widget = QTabWidget()
        self.dataset_tabs_widget.setTabsClosable(True)
        self.dataset_tabs_widget.tabCloseRequested.connect(self.close_dataset_tab)

        # Compact styling for dataset tabs
        self.dataset_tabs_widget.setStyleSheet("""
            QTabBar::tab {
                padding: 3px 8px;
                font-size: 9px;
                min-height: 18px;
                max-height: 22px;
            }
        """)

        # Add welcome widget as the first tab
        recent_files = self._load_recent_files()
        self.welcome_widget = WelcomeWidget(recent_files=recent_files)

        # Connect welcome widget signals
        self.welcome_widget.load_files_requested.connect(self.on_welcome_load_files)
        self.welcome_widget.load_sample_data_requested.connect(self.on_welcome_load_sample)
        self.welcome_widget.open_recent_file_requested.connect(self.on_welcome_open_recent)
        self.welcome_widget.open_help_topic_requested.connect(self.on_welcome_open_help)
        self.welcome_widget.dont_show_again_changed.connect(self.on_welcome_dont_show_again)
        self.welcome_widget.clear_sessions_requested.connect(self.on_clear_sessions)

        self.dataset_tabs_widget.addTab(self.welcome_widget, "🏠 Welcome")
        # Make welcome tab non-closable
        self.dataset_tabs_widget.tabBar().setTabButton(0, self.dataset_tabs_widget.tabBar().ButtonPosition.RightSide, None)

        samples_layout.addWidget(self.dataset_tabs_widget)

        # === COMPARISON TAB ===
        self.comparison_tab = ComparisonTab()

        # === REPORTING TAB ===
        self.reporting_tab = ReportingTab()

        # === EXPORT TAB ===
        self.export_tab = ExportTab()

        # Add all to top-level tabs
        self.top_tabs.addTab(samples_container, "📊 Individual Samples")
        self.top_tabs.addTab(self.comparison_tab, "🔍 Comparison")
        self.top_tabs.addTab(self.reporting_tab, "📝 Reports")
        self.top_tabs.addTab(self.export_tab, "💾 Export")

        # Style the top tabs with reduced padding
        self.top_tabs.setStyleSheet("""
            QTabWidget::tab-bar {
                left: 5px;
            }
            QTabBar::tab {
                background: #d2b48c;
                padding: 4px 12px;
                margin-right: 2px;
                font-weight: bold;
                font-size: 10px;
                min-height: 20px;
                max-height: 25px;
            }
            QTabBar::tab:selected {
                background: #6b8e23;
                color: white;
            }
            QTabBar::tab:hover {
                background: #ddbf94;
            }
        """)

        # Connect to update comparison when switching to comparison tab
        self.top_tabs.currentChanged.connect(self.on_top_tab_changed)

        # Add to splitter
        splitter.addWidget(control_scroll)
        splitter.addWidget(self.top_tabs)

        # Set splitter proportions
        splitter.setStretchFactor(0, 0)  # Control panel - no stretch
        splitter.setStretchFactor(1, 1)  # Tab area - stretch

        main_layout.addWidget(splitter)

    def setup_menus(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        if menubar is None:
            return

        # File menu
        file_menu = menubar.addMenu("&File")
        if file_menu is not None:
            export_results_action = QAction("Export &Results...", self)
            export_results_action.setShortcut("Ctrl+E")
            export_results_action.triggered.connect(self.export_results)
            file_menu.addAction(export_results_action)

            export_plot_action = QAction("Export &Plot...", self)
            export_plot_action.triggered.connect(self.export_plot)
            file_menu.addAction(export_plot_action)

            file_menu.addSeparator()

            exit_action = QAction("E&xit", self)
            exit_action.setShortcut("Ctrl+Q")
            exit_action.triggered.connect(self.close)
            file_menu.addAction(exit_action)

        # Analysis menu
        analysis_menu = menubar.addMenu("&Analysis")
        if analysis_menu is not None:
            calculate_action = QAction("&Calculate K Values", self)
            calculate_action.setShortcut("Ctrl+K")
            calculate_action.triggered.connect(self.calculate_all_k_values)
            analysis_menu.addAction(calculate_action)

            analysis_menu.addSeparator()

            update_comparison_action = QAction("&Update Comparison", self)
            update_comparison_action.triggered.connect(self.update_comparison)
            analysis_menu.addAction(update_comparison_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        if help_menu is not None:
            help_topics_action = QAction("📚 &Help Topics", self)
            help_topics_action.setShortcut("F1")
            help_topics_action.triggered.connect(self.show_help)
            help_menu.addAction(help_topics_action)

            help_menu.addSeparator()

            about_action = QAction("&About", self)
            about_action.triggered.connect(self.show_about)
            help_menu.addAction(about_action)

    # Toolbar removed - Help and About buttons are now in the sidebar
    # The setup_toolbar method is no longer used

    def setup_statusbar(self):
        """Setup status bar with progress indicator"""
        # Add progress bar to status bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)

        self._show_status_message("Ready - Add files to begin analysis")

    def on_welcome_load_files(self):
        """Handle 'Load Files' button click from welcome widget"""
        self.control_panel.add_files()
        self._show_status_message("Select files to load...")

    def on_welcome_load_sample(self):
        """Handle 'Load Sample Data' button click from welcome widget"""
        # Try to load sample data from test_data folder
        import os
        test_data_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_data")

        if os.path.exists(test_data_folder):
            # Find first CSV file in test_data
            for file in os.listdir(test_data_folder):
                if file.endswith('.csv'):
                    sample_path = os.path.join(test_data_folder, file)
                    try:
                        dataset = self.data_loader.load_file(sample_path)
                        self.add_dataset_tab(dataset)
                        self._save_recent_file(sample_path)
                        self._update_welcome_recent_files()
                        self._show_status_message(f"Loaded sample data: {file}")
                        return
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to load sample data:\n{str(e)}")
                        return

        QMessageBox.information(
            self,
            "No Sample Data",
            "No sample data files found. Use 'Load Files' to load your own data."
        )

    def on_welcome_open_recent(self, file_path: str):
        """Handle opening a recent file from welcome widget"""
        try:
            if os.path.exists(file_path):
                dataset = self.data_loader.load_file(file_path)
                dataset.file_path = file_path  # Store the file path in dataset
                self.add_dataset_tab(dataset)

                # Register with control panel so it shows in Sample Management
                self.control_panel.register_external_file(file_path, dataset)

                self._save_recent_file(file_path)
                self._update_welcome_recent_files()
                self._show_status_message(f"Opened: {os.path.basename(file_path)}")
            else:
                QMessageBox.warning(self, "File Not Found", f"The file no longer exists:\n{file_path}")
                self._remove_recent_file(file_path)
                self._update_welcome_recent_files()
        except Exception as e:
            QMessageBox.critical(self, "Error Loading File", f"Failed to load file:\n{str(e)}")

    def on_welcome_open_help(self, topic_file: str):
        """Handle opening help topic from welcome widget"""
        # Use existing help system
        from gui.help_dialog import HelpDialog

        help_dialog = HelpDialog(self)
        help_dialog.show_help_page(topic_file)
        help_dialog.exec()

    def on_welcome_dont_show_again(self, dont_show: bool):
        """Handle 'don't show again' checkbox change"""
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        settings.setValue("welcome_screen/dont_show", dont_show)
        if dont_show:
            self._show_status_message("Welcome screen will be hidden on next startup")

    def on_clear_sessions(self):
        """Clear all saved sessions"""
        reply = QMessageBox.question(
            self,
            "Clear Sessions",
            "Are you sure you want to clear all saved sessions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            settings = QSettings("GrainSizeAnalysis", "MainWindow")
            settings.setValue("recent_sessions", [])

            # Recreate welcome widget to reflect changes
            self._refresh_welcome_widget()

            self._show_status_message("All sessions cleared")

    def _load_recent_files(self) -> List[str]:
        """Load recent files from settings"""
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        recent = settings.value("recent_files", [])
        if isinstance(recent, str):
            return [recent] if recent else []
        return recent if recent else []

    def _save_recent_file(self, file_path: str):
        """Add file to recent files list"""
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        recent = self._load_recent_files()

        # Remove if already exists
        if file_path in recent:
            recent.remove(file_path)

        # Add to beginning
        recent.insert(0, file_path)

        # Keep only last 10
        recent = recent[:10]

        settings.setValue("recent_files", recent)

    def _save_current_session(self):
        """Save current loaded files as a session"""
        if not self.dataset_tabs:
            return

        settings = QSettings("GrainSizeAnalysis", "MainWindow")

        # Get all currently loaded files
        current_files = []
        for tab in self.dataset_tabs:
            dataset = tab.get_dataset()
            if hasattr(dataset, 'file_path') and dataset.file_path:
                current_files.append(dataset.file_path)

        if not current_files:
            return

        # Create session entry
        from datetime import datetime
        session = {
            'name': f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            'date': datetime.now().strftime('%Y-%m-%d'),
            'files': current_files,
            'timestamp': datetime.now().isoformat()
        }

        # Load existing sessions
        recent_sessions = settings.value("recent_sessions", [])
        if not isinstance(recent_sessions, list):
            recent_sessions = []

        # Check if this exact session already exists
        session_exists = False
        for existing in recent_sessions:
            if set(existing.get('files', [])) == set(current_files):
                session_exists = True
                break

        if not session_exists:
            # Add to beginning
            recent_sessions.insert(0, session)

            # Keep only last 10 sessions
            recent_sessions = recent_sessions[:10]

            settings.setValue("recent_sessions", recent_sessions)
            self._update_welcome_recent_files()

    def _remove_recent_file(self, file_path: str):
        """Remove file from recent files list"""
        settings = QSettings("GrainSizeAnalysis", "MainWindow")
        recent = self._load_recent_files()

        if file_path in recent:
            recent.remove(file_path)
            settings.setValue("recent_files", recent)

    def _update_welcome_recent_files(self):
        """Update welcome widget with current recent files"""
        recent_files = self._load_recent_files()
        self.welcome_widget.update_recent_files(recent_files)

    def _refresh_welcome_widget(self):
        """Refresh the welcome widget to reflect updated data"""
        # Remove old welcome widget
        self.dataset_tabs_widget.removeTab(0)

        # Create new welcome widget with updated data
        recent_files = self._load_recent_files()
        self.welcome_widget = WelcomeWidget(recent_files=recent_files)

        # Reconnect signals
        self.welcome_widget.load_files_requested.connect(self.on_welcome_load_files)
        self.welcome_widget.load_sample_data_requested.connect(self.on_welcome_load_sample)
        self.welcome_widget.open_recent_file_requested.connect(self.on_welcome_open_recent)
        self.welcome_widget.open_help_topic_requested.connect(self.on_welcome_open_help)
        self.welcome_widget.dont_show_again_changed.connect(self.on_welcome_dont_show_again)
        self.welcome_widget.clear_sessions_requested.connect(self.on_clear_sessions)

        # Insert at index 0
        self.dataset_tabs_widget.insertTab(0, self.welcome_widget, "🏠 Welcome")

        # Make welcome tab non-closable
        self.dataset_tabs_widget.tabBar().setTabButton(0, self.dataset_tabs_widget.tabBar().ButtonPosition.RightSide, None)

        # Switch to welcome tab
        self.dataset_tabs_widget.setCurrentIndex(0)

    def on_files_loaded(self, sample_names: List[str]):
        """Handle files loaded from control panel"""
        try:
            loaded_samples = self.control_panel.get_loaded_samples()

            # Show progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(len(sample_names))
            self.progress_bar.setValue(0)

            for i, sample_name in enumerate(sample_names):
                if sample_name in loaded_samples:
                    file_path = loaded_samples[sample_name]['file_path']

                    try:
                        # Load the dataset
                        dataset = self.data_loader.load_file(file_path)

                        # Create a new dataset tab
                        self.add_dataset_tab(dataset)

                        # Update control panel status
                        self.control_panel.set_sample_status(sample_name, "✅ Loaded")

                    except Exception as e:
                        print(f"Failed to load {file_path}: {e}")
                        # Try with column mapper as fallback
                        dataset = self.load_file_with_mapper(file_path)
                        if dataset:
                            self.add_dataset_tab(dataset)
                            self.control_panel.set_sample_status(sample_name, "✅ Loaded")
                        else:
                            self.control_panel.set_sample_status(sample_name, "❌ Failed")

                self.progress_bar.setValue(i + 1)

            self._show_status_message(f"Loaded {len(sample_names)} dataset(s)")

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Error loading files:\n{str(e)}")
            self._show_status_message("Error loading files")
        finally:
            self.progress_bar.setVisible(False)

    def load_file_with_mapper(self, file_path: str) -> Optional[GrainSizeData]:
        """Load a file using the column mapper dialog"""
        from gui.column_mapper import ColumnMapperDialog

        dialog = ColumnMapperDialog(file_path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                mapping_result = dialog.get_mapping_result()

                # Create GrainSizeData object from mapped data
                dataset = GrainSizeData(
                    sample_name=mapping_result['sample_name'],
                    particle_sizes=mapping_result['particle_sizes'],
                    percent_passing=mapping_result['percent_passing'],
                    temperature=mapping_result.get('temperature', 20.0),
                    porosity=mapping_result.get('porosity', 0.4)
                )

                return dataset

            except Exception as e:
                QMessageBox.critical(self, "Mapping Error", f"Error creating dataset:\n{str(e)}")
                return None

        return None

    def add_dataset_tab(self, dataset: GrainSizeData):
        """Add a new dataset tab"""
        self.dataset_counter += 1

        # Create new dataset tab
        dataset_tab = DatasetTab(dataset)

        # Set parameters from control panel
        temperature = self.control_panel.temp_spinbox.value()
        dataset_tab.set_parameters(temperature)

        # Connect calculation_complete signal to update export tab
        dataset_tab.calculation_complete.connect(self._on_calculation_complete)

        # Add to tabs
        self.dataset_tabs_widget.addTab(dataset_tab, f"📁 {dataset.sample_name}")
        self.dataset_tabs.append(dataset_tab)

        # Switch to the new tab
        self.dataset_tabs_widget.setCurrentIndex(self.dataset_tabs_widget.count() - 1)

        # Update comparison, reporting, and export tabs
        self.comparison_tab.set_dataset_tabs(self.dataset_tabs)
        self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
        self._update_export_tab()

        # Add to recent files if it has a file path
        if hasattr(dataset, 'file_path') and dataset.file_path:
            self._save_recent_file(dataset.file_path)

        # Automatically calculate K values for all methods when dataset is added
        selected_methods = self.k_calculator.get_all_method_names()
        dataset_tab.calculate_k_values(selected_methods)

        self._show_status_message(f"Added dataset: {dataset.sample_name} - K values calculated")

    def add_error_tab(self, file_path: str, error_message: str):
        """Add an error tab for a failed dataset"""
        # Create error tab
        error_tab = ErrorTab(file_path, error_message, self)

        # Connect to dataset fixed signal
        error_tab.dataset_fixed.connect(self.on_dataset_fixed)

        # Add tab with error styling
        file_name = os.path.basename(file_path)
        tab_title = f"❌ {file_name}"

        # Add to tabs with red styling
        index = self.dataset_tabs_widget.addTab(error_tab, tab_title)

        # Style the tab to indicate error
        tab_bar = self.dataset_tabs_widget.tabBar()
        tab_bar.setTabTextColor(index, QColor(211, 47, 47))  # Red color

        # Switch to the new tab
        self.dataset_tabs_widget.setCurrentIndex(index)

        self._show_status_message(f"Error loading: {file_name} - click tab to fix")

    def on_dataset_fixed(self, dataset: GrainSizeData, original_file_path: str):
        """Handle when an error tab successfully fixes a dataset"""
        # Find and remove the error tab
        for i in range(self.dataset_tabs_widget.count()):
            widget = self.dataset_tabs_widget.widget(i)
            if isinstance(widget, ErrorTab) and widget.file_path == original_file_path:
                self.dataset_tabs_widget.removeTab(i)
                break

        # Add the fixed dataset as a normal tab
        self.add_dataset_tab(dataset)

        self._show_status_message(f"Fixed and loaded: {dataset.sample_name}")

    def replace_error_tab_with_dataset(self, dataset: GrainSizeData, file_path: str):
        """Replace an error tab with a successful dataset tab"""
        # Find the error tab with this file path
        for i in range(self.dataset_tabs_widget.count()):
            widget = self.dataset_tabs_widget.widget(i)
            if isinstance(widget, ErrorTab) and widget.file_path == file_path:
                # Remove the error tab
                self.dataset_tabs_widget.removeTab(i)
                # Add the dataset tab
                self.add_dataset_tab(dataset)
                break

    def update_error_tab_message(self, file_path: str, error_message: str):
        """Update an existing error tab with a new error message"""
        # Find the error tab with this file path
        for i in range(self.dataset_tabs_widget.count()):
            widget = self.dataset_tabs_widget.widget(i)
            if isinstance(widget, ErrorTab) and widget.file_path == file_path:
                # Update the error message and refresh preview
                widget.update_error_message(error_message)
                widget.load_file_preview()

                # Update tab title to show error
                file_name = os.path.basename(file_path)
                self.dataset_tabs_widget.setTabText(i, f"❌ {file_name}")
                tab_bar = self.dataset_tabs_widget.tabBar()
                tab_bar.setTabTextColor(i, QColor(211, 47, 47))
                break

    def close_dataset_tab(self, index: int):
        """Close a dataset tab"""
        # Prevent closing the welcome tab (always at index 0)
        if index == 0:
            return

        if self.dataset_tabs_widget.count() > 0:
            # Adjust index for dataset_tabs list (welcome tab is not in the list)
            # Widget index 1 = dataset_tabs[0], widget index 2 = dataset_tabs[1], etc.
            dataset_index = index - 1

            # Remove from list
            if dataset_index >= 0 and dataset_index < len(self.dataset_tabs):
                removed_tab = self.dataset_tabs.pop(dataset_index)

            # Remove from widget
            self.dataset_tabs_widget.removeTab(index)

            # Update comparison, reporting, and export tabs
            self.comparison_tab.set_dataset_tabs(self.dataset_tabs)
            self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
            self._update_export_tab()

            self._show_status_message(f"Closed dataset tab")

    def on_top_tab_changed(self, index: int):
        """Handle top-level tab change"""
        if index == 1:  # Comparison tab
            # Update comparison when switching to it
            if len(self.dataset_tabs) >= 2:
                self.comparison_tab.update_comparison()
        elif index == 2:  # Reporting tab
            # Update reporting tab with current datasets
            self.reporting_tab.set_dataset_tabs(self.dataset_tabs)

    def calculate_all_k_values(self):
        """Calculate K values for all datasets"""
        if not self.dataset_tabs:
            QMessageBox.information(self, "No Data", "Please load datasets first")
            return

        # Get all available methods from calculator
        from k_calculations import KCalculator
        calculator = KCalculator()
        selected_methods = calculator.get_all_method_names()

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.dataset_tabs))
        self.progress_bar.setValue(0)

        try:
            # Get current parameters from control panel
            temperature = self.control_panel.temp_spinbox.value()

            # Calculate for each dataset
            for i, dataset_tab in enumerate(self.dataset_tabs):
                # Update parameters
                dataset_tab.set_parameters(temperature)

                # Calculate K values
                dataset_tab.calculate_k_values(selected_methods)

                self.progress_bar.setValue(i + 1)

            self._show_status_message(f"Calculated K values for {len(self.dataset_tabs)} dataset(s)")

            # Update comparison if on comparison tab
            if self.top_tabs.currentIndex() == 1:
                self.comparison_tab.update_comparison()

        except Exception as e:
            QMessageBox.critical(self, "Calculation Error",
                               f"Error during calculations:\n{str(e)}")
            self._show_status_message("Error in calculations")
        finally:
            self.progress_bar.setVisible(False)

    def update_comparison(self):
        """Update the comparison tab"""
        if len(self.dataset_tabs) < 2:
            QMessageBox.information(self, "Insufficient Data",
                                  "Load at least 2 datasets to compare")
            return

        # Switch to comparison tab
        self.top_tabs.setCurrentIndex(1)

        # Update comparison
        self.comparison_tab.update_comparison()

    def export_current(self):
        """Export current view (results or plot based on context)"""
        if self.top_tabs.currentIndex() == 0:  # Individual samples tab
            current_index = self.dataset_tabs_widget.currentIndex()
            if current_index >= 0 and current_index < len(self.dataset_tabs):
                # Try to export results first, fallback to plot
                try:
                    self.dataset_tabs[current_index].export_results()
                except:
                    self.dataset_tabs[current_index].plot_workspace.export_plot("png")
        else:  # Comparison or reporting tab
            self.comparison_tab.export_comparison()

    def export_results(self):
        """Export results for current dataset"""
        if self.top_tabs.currentIndex() == 0:  # Individual samples tab
            current_index = self.dataset_tabs_widget.currentIndex()
            if current_index >= 0 and current_index < len(self.dataset_tabs):
                self.dataset_tabs[current_index].export_results()
        else:  # Comparison tab
            self.comparison_tab.export_comparison()

    def export_plot(self):
        """Export plot for current view"""
        if self.top_tabs.currentIndex() == 0:  # Individual samples tab
            current_index = self.dataset_tabs_widget.currentIndex()
            if current_index >= 0 and current_index < len(self.dataset_tabs):
                # Get the plot workspace from the dataset tab
                dataset_tab = self.dataset_tabs[current_index]
                dataset_tab.plot_workspace.export_plot("png")
        else:  # Comparison tab
            self.comparison_tab.export_comparison()

    def show_help(self):
        """Show comprehensive help dialog"""
        from gui.help_dialog import HelpDialog
        help_dialog = HelpDialog(self)
        help_dialog.exec()

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About",
            """<h3>Grain Size Analysis Tool</h3>
            <p>Version 0.9.0-beta</p>
            <p>A comprehensive tool for grain size distribution analysis
            and hydraulic conductivity calculations.</p>
            <p>Features:</p>
            <ul>
            <li>Multiple dataset management</li>
            <li>14+ K-calculation methods</li>
            <li>Interactive plots with controls</li>
            <li>Dataset comparison tools</li>
            <li>Statistical analysis</li>
            <li>Comprehensive help system</li>
            </ul>
            <p>© 2024 - Geotechnical Analysis Suite</p>
            <p><em>Press F1 for detailed help topics</em></p>""")

    def _show_status_message(self, message: str, timeout: int = 0):
        """Show a message in the status bar"""
        self.statusBar().showMessage(message, timeout)

    def closeEvent(self, event):
        """Handle window close event - save current session before closing"""
        # Save the current session if there are loaded datasets
        if self.dataset_tabs:
            self._save_current_session()

        # Accept the close event
        event.accept()

    def _on_calculation_complete(self, sample_name: str, results):
        """Handle calculation complete signal from dataset tab"""
        # Update export tab with latest results
        self._update_export_tab()

    def _update_export_tab(self):
        """Update the export tab with current datasets"""
        # Build list of (name, GrainSizeData, results) tuples
        datasets = []
        for tab in self.dataset_tabs:
            name = tab.get_dataset_name()
            dataset = tab.get_dataset()
            results = tab.get_results()
            datasets.append((name, dataset, results))

        # Update export tab
        self.export_tab.update_datasets(datasets)
