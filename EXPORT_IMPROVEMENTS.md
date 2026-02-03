# Export Tab - Improvements Roadmap

**Last Updated:** 2025-11-27  
**Status:** Planning Phase  
**Goal:** Enhance export functionality with better content control, error handling, and user experience

---

## Overview

This document outlines planned improvements for the Export Tab in the Grain Size Analysis application. The improvements are organized by priority and grouped into implementable phases.

### Current State
- ✅ Clean codebase (507 lines of dead code removed)
- ✅ Card-based format selection UI
- ✅ Preview system for CSV/Excel/JSON/Plots
- ✅ File tree showing export output
- ⚠️ Limited content customization (only 4 broad categories)
- ⚠️ No error handling
- ⚠️ Limited format options
- ⚠️ Basic progress reporting

---

## Phase 1: Critical Functionality (High Priority)

### 1.1 Enhanced Content Selection System ⭐ **NEW REQUIREMENT**

**Problem:** Currently only 4 broad content toggles exist (grain_data, k_values, statistics, plots). Users need granular control over what data types to export.

**Current Content Toggles:**
```python
self.content_enabled = {
    'grain_data': True,      # Controls: grain_distribution, percentiles, gradation, classification
    'k_values': True,        # Controls: all K-value results
    'statistics': True,      # Controls: statistical summaries
    'plots': True           # Controls: plot generation
}
```

**Proposed Granular Content Selection:**

#### Data Categories:
1. **Grain Size Data**
   - [ ] Raw grain size distribution (particle sizes + % passing)
   - [ ] Percentile values (D5, D10, D16, D17, D20, D30, D50, D60, D84, D95)
   - [ ] Gradation parameters (Cu, Cc)
   - [ ] Soil classification (USCS/other)

2. **K-Value Results**
   - [ ] All calculation methods
   - [ ] Filter by method categories (Hazen-based, Kozeny-Carman, etc.)
   - [ ] Include/exclude specific methods (checkbox list)
   - [ ] Include formulas used
   - [ ] Include validation messages/warnings

3. **Statistical Summaries**
   - [ ] K-value statistics (mean, median, std dev, min, max)
   - [ ] Grain size statistics
   - [ ] Method comparison statistics
   - [ ] Confidence intervals

4. **Metadata**
   - [ ] Sample information (name, date)
   - [ ] Environmental parameters (temperature, porosity)
   - [ ] Processing notes/comments
   - [ ] Export timestamp
   - [ ] Software version

5. **Plots/Figures**
   - [ ] Grain size distribution curve
   - [ ] K-value comparison chart
   - [ ] Statistical box plots
   - [ ] Include plot legends
   - [ ] Include grid lines

**Implementation:**
- Add collapsible "Content Selection" panel in UI
- Organize as expandable tree structure or grouped checkboxes
- Save content preferences as presets
- Update `_build_export_config()` to handle granular options
- Modify `export_manager.py` to respect all content flags

**Files to modify:**
- `export_tab.py` - Add content selection UI (lines 289-325)
- `export_tab.py` - Update `_build_export_config()` (lines 1578-1605)
- `export_manager.py` - Update all export methods to check content flags

---

### 1.2 Error Handling & Validation

**Problem:** No error handling; crashes on invalid paths, permission errors, or disk full.

**Tasks:**
- [ ] Add try-except blocks around all file operations
- [ ] Validate output directory exists and is writable
- [ ] Check available disk space before export
- [ ] Warn if datasets have missing data
- [ ] Show meaningful error messages
- [ ] Sanitize filenames for invalid characters
- [ ] Handle Unicode in file paths (Danish characters: ø, å, æ)

**Implementation:**
```python
# In export_now() method
try:
    # Validate before export
    if not os.path.exists(output_dir):
        reply = QMessageBox.question(...)
        if reply == QMessageBox.Yes:
            os.makedirs(output_dir)
    
    if not os.access(output_dir, os.W_OK):
        QMessageBox.critical("Directory not writable")
        return
    
    # Check disk space
    stat = os.statvfs(output_dir)
    free_space = stat.f_bavail * stat.f_frsize
    if free_space < estimated_size:
        QMessageBox.warning("Insufficient disk space")
        return
        
    # Perform export
    manager.export(...)
    
except PermissionError as e:
    QMessageBox.critical("Permission denied")
except OSError as e:
    QMessageBox.critical(f"File system error: {e}")
except Exception as e:
    QMessageBox.critical(f"Export failed: {e}")
```

**Files to modify:**
- `export_tab.py` - Update `export_now()` (lines 1453-1550)
- `export_manager.py` - Add error handling to all `_export_*` methods

---

