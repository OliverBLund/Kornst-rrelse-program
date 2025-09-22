# Repository Guidelines

## Project Structure & Module Organization
The grain-size analysis application resides in `Program/`. `main.py` bootstraps the PyQt6 interface; `data_loader.py` parses CSV inputs and performs validation; `k_calculations.py` implements hydraulic conductivity equations; and `report_generator.py` together with `unit_conversions.py` covers exports plus shared conversions. GUI widgets and tabs live in `Program/gui/` (for example `main_window.py`, `control_panel.py`, `comparison_tab.py`). Example CSV fixtures are located in `test_data/`, while reference material and larger datasets belong in `Data/` and `Litterature/`. Document planned features or architectural decisions in `Program/development_roadmap.md` so the research context stays discoverable.

## Build, Test, and Development Commands
- `python -m venv .venv` create a dedicated virtual environment.
- `. .venv/Scripts/Activate.ps1` activate it from PowerShell prior to installing dependencies.
- `pip install pyqt6 matplotlib numpy pandas scipy` install the UI and numeric stack.
- `python Program/main.py` run the desktop application during development; `run_app.bat` offers a shortcut for Windows users.
- `python -m pytest` execute the future automated suite once tests land under `Program/tests/`.

## Coding Style & Naming Conventions
Adhere to PEP 8 with four-space indentation, snake_case for functions and module level variables, and CapWords for classes (see `Program/gui/main_window.py`). Prefer type hints, `dataclass`, and `Enum` to keep validation contracts explicit. Route operational diagnostics through the shared `logging` instance instead of direct prints, and collect user-facing strings within GUI modules to simplify localization.

## Testing Guidelines
Target `pytest` with files named `test_<module>.py` under `Program/tests/`. Leverage fixtures built from `test_data/test_comma.csv` and `test_data/test_error_handling.csv` to assert the validation paths, warning states, and K-value calculations. Until automated coverage matures, perform manual smoke tests by launching the app, loading those CSVs, and cross-checking the comparison plots and generated CSV reports.

## Commit & Pull Request Guidelines
Write imperative, topic-scoped commit messages such as `fix: handle non monotonic grain sizes` or `feat: add sauerbrei method configuration`. Reference issue IDs where available and keep refactors separate from feature changes. Pull requests should outline motivation, enumerate primary modules touched, summarize validation evidence (datasets or screenshots), and call out follow-on tasks so roadmap tracking stays accurate.

## Data Handling Tips
Store anonymized sample CSVs within `test_data/` and exclude large raw exports from version control. When adding new empirical formulas or heuristics, capture assumptions in `Program/development_roadmap.md` and deposit supporting papers in `Litterature/`. Update `report_generator.py` alongside any schema changes to keep downstream exports stable.
