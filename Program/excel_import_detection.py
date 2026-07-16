"""Backend helpers for detecting usable data regions in messy Excel sheets."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
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
    sample_name: str = ""
    source_label: str = ""
    candidate_key: str = ""


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
    sorted_curve = sorted(zip(sizes, passing), reverse=True)
    violations = sum(
        1
        for previous, current in zip(sorted_curve, sorted_curve[1:])
        if current[1] > previous[1]
    )
    transitions = max(1, len(sorted_curve) - 1)
    if violations / transitions > 0.5:
        return False
    return True


def extract_candidate_curve(
    rows: Rows,
    candidate: ImportCandidate,
) -> Tuple[List[float], List[float]]:
    """Extract one concrete processed-curve candidate from source rows."""
    if len(candidate.size_cells) != len(candidate.passing_cells):
        raise ValueError("Candidate size and passing ranges have different lengths")

    sizes: List[float] = []
    passing: List[float] = []
    for (size_row, size_col), (passing_row, passing_col) in zip(
        candidate.size_cells,
        candidate.passing_cells,
    ):
        try:
            size = coerce_float(rows[size_row][size_col])
            value = coerce_float(rows[passing_row][passing_col])
        except (IndexError, ValueError):
            continue
        if size > 0 and 0 <= value <= 100:
            sizes.append(size)
            passing.append(value)

    if len(sizes) < 3:
        raise ValueError("Candidate contains fewer than three valid curve rows")
    return sizes, passing


_SIZE_ROLE_KEYWORDS = (
    "particle size",
    "grain size",
    "sieve size",
    "mash size",
    "maskevidde",
    "diameter",
    "size",
    "d mm",
    "d mmm",
    "mesh",
)
_PASSING_ROLE_KEYWORDS = (
    "percent passing",
    "% passing",
    "passing",
    "percent finer",
    "% finer",
    "finer",
    "cumulative percent",
    "cumulative %",
    "kummulativ",
    "on curve",
    "pa kurve",
)
_RETAINED_ROLE_KEYWORDS = ("retained", "retain", "tilbageholdt")
_SAMPLE_ROLE_KEYWORDS = (
    "sample id",
    "sample name",
    "sample no",
    "sample nr",
    "sample",
    "proeve",
    "prove",
)


def _header_role(value: object) -> str:
    text = normalize_text(value)
    if _contains_any(text, _RETAINED_ROLE_KEYWORDS):
        return "retained"
    if _contains_any(text, _PASSING_ROLE_KEYWORDS):
        return "passing"
    if _contains_any(text, _SIZE_ROLE_KEYWORDS):
        return "size"
    if _contains_any(text, _SAMPLE_ROLE_KEYWORDS):
        return "sample"
    return ""


def _column_name(column: int) -> str:
    value = int(column) + 1
    name = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _candidate_pairs(
    rows: Rows,
    *,
    header_row: int,
    size_col: int,
    passing_col: int,
) -> Tuple[Tuple[Cell, Cell], ...]:
    """Return the first numeric curve block below a role-header row."""
    pairs: List[Tuple[Cell, Cell]] = []
    gap = 0
    for row_idx in range(header_row + 1, len(rows)):
        row = rows[row_idx]
        valid = False
        if len(row) > max(size_col, passing_col):
            try:
                size = coerce_float(row[size_col])
                passing = coerce_float(row[passing_col])
                valid = size > 0 and 0 <= passing <= 100
            except ValueError:
                valid = False
        if valid:
            pairs.append(((row_idx, size_col), (row_idx, passing_col)))
            gap = 0
        elif pairs:
            gap += 1
            if gap >= 3:
                break
    return tuple(pairs)


def _sample_label_above(
    rows: Rows,
    *,
    header_row: int,
    columns: Sequence[int],
) -> str:
    """Find a non-role label immediately above a candidate column group."""
    for row_idx in range(header_row - 1, max(-1, header_row - 4), -1):
        for column in columns:
            if row_idx >= len(rows) or column >= len(rows[row_idx]):
                continue
            raw = str(rows[row_idx][column]).strip()
            normalized = normalize_text(raw)
            role = _header_role(raw)
            if not normalized or role in {"size", "passing", "retained"}:
                continue
            if role == "sample" and normalized in _SAMPLE_ROLE_KEYWORDS:
                continue
            if normalized in {"mm", "um", "µm", "μm", "%", "(%)"}:
                continue
            return raw
    return ""


def _sample_label_from_passing_header(value: object) -> str:
    """Extract an explicit sample label from a combined passing-column header."""
    raw = "" if value is None else str(value).strip()
    if not raw:
        return ""
    cleaned = raw
    role_phrases = sorted(
        set(_PASSING_ROLE_KEYWORDS) | {"percent", "procent", "cumulative"},
        key=len,
        reverse=True,
    )
    for phrase in role_phrases:
        cleaned = re.sub(re.escape(phrase), " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[()%\[\]{}]", " ", cleaned)
    cleaned = " ".join(cleaned.split()).strip(" :|/")
    if not cleaned or _header_role(cleaned) in {"passing", "retained", "size"}:
        return ""
    return cleaned


def _finalize_multi_candidates(
    candidates: Sequence[ImportCandidate],
) -> Tuple[ImportCandidate, ...]:
    """Return distinct candidates only when a source clearly contains several."""
    distinct: List[ImportCandidate] = []
    seen = set()
    labels: Dict[str, int] = {}
    for candidate in candidates:
        signature = (candidate.size_cells, candidate.passing_cells)
        if signature in seen:
            continue
        seen.add(signature)
        base_name = candidate.sample_name.strip() or candidate.source_label
        labels[base_name] = labels.get(base_name, 0) + 1
        if labels[base_name] > 1:
            base_name = f"{base_name} ({candidate.source_label})"
        distinct.append(
            ImportCandidate(
                data_type=candidate.data_type,
                selection_method=candidate.selection_method,
                header_row=candidate.header_row,
                sheet_name=candidate.sheet_name,
                label=candidate.label,
                size_cells=candidate.size_cells,
                passing_cells=candidate.passing_cells,
                column_indices=dict(candidate.column_indices),
                sample_name=base_name,
                source_label=candidate.source_label,
                candidate_key=candidate.candidate_key,
            )
        )
    return tuple(distinct) if len(distinct) >= 2 else ()


def _detect_long_table_candidates(
    rows: Rows,
    *,
    sheet_name: Optional[str],
) -> Tuple[ImportCandidate, ...]:
    max_cols = _max_cols(rows)
    for header_row in range(min(16, len(rows))):
        roles: Dict[str, int] = {}
        for column in range(max_cols):
            role = _header_role(rows[header_row][column] if column < len(rows[header_row]) else "")
            if role in {"sample", "size", "passing"} and role not in roles:
                roles[role] = column
        if set(roles) != {"sample", "size", "passing"}:
            continue

        grouped: Dict[str, List[Tuple[Cell, Cell]]] = {}
        display_names: Dict[str, str] = {}
        max_col = max(roles.values())
        for row_idx in range(header_row + 1, len(rows)):
            row = rows[row_idx]
            if len(row) <= max_col:
                continue
            raw_name = str(row[roles["sample"]]).strip()
            if not raw_name:
                continue
            try:
                size = coerce_float(row[roles["size"]])
                passing = coerce_float(row[roles["passing"]])
            except ValueError:
                continue
            if size <= 0 or not 0 <= passing <= 100:
                continue
            key = normalize_text(raw_name)
            display_names.setdefault(key, raw_name)
            grouped.setdefault(key, []).append(
                ((row_idx, roles["size"]), (row_idx, roles["passing"]))
            )

        candidates: List[ImportCandidate] = []
        for key, pairs in grouped.items():
            if not _curve_pair_is_plausible(rows, pairs):
                continue
            source_label = (
                f"{_column_name(roles['sample'])}:"
                f"{_column_name(roles['passing'])}"
            )
            candidates.append(
                ImportCandidate(
                    data_type="processed_curve",
                    selection_method="range",
                    header_row=header_row,
                    sheet_name=sheet_name,
                    label="Detected sample-ID table",
                    size_cells=tuple(pair[0] for pair in pairs),
                    passing_cells=tuple(pair[1] for pair in pairs),
                    sample_name=display_names[key],
                    source_label=source_label,
                    candidate_key=f"long:{key}",
                )
            )
        finalized = _finalize_multi_candidates(candidates)
        if finalized:
            return finalized
    return ()


def _detect_wide_table_candidates(
    rows: Rows,
    *,
    sheet_name: Optional[str],
) -> Tuple[ImportCandidate, ...]:
    max_cols = _max_cols(rows)
    for header_row in range(min(16, len(rows))):
        size_cols = [
            column
            for column in range(max_cols)
            if _header_role(rows[header_row][column] if column < len(rows[header_row]) else "") == "size"
        ]
        passing_cols = [
            column
            for column in range(max_cols)
            if _header_role(rows[header_row][column] if column < len(rows[header_row]) else "") == "passing"
        ]
        if not size_cols or len(passing_cols) < 2:
            continue

        column_pairs: List[Tuple[int, int]] = []
        if len(size_cols) == 1:
            column_pairs = [(size_cols[0], passing_col) for passing_col in passing_cols]
        else:
            unused_passing = set(passing_cols)
            for size_col in size_cols:
                nearby = sorted(
                    (
                        (abs(passing_col - size_col), passing_col)
                        for passing_col in unused_passing
                        if abs(passing_col - size_col) <= 3
                    )
                )
                if nearby:
                    passing_col = nearby[0][1]
                    unused_passing.remove(passing_col)
                    column_pairs.append((size_col, passing_col))

        candidates: List[ImportCandidate] = []
        for size_col, passing_col in column_pairs:
            pairs = _candidate_pairs(
                rows,
                header_row=header_row,
                size_col=size_col,
                passing_col=passing_col,
            )
            if not _curve_pair_is_plausible(rows, pairs):
                continue
            source_label = (
                f"Columns {_column_name(size_col)}:{_column_name(passing_col)}"
            )
            sample_name = _sample_label_above(
                rows,
                header_row=header_row,
                columns=(passing_col, size_col),
            ) or _sample_label_from_passing_header(
                rows[header_row][passing_col]
                if passing_col < len(rows[header_row]) else ""
            ) or source_label
            candidates.append(
                ImportCandidate(
                    data_type="processed_curve",
                    selection_method="range",
                    header_row=header_row,
                    sheet_name=sheet_name,
                    label="Detected multi-sample columns",
                    size_cells=tuple(pair[0] for pair in pairs),
                    passing_cells=tuple(pair[1] for pair in pairs),
                    sample_name=sample_name,
                    source_label=source_label,
                    candidate_key=f"wide:{size_col}:{passing_col}",
                )
            )

        finalized = _finalize_multi_candidates(candidates)
        if finalized:
            return finalized
    return ()


def detect_multi_sample_candidates(
    rows: Rows,
    *,
    sheet_name: Optional[str] = None,
) -> Tuple[ImportCandidate, ...]:
    """Detect explicit multi-sample processed-curve layouts.

    This intentionally excludes incremental, retained, or generically labelled
    percentage columns. Ambiguous scientific semantics remain in manual mapping.
    """
    if not rows:
        return ()
    return (
        _detect_long_table_candidates(rows, sheet_name=sheet_name)
        or _detect_wide_table_candidates(rows, sheet_name=sheet_name)
    )


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
    retained_keywords = ("retained", "retain", "tilbageholdt")

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
                if _contains_any(passing_text, retained_keywords):
                    continue

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
