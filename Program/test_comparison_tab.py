"""
Regression tests for comparison tab dataset-selection state.
"""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, 'Program')

from PyQt6.QtWidgets import QApplication

import gui.comparison_tab as comparison_tab_module
from data_loader import GrainSizeData
from gui.comparison_tab import ComparisonTab
from k_calculations_v2 import CalculationStatus, KCalculationResult


APP = QApplication.instance() or QApplication([])


def build_dataset(name: str, file_key: str) -> GrainSizeData:
    return GrainSizeData(
        sample_name=name,
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
        percent_passing=[100.0, 95.0, 82.0, 61.0, 38.0, 14.0, 4.0],
        file_path=file_key,
    )


def build_results(scale: float) -> list[KCalculationResult]:
    return [
        KCalculationResult(
            method_name='Hazen',
            k_value=1.0e-4 * scale,
            formula_used='',
            status=CalculationStatus.OK,
            status_message='',
            conditions_met=True,
            temperature=20.0,
            porosity=0.35,
            grain_size_used='D10',
        ),
        KCalculationResult(
            method_name='Beyer',
            k_value=1.5e-4 * scale,
            formula_used='',
            status=CalculationStatus.OK,
            status_message='',
            conditions_met=True,
            temperature=20.0,
            porosity=0.35,
            grain_size_used='D10',
        ),
    ]


class DummyDatasetTab:
    def __init__(self, name: str, file_key: str, scale: float):
        self.dataset = build_dataset(name, file_key)
        self._results = build_results(scale)

    def get_dataset(self):
        return self.dataset

    def get_dataset_name(self):
        return self.dataset.sample_name

    def get_results(self):
        return self._results


class TestComparisonTabSelectionState(unittest.TestCase):
    def setUp(self):
        self.widget = ComparisonTab()
        self.tabs = [
            DummyDatasetTab('Sample A', 'A.csv', 1.0),
            DummyDatasetTab('Sample B', 'B.csv', 1.5),
            DummyDatasetTab('Sample C', 'C.csv', 2.0),
        ]

    def tearDown(self):
        self.widget.deleteLater()

    def test_set_dataset_state_tracks_loaded_and_selected_counts(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=[self.tabs[0], self.tabs[2]])

        self.assertEqual(len(self.widget.dataset_tabs), 3)
        self.assertEqual(
            [tab.get_dataset_name() for tab in self.widget.selected_datasets],
            ['Sample A', 'Sample C'],
        )
        self.assertIn('2 selected', self.widget._count_label.text())
        self.assertIn('3 loaded', self.widget._count_label.text())
        self.assertTrue(self.widget._update_btn.isEnabled())

    def test_manage_dialog_emits_sidebar_file_keys(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=[self.tabs[0], self.tabs[1]])

        captured: list[list[str]] = []
        self.widget.dataset_selection_requested.connect(captured.append)

        original_dialog = comparison_tab_module.DatasetSelectionDialog

        class FakeDialog:
            def __init__(self, dataset_tabs, currently_selected=None, parent=None):
                self._selected = [dataset_tabs[1], dataset_tabs[2]]

            def exec(self):
                return True

            def get_selected_tabs(self):
                return self._selected

        comparison_tab_module.DatasetSelectionDialog = FakeDialog
        try:
            self.widget._on_manage_datasets()
        finally:
            comparison_tab_module.DatasetSelectionDialog = original_dialog

        self.assertEqual(captured, [['B.csv', 'C.csv']])
        self.assertEqual(
            [tab.get_dataset_name() for tab in self.widget.selected_datasets],
            ['Sample B', 'Sample C'],
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
