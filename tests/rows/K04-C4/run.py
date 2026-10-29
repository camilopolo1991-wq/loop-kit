#!/usr/bin/env python3
"""K04-C4 rows runner: the user folder is a name. r1 and r2 are phrase rows (a bytes search in the tree's
preamble and audit skill); r3 builds a fixture repository inside a fake home and runs the tree's loop_scan.py
in its range form from inside it.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expected verdicts, so a tree
without the change prints FAIL), LOOP_ROWS_HOME (the home every spawned process gets as HOME and USERPROFILE;
LOOP_HOME is that home plus /.loop; r3 swaps in a fake home under LOOP_WORK), LOOP_WORK (a work folder, created
when absent), LOOP_PY (interpreter for the scan; default is the one running this file), LOOP_NAMES_FILE (passed
through untouched).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Every spawned process gets HOME and USERPROFILE set, LOOP_HOME under that home and PYTHONDONTWRITEBYTECODE=1.
The scan output can hold a home path, so r3 prints booleans and a sha256 in place of the line. Nothing is spawned
in the background, nothing is killed, no timeout is set.
"""
import hashlib
import os
import subprocess
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


def phrase_row(tree, rel, phrase):
    with open(tree + '/' + rel, 'rb') as fh:
        data = fh.read()
    found = phrase.encode('utf-8') in data
    return ('found' if found else 'absent'), sha(phrase)


def git(env, cwd, *args):
    return subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                           '-c', 'core.autocrlf=false'] + list(args),
                          cwd=cwd, env=env, capture_output=True, text=True)


def range_row(tree, work, py):
    fake = work + '/fh-%d' % os.getpid()
    repo = fake + '/fixrepo'
    os.makedirs(repo, exist_ok=True)
    env = make_env(fake)
    if git(env, repo, 'init', '-q').returncode != 0:
        return 'error', 'git-init'
    for n in (1, 2):
        with open(repo + '/note.txt', 'a', encoding='utf-8') as fh:
            fh.write('harmless line %d\n' % n)
        if git(env, repo, 'add', 'note.txt').returncode != 0:
            return 'error', 'git-add'
        if git(env, repo, 'commit', '-q', '-m', 'c%d' % n).returncode != 0:
            return 'error', 'git-commit'
    cp = subprocess.run([py, tree + '/bin/loop_scan.py', '--range', 'HEAD~1..HEAD'],
                        cwd=repo, env=env, capture_output=True, text=True)
    lines = [l for l in cp.stdout.splitlines() if ' repo=' in l]
    if not lines:
        return 'error', sha(cp.stdout + cp.stderr)
    line = lines[0]
    tilde = ' repo=~/' in line
    literal = fake.lower() in line.replace('\\', '/').lower()
    return ('tilde' if tilde and not literal else 'literal' if literal else 'other'), sha(line)


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
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, kind, rel, phrase in rows:
        if kind == 'phrase':
            expect = 'found'
            actual, why = phrase_row(tree, rel, phrase)
        else:
            expect = 'tilde'
            actual, why = range_row(tree, work, py)
        ok = actual == expect
        passed += ok
        failed += (not ok)
        print('%s %s expected=%s actual=%s sha=%s' % ('PASS' if ok else 'FAIL', rid, expect, actual, why))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
