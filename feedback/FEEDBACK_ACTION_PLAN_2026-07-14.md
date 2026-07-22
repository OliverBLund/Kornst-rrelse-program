# Feedback Synthesis and Action Plan

Date: 2026-07-14

## Purpose

This document consolidates feedback from Gro and Eskild into an agreed work plan for the Grain Size Analysis application.

It is a planning document only. No implementation should begin until the priorities, product decisions, and required test files in this document have been reviewed.

Feedback sources:

- `Gro_Grain Size Analysis_test-observationer_GRLI-20260714.docx`
- `Eskild_wsp_14072026.docx`
- `Eskild_generated_reports/FullRapEks_kampagne1.pdf`
- `Eskild_generated_reports/K_RapEks_kampagne1.pdf`

## Executive Summary

The feedback clusters around three user journeys:

1. First-run orientation and navigation.
2. Importing real laboratory files, especially irregular and multi-sample workbooks.
3. Producing readable reports for large batches.

The most serious issue is import correctness. Gro was able to create an inverted curve by treating percent-retained values as percent-passing values. The result looked plausible enough to continue into the analysis. Preventing this type of silent data interpretation error has higher priority than general visual polish.

The column mapper also needs a substantial workflow redesign. It exposes too many concepts and actions at once, mixes automatic detection with manual mapping and batch pattern tools, and makes the irregular-sheet workflow difficult to understand. Simplifying the mapper means reducing the number of decisions presented to the user, not merely shortening labels or moving the same controls.

There is no evidence from this feedback that the hydraulic-conductivity formulas should be changed. Installation, CSV loading, duplicate batch handling, and broad agreement with previous interpretations were positive findings.

## Priority Overview

| Priority | Workstream | Size | Status |
|---|---|---:|---|
| P0 | Prevent passing/retained interpretation errors | Medium | Interim guard implemented; broader format support deferred |
| P0 | Reproduce and fix the Excel mapper freeze | Unknown | Deferred: NDA-protected source artifact unavailable |
| P0 | Fix ErrorTab preview integration failure | Small, with architectural follow-up | Implemented; regression covered |
| P1 | Redesign and simplify the column mapper | Large | Implemented; awaiting user verification |
| P1 | Preserve mappings when the header row changes | Small | Implemented; awaiting user verification |
| P1 | Support delimited TXT consistently | Small to medium | Implemented with synthetic delimiter coverage |
| P1 | Make large-batch report plots adaptive | Large | In progress; landscape composition user verified |
| P1 | Import multiple samples from one worksheet | Large | Experimental next-release candidate; synthetic validation and documentation pending |
| P1 | Prevent the Plot visibility scrollbar from covering row controls | Small to medium | Implemented; user verified |
| P1 | Add clear batch selection and removal actions to the Samples sidebar | Medium | Implemented; user verified |
| P1 | Make K-value x-axis ticks honor Tick size | Small | Implemented; user verified |
| P2 | Unify Guides, Tutorials, and welcome-screen entry points | Medium | Implemented; user verified |
| P2 | Put prominent CSV and Excel examples in Data Format & Files | Small to medium | Agreed documentation gap |
| P2 | Audit all Guides for structure, examples, terminology, and readability | Medium | Agreed broader documentation task |
| P2 | Add a non-destructive Home tab | Medium | Implemented; user verified |
| P2 | Review Export presets and Export Tutorial clarity | Small to medium | Implemented; user verification pending |
| P2 | Add range selection to Scope & Groups | Medium | Implemented; user verified |
| P2 | Add controllable, wrapping legend layouts | Medium | Implemented; user verified |
| P2 | Expand shared plot Customize controls | Medium | Implemented; user verified |
| P2 | Simplify the Samples header and plot-type controls | Small to medium | Samples header implemented; plot selector deferred |
| P2 | Standardize K-value unit presentation | Small to medium | Implemented; user verified |
| P2 | Verify native multi-file selection | Small | Native Shift/Ctrl selection user verified |
| P2 | Report final batch-import outcomes | Small to medium | Proposed; value under review |
| P3 | Audit typography roles | Small | Polish, not a functional defect |
| P3 | Sync the bottom status bar to the active dataset | Small | Noted for later |
| Deferred | Generic PDF import | Large and format-specific | Representative files required |

## Workstream 1: Import Correctness and Data Safety

### Problem

The mapper allows a user to assign percent-retained data to the percent-passing role. Gro did this and obtained a reversed grain-size curve. The application may emit a warning, but the workflow does not stop the user from accepting a scientifically incorrect interpretation.

### Required outcome

- Define processed input explicitly as `Cumulative percent passing (0-100)`.
- Validate the declared input contract without guessing the scientific meaning of arbitrary numeric columns.
- Reject explicit retained-only headers in processed files and do not transform retained values automatically.
- Block strongly reversed curves while allowing small local irregularities to remain informational or warnings.
- Explain that cumulative retained can be converted in the source with `passing = 100 - retained`, while per-sieve retained requires accumulation and cannot use that direct conversion.
- Keep original sieve-weight imports supported through the separate `Raw Sieve Weighings` path, which derives cumulative passing from the measured masses.

### Acceptance criteria

- Mapping retained data as passing cannot silently produce an inverted curve.
- Explicit retained headers are not automatically mapped or converted as passing.
- A predominantly reversed declared-passing curve is blocked with a clear cumulative-passing contract message.
- A small local irregularity does not cause a false blocking error.
- Existing valid sample datasets continue to load without error.
- Automated tests cover correct passing data, explicit retained data, reversed direction, minor irregularities, Excel detection, and restored legacy retained mappings.

### Deferred product decision

The interim implementation prevents retained-only or strongly reversed processed data from silently entering analysis. It does not define the final retained-data workflow.

NDA-protected laboratory exports are unavailable for this cycle. Broader retained-data support therefore remains deferred. Any future expansion must start from a non-confidential or deliberately sanitized fixture that clearly identifies which of these forms it represents:

- cumulative percent retained, which can be converted with `passing = 100 - retained`;
- individual percent retained per sieve, which must be accumulated before conversion;
- raw sieve weights, which the existing Raw Sieve Weighings workflow already supports;
- other instrument- or laboratory-specific grain-size result formats.

Only then decide how much interpretation and transformation belongs inside the program, how users explicitly declare the source meaning, and what provenance must be stored. Also revisit whether retained-only files should display `Needs review`, `Source conversion required`, or an actionable in-program conversion workflow. Do not infer support from synthetic fixtures alone or finalize that UI until the supported formats are agreed.

## Workstream 2: Column Mapper Redesign

### Current problems

The current mapper combines too many responsibilities in one dialog:

- processed-curve data versus raw sieve weighings;
- automatic detection versus manual mapping;
- clean-column mapping versus irregular cell ranges;
- sheet selection and batch pattern reuse;
- sample name, temperature, and porosity;
- range detection, range assignment, clearing, and pattern learning;
- validation, preview, and import.

