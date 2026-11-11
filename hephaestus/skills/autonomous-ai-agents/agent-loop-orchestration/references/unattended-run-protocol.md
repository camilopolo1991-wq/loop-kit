# Running an agent loop unattended for hours

For the case where the owner goes away and the loop should keep working — an
overnight shift, a weekend run. Load this with the main skill when asked to keep
goals moving while nobody is watching.

## The failure mode is idling, not crashing

An unattended run rarely dies. It goes quiet at 02:00 because every remaining goal
hit a gate only the owner can clear, and the window is spent waiting. So the first
question is never "is the machinery ready" but "how many goals can actually run
without a human".

**Count dispatchable goals before promising a duration.** A goal qualifies only if
its plan has open work rows (TODO / RUNNING / RETRY) and its goal file is not
parked. Goals sitting at zero open tasks look available in any listing and are not;
so do goals whose only open items are decisions. A run with two dispatchable goals
is a two-goal run however many hours were asked for — say the measured number rather
than the requested one.

**Re-validate stale goals before counting them.** Goals written days earlier may
have premises the system has since outgrown; one such pair had all six of its open
tasks' premises measure FALSE, so its task count was pure illusion. A goal's open
row count is not evidence that the work exists.

## Lanes, not a flat queue

Group goals into lanes by the surface they touch: goals in a lane run serially,
lanes run in parallel. Two goals editing the same subsystem conflict even where the
tamper detector is correctly configured — the detector stops them corrupting each
other's *evidence*, it does not stop them editing the same *file*.

**Derive the lane map from the loop's own collision analysis, not from your reading
of the goal files.** A coarse surface guess made from goal prose missed an
interaction that quarantined a task on the first real parallel run. Where a planning
goal produces a collision matrix, that matrix is the input; your own classification
is a stopgap to be labelled as such.

**A peer's evidence is exempt only while that peer's window is OPEN.** Deleting or
moving files under another goal's evidence directory after that goal exits still
trips a running peer, because the exemption was scoped to the live window. Touch no
other goal's evidence while any leader runs.

## A gate parks the goal; the lane moves on

When a leader exits asking for a decision, append the goal to a held list, skip it
for the rest of the run, and dispatch the next goal in that lane. **Never retry a
gate unattended** — that is how an agent talks itself past a decision the owner
reserved, and a wrong ruling taken at 03:00 compounds unnoticed until morning.

The default contract to confirm with the owner before starting: no decision of any
kind is taken while they are away, however reversible it looks. Every gate that has
actually appeared in practice touched production or irreversibility — DDL, pushes,
rescores, reverts, destructive prunes.

## Session limit waits; weekly limit stops everything

These are different events and must not share a branch. A session limit is a pause:
sleep and retry the same goal. A weekly limit means no further work is possible, so
kill the leaders, write the halt reason to the state file, and stop — feeding the
remaining goals to a closed pool burns the queue and produces a pile of empty logs.

## Bound every loop twice

The advance condition and the dispatch count are independent guards and you need
both. See the main skill for the `grep -c` integer bug that defeats the first one.
The second is a hard cap on dispatches per goal per run: with the counting bug
present, a cap would have turned a 254-dispatch runaway into eight.

Refuse to start at all unless the preconditions the run depends on are measured
present — the detector carrying every required exemption, the auth state live, the
scripts installed. A shift that cannot run safely should not pretend to start.

## Re-stake the lanes from measured state at every start

A lane list hardcoded in the shift script decays silently: goals named in it close,
and the goals that now hold the open work are not in it. Re-derive the lists
immediately before launching, from the dispatchable test above, and **exclude every
goal whose dispatch output carries a gate marker** — a shift that re-dispatches a
gate-held goal is retrying a decision unattended by accident rather than by choice.
Leave a lane empty when a goal already running owns that surface, rather than
backfilling it to look busy.

Record in the script why each excluded goal was excluded. The next reader otherwise
cannot tell a deliberate omission from an oversight, and restores it.

## Never run a shift alongside the goal that is fixing concurrency itself

This is the most expensive sequencing error available to an orchestrator, because it
damages the one goal that would have ended the problem. While the detector is still
unpatched, every sibling a shift dispatches writes its own plan and report files at the
goal root, outside the peer exemption — so those writes quarantine the review windows
of the goal working on the fix. One such shift produced **zero** verdicted items in 33
minutes while quarantining three of the fix goal's four review windows, including its
final verdict. The goals were correctly excluded for gates, the lanes were correctly
re-staked, the cap correctly stopped the churn, and it was still net negative.

So add a precondition above all the others: **if a running goal's purpose is the
concurrency or integrity mechanism, the shift is a single lane containing nothing
else.** Serial is not a compromise here; it is the only configuration that lets the
fix land.

