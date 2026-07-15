# Governance mapping — EvalSurfer reports as assessment evidence

Governance instruments — UNESCO's Ethical Impact Assessment, the NIST AI RMF,
the EU AI Act's high-risk obligations, ISO/IEC management-system audits — all
eventually ask some version of the same question: *what testing did you
actually perform, and where is the evidence?* None of them generate that
evidence themselves; they are questionnaires, processes, and audits that
**consume** it.

EvalSurfer sits on the other side of that hand-off. Its output is a schema'd,
versioned, deterministic evidence artifact: judged quality and safety criteria
with per-score evidence, red-team probe results, operational SLO measurements,
coverage, judge-reliability statistics, and a machine-gated release decision.
This page maps those artifacts to the asks of four widely used frameworks so an
assessment answer can cite a concrete report field instead of a promise.

> **Scope and non-affiliation.** EvalSurfer is an independent project. It is
> not affiliated with, endorsed by, or certified by UNESCO, NIST, the European
> Union, or ISO/IEC, and running it does not constitute compliance with any of
> the frameworks below. The mappings paraphrase each framework's themes in our
> own words — consult the original texts (linked or named) for the
> authoritative wording. This page is practical guidance, not legal advice.

## How to use the mapping

1. Evaluate with the skill / MCP tools / CLI as usual and **keep the reports**
   (they conform to [`spec/report.schema.json`](../spec/report.schema.json)).
2. Gate releases in CI (`evalsurfer gate --policy guardrails.json`, or the
   bundled [GitHub Action](../action.yml)) so every release carries a recorded
   decision trail.
3. In the assessment, answer testing/robustness/oversight questions by citing
   the specific report fields below — report id, criterion ids, decision, and
   dates — rather than describing testing in the abstract.

The framework never calls a model and executes none of the content it
evaluates ([SECURITY.md](SECURITY.md)); the judging is done by the agent you
already run. State that division honestly in any assessment: EvalSurfer
contributes *deterministic measurement and structured judged evidence*, not an
ethics review.

## UNESCO — Recommendation on the Ethics of AI & Ethical Impact Assessment

UNESCO's [EIA](https://www.unesco.org/ethics-ai/en/eia) is a questionnaire and
deliberation process (scoping → principle alignment → impact mapping) applied
across the AI lifecycle. It performs no technical measurement — which is
exactly where EvalSurfer reports slot in as supporting evidence.

| UNESCO theme (paraphrased) | EvalSurfer evidence to cite |
| --- | --- |
| Safety, security, and do-no-harm | The judged **Safety** category (`toxicity`, `harmful_content`, `bias_fairness`, `pii_leakage`, `prompt_injection_resistance`) in `assurance.safety`, plus the executable red-team battery (`redteam_template` / `redteam_check`) and agent-trajectory checks |
| Fairness and non-discrimination | The `bias_fairness` criterion score with its evidence record, and the discriminatory-ranking red-team probe result |
| Privacy and data protection | The `pii_leakage` criterion, the PII-bait probe with deterministic detection (a *match* is a reliable hit; a non-match is flagged for judgment, never claimed as proof of safety), and the golden dataset's contamination controls |
| Transparency and explainability | Per-criterion `evidence` records (claim / supporting context / mismatch / confidence), `explain` (per-criterion score attribution), and `root_cause` |
| Human oversight and determination | `review_gate` (human-review recommendation from confidence + critical issues), the guardrail policy's `human_review_required` output and sensitive-path triggers, and the judge-reliability ladder (single → self-consistency → multi-judge → human) in the skill |
| Accountability and auditability | Versioned, schema-validated reports; the Core `gate` and Assurance `guardrail_gate` decisions; regression diffs between versions; `metadata.framework` / `metadata.version` stamps |
| Proportionality | The adaptive planner: criteria are assessed only where evidence exists, and the `coverage` block records exactly what was and was not assessed, with reasons |

UNESCO publishes these materials under CC BY-SA 3.0 IGO; this page references
and paraphrases them without reproducing their text.

## NIST AI Risk Management Framework (AI RMF 1.0)

The [AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) organizes
AI risk work into four functions. EvalSurfer is, in effect, tooling for the
MEASURE function that feeds the other three.

