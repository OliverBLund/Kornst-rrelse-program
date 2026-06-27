"""Tests for the persisted global report/export plot style store."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

import gui.report_plot_style as rps

APP = QApplication.instance() or QApplication([])


class TestReportPlotStyle(unittest.TestCase):
    def setUp(self):
        # Isolate from any real persisted settings.
        QSettings("GrainSizeAnalysis", "ReportPlotStyle").clear()
        rps._reset_cache_for_tests()

    def tearDown(self):
        QSettings("GrainSizeAnalysis", "ReportPlotStyle").clear()
        rps._reset_cache_for_tests()

    def test_default_resolves_to_first_preset(self):
        style = rps.resolve_report_style()
        self.assertEqual(style.name, "Professional")

    def test_preset_persists_and_resolves(self):
        rps.set_report_style_preset("Presentation")
        rps._reset_cache_for_tests()
        self.assertEqual(rps.get_report_style_preset(), "Presentation")
        self.assertEqual(rps.resolve_report_style().name, "Presentation")

    def test_invalid_preset_falls_back(self):
        rps.set_report_style_preset("Nonexistent")
        self.assertEqual(rps.get_report_style_preset(), "Professional")

    def test_overrides_round_trip_and_apply(self):
        rps.set_report_style_overrides({
            "title_fontsize": 22,
            "legend_loc": "upper left",
            "legend_bbox_to_anchor": [1.02, 1.0],  # JSON list → tuple on resolve
            "legend_ncol": 2,
        })
        rps._reset_cache_for_tests()
        style = rps.resolve_report_style()
        self.assertEqual(style.title_fontsize, 22)
        self.assertEqual(style.legend_loc, "upper left")
        self.assertEqual(style.legend_bbox_to_anchor, (1.02, 1.0))
        self.assertEqual(style.legend_ncol, 2)

    def test_unknown_override_fields_are_dropped(self):
        rps.set_report_style_overrides({"not_a_field": 5, "title_fontsize": 18})
        stored = rps.get_report_style_overrides()
        self.assertNotIn("not_a_field", stored)
        self.assertEqual(stored["title_fontsize"], 18)

    def test_clear_overrides_reverts_to_preset(self):
        rps.set_report_style_preset("Professional")
        base = rps.get_style("Professional").title_fontsize
        rps.set_report_style_overrides({"title_fontsize": base + 7})
        rps.clear_report_style_overrides()
        rps._reset_cache_for_tests()
        self.assertEqual(rps.resolve_report_style().title_fontsize, base)

    def test_palette_defaults_to_categorical(self):
        self.assertEqual(rps.get_report_palette(), "Categorical")

    def test_palette_persists_and_resolves_colors(self):
        from gui.plot_constants import DATASET_COLORS

        rps.set_report_palette("Viridis")
        rps._reset_cache_for_tests()
        self.assertEqual(rps.get_report_palette(), "Viridis")
        colors = rps.resolve_report_palette_colors(3)
        self.assertEqual(len(colors), 3)
        # A real colormap differs from the categorical default palette.
        self.assertNotEqual(colors, DATASET_COLORS[:3])

    def test_categorical_palette_matches_dataset_colors(self):
        from gui.plot_constants import DATASET_COLORS

        rps.set_report_palette("Categorical")
        self.assertEqual(rps.resolve_report_palette_colors(4), DATASET_COLORS[:4])

    def test_invalid_palette_falls_back_to_categorical(self):
        rps.set_report_palette("Rainbow Unicorn")
        self.assertEqual(rps.get_report_palette(), "Categorical")


class TestPaletteColors(unittest.TestCase):
    def test_categorical_cycles_dataset_colors(self):
        from gui.plot_constants import DATASET_COLORS, palette_colors

        n = len(DATASET_COLORS) + 2
        colors = palette_colors("Categorical", n)
        self.assertEqual(len(colors), n)
        self.assertEqual(colors[0], DATASET_COLORS[0])
        self.assertEqual(colors[len(DATASET_COLORS)], DATASET_COLORS[0])  # wraps

    def test_colormap_samples_distinct_hex_colors(self):
        from gui.plot_constants import palette_colors

        colors = palette_colors("Plasma", 5)
        self.assertEqual(len(colors), 5)
        self.assertEqual(len(set(colors)), 5)
        self.assertTrue(all(c.startswith("#") for c in colors))

    def test_zero_and_negative_counts_are_empty(self):
        from gui.plot_constants import palette_colors

        self.assertEqual(palette_colors("Viridis", 0), [])
        self.assertEqual(palette_colors("Viridis", -3), [])

    def test_grayscale_is_offered_and_distinct(self):
        from gui.plot_constants import PALETTE_NAMES, palette_colors

        self.assertIn("Grayscale", PALETTE_NAMES)
        grays = palette_colors("Grayscale", 7)
        self.assertEqual(len(grays), 7)
        self.assertEqual(len(set(grays)), 7)  # all distinct shades
        # Every shade is a true gray (R==G==B) and none is near-white.
        for hex_color in grays:
            r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
            self.assertEqual((r, g), (g, b))
            self.assertLess(r, 200)

    def test_colormap_samples_span_full_range_for_many_colors(self):
        # Regression: seven colours must spread across the whole colormap, not
        # cluster at one end (the bug behind '7 groups all look blue/purple').
        from gui.plot_constants import palette_colors

        first, last = palette_colors("Viridis", 7)[0], palette_colors("Viridis", 7)[-1]
        self.assertNotEqual(first, last)
        # Viridis runs dark-purple → yellow; the endpoints must be far apart.
        fr = int(first[1:3], 16)
        lr, lg = int(last[1:3], 16), int(last[3:5], 16)
        self.assertLess(fr, 100)         # dark purple start (low red)
        self.assertGreater(lr + lg, 300)  # yellow end (high red+green)


if __name__ == "__main__":
    unittest.main(verbosity=2)
