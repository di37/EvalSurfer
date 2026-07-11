# `evalsurfer/metrics/operational/` — Metrics layer: ops metrics & SLO scoring

Turn request traces into operational numbers, then into 1–5 operational-category
scores by comparing them to a service-level objective (SLO). Deterministic,
standard-library only, no model calls.

| Module | Public API | Purpose |
| --- | --- | --- |
| [`metrics/`](metrics/) | `OperationalMetrics`, `RequestTrace`, `Pricing`, `LatencyStats`, `OperationalSummary` | Parse heterogeneous trace mappings (`RequestTrace.from_mapping`) and summarize them: end-to-end + TTFT + inter-token-latency percentiles, throughput (TPS), P99/P50 tail ratio, average/total cost and cost-per-million-tokens from `Pricing`, failure rate, and latency-under-load grouped by concurrency. |
| [`slo/`](slo/) | `OperationalScorer`, `CriterionScore`, `OperationalScore` | Score each operational criterion 1–5 against its SLO target, following `constants.SLO_SCORE_BANDS`. Lower-is-better metrics score on the measured/target ratio; throughput is higher-is-better (scored on target/measured). The SLO targets are the only configurable input; `token_efficiency` has no SLO and stays unscored. |

> **As MCP tools:** the harness LLM calls these directly via the `evalsurfer[mcp]` server — `metrics`, `operational_score`, `cost_per_request`, `token_efficiency`. See [`../../interface/mcp/`](../../interface/mcp/) and [`../../../docs/mcp.md`](../../../docs/mcp.md).

## Metric → SLO field mapping

| Criterion | SLO field | Direction |
| --- | --- | --- |
| `end_to_end_latency` | `p95_latency_ms` | lower is better |
| `time_to_first_token` | `ttft_ms` | lower is better |
| `cost_per_request` | `max_cost_usd` | lower is better |
| `error_failure_rate` | `max_failure_rate` | lower is better |
| `latency_under_load` | `p95_latency_ms` | lower is better |
| `inter_token_latency` | `itl_ms` | lower is better |
| `output_throughput` | `min_tokens_per_second` | **higher is better** (TPS) |
| `tail_latency` | `max_p99_p50_ratio` | lower is better (P99 ÷ P50) |
| `cost_per_million_tokens` | `max_cost_per_million_usd` | lower is better |
| `token_efficiency` | — | not scored (no SLO) |

## Example

```bash
evalsurfer metrics examples/traces.json --pretty      # raw numbers
evalsurfer evaluate request-with-traces-and-slo.json  # 1–5 operational scores
```

This category is the deterministic half of EvalSurfer's hybrid design: quality
criteria are judged by the skill; operations are auto-scored here. The Interface
[`pipeline`](../../interface/pipeline.py) wires ops enrich into the full run
(not Core `Evaluator`, which assembles only).
