# `evalsurfer/core/` — CIMAA Core: planner, scoring, report, evaluate

Turn agent-produced criterion scores into a schema-shaped report and a Core `Gate`
decision. Four modules, no model or API calls; inputs are never mutated. Core does
**not** import Metrics or Analysis — ops enrich and diagnostics are applied by
[`../interface/pipeline.py`](../interface/pipeline.py).

| Module | Public API | Purpose |
| --- | --- | --- |
| [`planner/`](planner/) | `Signals`, `EvaluationPlanner`, `EvaluationPlan` | Adaptive scoping from `Signals.from_sample`. |
| [`scoring.py`](scoring.py) | `ScoringModel` | Category / overall scores and `pass` / `pass_with_fixes` / `fail`. |
| [`report/`](report/) | `ReportValidator`, `Gate` | Structural validation and decision-vs-minimum gate. |
| [`evaluate.py`](evaluate.py) | `Evaluator` | Assemble only: plan → place scores → score → decide → coverage. |

> **As MCP tools (Core):** `plan`, `coverage`, `score_*`, `decide`, `validate_report`, `gate`.
> The MCP/CLI **`evaluate` tool** is Interface — it runs
> [`../interface/pipeline.py`](../interface/pipeline.py) (Metrics + Core + Analysis).
> See [`../interface/mcp/`](../interface/mcp/).

## Flow

```
sample ──► Signals.from_sample ──► EvaluationPlanner.plan ──► applicable criteria
scores ──►                          ScoringModel (categories, overall, decision)
                                    └─► Evaluator assembles report (no diagnostics)
Interface pipeline: Metrics enrich → Core Evaluator → Analysis DiagnosticsBundle
```

Shared rubric constants: [`../constants/`](../constants/) and [`../../spec/framework.yaml`](../../spec/framework.yaml).
