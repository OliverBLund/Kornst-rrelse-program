'''Tests for shared import preview services.'''

import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, 'Program')

from import_preview import detect_headers, headers_from_row, load_preview_rows


class TestImportPreview(unittest.TestCase):
    def test_detect_headers_returns_row_without_dialog_instance(self):
        rows = [
            ['Laboratory export', '', ''],
            ['Sieve Size', 'Passing %', ''],
            ['4.75', '100', 'Top fraction'],
        ]

        headers, header_row = detect_headers(rows)

        self.assertEqual(header_row, 1)
        self.assertEqual(headers, ['Sieve Size', 'Passing %', 'Column 3'])

    def test_headers_from_row_matches_widest_source_row(self):
        rows = [
            ['Size', 'Passing'],
            ['4.75', '100', 'note'],
        ]

        self.assertEqual(
            headers_from_row(rows, 0),
            ['Size', 'Passing', 'Column 3'],
        )

    def test_csv_preview_loading_is_limited_to_fifty_rows(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, 'sample.csv')
            with open(path, 'w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(['Size', 'Passing'])
                for index in range(60):
                    writer.writerow([index, 100 - index])

            rows, sheets, resolved_sheet = load_preview_rows(path)

        self.assertEqual(len(rows), 50)
        self.assertEqual(sheets, [])
        self.assertIsNone(resolved_sheet)


if __name__ == '__main__':
    unittest.main(verbosity=2)
