#!/usr/bin/env bash
# install.sh <interpreter> [--with-tests]  or  LOOP_PY=<interpreter> [LOOP_WITH_TESTS=1] install.sh : install the loop kit from this repository into $HOME.
#
#   bash install.sh /full/path/to/python
#   bash install.sh /full/path/to/python --with-tests
#
# Second form, with no positional argument: the interpreter is taken from LOOP_PY and tests are
# installed when LOOP_WITH_TESTS is 1. The environment is read only when no positional argument is given.
#   LOOP_PY=/full/path/to/python LOOP_WITH_TESTS=1 bash install.sh
#
# Order, so a failure early leaves nothing behind:
#   1. check the interpreter runs, and that this repository and $HOME are usable
#   2. refuse if any destination file or config.env already exists (nothing is overwritten)
#   3. copy the kit at the layout below
#   4. replace every @LOOP_PYTHON@ token in the copied files with the interpreter, and $HOME on the hook
#      command lines of the installed agent files with the literal home (C:/... form), and, when LOOP_OWNER is
#      set and non-empty, the OWNER_HANDLE token in the installed files with that value (otherwise it stays
#      and one line says it is set by hand)
#   5. write config.env last: the content goes to a temporary file in .loop, and the rename into place is
#      the final step after the success lines, so a half-finished install never has one
#
# Layout (repository -> $HOME):
#   agents/     -> .claude/agents/
#   hooks/      -> .claude/hooks/
#   skills/     -> .claude/skills/
#   bin/        -> .loop/bin/
#   templates/  -> .loop/templates/
#   tests/      -> .loop/tests/   only with --with-tests (the docker shim that `loop-tripwire selftest`
#                                 finds at bin/../tests); without the flag no tests directory is made
#
# Exit codes: 0 installed, 2 usage or unusable repository or HOME, 3 interpreter does not run,
# 4 something is already installed there, 5 a copy or fill step failed.
# This script never edits settings.json or CLAUDE.md, never pushes, and does not touch git.
set -u

SRC="$(cd "$(dirname "$0")" && pwd)"

WITH_TESTS=0
PYARG=""
if [ "$#" -eq 0 ]; then
  # environment form: read only when no positional argument is given
  PYARG="${LOOP_PY:-}"
  if [ "${LOOP_WITH_TESTS:-}" = "1" ]; then WITH_TESTS=1; fi
else
  for a in "$@"; do
    if [ "$a" = "--with-tests" ]; then
      WITH_TESTS=1
    elif [ -z "$PYARG" ]; then
      PYARG="$a"
    else
      PYARG=""
      break
    fi
  done
fi
if [ -z "$PYARG" ]; then
  echo "usage: bash install.sh <interpreter> [--with-tests]   or   LOOP_PY=<interpreter> [LOOP_WITH_TESTS=1] bash install.sh   (the full path of a python 3.8+ that runs)" >&2
  exit 2
fi

# 1. the interpreter must run before anything is written
if ! "$PYARG" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' </dev/null >/dev/null 2>&1; then
  echo "install.sh: the interpreter given does not run as python 3.8 or newer. Nothing was written." >&2
  exit 3
fi
# the path goes into hook command lines inside double quotes: forward slashes only, no spaces
PY="$(printf '%s' "$PYARG" | tr '\\' '/')"
case "$PY" in
  *[[:space:]]*) echo "install.sh: the interpreter path contains whitespace; use a path without it. Nothing was written." >&2; exit 2;;
