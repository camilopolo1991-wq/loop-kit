#!/usr/bin/env python3
"""K11-C8 rows runner: the step-log tool's --check reads a BLOCKED leader record as the outcome of a dispatch that has no return.md.
A DISPATCH line whose card has no return.md beside it prints a FAIL line, unless a later line of the same task, before that task's
next DISPATCH, has the text "BLOCKED leader record: ..." (hook-denied, or cut by the usage limit). Then the dispatch is answered:
no FAIL line, a NOTE line instead.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k11c8-manifest.txt
  LOOP_PY          the interpreter the tool is run with (defaults to the one running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  check            the case named by arg is built under LOOP_WORK (throwaway plan, step log and goal folder; every goal id, task id and
                   path is constructed here) and LOOP_TREE/bin/loop_journal.py --check <goal> --file <log> --plan <plan> is run on it;
                   expect is '<exit>:<tokens>', the exit code and the tokens (separated by ' ;; ') that must be in the output, a token
                   with a leading ! being one that must be absent
Prints PASS or FAIL per row with expected and actual and the raw output of the fixture check (work folder masked), then
rows=N pass=P fail=F. Nothing is spawned in the background; the live step log and the live home are never named.
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
MANIFEST = 'k11c8-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
G = 'K11-FIX'
PLAN = '| id | what | owner | status |\n|---|---|---|---|\n| T01 | fixture change | writer | open |\n| T02 | fixture change | writer | open |\n'
W1 = 'evidence/T01/writer/card.md'
W2 = 'evidence/T02/writer/card.md'
R1 = 'evidence/T01/writer/return.md'
BLK = 'BLOCKED leader record: hook-denied, card ' + W1
START = ('GOAL', 'START fixture run')
D1 = ('T01', 'DISPATCH writer ' + W1)
D2 = ('T02', 'DISPATCH writer ' + W2)
NOTE = ('T02', 'NOTE a later line of the goal')

# case: lines (step, text) in order; returns: return files saved (relative to the plan folder)
CASES = {
    'blocked-no-return': dict(lines=[START, D1, ('T01', BLK), NOTE]),
    'neither': dict(lines=[START, D1, NOTE]),
    'return-saved': dict(lines=[START, D1, ('T01', 'RETURN ' + R1), NOTE], returns=[R1]),
    'blocked-other-task': dict(lines=[START, D1, ('T02', BLK), NOTE]),
    'blocked-not-leader-record': dict(lines=[START, D1, ('T01', 'BLOCKED needs a decision'), NOTE]),
    'blocked-before-dispatch': dict(lines=[START, ('T01', BLK), D1, NOTE]),
    'blocked-after-next-dispatch': dict(lines=[START, D1, ('T01', 'DISPATCH writer evidence/T01/writer/r2/card.md'), ('T01', BLK), NOTE]),
}


def build(ctx, name):
    c = CASES[name]
    base = '%s/k11c8-fixtures/%s-%d' % (ctx['work'], name, time.time_ns())
    register(ctx['work'], MANIFEST, base)
    pl = base + '/goal'
    os.makedirs(pl, exist_ok=True)
    os.makedirs(base + '/log', exist_ok=True)
    write_text(pl + '/plan.md', PLAN)
    log = base + '/log/steps.log'
    write_text(log, ''.join('- 2026-01-01T10:%02d:%02dZ %s %s %s\n' % (i * 10 // 60, i * 10 % 60, G, step, text)
                            for i, (step, text) in enumerate(c['lines'])))
    for rel in c.get('returns', []):
        os.makedirs(os.path.dirname(pl + '/' + rel), exist_ok=True)
        write_text(pl + '/' + rel, 'fixture return\n')
    return ['--check', G, '--file', log, '--plan', pl + '/plan.md']


def row_check(ctx, rid, expect, arg):
    code, toks = expect.split(':', 1)
    args = build(ctx, arg)
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_journal.py'] + args, capture_output=True, env=make_env(ctx['home'], None, DROP),
                        cwd=ctx['work'], stdin=subprocess.DEVNULL)
    out = cp.stdout.decode('utf-8', 'replace').replace('\r', '') + cp.stderr.decode('utf-8', 'replace').replace('\r', '')
    bad = []
    for t in toks.split(' ;; '):
        if t.startswith('!'):
            if t[1:] in out:
                bad.append(t)
        elif t not in out:
            bad.append(t)
    ok = cp.returncode == int(code) and not bad
    shown = out.replace(ctx['work'], 'WORK').replace('\n', ' / ')[:500]
    return ok, 'expected=exit %s, tokens %s actual=exit %d, unmet %s, output bytes %d sha256 %s raw output=%s' % (
        code, toks, cp.returncode, ' | '.join(bad) or 'none', len(out.encode('utf-8')), sha(out), shown)


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K11-C8/run.py', here + '/run.py'), ('tests/rows/K11-C8/rows.txt', here + '/rows.txt'),
              ('bin/loop_journal.py', tree + '/bin/loop_journal.py')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    return tally(load_rows(here + '/rows.txt'), {'check': row_check}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
