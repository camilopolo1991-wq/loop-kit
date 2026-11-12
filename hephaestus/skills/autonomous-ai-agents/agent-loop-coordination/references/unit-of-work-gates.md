# Getting a unit of work past the loop's own gates

A mature loop validates units before it runs them. Those gates are the reason a
hand-executed change is cheaper in the moment and worse afterwards: they are what make a
change auditable, and they only run on a written unit.

## Order of operations

1. **Prove the mechanism in the lower environment first**, using the input shape that
   actually fails in production. A fix proven on a convenient input is not proven, and
   the proof is what licenses the dispatch.
2. **Write the unit at the exact path and filename the role reads.** Check the literal
   name on disk; a system may use `GOAL` where its docs say `GOAL.md`, and a file under
   the wrong name is invisible.
3. **Run the format linter** and require rc 0. Where one exists it typically checks:
   filename, a title naming the unit id, ONE criteria numbering scheme, a budget section
   with actual figures for every ceiling, a hard-limits section, a control requirement,
   and a stop condition. Run its `--selftest` if a PASS looks too easy — a linter that
   cannot fail is not a gate.
4. **Run the executor/constitution gate** and require rc 0. It compares the resources the
   unit NAMES against the host's absolute rules.
5. **Map the write surface against every running peer.** A free concurrency slot answers
   "is there capacity", never "can these two run together".
6. **Dispatch detached and confirm the role is alive by two instruments** — the process
   table and the loop's own leader probe. One instrument agreeing with itself is one
   reading.

## Writing criteria that can actually close

- **Instruct the executor to RE-DERIVE any prepared artifact from current live state.**
  Where an earlier session built a patched file, hand over the recipe and the archived
  original, never the patched file as the thing to deploy. State the assertions
  explicitly: the target node exists exactly once, the marker is absent before, the
  mutated content DIFFERS from the original, the marker is present exactly once after. A
  string replace that matches nothing returns its input unchanged, so an unpatched
  artifact deployed from a stale file looks patched and verifies clean.
- **Pair the fix case with a case that must still fail.** A fallback that SUPPLIES
  missing input and a fallback that MASKS missing input pass the identical success test;
  only the negative case separates them. Name both subjects in the criterion and say
  which outcome means hold.
- **Carry the lower-environment proof into the unit text as the change's positive
  control**: the failing input shape now succeeds where the patch is installed.
- **Cap the mutation numerically and name the rollback.** "Exactly ONE write, on this
  object only; restore from the archived original and HOLD if it fails" is executable;
  "be careful" is not.
- **Quote mandatory flags from the tool's own help output**, including how to obtain any
  value a flag expects. A placeholder the executor cannot resolve will be guessed at.

## A gate false positive is fixed in the unit's WORDING, not in the gate

Constitution gates tokenise quoted names out of rule text, so a rule about a forbidden
schema *inside* a database fires on the bare database name — and a unit that
legitimately reads that database's ordinary tables reports a conflict.

Such gates usually exculpate a mention whose own LINE carries exclusion language. So
name the schema-qualified surface you actually touch and state the exclusion on the same
line. That keeps the prohibition's force and clears the gate.

Do not loosen the gate as part of a production fix. Loosening requires re-running its
true-positive control against a planted instance of the real defect, which is separate
work; card the tokeniser defect and proceed. The same applies to the prohibition you
write INTO a unit: name forbidden objects by role rather than identifier, or the gate
fires on your own hard-limits section.

## A helper's fixed endpoint is a TOOL limit, never an authority limit

When a wrapper returns 404 for an object you believe exists, read the wrapper's
configuration before concluding anything about permission. A helper hardwired to one
environment's API base will 404 every id from the other environment, truthfully and
uselessly.

This misdiagnosis propagates: once one unit records "that surface is outside our
authority", every later unit inherits it and escalates a question that was already
answered by the standing rules. Read the object from the orchestrator's own database and
drive its webhooks directly, then correct the earlier claim explicitly.

Before accepting any "outside authority" line in a held report, re-read the governing
rule. A standing permission that was granted months ago looks identical, in a queue, to
a question nobody has answered.

## Census the whole held pile before answering any single unit

Re-reading one held report's blocker is worth doing; sweeping all of them is worth more,
because the shapes cluster. Classify every held unit by WHAT IT WAITS ON — owner
authority (a privileged write, destructive schema change, spend, a credential), an owner
JUDGEMENT (a value call, an acceptable-cost ruling), a physical act only a human can
perform, or a MEASUREMENT nobody took. Only the first three are the owner's.

The measured distribution on a mature loop: of 68 held units, 17 needed owner authority,
13 needed a judgement, and 7 were waiting on a measurement — while the pile had been
presented to the owner as a single undifferentiated queue for weeks. Handing someone 68
items when 7 are yours to run is the failure, and it is invisible without the sweep.

**A unit whose own report states the recommendation AND its cost as zero has escalated a
measurement.** The giveaway phrasing is "my recommendation is (a) ... cost: ~20
agent-minutes, 0 model calls" sitting under a heading addressed to the owner. Nothing
there needs deciding; the unit ran out of retries and escalation was its only remaining
exit. Those convert directly into continuation units — see the continuation section
below — and closing one is the cheapest throughput available.

**Re-measure every blocker in a held report rather than inheriting its wording.** A
report is a snapshot of the moment the unit stopped, and blockers rot in both directions:
the repository it called dirty is now clean, the authority it called absent was granted,
the version it assumed has moved. Expect a mixed verdict per unit — measured, one held
unit's three blockers resolved to two dead and one live — so retract the dead ones
explicitly in the decision and route around the live one rather than waiving it.

**A held report can MISQUOTE the governing document, and the quote is the whole blocker.**
One cited its constitution as forbidding an entire environment; the live text forbade a
namespace inside a different environment and explicitly PERMITTED the environment under a
named condition. Open the governing file and read the cited lines yourself — a blocker
resting on a misquote is indistinguishable from a real one at report level, and it
propagates to every unit that inherits the claim.

### The census classifier is itself an instrument — control it

Classifying by grepping report headings fails quietly: roles write the same section under
different titles (`Gates waiting`, `Questions for <OWNER>`, `Why held`, `Open`), so a
narrow heading pattern leaves most of the pile unmatched. Measured: a first pass matched
30 of 68 and the remaining 38 defaulted to an unclassified bucket that reads, at a glance,
like nothing is pending.

- **An unparsed report is UNKNOWN, never clear.** Count it in its own bucket and print
  that count beside the results. A classifier that silently drops half the pile produces a
  confident wrong split.
- **Prove the widening with the set it previously missed.** Keep the known-missed ids as a
  literal positive control and assert each one now classifies
  (`assert len(still_missed) < len(KNOWN_MISSED)`), or the pattern edit is inert.
- **Do not quote the split as final while the unknown bucket is large.** Report it as
  indicative with the unparsed fraction stated; the shape is actionable long before the
  numbers are exact.

## Dispatching a continuation rather than re-running the original

A unit that stopped at a retry cap has usually done most of its work. A continuation unit
should:

- cite the original's measurements as CARRIED, with their instrument and date, so the
  executor does not re-derive them;
- scope itself to the ONE open criterion and say explicitly that the original's NOT RUN
  criteria are out of scope and must not be read as part of this verdict;
- carry forward the branch, worktree and rollback path the original left behind;
- keep both readings where the original kept two — a writer's and a reviewer's
  disagreement is information, and collapsing it to one loses the reason the unit held.
