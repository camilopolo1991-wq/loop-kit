#!/usr/bin/env python3
"""K09-C2 rows runner: the report sha at send, with the sent copy (bin/loop_report.py).

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   a folder the runner may read; every child gets its own throwaway home under LOOP_WORK instead
  LOOP_WORK        the work folder; every fixture is written under it and listed in k09c2-manifest.txt
  LOOP_PY          the interpreter the tool and the stub are run with (defaults to the one running this file)
The comparison tree for the control row is LOOP_MAIN, else the sibling folder wt-main of LOOP_TREE, else the first parent of
"Merge kit-09" exported by git from LOOP_TREE under LOOP_ROWS_HOME (exit 64 naming LOOP_MAIN when none is found).

Each row (rows.txt, id :: kind :: expect :: arg) builds a throwaway home (HOME, USERPROFILE and LOOP_HOME inside it, bytecode
off, REPORT_SEND_CMD only in that home's config.env), writes a constructed report, runs LOOP_TREE/bin/loop_report.py by
path with the report folder given relative to the child's working folder, and judges report.log, the sent folder and the
stub's out file. The stub (stub_sender.py) writes the message it receives to its out file, so the out file exists only if
the stub was called. Every byte comparison carries a control: the same comparison against the expected bytes with the last
byte changed must come out unequal. Prints PASS or FAIL per row, then rows=N pass=P fail=F.
"""
import hashlib
import os
import re
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, find_base, fwd, info_sha, load_rows, make_env, read_bytes, register, shafull, tally

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py '
         '(no positional argument)')
MANIFEST = 'k09c2-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS', 'REPORT_SEND_CMD', 'REPORT_MAX_LINES')
HERE = os.path.dirname(os.path.abspath(__file__))
STUB = fwd(HERE + '/stub_sender.py')
GID = 'K09-FIX'
R1 = b'# K09-C2 fixture report\nconstructed line one\nconstructed line two\n'
R2 = b'# K09-C2 fixture report\nconstructed line one\nconstructed line twp\n'  # R1 with the last letter before the newline changed
R3 = b'# K09-C2 fixture\r\nbytes with CR LF and a lone CR \r and no final newline'
LOGRE = r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ %s ' + GID + r' \S+ '


def flip(b):
    return (b[:-1] + bytes([b[-1] ^ 1])) if b else b'\x01'


def eq(got, want):
    """(ok, text): got == want as bytes, and the control (got against want with its last byte changed) is unequal."""
    real = got == want
    ctrl = got == flip(want)
    return real and not ctrl, 'equal=%s control_one_byte_changed_equal=%s' % (real, ctrl)


