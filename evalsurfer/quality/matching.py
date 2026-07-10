"""Deterministic match & classification metrics (exact match, accuracy, F1).

For extraction / short-answer QA these compare a predicted string to a gold
string: :meth:`MatchMetrics.exact_match` (SQuAD-normalised equality) and
:meth:`MatchMetrics.token_f1` (token-overlap F1). For classification they score
predicted labels against gold labels: :meth:`MatchMetrics.accuracy` and
:meth:`MatchMetrics.classification_report` (per-label precision / recall / F1
with micro or macro averaging, plus a binary mode).

Everything here is pure and standard-library only -- no model calls. Value
objects are immutable; inputs are never mutated. Magic values come from
:mod:`evalsurfer.constants`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Sequence

import evalsurfer.constants as constants
from evalsurfer.quality.tokenize import normalize_answer, normalized_tokens

__all__ = [
    "ClassificationReport",
    "MatchMetrics",
]


def _f1(precision: float, recall: float) -> float:
    """Harmonic mean of precision and recall, or ``0.0`` when both are zero.

    Args:
        precision: The precision in ``[0, 1]``.
        recall: The recall in ``[0, 1]``.

    Returns:
        The F1 score.
    """
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _paired(predictions: Any, references: Any) -> tuple[list[Any], list[Any]]:
    """Validate two equal-length, non-empty, non-string sequences.

    Args:
        predictions: The predicted values.
        references: The gold values.

    Returns:
        The two inputs as lists.

    Raises:
        TypeError: If either argument is a string, bytes, or not a sequence.
        ValueError: If they differ in length or are empty.
    """
    for value, name in ((predictions, "predictions"), (references, "references")):
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise TypeError(f"{name} must be a list, not {type(value).__name__}")
    preds, refs = list(predictions), list(references)
    if len(preds) != len(refs):
        raise ValueError("predictions and references must have the same length")
    if not preds:
        raise ValueError("predictions and references must be non-empty")
    return preds, refs


def _label(value: Any) -> str:
    """Coerce a classification label to a trimmed string for exact comparison.

    Args:
        value: The raw label.

    Returns:
        ``str(value).strip()`` -- categorical, not SQuAD-normalised, so labels
        like ``"NOT_SPAM"`` keep their exact form.
    """
    return str(value).strip()


@dataclass(frozen=True)
class ClassificationReport:
    """Aggregate and per-label classification scores."""

    accuracy: float
    precision: float
    recall: float
    f1: float
    average: str
    support: int
    per_label: dict[str, dict[str, float]]


class MatchMetrics:
    """Stateless match & classification calculations.

    All methods are static: the calculations carry no per-instance state, so the
    class is a cohesive namespace rather than something to instantiate.
    """

    @staticmethod
    def exact_match(prediction: str, reference: str) -> float:
        """SQuAD-normalised exact match between a prediction and a reference.

        Args:
            prediction: The predicted answer string.
            reference: The gold answer string.

        Returns:
            ``1.0`` when the normalised strings are equal, else ``0.0``.

        Raises:
            TypeError: If either argument is not a string.
        """
        return 1.0 if normalize_answer(prediction) == normalize_answer(reference) else 0.0

    @staticmethod
    def token_f1(prediction: str, reference: str) -> float:
        """Token-overlap F1 between a prediction and a reference (SQuAD-style).

        Args:
            prediction: The predicted answer string.
            reference: The gold answer string.

        Returns:
            The F1 over shared normalised tokens: ``1.0`` when both normalise to
            empty, ``0.0`` when exactly one does or there is no overlap.

        Raises:
            TypeError: If either argument is not a string.
        """
        pred_tokens = normalized_tokens(prediction)
        gold_tokens = normalized_tokens(reference)
        if not pred_tokens and not gold_tokens:
            return 1.0
        if not pred_tokens or not gold_tokens:
            return 0.0
        shared = sum((Counter(pred_tokens) & Counter(gold_tokens)).values())
        if shared == 0:
            return 0.0
        precision = shared / len(pred_tokens)
        recall = shared / len(gold_tokens)
        return _f1(precision, recall)

    @staticmethod
    def exact_match_accuracy(
        predictions: Sequence[str], references: Sequence[str]
    ) -> float:
        """Mean SQuAD exact match over paired predictions and references.

        Args:
            predictions: The predicted answer strings.
            references: The gold answer strings.

        Returns:
            The fraction of pairs that match, rounded to
            ``constants.SHARE_PRECISION`` decimals.

        Raises:
            TypeError: If an argument is not a list.
            ValueError: If the lists differ in length or are empty.
        """
        preds, refs = _paired(predictions, references)
        matches = sum(
            MatchMetrics.exact_match(pred, ref) for pred, ref in zip(preds, refs)
        )
        return round(matches / len(preds), constants.SHARE_PRECISION)

    @staticmethod
    def token_f1_mean(
        predictions: Sequence[str], references: Sequence[str]
    ) -> float:
        """Mean token-overlap F1 over paired predictions and references.

        Args:
            predictions: The predicted answer strings.
            references: The gold answer strings.

        Returns:
            The mean F1, rounded to ``constants.SHARE_PRECISION`` decimals.

        Raises:
            TypeError: If an argument is not a list.
            ValueError: If the lists differ in length or are empty.
        """
        preds, refs = _paired(predictions, references)
        total = sum(
            MatchMetrics.token_f1(pred, ref) for pred, ref in zip(preds, refs)
        )
        return round(total / len(preds), constants.SHARE_PRECISION)

    @staticmethod
    def accuracy(
        predictions: Sequence[Any], references: Sequence[Any]
    ) -> float:
        """Classification accuracy: fraction of predicted labels equal to gold.

        Labels are compared as trimmed strings (categorical equality), not
        SQuAD-normalised text.

        Args:
            predictions: The predicted labels.
            references: The gold labels.

        Returns:
            The accuracy, rounded to ``constants.SHARE_PRECISION`` decimals.

        Raises:
            TypeError: If an argument is not a list.
            ValueError: If the lists differ in length or are empty.
        """
        preds, refs = _paired(predictions, references)
        correct = sum(
            1 for pred, ref in zip(preds, refs) if _label(pred) == _label(ref)
        )
        return round(correct / len(preds), constants.SHARE_PRECISION)

    @staticmethod
    def _per_label_counts(
        preds: Sequence[str], refs: Sequence[str]
    ) -> dict[str, dict[str, int]]:
        """Count tp / fp / fn / support for every label in the data.

        Args:
            preds: The trimmed predicted labels.
            refs: The trimmed gold labels.

        Returns:
            A label-keyed mapping of ``{"tp", "fp", "fn", "support"}`` counts.
        """
        labels = sorted(set(preds) | set(refs))
        counts = {
            label: {"tp": 0, "fp": 0, "fn": 0, "support": 0} for label in labels
        }
        for pred, ref in zip(preds, refs):
            counts[ref]["support"] += 1
            if pred == ref:
                counts[pred]["tp"] += 1
            else:
                counts[pred]["fp"] += 1
                counts[ref]["fn"] += 1
        return counts

    @staticmethod
    def _scores(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
        """Precision, recall, and F1 from a confusion triple.

        Args:
            tp: True positives.
            fp: False positives.
            fn: False negatives.

        Returns:
            The ``(precision, recall, f1)`` triple; precision/recall are ``0.0``
            when their denominator is zero.
        """
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        return precision, recall, _f1(precision, recall)

    @classmethod
    def classification_report(
        cls,
        predictions: Sequence[Any],
        references: Sequence[Any],
        average: str = constants.AVERAGE_MACRO,
        positive_label: Any | None = None,
    ) -> ClassificationReport:
        """Per-label and averaged precision / recall / F1 for classification.

        With ``positive_label`` set, reports that one label's binary scores.
        Otherwise averages across every label in the data: ``macro`` (unweighted
        label mean) or ``micro`` (pooled counts, which equals accuracy for
        single-label tasks).

        Args:
            predictions: The predicted labels.
            references: The gold labels.
            average: ``constants.AVERAGE_MACRO`` or ``constants.AVERAGE_MICRO``
                (ignored when ``positive_label`` is given).
            positive_label: When set, report this label's binary P/R/F1.

        Returns:
            The :class:`ClassificationReport`. Values are rounded to
            ``constants.SHARE_PRECISION`` decimals.

        Raises:
            TypeError: If an argument is not a list.
            ValueError: If the lists differ in length or are empty, ``average``
                is unknown, or ``positive_label`` is absent from the data.
        """
        if average not in constants.CLASSIFICATION_AVERAGES:
            raise ValueError(
                f"average must be one of {constants.CLASSIFICATION_AVERAGES}"
            )
        raw_preds, raw_refs = _paired(predictions, references)
        preds = [_label(value) for value in raw_preds]
        refs = [_label(value) for value in raw_refs]
        counts = cls._per_label_counts(preds, refs)

        digits = constants.SHARE_PRECISION
        per_label: dict[str, dict[str, float]] = {}
        for label, count in counts.items():
            precision, recall, f1 = cls._scores(
                count["tp"], count["fp"], count["fn"]
            )
            per_label[label] = {
                "precision": round(precision, digits),
                "recall": round(recall, digits),
                "f1": round(f1, digits),
                "support": count["support"],
            }

        accuracy = round(
            sum(1 for pred, ref in zip(preds, refs) if pred == ref) / len(preds),
            digits,
        )

        if positive_label is not None:
            key = _label(positive_label)
            if key not in counts:
                raise ValueError(f"positive_label {positive_label!r} not in the data")
            precision, recall, f1 = cls._scores(
                counts[key]["tp"], counts[key]["fp"], counts[key]["fn"]
            )
            resolved_average = "binary"
        elif average == constants.AVERAGE_MICRO:
            tp = sum(count["tp"] for count in counts.values())
            fp = sum(count["fp"] for count in counts.values())
            fn = sum(count["fn"] for count in counts.values())
            precision, recall, f1 = cls._scores(tp, fp, fn)
            resolved_average = constants.AVERAGE_MICRO
        else:
            label_scores = [cls._scores(c["tp"], c["fp"], c["fn"]) for c in counts.values()]
            n_labels = len(label_scores) or 1
            precision = sum(score[0] for score in label_scores) / n_labels
            recall = sum(score[1] for score in label_scores) / n_labels
            f1 = sum(score[2] for score in label_scores) / n_labels
            resolved_average = constants.AVERAGE_MACRO

        return ClassificationReport(
            accuracy=accuracy,
            precision=round(precision, digits),
            recall=round(recall, digits),
            f1=round(f1, digits),
            average=resolved_average,
            support=len(preds),
            per_label=per_label,
        )
