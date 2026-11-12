# Running the first real mutating call against production

For the moment a tested change stops being a replay and writes to real data for the
first time: a re-score, a backfill, a migration row, a recompute. The canary exists to
catch a defect while it costs one record instead of N.

## Why the canary usually catches YOUR bug, not the change's

The change under test has normally been through review and offline testing. The harness
that drives it has been through neither. Expect the first failure to be in the driver,
and build the driver so it says so rather than blaming the change.

A canary that produced a bad record and was read as "the new version is broken" cost a
rollback recommendation that had to be retracted: the driver had sent a 56-character
fragment of a SQL error as the payload, and the model's low score was the correct
answer to that input. The change was never exercised.

## Replay is not live verification

Replaying recorded outputs through new consumer code tests the CONSUMER against those
outputs. It says nothing about whether the live producer still emits that shape. Both
halves need evidence, and "replay-verified" without naming which half is a claim that
covers one.

When only replay is available, say which direction is unverified and let the canary be
the test of the other.

## Driver checklist

Before the call:

1. **Screen every consumed stdout for error markers.** Many clients print `ERROR:` /
   `FATAL:` to stdout and still exit 0, so a wrapper that returns `p.stdout` hands the
   error text downstream as data. Check the exit code AND scan for the markers.
2. **Read the payload's metadata separately from the payload.** One query for
   `length(col)` and `md5(col)`, another for the content.
3. **Cross-check the decoded payload against that metadata** — length equal and hash
   equal — and abort on mismatch. This is the check that catches a corrupted,
   truncated or substituted fetch regardless of cause.
4. **Assert a plausibility floor.** A real document is never 56 characters. An absurd
   length is a defect even when the hash machinery is absent.
5. **Strip framing from encoded column reads.** A SQL client emits a header line and
   wraps long values across many lines; joining everything prepends the header and
   corrupts the value from byte 0. Keep only lines matching the encoding's alphabet.

After the call:

6. **Branch on the body, then on the store.** A 200 with `ok:true` was returned for the
   run that scored nothing real. Re-read the row the call was supposed to write.
7. **Fail on WHOLESALE nulls, and set the threshold from the healthy distribution, not
   from zero.** Partial output written as if it were a verdict is the signature of a bad
   input, and renormalising arithmetic over the surviving fields produces a plausible
   number from garbage. But a system that legitimately omits an unmeasured field will
   trip a halt-on-any-null guard on its first normal record: query the historical
   distribution of nulls-per-row among known-good rows first (`group by nulls_n`), set
   the threshold above the healthy maximum, and name which field is routinely absent.
   One guard set at zero halted a 21-item batch on its second entity, whose single null
   had been present in every scoring that entity had ever received. Re-check the chosen
   threshold against the known-bad record too, so the loosening cannot swallow the
   failure it was built for.
8. **Diff the side-effect counts** against the pre-call baseline, including tables the
   call clears and reinserts; a net change in either direction is a question to answer
   before the second run.

## Prove the driver's guards before trusting them

Run negative controls (bad argument, impossible entity, the previous bug reintroduced)
AND a positive control that exercises the success path up to the mutation. Negative
controls passing is compatible with a driver that aborts on everything — three of them
passed while a decoding defect made every run impossible, and only the positive control
exposed it.

## Driving the batch after the canary passes

Run the items serially through the SAME driver the canary used, append each item's
output to one log, and halt the whole batch on the first non-zero exit rather than
continuing. A batch that logs failures and presses on turns one diagnosable defect into
N records to triage.

Keep the queue in a file and resume from the remainder, so a halt costs only the
unprocessed tail: re-running completed items writes duplicate rows on an append-only
path. Launch detached (`setsid nohup`) and poll for the runner process, because a
foreground call long enough to cover the batch will be backgrounded by the harness
anyway and you lose the exit status.

Re-read the side-effect counters between items, not only at the end. A counter that
returns to baseline after each item is positive evidence the clear-and-reinsert path is
balancing; a drift is a question to answer before the next item runs.

## Scope and stop conditions

Write the stop conditions down before the first call: which field values mean halt, and
what the rollback is. Then honour them — a canary that proceeds past its own stop
condition is theatre.

Where the mutation appends rather than replaces, say so when reporting: the bad record
stays in history beneath the good one, and anything reading the full stack still sees it.

## Check what the consumer actually renders

Whether a bad record is user-visible depends on the read path, not the write path. Read
the deployed consumer's selection logic (latest row, a denormalised column, a join)
before stating whether anyone saw it, and identify the deployed copy by mtime and hash
rather than by picking the first match on disk.
