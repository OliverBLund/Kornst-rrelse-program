"""
Report generator for creating professional analysis reports
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
import importlib.util
import numpy as np
from datetime import datetime
import base64
import io
import os
import re
from data_loader import GrainSizeData
from analysis.comparison_snapshot import (
    ComparisonSnapshotOptions,
    DatasetAnalysisInput,
    build_comparison_snapshot,
)
from k_calculations import KCalculationResult
from k_aggregation import (
    KAggregationOptions,
    UNGROUPED_LABEL,
    build_k_result_summary,
    k_scope_value_series,
)
from grain_classification import (
    ISO14688,
    cu_label as _gc_cu_label,
    permeability_class as _gc_perm_class,
    cc_label as _gc_cc_label,
)
from gui.plot_constants import DATASET_COLORS, classify_k_status


def _get_plot_export():
    """Lazy import to avoid circular dependency (plot_export -> gui -> report_generator)."""
    import plot_export as _pe
    return _pe
from report_model import (
    AppendixLabelConfig,
    HeadingBlock,
    HtmlBlock,
    ImageBlock,
    PageBreakBlock,
    ParagraphBlock,
    ReportDocument,
    ReportSection,
    TableBlock,
)


DOCX_AVAILABLE = importlib.util.find_spec("docx") is not None


@dataclass
class _HtmlNode:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Any] = field(default_factory=list)


class _HtmlTreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _HtmlNode("document")
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        node = _HtmlNode(tag, {key: value or "" for key, value in attrs})
        self._stack[-1].children.append(node)
        self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        node = _HtmlNode(tag, {key: value or "" for key, value in attrs})
        self._stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        while len(self._stack) > 1:
            node = self._stack.pop()
            if node.tag == tag:
                break

    def handle_data(self, data: str) -> None:
        if data:
            self._stack[-1].children.append(data)


class ReportGenerator:
    """
    Generates professional reports for grain size analysis and K-value calculations
    """

    def __init__(self):
        self._scheme = ISO14688  # Active classification scheme; set via set_scheme()

        # Brand-aware professional report stylesheet.
        # --brand is the single color token; _get_branded_style() overrides it.
        self.report_style = """
        <style>
            :root {
                --brand:       #2c3e50;
                --brand-light: rgba(44,62,80,0.08);
                --text:        #1a1a1a;
                --text-mid:    #444444;
                --text-muted:  #6c757d;
                --border:      #d0d0d0;
                --bg:          #ffffff;
                --bg-alt:      #f7f7f7;
            }

            * { box-sizing: border-box; margin: 0; padding: 0; }

            @page {
                size: A4;
                margin: 20mm 20mm 25mm 20mm;
            }

            @media print {
                body { margin: 0; padding: 0; max-width: none; }
                .page-break { page-break-before: always; }
                .no-break   { page-break-inside: avoid; }
                h1, h2, h3  { page-break-after: avoid; }
                table       { page-break-inside: avoid; }
                .page-header { display: flex !important; }
                .report-top-bar { display: none; }
            }

            body {
                font-family: 'Calibri', 'Georgia', serif;
                line-height: 1.55;
                color: var(--text);
                background: var(--bg);
                max-width: 820px;
                margin: 0 auto;
                padding: 0 50px 60px 50px;
                font-size: 10.5pt;
            }

            /* ── Branded top bar — bleeds to body edges ──────── */
            .report-top-bar {
                height: 6px;
                background: var(--brand);
                margin: 0 -50px 40px -50px;
            }

            /* ── Cover page — bleeds to body edges ───────────── */
            .cover-page {
                padding: 50px 0 48px;
                min-height: 560px;
                display: flex;
                flex-direction: column;
                border-bottom: 1px solid var(--border);
                margin-bottom: 40px;
            }

            .cover-brand-block {
                margin-bottom: 64px;
            }

            .cover-title {
                font-size: 34px;
                font-weight: 700;
                color: var(--brand);
                margin-bottom: 10px;
                letter-spacing: -0.5px;
                line-height: 1.15;
            }

            .cover-subtitle {
                font-size: 15px;
                color: var(--text-mid);
                font-weight: 400;
                margin-bottom: 0;
            }

            .cover-meta {
                margin-top: auto;
                font-size: 10pt;
                color: var(--text-mid);
                line-height: 2;
                border-top: 1px solid var(--border);
                padding-top: 18px;
            }

            /* ── Typography ──────────────────────────────────── */
            h1 {
                font-size: 20pt;
                font-weight: 700;
                color: var(--text);
                margin: 0 0 8px 0;
                padding-bottom: 10px;
                border-bottom: 3px solid var(--brand);
            }

            h2 {
                font-size: 13pt;
                font-weight: 700;
                color: var(--brand);
                margin: 32px 0 12px 0;
                padding-bottom: 5px;
                border-bottom: 1px solid var(--border);
            }

            h3 {
                font-size: 11pt;
                font-weight: 700;
                color: var(--text);
                margin: 20px 0 8px 0;
            }

            h4 {
                font-size: 10.5pt;
                font-weight: 600;
                color: var(--text-mid);
                margin: 14px 0 6px 0;
            }

            p { margin: 8px 0; line-height: 1.55; }

            /* ── Stat cards ───────────────────────────────────── */
            .summary-stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                gap: 12px;
                margin: 20px 0;
            }

            .stat-card {
                background: var(--bg);
                padding: 14px 12px 10px;
                border: 1px solid var(--border);
                border-top: 3px solid var(--brand);
                text-align: center;
            }

            .stat-label {
                font-size: 8.5pt;
                color: var(--text-muted);
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 6px;
            }

            .stat-value {
                font-size: 19pt;
                font-weight: 700;
                color: var(--brand);
                line-height: 1.1;
            }

            .stat-unit {
                font-size: 8.5pt;
                color: var(--text-muted);
                margin-top: 3px;
            }

            /* ── Tables ───────────────────────────────────────── */
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 14px 0;
                font-size: 9.5pt;
                background: var(--bg);
            }

            thead { background: var(--brand); }

            th {
                color: white;
                padding: 8px 10px;
                text-align: left;
                font-weight: 600;
                font-size: 9pt;
                letter-spacing: 0.3px;
            }

            td {
                padding: 6px 10px;
                border-bottom: 1px solid var(--border);
                vertical-align: top;
                color: var(--text);
            }

            tr:nth-child(even) td { background: var(--bg-alt); }
            tbody tr:last-child td { border-bottom: 2px solid var(--brand); }

            .table-compact th { padding: 5px 8px; font-size: 8.5pt; }
            .table-compact td { padding: 4px 8px; }
            .table-wide {
                table-layout: fixed;
                font-size: 8pt;
            }
            .table-wide th,
            .table-wide td {
                padding: 4px 5px;
                overflow-wrap: anywhere;
                word-break: break-word;
            }
            .table-wide th:first-child,
            .table-wide td:first-child {
                width: 16%;
            }
            .table-wide th:last-child,
            .table-wide td:last-child {
                width: 16%;
            }

            /* ── Metadata box ─────────────────────────────────── */
            .metadata {
                background: var(--bg-alt);
                border: 1px solid var(--border);
                border-left: 3px solid var(--brand);
                padding: 14px 16px;
                margin: 18px 0;
                font-size: 9.5pt;
            }

            .metadata-grid {
                display: grid;
                grid-template-columns: 140px 1fr;
                gap: 6px 12px;
                line-height: 1.6;
            }

            .metadata-label { font-weight: 700; color: var(--text-mid); }
            .metadata-value { color: var(--text); }

            /* ── Info / status boxes ──────────────────────────── */
            .info-box {
                background: var(--bg-alt);
                border: 1px solid var(--border);
                border-left: 3px solid var(--brand);
                padding: 12px 14px;
                margin: 12px 0;
            }

            .info-box h3 { margin-top: 0; font-size: 10pt; color: var(--brand); }
            .info-box p  { margin: 4px 0; }

            .warning-box {
                background: #fffbf0;
                border: 1px solid #e6c200;
                border-left: 3px solid #e6a200;
                padding: 12px 14px;
                margin: 12px 0;
            }

            .success-box {
                background: #f4f9f4;
                border: 1px solid #85c285;
                border-left: 3px solid #4caf50;
                padding: 12px 14px;
                margin: 12px 0;
            }

            .error-box {
                background: #fff4f4;
                border: 1px solid #e08080;
                border-left: 3px solid #cc3333;
                padding: 12px 14px;
                margin: 12px 0;
            }

            /* ── Plots ────────────────────────────────────────── */
            .plot-container {
                text-align: center;
                margin: 20px 0;
                padding: 12px;
                background: var(--bg);
                border: 1px solid var(--border);
            }

            .plot-container img { max-width: 100%; height: auto; }

            .figure-caption {
                font-size: 9pt;
                color: var(--text-muted);
                font-style: italic;
                margin-top: 8px;
            }

            /* ── Appendix ─────────────────────────────────────── */
            .appendix-section {
                margin-top: 48px;
                padding-top: 24px;
                border-top: 2px solid var(--brand);
            }

            .appendix-title {
                font-size: 20px;
                font-weight: 700;
                color: var(--brand);
                margin-bottom: 12px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            .appendix-item {
                margin: 24px 0;
                padding: 16px;
                background: var(--bg-alt);
                border-left: 3px solid var(--brand);
            }

            .appendix-item-title {
                font-size: 10pt;
                font-weight: 700;
                color: var(--brand);
                margin-bottom: 10px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .appendix-subsection {
                margin-top: 18px;
            }

            .appendix-subtitle {
                margin: 0 0 10px 0;
                color: var(--text);
                font-size: 12pt;
                font-weight: 700;
            }

            /* ── Footer ───────────────────────────────────────── */
            .footer {
                margin-top: 56px;
                padding-top: 12px;
                border-top: 2px solid var(--brand);
                display: flex;
                justify-content: space-between;
                color: var(--text-muted);
                font-size: 8.5pt;
                line-height: 1.6;
            }

            /* ── Page header (print only) ─────────────────────── */
            .page-header {
                display: none;
                font-size: 8.5pt;
                color: var(--text-muted);
                padding-bottom: 8px;
                border-bottom: 1px solid var(--border);
                margin-bottom: 16px;
                justify-content: space-between;
            }

            /* ── Dividers ─────────────────────────────────────── */
            .section-divider, hr {
                border: none;
                height: 1px;
                background: var(--border);
                margin: 28px 0;
            }

            /* ── Lists ────────────────────────────────────────── */
            ul, ol { margin: 10px 0; padding-left: 22px; }
            li { margin: 4px 0; line-height: 1.55; }

            /* ── Badges ───────────────────────────────────────── */
            .badge {
                display: inline-block;
                padding: 2px 8px;
                font-size: 8.5pt;
                font-weight: 600;
                border-radius: 2px;
                background: var(--brand-light);
                color: var(--brand);
                border: 1px solid var(--brand);
            }

            .badge-success  { background: #edf7ed; color: #2a7a2a; border-color: #4caf50; }
            .badge-warning  { background: #fffbf0; color: #8a6200; border-color: #e6a200; }
            .badge-danger   { background: #fff4f4; color: #aa2222; border-color: #cc3333; }
            .badge-info     { background: var(--brand-light); color: var(--brand); border-color: var(--brand); }
            .badge-secondary{ background: #f0f0f0; color: #666;   border-color: #ccc; }

            /* ── Utilities ────────────────────────────────────── */
            .text-center { text-align: center; }
            .text-right  { text-align: right; }
            .text-muted  { color: var(--text-muted); }
            .highlight   { background: #fff8cc; padding: 1px 4px; }
            strong, b    { font-weight: 700; }

            code {
                font-family: 'Courier New', monospace;
                background: var(--bg-alt);
                padding: 1px 5px;
                border-radius: 2px;
                font-size: 9pt;
            }
        </style>
        """

    def set_scheme(self, scheme) -> None:
        """Set the active classification scheme used for all generated reports."""
        self._scheme = scheme

    def _get_branded_style(self, brand=None) -> str:
        """Return report CSS with --brand CSS variable set to the brand color."""
        if brand is None:
            return self.report_style
        color = brand.primary_color
        # Compute a transparent tint for --brand-light
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            light = f"rgba({r},{g},{b},0.08)"
        except (ValueError, IndexError):
            light = "rgba(44,62,80,0.08)"
        return (
            self.report_style
            .replace("--brand:       #2c3e50;", f"--brand:       {color};")
            .replace("--brand-light: rgba(44,62,80,0.08);", f"--brand-light: {light};")
        )

    @staticmethod
    def _esc(value: Any) -> str:
        return escape("" if value is None else str(value), quote=True)

    @staticmethod
    def _effective_porosity_value(dataset: GrainSizeData) -> Optional[float]:
        if hasattr(dataset, "effective_porosity"):
            return dataset.effective_porosity()
        current = getattr(dataset, "current_porosity", None)
        if current is not None:
            return current
        calculated = getattr(dataset, "calculated_porosity", None)
        if calculated is not None:
            return calculated
        return getattr(dataset, "porosity", None)

    def _porosity_display(self, dataset: GrainSizeData, value: Optional[float] = None) -> str:
        porosity = self._effective_porosity_value(dataset) if value is None else value
        if porosity is None:
            return "N/A"
        try:
            return f"{float(porosity):.4f}"
        except (TypeError, ValueError):
            return self._esc(porosity)

    def _porosity_source_display(self, dataset: GrainSizeData) -> str:
        if hasattr(dataset, "porosity_source_label"):
            return dataset.porosity_source_label()
        return "Current dataset value"

    def _note_html(self, value: Any) -> str:
        return self._esc(value).replace("\n", "<br>")

    @staticmethod
    def _extract_body_contents(html_text: str) -> str:
        match = re.search(r"<body[^>]*>(.*)</body>", html_text, flags=re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else html_text.strip()

    @staticmethod
    def _strip_leading_report_markup(body_html: str) -> str:
        body_html = re.sub(r"^\s*<div class=\"report-top-bar\"></div>\s*", "", body_html, count=1, flags=re.DOTALL)
        body_html = re.sub(
            r"^\s*<h1>\s*Hydraulic Conductivity Analysis Report\s*</h1>\s*",
            "",
            body_html,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return body_html.strip()

    @staticmethod
    def _summarize_sample_field(sample_details: List[Dict[str, Any]], key: str, suffix: str = "") -> str:
        values = [item.get(key) for item in sample_details if item.get(key) is not None]
        if not values:
            return "N/A"
        try:
            numeric = [float(value) for value in values]
        except (TypeError, ValueError):
            unique = []
            for value in values:
                if value not in unique:
                    unique.append(value)
            if len(unique) == 1:
                return f"{unique[0]}{suffix}"
            return "Varies by sample"

        low = min(numeric)
        high = max(numeric)
        low_text = f"{low:.3f}".rstrip("0").rstrip(".")
        high_text = f"{high:.3f}".rstrip("0").rstrip(".")
        if abs(high - low) < 1e-9:
            return f"{low_text}{suffix}"
        return f"Varies by sample ({low_text} to {high_text}{suffix})"

    @staticmethod
    def _coerce_appendix_label_config(config: Optional[Any]) -> AppendixLabelConfig:
        if config is None:
            return AppendixLabelConfig()
        if isinstance(config, AppendixLabelConfig):
            return config
        if isinstance(config, dict):
            return AppendixLabelConfig(
                mode=config.get("mode", "auto"),
                scheme=config.get("scheme", "alpha"),
                layout=config.get("layout", "separate"),
                prefix=config.get("prefix", "Appendix "),
                alpha_numeric_root=config.get("alpha_numeric_root", "A"),
                single_label=config.get("single_label", ""),
                manual_labels=dict(config.get("manual_labels") or {}),
            )
        raise TypeError("appendix_label_config must be an AppendixLabelConfig or dict")

    @staticmethod
    def docx_export_available() -> bool:
        return DOCX_AVAILABLE

    @staticmethod
    def _node_classes(node: _HtmlNode) -> set[str]:
        return {name for name in node.attrs.get("class", "").split() if name}

    @staticmethod
    def _child_nodes(node: _HtmlNode) -> list[_HtmlNode]:
        return [child for child in node.children if isinstance(child, _HtmlNode)]

    @classmethod
    def _node_text(cls, node: _HtmlNode) -> str:
        parts: list[str] = []
        for child in node.children:
            if isinstance(child, str):
                parts.append(child)
            else:
                parts.append(cls._node_text(child))
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    @classmethod
    def _find_first_node(cls, node: _HtmlNode, tag: str) -> Optional[_HtmlNode]:
        if node.tag.lower() == tag.lower():
            return node
        for child in cls._child_nodes(node):
            match = cls._find_first_node(child, tag)
            if match is not None:
                return match
        return None

    @staticmethod
    def _parse_html_tree(html_text: str) -> _HtmlNode:
        parser = _HtmlTreeBuilder()
        parser.feed(html_text)
        parser.close()
        return parser.root

    @staticmethod
    def _hex_to_rgb_triplet(hex_color: str) -> tuple[int, int, int]:
        color = (hex_color or "#2c3e50").strip().lstrip("#")
        if len(color) == 3:
            color = "".join(ch * 2 for ch in color)
        if len(color) != 6:
            return (44, 62, 80)
        return tuple(int(color[i:i + 2], 16) for i in range(0, 6, 2))

    def _set_docx_heading_color(self, paragraph, brand_rgb: tuple[int, int, int], ctx: dict[str, Any]) -> None:
        rgb = ctx["RGBColor"](*brand_rgb)
        for run in paragraph.runs:
            run.font.color.rgb = rgb

    def _add_docx_paragraph(self, container, text: str, ctx: dict[str, Any],
                            *, bold: bool = False, align=None, style: Optional[str] = None) -> None:
        clean = re.sub(r"\s+", " ", text).strip()
        if not clean:
            return
        paragraph = container.add_paragraph(style=style)
        if align is not None:
            paragraph.alignment = align
        run = paragraph.add_run(clean)
        run.bold = bold
        paragraph.paragraph_format.space_after = ctx["Pt"](6)

    def _render_docx_metadata_grid(self, container, node: _HtmlNode,
                                   ctx: dict[str, Any], brand_rgb: tuple[int, int, int]) -> None:
        items: list[tuple[str, str]] = []
        pending_label = ""
        for child in self._child_nodes(node):
            text = self._node_text(child)
            if not text:
                continue
            classes = self._node_classes(child)
            if "metadata-label" in classes:
                pending_label = text
            elif "metadata-value" in classes and pending_label:
                items.append((pending_label, text))
                pending_label = ""

        if not items:
            return

        table = container.add_table(rows=len(items), cols=2)
        table.style = "Table Grid"
        table.alignment = ctx["WD_TABLE_ALIGNMENT"].LEFT
        for row_index, (label, value) in enumerate(items):
            label_para = table.cell(row_index, 0).paragraphs[0]
            label_run = label_para.add_run(label.rstrip(":"))
            label_run.bold = True
            label_run.font.color.rgb = ctx["RGBColor"](*brand_rgb)
            table.cell(row_index, 1).paragraphs[0].add_run(value)

    def _render_docx_summary_stats(self, container, node: _HtmlNode, ctx: dict[str, Any]) -> None:
        cards = [
            child for child in self._child_nodes(node)
            if "stat-card" in self._node_classes(child)
        ]
        if not cards:
            return

        table = container.add_table(rows=1, cols=len(cards))
        table.style = "Table Grid"
        table.alignment = ctx["WD_TABLE_ALIGNMENT"].CENTER
        for index, card in enumerate(cards):
            label = ""
            value = ""
            unit = ""
            for child in self._child_nodes(card):
                classes = self._node_classes(child)
                text = self._node_text(child)
                if "stat-label" in classes:
                    label = text
                elif "stat-value" in classes:
                    value = text
                elif "stat-unit" in classes:
                    unit = text

            cell = table.cell(0, index)
            cell_para = cell.paragraphs[0]
            cell_para.alignment = ctx["WD_ALIGN_PARAGRAPH"].CENTER
            label_run = cell_para.add_run(label)
            label_run.bold = True
            if value:
                value_para = cell.add_paragraph()
                value_para.alignment = ctx["WD_ALIGN_PARAGRAPH"].CENTER
                value_run = value_para.add_run(value)
                value_run.bold = True
                value_run.font.size = ctx["Pt"](13)
            if unit:
                unit_para = cell.add_paragraph()
                unit_para.alignment = ctx["WD_ALIGN_PARAGRAPH"].CENTER
                unit_para.add_run(unit)

    def _iter_table_rows(self, node: _HtmlNode) -> list[_HtmlNode]:
        rows: list[_HtmlNode] = []
        for child in self._child_nodes(node):
            tag = child.tag.lower()
            if tag == "tr":
                rows.append(child)
            elif tag in {"thead", "tbody", "tfoot"}:
                rows.extend(self._iter_table_rows(child))
        return rows

    def _apply_docx_header_shading(self, cell, fill_hex: str, ctx: dict[str, Any]) -> None:
        shading = ctx["parse_xml"](f'<w:shd {ctx["nsdecls"]("w")} w:fill="{fill_hex}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    def _render_docx_table(self, container, node: _HtmlNode,
                           ctx: dict[str, Any], brand_rgb: tuple[int, int, int]) -> None:
        rows = self._iter_table_rows(node)
        if not rows:
            return

        col_count = max(
            sum(1 for child in self._child_nodes(row) if child.tag.lower() in {"th", "td"})
            for row in rows
        )
        table = container.add_table(rows=len(rows), cols=col_count)
        table.style = "Table Grid"
        table.alignment = ctx["WD_TABLE_ALIGNMENT"].CENTER
        fill_hex = "".join(f"{value:02X}" for value in brand_rgb)

        for row_index, row_node in enumerate(rows):
            cells = [child for child in self._child_nodes(row_node) if child.tag.lower() in {"th", "td"}]
            for col_index, cell_node in enumerate(cells):
                cell = table.cell(row_index, col_index)
                paragraph = cell.paragraphs[0]
                text = self._node_text(cell_node)
                if text:
                    run = paragraph.add_run(text)
                    if cell_node.tag.lower() == "th":
                        run.bold = True
                if row_index == 0 and any(child.tag.lower() == "th" for child in cells):
                    self._apply_docx_header_shading(cell, fill_hex, ctx)
                    for run in paragraph.runs:
                        run.font.color.rgb = ctx["RGBColor"](255, 255, 255)

    def _render_docx_image(self, container, node: _HtmlNode, ctx: dict[str, Any]) -> None:
        src = node.attrs.get("src", "")
        if not src:
            return

        image_bytes = None
        if src.startswith("data:"):
            match = re.match(r"data:([^;]+);base64,(.*)", src, flags=re.DOTALL)
            if not match:
                return
            mime_type = match.group(1).lower()
            if "svg" in mime_type:
                return
            image_bytes = base64.b64decode(match.group(2))
        elif os.path.exists(src):
            with open(src, "rb") as fh:
                image_bytes = fh.read()

        if not image_bytes:
            return

        paragraph = container.add_paragraph()
        paragraph.alignment = ctx["WD_ALIGN_PARAGRAPH"].CENTER
        run = paragraph.add_run()
        alt_text = (node.attrs.get("alt", "") or "").lower()
        width = ctx["Inches"](2.0 if "logo" in alt_text else 6.0)
        run.add_picture(io.BytesIO(image_bytes), width=width)

    def _render_docx_node(self, container, node: _HtmlNode,
                          ctx: dict[str, Any], brand_rgb: tuple[int, int, int],
                          state: dict[str, bool]) -> None:
        tag = node.tag.lower()
        classes = self._node_classes(node)

        if tag in {"document", "html", "body"}:
            for child in self._child_nodes(node):
                self._render_docx_node(container, child, ctx, brand_rgb, state)
            return

        if tag in {"head", "style", "script", "meta", "title"}:
            return

        if tag == "div":
            if "report-top-bar" in classes or "footer" in classes:
                return
            if "page-break" in classes and state.get("started_content") and hasattr(container, "add_page_break"):
                container.add_page_break()
            if "metadata-grid" in classes:
                self._render_docx_metadata_grid(container, node, ctx, brand_rgb)
                state["started_content"] = True
                return
            if "summary-stats" in classes:
                self._render_docx_summary_stats(container, node, ctx)
                state["started_content"] = True
                return
            if "cover-title" in classes:
                paragraph = container.add_heading(self._node_text(node), level=0)
                paragraph.alignment = ctx["WD_ALIGN_PARAGRAPH"].CENTER
                self._set_docx_heading_color(paragraph, brand_rgb, ctx)
                state["started_content"] = True
                return
            if "cover-subtitle" in classes:
                self._add_docx_paragraph(
                    container,
                    self._node_text(node),
                    ctx,
                    align=ctx["WD_ALIGN_PARAGRAPH"].CENTER,
                )
                state["started_content"] = True
                return

            child_nodes = self._child_nodes(node)
            if not child_nodes:
                text = self._node_text(node)
                if text:
                    self._add_docx_paragraph(container, text, ctx)
                    state["started_content"] = True
                return

            block_tags = {"div", "p", "h1", "h2", "h3", "h4", "table", "ul", "ol", "img"}
            if not any(child.tag.lower() in block_tags for child in child_nodes):
                text = self._node_text(node)
                if text:
                    self._add_docx_paragraph(container, text, ctx)
                    state["started_content"] = True
                return

            for child in child_nodes:
                self._render_docx_node(container, child, ctx, brand_rgb, state)
            return

        if tag in {"h1", "h2", "h3", "h4"}:
            heading_level = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}[tag]
            paragraph = container.add_heading(self._node_text(node), level=heading_level)
            self._set_docx_heading_color(paragraph, brand_rgb, ctx)
            state["started_content"] = True
            return

        if tag == "p":
            self._add_docx_paragraph(container, self._node_text(node), ctx)
            state["started_content"] = True
            return

        if tag in {"ul", "ol"}:
            for child in self._child_nodes(node):
                self._render_docx_node(container, child, ctx, brand_rgb, state)
            return

        if tag == "li":
            self._add_docx_paragraph(container, self._node_text(node), ctx, style="List Bullet")
            state["started_content"] = True
            return

        if tag == "table":
            self._render_docx_table(container, node, ctx, brand_rgb)
            state["started_content"] = True
            return

        if tag == "img":
            self._render_docx_image(container, node, ctx)
            state["started_content"] = True
            return

        for child in self._child_nodes(node):
            self._render_docx_node(container, child, ctx, brand_rgb, state)

    def generate_docx_from_html(self, html_text: str, brand=None) -> bytes:
        if not DOCX_AVAILABLE:
            raise RuntimeError("python-docx is not installed.")

        from docx import Document
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import parse_xml
        from docx.oxml.ns import nsdecls
        from docx.shared import Inches, Mm, Pt, RGBColor

        document = Document()
        section = document.sections[0]
        section.top_margin = Mm(20)
        section.right_margin = Mm(20)
        section.bottom_margin = Mm(20)
        section.left_margin = Mm(20)

        normal_style = document.styles["Normal"]
        normal_style.font.name = "Calibri"
        normal_style.font.size = Pt(10.5)

        body_html = self._extract_body_contents(html_text)
        root = self._parse_html_tree(body_html)
        body = self._find_first_node(root, "body") or root
        brand_rgb = self._hex_to_rgb_triplet(getattr(brand, "primary_color", "#2c3e50"))
        ctx = {
            "Inches": Inches,
            "Mm": Mm,
            "Pt": Pt,
            "RGBColor": RGBColor,
            "WD_ALIGN_PARAGRAPH": WD_ALIGN_PARAGRAPH,
            "WD_TABLE_ALIGNMENT": WD_TABLE_ALIGNMENT,
            "parse_xml": parse_xml,
            "nsdecls": nsdecls,
        }
        state = {"started_content": False}
        for child in self._child_nodes(body):
            self._render_docx_node(document, child, ctx, brand_rgb, state)

        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    def _render_table_block_html(self, block: TableBlock) -> str:
        html = "<table>"
        if block.columns:
            html += "<thead><tr>"
            for column in block.columns:
                html += f"<th>{self._esc(column)}</th>"
            html += "</tr></thead>"

        html += "<tbody>"
        for row in block.rows:
            html += "<tr>"
            for cell in row:
                html += f"<td>{self._esc(cell)}</td>"
            html += "</tr>"
        html += "</tbody></table>"

        if block.caption:
            html += f'<div class="figure-caption">{self._esc(block.caption)}</div>'
        return html

    def _render_report_block_html(self, block: Any) -> str:
        if isinstance(block, HeadingBlock):
            level = min(max(block.level, 1), 4)
            return f"<h{level}>{self._esc(block.text)}</h{level}>"
        if isinstance(block, ParagraphBlock):
            return f"<p>{self._note_html(block.text)}</p>"
        if isinstance(block, TableBlock):
            return self._render_table_block_html(block)
        if isinstance(block, HtmlBlock):
            return block.html
        if isinstance(block, ImageBlock):
            caption = ""
            if block.caption:
                caption = f'<div class="figure-caption">{self._esc(block.caption)}</div>'
            return (
                f'<div class="plot-container">'
                f'<img src="{self._esc(block.source)}" alt="{self._esc(block.alt_text or block.caption)}" />'
                f'{caption}'
                f'</div>'
            )
        if isinstance(block, PageBreakBlock):
            return '<div class="page-break"></div>'
        raise TypeError(f"Unsupported report block: {type(block)!r}")

    def _calculate_percentile_values(self, dataset: GrainSizeData,
                                     percentiles_list: List[int]) -> Dict[int, Optional[float]]:
        values: Dict[int, Optional[float]] = {}
        for percentile in percentiles_list:
            values[percentile] = dataset.get_percentile_size(percentile)
        return values

    def _create_percentiles_table_block(self, dataset: GrainSizeData) -> TableBlock:
        percentiles_list = [5, 10, 16, 20, 25, 30, 40, 50, 60, 75, 84, 90, 95]
        percentiles_dict = self._calculate_percentile_values(dataset, percentiles_list)
        max_val = max((value for value in percentiles_dict.values() if value is not None), default=0)
        rows: list[list[str]] = []
        for percentile in percentiles_list:
            value = percentiles_dict[percentile]
            relative = int((value / max_val) * 100) if value is not None and max_val > 0 else 0
            label = f"D{percentile}{'*' if percentile in [10, 30, 50, 60] else ''}"
            rows.append([label, f"{value:.3f}" if value is not None else "N/A", f"{relative}%"])

        return TableBlock(
            columns=["Percentile", "Size (mm)", "Relative (%)"],
            rows=rows,
        )

    def _create_data_quality_table_block(self, dataset: GrainSizeData) -> TableBlock:
        n_points = len(dataset.particle_sizes)
        size_min = min(dataset.particle_sizes)
        size_max = max(dataset.particle_sizes)
        size_range = size_max / size_min if size_min > 0 else 0

        sorted_indices = np.argsort(dataset.particle_sizes)[::-1]
        sorted_passing = [dataset.percent_passing[i] for i in sorted_indices]
        monotonic = all(sorted_passing[i] >= sorted_passing[i + 1] for i in range(len(sorted_passing) - 1))
        monotonicity_score = "Excellent" if monotonic else "Good"
        coverage_score = "Excellent" if size_range > 100 else "Good" if size_range > 10 else "Limited"
        density_score = "Excellent" if n_points > 20 else "Good" if n_points > 10 else "Adequate"
        confidence_score = "High" if (n_points > 15 and size_range > 50) else "Moderate" if n_points > 8 else "Low"

        rows = [
            ["Number of Data Points", str(n_points), density_score],
            ["Size Range", f"{size_min:.3f} - {size_max:.1f} mm", coverage_score],
            ["Span Ratio", f"{size_range:.1f}x", coverage_score],
            ["Curve Monotonicity", "Monotonic" if monotonic else "Some variation", monotonicity_score],
            ["Interpolation Confidence", "", confidence_score],
        ]
        return TableBlock(
            columns=["Quality Metric", "Value", "Assessment"],
            rows=rows,
        )

    def _create_raw_data_table_block(self, dataset: GrainSizeData) -> TableBlock:
        rows: list[list[str]] = []
        for size, passing in zip(dataset.particle_sizes, dataset.percent_passing):
            retained = 100 - passing
            rows.append([f"{size:.4f}", f"{passing:.2f}", f"{retained:.2f}"])

        return TableBlock(
            columns=["Grain Size (mm)", "Percent Passing (%)", "Percent Retained (%)"],
            rows=rows,
        )

    def _build_grain_size_appendix_document(self, dataset: GrainSizeData,
                                            sections: Dict[str, bool],
                                            appendix_label_config: Optional[Any] = None) -> ReportDocument:
        document = ReportDocument(
            title="Appendices",
            appendix_label_config=self._coerce_appendix_label_config(appendix_label_config),
        )

        if sections.get('percentiles', True):
            document.add_section(ReportSection(
                section_id="grain_percentiles",
                title="Detailed Percentile Data",
                kind="appendix",
                blocks=[HtmlBlock(self._create_percentiles_table(dataset))],
            ))
        if sections.get('data_quality', False):
            document.add_section(ReportSection(
                section_id="grain_data_quality",
                title="Data Quality Assessment",
                kind="appendix",
                blocks=[HtmlBlock(self._create_data_quality_table(dataset))],
            ))
        if sections.get('raw_data', False):
            raw_data_table = '<table class="table-compact"><thead><tr><th>Grain Size (mm)</th><th>Percent Passing (%)</th><th>Percent Retained (%)</th></tr></thead><tbody>'
            for size, passing in zip(dataset.particle_sizes, dataset.percent_passing):
                retained = 100 - passing
                raw_data_table += f'<tr><td>{size:.4f}</td><td>{passing:.2f}</td><td>{retained:.2f}</td></tr>'
            raw_data_table += '</tbody></table>'
            document.add_section(ReportSection(
                section_id="grain_raw_data",
                title="Raw Measurement Data",
                kind="appendix",
                blocks=[HtmlBlock(raw_data_table)],
            ))

        return document

    def _render_appendix_document_html(self, document: ReportDocument) -> str:
        appendix_sections = document.appendix_sections()
        if not appendix_sections:
            return ""

        html = '<div class="appendix-section page-break">'
        html += f'<h1 class="appendix-title">{self._esc(document.title)}</h1>'

        if document.single_appendix_enabled():
            html += '<div class="appendix-item">'
            html += f'<h3 class="appendix-item-title">{self._esc(document.single_appendix_label())}</h3>'
            for section in appendix_sections:
                html += '<div class="appendix-subsection">'
                if section.title:
                    html += f'<h4 class="appendix-subtitle">{self._esc(section.title)}</h4>'
                if section.notes:
                    html += f"<p>{self._note_html(section.notes)}</p>"
                for block in section.blocks:
                    html += self._render_report_block_html(block)
                html += '</div>'
            html += '</div>'
        else:
            for section in appendix_sections:
                html += '<div class="appendix-item">'
                html += f'<h3 class="appendix-item-title">{self._esc(document.appendix_display_title(section))}</h3>'
                if section.notes:
                    html += f"<p>{self._note_html(section.notes)}</p>"
                for block in section.blocks:
                    html += self._render_report_block_html(block)
                html += '</div>'

        html += '</div>'
        return html

    def _create_cover_page(self, title: str, subtitle: str,
                           metadata: Dict[str, str], brand=None) -> str:
        """Create a professional cover page"""
        html = '<div class="cover-page page-break">'

        # Brand header (logo + org name) if branding provided
        if brand is not None:
            html += f'<div style="margin-bottom:24px;">{brand.get_logo_html(56)}</div>'
            html += (
                f'<div style="font-size:13px;font-weight:600;'
                f'color:{brand.primary_color};margin-bottom:4px;">'
                f'{self._esc(brand.org_name)}</div>'
            )
            if brand.org_subtitle:
                html += (
                    f'<div style="font-size:11px;color:#7f8c8d;'
                    f'margin-bottom:28px;">{self._esc(brand.org_subtitle)}</div>'
                )

        html += f'<div class="cover-title">{self._esc(title)}</div>'
        html += f'<div class="cover-subtitle">{self._esc(subtitle)}</div>'

        html += '<div class="cover-meta">'
        if metadata.get('project_name'):
            html += f'<div><strong>Project:</strong> {self._esc(metadata["project_name"])}</div>'
        if metadata.get('location'):
            html += f'<div><strong>Location:</strong> {self._esc(metadata["location"])}</div>'
        if metadata.get('client'):
            html += f'<div><strong>Client:</strong> {self._esc(metadata["client"])}</div>'
        if metadata.get('analyst'):
            html += f'<div><strong>Analyst:</strong> {self._esc(metadata["analyst"])}</div>'
        html += f'<div><strong>Date:</strong> {datetime.now().strftime("%B %d, %Y")}</div>'
        html += '</div>'
        html += '</div>'

        return html

    def _create_grain_size_plot(
        self,
        dataset: GrainSizeData,
        plot_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create grain size distribution curve and return as base64."""
        pe = _get_plot_export()
        return pe.export_grain_size_plot(
            dataset,
            plot_context=plot_context,
            show_d_lines=False,
            show_markers=False,
            classification_scheme=self._scheme,
        )

    def _create_k_value_bar_chart(self, k_results: List[KCalculationResult]) -> str:
        """Create K-value comparison bar chart with error indication."""
        valid_results = [r for r in k_results if r.k_value is not None and r.k_value > 0]
        if not valid_results:
            return ""

        methods = [r.method_name for r in valid_results]
        k_values = [r.k_value for r in valid_results]
        flagged = {r.method_name for r in valid_results if classify_k_status(r) != "OK"}
        reference_values = [
            r.k_value
            for r in valid_results
            if classify_k_status(r) == "OK"
        ]

        pe = _get_plot_export()
        return pe.export_k_bar_chart(
            methods, k_values,
            flagged_methods=flagged,
            reference_values=reference_values,
            title="Hydraulic Conductivity Estimates by Method",
        )

    def _create_method_applicability_heatmap(self, k_results: List[KCalculationResult]) -> str:
        """Create method applicability status heatmap."""
        if not k_results:
            return ""
        return _get_plot_export().export_applicability_heatmap(k_results)

    def _create_comparison_grain_size_plot(self, datasets: List[GrainSizeData],
                                           sample_labels: Optional[List[str]] = None) -> str:
        """Create side-by-side grain size curves for comparison."""
        labels = sample_labels or [ds.sample_name for ds in datasets]
        return _get_plot_export().export_distribution_overlay(datasets, labels=labels)

    def _create_k_value_boxplot(self, k_results_dict: Dict[str, List[KCalculationResult]]) -> str:
        """Create box plots for K-value comparison across samples."""
        if not k_results_dict:
            return ""
        return _get_plot_export().export_k_boxplot(k_results_dict)

    def _comparison_uses_grouped_k_scope(self, comparison_snapshot) -> bool:
        return any(group != UNGROUPED_LABEL for group in comparison_snapshot.k.group_names)

    def _k_scope_plot_colors(self, comparison_snapshot, series) -> List[str]:
        if not self._comparison_uses_grouped_k_scope(comparison_snapshot):
            return []

        group_colors: Dict[str, str] = {}
        try:
            from gui.group_styles import group_color_map
            group_colors = group_color_map(
                comparison_snapshot.k.group_names,
                palette=DATASET_COLORS,
            )
        except Exception:
            fallback = tuple(DATASET_COLORS) or ("#3a7ea0", "#6b8e23", "#b46428")
            group_colors = {
                group: fallback[index % len(fallback)]
                for index, group in enumerate(comparison_snapshot.k.group_names)
            }

        colors = []
        for label, _values in series:
            if label == "Overall":
                colors.append("#8c6f45")
            else:
                colors.append(group_colors.get(label, "#777777"))
        return colors

    def _create_comparison_k_scope_boxplot(self, comparison_snapshot) -> str:
        """Create the report K boxplot from the shared comparison aggregation."""
        series = k_scope_value_series(comparison_snapshot.k)
        if not any(values for _label, values in series):
            return ""

        grouped = self._comparison_uses_grouped_k_scope(comparison_snapshot)
        title = (
            "Hydraulic Conductivity Distribution by Group"
            if grouped
            else "Hydraulic Conductivity Distribution by Dataset"
        )
        return _get_plot_export().export_k_scope_boxplot(
            series,
            colors=self._k_scope_plot_colors(comparison_snapshot, series),
            title=title,
        )

    def _create_method_reliability_matrix(self, k_results_dict: Dict[str, List[KCalculationResult]]) -> str:
        """Create method reliability matrix for comparison report."""
        if not k_results_dict:
            return ""
        return _get_plot_export().export_reliability_matrix(k_results_dict)

    def _format_metadata_section(self, metadata: Dict[str, str]) -> str:
        """Format project metadata section with modern grid layout"""
        html = '<div class="metadata"><div class="metadata-grid">'

        if metadata.get('project_name'):
            html += '<div class="metadata-label">Project:</div>'
            html += f'<div class="metadata-value">{self._esc(metadata["project_name"])}</div>'
        if metadata.get('location'):
            html += '<div class="metadata-label">Location:</div>'
            html += f'<div class="metadata-value">{self._esc(metadata["location"])}</div>'
        if metadata.get('client'):
            html += '<div class="metadata-label">Client:</div>'
            html += f'<div class="metadata-value">{self._esc(metadata["client"])}</div>'
        if metadata.get('analyst'):
            html += '<div class="metadata-label">Analyst:</div>'
            html += f'<div class="metadata-value">{self._esc(metadata["analyst"])}</div>'

        html += '<div class="metadata-label">Report Date:</div>'
        html += f'<div class="metadata-value">{datetime.now().strftime("%B %d, %Y at %H:%M")}</div>'
        html += '</div></div>'

        return html

    def generate_grain_size_report(self, dataset: GrainSizeData,
                                  metadata: Optional[Dict[str, str]] = None,
                                  sections: Optional[Dict[str, bool]] = None,
                                  report_template: str = "standard",
                                  brand=None,
                                  appendix_label_config: Optional[Any] = None,
                                  plot_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a grain size analysis report for a single sample

        Args:
            dataset: GrainSizeData object containing the sample data
            metadata: Dictionary with project metadata (project_name, location, client, analyst, notes)
            sections: Dictionary controlling which sections to include
            report_template: Template style - "standard", "executive", "technical", "appendix"

        Returns:
            HTML string of the complete report
        """

        # Set defaults
        if metadata is None:
            metadata = {}
        if sections is None:
            # Default sections based on template
            if report_template == "executive":
                sections = {
                    'cover_page': True,
                    'executive_summary': True,
                    'methodology': False,
                    'results': True,
                    'plots': True,
                    'raw_data': False,
                    'interpretation': True,
                    'percentiles': False,
                    'gradation': True,
                    'data_quality': False
                }
            elif report_template == "technical":
                sections = {
                    'cover_page': True,
                    'executive_summary': True,
                    'methodology': True,
                    'results': True,
                    'plots': True,
                    'raw_data': False,
                    'interpretation': True,
                    'percentiles': True,
                    'gradation': True,
                    'data_quality': True
                }
            elif report_template == "appendix":
                sections = {
                    'cover_page': False,
                    'executive_summary': False,
                    'methodology': False,
                    'results': False,
                    'plots': True,
                    'raw_data': True,
                    'interpretation': False,
                    'percentiles': True,
                    'gradation': True,
                    'data_quality': True
                }
            else:  # standard
                sections = {
                    'cover_page': False,
                    'executive_summary': True,
                    'methodology': True,
                    'results': True,
                    'plots': True,
                    'raw_data': False,
                    'interpretation': True,
                    'percentiles': True,
                    'gradation': True,
                    'data_quality': False
                }

        # Get characteristic grain sizes
        d10 = dataset.get_d10()
        d20 = dataset.get_d20()
        d30 = dataset.get_d30()
        d50 = dataset.get_d50()
        d60 = dataset.get_d60()

        # Calculate coefficients
        cu = (d60 / d10) if (d10 and d60 and d10 > 0) else None
        cc = ((d30 * d30) / (d10 * d60)) if (d10 and d30 and d60 and d10 > 0 and d60 > 0) else None

        # Start HTML report
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grain Size Analysis Report - {dataset.sample_name}</title>
    {self._get_branded_style(brand)}
</head>
<body>
<div class="report-top-bar"></div>
"""

        # Cover Page (optional)
        if sections.get('cover_page', False):
            html += self._create_cover_page(
                "Grain Size Analysis",
                f"Sample: {dataset.sample_name}",
                metadata, brand
            )

        # Main Title (if no cover page)
        if not sections.get('cover_page', False):
            html += f'<h1>Grain Size Analysis Report</h1>'
            html += self._format_metadata_section(metadata)

        # Sample Information
        html += f"""
<div class="metadata">
    <div class="metadata-grid">
        <div class="metadata-label">Sample Name:</div>
        <div class="metadata-value">{dataset.sample_name}</div>
        <div class="metadata-label">Soil Classification:</div>
        <div class="metadata-value"><strong>{dataset.classify(scheme=self._scheme).label}</strong></div>
        <div class="metadata-label">Temperature:</div>
        <div class="metadata-value">{dataset.temperature}°C</div>
        <div class="metadata-label">Porosity:</div>
        <div class="metadata-value">{self._porosity_display(dataset)}</div>
        <div class="metadata-label">Porosity Source:</div>
        <div class="metadata-value">{self._esc(self._porosity_source_display(dataset))}</div>
        <div class="metadata-label">Data Points:</div>
        <div class="metadata-value">{len(dataset.particle_sizes)}</div>
    </div>
</div>
"""

        # Executive Summary
        if sections.get('executive_summary', True):
            html += f"""
<div class="no-break">
<h2>Executive Summary</h2>
<div class="success-box">
    <p>Sample <strong>{dataset.sample_name}</strong> has been analyzed and classified as <strong>{dataset.classify(scheme=self._scheme).label}</strong>.</p>
</div>
<div class="summary-stats">
    <div class="stat-card">
        <div class="stat-label">Median Size (D₅₀)</div>
        <div class="stat-value">{f'{d50:.3f}' if d50 else 'N/A'}</div>
        <div class="stat-unit">mm</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Uniformity (Cu)</div>
        <div class="stat-value">{f'{cu:.2f}' if cu else 'N/A'}</div>
        <div class="stat-unit">{self._classify_uniformity(cu)}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Curvature (Cc)</div>
        <div class="stat-value">{f'{cc:.2f}' if cc else 'N/A'}</div>
        <div class="stat-unit">{self._classify_curvature(cc)}</div>
    </div>
</div>
</div>
"""

        # Methodology
        if sections.get('methodology', True):
            html += """
<div class="page-break">
<h2>Methodology</h2>
<div class="info-box">
    <h3>Grain Size Distribution Analysis</h3>
    <p>Grain size distribution was determined using sieve analysis and/or sedimentation methods following standard geotechnical procedures. The cumulative distribution curve plots percent passing versus grain size on a semi-logarithmic scale.</p>
</div>
<div class="info-box">
    <h3>Characteristic Diameters</h3>
    <p>Characteristic grain sizes represent specific percentiles of the grain size distribution:</p>
    <ul>
        <li><strong>D₁₀, D₃₀, D₅₀, D₆₀:</strong> Grain diameters at which 10%, 30%, 50%, and 60% of the soil mass is finer</li>
        <li><strong>D₅₀ (Median):</strong> The median grain size, representing the center of the distribution</li>
        <li>These values are fundamental for soil classification and hydraulic conductivity estimation</li>
    </ul>
</div>
<div class="info-box">
    <h3>Gradation Parameters</h3>
    <p><strong>Uniformity Coefficient:</strong> <code>Cu = D₆₀ / D₁₀</code></p>
    <ul>
        <li>Cu &lt; 4: Uniform gradation (narrow size range)</li>
        <li>4 ≤ Cu &lt; 6: Moderate gradation</li>
        <li>Cu ≥ 6: Well-graded soil (wide size range)</li>
    </ul>
    <p><strong>Coefficient of Curvature:</strong> <code>Cc = (D₃₀)² / (D₁₀ × D₆₀)</code></p>
    <ul>
        <li>1 ≤ Cc ≤ 3: Well-graded with good particle size distribution</li>
        <li>Outside this range: Gap-graded or uniform distribution</li>
    </ul>
</div>
</div>
"""

        # Results
        if sections.get('results', True):
            html += f"""
<div class="page-break">
<h2>Results & Analysis</h2>

<h3>Characteristic Grain Sizes</h3>
<div class="summary-stats">
    <div class="stat-card">
        <div class="stat-label">D₁₀</div>
        <div class="stat-value">{f'{d10:.3f}' if d10 else 'N/A'}</div>
        <div class="stat-unit">mm</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">D₃₀</div>
        <div class="stat-value">{f'{d30:.3f}' if d30 else 'N/A'}</div>
        <div class="stat-unit">mm</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">D₅₀</div>
        <div class="stat-value">{f'{d50:.3f}' if d50 else 'N/A'}</div>
        <div class="stat-unit">mm</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">D₆₀</div>
        <div class="stat-value">{f'{d60:.3f}' if d60 else 'N/A'}</div>
        <div class="stat-unit">mm</div>
    </div>
</div>

<h3>Soil Classification Parameters</h3>
<table>
    <thead>
        <tr>
            <th>Parameter</th>
            <th>Value</th>
            <th>Classification</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>Uniformity Coefficient</strong> (Cu = D₆₀/D₁₀)</td>
            <td class="text-center">{f'{cu:.2f}' if cu else 'N/A'}</td>
            <td><span class="badge badge-info">{self._classify_uniformity(cu)}</span></td>
        </tr>
        <tr>
            <td><strong>Coefficient of Curvature</strong> (Cc = D₃₀²/D₁₀·D₆₀)</td>
            <td class="text-center">{f'{cc:.2f}' if cc else 'N/A'}</td>
            <td><span class="badge badge-info">{self._classify_curvature(cc)}</span></td>
        </tr>
        <tr>
            <td><strong>Soil Classification</strong></td>
            <td colspan="2"><span class="badge badge-success">{dataset.classify(scheme=self._scheme).label}</span></td>
        </tr>
    </tbody>
</table>
"""

            if sections.get('gradation', True):
                html += f"<h3>Gradation Analysis</h3>{self._create_gradation_table(dataset)}"

            html += "</div>"

        # Visual Charts
        if sections.get('plots', True):
            grain_plot = self._create_grain_size_plot(dataset, plot_context)
            html += f"""
<div class="page-break">
<h2>Grain Size Distribution Curve</h2>
<div class="plot-container">
    <img src="{grain_plot}" alt="Grain Size Distribution" />
    <div class="figure-caption">Figure 1: Cumulative grain size distribution curve for {dataset.sample_name}</div>
</div>
</div>
"""

        # Interpretation
        if sections.get('interpretation', True):
            html += f"""
<div class="page-break">
<h2>Interpretation & Discussion</h2>
<div class="info-box">
    <h3>Grain Size Distribution Analysis</h3>
    <p>{self._interpret_grain_distribution(dataset, cu, cc)}</p>
</div>
"""
            if metadata.get('notes'):
                html += f"""
<div class="info-box">
    <h3>Additional Notes</h3>
    <p>{self._note_html(metadata['notes'])}</p>
</div>
"""
            html += "</div>"

        appendix_document = self._build_grain_size_appendix_document(
            dataset,
            sections,
            appendix_label_config=appendix_label_config,
        )
        html += self._render_appendix_document_html(appendix_document)

        # Footer
        html += """
<div class="footer">
    <span><strong>Grain Size Analysis Report</strong></span>
    <span>Generated by Grain Size Analysis &amp; Hydraulic Conductivity Calculator</span>
</div>
</body>
</html>
"""

        return html

    def generate_k_value_report(self, dataset: GrainSizeData,
                               k_results: List[KCalculationResult],
                               temperature: float,
                               porosity: float,
                               metadata: Optional[Dict[str, str]] = None,
                               sections: Optional[Dict[str, bool]] = None,
                               report_template: str = "standard",
                               brand=None) -> str:
        """
        Generate a hydraulic conductivity (K-value) report for a single sample

        Args:
            dataset: GrainSizeData object
            k_results: List of KCalculationResult objects from different methods
            temperature: Water temperature in °C
            porosity: Soil porosity
            metadata: Project metadata dictionary
            sections: Dictionary controlling which sections to include
            report_template: Template style - "standard", "executive", "technical", "appendix"

        Returns:
            HTML string of the complete report
        """

        # Set defaults
        if metadata is None:
            metadata = {}
        if sections is None:
            if report_template == "executive":
                sections = {
                    'cover_page': True,
                    'executive_summary': True,
                    'methodology': False,
                    'results': True,
                    'plots': True,
                    'interpretation': True,
                    'k_statistics': False
                }
            elif report_template == "technical":
                sections = {
                    'cover_page': True,
                    'executive_summary': True,
                    'methodology': True,
                    'results': True,
                    'plots': True,
                    'interpretation': True,
                    'k_statistics': True
                }
            elif report_template == "appendix":
                sections = {
                    'cover_page': False,
                    'executive_summary': False,
                    'methodology': False,
                    'results': False,
                    'plots': True,
                    'interpretation': False,
                    'k_statistics': True
                }
            else:  # standard
                sections = {
                    'cover_page': False,
                    'executive_summary': True,
                    'methodology': True,
                    'results': True,
                    'plots': True,
                    'interpretation': True,
                    'k_statistics': True
                }

        summary = build_k_result_summary(k_results)

        if summary.geometric_mean_m_s is None:
            return self._generate_no_results_report(dataset.sample_name)

        # Shared OK-only K summary.
        mean_k = summary.geometric_mean_m_s
        arithmetic_k = summary.arithmetic_mean_m_s
        median_k = summary.median_m_s
        std_k = summary.std_dev_m_s or 0.0
        min_k = summary.min_m_s
        max_k = summary.max_m_s
        variability_ratio = max_k / min_k if min_k > 0 else 0

        # Start HTML report
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hydraulic Conductivity Report - {dataset.sample_name}</title>
    {self._get_branded_style(brand)}
</head>
<body>
<div class="report-top-bar"></div>
"""

        # Cover Page (optional)
        if sections.get('cover_page', False):
            html += self._create_cover_page(
                "Hydraulic Conductivity Analysis",
                f"Sample: {dataset.sample_name}",
                metadata, brand
            )

        # Main Title (if no cover page)
        if not sections.get('cover_page', False):
            html += f'<h1>Hydraulic Conductivity Analysis Report</h1>'
            html += self._format_metadata_section(metadata)

        # Sample Information
        html += f"""
<div class="metadata">
    <div class="metadata-grid">
        <div class="metadata-label">Sample Name:</div>
        <div class="metadata-value">{dataset.sample_name}</div>
        <div class="metadata-label">Temperature:</div>
        <div class="metadata-value">{temperature}°C</div>
        <div class="metadata-label">Porosity:</div>
        <div class="metadata-value">{self._porosity_display(dataset, porosity)}</div>
        <div class="metadata-label">Porosity Source:</div>
        <div class="metadata-value">{self._esc(self._porosity_source_display(dataset))}</div>
        <div class="metadata-label">Methods Evaluated:</div>
        <div class="metadata-value">{len(k_results)} empirical methods</div>
        <div class="metadata-label">Valid Results:</div>
        <div class="metadata-value"><span class="badge badge-success">{summary.included_count} / {summary.total_cells}</span></div>
    </div>
</div>
"""

        # Executive Summary
        if sections.get('executive_summary', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Executive Summary</h2>
            <div class="info-box">
                <p><strong>Sample:</strong> {dataset.sample_name} hydraulic conductivity analysis using {len(k_results)} empirical methods.</p>
                <p><strong>Geometric Mean K:</strong> {mean_k:.2e} m/s (from {summary.included_count} OK methods)</p>
                <p><strong>Permeability Classification:</strong> {self._classify_permeability(mean_k)}</p>
                <p><strong>Variability:</strong> {max_k/min_k:.1f}x difference between minimum and maximum estimates</p>
            </div>
            </div>
            """

        # Methodology
        if sections.get('methodology', True):
            html += """
            <div style="page-break-before: auto;">
            <h2>Methodology</h2>
            <div class="info-box">
                <h3>Hydraulic Conductivity Estimation</h3>
                <p>Hydraulic conductivity (K) represents the ease with which water can move through pore spaces
                in soil. This analysis employs multiple empirical methods developed from various grain size
                parameters to estimate K-values for comparison and reliability assessment.</p>
                <h3>Empirical Methods</h3>
                <p>Each method has specific applicability ranges and underlying assumptions based on soil type,
                grain size distribution, and original calibration data. Methods include Hazen, Shepherd, Kozeny-Carman,
                Terzaghi, Breyer, Slichter, Sauerbrei, Kruger, Zunker, Zamarin, USBR, and Barr.</p>
                <h3>Quality Assessment</h3>
                <p>Each calculation is evaluated for applicability based on grain size parameters. Results are
                marked as OK (within recommended range), WARNING (outside optimal range), or ERROR (calculation failed).
                Statistical analysis of multiple methods provides confidence bounds on the estimated K-value.</p>
            </div>
            </div>
            """

        # Results
        if sections.get('results', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Results & Analysis</h2>

            <h3>Statistical Summary</h3>
            <div class="summary-stats">
                <div class="stat-card">
                    <div class="stat-label">K Geometric Mean</div>
                    <div class="stat-value">{mean_k:.2e} m/s</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">K Arithmetic Mean</div>
                    <div class="stat-value">{arithmetic_k:.2e} m/s</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Median K</div>
                    <div class="stat-value">{median_k:.2e} m/s</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Min K</div>
                    <div class="stat-value">{min_k:.2e} m/s</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Max K</div>
                    <div class="stat-value">{max_k:.2e} m/s</div>
                </div>
            </div>

            <h3>K-Value Calculations by Method</h3>
            <table>
                <tr>
                    <th>Method</th>
                    <th>K-Value (m/s)</th>
                    <th>Formula</th>
                    <th>Status</th>
                </tr>
            """

            for result in k_results:
                status_class = "success" if classify_k_status(result) == "OK" else "warning"
                k_display = f"{result.k_value:.2e}" if result.k_value else "N/A"

                html += f"""
                <tr>
                    <td>{result.method_name}</td>
                    <td>{k_display}</td>
                    <td style="font-size: 11px;">{result.formula_used}</td>
                    <td><span class="{status_class}">{result.status_message or result.status}</span></td>
                </tr>
                """

            html += """
            </table>

            <h3>Permeability Classification</h3>
            <div class="info-box">
                <p><strong>Classification:</strong> {}</p>
                <p><strong>Typical Application:</strong> {}</p>
            </div>
            """.format(self._classify_permeability(mean_k), self._get_permeability_application(mean_k))

            # Add detailed K-value statistics
            if sections.get('k_statistics', True):
                html += f"<h3>Detailed K-Value Statistics</h3>{self._create_k_statistics_table(k_results)}"

            html += "</div>"

        elif sections.get('k_statistics', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>K-Value Results</h2>
            <h3>K-Value Calculations by Method</h3>
            {self._create_k_statistics_table(k_results)}
            </div>
            """

        # Visual Charts
        if sections.get('plots', True):
            k_bar_chart = self._create_k_value_bar_chart(k_results)
            method_heatmap = self._create_method_applicability_heatmap(k_results)

            if k_bar_chart:
                html += f"""
                <div style="page-break-before: auto;">
                <h2>K-Value Comparison Chart</h2>
                <div class="plot-container">
                    <img src="{k_bar_chart}" alt="K-Value Bar Chart" style="max-width: 100%; height: auto;">
                </div>
                </div>
                """

            if method_heatmap:
                html += f"""
                <div style="page-break-before: auto;">
                <h2>Method Applicability Status</h2>
                <div class="plot-container">
                    <img src="{method_heatmap}" alt="Method Applicability Heatmap" style="max-width: 100%; height: auto;">
                </div>
                </div>
                """

        # Interpretation
        if sections.get('interpretation', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Interpretation & Discussion</h2>
            <div class="info-box">
                <h3>Method Variability Analysis</h3>
                <p><strong>Variability:</strong> {max_k/min_k:.1f}x difference between min and max</p>
                <p><strong>Standard Deviation:</strong> {std_k:.2e} m/s</p>
                <p><strong>Coefficient of Variation:</strong> {(std_k/mean_k)*100:.1f}%</p>
                <p>{self._interpret_k_variability(max_k/min_k)}</p>
            </div>
            """

            # Add custom notes if provided
            if metadata.get('notes'):
                html += f"""
                <div class="info-box">
                    <h3>Additional Notes</h3>
                    <p>{self._note_html(metadata['notes'])}</p>
                </div>
                """

            html += "</div>"

        # Add footer
        html += """
            <div class="footer">
                <span><strong>Hydraulic Conductivity Report</strong></span>
                <span>Generated by Grain Size Analysis &amp; Hydraulic Conductivity Calculator</span>
            </div>
        </body>
        </html>
        """

        return html

    def generate_combined_report(self, dataset: GrainSizeData,
                                k_results: List[KCalculationResult],
                                temperature: float,
                                porosity: float,
                                metadata: Optional[Dict[str, str]] = None,
                                sections: Optional[Dict[str, bool]] = None,
                                brand=None,
                                appendix_label_config: Optional[Any] = None,
                                plot_context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a combined report with both grain size and K-value analysis"""

        # Set defaults
        if metadata is None:
            metadata = {}
        if sections is None:
            sections = {
                'executive_summary': True,
                'methodology': True,
                'results': True,
                'plots': True,
                'raw_data': False,
                'interpretation': True
            }

        grain_sections = dict(sections)
        k_sections = dict(sections)
        k_sections['cover_page'] = False

        grain_report = self.generate_grain_size_report(
            dataset,
            metadata=metadata,
            sections=grain_sections,
            brand=brand,
            appendix_label_config=appendix_label_config,
            plot_context=plot_context,
        )
        k_report = self.generate_k_value_report(
            dataset,
            k_results,
            temperature,
            porosity,
            metadata=metadata,
            sections=k_sections,
            brand=brand,
        )

        grain_body = self._extract_body_contents(grain_report)
        k_body = self._strip_leading_report_markup(self._extract_body_contents(k_report))

        # Create combined report with page break between sections
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Complete Analysis Report - {dataset.sample_name}</title>
            {self._get_branded_style(brand)}
        </head>
        <body>
            {grain_body.replace('</body>', '').replace('</html>', '')}

            <div class="page-break"></div>

            <h1>Hydraulic Conductivity Analysis</h1>
            {k_body}
        </body>
        </html>
        """

        return html

    def generate_comparison_report(self, datasets: List[GrainSizeData],
                                  k_results_dict: Optional[Dict[str, List[KCalculationResult]]] = None,
                                  temperature: Optional[float] = None,
                                  porosity: Optional[float] = None,
                                  metadata: Optional[Dict[str, str]] = None,
                                  sections: Optional[Dict[str, bool]] = None,
                                  brand=None,
                                  sample_details: Optional[List[Dict[str, Any]]] = None) -> str:
        """Generate a comparison report for multiple samples."""
        if metadata is None:
            metadata = {}
        if sections is None:
            sections = {
                'cover_page': True,
                'executive_summary': True,
                'methodology': True,
                'results': True,
                'plots': True,
                'interpretation': True,
                'grain_comparison': True,
                'k_statistics': True,
            }

        if sample_details is None:
            k_results_dict = k_results_dict or {}
            sample_details = []
            for index, dataset in enumerate(datasets):
                label = dataset.sample_name or f"Sample {index + 1}"
                sample_details.append({
                    "label": label,
                    "dataset": dataset,
                    "k_results": list(k_results_dict.get(label, [])),
                    "group_name": getattr(dataset, "group_name", "Ungrouped"),
                    "temperature": temperature,
                    "porosity": porosity,
                    "plot_context": None,
                })
        else:
            normalized_details = []
            for index, item in enumerate(sample_details):
                dataset = item.get("dataset")
                if dataset is None:
                    continue
                normalized_details.append({
                    "label": item.get("label") or dataset.sample_name or f"Sample {index + 1}",
                    "dataset": dataset,
                    "k_results": list(item.get("k_results") or []),
                    "group_name": item.get("group_name") or getattr(dataset, "group_name", "Ungrouped"),
                    "temperature": item.get("temperature"),
                    "porosity": item.get("porosity"),
                    "plot_context": item.get("plot_context"),
                })
            sample_details = normalized_details

        datasets = [item["dataset"] for item in sample_details]
        sample_labels = [str(item["label"]) for item in sample_details]
        plot_results_dict = {
            str(item["label"]): list(item.get("k_results") or [])
            for item in sample_details
        }
        snapshot_inputs = [
            DatasetAnalysisInput(
                label=str(item["label"]),
                dataset=item["dataset"],
                k_results=tuple(item.get("k_results") or ()),
                group_name=item.get("group_name") or getattr(item["dataset"], "group_name", "Ungrouped"),
                temperature=item.get("temperature"),
                porosity=item.get("porosity"),
                plot_context=item.get("plot_context"),
            )
            for item in sample_details
        ]
        comparison_snapshot = build_comparison_snapshot(
            snapshot_inputs,
            ComparisonSnapshotOptions(
                k_options=KAggregationOptions(include_warnings=False),
                classification_scheme=self._scheme,
            ),
        )
        mean_k_by_sample = {
            name: stats.geometric_mean_m_s
            for name, stats in comparison_snapshot.k.by_dataset.items()
            if stats.geometric_mean_m_s is not None
        }

        temperature_summary = self._summarize_sample_field(sample_details, "temperature", " °C")
        porosity_summary = self._summarize_sample_field(sample_details, "porosity")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Multi-Sample Comparison Report</title>
            {self._get_branded_style(brand)}
        </head>
        <body>
        <div class="report-top-bar"></div>
        """

        if sections.get('cover_page', True):
            html += self._create_cover_page(
                title="Multi-Sample Comparison Report",
                subtitle=f"Hydraulic Conductivity Analysis - {len(datasets)} Samples",
                metadata=metadata,
                brand=brand,
            )

        html += f"""
            <h1>Multi-Sample Comparison Report</h1>

            {self._format_metadata_section(metadata)}

            <div class="metadata">
                <p><strong>Number of Samples:</strong> {len(datasets)}</p>
                <p><strong>Temperature:</strong> {self._esc(temperature_summary)}</p>
                <p><strong>Porosity:</strong> {self._esc(porosity_summary)}</p>
            </div>
        """

        if sections.get('executive_summary', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Executive Summary</h2>
            <div class="info-box">
                <p><strong>Comparison Analysis:</strong> This report compares {len(datasets)} soil samples
                based on grain size distribution and hydraulic conductivity estimates.</p>
            """

            if mean_k_by_sample:
                highest = max(mean_k_by_sample.items(), key=lambda x: x[1])
                lowest = min(mean_k_by_sample.items(), key=lambda x: x[1])
                html += f"""
                <p><strong>Key Findings:</strong></p>
                <ul>
                    <li>Highest permeability: {self._esc(highest[0])} ({highest[1]:.2e} m/s)</li>
                    <li>Lowest permeability: {self._esc(lowest[0])} ({lowest[1]:.2e} m/s)</li>
                    <li>Permeability range: {highest[1]/lowest[1]:.1f}x difference</li>
                </ul>
                """

            html += """
            </div>
            </div>
            """

        if sections.get('methodology', True):
            html += """
            <div style="page-break-before: auto;">
            <h2>Methodology</h2>
            <div class="info-box">
                <h3>Comparative Analysis Approach</h3>
                <p>This comparison report presents a side-by-side analysis of multiple soil samples
                to identify patterns, variations, and relationships between grain size characteristics
                and hydraulic conductivity estimates.</p>
                <h3>Analysis Components</h3>
                <p><strong>Grain Size Comparison:</strong> Overlapping distribution curves allow visual
                assessment of particle size variations between samples.</p>
                <p><strong>K-Value Comparison:</strong> Box plots and statistical summaries reveal the
                range and reliability of hydraulic conductivity estimates across samples.</p>
                <p><strong>Method Reliability:</strong> A reliability matrix shows which empirical methods
                are applicable for each sample, helping identify the most suitable estimation approaches.</p>
            </div>
            </div>
            """

        if sections.get('results', True):
            html += """
            <div style="page-break-before: auto;">
            <h2>Results & Analysis</h2>

            <h3>Sample Overview</h3>
            <table>
                <thead>
                    <tr>
                        <th>Sample</th>
                        <th>Temp (°C)</th>
                        <th>Porosity</th>
                        <th>D10 (mm)</th>
                        <th>D50 (mm)</th>
                        <th>D60 (mm)</th>
                        <th>Cu</th>
                        <th>Soil Type</th>
                        <th>K geometric mean (m/s)</th>
                    </tr>
                </thead>
                <tbody>
            """

            for item in sample_details:
                label = str(item["label"])
                dataset = item["dataset"]
                d10 = dataset.get_d10()
                d50 = dataset.get_d50()
                d60 = dataset.get_d60()
                cu = (d60 / d10) if (d10 and d60) else None

                mean_k = "N/A"
                if label in mean_k_by_sample:
                    mean_k = f"{mean_k_by_sample[label]:.2e}"

                temp_value = item.get("temperature")
                porosity_value = item.get("porosity")
                temp_display = "N/A" if temp_value is None else f"{float(temp_value):.2f}"
                porosity_display = "N/A" if porosity_value is None else f"{float(porosity_value):.3f}".rstrip("0").rstrip(".")

                html += f"""
                <tr>
                    <td>{self._esc(label)}</td>
                    <td>{temp_display}</td>
                    <td>{porosity_display}</td>
                    <td>{f'{d10:.3f}' if d10 else 'N/A'}</td>
                    <td>{f'{d50:.3f}' if d50 else 'N/A'}</td>
                    <td>{f'{d60:.3f}' if d60 else 'N/A'}</td>
                    <td>{f'{cu:.2f}' if cu else 'N/A'}</td>
                    <td>{self._esc(dataset.classify(scheme=self._scheme).label)}</td>
                    <td>{mean_k}</td>
                </tr>
                """

            html += "</tbody></table>"

            if sections.get('grain_comparison', True):
                html += f"<h3>Grain Parameters Comparison</h3>{self._create_grain_parameters_comparison_table(datasets, sample_labels)}"

            if sections.get('k_statistics', True) and plot_results_dict:
                html += f"<h3>K-Value Aggregate Summary</h3>{self._create_comparison_k_scope_summary_table(comparison_snapshot)}"
                html += f"<h3>K-Value Calculations by Dataset and Method</h3>{self._create_comparison_k_statistics_table(plot_results_dict)}"
                html += f"<h3>Permeability Classification Summary</h3>{self._create_permeability_classification_table(plot_results_dict)}"

            html += "</div>"

        elif sections.get('k_statistics', True) and plot_results_dict:
            html += f"""
            <div style="page-break-before: auto;">
            <h2>K-Value Results</h2>
            <h3>K-Value Aggregate Summary</h3>
            {self._create_comparison_k_scope_summary_table(comparison_snapshot)}
            <h3>K-Value Calculations by Dataset and Method</h3>
            {self._create_comparison_k_statistics_table(plot_results_dict)}
            <h3>Permeability Classification Summary</h3>
            {self._create_permeability_classification_table(plot_results_dict)}
            </div>
            """

        if sections.get('plots', True):
            comparison_plot = self._create_comparison_grain_size_plot(datasets, sample_labels)
            k_boxplot = self._create_comparison_k_scope_boxplot(comparison_snapshot)
            reliability_matrix = self._create_method_reliability_matrix(plot_results_dict)

            if comparison_plot:
                html += f"""
                <div style="page-break-before: auto;">
                <h2>Grain Size Distribution Comparison</h2>
                <div class="plot-container">
                    <img src="{comparison_plot}" alt="Grain Size Comparison" style="max-width: 100%; height: auto;">
                </div>
                </div>
                """

            if k_boxplot:
                html += f"""
                <div style="page-break-before: auto;">
                <h2>Hydraulic Conductivity Distribution</h2>
                <div class="plot-container">
                    <img src="{k_boxplot}" alt="K-Value Boxplot" style="max-width: 100%; height: auto;">
                </div>
                </div>
                """

            if reliability_matrix:
                html += f"""
                <div style="page-break-before: always;">
                <h2>Appendix: Method Reliability Matrix</h2>
                <div class="plot-container">
                    <img src="{reliability_matrix}" alt="Method Reliability Matrix" style="max-width: 100%; height: auto;">
                </div>
                </div>
                """

        if sections.get('interpretation', True):
            html += """
            <div style="page-break-before: auto;">
            <h2>Interpretation & Discussion</h2>
            <div class="info-box">
                <h3>Comparative Analysis</h3>
            """

            if mean_k_by_sample:
                highest = max(mean_k_by_sample.items(), key=lambda x: x[1])
                lowest = min(mean_k_by_sample.items(), key=lambda x: x[1])

                html += f"""
                <p><strong>Permeability Characteristics:</strong></p>
                <ul>
                    <li>The highest permeability sample is {self._esc(highest[0])} with K = {highest[1]:.2e} m/s,
                    classified as {self._classify_permeability(highest[1])}.</li>
                    <li>The lowest permeability sample is {self._esc(lowest[0])} with K = {lowest[1]:.2e} m/s,
                    classified as {self._classify_permeability(lowest[1])}.</li>
                    <li>The {highest[1]/lowest[1]:.1f}-fold difference in permeability reflects the
                    variability in grain size distribution among the samples.</li>
                </ul>
                """

                all_k_values = list(mean_k_by_sample.values())
                mean_all = np.mean(all_k_values)
                std_all = np.std(all_k_values)

                html += f"""
                <p><strong>Statistical Overview:</strong></p>
                <ul>
                    <li>Average sample K geometric mean: {mean_all:.2e} m/s</li>
                    <li>Standard deviation: {std_all:.2e} m/s</li>
                    <li>Coefficient of variation: {(std_all/mean_all)*100:.1f}%</li>
                </ul>
                """

            html += """
            </div>
            """

            if metadata.get('notes'):
                html += f"""
                <div class="info-box">
                    <h3>Additional Notes</h3>
                    <p>{self._note_html(metadata['notes'])}</p>
                </div>
                """

            html += "</div>"

        html += """
            <div class="footer">
                <span><strong>Multi-Sample Comparison Report</strong></span>
                <span>Generated by Grain Size Analysis &amp; Hydraulic Conductivity Calculator</span>
            </div>
        </body>
        </html>
        """

        return html

    # Helper methods
    def _classify_uniformity(self, cu: Optional[float]) -> str:
        if cu is None:
            return "Cannot calculate"
        return _gc_cu_label(cu)

    def _classify_curvature(self, cc: Optional[float]) -> str:
        if cc is None:
            return "Cannot calculate"
        lbl = _gc_cc_label(cc)
        if lbl == "Well-graded range":
            return "Well-graded (1 \u2264 Cc \u2264 3)"
        return "Gap-graded or Uniform"

    def _create_percentiles_table(self, dataset: GrainSizeData) -> str:
        """Generate HTML table with percentiles (D5, D10, D16, D20, D25, D30, D40, D50, D60, D75, D84, D90, D95)"""
        percentiles_list = [5, 10, 16, 20, 25, 30, 40, 50, 60, 75, 84, 90, 95]
        percentiles_dict = self._calculate_percentile_values(dataset, percentiles_list)
        max_val = max((value for value in percentiles_dict.values() if value is not None), default=0)

        html = """
        <table>
            <thead>
                <tr>
                    <th>Percentile</th>
                    <th>Size (mm)</th>
                    <th>Relative (%)</th>
                </tr>
            </thead>
            <tbody>
        """

        for p in percentiles_list:
            val = percentiles_dict[p]
            bar_width = int((val / max_val) * 100) if val is not None and max_val > 0 else 0

            # Highlight key percentiles (D10, D30, D50, D60)
            is_key = p in [10, 30, 50, 60]

            html += f"""
            <tr>
                <td style="text-align: center;"><strong>D{p}{'*' if is_key else ''}</strong></td>
                <td style="text-align: right;">{f'{val:.3f}' if val is not None else 'N/A'}</td>
                <td style="text-align: right;">{bar_width}%</td>
            </tr>
            """

        html += "</tbody></table>"
        return html

    def _create_gradation_table(self, dataset: GrainSizeData, scheme=None) -> str:
        """Generate HTML table showing gradation breakdown using scheme boundaries."""
        s = scheme if scheme is not None else ISO14688

        # Use the dataset's own classification to get accurate fractions
        try:
            result = dataset.classify(scheme=s)
            fracs = result.fractions
            gravel_percent = fracs.gravel_pct + getattr(fracs, 'cobble_pct', 0)
            sand_percent   = fracs.sand_pct
            fines_percent  = fracs.silt_pct + fracs.clay_pct
        except Exception:
            # Fallback to 0 if classification fails
            gravel_percent = sand_percent = fines_percent = 0.0

        silt_bnd = s.silt_max
        sand_bnd = s.sand_max

        html = f"""
        <table>
            <thead>
                <tr>
                    <th>Fraction</th>
                    <th>Size Range ({s.name})</th>
                    <th>Percentage</th>
                </tr>
            </thead>
            <tbody>
        """

        gradations = [
            ("Gravel", f"> {sand_bnd} mm",                  gravel_percent),
            ("Sand",   f"{silt_bnd} \u2013 {sand_bnd} mm", sand_percent),
            ("Fines",  f"< {silt_bnd} mm",                  fines_percent),
        ]

        for name, size_range, percent in gradations:
            html += f"""
            <tr>
                <td><strong>{name}</strong></td>
                <td>{size_range}</td>
                <td style="text-align: right;"><strong>{percent:.1f}%</strong></td>
            </tr>
            """

        html += "</tbody></table>"
        return html

    def _create_k_statistics_table(self, k_results: List[KCalculationResult]) -> str:
        """Generate HTML table with K-value statistics: Method, K-value, Status, Applicability Range"""
        html = """
        <table>
            <tr>
                <th>Method</th>
                <th>K-Value (m/s)</th>
                <th>Status</th>
                <th>Applicability Notes</th>
            </tr>
        """

        for result in k_results:
            status_text = classify_k_status(result)
            k_display = f"{result.k_value:.2e}" if result.k_value else "N/A"
            notes = result.status_message if hasattr(result, 'status_message') and result.status_message else str(result.status)

            html += f"""
            <tr>
                <td><strong>{result.method_name}</strong></td>
                <td style="text-align: right;">{k_display}</td>
                <td style="text-align: center;">{status_text}</td>
                <td>{notes}</td>
            </tr>
            """

        html += "</table>"
        return html

    def _create_comparison_k_scope_summary_table(self, comparison_snapshot) -> str:
        """Generate grouped/dataset K summaries from the shared aggregation snapshot."""
        k_report = comparison_snapshot.k
        grouped = self._comparison_uses_grouped_k_scope(comparison_snapshot)
        rows = [("Overall", k_report.overall)]
        if grouped:
            rows.extend(
                (group_name, k_report.by_group.get(group_name))
                for group_name in k_report.group_names
            )
        else:
            rows.extend(
                (dataset_name, k_report.by_dataset.get(dataset_name))
                for dataset_name in k_report.dataset_names
            )

        def fmt_k(value):
            return "N/A" if value is None else f"{value:.2e}"

        def fmt_float(value, precision=2):
            return "N/A" if value is None else f"{value:.{precision}f}"

        html = """
        <table>
            <thead>
                <tr>
                    <th>Scope</th>
                    <th>Datasets</th>
                    <th>K geometric mean (m/s)</th>
                    <th>K arithmetic mean (m/s)</th>
                    <th>K median (m/s)</th>
                    <th>ln(K) std dev</th>
                    <th>Included K cells</th>
                    <th>Warning cells</th>
                    <th>Permeability class</th>
                </tr>
            </thead>
            <tbody>
        """

        written = 0
        for scope_name, stats in rows:
            if stats is None:
                continue
            permeability = (
                _gc_perm_class(stats.geometric_mean_m_s)
                if stats.geometric_mean_m_s is not None
                else "N/A"
            )
            html += f"""
                <tr>
                    <td><strong>{self._esc(scope_name)}</strong></td>
                    <td style="text-align: right;">{stats.dataset_count}</td>
                    <td style="text-align: right;">{fmt_k(stats.geometric_mean_m_s)}</td>
                    <td style="text-align: right;">{fmt_k(stats.arithmetic_mean_m_s)}</td>
                    <td style="text-align: right;">{fmt_k(stats.median_m_s)}</td>
                    <td style="text-align: right;">{fmt_float(stats.ln_std_dev, 3)}</td>
                    <td style="text-align: center;">{stats.included_count} / {stats.total_cells}</td>
                    <td style="text-align: center;">{stats.warning_count}</td>
                    <td>{self._esc(permeability)}</td>
                </tr>
            """
            written += 1

        if written == 0:
            html += """
                <tr>
                    <td colspan="9" style="text-align: center;">No included K-value results available</td>
                </tr>
            """

        html += "</tbody></table>"
        return html

    def _create_comparison_k_statistics_table(self, k_results_dict: Dict[str, List[KCalculationResult]]) -> str:
        """Generate a multi-sample table with one row per K method result."""
        html = """
        <table>
            <thead>
                <tr>
                    <th>Sample</th>
                    <th>Method</th>
                    <th>K (m/s)</th>
                    <th>K (m/d)</th>
                    <th>Status</th>
                    <th>Included in Mean</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
        """

        row_count = 0
        for sample_name, results in k_results_dict.items():
            if not results:
                html += f"""
                <tr>
                    <td><strong>{self._esc(sample_name)}</strong></td>
                    <td colspan="6" style="text-align: center;">No K-value results available</td>
                </tr>
                """
                continue

            for result in results:
                status_text = classify_k_status(result)
                k_value = getattr(result, "k_value", None)
                has_value = k_value is not None and np.isfinite(k_value) and k_value > 0
                k_ms = f"{k_value:.2e}" if has_value else "N/A"
                k_md = f"{k_value * 86400.0:.2f}" if has_value else "N/A"
                included = has_value and status_text == "OK"
                notes = getattr(result, "status_message", "") or status_text

                html += f"""
                <tr>
                    <td><strong>{self._esc(sample_name)}</strong></td>
                    <td>{self._esc(getattr(result, "method_name", ""))}</td>
                    <td style="text-align: right;">{k_ms}</td>
                    <td style="text-align: right;">{k_md}</td>
                    <td style="text-align: center;">{self._esc(status_text)}</td>
                    <td style="text-align: center;">{"Yes" if included else "No"}</td>
                    <td>{self._esc(notes)}</td>
                </tr>
                """
                row_count += 1

        if row_count == 0:
            html += """
            <tr>
                <td colspan="7" style="text-align: center;">No K-value results available</td>
            </tr>
            """

        html += "</tbody></table>"
        return html

    def _create_data_quality_table(self, dataset: GrainSizeData) -> str:
        """Generate HTML table showing data quality metrics"""
        n_points = len(dataset.particle_sizes)
        size_min = min(dataset.particle_sizes)
        size_max = max(dataset.particle_sizes)
        size_range = size_max / size_min if size_min > 0 else 0

        # Check monotonicity
        sorted_indices = np.argsort(dataset.particle_sizes)[::-1]
        sorted_passing = [dataset.percent_passing[i] for i in sorted_indices]

        monotonic = all(sorted_passing[i] >= sorted_passing[i+1] for i in range(len(sorted_passing)-1))
        monotonicity_score = "Excellent" if monotonic else "Good"

        # Data coverage (log scale)
        coverage_score = "Excellent" if size_range > 100 else "Good" if size_range > 10 else "Limited"

        # Point density
        avg_spacing = np.mean([abs(dataset.particle_sizes[i] - dataset.particle_sizes[i-1])
                               for i in range(1, len(dataset.particle_sizes))])
        density_score = "Excellent" if n_points > 20 else "Good" if n_points > 10 else "Adequate"

        # Interpolation confidence
        confidence_score = "High" if (n_points > 15 and size_range > 50) else "Moderate" if n_points > 8 else "Low"

        html = """
        <table>
            <tr>
                <th>Quality Metric</th>
                <th>Value</th>
                <th>Assessment</th>
            </tr>
        """

        metrics = [
            ("Number of Data Points", str(n_points), density_score),
            ("Size Range", f"{size_min:.3f} - {size_max:.1f} mm", coverage_score),
            ("Span Ratio", f"{size_range:.1f}x", coverage_score),
            ("Curve Monotonicity", "Monotonic" if monotonic else "Some variation", monotonicity_score),
            ("Interpolation Confidence", "", confidence_score)
        ]

        for metric, value, assessment in metrics:
            # Color code assessment
            if assessment in ["Excellent", "High"]:
                color = "#e8f5e9"
            elif assessment in ["Good", "Moderate"]:
                color = "#fff9e6"
            else:
                color = "#ffebee"

            html += f"""
            <tr>
                <td style="font-weight: bold;">{metric}</td>
                <td>{value}</td>
                <td style="background-color: {color}; text-align: center;">{assessment}</td>
            </tr>
            """

        html += "</table>"
        return html

    def _create_grain_parameters_comparison_table(self, datasets: List[GrainSizeData],
                                                  sample_labels: Optional[List[str]] = None) -> str:
        """Generate HTML comparison table with color-coded cells showing D10, D50, D60, Cu, Cc for all samples"""
        labels = sample_labels or [dataset.sample_name for dataset in datasets]
        param_specs = [
            ("D10 (mm)", lambda ds: ds.get_d10(), ".3f"),
            ("D50 (mm)", lambda ds: ds.get_d50(), ".3f"),
            ("D60 (mm)", lambda ds: ds.get_d60(), ".3f"),
            ("Cu", lambda ds: ds.get_uniformity_coefficient(), ".2f"),
            ("Cc", lambda ds: ds.get_coefficient_of_curvature(), ".2f"),
        ]

        def fmt_value(value: Optional[float], fmt: str) -> str:
            return "-" if value is None else format(value, fmt)

        values_by_param = []
        for param, getter, fmt in param_specs:
            values = []
            for dataset in datasets:
                try:
                    values.append(getter(dataset))
                except Exception:
                    values.append(None)
            valid_values = [v for v in values if v is not None]
            if valid_values:
                mean = float(np.mean(valid_values))
                std = float(np.std(valid_values))
                summary = f"Mean: {format(mean, fmt)}<br>Std: {format(std, fmt)}"
            else:
                summary = "-"
            values_by_param.append((param, fmt, values, summary))

        if len(datasets) > 6:
            html = """
            <table class="table-compact">
                <thead>
                    <tr>
                        <th>Parameter</th>
                        <th>Sample</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
            """
            for param, fmt, values, summary in values_by_param:
                for label, value in zip(labels, values):
                    html += f"""
                    <tr>
                        <td><strong>{self._esc(param)}</strong></td>
                        <td>{self._esc(label)}</td>
                        <td style="text-align: right;">{self._esc(fmt_value(value, fmt))}</td>
                    </tr>
                    """
                html += f"""
                <tr>
                    <td><strong>{self._esc(param)} summary</strong></td>
                    <td>Included samples</td>
                    <td style="text-align: right;">{summary}</td>
                </tr>
                """
            html += "</tbody></table>"
            return html

        html = """
        <table class="table-compact table-wide">
            <thead>
                <tr>
                    <th>Parameter</th>
        """
        for label in labels:
            html += f"<th>{self._esc(label)}</th>"
        html += "<th>Statistics</th></tr></thead><tbody>"

        for param, fmt, values, summary in values_by_param:
            html += f"<tr><td style='font-weight: bold;'>{self._esc(param)}</td>"
            for value in values:
                html += f"<td style='text-align: center;'>{self._esc(fmt_value(value, fmt))}</td>"
            html += f"<td style='text-align: center; font-size: 9pt;'>{summary}</td></tr>"

        html += "</tbody></table>"
        return html

        html = """
        <table class="table-compact table-wide">
            <thead>
            <tr>
                    <th>Parameter</th>
        """

        # Add column headers for each dataset
        labels = sample_labels or [dataset.sample_name for dataset in datasets]
        for label in labels:
            html += f"<th>{self._esc(label)}</th>"

        # Add statistics column
        html += "<th>Statistics</th>"
        html += """
                </tr>
            </thead>
            <tbody>
        """

        # Parameters to compare
        params = ["D₁₀ (mm)", "D₅₀ (mm)", "D₆₀ (mm)", "Cu", "Cc"]

        for param in params:
            html += f"<tr><td style='font-weight: bold;'>{param}</td>"

            # Collect values for this parameter using dataset accessors
            values = []
            for dataset in datasets:
                if param == "D₁₀ (mm)":
                    val = dataset.get_d10()
                elif param == "D₅₀ (mm)":
                    val = dataset.get_d50()
                elif param == "D₆₀ (mm)":
                    val = dataset.get_d60()
                elif param == "Cu":
                    val = dataset.get_uniformity_coefficient()
                elif param == "Cc":
                    val = dataset.get_coefficient_of_curvature()
                else:
                    val = None

                values.append(val)

            # Filter valid values for statistics and color-coding
            valid_values = [v for v in values if v is not None]

            # Calculate color scale
            if len(valid_values) > 1:
                min_val = min(valid_values)
                max_val = max(valid_values)
                val_range = max_val - min_val
            else:
                min_val = max_val = val_range = 0

            # Add cells without color-coding (clean and simple)
            for val in values:
                if val is None:
                    html += "<td style='text-align: center;'>—</td>"
                else:
                    display_val = f"{val:.3f}" if param.endswith("(mm)") else f"{val:.2f}"
                    html += f"<td style='text-align: center;'>{display_val}</td>"

            # Add statistics column
            if valid_values:
                mean = np.mean(valid_values)
                std = np.std(valid_values)

                stats_text = f"Mean: {mean:.2f}<br>Std: {std:.2f}"
                html += f"<td style='text-align: center; font-size: 9pt;'>{stats_text}</td>"
            else:
                html += "<td style='text-align: center;'>—</td>"

            html += "</tr>"

        html += "</tbody></table>"
        return html

    def _create_permeability_classification_table(self, k_results_dict: Dict[str, List[KCalculationResult]]) -> str:
        """Generate HTML table with sample name, K geometric mean, and classification."""
        html = """
        <table>
            <thead>
                <tr>
                    <th>Sample Name</th>
                    <th>K geometric mean (m/s)</th>
                    <th>Classification</th>
                </tr>
            </thead>
            <tbody>
        """

        for sample_name, results in k_results_dict.items():
            summary = build_k_result_summary(results, dataset_name=sample_name)

            if summary.geometric_mean_m_s is not None:
                mean_k = summary.geometric_mean_m_s

                classification = _gc_perm_class(mean_k)

                html += f"""
                <tr>
                    <td><strong>{sample_name}</strong></td>
                    <td style="text-align: right;">{mean_k:.2e}</td>
                    <td>{classification}</td>
                </tr>
                """
            else:
                html += f"""
                <tr>
                    <td><strong>{sample_name}</strong></td>
                    <td style="text-align: center;">—</td>
                    <td style="text-align: center;">—</td>
                </tr>
                """

        html += "</tbody></table>"
        return html

    def _classify_permeability(self, k: float) -> str:
        return _gc_perm_class(k)

    def _get_permeability_application(self, k: float) -> str:
        if k > 1e-2:
            return "Excellent for drainage, unsuitable for water retention"
        elif k > 1e-4:
            return "Good for drainage systems, aquifers"
        elif k > 1e-5:
            return "Suitable for sand filters, moderate drainage"
        elif k > 1e-7:
            return "Poor drainage, may require improvement for construction"
        elif k > 1e-9:
            return "Natural barrier, suitable for liner with treatment"
        else:
            return "Excellent barrier material, natural aquitard"

    def _interpret_grain_distribution(self, dataset: GrainSizeData, cu: Optional[float], cc: Optional[float]) -> str:
        interpretation = f"The sample '{dataset.sample_name}' has been classified as {dataset.classify(scheme=self._scheme).label}. "

        if cu:
            cu_class = _gc_cu_label(cu)
            if cu_class == "Uniform":
                interpretation += "The uniform gradation (Cu < 4) indicates particles of similar size, "
                interpretation += "which typically results in higher void ratios and permeability. "
            elif cu_class == "Moderately graded":
                interpretation += "The moderate gradation (4 ≤ Cu < 6) suggests a reasonable distribution of particle sizes. "
            else:
                interpretation += "The well-graded nature (Cu ≥ 6) indicates a wide range of particle sizes, "
                interpretation += "which typically results in better compaction and lower permeability. "

        if cc and cu and cu >= 6:
            if 1 <= cc <= 3:
                interpretation += "The coefficient of curvature confirms well-graded material with good particle size distribution. "
            else:
                interpretation += "However, the coefficient of curvature suggests some gap-grading in the distribution. "

        return interpretation

    def _interpret_k_variability(self, ratio: float) -> str:
        if ratio < 10:
            return "The relatively low variability between methods suggests consistent and reliable results."
        elif ratio < 100:
            return "Moderate variability between methods is typical for this type of analysis. Consider using the median value."
        else:
            return "High variability between methods indicates uncertainty. Review input parameters and consider site-specific calibration."

    def _generate_no_results_report(self, sample_name: str) -> str:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>K-Value Report - {sample_name}</title>
            {self.report_style}
        </head>
        <body>
            <h1>Hydraulic Conductivity Analysis Report</h1>
            <div class="warning-box">
                <h3>No Valid Results</h3>
                <p>No valid K-value calculations were obtained for sample '{sample_name}'.</p>
                <p>This may be due to:</p>
                <ul>
                    <li>Grain size parameters outside method applicability ranges</li>
                    <li>Missing required grain size data (D10, D60, etc.)</li>
                    <li>Invalid input parameters</li>
                </ul>
                <p>Please review the input data and ensure all required parameters are available.</p>
            </div>
        </body>
        </html>
        """
