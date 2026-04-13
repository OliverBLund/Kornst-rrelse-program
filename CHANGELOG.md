# Changelog

All notable changes to the Grain Size Analysis application will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Smart Multi-Sheet Excel Workbook Support**: Revolutionary batch handling for multi-sheet workbooks
  - Automatically groups Excel files by sheet structure
  - Shows ONE dialog for all files with identical sheet names (e.g., 100 files → 1 dialog!)
  - Each sheet treated as separate sample with clear naming: `filename [SheetName]`
  - Sheet selection dialog with Select All/Clear All buttons
  - Full integration with error tabs and batch processing
  - Pattern matching works across sheets from different workbooks
  - Detailed documentation in MULTISHEET_WORKFLOW.md

### Changed
- Control Panel now pre-processes Excel files before showing error tabs
- Column Mapper supports single-sheet mode when called with specific sheet
- Error tabs display sheet names in title for multi-sheet files
- Sample Management table shows sheet-specific entries

### Fixed
- Batch "Apply Pattern to Batch" now works for sheet-qualified Excel error tabs (`path:::sheet`)
- Batch remap now updates Control Panel state through `_apply_mapping_results()` instead of bypassing file status tracking
- Added regression coverage for sheet-specific pattern application and batch remap routing

### Technical
- New file: `gui/sheet_selector.py` - Sheet selection dialog
- Enhanced: `control_panel.handle_batch_multisheet_excel()` - Smart grouping algorithm
- Enhanced: Error tab parsing for sheet-specific file keys (`path:::sheet`)
- File tracking now supports sheet-specific keys

---

## [0.9.0-beta] - 2024-01-XX

### Added
- Initial beta release
- 14+ K-calculation methods
- Interactive plots with controls
- Dataset comparison tools
- Statistical analysis
- Comprehensive help system
- Batch file processing
- Column mapping dialog for unknown formats
- Cell range selection mode for complex Excel files
- Pattern learning and batch application

### Known Issues
- _(To be documented)_

---

## Version Numbering
- **Major.Minor.Patch** format
- Major: Breaking changes
- Minor: New features, backward compatible
- Patch: Bug fixes only

## Categories
- **Added**: New features
- **Changed**: Changes in existing functionality  
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security vulnerability fixes
- **Technical**: Behind-the-scenes improvements
