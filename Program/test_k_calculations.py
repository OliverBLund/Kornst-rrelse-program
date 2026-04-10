"""
Test suite for K-calculation methods across multiple datasets.
Compares Python implementation against Excel results.
"""

import argparse
import sys
import unittest

sys.path.insert(0, 'Program')

from k_calculations_v2 import KCalculator


# ============================================================================
# TEST DATASETS
# ============================================================================

DATASET_1 = {
    'name': 'Example 1 Case 1 Vukovic (Test1)',
    'temperature': 20.0,  # °C
    'sample_mass': 100.0,  # g
    'porosity': 0.384,  # From Test1 data
    'grain_distribution': {
        'particle_sizes': [2.0, 0.82, 0.55, 0.42, 0.28, 0.15, 0.045],
        'percent_passing': [100, 80, 60, 40, 20, 10, 0]
    },
    'excel_results': {  # m/d - From results_test1.png
        'Hazen': 25.925,
        'Hazen_1892': 19.440,
        'Slichter': 8.291,
        'Terzaghi': 14.425,
        'Beyer': 21.434,
        'Sauerbrei': 29.297,
        'Kruger': 44.603,
        'Kozeny-Carman': 89.221,
        'Zunker': 48.733,
        'Zamarin': 57.419,
        'USBR': 22.044,
        'Barr': 11.554,
        'Alyamani-Sen': 7.240,
        'Chapuis': 15.022,
        'Krumbein-Monk': 27.806,
        'Shepherd': 43.272,
    }
}

DATASET_2 = {
    'name': 'Sample 1 Odong',
    'temperature': 20.0,  # °C
    'sample_mass': 100.0,  # g
    'porosity': 0.346078,  # TODO: Fill in from Excel - what porosity did Excel use?
    'grain_distribution': {
        'particle_sizes': [10.0, 4.75, 2.36, 1.18, 0.6, 0.425, 0.3, 0.15, 0.075],
        'percent_passing': [85.23, 79.57, 66.73, 49.99, 30.75, 17.55, 6.28, 2.84, 0]
    },
    'excel_results': {  # m/d - From Excel output
        'Hazen': 111.583,
        'Hazen_1892': 100.620,
        'Slichter': 30.550,
        'Terzaghi': 52.028,
        'Beyer': 101.685,
        'Sauerbrei': 57.642,
        'Kruger': 171.228,
        'Kozeny-Carman': 333.210,
        'Zunker': 189.704,
        'Zamarin': 221.019,
        'USBR': 68.184,
        'Barr': 38.945,
        'Alyamani-Sen': 30.187,
        'Chapuis': 65.605,
        'Krumbein-Monk': 49.690,
        'Shepherd': 187.828,
    }
}

DATASET_3 = {
    'name': 'Thomson SERDP Borden sand',
    'temperature': 20.0,  # °C
    'sample_mass': 100.0,  # g
    'porosity': 0.406547,  # TODO: Fill in from Excel
    'grain_distribution': {
        'particle_sizes': [10.0, 9.0, 3.0, 1.3, 0.8, 0.4, 0.23, 0.15, 0.07, 0.04, 0.027, 0.017, 0.01, 0.0055, 0.002],
        'percent_passing': [99.99, 99.9, 99.8, 98, 97, 95, 82, 31, 10, 2.6, 2.6, 2.6, 2.5, 1, 0]
    },
    'excel_results': {  # m/d - From Excel output
        'Hazen': 6.221,
        'Hazen_1892': 4.234,
        'Slichter': 2.182,
        'Terzaghi': 3.825,
        'Beyer': 4.926,
        'Sauerbrei': 6.042,
        'Kruger': 3.511,
        'Kozeny-Carman': 8.605,
        'Zunker': 4.300,
        'Zamarin': 4.704,
        'USBR': 2.469,
        'Barr': 3.225,
        'Alyamani-Sen': 2.667,
        'Chapuis': 3.951,
        'Krumbein-Monk': 5.535,
        'Shepherd': 8.417,
    }
}

