## Grain Size Analysis Program Plan ##

### Technology Stack
- **UI Framework**: PyQt6 (native look, good plotting integration, exe-friendly)
- **Plotting**: matplotlib with Qt backend (better exe compatibility than plotly)
- **Data**: pandas for data handling
- **Calculations**: numpy, scipy for hydraulic conductivity methods

### UI Layout (Main Window)
- **Top Toolbar**: Method selection (checkboxes for 20+ K calculation methods), export options
- **Left Panel** (300px): Control widgets
  - Data import section
  - Column mapping interface
  - Calculation parameters
  - Results summary/statistics
- **Right Panel**: matplotlib plot canvas with navigation toolbar
- **Status Bar**: Progress indicators, error messages

### Core Features
1. **Data Import**: CSV/Excel support with flexible column mapping
2. **K Calculations**: ~20 different hydraulic conductivity methods
3. **Visualization**: Interactive grain size distribution plots
4. **Export**: Results to CSV/Excel, plots to PNG/PDF
5. **Error Handling**: Method-specific validation and reporting

### Data Requirements
- Grain size distribution data (diameter vs cumulative %)
- Sample metadata (depth, location, etc.)
- Support for multiple samples per file 

