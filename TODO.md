# GrainSize Analysis - Pre-QA Roadmap

Last updated: 2026-06-17

Goal: get the program stable enough for the next tester round and then produce a release-candidate `.exe`. This roadmap is intentionally focused on remaining release work, not future feature ideas.

## Release Principle

- Freeze new feature scope unless testing finds a real workflow blocker.
- Prefer backend/shared-data fixes over UI-local calculations.
- Keep visible UI changes small, deliberate, and testable.
- Every fixed workflow should be checked in the running app and covered by at least a targeted regression test when practical.

## Priority Legend

- P0: Blocks final QA or can produce wrong/misleading output.
- P1: Strong usability issue likely to confuse testers.
- P2: Polish or cleanup that should not block the next tester round.

## P0 - Correctness And Release Blockers

- [ ] Verify data loading end-to-end for processed CSV, raw sieve CSV, processed Excel, raw sieve Excel, irregular Excel mapper, and multisheet Excel.
- [ ] Verify wrong-mode imports clearly report how the data was actually interpreted.
- [ ] Confirm calculated K geometric mean and arithmetic mean match HydrogeoSieveXL2 expectations for the demo/test datasets.
- [ ] Confirm warning/error K-method inclusion rules are identical everywhere: Results, Details, Statistics, Comparison plots, Reports, and Export.
- [ ] Verify aggregate K statistics use the shared backend aggregation model, not UI-local recalculation.
- [ ] Verify grouped aggregate statistics use the same backend model as overall aggregate statistics.
- [ ] Fix or explicitly document the calculated porosity workflow:
  - Decide whether both "Simple Formula" and "Urumovic Polynomial" should remain visible.
  - Make the default and impact on K calculations clear.
  - Confirm report/export include the porosity value actually used for calculations.
- [ ] Audit generated reports for correctness:
  - Tables do not go off page.
  - Report plots match the same renderers/settings used in the app where possible.
  - No stray page-number text appears.
  - Report generation works repeatedly in the same session.
- [ ] Verify export outputs include the exact visible plot/table data where relevant, especially single-plot and comparison-plot table drawers.

## P1 - UI/UX Hardening Before Final QA

- [x] Manually QA the redesigned Comparison > Details sidebar.
  - Approved concept: `design_concepts/19_comparison_details_sidebar.html`.
  - PyQt implementation is in `Program/gui/comparison_tab.py`.
  - Should prioritize compact, useful summaries over many dense rows.
  - Should avoid repeated decorative borders and cramped key/value lines.
- [x] Manually QA the redesigned Comparison > Statistics sidebar.
  - Draft concept: `design_concepts/20_comparison_statistics_sidebar.html`.
  - PyQt implementation is in `Program/gui/comparison_tab.py`.
  - Should show useful scope/filter/aggregate summaries without stealing plot space.
  - Should avoid duplicating data already visible in the table below the plot.
- [x] Remove the ambiguous Comparison > Statistics `Range` metric button.
  - Range remains visible as a min-to-max table/sidebar result where it has clear meaning.
- [x] Make Comparison > Details result tables expand into available width for small column counts.
- [x] Stabilize Comparison > Plot drawer table formatting on first open.
  - Drawer rows use fixed compact sizing immediately instead of relying on hidden-table auto-sizing.
- [x] Stabilize Individual Samples plot drawer table formatting to match Comparison > Plot.
  - Single-sample drawers now use the same compact fixed row/header sizing as comparison drawers.
- [x] Hide the redundant Comparison > Details dataset strip in individual mode.
  - Aggregate mode still shows group chips because they explain aggregate columns.
- [x] Hide the Individual Samples dataset tab strip.
  - The sidebar Samples section is the primary dataset navigation; the tab widget remains as the internal page container.
- [x] Make Comparison > Details heat coloring opt-in by default.
  - Entering the Details subtab resets heat coloring to off so tables start in a calm readable state.
- [x] Remove redundant Dataset & Group Manager toolbar action and improve button affordance.
  - `Select Visible` was removed; default/plot/action buttons now have a clearer light face and stronger border.
- [ ] Recheck Details toolbar behavior:
  - Individual mode: Grain/K-values should switch actual table content.
  - Aggregate mode: either clearly disable Grain/K-values or split aggregate into true Grain and K aggregate views.
- [ ] Recheck Statistics toolbar behavior:
  - Valid in all must not resize the program window.
  - Unit changes must not resize the program window or toolbar controls.
  - Metric/method/status toggles must keep layout stable.
