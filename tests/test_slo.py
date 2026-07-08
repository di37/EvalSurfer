from __future__ import annotations

from math import inf, nan
import unittest

import evalsurfer.constants as constants
from evalsurfer.operational.slo import (
    CriterionScore,
    OperationalScore,
    OperationalScorer,
)


# A single fast request: 1200 ms end-to-end, 300 ms TTFT, 0.006 USD cost.
SINGLE_TRACE = {
    "request_started_at": 0,
    "first_token_at": 0.3,
    "response_completed_at": 1.2,
    "input_tokens": 1000,
    "output_tokens": 500,
}
PRICING = {"input_per_million": 2.0, "output_per_million": 8.0}
FULL_SLO = {
    constants.SLO_P95_LATENCY_MS: 1000.0,
    constants.SLO_TTFT_MS: 500.0,
    constants.SLO_MAX_COST_USD: 0.01,
    constants.SLO_MAX_FAILURE_RATE: 0.02,
}


def by_id(result: dict) -> dict:
    """Index a score result's criteria list by criterion id."""
    return {criterion["id"]: criterion for criterion in result["criteria"]}


class ScoreRatioTest(unittest.TestCase):
    def test_returns_none_when_measured_or_target_missing(self) -> None:
        self.assertIsNone(OperationalScorer.score_ratio(None, 100.0))
        self.assertIsNone(OperationalScorer.score_ratio(50.0, None))

    def test_returns_none_when_target_not_positive(self) -> None:
        self.assertIsNone(OperationalScorer.score_ratio(50.0, 0.0))
        self.assertIsNone(OperationalScorer.score_ratio(50.0, -10.0))

    def test_maps_ratio_to_expected_band(self) -> None:
        cases = {
            0.0: 5,  # ratio 0.0
            40.0: 5,  # ratio 0.4
            50.0: 5,  # ratio 0.5 (band edge)
            60.0: 4,  # ratio 0.6
            80.0: 4,  # ratio 0.8 (band edge)
            100.0: 3,  # ratio 1.0 (band edge)
            110.0: 2,  # ratio 1.1
            125.0: 2,  # ratio 1.25 (band edge)
            130.0: 1,  # ratio 1.3 (beyond last band)
            500.0: 1,  # ratio 5.0
        }
        for measured, expected in cases.items():
            with self.subTest(measured=measured):
                self.assertEqual(
                    OperationalScorer.score_ratio(measured, 100.0), expected
                )

    def test_worst_band_uses_criterion_min_score(self) -> None:
        self.assertEqual(
            OperationalScorer.score_ratio(1000.0, 100.0),
            constants.CRITERION_MIN_SCORE,
        )


class OperationalScorerHappyPathTest(unittest.TestCase):
    def test_scores_all_criteria_from_object_payload(self) -> None:
        scorer = OperationalScorer(slo=FULL_SLO)

        result = scorer.score({"traces": [SINGLE_TRACE], "pricing": PRICING})
        criteria = by_id(result)

        self.assertEqual(criteria["end_to_end_latency"]["score"], 2)  # 1200/1000
        self.assertEqual(criteria["time_to_first_token"]["score"], 4)  # 300/500
        self.assertEqual(criteria["cost_per_request"]["score"], 4)  # 0.006/0.01
        self.assertEqual(criteria["error_failure_rate"]["score"], 5)  # 0.0/0.02
        self.assertEqual(criteria["latency_under_load"]["score"], 2)  # fallback 1200
        self.assertIsNone(criteria["token_efficiency"]["score"])

    def test_list_payload_cannot_measure_cost_without_pricing(self) -> None:
        scorer = OperationalScorer(slo=FULL_SLO)

        criteria = by_id(scorer.score([SINGLE_TRACE]))

        # Latency-based criteria still score; cost needs pricing to be measured.
        self.assertEqual(criteria["end_to_end_latency"]["score"], 2)
        self.assertIsNone(criteria["cost_per_request"]["score"])

    def test_pillar_score_matches_scoring_model(self) -> None:
        scorer = OperationalScorer(slo=FULL_SLO)

        result = scorer.score({"traces": [SINGLE_TRACE], "pricing": PRICING})

        # mean([2, 4, 4, 5, 2]) * 2 = 6.8
        self.assertEqual(result["pillar_score"], 6.8)

    def test_object_payload_with_pricing_scores_cost(self) -> None:
        scorer = OperationalScorer(slo=FULL_SLO)

        result = scorer.score({"traces": [SINGLE_TRACE], "pricing": PRICING})
        criteria = by_id(result)

        self.assertEqual(criteria["cost_per_request"]["score"], 4)
        self.assertIn("0.006", criteria["cost_per_request"]["evidence"])

    def test_criteria_preserve_rubric_order_and_names(self) -> None:
        scorer = OperationalScorer(slo=FULL_SLO)

        result = scorer.score([SINGLE_TRACE])
        ids = [criterion["id"] for criterion in result["criteria"]]

        self.assertEqual(
            ids,
            [
                "end_to_end_latency",
                "time_to_first_token",
                "cost_per_request",
                "token_efficiency",
                "error_failure_rate",
                "latency_under_load",
            ],
        )
        self.assertEqual(
            by_id(result)["end_to_end_latency"]["name"], "End-to-End Latency"
        )


