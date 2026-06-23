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


if __name__ == "__main__":
    unittest.main(verbosity=2)
