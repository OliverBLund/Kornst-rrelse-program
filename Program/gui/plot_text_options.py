"""Shared plot title and axis-label option model/dialog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QFont

from .theme import C, icon


DEFAULT_X_LABEL = "Grain Diameter (mm)"
DEFAULT_Y_LABEL = "Cumulative % Passing"
PLOT_TEXT_CONTEXT_KEYS = (
    "show_title",
    "plot_title",
    "show_x_label",
    "plot_x_label",
    "show_y_label",
    "plot_y_label",
)


@dataclass(frozen=True)
class PlotTextOptions:
    """Text visibility and labels for a single grain-size plot."""

    show_title: bool = True
    title: str = ""
    show_x_label: bool = True
    x_label: str = DEFAULT_X_LABEL
    show_y_label: bool = True
    y_label: str = DEFAULT_Y_LABEL


def default_plot_title(sample_name: str) -> str:
    return f"Grain Size Distribution: {sample_name}"


def plot_text_options_from_context(
    sample_name: str,
    context: Optional[Dict[str, Any]] = None,
) -> PlotTextOptions:
    context = context or {}
    return PlotTextOptions(
        show_title=context.get("show_title", True),
        title=context.get("plot_title") or default_plot_title(sample_name),
        show_x_label=context.get("show_x_label", True),
        x_label=context.get("plot_x_label") or DEFAULT_X_LABEL,
        show_y_label=context.get("show_y_label", True),
        y_label=context.get("plot_y_label") or DEFAULT_Y_LABEL,
    )


def plot_text_options_to_context(options: PlotTextOptions) -> Dict[str, Any]:
    return {
        "show_title": options.show_title,
        "plot_title": options.title,
        "show_x_label": options.show_x_label,
        "plot_x_label": options.x_label,
        "show_y_label": options.show_y_label,
        "plot_y_label": options.y_label,
    }


def plot_text_renderer_kwargs(
    sample_name: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return plot_text_options_to_renderer_kwargs(
        plot_text_options_from_context(sample_name, context)
    )


def plot_text_options_to_renderer_kwargs(options: PlotTextOptions) -> Dict[str, Any]:
    return {
        "show_title": options.show_title,
        "title": options.title,
        "show_x_label": options.show_x_label,
        "x_label": options.x_label,
        "show_y_label": options.show_y_label,
        "y_label": options.y_label,
    }


class PlotTextOptionsDialog(QDialog):
    """Shared dialog for title and axis-label visibility/text."""

    def __init__(self, sample_name: str, options: PlotTextOptions, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Plot Text - {sample_name}")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        heading = QHBoxLayout()
        heading_icon = QLabel()
        heading_icon.setPixmap(icon("fa6s.pen-ruler", C.OLIVE, 16).pixmap(QSize(16, 16)))
        heading.addWidget(heading_icon)
        heading_label = QLabel("Plot title and axis labels")
        heading_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        heading.addWidget(heading_label)
        heading.addStretch()
        layout.addLayout(heading)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

        self.show_title_cb = QCheckBox("Show")
        self.show_title_cb.setChecked(options.show_title)
        self.title_edit = QLineEdit(options.title)
        form.addRow("Title", self._row(self.show_title_cb, self.title_edit))

        self.show_x_label_cb = QCheckBox("Show")
        self.show_x_label_cb.setChecked(options.show_x_label)
        self.x_label_edit = QLineEdit(options.x_label)
        form.addRow("X-axis label", self._row(self.show_x_label_cb, self.x_label_edit))

        self.show_y_label_cb = QCheckBox("Show")
        self.show_y_label_cb.setChecked(options.show_y_label)
        self.y_label_edit = QLineEdit(options.y_label)
        form.addRow("Y-axis label", self._row(self.show_y_label_cb, self.y_label_edit))

        layout.addLayout(form)

        for checkbox, editor in (
            (self.show_title_cb, self.title_edit),
            (self.show_x_label_cb, self.x_label_edit),
            (self.show_y_label_cb, self.y_label_edit),
        ):
            checkbox.toggled.connect(editor.setEnabled)
            editor.setEnabled(checkbox.isChecked())

        note = QLabel("These options are shared by plot previews and exported plots.")
        note.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 9px;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _row(checkbox: QCheckBox, editor: QLineEdit) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(checkbox)
        layout.addWidget(editor, 1)
        return row

    def options(self) -> PlotTextOptions:
        return PlotTextOptions(
            show_title=self.show_title_cb.isChecked(),
            title=self.title_edit.text().strip(),
            show_x_label=self.show_x_label_cb.isChecked(),
            x_label=self.x_label_edit.text().strip() or DEFAULT_X_LABEL,
            show_y_label=self.show_y_label_cb.isChecked(),
            y_label=self.y_label_edit.text().strip() or DEFAULT_Y_LABEL,
        )


class GlobalPlotStylingPlaceholderDialog(QDialog):
    """Placeholder dialog for a future shared plot-styling workflow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Plot Styling")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        heading = QHBoxLayout()
        heading_icon = QLabel()
        heading_icon.setPixmap(
            icon("fa6s.brush", C.OLIVE, 16).pixmap(QSize(16, 16))
        )
        heading.addWidget(heading_icon)
        heading_label = QLabel("Global plot styling")
        heading_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        heading.addWidget(heading_label)
        heading.addStretch()
        layout.addLayout(heading)

        intro = QLabel(
            "This placeholder reserves space for a future workflow that will "
            "let you standardize plot presentation across the whole program."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        body = QLabel(
            "Planned scope:\n"
            "\n"
            "- Apply the current plot style to every dataset tab\n"
            "- Standardize legend, grid, markers, D-lines, and fill behavior\n"
            "- Apply shared title and axis-label rules across datasets\n"
            "- Keep exported plots and report plots aligned with the same defaults\n"
            "\n"
            "This is intentionally a placeholder for the next development phase, "
            "so testers know the feature is planned without introducing unfinished behavior."
        )
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {C.TEXT_MID};")
        layout.addWidget(body)

        note = QLabel(
            "For now, plot customizations remain per dataset tab and continue to flow "
            "through the shared plot context used by export and reporting."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; "
            f"border-radius: 6px; padding: 10px; color: {C.TEXT};"
        )
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
