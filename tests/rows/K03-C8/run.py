#!/usr/bin/env python3
"""K03-C8 rows runner: the step-log check reads the plan statuses; the card lint usage comment names --log.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (the home every spawned process gets as HOME and USERPROFILE,
with LOOP_HOME at its .loop), LOOP_WORK (a work folder, created when absent; each row writes its fixtures under its own
subfolder), LOOP_PY (the interpreter the tool needs), LOOP_NAMES_FILE (passed through to spawned processes).
Exits 64 with a usage line when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Every fixture is written at run time from the row text: a plan fixture and a log fixture, under a made-up goal id.
A check row runs: bash <tree>/bin/loop-journal --check <goal> --file <log fixture> --plan <plan fixture>.
JOURNAL_FILE for every spawned process points at an empty fixture under the work folder.
A phrase row is a Python bytes search of one line of one file of the tree.
Prints PASS or FAIL per row with expected and actual; a sha256 stands in for the output, which can hold a home path.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import hashlib
import os
import subprocess
import sys

GOAL = 'ZZZ-98'


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


def make_env(home, work):
    env = dict(os.environ)
    env['HOME'] = home
    env['USERPROFILE'] = home
    env['LOOP_HOME'] = home + '/.loop'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env.pop('LOOP_GOAL', None)
    jf = work + '/journal-fixture.log'
    with open(jf, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('')
    env['JOURNAL_FILE'] = jf
    return env


def run_check(tree, work, home, rid, expect, arg):
    want_exit, want_text = expect.split('|', 1)
    tasks, logtext = arg.split('|', 1)
    folder = '%s/%s' % (work, rid)
    os.makedirs(folder, exist_ok=True)
    plan = folder + '/plan.md'
    log = folder + '/steps.log'
    lines = ['# Plan ' + GOAL, '', '## Live', 'goal: %s | status: RUNNING' % GOAL, '', '## Tasks',
             '| T | task | owner | status |', '|---|------|-------|--------|']
    for t in tasks.split(','):
        tid, owner, status = t.split('/', 2)
        lines.append('| %s | a task | %s | %s |' % (tid, owner, status))
    with open(plan, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    with open(log, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(logtext.replace('@G', GOAL).replace('\\n', '\n') + '\n')
    cp = subprocess.run(['bash', tree + '/bin/loop-journal', '--check', GOAL, '--file', log, '--plan', plan],
                        capture_output=True, text=True, env=make_env(home, work), cwd=work)
    out = cp.stdout + cp.stderr
    ok = str(cp.returncode) == want_exit
    names = 'n/a'
    if want_text != '-':
        has = want_text in out
        names = 'yes' if has else 'no'
        ok = ok and has
    return ok, 'expected=exit %s names=%s actual=exit %d names=%s out_sha=%s' % (
        want_exit, want_text, cp.returncode, names, sha(out))


def run_phrase(tree, rid, expect, arg):
    rel, num, phrase = arg.split('|', 2)
    with open(tree + '/' + rel, 'rb') as fh:
        data = fh.read()
    line = data.split(b'\n')[int(num) - 1]
    found = phrase.encode('utf-8') in line
    return found == (expect == 'found'), 'expected=%s actual=%s file=%s line=%s' % (
        expect, 'found' if found else 'absent', rel, num)


def main():
    tree_e = os.environ.get('LOOP_TREE')
    home_e = os.environ.get('LOOP_ROWS_HOME')
    work_e = os.environ.get('LOOP_WORK')
    if not tree_e or not home_e or not work_e:
        print('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py')
        return 64
    tree, home, work = fwd(tree_e), fwd(home_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        if kind == 'check':
            ok, detail = run_check(tree, work, home, rid, expect, arg)
        elif kind == 'phrase':
            ok, detail = run_phrase(tree, rid, expect, arg)
        else:
            ok, detail = False, 'unknown kind ' + kind
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
