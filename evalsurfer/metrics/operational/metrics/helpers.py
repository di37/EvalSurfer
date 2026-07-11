"""Timestamp, mapping, and coercion utilities for operational metrics.

The :data:`Timestamp` alias plus the module-level helpers that parse and
normalise raw log values: timestamp conversion (:func:`to_datetime`,
:func:`duration_ms`), nested lookup (:func:`get_nested`), and the numeric/boolean
coercions (:func:`coerce_non_negative_int`, :func:`coerce_optional_concurrency`,
:func:`parse_bool`). Everything here is pure and standard-library-only; magic
values are sourced from :mod:`constants`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants

Timestamp = datetime | int | float | str


def to_datetime(value: Timestamp) -> datetime:
    """Convert numeric epoch timestamps or ISO strings to timezone-aware UTC.

    Numeric values are absolute epoch timestamps: those above
    ``constants.EPOCH_MILLISECONDS_THRESHOLD`` are read as milliseconds and
    smaller values as seconds. Sub-second or relative offsets are therefore not
    supported -- a small number like ``500`` is read as 500 epoch *seconds*, not
    a duration.

    Args:
        value: A ``datetime``, an absolute epoch value in seconds or
            milliseconds, or an ISO-8601 string.

    Returns:
        The timezone-aware UTC ``datetime``.

    Raises:
        TypeError: If ``value`` is not a supported timestamp type.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        # Values above the epoch-milliseconds threshold are treated as ms.
        seconds = (
            value / constants.MILLISECONDS_PER_SECOND
            if value > constants.EPOCH_MILLISECONDS_THRESHOLD
            else value
        )
        return datetime.fromtimestamp(seconds, tz=timezone.utc)

    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    raise TypeError(f"Unsupported timestamp type: {type(value).__name__}")


def duration_ms(start: Timestamp, end: Timestamp) -> float:
    """Calculate elapsed milliseconds between two timestamps.

    Args:
        start: The starting timestamp.
        end: The ending timestamp.

    Returns:
        The elapsed time in milliseconds.

    Raises:
        ValueError: If ``end`` is earlier than ``start``.
    """
    elapsed = (
        (to_datetime(end) - to_datetime(start)).total_seconds()
        * constants.MILLISECONDS_PER_SECOND
    )
    if elapsed < 0:
        raise ValueError("end timestamp must be greater than or equal to start")
    return elapsed


def validate_timestamp_order(
    started_at: Timestamp,
    first_token_at: Timestamp | None,
    completed_at: Timestamp | None,
) -> None:
    """Reject a trace whose timestamps are out of chronological order.

    The order must be ``started_at <= first_token_at <= completed_at`` for
    whichever of the three are present. This is a boundary check for log data
    parsed by :meth:`RequestTrace.from_mapping`, so a malformed record fails
    fast here with a clear message instead of raising deep inside
    :meth:`OperationalMetrics.summarize`. Values that cannot be parsed as
    timestamps are left untouched for the caller's own coercion to reject.

    Args:
        started_at: The request start timestamp.
        first_token_at: The first-token timestamp, or ``None`` if absent.
        completed_at: The completion timestamp, or ``None`` if absent.

    Raises:
        ValueError: If a present, parseable timestamp precedes an earlier one.
    """
    try:
        points = [
            (label, to_datetime(value))
            for label, value in (
                ("start", started_at),
                ("first token", first_token_at),
                ("completion", completed_at),
            )
            if value is not None
        ]
    except (TypeError, ValueError):
        # Unparseable timestamps are not ours to validate here; coercion or the
        # calculations surface those. We only enforce ordering.
        return
    for (earlier_label, earlier), (later_label, later) in zip(points, points[1:]):
        if later < earlier:
            raise ValueError(
                f"{later_label} timestamp is before {earlier_label} timestamp"
            )


def get_nested(data: Mapping[str, Any], paths: Sequence[str]) -> Any:
    """Fetch the first present nested value from dot-separated paths.

    Args:
        data: The mapping to search.
        paths: Dot-separated key paths tried in order.

    Returns:
        The first resolved value, or ``None`` if no path is present.
    """
    for path in paths:
        current: Any = data
        for key in path.split("."):
            if not isinstance(current, Mapping) or key not in current:
                break
            current = current[key]
        else:
            return current
    return None


def coerce_non_negative_int(value: Any, field_name: str) -> int:
    """Parse integer-like values and reject invalid or negative values.

    Args:
        value: The raw value (``None``, int, whole-number float, or digit string).
        field_name: Name used in error messages.

    Returns:
        The parsed non-negative integer (``0`` when ``value`` is ``None``).

    Raises:
        ValueError: If the value is a boolean, non-integer, or negative.
        TypeError: If the value has an unsupported type.
    """
    if value is None:
        return 0

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer, not a boolean")

    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        if not isfinite(value) or not value.is_integer():
            raise ValueError(f"{field_name} must be an integer")
        parsed = int(value)
    elif isinstance(value, str):
        normalized = value.strip()
        if not normalized or not normalized.lstrip("-").isdigit():
            raise ValueError(f"{field_name} must be an integer")
        parsed = int(normalized)
    else:
        raise TypeError(f"{field_name} must be an integer")

    if parsed < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return parsed


def coerce_optional_concurrency(value: Any) -> int | None:
    """Parse optional concurrency values from logs.

    Args:
        value: The raw concurrency value, or ``None`` when absent.

    Returns:
        The positive concurrency level, or ``None`` when ``value`` is ``None``.

    Raises:
        ValueError: If the concurrency is not a positive integer.
        TypeError: If the value has an unsupported type.
    """
    if value is None:
        return None

    concurrency = coerce_non_negative_int(value, "concurrency")
    if concurrency == 0:
        raise ValueError("concurrency must be greater than zero")
    return concurrency


def parse_bool(value: Any, field_name: str = "boolean value") -> bool:
    """Parse common boolean values from logs without treating 'false' as true.

    Args:
        value: The raw value (``None``, bool, finite number, or boolean-like
            string such as ``"true"`` or ``"off"``).
        field_name: Name used in error messages.

    Returns:
        The parsed boolean (``False`` when ``value`` is ``None``).

    Raises:
        ValueError: If a numeric value is non-finite or a string is not
            boolean-like.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if not isfinite(value):
            raise ValueError(f"{field_name} must be finite")
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "0", "false", "no", "n", "off"}:
            return False
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        raise ValueError(f"{field_name} must be boolean-like")
    return bool(value)
