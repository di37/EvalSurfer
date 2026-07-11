# `docs/` — guardrails & guidance

Design rationale and responsible-use guidance for EvalSurfer — the "why" behind
the CIMAA-aligned framework, framed as the failure modes it defends against.

| Doc | What it is |
| --- | --- |
| [`failure-modes.md`](failure-modes.md) | An *Evaluation Failure Modes* catalog (S1/S2/S3) — how AI evaluation itself fails, each mapped to the EvalSurfer feature that mitigates it. |
| [`anti-patterns.md`](anti-patterns.md) | Ten *Evaluation Anti-Patterns* with "do this instead → EvalSurfer feature". |
| [`mcp.md`](mcp.md) | Run EvalSurfer as an **MCP server** (Interface) — deterministic tools grouped by CIMAA layer. |
| [`ROADMAP.md`](ROADMAP.md) | Where EvalSurfer is heading. |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history. |
| [`RELEASING.md`](RELEASING.md) | Publish checklist. |
| [`SECURITY.md`](SECURITY.md) | Threat model, disclosure, and safe use of the CI gate. |

Format inspired by
[cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering),
adapted from operating agent loops to evaluating AI applications.
