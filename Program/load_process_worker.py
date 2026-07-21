from __future__ import annotations

import logging
import os
from typing import Any, Mapping, Sequence

from data_loader import DataLoader, GrainSizeData, calculate_sieve_percent_passing
from delimited_text import DELIMITED_TEXT_EXTENSIONS, read_delimited_rows
from import_resolver import resolve_excel_import
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


def _source_group_name(source: object, mapping_state: Mapping[str, Any] | None = None) -> str:
    value = None
    if isinstance(source, Mapping):
        value = source.get("group_name")
    if not value and mapping_state:
        value = mapping_state.get("group_name")
    text = str(value or "Ungrouped").strip()
    return text or "Ungrouped"


class _QueueLogHandler(logging.Handler):
    """Forward warning/error logs from a worker process to the UI queue."""

    def __init__(self, result_queue) -> None:
        super().__init__(logging.WARNING)
        self._result_queue = result_queue
        self._file_key: str | None = None
        self._context: dict[str, Any] = {}

    def set_context(self, file_key: str | None, context: Mapping[str, Any] | None = None) -> None:
        self._file_key = file_key
        self._context = dict(context or {})

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event = {
                "level": record.levelname,
                "source": record.name,
                "message": record.getMessage(),
            }
            if self._file_key:
                event["file_key"] = self._file_key
            if self._context:
                event["context"] = dict(self._context)
            self._result_queue.put(
                (
                    "log_event",
                    event,
                )
            )
        except Exception:
            pass


def _human_data_type(data_type: object) -> str:
    value = str(data_type or "processed_curve")
    if value == "raw_sieve":
        return "raw sieve weights"
    return "processed curve"


def _queue_log_event(
    result_queue,
    *,
    level: str,
    source: str,
    message: str,
    file_key: str | None = None,
    context: Mapping[str, Any] | None = None,
) -> None:
    event: dict[str, Any] = {
        "level": level,
        "source": source,
        "message": message,
    }
    if file_key:
        event["file_key"] = file_key
    if context:
        event["context"] = dict(context)
    result_queue.put(("log_event", event))


def _queue_dataset_import_event(result_queue, file_key: str, dataset, display_name: str | None = None) -> None:
    provenance = getattr(dataset, "_source_import_provenance", None) or {}
    mapping_state = getattr(dataset, "_source_mapping_state", None) or {}
    data_type = provenance.get("data_type")
    if not data_type:
        data_type = "raw_sieve" if mapping_state.get("raw_sieve_mode") else "processed_curve"

    source = provenance.get("source") or "standard_loader"
    if source == "auto_detected":
        pathway = "Excel auto-detection"
    elif source == "manual_mapping":
        pathway = "manual mapping"
    else:
        pathway = "standard file loader"

    context = dict(provenance)
    context.update(
        {
            "file_key": file_key,
            "sample_name": getattr(dataset, "sample_name", display_name or ""),
            "pathway": pathway,
            "data_type": data_type,
        }
    )

    sample_label = getattr(dataset, "sample_name", None) or display_name or os.path.basename(file_key)
    data_label = _human_data_type(data_type)
    intent = provenance.get("intent")
    intent_mismatch = bool(intent and not provenance.get("intent_matched", True))
    if intent_mismatch:
        requested_label = _human_data_type(intent)
        message = f"Requested {requested_label}; loaded {sample_label} as {data_label} via {pathway}."
    else:
        message = f"Loaded {sample_label} as {data_label} via {pathway}."

    _queue_log_event(
        result_queue,
        level="WARNING" if intent_mismatch else "INFO",
        source="data_loader",
        message=message,
        file_key=file_key,
        context=context,
    )


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
    if file_ext in DELIMITED_TEXT_EXTENSIONS:
        rows, _delimiter, _encoding = read_delimited_rows(file_path)
        return rows

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
    if passing_idx < 0:
        if retained_idx >= 0:
            raise ValueError(
                "Saved retained-column mappings are not imported automatically. "
                "Processed data must provide cumulative percent passing."
            )
        raise ValueError("Mapped source is missing a cumulative percent-passing column")

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
            percent_text = row[passing_idx]
            if not _is_numeric(percent_text):
                continue
            percent = _coerce_float(percent_text)
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
    pan_retained_weight = 0.0
    pan_labels = {"pan", "bund", "bottom"}
    for row in data_rows:
        if len(row) <= max_idx:
            continue
        try:
            if not (_is_numeric(row[empty_idx]) and _is_numeric(row[full_idx])):
                continue
            empty = _coerce_float(row[empty_idx])
            full = _coerce_float(row[full_idx])
            if not _is_numeric(row[size_idx]):
                if str(row[size_idx]).strip().lower() in pan_labels and full >= empty:
                    pan_retained_weight += full - empty
                continue
            size = _coerce_float(row[size_idx])
            if size <= 0:
                continue
            sieve_sizes.append(size)
            empty_weights.append(empty)
            full_weights.append(full)
        except (IndexError, ValueError):
            continue

    return calculate_sieve_percent_passing(
        sieve_sizes,
        empty_weights,
        full_weights,
        pan_retained_weight=pan_retained_weight,
    )


