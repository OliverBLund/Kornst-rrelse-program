# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Grain Size Analysis application for calculating hydraulic conductivity (K-values) from grain size distribution data using multiple empirical methods. It's a PyQt6-based desktop application focused on geotechnical and hydrogeological analysis.

## Key Commands

### Running the Application
```bash
# Run the main application
python Program/main.py
```

### Dependencies
The application requires the following Python packages:
- PyQt6 (GUI framework)
- matplotlib (plotting)
- numpy (numerical computations)
- scipy (scientific computing)
- pandas (data handling)
- openpyxl (Excel file support)

## Architecture

### High-Level Architecture
The application follows a multi-tab, dataset-oriented architecture where:
- **MainWindow** serves as the primary container with menu, toolbar, and status bar
- **ControlPanel** (left side) handles file management, batch operations, and global settings
- **Right side** contains a tab widget with individual **DatasetTab** instances for each loaded dataset
- Each **DatasetTab** contains nested tabs: plot workspace, results tables, and statistics
- **ComparisonTab** and **ReportingTab** provide cross-dataset analysis capabilities

### Core Data Flow
```
CSV/Excel Files → DataLoader → GrainSizeData objects → KCalculator →
KCalculationResult objects → GUI visualization (plots/tables/reports)
```

### Key Modules

**Core Processing:**
- **Program/main.py**: Application entry point and QApplication initialization
- **Program/data_loader.py**: Flexible CSV/Excel loading with format auto-detection and validation
- **Program/k_calculations.py**: Hydraulic conductivity calculations using 12+ empirical methods
- **Program/report_generator.py**: Professional HTML/PDF report generation

**GUI Architecture:**
- **Program/gui/main_window.py**: Main application window with two-level tab system
- **Program/gui/control_panel.py**: Left panel for file management and batch processing
- **Program/gui/dataset_tab.py**: Individual dataset container with nested tabs
- **Program/gui/comparison_tab.py**: Cross-dataset comparison and analysis
- **Program/gui/reporting_tab.py**: Report generation interface
- **Program/gui/plot_widget.py** & **plot_workspace.py**: Matplotlib integration components
- **Program/gui/column_mapper.py**: CSV column mapping dialog for flexible data import

### Data Models and Processing

**GrainSizeData Class** (`data_loader.py`):
- Encapsulates sample data: grain sizes, percent passing, metadata
- Built-in validation for data ranges and monotonic checks
- Supports temperature (°C) and porosity (0-1) parameters

**KCalculator Class** (`k_calculations.py`):
- Implements 12+ empirical hydraulic conductivity methods
- Returns structured `KCalculationResult` objects with status codes
- Handles method-specific applicability conditions and warnings
- Applies temperature corrections using viscosity ratios

### UI State Management Patterns

**Multi-Dataset Architecture:**
- Each loaded dataset gets its own `DatasetTab` with independent plot/results/statistics
- Central `ControlPanel` manages batch operations across all datasets
- `ComparisonTab` enables side-by-side analysis of multiple datasets
- Tab titles show dataset names with status indicators

**Signal-Slot Communication:**
- Dataset tabs emit signals for data updates and calculation completion
- Main window coordinates cross-tab communication and global state
- Progress tracking through QProgressBar for long-running operations

## Important Implementation Details

### Data Import Strategy
The `DataLoader` implements a multi-stage detection system:
1. **Auto-detection**: Attempts to identify CSV format and headers automatically
2. **Format fallback**: Tries multiple delimiter and header combinations
3. **Manual mapping**: Falls back to `ColumnMapper` dialog for user-guided import
4. **Validation**: Comprehensive range checks and data quality validation

### Calculation Method Framework
Each hydraulic conductivity method in `KCalculator` follows this pattern:
- Method-specific applicability ranges (grain size, uniformity coefficient)
- Temperature correction via viscosity adjustment
- Returns `KCalculationResult` with status codes: OK, WARNING, ERROR, OUT_OF_RANGE
- Color-coded display in GUI based on result status

### Professional UI Design Patterns
- **Earth-tone color scheme**: Browns, blues, greens for geotechnical appearance
- **Consistent QGroupBox organization**: Logical section grouping throughout
- **Status-driven styling**: Color coding based on calculation result status
- **Progress feedback**: QProgressBar and status messages for user feedback

## Current Development Status

The application is in **Phase 1** (Prototyping) according to `development_roadmap.md`:

**Completed Features:**
- Multi-tab dataset architecture with nested plot/results/statistics tabs
- Batch processing system with file management
- Method selection dialog with color-coded results
- Basic plotting infrastructure with matplotlib integration
- Professional UI styling with geotechnical theme

**Next Phase Priorities:**
- Enhanced data validation and error handling
- Real calculation method implementations (currently using placeholder logic)
- Advanced plotting with full matplotlib integration
- Report generation functionality

## Development Patterns

### Error Handling Philosophy
- **Graceful degradation**: Multiple fallback strategies for data import
- **User-friendly messaging**: QMessageBox dialogs with clear explanations
- **Status-based feedback**: Visual indicators for calculation reliability
- **Comprehensive validation**: Range checks for all input parameters

### Code Organization Principles
- **Separation of concerns**: Clear division between data processing and GUI
- **Signal-driven architecture**: PyQt6 signals for loose coupling between components
- **Dataclass usage**: Structured data objects (`GrainSizeData`, `KCalculationResult`)
- **Type hints**: Comprehensive typing throughout for better maintainability