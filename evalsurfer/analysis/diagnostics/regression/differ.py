"""The version / regression differ service.

:class:`RegressionDiffer` compares a *before* report against an *after* report
and describes what moved: the overall-score delta, any decision change, per-category
deltas, a criterion-by-criterion diff (matched by id within the same category), the
coverage delta, and the ids that regressed or improved. Stateless service,
standard library only, no model calls; it never mutates its inputs.
"""

from __future__ import annotations

from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.scoring import ScoringModel

from evalsurfer.analysis.diagnostics.regression.helpers import (
    _as_mapping,
    _criterion_name,
    _int_score,
    _number,
)
from evalsurfer.analysis.diagnostics.regression.models import CriterionDiff


class RegressionDiffer:
    """Diff two reports (before vs after) into a structured change summary.

    Stateless: every method is static because a diff carries no per-instance
    state. Scores already present in each report are read as-is and never
    recomputed; the class is a cohesive namespace rather than something to
    instantiate.
    """

    @staticmethod
    def _overall_score(report: Mapping[str, Any]) -> float | None:
        """Return the report's overall score, or ``None`` when absent."""
        overall = report.get("overall")
        if isinstance(overall, Mapping):
            return _number(overall.get("score"))
        return None

    @staticmethod
    def _category_score(report: Mapping[str, Any], category: str) -> float | None:
        """Return one category's score from a report, or ``None`` when absent."""
        entry = ScoringModel.category_block(report, category)
        if entry is not None:
            return _number(entry.get("score"))
        return None

    @staticmethod
    def _coverage_score(report: Mapping[str, Any]) -> float | None:
        """Return the report's coverage score, or ``None`` when absent."""
        coverage = report.get("coverage")
        if isinstance(coverage, Mapping):
            return _number(coverage.get("score"))
        return None

    @staticmethod
    def _decision(report: Mapping[str, Any]) -> str | None:
        """Return the report decision, preferring the top-level field.

        Args:
            report: A report mapping.

        Returns:
            The top-level ``decision`` string if present, else the ``overall``
            nested decision, else ``None``.
        """
        decision = report.get("decision")
        if isinstance(decision, str):
            return decision
        overall = report.get("overall")
        if isinstance(overall, Mapping):
            nested = overall.get("decision")
            if isinstance(nested, str):
                return nested
        return None

    @staticmethod
    def _delta(before: float | None, after: float | None, ndigits: int) -> float | None:
        """Return ``after - before`` rounded, or ``None`` if a side is missing.

        Args:
            before: The earlier value, or ``None``.
            after: The later value, or ``None``.
            ndigits: Decimal places to round the difference to.

        Returns:
            The rounded difference, or ``None`` when either side is ``None``.
        """
        if before is None or after is None:
            return None
        return round(after - before, ndigits)

    @staticmethod
    def _criteria_by_id(report: Mapping[str, Any], category: str) -> dict[str, Mapping[str, Any]]:
        """Map criterion id -> criterion for one category, preserving order.

        Args:
            report: A report mapping.
            category: The category whose criteria to collect.

        Returns:
            An id-keyed dict in report order; only the first entry for a repeated
            id is kept.
        """
        out: dict[str, Mapping[str, Any]] = {}
        entry = ScoringModel.category_block(report, category)
        if entry is None:
            return out
        for criterion in entry.get("criteria") or []:
            if isinstance(criterion, Mapping):
                cid = criterion.get("id")
                if isinstance(cid, str) and cid not in out:
                    out[cid] = criterion
        return out

    @staticmethod
    def _ordered_ids(
        before_map: Mapping[str, Any], after_map: Mapping[str, Any]
    ) -> list[str]:
        """Return ids in before-order, then ids new to after appended.

        Args:
            before_map: Id-keyed criteria from the before report.
            after_map: Id-keyed criteria from the after report.

        Returns:
            The combined id ordering (before ids first, then after-only ids).
        """
        ids = list(before_map.keys())
        ids.extend(cid for cid in after_map if cid not in before_map)
        return ids

    @staticmethod
    def _classify(before: int | None, after: int | None) -> str:
        """Label a criterion's movement from ``before`` to ``after`` scores.

        Args:
            before: The before score, or ``None`` when not assessed/absent.
            after: The after score, or ``None`` when not assessed/absent.

        Returns:
            One of the change labels in ``constants.CHANGES``.
        """
        if before is None and after is None:
            return constants.CHANGE_UNCHANGED
        if before is None:
            return constants.CHANGE_ADDED
        if after is None:
            return constants.CHANGE_REMOVED
        if after > before:
            return constants.CHANGE_IMPROVED
        if after < before:
            return constants.CHANGE_REGRESSED
        return constants.CHANGE_UNCHANGED

    @classmethod
    def _diff_criterion(
        cls,
        cid: str,
        before: Mapping[str, Any] | None,
        after: Mapping[str, Any] | None,
    ) -> CriterionDiff:
        """Diff one criterion, matched by id, into a :class:`CriterionDiff`.

        Args:
            cid: The criterion id.
            before: The before criterion mapping, or ``None`` when absent.
            after: The after criterion mapping, or ``None`` when absent.

        Returns:
            The resolved :class:`CriterionDiff`. ``delta`` is ``None`` unless both
            sides carry an int score. ``name`` falls back to the before name, then
            the id.
        """
        before_score = _int_score(before.get("score")) if isinstance(before, Mapping) else None
        after_score = _int_score(after.get("score")) if isinstance(after, Mapping) else None
        name = _criterion_name(after) or _criterion_name(before) or cid
        delta = None if before_score is None or after_score is None else after_score - before_score
        return CriterionDiff(
            id=cid,
            name=name,
            before=before_score,
            after=after_score,
            delta=delta,
            change=cls._classify(before_score, after_score),
        )

    @classmethod
    def _diff_criteria(
        cls, before: Mapping[str, Any], after: Mapping[str, Any]
    ) -> list[CriterionDiff]:
        """Diff criteria category by category, matching entries by id within a category.

        Args:
            before: The before report.
            after: The after report.

        Returns:
            The per-criterion diffs, ordered category by category (over
            ``constants.CATEGORIES``), then before-order, then after-only ids.
        """
        diffs: list[CriterionDiff] = []
        for category in constants.CATEGORIES:
            before_map = cls._criteria_by_id(before, category)
            after_map = cls._criteria_by_id(after, category)
            for cid in cls._ordered_ids(before_map, after_map):
                diffs.append(cls._diff_criterion(cid, before_map.get(cid), after_map.get(cid)))
        return diffs

    @classmethod
    def _category_deltas(
        cls, before: Mapping[str, Any], after: Mapping[str, Any]
    ) -> dict[str, dict[str, float | None]]:
        """Return each category's before/after score and rounded delta.

        Args:
            before: The before report.
            after: The after report.

        Returns:
            An entry per category in ``constants.CATEGORIES`` with ``before``,
            ``after``, and ``delta`` (rounded to ``constants.SCORE_PRECISION``).
        """
        deltas: dict[str, dict[str, float | None]] = {}
        for category in constants.CATEGORIES:
            before_score = cls._category_score(before, category)
            after_score = cls._category_score(after, category)
            deltas[category] = {
                "before": before_score,
                "after": after_score,
                "delta": cls._delta(before_score, after_score, constants.SCORE_PRECISION),
            }
        return deltas

    @classmethod
    def _decision_change(
        cls, before: Mapping[str, Any], after: Mapping[str, Any]
    ) -> dict[str, str | None] | None:
        """Return the decision change, or ``None`` when the decision held.

        Args:
            before: The before report.
            after: The after report.

        Returns:
            ``{"from": ..., "to": ...}`` when the decision moved, else ``None``.
        """
        before_decision = cls._decision(before)
        after_decision = cls._decision(after)
        if before_decision == after_decision:
            return None
        return {"from": before_decision, "to": after_decision}

    @classmethod
    def diff(
        cls, before: Mapping[str, Any], after: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Diff two reports (before vs after) into a structured change summary.

        Reads scores already present in each report; recomputes nothing. Missing
        or ``None`` scores yield ``None`` deltas rather than errors. Inputs are
        never mutated.

        Args:
            before: The earlier report mapping.
            after: The later report mapping.

        Returns:
            A dict with ``overall_delta`` (rounded to
            ``constants.SCORE_PRECISION``), ``decision_change``, ``categories``
            (per-category deltas), ``criteria`` (per-criterion diff dicts),
            ``coverage_delta`` (rounded to ``constants.SHARE_PRECISION``),
            ``regressions``, and ``improvements``.

        Raises:
            TypeError: If ``before`` or ``after`` is not a mapping.
        """
        before = _as_mapping(before, "before")
        after = _as_mapping(after, "after")

        criteria = cls._diff_criteria(before, after)
        regressions = [c.id for c in criteria if c.change == constants.CHANGE_REGRESSED]
        improvements = [c.id for c in criteria if c.change == constants.CHANGE_IMPROVED]

        return {
            "overall_delta": cls._delta(
                cls._overall_score(before),
                cls._overall_score(after),
                constants.SCORE_PRECISION,
            ),
            "decision_change": cls._decision_change(before, after),
            "categories": cls._category_deltas(before, after),
            "criteria": [c.to_dict() for c in criteria],
            "coverage_delta": cls._delta(
                cls._coverage_score(before),
                cls._coverage_score(after),
                constants.SHARE_PRECISION,
            ),
            "regressions": regressions,
            "improvements": improvements,
        }
