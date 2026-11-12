# Firing a stage through its real endpoint

The harness that drives a pipeline by hand has to speak exactly what the UI speaks.
Every rule here cost a batch of wasted calls or a wrong diagnosis.

## Sign the body the receiver RE-SERIALISES, not the bytes you sent

HMAC verification commonly digests `JSON.stringify(parsedBody)`: the receiver parses
the request, then re-serialises it. It does not hash the wire bytes. Python's
`json.dumps` inserts a space after `:` and `,`, so a default-encoded body fails every
signature check with 401 while the secret is perfectly correct.

```python
body = json.dumps(payload, separators=(",", ":"))   # mandatory, not cosmetic
sig  = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
```

**A whole batch returning 401 is a canonicalisation bug, not a credential problem.**
Before suspecting the secret, confirm the env file's value and the running
container's value agree by FINGERPRINT (never by printing them). Once they match,
stop looking at the secret.

## Read each handler's input source; siblings disagree

Stages written at different times take the same artifact from different places. One
fetches it from the database by subject id; the next reads it from the request body
with `body.field || ''` and silently proceeds on an empty string.

Posting only the id then runs the model against nothing, and the resulting schema
failure looks exactly like a defect in that stage. Grep the handler for the field name
and read its fallback before writing a stage up as broken — and pair a "zero lifetime
successes" count with a sibling as the control, because a stage may simply never have
been driven correctly.

## Time the successful calls; a stage near the per-task ceiling fails at random

Orchestrators impose a per-task wall clock (commonly 300s). A stage whose normal path
sits above roughly half that ceiling has no margin and will fail intermittently on
input-size or latency variation, with identical inputs succeeding and failing in the
same batch.

The tell is a failure that always lands at ~ceiling+0.x seconds while siblings finish
in a fraction of it. Record the successful durations in the harness output so the
pattern is visible. A warm retry failing identically kills any "cold start"
explanation — test that theory rather than asserting it, because an internal retry
loop inside ONE task spends the whole budget without the parent seeing attempts.

**A failure at the ceiling is a CLUE, not a diagnosis.** The ceiling is what stopped
the run; it need not be what broke it. Raising it is legitimate and the next run is a
NEW measurement that must be re-read from its own execution record. Expect the fault to
relocate: two stages failing at ceiling+0.4s, given room, ran 417s and died at a
different node entirely — the model reply was truncated mid-array because the output
token ceiling sat BELOW the size of the artifact the stage had to produce. Both limits
were real and each fixture needed a different one.

**Size any output ceiling from the artifacts that exist, never from a guess.** Query
`min / median / p90 / max` length over every stored instance of that artifact and set
the ceiling above the observed maximum. A ceiling under p90 truncates only the largest
cases, which presents as flakiness between identical replicas and is exactly how such a
limit survives for months. Divide characters by ~4 for a token estimate.

**When two subjects fail identically and one fix repairs only one of them, there are
two defects.** Do not let the first green close the investigation.

## Batch only after one subject proves the call shape

Fire a single subject, read the row it wrote, THEN loop. Append each result to a file
as the loop runs so a timeout keeps the completed work. A nine-subject batch that
fails on call shape costs nine times the latency to learn one thing.

## Reconcile calls against rows, every stage

Count the rows that landed and compare to the calls made. Report the gap explicitly,
and for each missing row name the reason from the orchestrator's own execution record
rather than inferring it. "Nine calls, four rows" is the finding; "nine successes" is
the lie the status codes tell.