### 1.3 Export Format Options

**Problem:** No control over CSV format, encoding, or plot DPI.

**Tasks:**
- [ ] CSV delimiter selection (comma, semicolon, tab)
- [ ] Decimal separator (period vs comma for European standards)
- [ ] Character encoding (UTF-8, Latin-1, Windows-1252)
- [ ] PNG DPI control (currently hardcoded to 300)
- [ ] Excel sheet naming options
- [ ] JSON indentation level

**UI Design:**
Add "Format Options" collapsible section:
```
📄 CSV Options
   Delimiter: [Comma ▼] [Semicolon] [Tab]
   Decimal: [Period ▼] [Comma]
   Encoding: [UTF-8 ▼]

🖼️ Plot Options
   PNG DPI: [300] (72-600)
   Background: [White ▼] [Transparent]
   
📗 Excel Options
   Sheet naming: [Default ▼] [Short names]
```

**Files to modify:**
- `export_tab.py` - Add format options UI in `setup_ui()`
- `export_tab.py` - Update `_build_export_config()` to include format options
- `export_manager.py` - Update CSV/Excel/Plot export methods to use options

---

### 1.4 File Naming System Improvements

**Problem:** No conflict resolution, limited template variables, no preview.

**Tasks:**
- [ ] Conflict resolution (auto-append (1), (2), etc.)
- [ ] Filename preview before export
- [ ] Custom template editor with live preview
- [ ] Sequential numbering for batch exports
- [ ] Additional template variables:
  - `{temperature}` - Sample temperature
  - `{porosity}` - Porosity value
  - `{classification}` - Soil type
  - `{count}` - Sequential number
  - `{timestamp}` - Full timestamp

**UI Design:**
```
📁 Filename Template:
   Template: {sample_name}_{classification}_{date}
   Preview:  Sample_A_SW_20251127.csv
   
   Available: {sample_name}, {date}, {time}, {temperature}, {porosity}, 
              {classification}, {count}, {timestamp}
```

**Files to modify:**
- `export_tab.py` - Add template editor UI
- `export_tab.py` - Update `_format_filename()` method (lines 1013-1037)
- `export_manager.py` - Add conflict resolution logic

---

### 1.5 Progress Reporting Enhancement

**Problem:** Basic progress dialog; no detail, no cancel, no summary.

**Tasks:**
- [ ] Show current file being exported
- [ ] Display estimated time remaining
- [ ] Add Cancel button (stop mid-export)
- [ ] Show export summary after completion
- [ ] List any errors/warnings encountered

**Implementation:**
```python
# Enhanced progress dialog
progress = QProgressDialog(self)
progress.setWindowTitle("Exporting...")
progress.setLabelText("Preparing export...")
progress.setCancelButton(QPushButton("Cancel"))
progress.setRange(0, total_steps)

# During export
progress.setLabelText(f"Exporting {filename}...")
progress.setValue(current_step)

# Check for cancel
if progress.wasCanceled():
    break

# After completion
summary = ExportSummaryDialog(self)
summary.set_results(exported_files, errors, warnings)
summary.exec()
```

**Files to modify:**
- `export_tab.py` - Update progress dialog in `export_now()`
- Create new `ExportSummaryDialog` class
- `export_manager.py` - Support cancellation, return detailed results

---

## Phase 2: User Experience (Medium Priority)

### 2.1 Export Presets System

**Problem:** Users must manually select formats every time.

**Tasks:**
- [ ] Built-in presets:
  - "Quick Report" (CSV Long + PNG)
  - "Full Analysis" (Excel + CSV Wide + PNG)
  - "Presentation" (PDF + SVG)
  - "Statistical Package" (CSV Wide only)
  - "Publication Ready" (Excel + PDF + high-DPI PNG)
- [ ] Save custom presets
- [ ] Load/edit/delete custom presets
- [ ] Preset selector dropdown

**UI Design:**
```
📦 Presets: [Custom ▼]
   - Quick Report
   - Full Analysis
   - Presentation
   - Statistical Package
   - Publication Ready
   ---
   - [Save Current as Preset...]
   - [Manage Presets...]
```

**Implementation:**
- Save presets as JSON in user config directory
- Include format selections, content selections, format options
- Add preset manager dialog

**Files to modify:**
- `export_tab.py` - Add preset UI and logic
- Create `export_presets.py` module for preset management

---

### 2.2 Preview Enhancements

**Tasks:**
- [ ] Copy to clipboard button for tables
- [ ] Export preview to file (test export)
- [ ] Show actual plot thumbnails
- [ ] Excel sheet structure preview
- [ ] Horizontal scroll indicator for wide previews
- [ ] Syntax highlighting for JSON preview
- [ ] Search/filter in preview tables

