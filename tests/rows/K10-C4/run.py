#!/usr/bin/env python3
"""K10-C4 rows runner: a worktree per goal (loop-worktree), the locked record helper (loop-record-commit), the locked merge
(loop-record-merge), and the dispatcher opening a goal's worktrees (bin/loop_dispatch.py).

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test (its bin/ is what runs)
  LOOP_ROWS_HOME   unused here (every child gets its own throwaway home under LOOP_WORK); required by the shape of the runners
  LOOP_WORK        the work folder; every fixture is written under it and listed in k10c4-manifest.txt
  LOOP_PY          the interpreter every child is run with (defaults to the one running this file)
  TIMEOUT_BIN      optional; a GNU timeout for the dispatch row (found and proved by --version as the K10-C2 runner does)
  K10C4_RAW_N      iterations per process of the unlocked index.lock control (default 25)
  K10C4_PAIR_N     iterations per process of the same pair through the helper (default 8)
  K10C4_TRIES      tries of the unlocked control before it says it could not reproduce (default 3)

Fixtures. Every world is built by this file under LOOP_WORK: a throwaway home, a constructed record repository (branch record) and a
constructed kit repository (branch main), never a clone of a real one, so no command here touches a real repository. The commit identity
is a placeholder passed by the environment. Every child gets HOME, USERPROFILE and LOOP_HOME at the world's own home and
PYTHONDONTWRITEBYTECODE=1 (make_env). The live home is never named.

How the tools read that a GOAL names the kit: bin/loop_worktree.py takes the Authority paragraph of the goal's GOAL.md (from the line that
starts Authority: to the next blank line or next "Label:" line) and looks for ~/loop-kit not followed by a letter, digit, underscore or dash.
Row K10-C4-OPEN opens a goal that names it (kit made) and a goal that mentions the kit only outside its Authority paragraph (no kit made).
"""
import importlib.util
import os
import re
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, register, shafull, sha, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [TIMEOUT_BIN=<gnu timeout>] '
         '[K10C4_RAW_N=<n>] [K10C4_PAIR_N=<n>] [K10C4_TRIES=<n>] python run.py (no positional argument)')
MANIFEST = 'k10c4-manifest.txt'
DROP = ('LOOP_GOAL', 'HERMES_HOME', 'CLAUDE_BIN', 'LOOP_CLAUDE_BIN', 'LOOP_LEADER_STUB', 'MAX_LEADERS', 'MIN_FREE_MB', 'REPORT_SEND_CMD',
        'JOURNAL_FILE', 'LOOP_GUARD_MODE', 'LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_PY', 'ENGINE_RECORD_DIR', 'RECORD_BRANCH', 'KIT_DIR',
        'KIT_BRANCH', 'LOOP_RECORD_WT', 'LOOP_KIT_WT', 'LOOP_STEPLOG_LOCK_WAIT_S', 'K10C4_CAP', 'K10C4_REC', 'K10C4_TURN')
