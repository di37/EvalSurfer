"""Persona evaluation aggregation for EvalSurfer.

The same target (an answer, a RAG response, an agent trace) is often judged from
several stakeholder viewpoints -- an engineer cares about correctness, a lawyer
about liability, a beginner about clarity. Each persona produces its own report;
:class:`PersonaAggregator` folds those reports into one comparison so you can see
which persona the target serves best and which it serves worst.

Deterministic and immutable: it reads each report's overall score (recomputing it
from the criterion scores via :meth:`ScoringModel.score` when the report omits
one), never mutates its inputs, and makes no model calls. Personas whose score is
unknown are kept in the per-persona breakdown but excluded from every aggregate
statistic. The reference persona set comes from :data:`constants.DEFAULT_PERSONAS`.
"""

from __future__ import annotations

from math import isfinite
from statistics import mean
from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.scoring import ScoringModel

__all__ = ["PersonaAggregator"]


class PersonaAggregator:
    """Fold one target's per-persona reports into a single comparison.

    Stateless: every method is static because aggregating persona reports carries
    no per-instance configuration, so the class is a cohesive namespace rather
    than something to instantiate. The reference persona set is exposed as a class
    attribute sourced from :data:`constants.DEFAULT_PERSONAS`.
    """

    #: A documented starting set of common stakeholder personas. Callers are free
    #: to pass any other persona names; this is only a reference.
    REFERENCE_PERSONAS: tuple[str, ...] = constants.DEFAULT_PERSONAS

    @staticmethod
    def _coerce_score(value: Any) -> float:
        """Validate a present ``overall.score`` and round it.

        Args:
            value: The raw ``overall.score`` read from a report.

        Returns:
            The score as a float rounded to ``SCORE_PRECISION`` decimals.

        Raises:
            ValueError: If ``value`` is a bool, non-numeric, or not finite.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("overall.score must be a number")
        number = float(value)
        if not isfinite(number):
            raise ValueError("overall.score must be finite")
        return round(number, constants.SCORE_PRECISION)

    @staticmethod
    def _target_score(report: Mapping[str, Any]) -> float | None:
        """Read a report's overall score, falling back to a recomputed one.

        Uses ``report["overall"]["score"]`` when present, otherwise recomputes the
        overall score from the criterion scores via :meth:`ScoringModel.score`.

        Args:
            report: A single persona's report mapping.

        Returns:
            The overall score rounded to ``SCORE_PRECISION`` decimals, or ``None``
            when neither path yields a score (e.g. a report with no assessed
            criteria).
        """
        overall = report.get("overall")
        if isinstance(overall, Mapping):
            raw = overall.get("score")
            if raw is not None:
                return PersonaAggregator._coerce_score(raw)

        computed = ScoringModel.score(report).get("overall")
        if computed is None:
            return None
        return round(float(computed), constants.SCORE_PRECISION)

    @staticmethod
    def _extremum(scored: Mapping[str, float], *, want_max: bool) -> tuple[str, float]:
        """Find the persona with the highest or lowest score.

        Iterates personas in sorted-name order and only replaces the running best
        on a strict improvement, so ties resolve to the alphabetically-first
        persona for both the minimum and the maximum. This keeps the result
        deterministic regardless of the input mapping's ordering.

        Args:
            scored: A non-empty mapping of persona name to known score.
            want_max: Find the highest score when ``True``, else the lowest.

        Returns:
            A ``(persona, score)`` pair at the requested extreme.
        """
        items = sorted(scored.items())
        best_persona, best_score = items[0]
        for persona, score in items[1:]:
            if (score > best_score) if want_max else (score < best_score):
                best_persona, best_score = persona, score
        return best_persona, best_score

    @staticmethod
    def aggregate(reports: Mapping[str, dict]) -> dict[str, Any]:
        """Aggregate one target's reports across personas into a comparison.

        Args:
            reports: A mapping of persona name to that persona's report.

        Returns:
            A dict holding the per-persona scores (``None`` where unknown) plus
            aggregate statistics computed over the personas that do have a score:

            * ``scores``        -- ``{persona: float | None}`` for every input.
            * ``mean``          -- mean of the known scores, rounded to
              ``SCORE_PRECISION`` decimals.
            * ``min`` / ``max`` -- ``{"persona", "score"}`` at the extremes.
            * ``range``         -- ``max`` minus ``min``, rounded to
              ``SCORE_PRECISION`` decimals.
            * ``most_served``   -- the persona with the highest score.
            * ``least_served``  -- the persona with the lowest score.

            Every aggregate is ``None`` when no persona has a known score. Inputs
            are never mutated.

        Raises:
            TypeError: If ``reports`` is not a mapping, a persona key is not a
                string, or a report is not a mapping.
            ValueError: If a present ``overall.score`` is not a finite number.
        """
        if not isinstance(reports, Mapping):
            raise TypeError("reports must be a mapping of persona -> report")

        scores: dict[str, float | None] = {}
        for persona, report in reports.items():
            if not isinstance(persona, str):
                raise TypeError("persona keys must be strings")
            if not isinstance(report, Mapping):
                raise TypeError(f"report for persona {persona!r} must be a mapping")
            scores[persona] = PersonaAggregator._target_score(report)

        scored = {
            persona: score for persona, score in scores.items() if score is not None
        }
        if not scored:
            return {
                "scores": scores,
                "mean": None,
                "min": None,
                "max": None,
                "range": None,
                "most_served": None,
                "least_served": None,
            }

        max_persona, max_score = PersonaAggregator._extremum(scored, want_max=True)
        min_persona, min_score = PersonaAggregator._extremum(scored, want_max=False)

        return {
            "scores": scores,
            "mean": round(mean(scored.values()), constants.SCORE_PRECISION),
            "min": {"persona": min_persona, "score": min_score},
            "max": {"persona": max_persona, "score": max_score},
            "range": round(max_score - min_score, constants.SCORE_PRECISION),
            "most_served": max_persona,
            "least_served": min_persona,
        }
