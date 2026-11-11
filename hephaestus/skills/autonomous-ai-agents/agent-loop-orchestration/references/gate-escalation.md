# Enumerating and relaying gates

A gate is a decision only a human can make. Goals stop at them constantly, and
gates left scattered one-per-report are usually the real throttle on delivery —
more than runtime, more than quota.

## Measure the constraint before proposing more throughput

Asked "how long" or "should we run overnight", count what stops goals rather than
estimating a duration:

- goals whose report verdict is `HELD` or `BLOCKED`
- gate entries in the loop's journal with no later ruling
- plan rows still `TODO` / `RUNNING` / `RETRY` / `GATE`
- against: quota deaths, and FAIL / quarantine lines (rework)

A representative reading from a mature loop: 21 goals, 8 ended HELD on a human
decision, ~20 open gate items, versus 6 quota deaths. That shape means added
runtime mostly enlarges the backlog waiting on the owner, while rework repeats at
full model price. Report the census and the top unblocking gates; ticket count is
never a duration, and neither is elapsed wall time.

## Extracting gates across every goal

Report headings are not uniform. Matching only one phrase such as `Gates waiting`
finds a minority of them. Widen to headings naming *gate*, *waiting*, the owner's
name, *decision*, or *open question*, and fall back to lines containing decision
verbs (*authorise*, *ruling*, *your call*, *decide*). Read the first few lines of
each report too — the lead sentence often states the decision outright.

```python
for d in sorted(glob.glob(f"{GOALS}/*/")):
    body = open(os.path.join(d, "report.md"), errors="replace").read()
    verdict = re.search(r"VERDICT:?\s*(\w+)", body.splitlines()[0])
    open_tasks = len(re.findall(r"\|\s*(TODO|RUNNING|RETRY|GATE)",
                     open(os.path.join(d, "plan.md"), errors="replace").read()))
```

When a report exposes no parseable gate section, open it and read it. Emitting
"needs a read" for eight goals is a placeholder, not an answer, and the owner
cannot act on it.

## Presenting them

Cluster by what each gate unblocks, not by goal id. For each: the decision in one
line, the recommendation with its cost, and what it releases. Mark which are
prerequisites of others — a DDL change gating an install gates everything behind
the install too.

Strip the ones you can answer. A gate asking whether a config file changed at a
timestamp when you performed a credential swap is answered by your own record.

## A capability hold is usually yours, not the owner's

When a unit stops because it cannot click, cannot sign, cannot see a rendered page or cannot
reach a browser-only surface, it is reporting a **missing capability**, not requesting a
human. The hold is correct; relaying it to the owner may not be. Ask first: do *I* hold this
capability? Where the orchestrator has a browser and the executor does not, the visual and
click-driven steps are structurally the orchestrator's, and handing them to the owner spends
their turn on work you could have done.

Before escalating any capability hold, check in order:

1. Can you do it directly with a tool the executor lacks?
2. Is there a legitimate authenticated route — a server-side endpoint that performs the
   privileged step itself? Calling an endpoint that signs a request on your behalf is using
   the system as designed, not forging a credential. Read the caller to see what the payload
   actually contains before concluding you cannot send it.
3. Only if neither holds, escalate — and say which capability is missing and why nobody in
   the loop has it.

Session state is the usual obstacle, not authority: credentials bind to the exact origin
that issued them, so a session obtained for a public hostname will not apply to a loopback
address for the same service, and the request lands on a login page instead. Stay on the
origin that authenticated you, and re-authenticate freely — short-lived sessions expiring
mid-task is normal, not a blocker.

## Relaying a single gate

- Quote every branch the gate offers. A two-option gate relayed as one instruction
  is a destroyed choice and can destroy work.
- Before recommending deletion, discard or revert of a named object, measure what
  it is: siblings, last-edited time, run history. An N-member set of similarly
  named artifacts is a design; its newest member is usually work in progress.
- Check the task's plan row and the reviewer's verdict line before escalating any
  retry or failure a report describes — the report may predate the task passing.
- Give your recommendation as one line inside the relay, never as a separate turn.

## A gate deferred to another goal needs that goal to exist

Before accepting "held until X decides", confirm X has a goal directory, and search
for a renamed equivalent before concluding the work is unscheduled. Report titles
routinely carry the old identifier in parentheses after a rename, so grep the goal
tree for the referenced id rather than listing directories: one deferral named a
goal with no directory while its work lived under a new name, and three cards sat on
a decision nothing was scheduled to make.

Then check whether the named goal's acceptance criteria actually decide the question.
A goal can own the subject area without owning the decision, in which case the cards
are blocked on nobody. Say that plainly instead of relaying the deferral.

**Re-measure a deferred card's impact before scheduling anything to unblock it.** The
cheapest outcome is that the decision no longer matters: where the objects a card
would change have zero live consumers, the card closes as zero-impact regardless of
which way the decision goes, and dispatching a goal to decide it buys nothing. Count
the consumers in the environment the objects actually live in — a staging id queried
against production returns zero for the wrong reason — and pair that zero with a
control showing the same query finds callers of a known-live object.

