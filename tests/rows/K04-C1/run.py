#!/usr/bin/env python3
"""K04-C1 rows runner: the read-only hook takes --active as a read form of the step-log tool, a leading ~ in a
script path, and a redirect into the goal's work/r-<anything>/ folder.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expected verdicts in rows.txt,
so a tree without the change prints FAIL on the rows the change adds), LOOP_ROWS_HOME (the home every
spawned process gets as HOME and USERPROFILE; LOOP_HOME is that home plus /.loop), LOOP_WORK (a work folder,
created when absent), LOOP_PY (the interpreter that runs the hook; default is the interpreter running this file),
LOOP_NAMES_FILE (passed through untouched).
Every spawned process gets HOME and USERPROFILE at LOOP_ROWS_HOME, LOOP_HOME at LOOP_ROWS_HOME/.loop, LOOP_GOAL at a
fixture goal id, LOOP_ROLE=reviewer and PYTHONDONTWRITEBYTECODE=1. The hook JSON goes in on stdin and
<tree>/hooks/readonly-guard.py runs by path. Prints PASS or FAIL per row with expected and actual; a sha256 stands
in for the hook's reason text, which can hold a home path. Nothing is spawned in the background, nothing is killed,
no timeout is set.
"""
import json
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import Score, env_dirs, fwd, load_rows, make_env, sha

GOAL = 'FIXG-01'


def judge(py, hook, env, command):
    payload = json.dumps({'tool_name': 'Bash', 'tool_input': {'command': command}})
    cp = subprocess.run([py, hook], input=payload, capture_output=True, text=True, env=env)
    out = cp.stdout.strip()
    if cp.returncode != 0:
        return 'error', sha(cp.stdout + cp.stderr)
    if not out:
        return 'allowed', sha('')
    try:
        d = json.loads(out)
        dec = d['hookSpecificOutput']['permissionDecision']
        why = d['hookSpecificOutput'].get('permissionDecisionReason', '')
    except (ValueError, KeyError, TypeError):
        return 'error', sha(out)
    return ('denied' if dec == 'deny' else 'error'), sha(why)


def main():
    tree, home, work = env_dirs('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)')
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    hook = tree + '/hooks/readonly-guard.py'
    env = make_env(home, {'LOOP_GOAL': GOAL, 'LOOP_ROLE': 'reviewer'}, ('JOURNAL_FILE',))
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    score = Score()
    for rid, expect, cmd in rows:
        actual, why_sha = judge(py, hook, env, cmd.replace('{LH}', home + '/.loop'))
        ok = actual == expect
        score.row(ok, rid, 'expected=%s actual=%s reason_sha=%s' % (expect, actual, why_sha))
    return score.done(rows)


if __name__ == '__main__':
    sys.exit(main())
