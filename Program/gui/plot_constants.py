"""Shared constants and helpers for K-value and grain-size plotting.

Both the interactive plot widgets and the headless report exporter
import from here so that colours, method ordering, and status
classification logic stay consistent everywhere.
"""

from __future__ import annotations

from typing import Dict, List

from method_registry import DEFAULT_METHOD_ORDER, ordered_methods


# ── Method colours ────────────────────────────────────────────
# One colour per empirical K-calculation method, used in bar charts.

METHOD_COLORS: Dict[str, str] = {
    "Hazen":         "#b71c1c",  # Deep red
    "Terzaghi":      "#2e7d32",  # Forest green
    "Beyer":         "#1565c0",  # Deep blue
    "Slichter":      "#ef6c00",  # Deep orange
    "Kozeny-Carman": "#7b1fa2",  # Deep purple
    "Shepherd":      "#c2185b",  # Deep pink
    "Zunker":        "#00acc1",  # Teal
    "Zamarin":       "#fbc02d",  # Golden yellow
    "USBR":          "#6d4c41",  # Earth brown
    "Sauerbrei":     "#546e7a",  # Blue gray
    "Hazen_1892":    "#d84315",  # Deep orange red
    "Kruger":        "#4527a0",  # Deep indigo
    "Barr":          "#8d6e63",  # Medium brown
    "Alyamani-Sen":  "#5d4037",  # Dark brown
    "Chapuis":       "#ff5722",  # Deep orange-red
    "Krumbein-Monk": "#9c27b0",  # Purple
}

# ── Dataset colours ───────────────────────────────────────────
# Used when multiple datasets share the same axes (comparison plots).

DATASET_COLORS: List[str] = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


# ── Status classification ─────────────────────────────────────

def classify_k_status(result) -> str:
    """Normalise a KCalculationResult's status to 'OK', 'Warning', or 'Error'.

    Works for both enum-based (`result.status.value`) and string-based
    status fields.
    """
    status_str = result.status.value if hasattr(result.status, "value") else str(result.status)
    conditions_met = getattr(result, "conditions_met", True)

    if ("OK" in status_str or "WITHIN_RANGE" in status_str) and conditions_met:
        return "OK"
    if "WARNING" in status_str or "OUTSIDE_RANGE" in status_str or not conditions_met:
        return "Warning"
    return "Error"
