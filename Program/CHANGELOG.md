# Changelog
All notable changes to Grain Size Analysis - Hydraulic Conductivity Calculator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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

## Future Enhancements (Planned)

### For Beta Testing Phase
- [ ] Multi-language support (Danish, English)
- [ ] Batch processing for multiple files
- [ ] Export to PDF with plots and tables
- [ ] Custom calculation method editor
- [ ] Integration with laboratory database systems

### For v3.0.0 (Post-Beta)
- [ ] Machine learning-based permeability predictions
- [ ] 3D visualization of grain size distributions
- [ ] Cloud sync for project files
- [ ] Mobile companion app for field data collection


---

## Notes for Testers

**Current Status:** 0.9.0-beta - Ready for beta testing

**Known Issues:**
- Export tab may be slow with very large datasets (>10,000 points)
- Some edge cases in column auto-detection need manual mapping

**Feedback:** Please report any bugs or suggestions to [your contact info]

**Testing Focus Areas:**
1. File import reliability across different CSV formats
2. Accuracy of K-value calculations
3. Export functionality with various format combinations
4. UI/UX of the welcome screen and help system
