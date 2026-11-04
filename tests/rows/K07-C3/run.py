#!/usr/bin/env python3
"""K07-C3 rows runner: the DISPATCH-order rule of the step-log tool's --check. A DISPATCH line of a goal needs a return file
(return.md in its card path's own folder), and a second DISPATCH of a task must not sit before that task's first return, FAIL or
BLOCKED line.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k07c3-manifest.txt
  LOOP_PY          the interpreter the tool is run with (defaults to the one running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  check            the case named by arg is built under LOOP_WORK (plan, step log, return files; every goal id, task id and path is
                   constructed here) and LOOP_TREE/bin/loop_journal.py --check <goal> --file <log> --plan <plan> is run on it;
                   expect is '<exit>:<tokens>', the exit code and the comma separated tokens that must be in the output, a
                   token with a leading ! being one that must be absent
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
MANIFEST = 'k07c3-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
GOAL = 'K07-FIX'
OTHER = 'K07-OTH'
PLAN = '| id | what | owner | status |\n|---|---|---|---|\n| T01 | fixture change | writer | open |\n'
W = 'evidence/T01/writer/card.md'
W2 = 'evidence/T01/writer/r2/card.md'
R = 'evidence/T01/writer/return.md'
R2 = 'evidence/T01/writer/r2/return.md'
S = 'evidence/T01/card.md'

# case: lines (goal, step, text) in order; returns: return files saved, relative to the plan folder ('pl/'), or 'log/...' beside the log;
# mode: plain (the card paths are relative, the plan is given), lh (cards spelled $LOOP_HOME/..., LOOP_HOME in the fixture),
# home (cards spelled ~/..., HOME in the fixture), defplan (no --plan: the plan is at LOOP_HOME/goals/<goal>/plan.md of the fixture)
CASES = {
    'two-one-saved': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'RETURN ' + R), (GOAL, 'T01', 'DISPATCH writer ' + W2),
                                 (GOAL, 'T01', 'RETURN ' + R2)], returns=[R]),
    'two-both-saved': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'RETURN ' + R), (GOAL, 'T01', 'DISPATCH writer ' + W2),
                                  (GOAL, 'T01', 'RETURN ' + R2)], returns=[R, R2]),
    'writer-none': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'ROLLBACK evidence/T01/writer/rollback.txt sha256 aa'),
                               (GOAL, 'T01', 'DONE ' + R)], returns=[]),
    'writer-saved': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'ROLLBACK evidence/T01/writer/rollback.txt sha256 aa'),
                                (GOAL, 'T01', 'DONE ' + R)], returns=[R]),
    'second-before-return': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'DISPATCH writer ' + W2),
                                        (GOAL, 'T01', 'RETURN ' + R2)], returns=[R, R2]),
    'blocked-between': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'BLOCKED needs a decision'),
                                   (GOAL, 'T01', 'DISPATCH writer ' + W2), (GOAL, 'T01', 'RETURN ' + R2)], returns=[R, R2]),
    'fail-between': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'FAIL the reviewer found a defect'),
                                (GOAL, 'T01', 'DISPATCH writer ' + W2), (GOAL, 'T01', 'RETURN ' + R2)], returns=[R, R2]),
    'note-between': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'NOTE only a note'),
                                (GOAL, 'T01', 'DISPATCH writer ' + W2), (GOAL, 'T01', 'RETURN ' + R2)], returns=[R, R2]),
    'last-in-flight': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'RETURN ' + R), (GOAL, 'T01', 'DISPATCH writer ' + W2)],
                           returns=[R]),
    'last-later-line': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'RETURN ' + R), (GOAL, 'T01', 'DISPATCH writer ' + W2),
                                   (GOAL, 'T01', 'NOTE a later line of the same goal')], returns=[R]),
    'last-later-other-goal': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'RETURN ' + R), (GOAL, 'T01', 'DISPATCH writer ' + W2),
                                         (OTHER, 'T01', 'NOTE a line of another goal')], returns=[R]),
    'only-dispatch-last': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W)], returns=[]),
    'only-dispatch-then-other-goal': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (OTHER, 'T01', 'NOTE a line of another goal')],
                                          returns=[]),
    'other-goal-dispatch-not-judged': dict(lines=[(OTHER, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'NOTE a line of this goal')], returns=[]),
    'no-card-word': dict(lines=[(GOAL, 'T01', 'DISPATCH writer the card is somewhere'), (GOAL, 'T01', 'BLOCKED x')], returns=[]),
    'last-md-word': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + S + ' see ' + W), (GOAL, 'T01', 'BLOCKED x')], returns=[R]),
    'first-md-word-only': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + S + ' see ' + W), (GOAL, 'T01', 'BLOCKED x')], returns=['evidence/T01/return.md']),
    'beside-log': dict(lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'BLOCKED x')], returns=[], beside_log=[R]),
    'lh': dict(mode='lh', lines=[(GOAL, 'T01', 'DISPATCH writer $LOOP_HOME/' + W), (GOAL, 'T01', 'BLOCKED x')], returns=[R]),
    'lh-none': dict(mode='lh', lines=[(GOAL, 'T01', 'DISPATCH writer $LOOP_HOME/' + W), (GOAL, 'T01', 'BLOCKED x')], returns=[]),
    'home': dict(mode='home', lines=[(GOAL, 'T01', 'DISPATCH writer ~/' + W), (GOAL, 'T01', 'BLOCKED x')], returns=[R]),
    'home-none': dict(mode='home', lines=[(GOAL, 'T01', 'DISPATCH writer ~/' + W), (GOAL, 'T01', 'BLOCKED x')], returns=[]),
    'defplan': dict(mode='defplan', lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'BLOCKED x')], returns=[R]),
    'defplan-none': dict(mode='defplan', lines=[(GOAL, 'T01', 'DISPATCH writer ' + W), (GOAL, 'T01', 'BLOCKED x')], returns=[]),
}


def build(ctx, name):
    c = CASES[name]
    mode = c.get('mode', 'plain')
    base = '%s/k07c3-fixtures/%s-%d' % (ctx['work'], name, time.time_ns())
    register(ctx['work'], MANIFEST, base)
    extra = {}
    if mode == 'lh':
        root = base + '/lhome'
        extra['LOOP_HOME'] = root
        plan_dir = base + '/pl'
        plan_arg = True
    elif mode == 'home':
        root = base + '/hm'
        extra.update({'HOME': root, 'USERPROFILE': root, 'LOOP_HOME': root + '/.loop'})
        plan_dir = base + '/pl'
        plan_arg = True
    elif mode == 'defplan':
        root = base + '/lhome'
        extra['LOOP_HOME'] = root
        plan_dir = root + '/goals/' + GOAL
        plan_arg = False
    else:
        root = base + '/pl'
        plan_dir = base + '/pl'
        plan_arg = True
    os.makedirs(plan_dir, exist_ok=True)
    os.makedirs(base + '/log', exist_ok=True)
    plan = plan_dir + '/plan.md'
    write_text(plan, PLAN)
    log = base + '/log/steps.log'
    stamps = ''.join('- 2026-01-01T00:00:%02dZ %s %s %s\n' % (i, g, s, t) for i, (g, s, t) in enumerate(c['lines']))
    write_text(log, stamps)
    where = plan_dir if mode in ('plain', 'defplan') else root
    for rel in c['returns']:
        os.makedirs(os.path.dirname(where + '/' + rel), exist_ok=True)
        write_text(where + '/' + rel, 'fixture return\n')
    for rel in c.get('beside_log', []):
        os.makedirs(os.path.dirname(base + '/log/' + rel), exist_ok=True)
        write_text(base + '/log/' + rel, 'fixture return\n')
    args = ['--check', GOAL, '--file', log] + (['--plan', plan] if plan_arg else [])
    return args, extra


def row_check(ctx, rid, expect, arg):
    code, toks = expect.split(':', 1)
    args, extra = build(ctx, arg)
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_journal.py'] + args, capture_output=True, env=make_env(ctx['home'], extra, DROP),
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
    info_sha((('tests/rows/K07-C3/run.py', here + '/run.py'), ('tests/rows/K07-C3/rows.txt', here + '/rows.txt')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    return tally(load_rows(here + '/rows.txt'), {'check': row_check}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
