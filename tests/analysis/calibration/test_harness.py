"""Tests for harness-invariant judgment reliability (design: docs/design/harness-invariance.md).

The anchor fixture is constructed from known model effects so the estimators
must recover them exactly (model-recovery validation):

    mu = 6; targets tau = (+2, 0, -2); harnesses eta = (+0.5, -0.5);
    interaction (tau*eta) = A:(+0.5, -0.5), B:(-0.5, +0.5), C:(0, 0);
    replications = cell mean +/- 0.5.

    Scores:            claude-code      cursor
        target-a       9.5, 8.5         7.5, 6.5
        target-b       6.5, 5.5         6.5, 5.5
        target-c       5.0, 4.0         4.0, 3.0

    Hand-computed ANOVA (n_t=3, n_h=2, n_r=2):
        cell means: a: 9, 7 | b: 6, 6 | c: 4.5, 3.5
        target means 8, 6, 4; harness means 6.5, 5.5; grand mean 6
        SS_t = 4 * [(8-6)^2 + 0 + (4-6)^2] = 32          -> MS_t = 16
        SS_h = 6 * [(0.5)^2 + (0.5)^2]    = 3            -> MS_h = 3
        SS_th (interaction residuals +/-0.5, +/-0.5, 0)  = 2 -> MS_th = 1
        SS_e = 6 cells * (0.5^2 + 0.5^2)  = 3            -> MS_e = 0.5
        sigma2_e  = 0.5
        sigma2_th = (1 - 0.5) / 2        = 0.25
        sigma2_h  = (3 - 1) / (3 * 2)    = 1/3   -> 0.333
        sigma2_t  = (16 - 1) / (2 * 2)   = 3.75
        shares (total 29/6): 0.776 / 0.069 / 0.052 / 0.103

    Coefficients at the observed design (n_h'=2, n_r'=2):
        rel err = 0.25/2 + 0.5/4               = 0.25   -> Erho2 = 3.75/4    = 0.938
        abs err = (1/3)/2 + 0.25/2 + 0.5/4     = 5/12   -> Phi   = 3.75/(3.75+5/12) = 0.9
        Phi(6.5) = (3.75 + 0.25) / (4 + 5/12)  = 0.906
        Phi(8.0) = (3.75 + 4.0)  / (8.166667)  = 0.949
    D-study (1,1): rel 0.75 -> 0.833; abs 13/12 -> 0.776 (= target share, as it must)
    Recommended for 0.8 (fewest total runs, tie -> fewer harnesses):
        (1,2): abs = 1/3 + 0.25 + 0.25 = 5/6 -> Phi = 3.75/(3.75+5/6) = 0.818  [2 runs]
    Fixed-facet: (3.75 + 0.25/2) / (3.875 + 0.5/4) = 3.875/4.0 = 0.969
"""

from __future__ import annotations

import copy
import unittest

import evalsurfer.constants as constants
from evalsurfer.analysis.calibration.harness import HarnessInvariance, VarianceComponents


def _j(target, harness, rep, score, decision=None, criteria=None) -> dict:
    """Build a slim judgment record."""
    report: dict = {"score": score}
    if decision is not None:
        report["decision"] = decision
    if criteria is not None:
        report["criteria"] = criteria
    return {"target": target, "harness": harness, "replication": rep, "report": report}


_ANCHOR_SCORES = {
    ("target-a", "claude-code"): (9.5, 8.5),
    ("target-a", "cursor"): (7.5, 6.5),
    ("target-b", "claude-code"): (6.5, 5.5),
    ("target-b", "cursor"): (6.5, 5.5),
    ("target-c", "claude-code"): (5.0, 4.0),
    ("target-c", "cursor"): (4.0, 3.0),
}


def _anchor_payload(criteria_by_cell=None) -> dict:
    judgments = []
    for (target, harness), scores in _ANCHOR_SCORES.items():
        for rep, score in enumerate(scores, start=1):
            crit = criteria_by_cell.get((target, harness)) if criteria_by_cell else None
            judgments.append(_j(target, harness, rep, score, criteria=crit))
    return {"judgments": judgments}


