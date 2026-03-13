# GrainSize Analysis — Visual Design Specification
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

**Name:** Grain Size Analysis — Hydraulic Conductivity Calculator
**Platform:** Windows desktop (PyQt6). Packaged with PyInstaller.
**Audience:** Geotechnical / hydrogeological consultants (DTU context).
**Entry point:** `Program/main.py` → `SimpleSplash` → `MainWindow`
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
| `--logo-sub` | `#c8a87a` | Logo subtitle ("ANALYSIS · v0.9-β") |

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
| 4 | `#2a9d8f` | Teal |
| 5 | `#a03a30` | Red-earth |
| 6 | `#4a6a9a` | Slate blue |
| 7 | `#7a6a28` | Dark gold |

> **Comparison scalability note:** The color palette above covers 8 samples. For 9–20+ datasets, use the Selected/Pinned model — see §5.10 and §5.10.1.

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
| Table headers | 10–10.5px | 600, uppercase | `--text-mid` |
| Table body | 12px | 400 | `--text` |
| Table mono data | 11.5px | 400 (Mono) | `#3a7ea0` |
| Stat card values | 14–20px | 500 (Mono) | varies |
| Status bar keys | 9.5px | 400 (Mono) | `--st-dim` |
| Status bar values | 10.5px | 400 (Mono) | `--st-text` |
| Badge / pill text | 10–10.5px | 500 | varies |

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
| Comparison sub-tab bar height | 34px | Custom sub-tab header |
| Comparison pinned panel width | 188px | `setFixedWidth(188)` (collapsible) |
| Border radius (`--r`) | 4px | `border-radius: 4px` in QSS |
| Sidebar card padding | 6px 8px | `setContentsMargins(8, 6, 8, 6)` |

---

## 5. Component Catalog

### 5.1 Application Shell
**Layout:** QMainWindow → QWidget (central) → QHBoxLayout: `[Sidebar | Main]`
Main has QVBoxLayout: `[MenuBar | Toolbar | ds-tab-bar | content-area]`
Status bar: QStatusBar (bottom).

### 5.2 Sidebar
**Structure:** QWidget (fixed 258px) → QVBoxLayout with no margins:
- Logo card (fixed height ~54px)
- Scrollable body (QScrollArea, expanding)
- DTU box (fixed height ~36px)
- Footer button row (fixed height ~42px)

**Logo card:** Custom QWidget with gradient background painted in `paintEvent`. Contains FA icon + "GrainSize" (Playfair Display) + subtitle (JetBrains Mono). Background: `#8e6e4a → #7a5e3e` linear gradient.

**Section headers:** QFrame with background `--sb-up`, containing a QLabel (uppercase, `--sb-muted`) and optional QPushButton (small, transparent).

**Sample cards:** Custom QWidget per sample. Two states: collapsed (row only) / expanded (row + detail section). Contains:
- Row: icon QLabel + name/meta QVBoxLayout + status LED + **selected toggle** (checkbox-style QPushButton) + expand chevron QPushButton
- Detail: status line QLabel + action buttons QHBoxLayout (Inspect / Log / Props / Remove)

Active card: background `--sb-act`, left accent bar (3×16px painted rectangle, `--olive`).

**Selected toggle:** Small 17×17px checkbox-style button on each card. Unchecked = white with `--sb-bdr` border. Checked = olive fill with white checkmark. Toggling updates the selected count in the inventory summary below.

**Inventory summary bar:** Below the sample list. Shows: `N loaded · N selected · ⚠ N` on a single line. Two compact action buttons: "Compare" (olive primary) and "Export" (secondary). This replaces the old 4-chip stats block.

**Filter pills:** "All" | "Selected" | "Warnings" — show/hide sample cards by state.

**Sidebar sync rule:** Clicking a sidebar card activates the matching dataset tab (and vice versa). Single `currentDatasetId` state owned by MainWindow.

