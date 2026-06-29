import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from grain_classification import (
    ISO14688,
    USCS,
    GrainFractions,
    make_custom_scheme,
    compute_fractions,
    compute_detailed_fractions,
    scheme_detail_bands,
    sedimentology_descriptor,
    classify,
)


class TestDetailedFractions(unittest.TestCase):
    # A fine-to-medium sand curve (coarse -> fine sieve data).
    sizes = [2.0, 0.63, 0.2, 0.063, 0.002]
    passing = [100.0, 96.0, 40.0, 4.0, 0.4]

    def test_iso_returns_eleven_bands(self):
        bands = scheme_detail_bands(ISO14688)
        self.assertEqual(len(bands), 11)
        labels = [b[2] for b in bands]
        self.assertIn("Fine sand", labels)
        self.assertIn("Medium sand", labels)
        self.assertIn("Coarse gravel", labels)

    def test_non_iso_falls_back_to_five_coarse_bands(self):
        for scheme in (USCS, make_custom_scheme("Custom", 0.002, 0.06, 1.0, 50.0)):
            bands = scheme_detail_bands(scheme)
            self.assertEqual([b[2] for b in bands],
                             ["Clay", "Silt", "Sand", "Gravel", "Cobble"])

    def test_detailed_sums_to_one_hundred(self):
        detailed = compute_detailed_fractions(self.sizes, self.passing, ISO14688)
        total = sum(d.pct for d in detailed)
        self.assertAlmostEqual(total, 100.0, delta=0.2)

    def test_detailed_aligns_with_coarse_fractions(self):
        coarse = compute_fractions(self.sizes, self.passing, ISO14688)
        detailed = compute_detailed_fractions(self.sizes, self.passing, ISO14688)
        by_label = {d.label: d.pct for d in detailed}

        sand = by_label["Fine sand"] + by_label["Medium sand"] + by_label["Coarse sand"]
        silt = (by_label["Fine silt"] + by_label["Medium silt"]
                + by_label["Coarse silt"])
        self.assertAlmostEqual(sand, coarse.sand_pct, delta=0.2)
        self.assertAlmostEqual(silt, coarse.silt_pct, delta=0.2)

    def test_dominant_detail_class_on_result(self):
        result = classify(self.sizes, self.passing, cu=None, cc=None, scheme=ISO14688)
        # Fine sand band (0.063-0.2) carries ~36%, but medium sand (0.2-0.63)
        # carries ~56% here -> dominant should be a sand sub-class.
        self.assertIn("sand", result.detailed_class.lower())
        self.assertEqual(len(result.detailed_fractions), 11)

    def test_empty_data_is_safe(self):
        detailed = compute_detailed_fractions([], [], ISO14688)
        self.assertEqual(len(detailed), 11)
        self.assertTrue(all(d.pct == 0.0 for d in detailed))

        result = classify([], [], cu=None, cc=None, scheme=ISO14688)
        self.assertEqual(result.detailed_class, "—")
        self.assertEqual(result.detailed_fractions, ())


class TestSedimentologyDescriptor(unittest.TestCase):
    def test_clean_uniform_sand(self):
        fr = GrainFractions(clay_pct=0.0, silt_pct=2.0, sand_pct=96.0, gravel_pct=2.0)
        text = sedimentology_descriptor(fr, d50_mm=0.18, cu=2.79)
        self.assertEqual(text, "Moderately well sorted sand low in fines")

    def test_modifiers_listed_finest_first_and_fines_flag(self):
        fr = GrainFractions(clay_pct=1.0, silt_pct=12.0, sand_pct=60.0, gravel_pct=27.0)
        text = sedimentology_descriptor(fr, d50_mm=0.3, cu=8.0)
        # sand primary; silt (12%) and gravel (27%) are >=10% -> finest first.
        self.assertEqual(text, "Poorly sorted silty gravelly sand with fines")

    def test_uniform_threshold(self):
        fr = GrainFractions(sand_pct=100.0)
        self.assertTrue(
            sedimentology_descriptor(fr, d50_mm=0.2, cu=1.5).startswith("Uniform"))

    def test_returns_empty_without_d50(self):
        fr = GrainFractions(sand_pct=100.0)
        self.assertEqual(sedimentology_descriptor(fr, d50_mm=None, cu=3.0), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