The same applies to a hypothesis a goal exists to test: if a later measurement
already answered it, the goal is a card closure rather than a dispatch. Check the
goal's own asserted counters against live values too — a stale assertion in the GOAL
text will fail its close check even when the work succeeds.

## Scope a goal to the criteria whose gates exist

When some criteria need an approval, a budget ruling or an input that is not on the
box, dispatch the rest and mark the blocked ones measure-and-report: have the agent
re-measure the premise, state what the work would cost and what it would answer, and
stop. A whole-goal dispatch spends its wall clock rediscovering the missing gate.

Say in the prompt which criteria are out of scope and why, by name. "Do not run
criterion N" without the reason invites the agent to treat it as an oversight.


## Reporting back

**A quarantined task is not a dead goal — never report its output as void while the
leader is still running.** Quarantine voids one window's verdict and triggers a
fresh review; goals routinely recover and close PASS afterwards. Reporting a
still-running goal's work as unusable, then discovering it closed cleanly, is a
retraction that costs the owner's trust in every other status you give. Wait for
the report verdict, or say "one window quarantined, re-review in flight".

**Re-read the plan file before reporting progress; never report from the last
thing you saw.** A leader advances through review rounds and retries between your
checks, so a status carried from an earlier poll can name a task that finished
hours ago and miss that the goal closed — the owner then acts on a stale picture
and the loop's own record contradicts you. Re-read, and say which task is open
now.

**Two artifacts from the SAME goal can disagree, and the later-recomputed one
wins.** A goal that writes both a report and a derived artifact (a question list, a
lane plan, a candidate set) commonly builds them at different points: one from the
pre-review pass, one after reviewers forced a recomputation. They then state
different numbers with equal confidence. Resolve it from the artifacts themselves —
a section headed "recomputed", or a change log saying which checks were re-applied,
is the authoritative one — and never average, pick the larger, or relay both as if
the choice were cosmetic. This is load-bearing: approving the stale list would have
dispatched a goal carrying a destructive gate on a night when no decisions were
meant to be taken. When an owner's instinct is to reconcile before approving,
reconcile.

**When the plan file and the report disagree, the plan wins.** They are written
by different mechanisms: the plan's status column is updated per task as each one
resolves, while the report is a narrative the leader composes and recomposes
across the run. A report paragraph therefore describes the state at the moment it
was drafted, and a review returning afterwards leaves it stale without
contradicting itself anywhere. The failure mode is specific and expensive: a
report's gate section asking for a retry, quoted to the owner while the plan row
already reads PASS, spends the owner's ruling on a decision that does not exist
and authorises re-running work that an independent reviewer has already graded.
Before relaying any gate, retry request, or failure from a report, read that
task's plan row and the reviewer's own verdict line; if they say PASS, the gate
is closed and the correct move is to say so and retract rather than to dispatch
the retry the owner just approved.

### Recording a ruling the loop will parse

When the loop reads decisions out of a journal or state file, the entry is machine
input, not prose. Two format rules are load-bearing:

- **Put the decision token in the FIRST LINE.** Leaders typically key on the first
  line of an entry; a ruling whose opening line reads only "OWNER RULINGS on <goal>"
  with the chosen option buried in a later paragraph names no decision at all, and the
  goal stays held while reading as answered. Check how prior accepted rulings phrase
  their first line and match it (search the log on the agent host for the pattern)
  rather than inventing a layout.
- **Never write a timestamp into the body.** The journal tool stamps the entry itself;
  a time you type is at best redundant and at worst ahead of the real write, which the
  loop flags as stamped-later-than-written and refuses. Refer to "this entry" instead.

**When measurement refutes the mechanism the owner chose, implement the measured
alternative and flag the deviation in the same message.** Rulings are given on the
option set you presented, so a ruling can select a mechanism that turns out not to
exist, not to be parseable, or to have been tried and rejected in the code already.
Building the ruled version anyway ships a check that cannot fail; silently building
something else hides a decision the owner is entitled to make. Say which ruling you
deviated from, the measurement that refuted it, and what you built instead — and put
the rejected approach and its evidence in a comment at the change, so the next reader
cannot re-derive the dead idea. The same applies to a ruling whose premise moved: a
replacement tolerance the owner just picked is void if the code's own comments record
that exact formulation being replaced for a measured reason.

**A leader that refuses to act on a malformed ruling has caught your defect.** Fix the
entry's shape and re-journal it; never reword or re-send until something complies. The
cost of getting this wrong is silent — the dispatch succeeds, the goal reports HELD,
and hours pass before anyone notices the decision never landed.

Lead with the decision the user has to make, then the evidence. Disclose your own
defects - a check that could not fail, a guessed path, a wrong carried fact - before
the result that depends on them, not after. Distinguish measured from carried on every
number, and prefer CANNOT DETERMINE over an inference presented as a finding.

### Relay a gate whole, never one half of it