This overload is especially visible in `Cell Ranges - irregular sheet`. The user is presented with four competing actions:

- `Use Selection as Size`
- `Use Selection as % Passing`
- `Clear / reset selection`
- `Detect Area from selection`

The user must understand the application's internal selection state before completing a basic import. The controls also clear the table selection after assigning a role, which makes the workflow harder to follow visually.

Other confirmed mapper issues include:

- Changing the header row re-runs detection and loses existing column choices.
- Duplicate headings are visually indistinguishable even though they refer to different columns.
- The user can select the wrong percentage semantics and still continue.
- One worksheet produces only one dataset, even when the sheet contains several samples.
- Error recovery and first-time import do not consistently use the same preview behavior.
- A blank or unresponsive mapper window was observed when opening an Excel workbook.

### Design principles

1. **Automatic first**: show the best detected interpretation before asking the user to configure it.
2. **Progressive disclosure**: show advanced controls only when automatic detection is wrong or insufficient.
3. **One decision at a time**: do not ask for data type, mapping method, ranges, metadata, and batch behavior simultaneously.
4. **Preview the result**: the user confirms an interpreted dataset, not only columns or cells.
5. **Use domain language**: ask about sieve size, passing, retained, and sample identity rather than internal mapping modes.
6. **Keep recovery consistent**: opening the mapper from an error tab must use the same workflow and state model as a normal import.

### Recommended top-level workflow

#### Step 1: Detect

- Read the file and show detected sheets and candidate datasets.
- If detection is confident, preselect the candidate and proceed directly to confirmation.
- If detection is ambiguous, explain the specific ambiguity in plain language.
- Keep `Processed curve` and `Raw sieve weighings` as meaningful domain choices, but do not force the user to choose when detection is confident.

#### Step 2: Confirm data source

For a clean table:

- Select the header row first.
- Select the particle-size column.
- Select the percentage column.
- Select whether the values are passing or retained.
- Identify duplicate columns by position, for example `F: Kornstorrelse` and `G: Kornstorrelse`.

Changing the header row must preserve the selected column positions when those columns still exist. Automatic detection should fill empty choices, not overwrite deliberate user choices.

#### Step 3: Confirm result

- Show the extracted row count.
- Show warnings and skipped rows inline.
- Show the interpreted grain-size curve.
- Show the sample name and source sheet/block.
- Use one primary command: `Import sample` or `Import N samples`.

Temperature, porosity, batch pattern reuse, and similar settings should be placed in a collapsed `Advanced` section unless they are required to complete the import.

### Simplified irregular-sheet workflow

The irregular-sheet path should be a guided sequence instead of four independent selection tools:

1. The mapper displays: `Select the particle-size values`.
2. The user drags across a contiguous range or selects a column segment.
3. The mapper records and labels the range, for example `B12:B30`.
4. The mapper displays: `Now select the passing or retained values`.
5. The user selects the matching range.
6. The mapper asks whether the values are passing or retained.
7. The mapper pairs the ranges, validates equal lengths, and shows the resulting curve.

There should be one unobtrusive `Start over` action. Automatic area detection can be offered as a suggestion, but it should not be a persistent toggle competing with the required steps.

The table should keep assigned ranges visibly highlighted with a stable legend. The user should not need to remember which cells were assigned after the active selection disappears.

### Multi-sample worksheets

Status: Experimental next-release candidate. Implemented on 2026-07-16 and
validated/documented with maintained synthetic fixtures on 2026-07-17. Because
representative laboratory workbooks are unavailable under NDA, the feature
remains explicitly experimental.

This must not be presented as universal support for arbitrary multi-sample
worksheets. Laboratory exports vary in headers, merged cells, units, table
orientation, percentage semantics, and placement of metadata. The normal
single-sample and manual-mapping pathways remain the supported fallback whenever
candidate detection is incomplete or ambiguous.

The feature is explicit opt-in. Normal `Processed Sieve Data` and `Raw Sieve
Weighings` imports do not run multi-sample detection. Users must deliberately
choose `Multiple Samples in One File (Experimental)` from the Add or File menu;
this prevents valid single-sample laboratory files such as the NBAL series from
being reclassified by an experimental heuristic.

The redesigned mapper must be capable of representing more than one candidate dataset per sheet. At minimum, it should support:

- one shared particle-size column with several percentage columns;
- repeated particle-size and percentage column pairs;
- sample names stored in one or more header rows;
- duplicate header text in different Excel columns.

The confirmation view should list detected samples with checkboxes and allow previewing each curve before importing them as separate datasets. Once imported as datasets, the existing comparison workflow can be reused.

Implemented behavior:

- Conservatively detects shared-size/multiple-passing-column layouts, repeated
  size/passing pairs, and long tables with an explicit sample-ID column.
- Requires an explicit cumulative passing/finer role. Incremental `% Volume In`,
  retained values, and generic percentage columns are not silently reinterpreted.
- Uses sample labels above a column group or the sample prefix in combined
  headers such as `BH-01 Percent Passing (%)`; Excel column coordinates remain
  visible as provenance and disambiguate duplicate headings.
- Presents all candidates as a short checked list. Selecting a candidate
  highlights its source cells and previews its interpreted curve; the user can
  exclude candidates before choosing `Import N samples`.
- Runs candidate detection only from the explicit `Multiple Samples in One File
  (Experimental)` command. Candidate confirmation is not presented as a load
  failure or as ordinary manual column mapping.
- Imports each confirmed candidate as a separate dataset, tab, sidebar card,
  scope identity, and saved-session source while retaining the original physical
  file path for remapping and reload.
- Removing one imported sample does not remove sibling samples from the same
  workbook. Remapping the physical source still replaces its complete set.
- Regression coverage includes all three layouts, single-curve fallback,
  incremental-percentage rejection, CSV review routing, mapper confirmation,
  independent removal, and session restoration.
- Verification fixture: `test_data/multi_sample_shared_size.xlsx`.

When a user completes a manual cell-range mapping, the mapper should treat the
relative range arrangement as a candidate pattern and test it against the
remaining unmapped candidates in the current import queue. This applies to both
processed curves and raw sieve weighings. Each proposed match must still be
parsed and scientifically validated as its own dataset; a structural match must
not be accepted solely because the cell offsets are similar. Successful matches
can become ready together, while failed or ambiguous matches remain visible as
`Needs review`. The final confirmation must list all proposed datasets and use
`Import N samples` rather than silently importing the batch.

### Mapper acceptance criteria

- A first-time user can import a clean two-column file without opening advanced controls.
- A first-time user can complete irregular range mapping by following visible sequential instructions.
- The mapper never presents four equally weighted range-selection commands at once.
- Header-row changes do not erase deliberate mappings when column positions remain valid.
- Duplicate headings are distinguishable by column letter or index.
- Passing versus retained meaning is explicit and validated.
- The mapper shows the resulting curve before import.
- Error-tab recovery and normal import share the same preview and mapping services.
- Mapper state survives correction attempts without stale or contradictory selections.
- Tests cover clean columns, irregular ranges, raw sieve data, multi-sheet files, multiple samples per sheet, duplicate headers, error recovery, and cancellation.

