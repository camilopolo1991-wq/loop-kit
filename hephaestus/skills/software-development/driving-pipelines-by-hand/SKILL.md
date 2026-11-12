---
name: driving-pipelines-by-hand
description: Use when pipeline output looks wrong. Drive it by hand.
---

# Driving a pipeline by hand

For multi-stage pipelines where a number at the END looks wrong — a score, a
rank, a classification — and the measurement so far has all been taken at that
last stage. The work is to walk ONE subject through every stage through the real
endpoints the UI calls, reading what each step actually produced, instead of
inferring the middle from the ends.

Use it when: a defect has been measured repeatedly at the output and the fix
keeps not landing; a stage has never been exercised; or an owner says the
problem is upstream and the evidence so far cannot distinguish stages.

## Why the last stage is the wrong place to stand

Auditing the stage where the number appears leaves every earlier stage
unexercised, and the earlier stages are where the input is shaped. Pooled
analysis of production rows cannot separate "this stage computes wrongly" from
"this stage received the wrong thing", because both produce the same bad output.

The cost of standing in the wrong place is measured in weeks, not hours: the
output keeps reproducing the defect, so the evidence always seems to point at
the stage you are already looking at.

## Procedure

1. **List the stages and their real endpoints.** Read the live registration
   table rather than a doc or a node list. Name the test path and the production
   path separately. Call-shape mechanics — body signing, per-handler input sources,
   per-task timeouts, batching — are in
   `references/firing-stages-through-real-endpoints.md`; read it before the first fire.
2. **Build fixtures as replicas, not as distinct subjects.** See *Fixture
   design* below. Nothing about same-input behaviour is measurable if no input
   repeats.
3. **Drive one stage at a time and read its output before firing the next.**
   Batch the whole arm only after a single subject proves the call shape.
   Append results to a file as you go so a timeout does not lose the arm.
4. **Reconcile calls against rows written** after every stage. Never take the
   HTTP status as proof.
5. **Read the per-stage detail, not just the headline.** Per-dimension values,
   null counts, which guard fired. The headline number hides the mechanism.
6. **Finish on the surface a user reads**, with a screenshot.
7. **Then fix what you found, and keep going until the list is empty.** The manual
   run is phase one; see *The fix loop* below. Reporting a diagnosis and stopping
   reads as finished work and is the single most expensive way to end this task.
   The script shape for editing a live database-defined workflow — rollback, marker
   idempotence, anchor counting, adding a refusal branch, and the fact that recreating
   a container unpublishes everything — is in
   `references/repair-loop-for-database-defined-workflows.md`.

## The fix loop

A measured defect is a work order addressed to you. Writing it up with its evidence
and its control is step one, and it FEELS like the whole job because it is the part
that produces a satisfying message. The job is the defect not being there any more.

The failure shape: a composite-scoring bug measured perfectly — two byte-identical
replicas, the one MISSING evidence scoring higher, control sitting beside it — written
up, turn ended. The owner's reply was four words: *"did you fix the bug?"*

So, per defect:

1. Fix it on the surface you are allowed to write to. Staging is yours; say so and
   proceed rather than asking.
2. Unit-test the DECISION in isolation before touching the live system, with at least
   two planted cases that must flip. A suite whose cases also pass on the old code has
   proven nothing. Reproduce the real measured numbers in the test so the before/after
   is the same pair the owner already saw.
3. Apply, publish, restart, then re-run **the exact input that exposed the defect**
   plus a known-good input beside it as the control.
4. **Re-test against the EXECUTING bytes, not your patch file.** Fetch the published
   version, pull the changed block out by brace-matching from its opening statement,
   wrap it in a minimal function with the thresholds above it, and run the planted cases
   through that. Testing the patch proves the patch; testing the shipped block proves the
   deploy. Where the live subjects already sit in the terminal band, the fix is a no-op on
   them and proves nothing — planted cases are the only evidence available.
5. Move to the next defect. The loop exits when the list is empty, not when the first
   fix lands.
6. Report once, at the end, before and after per defect.

The narrow exceptions still stop and go to the owner: a production write, a merge, a
push outside a documented exception, destructive SQL, a credential.

## A missing input must never improve a score

The general rule behind the renormalisation class: when a stage drops an absent
signal's weight and renormalises the rest, absence stops being neutral and starts
being favourable. Any subject whose stage FAILED then outscores the identical subject
whose stage completed.

Redistribution is still correct for a signal that genuinely never applied — a
permanently-unused assessment slot should not penalise everyone. The defect is that
the code cannot tell "never applied" from "attempted and broke".