GITENV = {'GIT_AUTHOR_NAME': 'Omicron Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid', 'GIT_COMMITTER_NAME': 'Omicron Fixture',
          'GIT_COMMITTER_EMAIL': 'fixture@example.invalid', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_TERMINAL_PROMPT': '0'}
STUB = fwd(HERE + '/stub_leader.py')
SENT = ("Every record commit outside the step log and STATE.md happens in the goal's own record worktree, `$LOOP_RECORD_WT` (and, when "
        "GOAL.md's Authority names the kit, the kit worktree `$LOOP_KIT_WT`), made with `loop-record-commit <GOAL-ID> -m <message> -- <path>`; "
        "the step log and STATE.md commit lands through `loop-record-merge <GOAL-ID>` run from the goal's record worktree, and "
        "`loop-record-commit <GOAL-ID>` with no path refuses while a goal worktree exists, so the step log and STATE.md are never committed in "
        "a goal worktree; a leader edits only its own `### <GOAL-ID>` subsection of STATE.md section 5; `loop-record-merge "
        "<GOAL-ID>` is the one step that lands the goal's branch on the record branch.")
NEW_BIN = ('bin/loop-worktree', 'bin/loop-record-commit', 'bin/loop-record-merge', 'bin/loop_worktree.py', 'bin/loop_record_commit.py',
           'bin/loop_record_merge.py')
FILLER = 'Acceptance criteria:\n1. a constructed line that is only here to make the file longer than a stub\n' * 6
ST = {}


USERPATH = re.compile(r'(?i)(?:[A-Za-z]:)?[\\/]+users[\\/]+[^\\/\s\'"]+')


def hide(ctx, s):
    # the interpreter path sits under the real user folder, which is a real name: it is cut first, then the work folder and the home,
    # in forward, backward and doubled-backward spelling (an interpreter's can't-open-file message doubles the backslashes); any
    # path of the shape <drive>:/Users/<name> that is left is cut by shape
    for p, repl in ((ctx['py'], '<py>'), (ctx['work'], '<work>'), (fwd(os.path.expanduser('~')), '~'), (os.path.expanduser('~'), '~')):
        s = s.replace(p, repl).replace(p.replace('/', '\\'), repl).replace(p.replace('/', '\\\\'), repl)
    return USERPATH.sub('~', s)


class World:
    """A throwaway home with a constructed record repository, a constructed kit repository and goal folders."""

    def __init__(self, ctx, tag, goals):
        self.ctx = ctx
        self.base = '%s/k10c4-fixtures/%s-%d' % (ctx['work'], tag, time.time_ns())
        register(ctx['work'], MANIFEST, self.base)
        self.home = self.base + '/home'
        self.lh = self.home + '/.loop'
        self.rec = self.base + '/record'
        self.kit = self.base + '/loop-kit'
        os.makedirs(self.lh + '/stub')
        os.makedirs(self.base + '/tmp')
        write_text(self.lh + '/config.env', 'ENGINE_RECORD_DIR=%s\nRECORD_BRANCH=record\nKIT_DIR=%s\nMAX_LEADERS=9\n' % (self.rec, self.kit))
        for g in goals:
            names = g in ('FIX-01', 'FIX-02')
            auth = ('Authority: writes to branch %s in `~/loop-kit` and its worktree; the record repository on its record branch.\n' % g.lower()
                    if names else 'Authority: the record repository on its record branch only.\n')
            ctxl = '' if names else 'Known context: the kit lives at ~/loop-kit and is read, never written, by this goal.\n'
            gd = '%s/goals/%s' % (self.lh, g)
            os.makedirs(gd + '/evidence/T01/writer')
            write_text(gd + '/GOAL.md', '# %s: constructed fixture goal\n%s%s\n%s' % (g, auth, ctxl, FILLER))
            write_text(gd + '/plan.md', '# plan\n| ID | Task | Owner | Status |\n|----|------|-------|--------|\n| T01 | fixture | writer | PASS |\n')
            write_text(gd + '/evidence/T01/writer/rollback.txt', 'fixture rollback\n')
        self.init_repo(self.rec, 'record', {
            '.gitattributes': '* text eol=lf\n',
            'docs/JOURNAL.md': '# step log fixture\n- 2026-01-01T00:00:00Z FIX-00 GOAL START fixture\n',
            'docs/STATE.md': '# STATE fixture\n## 5. Running goals\n' + ''.join('### %s\n- none\n' % g for g in ('FIX-01', 'FIX-02', 'FIX-03', 'FIX-04')),
            'docs/NOTES.md': 'alpha\n'})
        self.init_repo(self.kit, 'main', {'README.md': 'kit fixture\n', 'bin/tool.py': 'print("kit fixture")\n'})

    def env(self, extra=None, drop=()):
        e = dict(GITENV, TEMP=self.base + '/tmp', TMP=self.base + '/tmp', TIMEOUT_BIN=self.ctx['tmo'] or '',
                 LOOP_CLAUDE_BIN=self.lh + '/no-such-claude')
        e.update(extra or {})
        return make_env(self.home, e, DROP + tuple(drop))

    def git(self, cwd, *args):
        cp = subprocess.run(['git'] + list(args), cwd=cwd, capture_output=True, env=self.env(), stdin=subprocess.DEVNULL)
        return cp.returncode, (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '').strip()

    def init_repo(self, path, branch, files):
        os.makedirs(path)
        for args in (['init', '-q', '-b', branch], ['config', 'core.autocrlf', 'false']):
            rc, out = self.git(path, *args)
            assert rc == 0, out
        for rel, text in files.items():
            os.makedirs(os.path.dirname(path + '/' + rel), exist_ok=True)
            write_text(path + '/' + rel, text)
        for args in (['add', '-A'], ['commit', '-q', '-m', 'chore(fixture): initial']):
            rc, out = self.git(path, *args)
            assert rc == 0, out

    def tool(self, name, *args, extra=None, cwd=None):
        t = time.time()
        cp = subprocess.run([self.ctx['py'], '%s/bin/loop_%s.py' % (self.ctx['tree'], name)] + list(args), capture_output=True,
                            env=self.env(extra), cwd=cwd or self.base, stdin=subprocess.DEVNULL, timeout=300)
        out = (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '').strip()
        return cp.returncode, hide(self.ctx, out)

    def tip(self, repo, ref='HEAD'):
        return self.git(repo, 'rev-parse', ref)[1]

    def append_step(self, gid, text):
        """One line through the real step-log tool, JOURNAL_FILE at the record repository's work tree as the dispatcher leaves it."""
        cp = subprocess.run([self.ctx['py'], self.ctx['tree'] + '/bin/loop_journal.py', gid, 'T01', text], capture_output=True,
                            env=self.env({'JOURNAL_FILE': self.rec + '/docs/JOURNAL.md'}), cwd=self.base, stdin=subprocess.DEVNULL, timeout=120)
        return cp.returncode

    def edit_state(self, gid, line, path=None):
        """Put line first under the "### <gid>" heading of section 5 of the state file in path (default: the record work tree's)."""
        path = path or self.rec + '/docs/STATE.md'
        s = (read_bytes(path) or b'').decode('utf-8')
        assert '### %s\n' % gid in s
        write_text(path, s.replace('### %s\n' % gid, '### %s\n%s\n' % (gid, line), 1))

    def pending(self):
        """The tracked paths changed in the record repository's work tree (what the step-log tool and a state edit leave there)."""
        return sorted(x.split(None, 1)[1].strip() for x in self.git(self.rec, 'status', '--porcelain', '--untracked-files=no')[1].split('\n')
                      if x.strip())

    def branches(self, repo):
        return sorted(self.git(repo, 'for-each-ref', '--format=%(refname:short)', 'refs/heads')[1].split())

    def wtpath(self, g, which):
        return '%s/work/%s/%s' % (self.lh, g, which)

    def on_branch(self, folder, want):
        rc, out = self.git(folder, 'symbolic-ref', '--short', 'HEAD') if os.path.isdir(folder) else (1, '')
        return rc == 0 and out == want


def world(ctx):
    if 'a' not in ST:
        ST['a'] = World(ctx, 'main', ('FIX-01', 'FIX-02', 'FIX-03'))
    return ST['a']


def first(s):
    ls = [x for x in s.split('\n') if x.strip()]
    return ls[-1][:130] if ls else 'no output'


# ---------------------------------------------------------------- children (parallel processes)
def wait_until(start):
    while time.time() < start:
        time.sleep(0.005)


class Turn:
    """A mutex between the two leaders' children (a directory made and removed), standing for the fact that a leader's state edit and
    the commit that follows it are one quick step (the step-log line is shared; row K10-C4-TWOGOALS covers two simultaneous
    uncommitted subsection edits). Independent of the kit code."""

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        while True:
            try:
                os.mkdir(self.path)
                return self
            except OSError:
                time.sleep(0.01)

    def __exit__(self, *a):
        os.rmdir(self.path)


def child_goal(tree, gid, n, start):
    """n steps of one goal, each: a step-log line through the real loop_journal (JOURNAL_FILE at the record work tree), at step 3 an
    edit of the goal's own section-5 subsection, a note committed in the goal's record worktree through loop_record_commit with a path,
    then loop_record_merge from that worktree (KIT-11 C4 (b): with the worktree present the no-path call refuses, so the pending step-log
    and state lines land through the merge). The four are one turn at a time."""
    py = sys.executable
    rec = os.environ['K10C4_REC']
    gw = os.environ['LOOP_HOME'] + '/work/%s/record' % gid
    cap = open(os.environ['K10C4_CAP'], 'w', encoding='utf-8', newline='\n')
    wait_until(start)
    bad = 0
    for i in range(1, n + 1):
        text = {1: 'ROLLBACK evidence/T01/writer/rollback.txt sha256 0123456789abcdef', n: 'PASS evidence/T01/writer/proof.txt'}.get(i, 'NOTE step %d' % i)
        note = 'docs/step-%s-%d.md' % (gid.lower(), i)
        with Turn(os.environ['K10C4_TURN']):
            jp = subprocess.run([py, tree + '/bin/loop_journal.py', gid, 'T01', text], capture_output=True, stdin=subprocess.DEVNULL,
                                env=dict(os.environ, JOURNAL_FILE=rec + '/docs/JOURNAL.md'))
            if i == 3:
                sp = rec + '/docs/STATE.md'
                s = open(sp, encoding='utf-8', newline='').read()
                write_text(sp, s.replace('### %s\n- none\n' % gid, '### %s\n- step 3 written by the goal\n' % gid))
            write_text(gw + '/' + note, 'note of %s step %d\n' % (gid, i))
            nc = subprocess.run([py, tree + '/bin/loop_record_commit.py', gid, '-m', 'docs(record): %s note %d' % (gid.lower(), i), '--', note],
                                capture_output=True, stdin=subprocess.DEVNULL, cwd=gw)
            t0 = time.time()
            cp = subprocess.run([py, tree + '/bin/loop_record_merge.py', gid], capture_output=True, stdin=subprocess.DEVNULL, cwd=gw)
        out = (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '').replace('\n', ' | ').strip()
        bad += (jp.returncode != 0) + (nc.returncode != 0) + (cp.returncode != 0)
        cap.write('%d journal_rc=%d note_rc=%d merge_rc=%d secs=%.2f said=%s\n' % (i, jp.returncode, nc.returncode, cp.returncode, time.time() - t0, out))
    cap.close()
    sys.exit(1 if bad else 0)


def child_pair(tree, tag, n, start, gid):
    """n times: one line through the real loop_journal at the record work tree, then loop_record_commit with no path, no turn taken."""
    py = sys.executable
    rec = os.environ['K10C4_REC']
    cap = open(os.environ['K10C4_CAP'], 'w', encoding='utf-8', newline='\n')
    wait_until(start)
    for i in range(n):
        jp = subprocess.run([py, tree + '/bin/loop_journal.py', gid, 'T01', 'NOTE pair %s %d' % (tag, i)], capture_output=True,
                            stdin=subprocess.DEVNULL, env=dict(os.environ, JOURNAL_FILE=rec + '/docs/JOURNAL.md'))
        c = subprocess.run([py, tree + '/bin/loop_record_commit.py', gid, '-m', 'chore(record): pair %s %d' % (tag, i)], cwd=rec,
                           capture_output=True, stdin=subprocess.DEVNULL)
        out = c.stdout + c.stderr
        m = re.search(rb'index_lock_retries=(\d+)', out)
        cap.write('%d journal=%d commit=%d indexlock=%d retries=%s\n' % (i, jp.returncode, c.returncode, 1 if b'index.lock' in out else 0,
                                                                         m.group(1).decode() if m else '0'))
    cap.close()
    sys.exit(0)


def child_commit(mode, tree, folder, tag, n, start, gid):
    """n commits of files raw-<tag>-<i>.txt in one worktree: mode raw is add and commit with the plain tools, mode help is loop_record_commit."""
    py = sys.executable
    cap = open(os.environ['K10C4_CAP'], 'w', encoding='utf-8', newline='\n')
    wait_until(start)
    for i in range(n):
        name = 'raw-%s-%d.txt' % (tag, i)
        write_text(folder + '/' + name, 'line %s %d\n' % (tag, i))
        if mode == 'raw':
            a = subprocess.run(['git', 'add', '--', name], cwd=folder, capture_output=True, stdin=subprocess.DEVNULL)
            c = subprocess.run(['git', 'commit', '-q', '-m', 'chore(raw): %s %d' % (tag, i)], cwd=folder, capture_output=True,
                               stdin=subprocess.DEVNULL)
            err = a.stderr + c.stderr
            cap.write('%d add=%d commit=%d indexlock=%d\n' % (i, a.returncode, c.returncode, 1 if b'index.lock' in err else 0))
        else:
            c = subprocess.run([py, tree + '/bin/loop_record_commit.py', gid, '-m', 'chore(record): help %s %d' % (tag, i), '--', name],
                               cwd=folder, capture_output=True, stdin=subprocess.DEVNULL)
            out = c.stdout + c.stderr
            m = re.search(rb'index_lock_retries=(\d+)', out)
            cap.write('%d commit=%d indexlock=%d retries=%s\n' % (i, c.returncode, 1 if b'index.lock' in out else 0, m.group(1).decode() if m else '?'))
    cap.close()
    sys.exit(0)


def spawn(w, argv, capname):
    base = w.base + '/caps'
    os.makedirs(base, exist_ok=True)
    cap = '%s/%s' % (base, capname)
    p = subprocess.Popen([w.ctx['py'], fwd(__file__), '--child'] + argv,
                         env=w.env({'K10C4_CAP': cap, 'K10C4_REC': w.rec, 'K10C4_TURN': w.base + '/tmp/turn'}), cwd=w.base,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return p, cap


def start_epoch():
    return int(time.time()) + 6          # whole second, a few seconds ahead so both children are loaded and waiting


def lines_of(path):
    b = read_bytes(path)
    return [] if b is None else [x for x in b.decode('utf-8', 'replace').replace('\r', '').split('\n') if x.strip()]


# ---------------------------------------------------------------- rows
def open_row(ctx):
    w = world(ctx)
    rt0, kt0 = w.tip(w.rec, 'record'), w.tip(w.kit, 'main')
    res = {g: w.tool('worktree', 'open', g) for g in ('FIX-01', 'FIX-02', 'FIX-03')}
    bad = []
    for g in ('FIX-01', 'FIX-02'):
        rc, out = res[g]
        rf, kf = w.wtpath(g, 'record'), w.wtpath(g, 'kit')
        if rc != 0 or not out.startswith('record ') or '\nkit ' not in out:
            bad.append('%s open exit %d [%s]' % (g, rc, first(out)))
        if not (w.on_branch(rf, 'rec-' + g.lower()) and w.tip(rf) == rt0):
            bad.append('%s record worktree not on rec-%s at the record tip' % (g, g.lower()))
        if not (w.on_branch(kf, g.lower()) and w.tip(kf) == kt0):
            bad.append('%s kit worktree not on %s at kit main' % (g, g.lower()))
    rc, out = res['FIX-03']
    if rc != 0 or '\nkit ' in out or out.startswith('kit '):
        bad.append('FIX-03 open exit %d [%s]' % (rc, first(out)))
    if os.path.exists(w.wtpath('FIX-03', 'kit')) or 'fix-03' in w.branches(w.kit) or not w.on_branch(w.wtpath('FIX-03', 'record'), 'rec-fix-03'):
        bad.append('FIX-03 (Authority does not name the kit) has a kit folder or branch, or no record worktree')
    if bad:
        return False, 'PROBLEMS: ' + '; '.join(bad)
    return True, ('exits %s; record tip %s and kit main %s; FIX-01 and FIX-02 each on rec-<id> (record) and <id> (kit) at those tips; '
                  'FIX-03 record only (kit folder absent, kit branch absent)' % ([res[g][0] for g in res], rt0[:12], kt0[:12]))


def open_twice_row(ctx):
    w = world(ctx)
    before = (w.git(w.rec, 'worktree', 'list')[1], w.branches(w.rec), w.branches(w.kit))
    rc1, o1 = w.tool('worktree', 'open', 'FIX-01')
    after = (w.git(w.rec, 'worktree', 'list')[1], w.branches(w.rec), w.branches(w.kit))
    w.git(w.rec, 'branch', 'rec-fix-04', 'record')                              # a branch alone
    rc2, o2 = w.tool('worktree', 'open', 'FIX-04')
    folder_made = os.path.exists(w.lh + '/work/FIX-04')
    os.makedirs(w.lh + '/work/FIX-06/record')                                   # a folder alone
    rc3, o3 = w.tool('worktree', 'open', 'FIX-06')
    branch_made = 'rec-fix-06' in w.branches(w.rec)
    ok = (rc1 == 3 and 'already exists' in o1 and before == after and rc2 == 3 and 'branch' in o2 and not folder_made
          and rc3 == 3 and 'folder' in o3 and not branch_made)
    return ok, ('open FIX-01 again: exit %d [%s], worktree list and both branch lists unchanged %s; branch rec-fix-04 alone: exit %d [%s], '
                'folder made %s; folder FIX-06/record alone: exit %d [%s], branch made %s' % (
                    rc1, first(o1), before == after, rc2, first(o2), folder_made, rc3, first(o3), branch_made))


def commits_row(ctx):
    w = world(ctx)
    base = w.tip(w.rec, 'record')
    start = start_epoch()
    kids = [spawn(w, ['goal', ctx['tree'], g, '5', str(start)], 'goal-%s.txt' % g) for g in ('FIX-01', 'FIX-02')]
    for p, _ in kids:
        p.communicate()
    caps = {g: lines_of(c) for g, (p, c) in zip(('FIX-01', 'FIX-02'), kids)}
    ok = True
    parts = []
    retries = 0
    # KIT-11 C4 (b): with the goals' worktrees present the pending step-log and state lines land through loop-record-merge, which commits
    # them first (subject "step log and state lines before merging", trailer Goal:), on the record branch itself, on the record
    # repository's own work tree; the goals' branches carry only their notes
    pend_g = '--grep=step log and state lines before merging'
    rc, out = w.git(w.rec, 'log', '--no-merges', pend_g, '--format=%ct %(trailers:key=Goal,valueonly)', base + '..record')
    rows = [x.split() for x in out.split('\n') if x.strip()]
    stamps = [int(r[0]) for r in rows]
    rc, names = w.git(w.rec, 'log', '--no-merges', pend_g, '--name-only', '--format=', base + '..record')
    touched = sorted(set(x.strip() for x in names.split('\n') if x.strip()))
    rc, mout = w.git(w.rec, 'log', '--merges', '--format=%(trailers:key=Goal,valueonly)', base + '..record')
    merges = sorted(mout.split())
    contained = all(w.git(w.rec, 'merge-base', '--is-ancestor', 'rec-' + g.lower(), 'record')[0] == 0 for g in ('FIX-01', 'FIX-02'))
    notes_only = all(sorted(x for x in w.git(w.rec, 'diff', '--name-only', base, 'rec-' + g.lower())[1].split('\n') if x.strip()) ==
                     ['docs/step-%s-%d.md' % (g.lower(), i) for i in range(1, 6)] for g in ('FIX-01', 'FIX-02'))
    for g in ('FIX-01', 'FIX-02'):
        ls = caps[g]
        good = (len(ls) == 5 and all(' journal_rc=0 note_rc=0 merge_rc=0 ' in x and 'merged' in x and 'pending_lines_commit=none' not in x
                                     and 'pending_lines_commit=' in x for x in ls) and not any('index.lock' in x for x in ls))
        for x in ls:
            m = re.search(r'index_lock_retries=(\d+)', x)
            retries += int(m.group(1)) if m else 0
        landed = sum(1 for r in rows if len(r) == 2 and r[1] == g)
        ok = ok and good and landed == 5
        parts.append('%s: %d steps, %d with the journal, note and merge exits 0, a "merged" line naming a pending-lines commit and no index.lock text, '
                     '%d pending-lines commits on the record branch with the Goal: %s trailer' % (
                         g, len(ls), sum(1 for x in ls if ' journal_rc=0 note_rc=0 merge_rc=0 ' in x and 'merged' in x), landed, g))
    span = (max(stamps) - min(stamps)) if stamps else -1
    j = w.git(w.rec, 'show', 'HEAD:docs/JOURNAL.md')[1]
    in_log = sum(len(re.findall(r'^- \S+ %s ' % g, j, re.M)) for g in ('FIX-01', 'FIX-02'))
    scan = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_scan.py', '--range', base + '..record'], capture_output=True, cwd=w.rec,
                          env=w.env(), stdin=subprocess.DEVNULL)
    sm = re.search(rb'\bhits=(\d+)', scan.stdout)
    ok = (ok and len(rows) == 10 and 0 <= span < 600 and retries == 0 and touched == ['docs/JOURNAL.md', 'docs/STATE.md'] and contained
          and notes_only and merges == ['FIX-01'] * 5 + ['FIX-02'] * 5 and in_log == 10 and w.pending() == []
          and sm is not None and int(sm.group(1)) == 0 and scan.returncode == 0)
    return ok, ('%s; %d pending-lines commits since the base tip, commit timestamps span %d s (under 600); the ten touch only %s; merge commits with '
                'the Goal trailer %s; both goal branches contained in the record branch %s and carrying only their five notes %s; step-log lines of '
                'both goals in the committed docs/JOURNAL.md: %d (10 expected); record work tree clean %s; independent loop_scan.py --range hits=%s; '
                'index_lock_retries total %d; JOURNAL_FILE at the record work tree, the lines appended by the real step-log tool, each step a note '
                'committed in the goal worktree and loop-record-merge run from it; both children released at one epoch second and taking turns per step' % (
                    '; '.join(parts), len(rows), span, touched, merges, contained, notes_only, in_log, w.pending() == [],
                    sm.group(1).decode() if sm else 'none', retries))


def merge_row(ctx):
    w = world(ctx)
    t0 = w.tip(w.rec, 'record')
    res, dirty = {}, {}
    for g in ('FIX-01', 'FIX-02'):
        # the goal's own branch gets a note, committed in its worktree through the helper (the branch carries no step-log or state change)
        gw = w.wtpath(g, 'record')
        write_text(gw + '/docs/note-%s.md' % g.lower(), 'note of %s\n' % g)
        nrc, _ = w.tool('record_commit', g, '-m', 'docs(record): note of %s' % g.lower(), '--', 'docs/note-%s.md' % g.lower(), cwd=gw)
        # the live shape: a line from the real step-log tool and an edit of the goal's own subsection, both left uncommitted before the merge
        w.append_step(g, 'NOTE written before the merge')
        w.edit_state(g, '- merge pending')
        dirty[g] = (nrc, w.pending())
        res[g] = w.tool('record_merge', g)
    (r1, o1), (r2, o2) = res['FIX-01'], res['FIX-02']
    t1 = w.tip(w.rec, 'record')
    trailers = w.git(w.rec, 'log', '--merges', '--format=%(trailers:key=Goal,valueonly)', t0 + '..' + t1)[1].split()
    scan = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_scan.py', '--range', t0 + '..' + t1], capture_output=True, cwd=w.rec,
                          env=w.env(), stdin=subprocess.DEVNULL)
    m = re.search(rb'\bhits=(\d+)', scan.stdout)
    j = (read_bytes(w.rec + '/docs/JOURNAL.md') or b'').decode('utf-8', 'replace')
    st = (read_bytes(w.rec + '/docs/STATE.md') or b'').decode('utf-8', 'replace')
    n1, n2 = len(re.findall(r'^- \S+ FIX-01 ', j, re.M)), len(re.findall(r'^- \S+ FIX-02 ', j, re.M))
    contained = all(w.git(w.rec, 'merge-base', '--is-ancestor', 'rec-' + g, 'record')[0] == 0 for g in ('fix-01', 'fix-02'))
    clean = w.git(w.rec, 'status', '--porcelain', '--untracked-files=no')[1] == ''
    st_ok = '### FIX-01\n- merge pending\n' in st and '### FIX-02\n- merge pending\n' in st
    pend = w.git(w.rec, 'log', '--no-merges', '--format=%s %(trailers:key=Goal,valueonly)', t0 + '..' + t1)[1]
    pend_ok = sorted(x for x in pend.split('\n') if 'step log and state lines before merging' in x) == [
        'chore(record): step log and state lines before merging rec-fix-01 FIX-01', 'chore(record): step log and state lines before merging rec-fix-02 FIX-02']
    want = ['docs/JOURNAL.md', 'docs/STATE.md']
    was_dirty = all(dirty[g][0] == 0 and dirty[g][1] == want for g in dirty)
    ok = (r1 == 0 and r2 == 0 and sorted(trailers) == ['FIX-01', 'FIX-02'] and m is not None and int(m.group(1)) == 0 and scan.returncode == 0
          and n1 == 6 and n2 == 6 and contained and clean and st_ok and was_dirty and pend_ok
          and 'range_scan_hits=0' in o1 and 'range_scan_hits=0' in o2 and 'pending_lines_commit=none' not in o1 + o2)
    return ok, ('precondition before each merge: the helper committed the goal note (exit %s,%s) and the record work tree held exactly %s '
                'uncommitted (step-log line from the real tool, STATE edit of the goal\'s own subsection) %s; merge exits %d,%d [%s]; merge '
                'commits since the old tip carry Goal trailers %s; each merge committed the pending lines first with the goal trailer %s; '
                'independent loop_scan.py --range old..new hits=%s exit %d; merged step log holds FIX-01 lines %d and FIX-02 lines %d (6 and 6 '
                'expected, no union driver); both STATE.md subsections kept %s; both branches contained %s; tree clean %s' % (
                    dirty['FIX-01'][0], dirty['FIX-02'][0], dirty['FIX-01'][1], was_dirty, r1, r2, first(o2)[:150], sorted(trailers), pend_ok,
                    m.group(1).decode() if m else 'none', scan.returncode, n1, n2, st_ok, contained, clean))


