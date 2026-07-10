# `evalsurfer/core/` — scoring, planning, reports, orchestration

The heart of the deterministic layer: turn agent-produced criterion scores into a
validated, gated report. No model or API calls; inputs are never mutated.

| Module | Public API | Purpose |
| --- | --- | --- |
| [`scoring.py`](scoring.py) | `ScoringModel` | Pillar score (criterion mean ×2), overall score, and the `pass` / `pass_with_fixes` / `fail` decision — with the safety floor, critical-issue override, failure-rate and P95-within-SLO gates. Also iterates/collects assessed criteria. |
| [`planner.py`](planner.py) | `Signals`, `EvaluationPlanner`, `EvaluationPlan` | Adaptive scoping: infer which pillars/criteria apply from the inputs actually present (`Signals.from_sample`), with a reason per skip and a coverage score. |
| [`report.py`](report.py) | `ReportValidator`, `Gate` | Pure-Python structural validation of a report (`{"valid", "errors"}`) and a release gate against a minimum decision (`{"passed", "decision", "minimum", "reason"}`). |
| [`evaluate.py`](evaluate.py) | `Evaluator` | The end-to-end orchestrator: infer the plan, place provided scores, auto-score operations from traces + SLO, recompute pillar/overall, decide, measure coverage, and attach the diagnostics block. |

> **As MCP tools:** the harness LLM calls these directly via the `evalsurfer[mcp]` server — `plan`, `coverage`, `score_pillar`, `score_overall`, `decide`, `score_report`, `evaluate`, `validate_report`, `gate`. See [`../mcp/`](../mcp/) and [`../../docs/mcp.md`](../../docs/mcp.md).

## Flow

```
sample ──► Signals.from_sample ──► EvaluationPlanner.plan ──► applicable criteria
scores ──►                          ScoringModel (pillars, overall, decision)
traces ──► OperationalScorer ─────► operational pillar
                                    └─► Evaluator assembles ─► ReportValidator / Gate / DiagnosticsBundle
```

The judge's quality and safety scores come from the agent/skill via the request;
`core` never invents them.

Related: [`../operational/`](../operational/) (ops scoring),
[`../diagnostics/`](../diagnostics/) (the diagnostics block),
[`../cli/`](../cli/) (command-line front end).
