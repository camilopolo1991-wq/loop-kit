#!/usr/bin/env python3
"""K03-C3 rows runner: phrase rows for the leader text, the loop-goal skill and the loop-audit skill.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (used only for the set-or-usage check; no row targets it),
LOOP_WORK (a work folder, created when absent; no row writes into it), LOOP_PY and LOOP_NAMES_FILE (accepted, unused).
Exits 64 with a usage line when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Each row is a bytes search for one phrase in one named file under the tree. Nothing is spawned.
Prints PASS or FAIL per row with the file, expected and actual (found or absent).
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


def run_phrase(tree, expect, arg):
    rel, phrase = arg.split('|', 1)
    try:
        with open(tree + '/' + rel, 'rb') as fh:
            data = fh.read()
    except OSError:
        return False, 'file=%s expected=%s actual=unreadable' % (rel, expect)
    actual = 'found' if phrase.encode('utf-8') in data else 'absent'
    return actual == expect, 'file=%s expected=%s actual=%s file_sha=%s' % (rel, expect, actual, sha(data))


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
        else:
            ok, detail = False, 'unknown kind ' + kind
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
