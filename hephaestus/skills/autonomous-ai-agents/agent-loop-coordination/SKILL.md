---
name: agent-loop-coordination
description: Feed an existing agent loop; don't do its work yourself.
version: 1.0.0
author: hermes-curator
license: MIT
metadata:
  hermes:
    tags: [agents, orchestration, coordination, dispatch, multi-agent]
    related_skills: [agent-guardrail-verification, kanban-orchestrator]
---

# Coordinating an established agent loop

## When to Use

Load this when a project already HAS an agent loop — a defined unit of work (goal,
ticket, card), roles that consume it (leader, worker, reviewer), and a place reports
land — and your role is to feed and read that loop rather than to be another worker in
it. If the system has no loop and you are building the fan-out yourself, that is a
different job.

The governing question every turn: **is this work the loop's unit of work, and did I
send it through the loop?**

## The failure this skill exists to prevent

A coordinator with shell access and root on the host can do almost any task faster by
hand than by dispatching it. Every individual shortcut looks justified — it is small,
it is urgent, the loop has overhead. The accumulated result is a session where the
coordinator edited production files, graded its own work, and produced no goal, no
reviewer pass, and no report, while the loop it was hired to operate sat idle.

The tell is retrospective and reliable: **at the end of the session, is there a durable
artifact in the system's own format?** If the only record is the chat transcript, the
work happened outside the loop no matter how good it was.

Capability is not authority. Having root does not make hand-execution the right path;
it only removes the error message that would have stopped you.

**A live tell, available before the damage: you are archiving state, building a patched
artifact, and diffing it at the shell.** That sequence IS a unit of work's task list
being executed in the chat instead of written down, and it appears most readily right
after a genuine diagnostic win, when the fix feels like the obvious next keystroke.
Having proven the mechanism makes the case for DISPATCHING it; it does not make you the
executor. Stop at the archive step and write the unit — the proof you just produced
becomes its positive control, so nothing is wasted.

**Owner impatience is not authorisation to bypass the loop.** "Just go to prod" grants
the CHANGE, not the route, and a hand-made production write still arrives with no
reviewer, no journal line, no rollback gate and no criterion that could have failed it.
Dispatch it and say that is what you are doing.

## Procedure

### 0. Load the governing skill and read the system's state BEFORE the first tool call

Skills are passive: they bind only once loaded, so a coordinator that loads the loop's
governing skill after it has already started working has made every decision the skill
exists to govern while unbound. The measured shape of this failure is a multi-hour
session of hand-executed work, self-graded, with no unit of work written — followed by
loading the skill and discovering the role boundary it states plainly on the first page.

So, in this order, before any other tool call:

1. Load the skill that defines this loop and the owner's working agreement. Treat a
   session that has not loaded them as not yet started.
2. Run the system's own state-gathering script if one exists. These scripts exist
   precisely because the same state otherwise gets re-derived by hand a dozen times in
   one session; reading the world with a script costs no inference.
2a. **List the helper-script directory before diagnosing any capability as missing.**
   A coordinator's recollection of what it can do decays faster than the filesystem
   does, so "I have no way to read that mailbox / reach that surface" is a claim about
   memory, not about the host. Measured cost of skipping it: a credential was
   rediscovered from scratch and a second wrapper written for a working tool that had
   sat in the scripts directory for days, plus two needless interruptions of the owner
   for values the agent could already fetch. `ls` on the scripts dir is one call and
   settles it.
3. Check whether any enforcement the loop relies on is a MECHANISM or merely a rule —
   see the hook-existence check below. A gate you must remember to run is a rule, and
   rules do not survive a long session.

When the owner asks why you deviated, the answer is an audit of what you did outside the
loop, not a reassurance — and the durable fix is wiring, not resolve.

### 1. Read the loop's own format before writing anything for it

Find the skill, template or existing instance that defines the unit of work and copy
its structure. Check the literal filename on disk — a system may use `GOAL` where the
documentation says `GOAL.md`, and a file written under the wrong name is invisible to
the role that looks for it.

