# Estate-level parity: making two whole environments mirror

The per-unit promotion procedure in SKILL.md is the inner loop. This is the outer
loop, for the job "make staging and prod reflect the same thing so we can rely on it".

## 1. Classify before you count

Every difference falls in exactly one of three buckets, and the buckets decide the
work. Write them down as a parity map BEFORE touching anything, and keep it as the
living index of the job (not a final report).

| bucket | meaning | action |
|---|---|---|
| NATURAL | environment binding or control: DB name, port, path prefix, hostname, alert destination, a deliberately different timeout, test data | NEVER sync. Copying it across is the bug. Encode as the normaliser's rewrite list. |
| MUST-MATCH | the product's logic: scoring chain, auth verification + which secret each route names, data-writing routes, error-handling SHAPE, UI logic | any difference beyond NATURAL tokens is undeclared drift and blocks promotion until classified |
| DECLARED | a known divergence with an owner and a reason (a feature only one side has yet, a rewrite under test) | each needs a ruling: promote, backport, or move to NATURAL with a reason |

The tell for a NATURAL item mistaken for drift: it differs on EVERY twinned unit the
same way (`stg-` prefixes, `:5679`). The tell for MUST-MATCH drift mistaken for
natural: only one unit has it.

## 2. Normalise, then read, then count

Order matters. Counting first produces "35 of 41 differ", which is true and useless.

1. Build the normaliser from the NATURAL list and apply it to both sides.
2. Expand multi-line string fields (code bodies, prompts) into real lines.
3. Diff per node; keep only non-blank differing lines; drop `"options": {}` and
   key-order noise.
4. Classify each remaining node: COSMETIC / ENV-NATURAL (token the normaliser
   missed, add it) / SOURCE-AHEAD / TARGET-AHEAD / CONFLICT (both changed differently).
5. Only now count, and count per node, never per environment. "Which side is ahead"
   is a per-node answer.

Labels and titles are documentation, not evidence: a version column can match on
different text and a title can claim "five-dimension" over six. Diff the bytes.

## 3. Fan out the reading; keep the writing serial

Thirty-plus units cannot be read in one context without the picture going stale. Split
by concern (scoring chain / auth and writes / intake and routing), dispatch one
read-only reader per group with the SAME classification rubric and the SAME output
shape (one section per unit, one line per differing node, a verdict per unit, a
summary table). Consolidate the verdict files into one ruling sheet for the human.

Give every reader a diff tool that expands code bodies to lines and does NOT truncate
— a 200-char line cap hides the one field that matters (a `secretKeyName` nested in
`workflowInputs`), and each reader then patches its own copy of the tool. Tell readers
what is ALREADY handled so they classify it as done instead of re-proposing it, and
which concern is tracked separately (they note it, they do not classify it).

A reader's count is bounded by its slice. When a reader reports "N routes drift" for a
concern that cuts across groups, re-measure estate-wide yourself before quoting the
number; the auth reader saw five of ten secret drifts because the other five lived in
the intake and other workflows.

Consolidate into a ruling sheet with an execution order in waves — safe backports,
safe promotions, needs-a-timing-test, needs-the-owner — and name the blockers readers
surfaced (a sub-workflow with no twin blocks every unit that calls it). Then fan out
again: one builder per independent unit, each with the proven apply pattern as the
template to copy, staging-only writes, snapshot-first, dry-run then apply, a live
firing proof, and an evidence file. Keep two-sided contract changes (verifier + signer)
for yourself.

Writes stay gated per unit: one unit, built from its own target's graph, proven on
that target. Parallel builders are fine when their units share no workflow.

## 4. Work both directions as concurrent streams

Each side is ahead somewhere. Run the promotion stream (source ahead -> target) and the
backport stream (target ahead -> source) in parallel, each with its own snapshots and
proofs. A backport is not the "safe" direction and gets every gate the promotion gets.

Sequence by LAYER, whole layer first: backend (workflows, prompts, verification
contracts) to green before any frontend sync, because a UI synced onto a drifted
backend ships the drift. Confirm the layer order with the user once, then do not
revisit it.

## 5. Contracts move as pairs

A webhook verifier and its signer, a route and its callers, a prompt and the node that
parses its output: changing one side alone breaks the environment between the two
writes. Before the dry run of any contract-side change, locate the counterpart on the
same environment (grep the UI tree for the signer function, grep workflows for
callers), and either move both in one step or stop and get the direction ruled.

When the two sides disagree on a contract, the side where real users run is the
default direction — but a workaround built on top of the drift (a second signer
function added so the UI fits the wrong verifier) must be REMOVED when the drift is
fixed, not carried forward.

## 6. The unit of promotion is a JOURNEY LEG, and the proof is running it

