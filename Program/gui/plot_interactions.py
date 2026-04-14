"""
Shared matplotlib subplot interaction controller.
"""

from __future__ import annotations

import math
from typing import Callable

from PyQt6.QtCore import Qt

from .theme import C


class AxesInteractionController:
    """Shared zoom/pan/active-axes behavior for embedded matplotlib plots."""

    def __init__(
        self,
        *,
        figure,
        canvas,
        get_current_ax: Callable[[], object],
        set_current_ax: Callable[[object | None], None],
        get_active_axes: Callable[[], list],
        on_view_changed: Callable[[object | None], None] | None = None,
    ) -> None:
        self.figure = figure
        self.canvas = canvas
        self._get_current_ax = get_current_ax
        self._set_current_ax_cb = set_current_ax
        self._get_active_axes = get_active_axes
        self._on_view_changed = on_view_changed
        self._default_limits: dict[object, dict[str, tuple[float, float]]] = {}
        self._pan_state = None

    @staticmethod
    def zoom_axis_limits(limits, scale: str, factor: float) -> tuple[float, float]:
        """Zoom a linear or log axis around its center by the given factor."""
        lo, hi = limits
        reversed_axis = hi < lo
        if reversed_axis:
            lo, hi = hi, lo

        if scale == 'log' and lo > 0 and hi > 0:
            lo_log = math.log10(lo)
            hi_log = math.log10(hi)
            center_log = (lo_log + hi_log) / 2
            half_span = (hi_log - lo_log) * factor / 2
            new_lo = 10 ** (center_log - half_span)
            new_hi = 10 ** (center_log + half_span)
        else:
            center = (lo + hi) / 2
            half_range = (hi - lo) * factor / 2
            new_lo = center - half_range
            new_hi = center + half_range
            if lo >= 0 and new_lo < 0:
                new_lo = 0

        return (new_hi, new_lo) if reversed_axis else (new_lo, new_hi)

    @staticmethod
    def pan_axis_limits(limits, scale: str, start_data: float, current_data: float) -> tuple[float, float]:
        """Pan a linear or log axis based on pointer movement."""
        lo, hi = limits
        reversed_axis = hi < lo
        if reversed_axis:
            lo, hi = hi, lo

        if scale == 'log' and lo > 0 and hi > 0 and start_data and current_data and start_data > 0 and current_data > 0:
            factor = start_data / current_data
            new_lo = lo * factor
            new_hi = hi * factor
        else:
            delta = start_data - current_data
            new_lo = lo + delta
            new_hi = hi + delta
            if lo >= 0 and new_lo < 0:
                shift = -new_lo
                new_lo += shift
                new_hi += shift

        return (new_hi, new_lo) if reversed_axis else (new_lo, new_hi)

    def _axes_pool(self) -> list:
        axes = list(self._get_active_axes() or [])
        return axes if axes else list(self.figure.axes)

    def _notify_view_changed(self) -> None:
        if self._on_view_changed:
            self._on_view_changed(self._get_current_ax())

    def _draw_idle(self) -> None:
        draw_idle = getattr(self.canvas, "draw_idle", None)
        if callable(draw_idle):
            draw_idle()
        else:
            self.canvas.draw()

    @staticmethod
    def _event_has_shift(event) -> bool:
        key = getattr(event, "key", None)
        if isinstance(key, str) and "shift" in key.lower().split("+"):
            return True
        gui_event = getattr(event, "guiEvent", None)
        modifiers = getattr(gui_event, "modifiers", None)
        if callable(modifiers):
            return bool(modifiers() & Qt.KeyboardModifier.ShiftModifier)
        return False

    @staticmethod
    def _is_primary_button(event) -> bool:
        button = getattr(event, "button", None)
        if button in (1, "up", "down"):
            return button == 1
        name = getattr(button, "name", "")
        if isinstance(name, str) and name.upper() == "LEFT":
            return True
        value = getattr(button, "value", None)
        return value == 1

    def set_current_ax(self, ax, *, draw: bool = True) -> None:
        new_ax = ax if ax in self._axes_pool() else None
        if new_ax is self._get_current_ax():
            return
        self._set_current_ax_cb(new_ax)
        self.apply_active_axes_styling()
        self._notify_view_changed()
        if draw:
            self._draw_idle()

    def prime_current_ax(self) -> None:
        axes = self._axes_pool()
        if self._get_current_ax() not in axes:
            self._set_current_ax_cb(axes[0] if axes else None)

    def capture_default_limits(self) -> None:
        self._default_limits = {
            ax: {"xlim": ax.get_xlim(), "ylim": ax.get_ylim()}
            for ax in self._axes_pool()
        }

    def apply_active_axes_styling(self) -> None:
        current_ax = self._get_current_ax()
        for ax in self._axes_pool():
            is_active = ax is current_ax
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.6 if is_active else 0.8)
                spine.set_edgecolor(C.OLIVE if is_active else "#cfc5b4")
            ax.title.set_color(C.TEXT if is_active else C.TEXT_MID)

    def reset_axes_view(self, ax) -> None:
        defaults = self._default_limits.get(ax)
        if not defaults:
            return
        ax.set_xlim(*defaults["xlim"])
        ax.set_ylim(*defaults["ylim"])
        self.set_current_ax(ax, draw=False)
        self._notify_view_changed()

    def zoom_target_axes(self) -> list:
        current_ax = self._get_current_ax()
        if current_ax in self._axes_pool():
            return [current_ax]
        axes = self._axes_pool()
        if axes:
            self.set_current_ax(axes[0], draw=False)
            return [self._get_current_ax()]
        return []

    def zoom_current(self, factor: float) -> None:
        targets = self.zoom_target_axes()
        if not targets:
            return
        for ax in targets:
            ax.set_xlim(*self.zoom_axis_limits(ax.get_xlim(), ax.get_xscale(), factor))
            ax.set_ylim(*self.zoom_axis_limits(ax.get_ylim(), ax.get_yscale(), factor))
        self._notify_view_changed()
        self.canvas.draw()

    def reset_current_axes(self) -> bool:
        targets = self.zoom_target_axes()
        if not targets:
            return False
        for ax in targets:
            self.reset_axes_view(ax)
        self.canvas.draw()
        return True

    def on_click(self, event) -> None:
        ax = getattr(event, "inaxes", None)
        self.set_current_ax(ax)
        if ax is None:
            return
        if getattr(event, "dblclick", False):
            self.reset_axes_view(ax)
            self.canvas.draw()
            return
        if self._event_has_shift(event) and self._is_primary_button(event):
            if event.xdata is None or event.ydata is None:
                return
            self._pan_state = {
                "ax": ax,
                "xdata": event.xdata,
                "ydata": event.ydata,
                "xlim": ax.get_xlim(),
                "ylim": ax.get_ylim(),
            }

    def on_scroll(self, event) -> None:
        ax = getattr(event, "inaxes", None)
        if ax not in self._axes_pool():
            return
        self.set_current_ax(ax, draw=False)
        step = getattr(event, "step", 0)
        if not step:
            step = 1 if getattr(event, "button", "") == "up" else -1
        factor = 0.88 if step > 0 else 1.14
        ax.set_xlim(*self.zoom_axis_limits(ax.get_xlim(), ax.get_xscale(), factor))
        ax.set_ylim(*self.zoom_axis_limits(ax.get_ylim(), ax.get_yscale(), factor))
        self._notify_view_changed()
        self.canvas.draw()

    def on_motion(self, event) -> None:
        if not self._pan_state or event.xdata is None or event.ydata is None:
            return
        ax = self._pan_state["ax"]
        if ax not in self._axes_pool():
            self._pan_state = None
            return
        ax.set_xlim(*self.pan_axis_limits(self._pan_state["xlim"], ax.get_xscale(), self._pan_state["xdata"], event.xdata))
        ax.set_ylim(*self.pan_axis_limits(self._pan_state["ylim"], ax.get_yscale(), self._pan_state["ydata"], event.ydata))
        self._notify_view_changed()
        self._draw_idle()

    def on_release(self, _event) -> None:
        self._pan_state = None
