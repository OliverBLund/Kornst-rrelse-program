# GrainSize Analysis â€” Visual Design Specification
> Living document. Update as decisions are confirmed or revised.
> Last revised: 2026-03-12

---

## 1. Program Overview

This is a **hybrid PyQt6 desktop application**. The program is designed first as a native desktop tool, with selective embedded webviews used only where HTML/CSS materially improves presentation quality.

### 1.1 Preferred Rendering Split

**Native Qt by default**
- Application shell (sidebar, global toolbar, dataset tab bar, status bar)
- High-density data views (results tables, statistics cards, comparison tables)
- Dialogs and file-oriented workflows (load, mapping, selection, export configuration)
- Plot workspace controls and dataset navigation

**Selective webview candidates**
- Welcome / landing experience
- Help content
- Report preview / printable HTML output
- Optional future presentation-style views where HTML materially outperforms QSS for polish

**Ownership rule**
- Python/Qt is the source of truth for datasets, calculations, selections, and export/report state
- Web content renders supplied state and emits narrow UI events back to Python
- Business logic does not live in JavaScript

**Not a goal**
- Rebuilding the whole application as a browser UI inside `QWebEngineView`
- Duplicating business logic across Python and JavaScript

**Name:** Grain Size Analysis â€” Hydraulic Conductivity Calculator
**Platform:** Windows desktop (PyQt6). Packaged with PyInstaller.
**Audience:** Geotechnical / hydrogeological consultants (DTU context).
**Entry point:** `Program/main.py` â†’ `SimpleSplash` â†’ `MainWindow`
**Scale concern:** Must handle 20+ simultaneously loaded datasets gracefully in navigation and comparison views.

---

## 2. Color System

All tokens are anchored to the existing program palette. These are the canonical names used across all concept HTMLs.

### Content area
| Token | Hex | Usage |
|---|---|---|
| `--bg` | `#f5f5f0` | Main content background |
| `--bg-raised` | `#eee8dc` | Raised panels, tab bar backgrounds, summary bars |
| `--bg-low` | `#e8e0d0` | Pressed/active states, section backgrounds |
| `--border` | `#d4c4a8` | Default borders, dividers |
| `--border-dk` | `#c0ae90` | Stronger borders, table header underlines |
| `--text` | `#2f2f2f` | Primary text |
| `--text-mid` | `#5d4e37` | Secondary labels, table body text |
| `--text-muted` | `#9a8c78` | Placeholders, tertiary labels, column headers |

### Accent colors
| Token | Hex | Usage |
|---|---|---|
| `--olive` | `#6b8e23` | Primary action (Calculate K), active tab underline, active icons |
| `--olive-h` | `#7fa02d` | Olive hover state |
| `--olive-dk` | `#4f6a1a` | Olive border / pressed |
| `--forest` | `#2c5530` | Reserved (currently unused in redesign) |
| `--tan` | `#d2b48c` | Toolbar button hover background |
| `--tan-h` | `#ddbf94` | Tan hover |
| `--amber` | `#c4a574` | Scrollbar thumb, decorative accents |
| `--earth` | `#8b7355` | Status bar background, strong borders |

### Sidebar
| Token | Hex | Usage |
|---|---|---|
| `--sb` | `#ddd3be` | Sidebar base background |
| `--sb-up` | `#e5dcc8` | Section header bands (slightly lighter) |
| `--sb-dn` | `#d0c4ac` | Footer / DTU box background |
| `--sb-act` | `#c8ba9e` | Active sample card background |
| `--sb-bdr` | `#c0ae90` | Sidebar borders |
| `--sb-text` | `#3a2e1c` | Primary sidebar text |
| `--sb-mid` | `#6a5438` | Secondary sidebar text, button labels |
| `--sb-muted` | `#9a8468` | Muted sidebar labels, units |

### Logo card
| Token | Hex | Usage |
|---|---|---|
| `--logo-bg` | `#7a5e3e` | Logo card base (dark warm loam) |
| `--logo-bg-top` | `#8e6e4a` | Logo card gradient top |
| `--logo-text` | `#f4ece0` | Logo name + icon color |
| `--logo-sub` | `#c8a87a` | Logo subtitle ("ANALYSIS Â· v0.9-Î²") |

