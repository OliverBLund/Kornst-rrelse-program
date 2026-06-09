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
from typing import Dict, List, Optional, Sequence, Set

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
    annotate_log_bars,
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
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_grid: bool = True,
    show_legend: bool = True,
    show_reference_lines: bool = True,
    show_value_labels: bool = True,
    title: Optional[str] = None,
    y_label: str = "Hydraulic Conductivity K (m/s)",
    sample_name: str = "Sample",
    tick_fontsize_override: Optional[float] = None,
    value_label_fontsize: float = 8.0,
) -> None:
    """Draw a K-value bar chart on *ax*.

    *methods* and *k_values* must be parallel sequences (already
    converted to display units if required).
    """
    if not methods:
        return

    x_pos = np.arange(len(methods))

    # Colours ─────────────────────────────────────────────────────
    if style.use_method_specific_colors:
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
    apply_log_bar_limits(ax, k_values)

    if show_grid and style.grid_show:
        ax.grid(True, axis="y", alpha=style.grid_alpha,
                linestyle=style.grid_linestyle, color=style.grid_color,
                linewidth=style.grid_linewidth)

    # Reference lines ─────────────────────────────────────────────
    positive = [v for v in k_values if v and v > 0]
    if show_reference_lines and positive:
        arithmetic_mean = float(np.mean(positive))
        geometric_mean = float(np.exp(np.mean(np.log(positive))))
        ax.axhline(arithmetic_mean, color="#b83232", linestyle="-", alpha=0.62,
                   label=f"Arithmetic mean: {arithmetic_mean:.2e}")
        ax.axhline(geometric_mean, color="#5c3d8f", linestyle="--", alpha=0.68,
                   label=f"Geometric mean: {geometric_mean:.2e}")
        ax.axhline(min(positive), color="blue", linestyle=":", alpha=0.5,
                   label=f"Min: {min(positive):.2e}")
        ax.axhline(max(positive), color="green", linestyle=":", alpha=0.5,
                   label=f"Max: {max(positive):.2e}")

    # Bar labels ──────────────────────────────────────────────────
    if show_value_labels:
        labels = [f"{v:.1e}" if v and v > 0 else "" for v in k_values]
        annotate_log_bars(ax, bars, labels, fontsize=value_label_fontsize)

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
    style: PlotStyle = PROFESSIONAL_STYLE,
    show_grid: bool = True,
    show_legend: bool = True,
    title: str = "Grain Size Distribution Comparison",
) -> None:
    """Draw overlaid grain-size curves for multiple samples."""
    _colors = colors or DATASET_COLORS
    _linestyles = linestyles or ["-"]
    _labels = labels or [ds.sample_name for ds in datasets]

    for i, dataset in enumerate(datasets):
        c = _colors[i % len(_colors)]
        ls = _linestyles[i % len(_linestyles)]
        use_marker = len(dataset.particle_sizes) < 20
        ax.semilogx(
            dataset.particle_sizes,
            dataset.percent_passing,
            linewidth=style.curve_linewidth,
            linestyle=ls,
            label=_labels[i],
            color=c,
            marker="o" if use_marker else None,
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
    ax.set_xlim(0.001, 100)
    ax.set_ylim(0, 100)

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
    apply_log_bar_limits(ax, positive_values,
                         max_label_level=max(label_levels, default=0))
    if allow_labels:
        annotate_log_bars(
            ax, label_bars, label_texts,
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

    if plotted_values:
        xmin, xmax = min(plotted_values), max(plotted_values)
        if xmin == xmax:
            ax.set_xlim(xmin / 3.0, xmax * 3.0)
        else:
            ax.set_xlim(xmin / 1.7, xmax * 1.7)

    _apply_grid(ax, style, show_grid, which="both")

    if show_legend:
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
        k_vals = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]
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


def _draw_characteristic_lines(
    ax: Axes, particle_sizes, percent_passing, grain_size_data, style: PlotStyle,
) -> None:
    """Draw D10/D30/D60 guide lines."""
    if grain_size_data is not None:
        d_values = [
            grain_size_data.get_d10(),
            grain_size_data.get_d30(),
            grain_size_data.get_d60(),
        ]
    else:
        d_values = []
        if len(particle_sizes) > 0 and len(percent_passing) > 0:
            for percentile in (10, 30, 60):
                if min(percent_passing) <= percentile <= max(percent_passing):
                    d_values.append(np.interp(percentile, percent_passing, particle_sizes))
                else:
                    d_values.append(None)

    names   = ["D10", "D30", "D60"]
    colors  = [style.d10_color, style.d30_color, style.d60_color]
    lstyles = [style.d10_line_style, style.d30_line_style, style.d60_line_style]
    percs   = [10, 30, 60]

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
