# Changelog
All notable changes to Grain Size Analysis - Hydraulic Conductivity Calculator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.9.2-beta] - 2026-06-09

### Added
- Group-aware comparison summaries for K-values and grain-size metrics across selected datasets.
- Aggregate Details and Statistics modes with overall and per-group summaries for K and grain-size metrics.
- Shared comparison snapshot/aggregation layer for Details, Statistics, plots, reports, and exports.
- K distribution plot for lognormal-style hydraulic-conductivity review, including ln(K) variance and standard deviation.
- Plot data drawers for single-sample and comparison plots, showing the exact data behind the active plot.
- Direct drawer export for the currently visible plot data table.
- Results-tab K summary cards for OK-only geometric mean, arithmetic mean, and included method counts per dataset.
- Arithmetic mean grain size per dataset for downstream summaries and aggregate reporting.
- In-app activity/log overlay foundation for data-loading warnings and future program events.
- Visible remap access from dataset/sample surfaces so a loaded file can be corrected without digging through inspector dialogs.

### Changed
- Excel import flow simplified so detected workbook sheets can load directly while still allowing mapping/remapping when needed.
- Multi-sheet Excel selection now supports applying a shared sheet name across multiple selected workbooks.
- Welcome quick action wording changed from "Processed Curve Data" to "Processed Sieve Data" to better match "Raw Sieve Weighings".
- Column mapper smart selection remains available as a fallback for irregular Excel layouts, but the normal Excel path reaches it less often.
- K summary calculations are centralized through the shared aggregation backend for Results, Details, Statistics, Comparison, reports, and exports.
- OK-only K mean handling now follows the HydrogeoSieveXL2 inclusion philosophy more closely.
- Export and report wording now distinguishes K geometric mean from K arithmetic mean.
- Details aggregate mode separates summary grain rows from method aggregates so sorting does not mix incompatible row types.
- Statistics aggregate mode now includes group summaries and tabular results below the plot area.
- Individual-sample Statistics now uses structured Grain-size summary, Hydraulic conductivity, and Review/reference sections instead of a dense grid of scrollable text boxes.
- Comparison plots and tables now use dataset group colors consistently where group context is active.
- Distribution curve markers now default to D10, D50, and D60 instead of D10, D30, and D60.
- K-value plots default to a linear Y-axis, with log scaling available as an explicit option.
- K-value plots clarify geometric and arithmetic mean reference lines.
- Grain-size histogram now uses retained weight percent instead of generic frequency terminology.
- Grain-size histogram fraction labels now respect the active stratigraphy/classification scheme.
- Plot controls sidebars are resizable and collapse without leaving reserved blank space in the plot area.
- Plot export controls are more consistent between single-sample and comparison plot sidebars, including PNG access.
- Export-tab plot preview and export wording now make it clearer whether the output is a figure file or plot data table.
- Full changelog now opens in the in-app Help & Documentation window instead of opening the raw Markdown file.

### Fixed
- Raw sieve auto-detection no longer silently accepts obviously invalid columns such as loss-percent rows or numeric header artifacts as sieve/weight columns.
- HydrogeoSieveXL2 warning parity for DATASET_2: Hazen, Hazen_1892, Kruger, and USBR are warned; Terzaghi and Kozeny-Carman remain included.
- OK-only K geometric and arithmetic means now match the HydrogeoSieveXL2 inclusion philosophy more closely.
- K-value methods marked with warnings are excluded from OK-only means instead of being silently averaged into the accepted population.
- Grain-size histogram drawer/export now uses histogram fraction rows instead of accidentally exporting cumulative curve data.
- K-value histogram and related K plots no longer default to log-scaled Y-axis behavior.
- Min/max reference lines were removed from K plots to reduce clutter and keep the mean references clearer.
- Welcome-screen hover help no longer depends on native black Qt tooltips; welcome action buttons use a readable in-window tooltip overlay.
- Plot controls sidebar no longer reserves a blank vertical strip when the controls are closed.
- SVG/PNG sidebar export handling was tightened so requested export formats are written with the expected file type and extension.
- Details and Statistics sidebars were made less prone to clipped content by tightening summaries and improving scroll/resizing behavior.
- Individual-sample Statistics no longer shows placeholder in-tab Excel/CSV export buttons; export remains handled through the Export tab and plot/data drawers.
- Report and export K summaries now draw from the same shared calculation results used by the live UI.

### Manual QA Checklist
- Start the app and confirm the welcome quick actions, readable hover help, Help pages, and Full Changelog window.
- Load 6-10 NBAL Excel files as processed sieve data, use shared sheet-name selection, and confirm the mapper appears only when review is needed.
- Load `test_new_calc.xlsx` through the raw sieve path and confirm raw/processed pathway warnings and bad column choices are visible.
- Compare demo/reference K results against HydrogeoSieveXL2 expectations, especially OK-only geometric and arithmetic means.
- Assign datasets to groups, then check Details and Statistics in Aggregate mode for overall and per-group summaries.
- Review single-sample and comparison plots: distribution curve D10/D50/D60, K means, histogram fractions, K distribution, and plot data drawers.
- Export plot drawer data, figure files, aggregate tables, and a report; confirm labels, units, and geometric/arithmetic K wording stay consistent.


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

**Current Status:** 0.9.2-beta - Ready for focused beta testing after the data-loading, calculation, aggregate, plotting, report, and export passes.

**Known Review Areas:**
- Irregular Excel layouts may still require manual mapping or remapping.
- Data-loading logs, warning visibility, and raw-vs-processed pathway feedback should be checked during testing.
- Plot/export/report wording should be checked carefully wherever units or geometric/arithmetic K means are shown.

**Feedback:** Report issues with the file used, selected import path, expected result, and observed result.

**Short Manual QA Checklist:**
- Welcome screen: quick actions, readable hover help, demo data, Help topics, and Full Changelog.
- Data loading: processed CSV, raw sieve CSV, NBAL Excel batch, shared sheet-name selection, and remap recovery.
- Calculations: HydrogeoSieveXL2 parity for warnings, valid methods, OK-only geometric mean, and arithmetic mean.
- Details/Statistics: Individual vs Aggregate mode, group assignment, overall summaries, and per-group summaries.
- Plots: single and comparison distribution curves, K bar/histogram views, grain histogram scheme labels, K distribution, and table drawers.
- Output: drawer CSV export, plot PNG/SVG export, Export tab tables, aggregate outputs, and report generation.
