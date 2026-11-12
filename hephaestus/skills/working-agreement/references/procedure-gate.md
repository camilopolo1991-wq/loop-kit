# The procedure gate: never hand the owner a command from memory

Read this when: before sending the owner any command, path, or install procedure.

Split out of `SKILL.md` on 2026-10-09 for progressive disclosure
(Anthropic: SKILL.md body under 500 lines; detail lives in `references/`,
never duplicated in both).

## Never hand him a command written from memory. Gate it: `verify-procedure.py`

```
python3 scripts/verify-procedure.py <file>   # or - for stdin
python3 scripts/verify-procedure.py --selftest
```
Exit 0 = every path, binary and git object in it resolves. Exit 1 = DO NOT send it.
Exit 2 = nothing checkable, which is NOT a pass.

Earned 2026-10-09, three invented details in ONE task, all three reaching him as a
command to run:

- `$LOOP_HOME/goals/REDACT-01/artifacts/loop_redact.py` - no `artifacts/` dir exists.
  His shell returned `install: cannot stat`. The real artifact is a git blob:
  `git -C <ops repo> show <commit>:<kit path>/bin/<f>`.
- **ONE file named where the goal installs THREE** (`loop_redact.py`, `loop-scan`,
  `loop-names-refresh`). The worst of the three: it would have exited 0 and left a
  partial install that looks complete.
- `<loop home>/bin/loop-redact` - never existed. The entry point is `loop_redact.py`
  run as a stdin filter. His verification line would have said "No such file" and he
  would have reasonably concluded the install failed.

Proven on the real artifacts, not a synthetic case: rc=1 on the text actually sent,
naming both bad paths; rc=0 on the corrected procedure from the report. `--selftest`
plants each of the three defects and requires the gate to flip, 4/4.

The gate also catches the **empty-blob trap**: a wrong path in `git show REF:path`
prints nothing and exits 0, and hashing nothing yields `e3b0c442...`, which is sha256
of the empty string. Seen twice in one night. The gate fails a 0-byte blob explicitly.

**Root cause, and the rule: the goal's own `report.md` already held the correct
procedure.** All three defects came from composing a command from memory rather than
reading the authoritative source first. Before handing him any procedure, read it out
of the artifact that defines it - the goal report, `--help`, the branch - then gate it.
A remembered path is a guess wearing the costume of a fact.

Same failure shape as the invented `--rollback-first` flag on `loop-n8n put` earlier
that night, caught only by reading `put --help`. Verify a tool's flags from `--help`
before prescribing them; on 2026-10-09 `loop-n8n put` needed `--file --expect --goal
--reason`, all four mandatory (read `put --help` again before quoting it today).
