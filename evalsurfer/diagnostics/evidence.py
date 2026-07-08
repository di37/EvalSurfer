"""Structured evidence for a criterion score in EvalSurfer.

A judge attaches evidence to justify a criterion score. Historically that was a
single free-text string; this module upgrades it to a small structured record
without breaking legacy inputs. :class:`Evidence` captures the claim being made,
the supporting context that backs it, any mismatch between the answer and that
context, and an optional confidence in
``[constants.CONFIDENCE_MIN, constants.CONFIDENCE_MAX]``.

The class also owns the two behaviours that used to be module functions:
:meth:`Evidence.normalize` coerces legacy or structured input into a validated
plain dict, and :meth:`Evidence.to_dict` serialises an instance to the same
shape. Everything here is deterministic and operates on plain values only: it
never mutates its inputs, makes no model or network calls, and depends on the
standard library alone. It deliberately does not touch report.schema.json --
callers embed the returned plain dicts wherever a criterion's ``evidence`` field
lives.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

import evalsurfer.constants as constants

__all__ = ["Evidence"]


@dataclass(frozen=True)
class Evidence:
    """Structured justification for a single criterion score.

    Attributes:
        claim: The assertion the judge is making about the answer.
        supporting_context: Optional text backing the claim; omitted from the
            serialized dict when empty.
        mismatch: Optional description of a discrepancy; omitted when empty.
        confidence: Optional confidence in
            ``[constants.CONFIDENCE_MIN, constants.CONFIDENCE_MAX]``, or ``None``
            when the judge did not report one.
    """

    claim: str
    supporting_context: str = ""
    mismatch: str = ""
    confidence: float | None = None

    @classmethod
    def normalize(cls, value: Any) -> dict[str, Any]:
        """Coerce legacy or structured evidence into a validated plain dict.

        A plain string is legacy free-text and becomes
        ``{constants.EVIDENCE_CLAIM_FIELD: value}``. A mapping may carry any of
        the claim, the text fields in ``constants.EVIDENCE_TEXT_FIELDS``, and
        ``constants.CONFIDENCE_FIELD``; empty optional text fields are omitted
        and confidence is kept only when it is a finite float in
        ``[constants.CONFIDENCE_MIN, constants.CONFIDENCE_MAX]``. The input is
        never mutated.

        Args:
            value: A free-text string or a mapping of evidence fields.

        Returns:
            A validated plain dict carrying the claim plus any non-empty
            optional fields.

        Raises:
            TypeError: If ``value`` is neither a string nor a mapping.
            ValueError: If a text field is not a string, or confidence is out of
                range or not ``None``/finite float.
        """
        if isinstance(value, str):
            return {constants.EVIDENCE_CLAIM_FIELD: value}
        if isinstance(value, Mapping):
            return cls._normalize_mapping(value)
        raise TypeError("evidence must be a string or a mapping")

    @staticmethod
    def to_dict(ev: "Evidence") -> dict[str, Any]:
        """Serialize an :class:`Evidence` to a plain dict, omitting empty fields.

        Confidence is included only when it is not ``None`` and the empty text
        fields are dropped. Delegates to :meth:`normalize` so a dataclass and an
        equivalent mapping serialize identically.

        Args:
            ev: The evidence to serialize.

        Returns:
            A validated plain dict carrying the claim plus any non-empty
            optional fields.

        Raises:
            TypeError: If ``ev`` is not an :class:`Evidence` instance.
            ValueError: If ``ev.confidence`` is out of range or otherwise
                invalid.
        """
        if not isinstance(ev, Evidence):
            raise TypeError("ev must be an Evidence instance")
        mapping: dict[str, Any] = {constants.EVIDENCE_CLAIM_FIELD: ev.claim}
        for field_name in constants.EVIDENCE_TEXT_FIELDS:
            mapping[field_name] = getattr(ev, field_name)
        mapping[constants.CONFIDENCE_FIELD] = ev.confidence
        return Evidence.normalize(mapping)

    @classmethod
    def _normalize_mapping(cls, value: Mapping[str, Any]) -> dict[str, Any]:
        """Build a validated evidence dict from a mapping, omitting empty fields.

        Args:
            value: A mapping of evidence fields; unknown keys are ignored.

        Returns:
            The validated plain dict.

        Raises:
            ValueError: If a text field is not a string, or confidence is
                invalid.
        """
        claim_field = constants.EVIDENCE_CLAIM_FIELD
        result: dict[str, Any] = {
            claim_field: cls._validate_text(value.get(claim_field, ""), claim_field)
        }
        for field_name in constants.EVIDENCE_TEXT_FIELDS:
            text = cls._validate_text(value.get(field_name, ""), field_name)
            if text:
                result[field_name] = text
        confidence = cls._validate_confidence(value.get(constants.CONFIDENCE_FIELD))
        if confidence is not None:
            result[constants.CONFIDENCE_FIELD] = confidence
        return result

    @staticmethod
    def _validate_text(value: Any, field_name: str) -> str:
        """Require a string; reject other types at the boundary.

        Args:
            value: The candidate text value.
            field_name: The field name, used only in the error message.

        Returns:
            The value unchanged when it is a string.

        Raises:
            ValueError: If ``value`` is not a string.
        """
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        return value

    @staticmethod
    def _validate_confidence(value: Any) -> float | None:
        """Require ``None`` or a finite float in the confidence range.

        Args:
            value: The candidate confidence value.

        Returns:
            ``None`` when ``value`` is ``None``, otherwise the value as a float
            rounded to ``constants.SHARE_PRECISION`` decimals.

        Raises:
            ValueError: If ``value`` is a bool, a non-number, non-finite, or
                outside ``[constants.CONFIDENCE_MIN, constants.CONFIDENCE_MAX]``.
        """
        out_of_range = (
            "confidence must be a float in "
            f"[{constants.CONFIDENCE_MIN}, {constants.CONFIDENCE_MAX}] or None"
        )
        if value is None:
            return None
        # bool is an int subclass -- exclude it so True/False are not 1/0.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(out_of_range)
        confidence = float(value)
        if not isfinite(confidence) or not (
            constants.CONFIDENCE_MIN <= confidence <= constants.CONFIDENCE_MAX
        ):
            raise ValueError(out_of_range)
        return round(confidence, constants.SHARE_PRECISION)
