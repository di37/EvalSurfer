"""The golden dataset case value object.

Frozen dataclass only: :class:`DatasetCase` pairs an input with optional gold
references and coverage metadata, deriving a content-addressed identity at
construction. The fail-fast validators it relies on live in
:mod:`evalsurfer.metrics.dataset.case.helpers`, and the canonical hashing
implementation in :mod:`evalsurfer.metrics.dataset.contamination`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from evalsurfer.metrics.dataset.case.helpers import (
    _coerce_gold_score,
    _resolve_id,
    _validate_bool,
    _validate_input,
    _validate_optional_text,
    _validate_tags,
)
from evalsurfer.metrics.dataset.contamination import content_hash as compute_content_hash


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
