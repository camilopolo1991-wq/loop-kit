# Auditing drift across a whole environment pair

Use when the question is not "is this one artifact different" but "what is the state of
drift between these two environments" — before planning any reconciliation, after a long
gap with no promotions, or when someone proposes syncing one environment from the other.

The output is a MAP, not a change. Nothing is written in either environment.

## Why aggregate direction is the wrong question

The instinct is to establish which environment is "ahead" and promote from it. Measured
on one mature pair of pipeline instances:

    twin pairs (matched by name)        41
    differing nodes classified         238
      PROD_AHEAD                       166
      COSMETIC                          20
      ENV                               18
      STG_AHEAD                         16
      DIVERGED                          13
      UNRESOLVED                         5
    nodes found identical              367
    pairs differing in RAW BYTE SIZE    40 of 41

Two things fall out. Production was ahead on 166 nodes despite being the environment that
"should" lag, so a staging-to-production sync would have been a mass deletion. And raw
size flagged 40 of 41 pairs as different when most of that was formatting — making the
obvious cheap signal useless.

**Direction is a per-node property.** The aggregate number is useful only for sizing the
work.

## Procedure

### 1. Build the twin map

Match by name with the environment prefix stripped, then record what does NOT match:

- twinned pairs — the main body of work
- source-only definitions — each one is either dead, deliberate, or a testing gap
- target-only definitions — usually test tooling, occasionally an orphan

Classify the un-twinned by EXECUTION COUNT, never by opinion: a definition with zero
lifetime executions and no callers is dead; one running daily with no counterpart in the
other environment is a testing gap, meaning a change to it cannot be tested before it
reaches production.

### 2. Extract the published node set per side

Read the version that executes — the history row named by the active-version pointer —
not the draft row. Flag every definition where you had to fall back to the draft because
nothing is published; that is a finding in itself.

### 3. Normalise, then hash

Drop `position`, internal `id`, `webhookId`, condition ids, and empty `options` objects;
sort keys; hash the canonical JSON. Without this, formatting noise dominates and the real
signal is unreadable.

Prove the normaliser on both edges before trusting any label:

- a pair you know is identical must come back IDENTICAL
- a one-character mutation of that same pair must flip to DIFFERENT

A differ that cannot return IDENTICAL is as broken as one that cannot return DIFFERENT.

### 4. Mechanical labels first, semantic pass second

Hash equality gives IDENTICAL for free. Hostname-only and credential-name-only differences
are ENV and can be matched by pattern. Everything left needs a reading.

### 5. Fan the semantic pass out, blind

Batch the remaining pairs across parallel workers. Each worker reads both sides of each
node and emits: node name, label, 1-3 lines of the differing logic, and what the other
side would lose.

**Give the workers no expected labels.** A finding you already measured by hand becomes a
blind control: if an independent batch rediscovers it unprompted, the method holds.

**Require a per-batch hash control.** Each worker re-runs the normaliser on its own
extraction and confirms it reproduces the hashes from step 3. A batch whose extraction
drifted is classifying something other than what runs.

**Require hypothesis controls on the cheap labels.** For each COSMETIC or ENV claim, apply
the stated explanation to one side and re-compare — it must become equal. Pair it with a
negative control that must stay unequal. This is what separates "I think this is just key
ordering" from a measurement.

### 6. Reconcile disagreements by keeping both

Where two batches label the same node differently, record BOTH readings and name the
measurement that would settle it. Do not average, pick the majority, or re-run until they
agree. A disagreement caused by a denied measurement is honest and informative; a forced
consensus is neither.

### 7. Assemble and rank by blast radius

A shared sub-component called by both environments outranks a leaf definition. A node that
writes data outranks one that notifies. Rank, do not reconcile — the reconciliation is a
separate decision with a separate authorisation.

## What the audit reliably surfaces

These recur because nothing routine looks for them:

- **A privilege asymmetry.** A pre-production environment minting credentials with a
  higher database role than production, on a shared signing secret. Pre-production is
  usually assumed to be the weaker environment; where it is stronger, it is the softer
  target for the same data.
- **A hardcoded cross-environment host.** A production node naming an internal host and
  port literally. Harmless in place, catastrophic if that node is ever copied the other
  way — the copy points the test environment at live infrastructure.
- **A missing error handler on one side.** `errorWorkflow` absent on the test side for a
  large fraction of pairs is the mechanism behind "alerting silently stopped working".
  Settings diverge far more than nodes do and no node-level diff sees it.
- **A component disabled on one side only.** Reads as a trivial flag; promoting that side
  turns the feature off in the other environment.

## Scope limits to state in the output

- **Execution retention differs per environment.** Where one keeps 12 days and the other
  2, any claim about the shorter side's history beyond its window is unmeasurable.
- **A redacting query wrapper is not byte-faithful.** If the tool reading the definitions
  redacts secrets, exact byte counts are wrong, though comparisons still hold because the
  redaction applies to both sides. Say so rather than quoting sizes as exact.
- **Say plainly when the independent review step did not run.** An audit assembled without
  it is single-sourced, and a map that looks complete is trusted as though it were
  reviewed.
- **A guard that denies a measurement is a boundary, not an obstacle.** Where reading
  container environment is refused, the labels depending on it stay conditional. Record
  them as conditional and never route around the guard to resolve them.
