#!/usr/bin/env python3
"""K10-C3 rows runner: the step-log lock. Every append of loop-journal (step log) and loop-report (report.log) takes an exclusive
lock on a sibling file named as the log plus .lock, with bounded retries and a named failure on timeout or on a failed redactor.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k10c3-manifest.txt
  LOOP_PY          the interpreter every child is run with (defaults to the one running this file)
  K10C3_RUNS       runs of the locked row (default 3)
  K10C3_CONTROL_RUNS  runs of the control row (default 1)
  K10C3_LINES      lines per appender (default 2000)
  K10C3_FAULT_LINES   lines per appender of the redactor fault row (default 500); the chosen failing call is the middle one

Rows (rows.txt, id :: kind :: expect :: arg):
  locked          two appender processes, K10C3_LINES lines each, in parallel through LOOP_TREE/bin/loop_journal.py (the real tool, its
                  append core called in process) against a fixture log; each run must read the sibling .lock file present, 2 x LINES
                  lines, every line whole, every (appender, number) pair exactly once, every call and every redactor child counted
                  with no failure. Stops at the first failed run.
  control         the same two appenders without the lock: each call is today's append core (open the log for append, loop_redact.py
                  writes the line through the open handle), the lock never taken. Quotes lines and torn counts per run. The row passes
                  when every run could be read; it quotes the torn total, or says it tore none (and the lock is kept).
  fault_redactor  a fixture tree under LOOP_WORK whose loop_redact.py exits non-zero on one chosen call (all else the real redactor):
                  the attempt-1 signature (one line missing, one appender non-zero, lock file present) must show, and the failure must
                  be named on one line: class redactor, the exit code, the log path class.
  fault_lock      the lock is held by this process while two appenders run with a one-second bound: every call fails with exit 5 and
                  the named lock line (class lock), nothing is appended. Together with fault_redactor it tells the two causes apart.
  timeout_journal the lock is held by this process; loop-journal must exit 5 within the bound with one line naming the lock path class
                  and the wait, no stack trace, nothing appended; after the lock is released the same call exits 0 and appends one line.
  timeout_report  the same for loop-report and report.log: one line naming the report log lock, no report.log line written, and the
                  tool's exit code is the one it has with the lock free (2 here: no send command is configured), not 5.
Every appender call and every redactor child (exit code, stderr size, what the tool said) is written by the children to
capture-<A|B>.txt in the run's fixture folder, and the parent keeps a summary of every child and every failure in k10c3-children.txt
under LOOP_WORK. Prints PASS or FAIL per row, then rows=N pass=P fail=F.
"""
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, load_rows, make_env, read_bytes, register, shafull, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [K10C3_RUNS=<n>] [K10C3_CONTROL_RUNS=<n>] '
         '[K10C3_LINES=<n>] [K10C3_FAULT_LINES=<n>] python run.py (no positional argument)')
MANIFEST = 'k10c3-manifest.txt'
CHILDREN = 'k10c3-children.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS', 'REPORT_SEND_CMD', 'REPORT_MAX_LINES', 'LOOP_STEPLOG_LOCK_WAIT_S', 'K10C3_CAPTURE')
G = 'K10-FIX'
PAD = 'x' * 60
WHOLE = re.compile(rb'^- \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ ' + G.encode() + rb' T01 NOTE ([AB]) (\d+) ' + PAD.encode() + rb'$')
CAP = re.compile(r'^([AB]) (\d+) tool_exit=(\S+) redactor_exit=(\S+) redactor_err_bytes=(\d+) said=(.*)$')
FAULT_EXIT = 3


def text_for(tag, i):
    return 'NOTE %s %d %s' % (tag, i, PAD)


# ---- the appenders (child mode: run.py --child <kind> <tree> <log> <tag> <n>; the capture file is named by K10C3_CAPTURE) ----

