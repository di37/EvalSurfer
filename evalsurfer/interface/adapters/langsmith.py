"""LangSmith run adapter for EvalSurfer.

LangSmith records each traced call as a run with ISO-8601 ``start_time`` /
``end_time`` timestamps and, when the provider reports it, token usage.
:class:`LangSmithAdapter` converts runs into the request-trace dicts
:meth:`RequestTrace.from_mapping` accepts, relocating the timestamps and token
counts onto EvalSurfer's canonical keys.

Token usage is read from the common LangSmith shapes -- top-level fields and a
nested ``usage_metadata`` / ``usage`` block -- via the shared ``get_nested``
helper. Pure and standard-library-only; no model calls; the input runs are never
mutated.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from evalsurfer.metrics.operational.metrics import get_nested

__all__ = ["LangSmithAdapter"]

# Timestamp field aliases on a LangSmith run, tried in order.
_START_KEYS = ("start_time", "start", "startTime")
_END_KEYS = ("end_time", "end", "endTime")
# Token-usage paths (dot-separated for nested blocks), tried in order.
_INPUT_TOKEN_PATHS = (
    "input_tokens",
    "prompt_tokens",
    "usage_metadata.input_tokens",
    "usage_metadata.prompt_tokens",
    "usage.input_tokens",
    "usage.prompt_tokens",
)
_OUTPUT_TOKEN_PATHS = (
    "output_tokens",
    "completion_tokens",
    "usage_metadata.output_tokens",
    "usage_metadata.completion_tokens",
    "usage.output_tokens",
    "usage.completion_tokens",
)


class LangSmithAdapter:
    """Convert LangSmith runs into EvalSurfer request-trace dicts.

    Stateless: every conversion is derived from the run data with no per-instance
    state, so the class is a cohesive namespace.
    """

    @staticmethod
    def to_traces(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Convert LangSmith runs into request-trace dicts.

        Each run's ``start_time`` becomes ``request_started_at`` and its
        ``end_time`` becomes ``response_completed_at``; input/output token counts
        are lifted from the run's top-level or nested ``usage_metadata`` /
        ``usage`` fields when present.

        Args:
            runs: LangSmith runs, each a mapping with at least a start timestamp.

        Returns:
            A list of trace dicts that :meth:`RequestTrace.from_mapping` accepts.
            The input runs are never mutated.

        Raises:
            TypeError: If ``runs`` is not a list/tuple or a run is not a mapping.
            ValueError: If a run has no start timestamp.
        """
        if not isinstance(runs, (list, tuple)):
            raise TypeError("runs must be a list of run mappings")

        traces: list[dict[str, Any]] = []
        for run in runs:
            if not isinstance(run, Mapping):
                raise TypeError("each run must be a mapping")
            traces.append(LangSmithAdapter._to_trace(run))
        return traces

    @staticmethod
    def _to_trace(run: Mapping[str, Any]) -> dict[str, Any]:
        """Convert one LangSmith run into a request-trace dict.

        Args:
            run: A single LangSmith run mapping.

        Returns:
            The trace dict for the run.

        Raises:
            ValueError: If the run has no start timestamp.
        """
        started_at = get_nested(run, _START_KEYS)
        if started_at is None:
            raise ValueError("run is missing a start timestamp")

        trace: dict[str, Any] = {"request_started_at": started_at}
        completed_at = get_nested(run, _END_KEYS)
        if completed_at is not None:
            trace["response_completed_at"] = completed_at

        input_tokens = get_nested(run, _INPUT_TOKEN_PATHS)
        if input_tokens is not None:
            trace["input_tokens"] = input_tokens
        output_tokens = get_nested(run, _OUTPUT_TOKEN_PATHS)
        if output_tokens is not None:
            trace["output_tokens"] = output_tokens
        return trace
