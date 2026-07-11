"""The judge-confidence human-review gate service.

:class:`ReviewGate` reads the per-criterion confidence a judge attached to a
report and decides whether the result should be escalated to a human: a criterion
is flagged when its confidence falls below a configurable threshold, and any
``critical`` top issue also forces a review. The ``FlaggedCriterion`` /
``ReviewRecommendation`` value objects it emits live in
:mod:`evalsurfer.analysis.diagnostics.review_gate.models`. Deterministic and
immutable: it never mutates the report and makes no model calls.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.core.scoring import ScoringModel

from evalsurfer.analysis.diagnostics.review_gate.models import (
    FlaggedCriterion,
    ReviewRecommendation,
)


class ReviewGate:
    """Decide whether an evaluation report should be escalated to a human.

    Configurable: the confidence threshold below which a criterion is flagged is
    instance state, set once in ``__init__``. The evaluation itself is pure and
    standard-library-only -- it never mutates the report and makes no model
    calls.
    """

    def __init__(
        self,
        confidence_threshold: float = constants.DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        """Validate and store the confidence threshold for this gate.

        Args:
            confidence_threshold: The confidence below which a criterion is
                flagged, in ``[CONFIDENCE_MIN, CONFIDENCE_MAX]``. Defaults to
                ``constants.DEFAULT_CONFIDENCE_THRESHOLD``.

        Raises:
            TypeError: If ``confidence_threshold`` is not a real number.
            ValueError: If it is not finite or falls outside the valid range.
        """
        self.confidence_threshold = self._validate_threshold(confidence_threshold)

    @staticmethod
    def _validate_threshold(value: Any) -> float:
        """Reject non-numeric or out-of-range thresholds at the boundary.

        Args:
            value: The raw threshold supplied to the constructor.

        Returns:
            The threshold coerced to ``float``.

        Raises:
            TypeError: If ``value`` is not a real number.
            ValueError: If ``value`` is not finite or is out of range.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("confidence_threshold must be a number")
        if not isfinite(value):
            raise ValueError("confidence_threshold must be finite")
        if not constants.CONFIDENCE_MIN <= value <= constants.CONFIDENCE_MAX:
            raise ValueError(
                "confidence_threshold must be between "
                f"{constants.CONFIDENCE_MIN} and {constants.CONFIDENCE_MAX}"
            )
        return float(value)

    @staticmethod
    def _confidence_value(value: Any) -> float | None:
        """Coerce a raw confidence to a finite float, or ``None`` otherwise.

        Args:
            value: A raw confidence value from a criterion or its evidence.

        Returns:
            The value as a ``float``, or ``None`` when it is missing, a bool, or
            not a finite number.
        """
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)) and isfinite(value):
            return float(value)
        return None

    @classmethod
    def _criterion_confidence(cls, criterion: Mapping[str, Any]) -> float | None:
        """Read confidence from the criterion, then from its evidence mapping.

        Args:
            criterion: A single criterion mapping.

        Returns:
            The direct ``confidence`` when present, else the evidence mapping's
            ``confidence``, else ``None``.
        """
        direct = cls._confidence_value(criterion.get(constants.CONFIDENCE_FIELD))
        if direct is not None:
            return direct
        evidence = criterion.get("evidence")
        if isinstance(evidence, Mapping):
            return cls._confidence_value(evidence.get(constants.CONFIDENCE_FIELD))
        return None

    @staticmethod
    def _criterion_id(criterion: Mapping[str, Any]) -> str | None:
        """Return the criterion's ``id`` when it is a string, else ``None``.

        Args:
            criterion: A single criterion mapping.

        Returns:
            The string ``id``, or ``None`` when absent or non-string.
        """
        cid = criterion.get("id")
        return cid if isinstance(cid, str) else None

    @staticmethod
    def _low_confidence_reason(cid: str | None, confidence: float, threshold: float) -> str:
        """Explain why a criterion was flagged for low confidence.

        Args:
            cid: The criterion id, or ``None`` when unknown.
            confidence: The rounded confidence value.
            threshold: The review threshold in effect.

        Returns:
            A human-readable reason string.
        """
        name = cid if cid else "unknown criterion"
        return (
            f"Criterion '{name}' has confidence "
            f"{confidence:.{constants.SHARE_PRECISION}f}, "
            f"below the review threshold of "
            f"{threshold:.{constants.SHARE_PRECISION}f}."
        )

    @staticmethod
    def _critical_issue_reason(issue: Mapping[str, Any]) -> str:
        """Explain why a critical top issue forces review.

        Args:
            issue: A single top-issue mapping at critical severity.

        Returns:
            A human-readable reason string.
        """
        description = issue.get("description")
        text = (
            description
            if isinstance(description, str) and description.strip()
            else "unspecified critical issue"
        )
        criterion_id = issue.get("criterion_id")
        if isinstance(criterion_id, str) and criterion_id:
            return f"Critical issue on '{criterion_id}' requires human review: {text}"
        return f"Critical issue requires human review: {text}"

    @classmethod
    def _critical_issue_reasons(cls, report: Mapping[str, Any]) -> list[str]:
        """Collect a reason for every top issue at critical severity.

        Args:
            report: A report mapping; a missing or malformed ``top_issues``
                section yields no reasons.

        Returns:
            One reason per ``constants.SEVERITY_CRITICAL`` top issue, in order.
        """
        issues = report.get("top_issues")
        if not isinstance(issues, Sequence) or isinstance(issues, (str, bytes)):
            return []
        return [
            cls._critical_issue_reason(issue)
            for issue in issues
            if isinstance(issue, Mapping)
            and issue.get("severity") == constants.SEVERITY_CRITICAL
        ]

    def evaluate(self, report: Mapping[str, Any]) -> dict[str, Any]:
        """Recommend human review when the judge was unsure or flagged critical risk.

        A criterion is flagged when its confidence (from
        ``criterion["confidence"]`` or ``criterion["evidence"]["confidence"]``
        when evidence is a mapping) is strictly below this gate's
        ``confidence_threshold``. Criteria without a confidence value are
        skipped. Any ``constants.SEVERITY_CRITICAL`` top issue also triggers
        review. The input report is never mutated.

        Args:
            report: The evaluation report to gate.

        Returns:
            ``{"needs_human_review": bool, "reasons": [...],
            "flagged_criteria": [...], "low_confidence_count": int}``.

        Raises:
            TypeError: If ``report`` is not a mapping.
        """
        if not isinstance(report, Mapping):
            raise TypeError("report must be a mapping")
        threshold = self.confidence_threshold

        reasons: list[str] = []
        flagged: list[FlaggedCriterion] = []
        for _category_id, criterion in ScoringModel.iter_criteria(report):
            confidence = self._criterion_confidence(criterion)
            if confidence is None or confidence >= threshold:
                continue
            cid = self._criterion_id(criterion)
            rounded = round(confidence, constants.SHARE_PRECISION)
            flagged.append(FlaggedCriterion(id=cid, confidence=rounded))
            reasons.append(self._low_confidence_reason(cid, rounded, threshold))

        critical_reasons = self._critical_issue_reasons(report)
        reasons.extend(critical_reasons)

        recommendation = ReviewRecommendation(
            needs_human_review=bool(flagged) or bool(critical_reasons),
            reasons=tuple(reasons),
            flagged_criteria=tuple(flagged),
            low_confidence_count=len(flagged),
        )
        return recommendation.to_dict()
