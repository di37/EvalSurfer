# `evalsurfer/interface/adapters/` — Interface layer: ecosystem importers

Reuse scores and telemetry you already collected. Each adapter is a small,
stateless service that maps another tool's native output into an EvalSurfer
shape — with no model, network, or API calls, and no mutation of the input.

| Module | Public API | Imports | Into |
| --- | --- | --- | --- |
| [`ragas.py`](ragas.py) | `RagasAdapter.to_criteria` | RAGAS metrics (`faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`) in `[0,1]` | rubric criteria, rescaled to 1–5 |
| [`promptfoo.py`](promptfoo.py) | `PromptfooAdapter.to_report` | a promptfoo results object (`{"results": [{"success": …}]}`) | a minimal report (pass rate → `correctness_accuracy`) |
| [`otel.py`](otel.py) | `OtelAdapter.to_traces` | OpenTelemetry spans (epoch-nanosecond timestamps + GenAI token attributes) | request traces for Metrics operational scoring |
| [`langsmith.py`](langsmith.py) | `LangSmithAdapter.to_traces` | LangSmith runs (ISO timestamps + token usage) | request traces for Metrics operational scoring |
| [`langfuse.py`](langfuse.py) | `LangfuseAdapter.to_traces` | Langfuse observations / traces (ISO timestamps, `completionStartTime`, token usage, error level) | request traces for Metrics operational scoring — incl. TTFT |

> **As MCP tools:** the harness LLM calls these directly via the `evalsurfer[mcp]` server — `adapter_ragas`, `adapter_promptfoo`, `adapter_otel`, `adapter_langsmith`, `adapter_langfuse`. See [`../mcp/`](../mcp/) and [`../../../docs/mcp.md`](../../../docs/mcp.md).

## Example

```python
from evalsurfer.interface.adapters import RagasAdapter, OtelAdapter
from evalsurfer.metrics.operational.metrics import OperationalMetrics, RequestTrace

criteria = RagasAdapter.to_criteria({"faithfulness": 0.42, "answer_relevancy": 0.88})
traces   = OtelAdapter.to_traces(otel_spans)
summary  = OperationalMetrics.summarize([RequestTrace.from_mapping(t) for t in traces])
```

The adapters have no CLI verb, but they are exposed as MCP tools
(`adapter_ragas` / `adapter_promptfoo` / `adapter_otel` / `adapter_langsmith` / `adapter_langfuse`) and
can also be called from Python. A runnable driver lives at
[`../../examples/scenarios/06_adapters.py`](../../../examples/scenarios/06_adapters.py).
Releases can be gated straight from CI via the repo's GitHub Action
([`../../action.yml`](../../../action.yml)).
