"""Coercion helpers for the regression diff.

Small module-level helpers that read scores and names out of two already-produced
reports without recomputing anything: coerce a value to a mapping, a number, or an
int score, and pull a criterion's name. Used by
:mod:`evalsurfer.analysis.diagnostics.regression.differ`.
"""

from __future__ import annotations

from typing import Any, Mapping


def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    """Return ``value`` as a mapping or raise a labelled ``TypeError``.

    Args:
        value: The candidate report.
        label: A human-readable name for ``value`` used in the error message.

    Returns:
        ``value`` unchanged when it is a mapping.

    Raises:
        TypeError: If ``value`` is not a mapping.
    """
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    return value


def _number(value: Any) -> float | None:
    """Coerce a numeric score to ``float``.

    Args:
        value: A candidate score value.

    Returns:
        The value as a ``float``, or ``None`` for missing/non-numeric values
        (booleans are treated as non-numeric).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _int_score(value: Any) -> int | None:
    """Coerce a criterion score to an ``int`` on the criterion scale.

    Args:
        value: A candidate criterion score.

    Returns:
        The value as an ``int``, or ``None`` when it is not an int (booleans are
        treated as not-a-score).
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _criterion_name(criterion: Mapping[str, Any] | None) -> str | None:
    """Return a criterion's ``name`` string if present, else ``None``.

    Args:
        criterion: A criterion mapping, or ``None``.

    Returns:
        The ``name`` value when it is a string, otherwise ``None``.
    """
    if isinstance(criterion, Mapping):
        name = criterion.get("name")
        if isinstance(name, str):
            return name
    return None
