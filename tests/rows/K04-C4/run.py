#!/usr/bin/env python3
"""K04-C4 rows runner: the user folder is a name. r1 and r2 are phrase rows (a bytes search in the tree's
preamble and audit skill); r3 builds a fixture repository inside a fake home and runs the tree's loop_scan.py
in its range form from inside it.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expected verdicts, so a tree
without the change prints FAIL), LOOP_ROWS_HOME (the home every spawned process gets as HOME and USERPROFILE;
LOOP_HOME is that home plus /.loop; r3 swaps in a fake home under LOOP_WORK), LOOP_WORK (a work folder, created
when absent), LOOP_PY (interpreter for the scan; default is the one running this file), LOOP_NAMES_FILE (passed
through untouched).
Every spawned process gets HOME and USERPROFILE set, LOOP_HOME under that home and PYTHONDONTWRITEBYTECODE=1.
The scan output can hold a home path, so r3 prints booleans and a sha256 in place of the line. Nothing is spawned
in the background, nothing is killed, no timeout is set.
"""
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import Score, env_dirs, fwd, load_rows, make_env, sha


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
    env = make_env(fake, drop=('JOURNAL_FILE',))
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
    tree, home, work = env_dirs(usage)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    score = Score()
    for rid, kind, rel, phrase in rows:
        if kind == 'phrase':
            expect = 'found'
            actual, why = phrase_row(tree, rel, phrase)
        else:
            expect = 'tilde'
            actual, why = range_row(tree, work, py)
        ok = actual == expect
        score.row(ok, rid, 'expected=%s actual=%s sha=%s' % (expect, actual, why))
    return score.done(rows)


if __name__ == '__main__':
    sys.exit(main())
