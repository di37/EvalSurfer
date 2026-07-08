# `evalsurfer/operational/` — operational metrics & SLO scoring

Turn request traces into operational numbers, then into 1–5 operational-pillar
scores by comparing them to a service-level objective (SLO). Deterministic,
standard-library only, no model calls.

| Module | Public API | Purpose |
| --- | --- | --- |
| [`metrics.py`](metrics.py) | `OperationalMetrics`, `RequestTrace`, `Pricing`, `LatencyStats`, `OperationalSummary` | Parse heterogeneous trace mappings (`RequestTrace.from_mapping`) and summarize them: end-to-end latency + TTFT percentiles, average/total cost from `Pricing`, tokens/sec, failure rate, and latency-under-load grouped by concurrency. |
| [`slo.py`](slo.py) | `OperationalScorer`, `CriterionScore`, `OperationalScore` | Score each operational criterion 1–5 by the measured/target ratio, following `constants.SLO_SCORE_BANDS`. The SLO targets are the only configurable input; `token_efficiency` has no SLO and stays unscored. |

## Metric → SLO field mapping

| Criterion | SLO field | Direction |
| --- | --- | --- |
| `end_to_end_latency` | `p95_latency_ms` | lower is better |
| `time_to_first_token` | `ttft_ms` | lower is better |
| `cost_per_request` | `max_cost_usd` | lower is better |
| `error_failure_rate` | `max_failure_rate` | lower is better |
| `latency_under_load` | `p95_latency_ms` | lower is better |
| `token_efficiency` | — | not scored (no SLO) |

## Example

```bash
evalsurfer metrics examples/traces.json --pretty      # raw numbers
evalsurfer evaluate request-with-traces-and-slo.json  # 1–5 operational scores
```

This pillar is the deterministic half of EvalSurfer's hybrid design: quality
and safety are judged by the skill; operations are auto-scored here. See
[`../core/`](../core/) for how the `Evaluator` wires it in.
