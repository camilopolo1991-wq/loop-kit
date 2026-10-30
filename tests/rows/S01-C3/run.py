#!/usr/bin/env python3
"""S01-C3 rows runner: the status page docs/STATUS.md holds every figure of the kit, and the README holds no figure block.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same rows in rows.txt, so a tree without
docs/STATUS.md prints FAIL on the rows that need it), LOOP_ROWS_HOME (the home every child gets, with LOOP_HOME at that
home plus /.loop), LOOP_WORK (a work folder, created when absent), LOOP_PY and LOOP_NAMES_FILE (accepted, unused here).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
The runner writes no fixture. It removes at its start only what its own manifest file (s01c3-manifest.txt in LOOP_WORK)
lists from an earlier run, which is nothing today. The only children are short git reads under the tree, run to the end
in the foreground with HOME, USERPROFILE and LOOP_HOME at the rows home and core.autocrlf=false. Prints PASS or FAIL per
row with expected and actual, an info line with the sha256 of the runner's own two files, then rows=N pass=N fail=N.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import hashlib
import os
import re
import subprocess
import sys

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_PY=<python> LOOP_NAMES_FILE=<file> python run.py (no positional argument)'
MANIFEST = 's01c3-manifest.txt'
STATUS = 'docs/STATUS.md'

# The six kit figures: the command line as written in STATUS.md (after the dollar sign and a space), and the measurer.
FIGURES = [
    ('wc -l < MANIFEST.txt', 'manifest'),
    ('find bin -type f ! -name "*.py" ! -name "*.pyc" | wc -l', 'bin'),
    ('find hooks -type f ! -name "*.pyc" | wc -l', 'hooks'),
    ('find skills -type f -name SKILL.md | wc -l', 'skills'),
    ('find tests/rows -mindepth 1 -maxdepth 1 -type d | wc -l', 'rows'),
    ('git rev-list --count main', 'commits'),
]


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


def git(ctx, *args):
    """One git read under the tree; returns (returncode, stdout stripped)."""
    env = dict(os.environ)
    env.update({'HOME': ctx['home'], 'USERPROFILE': ctx['home'], 'LOOP_HOME': ctx['home'] + '/.loop'})
    env.pop('LOOP_GOAL', None)
    try:
        cp = subprocess.run(['git', '-c', 'core.autocrlf=false', '-C', ctx['tree']] + list(args), capture_output=True,
                            text=True, encoding='utf-8', errors='replace', env=env, cwd=ctx['work'])
    except OSError:
        return 127, ''
    return cp.returncode, cp.stdout.strip()


def files_under(base, keep):
    out = []
    for root, dirs, files in os.walk(base):
        for f in files:
            if keep(f):
                out.append(os.path.join(root, f))
    return out


def measure(ctx, kind):
    t = ctx['tree']
    if kind == 'manifest':
        b = read_bytes(t + '/MANIFEST.txt')
        return None if b is None else b.count(b'\n')
    if kind == 'bin':
        return len(files_under(t + '/bin', lambda f: not f.endswith('.py') and not f.endswith('.pyc')))
    if kind == 'hooks':
        return len(files_under(t + '/hooks', lambda f: not f.endswith('.pyc')))
    if kind == 'skills':
        return len(files_under(t + '/skills', lambda f: f == 'SKILL.md'))
    if kind == 'rows':
        base = t + '/tests/rows'
        return len([d for d in os.listdir(base) if os.path.isdir(base + '/' + d)]) if os.path.isdir(base) else None
    if kind == 'commits':
        rc, out = git(ctx, 'rev-list', '--count', 'main')
        return int(out) if rc == 0 and out.isdigit() else None
    return None


def status_figure(lines, cmd):
    """The value on the line after the line '$ <cmd>' in STATUS.md; None when absent or not a whole number."""
    for i, ln in enumerate(lines):
        if ln == '$ ' + cmd and i + 1 < len(lines):
            v = lines[i + 1].strip()
            return int(v) if v.isdigit() else None
    return None


def row_present(ctx, expect, arg):
    b = read_bytes(ctx['tree'] + '/' + arg)
    if b is None:
        return False, 'expected=%s present actual=absent' % arg
    return len(b) > 0, 'expected=%s present and not empty actual=%d bytes sha256=%s' % (arg, len(b), shafull(b))


def row_shalines(ctx, expect, arg):
    lines = read_lines(ctx, arg)
    if lines is None:
        return False, 'expected=%s actual=file absent' % expect
    pat = re.compile(r'^measured at commit ([0-9a-f]{40}) on ([0-9]{4}-[0-9]{2}-[0-9]{2})$')
    found = [ln for ln in lines if ln.startswith('measured at commit')]
    bad = []
    seen = {}
    for ln in found:
        m = pat.match(ln)
        if not m:
            bad.append('line not of the form')
            continue
        sha = m.group(1)
        if sha not in seen:
            rc, out = git(ctx, 'cat-file', '-t', sha)
            seen[sha] = (rc == 0 and out == 'commit')
        if not seen[sha]:
            bad.append('%s does not resolve' % sha[:8])
    ok = len(found) >= len(FIGURES) and not bad
    return ok, 'expected=%s actual=%d line(s), %d distinct sha(s), bad %d %s' % (expect, len(found), len(seen), len(bad), ';'.join(bad[:5]))


def row_figures(ctx, expect, arg):
    lines = read_lines(ctx, arg)
    if lines is None:
        return False, 'expected=%s actual=file absent' % expect
    bad = []
    shown = []
    for cmd, kind in FIGURES:
        want = measure(ctx, kind)
        got = status_figure(lines, cmd)
        shown.append('%s=%s/%s' % (kind, got, want))
        if want is None or got is None or want != got:
            bad.append(kind)
    return not bad, 'expected=%s actual=differ %d %s [stated/measured %s]' % (expect, len(bad), ','.join(bad), ' '.join(shown))


def row_nodollar(ctx, expect, arg):
    lines = read_lines(ctx, arg)
    if lines is None:
        return False, 'expected=%s actual=file absent' % expect
    hits = []
    inside = False
    first = False
    for i, ln in enumerate(lines, 1):
        if ln.startswith('```'):
            if not inside:
                inside = True
                first = True
            else:
                inside = False
            continue
        if inside and first:
            first = False
            if ln.startswith('$ '):
                hits.append(str(i))
    return not hits, 'expected=%s actual=%d fenced block(s) starting with a dollar sign and a space, at line(s) %s' % (expect, len(hits), ','.join(hits[:8]))


def row_noheading(ctx, expect, arg):
    rel, needle = arg.split('|', 1)
    lines = read_lines(ctx, rel)
    if lines is None:
        return False, 'expected=%s actual=file absent' % expect
    hits = [str(i) for i, ln in enumerate(lines, 1) if ln.startswith('#') and needle in ln]
    return not hits, 'expected=%s actual=%d heading(s) holding the words at line(s) %s' % (expect, len(hits), ','.join(hits))


def row_hasline(ctx, expect, arg):
    rel, needle = arg.split('|', 1)
    lines = read_lines(ctx, rel)
    if lines is None:
        return False, 'expected=%s actual=file absent' % expect
    n = len([ln for ln in lines if ln == needle])
    return n == 1, 'expected=%s actual=%d line(s) equal to it' % (expect, n)


def git_bytes(ctx, *args):
    """One git read under the tree; returns (returncode, stdout bytes)."""
    env = dict(os.environ)
    env.update({'HOME': ctx['home'], 'USERPROFILE': ctx['home'], 'LOOP_HOME': ctx['home'] + '/.loop'})
    env.pop('LOOP_GOAL', None)
    try:
        cp = subprocess.run(['git', '-c', 'core.autocrlf=false', '-C', ctx['tree']] + list(args), capture_output=True,
                            env=env, cwd=ctx['work'])
    except OSError:
        return 127, b''
    return cp.returncode, cp.stdout


def dollar_blocks(lines):
    """Each fenced block whose first line starts with a dollar sign and a space, as its list of lines (bytes)."""
    out = []
    cur = None
    for ln in lines:
        if ln.startswith(b'```'):
            if cur is None:
                cur = []
            else:
                if cur and cur[0].startswith(b'$ '):
                    out.append(cur)
                cur = None
            continue
        if cur is not None:
            cur.append(ln)
    return out


def row_moved(ctx, expect, arg):
    rel, sha = arg.split('|', 1)
    st = read_bytes(ctx['tree'] + '/' + rel)
    if st is None:
        return False, 'expected=%s actual=%s absent' % (expect, rel)
    rc, old = git_bytes(ctx, 'show', sha + ':README.md')
    if rc != 0 or not old:
        return False, 'expected=%s actual=git show of README.md at %s failed rc=%d' % (expect, sha[:8], rc)
    blocks = dollar_blocks(old.split(b'\n'))
    stl = st.split(b'\n')
    matched = 0
    hashes = []
    missing = []
    for i, b in enumerate(blocks, 1):
        n = len(b)
        found = any(stl[j:j + n] == b for j in range(len(stl) - n + 1))
        matched += found
        hashes.append(shafull(b'\n'.join(b))[:8])
        if not found:
            missing.append(str(i))
    ok = len(blocks) > 0 and matched == len(blocks)
    return ok, 'expected=%s actual=%d block(s) found at %s, %d matched, unmatched %s, block sha256 prefixes %s' % (
        expect, len(blocks), sha[:8], matched, ','.join(missing), ' '.join(hashes))


KINDS = {'moved': row_moved, 'present': row_present, 'shalines': row_shalines, 'figures': row_figures, 'nodollar': row_nodollar,
         'noheading': row_noheading, 'hasline': row_hasline}


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
    for label, p in (('tests/rows/S01-C3/run.py', here + '/run.py'), ('tests/rows/S01-C3/rows.txt', here + '/rows.txt')):
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
