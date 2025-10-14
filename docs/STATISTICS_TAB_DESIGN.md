# Statistics Tab - Comprehensive Design Document

## 📋 Overview

This document outlines the complete design and implementation plan for the **Statistics Tab** in the Grain Size Analysis application. The design emphasizes **modularity** to enable seamless reuse of statistical components in the reporting system.

---

## 🎯 Design Philosophy

### Core Principles
1. **Separation of Concerns**: Statistics calculation logic separate from GUI presentation
2. **Reusability**: All statistical components usable in both GUI and reports
3. **Data-First**: Statistics returned as structured data objects, not pre-formatted strings
4. **Professional Standards**: Follows geotechnical engineering conventions
5. **Extensibility**: Easy to add new statistical analyses

### Modular Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     USER INTERFACE LAYER                     │
├──────────────────┬───────────────────────┬───────────────────┤
│  Statistics Tab  │   Report Generator    │   Export Tools    │
│   (GUI Widgets)  │   (HTML Formatter)    │  (Excel/CSV/PDF)  │
└────────┬─────────┴───────────┬───────────┴─────────┬─────────┘
         │                     │                      │
         └─────────────────────┼──────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  STATISTICS ENGINE  │
                    │  (Core Calculator)  │
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
    ┌────▼────┐         ┌──────▼──────┐      ┌─────▼─────┐
    │  Grain  │         │   K-Value   │      │   Data    │
    │  Size   │         │  Statistics │      │  Quality  │
    │  Stats  │         │  Calculator │      │  Analyzer │
    └─────────┘         └─────────────┘      └───────────┘
```

---

## 📦 Module Structure

### 1. Core Statistics Module: `statistics_calculator.py`

This module contains **pure calculation logic** with no GUI dependencies.

#### Data Classes

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

@dataclass
class PercentileStats:
    """Complete percentile distribution"""
    percentiles: Dict[int, float]  # {5: 0.08, 10: 0.15, 20: 0.33, ...}
    size_range: Tuple[float, float]  # (min, max) in mm
    span_ratio: float  # max/min
    geometric_mean: float  # mm
    data_points: int
    coverage_quality: str  # "Excellent", "Good", "Fair", "Poor"

@dataclass
class GradationParams:
    """Gradation and uniformity parameters"""
    cu: Optional[float]  # Uniformity coefficient
    cc: Optional[float]  # Coefficient of curvature
    cu_classification: str  # "Uniform", "Moderately graded", "Well-graded"
    cc_classification: str  # "Well-graded", "Gap-graded", etc.
    sorting_coefficient: Optional[float]  # Statistical sorting
    gradation_type: str  # "Continuous", "Gap-graded", etc.
    gaps_detected: List[Tuple[float, float]]  # List of gap ranges

@dataclass
class KValueStats:
    """Hydraulic conductivity statistics"""
    # Basic statistics
    mean: float  # m/s
    median: float  # m/s
    std_dev: float  # m/s
    coefficient_of_variation: float  # percentage

    # Range statistics
    min_value: float  # m/s
    min_method: str
    max_value: float  # m/s
    max_method: str
    range_ratio: float  # max/min

    # Quartiles
    q1: float  # 25th percentile
    q2: float  # 50th percentile (median)
    q3: float  # 75th percentile
    iqr: float  # Interquartile range

    # Method counts
    total_methods: int
    valid_methods: int
    ok_count: int
    warning_count: int
    error_count: int

    # Classifications
    permeability_class: str  # "High Permeability", etc.
    typical_material: str  # "Fine Sand", "Clean Sand", etc.
    drainage_quality: str  # "Good", "Poor", etc.

@dataclass
class MethodAgreement:
    """Analysis of method agreement and clustering"""
    core_cluster_methods: List[str]  # Methods within ±25% of median
    core_cluster_mean: float  # m/s
    core_cluster_std: float  # m/s

    outlier_high: List[Tuple[str, float, float]]  # (method, value, % from median)
    outlier_low: List[Tuple[str, float, float]]

    failed_methods: List[Tuple[str, str]]  # (method, reason)

    recommended_range: Tuple[float, float]  # (min, max) in m/s
    confidence_level: str  # "High", "Moderate", "Low"

@dataclass
class DataQuality:
    """Data quality assessment"""
    monotonicity_score: float  # 0-1, 1 = perfect monotonic
    coverage_score: float  # 0-1, based on D5-D95 coverage
    point_density: int  # number of data points
    interpolation_quality: str  # "Excellent", "Good", "Fair", "Poor"

    warnings: List[str]  # List of quality warnings
    overall_rating: str  # "Excellent", "Good", "Fair", "Poor"
    star_rating: int  # 1-5 stars

@dataclass
class SoilClassification:
    """USCS soil classification and properties"""
    primary_classification: str  # "SP", "SW", "SM", etc.
    secondary_classification: Optional[str]  # "SP-SM", etc.
    full_name: str  # "Poorly Graded Sand"

    criteria_met: List[str]  # List of satisfied criteria

    # Typical engineering properties
    friction_angle_range: Tuple[float, float]  # degrees
    unit_weight_range: Tuple[float, float]  # kN/m³
    compressibility: str  # "Low", "Medium", "High"
    strength: str  # "Low", "Medium", "High"
    drainage: str  # "Poor", "Fair", "Good", "Excellent"

    related_soils: Dict[str, str]  # {"similar": "SW", "finer": "SM", ...}

@dataclass
class CompleteStatistics:
    """Complete statistics package for a single dataset"""
    sample_name: str

    # Core statistics
    percentiles: PercentileStats
    gradation: GradationParams
    k_values: Optional[KValueStats]  # None if no K calculations
    method_agreement: Optional[MethodAgreement]
    data_quality: DataQuality
    soil_classification: SoilClassification

    # Metadata
    temperature: float  # °C
    porosity: float
    calculated_porosity: Optional[float]

    # Timestamps
    calculated_at: str  # ISO format timestamp
```

