# loop-kit

A guard kit for running Claude Code agents as a small team that cannot leak a secret, cannot widen its own scope, and leaves a trail another agent can audit. It is the kit behind a working loop: one leader plans a goal, a scout measures, a writer makes one change, a reviewer tries to break it, an auditor judges all of them afterwards.

The LICENSE file names the licence holder. In `bin/loop_ticket.py`, `agents/loop-leader.md` and `hooks/pretool-guard.py` the token `OWNER_HANDLE` stands for the owner's account name on the machine the kit was taken from: set it at install if you use the ticket gate. `MANIFEST.txt` records those files as they are here.

Every number in this file is followed by the command that produced it, shown as a `$` line and its exact output. Commands are run from the repository root unless a path says otherwise. Paths outside the repository are written relative to `$HOME`.

## The problem the kit solves

Agents given a shell will, sooner or later, print a secret, write to a place they were not asked to, retry a denied command another way, or report a result they did not measure. A prompt that says "do not" does not stop that. This kit puts the rules where the agent cannot argue with them: in hooks that run before every tool call, in a wrapper that redacts every line of output, and in cards that give each role one job, a proof it must produce, and a place to put it.

Two habits run through all of it. Every zero needs a control that could have failed. Every claim of a result needs the command that produced it, so the next role can run it again.

## The five roles

Each role is an agent definition under `agents/`.

- **loop-leader.** Plans a goal as a table of tasks, writes a card per task, dispatches the other roles, judges their returns, owns the journal, the state file and the report, and commits on the record branch. It does not edit the product surface; the writer does. It stops only at an owner gate, a guard denial it cannot route around, or a spent budget. A reviewer FAIL after its retries lands partial or drops under the goal's standing rules, and is a stop only when the GOAL has none. It never pushes to main.
- **loop-scout.** Read-only fact finder. Measures and returns facts, each with its command and a control. It may write only into its own evidence folder. It may not change any product surface, run inline interpreter code, or read the writer's folder.
- **loop-writer.** Makes exactly one change a card describes. It records a rollback first, journals it through the wrapper, makes the change inside the worktree the leader checked out, proves it, and returns. It may not run git (the leader owns branches and commits), write outside the worktree and its evidence folder, widen the card's scope, or weaken a proof to fit what it managed. If the proof cannot be produced it returns BLOCKED.
- **loop-reviewer.** Independent and adversarial. It gets the criteria and the artefacts, never the writer's reasoning, and re-measures against the live system. Every check needs a control that could have failed, and any expected-output claim needs a raw byte comparison quoted. It may not read the writer's evidence folder or write anywhere but its own review folder.
- **loop-auditor.** Reviews the reviewers. After a goal closes or holds it judges the leader, scout, writer and reviewer from their artefacts alone, using the checklists in the `loop-audit` skill. It is read-only, and an item it cannot run is CANNOT DETERMINE, never PASS.

The skills under `skills/` carry the formats the roles share (goal and card format, recording, tickets, git rules, the audit checklists, and what may never reach output).

## The guard layer

Four hook scripts live under `hooks/`.

- **`pretool-guard.py`.** The PreToolUse hook for every session and subagent. It denies the command shapes that have leaked secrets before (environment dumps, reading a `.env`, credentials on a command line), the acts that belong to the owner (pushing main, force-push, history rewrite, merges onto main, role grants and drops, stopping containers), and the Windows shell launchers that would route around its rules. It requires every shell command to be one `loop-guard-run` heredoc so the output is redacted. It checks reviewer dispatches for leaked writer output, and task-card dispatches for missing fields. Machine-specific denies are loaded at runtime from `guard-deny.txt` in the loop home, so the script carries none.
- **`readonly-guard.py`.** Registered in the frontmatter of the scout, reviewer and auditor. It denies by class: inline interpreters, decoders, file-changing utilities, git beyond a read allowlist, and any redirect or write that is not inside the current goal's evidence folder for that role. The role comes from the `LOOP_ROLE` variable in the hook command.
- **`writer-git-guard.py`.** Registered on the writer's shell. The writer never has a reason to say git, so any token that is git, any inline interpreter, any decoder, and any command word it cannot resolve is denied. It is a net, not a sandbox: it stops the command shapes its rows under `tests/rows/C1/` test, not every shell construct that can start a program.
- **`writer-path-guard.py`.** Registered on the writer's Write and Edit tools. The writer may write only under its own evidence folder for the current goal and under the directories the leader lists in that goal's `writable.txt`. It may never write under `.git`, `.claude`, a journal, a state file, tickets, or another goal.

All four fail closed: an error inside a hook produces a deny, not a pass. The agent files register the role hooks with `onFailure: block` and a timeout.

