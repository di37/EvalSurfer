"""SHAP-style deduction attribution for EvalSurfer reports.

An explainability layer over the scoring model. Because that model is linear
(a pillar score is the mean of its assessed criterion scores times
``constants.PILLAR_SCALE``, and the overall score is the mean of the assessed
pillar scores), every point lost from a perfect ``constants.PERFECT_SCORE`` can
be attributed in closed form to the exact criterion that lost it -- no sampling
or feature-permutation needed.

Attribution:
* perfect = ``PERFECT_SCORE`` (every assessed criterion scored the maximum,
  ``CRITERION_MAX_SCORE``)
* points_lost(c) = (CRITERION_MAX_SCORE - score_c) * PILLAR_SCALE / (n_p * P)
    - n_p = number of assessed criteria in criterion c's pillar p
    - P   = number of assessed pillars
* the deductions sum to exactly (PERFECT_SCORE - the exact overall);
  ``reconstructed`` subtracts them from ``PERFECT_SCORE``. This matches the
  reported ``overall`` up to the scoring model's pillar-level rounding (both
  values are individually correct).

Deterministic, standard library only, no model calls. Inputs are never mutated;
every result is a freshly built object.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.scoring import ScoringModel

__all__ = [
    "Deduction",
    "Explainer",
]


@dataclass(frozen=True)
class Deduction:
    """One assessed criterion's contribution to the points lost from perfect."""

    id: str | None
    name: str
    pillar: str
    score: int
    points_lost: float

    def to_dict(self) -> dict[str, Any]:
        """Render this deduction as a plain dict for JSON output.

        Returns:
            A dict with ``id``, ``name``, ``pillar``, ``score``, and
            ``points_lost`` keys.
        """
        return {
            "id": self.id,
            "name": self.name,
            "pillar": self.pillar,
            "score": self.score,
            "points_lost": self.points_lost,
        }


def _criterion_name(criterion: Mapping[str, Any]) -> str:
    """Return the best-available display name for a criterion.

    Args:
        criterion: A criterion mapping.

    Returns:
        The ``name`` field when it is a non-empty string; otherwise the ``id``
        field when it is a string; otherwise the empty string.
    """
    name = criterion.get("name")
    if isinstance(name, str) and name:
        return name
    cid = criterion.get("id")
    return cid if isinstance(cid, str) else ""


class Explainer:
    """Closed-form deduction attribution over the scoring model.

    Stateless: the attribution inverts the linear scoring rules, so the methods
    derive an explanation without per-instance state.
    """

    @staticmethod
    def _validate_score(value: Any, criterion_id: Any) -> int:
        """Coerce an assessed criterion score to an int within the valid range.

        Args:
            value: The raw ``score`` value from a criterion.
            criterion_id: The criterion's id, used only for error messages.

        Returns:
            The score as an int in ``[CRITERION_MIN_SCORE, CRITERION_MAX_SCORE]``.

        Raises:
            ValueError: If the value is a bool, not an int, or out of range.
        """
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"criterion {criterion_id!r} score must be an int "
                f"{constants.CRITERION_MIN_SCORE}-{constants.CRITERION_MAX_SCORE}, "
                f"got {value!r}"
            )
        if not constants.CRITERION_MIN_SCORE <= value <= constants.CRITERION_MAX_SCORE:
            raise ValueError(
                f"criterion {criterion_id!r} score must be between "
                f"{constants.CRITERION_MIN_SCORE} and {constants.CRITERION_MAX_SCORE}, "
                f"got {value}"
            )
        return value

    @classmethod
    def _assessed_by_pillar(
        cls, report: Mapping[str, Any]
    ) -> dict[str, list[tuple[Mapping[str, Any], int]]]:
        """Group assessed criteria (score not ``None``) by pillar id.

        Criteria whose score is ``None`` are excluded. Pillars with no assessed
        criteria never appear, so ``len(...)`` is the assessed-pillar count ``P``.

        Args:
            report: A report mapping.

        Returns:
            A mapping of pillar id to a list of ``(criterion, validated_score)``
            pairs for its assessed criteria.

        Raises:
            ValueError: If any assessed criterion has an invalid score.
        """
        grouped: dict[str, list[tuple[Mapping[str, Any], int]]] = {}
        for pillar_id, criterion in ScoringModel.iter_criteria(report):
            raw = criterion.get("score")
            if raw is None:
                continue
            score = cls._validate_score(raw, criterion.get("id"))
            grouped.setdefault(pillar_id, []).append((criterion, score))
        return grouped

    @staticmethod
    def _deductions(
        grouped: Mapping[str, list[tuple[Mapping[str, Any], int]]],
    ) -> list[Deduction]:
        """Compute the closed-form deduction for every imperfect assessed criterion.

        Args:
            grouped: Assessed criteria grouped by pillar, as produced by
                :meth:`_assessed_by_pillar`.

        Returns:
            The deductions for criteria scoring below ``CRITERION_MAX_SCORE``,
            sorted by ``points_lost`` descending (ties broken by id).
        """
        pillar_count = len(grouped)  # P
        result: list[Deduction] = []
        for pillar_id, members in grouped.items():
            denominator = len(members) * pillar_count  # n_p * P
            for criterion, score in members:
                if score >= constants.CRITERION_MAX_SCORE:
                    continue  # a perfect criterion loses nothing
                points_lost = (
                    (constants.CRITERION_MAX_SCORE - score) * constants.PILLAR_SCALE
                    / denominator
                )
                result.append(
                    Deduction(
                        id=criterion.get("id"),
                        name=_criterion_name(criterion),
                        pillar=pillar_id,
                        score=score,
                        points_lost=round(points_lost, constants.SHARE_PRECISION),
                    )
                )
        result.sort(key=lambda deduction: (-deduction.points_lost, str(deduction.id)))
        return result

    @staticmethod
    def explain(report: Mapping[str, Any]) -> dict[str, Any]:
        """Attribute the gap between perfect and the overall score by criterion.

        Args:
            report: A report mapping.

        Returns:
            A dict with the ``perfect`` baseline (``PERFECT_SCORE``), the
            ``overall`` score recomputed via :meth:`ScoringModel.score`, the
            per-criterion ``deductions`` (only assessed criteria scoring below
            ``CRITERION_MAX_SCORE``, sorted by ``points_lost`` descending), and
            the ``reconstructed`` overall obtained by subtracting those
            deductions from ``PERFECT_SCORE``.

        Raises:
            TypeError: If ``report`` is not a mapping.
            ValueError: If any assessed criterion has an invalid score.
        """
        if not isinstance(report, Mapping):
            raise TypeError("report must be a mapping")

        deductions = Explainer._deductions(Explainer._assessed_by_pillar(report))
        total_lost = sum(deduction.points_lost for deduction in deductions)
        return {
            "perfect": constants.PERFECT_SCORE,
            "overall": ScoringModel.score(report)["overall"],
            "deductions": [deduction.to_dict() for deduction in deductions],
            "reconstructed": round(
                constants.PERFECT_SCORE - total_lost, constants.SHARE_PRECISION
            ),
        }
