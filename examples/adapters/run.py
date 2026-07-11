"""Import external eval/trace artifacts into EvalSurfer shapes.

The adapters have no CLI, so run this from the repository root:

    python examples/adapters/run.py

It reads the JSON files next to it and shows each adapter's output, then feeds the
imported telemetry back through the deterministic operational metrics.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict

from evalsurfer.interface.adapters import (
    LangSmithAdapter,
    OtelAdapter,
    PromptfooAdapter,
    RagasAdapter,
)
from evalsurfer.metrics.operational.metrics import OperationalMetrics, Pricing, RequestTrace

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name: str):
    with open(os.path.join(HERE, name), encoding="utf-8") as file:
        return json.load(file)


def show(title: str, value: object) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(value, indent=2, sort_keys=True))


# RAGAS metrics -> rubric criteria (rescaled 0-1 -> 1-5)
show("RAGAS -> criteria", RagasAdapter.to_criteria(load("ragas_metrics.json")))

# promptfoo pass/fail results -> a minimal report
show("promptfoo -> report", PromptfooAdapter.to_report(load("promptfoo_results.json")))

# OpenTelemetry spans -> request traces
otel_traces = OtelAdapter.to_traces(load("otel_spans.json"))
show("OTel spans -> traces", otel_traces)

# LangSmith runs -> request traces
langsmith_traces = LangSmithAdapter.to_traces(load("langsmith_runs.json"))
show("LangSmith runs -> traces", langsmith_traces)

# Compose: imported telemetry -> operational summary
pricing = Pricing(input_per_million=1.0, output_per_million=5.0)
for label, traces in (("OTel", otel_traces), ("LangSmith", langsmith_traces)):
    summary = OperationalMetrics.summarize(
        [RequestTrace.from_mapping(trace) for trace in traces], pricing=pricing
    )
    show(f"{label} -> operational summary", asdict(summary))
