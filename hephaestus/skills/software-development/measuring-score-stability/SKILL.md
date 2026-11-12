---
name: measuring-score-stability
description: Bound drift before claiming a score fix works.
version: 1.0.0
author: Hermes Agent
license: proprietary
metadata:
  hermes:
    tags: [scoring, llm, statistics, repeatability, measurement]
    related_skills: [llm-scoring-stability, verifying-measurements, staging-environment-fidelity]
---

# Measuring score stability without fooling yourself

For work on LLM scorers that emit numeric scores or bands and must be repeatable
on identical input. Every rule below was paid for by a wrong claim.

## When to Use

- Claiming a scorer is stable, or that a change improved its stability
- Designing a replica or fixture set to measure repeatability
- Reporting SEM, RC, ICC or an agreement rate to anyone
- A multi-stage pipeline's final number looks wrong and the stages were only
  audited individually
- Before writing any stability figure into a delivered document

## An effect inside its own drift band is not an effect

**Re-fire the UNCHANGED configuration first and bound run-to-run movement.** Only
then attribute an improvement to a change. State the bound even when it kills
the result.

Measured case: a prompt repair looked like a dimension going 12/50 -> 6/50 band
flips. Re-firing with nothing changed moved the same dimension 6 -> 4 anyway, and
a second dimension nobody touched went 6 -> 0. Both "improvements" were drift,
and both had already been reported as wins.

A dimension moving when nothing targeted it is the tell. Treat it as a drift
alarm, not a bonus.

Bound the drift for EVERY dimension, not only the ones that moved. A dimension
reading zero inside an unmeasured band is not a pass; it is an unknown wearing
one.

## Check the channel reaches the model before fixing what flows through it

Trace the actual payload from the artifact you intend to repair to the model
call, and confirm the field arrives, before spending anything on repairing its
content. Measured: sixteen days of work went into interview-guide coverage, and
the scorer never received the guide's per-question tag at all — it got a 240-char
truncation of one adjacent field. The whole hypothesis was unreachable from the
start and one payload read would have shown it.

This is the cheapest pre-registration there is: if the channel does not arrive,
the hypothesis is refuted at zero model spend.

## Scores come back in ONE call, so there is no per-dimension work to split

When a rubric returns every dimension in a single response, dimensions are not a
parallelisation axis — the same fact that makes median-of-N cost 1+kN calls
rather than 6×. Asked to speed a run up, measure first: a saturated pipeline
(busy/wall near 1, latency dominated by the model call inside the workflow)
cannot be helped by fanning out agents.

The axis that does exist is FIXTURES, when the scorer locks per
`(subject, stage)` rather than globally — read the concurrency guard to confirm
the lock's scope. Parallel fires across distinct fixtures turn a serial round
into a concurrent one.

Add concurrency only with the cap controls: the post cap must hold under N
workers (re-read the counter per post, never at init — a shared counter read once
accepted 50 posts against a cap of 25), two fires for the same subject must be
refused by the worker pool rather than by the remote's lock response, and
`--parallel 1` must reproduce the serial result byte-for-byte with a one-byte
control failing. A faster instrument that miscounts is worse than a slow one.

**Never change the instrument mid-arm.** A before/after comparison measured with
two different harness versions is not a comparison. Authorise the speedup, bind
it to start after the current arm's measurement lands, and say so in writing.

## A zero needs its N computed against the baseline rate, or it means nothing

"Zero flips across the replicas" is not evidence of a fix until you compute how
often the UNFIXED system would also have shown zero. Do the binomial before
reporting: at a baseline deviation rate p over n runs, P(0 deviations) = (1-p)^n.

Measured trap: a hand-built replica set returned five of six dimensions with
zero variance and it was reported as "five of six hold". The baseline rate from
the prior large set was 3.94% (14 of 355). Over 9 runs, P(0 deviations) = 0.70 —
so zero was the BROKEN system's most likely outcome, and the one flip actually
observed put the rate at 11% with a 95% interval of [0.02, 0.44] that contains
the old rate. Reaching p<0.05 needed about 75 runs. The claim had to be
retracted within the hour.

Run the power calculation BEFORE firing, not after the pretty result arrives.
It costs no model calls and it tells you whether the planned run can answer the
question at all. When n is too small, say "this run cannot distinguish fixed
from unchanged" in those words and state the n that could.

Per-dimension power is worse than the headline: three replicas per group means a
dimension that truly flips 20% of the time still shows zero flips half the time.

## N fixtures scored once is not one fixture scored N times

