"""Platform-specific chrome helpers."""

from __future__ import annotations

import os


def enable_windows_soft_corners(window) -> None:
    """Best-effort rounded window corners on Windows 11."""
    if os.name != "nt" or window is None:
        return
    try:
        import ctypes

        hwnd = int(window.winId())
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

