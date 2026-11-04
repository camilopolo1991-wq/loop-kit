#!/usr/bin/env python3
"""K07-C2 rows runner: the plan-row lint of loop-card-lint, rule (a) the evidence path of a PASS row and rule (b) --goal.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k07c2-manifest.txt
  LOOP_PY          the interpreter the lint is run with (defaults to the one running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  lint             the case named by arg is built under LOOP_WORK (every plan, GOAL and log text is constructed here) and
                   LOOP_TREE/bin/loop_card_lint.py is run on its arguments; expect is '<exit>:<tokens>', the exit code and
                   the comma separated tokens that must be in the output, a token with a leading ! being one that must be absent
Prints PASS or FAIL per row with expected and actual, then rows=N pass=P fail=F. Nothing is spawned in the background.
"""
import os
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, register, sha, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py '
         '(no positional argument)')
MANIFEST = 'k07c2-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
GID = 'FIX-01'


def plan(*tasks):
    """tasks: (task id, text cell, status cell)."""
    head = '# Fixture plan\n\n| T | task | done when | status |\n|---|---|---|---|\n'
    body = ''.join('| %s | %s | fixture done when | %s |\n' % t for t in tasks)
    return head + body + '\n## Live\ngoal: %s | status: RUNNING | window: none\n' % GID


def log(*tids):
    return ''.join('- 2026-01-01T00:00:00Z %s %s PASS fixture\n' % (GID, t) for t in tids)


def goal(n):
    return '# Fixture goal\n\nStatus: fixture\nAcceptance criteria\n' + ''.join('%d. fixture criterion %d\n' % (i, i) for i in range(1, n + 1))


STAND = '## Standing rules\n' + ''.join('%d. fixture standing rule %d\n' % (i, i) for i in range(1, 6))


def covers(*ns):
    return 'fixture work, serves ' + ' '.join('AC%d' % n for n in ns)


OWN = 'PASS evidence/T02/review/verdict.md'
OTHER = 'PASS evidence/T03/return.md'

