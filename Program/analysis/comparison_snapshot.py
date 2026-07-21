"""Shared comparison analysis snapshot.

The GUI, plots, exports, and reports should read aggregate comparison facts from
this module instead of recalculating means, medians, coverage, or group summaries
inside presentation files.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import statistics
from typing import Any, Iterable, Mapping, Optional, Sequence

from natural_order import natural_sort_key

from grain_classification import ISO14688, interpolate_at
from k_aggregation import (
    KAggregationOptions,
    KAggregationReport,
    build_k_aggregation,
    dataset_group_name,
    normalize_group_name,
)


@dataclass(frozen=True)
class DatasetAnalysisInput:
    """Dataset plus calculated K results and optional display metadata."""

    label: str
    dataset: object
    k_results: tuple[object, ...] = ()
    group_name: str = "Ungrouped"
    temperature: Optional[float] = None
    porosity: Optional[float] = None
    plot_context: Optional[Mapping[str, Any]] = None

    def get_dataset(self):
        return self.dataset

    def get_dataset_name(self) -> str:
        return self.label

    def get_results(self) -> tuple[object, ...]:
        return self.k_results


@dataclass(frozen=True)
class GrainMetricStats:
    name: str
    value_count: int = 0
    arithmetic_mean: Optional[float] = None
    median: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    std_dev: Optional[float] = None

    @property
    def values_available(self) -> bool:
        return self.value_count > 0


@dataclass(frozen=True)
class GrainAggregateStats:
    scope_name: str
    dataset_names: tuple[str, ...] = ()
    dataset_count: int = 0
    metrics: Mapping[str, GrainMetricStats] = field(default_factory=dict)
    class_counts: Mapping[str, int] = field(default_factory=dict)
    dominant_class: str = "N/A"


@dataclass(frozen=True)
class GrainAggregationReport:
    dataset_names: tuple[str, ...]
    group_names: tuple[str, ...]
    by_dataset: Mapping[str, GrainAggregateStats] = field(default_factory=dict)
    by_group: Mapping[str, GrainAggregateStats] = field(default_factory=dict)
    overall: GrainAggregateStats = field(default_factory=lambda: GrainAggregateStats("All selected"))


@dataclass(frozen=True)
class ComparisonSnapshotOptions:
    k_options: KAggregationOptions = field(default_factory=KAggregationOptions)
    classification_scheme: object = field(default_factory=lambda: ISO14688)


@dataclass(frozen=True)
class ComparisonSnapshot:
    inputs: tuple[DatasetAnalysisInput, ...]
    options: ComparisonSnapshotOptions
    k: KAggregationReport
    grain: GrainAggregationReport

    @property
    def dataset_count(self) -> int:
        return len(self.inputs)

    @property
    def group_names(self) -> tuple[str, ...]:
        return self.k.group_names


def dataset_analysis_from_tab(tab: object) -> DatasetAnalysisInput:
    """Build a plain analysis input from a DatasetTab-like object."""

    dataset = tab.get_dataset() if hasattr(tab, "get_dataset") else getattr(tab, "dataset", tab)
    label = (
        str(tab.get_dataset_name())
        if hasattr(tab, "get_dataset_name")
        else str(getattr(dataset, "sample_name", "Dataset"))
    )
    results = tuple(tab.get_results() or ()) if hasattr(tab, "get_results") else tuple(getattr(tab, "current_results", ()) or ())
    group_name = normalize_group_name(getattr(dataset, "group_name", dataset_group_name(dataset)))
    return DatasetAnalysisInput(
        label=label,
        dataset=dataset,
        k_results=results,
        group_name=group_name,
        temperature=getattr(tab, "temperature", getattr(dataset, "temperature", None)),
        porosity=getattr(tab, "porosity", getattr(dataset, "current_porosity", getattr(dataset, "porosity", None))),
    )


def build_comparison_snapshot(
    dataset_inputs: Sequence[DatasetAnalysisInput | object],
    options: ComparisonSnapshotOptions | None = None,
) -> ComparisonSnapshot:
    """Build a shared comparison snapshot for the selected datasets."""

    options = options or ComparisonSnapshotOptions()
    inputs = tuple(_coerce_input(item) for item in dataset_inputs)
    k_report = build_k_aggregation(inputs, options.k_options)
    grain_report = _build_grain_aggregation(inputs, options.classification_scheme)
    return ComparisonSnapshot(
        inputs=inputs,
        options=options,
        k=k_report,
        grain=grain_report,
    )


def _coerce_input(item: DatasetAnalysisInput | object) -> DatasetAnalysisInput:
    if isinstance(item, DatasetAnalysisInput):
        return item
    return dataset_analysis_from_tab(item)


def _build_grain_aggregation(
    inputs: Sequence[DatasetAnalysisInput],
    scheme: object,
) -> GrainAggregationReport:
    dataset_names = tuple(item.label for item in inputs)
    group_names = tuple(sorted(
        dict.fromkeys(item.group_name for item in inputs),
        key=natural_sort_key,
    ))
    metrics_by_dataset = {
        item.label: _grain_metrics_for_dataset(item.dataset, scheme)
        for item in inputs
    }
    class_by_dataset = {
        item.label: _classification_label(item.dataset, scheme)
        for item in inputs
    }

    by_dataset = {
        item.label: _grain_stats_for(
            item.label,
            [item.label],
            metrics_by_dataset,
            class_by_dataset,
        )
        for item in inputs
    }

    names_by_group: dict[str, list[str]] = defaultdict(list)
    for item in inputs:
        names_by_group[item.group_name].append(item.label)

    by_group = {
        group: _grain_stats_for(group, names, metrics_by_dataset, class_by_dataset)
        for group, names in names_by_group.items()
    }

    overall = _grain_stats_for("All selected", list(dataset_names), metrics_by_dataset, class_by_dataset)
    return GrainAggregationReport(
        dataset_names=dataset_names,
        group_names=group_names,
        by_dataset=by_dataset,
        by_group=by_group,
        overall=overall,
    )


def _grain_stats_for(
    scope_name: str,
    dataset_names: Sequence[str],
    metrics_by_dataset: Mapping[str, Mapping[str, Optional[float]]],
    class_by_dataset: Mapping[str, str],
) -> GrainAggregateStats:
    metric_names = ("D10", "D50", "D60", "Dmean", "Cu", "Cc", "Fines%")
    metric_stats = {
        name: _metric_stats(name, [metrics_by_dataset.get(ds, {}).get(name) for ds in dataset_names])
        for name in metric_names
    }
    class_counts = Counter(
        label for label in (class_by_dataset.get(ds, "N/A") for ds in dataset_names)
        if label and label != "N/A"
    )
    dominant_class = class_counts.most_common(1)[0][0] if class_counts else "N/A"
    return GrainAggregateStats(
        scope_name=scope_name,
        dataset_names=tuple(dataset_names),
        dataset_count=len(tuple(dataset_names)),
        metrics=metric_stats,
        class_counts=dict(class_counts),
        dominant_class=dominant_class,
    )


def _metric_stats(name: str, raw_values: Iterable[Optional[float]]) -> GrainMetricStats:
    values = [float(value) for value in raw_values if value is not None]
    if not values:
        return GrainMetricStats(name=name)
    return GrainMetricStats(
        name=name,
        value_count=len(values),
        arithmetic_mean=statistics.fmean(values),
        median=statistics.median(values),
        min_value=min(values),
        max_value=max(values),
        std_dev=statistics.pstdev(values) if len(values) > 1 else 0.0,
    )


def _grain_metrics_for_dataset(dataset: object, scheme: object) -> dict[str, Optional[float]]:
    return {
        "D10": _call_optional(dataset, "get_d10"),
        "D50": _call_optional(dataset, "get_d50"),
        "D60": _call_optional(dataset, "get_d60"),
        "Dmean": _call_optional(dataset, "get_arithmetic_mean_grain_size"),
        "Cu": _call_optional(dataset, "get_uniformity_coefficient"),
        "Cc": _call_optional(dataset, "get_coefficient_of_curvature"),
        "Fines%": _fines_pct(dataset, scheme),
    }


def _call_optional(obj: object, method_name: str) -> Optional[float]:
    method = getattr(obj, method_name, None)
    if not callable(method):
        return None
    try:
        value = method()
    except Exception:
        return None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _fines_pct(dataset: object, scheme: object) -> Optional[float]:
    try:
        sizes = list(getattr(dataset, "particle_sizes", []) or [])
        passing = list(getattr(dataset, "percent_passing", []) or [])
        target = getattr(scheme, "silt_max", ISO14688.silt_max)
        value = interpolate_at(sizes, passing, target)
        return float(value) if value is not None else None
    except Exception:
        return None


def _classification_label(dataset: object, scheme: object) -> str:
    classify = getattr(dataset, "classify", None)
    if not callable(classify):
        return "N/A"
    try:
        result = classify(scheme=scheme)
        return str(getattr(result, "label", "") or getattr(result, "primary_type", "") or "N/A")
    except Exception:
        return "N/A"
