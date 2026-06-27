"""Regression tests for report accent colour propagation."""

from __future__ import annotations

import io
import sys

sys.path.insert(0, "Program")

from openpyxl import load_workbook

from gui.report_brand import ReportBrand
from report_generator import ReportGenerator
from report_tables import generate_excel_appendix


def test_html_report_css_uses_brand_accent():
    brand = ReportBrand(primary_color="#1f4e79")

    css = ReportGenerator()._get_branded_style(brand)

    assert "--brand:       #1f4e79;" in css
    assert "--brand-light: rgba(31,78,121,0.08);" in css


def test_excel_appendix_uses_report_accent():
    html = """
    <h3>Summary</h3>
    <table data-report-table="summary">
      <thead><tr><th>Method</th><th>Value</th></tr></thead>
      <tbody><tr><td>Hazen</td><td>1e-4</td></tr></tbody>
    </table>
    """

    workbook = load_workbook(
        io.BytesIO(generate_excel_appendix(html, accent_color="#1f4e79"))
    )
    header = workbook["Summary"]["A1"]

    assert header.font.color.rgb == "001F4E79"
    assert header.border.bottom.color.rgb == "001F4E79"
