# EvalSurfer as an MCP server

The on-thesis interface. Instead of shelling out to a CLI or calling an external
model, EvalSurfer exposes its deterministic functions as **MCP tools**. Your
coding agent — the harness LLM — is the judge, and it calls these tools for every
part of an evaluation that must be deterministic. **No external model is ever
called:** the judgment stays in the agent; the measurement is the tools.

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

**Every** deterministic function is a tool (47 total), each with a pydantic input
schema. Grouped:

| Group | Tools |
| --- | --- |
| **Rubric & scope** | `rubric`, `plan`, `coverage` |
| **Scoring** | `score_pillar`, `score_overall`, `decide`, `score_report` |
| **Assemble / gate** | `evaluate`, `validate_report`, `gate`, `guardrail_gate` |
| **Diagnostics** | `explain`, `root_cause`, `regression_diff`, `maturity`, `industry_profiles`, `industry_profile`, `review_gate`, `personas`, `failure_map`, `diagnose` (bundle), `golden_set`, `build_evidence` |
| **Operational** | `metrics`, `operational_score`, `cost_per_request`, `token_efficiency` |
| **Safety & trajectory** | `redteam_template`, `redteam_check`, `trajectory` |
| **Calibration** | `calibrate`, `calibrate_one` |
| **Adapters** | `adapter_ragas`, `adapter_promptfoo`, `adapter_otel`, `adapter_langsmith` |

Every tool is **deterministic**. The one part that isn't — judging quality/safety
1–5 with evidence — is done by the agent itself, *between* the tool calls. Inputs
are validated pydantic models, so the agent gets a precise schema for each tool.

## The agent's workflow

1. Read the AI output to evaluate.
2. `plan(sample)` → which criteria apply.
3. **Judge** each applicable quality/safety criterion 1–5 with evidence (your own reasoning — no tool call).
4. `evaluate({sample, scores, evidence, top_issues, traces?, slo?})` → the report.
5. `diagnose(report)` and/or `gate(report, …)` → explain and decide what ships.

This is exactly why EvalSurfer needs **no external LLM**: the harness LLM judges,
and the tools measure. (The [`examples/judge/llm_judge.py`](../examples/judge/llm_judge.py)
script, which calls a model API directly, is only for non-agent pipelines that
have no harness LLM.)
