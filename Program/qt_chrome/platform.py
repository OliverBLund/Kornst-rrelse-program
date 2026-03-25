"""Platform-specific window chrome helpers."""

from __future__ import annotations

import os


def _window_hwnd(window) -> int:
    if os.name != "nt" or window is None:
        return 0
    handle = window.windowHandle()
    if handle is None:
        return 0
    try:
        return int(handle.winId())
    except Exception:
        return 0


def enable_windows_soft_corners(window) -> None:
    """Best-effort rounded window corners on Windows 11."""
    try:
        import ctypes

        hwnd = _window_hwnd(window)
        if not hwnd:
            return

        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        preference = ctypes.c_int(DWMWCP_ROUND)

        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd),
            ctypes.c_uint(DWMWA_WINDOW_CORNER_PREFERENCE),
            ctypes.byref(preference),
            ctypes.sizeof(preference),
        )
    except Exception:
        pass


def disable_windows_window_transitions(window) -> None:
    """Best-effort disable DWM show/hide transitions for a window."""
    try:
        import ctypes

        hwnd = _window_hwnd(window)
        if not hwnd:
            return

        DWMWA_TRANSITIONS_FORCEDISABLED = 3
        disable = ctypes.c_int(1)

        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd),
            ctypes.c_uint(DWMWA_TRANSITIONS_FORCEDISABLED),
            ctypes.byref(disable),
            ctypes.sizeof(disable),
        )
    except Exception:
        pass

