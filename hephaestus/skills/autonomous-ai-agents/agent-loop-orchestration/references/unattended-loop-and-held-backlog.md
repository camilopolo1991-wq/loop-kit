# Unattended loops and the held-for-ruling backlog

Read this when: an unattended window produced no closes, a queue looks stuck on one
unit, a dispatch prompt's assertions started failing, or a pile of reports awaiting a
human decision needs clearing.

## A refusal is information; a loop that forgets it starves

A gate that correctly refuses a unit of work, combined with a scheduler that re-offers
the same unit, is a system simultaneously working perfectly and achieving nothing. Each
half passes review in isolation, which is why this survives code review.

Measured shape: a queue's "next" answer kept naming one goal that failed its
pre-dispatch gate, and the dispatcher retried it on every tick for most of the window
while dozens of other dispatchable units waited. Nothing about the gate was wrong.

- Record a gate refusal where the queue computing "next" can read it, scope the record to
  the current window, and advance to the next candidate.
- Classify every refusal as retryable (transient: a lock, a peer still running, a
  rate limit) or terminal-for-now (needs a human edit to the unit). Re-asking a terminal
  refusal inside the same window cannot succeed, so retrying it is denial of service
  against the rest of the queue.
- Clear the refusal record at window end so the unit gets a fresh attempt once a human
  has had a chance to fix it. A permanent exclusion is a different and worse bug.
- Surface blocked units in the queue's own status output. A silently skipped unit and a
  completed unit look identical from outside.

### Proving a skip actually skips

Three checks, because the first alone is satisfied by a filter that empties the list:

1. the blocked unit is no longer offered
2. blocking a unit that was NOT next leaves the answer unchanged
3. removing the record restores the original answer

Run the queue's own selftest afterwards, and read the edited file back rather than
trusting the patch tool's diff.

**Define a shell helper before its first call site.** A call to an undefined function
converts a soft stall into a hard failure at the first refusal, which is strictly worse
than the bug being fixed.

## An unattended ladder's success predicate must MEASURE, never grep the report

When a watcher runs arms back-to-back until an objective is met, its "are we done" test is
the single most dangerous line in the system: a false positive stops the work and reports
victory with the defect still live, while the human who asked for it is asleep.

Measured: a predicate grepping the closing report for `all six ... zero` FIRED on a report
whose verdict was literally "DO NOT ship" — the phrase matched a sentence describing the
controls. Prose in a report is not a result.

- Query the system's own rows for the version currently live, and compute the pass
  condition from them. A report is a claim; the rows are the measurement.
- Require a MINIMUM denominator. A freshly deployed version has zero comparable rows, and
  "zero failures over zero samples" satisfies any naive all-clear. Make insufficient-n a
  distinct non-pass state and print the per-group counts every run.
- Exclude known-contaminated subjects by name inside the predicate, not by remembering to
  exclude them at report time.
- Prove it refuses TODAY before arming. A success test that has never returned false is
  untested.

### Pre-build the next rung, and deliberately leave the last one absent

A ladder that advances to a goal with no file stalls silently. Write every rung you are
willing to pre-authorise, and let the ladder EXIT with a distinct code when the next rung
is missing — that absence is the designed stopping point where a human must see the
result, not a bug. Exiting is also the correct response to a HELD verdict: an unattended
watcher must never invent the ruling that would let it continue.

## A consolidating goal must forbid writing new goals, or the pile regrows

Where each new measurement becomes its own unit, one subject accretes units faster than
any of them closes. Measured census on a single subject: **63 units, 32 HELD, 39 of them
having each built their own harness, 136 reviewer failures and retries, and 5 units in 16
days that changed the product at all.** Nothing was broken; the machinery had become the
output.

So when consolidating, write the prohibition INTO the goal text, not into the dispatch
chat:

- Out-of-scope findings go in the REPORT as findings. The goal may not create a successor.
- Name the units it supersedes and require one journal line each, evidence left intact.
- Require it to NAME any superseded unit whose question it did not answer, rather than
  silently absorbing it. Silent absorption is how a live question becomes invisible.
