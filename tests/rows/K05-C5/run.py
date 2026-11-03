#!/usr/bin/env python3
"""K05-C5 rows runner: the reviewer text carries the verdict-file rule, the git environment rule, the redactor-tag rule
and the two command rules of the owner's rulings; the scout text carries the return-length rule; skills/loop-audit
judges both (reviewer item 9, scout item 1).

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expectations in rows.txt, so a tree
without the change prints FAIL), LOOP_ROWS_HOME (accepted for layout parity with the K05-C4 runner), LOOP_WORK (a work
folder, created when absent, left empty), LOOP_PY and LOOP_NAMES_FILE (passed through untouched, unused here).
Rows read tree files only. A sha256 stands in for the searched text. Nothing is spawned, nothing is killed, no timeout
is set.
"""
import os
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import env_dirs, load_rows, row_linephrase, row_phrase, tally

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'


KINDS = {'linephrase': row_linephrase, 'phrase': row_phrase}


def main():
    tree, home, work = env_dirs(USAGE)
    ctx = {'tree': tree, 'home': home, 'work': work}
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    return tally(rows, KINDS, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
