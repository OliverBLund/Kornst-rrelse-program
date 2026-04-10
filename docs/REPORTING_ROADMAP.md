# Reporting System Roadmap

Last updated: April 10, 2026

## Purpose

This document tracks the reporting system as a living work plan.
It is focused on making report generation flexible, reliable, and client-friendly,
with appendix generation and editable Word export as the main product goals.

## Current Assessment

Status: beta candidate for appendix-oriented reports

What is working well now:
- HTML preview and PDF export are functional.
- DOCX export is functional for the live HTML report output.
- Individual, comparison, combined, and full-project report modes exist.
- Branding, metadata, and section toggles already provide useful flexibility.
- Report settings and appendix label settings persist between sessions.
- The appendix preset is already a reasonable starting point for technical outputs.

What is still limiting the system:
- Report generation is still HTML-string driven rather than model driven.
- Preview pagination is closer to PDF now, but still heuristic.
- DOCX export is based on the current HTML output path rather than a shared renderer model.
- Templates are checkbox presets, not true content/layout templates.
- Comparison and full-project reporting still need a more deliberate project-level format.

Best current use:
- Generate polished appendix-style HTML/PDF/DOCX output from selected report sections, especially appendix-oriented deliverables.

## Product Decisions

- [x] Keep the current reporting system and continue expanding it.
- [x] Prioritize DOCX export because clients may want to edit the report after export.
- [x] Treat appendix labels as presentation, not hardcoded structure.
- [x] Allow one appendix or many appendices.
- [x] Support automatic and manual appendix labeling.
- [x] Support either one combined appendix or multiple appendix sections.
- [ ] Full rich-text in-app report editing is not in scope right now.
- [ ] Light structured editing remains a later phase.

## Recent Completed Fixes

- [x] Fixed combined-report cover-page merge fragility.
- [x] Fixed comparison/full-project sample identity to avoid duplicate-name collisions.
- [x] Fixed comparison/full-project temperature and porosity handling so values can vary by sample.
- [x] Cleared stale preview/export state after failed report generation.
- [x] Escaped metadata and notes before injecting HTML.
- [x] Improved preview/PDF page-geometry alignment.
- [x] Wired the grain-size appendix section to the shared report model and flexible appendix labels.
- [x] Surfaced appendix label options in the reporting UI and passed them into live report generation.
- [x] Added single-appendix layout support in the report model, generator, and UI.
- [x] Implemented DOCX export from the live generated report HTML.
- [x] Added report-setting persistence for template, section, type, and metadata fields.
- [x] Added dedicated report-model and report-generator regression tests.

## Roadmap

### Phase 1 - Report Document Model

Goal: make report content structured before rendering it.

Status: in progress

- [x] Add a neutral internal report model.
- [x] Define core block types:
  - metadata block
  - heading block
  - paragraph block
  - table block
  - image/figure block
  - page break block
  - appendix section block
- [x] Represent appendix blocks independently from their visible label.
- [x] Add appendix label configuration:
  - auto labels
  - manual labels
  - label scheme support such as `A/B/C`, `1/2/3`, `A1/A2/A3`
- [ ] Move report-content assembly toward the model instead of writing raw HTML directly.

### Phase 2 - Renderer Separation

Goal: render the same report model to multiple outputs consistently.

Status: in progress

- [ ] Keep HTML/PDF as the first renderer path.
- [ ] Preserve the current visual style where possible.
- [ ] Reduce preview/export differences further.
- [ ] Separate content generation from HTML styling concerns.

### Phase 3 - DOCX Export

Goal: produce editable Word documents for clients.

Status: in progress

- [ ] Add DOCX rendering from the shared report model.
- [x] Implement `.docx` export in the reporting tab.
- [x] Map headings, tables, figures, captions, page breaks, and appendix labels to Word structures.
- [x] Carry branding into DOCX where practical.
- [x] Add smoke tests for generated DOCX files.

### Phase 4 - Structured In-App Editing

Goal: allow useful report adjustments without building a full word processor.

Status: not started

- [ ] Allow editing of section titles.
- [ ] Allow editing of notes and intro text blocks.
- [ ] Allow include/exclude and reordering of appendix blocks.
- [ ] Allow editing of appendix labels directly.
- [ ] Consider saved report presets if the workflow proves useful.

Not planned in this phase:
- [ ] Full rich-text freeform WYSIWYG editing.

## Current Focus

Current active task:
- [ ] Run live smoke tests on HTML/PDF/DOCX export and capture any layout issues before beta.

Immediate deliverables for this task:
- [x] Decide the model classes and field structure.
- [x] Decide where appendix labeling lives in the model.
- [x] Introduce the first implementation in code.
- [x] Add the first dedicated tests for report-model behavior.
- [x] Use the model in at least one live report path.
- [x] Add single-appendix layout support for live appendix generation.
- [x] Implement a first real DOCX export path.
- [x] Persist report configuration that beta users will expect to survive restarts.
- [ ] Move one more report path or shared section builder onto the model.
- [x] Decide how appendix label options should surface in the reporting UI.

## Suggested Initial File Layout

This is the current intended direction, not a strict commitment:

- `Program/report_model.py`
- `Program/report_generator.py`
- `Program/gui/reporting_tab.py`
- `Program/tests/test_report_model.py`
- `Program/tests/test_report_generator.py`

## Update Rule

When a reporting task is completed:

1. Mark the task complete in this file.
2. Move the next active task into `Current Focus`.
3. Keep completed tasks here unless the section becomes too noisy.
4. Update this file before or alongside the code change that completes the task.
