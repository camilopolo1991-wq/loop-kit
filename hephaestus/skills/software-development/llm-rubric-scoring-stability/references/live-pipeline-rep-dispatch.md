# Dispatching stability reps against a live pipeline

Depth for `llm-rubric-scoring-stability`. Use this when the reps cannot be replayed
from stored artifacts and you must actually drive the production scoring path N times.
Measured on a node-based (n8n) pipeline behind HMAC-gated webhooks; the failure shapes
generalise to any orchestrator that wraps the scorer in a workflow engine.

Prefer replay (`references/stored-run-replay.md`) whenever the stored payloads exist.
Everything below costs real model calls and real writes.

## HTTP 200 does not mean the run succeeded

Workflow engines commonly return the HTTP response from a dedicated terminal node. A run
that throws anywhere before reaching it returns **200 with an empty body**. A harness
that keys on the status code records those as successes and then averages over whichever
reps happened to survive.

Rules:

- Parse the body. Treat empty as FAILED and count it, never skip it silently.
- A `{"skipped": true, "reason": ...}` body is also a 200. Count skips as a third
  category: dispatched, scored, skipped, failed. A harness reporting "5 reps" having
  actually scored 2 is the defect this prevents.
- Read the result back out of the RESULT TABLE, not out of the response body. What was
  stored is what the pipeline will serve; the body can be a summary that omits the
  per-component breakdown entirely.
- Capture each response to a UNIQUE path you own (`tempfile.mkstemp` in your own scratch
  dir), never a fixed name under the system temp dir. Shared boxes run concurrent jobs
  that reuse the obvious names, so a fixed path means you eventually parse another
  process's output as your webhook's reply — which presents as a wildly off-topic body
  and sends you diagnosing a signature or a prompt that was never involved. If a response
  ever reads as unrelated prose, suspect the path collision before the endpoint.

## A retry wrapper that does not retry a malformed body

Shared backoff sub-workflows retry **transport** failures and frequently nothing else.
The measured shape: the loop `continue`s on HTTP 429/5xx, but a 200 whose body fails
`JSON.parse` is caught and wrapped as a raw-text fallback that is **returned with
`success: true` on attempt 1** — so the three allotted attempts are reachable only by the
transport path and a prose response gets none of them. Downstream schema validation then
refuses the record and the subject silently fails to score: 3 of 32 executions, ~9%.

This is plumbing, not scoring. The tells that separate it from an unstable rubric:

- the schema error names the fallback field itself (`unexpected additional property
  "raw_text"`, alongside the real fields missing), so the model returned prose once;
- it reproduces at a flat background rate across subjects rather than clustering on one
  input or one component;
- the surviving reps agree exactly, because the runs that parse are not the problem.

Fix inside the existing loop rather than adding attempts: on parse failure record the
error and `continue`, and emit the raw-text fallback only after the final attempt, so
today's behaviour becomes the last resort instead of the first response. Max attempts and
delays unchanged means worst case equals today. Assert before writing that the loop bound,
the transport-retry branch, the single fallback and the single return path all survive —
duplicating either the fallback or the return is the easy way to break this edit. At a ~9%
per-call parse rate, two extra re-asks put residual failure under 0.1%.

Report the malformed-body count as its own category beside dispatched / scored / skipped /
failed, because fixing the rubric cannot move it and leaving it in the failed bucket
invites exactly that mistake.

## Signing the request from Python when the engine signs in JS

The verifier almost always HMACs `JSON.stringify()` of the **parsed** body, so your bytes
must match JS's serialisation exactly. Two defaults in `json.dumps` each produce a silent
401, and each was isolated by a 401/200 pair on otherwise identical requests:

```python
body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
sig  = hmac.new(secret.encode(), body.encode('utf-8'), hashlib.sha256).hexdigest()
```

- Python's default separators emit `', '` / `': '`; JS emits `','` / `':'`.
- Python's default `ensure_ascii=True` escapes non-ASCII (an em-dash becomes `\u2014`);
  JS emits it literally. Any payload containing one fails, which makes this look
  content-dependent and therefore mysterious.

Test those two before theorising about field order or payload shape: field ORDER does not
matter provided the body round-trips identically, and permuting it to chase a 401 wastes
a cycle.

Each endpoint names its own secret. Where a shared verify sub-workflow resolves
`$env[secretKeyName]`, that name varies per workflow — read the caller's declared name
rather than assuming one project-wide secret. A UI route sharing one signing helper across
endpoints that verify different secrets fails on the majority while looking correct in
review.

**An endpoint with no verify node accepts anything.** Do not cite a 200 from such an
endpoint as proof your signature is correct; confirm the verify node exists first.

## The orchestrator may execute a different copy than the one you edited

