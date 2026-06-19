"""
Lightweight in-window guided tour overlay.

The tour is intentionally generic: callers provide late-bound target widgets, so
the same overlay can later drive global, tab-specific, and dialog-specific tours.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from PyQt6.QtCore import QEvent, QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QApplication,
)

from gui.theme import C, F, SZ


TargetResolver = Callable[[], QWidget | None]
StepCallback = Callable[[], None]


@dataclass(frozen=True)
class TourStep:
    title: str
    body: str
    target: TargetResolver
    tips: tuple[str, ...] = field(default_factory=tuple)
    kicker: str = "Startup guide"
    before_step: StepCallback | None = None


class StartupTourOverlay(QWidget):
    """Dim the host window, spotlight one target widget, and show step copy."""

    finished = pyqtSignal(bool)  # do_not_show_again

    def __init__(
        self,
        parent: QWidget,
        steps: Iterable[TourStep],
        *,
        show_startup_checkbox: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("startup-tour-overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._steps = list(steps)
        self._index = 0
        self._spotlight_rect = QRect()
        self._target_rect = QRect()
        self._show_startup_checkbox = show_startup_checkbox

        self._build_callout()
        parent.installEventFilter(self)
        self.hide()

    def start(self, index: int = 0) -> None:
        if not self._steps:
            return
        parent = self.parentWidget()
        if parent is None:
            return
        self.setGeometry(parent.rect())
        self.raise_()
        self.show()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self._show_step(index)

    def close_tour(self) -> None:
        self.hide()
        self.finished.emit(
            self._dont_show_check.isVisible() and self._dont_show_check.isChecked()
        )

    def eventFilter(self, watched, event) -> bool:
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
            self._position_current_step()
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_tour()
            return
        if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._next()
            return
        if event.key() == Qt.Key.Key_Left:
            self._back()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        overlay = QPainterPath()
        overlay.addRect(QRectF(self.rect()))

        if not self._spotlight_rect.isNull():
            cutout = QPainterPath()
            cutout.addRoundedRect(QRectF(self._spotlight_rect), 8, 8)
            overlay = overlay.subtracted(cutout)

        painter.fillPath(overlay, QColor(36, 29, 20, 166))

        if not self._spotlight_rect.isNull():
            painter.setPen(QPen(QColor(255, 253, 248, 240), 2))
            painter.drawRoundedRect(self._spotlight_rect, 8, 8)
            outer = self._spotlight_rect.adjusted(-5, -5, 5, 5)
            painter.setPen(QPen(QColor(107, 142, 35, 90), 3))
            painter.drawRoundedRect(outer, 12, 12)

    def _build_callout(self) -> None:
        self._callout = QFrame(self)
        self._callout.setObjectName("startup-tour-callout")
        self._callout.setFixedWidth(360)
        self._callout.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        self._callout.setStyleSheet(f"""
            QFrame#startup-tour-callout {{
                background: #fffdf8;
                border: 1px solid rgba(120,95,60,0.45);
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QPushButton {{
                background: #fffdf8;
                border: 1px solid {C.BORDER_DK};
                border-radius: {SZ.BORDER_RADIUS}px;
                color: {C.TEXT};
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                font-weight: 700;
                min-height: 26px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background: #ffffff;
                border-color: {C.EARTH};
            }}
            QPushButton[primary="true"] {{
                background: {C.OLIVE};
                border-color: {C.OLIVE_DK};
                color: white;
            }}
            QPushButton[primary="true"]:hover {{
                background: {C.OLIVE_H};
            }}
            QCheckBox {{
                background: transparent;
                color: {C.TEXT_MUTED};
                font-family: "{F.UI}";
                font-size: {F.SZ_XS}pt;
            }}
        """)

        layout = QVBoxLayout(self._callout)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QWidget()
        head.setStyleSheet(
            f"background: {C.BG_RAISED}; border-bottom: 1px solid {C.BORDER};"
            "border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        head_lay = QVBoxLayout(head)
        head_lay.setContentsMargins(14, 10, 14, 9)
        head_lay.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        self._kicker_lbl = QLabel("Startup guide")
        self._kicker_lbl.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}'; "
            f"font-size: {F.SZ_XS}pt; font-weight: 700; letter-spacing: 1px;"
        )
        self._count_lbl = QLabel("1 / 1")
        self._count_lbl.setStyleSheet(
            f"color: {C.OLIVE_DK}; background: rgba(107,142,35,0.10); "
            f"border: 1px solid rgba(107,142,35,0.25); border-radius: 8px; "
            f"font-family: '{F.MONO}'; font-size: {F.SZ_XS}pt; "
            "font-weight: 700; padding: 1px 7px;"
        )
        top_row.addWidget(self._kicker_lbl, 1)
        top_row.addWidget(self._count_lbl, 0)
        head_lay.addLayout(top_row)

        self._title_lbl = QLabel("")
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-family: '{F.UI}'; "
            f"font-size: {F.SZ_LG}pt; font-weight: 700;"
        )
        head_lay.addWidget(self._title_lbl)
        layout.addWidget(head)

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(14, 11, 14, 12)
        body_lay.setSpacing(8)

        self._body_lbl = QLabel("")
        self._body_lbl.setWordWrap(True)
        self._body_lbl.setStyleSheet(
            f"color: {C.TEXT_MID}; font-family: '{F.UI}'; "
            f"font-size: {F.SZ_MD}pt; line-height: 145%;"
        )
        body_lay.addWidget(self._body_lbl)

        self._tips_lbl = QLabel("")
        self._tips_lbl.setWordWrap(True)
        self._tips_lbl.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.UI}'; "
            f"font-size: {F.SZ_SM}pt;"
        )
        body_lay.addWidget(self._tips_lbl)
        layout.addWidget(body)

        footer = QWidget()
        footer.setStyleSheet(
            f"background: #f8f4ec; border-top: 1px solid {C.BORDER}; "
            "border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;"
        )
        foot_lay = QHBoxLayout(footer)
        foot_lay.setContentsMargins(12, 9, 12, 9)
        foot_lay.setSpacing(7)

        self._dont_show_check = QCheckBox("Do not show on startup")
        self._dont_show_check.setVisible(self._show_startup_checkbox)
        if self._show_startup_checkbox:
            foot_lay.addWidget(self._dont_show_check, 1)
        else:
            foot_lay.addStretch(1)

        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self._back)
        foot_lay.addWidget(self._back_btn)

        self._skip_btn = QPushButton("Skip")
        self._skip_btn.clicked.connect(self.close_tour)
        foot_lay.addWidget(self._skip_btn)

        self._next_btn = QPushButton("Next")
        self._next_btn.setObjectName("startup-tour-next")
        self._next_btn.setProperty("primary", True)
        self._next_btn.setStyleSheet(f"""
            QPushButton#startup-tour-next {{
                background: {C.OLIVE};
                border: 1px solid {C.OLIVE_DK};
                border-radius: {SZ.BORDER_RADIUS}px;
                color: white;
                font-family: "{F.UI}";
                font-size: {F.SZ_SM}pt;
                font-weight: 800;
                min-height: 26px;
                padding: 0 12px;
            }}
            QPushButton#startup-tour-next:hover {{
                background: {C.OLIVE_H};
                border-color: {C.OLIVE_DK};
                color: white;
            }}
            QPushButton#startup-tour-next:pressed {{
                background: {C.OLIVE_DK};
                color: white;
            }}
        """)
        self._next_btn.clicked.connect(self._next)
        foot_lay.addWidget(self._next_btn)
        layout.addWidget(footer)

    def _show_step(self, index: int) -> None:
        self._index = max(0, min(index, len(self._steps) - 1))
        step = self._steps[self._index]
        if step.before_step is not None:
            try:
                step.before_step()
                QApplication.processEvents()
            except RuntimeError:
                pass
        self._position_current_step()

    def _position_current_step(self) -> None:
        if not self.isVisible() or not self._steps:
            return

        step = self._steps[self._index]
        target_rect = self._target_rect_for(step)
        if target_rect is None:
            target_rect = QRect(
                max(16, self.width() // 2 - 80),
                max(16, self.height() // 2 - 30),
                160,
                60,
            )

        self._target_rect = target_rect
        self._spotlight_rect = target_rect.adjusted(-8, -8, 8, 8)

        self._kicker_lbl.setText(step.kicker.upper())
        self._count_lbl.setText(f"{self._index + 1} / {len(self._steps)}")
        self._title_lbl.setText(step.title)
        self._body_lbl.setText(step.body)
        if step.tips:
            tips = "<br>".join(f"- {tip}" for tip in step.tips)
            self._tips_lbl.setText(tips)
            self._tips_lbl.show()
        else:
            self._tips_lbl.hide()

        self._back_btn.setEnabled(self._index > 0)
        self._next_btn.setText("Done" if self._index >= len(self._steps) - 1 else "Next")
        self._position_callout(target_rect)
        self.update()

    def _target_rect_for(self, step: TourStep) -> QRect | None:
        try:
            target = step.target()
        except RuntimeError:
            target = None
        if target is None:
            return None
        parent = self.parentWidget()
        if parent is None or not target.isVisibleTo(parent):
            return None
        top_left = target.mapTo(parent, QPoint(0, 0))
        return QRect(top_left, target.size()).intersected(self.rect())

    def _position_callout(self, target_rect: QRect) -> None:
        margin = 16
        gap = 18
        self._callout.adjustSize()
        callout_size = self._callout.sizeHint()
        width = self._callout.width()
        height = callout_size.height()

        right_x = target_rect.right() + gap
        left_x = target_rect.left() - width - gap
        if right_x + width + margin <= self.width():
            x = right_x
        elif left_x >= margin:
            x = left_x
        else:
            x = max(margin, min(self.width() - width - margin, target_rect.center().x() - width // 2))

        y = target_rect.center().y() - height // 2
        if y < margin:
            y = target_rect.bottom() + gap
        if y + height + margin > self.height():
            y = target_rect.top() - height - gap
        y = max(margin, min(self.height() - height - margin, y))
        self._callout.move(x, y)

    def _back(self) -> None:
        if self._index > 0:
            self._show_step(self._index - 1)

    def _next(self) -> None:
        if self._index >= len(self._steps) - 1:
            self.close_tour()
            return
        self._show_step(self._index + 1)
