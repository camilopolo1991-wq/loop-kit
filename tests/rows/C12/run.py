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

NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder


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
    with open(stub, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('#!/usr/bin/env bash\nprintf "id|versionId|activeVersionId|active\\nfixture|v1|v1|t\\n"\n')
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


def run_phrase(tree, expect, arg):
    rel, phrase = arg.split('|', 1)
    try:
        with open(tree + '/' + rel, 'rb') as fh:
            data = fh.read()
    except OSError:
        return False, 'expected=%s actual=unreadable' % expect
    found = phrase.encode('utf-8') in data
    actual = 'found' if found else 'absent'
    return actual == expect, 'expected=%s actual=%s file_sha=%s' % (expect, actual, sha(data))


def main():
    if len(sys.argv) != 4:
        print('usage: run.py <tree> <home> <work>')
        return 2
    tree, home, work = fwd(sys.argv[1]), fwd(sys.argv[2]), fwd(sys.argv[3])
    os.makedirs(work, exist_ok=True)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = dict(os.environ)
    env.update({'HOME': home, 'USERPROFILE': home, 'LOOP_HOME': home + '/.loop',
                'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE,
                'PYTHONDONTWRITEBYTECODE': '1'})
    env.pop('LOOP_GOAL', None)
    env.pop('JOURNAL_FILE', None)
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        if kind == 'filehash':
            ok, detail = run_filehash(tree, expect, arg)
        elif kind == 'selftest':
            ok, detail = run_selftest(tree, work, env, expect, arg)
        elif kind == 'preflight':
            ok, detail = run_preflight(tree, work, env, expect)
        elif kind == 'phrase':
            ok, detail = run_phrase(tree, expect, arg)
        else:
            ok, detail = False, 'unknown kind ' + kind
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
