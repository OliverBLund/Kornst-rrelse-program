import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from calculation_internals import compute_calculation_internals, CalculationInternals


class TestCalculationInternals(unittest.TestCase):
    sizes = [2.0, 0.63, 0.2, 0.063, 0.002]
    passing = [100.0, 96.0, 40.0, 4.0, 0.4]

    def test_returns_four_populated_groups(self):
        internals = compute_calculation_internals(self.sizes, self.passing, 20.0, 0.40)
        self.assertIsInstance(internals, CalculationInternals)
        self.assertEqual(len(internals.groups()), 4)
        for group in internals.groups():
            self.assertTrue(group.title)
            self.assertTrue(group.rows)

    def test_physical_constants_present_and_formatted(self):
        internals = compute_calculation_internals(self.sizes, self.passing, 20.0, 0.40)
        labels = {label for label, _ in internals.physical_constants.rows}
        self.assertIn("ρg/μ", labels)
        self.assertIn("τ (Sauerbrei)", labels)
        self.assertIn("g (gravity)", labels)

    def test_porosity_functions_reflect_n(self):
        internals = compute_calculation_internals(self.sizes, self.passing, 20.0, 0.40)
        rows = dict(internals.porosity_functions.rows)
        # void ratio e = n/(1-n) = 0.4/0.6 = 0.667
        self.assertEqual(rows["void ratio e = n/(1−n)"], "0.667")

    def test_phi_sorting_present(self):
        internals = compute_calculation_internals(self.sizes, self.passing, 20.0, 0.40)
        labels = {label for label, _ in internals.phi_folk_ward.rows}
        self.assertIn("σφ (sorting)", labels)

    def test_missing_porosity_is_safe(self):
        internals = compute_calculation_internals(self.sizes, self.passing, 20.0, None)
        rows = dict(internals.porosity_functions.rows)
        self.assertIn("Porosity functions", rows)

    def test_empty_data_is_safe(self):
        internals = compute_calculation_internals([], [], 20.0, 0.40)
        self.assertEqual(len(internals.groups()), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
