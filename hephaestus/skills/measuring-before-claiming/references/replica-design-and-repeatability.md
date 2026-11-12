# Replica design and repeatability instruments

For any claim of the form "the system agrees with itself": model scorers, graders,
rankers, classifiers, flaky test suites, any non-deterministic subject measured by
repeating it.

## The subject definition is the measurement

**A replica is byte-identical input, verified by hashing. Not input that reads
alike.** Grouping near-duplicate items by textual similarity and calling each
group a subject measures variance in the INPUT, because any real difference
between two members lands inside the group and is charged to the system.

The cheap test before trusting a subject definition: *could two members of this
group legitimately deserve different results?* If yes, it is not a replica group
and the resulting figure is an upper bound on noise, not a measurement of it.

The cost of getting this wrong is not marginal. Rebuilding a repeatability study
on true replicas moved the headline error figure by roughly an order of
magnitude; weeks of work had been measuring the wrong end of the pipe.

**Hold EVERY input constant, not just the obvious one.** Where a system consumes
several inputs (a transcript and a summary, a prompt and a retrieved context),
all of them must be identical across replicas. Varying one while fixing the other
still measures input variance.

Prove identity rather than asserting it: hash the raw bodies with the varying
identifier removed and show N hashes collapse to 1. State the one residual
difference if a parser requires it (a speaker label, an id field).

## Pick the number of replicas for the degrees of freedom

n=3 per subject gives ~6 df and a confidence interval wide enough to be useless.
n=10 gives ~27 df. Report the upper confidence bound, not the point estimate,
when the decision depends on the figure being small.

## Never pool across a designed difference

Stages, rounds or modes that cover deliberately different ground must be reported
separately. Pooling a five-dimension stage with a six-dimension stage charges a
designed coverage difference to instability. The same applies to paths: measure
sets created by different routes separately, so a path effect cannot hide inside
an average.

## Controls must BRACKET the instrument

Two planted cases, both of which abort the run on failure:

- a deliberately unstable subject the instrument MUST flag (high error, low ICC)
- an identical-output subject the instrument MUST pass (error 0, ICC 1)

A check that cannot fail is worse than no check, and one that cannot pass is
equally useless. These two together prove the instrument discriminates.

## Spread-dependent statistics are upper bounds

ICC is a ratio of between-subject to total variance, so a pool built to span
quality deliberately yields a higher ICC than a real, pre-screened population.
Say so. Report the spread-independent figures (SEM, repeatability coefficient) as
the transferable numbers.

## Repeatability is not accuracy

Agreement with itself says nothing about whether the outputs are correct, fair or
predictive. When nothing has been validated against a real outcome, state that no
validation exists rather than letting a strong consistency figure imply one.

## Decision thresholds need an abstain band

A small wobble is harmless everywhere except across a decision boundary. When
repeated runs of identical input straddle a threshold, the outputs differ in
verdict while barely differing in value. Recommend escalating any result within
+/- the repeatability coefficient of a threshold, and look specifically for this
pattern: it is invisible in an aggregate error figure.

## Two clean passes means two DIFFERENT instruments

Re-running one checker over unchanged bytes is one measurement reported twice.
The second pass must be able to DISAGREE with the first:

- pass 1 reads the rendered ARTEFACT (extract the PDF/HTML text back and check the
  figures actually printed), catching render, rounding and formatting faults
- pass 2 recomputes every figure from the RAW SOURCE by different formulas
  (variance from the sd side vs the variance side; variance components by method
  of moments vs ANOVA mean squares), and re-reads the database rather than the
  intermediate file, so a fetch bug surfaces

Expect the passes to find real faults; if both come back clean on the first run,
suspect the checks before believing the result.

## Verify a rendered document by PIXELS as well as text

A text-layer check cannot see a clipped column, an overlapping cell, or content
spilling onto a near-empty trailing page. Render each page to PNG and look at it.
When a table overflows, convert its cells to wrapping paragraphs and widen the
prose column rather than shrinking the font alone.

## Retract in the document, not only in chat

When a published figure is withdrawn, the replacement document states the old
figure, the new one, and WHY the old instrument was wrong, in a comparison table.
A correction that lives only in conversation leaves the wrong number circulating
in the artefact people actually cite.