## The instruments

The wrappers and tools under `bin/` are installed into the loop home and put on `PATH`.

That count covers the whole kit: agents, hooks, skills, templates and these tools.

- **loop-guard-run.** Runs one shell command with stdin closed and passes its merged output through the redactor line by line. Every shell command in the loop goes through it.
- **loop-scan.** Scans files, a staged diff or a commit range for secrets and names. It first runs a built-in control that must fire, and it prints counts and file:line locations, never the matched text.
- **loop-journal.** Appends one line with a measured UTC timestamp to the append-only journal. `--read` and `--check` are the read forms; `--check` fails when a writer task has a PASS with no ROLLBACK line before it.
- **loop-card-lint.** Lints task and review cards, plans and reports by file name, so a card that routes a role to the journal or a plan with prose tasks is rejected before dispatch. Given `--log PATH`, the plan lint also checks each PASS row of a plan against that step log.
- **loop-preflight.** Prints the measured start-of-session facts: record repository state, leader count, state file size, redactor control.
- **loop-tripwire.** Opens a window around read-only batches and reports any change a guard missed. `start`, `check` and `selftest`.
- **loop-report.** Delivers a goal's report through the send command in `config.env`; with none set the report stays on disk and its path is printed.
- **loop-ticket and loop-ticket-migrate.** The one writer of the ticket files, and a one-shot format converter.
- **loop-settings-merge.** Merges kit settings into a Claude Code settings file without copying a secret, and keeps a fingerprinted backup.
- **loop-redact-check.** The live control for the redactor.
- **loop-names-refresh.** Retired. The name list is written by the owner by hand.

The redactor (`loop_redact.py`) masks secrets and every entry of `names.txt` in output. That list is owner-held and is not in this repository.

## Starting a leader: bin/loop-dispatch

`bin/loop-dispatch` is the one way to start a leader. It is a bash stub that runs `bin/loop_dispatch.py` with the interpreter in `LOOP_PY`. Call it with a goal id: `loop-dispatch <GOAL-ID> [--timeout SEC] [--dry-run] [--no-poll]`. Every path comes from `LOOP_HOME` (the environment, otherwise `.loop` in your home), and the claude binary comes from `LOOP_CLAUDE_BIN`, then `CLAUDE_BIN` in `config.env`, then `PATH`. A pin that is not an existing file is refused. It checks the goal file, the leader count against `MAX_LEADERS` and the free disk before it launches, and `--dry-run` prints the resolved command and launches nothing.

- **The timeout rule.** `--timeout` wins when given. Without it the timeout is the wall time in the GOAL's `Budget:` line (`wall time <n> min`) as `n*60+600` seconds, so the leader gets ten minutes beyond what the goal budgeted. A GOAL with no such line gets 7200 seconds, whatever `LEADER_TIMEOUT` holds. The ceiling is enforced by a GNU `timeout` that the dispatcher proves is GNU before it uses it; `TIMEOUT_BIN` in `config.env` names it when `PATH` does not.
- **Absent gates proceed, and say so.** The goal lint (a tool under `$LOOP_HOME/scripts`) and the recall receipt (a file at `$LOOP_HOME/cache/recall-receipts.json`) are optional, because this kit ships neither. When one is absent the dispatcher does not refuse: it prints a `note` line that names the gate as OFF and why, and prints no `ok` line for it. When one is present it is enforced: a lint that fails, or a receipt that is missing, stale or not rc 0 for the goal, refuses with exit 2.
- **The .rc file.** The leader runs under a small supervisor. When the leader ends, the supervisor writes its exit code to a file beside the run log, named like the run log with `.rc` added: `$LOOP_HOME/dispatch/<GOAL>.<ts>.log` gets `<GOAL>.<ts>.log.rc`. The code is that of the `timeout` wrapper, so it is the leader's own, or 124 when the wall time ran out. `--no-poll` returns at once and the file still appears when the leader ends. Without `--no-poll` the dispatcher watches the leader for 60 seconds and exits 5 if it ends in that time.

## Install

You need bash, and a Python 3 interpreter that runs. Pass its full path. Only `loop-preflight` has a fallback: when `LOOP_PY` is unset or does not run, it tries `python3` and then `python` from `PATH`. Every other tool in `bin/` stops with an error and does not fall back.

```
bash install.sh /full/path/to/python
```

Environment form: `LOOP_PY=/full/path/to/python LOOP_WITH_TESTS=1 bash install.sh` with no positional argument installs the same way, because a shell hook that allows an interpreter and one script path, nothing more, cannot pass a flag.

