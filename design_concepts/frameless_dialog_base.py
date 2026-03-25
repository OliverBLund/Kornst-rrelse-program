"""
Reusable frameless dialog base with native move/resize integration and custom title bar.
"""

import sys
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from shared.qt_chrome import (
    FramelessDialogChromeController,
    apply_frameless_round_mask,
    enable_windows_soft_corners,
    resolve_dialog_chrome_mode,
)


class FramelessDialogBase(QDialog):
    """Base dialog that can run in native or frameless mode with shared chrome behavior."""

    def __init__(
        self,
        parent=None,
        chrome_env_key: Optional[str] = None,
        default_mode: str = "auto",
    ):
        super().__init__(parent)
        # Retained for backward compatibility with existing subclass signatures.
        self._dialog_chrome_env_key = chrome_env_key
        self._dialog_default_mode = default_mode
        self._dialog_chrome_mode = "native"
        self._frameless_enabled = False

        self._frameless_corner_radius_px = 10
        self._resize_margin = 6

        self._maximize_btn = None
        self._chrome_controller = FramelessDialogChromeController(
            self, resize_margin=self._resize_margin
        )
        self._soft_corners_pending = False

        self._configure_window_chrome()
        self.destroyed.connect(self._cleanup_global_event_filter)

    def _resolve_dialog_chrome_mode(self) -> str:
        """Resolve dialog chrome mode from parent/default fallback."""
        parent_mode = str(getattr(self.parent(), "_window_chrome_mode", "")).strip().lower()
        return resolve_dialog_chrome_mode(
            parent_mode=parent_mode,
            default_mode=self._dialog_default_mode,
            default_windows="frameless",
            default_other="native",
        )

    def _configure_window_chrome(self):
        """Apply native or frameless window flags with safe fallback."""
        chrome_mode = self._resolve_dialog_chrome_mode()
        self._dialog_chrome_mode = chrome_mode

        flags = Qt.WindowType(self.windowFlags())
        if chrome_mode == "frameless":
            try:
                self.setWindowFlags(flags | Qt.WindowType.FramelessWindowHint)
                self._frameless_enabled = True
                # Defer native-handle-specific corner APIs until first show.
                self._soft_corners_pending = True
                return
            except Exception:
                self._frameless_enabled = False
                self._dialog_chrome_mode = "native"
                self._soft_corners_pending = False

        self.setWindowFlags(flags & ~Qt.WindowType.FramelessWindowHint)
        self._frameless_enabled = False
        self._soft_corners_pending = False

    def _enable_windows_soft_corners(self):
        """Best-effort rounded corners on Windows 11."""
        enable_windows_soft_corners(self)

    def _is_frameless_active(self) -> bool:
        return bool(self._frameless_enabled)

    def install_chrome_behavior(
        self,
        header_widget: Optional[QWidget],
        resize_widgets: Optional[list[QWidget]] = None,
        drag_widgets: Optional[list[QWidget]] = None,
        corner_radius: int = 10,
        resize_margin: int = 6,
    ):
        """Install frameless drag/resize behavior after UI widgets are created."""
        self._frameless_corner_radius_px = max(2, int(corner_radius))
        self._resize_margin = max(2, int(resize_margin))

        if not self._is_frameless_active():
            self._chrome_controller.set_enabled(False)
            self._cleanup_global_event_filter()
            self.clearMask()
            return

        self._chrome_controller.set_enabled(True)
        self._chrome_controller.configure(
            header_widget=header_widget,
            resize_widgets=resize_widgets,
            drag_widgets=drag_widgets,
            resize_margin=self._resize_margin,
        )

        self._apply_frameless_round_mask()
        self._sync_maximize_button()

    def _cleanup_global_event_filter(self):
        self._chrome_controller.cleanup()

    def _resolve_icon_search_dirs(self) -> list[Path]:
        """Return icon directories used for dialog chrome symbols."""
        if hasattr(sys, "_MEIPASS"):
            base_dir = Path(getattr(sys, "_MEIPASS"))
            if (base_dir / "src").is_dir():
                base_dir = base_dir / "src"
        else:
            base_dir = Path(__file__).resolve().parents[2]

        icons_root = base_dir / "views" / "code_editor" / "assets" / "icons"
        return [
            icons_root / "24" / "outline",
            icons_root / "24" / "solid",
            icons_root,
        ]

    def _load_chrome_icon_pixmap(
        self,
        icon_name: str,
        size: int = 16,
        color: str = "#2563EB",
        variant: str = "outline",
    ) -> Optional[QPixmap]:
        """Load and tint a shared SVG icon for dialog chrome."""
        icon_name = (icon_name or "").strip()
        if not icon_name:
            return None

        search_dirs = self._resolve_icon_search_dirs()
        search_order = list(search_dirs)
        if variant in {"outline", "solid"}:
            preferred = search_dirs[0] if variant == "outline" else search_dirs[1]
            search_order = [preferred] + [d for d in search_dirs if d != preferred]

        svg_path = None
        for icon_dir in search_order:
            candidate = icon_dir / f"{icon_name}.svg"
            if candidate.exists():
                svg_path = candidate
                break
        if svg_path is None:
            return None

        icon_size = max(12, int(size))
        try:
            renderer = QSvgRenderer(str(svg_path))
            if not renderer.isValid():
                return None

            pixmap = QPixmap(icon_size, icon_size)
            pixmap.fill(QColor(0, 0, 0, 0))

            painter = QPainter(pixmap)
            try:
                renderer.render(painter)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor(color))
            finally:
                painter.end()

            return pixmap
        except Exception:
            return None

    def build_chrome_titlebar(
        self,
        tokens: dict,
        title: str,
        subtitle: str = "",
        icon_text: str = "",
        icon_name: Optional[str] = None,
        icon_color: Optional[str] = None,
        icon_variant: str = "outline",
        on_close: Optional[Callable[[], None]] = None,
        show_window_controls: Optional[bool] = None,
    ) -> QFrame:
        """Create reusable title bar with minimize/maximize/close buttons."""
        bg_elevated = tokens.get("bg_elevated", "#1f2937")
        border_default = tokens.get("border_default", "#374151")
        text_primary = tokens.get("text_primary", "#F3F4F6")
        text_tertiary = tokens.get("text_tertiary", "#9CA3AF")
        text_muted = tokens.get("text_muted", "#9CA3AF")
        accent_ghost = tokens.get("accent_ghost", "rgba(37, 99, 235, 0.2)")
        accent_light = tokens.get("accent_light", "#93C5FD")
        radius_md = tokens.get("r_md", "6px")
        radius_sm = tokens.get("r_sm", "4px")

        header = QFrame()
        header.setStyleSheet(
            f"""
            QFrame {{
                background-color: {bg_elevated};
                border-bottom: 1px solid {border_default};
            }}
        """
        )

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 12, 12, 12)
        header_layout.setSpacing(10)

        icon_pixmap = None
        if icon_name:
            icon_pixmap = self._load_chrome_icon_pixmap(
                icon_name=icon_name,
                size=16,
                color=icon_color or accent_light,
                variant=icon_variant,
            )

        if icon_pixmap is not None or icon_text:
            icon_label = QLabel()
            icon_label.setFixedSize(28, 28)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if icon_pixmap is not None:
                icon_label.setPixmap(icon_pixmap)
                icon_label.setStyleSheet(
                    f"""
                    QLabel {{
                        background-color: {accent_ghost};
                        color: {accent_light};
                        border-radius: {radius_md};
                    }}
                """
                )
            else:
                icon_label.setText(icon_text)
                icon_label.setStyleSheet(
                    f"""
                    QLabel {{
                        background-color: {accent_ghost};
                        color: {accent_light};
                        border-radius: {radius_md};
                        font-size: 14px;
                        font-weight: 700;
                    }}
                """
                )
            header_layout.addWidget(icon_label)

        title_group = QWidget()
        title_group_layout = QVBoxLayout(title_group)
        title_group_layout.setContentsMargins(0, 0, 0, 0)
        title_group_layout.setSpacing(1)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"""
            QLabel {{
                font-size: 14px;
                font-weight: 700;
                color: {text_primary};
            }}
        """
        )
        title_group_layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setStyleSheet(
                f"""
                QLabel {{
                    font-size: 10px;
                    color: {text_tertiary};
                }}
            """
            )
            title_group_layout.addWidget(subtitle_label)

        header_layout.addWidget(title_group)
        header_layout.addStretch()

        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)
        controls.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        if show_window_controls is None:
            show_window_controls = self._is_frameless_active()

        def _control_button(text: str, tooltip: str, object_name: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setObjectName(object_name)
            btn.setToolTip(tooltip)
            btn.setFixedSize(36, 26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 10))
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            return btn

        if show_window_controls:
            minimize_btn = _control_button("\u2212", "Minimize", "windowMinimizeButton")
            minimize_btn.setFont(QFont("Segoe UI", 14))
            minimize_btn.setStyleSheet(
                f"""
                QPushButton#windowMinimizeButton {{
                    background-color: transparent;
                    color: {text_primary};
                    border: 1px solid transparent;
                    border-radius: {radius_sm};
                    padding-bottom: 1px;
                    padding-left: 0px;
                    padding-right: 0px;
                    min-width: 36px;
                    max-width: 36px;
                    min-height: 26px;
                    max-height: 26px;
                }}
                QPushButton#windowMinimizeButton:hover {{
                    background-color: {accent_ghost};
                    border: 1px solid {border_default};
                    color: {accent_light};
                }}
                QPushButton#windowMinimizeButton:pressed {{
                    background-color: {accent_ghost};
                }}
            """
            )
            minimize_btn.clicked.connect(self.showMinimized)
            controls_layout.addWidget(minimize_btn)

            maximize_btn = _control_button("\u25A1", "Maximize", "windowMaximizeButton")
            maximize_btn.setStyleSheet(
                f"""
                QPushButton#windowMaximizeButton {{
                    background-color: transparent;
                    color: {text_primary};
                    border: 1px solid transparent;
                    border-radius: {radius_sm};
                    padding: 0px;
                    min-width: 36px;
                    max-width: 36px;
                    min-height: 26px;
                    max-height: 26px;
                }}
                QPushButton#windowMaximizeButton:hover {{
                    background-color: {accent_ghost};
                    border: 1px solid {border_default};
                    color: {accent_light};
                }}
                QPushButton#windowMaximizeButton:pressed {{
                    background-color: {accent_ghost};
                }}
            """
            )
            maximize_btn.clicked.connect(self._toggle_maximize_restore)
            self._maximize_btn = maximize_btn
            controls_layout.addWidget(maximize_btn)
        else:
            self._maximize_btn = None

        close_btn = _control_button("\u2715", "Close", "windowCloseButton")
        close_btn.setStyleSheet(
            f"""
            QPushButton#windowCloseButton {{
                background: transparent;
                border: 1px solid transparent;
                color: {text_muted};
                border-radius: {radius_sm};
                padding: 0px;
                min-width: 36px;
                max-width: 36px;
                min-height: 26px;
                max-height: 26px;
            }}
            QPushButton#windowCloseButton:hover {{
                background-color: #DC2626;
                color: #FFFFFF;
                border: 1px solid #EF4444;
            }}
            QPushButton#windowCloseButton:pressed {{
                background-color: #B91C1C;
            }}
        """
        )
        close_btn.clicked.connect(on_close or self.reject)
        controls_layout.addWidget(close_btn)

        header_layout.addWidget(controls)
        self._sync_maximize_button()
        return header

    def _toggle_maximize_restore(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._sync_maximize_button()

    def _sync_maximize_button(self):
        if not self._maximize_btn:
            return
        if self.isMaximized():
            self._maximize_btn.setText("\u2750")
            self._maximize_btn.setToolTip("Restore")
        else:
            self._maximize_btn.setText("\u25A1")
            self._maximize_btn.setToolTip("Maximize")

    def _apply_frameless_round_mask(self):
        apply_frameless_round_mask(
            self,
            enabled=self._is_frameless_active(),
            is_effectively_maximized=bool(self.isMaximized()),
            corner_radius_px=max(2, int(self._frameless_corner_radius_px)),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_frameless_round_mask()

    def showEvent(self, event):
        if self._is_frameless_active():
            self._chrome_controller.on_show()

        if self._soft_corners_pending and self._is_frameless_active():
            self._enable_windows_soft_corners()
            self._soft_corners_pending = False

        super().showEvent(event)
        self._apply_frameless_round_mask()

    def hideEvent(self, event):
        self._cleanup_global_event_filter()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._cleanup_global_event_filter()
        super().closeEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._sync_maximize_button()
            self._apply_frameless_round_mask()
