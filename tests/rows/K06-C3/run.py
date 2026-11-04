#!/usr/bin/env python3
"""K06-C3 rows runner: one launcher text under bin/, and the step-log tool, the preflight and the card lint moved to modules.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the first three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k06c3-manifest.txt
  LOOP_PY, LOOP_NAMES_FILE   handed to the children (LOOP_PY defaults to the interpreter running this file)
The comparison tree is the sibling folder wt-main of LOOP_TREE (exit 64 with the usage line when it is absent).

Fixtures are written by the runner from the '#fixture <name> :: <text>' lines of rows.txt (the two characters \\n stand for a
line feed). Rows (rows.txt, id :: kind :: expect :: arg):
  pairs       every launcher under LOOP_TREE/bin/ (an extensionless file that execs the interpreter on a module) equals
              every other, byte for byte; arg is the least number of launchers. On wt-main the launchers differ.
  modules     every launcher has beside it the module its own name gives (dash to underscore, .py added)
  three       bin/loop-journal, bin/loop-preflight and bin/loop-card-lint are the launcher text beside their modules
  fixture     one tool case (arg) is run from LOOP_TREE and from wt-main on the same fixtures: stdout and exit equal as
              bytes, the exit equal to the number after expect 'equal:'. These rows pass on both trees: the tool of
              wt-main is the same behaviour, so a tree that moved it must not change one byte.
  append      the step-log tool appends the same line to two copies of a fixture log from each tree: stdout, exit and
              the file (the timestamp field masked) equal
  preflight   the preflight run from each tree on a fresh fixture home: stdout equal as RAW bytes (no carriage return is
              deleted; the timestamp, names age and disk lines are left out and the home path replaced), exit equal to
              expect and the redactor control line present
              With arg bad-config the fresh home holds a config file that cannot be decoded; both trees must go on with
              empty values (traceback on stderr, exit 0) as the old command file did.
              With arg crlf-goal the fresh home holds a current_goal file ending CRLF and a plan fixture with a Live block
              under that goal id; both trees must print the live line.
  nopy        failure-path change: the preflight with LOOP_PY at a missing file exits 3 with the launcher's message on stderr
              (the old command file fell back to python3 or python on PATH); this row fails on wt-main
  upgrade     wt-main installed into a fresh home under LOOP_WORK, then LOOP_TREE/install.sh in the upgrade form against it:
              the modules named in arg are printed under added (on wt-main none is)
  control     a copy of bin/<arg> with one byte changed is reported unequal by the comparison of the pairs row; the
              comparison is printed as FAIL on a control line and the row passes only when it is seen

Prints PASS or FAIL per row with expected and actual (a sha256 stands in for any output that could hold a path), then
rows=N pass=P fail=F. Nothing is spawned in the background and nothing is killed.
"""
import os
import re
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, register, sha, shafull, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] '
         'python run.py (no positional argument; the folder wt-main beside LOOP_TREE is the comparison tree)')
