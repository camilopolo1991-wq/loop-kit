#!/usr/bin/env bash
# Serial goal queue for an autonomous agent loop.
#
# Runs one leader at a time, in the order given, on the agent host. Install it
# on that host and start it detached; do not supervise dispatches by hand from
# the orchestrator.
#
# Usage:  nohup ./queue_goals.sh GOAL-A GOAL-B GOAL-C >> queue.log 2>&1 &
#
# Put the goal that FIXES the concurrency mechanism first, so everything behind
# it may run wide once it passes.
#
# Adapt the paths, the binary, the role name and the plan-file status tokens to
# the target system. The three guards below are the transferable part.

set -uo pipefail

QUEUE="${*:?usage: queue_goals.sh GOAL-ID [GOAL-ID ...]}"

GOALS_DIR=/path/to/goals          # <goal>/GOAL, <goal>/plan.md live here
DISPATCH_DIR=/path/to/dispatch    # per-goal .out logs, queue.log, queue.state
BINARY=/usr/bin/agent-binary
ROLE=leader-role-name
WORKDIR=/path/to/agent/home       # becomes cwd AND HOME for the session
WALL_CAP=14400                    # hard stop per goal, seconds

LOG="$DISPATCH_DIR/queue.log"
STATE="$DISPATCH_DIR/queue.state"

say() { echo "$(date -u +%H:%M:%SZ) $*" | tee -a "$LOG"; }

# GUARD 1 of 3: wait on the REAL binary, not the wrapper shell and not grep
# itself. `grep -c <name>` over ps output matches its own command line and the
# nohup wrapper, so a count of 1 routinely means zero agents are running.
wait_for_clear() {
  while pgrep -f "timeout $WALL_CAP $BINARY --agent $ROLE" >/dev/null 2>&1; do
    sleep 30
  done
}

# GUARD 2 of 3: a goal is finished only when no plan task is still open.
# Process exit is NOT completion -- a quota death, timeout or crash exits
# exactly like success.
goal_incomplete() {
  local p="$GOALS_DIR/$1/plan.md"
  [ -f "$p" ] || return 1
  grep -qE '\| *(TODO|RUNNING|RETRY)' "$p"
}

say "QUEUE START: $QUEUE"
wait_for_clear
say "WIP clear"

for G in $QUEUE; do
  if [ ! -f "$GOALS_DIR/$G/GOAL" ]; then
    say "SKIP $G: no goal file"
    continue
  fi

  say "DISPATCH $G"
  echo "running=$G" > "$STATE"
  cd "$WORKDIR" || exit 1

  # Redirect stays inside this shell; cwd and HOME are both load-bearing for
  # the agent runtime to find its role config.
  HOME="$WORKDIR" timeout "$WALL_CAP" "$BINARY" --agent "$ROLE" \
    -p "Run goal $G" > "$DISPATCH_DIR/$G.out" 2>&1
  RC=$?

  SZ=$(stat -c%s "$DISPATCH_DIR/$G.out" 2>/dev/null || echo 0)
  say "EXIT $G rc=$RC out=${SZ}b"

  # GUARD 3 of 3: quota death. Stop rather than feeding later goals to a
  # closed window. Match whatever notice the runtime prints.
  if grep -qi "session limit\|quota\|rate limit" "$DISPATCH_DIR/$G.out" 2>/dev/null; then
    say "HALT: quota limit on $G. Remaining goals NOT dispatched."
    echo "halted_at=$G reason=session_limit" > "$STATE"
    exit 0
  fi

  if goal_incomplete "$G"; then
    OPEN=$(grep -cE '\| *(TODO|RUNNING|RETRY)' "$GOALS_DIR/$G/plan.md")
    say "HALT: $G exited with $OPEN task(s) still open. Not advancing."
    echo "halted_at=$G reason=incomplete_plan open=$OPEN" > "$STATE"
    exit 0
  fi

  say "COMPLETE $G (no open plan tasks)"
  sleep 20
done

say "QUEUE DONE"
echo "done" > "$STATE"