- Forbid a HELD verdict explicitly and say what to do instead: make the recommended call,
  record the assumption, continue. A consolidation that ends held has added a 64th unit.

Before writing the consolidated goal, fan the existing units out across parallel readers
with an output schema (see the backlog-clearing procedure below) and feed the already
established facts INTO each reader's context, so each one can report "this unit merely
re-derives X" instead of re-reading the whole subject. That review overturned two of the
consolidation's own premises before it was dispatched, which is far cheaper than
discovering it mid-run.

## Verifying an unattended window is actually armed

"Is the shift scheduled?" has three independent answers and the wrong instrument gives a
confident no. Check all three before reporting the loop idle or arming a second copy:

- **The scheduler's OWN job store.** An agent-runtime scheduler keeps its jobs in its own
  database, not in the system crontab, so `crontab -l` returning "no crontab for <user>"
  says nothing about whether the window is armed. List jobs through the scheduler's
  interface and read the schedule, `enabled`, and `last_run_at`.
- **The protocol's own log.** A wrapper that appends a line on every code path — including
  refusals — is the authoritative record of whether it ran. ARM / WAIT / DISARM lines with
  recent timestamps prove the window is live even when every other signal looks quiet.
- **The process table**, for whether a unit is running right now.

A heartbeat line per tick is what makes the second check possible: a silent no-op and a
never-invoked script are indistinguishable from outside, which is why the wrapper must
write before it decides anything.

### Sweep the gate across the whole pool before arming, not one tick at a time

