#!/usr/bin/env python3
"""K06-C5 rows runner: a generated inventory (bin/loop-inventory) and one manifest column.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the first three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k06c5-manifest.txt
  LOOP_PY, LOOP_NAMES_FILE   handed to the children (LOOP_PY defaults to the interpreter running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  bytes     bash LOOP_TREE/bin/loop-inventory prints sections; each of them, found in docs/STATUS.md by its heading line and
            put together in the order printed, equals the tool output as bytes (both sha256 printed)
  columns   every line of MANIFEST.txt has the number of tab-separated columns in expect (two: path and repository hash);
            a tree with a third column, or with indented continuation lines, fails
  readme    README.md holds one line 'Kit files: N, counted by `wc -l < MANIFEST.txt`.' and N equals the lines of MANIFEST.txt
  absent    arg is 'relative path|text'; the text is nowhere in the file
  agents    AGENTS.md has no line starting with Row folders, Positional form or - Command files, and exactly one line names
            loop-inventory
  install   install.sh of the tree, environment form with LOOP_WITH_TESTS=1, into a throwaway home under LOOP_WORK: exit 0
            and the files named in arg are placed under .loop/bin, equal to the tree's (the tests land beside them)
  control   a scratch copy of docs/STATUS.md under LOOP_WORK holds the first figure changed by one byte: the bytes comparison
            of the rows above is printed as FAIL on a control line for it, and the row passes only when the unmodified
            copy compares equal, the changed copy does not, and exactly one byte differs

Prints PASS or FAIL per row with expected and actual (a sha256 stands in for any text that could hold a path), then
rows=N pass=P fail=F. Nothing is spawned in the background and nothing is killed.
"""
import hashlib
import os
import re
import subprocess
import sys
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, register, shafull, tally

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] '
         'python run.py (no positional argument)')
MANIFEST = 'k06c5-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
FIGURE_LINE = re.compile(r'^Kit files: ([0-9]+), counted by `wc -l < MANIFEST\.txt`\.$')


def sha_of(b):
    return hashlib.sha256(b).hexdigest()


def manifest_newlines(tree):
    b = read_bytes(tree + '/MANIFEST.txt')
    return None if b is None else b.count(b'\n')


def run_tool(ctx):
    """(exit code, stdout bytes) of bash LOOP_TREE/bin/loop-inventory, run to the end in the foreground."""
    env = make_env(ctx['home'], {'LOOP_PY': ctx['py']}, DROP)
    cp = subprocess.run(['bash', ctx['tree'] + '/bin/loop-inventory'], capture_output=True, env=env, cwd=ctx['work'])
    return cp.returncode, cp.stdout


def sections(b):
    """[(heading line, section bytes)] of a Markdown text in bytes: a section runs from a line starting with '## ' to the next."""
    out = []
    for ln in b.splitlines(True):
        if ln.startswith(b'## '):
            out.append([ln, ln])
        elif out:
            out[-1][1] += ln
    return [(h, s) for h, s in out]


def compare(tool_out, status):
    """(equal, detail): the sections of the tool output, found in the status text by heading and joined, equal the tool output."""
    ts = sections(tool_out)
    by_head = {}
    for h, s in sections(status):
        by_head.setdefault(h, s)
    found = [by_head[h] for h, _ in ts if h in by_head]
    joined = b''.join(found)
    ok = bool(tool_out) and len(ts) > 0 and len(found) == len(ts) and joined == tool_out
    detail = 'tool sha256=%s (%d bytes, %d sections) status sections sha256=%s (%d bytes, %d of %d found)' % (
        sha_of(tool_out), len(tool_out), len(ts), sha_of(joined), len(joined), len(found), len(ts))
    return ok, detail


def row_bytes(ctx, rid, expect, arg):
    rc, out = run_tool(ctx)
    status = read_bytes(ctx['tree'] + '/' + arg)
    if status is None:
        return False, 'expected=%s equal actual=%s absent' % (arg, arg)
    if rc != 0:
        return False, 'expected=tool exit 0 and the sections equal actual=tool exit %d (%d bytes of output, sha256=%s)' % (
            rc, len(out), sha_of(out))
    ok, detail = compare(out, status)
    return ok, 'expected=tool output equals the sections of %s as bytes actual=%s %s' % (arg, 'equal' if ok else 'differ', detail)


def row_columns(ctx, rid, expect, arg):
    b = read_bytes(ctx['tree'] + '/' + arg)
    if b is None:
        return False, 'expected=%s columns on every line actual=%s absent' % (expect, arg)
    want = int(expect)
    dist = {}
    cont = 0
    for ln in b.split(b'\n'):
        if not ln:
            continue
        cols = ln.rstrip(b'\r').split(b'\t')
        dist[len(cols)] = dist.get(len(cols), 0) + 1
        if cols[0] == b'':
            cont += 1
    total = sum(dist.values())
    ok = total > 0 and set(dist) == {want}
    return ok, 'expected=%d columns on every line actual=%d line(s) by column count %s, %d indented continuation line(s)' % (
        want, total, ' '.join('%d:%d' % (k, dist[k]) for k in sorted(dist)) or 'none', cont)


def row_readme(ctx, rid, expect, arg):
    b = read_bytes(ctx['tree'] + '/' + arg)
    n = manifest_newlines(ctx['tree'])
    if b is None or n is None:
        return False, 'expected=one figures line equal to the manifest lines actual=%s or MANIFEST.txt absent' % arg
    hits = [FIGURE_LINE.match(ln) for ln in b.decode('utf-8', 'replace').replace('\r', '').split('\n')]
    hits = [m for m in hits if m]
    stated = int(hits[0].group(1)) if len(hits) == 1 else None
    return stated == n, 'expected=one figures line naming the manifest line count actual=%d figures line(s), stated=%s manifest lines=%d' % (
        len(hits), stated, n)


