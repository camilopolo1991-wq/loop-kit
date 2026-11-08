# Goal preamble: shared hard lines and traps
# Every GOAL includes this file by reference. Every task and review card names its path.
# Roles READ it as their first action. Leaders never paste it into a card.
# Machine-specific traps (schema quirks, tool quirks, hosts) go in $LOOP_HOME/templates/TRAPS.md,
# which a card names. This file stays generic.

## HARD LINES. A breach is an INCIDENT: journal it immediately

1. **Never SELECT identity columns.** No email, full name, phone, or free text about a person into any query output, file, or tool result, a scout's stdout included. Scores, classes, ids (8-char prefix) and counts only. `select *` on any table that holds people is the usual way this happens. Name your columns. To prove a row exists, use `left(id::text,8)` and a count.
2. **Never message a human.** No chat webhook, no email, no notification. A workflow you trigger can message a human on your behalf: check its error wiring before you fire anything.
3. **Reports go through `loop-report` only.**
4. **No push to main, no merge, no grant, no role creation, no spend** without the owner.
5. **Never print a secret or forge a token.** Compare secrets by fingerprint, in process.

## MEASUREMENT DISCIPLINE

- **HTTP 200 means nothing.** Branch on the body. Several surfaces return 200 on failure.
- **Pair every zero with a control**, run against the same input, and name the instrument beside the number.
- **A check that cannot fail is worse than no check.** Verify by positive observation: name the row, the sha, the node, the rendered element.
- **Say CANNOT DETERMINE rather than infer.** Every number is CARRIED unless it says measured, and a carried figure never overrides a measured one.
- **A verdict with no command is a FAIL.**
- **Two readings that disagree are both data.** Keep both, with the instrument that produced each. Never merge them.
- **Never match outputs by filename glob.** Record the output path in the result row at call time and analyse the rows, never the directory.
- **Change ONE variable per run.** A replication that changes two things at once cannot attribute a difference to either.
- **One run per cell is not evidence**, however large n is inside it. Two independent runs beat one deeper run. Report the per-cell distribution, never only the worst range.
- **A stability claim needs the same input bytes, the same prompt version, the same model, in one window.** A cross-version comparison answers a different question.
- **Judge agreement is not stability.** Two same-model judges can agree with each other and be wrong together.
- **A fixture missing one production input manufactures a defect production does not have.** Before any measurement against a model or scorer, enumerate every placeholder in the live input and prove each is filled from the same source production fills it from.

## BEFORE YOU DESIGN AGAINST A NODE, READ ITS INPUT IDIOM

A fan-out that already ran "once per item" still collapsed eighteen results into one, silently, with HTTP 200 throughout, because the two nodes downstream each read only the first item. The same idiom one level down was correct. Position decides, not the pattern. Read the node body. One read is cheaper than a silent data-loss bug.

## WHEN A HUMAN CONTRADICTS A MEASUREMENT, RE-MEASURE FIRST

The owner is usually right about his own system. Twice a fresh measurement contradicted him and the measurement was wrong, because of a fixture defect. Find the evidence before defending a claim, and before investigating any mechanism, search the existing goal evidence with Python for the mechanism word. A re-derivation is not cheaper than a lookup just because it does not interrupt anyone.

## CLOSE

Close rule: a goal is HELD on any criterion measured FAIL unless a ruling names that criterion and reads it otherwise. The rule keys on criterion verdicts, not on task rows.

## CONCURRENCY

- Do not write under another goal's directory while any leader runs.
- Do not create a new goal directory while a reviewer window is open; the tripwire reads it as out-of-scope change and quarantines the review.
- Re-count the dirty-path baseline before finishing and attribute any change.
- Every record commit outside the step log and STATE.md happens in the goal's own record worktree, `$LOOP_RECORD_WT` (and, when GOAL.md's Authority names the kit, the kit worktree `$LOOP_KIT_WT`), made with `loop-record-commit <GOAL-ID> -m <message> -- <path>`; the step log and STATE.md commit lands through `loop-record-merge <GOAL-ID>` run from the goal's record worktree, and `loop-record-commit <GOAL-ID>` with no path refuses while a goal worktree exists, so the step log and STATE.md are never committed in a goal worktree; a leader edits only its own `### <GOAL-ID>` subsection of STATE.md section 5; `loop-record-merge <GOAL-ID>` is the one step that lands the goal's branch on the record branch.
- A leader runs one goal; peers may run beside it; PEER-NOISE, the tripwire's name for a peer's own change, is not an incident; a goal folder is placed only while no leader runs; every role inherits LOOP_GOAL.
- The goal's Standing rules section is law for the leader and is never a reason to stop.
- Planted control: a planted control inside an open window is written by the leader, as that one Write, inside a window that brackets no other role, and the window's check names it as the planted INCIDENT.
- Session-cut rule (templates/GOAL.md, Standing rule 1) and its resume step: When a goal resumes after a usage-limit cut, for every task whose last DISPATCH in the cut run has no RETURN, DONE, PARTIAL, FAIL or BLOCKED line after it, the leader writes `T<nn> BLOCKED leader record: cut by the usage limit, run log <name>, card <card path>` before it dispatches that task again, and never launches an agent whose DISPATCH line the step-log tool refused (a launch after a refused write is a FAIL under standing rule 1).

