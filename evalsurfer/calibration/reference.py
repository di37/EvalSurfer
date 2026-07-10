"""Reference-based judge calibration -- validate a judge against human/gold scores.

The canonical way to trust an LLM judge is to check its numeric verdicts against
per-item human (gold) scores and drive the disagreement toward zero. This module
never runs the judge; it *scores the judge's numbers*. :class:`ReferenceCalibrator`
reports two complementary signals: mean absolute error
(:meth:`~ReferenceCalibrator.mean_absolute_error` -- how far the judge lands from
the human on the raw scale) and Spearman's rank correlation
(:meth:`~ReferenceCalibrator.rank_correlation` -- whether the judge *orders* items
the way a human does). :meth:`~ReferenceCalibrator.compare` runs both over one
item's per-criterion scores, and :meth:`~ReferenceCalibrator.summarize` pools many
items into an overall error and correlation.

Everything here is pure and standard-library only -- no model calls and no
third-party numeric packages (Spearman is average-ranking plus a hand-rolled
Pearson). Inputs are never mutated; results are JSON-friendly plain dicts. Every
metric name and rounding precision comes from :mod:`evalsurfer.constants`.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants

__all__ = [
    "ReferenceCalibrator",
]

# Spearman's rho needs at least this many paired observations to mean anything:
# with one or two points any two distinct values are trivially, perfectly
# monotonic (rho would be +/-1 regardless of magnitude), so below this many pairs
# the coefficient is reported as undefined (``None``).
_MIN_RANK_CORRELATION_POINTS = 3


def _as_float(value: Any, name: str) -> float:
    """Coerce one score to ``float``, rejecting booleans and non-numbers.

    Args:
        value: The raw score.
        name: The argument name, for the error message.

    Returns:
        ``value`` as a ``float``.

    Raises:
        TypeError: If ``value`` is a bool or not an int / float (booleans never
            count as a numeric score, matching the rest of the framework).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"{name} must contain only numbers, got {type(value).__name__}"
        )
    return float(value)


def _paired_numeric(
    judge_scores: Any, human_scores: Any
) -> tuple[list[float], list[float]]:
    """Validate two equal-length, non-empty, all-numeric score sequences.

    Mirrors :func:`quality.matching._paired` and additionally coerces every
    element to a ``float`` so callers work on clean numeric vectors.

    Args:
        judge_scores: The judge's scores.
        human_scores: The human / gold scores.

    Returns:
        The two inputs as equal-length lists of floats.

    Raises:
        TypeError: If either argument is a string, bytes, or not a sequence, or
            any element is non-numeric.
        ValueError: If the sequences differ in length or are empty.
    """
    for value, name in (
        (judge_scores, "judge_scores"),
        (human_scores, "human_scores"),
    ):
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise TypeError(f"{name} must be a sequence, not {type(value).__name__}")
    if len(judge_scores) != len(human_scores):
        raise ValueError("judge_scores and human_scores must have the same length")
    if not judge_scores:
        raise ValueError("judge_scores and human_scores must be non-empty")
    judge = [_as_float(value, "judge_scores") for value in judge_scores]
    human = [_as_float(value, "human_scores") for value in human_scores]
    return judge, human


def _require_mapping(value: Any, name: str) -> None:
    """Fail fast unless ``value`` is a mapping.

    Args:
        value: The value to check.
        name: The argument name, for the error message.

    Raises:
        TypeError: If ``value`` is not a :class:`~typing.Mapping`.
    """
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")


