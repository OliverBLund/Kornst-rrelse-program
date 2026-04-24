from __future__ import annotations

import os
from typing import Any, Mapping, Sequence

from data_loader import DataLoader, GrainSizeData, calculate_sieve_percent_passing
from k_calculations import KCalculator


def _friendly_load_error(error: Exception | str) -> str:
    error_str = str(error)
    lowered = error_str.lower()
    if "xlrd" in lowered and "xls" in lowered:
        return "Legacy Excel (.xls) support is unavailable in this build. Rebuild with xlrd included or convert the file to .xlsx/.csv."
    if "requires manual" in lowered or "column mapping" in lowered:
        return "Excel sheet requires manual column mapping"
    if "could not parse" in lowered:
        return "Could not auto-detect column format"
    if "no valid" in lowered:
        return "No valid grain size data found"
    if "delimiter" in lowered:
        return "Could not determine file delimiter format"
    return error_str


def _split_file_key(file_key: str) -> tuple[str, str | None]:
    if ":::" in file_key:
        return file_key.split(":::", 1)
    return file_key, None


def _source_file_key(source: object) -> str:
    if isinstance(source, Mapping):
        file_key = source.get("file_key")
        if isinstance(file_key, str) and file_key:
            return file_key
        file_path = str(source.get("file_path") or "")
        sheet_name = source.get("sheet_name")
        if sheet_name:
            return f"{file_path}:::{sheet_name}"
        return file_path
    return str(source)


def _source_display_name(source: object) -> str:
    if isinstance(source, Mapping):
        sample_name = source.get("sample_name")
        if isinstance(sample_name, str) and sample_name:
            return sample_name
    file_key = _source_file_key(source)
    actual_path, sheet_name = _split_file_key(file_key)
    if sheet_name:
        return f"{os.path.basename(actual_path)} [{sheet_name}]"
    return os.path.basename(actual_path)


def _coerce_float(value: Any) -> float:
    return float(str(value).strip().replace(",", "."))


def _is_numeric(value: Any) -> bool:
    try:
        _coerce_float(value)
        return True
    except (TypeError, ValueError):
        return False


def _load_rows(file_path: str, sheet_name: str | None = None) -> list[list[str]]:
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext == ".csv":
        import csv

        with open(file_path, "r", encoding="utf-8") as handle:
            return [list(row) for row in csv.reader(handle)]

    if file_ext in {".xlsx", ".xls"}:
        import pandas as pd

        excel_file = pd.ExcelFile(file_path)
        try:
            sheet_names = list(excel_file.sheet_names)
        finally:
            excel_file.close()

        target_sheet = sheet_name
        if not target_sheet or target_sheet not in sheet_names:
            lower_name_map = {name.lower(): name for name in sheet_names}
            target_sheet = lower_name_map.get("english", sheet_names[0])
        df = pd.read_excel(file_path, sheet_name=target_sheet, header=None)
        return [[str(cell) if pd.notna(cell) else "" for cell in row] for row in df.values.tolist()]

    raise ValueError(f"Unsupported mapped source type: {file_ext or 'unknown'}")


def _extract_columns_from_rows(rows: list[list[str]], mapping_state: Mapping[str, Any]) -> tuple[list[float], list[float]]:
    column_indices = mapping_state.get("column_indices") or {}
    size_idx = int(column_indices.get("size", 0)) - 1
    passing_idx = int(column_indices.get("passing", 0)) - 1
    retained_idx = int(column_indices.get("retained", 0)) - 1

    if size_idx < 0:
        raise ValueError("Mapped source is missing a particle-size column")
    if passing_idx < 0 and retained_idx < 0:
        raise ValueError("Mapped source is missing a percent passing/retained column")
    if passing_idx >= 0 and retained_idx >= 0:
        retained_idx = -1

    header_row = int(mapping_state.get("header_row", 0) or 0)
    data_rows = rows[header_row + 1:] if len(rows) > header_row + 1 else rows
    max_idx = max(size_idx, passing_idx, retained_idx)

    particle_sizes: list[float] = []
    percent_passing: list[float] = []
    for row in data_rows:
        if len(row) <= max_idx:
            continue
        try:
            size_text = row[size_idx]
            if not _is_numeric(size_text):
                continue
            if passing_idx >= 0:
                percent_text = row[passing_idx]
                if not _is_numeric(percent_text):
                    continue
                percent = _coerce_float(percent_text)
            else:
                retained_text = row[retained_idx]
                if not _is_numeric(retained_text):
                    continue
                percent = 100.0 - _coerce_float(retained_text)
            particle_sizes.append(_coerce_float(size_text))
            percent_passing.append(percent)
        except (IndexError, ValueError):
            continue

    if not particle_sizes:
        raise ValueError("No valid mapped rows found")
    return particle_sizes, percent_passing


def _extract_ranges_from_rows(rows: list[list[str]], mapping_state: Mapping[str, Any]) -> tuple[list[float], list[float]]:
    size_range = mapping_state.get("selected_size_range") or []
    percent_range = mapping_state.get("selected_percent_range") or []
    if not size_range or not percent_range:
        raise ValueError("Mapped source is missing cell range selections")
    if len(size_range) != len(percent_range):
        raise ValueError("Mapped size and percent ranges have different lengths")

    size_positions = sorted((int(row), int(col)) for row, col in size_range)
    percent_positions = sorted((int(row), int(col)) for row, col in percent_range)

    particle_sizes: list[float] = []
    percent_passing: list[float] = []
    for (size_row, size_col), (percent_row, percent_col) in zip(size_positions, percent_positions):
        try:
            size_text = rows[size_row][size_col]
            percent_text = rows[percent_row][percent_col]
            if not _is_numeric(size_text) or not _is_numeric(percent_text):
                continue
            particle_sizes.append(_coerce_float(size_text))
            percent_passing.append(_coerce_float(percent_text))
        except (IndexError, ValueError):
            continue

    if not particle_sizes:
        raise ValueError("No valid numeric cells found in mapped ranges")
    return particle_sizes, percent_passing


