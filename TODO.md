# TODO - Grain Size Analysis Application

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

- [ ] **Fix smart cell selection + batch operation for multi-sheet**
  - [ ] Issue: Batch "Apply Pattern to Batch" broken when multiple sheets from ONE workbook
  - [ ] Root cause: Pattern application needs to understand sheet context
  - [ ] Test: Load one workbook with 3 sheets, map first, batch apply to others
  - [ ] Expected: All 3 sheets from same workbook should be mappable via batch

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
   - Status: Identified, needs fix

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
