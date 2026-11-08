#!/usr/bin/env python3
"""K11-C3 rows runner: the dispatcher exports the wait ceiling at 0 into every leader's environment, and its dry run prints it.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test (its bin/loop_dispatch.py is the file run)
  LOOP_ROWS_HOME   unused here (the child gets its own throwaway home under LOOP_WORK); required by the shape of the runners
  LOOP_WORK        the work folder; every fixture is written under it and listed in k11c3-manifest.txt
  LOOP_PY          the interpreter the dispatcher and the stub are run with (defaults to the one running this file)
  TIMEOUT_BIN      optional; a GNU timeout. Without it the runner looks for one on PATH and proves it by --version.

The child gets HOME, USERPROFILE and LOOP_HOME at a throwaway home inside LOOP_WORK (make_env). The live home is never
named. The variable under test is removed from the environment first, so a value read in the stub came from the dispatcher.

The stub launcher is written into the throwaway home by this runner and named by LOOP_LEADER_STUB (the KIT-10 C2 launcher
override), so no real claude is ever launched; LOOP_CLAUDE_BIN is pointed at a file that does not exist. The stub records
two names to a file: LOOP_GOAL (the positive control for the recorder: the dispatcher sets it) and the variable under test.
"""
import os
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, register, sha, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [TIMEOUT_BIN=<gnu timeout>] '
         'python run.py (no positional argument)')
MANIFEST = 'k11c3-manifest.txt'
VAR = 'CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS'
DROP = ('LOOP_GOAL', 'HERMES_HOME', 'CLAUDE_BIN', 'LOOP_CLAUDE_BIN', 'LOOP_LEADER_STUB', 'MAX_LEADERS', 'MIN_FREE_MB',
        'REPORT_SEND_CMD', 'JOURNAL_FILE', 'LOOP_GUARD_MODE', 'LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_PY',
        'ENGINE_RECORD_DIR', VAR)
HERE = os.path.dirname(os.path.abspath(__file__))
GID = 'FIX-31'
GOAL_MD = '# %s: constructed fixture goal\n' + 'Acceptance criteria:\n1. a constructed line that is only here to make the file longer than a stub\n' * 6
# The stub: records LOOP_GOAL and the variable (or the word unset) to <LOOP_HOME>/stub/env.txt, written whole then renamed, and exits.
STUB_CODE = ("import os\n"
             "d = os.path.join(os.environ['LOOP_HOME'], 'stub')\n"
             "t = os.path.join(d, 'env.tmp')\n"
             "open(t, 'w', encoding='utf-8').write('LOOP_GOAL=%s\\n%s=%s\\n' % (os.environ.get('LOOP_GOAL', 'unset'), '" + VAR + "', os.environ.get('" + VAR + "', 'unset')))\n"
             "os.replace(t, os.path.join(d, 'env.txt'))\n")


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
    def __init__(self, ctx, tag):
        self.ctx = ctx
        self.base = '%s/k11c3-fixtures/%s-%d' % (ctx['work'], tag, time.time_ns())
        register(ctx['work'], MANIFEST, self.base)
        self.home = self.base + '/home'
        self.lh = self.home + '/.loop'
        os.makedirs(self.lh + '/stub')
        os.makedirs(self.base + '/tmp')
        write_text(self.lh + '/config.env', 'MAX_LEADERS=9\n')
        os.makedirs(self.lh + '/goals/' + GID)
        write_text(self.lh + '/goals/%s/GOAL.md' % GID, GOAL_MD % GID)
        self.stub = self.lh + '/stub/stub_env.py'
        write_text(self.stub, STUB_CODE)

    def env(self, extra=None):
        e = {'TEMP': self.base + '/tmp', 'TMP': self.base + '/tmp', 'TIMEOUT_BIN': self.ctx['tmo'] or '',
             'LOOP_CLAUDE_BIN': self.lh + '/no-such-claude'}
        e.update(extra or {})
        return make_env(self.home, e, DROP)

    def run(self, argv, extra=None):
        cp = subprocess.run([self.ctx['py']] + argv, capture_output=True, env=self.env(extra), cwd=self.base,
                            stdin=subprocess.DEVNULL)
        return cp.returncode, (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '')


def wait_file(path, secs=40):
    t0 = time.time()
    while time.time() - t0 < secs:
        b = read_bytes(path)
        if b is not None:
            return b.decode('utf-8', 'replace').replace('\r', '')
        time.sleep(0.3)
    return None


# ---------------------------------------------------------------- rows
def stub_env(ctx):
    w = World(ctx, 'stub')
    rc, out = w.run([ctx['tree'] + '/bin/loop_dispatch.py', GID, '--no-poll', '--min-free-mb', '1'], {'LOOP_LEADER_STUB': w.stub})
    got = wait_file(w.lh + '/stub/env.txt')
    if got is None:
        return False, 'dispatch exit %d, the stub recorded nothing in 40 s; last line: %s' % (rc, (out.strip().splitlines() or [''])[-1][:110])
    vals = dict(ln.split('=', 1) for ln in got.split('\n') if '=' in ln)
    ok = rc == 0 and vals.get('LOOP_GOAL') == GID and vals.get(VAR) == '0'
    return ok, 'dispatch exit %d; stub recorded LOOP_GOAL=%s (control: the recorder works) and %s=%s' % (
        rc, vals.get('LOOP_GOAL'), VAR, vals.get(VAR))


def dry_line(ctx):
    w = World(ctx, 'dry')
    rc, out = w.run([ctx['tree'] + '/bin/loop_dispatch.py', GID, '--dry-run', '--min-free-mb', '1'], {'LOOP_CLAUDE_BIN': ctx['py']})
    want = ('ok    leader environment: %s=0' % VAR).encode('utf-8')
    lines = [ln.encode('utf-8') for ln in out.split('\n') if ln.startswith('ok    leader environment:')]
    got = lines[0] if lines else b''
    ctrl = bool(got) and got == (want[:-1] + bytes([want[-1] ^ 1]))
    ok = rc == 0 and len(lines) == 1 and got == want and not ctrl
    return ok, 'dry run exit %d; leader environment lines %d; line bytes %d, equal to expected bytes %s; control (expected with one byte changed) equal %s; line sha %s' % (
        rc, len(lines), len(got), got == want, ctrl, sha(got))


CHECKS = {'stub_env': stub_env, 'dry_line': dry_line}


def row_check(ctx, rid, expect, arg):
    ok, detail = CHECKS[arg](ctx)
    for p, repl in ((ctx['work'], '<work>'), (fwd(os.path.expanduser('~')), '~'), (os.path.expanduser('~'), '~')):
        detail = detail.replace(p, repl).replace(p.replace('/', '\\'), repl)
    return ok, 'expected [%s] measured: %s' % (expect, detail)


def main():
    tree, home, work = env_dirs(USAGE)
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K11-C3/run.py', HERE + '/run.py'), ('tests/rows/K11-C3/rows.txt', HERE + '/rows.txt'),
              ('bin/loop_dispatch.py', tree + '/bin/loop_dispatch.py')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable), 'tmo': find_timeout()}
    print('info GNU timeout for the leader launch: %s' % ('found and proved by --version' if ctx['tmo'] else 'NOT FOUND, the stub row will refuse'))
    return tally(load_rows(HERE + '/rows.txt'), {'check': row_check}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
