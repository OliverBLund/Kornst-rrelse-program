"""Shared helpers for capturing and replaying live grain-size plot state."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from grain_classification import ISO14688

from .plot_styles import PROFESSIONAL_STYLE, PlotStyle
from .plot_text_options import (
    DEFAULT_X_LABEL,
    DEFAULT_Y_LABEL,
    default_plot_title,
    plot_text_options_to_context,
)


def plot_context_value(context: Optional[Dict[str, Any]], key: str, default: Any) -> Any:
    if context and key in context:
        return context[key]
    return default


def plot_style_from_context(
    context: Optional[Dict[str, Any]],
    default_style: PlotStyle = PROFESSIONAL_STYLE,
) -> PlotStyle:
    style = plot_context_value(context, "style", default_style)
    return style if style is not None else PROFESSIONAL_STYLE


def plot_text_renderer_kwargs_from_context(
    sample_name: str,
    context: Optional[Dict[str, Any]] = None,
    *,
    default_title: Optional[str] = None,
    default_show_title: bool = True,
    default_x_label: str = DEFAULT_X_LABEL,
    default_y_label: str = DEFAULT_Y_LABEL,
    default_show_x_label: bool = True,
    default_show_y_label: bool = True,
) -> Dict[str, Any]:
    title_default = default_title or default_plot_title(sample_name)
    title = plot_context_value(context, "plot_title", title_default) or title_default
    x_label = plot_context_value(context, "plot_x_label", default_x_label) or default_x_label
    y_label = plot_context_value(context, "plot_y_label", default_y_label) or default_y_label
    return {
        "show_title": bool(plot_context_value(context, "show_title", default_show_title)),
        "title": title,
        "show_x_label": bool(plot_context_value(context, "show_x_label", default_show_x_label)),
        "x_label": x_label,
        "show_y_label": bool(plot_context_value(context, "show_y_label", default_show_y_label)),
        "y_label": y_label,
    }


def grain_size_renderer_kwargs_from_context(
    sample_name: str,
    dataset: Any = None,
    context: Optional[Dict[str, Any]] = None,
    *,
    default_style: PlotStyle = PROFESSIONAL_STYLE,
    default_show_d_lines: bool = True,
    default_show_markers: bool = False,
    default_show_grid: bool = True,
    default_show_legend: bool = True,
    default_show_classification_zones: bool = False,
    default_classification_scheme: Any = None,
    default_fill_curve: bool = False,
    default_fill_zone_labels: bool = False,
    default_title: Optional[str] = None,
    default_show_title: bool = True,
    default_x_label: str = DEFAULT_X_LABEL,
    default_y_label: str = DEFAULT_Y_LABEL,
    default_show_x_label: bool = True,
    default_show_y_label: bool = True,
    include_grid: bool = True,
    include_legend: bool = True,
) -> Dict[str, Any]:
    """Build renderer kwargs from a captured live-plot context."""
    scheme_default = default_classification_scheme if default_classification_scheme is not None else ISO14688
    kwargs = {
        "sample_name": sample_name,
        "style": plot_style_from_context(context, default_style),
        "show_d_lines": bool(plot_context_value(context, "show_d_lines", default_show_d_lines)),
        "show_markers": bool(plot_context_value(context, "show_markers", default_show_markers)),
        "show_grid": bool(include_grid and plot_context_value(context, "show_grid", default_show_grid)),
        "show_legend": bool(include_legend and plot_context_value(context, "show_legend", default_show_legend)),
        "show_classification_zones": bool(
            plot_context_value(context, "show_classification_zones", default_show_classification_zones)
        ),
        "classification_scheme": plot_context_value(context, "classification_scheme", scheme_default),
        "fill_curve": bool(plot_context_value(context, "fill_curve", default_fill_curve)),
        "fill_zone_labels": bool(plot_context_value(context, "fill_zone_labels", default_fill_zone_labels)),
    }
    if dataset is not None:
        kwargs["grain_size_data"] = dataset
    kwargs.update(
        plot_text_renderer_kwargs_from_context(
            sample_name,
            context,
            default_title=default_title,
            default_show_title=default_show_title,
            default_x_label=default_x_label,
            default_y_label=default_y_label,
            default_show_x_label=default_show_x_label,
            default_show_y_label=default_show_y_label,
        )
    )
    return kwargs


def apply_axis_limits_from_context(ax: Any, context: Optional[Dict[str, Any]]) -> None:
    axis_limits = plot_context_value(context, "axis_limits", None)
    if not axis_limits:
        return
    xlim = axis_limits.get("xlim")
    ylim = axis_limits.get("ylim")
    if xlim is not None:
        ax.set_xlim(*xlim)
    if ylim is not None:
        ax.set_ylim(*ylim)


def build_plot_context_from_tab(tab: Any, default_scheme: Any = None) -> Dict[str, Any]:
    """Capture the current distribution-plot state from a dataset tab."""
    try:
        workspace = tab.plot_workspace
        plot_widget = workspace.plot_widget
    except Exception:
        return {}

    try:
        style = (
            workspace._effective_style()
            if hasattr(workspace, "_effective_style")
            else getattr(plot_widget, "current_style", None)
        )
        context = {
            "style": style,
            "show_grid": getattr(workspace, "show_grid", True),
            "show_legend": getattr(workspace, "show_legend", True),
            "show_d_lines": getattr(workspace, "show_dlines", True),
            "show_markers": getattr(workspace, "show_markers", False),
            "show_classification_zones": getattr(workspace, "show_zones", False),
            "fill_curve": getattr(workspace, "fill_curve", False),
            "fill_zone_labels": getattr(workspace, "fill_zone_labels", False),
            "log_k_y_scale": getattr(workspace, "log_k_y_scale", False),
            "classification_scheme": getattr(
                plot_widget,
                "_scheme",
                default_scheme if default_scheme is not None else ISO14688,
            ),
        }
        if hasattr(plot_widget, "plot_text_options"):
            context.update(plot_text_options_to_context(plot_widget.plot_text_options))
        current_ax = getattr(plot_widget, "current_ax", None)
        if (
            getattr(workspace, "current_plot_type", "distribution") == "distribution"
            and current_ax is not None
        ):
            context["axis_limits"] = {
                "xlim": current_ax.get_xlim(),
                "ylim": current_ax.get_ylim(),
            }
        return context
    except Exception:
        return {}


def build_plot_contexts_from_tabs(
    tabs: Iterable[Any],
    default_scheme: Any = None,
) -> list[Dict[str, Any]]:
    return [build_plot_context_from_tab(tab, default_scheme) for tab in tabs]
