# TODO - Grain Size Analysis Application

## Original Notes Index

This section keeps the original numbered notes easy to locate while the rest of the file stays organized by priority and subsystem.

1. Sidebar long filenames and `.xlsx:::` naming
   Status: fixed
   Notes:
   - `1.1)` Long file names were pushing sidebar controls out for other datasets
   - `1.2)` Sheet-qualified Excel restore showed `:::sheet` in the UI
   Current state:
   - Sidebar wrapping/layout fixed
   - Session restore display fixed
   - Keep watching for any remaining filename edge cases

2. Welcome screen too large / requires scrolling
   Status: fixed

3. Welcome screen flashes after loading dialog finishes
   Status: fixed

4. Loading dialog says `0 of N files` and later changes to datasets
   Status: fixed

5. Dataset-tab results table improvements
   Status: fixed
   Notes:
   - continuous highlight selection
   - columns should expand to use available space better

6. No smooth transition when switching between dataset tabs
   Status: fixed

7. Report generation sidebar/layout should match the new concept fully
   Status: pending

8. Column mapping dialog needs a stronger redesign
   Status: partly fixed
   Notes:
   - `8.1)` Batch apply with Excel still needs manual audit even after the multi-sheet fix
   - `8.2)` Error tab redesign completed

9. Sidebar porosity method is unclear
   Status: fixed

10. Manage dataset porosity dialog looks bad
    Status: fixed

11. Dataset statistics subtab needs redesign
    Status: pending

12. Zooming comparison plots causes problems
    Status: fixed

13. `QFont::setPointSize: Point size <= 0 (-1)`
    Status: fixed

14. Comparison plot toolbar active-state behavior is odd
    Status: pending

15. Individual-plot sidebar-open controls are inconsistent / overlapping
    Status: fixed

16. Removing a dataset from the sidebar does not remove its dataset tab
    Status: fixed

17. Export tab still needs a proper audit
    Status: pending

18. Small dialog appears briefly between splash and main window
    Status: pending investigation

19. Welcome screen content issues
    Status: fixed

20. Help/documentation audit and rewrite
    Status: pending

21. "More plots" dropdown in individual plot subtab looks transparent/weird
    Status: fixed

22. Comparison tab "Details" area needs better focus/space management
    Status: fixed

23. Comparison statistics subtab needs a proper finish [FIXED]
    Status: pending

24. Comparison plots should use the broader plot-style system
    Status: pending audit

## 🔴 High Priority - Must Fix Before Release

### Multi-Sheet Excel Workflow
- [ ] **Test single Excel file with multiple sheets**
  - [ ] Verify sheet selection dialog appears
  - [ ] Verify each sheet creates separate error tab
  - [ ] Verify sheet names appear correctly in tabs
  - [ ] Test mapping one sheet manually
  - [ ] Test that mapped sheet loads as dataset

- [ ] **Test batch Excel files (100+ similar files)**
  - [ ] Verify smart grouping by sheet structure
  - [ ] Verify ONE dialog for files with identical sheets
  - [ ] Verify all sheets get added to Sample Management
  - [ ] Verify sheet-specific file keys work correctly

- [x] **Fix smart cell selection + batch operation for multi-sheet**
  - [x] Issue: Batch "Apply Pattern to Batch" broken when multiple sheets from ONE workbook
  - [x] Root cause: Pattern application now preserves sheet-qualified file keys (`path:::sheet`) during pattern application
  - [x] Regression tests added for sheet-qualified batch remap and sheet-specific pattern application
  - [ ] Manual verification: Load one workbook with 3 sheets, map first, batch apply to others
  - [ ] Manual verification: Confirm all 3 sheets from same workbook can be mapped via batch

### UI Update Issues
- [ ] **Dataset removal doesn't update all UI elements**
  - [ ] When closing a dataset tab, verify:
    - [ ] Sample Management table updates
    - [ ] Control Panel file status updates
    - [ ] Comparison tab updates
    - [ ] Export tab updates
    - [ ] Reporting tab updates
  - [ ] When removing from Sample Management table, verify:
    - [ ] Dataset tab closes
    - [ ] Error tab closes (if exists)
    - [ ] All other UI elements update

- [ ] **Control Panel synchronization**
  - [ ] Verify file status always matches actual state
  - [ ] Test: Load file → Close tab → Status should update
  - [ ] Test: Remove from table → All references cleaned up

- [ ] **Welcome screen sizing and post-load behavior**
  - [ ] Investigate why welcome screen may require scrolling to reach bottom content
  - [ ] Fix welcome-screen flash after loading dialog completes
  - [ ] Review welcome-screen content cleanup (`Batch workspace`, DTU logo, layout density)

- [ ] **Loading dialog flow and terminology cleanup**
  - [ ] Keep progress language consistent (`files` vs `datasets`)
  - [ ] Investigate whether the progress flow reflects unnecessary duplicated stages
  - [ ] Investigate the small transient dialog between splash and main window

- [ ] **Sidebar filename and file-key display robustness**
  - [x] Prevent long names from pushing sidebar controls out of place
  - [x] Format restored sheet-qualified keys as `filename [sheet]` instead of `:::sheet`
  - [ ] Verify no other raw internal file keys leak into the UI

- [ ] **Dataset-tab table and tab-switch polish**
  - [ ] Improve results-table selection highlight behavior
  - [ ] Expand results-table columns to use available width better
  - [ ] Add smooth transition when switching dataset tabs

- [ ] **Column mapper and error tab redesign**
  - [ ] Reduce text density and improve information hierarchy
  - [ ] Audit batch-apply behavior for Excel manually
  - [ ] Redesign the Error tab to match the modern UI language