### Header-row mapping preservation

Status: Implemented on 2026-07-16 and awaiting user verification.

- Changing the Header Row now preserves deliberate processed-curve and raw
  sieve column positions when those positions still exist.
- A position that no longer exists clears to 'Not Used' instead of silently
  moving to the last available column.
- Automatic detection fills only roles that were unmapped before the header
  change; it no longer overwrites deliberate choices.
- Regression coverage verifies both preservation and empty-role detection, and
  the complete mapper test module passes.

### Mapper redesign

Status: Design approved and implemented on 2026-07-16; partially user
verified with representative processed and raw laboratory files.

- Reworked both `design_concepts/12_column_mapper.html` and the application
  dialog around an automatic-first confirmation workflow rather than exposing
  every mapper tool at once.
- Processed curves and raw sieve weighings use one adaptive surface with only
  the roles required for the selected input pathway.
- Header-row selection appears before column roles, and duplicate headings are
  identified by spreadsheet column letter.
- The source preview remains visible beside a persistent interpreted-curve
  preview and scientific validation checks.
- Irregular sheets use one sequential range guide with a single `Use selected
  cells` action and a single `Start over` action instead of four competing
  selection commands.
- The range guide adapts to two roles for processed curves and three roles for
  raw sieve weighings, including pan mass in the raw calculation.
- Saved processed and raw range mappings can be restored without reopening the
  mapper.
- A completed manual pattern can be tested against remaining mapping-required
  Excel targets. Every proposed result is parsed and scientifically validated
  before the user confirms applying the batch.
- Optional sample metadata is kept in a collapsed `Sample details` section.
- Mapper, loader, error-recovery, percentage-contract, reopen, and batch-pattern
  regression tests pass. User verification is still required before this item
  is marked complete.

User verification progress:

- [x] Processed irregular-range import completes and opens the resulting
  dataset in Individual Samples.
- [x] Raw sieve column mapping imports NBAL-01.xls correctly using the detected
  header and three weighing columns.
- [x] Processed clean-column mapping.
- [ ] Raw sieve irregular-range mapping.
- [ ] Batch pattern reuse across remaining mapping-required items. Deferred
  until a representative batch of files requiring the same manual mapping is
  available; normal automatic batch loading already covers compatible files.

## Workstream 3: ErrorTab Preview Failure

### Observed error

`Preview error: "ErrorTab" object has no attribute "headers_from_row"`

### Confirmed cause

`ErrorTab` calls `ColumnMapperDialog.detect_headers(self, rows)` with the `ErrorTab` instance as `self`. The mapper method then calls `self.headers_from_row(...)`, which does not exist on `ErrorTab`.

This is more than a missing method on `ErrorTab`. It shows that file parsing and header detection are coupled to the dialog class and are being reused through unbound method calls.

### Required outcome

- Move preview loading, header detection, and header construction behind shared non-UI functions or an import-preview service.
- Have both `ErrorTab` and the mapper call that service normally.
- Do not copy mapper methods onto `ErrorTab` or continue using cross-class unbound method calls.
- Add a regression test that opens an error-tab preview for CSV, TXT, and Excel inputs.

### Acceptance criteria

- Error tabs display the same rows and detected headers as the mapper.
- Preview failures show the underlying file problem, not an application attribute error.
- Opening the mapper from an error tab preserves the file, sheet, and prior mapping state.

## Workstream 4: Excel Freeze and Responsiveness

### Problem

Gro observed a blank mapper window and an unresponsive application after opening an Excel workbook, requiring Task Manager to close the program.

### Required investigation

The exact workbook and original packaged build cannot be obtained because the
feedback artifact is NDA-protected. This workstream is deferred rather than
reported as fixed. Reopen it only if the freeze recurs with a non-confidential
or deliberately sanitized reproducer, then capture timings and verify both the
source environment and packaged executable.

### Reactivation criteria

- A non-confidential reproducing workbook opens the mapper without a blank or frozen window.
- Slow operations show progress and provide cancellation.
- Closing or cancelling the mapper returns control to the application cleanly.
- Forced termination is not required for any supported input.

## Workstream 5: TXT and PDF Inputs

### Delimited TXT

Implemented on 2026-07-17. `.csv` and `.txt` now share one delimited-text reader
across the file pickers, drag-and-drop, standard loader, preview, mapper,
background mapped loading, pattern reuse, and source inspection.

Maintained fixtures cover comma, semicolon, tab, and pipe delimiters, European
decimal commas, UTF-8, Windows CP1252, and rejection of free-form text.
Vendor-specific behavior remains unverified and must not be claimed.

### PDF

Generic PDF import should not be included in the first remediation batch. Laboratory PDFs are presentation documents and may contain text tables, positioned glyphs, scans, or vendor-specific layouts.

If PDF import becomes a product requirement:

- collect representative files from each laboratory/vendor;
- implement format-specific extraction adapters;
- always show extracted values in the same mapper confirmation workflow;
- never analyze automatically extracted PDF values without user review.

Until then, unsupported PDF input should produce a clear message explaining the supported alternatives.

## Workstream 6: Large-Batch Reports

### Confirmed behavior

Eskild's report contains 51 samples. Calculations complete, but several plots become unreadable:

- grain-size overlay legends consume most of the page;
- class-fraction bars merge into a dense field;
- hydraulic-conductivity method bars are too crowded;
- dataset labels overlap in the boxplot.

This is a report-composition problem rather than a calculation failure. The lognormal K histogram remains useful and demonstrates that not every large-batch plot needs replacing.

### Required outcome

Use plot strategies that adapt to the number of samples:

- paginated small multiples or grouped summaries for many grain-size curves;
- a heatmap for class fractions across many samples;
- distributions or boxplots instead of a 51-series grouped method bar chart;
- abbreviated labels with a separate sample key;
- sensible legend suppression or pagination;
- an explicit preview notice when the report switches to a large-batch layout.

Exact thresholds should be selected through visual tests rather than assumed. Test at least 1, 7, approximately 15, and 51 samples.

### Acceptance criteria

- All plots are readable at A4 size in HTML, PDF, and DOCX outputs.
- Legends do not displace or cover the plot area.
- Labels do not overlap into an unreadable block.
- The 7-sample layout remains appropriately detailed.
- The 51-sample layout emphasizes comparison and distribution rather than attempting to label every mark.

### Implementation progress

The first scale-aware report chart was implemented on 2026-07-15 and is awaiting
user verification:

- class fractions remain grouped bars for fewer than 12 plotted samples/groups;
- 12 or more plotted samples/groups switch to a sample-by-class heatmap;
- the heatmap uses a fixed 0-100% scale, removes the categorical legend, and
  grows vertically up to an A4-safe limit;
