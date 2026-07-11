"""Deterministic agent-trajectory evaluation for EvalSurfer.

An agent's *trajectory* is the ordered list of tool calls it made on the way to a
final answer. :class:`TrajectoryEvaluator` compares that actual trajectory
against an expected specification and reports structured, deterministic findings:
required tools that were never called, tools that were called but should not have
been, calls made out of the expected order, calls missing required arguments, and
errors the agent never recovered from.

The specification is intentionally partial: every field is optional, so a caller
can constrain only the tool sequence, only the forbidden tools, only the
parameters, or any combination. Whatever the caller does not declare is simply
not checked. The "expected toolset" against which extra tools are judged is the
union of the required, sequenced, and parameter-constrained tools -- but that
rule only fires when the caller positively declared a toolset via
``required_tools`` or ``tool_sequence``; declaring parameters alone never turns
every other tool into an "unnecessary" one.

This module is pure and standard-library-only. It makes no model calls, never
mutates its inputs, and refuses to fabricate the one judgment it cannot make
deterministically -- whether the final answer actually follows from the tool
results -- deferring that to a human or LLM judge via the
``final_answer_consistency`` flag. The finding type names come from
:mod:`constants` (``TRAJECTORY_*``) and error detection reuses
``constants.TOOL_FAILURE_KEYS`` so it stays consistent with the planner.

The implementation is split across focused modules -- :mod:`.schema` (the input
and output dict keys), :mod:`.models` (the :class:`ToolCall` and
:class:`Finding` value objects), and :mod:`.evaluator` (the
:class:`TrajectoryEvaluator` service) -- and re-exported here so that
``from evalsurfer.assurance.trajectory.agent_trace import TrajectoryEvaluator``
keeps working.
"""

from evalsurfer.assurance.trajectory.agent_trace.evaluator import TrajectoryEvaluator
from evalsurfer.assurance.trajectory.agent_trace.models import Finding, ToolCall
from evalsurfer.assurance.trajectory.agent_trace.schema import (
    ACTUAL_TOOL_CALLS_KEY,
    EXPECTED_FORBIDDEN_KEY,
    EXPECTED_PARAMETERS_KEY,
    EXPECTED_REQUIRED_KEY,
    EXPECTED_SEQUENCE_KEY,
    FINAL_ANSWER_CONSISTENCY_KEY,
    FINDING_DETAIL_KEY,
    FINDING_TOOLS_KEY,
    FINDING_TYPE_KEY,
    FINDINGS_KEY,
    NEEDS_JUDGMENT_KEY,
    PARAMETERS_REQUIRED_KEY,
    RECOVERED_AFTER_ERROR_KEY,
    TOOL_ARGUMENTS_KEY,
    TOOL_NAME_KEY,
)

__all__ = ["ToolCall", "Finding", "TrajectoryEvaluator"]
