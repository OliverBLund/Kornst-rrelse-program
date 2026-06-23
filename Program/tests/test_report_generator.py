"""
Regression tests for report generator appendix behavior.
"""

import sys
import unittest
import io
import zipfile
from unittest.mock import patch

sys.path.insert(0, 'Program')

from data_loader import GrainSizeData
from k_calculations import CalculationStatus, KCalculationResult
from report_generator import ReportGenerator
from unit_conversions import HydraulicConductivityUnit


def build_dataset(name: str = 'Sample A') -> GrainSizeData:
    return GrainSizeData(
        sample_name=name,
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
        percent_passing=[100.0, 95.0, 82.0, 61.0, 38.0, 14.0, 4.0],
    )


def build_results() -> list[KCalculationResult]:
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
    ]


class TestReportGeneratorAppendices(unittest.TestCase):
    def setUp(self):
        self.generator = ReportGenerator()
        self.dataset = build_dataset()
        self.results = build_results()

    def test_k_value_bar_chart_respects_plot_context_unit(self):
        ms_uri = self.generator._create_k_value_bar_chart(
            self.results, {'display_unit': HydraulicConductivityUnit.M_PER_S}
        )
        md_uri = self.generator._create_k_value_bar_chart(
            self.results, {'display_unit': HydraulicConductivityUnit.M_PER_DAY}
        )

        self.assertTrue(ms_uri.startswith('data:image/png;base64,'))
        self.assertTrue(md_uri.startswith('data:image/png;base64,'))
        # Different display unit -> different rendered chart.
        self.assertNotEqual(ms_uri, md_uri)

    def test_individual_report_includes_k_bar_when_selected(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={'plots': True},
            k_results=self.results,
            selected_plots={'grain_size_curve', 'k_value_bar'},
        )
        self.assertIn('Grain Size Distribution Curve', html)
        self.assertIn('Hydraulic Conductivity by Method', html)

    def test_individual_report_omits_k_bar_when_not_selected(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={'plots': True},
            k_results=self.results,
            selected_plots={'grain_size_curve'},
        )
        self.assertIn('Grain Size Distribution Curve', html)
        self.assertNotIn('Hydraulic Conductivity by Method', html)

    def test_comparison_report_can_omit_reliability_matrix(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35},
        ]
        html = self.generator.generate_comparison_report(
            [self.dataset, sample_b],
            sections={'plots': True},
            sample_details=details,
            selected_plots={'distribution_overlay', 'statistical_boxplots'},
        )
        self.assertIn('Grain Size Distribution Comparison', html)
        self.assertNotIn('Reliability Matrix', html)

    def test_comparison_report_renders_plots_via_shared_spec(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'group_name': 'Layer A', 'temperature': 20.0, 'porosity': 0.35},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'group_name': 'Layer B', 'temperature': 20.0, 'porosity': 0.35},
        ]
        captured = []

        def fake_spec(spec, **kwargs):
            captured.append(spec)
            return 'data:image/png;base64,spec'

        with patch('plot_export.export_comparison_spec', side_effect=fake_spec):
            html = self.generator.generate_comparison_report(
                [self.dataset, sample_b],
                sections={'plots': True, 'k_statistics': False,
                          'results': False, 'interpretation': False},
                sample_details=details,
                selected_plots={'distribution_overlay', 'k_value_comparison'},
            )

        by_type = {spec.current_plot_type: spec for spec in captured}
        # Both comparison plots route through the shared render_comparison spec.
        self.assertIn('distribution', by_type)
        self.assertIn('k-values', by_type)
        # Named groups -> group-aware breakdown, matching the Comparison tab.
        self.assertTrue(by_type['distribution'].use_group_breakdown)
        # K bars use m/s, consistent with the report's K tables/boxplot.
        self.assertEqual(
            by_type['k-values'].display_unit, HydraulicConductivityUnit.M_PER_S
        )
        self.assertIn('Grain Size Distribution Comparison', html)
        self.assertIn('Hydraulic Conductivity by Method', html)

    def test_comparison_report_honors_per_plot_breakdown(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'group_name': 'Layer A', 'temperature': 20.0, 'porosity': 0.35},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'group_name': 'Layer B', 'temperature': 20.0, 'porosity': 0.35},
        ]
        captured = []

        def fake_spec(spec, **kwargs):
            captured.append(spec)
            return 'data:image/png;base64,spec'

        with patch('plot_export.export_comparison_spec', side_effect=fake_spec):
            self.generator.generate_comparison_report(
                [self.dataset, sample_b],
                sections={'plots': True, 'k_statistics': False,
                          'results': False, 'interpretation': False},
                sample_details=details,
                selected_plots={'distribution_overlay', 'k_value_comparison'},
                plot_breakdowns={'distribution_overlay': 'dataset',
                                 'k_value_comparison': 'group'},
            )

        by_type = {spec.current_plot_type: spec for spec in captured}
        # Forced per-dataset distribution flattens the breakdown even though the
        # samples carry named groups; the K bars stay grouped.
        self.assertFalse(by_type['distribution'].use_group_breakdown)
        self.assertTrue(by_type['k-values'].use_group_breakdown)

    def test_comparison_report_can_omit_k_value_bar(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35},
        ]
        html = self.generator.generate_comparison_report(
            [self.dataset, sample_b],
            sections={'plots': True},
            sample_details=details,
            selected_plots={'distribution_overlay'},
        )
        self.assertIn('Grain Size Distribution Comparison', html)
        self.assertNotIn('Hydraulic Conductivity by Method', html)

    def test_percentile_appendix_uses_curve_interpolation(self):
        html = self.generator._create_percentiles_table(self.dataset)

        self.assertIn('>0.069<', html)
        self.assertIn('>0.100<', html)
        self.assertIn('>0.380<', html)
        self.assertIn('>2.000<', html)

    def test_single_visible_appendix_is_labeled_appendix_a(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': True,
                'interpretation': False,
                'percentiles': False,
                'gradation': False,
                'data_quality': False,
            },
        )

        self.assertIn('Appendix A: Raw Measurement Data', html)
        self.assertNotIn('Appendix C: Raw Measurement Data', html)

    def test_alpha_numeric_appendix_labels_are_supported_in_live_report_output(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': True,
                'interpretation': False,
                'percentiles': True,
                'gradation': False,
                'data_quality': False,
            },
            appendix_label_config={
                'scheme': 'alpha_numeric',
                'alpha_numeric_root': 'A',
            },
        )

        self.assertIn('A1: Detailed Percentile Data', html)
        self.assertIn('A2: Raw Measurement Data', html)

    def test_manual_appendix_labels_override_auto_labels(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': True,
                'interpretation': False,
                'percentiles': False,
                'gradation': False,
                'data_quality': False,
            },
            appendix_label_config={
                'mode': 'manual',
                'manual_labels': {
                    'grain_raw_data': 'Supplement S-2',
                },
            },
        )

        self.assertIn('Supplement S-2: Raw Measurement Data', html)
        self.assertNotIn('Appendix A: Raw Measurement Data', html)

    def test_single_appendix_layout_groups_sections_under_one_label(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': True,
                'interpretation': False,
                'percentiles': True,
                'gradation': False,
                'data_quality': False,
            },
            appendix_label_config={
                'layout': 'single',
                'mode': 'manual',
                'single_label': 'Appendix QA',
            },
        )

        self.assertIn('Appendix QA</h3>', html)
        self.assertIn('Detailed Percentile Data</h4>', html)
        self.assertIn('Raw Measurement Data</h4>', html)
        self.assertNotIn('Appendix QA: Raw Measurement Data', html)

    def test_combined_report_propagates_appendix_label_config(self):
        html = self.generator.generate_combined_report(
            self.dataset,
            self.results,
            temperature=20.0,
            porosity=0.35,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': True,
                'interpretation': False,
                'percentiles': False,
                'gradation': False,
                'data_quality': False,
                'k_statistics': False,
            },
            appendix_label_config={
                'mode': 'manual',
                'manual_labels': {
                    'grain_raw_data': 'Client Appendix R1',
                },
            },
        )

        self.assertIn('Client Appendix R1: Raw Measurement Data', html)

    def test_docx_export_generates_editable_document_bytes(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': True,
                'methodology': False,
                'results': True,
                'plots': False,
                'raw_data': False,
                'interpretation': False,
                'percentiles': True,
                'gradation': False,
                'data_quality': False,
            },
        )

        docx_bytes = self.generator.generate_docx_from_html(html)

        self.assertTrue(docx_bytes.startswith(b'PK'))
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
            document_xml = archive.read('word/document.xml').decode('utf-8')

        self.assertIn('Grain Size Analysis Report', document_xml)
        self.assertIn('Detailed Percentile Data', document_xml)

    def test_grain_size_report_plot_uses_live_plot_context(self):
        calls = []

        def capture_renderer(ax, particle_sizes, percent_passing, **kwargs):
            calls.append(kwargs)
            ax.plot(particle_sizes, percent_passing, label=kwargs.get('sample_name'))

        context = {
            'show_d_lines': False,
            'show_markers': False,
            'show_grid': False,
            'show_legend': False,
            'show_title': True,
            'plot_title': 'Custom report plot',
            'show_x_label': False,
            'plot_x_label': 'Custom diameter',
            'show_y_label': True,
            'plot_y_label': 'Custom passing',
        }

        with patch('plot_export.render_grain_size_distribution', side_effect=capture_renderer):
            html = self.generator.generate_grain_size_report(
                self.dataset,
                sections={
                    'cover_page': False,
                    'executive_summary': False,
                    'methodology': False,
                    'results': False,
                    'plots': True,
                    'raw_data': False,
                    'interpretation': False,
                    'percentiles': False,
                    'gradation': False,
                    'data_quality': False,
                },
                plot_context=context,
            )

        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertFalse(call['show_d_lines'])
        self.assertFalse(call['show_markers'])
        self.assertFalse(call['show_grid'])
        self.assertFalse(call['show_legend'])
        self.assertTrue(call['show_title'])
        self.assertEqual(call['title'], 'Custom report plot')
        self.assertFalse(call['show_x_label'])
        self.assertEqual(call['x_label'], 'Custom diameter')
        self.assertTrue(call['show_y_label'])
        self.assertEqual(call['y_label'], 'Custom passing')
        self.assertIn('data:image/png;base64,', html)

    def test_k_value_report_uses_ok_only_geometric_summary(self):
        results = [
            KCalculationResult(
                method_name='Hazen',
                k_value=1.0e-4,
                formula_used='',
                status=CalculationStatus.OK,
                status_message='',
                conditions_met=True,
                temperature=20.0,
                porosity=0.35,
                grain_size_used='D10',
            ),
            KCalculationResult(
                method_name='Kruger',
                k_value=1.0e-2,
                formula_used='',
                status=CalculationStatus.WARNING,
                status_message='outside recommended range',
                conditions_met=False,
                temperature=20.0,
                porosity=0.35,
                grain_size_used='D50',
            ),
            KCalculationResult(
                method_name='USBR',
                k_value=4.0e-4,
                formula_used='',
                status=CalculationStatus.OK,
                status_message='',
                conditions_met=True,
                temperature=20.0,
                porosity=0.35,
                grain_size_used='D20',
            ),
        ]

        html = self.generator.generate_k_value_report(
            self.dataset,
            results,
            temperature=20.0,
            porosity=0.35,
            sections={
                'cover_page': False,
                'executive_summary': True,
                'methodology': False,
                'results': True,
                'plots': False,
                'interpretation': False,
                'k_statistics': False,
            },
        )

        self.assertIn('Geometric Mean K:</strong> 2.00e-04 m/s', html)
        self.assertIn('from 2 OK methods', html)
        self.assertIn('K Arithmetic Mean', html)

    def test_reports_show_effective_porosity_and_source(self):
        self.dataset.calculated_porosity = 0.3123
        self.dataset.current_porosity = 0.5000
        self.dataset.porosity = 0.3500

        grain_html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': False,
                'interpretation': False,
                'percentiles': False,
                'gradation': False,
                'data_quality': False,
            },
        )
        k_html = self.generator.generate_k_value_report(
            self.dataset,
            self.results,
            temperature=20.0,
            porosity=0.5,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'interpretation': False,
                'k_statistics': False,
            },
        )

        self.assertIn('<div class="metadata-value">0.5000</div>', grain_html)
        self.assertIn('Porosity Source:', grain_html)
        self.assertIn('Manual override', grain_html)
        self.assertIn('<div class="metadata-value">0.5000</div>', k_html)
        self.assertIn('Porosity Source:', k_html)

    def test_k_value_report_can_show_method_table_without_results_section(self):
        html = self.generator.generate_k_value_report(
            self.dataset,
            self.results,
            temperature=20.0,
            porosity=0.35,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'interpretation': False,
                'k_statistics': True,
            },
        )

        self.assertIn('K-Value Results', html)
        self.assertIn('K-Value Calculations by Method', html)
        self.assertIn('Hazen', html)
        self.assertNotIn('Results & Analysis', html)

    def test_k_focus_comparison_report_includes_k_method_table_without_results_section(self):
        sample_b = build_dataset('Sample B')
        results_b = [
            KCalculationResult(
                method_name='USBR',
                k_value=2.0e-4,
                formula_used='k = f(d20)',
                status=CalculationStatus.OK,
                status_message='',
                conditions_met=True,
                temperature=20.0,
                porosity=0.35,
                grain_size_used='D20',
            ),
        ]

        html = self.generator.generate_comparison_report(
            [self.dataset, sample_b],
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'interpretation': False,
                'k_statistics': True,
            },
            sample_details=[
                {
                    'label': 'Sample A',
                    'dataset': self.dataset,
                    'k_results': self.results,
                    'temperature': 20.0,
                    'porosity': 0.35,
                },
                {
                    'label': 'Sample B',
                    'dataset': sample_b,
                    'k_results': results_b,
                    'temperature': 20.0,
                    'porosity': 0.35,
                },
            ],
        )

        self.assertIn('K-Value Calculations by Dataset and Method', html)
        self.assertIn('Permeability Classification Summary', html)
        self.assertIn('Sample A', html)
        self.assertIn('Sample B', html)
        self.assertIn('Hazen', html)
        self.assertIn('USBR', html)
        self.assertNotIn('Sample Overview', html)

    def test_comparison_report_uses_grouped_k_scope_for_summary_and_boxplot(self):
        sample_b = build_dataset('Sample B')
        results_b = [
            KCalculationResult(
                method_name='USBR',
                k_value=2.0e-4,
                formula_used='k = f(d20)',
                status=CalculationStatus.OK,
                status_message='',
                conditions_met=True,
                temperature=20.0,
                porosity=0.35,
                grain_size_used='D20',
            ),
        ]

        with patch('plot_export.export_distribution_overlay', return_value='grain-plot'), \
             patch('plot_export.export_reliability_matrix', return_value=''), \
             patch('plot_export.export_k_scope_boxplot', return_value='scope-plot') as boxplot:
            html = self.generator.generate_comparison_report(
                [self.dataset, sample_b],
                sections={
                    'cover_page': False,
                    'executive_summary': False,
                    'methodology': False,
                    'results': True,
                    'plots': True,
                    'interpretation': False,
                    'k_statistics': True,
                },
                sample_details=[
                    {
                        'label': 'Sample A',
                        'dataset': self.dataset,
                        'k_results': self.results,
                        'group_name': 'Layer A',
                        'temperature': 20.0,
                        'porosity': 0.35,
                    },
                    {
                        'label': 'Sample B',
                        'dataset': sample_b,
                        'k_results': results_b,
                        'group_name': 'Layer B',
                        'temperature': 20.0,
                        'porosity': 0.35,
                    },
                ],
            )

        self.assertIn('K-Value Aggregate Summary', html)
        self.assertIn('Layer A', html)
        self.assertIn('Layer B', html)
        self.assertIn('Included K cells', html)
        self.assertIn('scope-plot', html)
        series = boxplot.call_args[0][0]
        self.assertEqual([label for label, _values in series], ['Overall', 'Layer A', 'Layer B'])

    def test_large_grain_parameter_comparison_uses_long_table(self):
        datasets = [build_dataset(f'Sample {idx:02d}') for idx in range(1, 10)]
        labels = [dataset.sample_name for dataset in datasets]

        html = self.generator._create_grain_parameters_comparison_table(datasets, labels)

        self.assertIn('<th>Sample</th>', html)
        self.assertIn('<th>Value</th>', html)
        self.assertIn('D10 (mm) summary', html)
        self.assertNotIn('table-wide', html)

    def test_generated_reports_do_not_emit_literal_page_number_placeholder(self):
        grain_html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': True,
                'methodology': False,
                'results': True,
                'plots': False,
                'raw_data': False,
                'interpretation': False,
                'percentiles': False,
                'gradation': False,
                'data_quality': False,
            },
        )
        comparison_html = self.generator.generate_comparison_report(
            [self.dataset, build_dataset('Sample B')],
            sections={
                'cover_page': False,
                'executive_summary': True,
                'methodology': False,
                'results': True,
                'plots': False,
                'interpretation': False,
                'k_statistics': True,
            },
            sample_details=[
                {
                    'label': 'Sample A',
                    'dataset': self.dataset,
                    'k_results': self.results,
                    'temperature': 20.0,
                    'porosity': 0.35,
                },
                {
                    'label': 'Sample B',
                    'dataset': build_dataset('Sample B'),
                    'k_results': self.results,
                    'temperature': 20.0,
                    'porosity': 0.35,
                },
            ],
        )

        self.assertNotIn('Page #', grain_html)
        self.assertNotIn('Page #', comparison_html)

    def test_report_generation_is_repeatable_on_same_generator(self):
        sections = {
            'cover_page': False,
            'executive_summary': True,
            'methodology': False,
            'results': True,
            'plots': False,
            'interpretation': False,
            'k_statistics': True,
        }

        first = self.generator.generate_k_value_report(
            self.dataset,
            self.results,
            temperature=20.0,
            porosity=0.35,
            sections=sections,
        )
        second = self.generator.generate_k_value_report(
            self.dataset,
            self.results,
            temperature=20.0,
            porosity=0.35,
            sections=sections,
        )

        self.assertIn('Hydraulic Conductivity Analysis Report', first)
        self.assertIn('Hydraulic Conductivity Analysis Report', second)
        self.assertIn('K-Value Calculations by Method', second)


if __name__ == '__main__':
    unittest.main(verbosity=2)
