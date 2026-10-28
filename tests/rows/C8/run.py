#!/usr/bin/env python3
"""C8 rows runner: loop-card-lint and the plan status cell remainder.

Usage: run.py <tree> <home> <work>

Each row writes a plan.md fixture in its own subfolder of <work> (the basename the lint judges as a plan)
holding one task row whose status cell is the row's text, then runs "bash <tree>/bin/loop-card-lint <fixture>".
expect pass: exit 0. expect fail: exit 1 and the output names task T01.
HOME, USERPROFILE and LOOP_HOME point into <home>; LOOP_PY is this interpreter.
Prints PASS or FAIL per row with expected and actual exit (a sha256 stands in for the lint output, which
can hold a home path), then a count, and exits 1 on any FAIL. Nothing is spawned in the background and
nothing is killed.
"""
import hashlib
import os
import subprocess
import sys

NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder


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


def plan_text(cell):
    return '\n'.join([
        '# Plan',
        '',
        '## Live',
        'goal: FIXT-C8 | status: RUNNING',
        '',
        '## Tasks',
        '| T | task | status |',
        '|---|------|--------|',
        '| T01 | a task | %s |' % cell,
        '',
    ])


def run_plan(tree, work, env, rid, expect, cell):
    folder = work + '/' + rid
    os.makedirs(folder, exist_ok=True)
    fixture = folder + '/plan.md'
    with open(fixture, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(plan_text(cell))
    cp = subprocess.run(['bash', tree + '/bin/loop-card-lint', fixture],
                        capture_output=True, text=True, env=env, cwd=work)
    want = 0 if expect == 'pass' else 1
    names_task = ('task T01' in cp.stdout)
    ok = cp.returncode == want and (expect == 'pass' or names_task)
    detail = 'expected_exit=%d actual_exit=%d names_task=%s out_sha256=%s' % (
        want, cp.returncode, 'yes' if names_task else 'no', sha(cp.stdout + cp.stderr))
    return ok, detail


def main():
    if len(sys.argv) != 4:
        print('usage: run.py <tree> <home> <work>')
        return 2
    tree, home, work = fwd(sys.argv[1]), fwd(sys.argv[2]), fwd(sys.argv[3])
    os.makedirs(work, exist_ok=True)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = dict(os.environ)
    env.update({'HOME': home, 'USERPROFILE': home, 'LOOP_HOME': home + '/.loop',
                'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE,
                'PYTHONDONTWRITEBYTECODE': '1'})
    env.pop('LOOP_GOAL', None)
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        if kind == 'plan':
            ok, detail = run_plan(tree, work, env, rid, expect, arg)
        else:
            ok, detail = False, 'unknown kind ' + kind
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