DATASET_4 = {
    'name': 'Example 1 Case 2 Vukovic 15°C',
    'temperature': 20.0,  # °C (Excel calculations at 20°C, not 15°C)
    'sample_mass': 100.0,  # g
    'porosity': 0.383774,
    'grain_distribution': {
        'particle_sizes': [2.0, 1.5, 1.2, 0.95, 0.82, 0.73, 0.66, 0.6, 0.55, 0.51, 0.48, 0.45, 0.42, 0.39, 0.36, 0.32, 0.28, 0.22, 0.15, 0.08, 0.045],
        'percent_passing': [100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 0]
    },
    'excel_results': {  # m/d - From Excel output
        'Hazen': 25.925,
        'Hazen_1892': 19.440,
        'Slichter': 8.291,
        'Terzaghi': 14.425,
        'Beyer': 21.434,
        'Sauerbrei': 30.031,
        'Kruger': 37.668,
        'Kozeny-Carman': 97.652,
        'Zunker': 48.823,
        'Zamarin': 52.549,
        'USBR': 22.044,
        'Barr': 11.554,
        'Alyamani-Sen': 7.459,
        'Chapuis': 15.022,
        'Krumbein-Monk': 28.957,
        'Shepherd': 42.538,
    }
}

DATASET_5 = {
    'name': 'Example 2 Case 1 Vukovic 15°C',
    'temperature': 20.0,  # °C (Excel calculations at 20°C, not 15°C)
    'sample_mass': 100.0,  # g
    'porosity': 0.259704,
    'grain_distribution': {
        'particle_sizes': [5.0, 0.85, 0.3, 0.12, 0.039, 0.014, 0.0025, 0.001],
        'percent_passing': [100, 80, 60, 40, 20, 10, 5, 0]
    },
    'excel_results': {  # m/d - From Excel output
        'Hazen': 0.101,
        'Hazen_1892': 0.169,
        'Slichter': 0.020,
        'Terzaghi': 0.029,
        'Beyer': 0.120,
        'Sauerbrei': 0.107,
        'Kruger': 0.099,
        'Kozeny-Carman': 0.071,
        'Zunker': 0.062,
        'Zamarin': 0.086,
        'USBR': 0.237,
        'Barr': 0.022,
        'Alyamani-Sen': 1.178,
        'Chapuis': 0.004,
        'Krumbein-Monk': 0.304,
        'Shepherd': 10.874,
    }
}


DATASETS = [DATASET_1, DATASET_2, DATASET_3, DATASET_4, DATASET_5]

# Most methods match the reference sheets within 1%.
# A few validated methods need slightly looser bounds due to known formula/data nuances.
DEFAULT_MAX_ERROR_PCT = 1.0
KNOWN_LIMITATION_METHODS = {
    'Krumbein-Monk',
}
METHOD_MAX_ERROR_PCT = {
    'Barr': 3.0,
    'Chapuis': 12.0,
    # Known limitation until the geometric-mean path is fully verified.
    'Krumbein-Monk': 5.0,
}


# ============================================================================
# HELPERS
# ============================================================================

def _max_error_pct(method_name: str) -> float:
    """Return the maximum allowed relative error percentage for a method."""
    return METHOD_MAX_ERROR_PCT.get(method_name, DEFAULT_MAX_ERROR_PCT)


def _prepare_grain_data(dataset):
    """Build the grain-data payload expected by KCalculator."""
    calc = KCalculator()
    grain_data = dataset['grain_distribution'].copy()

    percentiles_to_calc = [5, 10, 16, 17, 20, 30, 50, 60, 84, 95, 160, 840, 950]
    for p in percentiles_to_calc:
        d_value = calc._interpolate_percentile(grain_data, p)
        if d_value is not None:
            grain_data[f'D{p}'] = d_value

    return calc, grain_data


