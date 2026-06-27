"""Background thread for report generation.

Report HTML (including every plot rendered to a PNG) is built off the UI thread
so a large report — e.g. a Full summary over 20 datasets with per-sample plots —
never freezes the app. The render path is pyplot-free (``plot_export`` uses bare
``Figure`` + ``FigureCanvasAgg``), so running it on a worker thread is safe.

``ReportWorker`` follows the project's ``QThread``-subclass pattern (see
``main.LoaderThread``): a thunk that produces the HTML runs in ``run()``, with
``progress``/``finished``/``failed``/``cancelled`` signals marshalled back to the
GUI thread. Cancellation is cooperative — the generator polls ``is_cancelled``
between plots and raises ``ReportCancelled``.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from report_generator import ReportCancelled


class ReportWorker(QThread):
    """Run a report-generating thunk off the UI thread.

    *build* is ``callable(progress, cancel_check) -> html`` — typically a small
    lambda that calls ``ReportGenerator.generate_*`` with the report's arguments
    plus the two callbacks this worker supplies.
    """

    progress = pyqtSignal(int, int, str)  # current, total, label
    finished_html = pyqtSignal(str)       # html on success
    failed = pyqtSignal(str)              # message on error
    cancelled = pyqtSignal()              # user cancelled

    def __init__(self, build: Callable[[Callable, Callable], str], parent=None):
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
            html = self._build(self._emit_progress, self.is_cancelled)
        except ReportCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:  # surfaced to the user via the dialog
            self.failed.emit(str(exc))
            return
        self.finished_html.emit(html)