The gate sequence a written unit must pass (format linter, constitution/executor gate,
write-surface map), how to write criteria that can close, and the two misdiagnoses that
send work back to the owner needlessly are in `references/unit-of-work-gates.md`.

### 1a. Search the unit-of-work tree for an existing unit before writing a new one

Grep the goal/ticket tree for the surface, identifier or archetype you are about to
work on, and check each hit for whether it ever ran (a unit directory holding only the
spec and no report never dispatched). Mature loops accumulate written-but-never-
dispatched units, so the task in front of you may already be specified — including the
owner's own constraints on how it must be done — and hand-executing it both duplicates
the spec and discards those constraints. A loop with dozens of units and no live role is
not an empty queue; it is an unread one.

### 2. Write the unit of work; do not write the plan

A mature loop's roles are designed to plan, decompose and dispatch from a goal. Supply
the outcome, acceptance criteria, authority, budget, out-of-scope and pointers — then
stop. Specifying the task breakdown steals the leader's job and encodes your own blind
spots as instructions.

What belongs in the unit of work:

- **Acceptance criteria that can each fail.** A criterion that cannot fail is worse
  than no criterion.
- **Pointers, never machine values.** Name the report, the card, the path. The worker
  measures the numbers; a carried figure in a goal becomes a false premise baked into
  the criteria.
- **Your own prior findings marked "in evidence, not in authority".** A coordinator's
  hand-measured verdicts are a claim to check like any other, and the goal should say
  the worker's measurement wins on conflict.
- **An explicit statement when the goal grades work you already did.** Retrofitting
  review onto an unreviewed change is legitimate; hiding that it is a retrofit is not.

### 3. Verify the artifact landed before dispatching

Re-read the file from the host and compare its hash to your local copy. A copy step
that reports success can still have written nothing.

### 4. Check the WIP limit — and believe it

Most loops define one unit in flight. Before dispatch, confirm nothing else is running.

When counting live processes over SSH, a naive `ps | grep -c <name>` counts the grep
itself and any shell wrapper carrying the name in its command line; use a bracketed
pattern and exclude wrappers, then sanity-check a zero and a one against the full
process line rather than the count alone.

### 5. Dispatch, and confirm a real process exists

Run the role non-interactively with working directory and HOME set explicitly.

**Call the system's own dispatcher; do not compose the invocation, even from its text.**
Grep the host for the existing dispatch script and INVOKE it, changing only the unit
identifier. A hand-composed command carries flags the runtime may refuse under the
privilege level the loop actually runs at, and such a refusal costs a full dispatch cycle
while looking like a loop problem. The proven line is on disk; find it before inventing
one.

Two things a hand-rolled launch silently drops, both measured:

- **The runtime-tuning environment variables the dispatcher exports.** One of these
  commonly governs how long the parent waits on background children; without it the
  runtime stops its own sub-agents a few minutes after the parent's last turn, mid-task,
  reporting it as a routine cleanup. The unit then dies with partial evidence on disk and
  no failure anywhere — attributable to the launcher, not to the loop. Diff your
  invocation's environment against the dispatcher's `env` assignments before using it.
- **The dispatcher's own refusals.** It encodes the WIP limit, the unit-file existence
  check and the post-launch liveness probe. Bypassing it bypasses those, so two roles can
  run on one surface — and the integrity windows they quarantine are the proof the limit
  was right. When it refuses your dispatch, that is the gate working; queue the unit and
  say so rather than launching around it.

**Where the dispatcher and the linter disagree on the unit's filename, fix the
dispatcher.** A loop whose documentation mandates one name while its launcher tests for
the legacy one makes every correctly-named new unit undispatchable, and the error reads
as a missing unit rather than a stale check. Accept both names in the launcher, then
confirm a nonexistent unit still refuses — widening an existence test is one keystroke
from removing it.

**Redirections are evaluated by the caller's shell, not by the privileged command.**
A line shaped `sudo cmd > /root/somewhere.log` fails with permission denied on the
redirect while the dispatch itself never starts — and the wrapper's exit code can still
look fine. Put the whole thing, redirect included, inside the privileged shell, then
confirm an actual process for the role is alive before reporting a dispatch.