def journal_check_row(ctx):
    w = world(ctx)
    jf = w.rec + '/docs/JOURNAL.md'
    outs = {}
    for g in ('FIX-01', 'FIX-02'):
        outs[g] = w.tool('journal', '--check', g, '--file', jf, '--plan', '%s/goals/%s/plan.md' % (w.lh, g))
    cp = fwd(w.base + '/journal-no-rollback.log')
    text = (read_bytes(jf) or b'').decode('utf-8', 'replace')
    write_text(cp, ''.join(x + '\n' for x in text.split('\n') if x and 'FIX-01 T01 ROLLBACK' not in x))
    crc, cout = w.tool('journal', '--check', 'FIX-01', '--file', cp, '--plan', '%s/goals/FIX-01/plan.md' % w.lh)
    ok = (all(o[0] == 0 and 'writer PASS 1' in o[1] and 'missing ROLLBACK 0' in o[1] for o in outs.values()) and crc == 1
          and 'missing ROLLBACK 1' in cout)
    return ok, ('loop-journal --check on the merged throwaway step log: FIX-01 exit %d [%s]; FIX-02 exit %d [%s]; control, a copy without the '
                'FIX-01 ROLLBACK line: exit %d [%s]' % (outs['FIX-01'][0], first(outs['FIX-01'][1])[:100], outs['FIX-02'][0],
                                                        first(outs['FIX-02'][1])[:100], crc, first(cout)[:100]))