- [ ] **Porosity UX cleanup**
  - [ ] Clarify what the sidebar porosity method actually does
  - [ ] Redesign the "Manage dataset porosity" dialog

- [ ] **Statistics and comparison UX audit**
  - [ ] Rework dataset statistics subtab
  - [ ] Fix comparison-plot zoom issues
  - [ ] Improve comparison toolbar active states
  - [ ] Improve comparison "Details" layout when many datasets are loaded
  - [ ] Finish comparison statistics subtab
  - [ ] Align comparison plot styling more closely with single-dataset plots

- [ ] **Plot sidebar controls and dropdown polish**
  - [ ] Fix individual-plot sidebar open-button placement / logic
  - [ ] Prevent centered arrow from overlapping the y-axis label
  - [ ] Fix the transparent/weird "More plots" dropdown

- [ ] **Export tab audit**
  - [ ] Remove emojis
  - [ ] Reduce nested "box within boxes" styling
  - [ ] Audit the full export workflow properly

---

## 🟡 Medium Priority - Important Improvements

### Error Handling
- [ ] **Better error messages for multi-sheet operations**
  - [ ] When user cancels sheet selection
  - [ ] When no sheets selected
  - [ ] When sheet mapping fails

### Performance
- [ ] **Optimize for 100+ file loads**
  - [ ] Test memory usage with 100 sheets
  - [ ] Test UI responsiveness during batch processing
  - [ ] Add progress indicators where missing

### User Experience
- [ ] **Add confirmation dialogs for destructive actions**
  - [ ] Confirm before removing multiple files
  - [ ] Confirm before clearing all files
  - [ ] Warn if closing unsaved work

---

## 🟢 Low Priority - Nice to Have

### Multi-Sheet Enhancements
- [ ] Remember last sheet selection per file structure
- [ ] Show data preview in sheet selection dialog
- [ ] Allow renaming sheets after import
- [ ] Undo sheet addition

### Documentation
- [ ] Add screenshots to MULTISHEET_WORKFLOW.md
- [ ] Create video tutorial for batch operations
- [ ] Update help dialog with multi-sheet instructions
- [ ] Big documentation/help audit and rewrite
- [ ] Replace outdated emoji-heavy help UI with Font Awesome / current design language
- [ ] Improve getting-started guidance for data loading and options

### Testing
- [ ] Create automated test suite
- [ ] Test with various Excel formats (.xls, .xlsx)
- [ ] Test with corrupted Excel files
- [ ] Test with very large workbooks (>10MB)

---

## 🐛 Known Issues to Track

### Critical
1. **Smart cell selection batch operation broken for multi-sheet workbooks**
   - Description: When selecting multiple sheets from ONE workbook, "Apply Pattern to Batch" doesn't work correctly
   - Impact: Users must manually map each sheet from same workbook
   - Status: Fixed in code; pending manual UI verification

### High
2. **UI elements not updating on dataset removal**
   - Description: Closing dataset tab or removing from table doesn't update all UI
   - Impact: Stale data shown in Control Panel, Comparison, Export tabs
   - Status: Needs investigation

### Medium
3. **Progress indicators missing for large batches**
   - Description: When loading 100+ files, no clear progress indication
   - Impact: Users unsure if app is working or frozen
   - Status: Enhancement needed

---

## 📋 Testing Checklist

### Before Next Release
- [ ] Single file, single sheet → Works perfectly
- [ ] Single file, multiple sheets → Sheet selector works, all sheets load
- [ ] Multiple files (100), same sheets → One dialog, batch loads correctly
- [ ] Multiple files, different sheets → Multiple dialogs (one per structure)
- [ ] Mixed CSV + Excel files → Excel sheets detected, CSV files unaffected
- [ ] Cell range selection → Smart selection works
- [ ] Batch pattern application → Works across all error tabs
- [ ] Dataset removal → All UI elements update correctly
- [ ] File status tracking → Always accurate
- [ ] Error tabs → Display correct sheet names
- [ ] Column mapper → Single-sheet mode works when sheet specified

### Regression Testing
- [ ] CSV files still load correctly
- [ ] Single-sheet Excel files work as before
- [ ] Existing batch operations (non-multi-sheet) still work
- [ ] Error tab fix workflow unchanged for CSV files
- [ ] All K-calculation methods still work
- [ ] Comparison tab works with mixed sources
- [ ] Export functionality works for all dataset types

---

## 💡 Ideas for Future Versions

### Version 1.0
- [ ] Sensitivity analysis tool
- [ ] Advanced filtering options
- [ ] Custom method editor
- [ ] Batch export presets

### Version 1.1
- [ ] Machine learning for column detection
- [ ] Cloud storage integration
- [ ] Collaborative features
- [ ] Mobile companion app

---

## 📝 Notes

### Development Workflow
1. Pick issue from High Priority
2. Create feature branch if needed
3. Implement fix
4. Update CHANGELOG.md
5. Test thoroughly
6. Update TODO.md (check off item)
7. Commit with clear message

### Testing Protocol
- Always test with both small (1-5 files) and large (100+ files) batches
- Test with real user data, not just test files
- Verify on Windows (primary platform)
- Check memory usage during operations

### Documentation Updates
When fixing issues:
- Update CHANGELOG.md with fix details
- Update MULTISHEET_WORKFLOW.md if workflow changes
- Update help dialog if user-facing changes
- Add comments to complex code sections

---

## ✅ Completed (Archive)

_Completed items will be moved here to keep the active list clean_

### Version 0.9.x
- [x] Implement smart batch detection for multi-sheet workbooks
- [x] Create sheet selector dialog
- [x] Update error tab for sheet-specific keys
- [x] Modify column mapper for single-sheet mode
- [x] Create CHANGELOG.md
- [x] Create TODO.md structure
