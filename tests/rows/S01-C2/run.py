#!/usr/bin/env python3
"""S01-C2 rows runner: AGENTS.md at the root and one-line DESCRIPTION.md files in the folders this goal writes.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same rows in rows.txt, so a tree without
the files prints FAIL on the rows that need them), LOOP_ROWS_HOME (the home any child would get, with LOOP_HOME at that
home plus /.loop; this runner reads files only and starts no child), LOOP_WORK (a work folder, created when absent;
fixtures would be written there), LOOP_PY and LOOP_NAMES_FILE (accepted, unused here).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
The runner removes at its start only what its own manifest file (s01c2-manifest.txt in LOOP_WORK) lists from an earlier
run. One row runs the C3 runner of the tree under test in the environment form as a child, with a work folder and a copy
of the synthetic names list under LOOP_WORK, both listed in that manifest. The top-level folders are read from the tree itself
(directories at the root, excluding .git). Prints PASS or FAIL per row with expected and actual, an info line with the
sha256 of MANIFEST.txt and of the runner's own two files, then rows=N pass=N fail=N. Nothing is spawned in the
background, nothing is killed, no timeout is set.
"""
import hashlib
import os
import re
import sys

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_PY=<python> LOOP_NAMES_FILE=<file> python run.py (no positional argument)'
MANIFEST = 's01c2-manifest.txt'
HEADINGS = ['## Where things are', '## Verify', '## Files that move together', '## Cost']
MAX_LINES = 120


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


def add_to_manifest(ctx, p):
    with open(ctx['work'] + '/' + MANIFEST, 'a', encoding='utf-8') as fh:
        fh.write(p + '\n')


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


def section(lines, name):
    """The lines under '## name' up to the next '## ' heading; None when the heading is absent."""
    out = None
    for ln in lines:
        if ln.startswith('## '):
            if out is not None:
                break
            if ln == '## ' + name:
                out = []
        elif out is not None:
            out.append(ln)
    return out


def tree_folders(tree):
    return sorted(d for d in os.listdir(tree) if d != '.git' and os.path.isdir(tree + '/' + d))


def listed_row_folders(lines):
    for ln in lines:
        if ln.startswith('Row folders: '):
            return ln[len('Row folders: '):].split()
    return None


def row_present(ctx, expect, arg):
    b = read_bytes(ctx['tree'] + '/' + arg)
    if b is None:
        return False, 'expected=%s present actual=absent' % arg
    return len(b) > 0, 'expected=%s present and not empty actual=%d bytes sha256=%s' % (arg, len(b), shafull(b))


def row_headings(ctx, expect, arg):
    lines = read_lines(ctx, arg)
    if lines is None:
        return False, 'expected=%s actual=file absent' % expect
    n = len(lines) - (1 if lines and lines[-1] == '' else 0)
    found = [ln for ln in lines if ln.startswith('## ')]
    ok = found == HEADINGS and n < MAX_LINES
    return ok, 'expected=%s actual=headings %s, %d lines' % (expect, 'match' if found == HEADINGS else 'differ (%d found)' % len(found), n)


def verify_commands(lines):
    sec = section(lines, 'Verify')
    return None if sec is None else [ln for ln in sec if ln.startswith('    ') and ln.strip()]


def row_verifypaths(ctx, expect, arg):
    lines = read_lines(ctx, arg)
    cmds = None if lines is None else verify_commands(lines)
    if cmds is None:
        return False, 'expected=%s actual=file or Verify section absent' % expect
    folders = listed_row_folders(lines) or []
    missing = []
    checked = 0
    for c in cmds:
        toks = re.findall(r'(?:bin|tests)/[^\s`]+', c)
        if not toks:
            missing.append('no bin/ or tests/ path in a command line')
        for t in toks:
            names = [t.replace('<folder>', f) for f in folders] if '<folder>' in t else [t]
            if '<folder>' in t and not folders:
                missing.append('placeholder with no Row folders line')
            for p in names:
                checked += 1
                if not os.path.exists(ctx['tree'] + '/' + p):
                    missing.append(p)
    ok = len(cmds) >= 4 and not missing and checked >= 4
    return ok, 'expected=%s actual=%d command lines, %d paths checked, missing %d %s' % (expect, len(cmds), checked, len(missing), ','.join(missing[:5]))


