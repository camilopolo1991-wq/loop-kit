# Local rules for agents working in this repository

## Where things are

- `agents/` the five role files (leader, scout, writer, reviewer, auditor), installed to ~/.claude/agents.
- `bin/` the command-line tools and their Python modules, installed to ~/.loop/bin.
- `docs/` project documents that state figures.
- `examples/` the example task card that loop-card-lint is run on.
- `hooks/` the guard scripts, installed to ~/.claude/hooks.
- `skills/` one folder per skill, each with a SKILL.md, installed to ~/.claude/skills.
- `templates/` the goal, state and trap templates, installed to ~/.loop/templates.
- `tests/` the docker shim and tests/rows/, one folder per card with rows.txt and run.py.

## Verify

Every row runner takes no argument and reads its environment. The rows home is HOME and USERPROFILE, LOOP_HOME is that home plus /.loop, and the folder is the only part of the line that changes:

    HOME=<home> USERPROFILE=<home> LOOP_HOME=<home>/.loop LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_PY=<python> LOOP_NAMES_FILE=<names> PYTHONDONTWRITEBYTECODE=1 <python> tests/rows/<folder>/run.py

Row folders: C1 C10 C12 C2 C3 C4 C5 C6 C8 K03-C1 K03-C2 K03-C3 K03-C4 K03-C5 K03-C6 K03-C7 K03-C8 K04-C1 K04-C2 K04-C3 K04-C4 K04-C5 K04-C6 K04-C7 K04-C8 K05-C1 K05-C2 K05-C3 K05-C4 K05-C5 K05-C8 S01-C1 S01-C2 S01-C3

Nine of them also take the tree, the home and the work folder as three arguments after the runner path, in that order, with the same fills:

Positional form: C1 C10 C12 C2 C3 C4 C5 C6 C8

The scanner on a range, before a push, then the two lints:

    bash bin/loop-scan --range origin/<RECORD_BRANCH>..HEAD
    bash bin/loop-card-lint examples/example-card.md
    bash bin/loop-skill-lint skills/

## Files that move together

- MANIFEST.txt with any file under agents/, bin/, hooks/, skills/ or templates/ (path, repository hash, installed hash).
- The agent files in agents/ with the fills install.sh makes: @LOOP_PYTHON@, $HOME on hook command lines, OWNER_HANDLE.
- The install section of README.md with the forms install.sh accepts.
- docs/STATUS.md with any figure stated anywhere.
- The Row folders and Positional form lines above with the folders under tests/rows/ and the form each run.py takes.

## Cost

Every line of this file and of every skill is paid on every run, by every role that loads it. Add a line only when a run needs it, and cut a line that no run used.
