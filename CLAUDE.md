# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Grain Size Analysis application for calculating hydraulic conductivity (K-values) from grain size distribution data using multiple empirical methods. It's a PyQt6-based desktop application focused on geotechnical and hydrogeological analysis.

## Key Commands

### Running the Application
```bash
# Run the main application
python Program/main.py

# Or use the batch file
run_app.bat
```

### Testing
```bash
# Test data loading functionality
python test_all_loading.py

# Test data flow
python test_data_flow.py
```

### Dependencies
The application requires the following Python packages (already installed):
- PyQt6 (GUI framework)
- matplotlib (plotting)
- numpy (numerical computations)
- scipy (scientific computing)
- pandas (data handling)
- openpyxl (Excel file support)

## Architecture

### Core Modules

1. **Program/main.py**: Entry point, initializes PyQt6 application
2. **Program/gui/main_window.py**: Main window with tabbed interface (Plots, Results, Statistics)
3. **Program/data_loader.py**: CSV data loading with flexible format detection
4. **Program/k_calculations.py**: 12+ hydraulic conductivity calculation methods (Hazen, Terzaghi, Beyer, etc.)

### GUI Components (Program/gui/)
- **control_panel.py**: Left panel for file management and batch processing
- **plot_widget.py**: Matplotlib integration for grain size distribution plots
- **column_mapper.py**: Dialog for mapping CSV columns to data fields

### Data Processing Flow
1. Load CSV/Excel files → auto-detect format with fallback to manual column mapping
2. Validate data (range checks, monotonic verification)
3. Calculate characteristic grain sizes (D10, D20, D30, D50, D60)
4. Apply selected K-calculation methods with temperature/porosity corrections
5. Display results in tables, plots, and statistics

### Supported File Formats
- **CSV**: Standard format, no headers, custom delimiters
- **Excel**: .xlsx and .xls files (single or multi-sheet)
- **Column Mapping**: Automatic detection with manual fallback dialog
- **Validation**: Grain size range (0.001-1000 mm), monotonic checks, porosity/temperature bounds

## Important Implementation Details

### Hydraulic Conductivity Methods
The application implements these empirical formulas in `k_calculations.py`:
- Each method has specific applicability conditions (grain size ranges, uniformity coefficients)
- Temperature corrections are applied using viscosity ratios
- Methods return structured `KCalculationResult` objects with status indicators

### Data Format Support
The `DataLoader` class supports three CSV formats:
1. Metadata format (sample name, temperature, porosity headers)
2. Simple two-column (size, percent passing)
3. Multi-column with flexible header detection

### UI State Management
- Multiple datasets can be loaded simultaneously
- Sample selector in toolbar for switching between datasets
- Batch processing capabilities through control panel
- Method selection dialog for choosing calculation methods

## Development Patterns

### Error Handling
- Graceful fallback for CSV parsing (tries multiple format detectors)
- Method-specific validation with status codes (OK, WARNING, ERROR)
- User-friendly error messages via QMessageBox

### Styling
- Professional geotechnical theme with earth-tone colors
- Consistent use of QGroupBox for section organization
- Color-coded method results for visual distinction

## Current Development Phase

The application is in the prototyping phase (Phase 1 of development_roadmap.md) with focus on:
- Core functionality implementation
- Professional UI/UX design
- Batch processing capabilities
- Method visualization and comparison

Future phases will add advanced features like Excel support, report generation, and machine learning integration.