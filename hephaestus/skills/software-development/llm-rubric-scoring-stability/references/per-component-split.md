# Splitting a multi-component scorer into one call per component

Depth for `llm-rubric-scoring-stability`. Read this when every in-call fix (anchored
bands, derived arithmetic, median aggregation) has failed to bring one or more components
within the gate, and the remaining hypothesis is that scoring N components in ONE model
call is itself the mechanism.

## Why this is the fix of last resort, and why it still may not be the fix

A single call asked for several component scores shares one sampling event, one context
and one reduction order across all of them. Consequences that no prompt edit reaches:

- Editing one component's text perturbs the others, so each round of per-component
  tuning requires re-measuring all N and the apparent cross-effects are partly fixture
  noise and partly real coupling, with no cheap way to separate them.
- A component that is stable in isolation can be dragged by whichever reading the shared
  context settled into.

Splitting to one call per component removes the coupling instead of fighting it.
Measured outcome on a six-component rubric: components that no in-call fix could move
below 14-22 points of spread came back at range 0 per-component, while a component
already stable in the combined call stayed stable.

**And the same split has been measured to destroy the scorer's discriminating power.**
On production inputs it drove every component that had scored at or above the advance
threshold down onto a single mid-scale value, halved the standard deviation, and left no
component anywhere in the cohort able to reach the advance threshold — a scorer that can
no longer advance anyone. The mechanism is the same one that buys the stability: scored
alone, a component has no sibling scores in context to calibrate against, so the model
retreats to the middle of the scale and stays there, consistently.

So the split is a HYPOTHESIS to be tested against the discrimination gate below, never a
remedy to be deployed on the strength of its stability numbers. Repeated in-call failure
is grounds to test it. Only the distribution across subjects decides it.

## The discrimination gate, which outranks the stability gate

Run this before any deploy and treat failure as a rollback rather than a tuning note. A
stability harness cannot fail on a scorer that returns a constant, so stability evidence
alone never licenses the split.

On a cohort spanning the score range, report per component, old architecture versus new:
min, max, range, mean, sd, and the count of scores at or above the advance threshold.
Fail the gate on any of:

- sd falling by roughly half or more
- several previously-distinct high scores landing on the SAME value
- zero scores at or above the advance threshold where the old architecture had some
- the aggregate range contracting toward a single band

Select the cohort by existing per-component scores and assert the span before accepting
it: at least one subject above the advance threshold and one near the floor. Three
mid-scoring subjects cannot reveal a ceiling collapse, because the sample had no ceiling.

Recommendation-level checks are too coarse to serve as this gate. Where bands are wide, a
full collapse of the underlying scores can leave every recommendation unchanged, so
"no recommendation moved" is consistent with having destroyed the scoring. Gate on the
component scores.


## Build the per-component prompts by generation, never by hand

Generate all N from the single combined rubric in one script, so the shared context,
evidence rules and scale cannot drift apart between components. Hand-editing one of N is
the failure shape: the components silently diverge and a later spread reading cannot be
attributed.

Per component, the generated prompt keeps the shared preamble and that component's own
section, and must have:

- the output schema narrowed to exactly ONE component key
- any anchor table restricted to the component it governs (carrying a sibling's anchor
  table is a real leak, not harmless context)
- an explicit header stating this call scores exactly one component and that inherited
  text referring to "the N components" does not apply

Verify content, not just shape. A check that only asserts schema keys and placeholder
presence cannot fail on stale cross-component instructions, and a combined rubric
restates "the six dimensions" many times. Assert: exactly one component key in the
schema, every placeholder still present, the governing anchor table present only where it
belongs, and a count of sibling-component mentions.

Keep deliberate cross-references. Scope boundaries of the form "X judges whether the
candidate has DONE the work, this component judges whether they want to" are
load-bearing and must survive the split; blanket-stripping every sibling mention removes
them. Read the residual mentions individually and keep the ones that define a boundary.

## Carry an already-stable component through the split as a control

Include at least one component that already passes the gate in the combined call. If it
comes back unstable in the per-component arm, the arm is broken and every other number in
the run is void. Without that control, a per-component arm reporting everything stable and
a per-component arm that has quietly changed the task are indistinguishable.

## The split MOVES scores; it is a recalibration, not only a narrowing

Compare modal score per cell between architectures before claiming anything. Measured on
one rubric: 4 of 20 cells moved by 13 to 16 points and weighted composites moved by up to
+6.45, with a systematic upward bias on most inputs. No recommendation boundary was
crossed in that sample, but one input landed within 6 points of one.

Three consequences to state in the same breath as the stability win:

- **Scores produced before and after are not comparable.** A population scored under both
  architectures carries two scales in one table. Re-scoring the already-scored population
  becomes mandatory rather than optional.
- **Any threshold, band or cutoff tuned against the old scale must be re-checked.** Those
  lines were not set against the new distribution.
- **Report the direction, not just the spread.** A change that narrows variance while
  shifting the whole distribution is a policy change and needs the owner's ruling.

