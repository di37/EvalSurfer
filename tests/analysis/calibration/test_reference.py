from __future__ import annotations

import copy
import unittest

import evalsurfer.constants as constants
from evalsurfer.analysis.calibration.reference import ReferenceCalibrator

MAE = constants.METRIC_JUDGE_HUMAN_MAE
RHO = constants.METRIC_RANK_CORRELATION


class MeanAbsoluteErrorTest(unittest.TestCase):
    def test_hand_verified_vector(self) -> None:
        # Errors 0, 1, 0 -> mean 1/3 -> 0.333.
        self.assertEqual(
            ReferenceCalibrator.mean_absolute_error([5, 4, 3], [5, 3, 3]),
            round(1 / 3, constants.SHARE_PRECISION),
        )

    def test_perfect_agreement_is_zero(self) -> None:
        self.assertEqual(
            ReferenceCalibrator.mean_absolute_error([5, 4, 3], [5, 4, 3]), 0.0
        )

    def test_rounds_to_share_precision(self) -> None:
        # |1-2| + |4-4| + |4-4| = 1 over 3 -> 0.333 (rounded).
        self.assertEqual(
            ReferenceCalibrator.mean_absolute_error([1, 4, 4], [2, 4, 4]), 0.333
        )

    def test_accepts_floats(self) -> None:
        self.assertEqual(
            ReferenceCalibrator.mean_absolute_error([1.5, 3.0], [1.0, 4.0]), 0.75
        )


class RankCorrelationTest(unittest.TestCase):
    def test_perfect_positive(self) -> None:
        self.assertEqual(
            ReferenceCalibrator.rank_correlation([1, 2, 3], [1, 2, 3]), 1.0
        )

    def test_perfect_negative(self) -> None:
        self.assertEqual(
            ReferenceCalibrator.rank_correlation([1, 2, 3], [3, 2, 1]), -1.0
        )

    def test_hand_verified_partial(self) -> None:
        # Spearman over ranks [1,2,3,4] vs [1,3,2,4] -> 4.0 / 5.0 = 0.8.
        self.assertEqual(
            ReferenceCalibrator.rank_correlation([1, 2, 3, 4], [1, 3, 2, 4]), 0.8
        )

    def test_tie_handling_uses_mean_ranks(self) -> None:
        # ranks [1.5,1.5,3,4] vs [1,2.5,2.5,4] -> 3.75 / 4.5 = 0.8333 -> 0.833.
        value = ReferenceCalibrator.rank_correlation([1, 1, 2, 3], [1, 2, 2, 3])
        self.assertIsNotNone(value)
        self.assertEqual(value, 0.833)

    def test_zero_variance_is_none(self) -> None:
        # A constant vector has no variance, so rho is undefined.
        self.assertIsNone(
            ReferenceCalibrator.rank_correlation([2, 2, 2], [1, 2, 3])
        )
        self.assertIsNone(
            ReferenceCalibrator.rank_correlation([1, 2, 3], [4, 4, 4])
        )

    def test_fewer_than_three_points_is_none(self) -> None:
        # Two distinct points are trivially perfectly monotonic; rho is undefined.
        self.assertIsNone(ReferenceCalibrator.rank_correlation([5, 4], [5, 3]))
        self.assertIsNone(ReferenceCalibrator.rank_correlation([1], [9]))

    def test_symmetric(self) -> None:
        forward = ReferenceCalibrator.rank_correlation([1, 2, 3, 4], [1, 3, 2, 4])
        backward = ReferenceCalibrator.rank_correlation([1, 3, 2, 4], [1, 2, 3, 4])
        self.assertEqual(forward, backward)


