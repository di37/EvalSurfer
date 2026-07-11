"""The golden-case value object and its validation.

:class:`GoldenCase` freezes one hand-audited evaluation scenario and its expected
outcome; the module-level ``_validate_*`` helpers fail fast on a malformed case so
the oracle stays trustworthy. The harness that replays cases against the
deterministic layer lives in
:mod:`evalsurfer.analysis.diagnostics.golden_set.set`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.planner import Signals


def _validate_score(criterion_id: str, score: Any) -> None:
    """Validate a single criterion score.

    Args:
        criterion_id: The id the score belongs to, used in error messages.
        score: The candidate score; ``None`` (not assessed) is allowed.

    Raises:
        TypeError: If ``score`` is neither ``None`` nor a non-bool ``int``.
        ValueError: If ``score`` falls outside the ``CRITERION_MIN_SCORE`` to
            ``CRITERION_MAX_SCORE`` band.
    """
    if score is None:
        return
    if isinstance(score, bool) or not isinstance(score, int):
        raise TypeError(f"score for {criterion_id!r} must be an int or None")
    if not constants.CRITERION_MIN_SCORE <= score <= constants.CRITERION_MAX_SCORE:
        raise ValueError(
            f"score for {criterion_id!r} must be within "
            f"{constants.CRITERION_MIN_SCORE}-{constants.CRITERION_MAX_SCORE}"
        )


def _validate_category_scores(category_id: str, scores: Any) -> None:
    """Validate one category's ``{criterion_id: score}`` mapping.

    Args:
        category_id: The category the scores belong to.
        scores: The candidate mapping of criterion ids to scores.

    Raises:
        ValueError: If ``category_id`` is not one of ``constants.CATEGORIES``.
        TypeError: If ``scores`` is not a mapping or a criterion id is not a
            string.
    """
    if category_id not in constants.CATEGORIES:
        raise ValueError(
            f"unknown category {category_id!r}; expected one of {constants.CATEGORIES}"
        )
    if not isinstance(scores, Mapping):
        raise TypeError(f"criterion_scores[{category_id!r}] must be a mapping")
    for criterion_id, score in scores.items():
        if not isinstance(criterion_id, str):
            raise TypeError("criterion ids must be strings")
        _validate_score(criterion_id, score)


def _validate_case(case: "GoldenCase") -> None:
    """Fail fast on a malformed case so the oracle stays trustworthy.

    Args:
        case: The case to validate.

    Raises:
        TypeError: If a field has the wrong type.
        ValueError: If a field carries an unknown category/decision or a blank
            name.
    """
    if not isinstance(case.name, str) or not case.name.strip():
        raise ValueError("name must be a non-empty string")
    if not isinstance(case.signals, Signals):
        raise TypeError("signals must be a planner.Signals instance")
    if not isinstance(case.criterion_scores, Mapping):
        raise TypeError("criterion_scores must be a mapping")
    for category_id, scores in case.criterion_scores.items():
        _validate_category_scores(category_id, scores)
    if not isinstance(case.expected_applicable_categories, frozenset):
        raise TypeError("expected_applicable_categories must be a frozenset")
    unknown = case.expected_applicable_categories - set(constants.CATEGORIES)
    if unknown:
        raise ValueError(f"unknown categories in expected: {sorted(unknown)}")
    if case.expected_decision not in constants.DECISIONS:
        raise ValueError(f"expected_decision must be one of {constants.DECISIONS}")


@dataclass(frozen=True)
class GoldenCase:
    """One hand-audited evaluation scenario and its expected outcome.

    ``signals`` is a :class:`planner.Signals`; ``criterion_scores`` maps a category
    id (``constants.CATEGORY_QUALITY`` / ``CATEGORY_SAFETY`` / ``CATEGORY_OPERATIONAL``)
    to a ``{criterion_id: score}`` dict of judge scores in the
    ``CRITERION_MIN_SCORE`` to ``CRITERION_MAX_SCORE`` band (``None`` means not
    assessed). The two ``expected_`` fields are the by-hand oracle: what the
    deterministic layer *should* produce.
    """

    name: str
    signals: Signals
    criterion_scores: Mapping[str, Mapping[str, int | None]]
    expected_applicable_categories: frozenset[str]
    expected_decision: str

    def __post_init__(self) -> None:
        """Validate the case immediately after construction.

        Raises:
            TypeError: If a field has the wrong type.
            ValueError: If a field carries an unknown category/decision or a blank
                name.
        """
        _validate_case(self)
