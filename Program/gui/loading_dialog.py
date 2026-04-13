from __future__ import annotations

import math
import os
import time
from typing import Sequence

from PyQt6.QtCore import QObject, QPointF, QRectF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QLinearGradient, QPainterPath
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
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


def _blend(c1: QColor, c2: QColor, amount: float) -> QColor:
    amount = max(0.0, min(1.0, amount))
    return QColor(
        round(c1.red() + (c2.red() - c1.red()) * amount),
        round(c1.green() + (c2.green() - c1.green()) * amount),
        round(c1.blue() + (c2.blue() - c1.blue()) * amount),
        round(c1.alpha() + (c2.alpha() - c1.alpha()) * amount),
    )


class _StratigraphyBackdrop(QWidget):
    """Lightweight animated backdrop that echoes the splash screen sediment bands."""

    _BAND_COLORS = (
        QColor(215, 191, 142),  # sand
        QColor(189, 157, 121),  # silt
        QColor(153, 163, 171),  # clay
        QColor(116, 130, 88),   # olive
    )
    _AMPLITUDES = (2.6, 4.0, 3.2, 1.8, 0.8)
    _FREQUENCIES = (0.92, 0.74, 1.08, 0.86, 0.60)
    _SPEEDS = (0.66, -0.42, 0.28, -0.18, 0.10)
    _BOUNDARY_RATIOS = (0.42, 0.56, 0.70, 0.84, 0.96)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        self._phase = (self._phase + 0.035) % 1000.0
        self.update()

    def _boundary_base(self, index: int) -> float:
        return self.height() * self._BOUNDARY_RATIOS[index]

    def _boundary_y(self, index: int, x: float) -> float:
        width = max(1.0, float(self.width()))
        nx = x / width
        phase = self._phase * self._SPEEDS[index]
        ripple = (
            0.65 * math.sin(nx * math.tau * self._FREQUENCIES[index] + phase)
            + 0.35 * math.cos(nx * math.tau * (self._FREQUENCIES[index] * 0.58) + phase * 1.2)
        )
        return self._boundary_base(index) + self._AMPLITUDES[index] * ripple

    def _sample_points(self) -> list[float]:
        points = list(range(-20, self.width() + 21, 18))
        if not points:
            points = [-20, self.width() + 20]
        elif points[-1] != self.width() + 20:
            points.append(self.width() + 20)
        return [float(x) for x in points]

    def _band_path(self, index: int) -> QPainterPath:
        points = self._sample_points()
        top = [QPointF(x, self._boundary_y(index, x)) for x in points]
        bottom = [QPointF(x, self._boundary_y(index + 1, x)) for x in points]

        path = QPainterPath(top[0])
        for point in top[1:]:
            path.lineTo(point)
        for point in reversed(bottom):
            path.lineTo(point)
        path.closeSubpath()
        return path

    def _boundary_path(self, index: int, fraction: float = 0.0) -> QPainterPath:
        points = self._sample_points()
        path = QPainterPath()
        for i, x in enumerate(points):
            top_y = self._boundary_y(index, x)
            bottom_y = self._boundary_y(index + 1, x)
            y = top_y + (bottom_y - top_y) * fraction
            point = QPointF(x, y)
            if i == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        return path

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        base = QLinearGradient(0, 0, 0, rect.height())
        base.setColorAt(0.0, QColor(247, 243, 235))
        base.setColorAt(1.0, QColor(235, 228, 214))
        painter.fillRect(rect, QBrush(base))

        wash = QLinearGradient(0, 0, rect.width(), rect.height())
        wash.setColorAt(0.0, QColor(255, 255, 255, 50))
        wash.setColorAt(0.55, QColor(255, 255, 255, 0))
        wash.setColorAt(1.0, QColor(159, 146, 118, 28))
        painter.fillRect(rect, QBrush(wash))

        painter.setPen(QPen(QColor(93, 78, 55, 44), 1))
        painter.drawLine(18, 18, 72, 18)
        painter.drawLine(self.width() - 72, 18, self.width() - 18, 18)

        for index, base_color in enumerate(self._BAND_COLORS):
            path = self._band_path(index)
            top = self._boundary_base(index)
            bottom = self._boundary_base(index + 1)
            gradient = QLinearGradient(0, top, 0, bottom)
            gradient.setColorAt(0.0, _blend(base_color, QColor(250, 246, 235), 0.10))
            gradient.setColorAt(1.0, _blend(base_color, QColor(74, 68, 55), 0.10 + index * 0.015))
            painter.fillPath(path, QBrush(gradient))

            painter.setPen(QPen(QColor(88, 76, 57, 54), 1.0))
            painter.drawPath(self._boundary_path(index))
            painter.setPen(QPen(QColor(255, 255, 255, 18), 0.8))
            painter.drawPath(self._boundary_path(index, 0.34))

        painter.end()


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


