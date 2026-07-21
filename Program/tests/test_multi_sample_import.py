"""Regression tests for conservative multi-sample source detection."""

import csv
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, "Program")

from excel_import_detection import (
    detect_multi_sample_candidates,
    extract_candidate_curve,
)
from import_resolver import resolve_excel_import
from data_loader import DataLoader
from load_process_worker import _load_source_without_mapping
from import_preview import load_preview_rows


CURVE_ROWS = [
    [0.063, 5.0, 8.0],
    [0.125, 18.0, 24.0],
    [0.25, 42.0, 50.0],
    [0.5, 70.0, 76.0],
    [1.0, 92.0, 95.0],
    [2.0, 100.0, 100.0],
]
SHARED_SIZE_FIXTURE = (
    Path(__file__).resolve().parents[2] / "test_data" / "multi_sample_shared_size.xlsx"
)


class TestMultiSampleImportDetection(unittest.TestCase):
    def test_maintained_shared_size_workbook_resolves_three_named_curves(self):
        rows, sheets, resolved_sheet = load_preview_rows(
            str(SHARED_SIZE_FIXTURE),
            sheet_name="Grain size results",
        )

        candidates = detect_multi_sample_candidates(
            rows,
            sheet_name=resolved_sheet,
        )

        self.assertEqual(sheets, ["Grain size results"])
        self.assertEqual(resolved_sheet, "Grain size results")
        self.assertEqual(
            [candidate.sample_name for candidate in candidates],
            ["BH-01", "BH-02", "BH-03"],
        )
        self.assertEqual(
            [candidate.source_label for candidate in candidates],
            ["Columns A:B", "Columns A:C", "Columns A:D"],
        )
        for candidate in candidates:
            sizes, passing = extract_candidate_curve(rows, candidate)
            self.assertEqual(len(sizes), 7)
            self.assertEqual(len(passing), 7)
            self.assertTrue(all(size > 0 for size in sizes))
            self.assertTrue(all(0 <= value <= 100 for value in passing))

    def test_single_curve_keeps_legacy_path(self):
        rows = [["Particle Size", "Percent Passing"]]
        rows.extend([row[:2] for row in CURVE_ROWS])

        self.assertEqual(detect_multi_sample_candidates(rows), ())
        resolution = resolve_excel_import(rows)
        self.assertEqual(resolution.candidates, ())
        self.assertNotIn("sample candidates", resolution.message)

    def test_detects_shared_size_with_named_passing_columns(self):
        rows = [
            ["", "Sample A", "Sample B"],
            ["Particle Size (mm)", "Percent Passing", "Percent Passing"],
            *CURVE_ROWS,
        ]

        candidates = detect_multi_sample_candidates(rows, sheet_name="Data")

        self.assertEqual([item.sample_name for item in candidates], ["Sample A", "Sample B"])
        self.assertEqual([item.source_label for item in candidates], ["Columns A:B", "Columns A:C"])
        sizes, passing = extract_candidate_curve(rows, candidates[1])
        self.assertEqual(sizes[:2], [0.063, 0.125])
        self.assertEqual(passing[:2], [8.0, 24.0])

        normal_resolution = resolve_excel_import(rows, sheet_name="Data")
        self.assertEqual(normal_resolution.candidates, ())

        resolution = resolve_excel_import(
            rows,
            sheet_name="Data",
            allow_multi_sample=True,
        )
        self.assertTrue(resolution.requires_mapping)
        self.assertEqual(len(resolution.candidates), 2)

    def test_uses_sample_prefix_from_combined_passing_header(self):
        rows = [[
            "Particle Size (mm)",
            "BH-01 Percent Passing (%)",
            "BH-02 Percent Passing (%)",
        ], *CURVE_ROWS]

        candidates = detect_multi_sample_candidates(rows)

        self.assertEqual(
            [item.sample_name for item in candidates],
            ["BH-01", "BH-02"],
        )

    def test_detects_repeated_horizontal_pairs(self):
        rows = [
            ["Sample A", "", "Sample B", ""],
            ["Size mm", "Passing %", "Size mm", "Passing %"],
        ]
        for size, passing_a, passing_b in CURVE_ROWS:
            rows.append([size, passing_a, size, passing_b])

        candidates = detect_multi_sample_candidates(rows)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].source_label, "Columns A:B")
        self.assertEqual(candidates[1].source_label, "Columns C:D")

    def test_detects_long_table_by_sample_id(self):
        rows = [["Sample ID", "Particle Size", "Cumulative Percent Passing"]]
        for sample_name, passing_index in (("A", 1), ("B", 2)):
            rows.extend(
                [sample_name, size, source[passing_index]]
                for source in CURVE_ROWS
                for size in [source[0]]
            )

        candidates = detect_multi_sample_candidates(rows)

        self.assertEqual([item.sample_name for item in candidates], ["A", "B"])
        self.assertEqual(len(candidates[0].size_cells), len(CURVE_ROWS))

    def test_does_not_treat_incremental_volume_columns_as_passing(self):
        rows = [
            ["", "Sample A", "Sample B"],
            ["Size (um)", "% Volume In", "% Volume In"],
            *CURVE_ROWS,
        ]

        self.assertEqual(detect_multi_sample_candidates(rows), ())

    def test_normal_csv_path_does_not_invoke_experimental_detection(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, "multi.csv")
            rows = [
                ["Sample ID", "Particle Size", "Percent Passing"],
                *[
                    [sample_name, source[0], source[passing_index]]
                    for sample_name, passing_index in (("A", 1), ("B", 2))
                    for source in CURVE_ROWS
                ],
            ]
            with open(path, "w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerows(rows)

            dataset = _load_source_without_mapping(
                path,
                loader=DataLoader(),
            )

            self.assertIsNotNone(dataset)
            self.assertGreaterEqual(len(dataset.particle_sizes), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
