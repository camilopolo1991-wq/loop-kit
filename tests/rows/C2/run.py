#!/usr/bin/env python3
"""C2 rows runner for the read-only hook.

Usage: run.py <tree> <home> <work>

Feeds <tree>/hooks/readonly-guard.py one hook JSON per row, in the guarded heredoc shape,
and judges it: a deny is a deny decision in the JSON output; an allow is empty output and
exit 0. Prints PASS or FAIL per row with expected and actual, then a count, and exits 1 on
any FAIL.

The hook judges the path string and never touches the disk, so no fixture file is written.
<work> is created if missing (the hook process runs in it) and removed at the end if this run made it.
<home> only supplies HOME, USERPROFILE and LOOP_HOME (<home>/.loop); <work> is the working
folder of the hook process and its parent holds the names file path. The interpreter is the
one running this file. Nothing is spawned in the background and nothing is killed.
"""
import hashlib
import json
import os
import subprocess
import sys

FIX = 'FIXTURE-C2'
OTHER_GOAL = 'FIXTURE-C2-OTHER'


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
            rid, role, expect, body = [x.strip() for x in line.split(' :: ', 3)]
            rows.append((rid, role, expect, body))
    return rows


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
    if len(sys.argv) == 1:
        tree_e = os.environ.get('LOOP_TREE')
        home_e = os.environ.get('LOOP_ROWS_HOME')
        work_e = os.environ.get('LOOP_WORK')
        if not tree_e or not home_e or not work_e:
            print('usage: run.py <tree> <home> <work>   or   LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> run.py')
            return 64
        sys.argv[1:] = [tree_e, home_e, work_e]
    if len(sys.argv) != 4:
        print('usage: run.py <tree> <home> <work>')
        return 2
    tree, home, work = fwd(sys.argv[1]), fwd(sys.argv[2]), fwd(sys.argv[3])
    real_home = fwd(os.path.expanduser('~'))
    names = os.path.dirname(work) + '/fixture-names.lst'
    hook = tree + '/hooks/readonly-guard.py'
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    lhome = home + '/.loop'
    ev = lhome + '/goals/' + FIX + '/evidence'
    other = lhome + '/goals/' + OTHER_GOAL + '/evidence'
    hide = [real_home, home, work, tree]
    made = []
    d = work
    while d and not os.path.isdir(d):
        made.append(d)
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    os.makedirs(work, exist_ok=True)
    passed = failed = 0
    for rid, role, expect, body in rows:
        cmd = (body.replace('{EV}', ev).replace('{OTHER}', other).replace('{LH}', lhome)
               .replace('{FIX}', FIX))
        cmd = "loop-guard-run <<'LOOP'\n" + cmd + "\nLOOP"
        env = dict(os.environ)
        env.update({'HOME': home, 'USERPROFILE': home, 'LOOP_HOME': lhome,
                    'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': names,
                    'LOOP_GOAL': FIX, 'LOOP_ROLE': role, 'PYTHONDONTWRITEBYTECODE': '1'})
        payload = json.dumps({'tool_name': 'Bash', 'tool_input': {'command': cmd}, 'cwd': work})
        cp = subprocess.run([sys.executable, hook], input=payload, capture_output=True, text=True,
                            env=env, cwd=work)
        actual, detail = classify(cp, hide)
        ok = actual == expect
        passed += ok
        failed += (not ok)
        print('%s %s expected=%s actual=%s%s' % ('PASS' if ok else 'FAIL', rid, expect, actual,
                                                 (' (' + detail + ')') if detail else ''))
    for d in made:  # folders this run made, deepest first; a non-empty one stays
        try:
            os.rmdir(d)
        except OSError:
            pass
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
