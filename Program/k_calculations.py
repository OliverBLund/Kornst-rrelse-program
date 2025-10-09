"""Compatibility wrapper re-exporting the rebuilt hydraulic conductivity calculator."""

from k_calculations_v2 import (
    CalculationStatus,
    KCalculationResult,
    KCalculator,
)

__all__ = ["CalculationStatus", "KCalculationResult", "KCalculator"]
