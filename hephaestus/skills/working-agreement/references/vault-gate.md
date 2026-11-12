# The vault gate: three places, not a filing cabinet

Read this when: before writing a goal, after measuring anything that contradicts a note, and at goal close.

Split out of `SKILL.md` on 2026-10-09 for progressive disclosure
(Anthropic: SKILL.md body under 500 lines; detail lives in `references/`,
never duplicated in both).

## Contents

- Retrieval beats writing. Spend the effort on the read, not the write
- Reachability is part of retrieval: do not leave a lesson orphaned
- Why this is a script and not a rule
- Write-back: `scripts/harvest-findings.py`

## The vault is a gate, in three places, not a filing cabinet

`scripts/vault-gate.py` (alias `predispatch-vault-check.py`). Exit 1 = stop,
exit 2 = cannot determine (NOT a pass), exit 0 = proceed. Capture the exit code
directly: `rc=$?` after a pipeline reads the LAST command, so `| sed` swallows the
verdict and turns the gate into a check that cannot fail. That mistake was made
while testing this very script.

**1. Before asking him anything** — "search-before-ask":
```
python3 scripts/vault-gate.py --ask "<the question verbatim>"
```
Exit 1 means a note may already answer it. His attention is the scarcest resource
in the system; his standing rule is already "can the box answer it?" — the vault is
the second source, checked first, not after. Proven against four real questions
asked on 2026-10-01: three were already answerable from the vault. Only a value
judgement, an authority call, or a fact in his head alone survives this gate.

**2. Before WRITING a goal** — find what is already known:
```
python3 scripts/vault-gate.py --topic "<subsystem and mechanism words>"
```
Fold the hits into the goal as carried evidence WITH their instruments, so the goal
re-verifies rather than rediscovers. A goal that measures what the vault already
holds costs a full agent run to learn nothing.

**3. Before DISPATCHING** — prior lessons about its mechanisms:
```
python3 scripts/vault-gate.py --goal <GOALFILE> [--ack '<note title substr>' ...]
```
Read the hits, fold the lesson into the GOAL text, then `--ack`. Acking without
folding is defeating the gate.

**4. Before PROPOSING A CHANGE TO AN INSTRUMENT, or ratifying a leader's claim**
```
python3 scripts/vault-gate.py --topic "<instrument> <mechanism> <failure words>"
```
Added 2026-10-07 after it was skipped, and skipping it cost a reverted rule and a wasted
approval from the owner. Proposing to loosen a guard, widen an exemption, relax a threshold,
or ratifying a leader's claim are all *acting on a belief about a mechanism*. That is
exactly when prior knowledge decides the answer, and it was the one moment the gate did
not fire, because triggers 1-3 are "ask him", "write a goal", "dispatch". None covers the
fix round of a goal already running.

Measured afterwards, retrieval was never the problem:
```
vault-gate --topic "tripwire peer differences noise exemption concurrency"
  -> rc=0, ranked the exact note FIRST of 3
```
The note that would have stopped it, *An integrity check that cannot tell peers from
intruders forces work to be serial*, was written nine days earlier, scored top, and named
the precise repair as the dangerous one. It was simply never queried.

### Retrieval beats writing. Spend the effort on the read, not the write

The measured finding of the day, and it matches the literature. *Diagnosing Retrieval vs
Utilization Bottlenecks in LLM Agent Memory* (ICLR 2026 MemAgents) crosses three write
strategies with three retrieval methods and finds **retrieval dominates: ~20 points of
accuracy across retrieval methods versus 3-8 across write strategies**, with raw chunked
storage matching expensive lossy summarisation. Breakdowns concentrate at the retrieval
stage, not at utilisation.

This vault measures the same way. The write side is healthy and is NOT where to spend
effort:
```
60 notes, 239 links, median 4 inbound, 0 dangling targets, lint rc=0
```
Every failure this week was a read that never happened, not a note missing or badly
written. **Stop optimising note quality. Optimise the moment of asking.**

Corollary, from *When Retrieval Fails Before It Begins* (FAGEN@ICML 2026): evidence can
survive storage yet be unreachable from the query that needs it, when the upstream
prerequisite is weakly aligned with the query wording. Defence: query with **mechanism
words, not conclusion words**. "Should I allow peer diffs" is a conclusion and misses.
"tripwire peer concurrency exemption" is a mechanism and hits.

### Reachability is part of retrieval: do not leave a lesson orphaned

A note nothing links to is findable only if the search wording happens to match it. Three
real lessons are orphaned and should be linked from a note a future reader passes through:
```
Engine Record - Durable Lessons                                           [10 Sources]
Vault Conventions                                                          [90 Meta]
The unstable thing is the per-item judgement, not the arithmetic above it  [20 Notes]
```
(`_retired/` and `_raw/` orphans are intentional and fine.)

When writing a note, add the backlink **from** the note a future reader passes through,
not just forward links out of the new one. Inbound links are the retrieval path.

### Why this is a script and not a rule

Measured 2026-10-01: across a 12-hour session, every lesson "learned" was already in
the vault, written days earlier. The note "An integrity check that cannot tell peers
from intruders forces work to be serial" (2026-09-28) described the exact concurrency
failure then rediscovered at the cost of two goals and three Opus review windows. The
vault's most-linked note is "A synthetic test proves nothing without a control" and
uncontrolled checks were still run that night. Capture was never the problem.
Retrieval at the moment of need was. A second brain read only when asked about is a
filing cabinet.

Prior art, researched 2026-10-01: "Search-Before-Ask" is a named agent-memory pattern
(MemNexus); obsidian-mind's CLAUDE.md marks vault search "Use PROACTIVELY before
reading files" with an explicit preference order; query rewriting / HyDE (arXiv
2305.14283) is the documented fix for the query-vocabulary mismatch. The gate's
TRIGGERS table IS that query expansion, hand-built because this vault has no semantic
index — which the vault's own research note predicted: "no semantic search ... if you
find yourself unable to recall a note because you do not remember its words, that is
the signal."

Gate-design lessons, each paid for: match note TITLES for a goal (body matching
flagged 32 of 50 notes and would have been acked blindly) but match BODIES for a
question (there the question is "does an answer exist", not "is there a lesson");
match keywords on word boundaries (`rag` matched inside `storage` and fired five
irrelevant retrieval notes); and index by the vocabulary of the QUESTION, not of the
answer. A gate that fires on everything is the same as no gate.

### Write-back: `scripts/harvest-findings.py`

The other half. Reads closed goal reports, stages vault-ready candidates under
`_vault_candidates/CANDIDATES.md`, marking each finding `new` or `covered by: <note>`.
It writes NOTHING to the vault — an unreviewed auto-note is how a second brain fills
with noise. Run it at goal close, not at session close: four goals closed on
2026-10-01 and produced exactly ONE hand-edited note. Vault write activity was 38
notes on 27 Sep then 8, 1, 2, 1 — not lost interest, an absent write path.
