"""Shared K-method registry used by GUI, aggregation, reports, and export."""

from __future__ import annotations

from typing import Iterable, Sequence


DEFAULT_METHOD_ORDER: tuple[str, ...] = (
    "Hazen",
    "Hazen_1892",
    "Slichter",
    "Terzaghi",
    "Beyer",
    "Sauerbrei",
    "Kruger",
    "Kozeny-Carman",
    "Zunker",
    "Zamarin",
    "USBR",
    "Barr",
    "Alyamani-Sen",
    "Chapuis",
    "Shepherd",
    "Krumbein-Monk",
)

METHOD_CATEGORY_MAP: dict[str, set[str]] = {
    "hazen_based": {"Hazen", "Hazen_1892"},
    "porosity_dependent": {"Slichter", "Kozeny-Carman", "Zunker", "Zamarin", "Barr"},
    "uniformity_dependent": {"Beyer"},
    "empirical": {
        "USBR",
        "Alyamani-Sen",
        "Chapuis",
        "Shepherd",
        "Terzaghi",
        "Kruger",
        "Krumbein-Monk",
    },
    "temperature_corrected": {"Sauerbrei"},
}


def ordered_methods(
    methods: Iterable[str],
    order: Sequence[str] = DEFAULT_METHOD_ORDER,
) -> list[str]:
    """Return method names in canonical order, with unknown names appended."""
    seen = {str(method) for method in methods}
    rank = {method: idx for idx, method in enumerate(order)}
    return sorted(seen, key=lambda method: (rank.get(method, len(rank)), method.lower()))


def normalize_method_selection(
    selected_methods: Iterable[str] | None,
    *,
    available_methods: Sequence[str] = DEFAULT_METHOD_ORDER,
) -> tuple[str, ...]:
    """Return a non-empty canonical method selection."""
    available_set = set(available_methods)
    if selected_methods is None:
        return tuple(ordered_methods(available_set, available_methods))
    selected = [method for method in selected_methods if method in available_set]
    if not selected:
        return tuple(ordered_methods(available_set, available_methods))
    return tuple(ordered_methods(selected, available_methods))

