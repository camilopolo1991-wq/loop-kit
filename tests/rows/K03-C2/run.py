#!/usr/bin/env python3
"""K03-C2 rows runner: the card lint checks plan PASS cells against the step log.

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (the home every spawned process gets as HOME and USERPROFILE,
with LOOP_HOME at its .loop), LOOP_WORK (a work folder, created when absent; each row writes its fixtures under its own
subfolder), LOOP_PY (the interpreter the lint needs), LOOP_NAMES_FILE (passed through to spawned processes).
Every fixture is written at run time from the row text: a plan fixture under the basename the plan lint judges, and a log
fixture. The lint is run as: bash <tree>/bin/loop-card-lint --log <log fixture> <plan fixture>.
Prints PASS or FAIL per row with expected and actual; a sha256 stands in for the output, which can hold a home path.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import env_dirs, load_rows, make_env, sha, tally, write_text


PLAN = (
    '# Plan ZZZ-99\n'
    '\n'
    '## Live\n'
    'goal: ZZZ-99 | status: RUNNING\n'
    '\n'
    '## Tasks\n'
    '| T | task | owner | status |\n'
    '|---|------|-------|--------|\n'
    '| T01 | scout the thing | scout | TODO |\n'
    '| T02 | change the thing | writer | PASS %s |\n'
)


def run_lint(tree, work, home, rid, expect, arg):
    want_exit, want_text = expect.split('|', 1)
    evpath, logtext = arg.split('|', 1)
    folder = '%s/%s' % (work, rid)
    os.makedirs(folder, exist_ok=True)
    plan = folder + '/plan.md'
    log = folder + '/steps.log'
    write_text(plan, PLAN % evpath)
    write_text(log, logtext.replace('\\n', '\n') + '\n')
    cp = subprocess.run(['bash', tree + '/bin/loop-card-lint', '--log', log, plan],
                        capture_output=True, text=True, env=make_env(home, drop=('LOOP_GOAL', 'JOURNAL_FILE')), cwd=work)
    out = cp.stdout + cp.stderr
    ok = str(cp.returncode) == want_exit
    names = 'n/a'
    if want_text != '-':
        has = want_text in out
        names = 'yes' if has else 'no'
        ok = ok and has
    return ok, 'expected=exit %s names=%s actual=exit %d names=%s out_sha=%s' % (
        want_exit, want_text, cp.returncode, names, sha(out))


def main():
    tree, home, work = env_dirs('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py', False)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    return tally(rows, {
        'lint': lambda rid, expect, arg: run_lint(tree, work, home, rid, expect, arg),
    })


if __name__ == '__main__':
    sys.exit(main())
