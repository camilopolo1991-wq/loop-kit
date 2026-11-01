#!/usr/bin/env python3
"""K05-C3 rows runner: the leader text carries the layout's statements on DISPATCH lines, commit message files and PASS
lines, and the step-log tool's --check fails a scout's or reviewer's DISPATCH line that lies outside a tripwire window and a
task PASS line that names no evidence path.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expectations in rows.txt, so a tree
without the change prints FAIL on the rows it adds), LOOP_ROWS_HOME (the home every spawned process gets as HOME and
USERPROFILE; LOOP_HOME is that home plus /.loop), LOOP_WORK (a work folder, created when absent), LOOP_PY (the
interpreter the tool needs), LOOP_NAMES_FILE (passed through untouched).
Every fixture (a plan, a step log, an empty journal file) is written under LOOP_WORK at run time from the row text.
JOURNAL_FILE is set to the fixture journal and LOOP_GOAL to a fixture goal id for every spawned process, so nothing reads
or appends the live step log. The tool is run as bash <tree>/bin/loop-journal --check. At its start the runner removes only
what its own manifest file (k05c3-manifest.txt in LOOP_WORK) lists from an earlier run. Prints PASS or FAIL per row with
expected and actual; a sha256 stands in for any text that could hold a home path. Nothing is spawned in the background,
nothing is killed, no timeout is set.
"""
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import SEP, clean_earlier, env_dirs, fwd, load_rows, make_env, register, row_phrases, sha, tally, write_text

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'
MANIFEST = 'k05c3-manifest.txt'
GOAL = 'K05-FIX'
LSEP = ' @@ '


def row_log(ctx, rid, expect, arg):
    want_exit, checks = expect.split('|', 1)
    goal, body = arg.split('|', 1)
    folder = '%s/%s' % (ctx['work'], rid)
    os.makedirs(folder, exist_ok=True)
    register(ctx['work'], MANIFEST, folder)
    plan = folder + '/plan.md'
    log = folder + '/steps.log'
    journal = folder + '/journal-fixture.log'
    write_text(plan, '| id | what | owner | status |\n|---|---|---|---|\n| T01 | fixture change | scout | open |\n')
    with open(log, 'w', encoding='utf-8', newline='\n') as fh:
        for ln in body.split(LSEP):
            ts, rest = ln.split(' ', 1)
            fh.write('- %s %s %s\n' % (ts, goal, rest))
    write_text(journal, '')
    cp = subprocess.run(['bash', ctx['tree'] + '/bin/loop-journal', '--check', goal, '--file', log, '--plan', plan],
                        capture_output=True, env=make_env(ctx['home'], {'JOURNAL_FILE': journal, 'LOOP_GOAL': GOAL, 'LOOP_PY': ctx['py']}), cwd=ctx['work'])
    out = (cp.stdout + cp.stderr).decode('utf-8', 'replace').replace('\r', '')
    bad = []
    for c in checks.split(SEP):
        if c == 'nofail':
            good = 'FAIL' not in out
        elif c.startswith('has:'):
            good = c[4:] in out
        else:
            good = False
        if not good:
            bad.append(c.split(':')[0])
    ok = str(cp.returncode) == want_exit and not bad
    return ok, 'expected=exit %s checks=%d actual=exit %d failed_checks=%s out_sha=%s' % (
        want_exit, len(checks.split(SEP)), cp.returncode, ','.join(bad) or 'none', sha(out))


KINDS = {'phrase': row_phrases, 'log': row_log}


def main():
    tree, home, work = env_dirs(USAGE)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    clean_earlier(work, MANIFEST, True)
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': py}
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    return tally(rows, KINDS, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
