"""
Column mapping dialog for CSV files with unknown formats
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
                            QDialogButtonBox, QGroupBox, QFormLayout, QSpinBox,
                            QDoubleSpinBox, QTextEdit, QTabWidget, QWidget,
                            QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
import csv
from typing import Dict, List, Optional, Tuple
import os

class ColumnMapperDialog(QDialog):
    """Dialog for mapping CSV columns to grain size data"""
    
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.column_mapping = {}
        self.sample_data = []
        self.headers = []
        
        self.setWindowTitle(f"Map Columns - {os.path.basename(file_path)}")
        self.setModal(True)
        self.resize(800, 600)
        
        # Apply professional styling
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #8b7355;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fafaf7;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: #f5f5f0;
            }
            QLabel {
                color: #2f2f2f;
                font-size: 11px;
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                padding: 5px;
                border: 1px solid #8b7355;
                border-radius: 3px;
                background-color: white;
            }
            QPushButton {
                background-color: #8b7355;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6d5a42;
            }
            QPushButton:pressed {
                background-color: #5a4835;
            }
        """)
        
        try:
            self.load_csv_preview()
            self.setup_ui()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load CSV file:\n{str(e)}")
            self.reject()
    
    def load_csv_preview(self):
        """Load first few rows of file for preview"""
        file_ext = os.path.splitext(self.file_path)[1].lower()
        rows = []
        
        if file_ext == '.csv':
            with open(self.file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                for i, row in enumerate(reader):
                    if i >= 20:  # Limit preview to 20 rows
                        break
                    rows.append(row)
        elif file_ext in ['.xlsx', '.xls']:
            # Load Excel file with pandas
            import pandas as pd
            df = pd.read_excel(self.file_path, nrows=20)
            # Convert dataframe to list of lists
            rows = [df.columns.tolist()] + df.values.tolist()
            rows = [[str(cell) for cell in row] for row in rows]  # Convert all to strings
        
        if not rows:
            raise ValueError("CSV file is empty")
        
        # Try to detect header row
        self.headers = self.detect_headers(rows)
        self.sample_data = rows[:10]  # Show first 10 rows
    
    def detect_headers(self, rows: List[List[str]]) -> List[str]:
        """Try to detect which row contains headers"""
        for i, row in enumerate(rows[:5]):  # Check first 5 rows
            if len(row) >= 2:
                # Check if this row looks like headers (contains text, not just numbers)
                text_count = sum(1 for cell in row if not self.is_numeric(cell.strip()))
                if text_count >= len(row) * 0.5:  # At least half are text
                    return [cell.strip() for cell in row]
        
        # If no headers detected, create generic ones
        max_cols = max(len(row) for row in rows) if rows else 2
        return [f"Column {i+1}" for i in range(max_cols)]
    
    def is_numeric(self, value: str) -> bool:
        """Check if a string represents a number"""
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Create tab widget
        tab_widget = QTabWidget()
        
        # Tab 1: Column Mapping
        mapping_tab = QWidget()
        mapping_layout = QVBoxLayout(mapping_tab)
        
        # Preview group
        preview_group = QGroupBox("File Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_table = QTableWidget()
        self.setup_preview_table()
        preview_layout.addWidget(self.preview_table)
        
        mapping_layout.addWidget(preview_group)
        
        # Mapping group
        mapping_group = QGroupBox("Column Mapping")
        mapping_form = QFormLayout(mapping_group)
        
        # Create combo boxes for mapping
        self.size_combo = QComboBox()
        self.passing_combo = QComboBox()
        self.retained_combo = QComboBox()
        
        # Populate combo boxes
        column_options = ["(Not Used)"] + self.headers
        for combo in [self.size_combo, self.passing_combo, self.retained_combo]:
            combo.addItems(column_options)
        
        # Try auto-detection
        self.auto_detect_columns()
        
        mapping_form.addRow("Particle Size (mm):", self.size_combo)
        mapping_form.addRow("Percent Passing (%):", self.passing_combo)
        mapping_form.addRow("Percent Retained (%):", self.retained_combo)
        
        # Add help text
        help_text = QLabel("""
💡 Instructions:
• Select which columns contain particle sizes and percentages
• If your data has "Percent Retained", it will be converted to "Percent Passing"
• Leave unused columns as "(Not Used)"
• Particle sizes should be in millimeters
        """)
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666; font-style: italic; margin: 10px;")
        mapping_form.addRow(help_text)
        
        mapping_layout.addWidget(mapping_group)
        
        tab_widget.addTab(mapping_tab, "📊 Column Mapping")
        
        # Tab 2: Sample Parameters
        params_tab = QWidget()
        params_layout = QVBoxLayout(params_tab)
        
        params_group = QGroupBox("Sample Parameters")
        params_form = QFormLayout(params_group)
        
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0, 50)
        self.temperature_spin.setValue(20.0)
        self.temperature_spin.setSuffix(" °C")
        
        self.porosity_spin = QDoubleSpinBox()
        self.porosity_spin.setRange(0.1, 0.9)
        self.porosity_spin.setValue(0.40)
        self.porosity_spin.setDecimals(3)
        
        self.sample_name_edit = QTextEdit()
        self.sample_name_edit.setMaximumHeight(60)
        self.sample_name_edit.setPlainText(os.path.splitext(os.path.basename(self.file_path))[0])
        
        params_form.addRow("Temperature:", self.temperature_spin)
        params_form.addRow("Porosity:", self.porosity_spin)
        params_form.addRow("Sample Name:", self.sample_name_edit)
        
        params_layout.addWidget(params_group)
        params_layout.addStretch()
        
        tab_widget.addTab(params_tab, "⚙️ Parameters")
        
        layout.addWidget(tab_widget)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                     QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # Add preview button
        preview_btn = QPushButton("🔍 Preview Results")
        preview_btn.clicked.connect(self.preview_mapping)
        button_box.addButton(preview_btn, QDialogButtonBox.ButtonRole.ActionRole)
        
        layout.addWidget(button_box)
    
    def setup_preview_table(self):
        """Setup the preview table with CSV data"""
        if not self.sample_data:
            return
        
        max_cols = max(len(row) for row in self.sample_data)
        self.preview_table.setRowCount(len(self.sample_data))
        self.preview_table.setColumnCount(max_cols)
        
        # Set headers
        if len(self.headers) >= max_cols:
            self.preview_table.setHorizontalHeaderLabels(self.headers[:max_cols])
        else:
            headers = self.headers + [f"Col {i+1}" for i in range(len(self.headers), max_cols)]
            self.preview_table.setHorizontalHeaderLabels(headers)
        
        # Fill data
        for i, row in enumerate(self.sample_data):
            for j, cell in enumerate(row):
                if j < max_cols:
                    item = QTableWidgetItem(str(cell))
                    # Highlight numeric data
                    if self.is_numeric(cell.strip()):
                        item.setBackground(QColor(200, 255, 200))  # Light green
                    self.preview_table.setItem(i, j, item)
        
        # Adjust column widths
        self.preview_table.resizeColumnsToContents()
    
    def auto_detect_columns(self):
        """Try to automatically detect column types"""
        if not self.headers:
            return
        
        size_keywords = ['size', 'diameter', 'grain', 'particle', 'sieve', 'mesh', 'mm']
        passing_keywords = ['passing', 'pass', 'finer', 'cumulative']
        retained_keywords = ['retained', 'retain']
        
        for i, header in enumerate(self.headers):
            header_lower = header.lower()
            
            # Check for size column
            if any(keyword in header_lower for keyword in size_keywords):
                self.size_combo.setCurrentIndex(i + 1)  # +1 because of "(Not Used)"
            
            # Check for passing column
            elif any(keyword in header_lower for keyword in passing_keywords):
                self.passing_combo.setCurrentIndex(i + 1)
            
            # Check for retained column
            elif any(keyword in header_lower for keyword in retained_keywords):
                self.retained_combo.setCurrentIndex(i + 1)
    
    def preview_mapping(self):
        """Preview the results of the current mapping"""
        try:
            particle_sizes, percent_passing = self.extract_data()
            
            preview_text = f"Preview Results:\n"
            preview_text += f"Extracted {len(particle_sizes)} data points\n\n"
            
            if len(particle_sizes) > 0:
                preview_text += f"Size range: {min(particle_sizes):.3f} - {max(particle_sizes):.3f} mm\n"
                preview_text += f"Passing range: {min(percent_passing):.1f}% - {max(percent_passing):.1f}%\n\n"
                
                preview_text += "First 5 data points:\n"
                for i in range(min(5, len(particle_sizes))):
                    preview_text += f"  {particle_sizes[i]:.3f} mm → {percent_passing[i]:.1f}%\n"
            
            QMessageBox.information(self, "Preview Results", preview_text)
            
        except Exception as e:
            QMessageBox.warning(self, "Preview Error", f"Error in mapping:\n{str(e)}")
    
    def extract_data(self) -> Tuple[List[float], List[float]]:
        """Extract data based on current column mapping"""
        size_idx = self.size_combo.currentIndex() - 1  # -1 for "(Not Used)"
        passing_idx = self.passing_combo.currentIndex() - 1
        retained_idx = self.retained_combo.currentIndex() - 1
        
        if size_idx < 0:
            raise ValueError("Please select a particle size column")
        
        if passing_idx < 0 and retained_idx < 0:
            raise ValueError("Please select either a passing or retained column")
        
        particle_sizes = []
        percent_passing = []
        
        # Load all data (not just preview)
        file_ext = os.path.splitext(self.file_path)[1].lower()
        
        if file_ext == '.csv':
            with open(self.file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                rows = list(reader)
        elif file_ext in ['.xlsx', '.xls']:
            import pandas as pd
            df = pd.read_excel(self.file_path)
            rows = [df.columns.tolist()] + df.values.tolist()
            rows = [[str(cell) for cell in row] for row in rows]
        
        # Skip header row(s)
        data_rows = rows[1:] if len(rows) > 1 else rows
        
        for row in data_rows:
            if len(row) <= max(size_idx, passing_idx, retained_idx):
                continue
            
            try:
                # Extract particle size
                size_str = row[size_idx].strip()
                if not size_str or not self.is_numeric(size_str):
                    continue
                size = float(size_str)
                
                # Extract percentage
                passing = None
                if passing_idx >= 0:
                    passing_str = row[passing_idx].strip()
                    if not passing_str or not self.is_numeric(passing_str):
                        continue
                    passing = float(passing_str)
                elif retained_idx >= 0:
                    retained_str = row[retained_idx].strip()
                    if not retained_str or not self.is_numeric(retained_str):
                        continue
                    retained = float(retained_str)
                    passing = 100.0 - retained  # Convert retained to passing
                
                if passing is not None:
                    particle_sizes.append(size)
                    percent_passing.append(passing)
                
            except (ValueError, IndexError):
                continue
        
        if not particle_sizes:
            raise ValueError("No valid data points extracted")
        
        return particle_sizes, percent_passing
    
    def get_mapping_result(self) -> Dict:
        """Get the final mapping result"""
        try:
            particle_sizes, percent_passing = self.extract_data()
            
            return {
                'particle_sizes': particle_sizes,
                'percent_passing': percent_passing,
                'sample_name': self.sample_name_edit.toPlainText().strip(),
                'temperature': self.temperature_spin.value(),
                'porosity': self.porosity_spin.value()
            }
        except Exception as e:
            raise ValueError(f"Mapping failed: {str(e)}")
