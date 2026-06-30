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
import math
from typing import Dict, List, Optional, Sequence, Set

import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402
from matplotlib.colors import to_rgba    # noqa: E402
from matplotlib.figure import Figure     # noqa: E402

import importlib as _il  # noqa: E402

# Import submodules directly to avoid triggering gui/__init__.py
# (which imports MainWindow → reporting_tab → report_generator → here,
#  causing a circular import).
_renderers = _il.import_module("gui.plot_renderers")
_styles    = _il.import_module("gui.plot_styles")
_theme     = _il.import_module("gui.theme")
_plot_ctx  = _il.import_module("gui.plot_context")
_cmp_spec  = _il.import_module("gui.comparison_plot_spec")

render_grain_size_distribution = _renderers.render_grain_size_distribution
render_k_bar_chart             = _renderers.render_k_bar_chart
render_distribution_overlay    = _renderers.render_distribution_overlay
render_k_overlay               = _renderers.render_k_overlay
render_k_boxplot               = _renderers.render_k_boxplot
render_k_scope_boxplot         = _renderers.render_k_scope_boxplot
render_applicability_heatmap   = _renderers.render_applicability_heatmap
render_reliability_matrix      = _renderers.render_reliability_matrix
apply_legend_aware_layout      = _renderers.apply_legend_aware_layout
render_comparison              = _cmp_spec.render_comparison
apply_axis_limits_from_context = _plot_ctx.apply_axis_limits_from_context
grain_size_renderer_kwargs_from_context = _plot_ctx.grain_size_renderer_kwargs_from_context

PlotStyle          = _styles.PlotStyle
PROFESSIONAL_STYLE = _styles.PROFESSIONAL_STYLE
apply_matplotlib_style = _theme.apply_matplotlib_style
C = _theme.C
F = _theme.F


# ── Helper ────────────────────────────────────────────────────

def _new_fig(figsize) -> Figure:
    """Create a standalone Agg figure (no pyplot global state → thread-safe).

    Report generation runs on a worker thread; using pyplot's global figure
    registry off the main thread is unsafe, so every report figure is built as a
    bare ``Figure`` with its own ``FigureCanvasAgg``.
    """
    fig = Figure(figsize=figsize)
    FigureCanvasAgg(fig)
    return fig


def _apply_comparison_spec_layout(fig: Figure, spec) -> None:
    apply_legend_aware_layout(fig, spec.style)


def _new_fig_ax(figsize):
    """Return ``(figure, axes)`` for a fresh single-axes Agg figure."""
    fig = _new_fig(figsize)
    ax = fig.add_subplot(1, 1, 1)
    return fig, ax


def _fig_to_base64(fig: Figure, *, dpi: int = 220) -> str:
    """Render *fig* to a base64-encoded PNG data-URL.

    No ``plt.close`` is needed — the figure carries its own canvas and holds no
    pyplot registry reference, so it is freed when it goes out of scope.
    """
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor="white")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


# ── Single-sample grain-size distribution ─────────────────────

def export_grain_size_plot(
    dataset,
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] = (10, 6),
    dpi: int = 220,
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
    fig, ax = _new_fig_ax(figsize)
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
    reference_values: Optional[list[float]] = None,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] = (12, 6),
    dpi: int = 220,
    show_grid: bool = True,
    show_legend: bool = True,
    show_reference_lines: bool = True,
    show_value_labels: bool = True,
    log_y_scale: bool = False,
    title: Optional[str] = None,
    y_label: str = "Hydraulic Conductivity K (m/s)",
    sample_name: str = "Sample",
    colors: Optional[Sequence[str]] = None,
) -> str:
    """Return a base64-encoded PNG of a K-value bar chart.

    *colors* (one per method) overrides the bar colours so reports/exports can
    drive them from the global palette instead of the preset.
    """
    apply_matplotlib_style()
    fig, ax = _new_fig_ax(figsize)

    render_k_bar_chart(
        ax, methods, k_values,
        flagged_methods=flagged_methods,
        reference_values=reference_values,
        style=style,
        show_grid=show_grid,
        show_legend=show_legend,
        show_reference_lines=show_reference_lines,
        show_value_labels=show_value_labels,
        log_y_scale=log_y_scale,
        title=title,
        y_label=y_label,
        sample_name=sample_name,
        colors=colors,
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
    dpi: int = 220,
    show_grid: bool = True,
    show_legend: bool = True,
    title: str = "Grain Size Distribution Comparison",
) -> str:
    """Return a base64-encoded PNG of overlaid grain-size curves."""
    apply_matplotlib_style()
    fig, ax = _new_fig_ax(figsize)

    render_distribution_overlay(
        ax, datasets,
        labels=labels, colors=colors, style=style,
        show_grid=show_grid, show_legend=show_legend, title=title,
    )

    apply_legend_aware_layout(fig, style)
    return _fig_to_base64(fig, dpi=dpi)


