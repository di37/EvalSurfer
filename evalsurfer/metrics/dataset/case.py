"""The golden dataset case: one immutable, content-addressed evaluation item.

A :class:`DatasetCase` pairs an input with optional gold references (answer,
label, score) and coverage metadata (tags, held-out flag). Its identity is
content-derived: :func:`~evalsurfer.metrics.dataset.contamination.content_hash` hashes
the content fields, the id is a short prefix of that hash, and both are recomputed
from content -- never trusted from untrusted input -- so the same content always
yields the same id across versions and machines.

Everything here is pure and standard-library only. Cases are frozen; validation
is fail-fast at construction. Magic values come from :mod:`evalsurfer.constants`.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.metrics.dataset.contamination import content_hash as compute_content_hash

__all__ = ["DatasetCase"]


def _validate_input(value: Any) -> str:
    """Validate that a case input is a non-empty string.

    Args:
        value: The candidate input.

    Returns:
        The validated input string, unchanged.

    Raises:
        ValueError: If the value is not a string or is blank.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("case input must be a non-empty string")
    return value


def _validate_optional_text(value: Any, field_name: str) -> str | None:
    """Validate an optional string field.

    Args:
        value: The candidate value, or ``None``.
        field_name: Name used in error messages.

    Returns:
        The string value, or ``None``.

    Raises:
        TypeError: If the value is neither a string nor ``None``.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    return value


def _validate_tags(tags: Any) -> frozenset[str]:
    """Validate coverage tags against the allowed vocabulary.

    Args:
        tags: An iterable of tag strings drawn from
            :data:`~evalsurfer.constants.COVERAGE_TAGS`.

    Returns:
        The validated tags as a frozenset.

    Raises:
        TypeError: If ``tags`` is a string/bytes or not iterable, or a tag is
            not a string.
        ValueError: If a tag is not a known coverage tag.
    """
    if isinstance(tags, (str, bytes)):
        raise TypeError("tags must be an iterable of tags, not a single string")
    try:
        candidates = list(tags)
    except TypeError as exc:
        raise TypeError("tags must be an iterable of tags") from exc
    result: set[str] = set()
    for tag in candidates:
        if not isinstance(tag, str):
            raise TypeError("each tag must be a string")
        if tag not in constants.COVERAGE_TAGS:
            raise ValueError(
                f"unknown coverage tag {tag!r}; allowed: {constants.COVERAGE_TAGS}"
            )
        result.add(tag)
    return frozenset(result)


def _coerce_gold_score(value: Any) -> float | None:
    """Validate and normalise an optional gold score.

    A gold score is a reference score on the criterion scale, so it must fall in
    ``[CRITERION_MIN_SCORE, CRITERION_MAX_SCORE]``. Integers are normalised to
    floats so ``3`` and ``3.0`` hash identically.

    Args:
        value: ``None`` or a finite, non-boolean number.

    Returns:
        The score as a float, or ``None``.

    Raises:
        TypeError: If the value is neither a number nor ``None``.
        ValueError: If the value is a boolean, non-finite, or out of range.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("gold_score must be a number, not a boolean")
    if not isinstance(value, (int, float)):
        raise TypeError("gold_score must be a number or None")
    score = float(value)
    if not isfinite(score):
        raise ValueError("gold_score must be a finite number")
    if not constants.CRITERION_MIN_SCORE <= score <= constants.CRITERION_MAX_SCORE:
        raise ValueError(
            "gold_score must be between "
            f"{constants.CRITERION_MIN_SCORE} and {constants.CRITERION_MAX_SCORE}"
        )
    return score


def _validate_bool(value: Any, field_name: str) -> bool:
    """Validate a strictly boolean flag.

    Args:
        value: The candidate flag.
        field_name: Name used in error messages.

    Returns:
        The validated boolean.

    Raises:
        TypeError: If the value is not a ``bool``.
    """
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean")
    return value


