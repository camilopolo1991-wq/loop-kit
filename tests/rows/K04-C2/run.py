#!/usr/bin/env python3
"""K04-C2 rows runner: install.sh gives the hook command lines of the installed agent files the literal home,
and writes config.env last through a temporary file renamed into place as the final step.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expectations in rows.txt, so a tree
without the change prints FAIL on the rows the change adds), LOOP_ROWS_HOME (used only for the set-or-usage check; every row
targets a fresh home under LOOP_WORK), LOOP_WORK (a work folder, created when absent), LOOP_PY (the interpreter the install
is given), LOOP_NAMES_FILE (passed through; row r4 reads its one word at run time and sets it as LOOP_OWNER for that one install).
Every spawned process gets HOME and USERPROFILE at the home the row targets, LOOP_HOME at that home plus /.loop, and
PYTHONDONTWRITEBYTECODE=1. The install runs as bash <tree>/install.sh with no positional argument. Prints PASS or FAIL per
row with expected and actual; a sha256 stands in for any text that could hold a home path. Nothing is spawned in the
background, nothing is killed, no timeout is set.
"""
import os
import subprocess
import sys
import time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import env_dirs, fresh_home, fwd, load_rows, make_env, read_bytes, run_phrase, sha, tally

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'
AGENTS = ['loop-leader', 'loop-scout', 'loop-writer', 'loop-reviewer', 'loop-auditor']
HOMEVAR = b'$' + b'HOME'


def install(script, home, work, py, owner=None):
    env = make_env(home, {'LOOP_PY': py}, ('LOOP_WITH_TESTS', 'LOOP_OWNER', 'LOOP_GOAL', 'JOURNAL_FILE'))
    if owner:
        env['LOOP_OWNER'] = owner
    return subprocess.run(['bash', script], capture_output=True, text=True, env=env, cwd=work)


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
    tree, home, work = env_dirs(USAGE)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    state = {}
    return tally(rows, {
        'hooks': lambda rid, expect, arg: row_hooks(tree, work, py, state),
        'standin': lambda rid, expect, arg: row_standin(tree, work, py),
        'reinstall': lambda rid, expect, arg: row_reinstall(tree, work, py, state),
        'owner': lambda rid, expect, arg: row_owner(tree, work, py, os.environ.get('LOOP_NAMES_FILE')),
        'phrase': lambda rid, expect, arg: run_phrase(tree, expect, arg),
    })


if __name__ == '__main__':
    sys.exit(main())
