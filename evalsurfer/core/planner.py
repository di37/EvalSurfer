"""Adaptive evaluation planner for EvalSurfer.

Rather than asking the user which criteria to run, :class:`EvaluationPlanner`
infers them from the evidence that is present: given a :class:`Signals` snapshot
(is there an answer? retrieved context? tool calls? a multi-turn history?
operational traces?), it returns exactly the pillars and criteria that can be
judged, each with a reason, plus a coverage score.

This is the deterministic "methodology" layer -- which signal gates which
dimension. It runs with no model calls and no third-party dependencies, and the
rubric catalog it plans over comes from :data:`constants.CRITERIA_CATALOG`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.core.scoring import ScoringModel

__all__ = [
    "Signals",
    "Criterion",
    "PlannedCriterion",
    "PlannedPillar",
    "EvaluationPlan",
    "EvaluationPlanner",
]


@dataclass(frozen=True)
class Signals:
    """What evidence is available for one evaluation target.

    ``safety_relevant`` defaults to ``True``: safety is assessed by default and
    must be opted out of deliberately.
    """

    answer: bool = False
    retrieved_context: bool = False
    citations: bool = False
    tool_calls: bool = False
    tool_failure: bool = False
    multi_turn: bool = False
    operational_traces: bool = False
    safety_relevant: bool = True

    @classmethod
    def from_sample(cls, sample: Mapping[str, Any]) -> "Signals":
        """Infer signals from a raw sample dict using common field names.

        Args:
            sample: An evaluation sample; recognised keys are listed in
                :mod:`constants` (``SAMPLE_*`` aliases). ``safety_relevant``
                honours an explicit ``safety_relevant: false`` opt-out.

        Returns:
            The inferred :class:`Signals`.

        Raises:
            TypeError: If ``sample`` is not a mapping.
            ValueError: If ``safety_relevant`` is present but not a bool.
        """
        if not isinstance(sample, Mapping):
            raise TypeError("sample must be a mapping")

        tool_calls = _first_present(sample, constants.SAMPLE_TOOL_KEYS)
        history = _first_present(sample, constants.SAMPLE_HISTORY_KEYS)
        multi_turn = isinstance(history, (list, tuple)) and len(history) > 1

        safety_relevant = sample.get(constants.SIGNAL_SAFETY_RELEVANT, True)
        if not isinstance(safety_relevant, bool):
            raise ValueError("safety_relevant must be a boolean")

        return cls(
            answer=_truthy(_first_present(sample, constants.SAMPLE_ANSWER_KEYS)),
            retrieved_context=_truthy(_first_present(sample, constants.SAMPLE_CONTEXT_KEYS)),
            citations=_truthy(_first_present(sample, constants.SAMPLE_CITATION_KEYS)),
            tool_calls=_truthy(tool_calls),
            tool_failure=_has_tool_failure(tool_calls),
            multi_turn=multi_turn,
            operational_traces=_truthy(_first_present(sample, constants.SAMPLE_TRACE_KEYS)),
            safety_relevant=safety_relevant,
        )


@dataclass(frozen=True)
class Criterion:
    """A rubric criterion and the signals required to assess it."""

    pillar: str
    group: str | None
    id: str
    name: str
    required: tuple[str, ...]


@dataclass(frozen=True)
class PlannedCriterion:
    """A criterion after applicability is resolved against the signals."""

    pillar: str
    group: str | None
    id: str
    name: str
    applicable: bool
    reason: str


@dataclass(frozen=True)
class PlannedPillar:
    """A pillar plus its planned criteria."""

    id: str
    applicable: bool
    criteria: tuple[PlannedCriterion, ...]


@dataclass(frozen=True)
class EvaluationPlan:
    """The full adaptive plan for one target."""

    pillars: tuple[PlannedPillar, ...]

    def applicable_criteria(self) -> tuple[PlannedCriterion, ...]:
        """Return every applicable criterion across all pillars."""
        return tuple(
            criterion
            for pillar in self.pillars
            for criterion in pillar.criteria
            if criterion.applicable
        )

    def to_dict(self) -> dict[str, Any]:
        """Render the plan (and its planned coverage) as a JSON-ready dict."""
        return {
            "pillars": [
                {
                    "id": pillar.id,
                    "applicable": pillar.applicable,
                    "criteria": [
                        {
                            "id": criterion.id,
                            "name": criterion.name,
                            "group": criterion.group,
                            "applicable": criterion.applicable,
                            "reason": criterion.reason,
                        }
                        for criterion in pillar.criteria
                    ],
                }
                for pillar in self.pillars
            ],
            "coverage": EvaluationPlanner.planned_coverage(self),
        }


def _truthy(value: Any) -> bool:
    """Report whether a value counts as present (non-empty)."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict, bytes)):
        return len(value) > 0
    return bool(value)


