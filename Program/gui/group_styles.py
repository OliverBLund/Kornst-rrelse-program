"""Shared presentation settings for dataset groups."""

from __future__ import annotations

import json
from typing import Iterable, Mapping, Sequence

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor

from k_aggregation import UNGROUPED_LABEL, normalize_group_name


DEFAULT_GROUP_COLORS: tuple[str, ...] = (
    "#3a7ea0",
    "#6b8e23",
    "#b46428",
    "#2a9d8f",
    "#8b4580",
    "#a03a30",
    "#4a6a9a",
    "#7a6a28",
)

LINE_STYLE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("-", "Solid"),
    ("--", "Dashed"),
    (":", "Dotted"),
    ("-.", "Dash-dot"),
    ("-|o", "Solid + circle markers"),
    ("--|s", "Dashed + square markers"),
    (":|^", "Dotted + triangle markers"),
    ("-.|D", "Dash-dot + diamond markers"),
)
DEFAULT_LINE_STYLE_CYCLE: tuple[str, ...] = tuple(style for style, _label in LINE_STYLE_OPTIONS)

UNGROUPED_COLOR = "#9a8f7f"
_SETTINGS_KEY = "group_color_overrides"
_LINE_STYLE_SETTINGS_KEY = "dataset_line_style_overrides"
_OVERRIDE_CACHE: dict[str, str] | None = None
_LINE_STYLE_CACHE: dict[str, str] | None = None


def _settings() -> QSettings:
    return QSettings("GrainSizeAnalysis", "GroupStyles")


def _valid_hex_color(value: object) -> str | None:
    color = QColor(str(value or "").strip())
    return color.name() if color.isValid() else None


def _valid_line_style(value: object) -> str | None:
    text = str(value or "").strip()
    valid = {style for style, _label in LINE_STYLE_OPTIONS}
    return text if text in valid else None


def dataset_series_key(dataset: object) -> str:
    """Return a stable presentation key for a dataset-like object."""
    for attr in ("file_path", "source_path", "path"):
        value = str(getattr(dataset, attr, "") or "").strip()
        if value:
            return value
    return str(getattr(dataset, "sample_name", "") or "Dataset").strip() or "Dataset"