A scheduler discovers refusals serially — one gate failure per tick, each costing a cycle.
Run the real gate binary over every never-run unit up front and count passes: knowing 19 of
21 pass tells you the window has genuine depth, and the two that fail can be fixed or
blocklisted deliberately instead of eating ticks. Drive the SAME binary the dispatcher
invokes (grep the dispatcher for the check's name) with the same input shape; a flag you
guessed at returns a uniform failure for every unit and measures nothing.

### Never forge the scheduler's state flag to force an early start

A running-flag or armed-stamp is an input to predicates written for the unattended case.
Seeding one by hand makes those predicates fire against a situation they were not written
for — commonly an "end the shift if the human is active again" branch, which clears the
flag on the very next tick. Drive the DISPATCHER directly to start the first unit through
its own gates, and let the scheduler adopt the running state once its preconditions are
genuinely met.

**Say plainly that a manual kickstart starts ONE unit.** The queue advances on later ticks
only if the scheduler's continuation predicate holds, and immediately after the human has
spoken it usually does not. Claiming the window will "keep dispatching as each leader
finishes" is a statement about a predicate you have not evaluated; read the continuation
branch and report what it will actually do, including when the window will end.

### `grep -c` already prints 0 — a `|| echo 0` fallback breaks the test

`grep -c .` prints `0` and exits **1** when nothing matches, so `$(... | grep -c . || echo 0)`
yields `0\n0` and the arithmetic test around it dies with "integer expression expected".
Strip non-digits and default instead:

```sh
N=$(cmd | grep -c . 2>/dev/null); N=${N//[^0-9]/}; N=${N:-0}
```

**Establish which DIRECTION a guard bug errs in before rating it.** This one only
misfires in the zero case, where proceeding is correct anyway, so the safety refusal
never broke — cosmetic, but it replaced the guard's reading with an error message, which
is the wrong failure to leave in a safety check. Prove both directions after fixing: a
planted running peer must still refuse, and the zero case must produce no error.

## Give every unit FOUR budget ceilings, and name the wall-time endpoints

A budget written as counts alone (writes, runs, model calls) is unbounded in the one
dimension that actually hangs. A stalled webhook or a waiting run spends no write and no
model call, so every stated ceiling stays satisfied while the unit sits forever.

Measured: a unit held in three minutes having spent nothing, because its own ticket review
failed TWICE on a missing wall time. The executor then proved the absence properly, with a
regex over the goal and ruling files plus a control showing the same regex did match an
unrelated duration phrase elsewhere, so the instrument could have found a limit if one
existed. Writing the number took one line; omitting it cost two reviews and a dispatch.

- State all four: **writes** (how many, to which surface), **runs**, **model calls** (and
  how counted), **max wall time with its START and END events named**. "Two hours, from the
  first staging write to the end of the final acceptance run" is a ceiling; "two hours" is
  a wish, because nothing says when the clock starts.
- Say explicitly that exceeding ANY ceiling stops the unit held, and state the accepted
  cost: a stall means the dependent criterion ends UNPROVEN rather than the unit waiting.
  A budget that cannot stop the work is decoration.
- **Count model calls from the thing that loops, not from the caller.** A retry node loops
  internally inside ONE node, so three attempts appear in the parent's executed-node list
  as one call. Read the retry result's own attempt counter; when it is unreadable, report
  "at most N, exact UNKNOWN" rather than a number you cannot defend.
- Only the human sets these numbers. An executor must never invent a ceiling, and holding
  to ask for a missing one is correct behaviour rather than a failure.

## Never hardcode a measured count as an invariant in a dispatch prompt

A prompt that asserts literal row counts goes stale the moment a legitimate deletion
lands. Every executor then fails its closing check for the wrong reason and reports data
loss, and the orchestrator chases a phantom incident.

- Instruct the executor to read the counters at window open and compare them against its
  own close read. Cite current figures as orientation only, and say explicitly that a
  mismatch against a written number is not evidence of loss.
- Before treating a counter gap as data loss, search the record for an authorised
  deletion and check whether the PARENT row survived. Derived rows gone while the parent
  remains is the signature of an intended void, not an accident.
- Clear yourself with the record, not with memory: group the write log by database and by
  unit, and confirm which writes were yours before asserting you did not cause the gap.
- An archive claimed in a record is not an archive until located. Search the filesystem
  for the named artifact; if the write wrapper takes no snapshots of its own, archiving
  was manual and may never have happened. Report it as UNKNOWN rather than missing, and
  never let a close inherit an unverified restore claim.

## A file-derived state model misreports work that skipped the sentinel file

A model that infers "never run" from the absence of a plan file labels a unit untouched
while its evidence directory holds hundreds of artifacts. List the directory before
believing the label, especially before dispatching that unit as fresh work.

The corollary is an opportunity, not just a hazard: that orphaned evidence is usually a
complete dataset nobody analysed. Replaying it answers the unit's question at zero model
spend, so inventory it before commissioning any run.

- Parse the archive's own filenames against the real convention, not an assumed one.
  Multi-segment arm tags and a nested payload shape each silently yield zero usable
  records, which reads as "the archive is empty" rather than "my parser is wrong". When
  every record fails to parse, print one raw file before concluding anything.
- Separate the arms before computing anything. Untagged repeats are the identical-input
  evidence; tagged records are perturbation or planted-condition runs on DIFFERENT input,
  and pooling them manufactures variance that was deliberately introduced.
- Check the archive satisfies the unit's own controls before trusting its numbers. Where
  the unit demanded every record carry its input hash and none do, grouping falls back to
  the filename convention the unit warned against: report the aggregate verdict as sound
  and the per-input attribution as filename-trusted.
- Confirm one model and one window across the records. Same model plus a single date,
  with within-day ranges equal to the overall ranges, is what licenses calling the
  variance run-to-run rather than version drift.

## A unit named for an outcome is not closed by measuring the outcome's absence

A unit called `...STAB` (a stability gate) that reports "every component fails the gate"
has produced a measurement, not a result. The name states the pass bar, so confirming the
bar is unmet is the first step of the work. Delivering that as the outcome reads as
abandoning the unit in a dead end.

- Read the unit's NAME as the pass bar. Where it names an outcome (stability, parity,
  coverage, isolation), keep going to a fix in the same session and report the defect as
  progress toward it.
- **Suspect the instrument once more before reporting an all-components-fail result.** A
  uniform failure across every component is far likelier to be one shared harness defect
  than N independent defects in the subject. Measured: all six components failed because
  the fixture stubbed four template slots; filling them from real rows fixed three
  outright with no change to the prompt or the model.
- Load the skill for the DEFECT CLASS before prescribing a remedy. Measuring a defect and
  fixing it are different bodies of knowledge, and reaching for the fix skill only after
  the measurement cost a full wrong diagnosis.
