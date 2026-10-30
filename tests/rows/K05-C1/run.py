#!/usr/bin/env python3
"""K05-C1 rows runner: install.sh upgrades a home it already installed (LOOP_UPGRADE=1, LOOP_BACKUP_DIR).

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expectations in rows.txt, so a tree
without the upgrade mode prints FAIL on the rows it adds), LOOP_ROWS_HOME (used only for the set-or-usage check; every row
targets a fresh home under LOOP_WORK), LOOP_WORK (a work folder, created when absent), LOOP_PY (the interpreter the
installs are given), LOOP_NAMES_FILE (passed through untouched).
Exits 64 with a usage line when a positional argument is given, when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset, or
when the base bundle, the sibling folder wt-main of LOOP_TREE, is absent.
The base bundle is always wt-main's install.sh: the fixture home is installed from it, then the tree's install.sh runs in the
upgrade form against that home. Every spawned process gets HOME and USERPROFILE at the home the row targets, LOOP_HOME at
that home plus /.loop, and PYTHONDONTWRITEBYTECODE=1. Every install runs as bash <tree>/install.sh in the environment form
with no positional argument. The runner writes its fixtures under LOOP_WORK and, at its start, removes only what its own
manifest file (k05c1-manifest.txt in LOOP_WORK) lists from an earlier run. Prints PASS or FAIL per row with expected and
actual; a sha256 stands in for any text that could hold a home path. Nothing is spawned in the background, nothing is
killed, no timeout is set.
"""
import hashlib
import os
import re
import subprocess
import sys
import time

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'
WORD = 'Omicronfixture'
WORD2 = 'Sigmafixture'
DIRS = [('agents', '.claude/agents'), ('skills', '.claude/skills'), ('bin', '.loop/bin'), ('templates', '.loop/templates')]
HOOKS = ('hooks', '.claude/hooks')
ROOTS = ['.claude/agents', '.claude/skills', '.claude/hooks', '.loop/bin', '.loop/templates']
LEADER = '.claude/agents/loop-leader.md'
CNT = re.compile(r'^upgrade: replaced (\d+), added (\d+), unchanged (\d+), hooks skipped (\d+)$', re.M)
LINE = re.compile(r'^(replaced|added) (\S+) sha256 before (\S+) after (\S+)$', re.M)
MANIFEST = 'k05c1-manifest.txt'


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def sha(s):
    if isinstance(s, str):
        s = s.encode('utf-8', 'replace')
    return hashlib.sha256(s).hexdigest()[:12]


def shafull(b):
    return hashlib.sha256(b).hexdigest()


def clean(s):
    return s.replace('\r', '')


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


def write_bytes(p, b):
    with open(p, 'wb') as fh:
        fh.write(b)


def register(ctx, path):
    with open(ctx['work'] + '/' + MANIFEST, 'a', encoding='utf-8') as fh:
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
        if p and fwd(p).startswith(work + '/') and fwd(p) != work + '/' + MANIFEST:
            remove_path(p)
            n += 1
    os.remove(mf)
    return n


def make_env(home, py):
    env = dict(os.environ)
    env['HOME'] = home
    env['USERPROFILE'] = home
    env['LOOP_HOME'] = home + '/.loop'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['LOOP_PY'] = py
    for k in ('LOOP_WITH_TESTS', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS',
              'LOOP_BACKUP_DIR', 'LOOP_GOAL', 'JOURNAL_FILE'):
        env.pop(k, None)
    return env


def fresh_path(ctx, kind, tag):
    p = '%s/%s-%s-%d' % (ctx['work'], kind, tag, time.time_ns())
    register(ctx, p)
    return p


def fresh_home(ctx, tag):
    home = fresh_path(ctx, 'home', tag)
    os.makedirs(home)
    return home


def run_install(ctx, script, home, extra=None, drop=()):
    env = make_env(home, ctx['py'])
    for k in drop:
        env.pop(k, None)
    if extra:
        env.update(extra)
    return subprocess.run(['bash', script], capture_output=True, text=True, encoding='utf-8', errors='replace',
                          env=env, cwd=ctx['work'])


