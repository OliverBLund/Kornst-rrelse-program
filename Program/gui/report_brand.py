"""Report branding configuration — organization identity for generated reports."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from PyQt6.QtCore import QSettings


@dataclass
class ReportBrand:
    """Organization branding settings injected into generated reports."""

    org_name:      str = "Danmarks Tekniske Universitet"
    org_subtitle:  str = "Department of Civil Engineering"
    logo_path:     str = ""         # absolute path to PNG/JPG/SVG; empty = SVG placeholder
    primary_color: str = "#990000"  # DTU red

    # ── Logo helpers ──────────────────────────────────────────────────────────

    def get_logo_html(self, height_px: int = 60) -> str:
        """Return an <img> tag embedding the logo, or a generated SVG placeholder."""
        if self.logo_path and os.path.exists(self.logo_path):
            ext = os.path.splitext(self.logo_path)[1].lower().lstrip(".")
            mime = {
                "png":  "image/png",
                "jpg":  "image/jpeg",
                "jpeg": "image/jpeg",
                "svg":  "image/svg+xml",
                "gif":  "image/gif",
            }.get(ext, "image/png")
            with open(self.logo_path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
            return (
                f'<img src="data:{mime};base64,{b64}" '
                f'style="height:{height_px}px;display:block;" alt="logo">'
            )
        return self._placeholder_svg(height_px)

    def _placeholder_svg(self, height_px: int) -> str:
        color = self.primary_color
        initials = "".join(w[0].upper() for w in self.org_name.split()[:3] if w)
        w, h = height_px * 2, height_px
        fs = int(h * 0.42)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">'
            f'<rect width="{w}" height="{h}" fill="{color}" rx="3"/>'
            f'<text x="{w // 2}" y="{int(h * 0.67)}" font-family="Arial,sans-serif" '
            f'font-size="{fs}" font-weight="bold" fill="white" '
            f'text-anchor="middle">{initials}</text>'
            f'</svg>'
        )
        b64 = base64.b64encode(svg.encode()).decode()
        return (
            f'<img src="data:image/svg+xml;base64,{b64}" '
            f'style="height:{height_px}px;display:block;" alt="logo">'
        )

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self) -> None:
        s = QSettings("GrainSizeAnalysis", "ReportBrand")
        s.setValue("org_name",      self.org_name)
        s.setValue("org_subtitle",  self.org_subtitle)
        s.setValue("logo_path",     self.logo_path)
        s.setValue("primary_color", self.primary_color)

    @staticmethod
    def load() -> ReportBrand:
        s = QSettings("GrainSizeAnalysis", "ReportBrand")
        return ReportBrand(
            org_name=      s.value("org_name",      "Danmarks Tekniske Universitet"),
            org_subtitle=  s.value("org_subtitle",  "Department of Civil Engineering"),
            logo_path=     s.value("logo_path",     ""),
            primary_color= s.value("primary_color", "#990000"),
        )
