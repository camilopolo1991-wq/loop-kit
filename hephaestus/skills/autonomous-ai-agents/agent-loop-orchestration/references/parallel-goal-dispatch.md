# Running several goal loops at once

Serial dispatch is the right default only while the integrity detector guarding the
work tree cannot distinguish a peer's legitimate writes from an intruder's. That is a
measurable property, not a permanent one. Once a negative-case test proves the
detector attributes peers correctly, keep obeying the concurrency cap and stop obeying
the serial conclusion drawn from the old limitation.

The failure this prevents: carrying a constraint whose premise you have already
disproved. The note that justified serial work names its own exit condition, and that
condition can be satisfied with a test.

## Step 1: prove the peer detector fires before you widen concurrency

Do not take "peer differences: 0" as evidence of safety when no window has ever shown
a non-zero. A detector whose positive branch has never fired is an absence of
evidence. Build a synthetic tree and exercise it:

- POSITIVE: a peer writes under its own evidence path while its window is open.
  Must appear as a peer difference, not a real one.
- NEGATIVE: a write outside any evidence path. Must count as REAL.
- NEGATIVE: a peer path whose window is NOT open. Must count as REAL.

A harness that only runs the positive case cannot fail. Each negative case must break
exactly one of the detector's documented conditions so the boundary is measured.

### Harness pitfalls, each of which produced a false zero

- **Override every root the detector walks, not just the obvious one.** An
  evidence-root variable usually only relocates where evidence is written; the file
  scanner walks a separate root. Miss it and the baseline captures the real
  filesystem (hundreds of thousands of entries) while your synthetic tree is never in
  scope, so every count returns zero and looks clean. Check the baseline's file count
  against the size of your synthetic tree before believing any result.
- **A clean check CLOSES the window.** Checking before planting anything writes a
  closed marker, so every later write is unwatched and reads zero. Give each case its
  own window: plant, then check once.
- **Tear down as the same user that created the tree.** A tool running under sudo
  leaves root-owned directories; a recursive delete as the unprivileged user fails,
  and with errors ignored it fails SILENTLY. The next case then inherits the previous
  case's open window and its baseline, which looks exactly like a detector gap. Delete
  with elevated privileges and assert the directory is gone, raising if it survives.
- **Write test artifacts as the user the tool runs as.** A write that dies on
  permissions reads as "no difference detected".
- **Confirm the environment variable name from the tool's own source** rather than
  guessing it. A guessed name is silently ignored and the tool runs against production
  paths.

## Step 2: compute the real cap, and say it plainly

Read the cap's wording from the tool, not from the number you remember. A cap phrased
as "refuses when N OTHER jobs hold an open window" means N+1 total, and with N already
running exactly one slot is open. Announcing three free slots when one exists sets an
expectation the tooling will refuse.

If the start call returns the cap's exit code, that IS the cap: wait and retry. Never
work around it.

**A cap refusal naming a unit you can prove is finished is a counting defect — report
it, do not route around it.** Caps count windows, and a window is only closed by a
valid marker; stale, legacy and abandoned windows from units that ended months ago can
keep occupying slots and refuse correct work for a reason that is not true. Verify by
walking the evidence directories directly (a baseline with no closed marker beside it
is open) and compare that list against the names the tool printed. When the two
disagree, the tool's count is the one blocking work and the discrepancy is the finding.

Diagnose it by READING state, never by calling the acquiring verb. Running `start` to
see whether it succeeds makes the coordinator the holder of a worker's window, which is
exactly the tampering the detector exists to catch. If that happens anyway, release it
immediately with a marker the tool accepts as valid, confirm it is treated as a
legitimate close rather than a forgery, and disclose the touch in the record — an
undisclosed probe becomes the next unit's unexplained anomaly.

## Step 3: pick co-runnable work by declared cluster, not by guess

Goals in these systems usually declare a surface tag or cluster plus an explicit
"cannot run concurrently with" list. Select on both:

- Reject any candidate naming a running goal, or sharing its cluster.
- Check the running goals' lists too; the exclusion may be declared on only one side.
- Throughput is bounded by cluster disjointness, not by cores or budget. Expect whole
  families to be excluded at once because every member shares a surface with the one
  already running. Say so rather than reporting a free slot you cannot fill.

