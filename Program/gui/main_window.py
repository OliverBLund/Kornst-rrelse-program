"""
Main window for the Grain Size Analysis application
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                            QMenuBar, QToolBar, QStatusBar, QSplitter, 
                            QCheckBox, QScrollArea, QFrame, QTabWidget,
                            QTableWidget, QTableWidgetItem, QTextEdit,
                            QGroupBox, QDialog, QDialogButtonBox,
                            QGridLayout, QLabel, QPushButton, QComboBox,
                            QFileDialog, QMessageBox, QHeaderView, QProgressBar)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from typing import Optional, List
import os

from gui.control_panel import ControlPanel
from gui.plot_widget import PlotWidget
from data_loader import DataLoader, GrainSizeData
from k_calculations import KCalculator, KCalculationResult, CalculationStatus


def format_grain_size_stats(dataset: GrainSizeData, temperature: float = None, porosity: float = None) -> str:
    """Format grain size statistics for display"""
    # Use provided values or fall back to dataset defaults
    temp = temperature if temperature is not None else dataset.temperature
    poros = porosity if porosity is not None else dataset.porosity
    
    stats_text = f"Sample: {dataset.sample_name}\n"
    stats_text += "=" * 50 + "\n\n"
    
    # Basic info
    stats_text += f"Temperature: {temp}°C\n"
    stats_text += f"Porosity: {poros}\n"
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
        
        # Initialize data structures early (before UI setup)
        self.data_loader = DataLoader()
        self.k_calculator = KCalculator()
        self.current_datasets: List[GrainSizeData] = []
        self.current_results: List[KCalculationResult] = []
        self.method_checkboxes = {}  # Initialize before UI setup
        
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
        
        # Initialize dataset selector
        self.update_dataset_selector()
        
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
        
        # Comparison tab
        self.comparison_widget = self.create_comparison_tab()
        self.tab_widget.addTab(self.comparison_widget, "Comparison")
        
        # Add panels to splitter
        splitter.addWidget(self.control_panel)
        splitter.addWidget(self.tab_widget)
        
        # Set splitter proportions (control panel should not resize)
        splitter.setStretchFactor(0, 0)  # Control panel - no stretch
        splitter.setStretchFactor(1, 1)  # Tab area - stretch
        
        main_layout.addWidget(splitter)
        
    def create_results_tab(self):
        """Create the results tab widget"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Dataset selector at the top
        selector_layout = QHBoxLayout()
        selector_label = QLabel("Select Dataset:")
        self.dataset_selector = QComboBox()
        self.dataset_selector.setMinimumWidth(200)
        self.dataset_selector.currentIndexChanged.connect(self.on_dataset_selected)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.dataset_selector)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)
        
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
        
        # Method selection controls - more accessible
        method_group = QGroupBox("Calculation Methods")
        method_layout = QVBoxLayout(method_group)
        
        # Quick method selection checkboxes
        # Use existing dictionary, don't recreate
        methods_grid = QGridLayout()
        
        common_methods = ["Hazen", "Terzaghi", "Beyer", "Slichter", "Kozeny-Carman", 
                         "Shepherd", "USBR", "Zunker", "Zamarin", "Sauerbrei"]
        
        for i, method in enumerate(common_methods):
            checkbox = QCheckBox(method)
            checkbox.setChecked(True)  # Default all checked
            self.method_checkboxes[method] = checkbox
            methods_grid.addWidget(checkbox, i // 2, i % 2)
        
        method_layout.addLayout(methods_grid)
        
        # Control buttons
        method_buttons_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: [cb.setChecked(True) for cb in self.method_checkboxes.values()])
        
        select_none_btn = QPushButton("Clear All")
        select_none_btn.clicked.connect(lambda: [cb.setChecked(False) for cb in self.method_checkboxes.values()])
        
        calculate_btn = QPushButton("Calculate K Values")
        calculate_btn.clicked.connect(self.calculate_k_values)
        calculate_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b8e23;
                color: white;
                font-weight: bold;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #7ba428;
            }
        """)
        
        method_buttons_layout.addWidget(select_all_btn)
        method_buttons_layout.addWidget(select_none_btn)
        method_buttons_layout.addStretch()
        method_buttons_layout.addWidget(calculate_btn)
        
        method_layout.addLayout(method_buttons_layout)
        layout.addWidget(method_group)
        
        layout.addStretch()
        return widget
    
    def update_dataset_selector(self):
        """Update the dataset selector dropdown with current datasets"""
        self.dataset_selector.blockSignals(True)  # Prevent triggering selection event
        self.dataset_selector.clear()
        
        if self.current_datasets:
            for i, dataset in enumerate(self.current_datasets):
                self.dataset_selector.addItem(f"{i+1}. {dataset.sample_name}")
        else:
            self.dataset_selector.addItem("No datasets loaded")
        
        self.dataset_selector.blockSignals(False)
    
    def on_dataset_selected(self, index):
        """Handle dataset selection from dropdown"""
        if index >= 0 and index < len(self.current_datasets):
            self.display_dataset(self.current_datasets[index])
        
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
    
    def create_comparison_tab(self):
        """Create the comparison tab widget for comparing multiple datasets"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Comparison table
        comparison_group = QGroupBox("Dataset Comparison")
        comparison_layout = QVBoxLayout(comparison_group)
        
        self.comparison_table = QTableWidget()
        self.comparison_table.setAlternatingRowColors(True)
        comparison_layout.addWidget(self.comparison_table)
        layout.addWidget(comparison_group)
        
        # Comparison summary
        summary_group = QGroupBox("Comparison Summary")
        summary_layout = QVBoxLayout(summary_group)
        
        self.comparison_summary = QTextEdit()
        self.comparison_summary.setReadOnly(True)
        self.comparison_summary.setMaximumHeight(150)
        self.comparison_summary.setPlaceholderText("Comparison summary will appear here after calculations...")
        
        summary_layout.addWidget(self.comparison_summary)
        layout.addWidget(summary_group)
        
        # Update comparison button
        update_btn = QPushButton("Update Comparison")
        update_btn.clicked.connect(self.update_comparison_view)
        update_btn.setStyleSheet("""
            QPushButton {
                background-color: #4682B4;
                color: white;
                font-weight: bold;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #5A92C4;
            }
        """)
        layout.addWidget(update_btn)
        
        layout.addStretch()
        return widget
    
    def update_comparison_view(self):
        """Update the comparison table with all dataset results"""
        if not self.current_datasets:
            QMessageBox.information(self, "No Data", "Please load datasets first.")
            return
        
        if not self.current_results:
            QMessageBox.information(self, "No Results", "Please calculate K values first.")
            return
        
        # Prepare comparison table
        methods = self.get_selected_methods()
        if not methods:
            methods = ["Hazen", "Terzaghi", "Beyer", "Slichter", "Kozeny-Carman"]
        
        # Set up table structure
        self.comparison_table.setRowCount(len(methods) + 5)  # Methods + grain size parameters
        self.comparison_table.setColumnCount(len(self.current_datasets) + 1)
        
        # Set headers
        headers = ["Parameter"] + [f"{i+1}. {ds.sample_name}" for i, ds in enumerate(self.current_datasets)]
        self.comparison_table.setHorizontalHeaderLabels(headers)
        
        # Add grain size parameters
        row = 0
        grain_params = [
            ("D10 (mm)", lambda ds: f"{ds.get_d10():.3f}" if ds.get_d10() else "N/A"),
            ("D30 (mm)", lambda ds: f"{ds.get_d30():.3f}" if ds.get_d30() else "N/A"),
            ("D50 (mm)", lambda ds: f"{ds.get_d50():.3f}" if ds.get_d50() else "N/A"),
            ("D60 (mm)", lambda ds: f"{ds.get_d60():.3f}" if ds.get_d60() else "N/A"),
            ("Classification", lambda ds: ds.classify_soil())
        ]
        
        for param_name, get_value in grain_params:
            self.comparison_table.setItem(row, 0, QTableWidgetItem(param_name))
            for col, dataset in enumerate(self.current_datasets, 1):
                self.comparison_table.setItem(row, col, QTableWidgetItem(get_value(dataset)))
            row += 1
        
        # Add K values for each method
        for method in methods:
            self.comparison_table.setItem(row, 0, QTableWidgetItem(f"K ({method})"))
            for col, dataset in enumerate(self.current_datasets, 1):
                # Calculate K value for this dataset and method
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
                
                results = self.k_calculator.calculate_all_methods(
                    grain_data,
                    temperature=self.control_panel.temp_spinbox.value(),
                    porosity=self.control_panel.porosity_spinbox.value(),
                    selected_methods=[method]
                )
                
                if results and results[0].k_value:
                    k_text = f"{results[0].k_value:.2e}"
                else:
                    k_text = "N/A"
                
                self.comparison_table.setItem(row, col, QTableWidgetItem(k_text))
            row += 1
        
        # Resize columns
        self.comparison_table.resizeColumnsToContents()
        
        # Update summary
        summary_text = f"""Comparison of {len(self.current_datasets)} Datasets
{'='*50}

Temperature: {self.control_panel.temp_spinbox.value()}°C
Porosity: {self.control_panel.porosity_spinbox.value()}

Number of methods compared: {len(methods)}
Datasets: {', '.join([ds.sample_name for ds in self.current_datasets])}
"""
        self.comparison_summary.setPlainText(summary_text)
        
        self._show_status_message("Comparison view updated")
    
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
        
        # Export options
        export_results_action = QAction("Export Results", self)
        export_results_action.triggered.connect(self.export_results)
        toolbar.addAction(export_results_action)

        export_plot_action = QAction("Export Plot", self)
        export_plot_action.triggered.connect(self.export_plot)
        toolbar.addAction(export_plot_action)

        # Remove duplicate sample selector - control panel handles this
        
    def get_selected_methods(self):
        """Get list of selected calculation methods"""
        return [method for method, checkbox in self.method_checkboxes.items() if checkbox.isChecked()]
        
    def update_combined_results_table(self, results):
        """Update results table with combined dataset results"""
        # Modify table to have 5 columns for multiple datasets
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["Dataset", "Method", "K (m/s)", "Formula", "Status"])
        
        self.results_table.setRowCount(len(results))
        for row, (dataset_name, method, k_value, formula, status) in enumerate(results):
            # Dataset name
            self.results_table.setItem(row, 0, QTableWidgetItem(dataset_name))
            
            # Method
            self.results_table.setItem(row, 1, QTableWidgetItem(method))
            
            # K value
            k_item = QTableWidgetItem()
            if k_value is not None and k_value > 0:
                k_item.setText(f"{k_value:.2e}")
            else:
                k_item.setText("N/A")
            self.results_table.setItem(row, 2, k_item)
            
            # Formula
            self.results_table.setItem(row, 3, QTableWidgetItem(formula))
            
            # Status with color coding
            status_parts = status.split(':', 1)
            status_type = status_parts[0].strip()
            status_message = status_parts[1].strip() if len(status_parts) > 1 else ""
            
            if status_message and status_type != "OK":
                key_info = status_message.split(',')[0] if ',' in status_message else status_message[:40]
                status_display = f"{status_type}: {key_info}"
            else:
                status_display = status_type
                
            status_item = QTableWidgetItem(status_display)
            if status_message:
                status_item.setToolTip(status_message)
            
            # Color code based on status
            if status_type == "OK":
                status_item.setBackground(QColor(200, 255, 200))
            elif "Warning" in status_type:
                status_item.setBackground(QColor(255, 255, 200))
            elif "Error" in status_type:
                status_item.setBackground(QColor(255, 200, 200))
                
            self.results_table.setItem(row, 4, status_item)
        
        # Resize columns to content
        self.results_table.resizeColumnsToContents()
        # Make formula column stretch
        header = self.results_table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    
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
        
        for i, result in enumerate(results):
            # Handle both tuple and object formats
            if isinstance(result, tuple):
                method, k_value, formula, status = result
                status_message = ""
            else:
                method = result.method_name
                k_value = result.k_value if result.k_value else 0
                formula = result.formula_used
                status = result.status.value if hasattr(result.status, 'value') else str(result.status)
                status_message = result.status_message if hasattr(result, 'status_message') else ""
            
            # Method name with color background
            method_item = QTableWidgetItem(method)
            if method in method_colors:
                method_item.setBackground(QColor(method_colors[method]))
            method_item.setToolTip(f"Method: {method}")
            self.results_table.setItem(i, 0, method_item)
            
            # K value
            if k_value and k_value > 0:
                k_item = QTableWidgetItem(f"{k_value:.2e}")
                k_item.setToolTip(f"K = {k_value:.4e} m/s")
            else:
                k_item = QTableWidgetItem("N/A")
                k_item.setToolTip("Calculation failed or invalid")
            if method in method_colors:
                k_item.setBackground(QColor(method_colors[method]))
            self.results_table.setItem(i, 1, k_item)
            
            # Formula
            formula_item = QTableWidgetItem(formula)
            formula_item.setToolTip(f"Formula: {formula}")
            if method in method_colors:
                formula_item.setBackground(QColor(method_colors[method]))
            self.results_table.setItem(i, 2, formula_item)
            
            # Status with detailed message
            if status_message and status != "OK":
                # Show key info in cell
                key_info = status_message.split(',')[0] if ',' in status_message else status_message[:40]
                status_display = f"{status}: {key_info}"
            else:
                status_display = status
                
            status_item = QTableWidgetItem(status_display)
            if status_message:
                status_item.setToolTip(status_message)
            
            # Color code status with better visibility
            if status == "OK":
                status_item.setForeground(QColor(0, 128, 0))  # Green
                status_item.setBackground(QColor(230, 255, 230))
            elif "Warning" in status:
                status_item.setForeground(QColor(204, 102, 0))  # Orange
                status_item.setBackground(QColor(255, 250, 205))
            elif "Error" in status:
                status_item.setForeground(QColor(204, 0, 0))  # Red
                status_item.setBackground(QColor(255, 230, 230))
            else:
                if method in method_colors:
                    status_item.setBackground(QColor(method_colors[method]))
                    
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
        # Add progress bar to status bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)
        
        self._show_status_message("Ready - Load data to begin analysis")
        
    
    def display_dataset(self, dataset: GrainSizeData):
        """Display a dataset in the GUI"""
        # Update statistics tab with grain size data (use control panel values)
        grain_stats = format_grain_size_stats(
            dataset, 
            temperature=self.control_panel.temp_spinbox.value(),
            porosity=self.control_panel.porosity_spinbox.value()
        )
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
        
        # Update summary (use control panel values for temperature and porosity)
        summary_data = [
            ("🌡️ Temperature", f"{self.control_panel.temp_spinbox.value()}°C"),
            ("🕳️ Porosity", f"{self.control_panel.porosity_spinbox.value()}"),
            ("📊 Data Points", f"{len(dataset.particle_sizes)}"),
            ("📏 D10", f"{dataset.get_d10():.3f} mm" if dataset.get_d10() else "N/A"),
            ("📏 D50", f"{dataset.get_d50():.3f} mm" if dataset.get_d50() else "N/A"),
            ("📋 Classification", dataset.classify_soil()),
            ("✅ Status", "Data Loaded")
        ]
        
        self.update_statistics(summary_data=summary_data)
        self._show_status_message(f"Displaying: {dataset.sample_name}")
            
    def export_results(self):
        """Export calculation results to CSV"""
        if not self.current_results:
            QMessageBox.warning(self, "No Results", "No results to export. Please run calculations first.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "", "CSV Files (*.csv);;All Files (*.*)"
        )
        
        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(['Method', 'K Value (m/s)', 'Formula', 'Status'])
                    
                    for result in self.current_results:
                        writer.writerow([
                            result.method_name,
                            result.k_value,
                            result.formula_used,
                            result.status.value if hasattr(result.status, 'value') else str(result.status)
                        ])
                        
                self._show_status_message(f"Results exported to {file_path}")
                QMessageBox.information(self, "Export Complete", f"Results saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Error exporting results:\n{str(e)}")
        
    def export_plot(self):
        """Export current plot to image file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Plot", "", 
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*.*)"
        )
        
        if file_path:
            if self.plot_widget.export_plot(file_path):
                self._show_status_message(f"Plot exported to {file_path}")
                QMessageBox.information(self, "Export Complete", f"Plot saved to:\n{file_path}")
            else:
                QMessageBox.critical(self, "Export Error", "Failed to export plot")
        
    def show_about(self):
        """Show about dialog"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(self, "About", 
                         "Grain Size Analysis Tool\n"
                         "Hydraulic Conductivity Calculator\n\n"
                         "Version 0.1.0 - Prototype")
        
    def method_selection_changed(self):
        """Handle K calculation method selection changes"""
        enabled_methods = self.get_selected_methods()
        self._show_status_message(f"Selected methods: {len(enabled_methods)}")
        
    def calculate_k_values(self):
        """Calculate K values using selected methods and real data"""
        if not self.current_datasets:
            QMessageBox.warning(self, "No Data", "Please load grain size data first.")
            return
            
        enabled_methods = self.get_selected_methods()
        
        if not enabled_methods:
            QMessageBox.warning(self, "No Methods", "Please select at least one calculation method.")
            return
            
        self._show_status_message(f"Calculating K values for {len(self.current_datasets)} dataset(s) using {len(enabled_methods)} methods...")
        
        # Show progress bar
        total_calculations = len(self.current_datasets) * len(enabled_methods)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total_calculations)
        self.progress_bar.setValue(0)
        
        try:
            # Calculate for all datasets
            all_results = []
            all_table_results = []
            current_progress = 0
            
            for dataset_idx, dataset in enumerate(self.current_datasets):
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
                # Use current control panel values (not dataset defaults)
                results = self.k_calculator.calculate_all_methods(
                    grain_data, 
                    temperature=self.control_panel.temp_spinbox.value(),
                    porosity=self.control_panel.porosity_spinbox.value(),
                    selected_methods=enabled_methods
                )
                
                if results:
                    all_results.extend([(dataset, r) for r in results])
                    
                    # Format results for this dataset
                    for result in results:
                        all_table_results.append((
                            f"{dataset.sample_name}",
                            result.method_name,
                            result.k_value,
                            result.formula_used,
                            result.status.value if hasattr(result.status, 'value') else str(result.status)
                        ))
                        # Update progress
                        current_progress += 1
                        self.progress_bar.setValue(current_progress)
            
            if not all_results:
                QMessageBox.warning(self, "Calculation Error", "No valid K calculations could be performed for any dataset.")
                self.progress_bar.setVisible(False)
                return
            
            # Store results from first dataset for backward compatibility
            self.current_results = [r for d, r in all_results if d == self.current_datasets[0]]
            
            # Update results table with all datasets
            self.update_combined_results_table(all_table_results)
            
            # Update plot with K results from currently selected dataset
            selected_idx = self.dataset_selector.currentIndex()
            if selected_idx >= 0 and selected_idx < len(self.current_datasets):
                selected_dataset = self.current_datasets[selected_idx]
                k_results_dict = {}
                for dataset, result in all_results:
                    if dataset == selected_dataset and result.k_value is not None and result.k_value > 0:
                        k_results_dict[result.method_name] = result.k_value
                self.plot_widget.add_k_calculation_results(k_results_dict)
                
                # Update statistics for selected dataset
                selected_results = [r for d, r in all_results if d == selected_dataset]
                self.display_calculation_statistics(selected_dataset, selected_results, enabled_methods)
            
            self._show_status_message(f"Calculated K values for {len(self.current_datasets)} dataset(s) using {len(enabled_methods)} methods")
            
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error during K calculations:\n{str(e)}")
            self._show_status_message("Error in K calculations")
        finally:
            # Hide progress bar
            self.progress_bar.setVisible(False)
    
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
Temperature: {self.control_panel.temp_spinbox.value()}°C
Porosity: {self.control_panel.porosity_spinbox.value()}

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
        
        # Update summary with real data (use control panel values for temperature and porosity)
        summary_data = [
            ("🌡️ Temperature", f"{self.control_panel.temp_spinbox.value()}°C"),
            ("🕳️ Porosity", f"{self.control_panel.porosity_spinbox.value()}"),
            ("📊 Data Points", f"{len(dataset.particle_sizes)}"),
            ("🔬 Methods Used", f"{len(enabled_methods)}/{len(self.method_checkboxes) if hasattr(self, 'method_checkboxes') else 10}"),
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
    
    # ================================
    # CONTROL PANEL INTEGRATION
    # ================================
    
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
                        self.control_panel.set_sample_status(sample_name, "✅ Loaded")
                    except Exception as e:
                        print(f"Auto-detection failed for {file_path}: {e}")
                        # Try with column mapper as fallback
                        dataset = self.load_file_with_mapper(file_path)
                        if dataset:
                            datasets.append(dataset)
                            self.control_panel.set_sample_status(sample_name, "✅ Manually mapped")
                        else:
                            self.control_panel.set_sample_status(sample_name, f"❌ {str(e)[:50]}")
            
            # Update main window with loaded data
            if datasets:
                self.current_datasets = datasets
                self.update_dataset_selector()  # Update dropdown
                self.display_dataset(datasets[0])  # Show first dataset
                self._show_status_message(f"Loaded {len(datasets)} dataset(s) from control panel")
                
                # Switch to Results tab to show data
                self.tab_widget.setCurrentIndex(0)  # Switch to Plots tab
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
            # Get enabled methods from checkboxes
            enabled_methods = self.get_selected_methods() if hasattr(self, 'method_checkboxes') else []
            
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
                # Switch to Plots tab to show the data
                self.tab_widget.setCurrentIndex(0)
                break


# MethodSelectionDialog removed - methods are now selected directly in the Results tab
