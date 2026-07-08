from __future__ import annotations

import copy
import unittest

from evalsurfer.diagnostics.root_cause import Contribution, RootCauseAnalyzer


def _report(pillars: dict) -> dict:
    """Wrap a ``{pillar: [criteria]}`` mapping into a minimal report dict."""

    return {"pillars": {pid: {"criteria": crits} for pid, crits in pillars.items()}}


class AttributeFailuresHappyPathTest(unittest.TestCase):
    def setUp(self) -> None:
        # quality lost 4 (core 3 + rag 1 + a perfect 5 worth 0),
        # safety lost 1, operational lost 2 (one criterion not assessed).
        self.report = _report(
            {
                "quality": [
                    {"id": "correctness_accuracy", "score": 2},  # core, lost 3
                    {"id": "context_relevance", "score": 4},  # rag, lost 1
                    {"id": "relevance", "score": 5},  # core, lost 0
                ],
                "safety": [
                    {"id": "toxicity", "score": 4},  # lost 1
                ],
                "operational": [
                    {"id": "end_to_end_latency", "score": 3},  # lost 2
                    {"id": "cost_per_request", "score": None},  # not assessed
                ],
            }
        )

    def test_total_lost_sums_five_minus_score(self) -> None:
        self.assertEqual(RootCauseAnalyzer.attribute(self.report)["total_lost"], 7)

    def test_by_pillar_ranked_with_shares(self) -> None:
        by_pillar = RootCauseAnalyzer.attribute(self.report)["by_pillar"]
        self.assertEqual(
            by_pillar,
            [
                {"pillar": "quality", "lost": 4, "share": 0.571},
                {"pillar": "operational", "lost": 2, "share": 0.286},
                {"pillar": "safety", "lost": 1, "share": 0.143},
            ],
        )

    def test_by_group_uses_rubric_groups_and_pillar_names(self) -> None:
        by_group = RootCauseAnalyzer.attribute(self.report)["by_group"]
        self.assertEqual(
            by_group,
            [
                {"group": "core_generation_quality", "lost": 3, "share": 0.429},
                {"group": "operational", "lost": 2, "share": 0.286},
                {"group": "rag_specific", "lost": 1, "share": 0.143},
                {"group": "safety", "lost": 1, "share": 0.143},
            ],
        )

    def test_top_contributor_is_biggest_pillar(self) -> None:
        self.assertEqual(RootCauseAnalyzer.attribute(self.report)["top_contributor"], "quality")

    def test_input_report_is_not_mutated(self) -> None:
        before = copy.deepcopy(self.report)
        RootCauseAnalyzer.attribute(self.report)
        self.assertEqual(self.report, before)


class AttributeFailuresMappingTest(unittest.TestCase):
    def test_canonical_pillar_overrides_report_placement(self) -> None:
        # toxicity is a safety criterion even if the report files it under quality.
        report = _report({"quality": [{"id": "toxicity", "score": 3}]})
        result = RootCauseAnalyzer.attribute(report)
        self.assertEqual(result["by_pillar"], [{"pillar": "safety", "lost": 2, "share": 1.0}])
        self.assertEqual(result["by_group"], [{"group": "safety", "lost": 2, "share": 1.0}])
        self.assertEqual(result["top_contributor"], "safety")

    def test_unknown_id_falls_back_to_report_pillar(self) -> None:
        report = _report({"quality": [{"id": "made_up_criterion", "score": 3}]})
        result = RootCauseAnalyzer.attribute(report)
        self.assertEqual(result["by_pillar"], [{"pillar": "quality", "lost": 2, "share": 1.0}])
        self.assertEqual(result["by_group"], [{"group": "quality", "lost": 2, "share": 1.0}])

    def test_missing_id_falls_back_to_report_pillar(self) -> None:
        report = _report({"operational": [{"score": 1}]})  # no id key
        result = RootCauseAnalyzer.attribute(report)
        self.assertEqual(result["by_pillar"], [{"pillar": "operational", "lost": 4, "share": 1.0}])

    def test_pillar_tie_breaks_alphabetically(self) -> None:
        report = _report(
            {
                "quality": [{"id": "correctness_accuracy", "score": 3}],  # lost 2
                "safety": [{"id": "toxicity", "score": 3}],  # lost 2
            }
        )
        by_pillar = RootCauseAnalyzer.attribute(report)["by_pillar"]
        self.assertEqual([entry["pillar"] for entry in by_pillar], ["quality", "safety"])
        self.assertEqual(RootCauseAnalyzer.attribute(report)["top_contributor"], "quality")