class _LoadingProgressRail(QWidget):
    """Determinate progress rail with a continuous shimmer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = 0
        self._total = 1
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.setFixedHeight(12)
        self.start()

    def start(self):
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        self._timer.stop()
        self.update()

    def set_progress(self, current: int, total: int):
        self._total = max(1, total)
        self._current = max(0, min(current, self._total))
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.02) % 1.0
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect().adjusted(0, 1, 0, -1))
        radius = rect.height() / 2

        track_path = QPainterPath()
        track_path.addRoundedRect(rect, radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        track_grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        track_grad.setColorAt(0.0, QColor(255, 255, 255, 120))
        track_grad.setColorAt(1.0, QColor(210, 196, 168, 116))
        painter.setBrush(QBrush(track_grad))
        painter.drawPath(track_path)

        progress = self._current / self._total if self._total else 0.0
        if self._timer.isActive() and progress <= 0:
            progress = 0.08

        if progress > 0:
            fill_width = max(rect.height(), rect.width() * progress)
            fill_rect = QRectF(rect)
            fill_rect.setWidth(fill_width)
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, radius, radius)
            fill_grad = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
            fill_grad.setColorAt(0.0, QColor(244, 237, 223))
            fill_grad.setColorAt(0.55, QColor(233, 228, 204))
            fill_grad.setColorAt(1.0, QColor(211, 224, 175))
            painter.setBrush(QBrush(fill_grad))
            painter.drawPath(fill_path)

        painter.save()
        painter.setClipPath(track_path)
        highlight_w = max(70.0, rect.width() * 0.18)
        highlight_x = rect.x() + (rect.width() + highlight_w) * self._phase - highlight_w
        highlight_rect = QRectF(rect)
        highlight_rect.moveLeft(highlight_x)
        highlight_rect.setWidth(highlight_w)
        grad = QLinearGradient(highlight_rect.topLeft(), highlight_rect.topRight())
        grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        grad.setColorAt(0.5, QColor(255, 255, 255, 132))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(grad))
        painter.drawRoundedRect(highlight_rect, radius, radius)
        painter.restore()
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
        self._live_frame = 0
        self._status_base = "Loading"
        self._started_at = time.monotonic()

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

        body = _StratigraphyBackdrop()
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

        self._stage_label = QLabel("Preparing items")
        self._stage_label.setStyleSheet(
            f"color: {C.TEXT}; font-family: '{F.UI}'; font-size: {F.SZ_XL + 1}pt; font-weight: 600;"
            " background: transparent;"
        )
        text_col.addWidget(self._stage_label)

        self._detail_label = QLabel("Setting up the background loader.")
        self._detail_label.setWordWrap(True)
        self._detail_label.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_SM + 1}pt; background: transparent;"
        )
        text_col.addWidget(self._detail_label)

        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(6)

        self._count_chip = QLabel("0 of 0 items")
        self._count_chip.setStyleSheet(
            f"color: {C.OLIVE_DK}; background: rgba(247,243,235,0.72); "
            f"border: 1px solid rgba(107,142,35,0.24); border-radius: 99px; "
            f"padding: 2px 8px; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
        )
        chips_row.addWidget(self._count_chip, 0, Qt.AlignmentFlag.AlignLeft)

        self._elapsed_chip = QLabel("00:00 elapsed")
        self._elapsed_chip.setStyleSheet(
            f"color: {C.TEXT_MUTED}; background: rgba(247,243,235,0.72); "
            f"border: 1px solid rgba(144,130,109,0.24); border-radius: 99px; "
            f"padding: 2px 8px; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
        )
        chips_row.addWidget(self._elapsed_chip, 0, Qt.AlignmentFlag.AlignLeft)
        chips_row.addStretch(1)
        text_col.addLayout(chips_row)
        text_col.addStretch(1)

        hero_row.addLayout(text_col, 1)
        body_lay.addLayout(hero_row)

        self._progress = _LoadingProgressRail()
        body_lay.addWidget(self._progress)

        self._note_label = QLabel(
            "Selected items are being processed in the background. This window closes automatically when loading is complete."
        )
        self._note_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_XS}pt; background: transparent;"
        )
        self._note_label.setWordWrap(True)
        body_lay.addWidget(self._note_label)

        panel = QFrame()
        panel.setStyleSheet(
            f"background: rgba(247,243,235,0.58); border: 1px solid rgba(144,130,109,0.24); "
            f"border-radius: {SZ.BORDER_RADIUS + 2}px;"
        )
        panel_lay = QHBoxLayout(panel)
        panel_lay.setContentsMargins(10, 8, 10, 8)
        panel_lay.setSpacing(8)

        self._activity_dot = QLabel()
        self._activity_dot.setFixedSize(8, 8)
        self._activity_dot.setStyleSheet(f"background: {C.OLIVE}; border-radius: 4px;")
        panel_lay.addWidget(self._activity_dot, 0, Qt.AlignmentFlag.AlignTop)

        self._activity_label = QLabel("Waiting for the background loader to start.")
        self._activity_label.setWordWrap(True)
        self._activity_label.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt; background: transparent;"
        )
        panel_lay.addWidget(self._activity_label, 1)
        body_lay.addWidget(panel)

        root.addWidget(body, 1)

        self._footer_status = QLabel("Loading")
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

        self._live_timer = QTimer(self)
        self._live_timer.setInterval(180)
        self._live_timer.timeout.connect(self._tick_live_state)
        self._live_timer.start()

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed_chip)
        self._elapsed_timer.start()
        self._update_elapsed_chip()

    def update_progress(
        self,
        current: int,
        total: int,
        stage: str,
        detail: str,
        *,
        count_label: str | None = None,
        activity_label: str | None = None,
    ):
        total = max(total, 1)
        current = max(0, min(current, total))
        self._progress.set_progress(current, total)
        self._stage_label.setText(stage)
        self._detail_label.setText(detail or " ")
        if activity_label is None:
            if current <= 0:
                activity_label = "Starting the background loader."
            else:
                activity_label = f"Processing item {current} of {total}."
        if count_label is None:
            count_label = f"{current} of {total} items"
        self._activity_label.setText(activity_label)
        self._count_chip.setText(count_label)
        self._status_base = "Loading"
        self._tick_live_state()

    def set_activity(self, text: str):
        self._note_label.setText(text)

    def mark_finished(self, headline: str, detail: str = "", *, ok: bool = True):
        self._finished = True
        self._spinner.stop()
        self._progress.set_progress(1, 1)
        self._progress.stop()
        self._live_timer.stop()
        self._elapsed_timer.stop()
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
        self._activity_dot.setStyleSheet(
            f"background: {C.OLIVE if ok else C.LED_WARN}; border-radius: 4px;"
        )
        if self._footer_button is not None:
            self._footer_button.setEnabled(True)
            self._footer_button.setText("Close")

    def mark_cancel_pending(self):
        if self._cancel_pending or self._finished:
            return
        self._cancel_pending = True
        self._detail_label.setText("Finishing the current file before stopping.")
        self._activity_label.setText("Cancellation requested.")
        self._status_base = "Stopping"
        self._tick_live_state()
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

    def _update_elapsed_chip(self):
        elapsed_seconds = max(0, int(time.monotonic() - self._started_at))
        minutes, seconds = divmod(elapsed_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            text = f"{hours:02d}:{minutes:02d}:{seconds:02d} elapsed"
        else:
            text = f"{minutes:02d}:{seconds:02d} elapsed"
        self._elapsed_chip.setText(text)

    def _tick_live_state(self):
        if self._finished:
            return
        self._live_frame = (self._live_frame + 1) % 24
        dot_suffix = "." * ((self._live_frame // 6) % 4)
        self._footer_status.setText(f"{self._status_base}{dot_suffix}")
        opacity_cycle = (0.35, 0.55, 0.75, 1.0, 0.75, 0.55)
        opacity = opacity_cycle[self._live_frame % len(opacity_cycle)]
        olive = QColor(C.OLIVE)
        self._activity_dot.setStyleSheet(
            f"background: rgba({olive.red()}, {olive.green()}, {olive.blue()}, {int(opacity * 255)}); "
            "border-radius: 4px;"
        )


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