- the preview/output includes a one-line large-batch explanation with the
  resolved sample/group count and heatmap semantics;
- visual fixtures were checked at 1, 7, 15, and 51 samples;
- the 51-sample image was verified in the DOCX path at 6.0 x 5.22 inches;
- the 51-sample HTML was printed through the application's Chromium A4 path
  without clipping; compact print-only plot spacing keeps the explanation,
  heatmap, and footer together without a footer-only trailing page.

This does not complete the large-batch report workstream. Grain-size overlays,
hydraulic-conductivity method comparisons, boxplots, and end-to-end PDF
verification still require separate changes.

A second composition-focused increment was implemented and user verified with
the 25-dataset workspace on 2026-07-15:

- comparison plot pages use A4 landscape orientation at 12 or more datasets,
  while narrative, table, and small-report pages remain portrait;
- the HTML preview shows those plots as distinct landscape sheets, and DOCX
  export creates matching portrait/landscape sections with wider plot images;
- the selected report preset and saved Customize values remain authoritative
  for typography, line styling, legend opacity, and explicit legend choices;
- when no legend placement/layout has been customized, large dataset legends
  automatically move below the axes and wrap into as many as four columns;
  the required bottom margin is derived from the resulting row count;
- the plot layout reserves a real gap between the x-axis title and the legend;
- large class-fraction heatmaps use 30-degree class labels while retaining the
  preset/custom tick size;
- large comparison boxplots and reliability matrices use landscape source
  dimensions while retaining the selected preset/custom style;
- the 7-dataset report retains its existing portrait layout and normal style;
- focused HTML/DOCX/reporting regressions pass, including a check that Word
  switches portrait-landscape-portrait and that legends do not overlap axes;
- choosing a preset clears prior Customize overrides, while Customize stores
  only values that actually differ from that preset; style changes are applied
  the next time the user explicitly presses `Generate Report`;
- landscape preview gaps now cover the narrower portrait sheet beneath them,
  avoiding the white-center/gray-side banding between mixed-orientation pages;
- enabling `Save companion Excel appendix` now replaces qualifying long tables
  with appendix notices in the live preview as well as the primary export;
  disabling it restores the tables, while the untouched report data remains
  available for generating the companion workbook.
- the user confirmed that the resulting landscape plot composition, smaller
  typography, and multi-row legend placement made the generated report
  substantially more readable.

This increment deliberately preserves every selected dataset curve. If the
real 25- and 51-dataset reports remain too dense after user testing, the next
step is semantic reduction (group summaries, pagination, or a sample key), not
further font-size reduction.

A page-utilization correction was implemented on 2026-07-15 and is awaiting
user verification:

- PDF printing now authoritatively removes the portrait report body's fixed
  820-pixel width and padding, allowing landscape plot pages to use their full
  printable width instead of leaving a large unused area;
- landscape DOCX plot images increased from 9.5 to 10.2 inches while remaining
  within the configured 16 mm page margins;
- portrait report pages and their existing plot sizes are unchanged;
- regression checks cover both the print CSS override and the generated Word
  image width.

### Final composition decision and cover polish

The report-output workstream was closed on 2026-07-17 with the following product decisions and final polish:

- the user accepted the mixed portrait/landscape large-batch composition and confirmed that the report plots now use the page well;
- reports retain only plots that the user can select and see in the application, plus tables containing actual program data;
- semantic substitute, summary, or fallback plots will not be invented by the exporter;
- the cover now uses a restrained technical-report hierarchy, includes project number and the user-entered report date, and remains balanced with or without a logo;
- no-image covers no longer fabricate an initials badge, and the Branding control provides an explicit text-only option;
- PNG, JPG, and SVG logos are bounded by both width and height; SVG logos are rasterized only for Word compatibility;
- the Word cover is composed from editable text, paragraphs, and tables, uses a hard page break before report content, and omits headers and footers from the first page;
- focused generation checks passed for text-only, wide/tall PNG, and SVG covers, including the Chromium PDF path and DOCX structure.

No representative client report artifacts will be added where NDA restrictions prevent their use. The existing synthetic and non-confidential fixtures remain the verification basis.

## Workstream 7: Onboarding and Help

### Problems

- `Getting Started` opens written help while `Help > Startup Guide` launches a different interactive tutorial.
- The main Samples sidebar is hidden on the welcome screen even though it is a primary data-loading location and a tutorial target.
- Advanced concepts such as scope and groups appear too early.
- The status line is difficult to see and is not essential to first-run success.
- Two visible areas are both labelled Help but behave differently.
- The startup tutorial exposes a `Do not show on startup` choice even though the tutorial is not automatically started and the completion callback does not apply that preference.

### Agreed information architecture

Use two explicit help categories throughout the application:

- `Guides`: written, searchable help pages and reference material.
- `Tutorials`: interactive overlays that point to and navigate through the live interface.

Rename visible `Tour`, `Guided Tour`, and interactive `Guide` labels consistently to `Tutorial`. Tutorial names should follow the same pattern, for example `Startup Tutorial`, `Individual Samples Tutorial`, `Comparison Tutorial`, `Reports Tutorial`, and `Export Tutorial`.

### Data Format & Files guide

Status: Core examples implemented and user approved on 2026-07-14. The
experimental multi-sample worksheet section was added and validated against the
maintained fixture on 2026-07-17.

The data examples must be among the first elements on the page, immediately after the short introduction and before loading methods, detailed rules, or troubleshooting. A new user should not need to scroll through reference text before seeing a valid table.

Provide clearly labelled, copyable examples for the input combinations the application expects:

1. Processed grain-size data in CSV.
2. Processed grain-size data in an Excel worksheet.
3. Raw sieve weighings in CSV.
4. Raw sieve weighings in an Excel worksheet.

Each example must show:

- the exact header row and several representative data rows;
- which particle-size unit is expected;
- the meaning and direction of cumulative percent passing;
- the required raw-weight columns and units;
- whether one file, worksheet, or column group represents one or several samples;
- a short `This works because...` explanation tied to what the loader or mapper detects.

CSV examples should show the delimiter and plain tabular structure. Excel examples should show the expected worksheet structure, header placement, sheet/sample naming, and when manual mapping is required. The examples must use the same terminology as the mapper, validation messages, and import commands.

#### Experimental multi-sample worksheet option

Add a clearly labelled `Experimental` section near the existing Excel format
examples. It must:

- show one shared-size/multiple-passing-columns example as the primary supported
  experimental layout;
- begin with the exact opt-in command: `Add > Multiple Samples in One File
  (Experimental)`; ordinary processed/raw imports must not be described as
  automatically discovering multiple samples;
- also describe repeated size/passing pairs and long tables with an explicit
  sample-ID column;
- require explicit particle-size and cumulative percent-passing/finer headers;
- state that retained values, incremental percentages such as `% Volume In`,
  merged or irregular headers, mixed units, and transposed tables may require
  manual mapping or source-file preparation;
