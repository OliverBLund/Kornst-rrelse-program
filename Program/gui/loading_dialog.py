from __future__ import annotations

import os
from typing import Sequence

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from data_loader import DataLoader
from gui.dialog_chrome import make_dialog_footer, make_dialog_header
from gui.theme import C, F, SZ
from qt_chrome.frameless_dialog_base import FramelessDialogBase


def _friendly_load_error(error: Exception | str) -> str:
    error_str = str(error)
    lowered = error_str.lower()
    if "requires manual" in lowered or "column mapping" in lowered:
        return "Excel sheet requires manual column mapping"
    if "could not parse" in lowered:
        return "Could not auto-detect column format"
    if "no valid" in lowered:
        return "No valid grain size data found"
    if "delimiter" in lowered:
        return "Could not determine file delimiter format"
    return error_str


class _LoadingSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(54, 54)
        self.start()

    def start(self):
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        self._timer.stop()
        self.update()

    def _tick(self):
        self._angle = (self._angle + 28) % 360
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(6, 6, -6, -6)

        track_pen = QPen(QColor(210, 196, 168, 140), 5)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        active_pen = QPen(QColor(C.OLIVE), 5)
        active_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(active_pen)
        start_angle = int(-self._angle * 16)
        painter.drawArc(rect, start_angle, -112 * 16)
        painter.end()


class LoadingDialog(FramelessDialogBase):
    cancellation_requested = pyqtSignal()

    def __init__(
        self,
        title: str,
        subtitle: str,
        parent=None,
        *,
        cancellable: bool = True,
    ):
        super().__init__(parent, default_mode="auto")
        self._cancellable = cancellable
        self._cancel_pending = False
        self._finished = False

        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        self.setMaximumWidth(560)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header_widget = make_dialog_header(
            title,
            subtitle,
            fa_icon="fa6s.arrows-rotate",
            close_fn=self._request_cancel,
        )
        root.addWidget(self._header_widget)

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(18, 18, 18, 16)
        body_lay.setSpacing(14)

        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 0, 0, 0)
        hero_row.setSpacing(14)

        self._spinner = _LoadingSpinner()
        hero_row.addWidget(self._spinner, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)

        self._stage_label = QLabel("Preparing load...")
        self._stage_label.setStyleSheet(
            f"color: {C.TEXT}; font-family: '{F.DISP}'; font-size: {F.SZ_XL}pt; font-weight: 700;"
            " background: transparent;"
        )
        text_col.addWidget(self._stage_label)

        self._detail_label = QLabel("Scanning selected files.")
        self._detail_label.setWordWrap(True)
        self._detail_label.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt; background: transparent;"
        )
        text_col.addWidget(self._detail_label)

        self._count_chip = QLabel("0 / 0")
        self._count_chip.setStyleSheet(
            f"color: {C.OLIVE_DK}; background: rgba(107,142,35,0.10); "
            f"border: 1px solid rgba(107,142,35,0.24); border-radius: 99px; "
            f"padding: 2px 8px; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
        )
        text_col.addWidget(self._count_chip, 0, Qt.AlignmentFlag.AlignLeft)
        text_col.addStretch(1)

        hero_row.addLayout(text_col, 1)
        body_lay.addLayout(hero_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(10)
        self._progress.setStyleSheet(
            f"QProgressBar {{ background: rgba(210,196,168,0.40); border: none; "
            f"border-radius: 5px; }} "
            f"QProgressBar::chunk {{ background: {C.OLIVE}; border-radius: 5px; }}"
        )
        body_lay.addWidget(self._progress)

        self._note_label = QLabel("The app stays responsive while data is being loaded.")
        self._note_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_XS}pt; background: transparent;"
        )
        self._note_label.setWordWrap(True)
        body_lay.addWidget(self._note_label)

        panel = QFrame()
        panel.setStyleSheet(
            f"background: rgba(255,255,255,0.75); border: 1px solid {C.BORDER}; border-radius: {SZ.BORDER_RADIUS}px;"
        )
        panel_lay = QHBoxLayout(panel)
        panel_lay.setContentsMargins(10, 8, 10, 8)
        panel_lay.setSpacing(8)

        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {C.OLIVE}; border-radius: 4px;")
        panel_lay.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

        self._activity_label = QLabel("Waiting for worker thread to start...")
        self._activity_label.setWordWrap(True)
        self._activity_label.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt; background: transparent;"
        )
        panel_lay.addWidget(self._activity_label, 1)
        body_lay.addWidget(panel)

        root.addWidget(body, 1)

        self._footer_status = QLabel("Loading…")
        self._footer_status.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; background: transparent;"
        )
        footer = make_dialog_footer(
            [("Cancel", self._request_cancel, "secondary")],
            left_widget=self._footer_status,
        )
        root.addWidget(footer)
        buttons = footer.findChildren(QPushButton)
        self._footer_button = buttons[0] if buttons else None
        if self._footer_button is not None and not cancellable:
            self._footer_button.setEnabled(False)

        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )

    def update_progress(self, current: int, total: int, stage: str, detail: str):
        total = max(total, 1)
        current = max(0, min(current, total))
        self._progress.setRange(0, total)
        self._progress.setValue(current)
        self._stage_label.setText(stage)
        self._detail_label.setText(detail or " ")
        self._activity_label.setText(f"Processing {current} of {total}.")
        self._count_chip.setText(f"{current} / {total}")
        self._footer_status.setText("Loading…")

    def set_activity(self, text: str):
        self._activity_label.setText(text)

    def mark_finished(self, headline: str, detail: str = "", *, ok: bool = True):
        self._finished = True
        self._spinner.stop()
        if self._progress.maximum() > 0:
            self._progress.setValue(self._progress.maximum())
        self._stage_label.setText(headline)
        self._detail_label.setText(detail or " ")
        self._activity_label.setText(
            "Completed successfully." if ok else "Completed with warnings."
        )
        self._footer_status.setText("Done" if ok else "Needs review")
        self._note_label.setText(
            "You can close this dialog now."
            if ok
            else "Some items could not be loaded automatically and may need review."
        )
        if self._footer_button is not None:
            self._footer_button.setEnabled(True)
            self._footer_button.setText("Close")

    def mark_cancel_pending(self):
        if self._cancel_pending or self._finished:
            return
        self._cancel_pending = True
        self._detail_label.setText("Finishing the current file before stopping…")
        self._activity_label.setText("Cancellation requested.")
        self._footer_status.setText("Stopping…")
        if self._footer_button is not None:
            self._footer_button.setEnabled(False)

    def _request_cancel(self):
        if self._finished:
            self.accept()
            return
        if not self._cancellable or self._cancel_pending:
            return
        self.mark_cancel_pending()
        self.cancellation_requested.emit()


