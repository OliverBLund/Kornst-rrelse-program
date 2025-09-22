"""
Unit conversion utilities for hydraulic conductivity values
Supports conversion between m/s, cm/s, m/d and other common units
"""

from typing import Dict, Tuple
from enum import Enum


class HydraulicConductivityUnit(Enum):
    """Enumeration of supported hydraulic conductivity units"""
    M_PER_S = "m/s"
    CM_PER_S = "cm/s"
    M_PER_DAY = "m/d"
    CM_PER_MIN = "cm/min"
    FT_PER_DAY = "ft/d"


class HydraulicConductivityConverter:
    """
    Converter for hydraulic conductivity units

    All conversions are relative to m/s as the base unit
    """

    # Conversion factors FROM base unit (m/s) TO target unit
    CONVERSION_FACTORS = {
        HydraulicConductivityUnit.M_PER_S: 1.0,
        HydraulicConductivityUnit.CM_PER_S: 100.0,  # 1 m/s = 100 cm/s
        HydraulicConductivityUnit.M_PER_DAY: 86400.0,  # 1 m/s = 86400 m/d (24*3600)
        HydraulicConductivityUnit.CM_PER_MIN: 6000.0,  # 1 m/s = 6000 cm/min (100*60)
        HydraulicConductivityUnit.FT_PER_DAY: 283464.567,  # 1 m/s = ~283464.567 ft/d
    }

    # Display formatting for each unit
    DISPLAY_FORMATS = {
        HydraulicConductivityUnit.M_PER_S: "{:.2e}",  # Scientific notation for small values
        HydraulicConductivityUnit.CM_PER_S: "{:.3f}",  # 3 decimal places
        HydraulicConductivityUnit.M_PER_DAY: "{:.2f}",  # 2 decimal places
        HydraulicConductivityUnit.CM_PER_MIN: "{:.2f}",  # 2 decimal places
        HydraulicConductivityUnit.FT_PER_DAY: "{:.1f}",  # 1 decimal place
    }

    # Unit symbols for display
    UNIT_SYMBOLS = {
        HydraulicConductivityUnit.M_PER_S: "m/s",
        HydraulicConductivityUnit.CM_PER_S: "cm/s",
        HydraulicConductivityUnit.M_PER_DAY: "m/d",
        HydraulicConductivityUnit.CM_PER_MIN: "cm/min",
        HydraulicConductivityUnit.FT_PER_DAY: "ft/d",
    }

    @classmethod
    def convert_from_m_per_s(cls, value_m_s: float, target_unit: HydraulicConductivityUnit) -> float:
        """
        Convert hydraulic conductivity from m/s to target unit

        Args:
            value_m_s: Value in m/s
            target_unit: Target unit to convert to

        Returns:
            Converted value in target unit
        """
        if target_unit not in cls.CONVERSION_FACTORS:
            raise ValueError(f"Unsupported unit: {target_unit}")

        return value_m_s * cls.CONVERSION_FACTORS[target_unit]

    @classmethod
    def convert_to_m_per_s(cls, value: float, source_unit: HydraulicConductivityUnit) -> float:
        """
        Convert hydraulic conductivity from source unit to m/s

        Args:
            value: Value in source unit
            source_unit: Source unit to convert from

        Returns:
            Value in m/s
        """
        if source_unit not in cls.CONVERSION_FACTORS:
            raise ValueError(f"Unsupported unit: {source_unit}")

        return value / cls.CONVERSION_FACTORS[source_unit]

    @classmethod
    def convert_between_units(cls, value: float,
                            source_unit: HydraulicConductivityUnit,
                            target_unit: HydraulicConductivityUnit) -> float:
        """
        Convert hydraulic conductivity between any two supported units

        Args:
            value: Value in source unit
            source_unit: Source unit
            target_unit: Target unit

        Returns:
            Value in target unit
        """
        # Convert to m/s first, then to target unit
        value_m_s = cls.convert_to_m_per_s(value, source_unit)
        return cls.convert_from_m_per_s(value_m_s, target_unit)

    @classmethod
    def format_value(cls, value: float, unit: HydraulicConductivityUnit) -> str:
        """
        Format hydraulic conductivity value for display

        Args:
            value: Value to format
            unit: Unit of the value

        Returns:
            Formatted string with value and unit
        """
        if unit not in cls.DISPLAY_FORMATS:
            raise ValueError(f"Unsupported unit: {unit}")

        format_str = cls.DISPLAY_FORMATS[unit]
        formatted_value = format_str.format(value)
        unit_symbol = cls.UNIT_SYMBOLS[unit]

        return f"{formatted_value} {unit_symbol}"

    @classmethod
    def get_all_units(cls) -> Dict[HydraulicConductivityUnit, str]:
        """Get all supported units with their symbols"""
        return cls.UNIT_SYMBOLS.copy()

    @classmethod
    def get_unit_from_string(cls, unit_str: str) -> HydraulicConductivityUnit:
        """
        Get unit enum from string representation

        Args:
            unit_str: String representation (e.g., "m/s", "cm/s", "m/d")

        Returns:
            Corresponding unit enum
        """
        for unit, symbol in cls.UNIT_SYMBOLS.items():
            if symbol.lower() == unit_str.lower():
                return unit

        raise ValueError(f"Unknown unit string: {unit_str}")


def get_default_plot_unit() -> HydraulicConductivityUnit:
    """
    Get the default unit for plotting (m/d as specified by user)
    """
    return HydraulicConductivityUnit.M_PER_DAY


def get_default_table_unit() -> HydraulicConductivityUnit:
    """
    Get the default unit for tables (m/s for compatibility)
    """
    return HydraulicConductivityUnit.M_PER_S


# Convenience functions for common conversions
def m_per_s_to_m_per_day(value_m_s: float) -> float:
    """Convert m/s to m/d"""
    return HydraulicConductivityConverter.convert_from_m_per_s(
        value_m_s, HydraulicConductivityUnit.M_PER_DAY
    )


def m_per_s_to_cm_per_s(value_m_s: float) -> float:
    """Convert m/s to cm/s"""
    return HydraulicConductivityConverter.convert_from_m_per_s(
        value_m_s, HydraulicConductivityUnit.CM_PER_S
    )


def cm_per_s_to_m_per_s(value_cm_s: float) -> float:
    """Convert cm/s to m/s"""
    return HydraulicConductivityConverter.convert_to_m_per_s(
        value_cm_s, HydraulicConductivityUnit.CM_PER_S
    )