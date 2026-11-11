# Verifying an install/rollback script before authorising it

For the case where a guarded change is delivered as a script the owner runs by hand on a
live host. The script is usually well built — staged shas, pre-checks, a saved rollback,
write-then-verify per step. That structure makes it easy to approve on the strength of
its own output, which is exactly the trap.

The question is not "did the pre-checks pass". It is "which code paths has anything
actually executed, and does the rollback work".

## A redacting transport corrupts byte-faithful backups

Where every command's output passes through a secret-redacting wrapper, a backup taken by
encoding a value and decoding it locally can be silently mangled: the redactor scans the
*encoded* text, matches a token-shaped run inside it, substitutes a marker, and the decode
then fails or truncates. The surrounding script can report success while the backup file
lands at zero bytes.

Base64 is the common choice and the vulnerable one — its alphabet overlaps the shapes
secret scanners hunt for, so a JWT-ish pattern matches the encoding itself.

**Encode as hex and refuse on anything that is not hex.** `[0-9a-f]` cannot match a
redactor's token patterns, and a strict character check turns a redaction into a loud
failure instead of a corrupt artifact:

```sh
hexq() {            # byte-faithful read of one text value through a redacting transport
  local o h; o=$("$SQL" -c "$1") || return 1
  h=$(printf '%s\n' "$o" | sed -e '/^\[wrapper/d' -e '1d' | tr -d '\n ')
  [ -n "$h" ] || { echo "hexq: empty result, refusing" >&2; return 1; }
  case "$h" in *[!0-9a-f]*) echo "hexq: non-hex (marker or truncation), refusing" >&2; return 1;; esac
  [ $(( ${#h} % 2 )) -eq 0 ] || { echo "hexq: odd length, refusing" >&2; return 1; }
  printf '%s' "$h" | xxd -r -p
}
```

Pair every such reader with `|| { rm -f "$out"; fail_out ...; }` so a failed read deletes
its partial file and stops the run before the first write, rather than leaving a
zero-byte backup that a later verify step trusts.

**Prove the reader both ways before the real run.** Positive: it recovers the value at the
expected byte count and hash, and the result parses. Negative: fed the encoding that
triggers the redactor, it exits non-zero and writes nothing. A reader proven only in the
positive direction is a check that cannot fail.

**Diagnose which values are affected with a marker count, not a guess.** Run the encode
query for each value and count redaction markers in the output. The value that fails will
show markers; a sibling value that succeeds shows zero. That contrast is the whole
diagnosis and it takes one command per value.

## A dry run does not exercise the steps it skips

A dry run that prints `[DRYRUN] would save ...` has not called the function that saves.
So "all pre-checks PASS" covers only the read-only pre-check block; every write path and
every helper used solely inside a write path is still unexecuted. When a defect lives in
the backup reader, the dry run passes clean and the real run dies at the first write.

State this explicitly when handing a dry run to an owner: name which steps were exercised
and which were only described. The dry run's value is the pre-check block and the plan,
not assurance about the writes.

**Dry-run message text is prose and drifts from the code.** After a fix changes the
mechanism, the `[DRYRUN] would ...` string often still describes the old one. Read the
real call sites, not the narration, when deciding which version of a script you are
holding — and treat a mismatch between them as a documentation defect to report, not as
evidence the fix is missing.

## Verify the rollback independently, before the forward action

A shared helper with a defect frequently appears in both the install and its restore
script. Before concluding the rollback is unsafe, determine whether the restore
**invokes** the helper or merely **defines** it:

```sh
grep -n 'helper' restore.sh                 # all occurrences
grep -nE 'helper[[:space:]]+["/$]' restore.sh   # invocation sites only
```

A definition with no call site is dead code and does not affect the rollback. Reporting it
as a live risk blocks a safe recovery path for no reason.

Then confirm what the restore actually reads from. A restore that reads the saved backup
**files** and validates each one before writing — manifest checksum, then a hash per file,
each with an explicit refuse-and-write-nothing branch — is sound regardless of how those
files were produced, provided the producing reader is itself proven. Quote the validation
chain when you report it.

## After the run, verify from outside the script

The script's own `VERIFIED` lines are the author's assertions. Re-measure the end state
with independent queries: the changed row's version and content hashes, each live
artifact's version identifier against its active identifier, the count and hash of the
rows that were supposed to stay untouched, and the repository's dirty-path count against
its known baseline.

**Expect a write step to leave artifacts where its own policy forbids.** Publish and
export helpers commonly drop files into a tracked tree as a side effect, so a run can
raise the dirty-path count even when the change itself is clean. Re-count against the
baseline afterwards and move strays to scratch; never let them reach a commit.

**A post-run informational step that fails is not a clean post-run check.** When the
script's own "what ran during the window" step errors out, the window is unobserved —
run the equivalent query yourself and say which instrument produced the answer, rather
than treating the step's absence as silence meaning nothing happened.

## Identifiers truncated in script output are not identifiers

Script logs abbreviate (`MZHBiX...`). Reconstructing a full identifier from a truncated
log and querying it produces a 404 that looks like a missing or broken artifact. Pull the
full value from the script source or a live listing, and keep a known-bad identifier as a
control so a genuine 404 is distinguishable from an invented one.