def _extract_raw_sieve_ranges_from_rows(
    rows: list[list[str]], mapping_state: Mapping[str, Any]
) -> tuple[list[float], list[float]]:
    ranges = [
        mapping_state.get("selected_size_range") or [],
        mapping_state.get("selected_empty_range") or [],
        mapping_state.get("selected_full_range") or [],
    ]
    if not all(ranges) or len({len(values) for values in ranges}) != 1:
        raise ValueError("Mapped raw sieve source is missing three matching cell ranges")

    positions = [
        sorted((int(row), int(col)) for row, col in values)
        for values in ranges
    ]
    sieve_sizes: list[float] = []
    empty_weights: list[float] = []
    full_weights: list[float] = []
    pan_retained_weight = 0.0

    for size_pos, empty_pos, full_pos in zip(*positions):
        try:
            size_text = rows[size_pos[0]][size_pos[1]]
            empty_text = rows[empty_pos[0]][empty_pos[1]]
            full_text = rows[full_pos[0]][full_pos[1]]
        except (IndexError, TypeError):
            continue
        if not (_is_numeric(empty_text) and _is_numeric(full_text)):
            continue
        empty = _coerce_float(empty_text)
        full = _coerce_float(full_text)
        if str(size_text).strip().lower() in {"pan", "bund", "bottom"}:
            if full >= empty:
                pan_retained_weight += full - empty
            continue
        if not _is_numeric(size_text):
            continue
        size = _coerce_float(size_text)
        if size <= 0:
            continue
        sieve_sizes.append(size)
        empty_weights.append(empty)
        full_weights.append(full)

    if len(sieve_sizes) < 3:
        raise ValueError("Mapped raw sieve ranges contain fewer than three valid sieve rows")
    return calculate_sieve_percent_passing(
        sieve_sizes,
        empty_weights,
        full_weights,
        pan_retained_weight=pan_retained_weight,
    )


def _load_mapped_source(source: Mapping[str, Any]) -> GrainSizeData:
    mapping_state = source.get("mapping_state") or {}
    if not isinstance(mapping_state, Mapping):
        raise ValueError("Mapped source has invalid mapping state")

    file_key = _source_file_key(source)
    file_path, sheet_from_key = _split_file_key(file_key)
    sheet_name = source.get("sheet_name") or sheet_from_key or mapping_state.get("current_sheet")
    rows = _load_rows(file_path, sheet_name=sheet_name)

    if (
        mapping_state.get("raw_sieve_mode")
        and mapping_state.get("calculated_selection_mode") == "range"
    ):
        particle_sizes, percent_passing = _extract_raw_sieve_ranges_from_rows(
            rows, mapping_state
        )
    elif mapping_state.get("raw_sieve_mode"):
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
        group_name=_source_group_name(source, mapping_state),
    )
    dataset._source_mapping_state = dict(mapping_state)
    dataset._source_descriptor = dict(source)
    provenance = source.get("import_provenance") or mapping_state.get("import_provenance")
    if provenance:
        dataset._source_import_provenance = dict(provenance)
    return dataset