def row_verifyshape(ctx, expect, arg):
    lines = read_lines(ctx, arg)
    cmds = None if lines is None else verify_commands(lines)
    if cmds is None:
        return False, 'expected=%s actual=file or Verify section absent' % expect
    has = {
        'environment-form runner line': any(all(k in c for k in ('HOME=', 'USERPROFILE=', 'LOOP_HOME=', 'LOOP_TREE=', 'LOOP_ROWS_HOME=', 'LOOP_WORK=', 'tests/rows/<folder>/run.py')) for c in cmds),
        'scanner on a range': any('bin/loop-scan' in c and '--range' in c for c in cmds),
        'card lint on the example card': any('bin/loop-card-lint' in c and 'examples/example-card.md' in c for c in cmds),
        'skill lint on skills/': any('bin/loop-skill-lint' in c and 'skills/' in c for c in cmds),
    }
    absent = [k for k, v in has.items() if not v]
    return not absent, 'expected=%s actual=missing %d %s' % (expect, len(absent), ','.join(absent))


def row_descs(ctx, expect, arg):
    bad = []
    for rel in arg.split('|'):
        b = read_bytes(ctx['tree'] + '/' + rel)
        if b is None:
            bad.append(rel + ' absent')
            continue
        parts = b.decode('utf-8', 'replace').replace('\r\n', '\n').split('\n')
        if parts and parts[-1] == '':
            parts = parts[:-1]
        if len(parts) != 1 or not parts[0].endswith('.') or len(parts[0]) < 2:
            bad.append('%s (%d lines)' % (rel, len(parts)))
    return not bad, 'expected=%s actual=%d of %d bad %s' % (expect, len(bad), len(arg.split('|')), '; '.join(bad))


def row_topfolders(ctx, expect, arg):
    lines = read_lines(ctx, arg)
    sec = None if lines is None else section(lines, 'Where things are')
    if sec is None:
        return False, 'expected=%s actual=file or section absent' % expect
    text = '\n'.join(sec)
    folders = tree_folders(ctx['tree'])
    unnamed = [d for d in folders if '`%s/`' % d not in text]
    return bool(folders) and not unnamed, 'expected=%s actual=%d folders read from the tree, unnamed %d %s' % (expect, len(folders), len(unnamed), ','.join(unnamed))


def row_pairs(ctx, expect, arg):
    lines = read_lines(ctx, arg)
    sec = None if lines is None else section(lines, 'Files that move together')
    if sec is None:
        return False, 'expected=%s actual=file or section absent' % expect
    text = '\n'.join(sec)
    want = {
        'MANIFEST.txt with agents bin hooks skills templates': 'MANIFEST.txt' in text and all(d + '/' in text for d in ('agents', 'bin', 'hooks', 'skills', 'templates')),
        'agent files with the install fills': 'agents/' in text and 'install.sh' in text and '@LOOP_PYTHON@' in text,
        'README install section with install.sh': 'README.md' in text and 'install.sh' in text and 'install section' in text,
        'docs/STATUS.md with any figure': 'docs/STATUS.md' in text and 'figure' in text,
    }
    absent = [k for k, v in want.items() if not v]
    return not absent, 'expected=%s actual=missing %d %s' % (expect, len(absent), ','.join(absent))


def row_cost(ctx, expect, arg):
    lines = read_lines(ctx, arg)
    sec = None if lines is None else section(lines, 'Cost')
    if sec is None:
        return False, 'expected=%s actual=file or section absent' % expect
    text = ' '.join(sec)
    ok = 'Every line of this file and of every skill' in text and 'every run' in text
    return ok, 'expected=%s actual=rule %s' % (expect, 'present' if ok else 'absent')


