"""Shared CSV/XLSX save dialog for user-visible table exports."""

from __future__ import annotations

import os
import re

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from exporting.table_model import ExportTable, write_csv_table, write_excel_table


def _ensure_extension(path: str, selected_filter: str) -> tuple[str, str]:
    extension = os.path.splitext(path)[1].lower().lstrip(".")
    if extension not in {"xlsx", "csv"}:
        extension = "csv" if "CSV" in selected_filter.upper() else "xlsx"
        path = f"{path}.{extension}"
    return path, extension


def _worksheet_title(name: str) -> str:
    cleaned = re.sub(r"[\\/*?:\[\]]", "_", str(name)).strip()
    return (cleaned or "Data")[:31]


def export_table_dialog(
    parent: QWidget,
    *,
    dialog_title: str,
    default_stem: str,
    table: ExportTable,
    success_label: str,
    file_dialog=QFileDialog,
    message_box=QMessageBox,
) -> str | None:
    """Prompt for XLSX/CSV and write one rectangular table."""
    path, selected_filter = file_dialog.getSaveFileName(
        parent,
        dialog_title,
        f"{default_stem}.xlsx",
        "Excel Workbook (*.xlsx);;CSV File (*.csv)",
    )
    if not path:
        return None

    path, extension = _ensure_extension(path, selected_filter)
    try:
        if extension == "csv":
            write_csv_table(path, table)
        else:
            from openpyxl import Workbook

            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = _worksheet_title(table.name)
            write_excel_table(worksheet, table)
            worksheet.freeze_panes = "A2"
            workbook.save(path)
        message_box.information(
            parent,
            "Export Successful",
            f"{success_label} exported to:\n{path}",
        )
        return path
    except Exception as exc:  # pragma: no cover - user-facing dialog
        message_box.warning(
            parent,
            "Export Failed",
            f"Could not save {success_label.lower()}:\n{exc}",
        )
        return None
