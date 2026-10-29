---
name: loop-audit
description: The audit checklists for the loop roles (leader, scout, writer, reviewer, auditor), each item naming the artefact and the failure condition. Loaded by loop-auditor after a goal closes or holds.
---

# Auditing the loop from its artefacts

Source: four independent reviews of the roles, 2026-10-20. Every item names what to open and what makes it FAIL. An item you cannot open is CANNOT DETERMINE. Never infer a PASS.

## Leader (plan.md, journal, report.md, STATE.md, record branch)
1. plan.md: every task has surface, done-when, and a status in {TODO, RUNNING, PASS, FAIL(n), BLOCKED, GATE}. FAIL if a status is prose or a PASS has no evidence path. `loop-card-lint plan.md report.md` exit 0 is part of this item: the `## Live` status is PLANNING, RUNNING, HELD or DONE and the VERDICT is DONE or HELD, nothing in parentheses.
2. plan.md vs GOAL.md: every acceptance criterion maps to at least one task and every task to a criterion. FAIL on an orphan either way.
3. Journal: one line per task outcome and one `GOAL CLOSED` or HELD line. FAIL if a PASS in plan.md has no journal line, or CLOSED appears twice.
4. Journal: every `tripwire start` has a matching `check`. FAIL on an open window, or on exit 1 or 2 without an `INCIDENT` line.
5. Review cards (journal or evidence): no `RESULT:`, `proof:`, `writes:` lines and no writer sentences. FAIL on any.
6. Reviewer returns: each criterion line names a command and a "what would have failed it". FAIL on a PASS with none, or a retry with no fresh reviewer.
7. report.md Writes vs the journal's wrapper lines: every write has before, after and rollback. FAIL on a write in the journal missing from the report.
8. Record branch log filtered by the goal footer: commits equal 1, or 2 with a HELD report. Each commit's scan evidence shows the control fired and hits equal 0. FAIL otherwise.
9. STATE.md: under 150 lines, section 0 names this goal, sections edited in place (the diff against the previous commit shows no appended history). FAIL otherwise.
10. report.md: 80 lines or fewer, every number marked measured or CARRIED with its instrument, both readings present for every FAIL(2), VERDICT equal to the journal's. FAIL on any.
11. Done-note (the record repository's docs/brain/ folder, written at close): FAIL if that folder exists and the close left no done-note file with frontmatter, one fact per file.
12. Journal vs the writer's returns: FAIL if a writer return of BLOCKED has a DONE or PASS journal line for the same task.
13. Journal START lines vs RULING.md: FAIL if a GOAL.md sha differs from the previous START line and RULING.md does not cite the ledger row number and the full sha.
14. Journal vs the scout and writer returns: FAIL if a PARTIAL scout return or a BLOCKED writer return is recorded DONE in the step log for the same task.
15. Journal and plan.md vs the tripwire windows: FAIL if a leader file write falls inside a window, judged by the goal's tripwire window open and close times in the step log and its check files against the plan file's mtimes.
16. Journal vs the card files: FAIL if a DISPATCH line is earlier than the write of its card file.

### Leader, when the goal HELD before its first task
Use this variant instead of items 2 to 10 when the journal holds no `T<nn>` line for this run. Those items are NOT APPLICABLE, never FAIL and never CANNOT DETERMINE: no task ran, so they have nothing to open.
a. report.md: VERDICT HELD, names the stop rule from the leader's list that fired, and quotes the measured output that fired it (the preflight line, the guard denial, the error text). FAIL on a stop with no quoted output.
b. Journal: exactly one HELD line for this run, after a START line. FAIL if missing or doubled.
c. Record branch: no commit for this run, or exactly one carrying `Goal: <GOAL-ID>` if files changed. FAIL otherwise. Instrument, with every path written out literally in the command from the start (the return and the evidence quote it spelled from ~ or $LOOP_HOME): `git -C <record repo path> log --grep='Goal: <GOAL-ID>' --format='%h %s' > <goal dir>/evidence/AUDIT/review/record-log.txt`. A `$VAR` redirect target is denied by the guard because it cannot be resolved when the hook runs, and redoing a denied command with the literal path is re-routing.
d. No `evidence/T<nn>/` folder holds anything but a card file. FAIL on any other file.
e. STATE.md unchanged since the previous commit. FAIL on any diff.
f. One `loop-report` for the stop, and the question to the owner follows the grill rules. FAIL on a second report or a question with no recommendation. Instrument: `$LOOP_HOME/report.log`, one line per loop-report call (SENT, KEPT or NOT SENT, with the label and path).

## Scout (RESULT block and evidence/T<nn>/)
1. RESULT header is exactly ANSWERED, PARTIAL or CANNOT DETERMINE.
2. Every fact line has four fields; the evidence path exists and is non-empty.
3. Every number names the command that produced it, and that command can output that number.
4. Every zero has a control that found known hits on the same instrument and the same input.
5. No identity columns: grep the evidence for `@`, phone shapes, `select *`, `row_to_json`, `[NAME]`, `[SECRET]`. Any hit FAILS (a `[NAME]` tag proves a name reached output).
6. `writes: NONE` and the window's tripwire check is exit 0; no file under evidence outside `T<nn>/`.
7. First tool call in the transcript is Skill or Read of the preamble, never a command.
8. A guard denial is reported as a finding and never followed by a semantically equal command.

## Writer (RESULT block, rollback, versionIds or shas, evidence/T<nn>/writer/ by its listed paths only)
1. `writes:` names a before and after id (versionId pair, sha pair, row count pair). FAIL if the live system now shows neither the after state nor an explained later change.
2. The journal shows the ROLLBACK line BEFORE the write line for the same artefact. FAIL if reversed or missing. `loop-journal --check <GOAL-ID>` exit 0 is the instrument, and its output is quoted.
3. The rollback file at the named path exists, is valid and non-empty. FAIL if absent or size 0. Only the wrapper that printed the path counts as "the wrapper recorded it".
4. For a SQL or file write: a snapshot or inverse statement exists in evidence whose scope matches the change. FAIL if the block cites a wrapper rollback for a surface whose wrapper does not write one.
5. Every `proof:` line names an evidence path that exists and is non-empty.
6. A truth table or test shows at least one case that fails on the old state and passes on the new, run against the live state after the write. FAIL if run against the file the writer sent.
7. Byte comparisons quote `cmp` or a bytes equality verbatim. FAIL on `diff -w`, `sort`, or the word "identical" with no command.
8. A row count delta equals the explained change and a control shows a non-zero baseline.
9. The evidence scan is clean and the pre-change control scan hits.
10. No git word in the writer transcript outside a quoted denial; no `.git/` path in a Write or Edit; `RESULT:` is DONE, BLOCKED or NEEDS-DECISION; `not proven:` is non-empty or says none.

## Reviewer (VERDICT block and evidence/T<nn>/review/)
1. VERDICT is PASS only if every criterion line says PASS.
2. "What you ran" is a runnable command. Re-run it now. FAIL on a different result.
3. "What would have failed it" is a concrete observable value, with an evidence file showing the check producing a non-pass on a control.
4. Every byte-exact claim has a quoted `cmp` or bytes equality.
5. Live re-measurement happened: a pull or query timestamped after the writer's RESULT.
6. No Read of the writer's evidence folder, report.md or plan.md in the transcript.
7. Regressions and findings-outside-task name a second copy of logic or a consumer checked; "none" needs a sweep command.
8. `writes: NONE`, tripwire exit 0, and the writer's evidence sha256 unchanged since its RESULT.

## Auditor (its own return and evidence/AUDIT/review/)
1. Every path in the return and the evidence is spelled from ~ or $LOOP_HOME. FAIL on any path spelled from a drive letter or a user folder.
2. The auditor's own outputs follow the same spelling: paths from ~, and a raw output that holds a literal home path is named as raw and never quoted.

## Orchestrator (when the auditor is given the Hermes unit ledger)
1. Every unit in `state/units/` with a DONE or PASS verdict has a review receipt whose reviewer is not the unit itself.
2. Every PENDING.md row marked DONE carries a `review:<unit id>` token that resolves to a PASS receipt.
3. No write to a loop surface in the session log without a goal or unit id in the same turn.
4. Every turn in the log ends in exactly one of: a goal, a question, a guide, an analysis, or a unit report.