Where the engine versions workflows, the running code is the PUBLISHED copy, which is
usually a separate row from the one a direct SQL edit touches. A prompt or node change
that reads back correctly and still has no effect is this, not a caching mystery.

The diagnostic is a contradiction between two reads of the same instant: your own SELECT
shows the new value while the engine's own export shows the old one. Trust the export —
it reflects what executes. Fix by updating both rows in one change, assert the node count
is unchanged in each, then restart the process so triggers re-register.

The same shape applies to mid-run edits: a config or prompt row changed between reps
means rep0 ran against a different specification than rep1..n. Record the live version
identifier IN each rep's result record so the split is visible in the data rather than
reconstructed from timestamps afterwards.

## Concurrency locks that release only on failure

Scoring paths commonly claim a lock row in an audit table and write the matching release
row **only on the failure branch**. A successful run therefore leaves its lock held until
a TTL (measured: 10 minutes) expires, and the next legitimate rep is skipped with an
`in_progress` reason — which, being a 200, reads as a success.

Check before building the loop:

- Find the release write and read which branch it sits on. A `payload.reason` that always
  names a failure is the tell.
- Compare lock and release counts over recent history. More locks than releases, with the
  newest release carrying a failure reason, confirms it.

The guard typically compares lock and release by TIMESTAMP and its own comments document
a compensating release row, so writing one between reps is the supported mechanism rather
than a workaround. Prefer that to deleting the lock, and never to shortening the TTL.

Separately: a rescore flag whose documented purpose is to bypass the already-scored skip
means that skip is not protecting your stored rows on this route. See the main skill's
re-score write-path rules before dispatching.

## Clearing prior rows: verify by row count, never by exit status

A harness that deletes stored scores between reps (because the scorer would otherwise
answer `already_scored`) must confirm the delete LANDED. Database CLI wrappers commonly
accept a multi-statement string, apply nothing, and still return **exit 0 with empty
stderr** — after which every rep skips as already-scored and the run reports successes
that never re-scored anything. The silent-success shape is the same class as the
dollar-quoting trap in the main skill: the check cannot fail.

- Issue one statement per invocation rather than a semicolon-joined block.
- Re-SELECT the count afterwards and assert it is zero. Exit status is not evidence.
- When the subsequent reps all answer `already_scored`, suspect the delete before
  suspecting the scorer.

## Reading the failure reason out of the execution record

The response body rarely carries it. In n8n, `execution_data.data` is a **pointer table**:
a JSON array in which fields hold string INDICES into that same array, so values must be
dereferenced rather than read in place.

```python
arr = json.loads(row)
def deref(v, d=0):
    if d > 8: return v
    if isinstance(v, str) and v.isdigit() and 0 <= int(v) < len(arr):
        return deref(arr[int(v)], d+1)
    return v
```

Extraction trap, severe enough to invert a verdict: **do not regex the whole blob for the
result object.** Prompts embed a worked EXAMPLE of their own output schema, so the match
is a structurally valid fake result with plausible values that passes field-presence
checks and returns the same static text once per rep — reading as perfect stability.
Locate the response positively (require its wrapper key), reject any element containing a
prompt marker (an unfilled `{{slot}}`, a known instruction heading), assert the field set
is complete, then cross-check one value against the stored row. The same record holds
both the stored template and the filled prompt, so when verifying that an input reached
the model, confirm the FILLED copy is present rather than inferring it from the score.

## Writing fixtures through the product's own path

Where the owner requires changes to go through the UI rather than the database, the UI
route is usually a thin wrapper over the same webhook. Drive the UI once to prove the
path works end to end, then dispatch the remaining fixtures to that endpoint with the
same payload shape and signing — it is the same write, and a six-fixture corpus does not
need six browser round-trips.

Two UI-specific notes when you do drive the browser:

- A coordinate click can land before the framework has enabled the button. Dispatch the
  full synthetic sequence (`pointerdown, mousedown, pointerup, mouseup, click`) on the
  element and confirm the network call fired rather than re-clicking.
- A native `confirm()` dialog blocks every subsequent automation call, and the symptom is
  an unrelated IPC timeout. If automation goes unresponsive right after a destructive
  action, check for an open dialog before debugging the harness.

## Fixture formats the pipeline will reject

Scoring pipelines that cite evidence commonly parse the source document for attributable
speaker turns and refuse to score what they cannot cite. Two refusals cost a cycle each:

- A `Q:`/`A:` transcript yields no speaker labels (`NO_SPEAKER_ATTRIBUTION`). The accepted
  shape is `[HH:MM:SS] Speaker: text` on every line — assert every line matches the
  parser's regex before writing the fixture.
- The speaker label must MATCH the subject's stored name, not an invented one
  (`CANDIDATE_NOT_IN_TRANSCRIPT`), or the parser accepts no quotes at all.

Both are refusals to fabricate, not bugs. Fix the fixture.