They answer different questions and the distinction is easy to lose when the
fixtures are byte-identical replicas. Replicas scored once each measure
SAME-INPUT DETERMINISM across rows. One fixture re-scored N times measures
RUN-TO-RUN stability of that row. A pipeline can be clean on the first and noisy
on the second, because a re-score crosses whatever caches, prompt-row reads and
model-side state a single batch does not.

State which one the run bought, and never let the replica count stand in for a
repeat count.

## Measure stability PER STAGE; noise concentrates where the input is largest

In a multi-stage pipeline (screen, round one, round two, holistic), stability is
not a property of "the scorer". Measure every stage separately on the same
subjects.

Measured: on identical replicas, round one returned five of six dimensions with
zero variance and a composite spread of 0.00-1.50 points, while round two on the
same subjects returned two of six and a spread of 3.75-5.75. The difference is
not the rubric, which is shared — round two's prompt additionally carries round
one's scores and its guide, so there is far more input for the model to vary on.
Compounding context compounds variance.

Two consequences. Attributing a pipeline's instability to "the scorer" when only
the last stage was ever measured points the fix at the wrong stage. And a stage
with a short prompt is not evidence about a stage with a long one, so never
generalise a stage's pass to its neighbours.

## Pre-register the refutation condition

Before the first measurement, write down what result would REFUTE the
hypothesis. A confirmation with no stated refutation condition is not evidence.
This is the difference between a measurement and a story.

## Every number carries its denominator in the same sentence

Quote n, effective n and the prompt/model version alongside any rate. Figures
from different denominators look like a regression when laid end to end:
"6 of 6 fail", "4 of 6 stable", "4 fail", "3 fail" were four different
experiments on three prompt versions, reported as if they were a trend.

**Effective n is usually smaller than the fixture count.** Check fixtures for
near-duplication (two transcripts at 0.9991 similarity are one input family) and
for fixtures that return range 0 on everything (they contribute no information).
A single wild fixture can supply half the apparent damage.

**Verdicts are grouping-dependent.** The same rows gave 0/50 flips under one
grouping rule and 5/36 under another. State the grouping and report both.

## A near-identical clone is not a repeat subject

Before pooling repeats, diff the inputs. A fixture that is another fixture's body
with a handful of characters changed measures *label sensitivity*, not run-to-run
noise. Pooling the two mixes phenomena and inflates the instability rate. Report
it separately.

**Collapsing fixtures by SIMILARITY does not make them replicas, and treating a
similarity cluster as one subject is itself a measurement error.** Near-identical
text belonging to DIFFERENT people is still different input: every genuine
between-person difference lands inside the cluster and gets charged to the scorer.
Measured, on the same pipeline: a headline of SEM 5.06 / RC 14.0 computed over ten
"transcript families" collapsed at >=0.95 similarity became SEM 0.39-2.09 /
RC 1.08-5.78 when recomputed over byte-identical replicas — roughly an order of
magnitude, and the scorer had been stable the whole time while two weeks of work
chased it.

So define the subject by CONSTRUCTION, not by distance:

- A replica is byte-identical input, **proven by hashing** — strip the one field
  that must vary (the name) and show the raw hashes collapse to a single distinct
  value per group. Name the normaliser and print its output.
- Everything the model sees must be identical, not just the main artifact. A
  screening summary that differs across replicas makes the run a measurement of
  input variance no matter how identical the transcripts are.
- The cheap test when a subject definition is in doubt: *could two members of this
  group legitimately deserve different scores?* If yes, it is not a replica group.

**Exclude the whole family or none of it.** Dropping one clone while keeping its
siblings is the most dangerous move in this whole area, because the member you
notice is the unstable one. Measured: excluding a single "label clone" while
retaining three fixtures at 0.9991 similarity to it halved the headline error —
SEM 5.06 -> 2.58, RC 14.0 -> 7.1 points — and the resulting figures were reported
as a result. The exclusion rule as stated applied verbatim to the three that
stayed. If a rule would remove the family, remove the family; otherwise publish
both framings side by side and cite the inclusive one. Where the subject unit
itself was wrong, retire the framing rather than re-tuning which members to drop —
changing the exclusion rule cannot fix a broken denominator.

Freeze check: the input must predate every score in the group. A group whose
transcript was written after its scores is invalid.

## Small drift across a decision threshold is a decision defect

Spread matters relative to the nearest boundary, not in absolute points. Check
every measured spread against the thresholds it could cross before calling it
harmless: a 5-point wobble is nothing mid-band and changes the outcome entirely
when it straddles a cutoff.

