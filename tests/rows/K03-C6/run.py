#!/usr/bin/env python3
"""K03-C6 rows runner: the effort line in the frontmatter of each of the five agent files.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (used only for the set-or-usage check; no row targets it),
LOOP_WORK (a work folder, created when absent; no row writes into it), LOOP_PY and LOOP_NAMES_FILE (accepted, unused).
Exits 64 with a usage line when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Phrase row: a bytes search for one exact line inside the frontmatter of one file (between the first three-dash line
and the next three-dash line). Frontmatter row: in each named file the first line is the three-dash line, a later
three-dash line closes the frontmatter, and a model line sits between them. Nothing is spawned.
Prints PASS or FAIL per row with the file, expected and actual.
"""
import hashlib
import os
import sys


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def sha(s):
    return hashlib.sha256(s).hexdigest()[:12]


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', 3)])
    return rows


def frontmatter(data):
    """Return the lines between the opening and closing three-dash lines, or None."""
    lines = data.replace(b'\r\n', b'\n').split(b'\n')
    if not lines or lines[0] != b'---':
        return None
    for i in range(1, len(lines)):
        if lines[i] == b'---':
            return lines[1:i]
    return None


def run_phrase(tree, expect, arg):
    rel, phrase = arg.split('|', 1)
    try:
        with open(tree + '/' + rel, 'rb') as fh:
            data = fh.read()
    except OSError:
        return False, 'file=%s expected=%s actual=unreadable' % (rel, expect)
    fm = frontmatter(data)
    actual = 'found' if fm is not None and phrase.encode('utf-8') in fm else 'absent'
    return actual == expect, 'file=%s expected=%s actual=%s file_sha=%s' % (rel, expect, actual, sha(data))


def run_frontmatter(tree, expect, arg):
    bad = []
    for rel in arg.split(','):
        try:
            with open(tree + '/' + rel, 'rb') as fh:
                data = fh.read()
        except OSError:
            bad.append(rel + ':unreadable')
            continue
        fm = frontmatter(data)
        if fm is None:
            bad.append(rel + ':no-frontmatter')
        elif not any(l.startswith(b'model:') for l in fm):
            bad.append(rel + ':no-model-line')
    actual = 'pass' if not bad else 'fail'
    return actual == expect, 'files=%d expected=%s actual=%s%s' % (len(arg.split(',')), expect, actual, (' bad=' + ';'.join(bad)) if bad else '')


def main():
    tree_e = os.environ.get('LOOP_TREE')
    home_e = os.environ.get('LOOP_ROWS_HOME')
    work_e = os.environ.get('LOOP_WORK')
    if not tree_e or not home_e or not work_e:
        print('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py')
        return 64
    tree, work = fwd(tree_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        if kind == 'phrase':
            ok, detail = run_phrase(tree, expect, arg)
        elif kind == 'frontmatter':
            ok, detail = run_frontmatter(tree, expect, arg)
        else:
            ok, detail = False, 'unknown kind ' + kind
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
