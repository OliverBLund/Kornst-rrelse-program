"""
Regression tests for report-generation pre-flight validation.
"""

import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication, QSizePolicy

from data_loader import GrainSizeData
from k_calculations import CalculationStatus, KCalculationResult
from gui.reporting_tab import ReportingTab

APP = QApplication.instance() or QApplication([])


class _FakeDatasetTab:
    """Minimal dataset-tab stand-in for the report thunk factories.

    Exposes only what `_build_*_thunk` touches; lacks `plot_workspace`, so
    `build_plot_context_from_tab` returns an empty context (fine for a report).
    """

    def __init__(self, name: str):
        self._dataset = GrainSizeData(
            sample_name=name, temperature=20.0, porosity=0.35,
            particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
            percent_passing=[100.0, 95.0, 82.0, 61.0, 38.0, 14.0, 4.0],
        )
        self.temperature = 20.0
        self.porosity = 0.35

    def get_dataset(self):
        return self._dataset

    def get_dataset_name(self):
        return self._dataset.sample_name

    def get_results(self):
        return [KCalculationResult(
            method_name="Hazen", k_value=1.0e-4, formula_used="",
            status=CalculationStatus.OK, status_message="", conditions_met=True,
            temperature=20.0, porosity=0.35, grain_size_used="D10",
        )]


def _run_worker(worker, timeout_ms=15000):
    """Drive a ReportWorker to completion on the test event loop; return outcome."""
    out = {}
    loop = QEventLoop()
    worker.progress.connect(lambda c, t, l: out.setdefault("progress", []).append((c, t, l)))
    worker.finished_html.connect(lambda h: (out.__setitem__("html", h), loop.quit()))
    worker.failed.connect(lambda m: (out.__setitem__("error", m), loop.quit()))
    worker.cancelled.connect(lambda: (out.__setitem__("cancelled", True), loop.quit()))
    QTimer.singleShot(timeout_ms, loop.quit)
    worker.start()
    loop.exec()
    worker.wait(2000)
    return out


def _state(type_id: int, selected: list[bool], dataset_count: int):
    return SimpleNamespace(
        dataset_tabs=[object()] * dataset_count,
        _sample_selected=selected,
        _selected_type=type_id,
        TYPE_INDIVIDUAL=ReportingTab.TYPE_INDIVIDUAL,
        TYPE_COMPARISON=ReportingTab.TYPE_COMPARISON,
        TYPE_KFOCUS=ReportingTab.TYPE_KFOCUS,
    )


class TestReportingTabValidation(unittest.TestCase):
    def test_comparison_report_requires_two_selected_samples(self):
        state = _state(ReportingTab.TYPE_COMPARISON, [True], 1)

        title, message = ReportingTab._generation_validation_error(state)

        self.assertEqual(title, "Select At Least Two Samples")
        self.assertIn("two or more samples", message)

    def test_individual_report_accepts_one_selected_sample(self):
        state = _state(ReportingTab.TYPE_INDIVIDUAL, [True], 1)

        self.assertIsNone(ReportingTab._generation_validation_error(state))

    def test_preview_css_does_not_inject_page_number_bars(self):
        html = "<html><head></head><body><h1>Report</h1></body></html>"

        injected = ReportingTab._inject_preview_css(html)

        self.assertNotIn("preview-page-sep", injected)
        self.assertNotIn("Page ' +", injected)


