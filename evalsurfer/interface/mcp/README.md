# `evalsurfer/interface/mcp/` — MCP tool server

Exposes every deterministic function as an MCP tool. The harness LLM is the
judge; tools only measure. Optional: `pip install "evalsurfer[mcp]"`.

Tool modules nest by CIMAA layer:

| Path | Layer |
| --- | --- |
| `tools/core/assemble.py` | Core (`plan`, score helpers, `validate_report`, `gate`) |
| `tools/interface/evaluate.py` | Interface full-run `evaluate` (Metrics → Core → Analysis) |
| `tools/interface/adapters.py` | Interface adapters |
| `tools/metrics/` (`operational`, `quality`, `dataset`) | Metrics |
| `tools/analysis/` (`diagnostics`, `calibration`) | Analysis |
| `tools/assurance/tools.py` | Assurance (`guardrail_gate`, redteam, trajectory) |

See [`docs/mcp.md`](../../../docs/mcp.md).