def close_row(ctx):
    w = world(ctx)
    f3 = w.wtpath('FIX-03', 'record')
    write_text(f3 + '/docs/f3.md', 'goal three note\n')
    c0, o0 = w.tool('record_commit', 'FIX-03', '-m', 'docs(record): f3 note', '--', 'docs/f3.md', cwd=f3)
    r1, p1 = w.tool('worktree', 'close', 'FIX-03')
    still = os.path.isdir(f3) and 'rec-fix-03' in w.branches(w.rec)
    m3, _ = w.tool('record_merge', 'FIX-03')
    f2 = w.wtpath('FIX-02', 'record')
    write_text(f2 + '/junk.txt', 'untracked\n')
    r2, p2 = w.tool('worktree', 'close', 'FIX-02')
    still2 = os.path.isdir(f2) and os.path.isdir(w.wtpath('FIX-02', 'kit'))
    os.remove(f2 + '/junk.txt')
    r3, p3 = w.tool('worktree', 'close', 'FIX-03')
    gone3 = not os.path.exists(w.wtpath('FIX-03', 'record'))
    br = w.branches(w.rec)
    kb0 = w.branches(w.kit)
    r4, p4 = w.tool('worktree', 'close', 'FIX-01')
    gone1 = not os.path.exists(w.wtpath('FIX-01', 'record')) and not os.path.exists(w.wtpath('FIX-01', 'kit'))
    r5, p5 = w.tool('worktree', 'close', 'FIX-08')
    kept = 'rec-fix-01' in w.branches(w.rec) and 'rec-fix-03' in w.branches(w.rec) and 'fix-01' in w.branches(w.kit)
    ok = (c0 == 0 and r1 == 3 and 'not merged' in p1 and still and m3 == 0 and r2 == 3 and 'uncommitted' in p2 and still2 and r3 == 0 and gone3
          and r4 == 0 and gone1 and r5 == 3 and kept and 'rec-fix-03' in br and sorted(kb0) == sorted(w.branches(w.kit)) and 'fix-02' in w.branches(w.kit))
    return ok, ('FIX-03 closed before its merge: exit %d [%s], worktree and branch kept %s; after loop-record-merge exit %d; FIX-02 dirty '
                '(untracked file): exit %d [%s], both worktrees kept %s; FIX-03 clean after merge: exit %d, folder gone %s; FIX-01 (record+kit): exit %d, '
                'both folders gone %s; never opened FIX-08: exit %d; branches rec-fix-01, rec-fix-03 and kit fix-01 still listed %s' % (
                    r1, first(p1)[:90], still, m3, r2, first(p2)[:90], still2, r3, gone3, r4, gone1, r5, kept))


def conflict_row(ctx):
    w = World(ctx, 'conflict', ('FIX-03', 'FIX-04'))
    for g in ('FIX-03', 'FIX-04'):
        w.tool('worktree', 'open', g)
    pre = []
    for g, word in (('FIX-03', 'beta'), ('FIX-04', 'gamma')):
        f = w.wtpath(g, 'record')
        write_text(f + '/docs/NOTES.md', word + '\n')
        pre.append(w.tool('record_commit', g, '-m', 'docs(record): notes %s' % word, '--', 'docs/NOTES.md', cwd=f)[0])
    m1, o1 = w.tool('record_merge', 'FIX-03')
    t0 = w.tip(w.rec, 'record')
    notes0 = read_bytes(w.rec + '/docs/NOTES.md')
    m2, o2 = w.tool('record_merge', 'FIX-04')
    t1 = w.tip(w.rec, 'record')
    notes1 = read_bytes(w.rec + '/docs/NOTES.md')
    st = w.git(w.rec, 'status', '--porcelain', '--untracked-files=no')[1]
    merging = os.path.exists(w.rec + '/.git/MERGE_HEAD')
    ok = pre == [0, 0] and m1 == 0 and m2 != 0 and t0 == t1 and notes0 == notes1 == b'beta\n' and st == '' and not merging and 'conflict' in o2
    return ok, ('precondition: both commits exit %s and the first merge exit %d (a pass of this row needs them); second merge of the same line: '
                'exit %d [%s]; record tip %s before and %s after (equal %s); NOTES.md bytes unchanged %s; status clean %s; MERGE_HEAD left %s' % (
                    pre, m1, m2, first(o2)[:110], t0[:12], t1[:12], t0 == t1, notes0 == notes1, st == '', merging))


