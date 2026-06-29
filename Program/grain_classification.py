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


@dataclass(frozen=True)
class DetailedFraction:
    """One sub-class band of the detailed grain-size breakdown.

    ``pct`` is the mass percentage of the sample whose grain size falls within
    ``[lower_mm, upper_mm)``.
    """
    label: str
    lower_mm: float
    upper_mm: float
    pct: float = 0.0


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

    # ── Detailed (sub-class) breakdown ────────────────────────────────────
    # For ISO 14688 this is the 11-band fine/medium/coarse scale; for other
    # schemes it falls back to the scheme's coarse classes.  detailed_class is
    # the dominant (largest-mass) sub-class, e.g. "Fine sand".
    detailed_fractions: tuple = ()          # tuple[DetailedFraction, ...]
    detailed_class:     str   = "—"

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


# ─────────────────────────────────────────────────────────────────────────────
# DETAILED (SUB-CLASS) GRAIN-SIZE BANDS
# ─────────────────────────────────────────────────────────────────────────────
# The detailed fine/medium/coarse subdivision is an ISO 14688 concept.  Each
# band is (lower_mm, upper_mm, label) with the lower bound inclusive.  This is
# the single source of truth shared by the plot ruler, the Statistics tab and
# the report/export builders.
ISO_FRACTION_BANDS: tuple[tuple[float, float, str], ...] = (
    (0.0,    0.002,  "Clay"),
    (0.002,  0.0063, "Fine silt"),
    (0.0063, 0.02,   "Medium silt"),
    (0.02,   0.063,  "Coarse silt"),
    (0.063,  0.2,    "Fine sand"),
    (0.2,    0.63,   "Medium sand"),
    (0.63,   2.0,    "Coarse sand"),
    (2.0,    6.3,    "Fine gravel"),
    (6.3,    20.0,   "Medium gravel"),
    (20.0,   63.0,   "Coarse gravel"),
    (63.0,   200.0,  "Cobble"),
)


def scheme_detail_bands(
    scheme: Optional[GrainClassificationScheme] = None,
) -> tuple[tuple[float, float, str], ...]:
    """Return the sub-class bands appropriate to *scheme*.

    ISO 14688 (and ``None``) get the full 11-band fine/medium/coarse scale.
    Other schemes (USCS, custom) do not define a size-based subdivision, so they
    fall back to their five coarse classes derived from the scheme boundaries.
    """
    if scheme is None or getattr(scheme, "key", "iso14688") == "iso14688":
        return ISO_FRACTION_BANDS

    clay_max   = float(getattr(scheme, "clay_max",   0.002))
    silt_max   = float(getattr(scheme, "silt_max",   0.063))
    sand_max   = float(getattr(scheme, "sand_max",   2.0))
    gravel_max = float(getattr(scheme, "gravel_max", 63.0))
    return (
        (0.0,        clay_max,   "Clay"),
        (clay_max,   silt_max,   "Silt"),
        (silt_max,   sand_max,   "Sand"),
        (sand_max,   gravel_max, "Gravel"),
        (gravel_max, max(gravel_max * 4.0, 300.0), "Cobble"),
    )


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


def compute_detailed_fractions(
    particle_sizes: list[float],
    percent_passing: list[float],
    scheme: Optional[GrainClassificationScheme] = None,
) -> tuple[DetailedFraction, ...]:
    """Compute the mass percentage in each detailed sub-class band.

    Uses the same log-linear interpolation as :func:`compute_fractions`, applied
    at every band boundary, then takes successive differences.  The bands are
    chosen by :func:`scheme_detail_bands`, so the result respects the active
    classification scheme (stratigraphy).  Percentages sum to ~100 and align
    with the coarse fractions from :func:`compute_fractions`.
    """
    bands = scheme_detail_bands(scheme)

    if not particle_sizes or not percent_passing:
        return tuple(DetailedFraction(label, lo, hi, 0.0) for lo, hi, label in bands)

    out: list[DetailedFraction] = []
    cum_prev = 0.0  # cumulative % passing at the previous band's upper edge
    for lo, hi, label in bands:
        pct_at_hi = interpolate_at(particle_sizes, percent_passing, hi)
        # interpolate_at returns None only when the boundary is coarser than the
        # measured range; everything passes, so cumulative passing is 100%.
        cum_hi = 100.0 if pct_at_hi is None else max(0.0, pct_at_hi)
        band_pct = max(0.0, cum_hi - cum_prev)
        out.append(DetailedFraction(label, lo, hi, round(band_pct, 1)))
        cum_prev = cum_hi

    return tuple(out)


def dominant_detail_class(detailed: tuple[DetailedFraction, ...]) -> str:
    """Return the label of the largest-mass sub-class, or '—' if none."""
    present = [d for d in detailed if d.pct > 0.0]
    if not present:
        return "—"
    return max(present, key=lambda d: d.pct).label


def sedimentology_descriptor(
    fractions: GrainFractions,
    d50_mm: Optional[float],
    cu: Optional[float],
    scheme: Optional[GrainClassificationScheme] = None,
) -> str:
    """Build a compound sedimentology-style descriptor.

    Example: ``"Moderately well sorted gravelly sand with fines"``.

    This is an optional descriptive overlay (Wentworth/sedimentology style),
    complementary to the ISO/USCS label:

    * primary type — from D50 (median) against the scheme boundaries;
    * modifiers    — secondary major fractions >= 10 %, listed finest-first
                     (clayey / silty / sandy / gravelly);
    * sorting      — Cu-based.  NOTE the inverse terminology: a high Cu reads as
                     "poorly sorted" here but "well-graded" in geotechnical use;
    * fines flag   — triggered at >= 5 % passing the silt/clay (fines) boundary.

    Returns "" when D50 is unavailable.
    """
    if d50_mm is None or d50_mm <= 0:
        return ""
    if scheme is None:
        scheme = ISO14688

    # Primary type from the median grain size.
    if d50_mm >= scheme.sand_max:
        primary = "gravel"
    elif d50_mm >= scheme.silt_max:
        primary = "sand"
    elif d50_mm >= scheme.clay_max:
        primary = "silt"
    else:
        primary = "clay"

    # Secondary modifiers: major fractions (excluding the primary) >= 10 %,
    # listed finest -> coarsest.
    adjective = {"clay": "clayey", "silt": "silty", "sand": "sandy", "gravel": "gravelly"}
    pct = {
        "clay":   fractions.clay_pct,
        "silt":   fractions.silt_pct,
        "sand":   fractions.sand_pct,
        "gravel": fractions.gravel_pct + fractions.cobble_pct,
    }
    modifiers = [
        adjective[k]
        for k in ("clay", "silt", "sand", "gravel")
        if k != primary and pct[k] >= 10.0
    ]

    # Sorting from Cu.
    if cu is None:
        sorting = ""
    elif cu < 2.0:
        sorting = "Uniform"
    elif cu < 5.0:
        sorting = "Moderately well sorted"
    else:
        sorting = "Poorly sorted"

    fines = "with fines" if fractions.fines_pct >= 5.0 else "low in fines"

    parts = [p for p in (sorting, " ".join(modifiers), primary, fines) if p]
    text = " ".join(parts)
    return text[:1].upper() + text[1:] if text else ""


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
            detailed_fractions = (),
            detailed_class     = "—",
        )

    fractions = compute_fractions(particle_sizes, percent_passing, scheme)
    detailed = compute_detailed_fractions(particle_sizes, percent_passing, scheme)

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
        detailed_fractions = detailed,
        detailed_class     = dominant_detail_class(detailed),
    )
