'''Shared deterministic ordering for human-readable sample and group labels.'''

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, TypeVar


_T = TypeVar('_T')
_DIGIT_RUN = re.compile(r'(\d+)')


def natural_sort_key(value: Any) -> tuple[tuple[int, Any], ...]:
    '''Return a case-insensitive key where digit runs compare numerically.

    Sample 2 therefore sorts before Sample 10. Unicode normalization keeps
    labels copied from spreadsheets deterministic across every output.
    Python's stable sort preserves source order for otherwise equal labels.
    '''

    value_text = unicodedata.normalize('NFKC', str(value or '')).strip()
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in _DIGIT_RUN.split(value_text)
        if part
    )


def natural_sorted(values: Iterable[_T], *, key=lambda value: value) -> list[_T]:
    '''Return values in stable natural order using an optional label key.'''

    return sorted(values, key=lambda value: natural_sort_key(key(value)))
