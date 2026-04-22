"""
Regression tests for export manager CSV filtering behavior.
"""

import csv
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, 'Program')

from data_loader import GrainSizeData
from PyQt6.QtWidgets import QApplication
from gui.export_tab import ExportTab
from gui.export_manager import ExportManager
from gui.plot_styles import PROFESSIONAL_STYLE
from k_calculations_v2 import CalculationStatus, KCalculationResult

APP = QApplication.instance() or QApplication([])


def build_dataset(name: str = 'Sample A') -> GrainSizeData:
    """Create a stable grain-size dataset for export tests."""
    return GrainSizeData(
        sample_name=name,
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
        percent_passing=[100.0, 95.0, 82.0, 61.0, 38.0, 14.0, 4.0],
    )


def build_results() -> list[KCalculationResult]:
    """Create representative K-results spanning multiple method groups."""
    return [
        KCalculationResult(
            method_name='Hazen',
            k_value=1.0e-4,
            formula_used='k = c * d10^2',
            status=CalculationStatus.OK,
            status_message='',
            conditions_met=True,
            temperature=20.0,
            porosity=0.35,
            grain_size_used='D10',
        ),
        KCalculationResult(
            method_name='Beyer',
            k_value=1.5e-4,
            formula_used='k = c * d10^2 * log(500 / Cu)',
            status=CalculationStatus.OK,
            status_message='',
            conditions_met=True,
            temperature=20.0,
            porosity=0.35,
            grain_size_used='D10',
        ),
        KCalculationResult(
            method_name='USBR',
            k_value=2.5e-4,
            formula_used='k = c * d20^2.3',
            status=CalculationStatus.OK,
            status_message='',
            conditions_met=True,
            temperature=20.0,
            porosity=0.35,
            grain_size_used='D20',
        ),
    ]


def read_csv_rows(path: str) -> list[list[str]]:
    with open(path, newline='', encoding='utf-8') as handle:
        return list(csv.reader(handle))


def read_json(path: str) -> dict:
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