### Status bar
| Token | Hex | Usage |
|---|---|---|
| `--st-bg` | `#8b7355` | Status bar background (same as `--earth`) |
| `--st-text` | `#f0e8d8` | Primary status text |
| `--st-muted` | `#c4a882` | Secondary status labels / key names |
| `--st-dim` | `#a89070` | Tertiary status text, version number |

### Chrome bars
| Token | Hex | Usage |
|---|---|---|
| `--mb-bg` | `#ede8de` | Menu bar background |
| `--mb-bdr` | `#cfc0a4` | Menu bar border |
| `--tb-bg` | `#e4d8c0` | Global toolbar background |
| `--tb-bdr` | `#ccc0a0` | Toolbar border |
| `--pw-sb` | `#ece5d8` | Plot workspace inner sidebar |

### Status / badge colors
| Purpose | Hex | Notes |
|---|---|---|
| OK indicator LED | `#5aaa3a` / `#7dd050` | Sidebar / status bar variants |
| Warning indicator | `#d08020` | Sidebar card + dropdown |
| Error indicator | `#c03828` | Sidebar card |
| K-value blue | `#3a7ea0` | All K numeric values in tables |
| DTU red | `#C8002A` | DTU wordmark background only |

### Sample identity colors (Comparison tab)
Used to distinguish samples across comparison views. Assign in order, cycle if > 8 samples.

| Index | Hex | Usage |
|---|---|---|
| 0 | `#3a7ea0` | Blue |
| 1 | `#6b8e23` | Olive |
| 2 | `#b46428` | Amber-brown |
| 3 | `#8b4580` | Purple |
| 4 | `#2a7a5a` | Teal |
| 5 | `#a03a30` | Red-earth |
| 6 | `#4a6a9a` | Slate blue |
| 7 | `#7a6a28` | Dark gold |

> **Comparison scalability note:** The color palette above covers 8 samples. For 9â€“20+ datasets, the comparison view must shift to a **selection model** (choose which 4â€“6 samples to display at once) rather than showing all simultaneously. Design deferred â€” see Â§8.

---

## 3. Typography

### Font stack
| Role | Font | Fallback | Weight | Notes |
|---|---|---|---|---|
| Display / logo | Playfair Display | Georgia, serif | 600, 700 | Logo name only |
| UI / body | Source Sans 3 | system-ui, sans-serif | 300, 400, 500, 600 | Everything else |
| Monospace / data | JetBrains Mono | monospace | 400, 500 | K-values, D-values, formulas, status bar |

### Font sizes
| Context | Size | Weight | Color token |
|---|---|---|---|
| Logo name | 14px | 700 (Playfair) | `--logo-text` |
| Logo subtitle | 8.5px | 400 (Mono) | `--logo-sub` |
| Menu items | 12.5px | 400 | `--text-mid` |
| Toolbar tabs | 12.5px | 500 | varies |
| Section headers (sidebar) | 9.5px | 600, uppercase | `--sb-muted` |
| Sample card name | 12px | 500 | `--sb-text` |
| Sample card meta | 9px | 400 (Mono) | `--sb-muted` |
| Parameter labels | 11.5px | 400 | `--sb-mid` |
| Parameter inputs | 11px | 400 (Mono) | `--sb-text` |
| Dataset tabs | 11.5px | 400/500 | `--text-muted` / `--text` |
| Nested sub-tabs | 12px | 500 | varies |
| Table headers | 10â€“10.5px | 600, uppercase | `--text-mid` |
| Table body | 12px | 400 | `--text` |
| Table mono data | 11.5px | 400 (Mono) | `#3a7ea0` |
| Stat card values | 14â€“20px | 500 (Mono) | varies |
| Status bar keys | 9.5px | 400 (Mono) | `--st-dim` |
| Status bar values | 10.5px | 400 (Mono) | `--st-text` |
| Badge / pill text | 10â€“10.5px | 500 | varies |

### PyQt6 font bundling
- Bundle TTF/OTF files inside the app package under `resources/fonts/`
- Load at startup via `QFontDatabase.addApplicationFont(path)`
- Required files: `PlayfairDisplay-SemiBold.ttf`, `PlayfairDisplay-Bold.ttf`, `SourceSans3-*.ttf` (Regular, Medium, SemiBold, Light), `JetBrainsMono-Regular.ttf`, `JetBrainsMono-Medium.ttf`
- Set application default font: `app.setFont(QFont("Source Sans 3", 9))`

