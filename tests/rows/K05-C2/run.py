#!/usr/bin/env python3
"""K05-C2 rows runner: the writer's rollback is a file under the task's writer folder, and the step-log tool's --check
fails a ROLLBACK line whose named path is outside the goal's evidence folders.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expectations in rows.txt, so a tree
without the change prints FAIL on the rows it adds), LOOP_ROWS_HOME (the home every spawned process gets as HOME and
USERPROFILE; LOOP_HOME is that home plus /.loop), LOOP_WORK (a work folder, created when absent), LOOP_PY (the
interpreter the tool needs), LOOP_NAMES_FILE (passed through untouched).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Every fixture (a plan, a step log, an empty journal file) is written under LOOP_WORK at run time from the row text.
JOURNAL_FILE is set to the fixture journal and LOOP_GOAL to a fixture goal id for every spawned process, so nothing reads
or appends the live step log. The tool is run as bash <tree>/bin/loop-journal --check. At its start the runner removes only
what its own manifest file (k05c2-manifest.txt in LOOP_WORK) lists from an earlier run. Prints PASS or FAIL per row with
expected and actual; a sha256 stands in for any text that could hold a home path. Nothing is spawned in the background,
nothing is killed, no timeout is set.
"""
import hashlib
import os
import subprocess
import sys

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'
MANIFEST = 'k05c2-manifest.txt'
GOAL = 'K05-FIX'
SEP = ' ;; '


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


def read_bytes(p):
    try:
        with open(p, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def register(work, path):
    with open(work + '/' + MANIFEST, 'a', encoding='utf-8') as fh:
        fh.write(path + '\n')


def remove_path(p):
    if os.path.isdir(p):
        for root, dirs, files in os.walk(p, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                os.chmod(fp, 0o600)
                os.remove(fp)
            for d in dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(p)
    elif os.path.exists(p):
        os.chmod(p, 0o600)
        os.remove(p)


def clean_earlier(work):
    mf = work + '/' + MANIFEST
    data = read_bytes(mf)
    if data is None:
        return 0
    n = 0
    for p in data.decode('utf-8', 'replace').split('\n'):
        p = p.strip()
        if p and fwd(p).startswith(work + '/') and fwd(p) != mf:
            remove_path(p)
            n += 1
    os.remove(mf)
    return n


def make_env(home, journal, py):
    env = dict(os.environ)
    env['HOME'] = home
    env['USERPROFILE'] = home
    env['LOOP_HOME'] = home + '/.loop'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['JOURNAL_FILE'] = journal
    env['LOOP_GOAL'] = GOAL
    env['LOOP_PY'] = py
    return env


def row_phrase(ctx, rid, expect, arg):
    rel, phrases = arg.split('|', 1)
    data = read_bytes(ctx['tree'] + '/' + rel)
    if data is None:
        return False, 'expected=%s actual=file absent' % expect
    text = data.decode('utf-8', 'replace').replace('\r', '')
    wanted = phrases.split(SEP)
    missing = [i + 1 for i, ph in enumerate(wanted) if ph not in text]
    ok = not missing
    return ok, 'expected=found phrases=%d actual=%s missing=%s file_sha=%s' % (
        len(wanted), 'found' if ok else 'not found', ','.join(str(m) for m in missing) or 'none', sha(data))


def row_check(ctx, rid, expect, arg):
    want_exit, checks = expect.split('|', 1)
    goal, named = arg.split('|', 1)
    folder = '%s/%s' % (ctx['work'], rid)
    os.makedirs(folder, exist_ok=True)
    register(ctx['work'], folder)
    plan = folder + '/plan.md'
    log = folder + '/steps.log'
    journal = folder + '/journal-fixture.log'
    with open(plan, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('| id | what | owner | status |\n|---|---|---|---|\n| T03 | fixture change | writer | open |\n')
    with open(log, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('- 2026-01-01T00:00:00Z %s T03 ROLLBACK %s sha256 0123456789abcdef\n' % (goal, named))
        fh.write('- 2026-01-01T00:01:00Z %s T03 DONE fixture change made\n' % goal)
    with open(journal, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('')
    cp = subprocess.run(['bash', ctx['tree'] + '/bin/loop-journal', '--check', goal, '--file', log, '--plan', plan],
                        capture_output=True, env=make_env(ctx['home'], journal, ctx['py']), cwd=ctx['work'])
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


KINDS = {'phrase': row_phrase, 'check': row_check}


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
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    cleaned = clean_earlier(work)
    print('cleaned %d path(s) listed by an earlier run' % cleaned)
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': py}
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        fn = KINDS.get(kind)
        if fn is None:
            ok, detail = False, 'unknown kind ' + kind
        else:
            try:
                ok, detail = fn(ctx, rid, expect, arg)
            except Exception as exc:
                ok, detail = False, 'expected=row runs actual=error %s' % type(exc).__name__
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