- explain that the mapper proposes candidates, highlights their source cells,
  previews one interpreted curve at a time, and imports only checked samples;
- tell users to verify sample names, units, source columns, curve direction, and
  the preview before choosing `Import N samples`;
- use `test_data/multi_sample_shared_size.xlsx` as the maintained documentation
  and tutorial fixture;
- state the fallback plainly: cancel the candidate import and use the ordinary
  mapper, or prepare each sample as a supported single-sample table.

Do not describe the option as automatic support for every laboratory workbook.
Because representative exports are unavailable under NDA, keep the experimental
label for this feedback cycle. Reconsider it only if non-confidential or
deliberately sanitized exports later demonstrate the accepted layouts.

### Documentation quality audit

Status: Deferred until the functional and interface workstreams are stable.

Treat the `Data Format & Files` revision as the pilot for a broader, page-by-page review of all written Guides. Complete and test one page at a time rather than rewriting the whole documentation set in one pass.

Use a consistent information order where it fits the topic:

1. State the purpose and expected outcome in a short introduction.
2. Put the most useful valid example or primary task near the top.
3. Present the normal workflow before exceptions, troubleshooting, and reference detail.
4. Use headings, tables, lists, notes, warnings, and code examples according to their meaning rather than as decoration.
5. End with validation guidance and links to the next relevant Guides.

For every Guide, verify:

- factual accuracy against the current interface, loader, calculations, and export behavior;
- clear heading hierarchy and a sequence that supports scanning;
- consistent names for tabs, commands, fields, Guides, and Tutorials;
- concrete, selectable examples wherever a user must prepare data or choose settings;
- explicit units, accepted ranges, prerequisites, outcomes, and limitations;
- concise plain language without duplicate, stale, or contradictory instructions;
- useful cross-links without requiring users to search for the next step.

The audit is complete only when every visible Guide has been reviewed against these criteria and any intentionally deferred documentation gap is recorded explicitly.

### Agreed onboarding flow

1. Prompt once on first launch to start the short `Startup Tutorial`, with a working preference for suppressing future prompts.
2. Keep the main Samples sidebar visible on the welcome screen in a useful empty/import state.
3. Allow every tutorial to be launched directly from the welcome screen and from the `Tutorials` area in Help.
4. Let a tutorial navigate away from Welcome when its next target belongs to a workspace tab. For example, the Export Tutorial may replace the welcome content with the Export tab as it already does.
5. Ensure every tutorial step first activates and reveals its target before positioning the overlay; the user must not need to prepare the interface manually.
6. Offer the built-in demo data as the fastest successful first-run path.
7. Keep scope, groups, reporting detail, and the status line in advanced or contextual Guides and Tutorials.

### Acceptance criteria

- A new user can go from launch to a plotted demo dataset without searching menus.
- The main Samples sidebar remains visible and usable while the welcome screen is active.
- `Data Format & Files` presents valid CSV and Excel examples near the top of the page without requiring substantial scrolling.
- The format examples cover both processed curves and raw sieve weighings and match the real loader/mapper requirements.
- Every Tutorial can be started from Welcome and automatically navigates to any tab or control required by its steps.
- A Tutorial never points at UI that is hidden after its preparation step.
- Guides and Tutorials have distinct labels and purposes everywhere they are exposed.
- Startup preferences correspond to real startup behavior.

## Workstream 8: Navigation

Both testers looked for a way back to the front page. Eskild adapted to the navigation, while Gro remained uncertain.

Agreed direction:

- Add `Home` as a persistent top-level tab alongside the four existing workspace tabs.
- The Home tab displays the welcome/dashboard content and keeps the main Samples sidebar visible.
- Switching to Home must preserve all loaded datasets, current analysis state, and the other workspace tabs.
- Tutorials can start from Home and activate another top-level tab when required by the tutorial step.
- Keep `New Workspace` or `Clear Workspace` as a separate action with confirmation.
- Never make the Home tab silently unload or reset data.

The existing Clear All behavior should be reviewed as part of this work to ensure it also removes dataset tabs and synchronizes all comparison, report, and export state.

### Acceptance criteria

- `Home` is visible next to the four existing top-level tabs whether or not datasets are loaded.
- Selecting Home returns to the welcome/dashboard without changing the loaded workspace.
- Returning from Home to another tab restores the existing analysis state.
- Home remains distinct from destructive `New Workspace`, `Clear Workspace`, and `Clear all samples` commands.

## Workstream 9: Dataset and Plot Controls

### Scope & Groups range selection

Status: Implemented and user verified on 2026-07-14.

The Scope & Groups dialog currently treats each row click as an independent toggle. It should support the familiar select-from-X-to-Y interaction without changing which datasets are included in the analysis.

Required behavior:

- A plain click on a row selects that row and establishes the range-selection anchor.
- `Shift`+click selects the contiguous range from the anchor row to the clicked row.
- `Ctrl`+click toggles individual rows for non-contiguous selection.
- `Ctrl`+`Shift`+click adds a contiguous range to the existing selection.
- Range selection follows the currently visible row order after filtering and grouping; hidden rows are not unexpectedly selected.
- Clicking a dataset's inclusion checkbox continues to control scope only. Row selection for grouping must not check or uncheck datasets.
- Filtering, rebuilding, and regrouping the list must preserve or reset the anchor predictably rather than leaving an invisible anchor.
- Where practical, `Shift`+Up/Down should provide the keyboard equivalent.

Acceptance criteria:

- Selecting row X and then `Shift`+clicking row Y selects every visible row between them.
- Range selection works in both filtered and grouped views.
- Inclusion checkboxes remain unchanged while rows are selected for a grouping action.
- Plain, additive, and range selection have visible and distinguishable states.

### Legend layout control

Status: Implemented and user verified on 2026-07-15.

The current choices (`Vertical (1 column)`, `Two columns`, and `Horizontal (fit)`) do not provide enough control. In particular, `Horizontal (fit)` effectively attempts to place all entries in one row instead of wrapping a larger legend across sensible rows and columns.

Recommended interaction:

- Replace the three fixed labels with a `Legend columns` control offering `Auto` and explicit column counts.
- Let the number of rows be derived from the entry count and chosen column count. Do not expose simultaneous row and column settings that can conflict.
- Make `Auto` fit the available legend width, label lengths, and legend position instead of equating fit with one row.
- Allow top and bottom legends to wrap across multiple rows. Side legends should normally use fewer columns.
- Preserve group headers and their member ordering when a structured legend wraps.
- Persist the chosen mode with the plot style and apply it consistently to on-screen plots and exported output.

Acceptance criteria:

- Legends with 2, 8, and 20 or more entries can be made readable without label clipping or overlap.
- `Auto` wraps to multiple rows when a one-row legend does not fit.
- Explicit column counts produce a predictable derived row count.
- Changing legend layout does not obscure the plot or break grouped legend structure.

