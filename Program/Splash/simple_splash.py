"""
Professional splash screen for Grain Size Analysis startup.
"""

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor, QLinearGradient, QPen, QBrush, QImage, QPainterPath, QRegion
from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QGraphicsDropShadowEffect
from typing import Optional
import os


class SimpleSplash(QWidget):
    """Professional splash screen for Grain Size Analysis startup."""

    def __init__(self, backdrop_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
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
        subtitle_startup = QLabel("Initializing application...")
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
