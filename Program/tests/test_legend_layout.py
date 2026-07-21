"""Focused tests for shared automatic and explicit legend columns."""

import dataclasses
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from gui.plot_renderers import legend_column_count
from gui.plot_styles import PROFESSIONAL_STYLE


class TestLegendColumnCount(unittest.TestCase):
    def test_auto_wraps_short_labels_across_four_columns_below_plot(self):
        style = dataclasses.replace(
            PROFESSIONAL_STYLE,
            legend_ncol=0,
            legend_loc="upper center",
            legend_bbox_to_anchor=(0.5, -0.22),
        )

        self.assertEqual(
            legend_column_count(
                style,
                labels=[f"Sample {index}" for index in range(20)],
                available_width_points=620,
            ),
            4,
        )

    def test_auto_reduces_columns_for_long_labels(self):
        style = dataclasses.replace(
            PROFESSIONAL_STYLE,
            legend_ncol=0,
            legend_loc="upper center",
            legend_bbox_to_anchor=(0.5, -0.22),
        )

        columns = legend_column_count(
            style,
            labels=[
                f"Laboratory campaign sample with long identifier {index}"
                for index in range(8)
            ],
            available_width_points=620,
        )

        self.assertLess(columns, 4)
        self.assertGreaterEqual(columns, 1)

    def test_auto_side_legend_uses_one_column(self):
        style = dataclasses.replace(
            PROFESSIONAL_STYLE,
            legend_ncol=0,
            legend_loc="upper left",
            legend_bbox_to_anchor=(1.02, 1.0),
        )

        self.assertEqual(
            legend_column_count(
                style,
                labels=[f"Sample {index}" for index in range(20)],
                available_width_points=620,
            ),
            1,
        )

    def test_auto_inside_legend_uses_at_most_two_columns(self):
        style = dataclasses.replace(
            PROFESSIONAL_STYLE,
            legend_ncol=0,
            legend_loc="upper left",
            legend_bbox_to_anchor=None,
        )

        columns = legend_column_count(
            style,
            labels=[f"Sample {index}" for index in range(20)],
            available_width_points=620,
        )

        self.assertLessEqual(columns, 2)

    def test_explicit_column_count_is_predictable_and_clamped(self):
        style = dataclasses.replace(PROFESSIONAL_STYLE, legend_ncol=3)

        self.assertEqual(legend_column_count(style, label_count=8), 3)
        self.assertEqual(legend_column_count(style, label_count=2), 2)


if __name__ == "__main__":
    unittest.main()
