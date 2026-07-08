#!/usr/bin/env bash
#
# Install the EvalSurfer skill into an agent harness.
#
# EvalSurfer ships as a portable agentskills.io SKILL.md, so the same skill
# works across every harness that reads the standard. This script just copies
# it into the directory your harness looks in.
#
# Usage:
#   ./install-skill.sh <harness> [--global]     # copy into a harness directory
#   ./install-skill.sh --dest <dir>             # copy into an explicit directory
#   ./install-skill.sh --list                   # list known harnesses
#
# Examples:
#   cd ~/my-project && /path/to/install-skill.sh claude       # -> .claude/skills/
#   ./install-skill.sh hermes --global                        # -> ~/.hermes/skills/
#   ./install-skill.sh openclaw                               # -> ./skills/
#   ./install-skill.sh --dest ~/work/app/.cursor/skills
#
set -euo pipefail

SKILL_NAME="eval-surfer"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/skills/$SKILL_NAME"

# harness | project directory | global directory ("-" = none)
HARNESSES="
claude|.claude/skills|$HOME/.claude/skills
cursor|.cursor/skills|$HOME/.cursor/skills
openclaw|skills|$HOME/.openclaw/skills
hermes|skills|$HOME/.hermes/skills
opencode|skills|-
codex|skills|-
standard|skills|-
"

die() { echo "error: $*" >&2; exit 1; }

list_harnesses() {
  echo "Known harnesses (project dir -> global dir):"
  printf '%s\n' "$HARNESSES" | while IFS='|' read -r name proj glob; do
    [ -n "$name" ] || continue
    echo "  $name  ->  $proj/$SKILL_NAME  |  ${glob}/$SKILL_NAME"
  done
  echo
  echo "'standard' targets the portable ./skills directory that OpenClaw,"
  echo "Hermes, OpenCode, Codex, and other agentskills.io tools read directly."
}

lookup() {  # $1 = harness, $2 = project|global -> prints target base dir
  printf '%s\n' "$HARNESSES" | while IFS='|' read -r name proj glob; do
    if [ "$name" = "$1" ]; then
      if [ "$2" = "global" ]; then printf '%s' "$glob"; else printf '%s' "$proj"; fi
      return
    fi
  done
}

[ -d "$SRC" ] || die "canonical skill not found at $SRC"

case "${1:-}" in
  "" ) die "no harness given. Run with --list to see options." ;;
  --list ) list_harnesses; exit 0 ;;
  --dest )
    [ -n "${2:-}" ] || die "--dest needs a directory"
    base="$2"
    ;;
  * )
    harness="$1"
    scope="project"
    [ "${2:-}" = "--global" ] && scope="global"
    base="$(lookup "$harness" "$scope")"
    [ -n "$base" ] || die "unknown harness '$harness'. Run with --list."
    [ "$base" = "-" ] && die "'$harness' has no global directory; drop --global."
    ;;
esac

dest="$base/$SKILL_NAME"
mkdir -p "$dest"
cp -R "$SRC/." "$dest/"
echo "Installed EvalSurfer skill -> $dest"