def child_main(kind, tree, log, tag, n):
    """kind 'tool': call the real tool's append core in process, n times. kind 'bare': today's append core, no lock.
    Every call is written to the capture file: the tool's exit, the redactor child's exit and stderr size, what the tool said."""
    os.environ['JOURNAL_FILE'] = log
    cap = open(os.environ['K10C3_CAPTURE'], 'w', encoding='utf-8', newline='\n', buffering=1)
    bad = 0
    state = {}
    real_run = subprocess.run

    def recording_run(*a, **k):
        """The redactor child's exit code and stderr, kept; its stderr is passed on to the tool's stderr as before."""
        k['stderr'] = subprocess.PIPE
        cp = real_run(*a, **k)
        state['rc'] = cp.returncode
        state['err'] = cp.stderr or b''
        if cp.stderr:
            sys.stderr.write(cp.stderr.decode('utf-8', 'replace'))
        return cp

    def note(i, tool_exit, said):
        cap.write('%s %d tool_exit=%s redactor_exit=%s redactor_err_bytes=%d said=%s\n' % (
            tag, i, tool_exit, state.get('rc', 'none'), len(state.get('err', b'')), ' | '.join(said.strip().split('\n'))[:300]))
    if kind == 'tool':
        sys.path.insert(0, tree + '/bin')
        import loop_journal as lj
        sys.stdout = open(os.devnull, 'w')
        lj.subprocess.run = recording_run
        for i in range(n):
            state.clear()
            sys.stderr = io.StringIO()
            code = 0
            try:
                lj.mode_append([G, 'T01', text_for(tag, i)])
            except SystemExit as e:
                code = 0 if e.code is None else e.code
            except Exception as e:
                code = 'exc:' + e.__class__.__name__
            said = sys.stderr.getvalue()
            sys.stderr = sys.__stderr__
            if code != 0:
                bad += 1
            note(i, code, said)
    else:
        for i in range(n):
            state.clear()
            line = '- %s %s T01 %s' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), G, text_for(tag, i))
            payload = (line + '\n').encode('utf-8')
            out = open(log, 'ab')
            with out:
                cp = subprocess.run([sys.executable, tree + '/bin/loop_redact.py'], input=payload, stdout=out, stderr=subprocess.PIPE)
            state['rc'], state['err'] = cp.returncode, cp.stderr or b''
            if cp.returncode != 0:
                bad += 1
            note(i, cp.returncode, cp.stderr.decode('utf-8', 'replace') if cp.stderr else '')
    cap.close()
    sys.stderr.write('child %s nonzero=%d\n' % (tag, bad))
    sys.exit(1 if bad else 0)


def fail_class(tool_exit, red_exit, said):
    if 'class: redactor' in said:
        return 'redactor'
    if 'lock was not taken' in said:
        return 'lock'
    if tool_exit.startswith('exc:'):
        return 'exception'
    if red_exit not in ('0', 'none'):
        return 'redactor-silent'      # the redactor child failed and the tool said nothing about it
    return 'unnamed'                  # a non-zero exit with no message at all


def read_capture(path):
    """(calls, tool_nonzero, redactor_calls, redactor_nonzero, failures) of one capture file; None when it is missing.
    A failure is (tag, call number, class, tool exit, redactor exit, said)."""
    data = read_bytes(path)
    if data is None:
        return None
    calls = tnz = rcalls = rnz = 0
    fails = []
    for ln in data.decode('utf-8', 'replace').split('\n'):
        m = CAP.match(ln.rstrip('\r'))
        if not m:
            continue
        tag, i, te, re_, eb, said = m.groups()
        calls += 1
        if re_ != 'none':
            rcalls += 1
        bad_t = te != '0'
        bad_r = re_ not in ('0', 'none')
        tnz += bad_t
        rnz += bad_r
        if bad_t or bad_r:
            fails.append((tag, int(i), fail_class(te, re_, said), te, re_, said))
    return calls, tnz, rcalls, rnz, fails


def fdesc(f):
    return '%s#%d class=%s tool_exit=%s redactor_exit=%s' % (f[0], f[1], f[2], f[3], f[4])


def pair(ctx, kind, tree, log, n, extra=None):
    """Two appenders in parallel (two processes, n lines each) against log. Returns (their nonzero-exit counts, per-child capture
    summaries by tag). Each child's stderr is kept in stderr-<tag>.txt beside the log."""
    base = os.path.dirname(log)
    ps = []
    for tag in ('A', 'B'):
        env = make_env(ctx['home'], dict(extra or {}, K10C3_CAPTURE='%s/capture-%s.txt' % (base, tag)), DROP)
        ps.append((tag, subprocess.Popen([ctx['py'], fwd(__file__), '--child', kind, tree, log, tag, str(n)], env=env, cwd=ctx['work'],
                                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)))
    nz = []
    kids = {}
    for tag, p in ps:
        err = p.communicate()[1].decode('utf-8', 'replace').replace('\r', '')
        write_text('%s/stderr-%s.txt' % (base, tag), err)
        m = re.search(r'nonzero=(\d+)', err)
        nz.append(int(m.group(1)) if m else -1)
        kids[tag] = read_capture('%s/capture-%s.txt' % (base, tag))
        if kids[tag] is None or m is None:
            print('info appender %s left no capture or no count; its stderr is in stderr-%s.txt of %s' % (tag, tag, os.path.basename(base)))
    return nz, kids