#### Calculator Class

```python
class StatisticsCalculator:
    """
    Core statistics calculator - no GUI dependencies
    All methods return structured data objects
    """

    def __init__(self):
        pass

    # ===== GRAIN SIZE STATISTICS =====

    def calculate_percentiles(self, dataset: GrainSizeData,
                             percentiles: List[int] = None) -> PercentileStats:
        """
        Calculate complete percentile distribution

        Args:
            dataset: GrainSizeData object
            percentiles: List of percentiles to calculate [5, 10, 20, ..., 95]
                        If None, uses standard geotechnical set

        Returns:
            PercentileStats object with all calculations
        """
        pass

    def calculate_gradation(self, dataset: GrainSizeData) -> GradationParams:
        """
        Calculate gradation parameters (Cu, Cc, sorting, gaps)

        Returns:
            GradationParams object with full gradation analysis
        """
        pass

    def detect_gradation_gaps(self, dataset: GrainSizeData,
                             threshold: float = 2.0) -> List[Tuple[float, float]]:
        """
        Detect gaps in gradation where spacing > threshold * average spacing

        Returns:
            List of (start_size, end_size) tuples for detected gaps
        """
        pass

    def calculate_sorting_coefficient(self, dataset: GrainSizeData) -> float:
        """
        Calculate Folk & Ward sorting coefficient
        σ = (D84/D16)^0.5
        """
        pass

    # ===== K-VALUE STATISTICS =====

    def calculate_k_statistics(self,
                              results: List[KCalculationResult]) -> KValueStats:
        """
        Calculate complete K-value statistics

        Returns:
            KValueStats object with all statistical measures
        """
        pass

    def analyze_method_agreement(self,
                                results: List[KCalculationResult],
                                cluster_threshold: float = 0.25) -> MethodAgreement:
        """
        Analyze agreement between methods and identify clusters/outliers

        Args:
            results: List of K calculation results
            cluster_threshold: Methods within ±threshold of median form core cluster

        Returns:
            MethodAgreement object with clustering analysis
        """
        pass

    def calculate_recommended_k_range(self,
                                     results: List[KCalculationResult]) -> Tuple[float, float]:
        """
        Calculate recommended K-value range based on core cluster

        Returns:
            (min_k, max_k) tuple representing recommended range
        """
        pass

    # ===== DATA QUALITY =====

    def assess_data_quality(self, dataset: GrainSizeData) -> DataQuality:
        """
        Comprehensive data quality assessment

        Returns:
            DataQuality object with quality metrics and warnings
        """
        pass

    def calculate_monotonicity_score(self, dataset: GrainSizeData) -> float:
        """
        Calculate monotonicity score (0-1) for percent passing curve
        1.0 = perfectly monotonic, 0.0 = completely non-monotonic
        """
        pass

    def assess_interpolation_quality(self, dataset: GrainSizeData) -> str:
        """
        Assess quality of interpolation based on point spacing

        Returns:
            "Excellent", "Good", "Fair", or "Poor"
        """
        pass

    # ===== SOIL CLASSIFICATION =====

    def classify_soil_uscs(self, dataset: GrainSizeData,
                          gradation: GradationParams) -> SoilClassification:
        """
        Complete USCS classification with engineering properties

        Returns:
            SoilClassification object with full classification and properties
        """
        pass

    def get_typical_properties(self, uscs_symbol: str) -> Dict[str, any]:
        """
        Get typical engineering properties for USCS soil type

        Returns:
            Dictionary with friction angle, unit weight, etc.
        """
        pass

    # ===== COMPLETE STATISTICS =====

    def calculate_complete_statistics(self,
                                     dataset: GrainSizeData,
                                     k_results: Optional[List[KCalculationResult]] = None,
                                     temperature: float = 20.0,
                                     porosity: float = 0.40) -> CompleteStatistics:
        """
        Calculate all statistics for a dataset in one call

        This is the main entry point for getting complete statistics

        Returns:
            CompleteStatistics object containing all analyses
        """
        pass
```

