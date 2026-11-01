#!/usr/bin/env python3
"""K06-C1 rows runner: one guard library under the four hooks (hooks/_guardlib.py).

Environment (no positional argument; exit 64 with the usage line when one is given or one of the first three is unset):
  LOOP_TREE        the tree under test (its hooks/ and install.sh are run)
  LOOP_ROWS_HOME   the rows home; HOME and USERPROFILE are set to it for every child, LOOP_HOME to <it>/.loop. Never written.
  LOOP_WORK        the work folder; every fixture is written under it
  LOOP_PY          the interpreter handed to install.sh (default: the one running this file)

Every child also gets LOOP_GOAL=FIXTURE-K06C1, LOOP_ROLE as the row says, JOURNAL_FILE at a fixture under LOOP_WORK and
PYTHONDONTWRITEBYTECODE=1.

Rows:
  decision rows   rows.txt: one hook JSON per row, fed to LOOP_TREE/hooks/<hook>; the decision and the first word of the
                  deny reason must equal what wt-main's hook gave (written into rows.txt when the rows were made)
  reason-text     one row: the sha256 of the whole deny reason equals the measured one on every row that has one
  count           no def name appears in two files under LOOP_TREE/hooks/ (two readings: ast and a text scan)
  control         a copy of LOOP_TREE/hooks/ with one byte of the copied library changed must flip one named payload's
                  decision; the comparison is printed as FAIL on a control line and the row passes only when the flip is seen
  nolib           a copy of LOOP_TREE/hooks/ without the library: each hook denies a payload it allows, naming itself
  upgrade         a copy of the rows home, install.sh with LOOP_UPGRADE=1 and LOOP_UPGRADE_HOOKS=1: the library lands beside
                  the four hooks and appears under added
  fresh           a fresh install places the library beside the four hooks

Prints PASS or FAIL per row with expected and actual (the sha256 of the text where it could hold a path), then
rows=N pass=P fail=F. Writes nothing outside LOOP_WORK, spawns nothing in the background, kills nothing.
"""
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py '
         '(no positional argument)')
GOAL = 'FIXTURE-K06C1'
MANIFEST = 'k06c1-manifest.txt'
HOOK_FILES = {'pre': 'pretool-guard.py', 'ro': 'readonly-guard.py', 'wg': 'writer-git-guard.py',
              'wp': 'writer-path-guard.py'}
CONTROL_ROW = 'ro-deny-bash-rm-exe'
CONTROL_FROM = b"'.exe'"
CONTROL_TO = b"'.exX'"


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def shafull(b):
    return hashlib.sha256(b).hexdigest()


def shatext(s):
    return hashlib.sha256(s.encode('utf-8', 'replace')).hexdigest()


