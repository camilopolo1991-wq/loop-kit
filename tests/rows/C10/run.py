#!/usr/bin/env python3
"""C10 rows runner: four statements and four audit items, each a phrase searched as bytes in its file.

Usage: run.py <tree> <home> <work>

phrase rows: a Python bytes search under <tree> for the phrase in the named file; a row passes when the
actual result (found or absent) equals the expected one.
HOME, USERPROFILE and LOOP_HOME point into <home>; the names file path is built from <work>'s parent.
Prints PASS or FAIL per row with the file's relative path and found or absent, then a count, and exits 1
on any FAIL. Nothing is spawned and nothing is killed.
"""
import hashlib
import os
import sys

NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder


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


def run_phrase(tree, expect, arg):
    rel, phrase = arg.split('|', 1)
    try:
        with open(tree + '/' + rel, 'rb') as fh:
            data = fh.read()
    except OSError:
        return False, '%s expected=%s actual=unreadable' % (rel, expect)
    found = phrase.encode('utf-8') in data
    actual = 'found' if found else 'absent'
    return actual == expect, '%s expected=%s actual=%s file_sha=%s' % (rel, expect, actual, sha(data))


def main():
    if len(sys.argv) == 1:
        tree_e = os.environ.get('LOOP_TREE')
        home_e = os.environ.get('LOOP_ROWS_HOME')
        work_e = os.environ.get('LOOP_WORK')
        if not tree_e or not home_e or not work_e:
            print('usage: run.py <tree> <home> <work>   or   LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> run.py')
            return 64
        sys.argv[1:] = [tree_e, home_e, work_e]
    if len(sys.argv) != 4:
        print('usage: run.py <tree> <home> <work>')
        return 2
    tree, home, work = fwd(sys.argv[1]), fwd(sys.argv[2]), fwd(sys.argv[3])
    os.makedirs(work, exist_ok=True)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = dict(os.environ)
    env.update({'HOME': home, 'USERPROFILE': home, 'LOOP_HOME': home + '/.loop',
                'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE,
                'PYTHONDONTWRITEBYTECODE': '1'})
    os.environ.update(env)
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
