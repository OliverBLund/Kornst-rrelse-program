"""Workspace-wide analysis settings dialog."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.dialog_chrome import make_dialog_footer, make_dialog_header, style_dialog_button
from gui.theme import C, F
from qt_chrome.frameless_dialog_base import FramelessDialogBase


class AnalysisSettingsDialog(FramelessDialogBase):
    """Edit workspace defaults and open the specialist selectors."""

    def __init__(self, control_panel, main_window, parent=None):
        super().__init__(parent, default_mode="auto")
        self.control_panel = control_panel
        self.main_window = main_window
        self._scheme = control_panel._active_scheme
        self._method_names = list(getattr(main_window, "active_method_names", []))
        self.setWindowTitle("Analysis Settings")
        self.setMinimumSize(680, 510)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._header_widget = make_dialog_header(
            "Analysis Settings",
            "Workspace defaults and calculation methods",
            fa_icon="fa6s.sliders",
            close_fn=self.reject,
        )
        root.addWidget(self._header_widget)

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        intro = QLabel(
            "These settings apply across the workspace. Dataset Inputs keeps "
            "temperature and porosity overrides explicit for individual datasets."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SZ_MD}pt;")
        layout.addWidget(intro)

        self.temperature = QDoubleSpinBox()
        source_temp = self.control_panel.temp_spinbox
        self.temperature.setRange(source_temp.minimum(), source_temp.maximum())
        self.temperature.setDecimals(source_temp.decimals())
        self.temperature.setSingleStep(source_temp.singleStep())
        self.temperature.setSuffix(" °C")
        self.temperature.setValue(source_temp.value())
        self.temperature.setStyleSheet(self._editor_style())
        self.temperature.setToolTip(
            "Default water temperature for new imports. Applying it also updates all loaded datasets."
        )
        layout.addWidget(self._setting_row(
            "Workspace temperature",
            "Default for new imports; Apply updates all loaded datasets",
            self.temperature,
        ))

        self.porosity_mode = QComboBox()
        source_mode = self.control_panel.porosity_mode_combo
        for index in range(source_mode.count()):
            self.porosity_mode.addItem(source_mode.itemText(index))
        self.porosity_mode.setCurrentText(source_mode.currentText())
        self.porosity_mode.setStyleSheet(self._editor_style())
        self.porosity_mode.setToolTip(
            "Formula used to calculate automatic porosity. Manual dataset overrides are preserved."
        )
        layout.addWidget(self._setting_row(
            "Automatic porosity formula",
            "Formula for automatic values; manual overrides are preserved",
            self.porosity_mode,
        ))

        layout.addWidget(self._divider())
        self.scheme_value = QLabel()
        self.methods_value = QLabel()
        self._refresh_workspace_labels()

        scheme_button = QPushButton("Change…")
        style_dialog_button(scheme_button, "secondary")
        scheme_button.clicked.connect(self._choose_scheme)
        layout.addWidget(self._selector_row(
            "Classification scheme",
            self.scheme_value,
            scheme_button,
            "Grain-class labels in views, reports, and exports",
        ))

        methods_button = QPushButton("Choose…")
        style_dialog_button(methods_button, "secondary")
        methods_button.clicked.connect(self._choose_methods)
        layout.addWidget(self._selector_row(
            "Active K methods",
            self.methods_value,
            methods_button,
            "Shared by results, plots, comparison, reports, and exports",
        ))

        layout.addWidget(self._divider())
        inputs_button = QPushButton("Open Dataset Inputs…")
        style_dialog_button(inputs_button, "secondary")
        inputs_button.clicked.connect(
            lambda: self.control_panel.open_dataset_inputs_dialog()
        )
        layout.addWidget(self._selector_row(
            "Dataset-specific inputs",
            QLabel("Temperature and effective porosity"),
            inputs_button,
            "Edit one, selected, or all loaded datasets",
        ))
        root.addWidget(body, 1)
        root.addWidget(make_dialog_footer([
            ("Cancel", self.reject, "secondary"),
            ("Apply Workspace Settings", self._apply, "primary"),
        ]))
        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {C.BORDER};")
        return line

    @staticmethod
    def _editor_style() -> str:
        return (
            f"QDoubleSpinBox, QComboBox {{ background: white; color: {C.TEXT};"
            f" border: 1px solid {C.BORDER}; border-radius: 4px;"
            " padding: 5px 8px; }"
            f"QDoubleSpinBox:hover, QComboBox:hover {{ border-color: {C.BORDER_DK}; }}"
            f"QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {C.OLIVE}; }}"
            "QComboBox::drop-down { border: none; width: 24px; }"
        )

    @staticmethod
    def _setting_row(title: str, note: str, editor: QWidget) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 3, 0, 3)
        text = QVBoxLayout()
        text.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {C.TEXT}; font-weight: 600;")
        note_label = QLabel(note)
        note_label.setWordWrap(True)
        note_label.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt;")
        text.addWidget(title_label)
        text.addWidget(note_label)
        lay.addLayout(text, 1)
        editor.setMinimumWidth(205)
        lay.addWidget(editor)
        return row

    @staticmethod
    def _selector_row(title: str, value: QLabel, button: QPushButton, note: str) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 3, 0, 3)
        text = QVBoxLayout()
        text.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {C.TEXT}; font-weight: 600;")
        value.setStyleSheet(f"color: {C.TEXT_MID}; font-family: '{F.MONO}';")
        note_label = QLabel(note)
        note_label.setWordWrap(True)
        note_label.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt;")
        text.addWidget(title_label)
        text.addWidget(value)
        text.addWidget(note_label)
        lay.addLayout(text, 1)
        lay.addWidget(button)
        return row

    def _refresh_workspace_labels(self) -> None:
        self.scheme_value.setText(
            getattr(self._scheme, "name", "Current scheme")
        )
        active = len(self._method_names)
        available = len(getattr(self.main_window, "available_method_names", []))
        self.methods_value.setText(f"{active} of {available} methods active")

    def _choose_scheme(self) -> None:
        from gui.classification_dialog import ClassificationDialog

        dialog = ClassificationDialog(current_scheme=self._scheme, parent=self)

        def stage_scheme(scheme) -> None:
            self._scheme = scheme
            self._refresh_workspace_labels()

        dialog.scheme_selected.connect(stage_scheme)
        dialog.exec()

    def _choose_methods(self) -> None:
        from gui.method_selection_dialog import MethodSelectionDialog

        dialog = MethodSelectionDialog(
            selected_methods=self._method_names,
            available_methods=getattr(self.main_window, "available_method_names", []),
            parent=self,
        )
        if dialog.exec():
            self._method_names = dialog.selected_methods()
            self._refresh_workspace_labels()

    def _apply(self) -> None:
        self.control_panel.temp_spinbox.setValue(self.temperature.value())
        index = self.control_panel.porosity_mode_combo.findText(
            self.porosity_mode.currentText()
        )
        if index >= 0:
            self.control_panel.porosity_mode_combo.setCurrentIndex(index)
        if self._scheme is not self.control_panel._active_scheme:
            self.control_panel._on_scheme_changed(self._scheme)
        self.main_window.set_active_k_methods(self._method_names)
        self.control_panel.sample_info_label.setText(
            f"Analysis settings updated: {self.control_panel.analysis_settings_summary()}"
        )
        self.accept()
