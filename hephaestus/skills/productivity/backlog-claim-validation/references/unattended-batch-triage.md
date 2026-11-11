# Unattended fan-out triage of a large card backlog

For turning hundreds of stale cards into verdicts overnight, with no human present to
unstick anything. The governing constraint is that the run must not stall: if one unit
is held, the next one starts anyway.

## Shape of the run

    parse board -> unclaimed set -> fixed-size batches -> N subagents in parallel
      -> each writes a verdict file -> recorder appends to an append-only ledger
      -> scheduler harvests, re-dispatches the next wave, repeats

Three properties make it survivable without supervision:

- **The ledger is append-only and keyed per card.** A wave that dies at card 200 keeps
  the first 199 verdicts. Nothing restarts from zero, and re-running the batcher simply
  skips what the ledger already holds.
- **The recorder validates the verdict vocabulary and reports rejects.** Anything outside
  the taxonomy is refused and counted, not silently coerced. Check the reject count every
  harvest; a non-zero count means a worker invented a verdict and its batch needs re-doing.
- **The scheduler re-dispatches rather than waiting.** It harvests whatever has landed,
  moves each consumed file aside so it cannot be double-counted, and launches the next
  batch numbers. A held or crashed unit costs its own batch, not the run.

Key the ledger on content (lane + title), not on batch index. Batch indices are derived
from "what is still untriaged", so they renumber between waves and a ledger keyed on them
will double-record.

## The verdict taxonomy for card-to-work-item conversion

This is a different question from "is the card's claim still true" and needs its own arms:

| verdict | meaning |
|---|---|
| `GOAL` | real, actionable now, enough signal to write a work item |
| `PRE-GOAL` | real, but a premise must be re-measured before it can be written |
| `MERGE` | duplicate or subset of another card, or of a work item that already exists |
| `DISCARD` | stale, done or superseded — must carry the evidence showing it |
| `BLOCKED` | genuinely needs a named human to supply a named thing |

`MERGE` is the arm most often missing, and on a mature backlog it is usually the largest
bucket. Without it every duplicate becomes a fresh work item.

## Rules that change the outcome most

- **Search the existing work items for a matching acceptance criterion before verdicting
  a card as new work.** On a backlog that has already been through one conversion pass,
  a large share of cards are verbatim acceptance criteria of work items that were written
  and never dispatched — the text is identical because it was copied. Re-triaging those
  as new manufactures duplicates of work that is already specified and waiting. Grep the
  work-item tree for the card's distinguishing phrase; where it hits, the verdict is
  `MERGE` and the finding is that the queue is undispatched, not uncaptured.
- **A lane label is not a verdict.** Cards filed under "blocked" were filed weeks ago and
  the blocker has often cleared since. Require every `BLOCKED` verdict to name WHO blocks
  it and WHAT specific thing they must supply; if the worker cannot name both, it is not
  blocked. Give the workers the list of blockers known to have cleared, or they will
  re-affirm the lane label from the card's own prose.
- **Tell workers the current date and the age of the cards.** Without it they read a
  card's present tense as present fact. The brief should state the spread ("written in
  September, it is now October") and the measured false rate from any pilot.

## The verdicts are claims too — audit before recording

A worker's verdict is a self-report and inherits every failure mode of a self-report.
Audit the batch before it lands, cheaply and mechanically:

- **Gate `DISCARD` on evidence.** A discard says "this is no longer true", which is
  exactly the claim that needs a measurement. Flag any discard whose evidence field is
  short or says "not checked", and report the audited fraction with the result.
- **Require the command in the evidence field**, not a conclusion. "Already fixed" is a
  verdict; `find / -name 'x*' returns 0 paths, control finds other real files` is
  evidence.
- **Check the ledger for duplicate keys after every harvest.** Equal row count and unique
  key count is the control that the recorder is not double-counting.
- **A worker's report ABOUT THE HARNESS is a self-report too — verify it before relaying
  it.** Workers inspect the shared machinery and will report data loss, missing
  ingestions or a broken recorder. Those claims are checkable in one query against the
  ledger, and they are not always right: an alarm that "8 of 12 verdicts were never
  ingested" can resolve to all 12 present. Relaying an unverified alarm hands the owner a
  phantom emergency and spends the credibility of the real findings alongside it. Check,
  then report the check.
- **Treat a worker that refuses rather than guesses as the system working.** When a
  worker's assignment turns out to be empty, stale or ambiguous, the correct output is an
  empty result plus a diagnosis — not a plausible set of verdicts for whatever cards it
  could find. Say so in the brief, and when one does it, trust that batch's other output
  more rather than less.

## Partition the FULL set, so a batch index is an identifier and not a cursor

Key the ledger on content (lane + title), never on batch index. That alone is not enough:
**slice the batches from the complete card list, not from the still-untriaged remainder.**

Deriving batches from the remaining pool makes every index a cursor that renumbers on
every record. Two failures follow, and the second is silent:

- A worker dispatched against a number captured minutes earlier finds its batch gone, or
  shrunk past its index. The honest ones refuse rather than guess; that is the behaviour
  to ask for explicitly in the brief, because the alternative is invented work.
- Two workers dispatched against different numbers receive overlapping cards and both
  triage them. A content-keyed ledger stops the double-COUNT but not the double-WORK, and
  if their verdicts disagree the store now holds two answers for one card.

Partitioning the full list fixes both: index `n` names the same cards in an hour as it
does now. Have `--batch n` print only the untriaged members of that partition and exit
non-zero when the partition is already complete, so a finished batch says so instead of
silently resolving to someone else's cards. Have the scheduler re-plan and dispatch only
indices the planner currently lists as having work.

After every harvest, check unique-key count against row count AND list the keys whose
verdicts disagree. Equal counts prove the recorder is not double-counting; they prove
nothing about two workers having answered the same card differently.

## Briefing the workers

Put the brief in a file and have every task load it, rather than repeating it per task.
One file means one place to fix a rule mid-run. The brief carries: the taxonomy, the
read-only limits, the facilities and their exact invocation, the host quirks that produce
silent wrong answers, and the instruction to pair every zero with a control.

Template placeholders in angle brackets inside a dispatch payload are rejected by some
dispatchers as unexpanded markers. Describe the output fields as a labelled list in prose
instead of an angle-bracket schema.

## Reporting to the absent owner

Write one durable log, appended per cycle, and push it where the owner reads on a phone.
Lead with the counts, then the findings that outrank the triage itself — a stale backlog
always contains a few live defects worth more than the sweep. Close with an explicit
ordered list of what needs the owner, since that is the only part they can act on before
the next cycle.

Never promote a card to a dispatched work item unattended. Triage is reversible, a
dispatch is not, and the whole premise of the sweep is that card claims are unreliable.
