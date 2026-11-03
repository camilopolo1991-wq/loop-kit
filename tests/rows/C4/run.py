#!/usr/bin/env python3
"""C4 rows runner: loop-journal --check judges DONE or PASS lines and takes --file and --plan.

Usage: run.py <tree> <home> <work>

Runs "bash <tree>/bin/loop-journal --check ..." on fixtures written under <work> at run time:
a step log per row, and a plan fixture in its own subfolder. HOME, USERPROFILE and LOOP_HOME
point into <home>; no home path is written in the row text. Prints PASS or FAIL per row with
the expected and actual exit and a sha256 prefix of the output text (never the text), then a
count, and exits 1 on any FAIL. Nothing is spawned in the background and nothing is killed.
"""
import os
import re
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import Score, dirs_or_args, fwd, load_rows, make_env, sha, write_text

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


def main():
    tree, home, work = dirs_or_args()
    os.makedirs(work, exist_ok=True)
    stub = tree + '/bin/loop-journal'
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = make_env(home, {'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE},
                   ('LOOP_GOAL', 'JOURNAL_FILE'))
    score = Score()
    for rid, kind, expect, _desc in rows:
        log = work + '/' + rid + '.log'
        write_text(log, '\n'.join(l % GOAL for l in LOGS[kind]) + '\n')
        cmd = ['bash', stub, '--check', GOAL, '--file', log]
        if kind != 'noplan':
            pdir = work + '/plan-' + rid
            os.makedirs(pdir, exist_ok=True)
            write_text(pdir + '/plan.md', PLAN)
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
        score.row(ok, rid, 'expected_exit=%d actual_exit=%d out_sha=%s' % (want, cp.returncode, sha(out)))
    return score.done(rows)


if __name__ == '__main__':
    sys.exit(main())
