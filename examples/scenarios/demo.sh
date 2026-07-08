#!/usr/bin/env bash
# Interactive EvalSurfer demo.
#
#   bash examples/scenarios/demo.sh
#
# Presents a menu, asks which use case to run, and prints the exact command for
# every step before running it — so it doubles as a how-to. Deterministic; no
# model or API calls anywhere.

set -u
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

menu() {
  cat <<'MENU'

============================================================
  EvalSurfer — interactive demo
============================================================
  Pick a use case to run (each prints the commands it uses):

    1) VitalsAI     clinical RAG   — plan · evaluate · validate · gate · diagnose
    2) LedgerAgent  banking agent  — trajectory · red-team template & check
    3) BriefBot     at scale       — operational metrics · SLO auto-scoring
    4) Calibration  eval-of-eval   — score a judge against an oracle
    5) HelpDeskAI   v1 -> v2       — regression diagnostic · maturity
    6) Adapters     ecosystem      — RAGAS / promptfoo / OTel / LangSmith

    a) Run ALL          q) Quit
============================================================
MENU
}

# Allow a one-shot choice: `bash demo.sh 3` (or `a`). Otherwise loop the menu.
run_choice() {
  case "$1" in
    1) scenario_1 ;;
    2) scenario_2 ;;
    3) scenario_3 ;;
    4) scenario_4 ;;
    5) scenario_5 ;;
    6) scenario_6 ;;
    a|A|all) run_all_scenarios ;;
    q|Q|quit|exit) return 9 ;;
    *) note "Unknown choice: '$1' (pick 1-6, a, or q)." ;;
  esac
}

banner_env

if [ "$#" -ge 1 ]; then
  run_choice "$1"
  exit 0
fi

while true; do
  menu
  printf 'Your choice: '
  if ! read -r choice; then echo; break; fi          # EOF (piped/no TTY) -> exit
  [ -z "$choice" ] && continue
  run_choice "$choice"; rc=$?
  [ "$rc" = "9" ] && break
  printf '\n%s(done — press Enter for the menu, or q to quit)%s ' "$_c_dim" "$_c_off"
  read -r more || break
  [ "$more" = "q" ] || [ "$more" = "Q" ] && break
done
note "Bye."
