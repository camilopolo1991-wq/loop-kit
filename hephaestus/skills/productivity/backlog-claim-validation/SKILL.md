---
name: backlog-claim-validation
description: Re-check backlog cards against the live system before work.
version: 1.0.0
author: hermes-curator
license: MIT
metadata:
  hermes:
    tags: [backlog, triage, verification, project-management]
    related_skills: [agent-guardrail-verification]
---

# Validating backlog claims against the live system

## When to Use

Load this when a board, backlog or issue tracker is about to drive work: promoting cards
to tasks, estimating a queue, or reporting "what is still broken". Also load it before
writing acceptance criteria that quote a card.

A card records what was true when someone looked. Nothing re-checks it. Expect a large
fraction to be false in the already-fixed direction, and budget the re-measurement as
part of the triage rather than as optional diligence.

## The two false directions are not symmetric

- **Card says broken, machine says fixed.** Costs a wasted task. Common, and the bulk of
  what triage finds.
- **Card says fixed or closed, machine says broken.** A silent regression nobody is
  watching. Rare, far more expensive, and only found by checking closed items too.

So do not triage by reading cards for plausibility. Plausibility is exactly what a stale
card has.

## Procedure

1. **Parse the board into structured data once**, rather than reading it card by card.
   Exported boards usually embed their content as a JSON blob in a script tag; extract
   and parse it, then work from the object. Print the section names with per-section
   counts and reconcile the total against the board's own tab counts before trusting the
   parse.
2. **Scrub before anything else if the artifact can carry personal data.** Use the
   system's own redaction tool as a filter, never a hand-rolled pattern list — an
   ad-hoc regex routinely finds an order of magnitude fewer names than the real
   redactor. Verify by re-scanning the output and by a positive control (inject a known
   name into the scrubbed text and confirm the detector still trips).
3. **Classify each card as machine-checkable or human-needed** before doing any checking.
   Machine-checkable means a command settles it. Everything else is a decision, a
   render, or an approval, and no amount of measurement closes it.
4. **Read the closing report of whatever produced the card, before checking the card.**
   A card derived from a completed task is downstream of that task's report, and the
   report is the authority on its own exceptions. It frequently states the finding
   already, with better provenance, and saves the trip to the machine.
   **But a report is evidence, not authority, wherever it REFUTES its own task's premise
   — re-measure every such refutation.** A report that overturns the thing its task was
   written to assume is the highest-value claim in it and the least reviewed: it reads as
   candour, it is usually accepted, and it propagates into follow-on cards and skill
   rules that are never traced back. Mechanism: the refutation is produced by a
   normaliser or parser the author wrote for that one pass, so a defect in it inverts the
   finding while every surrounding number reconciles.
5. **Prove the data was FROZEN before blaming drift for a disagreement with a report.**
   When your reading contradicts a report's, the two explanations are that the box moved
   or that one instrument is wrong, and they are distinguished by the data's own
   timestamps, not by which reading is newer. Select `min(ts), max(ts), count(*)` over
   the rows under dispute: `min = max`, at an instant predating the report, means nothing
   could have changed and the disagreement is instrument error — so the report's method is
   the defect and any card or rule derived from it must be withdrawn by name. Divergent
   timestamps straddling the report mean genuine drift, and then both readings are data
   (see the conflicting-verdicts rule below). Pair it with a control that the normaliser
   discriminates at all: pool two groups that must differ and require the distinct count
   to rise, because a transform that collapses everything to one value reports perfect
   uniformity.
6. **Batch the machine checks into one script with paired controls**, not one round trip
   per card. Each check prints its verdict and the measurement under it. See the
   controls section below.
7. **Report verdicts as a table with the measurement beside each**, grouped by verdict
   rather than by card order, so the false-card rate is visible as a number.

## Date the artifact against the record before grading a single claim

A held or blocked work item is frequently waiting for something that has since happened,
and no process closes it. Grading its claims one by one then produces a careful audit of
a question nobody needs answered. Establish supersession first, as a timeline:

- `stat` the spec and the closing report for their mtimes, and treat every claim in the
  spec as no fresher than the earlier of the two.
- Read the shared journal, state file and sibling reports for lines written AFTER those
  mtimes. A sibling task that touched the same surface is the usual superseder, and it
  names itself in its own closing line.
- Where the item was held for a HUMAN action, look for that action's own trace, timed
  after the report: a request log entry, a workflow execution row, a new artifact id. A
  held task whose gate cleared itself hours later is common and invisible from inside the
  task's own files.

Then grade claims against four verdicts, not two — STILL TRUE re-measured now, STALE
(true when written, the box has moved, quote both numbers), FALSE (never true), and
UNVERIFIABLE (name the instrument that would settle it). STALE and FALSE drive completely
different repairs: stale numbers get refreshed, a false one means the method that produced
it is suspect everywhere else in the same document.

