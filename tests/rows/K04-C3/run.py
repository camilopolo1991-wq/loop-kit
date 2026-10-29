#!/usr/bin/env python3
"""K04-C3 rows runner: the step-log tool's --active mode never labels a stopped run cut, a malformed timestamp on any
line of the goal exits 2, and an unknown leading flag exits 64 with a usage line and appends nothing.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expected results in rows.txt, so a
tree without the change prints FAIL on the rows the change adds), LOOP_ROWS_HOME (the home every spawned process gets as
HOME and USERPROFILE; LOOP_HOME is that home plus /.loop), LOOP_WORK (a work folder, created when absent; each row writes
its fixtures under its own subfolder), LOOP_PY (the interpreter the tool needs), LOOP_NAMES_FILE (passed through).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Every fixture is written at run time from the row text. JOURNAL_FILE is set to a fixture in the work folder for every
spawned process, so nothing reads or appends the live step log. The tool is run as bash <tree>/bin/loop-journal.
Prints PASS or FAIL per row with expected and actual; a sha256 stands in for output text, which can hold a home path.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import hashlib
import os
import subprocess
import sys

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'


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


def make_env(home, journal):
    env = dict(os.environ)
    env['HOME'] = home
    env['USERPROFILE'] = home
    env['LOOP_HOME'] = home + '/.loop'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['JOURNAL_FILE'] = journal
    env.pop('LOOP_GOAL', None)
    return env


def fixtures(work, rid, logtext):
    folder = '%s/%s' % (work, rid)
    os.makedirs(folder, exist_ok=True)
    log = folder + '/steps.log'
    journal = folder + '/journal-fixture.log'
    with open(log, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(logtext.replace('\\n', '\n') + '\n')
    with open(journal, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('')
    return log, journal


def run_active(tree, work, home, rid, expect, arg):
    want_exit, wants = expect.split('|', 1)
    goal, logtext = arg.split('|', 1)
    log, journal = fixtures(work, rid, logtext)
    cp = subprocess.run(['bash', tree + '/bin/loop-journal', '--active', goal, '--file', log],
                        capture_output=True, env=make_env(home, journal), cwd=work)
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
                        capture_output=True, env=make_env(home, journal), cwd=work)
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
    with open(journal, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(logtext.replace('\\n', '\n') + '\n')
    before = os.path.getsize(journal)
    cp = subprocess.run(['bash', tree + '/bin/loop-journal', '--bogus-flag', goal, 'T01', 'x'],
                        capture_output=True, env=make_env(home, journal), cwd=work)
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
    if len(sys.argv) > 1:
        print(USAGE)
        return 64
    tree_e = os.environ.get('LOOP_TREE')
    home_e = os.environ.get('LOOP_ROWS_HOME')
    work_e = os.environ.get('LOOP_WORK')
    if not tree_e or not home_e or not work_e:
        print(USAGE)
        return 64
    tree, home, work = fwd(tree_e), fwd(home_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        if kind == 'active':
            ok, detail = run_active(tree, work, home, rid, expect, arg)
        elif kind == 'active_err':
            ok, detail = run_active_err(tree, work, home, rid, expect, arg)
        elif kind == 'badflag':
            ok, detail = run_badflag(tree, work, home, rid, expect, arg)
        else:
            ok, detail = False, 'unknown kind ' + kind
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