- [ ] Review the main sidebar Samples section sizing.
  - Cards should be readable at default width.
  - Included/All/Review/Manage controls should not feel cramped.
  - Long sample names should truncate/wrap cleanly without shifting controls.
- [ ] Decide whether top toolbar `Add Data` and `Calculate K` should stay.
  - If kept, clarify why they exist in addition to sidebar/welcome actions.
  - If removed, keep equivalent actions available through the sidebar/menu/shortcuts.
- [ ] Recheck plot sidebars and drawer behavior across common screen sizes.
  - Controls must scroll rather than push content offscreen.
  - Opening/closing sidebars should not reserve stray empty space.
  - Export CSV/PNG/SVG actions should be available and consistent.

## P1 - Plot Improvements Still To Audit

- [ ] Single distribution curve:
  - D10/D50/D60 should be the default reference lines.
  - D30 should not replace D50.
  - Reference lines should be readable without overpowering the curve.
- [ ] K-value bar plot:
  - Show both geometric and arithmetic means, or make the displayed mean explicit.
  - Provide a clear way to hide/resize K labels above bars.
  - Avoid log-scaled y-axis by default unless explicitly enabled.
- [ ] Grain-size histogram:
  - Default y-axis should be weight percent / retained percent, not generic frequency.
  - Fraction labels should respect the selected stratigraphy scheme.
  - Drawer/export should contain histogram data, not distribution-curve data.
- [ ] Comparison plots:
  - Group coloring and line styles should be consistent with dataset/group scope.
  - Table drawer should describe exactly which data is shown/exported.
  - K distribution/lognormal plot should include geometric mean and ln(K) variance/std-dev context.

## P1 - Reports And Export

- [ ] Reports tab:
  - Confirm all report presets generate reliably.
  - Confirm report sample selection is clear.
  - Confirm report plot outputs match app plot defaults or documented report defaults.
  - Confirm wide comparison tables fit A4/PDF output.
- [ ] Export tab:
  - Include full detail dump plus aggregate/group aggregate tables.
  - Ensure export names clearly distinguish raw data, processed curve data, plot drawer data, and aggregate statistics.
  - Confirm selected dataset scope and group scope are respected.
  - Confirm PNG/SVG/PDF plot export works for single and comparison plots.

## P2 - Cleanup And Documentation

- [ ] Update `CHANGELOG.md` and the in-app "What's New" section after the UI/report/export stabilization pass.
- [ ] Make sure full changelog opens in the same help/dialog style as Guides/Help.
- [ ] Remove or archive dead legacy code only after related behavior has regression coverage.
- [ ] Review files marked legacy or containing unused older implementations.
- [ ] Keep design concepts aligned with implemented UI changes.
- [ ] Add a short "known assumptions" section to docs if any behavior intentionally differs from HydrogeoSieveXL2.

## Manual QA Checklist

- [ ] Load 10 NBAL Excel datasets as processed sieve data.
- [ ] Assign them into at least three groups.
- [ ] Toggle included/excluded datasets from the sidebar and Dataset & Group Manager.
- [ ] Confirm Comparison > Plot reflects included scope and group visibility.
- [ ] Confirm Comparison > Details individual mode.
- [ ] Confirm Comparison > Details aggregate mode.
- [ ] Confirm Comparison > Statistics K spread and coverage modes.
- [ ] Generate reports for:
  - One individual sample.
  - Cross-sample comparison.
  - K-value focus.
  - Full technical appendix.
- [ ] Export tables and plots for selected datasets and aggregate scope.
- [ ] Restart the program and confirm session restore/recent files behave correctly.
- [ ] Test on a smaller laptop-size window and a normal desktop-size window.

## EXE Release-Candidate Checklist

- [ ] Build a fresh `.exe` from a clean working tree or tagged release-candidate commit.
- [ ] Run the `.exe` from a local non-OneDrive folder.
- [ ] Run the `.exe` from a OneDrive path.
- [ ] Test paths containing spaces and Danish/non-ASCII characters.
- [ ] Confirm bundled Qt/PyQt files load without `Qt6Core.dll` crash.
- [ ] Confirm reports and exports can write to user-selected folders.
- [ ] Confirm no test/demo-only files are required outside the packaged application.
- [ ] Record the build date, commit hash, and test dataset set used for the release candidate.

## Next Immediate Task

Details and Statistics sidebars have passed manual QA. Next, continue the remaining P0/P1 release checks, especially plots, reports, export, porosity behavior, and end-to-end data-loading verification.