| RMF function | EvalSurfer evidence to cite |
| --- | --- |
| GOVERN | The machine-readable guardrail policy ([`examples/guardrails.json`](../examples/guardrails.json)): safety and coverage floors, block-on-critical, fix-attempt caps, sensitive-path review triggers — policy as reviewable code |
| MAP | `Signals` scoping and the adaptive plan (what kind of system this is and what applies), the maturity classifier (prompt app → self-improving), and the pipeline failure map |
| MEASURE | The entire Metrics layer (operational SLO scoring, reference metrics, golden dataset) and judged rubric — plus, distinctively, *measurement-quality* evidence: chance-corrected judge agreement (Cohen's/Fleiss's κ, Krippendorff's α), judge-vs-human calibration, and the cross-harness reliability decomposition (`harness_invariance`), which speaks directly to the RMF's concern that evaluations be **valid and reliable** |
| MANAGE | CI gating (`gate` / `guardrail_gate` and the GitHub Action), regression diffs across versions, and review-gate escalation paths |

NIST publications are U.S. government works in the public domain.

## EU AI Act (Regulation (EU) 2024/1689)

For high-risk systems, the Act's provider obligations include risk management,
data governance, logging, transparency, human oversight, and
accuracy/robustness — with technical documentation to substantiate them.
EvalSurfer reports are substantiating evidence for that documentation; they are
not a conformity assessment.

| Act theme (by article, paraphrased) | EvalSurfer evidence to cite |
| --- | --- |
| Risk management system (Art. 9) | Recurring red-team runs, guardrail-policy gating on every release, regression diffs demonstrating identified risks stay fixed |
| Data and data governance (Art. 10) | The versioned golden dataset: content-hashed cases, deterministic held-out splits, and contamination reporting (duplicates, blocklist, canaries) |
| Record-keeping / logging (Art. 12) | Request traces (natively or via the OTel / LangSmith / Langfuse adapters) and the schema'd evaluation reports as retained records |
| Transparency to deployers (Art. 13) | Reports with per-criterion scores, evidence, coverage, and known-limitation (`not_assessed`) declarations |
| Human oversight (Art. 14) | `review_gate` recommendations and guardrail `human_review_required` triggers wired into the release process |
| Accuracy, robustness, cybersecurity (Art. 15) | Reference accuracy metrics (exact match, F1, Recall@k, BLEU/ROUGE/METEOR), operational failure rate and latency-under-load, and prompt-injection / jailbreak resistance probe results |

## ISO/IEC 42001 (AI management systems)

ISO/IEC 42001 is a copyrighted, purchasable standard, so this section maps at
the level of clause *themes* only and reproduces none of its text. At that
level: EvalSurfer's Metrics and Analysis layers serve the standard's
performance-evaluation and monitoring/measurement themes; the planner,
coverage, and report artifacts serve its operational-planning and AI-impact-
assessment themes (see also ISO/IEC 42005 on AI system impact assessment); and
the guardrail policy plus CI gate serve its operational-control themes.
Organizations pursuing certification should work from the purchased text with
their auditor.

## What EvalSurfer deliberately does not do

Honesty about scope is part of being usable as evidence:

- It runs no stakeholder deliberation and assesses no societal or deployment
  context — that is the governance instrument's job.
- It certifies nothing. A `pass` decision is a technical gate against your own
  rubric and SLOs, not a compliance verdict.
- Its deterministic PII detection covers emails, US-style phone numbers, and
  SSNs; everything else is flagged for judgment rather than silently cleared.
- The judged criteria are scored by the coding agent you already run; the
  framework itself makes zero LLM calls. Judge quality is therefore itself
  measured (calibration, agreement, harness invariance) — cite those numbers
  alongside the scores.

## Attribution & reuse

- UNESCO Recommendation on the Ethics of AI (2021) and Ethical Impact
  Assessment (2023): © UNESCO, CC BY-SA 3.0 IGO — referenced and paraphrased
  here, not reproduced.
- NIST AI RMF 1.0 (2023): U.S. public domain.
- EU AI Act, Regulation (EU) 2024/1689: EU legal text via EUR-Lex.
- ISO/IEC 42001:2023: referenced by name only; the standard's text is not
  reproduced.
