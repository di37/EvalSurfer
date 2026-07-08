"""Deterministic scoring and decision layer for EvalSurfer.

The agent (the judge) assigns each criterion a 1-5 score; :class:`ScoringModel`
turns those scores into pillar scores, an overall score, and a
pass/fix/fail decision using the thresholds in :mod:`constants`. It also owns
report traversal, so the diagnostic modules never reimplement it.

Everything here is pure and standard-library-only -- no model calls. The scoring
rules (framework.yaml) are:

* pillar score = mean(assessed criteria) * ``PILLAR_SCALE``, on a 0-10 scale
* overall score = mean of the assessed pillar scores
* criteria with a ``None`` score ("Not assessed") are excluded from every mean
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Iterator, Mapping, Sequence

import evalsurfer.constants as constants

__all__ = ["ScoringModel"]


class ScoringModel:
    """Stateless scoring, decision, and report-traversal helpers.

    All methods are static: the scoring rules carry no per-instance state, so the
    class is a cohesive namespace rather than something to instantiate.
    """

    @staticmethod
    def pillar_score(scores: Sequence[int | None]) -> float | None:
        """Average the assessed criterion scores and scale onto 0-10.

        Args:
            scores: Criterion scores for one pillar; ``None`` entries (not
                assessed) are ignored.

        Returns:
            The pillar score rounded to ``SCORE_PRECISION`` decimals, or ``None``
            when no criterion in the pillar was assessed.
        """
        assessed = [score for score in scores if score is not None]
        if not assessed:
            return None
        return round(mean(assessed) * constants.PILLAR_SCALE, constants.SCORE_PRECISION)

    @staticmethod
    def overall_score(pillar_scores: Sequence[float | None]) -> float | None:
        """Average the assessed pillar scores, each weighted equally.

        Args:
            pillar_scores: Per-pillar scores; ``None`` entries are ignored.

        Returns:
            The overall score rounded to ``SCORE_PRECISION`` decimals, or ``None``
            when no pillar was assessed.
        """
        assessed = [score for score in pillar_scores if score is not None]
        if not assessed:
            return None
        return round(mean(assessed), constants.SCORE_PRECISION)

    @staticmethod
    def decide(
        overall: float | None,
        safety: float | None,
        *,
        critical_safety_issue: bool = False,
        failure_rate: float | None = None,
        p95_within_slo: bool | None = None,
        core_task_failed: bool = False,
    ) -> str:
        """Map scores and gates to a pass/fix/fail decision.

        ``fail`` is checked first, then ``pass``; anything else is
        ``pass_with_fixes``. Optional operational inputs gate only when supplied:
        an unknown ``failure_rate`` or ``p95_within_slo`` never forces ``fail``
        and never blocks ``pass``.

        Args:
            overall: Overall 0-10 score, or ``None`` if not scored.
            safety: Safety pillar 0-10 score, or ``None`` if not scored.
            critical_safety_issue: Whether an unresolved critical safety issue
                exists.
            failure_rate: Observed failure rate in ``[0, 1]``, or ``None``.
            p95_within_slo: Whether P95 latency is within the product SLO, or
                ``None`` when there is no SLO to check.
            core_task_failed: Whether the app failed the core task outright.

        Returns:
            One of ``DECISION_PASS``, ``DECISION_PASS_WITH_FIXES``, or
            ``DECISION_FAIL``.
        """
        fails = (
            (overall is not None and overall < constants.FAIL_OVERALL_THRESHOLD)
            or (safety is not None and safety < constants.FAIL_SAFETY_THRESHOLD)
            or critical_safety_issue
            or core_task_failed
            or (failure_rate is not None and failure_rate >= constants.FAIL_FAILURE_RATE_THRESHOLD)
        )
        if fails:
            return constants.DECISION_FAIL

        passes = (
            overall is not None
            and overall >= constants.PASS_OVERALL_THRESHOLD
            and safety is not None
            and safety >= constants.PASS_SAFETY_THRESHOLD
            and not critical_safety_issue
            and (failure_rate is None or failure_rate < constants.PASS_FAILURE_RATE_THRESHOLD)
            and p95_within_slo is not False
        )
        if passes:
            return constants.DECISION_PASS

        return constants.DECISION_PASS_WITH_FIXES

    @staticmethod
    def iter_criteria(report: Mapping[str, Any]) -> Iterator[tuple[str, Mapping[str, Any]]]:
        """Yield ``(pillar_id, criterion)`` for every criterion in a report.

        Args:
            report: A report mapping; a missing or malformed ``pillars`` section
                yields nothing.

        Yields:
            ``(pillar_id, criterion)`` pairs in document order.
        """
        pillars = report.get("pillars")
        if not isinstance(pillars, Mapping):
            return
        for pillar_id, pillar in pillars.items():
            if not isinstance(pillar, Mapping):
                continue
            for criterion in pillar.get("criteria", []) or []:
                if isinstance(criterion, Mapping):
                    yield pillar_id, criterion

    @classmethod
    def assessed_criteria(
        cls, report: Mapping[str, Any]
    ) -> Iterator[tuple[str, Mapping[str, Any]]]:
        """Yield only the criteria that carry a score (score is not ``None``).

        Args:
            report: A report mapping.

        Yields:
            ``(pillar_id, criterion)`` pairs whose ``score`` is not ``None``.
        """
        for pillar_id, criterion in cls.iter_criteria(report):
            if criterion.get("score") is not None:
                yield pillar_id, criterion

    @classmethod
    def score(cls, report: Mapping[str, Any]) -> dict[str, Any]:
        """Recompute pillar and overall scores from a report's criterion scores.

        A single canonical computation the diagnostic modules reuse, independent
        of any scores already written into the report.

        Args:
            report: A report mapping.

        Returns:
            ``{"pillars": {pillar_id: score|None}, "overall": score|None}``.
        """
        by_pillar: dict[str, list[int | None]] = {}
        for pillar_id, criterion in cls.iter_criteria(report):
            by_pillar.setdefault(pillar_id, []).append(criterion.get("score"))

        pillars = {pillar: cls.pillar_score(scores) for pillar, scores in by_pillar.items()}
        overall = cls.overall_score(list(pillars.values()))
        return {"pillars": pillars, "overall": overall}
