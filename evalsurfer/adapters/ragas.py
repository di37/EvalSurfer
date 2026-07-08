"""RAGAS metric adapter for EvalSurfer.

RAGAS reports RAG quality as a set of 0-1 metrics (faithfulness, answer
relevancy, context precision/recall). :class:`RagasAdapter` maps each supported
metric onto the matching EvalSurfer quality criterion and rescales its 0-1
value onto the framework's 1-5 criterion scale, so scores you already computed
with RAGAS drop straight into the rubric.

The metric-to-criterion mapping is the single source of truth in
:data:`constants.RAGAS_CRITERION_MAP`, and criterion display names come from the
planner's catalog. Pure and standard-library-only -- no model calls -- and the
input mapping is never mutated.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner

__all__ = ["RagasAdapter"]

# Width of the 1-5 criterion scale (max - min == 4); rescales a 0-1 RAGAS value
# onto it. Derived from the central bounds so no span literal is hard-coded.
_SCORE_SPAN = constants.CRITERION_MAX_SCORE - constants.CRITERION_MIN_SCORE


class RagasAdapter:
    """Map RAGAS 0-1 metrics onto EvalSurfer 1-5 rubric criteria.

    Stateless: the criterion-name lookup is a class attribute built once from the
    planner catalog, so the class is a cohesive namespace rather than something to
    instantiate.
    """

    #: Criterion id -> display name, from the planner's single catalog.
    _CRITERION_NAMES: dict[str, str] = {
        criterion.id: criterion.name for criterion in EvaluationPlanner.CRITERIA
    }

    @staticmethod
    def _score_from_value(value: float) -> int:
        """Rescale a 0-1 RAGAS value onto the 1-5 criterion scale.

        Args:
            value: A RAGAS metric value, nominally in ``[0, 1]``.

        Returns:
            The nearest 1-5 integer score, clamped to
            ``[CRITERION_MIN_SCORE, CRITERION_MAX_SCORE]`` so out-of-range values
            never escape the scale.
        """
        scaled = round(constants.CRITERION_MIN_SCORE + value * _SCORE_SPAN)
        return max(
            constants.CRITERION_MIN_SCORE,
            min(constants.CRITERION_MAX_SCORE, scaled),
        )

    @staticmethod
    def _coerce_value(metric: str, value: Any) -> float | None:
        """Coerce a metric value to a finite float, or ``None`` to skip it.

        Args:
            metric: The RAGAS metric name (for error messages).
            value: The raw value reported for the metric.

        Returns:
            The value as a ``float``, or ``None`` when the metric was reported as
            ``None`` (not computed) and should be skipped.

        Raises:
            TypeError: If ``value`` is present but not a real number.
            ValueError: If ``value`` is not finite.
        """
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"RAGAS metric {metric!r} value must be a number")
        if not isfinite(value):
            raise ValueError(f"RAGAS metric {metric!r} value must be finite")
        return float(value)

    @staticmethod
    def to_criteria(metrics: Mapping[str, float]) -> list[dict[str, Any]]:
        """Convert RAGAS metrics into EvalSurfer criterion entries.

        Every metric in :data:`constants.RAGAS_CRITERION_MAP` that is present with
        a numeric value is mapped to its criterion; unknown metrics (and metrics
        reported as ``None``) are skipped. Entries come out in the catalog's
        canonical metric order, independent of the input ordering.

        Args:
            metrics: A mapping of RAGAS metric name to its 0-1 value.

        Returns:
            A list of ``{"id", "name", "score", "evidence"}`` criterion dicts, one
            per mapped metric. The input mapping is never mutated.

        Raises:
            TypeError: If ``metrics`` is not a mapping, or a mapped metric's value
                is present but not a real number.
            ValueError: If a mapped metric's value is not finite.
        """
        if not isinstance(metrics, Mapping):
            raise TypeError("metrics must be a mapping")

        criteria: list[dict[str, Any]] = []
        for metric, criterion_id in constants.RAGAS_CRITERION_MAP.items():
            if metric not in metrics:
                continue
            value = RagasAdapter._coerce_value(metric, metrics[metric])
            if value is None:
                continue
            score = RagasAdapter._score_from_value(value)
            criteria.append(
                {
                    "id": criterion_id,
                    "name": RagasAdapter._CRITERION_NAMES.get(criterion_id, criterion_id),
                    "score": score,
                    "evidence": (
                        f"Imported from RAGAS metric {metric!r}={value} "
                        f"(0-1 scale), rescaled to {score}/"
                        f"{constants.CRITERION_MAX_SCORE}."
                    ),
                }
            )
        return criteria