**Drop zone:** QFrame with dashed border, `--sb-bdr`. Hover: border `--olive`.

**DTU box:** QWidget, background `--sb-dn`. Contains "DTU" QLabel with background `#C8002A` (red pill) + program name/subtitle QLabels.

### 5.3 Four-State Batch Model
**Confirmed vocabulary — use consistently everywhere in code and UI:**

| State | Meaning | Where visible |
|---|---|---|
| **Loaded** | Every dataset that has been imported into the session | Sidebar sample list, inventory summary count |
| **Open** | Datasets with an active tab in the dataset tab bar | Dataset tab bar tabs |
| **Selected** | Subset chosen for comparison/export scope | Sidebar selected toggle (checkbox), inventory "N selected" count, comparison header, export scope |
| **Pinned** | Visible subset within the comparison Plot view (when selected > manageable limit) | Comparison pinned panel sidebar |

Rules:
- Selected is managed in the sidebar (toggle per card)
- Pinning happens only in the Comparison tab's pinned panel
- A dataset can be Selected but not Pinned (it exists in the scope but is dimmed in the plot)
- Reports and Export default scope = Selected datasets

### 5.4 Menu Bar
Standard `QMenuBar`. Background `--mb-bg`. Item hover: `rgba(107,142,35,.1)`. Dropdown `QMenu`: background `--bg-raised`, border `--border`, border-radius 6px. Menu items 12.5px Source Sans 3.

**Menus:** File | Analysis | View | Help (right-aligned title label showing full program name)

### 5.5 Global Toolbar
QWidget (height 40px), background `--tb-bg`. QHBoxLayout.
Left: tab buttons for top-level views (Individual Samples | Comparison | Reports | Export).
Middle: separator + Add Files button + Calculate K button (olive primary).
Right: Help button.

**Tab styling:** active tab has 2px `--olive` bottom border, `--olive` text color. Inactive: `--text-muted`. Hover: `--text-mid`.

**Toolbar buttons:** QPushButton, transparent background, hover: `--tan` background + `--earth` border.
**Primary (Calculate K):** background `--olive`, border `--olive-dk`, white text.

### 5.6 Dataset Tab Bar
Custom widget (height 30px). **Not QTabWidget** — custom implementation required for:
- Scrollable overflow with `◀ / ▶` navigation buttons
- `⋯ +N` overflow dropdown listing all datasets
- Close (✕) button per tab

**Recommended implementation:** `QScrollArea` (horizontal only) containing a `QWidget` with `QHBoxLayout` of custom `DatasetTabButton` widgets. Nav arrows are `QPushButton` outside the scroll area. Overflow button opens a `QMenu`.

**Tab states:** inactive (`--text-muted`, transparent bg), hover (`--bg-low`, `--border`), active (`--bg`, `--border` all sides except bottom, `--text`).

**Welcome tab:** always leftmost, no close button, icon `fa.house`.

### 5.7 Nested Sub-Tab Bar (Plot / Results / Statistics)
QWidget (height 32px), background `--bg`. Contains 3 QPushButtons.
Active: 2px bottom border `--earth`, `--text` color.
Inactive: `--text-muted`. Hover: `--text-mid`.
Only visible when Individual Samples tab is active.

### 5.8 Plot Workspace (inner)
**Structure:** QVBoxLayout: `[inner-toolbar | body]`, body = QHBoxLayout: `[inner-sidebar | chart]`

**Inner toolbar** (height 34px, bg `--bg-raised`):
- Plot type segmented control (Dist. Curve / K-Values) — QButtonGroup of QPushButtons
- Style dropdown (QComboBox): Professional / Presentation / Minimalist / Classic
- Toggle buttons: Grid / Legend / Zones / D-lines
- Zoom buttons: +, −, Fit
- Export button
- Toggle-sidebar button (rightmost)