# case: (files: relative path -> text, arguments in order; an argument not starting with -- is a relative path)
CASES = {
    'ev-other-task': ({'d/plan.md': plan(('T01', 'fixture scout', 'PASS evidence/T01/r1/return.md'), ('T02', 'fixture writer', OTHER)),
                       'd/log.txt': log('T01', 'T02')}, ['--log', 'd/log.txt', 'd/plan.md']),
    'ev-own-task': ({'d/plan.md': plan(('T01', 'fixture scout', 'PASS evidence/T01/r1/return.md'), ('T02', 'fixture writer', OWN)),
                     'd/log.txt': log('T01', 'T02')}, ['--log', 'd/log.txt', 'd/plan.md']),
    'ev-c8-shape': ({'d/plan.md': plan(('T01', 'fixture writer', 'PASS evidence/T03/review/rollback.txt')), 'd/log.txt': log('T01')},
                    ['--log', 'd/log.txt', 'd/plan.md']),
    'ev-other-lower': ({'d/plan.md': plan(('T02', 'fixture writer', 'PASS evidence/t03/return.md')), 'd/log.txt': log('T02')},
                       ['--log', 'd/log.txt', 'd/plan.md']),
    'ev-no-path': ({'d/plan.md': plan(('T02', 'fixture writer', 'PASS')), 'd/log.txt': log('T02')}, ['--log', 'd/log.txt', 'd/plan.md']),
    'ev-no-path-no-log-line': ({'d/plan.md': plan(('T02', 'fixture writer', 'PASS')), 'd/log.txt': log('T01')},
                               ['--log', 'd/log.txt', 'd/plan.md']),
    'ev-non-pass-other': ({'d/plan.md': plan(('T02', 'fixture writer', 'TODO'))}, ['d/plan.md']),
    'goal4-plan3': ({'d/GOAL.md': goal(4), 'd/plan.md': plan(('T01', covers(1, 2), 'TODO'), ('T02', covers(3), 'TODO'))},
                    ['--goal', 'd/GOAL.md', 'd/plan.md']),
    'goal4-plan4': ({'d/GOAL.md': goal(4), 'd/plan.md': plan(('T01', covers(1, 2), 'TODO'), ('T02', covers(3, 4), 'TODO'))},
                    ['--goal', 'd/GOAL.md', 'd/plan.md']),
    'goal4-plan3-no-flag': ({'d/GOAL.md': goal(4), 'd/plan.md': plan(('T01', covers(1, 2), 'TODO'), ('T02', covers(3), 'TODO'))},
                            ['d/plan.md']),
    'ac10-not-ac1': ({'d/GOAL.md': goal(1), 'd/plan.md': plan(('T01', covers(10), 'TODO'))}, ['--goal', 'd/GOAL.md', 'd/plan.md']),
    'ac1-not-ac10': ({'d/GOAL.md': goal(10), 'd/plan.md': plan(('T01', covers(1, 2, 3, 4, 5, 6, 7, 8, 9), 'TODO'))},
                     ['--goal', 'd/GOAL.md', 'd/plan.md']),
    'standing-rules-after-field': ({'d/GOAL.md': goal(3) + 'Authority: fixture owner\n' + STAND,
                                    'd/plan.md': plan(('T01', covers(1, 2, 3), 'TODO'))}, ['--goal', 'd/GOAL.md', 'd/plan.md']),
    'standing-rules-read-without-field': ({'d/GOAL.md': goal(3) + STAND.split('\n', 1)[1],
                                           'd/plan.md': plan(('T01', covers(1, 2, 3), 'TODO'))}, ['--goal', 'd/GOAL.md', 'd/plan.md']),
    'token-in-other-cell': ({'d/GOAL.md': goal(2), 'd/plan.md': '# Fixture plan\n\n| T | task | done when | status |\n|---|---|---|---|\n'
                             '| T01 | fixture work, serves AC1 | AC2 is said here only | TODO |\n\n## Live\ngoal: %s | status: RUNNING | window: none\n' % GID},
                            ['--goal', 'd/GOAL.md', 'd/plan.md']),
    'goal-and-log': ({'d/GOAL.md': goal(2), 'd/plan.md': plan(('T01', covers(1, 2), 'PASS evidence/T01/review/verdict.md')),
                      'd/log.txt': log('T01')}, ['--log', 'd/log.txt', '--goal', 'd/GOAL.md', 'd/plan.md']),
    'goal-and-log-gap': ({'d/GOAL.md': goal(2), 'd/plan.md': plan(('T01', covers(1), 'PASS evidence/T01/review/verdict.md')),
                          'd/log.txt': log('T01')}, ['--goal', 'd/GOAL.md', '--log', 'd/log.txt', 'd/plan.md']),
    'goal-and-log-other-task': ({'d/GOAL.md': goal(1), 'd/plan.md': plan(('T01', covers(1), 'PASS evidence/T04/review/verdict.md')),
                                 'd/log.txt': log('T01')}, ['--goal', 'd/GOAL.md', '--log', 'd/log.txt', 'd/plan.md']),
    'goal-missing': ({'d/plan.md': plan(('T01', covers(1), 'TODO'))}, ['--goal', 'd/nothing.md', 'd/plan.md']),
    'goal-no-value': ({'d/plan.md': plan(('T01', covers(1), 'TODO'))}, ['d/plan.md', '--goal']),
}


def build(ctx, name):
    files, args = CASES[name]
    base = '%s/k07c2-fixtures/%s-%d' % (ctx['work'], name, time.time_ns())
    register(ctx['work'], MANIFEST, base)
    for rel, text in files.items():
        os.makedirs(os.path.dirname(base + '/' + rel), exist_ok=True)
        write_text(base + '/' + rel, text)
    return [a if a.startswith('--') else base + '/' + a for a in args]


def row_lint(ctx, rid, expect, arg):
    code, toks = expect.split(':', 1)
    args = build(ctx, arg)
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_card_lint.py'] + args, capture_output=True, env=make_env(ctx['home'], {}, DROP),
                        cwd=ctx['work'], stdin=subprocess.DEVNULL)
    out = cp.stdout.decode('utf-8', 'replace').replace('\r', '') + cp.stderr.decode('utf-8', 'replace').replace('\r', '')
    bad = []
    for t in toks.split(','):
        if t.startswith('!'):
            if t[1:] in out:
                bad.append(t)
        elif t not in out:
            bad.append(t)
    ok = cp.returncode == int(code) and not bad
    return ok, 'expected=exit %s, tokens %s actual=exit %d, unmet %s, output bytes %d sha256 %s' % (
        code, toks, cp.returncode, ' '.join(bad) or 'none', len(out.encode('utf-8')), sha(out))


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K07-C2/run.py', here + '/run.py'), ('tests/rows/K07-C2/rows.txt', here + '/rows.txt')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    return tally(load_rows(here + '/rows.txt'), {'lint': row_lint}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
