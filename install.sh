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
# Upgrade mode, environment form only (no positional argument): LOOP_UPGRADE=1 and LOOP_BACKUP_DIR=<absent or empty
# folder> against a home whose .loop holds config.env. Every file it is about to replace is first copied into
# LOOP_BACKUP_DIR under the same relative path; then every kit file under bin, templates, skills and agents is replaced
# with the bundle's text and the same three fills (OWNER_HANDLE: LOOP_OWNER_HANDLE when set, otherwise the word the
# existing file holds where the bundle line holds the token), and a bundle file the home lacks is added. config.env, the
# names list and everything else stay as they are. The hooks directory is touched only when LOOP_UPGRADE_HOOKS is also
# 1. One line per file replaced or added, with its sha256 before and after, then one line with four counts (replaced,
# added, unchanged, hooks skipped). Run again, it replaces 0 and adds 0. Without LOOP_UPGRADE an installed home still
# exits 4. A home with no config.env exits 5 (nothing to upgrade). A LOOP_BACKUP_DIR that is unset or not empty is
# refused with exit 2 before any write.
#
# Exit codes: 0 installed (or upgraded), 2 usage or unusable repository or HOME or backup folder, 3 interpreter does not
# run, 4 something is already installed there, 5 a copy or fill step failed, or an upgrade found no config.env.
# This script never edits settings.json or CLAUDE.md, never pushes, and does not touch git.
set -u

SRC="$(cd "$(dirname "$0")" && pwd)"

# spell a path as a drive-letter forward-slash literal (C:/... on Windows)
spell() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -m "$1"
  else
    printf '%s' "$1" | tr '\\' '/'
  fi
}

WITH_TESTS=0
UPGRADE=0
PYARG=""
if [ "$#" -eq 0 ]; then
  # environment form: read only when no positional argument is given
  PYARG="${LOOP_PY:-}"
  if [ "${LOOP_WITH_TESTS:-}" = "1" ]; then WITH_TESTS=1; fi
  if [ "${LOOP_UPGRADE:-}" = "1" ]; then UPGRADE=1; fi
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
if [ "$UPGRADE" -eq 0 ] && [ -e "$CONFIG" ]; then
  echo "install.sh: .loop/config.env already exists under HOME. This home is already installed; nothing was written." >&2
  exit 4
