"""Shared parsing for CSV and delimited TXT input files."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


DELIMITED_TEXT_EXTENSIONS = frozenset({".csv", ".txt"})
SUPPORTED_DELIMITERS = (",", ";", "\t", "|")
SUPPORTED_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def detect_text_encoding(file_path: str) -> str:
    """Return the first supported encoding that can decode the source."""
    for encoding in SUPPORTED_ENCODINGS:
        try:
            with open(file_path, "r", encoding=encoding) as handle:
                handle.read(65536)
            return encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode delimited text file: {Path(file_path).name}")


def _numeric(value: object) -> bool:
    text = str(value).strip()
    if not text:
        return False
    try:
        float(text)
        return True
    except ValueError:
        try:
            float(text.replace(",", "."))
            return True
        except ValueError:
            return False


def score_delimiter(sample_lines: Iterable[str], delimiter: str) -> float:
    """Score a delimiter by column consistency and numeric table content."""
    rows = [
        next(csv.reader([line], delimiter=delimiter))
        for line in sample_lines
        if line.strip()
    ]
    if not rows:
        return 0.0

    column_counts = [len(row) for row in rows]
    most_common_count = max(set(column_counts), key=column_counts.count)
    if most_common_count < 2:
        return 0.0

    consistency = column_counts.count(most_common_count) / len(column_counts)
    average_numeric = sum(
        sum(1 for cell in row if _numeric(cell))
        for row in rows
    ) / len(rows)
    numeric_score = min(1.0, average_numeric / 2)
    return consistency * 0.7 + numeric_score * 0.3


def detect_delimiter(file_path: str) -> tuple[str, float]:
    """Detect comma, semicolon, tab, or pipe delimiters."""
    encoding = detect_text_encoding(file_path)
    with open(file_path, "r", encoding=encoding, newline="") as handle:
        sample_lines = [line.rstrip("\r\n") for _, line in zip(range(20), handle)]

    if not any(line.strip() for line in sample_lines):
        raise ValueError("Delimited text file contains no data")

    scores = {
        delimiter: score_delimiter(sample_lines, delimiter)
        for delimiter in SUPPORTED_DELIMITERS
    }
    delimiter = max(SUPPORTED_DELIMITERS, key=scores.get)
    confidence = scores[delimiter]
    if confidence <= 0:
        raise ValueError(
            "Could not determine a supported delimiter. "
            "Use comma, semicolon, tab, or pipe-separated columns."
        )
    return delimiter, confidence


def read_delimited_rows(
    file_path: str,
    *,
    limit: int | None = None,
) -> tuple[list[list[str]], str, str]:
    """Read CSV-like rows and report the detected delimiter and encoding."""
    delimiter, _confidence = detect_delimiter(file_path)
    encoding = detect_text_encoding(file_path)
    rows: list[list[str]] = []
    with open(file_path, "r", encoding=encoding, newline="") as handle:
        for index, row in enumerate(csv.reader(handle, delimiter=delimiter)):
            if limit is not None and index >= limit:
                break
            rows.append(list(row))

    if not rows or not any(any(str(cell).strip() for cell in row) for row in rows):
        raise ValueError("Delimited text file contains no data")
    if max((len(row) for row in rows), default=0) < 2:
        raise ValueError(
            "Delimited text input must contain at least two separated columns"
        )
    return rows, delimiter, encoding
