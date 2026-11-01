#!/usr/bin/env python3
"""C5 rows runner: loop-journal append mode rewrites the home directory, in any spelling, to ~.

Usage: run.py <tree> <home> <work>

Runs "bash <tree>/bin/loop-journal <goal> <step> <text>" with JOURNAL_FILE pointing at a fixture under
<work>. HOME, USERPROFILE and LOOP_HOME point into <home>. The home spellings are built from <home> at
run time; no home path is written in the row text. Each row appends one line, then compares the text
after the fourth whitespace-separated field (the dash is the first) with the expected tail, by sha256.
Prints PASS or FAIL per row with the two sha256 prefixes (never the line), then a count, and exits 1 on
any FAIL. Nothing is spawned in the background and nothing is killed.
"""
import os
import re
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import Score, dirs_or_args, fwd, load_rows, make_env, sha, write_text

NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder
GOAL = 'FIXT-C5'
STEP = 'T01'
NOTE = 'a home path in the text was rewritten to ~'


def spelling(kind, home):
    drive, rest = home[0], home[2:]  # home is "X:/..." after fwd()
    if kind == 'drive_slash':
        return home
    if kind == 'drive_back':
        return home.replace('/', '\\')
    if kind == 'msys':
        return '/' + drive.lower() + rest
    if kind == 'bak':
        return home + '.bak'
    if kind.startswith('masked'):
        segs = home.split('/')
        idx = next((i for i, s in enumerate(segs[:-1]) if s.lower() == 'users'), None)
        if idx is None:
            raise SystemExit('home has no Users/ component: no masked form to build')
        segs[idx + 1] = '[NAME]'
        masked = '/'.join(segs)
        if kind == 'masked_back':
            return masked.replace('/', '\\')
        if kind == 'masked_msys':
            return '/' + drive.lower() + masked[2:]
        return masked
    return None


def tail_of(line):
    m = re.match(r'^\S+\s+\S+\s+\S+\s+\S+\s(.*)$', line.rstrip('\n'), re.S)
    return m.group(1) if m else None


def main():
    tree, home, work = dirs_or_args()
    os.makedirs(work, exist_ok=True)
    stub = tree + '/bin/loop-journal'
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = make_env(home, {'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE},
                   ('LOOP_GOAL',))
    score = Score()
    for rid, kind, expect, _desc in rows:
        fixture = work + '/' + rid + '.journal'
        write_text(fixture, '')
        env['JOURNAL_FILE'] = fixture
        sp = spelling(kind, home)
        if sp is None:
            text = 'plain note with no path, only words and 12345'
            want = text
        else:
            text = 'saw ' + sp + '/.loop/x.txt then done'
            want = text if expect == 'equal' else 'saw ~/.loop/x.txt then done'
        cp = subprocess.run(['bash', stub, GOAL, STEP, text], capture_output=True, text=True, env=env, cwd=work)
        with open(fixture, encoding='utf-8', errors='replace', newline='') as fh:
            lines = fh.read().splitlines()
        got = tail_of(lines[0]) if len(lines) == 1 else None
        out = cp.stdout + cp.stderr
        note_ok = (NOTE in out) if expect == 'rewritten' else (NOTE not in out)
        ok = (cp.returncode == 0 and got is not None and sha(got) == sha(want) and got == want
              and note_ok and 'journaled: ' + GOAL + ' ' + STEP in out)
        score.row(ok, rid, 'kind=%s exit=%d tail_sha=%s expected_sha=%s note=%s' % (kind, cp.returncode, sha(got) if got is not None else 'none',
            sha(want), 'yes' if NOTE in out else 'no'))
    return score.done(rows)


if __name__ == '__main__':
    sys.exit(main())
