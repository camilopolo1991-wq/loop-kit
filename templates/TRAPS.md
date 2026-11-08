# Machine traps (dated). Read by every role after GOAL_PREAMBLE.md.
# One line per trap: date | surface | the trap | the safe shape. Append, never rewrite.
# Lines below: date | surface | the standing rule, whose wording is the text from C1( to the end of the line (KIT-11 C1).
2026-11-08 | cards | C1(a) Interpreter shapes per role: scouts and reviewers run the venv python spelled with a leading ~/, then -I, then one drive-style absolute script path; writers run the venv python with a leading ~/, then exactly one drive-style absolute script path under the writer's own evidence folder or its goal's scratch folder, no flag, no LOOP_PY, no read of config.env; LOOP_PY and loop-py are named for reviewers only.
2026-11-08 | cards | C1(b) writable.txt: every writer card names, on one line headed Writable roots:, the roots its goal's writable.txt lists and nothing outside them.
2026-11-08 | cards | C1(c) No git for writers. A writer card carries no git command. Commits are the leader's, after a review PASS on the final bytes.
2026-11-08 | cards | C1(d) Every pre-edit and rollback copy goes under $LOOP_HOME/scratch/<GOAL-ID>/, never under evidence/.
2026-11-08 | cards | C1(e) A reviewer card names the comparison commands the reviewer runs, on a line headed Comparison commands:, and points only at copies the leader made under $LOOP_HOME/scratch/<GOAL-ID>/; a read-only role is never told to cp, mv or redirect.
2026-11-08 | cards | C1(f) No card carries a merge instruction or the name of the owner's denylist file; a card that measures ancestry names the command, never the merge as an action.
2026-11-08 | cards | C1(g) A reviewer card never names the writer's evidence subfolder, the Rollback line included.
2026-11-08 | cards | C1(h) Tripwire windows before rulings: a ruling, a placement or a goal-folder write happens only with no leader counted for that goal and no window open.
2026-11-08 | cards | C1(i) Subagents stay in the same turn: a leader does not end its turn while a subagent runs.
2026-11-08 | cards | C1(j) Before dispatching any role, the leader runs loop-card-lint on the card and journals its rc.
