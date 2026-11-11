#!/usr/bin/env bash

# ---------------------------------------------------------------- interpreter
# Named by FULL PATH, never as `"$PY"` on PATH. A presence check passes on a stub that
# cannot run: measured, the Microsoft Store alias resolves via `command -v` and then exits
# 49 on every invocation, so all 16 gates below failed for a reason unrelated to any gate.
# LOOP_PY overrides; otherwise the first candidate that actually EXECUTES wins.
pick_py() {
  local c p
  for c in "$LOOP_PY" "$PY" python; do
    [ -n "$c" ] || continue
    p=$(command -v "$c" 2>/dev/null) || continue
    if "$p" -c 'import sys' >/dev/null 2>&1; then printf '%s' "$p"; return 0; fi
  done
  return 1
}
LOOP_PY="${LOOP_PY:-}"
PY=$(pick_py) || { echo "FAIL   no working "$PY" found. Set LOOP_PY to the interpreter's full path."; exit 4; }
export LOOP_PY="$PY"

# Vault doctor. Proves the multi-vault system is actually healthy, and repairs
# the one thing that drifts on its own.
#
# Three independent checks, each of which can fail on its own:
#
#   1. REGISTRY CONSISTENCY. ~/.hermes/vaults.json (what Hermes resolves names
#      from) and ~/.config/obsidian/obsidian.json (what the Obsidian app shows
#      in its switcher) are two separate files that must agree. The Obsidian one
#      is owned by a GUI app that rewrites it from memory on exit, so an edit
#      made while the app is running is silently reverted. This script detects
#      the drift and repairs it, refusing to write while the app is running
#      rather than making an edit that will be thrown away.
#
#   2. GATE HEALTH. Every registered vault must have a gate and pass it.
#
#   3. RESTORE DRILL. The newest snapshot of each vault is extracted to a temp
#      directory and the RESTORED COPY is run through its own gate. A backup
#      nobody has restored is a hope, not a backup, and restore time is the
#      worst possible moment to find out an archive is bad.
#
# Exit 0 only when every check passed. Nonzero means something in the backup or
# vault chain is not what it claims to be.

set -uo pipefail

REGISTRY="${HOME}/.hermes/vaults.json"
OBSIDIAN_CFG="${HOME}/.config/obsidian/obsidian.json"
SNAP_ROOT="${HOME}/.hermes/vault-snapshots"
FIX=0
PROBLEMS=0
CHECKS=0

usage() {
  cat <<'USAGE'
usage: vault_doctor.sh [--fix]

  --fix   Repair registry drift by adding missing vaults to Obsidian's
          vault list. Refuses while Obsidian is running, because the app
          rewrites that file from memory on exit and would revert the edit.

Without --fix the script only reports. Exit 0 = everything verified.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --fix) FIX=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

problem() { echo "  PROBLEM: $*"; PROBLEMS=$((PROBLEMS + 1)); }
ok()      { echo "  ok: $*"; }

# Detect Obsidian by PROCESS NAME, never by full command line.
#
# `pgrep -f obsidian` matches any process whose ARGUMENTS contain the string,
# which includes this very script, any shell running it, and any grep for it.
# That false positive already caused a wrong report ("Obsidian is running" when
# it was not), and acting on it would mean refusing a repair that was perfectly
# safe. Match the executable name instead.
obsidian_running() {
  pgrep -x obsidian >/dev/null 2>&1 && return 0
  # AppImage/Electron builds may expose a truncated comm; check argv[0] only.
  ps -eo comm= | grep -qx "obsidian" && return 0
  return 1
}

echo "vault doctor  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

# ---------------------------------------------------------------------------
echo "=== 1. registry consistency ==="
CHECKS=$((CHECKS + 1))

if [ ! -f "$REGISTRY" ]; then
  problem "no Hermes vault registry at $REGISTRY"