class AttributeFailuresEdgeCaseTest(unittest.TestCase):
    def test_nothing_lost_when_all_perfect(self) -> None:
        report = _report(
            {
                "quality": [{"id": "relevance", "score": 5}],
                "safety": [{"id": "toxicity", "score": 5}],
            }
        )
        result = RootCauseAnalyzer.attribute(report)
        self.assertEqual(result["total_lost"], 0)
        self.assertEqual(result["by_pillar"], [])
        self.assertEqual(result["by_group"], [])
        self.assertIsNone(result["top_contributor"])

    def test_zero_lost_pillar_is_excluded(self) -> None:
        report = _report(
            {
                "quality": [{"id": "correctness_accuracy", "score": 2}],  # lost 3
                "safety": [{"id": "toxicity", "score": 5}],  # lost 0
            }
        )
        by_pillar = RootCauseAnalyzer.attribute(report)["by_pillar"]
        self.assertEqual([entry["pillar"] for entry in by_pillar], ["quality"])

    def test_empty_report(self) -> None:
        result = RootCauseAnalyzer.attribute({})
        self.assertEqual(
            result,
            {"total_lost": 0, "by_pillar": [], "by_group": [], "top_contributor": None},
        )

    def test_missing_pillars_key_tolerated(self) -> None:
        self.assertEqual(RootCauseAnalyzer.attribute({"metadata": {"x": 1}})["total_lost"], 0)

    def test_all_none_scores_are_skipped(self) -> None:
        report = _report({"quality": [{"id": "relevance", "score": None}]})
        result = RootCauseAnalyzer.attribute(report)
        self.assertEqual(result["total_lost"], 0)
        self.assertIsNone(result["top_contributor"])

    def test_criterion_without_score_key_is_skipped(self) -> None:
        report = _report({"quality": [{"id": "relevance"}]})
        self.assertEqual(RootCauseAnalyzer.attribute(report)["total_lost"], 0)

    def test_lowest_score_loses_four_points(self) -> None:
        report = _report({"quality": [{"id": "relevance", "score": 1}]})
        result = RootCauseAnalyzer.attribute(report)
        self.assertEqual(result["total_lost"], 4)
        self.assertEqual(result["by_pillar"], [{"pillar": "quality", "lost": 4, "share": 1.0}])


class AttributeFailuresValidationTest(unittest.TestCase):
    def test_non_mapping_report_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            RootCauseAnalyzer.attribute(["not", "a", "mapping"])

    def test_score_below_range_raises_value_error(self) -> None:
        report = _report({"quality": [{"id": "relevance", "score": 0}]})
        with self.assertRaises(ValueError):
            RootCauseAnalyzer.attribute(report)

    def test_score_above_range_raises_value_error(self) -> None:
        report = _report({"quality": [{"id": "relevance", "score": 6}]})
        with self.assertRaises(ValueError):
            RootCauseAnalyzer.attribute(report)

    def test_boolean_score_raises_value_error(self) -> None:
        report = _report({"quality": [{"id": "relevance", "score": True}]})
        with self.assertRaises(ValueError):
            RootCauseAnalyzer.attribute(report)

    def test_non_integer_score_raises_value_error(self) -> None:
        report = _report({"quality": [{"id": "relevance", "score": "3"}]})
        with self.assertRaises(ValueError):
            RootCauseAnalyzer.attribute(report)


class ContributionTest(unittest.TestCase):
    def test_as_dict_uses_requested_key(self) -> None:
        contribution = Contribution(label="quality", lost=3, share=0.5)
        self.assertEqual(contribution.as_dict("pillar"), {"pillar": "quality", "lost": 3, "share": 0.5})
        self.assertEqual(contribution.as_dict("group"), {"group": "quality", "lost": 3, "share": 0.5})

    def test_contribution_is_frozen(self) -> None:
        contribution = Contribution(label="safety", lost=1, share=0.1)
        with self.assertRaises(Exception):
            contribution.lost = 2  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