class AnchorFixtureTest(unittest.TestCase):
    """Model-recovery: the estimators recover the constructed effects exactly."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.result = HarnessInvariance.analyze(_anchor_payload())

    def test_design_summary(self) -> None:
        self.assertEqual(
            self.result["design"],
            {"targets": 3, "harnesses": 2, "replications": 2, "balanced": True, "confounded": False},
        )

    def test_grand_mean(self) -> None:
        self.assertEqual(self.result["grand_mean"], 6.0)

    def test_variance_components(self) -> None:
        self.assertEqual(
            self.result["variance_components"],
            {
                "target": 3.75,
                "harness": 0.333,
                "interaction": 0.25,
                "replication": 0.5,
                "residual": None,
                "clamped": [],
            },
        )

    def test_shares(self) -> None:
        self.assertEqual(
            self.result["shares"],
            {"target": 0.776, "harness": 0.069, "interaction": 0.052, "replication": 0.103},
        )

    def test_coefficients(self) -> None:
        self.assertEqual(
            self.result["coefficients"],
            {
                "generalizability": 0.938,
                "dependability": 0.9,
                "dependability_at_cuts": {"6.5": 0.906, "8.0": 0.949},
                "icc_2_1": None,
            },
        )

    def test_dstudy_grid(self) -> None:
        dstudy = self.result["dstudy"]
        self.assertEqual(
            len(dstudy),
            constants.DSTUDY_MAX_HARNESSES * constants.DSTUDY_MAX_REPLICATIONS,
        )
        self.assertEqual(
            dstudy[0],
            {"harnesses": 1, "replications": 1, "generalizability": 0.833, "dependability": 0.776},
        )
        # At (1, 1) the dependability equals the target share by definition.
        self.assertEqual(dstudy[0]["dependability"], self.result["shares"]["target"])

    def test_recommended(self) -> None:
        self.assertEqual(
            self.result["recommended"],
            {"harnesses": 1, "replications": 2, "dependability": 0.818, "target": 0.8},
        )

    def test_no_decisions_or_criteria(self) -> None:
        self.assertIsNone(self.result["decisions"])
        self.assertEqual(self.result["criteria"], [])

    def test_harness_diagnostics(self) -> None:
        diagnostics = self.result["harness_diagnostics"]
        self.assertEqual(diagnostics["per_harness_mean"], {"claude-code": 6.5, "cursor": 5.5})
        # Both harnesses rank a > b > c: mean pairwise Spearman rho is 1.0.
        self.assertEqual(diagnostics["mean_rank_correlation"], 1.0)
        self.assertEqual(
            diagnostics["rank_correlation_pairs"], {"defined": 1, "total": 1}
        )
        self.assertEqual(diagnostics["fixed_facet_dependability"], 0.969)
        self.assertIsInstance(diagnostics["note"], str)

    def test_notes_carry_only_the_cut_score_caveat(self) -> None:
        # Not confounded, recommendation found, all rank pairs defined: the only
        # note is the estimated-mean optimism caveat on dependability_at_cuts.
        notes = self.result["notes"]
        self.assertEqual(len(notes), 1)
        self.assertIn("optimistic", notes[0])

    def test_decompose_direct(self) -> None:
        components = HarnessInvariance.decompose(
            {cell: list(scores) for cell, scores in _ANCHOR_SCORES.items()}
        )
        self.assertIsInstance(components, VarianceComponents)
        self.assertAlmostEqual(components.target, 3.75, places=9)
        self.assertAlmostEqual(components.harness, 1 / 3, places=9)
        self.assertAlmostEqual(components.interaction, 0.25, places=9)
        self.assertAlmostEqual(components.replication, 0.5, places=9)
        self.assertFalse(components.confounded)

    def test_input_not_mutated(self) -> None:
        payload = _anchor_payload()
        snapshot = copy.deepcopy(payload)
        HarnessInvariance.analyze(payload)
        self.assertEqual(payload, snapshot)


class ConfoundedModeTest(unittest.TestCase):
    """n_r = 1: interaction and replication noise are confounded into a residual.

    Scores (perfectly additive): a: 8, 7 | b: 6, 5 | c: 4, 3.
    Two-way ANOVA without replication: MS_t = 8, MS_h = 1.5, MS_res = 0.
    sigma2_res = 0; sigma2_h = 1.5/3 = 0.5; sigma2_t = 8/2 = 4; grand mean 5.5.
    ICC(2,1) agreement = 4 / (4 + 0.5 + 0) = 0.889.
    Coefficients at n_h'=2: rel 0 -> Erho2 = 1.0; abs 0.25 -> Phi = 0.941.
    Phi(6.5) = (4+1)/(5.25) = 0.952; Phi(8.0) = (4+6.25)/(10.5) = 0.976.
    Recommended: (1, -): Phi = 4/4.5 = 0.889 >= 0.8.
    """

    @classmethod
    def setUpClass(cls) -> None:
        judgments = [
            _j("a", "cc", 1, 8), _j("a", "cu", 1, 7),
            _j("b", "cc", 1, 6), _j("b", "cu", 1, 5),
            _j("c", "cc", 1, 4), _j("c", "cu", 1, 3),
        ]
        cls.result = HarnessInvariance.analyze({"judgments": judgments})

    def test_design_flags_confounded(self) -> None:
        self.assertTrue(self.result["design"]["confounded"])
        self.assertEqual(self.result["design"]["replications"], 1)

    def test_components_confounded_shape(self) -> None:
        self.assertEqual(
            self.result["variance_components"],
            {
                "target": 4.0,
                "harness": 0.5,
                "interaction": None,
                "replication": None,
                "residual": 0.0,
                "clamped": [],
            },
        )

    def test_shares_use_residual(self) -> None:
        self.assertEqual(
            self.result["shares"], {"target": 0.889, "harness": 0.111, "residual": 0.0}
        )

    def test_icc_2_1_correspondence(self) -> None:
        self.assertEqual(self.result["coefficients"]["icc_2_1"], 0.889)

    def test_coefficients(self) -> None:
        coefficients = self.result["coefficients"]
        self.assertEqual(coefficients["generalizability"], 1.0)
        self.assertEqual(coefficients["dependability"], 0.941)
        self.assertEqual(
            coefficients["dependability_at_cuts"], {"6.5": 0.952, "8.0": 0.976}
        )

    def test_dstudy_has_no_replication_axis(self) -> None:
        dstudy = self.result["dstudy"]
        self.assertEqual(len(dstudy), constants.DSTUDY_MAX_HARNESSES)
        self.assertTrue(all(point["replications"] is None for point in dstudy))
        self.assertEqual(dstudy[0]["dependability"], 0.889)

    def test_recommended(self) -> None:
        self.assertEqual(
            self.result["recommended"],
            {"harnesses": 1, "replications": None, "dependability": 0.889, "target": 0.8},
        )

    def test_fixed_facet_needs_replications(self) -> None:
        self.assertIsNone(self.result["harness_diagnostics"]["fixed_facet_dependability"])

    def test_notes_explain_the_confounding(self) -> None:
        notes = self.result["notes"]
        self.assertTrue(any("confounded into 'residual'" in note for note in notes))
        # Target variance exists, so the cut-score caveat is also present.
        self.assertTrue(any("optimistic" in note for note in notes))


class ZeroSignalTest(unittest.TestCase):
    """All scores identical: no target variance, so coefficients are undefined."""

    @classmethod
    def setUpClass(cls) -> None:
        judgments = [
            _j(target, harness, rep, 7.0)
            for target in ("a", "b")
            for harness in ("cc", "cu")
            for rep in (1, 2)
        ]
        cls.result = HarnessInvariance.analyze({"judgments": judgments})

    def test_components_all_zero(self) -> None:
        components = self.result["variance_components"]
        self.assertEqual(components["target"], 0.0)
        self.assertEqual(components["harness"], 0.0)

    def test_undefined_outputs_are_null_not_perfect(self) -> None:
        self.assertIsNone(self.result["shares"])
        self.assertIsNone(self.result["coefficients"])
        self.assertIsNone(self.result["recommended"])
        self.assertEqual(self.result["dstudy"], [])

    def test_notes_explain_the_undefined_outputs(self) -> None:
        notes = self.result["notes"]
        self.assertTrue(any("no target variance" in note for note in notes))
        # Constant scores also leave every rank-correlation pair undefined.
        self.assertTrue(any("rank correlation is undefined" in note for note in notes))
        self.assertEqual(
            self.result["harness_diagnostics"]["rank_correlation_pairs"],
            {"defined": 0, "total": 1},
        )


class ClampTest(unittest.TestCase):
    """A negative interaction estimate is clamped to zero and reported.

    Scores: a: (9,7),(8,6) | b: (6,6),(6,4) | c: (5,3),(2,2).
    MS_t = 20.333, MS_h = 5.333, MS_th = 0.333, MS_e = 1.333.
    sigma2_th = (0.333 - 1.333)/2 = -0.5 -> clamped to 0.
    sigma2_e = 1.333; sigma2_h = 5/6 = 0.833; sigma2_t = 20/4 = 5.0.
    """

    def test_negative_component_clamped_and_listed(self) -> None:
        judgments = [
            _j("a", "h1", 1, 9), _j("a", "h1", 2, 7),
            _j("a", "h2", 1, 8), _j("a", "h2", 2, 6),
            _j("b", "h1", 1, 6), _j("b", "h1", 2, 6),
            _j("b", "h2", 1, 6), _j("b", "h2", 2, 4),
            _j("c", "h1", 1, 5), _j("c", "h1", 2, 3),
            _j("c", "h2", 1, 2), _j("c", "h2", 2, 2),
        ]
        result = HarnessInvariance.analyze({"judgments": judgments})
        components = result["variance_components"]
        self.assertEqual(components["interaction"], 0.0)
        self.assertEqual(components["clamped"], ["interaction"])
        self.assertEqual(components["target"], 5.0)
        self.assertEqual(components["harness"], 0.833)
        self.assertEqual(components["replication"], 1.333)


class UnattainableRecommendationTest(unittest.TestCase):
    """Huge run noise: no D-study point reaches the target, with the reason noted.

    a: both harnesses (9, 1) -> cell means 5; b: both harnesses (10, 4) -> 7.
    MS_t = 8, MS_h = 0, MS_th = 0, MS_e = 25 -> sigma2_t = 2, sigma2_h = 0,
    sigma2_th = (0-25)/2 clamped, sigma2_e = 25. Best grid point (5,5):
    Phi = 2 / (2 + 25/25) = 0.667 < 0.8 -> no recommendation.
    """

    @classmethod
    def setUpClass(cls) -> None:
        judgments = [
            _j("a", "h1", 1, 9), _j("a", "h1", 2, 1),
            _j("a", "h2", 1, 9), _j("a", "h2", 2, 1),
            _j("b", "h1", 1, 10), _j("b", "h1", 2, 4),
            _j("b", "h2", 1, 10), _j("b", "h2", 2, 4),
        ]
        cls.result = HarnessInvariance.analyze({"judgments": judgments})

    def test_recommendation_is_null_with_a_reason_in_notes(self) -> None:
        self.assertIsNone(self.result["recommended"])
        notes = self.result["notes"]
        self.assertTrue(
            any("reaches the dependability target 0.8" in note for note in notes)
        )

    def test_best_grid_point_confirms_the_shortfall(self) -> None:
        best = max(point["dependability"] for point in self.result["dstudy"])
        self.assertEqual(best, 0.667)


class DecisionAnalysisTest(unittest.TestCase):
    """Decision flips attributed within vs between harnesses.

    t1: cc (pass, pass), cu (pwf, pwf); t2: cc (pass, pass), cu (pass, pass);
    t3: cc (pass, fail), cu (pass, pass).
    Per-harness modals (tie -> most severe): t1 cc pass / cu pwf; t2 pass/pass;
    t3 cc fail (tie) / cu pass. Fleiss over those: kappa = -0.333.
    Overall modals: t1 pwf (2-2 tie -> severe), flips 0.5; t2 pass, 0;
    t3 pass, 0.25 -> mean 0.25.
    Within-harness rep pairs: 6, differing 1 (t3 cc) -> 0.167.
    Between-harness pairs: 12, differing t1: 4, t3: 2 -> 0.5.
    Rank correlation: cc target means (9, 9.5, 6.75), cu (7, 9, 8.5) -> rho 0.5.
    """

    @classmethod
    def setUpClass(cls) -> None:
        pass_ = constants.DECISION_PASS
        pwf = constants.DECISION_PASS_WITH_FIXES
        fail = constants.DECISION_FAIL
        judgments = [
            _j("t1", "cc", 1, 9.0, pass_), _j("t1", "cc", 2, 9.0, pass_),
            _j("t1", "cu", 1, 7.0, pwf), _j("t1", "cu", 2, 7.0, pwf),
            _j("t2", "cc", 1, 9.5, pass_), _j("t2", "cc", 2, 9.5, pass_),
            _j("t2", "cu", 1, 9.0, pass_), _j("t2", "cu", 2, 9.0, pass_),
            _j("t3", "cc", 1, 8.5, pass_), _j("t3", "cc", 2, 5.0, fail),
            _j("t3", "cu", 1, 8.5, pass_), _j("t3", "cu", 2, 8.5, pass_),
        ]
        cls.result = HarnessInvariance.analyze({"judgments": judgments})

    def test_fleiss_kappa_over_per_harness_modals(self) -> None:
        self.assertEqual(self.result["decisions"]["fleiss_kappa"], -0.333)

    def test_flip_rates(self) -> None:
        decisions = self.result["decisions"]
        self.assertEqual(decisions["mean_flip_rate"], 0.25)
        self.assertEqual(decisions["p_flip_within_harness"], 0.167)
        self.assertEqual(decisions["p_flip_between_harness"], 0.5)
        self.assertEqual(decisions["invalid_decisions"], 0)
        self.assertEqual(decisions["invalid"], [])

    def test_per_target_modals_tie_breaks_to_most_severe(self) -> None:
        per_target = {entry["target"]: entry for entry in self.result["decisions"]["per_target"]}
        self.assertEqual(per_target["t1"]["modal"], constants.DECISION_PASS_WITH_FIXES)
        self.assertEqual(per_target["t1"]["flip_rate"], 0.5)
        self.assertEqual(per_target["t2"]["modal"], constants.DECISION_PASS)
        self.assertEqual(per_target["t2"]["flip_rate"], 0.0)
        self.assertEqual(per_target["t3"]["modal"], constants.DECISION_PASS)
        self.assertEqual(per_target["t3"]["flip_rate"], 0.25)

    def test_weighted_flip_distinguishes_band_distance(self) -> None:
        # t1's flips are adjacent (pass vs modal pwf: distance 1 each over 4
        # judgments -> 0.5); t3's single flip is fail vs modal pass (distance 2
        # over 4 -> 0.5). Same weighted_flip from different shapes, while the
        # unweighted flip_rate (0.5 vs 0.25) cannot see the severity.
        per_target = {entry["target"]: entry for entry in self.result["decisions"]["per_target"]}
        self.assertEqual(per_target["t1"]["weighted_flip"], 0.5)
        self.assertEqual(per_target["t2"]["weighted_flip"], 0.0)
        self.assertEqual(per_target["t3"]["weighted_flip"], 0.5)

    def test_mean_rank_correlation(self) -> None:
        self.assertEqual(
            self.result["harness_diagnostics"]["mean_rank_correlation"], 0.5
        )

    def test_unknown_decision_is_excluded_and_named(self) -> None:
        judgments = [
            _j("a", "cc", 1, 8, "maybe"), _j("a", "cu", 1, 7, constants.DECISION_PASS),
            _j("b", "cc", 1, 6, constants.DECISION_PASS), _j("b", "cu", 1, 5, constants.DECISION_FAIL),
        ]
        result = HarnessInvariance.analyze({"judgments": judgments})
        decisions = result["decisions"]
        self.assertEqual(decisions["invalid_decisions"], 1)
        self.assertEqual(
            decisions["invalid"],
            [{"target": "a", "harness": "cc", "replication": 1, "decision": "maybe"}],
        )
        # The (a, cc) panel slot has no valid decision, so kappa is undefined.
        self.assertIsNone(decisions["fleiss_kappa"])
        # No replication pairs exist with n_r = 1.
        self.assertIsNone(decisions["p_flip_within_harness"])

    def test_non_string_decisions_are_counted_invalid_not_dropped(self) -> None:
        # A producer emitting numeric decision codes must not read as "no
        # decisions supplied": each is preserved via str() and named invalid.
        judgments = [
            _j("a", "cc", 1, 8, 1), _j("a", "cu", 1, 7, 1),  # type: ignore[arg-type]
            _j("b", "cc", 1, 6, 0), _j("b", "cu", 1, 5, 0),  # type: ignore[arg-type]
        ]
        result = HarnessInvariance.analyze({"judgments": judgments})
        decisions = result["decisions"]
        self.assertIsNotNone(decisions)
        self.assertEqual(decisions["invalid_decisions"], 4)
        self.assertEqual(decisions["invalid"][0]["decision"], "1")
        self.assertIsNone(decisions["fleiss_kappa"])


class CriterionProfileTest(unittest.TestCase):
    """Per-criterion decomposition, sensitivity flag, and subgrid bookkeeping.

    groundedness_faithfulness (harness-sensitive by construction):
        a: cc 5, cu 2 | b: cc 4, cu 2 | c: cc 5, cu 3 (both reps identical)
        sigma2_e = 0; sigma2_th = 1/6; sigma2_h = 8/3; sigma2_t = 1/6
        shares: target 0.056, harness 0.889, interaction 0.056, replication 0.0
        harness + interaction = 0.944 > 0.25 -> sensitive.
    correctness_accuracy: a 5s, b 3s, c 4s everywhere -> target share 1.0 -> not sensitive.
    citation_accuracy: assessed on a and b only (c null) -> dropped_targets 1, profiled.
    tool_selection: assessed on a only -> 1 target < 2 -> skipped.
    """

    @classmethod
    def setUpClass(cls) -> None:
        grounded = {"claude-code": 5, "cursor": 2}
        grounded_b = {"claude-code": 4, "cursor": 2}
        grounded_c = {"claude-code": 5, "cursor": 3}
        criteria_by_cell = {
            ("target-a", "claude-code"): {
                "groundedness_faithfulness": grounded["claude-code"],
                "correctness_accuracy": 5,
                "citation_accuracy": 4,
                "tool_selection": 4,
            },
            ("target-a", "cursor"): {
                "groundedness_faithfulness": grounded["cursor"],
                "correctness_accuracy": 5,
                "citation_accuracy": 4,
                "tool_selection": 4,
            },
            ("target-b", "claude-code"): {
                "groundedness_faithfulness": grounded_b["claude-code"],
                "correctness_accuracy": 3,
                "citation_accuracy": 2,
                "tool_selection": None,
            },
            ("target-b", "cursor"): {
                "groundedness_faithfulness": grounded_b["cursor"],
                "correctness_accuracy": 3,
                "citation_accuracy": 2,
                "tool_selection": None,
            },
            ("target-c", "claude-code"): {
                "groundedness_faithfulness": grounded_c["claude-code"],
                "correctness_accuracy": 4,
                "citation_accuracy": None,
                "tool_selection": None,
            },
            ("target-c", "cursor"): {
                "groundedness_faithfulness": grounded_c["cursor"],
                "correctness_accuracy": 4,
                "citation_accuracy": None,
                "tool_selection": None,
            },
        }
        result = HarnessInvariance.analyze(_anchor_payload(criteria_by_cell))
        cls.profiles = {entry["id"]: entry for entry in result["criteria"]}

    def test_criteria_sorted_by_id(self) -> None:
        self.assertEqual(
            list(self.profiles),
            sorted(self.profiles),
        )

    def test_harness_sensitive_criterion_flagged(self) -> None:
        profile = self.profiles["groundedness_faithfulness"]
        self.assertTrue(profile["harness_sensitive"])
        self.assertEqual(profile["shares"]["harness"], 0.889)
        self.assertEqual(profile["dropped_targets"], 0)

    def test_target_driven_criterion_not_flagged(self) -> None:
        profile = self.profiles["correctness_accuracy"]
        self.assertFalse(profile["harness_sensitive"])
        self.assertEqual(profile["shares"]["target"], 1.0)
        self.assertEqual(profile["dependability"], 1.0)

    def test_partial_assessment_drops_targets_but_profiles(self) -> None:
        profile = self.profiles["citation_accuracy"]
        self.assertEqual(profile["dropped_targets"], 1)
        self.assertFalse(profile["harness_sensitive"])

    def test_too_few_targets_is_skipped_with_reason(self) -> None:
        profile = self.profiles["tool_selection"]
        self.assertIn("skipped", profile)
        self.assertIn("2", profile["skipped"])
        self.assertEqual(profile["dropped_targets"], 2)


class ProjectionEquivalenceTest(unittest.TestCase):
    """Full reports and slim records produce identical analyses."""

    def test_full_report_equals_slim(self) -> None:
        def full(target, harness, rep, score, decision, criterion_score) -> dict:
            return {
                "target": target,
                "harness": harness,
                "replication": rep,
                "report": {
                    "overall": {"score": score, "decision": decision},
                    "metrics": {
                        "quality": {
                            "score": criterion_score * 2.0,
                            "criteria": [
                                {
                                    "id": "correctness_accuracy",
                                    "name": "Correctness / accuracy",
                                    "score": criterion_score,
                                    "evidence": "",
                                }
                            ],
                        }
                    },
                    "decision": decision,
                    "top_issues": [],
                },
            }

        def slim(target, harness, rep, score, decision, criterion_score) -> dict:
            return _j(
                target, harness, rep, score, decision,
                {"correctness_accuracy": criterion_score},
            )

        rows = [
            ("a", "cc", 1, 8.0, constants.DECISION_PASS, 4),
            ("a", "cc", 2, 8.0, constants.DECISION_PASS, 4),
            ("a", "cu", 1, 7.0, constants.DECISION_PASS_WITH_FIXES, 4),
            ("a", "cu", 2, 7.0, constants.DECISION_PASS_WITH_FIXES, 3),
            ("b", "cc", 1, 6.0, constants.DECISION_PASS_WITH_FIXES, 3),
            ("b", "cc", 2, 6.0, constants.DECISION_PASS_WITH_FIXES, 3),
            ("b", "cu", 1, 5.0, constants.DECISION_FAIL, 2),
            ("b", "cu", 2, 5.0, constants.DECISION_FAIL, 2),
        ]
        full_result = HarnessInvariance.analyze({"judgments": [full(*row) for row in rows]})
        slim_result = HarnessInvariance.analyze({"judgments": [slim(*row) for row in rows]})
        self.assertEqual(full_result, slim_result)


class ValidationTest(unittest.TestCase):
    def _valid(self) -> list[dict]:
        return [
            _j("a", "cc", 1, 8), _j("a", "cu", 1, 7),
            _j("b", "cc", 1, 6), _j("b", "cu", 1, 5),
        ]

    def test_non_mapping_payload_raises(self) -> None:
        with self.assertRaises(TypeError):
            HarnessInvariance.analyze(["not", "a", "mapping"])  # type: ignore[arg-type]

    def test_judgments_must_be_a_sequence_of_mappings(self) -> None:
        with self.assertRaises(TypeError):
            HarnessInvariance.analyze({"judgments": "nope"})
        with self.assertRaises(TypeError):
            HarnessInvariance.analyze({"judgments": [1, 2]})

    def test_empty_judgments_raise(self) -> None:
        with self.assertRaises(ValueError):
            HarnessInvariance.analyze({"judgments": []})

    def test_unknown_top_level_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            HarnessInvariance.analyze(
                {"judgments": self._valid(), "dependability_targt": 0.9}
            )

    def test_too_few_targets_or_harnesses(self) -> None:
        one_target = [_j("a", "cc", 1, 8), _j("a", "cu", 1, 7)]
        one_harness = [_j("a", "cc", 1, 8), _j("b", "cc", 1, 6)]
        for judgments in (one_target, one_harness):
            with self.subTest(judgments=judgments):
                with self.assertRaises(ValueError):
                    HarnessInvariance.analyze({"judgments": judgments})

    def test_incomplete_grid_names_missing_cells(self) -> None:
        judgments = self._valid()[:-1]  # drop (b, cu)
        with self.assertRaisesRegex(ValueError, r"b.*cu"):
            HarnessInvariance.analyze({"judgments": judgments})

    def test_unequal_replications_raise(self) -> None:
        judgments = self._valid() + [_j("a", "cc", 2, 8)]
        with self.assertRaisesRegex(ValueError, "replication"):
            HarnessInvariance.analyze({"judgments": judgments})

    def test_duplicate_key_raises(self) -> None:
        judgments = self._valid() + [_j("a", "cc", 1, 9)]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            HarnessInvariance.analyze({"judgments": judgments})

    def test_invalid_identity_fields_raise(self) -> None:
        bad_rows = (
            {"target": "", "harness": "cc", "replication": 1, "report": {"score": 8}},
            {"target": "a", "harness": "", "replication": 1, "report": {"score": 8}},
            {"target": "a", "harness": "cc", "replication": 0, "report": {"score": 8}},
            {"target": "a", "harness": "cc", "replication": True, "report": {"score": 8}},
        )
        for row in bad_rows:
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    HarnessInvariance.analyze({"judgments": [row] + self._valid()[1:]})

    def test_invalid_scores_raise_naming_the_judgment(self) -> None:
        for bad_score in (None, "high", True, -1, 11):
            with self.subTest(bad_score=bad_score):
                judgments = [_j("a", "cc", 1, bad_score)] + self._valid()[1:]
                with self.assertRaisesRegex(ValueError, "a.*cc"):
                    HarnessInvariance.analyze({"judgments": judgments})

    def test_invalid_criterion_scores_raise(self) -> None:
        for bad in (0, 6, "x", True):
            with self.subTest(bad=bad):
                judgments = [
                    _j("a", "cc", 1, 8, criteria={"correctness_accuracy": bad})
                ] + self._valid()[1:]
                with self.assertRaises(ValueError):
                    HarnessInvariance.analyze({"judgments": judgments})

    def test_invalid_options_raise(self) -> None:
        for options in (
            {"dependability_target": 1.5},
            {"dependability_target": 0},
            {"dstudy_max_harnesses": 0},
            {"dstudy_max_replications": -1},
            # Caps are bounded: the D-study grid is materialized, so unbounded
            # caller-supplied caps would allocate without limit.
            {"dstudy_max_harnesses": constants.DSTUDY_MAX_LIMIT + 1},
            {"dstudy_max_replications": 10_000_000},
        ):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    HarnessInvariance.analyze({"judgments": self._valid(), **options})

    def test_duplicate_criterion_id_across_report_sections_raises(self) -> None:
        # A full report carrying the same criterion id in two sections would
        # silently last-win in the per-criterion profile; it is rejected instead.
        report = {
            "overall": {"score": 8.0, "decision": constants.DECISION_PASS},
            "metrics": {
                "quality": {"score": 8.0, "criteria": [{"id": "acc", "score": 4}]}
            },
            "assurance": {
                "safety": {"score": 2.0, "criteria": [{"id": "acc", "score": 1}]}
            },
            "top_issues": [],
        }
        judgments = [
            {"target": "a", "harness": "cc", "replication": 1, "report": report}
        ] + self._valid()[1:]
        with self.assertRaisesRegex(ValueError, "acc"):
            HarnessInvariance.analyze({"judgments": judgments})


if __name__ == "__main__":
    unittest.main()
