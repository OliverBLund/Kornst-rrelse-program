"""
Regression tests for background dataset preparation.
"""

import sys
import tempfile
import unittest
import os

import pandas as pd

sys.path.insert(0, "Program")

from data_loader import GrainSizeData
from load_process_worker import (
    _friendly_load_error,
    _load_mapped_source,
    prepare_dataset_for_ui,
    run_batch_import,
    run_external_load,
)


def build_dataset(name: str = "Sample A") -> GrainSizeData:
    return GrainSizeData(
        sample_name=name,
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
        percent_passing=[100.0, 95.0, 82.0, 61.0, 38.0, 14.0, 4.0],
    )


class _ListQueue:
    def __init__(self):
        self.events = []

    def put(self, event):
        self.events.append(event)


def write_nbal_style_workbook(path: str) -> None:
    rows = [["" for _ in range(7)] for _ in range(53)]
    rows[0][0] = "Particle-size analysis"
    rows[6] = ["Mash size", "sieve+fraction", "sieve", "weight in", "mass", "", "Cumulative mass"]
    rows[7] = ["d mmm", "(g)", "(g)", "sieve (g)", "procentages", "on curve", "procentages"]
    data_rows = [
        [2, 137.23, 135.97, 1.26, 1.864181, "", 100.0],
        [1, 133.33, 118.71, 14.62, 21.630419, 2, 98.1358189081225],
        [0.6, 137.97, 117.21, 20.76, 30.714603, 1, 76.50540020713122],
        [0.355, 120.6, 106.85, 13.75, 20.343246, 0.6, 45.79079745524485],
        [0.25, 116.55, 105.56, 10.99, 16.259802, 0.355, 25.447551412930903],
        [0.18, 107.85, 104.25, 3.6, 5.326232, 0.25, 9.187749667110527],
        [0.125, 104.91, 103.56, 1.35, 1.997337, 0.18, 3.861517976031976],
        [0.09, 102.78, 102.41, 0.37, 0.547418, 0.125, 1.8641810918775248],
        [0.063, 104.18, 104.02, 0.16, 0.236721, 0.09, 1.3167628347388882],
        ["Pan", 75.31, 74.58, 0.73, 1.080041, 0.063, 1.0800414262464917],
    ]
    for row_index, row in enumerate(data_rows, start=11):
        rows[row_index] = row
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="English", header=False, index=False)


def write_processed_curve_only_workbook(path: str) -> None:
    rows = [["" for _ in range(4)] for _ in range(16)]
    rows[0][0] = "Particle-size analysis"
    rows[3] = ["", "", "on curve", "procentages"]
    rows[4] = ["", "", "d mm", "%"]
    data_rows = [
        [2.0, 100.0],
        [1.0, 70.0],
        [0.5, 30.0],
        [0.25, 8.0],
    ]
    for row_index, (size, passing) in enumerate(data_rows, start=5):
        rows[row_index][2] = size
        rows[row_index][3] = passing
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="English", header=False, index=False)


def write_raw_sieve_only_workbook(path: str) -> None:
    rows = [
        ["Mash size", "empty", "sieve+fraction"],
        [2.0, 100.0, 110.0],
        [1.0, 100.0, 125.0],
        [0.5, 100.0, 140.0],
        [0.25, 100.0, 150.0],
    ]
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="English", header=False, index=False)


