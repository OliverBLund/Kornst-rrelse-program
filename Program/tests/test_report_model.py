"""
Tests for the shared report document model.
"""

import sys
import unittest

sys.path.insert(0, 'Program')

from report_model import (
    AppendixLabelConfig,
    ReportDocument,
    ReportSection,
)


class TestReportModelAppendixLabels(unittest.TestCase):
    def build_document(self, config: AppendixLabelConfig | None = None) -> ReportDocument:
        document = ReportDocument(
            title='Appendix Test',
            appendix_label_config=config or AppendixLabelConfig(),
        )
        document.add_section(ReportSection('intro', 'Introduction'))
        document.add_section(ReportSection('app-grain', 'Grain Size Summary', kind='appendix'))
        document.add_section(ReportSection('app-k', 'K-Value Summary', kind='appendix'))
        return document

    def test_alpha_labels_follow_visible_appendix_order(self):
        document = self.build_document()

        self.assertEqual(
            document.appendix_label_map(),
            {
                'app-grain': 'Appendix A',
                'app-k': 'Appendix B',
            },
        )

    def test_numeric_labels_are_supported(self):
        document = self.build_document(
            AppendixLabelConfig(scheme='numeric', prefix='Appendix ')
        )

        self.assertEqual(
            document.appendix_label_map(),
            {
                'app-grain': 'Appendix 1',
                'app-k': 'Appendix 2',
            },
        )

    def test_alpha_numeric_labels_are_supported(self):
        document = self.build_document(
            AppendixLabelConfig(scheme='alpha_numeric', alpha_numeric_root='A')
        )

        self.assertEqual(
            document.appendix_label_map(),
            {
                'app-grain': 'A1',
                'app-k': 'A2',
            },
        )

    def test_manual_labels_override_auto_labels(self):
        document = self.build_document(
            AppendixLabelConfig(
                mode='manual',
                scheme='alpha',
                manual_labels={
                    'app-grain': 'Lab Appendix 1',
                    'app-k': 'Supplement S-2',
                },
            )
        )

        self.assertEqual(
            document.appendix_label_map(),
            {
                'app-grain': 'Lab Appendix 1',
                'app-k': 'Supplement S-2',
            },
        )

    def test_hidden_appendices_do_not_consume_visible_labels(self):
        document = self.build_document()
        document.sections[1].include = False

        self.assertEqual(
            document.appendix_label_map(),
            {
                'app-k': 'Appendix A',
            },
        )

    def test_appendix_display_title_uses_resolved_label(self):
        document = self.build_document(
            AppendixLabelConfig(mode='manual', manual_labels={'app-grain': 'A1'})
        )

        self.assertEqual(
            document.appendix_display_title(document.sections[1]),
            'A1: Grain Size Summary',
        )
        self.assertEqual(
            document.appendix_display_title(document.sections[0]),
            'Introduction',
        )

    def test_single_appendix_uses_single_resolved_label(self):
        document = self.build_document(
            AppendixLabelConfig(layout='single', scheme='numeric', prefix='Appendix ')
        )

        self.assertTrue(document.single_appendix_enabled())
        self.assertEqual(document.single_appendix_label(), 'Appendix 1')

    def test_single_appendix_manual_label_is_supported(self):
        document = self.build_document(
            AppendixLabelConfig(layout='single', mode='manual', single_label='Appendix QA')
        )

        self.assertEqual(document.single_appendix_label(), 'Appendix QA')


if __name__ == '__main__':
    unittest.main(verbosity=2)
