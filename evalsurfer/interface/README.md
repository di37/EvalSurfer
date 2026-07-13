# `evalsurfer/interface/` — CIMAA Interface

How users, agents, and external tools reach EvalSurfer.

| Path | Role |
| --- | --- |
| [`pipeline.py`](pipeline.py) | Full CIMAA run: Metrics enrich → Core assemble → Analysis diagnose |
| [`cli/`](cli/) | `evalsurfer` command |
| [`mcp/`](mcp/) | 48-tool MCP server |
| [`adapters/`](adapters/) | RAGAS / promptfoo / OTel / LangSmith |

CLI and MCP `evaluate` call `pipeline.evaluate`, not Core `Evaluator` alone.
