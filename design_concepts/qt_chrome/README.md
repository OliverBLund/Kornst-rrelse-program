# qt_chrome (Portable PyQt6 Frameless Helpers)

This folder contains reusable frameless-window/dialog helpers extracted from DataMerger.

## Included pieces
- `mode.py`
  - `resolve_window_chrome_mode(...)`
  - `resolve_dialog_chrome_mode(...)`
- `window_helper.py`
  - `FramelessWindowChromeHelper` (edge resize + cursor handling with native system resize fallback)
- `dialog_controller.py`
  - `FramelessDialogChromeController` (frameless dialog drag + resize event-filter controller)
- `mask.py`
  - `apply_frameless_round_mask(...)`
- `platform.py`
  - `enable_windows_soft_corners(...)` (best-effort Windows 11 DWM rounded corners)

## Quick usage (main window)
```python
from shared.qt_chrome import (
    FramelessWindowChromeHelper,
    apply_frameless_round_mask,
    enable_windows_soft_corners,
    resolve_window_chrome_mode,
)

mode = resolve_window_chrome_mode()
if mode == "frameless":
    self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    self.window_chrome = FramelessWindowChromeHelper(
        self,
        margin=8,
        top_margin=6,
        is_effectively_maximized=self.is_window_effectively_maximized,
    )
    enable_windows_soft_corners(self)
```

## Quick usage (dialog)
```python
from shared.qt_chrome import resolve_dialog_chrome_mode

dialog_mode = resolve_dialog_chrome_mode(
    parent_mode=getattr(parent, "_window_chrome_mode", ""),
    default_mode="auto",
)
```

## Copy to another project
1. Copy `shared/qt_chrome/` (and optionally `shared/__init__.py`) into your project source root.
2. Wire your main window and base dialog to these helpers.
3. Keep your own title-bar widget implementation separate from these low-level chrome helpers.