---

## 4. Layout Constants

| Variable | Value | PyQt6 equivalent |
|---|---|---|
| Sidebar width (`--sw`) | 258px | `setFixedWidth(258)` on sidebar QWidget |
| Menu bar height (`--mbh`) | 24px | `setFixedHeight(24)` or native QMenuBar |
| Toolbar height (`--tbh`) | 40px | `setFixedHeight(40)` on toolbar QWidget |
| Dataset tab bar height (`--dth`) | 30px | Custom tab widget header |
| Status bar height (`--sth`) | 24px | `setFixedHeight(24)` on QStatusBar |
| Plot inner toolbar height | 34px | `setFixedHeight(34)` |
| Plot inner sidebar width | 200px | `setFixedWidth(200)` (collapsible) |
| Nested sub-tab bar height | 32px | Custom sub-tab header |
| Border radius (`--r`) | 4px | `border-radius: 4px` in QSS |
| Sidebar card padding | 6px 8px | `setContentsMargins(8, 6, 8, 6)` |

---

## 5. Component Catalog

### 5.1 Application Shell
**Layout:** QMainWindow â†’ QWidget (central) â†’ QHBoxLayout: `[Sidebar | Main]`
Main has QVBoxLayout: `[MenuBar | Toolbar | ds-tab-bar | content-area]`
Status bar: QStatusBar (bottom).

### 5.2 Sidebar
**Structure:** QWidget (fixed 258px) â†’ QVBoxLayout with no margins:
- Logo card (fixed height ~54px)
- Scrollable body (QScrollArea, expanding)
- DTU box (fixed height ~36px)
- Footer button row (fixed height ~42px)

**Logo card:** Custom QWidget with gradient background painted in `paintEvent`. Contains `fa-layer-group` icon + "GrainSize" (Playfair Display) + subtitle (JetBrains Mono). Background: `#8e6e4a â†’ #7a5e3e` linear gradient.

**Section headers:** QFrame with background `--sb-up`, containing a QLabel (uppercase, `--sb-muted`) and optional QPushButton (small, transparent).

**Sample cards:** Custom QWidget per sample. Two states: collapsed (row only) / expanded (row + detail section). Contains:
- Row: icon QLabel + name/meta QVBoxLayout + status LED + expand chevron QPushButton
- Detail: status line QLabel + action buttons QHBoxLayout (Inspect / Log / Props / Remove)

Active card: background `--sb-act`, left accent bar (3Ã—16px painted rectangle, `--olive`).

**Sidebar sync rule:** Clicking a sidebar card activates the matching dataset tab (and vice versa). Single `currentDatasetId` state owned by MainWindow.

**Drop zone:** QFrame with dashed border, `--sb-bdr`. Hover: border `--olive`.

**DTU box:** QWidget, background `--sb-dn`. Contains "DTU" QLabel with background `#C8002A` (red pill) + program name/subtitle QLabels.

### 5.3 Menu Bar
Standard `QMenuBar`. Background `--mb-bg`. Item hover: `rgba(107,142,35,.1)`. Dropdown `QMenu`: background `--bg-raised`, border `--border`, border-radius 6px. Menu items 12.5px Source Sans 3.

**Menus:** File | Analysis | View | Help (right-aligned title label showing full program name)

### 5.4 Global Toolbar
QWidget (height 40px), background `--tb-bg`. QHBoxLayout.
Left: tab buttons for top-level views (Individual Samples | Comparison | Reports | Export).
Middle: separator + Add Files button + Calculate K button (olive primary).
Right: Help button.

**Tab styling:** active tab has 2px `--olive` bottom border, `--olive` text color. Inactive: `--text-muted`. Hover: `--text-mid`.

**Toolbar buttons:** QPushButton, transparent background, hover: `--tan` background + `--earth` border.
**Primary (Calculate K):** background `--olive`, border `--olive-dk`, white text.

### 5.5 Dataset Tab Bar
Custom widget (height 30px). **Not QTabWidget** â€” custom implementation required for:
- Scrollable overflow with `â—€ / â–¶` navigation buttons
- `â‹¯ +N` overflow dropdown listing all datasets
- Close (âœ•) button per tab

