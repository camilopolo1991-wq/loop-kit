#!/usr/bin/env python3
"""K10-C2 rows runner: a current file per goal, per-goal settle, guards read LOOP_GOAL when more than one goal is current.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test (its bin/ and hooks/ are the files run)
  LOOP_ROWS_HOME   unused here (every child gets its own throwaway home under LOOP_WORK); required by the shape of the runners
  LOOP_WORK        the work folder; every fixture is written under it and listed in k10c2-manifest.txt
  LOOP_PY          the interpreter the tools and the stub are run with (defaults to the one running this file)
  TIMEOUT_BIN      optional; a GNU timeout. Without it the runner looks for one on PATH and proves it by --version.

Every child gets HOME, USERPROFILE and LOOP_HOME at a throwaway home inside LOOP_WORK and PYTHONDONTWRITEBYTECODE=1
(make_env). The live home is never named. LOOP_GOAL, HERMES_HOME and every pin of the claude binary are removed from the
environment first.

Counting and MAX_LEADERS. The kit's counting (bin/loop_procs.py) reads the machine's process table, not the throwaway home,
so a leader running on the machine for another goal is counted by the dispatcher and by preflight. It is a different goal
id, so every per-goal count here is unaffected. The throwaway config.env sets MAX_LEADERS=9 so a leader running elsewhere
does not stop a fixture dispatch. Row C2c-6 reads the machine-wide count (the no-id settle's rule) and says which branch ran.

The launcher override is LOOP_LEADER_STUB (bin/loop_dispatch.py, resolve_claude): the leader argv becomes
<GNU timeout> <seconds> <interpreter> stub_leader.py <the real claude arguments>. LOOP_CLAUDE_BIN is pointed at a file that
does not exist in every dispatch child, so a dispatcher that does not know the override refuses instead of launching a real
claude. A tree whose dispatcher lacks the override therefore fails these rows with a refusal, and launches nothing.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, register, shafull, sha, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [TIMEOUT_BIN=<gnu timeout>] '
         'python run.py (no positional argument)')
MANIFEST = 'k10c2-manifest.txt'
DROP = ('LOOP_GOAL', 'HERMES_HOME', 'CLAUDE_BIN', 'LOOP_CLAUDE_BIN', 'LOOP_LEADER_STUB', 'MAX_LEADERS', 'MIN_FREE_MB',
        'REPORT_SEND_CMD', 'JOURNAL_FILE', 'LOOP_GUARD_MODE', 'LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_PY', 'ENGINE_RECORD_DIR')
HERE = os.path.dirname(os.path.abspath(__file__))
STUB = fwd(HERE + '/stub_leader.py')
A, B = 'FIX-01', 'FIX-02'
GOAL_MD = '# %s: constructed fixture goal\n' + 'Acceptance criteria:\n1. a constructed line that is only here to make the file longer than a stub\n' * 6
ST = {}   # shared state between rows: the two-goal world


def find_timeout():
    cands = []
    if os.environ.get('TIMEOUT_BIN'):
        cands.append(os.environ['TIMEOUT_BIN'])
    for d in os.environ.get('PATH', '').split(os.pathsep):
        for n in ('timeout.exe', 'timeout'):
            cands.append(os.path.join(d, n))
    for c in cands:
        if not os.path.isfile(c):
            continue
        try:
            r = subprocess.run([c, '--version'], capture_output=True, text=True, timeout=15)
        except Exception:
            continue
        if r.returncode == 0 and 'coreutils' in (r.stdout + r.stderr).lower():
            return fwd(c)
    return None


class World:
    def __init__(self, ctx, tag, goals=(A, B), current_goal=None):
        self.ctx = ctx
        self.base = '%s/k10c2-fixtures/%s-%d' % (ctx['work'], tag, time.time_ns())
        register(ctx['work'], MANIFEST, self.base)
        self.home = self.base + '/home'
        self.lh = self.home + '/.loop'
        os.makedirs(self.lh + '/stub')
        os.makedirs(self.base + '/tmp')
        write_text(self.lh + '/config.env', 'MAX_LEADERS=9\n')
        for g in goals:
            os.makedirs(self.lh + '/goals/' + g)
            write_text(self.lh + '/goals/%s/GOAL.md' % g, GOAL_MD % g)
        if current_goal:
            write_text(self.lh + '/current_goal', current_goal + '\n')

    def env(self, extra=None, drop=()):
        e = {'TEMP': self.base + '/tmp', 'TMP': self.base + '/tmp', 'TIMEOUT_BIN': self.ctx['tmo'] or '',
             'LOOP_CLAUDE_BIN': self.lh + '/no-such-claude'}
        e.update(extra or {})
        return make_env(self.home, e, DROP + tuple(drop))

    def run(self, argv, extra=None, drop=(), stdin=None):
        kw = {'input': stdin} if stdin is not None else {'stdin': subprocess.DEVNULL}
        cp = subprocess.run([self.ctx['py']] + argv, capture_output=True, env=self.env(extra, drop), cwd=self.base, **kw)
        return cp.returncode, (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '')

    def dispatch(self, gid):
        return self.run([self.ctx['tree'] + '/bin/loop_dispatch.py', gid, '--no-poll', '--min-free-mb', '1'],
                        {'LOOP_LEADER_STUB': STUB})

    def settle(self, gid=None):
        return self.run([self.ctx['tree'] + '/bin/loop_dispatch.py', '--settle'] + ([gid] if gid else []))

    def current(self):
        d = self.lh + '/current'
        return sorted(os.listdir(d)) if os.path.isdir(d) else None

    def report(self, gid, text):
        write_text(self.lh + '/goals/%s/report.md' % gid, text)

    def stop(self, gid):
        write_text(self.lh + '/stub/%s.stop' % gid, 'stop\n')

    def read(self, rel):
        b = read_bytes(self.lh + '/' + rel)
        return None if b is None else b.decode('utf-8', 'replace')


def counted(ctx):
    """The kit's own count: list of (pid, goal), or None for UNKNOWN."""
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_procs.py'], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                        env=make_env(ctx['work'] + '/none', None, DROP))
    if cp.returncode != 0:
        return None
    return [tuple(ln.split()) for ln in cp.stderr.replace('\r', '').splitlines() if len(ln.split()) == 2]


