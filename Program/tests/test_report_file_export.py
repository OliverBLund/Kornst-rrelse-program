"""Focused tests for threaded report file export."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GSA_DISABLE_WEBENGINE", "1")
sys.path.insert(0, "Program")

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtGui import QPageLayout
from PyQt6.QtWidgets import QApplication

from gui.report_export_worker import ReportExportCancelled, ReportExportWorker
from gui.reporting_tab import ReportingTab


APP = QApplication.instance() or QApplication(
    sys.argv[:1] or ["test_report_file_export"]
)


def run_worker(worker: ReportExportWorker, timeout_ms: int = 5000) -> dict:
    outcome = {}
    loop = QEventLoop()
    worker.finished_export.connect(
        lambda result: (outcome.__setitem__("result", result), loop.quit())
    )
    worker.failed.connect(
        lambda message: (outcome.__setitem__("error", message), loop.quit())
    )
    worker.cancelled.connect(
        lambda: (outcome.__setitem__("cancelled", True), loop.quit())
    )
    QTimer.singleShot(timeout_ms, loop.quit)
    worker.start()
    loop.exec()
    worker.wait(2000)
    return outcome


class TestReportExportWorker(unittest.TestCase):
    def test_worker_returns_result_and_progress(self):
        progress_events = []

        def build(progress, cancel_check):
            self.assertFalse(cancel_check())
            progress(1, 2, "Converting")
            progress(2, 2, "Saved")
            return {"primary_path": "report.docx"}

        worker = ReportExportWorker(build)
        worker.progress.connect(
            lambda current, total, label: progress_events.append(
                (current, total, label)
            )
        )
        outcome = run_worker(worker)

        self.assertEqual(outcome["result"]["primary_path"], "report.docx")
        self.assertEqual(progress_events[-1], (2, 2, "Saved"))

    def test_worker_emits_cancelled(self):
        def build(_progress, cancel_check):
            if cancel_check():
                raise ReportExportCancelled()
            return {}

        worker = ReportExportWorker(build)
        worker.cancel()
        outcome = run_worker(worker)

        self.assertTrue(outcome.get("cancelled"))
        self.assertNotIn("result", outcome)


class TestReportingTabFileExport(unittest.TestCase):
    def setUp(self):
        self.tab = ReportingTab()
        self.tab.current_report_html = "<html><body><p>Report</p></body></html>"
        self.tab._preview_load_ready = True

    def tearDown(self):
        self.tab._report_export_worker = None
        self.tab.deleteLater()

    def test_html_export_uses_worker_and_loading_dialog(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "report.html")
            fake_dialog = Mock()
            fake_worker = Mock()

            with patch(
                "gui.reporting_tab.QFileDialog.getSaveFileName",
                return_value=(path, "HTML (*.html)"),
            ), patch(
                "gui.reporting_tab.LoadingDialog",
                return_value=fake_dialog,
            ), patch(
                "gui.reporting_tab.ReportExportWorker",
                return_value=fake_worker,
            ) as worker_class:
                self.tab._on_export_html()

            build = worker_class.call_args.args[0]
            result = build(lambda *_args: None, lambda: False)

            self.assertEqual(result["primary_path"], path)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), self.tab.current_report_html)
            fake_worker.start.assert_called_once()
            fake_dialog.exec.assert_called_once()

    def test_html_export_externalizes_large_tables_when_excel_appendix_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "report.html")
            self.tab._excel_appendix_panel.setVisible(True)
            self.tab._excel_appendix_check.setChecked(True)
            table_rows = "".join(
                f"<tr><td>Sample {index}</td><td>{index}</td></tr>"
                for index in range(60)
            )
            self.tab.current_report_html = (
                "<html><body><h3>Large Result Table</h3>"
                "<table data-report-table='large-result-table'>"
                "<thead><tr><th>Sample</th><th>Value</th></tr></thead>"
                f"<tbody>{table_rows}</tbody></table></body></html>"
            )
            self.tab.report_generator.generate_excel_appendix = Mock(
                return_value=b"xlsx"
            )
            fake_dialog = Mock()
            fake_worker = Mock()

            with patch(
                "gui.reporting_tab.QFileDialog.getSaveFileName",
                return_value=(path, "HTML (*.html)"),
            ), patch(
                "gui.reporting_tab.LoadingDialog",
                return_value=fake_dialog,
            ), patch(
                "gui.reporting_tab.ReportExportWorker",
                return_value=fake_worker,
            ) as worker_class:
                self.tab._on_export_html()

            build = worker_class.call_args.args[0]
            result = build(lambda *_args: None, lambda: False)

            with open(path, encoding="utf-8") as fh:
                exported_html = fh.read()
            self.assertIn("Large table moved to companion Excel appendix", exported_html)
            self.assertNotIn("Sample 59", exported_html)
            self.assertEqual(
                result["appendix_path"],
                os.path.join(directory, "report_tables.xlsx"),
            )
            appendix_html = (
                self.tab.report_generator.generate_excel_appendix.call_args.args[0]
            )
            self.assertIn("Sample 59", appendix_html)

    def test_word_and_excel_appendix_are_built_in_worker_callable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "report.docx")
            appendix_path = os.path.join(directory, "report_tables.xlsx")
            self.tab._excel_appendix_panel.setVisible(True)
            self.tab._excel_appendix_check.setChecked(True)
            self.tab.project_name_edit.setText("Project")
            table_rows = "".join(
                f"<tr><td>Sample {index}</td><td>{index}</td></tr>"
                for index in range(60)
            )
            self.tab.current_report_html = (
                "<html><body><h3>Large Result Table</h3>"
                "<table data-report-table='large-result-table'>"
                "<thead><tr><th>Sample</th><th>Value</th></tr></thead>"
                f"<tbody>{table_rows}</tbody></table></body></html>"
            )
            self.tab.report_generator.generate_docx_from_html = Mock(
                return_value=b"docx"
            )
            self.tab.report_generator.generate_excel_appendix = Mock(
                return_value=b"xlsx"
            )
            fake_dialog = Mock()
            fake_worker = Mock()

            with patch.object(
                self.tab.report_generator,
                "docx_export_available",
                return_value=True,
            ), patch(
                "gui.reporting_tab.QFileDialog.getSaveFileName",
                return_value=(path, "Word Document (*.docx)"),
            ), patch(
                "gui.reporting_tab.LoadingDialog",
                return_value=fake_dialog,
            ), patch(
                "gui.reporting_tab.ReportExportWorker",
                return_value=fake_worker,
            ) as worker_class:
                self.tab._on_export_docx()

            build = worker_class.call_args.args[0]
            result = build(lambda *_args: None, lambda: False)

            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), b"docx")
            with open(appendix_path, "rb") as fh:
                self.assertEqual(fh.read(), b"xlsx")
            self.assertEqual(result["appendix_path"], appendix_path)
            docx_kwargs = (
                self.tab.report_generator.generate_docx_from_html.call_args.kwargs
            )
            self.assertEqual(
                docx_kwargs["externalized_table_ids"],
                {"large-result-table"},
            )
            self.assertEqual(
                docx_kwargs["externalized_table_titles"],
                {"large-result-table": "Large Result Table"},
            )
            self.assertEqual(docx_kwargs["metadata"]["project_name"], "Project")
            fake_worker.start.assert_called_once()
            fake_dialog.exec.assert_called_once()

    def test_pdf_uses_webengine_async_api_behind_loading_dialog(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "report.pdf")
            fake_page = Mock()
            fake_web_view = Mock()
            fake_web_view.page.return_value = fake_page
            fake_dialog = Mock()
            self.tab.web_view = fake_web_view

            with patch("gui.reporting_tab.HAS_WEBENGINE", True), patch(
                "gui.reporting_tab.QFileDialog.getSaveFileName",
                return_value=(path, "PDF (*.pdf)"),
            ), patch(
                "gui.reporting_tab.LoadingDialog",
                return_value=fake_dialog,
            ) as dialog_class:
                self.tab._on_export_pdf()

            self.assertFalse(dialog_class.call_args.kwargs["cancellable"])
            fake_page.printToPdf.assert_called_once()
            layout = fake_page.printToPdf.call_args.args[1]
            margins = layout.margins(QPageLayout.Unit.Millimeter)
            self.assertAlmostEqual(margins.left(), 20.0, places=1)
            self.assertAlmostEqual(margins.top(), 20.0, places=1)
            self.assertAlmostEqual(margins.right(), 20.0, places=1)
            self.assertAlmostEqual(margins.bottom(), 25.0, places=1)
            fake_dialog.exec.assert_called_once()
            self.assertEqual(self.tab._pdf_export_path, path)

            with patch("gui.reporting_tab.QMessageBox.information"):
                self.tab._on_pdf_done(path, True)

            self.assertIsNone(self.tab._pdf_export_path)
            self.assertIsNone(self.tab._report_export_dialog)

    def test_pdf_export_externalizes_large_tables_when_excel_appendix_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "report.pdf")
            self.tab._excel_appendix_panel.setVisible(True)
            self.tab._excel_appendix_check.setChecked(True)
            table_rows = "".join(
                f"<tr><td>Sample {index}</td><td>{index}</td></tr>"
                for index in range(60)
            )
            self.tab.current_report_html = (
                "<html><body><h3>Large Result Table</h3>"
                "<table data-report-table='large-result-table'>"
                "<thead><tr><th>Sample</th><th>Value</th></tr></thead>"
                f"<tbody>{table_rows}</tbody></table></body></html>"
            )
            self.tab.report_generator.generate_excel_appendix = Mock(
                return_value=b"xlsx"
            )
            fake_page = Mock()
            fake_web_view = Mock()
            fake_web_view.page.return_value = fake_page
            fake_web_view.url.return_value.toLocalFile.return_value = ""
            fake_dialog = Mock()
            self.tab.web_view = fake_web_view
            preview_html = []

            with patch("gui.reporting_tab.HAS_WEBENGINE", True), patch(
                "gui.reporting_tab.QFileDialog.getSaveFileName",
                return_value=(path, "PDF (*.pdf)"),
            ), patch(
                "gui.reporting_tab.LoadingDialog",
                return_value=fake_dialog,
            ), patch.object(
                self.tab,
                "_set_preview_html",
                side_effect=preview_html.append,
            ), patch.object(
                self.tab,
                "_start_report_export_worker",
            ) as start_worker:
                self.tab._on_export_pdf()

                fake_page.printToPdf.assert_not_called()
                self.assertTrue(self.tab._pdf_print_after_preview_load)
                self.assertIn(
                    "Large table moved to companion Excel appendix",
                    preview_html[0],
                )
                self.assertNotIn("Sample 59", preview_html[0])

                self.tab._on_preview_load_finished(True)
                fake_page.printToPdf.assert_called_once()

                self.tab._on_pdf_done(path, True)
                self.assertIn("Sample 59", preview_html[-1])

            build = start_worker.call_args.args[0]
            result = build(lambda *_args: None, lambda: False)

            self.assertEqual(
                result["appendix_path"],
                os.path.join(directory, "report_tables.xlsx"),
            )
            appendix_html = (
                self.tab.report_generator.generate_excel_appendix.call_args.args[0]
            )
            self.assertIn("Sample 59", appendix_html)

    def test_failed_export_releases_guard(self):
        self.tab._report_export_worker = Mock()
        self.tab._report_export_dialog = Mock()

        with patch("gui.reporting_tab.QMessageBox.critical"):
            self.tab._on_report_export_failed("failure")

        self.assertIsNone(self.tab._report_export_worker)
        self.assertIsNone(self.tab._report_export_dialog)


if __name__ == "__main__":
    unittest.main(verbosity=2)
