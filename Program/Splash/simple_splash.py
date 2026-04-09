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
        QColor(215, 191, 142),  # sand
        QColor(189, 157, 121),  # silt
        QColor(153, 163, 171),  # clay
        QColor(116, 130, 88),   # olive
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
        base.setColorAt(0.0, QColor(247, 243, 235))
        base.setColorAt(1.0, QColor(234, 227, 213))
        painter.fillRect(rect, base)

        wash = QLinearGradient(0, 0, rect.width(), rect.height())
        wash.setColorAt(0.0, QColor(255, 255, 255, 65))
        wash.setColorAt(0.55, QColor(255, 255, 255, 0))
        wash.setColorAt(1.0, QColor(159, 146, 118, 40))
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

        painter.setPen(QPen(QColor(86, 100, 59, 100), 1.1))
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
            QColor(63, 73, 45),
        )
        self._draw_transition_text(
            painter,
            detail_rect,
            self._detail_previous,
            self._detail_text,
            QFont("Source Sans 3", 10),
            QColor(112, 100, 82),
        )
        painter.setPen(QPen(QColor(107, 142, 35, 125), 1.4))
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

        track_pen = QPen(QColor(63, 68, 49, 90), 2.0)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawLine(QPointF(rail_x, rail_y), QPointF(rail_x + rail_width, rail_y))

        for marker in range(1, 4):
            tick_x = rail_x + rail_width * (marker / 4.0)
            painter.setPen(QPen(QColor(232, 224, 208, 120), 1.0))
            painter.drawLine(QPointF(tick_x, rail_y - 6), QPointF(tick_x, rail_y + 6))

        fill_gradient = QLinearGradient(rail_x, rail_y, rail_x + rail_width, rail_y)
        fill_gradient.setColorAt(0.0, QColor(244, 237, 223))
        fill_gradient.setColorAt(0.55, QColor(233, 228, 204))
        fill_gradient.setColorAt(1.0, QColor(211, 224, 175))
        fill_pen = QPen(QBrush(fill_gradient), 3.0)
        fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(fill_pen)
        painter.drawLine(QPointF(rail_x, rail_y), QPointF(progress_x, rail_y))

        cap_color = _blend(QColor(233, 228, 204), QColor(107, 142, 35), progress_ratio * 0.45)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_with_alpha(cap_color, 235))
        painter.drawEllipse(QPointF(progress_x, rail_y), 3.6, 3.6)

        percent_font = QFont("JetBrains Mono", 10, QFont.Weight.Medium)
        painter.setFont(percent_font)
        painter.setPen(QColor(67, 79, 47))
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
        self._target_progress = max(0, min(100, int(value)))
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


