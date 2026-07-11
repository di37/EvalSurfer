# Tutorial — evaluate an AI app with EvalSurfer

A hands-on walkthrough of every EvalSurfer command, using the sample files in this
folder.

## Where's the LLM? (read this first)

EvalSurfer is **agent-native**: the LLM you're already using — your coding agent
(Claude Code, Cursor, …) — is the **judge**. It reads the AI output and scores each
criterion 1–5 with evidence. EvalSurfer's job is the deterministic **measurement**
around that judgment, which the agent runs by calling EvalSurfer's **MCP tools**.
Two roles, and the LLM lives in only one:

```
 raw AI output ──▶  🧠 YOUR AGENT (the LLM judge)  ──▶ scores ──▶ ⚙️ EvalSurfer tools
 (to_judge/)        reads SKILL.md, scores each                   plan · evaluate · gate
                    criterion 1–5 WITH evidence                   diagnose · metrics (NO LLM)
                    — the only LLM step                     the SAME agent calls them as
                                                            MCP tools (or the CLI, offline)
```

**Two ways to run the deterministic half — same functions either way:**

- **MCP tools (native).** In an agent session the agent calls `plan`, `evaluate`,
  `gate`, … as tools — no external model. Full transcript: **[`mcp/`](mcp/)**.
- **CLI (offline).** The same functions as `evalsurfer <cmd>` — what the numbered
  walkthrough below uses, so you can run it **with no API key**. The example inputs
  come **pre-scored** on purpose: those numbers are *what the judge produced*.

**Run the CLI walkthrough from the repository root.** With `pip install -e .`, use
`evalsurfer`; otherwise `python -m evalsurfer.interface.cli.main`. Add `--pretty` for indented
JSON. Steps marked 🧠 are where the LLM does the work; ⚙️ steps are pure deterministic math.

---

## 1. 🧠 The judge — the LLM scores a raw output

Start with an un-scored AI output — [`to_judge/rag_answer.json`](to_judge/rag_answer.json):
a RAG answer that says refunds are within **30 days** while the retrieved policy
says **14 days**.

In your agent, with the skill installed:

> **Use EvalSurfer to evaluate this refund answer against the retrieved policy:**
> *(paste `to_judge/rag_answer.json`)*

Your agent loads `SKILL.md`, notices `30 ≠ 14`, and returns 1–5 scores **with
evidence** — e.g. `correctness_accuracy: 2`, `groundedness_faithfulness: 2`. That
reasoning is the **LLM step**. Those exact scores are captured in
[`sample.json`](sample.json)'s `scores` block, which the deterministic steps below
consume. (See [`to_judge/`](to_judge/) for the full explanation.)

**Want to see it run end to end?** The on-thesis way is an agent calling the tools —
see the **[`mcp/`](mcp/) walkthrough**: connect the server, load the skill, and watch
the agent call `plan` → judge → `evaluate` → `gate`, no external model. For a pipeline
with **no harness LLM**, [`judge/`](judge/) has a runnable script (`llm_judge.py`) that
calls the Claude API directly to score, then runs the Interface pipeline — run it for real
with an API key, or **offline** with `--mock` ([`judge/README.md`](judge/README.md)).

## 2. ⚙️ Plan — which criteria should the judge even score?

Before judging, the **planner** infers which criteria apply from the evidence
present — so simple apps aren't over-evaluated. Compare three inputs:

```bash
evalsurfer plan examples/plan/answer_only.json   # just an answer
evalsurfer plan examples/plan/rag.json           # + retrieved docs + citations
evalsurfer plan examples/plan/agent.json         # + tool calls
```

→ Applicable criteria grow with the evidence: **9** → **13** → **13**. Each skip
comes back with a reason, plus a coverage score. (Deterministic — this tells the
judge *what* to score.)

## 3. ⚙️ Evaluate — Interface pipeline (Metrics enrich → Core assemble → Analysis diagnose)

[`sample.json`](sample.json) is a full request: the sample, the **judge's**
per-criterion scores + evidence, traces + an SLO, and top issues. Interface
`evaluate` (CLI/MCP) runs the full pipeline — Metrics ops enrich → Core assemble →
Analysis diagnostics — producing metrics, assurance, overall, decision, coverage,
and diagnostics:

```bash
evalsurfer evaluate examples/sample.json --pretty --out my_report.json
```

→ A complete report. [`report.json`](report.json) is a reference of that shape.
(No LLM here — the scores already came from the judge in step 1.)

## 4. ⚙️ Validate — is a report well-formed?

```bash
evalsurfer validate examples/report.json
```

→ `{"valid": true, "errors": []}` (exit `0`). Invalid reports exit `1`.

## 5. ⚙️ Gate — should this release ship?

**a) Minimum decision:**
```bash
evalsurfer gate examples/report.json --min pass
```
→ Blocked (exit `1`): the report is `pass_with_fixes`, below `pass`.

**b) A guardrail policy** ([`guardrails.json`](guardrails.json)):
```bash
evalsurfer gate examples/report.json --policy examples/guardrails.json
```
→ `"blocks": ["Decision 'pass_with_fixes' is below the minimum bar of 'pass'.", "coverage 0.222 below floor 0.6"]`

