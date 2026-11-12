# Verifying a derived artifact

A derived artifact is anything you produced by summarising, rolling up, or
classifying someone else's measurements: a report, a roll-up of parallel worker
outputs, a triage, a handoff. The source numbers were measured correctly and the
artifact is still wrong, because the error enters in the transcription, the
re-labelling, or the classification rule.

The main skill covers probing a live system. This file covers checking the thing
you wrote about it.

## Reconcile every roll-up against each source's own stated totals

Parallel workers each publish a tally. Sum the tallies, then verify the sum
against the sources rather than against your own arithmetic:

1. **Re-extract each source's totals programmatically** from its file, and diff
   against the numbers you transcribed. Hand-copying seven tables is where a
   digit flips, and the flip is invisible once it is inside your document.
2. **Prefer a source that states its own total row.** When a worker publishes
   both per-item counts and a `total` line, check the line against the column
   sum; a mismatch is the worker's bug and you want to find it, not inherit it.
3. **Account for every row in the input set.** If the inputs number N and your
   output numbers N-2, locate those two before shipping. A real answer exists:
   merged duplicates, renamed entities, items legitimately out of scope. "Close
   enough" means you do not know which.
4. **Check coverage, not just totals.** List which inputs appear in no output
   group, then confirm from the upstream data that each was correctly skipped.
   Absence from a roll-up has two causes and only one is benign.
5. **Parse per source SHAPE, and print the per-source row count before
   aggregating.** Independent authors use different table schemas for the same
   data. One parser run across all of them silently yields rows from the one
   schema it fits and zero from the rest, which reads as "those sources found
   nothing" rather than "my parser matched one layout". A per-source count of
   `{A:0, B:0, C:13}` is the tell.

## A label in your summary may not mean what the same word meant upstream

When a pipeline has a mechanical stage followed by a judgement stage, the
judgement stage only sees what the mechanical stage passed through. Summing the
judgement stage's `ENV` count and presenting it as "the environment differences"
understates the real figure by everything the mechanical stage already resolved
and never forwarded.

**For every category in a roll-up, state which stage produced it and what it
excludes.** If two stages both emit a category with the same name, report both
numbers or report their sum explicitly. Carrying one stage's count under a name
readers will read as the total is a factual error, not a presentation choice.

The same trap applies to a count of "identical" or "clean" items: identical by
one dimension (node contents) is not identical by all dimensions (wiring,
settings, flags). Say which dimension the number covers.

## Classify from the record, never from the headline

Pattern-matching a title, a first line, or a status field is a fast way to
produce a confident wrong taxonomy. Items that look alike at the headline level
routinely differ in what they actually need.

**Before classifying a set into act / defer / discard, search the system's own
log or journal for each item.** An item whose summary looks inert often has a
log line naming the exact decision it waits on. A triage built from headlines
alone will bury real open questions inside the discard pile, and the discard is
irreversible in a way the mistake is not.

When you must classify by pattern because reading everything is too expensive,
say so in the artifact, give the approximate counts as approximate, and commit
to reading an item in full before acting on it individually.

The same rule governs acting on a document rather than classifying it: **read
the CURRENT version in full before responding to it.** Reading only the head of
a status report missed a third open question below the fold and answered a
question that had already been superseded. What a document asks is whatever its
latest revision says, not what you remember it asking.

## Mutation-test the checker, and build mutants from real bytes

A self-review script that cannot fail is worse than no review. Prove each check
fires by planting the corresponding defect and requiring the check to flip.

```python
muts = {
    "claim removed": t.replace(real_line, ""),          # real_line read FROM t
    "verdict flipped": t.replace("OPTION A", "OPTION C"),
    "planted secret": t + "\n" + ("d" * 64) + "\n",
}
for name, m in muts.items():
    assert m != t, f"MUTANT NEVER APPLIED: {name}"   # non-negotiable
    assert review(m), f"MISSED: {name}"
```

- **`assert m != t` is the load-bearing line.** A `str.replace` whose needle is
  absent returns the string unchanged and the mutant silently passes, scoring a
  check that never ran. Prose wraps across lines, so a sentence you can see in
  the rendered document is frequently not a contiguous substring of the file.
