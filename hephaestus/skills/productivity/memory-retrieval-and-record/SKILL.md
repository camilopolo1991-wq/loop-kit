---
name: memory-retrieval-and-record
description: Use when a corrected mistake recurs. Search, expire.
version: 1.0.0
author: Hermes Agent
license: internal
metadata:
  hermes:
    tags: [memory, vault, retrieval, record, obsidian, staleness]
    related_skills: [memory-as-index, pending-work-record, <OWNER>-working-agreement]
---

# Memory retrieval and record discipline

## When to Use

- The user says a correction was already given and it did not stick.
- A fact quoted from a note or from memory turned out to be stale.
- Two loaded skills disagree on what to do.
- Before ending a session in which anything was learned, corrected or measured.

`memory-as-index` says WHERE facts live. This skill is about the two transitions that
actually fail: getting the stored thing in front of the decision (retrieval) and
writing it in a shape that cannot go silently stale (record).

## Retrieval: search before acting

A correction passes four transitions before it changes an action: encoded, retained,
retrieved, influential. When a written-down mistake recurs, the broken one is almost
always RETRIEVAL — the rule sat two hundred lines deep in a file loaded whole, or a
superseded paragraph of a correct note was read as present fact, or the skill that
happened to be loaded won over the one that contradicted it. Adding more text does not
fix a retrieval failure; it makes the next one likelier, because adherence to an
always-loaded file drops with its length.

Before any non-trivial ask, run the keyword search across every layer:

    python3 ~/.hermes/scripts/recall.py "<2-4 keywords from the ask>"

Order of authority it searches: the user's working agreement (their corrections outrank
everything) → the pending record → skill headings → vault notes. Vault hits match
`tags:` before body text (the vault's own index; query by its tag words, which the tool
suggests), rank live above expired and newer above older, and print each note's
`valid_from`/`invalid_at` window plus a flag when it carries retractions or a
`CURRENT STATE` block that must be read first.

**A hit is a dated claim, not a fact.** Rules apply as written. Anything about live
system state — prompt text, node counts, secrets, row counts — is re-measured before it
is quoted, however recent the note.

**When two loaded instructions disagree, say so in one line before acting**, and the
user's words outrank any skill. Then fix the losing skill in place so the conflict
cannot recur.

## Record: write so it cannot go stale silently

The stale-recall mechanism on the write side is a note with a DATE and no VALIDITY
WINDOW: a confident dated claim contradicted a week later still reads as current,
because nothing says it stopped being true. Three rules, enforced by the vault lint for
`20 Notes` and `90 Meta`:

- Every note carries `valid_from:` (when it became true) and `invalid_at: null` while it
  holds.
- **A correction expires its predecessor in the same turn.** When a new measurement
  contradicts a note, set `invalid_at: <date>` and `superseded_by: <live note title>` on
  the OLD note as part of writing the new one. Writing the correction and leaving the old
  note live is the defect, not an omission.
- Long meta notes lead with a `CURRENT STATE` callout that is appended to and dated, so
  a top-down read cannot resurrect a retracted section below it.

**Record in the session that paid for the lesson.** A rule that says so does not fire;
a check does. Before ending a session:

    python3 ~/.hermes/scripts/record_gate.py

It counts learning signals in the agent log against writes to the vault, the pending
record and skills, and fails on "learned a lot, wrote nothing". A gap of days with no
writes during heavy work is where stale recall is born: the notes get written later,
from memory, in one evening.

## Derived files are never hand-edited

Anything injected into every turn (the open-loops block the pre-LLM hook reads) is
derived from its source of truth (`PENDING.md`) by the record gate on every run. A
hand-maintained second copy of a moving record is guaranteed to lag it, and the lag is
invisible from inside the session that is being misled. Wire the gate as an
`on_session_end` hook; the agent cannot edit `config.yaml`, so hand the user the three
lines to add.

## Pitfalls

- Searching storage for the right sentence proves retention, not influence. The test of
  a correction is behavioural: replay the trigger in a fresh session and see whether the
  action changes.
- A tag-substring match (`score` hits `scoring`) is loose on purpose for recall; do not
  tighten it to exact-match or notes with near-synonym tags vanish.
- **Insert pending rows with a string-replace on the header separator line, never with
  the patch tool anchored on the next row's `| Pnn |`.** Anchoring on the following row
  consumes its leading cells and glues it onto the new row's tail; it happened three times
  in one session and each needed a repair. Replace
  `|----|...|\n` with `|----|...|\n<new row>\n` in Python, then assert every `| P` line has
  exactly 6 cells by `awk -F'|'` (a raw pipe count is wrong: bodies carry `|` inside
  backticks).
