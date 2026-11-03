#!/usr/bin/env python3
"""K06-C6 rows runner: the dead files out.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the first three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of the children that need no home of their own
  LOOP_WORK        the work folder; every fixture and throwaway home is written under it and listed in k06c6-manifest.txt
  LOOP_PY, LOOP_NAMES_FILE   handed to the children (LOOP_PY defaults to the interpreter running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  path      arg is a path under LOOP_TREE; expect absent: nothing is there; expect present: a file that is not empty is there
  moved     arg is 'new|old'; expect is a sha256: the file at the new place has that sha256 and nothing is at the old place
  launch    arg is a launcher file under LOOP_TREE; bash runs it with LOOP_PY set and no argument: it exits with the code in
            expect and its stderr holds the word neutralised (the launcher found its module beside itself and ran it)
  selftest  arg is 'command file|reference tree folder name'; bash runs 'selftest' from LOOP_TREE/bin with HOME, USERPROFILE
            and LOOP_HOME at a throwaway home under LOOP_WORK. It passes when tests/tripwire_selftest.py is there, the command
            prints expect (seventeen) case lines without a not-found message, and its exit code and the sha256 of its case-result
            lines (result and case name, no path) equal those of the same command run from the reference tree (the folder of
            that name beside LOOP_TREE, wt-main, which holds the file at the old path). Both exits and both sha256 are printed.
            On a host without the probe wrapper both trees exit 1; the criterion's exit 0 is not reached there.
  selftest-control   a scratch copy of LOOP_TREE/bin under LOOP_WORK with no tests folder beside it fails the same find check;
            printed as FAIL on a control line; the row passes when the tree passes the check and the copy fails it
  pii       the file is the skill; it holds the phrase 'written by the owner by hand' and neither 'refresh' nor 'loop-names-refresh'
  liners    arg is 'README path|one-liner ;; one-liner ...'; every one-liner stands on a line of a Markdown table of the file
  install   install.sh of the tree, environment form with LOOP_WITH_TESTS=1, into a throwaway home under LOOP_WORK: exit 0,
            none of the files named in arg under .loop/bin, a command file that stays (loop-scan) placed there, and the
            moved selftest placed under .loop/tests
  control   a scratch copy of the README under LOOP_WORK with the second one-liner's line removed: the check of the liners
            row, run on the copy, is printed as FAIL on a control line; the row passes when the unmodified README passes
            the check, the copy fails it and exactly the one line is gone

Prints PASS or FAIL per row with expected and actual (a sha256 stands in for any text that could hold a path), then
rows=N pass=P fail=F. Nothing is spawned in the background and nothing is killed.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import SEP, clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, register, shafull, tally

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] '
         'python run.py (no positional argument)')
MANIFEST = 'k06c6-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS', 'LOOP_TRIPWIRE_TESTS_DIR', 'SURFACES')
PII_PHRASE = 'written by the owner by hand'


def sha_of(b):
    return hashlib.sha256(b).hexdigest()


def throwaway_home(ctx, name):
    home = ctx['work'] + '/' + name
    register(ctx['work'], MANIFEST, home)
    os.makedirs(home)
    return home


def row_path(ctx, rid, expect, arg):
    p = ctx['tree'] + '/' + arg
    if expect == 'absent':
        there = os.path.exists(p)
        return not there, 'expected=%s absent actual=%s' % (arg, 'present' if there else 'absent')
    b = read_bytes(p)
    ok = b is not None and len(b) > 0
    return ok, 'expected=%s present and not empty actual=%s' % (arg, 'absent' if b is None else '%d bytes sha256=%s' % (len(b), sha_of(b)))


def row_moved(ctx, rid, expect, arg):
    new, old = arg.split('|')
    b = read_bytes(ctx['tree'] + '/' + new)
    got = None if b is None else sha_of(b)
    old_there = os.path.exists(ctx['tree'] + '/' + old)
    ok = got == expect and not old_there
    return ok, 'expected=%s at the new place and nothing at the old place actual=new place %s, old place %s' % (
        new, 'absent' if got is None else ('sha256 equal' if got == expect else 'sha256 %s' % got), 'present' if old_there else 'absent')


def row_launch(ctx, rid, expect, arg):
    script = ctx['tree'] + '/' + arg
    if read_bytes(script) is None:
        return False, 'expected=%s launches its module, exit %s actual=%s absent' % (arg, expect, arg)
    env = make_env(ctx['home'], {'LOOP_PY': ctx['py']}, DROP)
    cp = subprocess.run(['bash', script], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, cwd=ctx['work'])
    said = 'neutralised' in cp.stderr
    ok = cp.returncode == int(expect) and said
    return ok, 'expected=exit %s and a stderr holding the word neutralised actual=exit %d, word %s, stderr sha256=%s' % (
        expect, cp.returncode, 'found' if said else 'not found', sha_of(cp.stderr.encode('utf-8', 'replace'))[:12])


def selftest_run(ctx, root, name):
    """Runs bash root/bin/loop-tripwire selftest from root/bin with HOME, USERPROFILE and LOOP_HOME at a throwaway home under
    LOOP_WORK. Returns (exit code, [(result, case name)], sha256 of those result lines, stderr says not found)."""
    script = root + '/bin/loop-tripwire'
    if read_bytes(script) is None:
        return None, [], sha_of(b''), False
    home = throwaway_home(ctx, name)
    env = make_env(home, {'LOOP_PY': ctx['py']}, DROP)
    cp = subprocess.run(['bash', script, 'selftest'], capture_output=True, text=True, encoding='utf-8', errors='replace',
                        env=env, cwd=root + '/bin')
    cases = []
    for ln in cp.stdout.replace('\r', '').split('\n'):
        m = re.match(r'^(PASS|FAIL) (case[0-9]+-[^:]*):', ln)
        if m:
            cases.append((m.group(1), m.group(2)))
    digest = sha_of(''.join('%s %s\n' % c for c in cases).encode('utf-8'))
    return cp.returncode, cases, digest, 'not found' in cp.stderr


def find_check(ctx, root, name, want):
    """Row c's find check on a tree: tests/tripwire_selftest.py is there, and the command printed want case lines without
    saying the file was not found. Returns (ok, exit, cases, digest, detail)."""
    there = os.path.isfile(root + '/tests/tripwire_selftest.py')
    rc, cases, digest, nf = selftest_run(ctx, root, name)
    ok = there and rc is not None and not nf and len(cases) == want
    return ok, rc, cases, digest, 'file %s, %d case lines, not-found message %s' % ('there' if there else 'absent', len(cases), 'yes' if nf else 'no')


def row_selftest(ctx, rid, expect, arg):
    rel, ref = arg.split('|')
    ref_root = os.path.dirname(ctx['tree']) + '/' + ref
    ok, rc, cases, digest, detail = find_check(ctx, ctx['tree'], 'k06c6-selftest-home', int(expect))
    rrc, rcases, rdigest, _ = selftest_run(ctx, ref_root, 'k06c6-selftest-ref-home')
    same = rc is not None and rc == rrc and digest == rdigest and len(rcases) == int(expect)
    return ok and same, ('expected=the file at tests/tripwire_selftest.py found, %s case lines, and the exit and the sha256 of the case-result lines equal '
                         'those of the %s tree run the same way from its bin actual=tree exit %s sha256=%s (%s), %s exit %s sha256=%s with %d case lines') % (
        expect, ref, rc, digest, detail, ref, rrc, rdigest, len(rcases))


def row_selftest_control(ctx, rid, expect, arg):
    want = int(expect)
    real_ok = find_check(ctx, ctx['tree'], 'k06c6-selftest-control-home', want)[0]
    d = ctx['work'] + '/k06c6-selftest-control'
    register(ctx['work'], MANIFEST, d)
    os.makedirs(d)
    src = ctx['tree'] + '/bin'
    shutil.copytree(src, d + '/bin', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    ok, rc, cases, digest, detail = find_check(ctx, d, 'k06c6-selftest-control-copy-home', want)
    print('%s control %s expected=the file at tests/tripwire_selftest.py found and %d case lines actual=exit %s, %s (scratch copy of bin with no tests folder beside it)' % (
        'PASS' if ok else 'FAIL', 'j-control-find-check', want, rc, detail))
    return real_ok and not ok, 'expected=the tree passes the find check and the copy without tests/tripwire_selftest.py fails it actual=tree %s, copy %s, controls=1' % (
        'passes' if real_ok else 'fails', 'passes' if ok else 'fails')


def row_pii(ctx, rid, expect, arg):
    b = read_bytes(ctx['tree'] + '/' + arg)
    if b is None:
        return False, 'expected=%s holds the phrase actual=%s absent' % (arg, arg)
    text = b.decode('utf-8', 'replace').lower()
    has = PII_PHRASE in text
    refresh = 'refresh' in text
    return has and not refresh, 'expected=the phrase %r present and the word refresh absent actual=phrase %s, refresh %s, file sha256=%s' % (
        PII_PHRASE, 'present' if has else 'absent', 'present' if refresh else 'absent', sha_of(b)[:12])


def liners_check(text, liners):
    """(missing count, found count): a one-liner is found when it stands inside a line that starts with a pipe."""
    table_lines = [ln for ln in text.replace('\r', '').split('\n') if ln.startswith('|')]
    found = [x for x in liners if any(x in ln for ln in table_lines)]
    return len(liners) - len(found), len(found)


def row_liners(ctx, rid, expect, arg):
    rel, rest = arg.split('|', 1)
    liners = rest.split(SEP)
    b = read_bytes(ctx['tree'] + '/' + rel)
    if b is None:
        return False, 'expected=%d one-liners in a table of %s actual=%s absent' % (len(liners), rel, rel)
    missing, found = liners_check(b.decode('utf-8', 'replace'), liners)
    return missing == 0 and len(liners) == 4, 'expected=%d one-liners in a table of %s actual=%d found, %d missing, file sha256=%s' % (
        len(liners), rel, found, missing, sha_of(b)[:12])


def row_install(ctx, rid, expect, arg):
    names = arg.split('|')
    home = throwaway_home(ctx, 'k06c6-install-home')
    env = make_env(home, {'LOOP_PY': ctx['py'], 'LOOP_WITH_TESTS': '1'}, [d for d in DROP if d != 'LOOP_WITH_TESTS'])
    cp = subprocess.run(['bash', ctx['tree'] + '/install.sh'], capture_output=True, text=True, encoding='utf-8',
                        errors='replace', env=env, cwd=ctx['work'])
    placed = [n for n in names if os.path.exists(home + '/.loop/' + n)]
    scan = os.path.isfile(home + '/.loop/bin/loop-scan')
    selftest = os.path.isfile(home + '/.loop/tests/tripwire_selftest.py')
    ok = cp.returncode == 0 and not placed and scan and selftest
    return ok, 'expected=exit 0, none of %d retired paths under .loop, loop-scan placed, tests/tripwire_selftest.py placed actual=exit %d, %d placed %s, loop-scan %s, selftest %s, out sha256=%s' % (
        len(names), cp.returncode, len(placed), ','.join(placed) or 'none', 'placed' if scan else 'absent', 'placed' if selftest else 'absent',
        sha_of((cp.stdout + cp.stderr).encode('utf-8', 'replace'))[:12])


def row_control(ctx, rid, expect, arg):
    src = read_bytes(ctx['tree'] + '/' + arg)
    liners = None
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'), encoding='utf-8') as fh:
        for r in load_rows(fh.name):
            if r[1] == 'liners':
                liners = r[3].split('|', 1)[1].split(SEP)
    if src is None or not liners:
        return False, 'expected=a README and the one-liners actual=%s %s' % (arg, 'absent' if src is None else 'present, no liners row')
    text = src.decode('utf-8', 'replace')
    lines = text.split('\n')
    keep = [ln for ln in lines if not (ln.startswith('|') and liners[1] in ln)]
    removed = len(lines) - len(keep)
    d = ctx['work'] + '/k06c6-control'
    register(ctx['work'], MANIFEST, d)
    os.makedirs(d)
    with open(d + '/README.unmodified.md', 'wb') as fh:
        fh.write(src)
    with open(d + '/README.changed.md', 'wb') as fh:
        fh.write('\n'.join(keep).encode('utf-8'))
    same_missing, _ = liners_check(read_bytes(d + '/README.unmodified.md').decode('utf-8', 'replace'), liners)
    chg_missing, chg_found = liners_check(read_bytes(d + '/README.changed.md').decode('utf-8', 'replace'), liners)
    chg_ok = chg_missing == 0
    print('%s control %s expected=%d one-liners in a table actual=%d found, %d missing (scratch copy of %s with the line of one one-liner removed)' % (
        'PASS' if chg_ok else 'FAIL', 'h-control-liners-check', len(liners), chg_found, chg_missing, arg))
    ok = same_missing == 0 and not chg_ok and removed == 1
    return ok, 'expected=unmodified copy passes the check, changed copy fails it, one line removed actual=unmodified %s, changed %s, %d line(s) removed, controls=1' % (
        'passes' if same_missing == 0 else 'fails', 'passes' if chg_ok else 'fails', removed)


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K06-C6/run.py', here + '/run.py'), ('tests/rows/K06-C6/rows.txt', here + '/rows.txt')))
    rows = load_rows(here + '/rows.txt')
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    kinds = {'path': lambda r, e, a: row_path(ctx, r, e, a), 'moved': lambda r, e, a: row_moved(ctx, r, e, a),
             'launch': lambda r, e, a: row_launch(ctx, r, e, a), 'selftest': lambda r, e, a: row_selftest(ctx, r, e, a),
             'selftest-control': lambda r, e, a: row_selftest_control(ctx, r, e, a),
             'pii': lambda r, e, a: row_pii(ctx, r, e, a), 'liners': lambda r, e, a: row_liners(ctx, r, e, a),
             'install': lambda r, e, a: row_install(ctx, r, e, a), 'control': lambda r, e, a: row_control(ctx, r, e, a)}
    return tally(rows, kinds, (), True)


if __name__ == '__main__':
    sys.exit(main())
