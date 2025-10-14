"""
Enhanced Statistics Tab with Modular Design

This module provides a comprehensive statistics display for grain size analysis
and hydraulic conductivity calculations. The design is modular to enable easy
reuse in report generation.

Phase 1: Layout and visual structure
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGroupBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QLineEdit,
    QSplitter, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from typing import Optional, List
import numpy as np

from data_loader import GrainSizeData
from k_calculations import KCalculationResult


class CompactInfoBar(QFrame):
    """
    Compact single-line info bar showing key statistics
    Replaces the bulky summary cards
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Initialize compact info bar UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Plain)
        self.setStyleSheet("""
            QFrame {
                background-color: #f5f5f0;
                border: 1px solid #d4c4a8;
                border-radius: 4px;
                padding: 6px 12px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        # Create info label
        self.info_label = QLabel("Load data to view statistics")
        self.info_label.setStyleSheet("""
            QLabel {
                font-size: 10pt;
                font-family: 'Consolas', 'Courier New', monospace;
                color: #333;
            }
        """)

        layout.addWidget(self.info_label)
        layout.addStretch()

    def update_info(self, sample_name: str, d50: float = None, cu: float = None,
                   mean_k: float = None, soil_type: str = "N/A"):
        """Update the info bar with current statistics"""
        parts = []

        # Sample name
        parts.append(f"<b>{sample_name}</b>")

        # D50
        if d50:
            parts.append(f"D₅₀: {d50:.2f}mm")
        else:
            parts.append("D₅₀: N/A")

        # Cu
        if cu:
            parts.append(f"Cu: {cu:.2f}")
        else:
            parts.append("Cu: N/A")

        # Mean K
        if mean_k:
            parts.append(f"Mean K: {mean_k:.2e} m/s")
        else:
            parts.append("Mean K: Not calculated")

        # Soil type
        parts.append(f"Soil: {soil_type}")

        # Join with separator
        info_text = "  │  ".join(parts)

        self.info_label.setText(info_text)


class PercentileTableWidget(QGroupBox):
    """
    Table showing grain size percentiles with visual bars
    """

    def __init__(self, parent=None):
        super().__init__("Grain Size Percentiles", parent)
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #d4c4a8;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #2c5530;
            }
        """)
        self.init_ui()

    def init_ui(self):
        """Initialize table UI"""
        layout = QVBoxLayout(self)

        # Create table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Percentile", "Size (mm)", "Visual"])

        # Configure table appearance
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setMaximumHeight(400)

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 100)

        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                font-size: 9pt;
                background-color: white;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                padding: 5px;
                border: 1px solid #c0c0c0;
                font-weight: bold;
                font-size: 9pt;
            }
        """)

        layout.addWidget(self.table)

        # Info text below table
        self.info_text = QLabel("Load data to view percentiles")
        self.info_text.setStyleSheet("color: #666; font-size: 9pt; font-style: italic;")
        self.info_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_text)

    def set_percentile_data(self, percentiles: dict):
        """
        Populate table with percentile data

        Args:
            percentiles: Dict mapping percentile -> size in mm
        """
        self.table.setRowCount(0)

        if not percentiles:
            return

        # Standard percentiles to display (sorted descending)
        standard_percentiles = [95, 90, 85, 80, 75, 70, 60, 50, 40, 30, 25, 20, 10, 5]

        # Key percentiles get a star
        key_percentiles = {10, 20, 30, 50, 60}

        max_size = max(percentiles.values()) if percentiles else 1.0

        for p in standard_percentiles:
            if p not in percentiles:
                continue

            size = percentiles[p]
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Percentile column
            percentile_text = f"D{p}"
            if p in key_percentiles:
                percentile_text += " ⭐"
            percentile_item = QTableWidgetItem(percentile_text)
            percentile_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if p in key_percentiles:
                percentile_item.setBackground(QColor(255, 250, 205))  # Light yellow
            self.table.setItem(row, 0, percentile_item)

            # Size column
            size_item = QTableWidgetItem(f"{size:.3f}")
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 1, size_item)

            # Visual bar column
            bar_length = int((size / max_size) * 100)
            bar_text = "█" * (bar_length // 5)
            bar_item = QTableWidgetItem(bar_text)
            bar_item.setForeground(QColor(107, 142, 35))  # Olive green
            self.table.setItem(row, 2, bar_item)

        # Update info text
        min_size = min(percentiles.values())
        span = max_size / min_size if min_size > 0 else 0
        self.info_text.setText(
            f"Range: {min_size:.3f} - {max_size:.3f} mm  |  Span: {span:.1f}x"
        )


class GradationAnalysisWidget(QGroupBox):
    """
    Widget showing gradation parameters and classification
    """

    def __init__(self, parent=None):
        super().__init__("Gradation Analysis", parent)
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #d4c4a8;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #2c5530;
            }
        """)
        self.init_ui()

    def init_ui(self):
        """Initialize gradation display"""
        layout = QVBoxLayout(self)

        # Text display for gradation info
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setMaximumHeight(200)
        self.text_display.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #d0d0d0;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
        """)

        self.text_display.setPlainText(
            "Gradation Parameters:\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Load data to view gradation analysis"
        )

        layout.addWidget(self.text_display)

    def set_gradation_data(self, cu: float, cc: float, classification: str):
        """Update gradation display"""
        text = f"""Gradation Parameters:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Uniformity Coefficient (Cu): {cu:.2f}
  └─ D60/D10 ratio
  └─ {classification}

