"""
Dataset tab containing plot workspace, results, and statistics for a single dataset
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QGroupBox,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QHeaderView,
    QLabel,
    QFrame,
    QTextBrowser,
    QSplitter,
    QLineEdit,
    QScrollArea,
    QApplication,
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from typing import Optional, List, Dict
import numpy as np

from data_loader import GrainSizeData
from k_calculations import KCalculator, KCalculationResult, CalculationStatus
from .stack_fade import TabFadeInController


_METHOD_META = {
    "Hazen": {
        "category": "Empirical · Sand",
        "applicability": "Valid for uniform fine to medium sands with D₁₀ between 0.1–3.0 mm and Cu ≤ 5. Results may underestimate K for graded sediments.",
        "reference": "Hazen, A. (1892). Some physical properties of sands and gravels, with special reference to their use in filtration. Annual Report of the State Board of Health of Massachusetts.",
    },
    "Hazen_1892": {
        "category": "Empirical · Sand",
        "applicability": "Original 1892 mm² formulation with 10 °C reference temperature. D₁₀ in mm. Less commonly used than the simplified variant.",
        "reference": "Hazen, A. (1892). Some physical properties of sands and gravels, with special reference to their use in filtration. Annual Report of the State Board of Health of Massachusetts.",
    },
    "Slichter": {
        "category": "Empirical · Sand",
        "applicability": "Applicable to uniform sands. Uses D₁₀. Best suited for laboratory repacked samples.",
        "reference": "Slichter, C.S. (1898). Theoretical investigation of the motion of ground waters. 19th Annual Report of the U.S. Geological Survey, Part II, 295–384.",
    },
    "Terzaghi": {
        "category": "Empirical · Gravel",
        "applicability": "Developed for uniform sands and gravels using D₁₀. Based on Darcy flow through granular media.",
        "reference": "Terzaghi, K. (1925). Erdbaumechanik auf bodenphysikalischer Grundlage. Franz Deuticke, Leipzig.",
    },
    "Beyer": {
        "category": "Empirical · Sand/Gravel",
        "applicability": "Applicable to sands and gravels with D₁₀ between 0.06–0.6 mm and Cu between 1–20. Widely used in German hydrogeology.",
        "reference": "Beyer, W. (1964). Zur Bestimmung der Wasserdurchlässigkeit von Kiesen und Sanden aus der Kornverteilungskurve. Wasserwirtschaft–Wassertechnik, 14(6), 165–169.",
    },
    "Sauerbrei": {
        "category": "Empirical · Sand",
        "applicability": "Best suited for well-graded medium sands. Uses D₁₇ (17th percentile) as the characteristic grain size.",
        "reference": "Sauerbrei, E. (1932). Cited in: Vukovic, M. & Soro, A. (1992). Determination of Hydraulic Conductivity of Porous Media from Grain-Size Composition. Water Resources Publications, Colorado.",
    },
    "Kruger": {
        "category": "Semi-empirical · Sand/Gravel",
        "applicability": "Uses effective diameter dₑ derived from the full grain-size distribution. Suitable for non-uniform materials.",
        "reference": "Kruger, E. (1919). Die Grundwasserbewegung. Internationale Mitteilungen für Bodenkunde, 9, 1–12.",
    },
    "Kozeny-Carman": {
        "category": "Theoretical · All",
        "applicability": "Theoretically derived from Navier-Stokes equations. Applicable across a wide range of grain sizes when porosity is well constrained.",
        "reference": "Kozeny, J. (1927). Über kapillare Leitung des Wassers im Boden. Sitzungsberichte der Akademie der Wissenschaften, Wien, 136, 271–306. Carman, P.C. (1937). Fluid flow through granular beds. Trans. Inst. Chem. Eng., 15, 150–166.",
    },
    "Zunker": {
        "category": "Theoretical · Sand/Gravel",
        "applicability": "Based on specific surface area using an effective diameter from the grain-size distribution. Developed for Central European sediments.",
        "reference": "Zunker, F. (1930). Das Verhalten des Bodens zum Wasser. Handbuch der Bodenlehre, 6, 66–220.",
    },
    "Zamarin": {
        "category": "Semi-empirical · Sand/Gravel",
        "applicability": "Uses specific surface area-based effective diameter. Derived from grain-size distribution of granular soils.",
        "reference": "Zamarin, E.A. (1928). Cited in: Vukovic, M. & Soro, A. (1992). Determination of Hydraulic Conductivity of Porous Media from Grain-Size Composition. Water Resources Publications, Colorado.",
    },
    "USBR": {
        "category": "Empirical · Sand",
        "applicability": "Applicable to medium sands. Uses D₂₀. Developed by the U.S. Bureau of Reclamation for irrigation canal design.",
        "reference": "United States Bureau of Reclamation (1977). Design of Small Canal Structures. Denver, CO: USBR Engineering Monograph.",
    },
    "Barr": {
        "category": "Semi-empirical · Sand/Gravel",
        "applicability": "Uses D₅, D₁₀ and D₆₀. Suitable for poorly-sorted sands and gravels.",
        "reference": "Barr, D.W. (2001). Coefficient of permeability determined by measurable parameters. Ground Water, 39(3), 356–361.",
    },
    "Alyamani-Sen": {
        "category": "Empirical · Sand",
        "applicability": "Uses D₁₀, D₅₀ and the slope of the grain-size curve. More accurate for well-graded sands than single-diameter methods.",
        "reference": "Alyamani, M.S. & Sen, Z. (1993). Determination of hydraulic conductivity from complete grain-size distribution curves. Ground Water, 31(4), 551–555.",
    },
    "Chapuis": {
        "category": "Semi-empirical · Sand/Gravel",
        "applicability": "Applicable to natural, non-cohesive soils from clean sand to gravel. Requires D₁₀ and Cu. Not suitable for gap-graded materials.",
        "reference": "Chapuis, R.P. (2004). Predicting the saturated hydraulic conductivity of sand and gravel using effective diameter and void ratio. Canadian Geotechnical Journal, 41(5), 787–795.",
    },
    "Shepherd": {
        "category": "Empirical · Alluvial",
        "applicability": "Power-law relationship using D₅₀. Derived from fluvial sediment datasets. Best for alluvial aquifer materials.",
        "reference": "Shepherd, R.G. (1989). Correlations of permeability and grain size. Ground Water, 27(5), 633–638.",
    },
    "Krumbein-Monk": {
        "category": "Empirical · Sand",
        "applicability": "Uses geometric mean diameter and sorting coefficient from phi-scale statistics. Developed for unconsolidated sands from core samples.",
        "reference": "Krumbein, W.C. & Monk, G.D. (1943). Permeability as a function of the size parameters of unconsolidated sand. Trans. Am. Inst. Min. Metall. Pet. Eng., 151, 153–163.",
    },
}


class DatasetTab(QWidget):
    """
    A complete dataset tab with nested tabs for plots, results, and statistics
    """

    # Signals
    data_updated = pyqtSignal(str)  # Emitted when dataset data changes
    calculation_complete = pyqtSignal(str, list)  # dataset_name, results

    def __init__(self, dataset: GrainSizeData, parent=None):
        super().__init__(parent)
        self.dataset = dataset
        self.k_calculator = KCalculator()
        self.current_results: List[KCalculationResult] = []
        # Use dataset-specific values instead of global defaults
        self.temperature = dataset.temperature
        base_porosity = (
            dataset.current_porosity
            if dataset.current_porosity is not None
            else dataset.calculated_porosity
            if dataset.calculated_porosity is not None
            else dataset.porosity
        )
        if base_porosity is None:
            base_porosity = 0.40
        if dataset.current_porosity is None:
            dataset.current_porosity = base_porosity
        self.porosity = base_porosity

        self.init_ui()
        self.load_dataset_data()

    def init_ui(self):
        """Initialize the UI with nested tabs"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create nested tab widget
        self.nested_tabs = QTabWidget()
        self.nested_tabs.setObjectName("nested-subtabs")
        self.nested_tabs.setIconSize(QSize(12, 12))

        # Style to match .ntab-bar concept: 32px bar, earth bottom border on active
        from .theme import C, F, SZ
        self.nested_tabs.setStyleSheet(f"""
            QTabWidget#nested-subtabs::pane {{
                border: none;
                border-top: none;
            }}
            QTabWidget#nested-subtabs > QTabBar {{
                background: {C.BG};
                border-bottom: 2px solid {C.BORDER};
                qproperty-drawBase: 0;
            }}
            QTabWidget#nested-subtabs > QTabBar::tab {{
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: 0;
                padding: 0 15px;
                margin-bottom: -2px;
                margin-right: 0;
                font-family: "{F.UI}";
                font-size: {F.SZ_BASE}pt;
                font-weight: 500;
                color: {C.TEXT_MUTED};
                min-height: {SZ.SUB_TABBAR_H}px;
                max-height: {SZ.SUB_TABBAR_H}px;
            }}
            QTabWidget#nested-subtabs > QTabBar::tab:selected {{
                color: {C.TEXT};
                border-bottom: 2px solid {C.EARTH};
            }}
            QTabWidget#nested-subtabs > QTabBar::tab:hover:!selected {{
                color: {C.TEXT_MID};
            }}
        """)

        # Import here to avoid circular imports
        from .plot_workspace import PlotWorkspace
        from .theme import icon

        # Plot Workspace tab
        self.plot_workspace = PlotWorkspace(self.dataset)
        self.nested_tabs.addTab(self.plot_workspace, icon("fa6s.chart-line", C.TEXT_MID), "Plot")

        # Results tab
        self.results_widget = self.create_results_tab()
        self.nested_tabs.addTab(self.results_widget, icon("fa6s.table", C.TEXT_MID), "Results")

        # Statistics tab
        self.statistics_widget = self.create_statistics_tab()
        self.nested_tabs.addTab(self.statistics_widget, icon("fa6s.chart-column", C.TEXT_MID), "Statistics")

        self._nested_tab_fader = TabFadeInController(
            self.nested_tabs,
            self,
            duration_ms=105,
        )

        layout.addWidget(self.nested_tabs)

    def create_results_tab(self):
        """Create the results tab matching the 02_tabs.html concept layout."""
        from .theme import C, F
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Summary / stat bar ──────────────────────────────────────────────────
        self.res_bar = QFrame()
        self.res_bar.setObjectName("res-bar")
        self.res_bar.setFixedHeight(56)
        self.res_bar.setStyleSheet(f"""
            QFrame#res-bar {{
                background: {C.BG_RAISED};
                border-bottom: 1px solid {C.BORDER};
            }}
            QFrame#res-bar QLabel {{ background: transparent; }}
        """)
        bar_layout = QHBoxLayout(self.res_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        self._stat_k_md   = self._make_stat_cell(bar_layout, "—", "K̄ (m/d)",        C.OLIVE, sub="geometric mean")
        self._stat_k_ms   = self._make_stat_cell(bar_layout, "—", "K̄ (m/s)",        C.K_BLUE)
        self._stat_valid  = self._make_stat_cell(bar_layout, "—", "Methods valid",   C.TEXT)
        self._stat_d50    = self._make_stat_cell(bar_layout, "—", "D₅₀",             C.TEXT)
        self._stat_temp   = self._make_stat_cell(bar_layout, f"{self.temperature:.1f} °C", "Temperature", C.TEXT)

        bar_layout.addStretch()

        # Export / Copy buttons on right side of bar
        btn_frame = QFrame()
        btn_frame.setStyleSheet("QFrame { background: transparent; }")
        btn_fl = QHBoxLayout(btn_frame)
        btn_fl.setContentsMargins(0, 0, 10, 0)
        btn_fl.setSpacing(5)
        self._res_export_btn = QPushButton("Export")
        self._res_export_btn.setFixedHeight(24)
        self._res_copy_btn = QPushButton("Copy")
        self._res_copy_btn.setFixedHeight(24)
        for btn in (self._res_export_btn, self._res_copy_btn):
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.40);
                    border: 1px solid {C.BORDER};
                    border-radius: 4px;
                    font-family: '{F.UI}';
                    font-size: {F.SZ_SM}pt;
                    color: {C.TEXT_MID};
                    padding: 0 10px;
                }}
                QPushButton:hover {{
                    background: {C.BG_LOW};
                    border-color: {C.BORDER_DK};
                    color: {C.TEXT};
                }}
            """)
        self._res_export_btn.clicked.connect(self._on_res_export)
        self._res_copy_btn.clicked.connect(self._on_res_copy)
        btn_fl.addWidget(self._res_export_btn)
        btn_fl.addWidget(self._res_copy_btn)
        bar_layout.addWidget(btn_frame)

        self.res_bar.setVisible(False)
        layout.addWidget(self.res_bar)

        # ── Split view: table (left) + detail panel (right) ─────────────────────
        self._res_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._res_splitter.setObjectName("res-split")
        self._res_splitter.setStyleSheet("""
            QSplitter::handle { width: 1px; background: transparent; }
        """)

        # K-values table
        table_container = QWidget()
        tc_layout = QVBoxLayout(table_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(0)

        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(
            ["Method", "Category", "K (cm/s)", "K (m/s)", "K (m/d)", "Status"]
        )
        self.results_table.setSortingEnabled(True)
        self.results_table.setAlternatingRowColors(False)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results_table.setShowGrid(False)
        self.results_table.setStyleSheet(f"""
            QTableWidget {{
                border: none;
                border-radius: 0;
                font-family: '{F.UI}';
                font-size: {F.SZ_MD}pt;
                gridline-color: transparent;
            }}
            QTableWidget::item {{
                padding: 5px 10px;
                border-bottom: 1px solid rgba(212,196,168,0.4);
            }}
            QTableWidget::item:selected {{
                background: rgba(107,142,35,0.07);
                color: {C.TEXT};
            }}
            QTableWidget::item:hover {{
                background: rgba(212,196,168,0.18);
            }}
            QHeaderView::section {{
                background: {C.BG_RAISED};
                border: none;
                border-bottom: 2px solid {C.BORDER_DK};
                border-right: 1px solid {C.BORDER};
                padding: 6px 10px;
                font-family: '{F.UI}';
                font-size: {F.SZ_SM}pt;
                font-weight: 600;
                color: {C.TEXT_MID};
                text-transform: uppercase;
                letter-spacing: 0.04em;
            }}
        """)

        header = self.results_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(False)

        self.results_table.itemSelectionChanged.connect(self.on_result_row_selected)
        tc_layout.addWidget(self.results_table)

        # Method detail panel
        self.detail_panel = self._create_detail_panel()

        self._res_splitter.addWidget(table_container)
        self._res_splitter.addWidget(self.detail_panel)
        self._res_splitter.setStretchFactor(0, 60)
        self._res_splitter.setStretchFactor(1, 40)

        layout.addWidget(self._res_splitter, 1)
        return widget

    def _make_stat_cell(self, parent_layout, value: str, key: str, value_color: str = None, sub: str = "") -> "QLabel":
        """Create a stat cell for the results summary bar. Returns the value QLabel."""
        from .theme import C, F
        cell = QFrame()
        cell.setStyleSheet(f"""
            QFrame {{
                border-right: 1px solid {C.BORDER};
                background: transparent;
            }}
        """)
        vbox = QVBoxLayout(cell)
        vbox.setContentsMargins(16, 6, 16, 6)
        vbox.setSpacing(1)
        vbox.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        val_lbl = QLabel(value)
        color = value_color if value_color else C.TEXT
        val_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: 13pt; font-weight: 500; color: {color}; border: none;"
        )
        vbox.addWidget(val_lbl)

        key_lbl = QLabel(key)
        key_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_XS}pt; font-weight: 700; "
            f"color: {C.TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.06em; border: none;"
        )
        vbox.addWidget(key_lbl)

        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setStyleSheet(
                f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED}; border: none;"
            )
            vbox.addWidget(sub_lbl)

        parent_layout.addWidget(cell)
        return val_lbl

    def _create_detail_panel(self) -> "QFrame":
        """Create the method detail panel (right side of Results split view)."""
        from .theme import C, F
        panel = QFrame()
        panel.setObjectName("detail-panel")
        panel.setMinimumWidth(210)
        panel.setMaximumWidth(320)
        panel.setStyleSheet(f"""
            QFrame#detail-panel {{
                background: {C.BG_RAISED};
                border-left: 1px solid {C.BORDER};
            }}
            QFrame#detail-panel QLabel {{ background: transparent; }}
        """)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._detail_content = QWidget()
        self._detail_content.setStyleSheet(f"background: {C.BG_RAISED};")
        self._detail_layout = QVBoxLayout(self._detail_content)
        self._detail_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_layout.setSpacing(0)
        self._detail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Placeholder when nothing selected
        placeholder = QLabel("Select a row to view\nmethod details")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.UI}'; font-size: {F.SZ_MD}pt; padding: 30px;"
        )
        self._detail_layout.addWidget(placeholder)
        self._detail_placeholder = placeholder

        scroll.setWidget(self._detail_content)
        panel_layout.addWidget(scroll)
        return panel

    def _update_detail_panel(self, result) -> None:
        """Rebuild the detail panel content for the given calculation result."""
        from .theme import C, F

        # Clear existing content
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        meta = _METHOD_META.get(result.method_name, {})
        category = meta.get("category", "—")
        applicability = meta.get("applicability", "No applicability information available.")
        reference = meta.get("reference", "No reference available.")

        status = result.status.value if hasattr(result.status, "value") else str(result.status)
        if "OK" in status:
            status_color = C.OLIVE_DK
            status_bg = "rgba(107,142,35,0.08)"
            status_icon = "✓"
        elif "Warning" in status:
            status_color = C.LED_WARN
            status_bg = "rgba(208,128,32,0.08)"
            status_icon = "⚠"
        else:
            status_color = C.LED_ERR
            status_bg = "rgba(192,56,40,0.07)"
            status_icon = "✗"

        # ── Header section ──────────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: {C.BG_LOW};
                border-bottom: 1px solid {C.BORDER};
            }}
            QFrame QLabel {{ background: transparent; }}
        """)
        hdr_layout = QVBoxLayout(header)
        hdr_layout.setContentsMargins(14, 12, 14, 10)
        hdr_layout.setSpacing(2)

        name_lbl = QLabel(result.method_name)
        name_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_LG}pt; font-weight: 600; color: {C.TEXT};"
        )
        name_lbl.setWordWrap(True)
        hdr_layout.addWidget(name_lbl)

        cat_lbl = QLabel(category)
        cat_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_SM}pt; color: {C.TEXT_MUTED};"
        )
        hdr_layout.addWidget(cat_lbl)

        if result.k_value is not None and result.k_value > 0:
            k_m_s = result.k_value
            k_m_d = k_m_s * 86400.0
            k_cm_s = k_m_s * 100.0

            k_big = QLabel(f"{k_m_s:.3e} m/s")
            k_big.setStyleSheet(
                f"font-family: '{F.MONO}'; font-size: 15pt; font-weight: 500; color: {C.K_BLUE}; margin-top: 6px;"
            )
            hdr_layout.addWidget(k_big)

            k_units = QLabel(f"{k_m_d:.2f} m/d  ·  {k_cm_s:.3e} cm/s")
            k_units.setStyleSheet(
                f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED};"
            )
            hdr_layout.addWidget(k_units)
        else:
            no_k = QLabel("No valid K-value")
            no_k.setStyleSheet(
                f"font-family: '{F.UI}'; font-size: {F.SZ_MD}pt; color: {C.LED_ERR}; font-weight: 600; margin-top: 6px;"
            )
            hdr_layout.addWidget(no_k)

        self._detail_layout.addWidget(header)

        # ── Status alert (if message present) ───────────────────────────────────
        if result.status_message:
            alert = QFrame()
            alert.setStyleSheet(f"""
                QFrame {{
                    background: {status_bg};
                    border-left: 3px solid {status_color};
                    border-bottom: 1px solid {C.BORDER};
                }}
                QFrame QLabel {{ background: transparent; }}
            """)
            al = QVBoxLayout(alert)
            al.setContentsMargins(12, 8, 12, 8)
            msg = QLabel(f"{status_icon}  {result.status_message}")
            msg.setStyleSheet(
                f"font-family: '{F.UI}'; font-size: {F.SZ_SM}pt; color: {status_color}; font-weight: 500;"
            )
            msg.setWordWrap(True)
            al.addWidget(msg)
            self._detail_layout.addWidget(alert)

        # ── Parameters Used section ──────────────────────────────────────────────
        params = []
        d10 = self.dataset.get_d10()
        d30 = self.dataset.get_d30()
        d50 = self.dataset.get_d50()
        d60 = self.dataset.get_d60()
        if d10: params.append(("D₁₀", f"{d10:.3f} mm"))
        if d30: params.append(("D₃₀", f"{d30:.3f} mm"))
        if d50: params.append(("D₅₀", f"{d50:.3f} mm"))
        if d60: params.append(("D₆₀", f"{d60:.3f} mm"))
        if d10 and d60:
            cu = d60 / d10
            params.append(("Cu", f"{cu:.2f}"))
            if d30:
                cc = (d30 * d30) / (d10 * d60)
                params.append(("Cc", f"{cc:.2f}"))
        params.append(("Temperature", f"{self.temperature:.1f} °C"))
        params.append(("Porosity", f"{self.porosity:.4f}"))

        # Merge method-specific values
        method_vals = self.get_method_specific_values(result.method_name)
        for k, v in method_vals.items():
            params.append((k, v))

        self._detail_layout.addWidget(self._make_detail_section("Parameters Used", params))

        # ── Formula section ──────────────────────────────────────────────────────
        self._detail_layout.addWidget(self._make_detail_section_text("Formula", result.formula_used, monospace=True))

        # ── Applicability section ────────────────────────────────────────────────
        cond_text = (
            f"{'✓ Conditions met' if result.conditions_met else '✗ Conditions NOT met'}  —  {applicability}"
            if hasattr(result, 'conditions_met')
            else applicability
        )
        self._detail_layout.addWidget(self._make_detail_section_text("Applicability", cond_text))

        # ── Reference section ────────────────────────────────────────────────────
        self._detail_layout.addWidget(self._make_detail_section_text("Reference", reference))

        self._detail_layout.addStretch()

    def _make_detail_section(self, title: str, rows: list) -> "QFrame":
        """Create a detail panel section with label-value rows."""
        from .theme import C, F
        section = QFrame()
        section.setStyleSheet(f"""
            QFrame {{
                border-bottom: 1px solid rgba(212,196,168,0.4);
                background: transparent;
            }}
            QFrame QLabel {{ background: transparent; }}
        """)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_XS}pt; font-weight: 700; "
            f"color: {C.TEXT_MUTED}; letter-spacing: 0.07em; margin-bottom: 4px;"
        )
        layout.addWidget(lbl)

        for row_label, row_value in rows:
            row_frame = QFrame()
            row_frame.setStyleSheet("QFrame { background: transparent; }")
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            rl = QLabel(row_label)
            rl.setStyleSheet(
                f"font-family: '{F.UI}'; font-size: {F.SZ_SM}pt; color: {C.TEXT_MID};"
            )
            rv = QLabel(row_value)
            rv.setStyleSheet(
                f"font-family: '{F.MONO}'; font-size: {F.SZ_SM}pt; color: {C.TEXT};"
            )
            rv.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            row_layout.addWidget(rl)
            row_layout.addStretch()
            row_layout.addWidget(rv)
            layout.addWidget(row_frame)

        return section

    def _make_detail_section_text(self, title: str, text: str, monospace: bool = False) -> "QFrame":
        """Create a detail panel section with a text block."""
        from .theme import C, F
        section = QFrame()
        section.setStyleSheet(f"""
            QFrame {{
                border-bottom: 1px solid rgba(212,196,168,0.4);
                background: transparent;
            }}
            QFrame QLabel {{ background: transparent; }}
        """)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_XS}pt; font-weight: 700; "
            f"color: {C.TEXT_MUTED}; letter-spacing: 0.07em;"
        )
        layout.addWidget(lbl)

        content_lbl = QLabel(text)
        content_lbl.setWordWrap(True)
        if monospace:
            content_lbl.setStyleSheet(f"""
                font-family: '{F.MONO}';
                font-size: {F.SZ_SM}pt;
                color: {C.TEXT_MID};
                background: {C.BG_LOW};
                border: 1px solid {C.BORDER};
                border-radius: 3px;
                padding: 6px 8px;
                line-height: 1.7;
            """)
        else:
            content_lbl.setStyleSheet(
                f"font-family: '{F.UI}'; font-size: {F.SZ_SM}pt; color: {C.TEXT_MUTED}; line-height: 1.5;"
            )
        layout.addWidget(content_lbl)
        return section

    def _on_res_export(self) -> None:
        """Export results — delegates to existing export_results()."""
        self.export_results()

    def _on_res_copy(self) -> None:
        """Copy results table to clipboard as tab-separated text."""
        if not self.current_results:
            return
        rows = ["Method\tCategory\tK (cm/s)\tK (m/s)\tK (m/d)\tStatus"]
        for result in self.current_results:
            meta = _METHOD_META.get(result.method_name, {})
            cat = meta.get("category", "—")
            status = result.status.value if hasattr(result.status, "value") else str(result.status)
            if result.k_value is not None and result.k_value > 0:
                k_cm_s = f"{result.k_value * 100:.3e}"
                k_m_s = f"{result.k_value:.2e}"
                k_m_d = f"{result.k_value * 86400:.1f}"
            else:
                k_cm_s = k_m_s = k_m_d = "N/A"
            rows.append(f"{result.method_name}\t{cat}\t{k_cm_s}\t{k_m_s}\t{k_m_d}\t{status}")
        QApplication.clipboard().setText("\n".join(rows))

    # NOTE: Grain analysis panels (percentiles, gradation, special diameters, environmental params)
    # have been moved to the Statistics Tab for better organization.
    # See statistics_tab.py for these components.

    def create_statistics_tab(self):
        """Create the enhanced statistics tab"""
        from .statistics_tab import StatisticsTab

        # Create new modular statistics tab
        self.statistics_tab = StatisticsTab(self.dataset, parent=self)

        return self.statistics_tab
    def apply_distribution_rows(self, rows: List[tuple[float, float]]) -> None:
        particle_sizes = [size for size, _ in rows]
        percent_passing = [percent for _, percent in rows]

        replacement = GrainSizeData(
            sample_name=self.dataset.sample_name,
            temperature=self.temperature,
            porosity=self.dataset.porosity,
            particle_sizes=particle_sizes,
            percent_passing=percent_passing,
            comments=self.dataset.comments,
            file_path=self.dataset.file_path,
        )

        manual_porosity_override = self._has_manual_porosity_override()
        preserved_porosity = self.porosity

        self.dataset.particle_sizes = list(replacement.particle_sizes)
        self.dataset.percent_passing = list(replacement.percent_passing)
        self.dataset.validation_messages = list(replacement.validation_messages)
        self.dataset.calculated_porosity = replacement.calculated_porosity

        if manual_porosity_override:
            self.dataset.current_porosity = preserved_porosity
            self.dataset.porosity = preserved_porosity
            self.porosity = preserved_porosity
        else:
            effective_porosity = (
                replacement.current_porosity
                if replacement.current_porosity is not None
                else replacement.porosity
            )
            self.dataset.current_porosity = effective_porosity
            self.dataset.porosity = effective_porosity
            self.porosity = effective_porosity

        self._clear_stale_mass_data()
        self.load_dataset_data()

        if self.current_results:
            selected_methods = [result.method_name for result in self.current_results]
            self.calculate_k_values(selected_methods)

        self.data_updated.emit(self.dataset.sample_name)

    def _has_manual_porosity_override(self) -> bool:
        calculated = getattr(self.dataset, "calculated_porosity", None)
        if calculated is None:
            return False
        return abs(float(self.porosity) - float(calculated)) > 1e-9

    def _clear_stale_mass_data(self) -> None:
        for attr in (
            "mass_values",
            "mass_grams",
            "fraction_masses",
            "retained_masses",
            "retained_mass_grams",
            "retained_weights",
            "weights_g",
        ):
            if hasattr(self.dataset, attr):
                setattr(self.dataset, attr, None)

    @staticmethod
    def _format_data_value(value: float) -> str:
        if value >= 10:
            return f"{value:.1f}"
        if value >= 1:
            return f"{value:.2f}"
        if value >= 0.1:
            return f"{value:.3f}"
        return f"{value:.4f}"

    def load_dataset_data(self):
        """Load and display the dataset data"""
        self.plot_workspace.refresh_plot()

        # Update statistics tab with data
        if hasattr(self, "statistics_tab"):
            self.statistics_tab.update_display()

    # Note: update_grain_statistics() is now handled by StatisticsTab
    # This method is kept for backward compatibility but delegates to the new tab
    def update_grain_statistics(self):
        """Update the grain size statistics display"""
        if hasattr(self, "statistics_tab"):
            self.statistics_tab.update_display()

    def set_scheme(self, scheme) -> None:
        """Propagate a new classification scheme to the plot and statistics."""
        self.plot_workspace.set_scheme(scheme)
        if hasattr(self, "statistics_tab"):
            self.statistics_tab.set_scheme(scheme)

    def set_parameters(self, temperature: float):
        """Update calculation parameters"""
        self.temperature = temperature
        self.dataset.temperature = temperature
        # Update statistics tab
        if hasattr(self, "statistics_tab"):
            self.statistics_tab.temperature = temperature
            self.statistics_tab.update_display()

    def set_porosity(self, porosity: float):
        """Update porosity parameter (called from statistics tab)"""
        self.porosity = porosity
        self.dataset.current_porosity = porosity
        # Recalculate K-values if we have methods selected
        if self.current_results:
            self.calculate_k_values()

    def calculate_k_values(self, selected_methods: Optional[List[str]] = None):
        """Calculate K values for this dataset"""
        if selected_methods is None:
            # Get all available methods from calculator
            selected_methods = self.k_calculator.get_all_method_names()

        # Prepare grain data
        grain_data = {}
        for key, value in {
            "D10": self.dataset.get_d10(),
            "D20": self.dataset.get_d20(),
            "D30": self.dataset.get_d30(),
            "D50": self.dataset.get_d50(),
            "D60": self.dataset.get_d60(),
        }.items():
            if value is not None:
                grain_data[key] = value

        # Provide full grain size distribution for methods that need fraction data
        grain_data["particle_sizes"] = list(self.dataset.particle_sizes)
        grain_data["percent_passing"] = list(self.dataset.percent_passing)

        # Calculate K values
        self.current_results = self.k_calculator.calculate_all_methods(
            grain_data,
            temperature=self.temperature,
            porosity=self.porosity,
            selected_methods=selected_methods,
        )

        self._apply_calculation_results(self.current_results)

    def apply_precomputed_results(self, results: List[KCalculationResult]):
        """Bind worker-computed K results without recalculating on the UI thread."""
        self._apply_calculation_results(list(results))

    def _apply_calculation_results(self, results: List[KCalculationResult]):
        self.current_results = list(results)

        # Update results table
        self.update_results_table()

        # Update statistics tab with K-results (now includes grain analysis panels)
        if hasattr(self, "statistics_tab"):
            self.statistics_tab.set_k_results(self.current_results)

        # Update plot with K results
        if self.current_results:
            k_dict = {}
            flagged_methods = set()
            for result in self.current_results:
                if result.k_value is not None and result.k_value > 0:
                    k_dict[result.method_name] = result.k_value
                if result.status != CalculationStatus.OK or not result.conditions_met:
                    flagged_methods.add(result.method_name)
            self.plot_workspace.add_k_results(k_dict, flagged_methods)

        # Emit signal
        self.calculation_complete.emit(self.dataset.sample_name, self.current_results)

    def update_results_table(self):
        """Populate the 6-column K-values table."""
        from .theme import C, F
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(len(self.current_results))

        for row, result in enumerate(self.current_results):
            meta = _METHOD_META.get(result.method_name, {})
            category = meta.get("category", "—")

            # Col 0: Method name
            method_item = QTableWidgetItem(result.method_name)
            method_item.setForeground(QColor(C.TEXT))
            self.results_table.setItem(row, 0, method_item)

            # Col 1: Category
            cat_item = QTableWidgetItem(category)
            cat_item.setForeground(QColor(C.TEXT_MUTED))
            self.results_table.setItem(row, 1, cat_item)

            # Cols 2-4: K values
            if result.k_value is not None and result.k_value > 0:
                k_m_s = result.k_value
                k_cm_s = k_m_s * 100.0
                k_m_d = k_m_s * 86400.0

                for col, val, fmt in [(2, k_cm_s, f"{k_cm_s:.3e}"), (3, k_m_s, f"{k_m_s:.2e}"), (4, k_m_d, f"{k_m_d:.1f}")]:
                    item = QTableWidgetItem(fmt)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    item.setData(Qt.ItemDataRole.UserRole, val)
                    item.setForeground(QColor(C.K_BLUE))
                    self.results_table.setItem(row, col, item)
            else:
                for col in [2, 3, 4]:
                    item = QTableWidgetItem("N/A")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                    item.setData(Qt.ItemDataRole.UserRole, -1)
                    item.setForeground(QColor(C.TEXT_MUTED))
                    item.setFont(self._italic_font())
                    self.results_table.setItem(row, col, item)

            # Col 5: Status badge
            status = result.status.value if hasattr(result.status, "value") else str(result.status)
            conditions_met = getattr(result, "conditions_met", True)

            if "OK" in status and conditions_met:
                badge_text = "OK"
                badge_fg = QColor(79, 106, 26)    # OLIVE_DK
                badge_bg = QColor(90, 170, 58, 25)
            elif "Warning" in status or not conditions_met:
                badge_text = "Warning"
                badge_fg = QColor(208, 128, 32)   # LED_WARN
                badge_bg = QColor(208, 128, 32, 22)
            elif "Error" in status:
                badge_text = "Error"
                badge_fg = QColor(192, 56, 40)    # LED_ERR
                badge_bg = QColor(192, 56, 40, 20)
            else:
                badge_text = "N/A"
                badge_fg = QColor(154, 140, 120)  # TEXT_MUTED
                badge_bg = QColor(154, 140, 120, 20)

            status_item = QTableWidgetItem(badge_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            status_item.setForeground(badge_fg)
            status_item.setBackground(badge_bg)
            if result.status_message:
                status_item.setToolTip(result.status_message)
            self.results_table.setItem(row, 5, status_item)

        self.results_table.setSortingEnabled(True)
        self.update_summary_bar()

    def _italic_font(self):
        """Return an italic QFont for N/A cells."""
        f = QFont()
        f.setItalic(True)
        return f

    def update_summary_bar(self):
        """Update the summary stat bar with current calculation results."""
        if not self.current_results:
            self.res_bar.setVisible(False)
            return

        self.res_bar.setVisible(True)

        valid_results = [r for r in self.current_results if r.k_value is not None and r.k_value > 0]
        total = len(self.current_results)
        valid_count = len(valid_results)

        # K̄ geometric mean (m/d)
        if valid_results:
            import math
            log_k_values = [math.log(r.k_value) for r in valid_results]
            k_geom_ms = math.exp(sum(log_k_values) / len(log_k_values))
            k_geom_md = k_geom_ms * 86400.0
            self._stat_k_md.setText(f"{k_geom_md:.2f}")
            self._stat_k_ms.setText(f"{k_geom_ms:.2e}")
        else:
            self._stat_k_md.setText("—")
            self._stat_k_ms.setText("—")

        # Methods valid
        self._stat_valid.setText(f"{valid_count} / {total}")

        # D50
        d50 = self.dataset.get_d50()
        self._stat_d50.setText(f"{d50:.3f} mm" if d50 else "—")

        # Temperature (may have been updated)
        self._stat_temp.setText(f"{self.temperature:.1f} °C")

    def on_result_row_selected(self):
        """Handle row selection — update detail panel."""
        selected = self.results_table.selectedItems()
        if not selected or not self.current_results:
            return

        row = selected[0].row()
        method_item = self.results_table.item(row, 0)
        if not method_item:
            return

        method_name = method_item.text()
        result = next((r for r in self.current_results if r.method_name == method_name), None)
        if result:
            self._update_detail_panel(result)

    def get_method_specific_values(self, method_name: str) -> dict:
        """Get method-specific calculated values for display"""
        from k_calculations import KCalculator

        calculator = KCalculator()
        grain_data = {
            "particle_sizes": list(self.dataset.particle_sizes),
            "percent_passing": list(self.dataset.percent_passing),
        }

        values = {}

        # Methods with special diameter calculations
        if method_name == "Kruger":
            de_cm = calculator._kruger_diameter_cm(grain_data)
            if de_cm:
                values["Kruger Effective Diameter (dₑ)"] = (
                    f"{de_cm:.4f} cm ({de_cm * 10:.4f} mm)"
                )

        elif method_name == "Kozeny-Carman":
            de_cm = calculator._harmonic_mean_diameter_cm(grain_data)
            if de_cm:
                values["Harmonic Mean Diameter (dₑ)"] = (
                    f"{de_cm:.4f} cm ({de_cm * 10:.4f} mm)"
                )

        elif method_name == "Zunker":
            de_cm = calculator._zunker_diameter_cm(grain_data)
            if de_cm:
                values["Zunker Effective Diameter (dₑ)"] = (
                    f"{de_cm:.4f} cm ({de_cm * 10:.4f} mm)"
                )

        elif method_name == "Zamarin":
            de_cm = calculator._zamarin_diameter_cm(grain_data)
            if de_cm:
                values["Zamarin Effective Diameter (dₑ)"] = (
                    f"{de_cm:.4f} cm ({de_cm * 10:.4f} mm)"
                )

        elif method_name == "Krumbein-Monk":
            d_geom = calculator._calculate_geometric_mean(grain_data)
            if d_geom:
                values["Geometric Mean Diameter (dgeom)"] = f"{d_geom:.4f} mm"
            # Also calculate sorting coefficient (sigma_phi)
            d16 = calculator._interpolate_percentile(grain_data, 16)
            d84 = calculator._interpolate_percentile(grain_data, 84)
            if d16 and d84 and d16 > 0 and d84 > 0:
                import math

                sigma_phi = math.sqrt(d84 / d16)
                values["Sorting Coefficient (σφ)"] = f"{sigma_phi:.4f}"

        # Methods using specific percentiles
        elif method_name in ["Hazen", "Hazen_1892", "Slichter", "Terzaghi", "Chapuis"]:
            d10 = calculator._interpolate_percentile(grain_data, 10)
            if d10:
                values["D₁₀ (Primary)"] = f"{d10:.4f} mm"

        elif method_name == "USBR":
            d20 = calculator._interpolate_percentile(grain_data, 20)
            if d20:
                values["D₂₀ (Primary)"] = f"{d20:.4f} mm"

        elif method_name == "Shepherd":
            d50 = calculator._interpolate_percentile(grain_data, 50)
            if d50:
                values["D₅₀ (Primary)"] = f"{d50:.4f} mm"

        elif method_name == "Sauerbrei":
            d17 = calculator._interpolate_percentile(grain_data, 17)
            if d17:
                values["D₁₇ (Primary)"] = f"{d17:.4f} mm"

        elif method_name == "Alyamani-Sen":
            d10 = calculator._interpolate_percentile(grain_data, 10)
            d50 = calculator._interpolate_percentile(grain_data, 50)
            if d10:
                values["D₁₀"] = f"{d10:.4f} mm"
            if d50:
                values["D₅₀"] = f"{d50:.4f} mm"
            if d10 and d50:
                intercept = 1355.3 * (d50**2) + 1.1892 * (d10**2)
                values["Intercept (I₀)"] = f"{intercept:.2f}"

        elif method_name == "Beyer":
            d10 = calculator._interpolate_percentile(grain_data, 10)
            d60 = calculator._interpolate_percentile(grain_data, 60)
            if d10 and d60:
                cu = d60 / d10
                values["D₁₀"] = f"{d10:.4f} mm"
                values["D₆₀"] = f"{d60:.4f} mm"
                values["Cu (for log₁₀ factor)"] = f"{cu:.2f}"

        elif method_name == "Barr":
            d5 = calculator._interpolate_percentile(grain_data, 5)
            d10 = calculator._interpolate_percentile(grain_data, 10)
            d60 = calculator._interpolate_percentile(grain_data, 60)
            if d5:
                values["D₅"] = f"{d5:.4f} mm"
            if d10:
                values["D₁₀"] = f"{d10:.4f} mm"
            if d60:
                values["D₆₀"] = f"{d60:.4f} mm"

        return values

    # Note: update_k_statistics() is now handled by StatisticsTab
    # This method is kept for backward compatibility but delegates to the new tab
    def update_k_statistics(self):
        """Update K-value statistics"""
        if hasattr(self, "statistics_tab"):
            self.statistics_tab.set_k_results(self.current_results)

    def export_results(self):
        """Export results to file"""
        # TODO: Implement export functionality
        QMessageBox.information(
            self,
            "Export",
            f"Export functionality for {self.dataset.sample_name} will be implemented",
        )

    def get_dataset_name(self) -> str:
        """Get the dataset name"""
        return self.dataset.sample_name

    def get_dataset(self) -> GrainSizeData:
        """Get the dataset object"""
        return self.dataset

    def get_results(self) -> List[KCalculationResult]:
        """Get the current K-calculation results"""
        return self.current_results

    # Note: Porosity management methods are now in StatisticsTab
    # These have been removed to avoid duplication