**A task's own completed work is the most common superseder of its own spec.** Where the
work ran and then stopped at a gate, the spec's defect table describes a machine state
its own writer already changed, so nearly every figure in it is stale by the task's own
hand. Check the item's writes before hunting for an external cause.

## Confirm the batch boundary before triaging it

When the owner names a count ("the 54 cards before X"), count them yourself from the
parsed board and report the real figure before starting. Remembered counts drift, and
an hour spent grading the wrong subset is unrecoverable. If no combination of sections
yields their number, say so, state which boundary you used, and proceed on the measured
set rather than guessing which cards they meant.

## Query the schema before querying the data

A database-backed claim tempts a batch of queries written from the column names the
card uses. Those names are usually the card author's paraphrase. Read
`information_schema.columns` for the tables involved first, in one query, then write
the real ones — otherwise most of the batch fails on "column does not exist" and the
round trip is wasted.

**A guessed column name fails loudly; a guessed CONTAINER SHAPE fails silently.** Print
the real keys of any JSON artifact before parsing it. A verdict store keyed as a dict of
id-to-record, read as if it were a list, yields a length that looks exactly like a row
count and an index access that raises `KeyError: 0` — so "14 rows" was 14 keys, and a
follow-up set-difference built on the same misread reported every id as missing from the
index. Write one `rows_of()` normaliser that handles every observed shape and preserves
unrecognised keys, rather than assuming the shape per call site.

**Never eyeball a count from output that passed through `head`, `tail`, or a viewport.**
Count in code over the full set and print the total. A truncated listing of a registry
produced a wrong active/inactive split that was then reported as a measurement, and a
truncated `find` produced an undercount of verdict files large enough to misstate the
scope of the problem.

When a value visibly exists in a UI but its expected table is empty, the answer is
almost always storage location, not a broken pipeline. Search every table with a
similarly-shaped column before concluding anything is missing. Two classic causes:

- **One overloaded column holding two kinds of value at different granularity.** A
  `name`-style text column can carry both canonical keys and free-text items, with no
  type discriminator. Group by it and read the distinct values before assuming a key
  is absent.
- **Older records predating a schema convention.** Compare the rows' own metadata
  (author, created-at) across the present and absent groups; a clean split by date
  means a convention changed, not that a feature broke.

The real defect in that shape is usually downstream: any consumer aggregating by the
overloaded column silently drops whatever is stored under the other convention. Report
that as the finding, with the share of weight or rows lost.

## Every claimed absence needs a control

A check that reports "not found" has two explanations: the thing is absent, or the
instrument could not see. Pair each one:

- Searching for a missing file: also search for a file known to exist, with the same
  command.
- Reporting zero matches in a config: confirm the surrounding directive class is
  findable at all.
- Reporting an empty store: confirm the query tool runs and exits cleanly, so empty is a
  reading rather than a failure.

When a check depends on a path from the card, **verify the path exists before believing
the result**. Cards carry paths that were correct when written; a refactor moves the
file and the check then reports a true finding about a directory that does not exist.
The correct verdict in that case is CANNOT DETERMINE plus the real path, found by
searching for the symbol rather than the path.

## Separate deferred-on-purpose from broken

Two card types look identical on a board and are not: an unfixed defect, and a defect
somebody decided not to fix yet for a stated reason. Deferred cards usually say so in
their own body — "deliberately not fixed here", "held as the graded task", "its own
task and needs the owner".

Two consequences:

- A cluster of cards tracing to one completed task is usually a boundary that was held
  on purpose, not a task that limped. Read it as scope discipline, and say so.
- **Deferred cards unblock as a set, not one at a time.** They share a single gate — a
  merge, an approval, a decision. Triaging them individually produces many verdicts
  where one decision was needed. Name the gate instead.

## A stale board is still worth reading

Do not conclude that a high false rate makes the board worthless. Cards written by
people who hit the problem encode real complaints, and one of them will describe a
defect that still exists — including one introduced after the card was written. Treat a
card complaining that a gate over-fires as a ready-made regression suite for any recent
change to that gate.

## Converting a backlog to work items, at scale and unattended

When the task is not "is this card still true" but "turn hundreds of cards into work
items, discards and merges", the verdict set changes and so does the machinery: a
five-arm taxonomy, an append-only ledger so a crashed wave keeps its verdicts, batches
partitioned over the FULL card list so an index cannot renumber under a dispatched
worker, a recorder that validates the vocabulary, and a scheduler that re-dispatches
instead of waiting. Full procedure: `references/unattended-batch-triage.md`.

