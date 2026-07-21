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
    logo_path:     str = ""         # absolute path to PNG/JPG/SVG; empty = no cover image
    primary_color: str = "#990000"  # DTU red

    # ── Logo helpers ──────────────────────────────────────────────────────────

    def get_logo_html(self, height_px: int = 60) -> str:
        """Return an embedded, bounded logo image or an empty string."""
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
                f'class="cover-logo-image" '
                f'style="max-height:{height_px}px;max-width:220px;'
                f'width:auto;height:auto;object-fit:contain;display:block;" '
                f'alt="Organization logo">'
            )
        return ""

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
