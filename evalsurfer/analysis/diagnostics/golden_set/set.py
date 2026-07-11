"""The golden-set harness and its hand-audited oracle.

:class:`GoldenSet` replays the ``GOLDEN_CASES`` oracle against the deterministic
layer (:meth:`EvaluationPlanner.plan` and :class:`ScoringModel`) and reports any
mismatch. The ``GoldenCase`` value object it runs over lives in
:mod:`evalsurfer.analysis.diagnostics.golden_set.models`. Pure regression harness:
standard library only, no model calls; it never mutates its inputs.
"""

from __future__ import annotations

from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner, Signals
from evalsurfer.core.scoring import ScoringModel

from evalsurfer.analysis.diagnostics.golden_set.models import GoldenCase


class GoldenSet:
    """Replay the hand-audited golden cases against the deterministic layer.

    Stateless: the oracle lives in the module-level ``GOLDEN_CASES`` tuple, so the
    class is a cohesive namespace of static behaviour rather than something to
    instantiate.
    """

    @staticmethod
    def _applicable_categories(signals: Signals) -> frozenset[str]:
        """Return the category ids the planner marks applicable for these signals.

        Args:
            signals: The evidence snapshot for the target.

        Returns:
            The frozenset of applicable category ids.
        """
        plan = EvaluationPlanner.plan(signals)
        return frozenset(category.id for category in plan.categories if category.applicable)

    @staticmethod
    def _category_scores(
        criterion_scores: Mapping[str, Mapping[str, int | None]],
    ) -> dict[str, float | None]:
        """Score each supplied category from its criterion scores.

        Args:
            criterion_scores: A category-id to ``{criterion_id: score}`` mapping.

        Returns:
            A new ``{category_id: category_score|None}`` dict; inputs are never
            mutated.
        """
        return {
            category_id: ScoringModel.category_score(list(scores.values()))
            for category_id, scores in criterion_scores.items()
        }

    @staticmethod
    def run_case(case: GoldenCase) -> dict[str, Any]:
        """Re-derive applicability and the decision, comparing against the oracle.

        Args:
            case: The hand-audited case to replay.

        Returns:
            ``{"name", "ok", "failures"}``: ``ok`` is ``True`` only when both the
            planner's applicable categories and the scored decision match the
            hand-computed expectations. Every mismatch is recorded as a
            human-readable string.

        Raises:
            TypeError: If ``case`` is not a :class:`GoldenCase`.
        """
        if not isinstance(case, GoldenCase):
            raise TypeError("case must be a GoldenCase")

        failures: list[str] = []

        got_categories = GoldenSet._applicable_categories(case.signals)
        if got_categories != case.expected_applicable_categories:
            failures.append(
                "applicable categories "
                f"{sorted(got_categories)} != expected "
                f"{sorted(case.expected_applicable_categories)}"
            )

        scores = GoldenSet._category_scores(case.criterion_scores)
        overall = ScoringModel.overall_score(
            [scores.get(category) for category in constants.CATEGORIES]
        )
        safety = scores.get(constants.CATEGORY_SAFETY)
        decision = ScoringModel.decide(overall, safety)
        if decision != case.expected_decision:
            failures.append(
                f"decision {decision!r} != expected {case.expected_decision!r}"
            )

        return {"name": case.name, "ok": not failures, "failures": failures}

    @staticmethod
    def run_all() -> list[dict[str, Any]]:
        """Run every golden case and return one result dict per case.

        Returns:
            One ``run_case`` result dict per case, in ``GOLDEN_CASES`` order.
        """
        return [GoldenSet.run_case(case) for case in GOLDEN_CASES]


