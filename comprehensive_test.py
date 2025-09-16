#!/usr/bin/env python3
"""
Comprehensive test of the data loading system with all test files
"""

import os
import sys
sys.path.append('Program')

from Program.data_loader import DataLoader, ValidationSeverity

def test_file(file_path, description):
    """Test loading a specific file"""
    print(f"\n--- Testing {description} ---")
    print(f"File: {file_path}")

    if not os.path.exists(file_path):
        print("   ERROR: File not found")
        return

    loader = DataLoader()

    try:
        # Test delimiter detection
        delimiter, confidence = loader._detect_delimiter(file_path)
        print(f"   Delimiter: {repr(delimiter)} (confidence: {confidence:.2f})")

        # Test file loading
        dataset = loader.load_file(file_path)
        print(f"   SUCCESS: Loaded {len(dataset.particle_sizes)} data points")
        print(f"   Sample: {dataset.sample_name}")
        print(f"   Temperature: {dataset.temperature}C")
        print(f"   Porosity: {dataset.porosity}")

        # Validation messages
        if dataset.validation_messages:
            print(f"   Validation messages: {len(dataset.validation_messages)}")
            for msg in dataset.validation_messages:
                print(f"     - {msg.severity.value.upper()}: {msg.title}")
        else:
            print("   No validation issues")

        # D-values (safe formatting)
        d10 = dataset.get_d10()
        d30 = dataset.get_d30()
        d50 = dataset.get_d50()
        d60 = dataset.get_d60()
        cu = dataset.get_uniformity_coefficient()

        print("   Characteristic sizes:")
        print(f"     D10: {d10:.3f} mm" if d10 is not None else "     D10: N/A mm")
        print(f"     D30: {d30:.3f} mm" if d30 is not None else "     D30: N/A mm")
        print(f"     D50: {d50:.3f} mm" if d50 is not None else "     D50: N/A mm")
        print(f"     D60: {d60:.3f} mm" if d60 is not None else "     D60: N/A mm")
        print(f"     Cu: {cu:.2f}" if cu is not None else "     Cu: N/A")

        # Classification
        classification = dataset.classify_soil()
        print(f"   Classification: {classification}")

        return True

    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run comprehensive tests"""
    print("COMPREHENSIVE DATA LOADING SYSTEM TEST")
    print("=" * 50)

    # Test files to check
    test_files = [
        ('test_complete.csv', 'Complete grain size distribution'),
        ('test_semicolon.csv', 'Semicolon delimited format'),
        ('test_tab.csv', 'Tab delimited format'),
        ('test_metadata.csv', 'File with metadata'),
        ('test_nonmonotonic.csv', 'Non-monotonic data (should warn)'),
        ('test_problematic.csv', 'Problematic format (should fail or need mapping)')
    ]

    results = []
    for file_path, description in test_files:
        success = test_file(file_path, description)
        results.append((file_path, success))

    # Summary
    print(f"\n{'=' * 50}")
    print("TEST SUMMARY:")
    for file_path, success in results:
        status = "PASS" if success else "FAIL"
        print(f"   {file_path}: {status}")

    passed = sum(1 for _, success in results if success)
    print(f"\nTotal: {passed}/{len(results)} tests passed")

if __name__ == "__main__":
    main()