#!/usr/bin/env python3
"""K10-C5 rows runner: tripwire peers (bin/loop_tripwire.py start <GOAL> <window> --peers <ids>).

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test (its bin/loop_tripwire.py is what runs)
  LOOP_ROWS_HOME   unused here (every world has its own throwaway home under LOOP_WORK); required by the shape of the runners
  LOOP_WORK        the work folder; every fixture is written under it and listed in k10c5-manifest.txt
  LOOP_PY          the interpreter every child is run with (defaults to the one running this file)

Fixtures. Every world is built by this file under LOOP_WORK: a throwaway home, a constructed record repository (branch record) and
three constructed goal folders: FIX-01 (the window's goal, A), FIX-02 (the peer, B) and FIX-03 (C, not named as a peer). The commit
identity is a placeholder passed by the environment. Every child gets HOME, USERPROFILE and LOOP_HOME at the world's own home and
PYTHONDONTWRITEBYTECODE=1 (make_env). The live home is never named, and no real repository is read or written.

What B does (peer_activity): appends a step-log line, edits its own `### FIX-02` subsection of docs/STATE.md, makes its own record
worktree under work/FIX-02/record on branch rec-fix-02 and commits there, commits the step log and state file on the record branch with
a `Goal: FIX-02` trailer, edits its subsection again (left uncommitted), edits its plan, writes its current file and its dispatch log
and prompt. The fewest windows that still show each control: one world per row, one window per reading, two readings of one window
for the PEER and CONTROL rows (the second after the planted file).
"""
import os
import re
import subprocess
import sys
import time
HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.dirname(HERE)
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, register, tally, write_text

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py (no positional argument)'
MANIFEST = 'k10c5-manifest.txt'
DROP = ('LOOP_GOAL', 'HERMES_HOME', 'CLAUDE_BIN', 'LOOP_CLAUDE_BIN', 'MAX_LEADERS', 'REPORT_SEND_CMD', 'JOURNAL_FILE', 'LOOP_GUARD_MODE',
        'LOOP_PY', 'ENGINE_RECORD_DIR', 'RECORD_BRANCH', 'KIT_DIR', 'KIT_BRANCH', 'STATE_FILE', 'EXPORT_DIR', 'WRITABLE_TREES', 'SURFACES',
        'TRIPWIRE_NOISE', 'N8N_DB')
