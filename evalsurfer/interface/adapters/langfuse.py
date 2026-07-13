"""Langfuse observation adapter for EvalSurfer.

Langfuse records each traced LLM call as an observation (a *generation*) with
ISO-8601 ``startTime`` / ``endTime`` timestamps, a ``completionStartTime`` for
the first streamed token, token usage, and an error ``level``.
:class:`LangfuseAdapter` converts observations into the request-trace dicts
:meth:`RequestTrace.from_mapping` accepts -- notably mapping
``completionStartTime`` onto ``first_token_at``, so Langfuse telemetry feeds
EvalSurfer's TTFT and inter-token-latency metrics directly.

Both the API's camelCase JSON and the Python SDK's snake_case shapes are read
via the shared ``get_nested`` helper. A trace object that nests an
``observations`` list is flattened one level, keeping only its generations
(other span types are not request-shaped). Pure and standard-library-only; no
model calls; the input observations are never mutated.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from evalsurfer.metrics.operational.metrics import get_nested

__all__ = ["LangfuseAdapter"]

# Timestamp field aliases on a Langfuse observation, tried in order.
_START_KEYS = ("startTime", "start_time")
_END_KEYS = ("endTime", "end_time")
# First streamed token (generations only) -> EvalSurfer's first_token_at.
_FIRST_TOKEN_KEYS = ("completionStartTime", "completion_start_time")
# Token-usage paths (dot-separated for nested blocks), tried in order: the
# current ``usage`` / ``usageDetails`` blocks first, then the legacy flat fields.
_INPUT_TOKEN_PATHS = (
    "usage.input",
    "usageDetails.input",
    "usage_details.input",
    "usage.promptTokens",
    "usage.prompt_tokens",
    "promptTokens",
    "prompt_tokens",
)
_OUTPUT_TOKEN_PATHS = (
    "usage.output",
    "usageDetails.output",
    "usage_details.output",
    "usage.completionTokens",
    "usage.completion_tokens",
    "completionTokens",
    "completion_tokens",
)
_STATUS_MESSAGE_KEYS = ("statusMessage", "status_message")
_ERROR_LEVEL = "ERROR"
_GENERATION_TYPE = "GENERATION"


class LangfuseAdapter:
    """Convert Langfuse observations into EvalSurfer request-trace dicts.

    Stateless: every conversion is derived from the observation data with no
    per-instance state, so the class is a cohesive namespace.
    """

    @staticmethod
    def to_traces(observations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Convert Langfuse observations into request-trace dicts.

        Each observation's ``startTime`` becomes ``request_started_at``,
        ``endTime`` becomes ``response_completed_at``, and
        ``completionStartTime`` becomes ``first_token_at``. Token counts are
        lifted from ``usage`` / ``usageDetails`` blocks or the legacy flat
        fields, and an observation with ``level == "ERROR"`` is marked failed
        via its ``statusMessage``.

        An entry that carries a nested ``observations`` list (a Langfuse
        *trace* object) is flattened one level: its generations (and untyped
        observations) are converted, while spans/events are skipped -- they are
        not request-shaped. Entries passed directly are converted as-is; the
        caller has already curated them.

        Args:
            observations: Langfuse observations (or trace objects nesting
                them), each a mapping with at least a start timestamp.

        Returns:
            A list of trace dicts that :meth:`RequestTrace.from_mapping`
            accepts. The input observations are never mutated.

        Raises:
            TypeError: If ``observations`` is not a list/tuple or an entry is
                not a mapping.
            ValueError: If an observation has no start timestamp.
        """
        if not isinstance(observations, (list, tuple)):
            raise TypeError("observations must be a list of observation mappings")

        traces: list[dict[str, Any]] = []
        for entry in observations:
            if not isinstance(entry, Mapping):
                raise TypeError("each observation must be a mapping")
            nested = entry.get("observations")
            if isinstance(nested, (list, tuple)):
                for observation in nested:
                    if not isinstance(observation, Mapping):
                        raise TypeError("each nested observation must be a mapping")
                    if LangfuseAdapter._is_generation(observation):
                        traces.append(LangfuseAdapter._to_trace(observation))
            else:
                traces.append(LangfuseAdapter._to_trace(entry))
        return traces

    @staticmethod
    def _is_generation(observation: Mapping[str, Any]) -> bool:
        """Whether a nested observation is a generation (or carries no type).

        Args:
            observation: One observation from a trace object's nested list.

        Returns:
            ``True`` for generations and untyped observations; ``False`` for
            spans/events, which describe internal steps rather than requests.
        """
        observation_type = observation.get("type")
        if observation_type is None:
            return True
        return (
            isinstance(observation_type, str)
            and observation_type.upper() == _GENERATION_TYPE
        )

    @staticmethod
    def _to_trace(observation: Mapping[str, Any]) -> dict[str, Any]:
        """Convert one Langfuse observation into a request-trace dict.

        Args:
            observation: A single Langfuse observation mapping.

        Returns:
            The trace dict for the observation.

        Raises:
            ValueError: If the observation has no start timestamp.
        """
        started_at = get_nested(observation, _START_KEYS)
        if started_at is None:
            raise ValueError("observation is missing a start timestamp")

        trace: dict[str, Any] = {"request_started_at": started_at}
        completed_at = get_nested(observation, _END_KEYS)
        if completed_at is not None:
            trace["response_completed_at"] = completed_at
        first_token_at = get_nested(observation, _FIRST_TOKEN_KEYS)
        if first_token_at is not None:
            trace["first_token_at"] = first_token_at

        input_tokens = get_nested(observation, _INPUT_TOKEN_PATHS)
        if input_tokens is not None:
            trace["input_tokens"] = input_tokens
        output_tokens = get_nested(observation, _OUTPUT_TOKEN_PATHS)
        if output_tokens is not None:
            trace["output_tokens"] = output_tokens

        level = observation.get("level")
        if isinstance(level, str) and level.upper() == _ERROR_LEVEL:
            status = get_nested(observation, _STATUS_MESSAGE_KEYS)
            trace["error"] = (
                status if isinstance(status, str) and status else _ERROR_LEVEL
            )
        return trace
