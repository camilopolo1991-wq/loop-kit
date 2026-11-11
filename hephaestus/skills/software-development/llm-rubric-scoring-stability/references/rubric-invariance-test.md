# Designing a rubric invariance test

Depth for `llm-rubric-scoring-stability`. This is the test that measures the property a
stability fix is actually meant to buy, and it is routinely skipped in favour of a
cheaper one that looks similar.

## What determinism is not

Re-running the scorer on a byte-identical fixture and getting the same band measures
**repeatability**. Collapsing a fixture's spread to zero only shows that the items that
fixture happens to exercise are now decided.

**Inter-reader reliability** is the property being bought: would two competent readers,
looking at the same substance presented differently, assign the same band? A scorer can
be perfectly repeatable and still read the document rather than the person.

Never report repeatability as reliability. Where only repeatability has been measured,
say which one the number is and that the other is unmeasured.

## Construction

Hold the substance fixed and vary only surface properties the rubric declares
irrelevant. Each variant is a transformation of one base fixture, so the expected
classification is known by construction.

Variation axes worth including, cheapest first:

- **Reordering.** Permute the order in which the same facts appear.
- **Paraphrase.** Restate each fact in different words, same claims.
- **Length / padding.** Pad with on-topic but non-substantive text. Document length is
  known to move screening outcomes on its own; if padding moves a band, the pipeline is
  measuring the document rather than the person, and that is a fairness finding, not a
  tuning detail.
- **Formatting.** Bullets versus prose, headings added or removed.
- **Section relabelling.** The same content under a different heading, where the rubric
  does not key on headings.

## The control that makes it a test

Every invariance run must include, in the same batch, a **planted variation that SHOULD
move the classification** — remove a fact the rubric requires evidence for, or downgrade
an evidenced item to a mention.

Without it, a scorer that emits a constant label passes perfectly. "Nothing moved" is
only evidence when something was proven able to move.

Report both columns together: variants that should not move and did not, and the planted
variant that should move and did.

## Reading the result

- Invariants hold, planted control moves: the fix bought reliability on these axes. Name
  the axes; the claim does not extend to axes you did not vary.
- An invariant moves: the rubric keys on something it declares irrelevant. Record which
  axis, because that names the defect.
- Planted control does not move: the harness is not reaching the scorer, or the label is
  being produced downstream of the model. Fix the instrument before reading anything
  else.

## Cost and ordering

One base fixture times five axes plus one planted control is a handful of model calls —
cheap against any production re-score. Run it BEFORE writing re-scored rows, for the same
reason bounds are tightened first: a measurement taken after the write is advisory.
