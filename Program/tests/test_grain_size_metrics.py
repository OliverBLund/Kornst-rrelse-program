import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from data_loader import GrainSizeData


class TestGrainSizeMetrics(unittest.TestCase):
    def make_dataset(self, sizes, passing):
        return GrainSizeData(
            sample_name="Sample",
            temperature=20.0,
            porosity=0.35,
            particle_sizes=list(sizes),
            percent_passing=list(passing),
        )

    def test_arithmetic_mean_grain_size_uses_sieve_intervals(self):
        dataset = self.make_dataset([2.0, 1.0, 0.5], [100.0, 50.0, 0.0])

        # 50% retained in 2.0-1.0 mm interval and 50% in 1.0-0.5 mm interval.
        expected = (50.0 * 1.5 + 50.0 * 0.75) / 100.0

        self.assertAlmostEqual(dataset.get_arithmetic_mean_grain_size(), expected)

    def test_arithmetic_mean_grain_size_normalizes_known_bounded_fraction(self):
        dataset = self.make_dataset([4.0, 2.0, 1.0], [80.0, 30.0, 10.0])

        # Open tails above the largest sieve and below the smallest sieve are not
        # assigned a representative diameter.
        expected = (50.0 * 3.0 + 20.0 * 1.5) / 70.0

        self.assertAlmostEqual(dataset.get_arithmetic_mean_grain_size(), expected)

    def test_arithmetic_mean_grain_size_returns_none_without_retained_intervals(self):
        dataset = self.make_dataset([4.0, 2.0, 1.0], [10.0, 20.0, 30.0])

        self.assertIsNone(dataset.get_arithmetic_mean_grain_size())


if __name__ == "__main__":
    unittest.main(verbosity=2)
