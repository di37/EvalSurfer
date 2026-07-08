# EvalSurfer — worked scenarios & demo

Six realistic, end-to-end use cases that exercise **every** EvalSurfer
functionality. Everything here is deterministic and standard-library only —
**no model or API calls anywhere.** The agent/skill is the judge; these scenarios
drive the deterministic layer around it (planning, scoring, gating, diagnostics,
calibration, red-team triage, trajectory analysis, and ecosystem imports).

## Run it

From the repository root (Python ≥ 3.11):

```bash
# Interactive: pick a use case from a menu; each step prints the command it runs.
bash examples/scenarios/demo.sh

# Or jump straight to one scenario (1–6), or all:
bash examples/scenarios/demo.sh 3
bash examples/scenarios/demo.sh a

# Non-interactive: run the whole battery top to bottom.
bash examples/scenarios/run_all.sh
```

The scripts use the installed `evalsurfer` console script when present, and
otherwise fall back to `python -m evalsurfer.cli.main` (so `pip install -e .`
is optional). Generated reports are written to a temp dir by default; set
`OUT=./out` to keep them.

## The scenarios

| # | Target | Functionality exercised | What it demonstrates |
|---|--------|-------------------------|----------------------|
| 1 | **VitalsAI** — clinical-triage RAG that tells a warfarin patient to *double* a missed dose | `plan` → `evaluate` → `validate` → `gate` → `diagnose` (explainability, root-cause, review-gate) | A single **critical** safety issue fails the release (`decision: fail`) even though overall `7.1` and the safety pillar `8.4` look healthy — the decision logic doesn't trust pillar means alone. |
| 2 | **LedgerAgent** — autonomous banking agent | `trajectory`, `redteam-template`, `redteam-check` | Trajectory flags all four defects: forbidden tool, out-of-order calls, missing required arg, unrecovered error. Red-team triage is **honest** — only PII has a deterministic detector; the rest are `needs_judgment`. |
| 3 | **BriefBot** — news summarizer under production load | `metrics`, operational SLO auto-scoring via `evaluate` | Raw metrics (p95, failure rate, cost, latency-by-concurrency) and 1–5 operational scores derived by comparing measured values to the SLO. |
| 4 | **VitalsAI judge** — 5 repeated judge runs | `calibrate` (eval of the eval) | Catches a judge that wrongly *passes* the dangerous answer: `agreement 0.8`, `false_pass_rate 0.2`, plus score variance. |
| 5 | **HelpDeskAI** — a billing answer, v1 → v2 | `evaluate` ×2, regression `diagnose --before`, maturity | Surfaces the `pass_with_fixes → pass` decision change **and** the one criterion that regressed (`relevance`) while others improved. |
| 6 | **Ecosystem artifacts** | RAGAS / promptfoo / OpenTelemetry / LangSmith adapters | Import scores and telemetry you already collected into native shapes, then feed them straight back through the operational metrics. |

## Files

Inputs you can copy and adapt:

- `01_vitalsai_request.json` — full `evaluate` request (sample + scores + evidence + traces + SLO + issues)
- `02_ledgeragent_trajectory.json` — `actual` vs `expected` agent trajectory
- `02_ledgeragent_redteam_outputs.json` — collected probe outputs for `redteam-check`
- `03_briefbot_traces.json` — request traces for `metrics`
- `03_briefbot_ops_request.json` — operational-only `evaluate` request (traces + SLO)
- `04_vitalsai_calibration.json` — calibration oracle + repeated judge reports
- `05_helpdesk_v1_request.json`, `05_helpdesk_v2_request.json` — before/after `evaluate` requests
- `06_adapters.py` — adapter driver (Python; adapters have no CLI)

Harness:

- `demo.sh` — interactive menu (asks which use case to run)
- `run_all.sh` — runs all six non-interactively
- `_lib.sh` — shared scenario definitions (sourced by both)
