"""Helpers for K-value bar chart labels and compact method naming."""

from __future__ import annotations

from typing import Sequence


_COMPACT_METHOD_LABELS = {
    "Hazen_1892": "Hazen\n1892",
    "Kozeny-Carman": "Kozeny-\nCarman",
    "Alyamani-Sen": "Alyamani-\nSen",
    "Krumbein-Monk": "Krumbein-\nMonk",
}

_TINY_METHOD_LABELS = {
    "Hazen_1892": "Haz\n92",
    "Kozeny-Carman": "Koz-\nCar",
    "Alyamani-Sen": "Aly-\nSen",
    "Krumbein-Monk": "Kru-\nMon",
    "Sauerbrei": "Sauer",
    "Slichter": "Slich",
    "Terzaghi": "Terzag",
    "Shepherd": "Sheph",
    "Chapuis": "Chapu",
    "Zunker": "Zunk",
    "Zamarin": "Zamar",
}


def format_method_label(method: str, *, compact: bool = False, tiny: bool = False) -> str:
    """Return a readable method label for constrained plot axes."""
    if tiny:
        if method in _TINY_METHOD_LABELS:
            return _TINY_METHOD_LABELS[method]
        return method if len(method) <= 6 else method[:6]

    if compact:
        if method in _COMPACT_METHOD_LABELS:
            return _COMPACT_METHOD_LABELS[method]
        if "-" in method:
            head, tail = method.split("-", 1)
            return f"{head}-\n{tail}"
        if "_" in method:
            head, tail = method.split("_", 1)
            return f"{head}\n{tail}"

    return method


def compute_log_label_y(
    value: float,
    *,
    level: int = 0,
    base_offset_decades: float = 0.012,
    level_step_decades: float = 0.028,
) -> float:
    """Place a label just above a log-scale bar, with optional stagger levels."""
    safe_level = max(0, level)
    return value * (10 ** (base_offset_decades + safe_level * level_step_decades))


def apply_log_bar_limits(
    ax,
    values: Sequence[float],
    *,
    max_label_level: int = 0,
    bottom_factor: float = 3.0,
    base_offset_decades: float = 0.012,
    level_step_decades: float = 0.028,
    top_margin_decades: float = 0.065,
) -> None:
    """Set tighter default log-scale limits with enough room for bar labels."""
    positive_values = [float(value) for value in values if value and value > 0]
    if not positive_values:
        return

    highest = max(positive_values)
    label_top = compute_log_label_y(
        highest,
        level=max_label_level,
        base_offset_decades=base_offset_decades,
        level_step_decades=level_step_decades,
    )
    ax.set_yscale("log")
    ax.set_ylim(min(positive_values) / bottom_factor, label_top * (10 ** top_margin_decades))


def apply_linear_bar_limits(
    ax,
    values: Sequence[float],
    *,
    max_label_level: int = 0,
) -> None:
    """Set readable linear bar limits with room for value labels."""
    positive_values = [float(value) for value in values if value and value > 0]
    if not positive_values:
        return

    highest = max(positive_values)
    headroom = max(highest * 0.12, highest * (0.08 + max(0, max_label_level) * 0.035))
    ax.set_yscale("linear")
    ax.set_ylim(0.0, highest + headroom)


def annotate_log_bars(
    ax,
    bars,
    labels: Sequence[str],
    *,
    level_indices: Sequence[int] | None = None,
    base_offset_decades: float = 0.012,
    level_step_decades: float = 0.028,
    fontsize: float = 7.0,
    color: str = "#2f2419",
    add_bbox: bool = False,
) -> None:
    """Annotate positive log-scale bars with compact labels above the tops."""
    bar_list = list(bars)
    levels = list(level_indices) if level_indices is not None else [0] * len(bar_list)
    bbox = None
    if add_bbox:
        bbox = {
            "boxstyle": "round,pad=0.16",
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.78,
        }

    for bar, label, level in zip(bar_list, labels, levels):
        height = bar.get_height()
        if not label or height <= 0:
            continue

        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            compute_log_label_y(
                height,
                level=level,
                base_offset_decades=base_offset_decades,
                level_step_decades=level_step_decades,
            ),
            label,
            ha="center",
            va="bottom",
            fontsize=fontsize,
            color=color,
            clip_on=False,
            zorder=5,
            bbox=bbox,
        )


def annotate_linear_bars(
    ax,
    bars,
    labels: Sequence[str],
    *,
    level_indices: Sequence[int] | None = None,
    base_offset_fraction: float = 0.014,
    level_step_fraction: float = 0.030,
    fontsize: float = 7.0,
    color: str = "#2f2419",
    add_bbox: bool = False,
) -> None:
    """Annotate positive linear-scale bars above the tops."""
    bar_list = list(bars)
    levels = list(level_indices) if level_indices is not None else [0] * len(bar_list)
    y0, y1 = ax.get_ylim()
    span = float(y1) - float(y0)
    if span <= 0:
        span = max((bar.get_height() for bar in bar_list if bar.get_height() > 0), default=1.0)
    bbox = None
    if add_bbox:
        bbox = {
            "boxstyle": "round,pad=0.16",
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.78,
        }

    for bar, label, level in zip(bar_list, labels, levels):
        height = bar.get_height()
        if not label or height <= 0:
            continue
        safe_level = max(0, level)
        y = height + span * (base_offset_fraction + safe_level * level_step_fraction)
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            y,
            label,
            ha="center",
            va="bottom",
            fontsize=fontsize,
            color=color,
            clip_on=False,
            zorder=5,
            bbox=bbox,
        )
