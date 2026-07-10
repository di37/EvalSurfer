from __future__ import annotations

import unittest

from evalsurfer.analysis.calibration.agreement import AgreementStats


class CohenKappaTest(unittest.TestCase):
    def test_perfect_agreement(self) -> None:
        self.assertEqual(
            AgreementStats.cohen_kappa(["a", "a", "b", "b"], ["a", "a", "b", "b"]),
            1.0,
        )

    def test_known_value_po_070_pe_050(self) -> None:
        # 10-item binary case hand-built so po = 0.7 and pe = 0.5 => kappa = 0.4.
        # rater_a is balanced 5/5 (forcing pe = 0.5); the two raters agree on 7
        # of 10 items.
        rater_a = ["yes"] * 5 + ["no"] * 5
        rater_b = [
            "yes", "yes", "yes", "yes", "no",  # 4 agree, 1 disagree (a's yes half)
            "yes", "yes", "no", "no", "no",    # 2 disagree, 3 agree (a's no half)
        ]
        self.assertAlmostEqual(
            AgreementStats.cohen_kappa(rater_a, rater_b), 0.4, places=3
        )

    def test_total_chance_agreement_returns_one_when_identical(self) -> None:
        # Both raters always pick the same single label: 1 - pe == 0, po == 1.0.
        self.assertEqual(
            AgreementStats.cohen_kappa(["x", "x", "x"], ["x", "x", "x"]), 1.0
        )

    def test_unequal_length_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgreementStats.cohen_kappa(["a", "b"], ["a"])

    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgreementStats.cohen_kappa([], [])

    def test_non_sequence_raises(self) -> None:
        with self.assertRaises(TypeError):
            AgreementStats.cohen_kappa("ab", "ab")  # type: ignore[arg-type]


class FleissKappaTest(unittest.TestCase):
    def test_perfect_agreement(self) -> None:
        # Every rater picks the same label on each item.
        self.assertEqual(
            AgreementStats.fleiss_kappa([{"a": 3}, {"b": 3}, {"a": 3}]), 1.0
        )

    def test_known_negative_value(self) -> None:
        # n = 3 raters, 2 items, split labels each item: P_bar = 1/3, Pe_bar = 0.5
        # => kappa = -1/3.
        self.assertAlmostEqual(
            AgreementStats.fleiss_kappa([{"yes": 2, "no": 1}, {"yes": 1, "no": 2}]),
            -0.333,
            places=3,
        )

    def test_single_label_returns_one(self) -> None:
        # All mass on one label: 1 - Pe_bar == 0.
        self.assertEqual(AgreementStats.fleiss_kappa([{"a": 3}, {"a": 3}]), 1.0)

    def test_non_uniform_row_totals_raise(self) -> None:
        with self.assertRaises(ValueError):
            AgreementStats.fleiss_kappa([{"a": 3}, {"a": 2}])

    def test_fewer_than_two_raters_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgreementStats.fleiss_kappa([{"a": 1}])

    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgreementStats.fleiss_kappa([])

    def test_non_mapping_item_raises(self) -> None:
        with self.assertRaises(TypeError):
            AgreementStats.fleiss_kappa([["a", "a", "b"]])  # type: ignore[list-item]

    def test_non_int_count_raises(self) -> None:
        with self.assertRaises(TypeError):
            AgreementStats.fleiss_kappa([{"a": 2.5}])  # type: ignore[dict-item]


class KrippendorffAlphaTest(unittest.TestCase):
    def test_perfect_agreement(self) -> None:
        self.assertEqual(AgreementStats.krippendorff_alpha([[1, 1], [2, 2]]), 1.0)

    def test_full_disagreement(self) -> None:
        # o_12 = o_21 = 2, n = 4, D_o = 1, D_e = 2/3, alpha = 1 - 1.5 = -0.5.
        self.assertAlmostEqual(
            AgreementStats.krippendorff_alpha([[1, 2], [2, 1]]), -0.5, places=3
        )

    def test_missing_rating_unit_is_skipped(self) -> None:
        # The [3, None] unit has one valid rating (< 2), so it drops out and the
        # result matches the two-unit disagreement case (-0.5).
        self.assertAlmostEqual(
            AgreementStats.krippendorff_alpha([[1, 2], [2, 1], [3, None]]),
            -0.5,
            places=3,
        )

    def test_missing_rating_within_pairable_unit_is_dropped(self) -> None:
        # [1, 1, None] keeps its two valid ratings (weight 1/(2-1)); combined with
        # a fully disagreeing 3-rater unit gives a hand-derived alpha of 1/7.
        self.assertAlmostEqual(
            AgreementStats.krippendorff_alpha([[1, 2, 3], [1, 1, None]]),
            0.143,
            places=3,
        )

    def test_single_label_returns_one(self) -> None:
        # All valid ratings share one label: D_e == 0.
        self.assertEqual(AgreementStats.krippendorff_alpha([[1, 1], [1, 1]]), 1.0)

    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgreementStats.krippendorff_alpha([])

    def test_non_sequence_unit_raises(self) -> None:
        with self.assertRaises(TypeError):
            AgreementStats.krippendorff_alpha([1, 2])  # type: ignore[list-item]

    def test_non_sequence_data_raises(self) -> None:
        with self.assertRaises(TypeError):
            AgreementStats.krippendorff_alpha("12")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