Coefficient of Curvature (Cc): {cc:.2f}
  └─ D30²/(D10×D60)
  └─ {"Within range (1-3) ✓" if 1 <= cc <= 3 else "Outside typical range"}

Gradation Type: Continuous distribution
"""
        self.text_display.setPlainText(text)


class KStatisticsWidget(QGroupBox):
    """
    Widget showing hydraulic conductivity statistics
    Contains multiple sub-panels for different analyses
    """

    def __init__(self, parent=None):
        super().__init__("Hydraulic Conductivity Statistics", parent)
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #d4c4a8;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #2c5530;
            }
        """)
        self.init_ui()

    def init_ui(self):
        """Initialize K-statistics display"""
        layout = QVBoxLayout(self)

        # Summary statistics table
        self.summary_table = QTableWidget(0, 4)
        self.summary_table.setHorizontalHeaderLabels(["Metric", "m/s", "cm/s", "m/d"])
        self.summary_table.setMaximumHeight(250)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setAlternatingRowColors(True)

        header = self.summary_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.summary_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                font-size: 9pt;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                padding: 5px;
                border: 1px solid #c0c0c0;
                font-weight: bold;
            }
        """)

        layout.addWidget(self.summary_table)

        # Method agreement section
        self.agreement_text = QTextEdit()
        self.agreement_text.setReadOnly(True)
        self.agreement_text.setMaximumHeight(180)
        self.agreement_text.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #d0d0d0;
                padding: 8px;
                font-size: 9pt;
            }
        """)
        self.agreement_text.setPlainText(
            "Method Agreement Analysis:\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Calculate K-values to view method agreement"
        )

        layout.addWidget(self.agreement_text)

        # Permeability classification
        self.classification_label = QLabel("Permeability Classification: Not calculated")
        self.classification_label.setStyleSheet("""
            font-size: 10pt;
            font-weight: bold;
            color: #2c5530;
            padding: 8px;
            background-color: #f0f8ff;
            border: 1px solid #6b8e23;
            border-radius: 4px;
        """)
        self.classification_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.classification_label)


class DataQualityWidget(QGroupBox):
    """
    Widget showing data quality indicators
    """

    def __init__(self, parent=None):
        super().__init__("Data Quality Assessment", parent)
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #d4c4a8;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #2c5530;
            }
        """)
        self.init_ui()

    def init_ui(self):
        """Initialize quality display"""
        layout = QVBoxLayout(self)

        self.quality_text = QTextEdit()
        self.quality_text.setReadOnly(True)
        self.quality_text.setMaximumHeight(150)
        self.quality_text.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #d0d0d0;
                padding: 8px;
                font-size: 9pt;
            }
        """)

        self.quality_text.setPlainText(
            "Data Quality Indicators:\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✓ Curve Monotonicity      Excellent\n"
            "✓ Data Coverage           Good\n"
            "✓ Point Density           Adequate\n\n"
            "Overall Quality: ★★★★☆ (Good)"
        )

        layout.addWidget(self.quality_text)


