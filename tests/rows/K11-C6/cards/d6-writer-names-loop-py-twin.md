TASK K11-FIX/T01: change one fixture file
Preamble: $LOOP_HOME/templates/GOAL_PREAMBLE.md (Read it first; never pasted here)
Traps: $LOOP_HOME/templates/TRAPS.md (Read it second when it exists)
Load skill: none (filesystem via loop-guard-run, no surface skill)
Surface: branch fix-1 at C:/Fixture/loop/work/K11-FIX/kit: bin/tool.py
Writable roots: C:/Fixture/loop/work/K11-FIX/kit, C:/Fixture/loop/scratch/K11-FIX/work; nothing outside them, plus your evidence folder C:/Fixture/loop/goals/K11-FIX/evidence/T01/writer/.
Do: one change. Make bin/tool.py print its version, then run ~/pyenv/venv/Scripts/python.exe C:/Fixture/loop/goals/K11-FIX/evidence/T01/writer/check.py
Proof: the check output saved under evidence/T01/writer/
Must not: run any version-control command; write outside the writable roots and your evidence folder; edit any other file; print a real name or a secret.
Rollback: a pre-edit copy of bin/tool.py under C:/Fixture/loop/scratch/K11-FIX/work/T01/ if it is edited
Evidence to: $LOOP_HOME/goals/K11-FIX/evidence/T01/writer/
Return: the role's 30-line format
