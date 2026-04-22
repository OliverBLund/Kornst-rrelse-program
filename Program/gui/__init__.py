"""GUI package for the Grain Size Analysis application."""

__all__ = ["MainWindow", "ControlPanel", "PlotWidget"]


def __getattr__(name):
    """Load heavy GUI classes lazily to avoid package import cycles."""
    if name == "MainWindow":
        from .main_window import MainWindow
        return MainWindow
    if name == "ControlPanel":
        from .control_panel import ControlPanel
        return ControlPanel
    if name == "PlotWidget":
        from .plot_widget import PlotWidget
        return PlotWidget
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

