#!/usr/bin/env python3
"""K11-C2 rows runner: tripwire PEER-NOISE for the shared loop-home files and OWNER-NOISE for Downloads
(bin/loop_tripwire.py start <GOAL> <window> [--peers <ids>], then check).

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test (its bin/loop_tripwire.py is what runs)
  LOOP_ROWS_HOME   the folder every throwaway home is made under (k11c2-fixtures/<tag>-<ns>/home)
  LOOP_WORK        the work folder; the manifest k11c2-manifest.txt listing every world is kept here
  LOOP_PY          the interpreter every child is run with (defaults to the one running this file)

Fixtures. Every world is built by this file: a throwaway home with a constructed loop home (config.env, two goal folders FIX-01
as the window's goal A and FIX-02 as the listed peer B, current/, dispatch/, current_goal holding A, a report.log with one old
line, sent/ with one old copy, report.log.lock) and a throwaway Downloads folder with one old file. Every child gets HOME,
USERPROFILE and LOOP_HOME at the world's own home and PYTHONDONTWRITEBYTECODE=1. The live home is never named or read.

What B does (peer_activity): the dispatch of B writes current/FIX-02, dispatch/FIX-02.<ts>.log and current_goal (its id), and the
report of B appends a report.log line labelled FIX-02 stamped now, touches report.log.lock and writes sent/<sha256>.md for the
sha ending that line.
"""
import datetime
import hashlib
import os
import re
import subprocess
import sys
import time
HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.dirname(HERE)
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, remove_path, tally, write_text

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py (no positional argument)'
MANIFEST = 'k11c2-manifest.txt'
DROP = ('LOOP_GOAL', 'HERMES_HOME', 'CLAUDE_BIN', 'LOOP_CLAUDE_BIN', 'MAX_LEADERS', 'REPORT_SEND_CMD', 'JOURNAL_FILE', 'LOOP_GUARD_MODE',
        'LOOP_PY', 'ENGINE_RECORD_DIR', 'RECORD_BRANCH', 'KIT_DIR', 'KIT_BRANCH', 'STATE_FILE', 'EXPORT_DIR', 'WRITABLE_TREES', 'SURFACES',
        'TRIPWIRE_NOISE', 'N8N_DB')
A, B = 'FIX-01', 'FIX-02'
ST = {}
USERPATH = re.compile(r'(?i)(?:[A-Za-z]:)?[\\/]+users[\\/]+[^\\/\s\'"]+')


def hide(ctx, s):
    # the interpreter and the folders sit under the real user folder, a real name: cut first, in forward, backward and doubled spelling
    for p, repl in ((ctx['py'], '<py>'), (ctx['home'], '<rows-home>'), (ctx['work'], '<work>'),
                    (fwd(os.path.expanduser('~')), '~'), (os.path.expanduser('~'), '~')):
        s = s.replace(p, repl).replace(p.replace('/', '\\'), repl).replace(p.replace('/', '\\\\'), repl)
    return USERPATH.sub('~', s)


def now_z():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def clean_prior_worlds(ctx):
    """Remove the worlds an earlier run listed in its manifest (only paths under LOOP_ROWS_HOME/k11c2-fixtures/)."""
    mf = ctx['work'] + '/' + MANIFEST
    data = read_bytes(mf)
    n = 0
    if data is not None:
        for p in data.decode('utf-8', 'replace').split('\n'):
            p = p.strip()
            if p and fwd(p).startswith(ctx['home'] + '/k11c2-fixtures/') and os.path.exists(p):
                remove_path(p)
                n += 1
        os.remove(mf)
    print('cleaned %d path(s) listed by an earlier run' % n)