**The same rule governs a leading `cd` and any glob.** `cd /root && sudo -n cmd` runs
the `cd` as the unprivileged caller, so it fails on a directory only root can enter and
the dispatch never happens; a `*` expands in the caller's context too, matching nothing
and silently passing a literal. Both can still report success. Everything that needs the
privilege — cd, redirect, glob — goes INSIDE the privileged shell
(`sudo -n bash -lc 'cd /root && ... > /root/out 2>&1'`).

### 5b. Judge a running role's liveness from the LOOP's record, not its stdout log

A dispatched role's console log is written at turn boundaries, so it goes quiet for the
whole duration of any long tool call — a baseline snapshot, a large scan, a slow query —
while the role is working normally. Reading that silence as a stall is a false negative
with a high cost: the next step is usually to kill or re-dispatch a healthy run, or to
take its work back by hand.

Check the artifacts the loop itself writes, in this order, before concluding anything:

1. the journal or record the role appends to — compare its newest line's timestamp to now;
2. the evidence directory's mtimes, and whether the file being written parses as complete;
3. the process table, for the role and its children.

Two readings that disagree mean the instrument is wrong, not that the system is strange:
a log line claiming a baseline is "still being written" beside a complete, parseable
baseline file and a journal entry minutes NEWER than the log means the log is stale.
Quote the journal.

State which of the three you checked. "No process" derived from a log file is a claim
about the log.

### 5a. Count the dispatch's real wall time against the orchestrator's timeout

A dispatch that succeeds today at 90% of its timeout budget is a scheduled failure. Time
the run and report the margin, not just the exit code — and name what makes the slow part
grow, because that is the quantity to watch.

### 6. Read the report; carry the questions and gates back

The coordinator's deliverable is the loop's output plus the decisions it surfaced — not
a summary of work the user has already seen. Bring gates and questions verbatim enough
to be actionable, with the recommended option first and its cost.

## Parallelism is a capability, not a default

When asked to run as many units as possible, the honest answer usually depends on
machinery that may not exist yet. Check for it before promising fan-out:

- **Resource locks.** Without them, concurrent workers collide on shared state; a git
  index is the classic one.
- **Per-unit isolation.** Separate worktrees or scratch areas.
- **Integrity checks that can tell units apart.** This is the one that bites. A
  tripwire or baseline-diff that brackets a unit of work sees *another unit's writes*
  as tampering, trips, and invalidates the batch. The limit is not host capacity; it is
  that each unit's own verification cannot distinguish a sibling from an intruder.

Read-only units on disjoint surfaces are the safe exception, and even they trip a
shared-window integrity check. When the ceiling is 1, say so with the mechanism, and
name the unbuilt component that would raise it — that converts "no" into a roadmap.

Host load and free RAM are the least likely constraint. Do not cite them as the reason
for a low parallelism number when the real reason is missing isolation.

### Find the BINDING constraint before changing any configured cap

When the owner questions a concurrency limit, four candidate ceilings exist and they are
routinely confused. Measure each; the configured one is rarely the real one:

1. **The provider's rate limit.** Check it from the traffic the loop already produced
   rather than assuming — and count structured error fields, never a bare status number,
   which matches every id containing those digits (the `verifying-measurements` skill
   covers this under action-versus-mention). Measured: zero real
   throttling events across 1507 sessions, so the provider was not the constraint at all
   and raising or lowering the loop's cap on that theory would have been theatre.
2. **The runtime's configured concurrency**, which may be an order of magnitude above the
   loop's own cap and therefore not binding either.
3. **The orchestrator's per-dispatch timeout, minus what its own pre-flight consumes.**
   This is usually the true ceiling and the one nobody states. An integrity or cap check
   that walks accumulated state costs more as the system is used, so headroom shrinks
   with every unit ever run; measure the phase and quote the margin.
4. **Output validity.** Concurrency that produces quarantined or unattributable results
   has a throughput of zero regardless of how many units start.

