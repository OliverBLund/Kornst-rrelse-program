"""
Data loader module for grain size analysis
Handles CSV file loading and data validation
"""

import csv
import os
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging
import pandas as pd
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class GrainSizeData:
    """Data class for grain size distribution data"""
    sample_name: str
    temperature: float
    porosity: float
    particle_sizes: List[float]  # mm
    percent_passing: List[float]  # %
    comments: Optional[str] = None
    file_path: Optional[str] = None
    
    def __post_init__(self):
        """Validate data after initialization"""
        if len(self.particle_sizes) != len(self.percent_passing):
            raise ValueError("Particle sizes and percent passing must have same length")
        
        # Validate percent passing range
        if not all(0 <= pp <= 100 for pp in self.percent_passing):
            raise ValueError("Percent passing values must be between 0 and 100")
        
        # Validate particle sizes are positive and in reasonable range
        if not all(ps > 0 for ps in self.particle_sizes):
            raise ValueError("Particle sizes must be positive")
        
        # Check for reasonable grain size range (0.001 mm to 1000 mm)
        if any(ps < 0.001 or ps > 1000 for ps in self.particle_sizes):
            logger.warning(f"Unusual grain sizes detected: {min(self.particle_sizes):.4f} - {max(self.particle_sizes):.1f} mm")
        
        # Check if percent passing is monotonic (should generally increase with decreasing grain size)
        # Sort by particle size and check if percent passing increases
        sorted_data = sorted(zip(self.particle_sizes, self.percent_passing), reverse=True)
        for i in range(1, len(sorted_data)):
            if sorted_data[i][1] < sorted_data[i-1][1]:
                logger.warning(f"Non-monotonic percent passing detected at size {sorted_data[i][0]:.3f} mm")
        
        # Validate temperature and porosity
        if self.temperature < 0 or self.temperature > 50:
            logger.warning(f"Unusual temperature: {self.temperature}°C (typical range: 0-50°C)")
        
        if self.porosity < 0.1 or self.porosity > 0.8:
            logger.warning(f"Unusual porosity: {self.porosity} (typical range: 0.1-0.8)")
    
    def get_d10(self) -> Optional[float]:
        """Calculate D10 (grain size at 10% passing)"""
        return self._interpolate_grain_size(10.0)
    
    def get_d20(self) -> Optional[float]:
        """Calculate D20 (grain size at 20% passing)"""
        return self._interpolate_grain_size(20.0)
    
    def get_d30(self) -> Optional[float]:
        """Calculate D30 (grain size at 30% passing)"""
        return self._interpolate_grain_size(30.0)
    
    def get_d50(self) -> Optional[float]:
        """Calculate D50 (median grain size at 50% passing)"""
        return self._interpolate_grain_size(50.0)
    
    def get_d60(self) -> Optional[float]:
        """Calculate D60 (grain size at 60% passing)"""
        return self._interpolate_grain_size(60.0)
    
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
        """Interpolate grain size at target percent passing"""
        if not self.percent_passing or not self.particle_sizes:
            return None
        
        # Sort data by percent passing for interpolation
        sorted_data = sorted(zip(self.percent_passing, self.particle_sizes))
        percents, sizes = zip(*sorted_data)
        
        # Check if target is within range
        if target_percent < min(percents) or target_percent > max(percents):
            return None
        
        # Find exact match
        if target_percent in percents:
            idx = percents.index(target_percent)
            return sizes[idx]
        
        # Linear interpolation
        for i in range(len(percents) - 1):
            if percents[i] <= target_percent <= percents[i + 1]:
                # Linear interpolation
                x1, y1 = percents[i], sizes[i]
                x2, y2 = percents[i + 1], sizes[i + 1]
                
                # Interpolate in log space for grain sizes
                if y1 > 0 and y2 > 0:
                    log_y1, log_y2 = __import__('math').log(y1), __import__('math').log(y2)
                    log_y = log_y1 + (target_percent - x1) * (log_y2 - log_y1) / (x2 - x1)
                    return __import__('math').exp(log_y)
                else:
                    # Linear interpolation if log interpolation fails
                    return y1 + (target_percent - x1) * (y2 - y1) / (x2 - x1)
        
        return None
    
    def classify_soil(self) -> str:
        """Classify soil based on grain size distribution"""
        d10 = self.get_d10()
        d60 = self.get_d60()
        cu = self.get_uniformity_coefficient()
        cc = self.get_coefficient_of_curvature()
        
        # Basic size classification
        if d10 and d60:
            if d60 > 4.75:  # Larger than No. 4 sieve
                base_type = "Gravel"
            elif d60 > 0.075:  # Between No. 4 and No. 200 sieve
                base_type = "Sand"
            else:
                base_type = "Fine-grained"
        else:
            return "Insufficient data for classification"
        
        # Gradation classification
        if cu and cc and base_type in ["Sand", "Gravel"]:
            if base_type == "Sand":
                if cu >= 6 and 1 <= cc <= 3:
                    gradation = "Well-graded"
                else:
                    gradation = "Poorly-graded"
            else:  # Gravel
                if cu >= 4 and 1 <= cc <= 3:
                    gradation = "Well-graded"
                else:
                    gradation = "Poorly-graded"
            
            return f"{gradation} {base_type.lower()}"
        
        return base_type


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
    
    def _load_csv(self, file_path: str) -> GrainSizeData:
        """Load CSV file with flexible format detection"""
        metadata = {}
        particle_sizes = []
        percent_passing = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            # Try different approaches to parse the CSV
            dataset = None
            
            # Approach 1: Try our specific metadata format first
            try:
                dataset = self._load_csv_with_metadata(file_path)
            except:
                pass
            
            # Approach 2: Try simple two-column format
            if dataset is None:
                try:
                    dataset = self._load_csv_simple_format(file_path)
                except:
                    pass
            
            # Approach 3: Try multi-column format with headers
            if dataset is None:
                try:
                    dataset = self._load_csv_multi_column(file_path)
                except:
                    pass
            
            if dataset is None:
                raise ValueError(f"Could not parse CSV file format in {file_path}")
                
            return dataset
        
        except Exception as e:
            raise ValueError(f"Error reading CSV file {file_path}: {str(e)}")
    
    def _load_csv_with_metadata(self, file_path: str) -> GrainSizeData:
        """Load CSV with metadata section (our format)"""
        metadata = {}
        particle_sizes = []
        percent_passing = []
        
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
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
                            metadata['temperature'] = float(value.replace('°C', '').replace('C', ''))
                        except ValueError:
                            metadata['temperature'] = 20.0
                    elif 'porosity' in key or 'void' in key:
                        try:
                            metadata['porosity'] = float(value)
                        except ValueError:
                            metadata['porosity'] = 0.40
                    elif 'comment' in key or 'note' in key:
                        metadata['comments'] = value
                else:
                    # This is data
                    try:
                        size = float(row[0])
                        percent = float(row[1])
                        particle_sizes.append(size)
                        percent_passing.append(percent)
                    except (ValueError, IndexError):
                        continue
        
        return self._create_dataset(metadata, particle_sizes, percent_passing, file_path)
    
    def _load_csv_simple_format(self, file_path: str) -> GrainSizeData:
        """Load simple two-column CSV (size, percent passing)"""
        particle_sizes = []
        percent_passing = []
        
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            
            # Skip potential header row
            first_row = next(reader, None)
            if first_row:
                try:
                    # Try to parse first row as data
                    size = float(first_row[0])
                    percent = float(first_row[1])
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
                    size = float(row[0])
                    percent = float(row[1])
                    particle_sizes.append(size)
                    percent_passing.append(percent)
                except (ValueError, IndexError):
                    continue
        
        metadata = {}
        return self._create_dataset(metadata, particle_sizes, percent_passing, file_path)
    
    def _load_csv_multi_column(self, file_path: str) -> GrainSizeData:
        """Load multi-column CSV with flexible header detection"""
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            
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
            reader = csv.reader(file)
            
            # Skip to data rows
            for i, row in enumerate(reader):
                if i <= header_row_idx:
                    continue
                    
                if not row or len(row) <= max(size_col, percent_col):
                    continue
                    
                try:
                    size = float(row[size_col])
                    percent = float(row[percent_col])
                    particle_sizes.append(size)
                    percent_passing.append(percent)
                except (ValueError, IndexError):
                    continue
        
        metadata = {}
        return self._create_dataset(metadata, particle_sizes, percent_passing, file_path)
    
    def _load_excel(self, file_path: str) -> GrainSizeData:
        """Load Excel file with flexible format detection"""
        try:
            # Read Excel file - try first sheet by default
            excel_file = pd.ExcelFile(file_path)
            
            # If multiple sheets, use first one (could be enhanced to let user choose)
            sheet_name = excel_file.sheet_names[0]
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Try to detect grain size and percent passing columns
            particle_sizes = []
            percent_passing = []
            metadata = {}
            
            # Look for columns that might contain grain size data
            size_cols = []
            percent_cols = []
            
            for col in df.columns:
                col_lower = str(col).lower()
                if any(word in col_lower for word in ['size', 'diameter', 'grain', 'particle', 'sieve', 'mm']):
                    size_cols.append(col)
                elif any(word in col_lower for word in ['passing', 'percent', 'cumulative', 'finer', '%']):
                    percent_cols.append(col)
            
            # If we found potential columns, use them
            if size_cols and percent_cols:
                # Use first matching columns
                size_col = size_cols[0]
                percent_col = percent_cols[0]
                
                # Extract data, removing NaN values
                df_clean = df[[size_col, percent_col]].dropna()
                
                particle_sizes = df_clean[size_col].astype(float).tolist()
                percent_passing = df_clean[percent_col].astype(float).tolist()
            else:
                # Fall back to assuming first two numeric columns
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) >= 2:
                    df_clean = df[numeric_cols[:2]].dropna()
                    particle_sizes = df_clean.iloc[:, 0].astype(float).tolist()
                    percent_passing = df_clean.iloc[:, 1].astype(float).tolist()
                else:
                    raise ValueError(f"Could not find numeric columns in Excel file")
            
            # Extract metadata from non-numeric cells if present
            # Look for temperature, porosity, sample name in first few rows
            for idx, row in df.head(10).iterrows():
                for col in df.columns:
                    cell_value = str(row[col]).lower()
                    if 'temperature' in cell_value or 'temp' in cell_value:
                        # Try to extract temperature from next cell or same cell
                        try:
                            import re
                            temp_match = re.search(r'[\d.]+', str(row[col]))
                            if temp_match:
                                metadata['temperature'] = float(temp_match.group())
                        except:
                            pass
                    elif 'porosity' in cell_value:
                        try:
                            import re
                            por_match = re.search(r'[\d.]+', str(row[col]))
                            if por_match:
                                metadata['porosity'] = float(por_match.group())
                        except:
                            pass
            
            return self._create_dataset(metadata, particle_sizes, percent_passing, file_path)
            
        except Exception as e:
            raise ValueError(f"Error reading Excel file {file_path}: {str(e)}")
    
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
