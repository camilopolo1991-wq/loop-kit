#!/usr/bin/env python3
"""C3 rows runner: loop_scan.py counts a masked home path as a hit of category path.

Usage: run.py <tree> <home> <work>

Runs <tree>/bin/loop_scan.py by path with the interpreter running this file, on fixture files
written under <work> at run time. HOME, USERPROFILE and LOOP_HOME point into <home>. The masked
lines are built here from <home>; no home path is written in the row text. Prints PASS or FAIL
per row with a sha256 prefix of the actual output text (never the text), then a count, and exits
1 on any FAIL. Nothing is spawned in the background and nothing is killed.
"""
import hashlib
import os
import re
import subprocess
import sys

NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder


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


def fixture_line(kind, home):
    parent = fwd(home).rpartition('/')[0]
    drive, rest = parent[0], parent[2:]
    if kind == 'drive':
        return 'path ' + drive + ':' + rest + '/' + '[NAME]' + '/notes.txt\n'
    if kind == 'cform':
        return 'path /' + drive.lower() + rest + '/' + '[NAME]' + '/notes.txt\n'
    return 'a clean line with nothing to mask\n'


def main():
    if len(sys.argv) != 4:
        print('usage: run.py <tree> <home> <work>')
        return 2
    tree, home, work = fwd(sys.argv[1]), fwd(sys.argv[2]), fwd(sys.argv[3])
    os.makedirs(work, exist_ok=True)
    scan = tree + '/bin/loop_scan.py'
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = dict(os.environ)
    env.update({'HOME': home, 'USERPROFILE': home, 'LOOP_HOME': home + '/.loop',
                'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE,
                'PYTHONDONTWRITEBYTECODE': '1'})
    env.pop('LOOP_GOAL', None)
    passed = failed = 0
    for rid, kind, expect, _desc in rows:
        fx = work + '/' + rid + '.txt'
        with open(fx, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(fixture_line(kind, home))
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
        passed += ok
        failed += (not ok)
        print('%s %s expected=%s rc=%d hits=%d path=%d control_fired=%s out_sha=%s' % (
            'PASS' if ok else 'FAIL', rid, expect, cp.returncode, hitn, pathn, fired, sha(out)))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
