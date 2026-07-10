"""Scenario 6 — Ecosystem adapters: import external eval/trace artifacts.

Exercises RAGAS -> criteria, promptfoo -> report, OpenTelemetry -> traces, and
LangSmith -> traces, then feeds the imported telemetry back through the
deterministic operational metrics to show the adapters compose with the core.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from evalsurfer.interface.adapters import (
    LangSmithAdapter,
    OtelAdapter,
    PromptfooAdapter,
    RagasAdapter,
)
from evalsurfer.metrics.operational.metrics import OperationalMetrics, Pricing, RequestTrace


def show(title: str, value: object) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(value, indent=2, sort_keys=True))


# --- RAGAS: an offline RAG eval run (metrics in [0,1]) -> rubric criteria ------
ragas_metrics = {
    "faithfulness": 0.42,
    "answer_relevancy": 0.88,
    "context_precision": 0.91,
    "context_recall": 0.75,
}
show("RAGAS metrics -> EvalSurfer criteria", RagasAdapter.to_criteria(ragas_metrics))

# --- promptfoo: a red/green assertion suite -> a minimal report ----------------
promptfoo_results = {
    "results": [
        {"success": True, "score": 1.0},
        {"success": True, "score": 1.0},
        {"success": False, "score": 0.0},
        {"success": True, "score": 1.0},
        {"success": False, "score": 0.0},
    ]
}
show("promptfoo results -> EvalSurfer report", PromptfooAdapter.to_report(promptfoo_results))

# --- OpenTelemetry: GenAI spans (epoch-nanosecond) -> request traces -----------
otel_spans = [
    {
        "startTimeUnixNano": 1_752_055_200_000_000_000,
        "endTimeUnixNano": 1_752_055_201_500_000_000,
        "attributes": {
            "gen_ai.usage.input_tokens": 1100,
            "gen_ai.usage.output_tokens": 240,
        },
    },
    {
        "startTimeUnixNano": 1_752_055_202_000_000_000,
        "endTimeUnixNano": 1_752_055_205_200_000_000,
        "attributes": {
            "gen_ai.usage.input_tokens": 1300,
            "gen_ai.usage.output_tokens": 300,
        },
    },
]
otel_traces = OtelAdapter.to_traces(otel_spans)
show("OTel spans -> traces", otel_traces)

# --- LangSmith: traced runs (ISO timestamps + usage) -> request traces ---------
langsmith_runs = [
    {
        "start_time": "2026-07-09T10:00:00Z",
        "end_time": "2026-07-09T10:00:01.400Z",
        "usage_metadata": {"input_tokens": 950, "output_tokens": 210},
    },
    {
        "start_time": "2026-07-09T10:00:02Z",
        "end_time": "2026-07-09T10:00:06.100Z",
        "usage_metadata": {"input_tokens": 1200, "output_tokens": 280},
    },
]
langsmith_traces = LangSmithAdapter.to_traces(langsmith_runs)
show("LangSmith runs -> traces", langsmith_traces)

# --- Compose: imported telemetry -> core operational metrics -------------------
pricing = Pricing(input_per_million=1.0, output_per_million=5.0)
for label, payload in (("OTel", otel_traces), ("LangSmith", langsmith_traces)):
    summary = OperationalMetrics.summarize(
        [RequestTrace.from_mapping(t) for t in payload], pricing=pricing
    )
    show(f"{label} telemetry -> operational summary", asdict(summary))
