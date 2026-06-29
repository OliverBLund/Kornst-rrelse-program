"""
Regression tests for the startup guide overlay proof of concept.
"""

import inspect
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from gui.main_window import MainWindow
from gui.startup_tour import StartupTourOverlay, TourStep


APP = QApplication.instance() or QApplication([])


class TestStartupTourOverlay(unittest.TestCase):
    def test_overlay_targets_real_widget_and_advances_steps(self):
        host = QWidget()
        layout = QVBoxLayout(host)
        first_target = QPushButton("Drop Files")
        second_target = QPushButton("Help")
        layout.addWidget(first_target)
        layout.addWidget(second_target)
        host.resize(640, 360)
        host.show()
        APP.processEvents()

        overlay = StartupTourOverlay(
            host,
            [
                TourStep(
                    title="Start by adding data",
                    body="Choose the import path.",
                    target=lambda: first_target,
                ),
                TourStep(
                    title="Open help",
                    body="Use help for detailed guides.",
                    target=lambda: second_target,
                ),
            ],
        )
        try:
            overlay.start()
            APP.processEvents()

            self.assertTrue(overlay.isVisible())
            self.assertEqual(overlay._title_lbl.text(), "Start by adding data")
            self.assertFalse(overlay._spotlight_rect.isNull())
            self.assertTrue(hasattr(overlay, "_body_scroll"))
            self.assertIn("QPushButton#startup-tour-next", overlay._next_btn.styleSheet())

            overlay._next_btn.click()
            APP.processEvents()

            self.assertEqual(overlay._title_lbl.text(), "Open help")
            self.assertEqual(overlay._count_lbl.text(), "2 / 2")
        finally:
            overlay.close()
            host.close()
            overlay.deleteLater()
            host.deleteLater()

    def test_overlay_expands_callout_body_for_long_text(self):
        host = QWidget()
        layout = QVBoxLayout(host)
        target = QPushButton("Reports")
        layout.addWidget(target)
        host.resize(640, 700)
        host.show()
        APP.processEvents()

        overlay = StartupTourOverlay(
            host,
            [
                TourStep(
                    title="Choose the report type",
                    body=(
                        "The report type controls the default scope and section preset. "
                        "Changing type is more than a label: it updates which samples are "
                        "expected, which tables are emphasized, and which plots are selected "
                        "by default."
                    ),
                    target=lambda: target,
                    tips=(
                        "Individual: exactly one sample, with detailed grain-size and K-method context.",
                        "Comparison: two or more selected samples, with group and overall summaries.",
                        "Full summary: every loaded sample, including appendices by default.",
                    ),
                    kicker="Reports",
                ),
            ],
            show_startup_checkbox=False,
        )
        try:
            overlay.start()
            APP.processEvents()

            self.assertGreater(overlay._body_content.minimumHeight(), 120)
            self.assertGreaterEqual(
                overlay._body_scroll.height(),
                overlay._body_content.minimumHeight() - 2,
            )
            self.assertEqual(
                overlay._body_scroll.verticalScrollBarPolicy(),
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
            )
            self.assertLessEqual(overlay._callout.height(), overlay.height() - 32)
        finally:
            overlay.close()
            host.close()
            overlay.deleteLater()
            host.deleteLater()

    def test_overlay_runs_step_callback_before_positioning(self):
        host = QWidget()
        layout = QVBoxLayout(host)
        first_target = QPushButton("First")
        second_target = QPushButton("Second")
        layout.addWidget(first_target)
        layout.addWidget(second_target)
        host.resize(640, 360)
        host.show()
        APP.processEvents()

        callbacks = []
        overlay = StartupTourOverlay(
            host,
            [
                TourStep(
                    title="First",
                    body="First step.",
                    target=lambda: first_target,
                    before_step=lambda: callbacks.append("first"),
                ),
                TourStep(
                    title="Second",
                    body="Second step.",
                    target=lambda: second_target,
                    before_step=lambda: callbacks.append("second"),
                ),
            ],
            show_startup_checkbox=False,
        )
        try:
            overlay.start()
            APP.processEvents()

            self.assertEqual(callbacks, ["first"])
            self.assertFalse(overlay._dont_show_check.isVisible())

            overlay._next_btn.click()
            APP.processEvents()

            self.assertEqual(callbacks, ["first", "second"])
            self.assertEqual(overlay._title_lbl.text(), "Second")
        finally:
            overlay.close()
            host.close()
            overlay.deleteLater()
            host.deleteLater()

    def test_main_window_exposes_startup_guide_menu_hook(self):
        setup_menus_source = inspect.getsource(MainWindow.setup_menus)
        show_source = inspect.getsource(MainWindow.show_startup_guide)
        launcher_source = inspect.getsource(MainWindow._start_tour_overlay)

        self.assertIn("Startup Guide", setup_menus_source)
        self.assertIn("show_startup_guide", setup_menus_source)
        self.assertIn("Analysis Settings", setup_menus_source)
        self.assertIn("open_analysis_settings_dialog", setup_menus_source)
        self.assertIn("StartupTourOverlay", launcher_source)
        self.assertIn("_global_tour_steps", show_source)

    def test_global_tour_uses_sidebar_import_and_main_tabs(self):
        steps_source = inspect.getsource(MainWindow._global_tour_steps)

        self.assertIn("_drop_zone", steps_source)
        self.assertIn("_file_list", steps_source)
        self.assertIn("_manage_samples_btn", steps_source)
        self.assertIn("_analysis_menu_btn", steps_source)
        self.assertIn("Classification Scheme", steps_source)
        self.assertIn("global calculation settings", steps_source)
        self.assertIn("_nav_btns[0]", steps_source)
        self.assertIn("_nav_btns[1]", steps_source)
        self.assertIn("_nav_btns[2]", steps_source)
        self.assertIn("_nav_btns[3]", steps_source)
        self.assertNotIn("_add_btn", steps_source)
        self.assertNotIn("_calc_btn", steps_source)

    def test_main_window_exposes_individual_samples_guide(self):
        setup_menus_source = inspect.getsource(MainWindow.setup_menus)
        show_source = inspect.getsource(MainWindow.show_individual_samples_guide)
        steps_source = inspect.getsource(MainWindow._individual_samples_tour_steps)

        self.assertIn("Guide &Individual Samples", setup_menus_source)
        self.assertIn("show_individual_samples_guide", setup_menus_source)
        self.assertIn("show_startup_checkbox=False", show_source)
        self.assertIn("before_step=plot_step", steps_source)
        self.assertIn("before_step=results_step", steps_source)
        self.assertIn("before_step=stats_step", steps_source)
        self.assertIn("Plot", steps_source)
        self.assertIn("Results", steps_source)
        self.assertIn("Statistics", steps_source)
        self.assertIn("controls sidebar", steps_source)
        self.assertIn("result cards", steps_source)
        self.assertNotIn("_mean_summary_bar", steps_source)


    def test_main_window_exposes_reports_guide(self):
        setup_menus_source = inspect.getsource(MainWindow.setup_menus)
        show_source = inspect.getsource(MainWindow.show_reports_guide)
        steps_source = inspect.getsource(MainWindow._reports_tour_steps)
        plot_target_source = inspect.getsource(MainWindow._report_plot_tour_target)

        self.assertIn("Guide &Reports", setup_menus_source)
        self.assertIn("show_reports_guide", setup_menus_source)
        self.assertIn("_switch_to_tab(2)", show_source)
        self.assertIn("show_startup_checkbox=False", show_source)
        self.assertIn("_reports_tour_steps", show_source)
        self.assertIn("PDF is fixed and static", steps_source)
        self.assertIn("Word (.docx) is editable", steps_source)
        self.assertIn("HTML is useful", steps_source)
        self.assertIn("companion Excel appendix", steps_source)
        self.assertIn("_format_combo", steps_source)
        self.assertIn("_samp_table", steps_source)
        self.assertIn("_acc_sects", steps_source)
        self.assertIn("_style_controls", steps_source)
        self.assertIn("generate_btn", steps_source)
        self.assertIn("btn_save", steps_source)
        self.assertIn("_plot_rows", plot_target_source)

    def test_main_window_exposes_export_guide(self):
        setup_menus_source = inspect.getsource(MainWindow.setup_menus)
        show_source = inspect.getsource(MainWindow.show_export_guide)
        steps_source = inspect.getsource(MainWindow._export_tour_steps)
        prep_source = inspect.getsource(MainWindow._prepare_export_tour_step)
        format_card_source = inspect.getsource(MainWindow._export_format_card)

        self.assertIn("Guide &Export", setup_menus_source)
        self.assertIn("show_export_guide", setup_menus_source)
        self.assertIn("_switch_to_tab(3)", show_source)
        self.assertIn("show_startup_checkbox=False", show_source)
        self.assertIn("_export_tour_steps", show_source)
        self.assertIn("CSV Long is tidy", steps_source)
        self.assertIn("CSV Wide is comparison-oriented", steps_source)
        self.assertIn("Excel creates one combined workbook", steps_source)
        self.assertIn("PNG is a raster image", steps_source)
        self.assertIn("SVG is vector graphics", steps_source)
        self.assertIn("PDF plot output is static", steps_source)
        self.assertIn("scope_segment_frame", steps_source)
        self.assertIn("file_tree", steps_source)
        self.assertIn("plot_queue_tree", steps_source)
        self.assertIn("preview_tabs", steps_source)
        self.assertIn("export_inspector_tabs", prep_source)
        self.assertIn("content_index", prep_source)
        self.assertIn("format_card_", format_card_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