- Report partial as partial with the next lever named: which components still fail, why
  they are a different defect class, and what the next fix is. The acceptable stopping
  points are the pass bar met or a genuine human gate.

## A ruling channel nobody reads is not a question asked

Measure the backlog before assuming the loop is merely slow. A census of one mature loop:
**122 units, 67 HELD (55%), 23 PASS (19%), 27 with no report at all; 30 of the held were
waiting on a human ruling, 30 were older than seven days, and exactly ONE ruling file
existed in the entire history.**

The mechanism is structural, not an executor mistake. A leader finishes, writes
`VERDICT HELD ... needs <human>` into its report file, and stops. If that file lives in a
directory the human never opens, the ruling never arrives, the unit never closes, and the
next time the same work is needed the orchestrator does it BY HAND rather than queueing
unit #68. The loop keeps passing review while quietly routing its hardest work around
itself.

The tell is an orchestrator that has started executing gated operations personally and
has stopped mentioning the loop. That migration is invisible in the loop's own metrics,
because a unit nobody dispatched never fails.

- **Classify held units by WHY before counting them as a backlog.** Waiting-on-a-ruling,
  refused-by-the-executor's-permission-layer, blocked-at-a-write-boundary-by-design, and
  could-not-prove-a-criterion need four different remedies. Lumping them produces a
  number with no action attached.
- **Ask the question in the channel the human actually reads, BEFORE dispatching.** When a
  unit will predictably end held on a decision only they can make, get the decision first.
  A held report is a question asked into a void.
- **Never silently substitute hand-execution for a blocked loop.** Name the block out
  loud, then ask. Doing the work by hand hides the breakage and the backlog keeps growing.
- **Fix the ruling channel before writing units that depend on it.** A unit that ends HELD
  just becomes the next number and changes nothing.
- An executor's own permission classifier can refuse a gated operation **even with written
  approval present in the unit's files**, sometimes with no stated reason. Count those
  separately: they are a tooling problem, not an authorisation problem, and no amount of
  clearer approval text fixes them.

### Hand-executed work leaves no audit trail unless you write one

The loop journals itself; the orchestrator does not. A gated operation performed by hand
leaves a trace of WHAT changed in the target system's own history and no trace at all of WHY
or under whose authority. The shape to look for: a long gap in the journal bounded by a
leader's `HELD, refused` line and the next unit's START line is exactly the window in which
someone did the refused work manually.

- Append a journal line for every hand-executed write, ruling and roll-up, naming the
  artifact and recording that a human rather than a leader did it.
- Correct an earlier journal line by APPENDING a correction that cites the original
  timestamp. Never overwrite; the superseded reading is part of the record.
- **Resolve "who did this" from the logs before attributing it.** The target system's audit
  table names the actor; the journal names the authority. Reading only one yields a
  confident wrong answer.
- **Confirm the journal path from config, not from memory.** A leader that reads the wrong
  path finds an empty file and reports an unexplainable gap, turning a bookkeeping miss into
  a phantom incident.

### Make the dispatcher READ the ruling, or writing one changes nothing

A ruling file sitting beside the unit's goal file is invisible unless the dispatch prompt
names it. Where the prompt is a bare `"Run goal <ID>"`, a leader re-reads the goal from
scratch, redoes work the previous report already satisfied, and can hold a second time on
the question that was just answered. The one ruling that ever worked in a 122-unit history
worked only because a human pasted its contents into a fresh prompt by hand.

Build the resume into the dispatcher:

- **Emit a RESUME prompt when a ruling exists AND the report is HELD** -- both predicates,
  not either. It must name the ruling file's path, say to read it before the goal file and
  treat it as authoritative where the two differ, and say to continue from the gates the
  previous report named rather than re-running satisfied criteria.
- **Control on the stale case:** a ruling file left behind in a unit whose report is no
  longer HELD must NOT trigger a resume, or any forgotten ruling silently re-runs a
  completed unit.
