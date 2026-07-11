"""The calibration oracle value object and its validation.

:class:`CalibrationCase` freezes what a trustworthy judge should conclude about
one target; the module-level ``_validate_*`` helpers fail fast on a malformed
case so the oracle stays trustworthy. The scoring logic that reads a judge report
against a case lives in
:mod:`evalsurfer.analysis.calibration.calibrate.calibrator`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.planner import Signals


def _validate_score_range(criterion_id: Any, bounds: Any) -> None:
    """Validate one ``criterion_id -> (min, max)`` expected-score-range entry.

    Args:
        criterion_id: The mapping key; must be a non-empty string.
        bounds: The mapping value; must be a ``(min, max)`` pair of ints on the
            criterion scale with ``min <= max``.

    Raises:
        TypeError: If ``criterion_id`` is not a non-empty string, or ``bounds``
            is not a 2-tuple of (non-bool) ints.
        ValueError: If a bound falls off the criterion scale or ``min > max``.
    """
    if not isinstance(criterion_id, str) or not criterion_id.strip():
        raise TypeError("expected_score_ranges keys must be non-empty strings")
    if not isinstance(bounds, tuple) or len(bounds) != 2:
        raise TypeError(
            f"expected_score_ranges[{criterion_id!r}] must be a (min, max) tuple"
        )
    low, high = bounds
    for bound in (low, high):
        if isinstance(bound, bool) or not isinstance(bound, int):
            raise TypeError(
                f"expected_score_ranges[{criterion_id!r}] bounds must be ints"
            )
        if not constants.CRITERION_MIN_SCORE <= bound <= constants.CRITERION_MAX_SCORE:
            raise ValueError(
                f"expected_score_ranges[{criterion_id!r}] bounds must be within "
                f"{constants.CRITERION_MIN_SCORE}-{constants.CRITERION_MAX_SCORE}"
            )
    if low > high:
        raise ValueError(
            f"expected_score_ranges[{criterion_id!r}] has min greater than max"
        )


def _validate_case(case: "CalibrationCase") -> None:
    """Fail fast on a malformed case so the calibration oracle stays trustworthy.

    Args:
        case: The case to validate immediately after construction.

    Raises:
        TypeError: If a field has the wrong type.
        ValueError: If a field carries an unknown category, decision, or severity,
            a blank name, or an invalid score range.
    """
    if not isinstance(case.name, str) or not case.name.strip():
        raise ValueError("name must be a non-empty string")
    if not isinstance(case.signals, Signals):
        raise TypeError("signals must be a planner.Signals instance")
    if not isinstance(case.expected_applicable_categories, frozenset):
        raise TypeError("expected_applicable_categories must be a frozenset")
    unknown = case.expected_applicable_categories - set(constants.CATEGORIES)
    if unknown:
        raise ValueError(f"unknown categories in expected: {sorted(unknown)}")
    if not isinstance(case.expected_score_ranges, Mapping):
        raise TypeError("expected_score_ranges must be a mapping")
    for criterion_id, bounds in case.expected_score_ranges.items():
        _validate_score_range(criterion_id, bounds)
    if case.expected_decision not in constants.DECISIONS:
        raise ValueError(f"expected_decision must be one of {constants.DECISIONS}")
    if (
        case.expected_top_issue_severity is not None
        and case.expected_top_issue_severity not in constants.SEVERITIES
    ):
        raise ValueError(
            "expected_top_issue_severity must be None or one of "
            f"{constants.SEVERITIES}"
        )
    if not isinstance(case.expected_safety_escalation, bool):
        raise TypeError("expected_safety_escalation must be a boolean")


@dataclass(frozen=True)
class CalibrationCase:
    """One hand-authored expectation for what a trustworthy judge should conclude.

    ``signals`` is a :class:`planner.Signals` snapshot of the evidence available
    for the target. ``expected_score_ranges`` maps a criterion id to an inclusive
    ``(min, max)`` band the judge's score should fall inside. The remaining
    ``expected_`` fields pin the decision, the severity of the worst reported
    issue (``None`` when no issue is expected), and whether a critical safety
    issue should be escalated. All fields are validated on construction.
    """

    name: str
    signals: Signals
    expected_applicable_categories: frozenset[str]
    expected_score_ranges: Mapping[str, tuple[int, int]]
    expected_decision: str
    expected_top_issue_severity: str | None
    expected_safety_escalation: bool

    def __post_init__(self) -> None:
        """Validate the case immediately after construction.

        Raises:
            TypeError: If a field has the wrong type.
            ValueError: If a field carries an unknown category, decision, or
                severity, a blank name, or an invalid score range.
        """
        _validate_case(self)
