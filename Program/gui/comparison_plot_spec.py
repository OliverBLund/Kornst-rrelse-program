"""Widget-free comparison-plot rendering pipeline.

This module owns the comparison "what to draw" logic that used to live inside
``ComparisonPlotWidget``.  A :class:`ComparisonPlotSpec` carries the *resolved*
presentation (datasets, colours, line styles, units, options) so the renderer
needs no Qt, no ``group_styles``/``QSettings`` lookups, and no theme import.

``render_comparison(figure, spec)`` draws onto any matplotlib ``Figure`` — the
interactive ``ComparisonPlotWidget`` renders onto its Qt canvas, while headless
report/export code renders onto an Agg figure → byte-identical output.

The widget keeps everything stateful (interactions, drawer, sidebar, canvas
height, export); it builds a spec and hands it here.  ``render_comparison``
returns the number of faceted grid rows used (``0`` for single/overlay plots)
so the widget can grow its scroll canvas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
from matplotlib.patches import Patch

from .plot_renderers import (
    build_legend_kwargs,
    render_distribution_groups,
    render_distribution_overlay,
    render_k_distribution_function,
    render_k_histogram,
    render_k_overlay,
)
from .plot_styles import PlotStyle, PROFESSIONAL_STYLE
from .plot_constants import METHOD_COLORS, ordered_methods
from .k_plot_helpers import (
    apply_linear_bar_limits,
    apply_log_bar_limits,
    format_method_label,
)
from k_aggregation import UNGROUPED_LABEL
from grain_classification import ISO14688, compute_detailed_fractions
from unit_conversions import (
    HydraulicConductivityConverter,
    HydraulicConductivityUnit,
    get_default_plot_unit,
)


# Theme colours, duplicated as literals so this module stays widget-free (the
# ``theme`` module imports PyQt6/qtawesome).  Keep in sync with theme.C.
_FACET_OVERFLOW_COLOR = "#9a8c78"   # C.TEXT_MUTED
_GROUP_LEGEND_FALLBACK = "#5d4e37"  # C.TEXT_MID


@dataclass
class ComparisonPlotSpec:
    """Resolved, Qt-free description of a comparison plot to render.

    Built by ``ComparisonPlotWidget._build_spec`` (and, in later increments, by
    report/export capture code).  All presentation is pre-resolved so the
    renderer is a pure function of this spec.
    """

    # ── Data ────────────────────────────────────────────────────────
    datasets: List[Any] = field(default_factory=list)
    k_results_dict: Dict[str, Dict[str, float]] = field(default_factory=dict)  # m/s
    flagged_methods_dict: Dict[str, set] = field(default_factory=dict)
    comparison_snapshot: Optional[Any] = None

    # ── Plot selection / layout ─────────────────────────────────────
    current_plot_type: str = "distribution"
    display_mode: str = "overlay"  # overlay | grid
    histogram_layout: str = "bars"  # bars | heatmap
    dense_report_layout: bool = False
    automatic_report_legend_layout: bool = False
    use_group_breakdown: bool = False
    grid_cols: int = 2
    max_facet_panels: int = 16

    # ── Resolved presentation ───────────────────────────────────────
    dataset_groups: Dict[str, str] = field(default_factory=dict)
    group_color_map: Dict[str, str] = field(default_factory=dict)
    effective_colors: List[str] = field(default_factory=list)       # by dataset order
    color_by_name: Dict[str, str] = field(default_factory=dict)
    dataset_linestyles: Dict[str, str] = field(default_factory=dict)  # by sample name
    palette: List[str] = field(default_factory=list)                  # categorical fallback
    palette_authoritative: bool = False                               # palette should recolour single-unit plots
    known_dataset_order: List[str] = field(default_factory=list)
    known_group_order: List[str] = field(default_factory=list)
    known_dataset_group: Dict[str, str] = field(default_factory=dict)

    # ── Style / options ─────────────────────────────────────────────
    style: PlotStyle = field(default_factory=lambda: PROFESSIONAL_STYLE)
    show_grid: bool = True
    show_legend: bool = True
    log_k_y_scale: bool = False
    display_unit: HydraulicConductivityUnit = field(default_factory=get_default_plot_unit)
    k_group_aggregation: str = "geometric"  # geometric | arithmetic

    classification_scheme: Any = field(default_factory=lambda: ISO14688)

    # ── K Distribution sub-view ─────────────────────────────────────
    # The lognormal histogram is the default view (the empirical CDF is the
    # opt-in alternative); see render_k_histogram for the frequency/N/collapse
    # semantics carried by the three options below.
    k_dist_view: str = "histogram"   # histogram | cdf
    k_hist_axis: str = "lnk"         # lnk | k
    k_hist_bins: str = "auto"        # auto | off | digit string
    k_hist_y_mode: str = "frequency"  # frequency (counts) | density
    k_hist_show_n: bool = True        # annotate each bar with its count
    k_hist_drop_empty: bool = True    # collapse all-empty interior bins


# ═══════════════════════════════════════════════════════════════════
# Public entry point
# ═══════════════════════════════════════════════════════════════════

def render_comparison(figure, spec: ComparisonPlotSpec) -> int:
    """Draw *spec* onto *figure*; return the grid row count (0 = no scroll grow).

    Single-axes / overlay plots return ``0``; faceted grids return their row
    count so the caller can size a scroll canvas.
    """
    figure.clear()
    plot_type = spec.current_plot_type

    if plot_type == "distribution":
        return _plot_distribution(figure, spec)
    if plot_type == "k-values":
        return _plot_k_values(figure, spec)
    if plot_type == "k-distribution":
        return _plot_k_distribution(figure, spec)
    if plot_type == "combined":
        return _plot_combined(figure, spec)
    if plot_type == "histogram":
        return _plot_histogram(figure, spec)
    return 0


# ═══════════════════════════════════════════════════════════════════
# Unit / conversion helpers
# ═══════════════════════════════════════════════════════════════════

def unit_symbol(spec: ComparisonPlotSpec) -> str:
    return HydraulicConductivityConverter.UNIT_SYMBOLS[spec.display_unit]


def k_axis_label(spec: ComparisonPlotSpec) -> str:
    return f"Hydraulic Conductivity K ({unit_symbol(spec)})"


def convert_k_value(spec: ComparisonPlotSpec, value_m_s: Optional[float]) -> Optional[float]:
    if value_m_s is None:
        return None
    return HydraulicConductivityConverter.convert_from_m_per_s(value_m_s, spec.display_unit)


def convert_k_dict(spec: ComparisonPlotSpec, k_dict: Dict[str, float]) -> Dict[str, float]:
    converted: Dict[str, float] = {}
    for method, value in k_dict.items():
        display_value = convert_k_value(spec, value)
        if display_value is not None:
            converted[method] = display_value
    return converted


def display_k_results_dict(spec: ComparisonPlotSpec) -> Dict[str, Dict[str, float]]:
    return {
        name: convert_k_dict(spec, k_dict)
        for name, k_dict in spec.k_results_dict.items()
    }


# ═══════════════════════════════════════════════════════════════════
# Presentation helpers (resolved-state, Qt-free)
# ═══════════════════════════════════════════════════════════════════

def _has_named_groups(spec: ComparisonPlotSpec) -> bool:
    """True when at least one plotted dataset carries a real group label."""
    return any(group != UNGROUPED_LABEL for group in spec.dataset_groups.values())


def _series_style_parts(line_style: str) -> tuple[str, Optional[str]]:
    """Return matplotlib ``(linestyle, marker)`` for a stored style key.

    Mirrors ``group_styles.series_style_parts`` (pure string logic) so the
    renderer needs no PyQt6 import via ``group_styles``.
    """
    valid_lines = {"-", "--", ":", "-."}
    valid_markers = {"o", "s", "^", "D"}
    text = str(line_style or "-").strip()
    line_part, marker_part = (text.split("|", 1) + [""])[:2]
    line = line_part if line_part in valid_lines else "-"
    marker = marker_part if marker_part in valid_markers else None
    return line, marker


def _effective_dataset_linestyles(spec: ComparisonPlotSpec) -> List[str]:
    return [spec.dataset_linestyles.get(ds.sample_name, "-") for ds in spec.datasets]


def _effective_dataset_plot_styles(
    spec: ComparisonPlotSpec,
) -> tuple[List[str], List[Optional[str]]]:
    line_styles: list[str] = []
    markers: list[Optional[str]] = []
    for style_key in _effective_dataset_linestyles(spec):
        line_style, marker = _series_style_parts(style_key)
        line_styles.append(line_style)
        markers.append(marker)
    return line_styles, markers


def _ordered_methods(method_names) -> List[str]:
    return ordered_methods(method_names)


def group_order(spec: ComparisonPlotSpec) -> List[str]:
    """Group labels in first-seen dataset order (named groups + Ungrouped)."""
    order: list[str] = []
    for ds in spec.datasets:
        group = spec.dataset_groups.get(ds.sample_name, UNGROUPED_LABEL)
        if group not in order:
            order.append(group)
    return order


def group_overlay_inputs(
    spec: ComparisonPlotSpec,
) -> tuple[Dict[str, Dict[str, float]], List[str], Dict[str, set]]:
    """Per-group K aggregates for the K-Values overlay (in m/s).

    Named groups collapse to one method-mean series each (OK-only, from the
    comparison snapshot); ungrouped datasets stay individual so no scope is
    dropped. Returns parallel ``(results_m_s, colors, flagged_by_scope)``.
    """
    results: Dict[str, Dict[str, float]] = {}
    colors: List[str] = []
    flagged: Dict[str, set] = {}

    snapshot = spec.comparison_snapshot
    buckets: Dict[str, Dict[str, list]] = {}
    if snapshot is not None:
        for record in snapshot.k.included_records:
            if record.group_name == UNGROUPED_LABEL or record.positive_value is None:
                continue
            buckets.setdefault(record.group_name, {}).setdefault(
                record.method_name, []
            ).append(record.positive_value)

    group_names = list(snapshot.k.group_names) if snapshot is not None else []
    palette_fallback = spec.palette[0] if spec.palette else "#1f77b4"
    aggregation_mode = (
        "arithmetic" if spec.k_group_aggregation == "arithmetic" else "geometric"
    )

    def aggregate(values: list[float]) -> float:
        if aggregation_mode == "arithmetic":
            return float(sum(values) / len(values))
        return math.exp(sum(map(math.log, values)) / len(values))

    def emit_group(group_name: str) -> None:
        method_means = {
            method: aggregate(values)
            for method, values in buckets.get(group_name, {}).items()
            if values
        }
        if not method_means:
            return
        results[group_name] = method_means
        colors.append(spec.group_color_map.get(group_name, palette_fallback))
        flagged[group_name] = set()

    for group_name in group_names:
        if group_name != UNGROUPED_LABEL:
            emit_group(group_name)
            continue
        # Expand Ungrouped into its member datasets so each keeps identity.
        for ds in spec.datasets:
            name = ds.sample_name
            if spec.dataset_groups.get(name, UNGROUPED_LABEL) != UNGROUPED_LABEL:
                continue
            k_dict = spec.k_results_dict.get(name)
            if not k_dict:
                continue
            results[name] = dict(k_dict)
            colors.append(spec.color_by_name.get(name, palette_fallback))
            flagged[name] = set(spec.flagged_methods_dict.get(name, set()))

    return results, colors, flagged


def distribution_units(spec: ComparisonPlotSpec) -> list[dict]:
    """Faceting units for distribution plots.

    Per dataset → one single-member unit each. Per group → one multi-member
    unit per named group (members feed the aggregate curve + band), with
    ungrouped datasets kept as individual single-member units.
    """
    color_by_name = spec.color_by_name
    palette_fallback = spec.palette[0] if spec.palette else "#1f77b4"

    def member(ds) -> tuple:
        return (ds.particle_sizes, ds.percent_passing)

    if not spec.use_group_breakdown:
        return [
            {
                "label": ds.sample_name,
                "color": color_by_name.get(ds.sample_name, palette_fallback),
                "members": [member(ds)],
            }
            for ds in spec.datasets
        ]

    units: list[dict] = []
    for group_name in group_order(spec):
        members = [
            ds for ds in spec.datasets
            if spec.dataset_groups.get(ds.sample_name, UNGROUPED_LABEL) == group_name
        ]
        if group_name == UNGROUPED_LABEL:
            units.extend(
                {
                    "label": ds.sample_name,
                    "color": color_by_name.get(ds.sample_name, palette_fallback),
                    "members": [member(ds)],
                }
                for ds in members
            )
        else:
            units.append({
                "label": group_name,
                "color": spec.group_color_map.get(group_name, palette_fallback),
                "members": [member(ds) for ds in members],
            })
    return units


def _k_grid_units(
    spec: ComparisonPlotSpec,
) -> tuple[Dict[str, Dict[str, float]], Dict[str, set]]:
    """Return ``(display_results, flagged_by_scope)`` for K grid facets.

    Honours the breakdown: per-dataset cells use raw per-dataset results;
    per-group cells use the selected group method-mean aggregates.
    """
    if spec.use_group_breakdown:
        results_m_s, _colors, flagged = group_overlay_inputs(spec)
        display = {
            name: convert_k_dict(spec, k_dict)
            for name, k_dict in results_m_s.items()
        }
        return display, flagged
    return display_k_results_dict(spec), spec.flagged_methods_dict


def _group_mean_passing(members) -> tuple[list, list]:
    """Mean % passing across group members on the union of their sizes.

    Each member is interpolated (log-x) onto the shared size union and
    averaged, giving a monotonic aggregate curve whose retained differences
    stay non-negative — safe to feed the histogram helper.
    """
    sizes_set = {
        float(size)
        for sizes, _pcts in members
        for size in sizes
        if size is not None and float(size) > 0
    }
    union = sorted(sizes_set)
    if not union:
        return [], []
    log_grid = np.log10(union)
    stacked = []
    for sizes, pcts in members:
        pairs = sorted(
            (float(s), float(p))
            for s, p in zip(sizes, pcts)
            if s is not None and float(s) > 0 and p is not None
        )
        if len(pairs) < 2:
            continue
        xs = np.log10([s for s, _ in pairs])
        ys = np.array([p for _, p in pairs], dtype=float)
        stacked.append(np.interp(log_grid, xs, ys))
    if not stacked:
        return [], []
    mean_passing = np.mean(np.vstack(stacked), axis=0)
    return union, mean_passing.tolist()


def _scheme_short_name(scheme) -> str:
    if getattr(scheme, "key", "") == "iso14688":
        return "ISO 14688"
    if getattr(scheme, "key", "") == "uscs":
        return "USCS"
    return str(getattr(scheme, "name", None) or "active scheme")


def _calculate_histogram_class_fractions(
    particle_sizes,
    percent_passing,
    scheme=None,
):
    """Convert cumulative percent passing to retained fractions per class."""
    sizes = [] if particle_sizes is None else list(particle_sizes)
    passing = [] if percent_passing is None else list(percent_passing)
    fractions = compute_detailed_fractions(sizes, passing, scheme or ISO14688)
    labels = [fraction.label for fraction in fractions]
    lower = np.array([fraction.lower_mm for fraction in fractions], dtype=float)
    upper = np.array([fraction.upper_mm for fraction in fractions], dtype=float)
    freq = np.array([fraction.pct for fraction in fractions], dtype=float)
    return labels, lower, upper, freq


def histogram_units(spec: ComparisonPlotSpec) -> list[dict]:
    """Faceting units for the grain histogram (per dataset or per group)."""
    color_by_name = spec.color_by_name
    palette_fallback = spec.palette[0] if spec.palette else "#1f77b4"
    dataset_palette = spec.palette or [palette_fallback]
    dataset_order = spec.known_dataset_order or [
        ds.sample_name for ds in spec.datasets
    ]

    def dataset_bar_color(sample_name: str, index: int) -> str:
        if spec.use_group_breakdown:
            return color_by_name.get(sample_name, palette_fallback)
        stable_index = (
            dataset_order.index(sample_name)
            if sample_name in dataset_order
            else index
        )
        return dataset_palette[stable_index % len(dataset_palette)]

    def dataset_unit(ds, index: int) -> dict:
        labels, lower, upper, freq = _calculate_histogram_class_fractions(
            ds.particle_sizes,
            ds.percent_passing,
            spec.classification_scheme,
        )
        return {
            "label": ds.sample_name,
            "color": dataset_bar_color(ds.sample_name, index),
            "class_labels": labels,
            "lower": lower,
            "upper": upper,
            "sizes": upper,
            "freq": freq,
        }

    if not spec.use_group_breakdown:
        return [dataset_unit(ds, i) for i, ds in enumerate(spec.datasets)]

    units: list[dict] = []
    for group_name in group_order(spec):
        members = [
            ds for ds in spec.datasets
            if spec.dataset_groups.get(ds.sample_name, UNGROUPED_LABEL) == group_name
        ]
        if group_name == UNGROUPED_LABEL:
            units.extend(dataset_unit(ds, i) for i, ds in enumerate(members))
            continue
        usizes, mean_passing = _group_mean_passing(
            [(ds.particle_sizes, ds.percent_passing) for ds in members]
        )
        labels, lower, upper, freq = _calculate_histogram_class_fractions(
            usizes,
            mean_passing,
            spec.classification_scheme,
        )
        units.append({
            "label": group_name,
            "color": spec.group_color_map.get(group_name, palette_fallback),
            "class_labels": labels,
            "lower": lower,
            "upper": upper,
            "sizes": upper,
            "freq": freq,
        })
    return units


def combined_facets(spec: ComparisonPlotSpec) -> list[dict]:
    """Faceting units for the combined view: distribution + K per unit.

    Joins each distribution unit to its K values by label: selected group
    method-mean aggregates per group, or raw per-dataset results otherwise.
    """
    if spec.use_group_breakdown:
        k_results_m_s, _colors, flagged_by_scope = group_overlay_inputs(spec)
    else:
        k_results_m_s = spec.k_results_dict
        flagged_by_scope = spec.flagged_methods_dict

    facets: list[dict] = []
    for unit in distribution_units(spec):
        label = unit["label"]
        facets.append({
            "label": label,
            "color": unit["color"],
            "members": unit["members"],
            "k": k_results_m_s.get(label, {}),
            "flagged": flagged_by_scope.get(label, set()),
        })
    return facets


def k_distribution_scopes(spec: ComparisonPlotSpec) -> list[dict]:
    snapshot = spec.comparison_snapshot
    if snapshot is None:
        return []

    records = [
        record for record in snapshot.k.included_records
        if record.positive_value is not None
    ]
    if not records:
        return []

    named_groups = [
        group for group in snapshot.k.group_names
        if group and group != UNGROUPED_LABEL
    ]
    palette = spec.palette or ["#1f77b4"]
    reserved_group_colors = {
        color for color in (
            spec.group_color_map.get(group_name) for group_name in named_groups
        )
        if color
    }
    overall_color = next(
        (color for color in palette if color not in reserved_group_colors),
        palette[0],
    )
    scopes: list[dict] = [{
        "label": "Overall",
        "values": [convert_k_value(spec, record.positive_value) for record in records],
        "color": overall_color,
        "linestyle": "-",
        "is_overall": True,
    }]

    group_palette_offset = 1 if len(palette) > 1 and bool(named_groups) else 0
    for index, group_name in enumerate(named_groups):
        values = [
            convert_k_value(spec, record.positive_value)
            for record in records
            if record.group_name == group_name and record.positive_value is not None
        ]
        if not values:
            continue
        scopes.append({
            "label": group_name,
            "values": values,
            "color": spec.group_color_map.get(
                group_name,
                palette[(index + group_palette_offset) % len(palette)],
            ),
            "linestyle": "-",
            "is_overall": False,
        })
    return scopes


# ═══════════════════════════════════════════════════════════════════
# Faceting / layout helpers
# ═══════════════════════════════════════════════════════════════════

def facet_dims(spec: ComparisonPlotSpec, count: int) -> tuple[int, int, int, int]:
    """Return ``(rows, cols, shown, hidden)`` fitting *count* faceted panels.

    Columns follow the layout selector; rows expand to fit every unit so
    nothing is silently dropped. A soft cap keeps pathological counts readable,
    surfacing the remainder through an overflow note.
    """
    shown = max(0, min(count, spec.max_facet_panels))
    hidden = max(0, count - shown)
    cols = min(max(1, spec.grid_cols), max(shown, 1))
    rows = max(1, math.ceil(max(shown, 1) / cols))
    return rows, cols, shown, hidden


def _draw_facet_overflow_note(figure, hidden: int) -> None:
    """Annotate the figure when the soft panel cap hid some units."""
    if hidden <= 0:
        return
    figure.text(
        0.5, 0.005,
        f"+{hidden} more not shown — narrow the comparison scope to see them",
        ha="center", va="bottom",
        fontsize=8, color=_FACET_OVERFLOW_COLOR, fontstyle="italic",
    )


# ═══════════════════════════════════════════════════════════════════
# Legend / bar styling helpers
# ═══════════════════════════════════════════════════════════════════

def _legend_kwargs(
    spec: ComparisonPlotSpec,
    labels: Optional[List[str]] = None,
    ax=None,
) -> dict:
    """Build legend kwargs from the active PlotStyle (loc/bbox/fontsize honoured)."""
    return build_legend_kwargs(spec.style, labels=labels, ax=ax)


def _style_k_bar(bar, color: str, flagged: bool) -> None:
    """Apply warning styling to flagged K-value bars."""
    if flagged:
        bar.set_facecolor('none')
        bar.set_edgecolor(color)
        bar.set_linewidth(2.0)
        bar.set_hatch('////')
        bar.set_alpha(1.0)
    else:
        bar.set_edgecolor('black')
        bar.set_linewidth(0.5)


def _apply_group_structured_legend(spec: ComparisonPlotSpec, ax) -> None:
    """Re-draw the legend grouped by dataset group: a bold group header followed
    by its indented members; ungrouped series and any non-dataset entries (e.g. a
    flag marker) are listed plainly at the end.
    """
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return

    grouped: dict[str, list[tuple]] = {}
    extras: list[tuple] = []
    for handle, label in zip(handles, labels):
        group = spec.dataset_groups.get(label)
        if group is None:
            extras.append((handle, label))
        else:
            grouped.setdefault(group, []).append((handle, label))

    order = [g for g in spec.known_group_order if g in grouped]
    if UNGROUPED_LABEL in grouped:
        order.append(UNGROUPED_LABEL)

    new_handles: list = []
    new_labels: list[str] = []
    header_rows: list[int] = []
    for group in order:
        members = grouped[group]
        if group != UNGROUPED_LABEL:
            # A filled group-colour swatch as the header handle keeps every row's
            # glyph at the same left edge (an empty handle would leave the header
            # text indented relative to the member line samples).
            group_color = spec.group_color_map.get(group, _GROUP_LEGEND_FALLBACK)
            new_handles.append(Patch(facecolor=group_color, edgecolor="none"))
            new_labels.append(group)
            header_rows.append(len(new_labels) - 1)
        for handle, label in members:
            new_handles.append(handle)
            new_labels.append(label)
    for handle, label in extras:
        new_handles.append(handle)
        new_labels.append(label)

    legend_kwargs = _legend_kwargs(spec, new_labels, ax)
    legend_kwargs["alignment"] = "left"
    legend = ax.legend(new_handles, new_labels, **legend_kwargs)
    for row in header_rows:
        texts = legend.get_texts()
        if row < len(texts):
            texts[row].set_fontweight("bold")


# ═══════════════════════════════════════════════════════════════════
# Empty state
# ═══════════════════════════════════════════════════════════════════

def _draw_empty_state(figure, message: str) -> int:
    """Draw a centred placeholder message; return 0 (no grid growth)."""
    ax = figure.add_subplot(1, 1, 1)
    ax.text(0.5, 0.5, message, transform=ax.transAxes,
            ha='center', va='center', fontsize=12, color='gray')
    ax.set_xticks([])
    ax.set_yticks([])
    return 0


# ═══════════════════════════════════════════════════════════════════
# Distribution
# ═══════════════════════════════════════════════════════════════════

def _plot_distribution(figure, spec: ComparisonPlotSpec) -> int:
    if spec.display_mode == "overlay":
        ax = figure.add_subplot(1, 1, 1)
        if spec.use_group_breakdown:
            _plot_distribution_overlay_groups(ax, spec)
        else:
            _plot_distribution_overlay(ax, spec)
        return 0
    return _plot_distribution_grid(figure, spec)


def _plot_distribution_overlay(ax, spec: ComparisonPlotSpec) -> None:
    """Plot all distributions on single axes via shared renderer.

    When named groups exist (per-dataset breakdown), members share a group
    colour and differ only by line style, so a flat legend reads as repeated
    colours. We then render a group-structured legend instead.
    """
    linestyles, markers = _effective_dataset_plot_styles(spec)
    structured = spec.show_legend and _has_named_groups(spec)
    render_distribution_overlay(
        ax, spec.datasets,
        colors=spec.effective_colors,
        linestyles=linestyles,
        markers=markers,
        style=spec.style,
        show_grid=spec.show_grid,
        show_legend=spec.show_legend and not structured,
    )
    if structured:
        _apply_group_structured_legend(spec, ax)


def _plot_distribution_overlay_groups(ax, spec: ComparisonPlotSpec) -> None:
    """Overlay one aggregate curve + spread band + faint members per group."""
    render_distribution_groups(
        ax, distribution_units(spec),
        style=spec.style,
        show_grid=spec.show_grid,
        show_legend=spec.show_legend,
        title="Grain Size Distribution by Group",
    )


def _plot_distribution_grid(figure, spec: ComparisonPlotSpec) -> int:
    """Plot distributions in a grid — one panel per dataset or per group."""
    units = distribution_units(spec)
    rows, cols, shown, hidden = facet_dims(spec, len(units))

    for i, unit in enumerate(units[:shown]):
        ax = figure.add_subplot(rows, cols, i + 1)
        render_distribution_groups(
            ax, [unit],
            style=spec.style,
            show_grid=spec.show_grid,
            show_legend=False,
            title=unit["label"],
        )
        ax.title.set_fontsize(9)
        ax.set_xlabel('Size (mm)', fontsize=8)
        ax.set_ylabel('% Passing', fontsize=8)
        ax.tick_params(labelsize=7)
    _draw_facet_overflow_note(figure, hidden)
    return rows


# ═══════════════════════════════════════════════════════════════════
# K-values
# ═══════════════════════════════════════════════════════════════════

def _plot_k_values(figure, spec: ComparisonPlotSpec) -> int:
    if not spec.k_results_dict:
        return _draw_empty_state(figure, "No K-values calculated")
    if spec.display_mode == "overlay":
        _plot_k_values_overlay(figure, spec)
        return 0
    return _plot_k_values_grid(figure, spec)


def _plot_k_values_overlay(figure, spec: ComparisonPlotSpec) -> None:
    """Plot K-values as grouped bars via shared renderer.

    When dataset groups exist, each named group collapses to a single
    method-mean bar series (one bar per group per method) so same-group
    members no longer render as indistinguishable same-colour bars.
    """
    ax = figure.add_subplot(1, 1, 1)

    if spec.use_group_breakdown:
        results_m_s, colors, flagged = group_overlay_inputs(spec)
        display = {
            name: convert_k_dict(spec, k_dict)
            for name, k_dict in results_m_s.items()
        }
        render_k_overlay(
            ax, display,
            flagged_methods_dict=flagged,
            colors=colors,
            style=spec.style,
            show_grid=spec.show_grid,
            show_legend=spec.show_legend,
            show_value_labels=True,
            log_y_scale=spec.log_k_y_scale,
            y_label=f"K ({unit_symbol(spec)})",
            title="Hydraulic Conductivity by Group",
        )
        return

    render_k_overlay(
        ax, display_k_results_dict(spec),
        flagged_methods_dict=spec.flagged_methods_dict,
        colors=spec.effective_colors,
        style=spec.style,
        show_grid=spec.show_grid,
        show_legend=spec.show_legend,
        show_value_labels=True,
        log_y_scale=spec.log_k_y_scale,
        y_label=f"K ({unit_symbol(spec)})",
    )


def _plot_k_values_grid(figure, spec: ComparisonPlotSpec) -> int:
    """Plot K-values in a grid — one panel per dataset or per group."""
    display, flagged_by_scope = _k_grid_units(spec)
    rows, cols, shown, hidden = facet_dims(spec, len(display))

    for i, (name, k_dict) in enumerate(display.items()):
        if i >= shown:
            break

        ax = figure.add_subplot(rows, cols, i + 1)

        methods = _ordered_methods(k_dict.keys())
        values = [k_dict[m] for m in methods]
        colors = [METHOD_COLORS.get(m, '#888888') for m in methods]
        flagged_methods = flagged_by_scope.get(name, set())

        bars = ax.bar(range(len(methods)), values, color=colors,
                      alpha=0.8, edgecolor='black', linewidth=0.5)
        ax.set_axisbelow(True)
        for bar, method, color in zip(bars, methods, colors):
            _style_k_bar(bar, color, method in flagged_methods)

        ax.set_title(name, fontsize=9, fontweight='bold')
        ax.set_xlabel('Method', fontsize=8)
        ax.set_ylabel(f"K ({unit_symbol(spec)})", fontsize=8)
        ax.set_xticks(range(len(methods)))
        ax.set_xticklabels(
            [format_method_label(method, tiny=True) for method in methods],
            rotation=45,
            ha='right',
            fontsize=spec.style.tick_fontsize,
            fontfamily=spec.style.font_family,
        )
        if spec.log_k_y_scale:
            apply_log_bar_limits(ax, values)
        else:
            apply_linear_bar_limits(ax, values)
        ax.tick_params(labelsize=spec.style.tick_fontsize)

        if spec.show_grid:
            ax.grid(True, axis='y', alpha=0.3)
    _draw_facet_overflow_note(figure, hidden)
    return rows


# ═══════════════════════════════════════════════════════════════════
# K distribution
# ═══════════════════════════════════════════════════════════════════

def _plot_k_distribution(figure, spec: ComparisonPlotSpec) -> int:
    """Plot aggregate/group empirical distribution functions for K."""
    snapshot = spec.comparison_snapshot
    if not snapshot or not snapshot.k.included_records:
        return _draw_empty_state(figure, "No K-values available for K distribution")

    scopes = k_distribution_scopes(spec)
    if not scopes:
        return _draw_empty_state(
            figure, "No positive K-values available for K distribution"
        )

    ax = figure.add_subplot(1, 1, 1)
    if spec.k_dist_view == "histogram":
        if spec.use_group_breakdown:
            hist_scopes = [s for s in scopes if not s.get("is_overall")] or scopes
        else:
            hist_scopes = [s for s in scopes if s.get("is_overall")] or scopes
        render_k_histogram(
            ax,
            hist_scopes,
            axis=spec.k_hist_axis,
            bins=spec.k_hist_bins,
            y_mode=spec.k_hist_y_mode,
            show_n=spec.k_hist_show_n,
            drop_empty_bins=spec.k_hist_drop_empty,
            unit_symbol=unit_symbol(spec),
            style=spec.style,
            show_grid=spec.show_grid,
            show_legend=spec.show_legend,
            title="K Distribution (lognormal)",
        )
        return 0

    render_k_distribution_function(
        ax,
        scopes,
        style=spec.style,
        show_grid=spec.show_grid,
        show_legend=spec.show_legend,
        x_label=k_axis_label(spec),
        title="K Distribution Function",
    )
    return 0


# ═══════════════════════════════════════════════════════════════════
# Combined
# ═══════════════════════════════════════════════════════════════════

def _plot_combined(figure, spec: ComparisonPlotSpec) -> int:
    """Plot combined distribution + K view, faceted per dataset or per group."""
    facets = combined_facets(spec)
    rows, cols, shown, hidden = facet_dims(spec, len(facets))

    for i, facet in enumerate(facets[:shown]):
        ax1 = figure.add_subplot(rows, cols * 2, i * 2 + 1)
        ax2 = figure.add_subplot(rows, cols * 2, i * 2 + 2)

        # Left — distribution (aggregate + band + faint members for groups).
        render_distribution_groups(
            ax1,
            [{"label": facet["label"], "color": facet["color"], "members": facet["members"]}],
            style=spec.style,
            show_grid=spec.show_grid,
            show_legend=False,
            title=f'{facet["label"]} - Dist',
        )
        ax1.title.set_fontsize(8)
        ax1.set_xlabel('Size (mm)', fontsize=7)
        ax1.set_ylabel('% Pass', fontsize=7)
        ax1.tick_params(labelsize=6)

        # Right — K-values (group geo-mean or per-dataset).
        k_dict = convert_k_dict(spec, facet["k"])
        if k_dict:
            methods = _ordered_methods(k_dict.keys())[:5]  # cap for space
            values = [k_dict[m] for m in methods]
            flagged_methods = facet["flagged"]

            bars = ax2.bar(range(len(methods)), values, alpha=0.8)
            ax2.set_axisbelow(True)
            for bar, method in zip(bars, methods):
                _style_k_bar(
                    bar, METHOD_COLORS.get(method, '#888888'),
                    method in flagged_methods,
                )
            ax2.set_title(f'{facet["label"]} - K', fontsize=8)
            ax2.set_xticks(range(len(methods)))
            ax2.set_xticklabels(
                [format_method_label(method, tiny=True) for method in methods],
                rotation=45,
                fontsize=6,
            )
            ax2.set_ylabel(f"K ({unit_symbol(spec)})", fontsize=7)
            if spec.log_k_y_scale:
                apply_log_bar_limits(ax2, values)
            else:
                apply_linear_bar_limits(ax2, values)
            ax2.tick_params(labelsize=6)
            if spec.show_grid:
                ax2.grid(True, axis='y', alpha=0.3)
        else:
            ax2.text(0.5, 0.5, 'No K-values', transform=ax2.transAxes,
                     ha='center', va='center', fontsize=8)
            ax2.set_xticks([])
            ax2.set_yticks([])
    _draw_facet_overflow_note(figure, hidden)
    return rows


# ═══════════════════════════════════════════════════════════════════
# Histogram
# ═══════════════════════════════════════════════════════════════════

def _histogram_label_order(units: list[dict]) -> list[str]:
    """Stable class-label union for overlaid/grouped histogram comparisons."""
    labels: list[str] = []
    seen: set[str] = set()
    for unit in units:
        for label in unit.get("class_labels", []):
            if label in seen:
                continue
            seen.add(label)
            labels.append(label)
    return labels


def _histogram_freq_for_labels(unit: dict, labels: list[str]) -> list[float]:
    values = {
        str(label): float(value)
        for label, value in zip(unit.get("class_labels", []), unit.get("freq", []))
    }
    return [values.get(label, 0.0) for label in labels]


def _plot_histogram_comparison(
    figure,
    spec: ComparisonPlotSpec,
    units: list[dict],
    style: PlotStyle,
) -> None:
    """Plot class fractions for all selected samples/groups on one axes."""
    ax = figure.add_subplot(1, 1, 1)
    labels = _histogram_label_order(units)
    if not labels:
        ax.text(0.5, 0.5, "No class fractions", transform=ax.transAxes,
                ha="center", va="center", fontsize=style.label_fontsize,
                fontfamily=style.font_family)
        ax.set_axis_off()
        return

    x = np.arange(len(labels), dtype=float)
    count = max(1, len(units))
    width = min(0.82 / count, 0.18)
    offsets = (np.arange(count, dtype=float) - (count - 1) / 2.0) * width
    edge_color = style.curve_markeredgecolor or "black"
    edge_width = max(0.5, float(style.curve_markeredgewidth or 0.5))

    for idx, unit in enumerate(units):
        color = unit.get("color")
        if not color:
            color = spec.palette[idx % len(spec.palette)] if spec.palette else style.curve_color
        ax.bar(
            x + offsets[idx],
            _histogram_freq_for_labels(unit, labels),
            width=width * 0.92,
            color=color,
            alpha=0.88,
            edgecolor=edge_color,
            linewidth=edge_width,
            label=unit.get("label", f"Series {idx + 1}"),
        )

    scope_label = "Group" if spec.use_group_breakdown else "Sample"
    ax.set_facecolor(style.axes_facecolor)
    ax.set_axisbelow(True)
    ax.set_title(
        f"Class fractions by {scope_label.lower()}",
        fontsize=style.title_fontsize,
        fontweight=style.title_fontweight,
        fontfamily=style.font_family,
    )
    ax.set_xlabel(
        f"Grain-size class ({_scheme_short_name(spec.classification_scheme)})",
        fontsize=style.label_fontsize,
        fontfamily=style.font_family,
    )
    ax.set_ylabel(
        "Weight (%)",
        fontsize=style.label_fontsize,
        fontfamily=style.font_family,
    )
    ax.set_xticks(x)
    ax.set_xlim(-0.6, len(labels) - 0.4)
    ax.set_ylim(bottom=0)
    ax.set_xticklabels(
        [label.replace(" ", "\n") for label in labels],
        rotation=0,
        ha="center",
        fontsize=max(6, style.tick_fontsize - 1),
        fontfamily=style.font_family,
    )
    ax.tick_params(axis="y", labelsize=style.tick_fontsize)
    for tick in ax.get_yticklabels():
        tick.set_fontfamily(style.font_family)

    if spec.show_grid and style.grid_show:
        ax.grid(
            True,
            axis="y",
            alpha=style.grid_alpha,
            linestyle=style.grid_linestyle,
            color=style.grid_color,
            linewidth=style.grid_linewidth,
        )
    else:
        ax.grid(False)

    if spec.show_legend and len(units) > 1:
        _handles, legend_labels = ax.get_legend_handles_labels()
        ax.legend(**build_legend_kwargs(style, labels=legend_labels, ax=ax))


def _plot_histogram_heatmap(
    figure,
    spec: ComparisonPlotSpec,
    units: list[dict],
    style: PlotStyle,
) -> None:
    """Plot a compact sample-by-class matrix for large report scopes."""
    ax = figure.add_subplot(1, 1, 1)
    labels = _histogram_label_order(units)
    if not labels:
        ax.text(
            0.5,
            0.5,
            "No class fractions",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=style.label_fontsize,
            fontfamily=style.font_family,
        )
        ax.set_axis_off()
        return

    matrix = np.asarray(
        [_histogram_freq_for_labels(unit, labels) for unit in units],
        dtype=float,
    )
    image = ax.imshow(
        matrix,
        aspect="auto",
        interpolation="nearest",
        cmap="YlGnBu",
        vmin=0.0,
        vmax=100.0,
    )

    scope_label = "Group" if spec.use_group_breakdown else "Sample"
    row_tick_size = style.tick_fontsize
    ax.set_facecolor(style.axes_facecolor)
    ax.set_title(
        f"Class fractions by {scope_label.lower()} "
        f"(heatmap, n={len(units)})",
        fontsize=style.title_fontsize,
        fontweight=style.title_fontweight,
        fontfamily=style.font_family,
    )
    ax.set_xlabel(
        f"Grain-size class ({_scheme_short_name(spec.classification_scheme)})",
        fontsize=style.label_fontsize,
        fontfamily=style.font_family,
    )
    ax.set_ylabel(
        scope_label,
        fontsize=style.label_fontsize,
        fontfamily=style.font_family,
    )
    ax.set_xticks(np.arange(len(labels)))
    if spec.dense_report_layout:
        ax.set_xticklabels(
            labels,
            rotation=30,
            ha="right",
            fontsize=style.tick_fontsize,
            fontfamily=style.font_family,
        )
    else:
        ax.set_xticklabels(
            [label.replace(" ", "\n") for label in labels],
            fontsize=max(6, style.tick_fontsize - 1),
            fontfamily=style.font_family,
        )
    ax.set_yticks(np.arange(len(units)))
    ax.set_yticklabels(
        [unit.get("label", f"Series {idx + 1}") for idx, unit in enumerate(units)],
        fontsize=row_tick_size,
        fontfamily=style.font_family,
    )
    ax.tick_params(axis="both", which="major", length=0)

    if spec.show_grid and style.grid_show:
        ax.set_xticks(np.arange(-0.5, len(labels), 1.0), minor=True)
        ax.set_yticks(np.arange(-0.5, len(units), 1.0), minor=True)
        ax.grid(
            which="minor",
            color=style.figure_facecolor,
            linewidth=max(0.4, style.grid_linewidth),
            alpha=0.9,
        )
        ax.tick_params(which="minor", bottom=False, left=False)

    colorbar = figure.colorbar(image, ax=ax, fraction=0.035, pad=0.025)
    colorbar.set_label(
        "Weight (%)",
        fontsize=style.label_fontsize,
        fontfamily=style.font_family,
    )
    colorbar.ax.tick_params(labelsize=style.tick_fontsize)
    for tick in colorbar.ax.get_yticklabels():
        tick.set_fontfamily(style.font_family)


def _plot_histogram(figure, spec: ComparisonPlotSpec) -> int:
    """Plot grain histogram class fractions."""
    units = histogram_units(spec)
    style = spec.style or PROFESSIONAL_STYLE
    if spec.histogram_layout == "heatmap" and len(units) > 1:
        _plot_histogram_heatmap(figure, spec, units, style)
        return 0
    if spec.display_mode != "grid" and len(units) > 1:
        _plot_histogram_comparison(figure, spec, units, style)
        return 0

    rows, cols, shown, hidden = facet_dims(spec, len(units))

    for i, unit in enumerate(units[:shown]):
        ax = figure.add_subplot(rows, cols, i + 1)
        labels = list(unit.get("class_labels", []))
        freq = unit["freq"]
        single_dataset_histogram = (
            len(units) == 1 and len(spec.datasets) == 1 and not spec.use_group_breakdown
        )
        use_unit_color = not single_dataset_histogram or spec.palette_authoritative
        bar_color = (
            (unit.get("color") or style.curve_color) if use_unit_color else style.curve_color
        )

        ax.bar(
            range(len(labels)),
            freq,
            color=bar_color,
            alpha=0.9,
            edgecolor=style.curve_markeredgecolor or "black",
            linewidth=max(0.5, float(style.curve_markeredgewidth or 0.5)),
        )
        ax.set_facecolor(style.axes_facecolor)
        ax.set_axisbelow(True)

        ax.set_title(
            unit["label"],
            fontsize=style.title_fontsize,
            fontweight=style.title_fontweight,
            fontfamily=style.font_family,
        )
        ax.set_xlabel(
            f'Grain-size class ({_scheme_short_name(spec.classification_scheme)})',
            fontsize=style.label_fontsize,
            fontfamily=style.font_family,
        )
        ax.set_ylabel(
            'Weight (%)',
            fontsize=style.label_fontsize,
            fontfamily=style.font_family,
        )
        if labels:
            ax.set_xticks(range(len(labels)))
            ax.set_xlim(-0.6, len(labels) - 0.4)
            ax.set_xticklabels(
                [label.replace(" ", "\n") for label in labels],
                rotation=0,
                ha='center',
                fontsize=max(6, style.tick_fontsize - 1),
                fontfamily=style.font_family,
            )
        ax.tick_params(labelsize=style.tick_fontsize)
        for tick in ax.get_yticklabels():
            tick.set_fontfamily(style.font_family)

        if spec.show_grid and style.grid_show:
            ax.grid(
                True,
                axis='y',
                alpha=style.grid_alpha,
                linestyle=style.grid_linestyle,
                color=style.grid_color,
                linewidth=style.grid_linewidth,
            )
        else:
            ax.grid(False)
    _draw_facet_overflow_note(figure, hidden)
    return rows
