"""Pure matplotlib rendering functions for grain-size and K-value plots.

Every function in this module draws onto a provided ``matplotlib.axes.Axes``
(or ``Figure``).  There are **no** QWidget dependencies, so the same code
can be called from:

* the interactive ``PlotWidget`` / ``ComparisonPlotWidget`` (via the Qt
  canvas), and
* the headless ``plot_export`` module (via the Agg backend for report
  generation).
"""

from __future__ import annotations

import math
import warnings
from typing import Dict, List, Mapping, Optional, Sequence, Set

import numpy as np
from matplotlib.axes import Axes
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from .plot_styles import PlotStyle, PROFESSIONAL_STYLE
from .plot_constants import (
    METHOD_COLORS,
    DATASET_COLORS,
    classify_k_status,
    ordered_methods,
)
from .k_plot_helpers import (
    annotate_linear_bars,
    annotate_log_bars,
    apply_linear_bar_limits,
    apply_log_bar_limits,
    format_method_label,
)

# ── Classification-zone colours (duplicated from theme.C to avoid a
#    PyQt6 import — this module must stay widget-free) ─────────────
_GC_CLAY   = "#7a9bbd"
_GC_SILT   = "#b09870"
_GC_SAND   = "#d4b86a"
_GC_GRAVEL = "#a09080"
_GC_COBBLE = "#807870"

_DIST_X_PAD = 2.5
_DIST_Y_MAX = 102.0


# ═══════════════════════════════════════════════════════════════════
# Distribution curve (single sample)
# ═══════════════════════════════════════════════════════════════════