def _ordered_named_groups(group_names: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    for group_name in group_names:
        normalized = normalize_group_name(group_name)
        if normalized == UNGROUPED_LABEL or normalized in ordered:
            continue
        ordered.append(normalized)
    return ordered


def load_group_color_overrides() -> dict[str, str]:
    global _OVERRIDE_CACHE
    if _OVERRIDE_CACHE is not None:
        return dict(_OVERRIDE_CACHE)

    raw = _settings().value(_SETTINGS_KEY, "")
    if not raw:
        _OVERRIDE_CACHE = {}
        return {}
    try:
        loaded = json.loads(str(raw))
    except (TypeError, ValueError):
        _OVERRIDE_CACHE = {}
        return {}
    if not isinstance(loaded, Mapping):
        _OVERRIDE_CACHE = {}
        return {}
    cleaned: dict[str, str] = {}
    for group_name, color in loaded.items():
        normalized = normalize_group_name(group_name)
        if normalized == UNGROUPED_LABEL:
            continue
        hex_color = _valid_hex_color(color)
        if hex_color:
            cleaned[normalized] = hex_color
    _OVERRIDE_CACHE = dict(cleaned)
    return dict(cleaned)


def save_group_color_overrides(overrides: Mapping[str, str]) -> None:
    global _OVERRIDE_CACHE
    cleaned: dict[str, str] = {}
    for group_name, color in overrides.items():
        normalized = normalize_group_name(group_name)
        if normalized == UNGROUPED_LABEL:
            continue
        hex_color = _valid_hex_color(color)
        if hex_color:
            cleaned[normalized] = hex_color
    _OVERRIDE_CACHE = dict(cleaned)
    settings = _settings()
    settings.setValue(_SETTINGS_KEY, json.dumps(cleaned, sort_keys=True))
    settings.sync()


def load_dataset_line_style_overrides() -> dict[str, str]:
    global _LINE_STYLE_CACHE
    if _LINE_STYLE_CACHE is not None:
        return dict(_LINE_STYLE_CACHE)

    raw = _settings().value(_LINE_STYLE_SETTINGS_KEY, "")
    if not raw:
        _LINE_STYLE_CACHE = {}
        return {}
    try:
        loaded = json.loads(str(raw))
    except (TypeError, ValueError):
        _LINE_STYLE_CACHE = {}
        return {}
    if not isinstance(loaded, Mapping):
        _LINE_STYLE_CACHE = {}
        return {}
    cleaned: dict[str, str] = {}
    for key, style in loaded.items():
        dataset_key = str(key or "").strip()
        valid_style = _valid_line_style(style)
        if dataset_key and valid_style:
            cleaned[dataset_key] = valid_style
    _LINE_STYLE_CACHE = dict(cleaned)
    return dict(cleaned)


def save_dataset_line_style_overrides(overrides: Mapping[str, str]) -> None:
    global _LINE_STYLE_CACHE
    cleaned: dict[str, str] = {}
    for key, style in overrides.items():
        dataset_key = str(key or "").strip()
        valid_style = _valid_line_style(style)
        if dataset_key and valid_style:
            cleaned[dataset_key] = valid_style
    _LINE_STYLE_CACHE = dict(cleaned)
    settings = _settings()
    settings.setValue(_LINE_STYLE_SETTINGS_KEY, json.dumps(cleaned, sort_keys=True))
    settings.sync()


def set_dataset_line_style(dataset_key: str, line_style: str) -> str:
    key = str(dataset_key or "").strip()
    if not key:
        return "-"
    valid_style = _valid_line_style(line_style)
    if valid_style is None:
        raise ValueError(f"Invalid line style: {line_style!r}")
    overrides = load_dataset_line_style_overrides()
    overrides[key] = valid_style
    save_dataset_line_style_overrides(overrides)
    return valid_style


def clear_dataset_line_style(dataset_key: str) -> None:
    key = str(dataset_key or "").strip()
    overrides = load_dataset_line_style_overrides()
    if key in overrides:
        del overrides[key]
        save_dataset_line_style_overrides(overrides)


def line_style_label(line_style: str) -> str:
    labels = {style: label for style, label in LINE_STYLE_OPTIONS}
    return labels.get(line_style, "Solid")


def series_style_parts(line_style: str) -> tuple[str, str | None]:
    """Return matplotlib ``(linestyle, marker)`` parts for a stored style key."""
    valid_lines = {"-", "--", ":", "-."}
    valid_markers = {"o", "s", "^", "D"}
    text = str(line_style or "-").strip()
    line_part, marker_part = (text.split("|", 1) + [""])[:2]
    line = line_part if line_part in valid_lines else "-"
    marker = marker_part if marker_part in valid_markers else None
    return line, marker


def default_line_style(member_index: int) -> str:
    return DEFAULT_LINE_STYLE_CYCLE[member_index % len(DEFAULT_LINE_STYLE_CYCLE)]


def dataset_line_style(dataset_key: str, default_style: str = "-") -> str:
    key = str(dataset_key or "").strip()
    overrides = load_dataset_line_style_overrides()
    return overrides.get(key, _valid_line_style(default_style) or "-")


def set_group_color(group_name: str, color: str) -> str:
    normalized = normalize_group_name(group_name)
    if normalized == UNGROUPED_LABEL:
        return UNGROUPED_COLOR
    hex_color = _valid_hex_color(color)
    if not hex_color:
        raise ValueError(f"Invalid color: {color!r}")
    overrides = load_group_color_overrides()
    overrides[normalized] = hex_color
    save_group_color_overrides(overrides)
    return hex_color


def clear_group_color(group_name: str) -> None:
    normalized = normalize_group_name(group_name)
    overrides = load_group_color_overrides()
    if normalized in overrides:
        del overrides[normalized]
        save_group_color_overrides(overrides)


def default_group_color(
    group_name: str,
    group_names: Sequence[str] | None = None,
    *,
    palette: Sequence[str] = DEFAULT_GROUP_COLORS,
) -> str:
    normalized = normalize_group_name(group_name)
    if normalized == UNGROUPED_LABEL:
        return UNGROUPED_COLOR

    named_groups = _ordered_named_groups(group_names or [normalized])
    try:
        index = named_groups.index(normalized)
    except ValueError:
        index = 0
    colors = tuple(palette or DEFAULT_GROUP_COLORS)
    return colors[index % len(colors)]


def group_color(
    group_name: str,
    group_names: Sequence[str] | None = None,
    *,
    palette: Sequence[str] = DEFAULT_GROUP_COLORS,
) -> str:
    normalized = normalize_group_name(group_name)
    if normalized == UNGROUPED_LABEL:
        return UNGROUPED_COLOR
    overrides = load_group_color_overrides()
    return overrides.get(
        normalized,
        default_group_color(normalized, group_names, palette=palette),
    )


def group_color_map(
    group_names: Sequence[str],
    *,
    palette: Sequence[str] = DEFAULT_GROUP_COLORS,
    include_ungrouped: bool = True,
    ignore_overrides: bool = False,
) -> dict[str, str]:
    """Map each group to a colour from *palette* (in first-seen order).

    By default a user's persisted per-group colour override wins over the
    palette. Pass ``ignore_overrides=True`` to make the palette authoritative
    (used by reports/exports when a non-Categorical palette is chosen, so the
    palette re-colours every group regardless of Comparison-tab tweaks).
    """
    ordered = [normalize_group_name(group_name) for group_name in group_names]
    colors: dict[str, str] = {}
    for group_name in dict.fromkeys(ordered):
        if group_name == UNGROUPED_LABEL and not include_ungrouped:
            continue
        if ignore_overrides:
            colors[group_name] = default_group_color(group_name, ordered, palette=palette)
        else:
            colors[group_name] = group_color(group_name, ordered, palette=palette)
    return colors
