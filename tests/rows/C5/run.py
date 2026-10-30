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
import hashlib
import os
import re
import subprocess
import sys

NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder
GOAL = 'FIXT-C5'
STEP = 'T01'
NOTE = 'a home path in the text was rewritten to ~'


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
    stub = tree + '/bin/loop-journal'
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = dict(os.environ)
    env.update({'HOME': home, 'USERPROFILE': home, 'LOOP_HOME': home + '/.loop',
                'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE,
                'PYTHONDONTWRITEBYTECODE': '1'})
    env.pop('LOOP_GOAL', None)
    passed = failed = 0
    for rid, kind, expect, _desc in rows:
        fixture = work + '/' + rid + '.journal'
        with open(fixture, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('')
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
        passed += ok
        failed += (not ok)
        print('%s %s kind=%s exit=%d tail_sha=%s expected_sha=%s note=%s' % (
            'PASS' if ok else 'FAIL', rid, kind, cp.returncode, sha(got) if got is not None else 'none',
            sha(want), 'yes' if NOTE in out else 'no'))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
