"""Headless figure creation and base64 export for report generation.

Each ``export_*`` function:
1. Applies the shared matplotlib rcParams (fonts, grid, …).
2. Creates a throw-away ``Figure`` + ``Axes``.
3. Delegates all drawing to a renderer in ``gui.plot_renderers``.
4. Returns the plot as a ``data:image/png;base64,…`` string ready
   for embedding in an ``<img>`` tag.

No QWidget is needed — only the Agg backend.
"""

from __future__ import annotations

import base64
import io
from typing import Dict, List, Optional, Set

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.figure import Figure     # noqa: E402

import importlib as _il  # noqa: E402

# Import submodules directly to avoid triggering gui/__init__.py
# (which imports MainWindow → reporting_tab → report_generator → here,
#  causing a circular import).
_renderers = _il.import_module("gui.plot_renderers")
_styles    = _il.import_module("gui.plot_styles")
_theme     = _il.import_module("gui.theme")
_plot_ctx  = _il.import_module("gui.plot_context")

render_grain_size_distribution = _renderers.render_grain_size_distribution
render_k_bar_chart             = _renderers.render_k_bar_chart
render_distribution_overlay    = _renderers.render_distribution_overlay
render_k_overlay               = _renderers.render_k_overlay
render_k_boxplot               = _renderers.render_k_boxplot
render_applicability_heatmap   = _renderers.render_applicability_heatmap
render_reliability_matrix      = _renderers.render_reliability_matrix
apply_legend_aware_layout      = _renderers.apply_legend_aware_layout
apply_axis_limits_from_context = _plot_ctx.apply_axis_limits_from_context
grain_size_renderer_kwargs_from_context = _plot_ctx.grain_size_renderer_kwargs_from_context

PlotStyle          = _styles.PlotStyle
PROFESSIONAL_STYLE = _styles.PROFESSIONAL_STYLE
apply_matplotlib_style = _theme.apply_matplotlib_style


# ── Helper ────────────────────────────────────────────────────

