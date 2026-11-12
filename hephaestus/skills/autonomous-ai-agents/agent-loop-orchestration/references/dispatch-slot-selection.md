# Choosing what goes into a free dispatch slot

For the supervised case: a slot opens, the owner wants throughput, and you must pick
the next goal without creating a collision or a false start. Load with the main skill
when an owner asks "what else can run?" or "speed this up".

## Check collisions in BOTH directions, and expect families to exhaust

A candidate's own `## Collisions` list and the running goals' lists are different sets
and either can veto, so test both:

```
for g in <candidates>; do
  sed -n "/## Surface/,/## Acceptance/p" $g/GOAL | grep -ohiE "cluster [A-Z]+[0-9]|Tag: [a-z-]+"
  sed -n "/## Collisions/,/^## /p"       $g/GOAL | grep -ohiE "<running goal names>"
done
```

Because lanes are organised by subsystem, taking one goal in a lane typically
disqualifies every remaining goal in it. An open slot with no legal candidate is
therefore the normal late-batch state, not a planning failure. Say that plainly rather
than filling the slot with a colliding goal: throughput here is bounded by lane
disjointness, not by cores or model budget, and an owner pressing for more width is
owed the mechanism rather than a dispatch.

Pick by set difference, never by card count. The goal with the most cards is usually
the one most likely to collide.

## A report file is not a finished leader

The two obvious liveness signals disagree in opposite directions at the same moment:
`report.md` is written before the close sequence ends, so it tempts you to dispatch
into an occupied slot, while a process-list grep on the goal name counts a
shutting-down leader's lingering children as a running leader. Trust the loop's own
leader-list helper and its `--can-dispatch` predicate over either, and re-read the live
leader set immediately before composing any prompt that asserts who the peers are.

## A deferral is only as real as the goal it names

When a leader parks cards on "goal X decides this", check X exists before relaying the
deferral as queued work. Three outcomes, and only the first is what the report implies:

- X exists and its acceptance criteria decide the question.
- X was RENAMED. Grep the goals tree for the old id, then read the survivor's criteria,
  which frequently do not decide the question at all.
- X was never written and the cards are parked on nothing.

Where the target does not decide it, the honest answer is usually that nothing needs to
run: the question is answerable by measurement now, and a sibling goal may already have
answered it. Carry that back as closed cards with the measurement named, not as a
dispatch. A deferral chain relayed unchecked converts one leader's uncertainty into
standing work for the whole backlog.

## Scope a dispatch to the gates that actually exist

Before dispatching a goal whose criteria need approvals or external artifacts, check
which are in hand. Forbid the rest explicitly in the prompt and require premise
re-measurement plus a cost report in their place. Dispatching a large goal to have it
stop at an ungranted gate spends its whole wall clock rediscovering a fact you already
had, and the leader cannot know which approvals exist unless the prompt says so.

## Tell the slot's occupant what changed under it

A goal dispatched into a lane whose tooling moved since its cards were written will
measure the old premise. Put the delta in the prompt with its instrument: the artifact
that changed, its before and after identity, and which of the goal's own stated
blockers that retires. A leader given a retired blocker re-reports it; a leader given
the delta continues from it.

Include sibling state it would otherwise assume: staged-but-uninstalled work left by a
peer in the same lane family, and which branch is awaiting the owner. Without that, it
treats staged hashes as live and may build on a change nobody approved.
