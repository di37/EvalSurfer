# `evalsurfer/metrics/` — CIMAA Metrics

Deterministic measurement: operational/SLO scoring, **reference** quality metrics
(BLEU/ROUGE/…), and the **eval golden dataset**. Not the agent-judged Quality
rubric category (that catalog lives in `constants/` and is scored by the judge).

| Subpackage | Role |
| --- | --- |
| [`operational/`](operational/) | Traces → latency/TTFT/cost/failure + SLO criterion scores |
| [`quality/`](quality/) | Reference retrieval / match / text metrics |
| [`dataset/`](dataset/) | Versioned eval golden dataset (≠ Analysis `GoldenSet`) |
