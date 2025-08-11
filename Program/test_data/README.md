# Test Data for Grain Size Analysis

This directory contains real grain size distribution datasets from the literature for testing the hydraulic conductivity calculation methods.

## Data Sources

### Vukovic Datasets
- **vukovic_case1_dataset1.csv**: Example 1 Case 1 from Vukovic (15°C)
- **vukovic_case1_dataset2.csv**: Example 1 Case 1 from Vukovic (15°C) - more detailed
- **vukovic_example2_case1.csv**: Example 2 Case 1 from Vukovic (15°C)

### Odong Datasets  
- **odong_sample1.csv**: Sample 1 from Odong study (20°C)
- **odong_sample2.csv**: Sample 2 from Odong study (20°C)
- **odong_sample3.csv**: Sample 3 from Odong study (20°C)
- **odong_sample4.csv**: Sample 4 from Odong study (20°C)

### Field Test Data
- **thomson_borden_sand.csv**: Thomson SERDP Borden sand dataset
- **schillig_pvp4-5.csv**: Schillig PVP4-5 sample from elevation 289.5 masl
  - *Note: This dataset includes field-measured hydraulic conductivity values (Ks: 1.9e-3 to 1.4e-2 m/s) for validation*

## CSV Format

Each CSV file contains:
- Sample Name: Descriptive name
- Temperature: Testing temperature (°C)
- Porosity: Assumed or measured porosity
- Comments: Additional notes (if applicable)
- Data columns: Particle Size (mm), Percent Passing (%)

## Usage

These files can be loaded into the grain size analysis program to:
1. Test different empirical hydraulic conductivity calculation methods
2. Compare calculated vs. measured K values (where available)
3. Validate the program functionality with real-world data
4. Demonstrate the range of soil types and grain size distributions

## Expected K Value Ranges

Based on grain size characteristics:
- **Vukovic datasets**: Medium to coarse sand (K ≈ 1e-5 to 1e-3 m/s)
- **Odong samples**: Fine to medium sand (K ≈ 1e-6 to 1e-4 m/s)  
- **Thomson Borden**: Well-graded sand (K ≈ 1e-5 to 1e-3 m/s)
- **Schillig PVP4-5**: Measured K = 1.9e-3 to 1.4e-2 m/s (validation case)
