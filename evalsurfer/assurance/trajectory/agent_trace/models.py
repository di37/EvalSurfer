"""Trajectory value objects -- the parsed tool call and the finding.

Frozen dataclasses only: :class:`ToolCall` (one parsed call from an actual
trajectory) and :class:`Finding` (one deterministic finding). The evaluation
logic that produces them lives in
:mod:`evalsurfer.assurance.trajectory.agent_trace.evaluator`; the output dict
keys :class:`Finding` renders to come from
:mod:`evalsurfer.assurance.trajectory.agent_trace.schema`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evalsurfer.assurance.trajectory.agent_trace.schema import (
    FINDING_DETAIL_KEY,
    FINDING_TOOLS_KEY,
    FINDING_TYPE_KEY,
)

__all__ = ["ToolCall", "Finding"]


@dataclass(frozen=True)
class ToolCall:
    """One parsed tool call from an actual trajectory.

    Only the fields the evaluator needs are retained: the tool ``name`` (or
    ``None`` when absent or non-string), the set of argument *names* the call
    supplied, and whether the call recorded an error.
    """

    name: str | None
    argument_names: frozenset[str]
    errored: bool


@dataclass(frozen=True)
class Finding:
    """A single deterministic trajectory finding.

    ``type`` is one of the ``constants.TRAJECTORY_*`` names, ``detail`` is a
    human-readable explanation, and ``tools`` lists the tool names the finding
    concerns in a deterministic order.
    """

    type: str
    detail: str
    tools: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Render the finding as a JSON-ready dict.

        Returns:
            ``{"type": <type>, "detail": <detail>, "tools": [<tool>, ...]}``.
        """
        return {
            FINDING_TYPE_KEY: self.type,
            FINDING_DETAIL_KEY: self.detail,
            FINDING_TOOLS_KEY: list(self.tools),
        }
