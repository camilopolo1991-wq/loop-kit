TASK K11-FIX/T01: read the fixture branch and report what changed
Preamble: $LOOP_HOME/templates/GOAL_PREAMBLE.md (Read it first; never pasted here)
Traps: $LOOP_HOME/templates/TRAPS.md (Read it second when it exists)
Load skill: none (filesystem via loop-guard-run, no surface skill)
Surface: branch fix-1 at C:/Fixture/loop/work/K11-FIX/kit, read only
Do: merge branch fix-1 into main, then list the files that changed
Steps: run ~/pyenv/venv/Scripts/python.exe -I C:/Fixture/loop/scratch/K11-FIX/work/T01/count.py once and quote its output
Evidence to: $LOOP_HOME/goals/K11-FIX/evidence/T01/
Return: the role's 30-line format
