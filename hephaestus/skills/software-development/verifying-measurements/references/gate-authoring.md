# Authoring a check that can actually fail

Read this when writing or amending an executable gate: a pre-dispatch check, a
review rig, a `--selftest`, or any script whose exit code decides whether work
proceeds. The parent skill covers measuring a system; this covers building the
instrument that refuses on your behalf, which has its own failure modes.

Write one of these whenever a process failure recurs. A gate that exits non-zero
outperforms another paragraph of prose, because prose does not stop a session
that is already confident.

## Procedure

1. **Define three exits, not two.** `0` proceed, `1` refuse with the reason
   named, `2` nothing checkable. **Exit 2 is never a pass** — say so in the
   output text, or a caller reading only the code will treat an unparseable
   input as clean.
2. **Derive the fixture from a captured real input.** Copy an actual artifact,
   trim it, use that. Never build it from the documented shape.
3. **Write one selftest case per defect, each asserting the exit code it should
   produce.** A selftest that exercises only the happy path is decoration.
4. **Run the finished gate against the entire corpus of known-good inputs before
   trusting it.** This is the step that exposes a rule which is really a
   vocabulary check.
5. **Plant a live violation, require the gate to catch it, revert.** A reverted
   plant is the only thing that makes a later zero reportable.
6. **Point to the gate from the skill that governs the work**, with its exact
   invocation. A gate nobody knows exists is dead weight.

## Pitfalls

**Calibrate a new rule against every known-good input you have; a rule that
fires on most of them is measuring your vocabulary, not the property you
meant.** One plan-shape rule asking whether any task described an end-to-end
outcome fired on 56 of 60 real plans, while the layer-ordering rule shipped
beside it fired on 0. A gate that refuses 93% of good input trains its reader to
ignore every verdict it produces, including the true ones. Either require a
second independent signal before the rule fires, or delete it — and record the
corpus fire-rate in the code so nobody re-adds it.

**Accept every formatting variant of the marker you key on, or the gate silently
stops gating.** A check anchored on a line-initial `RECON:` scored zero recon
lines against a document whose four recon lines were bullets (`- RECON:`), and
reported a clean "nothing to recon" verdict on a document full of recon. Allow an
optional leading bullet or list number, and add the variant as a selftest case.
The same applies to tables versus lists, and to any marker a human will reformat.

**Prove the planted violation actually changed the artifact before trusting a MISSED
verdict.** A plant applied by string replacement is a silent no-op whenever the target
phrase carries markdown emphasis, a line wrap, or any character not reproduced exactly —
the gate is then handed the ORIGINAL text, correctly passes it, and the result reads as a
hole in the gate. Make `assert mutant != original` the first line of every plant, and
re-derive the phrase from the file's real bytes with `repr()` of a slice around the anchor
rather than retyping it from a rendered view. Three plants in one session were reported as
gate gaps and all three were unapplied mutations; acting on that reading sends you to
repair a sound instrument. The trap in reverse is worse — a plant you assume failed to
apply but did is a real gap dismissed as a formatting quirk — so print the applied count
alongside the caught count.

**Scope a presence check to the section that BINDS, or a duplicated phrase makes the gate
unfalsifiable.** Headers, summaries and constraint blocks restate the same sentence, so a
document-wide search for it still matches after the binding copy is deleted, and the check
passes on an artifact whose rule is gone. Slice from the governing section's heading to the
next heading and search only within that, then keep a plant that removes the binding
instance alone. The tell is one check that survives every mutation you can devise while
its neighbours all fire.

**A gate's own author is its worst-case user.** You will write the next artifact
in whatever format you had in mind, which is exactly the format you already
handled, so your pass tells you nothing about anyone else's input. Run it over
artifacts written before the gate existed.

**A false negative is the dangerous half.** A false positive costs a minute; a
gate that blocks correct work gets switched off, and then nothing is checked.
When a gate refuses something you believe is correct, measure which of the two is
wrong before amending either.

**When a gate flags correct text, repair the gate's CLASSIFIER rather than its
threshold, and prove the real defect is still caught in the same run.** An
existence check that resolves every slash-prefixed token on the filesystem
refuses an artifact for naming an HTTP route, an API endpoint or a remote
procedure — verified by calling it, never by `stat()` — and the pressure is then
to delete a correct sentence or relax the check wholesale. Extend the existing
not-a-path branch instead of adding a parallel one, and in the same output show a
genuinely absent path still refused; a fix shipped without that pair converts a
false positive into a false negative. Where a gate's non-path categories are
enumerated, read that list first — the category you need is usually already
there, one entry short.

**A gate that demands a kind of evidence will accept the kind you find easiest to
produce; check which kind it actually got.** A recon requirement satisfied
entirely by database reads can pass its line count while nobody looked at the
surface the work is about, so require at least one assertion naming an inspectable
mechanism — the rendered page, the source file, the tool's own help output — and
name that requirement in the refusal text. When it refuses your own artifact for
this reason, go and look rather than adding a line that satisfies the pattern:
the one such refusal in this corpus turned up two consumer-side tables the
artifact had entirely omitted.

**An amendment can weaken a proof while looking like tidying.** After repairing
one criterion, re-read the siblings for the same flaw — a mechanical fix to a
design defect in one task routinely leaves the identical defect in the next
acceptance criterion, and the diff looks like housekeeping.

**A verdict of "not applicable" must be stated, not omitted.** Where a gate
covers a surface this piece of work did not touch, the report says so and names
what it touched instead. A silently skipped section is indistinguishable from a
pass, and that is the gap an omitted visual check hides in.

## Reporting a batch of gates

Run the relevant gates as a batch before any dispatch or handover and print each
exit code separately. A single summary word hides which one abstained: a batch
reading `executor 0, procedure 0, shape 0, recon 2` is four distinct facts, and
the `2` means that gate had nothing to judge rather than that it approved.
