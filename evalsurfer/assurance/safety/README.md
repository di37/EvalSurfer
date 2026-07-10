# `evalsurfer/assurance/safety/` — executable red-team probes

A small, reusable battery of adversarial probes for the safety pillar, plus
deterministic triage of the collected outputs. No model calls; inputs never
mutated.

| Module | Public API | Purpose |
| --- | --- | --- |
| [`redteam.py`](redteam.py) | `RedTeam`, `RedTeamCase` | Select probes that fit a target's shape (`template`) and triage the responses (`check`). |

> **As MCP tools:** the harness LLM calls these directly via the `evalsurfer[mcp]` server — `redteam_template`, `redteam_check`. See [`../mcp/`](../../interface/mcp/) and [`../../docs/mcp.md`](../../../docs/mcp.md).

## Two helpers

- **`RedTeam.template(*, rag, agent, pii)`** — returns the probe dicts to send. A
  base battery (instruction-override injection, weapons jailbreak, discriminatory
  ranking) is always included; retrieval injection, tool exfiltration, and the
  PII-bait probe are added for RAG / agent / PII targets respectively.
- **`RedTeam.check(target_outputs)`** — triages the outputs. **Only PII has a
  reliable deterministic detector** (email / phone / SSN regex), so its
  `triggered` is a real boolean. Every other issue type is surfaced with
  `needs_judgment=True` for the skill to assess — no signal is ever fabricated.

## Honesty by design

Pattern matching cannot decide whether a model *followed* an injected
instruction, produced harmful content, or ranked people unfairly. Rather than
guess, this module does its deterministic half (PII) and hands the rest to the
judge. See [`../../README.md#safety-red-team-cases`](../../README.md#safety-red-team-cases).

```bash
evalsurfer redteam-template --rag --agent --pii --pretty
evalsurfer redteam-check collected_outputs.json --pretty
```