def run_upgrade(ctx, home, backup, extra=None):
    e = {'LOOP_UPGRADE': '1'}
    if backup is not None:
        e['LOOP_BACKUP_DIR'] = backup
    if extra:
        e.update(extra)
    return run_install(ctx, ctx['tree'] + '/install.sh', home, e)


def tree_files(base, sub):
    root = base + '/' + sub
    out = []
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f.endswith('.pyc'):
                continue
            out.append(fwd(os.path.join(r, f))[len(root) + 1:])
    return sorted(out)


def collect(home):
    got = {}
    for sub in ROOTS:
        root = home + '/' + sub
        for r, dirs, files in os.walk(root):
            for f in files:
                p = fwd(os.path.join(r, f))
                got[p[len(home) + 1:]] = read_bytes(p)
    return got


def whole_home(home):
    got = {}
    for r, dirs, files in os.walk(home):
        for f in files:
            p = fwd(os.path.join(r, f))
            got[p[len(home) + 1:]] = shafull(read_bytes(p) or b'')
    return got


def fill_expected(rel, data, py, homelit, owner):
    new = data.replace(b'@LOOP_PYTHON@', py.encode())
    if rel.startswith('.claude/agents/'):
        out = []
        front = 0
        for ln in new.split(b'\n'):
            if ln.strip(b'\r') == b'---':
                front += 1
            if front == 1 and ln.lstrip().startswith(b'command:') and b'$HOME' in ln:
                ln = ln.replace(b'$HOME', homelit.encode())
            out.append(ln)
        new = b'\n'.join(out)
    scope, word = owner
    if scope == 'all' or (scope == 'leader' and rel == LEADER):
        new = new.replace(b'OWNER_HANDLE', word.encode())
    return new


def expected_for(ctx, st, with_hooks, owner):
    exp = {}
    for s, t in DIRS + ([HOOKS] if with_hooks else []):
        for f in tree_files(ctx['tree'], s):
            exp[t + '/' + f] = fill_expected(t + '/' + f, read_bytes(ctx['tree'] + '/' + s + '/' + f), ctx['py'], st['home'], owner)
    return exp


def classify(st, exp):
    rep, add, unch = [], [], 0
    for rel in sorted(exp):
        cur = st['pre'].get(rel)
        if cur is None:
            add.append(rel)
        elif cur != exp[rel]:
            rep.append(rel)
        else:
            unch += 1
    return rep, add, unch


def setup(ctx, tag):
    """A home installed from the base bundle, then edited so an upgrade has work to do."""
    home = fresh_home(ctx, tag)
    st = {'home': home, 'ok': False}
    cp = run_install(ctx, ctx['base'] + '/install.sh', home)
    st['base_exit'] = cp.returncode
    if cp.returncode != 0:
        return st
    leader = read_bytes(home + '/' + LEADER) or b''
    st['leader_tokens'] = leader.count(b'OWNER_HANDLE')
    write_bytes(home + '/' + LEADER, leader.replace(b'OWNER_HANDLE', WORD.encode()))
    write_bytes(home + '/.loop/names.txt', b'fixture-name-one\nfixture-name-two\n')
    bins = tree_files(ctx['base_dir'], 'bin')
    tpls = tree_files(ctx['base_dir'], 'templates')
    hooks = tree_files(ctx['base_dir'], 'hooks')
    if not bins or not tpls or not hooks:
        return st
    b0 = home + '/.loop/bin/' + bins[0]
    write_bytes(b0, (read_bytes(b0) or b'') + b'\n# fixture edit\n')
    os.remove(home + '/.loop/templates/' + tpls[-1])
    h0 = home + '/.claude/hooks/' + hooks[0]
    write_bytes(h0, (read_bytes(h0) or b'') + b'\n# fixture edit\n')
    st['edited_hook'] = '.claude/hooks/' + hooks[0]
    st['pre'] = collect(home)
    st['cfg'] = read_bytes(home + '/.loop/config.env')
    st['names'] = read_bytes(home + '/.loop/names.txt')
    st['ok'] = st['cfg'] is not None
    return st


def counts(out):
    m = CNT.search(out)
    return tuple(int(x) for x in m.groups()) if m else None


def lines_of(out):
    return set(LINE.findall(out))


