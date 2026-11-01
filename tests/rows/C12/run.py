#!/usr/bin/env python3
"""C12 rows runner: the four carried tripwire and preflight files, the tripwire selftest, the preflight writable line, the README phrase.

Usage: run.py <tree> <home> <work>

filehash rows: sha256 of a file under <tree> against the carried hash held in the row text.
selftest row: "<tree>/bin/loop_tripwire.py selftest" run by this interpreter; a stub loop-sql is written into a shim
folder under <work> and put first on PATH for this row only; the row passes when the output holds each named case (exit code and WinError 2 count are information only).
preflight row: "bash <tree>/bin/loop-preflight" with LOOP_HOME at <home>/.loop; one output line must start with the word.
phrase row: a Python bytes search under <tree> for the phrase in the named file.
HOME, USERPROFILE and LOOP_HOME point into <home>. Prints PASS or FAIL per row with expected and actual (a sha256
stands in for any text that could hold a home path), then a count, and exits 1 on any FAIL. Nothing is spawned
in the background and nothing is killed.
"""
import hashlib
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import dirs_or_args, fwd, load_rows, make_env, run_phrase, sha, tally, write_text

NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder


def run_filehash(tree, expect, rel):
    try:
        with open(tree + '/' + rel, 'rb') as fh:
            data = fh.read()
    except OSError:
        return False, 'expected=%s actual=unreadable' % expect
    actual = hashlib.sha256(data).hexdigest()
    return actual == expect, 'expected=%s actual=%s' % (expect, actual)


def run_selftest(tree, work, env, expect, names):
    shim = work + '/shim'
    os.makedirs(shim, exist_ok=True)
    stub = shim + '/loop-sql'
    write_text(stub, '#!/usr/bin/env bash\nprintf "id|versionId|activeVersionId|active\\nfixture|v1|v1|t\\n"\n')
    os.chmod(stub, 0o755)
    env = dict(env)
    env['PATH'] = shim + os.pathsep + env.get('PATH', '')
    cp = subprocess.run([sys.executable, tree + '/bin/loop_tripwire.py', 'selftest'],
                        capture_output=True, text=True, env=env, cwd=work)
    out = cp.stdout
    missing = [n for n in names.split('|') if n not in out]
    # The row passes when the output holds every named case. The exit code and the count of cases
    # that failed with WinError 2 (a stub the host cannot start by name) are information only.
    winerr = len([l for l in out.splitlines() if l.startswith('FAIL ') and 'WinError 2' in l])
    ok = not missing
    actual = 'names' if ok else 'missing=' + ','.join(missing)
    return ok, 'expected=%s actual=%s names_wanted=%d names_missing=%d info: exit=%d winerror2_cases=%d out_sha=%s' % (
        expect, actual, len(names.split('|')), len(missing), cp.returncode, winerr, sha(out + cp.stderr))


def run_preflight(tree, work, env, expect):
    cp = subprocess.run(['bash', tree + '/bin/loop-preflight'],
                        capture_output=True, text=True, env=env, cwd=work)
    hits = [l for l in cp.stdout.splitlines() if l.startswith(expect + ' ') or l == expect]
    actual = expect if hits else 'absent'
    return actual == expect, 'expected=%s actual=%s exit=%d out_sha=%s' % (
        expect, actual, cp.returncode, sha(cp.stdout + cp.stderr))


def main():
    tree, home, work = dirs_or_args()
    os.makedirs(work, exist_ok=True)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = make_env(home, {'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE},
                   ('LOOP_GOAL', 'JOURNAL_FILE'))
    return tally(rows, {
        'filehash': lambda rid, expect, arg: run_filehash(tree, expect, arg),
        'selftest': lambda rid, expect, arg: run_selftest(tree, work, env, expect, arg),
        'preflight': lambda rid, expect, arg: run_preflight(tree, work, env, expect),
        'phrase': lambda rid, expect, arg: run_phrase(tree, expect, arg),
    })


if __name__ == '__main__':
    sys.exit(main())