**Files to modify:**
- `export_tab.py` - Enhance all `_add_*_preview_tab()` methods
- Add matplotlib thumbnail generation for plots

---

### 2.3 File Tree Improvements

**Tasks:**
- [ ] Right-click context menu (Open folder, Copy path)
- [ ] Show full file paths
- [ ] Color-code by file type
- [ ] Accurate file size estimates
- [ ] Checkboxes to exclude individual files
- [ ] Expandable file details (shows columns, row count)

**Files to modify:**
- `export_tab.py` - Update `update_file_tree()` (lines 161-240)
- Add context menu handler

---

### 2.4 Quick Action Buttons

**Tasks:**
- [ ] "Select Common Formats" button
- [ ] "Select All Formats" button
- [ ] "Deselect All" button
- [ ] "Export to Temp Folder" (quick test)
- [ ] "Repeat Last Export" button

**Files to modify:**
- `export_tab.py` - Add quick action toolbar

---

### 2.5 Pre-Export Validation Dialog

**Tasks:**
- [ ] Show summary before exporting:
  - Total files to create
  - Total disk space required
  - List of all filenames
  - What will be overwritten
- [ ] Warnings for:
  - Missing data
  - Large file sizes
  - Overwrite warnings
- [ ] Option to review/edit selections
- [ ] "Don't show again" checkbox

**Implementation:**
Create `ExportConfirmationDialog` that shows before export

**Files to modify:**
- Create new `export_confirmation_dialog.py`
- `export_tab.py` - Show dialog before export

---

## Phase 3: Advanced Features (Low Priority)

### 3.1 Custom Column Selection (CSV)

**Tasks:**
- [ ] Select which columns to include/exclude
- [ ] Reorder columns via drag-and-drop
- [ ] Add calculated columns (e.g., K normalized to 20°C)
- [ ] Column naming customization

**Files to modify:**
- Create new column selector dialog
- `export_manager.py` - Support custom column configuration

---

### 3.2 Export Filtering

**Tasks:**
- [ ] Filter datasets by:
  - K-value range
  - Temperature range
  - Soil classification
  - Validity status
- [ ] Filter methods by category
- [ ] Preview filter results before export

**Files to modify:**
- Add filter UI panel
- `export_tab.py` - Apply filters in `_get_datasets_to_export()`

---

### 3.3 Compression Option

**Tasks:**
- [ ] ZIP all exports into single archive
- [ ] Auto-compress for >10 files
- [ ] Compression level selection
- [ ] Archive naming options

**Files to modify:**
- `export_manager.py` - Add ZIP creation logic
- Require `zipfile` module

---

### 3.4 Export Comparison Tool

**Tasks:**
- [ ] Save export metadata (what/when/where)
- [ ] Compare two exports side-by-side
- [ ] Track changes in K-values over time
- [ ] Diff viewer for CSV files

**Files to modify:**
- Create new comparison tool module
- Add export metadata logging

---

### 3.5 Export History Log

**Tasks:**
- [ ] Keep log of recent exports (last 20)
- [ ] Show: timestamp, datasets, formats, location
- [ ] Re-run previous export
- [ ] Open export location from history

**Files to modify:**
- Create export history manager
- Add history viewer dialog

---

### 3.6 Batch File Naming

**Tasks:**
- [ ] Advanced template variables: `{Cu}`, `{Cc}`, `{D50}`
- [ ] Conditional naming (e.g., different templates per file type)
- [ ] Substring/formatting operations (e.g., `{sample_name:upper}`)

**Files to modify:**
- `export_tab.py` - Enhance `_format_filename()`

---

### 3.7 Post-Export Actions

**Tasks:**
- [ ] Open output folder automatically (optional)
- [ ] Open first exported file (optional)
- [ ] Copy export summary to clipboard
- [ ] Show notification when complete

**Files to modify:**
- `export_tab.py` - Add post-export handler

---

## Implementation Phases

### 🔴 **Phase 1: Core Quality** (3-4 weeks)
**Priority:** CRITICAL - Foundation for all other improvements

**Week 1:**
- [x] Remove dead code (COMPLETED)
- [ ] 1.2: Error handling & validation
- [ ] 1.3: Export format options (CSV delimiter, encoding, DPI)

**Week 2:**
- [ ] 1.1: Enhanced content selection system ⭐
- [ ] 1.4: File naming improvements

**Week 3:**
- [ ] 1.5: Progress reporting enhancement
- [ ] Testing & bug fixes

**Week 4:**
- [ ] Documentation
- [ ] User testing
- [ ] Refinements

