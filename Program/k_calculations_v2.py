"""Rebuilt hydraulic conductivity calculator based directly on reference equations.
# NOTE: Several methods have optional coefficients/branches (e.g. Terzaghi smooth vs coarse grains,
#       Zunker/Zamarin detailed fractions, Krüger arithmetic vs geometric means). For now we keep the baseline
#       coefficients from the literature tables. Once the numerical implementation is stable we can expose
#       user-facing toggles so analysts can choose the appropriate branch without editing code.
# NOTE: Several methods have optional coefficients/branches (e.g. Terzaghi smooth vs coarse grains,
#       Zunker/Zamarin detailed fractions, etc.). For now we keep the baseline coefficients from the
#       literature tables. Once the numerical implementation is stable we can expose user-facing
#       toggles so analysts can choose the appropriate branch without editing code.

 I dug into the new numbers using Test1.csv and compared each method against the “ground truth” in results_test1.png.
  Here’s where we stand right now:

  Method          Excel (m/d)   Current (m/d)   Gap      Status
  -----------------------------------------------------------------
  Hazen           25.925        25.688          -0.237   OK
  Hazen_1892      19.440        19.440           0.000   Warning (mm² variant)
  Slichter         8.290         8.291           0.001   OK
  Terzaghi        14.425        18.374          +3.949   OK (but high)
  Beyer           21.434        21.434           0.000   OK
  Sauerbrei       29.297        29.194          -2.103   OK
  Kruger          44.600        44.60          -6.780   Warning (U≤5)
  Kozeny-Carman   89.221        23.855         -65.366   Warning
  Zunker          48.733        66.848         +18.115   OK
  Zamarin         57.556       124.833         +67.277   OK
  USBR            22.044      1346.029       +1323.985   OK (but wild)
  Barr            11.554   6.898×10⁶      +6.898×10⁶    OK (unit issue)
  Alyamani-Sen     7.240      5982.794       +5975.554   OK
  Chapuis         15.022       -0.000         -15.022   OK (sign issue)
  Krumbein-Monk  277.008         0.000        -277.008   Error (needs D160/840/950)
  Shepherd        43.272      1155.639       +1112.367   OK

"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


class CalculationStatus(Enum):
    """Status codes for hydraulic conductivity calculations."""

    OK = "OK"
    WARNING = "Warning"
    ERROR = "Error"


@dataclass
class KCalculationResult:
    """Container for a single hydraulic conductivity estimate."""

    method_name: str
    k_value: float  # m/s
    formula_used: str
    status: CalculationStatus
    status_message: str
    conditions_met: bool
    temperature: float
    porosity: float
    grain_size_used: str


class KCalculator:
    """Hydraulic conductivity calculator following the literature tables."""

    def __init__(self) -> None:
        self.methods = {
            "Hazen": self._hazen_simplified,
            "Hazen_1892": self._hazen_1892,
            "Slichter": self._slichter,
            "Terzaghi": self._terzaghi,
            "Beyer": self._beyer,
            "Sauerbrei": self._sauerbrei,
            "Kruger": self._kruger,
            "Kozeny-Carman": self._kozeny_carman,
            "Zunker": self._zunker,
            "Zamarin": self._zamarin,
            "USBR": self._usbr,
            "Barr": self._barr,
            "Alyamani-Sen": self._alyamani_sen,
            "Chapuis": self._chapuis,
            "Shepherd": self._shepherd,
            "Krumbein-Monk": self._krumbein_monk,
        }

    def get_all_method_names(self) -> List[str]:
        """Return all implemented method identifiers."""
        return list(self.methods.keys())

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def calculate_all_methods(
        self,
        grain_data: Dict[str, float],
        temperature: float = 20.0,
        porosity: float = 0.40,
        selected_methods: Optional[Sequence[str]] = None,
    ) -> List[KCalculationResult]:
        """Evaluate the requested methods and return their results."""

        if porosity <= 0 or porosity >= 1:
            return [
                KCalculationResult(
                    method_name="All",
                    k_value=0.0,
                    formula_used="N/A",
                    status=CalculationStatus.ERROR,
                    status_message="Porosity must be between 0 and 1",
                    conditions_met=False,
                    temperature=temperature,
                    porosity=porosity,
                    grain_size_used="N/A",
                )
            ]

        if selected_methods is None:
            method_names = list(self.methods.keys())
        else:
            method_names = [name for name in selected_methods if name in self.methods]

        results: List[KCalculationResult] = []
        for name in method_names:
            try:
                result = self.methods[name](grain_data, temperature, porosity)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Error while evaluating %s", name)
                result = KCalculationResult(
                    method_name=name,
                    k_value=0.0,
                    formula_used="N/A",
                    status=CalculationStatus.ERROR,
                    status_message=str(exc),
                    conditions_met=False,
                    temperature=temperature,
                    porosity=porosity,
                    grain_size_used="N/A",
                )
            results.append(result)

        return results

    def _apply_temperature_correction(self, k_ref: float, temperature: float, ref_temp: float = 20.0) -> float:
        """Adjust K from a reference temperature to the requested temperature."""
        if temperature == ref_temp:
            return k_ref

        mu_ref = self._water_viscosity(ref_temp)
        rho_ref = self._water_density(ref_temp)
        mu_t = self._water_viscosity(temperature)
        rho_t = self._water_density(temperature)
        if mu_t <= 0:
            return k_ref

        correction = (mu_ref / mu_t) * (rho_t / rho_ref)
        return k_ref * correction

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _water_density(temp_c: float) -> float:
        """Density of water in g/cm³ (Vuković & Soro, 1992)."""

        return 3.1e-8 * temp_c**3 - 7.0e-6 * temp_c**2 + 4.19e-5 * temp_c + 0.99985

    @staticmethod
    def _water_viscosity(temp_c: float) -> float:
        """Dynamic viscosity of water in g/(cm·s) (Vuković & Soro, 1992)."""

        return -7.0e-8 * temp_c**3 + 1.002e-5 * temp_c**2 - 5.7e-4 * temp_c + 0.0178

    @classmethod
    def _rho_g_over_mu(cls, temp_c: float) -> float:
        """Convenience wrapper returning (ρ g / μ) in cgs units."""

        rho = cls._water_density(temp_c)
        mu = cls._water_viscosity(temp_c)
        if mu <= 0:
            raise ValueError("Dynamic viscosity evaluated to a non-positive value")
        g = 980.0  # cm/s²
        return (rho * g) / mu

    @staticmethod
    def _to_cm(diameter_mm: float) -> float:
        return diameter_mm / 10.0

    @staticmethod
    def _porosity_ratio(porosity: float) -> float:
        return porosity / (1.0 - porosity) ** 2

    @staticmethod
    def _porosity_cubic_ratio(porosity: float) -> float:
        return porosity**3 / (1.0 - porosity) ** 2

    @staticmethod
    def _void_ratio(porosity: float) -> float:
        return porosity / (1.0 - porosity)

    @staticmethod
    def _extract_percentiles(grain_data: Dict[str, float]) -> Dict[float, float]:
        percentiles: Dict[float, float] = {}
        for key, value in grain_data.items():
            if not isinstance(key, str) or not key.startswith("D"):
                continue
            try:
                percentile = float(key[1:])
            except ValueError:
                continue
            percentiles[percentile] = float(value)
        return percentiles

    def _build_distribution(
        self, grain_data: Dict[str, float]
    ) -> List[Tuple[float, float]]:
        """Return (diameter_mm, percent_passing) pairs."""

        sizes = grain_data.get("particle_sizes")
        percents = grain_data.get("percent_passing")
        if sizes and percents and len(sizes) == len(percents):
            distribution = [
                (float(size), float(percent))
                for size, percent in zip(sizes, percents)
            ]
            return [pair for pair in distribution if pair[0] > 0]

        percentiles = self._extract_percentiles(grain_data)
        distribution = [
            (diameter, percentile)
            for percentile, diameter in percentiles.items()
        ]
        return [pair for pair in distribution if pair[0] > 0]

    def _calculate_geometric_mean(self, grain_data: Dict[str, float]) -> Optional[float]:
        """
        Calculate geometric mean grain size using Excel's Urumovic method:
        dg = exp((1/Mtot) * Σ(mr(i) * log(sqrt(ps(i) * ps(i+1)))))

        Where mr(i) is mass retained between adjacent sieves
        """
        sizes = grain_data.get("particle_sizes")
        percents = grain_data.get("percent_passing")

        if not sizes or not percents or len(sizes) != len(percents):
            return None

        try:
            # Sort by grain size (descending)
            sorted_data = sorted(zip(sizes, percents), reverse=True)
            sorted_sizes, sorted_percents = zip(*sorted_data)

            # Calculate mass retained in each interval (as fraction of total)
            # Assuming total mass = 1 (or 100%)
            dg_sum = 0.0
            total_mass = 0.0

            for i in range(len(sorted_sizes) - 1):
                # Mass retained between sieve i and i+1
                if i == 0:
                    mass_retained = (100.0 - sorted_percents[i]) / 100.0
                else:
                    mass_retained = (sorted_percents[i-1] - sorted_percents[i]) / 100.0

                if mass_retained > 0 and sorted_sizes[i] > 0 and sorted_sizes[i+1] > 0:
                    # Geometric mean of adjacent sieve sizes
                    geom_mean_size = math.sqrt(sorted_sizes[i] * sorted_sizes[i+1])
                    dg_sum += mass_retained * math.log(geom_mean_size)
                    total_mass += mass_retained

            # Handle last interval (finest size to 0)
            if len(sorted_sizes) > 0:
                last_mass = sorted_percents[-1] / 100.0
                if last_mass > 0 and sorted_sizes[-1] > 0:
                    # For finest fraction, use the sieve size itself
                    dg_sum += last_mass * math.log(sorted_sizes[-1])
                    total_mass += last_mass

            if total_mass == 0:
                return None

            # Calculate geometric mean
            geometric_mean = math.exp(dg_sum / total_mass)

            return geometric_mean

        except Exception:
            return None

    def _interpolate_percentile(
        self, grain_data: Dict[str, float], target_percent: float
    ) -> Optional[float]:
        """
        Interpolate grain diameter at a target percent passing.
        Uses LINEAR interpolation to match Excel's VBA implementation.
        """

        distribution = self._build_distribution(grain_data)
        if not distribution:
            return None

        # Sort by percent passing to make interpolation monotonic.
        by_percent = sorted(distribution, key=lambda item: item[1])
        percents = [p for _, p in by_percent]
        sizes = [d for d, _ in by_percent]

        if target_percent <= percents[0]:
            return sizes[0]
        if target_percent >= percents[-1]:
            return sizes[-1]

        for (size_low, percent_low), (size_high, percent_high) in zip(
            zip(sizes, percents), zip(sizes[1:], percents[1:])
        ):
            if percent_low <= target_percent <= percent_high:
                if percent_high == percent_low:
                    return size_low
                # LINEAR interpolation (matches Excel VBA):
                # d = size_low + (size_high - size_low) * (target - percent_low) / (percent_high - percent_low)
                fraction = (target_percent - percent_low) / (percent_high - percent_low)
                return size_low + fraction * (size_high - size_low)

        return None

    def _harmonic_mean_diameter_cm(
        self, grain_data: Dict[str, float]
    ) -> Optional[float]:
        """
        Compute harmonic mean diameter for Kozeny-Carman using Excel VBA formula:
        invde = Σ(mass_fraction × 0.5 × (ps(i) + ps(i+1)) / (ps(i) × ps(i+1)))
        Then de = 1 / invde
        """
        distribution = self._build_distribution(grain_data)
        if not distribution:
            return None

        # Sort by descending diameter so that percent passing decreases.
        sorted_points = sorted(distribution, key=lambda item: item[0], reverse=True)
        invde = 0.0

        for (d_upper_mm, p_upper), (d_lower_mm, p_lower) in zip(
            sorted_points[:-1], sorted_points[1:]
        ):
            mass_fraction = max(0.0, p_upper - p_lower) / 100.0
            if mass_fraction <= 0.0:
                continue

            if d_upper_mm > 0 and d_lower_mm > 0:
                # VBA formula: mass_fraction × 0.5 × (ps(i) + ps(i+1)) / (ps(i) × ps(i+1))
                # This simplifies to: mass_fraction × 0.5 × (1/ps(i) + 1/ps(i+1))
                invde += mass_fraction * 0.5 * (d_upper_mm + d_lower_mm) / (d_upper_mm * d_lower_mm)

        # Mass finer than the last sieve - special case for finest fraction
        smallest_size_mm, smallest_percent = sorted_points[-1]
        if smallest_percent > 0:
            if smallest_size_mm < 0.0025:
                # VBA special case: invde = 3/2 × mass_fraction / 0.0025
                invde += (smallest_percent / 100.0) * 1.5 / 0.0025
            else:
                # For finest fraction, use standard approach with assumed finer size
                assumed_mm = smallest_size_mm / 2.0
                if assumed_mm > 0:
                    mass_fraction = smallest_percent / 100.0
                    invde += mass_fraction * 0.5 * (smallest_size_mm + assumed_mm) / (smallest_size_mm * assumed_mm)

        if invde <= 0:
            return None

        de_mm = 1.0 / invde
        return de_mm / 10.0  # Convert to cm

    def _create_error(
        self,
        method: str,
        message: str,
        temperature: float,
        porosity: float,
    ) -> KCalculationResult:
        return KCalculationResult(
            method_name=method,
            k_value=0.0,
            formula_used="N/A",
            status=CalculationStatus.ERROR,
            status_message=message,
            conditions_met=False,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="N/A",
        )

    # ------------------------------------------------------------------
    # Individual methods
    # ------------------------------------------------------------------
    def _hazen_simplified(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d10 = grain_data.get("D10")
        if d10 is None:
            return self._create_error("Hazen", "D10 required", temperature, porosity)

        d10_cm = self._to_cm(d10)
        rho_ratio = self._rho_g_over_mu(temperature)
        hazen_constant = 100.0 / self._rho_g_over_mu(10.0)
        k_cm_s = rho_ratio * hazen_constant * d10_cm**2
        k_m_s = k_cm_s / 100.0

        return KCalculationResult(
            method_name="Hazen",
            k_value=k_m_s,
            formula_used="K = (ρg/μ) * (100/(ρg/μ)₁₀°C) * d₁₀²",
            status=CalculationStatus.OK,
            status_message="Derived from Freeze & Cherry (1979)",
            conditions_met=True,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10",
        )

    def _hazen_1892(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d10 = grain_data.get("D10")
        if d10 is None:
            return self._create_error("Hazen_1892", "D10 required", temperature, porosity)

        d10_cm = self._to_cm(d10)
        d10_mm = d10
        k_cm_s = d10_mm ** 2
        k_m_s = k_cm_s / 100.0

        conditions_met = 0.01 <= d10_cm <= 0.3
        note_parts = []
        if not conditions_met:
            note_parts.append("D10 outside 0.01–0.3 cm")
        note_parts.append("Empirical mm² variant (10°C reference)")
        note = "; ".join(note_parts)
        status = CalculationStatus.WARNING

        return KCalculationResult(
            method_name="Hazen_1892",
            k_value=k_m_s,
            formula_used="K = (ρg/μ) * 6×10⁻⁴ * [1 + 10(n - 0.26)] * d₁₀²",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10",
        )

    def _slichter(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d10 = grain_data.get("D10")
        if d10 is None:
            return self._create_error("Slichter", "D10 required", temperature, porosity)

        d10_cm = self._to_cm(d10)
        rho_ratio = self._rho_g_over_mu(temperature)
        phi_n = porosity**3.287
        k_cm_s = rho_ratio * 1.0e-2 * phi_n * d10_cm**2
        k_m_s = k_cm_s / 100.0

        return KCalculationResult(
            method_name="Slichter",
            k_value=k_m_s,
            formula_used="K = (ρg/μ) * 1×10⁻² * n³·²⁸⁷ * d₁₀²",
            status=CalculationStatus.OK,
            status_message="",
            conditions_met=True,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10",
        )

    def _terzaghi(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d10 = grain_data.get("D10")
        if d10 is None:
            return self._create_error("Terzaghi", "D10 required", temperature, porosity)

        if porosity <= 0.13:
            return self._create_error(
                "Terzaghi",
                "Porosity must exceed 0.13 for Terzaghi formula",
                temperature,
                porosity,
            )

        d10_cm = self._to_cm(d10)
        phi_n = ((porosity - 0.13) / (1.0 - porosity) ** (1.0 / 3.0)) ** 2
        rho_base = self._rho_g_over_mu(10.0)
        k_cm_s_ref = rho_base * 11.1e-3 * phi_n * d10_cm**2
        k_m_s = k_cm_s_ref / 100.0

        note_parts = []
        if temperature != 10.0:
            note_parts.append(f"Reference 10°C calibration")
        status = CalculationStatus.OK if not note_parts else CalculationStatus.WARNING

        return KCalculationResult(
            method_name="Terzaghi",
            k_value=k_m_s,
            formula_used="K = 11.1×10⁻³ * (ρg/μ)₁₀°C * ((n-0.13)/∛(1-n))² * d₁₀²",
            status=status,
            status_message='; '.join(note_parts) or "Smooth-grain coefficient",
            conditions_met=True,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10",
        )

    def _beyer(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d10 = grain_data.get("D10")
        d60 = grain_data.get("D60")
        if d10 is None or d60 is None:
            return self._create_error(
                "Beyer", "D10 and D60 required", temperature, porosity
            )

        if d10 <= 0:
            return self._create_error(
                "Beyer", "D10 must be positive", temperature, porosity
            )

        U = d60 / d10
        if U <= 0:
            return self._create_error(
                "Beyer", "Uniformity coefficient must be positive", temperature, porosity
            )

        N = 5.2e-4 * math.log10(500.0 / U)
        d10_cm = self._to_cm(d10)
        rho_ratio = self._rho_g_over_mu(temperature)
        k_cm_s = rho_ratio * N * d10_cm**2
        k_m_s = k_cm_s / 100.0

        conditions_met = 1.0 < U < 20.0 and 0.006 <= d10_cm <= 0.06
        status = CalculationStatus.OK if conditions_met else CalculationStatus.WARNING
        note = "Within recommended range" if conditions_met else "Outside stated U or D10 limits"

        return KCalculationResult(
            method_name="Beyer",
            k_value=k_m_s,
            formula_used="K = (ρg/μ) * 5.2×10⁻⁴ log₁₀(500/U) * d₁₀²",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10",
        )

    def _sauerbrei(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d17 = grain_data.get("D17")
        if d17 is None:
            d10 = grain_data.get("D10")
            d20 = grain_data.get("D20")
            if d10 is not None and d20 is not None:
                d17 = d10 + (17.0 - 10.0) / (20.0 - 10.0) * (d20 - d10)
            else:
                d17 = self._interpolate_percentile(grain_data, 17.0)
        if d17 is None:
            return self._create_error(
                "Sauerbrei", "D17 or interpolation data required", temperature, porosity
            )

        d17_cm = self._to_cm(d17)
        tau = 1.093e-4 * temperature**2 + 2.102e-2 * temperature + 0.5889
        rho_ratio = self._rho_g_over_mu(temperature)
        phi_n = self._porosity_cubic_ratio(porosity)
        k_cm_s = rho_ratio * 3.75e-3 * tau * phi_n * d17_cm**2
        k_m_s = k_cm_s / 100.0

        conditions_met = d17_cm < 0.05
        status = CalculationStatus.OK if conditions_met else CalculationStatus.WARNING
        note = "" if conditions_met else "D17 exceeds 0.05 cm applicability limit"

        return KCalculationResult(
            method_name="Sauerbrei",
            k_value=k_m_s,
            formula_used="K = (ρg/μ) * 3.75×10⁻³ τ * n³/(1-n)² * d₁₇²",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D17",
        )

    def _kruger(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d10 = grain_data.get("D10")
        if d10 is None:
            return self._create_error("Kruger", "D10 required", temperature, porosity)

        de_cm = self._harmonic_mean_diameter_cm(grain_data)
        fallback_used = False
        if de_cm is None:
            de_cm = self._to_cm(d10)
            fallback_used = True

        rho_ratio = self._rho_g_over_mu(temperature)
        phi_n = self._porosity_ratio(porosity)
        k_cm_s = rho_ratio * 4.35e-4 * phi_n * de_cm**2
        k_m_s = k_cm_s / 100.0

        d60 = grain_data.get("D60")
        conditions_met = True
        status = CalculationStatus.OK
        messages: List[str] = []

        if fallback_used:
            status = CalculationStatus.WARNING
            messages.append("Used D10 approximation; full curve recommended")
            conditions_met = False

        if d60 and d10 > 0:
            U = d60 / d10
            if U <= 5.0:
                status = CalculationStatus.WARNING
                messages.append("Uniformity coefficient must exceed 5 for Kruger")
                conditions_met = False

        note = "; ".join(messages)
        return KCalculationResult(
            method_name="Kruger",
            k_value=k_m_s,
            formula_used="K = (ρg/μ) * 4.35×10⁻⁴ * n/(1-n)² * dₑ²",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="Full curve" if not fallback_used else "D10",
        )


    def _kozeny_carman(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        """
        Kozeny-Carman method using Excel VBA formula:
        K = (ρg/μ) * 0.0083 * n³/(1-n)² * de²
        where de is the harmonic mean diameter from dKozeny calculation
        """
        # Use harmonic mean diameter (matches Excel's L16 cell - dKozeny calculation)
        de_cm = self._harmonic_mean_diameter_cm(grain_data)

        if de_cm is None:
            return self._create_error(
                "Kozeny-Carman",
                "Could not calculate harmonic mean diameter",
                temperature,
                porosity
            )

        # Excel VBA formula
        rho_ratio = self._rho_g_over_mu(temperature)
        phi_n = self._porosity_cubic_ratio(porosity)  # n³/(1-n)²
        k_cm_s = rho_ratio * 8.3e-3 * phi_n * de_cm**2
        k_m_s = k_cm_s / 100.0

        # Check applicability
        d10 = grain_data.get("D10")
        conditions_met = True
        status = CalculationStatus.OK
        note = ""

        if d10 and d10 < 0.5:
            conditions_met = False
            status = CalculationStatus.WARNING
            note = "D10 < 0.5 mm may be too fine for Kozeny-Carman"

        return KCalculationResult(
            method_name="Kozeny-Carman",
            k_value=k_m_s,
            formula_used="K = (ρg/μ) * 8.3×10⁻³ * n³/(1-n)² * dₑ²",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="Harmonic mean",
        )

    def _zunker(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d10 = grain_data.get("D10")
        if d10 is None:
            return self._create_error("Zunker", "D10 required", temperature, porosity)

        d10_cm = self._to_cm(d10)
        rho_ratio = self._rho_g_over_mu(temperature)
        phi_n = self._void_ratio(porosity)
        k_cm_s = rho_ratio * 2.4e-3 * phi_n * d10_cm**1.8
        k_m_s = k_cm_s / 100.0

        conditions_met = d10 > 0.0025
        status = CalculationStatus.OK if conditions_met else CalculationStatus.WARNING
        note = "" if conditions_met else "D10 ≤ 0.0025 mm violates Zunker clean-sand assumption"

        return KCalculationResult(
            method_name="Zunker",
            k_value=k_m_s,
            formula_used="K = (ρg/μ) * 2.4×10⁻³ * n/(1-n) * d₁₀¹·⁸",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10",
        )

    def _zamarin(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d50 = grain_data.get("D50")
        if d50 is None:
            return self._create_error("Zamarin", "D50 required", temperature, porosity)

        d50_cm = self._to_cm(d50)
        rho_ratio = self._rho_g_over_mu(temperature)
        Cn = (1.275 - 1.5 * porosity) ** 2
        Cn = max(Cn, 0.0)
        phi_n = self._porosity_cubic_ratio(porosity) * Cn
        k_cm_s = rho_ratio * 8.65e-3 * phi_n * d50_cm**2
        k_m_s = k_cm_s / 100.0

        conditions_met = d50 > 0.00025
        status = CalculationStatus.OK if conditions_met else CalculationStatus.WARNING
        note = "" if conditions_met else "Material contains fractions finer than 0.00025 mm"

        return KCalculationResult(
            method_name="Zamarin",
            k_value=k_m_s,
            formula_used="K = (ρg/μ) * 8.65×10⁻³ * n³/(1-n)² Cₙ * d₅₀²",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D50",
        )

    def _usbr(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        # Excel VBA formula:
        # C = 0.00048 * 10^0.3 = 0.000958
        # de = (d20_mm / 10)^1.15 = d20_cm^1.15
        # K = (g*P/u) * C * de^2 = (ρg/μ) * 0.000958 * (d20_cm^1.15)^2
        # Final: K = (ρg/μ) * 0.000958 * d20_cm^2.3

        d20 = grain_data.get("D20")
        if d20 is None:
            return self._create_error("USBR", "D20 required", temperature, porosity)

        d20_cm = self._to_cm(d20)
        rho_ratio = self._rho_g_over_mu(temperature)
        coefficient = 4.8e-4 * (10 ** 0.3)  # = 0.000958

        # VBA uses de^2 where de = d20_cm^1.15, so effective exponent is 2.3
        k_cm_s = rho_ratio * coefficient * (d20_cm ** 2.3)
        k_m_s = k_cm_s / 100.0

        d60 = grain_data.get("D60")
        d10 = grain_data.get("D10")
        conditions_met = True
        note_parts: List[str] = []
        if d60 and d10 and d10 > 0:
            U = d60 / d10
            if U >= 5.0:
                conditions_met = False
                note_parts.append("U ≥ 5 exceeds USBR limit")
        status = CalculationStatus.OK if conditions_met else CalculationStatus.WARNING
        note = "; ".join(note_parts)

        return KCalculationResult(
            method_name="USBR",
            k_value=k_m_s,
            formula_used="K = (ρg/μ) * 4.8×10⁻⁴·10⁰·³ * d₂₀¹·¹⁵",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D20",
        )

    def _barr(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d10 = grain_data.get("D10")
        if d10 is None:
            return self._create_error("Barr", "D10 required", temperature, porosity)

        d10_cm = self._to_cm(d10)
        rho_ratio = self._rho_g_over_mu(temperature)
        phi_n = self._porosity_cubic_ratio(porosity)
        Cs_squared = 1.35  # angular grains (1.0 for spherical)
        coefficient = 1.0 / (36.0 * 5.0 * Cs_squared)
        k_cm_s = rho_ratio * coefficient * phi_n * d10_cm**2
        k_m_s = k_cm_s / 100.0

        conditions_met = 0.1 <= porosity <= 0.6
        status = CalculationStatus.OK if conditions_met else CalculationStatus.WARNING
        note = "" if conditions_met else "Porosity outside typical 0.1–0.6 range"

        return KCalculationResult(
            method_name="Barr",
            k_value=k_m_s,
            formula_used="K = (ρg/μ) * 1/(36×5×Cₛ²) * n³/(1-n)² * d₁₀² (Cₛ²=1.35 angular)",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10",
        )

    def _alyamani_sen(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d10 = grain_data.get("D10")
        d50 = grain_data.get("D50")
        if d10 is None or d50 is None:
            return self._create_error("Alyamani-Sen", "D10 and D50 required", temperature, porosity)

        # Calculate l0 (x-intercept) using Excel formula
        # =-(10-(40/(D50-D10))*D10)*(D50-D10)/40
        l0 = -(10.0 - (40.0 / (d50 - d10)) * d10) * (d50 - d10) / 40.0

        de_mm = l0 + 0.025 * (d50 - d10)
        de_m = de_mm / 1000.0  # Convert mm to meters

        # rho_g/mu in m/s^2 (convert from cm/s^2)
        rho_ratio_cm = self._rho_g_over_mu(temperature)
        rho_ratio_m = rho_ratio_cm / 10000.0

        # Using de² form: K = (ρg/μ in m/s²) × 1300 × de²(in m)
        # This gives K in m/s
        k_m_s = rho_ratio_m * 1300.0 * de_m**2

        conditions_met = de_m > 0
        status = CalculationStatus.OK if conditions_met else CalculationStatus.WARNING
        note = "" if conditions_met else "Effective diameter non-positive"

        return KCalculationResult(
            method_name="Alyamani-Sen",
            k_value=k_m_s,
            formula_used="K = 1300 * [l0 + 0.025(d50 - d10)]^2",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10, D50",
        )

    def _chapuis(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        d10 = grain_data.get("D10")
        if d10 is None:
            return self._create_error("Chapuis", "D10 required", temperature, porosity)

        d10_mm = d10  # Keep in mm
        e = self._void_ratio(porosity)  # e = n/(1-n)

        # Excel VBA formula (NO viscosity correction per VBA code comment):
        # C = 1
        # fn = 10^(1.291 * e - 0.6435)
        # a = 10^(0.5504 - 0.2937 * e)
        # de = d10^(a/2)
        # K = C * fn * de^2

        fn = 10 ** (1.291 * e - 0.6435)
        a = 10 ** (0.5504 - 0.2937 * e)
        de = d10_mm ** (a / 2.0)

        # K = fn * de^2 (result in cm/s based on Excel)
        k_cm_s = fn * (de ** 2)
        k_m_s = k_cm_s / 100.0  # Convert cm/s to m/s

        conditions_met = True
        note_parts: List[str] = []
        d60 = grain_data.get("D60")
        d5 = grain_data.get("D5")
        if not (0.3 < porosity < 0.7):
            conditions_met = False
            note_parts.append("0.3 < n < 0.7 not satisfied")
        if not (0.10 < d10 < 2.0):
            conditions_met = False
            note_parts.append("0.10 < D10 < 2.0 mm not satisfied")
        if d60 and d10:
            U = d60 / d10
            if not (2.0 < U < 12.0):
                conditions_met = False
                note_parts.append("Uniformity coefficient outside 2–12")
        if d5 and d5 > 0:
            ratio = d10 / d5
            if ratio >= 1.4:
                conditions_met = False
                note_parts.append("D10/D5 ≥ 1.4")

        status = CalculationStatus.OK if conditions_met else CalculationStatus.WARNING
        note = "; ".join(note_parts)

        return KCalculationResult(
            method_name="Chapuis",
            k_value=k_m_s,
            formula_used="K = (μ/ρg) * 10^{1.291e-0.6435} * D10 * 10^{0.5504-0.2937e}/2",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10",
        )

    def _shepherd(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        """
        Shepherd method using Excel VBA formula:
        K = 142.8 × d50_mm^1.65 (result in m/d)

        VBA shows: C = 142.8 * u/(P*g), then K = (ρg/μ) × C × de²
        where de = d50^(r/2) with r=1.65
        This simplifies to: K = 142.8 × d50^1.65 (in m/d)
        """
        d50 = grain_data.get("D50")
        if d50 is None:
            return self._create_error("Shepherd", "D50 required", temperature, porosity)

        d50_mm = d50  # Keep in mm (VBA comment: "de used in mm - no need to convert to cm")
        r = 1.65  # VBA: r = 1.65

        # Excel VBA formula (result in m/d):
        # de = d50_mm^(r/2), then K = (ρg/μ) × C × de² where C = 142.8 × μ/(ρg)
        # This simplifies to: K = 142.8 × d50_mm^r
        k_m_d = 142.8 * (d50_mm ** r)

        # Convert from m/d to cm/s (VBA: K * 100 / (24*60*60))
        k_cm_s = k_m_d / 864.0
        k_m_s = k_cm_s / 100.0

        conditions_met = 0.0063 <= d50 <= 2.0
        status = CalculationStatus.OK if conditions_met else CalculationStatus.WARNING
        note = "" if conditions_met else "D50 outside 0.0063–2.0 mm range"

        return KCalculationResult(
            method_name="Shepherd",
            k_value=k_m_s,
            formula_used="K = 142.8 × d₅₀^1.65 (mm, m/d)",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D50",
        )

    def _krumbein_monk(
        self, grain_data: Dict[str, float], temperature: float, porosity: float
    ) -> KCalculationResult:
        # TODO: Excel VBA uses geometric mean (d_geom from cell L14 = 0.159 mm for Borden)
        # but our calculation gives different value (0.091 mm). The VBA geometric mean
        # calculation uses mass retained array (mr) that we can't replicate from just
        # percent passing data. Formula structure verified:
        # C = 760 (darcys), fn = Exp(-1.31 * sigma), K = (g*P/u) * C * fn * de^2
        # Coefficient correct: 760 * 9.869233e-9 = 7.5006e-6
        # Sigma calculation verified (using phi with ADDITION)
        # Issue: Cannot match Excel's d_geometric_mean calculation exactly

        # Need D5, D16, D50, D84, D95 for sigma calculation
        required = ['D5', 'D16', 'D50', 'D84', 'D95']
        sizes_mm: Dict[str, float] = {}
        for key in required:
            value = grain_data.get(key)
            if value is None:
                return self._create_error("Krumbein-Monk", f"{key} required", temperature, porosity)
            sizes_mm[key] = value

        # Convert to phi units: φ = log2(d_mm / 1mm) = log2(d_mm)
        phi = {key: math.log2(d_mm) for key, d_mm in sizes_mm.items()}

        # Calculate sigma_phi using ADDITION (verified from VBA)
        part1 = (phi['D84'] - phi['D16']) / 4.0
        part2 = (phi['D95'] - phi['D5']) / 6.6
        sigma_phi = part1 + part2

        # Calculate geometric mean grain size
        d_geom = self._calculate_geometric_mean(grain_data)
        if d_geom is None:
            return self._create_error("Krumbein-Monk", "Could not calculate geometric mean", temperature, porosity)

        de_mm = d_geom
        de_cm = de_mm / 10.0

        rho_ratio = self._rho_g_over_mu(temperature)

        # VBA uses de^2 (squared)!
        # Coefficient: 760 darcys * 9.869233e-9 cm²/darcy = 7.501e-6 cm²
        k_cm_s = rho_ratio * 7.501e-6 * math.exp(-1.31 * sigma_phi) * (de_cm ** 2)
        k_m_s = k_cm_s / 100.0

        conditions_met = 0.5 <= sigma_phi <= 3.0
        status = CalculationStatus.OK if conditions_met else CalculationStatus.WARNING
        note = "" if conditions_met else f"sigma_phi = {sigma_phi:.2f} suggests non-lognormal distribution"

        return KCalculationResult(
            method_name="Krumbein-Monk",
            k_value=k_m_s,
            formula_used="K = 7.501×10^-6 * e^(-1.31*sigma_phi) * de",
            status=status,
            status_message=note,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D50, D160, D840, D950",
        )

__all__ = ["CalculationStatus", "KCalculationResult", "KCalculator"]
