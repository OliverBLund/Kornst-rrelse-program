"""
Regression tests for calculated-porosity mode behavior.
"""

import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from data_loader import GrainSizeData
from gui.control_panel import ControlPanel


class _Label:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _FakeStats:
    def __init__(self):
        self.porosity = None
        self.updated = 0

    def update_display(self):
        self.updated += 1


class _FakeDatasetTab:
    def __init__(self, dataset, *, has_results=True):
        self.dataset = dataset
        self.porosity = dataset.current_porosity
        self.current_results = [object()] if has_results else []
        self.statistics_tab = _FakeStats()
        self.grain_updates = 0
        self.k_recalculations = 0

    def update_grain_statistics(self):
        self.grain_updates += 1

    def calculate_k_values(self):
        self.k_recalculations += 1


class _FakeTabWidget:
    def __init__(self, widgets):
        self._widgets = list(widgets)

    def count(self):
        return len(self._widgets)

    def widget(self, index):
        return self._widgets[index]


class _Parent:
    def __init__(self, widgets):
        self.dataset_tabs_widget = _FakeTabWidget(widgets)


class _ControlPanelHarness:
    on_porosity_mode_changed = ControlPanel.on_porosity_mode_changed

    def __init__(self, parent):
        self._parent = parent
        self.sample_info_label = _Label()

    def parent(self):
        return self._parent


def _build_dataset() -> GrainSizeData:
    return GrainSizeData(
        sample_name="Sample A",
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25],
        percent_passing=[100.0, 84.0, 55.0, 28.0, 10.0],
        file_path="sample_a.csv",
    )


class TestPorosityMode(unittest.TestCase):
    def test_recalculate_porosity_updates_auto_managed_dataset(self):
        dataset = _build_dataset()
        old_simple = dataset.calculated_porosity
        expected = dataset._calculate_urumovic_porosity()
        tab = _FakeDatasetTab(dataset)
        harness = _ControlPanelHarness(_Parent([tab]))

        harness.on_porosity_mode_changed("Urumovic Polynomial (Research)")

        self.assertNotEqual(old_simple, expected)
        self.assertEqual(dataset.calculated_porosity, expected)
        self.assertEqual(dataset.current_porosity, expected)
        self.assertEqual(tab.porosity, expected)
        self.assertEqual(tab.statistics_tab.porosity, expected)
        self.assertEqual(tab.statistics_tab.updated, 1)
        self.assertEqual(tab.grain_updates, 1)
        self.assertEqual(tab.k_recalculations, 1)
        self.assertIn("Calculated porosity set to Urumovic Polynomial", harness.sample_info_label.text)

    def test_recalculate_porosity_preserves_manual_override(self):
        dataset = _build_dataset()
        dataset.current_porosity = 0.55
        dataset.porosity = 0.55
        previous_manual = dataset.current_porosity
        expected = dataset._calculate_urumovic_porosity()
        tab = _FakeDatasetTab(dataset, has_results=False)
        harness = _ControlPanelHarness(_Parent([tab]))

        harness.on_porosity_mode_changed("Urumovic Polynomial (Research)")

        self.assertEqual(dataset.calculated_porosity, expected)
        self.assertEqual(dataset.current_porosity, previous_manual)
        self.assertEqual(tab.porosity, previous_manual)
        self.assertEqual(tab.statistics_tab.porosity, previous_manual)
        self.assertIn("preserved 1 manual override", harness.sample_info_label.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