- **Update EVERY place that identifies a running leader by its prompt string.** Adding a
  second prompt form breaks the duplicate guard, the concurrency cap and the watcher all
  at once if they each match only the original wording -- so two leaders land on one unit
  and the watcher never sees either exit. Use one shared pattern matching both forms, and
  control that it does NOT match a line merely mentioning the unit id.
- **Shell-quote the task string.** A multi-word resume prompt interpolated unquoted is
  split on spaces and the executor receives only the first word.

The selftest for this is cheap and worth writing: stub the two predicates, build the
command, and assert the prompt shape for ruling-absent, ruling-plus-held, and
ruling-without-held.

### Detect the verdict wherever the executor put it, and prove the ruling is not stale

Two defects that each silently defeat the resume path. Both are cheap to cover and both
cost a wasted dispatch when missed.

- **Scan the report's HEAD for the verdict, not line 1.** Executors are inconsistent about
  placement: one writes `VERDICT: HELD` inside the title line, another writes a markdown
  title on line 1 and `VERDICT HELD:` on line 3. A line-1-only check ignored the ruling and
  sent the plain prompt, which is exactly the failure the resume path exists to prevent.
  Bound the scan to the first ~15 lines, because an unbounded scan matches a report that
  merely MENTIONS a held peer unit and marks a passing unit as held.
- **A ruling answers the gate that existed when it was written.** A unit can consume a
  ruling, act on it, and hold AGAIN on new questions. Resuming on the old file then asserts
  "the human has answered" when they have not. Put the ruling file's MTIME in the prompt and
  instruct the executor to compare it against its own last report, stopping if the ruling
  predates the open gate. A good executor will prove the staleness itself (file timestamps
  plus a `find -newer` control showing the instrument can see new files) and refuse in its
  first turn, which costs a minute instead of a full run.
- **Re-read the current report IN FULL before writing a ruling or re-dispatching.** Reading
  only the head caused one dispatch spent on an already-consumed ruling, and then missed a
  third open question sitting below the fold while answering the first two. The open gates
  are whatever the LATEST report says, never what the previous one said or what you remember
  asking.
- When an executor proposes a fix to the orchestration tooling in its report, implement it
  before re-dispatching that unit. It is the component that just paid for the defect.

### A ruling is authoritative on DECISIONS, never on FACTS

Rulings settle which option, what budget, what is acceptable. They do not settle what
happened. A ruling written from the unit's report alone produces confident answers to
questions the record already closed, and the executor is right to refuse it.

Measured across one batch of six rulings written in a single sitting, FOUR were wrong and
all four the same way: the author read the report and not the journal underneath it.

- **Attributed a write to the unit itself on time correlation**, when that unit's journal
  held zero write lines and its last line PREDATED the write. Time correlation is not
  attribution. A ruling asserting WHO or WHAT did something must cite the instrument that
  attributes it (an audit row, an API key, a journal line), not a timestamp sitting nearby.
- **Declared a shipped decision undecided** ("deferred, leave the staged text staged") when
  the human had ruled it eleven days earlier and it reached the live registry twelve minutes
  after that. Nineteen journal lines for that unit existed and none were read.
- **Authorised a deploy that had already happened**, of a version superseded twice since.
  Executing it would have overwritten the current live artifact with a ten-day-old one.
- **Authorised publishing data that must never be published** (see the push rule in the
  main skill): the authorisation named an author check when the actual risk was content.

So, before writing any ruling file:

    grep the journal for the unit id, and read EVERY line

Look specifically for human-ruling lines, write lines and deploy lines. If a decision is
already journaled, the ruling RECORDS it with its original date; it does not re-decide it.
Re-verify any deploy the ruling would authorise against the live version first, because a
unit held for days describes a surface that has since moved and nothing marks its
recommendation stale.

**When the record contradicts a ruling, the executor records both readings side by side and
leaves the question open.** That refusal is the channel working, not a malfunction: say so
plainly and fix the ruling. Never withdraw a true earlier claim because a ruling asked for
it. "Do not re-measure" is a budget instruction, not a gag -- if one cheap read would settle
a fact the ruling got wrong, name it as an option with its cost.