def _load_detected_excel_source(
    file_path: str,
    *,
    sheet_name: str | None = None,
    sample_name: str | None = None,
    temperature: float | None = None,
    porosity: float | None = None,
    import_intent: str = "processed",
) -> GrainSizeData:
    rows = _load_rows(file_path, sheet_name=sheet_name)
    resolution = resolve_excel_import(rows, sheet_name=sheet_name, intent=import_intent)
    if resolution.requires_mapping:
        raise ValueError(resolution.message or "Excel sheet requires manual column mapping")

    source = {
        "file_key": f"{file_path}:::{sheet_name}" if sheet_name else file_path,
        "file_path": file_path,
        "sheet_name": sheet_name,
        "sample_name": sample_name,
        "temperature": temperature,
        "porosity": porosity,
        "mapping_state": dict(resolution.mapping_state),
        "import_intent": resolution.intent,
        "import_provenance": dict(resolution.provenance),
    }
    return _load_mapped_source(source)


def _load_source_without_mapping(
    file_path: str,
    *,
    sheet_name: str | None = None,
    loader: DataLoader,
    temperature: float | None = None,
    import_intent: str = "processed",
) -> GrainSizeData:
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext in {".xlsx", ".xls"}:
        return _load_detected_excel_source(
            file_path,
            sheet_name=sheet_name,
            temperature=temperature,
            import_intent=import_intent,
        )
    dataset = loader.load_file(file_path)
    dataset.file_path = f"{file_path}:::{sheet_name}" if sheet_name else file_path
    return dataset


