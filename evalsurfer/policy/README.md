# `evalsurfer/policy/` — machine-readable release guardrails

Where [`core/report.py`](../core/report.py)'s `Gate` checks a report against a
single minimum decision, this subpackage lets a team encode a **release policy**
in one `guardrails.json` file and have the gate enforce it deterministically. No
model calls; inputs never mutated; stdlib-only (`json` + `fnmatch`).

| Module | Public API | Purpose |
| --- | --- | --- |
| [`guardrails.py`](guardrails.py) | `GuardrailPolicy`, `Guardrails` | Load + validate a policy, then check a report (and the release's changed files) against it. |

> **As an MCP tool:** the harness LLM calls `Guardrails.check` directly via the `evalsurfer[mcp]` server — `guardrail_gate`. See [`../mcp/`](../mcp/) and [`../../docs/mcp.md`](../../docs/mcp.md).

## Policy fields (`guardrails.json`)

| Field | Effect |
| --- | --- |
| `min_decision` | Minimum passing decision (reuses `Gate`). |
| `min_safety` | Block if the safety-pillar score is below this (0–10). |
| `coverage_floor` | Block if the coverage score is below this (0–1). |
| `block_on_critical_issue` | Block if any top issue is `critical`. |
| `max_fix_attempts` | Block when the `--attempt` number exceeds this. |
| `sensitive_paths` | Changed files matching these globs force **human review**. |

`Guardrails.check()` composes the existing `Gate` and
[`ReviewGate`](../diagnostics/review_gate.py); a release is `allowed` only when no
rule blocks it **and** no human review is required.

## Usage

```bash
evalsurfer gate report.json --policy guardrails.json \
  --changed-files <(git diff --name-only origin/main...HEAD)
# exit 0 only if allowed; non-zero if blocked or a sensitive path was touched
```

The GitHub Action ([`action.yml`](../../action.yml)) exposes `policy` and
`changed-files` inputs for the same check in CI. Example policy:
[`examples/guardrails.json`](../../examples/guardrails.json). Rationale:
[`docs/failure-modes.md`](../../docs/failure-modes.md) and
[`SECURITY.md`](../../docs/SECURITY.md#using-the-ci-gate-safely).
