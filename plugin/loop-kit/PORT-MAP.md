# PORT-MAP: loop-kit plugin (KIT12B-01)

Every row of the T01 inventory (67 rows: 54 at main, 13 at 6206b7f) with its class and its home.
Classes: port = bytes carried into this plugin; wrap = called in place from `$LOOP_HOME/bin`, never copied; exclude = not shipped here.
The 6206b7f hook copies are superseded by the main ports (6206b7f carries a role alias that lands with the crew agents). `agents/` is absent in this build.
Plugin-own files (no kit source): `.claude-plugin/plugin.json`, `hooks/hooks.json`, `hooks/run-guard.sh`, `selftest/run_selftest.py`, `PORT-MAP.md`, `INSTALL.md`.

| source | path | class | home | note |
|---|---|---|---|---|
| main | agents/loop-auditor.md | exclude | not shipped | agents belong to REPOS-01; a follow-up card adds plugin/loop-kit/agents/ after its merge |
| main | agents/loop-leader.md | exclude | not shipped | agents belong to REPOS-01; a follow-up card adds plugin/loop-kit/agents/ after its merge |
| main | agents/loop-reviewer.md | exclude | not shipped | agents belong to REPOS-01; a follow-up card adds plugin/loop-kit/agents/ after its merge |
| main | agents/loop-scout.md | exclude | not shipped | agents belong to REPOS-01; a follow-up card adds plugin/loop-kit/agents/ after its merge |
| main | agents/loop-writer.md | exclude | not shipped | agents belong to REPOS-01; a follow-up card adds plugin/loop-kit/agents/ after its merge |
| main | bin/loop-card-lint | wrap | $LOOP_HOME/bin/loop-card-lint | called in place, not copied |
| main | bin/loop-dispatch | wrap | $LOOP_HOME/bin/loop-dispatch | called in place, not copied |
| main | bin/loop-guard-run | wrap | $LOOP_HOME/bin/loop-guard-run | called in place, not copied |
| main | bin/loop-inventory | wrap | $LOOP_HOME/bin/loop-inventory | called in place, not copied |
| main | bin/loop-journal | wrap | $LOOP_HOME/bin/loop-journal | called in place, not copied |
| main | bin/loop-preflight | wrap | $LOOP_HOME/bin/loop-preflight | called in place, not copied |
| main | bin/loop-py | wrap | $LOOP_HOME/bin/loop-py | called in place, not copied |
| main | bin/loop-record-commit | wrap | $LOOP_HOME/bin/loop-record-commit | called in place, not copied |
| main | bin/loop-record-merge | wrap | $LOOP_HOME/bin/loop-record-merge | called in place, not copied |
| main | bin/loop-redact-check | wrap | $LOOP_HOME/bin/loop-redact-check | redactor/scanner/name control, KIT12A-01 lane, called in place, not copied |
| main | bin/loop-report | wrap | $LOOP_HOME/bin/loop-report | called in place, not copied |
| main | bin/loop-scan | wrap | $LOOP_HOME/bin/loop-scan | redactor/scanner/name control, KIT12A-01 lane, called in place, not copied |
| main | bin/loop-settings-merge | wrap | $LOOP_HOME/bin/loop-settings-merge | called in place, not copied |
| main | bin/loop-skill-lint | wrap | $LOOP_HOME/bin/loop-skill-lint | called in place, not copied |
| main | bin/loop-ticket | wrap | $LOOP_HOME/bin/loop-ticket | called in place, not copied |
| main | bin/loop-tripwire | wrap | $LOOP_HOME/bin/loop-tripwire | called in place, not copied |
| main | bin/loop-worktree | wrap | $LOOP_HOME/bin/loop-worktree | called in place, not copied |
| main | bin/loop_card_lint.py | wrap | $LOOP_HOME/bin/loop_card_lint.py | called in place, not copied |
| main | bin/loop_conf.py | wrap | $LOOP_HOME/bin/loop_conf.py | called in place, not copied |
| main | bin/loop_dispatch.py | wrap | $LOOP_HOME/bin/loop_dispatch.py | called in place, not copied |
| main | bin/loop_guard_run.py | wrap | $LOOP_HOME/bin/loop_guard_run.py | called in place, not copied |
| main | bin/loop_inventory.py | wrap | $LOOP_HOME/bin/loop_inventory.py | called in place, not copied |
| main | bin/loop_journal.py | wrap | $LOOP_HOME/bin/loop_journal.py | called in place, not copied |
| main | bin/loop_preflight.py | wrap | $LOOP_HOME/bin/loop_preflight.py | called in place, not copied |
| main | bin/loop_procs.py | wrap | $LOOP_HOME/bin/loop_procs.py | called in place, not copied |
| main | bin/loop_record_commit.py | wrap | $LOOP_HOME/bin/loop_record_commit.py | called in place, not copied |
| main | bin/loop_record_merge.py | wrap | $LOOP_HOME/bin/loop_record_merge.py | called in place, not copied |
| main | bin/loop_redact.py | wrap | $LOOP_HOME/bin/loop_redact.py | redactor/scanner/name control, KIT12A-01 lane, called in place, not copied |
| main | bin/loop_redact_check.py | wrap | $LOOP_HOME/bin/loop_redact_check.py | redactor/scanner/name control, KIT12A-01 lane, called in place, not copied |
| main | bin/loop_report.py | wrap | $LOOP_HOME/bin/loop_report.py | called in place, not copied |
| main | bin/loop_scan.py | wrap | $LOOP_HOME/bin/loop_scan.py | redactor/scanner/name control, KIT12A-01 lane, called in place, not copied |
| main | bin/loop_settings_merge.py | wrap | $LOOP_HOME/bin/loop_settings_merge.py | called in place, not copied |
| main | bin/loop_skill_lint.py | wrap | $LOOP_HOME/bin/loop_skill_lint.py | called in place, not copied |
| main | bin/loop_steplog.py | wrap | $LOOP_HOME/bin/loop_steplog.py | called in place, not copied |
| main | bin/loop_ticket.py | wrap | $LOOP_HOME/bin/loop_ticket.py | called in place, not copied |
| main | bin/loop_tripwire.py | wrap | $LOOP_HOME/bin/loop_tripwire.py | called in place, not copied |
| main | bin/loop_worktree.py | wrap | $LOOP_HOME/bin/loop_worktree.py | called in place, not copied |
| main | hooks/_guardlib.py | port | plugin/loop-kit/hooks/_guardlib.py | guard bytes carried |
| main | hooks/pretool-guard.py | port | plugin/loop-kit/hooks/pretool-guard.py | guard bytes carried |
| main | hooks/readonly-guard.py | port | plugin/loop-kit/hooks/readonly-guard.py | guard bytes carried |
| main | hooks/writer-git-guard.py | port | plugin/loop-kit/hooks/writer-git-guard.py | guard bytes carried |
| main | hooks/writer-path-guard.py | port | plugin/loop-kit/hooks/writer-path-guard.py | guard bytes carried |
| main | skills/loop-audit/SKILL.md | port | plugin/loop-kit/skills/loop-audit/SKILL.md | skill bytes carried |
| main | skills/loop-git/SKILL.md | port | plugin/loop-kit/skills/loop-git/SKILL.md | skill bytes carried |
| main | skills/loop-goal/SKILL.md | port | plugin/loop-kit/skills/loop-goal/SKILL.md | skill bytes carried |
| main | skills/loop-grill/SKILL.md | port | plugin/loop-kit/skills/loop-grill/SKILL.md | skill bytes carried |
| main | skills/loop-pii/SKILL.md | port | plugin/loop-kit/skills/loop-pii/SKILL.md | skill bytes carried |
| main | skills/loop-record/SKILL.md | port | plugin/loop-kit/skills/loop-record/SKILL.md | skill bytes carried |
| main | skills/loop-ticket/SKILL.md | port | plugin/loop-kit/skills/loop-ticket/SKILL.md | skill bytes carried |
| 6206b7f | plugin/loop-kit/.claude-plugin/plugin.json | exclude | not shipped | plugin-own file, rewritten in this plugin |
| 6206b7f | plugin/loop-kit/PORT-MAP.md | exclude | not shipped | replaced by this file |
| 6206b7f | plugin/loop-kit/agents/argus.md | exclude | not shipped | agents belong to REPOS-01; a follow-up card adds plugin/loop-kit/agents/ after its merge |
| 6206b7f | plugin/loop-kit/agents/daedalus.md | exclude | not shipped | agents belong to REPOS-01; a follow-up card adds plugin/loop-kit/agents/ after its merge |
| 6206b7f | plugin/loop-kit/agents/minos.md | exclude | not shipped | agents belong to REPOS-01; a follow-up card adds plugin/loop-kit/agents/ after its merge |
| 6206b7f | plugin/loop-kit/agents/nemesis.md | exclude | not shipped | agents belong to REPOS-01; a follow-up card adds plugin/loop-kit/agents/ after its merge |
| 6206b7f | plugin/loop-kit/agents/talos.md | exclude | not shipped | agents belong to REPOS-01; a follow-up card adds plugin/loop-kit/agents/ after its merge |
| 6206b7f | plugin/loop-kit/hooks/_guardlib.py | exclude | plugin/loop-kit/hooks/_guardlib.py (from main, not this copy) | superseded by the main port of the same name (bytes equal main) |
| 6206b7f | plugin/loop-kit/hooks/hooks.json | exclude | not shipped | plugin-own file, rewritten in this plugin |
| 6206b7f | plugin/loop-kit/hooks/pretool-guard.py | exclude | plugin/loop-kit/hooks/pretool-guard.py (from main, not this copy) | superseded by the main port of the same name (differs from main by a role alias) |
| 6206b7f | plugin/loop-kit/hooks/readonly-guard.py | exclude | plugin/loop-kit/hooks/readonly-guard.py (from main, not this copy) | superseded by the main port of the same name (differs from main by a role alias) |
| 6206b7f | plugin/loop-kit/hooks/writer-git-guard.py | exclude | plugin/loop-kit/hooks/writer-git-guard.py (from main, not this copy) | superseded by the main port of the same name (bytes equal main) |
| 6206b7f | plugin/loop-kit/hooks/writer-path-guard.py | exclude | plugin/loop-kit/hooks/writer-path-guard.py (from main, not this copy) | superseded by the main port of the same name (bytes equal main) |

Counts: 67 rows, port 12, wrap 37, exclude 18 (the 6206b7f hook rows are counted as exclude here because the main port stands in).

Windows-only, not ported: the Hermes venv interpreter path and the `loop-py` Windows spelling (LOOP_PYTHON or `$LOOP_HOME/venv` take their place); the SessionStart preflight registration in the owner's Windows settings.
The three per-role guards ship in `hooks/` but are not registered by `hooks/hooks.json`; the role agents register them with `bash "${CLAUDE_PLUGIN_ROOT}/hooks/run-guard.sh" <guard>` once REPOS-01's agents land.