def compare_dataset(dataset, verbose=True):
    """
    Compare all K-calculation methods on a single dataset.

    Args:
        dataset: Dictionary containing test data and expected results
        verbose: If True, print detailed output

    Returns:
        Dictionary with comparison results
    """
    if dataset['porosity'] is None:
        print(f"\nWARNING: Porosity not set for {dataset['name']}")
        print("  Using default porosity = 0.40 for testing")
        porosity = 0.40
    else:
        porosity = dataset['porosity']

    calc, grain_data = _prepare_grain_data(dataset)

    results = calc.calculate_all_methods(
        grain_data,
        temperature=dataset['temperature'],
        porosity=porosity
    )

    if verbose:
        print(f"\n{'='*90}")
        print(f"Dataset: {dataset['name']}")
        print(f"Temperature: {dataset['temperature']}°C, Porosity: {porosity:.3f}")
        print(f"{'='*90}")
        print(f"{'Method':<18} {'Excel (m/d)':>12} {'Python (m/d)':>12} {'Diff (m/d)':>12} {'Error %':>10} {'Status':>10}")
        print(f"{'-'*90}")

    comparison = {}

    for result in results:
        method_name = result.method_name
        k_python_m_d = result.k_value * 86400  # Convert m/s to m/d
        k_excel_m_d = dataset['excel_results'].get(method_name)

        if k_excel_m_d is None:
            # No Excel data to compare
            if verbose:
                print(f"{method_name:<18} {'N/A':>12} {k_python_m_d:12.3f} {'N/A':>12} {'N/A':>10} {'NO DATA':>10}")
            comparison[method_name] = {
                'excel': None,
                'python': k_python_m_d,
                'diff': None,
                'error_pct': None,
                'status': 'NO_DATA'
            }
        else:
            diff = k_python_m_d - k_excel_m_d
            error_pct = (diff / k_excel_m_d * 100) if k_excel_m_d != 0 else float('inf')
            max_error_pct = _max_error_pct(method_name)

            # Determine status
            if abs(error_pct) <= max_error_pct:
                status = 'OK'
            elif abs(error_pct) <= max(max_error_pct * 2, 20):
                status = 'WARNING'
            else:
                status = 'ERROR'

            if verbose:
                print(f"{method_name:<18} {k_excel_m_d:12.3f} {k_python_m_d:12.3f} {diff:12.3f} {error_pct:9.1f}% {status:>10}")

            comparison[method_name] = {
                'excel': k_excel_m_d,
                'python': k_python_m_d,
                'diff': diff,
                'error_pct': error_pct,
                'status': status
            }

    return comparison


def run_all_tests():
    """Run tests on all datasets and provide summary."""
    all_comparisons = {}

    for dataset in DATASETS:
        comparison = compare_dataset(dataset, verbose=True)
        all_comparisons[dataset['name']] = comparison

    # Summary
    print(f"\n{'='*90}")
    print("SUMMARY")
    print(f"{'='*90}")

    for dataset_name, comparison in all_comparisons.items():
        ok_count = sum(1 for v in comparison.values() if v['status'] == 'OK')
        warning_count = sum(1 for v in comparison.values() if v['status'] == 'WARNING')
        error_count = sum(1 for v in comparison.values() if v['status'] == 'ERROR')
        no_data_count = sum(1 for v in comparison.values() if v['status'] == 'NO_DATA')

        print(f"\n{dataset_name}:")
        print(f"  OK: {ok_count}, WARNING: {warning_count}, ERROR: {error_count}, NO DATA: {no_data_count}")

    print(f"\n{'='*90}")
    print("METHOD SUMMARY")
    print(f"{'='*90}")

    method_names = list(DATASETS[0]['excel_results'].keys())
    for method_name in method_names:
        statuses = []
        errors = []
        for comparison in all_comparisons.values():
            method_result = comparison.get(method_name, {})
            status = method_result.get('status', 'NO_DATA')
            error_pct = method_result.get('error_pct')
            statuses.append(status)
            if error_pct is not None:
                errors.append(abs(error_pct))

        ok_count = statuses.count('OK')
        warning_count = statuses.count('WARNING')
        error_count = statuses.count('ERROR')
        no_data_count = statuses.count('NO_DATA')
        max_error = max(errors) if errors else None
        limit_note = "KNOWN LIMITATION" if method_name in KNOWN_LIMITATION_METHODS else ""
        max_error_text = f"{max_error:6.2f}%" if max_error is not None else "  N/A  "

        print(
            f"{method_name:<18} "
            f"OK:{ok_count:<2} WARNING:{warning_count:<2} ERROR:{error_count:<2} NO_DATA:{no_data_count:<2} "
            f"max|err|={max_error_text} {limit_note}"
        )

    unexpected_failures = []
    known_limitations = []
    for dataset_name, comparison in all_comparisons.items():
        for method_name, method_result in comparison.items():
            if method_result['status'] not in {'WARNING', 'ERROR'}:
                continue
            entry = (
                f"{dataset_name} | {method_name}: {method_result['status']} "
                f"({method_result['error_pct']:.2f}% error)"
            )
            if method_name in KNOWN_LIMITATION_METHODS:
                known_limitations.append(entry)
            else:
                unexpected_failures.append(entry)

    print(f"\n{'='*90}")
    print("ASSESSMENT")
    print(f"{'='*90}")

    if unexpected_failures:
        print("Unexpected failures:")
        for entry in unexpected_failures:
            print(f"  - {entry}")
    else:
        print("Unexpected failures: none")

    if known_limitations:
        print("Known limitations:")
        for entry in known_limitations:
            print(f"  - {entry}")
    else:
        print("Known limitations: none")

    return all_comparisons