def _extract_raw_sieve_from_rows(rows: list[list[str]], mapping_state: Mapping[str, Any]) -> tuple[list[float], list[float]]:
    column_indices = mapping_state.get("column_indices") or {}
    size_idx = int(column_indices.get("raw_size", 0)) - 1
    empty_idx = int(column_indices.get("empty_sieve", 0)) - 1
    full_idx = int(column_indices.get("sieve_sample", 0)) - 1

    if size_idx < 0 or empty_idx < 0 or full_idx < 0:
        raise ValueError("Mapped raw sieve source is missing required columns")

    header_row = int(mapping_state.get("header_row", 0) or 0)
    data_rows = rows[header_row + 1:] if len(rows) > header_row + 1 else rows
    max_idx = max(size_idx, empty_idx, full_idx)

    sieve_sizes: list[float] = []
    empty_weights: list[float] = []
    full_weights: list[float] = []
    for row in data_rows:
        if len(row) <= max_idx:
            continue
        try:
            if not (_is_numeric(row[size_idx]) and _is_numeric(row[empty_idx]) and _is_numeric(row[full_idx])):
                continue
            size = _coerce_float(row[size_idx])
            if size <= 0:
                continue
            sieve_sizes.append(size)
            empty_weights.append(_coerce_float(row[empty_idx]))
            full_weights.append(_coerce_float(row[full_idx]))
        except (IndexError, ValueError):
            continue

    return calculate_sieve_percent_passing(sieve_sizes, empty_weights, full_weights)


def _load_mapped_source(source: Mapping[str, Any]) -> GrainSizeData:
    mapping_state = source.get("mapping_state") or {}
    if not isinstance(mapping_state, Mapping):
        raise ValueError("Mapped source has invalid mapping state")

    file_key = _source_file_key(source)
    file_path, sheet_from_key = _split_file_key(file_key)
    sheet_name = source.get("sheet_name") or sheet_from_key or mapping_state.get("current_sheet")
    rows = _load_rows(file_path, sheet_name=sheet_name)

    if mapping_state.get("raw_sieve_mode"):
        particle_sizes, percent_passing = _extract_raw_sieve_from_rows(rows, mapping_state)
    elif mapping_state.get("calculated_selection_mode") == "range":
        particle_sizes, percent_passing = _extract_ranges_from_rows(rows, mapping_state)
    else:
        particle_sizes, percent_passing = _extract_columns_from_rows(rows, mapping_state)

    sample_name = str(source.get("sample_name") or mapping_state.get("sample_name") or os.path.splitext(os.path.basename(file_path))[0])
    if sheet_name and f"[{sheet_name}]" not in sample_name:
        sample_name = f"{sample_name} [{sheet_name}]"

    dataset = GrainSizeData(
        sample_name=sample_name,
        temperature=float(source.get("temperature") or mapping_state.get("temperature") or 20.0),
        porosity=float(source.get("porosity") or mapping_state.get("porosity") or 0.35),
        particle_sizes=particle_sizes,
        percent_passing=percent_passing,
        file_path=file_key,
    )
    dataset._source_mapping_state = dict(mapping_state)
    dataset._source_descriptor = dict(source)
    return dataset


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
    file_paths: Sequence[object],
    *,
    stage_title: str,
    result_queue,
    temperature: float | None = None,
) -> None:
    """Load external datasets in a separate process and stream queue events back to the UI."""
    try:
        loader = DataLoader()
        calculator = KCalculator()
        sources = list(file_paths)
        total = len(sources)
        summary = {"total": total, "loaded": 0, "failed": 0, "canceled": False}

        for index, source in enumerate(sources, start=1):
            file_key = _source_file_key(source)
            display_name = _source_display_name(source)
            result_queue.put(("progress", index, total, stage_title, display_name))

            try:
                if isinstance(source, Mapping) and source.get("mapping_state"):
                    dataset = _load_mapped_source(source)
                    prepare_dataset_for_ui(dataset, temperature=dataset.temperature, calculator=calculator)
                    file_key = getattr(dataset, "file_path", file_key)
                else:
                    actual_path, sheet_name = _split_file_key(file_key)
                    if sheet_name:
                        raise ValueError("Excel sheet requires manual column mapping")
                    dataset = loader.load_file(actual_path)
                    dataset.file_path = file_key
                    restore_temperature = temperature
                    if isinstance(source, Mapping) and source.get("temperature") is not None:
                        restore_temperature = float(source["temperature"])
                    prepare_dataset_for_ui(dataset, temperature=restore_temperature, calculator=calculator)
                summary["loaded"] += 1
                result_queue.put(("file_loaded", file_key, dataset))
            except Exception as exc:
                summary["failed"] += 1
                result_queue.put(("file_failed", file_key, _friendly_load_error(exc)))

        result_queue.put(("finished", summary))
    except Exception as exc:
        result_queue.put(("process_error", str(exc)))