else
  if obsidian_running; then
    OBS_STATE="RUNNING"
  else
    OBS_STATE="not running"
  fi
  echo "  obsidian: $OBS_STATE"

  DRIFT=$("$PY" - "$REGISTRY" "$OBSIDIAN_CFG" <<'PY'
import json, os, sys
reg_p, obs_p = sys.argv[1], sys.argv[2]
reg = json.load(open(reg_p))
want = {v["path"]: v["name"] for v in reg.get("vaults", []) if v.get("path")}
have = set()
if os.path.isfile(obs_p):
    try:
        obs = json.load(open(obs_p))
        have = {v.get("path") for v in (obs.get("vaults") or {}).values()}
    except ValueError:
        print("PARSE_ERROR")
        raise SystemExit
for path, name in sorted(want.items()):
    if not os.path.isdir(path):
        print(f"MISSING_DIR\t{name}\t{path}")
    elif path not in have:
        print(f"NOT_IN_OBSIDIAN\t{name}\t{path}")
# A vault Obsidian knows about that Hermes does not is worth saying out loud:
# it means I would fail to resolve a vault the user can see in their app.
for path in sorted(p for p in have if p and p not in want):
    print(f"NOT_IN_HERMES\t?\t{path}")
PY
)

  if [ "$DRIFT" = "PARSE_ERROR" ]; then
    problem "Obsidian's vault list is not valid JSON: $OBSIDIAN_CFG"
  elif [ -z "$DRIFT" ]; then
    ok "both registries agree on every vault"
  else
    while IFS=$'\t' read -r KIND NAME VPATH; do
      [ -z "${KIND:-}" ] && continue
      case "$KIND" in
        MISSING_DIR)
          problem "registry lists '$NAME' but the directory does not exist: $VPATH" ;;
        NOT_IN_OBSIDIAN)
          if [ "$FIX" = "1" ] && [ "$OBS_STATE" = "not running" ]; then
            cp "$OBSIDIAN_CFG" "${OBSIDIAN_CFG}.bak-$(date +%s)" 2>/dev/null
            # The parent dir does not exist on a headless box where Obsidian has
            # never run. Without it json.dump() raises FileNotFoundError and the
            # old code still printed FIXED, so three vaults were reported fixed
            # while nothing was written. Create it, and branch on python's rc.
            mkdir -p "$(dirname "$OBSIDIAN_CFG")"
            if "$PY" - "$OBSIDIAN_CFG" "$VPATH" <<'PY'
import json, sys, time, hashlib, os
cfg, path = sys.argv[1], sys.argv[2]
d = json.load(open(cfg)) if os.path.isfile(cfg) else {}
vaults = d.setdefault("vaults", {})
vid = hashlib.md5(path.encode()).hexdigest()[:16]
vaults[vid] = {"path": path, "ts": int(time.time() * 1000), "open": False}
json.dump(d, open(cfg, "w"), indent=2)
PY
            then
              # Verify by reading the file back: a zero exit is not proof the
              # path is in the list.
              if "$PY" -c "
import json,sys
d=json.load(open('$OBSIDIAN_CFG'))
sys.exit(0 if any(v.get('path')=='''$VPATH''' for v in d.get('vaults',{}).values()) else 1)
" 2>/dev/null; then
                echo "  FIXED: added '$NAME' to Obsidian's vault list ($VPATH)"
              else
                problem "tried to add '$NAME' but it is not in the file afterwards: $OBSIDIAN_CFG"
              fi
            else
              problem "failed to write Obsidian's vault list for '$NAME': $OBSIDIAN_CFG"
            fi
          elif [ "$FIX" = "1" ]; then
            problem "'$NAME' is missing from Obsidian's list, and Obsidian is RUNNING."
            echo "           Not writing: the app rewrites that file from memory on exit,"
            echo "           so the edit would be silently reverted. Quit Obsidian, re-run --fix."
          else
            problem "'$NAME' is not in Obsidian's vault list. Re-run with --fix."
          fi ;;
        NOT_IN_HERMES)
          problem "Obsidian knows a vault Hermes does not: $VPATH"
          echo "           Add it to $REGISTRY or I cannot resolve it by name." ;;
      esac
    done <<< "$DRIFT"
  fi
fi
echo

# ---------------------------------------------------------------------------
echo "=== 2. gate health ==="
while IFS=$'\t' read -r NAME VPATH; do
  [ -z "${NAME:-}" ] && continue
  CHECKS=$((CHECKS + 1))
  if [ ! -d "$VPATH" ]; then
    problem "$NAME: directory missing"; continue
  fi
  if [ ! -f "$VPATH/scripts/lint.py" ]; then
    problem "$NAME: no gate at scripts/lint.py"; continue
  fi
  OUT=$(OBSIDIAN_VAULT_PATH="$VPATH" "$PY" "$VPATH/scripts/lint.py" 2>&1)
  RC=$?
  if [ "$RC" -ne 0 ]; then
    problem "$NAME: gate exits $RC"
    echo "$OUT" | grep -E "^FAIL" | sed 's/^/           /'
  else
    ok "$NAME: gate clean ($(echo "$OUT" | grep -m1 '^pii-scanned'))"
  fi
