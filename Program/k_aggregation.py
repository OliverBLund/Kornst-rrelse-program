"""Cross-dataset hydraulic-conductivity aggregation.

This module keeps batch statistics out of the Qt comparison widgets.  It works
with dataset-tab-like objects exposing get_dataset(), get_dataset_name(), and
get_results(), but it has no Qt dependency.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import math
import statistics
from typing import Iterable, Mapping, Optional, Sequence


UNGROUPED_LABEL = "Ungrouped"


@dataclass(frozen=True)
class KAggregationOptions:
    """Options controlling which K result cells contribute to aggregates."""

    selected_methods: Optional[frozenset[str]] = None
    include_warnings: bool = False
    include_errors: bool = False
    require_methods_in_all_datasets: bool = False
    method_order: tuple[str, ...] = ()

    @classmethod
    def from_methods(
        cls,
        methods: Optional[Iterable[str]],
        **kwargs,
    ) -> "KAggregationOptions":
        selected = None if methods is None else frozenset(str(m) for m in methods)
        return cls(selected_methods=selected, **kwargs)


@dataclass(frozen=True)
class KValueRecord:
    dataset_name: str
    group_name: str
    method_name: str
    k_value: Optional[float]
    status: str
    conditions_met: bool
    status_message: str = ""
    included: bool = False
    exclusion_reason: str = ""

    @property
    def positive_value(self) -> Optional[float]:
        if self.k_value is None or self.k_value <= 0:
            return None
        return float(self.k_value)


@dataclass(frozen=True)
class AggregateStats:
    scope_name: str
    value_count: int = 0
    total_cells: int = 0
    included_count: int = 0
    excluded_count: int = 0
    missing_count: int = 0
    ok_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    dataset_count: int = 0
    method_count: int = 0
    geometric_mean_m_s: Optional[float] = None
    arithmetic_mean_m_s: Optional[float] = None
    median_m_s: Optional[float] = None
    min_m_s: Optional[float] = None
    max_m_s: Optional[float] = None
    std_dev_m_s: Optional[float] = None
    ln_std_dev: Optional[float] = None
    ln_variance: Optional[float] = None
    log10_std_dev: Optional[float] = None
    dataset_names: tuple[str, ...] = ()
    method_names: tuple[str, ...] = ()

    @property
    def values_available(self) -> bool:
        return self.value_count > 0


@dataclass(frozen=True)
class KAggregationReport:
    options: KAggregationOptions
    dataset_names: tuple[str, ...]
    group_names: tuple[str, ...]
    method_names: tuple[str, ...]
    records: tuple[KValueRecord, ...]
    included_records: tuple[KValueRecord, ...]
    overall: AggregateStats
    by_group: Mapping[str, AggregateStats] = field(default_factory=dict)
    by_dataset: Mapping[str, AggregateStats] = field(default_factory=dict)
    by_method: Mapping[str, AggregateStats] = field(default_factory=dict)
    complete_methods: frozenset[str] = frozenset()


def normalize_group_name(value: object) -> str:
    text = str(value or "").strip()
    return text or UNGROUPED_LABEL


def dataset_group_name(dataset: object) -> str:
    for attr in ("group_name", "dataset_group", "sample_group", "stratigraphy_group"):
        value = getattr(dataset, attr, None)
        if value:
            return normalize_group_name(value)
    return UNGROUPED_LABEL


def _dataset_from_tab(tab: object) -> object:
    if hasattr(tab, "get_dataset"):
        return tab.get_dataset()
    return getattr(tab, "dataset", tab)


def _dataset_name(tab: object, dataset: object) -> str:
    if hasattr(tab, "get_dataset_name"):
        return str(tab.get_dataset_name())
    return str(getattr(dataset, "sample_name", "Dataset"))


def _results_from_tab(tab: object) -> Sequence[object]:
    if hasattr(tab, "get_results"):
        return list(tab.get_results() or [])
    return list(getattr(tab, "current_results", []) or getattr(tab, "results", []) or [])


@dataclass(frozen=True)
class _ResultSequenceInput:
    label: str
    group_name: str
    results: tuple[object, ...]

    def get_dataset(self) -> object:
        return self

    def get_dataset_name(self) -> str:
        return self.label

    def get_results(self) -> tuple[object, ...]:
        return self.results


def _classify_result_status(result: object) -> str:
    status = getattr(result, "status", "")
    status_text = status.value if hasattr(status, "value") else str(status)
    status_upper = status_text.upper()
    conditions_met = bool(getattr(result, "conditions_met", True))
    if ("OK" in status_upper or "WITHIN_RANGE" in status_upper) and conditions_met:
        return "OK"
    if "WARNING" in status_upper or "OUTSIDE_RANGE" in status_upper or not conditions_met:
        return "Warning"
    return "Error"


def _ordered_methods(methods: Iterable[str], order: Sequence[str]) -> tuple[str, ...]:
    method_set = {str(method) for method in methods}
    order_index = {method: idx for idx, method in enumerate(order)}
    return tuple(sorted(method_set, key=lambda m: (order_index.get(m, len(order_index)), m.lower())))


def _record_is_allowed(record: KValueRecord, options: KAggregationOptions) -> tuple[bool, str]:
    if record.positive_value is None:
        return False, "missing_value"
    if record.status == "OK":
        return True, ""
    if record.status == "Warning":
        return (True, "") if options.include_warnings else (False, "warning")
    if record.status == "Error":
        return (True, "") if options.include_errors else (False, "error")
    return False, "error"


def _stats_for(
    scope_name: str,
    records: Sequence[KValueRecord],
    *,
    dataset_names: Sequence[str],
    method_names: Sequence[str],
) -> AggregateStats:
    included = [record for record in records if record.included and record.positive_value is not None]
    values = [record.positive_value for record in included if record.positive_value is not None]
    status_counts = Counter(record.status for record in records)
    total_cells = len(dataset_names) * len(method_names)
    missing_count = max(0, total_cells - len(records))
    excluded_count = len(records) - len(included)

    if not values:
        return AggregateStats(
            scope_name=scope_name,
            total_cells=total_cells,
            included_count=0,
            excluded_count=excluded_count,
            missing_count=missing_count,
            ok_count=status_counts.get("OK", 0),
            warning_count=status_counts.get("Warning", 0),
            error_count=status_counts.get("Error", 0),
            dataset_count=len(tuple(dataset_names)),
            method_count=len(tuple(method_names)),
            dataset_names=tuple(dataset_names),
            method_names=tuple(method_names),
        )

    log_values = [math.log(value) for value in values if value > 0]
    log10_values = [math.log10(value) for value in values if value > 0]
    ln_std_dev = statistics.pstdev(log_values) if len(log_values) > 1 else 0.0
    return AggregateStats(
        scope_name=scope_name,
        value_count=len(values),
        total_cells=total_cells,
        included_count=len(included),
        excluded_count=excluded_count,
        missing_count=missing_count,
        ok_count=status_counts.get("OK", 0),
        warning_count=status_counts.get("Warning", 0),
        error_count=status_counts.get("Error", 0),
        dataset_count=len(tuple(dataset_names)),
        method_count=len(tuple(method_names)),
        geometric_mean_m_s=math.exp(sum(log_values) / len(log_values)) if log_values else None,
        arithmetic_mean_m_s=statistics.fmean(values),
        median_m_s=statistics.median(values),
        min_m_s=min(values),
        max_m_s=max(values),
        std_dev_m_s=statistics.pstdev(values) if len(values) > 1 else 0.0,
        ln_std_dev=ln_std_dev,
        ln_variance=ln_std_dev * ln_std_dev,
        log10_std_dev=statistics.pstdev(log10_values) if len(log10_values) > 1 else 0.0,
        dataset_names=tuple(dataset_names),
        method_names=tuple(method_names),
    )


def build_k_aggregation(dataset_tabs: Sequence[object], options: KAggregationOptions | None = None) -> KAggregationReport:
    """Build aggregate K statistics across dataset tabs."""

    options = options or KAggregationOptions()
    dataset_names: list[str] = []
    group_by_dataset: dict[str, str] = {}
    raw_records: list[KValueRecord] = []

    for tab in dataset_tabs:
        dataset = _dataset_from_tab(tab)
        dataset_name = _dataset_name(tab, dataset)
        group_name = dataset_group_name(dataset)
        dataset_names.append(dataset_name)
        group_by_dataset[dataset_name] = group_name
        for result in _results_from_tab(tab):
            method_name = str(getattr(result, "method_name", "") or "").strip()
            if not method_name:
                continue
            k_value = getattr(result, "k_value", None)
            try:
                k_value = float(k_value) if k_value is not None else None
            except (TypeError, ValueError):
                k_value = None
            status = _classify_result_status(result)
            raw_records.append(
                KValueRecord(
                    dataset_name=dataset_name,
                    group_name=group_name,
                    method_name=method_name,
                    k_value=k_value,
                    status=status,
                    conditions_met=bool(getattr(result, "conditions_met", True)),
                    status_message=str(getattr(result, "status_message", "") or ""),
                )
            )

    selected_methods = options.selected_methods
    discovered_methods = {record.method_name for record in raw_records}
    if selected_methods is not None:
        candidate_methods = discovered_methods & set(selected_methods)
    else:
        candidate_methods = discovered_methods
    method_names = _ordered_methods(candidate_methods, options.method_order)

    base_allowed_by_cell: dict[tuple[str, str], bool] = {}
    exclusion_by_cell: dict[tuple[str, str], str] = {}
    for record in raw_records:
        if record.method_name not in method_names:
            base_allowed_by_cell[(record.dataset_name, record.method_name)] = False
            exclusion_by_cell[(record.dataset_name, record.method_name)] = "method_filter"
            continue
        allowed, reason = _record_is_allowed(record, options)
        base_allowed_by_cell[(record.dataset_name, record.method_name)] = allowed
        exclusion_by_cell[(record.dataset_name, record.method_name)] = reason

    complete_methods = {
        method
        for method in method_names
        if all(base_allowed_by_cell.get((dataset_name, method), False) for dataset_name in dataset_names)
    }
    if options.require_methods_in_all_datasets:
        included_methods = complete_methods
    else:
        included_methods = set(method_names)

    records: list[KValueRecord] = []
    included_records: list[KValueRecord] = []
    for record in raw_records:
        if record.method_name not in method_names:
            continue
        key = (record.dataset_name, record.method_name)
        allowed = base_allowed_by_cell.get(key, False)
        reason = exclusion_by_cell.get(key, "")
        if allowed and record.method_name not in included_methods:
            allowed = False
            reason = "not_valid_for_every_dataset"
        updated = KValueRecord(
            dataset_name=record.dataset_name,
            group_name=record.group_name,
            method_name=record.method_name,
            k_value=record.k_value,
            status=record.status,
            conditions_met=record.conditions_met,
            status_message=record.status_message,
            included=allowed,
            exclusion_reason="" if allowed else reason,
        )
        records.append(updated)
        if updated.included:
            included_records.append(updated)

    group_names = tuple(dict.fromkeys(group_by_dataset.get(name, UNGROUPED_LABEL) for name in dataset_names))
    overall = _stats_for("All selected", records, dataset_names=dataset_names, method_names=method_names)

    records_by_group: dict[str, list[KValueRecord]] = defaultdict(list)
    datasets_by_group: dict[str, list[str]] = defaultdict(list)
    for dataset_name in dataset_names:
        datasets_by_group[group_by_dataset.get(dataset_name, UNGROUPED_LABEL)].append(dataset_name)
    for record in records:
        records_by_group[record.group_name].append(record)

    by_group = {
        group: _stats_for(group, records_by_group.get(group, []), dataset_names=datasets, method_names=method_names)
        for group, datasets in datasets_by_group.items()
    }
    by_dataset = {
        dataset_name: _stats_for(
            dataset_name,
            [record for record in records if record.dataset_name == dataset_name],
            dataset_names=[dataset_name],
            method_names=method_names,
        )
        for dataset_name in dataset_names
    }
    by_method = {
        method: _stats_for(
            method,
            [record for record in records if record.method_name == method],
            dataset_names=dataset_names,
            method_names=[method],
        )
        for method in method_names
    }

    return KAggregationReport(
        options=options,
        dataset_names=tuple(dataset_names),
        group_names=group_names,
        method_names=method_names,
        records=tuple(records),
        included_records=tuple(included_records),
        overall=overall,
        by_group=by_group,
        by_dataset=by_dataset,
        by_method=by_method,
        complete_methods=frozenset(complete_methods),
    )


def build_k_result_aggregation(
    results: Sequence[object],
    options: KAggregationOptions | None = None,
    *,
    dataset_name: str = "Dataset",
    group_name: str = UNGROUPED_LABEL,
) -> KAggregationReport:
    """Build a K aggregation report for one dataset's calculation results."""

    source = _ResultSequenceInput(
        label=str(dataset_name or "Dataset"),
        group_name=normalize_group_name(group_name),
        results=tuple(results or ()),
    )
    return build_k_aggregation([source], options)


def build_k_result_summary(
    results: Sequence[object],
    options: KAggregationOptions | None = None,
    *,
    dataset_name: str = "Dataset",
    group_name: str = UNGROUPED_LABEL,
) -> AggregateStats:
    """Return the shared per-dataset K summary used by GUI, reports, and exports."""

    return build_k_result_aggregation(
        results,
        options,
        dataset_name=dataset_name,
        group_name=group_name,
    ).overall