**Diagnose the observed peak, not the documented cap.** Reconstruct real concurrency by
sweeping session timestamps for overlap. A loop configured for 3 that has demonstrably
run 5 at once without provider failure tells you the cap is not what is holding the
system back.

**Do not infer a safe number from a past failure without resolving its cause.** A batch
that lost its reviews at concurrency 3 is evidence about the integrity check's inability
to attribute writes, not evidence that 3 is too many — those imply different fixes, and
recommending a lower count treats a detector defect as a capacity law. The honest verdict
is **UNMEASURED above N**, with the detector fix named as the prerequisite.

The useful recommendation is therefore rarely a number. It is: make the pre-flight cheap,
fix attribution, then re-measure. Say that instead of lowering the cap.


## A loop that cannot receive a DECISION cannot close a goal

When a majority of a loop's units sit in a held state, the usual diagnosis is that the
workers are failing. Measure before believing it: the common cause is that units stop on
decisions only the owner can make, and **no channel exists to deliver the answer back**.

The mechanism, measured on a mature loop: 67 of 122 units held, 30 of those waiting on an
owner decision, 30 older than a week, and exactly ONE decision file written in the loop's
entire history. A worker finished, wrote `VERDICT HELD ... needs <owner>` into its report,
and stopped. That report was the only channel, and the owner never opened that directory.
Meanwhile the dispatcher's prompt was the bare string `"Run goal <ID>"`, so a decision
file sitting on disk beside the report was **invisible to the role that needed it**.

The second-order cost is the expensive one: the work does not stop, it migrates. Each time
a held unit's outcome was needed, the coordinator did it by hand rather than queue unit
#68 — which is how hand-executed production writes accumulate in a system whose loop looks
merely idle.

**Build the channel before writing units that depend on it.** A unit that ends held just
becomes the next number and changes nothing. The channel needs four parts:

