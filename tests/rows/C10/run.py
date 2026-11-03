#!/usr/bin/env python3
"""C10 rows runner: four statements and four audit items, each a phrase searched as bytes in its file.

Usage: run.py <tree> <home> <work>

phrase rows: a Python bytes search under <tree> for the phrase in the named file; a row passes when the
actual result (found or absent) equals the expected one.
HOME, USERPROFILE and LOOP_HOME point into <home>; the names file path is built from <work>'s parent.
Prints PASS or FAIL per row with the file's relative path and found or absent, then a count, and exits 1
on any FAIL. Nothing is spawned and nothing is killed.
"""
import os
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import dirs_or_args, fwd, load_rows, make_env, run_phrase, tally

NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder


def main():
    tree, home, work = dirs_or_args()
    os.makedirs(work, exist_ok=True)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = make_env(home, {'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE})
    os.environ.update(env)
    return tally(rows, {
        'phrase': lambda rid, expect, arg: run_phrase(tree, expect, arg, '%s '),
    })


if __name__ == '__main__':
    sys.exit(main())