Implementation record:

- Replaced `Horizontal (fit)` with a single `Legend columns` control offering
  `Auto (fit and wrap)` and explicit 1, 2, 3, or 4-column choices.
- `Auto` estimates the width required by the actual label text and active
  legend font before choosing a column count.
- Automatic top and bottom legends can use up to four columns; side legends
  remain vertical, and inside legends use at most two columns.
- Explicit choices are clamped only when fewer legend entries exist, so their
  derived row counts remain predictable.
- The shared resolver is used by interactive plots and report/export rendering,
  including structured comparison legends without changing handle order.
- Large reports now request the shared automatic layout instead of baking in a
  fixed four-column legend.
- Focused regression coverage includes short and long labels, inside/side
  positions, explicit column counts, and the Comparison/Report UI choices.
- User testing confirmed that automatic wrapping and the explicit column
  choices work as intended in the generated report workflow.

### Shared plot Customize controls

Status: Implemented and user verified. The Lines & Markers increment was
verified on 2026-07-15, and the corrected independent major/minor Grid
increment was accepted on 2026-07-16.

Implemented in this increment:

- Reorganized the dialog into scrollable Typography, Lines & Markers, Grid,
  and Legend accordion sections using the application's shared section
  component.
- Consolidated those accordions into one shared control implementation used by
  the Individual plot sidebar, Comparison plot sidebar, and report/export
  Customize dialog.
- Individual and Comparison plots retain their local style state, while
  Report and Export continue sharing their persisted output style; the control
  definitions, ranges, labels, reset behavior, and marker semantics are common.
- Removed the duplicate Individual plot 'Markers on curve' toggle so marker
  visibility has one source of truth in the Lines & Markers accordion.
- Made the shared Lines & Markers accordion contextual: it is hidden for
  K-value bar charts and grain/lognormal histograms, while remaining available
  for distribution curves, combined plots, and the empirical K-value CDF.
- Added curve width and marker-size controls across interactive plots and
  report/export plots.
- Added a three-state marker control: Preset behavior, Show, or Hide.
- Preset behavior leaves the selected preset and captured plot behavior intact;
  explicit Show or Hide remains authoritative across single-sample and
  comparison distribution curves.
- Marker size is disabled while Hide is selected.
- Saved values remain overrides on the selected preset and are applied only
  after the user explicitly generates the report again.
- User testing confirmed the shared controls work across Individual,
  Comparison, and Report/Export contexts, including contextual removal of
  irrelevant Lines & Markers controls from bar and histogram plots.
- Added a collapsed shared Grid accordion with major-grid visibility,
  minor-grid visibility, solid/dashed/dotted/dash-dot line styles, and separate
  major/minor opacity controls.
- Major and minor visibility are independent; hiding the major grid does not
  disable or suppress an enabled minor grid.
- Removed the duplicate grid row from the Individual and Comparison Display
  Options sections. The Individual toolbar Grid button remains as a quick
  action and stays synchronized with the shared accordion; Comparison uses the
  accordion as its single grid control.
- Consolidated hardcoded renderer grids behind one shared major/minor grid
  contract so interactive plots, report plots, and export plots honor the same
  visibility, opacity, and line-style settings.
- Report/Export grid overrides persist on the selected preset and still wait
  for an explicit Generate Report action before changing report output.
- Regression coverage verifies toolbar synchronization, Comparison behavior,
  major/minor rendering, persisted overrides, and preservation in large-report
  composition.

Planned later increments:

- Additional legend frame and spacing controls if user testing shows value.
- Keep analytical plot settings out of this dialog.

### Plot visibility sidebar

Status: Implemented and user verified on 2026-07-14.

When many datasets are loaded, the vertical scrollbar in the `Plot visibility` sidebar overlaps the rightmost pin button. This makes a primary row action partly hidden or difficult to click.

Required outcome:

- Reserve a stable scrollbar gutter whenever vertical scrolling may be needed.
- Keep the eye and pin actions in a fixed right-aligned action area that remains fully inside the scroll viewport.
- Do not let the scrollbar cover controls, focus indicators, or tooltips at any supported display scale.
- Preserve useful content width for dataset names, using elision and tooltips where necessary.

Acceptance criteria:

- Every eye and pin button remains fully visible and clickable with 5, 25, and 50 or more datasets.
- The sidebar works at 100%, 125%, 150%, and 200% Windows display scaling.
- Mouse-wheel and keyboard scrolling reach the final row without covering its controls.
- The fix does not introduce a horizontal scrollbar or resize rows when the vertical scrollbar appears.

### Main Samples sidebar

The Samples header currently spreads counts, filters, and Scope & Groups across several short rows while the available batch actions are not visible. The existing Clear All control is located in a batch panel that is permanently hidden. Adding bulk actions must also avoid conflating three different states:

- the active sample whose tab or details are open;
- samples included in comparisons and reports;
- samples temporarily batch-selected for a bulk action.

Recommended interaction:

- Keep normal card clicks for activating a sample and keep the inclusion control dedicated to comparison/report scope.
- Add standard `Ctrl` additive selection and `Shift` range selection for batch operations, with a clearly different visual treatment from both active and included states.
- Provide explicit `Select all visible`, `Clear selection`, and `Remove selected...` actions.
- Use `Remove selected...` for unloading selected samples. Do not call this destructive action `Clear selected`, which can be confused with merely clearing the selection.
- Keep `Clear all samples...` available in the Samples actions menu and require confirmation that states how many samples and related tabs will be removed.
- Ensure removal synchronizes the sidebar, sample tabs, comparison scope, reports, and export state.

Recommended compact layout:

- One header row: `SAMPLES`, Add, a batch-select action, Scope & Groups, and an overflow actions menu. Use icons with tooltips where full labels do not fit.
- One compact status line for loaded, included, and review counts; it must not wrap into separate chip rows.
- One stable segmented filter row for `All`, `Included`, and `Review`.
- When batch selection is active, replace the filter row with a contextual selection bar showing the selected count and the relevant bulk actions.
- Do not cram actions into a row that wraps unpredictably. The sidebar should keep stable heights at supported text and display scales.

Acceptance criteria:

- Users can batch-select adjacent and non-adjacent samples without changing which samples are included.
- `Clear selection` is non-destructive, `Remove selected...` removes only the batch selection, and `Clear all samples...` removes everything after confirmation.
- The active, included, and batch-selected states remain visually distinguishable.
- The header does not wrap or create isolated one-button rows at supported sidebar widths and 100% to 200% display scaling.
- Bulk removal leaves no orphaned tabs, comparison entries, report records, or export records.

### Active dataset status bar

Status: Noted for later.

The bottom status bar may not update when the user activates a different
dataset. Verify the intended contents and current signal wiring before changing
it. If it is meant to identify the active dataset, it should follow the
currently clicked sample and clear or fall back appropriately on Home and after
workspace removal actions.