def render_grain_size_distribution(
    ax: Axes,
    particle_sizes: Sequence[float],
    percent_passing: Sequence[float],
    *,
    sample_name: str = "Sample",
    grain_size_data=None,
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_d_lines: bool = True,
    show_markers: bool = True,
    show_grid: bool = True,
    show_legend: bool = True,
    show_classification_zones: bool = False,
    classification_scheme=None,
    fill_curve: bool = False,
    fill_zone_labels: bool = False,
    title: Optional[str] = None,
    show_title: bool = True,
    x_label: str = "Grain Diameter (mm)",
    y_label: str = "Cumulative % Passing",
    show_x_label: bool = True,
    show_y_label: bool = True,
) -> None:
    """Draw a single-sample grain size distribution curve on *ax*."""

    # Axis limits ─────────────────────────────────────────────────
    x_min, x_max, y_min, y_max = _distribution_limits(
        particle_sizes, percent_passing, classification_scheme,
    )
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)

    # Classification zones ────────────────────────────────────────
    if show_classification_zones and classification_scheme is not None:
        _draw_classification_zones(ax, classification_scheme)

    # Curve ───────────────────────────────────────────────────────
    marker = style.curve_marker if show_markers else None
    ax.semilogx(
        particle_sizes,
        percent_passing,
        color=style.curve_color,
        linewidth=style.curve_linewidth,
        label=sample_name,
        marker=marker,
        markersize=style.curve_markersize,
        markeredgecolor=style.curve_markeredgecolor,
        markeredgewidth=style.curve_markeredgewidth,
    )
    if fill_curve:
        ax.fill_between(particle_sizes, percent_passing, 0,
                         color=style.curve_color, alpha=0.12)
        if fill_zone_labels and grain_size_data is not None and classification_scheme is not None:
            _draw_fill_zone_labels(ax, particle_sizes, percent_passing,
                                   grain_size_data, classification_scheme)

    # D-lines ─────────────────────────────────────────────────────
    if show_d_lines:
        _draw_characteristic_lines(ax, particle_sizes, percent_passing,
                                   grain_size_data, style)

    # Labels & formatting ─────────────────────────────────────────
    ax.set_xlabel(x_label if show_x_label else "",
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_ylabel(y_label if show_y_label else "",
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    if show_title:
        ax.set_title(title or f"Grain Size Distribution: {sample_name}",
                     fontsize=style.title_fontsize,
                     fontweight=style.title_fontweight,
                     fontfamily=style.font_family)
    else:
        ax.set_title("")

    _apply_grid(ax, style, show_grid)
    ax.set_facecolor(style.axes_facecolor)
    ax.tick_params(labelsize=style.tick_fontsize)

    if show_legend:
        _apply_styled_legend(ax, style)


# ═══════════════════════════════════════════════════════════════════
# K-value bar chart (single sample)
# ═══════════════════════════════════════════════════════════════════

def render_k_bar_chart(
    ax: Axes,
    methods: Sequence[str],
    k_values: Sequence[float],
    *,
    flagged_methods: Set[str] = frozenset(),
    reference_values: Optional[Sequence[float]] = None,
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_grid: bool = True,
    show_legend: bool = True,
    show_reference_lines: bool = True,
    show_value_labels: bool = True,
    log_y_scale: bool = False,
    title: Optional[str] = None,
    y_label: str = "Hydraulic Conductivity K (m/s)",
    sample_name: str = "Sample",
    tick_fontsize_override: Optional[float] = None,
    value_label_fontsize: float = 8.0,
    colors: Optional[Sequence[str]] = None,
) -> None:
    """Draw a K-value bar chart on *ax*.

    *methods* and *k_values* must be parallel sequences (already
    converted to display units if required).  ``reference_values`` can be used
    for the OK-only population behind the mean reference lines while still
    drawing warning/error bars in the chart. *colors* (one per method) overrides
    the bar colours entirely — reports/exports pass palette colours so the colour
    follows the global palette, not the preset; when omitted the preset's
    method-specific / flat colouring applies (the live GUI tabs).
    """
    if not methods:
        return

    x_pos = np.arange(len(methods))

    # Colours ─────────────────────────────────────────────────────
    if colors is not None:
        colors = list(colors)
    elif style.use_method_specific_colors:
        colors = [METHOD_COLORS.get(m, "#888888") for m in methods]
    else:
        colors = [
            style.k_bar_flagged_color if m in flagged_methods
            else style.k_bar_valid_color
            for m in methods
        ]

    bars = ax.bar(x_pos, k_values, color=colors, alpha=0.8)
    ax.set_axisbelow(True)

    for bar, method, color in zip(bars, methods, colors):
        _style_k_bar(bar, method, color, flagged_methods)

    # Axis formatting ─────────────────────────────────────────────
    tick_fs = tick_fontsize_override or style.tick_fontsize
    ax.set_xlabel("Calculation Method",
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_ylabel(y_label,
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_title(title or f"K-Value Comparison: {sample_name}",
                 fontsize=style.title_fontsize,
                 fontweight=style.title_fontweight,
                 fontfamily=style.font_family)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(
        [format_method_label(m, compact=True) for m in methods],
        rotation=45, ha="right", fontsize=tick_fs,
    )
    ax.set_facecolor(style.axes_facecolor)
    ax.tick_params(labelsize=tick_fs)
    if log_y_scale:
        apply_log_bar_limits(ax, k_values)
    else:
        apply_linear_bar_limits(ax, k_values)

    if show_grid and style.grid_show:
        ax.grid(True, axis="y", alpha=style.grid_alpha,
                linestyle=style.grid_linestyle, color=style.grid_color,
                linewidth=style.grid_linewidth)

    # Reference lines ─────────────────────────────────────────────
    reference_source = k_values if reference_values is None else reference_values
    positive = [v for v in reference_source if v and v > 0]
    if show_reference_lines and positive:
        arithmetic_mean = float(np.mean(positive))
        geometric_mean = float(np.exp(np.mean(np.log(positive))))
        ax.axhline(arithmetic_mean, color=style.k_mean_arith_color, linestyle="-", alpha=0.62,
                   label=f"Arithmetic mean: {arithmetic_mean:.2e}")
        ax.axhline(geometric_mean, color=style.k_mean_geo_color, linestyle="--", alpha=0.68,
                   label=f"Geometric mean: {geometric_mean:.2e}")

    # Bar labels ──────────────────────────────────────────────────
    if show_value_labels:
        labels = [f"{v:.1e}" if v and v > 0 else "" for v in k_values]
        if log_y_scale:
            annotate_log_bars(ax, bars, labels, fontsize=value_label_fontsize)
        else:
            annotate_linear_bars(ax, bars, labels, fontsize=value_label_fontsize)

    # Legend ───────────────────────────────────────────────────────
    if show_legend:
        _add_k_status_legend(ax, flagged_methods, style)


# ═══════════════════════════════════════════════════════════════════
# Distribution overlay (multi-sample)
# ═══════════════════════════════════════════════════════════════════

def render_distribution_overlay(
    ax: Axes,
    datasets,
    *,
    labels: Optional[List[str]] = None,
    colors: Optional[List[str]] = None,
    linestyles: Optional[List[str]] = None,
    markers: Optional[List[Optional[str]]] = None,
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_grid: bool = True,
    show_legend: bool = True,
    title: str = "Grain Size Distribution Comparison",
) -> None:
    """Draw overlaid grain-size curves for multiple samples."""
    _colors = colors or DATASET_COLORS
    _linestyles = linestyles or ["-"]
    _markers = markers or [None]
    _labels = labels or [ds.sample_name for ds in datasets]

    for i, dataset in enumerate(datasets):
        c = _colors[i % len(_colors)]
        ls = _linestyles[i % len(_linestyles)]
        configured_marker = _markers[i % len(_markers)] if _markers else None
        use_marker = len(dataset.particle_sizes) < 20
        ax.semilogx(
            dataset.particle_sizes,
            dataset.percent_passing,
            linewidth=style.curve_linewidth,
            linestyle=ls,
            label=_labels[i],
            color=c,
            marker=configured_marker or ("o" if use_marker else None),
            markersize=style.curve_markersize,
            markeredgecolor="white",
            markeredgewidth=style.curve_markeredgewidth,
        )

    ax.set_xlabel("Grain Size (mm)",
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_ylabel("Percent Passing (%)",
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_title(title, fontsize=style.title_fontsize,
                 fontweight=style.title_fontweight, fontfamily=style.font_family)
    x_min, x_max, y_min, y_max = _overlay_distribution_limits(datasets)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.tick_params(labelsize=style.tick_fontsize)

    _apply_grid(ax, style, show_grid, which="both")

    if show_legend:
        _apply_styled_legend(ax, style)


def _interp_passing_on_grid(sizes, pcts, grid) -> Optional[np.ndarray]:
    """Interpolate one curve's % passing onto a shared log-spaced size grid.

    Values outside the curve's own size range clamp to its end values (the curve
    is monotonic), so members with different sieve sets still align for
    averaging. Returns ``None`` when there are too few usable points.
    """
    pairs = sorted(
        (float(s), float(p))
        for s, p in zip(sizes, pcts)
        if s is not None and float(s) > 0 and p is not None
    )
    if len(pairs) < 2:
        return None
    xs = np.log10([s for s, _ in pairs])
    ys = np.array([p for _, p in pairs], dtype=float)
    return np.interp(np.log10(grid), xs, ys)


def render_distribution_groups(
    ax: Axes,
    groups: Sequence[Mapping],
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_grid: bool = True,
    show_legend: bool = True,
    show_members: bool = True,
    title: str = "Grain Size Distribution by Group",
    grid_points: int = 60,
) -> None:
    """Draw one aggregate curve + min–max spread band + faint members per group.

    *groups*: sequence of mappings with ``label``, ``color`` and ``members``
    (an iterable of ``(particle_sizes, percent_passing)`` pairs). Used for both
    the overlay (all groups on one axes) and the grid·group cell (one group).
    """
    all_sizes: list[float] = []
    all_pcts: list[float] = []
    for group in groups:
        for sizes, pcts in group.get("members", ()):
            for size, pct in zip(sizes, pcts):
                if size is not None and float(size) > 0 and pct is not None:
                    all_sizes.append(float(size))
                    all_pcts.append(float(pct))
    if all_sizes:
        x_min, x_max, y_min, y_max = _distribution_limits(all_sizes, all_pcts)
    else:
        x_min, x_max, y_min, y_max = 0.001, 100.0, 0.0, _DIST_Y_MAX

    grid = np.logspace(math.log10(x_min), math.log10(x_max), grid_points)

    for group in groups:
        color = group.get("color") or "#2b5797"
        label = group.get("label", "Group")
        curves = [
            curve
            for sizes, pcts in group.get("members", ())
            if (curve := _interp_passing_on_grid(sizes, pcts, grid)) is not None
        ]
        if not curves:
            continue
        stacked = np.vstack(curves)
        aggregate = np.nanmean(stacked, axis=0)
        member_count = stacked.shape[0]

        if member_count > 1:
            ax.fill_between(grid, np.nanmin(stacked, axis=0),
                            np.nanmax(stacked, axis=0),
                            color=color, alpha=0.12, zorder=1)
            if show_members:
                for curve in curves:
                    ax.semilogx(grid, curve, color=color, alpha=0.28,
                                linewidth=max(0.6, style.curve_linewidth * 0.5),
                                zorder=2)
        ax.semilogx(grid, aggregate, color=color,
                    linewidth=style.curve_linewidth + 0.4,
                    label=f"{label} (n={member_count})", zorder=3)

    ax.set_xlabel("Grain Size (mm)",
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_ylabel("Percent Passing (%)",
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_title(title, fontsize=style.title_fontsize,
                 fontweight=style.title_fontweight, fontfamily=style.font_family)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.tick_params(labelsize=style.tick_fontsize)
    _apply_grid(ax, style, show_grid, which="both")
    if show_legend:
        _apply_styled_legend(ax, style)


# ═══════════════════════════════════════════════════════════════════
# K-value overlay (multi-sample grouped bars)
# ═══════════════════════════════════════════════════════════════════

def render_k_overlay(
    ax: Axes,
    k_results_dict: Dict[str, Dict[str, float]],
    *,
    flagged_methods_dict: Optional[Dict[str, Set[str]]] = None,
    colors: Optional[List[str]] = None,
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_grid: bool = True,
    show_legend: bool = True,
    show_value_labels: bool = True,
    log_y_scale: bool = False,
    y_label: str = "K (m/s)",
    title: str = "Hydraulic Conductivity Comparison",
) -> None:
    """Draw grouped K-value bars for multiple samples."""
    ax.set_axisbelow(True)
    flagged = flagged_methods_dict or {}
    _colors = colors or DATASET_COLORS

    all_methods: set[str] = set()
    for kd in k_results_dict.values():
        all_methods.update(kd.keys())
    methods = ordered_methods(all_methods)

    n_datasets = len(k_results_dict)
    n_methods = len(methods)
    bar_width = 0.8 / max(n_datasets, 1)

    allow_labels = show_value_labels and n_datasets <= 4 and (n_methods * n_datasets) <= 36
    label_bars: list = []
    label_texts: list[str] = []
    label_levels: list[int] = []
    positive_values: list[float] = []
    has_flagged = False

    for i, (name, k_dict) in enumerate(k_results_dict.items()):
        values = [k_dict.get(m, 0) for m in methods]
        positions = np.arange(n_methods) + i * bar_width
        color = _colors[i % len(_colors)]
        sample_flagged = flagged.get(name, set())

        bars = ax.bar(positions, values, bar_width, label=name,
                      color=color, alpha=0.8, edgecolor="black", linewidth=0.5)
        for bar, method, val in zip(bars, methods, values):
            is_flagged = method in sample_flagged
            has_flagged = has_flagged or is_flagged
            _style_k_bar_simple(bar, color, is_flagged)
            if val > 0:
                positive_values.append(val)
                if allow_labels:
                    label_bars.append(bar)
                    label_texts.append(f"{val:.1e}")
                    label_levels.append(i)

    ax.set_xlabel("Method", fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_ylabel(y_label, fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_title(title, fontsize=style.title_fontsize,
                 fontweight=style.title_fontweight, fontfamily=style.font_family)
    ax.set_xticks(np.arange(n_methods) + bar_width * (n_datasets - 1) / 2)
    ax.set_xticklabels(
        [format_method_label(m, compact=True) for m in methods],
        rotation=45, ha="right", fontsize=8,
    )
    ax.tick_params(axis="y", labelsize=style.tick_fontsize)
    max_label_level = max(label_levels, default=0)
    if log_y_scale:
        apply_log_bar_limits(ax, positive_values, max_label_level=max_label_level)
    else:
        apply_linear_bar_limits(ax, positive_values, max_label_level=max_label_level)
    if allow_labels:
        annotate = annotate_log_bars if log_y_scale else annotate_linear_bars
        annotate(
            ax,
            label_bars,
            label_texts,
            level_indices=label_levels,
            fontsize=5.75 if n_datasets > 2 else 6.0,
            add_bbox=n_datasets > 1,
        )

    if show_grid:
        ax.grid(True, axis="y", alpha=0.3)
    if show_legend:
        if has_flagged:
            _add_flagged_legend_handle(ax, style)
        else:
            _apply_styled_legend(ax, style)


# ═══════════════════════════════════════════════════════════════════
# K-value boxplot (multi-sample)
# ═══════════════════════════════════════════════════════════════════

def render_k_distribution_function(
    ax: Axes,
    scopes: Sequence[dict],
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_grid: bool = True,
    show_legend: bool = True,
    x_label: str = "Hydraulic Conductivity K (m/s)",
    title: str = "K Distribution Function",
) -> None:
    """Draw empirical K-value CDFs for overall/group scopes.

    Each scope dict should contain ``label``, ``values`` and optional ``color``,
    ``linestyle`` and ``is_overall`` keys. Values must be positive K values in
    m/s; invalid values are ignored here so callers can share one defensive
    renderer between GUI, export, and reports.
    """

    plotted_values: list[float] = []
    overall_values: list[float] = []

    for scope in scopes:
        values = sorted(
            float(value)
            for value in scope.get("values", ())
            if value is not None and float(value) > 0
        )
        if not values:
            continue

        plotted_values.extend(values)
        if scope.get("is_overall"):
            overall_values = values

        n = len(values)
        probabilities = ((np.arange(1, n + 1, dtype=float) - 0.5) / n) * 100.0
        color = scope.get("color") or "#2b5797"
        linewidth = 2.4 if scope.get("is_overall") else 1.8
        alpha = 0.95 if scope.get("is_overall") else 0.78

        ax.plot(
            values,
            probabilities,
            color=color,
            linestyle=scope.get("linestyle", "-"),
            linewidth=linewidth,
            alpha=alpha,
            marker="o" if n <= 12 else None,
            markersize=3.2,
            label=scope.get("label", "Scope"),
        )

    if overall_values and len(overall_values) > 1:
        log_values = [math.log(value) for value in overall_values]
        mu = sum(log_values) / len(log_values)
        sigma = float(np.std(log_values))
        if sigma > 0:
            xmin, xmax = min(overall_values), max(overall_values)
            x_fit = np.logspace(math.log10(xmin), math.log10(xmax), 160)
            inv_sigma = 1.0 / (sigma * math.sqrt(2.0))
            y_fit = np.array([
                0.5 * (1.0 + math.erf((math.log(x) - mu) * inv_sigma)) * 100.0
                for x in x_fit
            ])
            ax.plot(
                x_fit,
                y_fit,
                color="#6a6254",
                linestyle="--",
                linewidth=1.2,
                alpha=0.62,
                label="Overall lognormal fit",
            )
            ax.axvline(
                math.exp(mu),
                color="#6b8e23",
                linestyle=":",
                linewidth=1.3,
                alpha=0.78,
                label="Overall Kgeo",
            )

    ax.set_xscale("log")
    ax.set_xlabel(x_label,
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_ylabel("Cumulative Probability (%)",
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_title(title, fontsize=style.title_fontsize,
                 fontweight=style.title_fontweight, fontfamily=style.font_family)
    ax.set_ylim(0, 100)
    ax.tick_params(labelsize=style.tick_fontsize)

    if plotted_values:
        xmin, xmax = min(plotted_values), max(plotted_values)
        if xmin == xmax:
            ax.set_xlim(xmin / 3.0, xmax * 3.0)
        else:
            ax.set_xlim(xmin / 1.7, xmax * 1.7)

    _apply_grid(ax, style, show_grid, which="both")

    if show_legend:
        _apply_styled_legend(ax, style)


def heterogeneity_label(sigma: Optional[float]) -> str:
    """Aquifer heterogeneity class from σ_lnK (Bohling et al. 2012 banding)."""
    if sigma is None:
        return ""
    if sigma < 1.0:
        return "moderately heterogeneous"
    if sigma < 2.0:
        return "heterogeneous"
    return "highly heterogeneous"


def _prepare_k_hist_scopes(scopes: Sequence[dict]) -> list[dict]:
    """Normalise raw scope dicts into prepared lognormal stats.

    Keeps only positive values (K is lognormal) and pre-computes ``logs``,
    ``mu`` (mean lnK), ``sigma`` (σ_lnK = population std of lnK) and ``n``.
    """
    prepared: list[dict] = []
    for scope in scopes:
        values = sorted(
            float(v) for v in scope.get("values", ())
            if v is not None and float(v) > 0
        )
        if not values:
            continue
        logs = [math.log(v) for v in values]
        mu = sum(logs) / len(logs)
        sigma = float(np.std(logs))  # population std == σ_lnK
        prepared.append({
            "label": scope.get("label", "Scope"),
            "color": scope.get("color") or "#2b5797",
            "values": values, "logs": logs, "mu": mu, "sigma": sigma, "n": len(values),
        })
    return prepared


def _annotate_bar_counts(ax: Axes, rects, counts) -> None:
    """Print the sample count above each populated bar (the ``N`` labels)."""
    for rect, count in zip(rects, counts):
        n = int(count)
        if n > 0:
            ax.annotate(
                str(n),
                (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                textcoords="offset points", xytext=(0, 1.5),
                ha="center", va="bottom", fontsize=6, color="#3a2e1c", zorder=4,
            )


def _render_k_hist_collapsed(
    ax: Axes,
    prepared: list[dict],
    bin_edges,
    use_lnk: bool,
    *,
    frequency: bool,
    show_n: bool,
    single: bool,
) -> None:
    """Draw the histogram on a categorical axis with all-empty bins dropped.

    Every bin with no data in *any* scope is removed so the populated bars sit
    adjacent (no empty interior space). Bars are dodged per scope; a faint
    separator marks where an interior gap was collapsed. No continuous fitted
    curve is drawn here — the broken axis would distort it — so the σ_lnK / Kgeo
    figures carry the lognormal fit instead (annotation/legend).
    """
    edges = np.asarray(bin_edges, dtype=float)
    widths = np.diff(edges)
    centers = 0.5 * (edges[:-1] + edges[1:])
    counts = [
        np.histogram(p["logs"] if use_lnk else p["values"], bins=edges)[0]
        for p in prepared
    ]
    total = np.sum(counts, axis=0)
    retained = [i for i in range(len(total)) if total[i] > 0]
    if not retained:
        return

    num = len(prepared)
    group_width = 0.8
    bar_width = group_width / num

    for s, p in enumerate(prepared):
        positions = [
            c - group_width / 2 + bar_width * (s + 0.5)
            for c in range(len(retained))
        ]
        bin_counts = [counts[s][i] for i in retained]
        if frequency:
            heights = [float(c) for c in bin_counts]
        else:
            heights = [
                counts[s][i] / (p["n"] * widths[i]) if widths[i] > 0 else 0.0
                for i in retained
            ]
        label = p["label"]
        if not single:
            label = f'{p["label"]} (Kgeo={math.exp(p["mu"]):.1e}, σ={p["sigma"]:.2f})'
        bars = ax.bar(
            positions, heights, width=bar_width, color=p["color"],
            edgecolor="black", linewidth=0.5,
            alpha=0.85 if num > 1 else 0.7, label=label, zorder=2,
        )
        ax.set_axisbelow(True)
        if show_n:
            _annotate_bar_counts(ax, bars, bin_counts)

    # Categorical ticks show each retained bin's representative value.
    ax.set_xticks(range(len(retained)))
    if use_lnk:
        tick_labels = [f"{centers[i]:.1f}" for i in retained]
    else:
        tick_labels = [f"{centers[i]:.1e}" for i in retained]
    ax.set_xticklabels(tick_labels, rotation=45, ha="right")
    ax.set_xlim(-0.5, len(retained) - 0.5)

    # Flag every collapsed interior gap so the compaction stays honest.
    for pos in range(len(retained) - 1):
        if retained[pos + 1] - retained[pos] > 1:
            sep_x = pos + 0.5
            ax.axvline(sep_x, color="#b8ad97", linestyle=(0, (2, 2)),
                       linewidth=0.8, zorder=1)
            ax.annotate("//", (sep_x, 0.5), xycoords=("data", "axes fraction"),
                        ha="center", va="center", fontsize=8, color="#9a8c78")


def _render_k_hist_continuous(
    ax: Axes,
    prepared: list[dict],
    bar_scopes: list[dict],
    bin_edges,
    xs,
    use_lnk: bool,
    *,
    frequency: bool,
    show_n: bool,
    single: bool,
    style: PlotStyle,
) -> None:
    """Draw the histogram on the true linear lnK/K axis (real gaps preserved).

    Bars (dodged per scope) sit under the fitted lognormal PDF curve + a Kgeo
    line for each scope. In frequency mode the PDF is scaled to per-bin counts
    (``pdf · n · bin_width``) so the curve tracks the bars; with no bars
    (``bins="off"``) a probability density is drawn instead.
    """
    edges = np.asarray(bin_edges, dtype=float)
    bin_width = float(edges[1] - edges[0]) if len(edges) > 1 else 1.0

    # Draw all scopes' bars in one call so matplotlib dodges them side-by-side
    # (black outlines) instead of muddily overlapping translucent bars.
    if bar_scopes:
        bar_data = [(p["logs"] if use_lnk else p["values"]) for p in bar_scopes]
        bar_colors = [p["color"] for p in bar_scopes]
        raw_counts = [np.histogram(data, bins=edges)[0] for data in bar_data]
        _n, _bins, patch_groups = ax.hist(
            bar_data, bins=edges, density=not frequency, color=bar_colors,
            histtype="bar", edgecolor="black", linewidth=0.5,
            alpha=0.85 if len(bar_data) > 1 else 0.45, zorder=1,
        )
        ax.set_axisbelow(True)
        if show_n:
            containers = patch_groups if len(bar_data) > 1 else [patch_groups]
            for counts_arr, container in zip(raw_counts, containers):
                _annotate_bar_counts(ax, container, counts_arr)

    for p in prepared:
        color = p["color"]
        label = p["label"]
        if not single:
            label = f'{p["label"]} (Kgeo={math.exp(p["mu"]):.1e}, σ={p["sigma"]:.2f})'

        scale = (p["n"] * bin_width) if (frequency and bar_scopes) else 1.0
        if p["sigma"] > 0:
            if use_lnk:
                pdf = (1.0 / (p["sigma"] * math.sqrt(2 * math.pi))) * np.exp(
                    -((xs - p["mu"]) ** 2) / (2 * p["sigma"] ** 2)
                )
            else:
                safe_xs = np.where(xs > 0, xs, np.nan)
                pdf = (1.0 / (safe_xs * p["sigma"] * math.sqrt(2 * math.pi))) * np.exp(
                    -((np.log(safe_xs) - p["mu"]) ** 2) / (2 * p["sigma"] ** 2)
                )
            ax.plot(xs, pdf * scale, color=color, linewidth=style.curve_linewidth + 0.3,
                    label=label, zorder=3)
        else:
            ax.axvline(p["mu"] if use_lnk else p["values"][0], color=color, label=label)

        center = p["mu"] if use_lnk else math.exp(p["mu"])
        ax.axvline(center, color=color, linestyle=":", linewidth=1.1, alpha=0.7, zorder=2)


def render_k_histogram(
    ax: Axes,
    scopes: Sequence[dict],
    *,
    axis: str = "lnk",
    unit_symbol: str = "m/s",
    bins: "str | int" = "auto",
    y_mode: str = "frequency",
    show_n: bool = True,
    drop_empty_bins: bool = True,
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_grid: bool = True,
    show_legend: bool = True,
    title: str = "K Distribution (lognormal)",
) -> None:
    """Draw the lognormal K histogram (Poul's distribution function for K).

    K is lognormal, so on the ``lnk`` axis the data forms a bell with a fitted
    normal curve; on the ``k`` axis it is right-skewed with a fitted lognormal
    curve. A K_geo / σ_lnK annotation is shown for a single scope; group bars are
    dodged side-by-side (black-outlined).

    *y_mode* picks the vertical axis: ``"frequency"`` (per-bin counts, the
    default) or ``"density"`` (a probability density the fitted PDF integrates
    to). *show_n* annotates each drawn bar with its sample count. *drop_empty_bins*
    (default) collapses every all-empty interior bin so populated bars sit
    adjacent on a categorical axis — set it False to keep the true linear K/lnK
    axis with the fitted PDF curve overlaid (real gaps shown). ``bins`` controls
    the bars: ``"auto"`` sizes them to the data, ``"off"`` shows fitted curves
    only (always the continuous view), and an integer forces that many bins.
    Values must be positive, in display units.
    """
    use_lnk = axis != "k"
    frequency = y_mode != "density"

    prepared = _prepare_k_hist_scopes(scopes)
    if not prepared:
        return
    single = len(prepared) == 1

    # Shared evaluation range + bin edges across every scope so fitted curves
    # are not asymmetrically clipped to each scope's own min/max and so grouped
    # histograms stay directly comparable.
    all_x = [
        value
        for p in prepared
        for value in (p["logs"] if use_lnk else p["values"])
    ]
    if use_lnk:
        g_min, g_max = min(all_x), max(all_x)
        span = (g_max - g_min) or (abs(g_max) or 1.0)
        pad = span * 0.12
        x_lo, x_hi = g_min - pad, g_max + pad
    else:
        # Linear-K is dominated by the long right tail when σ_lnK is large;
        # clip the upper limit to a high percentile so the bulk stays readable
        # while the lognormal skew is still visible.
        g_max = float(np.percentile(all_x, 95))
        x_lo = 0.0
        x_hi = (g_max * 1.05) or 1.0
    n_max = max(p["n"] for p in prepared)
    bins_arg = str(bins).strip().lower()
    if bins_arg == "off":
        draw_bars, n_bins = False, 10
    elif bins_arg.isdigit():
        # Explicit bin count forces bars for every scope.
        draw_bars, n_bins = True, max(2, int(bins_arg))
    else:  # "auto": always draw bars (dodged for groups), sized to the data.
        draw_bars, n_bins = True, max(6, min(24, n_max // 2))
    bin_edges = np.linspace(x_lo, x_hi, n_bins + 1)
    xs = np.linspace(x_lo, x_hi, 320)

    # Collapsed view: drop all-empty bins onto a categorical axis (default).
    # Continuous view: real axis + fitted curves (bins="off" or gaps shown).
    collapsed = draw_bars and drop_empty_bins
    bars_present = collapsed or (draw_bars and any(p["n"] >= 3 for p in prepared))
    if collapsed:
        _render_k_hist_collapsed(
            ax, prepared, bin_edges, use_lnk,
            frequency=frequency, show_n=show_n, single=single,
        )
    else:
        bar_scopes = [p for p in prepared if draw_bars and p["n"] >= 3]
        _render_k_hist_continuous(
            ax, prepared, bar_scopes, bin_edges, xs, use_lnk,
            frequency=frequency, show_n=show_n, single=single, style=style,
        )
        ax.set_xlim(x_lo, x_hi)

    # ── Shared axis labels / title ────────────────────────────────
    if use_lnk:
        x_label = f"ln K   (K in {unit_symbol})"
    else:
        x_label = f"Hydraulic Conductivity K ({unit_symbol})"
    if collapsed:
        x_label += "  (populated bins only)"
    ax.set_xlabel(x_label, fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_ylabel(
        "Frequency (count)" if (frequency and bars_present) else "Probability density",
        fontsize=style.label_fontsize, fontfamily=style.font_family,
    )
    ax.set_title(title, fontsize=style.title_fontsize,
                 fontweight=style.title_fontweight, fontfamily=style.font_family)
    ax.set_ylim(bottom=0)
    ax.tick_params(labelsize=style.tick_fontsize)

    _apply_grid(ax, style, show_grid)

    if single:
        p = prepared[0]
        het = heterogeneity_label(p["sigma"])
        lines = [
            f"$K_{{geo}}$ = {math.exp(p['mu']):.2e} {unit_symbol}",
            f"$\\sigma_{{lnK}}$ = {p['sigma']:.2f}" + (f"  ({het})" if het else ""),
            f"n = {p['n']}",
        ]
        ax.text(0.97, 0.97, "\n".join(lines), transform=ax.transAxes,
                ha="right", va="top", fontsize=8, color="#3a2e1c",
                bbox=dict(boxstyle="round", facecolor="white",
                          edgecolor=style.legend_edgecolor, alpha=0.85))
    elif show_legend:
        _apply_styled_legend(ax, style)


def render_k_boxplot(
    ax: Axes,
    k_results_dict: Dict[str, list],
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_grid: bool = True,
    title: str = "K-Value Distribution Comparison",
) -> None:
    """Draw box plots of K-values across samples.

    *k_results_dict*: ``{sample_name: [KCalculationResult, ...]}``
    """
    data_for_plot: list[list[float]] = []
    labels: list[str] = []

    for sample_name, results in k_results_dict.items():
        k_vals = [
            r.k_value
            for r in results
            if r.k_value is not None
            and r.k_value > 0
            and classify_k_status(r) == "OK"
        ]
        if k_vals:
            data_for_plot.append(k_vals)
            labels.append(sample_name)

    if not data_for_plot:
        return

    boxplot_kwargs = dict(
        patch_artist=True,
        showmeans=True,
        meanline=True,
        boxprops=dict(facecolor=style.legend_edgecolor, alpha=0.7),
        medianprops=dict(color=style.d10_color, linewidth=2),
        meanprops=dict(color=style.d30_color, linewidth=2, linestyle="--"),
    )
    try:
        ax.boxplot(data_for_plot, tick_labels=labels, **boxplot_kwargs)
    except TypeError:
        ax.boxplot(data_for_plot, labels=labels, **boxplot_kwargs)

    ax.set_yscale("log")
    ax.set_ylabel("Hydraulic Conductivity (m/s)",
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_xlabel("Sample",
                  fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_title(title, fontsize=style.title_fontsize,
                 fontweight=style.title_fontweight, fontfamily=style.font_family)

    if show_grid:
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    if len(labels) > 5:
        ax.set_xticklabels(labels, rotation=45, ha="right",
                           fontsize=style.tick_fontsize)


# ═══════════════════════════════════════════════════════════════════
# Applicability heatmap (single sample)
# ═══════════════════════════════════════════════════════════════════

def render_k_scope_boxplot(
    ax: Axes,
    scope_values: Mapping[str, Sequence[float]] | Sequence[tuple[str, Sequence[float]]],
    *,
    colors: Optional[Sequence[str]] = None,
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_grid: bool = True,
    title: str = "Hydraulic Conductivity Distribution by Scope",
    x_label: str = "Scope",
    y_label: str = "Hydraulic Conductivity (m/s)",
) -> None:
    """Draw K-value boxplots from pre-aggregated comparison scopes."""
    raw_items = list(scope_values.items()) if isinstance(scope_values, Mapping) else list(scope_values)

    data_for_plot: list[list[float]] = []
    labels: list[str] = []
    plot_colors: list[str] = []
    color_list = list(colors or [])

    for index, (label, values) in enumerate(raw_items):
        clean_values = []
        for value in values or []:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if np.isfinite(numeric) and numeric > 0:
                clean_values.append(numeric)
        if not clean_values:
            continue
        labels.append(str(label))
        data_for_plot.append(clean_values)
        if index < len(color_list):
            plot_colors.append(color_list[index])
        else:
            plot_colors.append(DATASET_COLORS[len(plot_colors) % len(DATASET_COLORS)])

    if not data_for_plot:
        return

    edge_color = getattr(style, "legend_edgecolor", "#777777")
    muted_color = "#777777"
    boxplot_kwargs = dict(
        patch_artist=True,
        showmeans=True,
        meanline=True,
        medianprops=dict(color=style.d10_color, linewidth=2),
        meanprops=dict(color=style.d30_color, linewidth=2, linestyle="--"),
        whiskerprops=dict(color=edge_color, linewidth=1.1),
        capprops=dict(color=edge_color, linewidth=1.1),
        flierprops=dict(
            marker="o",
            markersize=3,
            markerfacecolor=muted_color,
            markeredgecolor=muted_color,
            alpha=0.45,
        ),
    )
    try:
        box_artists = ax.boxplot(data_for_plot, tick_labels=labels, **boxplot_kwargs)
    except TypeError:
        box_artists = ax.boxplot(data_for_plot, labels=labels, **boxplot_kwargs)

    for patch, color in zip(box_artists.get("boxes", []), plot_colors):
        patch.set_facecolor(color)
        patch.set_edgecolor(color)
        patch.set_alpha(0.45)

    ax.set_yscale("log")
    ax.set_ylabel(y_label, fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_xlabel(x_label, fontsize=style.label_fontsize, fontfamily=style.font_family)
    ax.set_title(
        title,
        fontsize=style.title_fontsize,
        fontweight=style.title_fontweight,
        fontfamily=style.font_family,
    )

    if show_grid:
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    if len(labels) > 5 or any(len(label) > 14 for label in labels):
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=style.tick_fontsize)


def render_applicability_heatmap(
    ax: Axes,
    k_results: list,
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    title: str = "Method Applicability Status",
) -> None:
    """Draw a single-sample method applicability status heatmap."""
    if not k_results:
        return

    methods = [r.method_name for r in k_results]
    status_values: list[int] = []
    status_labels: list[str] = []

    for r in k_results:
        if r.k_value is None or r.k_value <= 0:
            status_values.append(0)
            status_labels.append("N/A")
        else:
            tag = classify_k_status(r)
            status_values.append({"OK": 3, "Warning": 2, "Error": 1}[tag])
            status_labels.append(tag)

    data = np.array(status_values).reshape(-1, 1)
    cmap = ListedColormap(["#cccccc", "#ff6b6b", "#ffd93d", "#6bcf7f"])

    ax.imshow(data, cmap=cmap, aspect="auto", vmin=0, vmax=3)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels(methods, fontsize=style.tick_fontsize)
    ax.set_xticks([0])
    ax.set_xticklabels(["Status"], fontsize=style.label_fontsize, fontweight="bold")
    ax.set_title(title, fontsize=style.title_fontsize,
                 fontweight=style.title_fontweight, fontfamily=style.font_family)

    for i, (val, label) in enumerate(zip(status_values, status_labels)):
        ax.text(0, i, label, ha="center", va="center",
                fontweight="bold", fontsize=style.tick_fontsize,
                color="white" if val in (1, 3) else "black")


# ═══════════════════════════════════════════════════════════════════
# Reliability matrix (multi-sample)
# ═══════════════════════════════════════════════════════════════════

def render_reliability_matrix(
    ax: Axes,
    k_results_dict: Dict[str, list],
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    title: str = "Method Applicability Matrix \u2014 All Samples",
) -> None:
    """Draw a multi-sample method reliability heatmap."""
    if not k_results_dict:
        return

    all_methods: set[str] = set()
    for results in k_results_dict.values():
        for r in results:
            all_methods.add(r.method_name)
    methods = sorted(all_methods)
    sample_names = list(k_results_dict.keys())

    if not methods or not sample_names:
        return

    matrix = np.zeros((len(methods), len(sample_names)))
    for j, sample_name in enumerate(sample_names):
        for i, method in enumerate(methods):
            result = next((r for r in k_results_dict[sample_name]
                           if r.method_name == method), None)
            if result is None or result.k_value is None or result.k_value <= 0:
                matrix[i, j] = 0
            else:
                tag = classify_k_status(result)
                matrix[i, j] = {"OK": 3, "Warning": 2, "Error": 1}[tag]

    cmap = ListedColormap(["#cccccc", "#ff6b6b", "#ffd93d", "#6bcf7f"])
    ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=3)
    ax.set_xticks(range(len(sample_names)))
    ax.set_xticklabels(sample_names, rotation=45, ha="right",
                       fontsize=style.tick_fontsize)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels(methods, fontsize=max(style.tick_fontsize - 1, 7))
    ax.set_title(title, fontsize=style.title_fontsize,
                 fontweight=style.title_fontweight, fontfamily=style.font_family)

    for i in range(len(methods)):
        for j in range(len(sample_names)):
            val = matrix[i, j]
            label = ["N/A", "ERR", "WARN", "OK"][int(val)]
            ax.text(j, i, label, ha="center", va="center",
                    fontweight="bold", fontsize=8,
                    color="white" if val in (1, 3) else "black")


# ═══════════════════════════════════════════════════════════════════
# Internal helpers (shared across renderers)
# ═══════════════════════════════════════════════════════════════════

def _distribution_limits(
    particle_sizes, percent_passing, scheme=None,
) -> tuple[float, float, float, float]:
    """Compute padded distribution-plot limits."""
    sorted_pairs = sorted(zip(particle_sizes, percent_passing))
    x_min = sorted_pairs[0][0] / _DIST_X_PAD
    last_x = sorted_pairs[-1][0]
    pct_at_largest = sorted_pairs[-1][1]
    x_max = last_x * _DIST_X_PAD

    if pct_at_largest > 1.0 and scheme is not None:
        sand_max = getattr(scheme, "sand_max", 2.0)
        gravel_max = getattr(scheme, "gravel_max", 63.0)
        if last_x < sand_max:
            x_max = max(x_max, sand_max * 1.35)
        elif last_x < gravel_max:
            x_max = max(x_max, gravel_max * 1.35)
        else:
            x_max = max(x_max, last_x * 3.5)

    return x_min, x_max, 0.0, _DIST_Y_MAX


def _overlay_distribution_limits(datasets, scheme=None) -> tuple[float, float, float, float]:
    """Compute padded limits spanning every dataset in a comparison overlay.

    Falls back to the historical fixed window when no usable points exist so an
    empty overlay still renders a sensible axes box.
    """
    all_sizes: list[float] = []
    all_pcts: list[float] = []
    for dataset in datasets:
        sizes = list(getattr(dataset, "particle_sizes", []) or [])
        pcts = list(getattr(dataset, "percent_passing", []) or [])
        for size, pct in zip(sizes, pcts):
            if size is None or size <= 0 or pct is None:
                continue
            all_sizes.append(float(size))
            all_pcts.append(float(pct))
    if not all_sizes:
        return 0.001, 100.0, 0.0, _DIST_Y_MAX
    return _distribution_limits(all_sizes, all_pcts, scheme)


def _draw_characteristic_lines(
    ax: Axes, particle_sizes, percent_passing, grain_size_data, style: PlotStyle,
) -> None:
    """Draw D10/D50/D60 guide lines."""
    if grain_size_data is not None:
        d_values = [
            grain_size_data.get_d10(),
            grain_size_data.get_d50(),
            grain_size_data.get_d60(),
        ]
    else:
        d_values = []
        if len(particle_sizes) > 0 and len(percent_passing) > 0:
            for percentile in (10, 50, 60):
                if min(percent_passing) <= percentile <= max(percent_passing):
                    d_values.append(np.interp(percentile, percent_passing, particle_sizes))
                else:
                    d_values.append(None)

    names   = ["D10", "D50", "D60"]
    colors  = [style.d10_color, style.d30_color, style.d60_color]
    lstyles = [style.d10_line_style, style.d30_line_style, style.d60_line_style]
    percs   = [10, 50, 60]

    for d_val, perc, color, ls, name in zip(d_values, percs, colors, lstyles, names):
        if d_val is None:
            continue
        ax.axvline(x=d_val, color=color, linestyle=ls,
                   linewidth=style.d_line_width, alpha=style.d_line_alpha,
                   label=f"{name} = {d_val:.3f} mm")
        ax.axhline(y=perc, color=color, linestyle=":",
                   alpha=style.d_line_alpha * 0.7)


def _draw_classification_zones(ax: Axes, scheme) -> None:
    """Draw grain size classification zones as background bands."""
    x_min, x_max = ax.get_xlim()
    zones = [
        ("Clay",   0.0001,          scheme.clay_max,   _GC_CLAY),
        ("Silt",   scheme.clay_max,  scheme.silt_max,   _GC_SILT),
        ("Sand",   scheme.silt_max,  scheme.sand_max,   _GC_SAND),
        ("Gravel", scheme.sand_max,  scheme.gravel_max, _GC_GRAVEL),
        ("Cobble", scheme.gravel_max, 300,              _GC_COBBLE),
    ]
    for name, lo, hi, color in zones:
        if hi <= x_min or lo >= x_max:
            continue
        ax.axvspan(lo, hi, color=color, alpha=0.18, zorder=0)
        lo_vis = max(lo, x_min)
        hi_vis = min(hi, x_max)
        mid = math.sqrt(lo_vis * hi_vis)
        ax.text(mid, 95, name, ha="center", va="top", fontsize=8,
                color="#5a4a3a", fontweight="bold", alpha=0.6)


def _draw_fill_zone_labels(ax, particle_sizes, percent_passing,
                           grain_size_data, scheme) -> None:
    """Draw grain fraction % labels centred inside the filled area."""
    try:
        result = grain_size_data.classify(scheme=scheme)
        fracs = result.fractions
    except Exception:
        return

    from grain_classification import interpolate_at as _gc_interp
    zone_fracs = [
        ("Clay",   0.0001,          scheme.clay_max,   fracs.clay_pct),
        ("Silt",   scheme.clay_max,  scheme.silt_max,   fracs.silt_pct),
        ("Sand",   scheme.silt_max,  scheme.sand_max,   fracs.sand_pct),
        ("Gravel", scheme.sand_max,  scheme.gravel_max, fracs.gravel_pct),
        ("Cobble", scheme.gravel_max, 200.0,            fracs.cobble_pct),
    ]
    for name, lo, hi, frac in zone_fracs:
        if frac < 2.0:
            continue
        x_mid = math.sqrt(lo * hi)
        y_at_mid = _gc_interp(list(particle_sizes), list(percent_passing), x_mid)
        if y_at_mid is None or y_at_mid < 6.0:
            continue
        ax.text(x_mid, y_at_mid / 2.0,
                f"{frac:.0f}%\n{name}",
                ha="center", va="center",
                fontsize=7.5, fontweight="bold",
                color="#3a2e1c", alpha=0.72, zorder=3)


def _apply_grid(ax: Axes, style: PlotStyle, show: bool,
                which: str = "major") -> None:
    """Apply grid styling from *style*."""
    if not (show and style.grid_show):
        return
    ax.grid(True, alpha=style.grid_alpha, which=which,
            linestyle=style.grid_linestyle, color=style.grid_color,
            linewidth=style.grid_linewidth)
    if which == "major" and style.show_minor_grid:
        ax.grid(True, alpha=style.minor_grid_alpha, which="minor",
                linestyle=":", color=style.grid_color,
                linewidth=style.grid_linewidth * 0.5)


def legend_column_count(style: PlotStyle, label_count: Optional[int] = None) -> int:
    """Return the Matplotlib legend column count requested by *style*."""
    configured = int(getattr(style, "legend_ncol", 1) or 0)
    if configured <= 0:
        return max(1, label_count or 1)
    if label_count:
        return max(1, min(configured, label_count))
    return max(1, configured)


def build_legend_kwargs(
    style: PlotStyle,
    label_count: Optional[int] = None,
) -> dict:
    """Build common Matplotlib legend kwargs from a PlotStyle."""
    kwargs = dict(
        loc=style.legend_loc,
        fontsize=style.legend_fontsize,
        framealpha=style.legend_framealpha,
        edgecolor=style.legend_edgecolor,
        ncol=legend_column_count(style, label_count),
    )
    if style.legend_bbox_to_anchor is not None:
        kwargs["bbox_to_anchor"] = style.legend_bbox_to_anchor
    return kwargs


def legend_outside_side(style: PlotStyle) -> Optional[str]:
    """Return the outside side implied by the style's bbox anchor."""
    bbox = getattr(style, "legend_bbox_to_anchor", None)
    if bbox is None:
        return None
    x, y = bbox
    if x > 1.0:
        return "right"
    if x < 0.0:
        return "left"
    if y > 1.0:
        return "top"
    if y < 0.0:
        return "bottom"
    return None


def apply_legend_aware_layout(
    figure: Figure,
    style: PlotStyle,
    *,
    pad: float = 0.9,
    fallback: Optional[dict] = None,
) -> None:
    """Run tight_layout and reserve figure margin for outside legends."""
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "error",
                message="Tight layout not applied.*",
                category=UserWarning,
            )
            figure.tight_layout(pad=pad)
    except UserWarning:
        figure.subplots_adjust(**(fallback or {}))

    side = legend_outside_side(style)
    if side is None:
        return

    pars = figure.subplotpars
    left = pars.left
    right = pars.right
    top = pars.top
    bottom = pars.bottom
    vertical = legend_column_count(style) == 1

    if side == "top":
        top = min(top, 0.72 if vertical else 0.80)
    elif side == "bottom":
        bottom = max(bottom, 0.24 if vertical else 0.18)
    elif side == "right":
        right = min(right, 0.78)
    elif side == "left":
        left = max(left, 0.22)

    figure.subplots_adjust(
        left=left,
        right=right,
        top=top,
        bottom=bottom,
        wspace=max(pars.wspace, 0.2),
        hspace=max(pars.hspace, 0.2),
    )


def _apply_styled_legend(ax: Axes, style: PlotStyle) -> None:
    """Draw a legend using *style*'s font, alpha, edge, loc, and optional bbox.

    When ``style.legend_bbox_to_anchor`` is set, matplotlib anchors the legend
    relative to the axes — this is how "outside the plot" placements work.
    """
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        _apply_styled_legend_with_handles(ax, style, handles, labels)


def _style_k_bar(bar, method: str, color: str, flagged: Set[str]) -> None:
    """Apply warning styling (hatch) to flagged K-value bars."""
    if method in flagged:
        bar.set_facecolor("none")
        bar.set_edgecolor(color)
        bar.set_linewidth(2.0)
        bar.set_hatch("////")
        bar.set_alpha(1.0)
    else:
        bar.set_edgecolor("black")
        bar.set_linewidth(1.0)


def _style_k_bar_simple(bar, color: str, flagged: bool) -> None:
    """Comparison-widget variant: colour arg is the dataset colour."""
    if flagged:
        bar.set_facecolor("none")
        bar.set_edgecolor(color)
        bar.set_linewidth(2.0)
        bar.set_hatch("////")
        bar.set_alpha(1.0)
    else:
        bar.set_edgecolor("black")
        bar.set_linewidth(0.5)


def _add_k_status_legend(ax: Axes, flagged: Set[str], style: PlotStyle) -> None:
    """Add legend including a Flagged entry when needed."""
    handles, labels = ax.get_legend_handles_labels()
    if flagged:
        handles.append(
            Patch(facecolor="none", edgecolor=style.k_bar_flagged_color,
                  hatch="////", label="Flagged / Warning")
        )
        labels.append("Flagged / Warning")
    if handles:
        _apply_styled_legend_with_handles(ax, style, handles, labels)


def _add_flagged_legend_handle(ax: Axes, style: PlotStyle = PROFESSIONAL_STYLE) -> None:
    """Append a warning-state legend entry (comparison widget style)."""
    handles, labels = ax.get_legend_handles_labels()
    handles.append(
        Patch(facecolor="none", edgecolor="#2f2419",
              hatch="////", label="Flagged / Warning")
    )
    labels.append("Flagged / Warning")
    _apply_styled_legend_with_handles(ax, style, handles, labels)


def _apply_styled_legend_with_handles(ax: Axes, style: PlotStyle,
                                      handles, labels) -> None:
    """Draw a legend with explicit handles/labels but honour style fields."""
    kwargs = build_legend_kwargs(style, len(labels))
    ax.legend(handles, labels, **kwargs)
