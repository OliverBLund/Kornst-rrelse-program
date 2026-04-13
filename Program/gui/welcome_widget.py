"""
Welcome Widget — styled to match design_concepts/05_welcome.html.

Background: soil_layers.png scaled to fill (KeepAspectRatioByExpanding),
with rgba(255,255,255,0.38) overlay. Scroll content is fully transparent
so the painted background shows through at every screen size.
"""

import math
import os
import sys
from pathlib import Path
from typing import List

from PyQt6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QTimer, pyqtProperty, pyqtSignal, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QBrush, QColor, QCursor, QLinearGradient, QPainter, QPainterPath, QPaintEvent, QPen, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import C, F, icon

# Max width of the centred cards (px)
_CARD_W = 712


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


def _hash01(value: float) -> float:
    return (math.sin(value * 127.1 + 19.19) * 43758.5453123) % 1.0


class WelcomeWidget(QWidget):
    """Welcome screen shown in the first dataset tab."""

    _LAYER_BASES = (0.22, 0.41, 0.56, 0.68, 0.82, 1.03)
    _LAYER_AMPLITUDES = (0.0040, 0.0054, 0.0047, 0.0040, 0.0035, 0.0)
    _LAYER_FREQUENCIES = (1.36, 1.02, 1.19, 0.93, 0.72, 1.0)
    _LAYER_SPEEDS = (0.60, -0.44, 0.31, -0.23, 0.16, 0.0)
    _LAYER_COLORS = (
        QColor(67, 48, 34),
        QColor(219, 186, 138),
        QColor(222, 160, 79),
        QColor(181, 103, 40),
        QColor(166, 89, 33),
    )
    _GRASS_CLUMPS = (
        (0.11, 0.082, 0.90),
        (0.21, 0.094, 1.05),
        (0.31, 0.088, 0.94),
        (0.45, 0.090, 0.98),
        (0.56, 0.097, 1.10),
        (0.65, 0.074, 0.82),
        (0.74, 0.084, 0.96),
    )
    _STONE_SPECS = (
        (0.035, 0.89, 0.040, 0.030, -18.0),
        (0.085, 0.94, 0.020, 0.018, -8.0),
        (0.148, 0.92, 0.026, 0.024, -12.0),
        (0.287, 0.90, 0.040, 0.034, -10.0),
        (0.368, 0.95, 0.022, 0.020, -16.0),
        (0.442, 0.92, 0.016, 0.014, -10.0),
        (0.528, 0.95, 0.030, 0.028, -12.0),
        (0.585, 0.86, 0.028, 0.030, -6.0),
        (0.732, 0.90, 0.042, 0.034, 8.0),
        (0.788, 0.94, 0.018, 0.016, -6.0),
        (0.846, 0.92, 0.034, 0.032, -14.0),
        (0.930, 0.94, 0.022, 0.020, -10.0),
        (0.972, 0.87, 0.030, 0.028, 10.0),
    )
    _CRACK_SPECS = (
        (0.08, 0.095, -0.020),
        (0.19, 0.070, 0.018),
        (0.33, 0.088, -0.025),
        (0.50, 0.082, 0.020),
        (0.67, 0.100, -0.015),
        (0.81, 0.084, 0.022),
        (0.94, 0.075, -0.012),
    )

    load_files_requested       = pyqtSignal()
    load_sample_data_requested = pyqtSignal()
    open_recent_file_requested = pyqtSignal(str)
    open_recent_session_requested = pyqtSignal(dict)
    open_help_topic_requested  = pyqtSignal(str)
    dont_show_again_changed    = pyqtSignal(bool)
    clear_sessions_requested   = pyqtSignal()

    def __init__(self, recent_files: List[str] = None, recent_sessions: List[dict] = None, parent=None):
        super().__init__(parent)
        self.recent_files = recent_files or []
        self.recent_sessions = recent_sessions or []
        self.setAutoFillBackground(False)
        self._bg_pixmap = self._load_bg_pixmap()
        self._background_phase = 0.0
        self._title_card = None
        self._title_eyebrow = None
        self._title_desc = None
        self._title_attr = None
        self._main_card = None
        self._footer = None
        self._footer_attr = None
        self._outer_scroll = None
        self._resume_btn = None
        self._resume_hint = None
        self._background_timer = QTimer(self)
        self._background_timer.setInterval(40)
        self._background_timer.timeout.connect(self._advance_background)
        if self._bg_pixmap.isNull():
            self._background_timer.start()
        self._setup_ui()

    @staticmethod
    def _load_bg_pixmap() -> QPixmap:
        if getattr(sys, "frozen", False):
            base_dir = Path(sys._MEIPASS) / "Program" / "resources"  # type: ignore[attr-defined]
        else:
            base_dir = Path(__file__).resolve().parent.parent / "resources"

        for name in ("soil_layers_refined.png", "soil_layers.png"):
            img = base_dir / name
            if img.exists():
                px = QPixmap(str(img))
                if not px.isNull():
                    return px
        return QPixmap()

    # ── Background painting ──────────────────────────────────────

    def _advance_background(self) -> None:
        self._background_phase = (self._background_phase + 0.012) % (math.tau * 32.0)
        if self.isVisible():
            self.update()

    def _sample_points(self) -> list[float]:
        points = list(range(-24, self.width() + 25, 18))
        if points[-1] != self.width() + 24:
            points.append(self.width() + 24)
        return [float(x) for x in points]

    def _boundary_y(self, index: int, x: float) -> float:
        width = max(1.0, float(self.width()))
        height = max(1.0, float(self.height()))
        nx = x / width
        phase = self._background_phase * self._LAYER_SPEEDS[index]
        amplitude = height * self._LAYER_AMPLITUDES[index]
        ripple = (
            0.72 * math.sin(nx * math.tau * self._LAYER_FREQUENCIES[index] + phase)
            + 0.28 * math.cos(nx * math.tau * (self._LAYER_FREQUENCIES[index] * 0.58) + phase * 1.16)
        )
        return height * self._LAYER_BASES[index] + amplitude * ripple

    def _layer_path(self, index: int) -> QPainterPath:
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

    def _band_path(self, index: int, fraction: float = 0.0) -> QPainterPath:
        points = self._sample_points()
        path = QPainterPath()
        for point_index, x in enumerate(points):
            top_y = self._boundary_y(index, x)
            bottom_y = self._boundary_y(index + 1, x)
            y = top_y + (bottom_y - top_y) * fraction
            point = QPointF(x, y)
            if point_index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        return path

    def _draw_paper_grain(self, painter: QPainter) -> None:
        width = float(self.width())
        sky_height = float(self.height()) * 0.44

        painter.setPen(Qt.PenStyle.NoPen)
        for speck_index in range(220):
            seed = 700.0 + speck_index * 11.17
            x = width * _hash01(seed + 0.11)
            y = sky_height * _hash01(seed + 0.43)
            radius = 0.35 + _hash01(seed + 0.79) * 0.95

            if speck_index % 3 == 0:
                tone = QColor(255, 248, 234, 9 + int(7 * _hash01(seed + 1.03)))
            else:
                tone = QColor(143, 112, 74, 7 + int(11 * _hash01(seed + 1.27)))

            painter.setBrush(tone)
            painter.drawEllipse(QRectF(x - radius, y - radius, radius * 2.0, radius * 2.0))

    def _draw_soil_grain(self, painter: QPainter, band_index: int, base_color: QColor) -> None:
        width = float(self.width())
        count = 240 if band_index == 0 else 170 if band_index in (1, 2) else 135

        painter.setPen(Qt.PenStyle.NoPen)
        for dot_index in range(count):
            seed = band_index * 91.0 + dot_index * 13.7
            x = width * _hash01(seed + 0.23)
            top = self._boundary_y(band_index, x)
            bottom = self._boundary_y(band_index + 1, x)
            y = top + (bottom - top) * (0.08 + 0.84 * _hash01(seed + 0.57))
            radius_x = 0.45 + _hash01(seed + 0.91) * (1.45 if band_index in (0, 4) else 1.05)
            radius_y = radius_x * (0.66 + 0.28 * _hash01(seed + 1.33))
            shade = _blend(base_color, QColor(56, 41, 29), 0.14 + 0.26 * _hash01(seed + 1.71))
            shade.setAlpha(9 + int(18 * _hash01(seed + 2.11)))
            painter.setBrush(shade)
            painter.drawEllipse(QRectF(x - radius_x, y - radius_y, radius_x * 2.0, radius_y * 2.0))

            if dot_index % 4 == 0:
                light = _blend(base_color, QColor(255, 245, 221), 0.34 + 0.18 * _hash01(seed + 2.53))
                light.setAlpha(8 + int(11 * _hash01(seed + 2.79)))
                painter.setBrush(light)
                painter.drawEllipse(
                    QRectF(
                        x - radius_x * 0.55,
                        y - radius_y * 0.55,
                        radius_x * 1.1,
                        radius_y * 1.1,
                    )
                )

            if band_index in (3, 4) and dot_index % 17 == 0:
                chunk = _with_alpha(QColor(78, 54, 34), 22 + int(16 * _hash01(seed + 3.1)))
                painter.setBrush(chunk)
                painter.drawEllipse(
                    QRectF(
                        x - radius_x * 1.8,
                        y - radius_y * 1.6,
                        radius_x * 3.6,
                        radius_y * 3.2,
                    )
                )

        if band_index in (1, 2, 3):
            painter.setPen(QPen(QColor(255, 255, 255, 10), 0.8))
            painter.drawPath(self._band_path(band_index, 0.33))
            painter.drawPath(self._band_path(band_index, 0.68))

    def _draw_cracks(self, painter: QPainter) -> None:
        width = float(self.width())
        height = float(self.height())
        pen = QPen(QColor(92, 56, 30, 54), 0.9)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for crack_index, (x_ratio, depth_ratio, lean_ratio) in enumerate(self._CRACK_SPECS):
            x = width * x_ratio
            start_y = self._boundary_y(4, x) + 1.5
            sway = math.sin(self._background_phase * 0.45 + crack_index * 0.9) * width * 0.0016
            depth = height * depth_ratio * 0.92
            mid = QPointF(x + width * lean_ratio * 0.26 + sway, start_y + depth * 0.28)
            end = QPointF(x + width * lean_ratio + sway * 1.3, start_y + depth)

            path = QPainterPath(QPointF(x, start_y))
            path.quadTo(mid, end)
            painter.drawPath(path)

            branch_anchor = QPointF(
                x + width * lean_ratio * 0.18 + sway * 0.5,
                start_y + depth * (0.38 + 0.08 * _hash01(crack_index + 0.4)),
            )
            branch_1 = QPainterPath(branch_anchor)
            branch_1.quadTo(
                QPointF(branch_anchor.x() - width * 0.018, branch_anchor.y() + depth * 0.12),
                QPointF(branch_anchor.x() - width * 0.028, branch_anchor.y() + depth * 0.28),
            )
            painter.drawPath(branch_1)

            branch_2 = QPainterPath(branch_anchor)
            branch_2.quadTo(
                QPointF(branch_anchor.x() + width * 0.016, branch_anchor.y() + depth * 0.10),
                QPointF(branch_anchor.x() + width * 0.024, branch_anchor.y() + depth * 0.24),
            )
            painter.drawPath(branch_2)

    def _draw_stones(self, painter: QPainter) -> None:
        width = float(self.width())
        height = float(self.height())

        for stone_index, (x_ratio, y_ratio, w_ratio, h_ratio, angle) in enumerate(self._STONE_SPECS):
            cx = width * x_ratio
            top = self._boundary_y(4, cx)
            cy = max(height * y_ratio, top + height * 0.035)
            stone_w = width * w_ratio
            stone_h = height * h_ratio

            painter.save()
            painter.translate(cx, cy)
            painter.rotate(angle + math.sin(self._background_phase * 0.12 + stone_index) * 0.35)
            rect = QRectF(-stone_w / 2.0, -stone_h / 2.0, stone_w, stone_h)

            fill = QLinearGradient(0, rect.top(), 0, rect.bottom())
            fill.setColorAt(0.0, QColor(156, 123, 82, 212))
            fill.setColorAt(1.0, QColor(126, 96, 60, 222))
            painter.setPen(QPen(QColor(82, 58, 34, 96), 0.8))
            painter.setBrush(QBrush(fill))
            painter.drawEllipse(rect)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 245, 222, 22))
            painter.drawEllipse(rect.adjusted(stone_w * 0.10, stone_h * 0.06, -stone_w * 0.32, -stone_h * 0.42))

            for mote_index in range(3):
                seed = stone_index * 5.0 + mote_index
                mote_x = rect.left() + rect.width() * (0.24 + 0.52 * _hash01(seed + 0.3))
                mote_y = rect.top() + rect.height() * (0.24 + 0.46 * _hash01(seed + 0.7))
                mote_r = rect.height() * (0.05 + 0.06 * _hash01(seed + 1.1))
                painter.setBrush(QColor(99, 73, 44, 32))
                painter.drawEllipse(QRectF(mote_x - mote_r, mote_y - mote_r, mote_r * 2.0, mote_r * 2.0))
            painter.restore()

    def _draw_grass(self, painter: QPainter) -> None:
        width = float(self.width())
        height = float(self.height())

        painter.setPen(QPen(QColor(76, 57, 35, 118), 1.0))
        painter.drawPath(self._band_path(0))

        for clump_index, (x_ratio, height_ratio, scale) in enumerate(self._GRASS_CLUMPS):
            base_x = width * x_ratio
            base_y = self._boundary_y(0, base_x) + 1.0

            for blade_index, offset in enumerate((-11.0, -5.5, 0.0, 5.0, 10.0)):
                blade_height = height * height_ratio * (0.82 + blade_index * 0.06)
                blade_offset = offset * scale
                sway = math.sin(self._background_phase * (0.92 + clump_index * 0.09) + blade_index * 0.62) * width * 0.0034 * scale
                tip = QPointF(base_x + blade_offset * 0.58 + sway, base_y - blade_height)
                left_base = QPointF(base_x + blade_offset * 0.22 - 1.15 * scale, base_y + 1.0)
                right_base = QPointF(base_x + blade_offset * 0.22 + 1.45 * scale, base_y + 1.0)

                blade = QPainterPath(left_base)
                blade.quadTo(
                    QPointF(base_x + blade_offset * 0.14 + sway * 0.22, base_y - blade_height * 0.48),
                    tip,
                )
                blade.quadTo(
                    QPointF(base_x + blade_offset * 0.64 + sway * 0.68 + 2.0 * scale, base_y - blade_height * 0.34),
                    right_base,
                )
                blade.closeSubpath()

                fill = QLinearGradient(left_base, tip)
                fill.setColorAt(0.0, QColor(88, 93, 44, 214))
                fill.setColorAt(0.55, QColor(123, 126, 53, 220))
                fill.setColorAt(1.0, QColor(154, 146, 81, 198))
                painter.fillPath(blade, QBrush(fill))
                painter.setPen(QPen(QColor(74, 73, 34, 34), 0.55))
                painter.drawPath(blade)

        painter.setPen(QPen(QColor(255, 255, 255, 14), 0.9))
        painter.drawPath(self._band_path(0, 0.18))

    def _draw_animated_background(self, painter: QPainter) -> None:
        rect = self.rect()
        width = float(self.width())
        height = float(self.height())

        sky = QLinearGradient(0, 0, 0, height * 0.44)
        sky.setColorAt(0.0, QColor(246, 240, 229))
        sky.setColorAt(0.68, QColor(238, 226, 202))
        sky.setColorAt(1.0, QColor(232, 214, 184))
        painter.fillRect(rect, sky)
        self._draw_paper_grain(painter)

        warm_wash = QLinearGradient(0, 0, width, height)
        warm_wash.setColorAt(0.0, QColor(255, 255, 255, 42))
        warm_wash.setColorAt(0.58, QColor(255, 255, 255, 0))
        warm_wash.setColorAt(1.0, QColor(171, 128, 70, 19))
        painter.fillRect(rect, warm_wash)

        for band_index, base_color in enumerate(self._LAYER_COLORS):
            path = self._layer_path(band_index)
            top_y = self._boundary_y(band_index, width * 0.5)
            bottom_y = self._boundary_y(band_index + 1, width * 0.5)

            gradient = QLinearGradient(0, top_y, 0, bottom_y)
            gradient.setColorAt(0.0, _blend(base_color, QColor(246, 239, 223), 0.11 if band_index else 0.05))
            gradient.setColorAt(0.55, base_color)
            gradient.setColorAt(1.0, _blend(base_color, QColor(69, 50, 33), 0.10 + band_index * 0.025))
            painter.fillPath(path, QBrush(gradient))
            self._draw_soil_grain(painter, band_index, base_color)

            painter.setPen(QPen(QColor(73, 51, 31, 112 if band_index == 0 else 82), 0.9))
            painter.drawPath(self._band_path(band_index))

        self._draw_cracks(painter)
        self._draw_stones(painter)
        self._draw_grass(painter)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_card_widths()
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not self._bg_pixmap.isNull():
            painter.drawPixmap(self.rect(), self._bg_pixmap)
        else:
            self._draw_animated_background(painter)

        # Background is fully procedural now; keep the overlay light for card readability.
            # Stretch to fill — slight distortion is invisible under the overlay
            # Static bitmap backdrop removed.

        # rgba(255,255,255,0.38) white overlay
        painter.fillRect(self.rect(), QColor(255, 255, 255, 88 if not self._bg_pixmap.isNull() else 74))
        painter.end()

    # ── UI Setup ─────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAutoFillBackground(False)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        # Use custom no-paint widgets for viewport and content so the global
        # QSS "QWidget { background-color: C.BG }" cannot paint over our soil image.
        scroll.setViewport(_ClearWidget())

        content = _ClearWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(10, 10, 10, 6)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._title_card = self._build_title_card()
        self._main_card = self._build_main_card()
        self._footer = self._build_footer()

        lay.addWidget(self._title_card, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._main_card,  0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._footer,     0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self._outer_scroll = scroll
        self._sync_card_widths()

    # ── Title card ───────────────────────────────────────────────

    def _build_title_card(self) -> QFrame:
        return self._build_title_card_concept_v2()

    def _build_title_card_concept(self) -> QFrame:
        card = QFrame()
        card.setObjectName("wlc-title")
        card.setStyleSheet("""
            QFrame#wlc-title {
                background: rgba(255,255,255,56);
                border: 1px solid rgba(255,255,255,97);
                border-radius: 8px;
            }
        """)
        card.setMaximumWidth(_CARD_W)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(22, 13, 22, 11)
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # ── Logo mark ──────────────────────────────────────────────
        mark = QFrame()
        mark.setObjectName("wlc-mark")
        mark.setFixedSize(42, 42)
        mark.setStyleSheet("""
            QFrame#wlc-mark {
                background: rgba(107,142,35,180);
                border: 1.5px solid rgba(107,142,35,220);
                border-radius: 10px;
            }
        """)
        m_lay = QHBoxLayout(mark)
        m_lay.setContentsMargins(0, 0, 0, 0)
        m_ico = QLabel()
        m_ico.setPixmap(icon("fa6s.layer-group", "#ffffff").pixmap(QSize(18, 18)))
        m_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        m_ico.setStyleSheet("background: transparent; border: none;")
        m_lay.addWidget(m_ico, 0, Qt.AlignmentFlag.AlignCenter)

        mark_wrap = QWidget()
        mark_wrap.setStyleSheet("background: transparent; border: none;")
        mw_lay = QHBoxLayout(mark_wrap)
        mw_lay.setContentsMargins(0, 0, 0, 0)
        mw_lay.addStretch()
        mw_lay.addWidget(mark)
        mw_lay.addStretch()
        lay.addWidget(mark_wrap)
        lay.addSpacing(12)

        # ── Title ──────────────────────────────────────────────────
        title = QLabel("Grain Size Analysis")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f'color: {C.TEXT}; font-family: "{F.DISP}"; font-size: {F.SZ_2XL}pt;'
            ' font-weight: 700; letter-spacing: 0.02em; background: transparent;'
        )
        lay.addWidget(title)
        lay.addSpacing(4)

        sub = QLabel("Hydraulic Conductivity Calculator")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_LG}pt; font-weight: 600;"
            " background: transparent;"
        )
        lay.addWidget(sub)
        lay.addSpacing(14)

        # ── Divider ────────────────────────────────────────────────
        div = QFrame()
        div.setObjectName("wlc-div")
        div.setFixedHeight(1)
        div.setStyleSheet("QFrame#wlc-div { background: rgba(139,115,85,50); border: none; }")
        lay.addWidget(div)
        lay.addSpacing(12)

        # ── Feature chips ──────────────────────────────────────────
        chips_w = QWidget()
        chips_w.setStyleSheet("background: transparent; border: none;")
        chips_lay = QHBoxLayout(chips_w)
        chips_lay.setContentsMargins(0, 0, 0, 0)
        chips_lay.setSpacing(8)
        chips_lay.addStretch()

        for chip_ico, chip_txt in [
            ("fa6s.vial",        "16 K-Methods"),
            ("fa6s.chart-line",  "D-values & Gradation"),
            ("fa6s.file-export", "Batch Export"),
        ]:
            chip = QWidget()
            chip.setObjectName("wlc-chip")
            chip.setStyleSheet("""
                QWidget#wlc-chip {
                    background: rgba(107,142,35,55);
                    border: 1px solid rgba(107,142,35,130);
                    border-radius: 99px;
                }
            """)
            c_lay = QHBoxLayout(chip)
            c_lay.setContentsMargins(9, 4, 9, 4)
            c_lay.setSpacing(5)

            c_ico = QLabel()
            c_ico.setPixmap(icon(chip_ico, C.OLIVE).pixmap(QSize(10, 10)))
            c_ico.setStyleSheet("background: transparent; border: none;")

            c_txt = QLabel(chip_txt)
            c_txt.setStyleSheet(
                f"color: {C.OLIVE_DK}; font-size: {F.SZ_XS}pt; font-weight: 700;"
                " background: transparent; border: none;"
            )
            c_lay.addWidget(c_ico)
            c_lay.addWidget(c_txt)
            chips_lay.addWidget(chip)

        chips_lay.addStretch()
        lay.addWidget(chips_w)
        lay.addSpacing(10)

        # ── Version ────────────────────────────────────────────────
        ver = QLabel("v0.9.0-beta")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(
            f"color: {C.TEXT_MID}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: transparent;"
        )
        lay.addWidget(ver)
        return card

    # ── Main card ────────────────────────────────────────────────

    def _build_title_card_concept_v2(self) -> QFrame:
        card = QFrame()
        card.setObjectName("wlc-title-concept")
        card.setStyleSheet("""
            QFrame#wlc-title-concept {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(252,250,245,196),
                    stop:1 rgba(247,242,233,176)
                );
                border: 1px solid rgba(255,255,255,132);
                border-radius: 12px;
            }
        """)
        card.setMaximumWidth(_CARD_W)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 12)
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignmentFlag.AlignLeft)

        meta_row = QWidget()
        meta_row.setStyleSheet("background: transparent; border: none;")
        meta_lay = QHBoxLayout(meta_row)
        meta_lay.setContentsMargins(0, 0, 0, 0)
        meta_lay.setSpacing(8)

        eyebrow = QLabel("BATCH WORKSPACE")
        eyebrow.setStyleSheet(
            f"color: {C.OLIVE_DK}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " font-weight: 700; letter-spacing: 0.16em; background: transparent; border: none;"
        )
        self._title_eyebrow = eyebrow
        meta_lay.addWidget(eyebrow)
        meta_lay.addStretch()

        ver = QLabel("v0.9.0-beta")
        ver.setStyleSheet(
            f"color: {C.TEXT_MID}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: rgba(255,255,255,122); border: 1px solid rgba(120,95,60,36);"
            " border-radius: 99px; padding: 2px 8px;"
        )
        meta_lay.addWidget(ver)
        lay.addWidget(meta_row)
        lay.addSpacing(6)

        title = QLabel("Grain Size Analysis")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title.setStyleSheet(
            f'color: {C.TEXT}; font-family: "{F.DISP}"; font-size: 21pt;'
            ' font-weight: 700; letter-spacing: 0.01em; background: transparent; border: none;'
        )
        lay.addWidget(title)
        lay.addSpacing(1)

        sub = QLabel("Hydraulic Conductivity Calculator")
        sub.setAlignment(Qt.AlignmentFlag.AlignLeft)
        sub.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_MD}pt; font-weight: 600;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sub)
        lay.addSpacing(6)

        desc = QLabel(
            "Load batches, return to recent workspaces, compare selected datasets, and export the chosen scope."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt; line-height: 1.35;"
            " background: transparent; border: none;"
        )
        self._title_desc = desc
        lay.addWidget(desc)
        lay.addSpacing(8)

        attr = QLabel("Batch import  ·  session restore  ·  selected-scope export")
        attr.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: transparent; border: none;"
        )
        self._title_attr = attr
        lay.addWidget(attr)
        lay.addSpacing(6)

        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background: rgba(107,142,35,72); border: none;")
        lay.addWidget(rule)
        return card

    def _build_main_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("wlc-card")
        card.setStyleSheet("""
            QFrame#wlc-card {
                background: rgba(249,246,240,245);
                border: 1px solid rgba(180,160,130,86);
                border-radius: 12px;
            }
        """)
        card.setMaximumWidth(_CARD_W)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        grid = QGridLayout(card)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        grid.addWidget(
            self._build_section("fa6s.bolt", "Quick Actions",
                                self._build_actions(),
                                accent=C.OLIVE), 0, 0, 1, 2
        )
        grid.addWidget(
            self._build_section("fa6s.clock-rotate-left", "Recent Sessions",
                                self._build_recent(), clear_btn=True,
                                accent=C.EARTH), 1, 0
        )
        grid.addWidget(
            self._build_section("fa6s.seedling", "What's New",
                                self._build_whats_new(),
                                accent=C.OLIVE), 1, 1
        )
        grid.addWidget(
            self._build_section("fa6s.book-open", "Guides",
                                self._build_help(),
                                accent=C.AMBER), 2, 0, 1, 2
        )
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        return card

    # ── Section box ──────────────────────────────────────────────

    def _build_section(self, icon_name: str, title: str, content: QWidget,
                       clear_btn: bool = False, accent: str = None) -> QFrame:
        return self._build_section_concept_v3(
            icon_name=icon_name,
            title=title,
            content=content,
            clear_btn=clear_btn,
            accent=accent,
        )

    def _build_section_concept_v2(self, icon_name: str, title: str, content: QWidget,
                                  clear_btn: bool = False, accent: str = None) -> QFrame:
        _accent = accent or C.BORDER
        sec = QFrame()
        sec.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sec.setStyleSheet(f"""
            QFrame {{
                background: #f9f7f3;
                border: 1px solid {C.BORDER};
                border-top: 3px solid {_accent};
                border-radius: 6px;
            }}
        """)

        lay = QVBoxLayout(sec)
        lay.setContentsMargins(0, 0, 0, 10)
        lay.setSpacing(8)

        # ── Header band ────────────────────────────────────────────
        hdr_band = QWidget()
        hdr_band.setStyleSheet(
            f"background: rgba(180,160,130,14); border: none; border-radius: 0px;"
        )
        hdr_band_lay = QHBoxLayout(hdr_band)
        hdr_band_lay.setContentsMargins(10, 8, 10, 8)
        hdr_band_lay.setSpacing(8)

        # Coloured icon pill
        ico_pill = QFrame()
        ico_pill.setFixedSize(22, 22)
        ico_pill.setStyleSheet(f"""
            QFrame {{
                background: {_accent};
                border-radius: 5px;
                border: none;
            }}
        """)
        ico_pill_lay = QHBoxLayout(ico_pill)
        ico_pill_lay.setContentsMargins(0, 0, 0, 0)
        ico_lbl = QLabel()
        ico_lbl.setPixmap(icon(icon_name, "#ffffff").pixmap(QSize(11, 11)))
        ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico_lbl.setStyleSheet("background: transparent; border: none;")
        ico_pill_lay.addWidget(ico_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        ttl_lbl = QLabel(title)
        ttl_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_LG}pt; font-weight: 700;"
            f" letter-spacing: 0.02em; background: transparent; border: none;"
        )

        hdr_band_lay.addWidget(ico_pill)
        hdr_band_lay.addWidget(ttl_lbl)
        hdr_band_lay.addStretch()

        if clear_btn:
            clr = QPushButton("Clear")
            clr.setIcon(icon("fa6s.trash-can", C.EARTH))
            clr.setFixedHeight(22)
            clr.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            clr.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(139,115,85,28);
                    color: {C.EARTH};
                    border: 1px solid rgba(139,115,85,90);
                    border-radius: 3px;
                    padding: 0 8px;
                    font-size: 9pt;
                }}
                QPushButton:hover {{
                    background: rgba(139,115,85,55);
                    color: {C.TEXT_MID};
                }}
            """)
            clr.clicked.connect(self.clear_sessions_requested.emit)
            hdr_band_lay.addWidget(clr)

        lay.addWidget(hdr_band)

        # Content with side padding
        content_wrap = QWidget()
        content_wrap.setStyleSheet("background: transparent; border: none;")
        cw_lay = QVBoxLayout(content_wrap)
        cw_lay.setContentsMargins(10, 0, 10, 0)
        cw_lay.setSpacing(0)
        cw_lay.addWidget(content, 1)

        lay.addWidget(content_wrap, 1)
        return sec

    # ── Recent Sessions ──────────────────────────────────────────

    def _build_section_concept_v3(self, icon_name: str, title: str, content: QWidget,
                                  clear_btn: bool = False, accent: str = None) -> QFrame:
        _accent = accent or C.BORDER
        sec = QFrame()
        sec.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sec.setStyleSheet(f"""
            QFrame {{
                background: rgba(255,255,255,126);
                border: 1px solid rgba(210,196,172,0.92);
                border-radius: 10px;
            }}
        """)

        lay = QVBoxLayout(sec)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(8)

        ico_tile = QFrame()
        ico_tile.setFixedSize(24, 24)
        ico_tile.setStyleSheet(
            "background: rgba(255,255,255,148); border: 1px solid rgba(0,0,0,0); border-radius: 7px;"
        )
        ico_tile_lay = QHBoxLayout(ico_tile)
        ico_tile_lay.setContentsMargins(0, 0, 0, 0)

        ico_lbl = QLabel()
        ico_lbl.setPixmap(icon(icon_name, _accent).pixmap(QSize(12, 12)))
        ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico_lbl.setStyleSheet("background: transparent; border: none;")
        ico_tile_lay.addWidget(ico_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        ttl_lbl = QLabel(title)
        ttl_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_MD}pt; font-weight: 700;"
            " background: transparent; border: none;"
        )

        header_lay.addWidget(ico_tile)
        header_lay.addWidget(ttl_lbl)
        header_lay.addStretch()

        if clear_btn:
            clr = QPushButton("Clear")
            clr.setIcon(icon("fa6s.trash-can", C.EARTH))
            clr.setFixedHeight(22)
            clr.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            clr.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(139,115,85,22);
                    color: {C.EARTH};
                    border: 1px solid rgba(139,115,85,84);
                    border-radius: 99px;
                    padding: 0 8px;
                    font-size: {F.SZ_XS}pt;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: rgba(139,115,85,40);
                    color: {C.TEXT};
                }}
            """)
            clr.clicked.connect(self.clear_sessions_requested.emit)
            header_lay.addWidget(clr)

        lay.addWidget(header)
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: rgba(212,196,168,0.65); border: none;")
        lay.addWidget(divider)
        lay.addWidget(content, 0, Qt.AlignmentFlag.AlignTop)
        lay.addStretch(1)
        return sec

    def _build_recent(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(168)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 5px; }}
            QScrollBar::handle:vertical {{ background: {C.BORDER}; border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        sc = QWidget()
        sc.setStyleSheet("background: transparent; border: none;")
        sc_lay = QVBoxLayout(sc)
        sc_lay.setContentsMargins(0, 0, 3, 0)
        sc_lay.setSpacing(6)

        if self.recent_sessions:
            for index, s in enumerate(self.recent_sessions[:4]):
                sc_lay.addWidget(self._build_session_row(s, is_latest=index == 0))
        else:
            empty = QLabel("No saved sessions yet")
            empty.setStyleSheet(
                f"color: {C.TEXT_MUTED}; font-size: {F.SZ_BASE}pt;"
                " background: transparent; border: none; padding: 14px 6px;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sc_lay.addWidget(empty)

            hint = QLabel("Load a batch once and it will appear here for quick return.")
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(
                f"color: {C.TEXT_MUTED}; font-size: {F.SZ_XS}pt;"
                " background: transparent; border: none; padding: 0 16px 8px 16px;"
            )
            sc_lay.addWidget(hint)

        sc_lay.addStretch()
        scroll.setWidget(sc)
        lay.addWidget(scroll)

        return w

    def _build_session_row(self, s: dict, is_latest: bool = False) -> QFrame:
        """One recent-session entry with stronger hierarchy and hover feedback."""
        files = s.get("files", [])
        date  = s.get("date", "")
        name  = s.get("name", "Unnamed Session")
        n     = len(files)

        row = _HoverFrame()
        row.setObjectName("rec-row")
        row.setStyleSheet(f"""
            QFrame#rec-row {{
                background: rgba(255,255,255,186);
                border: 1px solid rgba(212,196,168,0.82);
                border-left: 3px solid {C.EARTH};
                border-radius: 8px;
            }}
            QFrame#rec-row[hovered="true"] {{
                background: rgba(255,255,255,232);
                border-color: rgba(160,138,108,0.92);
            }}
        """)
        row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        row.setProperty("hovered", False)

        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(10, 8, 10, 8)
        row_lay.setSpacing(10)

        ico_tile = QFrame()
        ico_tile.setFixedSize(28, 28)
        ico_tile.setStyleSheet(
            f"background: rgba(139,115,85,20); border: 1px solid rgba(139,115,85,50); border-radius: 8px;"
        )
        ico_lay = QHBoxLayout(ico_tile)
        ico_lay.setContentsMargins(0, 0, 0, 0)

        ico = QLabel()
        ico.setPixmap(icon("fa6s.folder-open", C.EARTH).pixmap(QSize(14, 14)))
        ico.setStyleSheet("background: transparent; border: none;")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico_lay.addWidget(ico, 0, Qt.AlignmentFlag.AlignCenter)

        tx = QWidget()
        tx.setStyleSheet("background: transparent; border: none;")
        tx_lay = QVBoxLayout(tx)
        tx_lay.setContentsMargins(0, 0, 0, 0)
        tx_lay.setSpacing(3)

        title_row = QWidget()
        title_row.setStyleSheet("background: transparent; border: none;")
        tr_lay = QHBoxLayout(title_row)
        tr_lay.setContentsMargins(0, 0, 0, 0)
        tr_lay.setSpacing(6)

        nm_lbl = QLabel(name)
        nm_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_BASE}pt; font-weight: 700;"
            " background: transparent; border: none;"
        )
        tr_lay.addWidget(nm_lbl)

        if is_latest:
            latest = QLabel("Latest")
            latest.setStyleSheet(
                f"color: {C.OLIVE_DK}; background: rgba(107,142,35,20);"
                " border: 1px solid rgba(107,142,35,70); border-radius: 99px;"
                f" padding: 1px 6px; font-family: '{F.MONO}'; font-size: {F.SZ_XS - 1}pt; font-weight: 700;"
            )
            tr_lay.addWidget(latest)
        tr_lay.addStretch()

        meta_parts = [f"{n} dataset{'s' if n != 1 else ''}"]
        if date:
            meta_parts.append(date)
        meta_lbl = QLabel("  ·  ".join(meta_parts))
        meta_lbl.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: transparent; border: none;"
        )

        tx_lay.addWidget(title_row)
        tx_lay.addWidget(meta_lbl)

        chev = QLabel()
        chev.setPixmap(icon("fa6s.chevron-right", C.TEXT_MUTED).pixmap(QSize(9, 9)))
        chev.setStyleSheet("background: transparent; border: none;")
        chev.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        row_lay.addWidget(ico_tile)
        row_lay.addWidget(tx, 1)
        row_lay.addWidget(chev)

        row.clicked.connect(lambda session=dict(s): self.open_recent_session_requested.emit(session))
        return row

    # ── What's New ───────────────────────────────────────────────

    def _build_whats_new(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(132)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 5px; }}
            QScrollBar::handle:vertical {{ background: {C.BORDER}; border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        sc = QWidget()
        sc.setStyleSheet("background: transparent;")
        sc_lay = QVBoxLayout(sc)
        sc_lay.setContentsMargins(0, 0, 3, 0)
        sc_lay.setSpacing(9)

        for index, v in enumerate([
            {"version": "v0.9.0-beta",  "date": "2025-01-15", "changes": [
                "New batch export flow with scope selection",
                "Wide format CSV export for statistical analysis",
                "Enhanced welcome screen with recent sessions",
            ]},
            {"version": "v0.8.0-alpha", "date": "2024-12-20", "changes": [
                "Added comparison tab for multiple datasets",
                "Improved calculation methods validation",
                "Bug fixes for column mapping",
            ]},
            {"version": "v0.7.0-alpha", "date": "2024-11-30", "changes": [
                "New help system with comprehensive guides",
                "Enhanced reporting tab with templates",
                "Performance improvements for large datasets",
            ]},
            {"version": "v0.6.0-alpha", "date": "2024-11-10", "changes": [
                "Added statistics tab with grain analysis",
                "Improved porosity calculation methods",
                "New plot customization options",
            ]},
        ]):
            blk = QFrame()
            blk.setStyleSheet(
                "background: transparent; border: none;"
                if index else
                f"background: rgba(107,142,35,14); border: 1px solid rgba(107,142,35,45); border-radius: 8px;"
            )
            blk_lay = QVBoxLayout(blk)
            blk_lay.setContentsMargins(8 if index == 0 else 0, 8 if index == 0 else 0, 8 if index == 0 else 0, 8 if index == 0 else 0)
            blk_lay.setSpacing(2)

            hdr_row = QWidget()
            hdr_row.setStyleSheet("background: transparent; border: none;")
            hr_lay = QHBoxLayout(hdr_row)
            hr_lay.setContentsMargins(0, 0, 0, 0)
            hr_lay.setSpacing(5)

            ver_pill = QLabel(v["version"])
            ver_pill.setStyleSheet(
                f"color: white; background: {C.OLIVE}; font-size: {F.SZ_XS}pt;"
                f" font-weight: 700; padding: 1px 7px; border-radius: 99px; border: none;"
            )
            date_lbl = QLabel(v["date"])
            date_lbl.setStyleSheet(
                f"color: {C.TEXT_MUTED}; font-size: {F.SZ_XS}pt;"
                " background: transparent; border: none;"
            )

            hr_lay.addWidget(ver_pill)
            hr_lay.addWidget(date_lbl)
            hr_lay.addStretch()
            blk_lay.addWidget(hdr_row)

            for ch in v["changes"]:
                ch_lbl = QLabel(f"• {ch}")
                ch_lbl.setStyleSheet(
                    f"color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt; padding-left: 10px;"
                    " background: transparent; border: none;"
                )
                ch_lbl.setWordWrap(True)
                blk_lay.addWidget(ch_lbl)

            sc_lay.addWidget(blk)

        sc_lay.addStretch()
        scroll.setWidget(sc)
        lay.addWidget(scroll, 1)

        btn = QPushButton("View Full Changelog")
        btn.setIcon(icon("fa6s.book-open", C.OLIVE))
        btn.setFixedHeight(28)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,122);
                border: 1px solid rgba(107,142,35,87);
                border-radius: 99px;
                color: {C.OLIVE};
                font-size: {F.SZ_SM}pt;
                padding: 4px 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: rgba(107,142,35,20); }}
        """)
        btn.clicked.connect(self._open_full_changelog)
        lay.addWidget(btn)
        return w

    # ── Quick Help ───────────────────────────────────────────────

    def _build_help(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        grid = QGridLayout(w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(5)

        for (name, file, ico_name), (r, c) in zip(
            [
                ("Getting Started", "getting_started.html",  "fa6s.circle-play"),
                ("File Formats",    "file_formats.html",     "fa6s.file-csv"),
                ("Methods",         "methods_overview.html", "fa6s.flask"),
                ("Troubleshoot",    "troubleshooting.html",  "fa6s.screwdriver-wrench"),
            ],
            [(0, 0), (0, 1), (1, 0), (1, 1)],
        ):
            btn = QPushButton(name)
            btn.setIcon(icon(ico_name, C.AMBER))
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(30)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,114);
                    border: 1px solid rgba(196,165,116,100);
                    border-radius: 8px;
                    color: {C.TEXT_MID};
                    font-size: {F.SZ_SM}pt;
                    font-weight: 500;
                    padding: 6px 8px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: rgba(196,165,116,24);
                    border-color: rgba(196,165,116,160);
                    color: {C.TEXT};
                }}
            """)
            btn.clicked.connect(lambda ch, f=file: self.open_help_topic_requested.emit(f))
            grid.addWidget(btn, r, c)

        return w

    # ── Quick Actions ────────────────────────────────────────────

    def _build_actions(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QGridLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(8)
        lay.setVerticalSpacing(8)

        load_btn = QPushButton("Load Batch Files")
        load_btn.setIcon(icon("fa6s.folder-open", "#ffffff"))
        load_btn.setMinimumHeight(34)
        load_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        load_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        load_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.OLIVE};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 9px 18px;
                font-size: {F.SZ_LG}pt;
                font-weight: 600;
            }}
            QPushButton:hover   {{ background: {C.OLIVE_H}; }}
            QPushButton:pressed {{ background: {C.OLIVE_DK}; }}
        """)
        load_btn.clicked.connect(self.load_files_requested.emit)
        lay.addWidget(load_btn, 0, 0, 1, 2)

        resume_btn = QPushButton("Resume Latest Session")
        resume_btn.setIcon(icon("fa6s.clock-rotate-left", C.TEXT_MID))
        resume_btn.setMinimumHeight(32)
        resume_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        resume_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        resume_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,170);
                color: {C.TEXT_MID};
                border: 1.5px solid {C.BORDER_DK};
                border-radius: 8px;
                padding: 7px 18px;
                font-size: {F.SZ_BASE}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {C.EARTH};
                color: {C.EARTH};
                background: rgba(210,180,140,46);
            }}
            QPushButton:disabled {{
                color: {C.TEXT_MUTED};
                border-color: rgba(212,196,168,0.65);
                background: rgba(255,255,255,120);
            }}
        """)
        resume_btn.setEnabled(bool(self.recent_sessions))
        resume_btn.clicked.connect(self._resume_latest_session)
        self._resume_btn = resume_btn
        lay.addWidget(resume_btn, 1, 0)

        demo_btn = QPushButton("Open Demo Sample")
        demo_btn.setIcon(icon("fa6s.vial", C.OLIVE_DK))
        demo_btn.setMinimumHeight(32)
        demo_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        demo_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        demo_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,142);
                color: {C.TEXT_MID};
                border: 1px solid rgba(107,142,35,88);
                border-radius: 8px;
                padding: 7px 16px;
                font-size: {F.SZ_BASE}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(107,142,35,18);
                color: {C.OLIVE_DK};
                border-color: rgba(107,142,35,132);
            }}
        """)
        demo_btn.clicked.connect(self.load_sample_data_requested.emit)
        lay.addWidget(demo_btn, 1, 1)

        latest_name = self.recent_sessions[0].get("name", "Latest session") if self.recent_sessions else "No saved session yet"
        note = QLabel(
            f"Latest workspace: {latest_name}" if self.recent_sessions
            else "No saved workspace yet. Load files or open the demo sample to begin."
        )
        note.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt;"
            " background: transparent; border: none;"
        )
        note.setWordWrap(True)
        self._resume_hint = note
        lay.addWidget(note, 2, 0, 1, 2)
        return w

    # ── Footer ───────────────────────────────────────────────────

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        w.setMaximumWidth(_CARD_W)
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)

        self.dont_show_checkbox = QCheckBox(
            "Don't show this welcome screen on startup"
        )
        self.dont_show_checkbox.setStyleSheet(
            f"color: rgba(80,60,30,191); font-size: {F.SZ_SM}pt; background: transparent;"
        )
        self.dont_show_checkbox.stateChanged.connect(
            lambda state: self.dont_show_again_changed.emit(
                state == Qt.CheckState.Checked.value
            )
        )
        lay.addWidget(self.dont_show_checkbox)
        lay.addStretch()

        self._footer_attr = QLabel("Batch import · compare selected · export chosen scope")
        self._footer_attr.setStyleSheet(
            f"color: rgba(80,60,30,140); font-family: '{F.MONO}'; font-size: {F.SZ_XS - 1}pt;"
            " background: rgba(255,255,255,140); padding: 2px 8px; border-radius: 3px;"
        )
        lay.addWidget(self._footer_attr)
        return w

    # ── Helpers ──────────────────────────────────────────────────

    def _sync_card_widths(self):
        if self.width() <= 0:
            return

        target = min(_CARD_W, max(280, self.width() - 40))
        compact_height = self.height() < 760
        for widget in (self._title_card, self._main_card, self._footer):
            if widget is not None:
                widget.setFixedWidth(target)

        if self._title_desc is not None:
            self._title_desc.setVisible(not compact_height)
        if self._title_attr is not None:
            self._title_attr.setVisible(not compact_height)
        if self._title_eyebrow is not None:
            self._title_eyebrow.setVisible(not compact_height)
        if self._footer_attr is not None:
            self._footer_attr.setVisible(not compact_height)
            if target < 620:
                self._footer_attr.setText("Batch import · compare · export")
            else:
                self._footer_attr.setText("Batch import · compare selected · export chosen scope")

    def _resume_latest_session(self):
        if self.recent_sessions:
            self.open_recent_session_requested.emit(dict(self.recent_sessions[0]))
        else:
            self.load_files_requested.emit()

    def _load_session_files(self, files: List[str]):
        for f in files:
            if os.path.exists(f):
                self.open_recent_file_requested.emit(f)

    def _open_full_changelog(self):
        changelog_path = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
        if changelog_path.exists():
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(changelog_path)))
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Changelog",
                f"Changelog will be at:\n{changelog_path}\n\nCurrently in development.",
            )

    def update_recent_files(self, recent_files: List[str]):
        """Called by main_window; full refresh is handled by _refresh_welcome_widget."""
        self.recent_files = recent_files

    def update_recent_sessions(self, recent_sessions: List[dict]):
        """Called by main_window; full refresh is handled by _refresh_welcome_widget."""
        self.recent_sessions = recent_sessions


class _ClearWidget(QWidget):
    """QWidget that never paints its own background.

    Overriding paintEvent to skip super() prevents the global QSS rule
    ``QWidget { background-color: C.BG }`` from drawing a solid fill that
    would cover the parent WelcomeWidget's painted soil-image background.
    Child widgets (cards) still paint themselves normally on top.
    """

    def paintEvent(self, event: QPaintEvent):  # noqa: N802
        pass  # intentionally empty — parent's painted background shows through


class _HoverFrame(QFrame):
    """Hover-aware frame for interactive welcome-screen rows."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._hover_mix = 0.0
        self._pressed = False
        self._hover_anim = QPropertyAnimation(self, b"hoverMix", self)
        self._hover_anim.setDuration(140)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def enterEvent(self, event):
        self.setProperty("hovered", True)
        self.style().unpolish(self)
        self.style().polish(self)
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)
        self._pressed = False
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_pressed = self._pressed
            self._pressed = False
            self.update()
            if was_pressed and self.rect().contains(event.pos()):
                self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._hover_mix <= 0.0 and not self._pressed:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        overlay_alpha = int(16 * self._hover_mix) + (10 if self._pressed else 0)
        border_alpha = int(26 * self._hover_mix) + (14 if self._pressed else 0)
        accent_alpha = int(40 * self._hover_mix) + (20 if self._pressed else 0)

        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        overlay = QColor(255, 255, 255, min(52, overlay_alpha))
        border = QColor(QColor(C.OLIVE))
        border.setAlpha(min(88, border_alpha))
        accent = QColor(QColor(C.OLIVE))
        accent.setAlpha(min(110, accent_alpha))

        painter.setPen(border)
        painter.setBrush(overlay)
        painter.drawRoundedRect(rect, 8.0, 8.0)
        painter.fillRect(QRectF(rect.left() + 1.5, rect.top() + 1.5, 2.5, rect.height() - 3.0), accent)

    def _animate_hover(self, target: float) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_mix)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def _get_hover_mix(self) -> float:
        return self._hover_mix

    def _set_hover_mix(self, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        if abs(self._hover_mix - value) > 0.001:
            self._hover_mix = value
            self.update()

    hoverMix = pyqtProperty(float, fget=_get_hover_mix, fset=_set_hover_mix)
