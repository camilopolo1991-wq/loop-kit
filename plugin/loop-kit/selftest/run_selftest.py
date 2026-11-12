#!/usr/bin/env python3
"""run_selftest.py: one deny and one allow payload per guard, through run-guard.sh.

Usage: run_selftest.py --home <empty folder> --python <interpreter> [--flip]

Builds a minimal throwaway loop home in --home (fixtures written here, no copy of any live
config, name list or secret file), then pipes 8 payloads (a deny and an allow for each of
pretool-guard, readonly-guard, writer-git-guard, writer-path-guard) into the guards through
hooks/run-guard.sh. LOOP_HOME, LOOP_PYTHON, LOOP_GOAL and LOOP_ROLE are set for the child only.
One line per case: guard, case, expected, got, exit code. Exit 0 only when all 8 hold.
--flip inverts the deny expectation, a control that must exit non-zero.
A summary goes to stderr so stdout holds exactly the 8 case lines.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOAL = 'SELFTEST-01'


def find_bash():
    """A POSIX bash. On Windows the Git for Windows one, never the WSL launcher in system32."""
    if os.name == 'nt':
        for c in (os.environ.get('LOOP_BASH') or '',
                  'C:/Program Files/Git/bin/bash.exe',
                  'C:/Program Files (x86)/Git/bin/bash.exe'):
            if c and os.path.isfile(c):
                return c
        w = shutil.which('bash')
        if w and 'system32' not in w.replace('\\', '/').lower():
            return w
        return None
    return shutil.which('bash')


def build_home(home):
    """The fixture loop home: an empty config, an empty local deny list, one goal."""
    if os.path.exists(home) and os.listdir(home):
        raise SystemExit('selftest: --home must be empty or absent')
    gdir = os.path.join(home, 'goals', GOAL)
    os.makedirs(os.path.join(gdir, 'evidence', 'T01', 'writer'))
    os.makedirs(os.path.join(home, 'work', GOAL))
    with open(os.path.join(home, 'config.env'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('# selftest fixture, no keys\n')
    with open(os.path.join(home, 'guard-deny.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('# selftest fixture, no rules\n')
    with open(os.path.join(gdir, 'writable.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(home.replace('\\', '/') + '/work/' + GOAL + '\n')


def cases(home):
    h = home.replace('\\', '/')
    ev = h + '/goals/' + GOAL + '/evidence/T01/writer/note.txt'
    bash = lambda cmd: {'tool_name': 'Bash', 'tool_input': {'command': cmd}}
    return [
        ('pretool-guard.py', 'deny-env-dump', 'deny', bash('printenv'), {}),
        ('pretool-guard.py', 'allow-read-plain', 'allow',
         {'tool_name': 'Read', 'tool_input': {'file_path': h + '/work/' + GOAL + '/notes.txt'}}, {}),
        ('readonly-guard.py', 'deny-write-outside-evidence', 'deny',
         {'tool_name': 'Write', 'tool_input': {'file_path': h + '/work/' + GOAL + '/out.txt'}},
         {'LOOP_ROLE': 'scout'}),
        ('readonly-guard.py', 'allow-read-plain', 'allow',
         {'tool_name': 'Read', 'tool_input': {'file_path': h + '/work/' + GOAL + '/notes.txt'}},
         {'LOOP_ROLE': 'scout'}),
        ('writer-git-guard.py', 'deny-version-control', 'deny', bash('git status'), {'LOOP_GOAL': GOAL}),
        ('writer-git-guard.py', 'allow-plain-utility', 'allow', bash('wc -l ' + ev), {'LOOP_GOAL': GOAL}),
        ('writer-path-guard.py', 'deny-write-in-dot-git', 'deny',
         {'tool_name': 'Write', 'tool_input': {'file_path': h + '/work/' + GOAL + '/.git/config'}},
         {'LOOP_GOAL': GOAL}),
        ('writer-path-guard.py', 'allow-write-own-evidence', 'allow',
         {'tool_name': 'Write', 'tool_input': {'file_path': ev}}, {'LOOP_GOAL': GOAL}),
    ]


def decide(rc, out):
    """deny when the guard printed a deny decision; allow when it exited 0 with no deny."""
    if rc != 0:
        return 'error'
    text = (out or '').strip()
    if not text:
        return 'allow'
    try:
        d = json.loads(text)
        dec = d.get('hookSpecificOutput', {}).get('permissionDecision')
    except ValueError:
        return 'error'
    return 'deny' if dec == 'deny' else 'allow'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--home', required=True)
    ap.add_argument('--python', required=True)
    ap.add_argument('--flip', action='store_true')
    a = ap.parse_args()
    home = os.path.abspath(a.home).replace('\\', '/')
    bash = find_bash()
    if not bash:
        print('selftest: no POSIX bash found', file=sys.stderr)
        return 2
    build_home(home)
    launcher = PLUGIN.replace('\\', '/') + '/hooks/run-guard.sh'
    held = 0
    rows = cases(home)
    for guard, case, expected, payload, extra in rows:
        want = expected
        if a.flip and expected == 'deny':
            want = 'allow'
        env = dict(os.environ)
        for k in ('LOOP_GOAL', 'LOOP_ROLE', 'LOOP_GUARD_MODE'):
            env.pop(k, None)
        env.update(extra)
        env['LOOP_HOME'] = home
        env['LOOP_PYTHON'] = a.python
        env['CLAUDE_PLUGIN_ROOT'] = PLUGIN.replace('\\', '/')
        p = subprocess.run([bash, launcher, guard], input=json.dumps(payload),
                           capture_output=True, text=True, env=env, timeout=60)
        got = decide(p.returncode, p.stdout)
        ok = got == want
        held += ok
        print('guard=%s case=%s expected=%s got=%s exit=%d%s'
              % (guard, case, want, got, p.returncode, '' if ok else ' MISMATCH'))
    print('selftest: %d of %d hold%s' % (held, len(rows), ' (flip control)' if a.flip else ''),
          file=sys.stderr)
    return 0 if held == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main())