Parse failures matter here: an empty cluster field may mean genuinely no shared
surface, or a section heading that did not match your extraction. Print the raw
section before concluding a candidate is free.

**Where no cluster is declared, derive one from the WRITE SET before dispatching.**
An open slot answers "is there capacity", never "can these run together", and units
that sound unrelated routinely share one checkout, one service or one table. Three
units dispatched into three free slots all wrote the same application tree: they moved
its HEAD and restarted its service inside each other's windows, producing four
integrity incidents in forty-five minutes and quarantining findings that had to be
re-measured from scratch. Nothing was wrong with the units; the concurrency was wrong.

List for each candidate the files, services, branches and tables it will WRITE, and
serialise any pair that intersects. A unit touching a UI tree and a unit touching data
and workflows are a safe pair; two units on the same tree are one unit that must be
ordered. When the operator has authorised raising the cap for a specific unit, that
authorisation does not generalise — the next unit needs its own write-set check.

**A resumed unit must re-measure its own baseline.** Once a peer has moved shared
state, the BEFORE taken on the old state is void, and a comparison spanning the change
is two incomparable runs. Say in the report which earlier evidence was discarded and
why, and prefer a unit that stops and reports contention over one that routes around a
peer's lock — the latter produces evidence about a system nobody can reconstruct.

## Step 4: build the peer list at dispatch time, never by hand

**The dominant failure of parallel dispatch is a stale peer list in the prompt.**
Telling a leader "you are the only one running" or naming two peers and then starting
two more makes every subsequent integrity window unattributable, and a careful leader
responds by quarantining its own reviews. The work is not lost but it is repeated.

Therefore:

- Query the live leader list at the moment the prompt is assembled, and interpolate
  it. Do not type peer names into prose.
- Tell each leader that the set may GROW after it starts, and that an unlisted writer
  under a sibling goal's evidence path is still a peer.
- Instruct it to report real differences and peer differences separately with their
  own counts, and never to request a wider noise exemption.
- Give it the clearing procedure that works: re-hash its own files after a dirty
  window and show they match what was reviewed. That clears a window honestly;
  an exemption hides the signal.

## Step 5: expect legitimate dirty windows and read them correctly

A window showing many differences attributed to a named sibling is the detector
working. Before treating it as an incident, check whether the paths all sit under the
sibling's own evidence directory.

When differences are attributed as real despite coming from a known peer, check the
timing condition rather than assuming a bug: a peer window that OPENS DURING your
window does not make that peer eligible, because the eligibility record is taken from
your baseline. A sibling with an earlier window and a later one can therefore be
excused for the first and counted real for the second. This is specified behaviour.

## Step 6: hold box-level work while leaders run

Filesystem maintenance, guard edits, bulk compression and permission changes trip
every open window and force reviews to be redone. Schedule them for when no leader is
running. A cheap housekeeping job can cost more agent time in quarantined reviews than
it saves.

## Reading what comes back

- A leader reporting "closed this card as FALSE with evidence" has delivered a full
  result. Re-measuring a premise and refusing the implementation is the goal working,
  not a shortfall.
- Verify the leader's headline claims yourself against the live system, and verify
  them in the right place: an identifier belonging to a staging environment returns
  zero callers when queried against production, which reads as a finding and is
  actually a wrong-database error. Name the environment beside the number.
- When a leader defers a decision to another goal, confirm that goal EXISTS before
  carrying the deferral forward. A deferral to a goal with no directory is an open
  question wearing a plan's clothing, and the goal it meant may be the same one under
  a different name.
- Answer the open questions a leader hands back when they are mechanically decidable.
  For "do these two branches merge cleanly", a dry-run merge-tree printing "changed in
  both" is NOT a conflict; that line appears for any file touched on both sides. Run a
  real trial merge in a throwaway worktree, read the conflicted-file count, then abort
  and remove the worktree.

## Running goals concurrently

