"""Headless capture of a :class:`ComparisonPlotSpec` for reports/exports.

The interactive ``ComparisonPlotWidget`` resolves its presentation
(group breakdown, group colours, per-dataset line styles, unit) into a
``ComparisonPlotSpec`` via ``_build_spec``.  Reports and headless exports need
the *same* resolved spec but for an arbitrary, freshly-selected set of datasets
(a report plots its own chosen samples, which may differ from the Comparison
tab's live scope).

``build_comparison_spec`` reproduces the widget's first-load resolution from
plain data + the shared ``group_styles`` primitives (the same persisted group
colours / line styles the GUI reads), so the comparison plot in a report or
export matches the Comparison tab's structure and colours.  It is the headless
counterpart to ``ComparisonPlotWidget._build_spec`` referenced in the
report/export plot-parity plan as ``build_comparison_plot_context``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from k_aggregation import UNGROUPED_LABEL, dataset_group_name
from grain_classification import ISO14688

from .comparison_plot_spec import ComparisonPlotSpec
from .group_styles import (
    LINE_STYLE_OPTIONS,
    dataset_line_style,
    dataset_series_key,
    group_color_map,
)
from .plot_constants import DATASET_COLORS, palette_colors
from .plot_styles import PROFESSIONAL_STYLE, PlotStyle
from unit_conversions import HydraulicConductivityUnit, get_default_plot_unit


def _k_inputs_from_results(
    datasets: Sequence[Any],
    results_by_name: Mapping[str, Sequence[Any]],
) -> tuple[Dict[str, Dict[str, float]], Dict[str, set]]:
    """Build ``{name: {method: k_m_s}}`` + flagged sets (mirrors the widget).

    Only positive K values are plotted; a method is flagged when its status is
    not OK or its conditions are unmet — identical to
    ``ComparisonPlotWidget.set_datasets``.
    """
    k_results_dict: Dict[str, Dict[str, float]] = {}
    flagged_methods_dict: Dict[str, set] = {}
    for dataset in datasets:
        name = dataset.sample_name
        results = results_by_name.get(name) or []
        k_dict: Dict[str, float] = {}
        flagged: set = set()
        for result in results:
            if result.k_value is not None and result.k_value > 0:
                k_dict[result.method_name] = result.k_value
            status_value = getattr(result.status, "value", str(result.status))
            if status_value != "OK" or not getattr(result, "conditions_met", True):
                flagged.add(result.method_name)
        if k_dict:
            k_results_dict[name] = k_dict
            flagged_methods_dict[name] = flagged
    return k_results_dict, flagged_methods_dict


def build_comparison_spec(
    datasets: Sequence[Any],
    results_by_name: Optional[Mapping[str, Sequence[Any]]] = None,
    *,
    comparison_snapshot: Any = None,
    dataset_groups: Optional[Mapping[str, str]] = None,
    current_plot_type: str = "distribution",
    display_mode: str = "overlay",
    breakdown: Optional[str] = None,  # None = auto | "group" | "dataset"
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_grid: bool = True,
    show_legend: bool = True,
    log_k_y_scale: bool = False,
    display_unit: Optional[HydraulicConductivityUnit] = None,
    classification_scheme: Any = None,
    palette: Optional[Sequence[str]] = None,
    palette_name: Optional[str] = None,
    group_palette_authoritative: bool = False,
    grid_cols: int = 2,
    k_dist_view: str = "histogram",
    k_hist_axis: str = "lnk",
    k_hist_bins: str = "auto",
    k_hist_y_mode: str = "frequency",
    k_hist_show_n: bool = True,
    k_hist_drop_empty: bool = True,
) -> ComparisonPlotSpec:
    """Resolve a :class:`ComparisonPlotSpec` for a fresh dataset selection.

    *datasets* are ``GrainSizeData``-like objects (``sample_name``,
    ``particle_sizes``, ``percent_passing``, optional ``group_name``).
    *results_by_name* maps a dataset's ``sample_name`` to its
    ``KCalculationResult`` list (m/s).  Group colours and line styles come from
    the shared ``group_styles`` store, so the spec matches the GUI defaults.

    *dataset_groups* optionally overrides group membership (``sample_name`` →
    group); when omitted, each dataset's own ``group_name`` is used.  Reports
    assign groups per selected sample, which can differ from the intrinsic
    ``dataset.group_name``.
    """
    style = style or PROFESSIONAL_STYLE
    display_unit = display_unit or get_default_plot_unit()
    palette_list: List[str] = list(palette) if palette else list(DATASET_COLORS)
    palette_fallback = palette_list[0] if palette_list else "#1f77b4"
    results_by_name = results_by_name or {}

    k_results_dict, flagged_methods_dict = _k_inputs_from_results(datasets, results_by_name)

    # ── Group membership + first-seen ordering (fresh build) ────────
    dataset_groups_resolved: Dict[str, str] = {}
    dataset_style_keys: Dict[str, str] = {}
    known_dataset_order: List[str] = []
    known_group_order: List[str] = []
    known_dataset_group: Dict[str, str] = {}
    for dataset in datasets:
        name = dataset.sample_name
        if dataset_groups is not None and name in dataset_groups:
            group_name = dataset_groups[name] or UNGROUPED_LABEL
        else:
            group_name = dataset_group_name(dataset)
        dataset_groups_resolved[name] = group_name
        dataset_style_keys[name] = dataset_series_key(dataset)
        known_dataset_group[name] = group_name
        if name not in known_dataset_order:
            known_dataset_order.append(name)
        if group_name != UNGROUPED_LABEL and group_name not in known_group_order:
            known_group_order.append(group_name)

    # Sample the colormap to the number of GROUPS so the groups spread across the
    # full palette. Sampling to the (larger) dataset count would cram every group
    # into the first slice of the map — e.g. 7 groups among 20 datasets all landing
    # in viridis's dark-purple/blue end. Categorical/legacy keep the flat list.
    if palette_name and known_group_order:
        group_palette = palette_colors(palette_name, len(known_group_order))
    else:
        group_palette = palette_list

    # A non-Categorical report/export palette is authoritative: it re-colours
    # every group from the palette, bypassing persisted Comparison-tab group
    # colour overrides. Categorical (the default) keeps those overrides.
    resolved_group_colors = group_color_map(
        known_group_order, palette=group_palette, include_ungrouped=False,
        ignore_overrides=group_palette_authoritative,
    )

    # ── Per-dataset line styles (group members cycle the style table) ──
    dataset_linestyles: Dict[str, str] = {}
    for dataset in datasets:
        name = dataset.sample_name
        group_name = dataset_groups_resolved.get(name, UNGROUPED_LABEL)
        if group_name == UNGROUPED_LABEL:
            dataset_linestyles[name] = "-"
            continue
        members = [n for n in known_dataset_order if known_dataset_group.get(n) == group_name]
        member_index = members.index(name) if name in members else 0
        default_style = LINE_STYLE_OPTIONS[member_index % len(LINE_STYLE_OPTIONS)][0]
        dataset_linestyles[name] = dataset_line_style(dataset_style_keys[name], default_style)

    def effective_color(name: str, index: int) -> str:
        group_name = dataset_groups_resolved.get(name, UNGROUPED_LABEL)
        if group_name != UNGROUPED_LABEL and group_name in resolved_group_colors:
            return resolved_group_colors[group_name]
        stable_index = (
            known_dataset_order.index(name) if name in known_dataset_order else index
        )
        return palette_list[stable_index % len(palette_list)] if palette_list else palette_fallback

    effective_colors = [
        effective_color(dataset.sample_name, i) for i, dataset in enumerate(datasets)
    ]
    color_by_name = {
        dataset.sample_name: effective_colors[i] for i, dataset in enumerate(datasets)
    }

    has_named_groups = any(
        group != UNGROUPED_LABEL for group in dataset_groups_resolved.values()
    )
    if breakdown == "dataset":
        use_group_breakdown = False
    else:  # "group" or auto
        use_group_breakdown = has_named_groups

    return ComparisonPlotSpec(
        datasets=list(datasets),
        k_results_dict=k_results_dict,
        flagged_methods_dict=flagged_methods_dict,
        comparison_snapshot=comparison_snapshot,
        current_plot_type=current_plot_type,
        display_mode=display_mode,
        use_group_breakdown=use_group_breakdown,
        grid_cols=grid_cols,
        dataset_groups=dataset_groups_resolved,
        group_color_map=resolved_group_colors,
        effective_colors=effective_colors,
        color_by_name=color_by_name,
        dataset_linestyles=dataset_linestyles,
        palette=palette_list,
        palette_authoritative=group_palette_authoritative,
        known_dataset_order=known_dataset_order,
        known_group_order=known_group_order,
        known_dataset_group=known_dataset_group,
        style=style,
        show_grid=show_grid,
        show_legend=show_legend,
        log_k_y_scale=log_k_y_scale,
        display_unit=display_unit,
        classification_scheme=classification_scheme or ISO14688,
        k_dist_view=k_dist_view,
        k_hist_axis=k_hist_axis,
        k_hist_bins=k_hist_bins,
        k_hist_y_mode=k_hist_y_mode,
        k_hist_show_n=k_hist_show_n,
        k_hist_drop_empty=k_hist_drop_empty,
    )
