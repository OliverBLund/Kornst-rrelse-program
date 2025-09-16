# Data Loading System Improvements

## Overview
Develop a robust, user-friendly data loading system that handles diverse file formats and structures with minimal manual intervention, while providing easy correction mechanisms for failed cases.

---

## 🎯 Core Design Principles

1. **Auto-First Approach**: Automatically handle 90%+ of common file formats
2. **Graceful Failure**: Present failed files for manual review rather than blocking entire batch
3. **Post-Load Editing**: Allow users to correct any file after loading
4. **Simple Templates**: Save successful mappings for reuse (no complex learning)
5. **Visual Feedback**: Clear status indicators for each file's loading state

---

## 🔧 Priority 1: Enhanced Batch Loading System

### Current State
- Users must load files one by one
- Each file triggers individual column mapping dialog
- No batch processing or status overview

### Target Implementation

#### A. Batch Loading Interface
```
📁 Batch File Import
┌─────────────────────────────────────────────────────┐
│ [Add Files] [Add Folder] [Clear All]               │
├─────────────────────────────────────────────────────┤
│ File Name              Status      Actions          │
│ ├ sample_001.csv       ✅ Auto     [View] [Edit]   │
│ ├ sample_002.csv       ⚠️ Review    [Map] [Skip]    │
│ ├ data.xlsx           ❌ Failed     [Fix] [Remove]   │
│ └ test_data.csv       ✅ Auto      [View] [Edit]    │
├─────────────────────────────────────────────────────┤
│ Summary: 3/4 loaded successfully                    │
│ [Load Successful] [Review Failed] [Load All]       │
└─────────────────────────────────────────────────────┘
```

#### B. Status Categories
- **✅ Auto**: Successfully auto-mapped and loaded
- **⚠️ Review**: Needs manual column mapping (ambiguous structure)
- **❌ Failed**: Critical error (corrupted, wrong format, etc.)
- **🔄 Loading**: Currently processing
- **⏸️ Skipped**: User chose to skip

#### C. Batch Actions
- **Load Successful**: Import all auto-mapped files immediately
- **Review Failed**: Open mapping dialogs for problematic files
- **Load All**: Process entire batch (auto + manual review)

---

## 🔧 Priority 2: Smart Delimiter Detection

### Current Issues
- Hardcoded comma delimiter assumption
- Fails on semicolon, tab, pipe delimited files
- No fallback mechanism

### Enhanced Detection Strategy

#### A. Multi-Pass Delimiter Detection
```python
def detect_delimiter(file_path: str) -> Tuple[str, float]:
    """
    Returns: (delimiter, confidence_score)
    Try delimiters in order of likelihood:
    1. ',' (comma) - most common
    2. ';' (semicolon) - European standard
    3. '\t' (tab) - TSV files
    4. '|' (pipe) - database exports
    """
    delimiters = [',', ';', '\t', '|']

    for delimiter in delimiters:
        confidence = analyze_delimiter_consistency(file_path, delimiter)
        if confidence > 0.8:
            return delimiter, confidence

    return ',', 0.5  # Default fallback
```

#### B. Validation Criteria
- **Column Count Consistency**: Same number of columns across rows
- **Numeric Data Detection**: Expected numeric columns contain numbers
- **Header Recognition**: First row looks like headers vs data
- **Balanced Quotes**: Proper quote escaping for embedded delimiters

#### C. User Override Options
- Show detected delimiter with confidence score
- Allow manual delimiter selection if auto-detection fails
- Remember user preferences for specific file patterns

---

## 🔧 Priority 3: Post-Load File Management

### Current Limitations
- No way to inspect/edit loaded files
- Cannot change delimiter or column mapping after load
- Limited visibility into what was actually loaded

### Target Features

