"""
theme.py — Single source of truth for all visual design tokens.

Every color, font size, spacing value, and QSS rule originates here.
Import this module anywhere a color or style is needed.

Usage:
    from gui.theme import C, F, SZ, build_stylesheet, icon

    # Apply globally at startup (main.py or main_window.py):
    app.setStyleSheet(build_stylesheet())

    # Use a color constant directly:
    label.setStyleSheet(f"color: {C.TEXT_MID};")

    # Get a qtawesome icon:
    btn.setIcon(icon('fa6s.vial', C.SB_MID))
"""

from __future__ import annotations
import sys
from pathlib import Path
from PyQt6.QtCore import Qt, QRectF, QEvent, QObject
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPalette, QPen, QPixmap


_MATPLOTLIB_FONTS_REGISTERED = False
_QTA_MODULE = None
_ICON_BASE_SIZE_PX = 14.0


def _font_base_dir() -> Path:
    """Return the bundled font directory for dev and frozen builds."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        candidates = [
            base / "Program" / "resources" / "fonts",
            base / "resources" / "fonts",
        ]
        for candidate in candidates:
            if candidate.is_dir():
                return candidate
        return candidates[0]
    return Path(__file__).resolve().parent.parent / "resources" / "fonts"


def _register_matplotlib_fonts(base: Path) -> None:
    """Register bundled fonts with matplotlib for the current process."""
    global _MATPLOTLIB_FONTS_REGISTERED

    if _MATPLOTLIB_FONTS_REGISTERED or not base.is_dir():
        return

    try:
        from matplotlib import font_manager
    except Exception:
        return

    for font_file in sorted(base.glob("*.ttf")):
        try:
            font_manager.fontManager.addfont(str(font_file))
        except Exception as exc:
            print(f"[theme] WARNING: Failed to register matplotlib font: {font_file.name} ({exc})")

    _MATPLOTLIB_FONTS_REGISTERED = True


def _qtawesome():
    """Import qtawesome on first use to keep cold startup light."""
    global _QTA_MODULE

    if _QTA_MODULE is None:
        import qtawesome as qta

        _QTA_MODULE = qta

    return _QTA_MODULE


def load_fonts() -> None:
    """Load bundled font files from resources/fonts/ via QFontDatabase.

    Must be called after QApplication is created but before build_stylesheet().
    Supports both development and PyInstaller frozen builds.
    """
    base = _font_base_dir()

    if not base.is_dir():
        return

    for font_file in sorted(base.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id < 0:
            print(f"[theme] WARNING: Failed to load font: {font_file.name}")
        else:
            families = QFontDatabase.applicationFontFamilies(font_id)
            print(f"[theme] Loaded font: {font_file.name} -> {families}")


class _ReadableToolTipFilter(QObject):
    """Keep Qt's reused private tooltip popup independent of source-widget QSS."""

    _QSS = (
        'background-color: #fffdf7; color: #2f2f2f; '
        'border: 1px solid #6b8e23; padding: 6px 9px;'
    )

    @classmethod
    def _style_popup(cls, watched) -> None:
        if watched.property('_readableTooltipApplying'):
            return
        watched.setProperty('_readableTooltipApplying', True)
        try:
            palette = watched.palette()
            background = QColor('#fffdf7')
            foreground = QColor(C.TEXT)
            palette_changed = False
            for role in (
                QPalette.ColorRole.Window,
                QPalette.ColorRole.Base,
                QPalette.ColorRole.ToolTipBase,
            ):
                if palette.color(role) != background:
                    palette.setColor(role, background)
                    palette_changed = True
            for role in (
                QPalette.ColorRole.WindowText,
                QPalette.ColorRole.Text,
                QPalette.ColorRole.ToolTipText,
            ):
                if palette.color(role) != foreground:
                    palette.setColor(role, foreground)
                    palette_changed = True
            if palette_changed:
                watched.setPalette(palette)
            watched.setAutoFillBackground(True)
            watched.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            watched.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            if watched.styleSheet() != cls._QSS:
                watched.setStyleSheet(cls._QSS)
        finally:
            watched.setProperty('_readableTooltipApplying', False)

    def eventFilter(self, watched, event):
        try:
            is_tip = watched.metaObject().className() == 'QTipLabel'
        except Exception:
            is_tip = False
        if is_tip and event.type() in {
            QEvent.Type.Show,
            QEvent.Type.Polish,
            QEvent.Type.PaletteChange,
            QEvent.Type.StyleChange,
            QEvent.Type.ToolTipChange,
        }:
            self._style_popup(watched)
        return False


def apply_tooltip_style(app=None) -> None:
    """Force readable tooltips centrally, including controls with local QSS."""
    try:
        from PyQt6.QtWidgets import QApplication, QToolTip
    except Exception:
        return

    target = app or QApplication.instance()
    if target is None:
        return

    palette = target.palette()
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#fffdf7"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(C.TEXT))
    target.setPalette(palette)
    QToolTip.setPalette(palette)
    tooltip_filter = getattr(target, '_readable_tooltip_filter', None)
    if tooltip_filter is None:
        tooltip_filter = _ReadableToolTipFilter(target)
        target.installEventFilter(tooltip_filter)
        target._readable_tooltip_filter = tooltip_filter


def default_ui_font_family(platform_name: str | None = None) -> str:
    """Return the primary UI font family for the current platform."""
    platform_name = sys.platform if platform_name is None else platform_name
    if platform_name == "win32":
        # Native Windows UI text is consistently crisper than bundled variable fonts.
        return "Segoe UI"
    return "Source Sans 3"


def default_ui_font_families(platform_name: str | None = None) -> list[str]:
    """Return ordered fallbacks for plot text and other font consumers."""
    primary = default_ui_font_family(platform_name)
    families = [primary]
    if primary != "Source Sans 3":
        families.append("Source Sans 3")
    families.append("DejaVu Sans")
    return families


def default_matplotlib_font_families(platform_name: str | None = None) -> list[str]:
    """Return font fallbacks that Matplotlib can resolve reliably in frozen builds."""
    platform_name = sys.platform if platform_name is None else platform_name
    families = ["DejaVu Sans"]
    if platform_name == "win32":
        families.append("Segoe UI")
    return families


