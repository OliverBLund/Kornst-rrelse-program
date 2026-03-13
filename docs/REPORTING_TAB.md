# Reporting Tab — Status & Roadmap

## Current State (March 2026)

### What works

| Feature | Notes |
|---|---|
| HTML preview | `QWebEngineView` with `QTextEdit` fallback if WebEngine not installed |
| A4 paper simulation | Gray surround, white paper sheet, drop shadow |
| Page break preview | Word-style gray bands injected at ~952px intervals (JS, screen-only) |
| Page numbers in PDF | `@page { @bottom-right { content: counter(page)... } }` via Chromium |
| Brand system | Org name, subtitle, logo (PNG/JPG/SVG), primary color — persisted via `QSettings` |
| Brand color injection | `--brand` CSS variable replaced at render time; `--brand-light` auto-computed |
| Cover page | Optional (checkbox); shows logo, org name, project metadata |
| Report types | Individual (Grain Size / K-Values / Combined), Comparison, Full Project |
| Template presets | Standard / Executive / Technical / Appendix — sets section checkboxes in one click |
| Section toggles | 11 checkboxes: Cover Page, Executive Summary, Methodology, Results, Plots, Interpretation, Percentile Table, Gradation Analysis, K-Value Statistics, Data Quality, Raw Data Tables |
| Report metadata | Project name, Location, Client, Analyst, Notes |
| **PDF export** | `page().printToPdf()` — async, A4 portrait, 15mm margins |
| **HTML export** | Saves clean report HTML (no preview CSS injected) |

---

## Export Formats

| Format | Status | Notes |
|---|---|---|
| HTML | ✅ Working | Clean self-contained file with embedded CSS and base64 charts |
| PDF | ✅ Working | Via Chromium print pipeline; requires `PyQt6-WebEngine` |
| Markdown | ❌ Not implemented | Shows "Coming Soon" dialog |
| Word (.docx) | ❌ Not implemented | Shows "Coming Soon" dialog; `python-docx` already in requirements |

---

## Roadmap

### Markdown export

The HTML report already has a clean, semantic structure making conversion straightforward.

**Approach**: Walk the HTML DOM (or generate in parallel from `ReportGenerator`) and emit:
- `#` / `##` / `###` for headings
- `|` pipe tables for percentile/K-value tables
- `>` blockquotes for info/warning/metadata boxes
- `![fig](data:...)` for embedded plots (or save as `.png` alongside the `.md`)
- YAML front matter for project metadata

**Suggested implementation**: Add a `generate_*_markdown()` method in `ReportGenerator` mirroring the HTML methods, or add a lightweight `html_to_md()` converter in a new `markdown_exporter.py`.

**Dependency**: No new packages needed — pure Python string output.

---

### Word (.docx) export

`python-docx` is already listed in `requirements.txt`.

**Approach**: Build the `.docx` document programmatically in `ReportGenerator`, mirroring the HTML structure:
- `doc.add_heading()` for h1/h2/h3
- `doc.add_paragraph()` for body text
- `doc.add_table()` for data tables — style with brand color header fill
- `doc.add_picture(BytesIO(base64_decoded_plot))` for charts
- Custom paragraph styles for metadata boxes, badges, stat cards
- Header/footer with page numbers via `python-docx` section properties

**Brand color**: Pass `brand.primary_color` to set table header fill and heading colors using `RGBColor`.

**Suggested implementation**: New method `generate_*_docx(dataset, ..., brand) -> bytes` returning the `.docx` as bytes, saved by `_on_export_docx()` via `QFileDialog`.

**Dependency**: `python-docx>=1.0.0` (already in requirements).

---

### Other potential future formats

| Format | Value | Difficulty |
|---|---|---|
| Excel (.xlsx) | High — easy for clients to edit/append data | Low — `openpyxl` already used in export tab |
| LaTeX | High for academic users | Medium — needs template |
| CSV data dump | Low — data already in export tab | Trivial |
| Print directly | Medium — avoids PDF detour | Low — `QPrintDialog` + `page().print()` |

---

## Known Limitations

- **Full Project** report type is currently identical to Comparison (all samples selected). There is no dedicated "full project overview" report format yet.
- **Plot styling** in `ReportGenerator` uses hardcoded matplotlib colors (`#6b8e23`, `#ff6b6b`, etc.) rather than the brand color. Charts don't visually match the brand color set by the user.
- **PDF margins**: The `@page` CSS `margin: 20mm 20mm 25mm 20mm` is used for page number positioning, but `printToPdf()` is called with `QMarginsF(15, 15, 15, 15)` (15mm). These are slightly inconsistent — the `@page` margin wins for CSS content, but the QPageLayout margin controls the physical page margin in Chromium's print pipeline. Should be unified.
- **No report config persistence**: Template choice, metadata fields, and section toggles reset on every app launch (brand settings do persist via QSettings).
- **MD/DOCX export buttons** are enabled/disabled together with HTML, but clicking them only shows a "Coming Soon" dialog. They should remain visually disabled (grayed out) to avoid confusion.

---

## Files

| File | Role |
|---|---|
| `Program/gui/reporting_tab.py` | Tab UI — left config panel, WebEngine preview, export bar |
| `Program/report_generator.py` | HTML report generation for all 4 report types |
| `Program/gui/report_brand.py` | `ReportBrand` dataclass — org identity, color, logo, QSettings persistence |
| `requirements.txt` | `PyQt6-WebEngine>=6.4.0`, `python-docx>=1.0.0` already listed |