- **Build each needle from the file's own bytes** -- find the line containing a
  keyword and mutate THAT -- rather than retyping the sentence from memory.
  Curly quotes, markdown emphasis and line wrapping all defeat a retyped needle.
  When the assert trips, print `repr(text[i-60:i+80])` around the anchor to see
  the exact newline and indent before rebuilding.
- **Match the instruction, not the explanation.** A check that greps for the
  paragraph explaining why a figure is wrong still passes when a mutant flips
  the directive underneath it to "the figure is correct". Assert on the
  imperative sentence a reader would act on, and add a contradiction check for
  the reversing sentence, since an artifact can GAIN a line that negates a rule
  without removing it.
- **Count your anchor's occurrences before trusting it.** An anchor that appears
  in both a title and a constraints list is satisfied by the title alone, so a
  mutant deleting the constraint passes. Measured: a goal whose scope limit
  appeared twice let a "prod writes are fine" mutant through on the first round.
  Anchor on the form that carries the meaning (the full constraint sentence, not
  the bare phrase), or require the count you actually need.
- **Apply a structural pattern only to the structural part.** A verbless-bullet
  detector that tested whole lines against a verb allowlist found nothing,
  because values like `stale` and `rejected` were themselves in the allowlist.
  Split on the delimiter and test the LEFT side: text after a colon is a value,
  not a predicate.
- **ONE broken pattern masks EVERY mutant, and a perfect score is the tell.** If a
  check can never match, it reports its own `MISSING` label for the clean file AND
  for every mutant alike, so all of them score CAUGHT while nothing is being tested.
  Two guards: `assert not review(t)` on the UNMUTATED file first, because a clean file
  that reports a defect means the checker is broken rather than the file; and read
  WHICH label each mutant produced, not just whether the list was non-empty. The mutant
  that deletes the decision must report `MISSING decision`. Every row showing the same
  unrelated label identifies that label's pattern as the bug.
- **Do not strip data characters when normalising markdown.** Flattening with
  `re.sub(r"[*`|]", "", s)` turns a measured value like `52|1|59` into `52159`, so the
  pattern for it can never match -- which is exactly the masking defect above. Strip
  only what the markup adds (emphasis and backticks) and keep every character that can
  appear in data: pipes, slashes, dots, colons.
- **A verify subcommand may only read the envelope, not the payload.** `git bundle
  verify` reports "records a complete history" for a bundle truncated to 5% of its
  size, because it parses the ref list at the head of the file and never the pack. Before
  trusting any tool's own `verify`, feed it a deliberately corrupted copy of the real
  artifact; if it passes, the proof has to be a full restore-and-recount instead. Run
  such a control from an environment where the tool can work at all, since an
  environmental error ("need a repository") is returned identically for a good input and
  a broken one and reads as a corruption finding.
- **Run the clean pass twice and report both.** Any fix resets the count; one
  clean pass after an edit is the edit, not a review.

## Edit a live record by CONTENT, never by line number

A line number in an instruction is stale the moment anything above it changes. An
instruction to retire "line 96" was written when the stale entry sat there; by execution
time it had moved to 97 and line 96 held a must-not-touch entry, so the edit as written
would have destroyed the wrong record.

Match the line's text, and assert the occurrence count before writing:

```python
assert s.count(marker) == 1, f"expected 1 occurrence, found {s.count(marker)}"
```

Then verify the edit landed with three readings, not one: the false string now occurs 0
times, the replacement occurs 1 time, and an unrelated line still occurs 1 time as the
untouched control. Check the file's line count is unchanged when the edit was meant to be
in-place. Back the file up first when it is a live record, and check whether the bad
content was ever committed -- an uncommitted false claim has published nothing and that
changes how urgently it must be reported.

## Protect the content that brevity tends to eat

When the same script enforces a length or style budget, exempt by name:
retractions of your own earlier claims, the single open question only the reader
can answer, and any recommendation stated with its cost. These are the first
things a word-count rule deletes and the last things a reader can afford to lose.

**Exempt identifiers from style rules too.** A house rule banning a punctuation
mark applies to prose a human reads, never to a string that must match a system:
node names, file paths, config keys and database identifiers are copied
byte-for-byte. Sanitising a punctuation mark out of a node name broke the
identifier and the executor handed it back. When a style rule meets an
identifier, the identifier wins.
