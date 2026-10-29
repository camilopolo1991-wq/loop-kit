#!/usr/bin/env python3
"""K04-C5 rows runner: the leader's record and the audit's measure. Phrase rows (kind phrase: expected found) and
removal rows (kind removed: expected absent), each a bytes search for one phrase in a named file under the tree.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expected verdicts, so a
tree without the change prints FAIL), LOOP_ROWS_HOME (the home every spawned process gets as HOME and USERPROFILE;
LOOP_HOME is that home plus /.loop), LOOP_WORK (a work folder, created when absent), LOOP_PY (accepted, unused here;
default is the interpreter running this file), LOOP_NAMES_FILE (passed through untouched).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Every spawned process would get HOME and USERPROFILE set, LOOP_HOME under that home and PYTHONDONTWRITEBYTECODE=1;
these rows spawn nothing. Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import hashlib
import os
import sys


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def sha(s):
    if isinstance(s, str):
        s = s.encode('utf-8', 'replace')
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


def make_env(home):
    env = dict(os.environ)
    env['HOME'] = home
    env['USERPROFILE'] = home
    env['LOOP_HOME'] = home + '/.loop'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env.pop('JOURNAL_FILE', None)
    return env


def phrase_row(tree, rel, phrase, need=1):
    with open(tree + '/' + rel, 'rb') as fh:
        data = fh.read()
    found = data.count(phrase.encode('utf-8')) >= need
    return ('found' if found else 'absent'), sha(phrase)


def main():
    usage = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'
    if len(sys.argv) > 1:
        print(usage)
        return 64
    tree_e = os.environ.get('LOOP_TREE')
    home_e = os.environ.get('LOOP_ROWS_HOME')
    work_e = os.environ.get('LOOP_WORK')
    if not tree_e or not home_e or not work_e:
        print(usage)
        return 64
    tree, home, work = fwd(tree_e), fwd(home_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    make_env(home)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, kind, rel, phrase in rows:
        actual, why = phrase_row(tree, rel, phrase, 2 if kind == 'twice' else 1)
        expect = 'absent' if kind == 'removed' else 'found'
        ok = actual == expect
        passed += ok
        failed += (not ok)
        print('%s %s file=%s expected=%s actual=%s sha=%s' % ('PASS' if ok else 'FAIL', rid, rel, expect, actual, why))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