class TestLoadProcessWorker(unittest.TestCase):
    def test_friendly_load_error_rephrases_missing_xlrd_for_packaged_builds(self):
        message = _friendly_load_error(
            "Import xlrd failed. Install xlrd >= 2.0.1 for xls Excel support"
        )

        self.assertEqual(
            message,
            "Legacy Excel (.xls) support is unavailable in this build. Rebuild with xlrd included or convert the file to .xlsx/.csv.",
        )

    def test_prepare_dataset_for_ui_attaches_precomputed_results(self):
        dataset = build_dataset()

        prepare_dataset_for_ui(dataset, temperature=12.5)

        self.assertEqual(dataset.temperature, 12.5)
        self.assertEqual(dataset._precomputed_k_temperature, 12.5)
        self.assertEqual(dataset._precomputed_k_porosity, dataset.current_porosity)
        self.assertTrue(dataset._precomputed_k_results)
        self.assertTrue(all(result.temperature == 12.5 for result in dataset._precomputed_k_results))

    def test_batch_import_loads_processed_csv_through_standard_loader(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "processed.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("size,passing\n")
                handle.write("2.0,100\n")
                handle.write("1.0,68\n")
                handle.write("0.5,24\n")
                handle.write("0.25,6\n")

            queue = _ListQueue()
            run_batch_import([csv_path], queue, temperature=11.0)

        loaded_events = [event for event in queue.events if event[0] == "item_loaded"]
        failed_events = [event for event in queue.events if event[0] == "item_failed"]
        log_events = [event for event in queue.events if event[0] == "log_event"]

        self.assertEqual(failed_events, [])
        self.assertEqual(len(loaded_events), 1)
        _, file_key, dataset, status, sample_name = loaded_events[0]
        self.assertEqual(file_key, csv_path)
        self.assertEqual(status, "loaded")
        self.assertEqual(sample_name, "processed")
        self.assertEqual(dataset.particle_sizes, [2.0, 1.0, 0.5, 0.25])
        self.assertEqual(dataset.percent_passing, [100.0, 68.0, 24.0, 6.0])
        self.assertTrue(dataset._precomputed_k_results)
        self.assertTrue(
            any(
                event[1]["context"]["pathway"] == "standard file loader"
                and event[1]["context"]["data_type"] == "processed_curve"
                and event[1]["level"] == "INFO"
                for event in log_events
            )
        )

    def test_external_load_loads_raw_sieve_csv_from_mapping_state(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "raw.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("size,full,empty\n")
                handle.write("2.0,110,100\n")
                handle.write("1.0,130,100\n")
                handle.write("0.5,145,100\n")
                handle.write("Pan,105,100\n")

            source = {
                "file_key": csv_path,
                "file_path": csv_path,
                "sample_name": "Raw CSV",
                "import_provenance": {
                    "source": "manual_mapping",
                    "intent": "raw_sieve",
                    "data_type": "raw_sieve",
                    "selection_method": "column",
                    "intent_matched": True,
                },
                "mapping_state": {
                    "raw_sieve_mode": True,
                    "header_row": 0,
                    "column_indices": {
                        "raw_size": 1,
                        "sieve_sample": 2,
                        "empty_sieve": 3,
                    },
                },
            }
            queue = _ListQueue()
            run_external_load([source], stage_title="Opening file", result_queue=queue)

        loaded_events = [event for event in queue.events if event[0] == "file_loaded"]
        failed_events = [event for event in queue.events if event[0] == "file_failed"]
        log_events = [event for event in queue.events if event[0] == "log_event"]

        self.assertEqual(failed_events, [])
        self.assertEqual(len(loaded_events), 1)
        _, file_key, dataset = loaded_events[0]
        self.assertEqual(file_key, csv_path)
        self.assertEqual(dataset.sample_name, "Raw CSV")
        self.assertEqual(dataset.particle_sizes, [2.0, 1.0, 0.5])
        self.assertEqual(dataset.percent_passing, [88.888889, 55.555556, 5.555556])
        self.assertTrue(dataset._source_mapping_state["raw_sieve_mode"])
        self.assertTrue(dataset._precomputed_k_results)
        self.assertTrue(
            any(
                event[1]["context"]["pathway"] == "manual mapping"
                and event[1]["context"]["data_type"] == "raw_sieve"
                and event[1]["level"] == "INFO"
                for event in log_events
            )
        )

    def test_mapped_cell_range_source_can_be_restored_without_dialog(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "mapped.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("size,passing\n")
                handle.write("2.0,100\n")
                handle.write("1.0,60\n")
                handle.write("0.5,20\n")

            source = {
                "file_key": csv_path,
                "file_path": csv_path,
                "sample_name": "Restored mapped sample",
                "temperature": 12.0,
                "porosity": 0.31,
                "mapping_state": {
                    "raw_sieve_mode": False,
                    "calculated_selection_mode": "range",
                    "selected_size_range": [[1, 0], [2, 0], [3, 0]],
                    "selected_percent_range": [[1, 1], [2, 1], [3, 1]],
                },
            }

            dataset = _load_mapped_source(source)

        self.assertEqual(dataset.sample_name, "Restored mapped sample")
        self.assertEqual(dataset.file_path, csv_path)
        self.assertEqual(dataset.temperature, 12.0)
        self.assertEqual(dataset.porosity, 0.31)
        self.assertEqual(dataset.particle_sizes, [2.0, 1.0, 0.5])
        self.assertEqual(dataset.percent_passing, [100.0, 60.0, 20.0])
        self.assertEqual(dataset._source_mapping_state["calculated_selection_mode"], "range")

    def test_mapped_raw_sieve_source_includes_pan_mass(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "raw_mapped.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("size,full,empty\n")
                handle.write("2.0,110,100\n")
                handle.write("1.0,130,100\n")
                handle.write("0.5,150,100\n")
                handle.write("Pan,110,100\n")

            source = {
                "file_key": csv_path,
                "file_path": csv_path,
                "sample_name": "Restored raw sample",
                "mapping_state": {
                    "raw_sieve_mode": True,
                    "header_row": 0,
                    "column_indices": {
                        "raw_size": 1,
                        "sieve_sample": 2,
                        "empty_sieve": 3,
                    },
                },
            }

            dataset = _load_mapped_source(source)

        self.assertEqual(dataset.particle_sizes, [2.0, 1.0, 0.5])
        self.assertEqual(dataset.percent_passing, [90.0, 60.0, 10.0])

    def test_batch_import_loads_detected_sheet_qualified_excel_without_review(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workbook = os.path.join(tempdir, "nbal_like.xlsx")
            write_nbal_style_workbook(workbook)

            queue = _ListQueue()
            run_batch_import([(workbook, "English")], queue, temperature=12.0)

        loaded_events = [event for event in queue.events if event[0] == "item_loaded"]
        failed_events = [event for event in queue.events if event[0] == "item_failed"]
        finished_events = [event for event in queue.events if event[0] == "finished"]

        self.assertEqual(len(failed_events), 0)
        self.assertEqual(len(loaded_events), 1)
        _, file_key, dataset, status, sample_name = loaded_events[0]
        self.assertTrue(file_key.endswith("nbal_like.xlsx:::English"))
        self.assertEqual(status, "loaded")
        self.assertIn("English", sample_name)
        self.assertEqual(dataset.particle_sizes[:3], [2.0, 1.0, 0.6])
        self.assertAlmostEqual(dataset.percent_passing[0], 98.1358189081225)
        self.assertEqual(finished_events[0][1]["loaded"], 1)
        self.assertEqual(finished_events[0][1]["review"], 0)

    def test_batch_import_raw_intent_prefers_raw_sieve_candidate(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workbook = os.path.join(tempdir, "nbal_raw_like.xlsx")
            write_nbal_style_workbook(workbook)

            queue = _ListQueue()
            run_batch_import(
                [
                    {
                        "file_key": f"{workbook}:::English",
                        "file_path": workbook,
                        "sheet_name": "English",
                        "import_intent": "raw_sieve",
                    }
                ],
                queue,
                temperature=12.0,
            )

        loaded_events = [event for event in queue.events if event[0] == "item_loaded"]
        self.assertEqual(len(loaded_events), 1)
        _, _, dataset, _, _ = loaded_events[0]
        provenance = dataset._source_import_provenance
        self.assertEqual(provenance["intent"], "raw_sieve")
        self.assertEqual(provenance["data_type"], "raw_sieve")
        self.assertTrue(provenance["intent_matched"])
        self.assertTrue(dataset._source_mapping_state["raw_sieve_mode"])
        log_events = [event for event in queue.events if event[0] == "log_event"]
        self.assertTrue(
            any(
                event[1]["context"]["pathway"] == "Excel auto-detection"
                and event[1]["context"]["data_type"] == "raw_sieve"
                for event in log_events
            )
        )

    def test_external_load_forwards_raw_sieve_weight_warnings_to_log_queue(self):
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = os.path.join(tempdir, "raw_negative.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("size,full,empty\n")
                handle.write("2.0,110,100\n")
                handle.write("1.0,130,100\n")
                handle.write("0.063,99.8,100\n")

            queue = _ListQueue()
            run_external_load(
                [
                    {
                        "file_key": csv_path,
                        "file_path": csv_path,
                        "mapping_state": {
                            "raw_sieve_mode": True,
                            "header_row": 0,
                            "column_indices": {
                                "raw_size": 1,
                                "sieve_sample": 2,
                                "empty_sieve": 3,
                            },
                        },
                    }
                ],
                stage_title="Opening file",
                result_queue=queue,
                temperature=12.0,
            )

        warning_events = [
            event for event in queue.events
            if event[0] == "log_event" and event[1]["level"] == "WARNING"
        ]
        self.assertTrue(
            any(
                "Negative retained weight" in event[1]["message"]
                and event[1].get("file_key") == csv_path
                for event in warning_events
            )
        )

    def test_batch_import_warns_when_processed_intent_loads_raw_sieve_candidate(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workbook = os.path.join(tempdir, "raw_only.xlsx")
            write_raw_sieve_only_workbook(workbook)

            queue = _ListQueue()
            run_batch_import(
                [
                    {
                        "file_key": f"{workbook}:::English",
                        "file_path": workbook,
                        "sheet_name": "English",
                        "import_intent": "processed",
                    }
                ],
                queue,
                temperature=12.0,
            )

        loaded_events = [event for event in queue.events if event[0] == "item_loaded"]
        warning_events = [
            event for event in queue.events
            if event[0] == "log_event" and event[1]["level"] == "WARNING"
        ]

        self.assertEqual(len(loaded_events), 1)
        _, _, dataset, _, _ = loaded_events[0]
        provenance = dataset._source_import_provenance
        self.assertEqual(provenance["intent"], "processed_curve")
        self.assertEqual(provenance["data_type"], "raw_sieve")
        self.assertFalse(provenance["intent_matched"])
        self.assertTrue(dataset._source_mapping_state["raw_sieve_mode"])
        self.assertTrue(
            any(
                "Requested processed curve" in event[1]["message"]
                and "raw sieve weights" in event[1]["message"]
                and event[1]["context"]["data_type"] == "raw_sieve"
                for event in warning_events
            )
        )

    def test_batch_import_raw_intent_falls_back_to_processed_curve_candidate(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workbook = os.path.join(tempdir, "processed_only.xlsx")
            write_processed_curve_only_workbook(workbook)

            queue = _ListQueue()
            run_batch_import(
                [
                    {
                        "file_key": f"{workbook}:::English",
                        "file_path": workbook,
                        "sheet_name": "English",
                        "import_intent": "raw_sieve",
                    }
                ],
                queue,
                temperature=12.0,
            )

        loaded_events = [event for event in queue.events if event[0] == "item_loaded"]
        failed_events = [event for event in queue.events if event[0] == "item_failed"]
        self.assertEqual(len(failed_events), 0)
        self.assertEqual(len(loaded_events), 1)
        _, _, dataset, _, _ = loaded_events[0]
        provenance = dataset._source_import_provenance
        self.assertEqual(provenance["intent"], "raw_sieve")
        self.assertEqual(provenance["data_type"], "processed_curve")
        self.assertFalse(provenance["intent_matched"])
        self.assertFalse(dataset._source_mapping_state["raw_sieve_mode"])
        self.assertEqual(dataset.particle_sizes[:3], [2.0, 1.0, 0.5])
        self.assertEqual(dataset.percent_passing[:3], [100.0, 70.0, 30.0])
        log_events = [event for event in queue.events if event[0] == "log_event"]
        self.assertTrue(
            any(
                "Requested raw sieve weights" in event[1]["message"]
                and event[1]["context"]["data_type"] == "processed_curve"
                and event[1]["level"] == "WARNING"
                for event in log_events
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