MANIFEST = 'k06c3-manifest.txt'
FIX = '#fixture '
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
LAUNCH = re.compile(rb'(?m)^\s*exec\s+"\$PY"\s+"[^"\n]*(\.py|\$MOD)"')
ADDED = re.compile(r'^(replaced|added) (\S+) sha256 before (\S+) after (\S+)$', re.M)
STEP = re.compile(r'(?m)^- \S+ ')
J = 'loop-journal'
L = 'loop-card-lint'
LOG = '@pass/log.log'
# case: (tool, arguments, step log given to the child, how the log path is spelled)
CASES = {
    'check-pass': (J, ['--check', 'FIXT-C3', '--file', LOG, '--plan', '@pass/plan.md'], None, 'plain'),
    'check-fail': (J, ['--check', 'FIXT-C3', '--file', '@fail/log.log', '--plan', '@fail/plan.md'], None, 'plain'),
    'check-no-plan': (J, ['--check', 'FIXT-C3', '--file', LOG, '--plan', '@pass/absent.md'], None, 'plain'),
    'check-usage': (J, ['--check'], None, 'plain'),
    'active-pass': (J, ['--active', 'FIXT-C3', '--file', LOG], None, 'plain'),
    'active-no-start': (J, ['--active', 'NOPE-C3', '--file', LOG], None, 'plain'),
    'active-malformed': (J, ['--active', 'FIXT-C3', '--file', '@bad/log.log'], None, 'plain'),
    'active-usage': (J, ['--active'], None, 'plain'),
    'dispatches-pass': (J, ['--dispatches', 'FIXT-C3'], LOG, 'plain'),
    'dispatches-usage': (J, ['--dispatches'], LOG, 'plain'),
    'read-plain': (J, ['--read', 'FIXT-C3'], LOG, 'plain'),
    'read-tail': (J, ['--read', 'FIXT-C3', '--tail', '2'], LOG, 'plain'),
    'read-other-goal': (J, ['--read', 'OTHER-C3'], LOG, 'plain'),
    'read-none': (J, ['--read', 'NOPE-C3'], LOG, 'plain'),
    'read-drive-spelling': (J, ['--read', 'FIXT-C3'], LOG, 'drive'),
    'read-c-spelling': (J, ['--read', 'FIXT-C3', '--tail', '3'], LOG, 'msys'),
    'read-tail-zero': (J, ['--read', 'FIXT-C3', '--tail', '0'], LOG, 'plain'),
    'read-tail-plus-past-end': (J, ['--read', 'FIXT-C3', '--tail', '+99'], LOG, 'plain'),
    'read-tail-plus-two': (J, ['--read', 'FIXT-C3', '--tail', '+9'], LOG, 'plain'),
    'read-tail-bad':(J, ['--read', 'FIXT-C3', '--tail', 'x'], LOG, 'plain'),
    'read-usage': (J, ['--read'], LOG, 'plain'),
    'read-no-file': (J, ['--read', 'FIXT-C3'], '@pass/absent.log', 'plain'),
    'append-unknown-option': (J, ['--bogus', 'FIXT-C3', 'T01', 'x'], LOG, 'plain'),
    'append-usage': (J, ['FIXT-C3', 'T01'], LOG, 'plain'),
    'lint-card-pass': (L, ['@pass/card.md'], None, 'plain'),
    'lint-card-fail': (L, ['@fail/card.md'], None, 'plain'),
    'lint-plan-pass': (L, ['--log', LOG, '@pass/plan.md'], None, 'plain'),
    'lint-plan-fail': (L, ['--log', '@fail/log.log', '@fail/plan.md'], None, 'plain'),
    'lint-usage': (L, [], None, 'plain'),
    'lint-unknown-kind': (L, [LOG], None, 'plain'),
}


def launchers(tree):
    out = []
    for f in sorted(os.listdir(tree + '/bin')):
        b = read_bytes(tree + '/bin/' + f)
        if '.' not in f and b is not None and LAUNCH.search(b):
            out.append(f)
    return out


def same_bytes(pa, pb):
    """The comparison of the pairs row: two files equal as bytes."""
    a, b = read_bytes(pa), read_bytes(pb)
    return a is not None and a == b


def write_fixtures(ctx):
    d = ctx['work'] + '/k06c3-fixtures'
    register(ctx['work'], MANIFEST, d)
    with open(ctx['rows_file'], encoding='utf-8') as fh:
        for line in fh:
            if line.startswith(FIX):
                name, text = line[len(FIX):].rstrip('\n').split(' :: ', 1)
                os.makedirs(os.path.dirname(d + '/' + name), exist_ok=True)
                write_text(d + '/' + name, text.replace('\\n', '\n'))
                # K07-C3: the check also wants a return file beside the card of each DISPATCH line; the fixture saves one
                # (the card path resolves against the folder of the plan, which is the folder of the log), so the check rows
                # keep comparing the two trees on what they compared before.
                if name.endswith('log.log'):
                    for ln in text.replace('\\n', '\n').split('\n'):
                        words = ln.split(' ', 4)
                        if len(words) == 5 and words[4].startswith('DISPATCH '):
                            card = [w for w in words[4].split()[1:] if w.endswith('.md')]
                            if card:
                                rdir = os.path.dirname(d + '/' + os.path.dirname(name) + '/' + card[-1])
                                os.makedirs(rdir, exist_ok=True)
                                write_text(rdir + '/return.md', 'fixture return\n')
                    # K07-C4: the check also wants the file a ROLLBACK line names to be on disk; the fixture saves one. A relative
                    # path resolves against the folder of the plan (the folder of the log); a ~ path against the fixture home d/hm,
                    # which the check cases are given as HOME (case_run), so the rows home is never written.
                    for ln in text.replace('\\n', '\n').split('\n'):
                        words = ln.split(' ', 4)
                        if len(words) == 5 and words[4].startswith('ROLLBACK '):
                            named = words[4].split()[1].replace('\\', '/')
                            if named.startswith('~/'):
                                rpath = d + '/hm/' + named[2:]
                            else:
                                rpath = d + '/' + os.path.dirname(name) + '/' + named
                            os.makedirs(os.path.dirname(rpath), exist_ok=True)
                            write_text(rpath, 'fixture rollback\n')
    return d


