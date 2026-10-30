#!/usr/bin/env python3
"""S01-C5 rows runner: the decisions. Six ADRs under docs/adr/ and four out-of-scope notes under docs/out-of-scope/.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same rows in rows.txt, so a tree without
the decision files prints FAIL on every row that needs them), LOOP_ROWS_HOME (the home every child would get, with
LOOP_HOME at that home plus /.loop), LOOP_WORK (a work folder, created when absent), LOOP_PY and LOOP_NAMES_FILE
(accepted, unused here).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
The runner writes no fixture and starts no child process. It removes at its start only what its own manifest file
(s01c5-manifest.txt in LOOP_WORK) lists from an earlier run, which is nothing today. Prints PASS or FAIL per row with
expected and actual, an info line with the sha256 of the runner's own two files, then rows=N pass=N fail=N.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import hashlib
import os
import re
import sys

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_PY=<python> LOOP_NAMES_FILE=<file> python run.py (no positional argument)'
MANIFEST = 's01c5-manifest.txt'
HEADINGS = ['Context', 'Decision', 'Deliberately not', 'Consequences', 'Verification']
ROOTS = ('bin/', 'hooks/', 'tests/rows/')


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def shafull(b):
    return hashlib.sha256(b).hexdigest()


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', 3)])
    return rows


def read_bytes(p):
    try:
        with open(p, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def read_lines(ctx, rel):
    b = read_bytes(ctx['tree'] + '/' + rel)
    return None if b is None else b.decode('utf-8', 'replace').replace('\r\n', '\n').split('\n')


def remove_path(p):
    if os.path.isdir(p):
        for root, dirs, files in os.walk(p, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                os.chmod(fp, 0o600)
                os.remove(fp)
            for d in dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(p)
    elif os.path.exists(p):
        os.chmod(p, 0o600)
        os.remove(p)


def clean_earlier(work):
    mf = work + '/' + MANIFEST
    data = read_bytes(mf)
    if data is None:
        return 0
    n = 0
    for p in data.decode('utf-8', 'replace').split('\n'):
        p = p.strip()
        if p and fwd(p).startswith(work + '/') and fwd(p) != work + '/' + MANIFEST and os.path.exists(p):
            remove_path(p)
            n += 1
    os.remove(mf)
    return n


def row_present(ctx, expect, arg):
    b = read_bytes(ctx['tree'] + '/' + arg)
    if b is None:
        return False, 'expected=%s present actual=absent' % arg
    return len(b) > 0, 'expected=%s present and not empty actual=%d bytes sha256=%s' % (arg, len(b), shafull(b))


def headings_of(lines):
    """The level-two headings outside fenced blocks, in order."""
    out = []
    inside = False
    for ln in lines:
        if ln.startswith('```'):
            inside = not inside
            continue
        if not inside and ln.startswith('## '):
            out.append(ln[3:].strip())
    return out


def row_headings(ctx, expect, arg):
    bad = []
    for rel in arg.split('|'):
        lines = read_lines(ctx, rel)
        if lines is None:
            bad.append('%s absent' % rel)
        elif headings_of(lines) != HEADINGS:
            bad.append('%s has %d heading(s) not equal to the five' % (rel, len(headings_of(lines))))
    n = len(arg.split('|'))
    return not bad, 'expected=%s actual=%d of %d ok %s' % (expect, n - len(bad), n, ';'.join(bad))


def first_fenced_line(lines):
    """The first line inside the first fenced block after the Verification heading; None when absent."""
    seen = False
    inside = False
    for ln in lines:
        if not seen:
            if ln.strip() == '## Verification':
                seen = True
            continue
        if ln.startswith('## '):
            return None
        if ln.startswith('```'):
            if inside:
                return None
            inside = True
            continue
        if inside:
            return ln
    return None


def row_verifyfile(ctx, expect, arg):
    bad = []
    shown = []
    for rel in arg.split('|'):
        lines = read_lines(ctx, rel)
        if lines is None:
            bad.append('%s absent' % rel)
            continue
        fl = first_fenced_line(lines)
        word = fl.split()[0] if fl and fl.split() else ''
        ok = word.startswith(ROOTS) and os.path.isfile(ctx['tree'] + '/' + word)
        shown.append(word or 'none')
        if not ok:
            bad.append('%s first word %s' % (rel, word or 'none'))
    n = len(arg.split('|'))
    return not bad, 'expected=%s actual=%d of %d ok %s [first words %s]' % (expect, n - len(bad), n, ';'.join(bad), ' '.join(shown))


def row_underlines(ctx, expect, arg):
    bad = []
    counts = []
    for rel in arg.split('|'):
        lines = read_lines(ctx, rel)
        if lines is None:
            bad.append('%s absent' % rel)
            continue
        n = len(lines) - (1 if lines and lines[-1] == '' else 0)
        counts.append(str(n))
        if n >= 15:
            bad.append('%s has %d lines' % (rel, n))
    k = len(arg.split('|'))
    return not bad, 'expected=%s actual=%d of %d ok %s [line counts %s]' % (expect, k - len(bad), k, ';'.join(bad), ' '.join(counts))


def row_datedgoal(ctx, expect, arg):
    date_re = re.compile(r'^Date decided: .*[0-9]{4}-[0-9]{2}')
    goal_re = re.compile(r'^Goal that decided: [A-Za-z]+-[0-9]{2}')
    bad = []
    for rel in arg.split('|'):
        lines = read_lines(ctx, rel)
        if lines is None:
            bad.append('%s absent' % rel)
            continue
        d = len([ln for ln in lines if date_re.match(ln)])
        g = len([ln for ln in lines if goal_re.match(ln)])
        n = len([ln for ln in lines if 'not recorded in the kit' in ln])
        if d != 1 or g != 1 or n:
            bad.append('%s date lines %d goal lines %d unrecorded lines %d' % (rel, d, g, n))
    k = len(arg.split('|'))
    return not bad, 'expected=%s actual=%d of %d ok %s' % (expect, k - len(bad), k, ';'.join(bad))


KINDS = {'present': row_present, 'headings': row_headings, 'verifyfile': row_verifyfile, 'underlines': row_underlines,
         'datedgoal': row_datedgoal}


def main():
    if len(sys.argv) > 1:
        print(USAGE)
        return 64
    tree_e = os.environ.get('LOOP_TREE')
    home_e = os.environ.get('LOOP_ROWS_HOME')
    work_e = os.environ.get('LOOP_WORK')
    if not tree_e or not home_e or not work_e:
        print(USAGE)
        return 64
    tree, work = fwd(tree_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    cleaned = clean_earlier(work)
    print('cleaned %d path(s) listed by an earlier run' % cleaned)
    ctx = {'tree': tree, 'work': work, 'home': fwd(home_e)}
    here = os.path.dirname(os.path.abspath(__file__))
    for label, p in (('tests/rows/S01-C5/run.py', here + '/run.py'), ('tests/rows/S01-C5/rows.txt', here + '/rows.txt')):
        b = read_bytes(p)
        print('info sha256 %s %s' % (label, shafull(b) if b is not None else 'absent'))
    rows = load_rows(os.path.join(here, 'rows.txt'))
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        fn = KINDS.get(kind)
        if fn is None:
            ok, detail = False, 'unknown kind ' + kind
        else:
            try:
                ok, detail = fn(ctx, expect, arg)
            except Exception as exc:
                ok, detail = False, 'expected=row runs actual=error %s' % type(exc).__name__
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
