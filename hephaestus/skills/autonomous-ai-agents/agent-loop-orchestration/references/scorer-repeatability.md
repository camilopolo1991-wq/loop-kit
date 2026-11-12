# Measuring a live LLM scorer's repeatability

For the question "does this scorer return the same answer on the same input", when
the scorer runs inside a production pipeline. The orchestration-side rules (verifying
reproducibility and irreversibility before writing the goal, the synthetic-fixture
gate, the no-outbound-alert proof) are in SKILL.md; this file is the measurement
shape.

## Group within the entity, never across entities

A standard deviation computed across different subjects is meaningless for
repeatability — different subjects *should* score differently, and the resulting
spread looks alarming while measuring nothing. Group by entity AND stage AND
component, then read the series in time order. A cross-entity spread table is the
most common way a repeatability claim gets fabricated from real data.

## Pin every upstream non-deterministic stage, or the number is confounded

When the component under test consumes the output of another model call, two runs
never had the same input. Capture ONE upstream output, pin it, and reuse it for
every run; report the upstream stage's own variance separately if it matters. A
spread measured without pinning is the sum of two variances and cannot be
attributed to either. If no code path accepts a pinned upstream value, say the
measurement is unavailable on the current wiring rather than reporting the combined
figure.

## Separate version changes from run-to-run noise

Historical reruns salvaged from production are not a repeatability sample: the
prompt version, the schema and the component names change underneath, so a step in
the series is a deliberate change rather than noise. Record the version beside every
value and segment the series by it. Components renamed between versions break the
series entirely — a key absent from the current version cannot be compared to its
historical namesake without establishing the mapping, and that mapping is a finding,
not an assumption.

## Report per component, and make the band the headline

For each component: every value in run order, max-minus-min, the band or label in
run order, the count of band changes, the null count, and which null source produced
each null. A spread that never crosses a band boundary is noise the consumer cannot
see; a small spread that flips the band twice in five runs is a user-visible defect.
Rank findings by band changes, not by point spread.

State n and the fixture count beside the verdict. A clean result at n=5 does not
show a defect is absent when the historical rate was roughly one occurrence in
seven — say so explicitly, because "not reproduced" is routinely read as "fixed".

**n=5 does not identify WHICH component is broken, and it inverts.** On one
fixture, a 5-run pass reported the lowest-weighted component swinging twelve points
with two band flips and the heaviest-weighted component as perfectly stable; at
n=20 on the same pinned input both reversed — the "unstable" one held a spread of 2
with zero band changes, and the "stable" one dropped a full band on five runs in
twenty. A small-n series misranks components in both directions because a trimodal
component that reads its high value five times looks deterministic. Never let an
owner set priority, and never design a fix, on a spread below roughly n=20; when an
interim figure has already been relayed, retract the ranking explicitly rather than
quietly reporting the new one, because work may already be queued against it.

The band-change rule still decides severity, but weight decides consequence: a
full-band drop on the heaviest-weighted component moves the composite far more than
a band flip on the lightest. Report each component's weight beside its spread, and
check the composite series against its own decision thresholds — a spread that
stays inside one recommendation band today may sit a few points from the next
boundary.

## Convert the spread into decision flips against the LIVE population

A spread is not a severity until it is expressed as decisions that change. The rerun
series alone systematically understates exposure, because the fixture it used may sit
nowhere near a threshold. Four steps, in order:

1. **Propagate through the weight.** A 19-point spread on a component weighted 0.25
   moves the composite 4.75 points, not 19.
2. **Name the boundary** the composite feeds.
3. **Define the flip zone** as the band within one propagated delta above the boundary.
4. **Count the live population inside that zone**, and report where the population's
   centre of mass sits relative to the boundary.

Step 4 is where the conclusion inverts. A series in which no composite crossed the
boundary reads as harmless and was reported that way; the live population then placed 7
of 24 evaluated records inside the flip zone with the mean essentially on the boundary,
making roughly a third of outcomes non-reproducible. Retract the harmless reading
explicitly when this measurement lands — an owner may already have deprioritised it.