GITENV = {'GIT_AUTHOR_NAME': 'Omicron Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid', 'GIT_COMMITTER_NAME': 'Omicron Fixture',
          'GIT_COMMITTER_EMAIL': 'fixture@example.invalid', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_TERMINAL_PROMPT': '0'}
A, B, C = 'FIX-01', 'FIX-02', 'FIX-03'
ST = {}
USERPATH = re.compile(r'(?i)(?:[A-Za-z]:)?[\\/]+users[\\/]+[^\\/\s\'"]+')


def hide(ctx, s):
    # the interpreter and the work folder sit under the real user folder, a real name: cut first, in forward, backward and doubled spelling
    for p, repl in ((ctx['py'], '<py>'), (ctx['work'], '<work>'), (fwd(os.path.expanduser('~')), '~'), (os.path.expanduser('~'), '~')):
        s = s.replace(p, repl).replace(p.replace('/', '\\'), repl).replace(p.replace('/', '\\\\'), repl)
    return USERPATH.sub('~', s)


class World:
    """A throwaway home with a constructed record repository and three goal folders."""

    def __init__(self, ctx, tag):
        self.ctx = ctx
        self.base = '%s/k10c5-fixtures/%s-%d' % (ctx['work'], tag, time.time_ns())
        register(ctx['work'], MANIFEST, self.base)
        self.home = self.base + '/home'
        self.lh = self.home + '/.loop'
        self.rec = self.base + '/record'
        os.makedirs(self.base + '/tmp', exist_ok=True)
        for d in ('current', 'dispatch', 'work'):
            os.makedirs(self.lh + '/' + d, exist_ok=True)
        write_text(self.lh + '/config.env', 'ENGINE_RECORD_DIR=%s\nRECORD_BRANCH=record\n' % self.rec)
        for g in (A, B, C):
            gd = '%s/goals/%s' % (self.lh, g)
            os.makedirs(gd + '/evidence/T01/writer')
            write_text(gd + '/GOAL.md', '# %s: constructed fixture goal\nAuthority: the record repository on its record branch only.\n' % g)
            write_text(gd + '/plan.md', '# plan\n| ID | Task | Owner | Status |\n|----|------|-------|--------|\n| T01 | fixture | writer | PASS |\n')
            write_text(gd + '/evidence/T01/writer/rollback.txt', 'fixture rollback\n')
        write_text(self.lh + '/current/' + A, 'fixture current file\n')
        os.makedirs(self.rec)
        for args in (['init', '-q', '-b', 'record'], ['config', 'core.autocrlf', 'false']):
            self.must(self.rec, *args)
        write_text(self.rec + '/.gitattributes', '* text eol=lf\n')
        os.makedirs(self.rec + '/docs')
        write_text(self.rec + '/docs/JOURNAL.md', '# step log fixture\n- 2026-01-01T00:00:00Z FIX-00 GOAL START fixture\n')
        write_text(self.rec + '/docs/STATE.md', '# STATE fixture\n## 5. Running goals\n' + ''.join('### %s\n- none\n' % g for g in (A, B, C)))
        write_text(self.rec + '/docs/NOTES.md', 'alpha\n')
        self.must(self.rec, 'add', '-A')
        self.must(self.rec, 'commit', '-q', '-m', 'chore(fixture): initial')

    def env(self, extra=None):
        drop = DROP + tuple(k for k in os.environ if k.startswith('LOOP_TRIPWIRE_'))
        e = dict(GITENV, TEMP=self.base + '/tmp', TMP=self.base + '/tmp')
        e.update(extra or {})
        return make_env(self.home, e, drop)

    def git(self, cwd, *args):
        cp = subprocess.run(['git'] + list(args), cwd=cwd, capture_output=True, env=self.env(), stdin=subprocess.DEVNULL, timeout=120)
        return cp.returncode, (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '').strip()

    def must(self, cwd, *args):
        rc, out = self.git(cwd, *args)
        assert rc == 0, out

    def tw(self, *args):
        """loop_tripwire.py with args in this world's home: (exit, stdout lines, stderr text)."""
        cp = subprocess.run([self.ctx['py'], self.ctx['tree'] + '/bin/loop_tripwire.py'] + list(args), capture_output=True, env=self.env(),
                            cwd=self.base, stdin=subprocess.DEVNULL, timeout=300)
        out = cp.stdout.decode('utf-8', 'replace').replace('\r', '')
        return cp.returncode, [x for x in out.split('\n') if x.strip()], cp.stderr.decode('utf-8', 'replace').replace('\r', '')

    def tip(self, ref='HEAD'):
        return self.git(self.rec, 'rev-parse', ref)[1]

    def diff_text(self, window, goal=A):
        b = read_bytes('%s/goals/%s/evidence/%s/diff-latest.txt' % (self.lh, goal, window))
        return '' if b is None else b.decode('utf-8', 'replace').replace('\r', '')

    def state_edit(self, gid, old, new):
        p = self.rec + '/docs/STATE.md'
        s = (read_bytes(p) or b'').decode('utf-8')
        assert '### %s\n%s' % (gid, old) in s
        write_text(p, s.replace('### %s\n%s' % (gid, old), '### %s\n%s' % (gid, new), 1))

    def commit_record(self, subject, trailer):
        """Add the step log and state file on the record branch's work tree and commit them; trailer is the final paragraph or None."""
        self.must(self.rec, 'add', '--', 'docs/JOURNAL.md', 'docs/STATE.md')
        args = ['commit', '-q', '-m', subject] + (['-m', trailer] if trailer else [])
        self.must(self.rec, *args)

    def peer_activity(self, gid=B):
        low = gid.lower()
        with open(self.rec + '/docs/JOURNAL.md', 'a', encoding='utf-8', newline='\n') as fh:
            fh.write('- 2026-01-01T00:01:00Z %s T01 NOTE written by the peer\n' % gid)
        self.state_edit(gid, '- none\n', '- step one\n')
        wtp = '%s/work/%s/record' % (self.lh, gid)
        self.must(self.rec, 'worktree', 'add', '-q', '-b', 'rec-' + low, wtp, 'record')
        write_text(wtp + '/docs/note-%s.md' % low, 'note of %s\n' % gid)
        self.must(wtp, 'add', '--', 'docs/note-%s.md' % low)
        self.must(wtp, 'commit', '-q', '-m', 'docs(record): note of %s' % low, '-m', 'Goal: ' + gid)
        self.commit_record('chore(record): step log and state of %s' % low, 'Goal: ' + gid)
        self.state_edit(gid, '- step one\n', '- step one\n- step two\n')
        pp = '%s/goals/%s/plan.md' % (self.lh, gid)
        write_text(pp, (read_bytes(pp) or b'').decode('utf-8') + '| T02 | peer edit | writer | OPEN |\n')
        write_text('%s/current/%s' % (self.lh, gid), 'peer current file\n')
        write_text('%s/dispatch/%s.20260101T000100Z.log' % (self.lh, gid), 'peer dispatch log\n')
        write_text('%s/dispatch/%s.prompt' % (self.lh, gid), 'Run goal %s\n' % gid)


def lines_kinds(lines):
    return sorted({re.sub(r' x\d+$', '', x.split(' ', 2)[2]) for x in lines if x.startswith('PEER-NOISE ') and len(x.split(' ', 2)) == 3})


def say(ctx, rc, lines, n=3):
    return '; '.join(hide(ctx, x)[:110] for x in lines[:n]) or 'no stdout'


# ---------------------------------------------------------------- rows
def peer_world(ctx):
    if 'peer' in ST:
        return ST['peer']
    w = World(ctx, 'peer')
    s_rc, s_out, s_err = w.tw('start', A, 'w-peer', '--peers', B)
    tip0, plan0 = w.tip('record'), read_bytes('%s/goals/%s/plan.md' % (w.lh, B))
    w.peer_activity(B)
    pre = (w.tip('record') != tip0, w.git(w.rec, 'rev-parse', '--verify', '-q', 'rec-fix-02')[0] == 0,
           read_bytes('%s/goals/%s/plan.md' % (w.lh, B)) != plan0, os.path.isfile('%s/current/%s' % (w.lh, B)))
    rc, out, err = w.tw('check', A, 'w-peer')
    ST['peer'] = (w, s_rc, s_out, s_err, rc, out, err, pre)
    return ST['peer']


def peer_row(ctx):
    w, s_rc, s_out, s_err, rc, out, err, pre = peer_world(ctx)
    kinds = lines_kinds(out)
    need = ['STATE.md lines of its subsection', 'commits with its Goal trailer', 'current file', 'dispatch log or prompt', 'git tree',
            'goal folder', 'own branch', 'work folder']
    dt = w.diff_text('w-peer')
    ok = (s_rc == 0 and 'peers: %s' % B in ' '.join(s_out) and all(pre) and rc == 0 and out and all(x.startswith('PEER-NOISE %s ' % B) for x in out)
          and all(k in kinds for k in need) and 'DIFFERENCES (0):' in dt and C not in dt)
    return ok, ('precondition, B moved the record tip %s, made rec-fix-02 %s, changed its plan %s, wrote its current file %s; start --peers %s exit %d; '
                'check exit %d with %d stdout line(s), all PEER-NOISE %s %s; kinds %s; diff-latest "DIFFERENCES (0)" %s and no mention of the '
                'unnamed goal %s; stderr %s bytes' % (
                    *pre, B, s_rc, rc, len(out), B, '(yes)' if out and all(x.startswith('PEER-NOISE %s ' % B) for x in out) else '(NO)', kinds,
                    'DIFFERENCES (0):' in dt, C not in dt, len(err)))


def control_row(ctx):
    w, s_rc, s_out, s_err, rc0, out0, err0, pre = peer_world(ctx)
    write_text('%s/goals/%s/planted.txt' % (w.lh, A), 'a planted file under the window goal\n')
    rc, out, err = w.tw('check', A, 'w-peer')
    dt = w.diff_text('w-peer')
    file_lines = [x for x in out if x.startswith('FILE ') and 'planted.txt' in x]
    ok = (rc0 == 0 and rc == 1 and len(file_lines) == 1 and any(x.startswith('PEER-NOISE %s ' % B) for x in out)
          and not any(x.startswith('PEER-NOISE') and 'planted' in x for x in out) and 'planted.txt' in dt)
    return ok, ('same window and baseline: the check before the plant exited %d; after planting goals/%s/planted.txt the check exited %d, '
                'FILE difference lines naming it %d, PEER-NOISE %s lines still printed %s; first stdout lines [%s]' % (
                    rc0, A, rc, len(file_lines), B, any(x.startswith('PEER-NOISE %s ' % B) for x in out), say(ctx, rc, out)))


def trailer_row(ctx):
    w = World(ctx, 'trailer')
    c_rc, c_out, _ = w.tw('start', A, 'w-ctl', '--peers', B)
    z_rc, z_out, _ = w.tw('check', A, 'w-ctl')                      # control: no change reads clean, so a verdict here can fail
    s1, _, _ = w.tw('start', A, 'w-other', '--peers', B)
    write_text(w.rec + '/docs/NOTES.md', 'beta\n')
    w.must(w.rec, 'add', '--', 'docs/NOTES.md')
    w.must(w.rec, 'commit', '-q', '-m', 'docs(record): note by C', '-m', 'Goal: ' + C)
    r1, o1, _ = w.tw('check', A, 'w-other')
    s2, _, _ = w.tw('start', A, 'w-none', '--peers', B)
    write_text(w.rec + '/docs/NOTES.md', 'gamma\n')
    w.must(w.rec, 'add', '--', 'docs/NOTES.md')
    w.must(w.rec, 'commit', '-q', '-m', 'docs(record): note with no trailer')
    r2, o2, _ = w.tw('check', A, 'w-none')
    g1 = [x for x in o1 if x.startswith('GIT ') and 'HEAD' in x]
    g2 = [x for x in o2 if x.startswith('GIT ') and 'HEAD' in x]
    ok = (c_rc == 0 and z_rc == 0 and z_out == ['no differences'] and s1 == 0 and r1 == 1 and len(g1) == 1 and s2 == 0 and r2 == 1 and len(g2) == 1
          and not any('commits with its Goal trailer' in x for x in o1 + o2))
    return ok, ('control, a window with no change: check exit %d [%s]; commit on the record branch with Goal: %s while the peer is %s: exit %d, '
                'GIT HEAD difference lines %d, no PEER-NOISE commits line %s; a commit with no trailer, in a fresh window: exit %d, GIT HEAD '
                'difference lines %d' % (z_rc, say(ctx, z_rc, z_out), C, B, r1, len(g1), not any('commits with' in x for x in o1), r2, len(g2)))


def stranger_row(ctx):
    w = World(ctx, 'stranger')
    s1, _, _ = w.tw('start', A, 'w-cur', '--peers', B)
    write_text('%s/current/%s' % (w.lh, C), 'a current file of a goal that is not a peer\n')
    r1, o1, _ = w.tw('check', A, 'w-cur')
    f1 = [x for x in o1 if x.startswith('FILE ') and ('/current/%s' % C) in x.replace('\\', '/')]
    s2, _, _ = w.tw('start', A, 'w-own', '--peers', B)
    w.state_edit(A, '- none\n', '- own edit\n')
    r2, o2, _ = w.tw('check', A, 'w-own')
    g2 = [x for x in o2 if x.startswith('GIT ') and 'status' in x]
    ok = (s1 == 0 and r1 == 1 and len(f1) == 1 and not any(x.startswith('PEER-NOISE') and C in x for x in o1)
          and s2 == 0 and r2 == 1 and len(g2) == 1 and not any(x.startswith('PEER-NOISE') for x in o2))
    return ok, ('peer is %s: a current file of %s: exit %d, FILE difference lines %d, PEER-NOISE naming it %s; an uncommitted edit of A\'s own STATE.md '
                'subsection, fresh window: exit %d, GIT status difference lines %d, any PEER-NOISE line %s' % (
                    B, C, r1, len(f1), any(x.startswith('PEER-NOISE') and C in x for x in o1), r2, len(g2), any(x.startswith('PEER-NOISE') for x in o2)))


def nopeers_row(ctx):
    w = World(ctx, 'nopeers')
    s_rc, s_out, _ = w.tw('start', A, 'w-none')
    bj = (read_bytes('%s/goals/%s/evidence/w-none/baseline.json' % (w.lh, A)) or b'').decode('utf-8', 'replace')
    w.peer_activity(B)
    rc, out, err = w.tw('check', A, 'w-none')
    diffs = [x for x in out if x.startswith('FILE ') or x.startswith('GIT ')]
    ok = s_rc == 0 and bj != '' and '"peers"' not in bj and rc == 1 and len(diffs) >= 5 and not any('PEER-NOISE' in x for x in out)
    return ok, ('no --peers: start exit %d, baseline has a peers key %s; the same activity of %s: check exit %d, %d FILE or GIT difference line(s) on '
                'stdout, PEER-NOISE lines %d' % (s_rc, '"peers"' in bj, B, rc, len(diffs), sum('PEER-NOISE' in x for x in out)))


def badpeer_row(ctx):
    w = World(ctx, 'badpeer')
    r1, _, e1 = w.tw('start', A, 'w-own', '--peers', A)
    r2, _, e2 = w.tw('start', A, 'w-bad', '--peers', 'bad/id')
    none = [not os.path.exists('%s/goals/%s/evidence/%s/baseline.json' % (w.lh, A, x)) for x in ('w-own', 'w-bad')]
    ok = r1 == 2 and r2 == 2 and 'not its own peer' in e1 and 'bad peer id' in e2 and all(none)
    return ok, ('--peers %s for the window of %s: exit %d [%s]; --peers with a slash in the id: exit %d [%s]; baseline written %s' % (
        A, A, r1, hide(ctx, e1.strip())[:80], r2, hide(ctx, e2.strip())[:60], [not n for n in none]))


CHECKS = {'peer': peer_row, 'control': control_row, 'trailer': trailer_row, 'stranger': stranger_row, 'nopeers': nopeers_row, 'badpeer': badpeer_row}


def row_check(ctx, rid, expect, arg):
    ok, detail = CHECKS[arg](ctx)
    return ok, 'expected [%s] measured: %s' % (expect, hide(ctx, detail))


def main():
    tree, home, work = env_dirs(USAGE)
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K10-C5/run.py', HERE + '/run.py'), ('tests/rows/K10-C5/rows.txt', HERE + '/rows.txt'),
              ('bin/loop_tripwire.py', tree + '/bin/loop_tripwire.py'), ('bin/loop_procs.py', tree + '/bin/loop_procs.py')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    print('info worlds are constructed repositories under the work folder, never a clone of a real one')
    return tally(load_rows(HERE + '/rows.txt'), {'check': row_check}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
