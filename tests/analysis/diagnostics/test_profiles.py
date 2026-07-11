from __future__ import annotations

import unittest

import evalsurfer.constants as constants
from evalsurfer.analysis.diagnostics.profiles import IndustryProfiler


class ProfilesPresetTest(unittest.TestCase):
    def test_every_preset_sums_to_one(self) -> None:
        for name, weights in constants.INDUSTRY_PROFILES.items():
            with self.subTest(profile=name):
                self.assertAlmostEqual(sum(weights.values()), 1.0, delta=1e-9)

    def test_every_preset_covers_the_three_categories(self) -> None:
        for name, weights in constants.INDUSTRY_PROFILES.items():
            with self.subTest(profile=name):
                self.assertEqual(set(weights), set(constants.CATEGORIES))

    def test_expected_profiles_are_present(self) -> None:
        self.assertEqual(
            IndustryProfiler.available_profiles(),
            (
                "customer_support",
                "default",
                "education",
                "finance",
                "gaming",
                "healthcare",
                "legal",
            ),
        )

    def test_specific_preset_weights(self) -> None:
        self.assertEqual(
            constants.INDUSTRY_PROFILES["healthcare"][constants.CATEGORY_SAFETY], 0.5
        )
        self.assertEqual(
            constants.INDUSTRY_PROFILES["gaming"][constants.CATEGORY_OPERATIONAL], 0.5
        )
        self.assertEqual(
            constants.INDUSTRY_PROFILES["education"][constants.CATEGORY_QUALITY], 0.6
        )


class IndustryProfilerConstructionTest(unittest.TestCase):
    def test_named_profile_exposes_a_copy_of_the_weights(self) -> None:
        profiler = IndustryProfiler("healthcare")
        self.assertEqual(profiler.weights, constants.INDUSTRY_PROFILES["healthcare"])
        # mutating the exposed copy must not touch the preset
        profiler.weights[constants.CATEGORY_SAFETY] = 0.0
        self.assertEqual(
            constants.INDUSTRY_PROFILES["healthcare"][constants.CATEGORY_SAFETY], 0.5
        )

    def test_default_profile_is_used_when_omitted(self) -> None:
        self.assertEqual(
            IndustryProfiler().weights,
            constants.INDUSTRY_PROFILES[constants.PROFILE_DEFAULT],
        )

    def test_unknown_profile_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            IndustryProfiler("aerospace")

    def test_custom_mapping_is_validated_and_copied(self) -> None:
        source = {"quality": 2.0, "safety": 1.0, "operational": 1.0}
        profiler = IndustryProfiler(source)
        self.assertEqual(profiler.weights, source)
        self.assertIsNot(profiler.weights, source)

    def test_negative_custom_weight_raises(self) -> None:
        with self.assertRaises(ValueError):
            IndustryProfiler({"quality": -0.1, "safety": 0.5, "operational": 0.6})

    def test_unknown_category_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            IndustryProfiler({"quality": 0.5, "speed": 0.5})

    def test_non_finite_custom_weight_raises(self) -> None:
        with self.assertRaises(ValueError):
            IndustryProfiler({"quality": float("nan"), "safety": 0.5})

    def test_boolean_weight_rejected(self) -> None:
        with self.assertRaises(TypeError):
            IndustryProfiler({"quality": True, "safety": 0.5})

    def test_non_mapping_non_string_profile_raises(self) -> None:
        with self.assertRaises(TypeError):
            IndustryProfiler(5)  # type: ignore[arg-type]


