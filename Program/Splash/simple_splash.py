"""
Stratigraphy-poster splash screen for Grain Size Analysis startup.
"""

from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, QTimer, Qt, QVariantAnimation
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QRegion
from PyQt6.QtWidgets import QApplication, QWidget


def _blend(c1: QColor, c2: QColor, amount: float) -> QColor:
    amount = max(0.0, min(1.0, amount))
    return QColor(
        round(c1.red() + (c2.red() - c1.red()) * amount),
        round(c1.green() + (c2.green() - c1.green()) * amount),
        round(c1.blue() + (c2.blue() - c1.blue()) * amount),
        round(c1.alpha() + (c2.alpha() - c1.alpha()) * amount),
    )


def _with_alpha(color: QColor, alpha: int) -> QColor:
    out = QColor(color)
    out.setAlpha(max(0, min(255, alpha)))
    return out


class SimpleSplash(QWidget):
    """Poster-style splash screen with animated sediment layers."""

    _BOUNDARY_BASES = (194.0, 226.0, 262.0, 302.0, 344.0)
    _BOUNDARY_AMPLITUDES = (3.0, 5.2, 4.6, 3.8, 2.4)
    _BOUNDARY_FREQUENCIES = (1.00, 0.82, 1.16, 0.94, 0.66)
    _BOUNDARY_SPEEDS = (0.75, -0.52, 0.42, -0.30, 0.18)
    _BAND_COLORS = (
        QColor(122, 113, 103),  # dark topsoil
        QColor(230, 210, 178),  # light cream
        QColor(229, 189, 137),  # pale sand
        QColor(206, 158, 120),  # warm tan
    )

    def __init__(self, backdrop_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(600, 360)
        self._corner_radius = 18
        self._backdrop_path = backdrop_path

        self._display_progress = 0.0
        self._target_progress = 0
        self._motion_phase = 0.0
        self._status_mix = 1.0
        self._stage_text = "Starting Grain Size Analysis"
        self._stage_previous = ""
        self._detail_text = "Loading fonts and preparing the application shell."
        self._detail_previous = ""
        self.fade_animation: Optional[QPropertyAnimation] = None

        self._progress_animation = QVariantAnimation(self)
        self._progress_animation.setDuration(420)
        self._progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._progress_animation.valueChanged.connect(self._on_progress_value)

        self._status_animation = QVariantAnimation(self)
        self._status_animation.setDuration(240)
        self._status_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._status_animation.valueChanged.connect(self._on_status_mix)

        self._motion_timer = QTimer(self)
        self._motion_timer.setInterval(16)
        self._motion_timer.timeout.connect(self._tick)
        self._motion_timer.start()

        self.setWindowOpacity(1.0)
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def _motion_strength(self) -> float:
        progress_ratio = max(0.0, min(1.0, self._display_progress / 100.0))
        return 0.45 + (1.0 - progress_ratio) * 0.55

    def _boundary_y(self, index: int, x: float) -> float:
        nx = x / max(1.0, float(self.width()))
        phase = self._motion_phase * self._BOUNDARY_SPEEDS[index]
        amplitude = self._BOUNDARY_AMPLITUDES[index] * self._motion_strength()
        frequency = self._BOUNDARY_FREQUENCIES[index]
        ripple = (
            0.65 * math.sin(nx * math.tau * frequency + phase)
            + 0.35 * math.cos(nx * math.tau * (frequency * 0.58) + phase * 1.2)
        )
        return self._BOUNDARY_BASES[index] + amplitude * ripple

    def _sample_points(self) -> list[float]:
        points = list(range(-24, self.width() + 25, 18))
        if points[-1] != self.width() + 24:
            points.append(self.width() + 24)
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
        for idx, x in enumerate(points):
            top_y = self._boundary_y(index, x)
            bottom_y = self._boundary_y(index + 1, x)
            y = top_y + (bottom_y - top_y) * fraction
            point = QPointF(x, y)
            if idx == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        return path

    def _segment_completion(self, index: int) -> float:
        start = index * 25.0
        return max(0.0, min(1.0, (self._display_progress - start) / 25.0))

    def _current_band_index(self) -> int:
        if self._display_progress >= 100.0:
            return 3
        return max(0, min(3, int(self._display_progress // 25.0)))

    def _tick(self) -> None:
        self._motion_phase = (self._motion_phase + 0.04) % 1000.0
        self.update()

    def _on_progress_value(self, value) -> None:
        self._display_progress = float(value)
        self.update()

    def _on_status_mix(self, value) -> None:
        self._status_mix = float(value)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self._corner_radius, self._corner_radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), self._corner_radius, self._corner_radius)
        painter.setClipPath(clip)

        self._draw_background(painter)
        self._draw_bands(painter)
        self._draw_text_block(painter)
        self._draw_progress_rail(painter)
        self._draw_frame(painter)

    def _draw_background(self, painter: QPainter) -> None:
        rect = self.rect()

        base = QLinearGradient(0, 0, 0, rect.height())
        base.setColorAt(0.0, QColor(246, 239, 227))
        base.setColorAt(1.0, QColor(229, 214, 191))
        painter.fillRect(rect, base)

        wash = QLinearGradient(0, 0, rect.width(), rect.height())
        wash.setColorAt(0.0, QColor(255, 251, 245, 42))
        wash.setColorAt(0.55, QColor(255, 255, 255, 0))
        wash.setColorAt(1.0, QColor(170, 133, 100, 26))
        painter.fillRect(rect, wash)

        hairline = QPen(QColor(93, 78, 55, 52), 1)
        painter.setPen(hairline)
        painter.drawLine(40, 36, 98, 36)
        painter.drawLine(self.width() - 98, 36, self.width() - 40, 36)

    def _draw_bands(self, painter: QPainter) -> None:
        active_index = self._current_band_index()

        for index, base_color in enumerate(self._BAND_COLORS):
            path = self._band_path(index)
            completion = self._segment_completion(index)
            highlight = 0.08 + completion * 0.18
            shadow = 0.10 + index * 0.015

            gradient = QLinearGradient(
                0,
                self._BOUNDARY_BASES[index],
                0,
                self._BOUNDARY_BASES[index + 1],
            )
            gradient.setColorAt(0.0, _blend(base_color, QColor(250, 246, 235), highlight))
            gradient.setColorAt(1.0, _blend(base_color, QColor(74, 68, 55), shadow))
            painter.fillPath(path, QBrush(gradient))

            if completion > 0.0:
                shimmer = QLinearGradient(0, 0, self.width(), 0)
                shimmer.setColorAt(0.0, QColor(255, 255, 255, 0))
                shimmer.setColorAt(0.42, QColor(255, 248, 236, int(34 + 60 * completion)))
                shimmer.setColorAt(1.0, QColor(255, 255, 255, 0))
                painter.fillPath(path, QBrush(shimmer))

            boundary_pen = QPen(QColor(88, 76, 57, 68 if index != active_index else 94), 1.0)
            painter.setPen(boundary_pen)
            painter.drawPath(self._boundary_path(index))

            painter.setPen(QPen(QColor(255, 255, 255, 18), 0.8))
            painter.drawPath(self._boundary_path(index, 0.34))
            painter.drawPath(self._boundary_path(index, 0.67))

        painter.setPen(QPen(QColor(118, 94, 70, 100), 1.1))
        painter.drawPath(self._boundary_path(3))

    def _title_font(self) -> QFont:
        """Return the title font used in the poster header."""
        title_font = QFont("Source Sans 3", 28, QFont.Weight.DemiBold)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.2)
        return title_font

    def _title_layout(self) -> tuple[QFont, QPointF, QPointF]:
        """Compute title baselines from live font metrics."""
        left = 40.0
        title_top = 48.0

        title_font = self._title_font()
        title_metrics = QFontMetricsF(title_font)
        glyph_height = max(
            title_metrics.tightBoundingRect("Grain Size").height(),
            title_metrics.tightBoundingRect("Analysis").height(),
        )
        line_step = max(
            33.0,
            min(
                title_metrics.lineSpacing() - 5.0,
                math.ceil(glyph_height + 2.0),
            ),
        )

        grain_pos = QPointF(left, title_top + title_metrics.ascent())
        analysis_pos = QPointF(left, title_top + title_metrics.ascent() + line_step)
        return title_font, grain_pos, analysis_pos

    def _draw_text_block(self, painter: QPainter) -> None:
        left = 40

        title_font, grain_pos, analysis_pos = self._title_layout()
        title_metrics = QFontMetricsF(title_font)
        painter.setFont(title_font)
        painter.setPen(QColor(44, 41, 35))
        painter.drawText(grain_pos, "Grain Size")
        painter.drawText(analysis_pos, "Analysis")

        analysis_top = analysis_pos.y() - title_metrics.ascent()
        analysis_bottom = analysis_top + title_metrics.tightBoundingRect("Analysis").height()
        subtitle_top = analysis_bottom + 10.0

        subtitle_font = QFont("Source Sans 3", 11, QFont.Weight.Medium)
        subtitle_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        painter.setFont(subtitle_font)
        painter.setPen(QColor(104, 91, 72))
        painter.drawText(
            QRectF(left, subtitle_top, 320, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Hydraulic conductivity calculator",
        )

        label_top = subtitle_top + 27.0
        label_font = QFont("Source Sans 3", 9, QFont.Weight.DemiBold)
        label_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.1)
        painter.setFont(label_font)
        painter.setPen(QColor(118, 106, 88))
        painter.drawText(
            QRectF(left, label_top, 200, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "STARTUP STATUS",
        )

        stage_rect = QRectF(left, label_top + 18.0, 420, 18)
        detail_rect = QRectF(left, label_top + 38.0, 360, 16)
        self._draw_transition_text(
            painter,
            stage_rect,
            self._stage_previous,
            self._stage_text,
            QFont("JetBrains Mono", 10, QFont.Weight.Medium),
            QColor(82, 67, 50),
        )
        self._draw_transition_text(
            painter,
            detail_rect,
            self._detail_previous,
            self._detail_text,
            QFont("Source Sans 3", 10),
            QColor(112, 100, 82),
        )
        painter.setPen(QPen(QColor(166, 132, 92, 125), 1.4))
        painter.drawLine(QPointF(left, label_top - 7.0), QPointF(left + 26, label_top - 7.0))

    def _draw_transition_text(
        self,
        painter: QPainter,
        rect: QRectF,
        previous: str,
        current: str,
        font: QFont,
        color: QColor,
    ) -> None:
        painter.setFont(font)

        if previous and self._status_mix < 1.0:
            previous_color = _with_alpha(color, round(color.alpha() * (1.0 - self._status_mix)))
            painter.setPen(previous_color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, previous)

        current_color = _with_alpha(color, round(color.alpha() * self._status_mix))
        painter.setPen(current_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, current)

    def _draw_progress_rail(self, painter: QPainter) -> None:
        rail_x = 40
        rail_y = self.height() - 38
        rail_width = self.width() - 120
        progress_ratio = max(0.0, min(1.0, self._display_progress / 100.0))
        progress_x = rail_x + rail_width * progress_ratio

        track_pen = QPen(QColor(116, 100, 79, 90), 2.0)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawLine(QPointF(rail_x, rail_y), QPointF(rail_x + rail_width, rail_y))

        for marker in range(1, 4):
            tick_x = rail_x + rail_width * (marker / 4.0)
            painter.setPen(QPen(QColor(232, 224, 208, 120), 1.0))
            painter.drawLine(QPointF(tick_x, rail_y - 6), QPointF(tick_x, rail_y + 6))

        fill_gradient = QLinearGradient(rail_x, rail_y, rail_x + rail_width, rail_y)
        fill_gradient.setColorAt(0.0, QColor(244, 237, 223))
        fill_gradient.setColorAt(0.55, QColor(229, 204, 167))
        fill_gradient.setColorAt(1.0, QColor(198, 156, 118))
        fill_pen = QPen(QBrush(fill_gradient), 3.0)
        fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(fill_pen)
        painter.drawLine(QPointF(rail_x, rail_y), QPointF(progress_x, rail_y))

        cap_color = _blend(QColor(229, 204, 167), QColor(166, 132, 92), progress_ratio * 0.45)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_with_alpha(cap_color, 235))
        painter.drawEllipse(QPointF(progress_x, rail_y), 3.6, 3.6)

        percent_font = QFont("JetBrains Mono", 10, QFont.Weight.Medium)
        painter.setFont(percent_font)
        painter.setPen(QColor(95, 77, 58))
        painter.drawText(
            QRectF(self.width() - 74, rail_y - 11, 36, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{int(round(self._display_progress)):>3d}%",
        )

    def _draw_frame(self, painter: QPainter) -> None:
        frame_rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        painter.setPen(QPen(QColor(144, 130, 109, 72), 1.1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(frame_rect, self._corner_radius, self._corner_radius)

    def _set_status_text(self, stage: str, detail: Optional[str] = None) -> None:
        next_stage = (stage or "").strip() or "Initializing..."
        next_detail = self._detail_text if detail is None else (detail or "").strip()

        if next_stage == self._stage_text and next_detail == self._detail_text:
            return

        self._stage_previous = self._stage_text
        self._detail_previous = self._detail_text
        self._stage_text = next_stage
        self._detail_text = next_detail

        self._status_animation.stop()
        self._status_mix = 0.0
        self._status_animation.setStartValue(0.0)
        self._status_animation.setEndValue(1.0)
        self._status_animation.start()
        self.update()

    def _animate_progress(self, value: int) -> None:
        incoming = max(0, min(100, int(value)))
        self._target_progress = max(self._target_progress, incoming)
        self._progress_animation.stop()
        self._progress_animation.setStartValue(self._display_progress)
        self._progress_animation.setEndValue(float(self._target_progress))
        self._progress_animation.start()

    def set_backdrop(self, image_path: str) -> None:
        """Retained for compatibility; the poster splash does not use backdrops."""
        self._backdrop_path = image_path

    def set_message(self, message: str) -> None:
        self._set_status_text(message)

    def set_progress(self, value: int, message: str = "", detail: Optional[str] = None) -> None:
        """Update startup progress and cross-fade the status copy."""
        self._animate_progress(value)
        stage = message or self._stage_text
        self._set_status_text(stage, detail)

    def finish_with_fade(self, message: str = "Ready!") -> None:
        self.set_message(message)
        QTimer.singleShot(260, self._start_fade_out)

    def _start_fade_out(self) -> None:
        if self.fade_animation:
            self.fade_animation.stop()

        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(240)
        self.fade_animation.setStartValue(self.windowOpacity())
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InQuad)
        self.fade_animation.finished.connect(self.close)
        self.fade_animation.start()