### Additional plot selector

Status: Deferred in favor of higher-impact workflow changes.

The `More Plots?` combo uses a question as a selectable placeholder, which makes it look like an unresolved prompt rather than a plot control.

Recommended outcome:

- Keep the two common plot types as the existing primary segmented buttons.
- Replace the combo with an `Other plots` menu button listing `Combined` and `Histogram`.
- Do not include a fake selectable header item in the menu.
- When an additional plot is active, show its name as the active plot state instead of leaving the toolbar with no apparent selection.

Acceptance criteria:

- Every toolbar state clearly identifies the plot currently displayed.
- Selecting a primary plot resets the additional-plot state without briefly rendering the placeholder as a plot choice.
- The control is labelled consistently in the application tour and help text.

### K-value tick-size defect

Status: Implemented and user verified on 2026-07-14.

In the comparison Plot subtab, changing `Tick size` does not change the K-value plot's x-axis method labels. The overlay renderer currently assigns a fixed size to those labels while applying the configured tick size only to the y-axis. The faceted K-value view also uses fixed tick sizes.

Required outcome:

- Apply the selected `tick_fontsize` to both x- and y-axis tick labels in K-value overlay and faceted views.
- Keep rotation and compact method-name formatting independent from font size.
- Ensure later rendering calls do not overwrite the configured size with fixed values.
- Apply the same style contract to on-screen rendering and exported plots that use these renderers.

Acceptance criteria:

- Changing Tick size from the minimum to the maximum produces a visible and measurable change on both K-value axes.
- The setting works in overlay, grouped, and faceted K-value displays.
- Long method labels remain readable and do not collide at the default size.
- A regression test asserts the rendered x- and y-tick font sizes rather than only checking the stored style value.

## Workstream 10: Units and Typography

### K-value units

Recommended convention:

- `m/s` is the primary value because it is the SI unit and is commonly used in downstream calculations.
- `m/d` is shown as a secondary hydrogeological value.
- `cm/s` remains available where useful but should not displace the two primary units.

The current source already defines a statistics table containing `m/s`, `cm/s`, and `m/d`, while the top result summary uses only `m/d`. Verify whether Gro tested an older build or whether the rightmost unit was clipped before changing the table.

### Typography

Different fonts are partly intentional: interface text and monospaced numerical values have different roles. The task is therefore a consistency audit rather than an automatic switch to one font.

Acceptance criteria:

- The same content role uses the same font treatment across pages.
- Numeric emphasis does not look like an accidental fallback font.
- Compact summary values remain readable without clipping.

## Workstream 11: Multi-File Selection and Batch Counts

Eskild believed the first file dialog only allowed one file at a time. The current source uses the native Windows multi-file dialog, and Shift/Ctrl selection has now been user verified. No custom file picker is required.

Actions:

- [x] Verify native Shift and Ctrl multi-file selection.
- [x] Keep the native picker rather than introducing a custom selection workflow.
- [ ] Decide whether a completed batch needs a persistent outcome summary.
- [ ] If implemented, distinguish selected source files, expanded file/sheet import items, loaded items, duplicates, failures, and items waiting for review.

Eskild described a 52-file batch, while the attached report contains 51 samples. This discrepancy should be reconciled so no skipped sample is hidden in aggregate counts.

## Workstream 12: Export Presets and Tutorial Clarity

Status: Implemented on 2026-07-17. The compact UI, Export Tutorial, and written Export guide are aligned; representative output-package verification remains.

### Decisions implemented

- Recipes are named for their output: `CSV + Grain Curves`, `Summary CSV`, `Analysis Tables`, `Workbook + Plots`, `Complete Package`, and `Custom`.
- Every recipe has a one-sentence package description and updates the live file summary immediately.
- The six format cards are replaced by one grouped, checkable `Formats` selector with an opaque field and popup.
- Export scope reuses the always-visible sidebar `Scope & Groups`; no duplicate scope-management button is shown.
- `Included Content` separates data tables, individual plot files, and comparison plot files. Plot tabs are flat checklists without redundant inner accordions or include-all headers.
- `Plot Appearance` is a separate conditional section. Preset, palette, and `Customize` control styling; plot checklists only decide which figure files are created.
- Review exposes the planned file tree, selected plot queue, real plot preview, output folder, and a `Go to Sample` navigation shortcut for individual plots.
- Sample and group labels use shared natural ordering across previews, CSV/Excel exports, plots, aggregates, and reports while preserving plot-context alignment.
- The Export Tutorial now follows the final `Configure` → `Review` → export order and distinguishes plot selection from shared `Plot Appearance`.
- The written Export guide documents scope, recipes, formats, content, plot appearance, review controls, dated output names, file counts, ordering, and troubleshooting.
- `Files to Create` shows the same dated filenames used by the writer, and `Summary CSV` remains a true one-file recipe by excluding collection aggregates.

### Remaining verification

- Manually verify representative CSV-only, Excel, and plot packages against the Review manifest.

## Positive Findings and Regression Requirements

The following behavior should be protected rather than redesigned:

- installation completed without problems;
- CSV loading worked for small and large batches;
- duplicate files were handled without an obvious crash;
- generated results broadly agreed with prior interpretations;
- built-in demo data provided a useful first dataset;
- method explanations were useful and should remain available.

Small-screen behavior was not tested. It should be recorded as an open test gap, not as a successful result.

## Recommended Implementation Sequence

### Phase 0: Capture reproducible evidence

- [x] Record that the original Excel/TXT artifacts, exact expected interpretation, original build, and source-file manifest are unavailable under NDA.
- [x] Stop treating the original Excel freeze and 52-versus-51 discrepancy as reproducible acceptance blockers.
- [x] Create non-confidential delimiter fixtures under `test_data/txt_delimiters`; do not claim they reproduce unavailable vendor files.

### Phase 1: Stabilize the import foundation

- [x] Extract shared preview and header detection from dialog classes.
- [x] Fix the ErrorTab preview failure.
- [x] Add consistent TXT picker, preview, mapping, loading, and help support.
- [x] Add import-candidate and mapping-state models that can represent one or many datasets.
- [ ] Finalize retained-data support only if a non-confidential supported-format requirement is supplied. The interim cumulative-passing guard remains the current boundary.
- [x] Defer the Excel freeze because the NDA-protected reproducer and original build are unavailable; reopen only with a non-confidential reproducer.

### Phase 2: Replace the mapper workflow

- [x] Implement the automatic-first confirmation flow.
- [x] Put header-row selection before column roles.
- [x] Preserve deliberate mappings across header changes.
- [x] Add a sequential irregular-range workflow.
- [x] Add final curve preview and inline validation.
- [x] Collapse advanced metadata and reveal batch reuse only when applicable.
- [x] Use the same mapper dialog for initial import and error recovery.
- [ ] Verify processed columns, processed ranges, raw columns, raw ranges, and
  batch pattern reuse with maintained synthetic fixtures. Record that vendor
  workbook coverage is unavailable.

