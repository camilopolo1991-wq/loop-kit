#!/usr/bin/env python3
"""K04-C2 rows runner: install.sh gives the hook command lines of the installed agent files the literal home,
and writes config.env last through a temporary file renamed into place as the final step.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expectations in rows.txt, so a tree
without the change prints FAIL on the rows the change adds), LOOP_ROWS_HOME (used only for the set-or-usage check; every row
targets a fresh home under LOOP_WORK), LOOP_WORK (a work folder, created when absent), LOOP_PY (the interpreter the install
is given), LOOP_NAMES_FILE (passed through; row r4 reads its one word at run time and sets it as LOOP_OWNER for that one install).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Every spawned process gets HOME and USERPROFILE at the home the row targets, LOOP_HOME at that home plus /.loop, and
PYTHONDONTWRITEBYTECODE=1. The install runs as bash <tree>/install.sh with no positional argument. Prints PASS or FAIL per
row with expected and actual; a sha256 stands in for any text that could hold a home path. Nothing is spawned in the
background, nothing is killed, no timeout is set.
"""
import hashlib
import os
import subprocess
import sys
import time

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'
AGENTS = ['loop-leader', 'loop-scout', 'loop-writer', 'loop-reviewer', 'loop-auditor']
HOMEVAR = b'$' + b'HOME'


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


def make_env(home, py):
    env = dict(os.environ)
    env['HOME'] = home
    env['USERPROFILE'] = home
    env['LOOP_HOME'] = home + '/.loop'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['LOOP_PY'] = py
    env.pop('LOOP_WITH_TESTS', None)
    env.pop('LOOP_OWNER', None)
    env.pop('LOOP_GOAL', None)
    env.pop('JOURNAL_FILE', None)
    return env


def fresh_home(work, tag):
    home = '%s/home-%s-%d' % (work, tag, time.time_ns())
    os.makedirs(home)
    return home


def install(script, home, work, py, owner=None):
    env = make_env(home, py)
    if owner:
        env['LOOP_OWNER'] = owner
    return subprocess.run(['bash', script], capture_output=True, text=True, env=env, cwd=work)


