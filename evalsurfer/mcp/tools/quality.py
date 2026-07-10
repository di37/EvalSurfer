"""Deterministic quality metrics tools (reference-based; zero LLM calls)."""

from __future__ import annotations

from evalsurfer.cli import quality as quality_cli
from evalsurfer.mcp import models as m
from evalsurfer.mcp.instance import mcp


@mcp.tool()
def retrieval_metrics(payload: m.RetrievalMetricsInput) -> dict:
    """Recall@k / Precision@k / MRR over ranked retrieved ids vs gold-relevant ids.
    Also scores tool-selection recall (a router miss is a recall error)."""
    return quality_cli.build_report(
        {"retrieval": payload.model_dump(exclude_none=True)}
    )["retrieval"]


@mcp.tool()
def match_metrics(payload: m.MatchMetricsInput) -> dict:
    """Extraction (exact-match / token-F1) or classification (accuracy, P/R/F1) scores
    of predictions against gold references."""
    return quality_cli.build_report({"match": payload.model_dump(exclude_none=True)})[
        "match"
    ]


@mcp.tool()
def text_metrics(payload: m.TextMetricsInput) -> dict:
    """Task-typed reference-text metrics: BLEU (translation), ROUGE (summarization),
    METEOR (generation) of candidates against gold references."""
    return quality_cli.build_report({"text": payload.model_dump(exclude_none=True)})[
        "text"
    ]