class World:
    """A throwaway home with a constructed loop home, two goal folders and a Downloads folder."""

    def __init__(self, ctx, tag):
        self.ctx = ctx
        self.base = '%s/k11c2-fixtures/%s-%d' % (ctx['home'], tag, time.time_ns())
        os.makedirs(self.base + '/tmp')
        with open(ctx['work'] + '/' + MANIFEST, 'a', encoding='utf-8') as fh:
            fh.write(self.base + '\n')
        self.home = self.base + '/home'
        self.lh = self.home + '/.loop'
        for d in ('current', 'dispatch', 'sent'):
            os.makedirs(self.lh + '/' + d, exist_ok=True)
        os.makedirs(self.home + '/Downloads')
        write_text(self.home + '/Downloads/old.bin', 'an old download\n')
        write_text(self.lh + '/config.env', 'RECORD_BRANCH=record\n')
        for g in (A, B):
            gd = '%s/goals/%s' % (self.lh, g)
            os.makedirs(gd + '/evidence/T01/writer')
            write_text(gd + '/GOAL.md', '# %s: constructed fixture goal\n' % g)
            write_text(gd + '/plan.md', '# plan\n| ID | Task | Owner | Status |\n|----|------|-------|--------|\n| T01 | fixture | writer | PASS |\n')
            write_text(gd + '/evidence/T01/writer/rollback.txt', 'fixture rollback\n')
        write_text(self.lh + '/current/' + A, A + '\n')
        write_text(self.lh + '/current_goal', A + '\n')
        old = hashlib.sha256(b'an old report\n').hexdigest()
        write_text(self.lh + '/report.log', '2026-01-01T00:00:00Z SENT %s %s/goals/%s/report.md sha256 %s\n' % (A, self.lh, A, old))
        write_text(self.lh + '/report.log.lock', '')
        write_text('%s/sent/%s.md' % (self.lh, old), 'an old report\n')

    def env(self):
        drop = DROP + tuple(k for k in os.environ if k.startswith('LOOP_TRIPWIRE_'))
        return make_env(self.home, {'TEMP': self.base + '/tmp', 'TMP': self.base + '/tmp'}, drop)

    def tw(self, *args):
        """loop_tripwire.py with args in this world's home: (exit, stdout lines, stderr text)."""
        cp = subprocess.run([self.ctx['py'], self.ctx['tree'] + '/bin/loop_tripwire.py'] + list(args), capture_output=True, env=self.env(),
                            cwd=self.base, stdin=subprocess.DEVNULL, timeout=300)
        out = cp.stdout.decode('utf-8', 'replace').replace('\r', '')
        return cp.returncode, [x for x in out.split('\n') if x.strip()], cp.stderr.decode('utf-8', 'replace').replace('\r', '')

    def diff_text(self, window, goal=A):
        b = read_bytes('%s/goals/%s/evidence/%s/diff-latest.txt' % (self.lh, goal, window))
        return '' if b is None else b.decode('utf-8', 'replace').replace('\r', '')

    def report_line(self, gid, text):
        """The report of gid: one report.log line stamped now, the lock touched, the copy written under sent/."""
        sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
        with open(self.lh + '/report.log', 'a', encoding='utf-8', newline='\n') as fh:
            fh.write('%s SENT %s %s/goals/%s/report.md sha256 %s\n' % (now_z(), gid, self.lh, gid, sha))
        with open(self.lh + '/report.log.lock', 'ab') as fh:
            fh.write(b'')
        os.utime(self.lh + '/report.log.lock', None)
        write_text('%s/sent/%s.md' % (self.lh, sha), text)
        return sha

    def peer_activity(self, gid=B):
        time.sleep(0.05)
        write_text('%s/current/%s' % (self.lh, gid), gid + '\n')
        write_text('%s/dispatch/%s.20260101T000100Z.log' % (self.lh, gid), 'peer dispatch log\n')
        write_text(self.lh + '/current_goal', gid + '\n')
        self.report_line(gid, 'a report of %s\n' % gid)


def kinds_of(lines):
    return sorted({re.sub(r' x\d+$', '', x.split(' ', 2)[2]) for x in lines if x.startswith('PEER-NOISE ') and len(x.split(' ', 2)) == 3})


def say(ctx, lines, n=6):
    return ' | '.join(hide(ctx, x)[:100] for x in lines[:n]) or 'no stdout'


# ---------------------------------------------------------------- rows
def peer_world(ctx):
    if 'peer' in ST:
        return ST['peer']
    w = World(ctx, 'peer')
    s_rc, s_out, _ = w.tw('start', A, 'w-peer', '--peers', B)
    cg0 = read_bytes(w.lh + '/current_goal')
    w.peer_activity(B)
    pre = (read_bytes(w.lh + '/current_goal') != cg0, len(read_bytes(w.lh + '/report.log').split(b'\n')) == 3, len(os.listdir(w.lh + '/sent')) == 2)
    rc, out, err = w.tw('check', A, 'w-peer')
    ST['peer'] = (w, s_rc, s_out, rc, out, err, pre)
    return ST['peer']


def peer_row(ctx):
    w, s_rc, s_out, rc, out, err, pre = peer_world(ctx)
    kinds = kinds_of(out)
    need = ['shared current_goal', 'shared report.log', 'shared report.log.lock', 'shared sent/']
    named = bool(out) and all(x.startswith('PEER-NOISE %s ' % B) for x in out)
    dt = w.diff_text('w-peer')
    ok = s_rc == 0 and all(pre) and rc == 0 and named and all(k in kinds for k in need) and 'DIFFERENCES (0):' in dt
    return ok, ('precondition, B changed current_goal %s, appended its report.log line %s, wrote its sent copy %s; start --peers %s exit %d; check exit %d, '
                '%d stdout line(s), all PEER-NOISE %s %s; shared kinds %s; diff-latest "DIFFERENCES (0)" %s; stdout [%s]; stderr %s bytes' % (
                    *pre, B, s_rc, rc, len(out), B, '(yes)' if named else '(NO)', [k for k in kinds if k.startswith('shared')],
                    'DIFFERENCES (0):' in dt, say(ctx, out), len(err)))


