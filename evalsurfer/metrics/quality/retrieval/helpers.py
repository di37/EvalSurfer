"""Module-level helpers for the retrieval-quality metrics.

Small pure validators shared by the calculations and the value objects:
sequence coercion (:func:`_as_sequence`) and rank-cutoff validation
(:func:`_validate_k`).
"""

from __future__ import annotations

from typing import Any, Sequence


def _as_sequence(value: Any, field_name: str) -> list[Any]:
    """Return ``value`` as a list, rejecting strings/bytes and non-sequences.

    Args:
        value: The value that should be an ordered, non-string sequence.
        field_name: Name used in error messages.

    Returns:
        The value as a list.

    Raises:
        TypeError: If ``value`` is a string, bytes, or not a sequence.
    """
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a list, not {type(value).__name__}")
    return list(value)


def _validate_k(k: Any) -> None:
    """Validate an optional rank cutoff ``k``.

    Args:
        k: ``None`` (use the whole list) or a positive integer.

    Raises:
        ValueError: If ``k`` is a boolean, non-integer, or not positive.
    """
    if k is None:
        return
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be None or a positive integer")
