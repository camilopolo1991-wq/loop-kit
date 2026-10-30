#!/usr/bin/env python3
"""C4 rows runner: loop-journal --check judges DONE or PASS lines and takes --file and --plan.

Usage: run.py <tree> <home> <work>

Runs "bash <tree>/bin/loop-journal --check ..." on fixtures written under <work> at run time:
a step log per row, and a plan fixture in its own subfolder. HOME, USERPROFILE and LOOP_HOME
point into <home>; no home path is written in the row text. Prints PASS or FAIL per row with
the expected and actual exit and a sha256 prefix of the output text (never the text), then a
count, and exits 1 on any FAIL. Nothing is spawned in the background and nothing is killed.
"""
import hashlib
import os
import re
import subprocess
import sys

NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder
GOAL = 'FIXT-C4'  # no plan for this id exists under the test home

PLAN = (
    '| Task | Owner | What |\n'
    '|---|---|---|\n'
    '| T01 | writer | first change |\n'
    '| T02 | reviewer | independent check |\n'
    '| T03 | writer | second change |\n'
)

LOGS = {
    'missing': [
        '- 2026-01-01T00:00:00Z %s T01 DONE change made, no rollback written',
        '- 2026-01-01T00:01:00Z %s T02 DONE reviewer line, not judged',
        '- 2026-01-01T00:02:00Z %s T03 ROLLBACK rb.txt sha256 0000000000000000',
        '- 2026-01-01T00:03:00Z %s T03 PASS second change',
    ],
    'inplace': [
        '- 2026-01-01T00:00:00Z %s T01 ROLLBACK rb.txt sha256 0000000000000000',
        '- 2026-01-01T00:01:00Z %s T01 DONE change made',
        '- 2026-01-01T00:02:00Z %s T03 ROLLBACK rb.txt sha256 1111111111111111',
        '- 2026-01-01T00:03:00Z %s T03 PASS second change',
    ],
    'noplan': [
        '- 2026-01-01T00:00:00Z %s T01 ROLLBACK rb.txt sha256 0000000000000000',
        '- 2026-01-01T00:01:00Z %s T01 DONE change made',
    ],
}


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def sha(s):
    return hashlib.sha256(s.encode('utf-8', 'replace')).hexdigest()[:12]


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', 3)])
    return rows


def main():
    if len(sys.argv) == 1:
        tree_e = os.environ.get('LOOP_TREE')
        home_e = os.environ.get('LOOP_ROWS_HOME')
        work_e = os.environ.get('LOOP_WORK')
        if not tree_e or not home_e or not work_e:
            print('usage: run.py <tree> <home> <work>   or   LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> run.py')
            return 64
        sys.argv[1:] = [tree_e, home_e, work_e]
    if len(sys.argv) != 4:
        print('usage: run.py <tree> <home> <work>')
        return 2
    tree, home, work = fwd(sys.argv[1]), fwd(sys.argv[2]), fwd(sys.argv[3])
    os.makedirs(work, exist_ok=True)
    stub = tree + '/bin/loop-journal'
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = dict(os.environ)
    env.update({'HOME': home, 'USERPROFILE': home, 'LOOP_HOME': home + '/.loop',
                'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE,
                'PYTHONDONTWRITEBYTECODE': '1'})
    env.pop('LOOP_GOAL', None)
    env.pop('JOURNAL_FILE', None)
    passed = failed = 0
    for rid, kind, expect, _desc in rows:
        log = work + '/' + rid + '.log'
        with open(log, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('\n'.join(l % GOAL for l in LOGS[kind]) + '\n')
        cmd = ['bash', stub, '--check', GOAL, '--file', log]
        if kind != 'noplan':
            pdir = work + '/plan-' + rid
            os.makedirs(pdir, exist_ok=True)
            with open(pdir + '/plan.md', 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(PLAN)
            cmd += ['--plan', pdir + '/plan.md']
        cp = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=work)
        out = cp.stdout + cp.stderr
        want = int(expect)
        if kind == 'missing':
            ok = (cp.returncode == want and re.search(r'\bT01 DONE at \S+ has no ROLLBACK', out) is not None
                  and 'T02' not in out.split('FAIL', 1)[-1] and 'T03 PASS' not in out
                  and 'missing ROLLBACK 1' in out)
        elif kind == 'inplace':
            ok = cp.returncode == want and 'missing ROLLBACK 0' in out and 'FAIL' not in out
        else:
            ok = cp.returncode == want and 'unreadable' in out
        passed += ok
        failed += (not ok)
        print('%s %s expected_exit=%d actual_exit=%d out_sha=%s' % (
            'PASS' if ok else 'FAIL', rid, want, cp.returncode, sha(out)))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
