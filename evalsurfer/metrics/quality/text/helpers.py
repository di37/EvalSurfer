"""Module-level helpers for the reference-text metrics.

Small pure utilities shared by the BLEU / ROUGE / METEOR calculations: F1
(:func:`_f1`), input coercion (:func:`_require_str`, :func:`_reference_list`),
the longest-common-subsequence length (:func:`_lcs_length`), and the BLEU
brevity-penalty reference length (:func:`_closest_reference_length`).
"""

from __future__ import annotations

from typing import Sequence


def _f1(precision: float, recall: float) -> float:
    """Harmonic mean of precision and recall, or ``0.0`` when both are zero."""
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _require_str(value: object, field_name: str) -> str:
    """Return ``value`` unchanged if it is a string, else raise.

    Args:
        value: The value to check.
        field_name: Name used in error messages.

    Returns:
        The string value.

    Raises:
        TypeError: If ``value`` is not a string.
    """
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    return value


def _reference_list(references: object) -> list[str]:
    """Coerce a single reference string or a list of them to a list of strings.

    Args:
        references: One reference string, or a non-string sequence of them.

    Returns:
        The references as a list of strings (at least one).

    Raises:
        TypeError: If ``references`` is not a string or a sequence of strings.
        ValueError: If a sequence of references is empty.
    """
    if isinstance(references, str):
        return [references]
    if not isinstance(references, Sequence):
        raise TypeError("references must be a string or a list of strings")
    refs = [_require_str(ref, "reference") for ref in references]
    if not refs:
        raise ValueError("references must not be empty")
    return refs


def _lcs_length(left: Sequence[str], right: Sequence[str]) -> int:
    """Length of the longest common subsequence of two token sequences.

    Args:
        left: The first token sequence.
        right: The second token sequence.

    Returns:
        The LCS length (a rolling-row dynamic program, O(len*len) time).
    """
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    for left_token in left:
        current = [0]
        for col, right_token in enumerate(right, start=1):
            if left_token == right_token:
                current.append(previous[col - 1] + 1)
            else:
                current.append(max(previous[col], current[col - 1]))
        previous = current
    return previous[-1]


def _closest_reference_length(candidate_length: int, reference_lengths: Sequence[int]) -> int:
    """Reference length closest to the candidate length (ties prefer shorter).

    Args:
        candidate_length: The candidate token count.
        reference_lengths: The reference token counts.

    Returns:
        The chosen effective reference length for the brevity penalty.
    """
    return min(
        reference_lengths,
        key=lambda ref_len: (abs(ref_len - candidate_length), ref_len),
    )
