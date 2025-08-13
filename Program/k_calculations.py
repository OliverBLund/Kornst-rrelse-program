"""
Hydraulic Conductivity Calculation Methods
Comprehensive implementation of empirical formulas for estimating hydraulic conductivity
from grain size distribution data.

References:
- Vukovic, M. and Soro, A. (1992) "Determination of hydraulic conductivity of porous media from grain-size composition"
- Freeze, R.A. and Cherry, J.A. (1979) "Groundwater"
- Various geotechnical and hydrogeological literature

All formulas calculate hydraulic conductivity K in m/s
Temperature corrections are applied where specified
Porosity effects are included where applicable
"""

import math
import logging
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum

# Set up logging
logger = logging.getLogger(__name__)

class CalculationStatus(Enum):
    """Status codes for calculation results"""
    OK = "OK"
    WARNING = "Warning"
    ERROR = "Error"
    OUT_OF_RANGE = "Out of Range"

@dataclass
class KCalculationResult:
    """Result from a hydraulic conductivity calculation"""
    method_name: str
    k_value: float  # m/s
    formula_used: str
    status: CalculationStatus
    status_message: str
    conditions_met: bool
    temperature: float
    porosity: float
    grain_size_used: str  # e.g., "D10", "D20"

class KCalculator:
    """
    Hydraulic conductivity calculator implementing multiple empirical methods.
    
    All methods are based on grain size distribution analysis and return
    hydraulic conductivity in m/s at the specified temperature.
    """
    
    def __init__(self):
        """Initialize the calculator with method definitions"""
        self.methods = {
            "Hazen": {
                "function": self._hazen_simplified,
                "description": "Hazen simplified formula (Freeze and Cherry, 1979)",
                "applicable_conditions": "Uniformly graded sand, n ≈ 0.375, T = 10°C",
                "grain_size": "D10",
                "valid_range": "0.1 < D10 < 3.0 mm",
                "reference": "Freeze and Cherry (1979)"
            },
            "Hazen_1892": {
                "function": self._hazen_1892,
                "description": "Original Hazen formula (1892)",
                "applicable_conditions": "0.01 cm < D10 < 0.3 cm, U < 5",
                "grain_size": "D10",
                "valid_range": "0.1 < D10 < 3.0 mm",
                "reference": "Hazen (1892)"
            },
            "Slichter": {
                "function": self._slichter,
                "description": "Slichter formula (1898)",
                "applicable_conditions": "0.01 cm < D10 < 0.5 cm, U < 5",
                "grain_size": "D10",
                "valid_range": "0.1 < D10 < 5.0 mm",
                "reference": "Slichter (1898)"
            },
            "Terzaghi": {
                "function": self._terzaghi,
                "description": "Terzaghi formula (1925)",
                "applicable_conditions": "Sandy soil, coarse sand",
                "grain_size": "D10",
                "valid_range": "0.1 < D10 < 2.0 mm",
                "reference": "Terzaghi (1925)"
            },
            "Beyer": {
                "function": self._beyer,
                "description": "Beyer formula (1964)",
                "applicable_conditions": "0.006 cm < D10 < 0.06 cm, 1 < U < 20",
                "grain_size": "D10",
                "valid_range": "0.06 < D10 < 0.6 mm",
                "reference": "Beyer (1964)"
            },
            "Sauerbrei": {
                "function": self._sauerbrei,
                "description": "Sauerbrei formula (Vukovic and Soro, 1992)",
                "applicable_conditions": "Sand and sandy clay, D17 < 0.05 cm",
                "grain_size": "D17",
                "valid_range": "D17 < 0.5 mm",
                "reference": "Sauerbrei (1932), Vukovic and Soro (1992)"
            },
            "Kruger": {
                "function": self._kruger,
                "description": "Kruger formula (1918)",
                "applicable_conditions": "Medium sand, U > 5, T = 0°C",
                "grain_size": "D10 or weighted average",
                "valid_range": "Medium sand gradations",
                "reference": "Kruger (1918)"
            },
            "Kozeny-Carman": {
                "function": self._kozeny_carman,
                "description": "Kozeny-Carman formula (1953)",
                "applicable_conditions": "Coarse sand",
                "grain_size": "Effective diameter",
                "valid_range": "Coarse sands and gravels",
                "reference": "Kozeny-Carman (1953)"
            },
            "Zunker": {
                "function": self._zunker,
                "description": "Zunker formula (1930)",
                "applicable_conditions": "No fractions finer than d = 0.0025 mm",
                "grain_size": "Weighted grain sizes",
                "valid_range": "Clean sands and gravels",
                "reference": "Zunker (1930)"
            },
            "Zamarin": {
                "function": self._zamarin,
                "description": "Zamarin formula (1928)",
                "applicable_conditions": "Large grained sands with no fractions having d < 0.00025 mm",
                "grain_size": "Effective diameter",
                "valid_range": "Clean, coarse sands",
                "reference": "Zamarin (1928)"
            },
            "USBR": {
                "function": self._usbr,
                "description": "United States Bureau of Reclamation (Bialas, 1966)",
                "applicable_conditions": "Medium grained sands with U < 5, derived for T = 15°C",
                "grain_size": "D20",
                "valid_range": "Medium sands",
                "reference": "Bialas (1966)"
            },
            "Shepherd": {
                "function": self._shepherd,
                "description": "Shepherd formula (1989)",
                "applicable_conditions": "0.0063 < d50 < 2",
                "grain_size": "D50 (r/2)",
                "valid_range": "0.0063 mm < D50 < 2 mm",
                "reference": "Shepherd (1989)"
            }
        }
    
    def calculate_all_methods(self, grain_data: Dict[str, float], 
                            temperature: float = 20.0, 
                            porosity: float = 0.40,
                            selected_methods: Optional[List[str]] = None) -> List[KCalculationResult]:
        """
        Calculate hydraulic conductivity using all applicable methods.
        
        Args:
            grain_data: Dictionary with keys like 'D10', 'D20', 'D50', etc. (in mm)
            temperature: Water temperature in °C
            porosity: Porosity as fraction (0-1)
            selected_methods: List of method names to use (None = all methods)
            
        Returns:
            List of KCalculationResult objects
        """
        results = []
        
        # Use all methods if none specified or if True is passed
        if selected_methods is None or selected_methods is True:
            selected_methods = list(self.methods.keys())
        elif selected_methods is False:
            selected_methods = []
        
        for method_name in selected_methods:
            if method_name not in self.methods:
                logger.warning(f"Unknown method: {method_name}")
                continue
                
            try:
                method_info = self.methods[method_name]
                result = method_info["function"](grain_data, temperature, porosity)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error calculating {method_name}: {e}")
                error_result = KCalculationResult(
                    method_name=method_name,
                    k_value=0.0,
                    formula_used="Error in calculation",
                    status=CalculationStatus.ERROR,
                    status_message=str(e),
                    conditions_met=False,
                    temperature=temperature,
                    porosity=porosity,
                    grain_size_used="Unknown"
                )
                results.append(error_result)
        
        return results
    
    def _apply_temperature_correction(self, k_20: float, temperature: float) -> float:
        """
        Apply temperature correction to hydraulic conductivity.
        
        Formula: K_T = K_20 * (μ_20/μ_T) * (ρ_T/ρ_20)
        Simplified: K_T = K_20 * viscosity_correction
        
        Args:
            k_20: Hydraulic conductivity at 20°C
            temperature: Target temperature in °C
            
        Returns:
            Temperature-corrected hydraulic conductivity
        """
        if temperature == 20.0:
            return k_20
            
        # Viscosity correction factor (approximate)
        # μ = 1.093 × 10^-6 * T² - 2.102 × 10^-4 * T + 0.5889 (dynamic viscosity ratio)
        t = temperature
        viscosity_ratio_20 = 1.002e-3  # Pa·s at 20°C
        viscosity_ratio_t = (1.093e-6 * t**2 - 2.102e-4 * t + 0.5889) * 1e-3
        
        correction_factor = viscosity_ratio_20 / viscosity_ratio_t
        return k_20 * correction_factor
    
    def _hazen_simplified(self, grain_data: Dict[str, float], 
                         temperature: float, porosity: float) -> KCalculationResult:
        """
        Hazen simplified formula (Freeze and Cherry, 1979)
        K = 100 * (μ/ρg) * d10²
        Where the constant ≈ 1 for d10 in mm and K in m/s
        
        Applicable: Uniformly graded sand, n ≈ 0.375, T = 10°C
        """
        d10 = grain_data.get('D10')
        if d10 is None:
            return self._create_error_result("Hazen", "D10 required", temperature, porosity)
        
        # Convert mm to m
        d10_m = d10 / 1000.0
        
        # Hazen coefficient (approximately 1.0 for standard conditions)
        C = 1.0
        
        # Calculate K at reference temperature
        k_ref = C * d10_m**2
        
        # Apply temperature correction
        k_corrected = self._apply_temperature_correction(k_ref, temperature)
        
        # Check applicable conditions
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = "Calculation successful"
        
        if d10 < 0.1 or d10 > 3.0:
            status = CalculationStatus.WARNING
            status_msg = f"D10 = {d10:.3f} mm outside recommended range (0.1-3.0 mm)"
            conditions_met = False
        
        return KCalculationResult(
            method_name="Hazen",
            k_value=k_corrected,
            formula_used="K = C * D10² (C = 1.0)",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10"
        )
    
    def _hazen_1892(self, grain_data: Dict[str, float], 
                   temperature: float, porosity: float) -> KCalculationResult:
        """
        Original Hazen formula (1892)
        K = 6 × 10^-4 * [1 + 10(n - 0.26)] * d10²
        
        Applicable: 0.01 cm < d10 < 0.3 cm, U < 5
        """
        d10 = grain_data.get('D10')
        if d10 is None:
            return self._create_error_result("Hazen_1892", "D10 required", temperature, porosity)
        
        # Convert mm to cm for formula
        d10_cm = d10 / 10.0
        
        # Hazen 1892 formula
        k_ref = 6e-4 * (1 + 10 * (porosity - 0.26)) * d10_cm**2
        
        # Convert from cm/s to m/s
        k_ref = k_ref / 100.0
        
        # Apply temperature correction
        k_corrected = self._apply_temperature_correction(k_ref, temperature)
        
        # Check conditions
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = "Calculation successful"
        
        if d10_cm < 0.01 or d10_cm > 0.3:
            status = CalculationStatus.WARNING
            status_msg = f"D10 = {d10_cm:.3f} cm outside valid range (0.01-0.3 cm)"
            conditions_met = False
        
        return KCalculationResult(
            method_name="Hazen_1892",
            k_value=k_corrected,
            formula_used="K = 6×10⁻⁴ * [1 + 10(n - 0.26)] * D10²",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10"
        )
    
    def _slichter(self, grain_data: Dict[str, float], 
                 temperature: float, porosity: float) -> KCalculationResult:
        """
        Slichter formula (1898)
        K = 1 × 10^-2 * n^2.287 * d10²
        
        Applicable: 0.01 cm < d10 < 0.5 cm, U < 5
        """
        d10 = grain_data.get('D10')
        if d10 is None:
            return self._create_error_result("Slichter", "D10 required", temperature, porosity)
        
        # Convert mm to cm
        d10_cm = d10 / 10.0
        
        # Slichter formula
        k_ref = 1e-2 * (porosity**2.287) * d10_cm**2
        
        # Convert from cm/s to m/s
        k_ref = k_ref / 100.0
        
        # Apply temperature correction
        k_corrected = self._apply_temperature_correction(k_ref, temperature)
        
        # Check conditions
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = "Calculation successful"
        
        if d10_cm < 0.01 or d10_cm > 0.5:
            status = CalculationStatus.WARNING
            status_msg = f"D10 = {d10_cm:.3f} cm outside valid range (0.01-0.5 cm)"
            conditions_met = False
        
        return KCalculationResult(
            method_name="Slichter",
            k_value=k_corrected,
            formula_used="K = 1×10⁻² * n^2.287 * D10²",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10"
        )
    
    def _terzaghi(self, grain_data: Dict[str, float], 
                 temperature: float, porosity: float) -> KCalculationResult:
        """
        Terzaghi formula (1925)
        K = (10.7 × 10^-3 for smooth grains, 6.1 × 10^-3 for coarse grains) * ((n - 0.13)/(√(1-n)))² * d10²
        
        Applicable: Sandy soil, coarse sand
        """
        d10 = grain_data.get('D10')
        if d10 is None:
            return self._create_error_result("Terzaghi", "D10 required", temperature, porosity)
        
        # Convert mm to cm
        d10_cm = d10 / 10.0
        
        # Use average coefficient (smooth grains coefficient)
        C = 10.7e-3
        
        # Terzaghi formula
        porosity_term = ((porosity - 0.13) / math.sqrt(1 - porosity))**2
        k_ref = C * porosity_term * d10_cm**2
        
        # Convert from cm/s to m/s
        k_ref = k_ref / 100.0
        
        # Apply temperature correction
        k_corrected = self._apply_temperature_correction(k_ref, temperature)
        
        # Check conditions
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = "Calculation successful (smooth grains coefficient used)"
        
        if porosity < 0.13:
            status = CalculationStatus.WARNING
            status_msg = f"Porosity = {porosity:.3f} below formula minimum (0.13)"
            conditions_met = False
        
        return KCalculationResult(
            method_name="Terzaghi",
            k_value=k_corrected,
            formula_used="K = C * ((n-0.13)/√(1-n))² * D10²",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10"
        )
    
    def _beyer(self, grain_data: Dict[str, float], 
              temperature: float, porosity: float) -> KCalculationResult:
        """
        Beyer formula (1964)
        K = 5.2 × 10^-4 * log(500/U) * d10^1.5
        
        Applicable: 0.006 cm < d10 < 0.06 cm, 1 < U < 20
        """
        d10 = grain_data.get('D10')
        d60 = grain_data.get('D60')
        
        if d10 is None:
            return self._create_error_result("Beyer", "D10 required", temperature, porosity)
        
        # Calculate uniformity coefficient
        if d60 is not None and d10 > 0:
            U = d60 / d10
        else:
            U = 5.0  # Assume moderate uniformity if D60 not available
            
        # Convert mm to cm
        d10_cm = d10 / 10.0
        
        # Beyer formula
        if U > 0:
            k_ref = 5.2e-4 * math.log10(500/U) * (d10_cm**1.5)
        else:
            return self._create_error_result("Beyer", "Invalid uniformity coefficient", temperature, porosity)
        
        # Convert from cm/s to m/s
        k_ref = k_ref / 100.0
        
        # Apply temperature correction
        k_corrected = self._apply_temperature_correction(k_ref, temperature)
        
        # Check conditions
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = f"Calculation successful (U = {U:.2f})"
        
        if d10_cm < 0.006 or d10_cm > 0.06:
            status = CalculationStatus.WARNING
            status_msg += f", D10 = {d10_cm:.4f} cm outside valid range (0.006-0.06 cm)"
            conditions_met = False
            
        if U < 1 or U > 20:
            status = CalculationStatus.WARNING
            status_msg += f", U = {U:.2f} outside valid range (1-20)"
            conditions_met = False
        
        return KCalculationResult(
            method_name="Beyer",
            k_value=k_corrected,
            formula_used="K = 5.2×10⁻⁴ * log(500/U) * D10^1.5",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10"
        )
    
    def _sauerbrei(self, grain_data: Dict[str, float], 
                  temperature: float, porosity: float) -> KCalculationResult:
        """
        Sauerbrei formula (Vukovic and Soro, 1992)
        K = (3.75 × 10^-5) × τ * (n³/(1-n)²) * d17²
        Where τ = temperature correction factor
        
        Applicable: Sand and sandy clay, d17 < 0.05 cm
        """
        # Try to get D17, or estimate from available data
        d17 = grain_data.get('D17')
        if d17 is None:
            # Estimate D17 from other percentiles if available
            d10 = grain_data.get('D10')
            d20 = grain_data.get('D20')
            if d10 and d20:
                # Linear interpolation in log space
                log_d10 = math.log(d10)
                log_d20 = math.log(d20)
                log_d17 = log_d10 + (17-10)/(20-10) * (log_d20 - log_d10)
                d17 = math.exp(log_d17)
            elif d10:
                # Rough estimate: D17 ≈ 1.2 * D10 for typical distributions
                d17 = 1.2 * d10
            else:
                return self._create_error_result("Sauerbrei", "D17 or D10 required", temperature, porosity)
        
        # Convert mm to cm
        d17_cm = d17 / 10.0
        
        # Temperature correction factor (from Vukovic and Soro)
        tau = 1.093e-6 * temperature**2 + 2.102e-4 * temperature + 0.5889
        
        # Sauerbrei formula
        porosity_term = porosity**3 / (1 - porosity)**2
        k_ref = 3.75e-5 * tau * porosity_term * d17_cm**2
        
        # Convert from cm/s to m/s
        k_ref = k_ref / 100.0
        
        # Apply temperature correction (already included in tau)
        k_corrected = k_ref
        
        # Check conditions
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = "Calculation successful"
        
        if d17_cm > 0.05:
            status = CalculationStatus.WARNING
            status_msg = f"D17 = {d17_cm:.4f} cm exceeds recommended limit (0.05 cm)"
            conditions_met = False
        
        if 'D17' not in grain_data:
            status_msg += " (D17 estimated from other percentiles)"
        
        return KCalculationResult(
            method_name="Sauerbrei",
            k_value=k_corrected,
            formula_used="K = 3.75×10⁻⁵ * τ * n³/(1-n)² * D17²",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D17"
        )
    
    def _kruger(self, grain_data: Dict[str, float], 
               temperature: float, porosity: float) -> KCalculationResult:
        """
        Kruger formula (1918)
        K = 4.35 × 10^-4 * (n/(1-n)²) * Σ(Δwi/di) or d10
        
        Applicable: Medium sand, U > 5, T = 0°C
        """
        d10 = grain_data.get('D10')
        if d10 is None:
            return self._create_error_result("Kruger", "D10 required", temperature, porosity)
        
        # Convert mm to cm
        d10_cm = d10 / 10.0
        
        # Kruger formula (simplified version using D10)
        porosity_term = porosity / (1 - porosity)**2
        k_ref = 4.35e-4 * porosity_term * d10_cm
        
        # Convert from cm/s to m/s
        k_ref = k_ref / 100.0
        
        # Apply temperature correction from 0°C to target temperature
        k_corrected = self._apply_temperature_correction(k_ref, temperature)
        
        # Check conditions
        d60 = grain_data.get('D60')
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = "Calculation successful (simplified version)"
        
        if d60 and d10 > 0:
            U = d60 / d10
            if U <= 5:
                status = CalculationStatus.WARNING
                status_msg = f"U = {U:.2f} ≤ 5, outside recommended range (U > 5)"
                conditions_met = False
        
        return KCalculationResult(
            method_name="Kruger",
            k_value=k_corrected,
            formula_used="K = 4.35×10⁻⁴ * n/(1-n)² * D10",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10"
        )
    
    def _kozeny_carman(self, grain_data: Dict[str, float], 
                      temperature: float, porosity: float) -> KCalculationResult:
        """
        Kozeny-Carman formula (1953)
        K = 8.3 × 10^-3 * (n³/(1-n)²) * de²
        Where de is effective diameter
        
        Applicable: Coarse sand
        """
        # Use D10 as effective diameter approximation
        d10 = grain_data.get('D10')
        if d10 is None:
            return self._create_error_result("Kozeny-Carman", "D10 required", temperature, porosity)
        
        # Convert mm to cm
        d10_cm = d10 / 10.0
        
        # Kozeny-Carman formula
        porosity_term = porosity**3 / (1 - porosity)**2
        k_ref = 8.3e-3 * porosity_term * d10_cm**2
        
        # Convert from cm/s to m/s
        k_ref = k_ref / 100.0
        
        # Apply temperature correction
        k_corrected = self._apply_temperature_correction(k_ref, temperature)
        
        # Check conditions
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = "Calculation successful"
        
        if d10 < 0.5:  # Coarse sand typically > 0.5 mm
            status = CalculationStatus.WARNING
            status_msg = f"D10 = {d10:.3f} mm may be too fine for coarse sand assumption"
            conditions_met = False
        
        return KCalculationResult(
            method_name="Kozeny-Carman",
            k_value=k_corrected,
            formula_used="K = 8.3×10⁻³ * n³/(1-n)² * D10²",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10"
        )
    
    def _zunker(self, grain_data: Dict[str, float], 
               temperature: float, porosity: float) -> KCalculationResult:
        """
        Zunker formula (1930)
        K = Various constants * (n/(1-n)) * Σ(Δgi * (di^n - di^l)/(di^n * di^l * ln(di^n/di^l)))
        Simplified: K ≈ 2.4×10^-3 * (n/(1-n)) * d10^1.8
        
        Applicable: No fractions finer than d = 0.0025 mm
        """
        d10 = grain_data.get('D10')
        if d10 is None:
            return self._create_error_result("Zunker", "D10 required", temperature, porosity)
        
        # Convert mm to cm
        d10_cm = d10 / 10.0
        
        # Zunker formula (simplified approximation)
        porosity_term = porosity / (1 - porosity)
        k_ref = 2.4e-3 * porosity_term * (d10_cm**1.8)
        
        # Convert from cm/s to m/s
        k_ref = k_ref / 100.0
        
        # Apply temperature correction
        k_corrected = self._apply_temperature_correction(k_ref, temperature)
        
        # Check conditions
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = "Calculation successful (simplified version)"
        
        if d10 < 0.0025:  # Check for fine fractions
            status = CalculationStatus.WARNING
            status_msg = f"D10 = {d10:.4f} mm includes fractions < 0.0025 mm limit"
            conditions_met = False
        
        return KCalculationResult(
            method_name="Zunker",
            k_value=k_corrected,
            formula_used="K = 2.4×10⁻³ * n/(1-n) * D10^1.8",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D10"
        )
    
    def _zamarin(self, grain_data: Dict[str, float], 
                temperature: float, porosity: float) -> KCalculationResult:
        """
        Zamarin formula (1928)
        K = 8.65 × 10^-3 * (n³/(1-n)²) * Cn * (1/ln(di^n/di^l)) * Σ(Δgi * (di^n - di^l)/(di^n * di^l))
        Simplified: K ≈ 8.65×10^-3 * (n³/(1-n)²) * d50²
        
        Applicable: Large grained sands with no fractions having d < 0.00025 mm
        """
        d50 = grain_data.get('D50')
        if d50 is None:
            return self._create_error_result("Zamarin", "D50 required", temperature, porosity)
        
        # Convert mm to cm
        d50_cm = d50 / 10.0
        
        # Zamarin formula (simplified approximation)
        porosity_term = porosity**3 / (1 - porosity)**2
        Cn = (1.275 - 1.5 * porosity)**2  # Correction factor
        k_ref = 8.65e-3 * porosity_term * Cn * d50_cm**2
        
        # Convert from cm/s to m/s
        k_ref = k_ref / 100.0
        
        # Apply temperature correction
        k_corrected = self._apply_temperature_correction(k_ref, temperature)
        
        # Check conditions
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = "Calculation successful (simplified version)"
        
        d10 = grain_data.get('D10')
        if d10 and d10 < 0.00025:  # Check for very fine fractions
            status = CalculationStatus.WARNING
            status_msg = f"Sample contains fractions < 0.00025 mm limit"
            conditions_met = False
        
        return KCalculationResult(
            method_name="Zamarin",
            k_value=k_corrected,
            formula_used="K = 8.65×10⁻³ * n³/(1-n)² * Cn * D50²",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D50"
        )
    
    def _usbr(self, grain_data: Dict[str, float], 
             temperature: float, porosity: float) -> KCalculationResult:
        """
        United States Bureau of Reclamation formula (Bialas, 1966)
        K = (4.8 × 10^-4)(10^0.3) * d20^1.15
        
        Applicable: Medium grained sands with U < 5, derived for T = 15°C
        """
        d20 = grain_data.get('D20')
        if d20 is None:
            return self._create_error_result("USBR", "D20 required", temperature, porosity)
        
        # Convert mm to cm
        d20_cm = d20 / 10.0
        
        # USBR formula
        k_ref = 4.8e-4 * (10**0.3) * (d20_cm**1.15)
        
        # Convert from cm/s to m/s
        k_ref = k_ref / 100.0
        
        # Apply temperature correction from 15°C
        k_15 = k_ref
        k_corrected = self._apply_temperature_correction(k_15 * self._apply_temperature_correction(1.0, 15.0), temperature)
        
        # Check conditions
        d60 = grain_data.get('D60')
        d10 = grain_data.get('D10')
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = "Calculation successful"
        
        if d60 and d10 and d10 > 0:
            U = d60 / d10
            if U >= 5:
                status = CalculationStatus.WARNING
                status_msg = f"U = {U:.2f} ≥ 5, outside recommended range (U < 5)"
                conditions_met = False
        
        return KCalculationResult(
            method_name="USBR",
            k_value=k_corrected,
            formula_used="K = 4.8×10⁻⁴ * 10^0.3 * D20^1.15",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D20"
        )
    
    def _shepherd(self, grain_data: Dict[str, float], 
                 temperature: float, porosity: float) -> KCalculationResult:
        """
        Shepherd formula (1989)
        K = Various constants * d50^(r/2)
        Where r depends on deposit type (1.65 for channel deposits, 1.75 for beach sand, 1.85 for dune sand)
        
        Applicable: 0.0063 < d50 < 2
        """
        d50 = grain_data.get('D50')
        if d50 is None:
            return self._create_error_result("Shepherd", "D50 required", temperature, porosity)
        
        # Convert mm to units used in formula (assume mm)
        d50_mm = d50
        
        # Use average exponent for mixed deposits
        r = 1.75  # Beach sand value as default
        
        # Shepherd formula (simplified - constants vary by deposit type)
        # Using average constant for demonstration
        C = 142.8  # Channel deposits constant
        k_ref = C * (d50_mm**(r/2))
        
        # Convert to m/s (assuming formula gives mm/s)
        k_ref = k_ref / 1000.0
        
        # Apply temperature correction
        k_corrected = self._apply_temperature_correction(k_ref, temperature)
        
        # Check conditions
        conditions_met = True
        status = CalculationStatus.OK
        status_msg = "Calculation successful (using beach sand exponent r=1.75)"
        
        if d50_mm < 0.0063 or d50_mm > 2.0:
            status = CalculationStatus.WARNING
            status_msg = f"D50 = {d50_mm:.4f} mm outside valid range (0.0063-2.0 mm)"
            conditions_met = False
        
        return KCalculationResult(
            method_name="Shepherd",
            k_value=k_corrected,
            formula_used="K = C * D50^(r/2), r=1.75",
            status=status,
            status_message=status_msg,
            conditions_met=conditions_met,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="D50"
        )
    
    def _create_error_result(self, method_name: str, error_msg: str, 
                           temperature: float, porosity: float) -> KCalculationResult:
        """Create an error result for failed calculations"""
        return KCalculationResult(
            method_name=method_name,
            k_value=0.0,
            formula_used="N/A",
            status=CalculationStatus.ERROR,
            status_message=error_msg,
            conditions_met=False,
            temperature=temperature,
            porosity=porosity,
            grain_size_used="N/A"
        )
    
    def get_method_info(self, method_name: str) -> Optional[Dict[str, str]]:
        """Get information about a specific calculation method"""
        return self.methods.get(method_name)
    
    def get_all_method_names(self) -> List[str]:
        """Get list of all available method names"""
        return list(self.methods.keys())
    
    def get_required_grain_sizes(self, method_names: List[str]) -> List[str]:
        """Get list of required grain size percentiles for given methods"""
        required = set()
        for method_name in method_names:
            if method_name in self.methods:
                grain_size = self.methods[method_name]["grain_size"]
                if "D" in grain_size:
                    required.add(grain_size.split()[0])  # Extract D10, D20, etc.
        return sorted(list(required))
