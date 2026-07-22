"""Tests for the shared CSV/XLSX table export dialog."""

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "Program")

from openpyxl import load_workbook

from exporting.table_model import ExportTable
from gui.table_export_dialog import export_table_dialog


class _Dialog:
    result = ("", "")

    @classmethod
    def getSaveFileName(cls, *args, **kwargs):
        return cls.result


class _Messages:
    infos = []
    warnings = []

    @classmethod
    def information(cls, *args):
        cls.infos.append(args)

    @classmethod
    def warning(cls, *args):
        cls.warnings.append(args)


def test_shared_dialog_writes_typed_xlsx_table():
    table = ExportTable.from_rows("K Results", ["Method", "K (m/s)"], [("Hazen", 1.5e-4)])
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "results"
        _Dialog.result = (str(output), "Excel Workbook (*.xlsx)")
        written = export_table_dialog(
            None,
            dialog_title="Export Results",
            default_stem="results",
            table=table,
            success_label="Results",
            file_dialog=_Dialog,
            message_box=_Messages,
        )

        workbook = load_workbook(written, data_only=True)
        worksheet = workbook.active
        assert worksheet["A2"].value == "Hazen"
        assert worksheet["B2"].value == 1.5e-4
        assert worksheet.freeze_panes == "A2"


def test_shared_dialog_writes_csv_when_csv_filter_is_selected():
    table = ExportTable.from_rows("Plot data", ["Size", "Passing"], [(0.5, 42.0)])
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "plot_data"
        _Dialog.result = (str(output), "CSV File (*.csv)")
        written = export_table_dialog(
            None,
            dialog_title="Export Plot Data",
            default_stem="plot_data",
            table=table,
            success_label="Plot data",
            file_dialog=_Dialog,
            message_box=_Messages,
        )

        with open(written, newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        assert rows == [["Size", "Passing"], ["0.5", "42.0"]]
