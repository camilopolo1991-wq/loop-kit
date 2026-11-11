# Pipeline clone endpoint isolation

Use when a pipeline, workflow or job has been cloned into a pre-production instance and
the question is whether it can still reach production. Rewriting is step one; this is
step two and it is the one that catches the leak.

## Why rewriting is not enough

A rewrite pass replaces the forms its author thought of. The endpoint that reaches
production is the one nobody thought of. Observed leak shapes, all surviving a hostname
rewrite:

- a **raw IP literal and port** instead of a service name (`172.17.0.1:5678`)
- a node whose code was never touched because it contained no other rewrite marker
- a guard or state-update node, i.e. one that runs at the START or END rather than in the
  scoring/processing middle where attention goes
- an artifact built during an earlier production attempt, deployed verbatim later
- a path **computed at runtime** rather than written as a literal, e.g.
  `const path = input.stage === 'r1' ? 'r1-generate' : 'r2-generate'`. A rewrite keyed on
  the full prefixed path matches nothing here, and a grep for the staging prefix reports
  the node as clean because the prefix is genuinely absent. Extract every quoted fragment
  that is later concatenated into a request path, not only complete paths, and re-prefix
  each branch of the expression.

A whole-definition hash comparison cannot find these, and neither can a per-node diff
that normalises the staging host back to the production host: a node pointed at
production then reads as *identical to production*, which is exactly what makes it
dangerous. The per-node review and the endpoint enumeration are not redundant; neither is
sufficient alone.

## The enumeration

For every ENABLED node, extract all of:

| Kind | Pattern | Why it matters |
| --- | --- | --- |
| hostname | `hostname:\s*['"]([^'"]+)` | service-name targets |
| port | `port:\s*(\d+)` | a staging host on a production port |
| url host | `https?://([\w.\-]+)(?::(\d+))?` | inline URLs |
| raw IP | `\b\d{1,3}(?:\.\d{1,3}){3}\b` | bypasses every name-based rewrite |
| entry path | `['"](/webhook/[\w\-]+)` | must carry the staging prefix |
| credential var | `\$env\.([A-Z_]+)` | alert/billing paths |

Then classify each against an allowlist and **fail on anything not positively
recognised**. The default must be "finding", so an endpoint form this list does not
anticipate still reports rather than passing silently.

Allowlist shape:

```
ALLOW_HOSTS = {'<store>-staging', 'localhost', '127.0.0.1', '<external-api-host>'}
ALLOW_PORTS = {<staging-store-port>, 443, <staging-instance-port>}
DENY_MARKERS = {'<prod-store-host>': 'production store (writes live data)',
                '<prod-instance-ip>:<port>': 'production instance (triggers real jobs)',
                '<alert-host>': 'real alerting (messages humans)',
                '<billing-api-host>': 'billing API (costs money)'}
```

Order matters: **test the allowlist first**. `store-staging` contains `store` as a
substring, so marker-first matching reports every correct endpoint as a leak — one run
produced 45 findings of which nearly all were false, which buries the real one.

Skip disabled nodes and say so in the output; a disabled node cannot execute, and
counting it forces a permanent non-zero that trains everyone to ignore the gate.

## Resolving each finding

| Finding | Resolution |
| --- | --- |
| hostname naming the production store | rewrite to the staging store |
| node posting to the production instance with no staging counterpart | DISABLE the node |
| entry path without the staging prefix | re-prefix |
| raw IP | replace with a resolvable staging service name, or disable |

Disabling is legitimate where the called service has no staging counterpart AND the node
is not load-bearing for the property under test. Check the connection graph first: a node
whose inputs and outputs are at the tail of the chain can be disabled with no effect on
the middle, and most runners pass items through a disabled node unchanged. Record what
the disablement costs — a disabled composite-score trigger means the rig cannot validate
composites, only the per-item path.

## Proving it

Run the enumerator as a hard gate inside the deploy script, before and after the write,
and refuse to publish on a non-zero result. Then plant two defects and confirm each is
caught:

1. restore one production hostname → expect exit non-zero naming that node
2. re-enable a disabled production-reaching node → expect exit non-zero naming the port

Restore, confirm zero, and only then publish.

## Entry-point registration is separate state from the definition

Rewriting a path inside a node is not the same as changing what the engine routes. Three
distinct defects live in the registration table, and none is visible from the definition:

**Stale registrations survive a rename.** Engines commonly ADD a registration at startup
and never remove one whose path changed, so after a re-prefix both old and new paths are
registered and routable. Count registrations against declared paths; a registered total
meaningfully higher than the declared total is the tell. Compute the delete set as
`registered - declared`, assert no declared path leaked into it, delete only those rows,
and re-count.

**Two definitions can claim one path.** Only one wins: the engine registers whichever it
encounters first and the other silently never fires. A leftover test or spike definition
holding a real stage's path means that stage has never executed in this environment.
Group declared paths across every definition and fail on any count above one. Treat a hit
as a pre-existing defect to report, not as damage from the current change.

**Prove both by live probe, not by reading rows.** After the cleanup:

| Probe | Expected | Meaning |
| --- | --- | --- |
| old unprefixed path | not-found | rename actually took effect |
| new prefixed path | validation or auth error | registered and reachable |
| path a node declares but is inactive | not-found | acceptable, state it |

A validation or auth error is the PASS signal here: it proves the route exists and the
handler ran. Only not-found proves absence.

## A caller that does not assert its own response status

An internal node that fires an outbound request, captures the result and writes an audit
row without branching on the status code reports `success` on every run while the call
404s every time. The downstream effect is simply absent, the callee's execution history
is empty, and the UI renders the missing output as a failure of the callee — so the
investigation starts at the component that never ran.

The tell is a high success count on the CALLER paired with zero executions on the CALLEE.
Check that pair before debugging either one. When fixing, decode the caller's stored
execution record and read the captured response body; a `Cannot POST /<path>` string names
the routing defect immediately. Where you own the caller, make the non-2xx branch fail the
node rather than audit-and-continue — a silent swallow of 404 turns a wiring break into
ninety successful runs that did nothing.

## Auth-gated entry points and the forgery boundary

Census the gate state of every entry point before designing an end-to-end run, because a
signed endpoint cannot be driven by a hand-rolled client. Probe each with an empty body
and classify on the BODY:

| Response | Classification |
| --- | --- |
| explicit auth/signature error | gated — reachable only via the real client |
| accepted, missing-field or empty response | open — drivable directly |

Do not mint a signature to get past a gate, even to test the gate: a path proven with a
forged credential proves nothing about the real path, and the application that holds the
signing secret is the only legitimate driver. Report the split (how many gated, how many
open), run the open stages, and name the gated ones as blocked on the client rather than
reporting a partial run as a full one.

Client reachability is a separate question from correctness: a cloud-hosted preview build
cannot reach a backend bound to loopback or a host-local bridge address. Read the
published bind addresses first; where they are host-local, run the client on the same host
and forward a port instead of exposing the service.

## The runtime control

Code inspection is not containment. After publishing, run ONE subject through and
compare a production fingerprint captured immediately before: row counts in every table
the pipeline writes, plus the `updated_at` of the specific records involved at full
precision. Identical counts and timestamps to the microsecond is the positive
observation; anything else means a path is still open. Capture the fingerprint before the
run, not after — a count taken afterwards cannot distinguish "nothing happened" from
"something happened and this is the new normal".
