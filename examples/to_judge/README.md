# `examples/to_judge/` — raw outputs for the LLM judge

These are **un-scored** AI-app outputs — the thing you hand to the judge. There
are no 1–5 scores here yet, because producing those scores *is the LLM's job*.

| File | What it is |
| --- | --- |
| [`rag_answer.json`](rag_answer.json) | A RAG answer + the retrieved context. The answer says refunds are within **30 days**; the retrieved policy says **14 days** — an ungrounded claim a judge should catch. |
| [`healthcare_unsafe_omission.json`](healthcare_unsafe_omission.json) | A longer, multi-paragraph medical RAG answer that reads well but **omits a life-threatening drug interaction** the retrieved sources warn about — unsafe by omission (should `fail` on safety). |
| [`legal_strong_answer.json`](legal_strong_answer.json) | A longer, fully-grounded, correctly-cited contract answer — a **strong "good answer" reference** (should `pass`). |

## How it gets judged

In your coding agent (Claude Code, Cursor, …) with the EvalSurfer skill installed:

> **Use EvalSurfer to evaluate this refund answer against the retrieved policy:**
> *(paste the contents of `rag_answer.json`)*

Your agent — **the LLM judge** — loads `SKILL.md`, decides which criteria apply,
reads the answer, notices `30 ≠ 14`, and scores each criterion 1–5 **with
evidence**. That reasoning is the LLM step; it happens in your session, not in
EvalSurfer's code.

The scores it produces are exactly the `scores` block captured in
[`../sample.json`](../sample.json) — which is why the rest of the
[tutorial](../README.md) can run offline with no API key.

In an agent session, that same agent then calls EvalSurfer's **MCP tools** —
`evaluate` for the full Interface pipeline (Metrics → Core → Analysis), `gate` to decide — with no external model. The
full transcript is in the [`../mcp/`](../mcp/) walkthrough.
