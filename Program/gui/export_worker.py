"""Background thread for the data/plot export.

Exporting a large selection (many datasets × CSV/Excel/plots) writes files and
renders plots, which froze the UI when run inline. The plot render path is
pyplot-free (``plot_export`` uses bare ``Figure`` + ``FigureCanvasAgg``), so the
export is safe to run on a worker thread.

``ExportWorker`` follows the project's ``QThread``-subclass pattern (see
``main.LoaderThread`` and ``gui.report_worker``). Cancellation is cooperative and
free: ``ExportManager.export`` calls ``progress.setValue`` after every file, so a
proxy that raises :class:`ExportCancelled` from ``setValue`` stops the export
promptly between files — no changes to the export manager are needed.
"""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt6.QtCore import QThread, pyqtSignal


class ExportCancelled(Exception):
    """Raised by the progress proxy to abort an in-flight export."""


class _WorkerProgressProxy:
    """Progress sink handed to ``ExportManager.export`` from the worker thread.

    Implements the ``setMaximum``/``setValue`` protocol the export manager
    expects, but instead of touching widgets (illegal off the GUI thread) it
    emits the worker's ``progress`` signal (queued to the GUI thread). It raises
    :class:`ExportCancelled` when the worker was asked to cancel.
    """

    def __init__(self, worker: "ExportWorker"):
        self._worker = worker
        self._total = 1

    def setMaximum(self, total: int) -> None:
        self._total = max(1, int(total))
        self._worker.progress.emit(0, self._total)

    def setValue(self, current: int) -> None:
        if self._worker.is_cancelled():
            raise ExportCancelled()
        value = max(0, min(int(current), self._total))
        self._worker.progress.emit(value, self._total)


class ExportWorker(QThread):
    """Run ``manager.export(datasets, config, proxy)`` off the UI thread."""

    progress = pyqtSignal(int, int)        # current, total
    finished_files = pyqtSignal(list)      # exported file paths on success
    failed = pyqtSignal(str)               # message on error
    cancelled = pyqtSignal()               # user cancelled

    def __init__(self, manager, datasets: List[tuple], config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._manager = manager
        self._datasets = datasets
        self._config = config
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def is_cancelled(self) -> bool:
        return self._cancel_requested

    def run(self) -> None:
        try:
            files = self._manager.export(
                self._datasets, self._config, _WorkerProgressProxy(self)
            )
        except ExportCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:  # surfaced to the user via the dialog
            self.failed.emit(str(exc))
            return
        self.finished_files.emit(list(files))
