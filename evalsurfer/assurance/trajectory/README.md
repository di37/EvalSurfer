# `evalsurfer/assurance/trajectory/` — Assurance layer: agent tool-call evaluation

Compare an agent's *actual* trajectory (the ordered tool calls it made) against
an *expected* specification, and report structured, deterministic findings. No
model calls; inputs never mutated.

| Module | Public API | Purpose |
| --- | --- | --- |
| [`agent_trace/`](agent_trace/) | `TrajectoryEvaluator`, `ToolCall`, `Finding` | Diff `actual` vs `expected` and return findings + error-recovery status. |

> **As an MCP tool:** the harness LLM calls this directly via the `evalsurfer[mcp]` server — `trajectory`. See [`../../interface/mcp/`](../../interface/mcp/) and [`../../../docs/mcp.md`](../../../docs/mcp.md).

## Checks

| Finding | Fires when |
| --- | --- |
| `missing_tool` | a required or sequenced tool was never called |
| `unnecessary_tool` | a forbidden tool was called, or a tool outside a declared toolset |
| `out_of_order` | sequenced tools appear in the wrong relative order |
| `bad_parameters` | a constrained tool call omits a required argument |
| `no_recovery` | a tool errored with no later successful retry |

The expected spec is intentionally partial — declare only `tool_sequence`,
`required_tools`, `forbidden_tools`, and/or `tool_parameters`; whatever you don't
declare isn't checked.

## Deferred judgment

Whether the final answer actually *follows* from the tool results is **not**
decided here — it is always returned as
`final_answer_consistency: {"needs_judgment": true}` for a human or the skill.

```bash
evalsurfer trajectory examples/agent_trace.json --pretty
```