def _build_grain_data(dataset) -> dict:
    grain_data = {}
    for key, value in {
        "D10": dataset.get_d10(),
        "D20": dataset.get_d20(),
        "D30": dataset.get_d30(),
        "D50": dataset.get_d50(),
        "D60": dataset.get_d60(),
        "Dmean_arithmetic": (
            dataset.get_arithmetic_mean_grain_size()
            if hasattr(dataset, "get_arithmetic_mean_grain_size")
            else None
        ),
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
    log_handler = _QueueLogHandler(result_queue)
    root_logger = logging.getLogger()
    root_logger.addHandler(log_handler)
    try:
        loader = DataLoader()
        calculator = KCalculator()
        total = len(file_entries)
        summary = {"total": total, "loaded": 0, "review": 0, "failed": 0, "canceled": False}

        for index, file_entry in enumerate(file_entries, start=1):
            if isinstance(file_entry, Mapping):
                file_key = _source_file_key(file_entry)
                file_path, sheet_from_key = _split_file_key(file_key)
                file_path = str(file_entry.get("file_path") or file_path)
                sheet_name = file_entry.get("sheet_name") or sheet_from_key
                import_intent = str(file_entry.get("import_intent") or "processed")
                display_name = _source_display_name(file_entry)
            elif isinstance(file_entry, tuple):
                file_path, sheet_name = file_entry
                file_key = f"{file_path}:::{sheet_name}"
                import_intent = "processed"
                display_name = f"{os.path.basename(file_path)} [{sheet_name}]"
            else:
                file_path = str(file_entry)
                sheet_name = None
                file_key = file_path
                import_intent = "processed"
                display_name = os.path.basename(file_path)

            log_handler.set_context(
                file_key,
                {
                    "file_key": file_key,
                    "pathway": "data loading",
                    "intent": import_intent,
                },
            )
            result_queue.put(("progress", index, total, "Loading selected files", display_name))

            try:
                dataset = _load_source_without_mapping(
                    file_path,
                    sheet_name=sheet_name,
                    loader=loader,
                    temperature=temperature,
                    import_intent=import_intent,
                )
                dataset.file_path = file_key
                sample_name = getattr(dataset, "sample_name", os.path.basename(file_path))
                _queue_dataset_import_event(result_queue, file_key, dataset, display_name)

                if dataset.has_errors():
                    summary["failed"] += 1
                    result_queue.put(
                        (
                            "item_validation_failed",
                            file_key,
                            dataset,
                            sample_name,
                            dataset.get_detailed_validation_report(),
                        )
                    )
                else:
                    prepare_dataset_for_ui(dataset, temperature=temperature, calculator=calculator)
                    summary["loaded"] += 1
                    result_queue.put(("item_loaded", file_key, dataset, "loaded", sample_name))
            except Exception as exc:
                detail = _friendly_load_error(exc)
                summary["review"] += 1
                _queue_log_event(
                    result_queue,
                    level="WARNING",
                    source="data_loader",
                    message=f"Could not load {display_name}: {detail}",
                    file_key=file_key,
                    context={
                        "file_key": file_key,
                        "pathway": "import review",
                        "intent": import_intent,
                    },
                )
                result_queue.put(("item_failed", file_key, detail))

        result_queue.put(("finished", summary))
    except Exception as exc:
        result_queue.put(("process_error", str(exc)))
    finally:
        try:
            root_logger.removeHandler(log_handler)
        except Exception:
            pass


def run_external_load(
    file_paths: Sequence[object],
    *,
    stage_title: str,
    result_queue,
    temperature: float | None = None,
) -> None:
    """Load external datasets in a separate process and stream queue events back to the UI."""
    log_handler = _QueueLogHandler(result_queue)
    root_logger = logging.getLogger()
    root_logger.addHandler(log_handler)
    try:
        loader = DataLoader()
        calculator = KCalculator()
        sources = list(file_paths)
        total = len(sources)
        summary = {"total": total, "loaded": 0, "failed": 0, "canceled": False}

        for index, source in enumerate(sources, start=1):
            file_key = _source_file_key(source)
            display_name = _source_display_name(source)
            log_handler.set_context(
                file_key,
                {
                    "file_key": file_key,
                    "pathway": "external load",
                },
            )
            result_queue.put(("progress", index, total, stage_title, display_name))

            try:
                if isinstance(source, Mapping) and source.get("mapping_state"):
                    dataset = _load_mapped_source(source)
                    prepare_dataset_for_ui(dataset, temperature=dataset.temperature, calculator=calculator)
                    file_key = getattr(dataset, "file_path", file_key)
                else:
                    actual_path, sheet_name = _split_file_key(file_key)
                    restore_temperature = temperature
                    import_intent = "processed"
                    if isinstance(source, Mapping) and source.get("temperature") is not None:
                        restore_temperature = float(source["temperature"])
                    if isinstance(source, Mapping) and source.get("import_intent"):
                        import_intent = str(source["import_intent"])
                    dataset = _load_source_without_mapping(
                        actual_path,
                        sheet_name=sheet_name,
                        loader=loader,
                        temperature=restore_temperature,
                        import_intent=import_intent,
                    )
                    dataset.file_path = file_key
                    if isinstance(source, Mapping) and source.get("group_name") is not None:
                        dataset.group_name = _source_group_name(source)
                    prepare_dataset_for_ui(dataset, temperature=restore_temperature, calculator=calculator)
                summary["loaded"] += 1
                _queue_dataset_import_event(result_queue, file_key, dataset, display_name)
                result_queue.put(("file_loaded", file_key, dataset))
            except Exception as exc:
                detail = _friendly_load_error(exc)
                summary["failed"] += 1
                _queue_log_event(
                    result_queue,
                    level="WARNING",
                    source="data_loader",
                    message=f"Could not load {display_name}: {detail}",
                    file_key=file_key,
                    context={
                        "file_key": file_key,
                        "pathway": "external load",
                    },
                )
                result_queue.put(("file_failed", file_key, detail))

        result_queue.put(("finished", summary))
    except Exception as exc:
        result_queue.put(("process_error", str(exc)))
    finally:
        try:
            root_logger.removeHandler(log_handler)
        except Exception:
            pass
