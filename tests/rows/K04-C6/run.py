#!/usr/bin/env python3
"""K04-C6 rows runner: bin/loop-dispatch, the dispatcher in the kit.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expected values in rows.txt,
so a tree without the dispatcher prints FAIL on the rows it adds), LOOP_ROWS_HOME (the home every spawned process
gets as HOME and USERPROFILE; LOOP_HOME is that home plus /.loop), LOOP_WORK (a work folder, created when absent),
LOOP_PY (the interpreter that runs the dispatcher; default is the interpreter running this file),
LOOP_NAMES_FILE (passed through untouched).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
At run time the runner writes a fixture goal under LOOP_ROWS_HOME/.loop/goals/ whose GOAL carries "wall time 400 min",
and a stand-in binary under LOOP_WORK that exits 3 at once. Every dispatcher row sets LOOP_CLAUDE_BIN to the stand-in,
so the real claude binary is never launched. Every spawned process gets HOME, USERPROFILE and LOOP_HOME at a home and
PYTHONDONTWRITEBYTECODE=1. r1 and r2 (pure dry-runs) use the shared rows home and remove their fixture goal at the end of the
row; at its start the runner removes exactly three paths a first pass left there (current_goal, dispatch, the fixture goal).
r3, r6 and r7 each use a throwaway home of their own under LOOP_WORK, never the shared one. MAX_LEADERS is set high so a leader running elsewhere on the machine cannot refuse a
fixture dispatch. Prints PASS or FAIL per row with expected and actual; a sha256 stands in for any text that could
hold a home path. Nothing is spawned in the background by this runner, nothing is killed, no timeout is set.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

GOAL = 'ZZFIX-06'
USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] '
         '[LOOP_NAMES_FILE=<file>] python run.py (no positional argument)')
FIXTURE_GOAL = ('# ZZFIX-06: fixture goal for the K04-C6 rows\n\n'
                'Budget: writes 5 | external calls 0 | model calls 0 | wall time 400 min\n\n'
                'Acceptance criteria:\n1. This file exists so the dispatcher has a goal to read.\n'
                '2. It is long enough to pass the stub check, which refuses a GOAL under 200 bytes.\n')
NOWALL_GOAL = ('# ZZFIX-06: fixture goal with no wall time line\n\n'
               'Budget: writes 5 | external calls 0 | model calls 0\n\n'
               'Acceptance criteria:\n1. This file exists so the dispatcher has a goal to read.\n'
               '2. It is long enough to pass the stub check, which refuses a GOAL under 200 bytes.\n')
STANDIN = '#!/bin/sh\nexit 3\n'
DRIVE_RE = re.compile(rb'(?<![A-Za-z0-9])[A-Za-z]:[\\/]')
HOOKLINE_RE = re.compile(rb'(?i)(hook|command:)')


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
            rows.append([x.strip() for x in line.split(' :: ', 2)])
    return rows


def make_env(home, standin):
    env = dict(os.environ)
    env['HOME'] = home
    env['USERPROFILE'] = home
    env['LOOP_HOME'] = home + '/.loop'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['LOOP_CLAUDE_BIN'] = standin
    env['MAX_LEADERS'] = '99'
    for k in ('JOURNAL_FILE', 'LOOP_GOAL', 'CLAUDE_BIN'):
        env.pop(k, None)
    return env


def write_goal(home, text):
    gdir = home + '/.loop/goals/' + GOAL
    os.makedirs(gdir, exist_ok=True)
    with open(gdir + '/GOAL.md', 'wb') as fh:
        fh.write(text.encode('utf-8'))


def write_standin(work):
    standin = work + '/standin-claude'
    with open(standin, 'wb') as fh:
        fh.write(STANDIN.encode('utf-8'))
    os.chmod(standin, 0o755)
    return standin


def throwaway(work, name):
    """A fresh home of this row's own under LOOP_WORK (removed first when a past run left one)."""
    h = work + '/' + name
    if os.path.isdir(h):
        shutil.rmtree(h)
    os.makedirs(h + '/.loop', exist_ok=True)
    return h


def clean_start(home):
    """Remove, when present, exactly the three paths an earlier pass left under the shared rows home."""
    p = home + '/.loop/current_goal'
    if os.path.isfile(p):
        os.remove(p)
    for d in (home + '/.loop/dispatch', home + '/.loop/goals/' + GOAL):
        if os.path.isdir(d):
            shutil.rmtree(d)