---

## 🎨 GUI Components: `statistics_widgets.py`

Separate module for GUI presentation components that consume the statistics objects.

```python
from PyQt6.QtWidgets import (
    QWidget, QLabel, QFrame, QTableWidget, QGroupBox,
    QVBoxLayout, QHBoxLayout, QTextBrowser
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

class SummaryCardWidget(QWidget):
    """Single stat card for top summary row"""

    def __init__(self, label: str, value: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.init_ui(label, value, subtitle)

    def init_ui(self, label, value, subtitle):
        """Create card with label, large value, and optional subtitle"""
        pass

    def update_value(self, value: str, subtitle: str = ""):
        """Update card value"""
        pass

class PercentileTableWidget(QTableWidget):
    """Enhanced table showing percentiles with visual bars"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def set_percentile_data(self, percentile_stats: PercentileStats):
        """Populate table from PercentileStats object"""
        pass

    def add_visual_bars(self):
        """Add horizontal bars showing relative sizes"""
        pass

class GradationAnalysisWidget(QGroupBox):
    """Widget showing gradation parameters and classification"""

    def __init__(self, parent=None):
        super().__init__("Gradation Analysis", parent)
        self.init_ui()

    def set_gradation_data(self, gradation: GradationParams):
        """Display gradation parameters"""
        pass

    def show_classification_chart(self, gradation: GradationParams):
        """Show Cu/Cc position on USCS diagram"""
        pass

class KStatisticsWidget(QGroupBox):
    """Widget showing K-value statistics with multiple sub-panels"""

    def __init__(self, parent=None):
        super().__init__("Hydraulic Conductivity Statistics", parent)
        self.init_ui()

    def set_k_statistics(self, k_stats: KValueStats,
                        method_agreement: MethodAgreement):
        """Display K-value statistics"""
        pass

    def create_summary_panel(self) -> QWidget:
        """Statistical summary table"""
        pass

    def create_distribution_panel(self) -> QWidget:
        """Box plot, histogram, scatter plot"""
        pass

    def create_agreement_panel(self) -> QWidget:
        """Method agreement and clustering analysis"""
        pass

    def create_classification_panel(self) -> QWidget:
        """Permeability classification with visual scale"""
        pass

class DataQualityWidget(QGroupBox):
    """Widget showing data quality indicators"""

    def __init__(self, parent=None):
        super().__init__("Data Quality Assessment", parent)
        self.init_ui()

    def set_quality_data(self, quality: DataQuality):
        """Display quality assessment"""
        pass

    def show_star_rating(self, stars: int):
        """Display star rating visually"""
        pass

class SoilClassificationWidget(QGroupBox):
    """Widget showing USCS classification and properties"""

    def __init__(self, parent=None):
        super().__init__("USCS Soil Classification", parent)
        self.init_ui()

    def set_classification_data(self, classification: SoilClassification):
        """Display soil classification and properties"""
        pass

class PermeabilityScaleWidget(QWidget):
    """Visual scale showing K-value position on permeability spectrum"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def set_k_value(self, k_mean: float, k_range: Tuple[float, float] = None):
        """Show K-value position on logarithmic scale"""
        pass

    def paintEvent(self, event):
        """Custom paint for visual scale"""
        pass
```

---

## 📊 Statistics Tab Layout

### Complete Layout Structure

