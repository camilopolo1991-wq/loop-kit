# Condition-boolean scoring: moving the band decision out of the model

Depth for `llm-rubric-scoring-stability`. Read this when a component's competing runs
cite the SAME evidence and disagree only about which band that evidence earns. This is
the specification-layer fix, it costs no extra model calls, and it is the cheapest thing
to try before escalating to aggregation or a per-component split.

## When it applies, and how to confirm it does

Diagnose from the justifications, not the scores. Pull the free-text reason behind each
competing value and compare them clause by clause.

- Different facts cited -> the model is reading inconsistently. This technique does not
  apply; the evidence slots or the input are the problem.
- Same facts cited, same quotes, same turn references, and the clauses diverge only on
  whether one of those facts SATISFIES a named condition -> this technique applies.

The tell is explicit in the text. One cluster writes "...offered no concrete commitment
beyond the schedule" while the other writes "...he ALSO accepted the specific
arrangement", about the identical quoted sentence. Both are defensible readings of a rule
that never said which one was intended.

## The rubric pattern

Replace the anchor table with a boolean report plus an explicit instruction not to score.

1. **Name the conditions, one testable fact each.** Each condition gets a key, a
   definition of what makes it true, and at least one stated exclusion of what does not.
2. **Require a one-line reason per condition naming the turn.** The reasons are what make
   a later disagreement diagnosable.
3. **Forbid the score explicitly.** State that the score is computed outside the call and
   that any score emitted for this component is ignored. Expect `"score": null` in the
   output: that reads like a failure and is the intended behaviour.
4. **Require a self-check integer** (the count of true conditions) so the arithmetic can
   be verified without re-reading the booleans. Assert it equals the count you derive;
   a mismatch means the model is not tracking its own report.
5. **Keep the never-asked case distinct.** When no source speaks to the component at all,
   require all conditions false AND a null score and band, so "never asked" cannot be
   confused with "answered badly".
6. **Write the observed disagreement into the rule as an explicit verdict.** The clause
   the clusters split on must be resolved in so many words -- "plain acceptance of a
   named schedule IS acceptance and IS true". A definition that merely lists examples
   leaves the contested case open and the split survives.

Score in code from the count of trues, with the mapping in one table. Deriving the score
outside the call is what makes the component deterministic by construction.

## The bundling pitfall: one boolean, one fact

A condition that bundles several alternatives reproduces the original ambiguity one layer
down. Measured: a third condition defined as "a turnaround time, OR a response window, OR
accepting an off-hours slot, OR on-call willingness, OR describing their working setup"
fixed the cell it was written for and created a NEW split on a different input, where runs
disagreed 4-to-2 about whether the evidence met any of the five.

This is the same defect as the component that bundles three judgements with no combining
rule -- the thing the rubric split was meant to cure. Five alternatives behind one boolean
is five judgements wearing one name. Split each alternative into its own key and let the
code decide how many must be true.

Budget for this: expect the first pass to fix the cell you targeted and to expose a
bundled condition elsewhere. The spread moves rather than vanishing, which is progress and
must be reported as such, not as a pass.

## Splitting relocates the disagreement, so re-measure EVERY boolean

A split fixes the condition it targets and can move the instability onto a boolean that
was unanimous before. Measured: splitting a bundled condition brought the bundle's own
keys to 6-of-6 agreement, and the next run split 3/3 on a plain "was a timezone or
working hours stated" key that had been stable across every earlier run.

The mechanism is that the conditions share one response, so adding keys changes the
prompt and the generation the other keys are drawn from. Never report a split on the
evidence of the targeted key alone: tabulate the combination frequency for all keys every
run, and treat a newly-split key as the same defect class -- an under-specified condition
-- rather than as noise.

## Fixing a split key: enumerate the accepted forms, do not describe them

A key splits because its definition describes a CATEGORY and leaves the boundary to the
reader. Measured: "volunteering their local time in passing counts" drew six runs that all
quoted the same utterance and split 3/3, because a statement of local clock time is
arguably a statement of local time and arguably not a statement of a timezone. The
definition was not wrong, it was unenumerated.

Rewrite such a key as lettered cases, and resolve the contested one in the same breath:

- List the accepted forms as (a)(b)(c)(d), each a concrete observable, rather than one
  prose sentence naming the category.
- Add a sentence naming the borderline case, ruling on it, and giving the one-clause
  mechanism -- "a local clock time stated against a known interview moment fixes the
  subject's offset, which is the only thing this condition is for".
- Forbid the adjacent reasoning the split runs used: "do not require the word timezone,
  do not require a UTC offset, do not reason about whether it was deliberate".

Measured effect of that single edit, nothing else changed: the targeted cell went from a
3/3 split worth 40 points to six identical combinations, range 0. The model applies a
stated rule consistently and cannot apply an unstated one at all.

### After the forms, pin the QUANTIFIER

