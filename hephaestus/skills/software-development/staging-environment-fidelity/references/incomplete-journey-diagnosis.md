# Diagnosing a journey that never reaches its last stage

Use when a multi-stage pipeline has output at early stages and little or none at a later
one, when a stage's table is empty or implausibly thin, or when the owner asks why the
artifacts a later stage should produce do not exist.

The instinct is to debug the empty stage. That stage is usually innocent: nothing ever
arrived at it.

## Trace BACKWARD from the empty stage, one gate at a time

Start at the first stage with no output and walk upstream, asking at each hop "what
promotes a row into here, and has any row ever satisfied it?" The chain terminates at the
first gate no row has ever passed, and that gate is the finding.

The decisive query is a census of the promotion predicate over ALL stored rows, not over
the cohort you just created:

```sql
select <promotion_label>, count(*), min(<score>), max(<score>)
from <stage_output> group by 1 order by 2 desc;
```

A promotion label with **count zero across the entire history** means the next stage has
never been reachable, and every hour spent on that stage is wasted. Measured on one
pipeline: the terminal label had 0 rows of 21 ever, and the stage behind it had no
artifacts for the entirely sufficient reason that nothing had ever been promoted into it.

## A correct guard is often the proximate cause

Read the promotion rule in the code, not from the design doc, and compare it against the
rows that fell short. The common shape is a cap applied for good reasons:

```javascript
if (absent.length > 0 && recommendation === 'Advance') recommendation = 'Hold';
```

That rule is right — a component with no evidence must not be able to push a subject over
a promotion boundary. But combined with an upstream step that never collects evidence for
one component, it caps **every** subject forever. Measured: seven subjects scored above the
promotion threshold, one well above it, and all seven were capped by exactly one missing
component.

So report the guard as the mechanism and the collection gap as the defect. Do not propose
loosening the guard: that converts a stalled pipeline into one that promotes on absent
evidence. The fix belongs upstream, and a per-component null census names which component
to fix.

## Count rows that carry the COMPLETE upstream chain, never rows per stage

A corpus assembled by direct writes has volume without causality, and per-stage counts read
as progress while no row has traversed the pipeline. Join the chain instead of counting its
links:

```sql
select count(*) total,
  count(*) filter (where exists (select 1 from <stage1> s where s.subject_id=c.id)) s1,
  count(*) filter (where exists (select 1 from <stage2> s where s.subject_id=c.id)) s2
from <subjects> c;
```

Measured on a corpus that looked well populated: 89 late-stage transcripts of which **4**
had the preceding stage's score and 4 had its artifact. The other 85 were bulk backfill, so
the transition under test had never executed once. A populated corpus with no causal chain
through it is worse than an empty one, because it reads as coverage and silently licenses a
claim that the journey works. Whoever wrote the backfill owns this one — check it before
citing your own corpus as evidence.

Before trusting any end-to-end claim, assert that at least one subject reached the final
stage **through** the pipeline, and name that subject.

## Audit what CALLERS post to against what the engine has REGISTERED

The fidelity checks that enumerate a definition's own declared entry points cannot see this
class, because the caller is not a definition. A route, button or node that posts to a path
which exists in production and was never created in the test environment fails the only way
it can: the engine returns not-found, the caller wraps it in a generic error, and **zero
executions are recorded**.

Build both sets and diff them:

```sql
-- every path any definition registers
select w.id, w.name, n->'parameters'->>'path' path
  from workflow_entity w, json_array_elements(w.nodes) n
 where n->>'type' like '%webhook%' and (n->'parameters'->>'path') is not null;
```

```bash
# every path anything CALLS -- application routes, node code, client fetches
grep -rhoE "(webhook|hooks)/[A-Za-z0-9_-]+" <app-routes> <exported-definitions>
```

Any called path absent from the registered set is a dead caller. Expect more than one: each
new caller is a separate omission, invisible until a human clicks it. Two instances surfaced
on one environment within a day — a manual-trigger button and an automatic post-write
scoring trigger — neither detectable from the definition side.

## Read the audit table, not the HTTP response, for a trigger that fired and failed

A chained trigger that runs and then fails to reach its target returns success to the
original caller, because the write it was attached to did succeed. The failure is recorded
only where the trigger node logs it:

```sql
select event_type, subject_id, stage, left(payload::text, 200)
from <audit_table> where created_at > now() - interval '15 minutes'
order by created_at desc;
```

A `*_trigger_failed` row carrying the engine's own not-found message is the whole diagnosis.
Without that read the symptom is "the transcript saved but no score appeared", which invites
debugging the scorer.

## Read the caller before concluding it sends the wrong payload

