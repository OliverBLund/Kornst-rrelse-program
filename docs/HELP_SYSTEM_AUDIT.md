# Help System Audit

## Audit Summary

The previous in-app help set had three main problems:

1. It described older workflows rather than the current UI.
   Key gaps were the welcome-screen flow, sidebar selection behavior, Excel sheet selection, the dedicated error tab, and the current top-level tab structure.

2. It mixed onboarding with long reference copy.
   New-user pages were overloaded with method and feature detail that made the first-use path harder to follow.

3. It relied on emoji-heavy copy and stale topic wiring.
   Several pages used emoji as structural markers, and the help tree referenced method pages that were not present in the app bundle.

## Updated Information Architecture

### Start Here
- Getting Started
- Data Format & Files
- Excel Workbooks
- Mapping & Recovery

### Use The App
- Workspace Tour
- Results, Comparison & Export
- Analysis Parameters
- Common Issues

### Reference
- Methods Overview
- Hazen
- Terzaghi
- Beyer
- Kozeny-Carman
- Shepherd
- About & References

## What Changed

- Replaced the help navigation model with a sectioned tree aligned to current user workflows.
- Added new onboarding pages for Excel workbooks, mapping/recovery, workspace orientation, and the main review/export flow.
- Reworked welcome-screen quick-help links to point at the new onboarding pages.
- Added route compatibility inside the help dialog so older internal page requests resolve to the new page set.
- Removed the old missing-method entries from the visible help tree.
- Refreshed the help HTML styling with cleaner callouts, subdued palette usage, and no emoji-based section markers.

## Consistency Review Against The Live UI

The updated help pages were checked against the current application code for the following points:

- Top toolbar tabs: Individual Samples, Comparison, Reports, Export.
- Welcome-screen behavior: sidebar hidden until datasets are loaded.
- Per-dataset subtabs: Plot, Results, Statistics.
- Comparison view: subset driven by sidebar selection, fallback to all datasets when none are selected.
- Export behavior: scope controlled in the Export tab, not by sidebar selection.
- Excel import: multi-sheet selection dialog before mapping.
- Mapper modes: Calculated Data vs Raw Sieve Weighings, Column Mapping vs Cell Range Selection.
- Range-mode limitation: one sheet at a time.
- Error recovery: dedicated error tab with mapper re-entry.

## Residual Notes

- Legacy HTML help files remain on disk but are no longer the primary in-app path for onboarding.
- Detailed reference pages still exist only for a subset of methods. The help tree now reflects only the pages that are actually bundled.
