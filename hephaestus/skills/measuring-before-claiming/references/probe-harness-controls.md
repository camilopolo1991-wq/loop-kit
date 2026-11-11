# Probe and harness controls

How to build a probe whose zeros mean something. Every rule here is the fix for a
real all-zero reading that looked like a clean subject and was actually a blind
instrument.

## The order that makes a zero trustworthy

1. Read the subject's own source for the CONDITIONS it evaluates. Do not infer them
   from the spec prose or the variable names.
2. Find every root, path, or scope the subject walks, and override ALL of them.
3. Plant a deliberate positive that MUST register. Run it. Confirm non-zero.
4. Only then plant the negatives, one broken condition per case.
5. Re-run the whole suite twice. Identical output or the result is not a measurement.

Step 3 before step 5 is the whole discipline: a suite whose positive case has never
fired cannot distinguish a sound subject from a probe that never looked.

## Failure shapes

**Override every root the subject walks, not just the one named after your target.**
An evidence-root override relocated where results were WRITTEN while the detector
kept scanning its default filesystem root. The tell was in the artifact: a baseline
holding 330,837 entries for a synthetic tree containing four files. Check the
baseline's own size against what you planted before reading any count.

**Grep the subject for its env-override names rather than guessing them.** A guessed
name silently does nothing; the probe then measures production. Prefixed names are
usually uniform (`TOOL_A`, `TOOL_B`), so list them all with one pattern and override
the set.

**An observation that closes its own window makes every later write unwatched.** A
clean check wrote a closed marker, so artifacts planted afterwards were outside the
watched period and every count came back zero. Give each case its OWN window: plant
first, observe once.

**Teardown that ignores errors contaminates every later case.** `rmtree(...,
ignore_errors=True)` as an unprivileged user against root-owned directories fails
SILENTLY; the next case inherited the previous case's still-open window and a stale
baseline, and its result read as a subject defect. Delete as the owning user and
ASSERT the path is gone — raise if it survives, never continue.

**Write fixtures as the user the subject runs as.** A tool invoked through `sudo`
leaves root-owned directories; a fixture write as the agent then raises
PermissionError, which surfaces as an empty result rather than an error.

**Place import probes inside the project tree.** A script in a scratch directory
resolves relative imports against that directory, so a module-not-found error looks
like a missing symbol in the subject. Write the probe into the project, run it, then
remove it.

## A per-item rc sweep over a CLI needs a bogus-flag control

Most CLIs exit non-zero for an unrecognised argument, so a sweep calling a verb that
does not exist returns the SAME failing rc for every item. The output is a tidy column
of identical refusals that reads as a finding about the subjects — a sweep of 21 queue
items all returning `rc=1` was about to be reported as "every unit fails its gate" when
not one of them had been evaluated.

Before trusting any such sweep:

- read `--help` (or the usage block) and confirm the verb you are calling is listed;
- run the tool once with a deliberately nonsensical flag and record its rc. **An rc
  identical to your sweep's condemns the sweep**, not the subjects;
- require the sweep to DISCRIMINATE: a uniform result across items that should differ is
  not a measurement. Find the item you expect to fail and the item you expect to pass,
  and confirm they come out differently before reading the rest.

When the verb genuinely does not exist, locate the real gate the production caller
invokes — grep the dispatcher or scheduler for the check's name — and drive that same
binary with the same inputs, rather than inventing a flag that resembles it.

## Count the DISCARDS, not just the usable records

A parser that drops records silently turns a complete dataset into a zero, and a bare
`usable=0` reads as "the evidence is unusable" rather than "my pattern is wrong". Emit
every rejection reason beside the usable total and assert the ones that must be zero:

```python
print(f"usable={len(rows)} bad_name={bad} no_json={nj} no_fields={nf}")
assert bad == 0, "filename pattern does not match the corpus"
```

A zero-usable result next to a large discard count is a claim about the instrument.
The same shape appears in filename conventions: variable-length tag segments
(`rF_tech`, `cond3R_reli`, `pdmoti`) break a pattern that assumes one optional part,
so anchor on the fixed-shape fields and let the middle float.

