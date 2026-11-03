#!/usr/bin/env python3
"""K03-C8 rows runner: the step-log check reads the plan statuses; the card lint usage comment names --log.

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (the home every spawned process gets as HOME and USERPROFILE,
with LOOP_HOME at its .loop), LOOP_WORK (a work folder, created when absent; each row writes its fixtures under its own
subfolder), LOOP_PY (the interpreter the tool needs), LOOP_NAMES_FILE (passed through to spawned processes).
Every fixture is written at run time from the row text: a plan fixture and a log fixture, under a made-up goal id.
A check row runs: bash <tree>/bin/loop-journal --check <goal> --file <log fixture> --plan <plan fixture>.
JOURNAL_FILE for every spawned process points at an empty fixture under the work folder.
A phrase row is a Python bytes search of one line of one file of the tree.
Prints PASS or FAIL per row with expected and actual; a sha256 stands in for the output, which can hold a home path.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import env_dirs, journal_file, load_rows, make_env, run_line_phrase, sha, tally, write_text

GOAL = 'ZZZ-98'


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
    write_text(plan, '\n'.join(lines) + '\n')
    write_text(log, logtext.replace('@G', GOAL).replace('\\n', '\n') + '\n')
    cp = subprocess.run(['bash', tree + '/bin/loop-journal', '--check', GOAL, '--file', log, '--plan', plan],
                        capture_output=True, text=True, env=make_env(home, {'JOURNAL_FILE': journal_file(work)}, ('LOOP_GOAL',)), cwd=work)
    out = cp.stdout + cp.stderr
    ok = str(cp.returncode) == want_exit
    names = 'n/a'
    if want_text != '-':
        has = want_text in out
        names = 'yes' if has else 'no'
        ok = ok and has
    return ok, 'expected=exit %s names=%s actual=exit %d names=%s out_sha=%s' % (
        want_exit, want_text, cp.returncode, names, sha(out))


def tool_phrase(tree, expect, arg):
    """K06-C3. The usage comment is in the command file on a tree where the command file is the tool, and in the module
    beside the one launcher text on a tree where it moved: the named file is searched first, then its module."""
    rel, num, phrase = arg.split('|', 2)
    first = run_line_phrase(tree, expect, arg)
    mod = rel.replace('-', '_') + '.py'
    if first[0] or not os.path.isfile(tree + '/' + mod):
        return first
    return run_line_phrase(tree, expect, '%s|%s|%s' % (mod, num, phrase))


def main():
    tree, home, work = env_dirs('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py', False)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    return tally(rows, {
        'check': lambda rid, expect, arg: run_check(tree, work, home, rid, expect, arg),
        'phrase': lambda rid, expect, arg: tool_phrase(tree, expect, arg),
    })


if __name__ == '__main__':
    sys.exit(main())
