#!/usr/bin/env python3
"""S01-C8 rows runner: the tripwire's path list read through the configuration module, and the module's one splitter.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same rows in rows.txt, so a tree whose
tripwire still reads the environment alone, or whose configuration module has no splitter, prints FAIL on the rows
that need them), LOOP_ROWS_HOME (HOME and USERPROFILE of every child, with LOOP_HOME at that home plus /.loop unless a
row names a fixture loop home), LOOP_WORK (a work folder, created when absent), LOOP_PY and LOOP_NAMES_FILE (accepted,
unused here).
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
import json
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import clean_earlier, env_dirs, info_sha, load_rows, make_env, register, shafull, tally, write_text

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


def sha12(s):
    return shafull(s.encode('utf-8', 'replace'))[:12]


def run_child(ctx, mode, text, loop_home, writable):
    env = make_env(ctx['home'], {'LOOP_HOME': loop_home, 'S01C8_BIN': ctx['tree'] + '/bin', 'S01C8_MODE': mode,
                                 'S01C8_INPUT': text},
                   ('WRITABLE_TREES', 'LOOP_TRIPWIRE_GIT_SEARCH_BASES', 'JOURNAL_FILE', 'LOOP_GOAL'))
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
    register(ctx['work'], MANIFEST, fh_dir)
    write_text(fh_dir + '/config.env', arg + '\n')
    got, why = run_child(ctx, 'bases', '', fh_dir, None)
    return verdict(expect, got, why)


def row_split(ctx, expect, arg):
    got, why = run_child(ctx, 'split', arg, ctx['home'] + '/.loop', None)
    return verdict(expect, got, why)


KINDS = {'bases': row_bases, 'basesconf': row_basesconf, 'split': row_split}


def main():
    tree, home, work = env_dirs(USAGE)
    clean_earlier(work, MANIFEST, True)
    ctx = {'tree': tree, 'work': work, 'home': home}
    write_text(work + '/' + PROBE, PROBE_TEXT)
    register(ctx['work'], MANIFEST, work + '/' + PROBE)
    here = os.path.dirname(os.path.abspath(__file__))
    info_sha((('tests/rows/S01-C8/run.py', here + '/run.py'), ('tests/rows/S01-C8/rows.txt', here + '/rows.txt')))
    rows = load_rows(os.path.join(here, 'rows.txt'))
    return tally(rows, KINDS, (ctx,), True, False)


if __name__ == '__main__':
    sys.exit(main())
