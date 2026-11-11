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

# graph_build.sh: build or update the graphify knowledge graph over the Obsidian vault.
# The vault stays the writing surface (notes, conventions, PII gate). Graphify is the retrieval
# layer: one graph.json, named communities, a wiki with an index.md the agent can crawl, and
# graphify query / path / explain for recall. Added 2026-10-20.
#
#   graph_build.sh            # full build if no graph yet, else incremental (cached extract)
#   graph_build.sh --full     # force a full rebuild
#   graph_build.sh --status   # age of the graph vs the newest vault note, no build
#
# Env: OBSIDIAN_VAULT_PATH (required), HERMES_HOME (default ~/.hermes),
#      GRAPH_OUT (default $HERMES_HOME/graph), GRAPHIFY_BACKEND (default claude-cli; use
#      ollama for fully local; see README), GRAPH_WIKI=0 to skip the wiki, GRAPH_OBSIDIAN=1 to
#      also export a node-per-note Obsidian vault under $GRAPH_OUT/obsidian.
#
# HARD PRECONDITION: scripts/lint.py in the vault exits 0. The semantic pass sends note text to
# the configured backend. The PII gate runs first, every time, and a failure stops the build.
# Exit: 0 built or current, 2 lint failed, 3 graphify missing, 4 vault missing, 5 build failed.
set -uo pipefail
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
VAULT="${OBSIDIAN_VAULT_PATH:-}"
GRAPH_OUT="${GRAPH_OUT:-$HERMES_HOME/graph}"
BACKEND="${GRAPHIFY_BACKEND:-claude-cli}"
LOG="$HERMES_HOME/logs/graph_build.log"
mkdir -p "$HERMES_HOME/logs"
say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }

[ -n "$VAULT" ] && [ -d "$VAULT" ] || { say "FAIL vault missing: OBSIDIAN_VAULT_PATH='$VAULT'"; exit 4; }
command -v graphify >/dev/null || { say "FAIL graphify not on PATH (uv tool install graphifyy)"; exit 3; }

newest_note=$(find "$VAULT" -name '*.md' -not -path '*/_retired/*' -not -path '*/.obsidian/*' -printf '%T@\n' 2>/dev/null | sort -n | tail -1 | cut -d. -f1)
graph_ts=$( [ -f "$GRAPH_OUT/graph.json" ] && stat -c %Y "$GRAPH_OUT/graph.json" || echo 0 )
if [ "${1:-}" = "--status" ]; then
  if [ "$graph_ts" = 0 ]; then echo "graph: none at $GRAPH_OUT"; exit 1; fi
  age=$(( ($(date +%s) - graph_ts) / 3600 ))
  [ "${newest_note:-0}" -gt "$graph_ts" ] && echo "graph: STALE (${age}h old, a note is newer). Run graph_build.sh" && exit 1
  echo "graph: current (${age}h old), nodes=$("$PY" -c "import json;g=json.load(open('$GRAPH_OUT/graph.json'));n=g.get('nodes');print(len(n) if isinstance(n,list) else len(n or {}))" 2>/dev/null)"; exit 0
fi

# 1. PII gate first. Never read the exit code through a pipe.
( cd "$VAULT" && OBSIDIAN_VAULT_PATH="$VAULT" "$PY" -I scripts/lint.py > "$HERMES_HOME/logs/graph_build.lint.out" 2>&1 )
rc=$?
if [ $rc -ne 0 ]; then say "FAIL vault lint rc=$rc; nothing sent to the backend. See logs/graph_build.lint.out"; exit 2; fi
say "ok lint clean"

# 2. ignore file inside the vault: queue, retired, scripts, Obsidian config never enter the graph
IGN="$VAULT/.graphifyignore"
if [ ! -f "$IGN" ]; then printf '_retired/\n00 Inbox/\nscripts/\n.obsidian/\n.trash/\n' > "$IGN"; say "ok wrote $IGN"; fi

# 3. build or update
mkdir -p "$GRAPH_OUT"
export GRAPHIFY_OUT="$GRAPH_OUT" GRAPHIFY_BACKEND="$BACKEND" GRAPHIFY_QUERY_LOG="$HERMES_HOME/logs/graphify-queries.log"
if [ "$graph_ts" = 0 ] || [ "${1:-}" = "--full" ]; then
  say "build full backend=$BACKEND out=$GRAPH_OUT"
  graphify extract "$VAULT" --backend "$BACKEND" --no-viz >> "$LOG" 2>&1 || { say "FAIL extract rc=$?"; exit 5; }
else
  if [ "${newest_note:-0}" -le "$graph_ts" ]; then say "ok graph current, nothing to do"; exit 0; fi
  # `graphify update` re-extracts CODE only. Notes go through `extract` again, whose SHA256 cache
  # under $GRAPH_OUT/cache skips every unchanged file, so this is the incremental path for docs.
  say "update incremental (extract with cache) backend=$BACKEND"
  graphify extract "$VAULT" --backend "$BACKEND" --no-viz >> "$LOG" 2>&1 || { say "FAIL extract rc=$?"; exit 5; }
fi
graphify cluster-only "$VAULT" >> "$LOG" 2>&1 || say "WARN cluster-only rc=$? (graph still usable)"
[ "${GRAPH_WIKI:-1}" = 1 ] && { graphify export wiki >> "$LOG" 2>&1 && say "ok wiki at $GRAPH_OUT/wiki/index.md" || say "WARN wiki export failed"; }
[ "${GRAPH_OBSIDIAN:-0}" = 1 ] && { graphify export obsidian --dir "$GRAPH_OUT/obsidian" >> "$LOG" 2>&1 && say "ok obsidian export at $GRAPH_OUT/obsidian" || say "WARN obsidian export failed"; }
n=$("$PY" -c "import json;g=json.load(open('$GRAPH_OUT/graph.json'));n=g.get('nodes');print(len(n) if isinstance(n,list) else len(n or {}))" 2>/dev/null)
say "ok graph.json nodes=$n at $GRAPH_OUT"
exit 0