```python
class StatisticsTab(QWidget):
    """
    Enhanced statistics tab using modular components
    """

    def __init__(self, dataset: GrainSizeData, parent=None):
        super().__init__(parent)

        self.dataset = dataset
        self.stats_calculator = StatisticsCalculator()
        self.complete_stats: Optional[CompleteStatistics] = None

        self.init_ui()

    def init_ui(self):
        """Build the complete statistics tab layout"""
        layout = QVBoxLayout(self)

        # 1. SUMMARY CARDS ROW (Top)
        summary_row = self.create_summary_cards()
        layout.addWidget(summary_row)

        # 2. MAIN CONTENT (Two columns)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left column: Grain size + Gradation
        left_panel = self.create_left_panel()

        # Right column: K-statistics (larger)
        right_panel = self.create_right_panel()

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 30)  # 30% width
        main_splitter.setStretchFactor(1, 70)  # 70% width

        layout.addWidget(main_splitter, 1)  # stretch factor

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

        # Initial calculation
        self.calculate_statistics()

    def create_summary_cards(self) -> QWidget:
        """Create top row with 4 summary cards"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QHBoxLayout(widget)

        self.card_d50 = SummaryCardWidget("D50", "N/A", "Median")
        self.card_cu = SummaryCardWidget("Cu", "N/A", "Uniformity")
        self.card_mean_k = SummaryCardWidget("Mean K", "N/A", "±std")
        self.card_soil_type = SummaryCardWidget("Soil Type", "N/A", "USCS")

        layout.addWidget(self.card_d50)
        layout.addWidget(self.card_cu)
        layout.addWidget(self.card_mean_k)
        layout.addWidget(self.card_soil_type)

        return widget

    def create_left_panel(self) -> QWidget:
        """Create left panel with grain size stats"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Percentile table
        percentile_group = QGroupBox("Grain Size Percentiles")
        percentile_layout = QVBoxLayout(percentile_group)

        self.percentile_table = PercentileTableWidget()
        percentile_layout.addWidget(self.percentile_table)

        layout.addWidget(percentile_group)

        # Gradation analysis
        self.gradation_widget = GradationAnalysisWidget()
        layout.addWidget(self.gradation_widget)

        # ===== IMPORTANT: PRESERVE EXISTING POROSITY SETTINGS =====
        # Porosity control section - MUST BE KEPT
        porosity_group = QGroupBox("Porosity Settings")
        porosity_layout = QVBoxLayout(porosity_group)

        # Porosity display and edit controls
        porosity_controls_layout = QHBoxLayout()

        # Show calculated vs current porosity
        calculated_porosity = self.dataset.calculated_porosity
        current_text = f"{self.porosity:.4f}" if self.porosity is not None else "N/A"
        if calculated_porosity is not None:
            porosity_info = QLabel(f"Calculated: {calculated_porosity:.4f} | Current: {current_text}")
        else:
            porosity_info = QLabel(f"Current: {current_text} [Manual]")

        # Add edit capability
        self.porosity_edit = QLineEdit()
        self.porosity_edit.setText(current_text)
        self.porosity_edit.setMaximumWidth(100)

        update_porosity_btn = QPushButton("Update")
        update_porosity_btn.clicked.connect(self._update_porosity)

        reset_porosity_btn = QPushButton("Reset to Calculated")
        reset_porosity_btn.clicked.connect(self._reset_porosity)
        if self.dataset.calculated_porosity is None:
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

        self.k_stats_widget = KStatisticsWidget()
        layout.addWidget(self.k_stats_widget, 1)

        return widget

    def create_export_buttons(self) -> QHBoxLayout:
        """Create export button row"""
        layout = QHBoxLayout()

        export_excel_btn = QPushButton("Export to Excel")
        export_excel_btn.clicked.connect(self.export_to_excel)

        export_csv_btn = QPushButton("Export to CSV")
        export_csv_btn.clicked.connect(self.export_to_csv)

        copy_btn = QPushButton("Copy Statistics")
        copy_btn.clicked.connect(self.copy_to_clipboard)

        layout.addWidget(export_excel_btn)
        layout.addWidget(export_csv_btn)
        layout.addWidget(copy_btn)
        layout.addStretch()

        return layout

    # ===== CALCULATION METHODS =====

    def calculate_statistics(self):
        """Calculate all statistics using the calculator"""
        # Get K results if available (from parent DatasetTab)
        k_results = self.parent().get_results() if self.parent() else None

        # Calculate complete statistics
        self.complete_stats = self.stats_calculator.calculate_complete_statistics(
            dataset=self.dataset,
            k_results=k_results,
            temperature=self.dataset.temperature,
            porosity=self.dataset.porosity
        )

        # Update all widgets
        self.update_all_widgets()

    def update_all_widgets(self):
        """Update all GUI widgets with calculated statistics"""
        if not self.complete_stats:
            return

        stats = self.complete_stats

        # Update summary cards
        d50 = stats.percentiles.percentiles.get(50, None)
        self.card_d50.update_value(
            f"{d50:.2f} mm" if d50 else "N/A",
            "Median"
        )

        cu_val = stats.gradation.cu
        self.card_cu.update_value(
            f"{cu_val:.2f}" if cu_val else "N/A",
            stats.gradation.cu_classification
        )

        if stats.k_values:
            mean_k = stats.k_values.mean
            std_k = stats.k_values.std_dev
            self.card_mean_k.update_value(
                f"{mean_k:.2e} m/s",
                f"±{std_k:.2e}"
            )
        else:
            self.card_mean_k.update_value("N/A", "Not calculated")

        self.card_soil_type.update_value(
            stats.soil_classification.primary_classification,
            stats.soil_classification.full_name
        )

        # Update widgets
        self.percentile_table.set_percentile_data(stats.percentiles)
        self.gradation_widget.set_gradation_data(stats.gradation)

        if stats.k_values and stats.method_agreement:
            self.k_stats_widget.set_k_statistics(
                stats.k_values,
                stats.method_agreement
            )

        self.quality_widget.set_quality_data(stats.data_quality)
        self.classification_widget.set_classification_data(stats.soil_classification)

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
                self.calculate_statistics()  # Recalculate stats with new porosity
            else:
                QMessageBox.warning(self, "Invalid Porosity",
                                  "Porosity must be between 0.1 and 0.8")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input",
                              "Please enter a valid number")

    def _reset_porosity(self):
        """Reset porosity to calculated value"""
        if self.dataset.calculated_porosity is not None:
            self.porosity = self.dataset.calculated_porosity
            self.dataset.current_porosity = self.dataset.calculated_porosity
            self.porosity_edit.setText(f"{self.porosity:.4f}")
            # Trigger recalculation in parent
            if self.parent():
                self.parent().set_porosity(self.porosity)
            self.calculate_statistics()  # Recalculate stats

    # ===== EXPORT METHODS =====

    def export_to_excel(self):
        """Export statistics to formatted Excel file"""
        pass

    def export_to_csv(self):
        """Export statistics to CSV"""
        pass

    def copy_to_clipboard(self):
        """Copy formatted statistics to clipboard"""
        pass

    def get_statistics(self) -> Optional[CompleteStatistics]:
        """Get complete statistics object (for reports)"""
        return self.complete_stats
```