def goal_count(ctx, gid):
    rows = counted(ctx)
    return None if rows is None else sum(1 for _, g in rows if g == gid)


def wait_for(fn, secs=40):
    t0 = time.time()
    while time.time() - t0 < secs:
        v = fn()
        if v:
            return v
        time.sleep(0.5)
    return fn()


def wait_counted(ctx, gid, want, secs=40):
    return wait_for(lambda: (goal_count(ctx, gid) or 0) >= 1 if want else goal_count(ctx, gid) == 0, secs)


def world(ctx):
    if 'w' not in ST:
        ST['w'] = World(ctx, 'two')
    return ST['w']


def teardown(ctx):
    w = ST.get('w')
    if not w:
        return
    for g in (A, B):
        w.stop(g)
    wait_counted(ctx, A, False, 30)
    wait_counted(ctx, B, False, 30)


# ---------------------------------------------------------------- rows
def inherit_control(ctx):
    w = World(ctx, 'ctl-env')
    code = "import os;print(os.environ.get('LOOP_GOAL','unset'))"
    rc, out = w.run(['-I', '-c', code])
    rc2, out2 = w.run(['-I', '-c', code], {'LOOP_GOAL': A})
    return rc == 0 and out.strip() == 'unset' and rc2 == 0 and out2.strip() == A, \
        'child with LOOP_GOAL removed read [%s]; same child with LOOP_GOAL=%s read [%s]' % (out.strip(), A, out2.strip())


