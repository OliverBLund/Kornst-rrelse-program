"""Background worker and atomic writers for report file exports."""

from __future__ import annotations

import os
import tempfile
from typing import Any, Callable, Dict

from PyQt6.QtCore import QThread, pyqtSignal


class ReportExportCancelled(Exception):
    """Raised when a report file export is cancelled cooperatively."""


def atomic_write_bytes(path: str, data: bytes) -> None:
    """Replace *path* only after the complete byte payload is on disk."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, temporary_path = tempfile.mkstemp(
        prefix=".gsa_report_",
        suffix=".tmp",
        dir=directory,
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.remove(temporary_path)
        except OSError:
            pass
        raise


def atomic_write_text(path: str, text: str) -> None:
    """Replace *path* only after the complete UTF-8 payload is on disk."""
    atomic_write_bytes(path, text.encode("utf-8"))


class ReportExportWorker(QThread):
    """Run a report-export callable away from the GUI thread."""

    progress = pyqtSignal(int, int, str)
    finished_export = pyqtSignal(dict)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(
        self,
        build: Callable[[Callable[[int, int, str], None], Callable[[], bool]], Dict[str, Any]],
        parent=None,
    ):
        super().__init__(parent)
        self._build = build
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def is_cancelled(self) -> bool:
        return self._cancel_requested

    def _emit_progress(self, current: int, total: int, label: str) -> None:
        self.progress.emit(int(current), int(total), str(label))

    def run(self) -> None:
        try:
            result = self._build(self._emit_progress, self.is_cancelled)
            if self.is_cancelled():
                raise ReportExportCancelled()
        except ReportExportCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished_export.emit(dict(result))
