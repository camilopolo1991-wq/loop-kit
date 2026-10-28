#!/usr/bin/env python3
"""K03-C1 rows runner: install.sh environment form, positional form, README phrase.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (used only for the set-or-usage check; no row targets it,
because each install row makes a fresh home under LOOP_WORK), LOOP_WORK (a work folder, created when absent),
LOOP_PY (the interpreter for the install rows), LOOP_NAMES_FILE (passed through to spawned processes).
Exits 64 with a usage line when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Every spawned process gets HOME and USERPROFILE at the home it targets and LOOP_HOME at that home's .loop,
and PYTHONDONTWRITEBYTECODE=1. The install rows each target a fresh home under LOOP_WORK.
Prints PASS or FAIL per row with expected and actual; a sha256 stands in for any text that could hold a home path.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import hashlib
import os
import subprocess
import sys
import time


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
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env.pop('LOOP_GOAL', None)
    env.pop('JOURNAL_FILE', None)
    return env


def fresh_home(work, tag):
    home = '%s/home-%s-%d' % (work, tag, time.time_ns())
    os.makedirs(home)
    return home


def run_install(tree, work, py, expect, arg, rowid, use_env):
    home = fresh_home(work, rowid)
    env = make_env(home)
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


def run_phrase(tree, expect, arg):
    rel, phrase = arg.split('|', 1)
    try:
        with open(tree + '/' + rel, 'rb') as fh:
            data = fh.read()
    except OSError:
        return False, 'expected=%s actual=unreadable' % expect
    actual = 'found' if phrase.encode('utf-8') in data else 'absent'
    return actual == expect, 'expected=%s actual=%s file_sha=%s' % (expect, actual, sha(data))


def main():
    tree_e = os.environ.get('LOOP_TREE')
    home_e = os.environ.get('LOOP_ROWS_HOME')
    work_e = os.environ.get('LOOP_WORK')
    if not tree_e or not home_e or not work_e:
        print('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py')
        return 64
    tree, work = fwd(tree_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        if kind == 'envinstall':
            ok, detail = run_install(tree, work, py, expect, arg, 'a', True)
        elif kind == 'posinstall':
            ok, detail = run_install(tree, work, py, expect, arg, 'b', False)
        elif kind == 'phrase':
            ok, detail = run_phrase(tree, expect, arg)
        else:
            ok, detail = False, 'unknown kind ' + kind
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