1. **A conventional path** the role reads, beside the report (e.g. `RULING.md` in the
   unit's directory).
2. **A resume prompt that NAMES the file**, because a role told only to "run" re-reads the
   spec and redoes finished work. Say: read the decision file FIRST, treat it as
   authoritative where it differs from the spec, and continue from the gates the previous
   report named rather than repeating satisfied criteria.
3. **The decision file's MTIME in the prompt**, plus an instruction to compare it against
   the role's own last report and stop if the decision predates the gate it is held on.
   Without this a stale answer gets applied to a newer question and a whole dispatch is
   spent proving the answer does not fit.
4. **One matcher for both verbs.** Duplicate-guard, concurrency-cap and watcher code that
   greps for the dispatch verb will be blind to a resume, so the cap stops working and two
   roles run on one surface. Unify on a single pattern matching run and resume alike.

Two detection pitfalls, both measured:

- **Scan the first ~15 lines of a report for the held verdict, not line 1.** Roles put a
  markdown title first and the verdict on line 3; a line-1 check silently ignores the
  decision for every report of that shape.
- **Bound that scan so a report MENTIONING a held peer does not trigger a false resume.**
  Require the verdict keyword within a few characters of its value.

Carry the held unit's gates into chat where the owner actually reads, with the recommended
option first and its cost. A held report is not a question asked.

## A coordinator DECISION can be the thing that is wrong

Decisions are authoritative on CHOICES: which option, what budget, what is acceptable.
They are not authoritative on FACTS. A decision file that asserts a fact the record
contradicts must be refused by the role, which records both readings and leaves the
question open rather than writing the coordinator's version.

Measured: four of six decisions written in one batch were wrong, every one because they
were composed from the unit's own report without reading the system journal underneath it.
The four failure shapes are worth recognising individually:

- **Attribution from time correlation.** A write was attributed to the unit that was
  "working on that surface at that minute". Its journal had zero write lines and its last
  line predated the write by four minutes. **Time correlation is not attribution** — a
  decision asserting WHO did something must cite the instrument that attributes it (an
  audit trail, an API key, a journal line), never a nearby timestamp.
- **Declaring a shipped decision undecided.** Two questions were marked DEFERRED with
  "leave the staged text staged". The owner had ruled both eleven days earlier, the text
  shipped to the live registry twelve minutes after that ruling, and the row had since
  moved forward several versions. Nineteen journal lines for that unit existed, unread.
- **Authorising a deploy that already happened.** An ordered deploy was authorised whose
  steps had shipped ten days before, of a version superseded twice since. Executing it
  would have overwritten live config with a stale payload.
- **Authorising a publish without scanning its content.** See the push-authorisation rule
  below.

**Before writing any decision file:**

    grep -a "<UNIT-ID>" <journal path>        # read EVERY line

Look specifically for owner-ruling lines, write/SQL lines and deploy lines. If a decision
is already journaled, the file RECORDS it with its original date and does not re-decide it.
Then check the live state of whatever the decision touches — a held unit's report
describes the surface as it was when the unit stopped, which may be weeks stale.

Further rules this earned:

- **A held unit whose target has since moved version is a stale recommendation, and
  nothing marks it so.** When resuming, re-read the live version and compare it to what
  the report assumed.
- **"Do not re-measure" is a budget instruction, not a gag.** If one cheap read would
  settle a fact the decision got wrong, name it as an option with its cost.
- **Check the journal for every unit still QUEUED, not only the one in front of you.** The
  one bad decision caught before it executed was found by sweeping the queue's journals
  after the first two were refused.
- **The loop refusing a coordinator decision is the channel working.** Say so plainly,
  fix the decision, and never withdraw a true earlier claim because a decision asked for
  it.

## Authorising a push authorises every commit in the RANGE

A decision that says "push this branch" publishes every commit in the range, not just the
one the unit wrote. Scan the whole range, with a control, BEFORE writing the authorisation.

Measured: a push was authorised with the instruction to stop only if a commit carried a
particular author — a deploy concern. The scan the role ran instead found a real person's
name and a private score in a code comment, introduced by an EARLIER unit's commit inside
the range. A grep across all remote refs found none carrying the line, with a control
proving the grep worked, so the push would have published it for the first time. The role
refused.

    cd <repo> && <pii/secret scanner> --range <base>^..<tip>   # rc 0 required, control must fire

- **Name the range, not the branch.** "Push the branch" hides the other commits.
- **A clean tip commit does not make a branch pushable.** Do not cherry-pick the clean
  commit as a workaround; it leaves the dirty one for whoever pushes the branch whole.
- **The remedy is removing the content from every commit in the range**, re-scanning the
  rewritten range with the control still firing, and only then re-asking.
- **A scan at the push boundary is the LAST line of defence.** Sensitive content in a
  tracked file should fail at commit time, and that gap deserves its own unit of work.

## Dispatching workers: what the coordinator owns

If the architecture says the coordinator talks to leaders and leaders dispatch workers,
dispatching workers directly is a layer violation even when it works. The symptom shows
up in the workers' own output: given a prompt instead of a unit of work, they invent
identifiers for the evidence directory they were supposed to be told, and their findings
land somewhere the loop will never look.

Before any fan-out, probe with ONE bounded instance and read its self-check. A role that
has never executed in the system's history is unproven; its first run is a measurement,
not a throwaway.

## Know what the loop can SEE before you accept its pass

Enumerate a role's verification reach before trusting its green: read the tool list in
its definition and the runtime's configured tool servers. A role granted a shell, an
HTTP client and a database client verifies through exactly those, and a role with no
browser cannot observe anything that exists only once a page has rendered.

Three defect classes are invisible to an HTTP client and a database query *at the same
time*, so a loop limited to those two reports success on all of them:

- a failure banner rendered beside the working control it contradicts, while the
  underlying row is healthy and the request returned success
- a control scrolled outside the viewport, so the click lands on nothing and no request
  is ever issued
- a control the front-end framework has disabled, which absorbs the click and discards
  it silently

So the rendered-pixel gate is the coordinator's own and cannot be delegated to a loop
that lacks eyes. That is not a layer violation; it is the division the tool grants force.
Delegate the work and the HTTP/SQL proof, then open the page yourself once, at the end,
on success.

**Audit whether the gate is actually running, because it decays to zero silently.** It is
the last step of a long session, it is owed by the coordinator rather than by any role,
and nothing exits non-zero when it is skipped. Grep the recent units' reports for either
of the two permitted lines — rendered evidence with paths, or an explicit
not-applicable naming what changed instead — and count. Measured: zero of ten consecutive
units carried either, including two whose own text read "PASS, shipped, not proven in a
browser" and one whose user-visible claim rested on reading source rather than loading
the page.

**The mechanism is the unit text, not coordinator discipline.** A unit written with no
visual criterion will never produce visual evidence, so a loop that cannot see is only
half the cause — the other half is a spec that never asked. When the change touches a
rendered surface, write the criterion into the unit naming the element and requiring a
negative control, and keep the pixel pass for yourself at delivery.

The inverse error costs more: do not hand-execute the work in order to reach the
screenshot. Dispatch it, let the role prove its change over the surfaces it can reach,
and spend your own browser pass on confirmation rather than on production.

The method for that browser pass — route discovery, framework-controlled inputs,
below-the-fold clicks, mid-batch session expiry, and proving a UI write in the database
with a control — is in `references/driving-a-web-ui.md`.

**When a role's gate blocks only on a credential you legitimately hold, satisfy it
yourself instead of parking the goal.** A loop forbidden from minting signatures or
holding a session will correctly refuse the one step that needs an authenticated human,
and that refusal is not a request for the owner by default — it is a request for whoever
holds the credential. Check whether the coordinator already has the sanctioned path (a
standing login helper, an existing session) before escalating; reserve escalation for
decisions, not for clicks.

When the blindness itself is the problem, write a unit of work to close it instead of
absorbing it every session — and make a **negative control** an acceptance criterion:
the new verifier must be shown REPORTING FAILURE against a known-absent element or a
deliberately broken selector. A capability goal whose criteria only ever observe success
ships a gate that cannot fail. Point the goal at any rig already on the host; partial
rigs are common, and the missing piece is usually authentication rather than the browser
itself, so specify reuse of the existing login mechanism explicitly.

## A safety classifier denying an AUTHORISED action is an executor problem, not a decision problem

A runtime-side classifier sits between a role and its tool calls and can deny an action
the owner has already approved in writing. The decision file is then correct, the role is
correct to stop, and nothing is wrong with the unit of work — so re-dispatching it a third
time produces the identical denial and burns a cycle.

Stop after the second identical denial at the same gate. Then separate the two questions,
because the owner has already answered one of them: the DECISION stands, the EXECUTOR
changed. Put that to them as a new question naming the three routes — you perform it by
hand, the owner performs it, or a unit of work finds a sanctioned route first — with the
cost of each. Re-asking an answered question is noise; reporting that the approved actor
cannot act is not.

**The denial's real cost is migration, not the block.** Each denial hands the work to
whoever is not gated, which is usually the coordinator, which is how unjournalled
production writes accumulate in a system whose loop looks merely idle. Count denials
across the session and treat a recurring one as its own unit of work: census them from the
record with their verbatim reasons, determine what the classifier keys on from events
already logged, and distinguish the LOCAL guard (yours, auditable) from the runtime-side
classifier (opaque, not configurable by you). Conflating those two wastes the goal.

Two hard rules for that unit: it diagnoses and proposes only, touching no guard, settings
file or permission; and it never rewords a previously denied command to see whether the
new spelling passes, because **testing whether a denial can be bypassed IS the bypass**.
A measurement that would require it is reported as CANNOT DETERMINE with its cost named.
Include "accept that this class of write is always the owner's hands, and close the
JOURNALLING gap instead" as a genuine candidate rather than a strawman — the measured harm
in the incident that motivates this is unjournalled writes, not writes.

## A role can find the hazard your decision missed — then the criterion is UNPROVEN, not dropped

Acceptance criteria for an error path are the ones most likely to be unsatisfiable, because
error paths are commonly wired to notification. Before writing a criterion that requires a
failure run on a live surface, read the target's error-handler binding and that handler's
nodes: an error workflow that fans out to a chat channel or mailbox turns every proof run
into a message to a human, which standing limits forbid. The role will refuse, correctly,
after you have already set a clock running.

When it does refuse: do not loosen the limit, and do not quietly delete the criterion.
Record it **UNPROVEN with the reason** — "the only available proof posts to a human
channel" — and state what IS proven instead (the same path exercised in the lower
environment, byte-identical payload). An honest unproven survives review; a dropped
criterion reads as a pass. Then carry the structural finding out as its own item: if no
error path on that surface can ever be proven under current wiring, that is a defect in
how proof criteria are written for it, needing a non-messaging proof route.

