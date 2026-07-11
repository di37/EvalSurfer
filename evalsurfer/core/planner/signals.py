"""Evidence signals for one evaluation target.

:class:`Signals` is a snapshot of *what evidence is available* for a target --
is there an answer? retrieved context? tool calls? a multi-turn history?
operational traces? -- and :meth:`Signals.from_sample` infers it from a raw
sample dict using the common field-name aliases in :mod:`constants`. The private
helpers below (``_truthy`` / ``_first_present`` / ``_has_tool_failure``) exist
only to serve that inference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants

__all__ = ["Signals"]


@dataclass(frozen=True)
class Signals:
    """What evidence is available for one evaluation target.

    ``safety_relevant`` defaults to ``True``: safety is assessed by default and
    must be opted out of deliberately.
    """

    answer: bool = False
    retrieved_context: bool = False
    citations: bool = False
    tool_calls: bool = False
    tool_failure: bool = False
    multi_turn: bool = False
    operational_traces: bool = False
    safety_relevant: bool = True

    @classmethod
    def from_sample(cls, sample: Mapping[str, Any]) -> "Signals":
        """Infer signals from a raw sample dict using common field names.

        Args:
            sample: An evaluation sample; recognised keys are listed in
                :mod:`constants` (``SAMPLE_*`` aliases). ``safety_relevant``
                honours an explicit ``safety_relevant: false`` opt-out.

        Returns:
            The inferred :class:`Signals`.

        Raises:
            TypeError: If ``sample`` is not a mapping.
            ValueError: If ``safety_relevant`` is present but not a bool.
        """
        if not isinstance(sample, Mapping):
            raise TypeError("sample must be a mapping")

        tool_calls = _first_present(sample, constants.SAMPLE_TOOL_KEYS)
        history = _first_present(sample, constants.SAMPLE_HISTORY_KEYS)
        multi_turn = isinstance(history, (list, tuple)) and len(history) > 1

        safety_relevant = sample.get(constants.SIGNAL_SAFETY_RELEVANT, True)
        if not isinstance(safety_relevant, bool):
            raise ValueError("safety_relevant must be a boolean")

        return cls(
            answer=_truthy(_first_present(sample, constants.SAMPLE_ANSWER_KEYS)),
            retrieved_context=_truthy(_first_present(sample, constants.SAMPLE_CONTEXT_KEYS)),
            citations=_truthy(_first_present(sample, constants.SAMPLE_CITATION_KEYS)),
            tool_calls=_truthy(tool_calls),
            tool_failure=_has_tool_failure(tool_calls),
            multi_turn=multi_turn,
            operational_traces=_truthy(_first_present(sample, constants.SAMPLE_TRACE_KEYS)),
            safety_relevant=safety_relevant,
        )


def _truthy(value: Any) -> bool:
    """Report whether a value counts as present (non-empty)."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict, bytes)):
        return len(value) > 0
    return bool(value)


def _first_present(data: Mapping[str, Any], keys: Sequence[str]) -> Any:
    """Return the first non-``None`` value among ``keys``, else ``None``."""
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _has_tool_failure(tool_calls: Any) -> bool:
    """Report whether any tool call in the list recorded a failure."""
    if not isinstance(tool_calls, (list, tuple)):
        return False
    return any(
        isinstance(call, Mapping) and any(call.get(key) for key in constants.TOOL_FAILURE_KEYS)
        for call in tool_calls
    )
