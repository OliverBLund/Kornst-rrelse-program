"""
Custom toggle switch widget matching the design concept's .toggle-sw style.

26×14px track with a 10px white knob that slides between off (left) and on (right).
Off: C.BORDER track. On: C.OLIVE track. Animated 150ms.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, pyqtProperty, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QPainter, QColor, QPen

from .theme import C


class ToggleSwitch(QWidget):
    """Animated toggle switch — 26×14 track, 10px white knob."""

    toggled = pyqtSignal(bool)

    TRACK_W = 26
    TRACK_H = 14
    KNOB_D = 10
    KNOB_PAD = 2
    TRAVEL = 12  # translateX distance

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._offset = float(self.TRAVEL if checked else 0)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.TRACK_W, self.TRACK_H)

        self._anim = QPropertyAnimation(self, b"offset")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    # ── Animated property ──────────────────────────────────────

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float):
        self._offset = value
        self.update()

    offset = pyqtProperty(float, _get_offset, _set_offset)

    # ── Public API ─────────────────────────────────────────────

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = True):
        if checked == self._checked:
            return
        self._checked = checked
        target = float(self.TRAVEL if checked else 0)
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._offset)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._offset = target
            self.update()
        self.toggled.emit(checked)

    # ── Events ─────────────────────────────────────────────────

    def mousePressEvent(self, event):
        self.setChecked(not self._checked)

    def sizeHint(self):
        return QSize(self.TRACK_W, self.TRACK_H)

    # ── Paint ──────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track
        ratio = self._offset / self.TRAVEL
        off_color = QColor(C.BORDER)
        on_color = QColor(C.OLIVE)
        r = off_color.red() + int((on_color.red() - off_color.red()) * ratio)
        g = off_color.green() + int((on_color.green() - off_color.green()) * ratio)
        b = off_color.blue() + int((on_color.blue() - off_color.blue()) * ratio)
        track_color = QColor(r, g, b)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(0, 0, self.TRACK_W, self.TRACK_H,
                          self.TRACK_H / 2, self.TRACK_H / 2)

        # Knob
        knob_x = self.KNOB_PAD + self._offset
        knob_y = self.KNOB_PAD
        p.setBrush(QColor("#ffffff"))
        p.setPen(Qt.PenStyle.NoPen)
        # subtle shadow
        shadow = QColor(0, 0, 0, 40)
        p.setBrush(shadow)
        p.drawEllipse(int(knob_x), int(knob_y) + 1, self.KNOB_D, self.KNOB_D)
        # white knob
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(int(knob_x), int(knob_y), self.KNOB_D, self.KNOB_D)

        p.end()