**Find a discriminator that is written by the ATTEMPT, not by the result.** Check
candidates against the live rows before choosing: the obvious evaluation/results table
is usually absent in BOTH cases and cannot discriminate, while the artifact the stage
consumes (a transcript, an upload, a submitted form) proves the round took place.

Then **withhold rather than invent**. Scoring the missing stage as zero punishes the
subject for an infrastructure fault — the same unfairness mirrored. Refuse to compute,
leave the prior state alone, and say which stage owes a value.

### Inside a stage that DID run, demote instead of withholding

The same arithmetic bites one level down: a single missing dimension inside a completed
stage still loses its weight and still pays the subject. Withholding is wrong here,
though — a missing dimension usually means the interview never covered that ground, and
no re-run fixes the transcript, so refusing to compute strands the subject forever.

Demote the RECOMMENDATION by exactly one band and leave the stored score as the
renormalised value, so historical rows stay comparable and the correction rides on the
decision instead of silently re-scaling hundreds of past rows. One band, not straight to
the floor: incomplete evidence means the picture is partial, not that the subject is bad.

**A guard written against ONE band name is one-sided and leaks.** A cap reading
`if (absent && rec === 'Advance') rec = 'Hold'` catches only the top transition, so the
band below promotes freely. Quantify the uncaught case before trusting the guard:
sweeping 200k random dimension sets on live weights found 19,590 promotions caused purely
by a null, of which that cap caught 6,991 and 12,599 slipped through one band lower —
nearly twice as many uncaught as caught. Enumerate the whole ladder as a map
(`{Advance:'Hold', Hold:'Reject', Reject:'Reject'}`) rather than testing band names.

## A refusal must ANSWER like a refusal

Adding a throw to stop a bad write is half a fix. Where the response comes from a
responder node on the success path, a throw never reaches one and the caller gets the
orchestrator's default: a 2xx with an empty body. Replacing a wrong number with a
silent failure is not an improvement, and it is the same silent-success defect you
already flagged one step earlier.

Give the refusal its own branch and its own responder, with a 4xx and a body naming
the stage that owes a value and the action that clears it. A global error handler does
not substitute: it notifies an operator, it cannot change the response the caller
already received.

## Repair existing wrong rows by RE-RUNNING, not by deleting them

Once a bug has written bad values, re-driving the fixed pipeline over those subjects
replaces them legitimately and leaves an audit trail. Destructive correction is a last
resort for rows no re-run can reach, and that is the owner's gate rather than yours.

Expect the re-run to split: subjects the fix now withholds will correctly NOT update,
so reconcile the count and name them rather than reading the gap as a failed backfill.

## Your verification step can be the broken thing

Twice in one session a check reported failure on a write that had actually landed:

- a substring test against JSON pulled back through a CLI flag that mangled a
  non-ASCII character in the node name (em dashes and middle dots are common in
  generated names), and
- a `LIKE '0[12]'` pattern, which is regex syntax the SQL engine does not implement, so
  it matched nothing and read as "no stale rows exist".

Both looked like the fix not applying. When a verification fails, re-measure with a
DIFFERENT instrument before believing it — parse the structure rather than grepping its
serialisation, and pair the probe with a case it is known to catch. A check that can
fail on correct work sends you hunting a bug that does not exist, and an empty result
is UNKNOWN until a positive control fires.

**A generated search can be DEGENERATE: built so the effect it hunts is arithmetically
impossible.** Sweeping every band combination for "can a missing value promote an
outcome" returned zero, because the sweep filled the missing slot with the SAME number
every surviving input held — which makes renormalisation an identity, so no promotion
could ever appear. A hand-built positive control (survivors high, the missing value low)
produced one immediately, and the corrected sweep then found tens of thousands. Before
trusting a zero from a search you generated, construct one case the mechanism MUST flag
and watch it flag; if you cannot make the effect appear by hand, the zero is a fact about
your search.

## State the POWER of the run before reporting its cleanliness

A hand-driven arm is a handful of runs, and a handful of runs cannot distinguish "fixed"
from "unchanged" for anything but a gross defect. Compute that before reporting, not
after the owner asks.

Against a previously measured per-run deviation rate of ~4%, nine runs return ZERO
deviations about 70% of the time, so a clean nine is exactly what the broken version
predicts. Per dimension it is worse: with three replicas per archetype, a dimension that
truly flips 20% of runs shows zero flips half the time. Reaching p < 0.05 on a
"zero flips" claim needs on the order of 75 runs per arm.

