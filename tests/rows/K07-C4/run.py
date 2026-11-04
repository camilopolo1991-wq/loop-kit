#!/usr/bin/env python3
"""K07-C4 rows runner: the ROLLBACK-file rule of the step-log tool's --check. A ROLLBACK line of a goal needs the file it names on
disk, and, with --report PATH, the path it names must appear in the Writes section of the report.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k07c4-manifest.txt
  LOOP_PY          the interpreter the tool is run with (defaults to the one running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  check            the case named by arg is built under LOOP_WORK (plan, step log, the files the log names, a report; every goal id,
                   task id and path is constructed here) and LOOP_TREE/bin/loop_journal.py --check <goal> --file <log> --plan <plan>
                   [--report <report>] is run on it; expect is '<exit>:<tokens>', the exit code and the comma separated tokens that
                   must be in the output, a token with a leading ! being one that must be absent
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
MANIFEST = 'k07c4-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
GOAL = 'K07-FIX'
OTHER = 'K07-OTH'
PLAN = '| id | what | owner | status |\n|---|---|---|---|\n| T01 | fixture change | writer | open |\n'
RB = 'evidence/T01/writer/rollback.txt'
ROLL = 'ROLLBACK ' + RB + ' sha256 0123456789abcdef'
DONE = 'DONE evidence/T01/writer/return.md'
LINES = [(GOAL, 'T01', ROLL), (GOAL, 'T01', DONE)]

REP_OK = '# Report\n\n## Writes\n\n- ' + RB + '\n\n## Proof\n\nnothing else\n'
REP_NO_HEADING = '# Report\n\n- ' + RB + '\n\n## Proof\n\nnothing else\n'
REP_NO_SECTION = '# Report\n\n## Proof\n\nnothing else\n'
REP_OUTSIDE = '# Report\n\n## Writes\n\n- nothing written here\n\n## Proof\n\n' + RB + '\n'
REP_AFTER_SUB = '# Report\n\n## Writes\n\n- nothing yet\n\n### Detail\n\n- ' + RB + '\n'
REP_BEFORE = '# Report\n\n- ' + RB + '\n\n## Writes\n\n- nothing written here\n'
REP_COLON = '# Report\n\nWrites:\n\n- ' + RB + '\n\n## Proof\n\nnothing else\n'
REP_PLAIN = '# Report\n\nWrites\n\n- ' + RB + '\n'
REP_LOWER = '# Report\n\n## writes\n\n- ' + RB + '\n'
REP_TWO = '# Report\n\n## Writes\n\n- nothing yet\n\n## Proof\n\nx\n\n## Writes:\n\n- ' + RB + '\n'
# the paths of the home and loop-home cases lie under goals/<goal>/evidence/, which the K05-C2 path rule accepts
GRB = 'goals/' + GOAL + '/evidence/T01/writer/rollback.txt'
REP_HOME = '# Report\n\n## Writes\n\n- ~/.loop/' + GRB + '\n'
REP_LH = '# Report\n\n## Writes\n\n- $LOOP_HOME/' + GRB + '\n'
REP_ELSEWHERE = '# Report\n\n## Writes\n\n- ~/.loop/goals/' + GOAL + '/evidence/T02/writer/rollback.txt\n'

# case: lines (goal, step, text) in order, '@ROOT' standing for the case root (HM or LH folder); files: relative to the root of the case
# (the plan folder 'pl' in plain mode); report: the report text, None for no report file; flag: pass --report (default when a report
# or a missing report is meant); mode: plain, home (HOME is the fixture hm folder), lh (LOOP_HOME is the fixture lhome folder),
# defplan (no --plan; the plan is at LOOP_HOME/goals/<goal>/plan.md of the fixture)
CASES = {
    'file-absent': dict(lines=LINES, files=[], report=None),
    'file-present': dict(lines=LINES, files=[RB], report=None),
    'second-line-absent': dict(lines=[(GOAL, 'T01', ROLL), (GOAL, 'T01', 'ROLLBACK evidence/T01/writer/other.txt sha256 aa'), (GOAL, 'T01', DONE)],
                               files=[RB], report=None),
    'other-goal-not-judged': dict(lines=[(OTHER, 'T01', 'ROLLBACK evidence/T01/writer/none.txt sha256 aa')] + LINES, files=[RB], report=None),
    'no-word': dict(lines=[(GOAL, 'T01', 'ROLLBACK'), (GOAL, 'T01', DONE)], files=[RB], report=None),
    'quoted-word': dict(lines=[(GOAL, 'T01', 'ROLLBACK `' + RB + '` sha256 aa'), (GOAL, 'T01', DONE)], files=[RB], report=None),
    'first-word-only': dict(lines=[(GOAL, 'T01', 'ROLLBACK evidence/T01/writer/none.txt ' + RB), (GOAL, 'T01', DONE)], files=[RB], report=None),
    'home-present': dict(mode='home', lines=[(GOAL, 'T01', 'ROLLBACK ~/.loop/' + GRB + ' sha256 aa'), (GOAL, 'T01', DONE)],
                         files=['.loop/' + GRB], report=None),
    'home-absent': dict(mode='home', lines=[(GOAL, 'T01', 'ROLLBACK ~/.loop/' + GRB + ' sha256 aa'), (GOAL, 'T01', DONE)], files=[], report=None),
    'lh-present': dict(mode='lh', lines=[(GOAL, 'T01', 'ROLLBACK $LOOP_HOME/' + GRB + ' sha256 aa'), (GOAL, 'T01', DONE)], files=[GRB], report=None),
    'lh-absent': dict(mode='lh', lines=[(GOAL, 'T01', 'ROLLBACK $LOOP_HOME/' + GRB + ' sha256 aa'), (GOAL, 'T01', DONE)], files=[], report=None),
    'defplan-present': dict(mode='defplan', lines=LINES, files=[RB], report=None),
    'defplan-absent': dict(mode='defplan', lines=LINES, files=[], report=None),
    'report-ok': dict(lines=LINES, files=[RB], report=REP_OK),
    'report-no-heading': dict(lines=LINES, files=[RB], report=REP_NO_HEADING),
    'report-no-section': dict(lines=LINES, files=[RB], report=REP_NO_SECTION),
    'report-outside': dict(lines=LINES, files=[RB], report=REP_OUTSIDE),
    'report-after-subheading': dict(lines=LINES, files=[RB], report=REP_AFTER_SUB),
    'report-before-section': dict(lines=LINES, files=[RB], report=REP_BEFORE),
    'report-colon-opener': dict(lines=LINES, files=[RB], report=REP_COLON),
    'report-plain-opener': dict(lines=LINES, files=[RB], report=REP_PLAIN),
    'report-lowercase-opener': dict(lines=LINES, files=[RB], report=REP_LOWER),
    'report-second-writes': dict(lines=LINES, files=[RB], report=REP_TWO),
    'report-and-file-absent': dict(lines=LINES, files=[], report=REP_NO_HEADING),
    'report-no-word': dict(lines=[(GOAL, 'T01', 'ROLLBACK'), (GOAL, 'T01', DONE)], files=[], report=REP_OK),
    'report-home-spelling': dict(mode='home', lines=[(GOAL, 'T01', 'ROLLBACK @ROOT/.loop/' + GRB + ' sha256 aa'), (GOAL, 'T01', DONE)],
                                 files=['.loop/' + GRB], report=REP_HOME),
    'report-lh-spelling': dict(mode='lh', lines=[(GOAL, 'T01', 'ROLLBACK @ROOT/' + GRB + ' sha256 aa'), (GOAL, 'T01', DONE)], files=[GRB], report=REP_LH),
    'report-spelling-elsewhere': dict(lines=LINES, files=[RB], report=REP_ELSEWHERE),
    'report-unreadable': dict(lines=LINES, files=[RB], report=None, flag=True),
    'report-not-passed': dict(lines=LINES, files=[RB], report=REP_NO_SECTION, flag=False),
}


def build(ctx, name):
    c = CASES[name]
    mode = c.get('mode', 'plain')
    base = '%s/k07c4-fixtures/%s-%d' % (ctx['work'], name, time.time_ns())
    register(ctx['work'], MANIFEST, base)
    extra = {}
    root = base + '/pl'
    plan_dir = base + '/pl'
    plan_arg = True
    if mode == 'lh':
        root = base + '/lhome'
        extra['LOOP_HOME'] = root
    elif mode == 'home':
        root = base + '/hm'
        extra.update({'HOME': root, 'USERPROFILE': root, 'LOOP_HOME': root + '/.loop'})
    elif mode == 'defplan':
        root = base + '/lhome'
        extra['LOOP_HOME'] = root
        plan_dir = root + '/goals/' + GOAL
        root = plan_dir
        plan_arg = False
    os.makedirs(plan_dir, exist_ok=True)
    os.makedirs(base + '/log', exist_ok=True)
    os.makedirs(base + '/rep', exist_ok=True)
    plan = plan_dir + '/plan.md'
    write_text(plan, PLAN)
    log = base + '/log/steps.log'
    stamps = ''.join('- 2026-01-01T00:00:%02dZ %s %s %s\n' % (i, g, s, t.replace('@ROOT', root)) for i, (g, s, t) in enumerate(c['lines']))
    write_text(log, stamps)
    for rel in c['files']:
        os.makedirs(os.path.dirname(root + '/' + rel), exist_ok=True)
        write_text(root + '/' + rel, 'fixture rollback\n')
    report = base + '/rep/report.md'
    if c['report'] is not None:
        write_text(report, c['report'])
    args = ['--check', GOAL, '--file', log] + (['--plan', plan] if plan_arg else [])
    if c.get('flag', c['report'] is not None):
        args += ['--report', report]
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
    info_sha((('tests/rows/K07-C4/run.py', here + '/run.py'), ('tests/rows/K07-C4/rows.txt', here + '/rows.txt')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    return tally(load_rows(here + '/rows.txt'), {'check': row_check}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
