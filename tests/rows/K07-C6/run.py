#!/usr/bin/env python3
"""K07-C6 rows runner: the return.md kind of loop-card-lint, its path rule and its head rule.
The path rule applies to every return: a drive-letter spelling or a user-folder spelling of a path is exit 1, naming the line.
The head rule applies only beside a file named verdict.md: the return's lines must be the first thirty lines of that verdict
(all of them when it holds fewer), as an equality of the whole list with line endings removed; no sibling verdict, the rule is silent.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k07c6-manifest.txt
  LOOP_PY          the interpreter the lint is run with (defaults to the one running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  lint             the case named by arg is built under LOOP_WORK (every path and line is constructed here; a drive-letter or
                   user-folder spelling is assembled at run time from parts) and LOOP_TREE/bin/loop_card_lint.py is run on its
                   files; expect is '<exit>:<tokens>', the exit code and the comma separated tokens that must be in the output,
                   a token with a leading ! being one that must be absent
Prints PASS or FAIL per row with expected and actual, then rows=N pass=P fail=F. Nothing is spawned in the background.
"""
import os
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, register, sha, tally

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py '
         '(no positional argument)')
MANIFEST = 'k07c6-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')

# constructed spellings, assembled here at run time from parts
LETTER = 'Q'
COLON = ':'
FS = '/'
BS = chr(92)
DRIVE_FWD = LETTER + COLON + FS + 'fixture' + FS + 'a.txt'
DRIVE_BACK = LETTER + COLON + BS + 'fixture' + BS + 'a.txt'
TILDE = '~' + FS + 'fixture' + FS + 'a.txt'
USERS_FWD = FS + 'Users' + FS + 'fixture' + FS + 'a.txt'
USERS_BACK = BS + 'Users' + BS + 'fixture' + BS + 'a.txt'
USERS_LOW = FS + 'users' + FS + 'fixture'
USERS_C = FS + 'c' + FS + 'Users' + FS + 'fixture'
USERS_CUP = FS + 'C' + FS + 'USERS' + FS + 'fixture'
HOME_NAME = FS + 'home' + FS + 'fixture' + FS + 'a.txt'
HOME_BARE = FS + 'home' + FS
URL = 'https' + COLON + FS + FS + 'example.invalid' + FS + 'fixture'


def n_lines(n, tag='fixture line'):
    return ['%s %d' % (tag, i) for i in range(1, n + 1)]


def txt(lines, eol='\n'):
    return ''.join(l + eol for l in lines)


def with_line(lines, k, text):
    """lines with line k (1-based) replaced by text."""
    out = list(lines)
    out[k - 1] = text
    return out


V40 = n_lines(40)
V31 = n_lines(31)
V5 = n_lines(5)
CLEAN = ['scout return fixture', 'finding one', 'finding two', 'finding three']


def one_byte(l):
    return l[:-1] + chr(ord(l[-1]) ^ 1)


