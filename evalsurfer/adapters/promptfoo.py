"""promptfoo result adapter for EvalSurfer.

promptfoo runs assertion-based test cases and reports, per case, whether it
succeeded. :class:`PromptfooAdapter` turns a promptfoo results object into a
minimal EvalSurfer report: it scores the single ``correctness_accuracy``
quality criterion from the pass rate, then reuses :class:`ScoringModel` for the
pillar score, the overall score, and the pass/fix/fail decision.

Deliberately minimal -- one criterion, one pillar -- so a promptfoo suite you
already run can gate through the same decision logic as a native evaluation.
Pure and standard-library-only; no model calls; the input is never mutated.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner
from evalsurfer.core.scoring import ScoringModel
from evalsurfer.operational.metrics import parse_bool

__all__ = ["PromptfooAdapter"]

# The single quality criterion a promptfoo pass rate maps onto.
_TARGET_CRITERION = "correctness_accuracy"
# Width of the 1-5 criterion scale; rescales a 0-1 pass fraction onto it.
_SCORE_SPAN = constants.CRITERION_MAX_SCORE - constants.CRITERION_MIN_SCORE


class PromptfooAdapter:
    """Build a minimal EvalSurfer report from promptfoo results.

    Stateless: the target criterion's display name is resolved once from the
    planner catalog, and the report is derived with no per-instance state.
    """

    #: The display name for the target criterion, from the planner catalog.
    _CRITERION_NAME: str = next(
        (
            criterion.name
            for criterion in EvaluationPlanner.CRITERIA
            if criterion.id == _TARGET_CRITERION
        ),
        _TARGET_CRITERION,
    )

    @staticmethod
    def _extract_cases(results: Mapping[str, Any] | Sequence[Any]) -> list[Any]:
        """Pull the list of result cases from a promptfoo object or bare list.

        Args:
            results: A promptfoo results object (``{"results": [...]}``) or a bare
                list of per-case entries.

        Returns:
            The list of per-case result entries.

        Raises:
            TypeError: If ``results`` is neither a mapping nor a list.
            ValueError: If a mapping lacks a ``results`` list.
        """
        if isinstance(results, Mapping):
            cases = results.get("results")
            if not isinstance(cases, list):
                raise ValueError("promptfoo object must contain a 'results' list")
            return cases
        if isinstance(results, list):
            return results
        raise TypeError("results must be a promptfoo object or a list of cases")

    @staticmethod
    def _pass_count(cases: Sequence[Any]) -> int:
        """Count the promptfoo cases that succeeded.

        Args:
            cases: The per-case result mappings.

        Returns:
            The number of cases whose ``success`` field is truthy. A missing
            ``success`` counts as a failure.

        Raises:
            TypeError: If a case is not a mapping.
            ValueError: If a ``success`` value is not boolean-like.
        """
        passed = 0
        for case in cases:
            if not isinstance(case, Mapping):
                raise TypeError("each promptfoo result must be a mapping")
            if parse_bool(case.get("success"), "success"):
                passed += 1
        return passed

    @staticmethod
    def to_report(results: Mapping[str, Any] | Sequence[Any]) -> dict[str, Any]:
        """Convert promptfoo results into a minimal EvalSurfer report.

        The pass rate over the cases is mapped to a 1-5 ``correctness_accuracy``
        score; the quality pillar score, overall score, and decision are all
        computed by :class:`ScoringModel`. With no safety pillar assessed, the
        decision can only ever be ``fail`` or ``pass_with_fixes`` (a full pass
        requires a safety assessment).

        Args:
            results: A promptfoo-style object ``{"results": [{"success": bool,
                "score": float?}, ...]}`` (a bare list of cases is also accepted).

        Returns:
            A new report dict with an ``overall`` block, a single ``quality``
            pillar carrying the ``correctness_accuracy`` criterion, a top-level
            ``decision``, and ``metadata`` recording the import. The input is
            never mutated.

        Raises:
            TypeError: If ``results`` is neither a mapping nor a list, or a case is
                not a mapping.
            ValueError: If the results list is missing or empty, or a ``success``
                value is not boolean-like.
        """
        cases = PromptfooAdapter._extract_cases(results)
        if not cases:
            raise ValueError("promptfoo results list must not be empty")

        passed = PromptfooAdapter._pass_count(cases)
        total = len(cases)
        pass_fraction = passed / total
        score = round(constants.CRITERION_MIN_SCORE + pass_fraction * _SCORE_SPAN)
        rounded_fraction = round(pass_fraction, constants.SHARE_PRECISION)

        criterion = {
            "id": _TARGET_CRITERION,
            "name": PromptfooAdapter._CRITERION_NAME,
            "score": score,
            "evidence": (
                f"{passed}/{total} promptfoo cases passed "
                f"(pass rate {rounded_fraction})."
            ),
        }
        pillar_score = ScoringModel.pillar_score([score])
        overall = ScoringModel.overall_score([pillar_score])
        decision = ScoringModel.decide(overall, None)

        return {
            "overall": {
                "score": overall,
                "decision": decision,
                "summary": (
                    f"Imported {total} promptfoo case(s); correctness scored "
                    f"{score}/{constants.CRITERION_MAX_SCORE}."
                ),
            },
            "pillars": {
                constants.PILLAR_QUALITY: {
                    "score": pillar_score,
                    "criteria": [criterion],
                }
            },
            "decision": decision,
            "top_issues": [],
            "not_assessed": [],
            "metadata": {
                "source": constants.ADAPTER_PROMPTFOO,
                "case_count": total,
                "pass_count": passed,
            },
        }