### Phase 3: Add multi-sample worksheet import

- [x] Detect shared-size/multiple-series layouts.
- [x] Detect repeated size/percentage pairs.
- [x] Disambiguate duplicate headers by Excel column.
- [x] Preview and select candidate samples before import.
- [x] Import each selected curve as a separate dataset.
- [x] Separate the feature behind an explicit experimental import command so
  normal NBAL and other established single-sample pathways are not probed.
- [x] Verify the maintained shared-size, repeated-pair, and long-table fixtures.
- [x] Add the experimental multi-sample worksheet section to `Data Format &
  Files`, including supported examples, limitations, verification steps, and
  the manual-mapping fallback.
- [x] Keep the feature experimental because representative laboratory validation
  is unavailable under NDA; reconsider only with non-confidential evidence.

### Phase 4: Make report output scale-aware

- [x] Establish visual thresholds using 1, 7, 15, and 51-sample fixtures.
- [x] User-verify the adaptive class-fraction layout and mixed-orientation large-batch composition.
- [x] Close semantic chart replacement: retain only plots selected and visible in the application; do not invent exporter-only fallback plots.
- [x] Close pagination/group-summary fallbacks as unnecessary after the landscape composition was accepted.
- [x] Replace `Horizontal (fit)` with automatic wrapping and explicit legend-column control.
- [x] User-verify automatic and explicit legend columns with small and large plot scopes.
- [x] Reserve space for the Plot visibility scrollbar and verify all row actions at large dataset counts and high display scaling.
- [x] Make K-value x- and y-axis ticks honor the shared Tick size in overlay and faceted views.
- [x] Verify mixed-orientation HTML, PDF, and DOCX output at A4 size.

### Phase 5: Improve everyday interaction and navigation

- [x] Put prominent, valid processed/raw CSV and Excel examples at the top of `Data Format & Files`.
- [ ] After the functional workstreams are stable, review the remaining Guides one page at a time for hierarchy, accuracy, examples, terminology, and useful cross-links.
- [x] Separate written `Guides` from interactive `Tutorials` throughout the UI and help content.
- [x] Rename interactive tours and guided tours consistently to Tutorials.
- [x] Keep the main Samples sidebar visible and usable on the welcome screen.
- [x] Make every Tutorial launchable from Welcome and automatically reveal each required tab/control.
- [x] Make the Getting Started tutorial call the main area the `Samples panel`, spotlight the complete Help menu, remove the redundant toolbar Help shortcut, and retain F1 for direct Written Guides access.
- [ ] Delay advanced concepts until after the first successful import.
- [x] Add a persistent, non-destructive Home tab alongside the four existing workspace tabs.
- [x] Replace audience-based Export preset names with reviewed output-based recipes and package descriptions.
- [x] Complete the final Export Tutorial walkthrough against the compact control order and remove redundant explanation.
- [x] Rewrite the written Export guide to match the final scope, recipe, format, content, appearance, Review, and output behavior.
- [x] Review Clear/New Workspace state synchronization.
- [x] Reorganize the Samples header into stable header, status, and filter states without wrapping.
- [x] Add a distinct batch-selection mode with range/additive selection, Clear selection, Remove selected, and Clear all samples.
- [ ] Later polish: replace the `More Plots?` placeholder combo with an `Other plots` action menu and an explicit active state.
- [x] Add standard plain, `Ctrl`, `Shift`, and `Ctrl`+`Shift` row selection to Scope & Groups without changing dataset inclusion.
- [x] Standardize visible K-value units.
- [ ] Audit typography roles and clipping.

### Phase 6: Final release communication

- [x] At the end of this update, replace the Home page's hardcoded `What's New`
  summary with the final version, date, and user-facing highlights.
- [x] Update both the repository and bundled application changelogs with the
  complete release changes, keeping `CHANGELOG.md` and
  `Program/CHANGELOG.md` synchronized.
- [x] Cross-check `What's New`, the changelog, Guides, version number, and release
  date so they describe the same shipped behavior without unfinished or
  NDA-dependent claims.
- [x] Align the application, executable metadata, folder-build version, and
  installer version, and reject mismatched release commands.

## Product Decisions Recommended for Approval

1. Use `m/s` as the primary K-value display and `m/d` as the secondary display.
2. Support delimited TXT as a CSV-like input format.
3. Defer generic PDF import until representative vendor formats are available.
4. Add Home as a persistent, non-destructive top-level tab and keep workspace clearing separate.
5. Replace the existing mapper interaction model instead of incrementally adding more instructions to it.
6. Require cumulative percent passing for processed input, block clear contradictions, and do not infer or automatically transform retained data.
7. Use standard desktop range-selection semantics in Scope & Groups while keeping selection and inclusion as separate states.
8. Control legend wrapping through `Auto` or an explicit column count, with the row count derived automatically.
9. Treat active, included, and batch-selected samples as three separate states in the main sidebar.
10. Use `Clear selection` only for a non-destructive deselection; use `Remove selected...` and `Clear all samples...` for destructive actions with confirmation.
11. Keep the two primary plot buttons and expose Combined and Histogram through an `Other plots` menu without a fake placeholder item.
12. Use `Guides` for written help and `Tutorials` for interactive overlays throughout the application.
13. Keep the main Samples sidebar visible on Home/Welcome as well as in the loaded workspace.
14. Put processed/raw CSV and Excel examples before detailed reference material in `Data Format & Files`.

## Definition of Done for This Feedback Cycle

This feedback cycle is complete only when:

- Gro's workbook imports without freezing and produces the expected number of correctly oriented curves;
- the irregular-sheet workflow can be completed without knowledge of internal selection modes;
- ErrorTab preview and recovery use the same reliable import services as normal import;
- TXT behavior is consistent across picker, drag-and-drop, loader, mapper, and help;
- a 51-sample report remains legible on A4;
- first-time users can reach a successful demo analysis without contradictory guidance;
- `Data Format & Files` opens with accurate, readily visible processed/raw CSV and Excel examples;
- all interactive Tutorials can start from Home/Welcome and reveal their required targets automatically;
- the Samples sidebar remains visible on Home and Home preserves the loaded workspace;
- Scope & Groups supports predictable X-to-Y range selection without changing dataset inclusion;
- large legends can wrap across multiple rows with an automatic or explicit column layout;
- the Plot visibility scrollbar never covers eye or pin controls, including with 50 or more datasets and high display scaling;
- the Samples sidebar supports clearly differentiated batch selection, selected-sample removal, and complete clearing without wrapping its controls;
- every plot toolbar state clearly names the active plot and no `More Plots?` placeholder remains;
- K-value x- and y-axis ticks both respond to the configured Tick size in every comparison display mode;
- all supported views make `m/s` readily visible;
- imported, skipped, duplicate, failed, and review-required counts are explicit;
- regression tests cover the real files and workflows that produced this feedback.
