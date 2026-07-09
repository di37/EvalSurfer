# Stories — evaluation post-mortems

Short, blameless write-ups of times AI **evaluation** went wrong: a bad release
passed the gate, a good one was wrongly blocked, a judge rubber-stamped a
hallucination, a guardrail over-fired. Each story names the
[failure mode](../docs/failure-modes.md) it belongs to and ends with the concrete
change that prevents a repeat — a `guardrails.json` rule, a calibration case, a
tightened floor, or a process tweak.

> Format inspired by the `stories/` post-mortems in
> [cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering),
> adapted from operating agent loops to evaluating AI applications.

## Add a story

1. Copy [`TEMPLATE.md`](TEMPLATE.md) to `NNNN-short-slug.md` (next number).
2. Keep it blameless — focus on the system and the fix, not the person.
3. Link the failure mode and the durable prevention.
4. Add a row to the index below.

## Index

| # | Story | Severity | Failure mode |
| --- | --- | --- | --- |
| [0001](0001-average-washed-critical.md) | A critical safety issue shipped behind a healthy average | S3 | Average-Washing |
| [0002](0002-rubber-stamp-judge.md) | A cheap judge passed ungrounded RAG answers | S2 | Judge Theater |
| [0003](0003-overzealous-denylist.md) | A guardrail denylist over-blocked and eroded trust | S1 | (guardrail misconfiguration) |

> The seed stories below are **illustrative** — synthetic incidents that show the
> template and reinforce the failure-mode catalog. Replace/append with real ones
> as they happen.
