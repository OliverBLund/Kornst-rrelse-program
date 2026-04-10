"""
Data loader module for grain size analysis
Handles CSV file loading and data validation
"""

import csv
import os
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from grain_classification import (
    ClassificationResult, GrainClassificationScheme,
    ISO14688, classify as _gc_classify,
)
import logging
import pandas as pd
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationSeverity(Enum):
    """Severity levels for validation messages"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class ValidationMessage:
    """A user-friendly validation message"""
    severity: ValidationSeverity
    title: str
    message: str
    suggestion: str = ""
    impact: str = ""

    def get_icon(self) -> str:
        icons = {
            ValidationSeverity.INFO: "INFO",
            ValidationSeverity.WARNING: "WARN",
            ValidationSeverity.ERROR: "ERROR"
        }
        return icons.get(self.severity, "UNKNOWN")

@dataclass
class GrainSizeData:
    """Data class for grain size distribution data"""
    sample_name: str
    temperature: float
    porosity: float  # Will be replaced by calculated_porosity
    particle_sizes: List[float]  # mm
    percent_passing: List[float]  # %
    comments: Optional[str] = None
    file_path: Optional[str] = None
    validation_messages: List[ValidationMessage] = field(default_factory=list)
    calculated_porosity: Optional[float] = field(default=None)  # Urumovic calculation
    current_porosity: Optional[float] = field(default=None)  # User can override this

    def __post_init__(self):
        """Validate data after initialization"""
        if len(self.particle_sizes) != len(self.percent_passing):
            raise ValueError("Particle sizes and percent passing must have same length")

        # Clean and validate percent passing values with smart tolerance
        self.percent_passing = self._clean_percent_passing_values(self.percent_passing)

        # Validate particle sizes are positive and in reasonable range
        if not all(ps > 0 for ps in self.particle_sizes):
            raise ValueError("Particle sizes must be positive")

        # Check for reasonable grain size range (0.001 mm to 1000 mm)
        if any(ps < 0.001 or ps > 1000 for ps in self.particle_sizes):
            min_size, max_size = min(self.particle_sizes), max(self.particle_sizes)
            self.validation_messages.append(ValidationMessage(
                severity=ValidationSeverity.WARNING,
                title="Unusual grain sizes detected",
                message=f"Grain sizes range from {min_size:.4f} to {max_size:.1f} mm",
                suggestion="Typical range is 0.001-1000 mm. Check if units are correct.",
                impact="May affect method applicability"
            ))

        # Check if percent passing is monotonic (should generally decrease with decreasing grain size)
        # Sort by particle size (largest to smallest) and check if percent passing decreases
        sorted_data = sorted(zip(self.particle_sizes, self.percent_passing), reverse=True)
        non_monotonic_count = 0
        problem_sizes = []

        for i in range(1, len(sorted_data)):
            # Percent passing should decrease (or stay same) as grain size decreases
            if sorted_data[i][1] > sorted_data[i-1][1]:
                non_monotonic_count += 1
                if len(problem_sizes) < 3:  # Collect first few examples
                    problem_sizes.append(f"{sorted_data[i][0]:.3f}mm")

        # Only flag as error if there are many violations (> 30% of data points)
        # Some variation is normal in real-world data
        if non_monotonic_count > 0:
            violation_ratio = non_monotonic_count / len(sorted_data)

            if violation_ratio > 0.5:
                # Majority of data is non-monotonic - might be "retained" instead of "passing"
                self.validation_messages.append(ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    title="Data may be 'percent retained' instead of 'percent passing'",
                    message=f"Found {non_monotonic_count} data points where values increase with smaller grain sizes",
                    suggestion="Check if your data represents 'percent retained' rather than 'percent passing'. If so, convert using: % passing = 100 - % retained",
                    impact="Analysis assumes percent passing values; retained values will produce incorrect results"
                ))
            elif violation_ratio > 0.3:
                # Significant violations - quality warning
                self.validation_messages.append(ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    title="Non-monotonic grain size data detected",
                    message=f"Found {non_monotonic_count} data points with unexpected trends",
                    suggestion="Review data for entry errors or confirm this represents the actual grain size distribution",
                    impact="Minor irregularities may affect characteristic grain size calculations"
                ))
            elif non_monotonic_count <= 2:
                # Minor violations - informational only
                self.validation_messages.append(ValidationMessage(
                    severity=ValidationSeverity.INFO,
                    title="Minor data irregularities detected",
                    message=f"Found {non_monotonic_count} data points with small deviations from expected trend",
                    suggestion="Small irregularities are normal in laboratory data",
                    impact="Minimal impact on analysis results"
                ))

        # Validate temperature and porosity
        if self.temperature < 0 or self.temperature > 50:
            self.validation_messages.append(ValidationMessage(
                severity=ValidationSeverity.WARNING,
                title="Unusual temperature",
                message=f"Temperature is {self.temperature}°C",
                suggestion="Typical range is 0-50°C for soil testing",
                impact="Used for viscosity corrections in hydraulic conductivity calculations"
            ))

        if self.porosity < 0.1 or self.porosity > 0.8:
            self.validation_messages.append(ValidationMessage(
                severity=ValidationSeverity.WARNING,
                title="Unusual porosity",
                message=f"Porosity is {self.porosity}",
                suggestion="Typical range is 0.1-0.8 for natural soils",
                impact="Used directly in some hydraulic conductivity formulas"
            ))

        # Calculate porosity using simple Excel formula by default
        self.calculated_porosity = self._calculate_simple_porosity()

        # Set current porosity to calculated value (can be overridden by user)
        if self.current_porosity is None:
            self.current_porosity = self.calculated_porosity or self.porosity

    def _clean_percent_passing_values(self, percent_values: List[float]) -> List[float]:
        """Clean percent passing values with smart tolerance for floating-point precision issues"""
        cleaned_values = []
        values_rounded = 0
        values_significantly_rounded = 0
        invalid_values = []

        for i, value in enumerate(percent_values):
            if value < 0:
                # Negative values are always invalid
                invalid_values.append(f"{value:.6f} (position {i+1})")
                continue
            elif 0 <= value <= 100:
                # Valid range - keep as is
                cleaned_values.append(value)
            elif 100 < value <= 100.001:
                # Minor floating-point precision issue - round to 100
                cleaned_values.append(100.0)
                values_rounded += 1
            elif 100.001 < value <= 105:
                # Significant but potentially recoverable error - round to 100 with warning
                cleaned_values.append(100.0)
                values_significantly_rounded += 1
            else:
                # Major error - likely data entry mistake
                invalid_values.append(f"{value:.6f} (position {i+1})")

        # Report any invalid values that couldn't be cleaned
        if invalid_values:
            invalid_str = ", ".join(invalid_values[:5])  # Show first 5
            if len(invalid_values) > 5:
                invalid_str += f" and {len(invalid_values) - 5} more"
            raise ValueError(f"Invalid percent passing values found: {invalid_str}. Values must be between 0 and 100.")

        # Add informative messages about data cleaning
        if values_rounded > 0:
            self.validation_messages.append(ValidationMessage(
                severity=ValidationSeverity.INFO,
                title="Minor data precision adjustments made",
                message=f"Rounded {values_rounded} value(s) slightly above 100% to exactly 100%",
                suggestion="This is normal for Excel data and indicates minor floating-point precision differences",
                impact="No impact on analysis accuracy"
            ))

        if values_significantly_rounded > 0:
            self.validation_messages.append(ValidationMessage(
                severity=ValidationSeverity.WARNING,
                title="Significant data adjustments made",
                message=f"Rounded {values_significantly_rounded} value(s) significantly above 100% to exactly 100%",
                suggestion="Check original data for potential entry errors - values should not exceed 100%",
                impact="Minor impact: clamped values may slightly affect curve interpolation"
            ))

        return cleaned_values

    def get_percentile_size(self, percentile: float) -> Optional[float]:
        """Calculate grain size at an arbitrary percent passing."""
        return self._interpolate_grain_size(float(percentile))

    def get_d10(self) -> Optional[float]:
        """Calculate D10 (grain size at 10% passing)"""
        return self.get_percentile_size(10.0)

    def get_d20(self) -> Optional[float]:
        """Calculate D20 (grain size at 20% passing)"""
        return self.get_percentile_size(20.0)

    def get_d30(self) -> Optional[float]:
        """Calculate D30 (grain size at 30% passing)"""
        return self.get_percentile_size(30.0)

    def get_d50(self) -> Optional[float]:
        """Calculate D50 (median grain size at 50% passing)"""
        return self.get_percentile_size(50.0)

    def get_d60(self) -> Optional[float]:
        """Calculate D60 (grain size at 60% passing)"""
        return self.get_percentile_size(60.0)

    def get_uniformity_coefficient(self) -> Optional[float]:
        """Calculate uniformity coefficient Cu = D60/D10"""
        d10 = self.get_d10()
        d60 = self.get_d60()
        if d10 and d60 and d10 > 0:
            return d60 / d10
        return None

    def get_coefficient_of_curvature(self) -> Optional[float]:
        """Calculate coefficient of curvature Cc = (D30)²/(D10 × D60)"""
        d10 = self.get_d10()
        d30 = self.get_d30()
        d60 = self.get_d60()
        if d10 and d30 and d60 and d10 > 0 and d60 > 0:
            return (d30 ** 2) / (d10 * d60)
        return None

    def _interpolate_grain_size(self, target_percent: float) -> Optional[float]:
        """Interpolate grain size at target percent passing using the VBA path."""
        if not self.percent_passing or not self.particle_sizes:
            return None

        # Create working copies and ensure we have valid data
        percents = list(self.percent_passing)
        sizes = list(self.particle_sizes)

        if len(percents) != len(sizes):
            return None

        # Scan the sieve curve from coarse to fine like the workbook VBA.
        # This avoids choosing the wrong interval when flat percent-passing
        # plateaus create duplicate x-values.
        sorted_data = sorted(zip(sizes, percents), reverse=True)
        sizes_sorted, percents_sorted = zip(*sorted_data)
        sizes_sorted = list(sizes_sorted)
        percents_sorted = list(percents_sorted)

        # Check if target is within data range
        min_percent, max_percent = min(percents_sorted), max(percents_sorted)
        if target_percent < min_percent or target_percent > max_percent:
            # Add a validation message about missing data range
            missing_range_msg = f"Cannot calculate D{int(target_percent)} - data range is {min_percent:.1f}% to {max_percent:.1f}%"

            # Only add message if it's not already present
            if not any(msg.message.startswith(f"Cannot calculate D{int(target_percent)}")
                      for msg in self.validation_messages):
                self.validation_messages.append(ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    title="Incomplete grain size range",
                    message=missing_range_msg,
                    suggestion=f"Extend sieve analysis to include {target_percent}% passing range",
                    impact="Some characteristic grain sizes cannot be calculated"
                ))
            return None

        # Check for exact match first
        for size_mm, percent in sorted_data:
            if percent == target_percent:
                return size_mm

        # Find the two points that bracket our target percent
        for i in range(1, len(percents_sorted)):
            percent_prev = percents_sorted[i - 1]
            percent_curr = percents_sorted[i]
            if percent_prev == percent_curr:
                continue
            if percent_prev >= target_percent and percent_curr < target_percent:
                size_prev = sizes_sorted[i - 1]
                size_curr = sizes_sorted[i]
                return (
                    (size_prev - size_curr)
                    * (target_percent - percent_curr)
                    / (percent_prev - percent_curr)
                    + size_curr
                )

        return None

    def has_errors(self) -> bool:
        """Check if dataset has any error-level validation messages"""
        return any(msg.severity == ValidationSeverity.ERROR for msg in self.validation_messages)

    def has_warnings(self) -> bool:
        """Check if dataset has any warning-level validation messages"""
        return any(msg.severity == ValidationSeverity.WARNING for msg in self.validation_messages)

    def get_validation_summary(self) -> str:
        """Get a brief summary of validation status for GUI display"""
        if not self.validation_messages:
            return f"OK {len(self.particle_sizes)} pts"

        errors = sum(1 for msg in self.validation_messages if msg.severity == ValidationSeverity.ERROR)
        warnings = sum(1 for msg in self.validation_messages if msg.severity == ValidationSeverity.WARNING)

        if errors > 0:
            return f"ERROR {errors} error{'s' if errors > 1 else ''}"
        elif warnings > 0:
            return f"WARN {warnings} warning{'s' if warnings > 1 else ''}"
        else:
            return f"INFO {len(self.particle_sizes)} pts"

    def get_detailed_validation_report(self) -> str:
        """Get detailed validation report for display in info dialog"""
        if not self.validation_messages:
            return "OK: No validation issues detected"

        report = "Validation Report:\n" + "="*40 + "\n\n"
        for msg in self.validation_messages:
            report += f"{msg.severity.value.upper()}: {msg.title}\n"
            report += f"   {msg.message}\n"
            if msg.suggestion:
                report += f"   Suggestion: {msg.suggestion}\n"
            if msg.impact:
                report += f"   Impact: {msg.impact}\n"
            report += "\n"

        return report

    def classify(
        self,
        scheme: Optional[GrainClassificationScheme] = None,
        k_mean_ms: Optional[float] = None,
    ) -> ClassificationResult:
        """Return a structured ClassificationResult for this dataset.

        Parameters
        ----------
        scheme     : classification scheme (default: ISO14688)
        k_mean_ms  : mean hydraulic conductivity in m/s (for permeability class)
        """
        return _gc_classify(
            particle_sizes  = self.particle_sizes,
            percent_passing = self.percent_passing,
            cu              = self.get_uniformity_coefficient(),
            cc              = self.get_coefficient_of_curvature(),
            scheme          = scheme if scheme is not None else ISO14688,
            k_mean_ms       = k_mean_ms,
        )

    def classify_soil(self) -> str:
        """Return the classification label using the default (ISO 14688) scheme.

        .. deprecated::
            Use classify() which returns a structured ClassificationResult and
            supports scheme selection.  This wrapper is kept for call sites that
            only need a plain string and have no scheme context.
        """
        return self.classify().label

    def _calculate_simple_porosity(self) -> Optional[float]:
        """
        Calculate porosity using simple Excel formula
        n = 0.255 * (1 + 0.83^U)
        Where U = D60/D10 (uniformity coefficient)
        """
        try:
            # Get D10 and D60 for uniformity coefficient
            d10 = self.get_d10()
            d60 = self.get_d60()

            if d10 is None or d60 is None or d10 <= 0:
                return None

            # Calculate uniformity coefficient
            U = d60 / d10

            # Simple Excel formula
            n = 0.255 * (1 + 0.83**U)

            # Ensure reasonable porosity range
            if 0.1 <= n <= 0.8:
                return n
            else:
                self.validation_messages.append(ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    title="Calculated porosity outside typical range",
                    message=f"Simple formula gave porosity = {n:.3f}",
                    suggestion="Using default porosity value instead",
                    impact="May affect hydraulic conductivity calculations"
                ))
                return None

        except Exception as e:
            self.validation_messages.append(ValidationMessage(
                severity=ValidationSeverity.WARNING,
                title="Porosity calculation failed",
                message=f"Error in simple calculation: {str(e)}",
                suggestion="Using default porosity value",
                impact="May affect hydraulic conductivity calculations"
            ))
            return None

    def _calculate_urumovic_porosity(self) -> Optional[float]:
        """
        Calculate porosity using Urumovic & Urumovic (2016) method
        Based on geometric mean grain size and uniformity coefficient
        """
        try:
            # Calculate geometric mean grain size
            dgeom = self._calculate_geometric_mean_grain_size()
            if dgeom is None:
                return None

            # Calculate uniformity coefficient
            d10 = self.get_d10()
            d60 = self.get_d60()
            if d10 is None or d60 is None or d10 <= 0:
                return None

            U = d60 / d10

            # Urumovic & Urumovic (2016) coefficients
            # Based on dgeometric and U ranges
            if dgeom < 0.1:
                if U < 2:
                    coeffs = {
                        'a0': 0.239930340, 'a1': 0.032474578, 'a2': 0.057021316, 'a3': 0.000027594,
                        'b1': 0.116365861, 'b2': 0.050843630, 'b3': 0.000000000,
                        'PS': 0.000000000, 'Pd': 7.087465633
                    }
                elif U < 20:
                    coeffs = {
                        'a0': 0.059050678, 'a1': 0.000010100, 'a2': 0.000010001, 'a3': 0.000000996,
                        'b1': 0.143417294, 'b2': 0.118561346, 'b3': 0.040133037,
                        'PS': 0.014623250, 'Pd': 6.684384604
                    }
                else:  # U >= 20
                    coeffs = {
                        'a0': 0.170865853, 'a1': 0.000052100, 'a2': 0.000350603, 'a3': 0.002273075,
                        'b1': 0.045587305, 'b2': 0.061260545, 'b3': 0.054019240,
                        'PS': 0.096121263, 'Pd': 5.124402300
                    }
            else:  # dgeometric >= 0.1
                coeffs = {
                    'a0': 0.167837529, 'a1': 0.025095016, 'a2': 0.018411845, 'a3': 0.003629859,
                    'b1': 0.105251524, 'b2': 0.027111256, 'b3': 0.000000000,
                    'PS': 0.703849715, 'Pd': 4.735241378
                }

            # Calculate porosity using Urumovic polynomial
            import math

            # Convert dgeom to mm for calculation (if needed)
            dgeom_mm = dgeom  # Assuming dgeom is already in mm

            # Calculate the argument for sin/cos functions
            arg = (2 * math.pi * math.log(dgeom_mm)) / coeffs['Pd'] + coeffs['PS']

            # Urumovic formula: n = a0 + a1*sin(arg) + b1*cos(arg) + a2*sin(arg)*b2*cos(arg) + a3*sin(arg)*b3*cos(arg)
            sin_arg = math.sin(arg)
            cos_arg = math.cos(arg)

            ne = (coeffs['a0'] +
                  coeffs['a1'] * sin_arg +
                  coeffs['b1'] * cos_arg +
                  coeffs['a2'] * sin_arg * coeffs['b2'] * cos_arg +
                  coeffs['a3'] * sin_arg * coeffs['b3'] * cos_arg)

            # Ensure reasonable porosity range
            if 0.1 <= ne <= 0.8:
                return ne
            else:
                # If calculated porosity is outside reasonable range, return None
                self.validation_messages.append(ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    title="Calculated porosity outside typical range",
                    message=f"Urumovic calculation gave porosity = {ne:.3f}",
                    suggestion="Using default porosity value instead",
                    impact="May affect hydraulic conductivity calculations"
                ))
                return None

        except Exception as e:
            self.validation_messages.append(ValidationMessage(
                severity=ValidationSeverity.WARNING,
                title="Porosity calculation failed",
                message=f"Error in Urumovic calculation: {str(e)}",
                suggestion="Using default porosity value",
                impact="May affect hydraulic conductivity calculations"
            ))
            return None

    def _calculate_geometric_mean_grain_size(self) -> Optional[float]:
        """Calculate geometric mean grain size from distribution"""
        if not self.particle_sizes or not self.percent_passing:
            return None

        try:
            import math

            # Create sorted data by grain size (descending)
            sorted_data = sorted(zip(self.particle_sizes, self.percent_passing), reverse=True)
            sizes, percents = zip(*sorted_data)

            # Calculate weight fractions for each size interval
            weight_fractions = []
            log_sizes = []

            for i in range(len(sizes)):
                if i == 0:
                    # First interval: from 100% to current percent
                    weight_frac = (100.0 - percents[i]) / 100.0
                else:
                    # Subsequent intervals: difference between adjacent percents
                    weight_frac = (percents[i-1] - percents[i]) / 100.0

                if weight_frac > 0 and sizes[i] > 0:
                    weight_fractions.append(weight_frac)
                    log_sizes.append(math.log(sizes[i]))

            if not weight_fractions:
                return None

            # Calculate geometric mean: exp(sum(wi * ln(di)))
            weighted_log_sum = sum(w * log_d for w, log_d in zip(weight_fractions, log_sizes))
            geometric_mean = math.exp(weighted_log_sum)

            return geometric_mean

        except Exception:
            return None


class DataLoader:
    """Main data loader class for grain size analysis"""

    def __init__(self):
        self.supported_formats = ['.csv', '.xlsx', '.xls']
        self.loaded_datasets: List[GrainSizeData] = []

    def load_file(self, file_path: str) -> GrainSizeData:
        """Load a single file and return GrainSizeData object"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {file_ext}")

        if file_ext == '.csv':
            return self._load_csv(file_path)
        elif file_ext in ['.xlsx', '.xls']:
            return self._load_excel(file_path)

        raise NotImplementedError(f"Loader for {file_ext} not implemented")

    def load_multiple_files(self, file_paths: List[str]) -> List[GrainSizeData]:
        """Load multiple files and return list of GrainSizeData objects"""
        datasets = []
        errors = []

        for file_path in file_paths:
            try:
                dataset = self.load_file(file_path)
                datasets.append(dataset)
                logger.info(f"Successfully loaded: {os.path.basename(file_path)}")
            except Exception as e:
                error_msg = f"Error loading {os.path.basename(file_path)}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        if errors:
            logger.warning(f"Failed to load {len(errors)} out of {len(file_paths)} files")

        self.loaded_datasets.extend(datasets)
        return datasets

    def _parse_european_float(self, value: str) -> float:
        """Parse float that might use European format (comma as decimal separator)"""
        try:
            # Try standard format first
            return float(value.strip())
        except ValueError:
            # Try European format
            return float(value.strip().replace(',', '.'))

    def _detect_delimiter(self, file_path: str) -> tuple:
        """
        Simple delimiter detection - try common delimiters and return best match
        Returns: (delimiter, confidence_score)
        """
        delimiters = [',', ';', '\t', '|']

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                # Read first few lines for analysis
                sample_lines = []
                for i, line in enumerate(file):
                    if i >= 10:  # Analyze first 10 lines
                        break
                    sample_lines.append(line.strip())
        except Exception:
            return ',', 0.5  # Default fallback

        if not sample_lines:
            return ',', 0.5

        best_delimiter = ','
        best_score = 0

        for delimiter in delimiters:
            score = self._score_delimiter(sample_lines, delimiter)
            if score > best_score:
                best_score = score
                best_delimiter = delimiter

        return best_delimiter, best_score

    def _score_delimiter(self, sample_lines: list, delimiter: str) -> float:
        """Score a delimiter based on consistency and data patterns"""
        if not sample_lines:
            return 0.0

        # Count columns in each line
        column_counts = []
        numeric_column_counts = []

        for line in sample_lines:
            if not line:
                continue

            parts = line.split(delimiter)
            column_counts.append(len(parts))

            # Count numeric columns (handle both US and European decimal formats)
            numeric_count = 0
            for part in parts:
                try:
                    # Try standard US format first
                    float(part.strip())
                    numeric_count += 1
                except ValueError:
                    try:
                        # Try European format (comma as decimal separator)
                        float(part.strip().replace(',', '.'))
                        numeric_count += 1
                    except ValueError:
                        pass
            numeric_column_counts.append(numeric_count)

        if not column_counts:
            return 0.0

        # Consistency score - prefer consistent column counts
        most_common_count = max(set(column_counts), key=column_counts.count)
        consistency = column_counts.count(most_common_count) / len(column_counts)

        # Prefer at least 2 columns
        if most_common_count < 2:
            return 0.0

        # Numeric data score - expect some numeric columns
        avg_numeric = sum(numeric_column_counts) / len(numeric_column_counts) if numeric_column_counts else 0
        numeric_score = min(1.0, avg_numeric / 2)  # Normalize expecting ~2 numeric columns

        # Combined score
        return consistency * 0.7 + numeric_score * 0.3

    def _load_csv(self, file_path: str) -> GrainSizeData:
        """Load CSV file with flexible format detection"""
        try:
            # First detect the best delimiter
            delimiter, confidence = self._detect_delimiter(file_path)
            logger.info(f"Detected delimiter '{delimiter}' with confidence {confidence:.2f} for {os.path.basename(file_path)}")

            # Try different approaches to parse the CSV with detected delimiter
            dataset = None

            # Approach 1: Try our specific metadata format first
            try:
                dataset = self._load_csv_with_metadata(file_path, delimiter)
            except:
                pass

            # Approach 2: Try simple two-column format
            if dataset is None:
                try:
                    dataset = self._load_csv_simple_format(file_path, delimiter)
                except:
                    pass

            # Approach 3: Try multi-column format with headers
            if dataset is None:
                try:
                    dataset = self._load_csv_multi_column(file_path, delimiter)
                except:
                    pass

            if dataset is None:
                raise ValueError(f"Could not parse CSV file format in {file_path}")

            return dataset

        except Exception as e:
            raise ValueError(f"Error reading CSV file {file_path}: {str(e)}")

    def _load_csv_with_metadata(self, file_path: str, delimiter: str = ',') -> GrainSizeData:
        """Load CSV with metadata section (our format)"""
        metadata = {}
        particle_sizes = []
        percent_passing = []

        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=delimiter)
            data_section_started = False

            for row in reader:
                if not row or len(row) < 2:
                    continue

                # Check if this is the data header row (flexible matching)
                first_cell = row[0].strip().lower()
                if any(keyword in first_cell for keyword in
                       ['particle size', 'grain size', 'size', 'diameter', 'sieve']):
                    data_section_started = True
                    continue

                if not data_section_started:
                    # This is metadata
                    key = row[0].strip().lower()
                    value = row[1].strip()

                    # Flexible metadata parsing
                    if 'sample' in key or 'name' in key:
                        metadata['sample_name'] = value
                    elif 'temperature' in key or 'temp' in key:
                        try:
                            metadata['temperature'] = self._parse_european_float(value.replace('°C', '').replace('C', ''))
                        except ValueError:
                            metadata['temperature'] = 20.0
                    elif 'porosity' in key or 'void' in key:
                        try:
                            metadata['porosity'] = self._parse_european_float(value)
                        except ValueError:
                            metadata['porosity'] = 0.40
                    elif 'comment' in key or 'note' in key:
                        metadata['comments'] = value
                else:
                    # This is data
                    try:
                        size = self._parse_european_float(row[0])
                        percent = self._parse_european_float(row[1])
                        particle_sizes.append(size)
                        percent_passing.append(percent)
                    except (ValueError, IndexError):
                        continue

        return self._create_dataset(metadata, particle_sizes, percent_passing, file_path)

    def _load_csv_simple_format(self, file_path: str, delimiter: str = ',') -> GrainSizeData:
        """Load simple two-column CSV (size, percent passing)"""
        particle_sizes = []
        percent_passing = []

        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=delimiter)

            # Skip potential header row
            first_row = next(reader, None)
            if first_row:
                try:
                    # Try to parse first row as data
                    size = self._parse_european_float(first_row[0])
                    percent = self._parse_european_float(first_row[1])
                    particle_sizes.append(size)
                    percent_passing.append(percent)
                except (ValueError, IndexError):
                    # First row is probably a header, skip it
                    pass

            # Read data rows
            for row in reader:
                if not row or len(row) < 2:
                    continue
                try:
                    size = self._parse_european_float(row[0])
                    percent = self._parse_european_float(row[1])
                    particle_sizes.append(size)
                    percent_passing.append(percent)
                except (ValueError, IndexError):
                    continue

        metadata = {}
        return self._create_dataset(metadata, particle_sizes, percent_passing, file_path)

    def _load_csv_multi_column(self, file_path: str, delimiter: str = ',') -> GrainSizeData:
        """Load multi-column CSV with flexible header detection"""
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=delimiter)

            # Read first few rows to detect headers
            rows = []
            for i, row in enumerate(reader):
                rows.append(row)
                if i >= 10:  # Look at first 10 rows
                    break

        # Find header row and column indices
        size_col = None
        percent_col = None
        header_row_idx = None

        for i, row in enumerate(rows):
            if len(row) < 2:
                continue

            # Check if this looks like a header row
            for j, cell in enumerate(row):
                cell_lower = cell.strip().lower()

                # Look for size column
                if size_col is None and any(keyword in cell_lower for keyword in
                                          ['size', 'diameter', 'sieve', 'grain', 'particle', 'mm']):
                    size_col = j
                    header_row_idx = i

                # Look for percent passing column
                if percent_col is None and any(keyword in cell_lower for keyword in
                                             ['percent', '%', 'passing', 'finer', 'cumulative']):
                    percent_col = j
                    header_row_idx = i

            # If we found both columns, break
            if size_col is not None and percent_col is not None:
                break

        # If no headers found, assume first two columns
        if size_col is None or percent_col is None:
            size_col = 0
            percent_col = 1
            header_row_idx = 0

        # Ensure header_row_idx is not None
        if header_row_idx is None:
            header_row_idx = 0

        # Extract data
        particle_sizes = []
        percent_passing = []

        # Re-read file and extract data
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=delimiter)

            # Skip to data rows
            for i, row in enumerate(reader):
                if i <= header_row_idx:
                    continue

                if not row or len(row) <= max(size_col, percent_col):
                    continue

                try:
                    size = self._parse_european_float(row[size_col])
                    percent = self._parse_european_float(row[percent_col])
                    particle_sizes.append(size)
                    percent_passing.append(percent)
                except (ValueError, IndexError):
                    continue

        metadata = {}
        return self._create_dataset(metadata, particle_sizes, percent_passing, file_path)

    def _load_excel(self, file_path: str) -> GrainSizeData:
        """Load Excel file - conservative approach, requires manual mapping for complex files"""
        try:
            # Read Excel file with default settings only
            df = pd.read_excel(file_path)

            # Immediately require manual mapping for any Excel file that's not trivially simple
            raise ValueError(f"Excel files require manual column mapping to ensure data accuracy. Please use the column mapper to select the correct data columns.")

        except Exception as e:
            # Always require manual column mapping for Excel files
            raise ValueError(f"Excel files require manual column mapping. Please use the column mapper to select the correct data columns.")

    def _create_dataset(self, metadata: dict, particle_sizes: list, percent_passing: list, file_path: str) -> GrainSizeData:
        """Create GrainSizeData object with validation"""
        # Set defaults for missing metadata
        if 'sample_name' not in metadata:
            metadata['sample_name'] = os.path.splitext(os.path.basename(file_path))[0]
        if 'temperature' not in metadata:
            metadata['temperature'] = 20.0
        if 'porosity' not in metadata:
            metadata['porosity'] = 0.40

        # Validate data
        if not particle_sizes or not percent_passing:
            raise ValueError(f"No valid grain size data found in {file_path}")

        if len(particle_sizes) < 3:
            raise ValueError(f"Insufficient data points in {file_path} (minimum 3 required)")

        # Auto-sort data by particle size for consistent analysis
        # Combine size and percent data, sort by size (descending for grain size analysis)
        combined_data = list(zip(particle_sizes, percent_passing))
        combined_data.sort(key=lambda x: x[0], reverse=True)  # Sort by size, largest first

        # Extract sorted data
        particle_sizes = [item[0] for item in combined_data]
        percent_passing = [item[1] for item in combined_data]

        # Create and return GrainSizeData object
        return GrainSizeData(
            sample_name=metadata['sample_name'],
            temperature=metadata['temperature'],
            porosity=metadata['porosity'],
            particle_sizes=particle_sizes,
            percent_passing=percent_passing,
            comments=metadata.get('comments'),
            file_path=file_path
        )

    def _validate_auto_extracted_data(self, particle_sizes: list, percent_passing: list) -> bool:
        """Validate that auto-extracted data looks like actual grain size data"""
        if len(particle_sizes) < 3:
            return False  # Too few data points

        # Check for reasonable grain size range (0.001 to 1000 mm)
        min_size = min(particle_sizes)
        max_size = max(particle_sizes)
        if min_size < 0.001 or max_size > 1000:
            return False  # Unreasonable size range

        # Check for reasonable percentage range (0 to 100%)
        min_percent = min(percent_passing)
        max_percent = max(percent_passing)
        if min_percent < 0 or max_percent > 100:
            return False  # Invalid percentage range

        # Check for reasonable data spread
        if max_size / min_size < 2:
            return False  # Too narrow size range (likely not grain size data)

        if max_percent - min_percent < 10:
            return False  # Too narrow percentage range

        # Check for suspicious patterns that indicate wrong data
        # 1. Grain sizes should typically be in descending order for sieve data
        # 2. Percentages should generally decrease as grain size decreases (for cumulative passing)
        sorted_by_size = sorted(zip(particle_sizes, percent_passing), reverse=True)
        sizes_desc = [x[0] for x in sorted_by_size]
        percents_for_desc_sizes = [x[1] for x in sorted_by_size]

        # Check if percentages are roughly monotonic when sizes are sorted
        monotonic_violations = 0
        for i in range(1, len(percents_for_desc_sizes)):
            if percents_for_desc_sizes[i] > percents_for_desc_sizes[i-1]:
                monotonic_violations += 1

        # If more than 50% of data violates monotonic expectation, likely wrong data
        if monotonic_violations > len(percents_for_desc_sizes) * 0.5:
            return False

        # Check for monotonic tendency (most grain size data should be roughly monotonic)
        size_order_desc = sorted(particle_sizes, reverse=True)
        size_order_asc = sorted(particle_sizes)

        # Data should be either mostly ascending or descending by size
        if particle_sizes != size_order_desc and particle_sizes != size_order_asc:
            # Check if it's at least 70% monotonic
            violations_desc = sum(1 for i in range(1, len(particle_sizes))
                                 if particle_sizes[i] > particle_sizes[i-1])
            violations_asc = sum(1 for i in range(1, len(particle_sizes))
                                if particle_sizes[i] < particle_sizes[i-1])

            violation_ratio = min(violations_desc, violations_asc) / len(particle_sizes)
            if violation_ratio > 0.3:  # More than 30% violations
                return False

        return True  # Data looks reasonable

    def get_sample_summary(self, dataset: GrainSizeData) -> Dict[str, Any]:
        """Get a summary of a grain size dataset"""
        summary = {
            'sample_name': dataset.sample_name,
            'temperature': dataset.temperature,
            'porosity': dataset.porosity,
            'data_points': len(dataset.particle_sizes),
            'size_range': (min(dataset.particle_sizes), max(dataset.particle_sizes)),
            'percent_range': (min(dataset.percent_passing), max(dataset.percent_passing)),
            'd10': dataset.get_d10(),
            'd20': dataset.get_d20(),
            'd30': dataset.get_d30(),
            'd50': dataset.get_d50(),
            'd60': dataset.get_d60(),
            'uniformity_coefficient': dataset.get_uniformity_coefficient(),
            'coefficient_of_curvature': dataset.get_coefficient_of_curvature(),
            'soil_classification': dataset.classify_soil(),
            'comments': dataset.comments
        }

        return summary

    def validate_file_format(self, file_path: str) -> Tuple[bool, str]:
        """Validate if a file can be loaded"""
        try:
            dataset = self.load_file(file_path)
            return True, f"Valid file with {len(dataset.particle_sizes)} data points"
        except Exception as e:
            return False, str(e)

    def get_loaded_datasets(self) -> List[GrainSizeData]:
        """Get all loaded datasets"""
        return self.loaded_datasets.copy()

    def clear_loaded_datasets(self):
        """Clear all loaded datasets"""
        self.loaded_datasets.clear()


