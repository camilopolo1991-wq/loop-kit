#!/usr/bin/env python3
"""K03-C5 rows runner: one instrument for active time (step-log tool --active mode, record skill wording).

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (the home every spawned process gets as HOME and USERPROFILE,
with LOOP_HOME at its .loop), LOOP_WORK (a work folder, created when absent; each row writes its fixtures under its own
subfolder), LOOP_PY (the interpreter the tool needs), LOOP_NAMES_FILE (passed through to spawned processes).
Every fixture is written at run time from the row text. JOURNAL_FILE is set to a fixture in the work folder for every
spawned process, so nothing reads or appends the live step log. The tool is run as:
bash <tree>/bin/loop-journal --active <goal> --file <log fixture>.
Active rows compare the tool's stdout bytes to the LF-terminated expected text. Phrase rows search a file in the tree as bytes.
Prints PASS or FAIL per row with expected and actual; a sha256 stands in for the output, which can hold a home path.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import env_dirs, load_rows, make_env, sha, tally, write_text


def run_active(tree, work, home, rid, expect, arg):
    want_exit, wants = expect.split('|', 1)
    goal, logtext = arg.split('|', 1)
    folder = '%s/%s' % (work, rid)
    os.makedirs(folder, exist_ok=True)
    log = folder + '/steps.log'
    journal = folder + '/journal-fixture.log'
    write_text(log, logtext.replace('\\n', '\n') + '\n')
    write_text(journal, '')
    cp = subprocess.run(['bash', tree + '/bin/loop-journal', '--active', goal, '--file', log],
                        capture_output=True, env=make_env(home, {'JOURNAL_FILE': journal}, ('LOOP_GOAL',)), cwd=work)
    want = ('\n'.join(wants.split(' ;; ')) + '\n').encode('utf-8')
    same = cp.stdout == want
    ok = str(cp.returncode) == want_exit and same
    return ok, 'expected=exit %s bytes=%d actual=exit %d bytes=%d bytes_equal=%s out_sha=%s' % (
        want_exit, len(want), cp.returncode, len(cp.stdout), 'yes' if same else 'no', sha(cp.stdout + cp.stderr))


def run_active_err(tree, work, home, rid, expect, arg):
    want_exit, checks = expect.split('|', 1)
    goal, logtext = arg.split('|', 1)
    folder = '%s/%s' % (work, rid)
    os.makedirs(folder, exist_ok=True)
    log = folder + '/steps.log'
    journal = folder + '/journal-fixture.log'
    write_text(log, logtext.replace('\\n', '\n') + '\n')
    write_text(journal, '')
    cp = subprocess.run(['bash', tree + '/bin/loop-journal', '--active', goal, '--file', log],
                        capture_output=True, env=make_env(home, {'JOURNAL_FILE': journal}, ('LOOP_GOAL',)), cwd=work)
    out = cp.stdout + cp.stderr
    bad = []
    for c in checks.split(' ;; '):
        if c == 'nocr':
            good = len(out) > 0 and b'\r' not in out
        elif c == 'notrace':
            good = b'Traceback' not in out
        elif c.startswith('has:'):
            good = c[4:].encode('utf-8') in out
        else:
            good = False
        if not good:
            bad.append(c.split(':')[0])
    ok = str(cp.returncode) == want_exit and not bad
    return ok, 'expected=exit %s checks=%d actual=exit %d failed_checks=%s out_sha=%s' % (
        want_exit, len(checks.split(' ;; ')), cp.returncode, ','.join(bad) or 'none', sha(out))


def run_needle(tree, rid, expect, arg):
    rel, needle = arg.split('|', 1)
    with open(tree + '/' + rel, 'rb') as fh:
        data = fh.read()
    found = data.find(needle.encode('utf-8')) >= 0
    ok = found == (expect == 'present')
    return ok, 'expected=%s actual=%s needle_sha=%s' % (expect, 'present' if found else 'absent', sha(needle))


def main():
    tree, home, work = env_dirs('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py', False)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    return tally(rows, {
        'active': lambda rid, expect, arg: run_active(tree, work, home, rid, expect, arg),
        'active_err': lambda rid, expect, arg: run_active_err(tree, work, home, rid, expect, arg),
        'phrase': lambda rid, expect, arg: run_needle(tree, rid, expect, arg),
    })


if __name__ == '__main__':
    sys.exit(main())