## A status column is a claim about a process, not the fact itself

Pipelines record generation/scoring progress in a status table beside the artifact
table. Those rows are frequently written by only ONE code path — the trigger — so an
artifact produced by invoking the generator directly (which is exactly what a harness
does) leaves the stale `failed` row untouched. The product then renders a permanent
failure banner beside a working result, and no database check of the artifact table
ever shows it.

This class of defect is invisible to SQL verification and obvious in one screenshot,
which is the argument for rendering the end state at least once per journey rather
than trusting row counts.

- Before trusting a status column, find every workflow that writes it
  (`where nodes::text like '%<table>%'`) and compare against the artifact table:
  rows marked failed that HAVE an artifact are false negatives.
- Reconcile from the artifact, never from a guess — copy the real artifact id onto
  the status row. Compare both environments first: a status table that is healthy in
  production and broken in the test environment is harness drift, not a product bug,
  and that distinction decides whether anything needs fixing upstream.
- Report the counts per environment, because a zero can mean "no failures" or "no
  rows": prod holding 73 ready / 2 failed and staging holding 93 failed / 1 ready is
  the shape that identifies which side drifted.

## Editing a prompt-builder node: what a syntax check cannot catch

Wiring a new input into a builder means editing executable node code, and two failure
shapes present IDENTICALLY as the empty-body 200 above — returned far too fast for a model
call, which is the tell that it never reached the model. Only one is reachable by a parse
check:

- **Declarations inserted at the start of the line holding the first `.replace()` split
  the statement.** That line CONTINUES the assignment above it (`const prompt = tpl` /
  newline / `  .replace(...)`), so consts spliced there leave the chain dangling after a
  semicolon. This is a syntax error and a parse check finds it. Insert before the
  statement that STARTS the chain, located by searching for the assignment rather than by
  assuming a line number.
- **Referencing a name the node never destructured is VALID syntax** and fails only when
  that line executes. No parse check can find it. These nodes read every input through one
  destructuring statement at the top; any new name must be added there AND actually
  returned by the upstream node. Assert both before writing.

So run a parse check on every edited body — wrap it as `(async () => { ... })();` since
these bodies use top-level `await` — and then still verify by executing the real path and
reading the BODY. A green parse proves the file loads, never that it runs; a JS error
stores cleanly in SQL and surfaces only at runtime.

When an edit turns out to be both broken and unnecessary, restore the pre-edit body from
the backup and re-apply only the genuine gap, rather than repairing in place. Repairing
leaves the duplicate mechanism behind, which is the condition that makes the next reader
unable to tell which code is load-bearing.

## Promoting node changes between environments

- **Workflow IDs COLLIDE across environments.** Several ids exist in both databases with
  entirely different content, so "same id" never means "same workflow". Resolve the target
  by querying the id in the database you intend to write, and assert the returned name
  carries the expected environment prefix before any write. Sibling workflows often have
  genuinely different ids per environment, which is what makes the colliding ones easy to
  miss.
- **Never import a lower environment's workflow export into production.** Those exports
  carry that environment's hostnames, ports and webhook paths — importing one points
  production at the test database — and they carry `active: true`, so the import can arm
  itself with no human in the loop. Port the node logic instead, rewrite hosts to the
  target's own, and assert the payload is free of every foreign-environment token before
  the write. That assert earns its place: it has caught a live host reference that a
  reading of the diff missed.
- **Separate YOUR changes from pre-existing drift before promoting.** Generate a
  node-level diff between environments and expect most differing nodes to be drift that
  predates you; promoting the whole diff is a far larger change than the one that was
  approved. Put a unique marker comment in every edit you make so your own nodes can be
  identified mechanically rather than by memory.

## A status write with no precondition rewinds real state

A node that PATCHes a stage or status column to a hardcoded value with no precondition
moves a record BACKWARD whenever its step is re-run. Regenerating an artifact to clear a
cosmetic banner has been measured to reset three records that had already completed a
later round, the overwrite landing milliseconds after the legitimate write with no error
anywhere — the scores survived, the stage field did not.

Put the precondition in the REQUEST, not in a JS branch:
`&current_stage=in.(applied,screened,r1_guide_ready)`. A filter evaluated server-side is
atomic, so there is no read-then-write window for a concurrent writer, and a record
further along simply matches zero rows and the PATCH becomes a no-op. Derive the legal
value set from the live databases and from the mapping in the node that owns the forward
transition; never guess the vocabulary. Restore a rewound record by recomputing from that
same mapping applied to its stored result, not by assigning a value that looks right.

## Minimum report for a dispatched run

- input integrity: a hash of each stored input, asserted per rep
- dispatched / scored / skipped / failed counts
- per-component values per rep, and the count of reps returning a NUMBER versus a null
- per-component range, never pooled across subjects
- the positive control's result, named
