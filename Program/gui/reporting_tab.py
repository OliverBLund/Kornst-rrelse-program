"""
Reporting tab for generating professional analysis reports
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QTextEdit, QGroupBox, QCheckBox, QFileDialog,
    QMessageBox, QToolBar, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextDocument, QTextCursor
from typing import List, Optional
import os

from report_generator import ReportGenerator
from data_loader import GrainSizeData
from k_calculations import KCalculationResult


class ReportingTab(QWidget):
    """
    Tab for generating and previewing professional reports
    """
    
    # Signals
    report_generated = pyqtSignal(str)  # Emitted when report is generated
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.report_generator = ReportGenerator()
        self.dataset_tabs = []  # Will be populated by main window
        self.current_report_html = ""
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Create toolbar
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)
        
        # Create main content area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Report configuration
        config_panel = self.create_config_panel()
        config_panel.setMaximumWidth(300)
        
        # Right panel - Report preview
        preview_panel = self.create_preview_panel()
        
        splitter.addWidget(config_panel)
        splitter.addWidget(preview_panel)
        splitter.setStretchFactor(0, 0)  # Config panel doesn't stretch
        splitter.setStretchFactor(1, 1)  # Preview panel stretches
        
        layout.addWidget(splitter)
    
    def create_toolbar(self):
        """Create the toolbar with export options"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #f5f5f0;
                border: 1px solid #d4c4a8;
                padding: 4px;
                spacing: 4px;
            }
            QPushButton {
                padding: 6px 12px;
                font-size: 10px;
                background-color: #d2b48c;
                border: 1px solid #8b7355;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ddbf94;
            }
        """)
        
        # Export buttons
        self.export_html_btn = QPushButton("📄 Export HTML")
        self.export_html_btn.clicked.connect(self.export_html)
        self.export_html_btn.setEnabled(False)
        toolbar.addWidget(self.export_html_btn)
        
        self.export_pdf_btn = QPushButton("📑 Export PDF")
        self.export_pdf_btn.clicked.connect(self.export_pdf)
        self.export_pdf_btn.setEnabled(False)
        toolbar.addWidget(self.export_pdf_btn)
        
        self.print_btn = QPushButton("🖨️ Print")
        self.print_btn.clicked.connect(self.print_report)
        self.print_btn.setEnabled(False)
        toolbar.addWidget(self.print_btn)
        
        # Add stretch
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy(), 
                           spacer.sizePolicy().verticalPolicy())
        toolbar.addWidget(spacer)
        
        # Copy button
        self.copy_btn = QPushButton("📋 Copy to Clipboard")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.copy_btn.setEnabled(False)
        toolbar.addWidget(self.copy_btn)
        
        return toolbar
    
    def create_config_panel(self):
        """Create the configuration panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Report type selection
        type_group = QGroupBox("Report Type")
        type_layout = QVBoxLayout(type_group)
        
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems([
            "Individual - Grain Size",
            "Individual - K-Values",
            "Individual - Combined",
            "Multi-Sample Comparison",
            "Full Analysis Report"
        ])
        self.report_type_combo.currentTextChanged.connect(self.on_report_type_changed)
        type_layout.addWidget(self.report_type_combo)
        
        layout.addWidget(type_group)
        
        # Sample selection
        self.sample_group = QGroupBox("Sample Selection")
        sample_layout = QVBoxLayout(self.sample_group)
        
        self.sample_combo = QComboBox()
        self.sample_combo.addItem("No samples available")
        sample_layout.addWidget(self.sample_combo)
        
        # Multi-sample checkboxes will be added dynamically
        self.sample_checks_widget = QWidget()
        self.sample_checks_layout = QVBoxLayout(self.sample_checks_widget)
        self.sample_checks_widget.setVisible(False)
        sample_layout.addWidget(self.sample_checks_widget)
        
        layout.addWidget(self.sample_group)
        
        # Report options
        options_group = QGroupBox("Report Options")
        options_layout = QVBoxLayout(options_group)
        
        self.include_plots_check = QCheckBox("Include Plots")
        self.include_plots_check.setChecked(True)
        options_layout.addWidget(self.include_plots_check)
        
        self.include_raw_data_check = QCheckBox("Include Raw Data")
        self.include_raw_data_check.setChecked(False)
        options_layout.addWidget(self.include_raw_data_check)
        
        self.include_statistics_check = QCheckBox("Include Statistics")
        self.include_statistics_check.setChecked(True)
        options_layout.addWidget(self.include_statistics_check)
        
        self.include_interpretation_check = QCheckBox("Include Interpretation")
        self.include_interpretation_check.setChecked(True)
        options_layout.addWidget(self.include_interpretation_check)
        
        layout.addWidget(options_group)
        
        # Generate button
        self.generate_btn = QPushButton("🔄 Generate Report")
        self.generate_btn.clicked.connect(self.generate_report)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b8e23;
                color: white;
                font-weight: bold;
                padding: 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #7fa02d;
            }
        """)
        layout.addWidget(self.generate_btn)
        
        layout.addStretch()
        
        return panel
    
    def create_preview_panel(self):
        """Create the report preview panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel("Report Preview")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)
        
        # Preview area
        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #ddd;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        
        # Set initial content
        self.preview_edit.setHtml("""
            <div style="text-align: center; padding: 50px; color: #999;">
                <h2>No Report Generated</h2>
                <p>Select report type and sample(s), then click "Generate Report"</p>
            </div>
        """)
        
        layout.addWidget(self.preview_edit)
        
        return panel
    
    def set_dataset_tabs(self, dataset_tabs: List):
        """Set the available dataset tabs"""
        self.dataset_tabs = dataset_tabs
        self.update_sample_selection()
    
    def update_sample_selection(self):
        """Update the sample selection based on available datasets"""
        self.sample_combo.clear()
        
        # Clear multi-sample checkboxes
        while self.sample_checks_layout.count():
            item = self.sample_checks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.dataset_tabs:
            self.sample_combo.addItem("No samples available")
            self.generate_btn.setEnabled(False)
            return
        
        # Add samples to combo box
        for tab in self.dataset_tabs:
            self.sample_combo.addItem(tab.get_dataset_name())
        
        # Add checkboxes for multi-sample selection
        for tab in self.dataset_tabs:
            checkbox = QCheckBox(tab.get_dataset_name())
            checkbox.setChecked(True)
            self.sample_checks_layout.addWidget(checkbox)
        
        self.generate_btn.setEnabled(True)
    
    def on_report_type_changed(self, text: str):
        """Handle report type change"""
        # Show/hide sample selection based on report type
        is_multi_sample = "Multi-Sample" in text or "Full Analysis" in text
        
        self.sample_combo.setVisible(not is_multi_sample)
        self.sample_checks_widget.setVisible(is_multi_sample)
        
        # Update sample group title
        if is_multi_sample:
            self.sample_group.setTitle("Sample Selection (Select Multiple)")
        else:
            self.sample_group.setTitle("Sample Selection")
    
    def generate_report(self):
        """Generate the selected report"""
        if not self.dataset_tabs:
            QMessageBox.warning(self, "No Data", "Please load datasets first")
            return
        
        report_type = self.report_type_combo.currentText()
        
        try:
            if "Individual" in report_type:
                self.generate_individual_report(report_type)
            elif "Multi-Sample" in report_type:
                self.generate_comparison_report()
            elif "Full Analysis" in report_type:
                self.generate_full_report()
            
            # Enable export buttons
            self.export_html_btn.setEnabled(True)
            self.export_pdf_btn.setEnabled(True)
            self.print_btn.setEnabled(True)
            self.copy_btn.setEnabled(True)
            
            self.report_generated.emit(report_type)
            
        except Exception as e:
            QMessageBox.critical(self, "Report Generation Error", 
                               f"Failed to generate report:\n{str(e)}")
    
    def generate_individual_report(self, report_type: str):
        """Generate an individual sample report"""
        # Get selected sample
        sample_index = self.sample_combo.currentIndex()
        if sample_index < 0 or sample_index >= len(self.dataset_tabs):
            return
        
        dataset_tab = self.dataset_tabs[sample_index]
        dataset = dataset_tab.get_dataset()
        
        if "Grain Size" in report_type:
            html = self.report_generator.generate_grain_size_report(
                dataset,
                include_plot=self.include_plots_check.isChecked(),
                include_raw_data=self.include_raw_data_check.isChecked()
            )
        elif "K-Values" in report_type:
            k_results = dataset_tab.get_results()
            html = self.report_generator.generate_k_value_report(
                dataset,
                k_results,
                dataset_tab.temperature,
                dataset_tab.porosity
            )
        else:  # Combined
            k_results = dataset_tab.get_results()
            html = self.report_generator.generate_combined_report(
                dataset,
                k_results,
                dataset_tab.temperature,
                dataset_tab.porosity
            )
        
        self.current_report_html = html
        self.preview_edit.setHtml(html)
    
    def generate_comparison_report(self):
        """Generate a multi-sample comparison report"""
        # Get selected samples
        selected_tabs = []
        for i in range(self.sample_checks_layout.count()):
            checkbox = self.sample_checks_layout.itemAt(i).widget()
            if checkbox and checkbox.isChecked():
                # Find corresponding tab
                for tab in self.dataset_tabs:
                    if tab.get_dataset_name() == checkbox.text():
                        selected_tabs.append(tab)
                        break
        
        if not selected_tabs:
            QMessageBox.warning(self, "No Selection", 
                              "Please select at least one sample")
            return
        
        # Collect data
        datasets = [tab.get_dataset() for tab in selected_tabs]
        k_results_dict = {}
        
        for tab in selected_tabs:
            k_results = tab.get_results()
            if k_results:
                k_results_dict[tab.get_dataset_name()] = k_results
        
        # Generate report
        html = self.report_generator.generate_comparison_report(
            datasets,
            k_results_dict,
            selected_tabs[0].temperature if selected_tabs else 20.0,
            selected_tabs[0].porosity if selected_tabs else 0.4
        )
        
        self.current_report_html = html
        self.preview_edit.setHtml(html)
    
    def generate_full_report(self):
        """Generate a full analysis report for all samples"""
        # Select all samples and generate comparison
        for i in range(self.sample_checks_layout.count()):
            checkbox = self.sample_checks_layout.itemAt(i).widget()
            if checkbox:
                checkbox.setChecked(True)
        
        self.generate_comparison_report()
    
    def export_html(self):
        """Export report as HTML"""
        if not self.current_report_html:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report as HTML",
            "report.html",
            "HTML Files (*.html)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.current_report_html)
                
                QMessageBox.information(self, "Export Successful",
                                      f"Report exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error",
                                   f"Failed to export report:\n{str(e)}")
    
    def export_pdf(self):
        """Export report as PDF"""
        if not self.current_report_html:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report as PDF",
            "report.pdf",
            "PDF Files (*.pdf)"
        )
        
        if file_path:
            try:
                from PyQt6.QtPrintSupport import QPrinter
                from PyQt6.QtGui import QPageLayout, QPageSize
                
                printer = QPrinter(QPrinter.PrinterMode.HighResolution)
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                printer.setOutputFileName(file_path)
                printer.setPageSize(QPageSize.PageSizeId.A4)
                
                # Create document from HTML
                document = QTextDocument()
                document.setHtml(self.current_report_html)
                document.print(printer)
                
                QMessageBox.information(self, "Export Successful",
                                      f"Report exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error",
                                   f"Failed to export PDF:\n{str(e)}")
    
    def print_report(self):
        """Print the report"""
        if not self.current_report_html:
            return
        
        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dialog = QPrintDialog(printer, self)
            
            if dialog.exec() == QPrintDialog.DialogCode.Accepted:
                document = QTextDocument()
                document.setHtml(self.current_report_html)
                document.print(printer)
        except Exception as e:
            QMessageBox.critical(self, "Print Error",
                               f"Failed to print report:\n{str(e)}")
    
    def copy_to_clipboard(self):
        """Copy report to clipboard"""
        if not self.current_report_html:
            return
        
        try:
            from PyQt6.QtWidgets import QApplication
            
            clipboard = QApplication.clipboard()
            clipboard.setText(self.preview_edit.toPlainText())
            
            QMessageBox.information(self, "Copied",
                                  "Report copied to clipboard")
        except Exception as e:
            QMessageBox.critical(self, "Copy Error",
                               f"Failed to copy report:\n{str(e)}")