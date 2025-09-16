#!/usr/bin/env python3
"""
Fixed test without Unicode issues
"""

import os
import sys
sys.path.append('Program')

from Program.data_loader import DataLoader

def test_basic_functionality():
    """Test basic loading functionality"""
    print("TESTING DATA LOADING SYSTEM")
    print("="*40)

    # Create a simple test file
    with open('test_sample.csv', 'w') as f:
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

    print("1. Testing delimiter detection:")
    try:
        delimiter, confidence = loader._detect_delimiter('test_sample.csv')
        print(f"   Delimiter: {repr(delimiter)} (confidence: {confidence:.2f})")
    except Exception as e:
        print(f"   ERROR: {e}")

    print("2. Testing file loading:")
    try:
        dataset = loader.load_file('test_sample.csv')
        print(f"   SUCCESS: Loaded {len(dataset.particle_sizes)} data points")
        print(f"   Sample: {dataset.sample_name}")
        print(f"   Temperature: {dataset.temperature} C")
        print(f"   Porosity: {dataset.porosity}")

        # Check validation messages
        print(f"   Validation messages: {len(dataset.validation_messages)}")
        for msg in dataset.validation_messages:
            print(f"     - {msg.severity.value.upper()}: {msg.title}")

        # Test GUI methods
        summary = dataset.get_validation_summary()
        print(f"   GUI Summary: {summary}")
        print(f"   Has errors: {dataset.has_errors()}")
        print(f"   Has warnings: {dataset.has_warnings()}")

        print("3. Testing characteristic grain sizes:")
        d10 = dataset.get_d10()
        d30 = dataset.get_d30()
        d50 = dataset.get_d50()
        d60 = dataset.get_d60()
        cu = dataset.get_uniformity_coefficient()

        print(f"   D10: {d10:.3f if d10 else 'None'} mm")
        print(f"   D30: {d30:.3f if d30 else 'None'} mm")
        print(f"   D50: {d50:.3f if d50 else 'None'} mm")
        print(f"   D60: {d60:.3f if d60 else 'None'} mm")
        print(f"   Cu: {cu:.2f if cu else 'None'}")
        print(f"   Classification: {dataset.classify_soil()}")

    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()

    # Clean up
    if os.path.exists('test_sample.csv'):
        os.remove('test_sample.csv')

    print("="*40)
    print("Test complete!")

if __name__ == "__main__":
    test_basic_functionality()