def _fig_to_base64(fig: Figure, *, dpi: int = 150) -> str:
    """Render *fig* to a base64-encoded PNG data-URL and close it."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor="white")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return f"data:image/png;base64,{encoded}"


# ── Single-sample grain-size distribution ─────────────────────

def export_grain_size_plot(
    dataset,
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] = (10, 6),
    dpi: int = 150,
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
    axis_limits: Optional[Dict[str, tuple[float, float]]] = None,
    plot_context: Optional[Dict] = None,
) -> str:
    """Return a base64-encoded PNG of a grain-size distribution plot."""
    apply_matplotlib_style()
    fig, ax = plt.subplots(figsize=figsize)
    renderer_kwargs = grain_size_renderer_kwargs_from_context(
        dataset.sample_name,
        dataset,
        plot_context,
        default_style=style,
        default_show_d_lines=show_d_lines,
        default_show_markers=show_markers,
        default_show_grid=show_grid,
        default_show_legend=show_legend,
        default_show_classification_zones=show_classification_zones,
        default_classification_scheme=classification_scheme,
        default_fill_curve=fill_curve,
        default_fill_zone_labels=fill_zone_labels,
        default_title=title,
        default_show_title=show_title,
        default_x_label=x_label,
        default_y_label=y_label,
        default_show_x_label=show_x_label,
        default_show_y_label=show_y_label,
    )

    render_grain_size_distribution(
        ax,
        dataset.particle_sizes,
        dataset.percent_passing,
        **renderer_kwargs,
    )
    effective_axis_limits = axis_limits
    if plot_context and "axis_limits" in plot_context:
        effective_axis_limits = plot_context["axis_limits"]
    if effective_axis_limits:
        apply_axis_limits_from_context(ax, {"axis_limits": effective_axis_limits})

    apply_legend_aware_layout(fig, renderer_kwargs.get("style", style))
    return _fig_to_base64(fig, dpi=dpi)


# ── Single-sample K-value bar chart ──────────────────────────

def export_k_bar_chart(
    methods: list[str],
    k_values: list[float],
    *,
    flagged_methods: Set[str] = frozenset(),
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] = (12, 6),
    dpi: int = 150,
    show_grid: bool = True,
    show_legend: bool = True,
    show_reference_lines: bool = True,
    show_value_labels: bool = True,
    title: Optional[str] = None,
    y_label: str = "Hydraulic Conductivity K (m/s)",
    sample_name: str = "Sample",
) -> str:
    """Return a base64-encoded PNG of a K-value bar chart."""
    apply_matplotlib_style()
    fig, ax = plt.subplots(figsize=figsize)

    render_k_bar_chart(
        ax, methods, k_values,
        flagged_methods=flagged_methods,
        style=style,
        show_grid=show_grid,
        show_legend=show_legend,
        show_reference_lines=show_reference_lines,
        show_value_labels=show_value_labels,
        title=title,
        y_label=y_label,
        sample_name=sample_name,
    )

    apply_legend_aware_layout(fig, style)
    return _fig_to_base64(fig, dpi=dpi)


# ── Multi-sample distribution overlay ────────────────────────

def export_distribution_overlay(
    datasets: list,
    *,
    labels: Optional[List[str]] = None,
    colors: Optional[List[str]] = None,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] = (12, 7),
    dpi: int = 150,
    show_grid: bool = True,
    show_legend: bool = True,
    title: str = "Grain Size Distribution Comparison",
) -> str:
    """Return a base64-encoded PNG of overlaid grain-size curves."""
    apply_matplotlib_style()
    fig, ax = plt.subplots(figsize=figsize)

    render_distribution_overlay(
        ax, datasets,
        labels=labels, colors=colors, style=style,
        show_grid=show_grid, show_legend=show_legend, title=title,
    )

    apply_legend_aware_layout(fig, style)
    return _fig_to_base64(fig, dpi=dpi)


# ── Multi-sample K-value grouped bars ────────────────────────

def export_k_overlay(
    k_results_dict: Dict[str, Dict[str, float]],
    *,
    flagged_methods_dict: Optional[Dict[str, Set[str]]] = None,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] = (12, 7),
    dpi: int = 150,
    show_grid: bool = True,
    show_legend: bool = True,
    show_value_labels: bool = True,
    title: str = "Hydraulic Conductivity Comparison",
) -> str:
    """Return a base64-encoded PNG of grouped K-value bars."""
    apply_matplotlib_style()
    fig, ax = plt.subplots(figsize=figsize)

    render_k_overlay(
        ax, k_results_dict,
        flagged_methods_dict=flagged_methods_dict,
        style=style,
        show_grid=show_grid,
        show_legend=show_legend,
        show_value_labels=show_value_labels,
        title=title,
    )

    apply_legend_aware_layout(fig, style)
    return _fig_to_base64(fig, dpi=dpi)


# ── Multi-sample K-value boxplot ─────────────────────────────

def export_k_boxplot(
    k_results_dict: Dict[str, list],
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] = (12, 7),
    dpi: int = 150,
    show_grid: bool = True,
    title: str = "K-Value Distribution Comparison",
) -> str:
    """Return a base64-encoded PNG of K-value boxplots."""
    apply_matplotlib_style()
    fig, ax = plt.subplots(figsize=figsize)

    render_k_boxplot(
        ax, k_results_dict,
        style=style,
        show_grid=show_grid,
        title=title,
    )

    fig.tight_layout()
    return _fig_to_base64(fig, dpi=dpi)


# ── Single-sample applicability heatmap ──────────────────────

def export_applicability_heatmap(
    k_results: list,
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] | None = None,
    dpi: int = 150,
    title: str = "Method Applicability Status",
) -> str:
    """Return a base64-encoded PNG of a method applicability heatmap."""
    apply_matplotlib_style()
    _figsize = figsize or (10, max(4, len(k_results) * 0.4))
    fig, ax = plt.subplots(figsize=_figsize)

    render_applicability_heatmap(ax, k_results, style=style, title=title)

    fig.tight_layout()
    return _fig_to_base64(fig, dpi=dpi)


# ── Multi-sample reliability matrix ──────────────────────────

def export_reliability_matrix(
    k_results_dict: Dict[str, list],
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] | None = None,
    dpi: int = 150,
    title: str = "Method Applicability Matrix \u2014 All Samples",
) -> str:
    """Return a base64-encoded PNG of a multi-sample reliability matrix."""
    apply_matplotlib_style()

    all_methods: set[str] = set()
    for results in k_results_dict.values():
        for r in results:
            all_methods.add(r.method_name)
    n_methods = len(all_methods)
    n_samples = len(k_results_dict)
    _figsize = figsize or (max(10, n_samples * 0.8), max(6, n_methods * 0.5))
    fig, ax = plt.subplots(figsize=_figsize)

    render_reliability_matrix(ax, k_results_dict, style=style, title=title)

    fig.tight_layout()
    return _fig_to_base64(fig, dpi=dpi)