The sibling goals will tell you this themselves if you read their output. Two
independently reported it — one naming the repeated dispatches and saying whatever is
re-launching it should stop until the owner rules, the other recommending it start only
once the fix goal closes with no other leader running. A leader recommending its own
deferral is the loop diagnosing your sequencing, not an agent failing.

## A partial fix does not reopen parallelism

Do not promise the queue can go wide the moment a concurrency patch installs. Read the
goal's own report for which trip sources it closed and which it did not: one patch
proved its two main cases went from tripping every window to tripping none, while two
others — report spooling, and a goal writing its plan file before its first window ever
opens — were untouched and together still account for most quarantines. Its report said
so explicitly, that the patch alone would have cleared one of the three lost windows.
Count the remaining sources, name them, and keep work-in-progress at one goal until each
has a measured zero.

The measurement that settles it is the before/after window-trip count per scenario, run
with the real number of concurrent windows — not the selftest, which can pass identically
with the fix, without it, and with a mutant that disables the cap entirely.

## Re-seed the reporting offset before launching

A watcher that advances an offset over an append-only log will replay every event
since its last tick if that offset is hours stale — which it will be, because the
watcher was last run before the day's work. Re-seed through the watcher's own seed
path, then run one tick and require it to print nothing. A noisy first tick during an
unattended run buries the one event that mattered.

## Silence must be distinguishable from a dead poller

A correct quiet night and a crashed watcher produce identical output: nothing.
During an unattended run that ambiguity is the entire risk. Give the poller a
heartbeat — after N hours with nothing to report, emit one line naming the running
leaders and anything parked, so silence afterwards means "checked recently, nothing
needs you" rather than "unknown".

Raise the heartbeat interval while the owner is asleep and lower it when they
return: the heartbeat exists to prove liveness to someone who might act on it, so
waking them to prove the watcher is alive inverts the purpose. Keep the normal
event reporting fully on — heartbeat suppression is about the liveness line only,
never about real events.

## Hand off in writing before the run starts

Write a handoff file on the agent host, not only in the conversation: what is
running, what is held, the standing rulings for the night, and what to do first next
session. A fresh session with no conversation history should be able to resume from
it. Include your own errors by name — those are the entries that stop a repeat, and
they are the first thing lost when a context window ends.

## When the agent host runs out of quota mid-goal

The signature is a leader that exits early with a dispatch log containing only a
limit notice and a reset time, and no report written.

**Whether the orchestrator's quota and the agent host's are the same pool depends
on their credentials, and that can change without notice.** While both authenticate
as the same account, one empties for both and the orchestrator's own tooling fails
in the same minute the agent does. Once the owner points the agent host at a
different account, the pools are independent — and "my session ran out, work
stopped on both ends" becomes a guess rather than an observation. Re-read the
agent host's auth state rather than carrying the account, plan or org from an
earlier session, and check the host before agreeing that it stopped; reporting a
halt that did not happen wastes the window the owner still has.

This is not a failed goal. Handle it as a pause:

- **Resume, do not restart.** A well-built loop keeps per-task status in its plan file
  on disk; re-dispatching the same goal picks up at the first unfinished task and
  preserves the completed ones. Restarting from scratch discards graded work and
  spends the quota twice.
- **Probe before re-dispatching.** Run one cheap bounded session first and require a
  known literal back. Re-dispatching a multi-hour leader into a still-exhausted quota
  wastes the wall clock and produces another empty log.
- **Journal the interruption and the evidence that it lifted** — what the log said,
  how the reset was confirmed, which task the plan resumes at — so the gap in the
  record is not read later as an unexplained failure.
- **Re-scope to the budget that remains** rather than starting something large that
  will be abandoned half-done.

### Stopping a goal on request

Stop the supervisor first and the leader second, so the queue cannot relaunch the
goal in the gap between the two kills. Then confirm by process check that both are
gone, and write the queue state file to a paused marker so nothing auto-resumes.

**Stop between windows, and check for a task that has returned but not yet been
recorded.** A sub-role's output reaches the leader before the leader writes that
result into the plan row, so a stop in that gap discards graded work that was
already paid for — the plan still reads TODO and the task reruns in full on
resume. Read the journal's most recent entries first: a line reporting a writer or
reviewer returning, with no corresponding plan-row update, means waiting a minute
costs less than the rerun will. When an immediate stop is nonetheless the right
call, say in the handover which task will be paid for twice rather than letting it
surface later as unexplained spend.

Journal the pause with what was banked, what is in flight, and the exact command
to resume. A stop that leaves no resume instruction turns a pause into an
investigation.