---

## 🔗 Report Integration

### HTML Formatter: `statistics_formatter.py`

This module converts statistics objects to HTML for reports.

```python
class StatisticsHTMLFormatter:
    """
    Converts statistics objects to formatted HTML
    Used by ReportGenerator
    """

    def __init__(self, style: str = "professional"):
        self.style = style

    def format_percentile_table(self, percentiles: PercentileStats) -> str:
        """Generate HTML table for percentiles"""
        pass

    def format_gradation_analysis(self, gradation: GradationParams) -> str:
        """Generate HTML for gradation parameters"""
        pass

    def format_k_statistics(self, k_stats: KValueStats,
                           method_agreement: MethodAgreement) -> str:
        """Generate HTML for K-value statistics"""
        pass

    def format_summary_cards(self, stats: CompleteStatistics) -> str:
        """Generate HTML summary cards"""
        pass

    def format_complete_statistics(self, stats: CompleteStatistics) -> str:
        """Generate complete HTML report section"""
        html = f"""
        <div class="statistics-section">
            {self.format_summary_cards(stats)}
            {self.format_percentile_table(stats.percentiles)}
            {self.format_gradation_analysis(stats.gradation)}

            {self.format_k_statistics(stats.k_values, stats.method_agreement)
             if stats.k_values else ""}

            {self.format_data_quality(stats.data_quality)}
            {self.format_soil_classification(stats.soil_classification)}
        </div>
        """
        return html
```

### Integration with ReportGenerator

