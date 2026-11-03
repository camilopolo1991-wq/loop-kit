#!/usr/bin/env python3
"""S01-C2 rows runner: AGENTS.md at the root and one-line DESCRIPTION.md files in the folders this goal writes.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same rows in rows.txt, so a tree without
the files prints FAIL on the rows that need them), LOOP_ROWS_HOME (the home any child would get, with LOOP_HOME at that
home plus /.loop; this runner reads files only and starts no child), LOOP_WORK (a work folder, created when absent;
fixtures would be written there), LOOP_PY and LOOP_NAMES_FILE (accepted, unused here).
The runner removes at its start only what its own manifest file (s01c2-manifest.txt in LOOP_WORK) lists from an earlier
run. One row runs the C3 runner of the tree under test in the environment form as a child, with a work folder and a copy
of the synthetic names list under LOOP_WORK, both listed in that manifest. The top-level folders are read from the tree itself
(directories at the root, excluding .git). Prints PASS or FAIL per row with expected and actual, an info line with the
sha256 of MANIFEST.txt and of the runner's own two files, then rows=N pass=N fail=N. Nothing is spawned in the
background, nothing is killed, no timeout is set.
"""
import ast
import importlib.util
import os
import re
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import (clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, read_lines, register,
    row_present, shafull, tally)

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_PY=<python> LOOP_NAMES_FILE=<file> python run.py (no positional argument)'
MANIFEST = 's01c2-manifest.txt'
HEADINGS = ['## Where things are', '## Verify', '## Files that move together', '## Cost']
MAX_LINES = 120


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


def inventory_lines(ctx):
    """The lines the tree's inventory tool prints for the tree (its render function, loaded from the tree's
    bin/loop_inventory.py), or None when the tree has no tool. The Row folders and Positional form lines come from here."""
    p = ctx['tree'] + '/bin/loop_inventory.py'
    if read_bytes(p) is None:
        return None
    spec = importlib.util.spec_from_file_location('loop_inventory_of_the_tree', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.render(ctx['tree']).split('\n')


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
    folders = listed_row_folders(inventory_lines(ctx) or []) or []
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
    lines = inventory_lines(ctx)
    listed = None if lines is None else listed_row_folders(lines)
    if listed is None:
        return False, 'expected=%s actual=inventory tool or its Row folders line absent' % expect
    base = ctx['tree'] + '/tests/rows'
    actual = sorted(d for d in os.listdir(base) if os.path.isdir(base + '/' + d)) if os.path.isdir(base) else []
    return sorted(listed) == actual and len(actual) > 0, 'expected=%s actual=listed %d, on disk %d, only listed %s, only on disk %s' % (
        expect, len(listed), len(actual), ','.join(sorted(set(listed) - set(actual))), ','.join(sorted(set(actual) - set(listed))))


def called_readers(text, lib):
    """(reads LOOP_TREE, reads sys.argv[1]): whether the runner source text really calls (an ast Call on a name it imports
    from _lib) a function of the library source lib that reads LOOP_TREE, and one that reads sys.argv[1]. A name that
    only appears in a comment or a string is not a call."""
    try:
        tree, ltree = ast.parse(text), ast.parse(lib)
    except SyntaxError:
        return False, False
    imported = {a.asname or a.name: a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == '_lib'
                for a in n.names}
    called = {imported[n.func.id] for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
              and n.func.id in imported}
    fns = [f for f in ltree.body if isinstance(f, ast.FunctionDef) and f.name in called]
    env = any(isinstance(c, ast.Constant) and c.value == 'LOOP_TREE' for f in fns for c in ast.walk(f))
    arg = any(isinstance(s, ast.Subscript) and ast.get_source_segment(lib, s) == 'sys.argv[1]' for f in fns for s in ast.walk(f))
    return env, arg


def row_forms(ctx, expect, arg):
    """Every folder on the Row folders line has a run.py that reads LOOP_TREE (the environment form), and every folder
    on the Positional form line also reads its tree from the argument list. The needles are built from parts so this
    file holds neither one whole. A runner may read the tree through the library functions env_dirs and dirs_or_args
    (tests/rows/_lib.py then holds the read)."""
    lines = inventory_lines(ctx)
    if lines is None:
        return False, 'expected=%s actual=inventory tool absent' % expect
    pos_needle = 'sys.' + 'argv[1]'
    env_needle = 'os.environ.get(' + chr(39) + 'LOOP_TREE' + chr(39) + ')'
    allf = listed_row_folders(lines)
    found = [ln[len('Positional form: '):].split() for ln in lines if ln.startswith('Positional form: ')]
    if not allf or len(found) != 1:
        return False, 'expected=%s actual=the Row folders line is absent or the Positional form line is absent or repeated' % expect
    posf = found[0]
    wrong = []
    lib = read_bytes(ctx['tree'] + '/tests/rows/_lib.py')
    libtext = '' if lib is None else lib.decode('utf-8', 'replace')
    for f in allf:
        b = read_bytes(ctx['tree'] + '/tests/rows/' + f + '/run.py')
        text = '' if b is None else b.decode('utf-8', 'replace')
        via_env, via_arg = called_readers(text, libtext)
        if b is None or not (env_needle in text or via_env):
            wrong.append('%s(no LOOP_TREE read)' % f)
        elif f in posf and not (pos_needle in text or via_arg):
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
        register(ctx['work'], MANIFEST, names_dst)
    runwork = ctx['work'] + '/run-' + arg
    register(ctx['work'], MANIFEST, runwork)
    env = make_env(ctx['home'], {'LOOP_TREE': ctx['tree'], 'LOOP_ROWS_HOME': ctx['home'], 'LOOP_WORK': runwork},
                   ('LOOP_GOAL',))
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
        if len(t) >= 2 and t[0]:
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
        elif r[1] != h:
            bad.append(rel + ' hash differs')
    return not bad, 'expected=%s actual=%d bad %s [%s]' % (expect, len(bad), '; '.join(bad), '; '.join(shown))


KINDS = {'present': row_present, 'headings': row_headings, 'verifypaths': row_verifypaths, 'verifyshape': row_verifyshape,
         'descs': row_descs, 'topfolders': row_topfolders, 'pairs': row_pairs, 'cost': row_cost, 'rowlist': row_rowlist,
         'forms': row_forms, 'envline': row_envline, 'runone': row_runone,'nohome': row_nohome, 'manifest': row_manifest}


def main():
    tree, home, work = env_dirs(USAGE)
    clean_earlier(work, MANIFEST, True)
    ctx = {'tree': tree, 'work': work, 'home': home}
    here = os.path.dirname(os.path.abspath(__file__))
    info_sha((('tree MANIFEST.txt', tree + '/MANIFEST.txt'), ('tests/rows/S01-C2/run.py', here + '/run.py'),
                     ('tests/rows/S01-C2/rows.txt', here + '/rows.txt')))
    rows = load_rows(os.path.join(here, 'rows.txt'))
    return tally(rows, KINDS, (ctx,), True, False)


if __name__ == '__main__':
    sys.exit(main())
