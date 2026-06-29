"""
Shared per-sample "calculation internals" echo (no Qt dependency).

These are the intermediate values behind the K-value methods — water physical
constants at the sample temperature, the per-method effective diameters, the
phi-unit / Folk-Ward sorting inputs and the porosity functions — rendered as
labelled display rows.

The Statistics tab, the report generator and the export manager all build these
from this one module so the numbers (and their formatting) never drift apart.
Values echo the exact engine helpers in k_calculations rather than re-deriving
the formulas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from k_calculations import KCalculator


_PHI_PERCENTILES = (5, 16, 50, 84, 95)

# Group titles — single source so the Statistics tab, report and export labels
# never drift apart.
TITLE_CONSTANTS = "Physical constants"
TITLE_DIAMETERS = "Effective diameters dₑ"
TITLE_SORTING = "Sorting (φ units · Krumbein-Monk input)"
TITLE_POROSITY = "Porosity functions fₙ"


@dataclass(frozen=True)
class InternalsGroup:
    """One titled block of (label, value) display rows."""
    title: str
    rows: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CalculationInternals:
    physical_constants: InternalsGroup
    effective_diameters: InternalsGroup
    phi_folk_ward: InternalsGroup
    porosity_functions: InternalsGroup

    def groups(self) -> tuple[InternalsGroup, ...]:
        return (
            self.physical_constants,
            self.effective_diameters,
            self.phi_folk_ward,
            self.porosity_functions,
        )


def _percentiles(calc: KCalculator, grain_data: dict, wanted) -> dict:
    out: dict[int, float] = {}
    for p in wanted:
        value = calc._interpolate_percentile(grain_data, float(p))
        if value:
            out[p] = value
    return out


def compute_calculation_internals(
    particle_sizes: Sequence[float],
    percent_passing: Sequence[float],
    temperature: float,
    porosity: Optional[float],
) -> CalculationInternals:
    """Compute the four calculation-internals groups for one sample."""
    calc = KCalculator()
    grain_data = {
        "particle_sizes": list(particle_sizes or []),
        "percent_passing": list(percent_passing or []),
    }
    T = float(temperature)
    n = porosity if porosity else None
    pct = _percentiles(calc, grain_data, (5, 10, 16, 50, 84, 95))

    # ── Physical constants @ T ──────────────────────────────────────────
    try:
        rho = calc._water_density(T)
        mu = calc._water_viscosity(T)
        rho_g_mu = calc._rho_g_over_mu(T)
        tau = 1.093e-4 * T ** 2 + 2.102e-2 * T + 0.5889  # Sauerbrei τ(T)
        corr = calc._apply_temperature_correction(1.0, T)
        const_rows: list[tuple[str, str]] = [
            ("g (gravity)", "980 cm/s²"),
            ("ρ water density", f"{rho:.4f} g/cm³"),
            ("μ water viscosity", f"{mu:.5f} g/(cm·s)"),
            ("ρg/μ", f"{rho_g_mu:.3e} /(cm·s)"),
            ("τ (Sauerbrei)", f"{tau:.3f}"),
            ("Temp. correction", f"{corr:.3f} (20 °C ref)"),
        ]
    except Exception:
        const_rows = [("Physical constants", "unavailable")]

    # ── Effective diameters dₑ ──────────────────────────────────────────
    diam_rows: list[tuple[str, str]] = []
    kruger = calc._kruger_diameter_cm(grain_data)
    harmonic = calc._harmonic_mean_diameter_cm(grain_data)
    zunker = calc._zunker_diameter_cm(grain_data)
    zamarin = calc._zamarin_diameter_cm(grain_data)
    geom = calc._calculate_geometric_mean(grain_data)
    if kruger:
        diam_rows.append(("Kruger", f"{kruger:.4f} cm · {kruger * 10:.3f} mm"))
    if harmonic:
        diam_rows.append(("Kozeny-Carman (harmonic)", f"{harmonic:.4f} cm · {harmonic * 10:.3f} mm"))
    if zunker:
        diam_rows.append(("Zunker", f"{zunker:.4f} cm · {zunker * 10:.3f} mm"))
    if zamarin:
        diam_rows.append(("Zamarin", f"{zamarin:.4f} cm · {zamarin * 10:.3f} mm"))
    if geom:
        diam_rows.append(("Geometric mean d_geom", f"{geom:.4f} mm"))
    d10, d50 = pct.get(10), pct.get(50)
    if d10 and d50 and d50 != d10:
        io = -(10.0 - (40.0 / (d50 - d10)) * d10) * (d50 - d10) / 40.0
        de = io + 0.025 * (d50 - d10)
        diam_rows.append(("Alyamani-Sen Iₒ → dₑ", f"{io:.4f} → {de:.4f} mm"))
    if not diam_rows:
        diam_rows = [("Effective diameters", "insufficient data")]

    # ── φ units / Folk-Ward (Krumbein-Monk) ─────────────────────────────
    phi_rows: list[tuple[str, str]] = []
    phi_vals: dict[int, float] = {}
    for p in _PHI_PERCENTILES:
        d = pct.get(p)
        if d and d > 0:
            phi_vals[p] = math.log2(d)
            phi_rows.append((f"D{p} φ = log₂(d)", f"{phi_vals[p]:.2f}"))
    if {16, 84, 5, 95} <= set(phi_vals):
        sigma_phi = (phi_vals[84] - phi_vals[16]) / 4.0 + (phi_vals[95] - phi_vals[5]) / 6.6
        phi_rows.append(("σφ (sorting)", f"{sigma_phi:.2f}"))
    if not phi_rows:
        phi_rows = [("φ percentiles", "insufficient data")]

    # ── Porosity functions fₙ ───────────────────────────────────────────
    if n is not None and 0 < n < 1:
        poro_rows: list[tuple[str, str]] = [
            ("void ratio e = n/(1−n)", f"{calc._void_ratio(n):.3f}"),
            ("n/(1−n)²  (Kruger)", f"{calc._porosity_ratio(n):.3f}"),
            ("n³/(1−n)²  (Sauerbrei·K-C·Zamarin·Barr)", f"{calc._porosity_cubic_ratio(n):.3f}"),
            ("(n/(1−n))²  (Zunker)", f"{(n / (1 - n)) ** 2:.3f}"),
            ("Zamarin Cₙ = (1.275−1.5n)²", f"{max(0.0, (1.275 - 1.5 * n)) ** 2:.3f}"),
        ]
    else:
        poro_rows = [("Porosity functions", "porosity unavailable")]

    return CalculationInternals(
        physical_constants=InternalsGroup(TITLE_CONSTANTS, tuple(const_rows)),
        effective_diameters=InternalsGroup(TITLE_DIAMETERS, tuple(diam_rows)),
        phi_folk_ward=InternalsGroup(TITLE_SORTING, tuple(phi_rows)),
        porosity_functions=InternalsGroup(TITLE_POROSITY, tuple(poro_rows)),
    )