def conflict_live_row(ctx):
    """F1: a conflicted merge in the live shape (step-log line and own state line uncommitted) leaves the tip and the pending lines as they were."""
    w = World(ctx, 'conflictlive', ('FIX-03', 'FIX-04', 'FIX-05'))
    # FIX-05 is never opened: its no-path call below runs with no goal worktree present (KIT-11 C4 (b)); its state subsection is set up here
    write_text(w.rec + '/docs/STATE.md', (read_bytes(w.rec + '/docs/STATE.md') or b'').decode('utf-8') + '### FIX-05\n- none\n')
    w.git(w.rec, 'add', '--', 'docs/STATE.md')
    assert w.git(w.rec, 'commit', '-q', '-m', 'chore(fixture): a subsection for a goal that stays unopened')[0] == 0
    for g in ('FIX-03', 'FIX-04'):
        w.tool('worktree', 'open', g)
    pre = []
    for g, word in (('FIX-03', 'beta'), ('FIX-04', 'gamma')):
        f = w.wtpath(g, 'record')
        write_text(f + '/docs/NOTES.md', word + '\n')
        pre.append(w.tool('record_commit', g, '-m', 'docs(record): notes %s' % word, '--', 'docs/NOTES.md', cwd=f)[0])
    jf, sf = w.rec + '/docs/JOURNAL.md', w.rec + '/docs/STATE.md'
    # control 1: a clean merge in the live shape lands the pending lines
    w.append_step('FIX-03', 'NOTE written before the merge')
    w.edit_state('FIX-03', '- merge pending')
    pend3 = w.pending()
    m1, o1 = w.tool('record_merge', 'FIX-03')
    landed = ('FIX-03 T01 NOTE written before the merge' in w.git(w.rec, 'show', 'HEAD:docs/JOURNAL.md')[1]
              and '### FIX-03\n- merge pending\n' in w.git(w.rec, 'show', 'HEAD:docs/STATE.md')[1] + '\n')
    clean1 = w.pending() == []
    # the row: the same kind of merge, now conflicted (FIX-04 changes the line FIX-03 changed), the live shape left uncommitted
    w.append_step('FIX-04', 'NOTE written before the merge')
    w.edit_state('FIX-04', '- merge pending')
    t0, p0, jb, sb = w.tip(w.rec, 'record'), w.pending(), read_bytes(jf), read_bytes(sf)
    m2, o2 = w.tool('record_merge', 'FIX-04')
    t1, p1, jb1, sb1 = w.tip(w.rec, 'record'), w.pending(), read_bytes(jf), read_bytes(sf)
    staged = w.git(w.rec, 'diff', '--cached', '--name-only')[1]
    merging = os.path.exists(w.rec + '/.git/MERGE_HEAD')
    ok_live = (m2 != 0 and 'conflict' in o2 and t0 == t1 and p0 == p1 == ['docs/JOURNAL.md', 'docs/STATE.md'] and jb == jb1 and sb == sb1
               and staged == '' and not merging and 'unchanged' in o2 and 'uncommitted' in o2)
    # control 2: the same conflict on a clean tree. With FIX-04's worktree present the no-path call refuses (KIT-11 C4 (b)), so the live
    # shape is cleared (FIX-04's pending lines restored, as asserted above they were untouched by the conflicted merge) and a pending
    # step-log line and own state line of FIX-05, whose worktree is absent, are committed through the helper with no path
    w.git(w.rec, 'checkout', '--', 'docs/JOURNAL.md', 'docs/STATE.md')
    w.append_step('FIX-05', 'NOTE written before the commit')
    w.edit_state('FIX-05', '- commit pending')
    c, oc = w.tool('record_commit', 'FIX-05', '-m', 'chore(record): pending lines')
    t2, p2 = w.tip(w.rec, 'record'), w.pending()
    m3, o3 = w.tool('record_merge', 'FIX-04')
    t3, p3, merging3 = w.tip(w.rec, 'record'), w.pending(), os.path.exists(w.rec + '/.git/MERGE_HEAD')
    ok_clean = c == 0 and p2 == [] and m3 != 0 and 'conflict' in o3 and t2 == t3 and p3 == [] and not merging3
    ok = (pre == [0, 0] and pend3 == ['docs/JOURNAL.md', 'docs/STATE.md'] and m1 == 0 and landed and clean1 and ok_live and ok_clean)
    return ok, ('precondition: both notes committed %s and the live shape held for the clean control (%s); control, a clean merge with pending lines: '
                'exit %d, the pending step-log and state lines landed %s, tree clean %s; live-shape conflicted merge: exit %d [%s], tip %s before and '
                '%s after (equal %s), pending %s before and after (equal %s), step log and state file bytes unchanged %s, nothing staged %s, '
                'MERGE_HEAD left %s; control, the same conflict on a clean tree: helper exit %d, merge exit %d [%s], tip unchanged %s, tree clean %s' % (
                    pre, pend3, m1, landed, clean1, m2, first(o2)[:150], t0[:12], t1[:12], t0 == t1, p1, p0 == p1, jb == jb1 and sb == sb1,
                    staged == '', merging, c, m3, first(o3)[:80], t2 == t3, p3 == []))


def state_case(w, base, text):
    """Reset the throwaway record repository to base, put text in the state file, call the helper as FIX-01:
    (exit, output, tip before, tip after, staged paths, committed text)."""
    w.git(w.rec, 'reset', '-q', '--hard', base)
    write_text(w.rec + '/docs/STATE.md', text)
    t0 = w.tip(w.rec, 'record')
    rc, out = w.tool('record_commit', 'FIX-01', '-m', 'chore(record): state edit')
    raw = subprocess.run(['git', 'show', 'HEAD:docs/STATE.md'], cwd=w.rec, capture_output=True, env=w.env(), stdin=subprocess.DEVNULL)
    return rc, out, t0, w.tip(w.rec, 'record'), w.git(w.rec, 'diff', '--cached', '--name-only')[1], raw.stdout.decode('utf-8', 'replace').replace('\r', '')


def state_base(w, text):
    write_text(w.rec + '/docs/STATE.md', text)
    w.git(w.rec, 'add', '--', 'docs/STATE.md')
    assert w.git(w.rec, 'commit', '-q', '-m', 'chore(fixture): state')[0] == 0
    return w.tip(w.rec, 'record')


def section5_template_row(ctx):
    """F2 on the kit's own state template: section 5 is its last section."""
    w = World(ctx, 'sec5tpl', ('FIX-01',))
    tpl = (read_bytes(ctx['tree'] + '/templates/STATE.md') or b'').decode('utf-8').replace('\r', '')
    if not tpl.endswith('\n'):
        tpl += '\n'
    ls = tpl.split('\n')
    h5 = [i for i, x in enumerate(ls) if re.match(r'^## 5([. ]|$)', x)]
    t4 = '(none)\n## 5'
    if len(h5) != 1 or t4 not in tpl:
        return False, 'the template has %d section-5 headings (1 expected) or no "(none)" line closing section 4' % len(h5)
    i5 = h5[0]
    own = '### FIX-01\n- own line\n'
    base = state_base(w, tpl)
    res = {}
    res['append'] = state_case(w, base, tpl + own)                                       # own subsection appended at the end
    nonl = tpl.rstrip('\n')
    res['nonl'] = state_case(w, state_base(w, nonl), nonl + '\n' + own)                   # same, the committed file has no final newline
    base = state_base(w, tpl)
    res['under'] = state_case(w, base, '\n'.join(ls[:i5 + 1] + ['a line under the heading'] + ls[i5 + 1:]))
    res['drift'] = state_case(w, base, '\n'.join(ls[:-2] + ['drift line: a thing'] + ['']))          # the last section-5 line replaced
    res['head'] = state_case(w, base, tpl.replace(ls[i5], ls[i5] + ' edited', 1))
    res['ctrl'] = state_case(w, base, tpl.replace('(none)\n## 5', '(a trap)\n## 5', 1))    # control: an edit in section 4
    res['subhead'] = state_case(w, base, tpl + own + '### FIX-02\n- peer line\n')           # the peer's new subsection stays uncommitted

    def refused(k, part):
        r = res[k]
        return r[0] == 3 and part in r[1] and 'nothing was committed' in r[1] and r[2] == r[3] and r[4] == ''
    a, n, s = res['append'], res['nonl'], res['subhead']
    ok = (a[0] == 0 and a[2] != a[3] and a[5] == tpl + own and n[0] == 0 and n[5] == nonl + '\n' + own
          and refused('under', 'before its first') and refused('drift', 'before its first') and refused('head', 'heading line')
          and refused('ctrl', 'outside section 5') and s[0] == 0 and s[5] == tpl + own)
    return ok, ('on a copy of the state template (%d lines, section 5 last): own subsection appended at the end: exit %d, committed text is the template '
                'plus the subsection %s; same with a committed file that has no final newline: exit %d, committed text as expected %s; a line under the '
                'heading: exit %d [%s]; a drift line replacing the section-5 text: exit %d [%s]; the heading line edited: exit %d [%s]; control, an edit in '
                'section 4: exit %d [%s]; own subsection plus a peer\'s new one: exit %d, only the own one committed %s; the four refusals left the tip '
                'unchanged and nothing staged %s' % (
                    len(ls) - 1, a[0], a[5] == tpl + own, n[0], n[5] == nonl + '\n' + own, res['under'][0], first(res['under'][1])[:120], res['drift'][0],
                    first(res['drift'][1])[:120], res['head'][0], first(res['head'][1])[:120], res['ctrl'][0], first(res['ctrl'][1])[:120], s[0],
                    s[5] == tpl + own, all(res[k][2] == res[k][3] and res[k][4] == '' for k in ('under', 'drift', 'head', 'ctrl'))))


