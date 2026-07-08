"""Visual failure map for EvalSurfer reports.

Projects a produced report onto a linear application pipeline
(Prompt -> Retriever -> Ranker -> Generator -> Tool -> Response) and marks which
stages are weak. Each rubric criterion is mapped to the stage it exercises via
its ``(pillar, group)`` location (RAG criteria to the retriever and ranker,
core-generation / multi-turn / safety criteria to the generator, tool-use
criteria to the tool stage). A stage fails when any of its *assessed* criteria
scored below a threshold.

The result is renderable in three shapes: a structured list of stage diagnoses,
a Mermaid ``flowchart LR`` with failing stages styled, and a plain arrow chain
for terminals. Standard library only, no model calls -- it reads an existing
report and never mutates it. The pipeline, statuses, selectors, and default
threshold all come from :mod:`constants`.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner
from evalsurfer.core.scoring import ScoringModel

__all__ = ["StageDiagnosis", "FailureMap"]

# Mermaid / plain-text rendering literals. These are presentation details unique
# to this module (not framework values), named here rather than inlined.
_MERMAID_HEADER = "flowchart LR"
_MERMAID_EDGE = " --> "
_MERMAID_INDENT = "    "
# The styled Mermaid class applies only to failing stages, so its name is the
# fail status itself rather than a separate literal.
_MERMAID_FAIL_CLASS = constants.STAGE_STATUS_FAIL
_MERMAID_FAIL_CLASSDEF = f"classDef {_MERMAID_FAIL_CLASS} fill:#f88,stroke:#900,color:#111;"
_TEXT_EDGE = " -> "
_TEXT_FAIL_MARKER = "[FAIL]"

# Each criterion id mapped to its ``(pillar, group)`` location, from the planner's
# canonical catalog. Used to decide which pipeline stage a criterion feeds.
_CRITERION_LOCATION: dict[str, tuple[str, str | None]] = {
    criterion.id: (criterion.pillar, criterion.group)
    for criterion in EvaluationPlanner.CRITERIA
}


@dataclass(frozen=True)
class StageDiagnosis:
    """The health of one pipeline stage after projecting a report onto it."""

    stage: str
    status: str
    weak_criteria: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Render the diagnosis as a JSON-ready dict.

        Returns:
            ``{"stage", "status", "weak_criteria"}`` with ``weak_criteria`` as a
            list.
        """
        return {
            "stage": self.stage,
            "status": self.status,
            "weak_criteria": list(self.weak_criteria),
        }


