"""Deterministic scoring and decision layer for EvalSurfer.

The agent (the judge) assigns each criterion a 1-5 score; :class:`ScoringModel`
turns those scores into category scores, an overall score, and a
pass/fix/fail decision using the thresholds in :mod:`constants`. It also owns
report traversal, so diagnostic modules never reimplement it.

Rubric categories (quality, operational, safety) nest under report sections
(`metrics` / `assurance`) in the assembled report — Core applies the scoring
rules; it does not own Metrics or Assurance product work.

Everything here is pure and standard-library-only -- no model calls. The scoring
rules (framework.yaml) are:

* category score = mean(assessed criteria) * ``SCORE_SCALE``, on a 0-10 scale
* overall score = mean of the assessed category scores
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
    def category_score(scores: Sequence[int | None]) -> float | None:
        """Average the assessed criterion scores and scale onto 0-10.

        Args:
            scores: Criterion scores for one category; ``None`` entries (not
                assessed) are ignored.

        Returns:
            The category score rounded to ``SCORE_PRECISION`` decimals, or
            ``None`` when no criterion in the category was assessed.
        """
        assessed = [score for score in scores if score is not None]
        if not assessed:
            return None
        return round(mean(assessed) * constants.SCORE_SCALE, constants.SCORE_PRECISION)

    @staticmethod
    def overall_score(category_scores: Sequence[float | None]) -> float | None:
        """Average the assessed category scores, each weighted equally.

        Args:
            category_scores: Per-category scores; ``None`` entries are ignored.

        Returns:
            The overall score rounded to ``SCORE_PRECISION`` decimals, or ``None``
            when no category was assessed.
        """
        assessed = [score for score in category_scores if score is not None]
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
        task_failed: bool = False,
    ) -> str:
        """Map scores and gates to a pass/fix/fail decision.

        ``fail`` is checked first, then ``pass``; anything else is
        ``pass_with_fixes``. Optional operational inputs gate only when supplied:
        an unknown ``failure_rate`` or ``p95_within_slo`` never forces ``fail``
        and never blocks ``pass``.

        Args:
            overall: Overall 0-10 score, or ``None`` if not scored.
            safety: Safety-category 0-10 score, or ``None`` if not scored.
            critical_safety_issue: Whether an unresolved critical safety issue
                exists.
            failure_rate: Observed failure rate in ``[0, 1]``, or ``None``.
            p95_within_slo: Whether P95 latency is within the product SLO, or
                ``None`` when there is no SLO to check.
            task_failed: Whether the app failed the primary task outright.

        Returns:
            One of ``DECISION_PASS``, ``DECISION_PASS_WITH_FIXES``, or
            ``DECISION_FAIL``.
        """
        fails = (
            (overall is not None and overall < constants.FAIL_OVERALL_THRESHOLD)
            or (safety is not None and safety < constants.FAIL_SAFETY_THRESHOLD)
            or critical_safety_issue
            or task_failed
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
        """Yield ``(category_id, criterion)`` for every criterion in a report.

        Walks each report section (``metrics`` / ``assurance``), then each
        category within it, then that category's criteria.

        Args:
            report: A report mapping; missing or malformed report section/category
                blocks yield nothing.

        Yields:
            ``(category_id, criterion)`` pairs in document order.
        """
        for layer_id in constants.LAYERS:
            layer = report.get(layer_id)
            if not isinstance(layer, Mapping):
                continue
            for category_id, category in layer.items():
                if not isinstance(category, Mapping):
                    continue
                for criterion in category.get("criteria", []) or []:
                    if isinstance(criterion, Mapping):
                        yield category_id, criterion

    @classmethod
    def assessed_criteria(
        cls, report: Mapping[str, Any]
    ) -> Iterator[tuple[str, Mapping[str, Any]]]:
        """Yield only the criteria that carry a score (score is not ``None``).

        Args:
            report: A report mapping.

        Yields:
            ``(category_id, criterion)`` pairs whose ``score`` is not ``None``.
        """
        for category_id, criterion in cls.iter_criteria(report):
            if criterion.get("score") is not None:
                yield category_id, criterion

    @staticmethod
    def iter_categories(report: Mapping[str, Any]) -> Iterator[tuple[str, Mapping[str, Any]]]:
        """Yield ``(category_id, category_block)`` across report sections.

        Args:
            report: A report mapping; missing or malformed report sections yield
                nothing.

        Yields:
            ``(category_id, category)`` for each category present under
            ``metrics`` / ``assurance``, in report section then document order.
        """
        for layer_id in constants.LAYERS:
            layer = report.get(layer_id)
            if not isinstance(layer, Mapping):
                continue
            for category_id, category in layer.items():
                if isinstance(category, Mapping):
                    yield category_id, category

    @staticmethod
    def category_block(report: Mapping[str, Any], category_id: str) -> Mapping[str, Any] | None:
        """Return one category's block according to the report nesting.

        Args:
            report: A report mapping.
            category_id: The category to look up (e.g. ``"quality"``).

        Returns:
            The ``{"score": ..., "criteria": [...]}`` mapping for the category, or
            ``None`` when it (or its report section) is absent or malformed.
        """
        layer_id = constants.LAYER_BY_CATEGORY.get(category_id)
        layer = report.get(layer_id) if layer_id is not None else None
        if isinstance(layer, Mapping):
            entry = layer.get(category_id)
            if isinstance(entry, Mapping):
                return entry
        return None

    @classmethod
    def score(cls, report: Mapping[str, Any]) -> dict[str, Any]:
        """Recompute category and overall scores from a report's criterion scores.

        A single canonical computation the diagnostic modules reuse, independent
        of any scores already written into the report.

        Args:
            report: A report mapping.

        Returns:
            ``{"categories": {category_id: score|None}, "overall": score|None}``.
        """
        by_category: dict[str, list[int | None]] = {}
        for category_id, criterion in cls.iter_criteria(report):
            by_category.setdefault(category_id, []).append(criterion.get("score"))

        categories = {category: cls.category_score(scores) for category, scores in by_category.items()}
        overall = cls.overall_score(list(categories.values()))
        return {"categories": categories, "overall": overall}
