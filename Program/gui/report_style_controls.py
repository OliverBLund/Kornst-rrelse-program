"""Shared global plot-style controls for the Report and Export tabs.

Both tabs expose the SAME "restyle once" controls — a style preset, a colour
palette, and a Customize dialog (typography + legend) — all reading and writing
the single persisted store in :mod:`gui.report_plot_style`.  Centralised here so
the two tabs never drift: change the look once and every report/export plot
follows.

``ReportStyleControls`` is a compact ``QWidget`` (preset combo + palette combo +
Customize button) that emits ``changed`` after any edit so the host tab can
refresh a live preview.  ``open_report_style_dialog`` is the typography/legend
override panel, shared verbatim by both tabs.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .plot_constants import PALETTE_NAMES
from .plot_styles import get_available_style_names, get_style
from .report_plot_style import (
    clear_report_style_overrides,
    get_report_palette,
    get_report_style_overrides,
    get_report_style_preset,
    resolve_report_style,
    set_report_palette,
    set_report_style_overrides,
    set_report_style_preset,
)
from .theme import C, F, opaque_combo_qss


def _custom_overrides_for_preset(chosen: dict) -> dict:
    """Keep only values that differ from the currently selected preset."""
    preset = get_style(get_report_style_preset())
    return {
        field: value
        for field, value in chosen.items()
        if value != getattr(preset, field)
    }


def open_report_style_dialog(parent: Optional[QWidget] = None) -> bool:
    """Compact presentation override panel for the global report style.

    Returns ``True`` when the user saved or reset (i.e. the persisted style may
    have changed), ``False`` on cancel.
    """
    from .sidebar_controls import (
        PlotStyleControlSections,
    )

    style = resolve_report_style()
    dlg = QDialog(parent.window() if parent is not None else None)
    dlg.setWindowTitle("Report Plot Style")
    dlg.resize(420, 560)
    dlg.setMinimumWidth(380)
    root = QVBoxLayout(dlg)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(4)

    intro = QLabel(
        f"Custom tweaks on top of the '{get_report_style_preset()}' preset. "
        "Applied to every report and export plot."
    )
    intro.setWordWrap(True)
    intro.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SZ_XS}pt;")
    root.addWidget(intro)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    section_host = QWidget()
    section_host.setStyleSheet("background: transparent;")
    section_layout = QVBoxLayout(section_host)
    section_layout.setContentsMargins(0, 4, 0, 4)
    section_layout.setSpacing(6)
    scroll.setWidget(section_host)
    root.addWidget(scroll, 1)

    style_sections = PlotStyleControlSections(style)
    section_layout.addWidget(style_sections)
    section_layout.addStretch(1)

    buttons = QDialogButtonBox()
    reset_btn = buttons.addButton("Reset to preset", QDialogButtonBox.ButtonRole.ResetRole)
    buttons.addButton(QDialogButtonBox.StandardButton.Save)
    buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
    root.addWidget(buttons)

    result = {"changed": False}

    def on_reset():
        clear_report_style_overrides()
        result["changed"] = True
        dlg.reject()

    def on_save():
        chosen = style_sections.values()
        set_report_style_overrides(_custom_overrides_for_preset(chosen))
        result["changed"] = True
        dlg.accept()

    reset_btn.clicked.connect(on_reset)
    buttons.accepted.connect(on_save)
    buttons.rejected.connect(dlg.reject)
    dlg.exec()
    return result["changed"]


class ReportStyleControls(QWidget):
    """Preset + palette combos and a Customize button over the global store.

    Emits :pyattr:`changed` after any edit (preset, palette, or a saved/reset
    Customize dialog) so the host can re-render a preview.  Stateless beyond the
    widgets — the source of truth is the persisted ``report_plot_style`` store.
    """

    changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        # ── Preset + Customize row ──────────────────────────────
        preset_row = QWidget()
        preset_row.setStyleSheet("background: transparent;")
        play = QHBoxLayout(preset_row)
        play.setContentsMargins(9, 2, 9, 2)
        play.setSpacing(7)
        play.addWidget(self._label("Preset"))

        self._preset_combo = QComboBox()
        self._preset_combo.addItems(get_available_style_names())
        self._select_text(self._preset_combo, get_report_style_preset())
        # Set the opaque-popup QSS on the combo itself so the transparent panel
        # background can't bleed into the dropdown list (see opaque_combo_qss).
        self._preset_combo.setStyleSheet(opaque_combo_qss())
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        play.addWidget(self._preset_combo, 1)

        self._customize_btn = QPushButton("Customize…")
        self._customize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._customize_btn.clicked.connect(self._on_customize)
        play.addWidget(self._customize_btn)
        root.addWidget(preset_row)

        # ── Palette row ─────────────────────────────────────────
        palette_row = QWidget()
        palette_row.setStyleSheet("background: transparent;")
        qlay = QHBoxLayout(palette_row)
        qlay.setContentsMargins(9, 2, 9, 2)
        qlay.setSpacing(7)
        qlay.addWidget(self._label("Palette"))

        self._palette_combo = QComboBox()
        self._palette_combo.addItems(PALETTE_NAMES)
        self._palette_combo.setStyleSheet(opaque_combo_qss())
        self._palette_combo.setToolTip(
            "Colours for multi-series comparison plots in reports and exports.\n"
            "Categorical keeps the program's default palette; the others sample a "
            "perceptually-uniform colormap."
        )
        self._select_text(self._palette_combo, get_report_palette())
        self._palette_combo.currentTextChanged.connect(self._on_palette_changed)
        qlay.addWidget(self._palette_combo, 1)
        root.addWidget(palette_row)

    # ── helpers ────────────────────────────────────────────────
    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f'color: {C.TEXT_MID}; font-family: "{F.UI}"; font-size: {F.SZ_MD}pt; '
            f'background: transparent;'
        )
        return lbl

    @staticmethod
    def _select_text(combo: QComboBox, text: str) -> None:
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _on_preset_changed(self, name: str) -> None:
        set_report_style_preset(name)
        clear_report_style_overrides()
        self.changed.emit()

    def _on_palette_changed(self, name: str) -> None:
        set_report_palette(name)
        self.changed.emit()

    def _on_customize(self) -> None:
        if open_report_style_dialog(self):
            self.changed.emit()

    def sync_from_store(self) -> None:
        """Refresh both combos from the persisted store (e.g. another tab edited it)."""
        for combo, value in (
            (self._preset_combo, get_report_style_preset()),
            (self._palette_combo, get_report_palette()),
        ):
            combo.blockSignals(True)
            self._select_text(combo, value)
            combo.blockSignals(False)