def run_tool(py, tool, env, args):
    cp = subprocess.run([py, tool] + args, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
    return cp.returncode, cp.stdout + cp.stderr


def dry_timeout(py, tool, env, extra):
    if not os.path.isfile(tool):
        return 'no-tool'
    rc, out = run_tool(py, tool, env, [GOAL, '--dry-run'] + extra)
    m = re.search(r'(?i)dry run: .*?\btimeout(?:\.exe)? (\d+) ', out)
    return 'timeout=%s rc=%d' % (m.group(1) if m else 'none', rc), sha(out)


def row_r3(py, tool, env):
    if not os.path.isfile(tool):
        return 'no-tool', sha('')
    rc, out = run_tool(py, tool, env, [GOAL])
    m = re.search(r'launched pid \d+, log (.*?), exit code file ', out)
    if not m:
        return 'dispatcher=%d rc_file=none log=no' % rc, sha(out)
    logp = m.group(1)
    rcp = logp + '.rc'
    rc_text = open(rcp, encoding='utf-8').read().strip() if os.path.isfile(rcp) else 'none'
    return 'dispatcher=%d rc_file=%s log=%s' % (rc, rc_text, 'yes' if os.path.isfile(logp) else 'no'), sha(out)


def row_r7(py, tool, work, standin):
    if not os.path.isfile(tool):
        return 'no-tool', sha('')
    h = throwaway(work, 'home-r7')
    write_goal(h, FIXTURE_GOAL)
    rc, out = run_tool(py, tool, make_env(h, standin), [GOAL, '--dry-run'])
    lines = out.splitlines()
    off = 'recall receipt gate OFF' in out and 'goal lint gate OFF' in out
    ok_line = any(ln.startswith('ok') and 'recall receipt' in ln for ln in lines)
    # control: the same dry-run in a home that holds a matching receipt must print an ok line for it
    hc = throwaway(work, 'home-r7c')
    write_goal(hc, FIXTURE_GOAL)
    os.makedirs(hc + '/.loop/cache', exist_ok=True)
    digest = hashlib.sha256(FIXTURE_GOAL.encode('utf-8')).hexdigest()
    with open(hc + '/.loop/cache/recall-receipts.json', 'w', encoding='utf-8') as fh:
        json.dump({GOAL: {'sha256': digest, 'rc': 0}}, fh)
    _, outc = run_tool(py, tool, make_env(hc, standin), [GOAL, '--dry-run'])
    ctl = any(ln.startswith('ok') and 'recall receipt' in ln for ln in outc.splitlines()) and 'recall receipt gate OFF' not in outc
    return ('rc=%d gate-off=%s ok-receipt-line=%s control-ok-line=%s'
            % (rc, 'yes' if off else 'no', 'yes' if ok_line else 'no', 'yes' if ctl else 'no')), sha(out)


def bad_bytes(data):
    """Drive-letter paths, and an at-sign on a line that mentions a hook or a command: line."""
    if DRIVE_RE.search(data):
        return True
    return any(b'@' in ln and HOOKLINE_RE.search(ln) for ln in data.splitlines())


def row_r5(tree):
    files = [tree + '/bin/loop-dispatch', tree + '/bin/loop_dispatch.py']
    if not all(os.path.isfile(f) for f in files):
        return 'no-tool', sha('')
    drive_bad = b'path ' + bytes([67]) + b':/x/y\n'
    at_bad = b'  command: "run ' + bytes([64]) + b'tool"\n'
    fired = bad_bytes(drive_bad) and bad_bytes(at_bad) and not bad_bytes(b'plain line\n')
    held = [bad_bytes(open(f, 'rb').read()) for f in files]
    return ('clean' if not any(held) else 'dirty') + ' control=' + ('fired' if fired else 'silent'), sha(repr(held))


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
    tree, home, work = fwd(tree_e), fwd(home_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    standin = write_standin(work)
    clean_start(home)
    env = make_env(home, standin)
    tool = tree + '/bin/loop_dispatch.py'
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, expect, _what in rows:
        if rid in ('r1', 'r2'):
            # pure dry-runs: the shared rows home, with the fixture goal removed at the end of the row
            if not os.path.isfile(tool):
                actual, why = 'no-tool', sha('')
            else:
                goals_dir = home + '/.loop/goals'
                goals_existed = os.path.isdir(goals_dir)
                write_goal(home, FIXTURE_GOAL)
                try:
                    actual, why = dry_timeout(py, tool, env, [] if rid == 'r1' else ['--timeout', '100'])
                finally:
                    shutil.rmtree(goals_dir + '/' + GOAL, ignore_errors=True)
                    if not goals_existed and os.path.isdir(goals_dir) and not os.listdir(goals_dir):
                        os.rmdir(goals_dir)
        elif rid == 'r3':
            h3 = throwaway(work, 'home-r3')
            write_goal(h3, FIXTURE_GOAL)
            actual, why = row_r3(py, tool, make_env(h3, standin))
        elif rid == 'r6':
            h6 = throwaway(work, 'home-r6')
            write_goal(h6, NOWALL_GOAL)
            e6 = make_env(h6, standin)
            e6['LEADER_TIMEOUT'] = '5555'
            e6['LOOP_LEADER_TIMEOUT'] = '5555'
            actual, why = dry_timeout(py, tool, e6, []) if os.path.isfile(tool) else ('no-tool', sha(''))
        elif rid == 'r7':
            actual, why = row_r7(py, tool, work, standin)
        elif rid == 'r4':
            readme = tree + '/README.md'
            data = open(readme, 'rb').read() if os.path.isfile(readme) else b''
            actual, why = 'phrase=' + ('present' if b'.log.rc' in data else 'absent'), sha(data)
        elif rid == 'r5':
            actual, why = row_r5(tree)
        else:
            actual, why = 'unknown-row', sha(rid)
        ok = actual == expect
        passed += ok
        failed += (not ok)
        print('%s %s expected=%s actual=%s detail_sha=%s' % ('PASS' if ok else 'FAIL', rid, expect, actual, why))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
