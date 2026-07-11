"""Deterministic quality metrics tools (reference-based; zero LLM calls)."""

from __future__ import annotations

from evalsurfer.interface.mcp import models as m
from evalsurfer.interface.mcp.instance import mcp
from evalsurfer.metrics.quality.report import build_report


@mcp.tool()
def retrieval_metrics(payload: m.RetrievalMetricsInput) -> dict:
    """Recall@k / Precision@k / MRR over ranked retrieved ids vs gold-relevant ids.
    Also scores tool-selection recall (a router miss is a recall error)."""
    return build_report({"retrieval": payload.model_dump(exclude_none=True)})["retrieval"]


@mcp.tool()
def match_metrics(payload: m.MatchMetricsInput) -> dict:
    """Extraction (exact-match / token-F1) or classification (accuracy, P/R/F1) scores
    of predictions against gold references."""
    return build_report({"match": payload.model_dump(exclude_none=True)})["match"]


@mcp.tool()
def text_metrics(payload: m.TextMetricsInput) -> dict:
    """Task-typed reference-text metrics: BLEU (translation), ROUGE (summarization),
    METEOR (generation) of candidates against gold references."""
    return build_report({"text": payload.model_dump(exclude_none=True)})["text"]