def row_rowlist(ctx, expect, arg):
    lines = read_lines(ctx, arg)
    listed = None if lines is None else listed_row_folders(lines)
    if listed is None:
        return False, 'expected=%s actual=file or Row folders line absent' % expect
    base = ctx['tree'] + '/tests/rows'
    actual = sorted(d for d in os.listdir(base) if os.path.isdir(base + '/' + d)) if os.path.isdir(base) else []
    return sorted(listed) == actual and len(actual) > 0, 'expected=%s actual=listed %d, on disk %d, only listed %s, only on disk %s' % (
        expect, len(listed), len(actual), ','.join(sorted(set(listed) - set(actual))), ','.join(sorted(set(actual) - set(listed))))


def row_forms(ctx, expect, arg):
    """Every folder on the Row folders line has a run.py that reads LOOP_TREE (the environment form), and every folder
    on the Positional form line also reads its tree from the argument list. The needles are built from parts so this
    file holds neither one whole."""
    lines = read_lines(ctx, arg)
    if lines is None:
        return False, 'expected=%s actual=file absent' % expect
    pos_needle = 'sys.' + 'argv[1]'
    env_needle = 'os.environ.get(' + chr(39) + 'LOOP_TREE' + chr(39) + ')'
    allf = listed_row_folders(lines)
    found = [ln[len('Positional form: '):].split() for ln in lines if ln.startswith('Positional form: ')]
    if not allf or len(found) != 1:
        return False, 'expected=%s actual=the Row folders line is absent or the Positional form line is absent or repeated' % expect
    posf = found[0]
    wrong = []
    for f in allf:
        b = read_bytes(ctx['tree'] + '/tests/rows/' + f + '/run.py')
        text = '' if b is None else b.decode('utf-8', 'replace')
        if b is None or env_needle not in text:
            wrong.append('%s(no LOOP_TREE read)' % f)
        elif f in posf and pos_needle not in text:
            wrong.append('%s(listed positional, no argument read)' % f)
    subset = bool(posf) and set(posf) <= set(allf)
    return not wrong and subset, 'expected=%s actual=%d folders, %d also positional, misplaced %d %s, positional within folders %s' % (
        expect, len(allf), len(posf), len(wrong), ','.join(wrong[:5]), subset)


ENV_NAMES = ('HOME', 'USERPROFILE', 'LOOP_HOME', 'LOOP_TREE', 'LOOP_ROWS_HOME', 'LOOP_WORK', 'LOOP_PY', 'LOOP_NAMES_FILE')


def row_envline(ctx, expect, arg):
    lines = read_lines(ctx, arg)
    cmds = None if lines is None else verify_commands(lines)
    if cmds is None:
        return False, 'expected=%s actual=file or Verify section absent' % expect
    best = None
    for c in cmds:
        if 'tests/rows/<folder>/run.py' in c:
            toks = c.split()
            have = [n for n in ENV_NAMES if any(t.startswith(n + '=') for t in toks)]
            if 'PYTHONDONTWRITEBYTECODE=1' in toks:
                have.append('PYTHONDONTWRITEBYTECODE')
            if best is None or len(have) > len(best):
                best = have
    want = list(ENV_NAMES) + ['PYTHONDONTWRITEBYTECODE']
    missing = [n for n in want if best is None or n not in best]
    return not missing, 'expected=%s actual=missing %d %s' % (expect, len(missing), ','.join(missing))


