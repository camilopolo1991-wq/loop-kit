#!/usr/bin/env python3
"""K03-C1 rows runner: install.sh environment form, positional form, README phrase.

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (used only for the set-or-usage check; no row targets it,
because each install row makes a fresh home under LOOP_WORK), LOOP_WORK (a work folder, created when absent),
LOOP_PY (the interpreter for the install rows), LOOP_NAMES_FILE (passed through to spawned processes).
Every spawned process gets HOME and USERPROFILE at the home it targets and LOOP_HOME at that home's .loop,
and PYTHONDONTWRITEBYTECODE=1. The install rows each target a fresh home under LOOP_WORK.
Prints PASS or FAIL per row with expected and actual; a sha256 stands in for any text that could hold a home path.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import os
import subprocess
import sys
import time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import env_dirs, fresh_home, fwd, load_rows, make_env, run_phrase, sha, tally


def run_install(tree, work, py, expect, arg, rowid, use_env):
    home = fresh_home(work, rowid)
    env = make_env(home, drop=('LOOP_GOAL', 'JOURNAL_FILE'))
    env.pop('LOOP_PY', None)
    env.pop('LOOP_WITH_TESTS', None)
    if use_env:
        env['LOOP_PY'] = py
        env['LOOP_WITH_TESTS'] = '1'
        cmd = ['bash', tree + '/install.sh']
    else:
        cmd = ['bash', tree + '/install.sh', py]
    cp = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=work)
    ok = str(cp.returncode) == expect
    held = ''
    if use_env:
        has = os.path.isdir(home + '/' + arg)
        held = ' holds_%s=%s' % (arg.replace('/', '_').lstrip('.'), 'yes' if has else 'no')
        ok = ok and has
    return ok, 'expected=exit %s%s actual=exit %d%s out_sha=%s' % (
        expect, (' and ' + arg) if use_env else '', cp.returncode, held, sha(cp.stdout + cp.stderr))


def main():
    tree, home, work = env_dirs('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py', False)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    return tally(rows, {
        'envinstall': lambda rid, expect, arg: run_install(tree, work, py, expect, arg, 'a', True),
        'posinstall': lambda rid, expect, arg: run_install(tree, work, py, expect, arg, 'b', False),
        'phrase': lambda rid, expect, arg: run_phrase(tree, expect, arg),
    })


if __name__ == '__main__':
    sys.exit(main())