def row_absent(ctx, rid, expect, arg):
    rel, text = arg.split('|', 1)
    b = read_bytes(ctx['tree'] + '/' + rel)
    if b is None:
        return False, 'expected=absent actual=%s unreadable' % rel
    got = 'found' if text.encode('utf-8') in b else 'absent'
    return got == expect, 'expected=%s actual=%s file sha256=%s' % (expect, got, sha_of(b)[:12])


def row_agents(ctx, rid, expect, arg):
    b = read_bytes(ctx['tree'] + '/' + arg)
    if b is None:
        return False, 'expected=%s actual=%s absent' % (expect, arg)
    lines = b.decode('utf-8', 'replace').replace('\r', '').split('\n')
    banned = [ln for ln in lines if ln.startswith(('Row folders', 'Positional form', '- Command files'))]
    naming = [ln for ln in lines if 'loop-inventory' in ln]
    ok = not banned and len(naming) == 1
    return ok, 'expected=no Row folders, Positional form or command list line, one line naming loop-inventory actual=%d banned line(s), %d naming line(s)' % (
        len(banned), len(naming))


def row_install(ctx, rid, expect, arg):
    names = arg.split('|')
    home = ctx['work'] + '/k06c5-install-home'
    register(ctx['work'], MANIFEST, home)
    os.makedirs(home)
    env = make_env(home, {'LOOP_PY': ctx['py'], 'LOOP_WITH_TESTS': '1'}, [d for d in DROP if d != 'LOOP_WITH_TESTS'])
    cp = subprocess.run(['bash', ctx['tree'] + '/install.sh'], capture_output=True, text=True, encoding='utf-8',
                        errors='replace', env=env, cwd=ctx['work'])
    state = []
    ok = cp.returncode == 0
    for n in names:
        src = read_bytes(ctx['tree'] + '/' + n)
        got = read_bytes(home + '/.loop/' + n)
        s = 'absent' if got is None else ('equal' if got == src else 'differs')
        ok = ok and s == 'equal'
        state.append('%s %s' % (n, s))
    tests = os.path.isfile(home + '/.loop/tests/rows/K06-C5/run.py')
    ok = ok and tests
    return ok, 'expected=exit 0, %s placed equal to the tree, tests placed beside actual=exit %d, %s, tests/rows/K06-C5/run.py %s out sha256=%s' % (
        ' and '.join(names), cp.returncode, ', '.join(state), 'placed' if tests else 'absent', sha_of((cp.stdout + cp.stderr).encode('utf-8', 'replace'))[:12])


def row_control(ctx, rid, expect, arg):
    rc, out = run_tool(ctx)
    src = read_bytes(ctx['tree'] + '/' + arg)
    if src is None or rc != 0:
        return False, 'expected=a tool output and %s to compare actual=tool exit %d, %s %s' % (arg, rc, arg, 'absent' if src is None else 'present')
    d = ctx['work'] + '/k06c5-control'
    register(ctx['work'], MANIFEST, d)
    os.makedirs(d)
    marker = b'$ wc -l < MANIFEST.txt\n'
    at = src.find(marker)
    m = re.compile(rb'[0-9]+').match(src, at + len(marker)) if at >= 0 else None
    if m is None:
        return False, 'expected=a figure after the manifest line command actual=none found in %s' % arg
    last = m.end() - 1
    changed = src[:last] + bytes([ord('0') + (src[last] - ord('0') + 1) % 10]) + src[last + 1:]
    diff = sum(1 for x, y in zip(src, changed) if x != y)
    for name, data in (('STATUS.unmodified.md', src), ('STATUS.changed.md', changed)):
        with open(d + '/' + name, 'wb') as fh:
            fh.write(data)
    same_ok, same_detail = compare(out, read_bytes(d + '/STATUS.unmodified.md'))
    chg_ok, chg_detail = compare(out, read_bytes(d + '/STATUS.changed.md'))
    print('%s control %s expected=tool output equals the sections actual=%s %s (scratch copy of %s with the figure on the line after the manifest command changed by one byte)' % (
        'PASS' if chg_ok else 'FAIL', 'g-control-compare', 'equal' if chg_ok else 'differ', chg_detail, arg))
    ok = same_ok and not chg_ok and diff == 1 and len(changed) == len(src)
    return ok, 'expected=unmodified copy equal, changed copy differ, one byte changed actual=unmodified %s, changed %s, %d byte(s) differ, controls=1' % (
        'equal' if same_ok else 'differ', 'equal' if chg_ok else 'differ', diff)


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K06-C5/run.py', here + '/run.py'), ('tests/rows/K06-C5/rows.txt', here + '/rows.txt')))
    rows = load_rows(here + '/rows.txt')
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    kinds = {'bytes': lambda r, e, a: row_bytes(ctx, r, e, a), 'columns': lambda r, e, a: row_columns(ctx, r, e, a),
             'readme': lambda r, e, a: row_readme(ctx, r, e, a), 'absent': lambda r, e, a: row_absent(ctx, r, e, a),
             'agents': lambda r, e, a: row_agents(ctx, r, e, a), 'install': lambda r, e, a: row_install(ctx, r, e, a),
             'control': lambda r, e, a: row_control(ctx, r, e, a)}
    return tally(rows, kinds, (), True)


if __name__ == '__main__':
    sys.exit(main())
