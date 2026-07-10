"""Deterministic quality metrics (reference-based / programmatic; zero LLM calls).

Reference-text metric ids, answer normalization, classification averaging modes,
metric parameters (BLEU/ROUGE/METEOR), and the task-type -> metric mapping.
Reported metric values reuse SHARE_PRECISION (3 decimals) for rounding.
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Deterministic quality metrics (reference-based / programmatic; zero LLM calls)
# --------------------------------------------------------------------------- #
# Reported metric values reuse SHARE_PRECISION (3 decimals) for rounding.

# Reference-text metric ids (task-typed). These are wired into the CLI/MCP
# dispatch; retrieval and match outputs use their descriptive dict keys directly.
METRIC_BLEU: Final = "bleu"
METRIC_ROUGE_N: Final = "rouge_n"
METRIC_ROUGE_L: Final = "rouge_l"
METRIC_METEOR: Final = "meteor"

# SQuAD-style answer normalization for exact-match / token-F1 (articles removed).
NORMALIZE_ARTICLES: Final = frozenset({"a", "an", "the"})

# Classification averaging modes.
AVERAGE_MICRO: Final = "micro"
AVERAGE_MACRO: Final = "macro"
CLASSIFICATION_AVERAGES: Final = (AVERAGE_MICRO, AVERAGE_MACRO)

# Reference-text metric parameters.
BLEU_MAX_N: Final = 4  # BLEU-4 by default: geometric mean of 1..4-gram precision
ROUGE_DEFAULT_N: Final = 1  # ROUGE-1 (unigram) by default
# METEOR tuned constants (Banerjee & Lavie 2005 / Lavie 2007 defaults). Fmean =
# P*R / (alpha*P + (1-alpha)*R); penalty = gamma * (chunks/matches) ** beta.
METEOR_ALPHA: Final = 0.9
METEOR_BETA: Final = 3.0
METEOR_GAMMA: Final = 0.5

# Task type -> the reference metric(s) conventionally reported for it. Used to
# pick sensible defaults; the caller can always request any metric explicitly.
TASK_TRANSLATION: Final = "translation"
TASK_SUMMARIZATION: Final = "summarization"
TASK_GENERATION: Final = "generation"
TEXT_TASKS: Final = (TASK_TRANSLATION, TASK_SUMMARIZATION, TASK_GENERATION)
TEXT_TASK_METRICS: Final = {
    TASK_TRANSLATION: (METRIC_BLEU,),
    TASK_SUMMARIZATION: (METRIC_ROUGE_N, METRIC_ROUGE_L),
    TASK_GENERATION: (METRIC_METEOR,),
}

__all__ = [
    "METRIC_BLEU",
    "METRIC_ROUGE_N",
    "METRIC_ROUGE_L",
    "METRIC_METEOR",
    "NORMALIZE_ARTICLES",
    "AVERAGE_MICRO",
    "AVERAGE_MACRO",
    "CLASSIFICATION_AVERAGES",
    "BLEU_MAX_N",
    "ROUGE_DEFAULT_N",
    "METEOR_ALPHA",
    "METEOR_BETA",
    "METEOR_GAMMA",
    "TASK_TRANSLATION",
    "TASK_SUMMARIZATION",
    "TASK_GENERATION",
    "TEXT_TASKS",
    "TEXT_TASK_METRICS",
]
