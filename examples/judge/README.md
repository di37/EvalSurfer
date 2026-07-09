# Walkthrough — from a query/answer pair to an evaluated, saved report

The complete round-trip a real user takes: **load the skill → point at your
query/response pairs → the LLM judges → results are displayed and saved as JSON.**

There are two ways to run the judge. Both use the *same* rubric; the only
difference is whether the LLM judging happens inside your coding agent or in a
Python script.

> **Looking for the flagship walkthrough?** [`../mcp/`](../mcp/) shows the agent
> calling EvalSurfer's tools (`plan` → judge → `evaluate` → `gate`) end to end — the
> native, no-external-model path. This page zooms in on the *judge* step and adds a
> runnable script alternative for pipelines with no harness LLM.

```
                              ┌─ A. IN YOUR HARNESS (no code) ─┐
 query / answer pair ────────▶│  agent reads SKILL.md, judges  │────▶ report (in chat / saved)
 (examples/judge/qa_pairs)    └────────────────────────────────┘
                              ┌─ B. PYTHON SCRIPT + LLM ───────┐
                        ─────▶│  llm_judge.py → Claude judges  │────▶ printed + report.json
                              │  → EvalSurfer assembles report │
                              └────────────────────────────────┘
```

---

## Step 0 — Load the skill into your harness

From your project directory, copy the `eval-surfer` skill into where your harness
looks (the repo ships an installer):

```bash
/path/to/EvalSurfer/install-skill.sh claude     # Claude Code  -> .claude/skills/eval-surfer/
/path/to/EvalSurfer/install-skill.sh cursor     # Cursor       -> .cursor/skills/eval-surfer/
/path/to/EvalSurfer/install-skill.sh --list     # all supported harnesses
```

The harness discovers the skill by its `description` and loads it automatically
when your request matches. (Full per-harness table: the [root README](../../README.md#install).)

## Step 1 — Point at your query/response pairs

Put the answers you want judged in a JSON list — see
[`qa_pairs.json`](qa_pairs.json):

```json
[
  { "query": "What does the refund policy say about annual plans?",
    "answer": "Annual plans are refundable within 30 days.",
    "retrieved_docs": ["Annual plans are refundable within 14 days …"] }
]
```

## Step 2 — Judge it

### Path A — in your harness (recommended; the agent is the judge)

Just ask, and paste a pair:

> **Use EvalSurfer to evaluate these answers against their retrieved context, and
> save the report as `report.json`:** *(paste `qa_pairs.json`)*

Your agent loads the skill, scores each applicable criterion 1–5 **with evidence**,
and hands back the report (and writes the JSON). No API key beyond your normal
agent session — the agent *is* the LLM. See [`../mcp/`](../mcp/) for the full
transcript of the agent calling `plan`, `evaluate`, and `gate` as deterministic tools.

### Path B — a Python script (`llm_judge.py`)

> **On-thesis alternative:** if your agent speaks MCP, prefer the
> [MCP server](../../docs/mcp.md) — the harness LLM judges *and* calls the
> deterministic tools, so **nothing external is called**. The script below calls a
> model API directly; it's for pipelines/CI that have no harness LLM.

For pipelines/CI, run the judge as a script. It calls Claude to produce the
scores, then EvalSurfer's deterministic layer assembles, prints, and saves them:

```bash
pip install "evalsurfer[llm]"        # installs the anthropic SDK (optional extra)
export ANTHROPIC_API_KEY=sk-...

python examples/judge/llm_judge.py examples/judge/qa_pairs.json --out report.json
```

**No API key?** Run the *same* pipeline offline with canned judge output:

```bash
python examples/judge/llm_judge.py examples/judge/qa_pairs.json \
    --mock examples/judge/mock_scores.json --out report.json
```

## Step 3 — Results displayed + JSON saved

```
[1/1] What does the refund policy say about annual plans?
  decision: PASS  |  overall 8.7/10  (quality 7.4, safety 10)
    [major] The refund window is wrong (30 vs 14 days).

saved report → report.json
```

The saved `report.json` is a full EvalSurfer report (pillars, overall, decision,
coverage, diagnostics) — treat it like any other report:

```bash
evalsurfer validate report.json          # exit 0 — well-formed
evalsurfer gate report.json --min pass    # exit 0 — it's a PASS
```

> **Batching:** pass more than one pair in `qa_pairs.json` and `--out` writes a
> JSON array — one report per answer (validate/gate them one at a time).

## ⚠️ Teaching moment — the judge caught it, but it still PASSED

Look again: the judge flagged a real, ungrounded error (`correctness_accuracy`
2/5, **with evidence**) — yet the decision is **pass** at 8.7, and a guardrail gate
allows it. That's the [Average-Washing](../../docs/failure-modes.md#average-washing)
failure mode: one `major` **quality** issue doesn't sink a strong aggregate, and
EvalSurfer's hard-fail override fires only on **critical safety** issues, not
quality ones.

The point isn't that the gate rescues you here — it's that the issue is **visible,
with evidence**, instead of buried under an 8.7. What ships is a *policy* choice:

- Read `top_issues` and the per-criterion evidence, not just the number.
- If grounding errors must block in your domain, raise the bar (require a higher
  overall) or treat grounding as safety-relevant so a `critical` safety issue
  hard-fails.

Separating the **LLM's judgment** (catch it, with evidence) from the
**deterministic decision** (what your policy ships) is the whole design.

## Files

| File | What it is |
| --- | --- |
| [`llm_judge.py`](llm_judge.py) | The LLM-backed judge script (real Claude call, or `--mock` offline). |
| [`qa_pairs.json`](qa_pairs.json) | The query/answer/context pairs to judge. |
| [`mock_scores.json`](mock_scores.json) | Canned judge output, so the pipeline runs without an API key. |

> The core `evalsurfer` package never imports `anthropic`; only this example does.
> `pip install "evalsurfer[llm]"` adds the SDK for Path B.
