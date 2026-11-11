# Serialised dispatch queues

Where the dispatcher allows ONE leader at a time — because concurrent peers quarantine
each other's tripwire windows — an authorised goal frequently cannot start when you decide
it should. This file is the pattern for handing that wait to a script instead of to a
future turn, and the traps each guard exists for.

## The rule that creates all of this

**Never report an authorised goal as "queued" or "ready" in a reply and leave it there.**
Capability is not completion. Either it is running, or a watcher is running that will
start it, or you say plainly that it is blocked and on what. A queue that exists only as
a sentence in chat is a dropped goal.

## Shape of the watcher

Run it as a tracked background process (`terminal(background=true, notify=true)`), never
via a shell-level `nohup`/`disown` wrapper — those are refused, and the process would be
untracked anyway. Log every state transition to a file with a UTC stamp, so the next turn
reads the log instead of re-deriving the state.

The loop: poll every 60s, dispatch when the slot is free, cap the total wait, and exit
with a DISTINCT code per outcome (dispatched / gave up / held on a precondition). One
shared non-zero exit forces the next session to re-measure which of them happened.

## Count leader liveness by PROCESS NAME, never by goal text

A wait loop keyed on the goal id matches its OWN command line and waits forever. That
trap has hung multiple queues, and each one was reported as "still running".

    leaders() { ps -eo comm= -o args= | awk '$1=="claude"' | wc -l; }

Controls to print before arming: the counter must see the currently-running leader
(non-zero now), and zero live processes may mention the queued goal's id.

## Never `pkill -f` a goal id, a script name, or any string you just typed

The pattern matches the issuing shell's own command line, because that command line
contains the pattern. The result is the orchestrator terminating itself mid-operation,
reported back as a signal-15 exit on the wrong process.

Resolve to a PID and kill that:

    for p in $(pgrep -x claude); do
      g=$(tr '\0' ' ' < /proc/$p/cmdline | grep -oE 'dispatch-[A-Z0-9-]+' | head -1)
      case "$g" in *TARGET*) kill -TERM "$p";; esac
    done

Two follow-ons measured in the same attempt: a leader started by the dispatcher runs as
root, so an unprivileged `kill` silently fails and the process count stays at 1 — escalate
and re-check rather than assuming the signal landed. And when a watcher must stand down a
peer watcher, match the SCRIPT PATH (`bash .../queue_x.sh`) rather than the bare name, and
skip `$$`.

A script whose job is only to dispatch should contain no kill calls at all; grep it for
`kill` before arming and expect zero.

## A goal file edited AFTER dispatch is invisible to the running leader

A leader reads its goal file once at startup. Rewriting that file a minute later — to fold
in a criterion, to add a ruling — changes nothing about the run already underway: the plan
never carries the new criterion, the executor cannot miss what it never saw, and the gap
surfaces only if a late review round happens to notice. Measured cost: an entire
acceptance criterion ended UNPROVEN because the dispatch raced the edit by sixty seconds.

So the watcher must refuse to dispatch a moving target:

- Require the goal file's mtime to be at least ~60s old before dispatching, and log the
  wait when it is not. Prove the guard refuses a just-touched file before arming.
- Record the file's sha BEFORE the dispatch and again after, and log whether they match.
  A mismatch is the race having happened, visible in the log instead of three hours later.
- If the edit is already lost, do NOT restart a run that is hours in. Write the addition
  as a ruling file beside the goal and say in the log that the plan never carried it, so
  the gap is attributable to the dispatch rather than to the executor.

Corollary for reporting: grepping the PLAN for a criterion measures whether the plan
mentions it, not whether the work is happening. Check the evidence directory and the
process arguments before telling anyone a criterion was skipped.

## A stale verdict file will refuse your queue on an old answer

Where a queue gates on another goal's verdict, reading the report file is not enough:
goals that held earlier in the day already have one from that hold. A naive read returns
the OLD verdict and the queue refuses, or worse, proceeds.

Require the report to postdate the dispatch, and make staleness a THIRD state distinct
from any verdict:

    mt=$(stat -c %Y "$report" 2>/dev/null || echo 0)
    [ "$mt" -le "$DISPATCH_EPOCH" ] && { echo STALE; return; }

- `PASS` → dispatch
- `HELD` / `FAIL` → hold and say why, exit a dedicated code
- `STALE` while the slot is FREE → the leader exited without writing a verdict. Stop and
  say that; waiting forever on it is a silent hang.

Prove both directions before arming: the current file must read STALE, and a file written
now must read FRESH.

## Gate a second goal that writes the SAME artifact on the first closing PASS

Two goals targeting one workflow or one file must not interleave. If the first ends HELD
or FAIL its changes may be half-applied, and a second goal editing those nodes merges two
goals' work with no record of which half is whose. Make the queue refuse on anything but
PASS and name the shared artifact in the log line, so the hold is self-explaining.

Tell the dispatched goal the same thing in its prompt: diff the live artifact against the
other goal's staged version, report the overlap, and STOP on a collision rather than
merging. That is a hold, not a failure.

## Writing goal files while a leader runs trips its window check

A live leader's tripwire watches for filesystem changes in the trees it owns, and a new
goal file appearing under the goals directory registers as a peer difference. A
well-behaved leader classifies it and continues, but it costs a review round and pollutes
the window record. Prepare goal files in a scratch directory while a leader is live and
copy them into place in the gap, or expect the incident line.

## Before opening a new investigation, grep CLOSED goals for orphaned recommendations

A goal that closes PASS with a single recommendation — "a follow-up goal that does X" —
produces nothing unless someone writes that goal. Those recommendations sit unimplemented
while the same finding gets rediscovered from scratch at full cost, usually worse than the
original.

So before writing a new goal from a fresh finding, search closed reports for the territory
and read the match. One such closed report already carried the mechanism, a full channel
inventory and its own archive-and-restore pattern, none of which the rediscovery had. When
the finding is already measured, the right next step is to turn the existing
recommendation into a dispatched goal and cite it — not to re-measure it.

## Goal lint and executor-gate invocations take PATHS, not ids

Handed a goal id, those checkers report the goal as unreadable, which looks exactly like a
missing goal. Pass the full path to the goal file.

An executor gate that tokenises bare database or resource names will fire against a rule
whose real subject is a narrower object inside one. Fix the goal's wording — name the
resource in prose rather than as a bare token — and never loosen the gate: a gate change
needs its own proof.
