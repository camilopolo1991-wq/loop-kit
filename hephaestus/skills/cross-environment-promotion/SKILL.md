---
name: cross-environment-promotion
description: Promote staging to prod where no git reconciles them.
version: 1.0.0
author: Hermes Agent
license: internal
metadata:
  hermes:
    tags: [promotion, staging, production, deployment, verification]
    related_skills: [measuring-before-claiming, working-agreement]
---

# Promoting a change into an environment that has no git

For systems where two environments hold independently editable copies of the same
logic and nothing reconciles them: workflow engines (n8n, Zapier, Airflow UIs),
low-code platforms, hand-edited server configs, database-stored prompts or rules.

The governing fact: **drift runs in BOTH directions.** The target may be AHEAD of
the source in places, because someone once hardened production directly. A naive
"copy source over target" is therefore a regression wearing a fix's clothes.

## When to Use

- About to copy a workflow, prompt, config or rule from staging into production.
- About to claim a fix is live in an environment you just wrote to.
- About to estimate how many production records a defect touched.
- Asked to act as a merge reviewer on a change crossing environments.
- A promotion just produced a new error and you are deciding whether to fix forward.
- Asked to make two whole environments "match" or "mirror" (estate-level parity, not
  one fix). Read `references/estate-parity.md` first; the per-unit procedure below
  is the inner loop of that job, not the whole of it.

## Procedure

### 1. Diff both directions before building anything

List the objects on both sides and classify every difference:

```
SOURCE ONLY   candidate for promotion
TARGET ONLY   the target would LOSE this -- name it explicitly
BOTH DIFFER   needs a human read; note which side is LARGER
```

A target-only object or a target copy that is *larger* than the source is the
signal for hand-written hardening that never flowed back. Report those by name
before proposing any promotion.

### 2. Build the payload FROM THE TARGET, never from the source

Start with the target's own current object list and replace only the specific
units carrying the fix. Everything else stays byte-identical. This makes
target-only work survive by construction rather than by remembering to preserve
it, and the object COUNT becomes a cheap invariant: if the target had 31 nodes
and the source 30, a correct payload has 31.

### 3. Attribute every added line to a claimed fix, and refuse the rest

**A fix label is a claim about a node, not a measurement of it.** Diff the unit
being promoted against the target's current copy and bucket the ADDED lines:
lines that carry the fix marker, and lines that do not. A unit labelled as a
seven-line change that adds sixty unattributed lines is importing unrelated
features.

This is the costliest pitfall in this class. Unrelated features ride along inside
a shared unit and silently acquire the fix's authorisation.

### 4. Check the preconditions the promoted code ASSUMES

Promoted code carries assumptions about its surroundings that the target may not
satisfy. Before accepting a payload, read the first lines of each promoted unit
for guards and preconditions, then verify each against the TARGET's graph:

- item or sample counts (`if (input.length !== 3) throw ...`) against what the
  target's upstream node actually emits
- node names and connections the code calls into
- fields the code reads that the target's schema may not have

A guard like "require exactly N inputs" is invisible in a node-body diff and
total in effect: every run throws and nothing is written.

### 5. Rewrite environment-bound identifiers, and gate on their absence

Hostnames, database names, ports, bucket names and queue names are CORRECT for
the source and WRONG the moment the code crosses over. They travel invisibly
inside node bodies.

Maintain an explicit rewrite list and a forbidden-token list, then refuse to
emit a payload if a single forbidden token survives:

```python
ENV_REWRITES = [("service-staging", "service")]
FORBIDDEN_IN_PROD = ["service-staging", "appdb_staging", "queue_staging"]
```

Self-test the gate in both directions: a dirty payload must be refused and a
clean one accepted. A gate only ever observed passing has not been shown to work.

### 6. Snapshot, and prove the snapshot before any overwrite

Capture the target's current state, then **read it back and parse it**. A
snapshot that is actually an error message is the shape to fear: it has a
plausible file size, a sensible name, and restores nothing.

Do the capture from a Python file, not a nested shell heredoc. Multi-level
quoting through `sudo bash -c "... psql -c \"...\" ..."` mangles identifiers and
writes the resulting error text into the archive file, exit code 0.

Abort the promotion if any snapshot fails to parse or its object count does not
match the live target.

### 7. Land the diff and PUBLISH as two separate steps