Promoting one node per round-trip and proving the node is the failure shape of this
job: a dozen units land, each proven in isolation, and the user's leg (R1, R2, the
composite) is still unproven at the end. The owner reads that as "why is this merge so
difficult". It is difficult because the loop is wrong, not because the diff is large.

**Start from a dated registry, not from a diff.** One table, every workflow name on both
sides: live version id, when that version was published and by whom, node count,
logic-only differing nodes, and a CALL per row (IDENTICAL / PUSH / PULL / CONFLICT /
ONE-SIDE-ONLY / TEST). Publish dates settle "which side is newer" per workflow; a
CONFLICT is a row where both sides carry exclusive content, and only those need a
human. Regenerate the registry after every apply; it is the scoreboard.

**Then group by what the user's click runs.** A leg = the workflows one user action
triggers, plus the prompts they read. `diff <leg>` shows the real items; `apply <leg>`
snapshots every target, swaps every differing body from the source into the target's
graph, gates, publishes each, restarts ONCE, and re-diffs. Prompts stored in a DB row
are part of the leg (compare whitespace-stripped md5 + version, not length — trailing
blank lines differ by environment). Then prove the LEG by driving it through the UI;
nothing else counts as proof of a leg.

Normaliser additions this needs, or every workflow reads as drifted: strip `options: {}`;
map `"path": "stg-x"` to `"path": "x"`; replace 16-char sub-workflow ids with a
placeholder; collapse runs of `\n`; strip `//` comments; unify quote style; ignore
`onError` unless the body also differs (error wiring is a per-side choice, report it).

## 7. Inserting a node into a live graph

- **A Code node has ONE output. Branch with an IF node.** Returning
  `[[items], [items]]` from Code does not fan out; the second array is dropped and
  the "refused" branch runs the normal path. Tag the item (`__route: 'refused'`) in
  Code, then an IF on that field feeds the two targets.
- **By-name readers bypass an inserted node.** Downstream nodes that read
  `$('Upstream Node')` see the ORIGINAL upstream output, not the modified item the
  new node passed along, so a value rewritten in transit (a stripped marker, a
  normalised name) never reaches them. Grep the graph for `$('<upstream>')` and
  rewire those readers to the inserted node, and assert it in the dry run.
- A rescore/retrigger route has its own required field names (`actor_user_id`, not
  `user_id`); a 200 in 0.1s with no execution is the responder echoing before the
  validator ran. Read the route's validate node for its required list before the
  first call, then confirm an execution row started.
- After a container restart, wait for `healthz` 200 AND then a few seconds more
  before the first webhook probe; a 404 "webhook not registered" in the first
  seconds is registration lag, not a failed publish.
- **A restart kills in-flight executions as `crashed`, including the user's.** A
  transcript saved in the same second as your restart leaves a candidate with no
  score and a held lock. Before restarting a shared engine, check for running
  executions; afterwards, list `status='crashed'` in the window and rerun them
  once the lock window expires — say so, do not force rows.

## 8. Re-measure, attach, repeat

After each landed pair, re-run the full normalised scan and append the scoreboard
(twinned / identical / still-drifted / source-only / target-only) to the parity map
with a date. The target state is: every MUST-MATCH unit identical after
normalisation, every DECLARED item resolved, scoreboard attached to the final
promotion report. The job is done when the scan says so, not when the map is written.

## 9. When the chain is identical and the number still differs, stop diffing

Scorer logic, prompts and guide generators byte-equivalent on both sides, and the
same byte-identical fixture still scores 25-30 points lower on the target: parity of
the SCORER is proven and re-diffing it is the loop that never ends. Read the
per-dimension row before theorising: one dimension at `weak` against five at
`strong` names the cause (the fixture's experience does not match THIS requisition's
responsibility list), and that is a fixture-vs-requisition mismatch, not a scorer
difference. **A score comparison across environments is only valid against the same
requisition on both sides**; a replica scored 90 on staging against req A and 61 on
prod against req B measured two jobs, not two scorers. Twin the requisition first
(same JD, same weights), then compare.

## 10. An auth failure right after a push may be months old

When a UI action fails with "Auth failed" / 400 on the target just after a parity
push, read the verifier node's `$env.<SECRET>` name and the executing version's publish
date before blaming the push. The tell for a long-dead path: a daily-constant execution
count (a schedule) with zero `mode='webhook'` rows in 30 days except the user's own
clicks. Fix it as its own one-line unit with its own snapshot; it is the same
contract-pair defect as §5, found on the other side.

## 11. The diff loop is wrong when the owner asks "why is this merge so difficult"

That question means the unit of work is too small, not that the diff is too big. The
answer is never a better per-node diff; it is §6 (registry + journey legs) and then
running the leg. Switch immediately, say so in one line, and do not report another
node.
