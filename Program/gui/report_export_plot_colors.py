"""Shared colour allocation for report/export plot renderers."""

from __future__ import annotations

from typing import Iterable, Sequence

from k_aggregation import UNGROUPED_LABEL

from .plot_constants import CATEGORICAL_PALETTE, DATASET_COLORS
from .report_plot_style import get_report_palette, resolve_report_palette_colors


def _first_unused_color(
    colors: Sequence[str],
    used: Iterable[str],
    fallback: str,
) -> str:
    used_set = set(used)
    for color in colors:
        if color not in used_set:
            return color
    return colors[0] if colors else fallback


def k_scope_plot_colors(
    group_names: Iterable[str],
    series: Sequence[tuple[str, Sequence[float]]],
) -> list[str]:
    """Return report/export colors for K scope boxplot series.

    The active palette is sampled to the actual rendered series count so
    ungrouped datasets spread across a colormap instead of falling through to a
    renderer default. Named groups still honor persisted group colors for the
    Categorical palette; non-Categorical palettes are authoritative.
    """

    labels = [str(label) for label, _values in series]
    if not labels:
        return []

    palette_name = get_report_palette()
    authoritative = palette_name != CATEGORICAL_PALETTE
    series_palette = resolve_report_palette_colors(len(labels)) or list(DATASET_COLORS)

    named_groups = [
        str(group)
        for group in group_names
        if group and str(group) != UNGROUPED_LABEL
    ]
    group_colors: dict[str, str] = {}
    if named_groups:
        group_palette = resolve_report_palette_colors(len(named_groups)) or series_palette
        try:
            from .group_styles import group_color_map

            group_colors = group_color_map(
                named_groups,
                palette=group_palette,
                include_ungrouped=False,
                ignore_overrides=authoritative,
            )
        except Exception:
            group_colors = {
                group: group_palette[index % len(group_palette)]
                for index, group in enumerate(named_groups)
            }

    fallback_by_label = {
        label: series_palette[index % len(series_palette)]
        for index, label in enumerate(labels)
    }
    overall_color = _first_unused_color(
        series_palette,
        group_colors.values(),
        fallback_by_label.get("Overall", DATASET_COLORS[0]),
    )

    return [
        overall_color if label == "Overall"
        else group_colors.get(label, fallback_by_label[label])
        for label in labels
    ]
