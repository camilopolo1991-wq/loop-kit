#!/usr/bin/env python3
"""K11-C9 rows runner: loop-scan with no argument, run from a folder outside any git repository, exits 2 and prints one line naming the cause.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test (its bin/loop_scan.py is what runs)
  LOOP_ROWS_HOME   the folder under which the throwaway folders of this runner are made
  LOOP_WORK        the work folder; the runner's manifest k11c9-manifest.txt lists what it made, and the next run removes only that
  LOOP_PY          the interpreter every child is run with (defaults to the one running this file)

Fixture. One throwaway base folder under LOOP_ROWS_HOME holds a home (HOME, USERPROFILE and LOOP_HOME at its own folders, the config
naming a throwaway record repository as ENGINE_RECORD_DIR, the shape the live config has), that record repository (made here by git init,
the one version-control command of this runner, in a repository this file creates), a folder "outside" that is not inside any
repository, and a second throwaway repository "inside". GIT_CEILING_DIRECTORIES is the base folder, so git never looks above the base
for a repository: the folder "outside" is outside any repository whatever sits above LOOP_ROWS_HOME. No real repository is touched.

The reason the config names a record repository: a tree before the change reads it as the fallback and scans it, exit 0; with no
config the old code also exits 2 and the row could not tell the trees apart.
"""
import os
import re
import subprocess
import sys
import time

ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import Score, clean_earlier, env_dirs, fwd, load_rows, make_env, register, sha, write_text  # noqa: E402

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py (no positional argument)')
MANIFEST = 'k11c9-manifest.txt'
DROP = ('LOOP_GOAL', 'HERMES_HOME', 'JOURNAL_FILE', 'LOOP_GUARD_MODE', 'LOOP_PY', 'ENGINE_RECORD_DIR', 'RECORD_BRANCH', 'KIT_DIR',
        'LOOP_RECORD_WT', 'LOOP_KIT_WT', 'LOOP_NAMES_FILE')
GITENV = {'GIT_AUTHOR_NAME': 'Omicron Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid', 'GIT_COMMITTER_NAME': 'Omicron Fixture',
          'GIT_COMMITTER_EMAIL': 'fixture@example.invalid', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_TERMINAL_PROMPT': '0'}
ST = {}


def world(rows_home, work):
    if 'w' in ST:
        return ST['w']
    base = '%s/k11c9-%d' % (rows_home, time.time_ns())
    os.makedirs(base)
    register(work, MANIFEST, base)
    w = {'base': base, 'home': base + '/home', 'rec': base + '/record', 'outside': base + '/outside', 'inside': base + '/inside'}
    os.makedirs(w['home'] + '/.loop')
    os.makedirs(w['outside'])
    env = make_env(w['home'], dict(GITENV, GIT_CEILING_DIRECTORIES=base), DROP)
    w['env'] = env
    write_text(w['home'] + '/.loop/config.env', 'ENGINE_RECORD_DIR=%s\nRECORD_BRANCH=record\n' % w['rec'])
    for repo in (w['rec'], w['inside']):
        os.makedirs(repo)
        cp = subprocess.run(['git', 'init', '-q', '-b', 'record'], cwd=repo, env=env, capture_output=True, stdin=subprocess.DEVNULL)
        assert cp.returncode == 0, cp.stderr.decode('utf-8', 'replace')[:80]
    ST['w'] = w
    return w


def bare_call(w, py, tree, cwd):
    cp = subprocess.run([py, tree + '/bin/loop_scan.py'], cwd=cwd, env=w['env'], capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
    out = (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '')
    return cp.returncode, [x for x in out.split('\n') if x.strip()]


def row_outside(w, py, tree, expect, arg):
    rc, lines = bare_call(w, py, tree, w['outside'])
    one = lines[0] if len(lines) == 1 else ''
    ok = rc == int(expect) and len(lines) == 1 and 'outside any git repository' in one
    return ok, 'expected=exit %s and one line naming the cause actual=exit %d, %d line(s), cause named %s, first_line_sha=%s' % (
        expect, rc, len(lines), 'outside any git repository' in one, sha(lines[0] if lines else ''))


def row_inside(w, py, tree, expect, arg):
    rc, lines = bare_call(w, py, tree, w['inside'])
    summary = [x for x in lines if x.startswith('loop-scan: control=fired')]
    hits0 = bool(summary) and re.search(r'\bhits=0\b', summary[0]) is not None
    ok = rc == int(expect) and len(summary) == 1 and hits0
    return ok, 'expected=exit %s and a scan summary with hits=0 actual=exit %d, %d line(s), summary lines %d, hits=0 %s' % (
        expect, rc, len(lines), len(summary), hits0)


KINDS = {'outside': row_outside, 'inside': row_inside}


def main():
    tree, home, work = env_dirs(USAGE)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    clean_earlier(work, MANIFEST, say=True)
    rows = load_rows(os.path.join(HERE, 'rows.txt'))
    w = world(home, work)
    score = Score()
    for rid, kind, expect, arg in rows:
        fn = KINDS.get(kind)
        if fn is None:
            score.row(False, rid, 'unknown kind ' + kind)
            continue
        try:
            ok, detail = fn(w, py, tree, expect, arg)
        except Exception as exc:
            ok, detail = False, 'expected=row runs actual=error %s' % type(exc).__name__
        score.row(ok, rid, detail)
    return score.done(rows)


if __name__ == '__main__':
    sys.exit(main())
