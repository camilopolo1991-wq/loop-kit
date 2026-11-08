#!/usr/bin/env python3
"""K11-C4 rows runner: the planted control and the step-log commit place (FIXTURE-01 report gates 1 and 3).

(a) the fixture goal template (templates/GOAL.md) and the preamble (templates/GOAL_PREAMBLE.md) name, in one wording, the leader as the
writer of a planted control inside an open window; a planted control written that way reads as a difference (check exit 1, naming the file).
(b) loop-record-commit with no path refuses while the goal's record worktree exists; loop-record-merge lands the step-log commit with a
range scan of 0 hits; with no goal worktree the same call still commits (control).

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test (its bin/ and templates/ are what is read and run)
  LOOP_ROWS_HOME   the folder every throwaway home is made under (k11c4-fixtures/<tag>-<ns>/home)
  LOOP_WORK        the work folder; the manifest k11c4-manifest.txt listing every world is kept here
  LOOP_PY          the interpreter every child is run with (defaults to the one running this file)

Fixtures. Every world is built by this file: a throwaway home with a constructed loop home (config.env, one goal folder FIX-01), and for
the (b) rows a constructed record repository (branch record) with a step log and a state file, never a clone of a real one. The repository
commands this file runs are run inside those throwaway repositories only. The commit identity is a placeholder passed by the environment.
Every child gets HOME, USERPROFILE and LOOP_HOME at the world's own home and PYTHONDONTWRITEBYTECODE=1 (make_env). The live home, the
live record repository and the live step log are never named or read.

The leader's step in row A is the row itself: it stands for the leader's one Write inside the window (no other role is dispatched, no
peer is listed). Rows B1 and B2 share one world (b1 leaves the pending lines that b2 lands); B3 has its own world with no worktree.
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
from _lib import env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, remove_path, tally, write_text

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py (no positional argument)'
MANIFEST = 'k11c4-manifest.txt'
DROP = ('LOOP_GOAL', 'HERMES_HOME', 'CLAUDE_BIN', 'LOOP_CLAUDE_BIN', 'MAX_LEADERS', 'REPORT_SEND_CMD', 'JOURNAL_FILE', 'LOOP_GUARD_MODE',
        'LOOP_PY', 'ENGINE_RECORD_DIR', 'RECORD_BRANCH', 'KIT_DIR', 'KIT_BRANCH', 'STATE_FILE', 'EXPORT_DIR', 'WRITABLE_TREES', 'SURFACES',
        'TRIPWIRE_NOISE', 'N8N_DB', 'LOOP_RECORD_WT', 'LOOP_KIT_WT', 'LOOP_STEPLOG_LOCK_WAIT_S', 'LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS')
GITENV = {'GIT_AUTHOR_NAME': 'Omicron Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid', 'GIT_COMMITTER_NAME': 'Omicron Fixture',
          'GIT_COMMITTER_EMAIL': 'fixture@example.invalid', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_TERMINAL_PROMPT': '0'}
G = 'FIX-01'
WORDS = ('Planted control: a planted control inside an open window is written by the leader, as that one Write, inside a window that '
         'brackets no other role, and the window\'s check names it as the planted INCIDENT.')
ST = {}
USERPATH = re.compile(r'(?i)(?:[A-Za-z]:)?[\\/]+users[\\/]+[^\\/\s\'"]+')


def hide(ctx, s):
    # the interpreter and the folders sit under the real user folder, a real name: cut first, in forward, backward and doubled spelling
    for p, repl in ((ctx['py'], '<py>'), (ctx['home'], '<rows-home>'), (ctx['work'], '<work>'),
                    (fwd(os.path.expanduser('~')), '~'), (os.path.expanduser('~'), '~')):
        s = s.replace(p, repl).replace(p.replace('/', '\\'), repl).replace(p.replace('/', '\\\\'), repl)
    return USERPATH.sub('~', s)


def clean_prior_worlds(ctx):
    """Remove the worlds an earlier run listed in its manifest (only paths under LOOP_ROWS_HOME/k11c4-fixtures/)."""
    mf = ctx['work'] + '/' + MANIFEST
    data = read_bytes(mf)
    n = 0
    if data is not None:
        for p in data.decode('utf-8', 'replace').split('\n'):
            p = p.strip()
            if p and fwd(p).startswith(ctx['home'] + '/k11c4-fixtures/') and os.path.exists(p):
                remove_path(p)
                n += 1
        os.remove(mf)
    print('cleaned %d path(s) listed by an earlier run' % n)


class World:
    """A throwaway home with a constructed loop home and goal folder; with repo true also a constructed record repository."""

    def __init__(self, ctx, tag, repo=False):
        self.ctx = ctx
        self.base = '%s/k11c4-fixtures/%s-%d' % (ctx['home'], tag, time.time_ns())
        os.makedirs(self.base + '/tmp')
        with open(ctx['work'] + '/' + MANIFEST, 'a', encoding='utf-8') as fh:
            fh.write(self.base + '\n')
        self.home = self.base + '/home'
        self.lh = self.home + '/.loop'
        self.rec = self.base + '/record'
        os.makedirs(self.lh)
        cfg = 'RECORD_BRANCH=record\n' + ('ENGINE_RECORD_DIR=%s\nMAX_LEADERS=9\n' % self.rec if repo else '')
        write_text(self.lh + '/config.env', cfg)
        gd = '%s/goals/%s' % (self.lh, G)
        os.makedirs(gd + '/evidence/T01/writer')
        write_text(gd + '/GOAL.md', '# %s: constructed fixture goal\nAuthority: the record repository on its record branch only.\n' % G)
        write_text(gd + '/plan.md', '# plan\n| ID | Task | Owner | Status |\n|----|------|-------|--------|\n| T01 | fixture | writer | PASS |\n')
        write_text(gd + '/evidence/T01/writer/rollback.txt', 'fixture rollback\n')
        if repo:
            self.init_repo()

    def env(self, extra=None):
        drop = DROP + tuple(k for k in os.environ if k.startswith('LOOP_TRIPWIRE_'))
        e = dict(GITENV, TEMP=self.base + '/tmp', TMP=self.base + '/tmp')
        e.update(extra or {})
        return make_env(self.home, e, drop)

    def git(self, cwd, *args):
        cp = subprocess.run(['git'] + list(args), cwd=cwd, capture_output=True, env=self.env(), stdin=subprocess.DEVNULL)
        return cp.returncode, (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '').strip()

    def init_repo(self):
        os.makedirs(self.rec)
        for args in (['init', '-q', '-b', 'record'], ['config', 'core.autocrlf', 'false']):
            rc, out = self.git(self.rec, *args)
            assert rc == 0, out
        files = {'.gitattributes': '* text eol=lf\n',
                 'docs/JOURNAL.md': '# step log fixture\n- 2026-01-01T00:00:00Z FIX-00 GOAL START fixture\n',
                 'docs/STATE.md': '# STATE fixture\n## 5. Running goals\n### %s\n- none\n' % G}
        for rel, text in files.items():
            os.makedirs(os.path.dirname(self.rec + '/' + rel), exist_ok=True)
            write_text(self.rec + '/' + rel, text)
        for args in (['add', '-A'], ['commit', '-q', '-m', 'chore(fixture): initial']):
            rc, out = self.git(self.rec, *args)
            assert rc == 0, out

    def tool(self, name, *args, cwd=None):
        cp = subprocess.run([self.ctx['py'], '%s/bin/loop_%s.py' % (self.ctx['tree'], name)] + list(args), capture_output=True,
                            env=self.env(), cwd=cwd or self.base, stdin=subprocess.DEVNULL, timeout=300)
        out = (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '').strip()
        return cp.returncode, hide(self.ctx, out)

    def tip(self, ref='HEAD'):
        return self.git(self.rec, 'rev-parse', ref)[1]

    def pending(self):
        return sorted(x.split(None, 1)[1].strip() for x in self.git(self.rec, 'status', '--porcelain', '--untracked-files=no')[1].split('\n')
                      if x.strip())

    def wt(self):
        return '%s/work/%s/record' % (self.lh, G)

    def leave_pending(self, word):
        """What the step-log tool and a leader's state edit leave in the record work tree: one step-log line and an edit of the goal's own
        subsection, both uncommitted."""
        with open(self.rec + '/docs/JOURNAL.md', 'a', encoding='utf-8', newline='\n') as fh:
            fh.write('- 2026-01-02T00:00:00Z %s T01 NOTE %s\n' % (G, word))
        sp = self.rec + '/docs/STATE.md'
        s = (read_bytes(sp) or b'').decode('utf-8')
        write_text(sp, s.replace('### %s\n' % G, '### %s\n- %s\n' % (G, word), 1))

    def tw(self, *args):
        cp = subprocess.run([self.ctx['py'], self.ctx['tree'] + '/bin/loop_tripwire.py'] + list(args), capture_output=True, env=self.env(),
                            cwd=self.base, stdin=subprocess.DEVNULL, timeout=300)
        out = cp.stdout.decode('utf-8', 'replace').replace('\r', '')
        return cp.returncode, [x for x in out.split('\n') if x.strip()]

    def scan(self, rng):
        cp = subprocess.run([self.ctx['py'], self.ctx['tree'] + '/bin/loop_scan.py', '--range', rng], capture_output=True, env=self.env(),
                            cwd=self.rec, stdin=subprocess.DEVNULL, timeout=300)
        text = cp.stdout.decode('utf-8', 'replace')
        m = re.search(r'\bhits=(\d+)', text)
        c = re.search(r'\bcontrol=(\w+)', text)
        return cp.returncode, (int(m.group(1)) if m else None), (c.group(1) if c else None)


def first(ctx, s, n=170):
    ls = [x for x in s.split('\n') if x.strip()]
    return hide(ctx, ls[-1])[:n] if ls else 'no output'


def line_of(tree, rel, prefix):
    """(1-based line number, text after the prefix) of the first line of tree/rel that starts with prefix; (0, None) when none."""
    b = read_bytes(tree + '/' + rel)
    if b is None:
        return 0, None
    for i, ln in enumerate(b.decode('utf-8', 'replace').replace('\r', '').split('\n'), 1):
        if ln.startswith(prefix):
            return i, ln[len(prefix):]
    return 0, None


# ---------------------------------------------------------------- rows
def words_row(ctx):
    a = line_of(ctx['tree'], 'templates/GOAL.md', '6. ')
    b = line_of(ctx['tree'], 'templates/GOAL_PREAMBLE.md', '- Planted control: ')
    if b[1] is not None:
        b = (b[0], 'Planted control: ' + b[1])
    ok = a[1] == WORDS and b[1] == WORDS
    return ok, ('templates/GOAL.md line %d carries the wording %s; templates/GOAL_PREAMBLE.md line %d carries the wording %s; the two are '
                'byte-equal %s' % (a[0], a[1] == WORDS, b[0], b[1] == WORDS, a[1] is not None and a[1] == b[1]))


def plant_row(ctx):
    w = World(ctx, 'plant')
    s_rc, _ = w.tw('start', G, 'w-plant')                       # a window that brackets no other role and lists no peer
    z_rc, z_out = w.tw('check', G, 'w-plant')                   # control: nothing written yet reads clean
    time.sleep(0.05)
    write_text('%s/goals/%s/planted-control.txt' % (w.lh, G), 'the planted control, the leader\'s one Write inside the window\n')
    rc, out = w.tw('check', G, 'w-plant')
    named = [x for x in out if x.startswith('FILE ') and x[5:].replace('\\', '/').split(': ', 1)[0].endswith('/goals/%s/planted-control.txt' % G)]
    b = read_bytes('%s/goals/%s/evidence/w-plant/diff-latest.txt' % (w.lh, G)) or b''
    ok = s_rc == 0 and z_rc == 0 and z_out == ['no differences'] and rc == 1 and len(named) == 1 and b'planted-control.txt' in b
    return ok, ('start exit %d; control check before the Write exit %d [%s]; after the leader\'s one Write of goals/%s/planted-control.txt the '
                'check exit %d with %d FILE line(s) naming it, diff-latest names it %s; first stdout line [%s]' % (
                    s_rc, z_rc, ' | '.join(z_out)[:40], G, rc, len(named), b'planted-control.txt' in b, hide(ctx, out[0])[:110] if out else 'none'))


def refuse_world(ctx):
    if 'b' not in ST:
        w = World(ctx, 'b', repo=True)
        o_rc, o_out = w.tool('worktree', 'open', G)
        w.leave_pending('pending before the commit call')
        ST['b'] = (w, o_rc, o_out)
    return ST['b']


def refuse_row(ctx):
    w, o_rc, o_out = refuse_world(ctx)
    t0, p0 = w.tip(), w.pending()
    rc, out = w.tool('record_commit', G, '-m', 'chore(record): step log lines', cwd=w.rec)
    t1, p1 = w.tip(), w.pending()
    lines = [x for x in out.split('\n') if x.strip()]
    staged = w.git(w.rec, 'diff', '--cached', '--name-only')[1]
    ok = (o_rc == 0 and os.path.isdir(w.wt()) and p0 == ['docs/JOURNAL.md', 'docs/STATE.md'] and rc != 0 and len(lines) == 1
          and 'worktree' in out and 'loop-record-merge' in out and t0 == t1 and p0 == p1 and staged == '')
    return ok, ('precondition: worktree open exit %d, folder present %s, pending %s; loop-record-commit %s with no path: exit %d, %d output line(s) '
                '[%s]; tip unchanged %s, pending unchanged %s, nothing staged %s' % (
                    o_rc, os.path.isdir(w.wt()), p0, G, rc, len(lines), first(ctx, out), t0 == t1, p0 == p1, staged == ''))


def merge_row(ctx):
    w, o_rc, o_out = refuse_world(ctx)
    gw = w.wt()
    write_text(gw + '/docs/note.md', 'a note of the goal\n')                       # the goal's own branch gets a note, committed by path
    n_rc, n_out = w.tool('record_commit', G, '-m', 'docs(record): note', '--', 'docs/note.md', cwd=gw)
    pend = w.pending()
    t0 = w.tip()
    m_rc, m_out = w.tool('record_merge', G, cwd=gw)                                # from the goal's record worktree
    t1 = w.tip()
    s_rc, hits, ctl = w.scan(t0 + '..' + t1)
    j = w.git(w.rec, 'show', 'HEAD:docs/JOURNAL.md')[1]
    st = w.git(w.rec, 'show', 'HEAD:docs/STATE.md')[1]
    trailers = w.git(w.rec, 'log', '--format=%(trailers:key=Goal,valueonly)', t0 + '..' + t1)[1].split()
    contained = w.git(w.rec, 'merge-base', '--is-ancestor', 'rec-fix-01', 'record')[0] == 0
    clean = w.pending() == []
    # control for the zero: a range holding a line the scanner flags gives hits above 0 with the same instrument
    w.git(w.rec, 'branch', 'ctl', t0)
    cw = w.base + '/ctlwt'
    c_ok = w.git(w.rec, 'worktree', 'add', '-q', cw, 'ctl')[0] == 0
    flagged = 'a remote ' + 'github' + '.com/example-org/example-repo' + ' is a shape the scanner flags\n'   # built here so this file holds no flagged line
    write_text(cw + '/ctl.txt', flagged)
    w.git(cw, 'add', 'ctl.txt')
    w.git(cw, 'commit', '-q', '-m', 'chore(fixture): control line')
    cs_rc, chits, cctl = w.scan(t0 + '..ctl')
    w.git(w.rec, 'worktree', 'remove', '--force', cw)
    ok = (o_rc == 0 and n_rc == 0 and pend == ['docs/JOURNAL.md', 'docs/STATE.md'] and m_rc == 0 and 'range_scan_hits=0' in m_out
          and 'pending_lines_commit=none' not in m_out and t0 != t1 and hits == 0 and s_rc == 0 and ctl == 'fired'
          and 'FIX-01 T01 NOTE pending before the commit call' in j and '- pending before the commit call' in st
          and trailers and set(trailers) == {G} and contained and clean and c_ok and chits is not None and chits > 0 and cs_rc != 0)
    return ok, ('precondition: goal note committed by path exit %d, record work tree held %s uncommitted; loop-record-merge %s from the goal worktree '
                'exit %d [%s]; tip moved %s; independent scan of old..new exit %d hits=%s scanner control=%s; the pending step-log line is in the '
                'committed step log %s and the own state line in the committed state file %s; Goal trailers %s; branch contained %s; tree clean '
                '%s; control range (a flagged line) scan exit %d hits=%s' % (
                    n_rc, pend, G, m_rc, first(ctx, m_out, 150), t0 != t1, s_rc, hits, ctl,
                    'FIX-01 T01 NOTE pending before the commit call' in j, '- pending before the commit call' in st, sorted(set(trailers)),
                    contained, clean, cs_rc, chits))


def control_row(ctx):
    w = World(ctx, 'ctl', repo=True)
    w.leave_pending('pending with no worktree')
    exists = os.path.isdir(w.wt())
    t0, p0 = w.tip(), w.pending()
    rc, out = w.tool('record_commit', G, '-m', 'chore(record): step log lines', cwd=w.rec)
    t1, p1 = w.tip(), w.pending()
    j = w.git(w.rec, 'show', 'HEAD:docs/JOURNAL.md')[1]
    tr = w.git(w.rec, 'log', '-1', '--format=%(trailers:key=Goal,valueonly)')[1].strip()
    ok = (not exists and p0 == ['docs/JOURNAL.md', 'docs/STATE.md'] and rc == 0 and 'committed' in out and t0 != t1 and p1 == []
          and 'FIX-01 T01 NOTE pending with no worktree' in j and tr == G)
    return ok, ('goal worktree present %s; pending %s; loop-record-commit %s with no path: exit %d [%s]; tip moved %s; pending after %s; the line is in '
                'the committed step log %s; trailer Goal %s' % (exists, p0, G, rc, first(ctx, out, 120), t0 != t1, p1,
                                                              'FIX-01 T01 NOTE pending with no worktree' in j, tr))


CHECKS = {'words': words_row, 'plant': plant_row, 'refuse': refuse_row, 'merge': merge_row, 'control': control_row}


def row_check(ctx, rid, expect, arg):
    ok, detail = CHECKS[arg](ctx)
    return ok, 'expected [%s] measured: %s' % (expect[:150], hide(ctx, detail))


def main():
    tree, home, work = env_dirs(USAGE)
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    clean_prior_worlds(ctx)
    info_sha((('tests/rows/K11-C4/run.py', HERE + '/run.py'), ('tests/rows/K11-C4/rows.txt', HERE + '/rows.txt'),
              ('bin/loop_record_commit.py', tree + '/bin/loop_record_commit.py'), ('bin/loop_record_merge.py', tree + '/bin/loop_record_merge.py')))
    print('info worlds are constructed homes and record repositories under the rows home, never a clone of a real one')
    kinds = {k: row_check for k in ('words', 'check', 'refuse', 'merge', 'control')}
    return tally(load_rows(HERE + '/rows.txt'), kinds, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