class LatencyUnderLoadTest(unittest.TestCase):
    def test_uses_max_p95_across_load_groups_not_overall_latency(self) -> None:
        # Two concurrency groups (1000 ms @1, 3000 ms @10) plus a slow request
        # with no concurrency (5000 ms) that lifts the *overall* p95 to 5000.
        traces = [
            {"request_started_at": 0, "response_completed_at": 1, "concurrency": 1},
            {"request_started_at": 0, "response_completed_at": 3, "concurrency": 10},
            {"request_started_at": 0, "response_completed_at": 5},
        ]
        scorer = OperationalScorer(slo={constants.SLO_P95_LATENCY_MS: 4000.0})

        result = scorer.score(traces)
        criteria = by_id(result)

        # end_to_end uses overall p95 = 5000 -> ratio 1.25 -> score 2.
        self.assertEqual(criteria["end_to_end_latency"]["score"], 2)
        # under_load uses max load-group p95 = 3000 -> ratio 0.75 -> score 4.
        self.assertEqual(criteria["latency_under_load"]["score"], 4)
        # Only these two SLO fields are configured; the rest are unscored.
        self.assertIsNone(criteria["time_to_first_token"]["score"])
        self.assertIsNone(criteria["cost_per_request"]["score"])
        self.assertIsNone(criteria["error_failure_rate"]["score"])
        self.assertEqual(result["pillar_score"], 6.0)  # mean([2, 4]) * 2


class MissingAndEmptyInputTest(unittest.TestCase):
    def test_absent_slo_field_leaves_criterion_unscored(self) -> None:
        scorer = OperationalScorer(slo={constants.SLO_P95_LATENCY_MS: 1000.0})

        criteria = by_id(scorer.score([SINGLE_TRACE]))

        self.assertEqual(criteria["end_to_end_latency"]["score"], 2)
        self.assertIsNone(criteria["time_to_first_token"]["score"])
        self.assertIsNone(criteria["cost_per_request"]["score"])
        self.assertIn("not scored", criteria["time_to_first_token"]["evidence"])

    def test_no_slo_configured_scores_nothing(self) -> None:
        scorer = OperationalScorer()

        result = scorer.score([SINGLE_TRACE])

        self.assertTrue(
            all(criterion["score"] is None for criterion in result["criteria"])
        )
        self.assertIsNone(result["pillar_score"])

    def test_empty_traces_only_scores_failure_rate(self) -> None:
        scorer = OperationalScorer(slo=FULL_SLO)

        result = scorer.score([])
        criteria = by_id(result)

        # No completed requests: latency/ttft/cost cannot be measured.
        self.assertIsNone(criteria["end_to_end_latency"]["score"])
        self.assertIsNone(criteria["time_to_first_token"]["score"])
        self.assertIsNone(criteria["cost_per_request"]["score"])
        self.assertIsNone(criteria["latency_under_load"]["score"])
        # An empty trace set has a 0.0 failure rate, which meets any target.
        self.assertEqual(criteria["error_failure_rate"]["score"], 5)
        self.assertEqual(result["pillar_score"], 10.0)  # mean([5]) * 2

    def test_missing_cost_reports_no_measured_value(self) -> None:
        # No pricing -> average_cost_usd is None even though a target exists.
        scorer = OperationalScorer(slo={constants.SLO_MAX_COST_USD: 0.01})

        criteria = by_id(scorer.score([SINGLE_TRACE]))

        self.assertIsNone(criteria["cost_per_request"]["score"])
        self.assertIn(
            "no measured value", criteria["cost_per_request"]["evidence"]
        )


