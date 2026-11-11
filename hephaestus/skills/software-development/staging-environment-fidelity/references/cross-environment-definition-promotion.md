# Promoting a pipeline definition between environments

Use when the diff of called-versus-registered paths names a definition that exists in one
environment and not another, or when a cloned pipeline needs a component the target
instance is missing. The source environment's definition is the reference implementation;
copy it and rewrite, never author a replacement from the caller's expectations.

## Export, then transform in a real language

```bash
docker exec <SOURCE_CONTAINER> n8n export:workflow --id=<ID> --output=/tmp/wf.json
docker cp <SOURCE_CONTAINER>:/tmp/wf.json /tmp/wf.json
```

**A secret-scanner in the reading path can redact what it prints while leaving the file
intact.** An exported code node assembling an `Authorization` header from an env var comes
back through a terminal as `'Authorization': '***'+__jwt`. Do not conclude the export is
corrupted and do not retype the node from what was printed. Load the JSON in a runtime,
assert the sensitive line is whole (`'***' not in code`), and edit programmatically.

## Enumerate the per-environment values against the file, then assert both directions

Typical set, but derive it by reading rather than assuming:

| kind | source | target |
|---|---|---|
| internal service host | `http://store:3000` | `http://store-staging:3000` |
| engine port for peer calls | `port: 5678` | `port: 5679` |
| forwarded entry-point paths | `r1-score` | `stg-r1-score` |
| definition name | `PROD · ...` | `STG · ...` |
| `active` | `true` | false; activate explicitly after import |

Sub-workflow references by id often stay as-is — check the id resolves in the target
database before rewriting, since some are deliberately identical across environments.

```python
blob = json.dumps(w)
checks = {
  "target host present":  "store-staging:3000" in blob,
  "source host GONE":     "store:3000" not in blob.replace("store-staging:3000", ""),
  "target port present":  "port: 5679" in blob,
  "source port GONE":     "port: 5678" not in blob,
  "prefixed path present":"stg-r1-score" in blob,
  "bare path GONE":       "/webhook/r1-score" not in blob,
  "promoted path kept":   "<path being promoted>" in blob,
}
assert all(checks.values()), [k for k, v in checks.items() if not v]
```

The `.replace()` in the source-host check is load-bearing: a substring test for the source
host matches the target host too, so without masking the target first the assert passes
while a production host is still embedded.

## Import needs an explicit id, verified free in EVERY instance

Stripping `id` fails with `null value in column "id" of relation "workflow_entity"`.
Stripping `versionId` is correct and necessary.

Generate a 16-character alphanumeric id and check it against every n8n database on the
host, not just the target — ids collide across environments on shared-Postgres setups, and
a collision makes later `--id=` commands ambiguous about which environment they hit.

```bash
docker cp /tmp/wf.json <TARGET_CONTAINER>:/tmp/wf.json
docker exec <TARGET_CONTAINER> n8n import:workflow --input=/tmp/wf.json
docker exec <TARGET_CONTAINER> n8n update:workflow --id=<ID> --active=true
```

## Activation sets a flag; registration happens at boot

After `--active=true` the row reads active and the endpoint still returns 404, because
entry points are registered at process start. **Probe for the 404 before asking to
restart** — it is the evidence the restart is needed, and on a host where restarts require
authorisation it is what you show to get it.

Before restarting: confirm the target container is distinct from production's
(`docker ps --format '{{.Names}} | {{.Ports}}'`) and check `select count(*) from
execution_entity where status='running'` so the restart is not killing live work.

Then prove registration with a **deliberately invalid signature** — 404 means not
registered, an auth error means registered and guarded, 200 means you just published an
unauthenticated writer. See `webhook-signature-and-execution-forensics.md`.

## Porting a FIX back from the repaired environment: take the whole hunk set

When one environment already carries the fix and the other does not, the unit of promotion
is not "the block that implements the fix" — it is every hunk the block DEPENDS ON.
A block that assigns to a variable depends on how that variable is declared, and the two
environments routinely declare it differently because the repair changed the declaration
too.

The measured shape: the fixed environment declared
`let x = (typeof src.x === 'string') ? src.x : ''` while the unrepaired one still had
`const x = src.x || ''`. The fallback block, which assigns to `x`, was correct in
isolation and byte-identical to the working version. Ported alone it throws
`TypeError: Assignment to constant variable` on the FIRST execution of the live path —
trading a silent wrong-output defect for a hard failure on every run, which is strictly
worse than the bug being fixed.

So: diff the whole function, not the region you identified as the fix. Enumerate every
line the ported code reads or writes, and check each one's declaration on both sides.

**Treat a guard clause in the source as load-bearing until proven cosmetic.** The
`typeof` test above looks like defensive noise next to `|| ''`; it is what keeps a
non-string value from reaching `.trim()` on the next line. Prove each clause's necessity
by removing it in the stub below and requiring the removal to throw.

## Splice into the target's body; never carry the source's body across

