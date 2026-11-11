# Comparing successive measurements of the same subject

The failure this prevents: handing someone a SEQUENCE of numbers about one subject
that are not comparable to each other. Each reading was honest; none carried its
denominator; the reader experiences "6 of 6, then 4 of 6, then 4 failing, then 3
failing" as the system changing underneath them and loses confidence in every number.
The question it produces — "why do they start to fail again?" — is the signal that
this discipline was skipped.

Nothing here is about measuring more carefully. It is about what travels WITH a number
once it leaves your context.

## Every number carries n, subject version, and grouping rule in the same sentence

Not in a footnote, not in the previous message, not implied by context. A reading
reported as a bare count is uncomparable the moment the next one arrives, and you
will not remember which denominator it had either.

    tc 10 of 50 pairs, prompt v20, 5 fixtures x 5 reps, R1 grouping

not

    4 of 6 dimensions fail

## Before reporting a NEW number, lay it beside the OLD one with both denominators

When you have measured a subject before, the deliverable is the TABLE, not the latest
row. Build it before you write the message:

| when | instrument | claim | version | n | population |
|---|---|---|---|---|---|

If two rows differ in version, population, or grouping, say so in the same breath as
the numbers. A reader cannot be expected to notice that one row measured a dead
version on a stub assembly and another measured live scoring. Absent that, successive
readings read as regression, and the next instruction you get will be to explain a
change that never happened.

## A single repeat pair is one draw, not a rate

n=2 showing four of six values unchanged means four values did not move IN THAT DRAW.
It is an existence proof at best. Reporting it in the same shape as a rate ("4 of 6
stable") makes weak evidence look like good news and poisons every later comparison,
because the real rate measured at volume will look like a regression against it.

Label sub-threshold samples as what they are — one pair, one draw, not a rate — or do
not report them.

## A MAX aggregation is a GATE, not a description of state

A rule like "any single failure anywhere fails the subject" is the correct pass/fail
gate and a terrible summary. It cannot distinguish "broken everywhere" from "one
subject broke it once". Report BOTH:

- the gate verdict (what passes/fails under the agreed rule);
- the cell-level rate (how much of the matrix is actually sound).

"All six fail" and "67% of cells are stable, one subject causes half the damage" were
both true of the same data. Give the second alongside the first or the reader
reasonably concludes the whole system is broken.

## Ask whether the worst subject belongs in the population at all

Before letting an outlier set the verdict, check WHAT it is. A subject contributing
half the observed failures turned out to be another subject's input with eight
characters changed — a label-sensitivity probe, not a repeat subject, and a different
phenomenon pooled into the same number. Excluding it removed two dimensions from the
failure list entirely.

Run the diff. Similarity near 1.0 against another member of the population means it is
not an independent observation; report it on its own line, never inside the verdict.

## Report EFFECTIVE n, not nominal n

Nominal pair counts overstate evidence when the population is not independent:

- near-identical subjects are ONE input family however many pairs they generate;
- a subject returning zero variance on every dimension contributes no information.

Five fixtures yielding "50 pairs" can rest on three effective inputs. State the
effective count beside the nominal one.

### Census the WHOLE pool once, before planning any run that aims to widen n

Checking suspicious pairs one at a time understates the problem. Compute the collapse
over the entire fixture pool and keep the result as an artifact: hash every input body
for exact duplicates, then pairwise-similarity the distinct bodies and union-find
everything above a stated threshold into families.

Measured on an eval pool that looked like 93 independent subjects: zero exact
duplicates, 395 near-duplicate pairs at >= 0.95, and **10 effective families** — ten
interviews wearing ninety-three badges, members differing by 7-8 characters because the
pool was built by swapping name labels. One family held 111 of the scorings under four
different identifiers.

Two consequences to act on, not just report:

- **A plan to "test more subjects" cannot widen coverage past the family count.** More
  runs buy DEPTH (tighter SEM, more pairs per family), which is often what the power
  calculation actually needs — but say which one you are buying, because "100 subjects"
  and "10 families, 10 deep" are different claims and only one is true.
- **A name-variant pool measures label sensitivity, not independence.** It is the right
  instrument for a bias probe and the wrong one for a repeatability denominator. Check
  which question the pool was built for before quoting its n.

Also check that the families SPAN the outcome range before citing the pool as
representative: bucket each family by its mean outcome and confirm good / middling / bad
are all populated, and that a family's own fixture label agrees with where the subject
places it. A label/score disagreement is either a mislabelled fixture or a real subject
defect, and it has to be resolved before the spread is evidence of anything.

## State the grouping rule; if another defensible grouping flips the verdict, give both

Which records count as repeats of each other is a CHOICE. One grouping gave two
dimensions passing cleanly; a different, equally defensible grouping with a different
time cut had both failing. "Only two dimensions pass" was true under one and false
under the other.

A verdict sensitive to the grouping rule is not yet a verdict. Name the rule you used
and report the alternative when it disagrees.

## Derive the counterfactual from the SAME samples before crediting a remedy

A before/after improvement across two separate runs is confounded with run-to-run
variation. When the remedy aggregates several draws (median, mean, best-of-n), the
samples to answer this are already in hand: recompute what a SINGLE draw would have
produced from the same stored samples and compare against the aggregate.

This is the check that overturned a reported improvement: the aggregate had been
credited with taking four failing dimensions to three, but reconstructing the
single-draw counterfactual from its own samples showed it beat a single sample on ZERO
dimensions and was WORSE on the noisiest one. Without that reconstruction the remedy
ships on the strength of noise.

## A variable you did NOT touch moving is the alternative explanation, not a bonus

When a repair aimed at one variable improves a variable you never changed, that is not
extra credit — it is evidence that the whole response shifts, and your intended effect
may be the same shift rather than the repair working. The two are indistinguishable
until you bound the movement.

Before attributing any improvement to a change:

- re-fire the UNCHANGED configuration enough times to bound run-to-run movement on the
  variables you did not touch;
- report that bound BESIDE the effect size.

An effect inside its own drift band is not an effect. State the bound even when it
kills the result — a repair credited on drift ships and then fails silently in the
place it was supposed to fix.

This is especially acute when every variable is produced by ONE generation event (one
model call, one transaction, one batch job). Sibling variables from a shared event are
co-treatments, never controls for each other.

## Do not pool records that straddle a change to the subject

An in-place edit to a prompt, rule or config with no version bump makes two records
look like repeats of each other when they are not. Key repeat groups on hashes of
EVERY input (subject text, rubric, auxiliary stages), not on a version field that may
not have moved, and exclude any group whose span crosses the edit.

The same applies to mixing eras: pooling rows from an earlier run with the current
run's rows produced six "repeat groups" of which zero were clean. Restrict to the
current run and say so.

## Freeze check: the input must predate the output

A group whose input artifact was written AFTER the outputs it supposedly produced is
not a same-input repeat. Assert `input_written_at < min(output_created_at)` per group
and drop the ones that fail. A twelve-record group discarded this way is a better
result than a twelve-record group reported.