def _validated_pairs(
    pairs: Any,
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Validate a sequence of ``(judge, gold)`` mapping pairs.

    Args:
        pairs: The candidate sequence of item pairs.

    Returns:
        The pairs as a list of ``(judge_map, gold_map)`` tuples.

    Raises:
        TypeError: If ``pairs`` is a string / bytes / non-sequence, or any entry
            is not a two-element pair of mappings.
    """
    if isinstance(pairs, (str, bytes)) or not isinstance(pairs, Sequence):
        raise TypeError(f"pairs must be a sequence, not {type(pairs).__name__}")
    items: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for index, pair in enumerate(pairs):
        if (
            isinstance(pair, (str, bytes))
            or not isinstance(pair, Sequence)
            or len(pair) != 2
        ):
            raise TypeError(f"pairs[{index}] must be a (judge, gold) pair")
        judge_map, gold_map = pair
        _require_mapping(judge_map, f"pairs[{index}] judge")
        _require_mapping(gold_map, f"pairs[{index}] gold")
        items.append((judge_map, gold_map))
    return items


def _average_ranks(values: Sequence[float]) -> list[float]:
    """Rank a vector 1..n, giving tied values their shared mean rank.

    Args:
        values: The numeric vector to rank.

    Returns:
        A list of ranks aligned with ``values``; each group of equal values
        receives the average of the ranks it spans (so ``[1, 1, 2]`` ranks as
        ``[1.5, 1.5, 3]``).
    """
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    total = len(values)
    position = 0
    while position < total:
        end = position
        while end + 1 < total and values[order[end + 1]] == values[order[position]]:
            end += 1
        # ``position``..``end`` cover the 1-based ranks (position + 1)..(end + 1);
        # every tied entry shares the mean of that inclusive span.
        shared_rank = (position + 1 + end + 1) / 2.0
        for index in range(position, end + 1):
            ranks[order[index]] = shared_rank
        position = end + 1
    return ranks


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson correlation of two equal-length vectors, or ``None`` if undefined.

    Args:
        xs: The first vector (non-empty, same length as ``ys``).
        ys: The second vector.

    Returns:
        The Pearson correlation coefficient, or ``None`` when either vector has
        zero variance (the coefficient is then undefined -- division by zero).
    """
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    var_x = sum(delta * delta for delta in dx)
    var_y = sum(delta * delta for delta in dy)
    if var_x == 0 or var_y == 0:
        return None
    covariance = sum(a * b for a, b in zip(dx, dy))
    return covariance / math.sqrt(var_x * var_y)


def _mean_absolute_error(judge: Sequence[float], human: Sequence[float]) -> float:
    """Rounded mean absolute error over two validated, non-empty vectors.

    Args:
        judge: The judge scores (non-empty, same length as ``human``).
        human: The human / gold scores.

    Returns:
        ``mean(|judge - human|)`` rounded to ``constants.SHARE_PRECISION``.
    """
    total = sum(abs(j - h) for j, h in zip(judge, human))
    return round(total / len(judge), constants.SHARE_PRECISION)


def _spearman(judge: Sequence[float], human: Sequence[float]) -> float | None:
    """Rounded Spearman's rho over two validated, non-empty vectors, or ``None``.

    Args:
        judge: The judge scores (non-empty, same length as ``human``).
        human: The human / gold scores.

    Returns:
        Spearman's rho -- Pearson correlation of the average ranks -- rounded to
        ``constants.SHARE_PRECISION``, or ``None`` when fewer than
        ``_MIN_RANK_CORRELATION_POINTS`` pairs are given or either vector has zero
        variance (rho is then undefined).
    """
    if len(judge) < _MIN_RANK_CORRELATION_POINTS:
        return None
    rho = _pearson(_average_ranks(judge), _average_ranks(human))
    if rho is None:
        return None
    return round(rho, constants.SHARE_PRECISION)


class ReferenceCalibrator:
    """Validate a judge's numeric scores against human / gold scores.

    Stateless: every method is static and derives its result purely from the
    scores passed in. Nothing here calls a model or mutates its inputs; the
    calibration signals (mean absolute error, Spearman's rho) are computed with
    the standard library alone.
    """

    @staticmethod
    def mean_absolute_error(
        judge_scores: Sequence[float], human_scores: Sequence[float]
    ) -> float:
        """Mean absolute error between judge scores and human / gold scores.

        Args:
            judge_scores: The judge's numeric scores.
            human_scores: The aligned human / gold scores.

        Returns:
            ``mean(|judge - human|)`` rounded to ``constants.SHARE_PRECISION``
            decimals; ``0.0`` only when the judge matches the human everywhere.

        Raises:
            TypeError: If an argument is not a sequence or holds a non-number.
            ValueError: If the sequences differ in length or are empty.
        """
        judge, human = _paired_numeric(judge_scores, human_scores)
        return _mean_absolute_error(judge, human)

    @staticmethod
    def rank_correlation(
        judge_scores: Sequence[float], human_scores: Sequence[float]
    ) -> float | None:
        """Spearman's rank correlation between judge and human / gold scores.

        Each vector is average-ranked (ties share their mean rank) and the two
        rank vectors are correlated with Pearson's coefficient.

        Args:
            judge_scores: The judge's numeric scores.
            human_scores: The aligned human / gold scores.

        Returns:
            Spearman's rho in ``[-1, 1]`` rounded to ``constants.SHARE_PRECISION``
            decimals, or ``None`` when it is undefined -- either vector is
            constant (zero variance) or fewer than
            ``_MIN_RANK_CORRELATION_POINTS`` pairs were given.

        Raises:
            TypeError: If an argument is not a sequence or holds a non-number.
            ValueError: If the sequences differ in length or are empty.
        """
        judge, human = _paired_numeric(judge_scores, human_scores)
        return _spearman(judge, human)

    @staticmethod
    def compare(
        judge: Mapping[str, float], gold: Mapping[str, float]
    ) -> dict[str, Any]:
        """Score one item's per-criterion judge scores against gold scores.

        Only criteria present in *both* mappings are scored; a criterion missing
        from either side is ignored. Criteria are ordered by id so the pooled
        vectors (and therefore the correlation) are deterministic.

        Args:
            judge: A ``criterion_id -> score`` mapping from the judge.
            gold: A ``criterion_id -> score`` mapping of human / gold scores.

        Returns:
            ``{"per_criterion", constants.METRIC_JUDGE_HUMAN_MAE,
            constants.METRIC_RANK_CORRELATION, "criteria"}`` where
            ``per_criterion`` maps each shared criterion id to its absolute error,
            the MAE is the mean of those errors (``None`` when no criterion is
            shared), the correlation is Spearman's rho over the shared scores
            (``None`` when undefined), and ``criteria`` is the shared count.

        Raises:
            TypeError: If ``judge`` or ``gold`` is not a mapping, or a shared
                score is non-numeric.
        """
        _require_mapping(judge, "judge")
        _require_mapping(gold, "gold")
        shared = sorted(set(judge) & set(gold))
        judge_vector = [_as_float(judge[cid], "judge") for cid in shared]
        gold_vector = [_as_float(gold[cid], "gold") for cid in shared]
        per_criterion = {
            cid: round(abs(j - g), constants.SHARE_PRECISION)
            for cid, j, g in zip(shared, judge_vector, gold_vector)
        }
        return {
            "per_criterion": per_criterion,
            constants.METRIC_JUDGE_HUMAN_MAE: (
                _mean_absolute_error(judge_vector, gold_vector) if shared else None
            ),
            constants.METRIC_RANK_CORRELATION: (
                _spearman(judge_vector, gold_vector) if shared else None
            ),
            "criteria": len(shared),
        }

    @staticmethod
    def summarize(
        pairs: Sequence[tuple[Mapping[str, float], Mapping[str, float]]],
    ) -> dict[str, Any]:
        """Pool many items' shared judge/gold scores into overall error & rho.

        Every ``(judge, gold)`` pair contributes its shared-criterion score pairs
        to one pooled sample, and the metrics are computed once over that pool.

        Args:
            pairs: A sequence of ``(judge_map, gold_map)`` score-mapping pairs,
                one per evaluated item.

        Returns:
            ``{constants.METRIC_JUDGE_HUMAN_MAE,
            constants.METRIC_RANK_CORRELATION, "n"}`` where the MAE and
            correlation are computed over all pooled score pairs (each ``None``
            when undefined) and ``n`` is the number of pooled pairs.

        Raises:
            TypeError: If ``pairs`` is not a (non-string) sequence, an entry is
                not a two-element ``(judge, gold)`` pair of mappings, or a shared
                score is non-numeric.
        """
        items = _validated_pairs(pairs)
        pooled_judge: list[float] = []
        pooled_gold: list[float] = []
        for judge_map, gold_map in items:
            for cid in sorted(set(judge_map) & set(gold_map)):
                pooled_judge.append(_as_float(judge_map[cid], "judge"))
                pooled_gold.append(_as_float(gold_map[cid], "gold"))
        pooled = len(pooled_judge)
        return {
            constants.METRIC_JUDGE_HUMAN_MAE: (
                _mean_absolute_error(pooled_judge, pooled_gold) if pooled else None
            ),
            constants.METRIC_RANK_CORRELATION: (
                _spearman(pooled_judge, pooled_gold) if pooled else None
            ),
            "n": pooled,
        }