class CompareTest(unittest.TestCase):
    def test_two_criteria_case(self) -> None:
        result = ReferenceCalibrator.compare(
            {"correctness": 5, "relevance": 4},
            {"correctness": 5, "relevance": 3},
        )
        self.assertEqual(
            result["per_criterion"], {"correctness": 0, "relevance": 1}
        )
        self.assertEqual(result[MAE], 0.5)
        # Only two shared criteria: rho needs >= 3 points, so it is undefined.
        self.assertIsNone(result[RHO])
        self.assertEqual(result["criteria"], 2)

    def test_result_shape(self) -> None:
        result = ReferenceCalibrator.compare({"a": 5}, {"a": 5})
        self.assertEqual(set(result), {"per_criterion", MAE, RHO, "criteria"})

    def test_ignores_criteria_not_in_both(self) -> None:
        result = ReferenceCalibrator.compare(
            {"a": 5, "b": 3, "judge_only": 1},
            {"a": 5, "b": 2, "gold_only": 4},
        )
        self.assertEqual(set(result["per_criterion"]), {"a", "b"})
        self.assertEqual(result["criteria"], 2)
        self.assertEqual(result[MAE], 0.5)  # |5-5| + |3-2| over 2

    def test_three_shared_criteria_yield_correlation(self) -> None:
        # judge ranks [3,1,2] vs gold ranks [3,1,2] -> rho 1.0; MAE 1/3.
        result = ReferenceCalibrator.compare(
            {"a": 5, "b": 3, "c": 4},
            {"a": 5, "b": 2, "c": 4},
        )
        self.assertEqual(result["criteria"], 3)
        self.assertEqual(result[MAE], round(1 / 3, constants.SHARE_PRECISION))
        self.assertEqual(result[RHO], 1.0)

    def test_four_shared_criteria_partial_correlation(self) -> None:
        # Shared scores order to [1,2,3,4] vs [1,3,2,4] -> rho 0.8, MAE 0.5.
        result = ReferenceCalibrator.compare(
            {"a": 1, "b": 2, "c": 3, "d": 4},
            {"a": 1, "b": 3, "c": 2, "d": 4},
        )
        self.assertEqual(result["criteria"], 4)
        self.assertEqual(result[MAE], 0.5)
        self.assertEqual(result[RHO], 0.8)

    def test_no_shared_criteria(self) -> None:
        result = ReferenceCalibrator.compare({"a": 5}, {"b": 3})
        self.assertEqual(result["per_criterion"], {})
        self.assertIsNone(result[MAE])
        self.assertIsNone(result[RHO])
        self.assertEqual(result["criteria"], 0)

    def test_rejects_non_mapping(self) -> None:
        with self.assertRaises(TypeError):
            ReferenceCalibrator.compare(["a", 5], {"a": 5})
        with self.assertRaises(TypeError):
            ReferenceCalibrator.compare({"a": 5}, "gold")

    def test_rejects_non_numeric_shared_score(self) -> None:
        with self.assertRaises(TypeError):
            ReferenceCalibrator.compare({"a": "high"}, {"a": 5})

    def test_does_not_mutate_inputs(self) -> None:
        judge = {"a": 5, "b": 4}
        gold = {"a": 5, "b": 3}
        judge_snapshot = copy.deepcopy(judge)
        gold_snapshot = copy.deepcopy(gold)
        ReferenceCalibrator.compare(judge, gold)
        self.assertEqual(judge, judge_snapshot)
        self.assertEqual(gold, gold_snapshot)


