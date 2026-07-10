# `evalsurfer/diagnostics/` — explain and compare, don't just score

Diagnostics turn a report from a number into an explanation. Each module is a
small, deterministic service (no model calls, inputs never mutated); the
`DiagnosticsBundle` runs the applicable ones into a single `diagnostics` block.

| Module | Public API | Purpose |
| --- | --- | --- |
| [`bundle.py`](bundle.py) | `DiagnosticsBundle` | Orchestrates the report-only diagnostics (always) plus `maturity` (when a `Signals` snapshot is given) and `regression` (when a prior report is given), keyed by `constants.DIAGNOSTICS_KEYS`. |
| [`explainability.py`](explainability.py) | `Explainer` | SHAP-style attribution: how much each assessed criterion deducts from a perfect 10. |
| [`root_cause.py`](root_cause.py) | `RootCauseAnalyzer` | Attribute lost points by pillar and criterion group, with a top contributor. |
| [`regression.py`](regression.py) | `RegressionDiffer` | Diff two reports: overall/coverage deltas, per-pillar/criterion changes, decision change, and the lists of improvements and regressions. |
| [`maturity.py`](maturity.py) | `MaturityClassifier` | Map a `Signals` snapshot to a maturity level (1–6, e.g. "Prompt + RAG") with drivers and recommendations. |
| [`profiles.py`](profiles.py) | `IndustryProfiler` | Re-weight the overall score using an industry profile's pillar weights. |
| [`review_gate.py`](review_gate.py) | `ReviewGate` | Recommend human review (critical issues, low-confidence criteria, disagreement). |
| [`evidence.py`](evidence.py) | `Evidence` | Build structured evidence records (claim / supporting context / mismatch / confidence). |
| [`personas.py`](personas.py) | `PersonaAggregator` | Aggregate scores across weighted evaluation personas. |
| [`failure_map.py`](failure_map.py) | `FailureMap` | Diagnose which pipeline stage (retrieval, generation, tools, …) failures concentrate in. |
| [`golden_set.py`](golden_set.py) | `GoldenSet`, `GoldenCase` | Frozen golden cases that validate the deterministic layer itself. |

> **As MCP tools:** the harness LLM calls these directly via the `evalsurfer[mcp]` server — `explain`, `root_cause`, `regression_diff`, `maturity`, `industry_profiles`, `industry_profile`, `review_gate`, `personas`, `failure_map`, `diagnose`, `golden_set`, `build_evidence`. See [`../mcp/`](../mcp/) and [`../../docs/mcp.md`](../../docs/mcp.md).

## Usage

```python
from evalsurfer.diagnostics import Explainer, RegressionDiffer

Explainer.explain(report)                 # deductions from a perfect 10
RegressionDiffer.diff(before, after)      # what improved / regressed
```

Or via the CLI: `evalsurfer diagnose report.json --before prior.json`.

These classes are measurement helpers, not the product — see the
[root README](../../README.md#diagnostics).