# ─────────────────────────────────────────────────────────────
# COLOR TOKENS
# ─────────────────────────────────────────────────────────────

class C:
    """Color constants — mirrors CSS custom properties in _shared.css."""

    # ── Content area ──
    BG          = "#f5f5f0"   # --bg        Main content background
    BG_RAISED   = "#eee8dc"   # --bg-raised Raised panels, tab bar backgrounds
    BG_LOW      = "#e8e0d0"   # --bg-low    Pressed/active states
    BORDER      = "#d4c4a8"   # --border    Default borders
    BORDER_DK   = "#c0ae90"   # --border-dk Stronger borders, table header underlines
    TEXT        = "#2f2f2f"   # --text      Primary text
    TEXT_MID    = "#5d4e37"   # --text-mid  Secondary labels
    TEXT_MUTED  = TEXT_MID    # --text-muted High-contrast tertiary labels

    # ── Accent ──
    OLIVE       = "#6b8e23"   # --olive     Primary action, active underline
    OLIVE_H     = "#7fa02d"   # --olive-h   Olive hover
    OLIVE_DK    = "#4f6a1a"   # --olive-dk  Olive border / pressed
    TAN         = "#d2b48c"   # --tan       Toolbar button hover bg
    TAN_H       = "#ddbf94"   # --tan-h     Tan hover
    AMBER       = "#c4a574"   # --amber     Scrollbar thumb, decorative
    EARTH       = "#8b7355"   # --earth     Status bar bg, strong borders

    # ── Sidebar ──
    SB          = "#ddd3be"   # --sb        Sidebar base background
    SB_UP       = "#e5dcc8"   # --sb-up     Section header bands
    SB_DN       = "#d0c4ac"   # --sb-dn     Footer / DTU box background
    SB_ACT      = "#c8ba9e"   # --sb-act    Active sample card background
    SB_BDR      = "#c0ae90"   # --sb-bdr    Sidebar borders
    SB_TEXT     = "#3a2e1c"   # --sb-text   Primary sidebar text
    SB_MID      = "#6a5438"   # --sb-mid    Secondary sidebar text
    SB_MUTED    = "#9a8468"   # --sb-muted  Muted sidebar labels

    # ── Logo card ──
    LOGO_BG     = "#7a5e3e"
    LOGO_BG_TOP = "#8e6e4a"
    LOGO_TEXT   = "#f4ece0"
    LOGO_SUB    = "#c8a87a"

    # ── Status bar ──
    ST_BG       = "#8b7355"
    ST_TEXT     = "#f0e8d8"
    ST_MUTED    = "#c4a882"
    ST_DIM      = "#a89070"

    # ── Chrome bars ──
    MB_BG       = "#ede8de"   # Menu bar background
    MB_BDR      = "#cfc0a4"   # Menu bar border
    TB_BG       = "#e4d8c0"   # Global toolbar background
    TB_BDR      = "#ccc0a0"   # Toolbar border
    PW_SB       = "#ece5d8"   # Plot workspace inner sidebar

    # ── Status indicators ──
    LED_OK      = "#5aaa3a"   # Green LED (sidebar)
    LED_OK_ST   = "#7dd050"   # Green LED (status bar, brighter)
    LED_WARN    = "#d08020"   # Orange warning
    LED_ERR     = "#c03828"   # Red error
    K_BLUE      = "#3a7ea0"   # K-value numeric color (tables)
    DTU_RED     = "#C8002A"   # DTU wordmark background

    # ── Grain-zone palette (Stratigraphy widget + plot bands) ──
    GC_CLAY   = "#7a9bbd"   # Muted blue  — clay
    GC_SILT   = "#b09870"   # Warm tan    — silt
    GC_SAND   = "#d4b86a"   # Sandy gold  — sand
    GC_GRAVEL = "#a09080"   # Grey-brown  — gravel
    GC_COBBLE = "#807870"   # Dark grey   — cobble

    # ── Sample identity palette (Comparison tab) ──
    # Assign in order; cycle if > 8 samples.
    SAMPLE_COLORS = [
        "#3a7ea0",  # 0 Blue
        "#6b8e23",  # 1 Olive
        "#b46428",  # 2 Amber-brown
        "#8b4580",  # 3 Purple
        "#2a9d8f",  # 4 Teal
        "#a03a30",  # 5 Red-earth
        "#4a6a9a",  # 6 Slate blue
        "#7a6a28",  # 7 Dark gold
    ]

    @staticmethod
    def sample_color(index: int) -> str:
        """Return identity color for sample at given index (cycles)."""
        return C.SAMPLE_COLORS[index % len(C.SAMPLE_COLORS)]


# ─────────────────────────────────────────────────────────────
# FONT TOKENS
# ─────────────────────────────────────────────────────────────

FONT_BUMP = 1  # 0 = normal/compact, 1 = larger body UI.


def _normalise_font_bump(value) -> int:
    """Clamp the UI font bump to supported display-size presets."""
    try:
        bump = int(value)
    except (TypeError, ValueError):
        bump = 1
    return max(0, min(1, bump))


class F:
    """Font family names. Must match names registered via QFontDatabase."""
    UI    = default_ui_font_family()
    MONO  = "JetBrains Mono"
    DISP  = "Playfair Display"

    # Font size constants (as int, for QFont)
    SZ_XS   = 8                    # Logo subtitle
    SZ_SM   = 9                    # Section headers, meta labels, badge text
    SZ_BASE = 10 + FONT_BUMP       # Default body / sidebar
    SZ_MD   = 11 + FONT_BUMP       # Parameter labels, table body, inputs
    SZ_LG   = 12 + FONT_BUMP       # Menu items, toolbar tabs, cards, nested sub-tabs
    SZ_XL   = 13 + FONT_BUMP       # Toolbar section labels, dialog titles
    SZ_2XL  = 14 + FONT_BUMP       # Logo name, stat card values (small)
    SZ_3XL  = 18 + FONT_BUMP       # Stat card values (large)


