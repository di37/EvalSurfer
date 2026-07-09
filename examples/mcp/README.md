# `examples/mcp/` — the agent calls the tools (flagship)

This is EvalSurfer's **on-thesis** walkthrough: your coding agent is the judge, and it
calls EvalSurfer's deterministic functions as **MCP tools**. No external model, no eval
service — the only LLM in the loop is the agent you are already talking to.

Every number below is real. Reproduce it with the CLI, which calls the identical
functions: `python -m evalsurfer.cli.main evaluate ../sample.json`.

## 0. Install & connect (once)

Register the server in your harness — nothing to install first, it's fetched on first
launch. `.mcp.json` (Claude Code) or `.cursor/mcp.json` (Cursor):

```json
{ "mcpServers": { "evalsurfer": { "command": "uvx", "args": ["--from", "evalsurfer[mcp]", "evalsurfer-mcp"] } } }
```

(Prefer npm? `"command": "npx", "args": ["-y", "evalsurfer"]`.) Then install the skill so
the agent knows the workflow — from the repo root:

```bash
./install-skill.sh claude            # copies the eval-surfer skill into .claude/skills/
```

Restart the client. The 36 EvalSurfer tools now appear in the agent's toolset, and the
`eval-surfer` skill tells it how to use them.

## 1. Ask

Paste the raw output to judge — [`../to_judge/rag_answer.json`](../to_judge/rag_answer.json)
(an answer that says refunds are within **30 days** while the retrieved policy says **14**):

> **Use EvalSurfer to evaluate this refund answer against the retrieved policy:**
> ```json
> {"query": "What does the refund policy say about annual plans?",
>  "answer": "Annual plans are refundable within 30 days.",
>  "retrieved_docs": ["Annual plans are refundable within 14 days if usage is below 20% of the monthly quota."]}
> ```

## 2. Watch the agent work the skill

The agent loads `SKILL.md` and drives the tools. A representative transcript:

**① Scope — `plan`**
```
→ plan(sample={query, answer, retrieved_docs})
← 12 applicable criteria: core generation + RAG + safety.
  skipped: agent/tool-use (no tool calls), multi-turn (no history),
           operational (no traces), citation_accuracy (no citations).
```

**② Judge — the agent itself (the one step with no tool call)**
The agent reads `30 ≠ 14` and scores each applicable criterion 1–5 **with evidence**.
This reasoning happens in the harness LLM, not in EvalSurfer's code:
```
correctness_accuracy: 2   — "context says 14 days; the answer says 30"
groundedness_faithfulness: 2 — "refund window unsupported by the retrieved context"
relevance: 5, completeness: 4, instruction_following: 5,
context_relevance: 5, retrieval_recall: 4, toxicity … pii_leakage: 5
```

**③ Assemble — `evaluate`**
```
→ evaluate({sample, scores, evidence, traces, slo, top_issues})
← overall 8.7 → pass_with_fixes
  quality 7.7 · safety 10.0 · operational 8.4 · coverage 12/12
  top_issues: [major] the refund window is incorrect (correctness_accuracy)
```

**④ Decide — `gate`**
```
→ gate(report, min="pass")
← {"passed": false,
   "reason": "Decision 'pass_with_fixes' is below the minimum bar of 'pass'."}
```

(Optionally `diagnose(report)` for the explainability / root-cause / review-gate bundle,
or `guardrail_gate(report, policy, changed_files)` to enforce a full CI policy.)

## 3. The point

Look at ③: the aggregate is a healthy-looking **8.7**, yet the agent still surfaces the
**major** grounding error as the top issue — that is the judge doing its job, and the
gate holding the line at `min=pass`. Crucially, **not one of those tool calls invoked a
model.** The judgment lived entirely in the harness LLM; the tools only measured and
decided.

That is the whole thesis — see [how EvalSurfer differs](../../README.md#how-evalsurfer-is-different).

## Not running an agent?

If there is no harness LLM in the loop — a plain CI script, say — [`../judge/`](../judge/)
calls the Claude API directly to produce the scores instead. That is the fallback; this
MCP walkthrough is the native path. Full tool catalog: [`../../docs/mcp.md`](../../docs/mcp.md).