def backup_files(bk):
    got = {}
    if os.path.isdir(bk):
        for r, dirs, files in os.walk(bk):
            for f in files:
                p = fwd(os.path.join(r, f))
                got[p[len(bk) + 1:]] = shafull(read_bytes(p) or b'')
    return got


def no_state(what):
    return False, 'expected=%s actual=no fixture home from r1' % what


def row_upgrade(ctx):
    st = setup(ctx, 'r1')
    ctx['h1'] = st
    if not st['ok']:
        return False, 'expected=fixture home ready actual=base_exit=%s' % st.get('base_exit')
    exp = expected_for(ctx, st, False, ('leader', WORD))
    rep, add, unch = classify(st, exp)
    nhooks = len(tree_files(ctx['tree'], 'hooks'))
    bk = fresh_path(ctx, 'bk', 'r1')
    st['bk'] = bk
    st['exp'] = exp
    st['rep'] = rep
    cp = run_upgrade(ctx, st['home'], bk)
    st['up'] = cp
    out = clean(cp.stdout)
    got_c = counts(out)
    want_c = (len(rep), len(add), unch, nhooks)
    want_l = set()
    for rel in rep:
        want_l.add(('replaced', rel, shafull(st['pre'][rel]), shafull(exp[rel])))
    for rel in add:
        want_l.add(('added', rel, '-', shafull(exp[rel])))
    got_l = lines_of(out)
    ok = cp.returncode == 0 and got_c == want_c and got_l == want_l and leader_ok(st) and len(rep) >= 1 and len(add) >= 1
    return ok, 'expected=exit 0, counts(replaced,added,unchanged,hooks_skipped)=%s, file_lines=%d actual=exit %d counts=%s file_lines=%d lines_match=%s leader_tokens_in_base=%s out_sha=%s' % (
        want_c, len(want_l), cp.returncode, got_c, len(got_l), 'yes' if got_l == want_l else 'no', st['leader_tokens'], sha(cp.stdout + cp.stderr))


def leader_ok(st):
    return st.get('leader_tokens', 0) >= 1


def row_config(ctx):
    st = ctx.get('h1')
    if not st or not st.get('ok') or 'up' not in st:
        return no_state('config.env and names unchanged')
    cfg = read_bytes(st['home'] + '/.loop/config.env')
    names = read_bytes(st['home'] + '/.loop/names.txt')
    ok = st['up'].returncode == 0 and cfg == st['cfg'] and names == st['names']
    return ok, 'expected=exit 0, config.env and names list unchanged actual=exit %d config_before=%s config_after=%s names_before=%s names_after=%s' % (
        st['up'].returncode, sha(st['cfg']), sha(cfg or b''), sha(st['names']), sha(names or b''))


def row_bytes(ctx):
    st = ctx.get('h1')
    if not st or not st.get('ok') or 'up' not in st:
        return no_state('every kit file equals the tree text with fills')
    bad = missing = 0
    for rel, want in st['exp'].items():
        got = read_bytes(st['home'] + '/' + rel)
        if got is None:
            missing += 1
        elif got != want:
            bad += 1
    leader = read_bytes(st['home'] + '/' + LEADER) or b''
    kept = WORD.encode() in leader and b'OWNER_HANDLE' not in leader
    ok = st['up'].returncode == 0 and bad == 0 and missing == 0 and kept and leader_ok(st)
    return ok, 'expected=exit 0, files=%d all equal, handle kept actual=exit %d different=%d missing=%d handle_kept=%s leader_sha=%s' % (
        len(st['exp']), st['up'].returncode, bad, missing, 'yes' if kept else 'no', sha(leader))


def row_backup(ctx):
    st = ctx.get('h1')
    if not st or not st.get('ok') or 'up' not in st:
        return no_state('backup holds the replaced files')
    want = {rel: shafull(st['pre'][rel]) for rel in st['rep']}
    got = backup_files(st['bk'])
    ok = st['up'].returncode == 0 and len(want) >= 1 and got == want
    return ok, 'expected=exit 0, backup files=%d each with its before hash actual=exit %d backup_files=%d same_set_and_hashes=%s' % (
        len(want), st['up'].returncode, len(got), 'yes' if got == want else 'no')


