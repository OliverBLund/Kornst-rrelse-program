"""Regression tests for the cumulative percent-passing input contract."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "Program")

from data_loader import DataLoader, GrainSizeData, ValidationSeverity
from excel_import_detection import detect_processed_curve_candidate
from load_process_worker import _load_mapped_source, run_batch_import


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "test_data" / "validation_examples"


class _ListQueue:
    def __init__(self):
        self.events = []

    def put(self, event):
        self.events.append(event)


class TestPercentPassingContract(unittest.TestCase):
    def test_valid_converted_example_loads_as_cumulative_passing(self):
        dataset = DataLoader().load_file(
            str(EXAMPLES / "02_valid_cumulative_passing.csv")
        )

        self.assertFalse(dataset.has_errors())
        self.assertEqual(dataset.percent_passing, [99.0, 95.0, 82.0, 58.0, 32.0, 12.0, 2.0])

    def test_explicit_retained_example_is_not_converted_automatically(self):
        with self.assertRaisesRegex(
            ValueError,
            "requires cumulative percent passing",
        ):
            DataLoader().load_file(
                str(EXAMPLES / "01_invalid_cumulative_retained.csv")
            )

    def test_strongly_reversed_declared_passing_curve_is_an_error(self):
        dataset = GrainSizeData(
            sample_name="Reversed",
            temperature=20.0,
            porosity=0.35,
            particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
            percent_passing=[1.0, 5.0, 18.0, 42.0, 68.0, 88.0, 98.0],
        )

        errors = [
            message
            for message in dataset.validation_messages
            if message.severity == ValidationSeverity.ERROR
        ]
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            errors[0].title,
            "Values do not satisfy cumulative percent passing",
        )
        self.assertIn("6 of 6 transitions", errors[0].message)
        self.assertNotIn("may be", errors[0].message.lower())

    def test_one_local_irregularity_does_not_block_import(self):
        dataset = GrainSizeData(
            sample_name="Minor irregularity",
            temperature=20.0,
            porosity=0.35,
            particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
            percent_passing=[99.0, 95.0, 82.0, 84.0, 32.0, 12.0, 2.0],
        )

        self.assertFalse(dataset.has_errors())
        self.assertTrue(
            any(
                message.title == "Minor data irregularities detected"
                for message in dataset.validation_messages
            )
        )

    def test_excel_detection_rejects_explicit_retained_column(self):
        rows = [
            ["Particle Size (mm)", "Cumulative Percent Retained (%)"],
            ["4.75", "1"],
            ["2.00", "5"],
            ["1.00", "18"],
            ["0.50", "42"],
        ]

        self.assertIsNone(detect_processed_curve_candidate(rows))

    def test_excel_detection_rejects_reversed_generic_curve(self):
        rows = [
            ["on curve", "percentages"],
            ["4.75", "1"],
            ["2.00", "5"],
            ["1.00", "18"],
            ["0.50", "42"],
        ]

        self.assertIsNone(detect_processed_curve_candidate(rows))

    def test_saved_retained_mapping_is_rejected_instead_of_converted(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, "old_mapping.csv")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("size,retained\n")
                handle.write("4.75,1\n2.0,5\n1.0,18\n")

            source = {
                "file_key": path,
                "file_path": path,
                "mapping_state": {
                    "header_row": 0,
                    "column_indices": {
                        "size": 1,
                        "passing": 0,
                        "retained": 2,
                    },
                },
            }

            with self.assertRaisesRegex(ValueError, "not imported automatically"):
                _load_mapped_source(source)

    def test_batch_import_surfaces_retained_contract_message_for_review(self):
        path = str(EXAMPLES / "01_invalid_cumulative_retained.csv")
        queue = _ListQueue()

        run_batch_import([path], queue)

        failed = [event for event in queue.events if event[0] == "item_failed"]
        loaded = [event for event in queue.events if event[0] == "item_loaded"]
        self.assertEqual(loaded, [])
        self.assertEqual(len(failed), 1)
        self.assertIn("requires cumulative percent passing", failed[0][2])

    def test_batch_import_reports_reversed_declared_passing_validation(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, "reversed_passing.csv")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("Particle Size (mm),Cumulative Percent Passing (%)\n")
                handle.write("4.75,1\n2.0,5\n1.0,18\n0.5,42\n0.25,68\n")

            queue = _ListQueue()
            run_batch_import([path], queue)

        validation_failures = [
            event for event in queue.events
            if event[0] == "item_validation_failed"
        ]
        self.assertEqual(len(validation_failures), 1)
        self.assertIn(
            "Values do not satisfy cumulative percent passing",
            validation_failures[0][4],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
