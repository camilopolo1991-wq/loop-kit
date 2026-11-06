#!/usr/bin/env python3
"""K09-C1 rows runner: the DISPATCH refusal of the step-log tool's append form, and the resume step in the leader file and the preamble.
A DISPATCH write for a task is refused (exit 1, nothing appended) while that task's previous DISPATCH has no RETURN, DONE, PARTIAL, FAIL
or BLOCKED line after it, and the refusal prints the line number and the filled BLOCKED line.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k09c1-manifest.txt
  LOOP_PY          the interpreter the tool is run with (defaults to the one running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  append     the case named by arg is built (a step log of constructed lines) and LOOP_TREE/bin/loop_journal.py is run to write the
             case's attempt line with JOURNAL_FILE at that log; expect is '<exit>:<tokens>', the exit code and the comma separated
             tokens that must be in the output (a leading ! means absent). The log bytes must be unchanged after an exit 1 and grow by
             exactly one line after an exit 0.
  roundtrip  as append for the refusal, then the BLOCKED line the refusal printed is written by the tool (exit 0), the log's new last
             line must end with that printed line byte for byte, and the same attempt then exits 0.
  check      LOOP_TREE/bin/loop_journal.py --check on the case; expect is 'present' or 'absent' for the words second DISPATCH.
  text       arg is a sentence; it must be found as bytes in agents/loop-leader.md and in templates/GOAL_PREAMBLE.md (expect found).
Prints PASS or FAIL per row, then rows=N pass=P fail=F.
"""
import os
import re
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, register, sha, shafull, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py '
         '(no positional argument)')
MANIFEST = 'k09c1-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
G = 'K09-FIX'
O = 'K09-OTH'
W = 'evidence/T01/writer/card.md'
W2 = 'evidence/T01/writer/r2/card.md'
L1 = G + '.20260101T000000Z.log'
L2 = G + '.20260102T000000Z.log'
INC = 'usage-limit cut: run log %s ends on the account limit'
D1 = (G, 'T01', 'DISPATCH writer ' + W)
D2 = (G, 'T01', 'DISPATCH writer ' + W2)
CUT = (G, 'INCIDENT', INC % L1)
BLK = lambda log, card: (G, 'T01', 'BLOCKED leader record: cut by the usage limit, run log %s, card %s' % (log, card))
PLAN = '| id | what | owner | status |\n|---|---|---|---|\n| T01 | fixture change | writer | open |\n'

CASES = {
    'cut-open': dict(lines=[D1, CUT], attempt=D2),
    'cut-blocked': dict(lines=[D1, CUT, BLK(L1, W)], attempt=D2),
    'cut-no-incident': dict(lines=[D1], attempt=D2),
    'cut-incident-before': dict(lines=[(G, 'INCIDENT', INC % L1), D1], attempt=D2),
    'cut-two-incidents': dict(lines=[D1, (G, 'INCIDENT', INC % L1), (G, 'INCIDENT', 'usage-limit cut 2: run log %s ends on the limit' % L2)],
                              attempt=D2),
    'cut-incident-text-form': dict(lines=[D1, (G, 'NOTE', 'INCIDENT usage-limit cut: run log %s ends on the limit' % L1)], attempt=D2),
    'cut-other-incident-kind': dict(lines=[D1, (G, 'INCIDENT', 'window closed non-zero, run log ' + L1)], attempt=D2),
    'cut-no-card-word': dict(lines=[(G, 'T01', 'DISPATCH writer somewhere'), CUT], attempt=D2),
    'cut-incident-other-goal': dict(lines=[D1, (O, 'INCIDENT', 'usage-limit cut: run log %s.20260101T000000Z.log ends' % O)], attempt=D2),
    'returned': dict(lines=[D1, (G, 'T01', 'RETURN evidence/T01/writer/return.md')], attempt=D2),
    'done': dict(lines=[D1, (G, 'T01', 'DONE evidence/T01/writer/return.md')], attempt=D2),
    'partial': dict(lines=[D1, (G, 'T01', 'PARTIAL x')], attempt=D2),
    'failed': dict(lines=[D1, (G, 'T01', 'FAIL x')], attempt=D2),
    'blocked-plain': dict(lines=[D1, (G, 'T01', 'BLOCKED x')], attempt=D2),
    'note-only': dict(lines=[D1, (G, 'T01', 'NOTE only a note'), (G, 'T01', 'ROLLBACK evidence/T01/writer/rollback.txt sha256 aa')], attempt=D2),
    'other-task-closer': dict(lines=[D1, (G, 'T02', 'BLOCKED x')], attempt=D2),
    'other-goal-closer': dict(lines=[D1, (O, 'T01', 'BLOCKED x')], attempt=D2),
    'other-goal-dispatch': dict(lines=[(O, 'T01', 'DISPATCH writer ' + W)], attempt=D2),
    'first-dispatch': dict(lines=[(G, 'GOAL', 'START GOAL.md sha256 aa')], attempt=D1),
    'other-task-dispatch': dict(lines=[D1], attempt=(G, 'T02', 'DISPATCH writer evidence/T02/writer/card.md')),
    'third-after-closed-second': dict(lines=[D1, (G, 'T01', 'BLOCKED x'), D2], attempt=(G, 'T01', 'DISPATCH writer evidence/T01/writer/r3/card.md')),
    'open-then-note-step': dict(lines=[D1], attempt=(G, 'T01', 'NOTE a note while the dispatch is open')),
    'open-then-rollback-step': dict(lines=[D1], attempt=(G, 'T01', 'ROLLBACK evidence/T01/writer/rollback.txt sha256 aa')),
    'open-then-dispatch-step-not-task': dict(lines=[D1], attempt=(G, 'GOAL', 'DISPATCH writer ' + W2)),
    'chk-with-blocked': dict(lines=[D1, CUT, BLK(L1, W), D2], attempt=D2),
    'chk-without-blocked': dict(lines=[D1, CUT, D2], attempt=D2),
    'chk-third-unchanged': dict(lines=[D1, (G, 'T01', 'BLOCKED x'), D2, (G, 'T01', 'DISPATCH writer evidence/T01/writer/r3/card.md')], attempt=D2),
    'reviewer-after-open-writer': dict(lines=[D1, CUT], attempt=(G, 'T01', 'DISPATCH reviewer evidence/T01/review/card.md')),
}