def row_hooks(ctx):
    st = ctx.get('h1')
    if not st or not st.get('ok') or 'up' not in st:
        return no_state('hooks files unchanged')
    now = collect(st['home'])
    changed = sum(1 for rel, b in st['pre'].items() if rel.startswith('.claude/hooks/') and now.get(rel) != b)
    nh = sum(1 for rel in st['pre'] if rel.startswith('.claude/hooks/'))
    c = counts(clean(st['up'].stdout))
    ok = st['up'].returncode == 0 and changed == 0 and nh >= 1 and c is not None and c[3] == nh
    return ok, 'expected=exit 0, hooks files=%d unchanged, hooks skipped=%d actual=exit %d changed=%d counts=%s' % (
        nh, nh, st['up'].returncode, changed, c)


def row_again(ctx):
    st = ctx.get('h1')
    if not st or not st.get('ok') or 'up' not in st:
        return no_state('second upgrade replaces 0 and adds 0')
    bk = fresh_path(ctx, 'bk', 'r6')
    cp = run_upgrade(ctx, st['home'], bk)
    out = clean(cp.stdout)
    c = counts(out)
    ok = cp.returncode == 0 and c is not None and c[0] == 0 and c[1] == 0 and not lines_of(out)
    return ok, 'expected=exit 0, replaced 0, added 0, no file lines actual=exit %d counts=%s file_lines=%d out_sha=%s' % (
        cp.returncode, c, len(lines_of(out)), sha(cp.stdout + cp.stderr))


def row_hooksflag(ctx):
    st = setup(ctx, 'r7')
    if not st['ok']:
        return False, 'expected=fixture home ready actual=base_exit=%s' % st.get('base_exit')
    exp = expected_for(ctx, st, True, ('leader', WORD))
    rep, add, unch = classify(st, exp)
    bk = fresh_path(ctx, 'bk', 'r7')
    cp = run_upgrade(ctx, st['home'], bk, {'LOOP_UPGRADE_HOOKS': '1'})
    c = counts(clean(cp.stdout))
    bad = sum(1 for rel, want in exp.items() if read_bytes(st['home'] + '/' + rel) != want)
    got = backup_files(bk)
    want_b = {rel: shafull(st['pre'][rel]) for rel in rep}
    edited = st['edited_hook']
    ok = (cp.returncode == 0 and bad == 0 and c is not None and c[3] == 0 and edited in rep
          and got == want_b and got.get(edited) == shafull(st['pre'][edited]))
    return ok, 'expected=exit 0, hooks skipped 0, all %d files equal, edited hooks file replaced and backed up actual=exit %d counts=%s different=%d edited_in_backup=%s backup_set_matches=%s' % (
        len(exp), cp.returncode, c, bad, 'yes' if edited in got else 'no', 'yes' if got == want_b else 'no')


def row_noconfig(ctx):
    home = fresh_home(ctx, 'r8')
    bk = fresh_path(ctx, 'bk', 'r8')
    cp = run_upgrade(ctx, home, bk)
    text = clean(cp.stdout + cp.stderr)
    said = 'nothing to upgrade' in text
    empty = os.listdir(home) == [] and not os.path.exists(bk)
    ok = cp.returncode == 5 and said and empty
    return ok, 'expected=exit 5, line says nothing to upgrade, nothing written actual=exit %d says_nothing_to_upgrade=%s nothing_written=%s out_sha=%s' % (
        cp.returncode, 'yes' if said else 'no', 'yes' if empty else 'no', sha(cp.stdout + cp.stderr))


def row_plain(ctx):
    home = fresh_home(ctx, 'r9')
    first = run_install(ctx, ctx['tree'] + '/install.sh', home)
    cfg = read_bytes(home + '/.loop/config.env')
    second = run_install(ctx, ctx['tree'] + '/install.sh', home)
    after = read_bytes(home + '/.loop/config.env')
    ok = first.returncode == 0 and cfg is not None and second.returncode == 4 and cfg == after
    return ok, 'expected=first exit 0, second exit 4, config.env unchanged actual=first exit %d second exit %d config_unchanged=%s out_sha=%s' % (
        first.returncode, second.returncode, 'yes' if cfg == after else 'no', sha(second.stdout + second.stderr))


