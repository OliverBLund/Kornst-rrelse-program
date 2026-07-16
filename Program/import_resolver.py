"""Import resolution for grain-size sources.

The resolver keeps UI intent separate from source format detection. Callers say
what the user meant to load; this module decides whether a sheet can be loaded
automatically and returns the mapping state needed to reproduce that decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from excel_import_detection import (
    ImportCandidate,
    detect_multi_sample_candidates,
    find_best_import_candidate,
)


Rows = Sequence[Sequence[str]]
MULTI_SAMPLE_CONFIRMATION_TEXT = "sample candidates require confirmation"


def is_multi_sample_confirmation_message(message: object) -> bool:
    """Return whether a loader message represents candidate review, not failure."""
    return MULTI_SAMPLE_CONFIRMATION_TEXT in str(message or "").strip().lower()


@dataclass(frozen=True)
class ImportResolution:
    """Resolved import plan for one source sheet."""

    action: str
    intent: str
    candidate: Optional[ImportCandidate] = None
    candidates: tuple[ImportCandidate, ...] = ()
    mapping_state: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    message: str = ""

    @property
    def requires_mapping(self) -> bool:
        return self.action == "manual_mapping"


def normalize_import_intent(intent: object) -> str:
    """Normalize user intent to the import data types used by the resolver."""
    value = str(intent or "processed").strip().lower()
    if value in {"raw", "raw_sieve", "raw_sieve_weightings", "raw_sieve_weighings"}:
        return "raw_sieve"
    return "processed_curve"


def _selection_method(candidate: ImportCandidate) -> str:
    if candidate.data_type == "raw_sieve":
        return "column"
    return candidate.selection_method or "column"


def mapping_state_from_candidate(candidate: ImportCandidate, *, intent: object = "processed") -> dict[str, Any]:
    """Build mapper state for an automatically detected import candidate."""
    normalized_intent = normalize_import_intent(intent)
    state: dict[str, Any] = {
        "raw_sieve_mode": candidate.data_type == "raw_sieve",
        "calculated_selection_mode": _selection_method(candidate),
        "header_row": candidate.header_row,
        "current_sheet": candidate.sheet_name,
        "checked_sheets": [candidate.sheet_name] if candidate.sheet_name else [],
        "detected_data_type": candidate.data_type,
        "import_intent": normalized_intent,
        "column_indices": {
            "size": 0,
            "passing": 0,
            "retained": 0,
            "raw_size": 0,
            "empty_sieve": 0,
            "sieve_sample": 0,
        },
    }

    if candidate.data_type == "processed_curve" and candidate.selection_method == "range":
        state["selected_size_range"] = [list(pos) for pos in candidate.size_cells]
        state["selected_percent_range"] = [list(pos) for pos in candidate.passing_cells]
    elif candidate.data_type == "raw_sieve":
        for key, col_index in candidate.column_indices.items():
            state["column_indices"][key] = int(col_index) + 1

    return state


def provenance_from_candidate(candidate: ImportCandidate, *, intent: object = "processed") -> dict[str, Any]:
    """Describe how a source was loaded so it can be shown or restored later."""
    normalized_intent = normalize_import_intent(intent)
    data_type = candidate.data_type
    return {
        "source": "auto_detected",
        "intent": normalized_intent,
        "data_type": data_type,
        "selection_method": _selection_method(candidate),
        "sheet_name": candidate.sheet_name,
        "label": candidate.label,
        "intent_matched": data_type == normalized_intent,
    }


def manual_mapping_provenance(mapping_state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Describe a manually mapped import."""
    mapping_state = mapping_state or {}
    data_type = "raw_sieve" if mapping_state.get("raw_sieve_mode") else "processed_curve"
    selection_method = (
        "column"
        if data_type == "raw_sieve"
        else str(mapping_state.get("calculated_selection_mode") or "column")
    )
    return {
        "source": "manual_mapping",
        "intent": normalize_import_intent(mapping_state.get("import_intent") or data_type),
        "data_type": data_type,
        "selection_method": selection_method,
        "sheet_name": mapping_state.get("current_sheet"),
        "intent_matched": True,
    }


def resolve_excel_import(
    rows: Rows,
    *,
    sheet_name: str | None = None,
    intent: object = "processed",
    allow_multi_sample: bool = False,
) -> ImportResolution:
    """Resolve one Excel sheet into an automatic import plan or mapper fallback."""
    normalized_intent = normalize_import_intent(intent)
    if allow_multi_sample and normalized_intent == "processed_curve":
        candidates = detect_multi_sample_candidates(rows, sheet_name=sheet_name)
        if candidates:
            return ImportResolution(
                action="manual_mapping",
                intent=normalized_intent,
                candidates=candidates,
                message=f"{len(candidates)} sample candidates require confirmation",
            )

    candidate = find_best_import_candidate(
        rows,
        sheet_name=sheet_name,
        prefer_data_type=normalized_intent,
    )
    if candidate is None:
        return ImportResolution(
            action="manual_mapping",
            intent=normalized_intent,
            message="Excel sheet requires manual column mapping",
        )

    mapping_state = mapping_state_from_candidate(candidate, intent=normalized_intent)
    provenance = provenance_from_candidate(candidate, intent=normalized_intent)
    mapping_state["import_provenance"] = dict(provenance)
    return ImportResolution(
        action="auto_load",
        intent=normalized_intent,
        candidate=candidate,
        mapping_state=mapping_state,
        provenance=provenance,
        message=candidate.label,
    )
