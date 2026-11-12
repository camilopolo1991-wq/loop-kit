# Dispatching work to an autonomous executor

Depth for the SKILL.md rules "Hand work to the executor through its own wrapper",
"Capability is not completion" and "Sequencing". Read when launching, re-launching, or
answering a worker that runs outside your own turn.

## Launch through the wrapper

The wrapper's value is the parts you cannot see failing:

- **environment variables the runtime needs** — notably any ceiling that stops a worker
  from stopping its own background children. A worker that reaps its subagent mid-task
  reports as "stopped", not as "failed", so the log line naming the reason is the only
  evidence;
- **serialisation** — one worker at a time where concurrency was measured to corrupt
  integrity windows;
- **pre-flight gates** — artifact exists, prompt staged, no peer running;
- **positive confirmation** — the better wrappers poll the orchestrator's own listing
  after launch and refuse to return 0 until the unit appears there. That is the reading
  to trust, not the spawn's exit code.

Pass the prompt by FILE, not as a shell argument: a staged prompt file cannot be mangled
by quoting, and its byte count and hash are reportable.

## Two tools in one pipeline must agree on how they resolve an artifact

Where a linter mandates one filename and the dispatcher tests for another, every
correctly-named new artifact is silently undispatchable while every legacy one works —
and the failure surfaces as a flat refusal with no hint that the contract is split. When
a pipeline has a validator and a runner, read both resolvers and confirm they accept the
same set of names. Fix the one that is narrower, then prove the fix with a control: the
genuinely-missing artifact must still be refused.

The general form: any two components that locate the same object by convention are a
contract, and nothing tests a contract that was never written down.

## Answering a stopped worker

A unit that HELD on a question has exited. Writing its answer to disk is necessary and
not sufficient:

1. confirm the ruling file is on disk and byte-identical to the source;
2. scan it for secret shapes and for names, with a control pattern that must match, so a
   clean result is not just a grep looking in the wrong place;
3. re-dispatch, and name the ruling file's path IN the launch prompt — a leader does not
   discover a file it was never told about;
4. tell the re-dispatched unit which of its earlier windows were quarantined and must be
   re-measured, and that every figure in the ruling is the author's reading to be
   reproduced, not inherited.

State in the ruling which blockers are retracted and WHY, with the current reading beside
the dead one. A retraction without its measurement is just a contradiction for the next
reader to adjudicate.

## A blocker that rests on a quotation needs the source re-read

Held units commonly cite a governing rule file — a constitution, a policy, a runbook — and
the citation drifts from the file. One unit sat blocked for over a week on a prohibition
whose wording was not in the file at all; the real rule forbade a narrower object and the
adjacent line explicitly PERMITTED what the unit needed.

So: re-read the cited lines yourself and quote them in the ruling. Distinguish objects
that share a name — an environment versus a schema of the same name inside a production
database are different objects with opposite permissions, and a substring match cannot
tell them apart. Then check the permission's own CONDITIONS and carry them into the
ruling, because a grant with unmet preconditions is not a grant.

When only part of a unit's blocker list is dead, say which parts and route around the
live one rather than waiving it. A privilege-escalation refusal (a privileged executor
running code writable by a lesser uid) is correct and must be routed around by
re-deriving the measurement with vouched tools, or reported as CANNOT DETERMINE with the
instrument named — never by copying the script to a privileged path, which launders
provenance instead of establishing it.

## Porting a hunk between environments: diff the ENCLOSING declaration

Copying a verified block from one environment to another is the cheapest-looking change
and carries a specific trap: the block depends on its surroundings. A fallback block that
ASSIGNS to a variable, ported onto a target where that variable is declared `const`,
throws on every run — trading a silent wrong-value bug for a hard failure, in production,
with the patch looking byte-correct in review.

Before porting, diff the whole enclosing scope between source and target, not the hunk:
the declaration keyword, the type guard, the surrounding early returns. Port every hunk
the block depends on, in the same change. Then assert mechanically before writing:

- exactly one object matches the name you are editing;
- the anchor you insert against appears exactly once;
- the mutation actually differs from the original (`assert new != old`) — a replace whose
  search string does not match returns the input unchanged and you deploy an unpatched
  artifact that looks patched;
