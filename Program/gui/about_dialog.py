"""Application identity, provenance, and attribution dialog."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.dialog_chrome import make_dialog_footer, make_dialog_header
from gui.theme import C, F
from qt_chrome.frameless_dialog_base import FramelessDialogBase
from version import RELEASE_DATE_DISPLAY, VERSION


class AboutDialog(FramelessDialogBase):
    """Show the product identity and the lineage behind the application."""

    def __init__(self, parent=None):
        super().__init__(parent, default_mode="auto")
        self.setWindowTitle("About Grain Size Analysis")
        self.setMinimumSize(610, 500)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._header_widget = make_dialog_header(
            "About Grain Size Analysis",
            "Version, purpose, and project provenance",
            fa_icon="fa6s.circle-info",
            close_fn=self.accept,
        )
        root.addWidget(self._header_widget)

        body = QWidget()
        body.setStyleSheet(f"background: {C.BG};")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        identity = QHBoxLayout()
        identity.setSpacing(16)
        logo = QLabel()
        logo.setFixedSize(64, 64)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background: transparent;")
        icon_path = Path(__file__).resolve().parents[1] / "resources" / "app_icon.ico"
        logo.setPixmap(QIcon(str(icon_path)).pixmap(58, 58))
        identity.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)

        title_column = QVBoxLayout()
        title_column.setSpacing(4)
        title = QLabel("Grain Size Analysis Tool")
        title.setStyleSheet(
            f"color: {C.TEXT}; font-family: '{F.DISP}';"
            f" font-size: {F.SZ_2XL + 2}pt; font-weight: 700; background: transparent;"
        )
        version = QLabel(f"Version {VERSION}  ·  Released {RELEASE_DATE_DISPLAY}")
        version.setStyleSheet(
            f"color: {C.OLIVE_DK}; font-family: '{F.MONO}';"
            f" font-size: {F.SZ_SM}pt; background: transparent;"
        )
        purpose = QLabel(
            "Desktop analysis of grain-size distributions, hydraulic conductivity, "
            "dataset comparison, reporting, and reproducible export."
        )
        purpose.setWordWrap(True)
        purpose.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_MD}pt; background: transparent;"
        )
        title_column.addWidget(title)
        title_column.addWidget(version)
        title_column.addSpacing(4)
        title_column.addWidget(purpose)
        identity.addLayout(title_column, 1)
        layout.addLayout(identity)

        layout.addWidget(self._divider())
        layout.addWidget(self._section_label("PROJECT"))
        layout.addWidget(self._attribution("Developed by", "Oliver Lund · DTU Sustain"))
        layout.addWidget(self._attribution(
            "Made in collaboration with",
            "Poul Løgstrup Bjerg · DTU Sustain",
        ))

        layout.addWidget(self._divider())
        layout.addWidget(self._section_label("ORIGINAL TOOL"))
        lineage = QLabel(
            "This program is a further development of "
            "<b>HydrogeoSieveXL</b>, the original grain-size and hydraulic-"
            "conductivity tool developed by <b>J. F. Devlin</b>."
        )
        lineage.setWordWrap(True)
        lineage.setTextFormat(Qt.TextFormat.RichText)
        lineage.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_MD}pt; background: transparent;"
        )
        layout.addWidget(lineage)

        layout.addWidget(self._divider())
        layout.addWidget(self._section_label("REFERENCES"))
        references = QLabel(
            'Original software: '
            '<a href="https://jfdevlin.github.io/DevlinWebPages/Software.html">'
            'HydrogeoSieveXL software page</a><br>'
            'J. F. Devlin (2015), <i>HydrogeoSieveXL: an Excel-based tool to '
            'estimate hydraulic conductivity from grain-size analysis</i>, '
            '<i>Hydrogeology Journal</i>. '
            '<a href="https://doi.org/10.1007/s10040-015-1255-0">'
            'DOI 10.1007/s10040-015-1255-0</a>'
        )
        references.setObjectName("about-references")
        references.setWordWrap(True)
        references.setOpenExternalLinks(True)
        references.setTextFormat(Qt.TextFormat.RichText)
        references.setStyleSheet(
            f"color: {C.TEXT_MID}; font-size: {F.SZ_SM}pt;"
            f" background: transparent;"
            f" selection-background-color: {C.OLIVE};"
        )
        layout.addWidget(references)

        self._article_button = QPushButton("Open cited article (PDF)")
        self._article_button.setObjectName("about-article-button")
        self._article_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._article_button.setFixedHeight(28)
        self._article_button.setStyleSheet(
            f"QPushButton {{ background: {C.BG_LOW}; color: {C.OLIVE_DK};"
            f" border: 1px solid {C.BORDER}; border-radius: 5px; padding: 3px 9px; }}"
            f"QPushButton:hover {{ background: {C.BG_RAISED}; border-color: {C.OLIVE}; }}"
            f"QPushButton:disabled {{ color: {C.TEXT_MUTED}; background: transparent; }}"
        )
        article_path = self._article_path()
        if article_path is not None:
            self._article_button.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(article_path)))
            )
        else:
            self._article_button.setEnabled(False)
            self._article_button.setToolTip(
                "The cited PDF is available in the source distribution or via the DOI above."
            )
        layout.addWidget(self._article_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

        copyright_label = QLabel("© 2025–2026 · DTU Sustain")
        copyright_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}';"
            f" font-size: {F.SZ_SM}pt; background: transparent;"
        )
        layout.addWidget(copyright_label)

        root.addWidget(body, 1)
        root.addWidget(make_dialog_footer([("Close", self.accept, "primary")]))
        self.install_chrome_behavior(
            header_widget=self._header_widget,
            corner_radius=8,
            resize_margin=6,
        )

    @staticmethod
    def _divider() -> QFrame:
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {C.BORDER};")
        return divider

    @staticmethod
    def _article_path() -> Path | None:
        """Locate the cited PDF in both source and PyInstaller layouts."""
        path = Path(__file__).resolve().parents[2] / "Litterature" / (
            "DevlinHydrogeoSieveXL_HydrogeologyJ-15.pdf"
        )
        return path if path.is_file() else None

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-family: '{F.MONO}';"
            f" font-size: {F.SZ_XS}pt; font-weight: 700; background: transparent;"
        )
        return label

    @staticmethod
    def _attribution(role: str, name: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        role_label = QLabel(role)
        role_label.setMinimumWidth(180)
        role_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SZ_SM}pt; background: transparent;"
        )
        name_label = QLabel(name)
        name_label.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.SZ_MD}pt; font-weight: 600;"
            " background: transparent;"
        )
        layout.addWidget(role_label)
        layout.addWidget(name_label, 1)
        return row