def refused(ctx, tag, backup, prep=None):
    st = setup(ctx, tag)
    if not st['ok']:
        return False, 'expected=fixture home ready actual=base_exit=%s' % st.get('base_exit')
    if prep:
        prep(backup)
    before = whole_home(st['home'])
    cp = run_upgrade(ctx, st['home'], backup)
    after = whole_home(st['home'])
    text = clean(cp.stdout + cp.stderr)
    ok = cp.returncode != 0 and 'LOOP_BACKUP_DIR' in text and before == after
    return ok, st, cp, text, before == after


def row_nobackup(ctx):
    r = refused(ctx, 'r10', None)
    if len(r) == 2:
        return r
    ok, st, cp, text, same = r
    return ok, 'expected=non-zero exit, line names LOOP_BACKUP_DIR, home unchanged actual=exit %d names_it=%s home_unchanged=%s out_sha=%s' % (
        cp.returncode, 'yes' if 'LOOP_BACKUP_DIR' in text else 'no', 'yes' if same else 'no', sha(cp.stdout + cp.stderr))


def row_fullbackup(ctx):
    bk = fresh_path(ctx, 'bk', 'r11')

    def prep(p):
        os.makedirs(p)
        write_bytes(p + '/keep.txt', b'fixture keep\n')
    r = refused(ctx, 'r11', bk, prep)
    if len(r) == 2:
        return r
    ok, st, cp, text, same = r
    held = backup_files(bk)
    intact = held == {'keep.txt': shafull(b'fixture keep\n')}
    return ok and intact, 'expected=non-zero exit, line names LOOP_BACKUP_DIR, home unchanged, folder content untouched actual=exit %d names_it=%s home_unchanged=%s folder_untouched=%s out_sha=%s' % (
        cp.returncode, 'yes' if 'LOOP_BACKUP_DIR' in text else 'no', 'yes' if same else 'no', 'yes' if intact else 'no', sha(cp.stdout + cp.stderr))


def row_handle(ctx):
    st = setup(ctx, 'r12')
    if not st['ok']:
        return False, 'expected=fixture home ready actual=base_exit=%s' % st.get('base_exit')
    exp = expected_for(ctx, st, False, ('all', WORD2))
    bk = fresh_path(ctx, 'bk', 'r12')
    cp = run_upgrade(ctx, st['home'], bk, {'LOOP_OWNER_HANDLE': WORD2})
    bad = sum(1 for rel, want in exp.items() if read_bytes(st['home'] + '/' + rel) != want)
    leader = read_bytes(st['home'] + '/' + LEADER) or b''
    wins = WORD2.encode() in leader and WORD.encode() not in leader
    ok = cp.returncode == 0 and bad == 0 and wins and leader_ok(st)
    return ok, 'expected=exit 0, %d files equal, the env value in the leader file and the old handle gone actual=exit %d different=%d env_value_wins=%s leader_sha=%s' % (
        len(exp), cp.returncode, bad, 'yes' if wins else 'no', sha(leader))


KINDS = {
    'upgrade': row_upgrade, 'config': row_config, 'bytes': row_bytes, 'backup': row_backup, 'hooks': row_hooks,
    'again': row_again, 'hooksflag': row_hooksflag, 'noconfig': row_noconfig, 'plain': row_plain,
    'nobackup': row_nobackup, 'fullbackup': row_fullbackup, 'handle': row_handle,
}


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
    base_dir = fwd(os.path.join(os.path.dirname(tree), 'wt-main'))
    if not os.path.isfile(base_dir + '/install.sh'):
        print('the base bundle (the sibling folder wt-main of the tree) is absent')
        print(USAGE)
        return 64
    os.makedirs(work, exist_ok=True)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    cleaned = clean_earlier(work)
    print('cleaned %d path(s) listed by an earlier run' % cleaned)
    ctx = {'tree': tree, 'work': work, 'py': py, 'base_dir': base_dir, 'base': base_dir}
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, kind, _expect, _what in rows:
        fn = KINDS.get(kind)
        if fn is None:
            ok, detail = False, 'unknown kind ' + kind
        else:
            try:
                ok, detail = fn(ctx)
            except Exception as exc:
                ok, detail = False, 'expected=row runs actual=error %s' % type(exc).__name__
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
