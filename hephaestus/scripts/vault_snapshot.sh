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

# Weekly vault snapshot. Gate first, then archive, then upload.
#
# A snapshot is the backup. Sync is only a mirror: a mirror propagates a bad
# delete, and per-file cloud version history means recovering 40 deleted notes is
# 40 manual restores. This script produces immutable timestamped archives that
# nothing later overwrites.
#
# ORDER IS THE POINT, and it is a gate, not a rule:
#   1. lint.py must exit 0 for the vault
#   2. only then is an archive written
#   3. only then is it uploaded
# A vault that fails its gate is NOT snapshotted and NOT uploaded, because the
# thing the gate catches is a PII leak, and a leak that reaches cloud version
# history is effectively permanent. Refusing to back up a dirty vault is the
# lesser harm, and the refusal is loud.
#
# Uploads are UPLOAD-ONLY by construction: this script only ever calls
# `rclone copy` from local to remote, never the reverse, and never `sync`
# (which deletes on the destination to match the source). A local delete can
# therefore never remove a cloud copy.
#
# Snapshots may contain candidate-adjacent work material, so the work vault's
# archive is encrypted through an rclone crypt remote. The passphrase lives in
# rclone's own config and is never printed, logged or passed on a command line
# by this script.

set -uo pipefail

REGISTRY="${HOME}/.hermes/vaults.json"
SNAP_ROOT="${HOME}/.hermes/vault-snapshots"
# Handoff folder for manual upload. Deliberately NOT under ~/.hermes: it is for
# your hands, so it sits somewhere a file manager opens without hunting through
# a dotfolder.
UPLOAD_DIR="${HOME}/Vault-Uploads"
KEEP_LOCAL=8                    # ~2 months of weeklies on disk
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DRY_RUN=0
ONLY_VAULT=""

usage() {
  cat <<'USAGE'
usage: vault_snapshot.sh [--dry-run] [--vault NAME]

  --dry-run      Run every gate and report what WOULD happen. Writes no
                 archive and uploads nothing. Use this to verify a change.
  --vault NAME   Snapshot one vault only (work | study | personal).

Exit codes: 0 all attempted vaults succeeded; 1 at least one failed its gate
or its archive step. Nonzero means at least one vault is NOT backed up.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --vault)   ONLY_VAULT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ ! -f "$REGISTRY" ]; then
  echo "SNAPSHOT FAIL: no vault registry at $REGISTRY"
  exit 1
fi

# rclone is optional: archives are still written locally without it, and the
# upload is reported as skipped. A missing uploader must not cost you the
# local backup.
RCLONE=""
command -v rclone >/dev/null 2>&1 && RCLONE=$(command -v rclone)

mkdir -p "$SNAP_ROOT"
FAILED=0
ATTEMPTED=0

# name<TAB>path<TAB>remote  for each vault, from the registry
VAULTS=$("$PY" - "$REGISTRY" <<'PY'
import json, sys
reg = json.load(open(sys.argv[1]))
for v in reg.get("vaults", []):
    print("\t".join([v.get("name",""), v.get("path",""), v.get("snapshot_remote","")]))
PY
)

echo "vault snapshot run $STAMP  (dry-run=$DRY_RUN)"
echo

