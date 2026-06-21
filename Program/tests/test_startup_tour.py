"""
Regression tests for the startup guide overlay proof of concept.
"""

import inspect
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

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
            self.assertFalse(hasattr(overlay, "_body_scroll"))
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
