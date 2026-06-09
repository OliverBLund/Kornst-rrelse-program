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


if __name__ == '__main__':
    unittest.main(verbosity=2)