The section above says take every hunk the fix DEPENDS ON. Its complement is equally
binding and pulls the other way: take nothing the fix does not depend on. Both are
satisfied by one rule — the unit of promotion is a set of anchored blocks spliced into
the TARGET's existing code, never the source node's body.

The reason is that a long-lived source node accumulates features the target's surrounding
pipeline does not support, and the resulting failure is total rather than degraded. The
measured shape: the source node had separately grown median-of-N sampling opening with

```javascript
const __samples = $input.all();
if (__samples.length !== 3) throw new Error(`SHORT_SAMPLE count=${__samples.length}`);
```

while the target's prompt builder returned a single item (`return [{ json: {...} }]`
against the source's `return [0,1,2].map(...)`). Copied wholesale, every run in the target
throws on line one and writes nothing. Nothing in a node-level comparison objects: the
node name matches, the fix marker is present, the body parses.

Two further classes ride along the same way and are worth asserting against by name:

- **per-environment hostnames inside the body.** A body correct for the source names the
  source's store; copied unchanged it points the TARGET's pipeline at the source's
  database. Scan the assembled payload for every environment-scoped host, database and
  queue name and refuse on any hit — see the both-directions assert above.
- **the target's own markers disappearing.** Assert a string only the target's body
  contains is still present after the splice. Its absence means a body swap happened
  somewhere despite the intent to splice.

### Derive the expected diff size from the blocks, and never positionally

Two metric bugs make a correct splice look alarming and an incorrect one look fine:

- **Comparing lines by position after an insertion reports every following line as
  changed** — a three-line insert into a four-hundred-line body shows dozens of
  differences, which trains you to ignore the number. Count with a real unified diff at
  zero context, not by zipping the two line lists.
- **Hardcoding the expected hunk size is off by one whenever the old and new blocks share
  a leading or trailing line** (commonly the closing brace). Compute it from the blocks
  themselves: strip common leading lines, strip common trailing lines, and require the
  diff's removed/added counts to equal what remains. Then the gate stays correct when a
  block is later edited.

```python
_o, _n = old.split("\n"), new.split("\n")
while _o and _n and _o[0] == _n[0]:   _o, _n = _o[1:],  _n[1:]
while _o and _n and _o[-1] == _n[-1]: _o, _n = _o[:-1], _n[:-1]
assert (len(removed), len(added)) == (len(_o), len(_n))
```

### Hold a multi-node fix together when splitting it restores the defect

Where one part of a fix makes a decision and another part REPORTS that decision, splicing
only the first leaves the target answering success with an empty body — the silent-success
shape the fix existed to remove. Classify each fix as single-node-splicable or
multi-node-with-graph-change at planning time, promote the second kind as one reviewed
unit, and state in the report which fixes were deliberately NOT spliced and why. A
partially promoted fix is worse than an unpromoted one, because the report reads done.

## Prove a port by EXECUTING the declaration plus the mutation, never by asserting strings

A parse check cannot see this class. `node --check` passes on `const` reassignment
because it is a runtime `TypeError`, not a syntax error — so a patch that is certain to
throw on its first execution clears every static gate: the hash matches, the diff shows
one node, the parser is happy.

Run the shapes instead. A dozen lines with no network, no engine and no credential:

```javascript
function runShape(decl, assign) {
  try {
    eval(`const src = {};\n${decl}\n${assign}\nglobalThis.__out = x;`);
    return 'OK: ' + JSON.stringify(globalThis.__out);
  } catch (e) { return 'THREW: ' + e.constructor.name + ': ' + e.message; }
}
```

Require all four outcomes in one run, and read them rather than counting them:

| case | required |
|---|---|
| old declaration + ported block | THREW — proves the naive port was broken |
| new declaration + ported block | OK with the fallback value |
| guard present, hostile input | OK — the guard absorbs it |
| guard removed, hostile input | THREW — proves the guard is load-bearing |

The first row is the one that justifies the extra hunk to a reviewer; without it the
wider patch looks like unnecessary scope. The last row is the negative control: a stub
where every case passes is testing nothing.

## Assert the mutation applied before writing the artifact

A string replacement that matches nothing returns its input unchanged, so a patch script
emits a perfectly valid artifact identical to the original and every downstream check
agrees it is fine. Per hunk: `assert new != old, '<hunk name> matched nothing'`. Then
assert the postconditions positively — the new declaration present exactly once, the old
one absent, the inserted marker counted once, and the mutated declaration ordered BEFORE
the block that assigns to it.

**Re-derive the patch from a fresh export at apply time; never reuse a candidate file
built earlier in the session.** The earlier file may encode a diagnosis that has since
been corrected — the naive single-hunk port above sat on disk looking applyable for an
hour — and a stale candidate is indistinguishable from a current one by inspection.

## Controls for the whole promotion

Record before the first write, re-read after:

- source definition count unchanged;
- `md5(nodes::text)` of the source definition unchanged;
- both engines' health endpoint returning 200 after the restart;
- the new id present exactly once, in the target database only.

Then verify the END-TO-END effect at the destination rather than on any HTTP status:
trigger the real caller and confirm the row, score or artifact the chain should produce.