The same applies to a hazard the role reports in passing, such as a lock row written with
a TTL and never released on the error branch. Card it by name in the close rather than
fixing it inside the unit whose budget is spent.

## A worker's refusal is a result, not a failure

When a dispatched role stops and asks rather than proceeding, read it closely before
treating it as a problem. A well-built loop refuses on exactly the conditions worth
refusing on, and its refusal frequently identifies coordinator errors:

- an input path named in the goal that does not exist on the host
- a concurrency violation the coordinator created
- a side effect the coordinator's unreviewed change would cause on close, such as an
  unpushed commit riding out with the next legitimate push

Fix the cause and re-dispatch. Do not loosen the goal to make the refusal go away.

## When asked for a new rule, search for it first — it is usually already written

After a recurring mistake the natural request is "write a skill for that". Grep the
loop's skills, role definitions and tooling for the rule BEFORE authoring anything. The
common finding is that the rule already exists, stated in more than one document, and
nothing executes it — so a new artifact becomes the third unenforced copy and changes
nothing about the behaviour.

    grep -rliE '<rule keywords>' <skills dir>/*/SKILL.md <roles dir>/*
    grep -rnE  '<rule keywords>' <tooling dir>/* <hooks dir>/*

Then ask the separating question: **does anything exit non-zero when the rule is
violated?** Recommending against the artifact the owner asked for, with the grep as
evidence and the mechanism gap named, is the useful answer. Say which instrument you
checked, because the obvious candidate is often the wrong one — a tool that only
TRANSMITS a report cannot gate the verdict inside it, so read the tool before proposing
to patch it.

A second shape worth naming: a rule can be unenforceable **by its own design**. Where the
procedure says the loop may not perform the closing step (merge, push, delete, deploy)
and must print it for a human, that step depends on a human action that may never come —
so the drift the rule forbids accumulates while every actor follows the rule. Prose
cannot fix that. Either the closing step gets delegated, or a check must surface the
backlog it creates at the start of every run.

## Surface slow drift at the START of a run, not weeks later

The cheapest mechanism for accumulation (unmerged branches, unclosed windows, unscored
records, stale rows) is one line added to the preflight the loop already runs. Reporting
is enough; it need not block, and a status tool should not be given a blocking mechanism
it does not have. What makes such a counter trustworthy:

- **Exclude the states that are legitimately open, and derive the exclusions from the
  machine** rather than a list you maintain. For branches that means checked-out
  worktrees (`git worktree list --porcelain | awk '/^branch /{print $2}'`) plus the
  human keep-list parsed from its own document. A counter missing either will instruct a
  future run to destroy protected work — measured: a first draft flagged a branch that
  was checked out in an active worktree, which the loop's own rules forbid deleting.
- **Name the actionable count distinctly from the context counts.** One field means "act
  on these"; the rest are orientation. A single blended number gets argued with, then
  ignored.
- **Prove it in both directions before installing**, using a throwaway fixture: one case
  it must flag, one it must call OK. A counter that cannot report the problem is
  decoration.
- **Build the fixture with production's own defaults.** A fresh scratch repo takes
  whatever default branch name local git is configured for, so an exclusion list naming
  only production's default lets that name through and inflates the count. The symptom is
  a control reporting one more item than you planted — debug that discrepancy rather than
  patching logic that is already correct.
- **Patch the live tool AND its source-of-truth copy in the kit**, then confirm both emit
  the same line, or the next install silently reverts it.

Running the counter immediately reframes the problem: a surface you assumed was drifting
may be clean while a different one holds all the debt. Quote the measured split rather
than the assumption you arrived with.

## Improving the loop means editing what the AGENTS read

When the owner asks for improvements "to the loop" after a session that produced hard-won
lessons, the deliverable is a change to the standing instructions every dispatched role
receives — not new coordinator-side tooling. These are different surfaces and only one of
them was asked for.

The reliable check is mtime. List the agent-facing files (the goal preamble or equivalent
standing brief, the role definitions, the repo-level agent instructions) with their
modification times, and compare against today. Files dated before this session were not
improved, however much was built elsewhere. Convenience tooling the coordinator calls is
worth building and must be reported as what it is: it speeds up one actor, the one that
was already fastest.

**Verify the standing brief is DELIVERED, not merely written.** A brief that reaches
agents "by reference" reaches only the units whose authors remembered to include it.
Count it: grep the whole unit-of-work tree for the brief's filename and report the
fraction, with a control proving the grep matches. One brief asserting in its own second
line that every unit must include it was referenced by under a fifth of them, with no
dispatcher injection and no role file mentioning it — so each hard-won rule in it was
advisory for most runs. Convention is not a mechanism; propose dispatcher injection or a
leader-side refusal of any unit that omits the brief.

**Read the standing brief before changing the system it governs, because its rules bind
the coordinator too.** It is the densest statement of the host's traps and prohibitions
and it is cheap to read. A coordinator that never opened it broke one of its explicit
rules twice in the same session — an export command the brief forbids because it writes
into a tracked git tree — and then had to clean up paths the rule existed to prevent.
When you do violate one, fix the mess, and annotate the rule with the fact that it was
broken rather than only restating it: a rule with an observed violation beside it is read
differently from one more imperative.

**Audit the brief's factual claims against the host whenever you edit it, and fix the
stale ones in place.** A standing brief accumulates assertions about which tools exist
and what they do, and those decay as the host changes; one claimed a utility was absent
which had been installed days earlier, which teaches every agent to work around a tool
they have. Check each named tool and path, then correct the claim rather than appending a
note under it.

**Write each new rule as the generalisable form plus its mechanism, not as the incident.**
The brief is read by every role on every run, so a narrative costs tokens forever. State
the rule, one clause of why, and the measured consequence that makes it credible.

Where the programme keeps re-deriving the same state or re-litigating settled decisions,
the fix is durable project memory rather than another brief edit: state probes, immutable
decision records and an external-surface note, in
`references/durable-decision-records.md`.

## An enforcement hook that is configured but absent is silently disabled

Before relying on any gate to constrain your own behaviour, confirm the hook's script
FILE exists and executes. Configuration, a consent/allowlist entry and an auto-accept
flag all record INTENT; none of them record presence. A hook whose command points at a
path that was never created registers cleanly, never fires, and leaves every matching
tool call ungated while the config reads as enforced — which is indistinguishable from
enforcement right up until someone checks.

The tells, each cheap:

- the allowlist entry carries a null script-mtime-at-approval, because there was no file
  to stamp when consent was granted
- the hook's directory does not exist at all
- the file is absent from every backup and snapshot, which distinguishes "never created"
  from "created and lost"

After confirming the file exists, execute it once against a payload it must refuse. A
configured-and-present hook can still fail open; only a refusal you watched is evidence.

**Write the hook before relying on the gate it implements, and have the OWNER install it
where the runtime forbids self-registration.** A gate the agent can install it can also
remove, so it guards nothing; that refusal is correct, and routing around it by writing
the file through another path is the respelling-past-a-denial pattern wearing a different
tool. Hand over a paste block naming the host, the absolute path, and the editor.

## Disclose your own process violations before the results that rest on them

When you notice mid-session that you bypassed the loop, say so plainly and name every
artifact produced outside it, before presenting any of that work's conclusions. State
what would restore the process. Self-written verification stands as a measurement and
never as a review — say which one you are offering.
