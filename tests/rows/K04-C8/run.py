#!/usr/bin/env python3
"""K04-C8 rows runner: the reviewer's regressions line; one step-log reader shared by the card lint and the step-log
tool; PASS and DONE matched as whole words.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expectations in rows.txt, so a tree
without the change prints FAIL on the rows the change adds), LOOP_ROWS_HOME (the home every spawned process gets as HOME and
USERPROFILE, with LOOP_HOME at its .loop, except row r3, see below), LOOP_WORK (a work folder, created when absent; each row
writes its fixtures under its own subfolder), LOOP_PY (the interpreter the tools need; default is the interpreter running
this file), LOOP_NAMES_FILE (passed through untouched).
Every spawned process gets PYTHONDONTWRITEBYTECODE=1 and JOURNAL_FILE at an empty fixture under the work folder, so nothing
that appends can reach a real log. Row r3 is the one exception to JOURNAL_FILE and LOOP_HOME: it needs the configuration
to be read, so it gives its processes no JOURNAL_FILE and a LOOP_HOME under its own work subfolder, holding a config.env
that cannot be decoded; HOME and USERPROFILE stay at LOOP_ROWS_HOME, and nothing in the rows home is written.
Fixtures are written at run time from the row text. Kinds: phrase (a bytes search of one line of one file of the tree),
lint (loop-card-lint --log <log> <plan>), lintp (the same with a PASSED status cell), check (loop-journal --check),
checkw (check with T02 owned by a writer and a TODO status cell: the writer-ROLLBACK rule alone),
conf (both tools with an undecodable configuration; the first output line of the two must be equal as bytes), child
(the earlier runners, each run as a child process with its own documented invocation, counts reported).
Prints PASS or FAIL per row with expected and actual; a sha256 stands in for any output, which can hold a home path.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import os
import re
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import env_dirs, fwd, journal_file, load_rows, make_env, run_line_phrase, sha, tally, write_text

GOAL = 'ZZZ-97'
USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] '
         '[LOOP_NAMES_FILE=<file>] python run.py (no positional argument)')


def plan_text(status_cell, owner):
    return ('# Plan %s\n\n## Live\ngoal: %s | status: RUNNING\n\n## Tasks\n'
            '| T | task | owner | status |\n|---|------|-------|--------|\n'
            '| T01 | scout the thing | scout | TODO |\n'
            '| T02 | change the thing | %s | %s |\n' % (GOAL, GOAL, owner, status_cell))


def judge(cp, want_exit, want_text):
    out = cp.stdout + cp.stderr
    ok = str(cp.returncode) == want_exit
    names = 'n/a'
    if want_text != '-':
        has = want_text in out
        names = 'yes' if has else 'no'
        ok = ok and has
    return ok, 'expected=exit %s names=%s actual=exit %d names=%s out_sha=%s' % (
        want_exit, want_text, cp.returncode, names, sha(out))


def run_lint(tree, work, home, rid, expect, arg, status_word):
    want_exit, want_text = expect.split('|', 1)
    evpath, logtext = arg.split('|', 1)
    folder = '%s/%s' % (work, rid)
    os.makedirs(folder, exist_ok=True)
    plan, log = folder + '/plan.md', folder + '/steps.log'
    write_text(plan, plan_text('%s %s' % (status_word, evpath), 'writer'))
    write_text(log, logtext.replace('\\n', '\n') + '\n')
    cp = subprocess.run(['bash', tree + '/bin/loop-card-lint', '--log', log, plan],
                        capture_output=True, text=True, env=make_env(home, {'JOURNAL_FILE': journal_file(work)}, ('LOOP_GOAL',)), cwd=work)
    return judge(cp, want_exit, want_text)


def run_check(tree, work, home, rid, expect, arg, status_cell='PASS', owner='scout'):
    want_exit, want_text = expect.split('|', 1)
    folder = '%s/%s' % (work, rid)
    os.makedirs(folder, exist_ok=True)
    plan, log = folder + '/plan.md', folder + '/steps.log'
    write_text(plan, plan_text(status_cell, owner))
    write_text(log, arg.replace('\\n', '\n') + '\n')
    cp = subprocess.run(['bash', tree + '/bin/loop-journal', '--check', GOAL, '--file', log, '--plan', plan],
                        capture_output=True, text=True, env=make_env(home, {'JOURNAL_FILE': journal_file(work)}, ('LOOP_GOAL',)), cwd=work)
    return judge(cp, want_exit, want_text)


def run_conf(tree, work, home, rid, expect):
    want_exit, want_text = expect.split('|', 1)
    folder = '%s/%s' % (work, rid)
    lh = folder + '/lh'
    os.makedirs(lh, exist_ok=True)
    with open(lh + '/config.env', 'wb') as fh:
        fh.write(b'JOURNAL_FILE=\xff\xfe\n')
    plan = folder + '/plan.md'
    write_text(plan, plan_text('PASS evidence/T02/review', 'scout'))
    env = make_env(home, {'LOOP_HOME': lh}, ('LOOP_GOAL', 'JOURNAL_FILE'))
    a = subprocess.run(['bash', tree + '/bin/loop-card-lint', plan], capture_output=True, env=env, cwd=work)
    b = subprocess.run(['bash', tree + '/bin/loop-journal', '--check', GOAL, '--plan', plan],
                       capture_output=True, env=env, cwd=work)
    fa = a.stdout.split(b'\n')[0]
    fb = b.stdout.split(b'\n')[0]
    same = fa == fb
    shaped = fa.startswith(want_text.encode('utf-8'))
    ok = same and shaped and str(a.returncode) == want_exit and str(b.returncode) == want_exit
    return ok, 'expected=exit %s both, first lines equal as bytes, starting with the shared wording; actual=exit %d and %d equal=%s shared_wording=%s lint_line_sha=%s journal_line_sha=%s' % (
        want_exit, a.returncode, b.returncode, 'yes' if same else 'no', 'yes' if shaped else 'no', sha(fa), sha(fb))


def run_child(tree, work, home, py, rid, expect, arg):
    ok_all = True
    parts = []
    for folder in arg.split(','):
        sub = '%s/%s-%s' % (work, rid, folder)
        os.makedirs(sub, exist_ok=True)
        env = make_env(home, {'JOURNAL_FILE': journal_file(work)}, ('LOOP_GOAL',))
        env['LOOP_TREE'] = tree
        env['LOOP_ROWS_HOME'] = home
        env['LOOP_WORK'] = sub
        cp = subprocess.run([py, tree + '/tests/rows/' + folder + '/run.py'], capture_output=True, text=True,
                            env=env, cwd=work)
        last = [l for l in (cp.stdout + cp.stderr).splitlines() if l.startswith('rows=')]
        counts = last[-1] if last else 'rows=? pass=? fail=?'
        good = str(cp.returncode) == expect and bool(last) and re.search(r'fail=0$', counts) is not None
        ok_all = ok_all and good
        parts.append('%s exit=%d %s' % (folder, cp.returncode, counts))
    return ok_all, 'expected=exit %s fail=0 each; actual: %s' % (expect, '; '.join(parts))


def main():
    tree, home, work = env_dirs(USAGE)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    return tally(rows, {
        'phrase': lambda rid, expect, arg: run_line_phrase(tree, expect, arg),
        'lint': lambda rid, expect, arg: run_lint(tree, work, home, rid, expect, arg, 'PASS'),
        'lintp': lambda rid, expect, arg: run_lint(tree, work, home, rid, expect, arg, 'PASSED'),
        'check': lambda rid, expect, arg: run_check(tree, work, home, rid, expect, arg),
        'checkw': lambda rid, expect, arg: run_check(tree, work, home, rid, expect, arg, 'TODO', 'writer'),
        'conf': lambda rid, expect, arg: run_conf(tree, work, home, rid, expect),
        'child': lambda rid, expect, arg: run_child(tree, work, home, py, rid, expect, arg),
    })


if __name__ == '__main__':
    sys.exit(main())
