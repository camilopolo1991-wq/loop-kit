#!/usr/bin/env python3
"""S01-C8 rows runner: the tripwire's path list read through the configuration module, and the module's one splitter.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same rows in rows.txt, so a tree whose
tripwire still reads the environment alone, or whose configuration module has no splitter, prints FAIL on the rows
that need them), LOOP_ROWS_HOME (HOME and USERPROFILE of every child, with LOOP_HOME at that home plus /.loop unless a
row names a fixture loop home), LOOP_WORK (a work folder, created when absent), LOOP_PY and LOOP_NAMES_FILE (accepted,
unused here).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Each row runs one child process of this interpreter (flags -I -B) on a probe script this runner writes under LOOP_WORK. The
probe imports the tree's bin/loop_tripwire.py or bin/loop_conf.py and prints one JSON list. The child environment has
WRITABLE_TREES, LOOP_TRIPWIRE_GIT_SEARCH_BASES, JOURNAL_FILE and LOOP_GOAL removed, then WRITABLE_TREES set only by a
'bases' row. A 'basesconf' row writes a fixture config.env into a fixture loop home under LOOP_WORK and points LOOP_HOME
there. Nothing runs the tripwire selftest, start or check. Every path the runner creates is listed in
s01c8-manifest.txt in LOOP_WORK; the next run removes only what that file lists. The entries read are compared with
the expected ones; a sha256 prefix of the actual list stands in for the text. Prints PASS or FAIL per row, an info line
with the sha256 of the runner's own two files, then rows=N pass=N fail=N. Nothing is spawned in the background and
nothing is killed.
"""
import hashlib
import json
import os
import subprocess
import sys

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_PY=<python> LOOP_NAMES_FILE=<file> python run.py (no positional argument)'
MANIFEST = 's01c8-manifest.txt'
PROBE = 's01c8-probe.py'
FIXTURE_HOME = 's01c8-loophome'
PROBE_TEXT = '''import json
import os
import sys

sys.path.insert(0, os.environ['S01C8_BIN'])
mode = os.environ['S01C8_MODE']
if mode == 'bases':
    import loop_tripwire
    out = loop_tripwire.get_roots()['git_search_bases']
else:
    import loop_conf
    out = loop_conf.split_list(os.environ['S01C8_INPUT'])
print(json.dumps(out))
'''


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def shafull(b):
    return hashlib.sha256(b).hexdigest()


def sha12(s):
    return shafull(s.encode('utf-8', 'replace'))[:12]


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
        if p and fwd(p).startswith(work + '/') and fwd(p) != work + '/' + MANIFEST and os.path.exists(p):
            remove_path(p)
            n += 1
    os.remove(mf)
    return n


def add_to_manifest(ctx, p):
    with open(ctx['work'] + '/' + MANIFEST, 'a', encoding='utf-8') as fh:
        fh.write(p + '\n')


def run_child(ctx, mode, text, loop_home, writable):
    env = dict(os.environ)
    for k in ('WRITABLE_TREES', 'LOOP_TRIPWIRE_GIT_SEARCH_BASES', 'JOURNAL_FILE', 'LOOP_GOAL'):
        env.pop(k, None)
    env.update({'HOME': ctx['home'], 'USERPROFILE': ctx['home'], 'LOOP_HOME': loop_home,
                'PYTHONDONTWRITEBYTECODE': '1', 'S01C8_BIN': ctx['tree'] + '/bin',
                'S01C8_MODE': mode, 'S01C8_INPUT': text})
    if writable is not None:
        env['WRITABLE_TREES'] = writable
    cp = subprocess.run([sys.executable, '-I', '-B', ctx['work'] + '/' + PROBE],
                        capture_output=True, text=True, env=env, cwd=ctx['work'])
    if cp.returncode != 0:
        err = [ln for ln in cp.stderr.splitlines() if ln.strip()]
        return None, 'child exit=%d last_error_sha=%s' % (cp.returncode, sha12(err[-1] if err else ''))
    try:
        got = json.loads(cp.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None, 'child printed no list'
    return got, ''


def verdict(expect, got, why):
    want = expect.split('|') if expect else []
    if got is None:
        return False, 'expected=%d entries actual=error %s' % (len(want), why)
    ok = got == want
    return ok, 'expected=%d entries actual=%d entries equal=%s sha256=%s' % (len(want), len(got), 'yes' if ok else 'no', sha12('|'.join(got)))


def row_bases(ctx, expect, arg):
    got, why = run_child(ctx, 'bases', '', ctx['home'] + '/.loop', arg)
    return verdict(expect, got, why)


def row_basesconf(ctx, expect, arg):
    fh_dir = ctx['work'] + '/' + FIXTURE_HOME
    os.makedirs(fh_dir, exist_ok=True)
    add_to_manifest(ctx, fh_dir)
    with open(fh_dir + '/config.env', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(arg + '\n')
    got, why = run_child(ctx, 'bases', '', fh_dir, None)
    return verdict(expect, got, why)


def row_split(ctx, expect, arg):
    got, why = run_child(ctx, 'split', arg, ctx['home'] + '/.loop', None)
    return verdict(expect, got, why)


KINDS = {'bases': row_bases, 'basesconf': row_basesconf, 'split': row_split}


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
    tree, work = fwd(tree_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    cleaned = clean_earlier(work)
    print('cleaned %d path(s) listed by an earlier run' % cleaned)
    ctx = {'tree': tree, 'work': work, 'home': fwd(home_e)}
    with open(work + '/' + PROBE, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(PROBE_TEXT)
    add_to_manifest(ctx, work + '/' + PROBE)
    here = os.path.dirname(os.path.abspath(__file__))
    for label, p in (('tests/rows/S01-C8/run.py', here + '/run.py'), ('tests/rows/S01-C8/rows.txt', here + '/rows.txt')):
        b = read_bytes(p)
        print('info sha256 %s %s' % (label, shafull(b) if b is not None else 'absent'))
    rows = load_rows(os.path.join(here, 'rows.txt'))
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        fn = KINDS.get(kind)
        if fn is None:
            ok, detail = False, 'unknown kind ' + kind
        else:
            try:
                ok, detail = fn(ctx, expect, arg)
            except Exception as exc:
                ok, detail = False, 'expected=row runs actual=error %s' % type(exc).__name__
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
