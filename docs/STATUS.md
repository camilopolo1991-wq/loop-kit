# Status of the kit

Every figure of the kit is stated here and nowhere else. The sections "The kit", "Row folders and call forms" and "Configuration keys" are the output of `bash bin/loop-inventory`, run at the repository root, byte for byte; tests/rows/K06-C5/run.py compares the two. A figure in those sections is the tool's measure of the tree it is run in and carries no commit line. The two figures after them cannot be read from the tree alone: each is the figure, the command that measured it, and one line reading "measured at commit <sha> on <date>". Commands are run from the repository root. Paths outside the repository are written relative to `$HOME`.

The commit named on those lines is the head of the task branch before the commit that holds this file.

## The kit

Lines in MANIFEST.txt:

```
$ wc -l < MANIFEST.txt
58
```

Files under bin/ that are not modules (`.py`) or caches (`.pyc`):

```
$ find bin -type f ! -name "*.py" ! -name "*.pyc" | wc -l
16
```

Command files, those files less DESCRIPTION.md: loop-card-lint loop-dispatch loop-guard-run loop-inventory loop-journal loop-names-refresh loop-preflight loop-redact-check loop-report loop-scan loop-settings-merge loop-skill-lint loop-ticket loop-ticket-migrate loop-tripwire

Hooks files (caches left out):

```
$ find hooks -type f ! -name "*.pyc" | wc -l
5
```

Hooks files: _guardlib.py pretool-guard.py readonly-guard.py writer-git-guard.py writer-path-guard.py

## Row folders and call forms

Row folders under tests/rows/:

```
$ find tests/rows -mindepth 1 -maxdepth 1 -type d | wc -l
43
```

Every row runner takes no argument and reads its environment. The folders on the second line below also take the tree, the home and the work folder as three arguments after the runner path, in that order, with the same fills.

Row folders: C1 C10 C12 C2 C3 C4 C5 C6 C8 K03-C1 K03-C2 K03-C3 K03-C4 K03-C5 K03-C6 K03-C7 K03-C8 K04-C1 K04-C2 K04-C3 K04-C4 K04-C5 K04-C6 K04-C7 K04-C8 K05-C1 K05-C2 K05-C3 K05-C4 K05-C5 K05-C8 K06-C1 K06-C2 K06-C3 K06-C4 K06-C5 S01-C1 S01-C2 S01-C3 S01-C4 S01-C5 S01-C7 S01-C8
Positional form: C1 C10 C12 C2 C3 C4 C5 C6 C8

## Configuration keys

The keys of the DEFAULTS table in bin/loop_conf.py, each read from `$HOME/.loop/config.env`.

- LOOP_HOME: the loop home, `~/.loop` by default.
- ENGINE_RECORD_DIR: the worktree of the record branch.
- RECORD_BRANCH: the branch inside that worktree which carries state, journal and exports.
- STATE_FILE: the state document, `docs/STATE.md` of the record worktree by default.
- JOURNAL_FILE: the append-only journal, `docs/JOURNAL.md` of the record worktree by default.
- EXPORT_DIR: the exports folder, `exports` of the record worktree by default.
- WRAPPERS: the space-separated wrappers the roles run commands through.
- WRITABLE_TREES: the colon-separated git worktrees the leader may create task branches in.
- MAX_LEADERS: how many leaders run at once, 1 by default.
- SURFACES: the space-separated surface wrappers installed here, empty for none.
- TRIPWIRE_NOISE: the name patterns at the top of the home whose changes the tripwire reports as noise.
- REPORT_SEND_CMD: the command that sends a report; empty leaves the report on disk.
- REPORT_MAX_LINES: the line limit of a report, 80 by default.
- STATE_MAX_LINES: the line limit of the state document, 150 by default.

## Figures measured by hand

Skills, one SKILL.md each:

```
$ find skills -type f -name SKILL.md | wc -l
7
```

measured at commit 14bf1d0dc9a44bc006e141ac09c71441b7cae13f on 2026-10-30

Commits on main (the value at the main this branch grew from):

```
$ git rev-list --count main
43
```

measured at commit 345cfbf7e2198ec12131b2cdced6d7308a22890f on 2026-10-31
