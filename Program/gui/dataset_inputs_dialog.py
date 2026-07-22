"""Unified editor for per-dataset temperature and effective porosity."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.dialog_chrome import (
    make_dialog_footer,
    make_dialog_header,
    style_dialog_button,
)
from gui.theme import C, F
from qt_chrome.frameless_dialog_base import FramelessDialogBase


def apply_dataset_inputs(
    tab,
    *,
    temperature: float,
    porosity: float | None = None,
    use_automatic_porosity: bool = False,
) -> bool:
    """Synchronize one dataset's effective inputs and recalculate once."""
    dataset = getattr(tab, "dataset", None)
    if dataset is None:
        return False

    previous_temperature = float(getattr(tab, "temperature", dataset.temperature))
    previous_porosity = float(
        getattr(tab, "porosity", None)
        or getattr(dataset, "current_porosity", None)
        or getattr(dataset, "porosity", 0.40)
    )
    if use_automatic_porosity:
        effective_porosity = getattr(dataset, "calculated_porosity", None)
        if effective_porosity is None:
            effective_porosity = previous_porosity
    else:
        effective_porosity = porosity if porosity is not None else previous_porosity

    temperature = float(temperature)
    effective_porosity = float(effective_porosity)
    changed = (
        abs(previous_temperature - temperature) > 1e-9
        or abs(previous_porosity - effective_porosity) > 1e-9
    )

    dataset.temperature = temperature
    dataset.current_porosity = effective_porosity
    dataset.porosity = effective_porosity
    tab.temperature = temperature
    tab.porosity = effective_porosity

    stats = getattr(tab, "statistics_tab", None)
    if stats is not None:
        if hasattr(stats, "temperature"):
            stats.temperature = temperature
        if hasattr(stats, "porosity"):
            stats.porosity = effective_porosity

    if changed and getattr(tab, "current_results", None) and hasattr(tab, "calculate_k_values"):
        tab.calculate_k_values()
    elif stats is not None and hasattr(stats, "update_display"):
        stats.update_display()

    if hasattr(tab, "update_summary_bar"):
        tab.update_summary_bar()
    return changed