```python
# In report_generator.py

from statistics_calculator import StatisticsCalculator, CompleteStatistics
from statistics_formatter import StatisticsHTMLFormatter

class ReportGenerator:

    def __init__(self):
        self.stats_calculator = StatisticsCalculator()
        self.stats_formatter = StatisticsHTMLFormatter()
        # ... existing code ...

    def generate_complete_analysis_report(self,
                                         dataset: GrainSizeData,
                                         k_results: List[KCalculationResult],
                                         temperature: float,
                                         porosity: float) -> str:
        """
        Enhanced report with complete statistics
        """

        # Calculate statistics using the calculator
        stats = self.stats_calculator.calculate_complete_statistics(
            dataset=dataset,
            k_results=k_results,
            temperature=temperature,
            porosity=porosity
        )

        # Format to HTML
        stats_html = self.stats_formatter.format_complete_statistics(stats)

        # Combine with existing report sections
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Complete Analysis Report - {dataset.sample_name}</title>
            {self.report_style}
        </head>
        <body>
            <h1>Complete Analysis Report</h1>

            {self._format_metadata(dataset, temperature, porosity)}

            <h2>Statistical Analysis</h2>
            {stats_html}

            {self._format_plots()}

            <div class="footer">
                <p>Generated by Grain Size Analysis Tool</p>
            </div>
        </body>
        </html>
        """

        return html
```

---

## 📈 Visualization Components

### Chart Generator: `statistics_charts.py`

```python
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Tuple
import io
import base64

class StatisticsChartGenerator:
    """
    Generate matplotlib charts for statistics
    Charts can be embedded in GUI or saved as images for reports
    """

    def __init__(self, style: str = "seaborn-v0_8-darkgrid"):
        plt.style.use(style)
        self.figure_dpi = 100
        self.figure_size = (8, 6)

    def create_k_value_boxplot(self, k_stats: KValueStats,
                               results: List[KCalculationResult]) -> plt.Figure:
        """
        Create box plot of K-values

        Returns:
            matplotlib Figure object
        """
        pass

    def create_k_value_histogram(self, results: List[KCalculationResult]) -> plt.Figure:
        """Create histogram with normal curve overlay"""
        pass

    def create_method_scatter_plot(self, results: List[KCalculationResult],
                                   method_agreement: MethodAgreement) -> plt.Figure:
        """
        Create scatter plot showing methods on log scale
        Color-coded by core cluster / outliers
        """
        pass

    def create_permeability_scale(self, k_mean: float,
                                 k_range: Tuple[float, float]) -> plt.Figure:
        """
        Create visual permeability scale showing K position
        """
        pass

    def create_cu_cc_diagram(self, cu: float, cc: float) -> plt.Figure:
        """
        Create Cu vs Cc classification diagram
        Shows USCS boundaries and sample position
        """
        pass

    def figure_to_base64(self, fig: plt.Figure) -> str:
        """
        Convert matplotlib figure to base64 string for HTML embedding

        Returns:
            Base64-encoded PNG image string
        """
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=self.figure_dpi, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode()
        plt.close(fig)
        return f"data:image/png;base64,{image_base64}"

    def save_figure(self, fig: plt.Figure, filepath: str):
        """Save figure to file"""
        fig.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
```

---

## 🗂️ Excel Export: `statistics_excel_exporter.py`

```python
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, LineChart, ScatterChart, Reference
from statistics_calculator import CompleteStatistics

class StatisticsExcelExporter:
    """
    Export statistics to formatted Excel workbook
    """

    def __init__(self):
        self.header_font = Font(bold=True, size=12, color="FFFFFF")
        self.header_fill = PatternFill(start_color="4A5F7F", end_color="4A5F7F", fill_type="solid")
        self.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

    def export_statistics(self, stats: CompleteStatistics, filepath: str):
        """
        Export complete statistics to Excel file

        Creates multiple sheets:
        - Summary
        - Percentiles
        - K-Value Results
        - Method Comparison
        - Data Quality
        """

        wb = Workbook()

        # Create sheets
        self._create_summary_sheet(wb, stats)
        self._create_percentiles_sheet(wb, stats)

        if stats.k_values:
            self._create_k_values_sheet(wb, stats)
            self._create_method_comparison_sheet(wb, stats)

        self._create_quality_sheet(wb, stats)

        # Save
        wb.save(filepath)

    def _create_summary_sheet(self, wb: Workbook, stats: CompleteStatistics):
        """Create summary overview sheet"""
        pass

    def _create_percentiles_sheet(self, wb: Workbook, stats: CompleteStatistics):
        """Create percentile table with chart"""
        pass

    def _create_k_values_sheet(self, wb: Workbook, stats: CompleteStatistics):
        """Create K-value statistics sheet with charts"""
        pass
```

---

## 📝 Implementation Phases

### Phase 1: Core Foundation (Week 1)
**Goal**: Get basic statistics calculating and displaying

