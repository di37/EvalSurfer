#!/usr/bin/env bash
# Shared scenario definitions for the EvalSurfer demo.
#
# Sourced by both run_all.sh (non-interactive) and demo.sh (interactive menu).
# Every step is printed as the exact command a user would type, then executed,
# so the demo doubles as a how-to. Nothing here calls a model or an API.

# --- locate the repo root (two levels up from examples/scenarios/) ------------
_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$_LIB_DIR/../.." && pwd)"
SCN="examples/scenarios"
cd "$REPO_ROOT" || exit 1
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

# --- resolve the CLI: prefer the installed console script, else python -m -----
if command -v evalsurfer >/dev/null 2>&1; then
  EJE=(evalsurfer)
  EJE_FALLBACK=0
else
  EJE=(python -m evalsurfer.cli.main)
  EJE_FALLBACK=1
fi

# --- generated reports go to a temp dir so the repo tree stays clean ----------
OUT="${OUT:-$(mktemp -d 2>/dev/null || echo "${TMPDIR:-/tmp}/eje-demo")}"
mkdir -p "$OUT"

# --- presentation helpers -----------------------------------------------------
_c_title=$'\033[1;36m'; _c_cmd=$'\033[0;33m'; _c_dim=$'\033[2m'; _c_off=$'\033[0m'
[ -t 1 ] || { _c_title=""; _c_cmd=""; _c_dim=""; _c_off=""; }

hr()    { printf '%s\n' "----------------------------------------------------------------"; }
title() { printf '\n%s══ %s ══%s\n' "$_c_title" "$1" "$_c_off"; }
note()  { printf '%s# %s%s\n' "$_c_dim" "$*" "$_c_off"; }

# cli <args...> : show the canonical `evalsurfer <args>` line, then run it.
# The banner goes to stderr so it never contaminates stdout when the caller
# pipes the command's JSON output into a summarizer.
cli() {
  printf '\n%s$ evalsurfer %s%s\n' "$_c_cmd" "$*" "$_c_off" >&2
  "${EJE[@]}" "$@"
  return $?
}

# gate is expected to exit non-zero when a report is below the bar; show it.
cli_expect_gate() {
  printf '\n%s$ evalsurfer %s%s\n' "$_c_cmd" "$*" "$_c_off" >&2
  "${EJE[@]}" "$@"; local rc=$?; printf '%s# -> exit code %d%s\n' "$_c_dim" "$rc" "$_c_off" >&2
}

peek() { note "inspecting $(basename "$1"):"; python -c "$2"; }

banner_env() {
  if [ "$EJE_FALLBACK" = "1" ]; then
    note "Using 'python -m evalsurfer.cli.main' (run 'pip install -e .' to get the 'evalsurfer' command)."
  fi
  note "Generated reports are written to: $OUT"
}

# =============================================================================
# Scenario 1 — VitalsAI: clinical-triage RAG that gives dangerous dosing advice
# =============================================================================
scenario_1() {
  title "SCENARIO 1 — VitalsAI clinical-triage RAG (plan → evaluate → validate → gate → diagnose)"
  note "A RAG assistant tells a warfarin patient to DOUBLE a missed dose — contradicting the retrieved guideline."

  note "1a. Adaptive scoping: infer which pillars/criteria apply from the sample."
  cli plan "$SCN/01_vitalsai_request.json" --pretty | python -c 'import sys,json;d=json.load(sys.stdin);c=d["plan"]["coverage"];print("   ->",c["applicable_criteria"],"/",c["total_criteria"],"criteria across",c["applicable_pillars"],"/",c["total_pillars"],"pillars (score",str(c["score"])+")")'

  note "1b. Assemble the full report (quality + safety + operational + diagnostics)."
  cli evaluate "$SCN/01_vitalsai_request.json" --pretty --out "$OUT/01_vitalsai_report.json" >/dev/null
  peek "$OUT/01_vitalsai_report.json" 'import json;d=json.load(open("'"$OUT"'/01_vitalsai_report.json"));print("   overall:",d["overall"]["score"],"| safety pillar:",d["pillars"]["safety"]["score"],"| DECISION:",d["decision"]);print("   -> a single CRITICAL safety issue fails the release even though the averages look healthy");print("   review_gate needs human review:",d["diagnostics"]["review_gate"]["needs_human_review"])'

  note "1c. Structurally validate the report (exit 0 = valid)."
  cli validate "$OUT/01_vitalsai_report.json"

  note "1d. Gate for release. --min pass should FAIL (exit 1); --min fail should pass (exit 0)."
  cli_expect_gate gate "$OUT/01_vitalsai_report.json" --min pass
  cli_expect_gate gate "$OUT/01_vitalsai_report.json" --min fail

  note "1e. Diagnose: attribute the gap from a perfect 10 to individual criteria."
  cli diagnose "$OUT/01_vitalsai_report.json" --pretty | python -c 'import sys,json;d=json.load(sys.stdin);e=d["explainability"];print("   perfect",e["perfect"],"-> overall",e["overall"],"; top deductions:");[print("     -",x["id"],"scored",x["score"],"loses",x["points_lost"]) for x in e["deductions"][:4]]'
}