The single highest-value rule from that procedure, because it inverts the expected
finding: **search the existing work items for a matching acceptance criterion before
verdicting any card as new work.** On a backlog that has already been through one
conversion pass, a large share of cards are verbatim acceptance criteria of work items
that were written and never dispatched — the text matches because it was copied out of
the card. Triaging those as new manufactures duplicates of work that is already
specified and queued, and it hides the real finding, which is a dispatch gap rather than
a capture gap. Grep the work-item tree for the card's distinguishing phrase first.

**Never promote a card to a dispatched work item unattended.** Triage is reversible and a
dispatch is not, and the premise of the whole sweep is that card claims are unreliable.

## Hand-triage is a fallback, not the method

Where the project already defines triage as a unit of work for its own agent loop,
running it by hand produces a worse result even when it produces a faster one: a single
pass with no independent second reader, no DISPUTED path for disagreements, no pinned
board revision, and no durable report. Check for an existing triage task or design
before starting, and route through it. See `agent-loop-coordination`.

When you have already hand-graded part of a batch, hand those verdicts to the loop as
evidence explicitly marked *not authority* — a claim to re-check like any other, with
the worker's own measurement winning on conflict.

## Turning a spec into a delivery backlog

When the owner supplies the original design document and asks what is left to build,
the work is the same discipline applied to spec clauses instead of cards. See
`references/spec-delta-to-tickets.md` for the procedure, the half-built shapes to
probe for, and why ticket count is never converted into a duration.

## Verdicts land in one index, or the triage did not happen

A goal loop that verdicts cards writes its results where it writes everything else:
into its own evidence tree. Nothing promotes them. Check for a consolidation path
**before** dispatching triage, because its absence is invisible until someone asks what
the backlog says — one box held 90 verdict files carrying 828 rows across 445 unique
card ids, while the central index was 14 stale entries and no consolidator existed
anywhere in the tooling. Measurement was cheap; landing the result was the step that
never ran. Work completed and then stranded is the same loss as work never done, and it
is harder to see.

When building the consolidator:

- **Read-only by default, with an explicit `--write` and a refusal to clobber.** The
  existing central file is often the only record of its own key space and cannot be
  merged automatically — reconcile namespaces deliberately, never by overwrite.
- **Expect several id namespaces and reconcile them explicitly.** Different triage runs
  mint different id shapes for the same board, and a free-text-keyed legacy index shares
  no keys with any of them. Report the namespace census rather than silently keying on
  one.
- **Expect several FIELD namespaces too, and measure null-rate per producer.** Runs that
  minted different id shapes also named their detail fields differently: one used
  `premise`/`remaining_work`/`surface`, another `claim`/`proposed`/`settle_by`, a third
  `note`+`section`. An extractor written against one vocabulary returns the right record
  COUNT with the right ids while every description, size and route comes back null for
  whole subgroups — which reads as "these cards were never documented" and gets reported
  as unsized scope and a schedule risk. The id-level total reconciles perfectly, so it
  does not catch this. The control that does: group the null rate of each detail field BY
  SOURCE, and treat any field that is null for 100% of one producer and populated for
  another as a synonym to find, never as missing data. Read one record's real keys from
  each producer before writing the parser, then map synonyms explicitly
  (`desc = premise or claim or note`).
- **A dedicated status flag is not the only place its own status is recorded.** Cards
  carried `blocked_on_human: null` while naming the owner inside `remaining_work` or
  `settle_route` prose, so counting the flag alone undercounted human-gated work by about
  six-fold and made a delivery plan look machine-bound when it was decision-bound. Scan
  the free-text fields for the same signal (the stakeholders' names, "decide", "approve",
  "merge") and report the union, with the flagged and implied counts separately so the
  flag's reliability is visible.
- **Never silently reconcile conflicting verdicts, and never resolve one by recency.**
  The same card verdicted TRUE by one goal and FALSE by another is two readings, and both
  are data. Keep every observation, flag the id as conflicting, and surface the conflict
  count as a headline — they are invisible while the verdicts sit in separate directories.
  Where the store is append-only, collapse last-wins **on read** rather than rejecting the
  later write, so the audit trail survives while the effective state stays unambiguous.
- **Before escalating a conflict, check whether it is structurally decidable.** Conflicts
  split into two kinds and only one is owed to a human. A conflict of JUDGEMENT (is this
  worth doing, who owns it, is the risk acceptable) is theirs. A conflict whose claim is
  CHECKABLE is yours, and "duplicate of existing work" is almost always checkable: the
  claim names a work item and a criterion, so the test is whether that criterion actually
  exists in that item. Grep the work-item tree for the cited criterion id, with a
  deliberately fake id as the control. Escalating a decidable conflict spends the owner's
  attention on arithmetic, and the test routinely overturns a claim — a merge pointing at
  a real work item that carries no matching criterion is a wrong merge, however confident
  its prose.