So a manual run licenses two kinds of claim and not a third:

- **Licensed:** structural facts (a null appeared where the input had evidence; a stage
  wrote nothing; a card did not move). One observation is enough for an existence claim.
- **Licensed:** separation between archetypes, which is a large effect by design.
- **NOT licensed:** "the instability is fixed". Report the observed rate WITH its
  confidence interval and whether the old rate falls inside it — it usually does, which
  is the honest answer.

A stability number without its power is the same class of error as a count without its
denominator, and reporting one as good news is how false hope gets manufactured.

## Deploy by id; name-glob publishers hit the wrong stage

Where promotion runs through a helper that selects by name pattern, long shared
prefixes make a near-miss silent: a pattern meant for one stage's scorer matches its
guide instead, republishes that, and prints a confident success line while the
workflow you meant to ship stays on its old version. Resolve the id first, pass the
id, and confirm the echoed name is the one you intended.

## HTTP 200 proves nothing; branch on the body

Many orchestrators answer 200 by default when a chain errors before reaching its
responder, so the caller is told success while nothing was written. Branch on a
body field (`{"ok":true,...}`), and after each batch count the rows that actually
landed. A stage can report nine successes and have written four.

This is worth fixing in the workflow, not just working around in the harness: a
user clicking the button gets the same false success.

## Sibling stages disagree about where their input comes from

Stages written at different times read the same artifact differently — one
fetches it from the database by subject id, the next takes it from the request
body and defaults to an empty string when absent. Posting only the id then runs
the model against nothing, and the downstream schema failure looks exactly like
a defect in that stage.

**Grep the handler for the field name and read its fallback before writing up a
stage as broken.** A stage with zero lifetime successes may simply never have
been driven correctly; pair that count with a sibling as the control.

## Fixture design: replicas for noise, archetypes for discrimination

Three archetypes (good, middling, bad) × TEN byte-identical replicas each, all
on ONE parent record so the shared context is constant. Build the set, and the
construction mechanics, from `references/building-fixture-sets.md`.

**Ten, not three, because three cannot answer the question.** Three replicas per
archetype gives 6 degrees of freedom and a confidence interval on the spread wide
enough to contain the broken version's own rate; ten gives 27 df and roughly halves
it. The extra cost is wall clock on an unattended batch, which is the cheapest
resource in this work — spend it rather than reporting a number you then have to
qualify away. Measured at ten replicas, per-archetype SD came out under one point on
all three archetypes, which is a quotable figure; the same pipeline at three replicas
only supported "looks stable".

- Spread WITHIN an archetype is model noise and nothing else.
- Separation BETWEEN archetypes is discrimination. Stability without separation
  is a broken instrument agreeing with itself, so report both or neither.

**The bad archetype must answer every question BADLY and stay on topic.** An
omitted topic scores null, and a scorer that renormalises the remaining weights
then PAYS the subject for the gap — the opposite of the intended control. This
is the single most common fixture mistake, and production data rarely contains
the control, which is why the bug survives there.

Do not build nine distinct subjects. Same-input behaviour is unmeasurable when
no input repeats, and that error is easy to make while over-correcting for
duplicate-looking production fixtures.

## Design one fixture arm to OMIT a signal the next arm covers

The strongest control in this class: write stage one's input so the interviewer (or
form, or upstream producer) never raises one specific signal, and stage two's input so
it does. The same subject is then measured on five signals and then on six, with
everything else byte-identical, and the difference isolates the absent-signal
arithmetic instead of arguing about it. Production data only ever has ACCIDENTAL gaps,
where the missing topic also changed everything else about the input, which is why the
defect survives there unmeasured.

Gate the omission with a keyword probe over the fixture text before loading it, and
pair it with the positive control that the later arm DOES raise the topic. A single
incidental mention — one clause naming a colleague in a transcript meant to omit
collaboration — gives the model a thread to pull and silently destroys the control.

**Expect the model to score a signal nobody asked about.** Measured: with the topic
never raised at stage one, the scorer still returned a value for it on 20 of 27
subjects, inferred from asides in the screen summary and from unrelated answers — a
mentioned weekly meeting became a 95. That is not obviously wrong, since it IS
evidence, but it means **a signal's score does not depend on that signal being
measured**, and an owner who skips a topic still receives a confident number for it.

The split matters more than the headline: only the WEAKEST archetype went null,
because a thin input gives the model nothing to infer from. So absent-signal
renormalisation fires precisely on the subjects with the least evidence — the two
defects compound, inference hiding the gap for strong subjects and exposing it for weak
ones. Report that interaction, not the two bugs separately.

