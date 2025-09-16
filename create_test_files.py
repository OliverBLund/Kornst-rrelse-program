#!/usr/bin/env python3
"""
Create proper test files for the enhanced data loading system
"""

import os

def create_test_files():
    """Create comprehensive test files"""

    print("Creating test files...")

    # Test 1: Complete grain size distribution (0-100% range for proper D-value calculations)
    with open('test_complete.csv', 'w') as f:
        f.write("""Grain Size (mm),Percent Passing (%)
25.0,100.0
19.0,99.5
12.5,98.8
9.5,97.2
6.3,94.5
4.75,90.8
2.36,82.4
1.18,70.3
0.60,58.1
0.30,45.2
0.15,32.8
0.075,22.1
0.045,15.6
0.025,10.2
0.015,6.8
0.010,3.4
0.005,1.2""")

    # Test 2: Semicolon delimited (European format)
    with open('test_semicolon.csv', 'w') as f:
        f.write("""Size;Passing
10,0;100,0
5,0;85,0
2,0;68,0
1,0;52,0
0,5;38,0
0,25;26,0
0,125;18,0
0,075;12,0""")

    # Test 3: Tab delimited
    with open('test_tab.csv', 'w') as f:
        f.write("""Size	Passing
10.0	100.0
5.0	85.0
2.0	68.0
1.0	52.0
0.5	38.0
0.25	26.0
0.125	18.0
0.075	12.0""")

    # Test 4: With metadata
    with open('test_metadata.csv', 'w') as f:
        f.write("""Sample Name,Sandy Soil Test
Temperature,25
Porosity,0.42
Comments,Test sample with metadata

Grain Size (mm),Percent Passing (%)
10.0,100.0
5.0,85.0
2.0,68.0
1.0,52.0
0.5,38.0
0.25,26.0
0.125,18.0
0.075,12.0
0.05,8.0
0.01,2.0""")

    # Test 5: Non-monotonic data (should trigger warnings)
    with open('test_nonmonotonic.csv', 'w') as f:
        f.write("""Size,Passing
10.0,100.0
5.0,85.0
2.0,88.0
1.0,52.0
0.5,65.0
0.25,26.0""")

    # Test 6: Problematic format (should need manual mapping)
    with open('test_problematic.csv', 'w') as f:
        f.write("""Laboratory Test Results
Sample ID: ABC-123
Date: 2024-01-15
Technician: J. Smith

Sieve Analysis Results:
Mesh,Opening_mm,Mass_Retained_g,Cumulative_Passing_%
4,4.75,12.5,100.0
8,2.36,25.8,87.5
16,1.18,35.2,62.7
30,0.60,28.9,33.8
50,0.30,22.4,4.9
100,0.15,18.7,0.0""")

    print("Test files created:")
    print("  - test_complete.csv (complete 0-100% data)")
    print("  - test_semicolon.csv (semicolon delimiter)")
    print("  - test_tab.csv (tab delimiter)")
    print("  - test_metadata.csv (with sample metadata)")
    print("  - test_nonmonotonic.csv (data quality issues)")
    print("  - test_problematic.csv (complex format)")

if __name__ == "__main__":
    create_test_files()