def read_bytes(p):
    try:
        with open(p, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def row_hooks(tree, work, py, state):
    home = fresh_home(work, 'r1')
    state['home'] = home
    cp = install(tree + '/install.sh', home, work, py)
    var_lines = lit_lines = 0
    missing = 0
    held = []
    for a in AGENTS:
        data = read_bytes('%s/.claude/agents/%s.md' % (home, a))
        if data is None:
            missing += 1
            continue
        for ln in data.split(b'\n'):
            if b'command:' not in ln:
                continue
            if HOMEVAR in ln:
                var_lines += 1
            if home.encode() in ln:
                lit_lines += 1
            held.append(ln)
    ok = cp.returncode == 0 and missing == 0 and var_lines == 0 and lit_lines >= 1
    state['installed'] = cp.returncode == 0 and os.path.exists(home + '/.loop/config.env')
    return ok, 'expected=exit 0, home_var_hook_lines=0, literal_home_hook_lines>=1 actual=exit %d missing_agents=%d home_var_hook_lines=%d literal_home_hook_lines=%d hook_lines_sha=%s out_sha=%s' % (
        cp.returncode, missing, var_lines, lit_lines, sha(b'\n'.join(held)), sha(cp.stdout + cp.stderr))


def row_standin(tree, work, py):
    with open(tree + '/install.sh', encoding='utf-8', newline='') as fh:
        lines = fh.read().split('\n')
    out = []
    renames = srcs = 0
    for ln in lines:
        s = ln.strip()
        if s.startswith('SRC="$(cd'):
            out.append('SRC="%s"' % tree)
            srcs += 1
        elif s.startswith('mv ') and 'CONFIG' in s:
            out.append('exit 0')
            renames += 1
        else:
            out.append(ln)
    if srcs != 1:
        return False, 'expected=exit 0, success line, config.env absent actual=no stand-in (rename_lines=%d src_lines=%d)' % (renames, srcs)
    # a script with no rename line is still run (with only its source folder pinned), and then measures config.env present
    path = '%s/standin-%d.sh' % (work, time.time_ns())
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write('\n'.join(out))
    home = fresh_home(work, 'r2')
    cp = install(path, home, work, py)
    success = 'installed. config.env written' in cp.stdout
    present = os.path.exists(home + '/.loop/config.env')
    ok = cp.returncode == 0 and success and not present
    return ok, 'expected=exit 0, success_line=yes, config_env=absent actual=exit %d success_line=%s config_env=%s rename_lines=%d out_sha=%s' % (
        cp.returncode, 'yes' if success else 'no', 'present' if present else 'absent', renames, sha(cp.stdout + cp.stderr))


def row_owner(tree, work, py, names_file):
    word = ''
    if names_file:
        raw = read_bytes(names_file)
        toks = (raw or b'').decode('utf-8', 'replace').split()
        if len(toks) == 1:
            word = toks[0]
    if not word:
        return False, 'expected=exit 0, no OWNER_HANDLE token left actual=no single fixture word in LOOP_NAMES_FILE'
    src = read_bytes(tree + '/agents/loop-leader.md') or b''
    src_tokens = src.count(b'OWNER_HANDLE')
    home = fresh_home(work, 'r4')
    cp = install(tree + '/install.sh', home, work, py, owner=word)
    inst = read_bytes(home + '/.claude/agents/loop-leader.md')
    left = -1 if inst is None else inst.count(b'OWNER_HANDLE')
    filled = inst is not None and word.encode() in inst
    ok = cp.returncode == 0 and src_tokens >= 1 and left == 0 and filled
    return ok, 'expected=exit 0, source_tokens>=1, installed_tokens_left=0, value_present=yes actual=exit %d source_tokens=%d installed_tokens_left=%d value_present=%s file_sha=%s out_sha=%s' % (
        cp.returncode, src_tokens, left, 'yes' if filled else 'no', sha(inst or b''), sha(cp.stdout + cp.stderr))


def run_phrase(tree, expect, arg):
    rel, phrase = arg.split('|', 1)
    data = read_bytes(tree + '/' + rel)
    if data is None:
        return False, 'expected=%s actual=unreadable' % expect
    actual = 'found' if phrase.encode('utf-8') in data else 'absent'
    return actual == expect, 'expected=%s actual=%s file_sha=%s' % (expect, actual, sha(data))


def row_reinstall(tree, work, py, state):
    home = state.get('home')
    if not home or not state.get('installed'):
        return False, 'expected=exit 4, config.env bytes unchanged actual=no installed home from r1'
    cfg = home + '/.loop/config.env'
    before = read_bytes(cfg)
    cp = install(tree + '/install.sh', home, work, py)
    after = read_bytes(cfg)
    same = before is not None and before == after
    ok = cp.returncode == 4 and same
    return ok, 'expected=exit 4, config.env bytes unchanged actual=exit %d config_env_unchanged=%s config_sha=%s out_sha=%s' % (
        cp.returncode, 'yes' if same else 'no', sha(after or b''), sha(cp.stdout + cp.stderr))


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
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    state = {}
    passed = failed = 0
    for rid, kind, expect, _what in rows:
        if kind == 'hooks':
            ok, detail = row_hooks(tree, work, py, state)
        elif kind == 'standin':
            ok, detail = row_standin(tree, work, py)
        elif kind == 'reinstall':
            ok, detail = row_reinstall(tree, work, py, state)
        elif kind == 'owner':
            ok, detail = row_owner(tree, work, py, os.environ.get('LOOP_NAMES_FILE'))
        elif kind == 'phrase':
            ok, detail = run_phrase(tree, expect, _what)
        else:
            ok, detail = False, 'unknown kind ' + kind
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
