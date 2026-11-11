# Building a fixture set that can actually answer the question

Three archetypes x ten byte-identical replicas, created through the real intake path.
Every rule here cost either a wasted batch or a number that had to be withdrawn.

## Create the first subject through the UI, the rest through the endpoint it revealed

Drive the real form by hand ONCE: open it, fill every field, submit, and watch the
success indicator. Capture the request it makes by wrapping `window.fetch` before
clicking submit, so you learn the endpoint, the exact payload shape, and the field
names the form actually sends. Then post that identical shape for the remaining
subjects.

This is not a shortcut around verification — it is the same code path, the same auth,
the same server-side validation. What it skips is repeated typing, which tests nothing.
Say so plainly if asked whether the set was "made in the browser": one by hand to
establish the shape, the rest through the shape it proved.

Doing the first one manually is also where intake defects surface. Measured: an
autocomplete displayed a selected country while the captured request body carried
`country: ""` — the picked value never reached the payload. No amount of API-level
batching would have found that, because the harness never used the widget.

## Prove replica identity by HASH, with the name stripped

Ten replicas cannot be byte-identical if the subject's name is embedded in the text
(transcript speaker labels usually must match the subject name or the parser fails).
So the raw hashes legitimately differ, and a naive "distinct md5 = 10" reads as a
broken fixture set.

Assert the right thing instead: hash the text with the name REPLACED by a constant and
require exactly one distinct value per archetype per stage.

```sql
select count(distinct md5(t.body))                          as raw_md5s,
       count(distinct md5(replace(t.body, c.name, 'SUBJ'))) as stripped_md5s
```

`raw=10, stripped=1` is the proof. Report both numbers so the difference is explained
rather than looking like an inconsistency.

Apply the same check to whatever upstream summary feeds the first stage. If the
generator reads a screen summary plus a job description, the summary must be identical
too — letting it vary measures input variance and calls it model variance.

## Browser-side batch loops die on the eval timeout; the database is the authority

A long sequential loop inside one page-evaluation call hits the automation daemon's
response timeout (seconds, not minutes) and the call raises while the page keeps
working. The results are then unreadable from the raised call even though the writes
landed.

Two consequences:

- **Fire and do not await.** Start the loop in a promise, return a `queued N`
  acknowledgement immediately, and poll progress in a later call. Counters stored on
  `window` are lost on any navigation or reload, so never treat an empty counter as
  zero work done.
- **Count the rows in the database, not the harness's own tally.** After every batch,
  group by archetype and compare to the intended count. That number is correct across
  timeouts, reloads, and lost sessions.

A duplicate-rejection status (409) on a subject you believe is missing means an earlier
attempt DID land before its call raised. Re-check the rows before re-queueing.

## A short-lived session will expire mid-batch; re-auth and resume

Magic-link or short-TTL app sessions drop after a few minutes of batch work, and every
subsequent create returns 401 from the same code that was working. Re-authenticate and
resume from the database count rather than from the start; the created subjects are
already there.

A relative-URL fetch also fails outright (`Failed to parse URL`) once the page has
navigated to a blank or error document — use an absolute origin and confirm the current
URL before each batch, because that symptom is indistinguishable from a broken endpoint.

## Build the runner resumable from the start

For each stage, derive the pending list from a `not exists` query against the artifact
that stage produces, and append each result to a JSON file on disk as it completes. The
run then survives interruption, re-running is free, and `status` is a real query rather
than a memory of what you think happened.

That structure also makes an idempotency skip legible: a stage answering
`{"ok":true,"skipped":true,...}` in under a second is the guard working, and the pending
query already knows the artifact exists.

Expect some stages to be free. A creation endpoint may already fire the first generator
itself, so the first stage's pending count is zero before you run anything — check
before budgeting an hour for it.

## Leftover locks outlive the run that took them

An execution killed mid-flight can leave an in-progress marker that makes later attempts
return a skip (`reason: in_progress`) forever. That is not a new failure and not a
pipeline defect: it is a stale lock, and the subjects holding one need it cleared before
they will re-run. Name them separately in any count rather than folding them into
failures.