class SummarizeTest(unittest.TestCase):
    def test_pools_across_items(self) -> None:
        # Pooled judge [1,2,3,4] vs gold [1,3,2,4] -> MAE 0.5, rho 0.8, n 4.
        pairs = [
            ({"a": 1, "b": 2}, {"a": 1, "b": 3}),
            ({"a": 3, "b": 4}, {"a": 2, "b": 4}),
        ]
        summary = ReferenceCalibrator.summarize(pairs)
        self.assertEqual(summary["n"], 4)
        self.assertEqual(summary[MAE], 0.5)
        self.assertEqual(summary[RHO], 0.8)

    def test_result_shape(self) -> None:
        summary = ReferenceCalibrator.summarize([({"a": 5}, {"a": 5})])
        self.assertEqual(set(summary), {MAE, RHO, "n"})

    def test_ignores_unshared_criteria_when_pooling(self) -> None:
        pairs = [({"a": 5, "extra": 9}, {"a": 4})]
        summary = ReferenceCalibrator.summarize(pairs)
        self.assertEqual(summary["n"], 1)
        self.assertEqual(summary[MAE], 1.0)
        # Only one pooled pair -> rho undefined.
        self.assertIsNone(summary[RHO])

    def test_empty_pairs(self) -> None:
        summary = ReferenceCalibrator.summarize([])
        self.assertEqual(summary["n"], 0)
        self.assertIsNone(summary[MAE])
        self.assertIsNone(summary[RHO])

    def test_pairs_with_no_shared_criteria_pool_to_nothing(self) -> None:
        summary = ReferenceCalibrator.summarize([({"a": 5}, {"b": 3})])
        self.assertEqual(summary["n"], 0)
        self.assertIsNone(summary[MAE])
        self.assertIsNone(summary[RHO])

    def test_rejects_non_sequence(self) -> None:
        with self.assertRaises(TypeError):
            ReferenceCalibrator.summarize(5)

    def test_rejects_string_sequence(self) -> None:
        with self.assertRaises(TypeError):
            ReferenceCalibrator.summarize("not pairs")

    def test_rejects_malformed_pair(self) -> None:
        with self.assertRaises(TypeError):
            ReferenceCalibrator.summarize([({"a": 5},)])  # not a 2-tuple
        with self.assertRaises(TypeError):
            ReferenceCalibrator.summarize([("judge", {"a": 5})])  # judge not a map

    def test_does_not_mutate_inputs(self) -> None:
        pairs = [({"a": 1, "b": 2}, {"a": 1, "b": 3})]
        snapshot = copy.deepcopy(pairs)
        ReferenceCalibrator.summarize(pairs)
        self.assertEqual(pairs, snapshot)


class ValidationTest(unittest.TestCase):
    def test_unequal_length_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ReferenceCalibrator.mean_absolute_error([1, 2], [1])
        with self.assertRaises(ValueError):
            ReferenceCalibrator.rank_correlation([1, 2, 3], [1, 2])

    def test_empty_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ReferenceCalibrator.mean_absolute_error([], [])
        with self.assertRaises(ValueError):
            ReferenceCalibrator.rank_correlation([], [])

    def test_non_numeric_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ReferenceCalibrator.mean_absolute_error([1, "a"], [1, 2])
        with self.assertRaises(TypeError):
            ReferenceCalibrator.rank_correlation([1, 2, None], [1, 2, 3])

    def test_string_sequence_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ReferenceCalibrator.mean_absolute_error("12", "34")

    def test_non_sequence_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ReferenceCalibrator.mean_absolute_error(5, 5)

    def test_boolean_scores_rejected(self) -> None:
        # Booleans never count as a numeric score (framework-wide convention).
        with self.assertRaises(TypeError):
            ReferenceCalibrator.mean_absolute_error([True, 2], [1, 2])


class PublicApiTest(unittest.TestCase):
    def test_metric_name_constants(self) -> None:
        self.assertEqual(constants.METRIC_JUDGE_HUMAN_MAE, "judge_human_mae")
        self.assertEqual(constants.METRIC_RANK_CORRELATION, "rank_correlation")

    def test_exposes_callables(self) -> None:
        for name in (
            "mean_absolute_error",
            "rank_correlation",
            "compare",
            "summarize",
        ):
            self.assertTrue(callable(getattr(ReferenceCalibrator, name)))

    def test_is_deterministic(self) -> None:
        judge = {"a": 5, "b": 3, "c": 4}
        gold = {"a": 5, "b": 2, "c": 4}
        self.assertEqual(
            ReferenceCalibrator.compare(judge, gold),
            ReferenceCalibrator.compare(judge, gold),
        )


if __name__ == "__main__":
    unittest.main()
