"""Validation and coercion helpers for the golden dataset case.

The module-level, fail-fast validators that :class:`DatasetCase` uses to check
its content at construction: input/text validation
(:func:`_validate_input`, :func:`_validate_optional_text`), coverage-tag and
gold-score coercion (:func:`_validate_tags`, :func:`_coerce_gold_score`), the
boolean flag check (:func:`_validate_bool`), and stable-id derivation
(:func:`_resolve_id`). Magic values come from :mod:`evalsurfer.constants`.
"""

from __future__ import annotations

from math import isfinite
from typing import Any

import evalsurfer.constants as constants


def _validate_input(value: Any) -> str:
    """Validate that a case input is a non-empty string.

    Args:
        value: The candidate input.

    Returns:
        The validated input string, unchanged.

    Raises:
        ValueError: If the value is not a string or is blank.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("case input must be a non-empty string")
    return value


def _validate_optional_text(value: Any, field_name: str) -> str | None:
    """Validate an optional string field.

    Args:
        value: The candidate value, or ``None``.
        field_name: Name used in error messages.

    Returns:
        The string value, or ``None``.

    Raises:
        TypeError: If the value is neither a string nor ``None``.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    return value


def _validate_tags(tags: Any) -> frozenset[str]:
    """Validate coverage tags against the allowed vocabulary.

    Args:
        tags: An iterable of tag strings drawn from
            :data:`~evalsurfer.constants.COVERAGE_TAGS`.

    Returns:
        The validated tags as a frozenset.

    Raises:
        TypeError: If ``tags`` is a string/bytes or not iterable, or a tag is
            not a string.
        ValueError: If a tag is not a known coverage tag.
    """
    if isinstance(tags, (str, bytes)):
        raise TypeError("tags must be an iterable of tags, not a single string")
    try:
        candidates = list(tags)
    except TypeError as exc:
        raise TypeError("tags must be an iterable of tags") from exc
    result: set[str] = set()
    for tag in candidates:
        if not isinstance(tag, str):
            raise TypeError("each tag must be a string")
        if tag not in constants.COVERAGE_TAGS:
            raise ValueError(
                f"unknown coverage tag {tag!r}; allowed: {constants.COVERAGE_TAGS}"
            )
        result.add(tag)
    return frozenset(result)


def _coerce_gold_score(value: Any) -> float | None:
    """Validate and normalise an optional gold score.

    A gold score is a reference score on the criterion scale, so it must fall in
    ``[CRITERION_MIN_SCORE, CRITERION_MAX_SCORE]``. Integers are normalised to
    floats so ``3`` and ``3.0`` hash identically.

    Args:
        value: ``None`` or a finite, non-boolean number.

    Returns:
        The score as a float, or ``None``.

    Raises:
        TypeError: If the value is neither a number nor ``None``.
        ValueError: If the value is a boolean, non-finite, or out of range.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("gold_score must be a number, not a boolean")
    if not isinstance(value, (int, float)):
        raise TypeError("gold_score must be a number or None")
    score = float(value)
    if not isfinite(score):
        raise ValueError("gold_score must be a finite number")
    if not constants.CRITERION_MIN_SCORE <= score <= constants.CRITERION_MAX_SCORE:
        raise ValueError(
            "gold_score must be between "
            f"{constants.CRITERION_MIN_SCORE} and {constants.CRITERION_MAX_SCORE}"
        )
    return score


def _validate_bool(value: Any, field_name: str) -> bool:
    """Validate a strictly boolean flag.

    Args:
        value: The candidate flag.
        field_name: Name used in error messages.

    Returns:
        The validated boolean.

    Raises:
        TypeError: If the value is not a ``bool``.
    """
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean")
    return value


def _resolve_id(id_value: Any, digest: str) -> str:
    """Return the provided id, or derive a stable one from the content digest.

    Args:
        id_value: An explicit id, or ``None`` to derive one.
        digest: The content hash a derived id is based on.

    Returns:
        The case id: the explicit id when given, else
        ``"<DATASET_CASE_ID_PREFIX><first N hex chars of the digest>"``.

    Raises:
        ValueError: If an explicit id is given but is not a non-empty string.
    """
    if id_value is None:
        prefix = constants.DATASET_CASE_ID_PREFIX
        return f"{prefix}{digest[:constants.DATASET_ID_HASH_LENGTH]}"
    if not isinstance(id_value, str) or not id_value.strip():
        raise ValueError("id must be a non-empty string when provided")
    return id_value
