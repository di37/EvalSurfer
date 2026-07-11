# `evalsurfer/assurance/policy/` — Assurance layer: release guardrails

Where Core [`report/`](../../core/report/)'s `Gate` checks a report against a
single minimum decision, this subpackage lets a team encode a **release policy**
in one `guardrails.json` file and have Assurance `Guardrails` /
`guardrail_gate` enforce it (composing Core `Gate` + Analysis `ReviewGate`). No
model calls; inputs never mutated; stdlib-only (`json` + `fnmatch`).

| Module | Public API | Purpose |
| --- | --- | --- |
| [`guardrails/`](guardrails/) | `GuardrailPolicy`, `Guardrails` | Load + validate a policy, then check a report (and the release's changed files) against it. |

> **As an MCP tool:** the harness LLM calls `Guardrails.check` directly via the `evalsurfer[mcp]` server — `guardrail_gate`. See [`../../interface/mcp/`](../../interface/mcp/) and [`../../../docs/mcp.md`](../../../docs/mcp.md).

## Policy fields (`guardrails.json`)

| Field | Effect |
| --- | --- |
| `min_decision` | Minimum passing decision (reuses Core's `Gate`). |
| `min_safety` | Block if the safety-category score is below this (0–10). |
| `coverage_floor` | Block if the coverage score is below this (0–1). |
| `block_on_critical_issue` | Block if any top issue is `critical`. |
| `max_fix_attempts` | Block when the `--attempt` number exceeds this. |
| `sensitive_paths` | Changed files matching these globs force **human review**. |

`Guardrails.check()` composes Core's `Gate` and Analysis
[`ReviewGate`](../../analysis/diagnostics/review_gate/); a release is `allowed`
only when no rule blocks it **and** no human review is required.

## Usage

```bash
evalsurfer gate report.json --policy guardrails.json \
  --changed-files <(git diff --name-only origin/main...HEAD)
# exit 0 only if allowed; non-zero if blocked or a sensitive path was touched
```

The GitHub Action ([`action.yml`](../../../action.yml)) exposes `policy` and
`changed-files` inputs for the same check in CI. Example policy:
[`examples/guardrails.json`](../../../examples/guardrails.json). Rationale:
[`docs/failure-modes.md`](../../../docs/failure-modes.md) and
[`SECURITY.md`](../../../docs/SECURITY.md#using-the-ci-gate-safely).