- the marker is present exactly once afterwards;
- a syntax check passes on the edited code in isolation;
- an object-by-object diff shows only the intended one changed, with the connection or
  wiring structure byte-identical.

Re-derive the patch from a FRESH export at execution time. A prepared file from an
earlier session describes a state that may have moved, and the whole point of the
assertions is lost if they ran against a stale base.

## Gating one unit on another unit's result

When two units write the same object, the successor must wait for the predecessor's
VERDICT, not merely for its slot. A free slot answers "is anything running", and a unit
that ended HELD or FAIL can leave its staged edits half-applied on the shared object — so
dispatching the successor into the freed slot interleaves two units' changes into one
artifact, and neither unit's evidence survives. Encode the condition as: slot free AND
predecessor closed PASS; anything else holds with the reason named, because "both goals
write this object and it may be half-applied" is a sentence a human can act on.

Build the wait on the verdict file's freshness as well as its contents (see the SKILL.md
rule on STALE as a third state), and give the watcher a distinct exit code per outcome —
dispatched, predecessor not PASS, predecessor exited without a verdict, gave up on time.
A watcher that can only succeed or hang tells you nothing about which happened.

Two construction rules for such a watcher, both learned from hangs:

- **Count liveness by the executable at the start of the command line, never by the goal
  identifier.** A loop waiting on a pattern that includes its own target's name matches
  its own command line and waits forever, reporting a queued unit as pending
  indefinitely. Prove it with two controls before arming: the counter sees a known-live
  worker, and zero live workers mention the identifier.
- **Do not create files in the peer's watched tree while it holds an integrity window.**
  This is not limited to bulk filesystem work — a single new artifact, including a goal
  file written for the NEXT unit, registers as a difference and forces the running peer
  to classify it. A well-built peer classifies it as a peer difference and continues, but
  the noise is avoidable: stage such files outside the watched root and move them in once
  the window closes.
- **Stand down competing watchers before dispatching, and never kill by command-line
  pattern.** Two watchers polling one slot race, and whichever samples first wins —
  silently reordering a priority a human just set. Have the higher-priority watcher
  terminate its peers by SCRIPT PATH (which no worker process carries) before it
  launches. Separately: a pattern kill matches the KILLING shell's own command line,
  because the pattern is in it — this terminates your own session instead of the target.
  Resolve to PIDs, filter by the executable name, then signal each PID; and expect a
  privileged worker to need a privileged signal, since an unprivileged kill against it
  fails silently and the process count stays stubbornly at one.

## The staged prompt is a SNAPSHOT; edits after launch do not reach the worker

A dispatcher stages the prompt to its own path at launch. Every edit to the source file
after that moment is invisible to the running worker, and the only tell is the staged
artifact's byte count. The expensive version of this: an instruction folded into the
prompt seconds before a queue fired was absent from the staged copy, and the worker
planned a full task list without it.

So after any launch you did not personally sequence:

- read the STAGED artifact (not your source) and grep it for the newest instruction;
- if it is missing, do NOT restart a worker that has already done real work. Write the
  instruction to the ruling file the worker reads at task boundaries and verify it lands,
  because restarting discards completed measurements to fix a text omission.

A durable artifact the worker re-reads (the goal or ruling file) CAN still be amended
mid-run; the launch prompt cannot. Prefer putting anything that might change into the
re-read artifact and keep the prompt a pointer to it.

### Prevent the race instead of detecting it

The reactive check above recovers a run; a settle guard stops the loss. When a watcher
may fire at any moment while you are still editing the goal or prompt, make the watcher
refuse to dispatch until BOTH files have been unmodified for a settle interval, and have
it log the artifact hash before launch and again after, asserting they match.

    settled() { now-mtime(goal) >= SETTLE_S && now-mtime(prompt) >= SETTLE_S; }

A dispatcher that launches a moving target produces a worker whose plan is missing
whatever you wrote in the last minute, and nothing in its output says so. Prove the
guard both ways before arming it: a just-touched file must be refused, and an old one
must pass.

## Promote the measurement harness out of per-unit scratch