class BatchImportWorker(QObject):
    progress = pyqtSignal(int, int, str, str)
    item_loaded = pyqtSignal(str, object, str, str)
    item_validation_failed = pyqtSignal(str, object, str, str)
    item_failed = pyqtSignal(str, str)
    finished = pyqtSignal(dict)

    def __init__(self, file_entries: Sequence[object]):
        super().__init__()
        self._file_entries = list(file_entries)
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        loader = DataLoader()
        total = len(self._file_entries)
        summary = {"total": total, "loaded": 0, "review": 0, "failed": 0, "canceled": False}

        for index, file_entry in enumerate(self._file_entries, start=1):
            if self._cancel_requested:
                summary["canceled"] = True
                break

            if isinstance(file_entry, tuple):
                file_path, sheet_name = file_entry
                file_key = f"{file_path}:::{sheet_name}"
                display_name = f"{os.path.basename(file_path)} [{sheet_name}]"
            else:
                file_path = str(file_entry)
                sheet_name = None
                file_key = file_path
                display_name = os.path.basename(file_path)

            self.progress.emit(index, total, "Loading selected files", display_name)

            try:
                if sheet_name:
                    raise ValueError("Excel sheet requires manual column mapping")

                dataset = loader.load_file(file_path)
                dataset.file_path = file_path
                sample_name = getattr(dataset, "sample_name", os.path.basename(file_path))

                if dataset.has_errors():
                    summary["failed"] += 1
                    self.item_validation_failed.emit(
                        file_key,
                        dataset,
                        sample_name,
                        "Data loaded but has validation errors",
                    )
                else:
                    summary["loaded"] += 1
                    self.item_loaded.emit(file_key, dataset, "loaded", sample_name)
            except Exception as exc:
                summary["review"] += 1
                self.item_failed.emit(file_key, _friendly_load_error(exc))

        self.finished.emit(summary)


class ExternalLoadWorker(QObject):
    progress = pyqtSignal(int, int, str, str)
    file_loaded = pyqtSignal(str, object)
    file_failed = pyqtSignal(str, str)
    finished = pyqtSignal(dict)

    def __init__(self, file_paths: Sequence[str], *, stage_title: str = "Loading datasets"):
        super().__init__()
        self._file_paths = [os.path.normpath(path) for path in file_paths]
        self._stage_title = stage_title
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        loader = DataLoader()
        total = len(self._file_paths)
        summary = {"total": total, "loaded": 0, "failed": 0, "canceled": False}

        for index, file_path in enumerate(self._file_paths, start=1):
            if self._cancel_requested:
                summary["canceled"] = True
                break

            display_name = os.path.basename(file_path)
            self.progress.emit(index, total, self._stage_title, display_name)

            try:
                dataset = loader.load_file(file_path)
                dataset.file_path = file_path
                summary["loaded"] += 1
                self.file_loaded.emit(file_path, dataset)
            except Exception as exc:
                summary["failed"] += 1
                self.file_failed.emit(file_path, _friendly_load_error(exc))

        self.finished.emit(summary)
