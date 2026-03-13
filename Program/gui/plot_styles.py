"""
Plot styling system with preset templates for consistent visualization
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class PlotStyle:
    """
    Container for all plot styling parameters
    """
    # Name and description
    name: str
    description: str

    # Main data curve
    curve_color: str
    curve_linewidth: float
    curve_marker: str
    curve_markersize: float
    curve_markeredgecolor: str
    curve_markeredgewidth: float

    # D-value lines
    d10_color: str
    d30_color: str
    d60_color: str
    d10_line_style: str
    d30_line_style: str
    d60_line_style: str
    d_line_width: float
    d_line_alpha: float

    # Grid
    grid_show: bool
    grid_color: str
    grid_alpha: float
    grid_linestyle: str
    grid_linewidth: float

    # Typography
    title_fontsize: int
    title_fontweight: str
    label_fontsize: int
    tick_fontsize: int
    legend_fontsize: int
    font_family: str

    # Legend
    legend_loc: str
    legend_framealpha: float
    legend_edgecolor: str

    # Figure
    figure_facecolor: str
    axes_facecolor: str

    # K-value bar chart colors
    use_method_specific_colors: bool  # If True, use colorful method colors; if False, use unified colors
    k_bar_valid_color: str  # Color for valid K calculations (when not using method-specific)
    k_bar_flagged_color: str  # Color for flagged/error calculations

    # Misc
    show_minor_grid: bool
    minor_grid_alpha: float


# Preset style templates

PROFESSIONAL_STYLE = PlotStyle(
    name="Professional",
    description="Clean, publication-ready style with professional colors",

    # Main curve - Steel blue that complements the earthy UI palette
    curve_color="#2b5797",
    curve_linewidth=2.0,
    curve_marker="o",
    curve_markersize=4,
    curve_markeredgecolor="white",
    curve_markeredgewidth=0.8,

    # D-value lines - warm but distinct
    d10_color="#b83232",  # Muted red
    d30_color="#2e6b30",  # Forest green
    d60_color="#5c3d8f",  # Muted purple
    d10_line_style="--",
    d30_line_style="--",
    d60_line_style="--",
    d_line_width=1.2,
    d_line_alpha=0.70,

    # Grid - warm, matches --border (#d4c4a8)
    grid_show=True,
    grid_color="#d4c4a8",
    grid_alpha=0.6,
    grid_linestyle="-",
    grid_linewidth=0.5,

    # Typography - matches theme font stack
    title_fontsize=12,
    title_fontweight="600",
    label_fontsize=11,
    tick_fontsize=10,
    legend_fontsize=9,
    font_family="Source Sans 3",

    # Legend - upper left, warm frame
    legend_loc="upper left",
    legend_framealpha=0.92,
    legend_edgecolor="#d4c4a8",

    # Figure colors - match C.BG / white axes
    figure_facecolor="#f5f5f0",
    axes_facecolor="#ffffff",

    # K-value bar chart
    use_method_specific_colors=True,
    k_bar_valid_color="#2b5797",
    k_bar_flagged_color="#b83232",

    # Minor grid
    show_minor_grid=True,
    minor_grid_alpha=0.18,
)


PRESENTATION_STYLE = PlotStyle(
    name="Presentation",
    description="Bold style optimized for slides and presentations",

    # Main curve - Bright, highly visible
    curve_color="#0066cc",
    curve_linewidth=3.5,
    curve_marker="o",
    curve_markersize=8,
    curve_markeredgecolor="white",
    curve_markeredgewidth=1.5,

    # D-value lines - Bright, bold colors
    d10_color="#ff3333",  # Bright red
    d30_color="#33cc33",  # Bright green
    d60_color="#9933ff",  # Bright purple
    d10_line_style="--",
    d30_line_style="--",
    d60_line_style="--",
    d_line_width=2.5,
    d_line_alpha=0.85,

    # Grid - Bold and clear
    grid_show=True,
    grid_color="#999999",
    grid_alpha=0.5,
    grid_linestyle="-",
    grid_linewidth=1.0,

    # Typography - Large, bold for visibility
    title_fontsize=16,
    title_fontweight="bold",
    label_fontsize=14,
    tick_fontsize=12,
    legend_fontsize=11,
    font_family="DejaVu Sans",

    # Legend - Prominent
    legend_loc="upper left",
    legend_framealpha=1.0,
    legend_edgecolor="#666666",

    # Figure colors - High contrast
    figure_facecolor="#f5f5f5",
    axes_facecolor="white",

    # K-value bar chart - use colorful method-specific colors for presentations
    use_method_specific_colors=True,
    k_bar_valid_color="#0066cc",
    k_bar_flagged_color="#ff3333",

    # Minor grid - Less important for presentations
    show_minor_grid=False,
    minor_grid_alpha=0.15,
)


MINIMALIST_STYLE = PlotStyle(
    name="Minimalist",
    description="Clean, simple style with minimal visual elements",

    # Main curve - Dark gray, elegant
    curve_color="#333333",
    curve_linewidth=2.0,
    curve_marker="",  # No markers
    curve_markersize=0,
    curve_markeredgecolor="none",
    curve_markeredgewidth=0,

    # D-value lines - Subtle monochrome with distinct styles
    d10_color="#666666",
    d30_color="#888888",
    d60_color="#555555",
    d10_line_style="--",  # Dashed
    d30_line_style="-",   # Solid
    d60_line_style=":",   # Dotted
    d_line_width=1.8,     # Thicker for visibility
    d_line_alpha=0.7,

    # Grid - Very subtle
    grid_show=True,
    grid_color="#e0e0e0",
    grid_alpha=0.3,
    grid_linestyle="-",
    grid_linewidth=0.5,

    # Typography - Simple, minimal
    title_fontsize=12,
    title_fontweight="normal",
    label_fontsize=10,
    tick_fontsize=9,
    legend_fontsize=8,
    font_family="DejaVu Sans",

    # Legend - Minimal frame
    legend_loc="upper left",
    legend_framealpha=0.7,
    legend_edgecolor="#dddddd",

    # Figure colors - Clean white
    figure_facecolor="white",
    axes_facecolor="white",

    # K-value bar chart - MINIMALIST: use unified monochrome colors
    use_method_specific_colors=False,  # Key difference!
    k_bar_valid_color="#666666",  # Dark gray for valid calculations
    k_bar_flagged_color="#cccccc",  # Light gray for flagged/errors

    # Minor grid - Off for minimalism
    show_minor_grid=False,
    minor_grid_alpha=0.1,
)


CLASSIC_STYLE = PlotStyle(
    name="Classic",
    description="Traditional geotechnical engineering style",

    # Main curve - Classic blue
    curve_color="#0000ff",
    curve_linewidth=2.0,
    curve_marker="o",
    curve_markersize=4,
    curve_markeredgecolor="blue",
    curve_markeredgewidth=0.5,

    # D-value lines - Traditional primary colors
    d10_color="#ff0000",  # Pure red
    d30_color="#00ff00",  # Pure green
    d60_color="#800080",  # Pure purple
    d10_line_style="--",
    d30_line_style="--",
    d60_line_style="--",
    d_line_width=1.0,
    d_line_alpha=0.7,

    # Grid - Traditional look
    grid_show=True,
    grid_color="#d3d3d3",
    grid_alpha=0.35,
    grid_linestyle="--",
    grid_linewidth=0.8,

    # Typography - Traditional sizing
    title_fontsize=12,
    title_fontweight="bold",
    label_fontsize=10,
    tick_fontsize=9,
    legend_fontsize=9,
    font_family="DejaVu Sans",

    # Legend - Traditional placement
    legend_loc="best",
    legend_framealpha=0.8,
    legend_edgecolor="#999999",

    # Figure colors - Traditional off-white
    figure_facecolor="#fafafa",
    axes_facecolor="#ffffff",

    # K-value bar chart - use colorful method-specific colors (traditional)
    use_method_specific_colors=True,
    k_bar_valid_color="#0000ff",  # Classic blue
    k_bar_flagged_color="#ff0000",  # Classic red

    # Minor grid
    show_minor_grid=True,
    minor_grid_alpha=0.15,
)


# Dictionary of all available styles
AVAILABLE_STYLES: Dict[str, PlotStyle] = {
    "Professional": PROFESSIONAL_STYLE,
    "Presentation": PRESENTATION_STYLE,
    "Minimalist": MINIMALIST_STYLE,
    "Classic": CLASSIC_STYLE,
}


def get_style(style_name: str) -> PlotStyle:
    """Get a plot style by name, defaults to Professional if not found"""
    return AVAILABLE_STYLES.get(style_name, PROFESSIONAL_STYLE)


def get_available_style_names():
    """Get list of all available style names"""
    return list(AVAILABLE_STYLES.keys())