def spell(path, how):
    if how == 'msys':
        return '/' + path[0].lower() + path[2:]
    return path


def child_env(ctx, jf=None, home=None):
    extra = {'LOOP_PY': ctx['py']}
    if jf is not None:
        extra['JOURNAL_FILE'] = jf
    return make_env(home or ctx['home'], extra, DROP)


def run_bash(ctx, script, args, env):
    return subprocess.run(['bash', script] + args, capture_output=True, env=env, cwd=ctx['work'])


def case_run(ctx, base, name):
    tool, args, jf, how = CASES[name]
    fx = ctx['fix']
    full = [fx + '/' + a[1:] if a.startswith('@') else a for a in args]
    jpath = None if jf is None else spell(fx + '/' + jf[1:], how)
    # K07-C4: the check cases get the fixture home (fx/hm) as HOME, USERPROFILE and (plus /.loop) LOOP_HOME, so a ~ path of a
    # ROLLBACK line fixture can name a file written there; every other case keeps the rows home.
    return run_bash(ctx, base + '/bin/' + tool, full, child_env(ctx, jpath, fx + '/hm' if name.startswith('check-') else None))


def row_pairs(ctx, rid, expect, arg):
    names = launchers(ctx['tree'])
    bad = 0
    pairs = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pairs += 1
            if not same_bytes('%s/bin/%s' % (ctx['tree'], a), '%s/bin/%s' % (ctx['tree'], b)):
                bad += 1
    ok = bad == int(expect) and len(names) >= int(arg)
    return ok, 'expected=unequal pairs %s with at least %s launchers actual=unequal pairs %d of %d with %d launchers' % (
        expect, arg, bad, pairs, len(names))


def row_modules(ctx, rid, expect, arg):
    names = launchers(ctx['tree'])
    missing = [n for n in names if not os.path.isfile('%s/bin/%s.py' % (ctx['tree'], n.replace('-', '_')))]
    return len(missing) == int(expect) and len(names) >= int(arg), 'expected=%s launchers without their module, at least %s launchers actual=%d without, %d launchers' % (
        expect, arg, len(missing), len(names))


def row_three(ctx, rid, expect, arg):
    ref = ctx['tree'] + '/bin/loop-scan'
    bad = []
    for n in arg.split():
        if not same_bytes(ctx['tree'] + '/bin/' + n, ref) or not os.path.isfile('%s/bin/%s.py' % (ctx['tree'], n.replace('-', '_'))):
            bad.append(n)
    return not bad, 'expected=%s are the launcher text beside their module actual=%d not: %s' % (arg, len(bad), ' '.join(bad) or 'none')


def row_fixture(ctx, rid, expect, arg):
    want = int(expect.split(':')[1])
    a = case_run(ctx, ctx['tree'], arg)
    b = case_run(ctx, ctx['main'], arg)
    ok = a.stdout == b.stdout and a.returncode == b.returncode == want
    return ok, 'expected=stdout and exit equal, exit %d actual=exit %d/%d stdout bytes %d/%d sha256 %s/%s' % (
        want, a.returncode, b.returncode, len(a.stdout), len(b.stdout), shafull(a.stdout)[:12], shafull(b.stdout)[:12])


