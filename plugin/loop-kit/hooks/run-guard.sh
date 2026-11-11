#!/usr/bin/env bash
# run-guard.sh <guard-file>: run one loop guard from this plugin's hooks/ folder.
# Interpreter: $LOOP_PYTHON if executable, else $LOOP_HOME/venv/bin/python (LOOP_HOME defaults
# to ~/.loop) if executable, else deny (reason on stderr, exit 2: the hook fails closed).
# Never python3 from PATH. Only a bare hooks/ file name ending in -guard.py is accepted.
# stdin goes to the guard untouched and the guard's exit code is this script's exit code.

deny() {
  printf 'run-guard: %s\n' "$1" >&2
  exit 2
}

guard="${1:-}"
case "$guard" in
  "") deny "no guard file name given" ;;
  */* | *\\* | .*) deny "guard must be a bare file name in hooks/" ;;
  *-guard.py) ;;
  *) deny "guard file name must end in -guard.py" ;;
esac

root="${CLAUDE_PLUGIN_ROOT:-}"
if [ -z "$root" ]; then
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || deny "plugin root not found"
fi
target="$root/hooks/$guard"
[ -f "$target" ] || deny "guard file not found in hooks/"

py=""
if [ -n "${LOOP_PYTHON:-}" ] && [ -x "$LOOP_PYTHON" ]; then
  py="$LOOP_PYTHON"
else
  home="${LOOP_HOME:-$HOME/.loop}"
  if [ -x "$home/venv/bin/python" ]; then
    py="$home/venv/bin/python"
  fi
fi
[ -n "$py" ] || deny "no interpreter: set LOOP_PYTHON or create LOOP_HOME/venv (default ~/.loop/venv)"

exec "$py" "$target"
