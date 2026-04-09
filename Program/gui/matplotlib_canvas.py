"""
Shared matplotlib Qt canvas helpers.

Keeps on-screen plots sharp on fractional Windows scaling by forcing the
QtAgg canvas to resync its device-pixel ratio once it is actually attached
to a shown window.
"""

from __future__ import annotations

import matplotlib

try:
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
except ImportError:
    matplotlib.use("Qt5Agg")
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as _FigureCanvas  # type: ignore
    from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar  # type: ignore

from PyQt6.QtCore import QEvent, QTimer


_RESYNC_EVENTS = {QEvent.Type.ParentWindowChange}
_dpr_change_event = getattr(QEvent.Type, "DevicePixelRatioChange", None)
if _dpr_change_event is not None:
    _RESYNC_EVENTS.add(_dpr_change_event)


class FigureCanvas(_FigureCanvas):
    """Qt canvas that eagerly syncs matplotlib to the active screen DPR."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._deferred_draw_pending = False

    def draw(self, *args, **kwargs) -> None:  # type: ignore[override]
        if not self.isVisible():
            self._deferred_draw_pending = True
            return
        self._deferred_draw_pending = False
        super().draw(*args, **kwargs)

    def _flush_deferred_draw(self) -> None:
        if self._deferred_draw_pending and self.isVisible():
            self._deferred_draw_pending = False
            super().draw()

    def _sync_device_pixel_ratio(self) -> None:
        update_pixel_ratio = getattr(self, "_update_pixel_ratio", None)
        if callable(update_pixel_ratio):
            update_pixel_ratio()
        self.draw_idle()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_device_pixel_ratio)
        QTimer.singleShot(0, self._flush_deferred_draw)

    def event(self, event):  # type: ignore[override]
        result = super().event(event)
        if event.type() in _RESYNC_EVENTS:
            QTimer.singleShot(0, self._sync_device_pixel_ratio)
        return result