def row_append(ctx, rid, expect, arg):
    res = []
    for tag, base in (('tree', ctx['tree']), ('main', ctx['main'])):
        jf = '%s/append-%s.log' % (ctx['work'], tag)
        register(ctx['work'], MANIFEST, jf)
        write_text(jf, read_bytes(ctx['fix'] + '/pass/log.log').decode('utf-8'))
        text = 'fixture appended line at %s/x.txt' % ctx['home']
        cp = run_bash(ctx, base + '/bin/loop-journal', ['FIXT-C3', 'T09', text], child_env(ctx, jf))
        res.append((cp, STEP.sub('- TS ', (read_bytes(jf) or b'').decode('utf-8', 'replace'))))
    (a, fa), (b, fb) = res
    ok = a.returncode == b.returncode == int(expect) and a.stdout == b.stdout and fa == fb and 'T09' in fa
    return ok, 'expected=exit %s, stdout and the appended file equal actual=exit %d/%d stdout sha256 %s/%s file sha256 %s/%s' % (
        expect, a.returncode, b.returncode, shafull(a.stdout)[:12], shafull(b.stdout)[:12], sha(fa), sha(fb))


def row_preflight(ctx, rid, expect, arg):
    outs = []
    for tag, base in (('tree', ctx['tree']), ('main', ctx['main'])):
        home = '%s/pf-home-%s-%d' % (ctx['work'], tag, time.time_ns())
        register(ctx['work'], MANIFEST, home)
        os.makedirs(home + '/.loop')
        if arg == 'bad-config':
            # a config file that cannot be decoded: loop_conf raises, and the old command file went on with empty values
            with open(home + '/.loop/config.env', 'wb') as fh:
                fh.write(b'LOOP_HOME=\xff\xfe\n')
        if arg == 'crlf-goal':
            # a current_goal file ending CRLF (the dispatcher writes it in text mode) and a plan fixture holding a Live block
            with open(home + '/.loop/current_goal', 'wb') as fh:
                fh.write(b'FIXT-C3\r\n')
            os.makedirs(home + '/.loop/goals/FIXT-C3')
            with open(home + '/.loop/goals/FIXT-C3/plan.md', 'wb') as fh:
                fh.write(read_bytes(ctx['fix'] + '/pass/plan.md'))
        cp = run_bash(ctx, base + '/bin/loop-preflight', [], child_env(ctx, None, home))
        # raw bytes: nothing is stripped (no carriage return is deleted); only the timestamp, disk and names-age lines are left
        # out and the fixture home path is replaced, at the byte level
        raw = b'\n'.join(x for x in cp.stdout.split(b'\n') if not re.match(rb'(preflight|disk|names) ', x))
        outs.append((cp.returncode, raw.replace(home.encode('utf-8'), b'HOME'), b'UnicodeDecodeError' in cp.stderr))
    (ra, ta, ea), (rb, tb, eb) = outs
    want_err = arg == 'bad-config'
    live = b'\nlive     goal: FIXT-C3 status: RUNNING\n' in ta and b'\nlive     goal: FIXT-C3 status: RUNNING\n' in tb
    ok = ra == rb == int(expect) and ta == tb and b'redactor control fired' in ta and ea == eb == want_err and (live or arg != 'crlf-goal')
    return ok, ('expected=exit %s, the stable lines equal as raw bytes, redactor control fired, traceback kind UnicodeDecodeError on stderr %s, '
                'the live line present on both trees %s actual=exit %d/%d raw bytes %d/%d sha256 %s/%s carriage returns %d/%d control=%s traceback=%s/%s live=%s') % (
        expect, want_err, arg == 'crlf-goal', ra, rb, len(ta), len(tb), shafull(ta)[:12], shafull(tb)[:12], ta.count(b'\r'), tb.count(b'\r'),
        b'redactor control fired' in ta, ea, eb, live)


