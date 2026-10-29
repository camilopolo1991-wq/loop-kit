#!/usr/bin/env python3
"""K04-C7 rows runner: the base texts stop naming the rules a goal's standing rules override. A phrase row looks for
a phrase the change adds; a removal row looks for words of the old stop rule, which must be gone.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expected verdicts in rows.txt,
so a tree without the change prints FAIL on the rows the change adds or removes), LOOP_ROWS_HOME (the home every
spawned process gets as HOME and USERPROFILE; LOOP_HOME is that home plus /.loop), LOOP_WORK (a work folder,
created when absent), LOOP_PY (accepted, unused), LOOP_NAMES_FILE (passed through untouched).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Nothing is spawned; the environment a spawned process would get is built anyway (HOME and USERPROFILE at
LOOP_ROWS_HOME, LOOP_HOME at LOOP_ROWS_HOME/.loop, PYTHONDONTWRITEBYTECODE=1). Files are read as bytes and the
phrase is searched as UTF-8 bytes, nothing normalised. Prints PASS or FAIL per row with expected and actual.
"""
import os
import sys

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', 3)])
    return rows


def make_env(home):
    env = dict(os.environ)
    env['HOME'] = home
    env['USERPROFILE'] = home
    env['LOOP_HOME'] = home + '/.loop'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


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
    tree, home, work = fwd(tree_e), fwd(home_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    make_env(home)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, expect, rel, phrase in rows:
        try:
            with open(tree + '/' + rel, 'rb') as fh:
                data = fh.read()
            actual = 'found' if phrase.encode('utf-8') in data else 'absent'
        except OSError:
            actual = 'unreadable'
        ok = actual == expect
        passed += ok
        failed += (not ok)
        print('%s %s expected=%s actual=%s file=%s' % ('PASS' if ok else 'FAIL', rid, expect, actual, rel))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
