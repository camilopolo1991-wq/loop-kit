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
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import dirs_or_args, fwd, load_rows, make_env, sha, tally, write_text

NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder


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
    write_text(fixture, plan_text(cell))
    # A step log fixture with a PASS line for the fixture's goal id (its Live goal: line) and task id T01,
    # named to the lint through JOURNAL_FILE in this process's environment (no --log: wt-main would read it as a file).
    goal = 'FIXT-C8'
    for pl in plan_text(cell).splitlines():
        if pl.startswith('goal:'):
            goal = pl.split()[1]
    logfix = folder + '/steps.log'
    write_text(logfix, '- 2026-01-01T00:00:00Z %s T01 PASS fixture line\n' % goal)
    renv = dict(env)
    renv['JOURNAL_FILE'] = logfix
    cp = subprocess.run(['bash', tree + '/bin/loop-card-lint', fixture],
                        capture_output=True, text=True, env=renv, cwd=work)
    want = 0 if expect == 'pass' else 1
    names_task = ('task T01' in cp.stdout)
    ok = cp.returncode == want and (expect == 'pass' or names_task)
    detail = 'expected_exit=%d actual_exit=%d names_task=%s out_sha256=%s' % (
        want, cp.returncode, 'yes' if names_task else 'no', sha(cp.stdout + cp.stderr))
    return ok, detail


def main():
    tree, home, work = dirs_or_args()
    os.makedirs(work, exist_ok=True)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = make_env(home, {'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE},
                   ('LOOP_GOAL',))
    return tally(rows, {
        'plan': lambda rid, expect, arg: run_plan(tree, work, env, rid, expect, arg),
    })


if __name__ == '__main__':
    sys.exit(main())
