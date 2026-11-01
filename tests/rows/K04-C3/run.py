#!/usr/bin/env python3
"""K04-C3 rows runner: the step-log tool's --active mode never labels a stopped run cut, a malformed timestamp on any
line of the goal exits 2, and an unknown leading flag exits 64 with a usage line and appends nothing.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expected results in rows.txt, so a
tree without the change prints FAIL on the rows the change adds), LOOP_ROWS_HOME (the home every spawned process gets as
HOME and USERPROFILE; LOOP_HOME is that home plus /.loop), LOOP_WORK (a work folder, created when absent; each row writes
its fixtures under its own subfolder), LOOP_PY (the interpreter the tool needs), LOOP_NAMES_FILE (passed through).
Every fixture is written at run time from the row text. JOURNAL_FILE is set to a fixture in the work folder for every
spawned process, so nothing reads or appends the live step log. The tool is run as bash <tree>/bin/loop-journal.
Prints PASS or FAIL per row with expected and actual; a sha256 stands in for output text, which can hold a home path.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import env_dirs, load_rows, make_env, sha, tally, write_text

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'


def fixtures(work, rid, logtext):
    folder = '%s/%s' % (work, rid)
    os.makedirs(folder, exist_ok=True)
    log = folder + '/steps.log'
    journal = folder + '/journal-fixture.log'
    write_text(log, logtext.replace('\\n', '\n') + '\n')
    write_text(journal, '')
    return log, journal


def run_active(tree, work, home, rid, expect, arg):
    want_exit, wants = expect.split('|', 1)
    goal, logtext = arg.split('|', 1)
    log, journal = fixtures(work, rid, logtext)
    cp = subprocess.run(['bash', tree + '/bin/loop-journal', '--active', goal, '--file', log],
                        capture_output=True, env=make_env(home, {'JOURNAL_FILE': journal}, ('LOOP_GOAL',)), cwd=work)
    want = ('\n'.join(wants.split(' ;; ')) + '\n').encode('utf-8')
    same = cp.stdout == want
    ok = str(cp.returncode) == want_exit and same
    return ok, 'expected=exit %s bytes=%d actual=exit %d bytes=%d bytes_equal=%s out_sha=%s' % (
        want_exit, len(want), cp.returncode, len(cp.stdout), 'yes' if same else 'no', sha(cp.stdout + cp.stderr))


def check_text(c, out):
    if c == 'nocr':
        return len(out) > 0 and b'\r' not in out
    if c == 'notrace':
        return b'Traceback' not in out
    if c.startswith('has:'):
        return c[4:].encode('utf-8') in out
    return False


def run_active_err(tree, work, home, rid, expect, arg):
    want_exit, checks = expect.split('|', 1)
    goal, logtext = arg.split('|', 1)
    log, journal = fixtures(work, rid, logtext)
    cp = subprocess.run(['bash', tree + '/bin/loop-journal', '--active', goal, '--file', log],
                        capture_output=True, env=make_env(home, {'JOURNAL_FILE': journal}, ('LOOP_GOAL',)), cwd=work)
    out = cp.stdout + cp.stderr
    bad = [c.split(':')[0] for c in checks.split(' ;; ') if not check_text(c, out)]
    ok = str(cp.returncode) == want_exit and not bad
    return ok, 'expected=exit %s checks=%d actual=exit %d failed_checks=%s out_sha=%s' % (
        want_exit, len(checks.split(' ;; ')), cp.returncode, ','.join(bad) or 'none', sha(out))


def run_badflag(tree, work, home, rid, expect, arg):
    want_exit, checks = expect.split('|', 1)
    goal, logtext = arg.split('|', 1)
    log, journal = fixtures(work, rid, logtext)
    # the fixture the tool would append to is the one JOURNAL_FILE names; give it content so a change is a byte count change
    write_text(journal, logtext.replace('\\n', '\n') + '\n')
    before = os.path.getsize(journal)
    cp = subprocess.run(['bash', tree + '/bin/loop-journal', '--bogus-flag', goal, 'T01', 'x'],
                        capture_output=True, env=make_env(home, {'JOURNAL_FILE': journal}, ('LOOP_GOAL',)), cwd=work)
    after = os.path.getsize(journal)
    out = cp.stdout + cp.stderr
    bad = []
    for c in checks.split(' ;; '):
        good = (before == after) if c == 'same' else check_text(c, out)
        if not good:
            bad.append(c.split(':')[0])
    ok = str(cp.returncode) == want_exit and not bad
    return ok, 'expected=exit %s checks=%d actual=exit %d failed_checks=%s fixture_bytes_before=%d after=%d out_sha=%s' % (
        want_exit, len(checks.split(' ;; ')), cp.returncode, ','.join(bad) or 'none', before, after, sha(out))


def main():
    tree, home, work = env_dirs(USAGE)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    return tally(rows, {
        'active': lambda rid, expect, arg: run_active(tree, work, home, rid, expect, arg),
        'active_err': lambda rid, expect, arg: run_active_err(tree, work, home, rid, expect, arg),
        'badflag': lambda rid, expect, arg: run_badflag(tree, work, home, rid, expect, arg),
    })


if __name__ == '__main__':
    sys.exit(main())