**First separate the two kinds of parallelism, because only one of them is capped.**
A leader fanning out several read-only sub-roles *inside one goal* is normal, is the
leader's own job, and typically runs many-way without incident: the sub-roles share
one goal id, one evidence tree and one tamper window, so nothing they write looks
foreign. What is capped is running several *goals* at once, because each goal opens
its own window over the same filesystem. Before telling anyone parallelism is
blocked, look at what the running leader is already doing — reporting a one-at-a-time
limit while a leader is fanned out eight ways is simply wrong, and adding a second
goal beside a fanned-out one slows both rather than speeding anything.

Before assuming capacity is the limit, find the mechanism that assumes a single actor.
Tamper detectors, resource locks, id minting and "current job" pointers all commonly
scope their exemptions to *self*: the running job ignores its own writes and watches
everything else. With one job, self and legitimate coincide. With three, a peer's
legitimate output reads as tampering and the integrity check refuses to certify.

That forces serial execution on a machine with ample headroom, and the symptom is a
second goal reporting differences that are entirely the first goal's files.

**Widening the exemption so every job ignores every other job is the wrong fix** - it
restores concurrency by deleting the property the detector existed for. Any change
here must ship with a negative case: name a modification a peer *could* make that the
new rule must still catch, and prove it is caught with all windows open. A change that
makes every window quiet in every case has disabled the check, not fixed it.

**That negative case is also the RETIREMENT CONDITION for the serial rule, so re-prove
it before accepting the limit as current.** A one-goal-at-a-time rule written when the
detector could not distinguish peers outlives the defect, because nothing re-tests a
constraint that is merely inconvenient. Re-run the three-case probe against a synthetic
root: a peer's write under its own open window must be EXCUSED, a write outside the
exempt path class must count as REAL, and a peer with no open window must count as
REAL. Where all three hold, the detector works and serial execution is leaving capacity
idle; where the first fails, no reading from that detector is reportable at all.
Keeping a disproved premise's conclusion is the carried-versus-measured error applied
to your own operating rules, and it is expensive in the direction nobody audits: idle
slots produce no incident.

