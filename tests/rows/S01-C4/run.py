#!/usr/bin/env python3
"""S01-C4 rows runner: the drift test and the two guides.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (HOME and USERPROFILE of every child, with LOOP_HOME at that
home plus /.loop), LOOP_WORK (a work folder, created when absent), LOOP_PY and LOOP_NAMES_FILE (accepted, unused here).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.

The drift test is this runner. It fails (exit 1) when any of these has no line naming it in docs/STATUS.md, docs/guides/,
AGENTS.md or README.md of the tree: a command file under bin/ (a file that is not a .py module, not under __pycache__ and
not DESCRIPTION.md), a key of the DEFAULTS table in bin/loop_conf.py (read with ast, never imported), or a file under
hooks/ (caches left out). A name counts as named when a line holds it as a whole token: the characters before and after
it are not letters, digits, underscore or hyphen. Each unnamed item is printed as a line 'UNNAMED <kind> <name>'.
A drift row runs the drift test as a child of this file (flags -I -B, the environment variable S01C4_DRIFT_BIN set to the
bin folder to read). The control row copies the tree's bin into LOOP_WORK with one planted command file added and runs the
drift test against that copy. The other rows check that a guide holds its ordered items, in order. Every path the runner
creates is listed in s01c4-manifest.txt in LOOP_WORK; the next run removes only what that file lists. Prints PASS or FAIL
per row, an info line with the sha256 of the runner's own two files, then rows=N pass=N fail=N. Nothing is spawned in the
background and nothing is killed.
"""
import ast
import hashlib
import os
import re
import shutil
import subprocess
import sys

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_PY=<python> LOOP_NAMES_FILE=<file> python run.py (no positional argument)'
MANIFEST = 's01c4-manifest.txt'
CONTROL_DIR = 's01c4-control'
PLANTED = 'loop-planted-s01c4'


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def shafull(b):
    return hashlib.sha256(b).hexdigest()


def read_bytes(p):
    try:
        with open(p, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def read_text(p):
    b = read_bytes(p)
    return b.decode('utf-8', 'replace') if b is not None else ''


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', 3)])
    return rows


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


def add_to_manifest(ctx, p):
    with open(ctx['work'] + '/' + MANIFEST, 'a', encoding='utf-8') as fh:
        fh.write(p + '\n')


# ---- the drift test ----

def walk_files(top):
    out = []
    for root, dirs, files in os.walk(top):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            out.append(fwd(os.path.join(root, f)))
    return sorted(out)


def command_files(bindir):
    names = []
    for p in walk_files(bindir):
        base = p.rsplit('/', 1)[-1]
        if base.endswith('.py') or base.endswith('.pyc') or base == 'DESCRIPTION.md':
            continue
        names.append(base)
    return names


def default_keys(bindir):
    tree = ast.parse(read_text(bindir + '/loop_conf.py'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'DEFAULTS' for t in node.targets):
            if isinstance(node.value, ast.Dict):
                return [k.value for k in node.value.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    return []


def hook_files(tree):
    out = []
    for p in walk_files(tree + '/hooks'):
        base = p.rsplit('/', 1)[-1]
        if not base.endswith('.pyc'):
            out.append(base)
    return out


def naming_text(tree):
    parts = [read_text(tree + '/docs/STATUS.md'), read_text(tree + '/AGENTS.md'), read_text(tree + '/README.md')]
    for p in walk_files(tree + '/docs/guides'):
        parts.append(read_text(p))
    return '\n'.join(parts)


def is_named(name, text):
    return re.search(r'(?<![A-Za-z0-9_-])' + re.escape(name) + r'(?![A-Za-z0-9_-])', text) is not None


def drift(tree, bindir):
    text = naming_text(tree)
    lines = []
    for kind, names in (('command', command_files(bindir)), ('key', default_keys(bindir)), ('hook', hook_files(tree))):
        for n in names:
            if not is_named(n, text):
                lines.append('UNNAMED %s %s' % (kind, n))
    return lines


def drift_child_main(tree, bindir):
    lines = drift(tree, bindir)
    print('drift keys=%d commands=%d hooks=%d' % (len(default_keys(bindir)), len(command_files(bindir)), len(hook_files(tree))))
    for ln in lines:
        print(ln)
    return 1 if lines else 0


# ---- rows ----

def run_drift(ctx, bindir):
    env = dict(os.environ)
    env.update({'HOME': ctx['home'], 'USERPROFILE': ctx['home'], 'LOOP_HOME': ctx['home'] + '/.loop',
                'PYTHONDONTWRITEBYTECODE': '1', 'S01C4_DRIFT_BIN': bindir})
    cp = subprocess.run([sys.executable, '-I', '-B', os.path.abspath(__file__)],
                        capture_output=True, text=True, env=env, cwd=ctx['work'])
    unnamed = [ln[len('UNNAMED '):] for ln in cp.stdout.splitlines() if ln.startswith('UNNAMED ')]
    return cp.returncode, unnamed, cp.stdout


def row_present(ctx, expect, arg):
    b = read_bytes(ctx['tree'] + '/' + arg)
    got = 'present' if b else 'absent'
    return got == expect, 'expected=%s actual=%s bytes=%d' % (expect, got, len(b or b''))


def row_drift(ctx, expect, arg):
    rc, unnamed, _ = run_drift(ctx, ctx['tree'] + '/bin')
    got = 'exit=%d unnamed=%d' % (rc, len(unnamed))
    return got == expect, 'expected=%s actual=%s%s' % (expect, got, (' first=' + ','.join(unnamed[:6])) if unnamed else '')


def row_control(ctx, expect, arg):
    dest = ctx['work'] + '/' + CONTROL_DIR
    add_to_manifest(ctx, dest)
    shutil.copytree(ctx['tree'] + '/bin', dest + '/bin', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    with open(dest + '/bin/' + arg, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('#!/usr/bin/env bash\n# planted by the S01-C4 control row\n')
    rc, unnamed, out = run_drift(ctx, dest + '/bin')
    got = 'exit=%d planted=%s' % (rc, 'yes' if arg in out else 'no')
    return got == expect, 'expected=%s actual=%s unnamed=%d' % (expect, got, len(unnamed))


def row_order(ctx, expect, arg):
    parts = [x.strip() for x in arg.split(' ;; ')]
    text = read_text(ctx['tree'] + '/' + parts[0])
    pos = 0
    got = 'ordered'
    for i, item in enumerate(parts[1:], 1):
        at = text.find(item, pos)
        if at < 0:
            got = 'missing item %d' % i
            break
        pos = at + len(item)
    return got == expect, 'expected=%s actual=%s items=%d' % (expect, got, len(parts) - 1)


KINDS = {'present': row_present, 'drift': row_drift, 'control': row_control, 'order': row_order}


def main():
    child_bin = os.environ.get('S01C4_DRIFT_BIN')
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
    if child_bin:
        return drift_child_main(tree, fwd(child_bin))
    os.makedirs(work, exist_ok=True)
    cleaned = clean_earlier(work)
    print('cleaned %d path(s) listed by an earlier run' % cleaned)
    ctx = {'tree': tree, 'work': work, 'home': fwd(home_e)}
    here = os.path.dirname(os.path.abspath(__file__))
    for label, p in (('tests/rows/S01-C4/run.py', here + '/run.py'), ('tests/rows/S01-C4/rows.txt', here + '/rows.txt')):
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
