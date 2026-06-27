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
# Single source of truth (warm-earth, consistent with the design spec): the
# Comparison tab, the comparison plot widget, the headless report/export spec
# builder and the renderer fallbacks all draw from this one palette so GUI and
# report/export colours match by construction.

DATASET_COLORS: List[str] = [
    "#3a7ea0",
    "#6b8e23",
    "#b46428",
    "#2a9d8f",
    "#8b4513",
    "#c45c2e",
    "#4a6fa5",
    "#5e7b1a",
    "#8b6914",
    "#2e6b7d",
]


# ── Palettes ──────────────────────────────────────────────────
# The dataset/group colours for comparison plots can be drawn from a chosen
# palette so reports/exports re-colour every multi-series plot at once. The
# "Categorical" default reuses DATASET_COLORS (so behaviour is unchanged unless
# a palette is picked); the others sample a perceptually-uniform matplotlib
# colormap to N evenly-spaced colours.

CATEGORICAL_PALETTE = "Categorical"
# Display name → matplotlib colormap key. Turbo/viridis-family are perceptually
# uniform; "Grayscale" (the 'gray' map) is for black-and-white printing.
_PALETTE_CMAPS: Dict[str, str] = {
    "Viridis": "viridis",
    "Plasma": "plasma",
    "Inferno": "inferno",
    "Cividis": "cividis",
    "Turbo": "turbo",
    "Grayscale": "gray",
}
PALETTE_NAMES: List[str] = [CATEGORICAL_PALETTE] + list(_PALETTE_CMAPS)

# Per-palette sampling window (fraction of the colormap to use). Trimming the
# endpoints keeps the extreme-dark/-light ends legible against a white plot;
# grayscale stops well short of white so every shade stays visible.
_DEFAULT_PALETTE_RANGE = (0.06, 0.94)
_PALETTE_RANGES: Dict[str, tuple] = {
    "Grayscale": (0.0, 0.62),
}


def palette_colors(name: str, n: int) -> List[str]:
    """Return *n* distinct hex colours for a palette *name*.

    "Categorical" cycles the canonical DATASET_COLORS (matching the GUI by
    construction); any colormap palette samples that matplotlib colormap at *n*
    evenly-spaced points across the palette's sampling window, so the colours are
    spread over the FULL map (sampling to the actual series count is the caller's
    job — under-sampling clusters everything at one end). Unknown names fall back
    to Categorical. ``n <= 0`` yields an empty list.
    """
    count = max(0, int(n))
    if count == 0:
        return []
    key = str(name or "").strip()
    cmap_name = next(
        (cmap for disp, cmap in _PALETTE_CMAPS.items() if disp.lower() == key.lower()),
        None,
    )
    if cmap_name is not None:
        try:
            import numpy as np
            from matplotlib import colormaps
            from matplotlib.colors import to_hex

            cmap = colormaps[cmap_name]
            display = next(d for d in _PALETTE_CMAPS if d.lower() == key.lower())
            lo, hi = _PALETTE_RANGES.get(display, _DEFAULT_PALETTE_RANGE)
            stops = [(lo + hi) / 2] if count == 1 else list(np.linspace(lo, hi, count))
            return [to_hex(cmap(stop)) for stop in stops]
        except (KeyError, ValueError, ImportError, StopIteration):
            pass  # Unknown/unavailable colormap → categorical fallback.
    return [DATASET_COLORS[i % len(DATASET_COLORS)] for i in range(count)]


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
