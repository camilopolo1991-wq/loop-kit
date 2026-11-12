# Defects only a hand-walked pipeline reveals

Load this when a multi-stage scoring pipeline misbehaves and pooled analysis of the final
number has not explained it. Everything here is a defect class that auditing the last
stage cannot see, because the last stage is where the number appears and not where it is
broken.

## Walk the pipeline by hand before attributing a defect to the stage you are watching

Auditing the last stage repeatedly leaves every earlier stage unexercised. Drive one
subject through every stage manually, through the real endpoints the UI calls, and read
what each step actually produced.

What this surfaces that pooled analysis cannot:

- **A bug's TRIGGER rather than its location.** A renormalisation defect that inflated a
  composite by 26 points never fired on hand-written transcripts that answered every
  question. The defect is real and still in the code, but it needs a GAP IN THE INPUT to
  fire — so the owning fix is upstream (do not let an interview end with a dimension
  unasked), not in the arithmetic. A defect reproduced only on production leftovers hides
  which half is at fault.
- **Surface defects invisible from the database.** Scores written correctly to the scores
  table while the board still rendered the subjects in their intake column: the writer
  advanced one stage column and the UI grouped by a different one that only a human drag
  ever updates. Every prior probe queried the table where the data was right. **When a
  write is the finding, verify it on the surface a user reads, not only in the column it
  lands in.**

  Half of that finding was wrong, which is its own lesson: the cards ALSO showed stale
  scores at the moment of looking, and that was attributed to a null subject-level score
  column. The UI was in fact reading the final-stage score row correctly and the number
  was stale only because that stage had not run yet. **A surface that disagrees with the
  database has two candidate causes — the surface reads the wrong thing, or the pipeline
  has not reached the stage that fills it. Re-check after completing the pipeline before
  naming a UI bug**, and read the component's own data path rather than inferring it from
  which columns look empty.
- **Guards earning or failing their keep.** A median-of-N guard refused to write one
  subject with a mixed null and let a sibling through with the same dimension absent. Both
  outcomes are information; neither appears in a pooled score table.

Feed the manual run fixtures that answer EVERY dimension, including the deliberately bad
one. A bad subject must score LOW, not ABSENT — absent drops the weight, renormalises, and
pays the subject a bonus. Production data rarely contains that control, which is why the
bug survives there.

## Test the WORKERS and the CONVEYOR separately

Firing each stage by hand proves the stages work and proves nothing about whether they
chain. A trigger that should fire the next stage on completion is only observable on a
subject that has NOT already reached that stage — a batch whose rows were produced by
manual fires cannot test it, because the guard that skips already-scored subjects makes
every chain attempt a no-op that reads like success.

So reserve fresh subjects for the conveyor test, drive the first step only, and wait for
the rest to appear on their own. Pair it with a before-control: a subject that ran the
same journey BEFORE the chaining fix must still be stuck at the pre-fix stage. The two
side by side is what proves a chain fix rather than asserting it.

**A disabled node reports success in 0 ms and passes its input through.** It therefore
looks like a working step in every execution list, and any audit logging that lives inside
it never runs — so the alarm for the thing it was supposed to do cannot fire. Check the
`disabled` flag on every node in a chain that silently does nothing, and before citing an
empty alarm table as health, locate where the alarm is raised from.

**A quarantine can outlive its cause.** A node disabled for a real reason (it was posting
to the wrong environment) stays disabled after the underlying fix lands, because nothing
ties re-enabling to the fix. Read the change journal for WHY a node is off before either
re-enabling it or treating it as intentional, and verify the original hazard is actually
gone in the live bytes first.

## Request-body versus stored-record inputs differ between sibling stages

Before concluding a stage is broken, check where it READS its input. Sibling stages
written at different times disagree: one fetches the artifact from the database by subject
id, the next takes it from the request body and defaults to an empty string when absent.
Posting only the id then runs the model against nothing, and the resulting schema failure
looks exactly like a defect in the stage.

Measured cost: a stage with zero lifetime successful executions was reported as "has never
worked, silent failure", and the real cause was the caller omitting a body field the
sibling stage did not need. Grep the handler for the field name and read its fallback
before writing up the stage.

## Redistributing a failed stage's weight pays the subject for the gap

Composites that renormalise over the stages that returned a value treat "this stage never
applied" and "this stage ran and broke" identically. The second case then RAISES the
score, because the failed stage's weight is handed to the stages that did return — so less
evidence scores higher.

Measured on two byte-identical replicas of one subject: the replica whose final round
failed scored 21.4 against 18.5 for the one that completed, a 2.9-point bonus for the
hole. Near a promotion cutoff that turns a failed interview into an advancement.

The fix is a discriminator plus a refusal, and both halves matter:

- **Find evidence that the stage was DUE**, separate from its result. The artifact that
  proves the step happened (a stored transcript) works; the evaluation row does not,
  because it is absent both when the stage never ran and when it failed. Verify the
  discriminator against live rows for all four combinations before building on it.
- **Withhold the composite rather than scoring the gap zero.** Zero punishes the subject
  for an infrastructure fault, the same unfairness mirrored. Refuse to write, name the
  stage in the error, and let the operator re-run it.
- Keep redistribution for stages that genuinely never apply, or every subject is penalised
  for a step nobody takes.

Test the decision in isolation with planted cases that must FLIP — a due-but-missing stage
withholds, a complete subject still computes, a not-yet-reached stage still computes.
Reproduce the measured before/after numbers in the test so it is visibly the same defect.

**A refusal must answer with an explicit failure, not a bare success status.** The first
implementation of the withhold above returned HTTP 200 with an empty body, which is
indistinguishable from a successful score — recreating the silent-success shape the fix
existed to remove, one hour after that exact shape had been flagged elsewhere. Pair the
refusal with its own status code and a parsed `withheld` field, and prove both branches:
the withheld subject answers the error status, the complete one answers 200 with its
composite unchanged.

A fix does not clear values already stored. Stale inflated composites survive until
re-run; say so rather than implying the deploy repaired history. And check what a re-score
DESTROYS before offering it as remediation — a rescore that deletes per-criterion rows
discards any human-adjusted score attached to them.

## A one-sided cap only catches the top band

A guard written as "if evidence is missing and the recommendation is the top band, demote
it one step" leaves every lower band uncorrected, so a null can still promote the floor
band to the middle one. Measured over 200k simulated cases: a null caused 19,590
promotions, of which the one-sided form caught 6,991 and missed 12,599.

Replace the single comparison with an explicit demotion map covering every band, and
drive the unit test from a case table that includes the previously-missed transition
(missing evidence + middle band must reach the floor) plus a planted control that must
fail, so the harness is known to be able to fail.

## The scorer scores dimensions it was never asked about

An absent dimension is not reliably absent from the output. Measured: with a round-one
guide that never raises one dimension, the scorer still returned a value for it in 20 of
27 scorings, citing both the transcript and the screening summary as evidence — and went
null only on the weakest archetype, 7 of 7.

That asymmetry is the dangerous part: the gap opens exactly where the subject is weakest,
which is precisely where a renormalising composite pays for it. When testing coverage,
plant a dimension that is genuinely unasked and check per-archetype whether it comes back
null — a pooled null rate hides which subjects get the hole.

Validators that count questions do not enforce coverage. A check asserting
`questions.length === 6` never reads each question's dimension tag, so six questions about
five dimensions passes.
