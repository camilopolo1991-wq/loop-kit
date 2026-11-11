# Unattended shift hygiene

For a loop that runs on a timer while nobody is watching: a cron tick arms,
dispatches a goal, and keeps the queue moving until its window closes. These are
the failure shapes that waste a whole window, and the checks that catch them.

## A refusal the queue does not remember starves every other goal

When a pre-dispatch gate refuses a goal, record the refusal and skip that goal
for the rest of the window. A `--next` selector that re-derives its answer purely
from goal state will keep returning the same ungated goal every tick, and the
gate will keep correctly refusing it, while every other dispatchable goal waits.
The gate is not the bug; the missing memory is.

Shape that works:

- the dispatcher appends `GOAL<TAB>reason` to a blocklist file on gate failure
- the queue selector filters blocklisted goals out of its candidate pool
- the shift-end path deletes the blocklist, so a blocked goal gets a fresh
  attempt next window after a human has had a chance to fix it
- `--list` prints the blocklist with reasons, because a goal that is silently
  skipped is indistinguishable from one that does not exist

Scope the block to one window. A permanent exclusion turns a transient refusal
into a goal nobody ever revisits.

## Prove the skip is real with a negative control

A filter that empties the candidate pool looks identical to a filter that skips
correctly. Test three cases before believing it:

1. block the goal that IS next, assert `--next` returns a different goal
2. block a goal that is NOT next, assert `--next` is unchanged
3. remove the blocklist, assert the original goal returns

Then block each successive answer in turn and confirm the selector keeps
advancing rather than jamming on the second candidate.

## Define a helper before the branch that calls it

In shell, a function called from an error branch but never defined fails only on
the path that was already failing: the dispatcher exits 127 the first time a gate
refuses, converting a slow stall into a hard crash at the worst moment. Read the
file back after editing and confirm every called helper has exactly one
definition, and that `bash -n` passes.

## Scheduled action must not depend on a model choosing to act

When the payload of a timer is a prompt that both says "run the protocol" and
"stay silent unless something happened", the instruction to stay quiet wins and
the tick records a completed run having done nothing. Put the action in a script
the scheduler executes, and use the model only to deliver a notification when the
script signals there is something to say. Branch on the script's exit code, not
on prose.

## Log a heartbeat on every tick, whatever the tick decides

A silent no-op and a never-invoked script look identical from outside. Append a
timestamped line on entry, before any decision, so the absence of the heartbeat
is itself evidence. Pair it with a decision log that records refusals and the
reason, so a window that produced no work can be explained afterwards.

## Read the outcome of a shift from its own logs, not from the code

To answer "did the shift work", read the decision log for ARM / START / DISPATCH
/ REFUSE / SHIFT END lines and count them. Reading the script tells you what it
intends; only the log tells you what happened. A shift can arm, honour its veto
window, and stand down correctly, which is a working shift and not a failure.

## Dispatch capacity is rarely the limit; the human-ruling pile is

Count goals by state before proposing more throughput. A loop whose reports come
back needing a human verdict accumulates them: when goals awaiting a ruling far
outnumber the dispatchable pool, adding dispatch capacity changes nothing. Report
the ruling backlog as the constraint.

## Identify an orphan agent process before killing it

Long-lived agent daemons leave spare/host process pairs behind when a session
dies. Before killing any of them, prove the specific pair is unclaimable rather
than inferring it from age:

- check whether its claim socket still exists on disk; a spare whose claim socket
  is gone can never be claimed again, while the live pair's socket is present
- control against the currently-live pair, and confirm the live one is NOT the
  process you are about to kill
- confirm no loop leader is running and the work window is closed
- record memory before and after, so the benefit is measured rather than assumed

Attribute the orphan to a goal only if the evidence supports it. Spawn time
correlating with a goal's activity is a correlation, not ownership; say so
instead of naming an owner you cannot prove.

## Globs expand before sudo

A pattern like `$LOOP_HOME/goals/*/` in a `sudo` command line expands as the
unprivileged user first, matches nothing, and the command reports zero without
error. Put the glob inside the privileged shell, and treat a zero from a
privileged listing as UNKNOWN until a positive control proves the probe can see
anything at all.
