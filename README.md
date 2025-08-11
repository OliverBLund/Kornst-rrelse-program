# Grain Size Analysis - Hydraulic Conductivity Calculator

A professional PyQt6 application for calculating hydraulic conductivity (K-values) from grain size distribution data using multiple empirical methods.

## Features

- **Data Import**: Load grain size distribution data from CSV files
- **Multiple Calculation Methods**: 10+ empirical formulas including:
  - Hazen, Terzaghi, Beyer, Slichter, Kozeny-Carman
  - Shepherd, USBR, Zunker, Zamarin, Sauerbrei
- **Interactive Visualization**: 
  - Grain size distribution curves with D10, D30, D60 markers
  - K-value comparison bar charts
  - Real-time matplotlib plots with zoom/pan
- **Batch Processing**: Analyze multiple samples simultaneously
- **Export Capabilities**: Save results to CSV and plots to PNG/PDF/SVG

## Quick Start

### Running the Application

**Windows:**
```bash
run_app.bat
```

**Or directly:**
```bash
cd Program
python main.py
```

### Loading Data

1. Click "Add Files" in the control panel or use File → Open Data
2. Select CSV files with grain size data
3. CSV format should have two columns:
   - Column 1: Grain Size (mm)
   - Column 2: Cumulative % Passing

Example CSV:
```csv
Grain Size (mm),Cumulative % Passing
10.0,100.0
5.0,95.5
2.0,85.2
...
```

### Calculating K-Values

1. Load your grain size data
2. Set temperature and porosity parameters
3. Select calculation methods using checkboxes
4. Click "Calculate K Values"
5. View results in the plots and results table

### Exporting Results

- **Export Results**: File → Export Results (saves to CSV)
- **Export Plot**: File → Export Plot (saves as PNG/PDF/SVG)

## Requirements

- Python 3.8+
- PyQt6
- matplotlib
- numpy
- scipy
- pandas

## Project Structure

```
Program/
├── main.py              # Application entry point
├── data_loader.py       # CSV data loading and validation
├── k_calculations.py    # Hydraulic conductivity formulas
└── gui/
    ├── main_window.py   # Main application window
    ├── control_panel.py # Sample management panel
    └── plot_widget.py   # Matplotlib integration
```

## Sample Data

A test sample file `test_sample.csv` is included for demonstration.

## Development

The application is in active development. See `Program/development_roadmap.md` for planned features.