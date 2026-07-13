# EvalSurfer as an MCP server

The on-thesis **Interface** layer. Instead of shelling out to a CLI or calling an
external model, EvalSurfer exposes its deterministic functions as **MCP tools**.
Your coding agent — the harness LLM — is the judge, and it calls these tools for
every part of an evaluation that must be deterministic. **No external model is
ever called:** the judgment stays in the agent; the measurement is the tools.

## Install & run

Pick your ecosystem — all four launch the same stdio server:

```bash
uvx --from "evalsurfer[mcp]" evalsurfer-mcp     # uv · run, no install (recommended)
pipx install "evalsurfer[mcp]"; evalsurfer-mcp  # pipx · install the command
npx evalsurfer                                   # npm · run, no install
pip install "evalsurfer[mcp]"; evalsurfer-mcp    # pip · classic install
```

(From a local checkout: `pip install -e ".[mcp]"` then `evalsurfer-mcp`, or `python -m evalsurfer.interface.mcp.server`.)

## Connect it to your agent

Drop a standard `mcpServers` entry into your harness config — nothing to install
first; the server is fetched on first launch.

**Claude Code** — `.mcp.json` (or `claude mcp add evalsurfer -- uvx --from "evalsurfer[mcp]" evalsurfer-mcp`):
```json
{ "mcpServers": { "evalsurfer": { "command": "uvx", "args": ["--from", "evalsurfer[mcp]", "evalsurfer-mcp"] } } }
```

**Cursor** — `.cursor/mcp.json`:
```json
{ "mcpServers": { "evalsurfer": { "command": "uvx", "args": ["--from", "evalsurfer[mcp]", "evalsurfer-mcp"] } } }
```

Prefer npm? Use `"command": "npx", "args": ["-y", "evalsurfer"]`. Already
`pipx install`ed? Use `"command": "evalsurfer-mcp"`. Restart the client and the
EvalSurfer tools appear in the agent's toolset.

## The tools

**Every** deterministic function is a tool (48 total), each with a pydantic input
schema. Grouped by **CIMAA** layer:

| Layer | Tools |
| --- | --- |
| **Core** | `rubric`, `plan`, `coverage`; `score_category`, `score_overall`, `decide`, `score_report`; `validate_report`, `gate` |
| **Interface** | `evaluate` (full pipeline: Metrics enrich → Core assemble → Analysis diagnose); `adapter_ragas`, `adapter_promptfoo`, `adapter_otel`, `adapter_langsmith` |
| **Metrics** | `metrics`, `operational_score`, `cost_per_request`, `token_efficiency`; `retrieval_metrics`, `match_metrics`, `text_metrics`; `dataset_from_traces`, `dataset_diff`, `dataset_contamination`, `dataset_coverage` |
| **Analysis** | `explain`, `root_cause`, `regression_diff`, `maturity`, `industry_profiles`, `industry_profile`, `review_gate`, `personas`, `failure_map`, `diagnose`, `golden_set`, `build_evidence`; `calibrate`, `calibrate_one`, `cohen_kappa`, `fleiss_kappa`, `krippendorff_alpha`, `reference_calibrate`, `harness_invariance` |
| **Assurance** | `guardrail_gate`; `redteam_template`, `redteam_check`, `trajectory` |

Every tool is **deterministic**. The one part that isn't — judging quality/safety
1–5 with evidence — is done by the agent itself, *between* the tool calls. Inputs
are validated pydantic models, so the agent gets a precise schema for each tool.

`gate` is Core's decision-vs-minimum bar; `guardrail_gate` is Assurance's policy
check on top of that same gate.

## The agent's workflow

1. Read the AI output to evaluate.
2. **Core** `plan(sample)` → which criteria apply.
3. **Judge** each applicable quality/safety criterion 1–5 with evidence (your own reasoning — no tool call).
4. **Interface** `evaluate({sample, scores, evidence, top_issues, traces?, slo?})` → full report (Metrics ops enrich when traces present → Core assemble → Analysis diagnostics).
5. **Core** `gate(report, …)` / **Assurance** `guardrail_gate(…)`, and optionally **Analysis** `diagnose(report, signals?, before?)` again (`signals` adds maturity; `before` adds regression) — Interface `evaluate` already attached diagnostics.

This is exactly why EvalSurfer needs **no external LLM**: the harness LLM judges,
and the tools measure. (The [`examples/judge/llm_judge.py`](../examples/judge/llm_judge.py)
script, which calls a model API directly, is only for non-agent pipelines that
have no harness LLM.)