When a chained trigger's guard requires a field, check where that field is supposed to come
from before blaming the caller. A field deliberately taken from the verified session rather
than the request body — so a client cannot spoof the actor — is absent from the body by
design and present by the time the trigger reads it. Grep the route for the field name and
read the comment beside it; a correct caller misdiagnosed as a broken one costs a cycle and
points the fix at the wrong file.

## Repairing a dead caller: clone the production definition rather than authoring one

Once the diff above names a called-but-unregistered path, the missing definition almost
certainly exists in production. Export that one as the reference and rewrite it; writing a
replacement from the caller's expectations reproduces the contract by guesswork and drifts
from the environment it is supposed to mirror.

1. **Export production's definition and read the caller's expectations out of the trigger
   node** — the host, port, path and the exact payload keys it signs. The caller is the
   spec; the production definition is the implementation.
2. **Rewrite only the environment-specific values, and assert each rewrite landed.** Data
   store hostname, engine port, and every forwarded entry-point path to its test prefix.
   Assert positively (the staging forms are present) AND negatively (no production form
   survives) over the serialised JSON before importing — a replace that matched nothing
   is indistinguishable from success.
3. **Transform in a real language, never by piping the export through a shell.** A terminal
   layer that redacts secret-shaped lines will quietly mangle an `Authorization` header in
   the code body; the file on disk is intact, so verify by reading it programmatically
   rather than by eye.
4. **Assign an explicit id, verified free in BOTH databases.** Import rejects a definition
   whose id was stripped (`null value in column "id"`), and instances sharing history hold
   colliding ids, so a borrowed id can collide with an unrelated definition in the other
   environment.
5. **Import, then activate, then RESTART the engine.** Setting the active flag updates the
   row; entry points are registered at boot, so the path keeps returning not-found until
   the process restarts. Confirm which container you are restarting and that production's
   engine is a different one, check for in-flight executions first, and treat the restart
   as a service action needing the owner's approval.
6. **Probe the new path with a DELIBERATELY INVALID signature and require an auth
   rejection.** Not-found means it still is not registered; acceptance means the guard is
   broken and you have published an unauthenticated writer. Only an explicit auth error
   proves registered-and-guarded. Write the probe's output to a fresh file: reusing an
   earlier response path makes a stale body read as a current result.
7. **Control on production throughout.** Definition count and the reference definition's
   node hash before and after, plus a health probe on the production engine after the
   restart. Report the pairs.

Then re-run the write that fires the trigger and assert the downstream row appeared. A
replayed write may be recorded as a replacement rather than a first insert; the trigger's
guard keys on ABSENCE of downstream output rather than on the event type, so a replacement
still fires when nothing has been scored.

## A hop that needs a click is yours to drive, not the owner's

Where the only legitimate signer of a request is the application itself, a worker with
shell and SQL cannot complete the hop and will correctly halt. That hold is addressed to
whoever has a browser — check your own capabilities before forwarding it to the owner.
Calling an application route that signs server-side is using the app as designed; the key
never leaves the server, so this is a click, not a forged credential. Read the route to
confirm before concluding a no-forging rule blocks you.

Three mechanics make a browser-driven batch survive:

- **Authenticate against the SAME ORIGIN the session is bound to.** A session issued for
  the public hostname does not apply to a loopback or port-local URL for the same service,
  and the symptom is a silent bounce to the login page.
- **Fire and forget, then verify in the store.** An evaluation helper with a short response
  timeout aborts while the request is still in flight, and the abort looks like a failure
  although the call completed. Start the request without awaiting it, poll the database for
  the row, and never conclude from a harness timeout that the write did not happen.
- **Re-authenticate between batches.** Long UI runs outlive the session; a mid-batch
  expiry presents as an element that cannot be found.

## Prove the end-to-end chain on ONE subject before authorising a batch

Where the batch costs real money, a single subject driven through every hop is the cheapest
available gate and routinely finds a break the per-stage checks missed. Create the subject,
let the automatic steps run, supply the input the next stage needs, and assert each hop's row
appeared. Report which hop stopped it.

Two rules make that single run worth trusting:

- **Existing stage inputs answer the OLD version of an upstream artifact.** A stored
  transcript or payload was produced against the previous question set, so scoring it
  measures the old coverage and proves nothing about the fix. Build the input against the
  NEW artifact — read the regenerated artifact's items and answer those — or state plainly
  that the stored input predates the change.
- **Keep one untouched control through the whole run.** A subject whose artifact hash is
  byte-identical afterwards is what makes the run a measurement rather than a
  demonstration, and it must be chosen and hashed before the first trigger.