class _LegacySimpleSplash(QWidget):
    """Professional splash screen for Grain Size Analysis startup."""

    def __init__(self, backdrop_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.SplashScreen |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(560, 320)
        self._corner_radius = 14

        # Add subtle gradient overlay
        gradient_overlay = QWidget(self)
        gradient_overlay.setObjectName("gradientOverlay")
        gradient_overlay.setStyleSheet(
            "#gradientOverlay {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            "    stop:0 rgba(0, 0, 0, 0.1),"
            "    stop:0.5 rgba(0, 0, 0, 0.0),"
            "    stop:1 rgba(0, 0, 0, 0.15));"
            "}"
        )
        gradient_overlay.lower()  # Put behind other widgets
        gradient_overlay.resize(self.size())  # Ensure it covers the full widget

        # Window shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        # Add subtle particle effect
        self.particles = []
        self._setup_particles()

        # Backdrop (optional) - try provided path, else discover common assets
        self.backdrop_pixmap = None
        if not backdrop_path:
            # Attempt to discover a data visualization image automatically
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                candidates = [
                    os.path.join(base_dir, '..', '..', 'assets', 'Icons', 'data_visualization_backdrop.jpg'),
                    os.path.join(base_dir, '..', '..', 'assets', 'Icons', 'hexagonal_background.jpg'),
                    os.path.join(base_dir, '..', '..', '..', 'icons', 'DataPal.webp'),
                    os.path.join(base_dir, '..', '..', '..', 'icons', 'Data_view.webp'),
                ]
                for p in candidates:
                    if os.path.exists(p):
                        backdrop_path = p
                        break
            except Exception:
                pass
        if backdrop_path and os.path.exists(backdrop_path):
            img = QImage(backdrop_path)
            self.backdrop_pixmap = QPixmap.fromImage(img) if not img.isNull() else None
        self._backdrop_path = backdrop_path

        self._setup_ui()
        self._center_on_screen()

        self.fade_animation = None
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(200)
        self.fade_in.setStartValue(0.85)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.setWindowOpacity(1.0)

        # Start particle animation
        self.particle_timer = QTimer(self)
        self.particle_timer.setInterval(50)  # 20 FPS
        self.particle_timer.timeout.connect(self._update_particles)
        self.particle_timer.start()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Clip to rounded rect so all content respects the radius
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self._corner_radius, self._corner_radius)
        painter.setClipPath(path)

        if self.backdrop_pixmap:
            # Draw backdrop prominently
            scaled = self.backdrop_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

            # Add a subtle darkening vignette to improve text contrast
            vignette = QLinearGradient(0, 0, self.width(), self.height())
            vignette.setColorAt(0.0, QColor(0, 0, 0, 30))
            vignette.setColorAt(1.0, QColor(0, 0, 0, 60))
            painter.fillRect(self.rect(), QBrush(vignette))

        # Earth/sand gradient overlay (grain size analysis theme)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, QColor(139, 115, 85, 160))   # Tan/brown
        grad.setColorAt(1.0, QColor(107, 142, 35, 160))    # Olive green (geotechnical)
        painter.fillRect(self.rect(), QBrush(grad))

        # Border uses the exact same radius for perfect alignment
        painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), self._corner_radius, self._corner_radius)

        # Draw particles
        self._draw_particles(painter)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(16)

        # Glass card container for logo/title/subtitles
        card = QWidget(self)
        card.setObjectName("glassCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 18, 24, 18)
        card_layout.setSpacing(10)
        card.setStyleSheet(
            "#glassCard {"
            "  background-color: rgba(255, 255, 255, 0.14);"
            "  border: 1px solid rgba(255, 255, 255, 0.32);"
            "  border-radius: 12px;"
            "}"
        )
        # Card shadow
        card_shadow = QGraphicsDropShadowEffect(self)
        card_shadow.setBlurRadius(22)
        card_shadow.setOffset(0, 6)
        card_shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(card_shadow)

        # Add highlight line to card
        highlight = QWidget(card)
        highlight.setObjectName("cardHighlight")
        highlight.setFixedHeight(2)
        highlight.setStyleSheet(
            "#cardHighlight {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            "    stop:0 rgba(255, 255, 255, 0.0),"
            "    stop:0.3 rgba(255, 255, 255, 0.6),"
            "    stop:0.7 rgba(255, 255, 255, 0.6),"
            "    stop:1 rgba(255, 255, 255, 0.0));"
            "  border-radius: 1px;"
            "}"
        )
        card_layout.addWidget(highlight, 0, Qt.AlignmentFlag.AlignTop)

        header = QVBoxLayout()
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo - different from QGIS (data/analytics themed)
        #logo = QLabel("📊")
        #logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #logo.setFont(QFont("Segoe UI Emoji", 56))
        #logo.setStyleSheet("color: white;")
        #card_layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel("Grain Size Analysis")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont("Calibri", 34, QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
        title.setFont(f)
        title.setObjectName("titleLabel")
        title.setStyleSheet(
            "QLabel#titleLabel {"
            "  color: white;"
            "  font-size: 38px;"
            "  font-weight: 700;"
            "  letter-spacing: 1px;"
            "}"
        )
        # Title shadow for prominence
        title_shadow = QGraphicsDropShadowEffect(self)
        title_shadow.setBlurRadius(118)
        title_shadow.setOffset(0, 2)
        title_shadow.setColor(QColor(0, 0, 0, 140))
        title.setGraphicsEffect(title_shadow)
        card_layout.addWidget(title, 0, Qt.AlignmentFlag.AlignCenter)

        # Subtitle
        subtitle_main = QLabel("Hydraulic Conductivity Calculator")
        subtitle_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_font = QFont("Calibri", 14)
        sub_font.setItalic(False)
        subtitle_main.setFont(sub_font)
        subtitle_main.setObjectName("subtitleMain")
        subtitle_main.setStyleSheet(
            "QLabel#subtitleMain {"
            "  color: rgba(255,255,255,0.95);"
            "  font-size: 16px;"
            "  font-style: normal;"
            "  font-weight: 600;"
            "}"
        )
        sub_shadow = QGraphicsDropShadowEffect(self)
        sub_shadow.setBlurRadius(12)
        sub_shadow.setOffset(0, 1)
        sub_shadow.setColor(QColor(0, 0, 0, 120))
        subtitle_main.setGraphicsEffect(sub_shadow)
        card_layout.addWidget(subtitle_main, 0, Qt.AlignmentFlag.AlignCenter)

        # Secondary subtitle - startup themed
        subtitle_startup = QLabel("Preparing workspace...")
        subtitle_startup.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_startup.setFont(QFont("Segoe UI", 13))
        subtitle_startup.setObjectName("subtitleStartup")
        subtitle_startup.setStyleSheet(
            "QLabel#subtitleStartup {"
            "  color: rgba(255,255,255,0.88);"
            "  font-size: 16px;"
            "}"
        )
        sub2_shadow = QGraphicsDropShadowEffect(self)
        sub2_shadow.setBlurRadius(10)
        sub2_shadow.setOffset(0, 1)
        sub2_shadow.setColor(QColor(0, 0, 0, 110))
        subtitle_startup.setGraphicsEffect(sub2_shadow)
        card_layout.addWidget(subtitle_startup, 0, Qt.AlignmentFlag.AlignCenter)

        header.addWidget(card)
        layout.addLayout(header)
        layout.addStretch(1)

        # Detail label for status descriptions beneath the bar
        self.detail_label = QLabel("")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setObjectName("detailLabel")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet(
            "#detailLabel {"
            "  color: rgba(255,255,255,0.78);"
            "  font-size: 11px;"
            "  font-weight: 500;"
            "}"
        )
        layout.addWidget(self.detail_label)

        # Animated progress bar with text inside
        self.progress_bar = _AnimatedAccentBar(self)
        layout.addWidget(self.progress_bar)

        # Add footer
        footer = QLabel("Geotechnical Engineering • Soil Mechanics Analysis")
        footer.setObjectName("footerLabel")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(
            "#footerLabel {"
            "  color: rgba(255, 255, 255, 0.75);"
            "  font-size: 10px;"
            "  font-weight: 400;"
            "  letter-spacing: 0.5px;"
            "}"
        )
        layout.addWidget(footer)

        self.progress_bar.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Apply a rounded mask to the whole window to guarantee rounded corners
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self._corner_radius, self._corner_radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

        # Ensure gradient overlay covers the full widget
        gradient_overlay = self.findChild(QWidget, "gradientOverlay")
        if gradient_overlay:
            gradient_overlay.resize(self.size())

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def set_backdrop(self, image_path: str):
        """Dynamically set/update the backdrop image and repaint."""
        try:
            if image_path and os.path.exists(image_path):
                img = QImage(image_path)
                if not img.isNull():
                    self.backdrop_pixmap = QPixmap.fromImage(img)
                    self._backdrop_path = image_path
                    self.update()
        except Exception:
            pass

    def set_message(self, message: str):
        try:
            display = message or ""
            if hasattr(self, 'progress_bar') and self.progress_bar:
                self.progress_bar.set_text(display or "Initializing...")
            self.repaint()
        except Exception:
            pass

    def set_progress(self, value: int, message: str = "", detail: str = ""):
        """Update progress and text inside progress bar."""
        try:
            parts = []
            if value is not None:
                parts.append(f"{int(value)}%")
            if message:
                parts.append(message)
            progress_text = "  •  ".join(parts)
            self.set_message(progress_text)
            if hasattr(self, 'detail_label') and self.detail_label is not None:
                self.detail_label.setText(detail or "")
        except Exception as e:
            print(f"Error updating splash UI: {e}")

    def finish_with_fade(self, message: str = "Ready!"):
        self.set_message(message)
        QTimer.singleShot(300, self._start_fade_out)

    def _start_fade_out(self):
        try:
            if self.fade_animation:
                self.fade_animation.stop()
            self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
            self.fade_animation.setDuration(280)
            self.fade_animation.setStartValue(1.0)
            self.fade_animation.setEndValue(0.0)
            self.fade_animation.setEasingCurve(QEasingCurve.Type.InQuad)
            self.fade_animation.finished.connect(self.close)
            self.fade_animation.start()
        except Exception:
            self.close()

    def _setup_particles(self):
        """Initialize floating particles for background effect."""
        import random
        for _ in range(8):  # 8 subtle particles
            particle = {
                'x': random.uniform(0, self.width()),
                'y': random.uniform(0, self.height()),
                'vx': random.uniform(-0.3, 0.3),
                'vy': random.uniform(-0.2, 0.2),
                'size': random.uniform(1, 3),
                'alpha': random.uniform(0.3, 0.7),
                'life': random.uniform(0, 1.0)
            }
            self.particles.append(particle)

    def _update_particles(self):
        """Update particle positions and life."""
        import random
        for particle in self.particles:
            # Update position
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']

            # Wrap around edges
            if particle['x'] < -10:
                particle['x'] = self.width() + 10
            elif particle['x'] > self.width() + 10:
                particle['x'] = -10
            if particle['y'] < -10:
                particle['y'] = self.height() + 10
            elif particle['y'] > self.height() + 10:
                particle['y'] = -10

            # Update life cycle
            particle['life'] += 0.01
            if particle['life'] > 1.0:
                particle['life'] = 0.0
                particle['alpha'] = random.uniform(0.3, 0.7)

        self.update()

    def _draw_particles(self, painter):
        """Draw floating particles."""
        for particle in self.particles:
            # Calculate alpha based on life cycle
            alpha = particle['alpha'] * (0.5 + 0.5 * abs(particle['life'] - 0.5))

            # Draw particle
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, int(alpha * 255))))
            painter.drawEllipse(
                int(particle['x']),
                int(particle['y']),
                int(particle['size']),
                int(particle['size'])
            )