## Calling a stage directly bypasses the TRIGGER that chains it

Driving stages by their own endpoints exercises the workers and says nothing about the
conveyor. Where the real product flow is event-chained — saving an artifact fires the
next stage automatically — a harness that posts to each scorer in turn has tested every
worker and not one trigger. A broken trigger then looks exactly like a healthy pipeline
in the harness results, because every stage really did run.

**Map the automation contract before reporting an arm complete:** for each stage, is it
fired by the previous stage's completion, by a human action, or only by a direct call?
Trace it in the handler the UI posts to and in the chaining node's code, not from a
diagram. A node named along the lines of "trigger next if unscored" is the thing to read.

Two properties of such triggers that change how you test them:

- **They guard on ABSENCE, not intent.** The trigger checks whether a result already
  exists and skips when one does. So once the harness has scored a subject directly,
  that subject can no longer prove the trigger works — proving it needs a subject
  holding the input artifact with no result, which is usually a leftover from a failed
  run rather than something you create.
- **A re-run can be destructive where a first run is not.** A rescore path that
  hardcodes its own bypass may append a result, overwrite the evaluation row, and DELETE
  the per-criterion rows, discarding any value a human adjusted by hand. Read that
  before proposing any user-facing re-run button, and before re-driving subjects a
  reviewer has touched.

## A defect's TRIGGER is the thing worth finding

A bug reproduced only on production leftovers hides which half is at fault.
Driving clean fixtures through tells you what the defect NEEDS.

Worked example: a renormalisation path inflated a composite by 26 points on real
data. Hand-written inputs that answered every question produced zero nulls and
the defect never fired. The arithmetic bug is real and still in the code — but
its owner is upstream (do not let the process end with a question unasked), and
knowing that re-ranks the fix below defects that fire unconditionally.

So: when a manual run does NOT reproduce a known defect, that is a finding, not
a failed run. Record what the defect requires.

## Measure each stage separately; noise concentrates where input is largest

Stability is not a property of "the pipeline". Measure every stage on the same
subjects.

Observed on identical replicas: an early stage returned five of six dimensions
with zero variance and a composite spread under 1.5 points, while a later stage
on the same subjects returned two of six and a spread of 3.75-5.75. The rubric is
shared; the later stage's prompt additionally carries the earlier stage's output,
so there is far more input to vary on. **Compounding context compounds variance.**

Two consequences. Blaming "the scorer" when only the last stage was measured
points the fix at the wrong stage. And a short-prompt stage passing says nothing
about a long-prompt stage, so never generalise a stage's result to its
neighbours.

## Verify a write on the surface, not only in the column it lands in

A write can be perfectly correct in its own table while the UI shows the subject
as untouched. The shape to expect: the writer advances one status column while
the UI groups by a DIFFERENT one, and a denormalised display column stays null so
the card falls back to a stale earlier value.

Every prior probe querying the table where the data is right will agree with
itself forever. Only the rendered surface disagrees, so the manual run has to end
there.

**Separate the two halves before writing either up.** Re-measure once the pipeline has
actually completed, because a surface showing an earlier value may simply be reading a
row that did not exist yet — a claim that the display logic is broken, withdrawn an
hour later, costs more than the delay in making it. In the case measured here the
score rendering was correct all along and read the right row; only the POSITION was
wrong, because no stage writer ever touched the grouping column and every subject sat
in the intake lane regardless of progress.

When fixing a status column the UI groups by: advance only FORWARD and only from the
intake value, so a human's own placement or terminal decision is never reverted by a
re-run. Take the valid column values from the UI source that renders them, not from
guesswork, and leave judgement transitions to the human.

## A guard refusing to write is information, not an error

A median-of-N or consensus guard that refuses a subject has told you something a
pooled score table cannot: that one internal run disagreed. Read which guard
fired and on which dimension. When a sibling subject writes successfully with
the same dimension absent, you have measured the guard's coverage gap directly.

## Do not let the harness's own bugs become findings about the system

Every wrong claim in this class of work has come from the harness, not the
pipeline. Before reporting a stage broken:

- Check the call shape against a stage that works.
- Probe the model API directly with the real prompt when a schema failure is
  blamed on token limits; `stop_reason` settles it at near-zero cost.
- When a theory predicts which subjects fail, test it — a "cold first call"
  explanation dies the moment a warm retry fails identically.

Retracting a pipeline diagnosis costs the owner's trust in every other number
from the same run. State the harness defect before the result that depends on it.