Harness code written inside a unit's working directory dies with that unit's cleanup, and
the measurements it produced become unreproducible. Measured consequence of letting this
run: the lineage root of a harness reused by five successive units was deleted at a
routine goal close, leaving its descendants as base-less diffs in evidence trees, so
three completed measurement runs can no longer be reproduced at all. Meanwhile the shared
tool directory held dozens of platform wrappers and not one measurement harness.

So treat the harness as a deliverable, not a by-product:

- install it to the SHARED tool directory with a `--selftest` that exercises its controls;
- require the unit that promotes it to produce its own numbers THROUGH the installed
  tool, not through a unit-local copy, or the promotion is cosmetic;
- have it reproduce the previous units' published numbers as an acceptance condition —
  that is what proves it measures the same thing;
- when it needs a change later, change it in place and re-run the selftest.

Watch for the self-duplication tell: a unit carrying two or three near-identical copies
of its own harness in different evidence subdirectories. That is both a sign nobody owns
the tool and an active hazard — a stray cache directory created by one copy tripped an
integrity window and cost a full review round.

## An unattended loop needs a ladder that ENDS, and a stop reason it reports

A "do not stop until X is fixed" instruction is satisfied by a watcher that survives
your turn, not by promising to keep working. Build it as: poll for a free slot, read the
predecessor's verdict, dispatch the next PRE-WRITTEN unit from a fixed ladder. Then make
the ladder terminate deliberately — leave the last rung absent so that two failed arms
stop the loop and surface the finding, rather than the loop inventing a third attempt
while nobody is watching.

Every exit must log WHICH condition fired: target met, predecessor held and needs a
human ruling, ladder exhausted, deadline. A watcher that exits silently is
indistinguishable from one that crashed, and the difference decides whether work resumes.

Two construction rules specific to such a loop:

- **Resolve the success test to a measurement, not to the predecessor's prose** — see
  `probe-harness-controls.md` on gates that grep a report.
- **Verify the target is reachable before arming the stop condition.** A stop at "N
  distinct subjects" against a pool holding fewer than N is a loop that can only end on
  its deadline. Count the pool first and either restate the target in a reachable unit
  (N new observations) or say the ceiling out loud.

## One invocation's caps may be lower than the target; chain waves, never widen a cap

A tool that refuses `--cap` above its own limit makes a single launch unable to reach a
larger goal, and the watcher then reports "wave complete" far short of the target — a
success-shaped stop. Read the tool's accepted ranges from its refusal messages or
`--help` BEFORE sizing the run, then chain sized waves: wait for fires to drain, compute
`remaining = target - current`, launch `min(remaining, cap)`.

Wait for the previous wave to clear rather than overlapping. Two waves sharing one goal
counter is the measured concurrency defect — a counter read at init and never re-read let
two runners accept double the cap.

## Prefer a guard that refuses cheaply over a run that spends

When a harness offers a gate subcommand, run it before every fire batch. Observed value:
the gate halted on a fixture whose stored transcript was empty, and on a baseline
mismatch after the fixture set changed, both at zero cost — each would otherwise have
been a batch of spend producing unusable rows. A gate refusal naming the offending
fixture is the cheapest measurement available; treat a HALT as information, regenerate
the baseline for the new set, and re-gate until clean.

## Do not infer progress from a timestamp the worker WROTE

A plan or report can carry a header timestamp minutes AHEAD of the file's own mtime,
because the worker writes the time it expects to finish the section. Reading that header
as "written later than I thought, so it is mid-write" produces a false all-clear about
whether your instruction was picked up. Trust `stat` mtime for when a file changed and
the content for what it says, and never the content for when.

## Measure where the queue TERMINATES before building dispatch capacity

An autonomous shift that starts units on schedule, honours its veto window, and closes
cleanly can still produce nothing: if units are written to stop at a question, every
successful dispatch adds one more item to the pile waiting on a human. Throughput at the
front of the queue is not throughput.

Before investing in dispatch capacity, count the TERMINAL states: how many units closed,
how many held, and what the held ones wait on. When the held pile grows faster than the
closed pile, the constraint is downstream and more dispatch makes it worse. The fix is to
drain the held pile first — see the SKILL.md rules on held items whose own reports contain
their answers, and on blockers that outlive their conditions.

Report dispatch and closure as separate numbers. "Six units dispatched" and "zero closed"
belong in the same sentence, because the first alone reads as a productive night.
