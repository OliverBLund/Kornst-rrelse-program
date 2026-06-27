"""Shared plot vocabulary for Report and Export tabs.

The report/export UI and export manager all need the same facts about a plot
type: its key, label, scope, file suffix, and whether it supports breakdowns.
Keeping those facts here prevents one path from silently gaining or losing a
plot that another path still knows about.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


PlotScope = Literal["single", "collection"]


@dataclass(frozen=True)
class PlotTypeSpec:
    key: str
    scope: PlotScope
    icon: str
    report_label: str
    export_label: str
    source_label: str
    file_suffix: str
    report_default: bool = False
    export_default: bool = False
    report_breakdown: bool = False
    exportable: bool = True


PLOT_TYPE_SPECS: tuple[PlotTypeSpec, ...] = (
    PlotTypeSpec(
        key="grain_size_curve",
        scope="single",
        icon="fa6s.chart-line",
        report_label="Grain size distribution",
        export_label="Grain size curve",
        source_label="Curve data: particle size + percent passing",
        file_suffix="plot",
        report_default=True,
        export_default=True,
    ),
    PlotTypeSpec(
        key="k_value_bar",
        scope="single",
        icon="fa6s.bolt",
        report_label="K-value bar chart",
        export_label="K-value bar chart",
        source_label="K table: method, K value, warning status",
        file_suffix="k_values",
        report_default=True,
    ),
    PlotTypeSpec(
        key="applicability_heatmap",
        scope="single",
        icon="fa6s.table-cells",
        report_label="Method applicability heatmap",
        export_label="Applicability heatmap",
        source_label="Method status table",
        file_suffix="applicability",
    ),
    PlotTypeSpec(
        key="distribution_overlay",
        scope="collection",
        icon="fa6s.chart-area",
        report_label="Grain size comparison",
        export_label="Distribution overlay",
        source_label="Curve data from all selected datasets",
        file_suffix="distribution_overlay",
        report_default=True,
        report_breakdown=True,
    ),
    PlotTypeSpec(
        key="k_value_comparison",
        scope="collection",
        icon="fa6s.bolt",
        report_label="K-value comparison (bars)",
        export_label="K-value comparison",
        source_label="K table from all selected datasets",
        file_suffix="k_value_comparison",
        report_default=True,
        report_breakdown=True,
    ),
    PlotTypeSpec(
        key="statistical_boxplots",
        scope="collection",
        icon="fa6s.chart-column",
        report_label="K distribution (box plots)",
        export_label="Overall/group K boxplot",
        source_label="Included K values grouped by overall/group scope",
        file_suffix="k_value_boxplot",
        report_default=True,
    ),
    PlotTypeSpec(
        key="k_distribution",
        scope="collection",
        icon="fa6s.chart-area",
        report_label="K distribution (lognormal)",
        export_label="K distribution (lognormal)",
        source_label="Pooled K values fitted to a lognormal distribution",
        file_suffix="k_distribution",
        report_breakdown=True,
    ),
    PlotTypeSpec(
        key="reliability_matrix",
        scope="collection",
        icon="fa6s.table-cells",
        report_label="Method reliability matrix",
        export_label="Reliability matrix",
        source_label="Method status matrix",
        file_suffix="reliability_matrix",
    ),
    PlotTypeSpec(
        key="per_sample_grain",
        scope="collection",
        icon="fa6s.chart-line",
        report_label="Per-sample grain curves",
        export_label="Per-sample grain curves",
        source_label="Individual grain-size curves embedded in a report",
        file_suffix="per_sample_grain",
        exportable=False,
    ),
    PlotTypeSpec(
        key="per_sample_kbar",
        scope="collection",
        icon="fa6s.bolt",
        report_label="Per-sample K-value bars",
        export_label="Per-sample K-value bars",
        source_label="Individual K-value bars embedded in a report",
        file_suffix="per_sample_kbar",
        exportable=False,
    ),
)

PLOT_SPECS_BY_KEY = {spec.key: spec for spec in PLOT_TYPE_SPECS}


def plot_spec(key: str) -> PlotTypeSpec:
    return PLOT_SPECS_BY_KEY[key]


def report_plot_rows(scope: PlotScope) -> list[tuple[str, str, str, bool, bool]]:
    return [
        (
            spec.key,
            spec.icon,
            spec.report_label,
            spec.report_default,
            spec.report_breakdown,
        )
        for spec in PLOT_TYPE_SPECS
        if spec.scope == scope
    ]


def export_plot_keys(scope: PlotScope | None = None) -> tuple[str, ...]:
    return tuple(
        spec.key for spec in PLOT_TYPE_SPECS
        if spec.exportable and (scope is None or spec.scope == scope)
    )


def selected_export_plot_keys(items: dict) -> list[str]:
    return [key for key in export_plot_keys() if items.get(key, False)]


def export_plot_items(defaults: dict[str, bool] | None = None) -> dict[str, bool]:
    default_map = defaults or {}
    return {
        spec.key: bool(default_map.get(spec.key, spec.export_default))
        for spec in PLOT_TYPE_SPECS
        if spec.exportable
    }


def plot_file_suffix(key: str) -> str:
    return PLOT_SPECS_BY_KEY.get(key, PlotTypeSpec(
        key=key,
        scope="collection",
        icon="",
        report_label=key,
        export_label=key,
        source_label="Plot source data",
        file_suffix=key,
    )).file_suffix


def plot_label(key: str, *, for_export: bool = True) -> str:
    spec = PLOT_SPECS_BY_KEY.get(key)
    if spec is None:
        return key.replace("_", " ").title()
    return spec.export_label if for_export else spec.report_label


def plot_source_label(key: str) -> str:
    spec = PLOT_SPECS_BY_KEY.get(key)
    return spec.source_label if spec is not None else "Plot source data"


def plot_keys_for_scope(keys: Iterable[str], scope: PlotScope) -> list[str]:
    allowed = set(export_plot_keys(scope))
    return [key for key in keys if key in allowed]