def set_font_bump(value) -> int:
    """Set theme font-size preset before widgets/stylesheets are built."""
    global FONT_BUMP

    FONT_BUMP = _normalise_font_bump(value)
    F.SZ_BASE = 10 + FONT_BUMP
    F.SZ_MD = 11 + FONT_BUMP
    F.SZ_LG = 12 + FONT_BUMP
    F.SZ_XL = 13 + FONT_BUMP
    F.SZ_2XL = 14 + FONT_BUMP
    F.SZ_3XL = 18 + FONT_BUMP
    return FONT_BUMP


def font_bump() -> int:
    """Return the active theme font-size preset."""
    return FONT_BUMP


# ─────────────────────────────────────────────────────────────
# LAYOUT / SPACING TOKENS
# ─────────────────────────────────────────────────────────────

class SZ:
    """Layout size constants (pixels)."""
    SIDEBAR_W       = 310
    MENUBAR_H       = 24
    TOOLBAR_H       = 40
    DS_TABBAR_H     = 30
    STATUS_H        = 24
    PLOT_INNER_TB_H = 34
    PLOT_SIDEBAR_W  = 240
    SUB_TABBAR_H    = 32
    CMP_TABBAR_H    = 34
    CMP_PINNED_W    = 188
    BORDER_RADIUS   = 4
    CARD_PAD_H      = 6
    CARD_PAD_V      = 8


# ─────────────────────────────────────────────────────────────
# MATPLOTLIB RCPARAMS
# ─────────────────────────────────────────────────────────────

MATPLOTLIB_RCPARAMS: dict = {
    "axes.facecolor":       "#ffffff",
    "figure.facecolor":     "#ffffff",
    "figure.dpi":           120,
    "axes.edgecolor":       "#000000",
    "axes.labelcolor":      "#000000",
    "xtick.color":          "#000000",
    "ytick.color":          "#000000",
    "text.color":           "#000000",
    "grid.color":           "#000000",
    "grid.linewidth":       0.5,
    "grid.alpha":           0.18,
    "font.family":          default_matplotlib_font_families(),
    "font.size":            11,
    "axes.titlesize":       12,
    "axes.titlecolor":      "#000000",
    "axes.titleweight":     "600",
    "legend.fontsize":      10,
    "legend.framealpha":    0.9,
    "legend.edgecolor":     "#000000",
    "legend.facecolor":     "#ffffff",
    "savefig.facecolor":    "#ffffff",
    "savefig.edgecolor":    "#ffffff",
    "lines.antialiased":    True,
    "patch.antialiased":    True,
    "text.antialiased":     True,
    "axes.linewidth":       0.8,
    "xtick.major.width":    0.8,
    "ytick.major.width":    0.8,
}


def apply_matplotlib_style() -> None:
    """Apply MATPLOTLIB_RCPARAMS to global matplotlib rcParams."""
    _register_matplotlib_fonts(_font_base_dir())
    import matplotlib as mpl
    mpl.rcParams.update(MATPLOTLIB_RCPARAMS)


# ─────────────────────────────────────────────────────────────
# ICON HELPER
# ─────────────────────────────────────────────────────────────

_ICON_WARNINGS_SHOWN: set[str] = set()


def _warn_icon_once(message: str) -> None:
    if message in _ICON_WARNINGS_SHOWN:
        return
    _ICON_WARNINGS_SHOWN.add(message)
    print(f"[theme] {message}")


def _safe_qta_icon(fa_name: str, **kwargs) -> QIcon:
    """Return a qtawesome icon with safe fallbacks for unsupported prefixes."""
    qta = _qtawesome()
    try:
        return qta.icon(fa_name, **kwargs)
    except Exception as exc:
        if fa_name.startswith("fa6r."):
            fallback_name = "fa6s." + fa_name.split(".", 1)[1]
            try:
                _warn_icon_once(f'Icon fallback: "{fa_name}" -> "{fallback_name}" ({exc})')
                return qta.icon(fallback_name, **kwargs)
            except Exception as fallback_exc:
                _warn_icon_once(f'Icon unavailable: "{fa_name}" ({fallback_exc})')
                return QIcon()
        _warn_icon_once(f'Icon unavailable: "{fa_name}" ({exc})')
        return QIcon()


def icon(fa_name: str, color: str = C.TEXT_MID, size: int = 14) -> QIcon:
    """
    Return a QIcon from qtawesome.

    Args:
        fa_name: qtawesome icon name, e.g. 'fa6s.vial', 'fa6s.triangle-exclamation'
        color:   hex color string, default TEXT_MID
        size:    pixel size hint

    Example:
        btn.setIcon(icon('fa6s.bolt', C.OLIVE))
    """
    scale_factor = float(size) / _ICON_BASE_SIZE_PX if size > 0 else 1.0
    return _safe_qta_icon(
        fa_name,
        color=color,
        draw="path",
        scale_factor=scale_factor,
    )


def icon_colored(fa_name: str, color: str, active_color: str | None = None) -> QIcon:
    """Return an icon with optional active (checked) state color."""
    if active_color:
        return _safe_qta_icon(
            fa_name,
            color=color,
            color_active=active_color,
            draw="path",
        )
    return _safe_qta_icon(fa_name, color=color, draw="path")