**Read the cap from the tool rather than choosing a number.** These detectors state
their own limit on simultaneously-open windows (commonly "refuses while N OTHER
distinct goals hold one", so the true ceiling is N+1), and dispatching above it refuses
quietly at window-open rather than failing loudly.

**Key collisions on the goals' declared CLUSTER or lane tag, not on a keyword scan of
their surface prose.** Goal files that carry an explicit tag (`Tag: <lane> cluster
<ID>`) have already had this decided by whoever wrote them; grepping the prose instead
reports two goals in the same lane as identical and two genuinely disjoint goals as
empty whenever their text names no tool. Dispatch only across distinct clusters, and
verify the tag was actually parsed rather than silently empty.

**Every concurrent dispatch must TELL the leader its peers exist.** Name the peers and
their clusters, require real differences and peer differences to be reported separately
with their own counts, and order the leader to stop and report a collision rather than
take an object outside its cluster. A leader that believes it is alone reads a peer's
legitimate writes as tampering and quarantines its own review - the exact cost the
serial rule was invented to avoid, reintroduced by omission in the prompt.

**A statement about the environment in a dispatch prompt is a promise for the whole
run, so never assert a situation you are about to change.** Telling a leader it is the
only one running and then starting peers behind it is worse than saying nothing: the
leader trusts the claim, reads every subsequent trip as intrusion, and quarantines its
own clean checks. One such prompt cost two quarantined review rounds and a redone
report while the detector was working perfectly and attributing every peer write by
name. Either name the peers, or tell the leader to enumerate the running set itself
before it opens a window.

**Disclose your own prompt defect to the owner before reporting the leader's result.**
A leader that reports an incident caused by your brief has found a defect in your work,
not in its own, and presenting the incident without that attribution invites the owner
to distrust the agent. Lead with the brief's error, then the result.

Once the three-case probe passes, the serial rule is retired: dispatch across distinct
clusters up to the tool's stated ceiling and say what you measured. Keep
work-in-progress at one goal only while that probe is unrun or its first case fails,
and name which of the three cases is outstanding rather than citing the limit as
standing policy. An owner asking "no other candidates for parallelism?" is the usual
signal that the rule outlived its premise, and arriving at that question before you is
a failure of your own audit, not of theirs.

**Separate a tool-enforced ceiling from a safety rule in a dispatcher you wrote.** A
night-shift or unattended dispatcher that refuses a second leader is a policy for
UNSUPERVISED runs; reading it as the system's concurrency limit silently halves
capacity during supervised work. Read both the detector's own cap and each dispatcher's
refusal condition, and state which one is binding.

### "Can we parallelise the backlog to go faster?" — measure the real ceiling first

When an owner proposes fanning a large read-only triage across many goals, three
numbers decide the answer and only one of them is usually the limit:

- **Host capacity.** Measure it (`nproc`, `/proc/loadavg`, `free -m`, and summed
  RSS of the live leader processes). Leaders are typically a few hundred MB each
  against many GB free, so hardware is rarely binding — do not cite it as the
  reason without the numbers.
- **The model budget.** This is normally the true ceiling, and it does not scale
  with cores. A triage of N cards is not N calls; it is (goals) × (leader +
  scouts + one reviewer window each). Quote remaining budget against that
  arithmetic rather than against the card count.
- **The detector's tolerance for concurrent windows.** Keep the practical cap well
  below what RAM allows, because every extra concurrent goal is another chance of
  the cross-goal foreign-write quarantine.

**Then check you can enumerate the work at all before promising a fan-out.** A
parallel plan needs a machine-readable inventory of the items and their states to
split into batches; if the tracking CLI has no list verb and the expected backlog
file is not at the path you assumed, you cannot divide anything. Confirm the store
and the read path first, and when they are missing, say the prerequisite is an
inventory goal rather than quoting a throughput figure you cannot deliver. Guessing
the backlog's location and reporting a plan built on it is the failure shape here.

### You are a peer. Your own writes quarantine running tasks

The detector scopes its exemption to the running goal's own evidence tree, and the
orchestrator is not inside it. Installing a new goal file, creating a goal
directory, or appending to a shared journal while a window is open lands as a
foreign write and quarantines whatever task was in flight — the agent then reruns
graded work for no reason, and the incident is logged against the goal rather than
against you.

Before any write under the loop's state tree, check whether a leader is running.
If one is, stage the file somewhere neutral and install it after the goal exits.
Journal entries are not exempt: they are writes like any other. When it happens
anyway, say so in the incident record — an unexplained quarantine sends the next
reader hunting a tampering bug that does not exist.

**Enqueuing a goal is not deferring it: the directory appears immediately.** A
queue that waits for a free slot still creates the new goal's directory, GOAL file
and evidence tree at enqueue time, hours before its leader starts. So "I only
queued it, the running goal is untouched" is false — the detector sees a new tree
under the watched path within the open window and quarantines the in-flight task,
which on one run discarded a completed independent review and forced a full
re-review at full price. Queueing is a write; hold the enqueue until no leader is
running, or give the queue's own dispatch path a narrow pre-authorised exemption
proven in both directions.

**Peer attribution usually exists already, and it has a precondition that dictates
the dispatch shape: create every goal directory BEFORE any leader starts.** Mature
detectors do excuse a sibling goal's writes under its own evidence tree — but only
when that sibling's goal file was already present in the checking window's own
baseline. A goal created *during* a window can never become a peer, by design, so
its legitimate output is unexcusable for the whole life of that window and both
sides quarantine. This is why trickling goals out one at a time produces quarantines
while a batch does not: stage all the goal files, verify each landed by hash, then
dispatch them together with one queue invocation. Read the detector's peer rules
before concluding concurrency is unsupported — reporting "the detector has no
concept of a sibling leader" when the mechanism is present and you violated its
precondition misdiagnoses your own error as an architecture gap.

**Read the detector's own documentation for a numeric cap, and set `-j` from it
rather than from host capacity.** Peer-attribution mechanisms commonly ship a hard
limit on simultaneously-open windows, stated in the same help text as the
attribution rules — so the paragraph you read to learn the precondition also names
the ceiling. Dispatching above it does not fail loudly: the surplus goals refuse at
window-open, journal the refusal, set a watcher and exit, which from the outside is
indistinguishable from a crash. Choosing a width from cores and free RAM while the
verification layer caps lower wastes those goals' slots entirely.

**Correctly-created peers still quarantine each other, because the exemption covers
only `<peer>/evidence/`.** Three writes every goal makes fall outside it. A leader's
own plan file sits at the goal ROOT, not under its evidence tree, so each sibling
writing its plan trips every other open window; a SHARED ledger — the model-call
counter and call log that all goals append to — is watched like any other file, so
any peer that spends a model call quarantines every concurrent window; and the
**report SPOOL plus its index** is where every goal writes when it CLOSES, so a peer
finishing normally quarantines whatever review is open at that moment. The last is
the one that proves the exemption is mis-scoped rather than merely incomplete: a rule
that every normal completion violates will fire forever, and it fires hardest at the
end of a batch when several goals close together. Before promising a batch will run
clean, check what the collector watches and whether the exemption reaches the goal
root, the shared ledger and the spool; where it does not, that is the fix to scope,
and it needs the both-directions proof above.

**Scope the exemption by PATH CLASS, and keep the boundary at the line where a diff
stops being attributable to a peer.** The defensible rule is that a difference
confined to another goal's own directory, another goal's scratch, or the shared spool
is noise, while anything outside those — the kit, the role definitions, the
orchestration repo, your own tree, or a path inside your own goal you did not write —
still quarantines. Require the report to state the check as a falsifiable sentence
("N differences, all confined to <list>, 0 outside") rather than as a verdict, because
that sentence is checkable by the next reader and a bare "peer noise" claim is not.
Verify the claim yourself before ratifying it: a leader reporting "all differences are
in peer X's folder" is routinely wrong about WHICH peers contributed, and the
conclusion usually survives in a stronger form (zero outside the exempt classes) that
is worth substituting for the one offered.

**Parallelise by PHASE, not by slot count: a goal inside a reviewer window must be
the only one writing.** The cap tells you how many goals may open windows; it does
not tell you when adding one is free. A goal in its measure-or-write phase tolerates
peers, because its own writes are what the detector excuses. A goal in a review
window is being graded against a filesystem snapshot, so every peer write is
potentially a quarantine — dispatching into that moment converts a finished review
into a rerun. The ratio is stark when measured: the same goal's windows ran with a
handful of diff lines while it was alone and with one to two orders of magnitude more
once peers were added, every extra line belonging to a peer. Before dispatching,
read the running goals' plan files for review-task rows and wait if one is open. The
honest summary when an owner asks why throughput did not scale: the work
parallelises, the verification instrument is global, so concurrency does not slow the
work down — it invalidates the evidence.

**A goal that exits rc=0 with tiny output and open plan rows has usually refused,
not died — read its stdout before reporting a crash.** A well-built leader that
cannot open a window says so in one line, names what is blocking it, and parks. That
is the design working, and it also means the goal will self-start when a slot frees,
so re-dispatching it immediately duplicates the run.

This is the most common way an orchestrator damages a healthy run, and it is
invisible from the orchestrator side: the dispatch succeeds, the file lands, and
the cost appears minutes later as a rerun inside someone else's goal.

**Resuming a goal is itself a write, so care alone cannot satisfy this rule.**
Re-dispatching touches the queue state file, the queue log and the goal's own
dispatch output — all under the watched tree and none inside the running goal's
evidence directory. A resume issued while the leader has already opened its next
window therefore quarantines a batch that your own resume started. Treat the
dispatch path as needing a standing exemption in the detector's configuration
rather than promising to be careful; until it has one, resume only in the gap
between a window closing and the next opening, which the loop's journal marks
explicitly.

**Adding that exemption is a three-step job, and skipping the first or third
step ships a lie.** First reproduce the defect: open a window, append one line to
the supervisor's own log, and read the diff naming that file — without this you
are guessing at which path is watched. Then patch the collector's skip set with
the narrowest path that covers the supervisor's bookkeeping and nothing else.
Then prove BOTH directions: bookkeeping writes must now report no differences,
**and a real modification to a goal file must still be caught by name.** An
exemption is the mirror image of a guard — a guard is worthless if it cannot
fire, an exemption is dangerous if it silences everything. Demonstrating only the
new quiet is how a detector gets blinded while reading as fixed.

Expect the patch to miss a second copy. These kits commonly exist as a tracked
source tree plus a live install, and an unrelated in-flight goal may have already
edited the region your patch targets, so the pattern match fails silently on one
of them. Re-read both copies' hashes afterwards: when they diverge, a routine
reinstall reverts the fix, and that must be recorded where whoever reinstalls
will see it.

**When a planned change will trip the detector, pre-authorise it narrowly and in
writing before making it.** Credential rotations, config swaps and tool installs
that the owner has approved still land as foreign writes. Record the
authorisation in the loop's own journal ahead of the change, naming the exact
paths covered and stating that any other path is *not* covered and must be
treated normally. That converts an alarming diff into an expected one without
weakening the detector, and it survives into the goal's incident record so the
next reader is not hunting a tampering bug. A blanket "ignore diffs for now" does
the opposite and must never be written.

**A surface the detector does NOT watch is more dangerous than one it does.**
Before making any write while a goal runs, establish what the detector actually
collects — read its collector functions, do not assume it covers everything the
goal touches. These detectors typically snapshot files plus the orchestration
database, and leave the *application's own* database unwatched. A config or data
write to that unwatched surface will not quarantine anything; it will silently
change the values a running goal is replaying, so the goal reports a measurement
nobody can reproduce afterwards and nothing marks it as contaminated. A loud
quarantine costs a rerun; a silent corruption costs the whole finding's
credibility. When an owner asks for such a write mid-goal, stage the statement
with its rollback, say why it is waiting, and apply it once no leader is running.

### Serving "run them all" while parallelism is still broken

An owner asking to resume everything wants throughput, not a specific dispatch
shape. Launching every goal at a detector you have already watched quarantine a peer
spends a work window to produce N quarantines. Run them **serially, unattended**,
and say in one line that you serialised and why — that satisfies the intent without
waiting on another round trip.

Install a queue script on the agent host and start it detached, rather than
supervising dispatches yourself from the orchestrator:

- **Order the unblocking goal first.** Put the goal that fixes the concurrency
  mechanism at the head of the queue, so everything behind it may run wide if it
  passes.
- **Wait on the real binary, not the wrapper**, using the same match discipline as
  the started-check above, and wait for the already-running leader to exit before
  the first queued dispatch.
- **Halt the queue on a quota death** instead of continuing. Detect it by grepping
  the dispatch log for the limit notice, record which goal it stopped at, and exit;
  feeding the remaining goals to a closed window burns the queue for nothing.
- **Never treat process exit as goal completion.** A leader that dies on a quota
  limit, a timeout, or a crash exits exactly like one that finished, so a queue
  that advances on exit hands the next goal a working tree full of the previous
  goal's half-applied edits. Require positive evidence before advancing: re-read
  the goal's plan file and refuse to continue while any task is still TODO,
  RUNNING or in RETRY. Record which goal stalled and how many tasks were open.
- **But do not treat open plan rows as proof of open work either — pair them with
  the report verdict.** Plan rows are frequently NOT updated when a goal closes, so
  a goal that finished and wrote a PASS report still shows TODO rows forever. Of
  thirteen goals showing open rows on one box, only four were genuinely open. A lane
  keyed on the row count alone re-dispatches completed work all night. Dispatchable
  means open rows AND no closing verdict in the report AND the goal file not marked
  parked; incomplete means open rows AND no verdict. The two rules are the same
  instrument read in opposite directions, and each is wrong alone.
- **Take the queue order as an argument, not a constant in the file.** Re-queueing
  after a halt is the normal case, and editing the script to change the order
  invites the running-script hazard below.
- **Write a state file** naming the running or halted goal, so the poller can tell a
  queue that is self-advancing from one that needs a human.

**Key the poller on each goal's own output, never on whether the queue is alive.**
Suppressing while the queue advances looks tidy and silently swallows the most
important event there is: a goal that stopped to ask the owner a question. The
queue moves on to the next goal, the poller sees work in progress, and the held
question is never delivered — the owner finds out by asking. Track a per-goal
signature (goal id, output size, mtime), report any goal whose output is new since
it was last reported, and dedupe on that signature alone. A halted queue is one
more event to report, not a precondition for reporting anything else. Prove the
speaking branch with a stand-in returning the finished state, because "it printed
nothing" is not evidence of correct silence.

Keep goals out of the queue when they need a decision first. A goal whose
instructions have drifted from its authorized amendments cannot be re-dispatched as
written; queueing it just spends a window reproducing the drift.

`templates/serial-goal-queue.sh` is a working starter implementing all three
guards above — real-binary wait, quota halt, and plan-not-complete halt. Copy and
adapt the paths, binary, role and status tokens.

**Never compute a loop's advance condition with `grep -c PATTERN file || echo 0`.**
`grep -c` prints `0` **and** exits 1 when nothing matches, so the fallback fires on
top of grep's own output and the function returns the two-line string `0\n0`, not an
integer. Every `[ "$n" -eq 0 ]` test against it then errors instead of matching, the
"no open tasks" skip never fires, and the lane re-dispatches a finished goal
forever: this ran one goal 254 times overnight and spent roughly a thousand dollars
of model budget doing nothing. Capture the output first, then default a non-numeric
value (`n=$(grep -c ... 2>/dev/null); case "$n" in ''|*[!0-9]*) n=0 ;; esac`). Then
add a hard per-goal dispatch cap regardless, so any future counting bug is bounded
instead of running until morning.

**The same trap applies to `pgrep -fc PATTERN || echo 0`, but its blast radius is
narrower — measure before escalating.** `pgrep -c` also prints `0` and exits 1 on
no match, so the fallback appends a second line and any `[ "$n" -ge "$max" ]` test
against it errors. Crucially it only misfires in the ZERO case: once a process
matches, pgrep exits 0, the fallback never runs, and the comparison gets a clean
integer — so a slot-wait gate built this way still holds. Diagnosing the string bug
and reporting "the concurrency limit is not enforced" is an overstatement that has
had to be retracted. **Prove the consequence with a sentinel before claiming
severity:** launch a stand-in process whose command line matches the pattern, run
the real predicate against it, and read whether it says WAIT or NOT-WAIT. Then
confirm against history — a queued job that demonstrably waited out its predecessor
is evidence the gate works. Downgrade the finding to cosmetic stderr when that is
what it is, and separately retract any consequence you wrongly attributed to it;
window quarantines caused by your own writes are not caused by a counting bug.

For unattended multi-hour runs — lane construction, gate parking, limit handling
and the liveness rule — see `references/unattended-run-protocol.md`. For filling a
slot that just freed — collision tests in both directions, lane exhaustion, deferral
targets that do not exist, and scoping a dispatch to the gates actually in hand — see
`references/dispatch-slot-selection.md`.

### Verify a new guard can actually fire, AND that it does not fire on everything

A guard added to a supervisor is itself a check that can silently never trigger.
Before trusting one, run its predicate by hand across several goals whose state
you already know — including at least one that must halt and one that must pass —
and confirm the verdicts differ in the right direction. Installing a halt
condition that never fires restores exactly the bug it was written to prevent,
while reading as fixed.

**The opposite failure is equally fatal and far easier to ship: a gate that fires
on every input is the same as no gate**, because the operator learns to acknowledge
it without reading. Measure the hit rate on real inputs before trusting a new
check. A relevance gate matching note BODIES flagged 32 of 50 notes for a single
goal and would have been waved through blind; restricting it to note TITLES — the
claim, not the passing mention — cut it to the eleven that genuinely applied. Match
short keywords on word boundaries for the same reason: an unanchored three-letter
term matched inside an unrelated longer word and fired five irrelevant hits while
the one critical hit stayed missing.

**Apply the control discipline to your OWN diagnostic probes, not only to the goals
you write.** The measurement rules an orchestrator enforces on agents are the ones it
exempts itself from, and a broken probe produces a confident finding rather than an
error. In one session four separate probes nearly became reported facts: a `printf`
that emitted nothing was read as "zero overlap between two files", an `rc=$?` taken
through a pipe reported a refusing gate as passing, open plan rows were read as
liveness without checking for a process, and a redirect to a clobbered `/dev/null`
inverted several negative results. Before reporting any zero, absence, or score that
your own command produced, run the paired control that must return non-zero. A probe
with no control is the check-that-cannot-fail shape, wherever it runs.

**Never let a verification string share fragile quoting with the content it checks.**
A verify step grepping for a phrase that contains a quote character, run through a
heredoc or a nested shell, reports `0` while the edit it was checking landed
perfectly — the escaping broke the pattern, not the write. Pick a distinctive
quote-free substring for the check, and keep the inserted text and the pattern that
proves it visibly separate in the script so a later reader can see they are two
things. Pair it with a control string that must return `0`, so a verify block of all
zeros is distinguishable from a verify block that cannot fire.

**Capture a gate's exit code with nothing between it and `rc=$?`.** A trailing
`| sed` or `| head` makes `$?` the filter's status, so every refusal reads as a pass
and the gate silently becomes a check that cannot fail. This is easy to do while
*testing* the gate, which is the worst moment for it: the test then certifies a gate
that never blocks. The same applies to anything else that runs in between — an `echo`
of the message, a `[ ... ]` test, a second command on the same line — all replace `$?`,
and a harness that prints `rc=0` immediately after a visible REFUSED line is reading
its own `echo`.

**An audited write tool that demands attribution is a feature; supply it rather than
routing around it.** Write wrappers commonly refuse with something like `--write needs
--goal and --reason`, and the refusal is the audit trail working. Pass the goal id and a
reason stating what is changing, the ruling behind it, and the measurement that made it
safe. Then prove the write with four reads in the same call: the named row before, the
named row after, a **blast-radius count** (how many rows carry the old value versus the
new) predicted before running, and an untouched-field hash showing nothing else moved.
A `returning` clause echoing the new value is not proof on its own — it reports intent,
not the committed state. Separately, do not claim an audit row exists for the write
unless you counted that table before and after; attribution reaching the tool does not
mean a row reached the log.

**Bind a gate's receipt to the artifact's content hash, never to its id.** A gate
that records "goal X passed" waves through a different revision of X installed
afterwards — one goal was gate-checked in the revision carrying its folded-in
lessons and installed in the earlier revision without them, and nothing noticed
until a later hash comparison. Store the sha256 and re-verify it at the point of
use; treat a missing staged file as a refusal, because cannot-determine is not a
pass.

**A gate you must remember to run is still a rule. Make it fire from the runtime.**
A pre-tool hook that inspects the dispatch command and blocks when no valid receipt
exists converts the discipline into a mechanism, and it should fail closed so a
crash in the hook blocks rather than permits. Scope the matcher narrowly to the
dispatch shapes only — a hook that intercepts broadly gets disabled within a day,
which is worse than never adding it. Expect the agent runtime to refuse letting an
agent register its own hook in the main config, and treat that refusal as correct:
a gate the agent can install can also be removed by it, so it guards nothing. Having
shell access is not a licence to write the file by another route — that is the
respelling-past-a-denial pattern wearing a different tool.

Hand the owner a paste block instead, and get three things right or the block
silently does nothing:

- **Derive every key from the config file's own documented example or the loader
  source.** An invented key is accepted by the parser and ignored by the runtime, so
  the hook never fires and the verify step still passes. Check too for a companion
  flag that non-interactive sessions need — first-use consent prompts that wait for a
  TTY never resolve under a gateway or cron session, so without the auto-accept key
  the hook is registered and never called.
- **Name the host and the file in the first line, and say it goes into an editor.** A
  bare block in a chat that has been SSH'd into a remote host gets pasted into that
  shell, where every line becomes a failed command. State which machine, the absolute
  path, and the editor invocation.
- **Give a paste-safe verify command and a restore command.** Prove the YAML parses as
  a unit with the surrounding keys before handing it over, and name the exact
  interpreter — a `yaml`-less default `python3` fails with an import error that reads
  like a broken config.

