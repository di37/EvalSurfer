"""Signals the planner reasons about.

Evidence signals available for a target, their human-readable descriptions, and
the field-name aliases used when inferring signals from a raw sample dict.
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Signals the planner reasons about (evidence available for a target)
# --------------------------------------------------------------------------- #
SIGNAL_ANSWER: Final = "answer"
SIGNAL_RETRIEVED_CONTEXT: Final = "retrieved_context"
SIGNAL_CITATIONS: Final = "citations"
SIGNAL_TOOL_CALLS: Final = "tool_calls"
SIGNAL_TOOL_FAILURE: Final = "tool_failure"
SIGNAL_MULTI_TURN: Final = "multi_turn"
SIGNAL_OPERATIONAL_TRACES: Final = "operational_traces"
SIGNAL_SAFETY_RELEVANT: Final = "safety_relevant"
SIGNALS: Final = (
    SIGNAL_ANSWER,
    SIGNAL_RETRIEVED_CONTEXT,
    SIGNAL_CITATIONS,
    SIGNAL_TOOL_CALLS,
    SIGNAL_TOOL_FAILURE,
    SIGNAL_MULTI_TURN,
    SIGNAL_OPERATIONAL_TRACES,
    SIGNAL_SAFETY_RELEVANT,
)

SIGNAL_DESCRIPTIONS: Final = {
    SIGNAL_ANSWER: "an answer to evaluate",
    SIGNAL_RETRIEVED_CONTEXT: "retrieved context",
    SIGNAL_CITATIONS: "citations in the answer",
    SIGNAL_TOOL_CALLS: "tool calls",
    SIGNAL_TOOL_FAILURE: "a tool failure to recover from",
    SIGNAL_MULTI_TURN: "multi-turn conversation history",
    SIGNAL_OPERATIONAL_TRACES: "operational traces",
    SIGNAL_SAFETY_RELEVANT: "safety relevance (opted out)",
}

# Field-name aliases used when inferring signals from a raw sample dict.
SAMPLE_ANSWER_KEYS: Final = ("answer", "output", "response")
SAMPLE_CONTEXT_KEYS: Final = ("retrieved_docs", "retrieved_context", "context", "chunks")
SAMPLE_CITATION_KEYS: Final = ("citations", "sources")
SAMPLE_TOOL_KEYS: Final = ("tool_calls", "tool_traces", "tools")
SAMPLE_HISTORY_KEYS: Final = ("conversation_history", "history", "messages")
SAMPLE_TRACE_KEYS: Final = ("traces", "trace", "timing", "latency")
TOOL_FAILURE_KEYS: Final = ("error", "failed", "is_error")

__all__ = [
    "SIGNAL_ANSWER",
    "SIGNAL_RETRIEVED_CONTEXT",
    "SIGNAL_CITATIONS",
    "SIGNAL_TOOL_CALLS",
    "SIGNAL_TOOL_FAILURE",
    "SIGNAL_MULTI_TURN",
    "SIGNAL_OPERATIONAL_TRACES",
    "SIGNAL_SAFETY_RELEVANT",
    "SIGNALS",
    "SIGNAL_DESCRIPTIONS",
    "SAMPLE_ANSWER_KEYS",
    "SAMPLE_CONTEXT_KEYS",
    "SAMPLE_CITATION_KEYS",
    "SAMPLE_TOOL_KEYS",
    "SAMPLE_HISTORY_KEYS",
    "SAMPLE_TRACE_KEYS",
    "TOOL_FAILURE_KEYS",
]