# case: (files: relative path -> text or bytes, arguments: relative paths in the order given)
CASES = {
    'drive-fwd': ({'d/return.md': txt(with_line(CLEAN, 3, 'see ' + DRIVE_FWD))}, ['d/return.md']),
    'drive-tilde': ({'d/return.md': txt(with_line(CLEAN, 3, 'see ' + TILDE))}, ['d/return.md']),
    'drive-back': ({'d/return.md': txt(with_line(CLEAN, 2, 'see ' + DRIVE_BACK))}, ['d/return.md']),
    'users-fwd': ({'d/return.md': txt(with_line(CLEAN, 4, 'see ' + USERS_FWD))}, ['d/return.md']),
    'users-back': ({'d/return.md': txt(with_line(CLEAN, 4, 'see ' + USERS_BACK))}, ['d/return.md']),
    'users-lower': ({'d/return.md': txt(with_line(CLEAN, 2, 'see ' + USERS_LOW))}, ['d/return.md']),
    'users-c': ({'d/return.md': txt(with_line(CLEAN, 2, 'see ' + USERS_C))}, ['d/return.md']),
    'users-c-upper': ({'d/return.md': txt(with_line(CLEAN, 2, 'see ' + USERS_CUP))}, ['d/return.md']),
    'home-name': ({'d/return.md': txt(with_line(CLEAN, 3, 'see ' + HOME_NAME))}, ['d/return.md']),
    'home-bare': ({'d/return.md': txt(with_line(CLEAN, 3, 'the folder ' + HOME_BARE + ' alone'))}, ['d/return.md']),
    'url-only': ({'d/return.md': txt(with_line(CLEAN, 2, 'see ' + URL))}, ['d/return.md']),
    'letter-after-letter': ({'d/return.md': txt(with_line(CLEAN, 2, 'see ab' + COLON + FS + 'x and 9z' + COLON + BS + 'y'))}, ['d/return.md']),
    'two-hits': ({'d/return.md': txt(with_line(with_line(CLEAN, 2, 'a ' + DRIVE_FWD), 4, 'b ' + USERS_FWD))}, ['d/return.md']),
    'name-upper': ({'d/RETURN.md': txt(with_line(CLEAN, 2, 'see ' + DRIVE_FWD))}, ['d/RETURN.md']),
    'longer-by-one': ({'d/verdict.md': txt(V40), 'd/return.md': txt(V40[:31])}, ['d/return.md']),
    'head-exact': ({'d/verdict.md': txt(V40), 'd/return.md': txt(V40[:30])}, ['d/return.md']),
    'shorter': ({'d/verdict.md': txt(V40), 'd/return.md': txt(V40[:20])}, ['d/return.md']),
    'verdict-31': ({'d/verdict.md': txt(V31), 'd/return.md': txt(V31[:30])}, ['d/return.md']),
    'one-byte': ({'d/verdict.md': txt(V40), 'd/return.md': txt(with_line(V40[:30], 7, one_byte(V40[6])))}, ['d/return.md']),
    'short-verdict-whole': ({'d/verdict.md': txt(V5), 'd/return.md': txt(V5)}, ['d/return.md']),
    'short-verdict-one-more': ({'d/verdict.md': txt(V5), 'd/return.md': txt(V5 + ['an extra line'])}, ['d/return.md']),
    'crlf-verdict': ({'d/verdict.md': txt(V40, '\r\n'), 'd/return.md': txt(V40[:30])}, ['d/return.md']),
    'trailing-space': ({'d/verdict.md': txt(V40), 'd/return.md': txt(with_line(V40[:30], 9, V40[8] + ' '))}, ['d/return.md']),
    'verdict-bad-bytes': ({'d/verdict.md': b'fixture \xff\xfe line\n', 'd/return.md': txt(n_lines(1))}, ['d/return.md']),
    'verdict-alone': ({'d/verdict.md': txt(V5)}, ['d/verdict.md']),
    'scout-clean': ({'d/return.md': txt(CLEAN)}, ['d/return.md']),
    'scout-drive': ({'d/return.md': txt(with_line(CLEAN, 3, 'see ' + DRIVE_FWD))}, ['d/return.md']),
    'verdict-other-folder': ({'p/return.md': txt(V5[:2]), 'q/verdict.md': txt(V5)}, ['p/return.md']),
    'drive-and-head-ok': ({'d/verdict.md': txt(with_line(V40, 5, 'see ' + DRIVE_FWD)),
                           'd/return.md': txt(with_line(V40[:30], 5, 'see ' + DRIVE_FWD))}, ['d/return.md']),
}


def build(ctx, name):
    files, args = CASES[name]
    base = '%s/k07c6-fixtures/%s-%d' % (ctx['work'], name, time.time_ns())
    register(ctx['work'], MANIFEST, base)
    for rel, body in files.items():
        os.makedirs(os.path.dirname(base + '/' + rel), exist_ok=True)
        with open(base + '/' + rel, 'wb') as fh:
            fh.write(body if isinstance(body, bytes) else body.encode('utf-8'))
    return base, [base + '/' + a for a in args]


def row_lint(ctx, rid, expect, arg):
    code, toks = expect.split(':', 1)
    base, files = build(ctx, arg)
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_card_lint.py'] + files, capture_output=True, env=make_env(ctx['home'], {}, DROP),
                        cwd=ctx['work'], stdin=subprocess.DEVNULL)
    out = cp.stdout.decode('utf-8', 'replace').replace('\r', '') + cp.stderr.decode('utf-8', 'replace').replace('\r', '')
    bad = []
    for t in toks.split(','):
        if not t:
            continue
        if t.startswith('!'):
            if t[1:] in out:
                bad.append(t)
        elif t not in out:
            bad.append(t)
    ok = cp.returncode == int(code) and not bad
    return ok, 'expected=exit %s, tokens %s actual=exit %d, unmet %s, output bytes %d sha256 %s' % (
        code, toks, cp.returncode, ' '.join(bad) or 'none', len(out.encode('utf-8')), sha(out))


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K07-C6/run.py', here + '/run.py'), ('tests/rows/K07-C6/rows.txt', here + '/rows.txt')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    return tally(load_rows(here + '/rows.txt'), {'lint': row_lint}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