# ── Comparison plot via the shared render spec ───────────────

def export_comparison_spec(
    spec,
    *,
    figsize: tuple[float, float] = (12, 7),
    dpi: int = 220,
) -> str:
    """Return a base64-encoded PNG of a comparison plot rendered from *spec*.

    Uses the same ``render_comparison`` pipeline as the Comparison tab, so the
    report/export plot matches the GUI (group breakdown, group colours,
    line styles, display unit, log-K). *spec* is a ``ComparisonPlotSpec``.
    """
    apply_matplotlib_style()
    fig = _new_fig(figsize)
    fig.patch.set_facecolor(getattr(spec.style, "figure_facecolor", "white"))
    render_comparison(fig, spec)
    _apply_comparison_spec_layout(fig, spec)
    return _fig_to_base64(fig, dpi=dpi)


# ── Multi-sample K-value grouped bars ────────────────────────

def export_k_overlay(
    k_results_dict: Dict[str, Dict[str, float]],
    *,
    flagged_methods_dict: Optional[Dict[str, Set[str]]] = None,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] = (12, 7),
    dpi: int = 220,
    show_grid: bool = True,
    show_legend: bool = True,
    show_value_labels: bool = True,
    log_y_scale: bool = False,
    title: str = "Hydraulic Conductivity Comparison",
) -> str:
    """Return a base64-encoded PNG of grouped K-value bars."""
    apply_matplotlib_style()
    fig, ax = _new_fig_ax(figsize)

    render_k_overlay(
        ax, k_results_dict,
        flagged_methods_dict=flagged_methods_dict,
        style=style,
        show_grid=show_grid,
        show_legend=show_legend,
        show_value_labels=show_value_labels,
        log_y_scale=log_y_scale,
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
    dpi: int = 220,
    show_grid: bool = True,
    title: str = "K-Value Distribution Comparison",
) -> str:
    """Return a base64-encoded PNG of K-value boxplots."""
    apply_matplotlib_style()
    fig, ax = _new_fig_ax(figsize)

    render_k_boxplot(
        ax, k_results_dict,
        style=style,
        show_grid=show_grid,
        title=title,
    )

    fig.tight_layout()
    return _fig_to_base64(fig, dpi=dpi)


# ── Single-sample applicability heatmap ──────────────────────

def export_k_scope_boxplot(
    scope_values,
    *,
    colors: Optional[List[str]] = None,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] = (12, 7),
    dpi: int = 220,
    show_grid: bool = True,
    title: str = "Hydraulic Conductivity Distribution by Scope",
) -> str:
    """Return a base64-encoded PNG of grouped/dataset K-value boxplots."""
    apply_matplotlib_style()
    fig, ax = _new_fig_ax(figsize)
    _render_statistics_scope_boxplot(
        ax,
        scope_values,
        colors=colors,
        show_grid=show_grid,
        title=title.replace("Hydraulic Conductivity", "K-value"),
        style=style,
    )

    fig.tight_layout()
    return _fig_to_base64(fig, dpi=dpi)


