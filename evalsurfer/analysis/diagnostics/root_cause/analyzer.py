"""The root-cause attribution service.

Given a produced report, :class:`RootCauseAnalyzer` attributes its *lost
quality* -- the points each assessed criterion fell short of a perfect
``constants.CRITERION_MAX_SCORE`` -- back to the categories and rubric groups
responsible. Standard library only, no model calls -- a diagnostic layer on top
of the scored report that never mutates its input.
"""

from __future__ import annotations

from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner
from evalsurfer.core.scoring import ScoringModel

from evalsurfer.analysis.diagnostics.root_cause.models import Contribution


class RootCauseAnalyzer:
    """Attribute a report's lost quality across categories and rubric groups.

    Stateless: the criterion index is a class attribute and every method derives
    its result from the report alone, without per-instance state.
    """

    #: id -> Criterion, for canonical category/group lookup.
    _CRITERION_INDEX = {criterion.id: criterion for criterion in EvaluationPlanner.CRITERIA}

    @staticmethod
    def attribute(report: Mapping[str, Any]) -> dict[str, Any]:
        """Attribute a report's lost quality across categories and rubric groups.

        Args:
            report: A report mapping; a missing or malformed ``categories`` section
                simply contributes nothing.

        Returns:
            ``total_lost`` (sum of ``CRITERION_MAX_SCORE - score`` over assessed
            criteria), ``by_category`` and ``by_group`` lists of
            ``{label, lost, share}`` sorted by lost points descending then label
            ascending, and ``top_contributor`` -- the category with the most lost
            points, or ``None`` when nothing was lost. The input is never
            mutated.

        Raises:
            TypeError: If ``report`` is not a mapping.
            ValueError: If a criterion score is not an integer within
                ``[CRITERION_MIN_SCORE, CRITERION_MAX_SCORE]``.
        """
        if not isinstance(report, Mapping):
            raise TypeError("report must be a mapping")

        category_totals: dict[str, int] = {}
        group_totals: dict[str, int] = {}
        total_lost = 0

        for report_category, criterion in ScoringModel.iter_criteria(report):
            criterion_id = criterion.get("id")
            lost = RootCauseAnalyzer._lost_points(criterion_id, criterion.get("score"))
            if lost is None:
                continue
            category, group = RootCauseAnalyzer._category_and_group(criterion_id, report_category)
            category_totals[category] = category_totals.get(category, 0) + lost
            group_totals[group] = group_totals.get(group, 0) + lost
            total_lost += lost

        by_category = RootCauseAnalyzer._rank(category_totals, total_lost, "category")
        by_group = RootCauseAnalyzer._rank(group_totals, total_lost, "group")
        top_contributor = by_category[0]["category"] if by_category else None

        return {
            "total_lost": total_lost,
            "by_category": by_category,
            "by_group": by_group,
            "top_contributor": top_contributor,
        }

    @staticmethod
    def _share(lost: int, total_lost: int) -> float:
        """Fraction of ``total_lost`` that one bucket accounts for.

        Args:
            lost: Lost points in one bucket.
            total_lost: Total lost points across all buckets.

        Returns:
            ``lost / total_lost`` rounded to ``SHARE_PRECISION`` decimals, or
            ``0.0`` when no points were lost.
        """
        if total_lost <= 0:
            return 0.0
        return round(lost / total_lost, constants.SHARE_PRECISION)

    @staticmethod
    def _lost_points(criterion_id: Any, score: Any) -> int | None:
        """Lost points for one criterion, or ``None`` when it was not assessed.

        Args:
            criterion_id: The criterion id, used only to enrich error messages.
            score: The recorded score; ``None`` means "not assessed".

        Returns:
            ``CRITERION_MAX_SCORE - score`` for an assessed criterion, or
            ``None`` when ``score`` is ``None``.

        Raises:
            ValueError: If ``score`` is not an integer within
                ``[CRITERION_MIN_SCORE, CRITERION_MAX_SCORE]``.
        """
        if score is None:
            return None
        suffix = f" for criterion {criterion_id!r}" if criterion_id else ""
        bounds = f"{constants.CRITERION_MIN_SCORE}-{constants.CRITERION_MAX_SCORE}"
        if isinstance(score, bool) or not isinstance(score, int):
            raise ValueError(f"criterion score must be an integer {bounds}, got {score!r}{suffix}")
        if not constants.CRITERION_MIN_SCORE <= score <= constants.CRITERION_MAX_SCORE:
            raise ValueError(f"criterion score must be within {bounds}, got {score}{suffix}")
        return constants.CRITERION_MAX_SCORE - score

    @staticmethod
    def _category_and_group(criterion_id: Any, report_category: str) -> tuple[str, str]:
        """Resolve the category and group labels for a criterion id.

        Known ids use their canonical category/group from
        :data:`planner.EvaluationPlanner.CRITERIA` (the category name stands in as
        the group for safety/operational criteria). Unknown or missing ids fall
        back to the report's own category key so no lost points are silently
        dropped.

        Args:
            criterion_id: The criterion id from the report.
            report_category: The category the report filed the criterion under.

        Returns:
            The ``(category, group)`` labels for the criterion.
        """
        criterion = (
            RootCauseAnalyzer._CRITERION_INDEX.get(criterion_id)
            if isinstance(criterion_id, str)
            else None
        )
        if criterion is not None:
            return criterion.category, criterion.group or criterion.category
        return report_category, report_category

    @staticmethod
    def _rank(totals: Mapping[str, int], total_lost: int, key: str) -> list[dict[str, Any]]:
        """Build contribution dicts for lost buckets, ranked most-lost first.

        Args:
            totals: ``label -> lost points`` for one bucketing (category or group).
            total_lost: Total lost points, used to compute each bucket's share.
            key: The label field name, either ``"category"`` or ``"group"``.

        Returns:
            ``{key, "lost", "share"}`` dicts for buckets that lost points, sorted
            by lost descending then label ascending.
        """
        contributions = [
            Contribution(label=label, lost=lost, share=RootCauseAnalyzer._share(lost, total_lost))
            for label, lost in totals.items()
            if lost > 0
        ]
        contributions.sort(key=lambda contribution: (-contribution.lost, contribution.label))
        return [contribution.as_dict(key) for contribution in contributions]