**Recommended implementation:** `QScrollArea` (horizontal only) containing a `QWidget` with `QHBoxLayout` of custom `DatasetTabButton` widgets. Nav arrows are `QPushButton` outside the scroll area. Overflow button opens a `QMenu`.

**Tab states:** inactive (`--text-muted`, transparent bg), hover (`--bg-low`, `--border`), active (`--bg`, `--border` all sides except bottom, `--text`).

**Welcome tab:** always leftmost, no close button, icon `fa-house`.

### 5.6 Nested Sub-Tab Bar (Plot / Results / Statistics)
QWidget (height 32px), background `--bg`. Contains 3 QPushButtons.
Active: 2px bottom border `--earth`, `--text` color.
Inactive: `--text-muted`. Hover: `--text-mid`.
Only visible when Individual Samples tab is active.

### 5.7 Plot Workspace (inner)
**Structure:** QVBoxLayout: `[inner-toolbar | body]`, body = QHBoxLayout: `[inner-sidebar | chart]`

**Inner toolbar** (height 34px, bg `--bg-raised`):
- Plot type segmented control (Dist. Curve / K-Values) â€” QButtonGroup of QPushButtons
- Style dropdown (QComboBox): Professional / Presentation / Minimalist / Classic
- Toggle buttons: Grid / Legend / Zones / D-lines
- Zoom buttons: +, âˆ’, Fit
- Export button
- Toggle-sidebar button (rightmost)

**Inner sidebar** (width 200px, collapsible, bg `--pw-sb`):
Collapse/expand via `QPropertyAnimation` on `maximumWidth` (0 â†” 200).
Contains: Axis Controls section (X/Y min/max inputs) + Display Options section (toggle switches) + Curve Color section (color pickers per loaded sample).

**Toggle switches:** Custom QWidget painting an on/off pill (background `--border` â†’ `--olive`, knob white circle). Animate knob position via `QPropertyAnimation`.

**Chart area:** `FigureCanvasQTAgg` (matplotlib). Style via matplotlib rcParams matching the color tokens â€” see Â§6.2.

### 5.8 Results Tab
**Structure:** QVBoxLayout: `[summary-bar | split-area]`
Split: QSplitter horizontal â†’ `[K-table | method-detail-panel]`

**Summary bar** (bg `--bg-raised`): Row of stat cells (KÌ„ m/d, KÌ„ m/s, methods valid, D50, temperature). Each cell: value (Mono, 15px) + key label (9.5px uppercase).

**K-values table:** QTableWidget. Columns: Method | Category | K cm/s | K m/s | K m/d | Status. Sticky header via `horizontalHeader().setStretchLastSection`. Selected row: olive left border + `rgba(107,142,35,.07)` background.

**Method detail panel** (width 240px): QScrollArea containing stacked QFrames for: header (name, K value big), Parameters Used, Formula, Applicability, Reference.

### 5.9 Statistics Tab
Scrollable QWidget with wrapping QFlowLayout (or QGridLayout). Cards:
- Grain Size Percentiles (QTableWidget, 340px wide)
- Gradation Parameters (2-column grid, 310px)
- Hydraulic Conductivity Statistics (3-column grid, 360px)
- Soil Classification (key-value pairs + badges, 300px)

**Stat card:** QFrame, border `--border`, border-radius 6px. Header: QFrame bg `--bg-low`, 10.5px bold uppercase label.

### 5.10 Comparison Tab
**Header bar:** sample identity chips + action buttons (Refresh / Export / Plot Comparison).
**Body:** QSplitter horizontal â†’ `[Grain Parameters panel | K-Values panel]`

Each panel: header label + QTableWidget. Columns: Parameter + one column per selected dataset.

**Scalability (20+ datasets):** Table columns will not scale past ~6 samples. Requires a dataset selection control (not yet designed â€” see Â§8). Deferred.

**Single encoding rule:** Sample identity shown by column header color only. No redundant chips in cell values.

### 5.11 Reports Tab
**Structure:** QSplitter horizontal â†’ `[config-panel (max 300px) | preview-panel]`

Config panel: QScrollArea with options â€” report type (Individual / Comparison / Full), dataset selection checkboxes, content toggles (grain data / K values / stats / plots), format options.

