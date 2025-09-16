#!/usr/bin/env python3
"""
Simple test for data loading system - no Unicode characters
"""

import os
import sys
sys.path.append('Program')

from Program.data_loader import DataLoader, ValidationSeverity

def test_basic_functionality():
    """Test basic loading functionality"""
    print("TESTING DATA LOADING SYSTEM")
    print("="*40)

    # Create a simple test file
    with open('simple_test.csv', 'w') as f:
        f.write("""Grain Size (mm),Percent Passing (%)
10.0,100.0
5.0,98.5
2.0,95.2
1.0,88.1
0.5,75.3
0.25,58.7
0.125,38.9
0.075,22.5""")

    loader = DataLoader()

    print("\n1. Testing delimiter detection:")
    try:
        delimiter, confidence = loader._detect_delimiter('simple_test.csv')
        print(f"   Delimiter: {repr(delimiter)} (confidence: {confidence:.2f})")
    except Exception as e:
        print(f"   ERROR: {e}")

    print("\n2. Testing file loading:")
    try:
        dataset = loader.load_file('simple_test.csv')
        print(f"   SUCCESS: Loaded {len(dataset.particle_sizes)} data points")
        print(f"   Sample: {dataset.sample_name}")
        print(f"   Temperature: {dataset.temperature}°C")
        print(f"   Porosity: {dataset.porosity}")

        # Check validation messages
        print(f"   Validation messages: {len(dataset.validation_messages)}")
        for msg in dataset.validation_messages:
            print(f"     - {msg.severity.value.upper()}: {msg.title}")
            print(f"       {msg.message}")

        # Test GUI methods
        print(f"   GUI Summary: {dataset.get_validation_summary()}")
        print(f"   Has errors: {dataset.has_errors()}")
        print(f"   Has warnings: {dataset.has_warnings()}")

    except Exception as e:
        print(f"   ERROR: {e}")

    print("\n3. Testing characteristic grain sizes:")
    try:
        d10 = dataset.get_d10()
        d30 = dataset.get_d30()
        d50 = dataset.get_d50()
        d60 = dataset.get_d60()
        cu = dataset.get_uniformity_coefficient()

        print(f"   D10: {d10:.3f if d10 else 'N/A'} mm")
        print(f"   D30: {d30:.3f if d30 else 'N/A'} mm")
        print(f"   D50: {d50:.3f if d50 else 'N/A'} mm")
        print(f"   D60: {d60:.3f if d60 else 'N/A'} mm")
        print(f"   Cu: {cu:.2f if cu else 'N/A'}")
        print(f"   Classification: {dataset.classify_soil()}")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Clean up
    if os.path.exists('simple_test.csv'):
        os.remove('simple_test.csv')

    print("\n" + "="*40)
    print("Test complete!")

if __name__ == "__main__":
    test_basic_functionality()