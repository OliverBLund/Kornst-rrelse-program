"""
Control panel widget for data import and analysis controls
"""

from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QPushButton, QLabel, QLineEdit, QComboBox, 
                            QTableWidget, QTableWidgetItem, QTextEdit,
                            QProgressBar, QCheckBox, QSpinBox, QDoubleSpinBox,
                            QListWidget, QListWidgetItem, QSplitter, QWidget,
                            QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

class ControlPanel(QFrame):
    # Signals for communication with main window
    files_loaded = pyqtSignal(list)  # Emitted when files are loaded
    analysis_requested = pyqtSignal(dict)  # Emitted when analysis is requested
    sample_selected = pyqtSignal(str)  # Emitted when a sample is selected
    
    def __init__(self):
        super().__init__()
        self.loaded_samples = {}  # Dictionary to store sample data
        self.validation_errors = []  # Track validation issues
        self.setup_ui()
        self.setup_validation()
        
    def setup_validation(self):
        """Setup input validation for parameters"""
        # Connect validation to parameter changes
        self.temp_spinbox.valueChanged.connect(self.validate_temperature)
        self.porosity_spinbox.valueChanged.connect(self.validate_porosity)
        self.diameter_combo.currentTextChanged.connect(self.validate_column_mapping)
        self.cumulative_combo.currentTextChanged.connect(self.validate_column_mapping)
        
    def setup_ui(self):
        """Setup the control panel layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Apply professional geotechnical styling
        self.setStyleSheet("""
            QFrame {
                background-color: #f5f5f0;
                border: 1px solid #d4c4a8;
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
            QPushButton:disabled {
                background-color: #e8e8e5;
                color: #999999;
                border-color: #cccccc;
            }
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #8b7355;
                border-radius: 4px;
                selection-background-color: #d2b48c;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                background-color: #ffffff;
                border: 1px solid #8b7355;
                border-radius: 3px;
                padding: 4px;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
                border-color: #5d4e37;
                border-width: 2px;
            }
            QProgressBar {
                border: 1px solid #8b7355;
                border-radius: 4px;
                background-color: #f0f0ed;
            }
            QProgressBar::chunk {
                background-color: #6b8e23;
                border-radius: 3px;
            }
            QCheckBox {
                color: #2f2f2f;
            }
            QCheckBox::indicator:checked {
                background-color: #6b8e23;
                border: 1px solid #5d4e37;
            }
        """)
        
        # === SAMPLE MANAGEMENT SECTION ===
        samples_group = QGroupBox("📁 Sample Management")
        samples_layout = QVBoxLayout(samples_group)
        
        # File operation buttons
        file_buttons_layout = QHBoxLayout()
        
        self.add_files_btn = QPushButton("➕ Add Files")
        self.add_files_btn.clicked.connect(self.add_files)
        self.add_files_btn.setToolTip("Add one or more grain size data files")
        
        self.remove_file_btn = QPushButton("🗑️ Remove")
        self.remove_file_btn.clicked.connect(self.remove_selected_file)
        self.remove_file_btn.setEnabled(False)
        
        self.clear_all_btn = QPushButton("🧹 Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all_files)
        
        file_buttons_layout.addWidget(self.add_files_btn)
        file_buttons_layout.addWidget(self.remove_file_btn)
        file_buttons_layout.addWidget(self.clear_all_btn)
        
        # Sample list
        self.samples_list = QListWidget()
        self.samples_list.setMaximumHeight(120)
        self.samples_list.itemSelectionChanged.connect(self.on_sample_selection_changed)
        self.samples_list.setToolTip("List of loaded samples. Click to select and preview.")
        
        # Sample info display
        self.sample_info_label = QLabel("No samples loaded")
        self.sample_info_label.setStyleSheet("color: gray; font-style: italic;")
        
        samples_layout.addLayout(file_buttons_layout)
        samples_layout.addWidget(self.samples_list)
        samples_layout.addWidget(self.sample_info_label)
        
        # === DATA IMPORT SECTION ===
        data_group = QGroupBox("🔧 Data Configuration")
        data_layout = QVBoxLayout(data_group)
        
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Current sample preview...")
        self.file_path_edit.setReadOnly(True)

        # Column Mapping Section
        mapping_group = QGroupBox("📊 Column Mapping")
        mapping_layout = QVBoxLayout(mapping_group)
        
        # Sample column mapping
        mapping_layout.addWidget(QLabel("Map your data columns:"))
        
        diameter_layout = QHBoxLayout()
        diameter_layout.addWidget(QLabel("Diameter (mm):"))
        self.diameter_combo = QComboBox()
        self.diameter_combo.addItems(["Select column...", "Diameter", "Size", "D", "Grain_Size"])
        diameter_layout.addWidget(self.diameter_combo)
        
        cumulative_layout = QHBoxLayout()
        cumulative_layout.addWidget(QLabel("Cumulative %:"))
        self.cumulative_combo = QComboBox()
        self.cumulative_combo.addItems(["Select column...", "Cumulative", "Cum_%", "Passing", "Percent_Passing"])
        cumulative_layout.addWidget(self.cumulative_combo)
        
        mapping_layout.addLayout(diameter_layout)
        mapping_layout.addLayout(cumulative_layout)
        
        data_layout.addWidget(QLabel("Selected Sample:"))
        data_layout.addWidget(self.file_path_edit)
        data_layout.addWidget(mapping_group)

        # === ANALYSIS PARAMETERS ===
        params_group = QGroupBox("⚙️ Analysis Parameters")
        params_layout = QVBoxLayout(params_group)
        
        # Global parameters (apply to all samples)
        global_params_label = QLabel("Global Parameters (applied to all samples):")
        global_params_label.setFont(QFont("", 9, QFont.Weight.Bold))
        params_layout.addWidget(global_params_label)
        
        # Temperature for viscosity calculations
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("🌡️ Temperature:"))
        self.temp_spinbox = QDoubleSpinBox()
        self.temp_spinbox.setRange(0, 50)
        self.temp_spinbox.setValue(20)
        self.temp_spinbox.setSuffix(" °C")
        self.temp_spinbox.setToolTip("Temperature affects water viscosity in calculations")
        temp_layout.addWidget(self.temp_spinbox)
        
        # Porosity
        porosity_layout = QHBoxLayout()
        porosity_layout.addWidget(QLabel("🕳️ Porosity:"))
        self.porosity_spinbox = QDoubleSpinBox()
        self.porosity_spinbox.setRange(0.1, 0.8)
        self.porosity_spinbox.setValue(0.4)
        self.porosity_spinbox.setSingleStep(0.01)
        self.porosity_spinbox.setDecimals(3)
        self.porosity_spinbox.setToolTip("Typical values: Sand 0.25-0.50, Silt 0.35-0.50, Clay 0.40-0.70")
        porosity_layout.addWidget(self.porosity_spinbox)
        
        params_layout.addLayout(temp_layout)
        params_layout.addLayout(porosity_layout)
        
        # === BATCH ANALYSIS SECTION ===
        analysis_group = QGroupBox("🚀 Batch Analysis")
        analysis_layout = QVBoxLayout(analysis_group)
        
        # Analysis options
        options_layout = QHBoxLayout()
        
        self.auto_analyze_cb = QCheckBox("Auto-analyze new samples")
        self.auto_analyze_cb.setChecked(True)
        self.auto_analyze_cb.setToolTip("Automatically run analysis when samples are loaded")
        
        self.export_results_cb = QCheckBox("Auto-export results")
        self.export_results_cb.setToolTip("Automatically export results to Excel after analysis")
        
        options_layout.addWidget(self.auto_analyze_cb)
        options_layout.addWidget(self.export_results_cb)
        
        # Main action buttons
        action_buttons_layout = QHBoxLayout()
        
        self.analyze_selected_btn = QPushButton("📊 Analyze Selected")
        self.analyze_selected_btn.clicked.connect(self.analyze_selected_sample)
        self.analyze_selected_btn.setEnabled(False)
        self.analyze_selected_btn.setToolTip("Analyze only the currently selected sample")
        
        self.analyze_all_btn = QPushButton("⚡ Analyze All Samples")
        self.analyze_all_btn.clicked.connect(self.analyze_all_samples)
        self.analyze_all_btn.setEnabled(False)
        self.analyze_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b8e23;
                color: white;
                font-weight: bold;
                border: 2px solid #556b2f;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #7ba428;
                border-color: #4a5a2a;
            }
            QPushButton:pressed {
                background-color: #5a7a1f;
            }
            QPushButton:disabled {
                background-color: #a8a8a5;
                color: #ffffff;
                border-color: #888888;
            }
        """)
        self.analyze_all_btn.setToolTip("Run batch analysis on all loaded samples")
        
        action_buttons_layout.addWidget(self.analyze_selected_btn)
        action_buttons_layout.addWidget(self.analyze_all_btn)
        
        analysis_layout.addLayout(options_layout)
        analysis_layout.addLayout(action_buttons_layout)

        # === VALIDATION STATUS ===
        validation_group = QGroupBox("✅ Validation Status")
        validation_layout = QVBoxLayout(validation_group)
        
        self.validation_label = QLabel("🔍 Checking parameters...")
        self.validation_label.setStyleSheet("color: #5d4e37; font-style: italic;")
        validation_layout.addWidget(self.validation_label)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        
        # Add all groups to main layout
        layout.addWidget(samples_group)
        layout.addWidget(data_group)
        layout.addWidget(params_group)
        layout.addWidget(analysis_group)
        layout.addWidget(validation_group)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        layout.addStretch()  # Push everything to top
        
    def add_files(self):
        """Add multiple files for batch processing"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "Add Grain Size Data Files", 
            "", 
            "Excel files (*.xlsx *.xls);;CSV files (*.csv);;All files (*.*)"
        )
        
        if file_paths:
            newly_added = []
            for file_path in file_paths:
                if file_path not in self.loaded_samples:
                    # Extract sample name from file path
                    sample_name = self.extract_sample_name(file_path)
                    
                    # Add to samples list
                    self.loaded_samples[sample_name] = {
                        'file_path': file_path,
                        'columns': [],
                        'data': None,
                        'status': 'Loaded'
                    }
                    
                    # Add to UI list
                    item = QListWidgetItem(f"📄 {sample_name}")
                    item.setData(Qt.ItemDataRole.UserRole, sample_name)
                    item.setToolTip(f"File: {file_path}\nStatus: Ready for analysis")
                    self.samples_list.addItem(item)
                    
                    newly_added.append(sample_name)
            
            if newly_added:
                self.update_ui_state()
                self.sample_info_label.setText(f"✅ Added {len(newly_added)} new sample(s)")
                
                # Auto-detect columns for the first file
                if newly_added:
                    self.load_file_preview(self.loaded_samples[newly_added[0]]['file_path'])
                
                # Emit signal
                self.files_loaded.emit(newly_added)
                
                # Auto-analyze if enabled
                if self.auto_analyze_cb.isChecked():
                    self.analyze_all_samples()
            else:
                QMessageBox.information(self, "Info", "All selected files were already loaded.")
    
    def remove_selected_file(self):
        """Remove selected file from the list"""
        current_item = self.samples_list.currentItem()
        if current_item:
            sample_name = current_item.data(Qt.ItemDataRole.UserRole)
            
            # Remove from data
            if sample_name in self.loaded_samples:
                del self.loaded_samples[sample_name]
            
            # Remove from UI
            row = self.samples_list.row(current_item)
            self.samples_list.takeItem(row)
            
            self.update_ui_state()
            self.sample_info_label.setText(f"🗑️ Removed sample: {sample_name}")
    
    def clear_all_files(self):
        """Clear all loaded files"""
        if self.loaded_samples:
            reply = QMessageBox.question(
                self, "Clear All", 
                f"Remove all {len(self.loaded_samples)} loaded samples?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.loaded_samples.clear()
                self.samples_list.clear()
                self.update_ui_state()
                self.sample_info_label.setText("🧹 All samples cleared")
    
    def on_sample_selection_changed(self):
        """Handle sample selection change"""
        current_item = self.samples_list.currentItem()
        if current_item:
            sample_name = current_item.data(Qt.ItemDataRole.UserRole)
            sample_data = self.loaded_samples[sample_name]
            
            # Update preview
            self.file_path_edit.setText(f"{sample_name} ({sample_data['file_path']})")
            
            # Load file preview for column mapping
            self.load_file_preview(sample_data['file_path'])
            
            # Update UI state
            self.remove_file_btn.setEnabled(True)
            self.analyze_selected_btn.setEnabled(True)
            
            # Emit signal
            self.sample_selected.emit(sample_name)
        else:
            self.file_path_edit.setText("")
            self.remove_file_btn.setEnabled(False)
            self.analyze_selected_btn.setEnabled(False)
    
    def analyze_selected_sample(self):
        """Analyze only the currently selected sample"""
        current_item = self.samples_list.currentItem()
        if current_item:
            sample_name = current_item.data(Qt.ItemDataRole.UserRole)
            self.run_analysis([sample_name])
    
    def analyze_all_samples(self):
        """Analyze all loaded samples"""
        if self.loaded_samples:
            sample_names = list(self.loaded_samples.keys())
            self.run_analysis(sample_names)
        else:
            QMessageBox.information(self, "No Samples", "Please add some samples first.")
    
    def run_analysis(self, sample_names):
        """Run analysis on specified samples"""
        if not sample_names:
            return
        
        # Perform full validation before analysis
        if not self.perform_full_validation():
            QMessageBox.warning(
                self, 
                "Validation Failed", 
                "Please fix the validation errors before running analysis:\n\n" + 
                "\n".join([err for err in self.validation_errors if '❌' in err or 'should be' in err])
            )
            return
            
        # Prepare analysis parameters
        analysis_params = {
            'samples': sample_names,
            'temperature': self.temp_spinbox.value(),
            'porosity': self.porosity_spinbox.value(),
            'diameter_column': self.diameter_combo.currentText(),
            'cumulative_column': self.cumulative_combo.currentText(),
            'auto_export': self.export_results_cb.isChecked()
        }
        
        # Show progress
        self.show_progress(True)
        self.progress_label.setText(f"🔄 Analyzing {len(sample_names)} sample(s)...")
        
        # Update sample status
        for sample_name in sample_names:
            if sample_name in self.loaded_samples:
                self.loaded_samples[sample_name]['status'] = 'Analyzing...'
        
        # Emit analysis request signal
        self.analysis_requested.emit(analysis_params)
    
    def extract_sample_name(self, file_path):
        """Extract a clean sample name from file path"""
        import os
        base_name = os.path.basename(file_path)
        # Remove extension
        name = os.path.splitext(base_name)[0]
        # Clean up common prefixes/suffixes
        name = name.replace('_grainsize', '').replace('_sieve', '').replace('_data', '')
        return name if name else base_name
    
    def update_ui_state(self):
        """Update UI state based on loaded samples"""
        has_samples = len(self.loaded_samples) > 0
        has_selection = self.samples_list.currentItem() is not None
        
        # Update sample count
        if has_samples:
            self.sample_info_label.setText(f"📊 {len(self.loaded_samples)} sample(s) loaded")
        else:
            self.sample_info_label.setText("No samples loaded")
            
        # Basic UI state (validation will override if needed)
        self.remove_file_btn.setEnabled(has_selection)
        
        # Trigger validation to determine if analysis buttons should be enabled
        self.perform_full_validation()
    
    def browse_file(self):
        """Legacy method - redirect to add_files"""
        self.add_files()
            
    def load_file_preview(self, file_path):
        """Load and preview the selected file"""
        try:
            # Try to detect CSV structure
            import csv
            with open(file_path, 'r', encoding='utf-8') as file:
                # Read first few rows to detect columns
                reader = csv.reader(file)
                rows = list(reader)[:10]
            
            if not rows:
                self.sample_info_label.setText("❌ File appears to be empty")
                return
            
            # Try to detect header row
            headers = []
            for i, row in enumerate(rows[:3]):  # Check first 3 rows
                if len(row) >= 2:
                    # Check if this row looks like headers (contains text, not just numbers)
                    text_count = sum(1 for cell in row if not self._is_numeric(cell.strip()))
                    if text_count >= len(row) * 0.5:  # At least half are text
                        headers = [cell.strip() for cell in row]
                        break
            
            # If no headers detected, create generic ones
            if not headers and rows:
                max_cols = max(len(row) for row in rows)
                headers = [f"Column_{i+1}" for i in range(max_cols)]
            
            # Update combo boxes with detected columns
            self.diameter_combo.clear()
            self.cumulative_combo.clear()
            
            self.diameter_combo.addItem("Select column...")
            self.cumulative_combo.addItem("Select column...")
            
            for col in headers:
                self.diameter_combo.addItem(col)
                self.cumulative_combo.addItem(col)
            
            # Try to auto-select reasonable defaults
            for i, col in enumerate(headers):
                col_lower = col.lower()
                if any(word in col_lower for word in ['diameter', 'size', 'grain', 'particle', 'sieve']):
                    if self.diameter_combo.currentText() == "Select column...":
                        self.diameter_combo.setCurrentIndex(i + 1)
                elif any(word in col_lower for word in ['cumulative', 'passing', 'percent', 'cum']):
                    if self.cumulative_combo.currentText() == "Select column...":
                        self.cumulative_combo.setCurrentIndex(i + 1)
            
            # Update UI
            self.sample_info_label.setText(f"✅ Detected {len(headers)} columns. Please verify mapping below.")
            
        except Exception as e:
            self.sample_info_label.setText(f"❌ Error loading file: {str(e)}")
    
    def _is_numeric(self, value: str) -> bool:
        """Check if a string represents a number"""
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    def update_analysis_progress(self, current, total, current_sample=""):
        """Update progress bar during analysis"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
            
            if current_sample:
                self.progress_label.setText(f"🔄 Analyzing: {current_sample} ({current}/{total})")
            else:
                self.progress_label.setText(f"🔄 Processing... ({current}/{total})")
    
    def analysis_complete(self, results):
        """Called when analysis is complete"""
        self.show_progress(False)
        
        # Update sample statuses
        for sample_name in results:
            if sample_name in self.loaded_samples:
                self.loaded_samples[sample_name]['status'] = 'Analyzed'
        
        # Update UI
        success_count = len(results)
        self.progress_label.setText(f"✅ Analysis complete! {success_count} sample(s) processed")
        
        # Auto-export if enabled
        if self.export_results_cb.isChecked():
            self.progress_label.setText(f"✅ Analysis complete! Results exported for {success_count} sample(s)")
    
    def get_analysis_parameters(self):
        """Get current analysis parameters"""
        return {
            'temperature': self.temp_spinbox.value(),
            'porosity': self.porosity_spinbox.value(),
            'diameter_column': self.diameter_combo.currentText(),
            'cumulative_column': self.cumulative_combo.currentText(),
            'auto_export': self.export_results_cb.isChecked()
        }
    
    def get_loaded_samples(self):
        """Get dictionary of loaded samples"""
        return self.loaded_samples.copy()
    
    def set_sample_status(self, sample_name, status):
        """Update the status of a specific sample"""
        if sample_name in self.loaded_samples:
            self.loaded_samples[sample_name]['status'] = status
            
            # Update UI list item tooltip
            for i in range(self.samples_list.count()):
                item = self.samples_list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == sample_name:
                    file_path = self.loaded_samples[sample_name]['file_path']
                    item.setToolTip(f"File: {file_path}\nStatus: {status}")
                    break
            
    def show_progress(self, show=True):
        """Show/hide progress bar"""
        self.progress_bar.setVisible(show)
        
    def set_progress(self, value):
        """Set progress bar value (0-100)"""
        self.progress_bar.setValue(value)
        
    # ================================
    # VALIDATION METHODS
    # ================================
    
    def validate_temperature(self, value):
        """Validate temperature input"""
        self.validation_errors = [err for err in self.validation_errors if 'Temperature' not in err]
        
        if value < 0 or value > 50:
            self.validation_errors.append("🌡️ Temperature should be between 0-50°C for realistic conditions")
        elif value < 5:
            self.validation_errors.append("⚠️ Temperature below 5°C may affect viscosity calculations")
        elif value > 35:
            self.validation_errors.append("⚠️ Temperature above 35°C is unusual for groundwater")
            
        self.update_validation_display()
    
    def validate_porosity(self, value):
        """Validate porosity input"""
        self.validation_errors = [err for err in self.validation_errors if 'Porosity' not in err]
        
        if value < 0.1 or value > 0.8:
            self.validation_errors.append("🕳️ Porosity should be between 0.1-0.8 for natural soils")
        elif value < 0.2:
            self.validation_errors.append("ℹ️ Low porosity (<0.2) typical for dense sands/clays")
        elif value > 0.6:
            self.validation_errors.append("ℹ️ High porosity (>0.6) typical for loose/organic soils")
            
        self.update_validation_display()
    
    def validate_column_mapping(self):
        """Validate column mapping selection"""
        self.validation_errors = [err for err in self.validation_errors if 'Column' not in err]
        
        diameter_col = self.diameter_combo.currentText()
        cumulative_col = self.cumulative_combo.currentText()
        
        if diameter_col == "Select column..." or diameter_col == "":
            self.validation_errors.append("📊 Column: Please select a diameter column")
        
        if cumulative_col == "Select column..." or cumulative_col == "":
            self.validation_errors.append("📊 Column: Please select a cumulative percent column")
            
        if diameter_col == cumulative_col and diameter_col != "Select column...":
            self.validation_errors.append("❌ Column: Diameter and cumulative columns cannot be the same")
            
        self.update_validation_display()
    
    def validate_samples(self):
        """Validate that samples are loaded and ready"""
        self.validation_errors = [err for err in self.validation_errors if 'Sample' not in err]
        
        if not self.loaded_samples:
            self.validation_errors.append("📁 Samples: No samples loaded - please add data files")
        else:
            for sample_name, sample_data in self.loaded_samples.items():
                if sample_data['status'] == 'Error':
                    self.validation_errors.append(f"❌ Sample '{sample_name}': Failed to load properly")
                    
        self.update_validation_display()
    
    def update_validation_display(self):
        """Update the validation status display"""
        if not self.validation_errors:
            self.validation_label.setText("✅ All parameters valid - ready for analysis!")
            self.validation_label.setStyleSheet("color: #6b8e23; font-weight: bold;")
            
            # Enable analysis if we have samples
            if self.loaded_samples:
                self.analyze_all_btn.setEnabled(True)
                if self.samples_list.currentItem():
                    self.analyze_selected_btn.setEnabled(True)
        else:
            # Show the most critical errors (limit to 3)
            display_errors = self.validation_errors[:3]
            error_text = "\n".join(display_errors)
            if len(self.validation_errors) > 3:
                error_text += f"\n... and {len(self.validation_errors) - 3} more issues"
                
            self.validation_label.setText(error_text)
            self.validation_label.setStyleSheet("color: #d2691e; font-weight: normal;")
            
            # Disable analysis if there are critical errors
            critical_errors = [err for err in self.validation_errors if '❌' in err or 'should be' in err]
            if critical_errors:
                self.analyze_all_btn.setEnabled(False)
                self.analyze_selected_btn.setEnabled(False)
    
    def perform_full_validation(self):
        """Perform complete validation of all parameters"""
        self.validation_errors.clear()
        
        # Validate all components
        self.validate_temperature(self.temp_spinbox.value())
        self.validate_porosity(self.porosity_spinbox.value())
        self.validate_column_mapping()
        self.validate_samples()
        
        return len([err for err in self.validation_errors if '❌' in err or 'should be' in err]) == 0
