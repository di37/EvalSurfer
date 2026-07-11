"""Contamination controls for the golden dataset artifact.

A golden dataset is only trustworthy if it is free of accidental leakage: exact
content duplicates that inflate agreement, blocked terms that must never appear,
and canary strings planted to detect train/test contamination. These are pure,
standard-library-only checks over case-like objects (anything exposing
``id`` / ``input`` / ``gold_answer`` / ``gold_label`` / ``content_hash``).

:func:`content_hash` is the single canonical hashing implementation, reused by
:class:`~evalsurfer.metrics.dataset.case.DatasetCase`, so a case's id and a duplicate
check always agree on what "the same case" means. Magic values come from
:mod:`evalsurfer.constants`.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Iterable, Sequence

import evalsurfer.constants as constants

if TYPE_CHECKING:  # pragma: no cover - typing only; avoids an import cycle
    from evalsurfer.metrics.dataset.case import DatasetCase

__all__ = [
    "content_hash",
    "find_duplicates",
    "blocklist_hits",
    "canary_hits",
    "report",
]


def content_hash(
    input: str,
    gold_answer: str | None,
    gold_label: str | None,
    gold_score: float | None,
) -> str:
    """Hash a case's content into a stable, order-independent digest.

    The digest is the SHA-256 of a canonical ``json.dumps(..., sort_keys=True)``
    encoding of the content fields only. Coverage tags and the held-out flag are
    deliberately excluded: they describe a case, they are not the case, so
    re-tagging or re-splitting never changes a case's identity.

    Args:
        input: The case input text.
        gold_answer: The gold answer, or ``None``.
        gold_label: The gold label, or ``None``.
        gold_score: The gold score, or ``None``.

    Returns:
        The 64-character hexadecimal SHA-256 digest of the canonical content.
    """
    canonical = json.dumps(
        {
            "input": input,
            "gold_answer": gold_answer,
            "gold_label": gold_label,
            "gold_score": gold_score,
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _text_fields(case: "DatasetCase") -> list[str]:
    """Collect a case's searchable text fields, skipping absent ones.

    Args:
        case: The dataset case.

    Returns:
        The present string fields among input, gold answer, and gold label.
    """
    return [
        field
        for field in (case.input, case.gold_answer, case.gold_label)
        if isinstance(field, str)
    ]


def find_duplicates(cases: Sequence["DatasetCase"]) -> list[list[str]]:
    """Group case ids that share an identical content hash.

    Args:
        cases: The cases to scan.

    Returns:
        One list of ids per duplicated content hash (groups of two or more),
        ordered by the content's first appearance and, within a group, by case
        order.
    """
    groups: dict[str, list[str]] = {}
    for case in cases:
        groups.setdefault(case.content_hash, []).append(case.id)
    return [ids for ids in groups.values() if len(ids) >= 2]


def blocklist_hits(cases: Sequence["DatasetCase"], terms: Iterable[str]) -> list[str]:
    """Find cases whose text contains any blocked term (case-insensitive).

    Args:
        cases: The cases to scan.
        terms: Blocked substrings; empty or non-string terms are ignored.

    Returns:
        The ids of cases matching at least one term, in case order (each id at
        most once).
    """
    needles = [term.lower() for term in terms if isinstance(term, str) and term]
    if not needles:
        return []
    hits: list[str] = []
    for case in cases:
        fields = [field.lower() for field in _text_fields(case)]
        if any(needle in field for field in fields for needle in needles):
            hits.append(case.id)
    return hits


def canary_hits(cases: Sequence["DatasetCase"], canaries: Iterable[str]) -> list[str]:
    """Find cases whose text contains any canary string (exact, case-sensitive).

    Canaries are planted markers, so the match is deliberately exact -- a
    case-folded near-miss is not a leak.

    Args:
        cases: The cases to scan.
        canaries: Canary substrings; empty or non-string canaries are ignored.

    Returns:
        The ids of cases containing at least one canary, in case order (each id
        at most once).
    """
    needles = [canary for canary in canaries if isinstance(canary, str) and canary]
    if not needles:
        return []
    hits: list[str] = []
    for case in cases:
        fields = _text_fields(case)
        if any(needle in field for field in fields for needle in needles):
            hits.append(case.id)
    return hits


def report(
    cases: Sequence["DatasetCase"],
    blocklist: Iterable[str] = (),
    canaries: Iterable[str] = (),
) -> dict[str, list]:
    """Build the full contamination report for a set of cases.

    Args:
        cases: The cases to scan.
        blocklist: Terms that must not appear (case-insensitive).
        canaries: Canary strings to detect leakage (exact match).

    Returns:
        A mapping keyed by the three contamination sections
        (:data:`~evalsurfer.constants.CONTAMINATION_DUPLICATES`,
        :data:`~evalsurfer.constants.CONTAMINATION_BLOCKLIST_HITS`,
        :data:`~evalsurfer.constants.CONTAMINATION_CANARY_HITS`), each mapped to
        a list of case ids (or, for duplicates, a list of id groups).
    """
    return {
        constants.CONTAMINATION_DUPLICATES: find_duplicates(cases),
        constants.CONTAMINATION_BLOCKLIST_HITS: blocklist_hits(cases, blocklist),
        constants.CONTAMINATION_CANARY_HITS: canary_hits(cases, canaries),
    }