def read_bytes(p):
    try:
        with open(p, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


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
    """Remove only what an earlier run of this runner wrote, as listed in its own manifest file."""
    mf = work + '/' + MANIFEST
    data = read_bytes(mf)
    if data is None:
        return 0
    n = 0
    for p in data.decode('utf-8', 'replace').split('\n'):
        p = p.strip()
        if p and fwd(p).startswith(work + '/') and fwd(p) != mf and os.path.exists(p):
            remove_path(p)
            n += 1
    os.remove(mf)
    return n


def register(ctx, p):
    with open(ctx['work'] + '/' + MANIFEST, 'a', encoding='utf-8') as fh:
        fh.write(p + '\n')


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', 6)])
    return rows


def child_env(ctx, home=None, role=None, extra=None):
    h = home or ctx['home']
    env = dict(os.environ)
    for k in ('LOOP_GUARD_MODE', 'LOOP_WITH_TESTS', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_UPGRADE',
              'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR'):
        env.pop(k, None)
    env.update({'HOME': h, 'USERPROFILE': h, 'LOOP_HOME': h + '/.loop', 'LOOP_GOAL': GOAL,
                'JOURNAL_FILE': ctx['work'] + '/journal-fixture.txt', 'PYTHONDONTWRITEBYTECODE': '1',
                'LOOP_PY': ctx['py']})
    if role:
        env['LOOP_ROLE'] = role
    if extra:
        env.update(extra)
    return env


def classify(cp):
    """(decision, first word of the deny reason, sha256 prefix of the whole reason)."""
    if cp.returncode == 0 and cp.stdout == '' and cp.stderr == '':
        return 'allow', '-', '-'
    if cp.returncode == 0 and cp.stderr == '':
        try:
            h = json.loads(cp.stdout)['hookSpecificOutput']
            if h['permissionDecision'] == 'deny':
                reason = str(h.get('permissionDecisionReason', ''))
                return 'deny', reason.split()[0], shatext(reason)[:12]
        except Exception:
            pass
    return 'other', 'rc=%s' % cp.returncode, 'out=%s err=%s' % (shatext(cp.stdout)[:12], shatext(cp.stderr)[:12])


def run_hook(ctx, hooks_dir, hook, role, payload):
    text = payload[4:] if payload.startswith('RAW:') else payload.replace('~/', ctx['home'] + '/')
    cp = subprocess.run([ctx['py_self'], '-I', '-B', hooks_dir + '/' + HOOK_FILES[hook]], input=text,
                        capture_output=True, text=True, encoding='utf-8', errors='replace',
                        env=child_env(ctx, role=role), cwd=ctx['work'])
    return classify(cp)


def safe(ctx, s):
    for h in ctx['hide']:
        if h and h in s:
            return 'sha256:' + shatext(s)[:12]
    return s


def emit(ctx, rid, ok, expected, actual):
    ctx['rows'] += 1
    if ok:
        ctx['pass'] += 1
    else:
        ctx['fail'] += 1
    print('%s %s expected=%s actual=%s' % ('PASS' if ok else 'FAIL', rid, safe(ctx, expected), safe(ctx, actual)))


def def_names(tree):
    """{def name: [files]} over every .py under <tree>/hooks, by ast and by a text scan."""
    by_ast, by_text = {}, {}
    base = tree + '/hooks'
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in sorted(files):
            if not f.endswith('.py'):
                continue
            p = os.path.join(root, f)
            b = read_bytes(p) or b''
            text = b.decode('utf-8', 'replace')
            names = set()
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(node.name)
            for n in names:
                by_ast.setdefault(n, []).append(f)
            tnames = set(re.findall(r'^[ \t]*(?:async[ \t]+)?def[ \t]+(\w+)', text, re.M))
            for n in tnames:
                by_text.setdefault(n, []).append(f)
    return ({k: v for k, v in by_ast.items() if len(v) > 1}, {k: v for k, v in by_text.items() if len(v) > 1})


def row_count(ctx):
    a, t = def_names(ctx['tree'])
    ok = not a and not t
    actual = 'ast=%d name(s) in two or more files [%s]; text scan=%d [%s]' % (
        len(a), ','.join(sorted(a)), len(t), ','.join(sorted(t)))
    emit(ctx, 'count-no-def-name-in-two-hook-files', ok, 'ast=0 text scan=0', actual)


def row_control(ctx, rows):
    src = ctx['tree'] + '/hooks'
    dst = ctx['work'] + '/ctl-hooks'
    payload = next((r for r in rows if r[0] == CONTROL_ROW), None)
    if payload is None:
        emit(ctx, 'control-flip-seen', False, 'flip seen', 'control payload row ' + CONTROL_ROW + ' absent')
        return
    register(ctx, dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    lib = dst + '/_guardlib.py'
    data = read_bytes(lib)
    if data is None:
        emit(ctx, 'control-flip-seen', False, 'a library in the tree to edit by one byte', 'no hooks/_guardlib.py in the tree')
        return
    if data.count(CONTROL_FROM) != 1:
        emit(ctx, 'control-flip-seen', False, 'one place to edit', '%d places' % data.count(CONTROL_FROM))
        return
    new = data.replace(CONTROL_FROM, CONTROL_TO)
    diff = sum(1 for x, y in zip(data, new) if x != y)
    if len(new) != len(data) or diff != 1:
        emit(ctx, 'control-flip-seen', False, 'a one byte edit', 'length %d->%d, %d byte(s) differ' % (len(data), len(new), diff))
        return
    with open(lib, 'wb') as fh:
        fh.write(new)
    hook, role, want_dec, want_word, payload_text = payload[1], payload[2], payload[3], payload[4], payload[6]
    base_dec, base_word, _ = run_hook(ctx, src, hook, role, payload_text)
    copy_dec, copy_word, _ = run_hook(ctx, dst, hook, role, payload_text)
    same = (copy_dec == want_dec and copy_word == want_word)
    print('%s control %s expected=%s/%s actual=%s/%s (copy with one byte of the library changed, payload row %s)' % (
        'PASS' if same else 'FAIL', 'c-control-comparison', want_dec, want_word, copy_dec, copy_word, CONTROL_ROW))
    flipped = base_dec == want_dec and copy_dec != want_dec
    emit(ctx, 'control-flip-seen', flipped, 'tree=%s copy differs' % want_dec, 'tree=%s copy=%s' % (base_dec, copy_dec))


def row_nolib(ctx, rows):
    """A copy of LOOP_TREE/hooks/ without the library: each hook, given a payload it allows, denies and names itself."""
    dst = ctx['work'] + '/nolib-hooks'
    register(ctx, dst)
    shutil.copytree(ctx['tree'] + '/hooks', dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '_guardlib.py'))
    for hook, fname in sorted(HOOK_FILES.items()):
        r = next((x for x in rows if x[1] == hook and x[3] == 'allow'), None)
        want = fname[:-3]
        if r is None:
            emit(ctx, 'nolib-%s-fails-closed' % hook, False, 'deny/%s' % want, 'no allow row for the hook')
            continue
        dec, w, _ = run_hook(ctx, dst, hook, r[2], r[6])
        emit(ctx, 'nolib-%s-fails-closed' % hook, dec == 'deny' and w == want, 'deny/%s' % want, '%s/%s' % (dec, w))


def row_upgrade(ctx):
    up = ctx['work'] + '/up-home'
    bk = ctx['work'] + '/up-backup'
    register(ctx, up)
    register(ctx, bk)
    shutil.copytree(ctx['home'], up)
    if not os.path.isfile(up + '/.loop/config.env'):
        with open(up + '/.loop/config.env', 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('# fixture config for the upgrade row\n')
    env = child_env(ctx, home=up, extra={'LOOP_UPGRADE': '1', 'LOOP_UPGRADE_HOOKS': '1', 'LOOP_BACKUP_DIR': bk})
    cp = subprocess.run(['bash', ctx['tree'] + '/install.sh'], capture_output=True, text=True, encoding='utf-8',
                        errors='replace', env=env, cwd=ctx['work'])
    out = cp.stdout.replace('\r', '')
    added = [ln for ln in out.split('\n') if ln.startswith('added .claude/hooks/_guardlib.py ')]
    tree_lib = read_bytes(ctx['tree'] + '/hooks/_guardlib.py')
    got = read_bytes(up + '/.claude/hooks/_guardlib.py')
    four = all(os.path.isfile(up + '/.claude/hooks/' + n) for n in HOOK_FILES.values())
    ok = (cp.returncode == 0 and len(added) == 1 and got is not None and got == tree_lib and four)
    emit(ctx, 'upgrade-places-library-under-added', ok,
         'exit 0, one added line for .claude/hooks/_guardlib.py, file equals the tree library, four hooks beside it',
         'exit %d, added lines %d, library %s, four hooks %s, out sha256=%s' % (
             cp.returncode, len(added), 'absent' if got is None else ('equal' if got == tree_lib else 'differs'),
             'yes' if four else 'no', shatext(cp.stdout + cp.stderr)[:12]))


def row_fresh(ctx):
    fh_dir = ctx['work'] + '/fresh-home'
    register(ctx, fh_dir)
    os.makedirs(fh_dir)
    cp = subprocess.run(['bash', ctx['tree'] + '/install.sh'], capture_output=True, text=True, encoding='utf-8',
                        errors='replace', env=child_env(ctx, home=fh_dir), cwd=ctx['work'])
    tree_lib = read_bytes(ctx['tree'] + '/hooks/_guardlib.py')
    got = read_bytes(fh_dir + '/.claude/hooks/_guardlib.py')
    four = all(os.path.isfile(fh_dir + '/.claude/hooks/' + n) for n in HOOK_FILES.values())
    ok = cp.returncode == 0 and got is not None and got == tree_lib and four
    emit(ctx, 'fresh-install-places-library', ok,
         'exit 0, library equals the tree library, four hooks beside it',
         'exit %d, library %s, four hooks %s, out sha256=%s' % (
             cp.returncode, 'absent' if got is None else ('equal' if got == tree_lib else 'differs'),
             'yes' if four else 'no', shatext(cp.stdout + cp.stderr)[:12]))


def main():
    if len(sys.argv) > 1 or not (os.environ.get('LOOP_TREE') and os.environ.get('LOOP_ROWS_HOME')
                                 and os.environ.get('LOOP_WORK')):
        print(USAGE)
        return 64
    tree = fwd(os.environ['LOOP_TREE'])
    home = fwd(os.environ['LOOP_ROWS_HOME'])
    work = fwd(os.environ['LOOP_WORK'])
    here = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(work, exist_ok=True)
    cleaned = clean_earlier(work)
    ctx = {'tree': tree, 'home': home, 'work': work, 'rows': 0, 'pass': 0, 'fail': 0,
           'py': fwd(os.environ.get('LOOP_PY') or sys.executable), 'py_self': fwd(sys.executable),
           'hide': [home, work, tree, fwd(os.path.expanduser('~'))]}
    for label, p in (('tests/rows/K06-C1/run.py', here + '/run.py'), ('tests/rows/K06-C1/rows.txt', here + '/rows.txt')):
        b = read_bytes(p)
        print('info %s sha256=%s' % (label, shafull(b) if b is not None else 'absent'))
    print('info cleaned %d earlier fixture(s)' % cleaned)
    rows = load_rows(here + '/rows.txt')
    hook_dir = tree + '/hooks'
    reason_bad = reason_n = 0
    for r in rows:
        rid, hook, role, exp, word, rsha, payload = r
        dec, w, rs = run_hook(ctx, hook_dir, hook, role, payload)
        ok = dec == exp and w == word
        if ok and exp == 'deny':
            reason_n += 1
            if rs != rsha:
                reason_bad += 1
        emit(ctx, rid, ok, '%s/%s' % (exp, word), '%s/%s' % (dec, w))
    emit(ctx, 'reason-text-equals-the-measured-reason', reason_bad == 0,
         'sha256 of the whole reason equal on every matched deny row',
         '%d of %d differ' % (reason_bad, reason_n))
    row_count(ctx)
    row_control(ctx, rows)
    row_nolib(ctx, rows)
    row_upgrade(ctx)
    row_fresh(ctx)
    print('decision rows=%d (deny %d, allow %d)' % (
        len(rows), sum(1 for r in rows if r[3] == 'deny'), sum(1 for r in rows if r[3] == 'allow')))
    print('rows=%d pass=%d fail=%d' % (ctx['rows'], ctx['pass'], ctx['fail']))
    return 1 if ctx['fail'] else 0


if __name__ == '__main__':
    sys.exit(main())