**When a ruling's letter is narrower than its evident purpose, act on the purpose and say in
the report that you widened it.** A remedy aimed at a scanner's MATCH rather than at the
underlying risk passes a clean scan while leaving the risk in place.

### A held unit can leave a FALSE claim on disk

An executor that cannot complete its record update may still have written part of it. One
unit wrote `<UNIT> CLOSED PASS` into the shared state file, then had its own correction of
that line refused by its permission classifier, and held. The record then asserted a close
that had not happened, and the unit could not fix it.

- After any held report mentioning a blocked record update, read the shared state file and
  check what actually landed. Grep for the unit id rather than trusting the report's summary.
- Check whether the false content was COMMITTED. Uncommitted means nothing was published,
  which changes the urgency but not the need to fix it.
- The orchestrator fixes it, because this is the blocked path rather than a routing-around.
  Edit by content with an occurrence assert, verify with a positive check, a negative check
  and an untouched control line, and back the file up first.
- The executor reporting its own overstated line is correct behaviour. Say so. Retrying the
  denied edit, or rewording it to pass the classifier, would have been the failure.

### Use the free slot. A sequential queue under a cap of two is half idle.

Running units one at a time while the concurrency cap allows two wastes the window, and the
waste is invisible because every unit still closes. Measured: six ruling-only resumes run
serially for forty minutes after the unit holding the second slot had already finished.

- Recompute capacity when a peer exits, not only at queue start.
- Ruling-only resumes and read-only audits are the cheapest things to parallelise: they hold
  no write surface and contend for nothing.
- Partition by WRITE SURFACE, not by unit count. Two units that both commit to the same
  record repo will sweep each other's staged hunks into one commit, so those stay serial
  however idle the slot looks.

## Clearing a backlog of units held for a human ruling

Once dispatch works, the throughput limit becomes the pile awaiting a decision, not
capacity. Procedure:

1. Stage every report where it can be read without privilege, one file per unit.
2. Fan the reading out across parallel subagents, roughly a dozen reports each, with an
   output schema. Require the report's OWN wording as the evidence for each blocker, plus
   a classification and a recommendation. Forbid identity data; require truncated ids.
3. Classify each: DECISION (a human must choose), BLOCKED-ON-EXTERNAL (waiting on a third
   party or a credential), CLOSEABLE (evidence complete, only the verdict needs flipping),
   STALE (the blocker describes a state that has since changed).
4. **Classify from the JOURNAL, never from the report headline.** A unit whose report
   headline states no gate very often has a log line naming the exact decision it waits
   on -- measured: of 34 units classified "no explicit gate" by headline, 7 had journal
   entries reading `HELD at <human> gate`, naming a branch push, a spend approval, or a
   re-enable decision. Headline-only triage buries live questions in the discard pile,
   and the discard is irreversible in a way the misclassification is not. Search the log
   for each unit id before proposing to archive it.
5. Separate the CLOSEABLE ones first. A report stating no gates remain needs a verdict
   flip, not a question.
6. **CLUSTER the remainder before asking anything.** Dozens of units typically ask a
   handful of distinct questions: whether peer writes count as noise, what the default is
   after the retry limit is hit, attribution for unexplained writes, a value judgement
   needing a named owner, authorisation for a measurement route. Relaying each unit's
   question individually spends the scarcest resource in the system on duplicates.
   **Most held reports already contain their own recommendation with its cost** -- in one
   census, 27 of the 34 units that stated a gate did. Those need the word yes, not
   analysis; present them as a batch to accept or decline rather than re-deriving each.
7. Verify the load-bearing claims yourself before asking. Reports flag their own
   staleness and several blockers dissolve on measurement: a named blocker may already be
   fixed, an alarm may trace to a disabled node or to the non-matching branch of a correct
   ternary, an install may already be partly on disk.
8. Record each answer where the executors read it, one entry per ruling, naming every
   unit it unblocks. A ruling that lives only in chat gets re-asked by the next leader.
9. Re-run the record's commit gate after writing, then commit.

**A value judgement with real-world exposure is never the agent's to make.** A fairness
target, an acceptable score-flip rate, a retention policy: route these to a named human
owner and leave the unit held rather than picking one to unblock it.