`install.sh` checks that the interpreter runs before it writes anything. If it does not, it exits non-zero and writes no `config.env`. If any destination file or a `config.env` already exists, it exits 4 and overwrites nothing. Otherwise it copies the kit into `$HOME` at this layout, makes three fills in the copied files (the `@LOOP_PYTHON@` token with the interpreter; `$HOME` on the hook command lines of the agent files with the literal home the kit is installed into; the `OWNER_HANDLE` token with the value of `LOOP_OWNER` when it is set, otherwise left for you to set by hand, which the install says in one line), and writes `config.env` last, through a temporary file renamed into place as the final step. On Windows, a test install into another home needs `USERPROFILE` set to that home as well as `HOME`, because the kit's Python code resolves `~` with `os.path.expanduser`, which reads `USERPROFILE` there.

Upgrade form: `LOOP_PY=/full/path/to/python LOOP_UPGRADE=1 LOOP_BACKUP_DIR=/path/to/an/empty/folder bash install.sh`, with no positional argument, brings a home that is already installed up to this checkout. It copies every file it is about to replace into `LOOP_BACKUP_DIR` under the same relative path, replaces the kit files under `.loop/bin`, `.loop/templates`, `.claude/skills` and `.claude/agents` with this checkout's text and the same three fills (a filled owner handle in an installed agent file survives; `LOOP_OWNER_HANDLE`, when set, wins), adds any file the home lacks, and prints one line per file with its sha256 before and after, then one line with four counts: replaced, added, unchanged, hooks skipped. `config.env`, the names list and the hooks directory are left alone; set `LOOP_UPGRADE_HOOKS=1` as well to replace the hooks files. A second run replaces 0 and adds 0. A `LOOP_BACKUP_DIR` that is unset or not empty is refused (exit 2) before any write; a home with no `config.env` exits 5 (nothing to upgrade). Without `LOOP_UPGRADE`, an installed home still exits 4.

| Repository | Installed at |
|---|---|
| `agents/` | `$HOME/.claude/agents/` |
| `hooks/` | `$HOME/.claude/hooks/` |
| `skills/` | `$HOME/.claude/skills/` |
| `bin/` | `$HOME/.loop/bin/` |
| `templates/` | `$HOME/.loop/templates/` |

It also makes `$HOME/.loop/goals`, `scratch` and `record/docs`, and copies the state template there. It does not run git, does not edit `settings.json` or `CLAUDE.md`, and does not register any hook. Do these yourself:

1. Put `$HOME/.loop/bin` on `PATH`.
2. Make `$HOME/.loop/record` a git repository on branch `record` (the leader keeps the state file and journal there).
3. Register the session-wide hook in your Claude Code `settings.json`, with the same interpreter path you gave the installer:

```
{"hooks": {"PreToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "/full/path/to/python $HOME/.claude/hooks/pretool-guard.py"}]}]}}
```

4. Write `$HOME/.loop/names.txt` by hand (one name per line). Without it `loop-scan` prints `name_control=n/a`, which is a scan without names.
5. Run `loop-preflight`, and `loop-card-lint examples/example-card.md`.

`tests/docker` is a fake `docker` for `loop-tripwire selftest`: it prints fixed workflow rows, changes a version id on request and can be told to fail, so the selftest never touches a real container. `install.sh` copies `tests/` to `$HOME/.loop/tests/`, where the selftest looks for it, only when you pass `--with-tests`; without the flag no tests directory is made.

`TRIPWIRE_NOISE` in `config.env` is a space-separated list of name patterns at the top of the home whose differences `loop-tripwire check` lists under NOISE and leaves out of its exit code; the default is `ntuser.dat* NTUSER.DAT*`.

A pass needs a `loop-sql` on PATH, a host that runs extensionless scripts by name, and symlink privilege.

The files below are left out of this repository on purpose and are owner-held: they are compiled caches that embed the path of the source they were built from, and the interpreter rebuilds them on first run.

- `bin/__pycache__/loop_conf.cpython-314.pyc`
- `bin/__pycache__/loop_procs.cpython-314.pyc`
- `bin/__pycache__/loop_redact.cpython-314.pyc`
- `bin/__pycache__/loop_report.cpython-314.pyc`
- `bin/__pycache__/loop_scan.cpython-314.pyc`
- `bin/__pycache__/tripwire_selftest.cpython-314.pyc`
- `hooks/__pycache__/readonly-guard.cpython-314.pyc`

`MANIFEST.txt` lists every other file with its source and destination sha256, and quotes each line the scrub rewrote.

Also owner-held and not in the kit: `config.env` values, `names.txt`, `guard-deny.txt`, and the `CLAUDE.md` boot sector.