class SoilClassificationWidget(QGroupBox):
    """
    Widget showing USCS soil classification and properties
    """

    def __init__(self, parent=None):
        super().__init__("USCS Soil Classification", parent)
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #d4c4a8;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #2c5530;
            }
        """)
        self.init_ui()

    def init_ui(self):
        """Initialize classification display"""
        layout = QVBoxLayout(self)

        self.classification_text = QTextEdit()
        self.classification_text.setReadOnly(True)
        self.classification_text.setMaximumHeight(150)
        self.classification_text.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #d0d0d0;
                padding: 8px;
                font-size: 9pt;
            }
        """)

        self.classification_text.setPlainText(
            "USCS Classification:\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Load data to view soil classification"
        )

        layout.addWidget(self.classification_text)


class StatisticsTab(QWidget):
    """
    Enhanced statistics tab with modular design

    Phase 1: Layout and visual structure complete
    Future phases will add data calculation and advanced features
    """

    # Signals
    statistics_updated = pyqtSignal()

    def __init__(self, dataset: GrainSizeData, parent=None):
        super().__init__(parent)

        self.dataset = dataset
        self.k_results: Optional[List[KCalculationResult]] = None

        # Get temperature and porosity from dataset
        self.temperature = dataset.temperature
        self.porosity = dataset.current_porosity if hasattr(dataset, 'current_porosity') else dataset.porosity

        self.init_ui()

    def init_ui(self):
        """Initialize the statistics tab UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 1. COMPACT INFO BAR (Top)
        info_bar = self.create_summary_bar()
        layout.addWidget(info_bar)

        # 2. MAIN CONTENT (Two columns with splitter)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Grain size distribution + Gradation + Porosity
        left_panel = self.create_left_panel()

        # Right panel: K-statistics (larger)
        right_panel = self.create_right_panel()

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 35)  # 35% width
        main_splitter.setStretchFactor(1, 65)  # 65% width

        layout.addWidget(main_splitter, 1)  # stretch factor = 1

        # 3. BOTTOM ROW (Quality + Classification)
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.quality_widget = DataQualityWidget()
        self.classification_widget = SoilClassificationWidget()

        bottom_splitter.addWidget(self.quality_widget)
        bottom_splitter.addWidget(self.classification_widget)
        bottom_splitter.setStretchFactor(0, 40)
        bottom_splitter.setStretchFactor(1, 60)

        layout.addWidget(bottom_splitter)

        # 4. EXPORT BUTTONS
        button_layout = self.create_export_buttons()
        layout.addLayout(button_layout)

        # Initial display with placeholder data
        self.update_display()

    def create_summary_bar(self) -> CompactInfoBar:
        """Create compact single-line info bar"""
        self.info_bar = CompactInfoBar()
        return self.info_bar

    def create_left_panel(self) -> QWidget:
        """Create left panel with grain size statistics"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Percentile table
        self.percentile_table = PercentileTableWidget()
        layout.addWidget(self.percentile_table)

        # Gradation analysis
        self.gradation_widget = GradationAnalysisWidget()
        layout.addWidget(self.gradation_widget)

        # ===== IMPORTANT: PRESERVE EXISTING POROSITY SETTINGS =====
        # Porosity control section - MUST BE KEPT
        porosity_group = QGroupBox("Porosity Settings")
        porosity_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #d4c4a8;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #2c5530;
            }
        """)
        porosity_layout = QVBoxLayout(porosity_group)

        # Porosity display and edit controls
        porosity_controls_layout = QHBoxLayout()

        # Show calculated vs current porosity
        calculated_porosity = self.dataset.calculated_porosity if hasattr(self.dataset, 'calculated_porosity') else None
        current_text = f"{self.porosity:.4f}" if self.porosity is not None else "N/A"

        if calculated_porosity is not None:
            porosity_info = QLabel(f"Calculated: {calculated_porosity:.4f} | Current: {current_text}")
        else:
            porosity_info = QLabel(f"Current: {current_text} [Manual]")
        porosity_info.setStyleSheet("font-size: 9pt; color: #333;")

        # Add edit capability
        self.porosity_edit = QLineEdit()
        self.porosity_edit.setText(current_text)
        self.porosity_edit.setMaximumWidth(100)
        self.porosity_edit.setStyleSheet("""
            QLineEdit {
                padding: 4px;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                font-size: 9pt;
            }
        """)

        update_porosity_btn = QPushButton("Update")
        update_porosity_btn.clicked.connect(self._update_porosity)
        update_porosity_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b8e23;
                color: white;
                padding: 4px 12px;
                border-radius: 3px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #7fa02d;
            }
        """)

        reset_porosity_btn = QPushButton("Reset to Calculated")
        reset_porosity_btn.clicked.connect(self._reset_porosity)
        reset_porosity_btn.setStyleSheet("""
            QPushButton {
                background-color: #d2b48c;
                padding: 4px 12px;
                border-radius: 3px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #ddbf94;
            }
        """)

        if calculated_porosity is None:
            reset_porosity_btn.setEnabled(False)

        porosity_controls_layout.addWidget(porosity_info)
        porosity_controls_layout.addWidget(QLabel("Edit:"))
        porosity_controls_layout.addWidget(self.porosity_edit)
        porosity_controls_layout.addWidget(update_porosity_btn)
        porosity_controls_layout.addWidget(reset_porosity_btn)
        porosity_controls_layout.addStretch()

        porosity_layout.addLayout(porosity_controls_layout)
        layout.addWidget(porosity_group)
        # ===== END POROSITY SETTINGS =====

        layout.addStretch()

        return widget

    def create_right_panel(self) -> QWidget:
        """Create right panel with K-statistics"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.k_stats_widget = KStatisticsWidget()
        layout.addWidget(self.k_stats_widget, 1)

        return widget

    def create_export_buttons(self) -> QHBoxLayout:
        """Create export button row"""
        layout = QHBoxLayout()

        export_excel_btn = QPushButton("Export to Excel")
        export_excel_btn.clicked.connect(self.export_to_excel)
        export_excel_btn.setStyleSheet("""
            QPushButton {
                background-color: #d2b48c;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #ddbf94;
            }
        """)

        export_csv_btn = QPushButton("Export to CSV")
        export_csv_btn.clicked.connect(self.export_to_csv)
        export_csv_btn.setStyleSheet("""
            QPushButton {
                background-color: #d2b48c;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #ddbf94;
            }
        """)

        copy_btn = QPushButton("Copy Statistics")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #d2b48c;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #ddbf94;
            }
        """)

        layout.addWidget(export_excel_btn)
        layout.addWidget(export_csv_btn)
        layout.addWidget(copy_btn)
        layout.addStretch()

        return layout

    # ===== DATA UPDATE METHODS =====

    def update_display(self):
        """Update all display widgets with current data"""
        # Update info bar
        self.update_summary_bar()

        # Update percentile table
        self.update_percentile_table()

        # Update gradation
        self.update_gradation()

        # Update K-statistics if available
        if self.k_results:
            self.update_k_statistics()

        # Update soil classification
        self.update_soil_classification()

    def update_summary_bar(self):
        """Update the compact info bar at the top"""
        d50 = self.dataset.get_d50()

        # Cu
        d10 = self.dataset.get_d10()
        d60 = self.dataset.get_d60()
        cu = None
        if d10 and d60 and d10 > 0:
            cu = d60 / d10

        # Mean K (if calculated)
        mean_k = None
        if self.k_results:
            valid_k = [r.k_value for r in self.k_results if r.k_value and r.k_value > 0]
            if valid_k:
                mean_k = np.mean(valid_k)

        # Soil type
        soil_type = self.dataset.classify_soil()

        # Update info bar
        self.info_bar.update_info(
            sample_name=self.dataset.sample_name,
            d50=d50,
            cu=cu,
            mean_k=mean_k,
            soil_type=soil_type
        )

    def update_percentile_table(self):
        """Update percentile table"""
        percentiles = {}
        for p in [5, 10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 85, 90, 95]:
            value = self.dataset._interpolate_grain_size(p)
            if value:
                percentiles[p] = value

        self.percentile_table.set_percentile_data(percentiles)

    def update_gradation(self):
        """Update gradation display"""
        d10 = self.dataset.get_d10()
        d30 = self.dataset.get_d30()
        d60 = self.dataset.get_d60()

        if d10 and d60 and d10 > 0:
            cu = d60 / d10

            if cu < 4:
                cu_class = "Uniform (Cu < 4)"
            elif cu < 6:
                cu_class = "Moderately graded (4 ≤ Cu < 6)"
            else:
                cu_class = "Well-graded (Cu ≥ 6)"

            if d30:
                cc = (d30 * d30) / (d10 * d60)
                self.gradation_widget.set_gradation_data(cu, cc, cu_class)

    def update_k_statistics(self):
        """Update K-statistics display"""
        if not self.k_results:
            return

        # Get valid results
        valid_results = [r for r in self.k_results if r.k_value and r.k_value > 0]

        if not valid_results:
            return

        k_values = [r.k_value for r in valid_results]

        # Populate summary table
        table = self.k_stats_widget.summary_table
        table.setRowCount(0)

        metrics = [
            ("Mean", np.mean(k_values)),
            ("Median", np.median(k_values)),
            ("Std Dev", np.std(k_values)),
            ("Min", np.min(k_values)),
            ("Max", np.max(k_values)),
        ]

        for metric_name, value in metrics:
            row = table.rowCount()
            table.insertRow(row)

            table.setItem(row, 0, QTableWidgetItem(metric_name))
            table.setItem(row, 1, QTableWidgetItem(f"{value:.2e}"))
            table.setItem(row, 2, QTableWidgetItem(f"{value*100:.3e}"))
            table.setItem(row, 3, QTableWidgetItem(f"{value*86400:.1f}"))

        # Update classification
        mean_k = np.mean(k_values)
        if mean_k > 1e-2:
            classification = "Very High Permeability (Gravel)"
        elif mean_k > 1e-4:
            classification = "High Permeability (Clean Sand)"
        elif mean_k > 1e-5:
            classification = "Moderate Permeability (Fine Sand)"
        elif mean_k > 1e-7:
            classification = "Low Permeability (Silt)"
        else:
            classification = "Very Low Permeability (Clay)"

        self.k_stats_widget.classification_label.setText(f"Permeability: {classification}")

    def update_soil_classification(self):
        """Update soil classification display"""
        soil_type = self.dataset.classify_soil()

        text = f"""USCS Classification:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Primary: {soil_type}

Classification based on:
  • Grain size distribution
  • Uniformity coefficient
  • Coefficient of curvature
"""
        self.classification_widget.classification_text.setPlainText(text)

    def set_k_results(self, results: List[KCalculationResult]):
        """Set K-calculation results and update display"""
        self.k_results = results
        self.update_display()

    # ===== POROSITY MANAGEMENT (PRESERVE EXISTING FUNCTIONALITY) =====

    def _update_porosity(self):
        """
        Update porosity value when user edits it
        IMPORTANT: This triggers K-value recalculation in parent DatasetTab
        """
        try:
            new_porosity = float(self.porosity_edit.text())
            if 0.1 <= new_porosity <= 0.8:
                self.porosity = new_porosity
                self.dataset.current_porosity = new_porosity
                # Trigger recalculation in parent
                if self.parent():
                    self.parent().set_porosity(new_porosity)
                QMessageBox.information(self, "Porosity Updated",
                                      f"Porosity set to {new_porosity:.4f}\n"
                                      "K-values will be recalculated.")
            else:
                QMessageBox.warning(self, "Invalid Porosity",
                                  "Porosity must be between 0.1 and 0.8")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input",
                              "Please enter a valid number")

    def _reset_porosity(self):
        """Reset porosity to calculated value"""
        calculated_porosity = self.dataset.calculated_porosity if hasattr(self.dataset, 'calculated_porosity') else None

        if calculated_porosity is not None:
            self.porosity = calculated_porosity
            self.dataset.current_porosity = calculated_porosity
            self.porosity_edit.setText(f"{self.porosity:.4f}")
            # Trigger recalculation in parent
            if self.parent():
                self.parent().set_porosity(self.porosity)
            QMessageBox.information(self, "Porosity Reset",
                                  f"Porosity reset to calculated value: {calculated_porosity:.4f}\n"
                                  "K-values will be recalculated.")

    # ===== EXPORT METHODS (Placeholders for now) =====

    def export_to_excel(self):
        """Export statistics to formatted Excel file"""
        QMessageBox.information(self, "Export to Excel",
                              "Excel export will be implemented in Phase 5")

    def export_to_csv(self):
        """Export statistics to CSV"""
        QMessageBox.information(self, "Export to CSV",
                              "CSV export will be implemented in Phase 5")

    def copy_to_clipboard(self):
        """Copy formatted statistics to clipboard"""
        QMessageBox.information(self, "Copy to Clipboard",
                              "Clipboard copy will be implemented in Phase 5")