## GUARDS

- The guard requires `loop-guard-run <<'LOOP' ... LOOP` with nothing after the terminator. A bare command is denied with that instruction. That denial is not a finding.
- The redactor has list-quality false positives: it masks ordinary words as `[NAME]`. Reword rather than fighting it, and never disable it.
- Read-only roles cannot run inline interpreter code. Write the script into evidence with the Write tool and run that file.
- The writer's limits on git and branches are in `agents/loop-writer.md`. The leader owns every branch and commit.
- **A denied command is never redone another way.** A denied `mkdir`, or a denied command that used a `$VAR` path, redone with the Write tool or with the path spelled out literally is re-routing, and re-routing is forbidden. Quote the denial as a finding and stop that step.
- **Evidence folders are made one way, by every role: the Write tool writing a file at its full path.** No role runs `mkdir`. The leader makes each task's folder by writing that task's card there (`evidence/T<nn>/card.md`, `evidence/T<nn>/writer/card.md`, `evidence/T<nn>/review/card.md`) before it dispatches. The orchestrator makes `evidence/AUDIT/review/` the same way before it dispatches the auditor. Inside its own folder a role makes a subfolder by writing its first file there. A role whose folder is missing returns BLOCKED and names the folder.

## STANDING CARD RULES (C1)

One wording per item. The same words stand in this file, in `templates/TRAPS.md` and in the card templates of `skills/loop-goal/SKILL.md`. `bin/loop_card_lint.py` has one named check for each item a card can get wrong; items (h), (i) and (j) are the leader's behaviour and have none.

- C1(a) Interpreter shapes per role: scouts and reviewers run the venv python spelled with a leading ~/, then -I, then one drive-style absolute script path; writers run the venv python with a leading ~/, then exactly one drive-style absolute script path under the writer's own evidence folder or its goal's scratch folder, no flag, no LOOP_PY, no read of config.env; LOOP_PY and loop-py are named for reviewers only.
- C1(b) writable.txt: every writer card names, on one line headed Writable roots:, the roots its goal's writable.txt lists and nothing outside them.
- C1(c) No git for writers. A writer card carries no git command. Commits are the leader's, after a review PASS on the final bytes.
- C1(d) Every pre-edit and rollback copy goes under $LOOP_HOME/scratch/<GOAL-ID>/, never under evidence/.
- C1(e) A reviewer card names the comparison commands the reviewer runs, on a line headed Comparison commands:, and points only at copies the leader made under $LOOP_HOME/scratch/<GOAL-ID>/; a read-only role is never told to cp, mv or redirect.
- C1(f) No card carries a merge instruction or the name of the owner's denylist file; a card that measures ancestry names the command, never the merge as an action.
- C1(g) A reviewer card never names the writer's evidence subfolder, the Rollback line included.
- C1(h) Tripwire windows before rulings: a ruling, a placement or a goal-folder write happens only with no leader counted for that goal and no window open.
- C1(i) Subagents stay in the same turn: a leader does not end its turn while a subagent runs.
- C1(j) Before dispatching any role, the leader runs loop-card-lint on the card and journals its rc.

## MACHINE TRAPS

The card names the traps file when this machine has one, and the role reads it second, after this file. It holds this machine's schema quirks, tool quirks and known-bad shapes, dated. An empty or missing file means none are recorded yet, not that none exist.

- **The user folder's name is a real name.** Every path in evidence prose, returns, committed text and the report is spelled from `~`, never from a drive letter or the user folder. A raw output that holds a literal home path is named as raw and never quoted.
