# Consolidating a proliferated backlog

Depth for the SKILL.md rules on held items and on measuring where a queue terminates.
Read when many units of work have accumulated on ONE subject and the subject's state
has become unknowable from the record.

The measured end state of letting it run: 63 units on a single subject, 32 of them
stopped at a question, 39 having each built their own measurement rig, 34 re-reading
the same identifier, 21 independently re-deriving the same result, 136 reviewer
failures and retries, and FIVE units in sixteen days that changed the product at all —
with the record of it all larger than the code it describes. The machinery becomes the
output: being auditable is easy to optimise for because it is what gets checked, and
it looks like compliance.

## The mechanism: every measurement became a new unit, and units do not share code

This is the causal chain to break, not a discipline problem:

1. a unit measures something and finds an adjacent question;
2. the adjacent question becomes a NEW unit rather than a line in the report;
3. the new unit cannot inherit the first one's rig, because rigs live in unit-local
   scratch, so it builds its own and pays its own review rounds;
4. each rig has a different denominator, so the numbers do not compose — see
   `references/comparing-successive-measurements.md`.

Step 2 is the one to forbid. Step 3 is fixed by promoting harnesses to shared tools
(`references/probe-harness-controls.md`).

## Writing the consolidated unit

**One unit owns the whole problem, and it may not spawn siblings.** State explicitly:
out-of-scope findings go in the REPORT, never into a new unit file. Without that
sentence the consolidation re-proliferates on its first interesting discovery.

**Forbid the stopped verdict.** Where a ruling would normally return to the human, the
unit makes the recommended call, records what it assumed, and continues. Running out
of time means naming which criteria are UNPROVEN — not stopping. Get the human's
explicit acceptance that the unit will occasionally choose wrong, then write that
acceptance into the unit so a later reader does not treat autonomy as overreach.

**Name ONE hypothesis and register its refutation condition BEFORE the data is read.**
Reject a confirmation that arrives without one. A unit that measures fragments
produces another incomparable number; a unit that can be WRONG produces an answer.
When the hypothesis is refuted, the unit still runs the planned repair and reports
that it did not help — otherwise "refuted" becomes an escape hatch back to stopping.

**Carry forward what is established and forbid re-deriving it.** List the findings
that already closed, with their numbers and sample sizes, and instruct the unit to
CITE rather than rebuild them. This is the single biggest cost saving available.

**Fix the ORDER with the human, then make it binding.** Where several root causes
compete, the human picks which to attack first and the unit may not switch mid-run
even if a reviewer argues another has stronger evidence. Record it as a quoted ruling.

**Fix ONE instance end to end rather than six partially.** Pick the worst-performing
case and take it through repair and re-measurement. One proven beats six attempted,
and it is the only shape that tests the hypothesis.

**Promote the harness as a hard acceptance criterion**, and require the unit's own
numbers to come from the promoted tool rather than a local copy.

**Carry a CORRECTIONS section when the audit overturns live claims.** A parallel read
of the pile will contradict things already reported as established — state which
earlier statements are superseded, inside the unit, so a later reader cannot act on
the dead version. Where a shipped remedy is among them, say what its own data showed
rather than softening it.

**Re-read the unit's artifact after any mid-flight edit, and say so in the prompt.**
A consolidated unit is long and gets amended while the queue is firing; a worker that
reads its brief once at startup plans without whatever arrived in the last minute.

## Auditing the pile before consolidating: fan out, do not read serially

Split the units across parallel read-only reviewers (six or seven each) and give EVERY
reviewer the same list of already-established findings with their numbers. That shared
context is what lets a reviewer say "this unit merely re-derives X" instead of
re-reading it from scratch, and it is what surfaces contradictions BETWEEN units.

Ask each reviewer, per unit: its verdict line; what it ESTABLISHED with the number and
sample size, or "nothing measurable"; what it marks unproven; which other unit makes
it unnecessary; and a one-line disposition of KEEP / SUPERSEDED / DEAD. Require "not
stated" where the artifact is silent, so absence does not get filled in.

This pass is worth running for its own sake: ten reviewers over 63 units overturned
five claims already reported to the human as established, including a remedy credited
with an improvement its own data refuted.

**Do not trust a subject-tagging regex over the corpus.** Matching bare words to
classify units by topic reported 123 of 132 as one subject, because every artifact
mentions a filename or a path. Classify by what a unit WAITS ON, read from its own
report, and treat any classifier that puts most of the corpus in one bucket as broken.
Say so before quoting its counts — a broken classifier's numbers are not a finding.

## Closing the superseded units

One journal line each, naming the consolidating unit and the superseded unit's own
last verdict, with evidence directories left INTACT. Do not archive them away and do
not delete evidence — several carry real measurements whose trail is the only record.

For any unit whose subject the consolidation does NOT answer, name it explicitly as a
remainder. Silent absorption is how a live obligation disappears.

## Look for rulings that were given and never actioned

A proliferated pile reliably contains decisions the human already made that nobody
implemented: an approved successor unit that was never created, blockers lifted by a
ruling whose units still sit stopped against the answered gate, and — worst — live
consequences for real people resting on arithmetic that costs nothing to redo.

Grep the journal for rulings and reconcile each against the current state of the
object it governed. Expect at least one case where the shipped code has since moved
AWAY from the ruling rather than toward it. Name these as remainders rather than
re-litigating them.

## Report the pile's own cost in the consolidation

Count, in the unit itself: how many units exist on the subject, how many stopped, how
many built their own rig, how many re-derived the same result, how many reviewer
retries, and how many changed the product. Those six numbers justify the consolidation
to a reader who was not there, and they make "the machinery became the output" a
finding rather than an opinion.

## Distinguish the count you are quoting

Two honest counts over the same corpus — units on the SUBJECT versus units in TOTAL —
reported a few messages apart with no statement that they measure different things
reads as an inconsistency and costs the reader's trust in both. Name the denominator
every time the scope changes.