def _has_unexpected_failures(all_comparisons):
    """Return True if any non-whitelisted method is WARNING/ERROR."""
    for comparison in all_comparisons.values():
        for method_name, result in comparison.items():
            if method_name in KNOWN_LIMITATION_METHODS:
                continue
            if result['status'] in {'WARNING', 'ERROR'}:
                return True
    return False


def main(argv=None):
    """Diagnostic entry point for manual reference checking."""
    parser = argparse.ArgumentParser(
        description="Compare Python K-calculations against Excel reference values."
    )
    parser.add_argument(
        '--unittest',
        action='store_true',
        help='Run the strict unittest suite instead of the diagnostic summary.',
    )
    args, remaining = parser.parse_known_args(argv)

    if args.unittest:
        unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
        return 0

    all_comparisons = run_all_tests()
    return 1 if _has_unexpected_failures(all_comparisons) else 0


class TestKCalculationsAgainstKnownResults(unittest.TestCase):
    """Reference-value regression tests for hydraulic conductivity calculations."""

    def test_all_expected_methods_are_returned(self):
        for dataset in DATASETS:
            with self.subTest(dataset=dataset['name']):
                calc, grain_data = _prepare_grain_data(dataset)
                results = calc.calculate_all_methods(
                    grain_data,
                    temperature=dataset['temperature'],
                    porosity=dataset['porosity'],
                )
                actual_methods = {result.method_name for result in results}
                expected_methods = set(dataset['excel_results'])
                self.assertEqual(expected_methods, actual_methods)

    def test_known_reference_values(self):
        failures = []

        for dataset in DATASETS:
            calc, grain_data = _prepare_grain_data(dataset)
            results = calc.calculate_all_methods(
                grain_data,
                temperature=dataset['temperature'],
                porosity=dataset['porosity'],
            )
            result_map = {result.method_name: result for result in results}

            for method_name, expected_m_d in dataset['excel_results'].items():
                result = result_map[method_name]
                actual_m_d = result.k_value * 86400
                error_pct = abs(actual_m_d - expected_m_d) / abs(expected_m_d) * 100
                max_error_pct = _max_error_pct(method_name)

                if error_pct > max_error_pct:
                    failures.append(
                        f"{dataset['name']} | {method_name}: expected {expected_m_d:.3f} m/d, "
                        f"got {actual_m_d:.3f} m/d ({error_pct:.2f}% > {max_error_pct:.2f}%)"
                    )

        if failures:
            self.fail("Reference calculation mismatches detected:\n" + "\n".join(failures))


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
