# `skills/` — the portable EvalSurfer skill

The canonical home of the EvalSurfer skill, packaged to the
[agentskills.io](https://agentskills.io) `SKILL.md` standard so a single skill
runs across many harnesses.

| Path | What it is |
| --- | --- |
| [`eval-surfer/SKILL.md`](eval-surfer/SKILL.md) | The skill itself — the workflow the agent follows to run an evaluation. **This is the product;** the Python package is its supporting toolkit. |

Beyond the workflow, `SKILL.md` routes the agent to EvalSurfer's 47 deterministic
[MCP tools](../docs/mcp.md) — install `evalsurfer[mcp]` and run `evalsurfer-mcp` —
with the CLI and Python API as a fallback when the server isn't connected.

## Three staged copies, kept identical

The same skill is staged in three places so opening this repo directly in any
supported tool just works:

- `skills/eval-surfer/` — the standard location (this folder)
- `.claude/skills/eval-surfer/` — for Claude Code
- `.cursor/skills/eval-surfer/` — for Cursor

The three `SKILL.md` files are **byte-identical**, enforced by
[`../tests/skill/test_skill_parity.py`](../tests/skill/test_skill_parity.py). Edit the skill
in one place, then re-sync the copies (and run the parity test) before
committing.

## Install into your own project

```bash
/path/to/EvalSurfer/install-skill.sh claude           # -> .claude/skills/
/path/to/EvalSurfer/install-skill.sh hermes --global  # -> ~/.hermes/skills/
/path/to/EvalSurfer/install-skill.sh --list           # list all harnesses
```

See the [root README](../README.md#install) for the full per-harness directory
table (OpenClaw, Hermes, OpenCode, Codex, …).
