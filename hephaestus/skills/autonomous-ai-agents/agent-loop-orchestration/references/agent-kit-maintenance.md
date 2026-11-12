# Editing the loop's own kit: role files, preambles and detectors

For changes to the machinery rather than to a goal — role definitions, the shared
goal preamble, the tamper detector, the dispatch queue. These edits are uniquely
dangerous because they are the instruments every other goal's correctness depends
on, and a bad one reads as fixed while silently voiding every window.

## Before proposing any addition: measure what the kit already says

The default assumption should be that the rule is already there in different
words. Independently-written role prose never matches a central file's vocabulary,
so a keyword probe built from your phrasing understates coverage badly — one scored
four role files at 1/8 and 2/8 while reading them showed every role stated the rule
in the form it needed.

Procedure: grep for the CONTENT of the rule using each role's own likely phrasing,
then read the files, then decide. Report per-file scores with the pattern list
beside them, so a reader can see whether a low score means a gap or a bad probe.

A second copy of doctrine is worse than no addition: the two statements drift, and
an owner who asked for a better kit gets a redundancy they will reject.

## Wire through the loading mechanism, not by pasting

Role definitions usually carry a `skills:` frontmatter key. That key is the wiring.
Pasting preamble prose into each role file bypasses it and creates the duplication
above. Check for the key before designing any distribution scheme.

A shared preamble that is referenced by goals but by no role file is only reaching
the windows whose goal text happens to cite it; measure how many goals cite it and
how many transcripts actually pulled it before calling it wired in.

## Install only when no leader is running, and make the script enforce it

Every kit path is under the watched tree. Begin the install script with a process
check that aborts nonzero when any leader is alive, so the rule survives being
forgotten at 2am. Back up each target to a dated sibling, and skip the backup when
one already exists so a re-run cannot overwrite the true pre-edit state.

## The kit exists twice; patch and verify both

These kits are commonly a tracked source tree plus a live install. Patching one and
testing the other is a check that cannot fail. Copy the edited file to the tracked
copy and compare hashes in the same script, printing both. When they diverge, a
routine reinstall silently reverts the fix — record that where whoever reinstalls
will read it.

## Changing a detector is a permission change, not a tidy-up

A patch that relaxes a path test will look like two lines. It is not: it moves the
boundary of the mechanism guaranteeing evidence integrity across concurrent goals.

Rules that apply to every such change:

- **Locate the defect by reading the classifying function, and quote it.** The
  common shape is an attribution helper that returns "not a peer" for any path
  failing a narrow structural test — for example requiring the second path segment
  to be the evidence directory, which silently excludes a peer's own plan and report
  files at the goal root, and any shared ledger the goals append to. Those are the
  two writes every goal makes, so the detector quarantines precisely when goals are
  doing real work.
- **Never widen blanket.** An exemption is the mirror image of a guard: a guard is
  worthless if it cannot fire, an exemption is dangerous if it silences everything.
- **Require a named negative case per excused path.** For each path the new rule
  lets through, name a modification a peer could make there that must still be
  caught, and prove it caught with the full number of windows open. Include at
  minimum: a modification to a peer's goal file, to a baseline or existing check
  artifact, a forged completion marker that must not free a cap slot, a symlink
  anywhere under the evidence tree, a write outside every goal tree, and a deletion
  of a path present in the baseline.
- **Quantify the symptom before and after.** Build a sandbox with several goals
  writing their plan and report files and appending to the shared ledger, and count
  windows tripped on each side of the patch. A fix that does not move that number
  has not addressed the cause.
- **Re-run the whole negative set after any amendment**, however cosmetic. A
  mechanical tweak during review can weaken a proof while looking like tidying.
- **Read the existing self-test and report how it asserts** before changing
  anything. A change that leaves an unknown test green proves nothing.
- **Sandbox via the detector's own root environment variable**, never against the
  live goal tree, and avoid contending with the live exclusive lock.
- **Stage, do not install.** Hand the owner the patch and the proof.

## Reconcile caps that were set independently

Verification layers and agent runtimes each carry a concurrency number, set by
different people at different times: a detector's documented cap on simultaneously
open windows, and the runtime's max-concurrent-subagents setting. They are routinely
an order of magnitude apart and neither references the other. Find both, write the
binding one where a dispatcher reads it before choosing a width, and do not raise
either as a side effect of another change.
