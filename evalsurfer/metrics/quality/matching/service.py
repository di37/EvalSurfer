"""The match & classification calculations (exact match, accuracy, F1).

:class:`MatchMetrics` groups the stateless match and classification calculations
into a single cohesive namespace. All methods are static: the calculations carry
no per-instance state, operate over the value objects in
:mod:`evalsurfer.metrics.quality.matching.models`, and make no model calls. Magic
values come from :mod:`evalsurfer.constants`.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

import evalsurfer.constants as constants
from evalsurfer.metrics.quality.matching.helpers import _f1, _label, _paired
from evalsurfer.metrics.quality.matching.models import ClassificationReport
from evalsurfer.metrics.quality.tokenize import normalize_answer, normalized_tokens


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
