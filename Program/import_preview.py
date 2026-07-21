'''Shared file-preview loading and header detection.

These helpers are intentionally independent of Qt dialogs so every import
surface interprets the same source rows without borrowing another widget's
instance methods.
'''

from __future__ import annotations

import os
from typing import List, Optional

from delimited_text import DELIMITED_TEXT_EXTENSIONS, read_delimited_rows


HEADER_KEYWORDS = (
    'size',
    'diameter',
    'grain',
    'particle',
    'sieve',
    'mm',
    'd mm',
    'mesh',
    'passing',
    'pass',
    'finer',
    'cumulative',
    'retained',
    '%',
    'procentages',
    'percentages',
    'mass',
    'weight',
    'curve',
)


def is_numeric(value: object) -> bool:
    '''Return whether *value* can be interpreted as a number.'''
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def load_preview_rows(
    file_path: str,
    *,
    sheet_name: Optional[str] = None,
    excel_sheets: Optional[List[str]] = None,
) -> tuple[List[List[str]], List[str], Optional[str]]:
    '''Load raw rows using the shared strategy for import preview surfaces.'''
    file_ext = os.path.splitext(file_path)[1].lower()
    rows: List[List[str]] = []
    discovered_sheets = list(excel_sheets or [])
    resolved_sheet = sheet_name

    if file_ext in DELIMITED_TEXT_EXTENSIONS:
        rows, _delimiter, _encoding = read_delimited_rows(file_path, limit=50)
    elif file_ext in ('.xlsx', '.xls'):
        import pandas as pd

        if not discovered_sheets:
            excel_file = pd.ExcelFile(file_path)
            try:
                discovered_sheets = list(excel_file.sheet_names)
            finally:
                excel_file.close()

        if not resolved_sheet or resolved_sheet not in discovered_sheets:
            resolved_sheet = discovered_sheets[0] if discovered_sheets else None

        frame = pd.read_excel(file_path, sheet_name=resolved_sheet, header=None)
        rows = frame.values.tolist()
        rows = [
            [str(cell) if pd.notna(cell) else '' for cell in row]
            for row in rows
        ]

    if not rows:
        raise ValueError('File contains no preview rows')

    return rows, discovered_sheets, resolved_sheet


def headers_from_row(rows: List[List[str]], row_index: int) -> List[str]:
    '''Build non-empty, width-matched headers from one source row.'''
    max_cols = max((len(row) for row in rows), default=2)
    source_row = rows[row_index] if 0 <= row_index < len(rows) else []
    headers: List[str] = []
    for index in range(max_cols):
        header = str(source_row[index]).strip() if index < len(source_row) else ''
        if not header or header.lower() in ('unnamed', 'nan'):
            header = f'Column {index + 1}'
        headers.append(header)
    return headers


def detect_headers(rows: List[List[str]]) -> tuple[List[str], int]:
    '''Return detected headers and their zero-based source row index.'''
    best_row = 0
    best_score = 0

    for index, row in enumerate(rows[:8]):
        if len(row) < 2:
            continue

        non_empty_cells = [str(cell).strip() for cell in row if str(cell).strip()]
        if len(non_empty_cells) < 2:
            continue

        score = 0
        text_count = sum(1 for cell in non_empty_cells if not is_numeric(cell))
        if text_count >= len(non_empty_cells) * 0.6:
            score += 10

        keyword_count = sum(
            1
            for cell in non_empty_cells
            for keyword in HEADER_KEYWORDS
            if keyword in cell.lower()
        )
        score += keyword_count * 5

        numeric_count = sum(1 for cell in non_empty_cells if is_numeric(cell))
        if numeric_count > len(non_empty_cells) * 0.7:
            score -= 5

        if score > best_score:
            best_score = score
            best_row = index

    return headers_from_row(rows, best_row), best_row