**Inner sidebar** (width 200px, collapsible, bg `--pw-sb`):
Collapse/expand via `QPropertyAnimation` on `maximumWidth` (0 ↔ 200).
Contains: Axis Controls section (X/Y min/max inputs) + Display Options section (toggle switches) + Curve Color section (color pickers per loaded sample).

**Toggle switches:** Custom QWidget painting an on/off pill (background `--border` → `--olive`, knob white circle). Animate knob position via `QPropertyAnimation`.

**Chart area:** `FigureCanvasQTAgg` (matplotlib). Style via matplotlib rcParams — see §6.3.

**Grain size zone bands:** The distribution plot shows soil classification zone bands (Clay / Silt / Fine Sand / Medium Sand / Coarse Sand / Gravel / Cobble). The band boundaries are defined by a classification standard. Multiple standards exist (USCS, BS 1377, ISO 14688, DIN 18196). The active standard must be selectable and drives:
- Band boundaries (sieve sizes in mm)
- Band labels
- Band fill colors (fixed to the earthy palette regardless of standard)
The zone band toggle in the inner toolbar shows/hides bands without changing the selected standard. Standard selection lives in the Analysis menu or a settings dialog.

### 5.9 Results Tab
**Structure:** QVBoxLayout: `[summary-bar | split-area]`
Split: QSplitter horizontal → `[K-table | method-detail-panel]`

**Summary bar** (bg `--bg-raised`): Row of stat cells (K̄ m/d, K̄ m/s, methods valid, D50, temperature). Each cell: value (Mono, 15px) + key label (9.5px uppercase).

**K-values table:** QTableWidget. Columns: Method | Category | K cm/s | K m/s | K m/d | Status. Sticky header via `horizontalHeader().setStretchLastSection`. Selected row: olive left border + `rgba(107,142,35,.07)` background.

**Method detail panel** (width 240px): QScrollArea containing stacked QFrames for: header (name, K value big), Parameters Used, Formula, Applicability, Reference.

### 5.10 Comparison Tab
**Confirmed design (2026-03-12):**

**Header bar:** `[icon] [title "Batch Comparison"] [scope note "N selected · N pinned in view"] [spacer] [Manage Datasets btn] [Export Selected btn (olive)]`

**Sub-tab bar** (height 34px): Two sub-tabs — **Plot** and **Details**. Active: 2px `--olive` bottom border. Only visible when Comparison tab is active.

#### 5.10.1 Plot sub-tab
**Layout:** QHBoxLayout: `[plot-area | pinned-panel]`

**Plot area:** `FigureCanvasQTAgg` displaying a multi-curve grain size distribution overlay. All selected-and-pinned datasets shown at full weight; selected-but-not-pinned datasets shown dimmed (opacity 0.3, dashed line). Each dataset uses its identity color from §2.

**Pinned panel** (width 188px, collapsible):
- Header: "Pinned (N/M)" + collapse chevron button
- List of all selected datasets. Each row: color dot + short name + thumbtack button (pinned = olive, unpinned = muted)
- Clicking a thumbtack toggles pinned state
- Collapse via `QPropertyAnimation` on `maximumWidth`

#### 5.10.2 Details sub-tab
**Layout:** QSplitter horizontal → `[Grain Parameters panel | Hydraulic Conductivity panel]`

Each panel: panel header label + QTableWidget.
- Columns: Parameter | one column per **pinned** dataset (colored dot in header)
- Rows: Grain Parameters (D10/D30/D50/D60/D90/Cu/Cc/Fines/USCS) and K Values (per method + geometric mean row + permeability class row)
- Summary/geomean row: slightly tinted background, bold values

### 5.11 Reports Tab
**Structure:** QSplitter horizontal → `[config-panel (max 300px) | preview-panel]`

**Default scope:** Selected datasets (not all loaded).

Config panel: QScrollArea with options — report type (Individual / Comparison / Full), dataset selection checkboxes, content toggles (grain data / K values / stats / plots), format options.