def keep_children(ctx, label, run, base, nz, kids):
    """Print the per-child counts and every failure (classes and exit codes) and append them to k10c3-children.txt under work."""
    path = ctx['work'] + '/' + CHILDREN
    first = not os.path.isfile(path)
    if first:
        register(ctx['work'], MANIFEST, path)
    all_fails = []
    with open(path, 'a', encoding='utf-8', newline='\n') as fh:
        for tag in ('A', 'B'):
            k = kids.get(tag)
            if k is None:
                s = 'child %s: no capture' % tag
            else:
                calls, tnz, rcalls, rnz, fails = k
                s = 'child %s: calls=%d tool_nonzero=%d redactor_children=%d redactor_nonzero=%d' % (tag, calls, tnz, rcalls, rnz)
                all_fails += fails
            line = '%s run %d (%s) %s' % (label, run, os.path.basename(base), s)
            fh.write(line + '\n')
            print('info ' + line)
        for f in all_fails:
            line = '%s run %d failure %s said=%s' % (label, run, fdesc(f), f[5] or 'nothing')
            fh.write(line + '\n')
            print('info ' + line)
    return all_fails


def judge(log, n):
    """(lines, whole, torn, missing, duplicate) of the log: a line is whole when it matches the one expected shape; torn is any
    other non-empty line; missing and duplicate count the (appender, number) pairs over the whole lines."""
    data = read_bytes(log) or b''
    lines = data.split(b'\n')
    tail = lines.pop() if lines else b''          # text after the last LF: a line with no terminator is torn
    seen = {}
    whole = torn = 0
    for ln in lines:
        if ln.endswith(b'\r'):   # the redactor child writes through the platform's text mode: CRLF on Windows, today's bytes
            ln = ln[:-1]
        m = WHOLE.match(ln)
        if m:
            whole += 1
            k = (m.group(1), int(m.group(2)))
            seen[k] = seen.get(k, 0) + 1
        else:
            torn += 1
    if tail:
        torn += 1
    want = [(t.encode(), i) for t in 'AB' for i in range(n)]
    missing = sum(1 for k in want if k not in seen)
    dup = sum(v - 1 for v in seen.values() if v > 1)
    return len(lines) + (1 if tail else 0), whole, torn, missing, dup


def fixture(ctx, name):
    base = '%s/k10c3-fixtures/%s-%d' % (ctx['work'], name, time.time_ns())
    register(ctx['work'], MANIFEST, base)
    os.makedirs(base, exist_ok=True)
    return base


def one_run(ctx, kind, label, r, n, tree=None, extra=None, base=None):
    """One run of the pair of appenders; returns the record dict (counts, judge numbers, failures, lock file)."""
    base = base or fixture(ctx, '%s-r%d' % (label, r))
    os.makedirs(base, exist_ok=True)
    log = base + '/steps.log'
    write_text(log, '')
    t0 = time.time()
    nz, kids = pair(ctx, kind, tree or ctx['tree'], log, n, extra)
    lines, whole, torn, missing, dup = judge(log, n)
    rec = dict(run=r, lines=lines, whole=whole, torn=torn, missing=missing, dup=dup, nz=nz, secs=time.time() - t0, base=base,
               lockfile=os.path.isfile(log + '.lock'), kids=kids)
    print('info %s run %d lines=%d whole=%d torn=%d missing=%d duplicate=%d appender_nonzero=%s lockfile=%s secs=%.1f' % (
        label, r, lines, whole, torn, missing, dup, nz, 'present' if rec['lockfile'] else 'absent', rec['secs']))
    rec['fails'] = keep_children(ctx, label, r, base, nz, kids)
    sys.stdout.flush()
    return rec


