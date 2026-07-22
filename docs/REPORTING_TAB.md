# Reporting Tab — Current Behavior

## Current State (July 2026)

The Reports tab builds a formatted document from selected datasets. It uses the same calculated values, tables, visible plots, plot presets, palettes, and saved plot customizations as the application. The exporter does not create substitute or fallback charts.

## Workflow

1. Choose a report type.
2. Select the valid sample scope for that type.
3. Adjust sections, plots, appendices, project information, and branding.
4. Choose PDF, HTML, or Word (.docx).
5. Generate the report, inspect the preview, then save it.

Configuration is persisted through `QSettings`, including the report type, output format, section and plot choices, project information, branding, and report color.

## Current Features

| Feature | Behavior |
|---|---|
| HTML preview | `QWebEngineView` preview with paper boundaries and mixed page orientations |
| Report types | Individual Sample, Cross-Sample Comparison, Full Project Summary, and K-Value Focus |
| Sample scope | Enforces the sample-count rule associated with the selected report type |
| Section and plot selection | Report-type defaults remain editable before generation |
| Plot style | Uses the shared report/export preset, palette, and saved Customize overrides |
| Large-batch plots | Uses adaptive layouts and landscape plot sheets where required; small reports remain portrait |
| Tables | Uses actual report data and can move qualifying large tables to a companion Excel appendix |
| Project information | Project name, project number, date, location, client, analyst, and notes |
| Branding | Organization name, subtitle, optional PNG/JPG/SVG logo, and report accent color |
| Cover | Optional image-or-text cover with a dedicated first page |
| Background generation | Long report generation runs as a cancellable background task |

## Output Formats

| Format | Status | Notes |
|---|---|---|
| HTML | Working | Self-contained report with embedded CSS and images |
| PDF | Working | Printed from the loaded Chromium preview using A4 portrait and landscape pages as composed |
| Word (.docx) | Working | Editable headings, paragraphs, metadata, tables, captions, figures, page breaks, and section orientations |
| Companion Excel (.xlsx) | Optional | Stores qualifying large report tables when requested; the primary report contains appendix notices |

Word is the preferred output when the recipient needs to revise wording, reorder content, add commentary, or apply a client template. PDF is the fixed-layout delivery format.

## Cover and Branding Contract

- The cover remains balanced with or without an image.
- No logo means no fabricated placeholder or initials badge.
- The user can explicitly remove a saved logo and return to a text-only cover.
- Wide and tall logos are bounded by both width and height.
- Project number and the user-entered report date are shown when provided.
- The Word cover is editable content rather than a flattened screenshot.
- Word report content begins on a new page, and the first page omits report headers and footers.
- SVG stays embedded in HTML/PDF and is rasterized only when Word compatibility requires it.

## Report Fidelity Contract

Reports may include only:

- tables containing data produced by the program; and
- plots the user selects and can see in the application.

The exporter must not invent fallback plots, semantic substitutes, or decorative data visualizations. Composition changes such as page orientation, plot sizing, label wrapping, legend placement, and table externalization are allowed because they preserve the underlying report content.

## Known Constraints

- PDF export requires `PyQt6-WebEngine`.
- Word export requires `python-docx`.
- Very large editable Word documents remain subject to the recipient's installed fonts, printer settings, and Word version.
- Representative confidential client reports are not stored as fixtures when NDA restrictions prevent it; synthetic and non-confidential fixtures are used instead.
- Plot-style changes are applied the next time the user explicitly generates the report.

## Main Files

| File | Role |
|---|---|
| `Program/gui/reporting_tab.py` | Report configuration, preview, background generation, and save workflow |
| `Program/report_generator.py` | HTML report generation and editable DOCX rendering |
| `Program/gui/report_brand.py` | Persisted organization identity, accent color, and optional logo |
| `Program/help_content/reports_tab.html` | User-facing written guide |
| `docs/REPORTING_ROADMAP.md` | Longer-term reporting architecture and enhancement record |