# Utility functions for GUI integration
def calculate_sieve_percent_passing(
    sieve_sizes: List[float],
    empty_weights: List[float],
    full_weights: List[float]
) -> Tuple[List[float], List[float]]:
    """
    Convert raw sieve weighing data into (sieve_size, cumulative % passing).

    Takes the three directly-measured columns from a standard sieve analysis
    (H.3 style) and returns the same two-column format the program uses
    everywhere else, so nothing downstream needs to change.

    Calculation:
        retained_weight  = (weight of sieve + sample) - (weight of empty sieve)
        total_weight     = sum of all retained weights
        weight_%         = retained_weight / total_weight * 100   (per sieve)
        % passing        = 100 - cumulative sum of weight_%        (coarsest → finest)

    Args:
        sieve_sizes:   Sieve opening sizes in mm (any order, will be sorted).
        empty_weights: Weight of each empty sieve in grams.
        full_weights:  Weight of each sieve + retained sample in grams.

    Returns:
        (sieve_sizes_sorted, percent_passing) sorted coarsest → finest,
        matching the format expected by GrainSizeData / _create_dataset.

    Raises:
        ValueError: If inputs are inconsistent or the total weight is zero.
    """
    if not sieve_sizes or not empty_weights or not full_weights:
        raise ValueError(
            "All three columns (sieve size, empty sieve weight, sieve+sample weight) "
            "must contain data."
        )

    if not (len(sieve_sizes) == len(empty_weights) == len(full_weights)):
        raise ValueError(
            f"Column length mismatch: sieve sizes ({len(sieve_sizes)}), "
            f"empty weights ({len(empty_weights)}), "
            f"full weights ({len(full_weights)}) must all be equal."
        )

    # Compute retained weight per sieve; skip rows with negative retained weight
    valid_pairs: List[Tuple[float, float]] = []
    for size, empty, full in zip(sieve_sizes, empty_weights, full_weights):
        retained = full - empty
        if retained < 0:
            logger.warning(
                f"Negative retained weight ({retained:.4f} g) for sieve {size} mm — row skipped."
            )
            continue
        valid_pairs.append((size, retained))

    if not valid_pairs:
        raise ValueError(
            "No valid sieve rows found after filtering negative retained weights."
        )

    total_weight = sum(w for _, w in valid_pairs)
    if total_weight <= 0:
        raise ValueError(
            "Total sample weight is zero or negative.  "
            "Check that 'Weight of Sieve + Sample' > 'Weight of Empty Sieve' "
            "for at least one row."
        )

    # Sort coarsest → finest (largest sieve size first)
    valid_pairs.sort(key=lambda x: x[0], reverse=True)

    result_sizes: List[float] = []
    result_passing: List[float] = []
    cumulative_retained_pct = 0.0

    for size, retained in valid_pairs:
        weight_pct = (retained / total_weight) * 100.0
        cumulative_retained_pct += weight_pct
        passing = max(0.0, 100.0 - cumulative_retained_pct)
        result_sizes.append(size)
        result_passing.append(round(passing, 6))

    return result_sizes, result_passing


