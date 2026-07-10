"""Shared, deterministic text preparation for the quality metrics.

Every reference-based metric (BLEU, ROUGE, METEOR, token-F1, exact match) needs
to turn a string into comparable units. Those steps live here once so the
metrics agree on tokenization and normalization. Pure and standard-library only
-- no model calls, no external data. Inputs are never mutated.
"""

from __future__ import annotations

import re
import string
from typing import Sequence

import evalsurfer.constants as constants

__all__ = [
    "tokenize",
    "normalize_answer",
    "normalized_tokens",
    "ngrams",
    "light_stem",
]

# One or more word characters (letters, digits, underscore). Punctuation and
# whitespace are separators, so tokenization is locale-independent and stable.
_WORD_RE = re.compile(r"\w+", re.UNICODE)

# Punctuation stripped by SQuAD-style normalization, as a fast translation table.
_PUNCTUATION_TABLE = str.maketrans("", "", string.punctuation)

# Common inflectional suffixes stripped by :func:`light_stem`, longest first so
# that e.g. ``"ies"`` is tried before ``"s"``.
_LIGHT_SUFFIXES = ("ies", "ing", "ted", "ed", "es", "ly", "s")
_MIN_STEM_LENGTH = 3


def tokenize(text: str) -> list[str]:
    """Split text into lowercase word tokens.

    Args:
        text: The string to tokenize.

    Returns:
        The lowercase word tokens, in order; punctuation and whitespace are
        dropped. A non-word string yields an empty list.

    Raises:
        TypeError: If ``text`` is not a string.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _WORD_RE.findall(text.lower())


def normalize_answer(text: str) -> str:
    """Normalize an answer the SQuAD way for exact-match comparison.

    Lowercases, removes punctuation, drops the articles in
    ``constants.NORMALIZE_ARTICLES``, and collapses runs of whitespace to a
    single space.

    Args:
        text: The answer string to normalize.

    Returns:
        The normalized string.

    Raises:
        TypeError: If ``text`` is not a string.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    lowered = text.lower().translate(_PUNCTUATION_TABLE)
    kept = [
        word for word in lowered.split() if word not in constants.NORMALIZE_ARTICLES
    ]
    return " ".join(kept)


def normalized_tokens(text: str) -> list[str]:
    """Return the whitespace tokens of :func:`normalize_answer` output.

    Args:
        text: The answer string.

    Returns:
        The normalized tokens, used by token-overlap F1.
    """
    return normalize_answer(text).split()


def ngrams(tokens: Sequence[str], n: int) -> list[tuple[str, ...]]:
    """Build the list of contiguous n-grams from a token sequence.

    Args:
        tokens: The token sequence.
        n: The n-gram order (a positive integer).

    Returns:
        The n-grams as tuples, in order; empty when ``len(tokens) < n``.

    Raises:
        ValueError: If ``n`` is not a positive integer.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("n must be a positive integer")
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def light_stem(token: str) -> str:
    """Strip a common English inflectional suffix (a light, dependency-free stem).

    This is a deliberately small stemmer -- it removes a single trailing
    ``-ies/-ing/-ted/-ed/-es/-ly/-s`` when a stem of at least
    ``_MIN_STEM_LENGTH`` characters remains. It is *not* a full Porter stemmer
    and carries no synonym lexicon; it only lets METEOR match obvious
    inflections (``"walk"`` vs ``"walked"``, ``"cat"`` vs ``"cats"``). It does
    not undo consonant doubling, so ``"run"`` / ``"running"`` do not match. See
    :mod:`evalsurfer.quality.text`.

    Args:
        token: A single lowercase token.

    Returns:
        The stemmed token, or the original when no suffix applies.
    """
    for suffix in _LIGHT_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= _MIN_STEM_LENGTH:
            return token[: -len(suffix)]
    return token