class World:
    def __init__(self, ctx, tag, stub_exit=0, with_cmd=True, tree=None):
        self.ctx = ctx
        self.tree = tree or ctx['tree']
        self.base = '%s/k09c2-fixtures/%s-%d' % (ctx['work'], tag, time.time_ns())
        register(ctx['work'], MANIFEST, self.base)
        self.home = self.base + '/home'
        self.lh = self.home + '/.loop'
        os.makedirs(self.lh)
        os.makedirs(self.base + '/tmp')
        self.out = self.base + '/stub-out.bin'
        cfg = ''
        if with_cmd:
            cfg = 'REPORT_SEND_CMD=%s %s %s %d {file}\n' % (ctx['py'], STUB, self.out, stub_exit)
        with open(self.lh + '/config.env', 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(cfg)
        os.makedirs(self.base + '/' + GID)
        self.cleanups = []

    def report(self, data):
        with open(self.base + '/' + GID + '/report.md', 'wb') as fh:
            fh.write(data)

    def run(self, args=None):
        env = make_env(self.home, {'TEMP': self.base + '/tmp', 'TMP': self.base + '/tmp'}, DROP)
        cp = subprocess.run([self.ctx['py'], self.tree + '/bin/loop_report.py'] + (args if args is not None else [GID]),
                            capture_output=True, env=env, cwd=self.base, stdin=subprocess.DEVNULL)
        return cp.returncode, (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '')

    def lines(self):
        b = read_bytes(self.lh + '/report.log')
        # the tool appends in text mode, so a line ends CR LF on this host: the CR is set aside, the line is judged without it
        return [] if b is None else b.decode('utf-8').replace('\r', '').split('\n')[:-1]

    def sent(self):
        d = self.lh + '/sent'
        return sorted(os.listdir(d)) if os.path.isdir(d) else None

    def stub_out(self):
        return read_bytes(self.out)

    def done(self):
        for fn in self.cleanups:
            fn()


def sha_of(data):
    return hashlib.sha256(data).hexdigest()


def tailsha(line):
    m = re.search(r'sha256 ([0-9a-f]{64}|none)$', line)
    return m.group(1) if m else None


def a_log_line(ctx):
    w = World(ctx, 'a-line')
    w.report(R1)
    rc, out = w.run()
    ls = w.lines()
    want = sha_of(read_bytes(w.base + '/' + GID + '/report.md'))
    shape = len(ls) == 1 and re.fullmatch(LOGRE % 'SENT' + r'sha256 [0-9a-f]{64}', ls[0]) is not None
    got = tailsha(ls[0]).encode() if ls and tailsha(ls[0]) else b''
    ok, t = eq(got, want.encode())
    return rc == 0 and shape and ok, 'exit %d, log lines %d, SENT line ending in sha256 <64 hex> %s, log sha vs sha256 of report.md: %s, sha %s' % (
        rc, len(ls), shape, t, want[:12])


def a_copy(ctx):
    w = World(ctx, 'a-copy')
    w.report(R1)
    rc, out = w.run()
    sha = sha_of(R1)
    names = w.sent()
    data = read_bytes(w.lh + '/sent/%s.md' % sha) or b''
    ok, t = eq(data, R1)
    return rc == 0 and names == [sha + '.md'] and ok, 'exit %d, sent folder %s, copy vs report bytes: %s, sha %s' % (
        rc, 'one file named <sha>.md' if names == [sha + '.md'] else 'WRONG (%s)' % names, t, sha[:12])


def a_first_line(ctx):
    w = World(ctx, 'a-first')
    w.report(R1)
    rc, out = w.run()
    got = w.stub_out()
    if got is None:
        return False, 'exit %d, stub out file absent' % rc
    sha = sha_of(R1)
    first, _, rest = got.partition(b'\n')
    ok1, t1 = eq(first, b'report.md sha256 ' + sha.encode())
    ok2, t2 = eq(rest, R1)
    return rc == 0 and ok1 and ok2, 'exit %d, first line: %s; rest of the message vs report bytes: %s, sha %s' % (rc, t1, t2, sha[:12])


def a_binary(ctx):
    w = World(ctx, 'a-bin')
    w.report(R3)
    rc, out = w.run()
    sha = sha_of(R3)
    copy = read_bytes(w.lh + '/sent/%s.md' % sha) or b''
    got = w.stub_out() or b''
    ok1, t1 = eq(copy, R3)
    ok2, t2 = eq(got, b'report.md sha256 ' + sha.encode() + b'\n' + R3)
    return rc == 0 and ok1 and ok2, 'exit %d, copy: %s; message: %s, sha %s' % (rc, t1, t2, sha[:12])


def a_file_mode(ctx):
    w = World(ctx, 'a-file')
    w.report(R1)
    rc, out = w.run(['--file', GID + '/report.md', '--label', 'ticket-index'])
    ls = w.lines()
    sha = sha_of(R1)
    shape = len(ls) == 1 and re.fullmatch(LOGRE.replace(GID, 'ticket-index') % 'SENT' + 'sha256 ' + sha, ls[0]) is not None
    got = w.stub_out() or b''
    ok, t = eq(got, b'report.md sha256 ' + sha.encode() + b'\n' + R1)
    return rc == 0 and shape and ok, 'exit %d, SENT line with label and sha %s, message: %s, sha %s' % (rc, shape, t, sha[:12])


def b_same(ctx):
    w = World(ctx, 'b-same')
    w.report(R1)
    rc1, o1 = w.run()
    sha = sha_of(R1)
    p = w.lh + '/sent/%s.md' % sha
    m1 = os.stat(p).st_mtime_ns if os.path.exists(p) else None
    time.sleep(0.05)
    rc2, o2 = w.run()
    m2 = os.stat(p).st_mtime_ns if os.path.exists(p) else None
    ls = w.lines()
    shas = [tailsha(x) for x in ls]
    ok, t = eq(read_bytes(p) or b'', R1)
    return (rc1 == 0 and rc2 == 0 and w.sent() == [sha + '.md'] and len(ls) == 2 and shas == [sha, sha] and m1 == m2 and ok), \
        'exits %d,%d, copies in sent folder %s, two log lines with one sha %s, copy untouched (mtime equal) %s, copy bytes: %s, sha %s' % (
            rc1, rc2, len(w.sent() or []), shas == [sha, sha], m1 == m2, t, sha[:12])


def b_changed(ctx):
    w = World(ctx, 'b-chg')
    w.report(R1)
    rc1, o1 = w.run()
    w.report(R2)
    rc2, o2 = w.run()
    s1, s2 = sha_of(R1), sha_of(R2)
    ls = w.lines()
    shas = [tailsha(x) for x in ls]
    ok1, t1 = eq(read_bytes(w.lh + '/sent/%s.md' % s1) or b'', R1)
    ok2, t2 = eq(read_bytes(w.lh + '/sent/%s.md' % s2) or b'', R2)
    diff = sum(1 for a, b in zip(R1, R2) if a != b) + abs(len(R1) - len(R2))
    return (rc1 == 0 and rc2 == 0 and s1 != s2 and diff == 1 and w.sent() == sorted([s1 + '.md', s2 + '.md']) and shas == [s1, s2]
            and ok1 and ok2), 'exits %d,%d, bytes differing between the two reports %d, copies %d, log shas %s and differ %s, copy1: %s; copy2: %s, shas %s %s' % (
        rc1, rc2, diff, len(w.sent() or []), 'match the two reports' if shas == [s1, s2] else 'WRONG', s1 != s2, t1, t2, s1[:12], s2[:12])


def b_clash(ctx):
    w = World(ctx, 'b-clash')
    w.report(R1)
    sha = sha_of(R1)
    os.makedirs(w.lh + '/sent')
    with open(w.lh + '/sent/%s.md' % sha, 'wb') as fh:
        fh.write(b'not the report')
    rc, out = w.run()
    ls = w.lines()
    kept = read_bytes(w.lh + '/sent/%s.md' % sha)
    ok, t = eq(kept or b'', b'not the report')
    shape = len(ls) == 1 and ' NOT SENT ' in ls[0] and 'existing sent copy has other bytes' in ls[0] and tailsha(ls[0]) == sha
    return rc == 2 and shape and ok and w.stub_out() is None, 'exit %d, NOT SENT line with the reason and the sha %s, existing file left as it was: %s, stub out absent %s' % (
        rc, shape, t, w.stub_out() is None)


def c_exit1(ctx):
    w = World(ctx, 'c-exit1', stub_exit=1)
    w.report(R1)
    rc, out = w.run()
    ls = w.lines()
    sha = sha_of(R1)
    shape = len(ls) == 1 and re.fullmatch(LOGRE % 'NOT SENT' + r'sender exit 1 sha256 ' + sha, ls[0]) is not None
    return rc == 1 and shape and w.stub_out() is not None, 'exit %d, NOT SENT line with reason and sha256 %s, stub called %s, sha %s' % (
        rc, shape, w.stub_out() is not None, sha[:12])


def c_kept(ctx):
    w = World(ctx, 'c-kept', with_cmd=False)
    w.report(R1)
    rc, out = w.run()
    ls = w.lines()
    sha = sha_of(R1)
    shape = len(ls) == 1 and re.fullmatch(LOGRE % 'KEPT' + r'REPORT_SEND_CMD not configured sha256 ' + sha, ls[0]) is not None
    return rc == 2 and shape and w.sent() is None, 'exit %d, KEPT line with sha256 %s, sent folder absent (nothing was sent) %s, sha %s' % (
        rc, shape, w.sent() is None, sha[:12])


def c_scan(ctx):
    w = World(ctx, 'c-scan')
    data = b'constructed line\nAPI key: ' + b'Zq9Xw3Lm' * 3 + b'\n'  # a constructed placeholder, built here so no file holds the shape
    w.report(data)
    rc, out = w.run()
    ls = w.lines()
    sha = sha_of(data)
    shape = len(ls) == 1 and re.fullmatch(LOGRE % 'NOT SENT' + r'loop-scan hit sha256 ' + sha, ls[0]) is not None
    return rc == 1 and shape and w.stub_out() is None and w.sent() is None, 'exit %d, NOT SENT line with reason and sha256 %s, stub out absent %s, sent folder absent %s, sha %s' % (
        rc, shape, w.stub_out() is None, w.sent() is None, sha[:12])


def c_missing(ctx):
    w = World(ctx, 'c-missing')
    rc, out = w.run()
    ls = w.lines()
    shape = len(ls) == 1 and re.fullmatch(LOGRE % 'NOT SENT' + r'no report file sha256 none', ls[0]) is not None
    return rc == 2 and shape and w.stub_out() is None, 'exit %d, NOT SENT line with reason and sha256 none %s, stub out absent %s' % (
        rc, shape, w.stub_out() is None)


def deny_write(path):
    """Make a folder refuse new files for everyone. Returns (undo, how)."""
    if os.name == 'nt':
        subprocess.run(['icacls', path, '/deny', '*S-1-1-0:(OI)(CI)(WD,AD)'], capture_output=True, check=True)
        return (lambda: subprocess.run(['icacls', path, '/remove:d', '*S-1-1-0'], capture_output=True)), 'ACL deny write'
    os.chmod(path, 0o555)
    return (lambda: os.chmod(path, 0o755)), 'mode 555'


def d_readonly(ctx):
    w = World(ctx, 'd-ro')
    w.report(R1)
    sent = w.lh + '/sent'
    os.makedirs(sent)
    undo, how = deny_write(sent)
    w.cleanups.append(undo)
    try:
        try:
            with open(sent + '/probe', 'xb'):
                pass
            os.remove(sent + '/probe')
            return False, 'fixture defect: a probe file could be created in the sent folder (%s did not take effect)' % how
        except OSError:
            pass
        rc, out = w.run()
        ls = w.lines()
        shape = len(ls) == 1 and re.fullmatch(LOGRE % 'NOT SENT' + r'sent copy failed \(\w+\) sha256 ' + sha_of(R1), ls[0]) is not None
        names = os.listdir(sent)
    finally:
        w.done()
    return rc == 2 and shape and w.stub_out() is None and names == [], 'exit %d, folder made read-only by %s and a probe write refused, NOT SENT line with reason and sha256 %s, stub out absent %s, files in sent folder %d' % (
        rc, how, shape, w.stub_out() is None, len(names))


def d_sentfile(ctx):
    w = World(ctx, 'd-file')
    w.report(R1)
    with open(w.lh + '/sent', 'wb') as fh:
        fh.write(b'a file where the folder should be')
    rc, out = w.run()
    ls = w.lines()
    shape = len(ls) == 1 and re.fullmatch(LOGRE % 'NOT SENT' + r'sent copy failed \(\w+\) sha256 ' + sha_of(R1), ls[0]) is not None
    return rc == 2 and shape and w.stub_out() is None, 'exit %d, NOT SENT line with reason and sha256 %s, stub out absent %s' % (
        rc, shape, w.stub_out() is None)


def deny_read(path):
    """Make a file refuse reads for everyone (it still exists and can still be stat-ed). Returns (undo, how)."""
    if os.name == 'nt':
        subprocess.run(['icacls', path, '/deny', '*S-1-1-0:(RD)'], capture_output=True, check=True)
        return (lambda: subprocess.run(['icacls', path, '/remove:d', '*S-1-1-0'], capture_output=True)), 'ACL deny read data'
    os.chmod(path, 0o000)
    return (lambda: os.chmod(path, 0o644)), 'mode 000'


def d_unreadable(ctx):
    w = World(ctx, 'd-unread')
    w.report(R1)
    rep = w.base + '/' + GID + '/report.md'
    undo, how = deny_read(rep)
    w.cleanups.append(undo)
    try:
        try:
            with open(rep, 'rb') as fh:
                fh.read(1)
            return False, 'fixture defect: the report file could be read (%s did not take effect)' % how
        except OSError as e:
            refused = e.__class__.__name__
        exists = os.path.isfile(rep)
        rc, out = w.run()
        ls = w.lines()
        shape = len(ls) == 1 and re.fullmatch(LOGRE % 'NOT SENT' + r'hash failed: report unreadable sha256 none', ls[0]) is not None
        sent = w.sent()
        outfile = w.stub_out()
    finally:
        w.done()
    intact = read_bytes(rep)  # after the deny is removed: the file was there, with the bytes written
    ok, t = eq(intact or b'', R1)
    return rc == 2 and exists and shape and sent is None and outfile is None and ok, 'exit %d, report file exists %s and a probe read refused by %s (%s), NOT SENT line with the hash-failure reason and sha256 none %s, sent folder absent %s, stub out absent %s, file bytes after the deny is removed: %s' % (
        rc, exists, refused, how, shape, sent is None, outfile is None, t)


def control_main(ctx):
    main = ctx['main']
    if not os.path.isfile(main + '/bin/loop_report.py'):
        return False, 'the comparison tree holds no bin/loop_report.py'
    w = World(ctx, 'ctl-main', tree=fwd(main))
    w.report(R1)
    rc, out = w.run()
    ls = w.lines()
    line = ls[0] if ls else ''
    return rc == 0 and len(ls) == 1 and 'sha256' not in line and ' SENT ' in line, 'exit %d, main tool report.log line: [%s] (no sha256 in it)' % (rc, line)


CHECKS = {k[0:].replace('a_', 'a_'): v for k, v in globals().items() if callable(v) and k[:2] in ('a_', 'b_', 'c_', 'd_')}
CHECKS['control_main'] = control_main


def row_check(ctx, rid, expect, arg):
    return CHECKS[arg](ctx)


def main():
    tree, home, work = env_dirs(USAGE)
    # KIT-11 T08: the comparison tree is LOOP_MAIN, else wt-main beside the tree, else the first parent of "Merge kit-09" exported by git
    main_tree = find_base(tree, home, 'kit-09')
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K09-C2/run.py', HERE + '/run.py'), ('tests/rows/K09-C2/rows.txt', HERE + '/rows.txt'),
              ('tests/rows/K09-C2/stub_sender.py', HERE + '/stub_sender.py')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable), 'main': main_tree}
    return tally(load_rows(HERE + '/rows.txt'), {'check': row_check}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