def _first_present(data: Mapping[str, Any], keys: Sequence[str]) -> Any:
    """Return the first non-``None`` value among ``keys``, else ``None``."""
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _has_tool_failure(tool_calls: Any) -> bool:
    """Report whether any tool call in the list recorded a failure."""
    if not isinstance(tool_calls, (list, tuple)):
        return False
    return any(
        isinstance(call, Mapping) and any(call.get(key) for key in constants.TOOL_FAILURE_KEYS)
        for call in tool_calls
    )


class EvaluationPlanner:
    """Resolve which pillars and criteria apply for a set of signals.

    Stateless: the rubric catalog is a class attribute and the methods derive a
    plan or coverage without per-instance state.
    """

    #: The 25 criteria, built once from the central catalog.
    CRITERIA: tuple[Criterion, ...] = tuple(
        Criterion(pillar, group, cid, name, required)
        for pillar, group, cid, name, required in constants.CRITERIA_CATALOG
    )

    @staticmethod
    def _missing_signals(signals: Signals, required: Iterable[str]) -> list[str]:
        """Return the required signal names that are not set on ``signals``."""
        return [name for name in required if not getattr(signals, name)]

    @staticmethod
    def _reason(missing: Sequence[str]) -> str:
        """Build the human-readable reason for a criterion's applicability."""
        if not missing:
            return "Applicable — all required inputs present."
        described = ", ".join(constants.SIGNAL_DESCRIPTIONS[name] for name in missing)
        return f"Skipped — missing: {described}."

    @classmethod
    def _plan_criterion(cls, criterion: Criterion, signals: Signals) -> PlannedCriterion:
        """Resolve one criterion's applicability against the signals."""
        missing = cls._missing_signals(signals, criterion.required)
        return PlannedCriterion(
            pillar=criterion.pillar,
            group=criterion.group,
            id=criterion.id,
            name=criterion.name,
            applicable=not missing,
            reason=cls._reason(missing),
        )

    @classmethod
    def plan(cls, signals: Signals) -> EvaluationPlan:
        """Resolve which pillars and criteria apply for the given signals.

        Args:
            signals: The evidence snapshot for the target.

        Returns:
            The resolved :class:`EvaluationPlan`.

        Raises:
            TypeError: If ``signals`` is not a :class:`Signals` instance.
        """
        if not isinstance(signals, Signals):
            raise TypeError("signals must be a Signals instance")

        planned = [cls._plan_criterion(criterion, signals) for criterion in cls.CRITERIA]
        pillars = []
        for pillar_id in constants.PILLARS:
            members = tuple(criterion for criterion in planned if criterion.pillar == pillar_id)
            pillars.append(
                PlannedPillar(
                    id=pillar_id,
                    applicable=any(criterion.applicable for criterion in members),
                    criteria=members,
                )
            )
        return EvaluationPlan(pillars=tuple(pillars))

    @staticmethod
    def planned_coverage(plan: EvaluationPlan) -> dict[str, Any]:
        """Summarise how much of the rubric the plan says applies.

        Args:
            plan: A resolved plan.

        Returns:
            Counts of applicable pillars/criteria and an applicable-over-total
            ``score`` rounded to ``SHARE_PRECISION`` decimals.
        """
        criteria = [criterion for pillar in plan.pillars for criterion in pillar.criteria]
        applicable = [criterion for criterion in criteria if criterion.applicable]
        applicable_pillars = [pillar for pillar in plan.pillars if pillar.applicable]
        total = len(criteria)
        return {
            "applicable_pillars": len(applicable_pillars),
            "total_pillars": len(plan.pillars),
            "applicable_criteria": len(applicable),
            "total_criteria": total,
            "score": round(len(applicable) / total, constants.SHARE_PRECISION) if total else 0.0,
        }

    @staticmethod
    def coverage(plan: EvaluationPlan, report: Mapping[str, Any]) -> dict[str, Any]:
        """Compare a plan against a produced report: applied vs assessed.

        Args:
            plan: The plan that was intended for the target.
            report: The report the judge produced.

        Returns:
            The count of applicable criteria, how many were assessed, the
            assessed-over-applicable ``score``, and the ``missing`` applicable
            criteria the report never scored.
        """
        applicable = {criterion.id for criterion in plan.applicable_criteria()}
        assessed = {
            criterion.get("id")
            for _, criterion in ScoringModel.assessed_criteria(report)
            if isinstance(criterion.get("id"), str)
        }
        covered = applicable & assessed
        return {
            "applicable": len(applicable),
            "assessed": len(covered),
            "score": round(len(covered) / len(applicable), constants.SHARE_PRECISION) if applicable else 0.0,
            "missing": sorted(applicable - assessed),
        }