**Deliverables:**
- Robust export system with proper error handling
- Granular content selection
- Flexible format options
- Better file naming

---

### 🟡 **Phase 2: User Experience** (2-3 weeks)
**Priority:** HIGH - Quality of life improvements

**Week 5:**
- [ ] 2.1: Export presets system
- [ ] 2.4: Quick action buttons

**Week 6:**
- [ ] 2.2: Preview enhancements
- [ ] 2.3: File tree improvements

**Week 7:**
- [ ] 2.5: Pre-export validation dialog
- [ ] Testing & refinements

**Deliverables:**
- Export presets for common scenarios
- Enhanced previews and file tree
- Better validation and warnings

---

### 🟢 **Phase 3: Advanced Features** (3-4 weeks)
**Priority:** MEDIUM - Power user features

**Week 8-9:**
- [ ] 3.1: Custom column selection
- [ ] 3.2: Export filtering

**Week 10-11:**
- [ ] 3.3: Compression option
- [ ] 3.5: Export history log

**Week 12:**
- [ ] 3.4: Export comparison tool (if time permits)
- [ ] 3.6: Batch file naming (if time permits)
- [ ] 3.7: Post-export actions

**Deliverables:**
- Power user features
- Export management tools
- Comparison capabilities

---

## File Structure Changes

### New Files to Create:
```
Program/gui/
├── export_tab.py (existing - will be heavily modified)
├── export_manager.py (existing - will be modified)
├── export_presets.py (NEW - preset management)
├── export_summary_dialog.py (NEW - post-export summary)
├── export_confirmation_dialog.py (NEW - pre-export validation)
├── export_history.py (NEW - export history logging)
└── export_comparison.py (NEW - optional comparison tool)

Data/
└── export_presets/ (NEW directory)
    ├── default_presets.json
    └── user_presets.json
```

---

## Testing Checklist

### Phase 1 Testing:
- [ ] Export with invalid output directory
- [ ] Export with read-only directory
- [ ] Export with insufficient disk space
- [ ] Export with special characters in filenames
- [ ] Export with Unicode paths (ø, å, æ)
- [ ] Test all CSV delimiters and encodings
- [ ] Test all DPI values for PNG
- [ ] Test all content selection combinations
- [ ] Test file naming conflict resolution
- [ ] Test cancel during export
- [ ] Export with missing data (no K-values, no grain data)

### Phase 2 Testing:
- [ ] Create/save/load custom presets
- [ ] Test all quick action buttons
- [ ] Copy preview data to clipboard
- [ ] Right-click file tree context menu
- [ ] Pre-export validation warnings
- [ ] Test with 1 dataset, 10 datasets, 50 datasets

### Phase 3 Testing:
- [ ] Custom column selection
- [ ] Export filtering
- [ ] ZIP compression
- [ ] Export history
- [ ] Export comparison

---

## Success Metrics

### Phase 1:
- Zero crashes during normal export operations
- 100% of file operations properly handle errors
- Granular content selection working for all export formats
- Format options (delimiter, encoding, DPI) working correctly

### Phase 2:
- Presets reduce export setup time by 70%
- Preview enhancements increase user confidence
- Pre-export validation catches 90% of potential issues

### Phase 3:
- Power users can customize exports to exact needs
- Export history enables quick re-runs
- Filtering saves time for large datasets

---

## Notes & Considerations

### Performance:
- For large datasets (50+ samples), consider:
  - Background threading for exports
  - Lazy loading in previews
  - Progress reporting every N files
  - Memory-efficient CSV writing (streaming)

### Compatibility:
- Ensure Excel exports work in Excel 2010+
- Test CSV files in Excel (European locale)
- Verify Unicode handling across Windows/Mac/Linux

### User Feedback Priority:
After Phase 1 completion, gather user feedback on:
1. Most-used export formats
2. Most-needed content types
3. Preset usage patterns
4. Pain points in workflow

This feedback will guide Phase 2 and 3 prioritization.

---

## Questions for User

Before implementation:
1. **Content Selection Priority:** Which data types are MOST important for granular control?
   - Percentile selection (which D-values to include)?
   - Method filtering (which K-methods to include)?
   - Statistical options (which stats to calculate)?

2. **Format Options:** Which are most important?
   - CSV delimiter (comma vs semicolon)?
   - Encoding (UTF-8 vs Windows-1252)?
   - Plot DPI control?

3. **Presets:** What are your most common export scenarios?
   - Quick report to supervisor?
   - Full dataset for publication?
   - Statistical analysis in R/Python?

4. **Phase Priority:** Should we follow the proposed 3-phase approach, or adjust?

---

**Document Version:** 1.0  
**Next Review:** After Phase 1 completion