class WeightedOverallTest(unittest.TestCase):
    def test_default_profile_is_the_plain_mean(self) -> None:
        scores = {"quality": 9.0, "safety": 6.0, "operational": 3.0}
        self.assertEqual(IndustryProfiler("default").weighted_overall(scores), 6.0)

    def test_default_is_the_implicit_profile(self) -> None:
        scores = {"quality": 8.0, "safety": 8.0, "operational": 8.0}
        self.assertEqual(IndustryProfiler().weighted_overall(scores), 8.0)

    def test_healthcare_pushes_safety_up(self) -> None:
        # safety .5, quality .4, operational .1 -> 4*.4 + 10*.5 + 0*.1 = 6.6
        scores = {"quality": 4.0, "safety": 10.0, "operational": 0.0}
        self.assertEqual(IndustryProfiler("healthcare").weighted_overall(scores), 6.6)

    def test_gaming_pushes_operational_up(self) -> None:
        # operational .5, quality .35, safety .15 -> 2*.35 + 4*.15 + 10*.5 = 6.3
        scores = {"quality": 2.0, "safety": 4.0, "operational": 10.0}
        self.assertEqual(IndustryProfiler("gaming").weighted_overall(scores), 6.3)

    def test_none_category_is_dropped_and_weights_renormalise(self) -> None:
        # operational is None: renormalise safety/quality of healthcare
        # (.4, .5) -> weighted mean of 8 and 6 = (8*.4 + 6*.5) / .9 = 6.888.. -> 6.9
        scores = {"quality": 8.0, "safety": 6.0, "operational": None}
        self.assertEqual(IndustryProfiler("healthcare").weighted_overall(scores), 6.9)

    def test_single_scored_category_returns_that_score(self) -> None:
        scores = {"quality": None, "safety": 7.4, "operational": None}
        self.assertEqual(IndustryProfiler("finance").weighted_overall(scores), 7.4)

    def test_custom_mapping_profile(self) -> None:
        # quality weight 3, safety weight 1 -> (9*3 + 5*1) / 4 = 8.0
        scores = {"quality": 9.0, "safety": 5.0}
        weights = {"quality": 3.0, "safety": 1.0, "operational": 0.0}
        self.assertEqual(IndustryProfiler(weights).weighted_overall(scores), 8.0)

    def test_missing_category_keys_are_ignored(self) -> None:
        # only quality present in the report; result is just that score
        scores = {"quality": 7.0}
        self.assertEqual(IndustryProfiler("default").weighted_overall(scores), 7.0)

    def test_unrelated_keys_in_scores_are_ignored(self) -> None:
        scores = {"quality": 8.0, "safety": 8.0, "operational": 8.0, "extra": 1.0}
        self.assertEqual(IndustryProfiler("default").weighted_overall(scores), 8.0)

    def test_empty_scores_returns_none(self) -> None:
        self.assertIsNone(IndustryProfiler("default").weighted_overall({}))

    def test_all_none_returns_none(self) -> None:
        scores = {"quality": None, "safety": None, "operational": None}
        self.assertIsNone(IndustryProfiler("gaming").weighted_overall(scores))

    def test_rounds_to_one_decimal(self) -> None:
        # (7.77 + 8.88 + 9.99) / 3 = 8.88 -> stays 8.9 after rounding
        scores = {"quality": 7.77, "safety": 8.88, "operational": 9.99}
        result = IndustryProfiler("default").weighted_overall(scores)
        self.assertEqual(result, round(result, constants.SCORE_PRECISION))
        self.assertEqual(result, 8.9)

    def test_zero_total_weight_over_scored_categories_raises(self) -> None:
        # the only scored category has zero weight in the custom profile
        scores = {"operational": 9.0}
        weights = {"quality": 0.5, "safety": 0.5, "operational": 0.0}
        with self.assertRaises(ValueError):
            IndustryProfiler(weights).weighted_overall(scores)

    def test_non_mapping_scores_raises(self) -> None:
        with self.assertRaises(TypeError):
            IndustryProfiler("default").weighted_overall([8.0, 9.0])  # type: ignore[arg-type]

    def test_non_numeric_score_raises(self) -> None:
        with self.assertRaises(TypeError):
            IndustryProfiler("default").weighted_overall({"quality": "high"})

    def test_does_not_mutate_inputs(self) -> None:
        scores = {"quality": 8.0, "safety": 6.0, "operational": None}
        weights = {"quality": 0.5, "safety": 0.5, "operational": 0.0}
        IndustryProfiler(weights).weighted_overall(scores)
        self.assertEqual(scores, {"quality": 8.0, "safety": 6.0, "operational": None})
        self.assertEqual(weights, {"quality": 0.5, "safety": 0.5, "operational": 0.0})


if __name__ == "__main__":
    unittest.main()