def format_grain_size_stats(dataset: GrainSizeData) -> str:
    """Format grain size statistics for display"""
    d10 = dataset.get_d10()
    d20 = dataset.get_d20()
    d30 = dataset.get_d30()
    d50 = dataset.get_d50()
    d60 = dataset.get_d60()

    stats_text = f"""Grain Size Analysis Results:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sample: {dataset.sample_name}
Temperature: {dataset.temperature}°C
Porosity: {dataset.porosity}
Data Points: {len(dataset.particle_sizes)}

Characteristic Grain Sizes:
D10: {d10:.3f} mm  (Used by: Hazen, Terzaghi, Beyer, Slichter, Kozeny-Carman, Zunker, Zamarin, Sauerbrei)
D20: {d20:.3f} mm  (Used by: Shepherd, USBR)
D30: {d30:.3f} mm  (Used by: Uniformity calculations)
D50: {d50:.3f} mm  (Median grain size)
D60: {d60:.3f} mm  (Used by: Uniformity calculations)

Gradation Parameters:
Uniformity Coefficient (Cu): {dataset.get_uniformity_coefficient():.2f}
Coefficient of Curvature (Cc): {dataset.get_coefficient_of_curvature():.2f}

Classification: {dataset.classify_soil()}
Suitable for empirical K calculations: {'Yes' if d10 is not None and d10 > 0.01 else 'Limited (very fine material)'}"""

    if dataset.comments:
        stats_text += f"\n\nComments: {dataset.comments}"

    return stats_text


def get_test_data_files() -> List[str]:
    """Get list of available test data files"""
    test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data')
    csv_files = []

    if os.path.exists(test_data_dir):
        for file in os.listdir(test_data_dir):
            if file.endswith('.csv'):
                csv_files.append(os.path.join(test_data_dir, file))

    return sorted(csv_files)
