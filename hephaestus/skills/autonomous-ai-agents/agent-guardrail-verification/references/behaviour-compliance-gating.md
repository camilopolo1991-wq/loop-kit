# Measuring whether agents follow a procedural rule, and when it can become a gate

Covers the case where the rule is not "do not touch X" but "load the governing rules
BEFORE you touch X" — skill loading, checklist reading, archive-before-write. The
owner's usual request is a reminder re-sent every message or a supervising agent; the
parent skill's hook section answers why both are category-1 and what the enforcing shape
is. This file covers the measurement that must come first, because the census decides
whether a gate is possible at all.

## Count EXECUTED commands, never tool-input prose

A census keyed on "this session's tool inputs mention the surface" counts task cards that
quote a wrapper, reviewer notes that name it, and plans that forbid it. Only a command
that actually ran is a touch. Mechanism: the same mention-versus-act indistinguishability
that sets the false-deny budget in `dispatch-payload-guarding.md`, moved from guarding to
measuring — and it inflates in the direction that makes the problem look worse than it is.

Restrict the touch test to the shell tool's command field, strip any wrapper prefix first,
and report the prose count beside the executed count as a delta so the inflation is
visible. Measured: one agent/surface cell carried +30 prose-only sessions against 50
executed ones, and the headline miss rate for another fell from 58% to 51% once prose
stopped counting.

## Read one real record's keys before believing any rate

A structured-field sweep that returns 0% or 100% uniformly across every actor has almost
certainly read the wrong key, not discovered total non-compliance. Measured: reading a
tool-use payload's `command` field where the runtime writes `skill` produced a flat 100%
miss on three surfaces, minutes after a separate sweep had counted 1574 genuine loads —
two results that cannot both be true. Dump `sorted(input.keys())` and one serialised
record from a real transcript, then write the extractor.

Assert the positive control before printing any rate: total loads must be non-zero, and
at least one actor/surface pair must show a HIT. A census where nothing complies cannot
distinguish real non-compliance from a broken extractor.

## Measure order-divergence before building the order-sensitive instrument

Two questions look different and usually are not:

- **session-total** — was the governing rule loaded anywhere in this session?
- **order-sensitive** — was it loaded *before* the first touch of that surface?

Only order-sensitive is enforceable at the point of action, so it is tempting to build it
first. Count the divergence instead: sessions that loaded the rule only AFTER the touch.
Measured: 2 late-loads across 1013 first-touches, so the cheap session-total census was
adequate and the expensive instrument changed nothing. Report the late-load count either
way — it is the number that justifies which instrument you used.

## A by-design exclusion needs its own control

Excluding an actor because the rule does not apply to it is legitimate and often correct.
It is also the step where a role's self-description gets promoted to fact. Two guards:

- **Record the measurement that justified the exclusion in the code**, beside the
  exclusion, so a future reader can overturn it with a newer measurement rather than
  guess at the reasoning.
- **Report when an excluded actor DOES comply.** A single compliant session means the
  design assumption moved and the exclusion needs re-deriving. Measured: an orchestrator
  role excluded on the strength of 135 surface touches with 0 loads and no exceptions was
  then observed loading two of the tracked rules in 8 sessions — caught only because the
  exclusion printed its own counter-examples.

**A role definition is prose, so verify what the role EXECUTES before accepting its
self-description as scope.** The inference "a 100% miss rate with no exceptions means the
rule is inapplicable" is sound about applicability and says nothing about the facts — the
correct reading is that the rate tells you to go and check what the actor does, not what
it is for.

**Then apply the executed-versus-prose classifier to the divergence itself, before
reporting it.** A role-boundary breach is the highest-stakes number a census produces, so
it is the one most worth a second instrument — and an unanchored write-verb regex inflates
it hardest, because role documents and task cards discuss writes constantly. Measured, in
order: an order-sensitive pass reported an orchestrator executing 20 writes against two
surfaces its own document says it never edits, and a sibling pass reported 10 more by the
read-only measuring and reviewing roles. Re-classifying every hit by whether the command
shape was *executing* reduced those to **3** real product writes of 48 regex hits (29
bookkeeping prose, 11 plain false positives, 5 real writes in the role's own granted
journal/state shape) and to **zero** for the read-only roles — whose hits were all
`grep -E 'put|--write'` over reports plus a command pasted beside its own `Result: DENIED`
in a guard-denial test.

