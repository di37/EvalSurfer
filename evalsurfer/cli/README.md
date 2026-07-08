# `evalsurfer/cli/` — command-line entry points

Thin argparse front ends over the deterministic layer. Every verb reads JSON
(from a file or `-` for stdin), writes JSON (to stdout or `--out`), and makes no
model calls. Non-zero exit codes make `validate` and `gate` CI-friendly.

| Module | Console script | Purpose |
| --- | --- | --- |
| [`main.py`](main.py) | `evalsurfer` | Unified CLI dispatching to every verb (below). |
| [`plan.py`](plan.py) | `evalsurfer-plan` | Standalone adaptive planner (`Signals` → applicable criteria + coverage). |
| [`metrics.py`](metrics.py) | `evalsurfer-metrics` | Standalone operational metrics from a traces payload. |

## Verbs (`evalsurfer <verb>`)

| Verb | Does | Exit code |
| --- | --- | --- |
| `evaluate` | assemble a full report from a request | 0 |
| `validate` | structurally validate a report | 1 if invalid |
| `gate` | check a report against `--min` decision | 1 if below the bar |
| `diagnose` | run the diagnostics bundle (`--before` adds regression) | 0 |
| `plan` | infer the adaptive plan for a sample | 0 |
| `metrics` | operational metrics from traces | 0 |
| `calibrate` | score a judge against a calibration case | 0 |
| `redteam-template` | emit probes for a target shape (`--rag/--agent/--pii`) | 0 |
| `redteam-check` | triage collected red-team outputs | 0 |
| `trajectory` | diff an agent trajectory vs an expected spec | 0 |

```bash
evalsurfer evaluate request.json --out report.json
evalsurfer gate report.json --min pass_with_fixes   # exit 1 blocks a release
```

Console scripts are declared in [`../../pyproject.toml`](../../pyproject.toml).
For runnable, worked examples of every verb see
[`../../examples/scenarios/`](../../examples/scenarios/).