class TestExportManagerExports(unittest.TestCase):
    def setUp(self):
        self.dataset = build_dataset()
        self.results = build_results()
        self.datasets = [(self.dataset.sample_name, self.dataset, self.results)]

    def make_config(self, output_dir: str, **overrides):
        config = {
            'csv': True,
            'csv_mode': 'combined',
            'csv_long': True,
            'csv_wide': False,
            'excel': False,
            'json': False,
            'png': False,
            'svg': False,
            'pdf_plot': False,
            'grain_distribution': False,
            'percentiles': True,
            'gradation': True,
            'classification': False,
            'k_values': True,
            'statistics': False,
            'plots': False,
            'formulas': False,
            'validation': False,
            'k_filter_mode': 'all',
            'selected_k_categories': {
                'hazen_based': True,
                'porosity_dependent': True,
                'uniformity_dependent': True,
                'empirical': True,
                'temperature_corrected': True,
            },
            'selected_percentiles': ['d10', 'd20', 'd30', 'd50', 'd60'],
            'selected_k_methods': None,
            'k_units': {
                'm_s': True,
                'cm_s': True,
                'm_d': True,
            },
            'selected_statistics': ['mean', 'median', 'std_dev', 'min', 'max', 'valid_count'],
            'include_grain_size_stats': True,
            'include_metadata': {
                'sample_info': True,
                'environmental': True,
                'export_timestamp': True,
            },
            'output_dir': output_dir,
            'filename_template': '{sample_name}_results_{date}',
        }
        config.update(overrides)
        return config

    def test_combined_long_csv_respects_selected_methods_and_units(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.make_config(
                temp_dir,
                csv_long=True,
                csv_wide=False,
                k_filter_mode='individual',
                selected_k_methods=['Beyer', 'USBR'],
                k_units={'m_s': True, 'cm_s': False, 'm_d': True},
            )

            exported = ExportManager().export(self.datasets, config)

            self.assertEqual(len(exported), 1)
            export_name = os.path.basename(exported[0])
            self.assertIn('combined_all_datasets', export_name)

            rows = read_csv_rows(exported[0])
            header = rows[0]
            methods = [row[1] for row in rows[1:]]

            self.assertIn('K (m/s)', header)
            self.assertIn('K (m/d)', header)
            self.assertNotIn('K (cm/s)', header)
            self.assertEqual(methods, ['Beyer', 'USBR'])
            self.assertTrue(all(len(row) == len(header) for row in rows[1:]))

    def test_wide_csv_only_writes_requested_format_and_category_methods(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.make_config(
                temp_dir,
                csv_long=False,
                csv_wide=True,
                k_filter_mode='category',
                selected_k_categories={
                    'hazen_based': False,
                    'porosity_dependent': False,
                    'uniformity_dependent': True,
                    'empirical': False,
                    'temperature_corrected': False,
                },
                selected_percentiles=['d10', 'd60'],
                k_units={'m_s': False, 'cm_s': True, 'm_d': False},
                selected_statistics=['median', 'valid_count'],
            )

            exported = ExportManager().export(self.datasets, config)

            self.assertEqual(len(exported), 1)
            export_name = os.path.basename(exported[0])
            self.assertIn('wide_format_all_datasets', export_name)

            rows = read_csv_rows(exported[0])
            header = rows[0]
            data_row = rows[1]

            self.assertIn('D10_mm', header)
            self.assertIn('D60_mm', header)
            self.assertNotIn('D20_mm', header)
            self.assertIn('K_Beyer_cm/s', header)
            self.assertIn('Status_Beyer', header)
            self.assertIn('K_Median_cm/s', header)
            self.assertNotIn('K_Mean_cm/s', header)
            self.assertNotIn('K_Hazen_cm/s', header)
            self.assertNotIn('K_Beyer_m/s', header)
            self.assertNotIn('K_Beyer_m/d', header)
            self.assertEqual(data_row[header.index('Valid_Methods_Count')], '1')

    def test_separate_statistics_csv_uses_filtered_results_metadata_and_stat_selection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.make_config(
                temp_dir,
                csv_mode='separate',
                csv_long=True,
                csv_wide=False,
                grain_distribution=False,
                k_values=False,
                statistics=True,
                k_filter_mode='individual',
                selected_k_methods=['USBR'],
                k_units={'m_s': False, 'cm_s': False, 'm_d': True},
                selected_statistics=['median', 'valid_count'],
                include_grain_size_stats=False,
                include_metadata={
                    'sample_info': False,
                    'environmental': False,
                    'export_timestamp': True,
                },
            )

            exported = ExportManager().export(self.datasets, config)

            self.assertEqual(len(exported), 1)
            export_name = os.path.basename(exported[0])
            self.assertIn('statistics', export_name)

            rows = read_csv_rows(exported[0])
            timestamp_rows = [row for row in rows if row and row[0] == 'Export Timestamp']
            self.assertEqual(len(timestamp_rows), 1)
            self.assertTrue(timestamp_rows[0][1])
            self.assertIn(['Statistic', 'K (m/d)'], rows)
            self.assertIn(['Median', '21.60'], rows)
            self.assertIn(['Valid Count', '1'], rows)
            self.assertNotIn(['Mean', '21.60'], rows)
            self.assertNotIn(['Sample Name', self.dataset.sample_name], rows)
            self.assertFalse(any(row and row[0] == 'Grain Size Percentiles' for row in rows))

    def test_json_export_honors_metadata_units_and_selected_statistics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.make_config(
                temp_dir,
                csv=False,
                json=True,
                statistics=True,
                k_filter_mode='individual',
                selected_k_methods=['USBR'],
                k_units={'m_s': False, 'cm_s': True, 'm_d': False},
                selected_statistics=['median', 'valid_count'],
                include_metadata={
                    'sample_info': False,
                    'environmental': False,
                    'export_timestamp': True,
                },
            )

            exported = ExportManager().export(self.datasets, config)

            self.assertEqual(len(exported), 1)
            payload = read_json(exported[0])

            self.assertNotIn('sample_name', payload)
            self.assertEqual(set(payload['metadata'].keys()), {'exported_at'})
            self.assertTrue(payload['metadata']['exported_at'])
            self.assertEqual(len(payload['k_values']), 1)
            self.assertEqual(payload['k_values'][0]['method'], 'USBR')
            self.assertIn('k_cm_s', payload['k_values'][0])
            self.assertNotIn('k_m_s', payload['k_values'][0])
            self.assertNotIn('k_m_d', payload['k_values'][0])
            self.assertEqual(set(payload['statistics'].keys()), {'median_k_cm_s', 'valid_count'})

    def test_excel_export_honors_metadata_and_stat_selection(self):
        try:
            from openpyxl import load_workbook
        except ImportError:
            self.skipTest('openpyxl not installed')

        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.make_config(
                temp_dir,
                csv=False,
                excel=True,
                statistics=True,
                k_units={'m_s': False, 'cm_s': False, 'm_d': True},
                selected_statistics=['median', 'valid_count'],
                include_grain_size_stats=False,
                include_metadata={
                    'sample_info': False,
                    'environmental': True,
                    'export_timestamp': True,
                },
            )

            exported = ExportManager().export(self.datasets, config)

            self.assertEqual(len(exported), 1)
            workbook = load_workbook(exported[0], data_only=True)
            summary_values = [row[0] for row in workbook['Summary'].iter_rows(values_only=True) if row and row[0]]
            stats_rows = list(workbook['Statistics'].iter_rows(values_only=True))

            self.assertNotIn('Sample Name:', summary_values)
            self.assertIn('Temperature:', summary_values)
            self.assertIn('Exported At:', summary_values)
            self.assertIn('Median (m/d):', summary_values)
            self.assertNotIn('Mean (m/d):', summary_values)
            self.assertEqual(stats_rows[0], ('Statistic', 'K (m/d)'))
            self.assertIn(('Median', 12.96), stats_rows)
            self.assertIn(('Valid Count', 3), stats_rows)
            self.assertFalse(any(row and row[0] == 'Mean' for row in stats_rows[1:]))

    def test_plot_export_generates_png_without_live_figure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.make_config(
                temp_dir,
                csv=False,
                png=True,
                plots=True,
                plot_figures=[],
                plot_contexts=[],
            )

            exported = ExportManager().export(self.datasets, config)

            self.assertEqual(len(exported), 1)
            self.assertTrue(exported[0].endswith('_plot.png'))
            with open(exported[0], 'rb') as handle:
                self.assertEqual(handle.read(8), b'\x89PNG\r\n\x1a\n')

    def test_plot_export_generates_vector_formats_without_live_figure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.make_config(
                temp_dir,
                csv=False,
                svg=True,
                pdf_plot=True,
                plots=True,
                plot_figures=[],
                plot_contexts=[],
            )

            exported = ExportManager().export(self.datasets, config)

            self.assertEqual({os.path.splitext(path)[1] for path in exported}, {'.svg', '.pdf'})
            svg_path = next(path for path in exported if path.endswith('.svg'))
            pdf_path = next(path for path in exported if path.endswith('.pdf'))
            with open(svg_path, encoding='utf-8') as handle:
                self.assertIn('<svg', handle.read())
            with open(pdf_path, 'rb') as handle:
                self.assertEqual(handle.read(4), b'%PDF')

    def test_plot_export_writes_selected_single_sample_plot_types(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.make_config(
                temp_dir,
                csv=False,
                png=True,
                plots=True,
                selected_plot_types=[
                    'grain_size_curve',
                    'k_value_bar',
                    'applicability_heatmap',
                ],
            )

            exported = ExportManager().export(self.datasets, config)

            basenames = {os.path.basename(path) for path in exported}
            self.assertEqual(len(exported), 3)
            self.assertTrue(any(name.endswith('_plot.png') for name in basenames))
            self.assertTrue(any(name.endswith('_k_values.png') for name in basenames))
            self.assertTrue(any(name.endswith('_applicability.png') for name in basenames))

    def test_plot_export_writes_selected_collection_plot_types_once(self):
        dataset_b = build_dataset('Sample B')
        datasets = [
            (self.dataset.sample_name, self.dataset, self.results),
            (dataset_b.sample_name, dataset_b, self.results),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.make_config(
                temp_dir,
                csv=False,
                png=True,
                plots=True,
                selected_plot_types=[
                    'distribution_overlay',
                    'k_value_comparison',
                    'statistical_boxplots',
                    'reliability_matrix',
                ],
            )

            exported = ExportManager().export(datasets, config)

            basenames = {os.path.basename(path) for path in exported}
            self.assertEqual(len(exported), 4)
            self.assertTrue(any(name.endswith('_distribution_overlay.png') for name in basenames))
            self.assertTrue(any(name.endswith('_k_value_comparison.png') for name in basenames))
            self.assertTrue(any(name.endswith('_k_value_boxplot.png') for name in basenames))
            self.assertTrue(any(name.endswith('_reliability_matrix.png') for name in basenames))
            self.assertTrue(all(name.startswith('all_datasets_results_') for name in basenames))

    def test_plot_export_uses_shared_renderer_and_plot_options(self):
        calls = []

        def capture_renderer(ax, particle_sizes, percent_passing, **kwargs):
            calls.append(kwargs)
            ax.plot(particle_sizes, percent_passing, label=kwargs.get('sample_name'))

        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.make_config(
                temp_dir,
                csv=False,
                png=True,
                plots=True,
                plot_include_legend=False,
                plot_include_grid=False,
                plot_contexts=[{
                    'style': PROFESSIONAL_STYLE,
                    'show_d_lines': True,
                    'show_markers': True,
                    'show_classification_zones': True,
                }],
            )

            with patch(
                'gui.export_manager.render_grain_size_distribution',
                side_effect=capture_renderer,
            ):
                exported = ExportManager().export(self.datasets, config)

            self.assertEqual(len(exported), 1)
            self.assertEqual(len(calls), 1)
            self.assertFalse(calls[0]['show_legend'])
            self.assertFalse(calls[0]['show_grid'])
            self.assertTrue(calls[0]['show_d_lines'])
            self.assertTrue(calls[0]['show_markers'])
            self.assertTrue(calls[0]['show_classification_zones'])

    def test_plot_export_keeps_live_legend_and_grid_state_when_allowed(self):
        calls = []

        def capture_renderer(ax, particle_sizes, percent_passing, **kwargs):
            calls.append(kwargs)
            ax.plot(particle_sizes, percent_passing, label=kwargs.get('sample_name'))

        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.make_config(
                temp_dir,
                csv=False,
                png=True,
                plots=True,
                plot_contexts=[{
                    'show_legend': False,
                    'show_grid': False,
                }],
            )

            with patch(
                'gui.export_manager.render_grain_size_distribution',
                side_effect=capture_renderer,
            ):
                exported = ExportManager().export(self.datasets, config)

        self.assertEqual(len(exported), 1)
        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0]['show_legend'])
        self.assertFalse(calls[0]['show_grid'])

    def test_plot_export_applies_axis_limits_from_plot_context(self):
        manager = ExportManager()

        figure = manager._build_grain_size_plot_figure(
            self.dataset.sample_name,
            self.dataset,
            self.make_config(output_dir='unused', csv=False),
            {
                'axis_limits': {
                    'xlim': (0.01, 10.0),
                    'ylim': (5.0, 95.0),
                },
            },
        )

        ax = figure.axes[0]
        self.assertAlmostEqual(ax.get_xlim()[0], 0.01)
        self.assertAlmostEqual(ax.get_xlim()[1], 10.0)
        self.assertAlmostEqual(ax.get_ylim()[0], 5.0)
        self.assertAlmostEqual(ax.get_ylim()[1], 95.0)
        figure.clear()

    def test_plot_export_applies_shared_text_options_from_context(self):
        manager = ExportManager()

        figure = manager._build_grain_size_plot_figure(
            self.dataset.sample_name,
            self.dataset,
            self.make_config(output_dir='unused', csv=False),
            {
                'show_title': False,
                'plot_title': 'Custom Title',
                'show_x_label': True,
                'plot_x_label': 'Custom X',
                'show_y_label': False,
                'plot_y_label': 'Custom Y',
            },
        )

        ax = figure.axes[0]
        self.assertEqual(ax.get_title(), '')
        self.assertEqual(ax.get_xlabel(), 'Custom X')
        self.assertEqual(ax.get_ylabel(), '')
        figure.clear()


class TestExportTabConfig(unittest.TestCase):
    def setUp(self):
        self.dataset = build_dataset()
        self.results = build_results()
        self.tab = ExportTab()
        self.tab.update_datasets(
            [(self.dataset.sample_name, self.dataset, self.results)],
            plot_contexts=[{'style': PROFESSIONAL_STYLE, 'show_grid': False}],
        )

    def tearDown(self):
        self.tab.deleteLater()

    def test_plot_content_options_are_written_to_export_config(self):
        self.tab._toggle_content_item('plots', 'include_legend', False)
        self.tab._toggle_content_item('plots', 'include_grid', False)
        self.tab._toggle_content_item('plots', 'k_value_bar', True)

        config = self.tab._build_export_config()

        self.assertFalse(config['plot_include_legend'])
        self.assertFalse(config['plot_include_grid'])
        self.assertEqual(config['selected_plot_types'], ['grain_size_curve', 'k_value_bar'])
        self.assertEqual(config['plot_contexts'][0]['style'], PROFESSIONAL_STYLE)
        self.assertFalse(config['plot_contexts'][0]['show_grid'])

    def test_disabling_grain_size_plot_item_disables_plot_export(self):
        self.tab._toggle_content_item('plots', 'grain_size_curve', False)

        config = self.tab._build_export_config()

        self.assertFalse(config['plots'])
        self.assertFalse(self.tab._plot_exports_enabled())
        self.assertNotIn('plot_contexts', config)

    def test_plot_preview_renders_canvas_and_can_request_dataset_jump(self):
        requested = []
        self.tab.jump_to_dataset_requested.connect(requested.append)

        self.tab.update_preview()
        self.assertIsNotNone(self.tab._plot_preview_table)
        self.assertEqual(self.tab._plot_preview_table.rowCount(), 1)
        self.assertIsNotNone(self.tab._plot_preview_canvas)

        self.tab._open_selected_plot_dataset()

        self.assertEqual(requested, [self.dataset.sample_name])


if __name__ == '__main__':
    unittest.main(verbosity=2)