So: anchor the write pattern at a statement boundary, classify each hit as a real product
write / the role's own granted bookkeeping / a mention, and require a positive control
naming the role that is SUPPOSED to write (the implementing role returned 26, which is
what licenses believing a 3 and a 0 elsewhere). Report the surviving count with the
classification beside it. A boundary breach reported at 7x and corrected in the next turn
costs more trust than the breach.

Whatever survives classification is a finding about the system's real behaviour and
outranks the compliance number it came from. Report it separately rather than folding it
into a rate.

## Check whether the rule can be PRELOADED before designing any gate

The cheapest fix is usually not enforcement. Where the runtime can attach the governing
rules to a role declaratively — a frontmatter `skills:` list, a system-prompt include, an
always-on context block — compliance becomes deterministic by construction and no gate,
reminder or supervising actor is needed. Check for that mechanism before costing anything
else.

**Diagnose by comparing the compliant actor's wiring against the others', not by reading
trigger text.** Two plausible causes get investigated first and are usually both wrong:

- *The rule's trigger wording is too vague to fire.* Measured false: every skill
  description already ended in an explicit trigger clause ("Load before any database
  task", "Load before touching any workflow").
- *The role is never told to load it.* Measured false: all three non-compliant role
  documents carried an explicit instruction naming the surface skill and the tool to load
  it with, one of them as step 1.

The only structural difference was the delivery mechanism. The compliant role preloaded
four rule-sets in frontmatter and loaded them ~always; the three non-compliant roles
preloaded one unrelated rule-set and received their surface rules by runtime instruction,
which they followed 49–81% of the time. **Preload is deterministic; an instruction
competes with the task for attention and loses** — the same category-1 weakness the parent
skill describes, arriving as a compliance rate.

Apply it selectively and price it, because preload is paid on every dispatch including
ones that touch neither surface:

- Preload for the role that makes the change and the role that must catch it — they carry
  the worst rates and the highest cost of acting unaware.
- Leave the highest-volume, best-performing role on instruction, where the context cost
  buys least.
- **Measure the context delta before and after** (one case went 2632 B to 11435 B per
  dispatch, ~+2200 tokens) and state it, so the trade is a decision rather than a guess.
- Verify the frontmatter still parses, the loading tool is still granted, any guard hooks
  are intact, and **every named rule-set exists on disk** — a preload of a missing file
  can break the role at startup. Control it with a deliberately absent name.
- The after-rate is UNMEASURED until a dispatch of that role actually runs. Say so in the
  commit rather than letting the change imply success, and re-measure on the next run.

## Disqualify a candidate gate on its firing rate, before arguing correctness

Compute what fraction of real calls the gate would deny, and decide against a threshold
fixed in advance. A gate that fires on roughly a third of invocations is an outage with a
justification, and one that fires on half of all sessions is ignored like any other noisy
alarm — in both cases the gate is removed and the rule ends up enforced by nothing.

Measured: an order-sensitive skill-load gate would have denied 361 of 1013 first-touches,
36%. Narrowing the same rule to write verbs only left 34 cases — small enough to inspect
individually and plausibly shippable. This is the parent skill's "scope it to writes on
named surfaces" rule arriving as a number: the read-mostly spellings are what generate
the volume, and reading with the rules unloaded is survivable where writing is not.

When the rate disqualifies the gate, the honest artifact is the census as a reported
trend plus the narrowing that would make it gateable. Do not ship it as a WARN to feel
productive: a warning firing on a third of calls trains its reader to ignore the one time
it matters.

## Report shape

Lead with absolute misses at a minimum sample size (n≥20), not with rates — a 100% rate
on n=3 otherwise leads the table and the real gap hides below it. Then:

- the executed count and the prose delta per actor/surface pair,
- the late-load count, naming which instrument it justified,
- every by-design exclusion with its justifying measurement and any counter-examples,
- the candidate gate's firing rate, the threshold it failed, and the narrowing,
- unattributed sessions as their own line, never silently dropped.
