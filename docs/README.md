# `docs/` — guardrails & guidance

Design rationale and responsible-use guidance for EvalSurfer — the "why" behind
the framework, framed as the failure modes it defends against.

| Doc | What it is |
| --- | --- |
| [`failure-modes.md`](failure-modes.md) | An *Evaluation Failure Modes* catalog (S1/S2/S3) — how AI evaluation itself fails, each mapped to the EvalSurfer feature that mitigates it. |
| [`anti-patterns.md`](anti-patterns.md) | Ten *Evaluation Anti-Patterns* with "do this instead → EvalSurfer feature". |
| [`mcp.md`](mcp.md) | Run EvalSurfer as an **MCP server** — the deterministic functions as tools your agent calls (judges + invokes, no external API). |

Related, at the repository root:

- [`../SECURITY.md`](../SECURITY.md) — threat model, disclosure policy, and safe use of the CI gate.

Format inspired by
[cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering),
adapted from operating agent loops to evaluating AI applications.