Measured: eight scorings of one byte-identical input returned 47.0 twice and 52.0
six times across a 50-point threshold, so the same input produced both
*Likely Reject* and *Possible*. The interview stages in the same pipeline showed no
such split, because their archetypes sat far from any boundary — which is why a
per-stage pass does not license the stage with a boundary inside its band.

Report the abstain band explicitly: any score within RC of a threshold should be
escalated for human review rather than decided by the model. State the band's
numeric range (threshold +/- RC), not just the principle.

## Perturb the verdict before reporting it

Arithmetic verified twice is still not a result. Before quoting any figure, drop
each subject in turn and recompute (leave-one-out). Report the full-set number
and the LOO range together. A verdict that does not survive losing one subject is
a property of that subject, not of the system.

Measured: a dimension read ICC 0.871 on the full set and 0.462 with one input
family removed; another swung 0.854-0.999. Both had already been published as
"clears the bar". Per-subject swing is the cheapest robustness check that exists
and it takes one loop.

Compute, cross-check the computation, **then perturb the input** — the third step
is the one that gets skipped, and skipping it produces a confident number that
has to be retracted later. Retracting the same headline three times in a day
destroys the reader's ability to use any of them.

## Count runs, not pairs

For "how often does the verdict agree with itself", the honest denominator is
scoring RUNS, not within-subject pairs. One deviant run among 15 siblings
manufactures 14 disagreeing pairs, so the pair rate reads like 14 failures where
there is one. Measured on the same rows: 97.18% by runs, 98.98% by pairs, and
94.21% once subjects were collapsed to input families — three numbers, one
phenomenon.

Pair counts also grow quadratically inside a family, so a pooled pair
denominator in the thousands implies independence that is not there. Quote the
run-level rate as the headline, show the pair rate beside it, and never present
a pair count as that many independent trials.

Prefer figures the reader can recount by hand ("10 of 355 runs disagreed") over
derived statistics. After a sequence of corrections, a raw count is the only kind
of number that rebuilds trust.

## Pick the metric the eval set was built to support

SEM and RC are WITHIN-subject: they answer "does the same input score the same
twice" and they are what a repeat-heavy eval set buys. ICC is a RATIO of
between-subject to total variance, so it depends on how widely the subject pool
spreads — it is partly a property of the fixtures, not of the scorer.

On an eval set built deliberately from clones of a few interviews, ICC is the
wrong instrument: removing one subject starves the between-subject term and the
value collapses. That collapse is an artefact of the metric, not a defect in the
data. Measured mistake: an ICC crash under leave-one-out was reported as "the
test data is too thin to measure four dimensions", when the within-subject SEM
for those same dimensions was stable to about 2 points across every LOO fold.

**Do not blame the fixtures for a metric you chose.** A clone-based eval set with
336 repeat scorings is a strong instrument for repeatability; say what it does
and does not support, and check whether the owner built it that way on purpose
before calling it a limitation.

Also report ICC with a confidence interval and read the verdict off the LOWER
bound. Four dimensions had point estimates above 0.90 whose intervals included
values below it.

## Deterministic modal value, or there is no modal value

`max(set(xs), key=xs.count)` breaks ties by set iteration order, silently
swapping which side counts as the deviation. It inflated a "deviant scored
higher" count from 4 to 7. On a tie there is no majority: record the subject as
TIED and exclude it from deviation counts rather than letting an arbitrary side
become the baseline.

## Never describe a control the build does not run

A document claimed "the measurement script carries two controls — a planted
unstable pair and a planted identical pair". The controls lived in a different
file; the build ran neither. Claiming verification that was not performed is
worse than having no controls at all.

Put the controls in the artifact that emits the numbers and make it ABORT on
failure: a planted unstable pair it must flag, and a planted identical pair it
must pass. Print both measured values in the output so the reader sees them fire.
Note that an ICC control needs at least two subjects — a single planted subject
returns undefined and reads as "control failed" rather than "control invalid".

## Two clean passes means two DIFFERENT instruments

Re-running one checker over unchanged bytes cannot fail — it is one measurement
reported twice. The second pass has to be able to DISAGREE with the first, which
means a different route to the same number and, where possible, a different source
of truth.

The shape that worked, for a document of statistics:

- **Pass 1 reads the rendered artifact.** Extract the text layer of the delivered
  file and assert every printed figure, every mandatory caveat, and the absence of
  any retracted headline from the results section. This catches what the build did
  to the numbers after computing them.