def counted_whole(rec, n):
    """Every call and every redactor child was counted for both appenders, with no failure of any class."""
    ks = rec['kids']
    return all(ks.get(t) is not None and ks[t][0] == n and ks[t][2] == n and ks[t][1] == 0 and ks[t][3] == 0 for t in 'AB') \
        and not rec['fails']


def fsum(recs):
    out = []
    for r in recs:
        out.append('run%d:%s' % (r['run'], ','.join(fdesc(f) for f in r['fails']) or 'none'))
    return '; '.join(out)


def row_locked(ctx, rid, expect, arg):
    n = ctx['lines']
    n2 = 2 * n
    runs = []
    for r in range(1, ctx['runs'] + 1):
        rec = one_run(ctx, 'tool', 'locked', r, n)
        runs.append(rec)
        if not (rec['lockfile'] and rec['lines'] == n2 and rec['whole'] == n2 and rec['torn'] == 0 and rec['missing'] == 0
                and rec['dup'] == 0 and rec['nz'] == [0, 0] and counted_whole(rec, n)):
            print('info locked stopped after run %d, which is not whole' % r)
            break
    ok = len(runs) == ctx['runs'] and all(r['lockfile'] and r['lines'] == n2 and r['whole'] == n2 and r['torn'] == 0
                                          and r['missing'] == 0 and r['dup'] == 0 and r['nz'] == [0, 0] and counted_whole(r, n)
                                          for r in runs)
    return ok, ('expected=%d runs of %d whole lines, the .lock file present, every call and redactor child counted with no failure '
                'actual=%d runs whole=%s lockfile_present=%s calls=%s failures=[%s]' % (
                    ctx['runs'], n2, len(runs), [r['whole'] for r in runs], [r['lockfile'] for r in runs],
                    [[(r['kids'][t][0], r['kids'][t][2]) if r['kids'].get(t) else None for t in 'AB'] for r in runs], fsum(runs)))


def row_control(ctx, rid, expect, arg):
    runs = [one_run(ctx, 'bare', 'control', r, ctx['lines']) for r in range(1, ctx['control_runs'] + 1)]
    readable = len(runs) == ctx['control_runs'] and all(r['nz'] == [0, 0] for r in runs)
    torn = sum(r['torn'] + r['missing'] + r['dup'] for r in runs)
    say = ('the unlocked appenders damaged %d line(s) over %d runs (torn+missing+duplicate)' % (torn, len(runs)) if torn
           else 'the unlocked appenders tore none in %d runs on this host; the lock is kept' % len(runs))
    return readable, 'expected=readable runs, torn count quoted actual=%s; lines per run %s failures=[%s]' % (
        say, [r['lines'] for r in runs], fsum(runs))


# ---- the fault rows ----

def row_fault_redactor(ctx, rid, expect, arg):
    """A fixture tree under work: the tree's bin with loop_redact.py replaced by a counting wrapper (the real redactor kept beside
    it as loop_redact_real.py) that exits FAULT_EXIT on the chosen call. The worktree's bin is not touched."""
    n = ctx['fault_lines']
    choose = n                                    # the middle call of the 2 x n calls
    ft = fixture(ctx, 'fault-redactor-tree')
    os.makedirs(ft + '/bin', exist_ok=True)
    src = ctx['tree'] + '/bin'
    for f in os.listdir(src):
        if f.endswith('.py'):
            shutil.copyfile(src + '/' + f, ft + '/bin/' + f)
    shutil.move(ft + '/bin/loop_redact.py', ft + '/bin/loop_redact_real.py')
    write_text(ft + '/bin/loop_redact.py', (
        'import os, sys\n'
        'HERE = os.path.dirname(os.path.abspath(__file__))\n'
        'CNT = os.path.join(os.path.dirname(HERE), "redactor-calls.txt")\n'
        'try:\n'
        '    n = int(open(CNT).read().strip() or 0)\n'
        'except (OSError, ValueError):\n'
        '    n = 0\n'
        'n += 1\n'
        'open(CNT, "w").write(str(n))\n'
        'if n == %d:\n'
        '    sys.stderr.write("fixture redactor: call %%d exits %d\\n" %% n)\n'
        '    sys.exit(%d)\n'
        'sys.path.insert(0, HERE)\n'
        'import loop_redact_real\n'
        'loop_redact_real.main()\n') % (choose, FAULT_EXIT, FAULT_EXIT))
    rec = one_run(ctx, 'tool', 'fault-redactor', 1, n, tree=ft, base=ft + '/run')
    calls_seen = (read_bytes(ft + '/redactor-calls.txt') or b'?').decode('ascii', 'replace')
    fs = rec['fails']
    named = len(fs) == 1 and fs[0][2] == 'redactor' and fs[0][3] == str(FAULT_EXIT) and fs[0][4] == str(FAULT_EXIT) \
        and 'class: redactor, exit code %d' % FAULT_EXIT in fs[0][5] and 'log path class: step log' in fs[0][5] \
        and 'Traceback' not in fs[0][5]
    signature = (rec['lines'] == 2 * n - 1 and rec['missing'] == 1 and rec['torn'] == 0 and rec['dup'] == 0 and rec['lockfile']
                 and sorted(rec['nz']) == [0, 1])
    ok = signature and named and calls_seen == str(2 * n)
    return ok, ('expected=the attempt-1 signature (lines=%d missing=1 one appender non-zero, lock file present) and one named line '
                '(class redactor, exit %d, log path class) actual=lines=%d missing=%d appender_nonzero=%s lockfile=%s '
                'redactor_calls_by_fixture=%s failures=[%s] named=%s' % (
                    2 * n - 1, FAULT_EXIT, rec['lines'], rec['missing'], rec['nz'], rec['lockfile'], calls_seen, fsum([rec]), named))


