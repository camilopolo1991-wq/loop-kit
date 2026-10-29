#!/usr/bin/env python3
"""loop_dispatch.py: the only sanctioned way to start a loop leader.

Every check below is a defect that happened at least once and has a fixed shape, so it gets
a check that exits non-zero rather than a reminder:

  * goal dir and GOAL.md exist; no bare GOAL twin; file is not a stub          (exit 2)
  * goal lint passes when one is installed under LOOP_HOME/scripts              (exit 2)
  * recall receipt matches this GOAL.md revision, when a receipts file exists   (exit 2)
    (an absent lint tool or receipts file does not refuse: the dispatcher prints a
    "gate OFF" note naming the gate and proceeds, and prints no ok line for it)
  * no leader already running for this goal; leader count under MAX_LEADERS     (exit 3)
  * free disk above --min-free-mb                                               (exit 3)
  * the claude binary resolves and is not run as root with a bypass flag        (exit 4)
  * one dispatch at a time: lock on LOOP_HOME/dispatch/.lock                    (exit 6)
  * after launch, a 60 s liveness poll: a leader that dies before plan.md is    (exit 5)
    reported, never assumed running (the "NEVER RUN all night" class)

Every path comes from LOOP_HOME (the environment, else a .loop folder in the user's home).
The claude binary comes from LOOP_CLAUDE_BIN, else CLAUDE_BIN in config.env, else PATH.

Wall time. When --timeout is absent it is the GOAL's own "wall time <n> min" budget
in seconds plus 600 (n*60+600). A GOAL with no such line gets 7200, whatever
LEADER_TIMEOUT holds.

Exit code. The leader runs under a small supervisor (this file, --supervise). When the
child ends the supervisor writes its exit code to a file named like the run log with the
suffix .rc, beside it (<GOAL>.<ts>.log.rc). With --no-poll the dispatcher returns at once and the
supervisor still writes that file. The code is the timeout wrapper's: the leader's own, or 124 when the
wall time ran out.

Prompt is written to a FILE for the record and passed as one argv element, never through a shell string. LOOP_GOAL is exported to the leader
so every subagent guard knows its goal. The leader's stdout goes to
LOOP_HOME/dispatch/<GOAL>.<ts>.log. Resume: when <goal>/RULING.md exists and report.md says
HELD, the prompt is "Resume goal <ID>" and the ruling path is named.

Usage:
  loop_dispatch.py <GOAL-ID> [--timeout SEC] [--min-free-mb MB] [--dry-run] [--no-poll]
  loop_dispatch.py --selftest     (proves the gates can FAIL inside a temp root)
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

try:                                  # POSIX
    import fcntl
    msvcrt = None
except ModuleNotFoundError:           # Windows: fcntl does not exist at all
    fcntl = None
    import msvcrt


def lock_exclusive(fh):
    """Non-blocking exclusive lock on fh. Raises OSError when another process holds it.

    fcntl is POSIX-only, so on Windows importing it aborts the whole script before any
    gate runs. msvcrt.locking is the genuine equivalent and is in fact stronger: the
    lock is mandatory (kernel-enforced) rather than advisory, it is non-blocking with
    LK_NBLCK, and it raises OSError on contention -- the same shape the caller handles.
    """
    if fcntl is not None:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)


def unlock(fh):
    if fcntl is not None:
        fcntl.flock(fh, fcntl.LOCK_UN)
    else:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)


def is_root():
    """True only where the concept exists. os.geteuid is absent on Windows, so the bare
    call raises AttributeError and kills the dispatch before any gate is evaluated."""
    return hasattr(os, 'geteuid') and os.geteuid() == 0


HERE = os.path.dirname(os.path.abspath(__file__))
LOOP_HOME = os.environ.get('LOOP_HOME') or os.path.join(os.path.expanduser('~'), '.loop')
GOALS = os.path.join(LOOP_HOME, 'goals')
DISPATCH = os.path.join(LOOP_HOME, 'dispatch')
RECEIPTS = os.path.join(LOOP_HOME, 'cache', 'recall-receipts.json')
LINTS = [os.path.join(LOOP_HOME, 'scripts', 'loop_goal_lint.py'),
         os.path.join(LOOP_HOME, 'scripts', 'goal_file_lint.py')]
ID_RE = re.compile(r'^[A-Za-z][A-Za-z0-9]{1,11}-\d{2,3}$')
WALL_RE = re.compile(r'wall\s+time\s*[:=]?\s*(\d+)\s*min', re.IGNORECASE)
WALL_PAD_S = 600
DEFAULT_TIMEOUT_S = 7200

# The leader runs headless with stdin closed, so anything that would prompt
# must be REFUSED, never waited on. dontAsk plus --permission-prompts none means
# a tool outside the list is denied immediately instead of hanging on a prompt
# nobody can answer. The allow rule is written in the documented prefix form,
# with a space, the way `claude --help` spells its own example Bash(git *).
# This list is not the security boundary: the PreToolUse hooks are, and
# settings.json permissions.deny still outranks everything here.
ALLOWED_TOOLS = 'Bash(loop-guard-run *) Read Glob Grep Write Edit Agent Skill'


def resolve_timeout_bin():
    """Absolute path to a VERIFIED GNU timeout, or None.

    A bare 'timeout' in argv resolves through CreateProcess on Windows, which searches
    the system directory first, so it finds TIMEOUT.EXE: a pause command that never
    runs the rest of the argv. shutil.which disagrees with CreateProcess here, so
    neither is trusted on its own. Every candidate must PROVE it is GNU by answering
    --version with the coreutils banner. Nothing is assumed from a filename, and there
    are no guessed install locations.

    An EXPLICIT TIMEOUT_BIN that fails verification is fatal and never falls back
    to PATH. Silently running a different binary than the one configured is the
    same defect class as a false zero.
    """
    explicit = conf('TIMEOUT_BIN')
    if explicit:
        return explicit if _is_gnu_timeout(explicit) else None
    w = shutil.which('timeout')
    if w and _is_gnu_timeout(w):
        return w
    return None


def _is_gnu_timeout(path):
    if not path or not os.path.isfile(path):
        return False
    try:
        r = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=15)
    except Exception:
        return False
    return r.returncode == 0 and 'coreutils' in (r.stdout + r.stderr).lower()


def conf(key, default=''):
    """A key's value: the environment first (as loop_conf and the stubs do), then config.env
    under LOOP_HOME, then the default."""
    if os.environ.get(key):
        return os.environ[key]
    path = os.path.join(LOOP_HOME, 'config.env')
    try:
        for line in open(path, encoding='utf-8'):
            line = line.split('#', 1)[0].strip()
            if line.startswith(key + '='):
                return line.split('=', 1)[1].strip().strip('"\'')
    except OSError:
        pass
    return os.environ.get(key, default)


def say(tag, msg):
    print('%-5s %s' % (tag, msg))


def wall_seconds(goal_md_path):
    """The default timeout in seconds from the GOAL's 'wall time <n> min' line, or None.

    n*60 plus WALL_PAD_S. None means the GOAL has no such line (or cannot be read), and
    the caller uses DEFAULT_TIMEOUT_S. The first match wins."""
    try:
        text = open(goal_md_path, encoding='utf-8', errors='replace').read()
    except OSError:
        return None
    m = WALL_RE.search(text)
    if not m:
        return None
    return int(m.group(1)) * 60 + WALL_PAD_S


def leaders_running():
    """Rows of (pid, goal), or None for UNKNOWN. Never a false zero.

    loop_procs.count() is the single instrument both this dispatcher and loop-preflight
    call, and it returns None when it could not measure. None is not zero."""
    for d in (HERE, os.path.join(LOOP_HOME, 'bin')):
        if d not in sys.path:
            sys.path.insert(0, d)
    try:
        import loop_procs
    except Exception as exc:
        say('FAIL', 'cannot load the leader-count instrument (%s). Refusing: an '
                    'unmeasurable MAX_LEADERS is not a pass.' % type(exc).__name__)
        return None
    return loop_procs.count()


def free_mb():
    """Free DISK, in MB, on the drive that holds LOOP_HOME. None means unmeasured, and
    the caller refuses on it rather than reading it as plenty."""
    try:
        return shutil.disk_usage(LOOP_HOME).free // (1024 * 1024)
    except OSError:
        return None


GATE_LINES = []   # (tag, message) per optional gate, refilled by each goal_checks call


def goal_checks(goal_id):
    problems = []
    del GATE_LINES[:]
    d = os.path.join(GOALS, goal_id)
    gm = os.path.join(d, 'GOAL.md')
    if not os.path.isdir(d):
        return gm, ['goal dir does not exist: ' + d]
    if os.path.exists(os.path.join(d, 'GOAL')):
        problems.append('a bare GOAL file exists; the leader reads GOAL.md. Keep exactly one.')
    if not os.path.isfile(gm):
        problems.append('GOAL.md missing in ' + d)
        return gm, problems
    data = open(gm, 'rb').read()
    if len(data.strip()) < 200:
        problems.append('GOAL.md is a stub (%d bytes)' % len(data))
    lint_ran = False
    for lint in LINTS:
        if os.path.exists(lint):
            lint_ran = True
            r = subprocess.run([sys.executable, '-I', lint, gm], capture_output=True, text=True)
            if r.returncode != 0:
                problems.append('goal lint exit %d: %s' % (r.returncode, (r.stdout + r.stderr).strip()[-300:]))
            else:
                GATE_LINES.append(('ok', 'goal lint passed'))
            break
    if not lint_ran:
        GATE_LINES.append(('note', 'goal lint gate OFF: no lint tool is installed under LOOP_HOME/scripts, so no lint ran; proceeding'))
    if not os.path.exists(RECEIPTS):
        GATE_LINES.append(('note', 'recall receipt gate OFF: no receipts file under LOOP_HOME/cache, so no receipt was checked; proceeding'))
    else:
        sha = hashlib.sha256(data).hexdigest()
        try:
            rec = json.load(open(RECEIPTS)).get(goal_id)
        except Exception:
            rec = None
        if not rec:
            problems.append('no recall receipt for %s in %s; record one, or remove the receipts file to switch this gate off' % (goal_id, RECEIPTS))
        elif rec.get('sha256') != sha:
            problems.append('recall receipt is for another revision of GOAL.md; record it again')
        elif rec.get('rc') != 0:
            problems.append('recall receipt rc=%s' % rec.get('rc'))
        else:
            GATE_LINES.append(('ok', 'recall receipt matches this GOAL.md'))
    return gm, problems


def held(goal_id):
    rep = os.path.join(GOALS, goal_id, 'report.md')
    try:
        head = open(rep, encoding='utf-8', errors='replace').read(4000)
    except OSError:
        return False
    return bool(re.search(r'VERDICT:\s*HELD', head))


def resolve_claude():
    """The one binary this dispatcher may launch. Returns (path, source) or (None, why).

    Order: LOOP_CLAUDE_BIN from the environment, then CLAUDE_BIN from config.env, then
    PATH only when neither is set. A pin is never second-guessed: a pin that is not an
    existing file is a refusal, never a fall back to PATH. A harness probe that meant to
    launch a stand-in once launched the real binary as a leader on a fixture goal, and
    the dispatcher was the only line left to stop it.
    """
    for key, val in (('LOOP_CLAUDE_BIN', os.environ.get('LOOP_CLAUDE_BIN', '')), ('CLAUDE_BIN', conf('CLAUDE_BIN', ''))):
        val = (val or '').strip()
        if val:
            if not os.path.isfile(val):
                return None, '%s pins the claude binary to %s, which is not an existing file. Refused, no PATH fallback.' % (key, val)
            return os.path.abspath(val), key
    found = shutil.which('claude')
    if not found:
        return None, 'claude binary not found: set LOOP_CLAUDE_BIN, or CLAUDE_BIN in config.env, or put claude on PATH'
    return found, 'PATH'


def build(goal_id, timeout_s, dry=False):
    claude, src = resolve_claude()
    if not claude:
        return None, src
    resume = held(goal_id) and os.path.exists(os.path.join(GOALS, goal_id, 'RULING.md'))
    prompt = ('Resume goal %s. Read %s/RULING.md first; it answers the gate you held on.' % (goal_id, os.path.join(GOALS, goal_id))
              if resume else 'Run goal %s' % goal_id)
    # The prompt is composed in memory. Only a real dispatch writes it to disk,
    # where it stays as the record of what the leader was told. A dry run writes
    # neither it nor the lock file.
    full = prompt + '\n'
    peers = [g for _, g in (leaders_running() or []) if g != goal_id]
    if peers:
        full += ('Peers: leaders are running on %s. Expect their writes under their own goal dirs; '
                 'attribute any tripwire difference there to them before calling it an incident.\n' % ', '.join(peers))
    if not dry:
        os.makedirs(DISPATCH, mode=0o700, exist_ok=True)
        with open(os.path.join(DISPATCH, '%s.prompt' % goal_id), 'w', encoding='utf-8') as fh:
            fh.write(full)
    # argv list, no shell: the prompt text is one argument, so no quoting can break it.
    tmo = resolve_timeout_bin()
    if not tmo:
        return None, ('no verified GNU timeout found. A bare "timeout" on Windows resolves to '
                      'TIMEOUT.EXE, which never runs the command, so the wall-time ceiling '
                      'cannot be enforced. Set TIMEOUT_BIN in config.env to a coreutils timeout. '
                      'Refusing rather than dispatching an unbounded leader.')
    cmd = [tmo, str(timeout_s), claude,
           '--permission-mode', 'dontAsk',
           '--permission-prompts', 'none',
           '--allowedTools', ALLOWED_TOOLS,
           '--agent', 'loop-leader', '-p', full]
    return cmd, prompt


def supervise(logp, cmd):
    """Run cmd with its output appended to logp, wait for it, and write its exit code to
    logp + '.rc' (a temporary name, then renamed, so a reader never sees half a number).
    A command that cannot start is recorded as 127. Returns the code."""
    try:
        with open(logp, 'ab') as lf:
            rc = subprocess.call(cmd, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=os.environ)
    except OSError as exc:
        with open(logp, 'ab') as lf:
            lf.write(('supervisor: cannot start the child (%s)\n' % type(exc).__name__).encode('utf-8'))
        rc = 127
    tmp = logp + '.rc.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write('%d\n' % rc)
    os.replace(tmp, logp + '.rc')
    return rc


def selftest():
    tmp = tempfile.mkdtemp(prefix='loop-dispatch-selftest-')
    global GOALS, RECEIPTS
    GOALS, RECEIPTS = os.path.join(tmp, 'goals'), os.path.join(tmp, 'receipts.json')
    os.makedirs(os.path.join(GOALS, 'ST-01'))
    json.dump({}, open(RECEIPTS, 'w'))
    results = []
    _, p = goal_checks('ST-01'); results.append(('missing GOAL.md refused', any('missing' in x for x in p)))
    open(os.path.join(GOALS, 'ST-01', 'GOAL.md'), 'w').write('# stub\n')
    _, p = goal_checks('ST-01'); results.append(('stub refused', any('stub' in x for x in p)))
    open(os.path.join(GOALS, 'ST-01', 'GOAL.md'), 'w').write('# ST-01: x\n' + 'Acceptance criteria:\n1. a\n' * 20)
    open(os.path.join(GOALS, 'ST-01', 'GOAL'), 'w').write('x')
    _, p = goal_checks('ST-01'); results.append(('bare GOAL twin refused', any('bare GOAL' in x for x in p)))
    os.remove(os.path.join(GOALS, 'ST-01', 'GOAL'))
    _, p = goal_checks('ST-01'); results.append(('no receipt refused', any('recall receipt' in x for x in p)))
    sha = hashlib.sha256(open(os.path.join(GOALS, 'ST-01', 'GOAL.md'), 'rb').read()).hexdigest()
    json.dump({'ST-01': {'sha256': 'deadbeef', 'rc': 0}}, open(RECEIPTS, 'w'))
    _, p = goal_checks('ST-01'); results.append(('stale receipt refused', any('another revision' in x for x in p)))
    json.dump({'ST-01': {'sha256': sha, 'rc': 0}}, open(RECEIPTS, 'w'))
    _, p = goal_checks('ST-01'); results.append(('clean goal passes', not [x for x in p if 'lint' not in x]))
    os.remove(RECEIPTS)
    _, p = goal_checks('ST-01'); results.append(('no receipts file, gate off', not [x for x in p if 'lint' not in x]))
    results.append(('bad id refused', not ID_RE.match('../x')))
    gm = os.path.join(GOALS, 'ST-01', 'GOAL.md')
    open(gm, 'w').write('Budget: writes 5 | wall time 400 min\n')
    results.append(('wall time 400 min gives 24600', wall_seconds(gm) == 24600))
    open(gm, 'w').write('Budget: writes 5\n')
    results.append(('no wall time line gives None', wall_seconds(gm) is None))
    lp = os.path.join(tmp, 'x.log')
    rc = supervise(lp, [sys.executable, '-I', '-c', 'import sys; sys.exit(7)'])
    results.append(('rc file holds the child code', rc == 7 and open(lp + '.rc').read().strip() == '7'))
    shutil.rmtree(tmp)
    allok = True
    for name, okk in results:
        say('ok' if okk else 'FAIL', name); allok &= okk
    return 0 if allok else 1


def settle_core():
    """Returns (cleared, message). The one rule, shared by --settle and dispatch start."""
    cg = os.path.join(LOOP_HOME, 'current_goal')
    if not os.path.exists(cg):
        return False, 'current_goal absent, nothing to settle'
    try:
        gid = open(cg, encoding='utf-8').read().strip().splitlines()[0].strip()
    except (OSError, IndexError):
        gid = ''
    rep = os.path.join(GOALS, gid, 'report.md') if gid else ''
    try:
        head = open(rep, encoding='utf-8', errors='replace').read(4000) if rep else ''
    except OSError:
        head = ''
    m = re.search(r'VERDICT:\s*(DONE|HELD)\b', head)
    if not m:
        return False, 'kept current_goal=%s: its report.md does not read VERDICT DONE or HELD' % (gid or '?')
    running = leaders_running()
    if running is None:
        return False, 'kept current_goal=%s: leader count UNKNOWN, never read as zero' % gid
    if running:
        return False, 'kept current_goal=%s: %d leader(s) counted (%s)' % (gid, len(running), ', '.join(g for _, g in running))
    os.remove(cg)
    return True, 'cleared current_goal=%s: report.md VERDICT %s, 0 leaders counted' % (gid, m.group(1))


def settle():
    """Clear current_goal once its goal is no longer live. Rule in settle_core().
    Exit 0 cleared or nothing to clear, 3 kept. The dispatcher also runs the same
    rule at dispatch start, so a stale previous goal clears on its own."""
    cleared, msg = settle_core()
    if cleared or msg.startswith('current_goal absent'):
        say('ok', msg); return 0
    say('FAIL', msg); return 3


def main():
    if len(sys.argv) > 3 and sys.argv[1] == '--supervise' and sys.argv[3] == '--':
        return supervise(sys.argv[2], sys.argv[4:])
    ap = argparse.ArgumentParser()
    ap.add_argument('goal', nargs='?')
    ap.add_argument('--timeout', type=int, default=None,
                    help='seconds; default is the GOAL wall time in minutes times 60 plus 600, '
                         'else 7200')
    ap.add_argument('--min-free-mb', type=int, default=int(conf('MIN_FREE_MB', '1024')))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-poll', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--settle', action='store_true',
                    help='clear a stale current_goal: only when its report.md reads DONE or HELD '
                         'and no leader is counted')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.settle:
        return settle()
    if not a.goal or not ID_RE.match(a.goal):
        say('FAIL', 'goal id must match %s' % ID_RE.pattern); return 2
    goal_id = a.goal.upper()
    if is_root():
        say('FAIL', 'do not dispatch as root: claude refuses permission bypass under root and the guards assume a user home'); return 4
    gm, problems = goal_checks(goal_id)
    for p in problems:
        say('FAIL', p)
    if problems:
        return 2
    say('ok', 'goal file present and not a stub')
    for tag, msg in GATE_LINES:
        say(tag, msg)
    if a.timeout is not None:
        timeout_s, why = a.timeout, '--timeout'
    else:
        derived = wall_seconds(gm)
        if derived is not None:
            timeout_s, why = derived, 'GOAL wall time line plus %d s' % WALL_PAD_S
        else:
            timeout_s, why = DEFAULT_TIMEOUT_S, 'no wall time line in the GOAL'
    say('ok', 'timeout %d s (%s)' % (timeout_s, why))
    claude_bin, claude_src = resolve_claude()
    if not claude_bin:
        say('FAIL', claude_src); return 2
    say('ok', 'claude binary %s (from %s)' % (claude_bin, claude_src))
    lock = None
    if not a.dry_run:  # a dry run creates no directory and no lock file
        os.makedirs(DISPATCH, mode=0o700, exist_ok=True)
        lock = open(os.path.join(DISPATCH, '.lock'), 'w')
        try:
            lock_exclusive(lock)
        except OSError:
            say('FAIL', 'another dispatch is in progress (lock held)'); return 6
        # Settle BEFORE the new goal id is written. A stale previous goal clears
        # on its own. A file with a counted leader is kept, and the MAX_LEADERS check
        # below then stops this dispatch. A dry run writes nothing, so it never settles.
        cleared, msg = settle_core()
        say('ok' if cleared or msg.startswith('current_goal absent') else 'note', 'settle: ' + msg)
    running = leaders_running()
    if running is None:
        say('FAIL', 'leader count UNKNOWN (no working process instrument). '
                    'MAX_LEADERS cannot be enforced, so this dispatch is refused.')
        return 3
    if any(g == goal_id for _, g in running):
        say('FAIL', 'a leader is already running for %s' % goal_id); return 3
    maxl = int(conf('MAX_LEADERS', '1'))
    if len(running) >= maxl:
        say('FAIL', '%d leader(s) running, MAX_LEADERS=%d' % (len(running), maxl)); return 3
    fm = free_mb()
    if fm is None:
        say('FAIL', 'free disk on the LOOP_HOME drive is UNKNOWN, so MIN_FREE_MB cannot be enforced. Refused.'); return 3
    if fm < a.min_free_mb:
        say('FAIL', 'free disk %d MB on the LOOP_HOME drive is under the floor MIN_FREE_MB=%d' % (fm, a.min_free_mb)); return 3
    say('ok', 'leaders %d/%d, free disk %d MB on the LOOP_HOME drive, floor %d MB' % (len(running), maxl, fm, a.min_free_mb))
    cmd, prompt = build(goal_id, timeout_s, dry=a.dry_run)
    if cmd is None:
        say('FAIL', prompt); return 4
    say('ok', 'prompt: ' + prompt.splitlines()[0])
    if a.dry_run:
        say('ok', 'dry run: ' + ' '.join(cmd)); return 0
    ts = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    logp = os.path.join(DISPATCH, '%s.%s.log' % (goal_id, ts))
    env = dict(os.environ, LOOP_GOAL=goal_id, LOOP_HOME=LOOP_HOME)
    with open(os.path.join(LOOP_HOME, 'current_goal'), 'w') as fh:
        fh.write(goal_id + '\n')
    sup = [sys.executable, os.path.abspath(__file__), '--supervise', logp, '--'] + cmd
    proc = subprocess.Popen(sup, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                            env=env, cwd=os.path.expanduser('~'), start_new_session=True)
    say('ok', 'launched pid %d, log %s, exit code file %s' % (proc.pid, logp, logp + '.rc'))
    unlock(lock)
    if a.no_poll:
        return 0
    plan = os.path.join(GOALS, goal_id, 'plan.md')
    for _ in range(12):
        time.sleep(5)
        rc = proc.poll()
        if rc is not None:
            say('FAIL', 'leader exited rc=%s within 60 s; read %s. A goal with no plan.md was NEVER RUN.' % (rc, logp)); return 5
    say('ok', 'alive after 60 s; plan.md %s' % ('present' if os.path.exists(plan) else 'not yet written'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