Where the platform separates a stored definition from the version it executes
(a draft/published split, or n8n's entity vs active version), use that gap
deliberately:

1. write the payload to the stored definition and verify it there
2. confirm the EXECUTING version is still the old one
3. publish as a distinct, separately authorised action

This gives a reviewable landed diff with zero runtime blast radius, and it means
a payload found to be wrong at step 2 is rolled back without anything having run
through it.

### 8. Verify with a control that distinguishes the two states

"Not live yet" and "my marker check is broken" look identical. Assert BOTH
directions: the executing version still contains a string unique to the OLD code,
and does not contain one unique to the NEW. One-sided checks cannot tell a
pending state from a broken instrument.

### 9. On any new error, roll back -- do not fix forward

Restore from the snapshot and verify byte-identity against it, then re-assert the
target-only objects survived. Fixing forward on a production surface compounds an
unproven change with another unproven change.

## Standing rules

- **A payload file plus the two-direction diff is the deliverable. The apply is a
  human gate.** When that gate is given, execute every authorised item in the
  same turn rather than re-confirming.
- **An inventory of drift is the start of parity work, never its deliverable.** A
  map of what differs, however accurate, changes nothing; the user reads a turn
  that ends on a document as a turn that did nothing. Land the first change, prove
  it, then write the map carrying the measured before/after. Document AFTER, not
  INSTEAD.
- **A change to one side of a contract is a change to both sides in the same
  step.** Flipping which secret a webhook verifies breaks every caller that signs
  with the old one; renaming a route breaks every link to it. Locate the
  counterpart (the signer, the caller, the consumer) before the dry run, and move
  both together or the environment is broken between the two writes.
- **A count of differing nodes is not knowledge of what differs.** Never apply a
  change built from a dry-run SUMMARY of units nobody read. When the reason for
  pausing is "the picture is incomplete", the move is a todo list with one line per
  unit and parallel readers (`delegate_task`) that return a classified verdict per
  unit, read-only; apply only from verdicts.
- **Diff code bodies as lines, not as one JSON string.** A `jsCode` field rendered
  as a single quoted line makes every change read as "code differs" and hides that
  three of five "drifted" nodes are a missing space after a colon. Expand multi-line
  string fields before diffing, and count NON-BLANK differing lines before calling
  anything drift.
- **When wiring an error output onto every node in a graph, skip any node whose
  error slot is already occupied, and never treat a branch slot as an error slot.**
  Two hazards share one index: an IF-type node's second output is its FALSE logic
  branch, not an error output, so wiring it to an error responder reroutes real
  control flow; and a node whose error slot already feeds an existing responder (a
  422 refusal path from an earlier fix) would fan error items to two responders if a
  second target is appended. Classify each node by TYPE first, then by slot
  occupancy, and print the skipped nodes by name so the human gate can confirm each
  skip is deliberate coexistence, not a miss.

- **Env-RESOLVED code is the one legitimate carrier of the other environment's tokens;
  carve it out of the forbidden-token gate by exact literal, never by relaxing the list.**
  A node that picks its target at runtime (`isStaging ? 5679 : 5678`,
  `isStaging ? '/webhook/stg-x' : '/webhook/x'`) MUST keep the staging literals in prod, so
  a blanket env rewrite silently destroys the feature (both branches become prod) while the
  gate stays green. Mask the exact ternary strings before rewriting and before gating, assert
  each appears exactly once, and still rewrite every other env-bound token in the same body
  (measured: the same node also carried a hardcoded `postgrest-staging` hostname that the
  gate caught only once the ternaries were masked instead of the whole body exempted).

- **A responder that answers a structured 500 ends the execution `success`, so it no
  longer fires the error hook.** Budget pages from the EXECUTING graph, not from last
  session's shape: after EMPTY200-style responders land, ghost-id probes page 0 times and
  the only alert left is the HMAC spoof alert from a deliberately bad signature. Count
  pages afterwards from the hook's execution rows and the audit table, not from intent.

- **A backport is the same procedure with source and target swapped — the "safe"
  direction does not exist.** Copying prod's hardening into staging still needs the
  env rewrite (prod hosts -> staging hosts), the forbidden-token gate, the snapshot,
  and a live firing proof. The instinct that writes to staging are low-stakes skips
  exactly the gates that make the later staging->prod promotion trustworthy.

- **After promoting a loud-failure path, prove BOTH arms live: a forced failure
  returns the structured error, and a known-good input still succeeds.** The failure
  arm alone can pass while the happy path is broken by the same wiring; the pair is
  the unit, one probe each.

- **Structural changes CAN be payload material, built from the target's own graph.**
  A fix that adds a unit AND a connection is buildable: deep-copy the target's
  connections, append exactly the new branch, and gate STRUCTURALLY by comparing the
  result against `target_connections + the one expected edge` rather than by pattern
  matching the textual diff. A textual connections gate is brittle (JSON indentation
  splits one logical edge across seven unattributable lines) and will reject a correct
  payload. Build the new unit from the TARGET's nearest sibling unit as the template,
  never from the source object, so the target's own typeVersion and conventions carry.
  Still say which other fix it is coupled to, because a refusal path promoted without
  its responder silently returns success.

- **Derive an expected diff size by diffing each block, not by trimming shared
  leading and trailing lines.** A block whose interior is unchanged (one line edited
  inside a five-line replacement) has those interior lines counted as changes by a
  trim-based estimate, so the gate demands a bigger diff than the correct splice
  produces and rejects good work. Run `difflib` per block and sum the real counts.

- **Self-validate the must-keep marker list against the target BEFORE using it.**
  A marker that the target does not actually contain is a check that cannot pass, and
  its failure looks exactly like a damaged payload. Measured: a marker carried over
  from a sibling workflow's gate appeared zero times in the workflow being promoted.
  Pair it with the mirror control: every forbidden marker must also be absent from the
  target NOW, or proving it absent afterwards proves nothing about the splice.

- **Re-read the SOURCE at the end, not just the target.** Staging can move while the
  payload is being built. Diff the source again before writing the report and classify
  anything new as a separate fix; otherwise its absence from the payload reads as an
  oversight. Measured: a third responder plus six `onError` flags landed on staging
  three minutes after the diff that the payload was built from.
- **Infrastructure-level settings are a separate decision** from logic. A timeout
  or memory ceiling deliberately differing between environments is a control, not
  drift; promote it only on its own merits.
- **Name the exposure in distinct subjects, not rows.** Eighteen bad rows across
  six candidates is a six-candidate problem; reporting the row count overstates
  it.
- Before recomputing affected records, check whether a recompute DESTROYS human
  edits (a rescore that deletes adjustment rows). Remediation that discards
  reviewer input is worse than the stale number.

Platform-specific mechanics: `references/n8n-promotion.md`.
Estate-level parity (making two whole environments mirror): `references/estate-parity.md`.
