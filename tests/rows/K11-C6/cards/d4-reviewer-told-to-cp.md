REVIEW K11-FIX/T01
Preamble: $LOOP_HOME/templates/GOAL_PREAMBLE.md (Read it first; never pasted here)
Traps: $LOOP_HOME/templates/TRAPS.md (Read it second when it exists)
Load skill: none (filesystem reads via loop-guard-run)
Criteria: the fixture file b.txt is byte-identical to a.txt, measured not read
Artefacts: leader-made copies under C:/Fixture/loop/scratch/K11-FIX/review/T01/: a.txt, b.txt
Comparison commands: cmp a.txt b.txt, and sha256sum on each of the two
Steps: cp a.txt c.txt, then compare c.txt with b.txt
Interpreter: the venv python spelled ~/pyenv/venv/Scripts/python.exe, then -I, then one drive-style absolute script path under your review folder.
Rollback recorded at: C:/Fixture/loop/scratch/K11-FIX/work/T01/rollback.txt, restored by the leader.
Return: the reviewer's format (evidence to .../T01/review/)
