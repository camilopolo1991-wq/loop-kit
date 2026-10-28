---
name: loop-record
description: How the LOOP leader records work, covering STATE.md, JOURNAL.md, commits, pushes and the per-goal report. Use when closing a task or a goal.
---

# Recording

## JOURNAL.md: append-only, one line per step
`loop-journal <GOAL-ID> <T-nn|GOAL> "<what happened, with ids, versionIds and shas>"`. The timestamp is measured by the script, never typed. The wrappers add their own lines for every PUT, rollback and SQL write.
Fixed line shapes, so `loop-journal --check` and the auditor can read them:
- `loop-journal <GOAL-ID> GOAL "START GOAL.md sha256 <first 16>"` at every leader start.
- `loop-journal <GOAL-ID> <window-id> "TRIPWIRE OPEN"` before `loop-tripwire start`, and `"TRIPWIRE CLOSE exit <n>"` after `loop-tripwire check`.
- `loop-journal <GOAL-ID> T<nn> "ROLLBACK <path> sha256 <first 16>"` by the writer, before its change.
- `loop-journal <GOAL-ID> T<nn> "DISPATCH <role> <card path>"` by the leader for every dispatch, scouts and reviewers as well as writers; <role> is scout, writer or reviewer, and `loop-journal --dispatches <GOAL-ID>` counts them.
- `loop-journal --check <GOAL-ID>` exits 1 when a writer task (owner column says writer) has a PASS line with no ROLLBACK line before it. The leader runs it before `GOAL CLOSED`, and a non-zero exit means the goal is not closed.

## STATE.md: current facts only, under 150 lines
Sections, in this order. Edit a section in place and never append history (history is the journal).
0. Last goal: id, verdict, date, and the one next thing.
1. Machine map: worktree paths, the verified sha on main, the record branch HEAD (`RECORD_BRANCH` from config.env), and the live version of each surface a goal touched.
2. Keep-list: branches the owner keeps (only by his word).
3. Open gates: what waits on the owner, one line each.
4. Standing traps found by goals, that are not yet in a skill. Move them into the skill when possible.
5. Drift log: at most 10 lines, newest first. Older lines go to the journal.
Over 150 lines means something belongs in the journal or a skill. Move it before closing the goal.

## Line endings in the record repo
At goal start the leader checks that the record repo has a `.gitattributes` holding `* text eol=lf`. If it is absent, the leader writes it ONLY when GOAL.md's Authority names the record repository as a whole; otherwise that is an owner gate: stop with VERDICT HELD and ask. When written, it rides in the goal's commit. (P34: GITHUB-01 wrote it under an Authority limited to STATE.md and the journal, because this rule said to.) Why: with `core.autocrlf` on, the working tree carried CR at every line end, so a byte check of a working-tree file read a CR the blob does not have (RECORD-01 AC2).

## Commits and pushes (the record branch `RECORD_BRANCH`, plus task branches the leader created for a writer)
- Record branch: exactly one commit at close, plus exactly one more only if the goal paused at an owner gate mid-goal, never one per task. Task branches are outside this cap. Tickets commit once per ticket. A goal that both hits a gate and later closes gets at most 2 commits total. If a skill file gets fixed during the goal, that fix rides along in the same commit as the goal's other changes (the leader definition's rule about fixing a skill alongside the finding); it never gets a separate commit of its own.
- Stage by path, never `git add -A`. Assert the staged file count matches what you intended to stage. Run `loop-scan` on the staged diff, and a hit stops the commit.
- `git commit -F <file>`: subject `docs(record): <summary>`, 72 characters or fewer, with a `Goal: <GOAL-ID>` footer. `hooks/commit-msg` in this kit enforces the shape when installed into the repo; without it the auditor checks it after the fact.
- Before the push: `loop-scan --range origin/<RECORD_BRANCH>..HEAD`. Then `git push origin <RECORD_BRANCH>`. Pushing is granted by default. Never push main.

## Tickets
A commit or a report that touches tickets names each ticket that changed, by id. A bulk import (many tickets at once) is reported as counts, not one line per id.

## report.md: one per goal, 80 lines or fewer, sent with loop-report
```
# <GOAL-ID>: <outcome>. VERDICT: DONE | HELD
Lead: the answer that decides most, in 3 lines.
Criteria: one line each: PASS/FAIL, how proven, evidence path.
Writes: each, with before and after and its rollback.
State: landed | shipped, not proven | done, per change, and what would move it.
Gates waiting: for the owner, with a recommendation and cost.
Proposed cards: one line each.
Incidents: guard denials that mattered, anything printed that should not have been, or "none".
Numbers: tasks, reviewer FAILs, writes, external calls, model calls spent, wall time. Wall time is measured: the first START line to the GOAL CLOSED or HELD line of this run, both timestamps quoted from `loop-journal --read`. Never estimated.
Commits: shas; unpushed count after the push.
branches: total | stale over 14 days | deleted or archived this batch.
deployments: only when a push from the record branch triggers a deploy on this machine; otherwise not applicable.
```
No carry-forward essay, no restating the goal, no narration. No em dashes. Every number not measured this goal is marked CARRIED, not stated as fact. Evidence stays on disk and the report points to it.

## Sending
One `loop-report` at close, plus one HELD report per stop. `loop-report` uses REPORT_SEND_CMD from config.env; with none set it writes the report and prints its path. No test mail, no proof mail, no channel check. If the send fails, write the draft to `report.md` (it already exists on disk) and print only its path, one line, nothing else.
