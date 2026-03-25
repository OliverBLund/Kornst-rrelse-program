"""
grain_classification.py
=======================
Single source of truth for all soil grain-size classification logic.

Supported standard schemes
---------------------------
- ISO 14688-1:2017 / DS/EN ISO 14688  (default — Danish/European practice)
- USCS / ASTM D2487-17                (US standard, K-formula literature)
- Custom                              (user-defined boundaries)

All boundary values are in millimetres (mm).
Permeability (K) values are in metres per second (m/s).

References
----------
ISO 14688-1:2017  https://www.iso.org/standard/66012.html
ISO 14688-2:2017  https://www.iso.org/standard/66013.html
ASTM D2487-17     https://www.astm.org/d2487-17.html
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GrainClassificationScheme:
    """Defines a complete grain-size classification scheme.

    All boundary attributes are upper limits in mm (i.e. clay_max is the
    largest grain size still classified as clay).
    """
    key: str                            # "iso14688" | "uscs" | "custom"
    name: str                           # Human-readable name
    standard_ref: str                   # Bibliographic reference string
    url: str                            # Primary standard URL

    # ── Grain-size boundaries (mm) ────────────────────────────────────────
    clay_max: float    = 0.002          # Clay  upper limit
    silt_max: float    = 0.063          # Silt  upper limit  (ISO: 0.063 / USCS: 0.075)
    sand_max: float    = 2.0            # Sand  upper limit  (ISO: 2.0   / USCS: 4.75 )
    gravel_max: float  = 63.0           # Gravel upper limit (ISO: 63.0  / USCS: 75.0 )

    # ── Well-graded criteria (USCS Cu thresholds; None = not applicable) ──
    cu_well_graded_sand:   Optional[float] = None   # USCS: 6.0
    cu_well_graded_gravel: Optional[float] = None   # USCS: 4.0
    cc_min: float = 1.0                              # Curvature lower bound
    cc_max: float = 3.0                              # Curvature upper bound


@dataclass
class GrainFractions:
    """Grain-size fraction percentages derived from the gradation curve."""
    clay_pct:   float = 0.0
    silt_pct:   float = 0.0
    sand_pct:   float = 0.0
    gravel_pct: float = 0.0
    cobble_pct: float = 0.0
    scheme: Optional[GrainClassificationScheme] = field(default=None, repr=False)

    @property
    def fines_pct(self) -> float:
        """Clay + Silt combined (the fraction passing the finest sieve)."""
        return self.clay_pct + self.silt_pct


@dataclass
class ClassificationResult:
    """Structured result from classify().  All consumers should use this."""
    scheme: GrainClassificationScheme
    fractions: GrainFractions

    # ── Textual results ───────────────────────────────────────────────────
    primary_type: str           # "Sand" | "Gravel" | "Fine-grained" | ...
    gradation:    str           # "Well-graded" | "Poorly-graded" | ""
    uscs_symbol:  Optional[str] # "SW" | "GP" | None (ISO has no symbols)
    label:        str           # Full label, e.g. "Well-graded sand (SW)"
    cu_label:     str           # "Well-graded" | "Moderately graded" | "Uniform" | "—"
    cc_label:     str           # "Well-graded range" | "Outside range" | "—"
    permeability_class: str     # "High" | "Moderate" | ...

    def __str__(self) -> str:
        return self.label


# ─────────────────────────────────────────────────────────────────────────────
# STANDARD SCHEME INSTANCES
# ─────────────────────────────────────────────────────────────────────────────

ISO14688 = GrainClassificationScheme(
    key          = "iso14688",
    name         = "ISO 14688 / DS/EN ISO 14688",
    standard_ref = "ISO 14688-1:2017 · ISO 14688-2:2017",
    url          = "https://www.iso.org/standard/66012.html",
    clay_max     = 0.002,
    silt_max     = 0.063,
    sand_max     = 2.0,
    gravel_max   = 63.0,
    cu_well_graded_sand   = None,   # ISO does not define USCS-style well-graded criteria
    cu_well_graded_gravel = None,
    cc_min = 1.0,
    cc_max = 3.0,
)

USCS = GrainClassificationScheme(
    key          = "uscs",
    name         = "USCS / ASTM D2487",
    standard_ref = "ASTM D2487-17",
    url          = "https://www.astm.org/d2487-17.html",
    clay_max     = 0.002,
    silt_max     = 0.075,
    sand_max     = 4.75,
    gravel_max   = 75.0,
    cu_well_graded_sand   = 6.0,
    cu_well_graded_gravel = 4.0,
    cc_min = 1.0,
    cc_max = 3.0,
)

# Dict for look-up by key string
SCHEMES: dict[str, GrainClassificationScheme] = {
    "iso14688": ISO14688,
    "uscs":     USCS,
}


def make_custom_scheme(
    name: str,
    clay_max: float,
    silt_max: float,
    sand_max: float,
    gravel_max: float,
) -> GrainClassificationScheme:
    """Create a custom user-defined scheme."""
    return GrainClassificationScheme(
        key          = "custom",
        name         = name,
        standard_ref = "User-defined",
        url          = "",
        clay_max     = clay_max,
        silt_max     = silt_max,
        sand_max     = sand_max,
        gravel_max   = gravel_max,
        cu_well_graded_sand   = None,
        cu_well_graded_gravel = None,
        cc_min = 1.0,
        cc_max = 3.0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CORE INTERPOLATION  (log-linear, same algorithm as data_loader.py)
# ─────────────────────────────────────────────────────────────────────────────

def interpolate_at(
    particle_sizes: list[float],
    percent_passing: list[float],
    target_mm: float,
) -> Optional[float]:
    """Return % passing at *target_mm* via log-linear interpolation.

    particle_sizes and percent_passing must be the same length.
    Returns None if target is outside the data range or data is insufficient.
    """
    if len(particle_sizes) < 2:
        return None

    # Sort ascending by particle size
    pairs = sorted(zip(particle_sizes, percent_passing), key=lambda p: p[0])
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    if target_mm <= xs[0]:
        return ys[0]
    if target_mm > xs[-1]:
        # Beyond measured range — cannot extrapolate; caller decides the default
        return None

    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        y0, y1 = ys[i], ys[i + 1]
        if x0 <= target_mm <= x1:
            if x0 > 0 and x1 > 0:
                # Log-linear interpolation
                t = (math.log(target_mm) - math.log(x0)) / (math.log(x1) - math.log(x0))
            else:
                t = (target_mm - x0) / (x1 - x0) if x1 != x0 else 0.0
            return y0 + t * (y1 - y0)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# GRAIN FRACTIONS
# ─────────────────────────────────────────────────────────────────────────────

def compute_fractions(
    particle_sizes: list[float],
    percent_passing: list[float],
    scheme: GrainClassificationScheme,
) -> GrainFractions:
    """Compute clay/silt/sand/gravel/cobble fractions from the gradation curve.

    Uses log-linear interpolation at each scheme boundary, then takes
    differences to obtain the mass fraction in each class.
    """
    # % passing at each boundary
    pct_at_clay   = interpolate_at(particle_sizes, percent_passing, scheme.clay_max)
    pct_at_silt   = interpolate_at(particle_sizes, percent_passing, scheme.silt_max)
    pct_at_sand   = interpolate_at(particle_sizes, percent_passing, scheme.sand_max)
    pct_at_gravel = interpolate_at(particle_sizes, percent_passing, scheme.gravel_max)

    # Fall back to 0 / 100 at the extremes if out of range
    def _safe(v, default):
        return v if v is not None else default

    pct_clay_bnd   = _safe(pct_at_clay,   0.0)
    pct_silt_bnd   = _safe(pct_at_silt,   pct_clay_bnd)
    pct_sand_bnd   = _safe(pct_at_sand,   pct_silt_bnd)
    # Use 100.0 when gravel boundary is beyond the data range — the retained material
    # above the last measured sieve falls within the gravel zone, not cobble.
    pct_gravel_bnd = _safe(pct_at_gravel, 100.0)

    clay_pct   = max(0.0, pct_clay_bnd)
    silt_pct   = max(0.0, pct_silt_bnd   - pct_clay_bnd)
    sand_pct   = max(0.0, pct_sand_bnd   - pct_silt_bnd)
    gravel_pct = max(0.0, pct_gravel_bnd - pct_sand_bnd)
    cobble_pct = max(0.0, 100.0          - pct_gravel_bnd)

    return GrainFractions(
        clay_pct   = round(clay_pct,   1),
        silt_pct   = round(silt_pct,   1),
        sand_pct   = round(sand_pct,   1),
        gravel_pct = round(gravel_pct, 1),
        cobble_pct = round(cobble_pct, 1),
        scheme     = scheme,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SHARED CLASSIFICATION LADDERS
# ─────────────────────────────────────────────────────────────────────────────

def cu_label(cu: Optional[float]) -> str:
    """Return a gradation descriptor from the uniformity coefficient.

    Thresholds follow USCS / common geotechnical practice:
      Cu < 4      → Uniform
      4 ≤ Cu < 6  → Moderately graded
      Cu ≥ 6      → Well-graded
    """
    if cu is None:
        return "—"
    if cu < 4:
        return "Uniform"
    if cu < 6:
        return "Moderately graded"
    return "Well-graded"


def cc_label(cc: Optional[float], scheme: Optional[GrainClassificationScheme] = None) -> str:
    """Return a curvature descriptor from the coefficient of curvature."""
    if cc is None:
        return "—"
    cc_min = scheme.cc_min if scheme else 1.0
    cc_max = scheme.cc_max if scheme else 3.0
    if cc_min <= cc <= cc_max:
        return "Well-graded range"
    return "Outside range"


def permeability_class(k_ms: Optional[float]) -> str:
    """Return a human-readable permeability class from k (m/s).

    Based on standard soil permeability ranges (e.g. Freeze & Cherry, 1979).
    """
    if k_ms is None or k_ms <= 0:
        return "—"
    if k_ms > 1e-2:
        return "Very High (Gravel)"
    if k_ms > 1e-4:
        return "High (Clean Sand)"
    if k_ms > 1e-5:
        return "Moderate (Fine Sand)"
    if k_ms > 1e-7:
        return "Low (Silt)"
    if k_ms > 1e-9:
        return "Very Low (Clay-Silt)"
    return "Practically Impermeable (Clay)"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CLASSIFICATION FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def classify(
    particle_sizes: list[float],
    percent_passing: list[float],
    cu: Optional[float],
    cc: Optional[float],
    scheme: Optional[GrainClassificationScheme] = None,
    k_mean_ms: Optional[float] = None,
) -> ClassificationResult:
    """Classify soil using the given scheme.

    Parameters
    ----------
    particle_sizes  : list of grain sizes in mm
    percent_passing : corresponding % passing values
    cu              : uniformity coefficient (D60/D10), or None
    cc              : coefficient of curvature, or None
    scheme          : classification scheme; defaults to ISO14688
    k_mean_ms       : mean hydraulic conductivity in m/s (optional, for perm class)

    Returns
    -------
    ClassificationResult
    """
    if scheme is None:
        scheme = ISO14688

    if not particle_sizes or not percent_passing:
        return ClassificationResult(
            scheme           = scheme,
            fractions        = GrainFractions(scheme=scheme),
            primary_type     = "No data",
            gradation        = "",
            uscs_symbol      = None,
            label            = "Insufficient data for classification",
            cu_label         = "—",
            cc_label         = "—",
            permeability_class = "—",
        )

    fractions = compute_fractions(particle_sizes, percent_passing, scheme)

    # ── Primary type from dominant fraction ──────────────────────────────
    # Use the scheme's sand_max boundary: D50 or the dominant mass fraction
    # determines primary type.  We follow the dominant-fraction rule.
    dominant = max(
        ("Clay",   fractions.clay_pct),
        ("Silt",   fractions.silt_pct),
        ("Sand",   fractions.sand_pct),
        ("Gravel", fractions.gravel_pct),
        ("Cobble", fractions.cobble_pct),
        key=lambda t: t[1],
    )[0]

    # Map dominant to coarser grouping for gradation logic
    if dominant in ("Gravel", "Cobble"):
        primary_type = "Gravel"
    elif dominant == "Sand":
        primary_type = "Sand"
    else:
        primary_type = "Fine-grained"

    # ── Gradation (well-graded / poorly-graded) ───────────────────────────
    gradation   = ""
    uscs_symbol = None

    if primary_type in ("Sand", "Gravel") and cu is not None and cc is not None:
        if primary_type == "Sand":
            cu_threshold = scheme.cu_well_graded_sand
        else:
            cu_threshold = scheme.cu_well_graded_gravel

        if cu_threshold is not None:
            # USCS-style well-graded criterion
            cc_ok = scheme.cc_min <= cc <= scheme.cc_max
            if cu >= cu_threshold and cc_ok:
                gradation = "Well-graded"
            else:
                gradation = "Poorly-graded"
        elif cu >= 6 if primary_type == "Sand" else cu >= 4:
            # ISO has no formal criterion; use common descriptive thresholds
            gradation = "Well-graded"
        else:
            gradation = "Poorly-graded"
    elif primary_type in ("Sand", "Gravel"):
        gradation = ""  # Not enough data for gradation

    # ── USCS symbol (only for USCS scheme) ────────────────────────────────
    if scheme.key == "uscs" and primary_type in ("Sand", "Gravel"):
        prefix = "S" if primary_type == "Sand" else "G"
        if gradation == "Well-graded":
            suffix = "W"
        else:
            suffix = "P"
        uscs_symbol = prefix + suffix
    elif scheme.key == "uscs" and primary_type == "Fine-grained":
        # Without Atterberg limits we can only say ML/CL-like — use generic
        uscs_symbol = None  # Cannot determine without plasticity data

    # ── Human label ───────────────────────────────────────────────────────
    type_str = primary_type.lower()
    if gradation:
        label = f"{gradation} {type_str}"
    else:
        label = primary_type

    if uscs_symbol:
        label = f"{label} ({uscs_symbol})"

    # ── Permeability class ────────────────────────────────────────────────
    perm_class = permeability_class(k_mean_ms)

    return ClassificationResult(
        scheme             = scheme,
        fractions          = fractions,
        primary_type       = primary_type,
        gradation          = gradation,
        uscs_symbol        = uscs_symbol,
        label              = label,
        cu_label           = cu_label(cu),
        cc_label           = cc_label(cc, scheme),
        permeability_class = perm_class,
    )
