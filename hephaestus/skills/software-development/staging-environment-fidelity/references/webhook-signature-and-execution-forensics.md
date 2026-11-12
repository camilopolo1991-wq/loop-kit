# Webhook signature matching and execution forensics

Mechanical detail for driving and debugging signature-gated pipeline endpoints.
Everything here was isolated by a 401/200 or empty/non-empty pair against a live
endpoint, not read off a doc.

## Matching the signed body BYTES

The common verifier shape computes `HMAC-SHA256(secret, rawBody)` where the
caller supplies `rawBody` as a re-serialisation of the **already-parsed** body:

```
={{ JSON.stringify($('Webhook').first().json.body) }}
```

So your signature must reproduce JS `JSON.stringify` byte for byte, not the bytes
you happened to send. Two language defaults break this, each proven by a 401/200
pair:

| Property | Python default | JS emits | Wrong result |
|---|---|---|---|
| Separators | `', '` / `': '` | `','` / `':'` | 401 signature failed |
| Non-ASCII | escaped `\u2014` | literal character | 401 signature failed |

```python
body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
sig  = hmac.new(secret.encode(), body.encode('utf-8'), hashlib.sha256).hexdigest()
# send the SAME string you signed, not a re-dump
```

A single em-dash anywhere in a free-text field (a transcript, a note) is enough
to trigger the second row, which makes it look intermittent across fixtures.

Field ORDER does not matter — the verifier re-serialises in the order keys
arrived in your JSON — so do not go hunting key order on a 401. Check separators,
then escaping, then the field SET against the body the legitimate client builds.

## Prefer the application's own route over signing anything yourself

Where the application exposes a route that signs server-side, calling that route is using
the app as designed and needs no secret in your hands. Read the route first: a payload of
plain JSON with the signature added inside the handler means the whole signing problem above
does not apply to you, and reaching for the secret instead is both unnecessary and a worse
proof of the production path. Reserve hand-signing for endpoints with no application caller.

## Prove the endpoint verifies at all before trusting it as a control

Some endpoints that look gated have **no verify node**, so they accept any
signature. "Endpoint X accepted my request, therefore my signing is correct" is
then false, and the conclusion sends you to debug the signer that was already
right — or worse, to trust a forged-looking call as validated. Confirm the
specific target path has a verify node before using its acceptance as evidence,
and expect an unauthenticated scorer or writer endpoint to be a finding in its own
right.

The probe that settles it is a **deliberately invalid signature**, and its three outcomes
are a decision table:

- **404** — not registered. Nothing about the guard has been tested.
- **401 / explicit auth error** — registered AND guarded. This is the only pass.
- **200** — registered and unguarded. Worse than the original defect, and if you just
  published this endpoint, it is a regression you introduced.

Write the probe's response body to a FRESH file each time. Reusing a temp path from an
earlier probe prints the previous body beside the current status code, and the mismatched
pair reads as a bizarre result rather than as stale output.

The secret is chosen **per endpoint**, carried as a field naming the env var
(`secretKeyName`), not fixed per environment. One stack measured 15 of 20 gated
paths on one secret and 3 on another. A client with a single shared signing
helper therefore signs every endpoint with one secret and silently fails on the
majority — read the verify node for the exact path rather than copying a
neighbour's. Fixing this belongs in the client (add a second signing helper and
repoint only the affected routes), leaving the existing helper intact for the
routes that legitimately use it.

## Reading the real error out of an execution record

`execution_data.data` is a **pointer table**: a JSON array in which many string
values are decimal indices into that same array. Grepping it yields
`{"message": "17"}`. Dereference recursively:

```python
arr = json.loads(blob)
def dr(v, d=0):
    if d > 8: return v
    if isinstance(v, str) and v.isdigit():
        i = int(v)
        if 0 <= i < len(arr): return dr(arr[i], d + 1)
    return v
for it in arr:
    if isinstance(it, dict) and 'message' in it:
        print(dr(it['message'])[:300])
```

**Start from `lastNodeExecuted`, not from the message.** The top-level object carries
`{'error': <idx>, 'runData': <idx>, 'lastNodeExecuted': <idx>}`; dereferencing the last of
those yields the node name that threw and orients the whole investigation in one step.
Dereferencing `error` gives a dict whose `message`, `description` and `stack` are themselves
indices.

```python
top = next(v for v in arr[:60] if isinstance(v, dict) and 'error' in v)
print(arr[int(top['lastNodeExecuted'])])     # the node that threw
```

**A sub-workflow node hides the cause; the real error is in the sub-workflow's own
execution row.** A node of type `executeWorkflow` reports only a generic wrapper message
(`Error executing workflow with item at index 0`), and `description` is frequently a
TRUNCATED fragment of the underlying API error with a source line appended — enough to
mislead, not enough to diagnose. Find the child row by workflow id and time window, and
read the latest of them:

```sql
select id, "workflowId", status, "startedAt" from execution_entity
where "startedAt" > now() - interval '25 minutes' and "workflowId"='<SUB_ID>'
order by id desc limit 6;
```

The child's ids sit a few numbers AFTER the parent's, because the parent started first.
In the child record a regex sweep for provider vocabulary — `invalid_request`, `overloaded`,
`rate_limit`, `authentication`, `credit`, `HTTP \d\d\d` — reaches the verbatim message
without any dereferencing.

**A retry/backoff wrapper converts an upstream refusal into a thrown error after N
attempts, so the stack points at the wrapper's own throw line.** Read that line in the
wrapper's source before diagnosing: `throw new Error('... failed after 3 attempts for
<skill>: ' + lastError)` means the cause is whatever `lastError` holds, and the
wrapper is innocent. The same wrapper usually posts to a human alert channel on final
failure, so mention that the owner's team may already have been paged.

Two correlation traps:

- A signed call commonly produces a **successful** verify sub-execution and a
  **failed** parent in the same second. Read the error execution, not the success
  beside it.
- Engines prune payloads on a retention policy, so a uniformly small `data` size
  across executions is NOT evidence that nothing ran. Corroborate with a side
  effect — a written row, a version column on the result — never with payload size.

## Distinguish a provider-account failure from a pipeline defect, and stop

A model or payment provider refusing on account state (`credit balance is too low`,
subscription lapsed, key revoked) arrives as an ordinary 4xx deep inside a code node and
looks exactly like a malformed-request bug. Three things make the call:

1. The verbatim provider message, pulled from the sub-workflow row as above.
2. The last success and first failure timestamps, which bound when the account state
   changed: `select max("startedAt") ... where status='success'` against `min("startedAt")
   ... where status='error' and "startedAt" > now() - interval '2 hours'`.
3. **Whether the credential is shared with production.** Hash the key from each
   environment's own config and compare the fingerprints — never print the value. Matching
   fingerprints mean production is failing the same way, which raises the report from a
   staging blocker to a live incident even if no production row has hit it yet.

This is not a defect you can fix, and continuing to probe burns time. Report the message,
the window, the production blast radius, and what was proven before the wall.
