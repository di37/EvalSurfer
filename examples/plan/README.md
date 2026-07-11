# `examples/plan/` — adaptive-scoping samples

Three inputs for `evalsurfer plan` that show how the planner infers which criteria
apply from the evidence present — the same rubric, scoped to what you actually have:

| File | Signals present | Applicable criteria |
| --- | --- | --- |
| [`answer_only.json`](answer_only.json) | an answer | 9 (generation + safety) |
| [`rag.json`](rag.json) | answer + retrieved docs + citations | 13 (adds RAG) |
| [`agent.json`](agent.json) | answer + tool calls | 13 (adds tool use) |

```bash
evalsurfer plan examples/plan/rag.json --pretty
```

As an MCP tool, the agent calls `plan(sample)` directly (see [`../../docs/mcp.md`](../../docs/mcp.md)).

See step 1 of the [tutorial](../README.md).