- **Pass 2 recomputes from the raw source by different formulas.** Re-read the
  database rather than the intermediate JSON, and arrive at each statistic another
  way — a df-weighted RMS of per-subject standard deviations against a pooled
  variance, variance components by method of moments against an ANOVA
  decomposition. Agreement to 1e-6 then means something; a shared helper would not.

Each pass carries its own controls, including a positive control that the extractor
or the instrument works at all — a broken text extractor silently passes every
"string is absent" check. Pair each absence assertion with a presence assertion.

A figure that legitimately appears twice (once as the retracted value, once in a
history table) needs a positional check, not a count check: assert it is absent
from the current-results section and present as history. A bare `count <= 1` fires
against a correct document, and the instinct to "fix" the document then damages it.

## Render the delivered artifact and look at it

Text-layer checks pass on a document whose tables are unreadable. Rasterise every
page and inspect it before delivery: measured faults that no textual assertion
caught were a clipped final column, a numeric cell colliding with its neighbour,
and a widened table pushing content onto a near-empty page whose footer still read
the previous page number. Wrap long table cells in flowable paragraphs rather than
raw strings, then re-render and re-check — a width fix on one page reflows the
others.

## Promote the harness out of scratch, once

Install the fire runner and flip checker to a shared tool directory with a
`--selftest`. Extend it in place; never write a second copy.

Measured cost of not doing this: 39 of 63 goals on one subject each built their
own harness. The lineage root was deleted by routine scratch cleanup, so three
earlier measurement runs became unreproducible. Code in a task's evidence
directory dies with the task.

## Averaging does not fix a deterministic perturbation

If the variance is per-call, median-of-N narrows point spread but need not fix
band flips. Measured: median-of-3 beat a single draw on *zero* dimensions and was
worse on one. Derive the single-draw rate from the same samples before claiming
the median helped — it costs nothing and it is the control that matters.

If the variance is a deterministic function of some input feature (a name, a
label), averaging returns the perturbation unchanged. Fix the input instead.

## Temperature 0 is not determinism

Verify per stage. Measured: identical output x4 for one model/stage, and 4
distinct raw outputs at a byte-identical prompt for another in the same pipeline.
Do not reason from "temperature 0 so the input must differ".

## Prove a prompt fix by the payload, never by the node source

Read what the model actually received from the execution record. A correct-looking
node and a payload still carrying the old value are indistinguishable from the
source. Pair it with an un-neutralised control that MUST still find the value.

Corollary: a template placeholder can reach production unreplaced. Count the
literal `{{token}}` in stored execution data, not in the template.

## A write guard refusing a duplicate is not a run failure

A scorer that de-duplicates identical results will accept the request, succeed,
and write nothing — the harness then halts on "new score rows = 0". That is the
guard working. Read the execution record for a skip/duplicate node before
treating it as breakage.

And a halt is sticky by design: a chaining script that reads the subsequent
`REFUSE: halt record(s) exist` as "wave finished" will burn every remaining wave
in seconds without firing once. Distinguish three outcomes explicitly —
completed, refused-because-halted, failed — and never let refused look like done.

## Defects only a hand-walked pipeline reveals

Auditing the last stage repeatedly, because that is where the number appears, leaves
every earlier stage unexercised. Drive one subject through every stage manually,
through the real endpoints the UI calls, and read what each step actually produced.
This finds a bug's TRIGGER rather than its location, surface defects invisible from
the database, and guards silently refusing or silently passing.

Two rules worth carrying without opening the reference. **Firing each stage by hand
tests the WORKERS, not the CONVEYOR** — a chaining trigger is only observable on a
subject that has not already reached the next stage, so reserve fresh subjects for it
and pair the run with a before-control that must still be stuck. And **a disabled node
reports success in 0 ms and passes its input through**, so it looks like a working step
and any audit logging inside it never runs — an alarm that has never fired may be
unable to.

The full set — the due-but-missing discriminator and why a withheld composite must
answer an explicit failure rather than an empty 200, request-body versus stored-record
inputs between sibling stages, one-sided caps that only catch the top band, dimensions
scored without being asked, and quarantines that outlive their cause:
`references/pipeline-walkthrough-defects.md`.

## Reliability is not validity

With no outcome labels (nobody hired, no review rows), no claim that a score is
CORRECT is falsifiable. Say "this buys repeatability, not accuracy" in those
words, every time.

## Normalise before claiming a fixture set is identical

Two instruments disagreed on whether the same fixtures were byte-identical after
name normalisation — one reported 1,424 differing characters where the other
reported none. Name the normaliser and show its output; otherwise the
identical-input premise the whole programme rests on is unverified.
