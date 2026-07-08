"""OpenTelemetry span adapter for EvalSurfer.

OpenTelemetry records each request as a span with nanosecond epoch start/end
timestamps and a bag of attributes. :class:`OtelAdapter` converts spans into the
request-trace dicts :meth:`RequestTrace.from_mapping` accepts: nanosecond
timestamps are divided down to epoch seconds, and input/output token counts are
lifted out of the span attributes when present.

Both attribute encodings are handled -- a plain ``{key: value}`` mapping and the
OTLP ``[{"key", "value": {...}}]`` list -- so real exporter output works
directly. Pure and standard-library-only; no model calls; the input spans are
never mutated.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

__all__ = ["OtelAdapter"]

# Nanoseconds per second: OTel span timestamps are epoch nanoseconds.
_NANOS_PER_SECOND = 1_000_000_000
# OTLP AnyValue wrapper keys, unwrapped to a scalar when reading an attribute.
_OTLP_VALUE_KEYS = ("intValue", "doubleValue", "stringValue", "boolValue")
# Span attribute keys carrying token counts (GenAI semantic conventions plus
# common vendor variants), tried in order.
_INPUT_TOKEN_KEYS = (
    "input_tokens",
    "prompt_tokens",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.prompt_tokens",
    "llm.usage.prompt_tokens",
    "llm.token_count.prompt",
)
_OUTPUT_TOKEN_KEYS = (
    "output_tokens",
    "completion_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.usage.completion_tokens",
    "llm.usage.completion_tokens",
    "llm.token_count.completion",
)


def _otlp_scalar(value: Any) -> Any:
    """Unwrap an OTLP ``AnyValue`` wrapper to its scalar, else return it as-is.

    Args:
        value: An attribute value, possibly an OTLP wrapper like
            ``{"intValue": "42"}``.

    Returns:
        The unwrapped scalar, or ``value`` unchanged when it is not a wrapper.
    """
    if isinstance(value, Mapping):
        for key in _OTLP_VALUE_KEYS:
            if key in value:
                return value[key]
        return None
    return value


def _attribute_map(attributes: Any) -> dict[str, Any]:
    """Normalise span attributes into a flat ``{key: scalar}`` dict.

    Args:
        attributes: Either a ``{key: value}`` mapping or an OTLP list of
            ``{"key", "value"}`` entries; any other type yields an empty dict.

    Returns:
        A new flat dict of attribute keys to unwrapped scalar values.
    """
    flat: dict[str, Any] = {}
    if isinstance(attributes, Mapping):
        for key, value in attributes.items():
            flat[key] = _otlp_scalar(value)
    elif isinstance(attributes, (list, tuple)):
        for item in attributes:
            if isinstance(item, Mapping) and "key" in item:
                flat[item["key"]] = _otlp_scalar(item.get("value"))
    return flat


def _nanos_to_seconds(value: Any) -> float:
    """Convert an epoch-nanosecond timestamp to epoch seconds.

    Args:
        value: The nanosecond timestamp as an int, float, or numeric string.

    Returns:
        The timestamp in epoch seconds.

    Raises:
        TypeError: If ``value`` is a bool or an unsupported type.
        ValueError: If a string value is empty or not numeric.
    """
    if isinstance(value, bool):
        raise TypeError("timestamp must be a number, not a boolean")
    if isinstance(value, (int, float)):
        return value / _NANOS_PER_SECOND
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("timestamp string must not be empty")
        return float(text) / _NANOS_PER_SECOND
    raise TypeError(f"unsupported timestamp type: {type(value).__name__}")


def _first_present(attributes: Mapping[str, Any], keys: Sequence[str]) -> Any:
    """Return the first non-``None`` attribute value among ``keys``.

    Args:
        attributes: A flat attribute map.
        keys: Candidate keys tried in order.

    Returns:
        The first present, non-``None`` value, or ``None`` when none match.
    """
    for key in keys:
        if key in attributes and attributes[key] is not None:
            return attributes[key]
    return None


class OtelAdapter:
    """Convert OpenTelemetry spans into EvalSurfer request-trace dicts.

    Stateless: every conversion is derived from the span data with no
    per-instance state, so the class is a cohesive namespace.
    """

    @staticmethod
    def to_traces(spans: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenTelemetry spans into request-trace dicts.

        Each span's ``startTimeUnixNano`` becomes ``request_started_at`` and its
        ``endTimeUnixNano`` becomes ``response_completed_at`` (both in epoch
        seconds); ``input_tokens`` / ``output_tokens`` are added when the span's
        attributes carry them.

        Args:
            spans: OpenTelemetry spans, each a mapping with at least
                ``startTimeUnixNano`` and optionally ``endTimeUnixNano`` and
                ``attributes``.

        Returns:
            A list of trace dicts that :meth:`RequestTrace.from_mapping` accepts.
            The input spans are never mutated.

        Raises:
            TypeError: If ``spans`` is not a list/tuple, a span is not a mapping,
                or a timestamp has an unsupported type.
            ValueError: If a span has no ``startTimeUnixNano``.
        """
        if not isinstance(spans, (list, tuple)):
            raise TypeError("spans must be a list of span mappings")

        traces: list[dict[str, Any]] = []
        for span in spans:
            if not isinstance(span, Mapping):
                raise TypeError("each span must be a mapping")
            traces.append(OtelAdapter._to_trace(span))
        return traces

    @staticmethod
    def _to_trace(span: Mapping[str, Any]) -> dict[str, Any]:
        """Convert one span into a request-trace dict.

        Args:
            span: A single OpenTelemetry span mapping.

        Returns:
            The trace dict for the span.

        Raises:
            TypeError: If a timestamp has an unsupported type.
            ValueError: If the span has no ``startTimeUnixNano``.
        """
        start = span.get("startTimeUnixNano")
        if start is None:
            raise ValueError("span is missing 'startTimeUnixNano'")

        trace: dict[str, Any] = {"request_started_at": _nanos_to_seconds(start)}
        end = span.get("endTimeUnixNano")
        if end is not None:
            trace["response_completed_at"] = _nanos_to_seconds(end)

        attributes = _attribute_map(span.get("attributes"))
        input_tokens = _first_present(attributes, _INPUT_TOKEN_KEYS)
        if input_tokens is not None:
            trace["input_tokens"] = input_tokens
        output_tokens = _first_present(attributes, _OUTPUT_TOKEN_KEYS)
        if output_tokens is not None:
            trace["output_tokens"] = output_tokens
        return trace