def row_runone(ctx, expect, arg):
    """Runs one folder's runner in the environment form from the tree under test, under LOOP_WORK."""
    import subprocess
    rel = 'tests/rows/' + arg + '/run.py'
    if read_bytes(ctx['tree'] + '/' + rel) is None:
        return False, 'expected=%s actual=%s absent' % (expect, rel)
    names_src = os.environ.get('LOOP_NAMES_FILE', '')
    nb = read_bytes(names_src) if names_src else None
    names_dst = ctx['work'] + '/fixture-names.lst'
    if nb is not None:
        with open(names_dst, 'wb') as fh:
            fh.write(nb)
        add_to_manifest(ctx, names_dst)
    runwork = ctx['work'] + '/run-' + arg
    add_to_manifest(ctx, runwork)
    env = dict(os.environ)
    env.update({'HOME': ctx['home'], 'USERPROFILE': ctx['home'], 'LOOP_HOME': ctx['home'] + '/.loop', 'LOOP_TREE': ctx['tree'],
                'LOOP_ROWS_HOME': ctx['home'], 'LOOP_WORK': runwork, 'PYTHONDONTWRITEBYTECODE': '1'})
    env.pop('LOOP_GOAL', None)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    cp = subprocess.run([py, ctx['tree'] + '/' + rel], capture_output=True, text=True, encoding='utf-8', errors='replace',
                        env=env, cwd=ctx['work'])
    out = (cp.stdout + cp.stderr).replace('\r', '')
    m = re.search(r'^rows=(\d+) pass=(\d+) fail=(\d+)$', out, re.M)
    if not m:
        return False, 'expected=%s actual=rc=%d, no rows= line, first line sha256=%s' % (
            expect, cp.returncode, shafull((out.split('\n') or [''])[0].encode('utf-8', 'replace'))[:12])
    n, p, f = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return cp.returncode == 0 and n > 0 and f == 0 and p == n, 'expected=%s actual=rc=%d rows=%d pass=%d fail=%d' % (expect, cp.returncode, n, p, f)


def home_patterns():
    drive = re.compile('[A-Za-z]' + ':' + '[/' + chr(92) + chr(92) + ']')
    users = re.compile('[/' + chr(92) + chr(92) + ']' + '[Uu]sers' + '[/' + chr(92) + chr(92) + ']')
    home = re.compile('/' + 'home' + '/')
    return [drive, users, home]


def row_nohome(ctx, expect, arg):
    hits = []
    absent = 0
    pats = home_patterns()
    for rel in arg.split('|'):
        b = read_bytes(ctx['tree'] + '/' + rel)
        if b is None:
            absent += 1
            continue
        text = b.decode('utf-8', 'replace')
        for i, ln in enumerate(text.split('\n'), 1):
            if any(p.search(ln) for p in pats):
                hits.append('%s:%d' % (rel, i))
    return absent == 0 and not hits, 'expected=%s actual=%d file(s) absent, %d hit(s) %s' % (expect, absent, len(hits), ','.join(hits[:5]))


def row_manifest(ctx, expect, arg):
    m = read_bytes(ctx['tree'] + '/MANIFEST.txt')
    if m is None:
        return False, 'expected=%s actual=MANIFEST.txt absent' % expect
    rows = {}
    for ln in m.decode('utf-8', 'replace').split('\n'):
        t = ln.rstrip('\r').split('\t')
        if len(t) >= 3 and t[0]:
            rows[t[0]] = t
    bad = []
    shown = []
    for rel in arg.split('|'):
        b = read_bytes(ctx['tree'] + '/' + rel)
        if b is None:
            bad.append(rel + ' file absent')
            continue
        h = shafull(b)
        r = rows.get(rel)
        shown.append('%s sha256=%s' % (rel, h))
        if r is None:
            bad.append(rel + ' not listed')
        elif r[1] != h or r[2] != h:
            bad.append(rel + ' hash differs')
    return not bad, 'expected=%s actual=%d bad %s [%s]' % (expect, len(bad), '; '.join(bad), '; '.join(shown))


KINDS = {'present': row_present, 'headings': row_headings, 'verifypaths': row_verifypaths, 'verifyshape': row_verifyshape,
         'descs': row_descs, 'topfolders': row_topfolders, 'pairs': row_pairs, 'cost': row_cost, 'rowlist': row_rowlist,
         'forms': row_forms, 'envline': row_envline, 'runone': row_runone,'nohome': row_nohome, 'manifest': row_manifest}


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
    for label, p in (('tree MANIFEST.txt', tree + '/MANIFEST.txt'), ('tests/rows/S01-C2/run.py', here + '/run.py'),
                     ('tests/rows/S01-C2/rows.txt', here + '/rows.txt')):
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
