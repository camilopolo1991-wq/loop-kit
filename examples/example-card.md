TASK EXAMPLE-01/T01: add a one-line greeting file to the example repository
Preamble: $LOOP_HOME/templates/GOAL_PREAMBLE.md (read it first; the card never pastes it)
Load skill: none (filesystem via loop-guard-run)
Surface: filesystem via loop-guard-run. Repository $HOME/example-repo, task branch already checked out by the leader.
Do: one change. Create `hello.txt` at the repository root holding the single line `hello`.
Done when: `hello.txt` exists at the repository root and `cmp` against a file holding exactly `hello` and a newline exits 0.
Proof: the `cmp` command quoted with its exit code, and the rollback path (the inverse is deleting `hello.txt`).
Must not: run git; write outside the repository and `evidence/T01/writer/`; touch any other file.
Evidence to: $LOOP_HOME/goals/EXAMPLE-01/evidence/T01/writer/
Card file: this card, written by the leader to evidence/T01/writer/card.md
Premises: `hello.txt` does not exist yet: CARRIED, check it.
Return: the role's 30-line format, with the rollback recorded first.