Preview panel: `QWebEngineView` preferred for HTML report preview; `QTextBrowser` is an acceptable fallback if packaging or printing constraints make it simpler. Toolbar above: Generate / Print / Save PDF.

### 5.12 Export Tab
**Default scope:** Selected datasets (not all loaded).

**Format selection:** Card-based grid — each format (CSV Long, CSV Wide, Excel, JSON, PNG, SVG, PDF) as a toggleable QFrame card. Selected: olive border + tinted bg.

**Content section:** Checkboxes — grain data, K values, statistics, plots.

**Output section:** Path selector + filename pattern + Export button.

**Progress:** `QProgressDialog` shown during export.

### 5.13 Status Bar
QStatusBar, height 24px, background `--st-bg` (#8b7355). Contains custom QLabel widgets:
- Status pill: LED dot (QLabel with circular stylesheet) + "Ready" text
- Separator: 1px vertical QFrame
- Segments: SAMPLE / D50 / K̄ / TEMP / METHODS / DATASETS
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
Existing dialog. Used by comparison/reporting to choose which datasets to include. Must be restyled. Vocabulary updated: shows Selected state, allows toggling. Will be extended later for pinned management.

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

Curve colors for multi-sample plots: use the 8-color identity palette from §2.

**Zone band implementation:** Render as `ax.axvspan(x_min, x_max, ...)` calls on a log-scaled X axis. Band colors use the earthy palette (see concept HTML for exact values). A `GrainClassificationSystem` dataclass holds boundary definitions per standard. The active system is passed to the plot function; toggling visibility is a simple `set_visible()` call on the axvspan patches.

### 6.4 Webview integration
When a webview surface is used, implement it as a thin hosted view:

- Host widget: dedicated PyQt widget or tab responsible for sizing, lifecycle, and loading local assets
- Asset location: bundled local files under `Program/resources/web/`
- Bridge: one explicit Python-to-JS / JS-to-Python bridge object for events and data updates
- Payload shape: JSON-serializable dictionaries and lists only
- Ownership rule: calculations, validation, dataset selection, and export logic stay in Python
- Fallback rule: if a webview surface becomes sluggish or hard to keep in sync, move that surface back to native Qt

### 6.5 Icons
**Confirmed: use `qtawesome` (pip package).**

```python
import qtawesome as qta

# Usage
icon = qta.icon('fa6s.vial', color='#6a5438')
button.setIcon(icon)

# For QLabel text icons
label = qta.IconWidget('fa6s.triangle-exclamation', color='#d08020', size=12)
```

- Import `qtawesome` everywhere icons are needed — no need to bundle font files manually
- Use `fa6s.*` (Font Awesome 6 Solid) prefix for solid icons
- Use `fa6r.*` for regular icons
- Color the icon at creation time using the appropriate token constant from `theme.py`
- For status LEDs, use painted `QLabel` with circular stylesheet (not icons)

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
The SVG noise grain texture (`body::after`) is **not achievable in QSS**. Skip it — the earthy palette reads well without it on desktop.

### 6.9 CSS transitions
Not supported in QSS. Replace with:
- `QPropertyAnimation` for structural changes (sidebar width, opacity)
- `QTimer` + incremental stylesheet updates for color fades (generally not worth it — just use instant color change)
- Hover effects: QSS `:hover` pseudo-state gives instant color change, which is acceptable

---

## 7. Files to Modify

| File | Change scope |
|---|---|
| `Program/main.py` | Minor — splash / startup only |
| `Program/gui/main_window.py` | **Major** — full layout restructure, new toolbar, QSS |
| `Program/gui/control_panel.py` | **Major** — full redesign to match sidebar spec |
| `Program/gui/dataset_tab.py` | **Medium** — new sub-tab bar style, content layout |
| `Program/gui/plot_workspace.py` | **Medium** — inner toolbar + sidebar style updates |
| `Program/gui/statistics_tab.py` | **Medium** — stat cards layout |
| `Program/gui/comparison_tab_enhanced.py` | **Major** — full redesign: header + Plot/Details sub-tabs + pinned panel |
| `Program/gui/reporting_tab.py` | **Medium** — config panel + preview styling |
| `Program/gui/export_tab.py` | **Medium** — format card grid + button styles |
| `Program/gui/welcome_widget.py` | **Medium** — style to match shell |
| `Program/gui/column_mapper.py` | **Low** — restyle dialog |
| `Program/gui/sheet_selector.py` | **Low** — restyle dialog |
| `Program/gui/dataset_selection_dialog.py` | **Low** — restyle dialog |
| `Program/gui/help_dialog.py` | **Low** — restyle dialog |
| `Program/gui/error_tab.py` | **Low** — restyle |
| **New:** `Program/gui/theme.py` | QSS token module + color constants |
| **New:** `Program/resources/fonts/` | Bundled font files (Source Sans 3, Playfair Display, JetBrains Mono) |

---

## 8. Design Concepts Status

| File | Status |
|---|---|
| `02_tabs.html` | ✓ Complete — Individual Samples + Comparison (Plot/Details sub-tabs + pinned panel) |
| `03_reports_export.html` | Needs update — scope rules (Selected default), empty states, stale preview state |
| `04_dialogs.html` | ✓ Complete — all 7 dialogs |
| `05_welcome.html` | ✓ Complete — based on existing `welcome_widget.py` structure |

### Open design questions (deferred)
1. **Error tab** (`error_tab.py`) — what does it show, when? Design not started.
2. **Column Mapper UX** — currently triggered when column names are ambiguous. Will the new "Inspect" action also surface this?
3. **Per-sample porosity management** — triggered from sidebar. Dialog confirmed; visual spec not detailed.
4. **Keyboard shortcuts** — no shortcut spec yet. Standard ones assumed (Ctrl+O open, Ctrl+K calculate, Ctrl+E export, F1 help).
5. **Grain classification standard selector** — which standards to support (USCS, BS 1377, ISO 14688, DIN 18196)? Where does the user select the active standard?

---

## 9. Implementation Order (recommended)

1. Create `gui/theme.py` — token module, generate base QSS
2. Bundle fonts, load at startup (`main.py`)
3. Restyle `main_window.py` — shell grid, menu bar, status bar
4. Restyle `control_panel.py` — full sidebar redesign (logo card, sample cards, inventory summary, filter pills)
5. Implement custom dataset tab bar (scrollable + overflow)
6. Restyle global toolbar (nav tabs + action buttons)
7. Restyle `dataset_tab.py` — nested sub-tab bar
8. Restyle `plot_workspace.py` — inner toolbar + collapsible sidebar + zone bands
9. Restyle `statistics_tab.py`
10. Restyle `comparison_tab_enhanced.py` — header + Plot sub-tab (pinned panel) + Details sub-tab
11. Restyle `reporting_tab.py` + `export_tab.py`
12. Restyle all dialogs
13. Restyle `welcome_widget.py`
14. Update matplotlib rcParams + zone band system
15. Integration testing across all views

---

## 10. Constraints & Accepted Compromises

| Feature | Decision |
|---|---|
| Grain texture overlay | **Skip** — palette works without it |
| CSS hover transitions | **Accept instant** — QSS `:hover` is instant, acceptable |
| Icons | **`qtawesome`** — FA6 icons via pip package, color at creation time using theme constants |
| CSS `border-radius` on QTabBar tabs | QSS supports this, test carefully on Windows |
| Sidebar animation | **QPropertyAnimation on maximumWidth** |
| Plot sidebar animation | Same as sidebar |
| Native window decorations | Keep — do not attempt custom titlebar |
| High-DPI | PyQt6 handles automatically; use `devicePixelRatio`-aware icon sizes |
| Dark mode | Not planned — warm earthy light theme only |
| Matplotlib backend | Use `QtAgg` (not `Qt5Agg`) for PyQt6 compatibility |
