"""Reusable frameless dialog base with controller-based chrome behavior."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QDialog, QWidget

from .dialog_controller import FramelessDialogChromeController
from .mask import apply_frameless_round_mask
from .mode import resolve_dialog_chrome_mode
from .platform import enable_windows_soft_corners


class FramelessDialogBase(QDialog):
    """Base dialog that can run in native or frameless mode with shared chrome behavior."""

    def __init__(
        self,
        parent=None,
        chrome_env_key: Optional[str] = None,
        default_mode: str = "auto",
    ):
        super().__init__(parent)
        self._dialog_chrome_env_key = chrome_env_key
        self._dialog_default_mode = default_mode
        self._dialog_chrome_mode = "native"
        self._frameless_enabled = False

        self._frameless_corner_radius_px = 10
        self._resize_margin = 6

        self._chrome_controller = FramelessDialogChromeController(
            self,
            resize_margin=self._resize_margin,
        )
        self._soft_corners_pending = False

        self._configure_window_chrome()
        self.destroyed.connect(self._cleanup_global_event_filter)

    def _resolve_dialog_chrome_mode(self) -> str:
        """Resolve dialog chrome mode from parent/default fallback."""
        parent_mode = str(getattr(self.parent(), "_window_chrome_mode", "")).strip().lower()
        return resolve_dialog_chrome_mode(
            parent_mode=parent_mode,
            default_mode=self._dialog_default_mode,
            default_windows="frameless",
            default_other="native",
        )

    def _configure_window_chrome(self):
        """Apply native or frameless window flags with safe fallback."""
        chrome_mode = self._resolve_dialog_chrome_mode()
        self._dialog_chrome_mode = chrome_mode

        flags = Qt.WindowType(self.windowFlags())
        if chrome_mode == "frameless":
            try:
                self.setWindowFlags(flags | Qt.WindowType.FramelessWindowHint)
                self._frameless_enabled = True
                self._soft_corners_pending = True
                return
            except Exception:
                self._frameless_enabled = False
                self._dialog_chrome_mode = "native"
                self._soft_corners_pending = False

        self.setWindowFlags(flags & ~Qt.WindowType.FramelessWindowHint)
        self._frameless_enabled = False
        self._soft_corners_pending = False

    def _enable_windows_soft_corners(self):
        """Best-effort rounded corners on Windows 11."""
        enable_windows_soft_corners(self)

    def _is_frameless_active(self) -> bool:
        return bool(self._frameless_enabled)

    def install_chrome_behavior(
        self,
        header_widget: Optional[QWidget],
        resize_widgets: Optional[list[QWidget]] = None,
        drag_widgets: Optional[list[QWidget]] = None,
        corner_radius: int = 10,
        resize_margin: int = 6,
    ):
        """Install frameless drag/resize behavior after UI widgets are created."""
        self._frameless_corner_radius_px = max(2, int(corner_radius))
        self._resize_margin = max(2, int(resize_margin))

        if not self._is_frameless_active():
            self._chrome_controller.set_enabled(False)
            self._cleanup_global_event_filter()
            self.clearMask()
            return

        self._chrome_controller.set_enabled(True)
        self._chrome_controller.configure(
            header_widget=header_widget,
            resize_widgets=resize_widgets,
            drag_widgets=drag_widgets,
            resize_margin=self._resize_margin,
        )

        self._apply_frameless_round_mask()

    def _cleanup_global_event_filter(self):
        self._chrome_controller.cleanup()

    def _apply_frameless_round_mask(self):
        apply_frameless_round_mask(
            self,
            enabled=self._is_frameless_active(),
            is_effectively_maximized=bool(self.isMaximized()),
            corner_radius_px=max(2, int(self._frameless_corner_radius_px)),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_frameless_round_mask()

    def showEvent(self, event):
        if self._is_frameless_active():
            self._chrome_controller.on_show()

        if self._soft_corners_pending and self._is_frameless_active():
            self._enable_windows_soft_corners()
            self._soft_corners_pending = False

        super().showEvent(event)
        self._apply_frameless_round_mask()

    def hideEvent(self, event):
        self._cleanup_global_event_filter()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._cleanup_global_event_filter()
        super().closeEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._apply_frameless_round_mask()
