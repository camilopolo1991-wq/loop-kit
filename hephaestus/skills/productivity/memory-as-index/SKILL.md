---
name: memory-as-index
description: Memory holds pointers; the vault holds the detail.
version: 1.0.0
author: Hermes Agent
license: internal
metadata:
  hermes:
    tags: [memory, vault, context, obsidian, discipline]
    related_skills: [obsidian, working-agreement, review-board]
---

# Memory as an index, not a store

## When to Use

Load this before writing persistent memory, when a memory write is rejected for overflow,
or when a durable fact feels too long to save. <OWNER>'s instruction, 2026-10-11:

> "We can reuse the amount of memory that is there so you can go follow this tag on the
> vault or follow this thing on the vault and the important stuff, so we can reuse the
> memory for new stuff."

## The rule

**Memory carries the trigger and the pointer. The vault carries the facts.**

Memory has a hard character budget (2,200 on this deployment) and is injected into every
turn, so every character competes with every future fact. The vault is unbounded, costs
nothing until read, and is already gated for correctness. A paragraph of detail in memory
is a paragraph that blocks the next ten facts.

A memory entry should answer *when do I need to go look*, never *what is the answer*:

    BAD  (burns 520 chars, goes stale silently)
      (worked example from the previous installation removed: it named company hosts. The shape: one
      line that says WHICH vault note holds the topology, never the topology itself.)
      before probing or claiming anything is down.

The second form is **better**, not merely shorter: the vault note holds the container
table, the port-boundary trap and the two readings that look like outages, none of which
would have fitted in memory at all.

## What belongs where

| content | home | why |
|---|---|---|
| Who the user is, how they want to be addressed | memory | needed before any tool call |
| A standing prohibition (never forge the session JWT) | memory | must fire without a lookup |
| A trap that silently returns a wrong answer | memory, one line | the cost of not knowing is a false measurement |
| Infrastructure tables, inventories, topology | **vault**, pointer in memory | long, changes, benefits from the lint gate |
| A procedure or workflow | **skill** | loads only when relevant |
| A measured lesson with reasoning | **vault note** | needs prose to be useful |
| Task progress, what is still open | **pending record**, not memory | changes hourly; see `pending-work-record` |

## Writing the pointer

Three parts, in this order:

1. **The trigger**: the situation in which this matters ("before probing or claiming
   anything is down").
2. **The scope**: enough of a contents list that the pointer is self-evaluating, so the
   decision to follow it needs no guesswork ("prod UI host, staging UI host, containers,
   ports, repos, DB id collisions").
3. **The path**: the exact vault note or skill name, verbatim, so it resolves first try.

A pointer without a trigger is never followed. A pointer without scope gets followed too
often or not at all. A pointer with a guessed path fails silently, which is the worst of
the three because a failed lookup proves only that the lookup failed.

## Consolidating when full

The memory tool is **all-or-nothing per batch** and the limit is checked on the final
result. So a single batch may remove, shorten and add together, and that is the only
reliable way to land a fact when memory is full.

Measured failure, 2026-10-11: four consecutive rejected batches, each trying to shorten a
little and add a lot, every one overflowing. After four failures the tool locks out for
the turn and the fact is lost. What worked was moving an entire block of detail to the
vault and replacing it with a pointer **in the same batch** as the new fact.

So when a write is rejected:

1. Do not retry with a slightly shorter version. That is the loop that burns the budget.
2. Find the **longest** entry, not the stalest, and ask whether its detail belongs in the
   vault. Length is the actionable property.
3. Write the vault note **first**, run the vault's lint gate, and only then replace the
   memory entry with a pointer in one batch alongside the new fact.
4. Count before sending: the batch is evaluated as a whole, so a replace that shortens by
   400 and an add that costs 300 nets to 100 saved.

## Phrasing

Memory is re-read as context in every future session, so write **declarative facts, not
instructions**. `User prefers concise responses` is a fact. `Always respond concisely` is
a directive that will later override the user's actual request in that moment.

## Verify the pointer resolves

A pointer is a promise that a path exists. Before finishing, confirm the target is really
there and the gate passes:

    ls "$VAULT/90 Meta/<Note Title>.md"
    cd "$VAULT" && python3 scripts/lint.py; echo "rc=$?"

Read the exit code **directly**, never through a pipe: `cmd | grep` reports grep's status,
which is how a gate that correctly exited 1 was once read as a pass.

One more trap, measured on the author's own note: the vault's PII gate flags
**email-shaped strings**, and an SSH git remote (`<GIT-REMOTE>`) is email-shaped.
It failed the gate on a note documenting repositories. Write remotes as `host:org/repo.git`
and describe the user in prose.
