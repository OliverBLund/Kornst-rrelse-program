from __future__ import annotations

import os
from typing import Sequence

from data_loader import DataLoader
from k_calculations import KCalculator


def _friendly_load_error(error: Exception | str) -> str:
    error_str = str(error)
    lowered = error_str.lower()
    if "requires manual" in lowered or "column mapping" in lowered:
        return "Excel sheet requires manual column mapping"
    if "could not parse" in lowered:
        return "Could not auto-detect column format"
    if "no valid" in lowered:
        return "No valid grain size data found"
    if "delimiter" in lowered:
        return "Could not determine file delimiter format"
    return error_str


def _build_grain_data(dataset) -> dict:
    grain_data = {}
    for key, value in {
        "D10": dataset.get_d10(),
        "D20": dataset.get_d20(),
        "D30": dataset.get_d30(),
        "D50": dataset.get_d50(),
        "D60": dataset.get_d60(),
    }.items():
        if value is not None:
            grain_data[key] = value

    grain_data["particle_sizes"] = list(dataset.particle_sizes)
    grain_data["percent_passing"] = list(dataset.percent_passing)
    return grain_data


def _resolve_porosity(dataset) -> float:
    porosity = getattr(dataset, "current_porosity", None)
    if porosity is None:
        porosity = getattr(dataset, "calculated_porosity", None)
    if porosity is None:
        porosity = dataset.porosity
    dataset.current_porosity = porosity
    return porosity


def prepare_dataset_for_ui(dataset, *, temperature: float | None = None, calculator: KCalculator | None = None):
    """Attach precomputed K results so the GUI can bind them without recalculating."""
    if temperature is not None:
        dataset.temperature = temperature

    calculator = calculator or KCalculator()
    porosity = _resolve_porosity(dataset)
    results = calculator.calculate_all_methods(
        _build_grain_data(dataset),
        temperature=dataset.temperature,
        porosity=porosity,
        selected_methods=calculator.get_all_method_names(),
    )

    dataset._precomputed_k_results = results
    dataset._precomputed_k_temperature = dataset.temperature
    dataset._precomputed_k_porosity = porosity
    return dataset


def run_batch_import(file_entries: Sequence[object], result_queue, *, temperature: float | None = None) -> None:
    """Load selected files in a separate process and stream queue events back to the UI."""
    try:
        loader = DataLoader()
        calculator = KCalculator()
        total = len(file_entries)
        summary = {"total": total, "loaded": 0, "review": 0, "failed": 0, "canceled": False}

        for index, file_entry in enumerate(file_entries, start=1):
            if isinstance(file_entry, tuple):
                file_path, sheet_name = file_entry
                file_key = f"{file_path}:::{sheet_name}"
                display_name = f"{os.path.basename(file_path)} [{sheet_name}]"
            else:
                file_path = str(file_entry)
                sheet_name = None
                file_key = file_path
                display_name = os.path.basename(file_path)

            result_queue.put(("progress", index, total, "Loading selected files", display_name))

            try:
                if sheet_name:
                    raise ValueError("Excel sheet requires manual column mapping")

                dataset = loader.load_file(file_path)
                dataset.file_path = file_path
                sample_name = getattr(dataset, "sample_name", os.path.basename(file_path))

                if dataset.has_errors():
                    summary["failed"] += 1
                    result_queue.put(
                        (
                            "item_validation_failed",
                            file_key,
                            dataset,
                            sample_name,
                            "Data loaded but has validation errors",
                        )
                    )
                else:
                    prepare_dataset_for_ui(dataset, temperature=temperature, calculator=calculator)
                    summary["loaded"] += 1
                    result_queue.put(("item_loaded", file_key, dataset, "loaded", sample_name))
            except Exception as exc:
                summary["review"] += 1
                result_queue.put(("item_failed", file_key, _friendly_load_error(exc)))

        result_queue.put(("finished", summary))
    except Exception as exc:
        result_queue.put(("process_error", str(exc)))


def run_external_load(
    file_paths: Sequence[str],
    *,
    stage_title: str,
    result_queue,
    temperature: float | None = None,
) -> None:
    """Load external datasets in a separate process and stream queue events back to the UI."""
    try:
        loader = DataLoader()
        calculator = KCalculator()
        normalized_paths = [os.path.normpath(path) for path in file_paths]
        total = len(normalized_paths)
        summary = {"total": total, "loaded": 0, "failed": 0, "canceled": False}

        for index, file_path in enumerate(normalized_paths, start=1):
            display_name = os.path.basename(file_path)
            result_queue.put(("progress", index, total, stage_title, display_name))

            try:
                dataset = loader.load_file(file_path)
                dataset.file_path = file_path
                prepare_dataset_for_ui(dataset, temperature=temperature, calculator=calculator)
                summary["loaded"] += 1
                result_queue.put(("file_loaded", file_path, dataset))
            except Exception as exc:
                summary["failed"] += 1
                result_queue.put(("file_failed", file_path, _friendly_load_error(exc)))

        result_queue.put(("finished", summary))
    except Exception as exc:
        result_queue.put(("process_error", str(exc)))