class EvidenceTest(unittest.TestCase):
    def test_scored_evidence_states_measured_and_target(self) -> None:
        scorer = OperationalScorer(slo=FULL_SLO)

        criteria = by_id(scorer.score([SINGLE_TRACE]))
        evidence = criteria["end_to_end_latency"]["evidence"]

        self.assertIn("1200", evidence)  # measured
        self.assertIn("1000", evidence)  # target
        self.assertIn(constants.SLO_P95_LATENCY_MS, evidence)
        self.assertIn("2/5", evidence)  # score/max

    def test_token_efficiency_evidence_notes_no_slo(self) -> None:
        scorer = OperationalScorer(slo=FULL_SLO)

        criteria = by_id(scorer.score([SINGLE_TRACE]))
        evidence = criteria["token_efficiency"]["evidence"]

        self.assertIn("no SLO", evidence)
        self.assertIn("not scored", evidence)


class ConstructorValidationTest(unittest.TestCase):
    def test_rejects_non_mapping_slo(self) -> None:
        with self.assertRaises(TypeError):
            OperationalScorer(slo=[1, 2, 3])  # type: ignore[arg-type]

    def test_rejects_unknown_slo_field(self) -> None:
        with self.assertRaises(ValueError):
            OperationalScorer(slo={"unknown_field": 1.0})

    def test_rejects_non_numeric_target(self) -> None:
        with self.assertRaises(TypeError):
            OperationalScorer(slo={constants.SLO_P95_LATENCY_MS: "fast"})

    def test_rejects_boolean_target(self) -> None:
        with self.assertRaises(TypeError):
            OperationalScorer(slo={constants.SLO_P95_LATENCY_MS: True})

    def test_rejects_non_finite_target(self) -> None:
        for bad in (inf, nan):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    OperationalScorer(slo={constants.SLO_P95_LATENCY_MS: bad})

    def test_does_not_mutate_input_slo(self) -> None:
        original = {constants.SLO_P95_LATENCY_MS: 1000.0}
        OperationalScorer(slo=original)

        self.assertEqual(original, {constants.SLO_P95_LATENCY_MS: 1000.0})


class PayloadValidationTest(unittest.TestCase):
    def test_rejects_non_list_non_mapping_payload(self) -> None:
        scorer = OperationalScorer(slo=FULL_SLO)
        with self.assertRaises(TypeError):
            scorer.score("not-a-payload")

    def test_rejects_mapping_without_traces_list(self) -> None:
        scorer = OperationalScorer(slo=FULL_SLO)
        with self.assertRaises(ValueError):
            scorer.score({"pricing": PRICING})

    def test_rejects_pricing_missing_required_field(self) -> None:
        scorer = OperationalScorer(slo=FULL_SLO)
        with self.assertRaises(ValueError):
            scorer.score(
                {"traces": [SINGLE_TRACE], "pricing": {"input_per_million": 2.0}}
            )


class ValueObjectTest(unittest.TestCase):
    def test_criterion_score_to_dict_shape(self) -> None:
        criterion = CriterionScore(
            id="end_to_end_latency", name="End-to-End Latency", score=3, evidence="ok"
        )

        self.assertEqual(
            criterion.to_dict(),
            {
                "id": "end_to_end_latency",
                "name": "End-to-End Latency",
                "score": 3,
                "evidence": "ok",
            },
        )

    def test_operational_score_to_dict_shape(self) -> None:
        criterion = CriterionScore("cost_per_request", "Cost per Request", None, "n/a")
        score = OperationalScore(criteria=(criterion,), pillar_score=None)

        self.assertEqual(
            score.to_dict(),
            {
                "criteria": [criterion.to_dict()],
                "pillar_score": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
