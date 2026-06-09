# Changelog
All notable changes to Grain Size Analysis - Hydraulic Conductivity Calculator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.9.2-beta] - 2026-06-08

### Added
- Group-aware comparison summaries for K-values and grain-size metrics across selected datasets
- Aggregate Details and Statistics views with overall and per-group summaries
- K distribution plot support for lognormal-style hydraulic-conductivity review, including ln(K) variance and standard deviation
- Results-tab summary strip showing OK-only K geometric mean, K arithmetic mean, and included method counts per dataset
- In-app activity/log overlay foundation for data-loading warnings and future program events

### Changed
- Excel import flow simplified so detected workbook sheets can load directly while still allowing remapping when needed
- Multi-sheet Excel selection now supports applying a shared sheet name across multiple selected workbooks
- Comparison plots and tables now use dataset group colors consistently where group context is active
- K summary calculations are centralized through the shared aggregation backend for Results, Statistics, Comparison, reports, and live exports
- Export and report wording now distinguishes K geometric mean from K arithmetic mean
- Full changelog now opens in the in-app Help & Documentation window instead of opening the raw Markdown file

### Fixed
- Raw sieve auto-detection no longer silently accepts obviously invalid columns without clearer validation pressure
- HydrogeoSieveXL2 warning parity for DATASET_2: Hazen, Hazen_1892, Kruger, and USBR are warned; Terzaghi and Kozeny-Carman remain included
- OK-only K geometric and arithmetic means now match the HydrogeoSieveXL2 inclusion philosophy more closely


## [0.9.1-beta] - 2026-04-24

### Added
- Built-in demo dataset set on the welcome screen based on the HydrogeoSieveXL2-3-11 inspired reference data in `test_data`
- Structured export folder layout for tables, workbooks, and per-dataset plot outputs
- Export scope selection that supports all datasets, current dataset, or selected dataset sets
- Plot text options shared through the plotting system so titles and axis labels can be adjusted more consistently

### Changed
- Welcome screen refreshed around recent sessions, compact quick actions, guide links, and current beta notes
- Export tab reorganized around live preview, grouped "files to create", and clearer dataset/file context
- Exported report/plot outputs now rely more directly on the shared plot rendering pipeline
- Export progress now uses the styled loading dialog and counts actual files instead of coarse export steps
- Exported plots now use white report-ready backgrounds for PNG, SVG, and PDF output

### Fixed
- CSV long/wide export preview now respects Grain Size Data, K-Value Results, Statistics, percentiles, gradation, and soil classification toggles
- Report/export plot desync issues where live plot settings were not fully reflected downstream
- Comparison plot sidebar sizing/toggle behavior and legend placement controls for outside positions
- Packaged `.xls` loading now includes `xlrd` so legacy Excel workbooks work in the built application


## [0.9.0-beta] - 2025-01-15

### Added
- **New Export Tab** with live data preview showing exactly what will be exported
- **Wide Format CSV Export** for statistical analysis in Excel/R/Python
- **Enhanced Welcome Screen** with recent files, quick help links, and scrollable changelog
- Real-time preview of K-results, grain data, and export format before exporting
- Side-by-side layout in export tab for better visibility

### Changed
- Improved export workflow with file count estimation
- Better organization of export options with clear visual separation
- Export tab now updates automatically when calculations complete

### Fixed
- Export tab now properly receives K-calculation results
- Column mapping issues with certain CSV formats


---

## [v1.9.0-alpha] - 2024-12-20

### Added
- **Comparison Tab** for analyzing multiple datasets side-by-side
- Method validation warnings with detailed explanation messages
- Ability to compare K-values across different calculation methods

### Changed
- Improved column mapping interface with better error messages
- Enhanced dataset loading with automatic format detection

### Fixed
- Bug where certain special characters in filenames caused loading failures
- Column mapper not properly handling headers with extra whitespace


---

## [v1.8.0-alpha] - 2024-11-30

### Added
- **Comprehensive Help System** with topics for all major features
- Help topics: Getting Started, File Formats, Methods Overview, Troubleshooting
- F1 key shortcut to open help dialog
- Enhanced reporting tab with customizable templates

### Changed
- Improved performance for datasets with 500+ data points
- Better memory management for large file operations

### Fixed
- Memory leak when loading multiple large datasets
- Crash when closing dataset tabs in certain conditions


---

## [v1.7.0-alpha] - 2024-11-10

### Added
- **Statistics Tab** with comprehensive grain size analysis
- Porosity calculation using both simple formula and Urumovic polynomial
- Grain classification (gravel, sand, silt, clay percentages)
- Gradation parameters (Cu, Cc) with validation

### Changed
- Improved plot customization options
- Better visual feedback for calculation status

### Fixed
- Incorrect D10 calculation for certain grain size distributions
- Plot not updating when switching between datasets


---

## [v1.6.0-alpha] - 2024-10-25

### Added
- **Initial K-Calculation Implementation** with 14+ empirical methods
- Support for methods: Hazen, Beyer, Kozeny-Carman, Terzaghi, Shepherd, and more
- Basic grain size distribution visualization
- CSV and Excel file import support
- Temperature and porosity parameter controls

### Changed
- N/A (Initial release)

### Fixed
- N/A (Initial release)


---

## Notes for Testers

**Current Status:** 0.9.2-beta - Ready for focused beta testing

**Known Review Areas:**
- Some irregular Excel layouts may still require manual mapping or remapping
- Data-loading logs, warning visibility, and remap entry points should be checked during testing

**Feedback:** Report issues with the file used, selected import path, expected result, and observed result.

**Testing Focus Areas:**
1. CSV and Excel import reliability, including remapping
2. HydrogeoSieveXL2 parity for K-values, warnings, and OK-only means
3. Comparison Details/Statistics behavior for groups and aggregates
4. Export/report consistency for geometric and arithmetic K summaries