def section5_live_row(ctx):
    """F2 on a fixture with the live heading shape, "## 5 Current goal (...)" with no dot."""
    w = World(ctx, 'sec5live', ('FIX-01',))
    head = '# STATE fixture\n## 4 Standing traps\n(none)\n## 5 Current goal (a goal is running)\nstatus: running\n'
    tail = '## 6 Notes\n(none)\n'
    sub = '### FIX-01\n- none\n### FIX-02\n- none\n'
    res = {}
    base = state_base(w, head + sub + tail)
    res['edit'] = state_case(w, base, head + '### FIX-01\n- edited by FIX-01 (its own)\n### FIX-02\n- none\n' + tail)
    res['under'] = state_case(w, base, head.replace('status: running\n', 'status: running\na line under the heading\n') + sub + tail)
    res['head'] = state_case(w, base, head.replace('(a goal is running)', '(edited)') + sub + tail)
    res['ctrl'] = state_case(w, base, head.replace('## 4 Standing traps\n(none)', '## 4 Standing traps\n(a trap)') + sub + tail)   # control: section 4
    res['six'] = state_case(w, base, head + sub + tail.replace('(none)', '(a note)'))                                              # section 6 is outside
    base2 = state_base(w, head + tail)
    res['new'] = state_case(w, base2, head + '### FIX-01\n- own line\n' + tail)                                                      # own subsection, new, before ## 6
    nonl = (head + '### FIX-02\n- peer\n').rstrip('\n')
    res['nonl'] = state_case(w, state_base(w, nonl), nonl + '\n### FIX-01\n- own line')                                           # section 5 last, no final newline

    def refused(k, part):
        r = res[k]
        return r[0] == 3 and part in r[1] and 'nothing was committed' in r[1] and r[2] == r[3] and r[4] == ''
    e, nw, nl = res['edit'], res['new'], res['nonl']
    ok = (e[0] == 0 and e[2] != e[3] and e[5] == head + '### FIX-01\n- edited by FIX-01 (its own)\n### FIX-02\n- none\n' + tail
          and nw[0] == 0 and nw[5] == head + '### FIX-01\n- own line\n' + tail
          and nl[0] == 0 and nl[5] == nonl + '\n### FIX-01\n- own line'
          and refused('under', 'before its first') and refused('head', 'heading line') and refused('ctrl', 'outside section 5')
          and refused('six', 'outside section 5'))
    return ok, ('heading shape "## 5 Current goal (...)": an edit inside the own subsection: exit %d, committed text as expected %s; a new own subsection '
                'before "## 6": exit %d, committed as expected %s; section 5 last with no final newline: exit %d, committed as expected %s; a line under '
                'the heading: exit %d [%s]; the heading edited: exit %d [%s]; control, an edit in section 4: exit %d [%s]; an edit in section 6: exit %d '
                '[%s]; each refusal left the tip unchanged and nothing staged %s' % (
                    e[0], e[5] == head + '### FIX-01\n- edited by FIX-01 (its own)\n### FIX-02\n- none\n' + tail, nw[0],
                    nw[5] == head + '### FIX-01\n- own line\n' + tail, nl[0], nl[5] == nonl + '\n### FIX-01\n- own line', res['under'][0],
                    first(res['under'][1])[:110], res['head'][0], first(res['head'][1])[:110], res['ctrl'][0], first(res['ctrl'][1])[:110],
                    res['six'][0], first(res['six'][1])[:110],
                    all(res[k][2] == res[k][3] and res[k][4] == '' for k in ('under', 'head', 'ctrl', 'six'))))


def indexlock_row(ctx):
    w = World(ctx, 'indexlock', ('FIX-05', 'FIX-06'))     # FIX-06 is never opened: the no-path pair below runs with no goal worktree present
    w.tool('worktree', 'open', 'FIX-05')
    folder = w.wtpath('FIX-05', 'record')
    rawn, pairn, tries = (int(os.environ.get(k, d)) for k, d in (('K10C4_RAW_N', '25'), ('K10C4_PAIR_N', '8'), ('K10C4_TRIES', '3')))
    seen = []
    for t in range(1, tries + 1):
        start = start_epoch()
        kids = [spawn(w, ['commit', 'raw', ctx['tree'], folder, tag + str(t), str(rawn), str(start), 'FIX-05'], 'raw-%s%d.txt' % (tag, t)) for tag in 'AB']
        for p, _ in kids:
            p.communicate()
        errs = sum(1 for _, c in kids for x in lines_of(c) if x.endswith('indexlock=1'))
        calls = sum(len(lines_of(c)) for _, c in kids)
        seen.append((t, calls, errs))
        if errs:
            break
    reproduced = any(e for _, _, e in seen)
    start = start_epoch()
    kids = [spawn(w, ['commit', 'help', ctx['tree'], folder, tag, str(pairn), str(start), 'FIX-05'], 'help-%s.txt' % tag) for tag in 'AB']
    for p, _ in kids:
        p.communicate()
    hl = [x for _, c in kids for x in lines_of(c)]
    lock_ok = len(hl) == 2 * pairn and all(' commit=0 ' in x and 'indexlock=0' in x for x in hl)
    retries = sum(int(m.group(1)) for x in hl for m in [re.search(r'retries=(\d+)', x)] if m)
    landed = sum(1 for x in w.git(folder, 'log', '--format=%s', 'record..HEAD')[1].split('\n') if x.startswith('chore(record): help '))
    start = start_epoch()                                  # the same forced second pair, on the record work tree: step-log line, then the helper
    kids = [spawn(w, ['pair', ctx['tree'], tag, str(pairn), str(start), 'FIX-06'], 'pair-%s.txt' % tag) for tag in 'AB']
    for p, _ in kids:
        p.communicate()
    pl = [x for _, c in kids for x in lines_of(c)]
    pair_ok = len(pl) == 2 * pairn and all(' journal=0 commit=0 ' in x and 'indexlock=0' in x for x in pl)
    pretries = sum(int(m.group(1)) for x in pl for m in [re.search(r'retries=(\d+)', x)] if m)
    jtxt = w.git(w.rec, 'show', 'HEAD:docs/JOURNAL.md')[1]
    in_log = len(re.findall(r'^- \S+ FIX-06 T01 NOTE pair ', jtxt, re.M))
    pair_ok = pair_ok and in_log == 2 * pairn and w.pending() == []
    ok = lock_ok and retries == 0 and landed >= 2 * pairn and pair_ok
    say = ('unlocked pair REPRODUCED the index.lock failure: %s' % ', '.join('try %d: %d calls, %d with index.lock' % s for s in seen) if reproduced
           else 'unlocked pair COULD NOT reproduce index.lock in %d tries (%s); the lock is kept' % (
               tries, ', '.join('try %d: %d calls, 0 failed' % (s[0], s[1]) for s in seen)))
    return ok, ('%s; the same forced-second pair of %d processes x %d commits through loop-record-commit on that worktree: %d calls, all exit 0 '
                'with no index.lock text %s, index_lock_retries %d, %d commits landed on the branch; the same pair on the record work tree (a step-log line '
                'from the real tool, then loop-record-commit with no path for a goal with no worktree, no turn taken): %d calls, all exit 0 with no index.lock text %s, '
                'index_lock_retries %d, step-log lines in the committed log %d (%d expected), record work tree clean %s' % (
                    say, 2, pairn, len(hl), lock_ok, retries, landed, len(pl), pair_ok, pretries, in_log, 2 * pairn, w.pending() == []))