# =============================================================================
# Scenario 2 — LedgerAgent: autonomous banking agent (trajectory + red-team)
# =============================================================================
scenario_2() {
  title "SCENARIO 2 — LedgerAgent banking agent (trajectory + red-team)"
  note "The agent skips identity verification, calls a forbidden delete_account, drops an idempotency key, and never recovers a failed call."

  note "2a. Trajectory: diff the actual tool calls against the expected spec."
  cli trajectory "$SCN/02_ledgeragent_trajectory.json" --pretty | python -c 'import sys,json;d=json.load(sys.stdin);[print("   finding:",f["type"],"->",f["detail"]) for f in d["findings"]];print("   recovered_after_error:",d["recovered_after_error"],"| final-answer consistency:",d["final_answer_consistency"])'

  note "2b. Generate a red-team probe battery for a tool-using target that handles PII."
  cli redteam-template --agent --pii --pretty | python -c 'import sys,json;d=json.load(sys.stdin);print(f"   -> {len(d)} probes:");[print("     -",p["id"],"["+p["issue_type"]+"]") for p in d]'

  note "2c. Triage the collected outputs. Only PII has a reliable deterministic detector; the rest are flagged for the judge."
  cli redteam-check "$SCN/02_ledgeragent_redteam_outputs.json" --pretty | python -c 'import sys,json;d=json.load(sys.stdin);[print("   ",r["case_id"],"triggered="+str(r["triggered"]),"needs_judgment="+str(r["needs_judgment"])) for r in d["results"]];print("   summary:",d["summary"])'
}

# =============================================================================
# Scenario 3 — BriefBot: news summarizer under production load (metrics + SLO)
# =============================================================================
scenario_3() {
  title "SCENARIO 3 — BriefBot summarizer at scale (operational metrics + SLO auto-scoring)"
  note "8 production requests, concurrency 2→30, one upstream timeout."

  note "3a. Raw operational metrics from request traces."
  cli metrics "$SCN/03_briefbot_traces.json" --pretty | python -c 'import sys,json;d=json.load(sys.stdin);s=d["summary"];L=s["latency"];print("   requests",s["request_count"],"| failures",s["failure_count"],"| failure_rate",round(s["failure_rate"],3));print("   latency median/p95/max ms:",L["median_ms"],"/",L["p95_ms"],"/",L["max_ms"]);print("   latency_under_load (p95 by concurrency):",{k:round(v["p95_ms"]) for k,v in sorted(d["latency_under_load"].items(),key=lambda kv:int(kv[0]))})'

  note "3b. Auto-score the operational pillar 1–5 by comparing measured metrics to the SLO."
  cli evaluate "$SCN/03_briefbot_ops_request.json" --pretty --out "$OUT/03_briefbot_report.json" >/dev/null
  peek "$OUT/03_briefbot_report.json" 'import json;d=json.load(open("'"$OUT"'/03_briefbot_report.json"));p=d["pillars"]["operational"];print("   DECISION:",d["decision"],"| operational pillar:",p["score"]);[print("     -",c["id"],"=",c["score"],"|",c["evidence"].split(";")[-1].strip()) for c in p["criteria"]]'
}

# =============================================================================
# Scenario 4 — Judge calibration for VitalsAI (the "eval of the eval")
# =============================================================================
scenario_4() {
  title "SCENARIO 4 — Judge calibration (eval of the eval)"
  note "Score 5 repeated judge runs against a hand-authored oracle. One run wrongly PASSES the dangerous answer."
  cli calibrate "$SCN/04_vitalsai_calibration.json" --pretty
  note "agreement 0.8 and false_pass_rate 0.2 catch the one unsafe miss; score_variance shows judge spread."
}

# =============================================================================
# Scenario 5 — HelpDeskAI regression v1 → v2 (evaluate ×2 + regression + maturity)
# =============================================================================
scenario_5() {
  title "SCENARIO 5 — HelpDeskAI regression v1 → v2 (regression diagnostic + maturity)"
  note "A billing answer improves from vague (v1) to complete (v2) — but gets a little verbose."

  cli evaluate "$SCN/05_helpdesk_v1_request.json" --out "$OUT/05_v1.json" >/dev/null
  cli evaluate "$SCN/05_helpdesk_v2_request.json" --out "$OUT/05_v2.json" >/dev/null
  peek "$OUT/05_v2.json" 'import json;a=json.load(open("'"$OUT"'/05_v1.json"));b=json.load(open("'"$OUT"'/05_v2.json"));print("   v1:",a["overall"]["score"],a["decision"]," ->  v2:",b["overall"]["score"],b["decision"]);m=b["diagnostics"]["maturity"];print("   v2 maturity:",m["level"],m["name"])'

  note "5b. Diff v2 against v1 to surface improvements AND regressions."
  cli diagnose "$OUT/05_v2.json" --before "$OUT/05_v1.json" --pretty | python -c 'import sys,json;d=json.load(sys.stdin);r=d["regression"];print("   overall delta:",r["overall_delta"],"| decision change:",r["decision_change"]);print("   improved:",r["improvements"]);print("   REGRESSED:",r["regressions"])'
}

# =============================================================================
# Scenario 6 — Ecosystem adapters (RAGAS / promptfoo / OTel / LangSmith)
# =============================================================================
scenario_6() {
  title "SCENARIO 6 — Ecosystem adapters (import external eval + trace artifacts)"
  note "Reuse scores/telemetry you already collected — no re-running the app."
  printf '\n%s$ python %s/06_adapters.py%s\n' "$_c_cmd" "$SCN" "$_c_off"
  python "$SCN/06_adapters.py"
}

run_all_scenarios() {
  banner_env
  scenario_1; scenario_2; scenario_3; scenario_4; scenario_5; scenario_6
  title "ALL SCENARIOS COMPLETE"
}
