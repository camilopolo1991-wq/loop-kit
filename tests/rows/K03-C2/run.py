#!/usr/bin/env python3
"""K03-C2 rows runner: the card lint checks plan PASS cells against the step log.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (the home every spawned process gets as HOME and USERPROFILE,
with LOOP_HOME at its .loop), LOOP_WORK (a work folder, created when absent; each row writes its fixtures under its own
subfolder), LOOP_PY (the interpreter the lint needs), LOOP_NAMES_FILE (passed through to spawned processes).
Exits 64 with a usage line when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Every fixture is written at run time from the row text: a plan fixture under the basename the plan lint judges, and a log
fixture. The lint is run as: bash <tree>/bin/loop-card-lint --log <log fixture> <plan fixture>.
Prints PASS or FAIL per row with expected and actual; a sha256 stands in for the output, which can hold a home path.
Nothing is spawned in the background, nothing is killed, no timeout is set.
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
    env.pop('LOOP_GOAL', None)
    env.pop('JOURNAL_FILE', None)
    return env


PLAN = (
    '# Plan ZZZ-99\n'
    '\n'
    '## Live\n'
    'goal: ZZZ-99 | status: RUNNING\n'
    '\n'
    '## Tasks\n'
    '| T | task | owner | status |\n'
    '|---|------|-------|--------|\n'
    '| T01 | scout the thing | scout | TODO |\n'
    '| T02 | change the thing | writer | PASS %s |\n'
)


def run_lint(tree, work, home, rid, expect, arg):
    want_exit, want_text = expect.split('|', 1)
    evpath, logtext = arg.split('|', 1)
    folder = '%s/%s' % (work, rid)
    os.makedirs(folder, exist_ok=True)
    plan = folder + '/plan.md'
    log = folder + '/steps.log'
    with open(plan, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(PLAN % evpath)
    with open(log, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(logtext.replace('\\n', '\n') + '\n')
    cp = subprocess.run(['bash', tree + '/bin/loop-card-lint', '--log', log, plan],
                        capture_output=True, text=True, env=make_env(home), cwd=work)
    out = cp.stdout + cp.stderr
    ok = str(cp.returncode) == want_exit
    names = 'n/a'
    if want_text != '-':
        has = want_text in out
        names = 'yes' if has else 'no'
        ok = ok and has
    return ok, 'expected=exit %s names=%s actual=exit %d names=%s out_sha=%s' % (
        want_exit, want_text, cp.returncode, names, sha(out))


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
        if kind == 'lint':
            ok, detail = run_lint(tree, work, home, rid, expect, arg)
        else:
            ok, detail = False, 'unknown kind ' + kind
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