def dispatch_two(ctx):
    w = world(ctx)
    before = w.current()
    rc1, o1 = w.dispatch(A)
    up1 = wait_counted(ctx, A, True)
    rc2, o2 = w.dispatch(B)
    up2 = wait_counted(ctx, B, True)
    cur = w.current()
    c1, c2 = w.read('current/' + A), w.read('current/' + B)
    cg = w.read('current_goal')
    ok = (before is None and rc1 == 0 and rc2 == 0 and up1 and up2 and cur == [A, B]
          and (c1 or '').strip() == A and (c2 or '').strip() == B and (cg or '').strip() == B)
    return ok, 'before the first dispatch the current folder was %s; exits %d,%d; stub leaders counted %s,%s; files now %s; contents %s,%s; current_goal reads %s%s' % (
        'absent' if before is None else before, rc1, rc2, up1, up2, cur, (c1 or '').strip(), (c2 or '').strip(), (cg or '').strip(),
        '' if rc1 == 0 and rc2 == 0 else '; refusal text: ' + (o1 + o2).strip().splitlines()[-1][:110])


def inherit_stub(ctx):
    w = world(ctx)
    got = {}
    for g in (A, B):
        got[g] = (w.read('stub/%s.child' % g), w.read('stub/%s.self' % g))
    ok = all(v == (g, g) for g, v in got.items())
    return ok, 'child of stub FIX-01 read %s, stub FIX-01 itself read %s; child of stub FIX-02 read %s, stub FIX-02 itself read %s' % (
        got[A][0], got[A][1], got[B][0], got[B][1])


def preflight_lists(ctx):
    w = world(ctx)
    rc, out = w.run([ctx['tree'] + '/bin/loop_preflight.py'])
    lines = out.split('\n')
    cur = [ln.rstrip() for ln in lines if ln.startswith('current  ')]
    m = re.search(r'^leaders  running=(\d+) max=9 ', out, re.M)
    want = ['current  %s verdict=none leaders=1' % g for g in (A, B)]
    ok = rc == 0 and cur == want and m is not None and int(m.group(1)) >= 2
    return ok, 'exit %d; current lines %s; leaders line running=%s max=9 (machine-wide count, at least the two stub leaders)' % (
        rc, cur, m.group(1) if m else 'absent')


def preflight_none(ctx):
    w = World(ctx, 'pf-none', goals=())
    rc, out = w.run([ctx['tree'] + '/bin/loop_preflight.py'])
    cur = [ln for ln in out.split('\n') if ln.startswith('current  ')]
    m = re.search(r'^leaders  running=(\S+) max=9 ', out, re.M)
    return rc == 0 and not cur and m is not None, 'exit %d; current lines %d; leaders line present %s' % (rc, len(cur), m is not None)


def settle_no_report(ctx):
    w = world(ctx)
    rc, out = w.settle(B)
    return rc == 3 and w.current() == [A, B], 'exit %d; files %s; text: %s' % (rc, w.current(), out.strip()[-90:])


def settle_b_counted(ctx):
    w = world(ctx)
    w.report(B, '# fixture report\nVERDICT: DONE\n')
    n = goal_count(ctx, B)
    rc, out = w.settle(B)
    return n == 1 and rc == 3 and w.current() == [A, B] and 'leader(s) counted for this goal' in out, \
        'FIX-02 leaders counted %s (the positive control for the instrument); report reads DONE; exit %d; files %s; text: %s' % (
            n, rc, w.current(), out.strip()[-90:])


def settle_legacy_kept(ctx):
    w = world(ctx)
    rc, out = w.settle()
    return rc == 3 and (w.read('current_goal') or '').strip() == B and w.current() == [A, B], \
        'no-id settle with current_goal=FIX-02, report DONE, FIX-02 leader counted: exit %d; current_goal reads %s; files %s; text: %s' % (
            rc, (w.read('current_goal') or '').strip(), w.current(), out.strip()[-80:])


def settle_a_done(ctx):
    w = world(ctx)
    w.stop(A)
    gone = wait_counted(ctx, A, False)
    w.report(A, '# fixture report\nVERDICT: DONE\n')
    rows = counted(ctx) or []
    total, b_alive = len(rows), sum(1 for _, g in rows if g == B)
    rc, out = w.settle(A)
    return gone and b_alive == 1 and rc == 0 and w.current() == [B], \
        'FIX-01 leader gone %s; leaders counted at the call: %d in total, %d for FIX-02; exit %d; files now %s; text: %s' % (
            gone, total, b_alive, rc, w.current(), out.strip()[-90:])