class FailureMap:
    """Project a report onto the application pipeline and mark weak stages.

    The weak-below ``threshold`` is the only configurable state and is fixed at
    construction. Everything else -- the pipeline order, stage statuses, and the
    stage-to-criteria mapping -- is derived from :mod:`constants` and the
    planner's rubric catalog.
    """

    #: Stage -> the criterion ids it covers, in canonical planner order. Stages
    #: absent from ``constants.STAGE_SELECTORS`` (Prompt, Response) cover none.
    STAGE_CRITERIA: dict[str, tuple[str, ...]] = {
        stage: tuple(
            cid
            for cid, location in _CRITERION_LOCATION.items()
            if location in constants.STAGE_SELECTORS.get(stage, ())
        )
        for stage in constants.PIPELINE_STAGES
    }

    def __init__(self, threshold: int = constants.FAILURE_MAP_THRESHOLD) -> None:
        """Configure the renderer with a weak-below score threshold.

        Args:
            threshold: A criterion scoring *below* this marks its stage weak.
                Must be an int within the criterion scale
                (``CRITERION_MIN_SCORE``..``CRITERION_MAX_SCORE``).

        Raises:
            TypeError: If ``threshold`` is not an int (bools are rejected).
            ValueError: If ``threshold`` is outside the criterion scale.
        """
        self._validate_threshold(threshold)
        self._threshold = threshold

    def render(self, report: Mapping[str, Any]) -> dict[str, Any]:
        """Render a report as a pipeline failure map.

        A stage is ``fail`` when any of its assessed criteria scored below the
        configured threshold, ``ok`` when it has assessed criteria and none are
        weak, and ``na`` when it has no assessed criteria. The Response stage
        instead mirrors the report's overall decision. The report is never
        mutated.

        Args:
            report: A produced report mapping.

        Returns:
            A dict with ``stages`` (one ``{"stage", "status", "weak_criteria"}``
            entry per pipeline stage), ``mermaid`` (a ``flowchart LR`` string
            with failing stages styled), and ``text`` (a plain arrow chain that
            marks failing stages with ``[FAIL]``).

        Raises:
            TypeError: If ``report`` is not a mapping.
        """
        if not isinstance(report, Mapping):
            raise TypeError("report must be a mapping")

        scores = self._scores_by_id(report)

        diagnoses: list[StageDiagnosis] = []
        statuses: dict[str, str] = {}
        for stage in constants.PIPELINE_STAGES:
            if stage == constants.STAGE_RESPONSE:
                status, weak = self._response_status(report), ()
            else:
                status, weak = self._diagnose_stage(self.STAGE_CRITERIA[stage], scores)
            statuses[stage] = status
            diagnoses.append(
                StageDiagnosis(stage=stage, status=status, weak_criteria=weak)
            )

        return {
            "stages": [diagnosis.to_dict() for diagnosis in diagnoses],
            "mermaid": self._mermaid(statuses),
            "text": self._text(statuses),
        }

    def _diagnose_stage(
        self,
        mapped_ids: tuple[str, ...],
        scores: Mapping[str, float],
    ) -> tuple[str, tuple[str, ...]]:
        """Compute the status and weak-criteria list for a criteria-backed stage.

        Args:
            mapped_ids: The criterion ids the stage covers, in canonical order.
            scores: Assessed criterion id -> numeric score.

        Returns:
            ``(status, weak_criteria)`` where ``status`` is ``STAGE_STATUS_NA``
            when the stage has no assessed criteria, ``STAGE_STATUS_FAIL`` when
            any assessed criterion is below the threshold, else
            ``STAGE_STATUS_OK``.
        """
        assessed = [(cid, scores[cid]) for cid in mapped_ids if cid in scores]
        if not assessed:
            return constants.STAGE_STATUS_NA, ()
        weak = tuple(cid for cid, score in assessed if score < self._threshold)
        status = constants.STAGE_STATUS_FAIL if weak else constants.STAGE_STATUS_OK
        return status, weak

    @staticmethod
    def _validate_threshold(threshold: int) -> None:
        """Validate a weak-below threshold against the criterion scale.

        Args:
            threshold: The candidate threshold.

        Raises:
            TypeError: If ``threshold`` is not an int (bools are rejected).
            ValueError: If ``threshold`` is outside the criterion scale.
        """
        if isinstance(threshold, bool) or not isinstance(threshold, int):
            raise TypeError("threshold must be an int")
        if not constants.CRITERION_MIN_SCORE <= threshold <= constants.CRITERION_MAX_SCORE:
            raise ValueError(
                "threshold must be between "
                f"{constants.CRITERION_MIN_SCORE} and {constants.CRITERION_MAX_SCORE}"
            )

    @staticmethod
    def _as_numeric_score(value: Any) -> float | None:
        """Interpret a report score as a number, or ``None`` if not assessed.

        Booleans and non-numeric values are treated as "not a score" rather than
        coerced, so a stray ``True`` never counts as an assessment.

        Args:
            value: A raw ``score`` value from a report criterion.

        Returns:
            The numeric score as a float, or ``None`` when it is not a finite
            number.
        """
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return float(value)
        if isinstance(value, float):
            return value if isfinite(value) else None
        return None

    @classmethod
    def _scores_by_id(cls, report: Mapping[str, Any]) -> dict[str, float]:
        """Map each assessed criterion id to its numeric score.

        Only criteria with a real numeric score are included; ``None`` and
        non-numeric scores are skipped. The first numeric score wins if an id
        somehow repeats, keeping the result deterministic.

        Args:
            report: A produced report mapping.

        Returns:
            A mapping of criterion id to its numeric score.
        """
        scores: dict[str, float] = {}
        for _pillar_id, criterion in ScoringModel.iter_criteria(report):
            cid = criterion.get("id")
            if not isinstance(cid, str) or cid in scores:
                continue
            numeric = cls._as_numeric_score(criterion.get("score"))
            if numeric is not None:
                scores[cid] = numeric
        return scores

    @staticmethod
    def _overall_decision(report: Mapping[str, Any]) -> str | None:
        """Return the report's decision, preferring ``overall.decision``.

        Args:
            report: A produced report mapping.

        Returns:
            The overall decision string, the top-level ``decision`` as a
            fallback, or ``None`` when neither is a non-empty string.
        """
        overall = report.get("overall")
        if isinstance(overall, Mapping):
            decision = overall.get("decision")
            if isinstance(decision, str) and decision:
                return decision
        decision = report.get("decision")
        if isinstance(decision, str) and decision:
            return decision
        return None

    @classmethod
    def _response_status(cls, report: Mapping[str, Any]) -> str:
        """Reflect the overall decision onto the Response stage.

        ``pass`` reads as ``ok``, any other explicit decision as ``fail``, and a
        missing decision as ``na`` (nothing to reflect).

        Args:
            report: A produced report mapping.

        Returns:
            One of ``STAGE_STATUS_OK``, ``STAGE_STATUS_FAIL``, or
            ``STAGE_STATUS_NA``.
        """
        decision = cls._overall_decision(report)
        if decision is None:
            return constants.STAGE_STATUS_NA
        if decision == constants.DECISION_PASS:
            return constants.STAGE_STATUS_OK
        return constants.STAGE_STATUS_FAIL

    @staticmethod
    def _mermaid(statuses: Mapping[str, str]) -> str:
        """Build a ``flowchart LR`` chain with failing stages styled.

        Args:
            statuses: Stage -> status for every pipeline stage.

        Returns:
            A Mermaid ``flowchart LR`` source string.
        """
        chain = _MERMAID_EDGE.join(constants.PIPELINE_STAGES)
        lines = [
            _MERMAID_HEADER,
            f"{_MERMAID_INDENT}{chain}",
            f"{_MERMAID_INDENT}{_MERMAID_FAIL_CLASSDEF}",
        ]
        failing = [
            stage
            for stage in constants.PIPELINE_STAGES
            if statuses[stage] == constants.STAGE_STATUS_FAIL
        ]
        if failing:
            lines.append(
                f"{_MERMAID_INDENT}class {','.join(failing)} {_MERMAID_FAIL_CLASS}"
            )
        return "\n".join(lines)

    @staticmethod
    def _text(statuses: Mapping[str, str]) -> str:
        """Build a plain arrow chain marking failing stages.

        Args:
            statuses: Stage -> status for every pipeline stage.

        Returns:
            A chain such as ``Prompt -> Retriever[FAIL] -> ... -> Response``.
        """
        parts = [
            f"{stage}{_TEXT_FAIL_MARKER}"
            if statuses[stage] == constants.STAGE_STATUS_FAIL
            else stage
            for stage in constants.PIPELINE_STAGES
        ]
        return _TEXT_EDGE.join(parts)
