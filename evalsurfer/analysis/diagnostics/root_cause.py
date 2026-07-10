"""Root-cause attribution for EvalSurfer reports.

Given a produced report, :class:`RootCauseAnalyzer` attributes its *lost
quality* -- the points each assessed criterion fell short of a perfect
``constants.CRITERION_MAX_SCORE`` -- back to the pillars and rubric groups
responsible. This turns a flat set of criterion scores into a ranked diagnosis
of where quality was lost, so a reviewer can see the biggest contributors at a
glance.

Lost points for one assessed criterion are ``CRITERION_MAX_SCORE - score`` (0
for a perfect score, up to ``CRITERION_MAX_SCORE - CRITERION_MIN_SCORE`` for the
lowest). Not-assessed criteria (``score`` is ``None``) are ignored. Each
criterion is mapped to its canonical pillar and rubric group via
:data:`planner.EvaluationPlanner.CRITERIA`; safety and operational criteria have
no subgroup, so the pillar name doubles as the group label. Unknown or missing
ids fall back to the report's own pillar key so no lost points are dropped.

Standard library only, no model calls -- a diagnostic layer on top of the
scored report that never mutates its input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner
from evalsurfer.core.scoring import ScoringModel

__all__ = [
    "Contribution",
    "RootCauseAnalyzer",
]


@dataclass(frozen=True)
class Contribution:
    """Lost points attributed to one pillar or rubric group."""

    label: str
    lost: int
    share: float

    def as_dict(self, key: str) -> dict[str, Any]:
        """Render the contribution as a plain dict keyed by ``key``.

        Args:
            key: The label field name, either ``"pillar"`` or ``"group"``.

        Returns:
            ``{key: label, "lost": lost, "share": share}``.
        """
        return {key: self.label, "lost": self.lost, "share": self.share}


class RootCauseAnalyzer:
    """Attribute a report's lost quality across pillars and rubric groups.

    Stateless: the criterion index is a class attribute and every method derives
    its result from the report alone, without per-instance state.
    """

    #: id -> Criterion, for canonical pillar/group lookup.
    _CRITERION_INDEX = {criterion.id: criterion for criterion in EvaluationPlanner.CRITERIA}

    @staticmethod
    def attribute(report: Mapping[str, Any]) -> dict[str, Any]:
        """Attribute a report's lost quality across pillars and rubric groups.

        Args:
            report: A report mapping; a missing or malformed ``pillars`` section
                simply contributes nothing.

        Returns:
            ``total_lost`` (sum of ``CRITERION_MAX_SCORE - score`` over assessed
            criteria), ``by_pillar`` and ``by_group`` lists of
            ``{label, lost, share}`` sorted by lost points descending then label
            ascending, and ``top_contributor`` -- the pillar with the most lost
            points, or ``None`` when nothing was lost. The input is never
            mutated.

        Raises:
            TypeError: If ``report`` is not a mapping.
            ValueError: If a criterion score is not an integer within
                ``[CRITERION_MIN_SCORE, CRITERION_MAX_SCORE]``.
        """
        if not isinstance(report, Mapping):
            raise TypeError("report must be a mapping")

        pillar_totals: dict[str, int] = {}
        group_totals: dict[str, int] = {}
        total_lost = 0

        for report_pillar, criterion in ScoringModel.iter_criteria(report):
            criterion_id = criterion.get("id")
            lost = RootCauseAnalyzer._lost_points(criterion_id, criterion.get("score"))
            if lost is None:
                continue
            pillar, group = RootCauseAnalyzer._pillar_and_group(criterion_id, report_pillar)
            pillar_totals[pillar] = pillar_totals.get(pillar, 0) + lost
            group_totals[group] = group_totals.get(group, 0) + lost
            total_lost += lost

        by_pillar = RootCauseAnalyzer._rank(pillar_totals, total_lost, "pillar")
        by_group = RootCauseAnalyzer._rank(group_totals, total_lost, "group")
        top_contributor = by_pillar[0]["pillar"] if by_pillar else None

        return {
            "total_lost": total_lost,
            "by_pillar": by_pillar,
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
    def _pillar_and_group(criterion_id: Any, report_pillar: str) -> tuple[str, str]:
        """Resolve the pillar and group labels for a criterion id.

        Known ids use their canonical pillar/group from
        :data:`planner.EvaluationPlanner.CRITERIA` (the pillar name stands in as
        the group for safety/operational criteria). Unknown or missing ids fall
        back to the report's own pillar key so no lost points are silently
        dropped.

        Args:
            criterion_id: The criterion id from the report.
            report_pillar: The pillar the report filed the criterion under.

        Returns:
            The ``(pillar, group)`` labels for the criterion.
        """
        criterion = (
            RootCauseAnalyzer._CRITERION_INDEX.get(criterion_id)
            if isinstance(criterion_id, str)
            else None
        )
        if criterion is not None:
            return criterion.pillar, criterion.group or criterion.pillar
        return report_pillar, report_pillar

    @staticmethod
    def _rank(totals: Mapping[str, int], total_lost: int, key: str) -> list[dict[str, Any]]:
        """Build contribution dicts for lost buckets, ranked most-lost first.

        Args:
            totals: ``label -> lost points`` for one bucketing (pillar or group).
            total_lost: Total lost points, used to compute each bucket's share.
            key: The label field name, either ``"pillar"`` or ``"group"``.

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