def owner_row(ctx):
    w = World(ctx, 'owner')
    s_rc, _, _ = w.tw('start', A, 'w-own')
    z_rc, z_out, _ = w.tw('check', A, 'w-own')                        # control: nothing changed reads clean
    write_text(w.home + '/Downloads/new.bin', 'a new download\n')
    rc, out, err = w.tw('check', A, 'w-own')
    lines = [x for x in out if x.startswith('OWNER-NOISE ')]
    ok = (s_rc == 0 and z_rc == 0 and z_out == ['no differences'] and rc == 0 and len(lines) == 1 and len(out) == 1
          and 'Downloads' in lines[0] and 'DIFFERENCES (0):' in w.diff_text('w-own'))
    return ok, ('control before the file, check exit %d [%s]; after adding Downloads/new.bin check exit %d, %d OWNER-NOISE line(s) of %d stdout line(s) [%s]; '
                'stderr %s bytes' % (z_rc, say(ctx, z_out), rc, len(lines), len(out), say(ctx, out), len(err)))


def control_row(ctx):
    w, s_rc, s_out, rc0, out0, err0, pre = peer_world(ctx)
    write_text('%s/goals/%s/planted.txt' % (w.lh, A), 'a planted file under the window goal\n')
    rc, out, err = w.tw('check', A, 'w-peer')
    dt = w.diff_text('w-peer')
    file_lines = [x for x in out if x.startswith('FILE ') and 'planted.txt' in x]
    still = any(x.startswith('PEER-NOISE %s ' % B) for x in out)
    ok = rc0 == 0 and rc == 1 and len(file_lines) == 1 and still and not any(x.startswith('PEER-NOISE') and 'planted' in x for x in out) and 'planted.txt' in dt
    return ok, ('same window and baseline: the check before the plant exited %d; after planting goals/%s/planted.txt the check exited %d, FILE difference '
                'lines naming it %d, PEER-NOISE %s lines still printed %s; first stdout lines [%s]' % (rc0, A, rc, len(file_lines), B, still, say(ctx, out, 3)))


def stranger_row(ctx):
    w = World(ctx, 'stranger')
    s1, _, _ = w.tw('start', A, 'w-cg', '--peers', B)
    time.sleep(0.05)
    write_text(w.lh + '/current_goal', A + '\n')
    write_text(w.lh + '/current/' + B, B + '\n')                      # B's dispatch file moved, but current_goal names A: no trace of B
    r1, o1, _ = w.tw('check', A, 'w-cg')
    f1 = [x for x in o1 if x.startswith('FILE ') and x[5:].replace('\\', '/').rstrip().split(': ', 1)[0].endswith('/.loop/current_goal')]
    s2, _, _ = w.tw('start', A, 'w-rep', '--peers', B)
    w.report_line(A, 'a report of A\n')                                 # A's own report: not a peer's
    r2, o2, _ = w.tw('check', A, 'w-rep')
    f2 = [x for x in o2 if x.startswith('FILE ') and x[5:].replace('\\', '/').split(': ', 1)[0].endswith('/.loop/report.log')]
    n2 = [x for x in o2 if x.startswith('PEER-NOISE') and 'shared' in x]
    ok = s1 == 0 and r1 == 1 and len(f1) == 1 and s2 == 0 and r2 == 1 and len(f2) == 1 and not n2
    return ok, ('current_goal holding %s, peer %s: exit %d, FILE current_goal lines %d; a report.log line labelled %s in a fresh window: exit %d, FILE '
                'report.log lines %d, PEER-NOISE shared lines %d' % (A, B, r1, len(f1), A, r2, len(f2), len(n2)))


CHECKS = {'peer': peer_row, 'owner': owner_row, 'control': control_row, 'stranger': stranger_row}


def row_check(ctx, rid, expect, arg):
    ok, detail = CHECKS[arg](ctx)
    return ok, 'expected [%s] measured: %s' % (expect, hide(ctx, detail))


def main():
    tree, home, work = env_dirs(USAGE)
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    clean_prior_worlds(ctx)
    info_sha((('tests/rows/K11-C2/run.py', HERE + '/run.py'), ('tests/rows/K11-C2/rows.txt', HERE + '/rows.txt'),
              ('bin/loop_tripwire.py', tree + '/bin/loop_tripwire.py')))
    print('info worlds are constructed homes under the rows home, never a clone of a real one')
    return tally(load_rows(HERE + '/rows.txt'), {'check': row_check}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
