# `evalsurfer/interface/cli/` — Interface layer: command-line entry points

Thin argparse front ends over the deterministic CIMAA layers. Every verb reads JSON
(from a file or `-` for stdin), writes JSON (to stdout or `--out`), and makes no
model calls. Non-zero exit codes make `validate` and `gate` CI-friendly.

| Module | Console script | Purpose |
| --- | --- | --- |
| [`main.py`](main.py) | `evalsurfer` | Unified CLI dispatching to every verb (below). |
| [`plan.py`](plan.py) | `evalsurfer-plan` | Standalone Core planner (`Signals` → applicable criteria + coverage). |
| [`metrics.py`](metrics.py) | `evalsurfer-metrics` | Standalone Metrics operational summary from a traces payload. |
| [`quality.py`](quality.py) | `evalsurfer-quality` | Standalone Metrics reference-quality calculations. |
| [`dataset.py`](dataset.py) | `evalsurfer-dataset` | Standalone Metrics golden-dataset operations. |
| [`../mcp/server.py`](../mcp/server.py) | `evalsurfer-mcp` | MCP server exposing the deterministic tool catalog (`evalsurfer[mcp]`). |

> **Agent-native alternative:** `evalsurfer-mcp` runs the same deterministic functions as an MCP tool server (`evalsurfer[mcp]`), so the harness LLM can call them as tools instead of shelling out to these verbs. There is no `mcp` CLI verb. See [`../mcp/`](../mcp/) and [`../../../docs/mcp.md`](../../../docs/mcp.md).

## Verbs (`evalsurfer <verb>`)

| Verb | CIMAA | Does | Exit code |
| --- | --- | --- | --- |
| `evaluate` | Interface | full CIMAA run (Metrics enrich → Core assemble → Analysis diagnose) | 0 |
| `validate` | Core | structurally validate a report | 1 if invalid |
| `gate` | Core (+ Assurance `--policy`) | check a report against `--min`, or a full `--policy guardrails.json` | 1 if blocked |
| `diagnose` | Analysis | run diagnostics (`--signals` adds maturity; `--before` adds regression) | 0 |
| `plan` | Core | infer the adaptive plan for a sample | 0 |
| `metrics` | Metrics | operational metrics from traces | 0 |
| `quality` | Metrics | reference metrics (retrieval / match / text) | 0 |
| `dataset` | Metrics | golden dataset ops | 0 |
| `calibrate` / `agreement` | Analysis | score a judge / chance-corrected agreement | 0 |
| `redteam-template` / `redteam-check` | Assurance | emit / triage safety probes | 0 |
| `trajectory` | Assurance | diff an agent trajectory vs an expected spec | 0 |

```bash
evalsurfer evaluate request.json --out report.json
evalsurfer gate report.json --min pass_with_fixes   # Core gate; add --policy for Assurance
```

Console scripts are declared in [`../../pyproject.toml`](../../../pyproject.toml).
For runnable, worked examples of every verb see
[`../../examples/scenarios/`](../../../examples/scenarios/).