- **Carry provenance on every row**: source file, goal, and the file's mtime, so
  staleness is visible. Also record whether the row had both a command and a control,
  and report the unevidenced fraction — verdicts that do not meet the evidence standard
  are a known quantity, not a surprise found later.

## Triaged, converted and closed are three different numbers

A verdict on every card is not progress on any card, and reporting "all N triaged"
invites the owner to hear "all N handled". Join each card's verdict against the
EXECUTION state of the work item it names, and report the three populations separately:
cards whose work item ran, cards whose work item exists and has never run, and cards
naming no work item at all. One fully-triaged board of 246 cards held 46 genuinely
closed, 56 waiting on work items that existed but had never executed, and 64 with no
work item written — so the headline "246/246 triaged" described 19% of the real state.
The cheap probe is a per-work-item check for the artifact that only a completed run
produces (a report file, a populated counter), because a directory and a spec file are
created by the dispatch step and prove only intent.

Re-derive this from the ledger rather than carrying it: the same figure quoted from an
earlier session's memory drifted by several cards in both directions, and a carried
figure never overrides a measured one.

## Reclassify the blocked pile before escalating any of it

A card parked as needing the owner's decision is frequently not a decision at all.
Three shapes hide there, and each is cleared without spending the owner's attention:
an ACTION somebody simply has to perform (restart a service, reply to a colleague, file
a support request); a card already SETTLED by work done since it was written; and a card
whose own numbers are REFUTED, which must be rewritten before it is worth ruling on.
Sort the pile into those three plus genuinely-live before composing a single question —
on one board, reclassification alone cleared four of forty-seven, and the staleness pass
settled three more.

Group what remains by the gate it shares (see the deferred-cards rule above) and look
for the one upstream definition several cards depend on; a third of one blocked pile
traced to a single undefined term, so one ruling was worth more than forty questions.

## A verdict is void unless it names the probe that produced it

When a batch classifier routes cards to probes by matching patterns against card text,
first-match-wins silently verdicts a card with a probe about something else: a card
whose body mentioned a neighbouring subsystem was graded by that subsystem's probe, and
the verdict was true about the probe's target and meaningless about the card. The
measurement looks impeccable because it IS impeccable — about the wrong thing.

Print the probe's identity beside every verdict and read that column before reporting;
a mismatch is obvious there and invisible in a verdict-only table. Prefer asserting the
probe's target against the card's own claim over pattern-routing, and treat a card
matching more than one probe pattern as needing a human read rather than the first hit.

**Then state the unprobed count as the headline, not the settled count.** A pass that
wrote ten probes against forty-seven cards settled fifteen; the remaining thirty-two
were UNKNOWN, which is 68% unmeasured and not coverage. Reporting the fifteen first
presents a third of a sweep as a sweep.

## Extracting a ruling the measurements cannot produce

When the gate is a definition the owner has never written down, the output is an
interview, not an analysis. Measure first so the questions are only the ones the system
cannot answer: what outcome data exists, how many comparable units there are, how much
reading the owner's judgement would actually require. That turns an open-ended "what
should this mean" into a short series of closed choices, and it stops you asking for
something the box already knows.

Fold each measurement into the question that depends on it, especially a measured trap:
where one outcome class held 76% of the rows, the question had to say so, because the
obvious form of agreement was defeated by the base rate and the owner would otherwise
have chosen a metric that scores high on a worthless model. Offer the form that beats
it (a forced pairwise choice) as a named option rather than assuming it.

Two rules for the interview itself:

- **Ask one question per turn and measure between them.** Each answer changes which
  measurement matters next; a batch of five asked up front gets answered against stale
  context, and the last two are usually the wrong questions.
- **An answer the owner says was a misclick is not data — discard it and re-ask
  verbatim.** Do not reconcile it against the corrected answer, and do not keep anything
  derived from it; carrying a retracted ruling forward is worse than having no ruling,
  because the artifact then cites the owner for a decision they did not make.

Write the result where definitions live (the knowledge base, not the work item), record
the measurements that bounded each answer beside it, and list what the ruling did NOT
settle. A definition with no pass bar is a legitimate outcome when the owner rules
"measure it and report against a null" — capture the refusal to set a threshold as the
decision it is, rather than filling one in.

## Reporting

State the false rate as a fraction of what was checkable, not of the whole board, and
say which cards were checkable. Distinguish four verdicts: TRUE, FALSE with the
measurement, CANNOT DETERMINE with what blocked it, and DEFERRED with the gate. Never
collapse CANNOT DETERMINE into FALSE — an unreadable check is not evidence of absence.