def row_fault_lock(ctx, rid, expect, arg):
    base = fixture(ctx, 'fault-lock')
    log = base + '/steps.log'
    release = hold(ctx['tree'], log + '.lock')
    try:
        rec = one_run(ctx, 'tool', 'fault-lock', 1, 2, extra={'LOOP_STEPLOG_LOCK_WAIT_S': '1'}, base=base)
    finally:
        release()
    fs = rec['fails']
    named = len(fs) == 4 and all(f[2] == 'lock' and f[3] == '5' and 'waited' in f[5] and 'lock path class' in f[5]
                                 and 'nothing was appended' in f[5] and 'Traceback' not in f[5] for f in fs)
    ok = named and rec['nz'] == [2, 2] and rec['lines'] == 0 and (read_bytes(log) or b'') == b''
    return ok, ('expected=every call exits 5 with the named lock line (class lock), nothing appended, no redactor child run '
                'actual=appender_nonzero=%s lines=%d failures=%d named=%s redactor_children=%s' % (
                    rec['nz'], rec['lines'], len(fs), named, [rec['kids'][t][2] if rec['kids'].get(t) else None for t in 'AB']))


# ---- the timeout rows ----

def load_tree_module(tree, name):
    spec = importlib.util.spec_from_file_location(name, tree + '/bin/' + name + '.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


WAIT_S = 2


def hold(tree, lockpath):
    """Take the lock on lockpath with the tree's own lock_exclusive(); returns release."""
    d = load_tree_module(tree, 'loop_dispatch')
    fh = open(lockpath, 'a+b')
    d.lock_exclusive(fh)

    def release():
        try:
            d.unlock(fh)
        finally:
            fh.close()
    return release


def run_cmd(ctx, args, env_extra, cwd):
    t0 = time.time()
    cp = subprocess.run([ctx['py']] + args, capture_output=True, env=make_env(ctx['home'], env_extra, DROP), cwd=cwd,
                        stdin=subprocess.DEVNULL, timeout=120)
    out = (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '')
    return cp.returncode, out, time.time() - t0


def named_failure(out, what):
    ls = [x for x in out.split('\n') if x.strip() and not x.startswith('ON DISK')]  # loop-report's own KEPT notice is not the failure line
    return (len(ls) == 1 and 'Traceback' not in out and 'lock' in ls[0] and 'waited' in ls[0] and what in ls[0]
            and 'lock path class' in ls[0] and 'nothing was appended' in ls[0]), len(ls)


def row_timeout_journal(ctx, rid, expect, arg):
    base = fixture(ctx, 'tj')
    log = base + '/steps.log'
    write_text(log, '- 2026-01-01T00:00:00Z %s GOAL START fixture\n' % G)
    before = read_bytes(log)
    tool = ctx['tree'] + '/bin/loop_journal.py'
    args = [tool, G, 'T01', 'NOTE one appended line']
    extra = {'JOURNAL_FILE': log, 'LOOP_STEPLOG_LOCK_WAIT_S': str(WAIT_S)}
    release = hold(ctx['tree'], log + '.lock') if os.path.isfile(tool) and os.path.isfile(ctx['tree'] + '/bin/loop_dispatch.py') else None
    try:
        rc, out, secs = run_cmd(ctx, args, extra, base)
    finally:
        if release:
            release()
    unchanged = read_bytes(log) == before
    named, nlines = named_failure(out, 'step log')
    rc2, out2, _ = run_cmd(ctx, args, extra, base)
    grew = read_bytes(log)
    appended = grew is not None and grew.startswith(before) and len(grew.split(b'\n')) == len(before.split(b'\n')) + 1
    ok = rc == 5 and named and unchanged and WAIT_S * 0.9 <= secs <= WAIT_S + 20 and rc2 == 0 and appended
    return ok, ('expected=exit 5 within the bound with one named line, log unchanged, then exit 0 and one line after release '
                'actual=exit %s lines=%d named=%s unchanged=%s secs=%.1f after_release=exit %s appended=%s' % (
                    rc, nlines, named, unchanged, secs, rc2, appended))


def row_timeout_report(ctx, rid, expect, arg):
    base = fixture(ctx, 'tr')
    lh = ctx['home'] + '/.loop'
    gdir = '%s/goals/%s' % (lh, 'K10-FIX-R-%d' % time.time_ns())
    os.makedirs(gdir, exist_ok=True)
    register(ctx['work'], MANIFEST, gdir)
    write_text(gdir + '/report.md', '# fixture report\nDONE\n')
    logp = lh + '/report.log'
    register(ctx['work'], MANIFEST, logp)
    register(ctx['work'], MANIFEST, logp + '.lock')
    tool = ctx['tree'] + '/bin/loop_report.py'
    size0 = len(read_bytes(logp) or b'')          # the home may hold a report.log from an earlier run: count what this row adds
    release = hold(ctx['tree'], logp + '.lock')
    try:
        rc, out, secs = run_cmd(ctx, [tool, gdir], {'LOOP_STEPLOG_LOCK_WAIT_S': str(WAIT_S)}, base)
    finally:
        release()
    size1 = len(read_bytes(logp) or b'')
    wrote = size1 > size0
    named, nlines = named_failure(out, 'report log')
    # the control: the same call with the lock free. Its exit code is the one the tool had before C3 for this fixture (no send command).
    rc2, out2, _ = run_cmd(ctx, [tool, gdir], {'LOOP_STEPLOG_LOCK_WAIT_S': str(WAIT_S)}, base)
    wrote2 = len(read_bytes(logp) or b'') > size1
    ok = rc == rc2 == 2 and named and not wrote and wrote2 and WAIT_S * 0.9 <= secs <= WAIT_S + 20
    return ok, ('expected=the exit code of the lock-free call (2: no send command), one named line for the report log, no report.log line '
                'while the lock is held, one after actual=exit %s lines=%d named=%s report_log_written=%s secs=%.1f '
                'lock_free_exit=%s lock_free_log_written=%s' % (rc, nlines, named, wrote, secs, rc2, wrote2))


KINDS = {'locked': row_locked, 'control': row_control, 'fault_redactor': row_fault_redactor, 'fault_lock': row_fault_lock,
         'timeout_journal': row_timeout_journal, 'timeout_report': row_timeout_report}


def main():
    tree, home, work = env_dirs(USAGE)
    if tree == '' or not os.path.isfile(tree + '/bin/loop_journal.py'):
        print('FAIL tree has no bin/loop_journal.py')
        return 2
    py = os.environ.get('LOOP_PY') or sys.executable
    clean_earlier(work, MANIFEST, say=True)
    ctx = dict(tree=tree, home=home, work=work, py=py, runs=int(os.environ.get('K10C3_RUNS', '3')),
               control_runs=int(os.environ.get('K10C3_CONTROL_RUNS', '1')), lines=int(os.environ.get('K10C3_LINES', '2000')),
               fault_lines=int(os.environ.get('K10C3_FAULT_LINES', '500')))
    os.makedirs(home + '/.loop', exist_ok=True)
    rows = load_rows(HERE + '/rows.txt', 3)
    return tally(rows, KINDS, pre=(ctx,), guard=True)


if __name__ == '__main__':
    if len(sys.argv) == 7 and sys.argv[1] == '--child':
        child_main(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]))
    sys.exit(main())
