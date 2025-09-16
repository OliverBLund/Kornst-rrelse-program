#!/usr/bin/env python3
"""
Comprehensive test script for the enhanced data loading system
This will test all aspects: delimiter detection, validation, error handling
"""

import os
import sys
sys.path.append('Program')

from Program.data_loader import DataLoader, ValidationSeverity

def create_test_files():
    """Create various test files to thoroughly test the system"""

    print("Creating comprehensive test files...")

    # Test 1: Perfect monotonic data (should load with no warnings)
    with open('test_perfect.csv', 'w') as f:
        f.write("""Grain Size (mm),Percent Passing (%)
10.0,100.0
5.0,98.5
2.0,95.2
1.0,88.1
0.5,75.3
0.25,58.7
0.125,38.9
0.075,22.5""")

    # Test 2: Non-monotonic data (should show warnings)
    with open('test_nonmonotonic.csv', 'w') as f:
        f.write("""Size,Passing
10.0,100.0
5.0,98.5
2.0,99.2
1.0,88.1
0.5,90.3
0.25,58.7""")

    # Test 3: Semicolon delimiter (should auto-detect)
    with open('test_semicolon.csv', 'w') as f:
        f.write("""Size;Passing
10,0;100,0
5,0;98,5
2,0;95,2
1,0;88,1
0,5;75,3""")

    # Test 4: Tab delimiter (should auto-detect)
    with open('test_tab.csv', 'w') as f:
        f.write("""Size	Passing
10.0	100.0
5.0	98.5
2.0	95.2
1.0	88.1""")

    # Test 5: Extreme values (should show warnings)
    with open('test_extreme.csv', 'w') as f:
        f.write("""Grain Size (mm),Percent Passing (%)
1000.0,100.0
0.001,50.0
0.0001,10.0""")

    # Test 6: Problematic format (should fail auto-loading)
    with open('test_problematic.csv', 'w') as f:
        f.write("""Lab Report - Sample XYZ
Test Date: 2024-01-15
Operator: John Smith

Sieve Analysis Results:
Sieve,Opening,Mass Retained,Cumulative Passing
#4,4.75,25.5,100.0
#8,2.36,38.2,85.2""")

    print("✅ Test files created")


def test_delimiter_detection():
    """Test delimiter detection functionality"""
    print("\n" + "="*50)
    print("TESTING DELIMITER DETECTION")
    print("="*50)

    loader = DataLoader()

    test_cases = [
        ('test_perfect.csv', ',', 'Comma CSV'),
        ('test_semicolon.csv', ';', 'Semicolon CSV'),
        ('test_tab.csv', '\t', 'Tab-delimited CSV'),
    ]

    for filename, expected_delimiter, description in test_cases:
        if os.path.exists(filename):
            try:
                detected_delimiter, confidence = loader._detect_delimiter(filename)
                status = "✅ PASS" if detected_delimiter == expected_delimiter else "❌ FAIL"
                print(f"{status} {description}:")
                print(f"  Expected: {repr(expected_delimiter)}")
                print(f"  Detected: {repr(detected_delimiter)} (confidence: {confidence:.2f})")
            except Exception as e:
                print(f"❌ ERROR {description}: {e}")
        else:
            print(f"⚠️  SKIP {description}: File not found")


def test_data_loading_and_validation():
    """Test data loading with validation"""
    print("\n" + "="*50)
    print("TESTING DATA LOADING & VALIDATION")
    print("="*50)

    loader = DataLoader()

    test_files = [
        ('test_perfect.csv', 'Perfect data', True, 0, 0),  # filename, description, should_load, expected_warnings, expected_errors
        ('test_nonmonotonic.csv', 'Non-monotonic data', True, 1, 0),
        ('test_extreme.csv', 'Extreme grain sizes', True, 1, 0),
        ('test_semicolon.csv', 'Semicolon format', True, 0, 0),
        ('test_tab.csv', 'Tab format', True, 0, 0),
        ('test_problematic.csv', 'Problematic format', False, 0, 0),
    ]

    for filename, description, should_load, expected_warnings, expected_errors in test_files:
        print(f"\nTesting: {description} ({filename})")

        if not os.path.exists(filename):
            print(f"  ⚠️  SKIP: File not found")
            continue

        try:
            dataset = loader.load_file(filename)

            if should_load:
                print(f"  ✅ LOADED: {len(dataset.particle_sizes)} data points")
                print(f"  📊 Sample: {dataset.sample_name}")
                print(f"  🌡️  Temperature: {dataset.temperature}°C")
                print(f"  🕳️ Porosity: {dataset.porosity}")

                # Check validation messages
                warnings = len([m for m in dataset.validation_messages if m.severity == ValidationSeverity.WARNING])
                errors = len([m for m in dataset.validation_messages if m.severity == ValidationSeverity.ERROR])

                print(f"  📋 Validation: {warnings} warnings, {errors} errors")

                if dataset.validation_messages:
                    for msg in dataset.validation_messages:
                        print(f"    {msg.get_icon()} {msg.title}: {msg.message}")
                        if msg.suggestion:
                            print(f"      💡 {msg.suggestion}")

                # Test the GUI summary methods
                summary = dataset.get_validation_summary()
                print(f"  📈 GUI Summary: {summary}")

            else:
                print(f"  ❌ UNEXPECTED SUCCESS: Should have failed")

        except Exception as e:
            if not should_load:
                print(f"  ✅ EXPECTED FAILURE: {str(e)}")
            else:
                print(f"  ❌ UNEXPECTED FAILURE: {str(e)}")


def test_characteristic_grain_sizes():
    """Test D10, D30, D50, D60 calculations"""
    print("\n" + "="*50)
    print("TESTING CHARACTERISTIC GRAIN SIZE CALCULATIONS")
    print("="*50)

    loader = DataLoader()

    if os.path.exists('test_perfect.csv'):
        try:
            dataset = loader.load_file('test_perfect.csv')

            print(f"Sample: {dataset.sample_name}")
            print(f"D10: {dataset.get_d10():.3f} mm")
            print(f"D20: {dataset.get_d20():.3f} mm")
            print(f"D30: {dataset.get_d30():.3f} mm")
            print(f"D50: {dataset.get_d50():.3f} mm")
            print(f"D60: {dataset.get_d60():.3f} mm")
            print(f"Uniformity Coefficient (Cu): {dataset.get_uniformity_coefficient():.2f}")
            print(f"Coefficient of Curvature (Cc): {dataset.get_coefficient_of_curvature():.2f}")
            print(f"Soil Classification: {dataset.classify_soil()}")

        except Exception as e:
            print(f"❌ ERROR: {e}")
    else:
        print("⚠️  SKIP: test_perfect.csv not found")


def main():
    print("🧪 COMPREHENSIVE DATA LOADING TEST SUITE")
    print("="*60)

    # Clean up old test files
    test_files = ['test_perfect.csv', 'test_nonmonotonic.csv', 'test_semicolon.csv',
                  'test_tab.csv', 'test_extreme.csv', 'test_problematic.csv']

    for f in test_files:
        if os.path.exists(f):
            os.remove(f)

    # Run tests
    create_test_files()
    test_delimiter_detection()
    test_data_loading_and_validation()
    test_characteristic_grain_sizes()

    print("\n" + "="*60)
    print("🎯 TEST SUMMARY")
    print("="*60)
    print("All tests completed. Check results above for any issues.")
    print("If you see unexpected results, the system needs further debugging.")

    # Clean up test files
    print("\nCleaning up test files...")
    for f in test_files:
        if os.path.exists(f):
            os.remove(f)
    print("✅ Cleanup complete")


if __name__ == "__main__":
    main()