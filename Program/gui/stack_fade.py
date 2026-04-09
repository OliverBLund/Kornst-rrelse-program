"""
Lightweight fade transitions for QStackedWidget page switches.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QTimer
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget, QTabWidget, QWidget


class StackFadeController(QObject):
    """Animate simple stacked-page transitions without changing page ownership."""

    def __init__(
        self,
        stack: QStackedWidget,
        parent: QObject | None = None,
        *,
        fade_out_ms: int = 90,
        fade_in_ms: int = 120,
    ) -> None:
        super().__init__(parent or stack)
        self._stack = stack
        self._fade_out_ms = max(0, fade_out_ms)
        self._fade_in_ms = max(0, fade_in_ms)
        self._running = False
        self._pending: tuple[int, Callable[[], None] | None] | None = None
        self._active_widget: QWidget | None = None
        self._active_effect: QGraphicsOpacityEffect | None = None
        self._active_animation: QPropertyAnimation | None = None

    def switch_to(
        self,
        index: int,
        after_switch: Callable[[], None] | None = None,
    ) -> bool:
        """Switch to a stack page, fading when the stack is currently visible."""
        if index < 0 or index >= self._stack.count():
            return False

        if self._running:
            self._pending = (index, after_switch)
            return True

        if self._stack.currentIndex() == index:
            if after_switch is not None:
                QTimer.singleShot(0, after_switch)
            return False

        current_widget = self._stack.currentWidget()
        if not self._should_animate(current_widget):
            self._stack.setCurrentIndex(index)
            if after_switch is not None:
                QTimer.singleShot(0, after_switch)
            return True

        self._running = True
        self._pending = None
        self._start_fade_out(current_widget, index, after_switch)
        return True

    @property
    def is_animating(self) -> bool:
        return self._running

    def _should_animate(self, current_widget: QWidget | None) -> bool:
        return (
            current_widget is not None
            and self._fade_out_ms > 0
            and self._fade_in_ms > 0
            and self._stack.isVisible()
            and current_widget.isVisible()
        )

    def _start_fade_out(
        self,
        current_widget: QWidget,
        index: int,
        after_switch: Callable[[], None] | None,
    ) -> None:
        effect = QGraphicsOpacityEffect(current_widget)
        effect.setOpacity(1.0)
        current_widget.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(self._fade_out_ms)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        animation.finished.connect(
            lambda idx=index, cb=after_switch, widget=current_widget, eff=effect:
            self._on_fade_out_finished(idx, cb, widget, eff)
        )

        self._active_widget = current_widget
        self._active_effect = effect
        self._active_animation = animation
        animation.start()

    def _on_fade_out_finished(
        self,
        index: int,
        after_switch: Callable[[], None] | None,
        previous_widget: QWidget,
        previous_effect: QGraphicsOpacityEffect,
    ) -> None:
        self._clear_effect(previous_widget, previous_effect)
        self._stack.setCurrentIndex(index)
        if after_switch is not None:
            QTimer.singleShot(0, after_switch)

        incoming_widget = self._stack.currentWidget()
        if not self._should_animate(incoming_widget):
            self._finish_transition()
            return

        effect = QGraphicsOpacityEffect(incoming_widget)
        effect.setOpacity(0.0)
        incoming_widget.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(self._fade_in_ms)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(
            lambda widget=incoming_widget, eff=effect: self._on_fade_in_finished(widget, eff)
        )

        self._active_widget = incoming_widget
        self._active_effect = effect
        self._active_animation = animation
        animation.start()

    def _on_fade_in_finished(
        self,
        widget: QWidget,
        effect: QGraphicsOpacityEffect,
    ) -> None:
        self._clear_effect(widget, effect)
        self._finish_transition()

    def _finish_transition(self) -> None:
        self._active_widget = None
        self._active_effect = None
        self._active_animation = None
        self._running = False

        if self._pending is not None:
            index, after_switch = self._pending
            self._pending = None
            QTimer.singleShot(
                0,
                lambda idx=index, cb=after_switch: self.switch_to(idx, cb),
            )

    @staticmethod
    def _clear_effect(widget: QWidget | None, effect: QGraphicsOpacityEffect | None) -> None:
        if widget is not None and effect is not None and widget.graphicsEffect() is effect:
            widget.setGraphicsEffect(None)


class TabFadeInController(QObject):
    """Lightweight fade-in for incoming QTabWidget pages."""

    def __init__(
        self,
        tab_widget: QTabWidget,
        parent: QObject | None = None,
        *,
        duration_ms: int = 110,
    ) -> None:
        super().__init__(parent or tab_widget)
        self._tab_widget = tab_widget
        self._duration_ms = max(0, duration_ms)
        self._active_widget: QWidget | None = None
        self._active_effect: QGraphicsOpacityEffect | None = None
        self._active_animation: QPropertyAnimation | None = None
        self._animating = False
        self._tab_widget.currentChanged.connect(self._queue_fade_for_index)

    @property
    def is_animating(self) -> bool:
        return self._animating

    def _queue_fade_for_index(self, index: int) -> None:
        if index < 0:
            return
        QTimer.singleShot(0, lambda idx=index: self._start_fade_for_index(idx))

    def _start_fade_for_index(self, index: int) -> None:
        if self._duration_ms <= 0 or index != self._tab_widget.currentIndex():
            return
        if not self._tab_widget.isVisible():
            return

        widget = self._tab_widget.widget(index)
        if widget is None or not widget.isVisible():
            return
        if widget.graphicsEffect() is not None and widget is not self._active_widget:
            return

        self._clear_active_effect()

        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(self._duration_ms)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(
            lambda target=widget, eff=effect: self._on_fade_finished(target, eff)
        )

        self._active_widget = widget
        self._active_effect = effect
        self._active_animation = animation
        self._animating = True
        animation.start()

    def _on_fade_finished(self, widget: QWidget, effect: QGraphicsOpacityEffect) -> None:
        if widget.graphicsEffect() is effect:
            widget.setGraphicsEffect(None)
        self._active_widget = None
        self._active_effect = None
        self._active_animation = None
        self._animating = False

    def _clear_active_effect(self) -> None:
        if self._active_widget is not None and self._active_effect is not None:
            if self._active_widget.graphicsEffect() is self._active_effect:
                self._active_widget.setGraphicsEffect(None)
        self._active_widget = None
        self._active_effect = None
        self._active_animation = None
        self._animating = False
