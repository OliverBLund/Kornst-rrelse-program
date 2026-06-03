"""Backend helpers for detecting usable data regions in messy Excel sheets."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import unicodedata
from typing import Dict, List, Optional, Sequence, Tuple


Cell = Tuple[int, int]
Rows = Sequence[Sequence[str]]


@dataclass(frozen=True)
class ImportCandidate:
    """A concrete import candidate that the UI can preview, apply, or edit."""

    data_type: str
    selection_method: str
    header_row: int
    sheet_name: Optional[str] = None
    label: str = ""
    size_cells: Tuple[Cell, ...] = ()
    passing_cells: Tuple[Cell, ...] = ()
    column_indices: Dict[str, int] = field(default_factory=dict)


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text.strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.replace("\n", " ").split())


def coerce_float(value: object) -> float:
    if value is None:
        raise ValueError("empty value")
    if isinstance(value, float) and math.isnan(value):
        raise ValueError("nan")
    text = str(value).strip()
    if not text:
        raise ValueError("empty value")
    return float(text.replace(",", "."))


def is_numeric(value: object) -> bool:
    try:
        coerce_float(value)
        return True
    except (TypeError, ValueError):
        return False


def _max_cols(rows: Rows) -> int:
    return max((len(row) for row in rows), default=0)


def _cell(rows: Rows, row: int, col: int) -> str:
    if row < 0 or row >= len(rows):
        return ""
    source_row = rows[row]
    if col < 0 or col >= len(source_row):
        return ""
    return normalize_text(source_row[col])


def _header_text(rows: Rows, row: int, col: int) -> str:
    parts = [_cell(rows, row - 1, col), _cell(rows, row, col), _cell(rows, row + 1, col)]
    return " ".join(part for part in parts if part)


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _numeric_curve_pairs(
    rows: Rows,
    *,
    start_row: int,
    size_col: int,
    passing_col: int,
) -> Tuple[Tuple[Cell, Cell], ...]:
    pairs: List[Tuple[Cell, Cell]] = []
    for row_idx in range(max(0, start_row), len(rows)):
        row = rows[row_idx]
        if len(row) <= max(size_col, passing_col):
            continue
        try:
            size = coerce_float(row[size_col])
            passing = coerce_float(row[passing_col])
        except ValueError:
            continue
        if size <= 0 or passing < 0 or passing > 100:
            continue
        pairs.append(((row_idx, size_col), (row_idx, passing_col)))
    return tuple(pairs)


def _curve_pair_is_plausible(rows: Rows, pairs: Sequence[Tuple[Cell, Cell]]) -> bool:
    if len(pairs) < 3:
        return False

    sizes: List[float] = []
    passing: List[float] = []
    for (size_row, size_col), (passing_row, passing_col) in pairs:
        try:
            sizes.append(coerce_float(rows[size_row][size_col]))
            passing.append(coerce_float(rows[passing_row][passing_col]))
        except (IndexError, ValueError):
            return False

    if min(sizes) <= 0 or max(sizes) / min(sizes) < 1.5:
        return False
    if max(passing) - min(passing) < 1.0:
        return False
    return True


def detect_processed_curve_candidate(
    rows: Rows,
    *,
    sheet_name: Optional[str] = None,
) -> Optional[ImportCandidate]:
    """Detect a size + percent-passing curve in a full sheet snapshot."""
    if not rows:
        return None

    size_keywords = (
        "on curve",
        "pa kurve",
        "size",
        "diameter",
        "grain",
        "particle",
        "sieve",
        "mash",
        "maske",
        "d mm",
        "d mmm",
    )
    strong_size_keywords = ("on curve", "pa kurve")
    passing_keywords = (
        "passing",
        "finer",
        "cumulative",
        "kummulativ",
        "percent",
        "procent",
        "%",
    )

    best: Optional[Tuple[int, int, int, Tuple[Tuple[Cell, Cell], ...], int]] = None
    max_cols = _max_cols(rows)
    search_rows = range(min(16, len(rows)))

    for size_col in range(max_cols):
        for passing_col in range(max_cols):
            if size_col == passing_col or abs(size_col - passing_col) > 3:
                continue

            for header_row in search_rows:
                size_text = _header_text(rows, header_row, size_col)
                passing_text = _header_text(rows, header_row, passing_col)

                header_score = 0
                has_strong_size_header = _contains_any(size_text, strong_size_keywords)
                if has_strong_size_header:
                    header_score += 6
                elif _contains_any(size_text, size_keywords):
                    header_score += 2
                if _contains_any(passing_text, passing_keywords):
                    header_score += 5
                if passing_col == size_col + 1:
                    header_score += 1

                pairs = _numeric_curve_pairs(
                    rows,
                    start_row=header_row + 1,
                    size_col=size_col,
                    passing_col=passing_col,
                )
                if not _curve_pair_is_plausible(rows, pairs):
                    continue
                if not has_strong_size_header:
                    continue

                score = header_score * 20 + len(pairs)
                if best is None or score > best[0]:
                    best = (score, header_row, size_col, pairs, passing_col)

    if best is None:
        return None

    _, header_row, _size_col, pairs, _passing_col = best
    return ImportCandidate(
        data_type="processed_curve",
        selection_method="range",
        header_row=header_row,
        sheet_name=sheet_name,
        label="Detected processed curve",
        size_cells=tuple(size_cell for size_cell, _ in pairs),
        passing_cells=tuple(passing_cell for _, passing_cell in pairs),
    )


def _numeric_raw_rows(
    rows: Rows,
    *,
    start_row: int,
    size_col: int,
    full_col: int,
    empty_col: int,
) -> Tuple[int, ...]:
    valid_rows: List[int] = []
    for row_idx in range(max(0, start_row), len(rows)):
        row = rows[row_idx]
        if len(row) <= max(size_col, full_col, empty_col):
            continue
        try:
            size = coerce_float(row[size_col])
            full = coerce_float(row[full_col])
            empty = coerce_float(row[empty_col])
        except ValueError:
            continue
        if size <= 0 or full < empty:
            continue
        valid_rows.append(row_idx)
    return tuple(valid_rows)


def detect_raw_sieve_candidate(
    rows: Rows,
    *,
    sheet_name: Optional[str] = None,
) -> Optional[ImportCandidate]:
    """Detect raw sieve weighing columns in a full sheet snapshot."""
    if not rows:
        return None

    size_keywords = ("mash size", "maskevidde", "sieve size", "d mm", "d mmm", "mesh")
    full_keywords = (
        "sieve+fraction",
        "sieve + fraction",
        "sieve and fraction",
        "sigte + fraktion",
        "sample",
        "gross",
        "full",
    )
    empty_keywords = ("empty", "tare", "blank", "sigte tom", "tom sieve")

    best: Optional[Tuple[int, int, int, int, int]] = None
    max_cols = _max_cols(rows)
    search_rows = range(min(16, len(rows)))

    for size_col in range(max_cols):
        for full_col in range(max_cols):
            for empty_col in range(max_cols):
                if len({size_col, full_col, empty_col}) != 3:
                    continue
                if max(size_col, full_col, empty_col) - min(size_col, full_col, empty_col) > 5:
                    continue

                for header_row in search_rows:
                    size_text = _header_text(rows, header_row, size_col)
                    full_text = _header_text(rows, header_row, full_col)
                    empty_text = _header_text(rows, header_row, empty_col)

                    header_score = 0
                    if _contains_any(size_text, size_keywords):
                        header_score += 4
                    if _contains_any(full_text, full_keywords):
                        header_score += 4
                    if _contains_any(empty_text, empty_keywords):
                        header_score += 4

                    direct_header_score = 0
                    if _contains_any(_cell(rows, header_row, size_col), size_keywords):
                        direct_header_score += 4
                    if _contains_any(_cell(rows, header_row, full_col), full_keywords):
                        direct_header_score += 4
                    if _contains_any(_cell(rows, header_row, empty_col), empty_keywords):
                        direct_header_score += 4

                    valid_rows = _numeric_raw_rows(
                        rows,
                        start_row=header_row + 1,
                        size_col=size_col,
                        full_col=full_col,
                        empty_col=empty_col,
                    )
                    if len(valid_rows) < 3:
                        continue
                    if header_score < 8:
                        continue

                    score = header_score * 20 + direct_header_score * 5 + len(valid_rows)
                    if best is None or score > best[0]:
                        best = (score, header_row, size_col, full_col, empty_col)

    if best is None:
        return None

    _, header_row, size_col, full_col, empty_col = best
    return ImportCandidate(
        data_type="raw_sieve",
        selection_method="column",
        header_row=header_row,
        sheet_name=sheet_name,
        label="Detected raw sieve weights",
        column_indices={
            "raw_size": size_col,
            "sieve_sample": full_col,
            "empty_sieve": empty_col,
        },
    )


def find_best_import_candidate(
    rows: Rows,
    *,
    sheet_name: Optional[str] = None,
    prefer_data_type: str = "processed_curve",
) -> Optional[ImportCandidate]:
    processed = detect_processed_curve_candidate(rows, sheet_name=sheet_name)
    raw = detect_raw_sieve_candidate(rows, sheet_name=sheet_name)

    if prefer_data_type == "raw_sieve":
        return raw or processed
    return processed or raw
