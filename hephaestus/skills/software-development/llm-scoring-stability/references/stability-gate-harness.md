# The stability gate: a harness that can fail

Build this BEFORE any prompt revision aimed at stability, and re-run it unchanged after
each candidate fix. It is the instrument that decides whether a scorer may be handed to a
calibrator or to production. Without it, "stable" is an opinion and every fix claim is
unfalsifiable.

## Why it must exist first

The same measurement error recurs in three directions, and all three were committed on
one surface in a single day:

1. Comparing score rows **across prompt versions and months** and reporting the result as
   run-to-run variance. That is a version diff, not a stability measurement.
2. Declaring stability from **one fixture**. A second real input showed an 18-point swing
   on the same component.
3. Declaring stability from **two fixtures**. Five showed every component failing, one by
   47 points.

The common shape is comparing things that were not the same input. The gate removes the
choice by fixing the input and varying only the repeat.

## Design

**Inputs.** At least 5 real production inputs, selected for distinctness and spread:

    select distinct on (md5(col)) ... where length(col) >= <floor> order by md5(col)

Span both the size range and the range of the score the component under test assigns.
Pick the extremes deliberately — the shortest and the longest, the lowest-scoring and the
highest. Floors matter: an input too short to evidence the rubric produces a legitimately
null or clamped score that reads as stability.

**Repeats.** 8 to 10 per input. Below ~8, a zero-range result carries a 95% upper bound
wide enough to contain the prior instability rate, so it cannot distinguish a fix from
luck. Quote the bound beside any zero.

**Interleaving.** Cycle across inputs within one window: t1..t5, t1..t5, not all of t1
then all of t2. Serving-host batch conditions drift, so a blocked design loads a time
effect onto whichever input ran in the bad half. Timestamp every call and report the
within-window trend as a control on the instrument; a null time effect validates the
measurement rather than passing a check.

**Record shape.** Every record carries **its own input hash**, not a filename. Match
results to inputs by that field only.

    {'input': '<prefix>', 'md5': '<hash>', 'rep': n, 'ts': '...', 'all': {<every component>}}

**Never glob output files to collect results.** A pattern like `o_P*` matches leftovers
from an earlier input's run and silently mixes two subjects. That produced a false
retraction of a correct finding: the pooled justification text named two different
subjects, which looked like contamination of the numbers when only the quoted prose was
affected. Write each call's result into a single accumulating JSON keyed by input hash,
flushed after every call so a timeout keeps partial progress, and use unique per-call
filenames so a stale file cannot be re-read.

**Integrity assert.** Re-hash each input from disk at load and abort if it does not match
the manifest. An input silently replaced between runs invalidates everything.

**Assert the insertion point rather than computing it.** When the harness or a prompt
edit locates a section by scanning for a heading shape, that scan finds the wrong line as
soon as the document's conventions differ from the assumption. Anchor on exact adjacent
text (`lines[n].startswith('Step 2')`) and let the assert abort; a guessed offset that
silently succeeds writes the change into the wrong section and every run after it is
measuring something else.

**Record all components, not just the suspect one.** They arrive in one call, so changing
or isolating one changes the stimulus the others see.

## Building the fixture from production

The input under study is the part everyone verifies. The rest of the prompt is where
fixtures silently diverge.

**Enumerate every placeholder and name its production source.** Grep the prompt template
for `{{...}}` tokens and build a table: token, production column or expression, expected
length. Fill all of them. A harness that hashes its main input while hardcoding the role,
the client, the job description or the prior-stage payload is measuring a subject against
a context no subject ever had. Partition the components by the placeholders they read, so
a stub voids only the components downstream of it and the rest of the run survives.

**Check the column's TYPE before assuming free text.** A column named like prose is often
JSON — the giveaway is the prompt variable's own name (`..._json`). Read it
field-by-field (`col::jsonb->>'field'`) and rebuild the object; a reconstructed length
within a few tens of chars of the stored length is formatting, not missing content.

**A redaction or secret marker in extracted output may be an artifact of your extraction
shape, not a property of the data.** Encoding a column to base64 to move it intact makes
the blob itself look like a credential to a secret scanner, which replaces a line and
breaks the integrity assert — the data was never protected. Before concluding that
content is redacted and unavailable, re-read it in a different shape (field by field,
shorter slices, no encoding) and check each candidate field for the marker individually.
Getting this wrong costs more than a cycle: it is reported to the owner as "this data is
protected and I will not work around it", which is a false blocker on a measurement that
was available all along. Never actually circumvent a redactor — change the read shape,
and if the marker follows the content rather than the encoding, stop.

## The mandatory positive control

**A harness reporting "all components stable" and a harness that cannot detect
instability produce identical output.** The passing result alone cannot distinguish them.

So carry a case known to be unstable, from a prior measurement on the same prompt and
model, and state its expected signature in the goal before running:

> Component X measured range 18 on input Y under this prompt and model. If this run
> reports X stable on Y, the harness is broken and every other number in the run is void.

That is a check that can fail. Verify it fired before reading any other result. A smoke
run of 1 rep across all inputs, checked for component count and absence of errors, costs
a fraction of the budget and catches a broken extractor before it eats the whole run.

## Pass threshold

The threshold is a human ruling, not a measurement — but propose a concrete one rather
than asking an open question. A workable default, both conditions required across every
input:

- range on identical input <= 3 points
- that range under 25% of the component's between-subject spread

The second condition matters because a flattened scale can buy the first: a component
with a tiny within-input range and a tiny between-subject range is repeatable and unable
to separate anybody.

