#!/usr/bin/env python3
"""K04-C1 rows runner: the read-only hook takes --active as a read form of the step-log tool, a leading ~ in a
script path, and a redirect into the goal's work/r-<anything>/ folder.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expected verdicts in rows.txt,
so a tree without the change prints FAIL on the rows the change adds), LOOP_ROWS_HOME (the home every
spawned process gets as HOME and USERPROFILE; LOOP_HOME is that home plus /.loop), LOOP_WORK (a work folder,
created when absent), LOOP_PY (the interpreter that runs the hook; default is the interpreter running this file),
LOOP_NAMES_FILE (passed through untouched).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Every spawned process gets HOME and USERPROFILE at LOOP_ROWS_HOME, LOOP_HOME at LOOP_ROWS_HOME/.loop, LOOP_GOAL at a
fixture goal id, LOOP_ROLE=reviewer and PYTHONDONTWRITEBYTECODE=1. The hook JSON goes in on stdin and
<tree>/hooks/readonly-guard.py runs by path. Prints PASS or FAIL per row with expected and actual; a sha256 stands
in for the hook's reason text, which can hold a home path. Nothing is spawned in the background, nothing is killed,
no timeout is set.
"""
import hashlib
import json
import os
import subprocess
import sys

GOAL = 'FIXG-01'


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def sha(s):
    if isinstance(s, str):
        s = s.encode('utf-8', 'replace')
    return hashlib.sha256(s).hexdigest()[:12]


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', 3)])
    return rows


def make_env(home):
    env = dict(os.environ)
    env['HOME'] = home
    env['USERPROFILE'] = home
    env['LOOP_HOME'] = home + '/.loop'
    env['LOOP_GOAL'] = GOAL
    env['LOOP_ROLE'] = 'reviewer'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env.pop('JOURNAL_FILE', None)
    return env


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
    if len(sys.argv) > 1:
        print('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)')
        return 64
    tree_e = os.environ.get('LOOP_TREE')
    home_e = os.environ.get('LOOP_ROWS_HOME')
    work_e = os.environ.get('LOOP_WORK')
    if not tree_e or not home_e or not work_e:
        print('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)')
        return 64
    tree, home, work = fwd(tree_e), fwd(home_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    hook = tree + '/hooks/readonly-guard.py'
    env = make_env(home)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, expect, cmd in rows:
        actual, why_sha = judge(py, hook, env, cmd.replace('{LH}', home + '/.loop'))
        ok = actual == expect
        passed += ok
        failed += (not ok)
        print('%s %s expected=%s actual=%s reason_sha=%s' % ('PASS' if ok else 'FAIL', rid, expect, actual, why_sha))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
