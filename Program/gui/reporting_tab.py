"""Reporting tab — generates and previews professional analysis reports."""
from __future__ import annotations

from html import escape
import os
from typing import List

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QComboBox, QFileDialog,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QSplitter, QTextEdit,
    QVBoxLayout, QWidget,
)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtCore import QMarginsF
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from .theme import C, F
from .report_brand import ReportBrand
from report_generator import ReportGenerator
from grain_classification import ISO14688


# ── Small UI helpers ──────────────────────────────────────────────────────────

def _cat_label(text: str) -> QLabel:
    """All-caps muted category heading."""
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(f"""
        QLabel {{
            font-family: "{F.UI}";
            font-size: {F.SZ_SM}pt;
            font-weight: 700;
            color: {C.TEXT_MUTED};
            letter-spacing: 1px;
            padding: 10px 0 3px 0;
        }}
    """)
    return lbl


def _hdivider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color: {C.BORDER};")
    f.setFixedHeight(1)
    return f


def _field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"""
        QLabel {{
            font-family: "{F.UI}";
            font-size: {F.SZ_SM}pt;
            color: {C.TEXT_MID};
        }}
    """)
    return lbl


def _line_edit(placeholder: str = "") -> QLineEdit:
    edit = QLineEdit()
    if placeholder:
        edit.setPlaceholderText(placeholder)
    edit.setStyleSheet(f"""
        QLineEdit {{
            font-family: "{F.UI}";
            font-size: {F.SZ_BASE}pt;
            color: {C.TEXT};
            background: white;
            border: 1px solid {C.BORDER};
            border-radius: 3px;
            padding: 3px 6px;
        }}
        QLineEdit:focus {{ border-color: {C.OLIVE}; }}
    """)
    return edit


# ── Report type card button ───────────────────────────────────────────────────