def _resolve_id(id_value: Any, digest: str) -> str:
    """Return the provided id, or derive a stable one from the content digest.

    Args:
        id_value: An explicit id, or ``None`` to derive one.
        digest: The content hash a derived id is based on.

    Returns:
        The case id: the explicit id when given, else
        ``"<DATASET_CASE_ID_PREFIX><first N hex chars of the digest>"``.

    Raises:
        ValueError: If an explicit id is given but is not a non-empty string.
    """
    if id_value is None:
        prefix = constants.DATASET_CASE_ID_PREFIX
        return f"{prefix}{digest[:constants.DATASET_ID_HASH_LENGTH]}"
    if not isinstance(id_value, str) or not id_value.strip():
        raise ValueError("id must be a non-empty string when provided")
    return id_value


@dataclass(frozen=True)
class DatasetCase:
    """One immutable, content-addressed golden evaluation case."""

    id: str
    input: str
    gold_answer: str | None
    gold_label: str | None
    gold_score: float | None
    tags: frozenset[str]
    held_out: bool
    content_hash: str

    @classmethod
    def create(
        cls,
        input: str,
        *,
        gold_answer: str | None = None,
        gold_label: str | None = None,
        gold_score: float | None = None,
        tags: Any = (),
        held_out: bool = False,
        id: str | None = None,
    ) -> "DatasetCase":
        """Validate content, derive identity, and build a frozen case.

        Args:
            input: The case input; must be a non-empty string.
            gold_answer: Optional gold answer text.
            gold_label: Optional gold label text.
            gold_score: Optional gold score in the criterion range.
            tags: Coverage tags from
                :data:`~evalsurfer.constants.COVERAGE_TAGS`.
            held_out: Whether the case belongs to the held-out split.
            id: Optional explicit id; when omitted, a stable id is derived from
                the content hash.

        Returns:
            The validated :class:`DatasetCase`.

        Raises:
            TypeError: If a field has an unsupported type.
            ValueError: If ``input`` is blank, a tag is unknown, ``gold_score``
                is out of range, or an explicit ``id`` is blank.
        """
        text = _validate_input(input)
        answer = _validate_optional_text(gold_answer, "gold_answer")
        label = _validate_optional_text(gold_label, "gold_label")
        score = _coerce_gold_score(gold_score)
        tag_set = _validate_tags(tags)
        held = _validate_bool(held_out, "held_out")
        digest = compute_content_hash(text, answer, label, score)
        return cls(
            id=_resolve_id(id, digest),
            input=text,
            gold_answer=answer,
            gold_label=label,
            gold_score=score,
            tags=tag_set,
            held_out=held,
            content_hash=digest,
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "DatasetCase":
        """Build a case from a mapping, recomputing identity from content.

        Any ``content_hash`` present in ``data`` is ignored and recomputed, so a
        tampered or stale hash can never enter the dataset.

        Args:
            data: A mapping with at least an ``input`` key.

        Returns:
            The parsed :class:`DatasetCase`.

        Raises:
            TypeError: If ``data`` is not a mapping or a field has a bad type.
            ValueError: If ``input`` is missing/blank or a field is invalid.
        """
        if not isinstance(data, Mapping):
            raise TypeError("dataset case must be a mapping")
        if "input" not in data:
            raise ValueError("dataset case requires an 'input' field")
        return cls.create(
            data["input"],
            gold_answer=data.get("gold_answer"),
            gold_label=data.get("gold_label"),
            gold_score=data.get("gold_score"),
            tags=data.get("tags", ()),
            held_out=data.get("held_out", False),
            id=data.get("id"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialise the case to a JSON-ready dict with a stable key order.

        Returns:
            A dict with keys ``id``, ``input``, ``gold_answer``, ``gold_label``,
            ``gold_score``, ``tags`` (a sorted list), ``held_out``, and
            ``content_hash``. Optional text/score fields are emitted as ``null``
            when absent.
        """
        return {
            "id": self.id,
            "input": self.input,
            "gold_answer": self.gold_answer,
            "gold_label": self.gold_label,
            "gold_score": self.gold_score,
            "tags": sorted(self.tags),
            "held_out": self.held_out,
            "content_hash": self.content_hash,
        }
