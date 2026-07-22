"""Persisted startup and display preferences."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gui.dialog_chrome import make_dialog_footer, make_dialog_header
from gui.theme import C, F
from qt_chrome.frameless_dialog_base import FramelessDialogBase


class ApplicationSettingsDialog(FramelessDialogBase):
    """Compact, cardless editor for application-level preferences."""

    def __init__(self, show_welcome_on_startup: bool, ui_font_bump: int = 1, parent=None):
        super().__init__(parent, default_mode="auto")
        self._show_welcome_on_startup = bool(show_welcome_on_startup)
        self._ui_font_bump = max(0, min(1, int(ui_font_bump)))
        self.setWindowTitle("Settings")
        self.setMinimumSize(540, 440)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._header_widget = make_dialog_header(
            "Settings",
            "Startup and display preferences",
            fa_icon="fa6s.gear",
            close_fn=self.reject,
        )
        root.addWidget(self._header_widget)

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(20, 18, 20, 20)
        body_lay.setSpacing(10)

        body_lay.addWidget(self._section_heading("STARTUP"))
        startup_title = QLabel("Home screen")
        startup_title.setStyleSheet(self._title_style())
        body_lay.addWidget(startup_title)
        startup_note = QLabel(
            "Choose whether Home is shown when the application starts. "
            "This never interrupts or resets an active workspace."
        )
        startup_note.setWordWrap(True)
        startup_note.setStyleSheet(self._note_style())
        body_lay.addWidget(startup_note)

        self.show_welcome_checkbox = QCheckBox("Show Home on startup")
        self.show_welcome_checkbox.setChecked(self._show_welcome_on_startup)
        self.show_welcome_checkbox.setStyleSheet(
            f"QCheckBox {{ color: {C.TEXT}; font-size: {F.SZ_MD}pt;"
            " spacing: 8px; background: transparent; }"
            "QCheckBox::indicator { width: 16px; height: 16px; }"
        )
        body_lay.addWidget(self.show_welcome_checkbox)
        body_lay.addSpacing(4)
        body_lay.addWidget(self._divider())
        body_lay.addSpacing(4)

        body_lay.addWidget(self._section_heading("DISPLAY"))
        display_title = QLabel("Interface text size")
        display_title.setStyleSheet(self._title_style())
        body_lay.addWidget(display_title)
        display_note = QLabel(
            "Select a consistent text-size preset for the complete interface."
        )
        display_note.setWordWrap(True)
        display_note.setStyleSheet(self._note_style())
        body_lay.addWidget(display_note)

        size_row = QWidget()
        size_row.setStyleSheet("background: transparent;")
        size_lay = QHBoxLayout(size_row)
        size_lay.setContentsMargins(0, 2, 0, 2)
        size_lay.setSpacing(12)
        size_label = QLabel("Text size")
        size_label.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_MD}pt; background: transparent;"
        )
        size_lay.addWidget(size_label)
        size_lay.addStretch(1)
        self.text_size_combo = QComboBox()
        self.text_size_combo.addItem("Normal", 0)
        self.text_size_combo.addItem("Large (+1 pt)", 1)
        current_index = self.text_size_combo.findData(self._ui_font_bump)
        self.text_size_combo.setCurrentIndex(max(0, current_index))
        self.text_size_combo.setMinimumWidth(190)
        self.text_size_combo.setStyleSheet(
            f"QComboBox {{ background: white; color: {C.TEXT};"
            f" border: 1px solid {C.BORDER}; border-radius: 4px; padding: 5px 8px; }}"
            f"QComboBox:hover {{ border-color: {C.BORDER_DK}; }}"
            f"QComboBox:focus {{ border-color: {C.OLIVE}; }}"
        )
        size_lay.addWidget(self.text_size_combo)
        body_lay.addWidget(size_row)

        self.display_detail_label = QLabel()
        self.display_detail_label.setWordWrap(True)
        self.display_detail_label.setStyleSheet(self._note_style())
        body_lay.addWidget(self.display_detail_label)
        restart_note = QLabel(
            "Text-size changes take effect the next time the application starts."
        )
        restart_note.setWordWrap(True)
        restart_note.setStyleSheet(
            f"color: {C.OLIVE_DK}; font-size: {F.SZ_SM}pt; background: transparent;"
        )
        body_lay.addWidget(restart_note)
        self.text_size_combo.currentIndexChanged.connect(self._update_display_detail)
        self._update_display_detail()
        body_lay.addStretch(1)

        root.addWidget(body, 1)
        root.addWidget(make_dialog_footer([
            ("Cancel", self.reject, "secondary"),
            ("Save Preferences", self.accept, "primary"),
        ]))
        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )

    def _update_display_detail(self) -> None:
        if self.text_size_combo.currentData() == 1:
            text = "Large adds one point to body text throughout the application."
        else:
            text = "Normal uses the standard compact desktop text scale."
        self.display_detail_label.setText(text)

    def show_welcome_on_startup(self) -> bool:
        return bool(self.show_welcome_checkbox.isChecked())

    def ui_font_bump(self) -> int:
        value = self.text_size_combo.currentData()
        try:
            return max(0, min(1, int(value)))
        except (TypeError, ValueError):
            return self._ui_font_bump

    @staticmethod
    def _section_heading(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}';"
            f" font-size: {F.SZ_XS}pt; font-weight: 700; background: transparent;"
        )
        return label

    @staticmethod
    def _divider() -> QFrame:
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {C.BORDER};")
        return divider

    @staticmethod
    def _title_style() -> str:
        return (
            f"color: {C.TEXT}; font-size: {F.SZ_LG}pt; font-weight: 600;"
            " background: transparent;"
        )

    @staticmethod
    def _note_style() -> str:
        return (
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt;"
            " background: transparent;"
        )
