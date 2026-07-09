# `examples/adapters/` — ecosystem import inputs

Sample artifacts from other tools, plus a runner. The adapters have **no CLI** —
use them from Python:

```bash
python examples/adapters/run.py
```

They expose no CLI verb, but all four are also MCP tools — `adapter_ragas`, `adapter_promptfoo`, `adapter_otel`, `adapter_langsmith` — that the agent can call directly (see [`../../docs/mcp.md`](../../docs/mcp.md)).

| File | Adapter | Converts into |
| --- | --- | --- |
| [`ragas_metrics.json`](ragas_metrics.json) | `RagasAdapter.to_criteria` | rubric criteria (0–1 → 1–5) |
| [`promptfoo_results.json`](promptfoo_results.json) | `PromptfooAdapter.to_report` | a minimal report |
| [`otel_spans.json`](otel_spans.json) | `OtelAdapter.to_traces` | request traces |
| [`langsmith_runs.json`](langsmith_runs.json) | `LangSmithAdapter.to_traces` | request traces |

[`run.py`](run.py) also feeds the imported traces back through the operational
metrics. See step 10 of the [tutorial](../README.md) and
[`evalsurfer/adapters/`](../../evalsurfer/adapters/).
