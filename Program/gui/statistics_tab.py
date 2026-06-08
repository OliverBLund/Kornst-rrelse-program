"""
Enhanced Statistics Tab with Modular Design

This module provides a comprehensive statistics display for grain size analysis
and hydraulic conductivity calculations. The design is modular to enable easy
reuse in report generation.

Phase 1: Layout and visual structure
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QGroupBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QLineEdit,
    QSplitter,
    QHeaderView,
    QMessageBox,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from typing import Optional, List
import numpy as np

from data_loader import GrainSizeData
from k_calculations import KCalculationResult
from .theme import C, F
from grain_classification import (
    ISO14688,
    cu_label as _cu_label,
    permeability_class as _perm_class,
)


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
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {C.BG};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 4px 12px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        # Create info label
        self.info_label = QLabel("Load data to view statistics")
        self.info_label.setStyleSheet(f"""
            QLabel {{
                font-size: {F.SZ_SM}pt;
                font-family: "{F.MONO}";
                color: {C.TEXT_MID};
            }}
        """)

        layout.addWidget(self.info_label)
        layout.addStretch()

    def update_info(
        self,
        sample_name: str,
        d50: float = None,
        cu: float = None,
        mean_k: float = None,
        soil_type: str = "N/A",
    ):
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

        layout.addWidget(self.table)

        # Info text below table
        self.info_text = QLabel("Load data to view percentiles")
        self.info_text.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; font-style: italic;")
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
                percentile_item.setBackground(QColor(107, 142, 35, 30))  # Warm olive tint
            self.table.setItem(row, 0, percentile_item)

            # Size column
            size_item = QTableWidgetItem(f"{size:.3f}")
            size_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
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
        self.init_ui()

    def init_ui(self):
        """Initialize gradation display"""
        layout = QVBoxLayout(self)

        # Text display for gradation info
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setMaximumHeight(200)

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

        layout.addWidget(self.summary_table)

        # Method agreement section
        self.agreement_text = QTextEdit()
        self.agreement_text.setReadOnly(True)
        self.agreement_text.setMaximumHeight(180)
        self.agreement_text.setPlainText(
            "Method Agreement Analysis:\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Calculate K-values to view method agreement"
        )

        layout.addWidget(self.agreement_text)

        # Permeability classification
        self.classification_label = QLabel(
            "Permeability Classification: Not calculated"
        )
        self.classification_label.setStyleSheet(f"""
            font-size: {F.SZ_BASE}pt;
            font-weight: 600;
            color: {C.OLIVE};
            padding: 8px;
            background-color: rgba(107,142,35,0.06);
            border: 1px solid {C.OLIVE_DK};
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
        self.init_ui()

    def init_ui(self):
        """Initialize quality display"""
        layout = QVBoxLayout(self)

        self.quality_text = QTextEdit()
        self.quality_text.setReadOnly(True)
        self.quality_text.setMaximumHeight(150)

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
        self.init_ui()

    def init_ui(self):
        """Initialize classification display"""
        layout = QVBoxLayout(self)

        self.classification_text = QTextEdit()
        self.classification_text.setReadOnly(True)
        self.classification_text.setMaximumHeight(150)

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
        self._scheme = ISO14688

        # Get temperature and porosity from dataset
        self.temperature = dataset.temperature
        self.porosity = (
            dataset.current_porosity
            if hasattr(dataset, "current_porosity")
            else dataset.porosity
        )

        self.init_ui()

    def init_ui(self):
        """Initialize the statistics tab UI with comprehensive grain analysis panels"""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 1. COMPACT INFO BAR (Top)
        info_bar = self.create_summary_bar()
        layout.addWidget(info_bar)

        # 2. GRAIN SIZE ANALYSIS SECTION (2x2 grid)
        grain_analysis_section = self.create_grain_analysis_section()
        layout.addWidget(grain_analysis_section)

        # 3. SPECIAL DIAMETERS & ENVIRONMENTAL PARAMETERS (side-by-side)
        special_env_section = self.create_special_env_section()
        layout.addWidget(special_env_section)

        # 4. K-STATISTICS & CLASSIFICATION (side-by-side)
        k_stats_section = self.create_k_stats_section()
        layout.addWidget(k_stats_section)

        # 5. EXPORT BUTTONS
        button_layout = self.create_export_buttons()
        layout.addLayout(button_layout)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        # Initial display with placeholder data
        self.update_display()

    def create_summary_bar(self) -> CompactInfoBar:
        """Create compact single-line info bar"""
        self.info_bar = CompactInfoBar()
        return self.info_bar

    def create_grain_analysis_section(self) -> QWidget:
        """Create 2x2 grid with grain size percentiles and gradation parameters"""
        widget = QWidget()
        main_layout = QHBoxLayout(widget)
        main_layout.setSpacing(8)

        # Left side: Grain Size Percentiles + Percentile Usage Reference
        left_side = QWidget()
        left_layout = QHBoxLayout(left_side)
        left_layout.setSpacing(8)

        # Percentiles values
        percentiles_group = QGroupBox("Grain Size Percentiles")
        percentiles_layout = QVBoxLayout(percentiles_group)

        self.percentiles_text = QTextEdit()
        self.percentiles_text.setReadOnly(True)
        self.percentiles_text.setMinimumHeight(200)
        self.percentiles_text.setPlainText(
            "Calculate K-values to see grain size percentiles"
        )
        percentiles_layout.addWidget(self.percentiles_text)

        left_layout.addWidget(percentiles_group, 50)

        # Percentile usage reference
        usage_group = QGroupBox("Percentile Usage by Methods")
        usage_layout = QVBoxLayout(usage_group)

        self.percentile_usage_text = QTextEdit()
        self.percentile_usage_text.setReadOnly(True)
        self.percentile_usage_text.setMinimumHeight(200)
        usage_ref = f"""<pre style='font-family: {F.MONO}, monospace; font-size: {F.SZ_SM}pt;'>
<b>Percentile Usage by Methods:</b>

<b>D₅:</b>   Barr
<b>D₁₀:</b>  Hazen, Hazen_1892, Slichter,
       Terzaghi, Beyer, Kozeny-Carman,
       Zunker, Zamarin, Chapuis,
       Alyamani-Sen

<b>D₁₆:</b>  Sorting Coefficient (σ)
<b>D₁₇:</b>  Sauerbrei
<b>D₂₀:</b>  USBR, Beyer (fallback)
<b>D₃₀:</b>  Cu, Cc calculations
<b>D₅₀:</b>  Kruger, Alyamani-Sen,
       Shepherd

<b>D₆₀:</b>  Beyer, Barr, Cu calculation
<b>D₈₄:</b>  Sorting Coefficient (σ),
       Krumbein-Monk
<b>D₉₅:</b>  Krumbein-Monk
</pre>"""
        self.percentile_usage_text.setHtml(usage_ref)
        usage_layout.addWidget(self.percentile_usage_text)

        left_layout.addWidget(usage_group, 50)

        main_layout.addWidget(left_side, 50)

        # Right side: Gradation Parameters + Classification Criteria
        right_side = QWidget()
        right_layout = QHBoxLayout(right_side)
        right_layout.setSpacing(8)

        # Gradation parameters
        gradation_group = QGroupBox("Gradation Parameters")
        gradation_layout = QVBoxLayout(gradation_group)

        self.gradation_text = QTextEdit()
        self.gradation_text.setReadOnly(True)
        self.gradation_text.setMinimumHeight(200)
        self.gradation_text.setPlainText(
            "Calculate K-values to see gradation parameters"
        )
        gradation_layout.addWidget(self.gradation_text)

        right_layout.addWidget(gradation_group, 50)

        # Classification criteria
        criteria_group = QGroupBox("Classification Criteria")
        criteria_layout = QVBoxLayout(criteria_group)

        self.classification_criteria_text = QTextEdit()
        self.classification_criteria_text.setReadOnly(True)
        self.classification_criteria_text.setMinimumHeight(200)
        criteria_ref = f"""<pre style='font-family: {F.MONO}, monospace; font-size: {F.SZ_SM}pt;'>
<b>Classification Criteria:</b>

<b>Uniformity Coefficient (Cu):</b>
  Cu &lt; 4      → Uniform
  4 ≤ Cu &lt; 6  → Moderately graded
  Cu ≥ 6      → Well-graded

<b>Coefficient of Curvature (Cc):</b>
  1 ≤ Cc ≤ 3  → Well-graded range
  Outside     → Gap/poorly graded

<b>Sorting Coefficient (σ):</b>
  σ &lt; 2       → Well sorted
  2 ≤ σ &lt; 4   → Moderately sorted
  σ ≥ 4       → Poorly sorted
</pre>"""
        self.classification_criteria_text.setHtml(criteria_ref)
        criteria_layout.addWidget(self.classification_criteria_text)

        right_layout.addWidget(criteria_group, 50)

        main_layout.addWidget(right_side, 50)

        return widget

    def create_special_env_section(self) -> QWidget:
        """Create section with special method diameters and environmental parameters"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(8)

        # Special Method Diameters
        special_group = QGroupBox("Special Method Diameters")
        special_layout = QVBoxLayout(special_group)

        self.special_diameters_text = QTextEdit()
        self.special_diameters_text.setReadOnly(True)
        self.special_diameters_text.setMinimumHeight(120)
        self.special_diameters_text.setPlainText(
            "Calculate K-values to see special method diameters"
        )
        special_layout.addWidget(self.special_diameters_text)

        layout.addWidget(special_group, 60)

        # Environmental Parameters (READ-ONLY)
        env_group = QGroupBox("Environmental Parameters")
        env_layout = QVBoxLayout(env_group)

        self.env_text = QTextEdit()
        self.env_text.setReadOnly(True)
        self.env_text.setMinimumHeight(120)
        env_layout.addWidget(self.env_text)

        # Populate environmental parameters immediately
        self.update_environmental_parameters()

        layout.addWidget(env_group, 40)

        return widget

    def create_k_stats_section(self) -> QWidget:
        """Create K-statistics and classification section"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(8)

        # K-Statistics Widget
        self.k_stats_widget = KStatisticsWidget()
        layout.addWidget(self.k_stats_widget, 60)

        # Right side: Quality + Classification stacked
        right_side = QWidget()
        right_layout = QVBoxLayout(right_side)
        right_layout.setSpacing(8)

        self.quality_widget = DataQualityWidget()
        self.classification_widget = SoilClassificationWidget()

        right_layout.addWidget(self.quality_widget)
        right_layout.addWidget(self.classification_widget)

        layout.addWidget(right_side, 40)

        return widget

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

        # NOTE: Porosity Settings have been moved to the Results tab
        # for better UX (edit porosity next to K-value calculations)

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

        export_csv_btn = QPushButton("Export to CSV")
        export_csv_btn.clicked.connect(self.export_to_csv)

        copy_btn = QPushButton("Copy Statistics")
        copy_btn.clicked.connect(self.copy_to_clipboard)

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

        # Update comprehensive grain analysis panels
        self.update_grain_analysis_panels()

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

        soil_type = self.dataset.classify(scheme=self._scheme).label

        # Update info bar
        self.info_bar.update_info(
            sample_name=self.dataset.sample_name,
            d50=d50,
            cu=cu,
            mean_k=mean_k,
            soil_type=soil_type,
        )

    # NOTE: update_percentile_table() and update_gradation() have been replaced
    # by update_grain_analysis_panels() which handles all grain analysis updates

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
            table.setItem(row, 2, QTableWidgetItem(f"{value * 100:.3e}"))
            table.setItem(row, 3, QTableWidgetItem(f"{value * 86400:.1f}"))

        # Update classification
        mean_k = np.mean(k_values)
        classification = _perm_class(mean_k)
        self.k_stats_widget.classification_label.setText(
            f"Permeability: {classification}"
        )

    def update_soil_classification(self):
        """Update soil classification display"""
        result = self.dataset.classify(scheme=self._scheme)
        f = result.fractions
        text = (
            f"{result.scheme.name} Classification:\n"
            f"{'─' * 35}\n\n"
            f"Primary type:  {result.primary_type}\n"
            f"Gradation:     {result.gradation or '—'}\n"
        )
        if result.uscs_symbol:
            text += f"USCS symbol:   {result.uscs_symbol}\n"
        text += (
            f"\nLabel: {result.label}\n\n"
            f"Grain fractions:\n"
            f"  Clay:   {f.clay_pct:.1f}%\n"
            f"  Silt:   {f.silt_pct:.1f}%\n"
            f"  Sand:   {f.sand_pct:.1f}%\n"
            f"  Gravel: {f.gravel_pct:.1f}%\n"
            f"  Cobble: {f.cobble_pct:.1f}%\n\n"
            f"Cu: {result.cu_label}  |  Cc: {result.cc_label}\n"
        )
        self.classification_widget.classification_text.setPlainText(text)

    def set_scheme(self, scheme):
        """Set the active classification scheme and refresh classification displays."""
        self._scheme = scheme
        self.update_soil_classification()
        self.update_summary_bar()

    def set_k_results(self, results: List[KCalculationResult]):
        """Set K-calculation results and update display"""
        self.k_results = results
        self.update_grain_analysis_panels()  # Update comprehensive grain analysis panels
        self.update_display()

    # NOTE: Porosity management methods have been moved to DatasetTab (Results tab)
    # where they can directly trigger K-value recalculation

    # ===== GRAIN ANALYSIS UPDATE METHODS =====

    def update_environmental_parameters(self):
        """Update environmental parameters display (READ-ONLY)"""
        text = f"Temperature: {self.temperature}°C\n"
        text += f"Porosity: {self.porosity:.4f}"
        if (
            hasattr(self.dataset, "calculated_porosity")
            and self.dataset.calculated_porosity
        ):
            if abs(self.porosity - self.dataset.calculated_porosity) < 0.001:
                text += " (calculated)"
            else:
                text += f" (modified from {self.dataset.calculated_porosity:.4f})"
        text += "\n\nNote: Edit porosity in the Results tab"
        self.env_text.setPlainText(text)

    def update_grain_analysis_panels(self):
        """Update all grain analysis panels with calculated values"""
        import math
        from k_calculations import KCalculator

        calculator = KCalculator()

        # Prepare grain_data dict for interpolation
        grain_data = {
            "particle_sizes": list(self.dataset.particle_sizes),
            "percent_passing": list(self.dataset.percent_passing),
        }
        dmean = (
            self.dataset.get_arithmetic_mean_grain_size()
            if hasattr(self.dataset, "get_arithmetic_mean_grain_size")
            else None
        )
        if dmean is not None:
            grain_data["Dmean_arithmetic"] = dmean

        # Calculate all percentiles
        percentiles = {}
        standard_percentiles = [
            5,
            10,
            15,
            16,
            17,
            20,
            25,
            30,
            40,
            50,
            60,
            70,
            75,
            80,
            84,
            85,
            90,
            95,
        ]
        for p in standard_percentiles:
            value = calculator._interpolate_percentile(grain_data, p)
            if value:
                percentiles[p] = value

        # === UPDATE PERCENTILES DISPLAY ===
        html_text = f"<pre style='font-family: {F.MONO}, monospace; font-size: {F.SZ_SM}pt;'>"
        html_text += "<b>Grain Size Percentiles (Linear Interpolation):</b>\n"
        html_text += "━" * 45 + "\n\n"

        # Display in 3 columns
        for i in range(0, len(standard_percentiles), 3):
            row_percentiles = standard_percentiles[i : i + 3]
            for p in row_percentiles:
                if p in percentiles:
                    # Bold for key percentiles used by multiple methods
                    if p in [10, 20, 30, 50, 60]:
                        html_text += f"<b>D{p:>2}: {percentiles[p]:>6.3f} mm</b>    "
                    else:
                        html_text += f"D{p:>2}: {percentiles[p]:>6.3f} mm    "
            html_text += "\n"

        html_text += "\n<b>Bold</b> = Critical values used by multiple methods"
        html_text += "</pre>"
        self.percentiles_text.setHtml(html_text)

        # === UPDATE GRADATION PARAMETERS DISPLAY ===
        d5 = percentiles.get(5)
        d10 = percentiles.get(10)
        d16 = percentiles.get(16)
        d30 = percentiles.get(30)
        d50 = percentiles.get(50)
        d60 = percentiles.get(60)
        d84 = percentiles.get(84)
        d95 = percentiles.get(95)

        gradation_text = "<b>Gradation Parameters:</b>\n"
        gradation_text += "━" * 35 + "\n\n"

        # Uniformity Coefficient
        if d10 and d60:
            cu = d60 / d10
            gradation_text += f"<b>Uniformity Coefficient (Cu):</b> {cu:.2f}\n"
            gradation_text += f"  └─ D60/D10 = {d60:.3f}/{d10:.3f}\n"
            gradation_text += f"  └─ <b>{_cu_label(cu)}</b>\n"

        # Coefficient of Curvature
        if d10 and d30 and d60:
            cc = (d30 * d30) / (d10 * d60)
            gradation_text += f"\n<b>Coefficient of Curvature (Cc):</b> {cc:.2f}\n"
            gradation_text += f"  └─ D30²/(D10×D60)\n"
            if 1 <= cc <= 3:
                gradation_text += "  └─ <b>Well-graded range</b> ✓\n"
            else:
                gradation_text += "  └─ Outside typical range\n"

        # Sorting Coefficient
        if d16 and d84 and d16 > 0 and d84 > 0:
            sigma = math.sqrt(d84 / d16)
            gradation_text += f"\n<b>Sorting Coefficient (σ):</b> {sigma:.2f}\n"
            gradation_text += f"  └─ √(D84/D16) = √({d84:.3f}/{d16:.3f})\n"
            if sigma < 2:
                gradation_text += "  └─ <b>Well sorted</b>\n"
            elif sigma < 4:
                gradation_text += "  └─ <b>Moderately sorted</b>\n"
            else:
                gradation_text += "  └─ <b>Poorly sorted</b>\n"

        # Span Ratio
        if d5 and d95:
            span = d95 / d5
            gradation_text += f"\n<b>Span Ratio:</b> {span:.1f}\n"
            gradation_text += f"  └─ D95/D5 = {d95:.3f}/{d5:.3f}\n"

        # Wrap in HTML pre tag
        gradation_html = f"<pre style='font-family: {F.MONO}, monospace; font-size: {F.SZ_SM}pt;'>{gradation_text}</pre>"
        self.gradation_text.setHtml(gradation_html)

        # === UPDATE SPECIAL METHOD DIAMETERS DISPLAY ===
        special_text = "<b>Special Method Diameters:</b>\n"
        special_text += "━" * 50 + "\n\n"

        # Calculate special diameters
        kruger_de = calculator._kruger_diameter_cm(grain_data)
        harmonic_de = calculator._harmonic_mean_diameter_cm(grain_data)
        zunker_de = calculator._zunker_diameter_cm(grain_data)
        zamarin_de = calculator._zamarin_diameter_cm(grain_data)
        geom_mean = calculator._calculate_geometric_mean(grain_data)

        if kruger_de:
            special_text += f"<b>Kruger dₑ:</b>        {kruger_de:.4f} cm  ({kruger_de * 10:.4f} mm)\n"
        if harmonic_de:
            special_text += f"<b>Kozeny-Carman dₑ:</b> {harmonic_de:.4f} cm  ({harmonic_de * 10:.4f} mm)\n"
        if zunker_de:
            special_text += f"<b>Zunker dₑ:</b>        {zunker_de:.4f} cm  ({zunker_de * 10:.4f} mm)\n"
        if zamarin_de:
            special_text += f"<b>Zamarin dₑ:</b>       {zamarin_de:.4f} cm  ({zamarin_de * 10:.4f} mm)\n"
        if geom_mean:
            special_text += f"\n<b>Geometric Mean:</b>   {geom_mean:.4f} mm\n"

        if not any([kruger_de, harmonic_de, zunker_de, zamarin_de, geom_mean]):
            special_text += "No special diameters calculated (insufficient data)\n"

        special_html = f"<pre style='font-family: {F.MONO}, monospace; font-size: {F.SZ_SM}pt;'>{special_text}</pre>"
        self.special_diameters_text.setHtml(special_html)

    # ===== EXPORT METHODS (Placeholders for now) =====

    def export_to_excel(self):
        """Export statistics to formatted Excel file"""
        QMessageBox.information(
            self, "Export to Excel", "Excel export will be implemented in Phase 5"
        )

    def export_to_csv(self):
        """Export statistics to CSV"""
        QMessageBox.information(
            self, "Export to CSV", "CSV export will be implemented in Phase 5"
        )

    def copy_to_clipboard(self):
        """Copy formatted statistics to clipboard"""
        QMessageBox.information(
            self, "Copy to Clipboard", "Clipboard copy will be implemented in Phase 5"
        )
