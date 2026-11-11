---
name: pending-work-record
description: Record blocked and deferred items in a file, not a reply.
version: 1.0.0
author: Hermes Agent
license: internal
metadata:
  hermes:
    tags: [pending, blockers, decisions, record, handoff]
    related_skills: [memory-as-index, review-board]
---

# Pending work record

## When to Use

Load this whenever something cannot be finished now: a blocker, a deferred task, or a
decision that belongs to the user. <OWNER>, 2026-10-11, asked for "records of the things
that we have pending" after open items had been living only inside chat replies.

## Why a file and not a reply

An open item mentioned in a reply survives exactly as long as the context window. After a
compaction it exists only if someone happened to restate it, and restating is how a
measured number quietly becomes a remembered one. Three costs, all observed on this
project:

- A question asked and never answered gets re-asked, which reads as not listening.
- A blocker reported once gets presented as new days later.
- An item the user already ruled on gets re-raised, which wastes their only scarce
  resource, attention.

## The file

    ~/.hermes/state/PENDING.md

One markdown table, newest first. Nothing else lives in this file: no narrative, no
progress log, no completed work.

    | id | opened | what | owner | status | evidence |
    |----|--------|------|-------|--------|----------|
    | P07 | 2026-10-11 | Which repo is canonical for the engine code | <OWNER> | OPEN | measured: two clones, 12 branches, last commit 10-09; an ops repo with 2 branches, records only; no third repo exists |

Rules for the columns:

- **owner** is `<OWNER>` or `Hermes`, never both. An item with two owners is two items.
- **status** is `OPEN`, `ANSWERED`, `DONE` or `DROPPED`. Nothing else.
- **evidence** carries the measurement that makes the item real, or the word `carried` if
  it is not yet measured. An item with neither is a rumour and does not belong here.
- An `ANSWERED` item keeps the ruling verbatim. A paraphrased ruling drifts.

## The three rules that make it work

**1. Write the item at the moment of blocking, not at the end of the session.** The end of
a session is exactly when context is thinnest and items get dropped. If something is
reported as blocked in a reply, it is written to the file in the same turn.

**2. Read it before asking the user anything.** A question already asked and answered is
in there with its ruling. A question already asked and unanswered gets re-raised as a
reminder, not as news.

**3. Never let it hold more than the open set.** Move `DONE` and `DROPPED` rows to a
`## Closed` section at the bottom on each pass. A pending record that accumulates history
becomes a log, and a log is not read.

## What does not go in here

- Procedures and pitfalls -> the relevant skill.
- Measured lessons with reasoning -> a vault note.
- Facts true in every session -> memory, as a pointer (see `memory-as-index`).
- Progress on a task currently in flight -> the task's own plan or todo list.

This file answers exactly one question: **what is outstanding, and whose move is it.**

## Close the loop out loud

When the user rules on an item, update the row in the same turn and say so in one clause.
An item silently marked answered is indistinguishable from an item ignored, and the user
is tracking whether their decisions land.
