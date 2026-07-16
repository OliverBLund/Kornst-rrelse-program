"""Persisted global plot style for reports and exports.

A single preset + optional custom field overrides drive every report/export
plot, so the user themes them once instead of per output.  Mirrors the
``gui/group_styles.py`` persistence pattern (QSettings + a small in-process
cache) and resolves to a ``PlotStyle`` the headless report/export code can use.

The GUI Individual/Comparison tabs keep their own per-tab style selectors for
now; this store is the report/export side of the "restyle once" workflow.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Dict

from PyQt6.QtCore import QSettings

from .plot_styles import PlotStyle, get_available_style_names, get_style
from .plot_constants import CATEGORICAL_PALETTE, PALETTE_NAMES, palette_colors


# Override fields the customize panel may set, with light type coercion so a
# round-trip through JSON/QSettings restores the right Python types. Mirrors the
# fields the per-tab style panels expose (typography + legend placement).
_INT_FIELDS = {
    "title_fontsize", "label_fontsize", "tick_fontsize", "legend_fontsize",
    "legend_ncol",
}
_FLOAT_FIELDS = {
    "legend_framealpha", "curve_linewidth", "curve_markersize",
}
_BOOL_FIELDS = {"curve_markers_visible"}
_STR_FIELDS = {"legend_loc"}
_TUPLE_FIELDS = {"legend_bbox_to_anchor"}  # (x, y) or None
ALLOWED_OVERRIDE_FIELDS = (
    _INT_FIELDS | _FLOAT_FIELDS | _BOOL_FIELDS | _STR_FIELDS | _TUPLE_FIELDS
)

_PRESET_KEY = "report_plot_style_preset"
_OVERRIDES_KEY = "report_plot_style_overrides"
_PALETTE_KEY = "report_plot_palette"
_PRESET_CACHE: str | None = None
_OVERRIDES_CACHE: Dict[str, Any] | None = None
_PALETTE_CACHE: str | None = None


def _settings() -> QSettings:
    return QSettings("GrainSizeAnalysis", "ReportPlotStyle")


def _default_preset() -> str:
    names = get_available_style_names()
    return names[0] if names else "Professional"


def get_report_style_preset() -> str:
    """Return the persisted preset name (defaults to the first available)."""
    global _PRESET_CACHE
    if _PRESET_CACHE is not None:
        return _PRESET_CACHE
    raw = _settings().value(_PRESET_KEY, "")
    name = str(raw or "").strip()
    if name not in set(get_available_style_names()):
        name = _default_preset()
    _PRESET_CACHE = name
    return name


def set_report_style_preset(name: str) -> str:
    """Persist the chosen preset; clears stale overrides' base implicitly."""
    global _PRESET_CACHE
    valid = name if name in set(get_available_style_names()) else _default_preset()
    _PRESET_CACHE = valid
    settings = _settings()
    settings.setValue(_PRESET_KEY, valid)
    settings.sync()
    return valid


def _coerce_override(field: str, value: Any) -> Any | None:
    try:
        if field in _INT_FIELDS:
            return int(value)
        if field in _FLOAT_FIELDS:
            return float(value)
        if field in _BOOL_FIELDS:
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in {"true", "1", "yes"}:
                return True
            if text in {"false", "0", "no"}:
                return False
            return None
        if field in _STR_FIELDS:
            text = str(value).strip()
            return text or None
        if field in _TUPLE_FIELDS:
            if value is None:
                return None
            seq = list(value)
            return (float(seq[0]), float(seq[1])) if len(seq) == 2 else None
    except (TypeError, ValueError, IndexError):
        return None
    return None


def get_report_style_overrides() -> Dict[str, Any]:
    """Return the persisted custom field overrides (validated)."""
    global _OVERRIDES_CACHE
    if _OVERRIDES_CACHE is not None:
        return dict(_OVERRIDES_CACHE)
    raw = _settings().value(_OVERRIDES_KEY, "")
    cleaned: Dict[str, Any] = {}
    if raw:
        try:
            loaded = json.loads(str(raw))
        except (TypeError, ValueError):
            loaded = {}
        if isinstance(loaded, dict):
            for field, value in loaded.items():
                if field not in ALLOWED_OVERRIDE_FIELDS:
                    continue
                coerced = _coerce_override(field, value)
                if coerced is not None or (field in _TUPLE_FIELDS and value is None):
                    cleaned[field] = coerced
    _OVERRIDES_CACHE = dict(cleaned)
    return dict(cleaned)


def set_report_style_overrides(overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Persist custom field overrides (only allowed, coercible fields kept)."""
    global _OVERRIDES_CACHE
    cleaned: Dict[str, Any] = {}
    for field, value in (overrides or {}).items():
        if field not in ALLOWED_OVERRIDE_FIELDS:
            continue
        coerced = _coerce_override(field, value)
        if coerced is not None or (field in _TUPLE_FIELDS and value is None):
            cleaned[field] = coerced
    _OVERRIDES_CACHE = dict(cleaned)
    settings = _settings()
    # legend_bbox_to_anchor tuples serialize as lists in JSON; resolve() restores.
    settings.setValue(_OVERRIDES_KEY, json.dumps(cleaned, sort_keys=True))
    settings.sync()
    return dict(cleaned)


def clear_report_style_overrides() -> None:
    """Revert to the bare preset (drop all custom field overrides)."""
    set_report_style_overrides({})


def get_report_palette() -> str:
    """Return the persisted palette name (defaults to Categorical)."""
    global _PALETTE_CACHE
    if _PALETTE_CACHE is not None:
        return _PALETTE_CACHE
    raw = str(_settings().value(_PALETTE_KEY, "") or "").strip()
    name = next(
        (p for p in PALETTE_NAMES if p.lower() == raw.lower()),
        CATEGORICAL_PALETTE,
    )
    _PALETTE_CACHE = name
    return name


def set_report_palette(name: str) -> str:
    """Persist the chosen palette name (validated against PALETTE_NAMES)."""
    global _PALETTE_CACHE
    valid = next(
        (p for p in PALETTE_NAMES if p.lower() == str(name or "").strip().lower()),
        CATEGORICAL_PALETTE,
    )
    _PALETTE_CACHE = valid
    settings = _settings()
    settings.setValue(_PALETTE_KEY, valid)
    settings.sync()
    return valid


def resolve_report_palette_colors(n: int) -> list[str]:
    """Return *n* colours for the persisted palette (Categorical → DATASET_COLORS)."""
    return palette_colors(get_report_palette(), n)


def resolve_report_style() -> PlotStyle:
    """Return the persisted preset with any custom field overrides applied."""
    style = get_style(get_report_style_preset())
    overrides = get_report_style_overrides()
    if not overrides:
        return style
    valid = {f: v for f, v in overrides.items() if hasattr(style, f)}
    return dataclasses.replace(style, **valid) if valid else style


def _reset_cache_for_tests() -> None:  # pragma: no cover - test helper
    global _PRESET_CACHE, _OVERRIDES_CACHE, _PALETTE_CACHE
    _PRESET_CACHE = None
    _OVERRIDES_CACHE = None
    _PALETTE_CACHE = None