class DatasetInputsDialog(FramelessDialogBase):
    """Edit temperature and effective porosity for selected or all datasets."""

    def __init__(self, main_window, parent=None, *, focus_dataset_name: str | None = None):
        super().__init__(parent, default_mode="auto")
        self.main_window = main_window
        self.focus_dataset_name = focus_dataset_name
        self._row_tabs: list = []
        self._row_auto_requests: set[int] = set()
        self._temperature_dirty: set[int] = set()
        self._porosity_dirty: set[int] = set()
        self._initial_inputs: list[tuple[float, float]] = []
        self.changes_applied = 0
        self.setWindowTitle("Dataset Inputs")
        self.setMinimumSize(900, 540)
        self._build_ui()
        self.load_values()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._header_widget = make_dialog_header(
            "Dataset Inputs",
            "Temperature and effective porosity | changes recalculate K values",
            fa_icon="fa6s.sliders",
            close_fn=self.reject,
        )
        root.addWidget(self._header_widget)

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(16, 14, 16, 14)
        body_lay.setSpacing(10)

        summary = QHBoxLayout()
        self.summary_label = QLabel("No datasets loaded")
        self.summary_label.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_LG}pt; font-weight: 650;"
        )
        self.summary_meta_label = QLabel("")
        self.summary_meta_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt;"
        )
        summary.addWidget(self.summary_label)
        summary.addStretch(1)
        summary.addWidget(self.summary_meta_label)
        body_lay.addLayout(summary)

        body_lay.addWidget(self._build_bulk_bar())

        self.inputs_table = QTableWidget(0, 6)
        self.inputs_table.setHorizontalHeaderLabels([
            "Dataset",
            "Temperature",
            "Auto porosity",
            "Porosity used",
            "Source",
            "",
        ])
        self.inputs_table.setAlternatingRowColors(True)
        self.inputs_table.verticalHeader().setVisible(False)
        self.inputs_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.inputs_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.inputs_table.setShowGrid(False)
        self.inputs_table.setFrameShape(QFrame.Shape.NoFrame)
        header = self.inputs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        for column, width in {
            1: 150,
            2: 105,
            3: 145,
            4: 150,
            5: 145,
        }.items():
            self.inputs_table.setColumnWidth(column, width)
        self.inputs_table.setStyleSheet(
            f"QTableWidget {{ background: white; border: 1px solid {C.BORDER};"
            f" alternate-background-color: rgba(238,232,220,0.45); font-size: {F.SZ_MD}pt; }}"
            f"QTableWidget::item {{ padding: 7px 9px; border-bottom: 1px solid rgba(212,196,168,0.42); }}"
            f"QTableWidget::item:selected {{ background: rgba(107,142,35,0.11); color: {C.TEXT}; }}"
            f"QHeaderView::section {{ background: {C.BG_LOW}; padding: 7px 10px; border: none;"
            f" border-bottom: 1px solid {C.BORDER}; color: {C.TEXT_MUTED}; font-weight: 600; }}"
        )
        body_lay.addWidget(self.inputs_table, 1)

        self.info_label = QLabel(
            "Edit rows directly or stage one value for selected/all datasets. "
            "Automatic porosity uses the workspace formula."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; background: transparent;"
        )
        body_lay.addWidget(self.info_label)
        root.addWidget(body, 1)
        root.addWidget(make_dialog_footer([
            ("Cancel", self.reject, "secondary"),
            ("Apply Changes", self.apply_changes, "primary"),
        ]))
        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )

    def _build_bulk_bar(self) -> QWidget:
        bulk = QFrame()
        bulk.setObjectName("datasetInputsBulkBar")
        bulk.setStyleSheet(
            f"QFrame#datasetInputsBulkBar {{ background: {C.BG_LOW};"
            f" border-top: 1px solid {C.BORDER}; border-bottom: 1px solid {C.BORDER}; }}"
            "QFrame#datasetInputsBulkBar QLabel { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(bulk)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(6)

        scope_row = QHBoxLayout()
        scope_row.setSpacing(7)
        scope_row.addWidget(QLabel("Apply staged values to"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Selected rows", "selected")
        self.scope_combo.addItem("All datasets", "all")
        self.scope_combo.setCurrentIndex(0 if self.focus_dataset_name else 1)
        scope_row.addWidget(self.scope_combo)
        scope_hint = QLabel("Select several table rows with Ctrl/Shift")
        scope_hint.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt;")
        scope_row.addWidget(scope_hint)
        scope_row.addStretch(1)
        layout.addLayout(scope_row)

        controls = QHBoxLayout()
        controls.setSpacing(7)
        controls.addWidget(QLabel("Temperature"))

        self.bulk_temperature = QDoubleSpinBox()
        self.bulk_temperature.setRange(0.0, 50.0)
        self.bulk_temperature.setDecimals(1)
        self.bulk_temperature.setSuffix(" °C")
        self.bulk_temperature.setValue(20.0)
        self.bulk_temperature.setToolTip(
            "Water temperature used by viscosity-dependent K methods"
        )
        controls.addWidget(self.bulk_temperature)
        set_temp = QPushButton("Set temperature")
        style_dialog_button(set_temp, "secondary")
        set_temp.clicked.connect(self._stage_bulk_temperature)
        controls.addWidget(set_temp)
        controls.addSpacing(10)
        controls.addWidget(QLabel("Effective porosity"))

        self.bulk_porosity = QDoubleSpinBox()
        self.bulk_porosity.setRange(0.10, 0.80)
        self.bulk_porosity.setDecimals(4)
        self.bulk_porosity.setSingleStep(0.01)
        self.bulk_porosity.setValue(0.40)
        self.bulk_porosity.setToolTip(
            "Effective porosity used by porosity-dependent K methods"
        )
        controls.addWidget(self.bulk_porosity)
        set_porosity = QPushButton("Set manual")
        style_dialog_button(set_porosity, "secondary")
        set_porosity.setToolTip("Stage this effective porosity as a manual override")
        set_porosity.clicked.connect(self._stage_bulk_porosity)
        controls.addWidget(set_porosity)
        use_auto = QPushButton("Use automatic")
        style_dialog_button(use_auto, "secondary")
        use_auto.setToolTip("Restore each target dataset's exact automatic porosity")
        use_auto.clicked.connect(self._stage_bulk_automatic)
        controls.addWidget(use_auto)
        controls.addStretch(1)
        layout.addLayout(controls)
        return bulk

    @staticmethod
    def _spin_style() -> str:
        return (
            f"QDoubleSpinBox {{ background: white; border: 1px solid {C.BORDER};"
            f" border-radius: 4px; padding: 4px 6px; color: {C.TEXT};"
            f" font-family: '{F.MONO}'; }}"
            f"QDoubleSpinBox:focus {{ border-color: {C.OLIVE}; }}"
        )

    def load_values(self) -> None:
        """Load temperature and porosity values for every dataset tab."""
        self.inputs_table.setRowCount(0)
        self._row_tabs = []
        self._row_auto_requests.clear()
        self._temperature_dirty.clear()
        self._porosity_dirty.clear()
        self._initial_inputs = []
        if not hasattr(self.main_window, "dataset_tabs_widget"):
            self.summary_label.setText("Unable to access datasets")
            return

        auto_count = 0
        manual_count = 0
        focus_row = -1
        for index in range(self.main_window.dataset_tabs_widget.count()):
            tab = self.main_window.dataset_tabs_widget.widget(index)
            dataset = getattr(tab, "dataset", None)
            if dataset is None:
                continue
            row = self.inputs_table.rowCount()
            self.inputs_table.insertRow(row)
            self.inputs_table.setRowHeight(row, 46)
            self._row_tabs.append(tab)
            name = str(dataset.sample_name)
            if name == self.focus_dataset_name:
                focus_row = row

            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setData(Qt.ItemDataRole.UserRole, name)
            self.inputs_table.setItem(row, 0, name_item)

            temperature = float(getattr(tab, "temperature", dataset.temperature))
            temp_spin = QDoubleSpinBox()
            temp_spin.setRange(0.0, 50.0)
            temp_spin.setDecimals(1)
            temp_spin.setSingleStep(0.5)
            temp_spin.setSuffix(" °C")
            temp_spin.setValue(temperature)
            temp_spin.setStyleSheet(self._spin_style())
            temp_spin.valueChanged.connect(
                lambda _value, r=row: self._temperature_dirty.add(r)
            )
            self.inputs_table.setCellWidget(row, 1, temp_spin)

            calculated = getattr(dataset, "calculated_porosity", None)
            mode = (
                dataset.calculated_porosity_mode_label()
                if hasattr(dataset, "calculated_porosity_mode_label")
                else "Automatic formula"
            )
            auto_item = QTableWidgetItem(
                f"{calculated:.4f}" if calculated is not None else "N/A"
            )
            auto_item.setToolTip(f"Automatic estimate from {mode}.")
            auto_item.setFlags(auto_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            auto_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.inputs_table.setItem(row, 2, auto_item)

            current = float(
                getattr(dataset, "current_porosity", None)
                or calculated
                or getattr(dataset, "porosity", 0.40)
            )
            self._initial_inputs.append((temperature, current))
            por_spin = QDoubleSpinBox()
            por_spin.setRange(0.10, 0.80)
            por_spin.setDecimals(4)
            por_spin.setSingleStep(0.01)
            por_spin.setValue(current)
            por_spin.setStyleSheet(self._spin_style())
            por_spin.valueChanged.connect(
                lambda _value, r=row: self._stage_manual_row(r)
            )
            self.inputs_table.setCellWidget(row, 3, por_spin)

            is_manual = calculated is None or abs(current - calculated) > 0.0001
            manual_count += int(is_manual)
            auto_count += int(not is_manual)
            source = QLabel("Manual override" if is_manual else mode)
            source.setAlignment(Qt.AlignmentFlag.AlignCenter)
            source.setMinimumWidth(136)
            self.inputs_table.setCellWidget(row, 4, source)
            self._set_source_state(row, source.text(), manual=is_manual)

            auto_btn = QPushButton("Use automatic")
            auto_btn.setMinimumWidth(135)
            auto_btn.setEnabled(calculated is not None)
            auto_btn.setToolTip(
                "Replace the manual value with the exact automatic estimate"
            )
            auto_btn.clicked.connect(
                lambda _checked=False, r=row: self._stage_row_automatic(r)
            )
            self.inputs_table.setCellWidget(row, 5, auto_btn)

        count = len(self._row_tabs)
        self.summary_label.setText(
            f"{count} dataset{'s' if count != 1 else ''} in workspace"
            if count
            else "No datasets loaded"
        )
        self.summary_meta_label.setText(
            f"{auto_count} automatic | {manual_count} manual override{'s' if manual_count != 1 else ''}"
            if count
            else ""
        )
        if focus_row >= 0:
            self.inputs_table.selectRow(focus_row)
            self.inputs_table.setCurrentCell(focus_row, 0)
            self.inputs_table.scrollToItem(self.inputs_table.item(focus_row, 0))

    def _target_rows(self) -> list[int]:
        if self.scope_combo.currentData() == "all":
            return list(range(len(self._row_tabs)))
        rows = sorted({index.row() for index in self.inputs_table.selectionModel().selectedRows()})
        if not rows and self.inputs_table.currentRow() >= 0:
            rows = [self.inputs_table.currentRow()]
        if not rows:
            QMessageBox.information(self, "Dataset Inputs", "Select one or more dataset rows, or choose All datasets.")
        return rows

    def _stage_bulk_temperature(self) -> None:
        rows = self._target_rows()
        for row in rows:
            spin = self.inputs_table.cellWidget(row, 1)
            if isinstance(spin, QDoubleSpinBox):
                spin.setValue(self.bulk_temperature.value())
        if rows:
            self.info_label.setText(f"Temperature staged for {len(rows)} dataset{'s' if len(rows) != 1 else ''}.")

    def _stage_bulk_porosity(self) -> None:
        rows = self._target_rows()
        for row in rows:
            spin = self.inputs_table.cellWidget(row, 3)
            if isinstance(spin, QDoubleSpinBox):
                spin.setValue(self.bulk_porosity.value())
            self._stage_manual_row(row)
        if rows:
            self.info_label.setText(f"Manual porosity staged for {len(rows)} dataset{'s' if len(rows) != 1 else ''}.")

    def _stage_row_automatic(self, row: int) -> None:
        if row < 0 or row >= len(self._row_tabs):
            return
        dataset = getattr(self._row_tabs[row], "dataset", None)
        calculated = getattr(dataset, "calculated_porosity", None)
        if calculated is None:
            return
        spin = self.inputs_table.cellWidget(row, 3)
        if isinstance(spin, QDoubleSpinBox):
            spin.blockSignals(True)
            spin.setValue(float(calculated))
            spin.blockSignals(False)
        self._row_auto_requests.add(row)
        self._porosity_dirty.add(row)
        self._set_source_state(row, "Automatic (staged)", manual=False)

    def _stage_manual_row(self, row: int) -> None:
        self._row_auto_requests.discard(row)
        self._porosity_dirty.add(row)
        self._set_source_state(row, "Manual override (staged)", manual=True)

    def _set_source_state(self, row: int, text: str, *, manual: bool) -> None:
        source = self.inputs_table.cellWidget(row, 4)
        if not isinstance(source, QLabel):
            return
        source.setText(text)
        source.setStyleSheet(
            f"padding: 2px 7px; color: {'#8f3525' if manual else C.OLIVE};"
            f" background: {'rgba(192,56,40,0.07)' if manual else 'rgba(107,142,35,0.09)'};"
            " border-radius: 9px;"
        )

    def _stage_bulk_automatic(self) -> None:
        rows = self._target_rows()
        applied = 0
        for row in rows:
            dataset = getattr(self._row_tabs[row], "dataset", None)
            if getattr(dataset, "calculated_porosity", None) is not None:
                self._stage_row_automatic(row)
                applied += 1
        if rows:
            self.info_label.setText(f"Automatic porosity staged for {applied} dataset{'s' if applied != 1 else ''}.")

    def _apply_row(self, row: int) -> bool:
        if (
            row not in self._temperature_dirty
            and row not in self._porosity_dirty
            and row not in self._row_auto_requests
        ):
            return False
        temp_spin = self.inputs_table.cellWidget(row, 1)
        por_spin = self.inputs_table.cellWidget(row, 3)
        if not isinstance(temp_spin, QDoubleSpinBox) or not isinstance(por_spin, QDoubleSpinBox):
            return False
        initial_temperature, initial_porosity = self._initial_inputs[row]
        return apply_dataset_inputs(
            self._row_tabs[row],
            temperature=(
                temp_spin.value()
                if row in self._temperature_dirty
                else initial_temperature
            ),
            porosity=(
                por_spin.value()
                if row in self._porosity_dirty
                else initial_porosity
            ),
            use_automatic_porosity=row in self._row_auto_requests,
        )

    def apply_changes(self) -> None:
        self.changes_applied = sum(1 for row in range(len(self._row_tabs)) if self._apply_row(row))
        if self.changes_applied:
            self.accept()
            return
        self.info_label.setText("No dataset input values changed.")
