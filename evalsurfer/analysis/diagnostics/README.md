# `evalsurfer/analysis/diagnostics/` — Analysis layer: explain and compare

Diagnostics turn a report from a number into an explanation. Each module is a
small, deterministic service (no model calls, inputs never mutated); the
`DiagnosticsBundle` runs the applicable ones into a single `diagnostics` block.

| Module | Public API | Purpose |
| --- | --- | --- |
| [`bundle.py`](bundle.py) | `DiagnosticsBundle` | Orchestrates the report-only diagnostics (always) plus `maturity` (when a `Signals` snapshot is given) and `regression` (when a prior report is given), keyed by `constants.DIAGNOSTICS_KEYS`. |
| [`explainability/`](explainability/) | `Explainer` | SHAP-style attribution: how much each assessed criterion deducts from a perfect 10. |
| [`root_cause/`](root_cause/) | `RootCauseAnalyzer` | Attribute lost points by category and criterion group, with a top contributor. |
| [`regression/`](regression/) | `RegressionDiffer` | Diff two reports: overall/coverage deltas, per-category/criterion changes, decision change, and the lists of improvements and regressions. |
| [`maturity/`](maturity/) | `MaturityClassifier` | Map a `Signals` snapshot to a maturity level (1–6, e.g. "Prompt + RAG") with drivers and recommendations. |
| [`profiles.py`](profiles.py) | `IndustryProfiler` | Re-weight the overall score using an industry profile's category weights. |
| [`review_gate/`](review_gate/) | `ReviewGate` | Recommend human review (critical issues, low-confidence criteria). |
| [`evidence.py`](evidence.py) | `Evidence` | Build structured evidence records (claim / supporting context / mismatch / confidence). |
| [`personas.py`](personas.py) | `PersonaAggregator` | Aggregate scores across evaluation personas (mean / min / max / range). |
| [`failure_map/`](failure_map/) | `FailureMap` | Diagnose which pipeline stage (retrieval, generation, tools, …) failures concentrate in. |
| [`golden_set/`](golden_set/) | `GoldenSet`, `GoldenCase` | Frozen golden cases that validate the deterministic layer itself. |

> **As MCP tools:** the harness LLM calls these directly via the `evalsurfer[mcp]` server — `explain`, `root_cause`, `regression_diff`, `maturity`, `industry_profiles`, `industry_profile`, `review_gate`, `personas`, `failure_map`, `diagnose`, `golden_set`, `build_evidence`. See [`../../interface/mcp/`](../../interface/mcp/) and [`../../../docs/mcp.md`](../../../docs/mcp.md).

## Usage

```python
from evalsurfer.analysis.diagnostics import Explainer, RegressionDiffer

Explainer.explain(report)                 # deductions from a perfect 10
RegressionDiffer.diff(before, after)      # what improved / regressed
```

Or via the CLI:
`evalsurfer diagnose report.json --signals sample.json --before prior.json`
(`--signals` adds maturity; `--before` adds regression).

These classes are measurement helpers, not the product — see the
[root README](../../../README.md#analysis).
