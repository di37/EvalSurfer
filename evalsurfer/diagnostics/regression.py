"""Version / regression diff for EvalSurfer reports.

Compare a *before* report against an *after* report and describe what moved:
:class:`RegressionDiffer` reports the overall-score delta, any decision change,
per-pillar score deltas, a criterion-by-criterion diff (matched by id within the
same pillar), the coverage delta, and the ids that regressed or improved.

This is a diagnostic layer over two already-produced reports. It reads the
scores that are present in each report rather than recomputing them, tolerates
any optional key being absent, and never mutates its inputs. Stateless service,
standard library only, no model calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import evalsurfer.constants as constants

__all__ = [
    "CriterionDiff",
    "RegressionDiffer",
]


@dataclass(frozen=True)
class CriterionDiff:
    """How one criterion moved, matched by id within a single pillar."""

    id: str
    name: str
    before: int | None
    after: int | None
    delta: int | None
    change: str

    def to_dict(self) -> dict[str, Any]:
        """Render the criterion diff as a JSON-ready dict.

        Returns:
            A dict with ``id``, ``name``, ``before``, ``after``, ``delta``, and
            ``change`` keys.
        """
        return {
            "id": self.id,
            "name": self.name,
            "before": self.before,
            "after": self.after,
            "delta": self.delta,
            "change": self.change,
        }


def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    """Return ``value`` as a mapping or raise a labelled ``TypeError``.

    Args:
        value: The candidate report.
        label: A human-readable name for ``value`` used in the error message.

    Returns:
        ``value`` unchanged when it is a mapping.

    Raises:
        TypeError: If ``value`` is not a mapping.
    """
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    return value


def _number(value: Any) -> float | None:
    """Coerce a numeric score to ``float``.

    Args:
        value: A candidate score value.

    Returns:
        The value as a ``float``, or ``None`` for missing/non-numeric values
        (booleans are treated as non-numeric).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _int_score(value: Any) -> int | None:
    """Coerce a criterion score to an ``int`` on the criterion scale.

    Args:
        value: A candidate criterion score.

    Returns:
        The value as an ``int``, or ``None`` when it is not an int (booleans are
        treated as not-a-score).
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _criterion_name(criterion: Mapping[str, Any] | None) -> str | None:
    """Return a criterion's ``name`` string if present, else ``None``.

    Args:
        criterion: A criterion mapping, or ``None``.

    Returns:
        The ``name`` value when it is a string, otherwise ``None``.
    """
    if isinstance(criterion, Mapping):
        name = criterion.get("name")
        if isinstance(name, str):
            return name
    return None


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
    def _pillar_score(report: Mapping[str, Any], pillar: str) -> float | None:
        """Return one pillar's score from a report, or ``None`` when absent."""
        pillars = report.get("pillars")
        if isinstance(pillars, Mapping):
            entry = pillars.get(pillar)
            if isinstance(entry, Mapping):
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
    def _criteria_by_id(report: Mapping[str, Any], pillar: str) -> dict[str, Mapping[str, Any]]:
        """Map criterion id -> criterion for one pillar, preserving order.

        Args:
            report: A report mapping.
            pillar: The pillar whose criteria to collect.

        Returns:
            An id-keyed dict in report order; only the first entry for a repeated
            id is kept.
        """
        out: dict[str, Mapping[str, Any]] = {}
        pillars = report.get("pillars")
        if not isinstance(pillars, Mapping):
            return out
        entry = pillars.get(pillar)
        if not isinstance(entry, Mapping):
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
        """Diff criteria pillar by pillar, matching entries by id within a pillar.

        Args:
            before: The before report.
            after: The after report.

        Returns:
            The per-criterion diffs, ordered pillar by pillar (over
            ``constants.PILLARS``), then before-order, then after-only ids.
        """
        diffs: list[CriterionDiff] = []
        for pillar in constants.PILLARS:
            before_map = cls._criteria_by_id(before, pillar)
            after_map = cls._criteria_by_id(after, pillar)
            for cid in cls._ordered_ids(before_map, after_map):
                diffs.append(cls._diff_criterion(cid, before_map.get(cid), after_map.get(cid)))
        return diffs

    @classmethod
    def _pillar_deltas(
        cls, before: Mapping[str, Any], after: Mapping[str, Any]
    ) -> dict[str, dict[str, float | None]]:
        """Return each pillar's before/after score and rounded delta.

        Args:
            before: The before report.
            after: The after report.

        Returns:
            An entry per pillar in ``constants.PILLARS`` with ``before``,
            ``after``, and ``delta`` (rounded to ``constants.SCORE_PRECISION``).
        """
        deltas: dict[str, dict[str, float | None]] = {}
        for pillar in constants.PILLARS:
            before_score = cls._pillar_score(before, pillar)
            after_score = cls._pillar_score(after, pillar)
            deltas[pillar] = {
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
            ``constants.SCORE_PRECISION``), ``decision_change``, ``pillars``
            (per-pillar deltas), ``criteria`` (per-criterion diff dicts),
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
            "pillars": cls._pillar_deltas(before, after),
            "criteria": [c.to_dict() for c in criteria],
            "coverage_delta": cls._delta(
                cls._coverage_score(before),
                cls._coverage_score(after),
                constants.SHARE_PRECISION,
            ),
            "regressions": regressions,
            "improvements": improvements,
        }