class _AnimatedAccentBar(QWidget):
    """Wide progress bar with text inside and animated accent line."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 FPS
        self._timer.timeout.connect(self._tick)
        self._phase = 0.0
        self._speed = 0.008  # tune movement speed
        self.setFixedHeight(35)  # Much taller for text
        self.setMinimumWidth(300)  # Wider for better text display
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._text = "Starting..."

    def start(self):
        self._phase = 0.0
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def set_text(self, text):
        """Update the text displayed in the progress bar."""
        self._text = text
        self.update()

    def _tick(self):
        self._phase = (self._phase + self._speed) % 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 2, 0, -2)

        # Track background
        track_color = QColor(255, 255, 255, 60)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_color))
        radius = rect.height() / 2
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        painter.drawPath(path)

        # Moving highlight
        w = rect.width()
        highlight_w = max(int(w * 0.22), 60)
        x = int((w + highlight_w) * self._phase) - highlight_w
        highlight_rect = QRectF(rect.x() + x, rect.y(), highlight_w, rect.height())

        grad = QLinearGradient(highlight_rect.topLeft(), highlight_rect.topRight())
        grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        grad.setColorAt(0.5, QColor(255, 255, 255, 180))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.setBrush(QBrush(grad))
        hp = QPainterPath()
        hp.addRoundedRect(highlight_rect, radius, radius)
        painter.drawPath(hp)

        # Draw text
        painter.setPen(QPen(QColor(255, 255, 255, 220)))
        font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font)

        # Center the text
        text_rect = rect
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._text)