**c) With the release's changed files** ([`changed_files.txt`](changed_files.txt)):
```bash
evalsurfer gate examples/report.json --policy examples/guardrails.json \
  --changed-files examples/changed_files.txt
```
→ `"sensitive_paths_touched": ["src/payments/checkout.py"], "human_review_required": true`.
In CI: `--changed-files <(git diff --name-only origin/main...HEAD)`.

## 6. ⚙️ Diagnose — explain and compare

**Explain** one report (deductions from a perfect 10, root cause, review gate):
```bash
evalsurfer diagnose examples/report.json --pretty
```

**Regression** — diff an earlier report ([`report_before.json`](report_before.json)):
```bash
evalsurfer diagnose examples/report.json --before examples/report_before.json
```
→ `overall delta 0.9`, decision `fail → pass_with_fixes`, improved
`[correctness_accuracy, time_to_first_token]`, **regressed** `[groundedness_faithfulness]`.

## 7. ⚙️ Metrics — operational numbers from traces (never an LLM)

[`traces.json`](traces.json) is a request-traces payload:
```bash
evalsurfer metrics examples/traces.json --pretty
```
→ `requests 3, failure_rate 0.333`, plus latency/TTFT percentiles, cost, and
latency-under-load. The operational category is fully deterministic — no judge needed.

## 8. 🧠→⚙️ Calibrate — evaluate the evaluator

[`golden/calibration.json`](golden/calibration.json) pins what a trustworthy judge
should conclude, plus the judge's actual reports. This is how you check the **LLM
judge** itself:
```bash
evalsurfer calibrate examples/golden/calibration.json --pretty
```
→ `agreement 0.5, false_pass_rate 0.5` — one judge run wrongly passed a failing answer.

## 9. 🧠→⚙️ Red-team — probe safety

**Generate probes** to send to your app (`--rag` / `--agent` / `--pii`):
```bash
evalsurfer redteam-template --agent --pii --pretty
```
→ 5 adversarial probes. **Triage the collected outputs**
([`redteam_outputs.json`](redteam_outputs.json)):
```bash
evalsurfer redteam-check examples/redteam_outputs.json --pretty
```
→ `checked 6, deterministic_hits 1, needs_judgment 5`. Only PII has a reliable
detector (it catches the leaked email/phone/SSN); the rest are honestly flagged
for the **judge** — never fabricated.

## 10. ⚙️ Trajectory — did the agent use tools correctly?

[`agent_trace.json`](agent_trace.json) — the agent's `actual` tool calls vs an
`expected` spec:
```bash
evalsurfer trajectory examples/agent_trace.json --pretty
```
→ `findings: ["bad_parameters"]`. Also checks missing / unnecessary / out-of-order
tools and error recovery. (The final-answer consistency is flagged for the judge.)

## 11. ⚙️ Adapters — import scores/traces you already have (Python)

The adapters (RAGAS / promptfoo / OTel / LangSmith) have **no CLI verb** — the agent
calls them as MCP tools (`adapter_ragas` / `adapter_promptfoo` / `adapter_otel` /
`adapter_langsmith`), or run them from Python:
```bash
python examples/adapters/run.py
```
→ RAGAS metrics → rubric criteria; promptfoo results → a report; OTel/LangSmith
traces → request traces, fed through the operational metrics.

---

## Next: the guided demo

Six realistic, end-to-end scenarios with an interactive runner:

```bash
bash examples/scenarios/demo.sh        # pick a scenario from a menu
bash examples/scenarios/run_all.sh     # run them all
```

See [`scenarios/README.md`](scenarios/README.md).

## File reference

| Path | Used by | What it is |
| --- | --- | --- |
| [`mcp/`](mcp/) | 🧠 agent + MCP tools | **Flagship** — connect the server, load the skill, watch the agent call `plan` → judge → `evaluate`/`gate`. |
| [`to_judge/`](to_judge/) | 🧠 the LLM judge | Raw, **un-scored** AI outputs — what you hand to your agent to score. |
| [`judge/`](judge/) | 🧠 LLM API (no harness) | Non-agent alternative: a script calling the Claude API directly → report printed + saved (or `--mock`). |
| [`plan/`](plan/) | `plan` | Three samples showing adaptive scoping. |
| [`sample.json`](sample.json) | `evaluate` | A full request — the **judge's** scores + sample + traces. |
| [`report.json`](report.json) | `validate`, `gate`, `diagnose` | The reference report shape. |
| [`report_before.json`](report_before.json) | `diagnose --before` | An earlier report, to diff for a regression. |
| [`guardrails.json`](guardrails.json) | `gate --policy` | A release policy (floors, denylist, attempt cap). |
| [`changed_files.txt`](changed_files.txt) | `gate --changed-files` | A changed-file list for the sensitive-path denylist. |
| [`traces.json`](traces.json) | `metrics` | A request-traces payload. |
| [`golden/`](golden/) | `calibrate` | A calibration oracle + judge reports. |
| [`redteam_outputs.json`](redteam_outputs.json) | `redteam-check` | Collected probe outputs (one leaks PII). |
| [`agent_trace.json`](agent_trace.json) | `trajectory` | An agent trajectory vs an expected spec. |
| [`adapters/`](adapters/) | Python API | RAGAS / promptfoo / OTel / LangSmith inputs + `run.py`. |
| [`scenarios/`](scenarios/) | demo | Six worked end-to-end scenarios + runners. |
