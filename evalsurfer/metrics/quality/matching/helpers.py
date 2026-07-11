"""Module-level helpers for the match & classification metrics.

Small pure utilities shared by the calculations: F1 (:func:`_f1`), paired-input
validation (:func:`_paired`), and label coercion (:func:`_label`).
"""

from __future__ import annotations

from typing import Any, Sequence


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