## Cost arithmetic, and what aggregation is still needed for

Price it per component, not per rubric. Where the split alone brings most components to
range 0, aggregation is only needed for the components that still move, and applying
median-of-k to all N multiplies cost for no effect on the ones already deterministic.

The cheap two-judge variant (two calls per component, adjudicate only on disagreement,
about 2.1 calls per component) does NOT substitute for the split: agreement between
judges is not stability, and it cannot clear a gate the single call fails.

## Deploying a fan-out in a node pipeline: count the responses

The fan-out itself is often already present — a sub-workflow call configured to run once
per input item will genuinely issue N calls when handed N items. The danger is entirely
downstream, and it surfaces one layer at a time: each fix exposes the next boundary, so
expect several end-to-end attempts and read each failure off the run record rather than
guessing the next patch.

**Audit every node between the model call and the write for single-item reads.** A node
whose body reads the first input item and returns one object will silently collapse N
responses to one, with a success status all the way through and no log line. The composite
is then built from whichever component arrived first. This is the canonical check that
cannot fail: the pipeline reports success, the row is written, and the value is wrong.

- Rewrite each such node to map over all input items and carry an explicit component
  field on every item.
- **Match responses back to components by that explicit field, never by array position.**
- **Verify the component field actually SURVIVES each boundary it crosses, because a
  sub-workflow commonly returns a FIXED shape and discards every field you added.** A
  retry or backoff wrapper that returns its own envelope drops the component tag
  silently, so the explicit-field rule above cannot be satisfied across it. Assert the
  field's presence immediately after the boundary rather than at the merge. Where the
  wrapper is configured to run once per item it does preserve ORDER even while dropping
  fields, which makes positional recovery the available fallback — but only with an
  asserted input-count-equals-output-count check, since position is meaningful only if
  nothing was dropped.
- **Merge the N responses BEFORE any per-item validator, not after.** A validator that
  runs once per item and requires all N components in the item it sees will reject every
  single-component item, which looks like a schema defect in your new prompts and is
  actually an ordering defect in the pipeline. Establish each downstream node's
  granularity (per item or per batch) before choosing where the merge goes.
- **Read the output schema's required top-level fields and confirm the merge still emits
  every one.** Splitting by component typically produces the component map and nothing
  else, while the schema also requires sibling top-level fields the single combined call
  used to produce once — an overall note, a coverage summary. The run fails validation on
  a field no per-component prompt is asked for. Decide deliberately whether one call still
  produces it or the schema changes, and never synthesise a placeholder value to clear the
  validator.
- Put a completeness assertion in the merge: exactly one score per expected component,
  and exactly k responses for any component being aggregated. A missing component must
  stop the run, not yield a composite over N-1 components.
- Note which single-item reads are CORRECT: inside a sub-workflow invoked once per item,
  a first-item read is right, because one item is in scope per invocation. Do not change
  those.
- Canary the fan-out by counting, not by inspecting the result. A run that silently used
  one response looks identical from the outside to a correct run; assert that N calls
  were made and N responses reached the merge.

## Reading the run record when a pipeline attempt fails

- **Resolve the stored run's error through its string table rather than regexing the
  blob.** Execution payloads are commonly serialised with de-duplicated strings and
  integer references, so a pattern match on a message key returns small integers that look
  like data. Dereference, or the diagnosis is built on indices.
- **A success status is not a scored run.** Concurrency guards return success while
  skipping, with a flag naming the skip reason; the lock itself commonly has a timed lease
  and an audit row, so the remedy is to wait out the lease rather than to retry
  immediately. Branch on the skip flag, never on the status.
- **Locate the failing step relative to the nodes you changed before accepting blame.** An
  error upstream of your first edited node cannot be your change; confirm with a control
  that the same upstream step succeeded on earlier runs, and say so rather than patching
  your own work to fit.
- **When a tool can only replace an existing node's body and cannot add a node or rewire
  connections, fold the new logic into a node that already sits in the right position** by
  replacing a single anchor line, asserting that the anchor occurs exactly once. Build the
  folded body from THAT node's own current source, separately per workflow: two workflows
  that look like copies routinely hold different node bodies, and pasting one into the
  other reverts the differences.


## Run a syntax check against the UNMODIFIED node before debugging your edit

Pipeline code nodes are wrapped by the runtime before execution, commonly in an async
function, so top-level `await` is valid in the node and rejected by a bare-file syntax
check. An edited node failing such a check looks like a defect you introduced. Run the
same checker against the original body first: when the original fails identically, the
instrument is wrong, not the patch. Then check both by wrapping them the way the runtime
does.

This is the general form of pairing every negative with a control, applied to the tool
rather than to the data.

## Sequencing replication runs

Run dependent measurement runs strictly in series and verify the dependent run actually
started, rather than assuming. Where a watcher shell is waiting on run A in order to
launch run B, stopping run A by process-name pattern kills the watcher too and B never
starts; the absence shows up only as a missing result file. Check for the second run's
records before analysing, and stop processes by explicit pid.
