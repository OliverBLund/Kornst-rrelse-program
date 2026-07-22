"""Workspace K-method selection dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from method_registry import DEFAULT_METHOD_ORDER, normalize_method_selection
from qt_chrome import FramelessDialogBase
from gui.dialog_chrome import make_dialog_header
from gui.theme import C, F, SZ


class MethodSelectionDialog(FramelessDialogBase):
    """Choose the workspace-wide active K methods."""

    def __init__(
        self,
        *,
        selected_methods: list[str] | tuple[str, ...],
        available_methods: list[str] | tuple[str, ...] = DEFAULT_METHOD_ORDER,
        parent=None,
    ) -> None:
        super().__init__(parent, default_mode="auto")
        self.setWindowTitle("Choose K Methods")
        self.setMinimumSize(520, 520)
        self._available_methods = tuple(available_methods)
        self._default_methods = tuple(available_methods)
        self._checks: dict[str, QCheckBox] = {}
        self._selected_methods = normalize_method_selection(
            selected_methods, available_methods=self._available_methods
        )
        self._build_ui()
        self._set_checked_methods(self._selected_methods)

    def selected_methods(self) -> tuple[str, ...]:
        """Return selected methods in canonical order."""
        return normalize_method_selection(
            [method for method, checkbox in self._checks.items() if checkbox.isChecked()],
            available_methods=self._available_methods,
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header_widget = make_dialog_header(
            "Choose K Methods",
            "Workspace method set | affects Results, plots, comparison, reports, and export",
            fa_icon="fa6s.sliders",
            close_fn=self.reject,
        )
        root.addWidget(self._header_widget)

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(14, 14, 14, 12)
        body_lay.setSpacing(12)

        summary = QFrame()
        summary.setStyleSheet(
            f"QFrame {{ background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; }}"
        )
        summary_lay = QVBoxLayout(summary)
        summary_lay.setContentsMargins(12, 10, 12, 10)
        summary_lay.setSpacing(3)
        title = QLabel("Selected methods are used everywhere the program displays or exports K results.")
        title.setWordWrap(True)
        title.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_MD}pt; font-weight: 700; "
            f"color: {C.TEXT}; background: transparent;"
        )
        self._summary_lbl = QLabel("")
        self._summary_lbl.setStyleSheet(
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; color: {C.TEXT_MUTED}; "
            f"background: transparent;"
        )
        summary_lay.addWidget(title)
        summary_lay.addWidget(self._summary_lbl)
        body_lay.addWidget(summary)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        action_tooltips = {
            "Select all": "Activate every available K method across the workspace.",
            "Clear": "Clear the selection; Apply remains unavailable until at least one method is active.",
            "Restore default": "Restore the complete default workspace K-method set.",
        }
        for label, callback in (
            ("Select all", self._select_all),
            ("Clear", self._clear_all),
            ("Restore default", self._restore_default),
        ):
            btn = QPushButton(label)
            btn.setToolTip(action_tooltips[label])
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: {C.BG_RAISED}; border: 1px solid {C.BORDER}; "
                f"border-radius: {SZ.BORDER_RADIUS}px; color: {C.TEXT_MID}; "
                f"padding: 0 10px; font-size: {F.SZ_SM}pt; }}"
                f"QPushButton:hover {{ background: {C.BG_LOW}; border-color: {C.BORDER_DK}; }}"
            )
            btn.clicked.connect(callback)
            action_row.addWidget(btn)
        action_row.addStretch(1)
        body_lay.addLayout(action_row)

        grid_frame = QFrame()
        grid_frame.setStyleSheet(
            f"QFrame {{ background: white; border: 1px solid {C.BORDER}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; }}"
        )
        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(7)
        for index, method in enumerate(self._available_methods):
            checkbox = QCheckBox(method)
            checkbox.setToolTip(
                f"Toggle {method} in the workspace-wide active method set used by Results, plots, comparison, reports, and exports."
            )
            checkbox.setStyleSheet(
                f"QCheckBox {{ background: transparent; color: {C.TEXT}; "
                f"font-family: '{F.UI}'; font-size: {F.SZ_MD}pt; }}"
                f"QCheckBox::indicator {{ width: 15px; height: 15px; }}"
            )
            checkbox.stateChanged.connect(self._sync_state)
            self._checks[method] = checkbox
            grid.addWidget(checkbox, index // 2, index % 2)
        body_lay.addWidget(grid_frame, 1)

        self._warning_lbl = QLabel("Select at least one method.")
        self._warning_lbl.setStyleSheet(
            f"font-family: '{F.UI}'; font-size: {F.SZ_SM}pt; color: {C.LED_ERR}; "
            f"background: transparent;"
        )
        body_lay.addWidget(self._warning_lbl)

        root.addWidget(body, 1)

        footer = QWidget()
        footer.setStyleSheet(
            f"background: {C.BG_RAISED}; border-top: 1px solid {C.BORDER};"
        )
        footer_lay = QHBoxLayout(footer)
        footer_lay.setContentsMargins(14, 8, 14, 8)
        footer_lay.addStretch(1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(28)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px; "
            f"background: {C.BG}; color: {C.TEXT_MID}; padding: 0 14px; font-size: {F.SZ_LG}pt; }}"
            f"QPushButton:hover {{ background: {C.BG_RAISED}; border-color: {C.BORDER_DK}; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        footer_lay.addWidget(cancel_btn)

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setFixedHeight(28)
        self._apply_btn.setStyleSheet(
            f"QPushButton {{ background: {C.OLIVE}; border: 1px solid {C.OLIVE_DK}; "
            f"border-radius: {SZ.BORDER_RADIUS}px; color: white; font-weight: 700; "
            f"padding: 0 16px; font-size: {F.SZ_LG}pt; }}"
            f"QPushButton:hover {{ background: {C.OLIVE_H}; }}"
            f"QPushButton:disabled {{ background: {C.BORDER}; border-color: {C.BORDER_DK}; "
            f"color: {C.TEXT_MUTED}; }}"
        )
        self._apply_btn.clicked.connect(self.accept)
        footer_lay.addWidget(self._apply_btn)
        root.addWidget(footer)

        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )
        self._sync_state()

    def _set_checked_methods(self, methods: tuple[str, ...]) -> None:
        selected = set(methods)
        for method, checkbox in self._checks.items():
            checkbox.setChecked(method in selected)
        self._sync_state()

    def _select_all(self) -> None:
        self._set_checked_methods(tuple(self._available_methods))

    def _clear_all(self) -> None:
        self._set_checked_methods(())

    def _restore_default(self) -> None:
        self._set_checked_methods(self._default_methods)

    def _sync_state(self, *_args) -> None:
        count = sum(1 for checkbox in self._checks.values() if checkbox.isChecked())
        total = len(self._available_methods)
        self._summary_lbl.setText(f"{count} / {total} active methods")
        has_selection = count > 0
        self._warning_lbl.setVisible(not has_selection)
        self._apply_btn.setEnabled(has_selection)