A goal's gate is written as a choice with costs on each side. Summarising it into
a single instruction destroys the choice, and the owner then rules on an option
set you invented. A gate reading *"discard that draft, or say it is yours to
keep"* relayed as "discard it" nearly deleted a workflow the owner had built and
edited the night before — his answer, and the rule, was *"discard seems wrong"*.
Quote every branch the gate offers, then add your recommendation as one line.
The recommendation belongs inside the relay, not in place of the options.

**Before recommending the deletion, revert or discard of any named object,
measure what the object is.** Query its siblings, its edit history and its run
history. A set of N similarly-named items — one per dimension, per stage, per
tenant — is a deliberate design, and the newest-edited member of that set is live
work in progress, not debris. This costs one query and is the difference between
clearing a blocker and destroying someone's unfinished architecture.

The same measurement often pays off twice: the artifacts the owner defended
turned out to store the very signal a blocked criterion needed, because an
ensemble that records per-judge agreement is a direct measure of scorer noise.
When the owner pushes back on discarding something, look at what it produces
before arguing.

### The owner is usually the binding constraint, not runtime or quota

When asked "how long will this take" or "should we run it 24/7", do not answer
with a duration. Count what actually stops goals: reports whose verdict is HELD or
BLOCKED, gate entries in the journal with no later ruling, and plan rows parked on
a decision — against quota deaths and rework lines. Where held-on-human dominates,
extra runtime only grows the queue waiting on the owner, and rework multiplies at
full price. Say that, give the gate census instead of a date, and name the two or
three gates that unblock the most.

**Classify each held goal by CAUSE before presenting the census, because much of a
held queue is manufactured by the verification layer rather than owed to the owner.**
Split the held goals into gates that need a human ruling and gates that exist only
because a window quarantined, a review FAILed on wording, or a sibling tripped a
detector. The ratio is measurable from the loop's own log: count quarantine mentions
and retry lines against genuine decision gates. On one box that read 88 quarantine
mentions and 130 retry lines, with at least four of seven held goals traceable to a
quarantine — including one that had finished all 44 of its cards and held anyway.
Reporting that as "the system measures faster than one person can decide" flatters the
loop and points the owner at the wrong fix: work completed and then discarded is a
plumbing defect, and the repair belongs upstream of the decisions. Do not hand-classify
with a keyword matcher and present it as fact — one built this way labelled a
quarantine-caused hold a genuine decision; either read each journal line or report the
raw counts and say the split is unclassified.

Then batch them. Enumerate every open gate across every held goal and present them
in one pass, clustered by what each unblocks rather than by goal id — five gates
that all feed one install get the install finished; five gates from five goals
finish nothing. Answer yourself any gate the record already settles: a goal asking
"was that config change you?" after a credential swap you performed is not a
question for the owner. `references/gate-escalation.md` has the extraction
procedure and why a single heading pattern misses most of them.

**"I don't recall" from the owner is not a dead end — look for a box-answerable
route before recording CANNOT DETERMINE.** An identity, an ownership or a
"which of these is mine" question usually has a measurable proxy: an address
fragment, a login timestamp against a day the owner is independently known to have
worked, an actor string in an audit table. Measuring one such question (which of
three accounts was the owner's) both answered it without a guess and surfaced two
defects nobody had asked about — a duplicate account for one human, and an audit
log that identifies actors by free-text string so a join on the user id returns
zero actions for the system's most active person. Project only what the answer
needs: an id prefix and a truncated address local-part settle identity without
printing a staff address.

**A flag that reads "inactive" may gate nothing — read how the consumer queries
it before concluding a component is off.** A registry row marked inactive was
running in production the whole time, because the consumers fetched it by id with
no active filter while sibling components filtered on it. Verify with a paired
query: the consumer's exact filter against this row, and a control component whose
flag is genuinely honoured. Getting this backwards generates an entire false
hypothesis — "the feature is disabled, activating it is the fix" — and an owner
can spend a decision on an action that is not available. The same caution applies
to any state you are about to call disabled: a value in a config table means
nothing until the reader's query is known.

**When an owner asks you to verify that something is fixed, first establish it was
ever broken.** A defect you reported from an inference may not exist, and running a
test against a healthy system produces a confident pass that entrenches the wrong
model of it. Re-measure the original claim, retract it in one line if it fails, and
only then test. The verification run is also where genuinely new defects surface —
the same pass that disproved a reported gap exposed a dimension null at exactly one
stage, and a nineteen-point spread across three runs on identical input. Report
those as the finding, not as a footnote to the retraction.

**A diagnosis that blames an external party stays unsent until it is re-measured
from this side.** Drafting a message asking an administrator whether they changed
something converts your inference into their work, and the local cause is the more
common one — an expired credential, an unauthorized tunnel resource, a client that
came back partially after a restart. When a later session disproves such a
diagnosis, retract it in one explicit line and cancel the queued message rather
than quietly reporting the new finding; the owner may already be acting on the old
one.

**On resuming after any interruption, re-verify access before reporting state.** An
orchestrator that lost reach to the agent host has two indistinguishable unknowns —
whether the host changed and whether the path changed — and reporting the last
known goal status as current conflates them. Probe the path, then the goal, then
report, in that order.