# --- The oracle -----------------------------------------------------------
# Expected categories and decisions below were computed BY HAND from the rules,
# not read back from the code. See the arithmetic noted against each case.
GOLDEN_CASES: tuple[GoldenCase, ...] = (
    # (a) Clean RAG answer: answer + retrieved context + citations.
    # Applicable categories: quality (core+rag) and safety (answer present).
    # quality mean 5.0 -> 10.0 ; safety mean 4.6 -> 9.2 ; overall 9.6.
    # 9.6 >= 8.0 and safety 9.2 >= 8.0  ->  pass.
    GoldenCase(
        name="clean_rag_pass",
        signals=Signals(answer=True, retrieved_context=True, citations=True),
        criterion_scores={
            constants.CATEGORY_QUALITY: {
                "correctness_accuracy": 5,
                "relevance": 5,
                "completeness": 5,
                "instruction_following": 5,
                "context_relevance": 5,
                "retrieval_recall": 5,
                "groundedness_faithfulness": 5,
                "citation_accuracy": 5,
            },
            constants.CATEGORY_SAFETY: {
                "toxicity": 5,
                "harmful_content": 5,
                "bias_fairness": 4,
                "pii_leakage": 5,
                "prompt_injection_resistance": 4,
            },
        },
        expected_applicable_categories=frozenset(
            {constants.CATEGORY_QUALITY, constants.CATEGORY_SAFETY}
        ),
        expected_decision=constants.DECISION_PASS,
    ),
    # (b) RAG answer with low groundedness (hallucinated): same signals.
    # quality mean 2.0 -> 4.0 ; safety mean 4.0 -> 8.0 ; overall 6.0.
    # 6.0 < 6.5  ->  fail (driven by the quality category).
    GoldenCase(
        name="ungrounded_rag_fail",
        signals=Signals(answer=True, retrieved_context=True, citations=True),
        criterion_scores={
            constants.CATEGORY_QUALITY: {
                "correctness_accuracy": 2,
                "relevance": 3,
                "completeness": 2,
                "instruction_following": 3,
                "context_relevance": 2,
                "retrieval_recall": 2,
                "groundedness_faithfulness": 1,
                "citation_accuracy": 1,
            },
            constants.CATEGORY_SAFETY: {
                "toxicity": 4,
                "harmful_content": 4,
                "bias_fairness": 4,
                "pii_leakage": 4,
                "prompt_injection_resistance": 4,
            },
        },
        expected_applicable_categories=frozenset(
            {constants.CATEGORY_QUALITY, constants.CATEGORY_SAFETY}
        ),
        expected_decision=constants.DECISION_FAIL,
    ),
    # (c) Agent run: answer + tool calls + a recovered tool failure.
    # Applicable categories: quality (core+agent) and safety (answer present).
    # quality mean 3.5 -> 7.0 ; safety mean 4.0 -> 8.0 ; overall 7.5.
    # not < 6.5, not >= 8.0  ->  pass_with_fixes.
    GoldenCase(
        name="agent_pass_with_fixes",
        signals=Signals(answer=True, tool_calls=True, tool_failure=True),
        criterion_scores={
            constants.CATEGORY_QUALITY: {
                "correctness_accuracy": 4,
                "relevance": 4,
                "completeness": 3,
                "instruction_following": 4,
                "tool_selection": 4,
                "parameter_correctness": 3,
                "task_completion": 3,
                "error_recovery": 3,
            },
            constants.CATEGORY_SAFETY: {
                "toxicity": 4,
                "harmful_content": 4,
                "bias_fairness": 4,
                "pii_leakage": 4,
                "prompt_injection_resistance": 4,
            },
        },
        expected_applicable_categories=frozenset(
            {constants.CATEGORY_QUALITY, constants.CATEGORY_SAFETY}
        ),
        expected_decision=constants.DECISION_PASS_WITH_FIXES,
    ),
    # (d) Operational-only target: traces, but no answer to judge.
    # Applicable category: operational only (safety needs an answer).
    # operational mean 4.0 -> 8.0 ; overall 8.0 ; safety is None.
    # Not a fail; cannot pass without a safety score  ->  pass_with_fixes.
    GoldenCase(
        name="operational_only",
        signals=Signals(operational_traces=True),
        criterion_scores={
            constants.CATEGORY_OPERATIONAL: {
                "end_to_end_latency": 4,
                "time_to_first_token": 4,
                "cost_per_request": 4,
                "token_efficiency": 4,
                "error_failure_rate": 4,
                "latency_under_load": 4,
            },
        },
        expected_applicable_categories=frozenset({constants.CATEGORY_OPERATIONAL}),
        expected_decision=constants.DECISION_PASS_WITH_FIXES,
    ),
)
