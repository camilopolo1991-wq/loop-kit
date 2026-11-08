#!/usr/bin/env python3
"""K11-C6 rows runner: the six card defects D1 to D6 and their corrected twins through bin/loop_card_lint.py.
Each defect card (cards/, built from the shape of a real task or review card, constructed names and paths only) exits 1 and its output
names the check that catches it and says one rule is broken; its corrected twin, which differs from it only in the defect, exits 0.
  D1 a scout card carrying a merge instruction          c1f-no-merge
  D2 a reviewer card naming no raw comparison command   c1e-reviewer-comparison
  D3 a reviewer card whose Rollback line points at the writer's evidence subfolder   c1g-reviewer-no-writer-folder
  D4 a read-only reviewer card told to cp               c1e-readonly-no-copy
  D5 a writer card sending pre-edit copies to evidence/ instead of scratch   c1d-copies-under-scratch
  D6 a writer card naming LOOP_PY                       c1a-interpreter-shape
The last row runs the same twelve through the lint of LOOP_MAIN_TREE and quotes how many of D1 to D6 that lint passes (the control).

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test: its bin/loop_card_lint.py judges rows 1 to 12
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k11c6-manifest.txt
  LOOP_MAIN_TREE   a main tree, for the last row; unset makes that row fail
  LOOP_PY          the interpreter the lint is run with (defaults to the one running this file)

Rows (rows.txt, id :: kind :: expect :: arg): defect, twin, main-count (see the header of rows.txt).
Each fixture card is copied to card.md at the place its role needs under a throwaway goal folder (goals/K11-FIX/evidence/T01/ for a
scout, .../review/ for a reviewer, .../writer/ for a writer) with the goal's writable.txt beside it, so the lint finds the role from
the path as it does for a real card. Prints PASS or FAIL per row with expected and actual and the raw lint output (work folder
masked), then rows=N pass=P fail=F. Nothing is spawned in the background; the live home and the live step log are never named.
"""
import os
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, register, sha, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_MAIN_TREE=<main tree> [LOOP_PY=<python>] python run.py '
         '(no positional argument)')
MANIFEST = 'k11c6-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
WRITABLE = 'C:/Fixture/loop/work/K11-FIX/kit\nC:/Fixture/loop/scratch/K11-FIX/work\n'
SUB = {'scout': '', 'reviewer': '/review', 'writer': '/writer'}
DEFECTS = ('d1-scout-merge.md|scout', 'd2-reviewer-no-comparison.md|reviewer', 'd3-reviewer-rollback-writer-folder.md|reviewer',
           'd4-reviewer-told-to-cp.md|reviewer', 'd5-writer-copies-to-evidence.md|writer', 'd6-writer-names-loop-py.md|writer')


def lint(ctx, tree, arg):
    """Place the fixture card named by arg ('file|role') and run tree/bin/loop_card_lint.py on it; (exit code, output)."""
    name, role = arg.split('|', 1)
    src = read_bytes(ctx['here'] + '/cards/' + name)
    if src is None:
        return -1, 'fixture card absent: ' + name
    base = '%s/k11c6-fixtures/%s-%d' % (ctx['work'], name[:-3], time.time_ns())
    register(ctx['work'], MANIFEST, base)
    goal = base + '/goals/K11-FIX'
    os.makedirs(goal + '/evidence/T01' + SUB[role], exist_ok=True)
    write_text(goal + '/writable.txt', WRITABLE)
    card = goal + '/evidence/T01' + SUB[role] + '/card.md'
    with open(card, 'wb') as fh:
        fh.write(src)
    cp = subprocess.run([ctx['py'], tree + '/bin/loop_card_lint.py', card], capture_output=True, env=make_env(ctx['home'], None, DROP),
                        cwd=ctx['work'], stdin=subprocess.DEVNULL)
    out = cp.stdout.decode('utf-8', 'replace').replace('\r', '') + cp.stderr.decode('utf-8', 'replace').replace('\r', '')
    return cp.returncode, out.replace(ctx['work'], 'WORK')


def judge(ctx, rid, expect, arg):
    code, toks = expect.split(':', 1)
    rc, out = lint(ctx, ctx['tree'], arg)
    bad = []
    for t in toks.split(' ;; '):
        if t.startswith('!'):
            if t[1:] in out:
                bad.append(t)
        elif t not in out:
            bad.append(t)
    ok = rc == int(code) and not bad
    shown = out.replace('\n', ' / ')[:600]
    return ok, 'expected=exit %s, tokens %s actual=exit %d, unmet %s, output bytes %d sha256 %s raw output=%s' % (
        code, toks, rc, ' | '.join(bad) or 'none', len(out.encode('utf-8')), sha(out), shown)


def row_defect(ctx, rid, expect, arg):
    return judge(ctx, rid, expect, arg)


def row_twin(ctx, rid, expect, arg):
    return judge(ctx, rid, expect, arg)


def row_main_count(ctx, rid, expect, arg):
    main = ctx['main']
    if not main or read_bytes(main + '/bin/loop_card_lint.py') is None:
        return False, 'expected=a main tree with bin/loop_card_lint.py actual=LOOP_MAIN_TREE unset or without the lint'
    passed = []
    twins = 0
    codes = []
    for d in DEFECTS:
        rc, out = lint(ctx, main, d)
        codes.append(rc)
        if rc == 0:
            passed.append(d.split('-')[0].upper())
        trc, _ = lint(ctx, main, d.replace('.md|', '-twin.md|'))
        codes.append(trc)
        twins += (trc == 0)
    ran = all(c in (0, 1) for c in codes)
    verdict = 'main lint caught all six' if not passed else 'main lint passes %d of D1 to D6 (%s)' % (len(passed), ' '.join(passed))
    return ran, 'expected=the twelve cards run on the main lint actual=%s; twins passed by main %d of 6; main lint sha256 %s; exit codes %s' % (
        verdict, twins, sha(read_bytes(main + '/bin/loop_card_lint.py')), ' '.join(str(c) for c in codes))


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    mt = os.environ.get('LOOP_MAIN_TREE')
    info_sha((('tests/rows/K11-C6/run.py', here + '/run.py'), ('tests/rows/K11-C6/rows.txt', here + '/rows.txt'),
              ('bin/loop_card_lint.py', tree + '/bin/loop_card_lint.py')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'here': fwd(here), 'main': fwd(mt) if mt else '',
           'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    return tally(load_rows(here + '/rows.txt'), {'defect': row_defect, 'twin': row_twin, 'main-count': row_main_count}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
