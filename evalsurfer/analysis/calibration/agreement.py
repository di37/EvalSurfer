"""Chance-corrected inter-rater agreement for EvalSurfer -- the "eval of the eval".

Raw boolean agreement between the judge and a human is roughly 50% by chance on a
binary call, so it overstates how much the judge actually tracks the human. These
metrics correct for chance: :meth:`AgreementStats.cohen_kappa` for two raters
(judge vs one human) over categorical decisions, :meth:`AgreementStats.fleiss_kappa`
for a fixed panel of ``n`` raters per item, and
:meth:`AgreementStats.krippendorff_alpha` (nominal) for the general case that also
tolerates missing ratings. Each returns a coefficient where ``1.0`` is perfect
agreement, ``0.0`` is chance-level, and negatives are systematic disagreement.

Everything here is pure and standard-library only -- no model calls. Inputs are
never mutated; the accumulators are always fresh local structures. The output
rounding precision comes from :mod:`evalsurfer.constants`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import permutations
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants

__all__ = [
    "AgreementStats",
]


def _rater_labels(rater_a: Any, rater_b: Any) -> tuple[list[Any], list[Any]]:
    """Validate two equal-length, non-empty, non-string label sequences.

    Args:
        rater_a: The first rater's per-item categorical labels.
        rater_b: The second rater's per-item categorical labels.

    Returns:
        The two inputs as lists.

    Raises:
        TypeError: If either argument is a string, bytes, or not a sequence.
        ValueError: If they differ in length or are empty.
    """
    for value, name in ((rater_a, "rater_a"), (rater_b, "rater_b")):
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise TypeError(f"{name} must be a list, not {type(value).__name__}")
    labels_a, labels_b = list(rater_a), list(rater_b)
    if len(labels_a) != len(labels_b):
        raise ValueError("rater_a and rater_b must have the same length")
    if not labels_a:
        raise ValueError("rater_a and rater_b must be non-empty")
    return labels_a, labels_b


def _row_counts(item: Any, index: int) -> dict[Any, int]:
    """Validate and copy one Fleiss item's ``label -> count`` mapping.

    Args:
        item: The rating item; a mapping from a label to how many raters chose it.
        index: The item's position in ``ratings``, used in error messages.

    Returns:
        A fresh dict of the item's non-negative integer counts.

    Raises:
        TypeError: If ``item`` is not a mapping or a count is not a (non-bool) int.
        ValueError: If a count is negative.
    """
    if not isinstance(item, Mapping):
        raise TypeError(f"ratings[{index}] must be a mapping of label to count")
    counts: dict[Any, int] = {}
    for label, count in item.items():
        if isinstance(count, bool) or not isinstance(count, int):
            raise TypeError(f"ratings[{index}][{label!r}] count must be an int")
        if count < 0:
            raise ValueError(f"ratings[{index}][{label!r}] count must be >= 0")
        counts[label] = count
    return counts


def _fleiss_rows(ratings: Any) -> tuple[list[dict[Any, int]], int]:
    """Validate the Fleiss rating table and return its rows and shared rater count.

    Args:
        ratings: A non-empty sequence of ``label -> count`` item mappings, every
            one summing to the same rater total ``n >= 2``.

    Returns:
        A ``(rows, n)`` pair: the validated per-item count dicts and the uniform
        number of raters per item.

    Raises:
        TypeError: If ``ratings`` is not a (non-string) sequence, an item is not a
            mapping, or a count is not a (non-bool) int.
        ValueError: If ``ratings`` is empty, a count is negative, the item totals
            are not uniform, or the shared total is below two.
    """
    if isinstance(ratings, (str, bytes)) or not isinstance(ratings, Sequence):
        raise TypeError("ratings must be a list of label-count mappings")
    items = list(ratings)
    if not items:
        raise ValueError("ratings must be non-empty")
    rows = [_row_counts(item, index) for index, item in enumerate(items)]
    totals = {sum(row.values()) for row in rows}
    if len(totals) != 1:
        raise ValueError("every rating item must share the same rater total n")
    (raters,) = totals
    if raters < 2:
        raise ValueError("each item must record at least 2 raters (n >= 2)")
    return rows, raters


def _units(reliability_data: Any) -> list[list[Any]]:
    """Validate and copy the Krippendorff reliability data into per-unit lists.

    Args:
        reliability_data: A non-empty sequence of units, each a sequence of rater
            values with ``None`` marking a missing rating.

    Returns:
        The units as fresh lists (inputs are never mutated).

    Raises:
        TypeError: If ``reliability_data`` or any unit is a string, bytes, or not
            a sequence.
        ValueError: If ``reliability_data`` is empty.
    """
    if isinstance(reliability_data, (str, bytes)) or not isinstance(
        reliability_data, Sequence
    ):
        raise TypeError("reliability_data must be a list of unit value-lists")
    units = list(reliability_data)
    if not units:
        raise ValueError("reliability_data must be non-empty")
    normalized: list[list[Any]] = []
    for index, unit in enumerate(units):
        if isinstance(unit, (str, bytes)) or not isinstance(unit, Sequence):
            raise TypeError(
                f"reliability_data[{index}] must be a list of rater values"
            )
        normalized.append(list(unit))
    return normalized


class AgreementStats:
    """Stateless chance-corrected inter-rater agreement calculations.

    All methods are static: the calculations carry no per-instance state, so the
    class is a cohesive namespace rather than something to instantiate. Inputs are
    read once and never mutated, and results are rounded to
    ``constants.SHARE_PRECISION`` decimals.
    """

    @staticmethod
    def cohen_kappa(rater_a: Sequence[Any], rater_b: Sequence[Any]) -> float:
        """Cohen's kappa: chance-corrected agreement between two raters.

        With observed agreement ``po`` (the fraction of items the two raters
        label identically) and chance agreement ``pe = sum_c p_a(c) * p_b(c)``
        over the per-rater label marginals, ``kappa = (po - pe) / (1 - pe)``.

        Args:
            rater_a: The first rater's per-item categorical labels (e.g. the
                judge's decisions).
            rater_b: The second rater's labels for the same items (e.g. a human's).

        Returns:
            The kappa coefficient rounded to ``constants.SHARE_PRECISION``
            decimals. When chance agreement is total (``1 - pe == 0``), returns
            ``1.0`` if the raters agree everywhere, else ``0.0``.

        Raises:
            TypeError: If either argument is a string, bytes, or not a sequence.
            ValueError: If the two sequences differ in length or are empty.
        """
        labels_a, labels_b = _rater_labels(rater_a, rater_b)
        n_items = len(labels_a)
        observed = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n_items
        counts_a = Counter(labels_a)
        counts_b = Counter(labels_b)
        expected = sum(
            (counts_a[label] / n_items) * (counts_b[label] / n_items)
            for label in set(counts_a) | set(counts_b)
        )
        denominator = 1 - expected
        if denominator == 0:
            return 1.0 if observed == 1.0 else 0.0
        return round((observed - expected) / denominator, constants.SHARE_PRECISION)

    @staticmethod
    def fleiss_kappa(ratings: Sequence[Mapping[Any, int]]) -> float:
        """Fleiss' kappa: chance-corrected agreement for a fixed panel of raters.

        Each item records how many of the ``n`` raters chose each label (every
        item shares the same total ``n``). Per item ``P_i = (sum_j n_ij^2 - n) /
        (n(n-1))``; with mean ``P_bar`` and label proportions ``p_j``, chance
        agreement ``Pe_bar = sum_j p_j^2`` and ``kappa = (P_bar - Pe_bar) /
        (1 - Pe_bar)``.

        Args:
            ratings: A non-empty sequence of ``label -> count`` mappings, one per
                item, each summing to the same rater total ``n >= 2``.

        Returns:
            The kappa coefficient rounded to ``constants.SHARE_PRECISION``
            decimals. When every rating lands on a single label
            (``1 - Pe_bar == 0``), returns ``1.0``.

        Raises:
            TypeError: If ``ratings`` is not a (non-string) sequence, an item is
                not a mapping, or a count is not a (non-bool) int.
            ValueError: If ``ratings`` is empty, a count is negative, the item
                totals are not uniform, or the shared total is below two.
        """
        rows, raters = _fleiss_rows(ratings)
        num_items = len(rows)
        agreement_per_item = [
            (sum(count * count for count in row.values()) - raters)
            / (raters * (raters - 1))
            for row in rows
        ]
        mean_agreement = sum(agreement_per_item) / num_items
        label_totals: Counter = Counter()
        for row in rows:
            label_totals.update(row)
        assignments = num_items * raters
        expected = sum((total / assignments) ** 2 for total in label_totals.values())
        denominator = 1 - expected
        if denominator == 0:
            return 1.0
        return round(
            (mean_agreement - expected) / denominator, constants.SHARE_PRECISION
        )

    @staticmethod
    def krippendorff_alpha(reliability_data: Sequence[Sequence[Any]]) -> float | None:
        """Krippendorff's alpha (nominal): chance-corrected agreement with gaps.

        Builds the nominal coincidence matrix over units that have at least two
        valid (non-``None``) ratings: a unit with ``m`` valid values contributes
        ``1 / (m - 1)`` to ``o[c][k]`` for each ordered pair ``(c, k)`` of its
        values. With row totals ``n_c`` and grand total ``n``, observed
        disagreement ``D_o = (1/n) * sum_{c != k} o[c][k]`` and expected
        disagreement ``D_e = (1 / (n(n-1))) * sum_{c != k} n_c * n_k`` give
        ``alpha = 1 - D_o / D_e``.

        Args:
            reliability_data: A non-empty sequence of units, each a sequence of
                rater values with ``None`` marking a missing rating. Units with
                fewer than two valid ratings are skipped.

        Returns:
            The alpha coefficient rounded to ``constants.SHARE_PRECISION``
            decimals, or ``None`` when there is no pairable data at all (no unit
            has two or more valid ratings), since agreement is then undefined
            rather than perfect. When there *is* pairable data but every valid
            rating shares one label (``D_e == 0``), returns ``1.0``.

        Raises:
            TypeError: If ``reliability_data`` or any unit is a string, bytes, or
                not a sequence.
            ValueError: If ``reliability_data`` is empty.
        """
        units = _units(reliability_data)
        coincidence: dict[Any, Counter] = defaultdict(Counter)
        for unit in units:
            values = [value for value in unit if value is not None]
            if len(values) < 2:
                continue
            weight = 1.0 / (len(values) - 1)
            for first, second in permutations(values, 2):
                coincidence[first][second] += weight

        row_totals = {label: sum(row.values()) for label, row in coincidence.items()}
        total = sum(row_totals.values())
        if total == 0:
            # No unit had two or more valid ratings: there is no evidence of
            # (dis)agreement, so alpha is undefined -- not perfect agreement.
            return None
        observed_disagreement = sum(
            value
            for label, row in coincidence.items()
            for other, value in row.items()
            if label != other
        )
        expected_disagreement = sum(
            row_totals[label] * row_totals[other]
            for label in row_totals
            for other in row_totals
            if label != other
        )
        if expected_disagreement == 0:
            return 1.0
        d_observed = observed_disagreement / total
        d_expected = expected_disagreement / (total * (total - 1))
        return round(1 - d_observed / d_expected, constants.SHARE_PRECISION)