Enumerating the accepted forms fixes the "what counts" ambiguity and exposes the next one
in the same key: over WHICH items is the condition evaluated. Measured: a key rewritten
with lettered forms went 4-to-2 and then 5-to-1, and the lone holdout reasoned correctly
from a rule that was never written — it evaluated the condition per named item, found one
item satisfying it and another not, and returned "mixed", while the other five read it as
"any item suffices". Both are valid readings of a key that states no scope.

Every boolean needs one sentence fixing all three of: the set it ranges over, the
quantifier (ANY versus ALL), and an explicit ban on a third verdict — "judge this over the
items the subject LACKS and only those; if at least one qualifies the key is true; it is a
single true or false, never mixed, and do not average across items". Also name which
neighbouring key owns the excluded items, or the excluded case falls out of the rubric
entirely.

Budget for this shape: expect roughly three passes per contested key — the undefined rule,
then the unenumerated boundary, then the missing quantifier — each a single-variable edit
with its own measured run. That is cheap against the spread being removed, but plan the
calls for it rather than reporting the first improvement as the fix.

## Simulate the prompt fix against the UNCHANGED map before touching the map

When a key is splitting and the map is also amplifying, both look like defects and the
temptation is to fix both at once. Replay instead: take the stored boolean records, set
the splitting key to the value the pin is intended to produce, and score them through the
EXISTING map. This costs zero calls.

Measured: that replay showed every cell at range 0 with no rescale, which retired a
planned map change that would have moved two already-stable cells and capped the
component's maximum. The map was never the defect. Simulating the cheaper single-variable
fix first is also the only way to keep the one-variable-per-run rule while two candidate
defects are open.

## The mapping is an amplifier: bound each boolean's marginal swing

The code-side mapping can turn a one-boolean disagreement into a spread larger than the
defect you set out to fix. Measured: a map that treated two keys as a required backbone
turned a single flipped boolean into 45-versus-85, a 40-point swing, against the 14-point
spread of the original unsplit rubric. The booleans had improved and the reported
component was worse, entirely because of the mapping.

Design the mapping against this directly.

- **Compute each key's marginal swing before shipping the map**: for every key, the
  largest score difference produced by flipping that key alone with the others held. Any
  key whose marginal swing exceeds the spread you are trying to fix is a new single point
  of failure, and the map needs flattening -- additive contributions rather than a gating
  backbone.
- **Prefer a map where no single key gates the scale.** A key that decides whether the
  subject is scored at all concentrates the whole component's stability into one
  judgement, which is what the split was meant to disperse.
- **Derive the map to reproduce the values already measured stable, and verify that it
  does** on every cell, before looking at the new numbers. Otherwise a mapping change
  silently rescales the component and every stored score moves for a reason nobody
  recorded. State the preserved anchors explicitly.
- **Report the marginal-swing table beside the per-cell ranges.** It distinguishes "the
  model disagreed" from "my map amplified one disagreement", and those have opposite
  fixes.

## The extraction trap: parse the shape you actually asked for

Asking for a reason alongside each boolean makes the model nest the value:

    "condition_name": { "value": true, "reason": "..." }

An extractor written for a flat `"condition_name": true` matches nothing and returns a
null for every cell, which reads as the model having ignored the instruction and the fix
having failed completely. Write the regex to accept the nested shape first and the flat
shape as a fallback.

Two guards that make this non-fatal:

- **When every cell comes back null, read one raw response before concluding anything.**
  A uniform null across all cells is far more likely to be the extractor than the model.
- **Assert the self-check integer parses too.** Its presence proves the model followed the
  schema even when your boolean regex finds nothing, which immediately localises the fault
  to the extractor.

## Reporting it

Report per cell: the boolean combination with its frequency, the code-derived score, and
the range. A cell going from an even split to a single unanimous combination is the win;
state it as "the conditions are now unanimous and the mapping is deterministic", not as
"the component is stable", until every cell for that component is clean.

**Two independent runs will agree on the aggregate and disagree about WHICH cell
wobbles.** Measured on an identical config in two windows: every cell's median matched
exactly, while the single 1-in-6 minority reading moved to a different input. Report the
median agreement as the verdict and the raw distributions only to classify the failure;
a single run points at whichever cell happened to wobble and invites a prompt edit aimed
at nothing. The corollary for deploy is that `k>1` repeats per component is load-bearing
rather than an optimisation, and the proposal must say so instead of quoting the passing
number alone.

**A cell that becomes stable by changing its meaning is not a win to bank silently.**
Tightening one key can make a previously-split cell unanimous in the other direction --
scoring null where it scored a number -- because the model is now applying a rule the
rubric always stated and the earlier runs applied only half the time. Read the
justifications before calling it a regression; if they quote the rule correctly it is the
specification working. Then hand the judgement up: whether that evidence SHOULD earn the
condition is the owner's ruling, not the analyst's, and the stability result does not
settle it. Report alongside it the share of inputs for which the component now returns
null, since a component unscored on a large fraction of subjects contributes little
whatever its spread.
