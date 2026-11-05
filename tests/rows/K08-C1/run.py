#!/usr/bin/env python3
"""K08-C1 rows runner: the usage-limit-cut exemption of the step-log tool's --check. A DISPATCH line with no return.md beside its card
is exempt from that one check, and prints a NOTE line, when an INCIDENT line of the goal names a run log (a), the run log's last
non-empty line says the account's usage limit was hit (b), the DISPATCH sits inside the run the INCIDENT names (c), no return word
of the same task follows it in that run (d) and only DISPATCH and ROLLBACK lines of the goal sit between it and the INCIDENT (e).

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k08c1-manifest.txt
  LOOP_PY          the interpreter the tool is run with (defaults to the one running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  check            the case named by arg is built under LOOP_WORK (plan, step log, run logs, return files; every goal id, task id and
                   path is constructed here) and LOOP_TREE/bin/loop_journal.py --check <goal> --file <log> --plan <plan> [--runs <dir>]
                   is run on it; expect is '<exit>:<tokens>', the exit code and the tokens (separated by ' ;; ') that must be in the
                   output, a token with a leading ! being one that must be absent
Prints PASS or FAIL per row with expected and actual (a failing row also shows the first bytes of the output, the work folder
masked), then rows=N pass=P fail=F. Nothing is spawned in the background.
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
MANIFEST = 'k08c1-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
G = 'K08-FIX'
OTH = 'K08-OTH'
LG = G + '.20260101T100000Z.log'
LG2 = G + '.20260101T103000Z.log'
OK = "You've hit your usage limit for the fixture account\n"
PLAN = '| id | what | owner | status |\n|---|---|---|---|\n| T01 | fixture change | writer | open |\n| T02 | fixture change | writer | open |\n'
W1 = 'evidence/T01/writer/card.md'
W1B = 'evidence/T01/writer/r2/card.md'
W2 = 'evidence/T02/writer/card.md'
R1 = 'evidence/T01/writer/return.md'
RB1 = 'ROLLBACK evidence/T01/writer/rollback.txt sha256 aa'
RB2 = 'ROLLBACK evidence/T02/writer/rollback.txt sha256 bb'
DIR = None  # a log value: the log's name is a folder, not a file


def e(step, text, ts=None, goal=G):
    """One step-log line of a case: step, text, an optional time of day (default 10:00:00 plus ten seconds per line), goal."""
    return (step, text, ts, goal)


START = e('GOAL', 'START fixture run')
D1 = e('T01', 'DISPATCH writer ' + W1)
D2 = e('T02', 'DISPATCH writer ' + W2)
B1 = e('T01', RB1)
B2 = e('T02', RB2)
INC = e('INCIDENT', 'usage-limit cut, run log ' + LG)
BASE = [START, D1, B1, INC]

# case: lines in order; logs: run log name -> content (a name given DIR is a folder); returns: return files saved (relative to the
# plan folder); runs: std (--runs <runs folder>), none (no --runs; the default folder), absent (--runs at a folder that does not
# exist), empty (--runs at an empty folder), novalue (--runs as the last word); logs_in: runs (the runs folder) or lhome (the
# default folder, LOOP_HOME/dispatch of the fixture); args: replaces the whole argument list
CASES = {
    # (a) the INCIDENT line
    'a-pass': dict(lines=BASE, logs={LG: OK}),
    'a-incident-text-form': dict(lines=[START, D1, B1, e('GOAL', 'INCIDENT usage-limit cut, run log ' + LG)], logs={LG: OK}),
    'a-numbered-form': dict(lines=[START, D1, B1, e('INCIDENT', 'usage-limit cut 2: run log ' + LG)], logs={LG: OK}),
    'a-no-incident': dict(lines=[START, D1, B1, e('T01', 'NOTE a later line of the goal')], logs={LG: OK}),
    'a-incident-other-words': dict(lines=[START, D1, B1, e('INCIDENT', 'rate error, run log ' + LG)], logs={LG: OK}),
    'a-incident-step-not-incident': dict(lines=[START, D1, B1, e('T01', 'usage-limit cut, run log ' + LG)], logs={LG: OK}),
    'a-incident-other-goal': dict(lines=[START, D1, B1, e('INCIDENT', 'usage-limit cut, run log ' + LG, goal=OTH)], logs={LG: OK}),
    'a-log-of-other-goal': dict(lines=[START, D1, B1, e('INCIDENT', 'usage-limit cut, run log ' + OTH + '.20260101T100000Z.log')],
                                logs={OTH + '.20260101T100000Z.log': OK}),
    'a-log-bad-stamp': dict(lines=[START, D1, B1, e('INCIDENT', 'usage-limit cut, run log ' + G + '.2026010T100000Z.log')],
                            logs={G + '.2026010T100000Z.log': OK}),
    'a-incident-names-no-log': dict(lines=[START, D1, B1, e('INCIDENT', 'usage-limit cut, no log is named here')], logs={LG: OK}),
    # (b) the run log
    'b-log-absent': dict(lines=BASE, logs={}),
    'b-runs-folder-absent': dict(lines=BASE, logs={LG: OK}, runs='absent'),
    'b-log-is-a-folder': dict(lines=BASE, logs={LG: DIR}),
    'b-last-line-other': dict(lines=BASE, logs={LG: 'finished normally\nall tasks done\n'}),
    'b-prefix-not-at-start': dict(lines=BASE, logs={LG: "Error: You've hit your usage limit\n"}),
    'b-no-limit-word': dict(lines=BASE, logs={LG: "You've hit your quota for the fixture account\n"}),
    'b-trailing-blank-lines': dict(lines=BASE, logs={LG: OK + '\n\n   \n'}),
    'b-surrounding-spaces': dict(lines=BASE, logs={LG: "   You've hit your limit   \n"}),
    'b-crlf-log': dict(lines=BASE, logs={LG: 'working\r\n' + OK.rstrip('\n') + '\r\n'}),
    'b-limit-line-not-last': dict(lines=BASE, logs={LG: OK + 'resuming later\n'}),
    'b-empty-log': dict(lines=BASE, logs={LG: ''}),
    # (c) the DISPATCH sits inside the run the INCIDENT names
    'c-start-after-incident': dict(lines=[e('T01', 'DISPATCH writer ' + W1), B1, INC, e('GOAL', 'START fixture run', '10:05:00')], logs={LG: OK}),
    'c-no-start-line': dict(lines=[D1, B1, INC], logs={LG: OK}),
    'c-after-next-start': dict(lines=[START, e('RESUME', 'START resumed', '10:30:00'), D1, B1, INC], logs={LG: OK}),
    'c-names-second-run': dict(lines=[START, e('RESUME', 'START resumed', '10:30:00'), D1, B1,
                                      e('INCIDENT', 'usage-limit cut, run log ' + LG2)], logs={LG2: OK}),
    'c-stamp-after-every-start': dict(lines=[e('GOAL', 'START fixture run', '09:59:00'), D1, B1, INC], logs={LG: OK}),
    'c-stamp-before-start': dict(lines=[e('GOAL', 'START fixture run', '10:00:30'), D1, B1, INC], logs={LG: OK}),
    'c-resume-start': dict(lines=[e('RESUME', 'START resumed'), D1, B1, INC], logs={LG: OK}),
    'c-start-wrong-step': dict(lines=[e('T01', 'START fixture'), D1, B1, INC], logs={LG: OK}),
    'c-dispatch-after-incident': dict(lines=[START, INC, D1, B1, e('T01', 'NOTE a later line of the goal')], logs={LG: OK}),
    'c-two-cuts': dict(lines=[START, D1, B1, INC, e('RESUME', 'START resumed', '10:30:00'), D2, B2, e('INCIDENT', 'usage-limit cut 2: run log ' + LG2)],
                       logs={LG: OK, LG2: OK}),
    'c-two-cuts-second-log-bad': dict(lines=[START, D1, B1, INC, e('RESUME', 'START resumed', '10:30:00'), D2, B2,
                                             e('INCIDENT', 'usage-limit cut 2: run log ' + LG2)], logs={LG: OK, LG2: 'finished normally\n'}),
    # (d) the role was in flight at the cut
    'd-return-after': dict(lines=[START, D1, B1, e('T01', 'RETURN ' + R1), INC], logs={LG: OK}),
    'd-done-after': dict(lines=[START, D1, B1, e('T01', 'DONE ' + R1), INC], logs={LG: OK}),
    'd-partial-after': dict(lines=[START, D1, B1, e('T01', 'PARTIAL ' + R1), INC], logs={LG: OK}),
    'd-fail-after': dict(lines=[START, D1, B1, e('T01', 'FAIL the role failed'), INC], logs={LG: OK}),
    'd-blocked-after': dict(lines=[START, D1, B1, e('T01', 'BLOCKED needs a decision'), INC], logs={LG: OK}),
    'd-return-of-other-task': dict(lines=[START, D1, B1, e('T02', 'RETURN evidence/T02/writer/return.md'), INC], logs={LG: OK}),
    'd-return-before-dispatch': dict(lines=[START, e('T01', 'RETURN ' + R1), D1, B1, INC], logs={LG: OK}),
    # (e) only DISPATCH and ROLLBACK lines of the goal between the DISPATCH and the INCIDENT
    'e-note-between': dict(lines=[START, D1, e('T01', 'NOTE something happened'), INC], logs={LG: OK}),
    'e-other-goal-between': dict(lines=[START, D1, e('T05', 'NOTE a line of another goal', goal=OTH), B1, INC], logs={LG: OK}),
    'e-two-dispatches-two-rollbacks': dict(lines=[START, D1, B1, D2, B2, INC], logs={LG: OK}),
    'e-pass-line-between': dict(lines=[START, D1, B1, e('T01', 'PASS verdict evidence/T01/review/verdict.md'), INC], logs={LG: OK}),
    'e-commit-between': dict(lines=[START, D1, e('GOAL', 'COMMIT fixture'), INC], logs={LG: OK}),
    'e-gap-between-two-dispatches': dict(lines=[START, D1, e('T01', 'NOTE something happened'), D2, INC], logs={LG: OK}),
    # the rest of the tool is unchanged
    'return-exists': dict(lines=BASE, logs={LG: OK}, returns=[R1]),
    'order-check-in-force': dict(lines=[START, D1, e('T01', 'DISPATCH writer ' + W1B), B1, INC], logs={LG: OK}),
    'no-card-word': dict(lines=[START, e('T01', 'DISPATCH writer the card is somewhere'), B1, INC], logs={LG: OK}),
    'last-line-exempt': dict(lines=[START, D1]),
    'cut-and-other-failure': dict(lines=[START, D1, B1, INC, D2, e('T02', 'NOTE a later line of the goal')], logs={LG: OK}),
    'default-runs-folder': dict(lines=BASE, logs={LG: OK}, runs='none', logs_in='lhome'),
    'default-runs-not-the-runs-folder': dict(lines=BASE, logs={LG: OK}, runs='none'),
    'runs-arg-overrides-default': dict(lines=BASE, logs={LG: OK}, runs='empty', logs_in='lhome'),
    'runs-no-value': dict(lines=BASE, logs={LG: OK}, runs='novalue'),
    'usage-line': dict(lines=BASE, args=['--check']),
}


def build(ctx, name):
    c = CASES[name]
    base = '%s/k08c1-fixtures/%s-%d' % (ctx['work'], name, time.time_ns())
    register(ctx['work'], MANIFEST, base)
    pl = base + '/pl'
    os.makedirs(pl, exist_ok=True)
    os.makedirs(base + '/log', exist_ok=True)
    extra = {}
    logs_dir = base + '/runs'
    if c.get('logs_in') == 'lhome':
        extra['LOOP_HOME'] = base + '/lhome'
        logs_dir = base + '/lhome/dispatch'
    os.makedirs(logs_dir, exist_ok=True)
    write_text(pl + '/plan.md', PLAN)
    log = base + '/log/steps.log'
    out = ''
    for i, (step, text, ts, goal) in enumerate(c['lines']):
        if ts is None:
            sec = i * 10
            ts = '10:%02d:%02d' % (sec // 60, sec % 60)
        out += '- 2026-01-01T%sZ %s %s %s\n' % (ts, goal, step, text)
        if text.startswith('ROLLBACK ') and text.split()[1].startswith('evidence/'):
            os.makedirs(os.path.dirname(pl + '/' + text.split()[1]), exist_ok=True)
            write_text(pl + '/' + text.split()[1], 'fixture rollback\n')
    write_text(log, out)
    for rel in c.get('returns', []):
        os.makedirs(os.path.dirname(pl + '/' + rel), exist_ok=True)
        write_text(pl + '/' + rel, 'fixture return\n')
    for lname, body in c.get('logs', {}).items():
        if body is DIR:
            os.makedirs(logs_dir + '/' + lname, exist_ok=True)
        else:
            with open(logs_dir + '/' + lname, 'w', encoding='utf-8', newline='') as fh:
                fh.write(body)
    if 'args' in c:
        return list(c['args']), extra
    args = ['--check', G, '--file', log, '--plan', pl + '/plan.md']
    runs = c.get('runs', 'std')
    if runs == 'std':
        args += ['--runs', base + '/runs']
    elif runs == 'absent':
        args += ['--runs', base + '/absent-runs']
    elif runs == 'empty':
        os.makedirs(base + '/empty-runs', exist_ok=True)
        args += ['--runs', base + '/empty-runs']
    elif runs == 'novalue':
        args += ['--runs']
    return args, extra


def row_check(ctx, rid, expect, arg):
    code, toks = expect.split(':', 1)
    args, extra = build(ctx, arg)
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_journal.py'] + args, capture_output=True, env=make_env(ctx['home'], extra, DROP),
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
    detail = 'expected=exit %s, tokens %s actual=exit %d, unmet %s, output bytes %d sha256 %s' % (
        code, toks, cp.returncode, ' | '.join(bad) or 'none', len(out.encode('utf-8')), sha(out))
    if not ok:
        detail += ' output=' + out.replace(ctx['work'], 'WORK').replace('\n', ' / ')[:400]
    return ok, detail


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K08-C1/run.py', here + '/run.py'), ('tests/rows/K08-C1/rows.txt', here + '/rows.txt')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    return tally(load_rows(here + '/rows.txt'), {'check': row_check}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