def settle_b_after(ctx):
    w = world(ctx)
    w.stop(B)
    gone = wait_counted(ctx, B, False)
    rc, out = w.settle(B)
    return gone and rc == 0 and w.current() == [], 'FIX-02 leader gone %s; exit %d; files now %s; text: %s' % (
        gone, rc, w.current(), out.strip()[-90:])


def settle_legacy_clear(ctx):
    w = world(ctx)
    rows = counted(ctx)
    others = sorted(set(g for _, g in (rows or []) if g not in (A, B)))
    rc, out = w.settle()
    cg = w.read('current_goal')
    if rows is None:
        return False, 'leader count UNKNOWN'
    if others:
        ok = rc == 3 and (cg or '').strip() == B
        return ok, 'branch KEPT: a leader of another goal (%s) is counted machine-wide, so the no-id rule keeps current_goal (today total count); exit %d; current_goal reads %s' % (
            ','.join(others), rc, (cg or '').strip())
    ok = rc == 0 and cg is None
    return ok, 'branch CLEARED: no other leader counted; exit %d; current_goal %s' % (rc, 'absent' if cg is None else 'present')


GUARD_CMD = 'touch %s/goals/%s/evidence/T01/writer/x.txt'


def guard_world(ctx, tag, files, current_goal=A):
    w = World(ctx, tag, goals=(A, B))
    os.makedirs(w.lh + '/goals/%s/evidence/T01/writer' % A)
    write_text(w.lh + '/goals/%s/writable.txt' % A, '# fixture\n')
    if files:
        os.makedirs(w.lh + '/current')
        for g in files:
            write_text(w.lh + '/current/' + g, g + '\n')
    if current_goal:
        write_text(w.lh + '/current_goal', current_goal + '\n')
    return w


def guard_call(ctx, w, goal=None):
    d = {'tool_name': 'Bash', 'tool_input': {'command': GUARD_CMD % (w.lh, A)}, 'cwd': w.base}
    rc, out = w.run(['-I', ctx['tree'] + '/hooks/writer-git-guard.py'], {'LOOP_GOAL': goal} if goal else {},
                    stdin=json.dumps(d).encode('utf-8'))
    if rc == 0 and out.strip() == '':
        return 'allow', ''
    try:
        h = json.loads(out)['hookSpecificOutput']
        if h.get('permissionDecision') == 'deny':
            return 'deny', str(h.get('permissionDecisionReason', ''))
    except Exception:
        pass
    return 'other', 'rc=%d out_sha=%s' % (rc, sha(out))


def guard_two_unset(ctx):
    w = guard_world(ctx, 'g-two', (A, B))
    kind, why = guard_call(ctx, w)
    return kind == 'deny', 'two current files, LOOP_GOAL unset, current_goal file reads %s: %s; reason: "%s"' % (A, kind.upper(), why)


def guard_set_and_single(ctx):
    w = guard_world(ctx, 'g-two-set', (A, B))
    k1, _ = guard_call(ctx, w, A)
    w2 = guard_world(ctx, 'g-one', (A,))
    k2, _ = guard_call(ctx, w2)
    return k1 == 'allow' and k2 == 'allow', 'two files with LOOP_GOAL=%s: %s; one file, LOOP_GOAL unset, current_goal=%s: %s' % (A, k1, A, k2)


LIB_CODE = ("import importlib.util,os,sys\n"
            "s=importlib.util.spec_from_file_location('gl',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
            "print(repr(m.current_goal(sys.argv[2],strict=False))+' '+repr(m.current_goal(sys.argv[2],strict=True)))\n")


def lib_goal(ctx):
    two = guard_world(ctx, 'l-two', (A, B))
    one = guard_world(ctx, 'l-one', (A,))
    lib = ctx['tree'] + '/hooks/_guardlib.py'
    res = {}
    for tag, w, goal in (('two+set', two, B), ('two+unset', two, None), ('two+badpattern', two, 'not a goal'),
                         ('one+unset', one, None)):
        rc, out = w.run(['-I', '-c', LIB_CODE, lib, w.lh], {'LOOP_GOAL': goal} if goal else {})
        res[tag] = out.strip() if rc == 0 else 'rc=%d' % rc
    want = {'two+set': "'%s' '%s'" % (B, B), 'two+unset': "'' ''", 'two+badpattern': "'not a goal' ''",
            'one+unset': "'%s' '%s'" % (A, A)}
    return res == want, '(non-strict strict) ' + '; '.join('%s -> %s' % (k, v) for k, v in res.items())