class _TypeCard(QPushButton):
    """Toggleable card button for report type selection."""

    def __init__(self, icon_ch: str, label: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setText(f"{icon_ch}\n{label}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(54)
        self.toggled.connect(lambda _: self._refresh())
        self._refresh()

    def _refresh(self):
        on = self.isChecked()
        self.setStyleSheet(f"""
            QPushButton {{
                background: {"#6b8e23" if on else C.BG_RAISED};
                color: {"#ffffff" if on else C.TEXT};
                border: {"1.5px solid #4f6a1a" if on else f"1px solid {C.BORDER}"};
                border-radius: 6px;
                padding: 6px 4px;
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                font-weight: {"700" if on else "500"};
                text-align: center;
            }}
            QPushButton:hover:!checked {{
                border-color: {C.OLIVE};
                background: {C.BG_LOW};
            }}
        """)


# ── Individual sub-type chip row ──────────────────────────────────────────────

class _SubtypeChips(QWidget):
    """Horizontal chip selector for Individual report sub-type."""

    NAMES = ["Grain Size", "K-Values", "Combined"]

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(4)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        chip_style = f"""
            QPushButton {{
                background: {C.BG};
                color: {C.TEXT_MID};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 3px 8px;
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
            }}
            QPushButton:checked {{
                background: rgba(107,142,35,0.12);
                color: {C.OLIVE_DK};
                border-color: {C.OLIVE};
                font-weight: 600;
            }}
            QPushButton:hover:!checked {{ border-color: {C.OLIVE}; }}
        """
        for i, name in enumerate(self.NAMES):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(chip_style)
            self._group.addButton(btn, i)
            lay.addWidget(btn)

        self._group.button(0).setChecked(True)

    def selected(self) -> str:
        idx = self._group.checkedId()
        return self.NAMES[idx] if idx >= 0 else "Grain Size"


# ── Color swatch ──────────────────────────────────────────────────────────────

class _ColorSwatch(QPushButton):
    """Small square button showing current hex color."""

    def __init__(self, color: str = "#990000", parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setToolTip("Click to change brand color")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_color(color)

    def set_color(self, hex_color: str):
        self._color = hex_color
        self.setStyleSheet(f"""
            QPushButton {{
                background: {hex_color};
                border: 2px solid {C.BORDER_DK};
                border-radius: 4px;
            }}
            QPushButton:hover {{ border-color: {C.TEXT_MID}; }}
        """)

    def color(self) -> str:
        return self._color


# ── Main tab ──────────────────────────────────────────────────────────────────

class ReportingTab(QWidget):
    """Tab for generating and previewing professional reports."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report_generator = ReportGenerator()
        self._scheme = ISO14688
        self.dataset_tabs: List = []
        self._sample_contexts: list[dict] = []
        self._sample_checkboxes: list[tuple[QCheckBox, dict]] = []
        self.current_report_html = ""
        self.brand = ReportBrand.load()
        self._init_ui()

    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = self._build_left_panel()
        left.setMinimumWidth(260)
        left.setMaximumWidth(320)

        right = self._build_right_panel()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 800])

        root.addWidget(splitter)

    # ── Left panel ────────────────────────────────────────────────────────────

    def _build_left_panel(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {C.BG}; }}
            QWidget#left_inner {{ background: {C.BG}; }}
        """)

        inner = QWidget()
        inner.setObjectName("left_inner")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(2)

        # Report type cards
        lay.addWidget(_cat_label("Report Type"))
        lay.addWidget(self._build_type_cards())
        self._subtype_chips = _SubtypeChips()
        lay.addWidget(self._subtype_chips)
        lay.addWidget(_hdivider())

        # Template
        lay.addWidget(_cat_label("Template"))
        lay.addWidget(self._build_template_selector())
        lay.addWidget(_hdivider())

        # Sample selection
        lay.addWidget(_cat_label("Samples"))
        lay.addWidget(self._build_sample_section())
        lay.addWidget(_hdivider())

        # Sections
        lay.addWidget(_cat_label("Sections"))
        for w in self._build_section_checks():
            lay.addWidget(w)
        lay.addWidget(_hdivider())

        # Branding
        lay.addWidget(_cat_label("Branding"))
        for w in self._build_branding_widgets():
            if isinstance(w, QHBoxLayout):
                lay.addLayout(w)
            else:
                lay.addWidget(w)
        lay.addWidget(_hdivider())

        # Report info
        lay.addWidget(_cat_label("Report Info"))
        for w in self._build_metadata_widgets():
            lay.addWidget(w)
        lay.addWidget(_hdivider())

        # Notes
        lay.addWidget(_cat_label("Notes"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Additional observations or notes…")
        self.notes_edit.setMaximumHeight(72)
        lay.addWidget(self.notes_edit)

        lay.addSpacing(8)

        # Generate button
        self.generate_btn = QPushButton("Generate Report")
        self.generate_btn.setMinimumHeight(36)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.OLIVE};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-family: "{F.UI}";
                font-size: {F.SZ_LG}pt;
                font-weight: 600;
            }}
            QPushButton:hover   {{ background: {C.OLIVE_H}; }}
            QPushButton:pressed {{ background: {C.OLIVE_DK}; }}
            QPushButton:disabled {{
                background: {C.BORDER};
                color: {C.TEXT_MUTED};
            }}
        """)
        self.generate_btn.clicked.connect(self._on_generate)
        self.generate_btn.setEnabled(False)
        lay.addWidget(self.generate_btn)
        lay.addStretch()

        scroll.setWidget(inner)
        return scroll

    def _build_type_cards(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self._card_group = QButtonGroup(self)
        self._card_group.setExclusive(True)

        for i, (icon_ch, label) in enumerate([
            ("◉", "Individual"),
            ("◎", "Comparison"),
            ("⊕", "Full Project"),
        ]):
            card = _TypeCard(icon_ch, label)
            self._card_group.addButton(card, i)
            lay.addWidget(card)

        self._card_group.button(0).setChecked(True)
        self._card_group.idToggled.connect(self._on_type_changed)
        return w

    def _build_sample_section(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.sample_combo = QComboBox()
        self.sample_combo.addItem("No samples loaded")
        lay.addWidget(self.sample_combo)

        self.sample_checks_widget = QWidget()
        self.sample_checks_layout = QVBoxLayout(self.sample_checks_widget)
        self.sample_checks_layout.setContentsMargins(0, 0, 0, 0)
        self.sample_checks_layout.setSpacing(2)
        self.sample_checks_widget.setVisible(False)
        lay.addWidget(self.sample_checks_widget)

        return w

    def _build_template_selector(self) -> QComboBox:
        combo = QComboBox()
        combo.addItems(["Standard", "Executive", "Technical", "Appendix"])
        combo.setStyleSheet(f"""
            QComboBox {{
                font-family: "{F.UI}";
                font-size: {F.SZ_BASE}pt;
                color: {C.TEXT};
                background: white;
                border: 1px solid {C.BORDER};
                border-radius: 3px;
                padding: 3px 6px;
            }}
            QComboBox:focus {{ border-color: {C.OLIVE}; }}
            QComboBox QAbstractItemView {{
                background: white;
                border: 1px solid {C.BORDER};
                selection-background-color: rgba(107,142,35,0.12);
                selection-color: {C.TEXT};
            }}
        """)
        combo.currentTextChanged.connect(self._apply_template)
        self._template_combo = combo
        return combo

    def _apply_template(self, name: str):
        """Set section checkboxes according to the named template."""
        if not hasattr(self, "s_cover"):
            return  # section checkboxes not yet built
        templates = {
            "Standard": {
                "cover": False, "executive": True,  "methodology": True,
                "results": True, "plots": True,      "interp": True,
                "percentiles": True, "gradation": True, "k_stats": True,
                "quality": False, "raw": False,
            },
            "Executive": {
                "cover": True,  "executive": True,  "methodology": False,
                "results": True, "plots": True,      "interp": True,
                "percentiles": False, "gradation": True, "k_stats": False,
                "quality": False, "raw": False,
            },
            "Technical": {
                "cover": False, "executive": False, "methodology": True,
                "results": True, "plots": True,      "interp": True,
                "percentiles": True, "gradation": True, "k_stats": True,
                "quality": True, "raw": True,
            },
            "Appendix": {
                "cover": False, "executive": False, "methodology": False,
                "results": False, "plots": False,    "interp": False,
                "percentiles": True, "gradation": True, "k_stats": True,
                "quality": True, "raw": True,
            },
        }
        cfg = templates.get(name)
        if cfg is None:
            return
        self.s_cover.setChecked(cfg["cover"])
        self.s_executive.setChecked(cfg["executive"])
        self.s_methodology.setChecked(cfg["methodology"])
        self.s_results.setChecked(cfg["results"])
        self.s_plots.setChecked(cfg["plots"])
        self.s_interp.setChecked(cfg["interp"])
        self.s_percentiles.setChecked(cfg["percentiles"])
        self.s_gradation.setChecked(cfg["gradation"])
        self.s_k_stats.setChecked(cfg["k_stats"])
        self.s_quality.setChecked(cfg["quality"])
        self.s_raw.setChecked(cfg["raw"])

    def _build_section_checks(self) -> list:
        cb_style = f"""
            QCheckBox {{
                font-family: "{F.UI}";
                font-size: {F.SZ_BASE}pt;
                color: {C.TEXT};
                spacing: 6px;
                padding: 1px 0;
            }}
            QCheckBox::indicator {{ width: 13px; height: 13px; }}
        """
        sub_style = f"""
            QLabel {{
                font-family: "{F.UI}";
                font-size: {F.SZ_XS}pt;
                color: {C.TEXT_MUTED};
                padding: 5px 0 1px 0;
            }}
        """

        def cb(label, checked=True):
            c = QCheckBox(label)
            c.setChecked(checked)
            c.setStyleSheet(cb_style)
            return c

        self.s_cover        = cb("Cover Page", False)
        self.s_executive    = cb("Executive Summary")
        self.s_methodology  = cb("Methodology")
        self.s_results      = cb("Results & Analysis")
        self.s_plots        = cb("Charts & Plots")
        self.s_interp       = cb("Interpretation")

        sub_lbl = QLabel("Data details")
        sub_lbl.setStyleSheet(sub_style)

        self.s_percentiles  = cb("Percentile Table")
        self.s_gradation    = cb("Gradation Analysis")
        self.s_k_stats      = cb("K-Value Statistics")
        self.s_quality      = cb("Data Quality", False)
        self.s_raw          = cb("Raw Data Tables", False)

        return [
            self.s_cover,
            self.s_executive, self.s_methodology, self.s_results,
            self.s_plots, self.s_interp,
            sub_lbl,
            self.s_percentiles, self.s_gradation, self.s_k_stats,
            self.s_quality, self.s_raw,
        ]

    def _build_branding_widgets(self) -> list:
        self.org_name_edit    = _line_edit()
        self.org_name_edit.setText(self.brand.org_name)
        self.org_subtitle_edit = _line_edit()
        self.org_subtitle_edit.setText(self.brand.org_subtitle)

        # Color + logo row
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 0)
        row.setSpacing(6)

        self._color_swatch = _ColorSwatch(self.brand.primary_color)
        self._color_swatch.clicked.connect(self._pick_color)

        logo_btn = QPushButton("Choose logo…")
        logo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logo_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.BG_RAISED};
                border: 1px solid {C.BORDER};
                border-radius: 3px;
                padding: 4px 8px;
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                color: {C.TEXT_MID};
            }}
            QPushButton:hover {{ border-color: {C.OLIVE}; color: {C.TEXT}; }}
        """)
        logo_btn.clicked.connect(self._pick_logo)

        clr_lbl = _field_label("Brand color")
        row.addWidget(clr_lbl)
        row.addWidget(self._color_swatch)
        row.addStretch()
        row.addWidget(logo_btn)

        self._logo_status = QLabel()
        self._logo_status.setFixedHeight(20)
        self._refresh_logo_status()

        return [
            _field_label("Organization"),
            self.org_name_edit,
            _field_label("Department / Group"),
            self.org_subtitle_edit,
            row,
            self._logo_status,
        ]

    def _build_metadata_widgets(self) -> list:
        fields = [
            ("project_name_edit", "Project",  "e.g., Site Investigation 2024"),
            ("location_edit",     "Location", "e.g., Copenhagen, Denmark"),
            ("client_edit",       "Client",   "e.g., ABC Engineering"),
            ("analyst_edit",      "Analyst",  "e.g., J. Doe"),
        ]
        widgets = []
        for attr, label, ph in fields:
            widgets.append(_field_label(label))
            edit = _line_edit(ph)
            setattr(self, attr, edit)
            widgets.append(edit)
        return widgets

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {C.BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._build_preview_area(), 1)
        lay.addWidget(_hdivider())
        lay.addWidget(self._build_export_bar())
        return w

    def _build_preview_area(self) -> QWidget:
        """Gray surround containing the HTML preview."""
        surround = QWidget()
        surround.setStyleSheet("background: #d0cbc2;")
        lay = QVBoxLayout(surround)
        lay.setContentsMargins(24, 20, 24, 20)

        if HAS_WEBENGINE:
            self.web_view = QWebEngineView()
            self.web_view.setStyleSheet("background: white; border: none;")
            self.web_view.setHtml(self._empty_preview_html())
            # Connect PDF signal once
            self.web_view.page().pdfPrintingFinished.connect(self._on_pdf_done)
            lay.addWidget(self.web_view)
        else:
            self.web_view = QTextEdit()
            self.web_view.setReadOnly(True)
            self.web_view.setHtml(self._empty_preview_html())
            lay.addWidget(self.web_view)

            warn = QLabel("PyQt6-WebEngine not installed — PDF export unavailable.")
            warn.setStyleSheet(
                f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; "
                f"font-family: '{F.UI}'; padding: 4px; background: transparent;"
            )
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(warn)

        return surround

    def _build_export_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background: {C.BG_RAISED};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)

        btn_style = f"""
            QPushButton {{
                background: {C.BG};
                color: {C.TEXT_MID};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 5px 14px;
                font-family: "{F.UI}";
                font-size: {F.SZ_BASE}pt;
            }}
            QPushButton:hover    {{ border-color: {C.OLIVE}; color: {C.TEXT}; }}
            QPushButton:disabled {{ color: {C.TEXT_MUTED}; border-color: {C.BORDER}; }}
        """

        self.btn_html  = QPushButton("Export HTML")
        self.btn_pdf   = QPushButton("Export PDF")
        self.btn_md    = QPushButton("Export Markdown")
        self.btn_docx  = QPushButton("Export Word (.docx)")

        for btn in [self.btn_html, self.btn_pdf, self.btn_md, self.btn_docx]:
            btn.setStyleSheet(btn_style)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setEnabled(False)
            lay.addWidget(btn)

        lay.addStretch()

        self.btn_html.clicked.connect(self._on_export_html)
        self.btn_pdf.clicked.connect(self._on_export_pdf)
        self.btn_md.clicked.connect(self._on_export_md)
        self.btn_docx.clicked.connect(self._on_export_docx)

        return bar

    # ── Data wiring ───────────────────────────────────────────────────────────

    def set_scheme(self, scheme) -> None:
        """Set the active classification scheme used for all generated reports."""
        self._scheme = scheme
        self.report_generator.set_scheme(scheme)

    def set_dataset_tabs(self, dataset_tabs: List):
        self.dataset_tabs = dataset_tabs
        self._refresh_sample_list()

    @staticmethod
    def _build_unique_labels(names: List[str]) -> List[str]:
        totals: dict[str, int] = {}
        for name in names:
            totals[name] = totals.get(name, 0) + 1

        seen: dict[str, int] = {}
        labels: list[str] = []
        for name in names:
            seen[name] = seen.get(name, 0) + 1
            if totals[name] > 1:
                labels.append(f"{name} ({seen[name]})")
            else:
                labels.append(name)
        return labels

    def _set_preview_html(self, html: str) -> None:
        self.web_view.setHtml(html)

    def _set_report_output(self, report_html: str) -> None:
        self.current_report_html = report_html
        self._set_preview_html(self._inject_preview_css(report_html))
        self.btn_html.setEnabled(True)
        self.btn_pdf.setEnabled(HAS_WEBENGINE)

    def _clear_report_output(self, message: str | None = None) -> None:
        self.current_report_html = ""
        self.btn_html.setEnabled(False)
        self.btn_pdf.setEnabled(False)
        self.btn_md.setEnabled(False)
        self.btn_docx.setEnabled(False)
        if message:
            self._set_preview_html(self._error_preview_html(message))
        else:
            self._set_preview_html(self._empty_preview_html())

    @staticmethod
    def _error_preview_html(message: str) -> str:
        safe = escape(message)
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
  body {{
    font-family: 'Calibri', Arial, sans-serif;
    background: white;
    margin: 0;
    padding: 60px 50px;
    color: #6a6a6a;
  }}
  .center {{ text-align: center; padding-top: 80px; }}
  h2 {{ font-weight: 400; font-size: 22px; margin-bottom: 12px; color: #7b2e2e; }}
  p  {{ font-size: 13px; line-height: 1.5; }}
  strong {{ color: #6b8e23; }}
  .msg {{
    margin: 18px auto 0;
    max-width: 520px;
    padding: 14px 16px;
    background: #faf7f4;
    border: 1px solid #ddd4ca;
    text-align: left;
    white-space: pre-wrap;
  }}
</style></head>
<body>
  <div class="center">
    <h2>Report Generation Failed</h2>
    <p>The preview was cleared so stale content cannot be exported.</p>
    <div class="msg">{safe}</div>
  </div>
</body></html>"""

    def _selected_sample_contexts(self) -> list[dict]:
        selected: list[dict] = []
        for checkbox, context in self._sample_checkboxes:
            if checkbox.isChecked():
                selected.append(context)
        return selected

    def _refresh_sample_list(self):
        self.sample_combo.clear()
        self._sample_contexts = []
        self._sample_checkboxes = []
        self._clear_report_output()
        while self.sample_checks_layout.count():
            item = self.sample_checks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.dataset_tabs:
            self.sample_combo.addItem("No samples loaded")
            self.generate_btn.setEnabled(False)
            return

        labels = self._build_unique_labels([tab.get_dataset_name() for tab in self.dataset_tabs])
        for tab, label in zip(self.dataset_tabs, labels):
            context = {"label": label, "tab": tab}
            self._sample_contexts.append(context)
            self.sample_combo.addItem(label)
            cb = QCheckBox(label)
            cb.setChecked(True)
            self.sample_checks_layout.addWidget(cb)
            self._sample_checkboxes.append((cb, context))

        self.generate_btn.setEnabled(True)

    # ── Slot handlers ─────────────────────────────────────────────────────────

    def _on_type_changed(self, btn_id: int, checked: bool):
        if not checked:
            return
        is_individual = (btn_id == 0)
        self._subtype_chips.setVisible(is_individual)
        self.sample_combo.setVisible(is_individual)
        self.sample_checks_widget.setVisible(not is_individual)

    def _pick_color(self):
        dlg = QColorDialog(QColor(self._color_swatch.color()), self)
        if dlg.exec():
            self._color_swatch.set_color(dlg.selectedColor().name())
            self._sync_brand()

    def _pick_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo Image", "",
            "Images (*.png *.jpg *.jpeg *.svg)"
        )
        if path:
            self.brand.logo_path = path
            self._refresh_logo_status()
            self._sync_brand()

    def _refresh_logo_status(self):
        if self.brand.logo_path and os.path.exists(self.brand.logo_path):
            fname = os.path.basename(self.brand.logo_path)
            self._logo_status.setText(f"✓ {fname}")
            self._logo_status.setStyleSheet(
                f"color: {C.OLIVE_DK}; font-size: {F.SZ_SM}pt; "
                f"font-family: '{F.UI}'; background: transparent;"
            )
        else:
            self._logo_status.setText("Auto-generated placeholder")
            self._logo_status.setStyleSheet(
                f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; "
                f"font-style: italic; background: transparent;"
            )

    def _sync_brand(self):
        """Push current UI values into brand and persist."""
        self.brand.org_name      = self.org_name_edit.text()
        self.brand.org_subtitle  = self.org_subtitle_edit.text()
        self.brand.primary_color = self._color_swatch.color()
        self.brand.save()

    # ── Data collection ───────────────────────────────────────────────────────

    def _collect_brand(self) -> ReportBrand:
        self._sync_brand()
        return self.brand

    def _collect_metadata(self) -> dict:
        return {
            "project_name": self.project_name_edit.text(),
            "location":     self.location_edit.text(),
            "client":       self.client_edit.text(),
            "analyst":      self.analyst_edit.text(),
            "notes":        self.notes_edit.toPlainText(),
        }

    def _collect_sections(self) -> dict:
        return {
            "cover_page":        self.s_cover.isChecked(),
            "executive_summary": self.s_executive.isChecked(),
            "methodology":       self.s_methodology.isChecked(),
            "results":           self.s_results.isChecked(),
            "plots":             self.s_plots.isChecked(),
            "interpretation":    self.s_interp.isChecked(),
            "percentiles":       self.s_percentiles.isChecked(),
            "gradation":         self.s_gradation.isChecked(),
            "k_statistics":      self.s_k_stats.isChecked(),
            "data_quality":      self.s_quality.isChecked(),
            "raw_data":          self.s_raw.isChecked(),
        }

    # ── Report generation ─────────────────────────────────────────────────────

    def _on_generate(self):
        if not self.dataset_tabs:
            QMessageBox.warning(self, "No Data", "Please load datasets first.")
            return

        brand    = self._collect_brand()
        metadata = self._collect_metadata()
        sections = self._collect_sections()

        try:
            type_id = self._card_group.checkedId()
            if type_id == 0:
                html = self._gen_individual(brand, metadata, sections)
            elif type_id == 1:
                html = self._gen_comparison(brand, metadata, sections)
            else:
                html = self._gen_full(brand, metadata, sections)

            self._set_report_output(html)

        except Exception as exc:
            self._clear_report_output(str(exc))
            QMessageBox.critical(self, "Report Error",
                                 f"Failed to generate report:\n{exc}")

    def _gen_individual(self, brand, metadata, sections) -> str:
        idx = self.sample_combo.currentIndex()
        if idx < 0 or idx >= len(self._sample_contexts):
            raise ValueError("No sample selected.")
        context = self._sample_contexts[idx]
        tab     = context["tab"]
        dataset = tab.get_dataset()
        subtype = self._subtype_chips.selected()

        if subtype == "K-Values":
            return self.report_generator.generate_k_value_report(
                dataset, tab.get_results(), tab.temperature, tab.porosity,
                metadata=metadata, sections=sections, brand=brand,
            )
        elif subtype == "Combined":
            return self.report_generator.generate_combined_report(
                dataset, tab.get_results(), tab.temperature, tab.porosity,
                metadata=metadata, sections=sections, brand=brand,
            )
        else:
            return self.report_generator.generate_grain_size_report(
                dataset, metadata=metadata, sections=sections, brand=brand,
            )

    def _gen_comparison(self, brand, metadata, sections) -> str:
        selected = self._selected_sample_contexts()
        if not selected:
            raise ValueError("Select at least one sample.")

        sample_details = []
        for context in selected:
            tab = context["tab"]
            sample_details.append({
                "label": context["label"],
                "dataset": tab.get_dataset(),
                "k_results": list(tab.get_results() or []),
                "temperature": tab.temperature,
                "porosity": tab.porosity,
            })

        return self.report_generator.generate_comparison_report(
            [item["dataset"] for item in sample_details],
            metadata=metadata,
            sections=sections,
            brand=brand,
            sample_details=sample_details,
        )

    def _gen_full(self, brand, metadata, sections) -> str:
        if not self._sample_contexts:
            raise ValueError("No samples loaded.")

        sample_details = []
        for context in self._sample_contexts:
            tab = context["tab"]
            sample_details.append({
                "label": context["label"],
                "dataset": tab.get_dataset(),
                "k_results": list(tab.get_results() or []),
                "temperature": tab.temperature,
                "porosity": tab.porosity,
            })

        return self.report_generator.generate_comparison_report(
            [item["dataset"] for item in sample_details],
            metadata=metadata, sections=sections, brand=brand,
            sample_details=sample_details,
        )

    # ── Export ────────────────────────────────────────────────────────────────

    def _on_export_html(self):
        if not self.current_report_html:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export HTML", "report.html", "HTML (*.html)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.current_report_html)
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    def _on_export_pdf(self):
        if not self.current_report_html or not HAS_WEBENGINE:
            return

        default = "report.pdf"
        proj = self.project_name_edit.text()
        if proj:
            safe = "".join(c for c in proj if c.isalnum() or c in " -_").strip()
            default = f"{safe}_report.pdf"

        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", default, "PDF (*.pdf)"
        )
        if path:
            try:
                layout = QPageLayout(
                    QPageSize(QPageSize.PageSizeId.A4),
                    QPageLayout.Orientation.Portrait,
                    QMarginsF(0, 0, 0, 0),
                )
                self.web_view.page().printToPdf(path, layout)
            except Exception as exc:
                QMessageBox.critical(self, "PDF Error",
                                     f"Failed to export PDF:\n{exc}")

    def _on_pdf_done(self, path: str, success: bool):
        if success:
            QMessageBox.information(self, "Exported", f"PDF saved to:\n{path}")
        else:
            QMessageBox.critical(self, "Export Error", "PDF export failed.")

    def _on_export_md(self):
        QMessageBox.information(
            self, "Coming Soon",
            "Markdown export will be available in a future update."
        )

    def _on_export_docx(self):
        QMessageBox.information(
            self, "Coming Soon",
            "Word (.docx) export will be available in a future update."
        )

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _inject_preview_css(html: str) -> str:
        """Inject screen-only CSS + JS that simulates an A4 paper sheet with Word-style
        page-break gaps in the WebEngine preview. Separators are in the document flow
        (not positioned overlays) so content is never obscured. Not in PDF export."""
        screen_block = """<style>
@media screen {
    html { background: #c8c4be !important; min-height: 100%; padding: 32px 0 48px 0; }
    body {
        box-shadow: 0 4px 28px rgba(0,0,0,0.22), 0 1.5px 6px rgba(0,0,0,0.10) !important;
        background: white !important;
        min-height: 297mm;
        width: 210mm;
        max-width: 210mm !important;
        margin: 0 auto !important;
        padding: 0 20mm !important;
        box-sizing: border-box !important;
    }
    .report-top-bar {
        margin: 0 -20mm 40px -20mm !important;
    }
    /* Flow-based page separator — bleeds to paper edges via negative margins */
    .preview-page-sep {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 40px;
        /* negative margins = body padding, so separator spans full paper width */
        margin: 0 -20mm;
        background: #c8c4be;
        border-top:    1px solid #b0aba5;
        border-bottom: 1px solid #b0aba5;
        box-shadow: inset 0 4px 8px rgba(0,0,0,0.07),
                    inset 0 -4px 8px rgba(0,0,0,0.07);
        font-family: sans-serif;
        font-size: 9px;
        color: #9a9590;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
}
</style>
<script>
(function () {
    /*
     * A4 @ 96 dpi: content height = (297 - 20 - 25) mm * (96/25.4) ≈ 952 px
     * Strategy: snapshot all direct body-children offsetTops BEFORE any insertion,
     * then insert flow-block separators in document order so later elements are
     * physically pushed down — never overlaid.
     */
    var PAGE_PX = 252 * 96 / 25.4;

    function isBreakCandidate(el) {
        if (!el || el.classList.contains('preview-page-sep')) return false;
        if (el.closest('table, thead, tbody, tr, td, th, ul, ol, li')) return false;
        var style = window.getComputedStyle(el);
        if (style.display === 'none' || style.position === 'fixed') return false;
        if (el.offsetHeight < 12) return false;
        return /^(H1|H2|H3|H4|P|DIV|HR|IMG|FIGURE|TABLE)$/.test(el.tagName);
    }

    function collectBreakCandidates() {
        var bodyTop = document.body.getBoundingClientRect().top;
        var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
        var candidates = [];

        while (walker.nextNode()) {
            var el = walker.currentNode;
            if (!isBreakCandidate(el)) continue;
            candidates.push({
                el: el,
                top: el.getBoundingClientRect().top - bodyTop
            });
        }

        candidates.sort(function (a, b) { return a.top - b.top; });
        return candidates;
    }

    function injectPageBreaks() {
        if (document.querySelector('.preview-page-sep')) return;

        var candidates = collectBreakCandidates();
        var bodyH = document.body.scrollHeight;
        var page = 1;
        var usedTargets = new Set();

        for (var boundary = PAGE_PX; boundary < bodyH; boundary += PAGE_PX) {
            var target = null;
            for (var i = 0; i < candidates.length; i++) {
                if (candidates[i].top >= boundary && !usedTargets.has(candidates[i].el)) {
                    target = candidates[i].el;
                    break;
                }
            }
            if (!target) continue;

            usedTargets.add(target);
            var sep = document.createElement('div');
            sep.className = 'preview-page-sep';
            sep.textContent = 'Page ' + (++page);
            target.insertAdjacentElement('beforebegin', sep);
        }
    }

    if (document.readyState === 'complete') { injectPageBreaks(); }
    else { window.addEventListener('load', injectPageBreaks); }
})();
</script>"""
        if "</head>" in html:
            return html.replace("</head>", screen_block + "\n</head>", 1)
        return screen_block + html

    @staticmethod
    def _empty_preview_html() -> str:
        return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
  body {
    font-family: 'Calibri', Arial, sans-serif;
    background: white;
    margin: 0;
    padding: 60px 50px;
    color: #aaa;
  }
  .center { text-align: center; padding-top: 80px; }
  h2 { font-weight: 300; font-size: 22px; margin-bottom: 12px; }
  p  { font-size: 13px; }
  strong { color: #6b8e23; }
</style></head>
<body>
  <div class="center">
    <h2>No Report Generated</h2>
    <p>
      Configure options on the left, then click
      <strong>Generate Report</strong>.
    </p>
  </div>
</body></html>"""

