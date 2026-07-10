"""Deterministic reference-text metrics: BLEU, ROUGE-N/L, METEOR.

These are *task-typed*: BLEU for translation, ROUGE for summarization, METEOR
for order-aware generation. They report a recognizable number against a gold
reference with **no judge**, at the known cost that they are stylistically
brittle and correlate only weakly with human judgment -- prefer them as a fast,
repeatable signal alongside the agent's judgment, not instead of it.

METEOR here matches on exact tokens plus a light dependency-free stem (see
:func:`evalsurfer.metrics.quality.tokenize.light_stem`); it carries **no WordNet synonym
lexicon**, so it under-credits synonym matches relative to full METEOR. BLEU is
corpus-accumulated with a brevity penalty and a simple **floor smoothing** (a
present n-gram order with no match is floored to ``1/(total+1)`` rather than
zeroing the product -- not the same as Chen & Cherry's ``epsilon/total``);
n-gram orders absent from the candidate are dropped from the geometric mean.

Everything here is pure and standard-library only -- no model calls. Value
objects are immutable; inputs are never mutated. Magic values come from
:mod:`evalsurfer.constants`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import exp, log
from typing import Sequence

import evalsurfer.constants as constants
from evalsurfer.metrics.quality.tokenize import light_stem, ngrams, tokenize

__all__ = [
    "RougeScore",
    "TextMetrics",
]


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


@dataclass(frozen=True)
class RougeScore:
    """Precision, recall, and F1 for a ROUGE variant."""

    precision: float
    recall: float
    f1: float


class TextMetrics:
    """Stateless reference-text metric calculations.

    All methods are static/class methods: the calculations carry no per-instance
    state, so the class is a cohesive namespace rather than something to
    instantiate.
    """

    # ----------------------------------------------------------------- BLEU
    @classmethod
    def bleu(
        cls,
        candidate: str,
        references: str | Sequence[str],
        max_n: int = constants.BLEU_MAX_N,
        smooth: bool = True,
    ) -> float:
        """Sentence BLEU of a candidate against one or more references.

        Args:
            candidate: The candidate (hypothesis) string.
            references: One reference string, or a list of them.
            max_n: The maximum n-gram order (BLEU-``max_n``).
            smooth: Apply floor smoothing so a single zero-match order does not
                collapse the whole score (see the module docstring).

        Returns:
            The BLEU score in ``[0, 1]``, rounded to
            ``constants.SHARE_PRECISION`` decimals.

        Raises:
            TypeError: If ``candidate`` or a reference is not a string.
            ValueError: If ``max_n`` is not positive or a reference list is empty.
        """
        return cls.corpus_bleu([candidate], [references], max_n=max_n, smooth=smooth)

    @classmethod
    def corpus_bleu(
        cls,
        candidates: Sequence[str],
        references_list: Sequence[str | Sequence[str]],
        max_n: int = constants.BLEU_MAX_N,
        smooth: bool = True,
    ) -> float:
        """Corpus BLEU: n-gram counts pooled across all candidate/reference pairs.

        Args:
            candidates: The candidate strings.
            references_list: For each candidate, one reference string or a list
                of them (same length as ``candidates``).
            max_n: The maximum n-gram order.
            smooth: Apply floor smoothing (see the module docstring).

        Returns:
            The corpus BLEU in ``[0, 1]``, rounded to
            ``constants.SHARE_PRECISION`` decimals. ``0.0`` for empty input.

        Raises:
            TypeError: If the inputs are not lists of the right types.
            ValueError: If ``max_n`` is not positive, the two lists differ in
                length, or a reference list is empty.
        """
        if isinstance(max_n, bool) or not isinstance(max_n, int) or max_n < 1:
            raise ValueError("max_n must be a positive integer")
        for value, name in (
            (candidates, "candidates"),
            (references_list, "references_list"),
        ):
            if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
                raise TypeError(f"{name} must be a list")
        if len(candidates) != len(references_list):
            raise ValueError("candidates and references_list must have equal length")

        clipped = [0] * max_n
        total = [0] * max_n
        candidate_length = 0
        effective_reference_length = 0

        for candidate, references in zip(candidates, references_list):
            cand_tokens = tokenize(_require_str(candidate, "candidate"))
            ref_token_lists = [tokenize(ref) for ref in _reference_list(references)]
            candidate_length += len(cand_tokens)
            effective_reference_length += _closest_reference_length(
                len(cand_tokens), [len(ref) for ref in ref_token_lists]
            )
            for index, order in enumerate(range(1, max_n + 1)):
                cand_ngrams = Counter(ngrams(cand_tokens, order))
                total[index] += sum(cand_ngrams.values())
                if not cand_ngrams:
                    continue
                max_ref_counts: Counter[tuple[str, ...]] = Counter()
                for ref_tokens in ref_token_lists:
                    for gram, count in Counter(ngrams(ref_tokens, order)).items():
                        max_ref_counts[gram] = max(max_ref_counts[gram], count)
                clipped[index] += sum(
                    min(count, max_ref_counts[gram])
                    for gram, count in cand_ngrams.items()
                )

        return round(
            cls._bleu_from_counts(
                clipped, total, candidate_length, effective_reference_length, smooth
            ),
            constants.SHARE_PRECISION,
        )

    @staticmethod
    def _bleu_from_counts(
        clipped: Sequence[int],
        total: Sequence[int],
        candidate_length: int,
        reference_length: int,
        smooth: bool,
    ) -> float:
        """Combine pooled n-gram counts and lengths into a BLEU score.

        Orders with no candidate n-grams (``total == 0``) are dropped from the
        geometric mean. Under ``smooth``, a present order that had no match is
        floored to ``1 / (total + 1)`` instead of zeroing the product.

        Args:
            clipped: Per-order clipped match counts.
            total: Per-order candidate n-gram counts.
            candidate_length: Total candidate token count.
            reference_length: Total effective reference length.
            smooth: Whether to apply method-1 smoothing.

        Returns:
            The BLEU score in ``[0, 1]``.
        """
        if candidate_length == 0:
            return 0.0
        precisions: list[float] = []
        for matched, produced in zip(clipped, total):
            if produced == 0:
                continue
            if matched == 0:
                if not smooth:
                    return 0.0
                precisions.append(1.0 / (produced + 1))
            else:
                precisions.append(matched / produced)
        if not precisions:
            return 0.0

        brevity_penalty = (
            1.0
            if candidate_length > reference_length
            else exp(1 - reference_length / candidate_length)
        )
        geometric_mean = exp(sum(log(p) for p in precisions) / len(precisions))
        return brevity_penalty * geometric_mean

    # ---------------------------------------------------------------- ROUGE
    @classmethod
    def rouge_n(
        cls, candidate: str, reference: str, n: int = constants.ROUGE_DEFAULT_N
    ) -> RougeScore:
        """ROUGE-N: n-gram overlap precision / recall / F1 (recall is the headline).

        Args:
            candidate: The candidate summary string.
            reference: The gold reference string.
            n: The n-gram order (1 = ROUGE-1, 2 = ROUGE-2, ...).

        Returns:
            The :class:`RougeScore`, each field rounded to
            ``constants.SHARE_PRECISION`` decimals.

        Raises:
            TypeError: If an argument is not a string.
            ValueError: If ``n`` is not positive.
        """
        cand_ngrams = Counter(ngrams(tokenize(_require_str(candidate, "candidate")), n))
        ref_ngrams = Counter(ngrams(tokenize(_require_str(reference, "reference")), n))
        overlap = sum((cand_ngrams & ref_ngrams).values())
        cand_total = sum(cand_ngrams.values())
        ref_total = sum(ref_ngrams.values())
        precision = overlap / cand_total if cand_total else 0.0
        recall = overlap / ref_total if ref_total else 0.0
        return cls._rounded_rouge(precision, recall)

    @classmethod
    def rouge_l(cls, candidate: str, reference: str) -> RougeScore:
        """ROUGE-L: longest-common-subsequence precision / recall / F1.

        Args:
            candidate: The candidate summary string.
            reference: The gold reference string.

        Returns:
            The :class:`RougeScore`, each field rounded to
            ``constants.SHARE_PRECISION`` decimals.

        Raises:
            TypeError: If an argument is not a string.
        """
        cand_tokens = tokenize(_require_str(candidate, "candidate"))
        ref_tokens = tokenize(_require_str(reference, "reference"))
        lcs = _lcs_length(cand_tokens, ref_tokens)
        precision = lcs / len(cand_tokens) if cand_tokens else 0.0
        recall = lcs / len(ref_tokens) if ref_tokens else 0.0
        return cls._rounded_rouge(precision, recall)

    @staticmethod
    def _rounded_rouge(precision: float, recall: float) -> RougeScore:
        """Build a :class:`RougeScore` with each field rounded consistently."""
        digits = constants.SHARE_PRECISION
        return RougeScore(
            precision=round(precision, digits),
            recall=round(recall, digits),
            f1=round(_f1(precision, recall), digits),
        )

    # --------------------------------------------------------------- METEOR
    @classmethod
    def meteor(cls, candidate: str, reference: str, stem: bool = True) -> float:
        """METEOR: recall-weighted unigram Fmean with a fragmentation penalty.

        Matches exact tokens first, then (when ``stem``) light-stem equivalents.
        The score is ``Fmean * (1 - penalty)`` where ``Fmean = P*R /
        (alpha*P + (1-alpha)*R)`` and ``penalty = gamma * (chunks/matches) **
        beta`` (constants ``METEOR_ALPHA/BETA/GAMMA``).

        Args:
            candidate: The candidate string.
            reference: The gold reference string.
            stem: Also match light-stem equivalents (no synonym lexicon).

        Returns:
            The METEOR score in ``[0, 1]``, rounded to
            ``constants.SHARE_PRECISION`` decimals. ``1.0`` when both strings are
            empty; ``0.0`` when exactly one is or nothing aligns.

        Raises:
            TypeError: If an argument is not a string.
        """
        cand_tokens = tokenize(_require_str(candidate, "candidate"))
        ref_tokens = tokenize(_require_str(reference, "reference"))
        if not cand_tokens and not ref_tokens:
            return 1.0
        if not cand_tokens or not ref_tokens:
            return 0.0

        alignment = cls._align(cand_tokens, ref_tokens, stem)
        matches = len(alignment)
        if matches == 0:
            return 0.0

        precision = matches / len(cand_tokens)
        recall = matches / len(ref_tokens)
        alpha = constants.METEOR_ALPHA
        fmean = (precision * recall) / (alpha * precision + (1 - alpha) * recall)

        chunks = cls._count_chunks(alignment)
        penalty = constants.METEOR_GAMMA * (chunks / matches) ** constants.METEOR_BETA
        return round(fmean * (1 - penalty), constants.SHARE_PRECISION)

    @staticmethod
    def _align(
        candidate: Sequence[str], reference: Sequence[str], stem: bool
    ) -> list[tuple[int, int]]:
        """Greedily map candidate tokens to reference tokens (1-1), exact then stem.

        Args:
            candidate: The candidate tokens.
            reference: The reference tokens.
            stem: Whether to run a second light-stem matching pass.

        Returns:
            The matched ``(candidate_index, reference_index)`` pairs.
        """
        reference_used = [False] * len(reference)
        pairs: list[tuple[int, int]] = []

        def match_pass(equal) -> None:
            matched = {cand_index for cand_index, _ in pairs}
            for cand_index, cand_token in enumerate(candidate):
                if cand_index in matched:
                    continue
                for ref_index, ref_token in enumerate(reference):
                    if not reference_used[ref_index] and equal(cand_token, ref_token):
                        reference_used[ref_index] = True
                        pairs.append((cand_index, ref_index))
                        break

        match_pass(lambda cand, ref: cand == ref)
        if stem:
            match_pass(lambda cand, ref: light_stem(cand) == light_stem(ref))
        return pairs

    @staticmethod
    def _count_chunks(pairs: Sequence[tuple[int, int]]) -> int:
        """Count contiguous matched chunks (adjacent in both candidate and reference).

        Args:
            pairs: The matched ``(candidate_index, reference_index)`` pairs.

        Returns:
            The number of chunks; ``0`` for an empty alignment.
        """
        if not pairs:
            return 0
        ordered = sorted(pairs)
        chunks = 1
        for (prev_cand, prev_ref), (cand, ref) in zip(ordered, ordered[1:]):
            if not (cand == prev_cand + 1 and ref == prev_ref + 1):
                chunks += 1
        return chunks