def row_nopy(ctx, rid, expect, arg):
    """Failure-path change of card C3: LOOP_PY at a missing file. The old preflight command file fell back to python3 or
    python on PATH; the one launcher text does not (exit 3 and its three-line message on stderr), so on wt-main this fails."""
    home = '%s/np-home-%d' % (ctx['work'], time.time_ns())
    register(ctx['work'], MANIFEST, home)
    os.makedirs(home + '/.loop')
    env = make_env(home, {'LOOP_PY': ctx['work'] + '/absent-python'}, DROP)
    cp = run_bash(ctx, ctx['tree'] + '/bin/loop-preflight', [], env)
    msg = b'loop-preflight: LOOP_PY does not resolve to a working python interpreter.' in cp.stderr
    return cp.returncode == int(expect) and msg and not cp.stdout, 'expected=exit %s, the message on stderr, nothing on stdout actual=exit %d, message %s, stdout bytes %d' % (
        expect, cp.returncode, msg, len(cp.stdout))


def row_upgrade(ctx, rid, expect, arg):
    home = '%s/up-home-%d' % (ctx['work'], time.time_ns())
    bk = '%s/up-backup-%d' % (ctx['work'], time.time_ns())
    register(ctx['work'], MANIFEST, home)
    register(ctx['work'], MANIFEST, bk)
    os.makedirs(home)
    base = subprocess.run(['bash', ctx['main'] + '/install.sh'], capture_output=True, text=True, encoding='utf-8', errors='replace',
                          env=make_env(home, {'LOOP_PY': ctx['py']}, DROP), cwd=ctx['work'])
    env = make_env(home, {'LOOP_PY': ctx['py'], 'LOOP_UPGRADE': '1', 'LOOP_BACKUP_DIR': bk}, DROP)
    cp = subprocess.run(['bash', ctx['tree'] + '/install.sh'], capture_output=True, text=True, encoding='utf-8', errors='replace',
                        env=env, cwd=ctx['work'])
    added = set(m[1] for m in ADDED.findall(cp.stdout.replace('\r', '')) if m[0] == 'added')
    want = set('.loop/bin/' + n for n in arg.split())
    got = sorted(w for w in want if w in added)
    ok = base.returncode == 0 and cp.returncode == 0 and len(got) == int(expect)
    return ok, 'expected=exit 0 and %s of %s printed under added actual=base exit %d, upgrade exit %d, %d printed under added (%d added in all), out sha256 %s' % (
        expect, arg, base.returncode, cp.returncode, len(got), len(added), sha(cp.stdout + cp.stderr))


def row_control(ctx, rid, expect, arg):
    src = ctx['tree'] + '/bin/' + arg
    data = read_bytes(src)
    d = ctx['work'] + '/k06c3-control'
    register(ctx['work'], MANIFEST, d)
    os.makedirs(d, exist_ok=True)
    if data is None:
        return False, 'expected=a stub to copy actual=%s absent' % arg
    i = len(data) // 2
    new = data[:i] + bytes([data[i] ^ 1]) + data[i + 1:]
    for name, body in (('copy-equal', data), ('copy-edited', new)):
        with open(d + '/' + name, 'wb') as fh:
            fh.write(body)
    equal_copy = same_bytes(src, d + '/copy-equal')
    edited_equal = same_bytes(src, d + '/copy-edited')
    print('%s control %s expected=equal actual=%s (copy of bin/%s with one byte changed, compared as the pairs row compares)' % (
        'PASS' if edited_equal else 'FAIL', 'c-control-comparison', 'equal' if edited_equal else 'unequal', arg))
    return equal_copy and not edited_equal and len(data) == len(new), 'expected=unmodified copy equal, one byte changed unequal actual=unmodified %s, changed %s' % (
        'equal' if equal_copy else 'unequal', 'equal' if edited_equal else 'unequal')


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    main_tree = os.path.dirname(tree) + '/wt-main'
    if not os.path.isdir(main_tree):
        print(USAGE)
        return 64
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K06-C3/run.py', here + '/run.py'), ('tests/rows/K06-C3/rows.txt', here + '/rows.txt')))
    ctx = {'tree': tree, 'main': main_tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable),
           'rows_file': here + '/rows.txt'}
    ctx['fix'] = write_fixtures(ctx)
    kinds = {'pairs': row_pairs, 'modules': row_modules, 'three': row_three, 'fixture': row_fixture, 'append': row_append,
             'preflight': row_preflight, 'nopy': row_nopy, 'upgrade': row_upgrade, 'control': row_control}
    return tally(load_rows(here + '/rows.txt'), kinds, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
