#!/usr/bin/env python3
"""S01-C5 rows runner: the decisions. Six ADRs under docs/adr/ and four out-of-scope notes under docs/out-of-scope/.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same rows in rows.txt, so a tree without
the decision files prints FAIL on every row that needs them), LOOP_ROWS_HOME (the home every child would get, with
LOOP_HOME at that home plus /.loop), LOOP_WORK (a work folder, created when absent), LOOP_PY and LOOP_NAMES_FILE
(accepted, unused here).
The runner writes no fixture and starts no child process. It removes at its start only what its own manifest file
(s01c5-manifest.txt in LOOP_WORK) lists from an earlier run, which is nothing today. Prints PASS or FAIL per row with
expected and actual, an info line with the sha256 of the runner's own two files, then rows=N pass=N fail=N.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import os
import re
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import clean_earlier, env_dirs, info_sha, load_rows, read_lines, row_present, tally

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_PY=<python> LOOP_NAMES_FILE=<file> python run.py (no positional argument)'
MANIFEST = 's01c5-manifest.txt'
HEADINGS = ['Context', 'Decision', 'Deliberately not', 'Consequences', 'Verification']
ROOTS = ('bin/', 'hooks/', 'tests/rows/')


def headings_of(lines):
    """The level-two headings outside fenced blocks, in order."""
    out = []
    inside = False
    for ln in lines:
        if ln.startswith('```'):
            inside = not inside
            continue
        if not inside and ln.startswith('## '):
            out.append(ln[3:].strip())
    return out


def row_headings(ctx, expect, arg):
    bad = []
    for rel in arg.split('|'):
        lines = read_lines(ctx, rel)
        if lines is None:
            bad.append('%s absent' % rel)
        elif headings_of(lines) != HEADINGS:
            bad.append('%s has %d heading(s) not equal to the five' % (rel, len(headings_of(lines))))
    n = len(arg.split('|'))
    return not bad, 'expected=%s actual=%d of %d ok %s' % (expect, n - len(bad), n, ';'.join(bad))


def first_fenced_line(lines):
    """The first line inside the first fenced block after the Verification heading; None when absent."""
    seen = False
    inside = False
    for ln in lines:
        if not seen:
            if ln.strip() == '## Verification':
                seen = True
            continue
        if ln.startswith('## '):
            return None
        if ln.startswith('```'):
            if inside:
                return None
            inside = True
            continue
        if inside:
            return ln
    return None


def row_verifyfile(ctx, expect, arg):
    bad = []
    shown = []
    for rel in arg.split('|'):
        lines = read_lines(ctx, rel)
        if lines is None:
            bad.append('%s absent' % rel)
            continue
        fl = first_fenced_line(lines)
        word = fl.split()[0] if fl and fl.split() else ''
        ok = word.startswith(ROOTS) and os.path.isfile(ctx['tree'] + '/' + word)
        shown.append(word or 'none')
        if not ok:
            bad.append('%s first word %s' % (rel, word or 'none'))
    n = len(arg.split('|'))
    return not bad, 'expected=%s actual=%d of %d ok %s [first words %s]' % (expect, n - len(bad), n, ';'.join(bad), ' '.join(shown))


def row_underlines(ctx, expect, arg):
    bad = []
    counts = []
    for rel in arg.split('|'):
        lines = read_lines(ctx, rel)
        if lines is None:
            bad.append('%s absent' % rel)
            continue
        n = len(lines) - (1 if lines and lines[-1] == '' else 0)
        counts.append(str(n))
        if n >= 15:
            bad.append('%s has %d lines' % (rel, n))
    k = len(arg.split('|'))
    return not bad, 'expected=%s actual=%d of %d ok %s [line counts %s]' % (expect, k - len(bad), k, ';'.join(bad), ' '.join(counts))


def row_datedgoal(ctx, expect, arg):
    date_re = re.compile(r'^Date decided: .*[0-9]{4}-[0-9]{2}')
    goal_re = re.compile(r'^Goal that decided: [A-Za-z]+-[0-9]{2}')
    bad = []
    for rel in arg.split('|'):
        lines = read_lines(ctx, rel)
        if lines is None:
            bad.append('%s absent' % rel)
            continue
        d = len([ln for ln in lines if date_re.match(ln)])
        g = len([ln for ln in lines if goal_re.match(ln)])
        n = len([ln for ln in lines if 'not recorded in the kit' in ln])
        if d != 1 or g != 1 or n:
            bad.append('%s date lines %d goal lines %d unrecorded lines %d' % (rel, d, g, n))
    k = len(arg.split('|'))
    return not bad, 'expected=%s actual=%d of %d ok %s' % (expect, k - len(bad), k, ';'.join(bad))


KINDS = {'present': row_present, 'headings': row_headings, 'verifyfile': row_verifyfile, 'underlines': row_underlines,
         'datedgoal': row_datedgoal}


def main():
    tree, home, work = env_dirs(USAGE)
    clean_earlier(work, MANIFEST, True)
    ctx = {'tree': tree, 'work': work, 'home': home}
    here = os.path.dirname(os.path.abspath(__file__))
    info_sha((('tests/rows/S01-C5/run.py', here + '/run.py'), ('tests/rows/S01-C5/rows.txt', here + '/rows.txt')))
    rows = load_rows(os.path.join(here, 'rows.txt'))
    return tally(rows, KINDS, (ctx,), True, False)


if __name__ == '__main__':
    sys.exit(main())
