#!/usr/bin/env python3
"""K03-C4 rows runner: phrase rows for the Standing rules section of the goal template and the preamble sentence.

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (used only for the set-or-usage check; no row targets it),
LOOP_WORK (a work folder, created when absent; no row writes into it), LOOP_PY and LOOP_NAMES_FILE (accepted, unused).
Each row is a bytes search for one phrase in one named file under the tree. Nothing is spawned.
Prints PASS or FAIL per row with the file, expected and actual (found or absent).
"""
import os
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import env_dirs, load_rows, run_phrase, tally


def main():
    tree, home, work = env_dirs('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py', False)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    return tally(rows, {
        'phrase': lambda rid, expect, arg: run_phrase(tree, expect, arg, 'file=%s '),
    })


if __name__ == '__main__':
    sys.exit(main())