Without a written number, "stable" stays contested and nothing can be gated on it.

## Reporting

A matrix, components as rows and inputs as columns, each cell the range, plus a WORST
column and the verdict. Pooling is prohibited. Then state plainly what a failing
component means: a component unstable on identical input is partly noise, and no
calibration or accuracy claim about it is defensible. Say that in those words rather than
reporting a number and leaving the reader to infer the consequence.

State the arithmetic consequence for the decision, not just the score: range times weight
against the band boundary, and how many subjects sit in the flip zone.

## What the industry does, and the compliance floor

Useful when the owner asks what other systems do about this, and for sizing how much
stability is enough.

- **No commercial hiring platform ships a raw model score as a decision.** Vendors state
  human review as structural, not as a disclaimer: AI parses, scores and summarises; a
  trained human reviews every result before any decision affects a person. Where the
  system already has a human-override field, that override is the primary safety net —
  so a re-score path that silently destroys it is a severity-raising bug, not a dormant
  one.
- **Anchored scales are the standard fix for a vague construct.** BARS (Behaviourally
  Anchored Rating Scales) pin each scale point to a concrete observable behaviour rather
  than asking for a 0-100 judgement on an abstraction. A component that bundles several
  distinct judgements with no combination rule is the classic BARS target, and rewriting
  it with anchors is categorically different work from adding more instructions — worth
  saying explicitly when prior prose revisions have already failed.

  Measured form and result, five real inputs, nine repeats each, against a generic shared
  band table. Anchors written as discrete condition-to-score pairs, with averaging,
  interpolation and impression adjustment forbidden in the text and a lower-of-two tie
  rule; where a component already enumerated items, its score made arithmetic on that
  count. Worst-range before -> anchored -> anchored plus median-of-5:

      bundled-construct component   47 ->  3 ->  1   (never anchored directly)
      count-based component         23 -> 16 -> 16   (residual = adjacent anchors)
      conditions component          11 -> 13 ->  0
      free-judgement component      23 -> 23 ->  3
      previously-stable component   11 -> 20 -> 20   (REGRESSED)

  Three readings matter. The worst component was fixed without being touched, because
  anchors anywhere in the scale section discipline the whole table. A previously stable
  component got worse, so the full gate must be re-run after every anchoring change and
  the components not aimed at reported alongside. And a residual split between two
  ADJACENT anchor values is progress of a different kind: the dispute has moved out of the
  scale and into the count feeding it, which is a layer-2 counting problem to move into
  code, not a reason for more anchors.
- **Reliability is published as a number.** Automated-interview vendors report test-retest
  and inter-rater coefficients across organisational samples as a precondition for use,
  and publish audit and explainability statements. A scorer with no reliability figure is
  below the industry floor regardless of how good its prompt is.
- **Scoring under standardized conditions is a legal requirement**, not a quality goal:
  29 CFR 1607 (US Uniform Guidelines on Employee Selection Procedures) requires selection
  procedures be administered and scored under standardized conditions, and NYC Local Law
  144 requires a bias audit within one year of use of an automated employment decision
  tool plus candidate notice. A component returning 35 or 82 for the same interview fails
  the standardized-conditions test on its face. Stabilisation is therefore a compliance
  precondition, not polish — frame it that way to the owner.
- **"Reliability without validity" is a documented failure category.** Clearing this gate
  earns the right to calibrate; it establishes nothing about whether a score is correct.
  Check separately whether outcome labels exist at all: where no subject has reached a
  terminal outcome and the review table is empty, calibration is blocked for a reason no
  amount of stability work touches, and the owner should be told now so collection starts
  in parallel.

## Robust aggregation, when the floor is the cause

If the gate fails on every component and prose revisions have already failed, the lever
is aggregation, not wording. Sampling k times and combining is the standard published fix,
and averaging aligns with human judgement better than single draws.

Prefer a **robust** combiner over the plain mean: the mean is fragile to the outlying
draw, and among classical alternatives the geometric median is tuning-free — no
contamination-rate hyperparameter — while coordinate-wise median and trimmed mean both
need a choice. For a single scalar per component, `median_low` over k is the simple
correct form.

Size it from the draws already collected before spending a call
(`references/sampling-nondeterminism.md`), and remember the gain is entirely a function of
how lopsided the distribution is: on values split cleanly either side of a cutoff, a median
removes zero. Implement it in the combine step rather than the prompt, and re-run the gate
unchanged to verify — the harness is the test, so do not modify it in the same change.

**Price the two-judge alternative from the same runs, for free.** Any two calls in a
repeat-run set are two same-model judges, so enumerate all pairs per cell
(`itertools.combinations(v, 2)`) and count the fraction landing within the agreement
tolerance; the complement is the adjudication rate, and cost is `2 + rate` calls per
component (~2.1 measured, against 5.0 for median-of-5). Report the spread of the AGREED
value beside the agreement rate: an 89% agreement rate whose agreed answers still range
20 points means the pair moves together, and the design cannot clear the gate however
cheap it is. Same-model, different-model and adjudicated variants all inherit this —
agreement is not reproducibility.

**Size a range reduction with subsets, not with replacement.** Resampling k draws WITH
replacement can return k copies of the same extreme, so the simulated median-of-k range
equals the single-draw range by construction and the fix reads as worthless. Enumerate
every distinct k-subset instead (`itertools.combinations`, 126 subsets at k=5 from n=9)
and take each subset's median. Replacement is right for a flip rate and wrong for a
spread. Control: an identical before/after figure on every component is a simulation bug,
because a real aggregation effect is never uniform across components.
