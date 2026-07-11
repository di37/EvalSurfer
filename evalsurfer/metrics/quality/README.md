# `evalsurfer/metrics/quality/` — reference quality metrics

Programmatic scores when gold answers / labels / relevant docs exist:
retrieval (Recall@k, MRR), match (exact-match, F1), text (BLEU, ROUGE, METEOR).

**Naming:** this is *reference* quality measurement. The judged rubric category
**Quality** (correctness, groundedness, …) is scored by the agent (the skill);
Core only assembles those scores into the report — not this package.
