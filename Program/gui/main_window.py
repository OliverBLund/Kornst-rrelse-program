"""
Main window for the Grain Size Analysis application - New Architecture
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QMenuBar, QToolBar, QStatusBar, QSplitter, 
    QTabWidget, QMessageBox, QProgressBar,
    QFileDialog, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from typing import List, Dict, Optional
import os

# Import our modules
from gui.control_panel import ControlPanel
from gui.dataset_tab import DatasetTab
from gui.comparison_tab import ComparisonTab
from gui.reporting_tab import ReportingTab
from data_loader import DataLoader, GrainSizeData
from k_calculations import KCalculator


class MainWindow(QMainWindow):
    """Main application window with new two-level tab architecture"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grain Size Analysis - Hydraulic Conductivity Calculator")
        self.setGeometry(100, 100, 1400, 800)
        
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
        self.setup_menus()
        self.setup_toolbar()
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
        
        # Control panel (simplified)
        self.control_panel = ControlPanel()
        self.control_panel.setMaximumWidth(250)
        
        # Connect control panel signals
        self.control_panel.files_loaded.connect(self.on_files_loaded)
        
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
        
        samples_layout.addWidget(self.dataset_tabs_widget)
        
        # === COMPARISON TAB ===
        self.comparison_tab = ComparisonTab()
        
        # === REPORTING TAB ===
        self.reporting_tab = ReportingTab()
        
        # Add all to top-level tabs
        self.top_tabs.addTab(samples_container, "📊 Individual Samples")
        self.top_tabs.addTab(self.comparison_tab, "🔍 Comparison")
        self.top_tabs.addTab(self.reporting_tab, "📝 Reports")
        
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
        splitter.addWidget(self.control_panel)
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
            about_action = QAction("&About", self)
            about_action.triggered.connect(self.show_about)
            help_menu.addAction(about_action)
    
    def setup_toolbar(self):
        """Setup simplified toolbar"""
        toolbar = QToolBar("Main Tools")
        self.addToolBar(toolbar)
        
        # Export options
        export_results_action = QAction("Export Results", self)
        export_results_action.triggered.connect(self.export_results)
        toolbar.addAction(export_results_action)
        
        export_plot_action = QAction("Export Plot", self)
        export_plot_action.triggered.connect(self.export_plot)
        toolbar.addAction(export_plot_action)
        
        toolbar.addSeparator()
        
        # Calculate action
        calculate_action = QAction("Calculate All", self)
        calculate_action.triggered.connect(self.calculate_all_k_values)
        toolbar.addAction(calculate_action)
    
    def setup_statusbar(self):
        """Setup status bar with progress indicator"""
        # Add progress bar to status bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)
        
        self._show_status_message("Ready - Add files to begin analysis")
    
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
        porosity = self.control_panel.porosity_spinbox.value()
        dataset_tab.set_parameters(temperature, porosity)
        
        # Add to tabs
        self.dataset_tabs_widget.addTab(dataset_tab, f"📁 {dataset.sample_name}")
        self.dataset_tabs.append(dataset_tab)
        
        # Switch to the new tab
        self.dataset_tabs_widget.setCurrentIndex(self.dataset_tabs_widget.count() - 1)
        
        # Update comparison and reporting tabs
        self.comparison_tab.set_dataset_tabs(self.dataset_tabs)
        self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
        
        self._show_status_message(f"Added dataset: {dataset.sample_name}")
    
    def close_dataset_tab(self, index: int):
        """Close a dataset tab"""
        if self.dataset_tabs_widget.count() > 0:
            # Remove from list
            if index < len(self.dataset_tabs):
                removed_tab = self.dataset_tabs.pop(index)
            
            # Remove from widget
            self.dataset_tabs_widget.removeTab(index)
            
            # Update comparison and reporting tabs
            self.comparison_tab.set_dataset_tabs(self.dataset_tabs)
            self.reporting_tab.set_dataset_tabs(self.dataset_tabs)
            
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
        
        # Get selected methods from first dataset tab (or use defaults)
        selected_methods = ["Hazen", "Terzaghi", "Beyer", "Slichter", 
                          "Kozeny-Carman", "Shepherd", "USBR", "Zunker", 
                          "Zamarin", "Sauerbrei"]
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.dataset_tabs))
        self.progress_bar.setValue(0)
        
        try:
            # Get current parameters from control panel
            temperature = self.control_panel.temp_spinbox.value()
            porosity = self.control_panel.porosity_spinbox.value()
            
            # Calculate for each dataset
            for i, dataset_tab in enumerate(self.dataset_tabs):
                # Update parameters
                dataset_tab.set_parameters(temperature, porosity)
                
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
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About",
            """<h3>Grain Size Analysis Tool</h3>
            <p>Version 2.0 - New Architecture</p>
            <p>A comprehensive tool for grain size distribution analysis 
            and hydraulic conductivity calculations.</p>
            <p>Features:</p>
            <ul>
            <li>Multiple dataset management</li>
            <li>12+ K-calculation methods</li>
            <li>Interactive plots with controls</li>
            <li>Dataset comparison tools</li>
            <li>Statistical analysis</li>
            </ul>
            <p>© 2024 - Geotechnical Analysis Suite</p>""")
    
    def _show_status_message(self, message: str, timeout: int = 0):
        """Show a message in the status bar"""
        self.statusBar().showMessage(message, timeout)