def section5_row(ctx):
    w = World(ctx, 'sec5', ('FIX-01', 'FIX-02'))
    sp = w.rec + '/docs/STATE.md'

    def edit_title():
        write_text(sp, (read_bytes(sp) or b'').decode('utf-8').replace('# STATE fixture\n', '# STATE fixture, edited by hand\n', 1))
    t0 = w.tip(w.rec, 'record')
    edit_title()                                                                # an edit outside section 5
    rc1, o1 = w.tool('record_commit', 'FIX-01', '-m', 'chore(record): state edit')
    t1, d1, st1 = w.tip(w.rec, 'record'), w.pending(), w.git(w.rec, 'diff', '--cached', '--name-only')[1]
    w.git(w.rec, 'checkout', '--', 'docs/STATE.md')
    w.edit_state('FIX-01', '- edited by FIX-01 (its own)')                    # control: the same call, the goal's own subsection
    rc2, o2 = w.tool('record_commit', 'FIX-01', '-m', 'chore(record): state edit')
    t2 = w.tip(w.rec, 'record')
    tr = w.git(w.rec, 'log', '-1', '--format=%(trailers:key=Goal,valueonly)')[1]
    files = w.git(w.rec, 'show', '--name-only', '--format=', 'HEAD')[1]
    w.edit_state('FIX-01', '- second own edit')                                 # a mix of its own subsection and a line outside section 5
    edit_title()
    rc3, o3 = w.tool('record_commit', 'FIX-01', '-m', 'chore(record): state edit')
    t3, st3 = w.tip(w.rec, 'record'), w.git(w.rec, 'diff', '--cached', '--name-only')[1]
    ok = (rc1 == 3 and 'outside section 5' in o1 and 'nothing was committed' in o1 and t0 == t1 and d1 == ['docs/STATE.md'] and st1 == ''
          and rc2 == 0 and t2 != t1 and tr == 'FIX-01' and files == 'docs/STATE.md' and rc3 == 3 and 'outside section 5' in o3 and t3 == t2
          and st3 == '')
    return ok, ('FIX-01 calls the helper with a line outside section 5 edited: exit %d [%s], record tip %s before and %s after (equal %s), STATE.md '
                'still uncommitted %s, nothing left staged %s; control, the file restored and FIX-01\'s own subsection edited, the same call: exit %d, '
                'tip moved %s, commit touches %s, Goal trailer %s; a mix of its own subsection and an outside line: exit %d [%s], tip unchanged %s, '
                'nothing left staged %s' % (
                    rc1, first(o1)[:150], t0[:12], t1[:12], t0 == t1, d1 == ['docs/STATE.md'], st1 == '', rc2, t2 != t1, files, tr, rc3,
                    first(o3)[:90], t3 == t2, st3 == ''))


def twogoals_row(ctx):
    w = World(ctx, 'twogoals', ('FIX-01', 'FIX-02'))
    sp = w.rec + '/docs/STATE.md'
    t0 = w.tip(w.rec, 'record')
    w.append_step('FIX-01', 'NOTE step of the first goal')
    w.append_step('FIX-02', 'NOTE step of the second goal')
    w.edit_state('FIX-01', '- line of FIX-01')                                 # both goals hold an uncommitted edit of their own subsection
    w.edit_state('FIX-02', '- line of FIX-02')
    both = read_bytes(sp)
    rcA, oA = w.tool('record_commit', 'FIX-01', '-m', 'chore(record): FIX-01 state')
    tA = w.tip(w.rec, 'record')
    stA = (w.git(w.rec, 'show', 'HEAD:docs/STATE.md')[1])
    trA = w.git(w.rec, 'log', '-1', '--format=%(trailers:key=Goal,valueonly)')[1]
    kept = read_bytes(sp) == both and w.pending() == ['docs/STATE.md']         # B's edit is still uncommitted, the work tree file untouched
    a_ok = '- line of FIX-01' in stA and '- line of FIX-02' not in stA
    rcA2, oA2 = w.tool('record_commit', 'FIX-01', '-m', 'chore(record): FIX-01 state again')    # only the peer's edit pending: nothing to commit
    tA2 = w.tip(w.rec, 'record')
    rcB, oB = w.tool('record_commit', 'FIX-02', '-m', 'chore(record): FIX-02 state')
    tB = w.tip(w.rec, 'record')
    trB = w.git(w.rec, 'log', '-1', '--format=%(trailers:key=Goal,valueonly)')[1]
    stB = w.git(w.rec, 'show', 'HEAD:docs/STATE.md')[1]
    final = read_bytes(sp)
    b_ok = '- line of FIX-01' in stB and '- line of FIX-02' in stB and stB.replace('\r', '').strip() == (final or b'').decode('utf-8').replace('\r', '').strip()
    j = w.git(w.rec, 'show', 'HEAD:docs/JOURNAL.md')[1]
    ok = (rcA == 0 and tA != t0 and trA == 'FIX-01' and a_ok and kept and rcA2 == 0 and tA2 == tA and 'nothing pending' in oA2
          and rcB == 0 and tB != tA and trB == 'FIX-02' and b_ok and w.pending() == [] and 'FIX-01 T01 NOTE step' in j and 'FIX-02 T01 NOTE step' in j)
    return ok, ('both goals hold an uncommitted edit of their own section-5 subsection; FIX-01 calls the helper: exit %d, tip moved %s, Goal trailer %s, '
                'committed STATE.md holds FIX-01\'s line and not FIX-02\'s %s, work tree file byte-equal to before and only STATE.md pending %s; '
                'FIX-01 calls again with only FIX-02\'s edit pending: exit %d [%s], tip unchanged %s; FIX-02 calls: exit %d, tip moved %s, Goal '
                'trailer %s, committed STATE.md holds both lines and equals the work tree %s, work tree clean %s' % (
                    rcA, tA != t0, trA, a_ok, kept, rcA2, first(oA2)[:80], tA2 == tA, rcB, tB != tA, trB, b_ok, w.pending() == []))


def goalwt_row(ctx):
    w = World(ctx, 'goalwt', ('FIX-01', 'FIX-02'))
    w.tool('worktree', 'open', 'FIX-01')
    gw = w.wtpath('FIX-01', 'record')
    b0 = w.tip(w.rec, 'rec-fix-01')
    outs = []
    for rel in ('docs/JOURNAL.md', 'docs/STATE.md'):
        write_text(gw + '/' + rel, (read_bytes(gw + '/' + rel) or b'').decode('utf-8') + 'a line written in the goal worktree\n')
        outs.append(w.tool('record_commit', 'FIX-01', '-m', 'chore(record): in a goal worktree', '--', rel, cwd=gw))
    b1 = w.tip(w.rec, 'rec-fix-01')
    w.git(gw, 'checkout', '--', 'docs')
    write_text(gw + '/docs/note.md', 'a note\n')                                # control: another file, same worktree, same call
    rcc, oc = w.tool('record_commit', 'FIX-01', '-m', 'docs(record): a note', '--', 'docs/note.md', cwd=gw)
    b2 = w.tip(w.rec, 'rec-fix-01')
    write_text(gw + '/docs/JOURNAL.md', (read_bytes(gw + '/docs/JOURNAL.md') or b'').decode('utf-8') + 'a raw line\n')   # not through the helper
    w.git(gw, 'add', 'docs/JOURNAL.md')
    w.git(gw, 'commit', '-q', '-m', 'chore(raw): step log on a goal branch')
    t0 = w.tip(w.rec, 'record')
    rcm, om = w.tool('record_merge', 'FIX-01')
    t1 = w.tip(w.rec, 'record')
    ok = (all(r == 3 and 'only on the record branch' in o for r, o in outs) and b0 == b1 and rcc == 0 and b2 != b1 and rcm == 3
          and 'docs/JOURNAL.md' in om and t0 == t1 and w.git(w.rec, 'merge-base', '--is-ancestor', 'rec-fix-01', 'record')[0] != 0)
    return ok, ('in a goal worktree: the helper with docs/JOURNAL.md exit %d, with docs/STATE.md exit %d [%s], branch tip unchanged %s; control, '
                'docs/note.md in the same worktree: exit %d, tip moved %s; a raw commit of the step log on the branch, then loop-record-merge: '
                'exit %d [%s], record tip unchanged %s, branch not merged' % (
                    outs[0][0], outs[1][0], first(outs[0][1])[:140], b0 == b1, rcc, b2 != b1, rcm, first(om)[:110], t0 == t1))


def dirty_row(ctx):
    w = World(ctx, 'dirty', ('FIX-01',))
    w.tool('worktree', 'open', 'FIX-01')
    gw = w.wtpath('FIX-01', 'record')
    write_text(gw + '/docs/note.md', 'a note\n')
    nrc, _ = w.tool('record_commit', 'FIX-01', '-m', 'docs(record): a note', '--', 'docs/note.md', cwd=gw)
    write_text(w.rec + '/docs/NOTES.md', 'edited by hand\n')
    t0 = w.tip(w.rec, 'record')
    rc1, o1 = w.tool('record_merge', 'FIX-01')
    t1 = w.tip(w.rec, 'record')
    w.git(w.rec, 'checkout', '--', 'docs/NOTES.md')                             # control: the same merge with the file restored
    rc2, o2 = w.tool('record_merge', 'FIX-01')
    t2 = w.tip(w.rec, 'record')
    ok = nrc == 0 and rc1 == 3 and 'other than the step log' in o1 and t0 == t1 and rc2 == 0 and t2 != t1
    return ok, ('another tracked file dirty in the record work tree: merge exit %d [%s], tip %s before and %s after (equal %s); control, the file '
                'restored, the same merge: exit %d, tip moved %s' % (rc1, first(o1)[:120], t0[:12], t1[:12], t0 == t1, rc2, t2 != t1))


def lockfile_row(ctx):
    w = world(ctx)
    lock = w.rec + '/docs/JOURNAL.md.lock'
    st = w.git(w.rec, 'status', '--porcelain')[1]
    names = w.git(w.rec, 'log', '--all', '--name-only', '--format=')[1]
    tracked = w.git(w.rec, 'ls-files')[1]
    in_history = [x for x in names.split('\n') + tracked.split('\n') if x.strip().endswith('.lock')]
    ok = os.path.exists(lock) and 'docs/JOURNAL.md.lock' in st and not in_history
    return ok, ('control: the lock file beside the step log exists after the earlier rows %s and the work tree lists it untracked %s; names ending in '
                '.lock across every commit of every branch and in the index: %d' % (os.path.exists(lock), 'docs/JOURNAL.md.lock' in st, len(in_history)))


