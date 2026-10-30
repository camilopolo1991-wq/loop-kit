# Your first goal

Paths are spelled from the tree root, or from ~ and $LOOP_HOME (the loop home, ~/.loop by default). The steps are in the order you do them.

1. The goal template. Copy templates/GOAL.md, installed at ~/.loop/templates/GOAL.md, and fill every `<...>` field: the outcome, the owner's words, the acceptance criteria (each able to fail, with its control), the authority, the budget, what is out of scope, and the premises. The Budget line carries `wall time <n> min`, which the dispatcher reads.

2. The placement under the loop home. Save the filled file as `$LOOP_HOME/goals/<GOAL-ID>/GOAL.md`. The goal folder lives outside every repository, because its evidence can hold names. The goal includes `$LOOP_HOME/templates/GOAL_PREAMBLE.md` by reference.

3. The dispatch command, with its timeout. From any shell where LOOP_PY names a working interpreter:

        loop-dispatch <GOAL-ID> --timeout <seconds>

   `--timeout` wins when given. Without it the timeout is the GOAL's wall time as n*60+600 seconds, and a GOAL with no wall time line gets 7200. `--dry-run` prints the resolved command and launches nothing. The leader ends with the exit code of the timeout wrapper, which is 124 when the wall time ran out, written beside the run log as `<GOAL>.<ts>.log.rc`.

4. The three stop kinds. The leader plans, then dispatches the scout, the writer and the reviewer, and it stops only at one of these:

   - Stop 1: an owner gate. A merge or push to main, a grant, a spend or anything else that is the owner's. The loop prints the exact command and waits.
   - Stop 2: a reviewer FAIL after two retries. The card lands partial when the reviewer passed at least one of its rows, otherwise it is dropped with the reason in the report.
   - Stop 3: the budget. The writes, calls or wall time the GOAL's Budget line allows are used up.

5. The report path. When the goal closes or holds, the leader writes `$LOOP_HOME/goals/<GOAL-ID>/report.md` and delivers it through loop-report. With no send command set in config.env, the report stays on disk and its path is printed.

6. The audit. After a close or a hold, the orchestrator dispatches loop-auditor, which judges all four other roles from their artefacts and writes under `$LOOP_HOME/goals/<GOAL-ID>/evidence/AUDIT/review/`.
