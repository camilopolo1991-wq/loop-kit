---
name: loop-goal
description: The GOAL, plan and task-card formats for the LOOP loop, and how the leader writes cards for the scout, writer and reviewer. Use when starting, planning or dispatching a goal.
---

# Goals, plans and cards

A ticket is the unit of work. A GOAL.md is written only for work spanning several tickets; a single ticket carries its own Acceptance criteria, Authority and Budget, and needs no GOAL.md (skill loop-ticket has the ticket format and procedure).

## GOAL.md (written by the owner or the orchestrator; the leader never edits it)
```
# <GOAL-ID>: <outcome in one line>
Requirement: the owner's words, verbatim. What it does not ask for.
Acceptance criteria: numbered, each observable, each able to fail.
Authority: what the loop may do without asking (for example: writes to named surfaces, task branches). Everything else is a gate.
Budget: max writes, max external calls, max model calls, max wall time. Four ceilings, every one a number.
Out of scope: named.
Known context: pointers only (report ids, card titles). Never machine values: the scout measures those.
```
An edit to a placed GOAL.md leaves a signed trace: a commit by the owner, or a ledger row naming the owner as the source of the text, with the new sha256. The orchestrator's RULING.md names that trace by its ledger row number and the full sha. A GOAL.md whose sha changed with no such entry is not run.

## plan.md (the leader's, on disk, so a compaction costs nothing)
```
# <GOAL-ID> plan. Updated <UTC>
| T | task | surface / skill | done when | owner | status |
|---|---|---|---|---|---|
| T01 | ... | db / loop-db | ... | scout | PASS <evidence path> |
Open questions for the owner: (only gates)
## Live
goal: <id> | status: <PLANNING | RUNNING | HELD | DONE> | window: <open tripwire id or none> | branch: <checked-out task branch or none> | retries: T<nn>=<n> | gate: <pending gate or none>
Proposed cards: (findings outside the goal)
```
The Live block is rewritten before `TRIPWIRE OPEN` and after `TRIPWIRE CLOSE`, never inside a window, where only journal lines are written.
Task status values: TODO, RUNNING, PASS, FAIL(n), BLOCKED, GATE, as the first word of the status cell.
Goal status, the `status:` field in `## Live`: PLANNING, RUNNING, HELD, DONE. Nothing in parentheses, ever (`DONE (closing)` is not a status).
`loop-card-lint plan.md` checks both, and `loop-card-lint report.md` checks the VERDICT.

## Task card (leader to scout or writer)
```
TASK <GOAL-ID>/T<nn>: <one line>
Preamble: $LOOP_HOME/templates/GOAL_PREAMBLE.md (Read it first; never pasted here)
Load skill: <the surface skill on this machine, or "none (filesystem via loop-guard-run)">
Surface: <workflow id and node name | tables | file paths | branch>
Do: <exact, one change or one question>
Done when: <observable criteria, copied into the review card>
Proof: <truth table against pulled activeVersion | AST identity | row counts with control | byte diff | any expected-output string: raw `cmp` or bytes equality, command quoted in evidence>
Must not: <limits from the goal's authority>
Evidence to: $LOOP_HOME/goals/<GOAL-ID>/evidence/T<nn>/ (writer: .../T<nn>/writer/)
Card file: this card, written by the leader to evidence/T<nn>/card.md (writer: .../T<nn>/writer/card.md)
Premises: each figure marked measured <instrument> or CARRIED; refuting one is a successful outcome
Return: the role's 30-line format
```

## Review card (leader to reviewer). Never include the writer's reasoning.
```
REVIEW <GOAL-ID>/T<nn>
Preamble: $LOOP_HOME/templates/GOAL_PREAMBLE.md
Load skill: <same surface skill>
Criteria: <copied verbatim from the task card>
Artefacts: <workflow id plus versionId before and after | table and query | commit sha | file paths | rows the criterion names, copied in>
Earlier populations: <the commands and their last counts, re-run by the reviewer as its regression sweep>
Rollback recorded at: <path or command>
Return: the reviewer's format (evidence to .../T<nn>/review/)
Card file: evidence/T<nn>/review/card.md
```
The pretool guard denies a reviewer dispatch that carries RESULT/proof/writes lines, report.md, or the writer subfolder. Every retry gets a fresh reviewer.

## Rules the leader applies
- A card never routes a role to plan.md, STATE.md or the journal. The leader copies what the role needs into the card. When a criterion names PASS rows of plan.md or journal lines, the leader copies those rows into the review card's Artefacts, and the reviewer's rule (never read plan.md) stands. Criteria and Done when stay the GOAL's words, verbatim, even when those words name plan.md.
- Every card is written to its card file with the Write tool (that write makes the task's evidence folder), then `loop-card-lint <card file>` must exit 0, then the role is dispatched with the same text. A card is written before its tripwire window opens, never inside one.
- A GOAL.md whose sha changed is run only when RULING.md cites the ledger row number and the full sha.
- One goal at a time. Inside it, tasks run in order. Scouts may run in parallel when their questions do not depend on each other. Writers never run in parallel.
- A finding inside the goal's surface and authority that is reversible becomes a new task. Everything else becomes a proposed card.
- Two readings that disagree are both kept and shown. Never merge them into one answer.
- A carried figure (from a report or a card) is a claim to check, not a fact.
- Trap: readonly-guard.py judges every physical line of the Bash payload, heredoc data included. A scout or reviewer that writes evidence quoting a guarded command (loop-sql with the write flag, a git state verb, loop-n8n put) is denied, and nothing is saved. In a read-only card, ask the role to describe such a command in words, or have the leader write that evidence from the return. The redirect check also reads a literal greater-than sign inside heredoc data (an arrow, say) as a redirect outside evidence/, so write `result:` in its place. Read-only roles cannot rm, so a throwaway debug file left in evidence/ stays there. Debug in scratch, or not at all.
- A filesystem task (moving files to trash, writing a tarball) has no surface skill. Its card says `Surface: filesystem via loop-guard-run (no surface skill)` and quotes the GOAL's authority line. A card naming a skill that does not fit gets refused. Split a bulk move in two: a scout computes the exact list and every exclusion, the leader checks the list, and the writer moves only those rows, with rollback, manifest and a per-row progress log written before the first move.
- Trap: the harness refuses a subagent's Write of a file named `summary.md`, `report.md`, `findings.md` or `analysis.md`. A task card must name its evidence write-up something else (for example `census.md`), or the write silently fails.
- Rule, not a gate (nothing enforces a writer's choice of comparison; the auditor checks it after the fact): a task card's Proof naming any expected-output string is proven only by a raw byte comparison — `cmp` or a bytes equality (Python bytes ==), never a whitespace- or case-normalised comparison — with a control that fails on a one-byte change, and the evidence quotes the exact comparison command run.
- Always: a tripwire window brackets every batch of scout or reviewer tasks: one `loop-tripwire start <GOAL-ID> <window-id>` per batch (parallel scouts dispatched together for the same purpose share one window, not one each), no writer dispatched and no leader write besides journal lines until `loop-tripwire check` closes it. `check` exit 1 or exit 2 both mean "do not trust this batch": quarantine its findings, journal an `INCIDENT` line, and report it rather than continue on it silently. The one exception is a difference confined to the session settings file or a surface the owner edits by hand, which the owner confirms he made himself, recorded as noise, never assumed without asking him.
