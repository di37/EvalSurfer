#!/usr/bin/env bash
# Run every EvalSurfer demo scenario end-to-end, non-interactively.
#
#   bash examples/scenarios/run_all.sh
#
# Set OUT=/some/dir to keep the generated reports; otherwise a temp dir is used.
set -u
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"
run_all_scenarios