**Recommend the boundary guard before the component fix.** Routing the flip zone to
human review stops irreproducible decisions at once; a prompt or model change needs its
own n≈20 series to prove it helped and leaves the boundary brittle if it under-delivers.
The guard is also measurable the day it ships, which the component fix is not.

## Re-running one entity measures less than scoring N clones of it

A zero spread from scoring one entity n times does not license the claim "the scorer
is stable". It measures repeatability for one payload. Build the other sample too:
N distinct entities whose evidence body is byte-identical, differing only in the
unavoidable per-entity field, and score each once.

The two numbers answer different questions, and they diverge. One rubric measured a
range of 0.00 across six reruns of a single entity, then 3.33 / 4.12 / 3.75 across
three-clone families of the same bodies — and in one family the spread straddled the
Advance/Reject boundary, so the same evidence produced different decisions. Report
both figures with their methods, and never promote the rerun figure to a stability
verdict.

**Retract the earlier verdict explicitly when the clone figure lands.** A "stable"
claim already relayed will have been acted on — a version promoted, a fix
deprioritised — so state plainly that the figure measured something narrower than it
sounded.

**When the only difference between clones is an identity field, the clone spread has
two candidate causes and you cannot yet separate them.** Run-to-run nondeterminism
and sensitivity to the identity token itself produce the identical signature. In a
pipeline where names are a known bias vector this distinction is the whole finding,
not a detail. The separating experiment is cheap: score the same body under swapped
identity tokens, and the same body under one repeated token, then compare the two
spreads. Do that before any rubric change, because tuning against the wrong cause
produces a fix that measures as working and is not.

**Normalise before claiming the inputs were identical.** When the format requires the
entity's own identifier inside the payload, raw hashes differ by construction: a
`count(distinct md5(body))` equal to the row count is the expected result, not
evidence the bodies differ. Hash the body with the identifier replaced by a constant
and report that, alongside the raw count so the difference is visible. A reviewer
reading only the raw count will correctly report "all rows differ" and wrongly
conclude the clone premise is false.

## Prove input identity by hash, not by reusing an id

A repeatability claim needs the payload byte-identical across runs. Hash the assembled
request body and report the single sha covering all n runs, plus a one-byte-mutation
control showing the comparison can detect a difference. Reusing the same record id
proves only that the same row was read, not that the same bytes reached the model.

## Count hard validation failures as their own class

A run whose output fails schema validation is not a bad score — it is a hard stop in
production, usually a different failure class with a different fix. An extra
unexpected property emitted by the model on roughly one call in six will be rejected
by a strict validator downstream. Count these separately, name the offending
property and path, keep the failed attempt in the ledger alongside its replacement,
and report the rate. A measurement run that silently retries past them understates
the pipeline's real failure rate.

## Check whether the recorded structure is load-bearing before proposing to use it

A component whose stored record carries evidence counts and a derived total may
still be storing a value the model emitted whole, with the derived figures only
range-checking a secondary field. The tell is a value that stays fixed across runs
while its own derived total moves. Read the code that assembles the record before
proposing any fix that depends on the derivation being causal.

## A constraint that blocks the obvious fix is usually deliberate

When a write is refused by a check constraint, read its definition and its origin
before working around it. An asymmetric rule — a per-scope override may hold zero
while the global default may not — encodes a real invariant: the base layer must
assign a weight to every stage, and only a specific scope may switch one off. Three
responses exist and only one is honest: satisfy the invariant by writing at the layer
it permits, or change the constraint deliberately with a reviewed forward/backward
migration, or report that the requested value is not expressible. Never insert a
near-zero placeholder to slip past the check — it leaves a value in the data whose
only purpose is to dodge a guard, and the next reader cannot tell why.

Also resolve the conflict when an owner's two answers disagree: choosing "no schema
change" and "this is permanently true for every scope" cannot both hold, because N
per-scope overrides mean every future scope silently reverts to the old default.
A permanent policy belongs in the default, not in N copies of an exception.
