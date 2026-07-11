# `evalsurfer/assurance/` — CIMAA Assurance

Harden what ships: red-team probes, agent trajectory diffs, and enforceable
guardrail policy on top of Core's `Gate`.

| Subpackage | Role |
| --- | --- |
| [`safety/`](safety/) | Red-team templates + deterministic PII triage |
| [`trajectory/`](trajectory/) | Actual vs expected tool-call trajectories |
| [`policy/`](policy/) | `Guardrails` / MCP `guardrail_gate` |

Human-review recommendations come from Analysis `ReviewGate`, not this layer.
Assurance `Guardrails.check` *composes* Analysis `ReviewGate` so a policy can
require human review — that is dependency (Assurance → Analysis), not ownership
transfer: `ReviewGate` stays Analysis; policy enforcement stays Assurance.
