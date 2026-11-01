#!/usr/bin/env python3
"""K04-C5 rows runner: the leader's record and the audit's measure. Phrase rows (kind phrase: expected found) and
removal rows (kind removed: expected absent), each a bytes search for one phrase in a named file under the tree.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expected verdicts, so a
tree without the change prints FAIL), LOOP_ROWS_HOME (the home every spawned process gets as HOME and USERPROFILE;
LOOP_HOME is that home plus /.loop), LOOP_WORK (a work folder, created when absent), LOOP_PY (accepted, unused here;
default is the interpreter running this file), LOOP_NAMES_FILE (passed through untouched).
Every spawned process would get HOME and USERPROFILE set, LOOP_HOME under that home and PYTHONDONTWRITEBYTECODE=1;
these rows spawn nothing. Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import os
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import Score, env_dirs, load_rows, make_env, sha


def phrase_row(tree, rel, phrase, need=1):
    with open(tree + '/' + rel, 'rb') as fh:
        data = fh.read()
    found = data.count(phrase.encode('utf-8')) >= need
    return ('found' if found else 'absent'), sha(phrase)


def main():
    usage = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'
    tree, home, work = env_dirs(usage)
    make_env(home)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    score = Score()
    for rid, kind, rel, phrase in rows:
        actual, why = phrase_row(tree, rel, phrase, 2 if kind == 'twice' else 1)
        expect = 'absent' if kind == 'removed' else 'found'
        ok = actual == expect
        score.row(ok, rid, 'file=%s expected=%s actual=%s sha=%s' % (rel, expect, actual, why))
    return score.done(rows)


if __name__ == '__main__':
    sys.exit(main())