Preview panel: `QWebEngineView` preferred for HTML report preview; `QTextBrowser` is an acceptable fallback if packaging or printing constraints make it simpler. Toolbar above: Generate / Print / Save PDF.

### 5.12 Export Tab
**Format selection:** Card-based grid â€” each format (CSV Long, CSV Wide, Excel, JSON, PNG, SVG, PDF) as a toggleable QFrame card. Selected: olive border + tinted bg.

**Content section:** Checkboxes â€” grain data, K values, statistics, plots.

**Output section:** Path selector + filename pattern + Export button.

**Progress:** `QProgressDialog` shown during export.

### 5.13 Status Bar
QStatusBar, height 24px, background `--st-bg` (#8b7355). Contains custom QLabel widgets:
- Status pill: LED dot (QLabel with circular stylesheet) + "Ready" text
- Separator: 1px vertical QFrame
- Segments: SAMPLE / D50 / KÌ„ / TEMP / METHODS / DATASETS
- Spacer
- Version label (right-aligned)

LED dot animation: `QTimer` toggling opacity via stylesheet (replaces CSS animation).

### 5.14 Dialogs

#### Manage Porosity
QDialog. Per-sample porosity override table (QTableWidget: Sample | Porosity | Use Default checkbox). Default value input at top.

#### Data Inspector
QDialog opened from sidebar card "Inspect" action. Shows raw loaded data (QTableWidget, read-only) for the selected dataset. Useful for verifying sieve data loaded correctly.

#### Load Log
QDialog opened from sidebar card "Log" action. `QTextEdit` (read-only, monospace) showing parsing log for the selected dataset.

#### Column Mapper (`column_mapper.py`)
Existing dialog. Maps spreadsheet columns to expected fields (mm sieve / weight columns). Must be restyled to match design system.

#### Sheet Selector (`sheet_selector.py`)
Existing dialog. Select which sheet(s) to import from multi-sheet XLSX. Must be restyled.

#### Dataset Selection (`dataset_selection_dialog.py`)
Existing dialog. Used by comparison/reporting to choose which datasets to include. Must be restyled. Will be extended later for comparison scalability.

#### Help Dialog (`help_dialog.py`)
Existing. `QWebEngineView` preferred for HTML help content; `QTextBrowser` acceptable fallback. Sidebar with topic list + content pane. Style to match shell.

#### About Dialog
Simple QDialog. Logo, program name (Playfair Display), version, DTU branding, short description.

---

## 6. PyQt6 Implementation Strategy

### 6.1 Hybrid rendering architecture
The implementation target is **not** "HTML everywhere." It is a PyQt6 desktop application with selective webview usage.

**Principles**
- MainWindow, navigation, high-density controls, tables, and dialogs remain native Qt widgets.
- Webviews are embedded only for surfaces that benefit from HTML/CSS layout or print-style rendering.
- All durable state lives in Python models/controllers owned by the Qt application.
- Webviews receive structured data payloads from Python and send back only explicit UI events.
- Any webview surface must have a clearly defined host widget and bridge boundary.

**Preferred webview use**
- Welcome tab / onboarding surface
- Help dialog content
- Reports preview and printable/exportable HTML
- Optional future polished read-only or low-editability analytic presentation views

**Avoid webview use for**
- Sidebar sample management
- Dataset tab overflow/navigation
- Results tables with row selection
- Dense comparison tables
- Core modal dialogs and file-loading workflows

### 6.2 QSS approach
PyQt6 does not support CSS custom properties (variables). Use a **Python-level theming module** (`gui/theme.py`) that:
- Defines all color tokens as Python constants
- Generates QSS strings via f-strings or string templates
- Applies via `app.setStyleSheet(theme.build_stylesheet())`
- Allows single-point changes

```python
# theme.py (example structure)
BG = "#f5f5f0"
BG_RAISED = "#eee8dc"
OLIVE = "#6b8e23"
# ...
def build_stylesheet() -> str:
    return f"""
    QMainWindow {{ background: {BG}; }}
    QPushButton.primary {{ background: {OLIVE}; color: white; }}
    ...
    """
```

### 6.3 Matplotlib plot styling
Match plot chrome to app palette via rcParams:

```python
import matplotlib as mpl
mpl.rcParams.update({
    'axes.facecolor':    '#ffffff',
    'figure.facecolor':  '#f5f5f0',
    'axes.edgecolor':    '#c0ae90',
    'axes.labelcolor':   '#5d4e37',
    'xtick.color':       '#9a8c78',
    'ytick.color':       '#9a8c78',
    'grid.color':        '#d4c4a8',
    'grid.linewidth':    0.5,
    'font.family':       'Source Sans 3',
    'font.size':         11,
    'axes.titlesize':    12,
})
```

Curve colors for multi-sample plots: use the 8-color identity palette from Â§2.

### 6.4 Webview integration
When a webview surface is used, implement it as a thin hosted view:

- Host widget: dedicated PyQt widget or tab responsible for sizing, lifecycle, and loading local assets
- Asset location: bundled local files under `Program/resources/web/`
- Bridge: one explicit Python-to-JS / JS-to-Python bridge object for events and data updates
- Payload shape: JSON-serializable dictionaries and lists only
- Ownership rule: calculations, validation, dataset selection, and export logic stay in Python
- Fallback rule: if a webview surface becomes sluggish or hard to keep in sync, move that surface back to native Qt

**Recommended pattern**
- Python loads HTML from local packaged assets
- Python injects initial state after page load
- JS renders the view and emits named events such as `openDataset`, `selectReportType`, `printPreview`
- Python handles the event, updates state, and re-publishes fresh data if needed

### 6.5 Icons
Font Awesome is not directly usable in PyQt6 as a CSS class. Options (in order of preference):

1. **Bundle FA as a font file** (`FontAwesome6Free-Solid.otf`) + load via `QFontDatabase`. Then use unicode codepoints in `QLabel` / `QPushButton` text: e.g. `\uf0c5` for copy icon. Helper function: `fa_icon(codepoint, size) â†’ QLabel`.

2. **SVG icon files** bundled in `resources/icons/`. Load as `QIcon` from SVG. More flexible for coloring.

3. **Emoji fallback** â€” only for dev/testing.

### 6.6 Sidebar expand/collapse animation
Use `QPropertyAnimation` on `maximumWidth`:
```python
anim = QPropertyAnimation(plot_sidebar, b"maximumWidth")
anim.setDuration(200)
anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
anim.setStartValue(0 if open else 200)
anim.setEndValue(200 if open else 0)
anim.start()
```

### 6.7 Scrollable dataset tab bar
QTabWidget's built-in tab scrolling (`setMovable`, `setTabsClosable`) does not support the custom overflow-dropdown pattern. Implement as:
- `QScrollArea` (horizontal, no scrollbars visible) wrapping a `QWidget` with `QHBoxLayout`
- Each tab: custom `DatasetTabButton(QPushButton)` with close button overlaid
- Left/right arrows: `QPushButton` outside scroll area, connected to `horizontalScrollBar().setValue()`
- Overflow dropdown: `QToolButton` with `QMenu` (built from current tabs list)

### 6.8 Texture overlay
The SVG noise grain texture (`body::after`) is **not achievable in QSS**. Options:
- Skip it â€” the palette reads well without it on desktop
- Apply as a low-opacity `QLabel` overlay with a tiled `QPixmap` (performance overhead, not recommended)
- **Recommended:** Skip. The earthy palette carries the aesthetic without it.

### 6.9 CSS transitions
Not supported in QSS. Replace with:
- `QPropertyAnimation` for structural changes (sidebar width, opacity)
- `QTimer` + incremental stylesheet updates for color fades (generally not worth it â€” just use instant color change)
- Hover effects: QSS `:hover` pseudo-state gives instant color change, which is acceptable

---

## 7. Files to Modify

| File | Change scope |
|---|---|
| `Program/main.py` | Minor â€” splash / startup only |
| `Program/gui/main_window.py` | **Major** â€” full layout restructure, new toolbar, QSS |
| `Program/gui/control_panel.py` | **Major** â€” full redesign to match sidebar spec |
| `Program/gui/dataset_tab.py` | **Medium** â€” new sub-tab bar style, content layout |
| `Program/gui/plot_workspace.py` | **Medium** â€” inner toolbar + sidebar style updates |
| `Program/gui/statistics_tab.py` | **Medium** â€” stat cards layout |
| `Program/gui/comparison_tab_enhanced.py` | **Medium** â€” header + table styles |
| `Program/gui/reporting_tab.py` | **Medium** â€” config panel + preview styling |
| `Program/gui/export_tab.py` | **Medium** â€” format card grid + button styles |
| `Program/gui/welcome_widget.py` | **Medium** â€” style to match shell |
| `Program/gui/column_mapper.py` | **Low** â€” restyle dialog |
| `Program/gui/sheet_selector.py` | **Low** â€” restyle dialog |
| `Program/gui/dataset_selection_dialog.py` | **Low** â€” restyle dialog |
| `Program/gui/help_dialog.py` | **Low** â€” restyle dialog |
| `Program/gui/error_tab.py` | **Low** â€” restyle |
| **New:** `Program/gui/theme.py` | QSS token module |
| **New:** `Program/gui/webview_bridge.py` | Python <-> JavaScript bridge for selective webview surfaces |
| **New:** `Program/resources/fonts/` | Bundled font files |
| **New:** `Program/resources/icons/` | SVG icon files (optional) |
| **New:** `Program/resources/web/` | Bundled HTML/CSS/JS assets for welcome/help/report surfaces |

---

## 8. Remaining Design Work

### Concept HTMLs still needed
| File | Content |
|---|---|
| `03_reports_export.html` | Reports tab (config + preview) + Export tab (format cards + content options) |
| `04_dialogs.html` | Column Mapper, Sheet Selector, Manage Porosity, Data Inspector, Load Log, About, Dataset Selection |
| `05_welcome.html` | Welcome tab (landing state before any data is loaded) |

### Open design questions (deferred)
1. **Comparison with 20+ datasets** â€” selection model not yet designed. When Comparison tab is active with >6 datasets, how does the user choose which to display? Options: multi-select checkbox list in a left panel, or "Compare selected" button from sidebar. To be addressed in concept HTML review.

2. **Error tab** (`error_tab.py`) â€” what does it show, when? Design not started.

3. **Welcome tab** â€” what does the landing screen look like before any data is loaded? Currently a `WelcomeWidget`. Needs redesign concept.

4. **Column Mapper UX** â€” currently triggered when column names are ambiguous. Will the new "Inspect" action also surface this? Relationship to be clarified.

5. **Per-sample porosity management** â€” triggered from sidebar. Is this a dialog or a panel? Not yet designed.

6. **Keyboard shortcuts** â€” no shortcut spec yet. Standard ones assumed (Ctrl+O open, Ctrl+K calculate, Ctrl+E export, F1 help).

---

## 9. Implementation Order (recommended)

1. Create `gui/theme.py` â€” token module, generate base QSS
2. Bundle fonts, load at startup
3. Restyle `main_window.py` â€” shell grid, menu bar, status bar
4. Restyle `control_panel.py` â€” full sidebar redesign
5. Implement custom dataset tab bar (scrollable + overflow)
6. Restyle global toolbar (nav tabs + action buttons)
7. Restyle `dataset_tab.py` â€” nested sub-tab bar
8. Restyle `plot_workspace.py` â€” inner toolbar + collapsible sidebar
9. Restyle `statistics_tab.py`
10. Restyle `comparison_tab_enhanced.py`
11. Restyle `reporting_tab.py` + `export_tab.py`
12. Restyle all dialogs
13. Restyle `welcome_widget.py`
14. Update matplotlib rcParams for plot styling
15. Integration testing across all views

---

## 10. Constraints & Accepted Compromises

| Feature | Decision |
|---|---|
| Grain texture overlay | **Skip** â€” palette works without it |
| CSS hover transitions | **Accept instant** â€” QSS `:hover` is instant, acceptable |
| Font Awesome classes | **Use unicode codepoints** via bundled FA font |
| CSS `border-radius` on QTabBar tabs | QSS supports this, test carefully on Windows |
| Sidebar animation | **QPropertyAnimation on maximumWidth** |
| Plot sidebar animation | Same as sidebar |
| Native window decorations | Keep â€” do not attempt custom titlebar |
| High-DPI | PyQt6 handles automatically; use `devicePixelRatio`-aware icon sizes |
| Dark mode | Not planned â€” warm earthy light theme only |