#### A. Loaded Files Panel Enhancement
```
📊 Loaded Datasets (4)
┌─────────────────────────────────────────────────────┐
│ ├ 📄 sample_001.csv          [Edit] [Remove] [Info] │
│   └ 45 points, 0.1-10mm, D10=0.8mm                 │
│ ├ ⚠️ sample_002.csv          [Fix]  [Remove] [Info] │
│   └ Warning: Non-monotonic data                     │
│ ├ 📊 data.xlsx               [Edit] [Remove] [Info] │
│   └ 23 points, 0.5-5mm, D10=1.2mm                  │
│ └ 📄 test_data.csv           [Edit] [Remove] [Info] │
│   └ 67 points, 0.01-50mm, D10=0.3mm                │
└─────────────────────────────────────────────────────┘
```

#### B. File Actions
- **Edit**: Re-open column mapping dialog for the file
- **Fix**: Address specific warnings/errors
- **Info**: Show detailed file statistics and metadata
- **Remove**: Remove from analysis
- **Reload**: Re-process with different settings

#### C. Quick File Inspection
- Click file name → show data preview
- Visual indicators for data quality issues
- Summary statistics (point count, size range, D10/D50/D90)

---

## 🔧 Priority 4: Advanced Excel Support

### Current Excel Limitations
- Assumes first sheet contains data
- Cannot handle merged cells or complex formatting
- No cell range selection for irregular layouts

### Enhanced Excel Features

#### A. Visual Cell Selection Interface
```
📊 Excel File: complex_data.xlsx
┌─────────────────────────────────────────────────────┐
│ Sheet: [Data] [Metadata] [Results]                  │
├─────────────────────────────────────────────────────┤
│     A      B        C        D        E             │
│ 1 │Sample Info              │                       │
│ 2 │Name:   │Sample_01        │                       │
│ 3 │Temp:   │20°C             │                       │
│ 4 │                          │                       │
│ 5 │Size(mm)│Passing(%)│Retained│                     │
│ 6 │  10.0  │  100.0   │  0.0   │ ← Select data range│
│ 7 │   5.0  │   95.5   │  4.5   │                     │
│ 8 │   2.0  │   85.2   │ 14.8   │                     │
└─────────────────────────────────────────────────────┘

Selection Tools:
[Auto-detect Data] [Select Range] [Mark Headers]
```

#### B. Excel-Specific Features
- **Sheet Selection**: Choose which sheet contains data
- **Range Selection**: Click-drag to select data area
- **Header Detection**: Identify header row within selected range
- **Merged Cell Handling**: Smart extraction from merged headers
- **Metadata Extraction**: Find temperature/porosity in separate cells

#### C. Complex Layout Handling
- Data scattered across non-contiguous ranges
- Multiple datasets per sheet
- Embedded charts and formatting that shouldn't be parsed
- Comments and annotations to preserve

---

## 🔧 Priority 5: Intelligent Column Mapping

### Enhanced Auto-Detection

#### A. Expanded Keyword Dictionary
```python
COLUMN_MAPPING_KEYWORDS = {
    'particle_size': [
        'size', 'diameter', 'grain', 'particle', 'sieve', 'mesh', 'mm', 'd',
        'opening', 'aperture', 'φ', 'phi', 'grain_size', 'particle_diameter'
    ],
    'percent_passing': [
        'passing', 'pass', 'finer', 'cumulative', '%_passing', 'pct_passing',
        'percent_finer', 'cumulative_passing', '% finer', 'finer_than'
    ],
    'percent_retained': [
        'retained', 'retain', '%_retained', 'pct_retained', 'percent_retained',
        'cumulative_retained', 'coarser', 'larger_than'
    ],
    'sample_metadata': [
        'sample', 'specimen', 'test', 'id', 'name', 'label', 'description'
    ],
    'temperature': [
        'temp', 'temperature', '°c', 'celsius', 'deg_c', 't'
    ],
    'porosity': [
        'porosity', 'void_ratio', 'n', 'e', 'voids', 'phi', 'φ'
    ]
}
```

#### B. Context-Aware Detection
- Consider column position (size usually first, percentage second)
- Analyze data patterns (sizes decrease, passing increases)
- Unit detection (mm, μm, inches, mesh numbers)
- Value range validation (sizes > 0, percentages 0-100)

#### C. Confidence Scoring
```python
def calculate_mapping_confidence(column_data, column_type):
    """
    Return confidence score 0.0-1.0 for column mapping

    Factors:
    - Header keyword match (0.4 weight)
    - Data pattern match (0.3 weight)
    - Value range validity (0.2 weight)
    - Position context (0.1 weight)
    """
```

