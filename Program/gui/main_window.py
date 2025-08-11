"""
Main window for the Grain Size Analysis application
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                            QMenuBar, QToolBar, QStatusBar, QSplitter, 
                            QCheckBox, QScrollArea, QFrame, QTabWidget,
                            QTableWidget, QTableWidgetItem, QTextEdit,
                            QGroupBox, QDialog, QDialogButtonBox,
                            QGridLayout, QLabel, QPushButton, QComboBox,
                            QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from typing import Optional, List
import os

from gui.control_panel import ControlPanel
from gui.plot_widget import PlotWidget
from data_loader import DataLoader, GrainSizeData
from k_calculations import KCalculator, KCalculationResult, CalculationStatus


def format_grain_size_stats(dataset: GrainSizeData) -> str:
    """Format grain size statistics for display"""
    stats_text = f"Sample: {dataset.sample_name}\n"
    stats_text += "=" * 50 + "\n\n"
    
    # Basic info
    stats_text += f"Temperature: {dataset.temperature}°C\n"
    stats_text += f"Porosity: {dataset.porosity}\n"
    stats_text += f"Data Points: {len(dataset.particle_sizes)}\n\n"
    
    # Grain size statistics
    stats_text += "Characteristic Grain Sizes:\n"
    stats_text += "-" * 30 + "\n"
    
    d10 = dataset.get_d10()
    d20 = dataset.get_d20()
    d30 = dataset.get_d30()
    d50 = dataset.get_d50()
    d60 = dataset.get_d60()
    
    stats_text += f"D10: {d10:.3f} mm\n" if d10 else "D10: N/A\n"
    stats_text += f"D20: {d20:.3f} mm\n" if d20 else "D20: N/A\n"
    stats_text += f"D30: {d30:.3f} mm\n" if d30 else "D30: N/A\n"
    stats_text += f"D50: {d50:.3f} mm\n" if d50 else "D50: N/A\n"
    stats_text += f"D60: {d60:.3f} mm\n" if d60 else "D60: N/A\n"
    
    # Derived parameters
    if d10 and d60:
        cu = d60 / d10
        stats_text += f"\nUniformity Coefficient (Cu): {cu:.2f}\n"
    if d10 and d30 and d60:
        cc = (d30 ** 2) / (d10 * d60)
        stats_text += f"Coefficient of Curvature (Cc): {cc:.3f}\n"
    
    # Soil classification
    stats_text += f"\nSoil Classification: {dataset.classify_soil()}\n"
    
    # Size range
    if dataset.particle_sizes:
        min_size = min(dataset.particle_sizes)
        max_size = max(dataset.particle_sizes)
        stats_text += f"Size Range: {min_size:.3f} - {max_size:.3f} mm\n"
    
    return stats_text


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grain Size Analysis - Hydraulic Conductivity Calculator")
        self.setGeometry(100, 100, 1400, 800)
        
        # Apply professional geotechnical styling to main window
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f0;
            }
            QTabWidget::pane {
                border: 2px solid #8b7355;
                border-radius: 8px;
                margin-top: -1px;
                background-color: #fafaf7;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background-color: #d2b48c;
                border: 1px solid #8b7355;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 20px;
                margin-right: 2px;
                font-weight: bold;
                color: #5d4e37;
                min-width: 120px;
            }
            QTabBar::tab:selected {
                background-color: #fafaf7;
                border-bottom: 2px solid #fafaf7;
                color: #2f2f2f;
            }
            QTabBar::tab:hover {
                background-color: #ddbf94;
            }
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #8b7355;
                border-radius: 4px;
                gridline-color: #d4c4a8;
                selection-background-color: #d2b48c;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e8e8e5;
            }
            QTableWidget::item:selected {
                background-color: #d2b48c;
                color: #2f2f2f;
            }
            QHeaderView::section {
                background-color: #8b7355;
                color: white;
                padding: 8px;
                border: 1px solid #6b5b47;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #8b7355;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                line-height: 1.4;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #8b7355;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #fafaf7;
                font-size: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 15px;
                top: 2px;
                padding: 2px 8px 2px 8px;
                color: #5d4e37;
                background-color: #fafaf7;
                border: 1px solid #8b7355;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton {
                background-color: #d2b48c;
                border: 1px solid #8b7355;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                color: #2f2f2f;
            }
            QPushButton:hover {
                background-color: #ddbf94;
                border-color: #6b5b47;
            }
            QPushButton:pressed {
                background-color: #c4a574;
            }
        """)
        
        self.setup_ui()
        self.setup_menus()
        self.setup_toolbar()
        self.setup_statusbar()
        
        # Initialize data processing components
        self.data_loader = DataLoader()
        self.k_calculator = KCalculator()
        self.current_datasets: List[GrainSizeData] = []
        self.current_results: List[KCalculationResult] = []
        
        # Set initial empty state
        self.set_empty_state()
        
    def setup_ui(self):
        """Setup the main UI layout"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main horizontal layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Control Panel (reduced width)
        self.control_panel = ControlPanel()
        self.control_panel.setFixedWidth(280)
        self.control_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        
        # Connect control panel signals
        self.control_panel.files_loaded.connect(self.on_files_loaded_from_control_panel)
        self.control_panel.analysis_requested.connect(self.on_analysis_requested_from_control_panel)
        self.control_panel.sample_selected.connect(self.on_sample_selected_from_control_panel)
        
        # Right panel - Tabbed interface
        self.tab_widget = QTabWidget()
        
        # Plot tab
        self.plot_widget = PlotWidget()
        self.tab_widget.addTab(self.plot_widget, "Plots")
        
        # Results tab
        self.results_widget = self.create_results_tab()
        self.tab_widget.addTab(self.results_widget, "Results")
        
        # Statistics tab
        self.statistics_widget = self.create_statistics_tab()
        self.tab_widget.addTab(self.statistics_widget, "Statistics")
        
        # Add panels to splitter
        splitter.addWidget(self.control_panel)
        splitter.addWidget(self.tab_widget)
        
        # Set splitter proportions (control panel should not resize)
        splitter.setStretchFactor(0, 0)  # Control panel - no stretch
        splitter.setStretchFactor(1, 1)  # Tab area - stretch
        
        main_layout.addWidget(splitter)
        
        # Initialize calculation methods (hidden by default)
        self.init_calculation_methods()
        
    def create_results_tab(self):
        """Create the results tab widget"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Results table
        results_group = QGroupBox("Hydraulic Conductivity Results")
        results_layout = QVBoxLayout(results_group)
        
        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Method", "K (m/s)", "Formula", "Status"])
        
        # Set header stretch after creation
        header = self.results_table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        
        results_layout.addWidget(self.results_table)
        layout.addWidget(results_group)
        
        # Method selection controls
        method_group = QGroupBox("Calculation Methods")
        method_layout = QVBoxLayout(method_group)
        
        method_buttons_layout = QHBoxLayout()
        select_methods_btn = QPushButton("Select Methods...")
        select_methods_btn.clicked.connect(self.show_method_selection_dialog)
        
        calculate_btn = QPushButton("Calculate K Values")
        calculate_btn.clicked.connect(self.calculate_k_values)
        
        self.selected_methods_label = QLabel("Selected methods: All (10)")
        
        method_buttons_layout.addWidget(select_methods_btn)
        method_buttons_layout.addWidget(calculate_btn)
        method_buttons_layout.addStretch()
        
        method_layout.addWidget(self.selected_methods_label)
        method_layout.addLayout(method_buttons_layout)
        layout.addWidget(method_group)
        
        layout.addStretch()
        return widget
        
    def create_statistics_tab(self):
        """Create the statistics tab widget"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Grain size statistics
        grain_stats_group = QGroupBox("Grain Size Statistics")
        grain_stats_layout = QVBoxLayout(grain_stats_group)
        
        self.grain_stats_text = QTextEdit()
        self.grain_stats_text.setPlaceholderText("Grain size statistics will appear here after data is loaded...")
        self.grain_stats_text.setReadOnly(True)
        self.grain_stats_text.setMaximumHeight(200)
        
        grain_stats_layout.addWidget(self.grain_stats_text)
        layout.addWidget(grain_stats_group)
        
        # K value statistics
        k_stats_group = QGroupBox("Hydraulic Conductivity Statistics")
        k_stats_layout = QVBoxLayout(k_stats_group)
        
        self.k_stats_text = QTextEdit()
        self.k_stats_text.setPlaceholderText("K value statistics will appear here after calculations...")
        self.k_stats_text.setReadOnly(True)
        self.k_stats_text.setMaximumHeight(200)
        
        k_stats_layout.addWidget(self.k_stats_text)
        layout.addWidget(k_stats_group)
        
        # Summary statistics table
        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_group)
        
        self.summary_table = QTableWidget(0, 2)
        self.summary_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        
        # Set header stretch after creation
        header = self.summary_table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        self.summary_table.setMaximumHeight(150)
        
        summary_layout.addWidget(self.summary_table)
        layout.addWidget(summary_group)
        
        layout.addStretch()
        return widget
        
    def init_calculation_methods(self):
        """Initialize calculation methods data"""
        self.available_methods = {
            "Hazen": {"enabled": True, "formula": "K = C * d10²"},
            "Terzaghi": {"enabled": True, "formula": "K = C * (n-0.13) * d10²"},
            "Beyer": {"enabled": True, "formula": "K = C * d10^1.5"},
            "Slichter": {"enabled": True, "formula": "K = C * n³ * d10²"},
            "Kozeny-Carman": {"enabled": True, "formula": "K = C * n³/(1-n)² * d10²"},
            "Shepherd": {"enabled": True, "formula": "K = C * d20²"},
            "Zunker": {"enabled": True, "formula": "K = C * (n/0.4)^3 * d10^1.8"},
            "Zamarin": {"enabled": True, "formula": "K = C * n^2.5 * d10²"},
            "USBR": {"enabled": True, "formula": "K = C * d20^1.3"},
            "Sauerbrei": {"enabled": True, "formula": "K = C * (n-0.07)^3 * d10²"}
        }
        self.update_selected_methods_label()
    
    def set_empty_state(self):
        """Set the application to empty state (no data loaded)"""
        # Clear results table
        self.results_table.setRowCount(0)
        
        # Set empty text for statistics
        self.grain_stats_text.setPlainText("")
        self.k_stats_text.setPlainText("")
        
        # Set initial summary showing empty state
        empty_summary_data = [
            ("📂 Data Status", "No data loaded"),
            ("🔬 Methods", "Select methods first"),
            ("📊 Samples", "0"),
            ("📈 K Results", "No calculations"),
            ("🌡️ Temperature", "Not set"),
            ("🕳️ Porosity", "Not set"),
            ("📏 Grain Range", "No data"),
            ("✅ Status", "Ready to load data")
        ]
        
        self.update_statistics(summary_data=empty_summary_data)
        
        # Set status message
        self._show_status_message("Ready - Load grain size data to begin analysis")
        
    def _show_status_message(self, message: str) -> None:
        """Safely show status message"""
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.showMessage(message)
        
    def setup_menus(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        if menubar is None:
            return
        
        # File menu
        file_menu = menubar.addMenu("&File")
        if file_menu is not None:
            open_action = QAction("&Open Data...", self)
            open_action.setShortcut("Ctrl+O")
            open_action.triggered.connect(self.open_data)
            file_menu.addAction(open_action)
            
            file_menu.addSeparator()
            
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
        
        # View menu
        view_menu = menubar.addMenu("&View")
        if view_menu is not None:
            reset_view_action = QAction("&Reset Plot View", self)
            reset_view_action.triggered.connect(self.plot_widget.reset_view)
            view_menu.addAction(reset_view_action)
        
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
        
        # File operations
        open_action = QAction("Open Data", self)
        open_action.triggered.connect(self.open_data)
        toolbar.addAction(open_action)
        
        toolbar.addSeparator()
        
        # Export options
        export_results_action = QAction("Export Results", self)
        export_results_action.triggered.connect(self.export_results)
        toolbar.addAction(export_results_action)

        export_plot_action = QAction("Export Plot", self)
        export_plot_action.triggered.connect(self.export_plot)
        toolbar.addAction(export_plot_action)

        # Sample selector for loaded datasets (hidden until data loaded)
        from PyQt6.QtWidgets import QLabel, QComboBox
        self.sample_selector_label = QLabel("Sample:")
        self.sample_selector = QComboBox()
        self.sample_selector.currentTextChanged.connect(self.on_sample_selector_changed)
        self.sample_selector_label.hide()
        self.sample_selector.hide()
        toolbar.addSeparator()
        toolbar.addWidget(self.sample_selector_label)
        toolbar.addWidget(self.sample_selector)
        # Map columns action
        self.map_columns_action = QAction("Map Columns", self)
        self.map_columns_action.triggered.connect(self.map_columns)
        self.map_columns_action.setEnabled(False)
        toolbar.addAction(self.map_columns_action)
        
    def show_method_selection_dialog(self):
        """Show dialog for selecting calculation methods"""
        dialog = MethodSelectionDialog(self.available_methods, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.available_methods = dialog.get_selected_methods()
            self.update_selected_methods_label()
            
    def update_selected_methods_label(self):
        """Update the label showing selected methods"""
        enabled_count = sum(1 for method_data in self.available_methods.values() if method_data["enabled"])
        total_count = len(self.available_methods)
        self.selected_methods_label.setText(f"Selected methods: {enabled_count}/{total_count}")
        
    def update_results_table(self, results):
        """Update the results table with calculation results"""
        self.results_table.setRowCount(len(results))
        
        # Method colors for table highlighting
        method_colors = {
            "Hazen": "#ffcccc",      # Light red
            "Terzaghi": "#ccffcc",   # Light green
            "Beyer": "#ccccff",      # Light blue
            "Slichter": "#ffeecc",   # Light orange
            "Kozeny-Carman": "#e6ccff", # Light purple
            "Shepherd": "#ffe6f2",      # Light pink
            "Zunker": "#ccffff",        # Light cyan
            "Zamarin": "#ffffcc",       # Light yellow
            "USBR": "#f2e6d9",          # Light brown
            "Sauerbrei": "#e6e6e6"      # Light gray
        }
        
        for i, (method, k_value, formula, status) in enumerate(results):
            # Method name with color background
            method_item = QTableWidgetItem(method)
            if method in method_colors:
                method_item.setBackground(QColor(method_colors[method]))
            self.results_table.setItem(i, 0, method_item)
            
            # K value
            k_item = QTableWidgetItem(f"{k_value:.2e}")
            if method in method_colors:
                k_item.setBackground(QColor(method_colors[method]))
            self.results_table.setItem(i, 1, k_item)
            
            # Formula
            formula_item = QTableWidgetItem(formula)
            if method in method_colors:
                formula_item.setBackground(QColor(method_colors[method]))
            self.results_table.setItem(i, 2, formula_item)
            
            # Status
            status_item = QTableWidgetItem(status)
            if method in method_colors:
                status_item.setBackground(QColor(method_colors[method]))
            # Color code status
            if status == "OK":
                status_item.setForeground(QColor("green"))
            elif status == "Warning":
                status_item.setForeground(QColor("orange"))
            elif status == "Error":
                status_item.setForeground(QColor("red"))
            self.results_table.setItem(i, 3, status_item)
            
        # Fix the stretch issue by checking if header exists
        header = self.results_table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
            
    def update_statistics(self, grain_stats=None, k_stats=None, summary_data=None):
        """Update all statistics displays"""
        if grain_stats:
            self.grain_stats_text.setPlainText(grain_stats)
            
        if k_stats:
            self.k_stats_text.setPlainText(k_stats)
            
        if summary_data:
            self.summary_table.setRowCount(len(summary_data))
            for i, (param, value) in enumerate(summary_data):
                self.summary_table.setItem(i, 0, QTableWidgetItem(param))
                self.summary_table.setItem(i, 1, QTableWidgetItem(str(value)))
                
            # Fix the stretch issue
            header = self.summary_table.horizontalHeader()
            if header is not None:
                header.setStretchLastSection(True)
        
    def setup_statusbar(self):
        """Setup status bar"""
        self._show_status_message("Ready - Load data to begin analysis")
        
    def open_data(self):
        """Open data file dialog and load CSV files"""
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("CSV Files (*.csv);;All Files (*)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)  # Allow multiple files
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        
        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()
            if file_paths:
                self.load_data_files(file_paths)
    
    def load_data_files(self, file_paths: List[str]):
        """Load multiple data files"""
        self._show_status_message(f"Loading {len(file_paths)} file(s)...")
        
        try:
            # Try automatic loading first
            datasets = []
            failed_files = []
            
            for file_path in file_paths:
                try:
                    dataset = self.data_loader.load_file(file_path)
                    datasets.append(dataset)
                except Exception as e:
                    print(f"Auto-load failed for {file_path}: {e}")
                    failed_files.append(file_path)
            
            # For failed files, use manual column mapping
            for file_path in failed_files:
                try:
                    dataset = self.load_file_with_mapper(file_path)
                    if dataset:
                        datasets.append(dataset)
                except Exception as e:
                    QMessageBox.warning(self, "Load Error", 
                                      f"Could not load {os.path.basename(file_path)}:\n{str(e)}")
            
            if not datasets:
                QMessageBox.warning(self, "Load Error", "No valid data files could be loaded.")
                return
            
            self.current_datasets = datasets
            self._show_status_message(f"Loaded {len(datasets)} dataset(s). Select a sample and map columns to display data.")
            # Populate sample selector for user to choose
            self.update_sample_selector()
            
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Error loading data files:\n{str(e)}")
            self._show_status_message("Error loading files")
    
    def load_file_with_mapper(self, file_path: str) -> Optional[GrainSizeData]:
        """Load a file using the column mapper dialog"""
        from .column_mapper import ColumnMapperDialog
        
        dialog = ColumnMapperDialog(file_path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                mapping_result = dialog.get_mapping_result()
                
                # Create GrainSizeData object from mapped data
                dataset = GrainSizeData(
                    sample_name=mapping_result['sample_name'],
                    particle_sizes=mapping_result['particle_sizes'],
                    percent_passing=mapping_result['percent_passing'],
                    temperature=mapping_result['temperature'],
                    porosity=mapping_result['porosity']
                )
                
                return dataset
                
            except Exception as e:
                QMessageBox.critical(self, "Mapping Error", f"Error creating dataset:\n{str(e)}")
                return None
        
        return None
    
    def display_dataset(self, dataset: GrainSizeData):
        """Display a dataset in the GUI"""
        # Update statistics tab with grain size data
        grain_stats = format_grain_size_stats(dataset)
        self.grain_stats_text.setPlainText(grain_stats)
        
        # Update plot with grain size distribution
        self.plot_widget.update_plot(
            dataset.particle_sizes,
            dataset.percent_passing, 
            dataset.sample_name
        )
        
        # Clear previous results
        self.results_table.setRowCount(0)
        self.k_stats_text.setPlainText("Click 'Calculate K Values' to compute hydraulic conductivity")
        
        # Update summary
        summary_data = [
            ("🌡️ Temperature", f"{dataset.temperature}°C"),
            ("🕳️ Porosity", f"{dataset.porosity}"),
            ("📊 Data Points", f"{len(dataset.particle_sizes)}"),
            ("📏 D10", f"{dataset.get_d10():.3f} mm" if dataset.get_d10() else "N/A"),
            ("📏 D50", f"{dataset.get_d50():.3f} mm" if dataset.get_d50() else "N/A"),
            ("📋 Classification", dataset.classify_soil()),
            ("✅ Status", "Data Loaded")
        ]
        
        self.update_statistics(summary_data=summary_data)
        self._show_status_message(f"Displaying: {dataset.sample_name}")
    
    def show_multiple_datasets_summary(self, datasets: List[GrainSizeData]):
        """Show summary when multiple datasets are loaded"""
        summary_text = f"Multiple Datasets Loaded ({len(datasets)} files):\n"
        summary_text += "=" * 50 + "\n\n"
        
        for i, dataset in enumerate(datasets, 1):
            d10 = dataset.get_d10()
            d50 = dataset.get_d50()
            summary_text += f"{i}. {dataset.sample_name}\n"
            summary_text += f"   D10: {d10:.3f} mm, D50: {d50:.3f} mm\n" if d10 and d50 else "   Grain sizes: Calculating...\n"
            summary_text += f"   Classification: {dataset.classify_soil()}\n\n"
        
        summary_text += "Note: Currently displaying first dataset. Use batch processing for multiple calculations."
        
        # Show in a message box or update stats
        QMessageBox.information(self, "Multiple Datasets", summary_text)
        
    def export_results(self):
        """Export calculation results"""
        self._show_status_message("Exporting results... (placeholder)")
        # TODO: Implement results export
        
    def export_plot(self):
        """Export current plot"""
        self._show_status_message("Exporting plot... (placeholder)")
        # TODO: Implement plot export
        
    def show_about(self):
        """Show about dialog"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(self, "About", 
                         "Grain Size Analysis Tool\n"
                         "Hydraulic Conductivity Calculator\n\n"
                         "Version 0.1.0 - Prototype")
        
    def method_selection_changed(self):
        """Handle K calculation method selection changes"""
        enabled_methods = [method for method, data in self.available_methods.items() 
                          if data["enabled"]]
        self._show_status_message(f"Selected methods: {len(enabled_methods)}")
        
    def calculate_k_values(self):
        """Calculate K values using selected methods and real data"""
        if not self.current_datasets:
            QMessageBox.warning(self, "No Data", "Please load grain size data first.")
            return
            
        enabled_methods = [method for method, data in self.available_methods.items() 
                          if data["enabled"]]
        
        if not enabled_methods:
            QMessageBox.warning(self, "No Methods", "Please select at least one calculation method.")
            return
            
        self._show_status_message(f"Calculating K values using {len(enabled_methods)} methods...")
        
        try:
            # Use the first dataset for calculation
            dataset = self.current_datasets[0]
            
            # Prepare grain data dictionary (filter out None values)
            grain_data = {}
            for key, value in {
                'D10': dataset.get_d10(),
                'D20': dataset.get_d20(),
                'D30': dataset.get_d30(),
                'D50': dataset.get_d50(),
                'D60': dataset.get_d60()
            }.items():
                if value is not None:
                    grain_data[key] = value
            
            # Calculate K values using real calculator
            results = self.k_calculator.calculate_all_methods(
                grain_data, 
                temperature=dataset.temperature,
                porosity=dataset.porosity,
                selected_methods=enabled_methods
            )
            
            if not results:
                QMessageBox.warning(self, "Calculation Error", "No valid K calculations could be performed.")
                return
            
            # Store results
            self.current_results = results
            
            # Format results for table display
            table_results = []
            k_results_dict = {}
            
            for result in results:
                table_results.append((
                    result.method_name,
                    result.k_value,
                    result.formula_used,
                    result.status.value if hasattr(result.status, 'value') else str(result.status)
                ))
                if result.k_value is not None and result.k_value > 0:
                    k_results_dict[result.method_name] = result.k_value
            
            self.update_results_table(table_results)
            
            # Update plot with K results
            self.plot_widget.add_k_calculation_results(k_results_dict)
            
            # Update statistics with real data
            self.display_calculation_statistics(dataset, results, enabled_methods)
            
            self._show_status_message(f"Calculated K values using {len(results)} methods")
            
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error during K calculations:\n{str(e)}")
            self._show_status_message("Error in K calculations")
    
    def display_calculation_statistics(self, dataset: GrainSizeData, results: List[KCalculationResult], enabled_methods: List[str]):
        """Display statistics from real calculations"""
        # Valid K values only
        valid_results = [r for r in results if r.k_value is not None and r.k_value > 0]
        
        if not valid_results:
            self.k_stats_text.setPlainText("No valid K calculations were obtained.")
            return
        
        # Calculate statistics
        k_values = [r.k_value for r in valid_results]
        mean_k = sum(k_values) / len(k_values)
        min_k = min(k_values)
        max_k = max(k_values)
        
        # Find methods for min/max
        min_method = next(r.method_name for r in valid_results if r.k_value == min_k)
        max_method = next(r.method_name for r in valid_results if r.k_value == max_k)
        
        # Create statistics text
        k_stats = f"""Hydraulic Conductivity Statistics:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sample: {dataset.sample_name}
Temperature: {dataset.temperature}°C
Porosity: {dataset.porosity}

Valid Calculations: {len(valid_results)} / {len(results)}

Statistical Summary:
Mean K: {mean_k:.2e} m/s
Min K: {min_k:.2e} m/s  ({min_method})
Max K: {max_k:.2e} m/s  ({max_method})
Variability: {max_k/min_k:.1f}x difference

"""
        
        # Add method breakdown
        k_stats += "Method Results:\n"
        k_stats += "-" * 30 + "\n"
        
        for result in results:
            status_symbol = "✅" if result.k_value is not None and result.k_value > 0 else "❌"
            if result.k_value is not None and result.k_value > 0:
                k_stats += f"{status_symbol} {result.method_name}: {result.k_value:.2e} m/s\n"
            else:
                k_stats += f"{status_symbol} {result.method_name}: {result.status_message}\n"
        
        # Add permeability classification
        if valid_results:
            k_stats += f"\nPermeability Classification (mean K = {mean_k:.2e} m/s):\n"
            k_stats += self.classify_permeability(mean_k)
        
        self.k_stats_text.setPlainText(k_stats)
        
        # Update summary with real data
        summary_data = [
            ("🌡️ Temperature", f"{dataset.temperature}°C"),
            ("🕳️ Porosity", f"{dataset.porosity}"),
            ("📊 Data Points", f"{len(dataset.particle_sizes)}"),
            ("🔬 Methods Used", f"{len(enabled_methods)}/{len(self.available_methods)}"),
            ("📈 Mean K", f"{mean_k:.2e} m/s"),
            ("📏 D10", f"{dataset.get_d10():.3f} mm" if dataset.get_d10() else "N/A"),
            ("📋 Classification", dataset.classify_soil()),
            ("✅ Status", "Analysis Complete")
        ]
        
        self.update_statistics(summary_data=summary_data)
    
    def classify_permeability(self, k_value: float) -> str:
        """Classify permeability based on K value"""
        if k_value > 1e-1:
            return "Very high permeability (gravel, fractured rock)"
        elif k_value > 1e-3:
            return "High permeability (clean sand, sandy gravel)"
        elif k_value > 1e-5:
            return "Moderate permeability (fine sand, silty sand)"
        elif k_value > 1e-7:
            return "Low permeability (silt, clayey sand)"
        elif k_value > 1e-9:
            return "Very low permeability (clay, organic soils)"
        else:
            return "Practically impermeable (dense clay, rock)"
    
    def update_sample_selector(self):
        """Populate the sample selector combobox with current dataset names"""
        # Clear existing items
        self.sample_selector.clear()
        names = [ds.sample_name for ds in self.current_datasets]
        if names:
            self.sample_selector.addItems(names)
            self.sample_selector_label.show()
            self.sample_selector.show()
            self.map_columns_action.setEnabled(True)
        else:
            self.sample_selector_label.hide()
            self.sample_selector.hide()
            self.map_columns_action.setEnabled(False)

    def on_sample_selector_changed(self, sample_name: str):
        """Handle selection change from sample selector combobox"""
        for ds in self.current_datasets:
            if ds.sample_name == sample_name:
                self.display_dataset(ds)
                self._show_status_message(f"Displaying: {sample_name}")
                break

    # ================================
    # CONTROL PANEL INTEGRATION
    # ================================
    def map_columns(self):
        """Open the column mapping dialog for the currently selected sample and update its data"""
        # Determine current dataset
        if not self.current_datasets:
            return
        # Get selected sample name
        sample_name = self.sample_selector.currentText() if hasattr(self, 'sample_selector') else None
        # Find corresponding dataset
        dataset = None
        for ds in self.current_datasets:
            if ds.sample_name == sample_name:
                dataset = ds
                break
        if dataset is None:
            dataset = self.current_datasets[0]
        # Launch mapping dialog
        from gui.column_mapper import ColumnMapperDialog
        file_path = dataset.file_path
        if not file_path:
            QMessageBox.warning(self, "Mapping Error", "Original file path unknown; cannot map columns.")
            return
        dialog = ColumnMapperDialog(file_path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_mapping_result()
            # Update dataset fields
            dataset.sample_name = result.get('sample_name', dataset.sample_name)
            dataset.particle_sizes = result.get('particle_sizes', dataset.particle_sizes)
            dataset.percent_passing = result.get('percent_passing', dataset.percent_passing)
            dataset.temperature = result.get('temperature', dataset.temperature)
            dataset.porosity = result.get('porosity', dataset.porosity)
            # Refresh selector and display
            self.update_sample_selector()
            self.sample_selector.setCurrentText(dataset.sample_name)
            self.display_dataset(dataset)
            self._show_status_message(f"Columns mapped for {dataset.sample_name}")
    
    def on_files_loaded_from_control_panel(self, sample_names: List[str]):
        """Handle files loaded from control panel"""
        try:
            datasets = []
            loaded_samples = self.control_panel.get_loaded_samples()
            
            for sample_name in sample_names:
                if sample_name in loaded_samples:
                    file_path = loaded_samples[sample_name]['file_path']
                    
                    # Try to load with auto-detection first
                    try:
                        dataset = self.data_loader.load_file(file_path)
                        datasets.append(dataset)
                        self.control_panel.set_sample_status(sample_name, "✅ Auto-loaded")
                    except Exception as e:
                        # Auto-detection failed, trigger manual mapping
                        print(f"Auto-detection failed for {file_path}: {e}")
                        dataset = self.load_file_with_mapper(file_path)
                        if dataset:
                            datasets.append(dataset)
                            self.control_panel.set_sample_status(sample_name, "✅ Manually mapped")
                        else:
                            self.control_panel.set_sample_status(sample_name, "❌ Load failed")
            
            # Update main window with loaded data
            if datasets:
                self.current_datasets = datasets
                self.display_dataset(datasets[0])  # Show first dataset
                self._show_status_message(f"Loaded {len(datasets)} dataset(s) from control panel")
            else:
                QMessageBox.warning(self, "Load Error", "No datasets could be loaded from the selected files.")
                
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Error loading files from control panel:\n{str(e)}")
    
    def on_analysis_requested_from_control_panel(self, analysis_params: dict):
        """Handle analysis request from control panel"""
        if not self.current_datasets:
            QMessageBox.warning(self, "No Data", "No datasets loaded for analysis.")
            return
            
        try:
            # Get enabled methods (use control panel parameters to determine which methods)
            enabled_methods = [method for method, data in self.available_methods.items() 
                              if data["enabled"]]
            
            if not enabled_methods:
                QMessageBox.warning(self, "No Methods", "Please select calculation methods first.")
                return
            
            # Run calculations for all loaded datasets
            all_results = []
            
            for dataset in self.current_datasets:
                # Prepare grain data dictionary (filter out None values)
                raw_grain_data = {
                    'D10': dataset.get_d10(),
                    'D20': dataset.get_d20(),
                    'D30': dataset.get_d30(),
                    'D50': dataset.get_d50(),
                    'D60': dataset.get_d60()
                }
                
                # Filter out None values
                grain_data = {k: v for k, v in raw_grain_data.items() if v is not None}
                
                # Calculate K values using analysis parameters from control panel
                results = self.k_calculator.calculate_all_methods(
                    grain_data, 
                    temperature=analysis_params.get('temperature', 20.0),
                    porosity=analysis_params.get('porosity', 0.40),
                    selected_methods=enabled_methods
                )
                
                all_results.extend(results)
            
            # Store and display results
            self.current_results = all_results
            
            # Format results for table display
            table_results = []
            k_results_dict = {}
            
            for result in all_results:
                table_results.append((
                    result.method_name,
                    result.k_value,
                    result.formula_used,
                    result.status.value if hasattr(result.status, 'value') else str(result.status)
                ))
                if result.k_value is not None and result.k_value > 0:
                    k_results_dict[result.method_name] = result.k_value
            
            self.update_results_table(table_results)
            self.plot_widget.add_k_calculation_results(k_results_dict)
            
            # Update statistics
            if self.current_datasets:
                self.display_calculation_statistics(self.current_datasets[0], all_results, enabled_methods)
            
            # Notify control panel of completion
            self.control_panel.analysis_complete({dataset.sample_name: "✅ Complete" for dataset in self.current_datasets})
            
            self._show_status_message(f"Analysis complete: {len(all_results)} calculations performed")
            
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", f"Error during analysis:\n{str(e)}")
            self.control_panel.show_progress(False)
    
    def on_sample_selected_from_control_panel(self, sample_name: str):
        """Handle sample selection from control panel"""
        # Find the dataset corresponding to this sample
        for dataset in self.current_datasets:
            if dataset.sample_name == sample_name or sample_name in dataset.sample_name:
                self.display_dataset(dataset)
                self._show_status_message(f"Displaying sample: {sample_name}")
                break


class MethodSelectionDialog(QDialog):
    """Dialog for selecting calculation methods"""
    
    def __init__(self, methods_dict, parent=None):
        super().__init__(parent)
        self.methods_dict = methods_dict.copy()
        self.setWindowTitle("Select Calculation Methods")
        self.setModal(True)
        self.resize(600, 400)
        
        # Apply professional styling to dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f0;
            }
            QLabel {
                color: #2f2f2f;
                font-weight: bold;
                font-size: 14px;
            }
            QCheckBox {
                color: #2f2f2f;
                font-size: 12px;
                spacing: 8px;
                padding: 4px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #8b7355;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #d2b48c;
                border-color: #5d4e37;
            }
            QCheckBox::indicator:hover {
                border-color: #6b5b47;
                background-color: #fafaf7;
            }
            QScrollArea {
                border: 1px solid #8b7355;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QPushButton {
                background-color: #d2b48c;
                border: 1px solid #8b7355;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                color: #2f2f2f;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #ddbf94;
                border-color: #6b5b47;
            }
            QPushButton:pressed {
                background-color: #c4a574;
            }
            QPushButton:default {
                background-color: #8b7355;
                color: white;
            }
            QPushButton:default:hover {
                background-color: #6b5b47;
            }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("Select which hydraulic conductivity calculation methods to use:")
        layout.addWidget(header_label)
        
        # Methods grid
        methods_group = QGroupBox("Available Methods")
        methods_layout = QGridLayout(methods_group)
        
        self.method_checkboxes = {}
        row = 0
        col = 0
        
        for method, data in self.methods_dict.items():
            checkbox = QCheckBox(method)
            checkbox.setChecked(data["enabled"])
            
            formula_label = QLabel(data["formula"])
            formula_label.setStyleSheet("color: gray; font-size: 10px;")
            
            methods_layout.addWidget(checkbox, row, col * 2)
            methods_layout.addWidget(formula_label, row, col * 2 + 1)
            
            self.method_checkboxes[method] = checkbox
            
            col += 1
            if col >= 2:  # 2 columns
                col = 0
                row += 1
                
        layout.addWidget(methods_group)
        
        # Buttons for select all/none
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_none)
        
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(select_none_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        
    def select_all(self):
        """Select all methods"""
        for checkbox in self.method_checkboxes.values():
            checkbox.setChecked(True)
            
    def select_none(self):
        """Deselect all methods"""
        for checkbox in self.method_checkboxes.values():
            checkbox.setChecked(False)
            
    def get_selected_methods(self):
        """Get the updated methods dictionary"""
        for method, checkbox in self.method_checkboxes.items():
            self.methods_dict[method]["enabled"] = checkbox.isChecked()
        return self.methods_dict
