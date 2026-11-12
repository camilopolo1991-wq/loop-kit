# Comparing two environments

For when the question is "what is different between staging and production" and
there is no version control underneath them -- two databases, two deployments,
two config trees that drift freely.

## Do not assume a direction

"Staging is ahead of production" is an assumption, not a property. Where nothing
enforces a promotion path, drift has no preferred direction, and production
routinely carries fixes that were written directly into it and never existed
upstream.

**Diff in BOTH directions before promoting anything, and name what the target
would lose.** A promotion that copies the "newer" side over the other can delete
working code in the target. Treat "which side is ahead" as a per-item question,
never a per-environment one.

A shared component called by both environments has the largest blast radius;
rank it above a leaf when deciding what to reconcile first.

## Normalise before diffing or everything is a difference

Raw byte size and raw equality are almost useless as signals. Strip, in this
order, before comparing:

- key ordering (serialise canonically)
- empty option objects and other defaults the UI writes but does not use
- positions, ids, and any surrogate key regenerated on write
- condition ids and other per-instance identifiers

Then hash the canonical form. Without this, nearly every pair reads as
different and the real differences are invisible inside the noise.

**Validate the normaliser with two controls:** one pair known to be identical
must come back IDENTICAL, and a one-character mutation of that same pair must
come back DIFFERENT. A differ that cannot return IDENTICAL is as broken as one
that cannot return DIFFERENT.

## Compare what runs, not what is saved

Many systems keep a draft separate from the released version. Compare the
released artifact on both sides, and flag any item where you had to fall back to
the draft because nothing is released. Reading the draft and describing it as
production behaviour is a silent, confident error.

## Classify each difference, do not just count them

Counts alone drive the wrong decision. Sort every difference into:

- **ENV** -- hostnames, credentials, database names that SHOULD differ
- **COSMETIC** -- ordering, defaults, whitespace
- **A_AHEAD / B_AHEAD** -- one side has logic the other lacks
- **DIVERGED** -- both sides changed the same thing differently
- **UNRESOLVED** -- not decidable without a measurement you could not take

DIVERGED and UNRESOLVED are the ones that need a human. Never silently merge a
DIVERGED item; it has two authors with two intentions.

## Node-level sameness is not sameness

Comparing the units (functions, nodes, keys) misses the wiring between them and
the container-level settings around them. Diff connections, settings and
enabled/disabled flags separately -- items that are identical unit-by-unit are
frequently wired differently or have a different error handler attached, and a
missing error-handler setting is exactly how alerting dies silently.

## Look for the hazards a diff does not label

While classifying, actively scan for these; they do not announce themselves:

- **Privilege asymmetry.** A lower environment holding a HIGHER-privileged role
  or credential than production, especially on a shared secret.
- **Hardcoded peer addresses.** A literal host or port in one environment's code
  means copying that item to the other environment points it at the first one.
- **Disabled flags.** An item disabled on one side only: promoting it as-is
  silently turns the feature off in the target.

## Report the disagreements rather than resolving them by guess

When two independent passes label the same item differently, keep both readings
and name the measurement that would decide it. If that measurement was refused
by a guard, say the claim is conditional. Do not route around the guard, and do
not pick the more convenient label to make the table tidy.

## Items with no counterpart are their own finding

Entities present in production with no counterpart in staging cannot be tested
before deployment -- there is nowhere to test them. Separate them by evidence
into dead (no executions, no callers), deliberate (production-only by design:
data-deletion jobs, backups), and genuine testing gaps. Use execution counts and
caller counts, not opinion.

Check each side's retention window before claiming anything about history: if
one side keeps 12 days and the other 2, any statement about older activity on
the short side is unmeasurable, not false.
