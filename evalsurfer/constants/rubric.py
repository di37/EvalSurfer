"""Rubric catalog: the single source of truth for the criteria.

Builds on the category/group names (``categories``) and the evidence signals
(``signals``) to declare every criterion as a (category, group, id, name,
required_signals) row. The planner builds Criterion objects from it.
Data only -- no behavior, no imports beyond typing helpers and sibling constants.
"""

from __future__ import annotations

from typing import Final

from evalsurfer.constants.categories import (
    GROUP_AGENT_TOOL_USE,
    GROUP_GENERATION,
    GROUP_MULTI_TURN,
    GROUP_RAG,
    CATEGORY_OPERATIONAL,
    CATEGORY_QUALITY,
    CATEGORY_SAFETY,
)
from evalsurfer.constants.signals import (
    SIGNAL_ANSWER,
    SIGNAL_CITATIONS,
    SIGNAL_MULTI_TURN,
    SIGNAL_OPERATIONAL_TRACES,
    SIGNAL_RETRIEVED_CONTEXT,
    SIGNAL_SAFETY_RELEVANT,
    SIGNAL_TOOL_CALLS,
    SIGNAL_TOOL_FAILURE,
)

# --------------------------------------------------------------------------- #
# Rubric catalog: (category, group, id, name, required_signals). Single source of
# truth for the judged rubric criteria; the planner builds Criterion objects from it.
# --------------------------------------------------------------------------- #
CRITERIA_CATALOG: Final = (
    (CATEGORY_QUALITY, GROUP_GENERATION, "correctness_accuracy", "Correctness / Accuracy", (SIGNAL_ANSWER,)),
    (CATEGORY_QUALITY, GROUP_GENERATION, "relevance", "Relevance", (SIGNAL_ANSWER,)),
    (CATEGORY_QUALITY, GROUP_GENERATION, "completeness", "Completeness", (SIGNAL_ANSWER,)),
    (CATEGORY_QUALITY, GROUP_GENERATION, "instruction_following", "Instruction Following", (SIGNAL_ANSWER,)),
    (CATEGORY_QUALITY, GROUP_RAG, "context_relevance", "Context Relevance", (SIGNAL_RETRIEVED_CONTEXT,)),
    (CATEGORY_QUALITY, GROUP_RAG, "retrieval_recall", "Retrieval Recall", (SIGNAL_RETRIEVED_CONTEXT,)),
    (CATEGORY_QUALITY, GROUP_RAG, "groundedness_faithfulness", "Groundedness / Faithfulness", (SIGNAL_RETRIEVED_CONTEXT, SIGNAL_ANSWER)),
    (CATEGORY_QUALITY, GROUP_RAG, "citation_accuracy", "Citation Accuracy", (SIGNAL_RETRIEVED_CONTEXT, SIGNAL_CITATIONS)),
    (CATEGORY_QUALITY, GROUP_AGENT_TOOL_USE, "tool_selection", "Tool Selection", (SIGNAL_TOOL_CALLS,)),
    (CATEGORY_QUALITY, GROUP_AGENT_TOOL_USE, "parameter_correctness", "Parameter Correctness", (SIGNAL_TOOL_CALLS,)),
    (CATEGORY_QUALITY, GROUP_AGENT_TOOL_USE, "task_completion", "Task Completion", (SIGNAL_TOOL_CALLS,)),
    (CATEGORY_QUALITY, GROUP_AGENT_TOOL_USE, "error_recovery", "Error Recovery", (SIGNAL_TOOL_CALLS, SIGNAL_TOOL_FAILURE)),
    (CATEGORY_QUALITY, GROUP_MULTI_TURN, "context_retention", "Context Retention / Memory", (SIGNAL_MULTI_TURN,)),
    (CATEGORY_QUALITY, GROUP_MULTI_TURN, "clarification_behavior", "Clarification Behavior", (SIGNAL_MULTI_TURN,)),
    (CATEGORY_SAFETY, None, "toxicity", "Toxicity", (SIGNAL_ANSWER, SIGNAL_SAFETY_RELEVANT)),
    (CATEGORY_SAFETY, None, "harmful_content", "Harmful Content", (SIGNAL_ANSWER, SIGNAL_SAFETY_RELEVANT)),
    (CATEGORY_SAFETY, None, "bias_fairness", "Bias / Fairness", (SIGNAL_ANSWER, SIGNAL_SAFETY_RELEVANT)),
    (CATEGORY_SAFETY, None, "pii_leakage", "PII Leakage", (SIGNAL_ANSWER, SIGNAL_SAFETY_RELEVANT)),
    (CATEGORY_SAFETY, None, "prompt_injection_resistance", "Prompt Injection / Jailbreak Resistance", (SIGNAL_ANSWER, SIGNAL_SAFETY_RELEVANT)),
    (CATEGORY_OPERATIONAL, None, "end_to_end_latency", "End-to-End Latency", (SIGNAL_OPERATIONAL_TRACES,)),
    (CATEGORY_OPERATIONAL, None, "time_to_first_token", "Time to First Token", (SIGNAL_OPERATIONAL_TRACES,)),
    (CATEGORY_OPERATIONAL, None, "cost_per_request", "Cost per Request", (SIGNAL_OPERATIONAL_TRACES,)),
    (CATEGORY_OPERATIONAL, None, "token_efficiency", "Token Efficiency", (SIGNAL_OPERATIONAL_TRACES,)),
    (CATEGORY_OPERATIONAL, None, "error_failure_rate", "Error / Failure Rate", (SIGNAL_OPERATIONAL_TRACES,)),
    (CATEGORY_OPERATIONAL, None, "latency_under_load", "Latency Under Load", (SIGNAL_OPERATIONAL_TRACES,)),
    (CATEGORY_OPERATIONAL, None, "inter_token_latency", "Inter-Token Latency", (SIGNAL_OPERATIONAL_TRACES,)),
    (CATEGORY_OPERATIONAL, None, "output_throughput", "Output Throughput", (SIGNAL_OPERATIONAL_TRACES,)),
    (CATEGORY_OPERATIONAL, None, "tail_latency", "Tail Latency", (SIGNAL_OPERATIONAL_TRACES,)),
    (CATEGORY_OPERATIONAL, None, "cost_per_million_tokens", "Cost per Million Tokens", (SIGNAL_OPERATIONAL_TRACES,)),
)
CRITERION_COUNT: Final = len(CRITERIA_CATALOG)

__all__ = [
    "CRITERIA_CATALOG",
    "CRITERION_COUNT",
]
