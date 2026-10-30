# loop-kit

A guard kit for running Claude Code agents as a small team that cannot leak a secret, cannot widen its own scope, and leaves a trail another agent can audit.

```
LOOP_PY=/full/path/to/python LOOP_WITH_TESTS=1 bash install.sh
LOOP_PY=/full/path/to/python LOOP_UPGRADE=1 LOOP_BACKUP_DIR=<absent or empty folder> bash install.sh
```

The first line installs into a home that holds nothing yet, the second brings an installed home up to this checkout. Both are explained in `docs/guides/install.md`.

| Without the kit | With the kit | Command |
|---|---|---|
| A tool prints a secret and it stays in the transcript | Every line of output passes the redactor, which masks secrets and names | `loop-guard-run` |
| An agent retries a denied command another way | The pre-tool hook denies the shape and fails closed | `pretool-guard.py` |
| A change has no way back | The journal check fails a PASS that has no ROLLBACK line before it | `loop-journal --check` |
| A plan row says PASS and no log shows it | Given `--log PATH`, the plan lint also checks each PASS row of a plan against that step log | `loop-card-lint --log PATH plan.md` |
| A reviewer FAIL stops the whole run | A reviewer FAIL after its retries lands partial or drops under the goal's standing rules, and is a stop only when the GOAL has none | `loop-card-lint plan.md` |
| A leader dies and nothing says why | The dispatcher writes the leader's exit code beside the run log as `<GOAL>.<ts>.log.rc` | `loop-dispatch <GOAL-ID> --dry-run` |

Start here: `AGENTS.md`, `docs/guides/install.md` and `docs/STATUS.md`.

Kit files: 67, counted by `wc -l < MANIFEST.txt`.

| Repository | Installed at |
|---|---|
| `agents/` | `~/.claude/agents/` |
| `hooks/` | `~/.claude/hooks/` |
| `skills/` | `~/.claude/skills/` |
| `bin/` | `$LOOP_HOME/bin/` |
| `templates/` | `$LOOP_HOME/templates/` |
| `tests/` | `$LOOP_HOME/tests/`, only in an install with tests |
