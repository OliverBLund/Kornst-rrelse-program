# Codebase Cleanup Audit

Date: 2026-07-03

This note records the first-pass cleanup findings for GrainSizeAnalysis. It is intentionally conservative: no file should be deleted only because it appears in this list.

## Current Shape

- Runtime code lives mostly in `Program/`.
- GUI code is the dominant Module group: 53 Python files in `Program/gui`.
- Tests live in `Program/tests`, but a few test or prototype files also appear outside that folder.
- Documentation, prototypes, generated exports, release outputs, and build tooling are mixed at the repository root.

## Large Modules

These are not dead files, but they are the main long-term maintainability pressure points:

- `Program/gui/comparison_tab.py` - 226 KB
- `Program/gui/control_panel.py` - 188 KB
- `Program/gui/main_window.py` - 181 KB
- `Program/gui/export_tab.py` - 164 KB
- `Program/report_generator.py` - 152 KB
- `Program/gui/reporting_tab.py` - 130 KB
- `Program/gui/column_mapper.py` - 129 KB
- `Program/gui/export_manager.py` - 116 KB
- `Program/gui/welcome_widget.py` - 104 KB
- `Program/gui/comparison_plot_widget.py` - 100 KB

## Likely Dead Or Prototype Files

These files had no active references from the app or tests during the first-pass scan:

- `Program/gui/test_export_debug.py`
  - Strongest deletion candidate.
  - It is a debug/prototype script inside the production GUI folder.
  - It currently contains a syntax error, so it should not stay in runtime source.

- `Program/gui/comparison_tab_enhanced.py`
  - Likely an old comparison-tab prototype.
  - Current app uses `Program/gui/comparison_tab.py`.

- `Program/gui/data_inspector_dialog.py`
  - Likely an older duplicate of `Program/gui/dataset_inspector_dialog.py`.
  - Current app and tests import `gui.dataset_inspector_dialog.DataInspectorDialog`.

- `Program/Splash/welcome_screen_v2.py`
  - Likely an old splash/welcome prototype.
  - Current app uses `Splash.simple_splash.SimpleSplash` and `gui.welcome_widget.WelcomeWidget`.

## Generated Or Non-Runtime Candidates

These should be cleaned or moved only after confirming they are not intentionally kept as release evidence:

- `.codex_pycache/`
- `.codex_pycache_check/`
- `.pytest_cache/`
- `Program/__pycache__/`
- `export_tests/`
- `build_system/venv/`
- `design_concepts/`

## False Positives

These looked unused in a simple graph but are active and should not be removed:

- `Program/qt_chrome/*`
  - Used through package exports such as `from qt_chrome import FramelessMainWindowMixin`.

- `Program/k_calculations.py`
  - Compatibility wrapper used by the app and tests.
  - The real implementation is `Program/k_calculations_v2.py`.

## Recommended Cleanup Order

1. Remove or quarantine generated folders and debug outputs.
2. Delete or archive the strongest dead-file candidates after one full test run.
3. Add a small `CONTEXT.md` that names the main Modules and their intended Interfaces.
4. Split large Modules only along real domain boundaries, not by arbitrary line count.
5. Start with low-risk deepening seams:
   - single release/version metadata source;
   - shared responsive toolbar implementation;
   - report generation Interface separate from report UI;
   - import/loading Interface separate from UI progress handling.