done <<< "$("$PY" -c "
import json,sys
reg=json.load(open('$REGISTRY'))
for v in reg.get('vaults',[]): print(v.get('name','')+'\t'+v.get('path',''))
" 2>/dev/null)"
echo

# ---------------------------------------------------------------------------
echo "=== 3. restore drill ==="
echo "  (extract the newest archive, then run the RESTORED copy through its own gate)"
while IFS=$'\t' read -r NAME VPATH; do
  [ -z "${NAME:-}" ] && continue
  CHECKS=$((CHECKS + 1))
  ARCHIVE=$(ls -1t "$SNAP_ROOT/${NAME}-"*.tar.gz 2>/dev/null | head -1)
  if [ -z "$ARCHIVE" ]; then
    problem "$NAME: no snapshot archive exists. Nothing to restore from."
    continue
  fi

  AGE_DAYS=$(( ( $(date +%s) - $(stat -c %Y "$ARCHIVE") ) / 86400 ))
  WORK=$(mktemp -d "${TMPDIR:-/tmp}/vaultdrill.XXXXXX")

  if ! tar -xzf "$ARCHIVE" -C "$WORK" 2>/dev/null; then
    problem "$NAME: archive will not extract: $(basename "$ARCHIVE")"
    rm -rf "$WORK"; continue
  fi

  RV=$(find "$WORK" -maxdepth 1 -mindepth 1 -type d | head -1)
  if [ -z "$RV" ] || [ ! -f "$RV/scripts/lint.py" ]; then
    problem "$NAME: restored copy has no gate; archive is not a usable vault"
    rm -rf "$WORK"; continue
  fi

  # The restored vault must pass its OWN gate. This is the check that catches a
  # silently corrupted or partial archive.
  OBSIDIAN_VAULT_PATH="$RV" "$PY" "$RV/scripts/lint.py" > "$WORK/gate.txt" 2>&1
  GRC=$?

  LIVE_N=$(find "$VPATH" -name '*.md' -not -path '*/.obsidian/*' 2>/dev/null | grep -c '')
  REST_N=$(find "$RV"   -name '*.md' -not -path '*/.obsidian/*' 2>/dev/null | grep -c '')

  if [ "$GRC" -ne 0 ]; then
    problem "$NAME: RESTORED copy fails its own gate (exit $GRC). The archive is not a good backup."
    grep -E "^FAIL" "$WORK/gate.txt" | head -3 | sed 's/^/           /'
  elif [ "$REST_N" -eq 0 ] && [ "$LIVE_N" -gt 0 ]; then
    # Zero notes is only a fault when the LIVE vault has notes. A genuinely
    # empty vault restores to an empty vault, which is correct, and failing it
    # would mean a brand new vault could never pass this drill.
    problem "$NAME: restored copy has zero notes but the live vault has $LIVE_N. The archive predates the content or is truncated."
  else
    # A note-count difference is expected when the vault changed after the
    # snapshot, so it is reported, not failed. Reporting it is the point: a
    # large gap means the backup is stale.
    ok "$NAME: restored $REST_N note(s) from a ${AGE_DAYS}d-old archive, restored gate exit 0 (live has $LIVE_N)"
    if [ "$REST_N" -ne "$LIVE_N" ]; then
      echo "         note: live vault differs by $((LIVE_N - REST_N)) note(s) since that snapshot"
    fi
    if [ "$AGE_DAYS" -gt 9 ]; then
      problem "$NAME: newest archive is ${AGE_DAYS} days old; the weekly snapshot may not be running"
    fi
  fi
  rm -rf "$WORK"
done <<< "$("$PY" -c "
import json,sys
reg=json.load(open('$REGISTRY'))
for v in reg.get('vaults',[]): print(v.get('name','')+'\t'+v.get('path',''))
" 2>/dev/null)"

echo
echo "-----"
if [ "$PROBLEMS" -gt 0 ]; then
  echo "VAULT DOCTOR: $PROBLEMS problem(s) across $CHECKS check(s)."
  exit 1
fi
echo "VAULT DOCTOR OK: $CHECKS check(s) passed."
exit 0