esac
case "$PY" in
  /*|[A-Za-z]:/*) ;;
  *) echo "install.sh: note: the interpreter is not an absolute path; hooks will resolve it through PATH." >&2;;
esac

if [ -z "${HOME:-}" ] || [ ! -d "$HOME" ]; then
  echo "install.sh: HOME is not a directory. Nothing was written." >&2
  exit 2
fi
NEED="agents bin hooks skills templates"
if [ "$WITH_TESTS" -eq 1 ]; then NEED="$NEED tests"; fi
for d in $NEED; do
  if [ ! -d "$SRC/$d" ]; then
    echo "install.sh: the repository directory $d is missing; run this from a complete checkout. Nothing was written." >&2
    exit 2
  fi
done

# 2. destinations: the map of source dir -> destination dir under $HOME
MAP="agents:.claude/agents hooks:.claude/hooks skills:.claude/skills bin:.loop/bin templates:.loop/templates"
if [ "$WITH_TESTS" -eq 1 ]; then MAP="$MAP tests:.loop/tests"; fi
CONFIG="$HOME/.loop/config.env"
if [ -e "$CONFIG" ]; then
  echo "install.sh: .loop/config.env already exists under HOME. This home is already installed; nothing was written." >&2
  exit 4
fi
LIST="$(mktemp)" || { echo "install.sh: cannot make a temporary file. Nothing was written." >&2; exit 2; }
trap 'rm -f "$LIST"' EXIT
: >"$LIST"
for pair in $MAP; do
  s="${pair%%:*}"; t="${pair#*:}"
  ( cd "$SRC/$s" && find . -type f ! -name '*.pyc' ! -path '*/__pycache__/*' | sed 's|^\./||' | sort ) | while IFS= read -r f; do
    printf '%s\t%s\n' "$s/$f" "$t/$f"
  done >>"$LIST"
done
TOTAL="$(wc -l <"$LIST" | tr -d ' ')"
if [ "$TOTAL" -eq 0 ]; then
  echo "install.sh: found no files to copy. Nothing was written." >&2
  exit 2
fi
CLASH=0
while IFS="$(printf '\t')" read -r from to; do
  if [ -e "$HOME/$to" ]; then CLASH=$((CLASH + 1)); fi
done <"$LIST"
if [ "$CLASH" -gt 0 ]; then
  echo "install.sh: $CLASH destination file(s) already exist under HOME. Nothing was overwritten or written." >&2
  exit 4
fi

# 3. copy
while IFS="$(printf '\t')" read -r from to; do
  mkdir -p "$(dirname "$HOME/$to")" && cp -p "$SRC/$from" "$HOME/$to" || { echo "install.sh: copy failed for $from" >&2; exit 5; }
done <"$LIST"
echo "copied $TOTAL file(s)"

# 4. fill the interpreter token, in the copied files only
# Besides the token, on the hook command lines of the installed agent files the $HOME spelling is replaced
# by the literal home this install goes into (drive-letter forward-slash form, C:/... on Windows), so an
# installed agent file has no $HOME on any hook line. Other lines and other files keep $HOME as written.
if command -v cygpath >/dev/null 2>&1; then
  HOMELIT="$(cygpath -m "$HOME")"
else
  HOMELIT="$(printf '%s' "$HOME" | tr '\\' '/')"
fi
if [ -z "$HOMELIT" ]; then
  echo "install.sh: could not spell HOME as a literal path" >&2
  exit 5
fi
FILL='
import sys
tok = b"@LOOP_PYTHON@"
val = sys.argv[1].encode()
home = sys.argv[2].encode()
owner = sys.argv[3].encode()
otok = b"OWNER_HANDLE"
hits = files = lines = ohits = 0
for line in sys.stdin.read().split("\n"):
    p = line.strip("\r")
    if not p:
        continue
    data = open(p, "rb").read()
    new = data.replace(tok, val)
    if owner and otok in new:
        ohits += new.count(otok)
        new = new.replace(otok, owner)
    if p.startswith(".claude/agents/"):
        out = []
        front = 0
        for ln in new.split(b"\n"):
            if ln.strip(b"\r") == b"---":
                front += 1
            # hook command lines are the frontmatter entries that start with command:, never a prose line
            if front == 1 and ln.lstrip().startswith(b"command:") and b"$HOME" in ln:
                ln = ln.replace(b"$HOME", home)
                lines += 1
            out.append(ln)
        new = b"\n".join(out)
    if new != data:
        open(p, "wb").write(new)
        hits += data.count(tok)
        files += 1
print("filled %d token(s) in %d file(s), %d hook line(s) given the literal home, %d owner handle token(s)" % (hits, files, lines, ohits))
'
( cd "$HOME" && cut -f2 "$LIST" | "$PY" -c "$FILL" "$PY" "$HOMELIT" "${LOOP_OWNER:-}" ) || { echo "install.sh: filling the interpreter token failed" >&2; exit 5; }
if [ -z "${LOOP_OWNER:-}" ]; then
  echo "LOOP_OWNER is not set: the owner handle (the OWNER_HANDLE token) is set by hand in the installed files."
fi

# 5. the home's own directories and its config, last
mkdir -p "$HOME/.loop/goals" "$HOME/.loop/scratch" "$HOME/.loop/record/docs" || { echo "install.sh: could not make the .loop directories" >&2; exit 5; }
if [ -f "$HOME/.loop/templates/STATE.md" ] && [ ! -e "$HOME/.loop/record/docs/STATE.md" ]; then
  cp "$HOME/.loop/templates/STATE.md" "$HOME/.loop/record/docs/STATE.md" || exit 5
fi
TMPCFG="$HOME/.loop/config.env.tmp.$$"
trap 'rm -f "$LIST" "$TMPCFG"' EXIT
{
  echo "# config.env for this home, written by install.sh. No secrets belong in this file."
  echo "# Paths may start with ~; the loop tools expand it. Environment variables of the same name win."
  echo "LOOP_HOME=~/.loop"
  echo "LOOP_PY=$PY"
  echo "ENGINE_RECORD_DIR=~/.loop/record"
  echo "RECORD_BRANCH=record"
  echo "WRAPPERS=loop-guard-run loop-journal loop-scan loop-report loop-tripwire loop-ticket"
  echo "MAX_LEADERS=1"
  echo "SURFACES="
  echo "REPORT_SEND_CMD="
} >"$TMPCFG" || { echo "install.sh: could not write the temporary config file" >&2; exit 5; }

echo "installed. config.env written for this home."
echo "next: put .loop/bin on PATH, make .loop/record a git repository on branch record,"
echo "      register hooks/pretool-guard.py in settings.json (see README.md)."
# the rename is the final step: config.env exists only once every line above has run
mv "$TMPCFG" "$CONFIG" || { echo "install.sh: could not move config.env into place" >&2; exit 5; }
exit 0