## Prefer the subject's own tool to a hand-rolled reimplementation

Where the subject ships a generator, refresher or selftest, drive THAT rather than
editing its output. A generated artifact hand-edited to fix a defect is reverted by
the next regeneration, and the reversion looks exactly like the fix never working — so
find the input the generator reads (a stop list, a config, a manifest) and change that
instead. Verify by re-running the generator and reading its own summary line.

## Interpreting a verdict file: read the predicate, do not guess the parse

Two traps when a tool reports a verdict you then parse:

- **A summary bucket merges categories.** See the main skill; re-derive from raw
  per-record values and reconcile.
- **Your extraction regex can be narrower than the data.** A verdict matcher looking
  for one literal keyword misses the synonyms the tool also emits, so records with a
  real verdict land in an "unknown" pile and the totals shift. Tabulate the DISTINCT
  verdict strings present before writing the matcher.

## Promote a reviewed harness to a shared tool; a harness in scratch is a harness deleted

A measurement rig that lives in one unit of work's scratch or evidence directory dies
with that unit, and its results become unreproducible the moment the directory is
cleaned. The observed end state: the lineage root of the most-reused rig on a box was
deleted at routine close, leaving only base-less diffs in several evidence trees, so
three earlier runs could no longer be reproduced at all — while the shared tool
directory held dozens of platform utilities and not one harness.

The second cost is duplication: where no shared harness exists, each new unit of work
builds its own, and each new build pays its own review rounds for the same controls.
Two units hours apart each spent multiple reviewer rounds approving equivalent rigs.

So when a harness passes review:

- install it to the shared tool directory with a `--selftest` that runs its controls;
- make the NEXT measurement call the promoted tool, and say so — a goal-local copy
  producing the numbers means the promotion did not happen;
- reconstruct from the pair that still has its controls recorded (the diff plus the
  verify script whose bad-hash, swap and perturb cases all fired), not from whichever
  copy is newest.

Treat "promote the harness" as a hard acceptance criterion, not housekeeping. It is
the step that gets dropped, and dropping it is what makes the same measurement cost
full price every time.

## A success gate must MEASURE the subject, never grep a report for a phrase

A gate that searches a worker's own report for words like "all six zero" or "no
failures" matches prose discussing controls, caveats or the criterion itself. Measured
consequence: a gate grepping for an all-clear phrase fired on a report whose actual
verdict was "DO NOT ship", declared the problem solved, and shut down the loop with the
defect live.

Build the gate to recompute the verdict from primary records — the rows the subject
wrote, for the version currently live — and to print the version and the per-category
sample counts every run. Then give it a third outcome: PASS, FAIL, and
`INSUFFICIENT n`, so a clean reading on too little data cannot be a pass.

Test it against a report you KNOW is negative before arming it. A gate that has never
been shown refusing is decoration, and a gate wired into an unattended loop is the one
place that costs the most.

## Render a generated document and LOOK at every page before handing it over

For any artifact a human reads — PDF, deck, report, dashboard — rasterise each page and
inspect it with your own vision. Extraction logic that looks correct produces documents
that are visibly wrong: a per-section extractor keyed on "longest paragraph mentioning
X" pasted the same shared JSON schema under four different section headings, and nothing
in the build output said so.

After fixing such an extractor, add a build-time control that ABORTS when two sections
share text. Section-level duplication is the characteristic failure of
extract-by-proximity, and an assertion in the builder catches it on every later rebuild
without another human read.

## Reporting

Report the harness defects alongside the finding. When five instrument faults
preceded one true reading, the count of rounds is itself the signal: it tells the
reader how much to trust the number and how the next probe should be built. A finding
presented without its instrument history invites the same five rounds next time.

When a claim already given to the user has to be withdrawn, lead with the withdrawal
and name the instrument fault that caused it. Two withdrawals in one session is the
signal to stop measuring and hand off, not to attempt a third reading in the same
context.