def dry_run_equal(ctx):
    w = World(ctx, 'dry', goals=(A,))
    shutil.copytree(ctx['tree'] + '/bin', w.lh + '/bin')
    shim = ctx['tree'] + '/shims/loop_dispatch_profile_shim.py'
    args = [A, '--dry-run', '--min-free-mb', '1']
    pin = {'LOOP_CLAUDE_BIN': ctx['py']}
    rc1, o1 = w.run([shim] + args, pin)
    rc2, o2 = w.run([w.lh + '/bin/loop_dispatch.py'] + args, pin)
    b1, b2 = o1.encode('utf-8'), o2.encode('utf-8')
    ctrl = b1 == (b2[:-1] + bytes([b2[-1] ^ 1]))
    ok = rc1 == 0 and rc2 == 0 and b1 == b2 and len(b1) > 0 and not ctrl
    shim_sha = shafull(read_bytes(shim) or b'')
    return ok, 'exits %d,%d; output bytes %d,%d equal %s; control (one byte changed) equal %s; shim sha256 %s; output sha %s' % (
        rc1, rc2, len(b1), len(b2), b1 == b2, ctrl, shim_sha, sha(b1))


CHECKS = {k: v for k, v in globals().items() if callable(v) and k in (
    'inherit_control', 'dispatch_two', 'inherit_stub', 'preflight_lists', 'preflight_none', 'settle_no_report',
    'settle_b_counted', 'settle_legacy_kept', 'settle_a_done', 'settle_b_after', 'settle_legacy_clear', 'guard_two_unset',
    'guard_set_and_single', 'lib_goal', 'dry_run_equal')}


def row_check(ctx, rid, expect, arg):
    ok, detail = CHECKS[arg](ctx)
    # a refusal or tool text can carry a path; the user folder is a real name, so every path is cut to ~ or <work> before print
    for p, repl in ((ctx['work'], '<work>'), (fwd(os.path.expanduser('~')), '~'), (os.path.expanduser('~'), '~')):
        detail = detail.replace(p, repl).replace(p.replace('/', '\\'), repl)
    return ok, 'expected [%s] measured: %s' % (expect, detail)


def main():
    tree, home, work = env_dirs(USAGE)
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K10-C2/run.py', HERE + '/run.py'), ('tests/rows/K10-C2/rows.txt', HERE + '/rows.txt'),
              ('tests/rows/K10-C2/stub_leader.py', HERE + '/stub_leader.py'),
              ('bin/loop_dispatch.py', tree + '/bin/loop_dispatch.py'), ('bin/loop_preflight.py', tree + '/bin/loop_preflight.py'),
              ('hooks/_guardlib.py', tree + '/hooks/_guardlib.py'), ('hooks/writer-git-guard.py', tree + '/hooks/writer-git-guard.py')))
    print('info C2 (e) CARRIED from the T01 scout, not measured here: a role launched by the leader read LOOP_GOAL=KIT-10 in its own '
          'environment (echo ${LOOP_GOAL-unset}, 2026-11-07). Rows C2e-1 and C2e-2 below are this runner\'s own measure.')
    print('info counting is machine-wide (loop_procs), not scoped to the throwaway home; per-goal counts use goal ids FIX-01 and FIX-02; '
          'throwaway config.env MAX_LEADERS=9')
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable), 'tmo': find_timeout()}
    print('info GNU timeout for the leader launch: %s' % ('found and proved by --version' if ctx['tmo'] else 'NOT FOUND, dispatch rows will refuse'))
    try:
        return tally(load_rows(HERE + '/rows.txt'), {'check': row_check}, (ctx,), True)
    finally:
        teardown(ctx)


if __name__ == '__main__':
    sys.exit(main())
