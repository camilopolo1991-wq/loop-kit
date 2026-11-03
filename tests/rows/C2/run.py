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
import json
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import dirs_or_args, fwd, hook_class, load_rows, make_env

FIX = 'FIXTURE-C2'
OTHER_GOAL = 'FIXTURE-C2-OTHER'


def main():
    tree, home, work = dirs_or_args()
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
        env = make_env(home, {'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': names, 'LOOP_GOAL': FIX,
                              'LOOP_ROLE': role})
        payload = json.dumps({'tool_name': 'Bash', 'tool_input': {'command': cmd}, 'cwd': work})
        cp = subprocess.run([sys.executable, hook], input=payload, capture_output=True, text=True,
                            env=env, cwd=work)
        actual, detail = hook_class(cp, hide)
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
