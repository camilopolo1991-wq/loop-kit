#!/usr/bin/env python3
"""C3 rows runner: loop_scan.py counts a masked home path as a hit of category path.

Usage: run.py <tree> <home> <work>

Runs <tree>/bin/loop_scan.py by path with the interpreter running this file, on fixture files
written under <work> at run time. HOME, USERPROFILE and LOOP_HOME point into <home>. The masked
lines are built here from <home>; no home path is written in the row text. Prints PASS or FAIL
per row with a sha256 prefix of the actual output text (never the text), then a count, and exits
1 on any FAIL. Nothing is spawned in the background and nothing is killed.
"""
import os
import re
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import Score, dirs_or_args, fwd, load_rows, make_env, sha, write_text

NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder


def fixture_line(kind, home):
    parent = fwd(home).rpartition('/')[0]
    drive, rest = parent[0], parent[2:]
    if kind == 'drive':
        return 'path ' + drive + ':' + rest + '/' + '[NAME]' + '/notes.txt\n'
    if kind == 'cform':
        return 'path /' + drive.lower() + rest + '/' + '[NAME]' + '/notes.txt\n'
    return 'a clean line with nothing to mask\n'


def main():
    tree, home, work = dirs_or_args()
    os.makedirs(work, exist_ok=True)
    scan = tree + '/bin/loop_scan.py'
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = make_env(home, {'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE},
                   ('LOOP_GOAL',))
    score = Score()
    for rid, kind, expect, _desc in rows:
        fx = work + '/' + rid + '.txt'
        write_text(fx, fixture_line(kind, home))
        cp = subprocess.run([sys.executable, scan, fx], capture_output=True, text=True, env=env, cwd=work)
        out = cp.stdout + cp.stderr
        hm = re.search(r'\bhits=(\d+)', out)
        pm = re.search(r'\bpath=(\d+)', out)
        hitn = int(hm.group(1)) if hm else -1
        pathn = int(pm.group(1)) if pm else 0
        fired = 'control=fired' in out
        at1 = ('hit at ' + fx + ':1') in out.replace('\\', '/')
        if expect == 'hit1':
            ok = cp.returncode == 1 and fired and hitn == 1 and pathn == 1 and at1
        elif expect == 'clean':
            ok = cp.returncode == 0 and fired and hitn == 0 and pathn == 0
        else:
            # ctrl: the normal run above must say control=fired; then the judged run makes the
            # masked control line unbuildable (home = a drive root, no user segment to mask) and
            # the scanner must fail closed with the control-failure exit 3.
            normal_ok = cp.returncode == 0 and fired
            renv = dict(env)
            root = work[:3] if work[1:3] == ':/' else '/'
            renv.update({'HOME': root, 'USERPROFILE': root})
            cp = subprocess.run([sys.executable, scan, fx], capture_output=True, text=True, env=renv, cwd=work)
            out = cp.stdout + cp.stderr
            hm = re.search(r'\bhits=(\d+)', out)
            hitn = int(hm.group(1)) if hm else -1
            pathn = 0
            fired = 'control=fired' in out
            ok = normal_ok and cp.returncode == 3 and 'PATH CONTROL DID NOT FIRE' in out and not fired
        score.row(ok, rid, 'expected=%s rc=%d hits=%d path=%d control_fired=%s out_sha=%s' % (expect, cp.returncode, hitn, pathn, fired, sha(out)))
    return score.done(rows)


if __name__ == '__main__':
    sys.exit(main())
