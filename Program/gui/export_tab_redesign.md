# Export Tab Redesign Notes

## New Structure

The export tab is being redesigned with a clearer 3-column layout:

### Left Column: Format Selection (Card-Based)
- Visual cards for each format option
- CSV Long, CSV Wide, Excel, JSON, PNG, SVG, PDF
- Each card shows icon, name, description, file count badge
- Click to toggle selection

### Middle Column: Export Summary & File Tree
- Visual summary card at top showing total files, formats, size
- File tree widget showing exact files to be created
- Grouped by format (CSV/, Excel/, Plots/)
- Each file shows icon, name, size, description

### Right Column: Smart Preview
- Tab 1: Data Availability Grid (datasets × methods)
- Tab 2: Format Examples (side-by-side CSV long/wide preview)
- Tab 3: Export Checklist (validation check)

### Bottom: Simplified Actions
- Content toggle buttons (Grain Data, K-Values, Stats, Plots) with badges
- Output directory selector
- Large Export button

## Implementation Notes
- Keep all existing backend methods (_build_export_config, export_now, etc.)
- Only replace the UI creation (setup_ui method)
- Use self.selected_formats dict instead of checkboxes
- Use self.content_enabled dict for content selection