while IFS=$'\t' read -r NAME VPATH REMOTE; do
  [ -z "${NAME:-}" ] && continue
  if [ -n "$ONLY_VAULT" ] && [ "$NAME" != "$ONLY_VAULT" ]; then continue; fi
  ATTEMPTED=$((ATTEMPTED + 1))
  echo "=== $NAME  ($VPATH)"

  if [ ! -d "$VPATH" ]; then
    echo "  FAIL vault directory does not exist. Not snapshotted."
    FAILED=$((FAILED + 1)); echo; continue
  fi

  LINT="$VPATH/scripts/lint.py"
  if [ ! -f "$LINT" ]; then
    echo "  FAIL no gate at scripts/lint.py. An ungated vault is not snapshotted,"
    echo "       because nothing has checked it for a leak. Not snapshotted."
    FAILED=$((FAILED + 1)); echo; continue
  fi

  # The gate. Exit code read directly, never through a pipe: a pipe reports the
  # LAST command's status, so `lint.py | tail` always looks like success and the
  # check could never fail.
  GATE_OUT="$SNAP_ROOT/.gate-$NAME-$STAMP.txt"
  OBSIDIAN_VAULT_PATH="$VPATH" "$PY" "$LINT" > "$GATE_OUT" 2>&1
  GATE_RC=$?
  if [ "$GATE_RC" -ne 0 ]; then
    echo "  FAIL gate exited $GATE_RC. NOT snapshotted, NOT uploaded."
    echo "       A failing gate usually means a PII hit, and a leak that reaches"
    echo "       cloud version history is permanent. Fix the vault, then re-run."
    grep -E "^FAIL" "$GATE_OUT" | sed 's/^/       /'
    rm -f "$GATE_OUT"
    FAILED=$((FAILED + 1)); echo; continue
  fi
  echo "  gate: exit 0  ($(grep -m1 '^pii-scanned' "$GATE_OUT" || echo 'no scan line'))"
  rm -f "$GATE_OUT"

  ARCHIVE="$SNAP_ROOT/${NAME}-${STAMP}.tar.gz"
  if [ "$DRY_RUN" = "1" ]; then
    echo "  DRY RUN: would write $ARCHIVE"
  else
    # --exclude .obsidian: per-machine UI state, not knowledge, and it churns.
    tar -czf "$ARCHIVE" -C "$(dirname "$VPATH")" \
      --exclude='.obsidian/workspace.json' \
      "$(basename "$VPATH")" 2>/dev/null
    TAR_RC=$?
    if [ "$TAR_RC" -ne 0 ] || [ ! -s "$ARCHIVE" ]; then
      echo "  FAIL archive step (tar rc=$TAR_RC). Not uploaded."
      rm -f "$ARCHIVE"
      FAILED=$((FAILED + 1)); echo; continue
    fi
    # Verify the archive is readable before trusting it. An archive that cannot
    # be listed is not a backup, and finding that out at restore time is the
    # worst possible moment.
    if ! tar -tzf "$ARCHIVE" >/dev/null 2>&1; then
      echo "  FAIL archive is unreadable. Not uploaded."
      rm -f "$ARCHIVE"
      FAILED=$((FAILED + 1)); echo; continue
    fi
    FILES=$(tar -tzf "$ARCHIVE" | grep -c '')
    echo "  archive: $(basename "$ARCHIVE") ($(du -h "$ARCHIVE" | cut -f1), $FILES entries, listing verified)"

    # --- zip export for manual upload -------------------------------------
    # A STABLE filename, no timestamp: you replace the same file on each drive
    # every week, so the name must not change or you accumulate duplicates
    # instead of replacing one file.
    #
    # History is not lost by the stable name. The timestamped .tar.gz archives
    # above are the real local history (8 kept), and both OneDrive and Google
    # Drive keep their own version history when a file is replaced. The zip is
    # a transport format, not the archive of record.
    mkdir -p "$UPLOAD_DIR"
    ZIP="$UPLOAD_DIR/${NAME}-vault.zip"
    ZTMP="${ZIP}.tmp"
    rm -f "$ZTMP"
    # -r recurse, -q quiet, -X drop extra OS metadata that bloats the file.
    # Run from the vault's PARENT so the zip contains one top-level folder
    # rather than exploding loose files into wherever it is extracted.
    ( cd "$(dirname "$VPATH")" && zip -r -q -X "$ZTMP" "$(basename "$VPATH")" \
        -x '*/.obsidian/workspace.json' ) 2>/dev/null
    ZIP_RC=$?
    if [ "$ZIP_RC" -ne 0 ] || [ ! -s "$ZTMP" ]; then
      echo "  FAIL zip export (rc=$ZIP_RC). Previous zip left in place, not replaced."
      rm -f "$ZTMP"
      FAILED=$((FAILED + 1))
    elif ! unzip -t "$ZTMP" >/dev/null 2>&1; then
      # Verify before replacing. Overwriting a known-good zip with a corrupt one
      # would hand you a broken file to upload, which is worse than an old file.
      echo "  FAIL zip failed its integrity test. Previous zip left in place."
      rm -f "$ZTMP"
      FAILED=$((FAILED + 1))
    else
      mv "$ZTMP" "$ZIP"
      ZN=$(unzip -l "$ZIP" | tail -1 | awk '{print $2}')
      echo "  zip:     $(basename "$ZIP") ($(du -h "$ZIP" | cut -f1), $ZN entries, integrity verified)"
    fi
  fi

  # --- upload ---
  # Manual by design: you replace the zip on each drive yourself. The rclone
  # path below stays because it costs nothing dormant and becomes the automatic
  # option the day a remote is configured, but it is silent unless a
  # snapshot_remote is actually set. No remote set is the NORMAL state here, so
  # it must not print a warning that trains you to ignore warnings.
  if [ -z "$REMOTE" ]; then
    :
  elif [ -z "$RCLONE" ]; then
    echo "  upload: SKIPPED, rclone is not installed. Local archive is kept."
  elif [ "$DRY_RUN" = "1" ]; then
    echo "  DRY RUN: would upload to $REMOTE (rclone copy, never sync)"
    "$RCLONE" lsd "$REMOTE" >/dev/null 2>&1 \
      && echo "  DRY RUN: remote reachable" \
      || echo "  DRY RUN: WARNING remote '$REMOTE' not reachable or not configured"
  else
    # `copy`, deliberately. `sync` would delete remote files to match local,
    # which is exactly the mirror-propagates-a-delete failure this design
    # avoids.
    if "$RCLONE" copy "$ARCHIVE" "$REMOTE" --no-traverse 2>/tmp/rclone-$NAME.err; then
      # Confirm by listing the remote, not by trusting the exit code.
      if "$RCLONE" lsf "$REMOTE" 2>/dev/null | grep -qx "$(basename "$ARCHIVE")"; then
        echo "  upload: $REMOTE  CONFIRMED present on remote"
      else
        echo "  upload: rclone reported success but the file is NOT listed on the remote."
        echo "          Treating this as a failure; the local archive is kept."
        FAILED=$((FAILED + 1))
      fi
    else
      echo "  upload: FAILED. Local archive is kept."
      sed 's/^/          /' /tmp/rclone-$NAME.err | head -3
      FAILED=$((FAILED + 1))
    fi
    rm -f /tmp/rclone-$NAME.err
  fi

  # --- local retention ---
  if [ "$DRY_RUN" = "0" ]; then
    COUNT=$(ls -1t "$SNAP_ROOT/${NAME}-"*.tar.gz 2>/dev/null | grep -c '')
    if [ "$COUNT" -gt "$KEEP_LOCAL" ]; then
      ls -1t "$SNAP_ROOT/${NAME}-"*.tar.gz | tail -n +$((KEEP_LOCAL + 1)) | while read -r old; do
        rm -f "$old"; echo "  retention: removed $(basename "$old")"
      done
    fi
    echo "  local snapshots kept: $(ls -1 "$SNAP_ROOT/${NAME}-"*.tar.gz 2>/dev/null | grep -c '')"
  fi
  echo