def build(ctx, name):
    c = CASES[name]
    base = '%s/k09c1-fixtures/%s-%d' % (ctx['work'], name, time.time_ns())
    register(ctx['work'], MANIFEST, base)
    os.makedirs(base, exist_ok=True)
    log = base + '/steps.log'
    write_text(log, ''.join('- 2026-01-01T00:00:%02dZ %s %s %s\n' % (i, g, s, t) for i, (g, s, t) in enumerate(c['lines'])))
    return base, log, c


def run_tool(ctx, log, args):
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_journal.py'] + args, capture_output=True,
                        env=make_env(ctx['home'], {'JOURNAL_FILE': log}, DROP), cwd=ctx['work'], stdin=subprocess.DEVNULL)
    return cp.returncode, cp.stdout.decode('utf-8', 'replace').replace('\r', '') + cp.stderr.decode('utf-8', 'replace').replace('\r', '')


def tokens_bad(toks, out):
    bad = []
    for t in toks.split(','):
        if t.startswith('!'):
            if t[1:] in out:
                bad.append(t)
        elif t not in out:
            bad.append(t)
    return bad


def row_append(ctx, rid, expect, arg):
    code, toks = expect.split(':', 1)
    base, log, c = build(ctx, arg)
    before = read_bytes(log)
    g, s, t = c['attempt']
    rc, out = run_tool(ctx, log, [g, s, t])
    after = read_bytes(log)
    bad = tokens_bad(toks, out)
    grew = after[len(before):] if after.startswith(before) else None
    if rc == 0:
        bytes_ok = grew is not None and grew.count(b'\n') == 1 and grew.endswith(b'\n')
    else:
        bytes_ok = after == before
    ok = rc == int(code) and not bad and bytes_ok
    return ok, 'expected=exit %s, tokens %s actual=exit %d, unmet %s, log bytes %s, sha256 before %s after %s' % (
        code, toks, rc, ' '.join(bad) or 'none', 'as expected' if bytes_ok else 'WRONG', shafull(before)[:12], shafull(after)[:12])


def row_roundtrip(ctx, rid, expect, arg):
    base, log, c = build(ctx, arg)
    g, s, t = c['attempt']
    rc1, out1 = run_tool(ctx, log, [g, s, t])
    printed = [ln for ln in out1.split('\n') if ln.startswith(s + ' BLOCKED leader record: cut by the usage limit, run log ')]
    if rc1 != 1 or len(printed) != 1:
        return False, 'expected=refusal prints one BLOCKED line actual=exit %d, printed lines %d' % (rc1, len(printed))
    step, text = printed[0].split(' ', 1)
    rc2, out2 = run_tool(ctx, log, [g, step, text])
    last = read_bytes(log).split(b'\n')[-2]
    # the append mode pipes the line through loop_redact, which on a Windows host ends it CR LF (main does the same): set that CR aside
    tail = last.split(b' ', 3)[3].rstrip(b'\r') if last.count(b' ') >= 3 else b''
    equal = tail == printed[0].encode('utf-8')
    rc3, out3 = run_tool(ctx, log, [g, s, t])
    ok = rc2 == 0 and equal and rc3 == 0
    return ok, 'expected=refused, printed line appended (exit 0, bytes equal), then the DISPATCH exits 0 actual=refusal exit %d, append exit %d, bytes equal %s, dispatch exit %d' % (
        rc1, rc2, equal, rc3)


def row_check(ctx, rid, expect, arg):
    base, log, c = build(ctx, arg)
    plan = base + '/plan.md'
    write_text(plan, PLAN)
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_journal.py', '--check', G, '--file', log, '--plan', plan], capture_output=True,
                        env=make_env(ctx['home'], {}, DROP), cwd=ctx['work'], stdin=subprocess.DEVNULL)
    out = cp.stdout.decode('utf-8', 'replace')
    present = 'second DISPATCH' in out
    return present == (expect == 'present'), 'expected=second DISPATCH %s actual=%s, exit %d' % (expect, 'present' if present else 'absent', cp.returncode)


def row_text(ctx, rid, expect, arg):
    b = arg.encode('utf-8')
    files = ('agents/loop-leader.md', 'templates/GOAL_PREAMBLE.md')
    got = [(f, (read_bytes(ctx['tree'] + '/' + f) or b'').count(b)) for f in files]
    ok = all(n == 1 for f, n in got)
    return ok, 'expected=the sentence once in each of two files actual=%s sentence sha256 %s' % (
        ', '.join('%s:%d' % (f, n) for f, n in got), shafull(b)[:12])


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K09-C1/run.py', here + '/run.py'), ('tests/rows/K09-C1/rows.txt', here + '/rows.txt')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    return tally(load_rows(here + '/rows.txt'), {'append': row_append, 'roundtrip': row_roundtrip, 'check': row_check, 'text': row_text},
                 (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
