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
import json
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import dirs_or_args, fwd, hook_class, load_rows, make_env, write_text

FIX = 'FIXTURE-C1'


def write(path, text, made):
    d = os.path.dirname(path)
    new = []
    while d and not os.path.isdir(d):
        new.append(d)
        d = os.path.dirname(d)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    made.extend(reversed(new))
    write_text(path, text)


def main():
    tree, home, work = dirs_or_args()
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
        env = make_env(home, {'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': names}, ('LOOP_GOAL',))
        if mode != 'cg':
            env['LOOP_GOAL'] = FIX
        payload = json.dumps({'tool_name': 'Bash', 'tool_input': {'command': cmd}, 'cwd': cwd})
        try:
            cp = subprocess.run([sys.executable, hook], input=payload, capture_output=True, text=True,
                                env=env, cwd=cwd)
            actual, detail = hook_class(cp, hide)
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