def dispatch_row(ctx):
    c2 = load_c2()
    w = World(ctx, 'dispatch', ('FIX-01', 'FIX-02', 'FIX-03'))
    w.git(w.rec, 'branch', 'rec-fix-02', 'record')                              # FIX-02 is refused: its branch exists with no worktree
    seen = {}

    def go(g):
        t = w.tool('dispatch', g, '--no-poll', '--min-free-mb', '1', extra={'LOOP_LEADER_STUB': STUB})
        return t

    def env_of(g, secs=40):
        end = time.time() + secs
        while time.time() < end:
            b = read_bytes(w.lh + '/stub/%s.env' % g)
            if b:
                return dict(x.split('=', 1) for x in b.decode('utf-8').split('\n') if '=' in x)
            time.sleep(0.3)
        return None
    try:
        r1, o1 = go('FIX-01')
        e1 = env_of('FIX-01')
        r3, o3 = go('FIX-03')
        e3 = env_of('FIX-03')
        r2, o2 = go('FIX-02')
        refused_clean = not os.path.exists(w.lh + '/current/FIX-02') and read_bytes(w.lh + '/stub/FIX-02.env') is None
        write_text(w.lh + '/stub/FIX-01.stop', 'stop\n')
        gone = c2.wait_counted(ctx, 'FIX-01', False, 30)
        os.remove(w.lh + '/stub/FIX-01.env')
        r4, o4 = go('FIX-01')
        e4 = env_of('FIX-01')
    finally:
        for g in ('FIX-01', 'FIX-02', 'FIX-03'):
            write_text(w.lh + '/stub/%s.stop' % g, 'stop\n')
        c2.wait_counted(ctx, 'FIX-01', False, 30)
        c2.wait_counted(ctx, 'FIX-03', False, 30)

    def same(a, b):
        return a is not None and fwd(a).lower() == fwd(b).lower()
    rec1, kit1 = w.wtpath('FIX-01', 'record'), w.wtpath('FIX-01', 'kit')
    ok1 = (r1 == 0 and e1 is not None and same(e1.get('LOOP_RECORD_WT'), rec1) and same(e1.get('LOOP_KIT_WT'), kit1) and e1.get('LOOP_GOAL') == 'FIX-01'
           and w.on_branch(rec1, 'rec-fix-01') and w.on_branch(kit1, 'fix-01'))
    ok3 = (r3 == 0 and e3 is not None and same(e3.get('LOOP_RECORD_WT'), w.wtpath('FIX-03', 'record')) and e3.get('LOOP_KIT_WT') == 'unset'
           and not os.path.exists(w.wtpath('FIX-03', 'kit')))
    ok2 = r2 == 7 and 'worktrees:' in o2 and refused_clean
    ok4 = gone and r4 == 0 and 'none, already there' in o4 and e4 is not None and same(e4.get('LOOP_RECORD_WT'), rec1) and same(e4.get('LOOP_KIT_WT'), kit1)
    return ok1 and ok3 and ok2 and ok4, (
        'FIX-01 (names the kit): exit %d, the stub read LOOP_RECORD_WT and LOOP_KIT_WT equal to its two worktrees and both are on their branches %s; '
        'FIX-03 (no kit): exit %d, the stub read LOOP_RECORD_WT set %s and LOOP_KIT_WT %s, no kit folder %s; FIX-02 (branch rec-fix-02 made first, no '
        'folder): exit %d [%s], no current file and no stub launched %s; FIX-01 dispatched again after its stub stopped (%s): exit %d [%s], the stub '
        'saw both again %s' % (
            r1, ok1, r3, e3 is not None and e3.get('LOOP_RECORD_WT') != 'unset', e3.get('LOOP_KIT_WT') if e3 else None, ok3, r2, first(o2)[:100],
            refused_clean, 'gone' if gone else 'NOT gone', r4, 'reused' if 'none, already there' in o4 else first(o4)[:60], ok4))


def sentence_row(ctx):
    res = []
    for rel in ('agents/loop-leader.md', 'templates/GOAL_PREAMBLE.md'):
        b = read_bytes(ctx['tree'] + '/' + rel)
        t = '' if b is None else b.decode('utf-8', 'replace').replace('\r', '')
        res.append((rel, SENT in t, t.count(SENT)))
    ok = all(f and n == 1 for _, f, n in res)
    return ok, 'sentence sha %s; ' % sha(SENT) + '; '.join('%s: found %s, %d time(s)' % r for r in res)


def manifest_row(ctx):
    mf = (read_bytes(ctx['tree'] + '/MANIFEST.txt') or b'').decode('utf-8', 'replace').replace('\r', '')
    lines = {x.split('\t')[0]: x.split('\t')[1] for x in mf.split('\n') if '\t' in x}
    bad = []
    for rel in NEW_BIN:
        b = read_bytes(ctx['tree'] + '/' + rel)
        if b is None:
            bad.append('%s absent' % rel)
        elif lines.get(rel) != shafull(b):
            bad.append('%s MANIFEST line %s' % (rel, 'absent' if rel not in lines else 'differs'))
    tw = read_bytes(ctx['tree'] + '/bin/loop-tripwire')
    for rel in NEW_BIN[:3]:
        if read_bytes(ctx['tree'] + '/' + rel) != tw or tw is None:
            bad.append('%s is not a byte copy of bin/loop-tripwire' % rel)
    rc = out = None
    try:
        cp = subprocess.run(['bash', ctx['tree'] + '/bin/loop-worktree'], capture_output=True, stdin=subprocess.DEVNULL, timeout=60,
                            env=make_env(ctx['home'] if os.path.isdir(ctx['home']) else ctx['work'], {'LOOP_PY': ctx['py']}, DROP))
        rc, out = cp.returncode, (cp.stdout + cp.stderr).decode('utf-8', 'replace')
    except (OSError, subprocess.SubprocessError) as exc:
        out = type(exc).__name__
    if rc != 64 or 'usage: loop-worktree' not in (out or ''):
        bad.append('launcher bin/loop-worktree with no argument gave exit %s, not 64 with the usage line' % rc)
    return not bad, ('six new bin files at their sha256 in MANIFEST.txt, three launchers byte-equal to bin/loop-tripwire (sha256 %s), launcher run '
                     'with no argument exits %s%s' % (shafull(tw)[:16] if tw else 'absent', rc, '' if not bad else '; PROBLEMS: ' + '; '.join(bad)))


def load_c2():
    if 'c2' not in ST:
        spec = importlib.util.spec_from_file_location('k10c2_run', ROWS + '/K10-C2/run.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ST['c2'] = mod
    return ST['c2']


CHECKS = {'open': open_row, 'open_twice': open_twice_row, 'commits': commits_row, 'merge': merge_row, 'journal_check': journal_check_row,
          'close': close_row, 'conflict': conflict_row, 'indexlock': indexlock_row, 'dispatch': dispatch_row, 'sentence': sentence_row,
          'manifest': manifest_row, 'section5': section5_row, 'conflict_live': conflict_live_row, 'section5_template': section5_template_row,
          'section5_live': section5_live_row, 'twogoals': twogoals_row, 'goalwt': goalwt_row, 'dirty': dirty_row, 'lockfile': lockfile_row}


def row_check(ctx, rid, expect, arg):
    ok, detail = CHECKS[arg](ctx)
    return ok, 'expected [%s] measured: %s' % (expect, hide(ctx, detail))


def main():
    tree, home, work = env_dirs(USAGE)
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K10-C4/run.py', HERE + '/run.py'), ('tests/rows/K10-C4/rows.txt', HERE + '/rows.txt'),
              ('tests/rows/K10-C4/stub_leader.py', HERE + '/stub_leader.py')) + tuple((r, tree + '/' + r) for r in NEW_BIN + ('bin/loop_dispatch.py',)))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    ctx['tmo'] = load_c2().find_timeout()
    print('info GNU timeout for the leader launch: %s' % ('found and proved by --version' if ctx['tmo'] else 'NOT FOUND, the dispatch row will refuse'))
    print('info worlds are constructed repositories under the work folder, never a clone of a real one')
    return tally(load_rows(HERE + '/rows.txt'), {'check': row_check}, (ctx,), True)


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == '--child':
        if sys.argv[2] == 'goal':
            child_goal(sys.argv[3], sys.argv[4], int(sys.argv[5]), int(sys.argv[6]))
        elif sys.argv[2] == 'pair':
            child_pair(sys.argv[3], sys.argv[4], int(sys.argv[5]), int(sys.argv[6]), sys.argv[7])
        else:
            child_commit(sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], int(sys.argv[7]), int(sys.argv[8]), sys.argv[9])
    sys.exit(main())
