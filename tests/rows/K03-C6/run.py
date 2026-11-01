#!/usr/bin/env python3
"""K03-C6 rows runner: the effort line in the frontmatter of each of the five agent files.

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (used only for the set-or-usage check; no row targets it),
LOOP_WORK (a work folder, created when absent; no row writes into it), LOOP_PY and LOOP_NAMES_FILE (accepted, unused).
Phrase row: a bytes search for one exact line inside the frontmatter of one file (between the first three-dash line
and the next three-dash line). Frontmatter row: in each named file the first line is the three-dash line, a later
three-dash line closes the frontmatter, and a model line sits between them. Nothing is spawned.
Prints PASS or FAIL per row with the file, expected and actual.
"""
import os
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import env_dirs, load_rows, sha, tally


def frontmatter(data):
    """Return the lines between the opening and closing three-dash lines, or None."""
    lines = data.replace(b'\r\n', b'\n').split(b'\n')
    if not lines or lines[0] != b'---':
        return None
    for i in range(1, len(lines)):
        if lines[i] == b'---':
            return lines[1:i]
    return None


def run_fm_phrase(tree, expect, arg):
    rel, phrase = arg.split('|', 1)
    try:
        with open(tree + '/' + rel, 'rb') as fh:
            data = fh.read()
    except OSError:
        return False, 'file=%s expected=%s actual=unreadable' % (rel, expect)
    fm = frontmatter(data)
    actual = 'found' if fm is not None and phrase.encode('utf-8') in fm else 'absent'
    return actual == expect, 'file=%s expected=%s actual=%s file_sha=%s' % (rel, expect, actual, sha(data))


def run_frontmatter(tree, expect, arg):
    bad = []
    for rel in arg.split(','):
        try:
            with open(tree + '/' + rel, 'rb') as fh:
                data = fh.read()
        except OSError:
            bad.append(rel + ':unreadable')
            continue
        fm = frontmatter(data)
        if fm is None:
            bad.append(rel + ':no-frontmatter')
        elif not any(l.startswith(b'model:') for l in fm):
            bad.append(rel + ':no-model-line')
    actual = 'pass' if not bad else 'fail'
    return actual == expect, 'files=%d expected=%s actual=%s%s' % (len(arg.split(',')), expect, actual, (' bad=' + ';'.join(bad)) if bad else '')


def main():
    tree, home, work = env_dirs('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py', False)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    return tally(rows, {
        'phrase': lambda rid, expect, arg: run_fm_phrase(tree, expect, arg),
        'frontmatter': lambda rid, expect, arg: run_frontmatter(tree, expect, arg),
    })


if __name__ == '__main__':
    sys.exit(main())
