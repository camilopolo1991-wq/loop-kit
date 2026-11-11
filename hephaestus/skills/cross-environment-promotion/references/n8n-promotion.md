# n8n promotion mechanics

Concrete details for applying the general procedure to n8n, where two Postgres
databases (`n8n`, `n8n_staging`) hold independently editable workflow copies.

## The entity / history split

`workflow_entity.nodes` is the STORED definition. n8n EXECUTES the
`workflow_history` row whose `versionId` equals `workflow_entity.activeVersionId`.

Consequences:

- Updating `workflow_entity` alone changes nothing at runtime. This is useful: it
  is a staging area inside production.
- Verifying a fix by reading `workflow_entity` proves storage, not behaviour.
  Always read through the join to `workflow_history` when the claim is "live".
- Recreating the container can leave `0 published workflows`. Re-publish and
  re-confirm each `activeVersionId` afterwards.

```sql
-- what is actually executing
select coalesce(h.nodes::text,'EMPTY')
from public.workflow_entity w
left join public.workflow_history h on h."versionId" = w."activeVersionId"
where w.id = '<workflow id>';
```

**A workflow with `activeVersionId` NULL makes that join drop every row**, so an
empty result reads as "clean" when it means "unknown". Query the entity directly
as the control.

## Writing a payload

Avoid embedding large JSON in SQL. Copy the file into the container and let
Postgres read it:

```python
subprocess.run(["sudo","-n","docker","cp",path,"<postgres-container>:/tmp/apply.json"],check=True)
psql("""update public.workflow_entity
        set nodes = pg_read_file('/tmp/apply.json')::json, "updatedAt" = now()
        where id='%s';""" % wid)
```

Touch `nodes` only when no promoted fix changes the graph; leaving `connections`
alone bounds the blast radius to node bodies.

## Disabled nodes

`"disabled": true` on a node makes it pass its input through and report success in
0 ms. Any audit or alarm implemented INSIDE that node can therefore never fire,
and its silence reads as health.

- Treat a never-fired alarm as unproven, not as a clean record.
- Compare the `disabled` flag across environments explicitly; a node quarantined
  for a real reason outlives its cause once the cause is fixed elsewhere.
- Check EVERY workflow that calls the same subworkflow. A quarantine applied to
  one caller is usually present on its siblings too.

## Fan-out and item counts

A node that computes a median or quorum over N samples depends on an upstream
builder emitting N items (`return [0,1,2].map(...)` versus `return [{json:{...}}]`).
That contract lives in a DIFFERENT node from the one being promoted, so compare
the builder on both sides before promoting any aggregator.

## Webhook response semantics

`responseMode: responseNode` means an error partway through the chain never
reaches the responder: the caller gets HTTP 200 with an empty body. Branch on the
response BODY, never on the status, and when adding a refusal path add its
responder in the same change.

## HMAC signing from Python

n8n re-serialises the parsed body before hashing, so the signature must be
computed over `JSON.stringify(parsedBody)` equivalence:

```python
body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
```

Both arguments are required. `separators` removes the spaces Python adds;
`ensure_ascii=False` stops Python escaping non-ASCII to `\uXXXX` where
`JSON.stringify` would not, which otherwise makes any accented or dashed text
sign differently and return a confusing `401`.

**Each webhook family verifies with its OWN secret.** Signing with the wrong one
produces a 401 that is correct behaviour, not a bug; parameterise the secret by
webhook family rather than assuming one global key.