def app_icon() -> QIcon:
    """Return a multi-size application icon for window/taskbar usage."""
    ico = QIcon()
    glyph_icon = _safe_qta_icon("fa6s.layer-group", color=C.LOGO_TEXT, draw="path")

    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        inset = max(1, size // 16)
        border_w = max(1, size // 32)
        radius = max(4.0, size * 0.22)
        rect = QRectF(inset, inset, size - inset * 2, size - inset * 2)

        painter.setPen(QPen(QColor(C.LOGO_BG_TOP), border_w))
        painter.setBrush(QColor(C.LOGO_BG))
        painter.drawRoundedRect(rect, radius, radius)

        accent_h = max(2.0, size * 0.14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(C.OLIVE))
        painter.drawRoundedRect(
            QRectF(rect.left(), rect.bottom() - accent_h, rect.width(), accent_h),
            radius * 0.55,
            radius * 0.55,
        )

        if not glyph_icon.isNull():
            glyph_size = max(10, int(size * 0.56))
            glyph = glyph_icon.pixmap(glyph_size, glyph_size)
            gx = int((size - glyph.width()) / 2)
            gy = int((size - glyph.height()) / 2 - size * 0.04)
            painter.drawPixmap(gx, gy, glyph)
        else:
            font = QFont(F.UI, max(7, int(size * 0.24)), QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(QColor(C.LOGO_TEXT))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "GS")

        painter.end()
        ico.addPixmap(pix)

    return ico


# ─────────────────────────────────────────────────────────────
# QSS STYLESHEET
# ─────────────────────────────────────────────────────────────

def _get_combo_arrow_path() -> str:
    """Write a tiny SVG chevron to temp and return its path for QSS url()."""
    import tempfile
    arrow_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 6">'
        f'<polygon points="0,0 10,0 5,6" fill="{C.TEXT_MUTED}"/>'
        '</svg>'
    )
    arrow_path = Path(tempfile.gettempdir()) / "gsa_combo_arrow.svg"
    arrow_path.write_text(arrow_svg, encoding="utf-8")
    return str(arrow_path).replace("\\", "/")


def combo_popup_qss(radius: int = 4) -> str:
    """QSS for *just* a combo's dropdown list, kept opaque, set on the combo itself.

    The app-wide ``QComboBox QAbstractItemView`` rule gives every dropdown an
    opaque background, but a bare ``background: transparent`` on an ancestor
    container bleeds into the popup and overrides it (an ancestor stylesheet beats
    the app stylesheet). Append this to a combo's own stylesheet — set directly on
    the combo, it wins over the bleed so the list never renders see-through, while
    leaving the combo's existing field styling intact. Use ``opaque_combo_qss``
    instead when the combo has no field styling of its own.
    """
    return f"""
        QComboBox QAbstractItemView {{
            background: {C.BG_RAISED};
            border: 1px solid {C.BORDER};
            border-radius: {radius}px;
            selection-background-color: rgba(107,142,35,0.12);
            selection-color: {C.TEXT};
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{ min-height: 22px; padding: 4px 8px; }}
        QComboBox QAbstractItemView::item:hover {{ background: rgba(107,142,35,0.08); }}
    """


def opaque_combo_qss(radius: int = 4) -> str:
    """Full opaque-combo QSS (field + dropdown list) to set directly on a combo.

    For a combo with no styling of its own that sits inside a transparent panel;
    pairs the standard field look with :func:`combo_popup_qss` so the popup can't
    render see-through. See that function for why the QSS must live on the combo.
    """
    arrow_url = _get_combo_arrow_path()
    return f"""
        QComboBox {{
            background: #ffffff;
            border: 1px solid {C.BORDER_DK};
            border-radius: {radius}px;
            padding: 3px 22px 3px 7px;
            color: {C.TEXT_MID};
            min-height: 22px;
        }}
        QComboBox:hover {{ border-color: {C.EARTH}; }}
        QComboBox:focus {{ border-color: {C.OLIVE}; }}
        QComboBox::drop-down {{ border: none; width: 18px; }}
        QComboBox::down-arrow {{ image: url("{arrow_url}"); width: 10px; height: 6px; }}
    """ + combo_popup_qss(radius)


def build_stylesheet() -> str:
    """
    Generate and return the full application QSS stylesheet.
    Apply with: app.setStyleSheet(build_stylesheet())

    Covers all widget types and named components. Cross-referenced against
    design_concepts/_shared.css for pixel accuracy.
    """
    r = SZ.BORDER_RADIUS
    _arrow_url = _get_combo_arrow_path()
    return f"""

/* ════════════════════════════════════════
   GLOBAL
════════════════════════════════════════ */
* {{
    outline: none;
}}
QWidget {{
    font-family: "{F.UI}";
    font-size: {F.SZ_BASE}pt;
    color: {C.TEXT};
    background-color: {C.BG};
}}

/* ════════════════════════════════════════
   MAIN WINDOW
════════════════════════════════════════ */
QMainWindow {{
    background-color: {C.BG};
}}

/* ════════════════════════════════════════
   MENU BAR  — matches _shared.css .mb
════════════════════════════════════════ */
QWidget#app-menubar {{
    background-color: {C.MB_BG};
    border-bottom: 1px solid {C.MB_BDR};
    min-height: {SZ.MENUBAR_H}px;
    max-height: {SZ.MENUBAR_H}px;
}}
QWidget#app-menubar[frameless="true"] {{
    border-bottom: 1px solid {C.MB_BDR};
}}
QWidget#app-menubar QWidget,
QWidget#app-menubar QLabel {{
    background: transparent;
}}
QToolButton[menubaritem="true"] {{
    padding: 3px 11px;
    border: none;
    border-radius: 2px;
    background: transparent;
    color: {C.TEXT_MID};
    font-family: "{F.UI}";
    font-size: {F.SZ_BASE}pt;
}}
QToolButton[menubaritem="true"]:hover,
QToolButton[menubaritem="true"]:pressed,
QToolButton[menubaritem="true"]:checked {{
    background: rgba(107,142,35,0.10);
    color: {C.TEXT};
}}
QToolButton[menubaritem="true"]::menu-indicator {{
    image: none;
    width: 0px;
}}
QWidget#menubar-spacer {{
    min-width: 0px;
}}
QLabel#menubar-title {{
    color: {C.TEXT_MUTED};
    font-family: "{F.UI}";
    font-size: {F.SZ_SM}pt;
    font-weight: 500;
    padding-right: 4px;
}}
QWidget#window-controls {{
    background: transparent;
}}
QToolButton[windowcontrol="true"] {{
    border: none;
    border-radius: 0;
    background: transparent;
    color: {C.TEXT_MID};
    padding: 0;
}}
QToolButton[windowcontrol="true"]:hover {{
    background: rgba(107,142,35,0.10);
    color: {C.TEXT};
}}
QToolButton[windowcontrol="true"][controlrole="close"]:hover {{
    background: rgba(176,58,46,0.12);
    color: #7a241d;
}}
QMenuBar {{
    background-color: {C.MB_BG};
    border-bottom: 1px solid {C.MB_BDR};
    font-size: {F.SZ_SM}pt;
    color: {C.TEXT_MID};
    padding: 0 6px;
    max-height: {SZ.MENUBAR_H}px;
}}
QMenuBar::item {{
    padding: 3px 10px;
    background: transparent;
    border-radius: 2px;
}}
QMenuBar::item:selected,
QMenuBar::item:pressed {{
    background: rgba(107,142,35,0.10);
    color: {C.TEXT};
}}
QMenu {{
    background-color: {C.BG_RAISED};
    border: 1px solid {C.BORDER};
    border-radius: 6px;
    padding: 4px 0;
    font-size: {F.SZ_BASE}pt;
    color: {C.TEXT_MID};
}}
QMenu::item {{
    padding: 5px 28px 5px 14px;
}}
QMenu::item:selected {{
    background: rgba(107,142,35,0.08);
    color: {C.TEXT};
    border-radius: 3px;
}}
QMenu::separator {{
    height: 1px;
    background: {C.BORDER};
    margin: 3px 8px;
}}
QMenu::icon {{
    padding-left: 8px;
}}

/* ════════════════════════════════════════
   GLOBAL TOOLBAR  — matches _shared.css .tb
   Apply via QWidget#app-toolbar
════════════════════════════════════════ */
QWidget#app-toolbar {{
    background: {C.TB_BG};
    border-bottom: 1px solid {C.TB_BDR};
    min-height: {SZ.TOOLBAR_H}px;
    max-height: {SZ.TOOLBAR_H}px;
}}
/* Force ALL children inside toolbar to be transparent so the warm
   tan background (#e4d8c0) shows through — prevents global
   QWidget {{ background: #f5f5f0 }} from washing out the toolbar. */
QWidget#app-toolbar QWidget,
QWidget#app-toolbar QFrame {{
    background: transparent;
}}
/* Nav tab buttons inside toolbar */
QWidget#app-toolbar QPushButton[navtab="true"] {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    color: {C.TEXT_MUTED};
    font-family: "{F.UI}";
    font-size: {F.SZ_BASE}pt;
    font-weight: 500;
    padding: 0 16px;
    min-height: {SZ.TOOLBAR_H}px;
    max-height: {SZ.TOOLBAR_H}px;
}}
QWidget#app-toolbar QPushButton[navtab="true"]:hover {{
    color: {C.TEXT_MID};
}}
QWidget#app-toolbar QPushButton[navtab="true"]:pressed {{
    color: {C.TEXT};
}}
QWidget#app-toolbar QPushButton[navtab="true"][active="true"] {{
    color: {C.OLIVE};
    border-bottom: 2px solid {C.OLIVE};
}}
/* Action buttons in toolbar */
QWidget#app-toolbar QPushButton[toolaction="true"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {r}px;
    color: {C.TEXT_MID};
    font-size: {F.SZ_BASE}pt;
    padding: 0 11px;
    min-height: 26px;
    max-height: 28px;
}}
QWidget#app-toolbar QPushButton[toolaction="true"]:hover {{
    background: {C.TAN};
    border-color: {C.EARTH};
    color: {C.TEXT};
}}
QWidget#app-toolbar QPushButton[toolaction="true"]:pressed {{
    background: {C.BG_LOW};
    border-color: {C.EARTH};
    color: {C.TEXT};
}}
QWidget#app-toolbar QPushButton[toolaction="true"][active="true"] {{
    background: rgba(107,142,35,0.10);
    border-color: rgba(107,142,35,0.35);
    color: {C.OLIVE};
}}
/* ════════════════════════════════════════
   STATUS BAR  — matches _shared.css .st
════════════════════════════════════════ */
QStatusBar {{
    background-color: {C.ST_BG};
    border-top: 1px solid #7a6448;
    color: {C.ST_TEXT};
    font-family: "{F.MONO}";
    font-size: {F.SZ_SM}pt;
    min-height: {SZ.STATUS_H}px;
    max-height: {SZ.STATUS_H}px;
    padding: 0;
}}
QStatusBar::item {{
    border: none;
}}
QStatusBar QLabel {{
    background: transparent;
    color: {C.ST_TEXT};
}}

/* ════════════════════════════════════════
   SIDEBAR  — matches _shared.css .sb
════════════════════════════════════════ */
QFrame#sidebar {{
    background: {C.SB};
    border: none;
    border-right: 1px solid {C.SB_BDR};
}}
QFrame#sidebar QLabel {{
    background: transparent;
}}

/* Input widgets inside the sidebar — warm tint (rgba(255,255,255,0.55) over #ddd3be) */
QFrame#sidebar QLineEdit,
QFrame#sidebar QSpinBox,
QFrame#sidebar QDoubleSpinBox,
QFrame#sidebar QComboBox {{
    background: #F0EBE2;
    border: 1px solid {C.SB_BDR};
    border-radius: {r}px;
    color: {C.SB_TEXT};
    font-family: "{F.MONO}";
    font-size: {F.SZ_SM}pt;
}}
QFrame#sidebar QLineEdit:focus,
QFrame#sidebar QSpinBox:focus,
QFrame#sidebar QDoubleSpinBox:focus,
QFrame#sidebar QComboBox:focus {{
    border-color: {C.OLIVE};
    background: #FAF8F5;
}}

/* Filter pills */
QPushButton[filterpill="true"] {{
    height: 22px;
    padding: 0 9px;
    border: 1px solid {C.SB_BDR};
    border-radius: 99px;
    background: #E8E1D3;
    font-size: {F.SZ_BASE}pt;
    color: {C.SB_MID};
}}
QPushButton[filterpill="true"]:hover {{
    background: #F0EBE2;
    border-color: {C.BORDER_DK};
    color: {C.SB_TEXT};
}}
QPushButton[filterpill="true"]:pressed {{
    background: {C.BG_LOW};
    border-color: {C.EARTH};
    color: {C.SB_TEXT};
}}
QPushButton[filterpill="true"][active="true"] {{
    background: {C.SB_ACT};
    border-color: {C.SB_BDR};
    color: {C.SB_TEXT};
    font-weight: 600;
}}

/* Sidebar action buttons */
QPushButton[sbaction="true"] {{
    background: #E9E2D5;
    border: 1px solid {C.SB_BDR};
    border-radius: {r}px;
    padding: 6px 10px;
    font-size: {F.SZ_LG}pt;
    color: {C.SB_MID};
}}
QPushButton[sbaction="true"]:hover {{
    background: #F1EDE5;
    border-color: {C.BORDER_DK};
    color: {C.SB_TEXT};
}}
QPushButton[sbaction="true"]:pressed {{
    background: {C.BG_LOW};
    border-color: {C.EARTH};
    color: {C.SB_TEXT};
}}
QPushButton[sbaction="true"][primary="true"] {{
    background: {C.OLIVE};
    border-color: {C.OLIVE_DK};
    color: white;
    font-weight: 600;
}}
QPushButton[sbaction="true"][primary="true"]:hover {{
    background: {C.OLIVE_H};
}}
QPushButton[sbaction="true"][primary="true"]:pressed {{
    background: {C.OLIVE_DK};
    border-color: {C.OLIVE_DK};
}}

/* ════════════════════════════════════════
   SCROLL BARS
════════════════════════════════════════ */
QScrollBar:vertical {{
    background: transparent;
    width: 7px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {C.AMBER};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C.EARTH};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 7px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {C.AMBER};
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {C.EARTH};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ════════════════════════════════════════
   GENERIC PUSH BUTTON
════════════════════════════════════════ */
QPushButton {{
    background: #FFFDF8;
    border: 1px solid {C.BORDER_DK};
    border-radius: {r}px;
    padding: 4px 11px;
    font-size: {F.SZ_MD}pt;
    color: {C.TEXT};
}}
QPushButton:hover {{
    background: #FFFFFF;
    border-color: {C.EARTH};
    color: {C.TEXT};
}}
QPushButton:pressed {{
    background: {C.BG_RAISED};
    border-color: {C.EARTH};
}}
QPushButton:disabled {{
    opacity: 0.45;
    color: {C.TEXT_MUTED};
    background: {C.BG_RAISED};
    border-color: {C.BORDER};
}}

/* Primary button (olive) */
QPushButton[primary="true"] {{
    background: {C.OLIVE};
    border-color: {C.OLIVE_DK};
    color: white;
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{
    background: {C.OLIVE_H};
    border-color: {C.OLIVE};
}}
QPushButton[primary="true"]:pressed {{
    background: {C.OLIVE_DK};
}}

/* Danger button */
QPushButton[danger="true"] {{
    color: #a03020;
    border-color: rgba(160,48,32,0.28);
}}
QPushButton[danger="true"]:hover {{
    background: rgba(160,48,32,0.07);
}}

/* ════════════════════════════════════════
   LINE EDIT / SPIN BOX
════════════════════════════════════════ */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: #ffffff;
    border: 1px solid {C.BORDER_DK};
    border-radius: {r}px;
    padding: 2px 6px;
    font-size: {F.SZ_MD}pt;
    font-family: "{F.MONO}";
    color: {C.TEXT};
    selection-background-color: {C.OLIVE};
    selection-color: white;
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {C.EARTH};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {C.OLIVE};
    background: #ffffff;
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background: {C.BG_RAISED};
    color: {C.TEXT_MUTED};
    border-color: {C.BORDER};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 14px;
    border: none;
    background: transparent;
}}

/* ════════════════════════════════════════
   COMBO BOX
════════════════════════════════════════ */
QComboBox {{
    background: #ffffff;
    border: 1px solid {C.BORDER_DK};
    border-radius: {r}px;
    padding: 3px 22px 3px 7px;
    font-size: {F.SZ_MD}pt;
    color: {C.TEXT_MID};
    min-height: 22px;
}}
QComboBox:hover {{
    border-color: {C.EARTH};
    background: #ffffff;
}}
QComboBox:focus {{
    border-color: {C.OLIVE};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox::down-arrow {{
    image: url("{_arrow_url}");
    width: 10px;
    height: 6px;
}}
QComboBox QAbstractItemView {{
    background: {C.BG_RAISED};
    border: 1px solid {C.BORDER};
    border-radius: {r}px;
    selection-background-color: rgba(107,142,35,0.12);
    selection-color: {C.TEXT};
    outline: none;
}}

/* ════════════════════════════════════════
   CHECK BOX
════════════════════════════════════════ */
QCheckBox {{
    font-size: {F.SZ_MD}pt;
    color: {C.TEXT_MID};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1.5px solid {C.BORDER_DK};
    border-radius: 3px;
    background: #ffffff;
}}
QCheckBox::indicator:checked {{
    background: {C.OLIVE};
    border-color: {C.OLIVE_DK};
    image: none;
}}
QCheckBox::indicator:hover {{
    border-color: {C.OLIVE};
}}

/* ════════════════════════════════════════
   TABLE WIDGET
════════════════════════════════════════ */
QTableWidget, QTableView {{
    background: white;
    border: 1px solid {C.BORDER};
    border-radius: {r}px;
    gridline-color: rgba(212,196,168,0.4);
    font-size: {F.SZ_MD}pt;
    color: {C.TEXT};
    selection-background-color: rgba(107,142,35,0.08);
    selection-color: {C.TEXT};
    alternate-background-color: rgba(238,232,220,0.35);
}}
QTableWidget::item:hover, QTableView::item:hover {{
    background: rgba(212,196,168,0.15);
}}
QHeaderView::section {{
    background: {C.BG_RAISED};
    border: none;
    border-bottom: 2px solid {C.BORDER_DK};
    border-right: 1px solid {C.BORDER};
    padding: 5px 10px;
    font-size: {F.SZ_SM}pt;
    font-weight: 600;
    color: {C.TEXT_MID};
}}
QHeaderView::section:last {{
    border-right: none;
}}

/* ════════════════════════════════════════
   PROGRESS BAR
════════════════════════════════════════ */
QProgressBar {{
    background: #A28F77;
    border: 1px solid {C.ST_MUTED};
    border-radius: 2px;
    text-align: center;
    font-size: {F.SZ_XS}pt;
    color: {C.ST_TEXT};
}}
QProgressBar::chunk {{
    background: {C.OLIVE};
    border-radius: 2px;
}}

/* ════════════════════════════════════════
   TEXT EDIT
════════════════════════════════════════ */
QTextEdit {{
    background: white;
    border: 1px solid {C.BORDER};
    border-radius: {r}px;
    padding: 4px;
    font-family: "{F.MONO}";
    font-size: {F.SZ_SM}pt;
    color: {C.TEXT};
}}
QTextEdit:focus {{
    border-color: {C.OLIVE};
}}
QTextEdit:read-only {{
    background: {C.BG};
    border-color: {C.BORDER};
}}

/* ════════════════════════════════════════
   GROUP BOX
════════════════════════════════════════ */
QGroupBox {{
    background: transparent;
    border: 1px solid {C.BORDER};
    border-radius: {r}px;
    margin-top: 14px;
    padding-top: 12px;
    font-size: {F.SZ_SM}pt;
    font-weight: 600;
    color: {C.TEXT_MID};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    background: {C.BG_RAISED};
    border: 1px solid {C.BORDER};
    border-radius: 3px;
    left: 10px;
}}

/* ════════════════════════════════════════
   SPLITTER
════════════════════════════════════════ */
QSplitter {{
    background: transparent;
}}
QSplitter::handle {{
    background: {C.BORDER};
    border: none;
}}
QSplitter::handle:horizontal {{
    width: 1px;
    margin: 0;
}}
QSplitter::handle:vertical {{
    height: 1px;
    margin: 0;
}}
QSplitter::handle:hover {{
    background: {C.BORDER_DK};
}}
QSplitter#shell-splitter::handle {{
    background: {C.SB_BDR};
}}
QSplitter#shell-splitter::handle:horizontal {{
    width: 6px;
    margin: 0;
}}
QSplitter#shell-splitter::handle:hover {{
    background: {C.BORDER_DK};
}}

/* ════════════════════════════════════════
   TAB WIDGET (dataset tabs)
════════════════════════════════════════ */
QTabWidget::pane {{
    border: none;
    background: {C.BG};
}}
QTabBar {{
    background: {C.BG_RAISED};
    border-bottom: 1px solid {C.BORDER};
}}
QTabBar::tab {{
    background: transparent;
    border: 1px solid transparent;
    border-bottom: none;
    border-radius: {r}px {r}px 0 0;
    padding: 4px 10px;
    margin-right: 1px;
    margin-bottom: -1px;
    font-family: "{F.UI}";
    font-size: {F.SZ_BASE}pt;
    color: {C.TEXT_MUTED};
    min-height: {SZ.DS_TABBAR_H - 6}px;
    max-height: {SZ.DS_TABBAR_H - 2}px;
}}
QTabBar::tab:selected {{
    background: {C.BG};
    border-color: {C.BORDER};
    color: {C.TEXT};
    font-weight: 500;
}}
QTabBar::tab:hover:!selected {{
    background: {C.BG_LOW};
    color: {C.TEXT_MID};
    border-color: {C.BORDER};
}}
QTabBar::close-button {{
    subcontrol-position: right;
    width: 15px;
    height: 15px;
    border-radius: 7px;
    background: transparent;
}}
QTabBar::close-button:hover {{
    background: {C.BORDER};
}}
QTabBar QToolButton {{
    border: 1px solid transparent;
    background: transparent;
    color: {C.TEXT_MUTED};
    width: 20px;
    padding: 0;
    margin-bottom: 1px;
}}
QTabBar QToolButton:hover {{
    background: {C.BG_LOW};
    border-color: {C.BORDER};
    color: {C.TEXT};
}}

/* ════════════════════════════════════════
   TOOL TIP
════════════════════════════════════════ */
QToolTip {{
    background: #fffdf7;
    background-color: #fffdf7;
    border: 1px solid {C.OLIVE};
    border-radius: {r}px;
    color: {C.TEXT};
    font-size: {F.SZ_BASE}pt;
    padding: 6px 9px;
}}

/* ════════════════════════════════════════
   DIALOG
════════════════════════════════════════ */
QDialog {{
    background: {C.BG};
}}
QDialog QLabel#dialog-title {{
    font-size: {F.SZ_XL}pt;
    font-weight: 600;
    color: {C.TEXT};
}}

/* ════════════════════════════════════════
   PLOT WORKSPACE — Inner Toolbar
   Matches _shared.css .pw-tb / .pw-*
════════════════════════════════════════ */
QWidget#pw-toolbar {{
    background: {C.BG_RAISED};
    border-bottom: 1px solid {C.BORDER};
    min-height: {SZ.PLOT_INNER_TB_H}px;
    max-height: {SZ.PLOT_INNER_TB_H}px;
}}
QWidget#pw-toolbar QWidget,
QWidget#pw-toolbar QFrame,
QWidget#pw-toolbar QLabel {{
    background: transparent;
}}
/* Re-assert backgrounds for input widgets in plot toolbar (rgba(255,255,255,0.4)
   over #eee8dc = #F5F1EA). Same specificity (102) as blanket rule, placed after
   so cascade order wins. */
QWidget#pw-toolbar QComboBox,
QWidget#pw-toolbar QLineEdit,
QWidget#pw-toolbar QSpinBox,
QWidget#pw-toolbar QDoubleSpinBox {{
    background: #F5F1EA;
    border: 1px solid {C.BORDER};
    border-radius: {r}px;
    color: {C.TEXT_MID};
    font-size: {F.SZ_SM}pt;
}}

/* Segmented control container — clipping border so inner radii work */
QFrame#pw-seg {{
    background: transparent;
    border: 1px solid {C.BORDER};
    border-radius: {r}px;
    max-height: 24px;
}}
/* First segment: left rounded corners */
QPushButton[pw-seg="true"] {{
    background: #F5F1EA;
    border: none;
    border-right: 1px solid {C.BORDER};
    border-radius: 0;
    padding: 0 8px;
    min-height: 22px;
    max-height: 22px;
    font-size: {F.SZ_SM}pt;
    color: {C.TEXT_MID};
}}
QPushButton[pw-seg="true"]:first-child {{
    border-top-left-radius: {r - 1}px;
    border-bottom-left-radius: {r - 1}px;
}}
QPushButton[pw-seg="true"]:last-child {{
    border-right: none;
    border-top-right-radius: {r - 1}px;
    border-bottom-right-radius: {r - 1}px;
}}
QPushButton[pw-seg="true"][active="true"] {{
    background: rgba(107,142,35,0.12);
    color: {C.OLIVE};
    font-weight: 700;
}}
QPushButton[pw-seg="true"]:hover:!checked {{
    background: {C.TAN_H};
}}

/* Toggle check buttons (Grid, Legend, Zones, D-lines) */
QPushButton[pw-chk="true"] {{
    background: #F3EFE7;
    border: 1px solid {C.BORDER};
    border-radius: {r}px;
    padding: 0 7px;
    min-height: 22px;
    max-height: 22px;
    font-size: {F.SZ_SM}pt;
    color: {C.TEXT_MID};
}}
QPushButton[pw-chk="true"]:hover {{
    background: #F8F6F1;
}}
QPushButton[pw-chk="true"][active="true"] {{
    background: rgba(107,142,35,0.1);
    border-color: rgba(107,142,35,0.35);
    color: {C.OLIVE};
}}

/* Small action buttons (zoom, export, sidebar toggle) */
QPushButton[pw-btn="true"] {{
    background: #FFFDF8;
    border: 1px solid {C.BORDER_DK};
    border-radius: {r}px;
    padding: 0 7px;
    min-height: 22px;
    max-height: 22px;
    font-size: {F.SZ_SM}pt;
    color: {C.TEXT};
}}
QPushButton[pw-btn="true"]:hover {{
    background: #FFFFFF;
    border-color: {C.EARTH};
}}
QPushButton[pw-btn="true"]:pressed {{
    background: {C.BG_RAISED};
    border-color: {C.EARTH};
}}

/* Style / unit dropdowns inside plot toolbar and sidebar */
QComboBox#pw-style-sel,
QComboBox#pw-more-plots-sel {{
    min-height: 22px;
    max-height: 22px;
    padding: 0 20px 0 6px;
    font-size: {F.SZ_SM}pt;
    background: #F5F1EA;
    border: 1px solid {C.BORDER};
    border-radius: {r}px;
    color: {C.TEXT_MID};
}}
QComboBox#pw-style-sel:hover,
QComboBox#pw-more-plots-sel:hover {{
    background: #F8F6F1;
    border-color: {C.BORDER_DK};
}}
QComboBox#pw-more-plots-sel {{
    min-width: 118px;
    background: #F7F3EB;
}}
QComboBox#pw-style-sel::drop-down,
QComboBox#pw-more-plots-sel::drop-down {{
    width: 20px;
    border: none;
    background: transparent;
}}
QComboBox#pw-style-sel QAbstractItemView,
QComboBox#pw-more-plots-sel QAbstractItemView {{
    background: #FBF8F2;
    border: 1px solid {C.BORDER};
    border-radius: {r}px;
    color: {C.TEXT};
    outline: none;
    padding: 4px;
    selection-background-color: rgba(107,142,35,0.12);
    selection-color: {C.TEXT};
}}
QComboBox#pw-style-sel QAbstractItemView::item,
QComboBox#pw-more-plots-sel QAbstractItemView::item {{
    min-height: 22px;
    padding: 4px 8px;
    border-radius: {r - 1}px;
    background: transparent;
}}
QComboBox#pw-style-sel QAbstractItemView::item:hover,
QComboBox#pw-more-plots-sel QAbstractItemView::item:hover {{
    background: rgba(107,142,35,0.08);
}}
/* Separator line in plot toolbar */
QFrame#pw-sep {{
    background: {C.BORDER};
    max-width: 1px;
    min-width: 1px;
    max-height: 16px;
    min-height: 16px;
    margin: 0 3px;
}}

/* ════════════════════════════════════════
   PLOT WORKSPACE — Inner Sidebar
   Matches _shared.css .pw-side / .pws-*
════════════════════════════════════════ */
QFrame#pw-sidebar {{
    background: {C.PW_SB};
    border: none;
    border-right: 1px solid {C.BORDER};
}}
QFrame#pw-sidebar QWidget {{
    background: transparent;
}}
QFrame#pw-sidebar QLabel {{
    background: transparent;
}}
/* Input widgets in plot sidebar — warm tint (rgba(255,255,255,0.6) over #ece5d8) */
QFrame#pw-sidebar QComboBox,
QFrame#pw-sidebar QSpinBox,
QFrame#pw-sidebar QDoubleSpinBox {{
    background: #F7F5EF;
    border: 1px solid {C.BORDER};
    border-radius: {r}px;
    color: {C.TEXT_MID};
    font-size: {F.SZ_SM}pt;
}}
/* Section header bands */
QLabel[pws-sect="true"] {{
    background: #F1ECE3;
    border-bottom: 1px solid rgba(212,196,168,0.6);
    padding: 6px 11px 5px 11px;
    font-size: {F.SZ_SM}pt;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: {C.TEXT_MUTED};
}}
/* Row labels */
QLabel[pws-lbl="true"] {{
    font-size: {F.SZ_SM}pt;
    color: {C.TEXT_MID};
    background: transparent;
}}
/* Axis input fields */
QFrame#pw-sidebar QLineEdit[pws-in="true"] {{
    max-width: 56px;
    min-height: 20px;
    max-height: 20px;
    background: #F7F5EF;
    border: 1px solid {C.BORDER};
    border-radius: 3px;
    font-family: "{F.MONO}";
    font-size: {F.SZ_SM}pt;
    color: {C.TEXT};
    padding: 0 4px;
}}
QFrame#pw-sidebar QLineEdit[pws-in="true"]:focus {{
    border-color: {C.OLIVE};
    background: #F7F5EF;
}}

/* Sidebar toggle handle on chart left edge */
QPushButton#pw-toggle-handle {{
    background: {C.BORDER};
    border: 1px solid {C.BORDER_DK};
    border-radius: 7px;
    min-width: 16px;
    max-width: 16px;
    min-height: 40px;
    max-height: 40px;
    padding: 0;
}}
QPushButton#pw-toggle-handle:hover {{
    background: {C.TAN};
}}

"""