done <<< "$VAULTS"

echo "-----"
if [ "$ATTEMPTED" = "0" ]; then
  echo "SNAPSHOT FAIL: no vaults attempted. Check --vault spelling against $REGISTRY."
  exit 1
fi

# --- manual upload handoff ---------------------------------------------------
# The point of the zips is that YOU upload them, so the run has to end by telling
# you exactly what to move and where. A report that just says "OK" leaves you to
# remember which zip belongs to which drive, and that is how the work vault ends
# up in a personal account.
if [ "$DRY_RUN" = "0" ] && [ -d "$UPLOAD_DIR" ]; then
  echo
  echo "READY TO UPLOAD  ->  $UPLOAD_DIR"
  "$PY" - "$REGISTRY" "$UPLOAD_DIR" <<'PY'
import json, os, sys, time
reg_p, up = sys.argv[1], sys.argv[2]
reg = json.load(open(reg_p))
now = time.time()
for v in reg.get("vaults", []):
    name = v.get("name", "")
    z = os.path.join(up, f"{name}-vault.zip")
    dest = v.get("sync", "destination not set")
    if not os.path.isfile(z):
        print(f"  {name:<10} NO ZIP  (vault failed its gate, or was not run)")
        continue
    age_min = (now - os.path.getmtime(z)) / 60
    size_mb = os.path.getsize(z) / 1048576
    fresh = "just written" if age_min < 5 else f"{age_min/1440:.1f}d old - STALE, not refreshed this run"
    print(f"  {name:<10} {size_mb:6.1f} MB  {fresh}")
    print(f"             -> {dest}")
PY
  echo
  echo "  Replace the existing file on each drive, keeping the same name."
  echo "  Both OneDrive and Google Drive keep version history on replace, so the"
  echo "  previous week stays recoverable from the drive itself."
fi

if [ "$FAILED" -gt 0 ]; then
  echo
  echo "SNAPSHOT INCOMPLETE: $FAILED of $ATTEMPTED vault(s) were NOT backed up."
  exit 1
fi
echo
echo "SNAPSHOT OK: $ATTEMPTED of $ATTEMPTED vault(s) backed up."
exit 0
