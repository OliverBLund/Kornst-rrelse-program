"""Coverage for CSV-like TXT imports and their supported delimiters."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, "Program")

from data_loader import DataLoader
from delimited_text import detect_delimiter, read_delimited_rows
from import_preview import load_preview_rows
from load_process_worker import _load_rows


FIXTURES = Path("test_data") / "txt_delimiters"


class TestDelimitedTextSupport(unittest.TestCase):
    def test_txt_delimiters_load_consistently_across_import_paths(self):
        expected = {
            "processed_comma.txt": ",",
            "processed_semicolon.txt": ";",
            "processed_tab.txt": "\t",
            "processed_pipe.txt": "|",
        }

        for filename, expected_delimiter in expected.items():
            with self.subTest(filename=filename):
                path = str(FIXTURES / filename)

                delimiter, confidence = detect_delimiter(path)
                preview_rows, sheets, resolved_sheet = load_preview_rows(path)
                mapped_rows = _load_rows(path)
                dataset = DataLoader().load_file(path)

                self.assertEqual(delimiter, expected_delimiter)
                self.assertGreater(confidence, 0)
                self.assertEqual(preview_rows, mapped_rows)
                self.assertEqual(sheets, [])
                self.assertIsNone(resolved_sheet)
                self.assertEqual(dataset.particle_sizes, [2.0, 1.0, 0.5, 0.25])
                self.assertEqual(dataset.percent_passing, [100.0, 68.0, 24.0, 6.0])

    def test_cp1252_txt_is_decoded_without_changing_table_semantics(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, "cp1252_sample.txt")
            content = (
                "Particle Size (mm);Percent Passing (%);Note\n"
                "2,000;100;Prøve\n"
                "1,000;68;Prøve\n"
                "0,500;24;Prøve\n"
                "0,250;6;Prøve\n"
            )
            with open(path, "wb") as handle:
                handle.write(content.encode("cp1252"))

            rows, delimiter, encoding = read_delimited_rows(path)
            dataset = DataLoader().load_file(path)

        self.assertEqual(delimiter, ";")
        self.assertEqual(encoding, "cp1252")
        self.assertEqual(rows[1][2], "Prøve")
        self.assertEqual(dataset.percent_passing, [100.0, 68.0, 24.0, 6.0])

    def test_free_form_txt_is_rejected_as_non_tabular(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, "notes.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("This is a laboratory note without tabular columns.\n")

            with self.assertRaisesRegex(ValueError, "supported delimiter"):
                read_delimited_rows(path)
            with self.assertRaisesRegex(ValueError, "supported delimiter"):
                DataLoader().load_file(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
