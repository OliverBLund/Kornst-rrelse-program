# ClassificationDialog Frameless Popup Debug Note

Last updated: 2026-03-26

## Symptom

On Windows, opening `ClassificationDialog` from the control panel shows a brief small transient popup before the real frameless dialog appears.

The original desktop/wallpaper flash was fixed earlier, but this smaller transient artifact still happens.

## Current Status

The issue is **not** the shared frameless base by itself.

Evidence:

- `Program/gui/classification_dialog.py` now uses `FramelessDialogBase`.
- `Program/gui/control_panel.py` -> `PorosityDialog` was also switched to `FramelessDialogBase`.
- `PorosityDialog` does **not** reproduce the popup.
- `ClassificationDialog` still does.

That means the remaining issue is specific to `ClassificationDialog`'s own widget tree, first-show layout work, or something the Windows compositor does in response to that dialog specifically.

## Important Files

- `Program/gui/classification_dialog.py`
- `Program/gui/control_panel.py`
- `Program/qt_chrome/frameless_dialog_base.py`
- `Program/qt_chrome/dialog_controller.py`
- `Program/qt_chrome/mode.py`
- `design_concepts/frameless_dialog_base.py`
- `design_concepts/qt_chrome/`

## Current Implementation State

### Classification dialog

`ClassificationDialog` currently:

- inherits `FramelessDialogBase`
- opens from `ControlPanel._open_classification_dialog()`
- uses `dlg.exec()`
- is parented to `self.window()`
- lazy-builds tabs 1-3 (`Boundaries`, `Custom`, `References`)
- builds only tab 0 (`Scheme`) during first show

Relevant code:

- `Program/gui/classification_dialog.py`
- `Program/gui/control_panel.py`

### Comparison dialog

`PorosityDialog` currently:

- also inherits `FramelessDialogBase`
- opens from the same general UI area
- does **not** show the transient popup

This is the strongest comparison point found so far.

## What Has Been Ruled Out

### 1. Generic frameless chrome bug

Not supported by current evidence, because `PorosityDialog` works with the same base.

### 2. A second real Qt top-level dialog/HWND

Instrumented runs did not show a second real dialog window.

Multiple probes were run against:

- isolated `ClassificationDialog`
- actual `MainWindow -> ControlPanel -> ClassificationDialog.exec()` path
- actual path with 2-3 datasets loaded

Observed result:

- only one `Classification System` HWND
- no second Qt dialog found
- no small second geometry matching the popup

### 3. Hidden tabs causing the first-show artifact

Tabs 1-3 were changed to lazy-build on first access.

Result:

- popup still happens

Conclusion:

- the trigger is likely in the initially visible page, the header/footer, or the tab widget itself
- not in the hidden `Boundaries`, `Custom`, or `References` content

## Investigations Already Tried

These were explored before narrowing the issue:

- moving frameless initialization earlier
- changing when rounded mask / Windows soft corners are applied
- avoiding forced `winId()` calls where possible
- deferring first-show chrome work
- switching from the original mixin approach to the working `FramelessDialogBase` pattern
- comparing against `design_concepts/frameless_dialog_base.py`
- converting `PorosityDialog` to the same base for comparison

The only consistently useful result was the comparison dialog test:

- same base + different dialog = no popup

## Most Likely Remaining Suspects

Because only `ClassificationDialog` reproduces:

1. The first visible `Scheme` tab content
2. The header widget
3. The footer widget
4. The `QTabWidget` / `QTabBar` first-show behavior in this specific dialog
5. A child widget that triggers a compositor-side animation or temporary native artifact without creating a second top-level window

## Recommended Next Steps

The next pass should avoid touching the frameless base again unless new evidence points there.

Highest-signal sequence:

1. Strip `ClassificationDialog` down by halves while keeping frameless behavior unchanged.
   Start with:
   - header only
   - header + empty body
   - header + plain placeholder instead of the full scheme tab
   - then reintroduce `_SchemeCard`
   - then the tab widget shell

2. Compare directly against `PorosityDialog` structure.
   The key question is:
   - what is present on first show in `ClassificationDialog` that is absent in `PorosityDialog`?

3. Test whether the popup still happens if tab 0 is replaced with a plain `QWidget` + simple `QLabel`.
   If that removes it, the culprit is inside the scheme page.

4. If the plain first tab still reproduces, temporarily bypass `QTabWidget` entirely and use a simple placeholder body.
   That would isolate whether the tab control itself is involved.

5. If needed, add targeted logging only inside `ClassificationDialog` for:
   - first `showEvent`
   - first `resizeEvent`
   - child widget `showEvent`
   - geometry changes on `_tabs`, `_header_widget`, and first-page content

## Good Repro Setup

Use the real app path, not an isolated dialog test.

Recommended repro:

- launch the main program normally
- load 2-3 datasets
- open `ClassificationDialog` from the control panel
- compare with `Manage Dataset Porosity...`

This matters because isolated tests did not reproduce the visual artifact reliably.

## Short Conclusion

At this point the problem should be treated as:

`ClassificationDialog`-specific first-show behavior, not a general frameless dialog infrastructure bug.
