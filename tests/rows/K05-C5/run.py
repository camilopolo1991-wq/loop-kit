#!/usr/bin/env python3
"""K05-C5 rows runner: the reviewer text carries the verdict-file rule, the git environment rule, the redactor-tag rule
and the two command rules of the owner's rulings; the scout text carries the return-length rule; skills/loop-audit
judges both (reviewer item 9, scout item 1).

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expectations in rows.txt, so a tree
without the change prints FAIL), LOOP_ROWS_HOME (accepted for layout parity with the K05-C4 runner), LOOP_WORK (a work
folder, created when absent, left empty), LOOP_PY and LOOP_NAMES_FILE (passed through untouched, unused here).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Rows read tree files only. A sha256 stands in for the searched text. Nothing is spawned, nothing is killed, no timeout
is set.
"""
import hashlib
import os
import sys

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def sha(s):
    return hashlib.sha256(s.encode('utf-8', 'replace')).hexdigest()[:12]


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', 3)])
    return rows


def text_of(tree, rel):
    try:
        with open(tree + '/' + rel, 'rb') as fh:
            return fh.read().decode('utf-8', 'replace').replace('\r', '')
    except OSError:
        return None


def row_linephrase(ctx, rid, expect, arg):
    rel, prefix, phrase = arg.split('|', 2)
    text = text_of(ctx['tree'], rel)
    if text is None:
        return False, 'expected=found actual=file absent'
    lines = [ln for ln in text.split('\n') if ln.startswith(prefix)]
    ok = any(phrase in ln for ln in lines)
    return ok, 'expected=found lines_with_prefix=%d actual=%s phrase_sha=%s' % (len(lines), 'found' if ok else 'not found', sha(phrase))


def row_phrase(ctx, rid, expect, arg):
    rel, phrase = arg.split('|', 1)
    text = text_of(ctx['tree'], rel)
    if text is None:
        return False, 'expected=found actual=file absent'
    ok = phrase in text
    return ok, 'expected=found actual=%s phrase_sha=%s' % ('found' if ok else 'not found', sha(phrase))


KINDS = {'linephrase': row_linephrase, 'phrase': row_phrase}


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
    ctx = {'tree': tree, 'home': home, 'work': work}
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        fn = KINDS.get(kind)
        if fn is None:
            ok, detail = False, 'unknown kind ' + kind
        else:
            try:
                ok, detail = fn(ctx, rid, expect, arg)
            except Exception as exc:
                ok, detail = False, 'expected=row runs actual=error %s' % type(exc).__name__
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