class TestReportingTabTypePresets(unittest.TestCase):
    def setUp(self):
        self.tab = ReportingTab()

    def tearDown(self):
        self.tab.deleteLater()

    def _apply(self, type_id: int):
        self.tab._set_type_selection(type_id)
        self.tab._apply_type_preset(type_id)

    def test_sample_hint_wraps_inside_available_width(self):
        self._apply(ReportingTab.TYPE_COMPARISON)

        self.assertTrue(self.tab._samp_hint_lbl.wordWrap())
        self.assertEqual(
            self.tab._samp_hint_lbl.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Ignored,
        )
        self.assertIn("Group/overall", self.tab._samp_hint_lbl.text())

    def test_kfocus_enables_plots_section(self):
        # Regression: K-Focus previously forced plots off, so its report had no
        # figures despite the hint promising K-distribution plots.
        self._apply(ReportingTab.TYPE_KFOCUS)
        self.assertTrue(self.tab._collect_sections()["plots"])

    def test_kfocus_defaults_to_k_only_plots(self):
        self._apply(ReportingTab.TYPE_KFOCUS)
        selected = self.tab._collect_selected_plots("collection")
        self.assertEqual(
            selected,
            {
                "k_value_comparison", "statistical_boxplots",
                "k_distribution", "reliability_matrix",
            },
        )
        # The grain-size comparison is dropped for the K-focused report.
        self.assertNotIn("distribution_overlay", selected)

    def test_comparison_keeps_grain_size_comparison(self):
        self._apply(ReportingTab.TYPE_COMPARISON)
        selected = self.tab._collect_selected_plots("collection")
        self.assertIn("distribution_overlay", selected)
        self.assertIn("grain_size_histogram_comparison", selected)
        self.assertNotIn("k_distribution", selected)

    def test_per_sample_plots_are_available_but_template_specific(self):
        for key in ("per_sample_grain", "per_sample_histogram", "per_sample_kbar"):
            self.assertIn(key, self.tab._plot_rows["collection"])

        for type_id in (ReportingTab.TYPE_COMPARISON, ReportingTab.TYPE_KFOCUS):
            self._apply(type_id)
            selected = self.tab._collect_selected_plots("collection")
            self.assertNotIn("per_sample_grain", selected)
            self.assertNotIn("per_sample_histogram", selected)
            self.assertNotIn("per_sample_kbar", selected)

        self._apply(ReportingTab.TYPE_FULL)
        selected = self.tab._collect_selected_plots("collection")
        self.assertIn("per_sample_grain", selected)
        self.assertIn("per_sample_histogram", selected)
        self.assertIn("per_sample_kbar", selected)

    def test_plot_row_changes_mark_template_modified(self):
        self._apply(ReportingTab.TYPE_COMPARISON)
        self.assertFalse(self.tab._is_modified_from_preset())

        self.tab._plot_rows["collection"]["k_distribution"].set_checked(True)

        self.assertTrue(self.tab._is_modified_from_preset())

    def test_plot_rows_stay_visible_for_all_report_types(self):
        for type_id in (ReportingTab.TYPE_INDIVIDUAL, ReportingTab.TYPE_FULL,
                        ReportingTab.TYPE_COMPARISON, ReportingTab.TYPE_KFOCUS):
            self._apply(type_id)
            self.assertEqual(self.tab._plots_header_lbl.text(), "PLOTS TO INCLUDE")
            for rows in self.tab._plot_rows.values():
                for row in rows.values():
                    self.assertFalse(row.isHidden())

    def test_preview_tempfile_holds_full_html_and_reuses_path(self):
        # Large reports must not go through setHtml (2 MB data-URL cap); the
        # temp file backing the preview holds the whole HTML and is reused.
        import os

        big_html = "<html><body>" + ("<p>x</p>" * 1000) + "</body></html>"
        path = self.tab._write_preview_tempfile(big_html)
        try:
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), big_html)
            # Re-render overwrites the same file rather than leaking new ones.
            self.assertEqual(self.tab._write_preview_tempfile("<html>2</html>"), path)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "<html>2</html>")
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_pdf_save_waits_for_loaded_web_preview(self):
        import gui.reporting_tab as reporting_tab

        self.tab.current_report_html = "<html>ready</html>"
        self.tab._format_combo.setCurrentText("PDF")
        self.tab._preview_load_ready = False
        self.tab._update_preview_action_buttons()
        self.assertFalse(self.tab.btn_save.isEnabled())

        self.tab._format_combo.setCurrentText("HTML")
        self.tab._update_preview_action_buttons()
        self.assertTrue(self.tab.btn_save.isEnabled())

        self.tab._format_combo.setCurrentText("PDF")
        self.tab._preview_load_ready = True
        self.tab._update_preview_action_buttons()
        self.assertEqual(self.tab.btn_save.isEnabled(), reporting_tab.HAS_WEBENGINE)


class TestReportGenerationThreading(unittest.TestCase):
    """Report generation runs on a worker thread with progress + cancel."""

    def setUp(self):
        from gui.report_worker import ReportWorker  # noqa: F401
        self.tab = ReportingTab()
        self.tab.set_dataset_tabs([_FakeDatasetTab("Sample A"), _FakeDatasetTab("Sample B")])

    def tearDown(self):
        self.tab.deleteLater()

    def test_comparison_thunk_runs_on_worker_and_returns_html(self):
        from gui.report_worker import ReportWorker

        self.tab._set_type_selection(ReportingTab.TYPE_COMPARISON)
        self.tab._apply_type_preset(ReportingTab.TYPE_COMPARISON)
        build = self.tab._build_comparison_thunk(
            self.tab._collect_brand(), self.tab._collect_metadata(),
            self.tab._collect_sections(), self.tab._selected_sample_contexts(),
        )
        out = _run_worker(ReportWorker(build))
        self.assertIn("html", out, msg=out.get("error"))
        self.assertIn("<", out["html"])
        # Progress was reported (at least the coarse comparison + finalize steps).
        self.assertGreaterEqual(len(out.get("progress", [])), 1)

    def test_cancelled_generation_emits_cancelled(self):
        from gui.report_worker import ReportWorker

        self.tab._set_type_selection(ReportingTab.TYPE_FULL)
        self.tab._apply_type_preset(ReportingTab.TYPE_FULL)
        # Enable per-sample plots so there are cancellable per-sample steps.
        for key in ("per_sample_grain", "per_sample_kbar"):
            self.tab._plot_rows["collection"][key].set_checked(True)
        build = self.tab._build_comparison_thunk(
            self.tab._collect_brand(), self.tab._collect_metadata(),
            self.tab._collect_sections(), self.tab._sample_contexts, scope="full",
        )
        worker = ReportWorker(build)
        worker.cancel()  # request cancellation up front
        out = _run_worker(worker)
        self.assertTrue(out.get("cancelled"))
        self.assertNotIn("html", out)

    def test_generate_does_not_start_second_worker_while_running(self):
        # The re-entrancy guard: a pending worker blocks another generation.
        self.tab._report_worker = object()
        self.tab._set_type_selection(ReportingTab.TYPE_COMPARISON)
        # _on_generate should early-return (no crash, no new dialog/worker).
        self.tab._on_generate()
        self.assertIsNotNone(self.tab._report_worker)


if __name__ == "__main__":
    unittest.main(verbosity=2)
