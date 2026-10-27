#!/usr/bin/env python3
"""C1 rows runner for the writer's shell hook.

Usage: run.py <tree> <home> <work>

Feeds <tree>/hooks/writer-git-guard.py one hook JSON per row, in the guarded heredoc shape,
and judges it: a deny is a deny decision in the JSON output; an allow is empty output and
exit 0. Prints PASS or FAIL per row with expected and actual, then a count, and exits 1 on
any FAIL.

Fixtures: a writable.txt under <home>/.loop/goals/<fixture id>/ (removed after its row, and
the directories this run made are removed at the end); everything else under <work>. The
rows that give the goal only through the current_goal file write <home>/.loop/current_goal
for the row and remove it after. The interpreter is the one
running this file. Nothing is spawned in the background and nothing is killed.
"""
import hashlib
import json
import os
import subprocess
import sys

FIX = 'FIXTURE-C1'


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def sha(s):
    return hashlib.sha256(s.encode('utf-8', 'replace')).hexdigest()[:12]


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rid, mode, expect, body = [x.strip() for x in line.split(' :: ', 3)]
            rows.append((rid, mode, expect, body))
    return rows


def write(path, text, made):
    d = os.path.dirname(path)
    new = []
    while d and not os.path.isdir(d):
        new.append(d)
        d = os.path.dirname(d)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    made.extend(reversed(new))
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def classify(cp, hide):
    if cp.returncode == 0 and cp.stdout == '' and cp.stderr == '':
        return 'allow', ''
    if cp.returncode == 0 and cp.stderr == '':
        try:
            h = json.loads(cp.stdout)['hookSpecificOutput']
            if h['permissionDecision'] == 'deny':
                reason = str(h.get('permissionDecisionReason', ''))
                if any(x and x in reason for x in hide):
                    reason = 'sha256:' + sha(reason)
                return 'deny', reason[:70]
        except Exception:
            pass
    return 'other', 'rc=%s out=%s err=%s' % (cp.returncode, sha(cp.stdout), sha(cp.stderr))


def main():
    if len(sys.argv) != 4:
        print('usage: run.py <tree> <home> <work>')
        return 2
    tree, home, work = fwd(sys.argv[1]), fwd(sys.argv[2]), fwd(sys.argv[3])
    real_home = fwd(os.path.expanduser('~'))
    names = os.path.dirname(work) + '/fixture-names.lst'  # beside <work>, in its parent folder
    hook = tree + '/hooks/writer-git-guard.py'
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    made = []
    for name, text in (('src.txt', 'alpha\nbeta\n'), ('under-root.sh', 'exit 0\n'),
                       ('under-root.py', 'pass\n')):
        write(work + '/' + name, text, made)
    roots = tree + '\n' + work + '\nwrapper: loop-fixture loop-ticket\n'
    hide = [real_home, home, work, tree]
    passed = failed = 0
    for rid, mode, expect, body in rows:
        mode, _, where = mode.partition('@')
        cwd = home if where == 'home' else work  # 'home': a folder that is no listed root
        lhome = home + '/.loop'
        ev = lhome + '/goals/' + FIX + '/evidence'
        wfile = lhome + '/goals/' + FIX + '/writable.txt'
        cfile = lhome + '/current_goal'
        files = []
        if mode in ('wt', 'cg'):
            write(wfile, roots, made)
            files.append(wfile)
        if mode == 'cg':
            write(cfile, FIX + '\n', made)
            files.append(cfile)
        cmd = body.replace('\\n', '\n')
        for k, v in (('{TREE}', tree), ('{HOME}', home), ('{WORK}', work), ('{PY}', fwd(sys.executable)),
                     ('{EV}', ev)):
            cmd = cmd.replace(k, v)
        cmd = "loop-guard-run <<'LOOP'\n" + cmd + "\nLOOP"
        env = dict(os.environ)
        env.update({'HOME': home, 'USERPROFILE': home, 'LOOP_HOME': lhome,
                    'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': names,
                    'PYTHONDONTWRITEBYTECODE': '1'})
        env.pop('LOOP_GOAL', None)
        if mode != 'cg':
            env['LOOP_GOAL'] = FIX
        payload = json.dumps({'tool_name': 'Bash', 'tool_input': {'command': cmd}, 'cwd': cwd})
        try:
            cp = subprocess.run([sys.executable, hook], input=payload, capture_output=True, text=True,
                                env=env, cwd=cwd)
            actual, detail = classify(cp, hide)
        finally:
            for f in files:
                try:
                    os.remove(f)
                except OSError:
                    pass
        ok = actual == expect
        passed += ok
        failed += (not ok)
        print('%s %s expected=%s actual=%s%s' % ('PASS' if ok else 'FAIL', rid, expect, actual,
                                                 (' (' + detail + ')') if detail else ''))
    for d in reversed(made):
        try:
            os.rmdir(d)
        except OSError:
            pass
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
