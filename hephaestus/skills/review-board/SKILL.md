---
name: review-board
description: Every sub-agent and the orchestrator get a reviewer. Cards, receipts, audit.
version: 1.0.0
platforms: [linux, macos]
---

# Review board: a reviewer for every sub-agent, and one for the orchestrator

Built 2026-10-20 from six independent reviews of the previous installation. The finding that
drove it: the Claude Code loop had a reviewer role, the Hermes side had none. Every
`delegate_task` result re-entered the conversation as fact, night triage appended any verdict
word it found, and "done" was a word the orchestrator wrote about itself. The owner asked for a
review of each sub-agent and of the orchestrator. This skill is that, as gates.

## The three layers

| layer | who reviews whom | mechanism |
|---|---|---|
| loop roles | loop-reviewer re-measures each writer task; loop-auditor audits leader, scout, writer and reviewer after close or hold | Claude Code agents, guards in `~/.claude/hooks`, checklists in skill loop-audit |
| orchestrator units | a REVIEW unit re-measures each `delegate_task` unit before its result is used | `unit-receipt.py` (post_tool_call) records claims; `review-gate.py` (pre_tool_call) blocks use of unreviewed claims and unreviewed DONE rows |
| the orchestrator | `orch_audit.py` counts what the orchestrator did outside the rules, on a schedule and at session end | cron plus on_session_end, exit 1 on any count, result lands in PENDING.md as a staged row |

## A unit card (what `delegate_task` must carry)

The review-gate refuses a card without these lines. Shape:

```
<one line: the question or the one change>
Premises: <fact> measured <instrument> | <fact> CARRIED. Refuting a premise is a successful outcome.
Scope: <surface, environment, what is out of scope>
Done when: <observable, with the control that proves the check can fail>
Return: <the handle you want back: absolute path, row id, url, sha> and <format, language>
Must not: <authority limits>
```

Numbers in a card are labelled measured or CARRIED, every one. A child cannot check a figure
you did not label and will restate it as fact (reference: verifying-delegated-reports).

## A review card (`REVIEW unit <id>`)

The unit-receipt line gives the id. The card names the unit's brief and its claimed handles,
never its result text (RESULT, proof, writes lines are refused by the gate), and asks for:

```
REVIEW unit <id>
Brief under review: <the unit's card, verbatim>
Claims to test: <handle> says <claim>   (one per line, from the receipt's handles)
Re-run the one query or command that reproduces each load-bearing number. Read the handle back
(file size, last line, row count). For each claim return: covered | partial | absent, the command
you ran, and what result would have failed it. A claim with no command is absent.
Return: VERDICT: PASS | FAIL | CANNOT DETERMINE, then the table. Read-only.
```

The reviewer is a fresh child. It never gets the first child's reasoning. If the first child was
truncated (receipt says TRUNCATED), the review starts with the artefact's size and last line.

## When the orchestrator re-measures instead

For one number, dispatching a review costs more than running the query. Run it, then write one
line to `$HERMES_HOME/state/units/<id>.remeasured`: the command, the value, the date. The gate
accepts that file as the review. A `.remeasured` file with no command in it is a lie the audit
will find.

## Marking work done

A PENDING.md row moves to DONE only with `review:<unit id>` (a PASS receipt) or
`measured:<command>` in its evidence column. The gate refuses the write otherwise. "Done" is a
reviewed state, not a word.

## The orchestrator's own audit

`$HERMES_HOME/scripts/orch_audit.py` reads `state/units/`, PENDING.md and the session log and
counts: units with a strong verdict and no review, review receipts with a FAIL that were followed
by use anyway, DONE rows with no review token, units that hit their iteration cap, dispatches per
goal per night over 2. Exit 1 on any count. Run it by cron at the end of a shift and from the
on_session_end hook. Its output goes to the owner unedited, and a staged PENDING row is written
for each count so the next session sees it. The orchestrator does not grade its own audit.

## Selftests

Every gate here proves it can fail: `review-gate.py --selftest` plants a unit receipt with no
review and requires a block, then a review receipt and requires allow. `orch_audit.py --selftest`
plants one unreviewed DONE unit and requires exit 1. A gate only ever observed passing is
decoration.
