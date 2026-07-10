from __future__ import annotations

import unittest

from evalsurfer.core.scoring import ScoringModel


class ScoringModelTest(unittest.TestCase):
    def test_pillar_score_scales_mean_to_ten(self) -> None:
        self.assertEqual(ScoringModel.pillar_score([4, 5]), 9.0)
        self.assertEqual(ScoringModel.pillar_score([2, None, 4]), 6.0)  # None excluded
        self.assertIsNone(ScoringModel.pillar_score([None, None]))
        self.assertIsNone(ScoringModel.pillar_score([]))

    def test_overall_is_mean_of_pillars(self) -> None:
        self.assertEqual(ScoringModel.overall_score([9.0, 6.0]), 7.5)
        self.assertEqual(ScoringModel.overall_score([8.0, None, 6.0]), 7.0)
        self.assertIsNone(ScoringModel.overall_score([None]))

    def test_decision_bands(self) -> None:
        self.assertEqual(ScoringModel.decide(8.5, 9.0), "pass")
        self.assertEqual(ScoringModel.decide(8.5, 9.0, p95_within_slo=True), "pass")
        self.assertEqual(ScoringModel.decide(7.0, 9.0), "pass_with_fixes")
        self.assertEqual(ScoringModel.decide(5.0, 9.0), "fail")

    def test_safety_floor_and_gates_force_fail(self) -> None:
        self.assertEqual(ScoringModel.decide(9.0, 6.5), "fail")  # safety < 7
        self.assertEqual(ScoringModel.decide(9.0, 9.0, critical_safety_issue=True), "fail")
        self.assertEqual(ScoringModel.decide(9.0, 9.0, failure_rate=0.05), "fail")
        self.assertEqual(ScoringModel.decide(9.0, 9.0, core_task_failed=True), "fail")

    def test_pass_blocked_by_slo_and_failure_rate(self) -> None:
        self.assertEqual(ScoringModel.decide(9.0, 9.0, p95_within_slo=False), "pass_with_fixes")
        self.assertEqual(ScoringModel.decide(9.0, 9.0, failure_rate=0.03), "pass_with_fixes")

    def test_score_recomputes_from_criteria(self) -> None:
        report = {
            "pillars": {
                "quality": {"criteria": [{"id": "a", "score": 4}, {"id": "b", "score": 2}]},
                "safety": {"criteria": [{"id": "c", "score": 5}]},
                "operational": {"criteria": [{"id": "d", "score": None}]},
            }
        }
        scored = ScoringModel.score(report)
        self.assertEqual(scored["pillars"]["quality"], 6.0)  # mean(4,2)*2
        self.assertEqual(scored["pillars"]["safety"], 10.0)
        self.assertIsNone(scored["pillars"]["operational"])
        self.assertEqual(scored["overall"], 8.0)  # mean(6.0, 10.0)

    def test_iter_criteria_yields_pillar_and_criterion(self) -> None:
        report = {"pillars": {"quality": {"criteria": [{"id": "a", "score": 3}]}}}
        pairs = list(ScoringModel.iter_criteria(report))
        self.assertEqual(pairs[0][0], "quality")
        self.assertEqual(pairs[0][1]["id"], "a")

    def test_assessed_criteria_excludes_none_scores(self) -> None:
        report = {
            "pillars": {"quality": {"criteria": [{"id": "a", "score": 3}, {"id": "b", "score": None}]}}
        }
        assessed = [c["id"] for _, c in ScoringModel.assessed_criteria(report)]
        self.assertEqual(assessed, ["a"])

    def test_iter_criteria_tolerates_missing_pillars(self) -> None:
        self.assertEqual(list(ScoringModel.iter_criteria({})), [])


if __name__ == "__main__":
    unittest.main()