- [ ] Create `statistics_calculator.py` with data classes
- [ ] Implement `calculate_percentiles()`
- [ ] Implement `calculate_gradation()`
- [ ] Implement `calculate_k_statistics()`
- [ ] Implement `calculate_complete_statistics()`
- [ ] Create basic `StatisticsTab` GUI layout
- [ ] **PRESERVE existing Porosity Settings section** (copy from old stats tab)
- [ ] **Wire up porosity update/reset callbacks** to trigger K-value recalculation
- [ ] Test with existing datasets

**Deliverable**: Statistics tab shows basic numbers in simple layout, porosity controls work

### Phase 2: Enhanced GUI (Week 2)
**Goal**: Professional, polished GUI components

- [ ] Create `statistics_widgets.py` with custom widgets
- [ ] Implement `SummaryCardWidget`
- [ ] Implement `PercentileTableWidget` with visual bars
- [ ] Implement `GradationAnalysisWidget`
- [ ] Implement `KStatisticsWidget` with sub-panels
- [ ] Implement `DataQualityWidget`
- [ ] Implement `SoilClassificationWidget`
- [ ] Polish styling and layout

**Deliverable**: Beautiful, professional statistics tab

### Phase 3: Advanced Analysis (Week 3)
**Goal**: Sophisticated statistical analysis

- [ ] Implement `analyze_method_agreement()`
- [ ] Implement `detect_gradation_gaps()`
- [ ] Implement `assess_data_quality()`
- [ ] Implement `classify_soil_uscs()` with full properties
- [ ] Create `statistics_charts.py`
- [ ] Implement box plots, histograms, scatter plots
- [ ] Add permeability scale visualization
- [ ] Add Cu/Cc classification diagram

**Deliverable**: Complete analysis with visualizations

### Phase 4: Report Integration (Week 4)
**Goal**: Seamless statistics in reports

- [ ] Create `statistics_formatter.py`
- [ ] Implement HTML formatting for all statistics
- [ ] Integrate with `ReportGenerator`
- [ ] Add chart embedding in reports
- [ ] Test report generation with statistics
- [ ] Polish HTML styling

**Deliverable**: Reports include all statistics

### Phase 5: Export & Polish (Week 5)
**Goal**: Multiple export formats, final polish

- [ ] Create `statistics_excel_exporter.py`
- [ ] Implement Excel export with formatting
- [ ] Implement CSV export
- [ ] Implement clipboard copy
- [ ] Add progress indicators for long calculations
- [ ] Add tooltips and help text
- [ ] User testing and refinement
- [ ] Documentation

**Deliverable**: Production-ready statistics system

---

## 🎯 Usage Examples

### Example 1: GUI Usage

```python
# In dataset_tab.py - replacing old statistics tab

def create_statistics_tab(self):
    """Create the enhanced statistics tab"""
    from statistics_tab import StatisticsTab

    stats_tab = StatisticsTab(self.dataset, parent=self)
    return stats_tab

# When K-values are calculated, statistics update automatically
def calculate_k_values(self, selected_methods):
    # ... existing calculation code ...

    # Statistics tab listens to results and updates
    self.statistics_tab.calculate_statistics()
```

### Example 2: Report Usage

```python
# In report_generator.py

def generate_enhanced_report(self, dataset, k_results, temp, porosity):
    # Calculate statistics
    stats = self.stats_calculator.calculate_complete_statistics(
        dataset=dataset,
        k_results=k_results,
        temperature=temp,
        porosity=porosity
    )

    # Format to HTML
    stats_html = self.stats_formatter.format_complete_statistics(stats)

    # Include in report
    return self._build_report_html(stats_html)
```

### Example 3: Excel Export

```python
# In statistics_tab.py

def export_to_excel(self):
    filepath, _ = QFileDialog.getSaveFileName(
        self,
        "Export Statistics to Excel",
        f"statistics_{self.dataset.sample_name}.xlsx",
        "Excel Files (*.xlsx)"
    )

    if filepath:
        exporter = StatisticsExcelExporter()
        exporter.export_statistics(self.complete_stats, filepath)
        QMessageBox.information(self, "Success", "Statistics exported!")
```

### Example 4: Programmatic Access

```python
# External scripts can use the calculator directly

from statistics_calculator import StatisticsCalculator
from data_loader import DataLoader

# Load data
loader = DataLoader()
dataset = loader.load_file("sample.csv")

# Calculate statistics
calculator = StatisticsCalculator()
stats = calculator.calculate_complete_statistics(dataset)

# Access any statistic
print(f"D50: {stats.percentiles.percentiles[50]} mm")
print(f"Cu: {stats.gradation.cu}")
print(f"Soil: {stats.soil_classification.full_name}")

# Export results
import json
with open("stats.json", "w") as f:
    json.dump(stats.__dict__, f, indent=2)
```

