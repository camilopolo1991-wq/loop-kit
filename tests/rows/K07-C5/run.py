#!/usr/bin/env python3
"""K07-C5 rows runner: the RULING and HOLD shapes of the step-log tool, and the ruling commit kind of the commit-msg template.
A HOLD line of a goal needs a COMMIT line of the same goal after it; an owner RULING line needs the shape
RULING <n> <path> sha256 <64 hexadecimal characters> ledger row <n>: <text>; a leader RULING line is not judged further.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k07c5-manifest.txt
  LOOP_PY          the interpreter the tool is run with (defaults to the one running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  check            the case named by arg is built under LOOP_WORK (plan, step log; every goal id, task id, path and hash is constructed
                   here) and LOOP_TREE/bin/loop_journal.py --check <goal> --file <log> --plan <plan> is run on it; expect is
                   '<exit>:<tokens>', the exit code and the comma separated tokens that must be in the output, a token with a leading
                   ! being one that must be absent
  append           the append form is run on a fixture log (JOURNAL_FILE) with the text of the case named by arg; expect is
                   '<exit>:<tokens>' as above, 'unchanged' meaning the log bytes are as before, 'appended' meaning the log is the
                   old bytes plus exactly one line ending with the text; a non-zero exit is written 'nz'
  hook             LOOP_TREE/templates/commit-msg is run by bash on a message file holding the subject named by arg; expect is the
                   exit code and ':' and tokens as above
Prints PASS or FAIL per row with expected and actual, then rows=N pass=P fail=F. Nothing is spawned in the background.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, register, sha, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py '
         '(no positional argument)')
MANIFEST = 'k07c5-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
GOAL = 'K07-FIX'
OTHER = 'K07-OTH'
PLAN = '| id | what | owner | status |\n|---|---|---|---|\n| T01 | fixture change | writer | open |\n'
H64 = hashlib.sha256(b'k07c5 fixture ruling').hexdigest()
H16 = H64[:16]
H64_BAD = H64[:63] + 'g'
PATH = '~/.loop/goals/' + GOAL + '/RULING.md'


def owner(h=H64, row=' ledger row 7'):
    return 'RULING 1 ' + PATH + ' sha256 ' + h + row + ': fixture owner ruling'


HOLD = (GOAL, 'GOAL', 'HOLD fixture reason')
COMMIT = (GOAL, 'T01', 'COMMIT fixture 0000000')
FILL = (GOAL, 'GOAL', 'START fixture')

# case: lines (goal, step, text) in order
CASES = {
    'hold-no-commit': dict(lines=[FILL, HOLD]),
    'hold-then-commit': dict(lines=[FILL, HOLD, COMMIT]),
    'hold-commit-other-goal': dict(lines=[FILL, HOLD, (OTHER, 'T01', 'COMMIT fixture 0000000')]),
    'commit-only-before-hold': dict(lines=[FILL, COMMIT, HOLD]),
    'two-holds-one-commit': dict(lines=[FILL, HOLD, COMMIT, (GOAL, 'GOAL', 'HOLD fixture second reason')]),
    'hold-not-first-word': dict(lines=[FILL, (GOAL, 'GOAL', 'DONE HOLD fixture')]),
    'hold-of-other-goal-not-judged': dict(lines=[FILL, (OTHER, 'GOAL', 'HOLD fixture reason')]),
    'ruling-hash-16': dict(lines=[FILL, (GOAL, 'GOAL', owner(H16))]),
    'ruling-hash-64': dict(lines=[FILL, (GOAL, 'GOAL', owner(H64))]),
    'ruling-hash-not-hex': dict(lines=[FILL, (GOAL, 'GOAL', owner(H64_BAD))]),
    'ruling-no-ledger-row': dict(lines=[FILL, (GOAL, 'GOAL', owner(row=''))]),
    'ruling-leader': dict(lines=[FILL, (GOAL, 'GOAL', 'RULING leader on fixture question: fixture answer')]),
    'ruling-leader-no-on': dict(lines=[FILL, (GOAL, 'GOAL', 'RULING leader fixture question: fixture answer')]),
    'ruling-not-first-word': dict(lines=[FILL, (GOAL, 'GOAL', 'DONE RULING 1 fixture without the owner shape')]),
    'ruling-of-other-goal-not-judged': dict(lines=[FILL, (OTHER, 'GOAL', owner(H16))]),
}

# append texts
TEXTS = {
    'ruling-hash-16': owner(H16),
    'ruling-hash-64': owner(H64),
    'ruling-no-ledger-row': owner(row=''),
    'ruling-leader': 'RULING leader on fixture question: fixture answer',
    'other-text': 'DONE fixture without a ruling',
}

# hook subjects
SUBJECTS = {
    'ruling-kind': 'ruling(kit-07): record fixture ruling 1',
    'listed-kind': 'feat(kit-07): fixture change',
    'unlisted-kind': 'wip(kit-07): fixture change',
    'ruling-no-scope': 'ruling: record fixture ruling 1',
}


def split_expect(expect):
    code, toks = expect.split(':', 1)
    return code, [t for t in toks.split(',') if t]


def tokens_unmet(toks, out):
    bad = []
    for t in toks:
        if t.startswith('!'):
            if t[1:] in out:
                bad.append(t)
        elif t not in out:
            bad.append(t)
    return bad


def base_dir(ctx, tag):
    base = '%s/k07c5-fixtures/%s-%d' % (ctx['work'], tag, time.time_ns())
    register(ctx['work'], MANIFEST, base)
    os.makedirs(base, exist_ok=True)
    return base


def stamp(lines):
    return ''.join('- 2026-01-01T00:00:%02dZ %s %s %s\n' % (i, g, s, t) for i, (g, s, t) in enumerate(lines))


def row_check(ctx, rid, expect, arg):
    code, toks = split_expect(expect)
    base = base_dir(ctx, arg)
    write_text(base + '/plan.md', PLAN)
    write_text(base + '/steps.log', stamp(CASES[arg]['lines']))
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_journal.py', '--check', GOAL, '--file', base + '/steps.log',
                         '--plan', base + '/plan.md'], capture_output=True, env=make_env(ctx['home'], None, DROP),
                        cwd=ctx['work'], stdin=subprocess.DEVNULL)
    out = cp.stdout.decode('utf-8', 'replace').replace('\r', '') + cp.stderr.decode('utf-8', 'replace').replace('\r', '')
    bad = tokens_unmet(toks, out)
    ok = cp.returncode == int(code) and not bad
    return ok, 'expected=exit %s, tokens %s actual=exit %d, unmet %s, output bytes %d sha256 %s' % (
        code, ','.join(toks), cp.returncode, ' '.join(bad) or 'none', len(out.encode('utf-8')), sha(out))


def row_append(ctx, rid, expect, arg):
    code, toks = split_expect(expect)
    base = base_dir(ctx, 'append-' + arg)
    log = base + '/steps.log'
    write_text(log, stamp([FILL]))
    before = read_bytes(log)
    env = make_env(ctx['home'], {'JOURNAL_FILE': log}, DROP)
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_journal.py', GOAL, 'GOAL', TEXTS[arg]], capture_output=True, env=env,
                        cwd=ctx['work'], stdin=subprocess.DEVNULL)
    out = cp.stdout.decode('utf-8', 'replace').replace('\r', '') + cp.stderr.decode('utf-8', 'replace').replace('\r', '')
    after = read_bytes(log)
    plain = [t for t in toks if t not in ('unchanged', 'appended')]
    bad = tokens_unmet(plain, out)
    if 'unchanged' in toks and after != before:
        bad.append('unchanged')
    if 'appended' in toks:
        # the redactor filter the append form pipes through ends the line it writes with CR LF on this platform (existing, not judged here)
        tail = after[len(before):].replace(b'\r\n', b'\n') if after.startswith(before) else b''
        if not (tail.endswith(TEXTS[arg].encode('utf-8') + b'\n') and tail.count(b'\n') == 1):
            bad.append('appended')
    code_ok = (cp.returncode != 0) if code == 'nz' else (cp.returncode == int(code))
    return code_ok and not bad, 'expected=exit %s, tokens %s actual=exit %d, unmet %s, log bytes %d -> %d' % (
        code, ','.join(toks), cp.returncode, ' '.join(bad) or 'none', len(before), len(after))


def find_bash():
    for cand in (shutil.which('bash'), 'C:/Program Files/Git/bin/bash.exe', 'C:/Program Files/Git/usr/bin/bash.exe'):
        if cand and os.path.isfile(cand):
            return cand
    return None


def row_hook(ctx, rid, expect, arg):
    code, toks = split_expect(expect)
    bash = find_bash()
    if bash is None:
        return False, 'expected=exit %s actual=no bash found' % code
    base = base_dir(ctx, 'hook-' + arg)
    msg = base + '/msg.txt'
    write_text(msg, SUBJECTS[arg] + '\n')
    cp = subprocess.run([bash, ctx['tree'] + '/templates/commit-msg', msg], capture_output=True, env=make_env(ctx['home'], None, DROP),
                        cwd=ctx['work'], stdin=subprocess.DEVNULL)
    out = cp.stdout.decode('utf-8', 'replace').replace('\r', '') + cp.stderr.decode('utf-8', 'replace').replace('\r', '')
    bad = tokens_unmet(toks, out)
    ok = cp.returncode == int(code) and not bad
    return ok, 'expected=exit %s, tokens %s actual=exit %d, unmet %s, output bytes %d sha256 %s' % (
        code, ','.join(toks), cp.returncode, ' '.join(bad) or 'none', len(out.encode('utf-8')), sha(out))


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K07-C5/run.py', here + '/run.py'), ('tests/rows/K07-C5/rows.txt', here + '/rows.txt')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    return tally(load_rows(here + '/rows.txt'), {'check': row_check, 'append': row_append, 'hook': row_hook}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
