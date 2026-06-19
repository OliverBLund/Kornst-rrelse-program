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
from grain_classification import USCS
from gui.comparison_tab import ComparisonTab
from k_calculations_v2 import CalculationStatus, KCalculationResult
from unit_conversions import HydraulicConductivityUnit


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


def build_results(scale: float, flagged_method: str | None = None) -> list[KCalculationResult]:
    return [
        KCalculationResult(
            method_name='Hazen',
            k_value=1.0e-4 * scale,
            formula_used='',
            status=CalculationStatus.WARNING if flagged_method == 'Hazen' else CalculationStatus.OK,
            status_message='',
            conditions_met=flagged_method != 'Hazen',
            temperature=20.0,
            porosity=0.35,
            grain_size_used='D10',
        ),
        KCalculationResult(
            method_name='Beyer',
            k_value=1.5e-4 * scale,
            formula_used='',
            status=CalculationStatus.WARNING if flagged_method == 'Beyer' else CalculationStatus.OK,
            status_message='',
            conditions_met=flagged_method != 'Beyer',
            temperature=20.0,
            porosity=0.35,
            grain_size_used='D10',
        ),
    ]


class DummyDatasetTab:
    def __init__(self, name: str, file_key: str, scale: float, group: str = 'Ungrouped'):
        self.dataset = build_dataset(name, file_key)
        self.dataset.group_name = group
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
            def __init__(self, dataset_tabs, currently_selected=None, parent=None, **_kwargs):
                self._tabs = dataset_tabs
                self._selected = [dataset_tabs[1], dataset_tabs[2]]

            def exec(self):
                return True

            def get_selected_tabs(self):
                return self._selected

            def get_group_assignments(self):
                return {
                    self._tabs[1]: 'Layer 1',
                    self._tabs[2]: 'Layer 2',
                }

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
        self.assertEqual(self.tabs[1].dataset.group_name, 'Layer 1')
        self.assertEqual(self.tabs[2].dataset.group_name, 'Layer 2')

    def test_plot_pin_filters_visible_plot_datasets(self):
        self.tabs[0].dataset.group_name = 'Layer 1'
        self.tabs[1].dataset.group_name = 'Layer 1'
        self.tabs[2].dataset.group_name = 'Layer 2'
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.widget._toggle_pin('Sample B')

        plotted = [dataset.sample_name for dataset in self.widget._plot_widget.datasets]
        self.assertEqual(plotted, ['Sample B'])
        self.assertIn('Focused: 1 visible of 3 scoped', self.widget._pin_scope_label.text())

    def test_plot_dataset_visibility_hides_without_changing_scope(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.widget._toggle_plot_visibility('Sample B')

        plotted = [dataset.sample_name for dataset in self.widget._plot_widget.datasets]
        self.assertEqual(plotted, ['Sample A', 'Sample C'])
        self.assertEqual(
            [tab.get_dataset_name() for tab in self.widget.selected_datasets],
            ['Sample A', 'Sample B', 'Sample C'],
        )
        self.assertIn('Visible: 2 of 3 scoped', self.widget._pin_scope_label.text())

        self.widget._toggle_plot_visibility('Sample B')

        plotted = [dataset.sample_name for dataset in self.widget._plot_widget.datasets]
        self.assertEqual(plotted, ['Sample A', 'Sample B', 'Sample C'])

    def test_plot_group_visibility_hides_group_without_changing_scope(self):
        self.tabs[0].dataset.group_name = 'Layer 1'
        self.tabs[1].dataset.group_name = 'Layer 1'
        self.tabs[2].dataset.group_name = 'Layer 2'
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.widget._toggle_group_visibility('Layer 1')

        plotted = [dataset.sample_name for dataset in self.widget._plot_widget.datasets]
        self.assertEqual(plotted, ['Sample C'])
        self.assertEqual(
            [tab.get_dataset_name() for tab in self.widget.selected_datasets],
            ['Sample A', 'Sample B', 'Sample C'],
        )
        self.assertIn('Visible: 1 of 3 scoped', self.widget._pin_scope_label.text())

        self.widget._toggle_group_visibility('Layer 1')

        plotted = [dataset.sample_name for dataset in self.widget._plot_widget.datasets]
        self.assertEqual(plotted, ['Sample A', 'Sample B', 'Sample C'])

    def test_plot_group_pin_focuses_group_and_show_all_resets(self):
        self.tabs[0].dataset.group_name = 'Layer 1'
        self.tabs[1].dataset.group_name = 'Layer 1'
        self.tabs[2].dataset.group_name = 'Layer 2'
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.widget._toggle_group_pin('Layer 1')

        plotted = [dataset.sample_name for dataset in self.widget._plot_widget.datasets]
        self.assertEqual(plotted, ['Sample A', 'Sample B'])
        self.assertEqual(self.widget._pinned, {'Sample A', 'Sample B'})
        self.assertIn('Focused: 2 visible of 3 scoped', self.widget._pin_scope_label.text())

        self.widget._show_all_plot_datasets()

        plotted = [dataset.sample_name for dataset in self.widget._plot_widget.datasets]
        self.assertEqual(plotted, ['Sample A', 'Sample B', 'Sample C'])
        self.assertFalse(self.widget._pinned)
        self.assertFalse(self.widget._plot_hidden)

    def test_details_defaults_to_grain_core_and_elides_long_headers(self):
        long_tabs = [
            DummyDatasetTab('Very Long Borehole Sample Name Alpha', 'A.csv', 1.0),
            DummyDatasetTab('Very Long Borehole Sample Name Beta', 'B.csv', 1.5),
            DummyDatasetTab('Very Long Borehole Sample Name Gamma', 'C.csv', 2.0),
        ]

        self.widget.set_dataset_state(long_tabs, selected_tabs=long_tabs)

        self.assertEqual(self.widget._details_mode, 'grain')
        self.assertEqual(self.widget._details_preset, 'core')
        self.assertIs(self.widget._details_stack.currentWidget(), self.widget._grain_table)
        self.assertEqual(self.widget._details_preset_context_btn.text(), 'Classification')

        header = self.widget._grain_table.horizontalHeaderItem(1)
        self.assertEqual(header.toolTip(), 'Very Long Borehole Sample Name Alpha')
        self.assertNotEqual(header.text(), header.toolTip())

    def test_details_mode_switch_updates_context_and_status_visibility(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.widget._set_details_mode('k')

        self.assertIs(self.widget._details_stack.currentWidget(), self.widget._k_table)
        self.assertEqual(self.widget._details_preset, 'all')
        self.assertEqual(self.widget._details_preset_context_btn.text(), 'Aggregate rows')
        self.assertFalse(self.widget._details_status_section.isHidden())
        self.assertFalse(self.widget._details_unit_lbl.isHidden())
        self.assertFalse(self.widget._details_unit_combo.isHidden())

    def test_details_aggregate_mode_shows_snapshot_table(self):
        self.tabs[0].dataset.group_name = 'Layer 1'
        self.tabs[1].dataset.group_name = 'Layer 2'
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs[:2])

        self.widget._set_details_view_mode('aggregate')

        self.assertIs(self.widget._details_stack.currentWidget(), self.widget._aggregate_table)
        self.assertFalse(self.widget._aggregate_table.isSortingEnabled())
        self.assertFalse(self.widget._aggregate_table.horizontalHeader().sectionsClickable())
        headers = [
            self.widget._aggregate_table.horizontalHeaderItem(col).text()
            for col in range(self.widget._aggregate_table.columnCount())
        ]
        self.assertIn('Overall', headers)
        self.assertIn('Layer 1', headers)
        self.assertIn('Layer 2', headers)
        header = self.widget._aggregate_table.horizontalHeader()
        for col in range(1, self.widget._aggregate_table.columnCount()):
            self.assertEqual(
                header.sectionResizeMode(col),
                comparison_tab_module.QHeaderView.ResizeMode.Stretch,
            )
        group_chip_texts = [
            self.widget._details_dataset_chips_layout.itemAt(i).widget().layout().itemAt(1).widget().text()
            for i in range(self.widget._details_dataset_chips_layout.count() - 1)
        ]
        self.assertTrue(any('Layer 1' in text for text in group_chip_texts))
        self.assertTrue(any('Layer 2' in text for text in group_chip_texts))
        labels = []
        for row in range(self.widget._aggregate_table.rowCount()):
            cell_widget = self.widget._aggregate_table.cellWidget(row, 0)
            if cell_widget is None:
                continue
            labels.append(cell_widget.layout().itemAt(0).widget().text())
        self.assertIn('K arithmetic mean', labels)
        self.assertIn('Mean grain size', labels)

    def test_details_aggregate_mode_hides_individual_grain_k_toggle(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.assertFalse(self.widget._details_mode_frame.isHidden())

        self.widget._set_details_view_mode('aggregate')

        self.assertTrue(self.widget._details_mode_frame.isHidden())
        self.assertIs(self.widget._details_stack.currentWidget(), self.widget._aggregate_table)

        self.widget._set_details_view_mode('individual')

        self.assertFalse(self.widget._details_mode_frame.isHidden())

    def test_grain_core_preset_hides_non_core_rows(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        d84_row = next(
            row for row, row_def in enumerate(self.widget._GRAIN_ROWS)
            if row_def[0] == 'D84'
        )
        d50_row = next(
            row for row, row_def in enumerate(self.widget._GRAIN_ROWS)
            if row_def[0] == 'D50'
        )

        self.assertTrue(self.widget._grain_table.isRowHidden(d84_row))
        self.assertFalse(self.widget._grain_table.isRowHidden(d50_row))

    def test_k_summary_preset_hides_method_rows(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)
        self.widget._set_details_mode('k')
        self.widget._set_details_preset('context')

        labels = []
        for row in range(self.widget._k_table.rowCount()):
            cell_widget = self.widget._k_table.cellWidget(row, 0)
            name = cell_widget.layout().itemAt(0).widget().text()
            labels.append((name, self.widget._k_table.isRowHidden(row)))

        hazen_hidden = dict(labels)['Hazen']
        summary_visible = dict(labels)['K\u0304 geometric']

        self.assertTrue(hazen_hidden)
        self.assertFalse(summary_visible)

    def test_mode_specific_presets_are_preserved_between_grain_and_k_views(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.widget._set_details_preset('all')
        self.widget._set_details_mode('k')
        self.widget._set_details_preset('context')
        self.widget._set_details_mode('grain')

        self.assertEqual(self.widget._details_preset, 'all')

        self.widget._set_details_mode('k')
        self.assertEqual(self.widget._details_preset, 'context')

    def test_details_k_unit_switch_reformats_values_and_context(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)
        self.widget._set_details_mode('k')

        source_index = self.widget._details_unit_combo.findData(HydraulicConductivityUnit.M_PER_S)
        self.widget._details_unit_combo.setCurrentIndex(source_index)
        mps_value = self.widget._k_table.item(0, 1).text()

        target_index = self.widget._details_unit_combo.findData(HydraulicConductivityUnit.M_PER_DAY)
        self.widget._details_unit_combo.setCurrentIndex(target_index)
        md_value = self.widget._k_table.item(0, 1).text()

        self.assertNotEqual(mps_value, md_value)
        self.assertIn('m/d', self.widget._details_context.text())
        self.assertIn('m/d', self.widget._details_focus_strip.text())

    def test_details_dataset_strip_is_hidden_until_aggregate_mode(self):
        self.tabs[0].dataset.group_name = 'Layer 1'
        self.tabs[1].dataset.group_name = 'Layer 1'
        self.tabs[2].dataset.group_name = 'Layer 2'
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.assertTrue(self.widget._details_dataset_strip.isHidden())

        self.widget._set_details_view_mode('aggregate')
        chip_labels = [
            self.widget._details_dataset_chips_layout.itemAt(i).widget().layout().itemAt(1).widget().text()
            for i in range(self.widget._details_dataset_chips_layout.count() - 1)
        ]

        self.assertFalse(self.widget._details_dataset_strip.isHidden())
        self.assertEqual(chip_labels, ['Layer 1 (2)', 'Layer 2 (1)'])

    def test_grain_heat_toggle_applies_visible_background_role(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)
        self.assertFalse(self.widget._heat_btn.isChecked())

        self.widget._heat_btn.setChecked(True)

        d50_row = next(
            row for row, row_def in enumerate(self.widget._GRAIN_ROWS)
            if row_def[0] == 'D50'
        )
        heated_item = self.widget._grain_table.item(d50_row, 1)
        heated_color = heated_item.data(comparison_tab_module.Qt.ItemDataRole.BackgroundRole)
        heated_widget = self.widget._grain_table.cellWidget(d50_row, 1)

        self.assertIsNotNone(heated_color)
        self.assertGreater(heated_color.alpha(), 0)
        self.assertIn(heated_color.name(), heated_widget.styleSheet())

    def test_method_column_uses_hidden_sort_item_without_duplicate_visible_text(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)
        self.widget._set_details_mode('k')

        method_item = self.widget._k_table.item(0, 0)
        method_widget = self.widget._k_table.cellWidget(0, 0)
        method_label = method_widget.layout().itemAt(0).widget().text()

        self.assertEqual(method_item.text(), '')
        self.assertEqual(method_item.data(comparison_tab_module.Qt.ItemDataRole.UserRole), method_label.lower())

    def test_grain_table_header_sort_reorders_rows_by_dataset_values(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)
        self.widget._set_details_preset('all')

        self.widget._grain_table.sortItems(1, comparison_tab_module.Qt.SortOrder.DescendingOrder)

        values = []
        for row in range(self.widget._grain_table.rowCount()):
            if self.widget._grain_table.isRowHidden(row):
                continue
            sort_value = self.widget._grain_table.item(row, 1).data(
                comparison_tab_module.Qt.ItemDataRole.UserRole
            )
            if isinstance(sort_value, (int, float)) and sort_value != float('inf'):
                values.append(sort_value)

        self.assertGreater(len(values), 3)
        self.assertEqual(values, sorted(values, reverse=True))

    def test_details_row_header_column_has_readable_fixed_width(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.assertGreaterEqual(self.widget._grain_table.columnWidth(0), 200)

        self.widget._set_details_mode('k')
        self.assertGreaterEqual(self.widget._k_table.columnWidth(0), 200)

    def test_dataset_subset_change_recalculates_details_heat_cells(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)
        self.widget._heat_btn.setChecked(True)
        self.widget._set_details_mode('k')

        hazen_row = next(
            row for row in range(self.widget._k_table.rowCount())
            if self.widget._k_table.cellWidget(row, 0).layout().itemAt(0).widget().text() == 'Hazen'
        )
        sample_b_initial = self.widget._k_table.cellWidget(hazen_row, 2).styleSheet()

        self.widget.set_dataset_state(self.tabs, selected_tabs=[self.tabs[1], self.tabs[2]])
        self.widget._set_details_mode('k')
        hazen_row = next(
            row for row in range(self.widget._k_table.rowCount())
            if self.widget._k_table.cellWidget(row, 0).layout().itemAt(0).widget().text() == 'Hazen'
        )
        sample_b_after_subset_change = self.widget._k_table.cellWidget(hazen_row, 1).styleSheet()

        self.assertNotEqual(sample_b_initial, sample_b_after_subset_change)
        self.assertIn(comparison_tab_module._heat_color(0.0).name(), sample_b_after_subset_change)

    def test_result_change_recalculates_details_heat_cells_on_update(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)
        self.widget._heat_btn.setChecked(True)
        self.widget._set_details_mode('k')

        hazen_row = next(
            row for row in range(self.widget._k_table.rowCount())
            if self.widget._k_table.cellWidget(row, 0).layout().itemAt(0).widget().text() == 'Hazen'
        )
        sample_b_initial = self.widget._k_table.cellWidget(hazen_row, 2).styleSheet()

        self.tabs[1]._results = build_results(4.0)
        self.widget.update_comparison()
        hazen_row = next(
            row for row in range(self.widget._k_table.rowCount())
            if self.widget._k_table.cellWidget(row, 0).layout().itemAt(0).widget().text() == 'Hazen'
        )
        sample_b_after_result_change = self.widget._k_table.cellWidget(hazen_row, 2).styleSheet()

        self.assertNotEqual(sample_b_initial, sample_b_after_result_change)
        self.assertIn(comparison_tab_module._heat_color(1.0).name(), sample_b_after_result_change)

    def test_details_heat_legend_uses_real_palette_swatch_widgets(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.assertTrue(self.widget._details_legend_section.isHidden())
        self.widget._heat_btn.setChecked(True)

        legend_frames = self.widget._details_legend_section.findChildren(comparison_tab_module.QFrame)
        swatches = [
            frame for frame in legend_frames
            if frame.width() == 16 and frame.height() == 16 and 'background:' in frame.styleSheet()
        ]

        self.assertEqual(len(swatches), 3)
        self.assertIn(comparison_tab_module._heat_color(0.0).name(), swatches[0].styleSheet())
        self.assertIn(comparison_tab_module._heat_color(0.5).name(), swatches[1].styleSheet())
        self.assertIn(comparison_tab_module._heat_color(1.0).name(), swatches[2].styleSheet())

        self.widget._heat_btn.setChecked(False)
        self.assertTrue(self.widget._details_legend_section.isHidden())

    def test_entering_details_tab_resets_heat_coloring(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)
        self.widget._heat_btn.setChecked(True)

        details_index = next(
            index for index in range(self.widget._tabs.count())
            if self.widget._tabs.tabText(index) == 'Details'
        )
        self.widget._tabs.setCurrentIndex(details_index)

        self.assertFalse(self.widget._heat_btn.isChecked())
        self.assertEqual(self.widget._heat_btn.text(), 'Off')

    def test_k_table_header_sort_reorders_rows_by_dataset_values(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)
        self.widget._set_details_mode('k')

        self.widget._k_table.sortItems(1, comparison_tab_module.Qt.SortOrder.DescendingOrder)

        labels = [
            self.widget._k_table.cellWidget(row, 0).layout().itemAt(0).widget().text()
            for row in range(self.widget._k_table.rowCount())
            if not self.widget._k_table.isRowHidden(row)
        ]
        self.assertEqual(labels[:2], ['Beyer', 'Hazen'])
        self.assertEqual(labels[-5:], [
            'K\u0304 geometric',
            'K\u0304 arithmetic',
            'K median',
            'K std. dev.',
            'Perm. class',
        ])

        method_values = []
        for row in range(self.widget._k_table.rowCount()):
            if self.widget._k_table.isRowHidden(row):
                continue
            label = self.widget._k_table.cellWidget(row, 0).layout().itemAt(0).widget().text()
            if label.startswith('K\u0304') or label in {'K median', 'K std. dev.', 'Perm. class'}:
                continue
            sort_value = self.widget._k_table.item(row, 1).data(
                comparison_tab_module.Qt.ItemDataRole.UserRole
            )
            if isinstance(sort_value, (int, float)) and sort_value != float('inf'):
                method_values.append(sort_value)

        self.assertGreaterEqual(len(method_values), 2)
        self.assertEqual(method_values, sorted(method_values, reverse=True))

    def test_scheme_change_updates_scheme_sensitive_grain_rows(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        fines_row = next(
            row for row, row_def in enumerate(self.widget._GRAIN_ROWS)
            if row_def[0] == 'Fines%'
        )
        iso_value = self.widget._grain_table.item(fines_row, 1).text()

        self.widget.set_scheme(USCS)
        uscs_value = self.widget._grain_table.item(fines_row, 1).text()

        self.assertNotEqual(iso_value, uscs_value)
        self.assertIn('USCS', self.widget._details_context.text())

    def test_statistics_unit_switch_updates_boxplot_axis_label(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.assertIn('m/d', self.widget._stats_context.text())
        self.assertIn('m/d', self.widget._box_fig.axes[0].get_ylabel())

        source_index = self.widget._stats_unit_combo.findData(HydraulicConductivityUnit.M_PER_S)
        self.widget._stats_unit_combo.setCurrentIndex(source_index)

        self.assertIn('m/s', self.widget._stats_context.text())
        self.assertIn('m/s', self.widget._box_fig.axes[0].get_ylabel())

    def test_statistics_metric_toolbar_omits_ambiguous_range_button(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        metric_texts = [
            self.widget._stats_metric_geo_btn.text(),
            self.widget._stats_metric_arith_btn.text(),
            self.widget._stats_metric_med_btn.text(),
        ]
        self.assertEqual(metric_texts, ['Geo. mean', 'Arith. mean', 'Median'])
        self.assertFalse(hasattr(self.widget, '_stats_metric_range_btn'))

        scope_headers = [
            self.widget._stats_scope_table.horizontalHeaderItem(col).text()
            for col in range(self.widget._stats_scope_table.columnCount())
        ]
        self.assertTrue(any(header.startswith('K range') for header in scope_headers))

    def test_statistics_toolbar_and_tables_do_not_request_content_width_growth(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        fixed_controls = [
            self.widget._stats_view_spread_btn,
            self.widget._stats_view_coverage_btn,
            self.widget._stats_metric_geo_btn,
            self.widget._stats_metric_arith_btn,
            self.widget._stats_metric_med_btn,
            self.widget._stats_methods_all_btn,
            self.widget._stats_methods_valid_all_btn,
            self.widget._stats_ok_only_btn,
            self.widget._stats_warnings_btn,
        ]
        widths_before = [(button.minimumWidth(), button.maximumWidth()) for button in fixed_controls]

        self.widget._set_stats_method_scope(valid_in_all=True)
        source_index = self.widget._stats_unit_combo.findData(HydraulicConductivityUnit.M_PER_S)
        self.widget._stats_unit_combo.setCurrentIndex(source_index)
        self.widget._on_stats_metric_changed('arithmetic')

        widths_after = [(button.minimumWidth(), button.maximumWidth()) for button in fixed_controls]
        self.assertEqual(widths_before, widths_after)
        for button in fixed_controls:
            self.assertEqual(button.minimumWidth(), button.maximumWidth())
        for table in (self.widget._stats_scope_table, self.widget._stats_method_table):
            self.assertEqual(
                table.sizePolicy().horizontalPolicy(),
                comparison_tab_module.QSizePolicy.Policy.Ignored,
            )
            self.assertEqual(
                table.horizontalScrollMode(),
                comparison_tab_module.QAbstractItemView.ScrollMode.ScrollPerPixel,
            )

    def test_statistics_heatmap_uses_stable_domain_method_order(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        method_labels = [tick.get_text() for tick in self.widget._heat_fig.axes[0].get_yticklabels()]
        self.assertEqual(method_labels[:2], ['Hazen', 'Beyer'])

    def test_dataset_subset_change_rebuilds_statistics_heatmap_labels(self):
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        self.widget.set_dataset_state(self.tabs, selected_tabs=[self.tabs[1], self.tabs[2]])

        dataset_labels = [tick.get_text() for tick in self.widget._heat_fig.axes[0].get_xticklabels()]
        self.assertEqual(dataset_labels, ['Sample B', 'Sample C'])

    def test_statistics_group_scope_uses_overall_and_group_labels(self):
        self.tabs[0].dataset.group_name = 'Layer 1'
        self.tabs[1].dataset.group_name = 'Layer 1'
        self.tabs[2].dataset.group_name = 'Layer 2'

        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)
        self.widget._set_stats_view_mode('coverage')

        self.assertIs(self.widget._stats_stack.currentWidget(), self.widget._stats_coverage_panel)
        scope_labels = [tick.get_text() for tick in self.widget._heat_fig.axes[0].get_xticklabels()]
        self.assertEqual(scope_labels, ['Overall', 'Layer 1', 'Layer 2'])
        chip_texts = [
            self.widget._stats_dataset_chips_layout.itemAt(i).widget().layout().itemAt(1).widget().text()
            for i in range(self.widget._stats_dataset_chips_layout.count() - 1)
        ]
        self.assertTrue(any('Overall' in text for text in chip_texts))
        self.assertTrue(any('Layer 1' in text for text in chip_texts))
        self.assertTrue(any('Layer 2' in text for text in chip_texts))
        table_scope_labels = [
            self.widget._stats_scope_table.item(row, 0).text().splitlines()[0]
            for row in range(self.widget._stats_scope_table.rowCount())
        ]
        self.assertEqual(table_scope_labels, ['Overall', 'Layer 1', 'Layer 2'])

    def test_statistics_aggregation_defaults_to_ok_only_and_can_include_warnings(self):
        self.tabs[0]._results = build_results(1.0, flagged_method='Beyer')
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs[:2])

        report = self.widget._build_k_aggregation()
        self.assertEqual(report.by_dataset['Sample A'].included_count, 1)
        self.assertEqual(report.overall.warning_count, 1)
        self.assertEqual(report.overall.excluded_count, 1)

        self.widget._stats_include_warnings = True
        report = self.widget._build_k_aggregation()
        self.assertEqual(report.by_dataset['Sample A'].included_count, 2)
        self.assertEqual(report.overall.excluded_count, 0)

    def test_statistics_common_methods_filter_keeps_complete_methods_only(self):
        self.tabs[0]._results = build_results(1.0, flagged_method='Beyer')
        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs[:2])
        self.widget._stats_common_methods_only = True

        report = self.widget._build_k_aggregation()

        self.assertEqual(report.complete_methods, frozenset({'Hazen'}))
        self.assertEqual(report.overall.included_count, 2)
        self.assertEqual(report.by_method['Beyer'].included_count, 0)

    def test_statistics_summary_shows_group_aggregates_when_groups_exist(self):
        self.tabs[0].dataset.group_name = 'Layer 1'
        self.tabs[1].dataset.group_name = 'Layer 1'
        self.tabs[2].dataset.group_name = 'Layer 2'

        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        coverage = {}
        for i in range(self.widget._stats_summary_layout.count()):
            row = self.widget._stats_summary_layout.itemAt(i).widget()
            if row is None:
                continue
            labels = row.findChildren(comparison_tab_module.QLabel)
            if len(labels) >= 2:
                coverage[labels[0].text()] = labels[1].text()

        groups = {}
        for i in range(self.widget._stats_group_layout.count()):
            row = self.widget._stats_group_layout.itemAt(i).widget()
            if row is None:
                continue
            labels = row.findChildren(comparison_tab_module.QLabel)
            if len(labels) >= 2:
                groups[labels[0].text()] = labels[1].text()

        self.assertIn('Methods available', coverage)
        self.assertIn('Layer 1', groups)
        self.assertIn('Layer 2', groups)
        self.assertIn('datasets', groups['Layer 1'])

    def test_statistics_tables_show_scope_and_method_summaries(self):
        self.tabs[0].dataset.group_name = 'Layer 1'
        self.tabs[1].dataset.group_name = 'Layer 1'
        self.tabs[2].dataset.group_name = 'Layer 2'
        self.tabs[0]._results = build_results(1.0, flagged_method='Beyer')

        self.widget.set_dataset_state(self.tabs, selected_tabs=self.tabs)

        scope_headers = [
            self.widget._stats_scope_table.horizontalHeaderItem(col).text()
            for col in range(self.widget._stats_scope_table.columnCount())
        ]
        self.assertIn('Mean grain size', scope_headers)
        self.assertIn('Dominant class', scope_headers)

        method_headers = [
            self.widget._stats_method_table.horizontalHeaderItem(col).text()
            for col in range(self.widget._stats_method_table.columnCount())
        ]
        self.assertIn('Warnings', method_headers)
        self.assertIn('Valid groups', method_headers)
        self.assertTrue(any(header.startswith('Median K') for header in method_headers))

        methods = [
            self.widget._stats_method_table.item(row, 0).text()
            for row in range(self.widget._stats_method_table.rowCount())
        ]
        self.assertIn('Hazen', methods)
        self.assertIn('Beyer', methods)

        beyer_row = methods.index('Beyer')
        status_col = method_headers.index('Status')
        self.assertEqual(self.widget._stats_method_table.item(beyer_row, status_col).text(), 'Warn')


if __name__ == '__main__':
    unittest.main(verbosity=2)