def _render_statistics_scope_boxplot(
    ax,
    scope_values,
    *,
    colors: Optional[Sequence[str]] = None,
    show_grid: bool = True,
    title: str = "K-value Distribution by Scope",
    style: PlotStyle = PROFESSIONAL_STYLE,
) -> None:
    """Render report K boxplots to match Comparison > Statistics defaults.

    Typography (title/axis/tick sizes) follows *style* so the global report
    Customize panel themes this plot like the others.
    """
    foreground = "#000000"
    raw_items = list(scope_values.items()) if isinstance(scope_values, dict) else list(scope_values)
    color_list = list(colors or [])
    plot_data: list[list[float]] = []
    plot_labels: list[str] = []
    plot_colors: list[str] = []

    for index, (label, values) in enumerate(raw_items):
        clean_values = []
        for value in values or []:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric) and numeric > 0:
                clean_values.append(numeric)
        if not clean_values:
            continue
        plot_data.append(clean_values)
        plot_labels.append(_short_scope_label(str(label)))
        plot_colors.append(color_list[index] if index < len(color_list) else C.TEXT_MID)

    ax.set_facecolor("#ffffff")
    if not plot_data:
        ax.text(
            0.5,
            0.5,
            "No K data available",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color=foreground,
            fontsize=11,
        )
        return

    bp = ax.boxplot(
        plot_data,
        tick_labels=plot_labels,
        patch_artist=True,
        medianprops={"color": foreground, "linewidth": 1.5},
        whiskerprops={"color": foreground, "linewidth": 1.0},
        capprops={"color": foreground, "linewidth": 1.0},
        flierprops={"marker": "o", "markersize": 4, "alpha": 0.6},
    )
    for patch, color in zip(bp["boxes"], plot_colors):
        patch.set_facecolor(to_rgba(color, 0.24))
        patch.set_edgecolor(color)
        patch.set_linewidth(1.2)

    marker_values = [
        float(math.exp(sum(math.log(value) for value in values) / len(values)))
        for values in plot_data
    ]
    ax.scatter(
        range(1, len(plot_data) + 1),
        marker_values,
        marker="D",
        s=34,
        color=foreground,
        edgecolors="white",
        linewidths=0.8,
        zorder=4,
    )

    ax.set_yscale("log")
    ax.set_ylabel("K (m/s)", color=foreground, fontsize=style.label_fontsize)
    ax.set_title(title, color=foreground,
                 fontsize=style.title_fontsize, fontweight=style.title_fontweight)
    many_scopes = len(plot_labels) > 6
    ax.tick_params(
        axis="x",
        labelrotation=18 if many_scopes else 0,
        labelsize=max(6, style.tick_fontsize - 1) if many_scopes else style.tick_fontsize,
        colors=foreground,
    )
    ax.tick_params(axis="y", labelsize=style.tick_fontsize, colors=foreground)
    for idx, tick_label in enumerate(ax.get_xticklabels()):
        tick_label.set_color(foreground)
        tick_label.set_ha("right" if many_scopes else "center")
    if show_grid:
        ax.grid(True, which="both", linestyle="--", alpha=0.18, color=foreground)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(foreground)
    ax.spines["bottom"].set_color(foreground)
    ax.text(
        0.99,
        0.98,
        "Marker: Geo. mean",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        color=foreground,
        family=F.MONO,
    )


def _short_scope_label(label: str, max_chars: int = 26) -> str:
    text = str(label or "")
    return text if len(text) <= max_chars else f"{text[:max_chars - 1]}..."


def export_applicability_heatmap(
    k_results: list,
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] | None = None,
    dpi: int = 220,
    title: str = "Method Applicability Status",
) -> str:
    """Return a base64-encoded PNG of a method applicability heatmap."""
    apply_matplotlib_style()
    _figsize = figsize or (10, max(4, len(k_results) * 0.4))
    fig, ax = _new_fig_ax(_figsize)

    render_applicability_heatmap(ax, k_results, style=style, title=title)

    fig.tight_layout()
    return _fig_to_base64(fig, dpi=dpi)


# ── Multi-sample reliability matrix ──────────────────────────

def export_reliability_matrix(
    k_results_dict: Dict[str, list],
    *,
    style: PlotStyle = PROFESSIONAL_STYLE,
    figsize: tuple[float, float] | None = None,
    dpi: int = 220,
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
    fig, ax = _new_fig_ax(_figsize)

    render_reliability_matrix(ax, k_results_dict, style=style, title=title)

    fig.tight_layout()
    return _fig_to_base64(fig, dpi=dpi)