---

## 🔧 Priority 6: Mapping Templates & Memory

### Template System

#### A. Automatic Template Creation
- Save successful mappings as templates
- Include file name patterns, column headers, and delimiters
- Store user corrections and preferences

#### B. Template Matching
```python
def find_matching_template(file_path: str, headers: List[str]) -> Optional[Template]:
    """
    Match file to existing templates based on:
    1. File name similarity (pattern matching)
    2. Header text similarity (fuzzy matching)
    3. Column count and types
    4. Historical success rate
    """
```

#### C. User Template Management
- View saved templates
- Edit template mappings
- Delete outdated templates
- Export/import templates for sharing

---

## 🔧 Priority 7: Data Validation & Quality Control

### Multi-Level Validation

#### A. Individual File Validation
- **Range Checks**: Particle sizes (0.001-1000mm), percentages (0-100%)
- **Monotonic Validation**: Passing should increase with decreasing size
- **Data Completeness**: Minimum data points, no large gaps
- **Unit Consistency**: All sizes in same units

#### B. Cross-Dataset Validation
- **Size Range Overlap**: Warn if datasets have very different ranges
- **Unit Consistency**: Flag mixed mm/inches across files
- **Temperature/Porosity**: Highlight unusual values across batch
- **Duplicate Detection**: Identify potentially identical datasets

#### C. Quality Indicators
```
Dataset Quality Score: ⭐⭐⭐⭐⭐ (4.2/5.0)
✅ 45 data points (Good coverage)
✅ Monotonic data (No reversals)
⚠️  Temperature: 35°C (Higher than typical)
✅ Size range: 0.1-10mm (Standard range)
❌ Gap at 2-3mm range (May affect D30 calculation)
```

---

## 🛠️ Implementation Plan

### Phase 1: Foundation (Week 1-2)
1. **Enhanced Delimiter Detection**: Implement multi-pass detection algorithm
2. **Batch Loading UI**: Create the batch import interface
3. **Status Management**: Implement loading state tracking

### Phase 2: Core Features (Week 3-4)
1. **Post-Load Editing**: Add file management actions to loaded datasets panel
2. **Template System**: Basic template creation and matching
3. **Improved Column Detection**: Enhanced keyword matching and confidence scoring

### Phase 3: Advanced Features (Week 5-6)
1. **Excel Cell Selection**: Visual range selection interface
2. **Cross-Dataset Validation**: Quality control across multiple files
3. **User Experience Polish**: Error messages, progress indicators, help tooltips

### Phase 4: Optimization (Week 7-8)
1. **Performance**: Optimize for large file batches
2. **Memory Management**: Handle multiple large datasets efficiently
3. **User Testing**: Refine based on user feedback

---

## 🧪 Testing Strategy

### Test File Collection
Create comprehensive test suite with:
- **Common Formats**: Standard comma CSV, semicolon CSV, tab-delimited
- **Edge Cases**: Mixed delimiters, quoted fields, missing data
- **Excel Variants**: Multiple sheets, merged cells, embedded metadata
- **Problem Files**: Corrupted data, wrong formats, encoding issues
- **Real User Data**: Anonymized samples from actual geotechnical labs

### Validation Metrics
- **Auto-Success Rate**: % of files loaded correctly without user intervention
- **Time to Load**: Batch loading performance benchmarks
- **Error Recovery**: How well the system handles and recovers from failures
- **User Satisfaction**: Ease of use for both auto and manual cases

---

## 💡 Future Enhancements

### Advanced Features (Post-MVP)
1. **Additional File Formats**: Add support for proprietary lab formats (as needed)
2. **Data Preprocessing**: Manual outlier detection and smoothing tools
3. **Integration APIs**: Direct import from lab instruments (if requested)
4. **Template Sharing**: Export/import mapping templates for sharing

---

*This plan provides a roadmap for creating a robust, user-friendly data loading system that handles the complexity of real-world grain size data while maintaining simplicity for users.*