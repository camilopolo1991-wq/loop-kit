#!/usr/bin/env python3
"""K04-C7 rows runner: the base texts stop naming the rules a goal's standing rules override. A phrase row looks for
a phrase the change adds; a removal row looks for words of the old stop rule, which must be gone.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expected verdicts in rows.txt,
so a tree without the change prints FAIL on the rows the change adds or removes), LOOP_ROWS_HOME (the home every
spawned process gets as HOME and USERPROFILE; LOOP_HOME is that home plus /.loop), LOOP_WORK (a work folder,
created when absent), LOOP_PY (accepted, unused), LOOP_NAMES_FILE (passed through untouched).
Nothing is spawned; the environment a spawned process would get is built anyway (HOME and USERPROFILE at
LOOP_ROWS_HOME, LOOP_HOME at LOOP_ROWS_HOME/.loop, PYTHONDONTWRITEBYTECODE=1). Files are read as bytes and the
phrase is searched as UTF-8 bytes, nothing normalised. Prints PASS or FAIL per row with expected and actual.
"""
import os
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import Score, env_dirs, load_rows, make_env

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'


def main():
    tree, home, work = env_dirs(USAGE)
    make_env(home)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    score = Score()
    for rid, expect, rel, phrase in rows:
        try:
            with open(tree + '/' + rel, 'rb') as fh:
                data = fh.read()
            actual = 'found' if phrase.encode('utf-8') in data else 'absent'
        except OSError:
            actual = 'unreadable'
        ok = actual == expect
        score.row(ok, rid, 'expected=%s actual=%s file=%s' % (expect, actual, rel))
    return score.done(rows)


if __name__ == '__main__':
    sys.exit(main())