fi
if [ "$UPGRADE" -eq 1 ]; then
  if [ ! -e "$CONFIG" ]; then
    echo "install.sh: LOOP_UPGRADE is set but .loop/config.env does not exist under HOME; there is nothing to upgrade. Nothing was written." >&2
    exit 5
  fi
  BK="$(printf '%s' "${LOOP_BACKUP_DIR:-}" | tr '\\' '/')"
  if [ -z "$BK" ]; then
    echo "install.sh: LOOP_UPGRADE needs LOOP_BACKUP_DIR set to an absent or empty folder; it is unset. Refused; nothing was written." >&2
    exit 2
  fi
  case "$BK" in
    /*|[A-Za-z]:/*) ;;
    *) BK="$(pwd)/$BK";;
  esac
  if [ -e "$BK" ] && { [ ! -d "$BK" ] || [ -n "$(ls -A "$BK" 2>/dev/null)" ]; }; then
    echo "install.sh: LOOP_BACKUP_DIR is not an empty folder. Refused; nothing was written." >&2
    exit 2
  fi
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

# 2b. upgrade mode: replace, add, back up, report; the plain install below is not reached
if [ "$UPGRADE" -eq 1 ]; then
  HOMELIT="$(spell "$HOME")"
  SRCLIT="$(spell "$SRC")"
  BKLIT="$(spell "$BK")"
  if [ -z "$HOMELIT" ] || [ -z "$SRCLIT" ] || [ -z "$BKLIT" ]; then
    echo "install.sh: could not spell a path as a literal path. Nothing was written." >&2
    exit 5
  fi
  UPG='
import hashlib, os, re, shutil, sys
src, home, py, bk, uph, owner = sys.argv[1:7]
tok = b"@LOOP_PYTHON@"
otok = b"OWNER_HANDLE"
pyb, hb, ob = py.encode(), home.encode(), owner.encode()
uph = (uph == "1")

def sha(b):
    return hashlib.sha256(b).hexdigest()

def keep(new, old):
    # where a bundle line holds the owner token, take the word that stands at the same place in the existing file
    oldlines = [l.rstrip(b"\r") for l in old.split(b"\n")]
    out = []
    for ln in new.split(b"\n"):
        if otok in ln:
            body = ln.rstrip(b"\r")
            eol = ln[len(body):]
            parts = body.split(otok)
            rx = re.escape(parts[0]) + b"(?P<h>\\S+?)"
            for p in parts[1:-1]:
                rx += re.escape(p) + b"(?P=h)"
            rx += re.escape(parts[-1]) + b"$"
            cr = re.compile(b"^" + rx)
            for ol in oldlines:
                m = cr.match(ol)
                if m:
                    h = m.group("h")
                    if h != otok:
                        ln = body.replace(otok, h) + eol
                    break
        out.append(ln)
    return b"\n".join(out)

def fill(to, data, old):
    new = data.replace(tok, pyb)
    if to.startswith(".claude/agents/"):
        out = []
        front = 0
        for ln in new.split(b"\n"):
            if ln.strip(b"\r") == b"---":
                front += 1
            if front == 1 and ln.lstrip().startswith(b"command:") and b"$HOME" in ln:
                ln = ln.replace(b"$HOME", hb)
            out.append(ln)
        new = b"\n".join(out)
    if otok in new:
        if ob:
            new = new.replace(otok, ob)
        elif old is not None:
            new = keep(new, old)
    return new

plan = []
skipped = unchanged = 0
for line in sys.stdin.read().split("\n"):
    line = line.strip("\r")
    if not line:
        continue
    frm, to = line.split("\t")
    if to.startswith(".claude/hooks/") and not uph:
        skipped += 1
        continue
    data = open(src + "/" + frm, "rb").read()
    dest = home + "/" + to
    old = open(dest, "rb").read() if os.path.isfile(dest) else None
    new = fill(to, data, old)
    if old is None:
        plan.append(("added", frm, to, None, new))
    elif old == new:
        unchanged += 1
    else:
        plan.append(("replaced", frm, to, old, new))
# every before-copy first, each read back, then the writes
for kind, frm, to, old, new in plan:
    if kind == "replaced":
        b = bk + "/" + to
        os.makedirs(os.path.dirname(b), exist_ok=True)
        with open(b, "wb") as fh:
            fh.write(old)
        if open(b, "rb").read() != old:
            print("install.sh: the backup copy of " + to + " does not match; nothing was replaced", file=sys.stderr)
            sys.exit(5)
nrep = nadd = 0
for kind, frm, to, old, new in plan:
    dest = home + "/" + to
    if kind == "added":
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(new)
        shutil.copymode(src + "/" + frm, dest)
        nadd += 1
    else:
        with open(dest, "wb") as fh:
            fh.write(new)
        nrep += 1
    print("%s %s sha256 before %s after %s" % (kind, to, sha(old) if old is not None else "-", sha(new)))
print("upgrade: replaced %d, added %d, unchanged %d, hooks skipped %d" % (nrep, nadd, unchanged, skipped))
'
  cut -f1,2 "$LIST" | "$PY" -c "$UPG" "$SRCLIT" "$HOMELIT" "$PY" "$BKLIT" "${LOOP_UPGRADE_HOOKS:-}" "${LOOP_OWNER_HANDLE:-}" || { echo "install.sh: the upgrade failed" >&2; exit 5; }
  exit 0
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
HOMELIT="$(spell "$HOME")"
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