---

## 🔍 Testing Strategy

### Unit Tests

```python
# tests/test_statistics_calculator.py

import pytest
from statistics_calculator import StatisticsCalculator
from data_loader import GrainSizeData

class TestStatisticsCalculator:

    def setup_method(self):
        self.calculator = StatisticsCalculator()

        # Create test dataset
        self.test_dataset = GrainSizeData(
            sample_name="Test Sample",
            temperature=20.0,
            porosity=0.40,
            particle_sizes=[2.0, 0.82, 0.55, 0.42, 0.28, 0.15, 0.045],
            percent_passing=[100, 80, 60, 40, 20, 10, 0]
        )

    def test_percentiles_calculation(self):
        """Test percentile calculation accuracy"""
        percentiles = self.calculator.calculate_percentiles(self.test_dataset)

        assert percentiles.percentiles[10] == pytest.approx(0.15, rel=0.01)
        assert percentiles.percentiles[50] == pytest.approx(0.55, rel=0.01)
        assert percentiles.geometric_mean > 0

    def test_gradation_parameters(self):
        """Test Cu and Cc calculations"""
        gradation = self.calculator.calculate_gradation(self.test_dataset)

        assert gradation.cu > 0
        assert gradation.cc > 0
        assert gradation.cu_classification in ["Uniform", "Moderately graded", "Well-graded"]

    def test_complete_statistics(self):
        """Test complete statistics calculation"""
        stats = self.calculator.calculate_complete_statistics(self.test_dataset)

        assert stats.sample_name == "Test Sample"
        assert stats.percentiles is not None
        assert stats.gradation is not None
        assert stats.data_quality is not None
```

### Integration Tests

```python
# tests/test_statistics_integration.py

def test_gui_statistics_tab():
    """Test statistics tab displays correctly"""
    pass

def test_report_statistics_formatting():
    """Test statistics appear correctly in reports"""
    pass

def test_excel_export():
    """Test Excel export produces valid file"""
    pass
```

---

## 📚 Documentation

### User Documentation

Create `docs/STATISTICS_USER_GUIDE.md` with:
- Explanation of each statistic
- Interpretation guidelines
- Export instructions
- Troubleshooting

### Developer Documentation

Create `docs/STATISTICS_API.md` with:
- API reference for all classes
- Usage examples
- Extension guide

---

## 🚀 Future Enhancements

### Potential Additions (Post-MVP)

1. **Comparative Statistics** (Multi-sample)
   - Side-by-side comparison tables
   - Correlation matrices
   - Statistical tests (t-test, ANOVA)

2. **Custom Percentiles**
   - User can specify which percentiles to calculate
   - Save custom percentile sets

3. **Statistical Uncertainty**
   - Confidence intervals for K-values
   - Bootstrap analysis
   - Sensitivity analysis

4. **Historical Tracking**
   - Track statistics over multiple analyses
   - Trend visualization
   - Change detection

5. **AI Insights**
   - Automated interpretation text
   - Anomaly detection
   - Recommendation engine

---

## ✅ Success Criteria

The Statistics Tab is complete when:

- ✅ All statistics calculate correctly and match validation data
- ✅ GUI is professional, responsive, and intuitive
- ✅ All components are modular and reusable in reports
- ✅ **Porosity settings section is preserved and functional**
- ✅ **Porosity changes trigger K-value recalculation**
- ✅ Export to Excel/CSV works flawlessly
- ✅ Report integration is seamless
- ✅ Code is well-tested (>80% coverage)
- ✅ Documentation is complete
- ✅ User feedback is positive

---

## 🤝 Contributing

When implementing new statistics:

1. Add calculation to `StatisticsCalculator` (returns data object)
2. Add data class to hold the results (if needed)
3. Create GUI widget in `statistics_widgets.py`
4. Add HTML formatter in `statistics_formatter.py`
5. Add to Excel exporter
6. Write tests
7. Update documentation

**Always maintain the modular architecture!**

---

## 📞 Questions & Clarifications

If unclear during implementation, refer back to this document or ask:
- What is the calculation formula?
- What is the geotechnical interpretation?
- How should this appear in reports?
- What is the expected output format?

---

**Document Version**: 1.0
**Last Updated**: 2025-10-13
**Status**: Ready for Implementation
**Next Step**: Begin Phase 1 - Core Foundation
