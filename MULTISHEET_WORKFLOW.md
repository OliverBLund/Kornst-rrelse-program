# Multi-Sheet Excel Workbook Workflow

## Overview
The application now treats multi-sheet Excel workbooks as **bundles of separate files**. When you drop a multi-sheet workbook into the app, you select which sheets to import, and each selected sheet is treated as an individual sample.

## 🚀 Smart Batch Detection
**NEW:** When you add multiple Excel files at once, the system intelligently groups them:
- Files with **identical sheet structures** are grouped together
- You see **ONE dialog per group** instead of one per file
- Select sheets once, apply to all files in the group automatically

**Example:** Add 100 Excel files that all have "English" and "Dansk" sheets:
- ✅ You see **ONE dialog** asking which sheets to import
- ✅ Select "English" → All 100 files get English sheet imported
- ❌ NO need to click through 100 individual dialogs!

## User Workflow

### 1. **Adding Multi-Sheet Workbooks**

#### Single File
When you add one Excel workbook with multiple sheets:
1. A **Sheet Selection Dialog** appears automatically
2. Check the sheets you want to import (all are checked by default)
3. Click OK

#### Multiple Files (Batch Mode - SMART!)
When you add multiple Excel workbooks:
1. The system analyzes all files and groups by sheet structure
2. For each group with identical sheet structures:
   - **One dialog** shows: "Select Sheets for X Similar Workbooks"
   - Lists the common sheet names
   - Your selection applies to **ALL files** in that group
3. Single-sheet files are added automatically (no dialog)

### 2. **Processing Individual Sheets**
Each selected sheet is treated as a separate file:
- Shown in the Sample Management table as: `filename.xlsx [Sheet1]`, `filename.xlsx [Sheet2]`, etc.
- Each sheet gets its own error tab if manual mapping is needed
- Each sheet becomes a separate dataset tab after successful loading

### 3. **Mapping Columns (Manual)**
When a sheet needs manual column mapping:
1. Click "Review Files Needing Attention" or click the error tab
2. The Column Mapper opens showing **only that specific sheet**
3. Map the columns once (Size and Percent Passing)
4. The sheet is loaded as a separate dataset

### 4. **Batch Processing**
Use the batch features to map multiple sheets efficiently:
1. Fix the first sheet manually using the Column Mapper
2. In the Column Mapper, switch to "Cell Range Selection" mode
3. Use "Smart Selection" to select headers and data
4. Click "Apply Pattern to Batch" to automatically apply the mapping to other error tabs
5. All sheets from the same workbook (or similar workbooks) are mapped at once

## Technical Details

### File Key Format
Internally, sheet-specific entries use the format:
```
file_path:::sheet_name
```
Example: `C:\Data\samples.xlsx:::English`

### Sample Names
Each sheet gets its own sample name:
- Base name: `samples` (from `samples.xlsx`)
- Sheet-specific: `samples [English]`, `samples [Dansk]`

### Control Panel
- Detects multi-sheet workbooks automatically
- Shows sheet selector before processing
- Tracks each sheet separately in the file status table
- Supports all batch operations per-sheet

### Column Mapper
- When called with a `sheet_name` parameter, it works in **single-sheet mode**
- Multi-sheet UI is hidden automatically
- Loads and maps only the specified sheet
- Pattern learning works across sheets

### Error Tab
- Handles sheet-specific file keys
- Shows sheet name in tab title: `❌ samples.xlsx [Sheet1]`
- Passes sheet name to Column Mapper when fixing
- Preview shows data from the specific sheet

## Benefits

1. **Simple Mental Model**: Each sheet = one file
2. **No Repeated Mapping**: Map columns once, apply to all sheets
3. **Batch Efficiency**: Use pattern matching to process multiple sheets quickly
4. **Clear Organization**: Each sheet gets its own tab with a descriptive name
5. **Error Handling**: Failed sheets don't block successful ones

## Example Scenarios

### Scenario A: Single Workbook with 5 Sheets
1. Drop `lab_results.xlsx` (5 sheets) into the app
2. Sheet selector shows: `Sheet1`, `Sheet2`, `Sheet3`, `English`, `Dansk`
3. Select `English` and `Dansk`, click OK
4. Two entries appear in Sample Management:
   - `lab_results.xlsx [English]` - ⚠️ Needs Review
   - `lab_results.xlsx [Dansk]` - ⚠️ Needs Review
5. Click first error tab, map columns for English sheet
6. Switch to Cell Range Selection, use Smart Selection
7. Click "Apply Pattern to Batch"
8. Dansk sheet is automatically mapped using the same pattern
9. Both sheets are now loaded as separate datasets:
   - Tab: `📁 lab_results [English]`
   - Tab: `📁 lab_results [Dansk]`

### Scenario B: 100 Similar Workbooks (SMART BATCH!)
1. Select 100 Excel files, all with sheets: `English`, `Dansk`, `Summary`
2. **ONE dialog appears**: "Select Sheets for 100 Similar Workbooks"
3. Dialog shows: "Sheets: English, Dansk, Summary"
4. Check `English` only, click OK
5. **200 entries appear** in Sample Management:
   - `file001.xlsx [English]` through `file100.xlsx [English]`
6. Click "Review Files Needing Attention"
7. Map the first sheet manually
8. Use "Apply Pattern to Batch" to map all remaining 99 sheets automatically!
9. Result: 100 datasets loaded with minimal clicking

### Scenario C: Mixed File Structures
1. Add 50 files with `[English, Dansk]` + 30 files with `[Data, Results]` + 20 single-sheet files
2. **Two dialogs appear**:
   - Dialog 1: "Select Sheets for 50 Similar Workbooks" → English, Dansk
   - Dialog 2: "Select Sheets for 30 Similar Workbooks" → Data, Results
3. 20 single-sheet files are added automatically (no dialog)
4. Total: 100 sheets imported with only 2 dialog clicks!

## Notes

- Single-sheet Excel files work as before (no sheet selector shown)
- CSV files are unaffected by this workflow
- Sheet selection can be changed by re-adding the file (remove and add again)
- All sheets share the same base file path for batch operations
