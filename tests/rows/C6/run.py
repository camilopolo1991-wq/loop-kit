#!/usr/bin/env python3
"""C6 rows runner: the dispatch line shape, loop-journal --dispatches, and the read-only hook's read list.

Usage: run.py <tree> <home> <work>

count rows: write a fixture journal under <work> and run "bash <tree>/bin/loop-journal --dispatches FIXT-C6"
with JOURNAL_FILE pointing at it; the output must be the expected three integers and the exit 0.
hook rows: feed <tree>/hooks/readonly-guard.py one hook JSON (the guarded heredoc shape) for the role in the
row; allow is empty output and exit 0, deny is a deny decision in the JSON output.
phrase rows: a Python bytes search under <tree> for the phrase in the named file.
HOME, USERPROFILE and LOOP_HOME point into <home>; the names file path is built from <work>'s parent.
Prints PASS or FAIL per row with expected and actual (a sha256 stands in for any text that could hold a home
path), then a count, and exits 1 on any FAIL. Nothing is spawned in the background and nothing is killed.
"""
import json
import os
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import Score, dirs_or_args, fwd, load_rows, make_env, run_phrase, sha, write_text

GOAL = 'FIXT-C6'
OTHER = 'FIXT-C6-OTHER'
NAMES_FILE = 'fixture-names.lst'  # beside <work>, in its parent folder


def fixture_lines(drop_one_reviewer):
    def ln(i, goal, step, text):
        return '- 2026-01-01T00:%02d:00Z %s %s %s' % (i, goal, step, text)
    body = [
        ('DISPATCH scout cards/a.md'),
        ('DISPATCH scout cards/b.md'),
        ('DISPATCH writer cards/c.md'),
        ('DISPATCH writer cards/d.md extra trailing words'),
        ('DISPATCH writer cards/e.md'),
        ('DISPATCH reviewer cards/f.md'),
        ('DISPATCH reviewer cards/g.md'),
    ]
    out = []
    i = 0
    for t in body:
        if drop_one_reviewer and t == 'DISPATCH reviewer cards/g.md':
            continue
        out.append(ln(i, GOAL, 'T%02d' % (i + 1), t))
        i += 1
    # lines that must not count
    out.append(ln(i, OTHER, 'T01', 'DISPATCH writer cards/z.md'))
    out.append(ln(i + 1, GOAL, 'T09', 'note: DISPATCH writer cards/y.md inside the text'))
    out.append(ln(i + 2, GOAL, 'T09', 'DISPATCH auditor cards/x.md'))
    out.append(ln(i + 3, GOAL, 'T09', 'DISPATCHED writer cards/w.md'))
    out.append(ln(i + 4, GOAL, 'T09', 'ROLLBACK somewhere sha256 0123456789abcdef'))
    return out


def run_count(tree, work, env, rid, expect, drop):
    fixture = work + '/' + rid + '.journal'
    write_text(fixture, '\n'.join(fixture_lines(drop)) + '\n')
    env = dict(env)
    env['JOURNAL_FILE'] = fixture
    cp = subprocess.run(['bash', tree + '/bin/loop-journal', '--dispatches', GOAL],
                        capture_output=True, text=True, env=env, cwd=work)
    out = cp.stdout.strip()
    simple = out if all(c in '0123456789 ' for c in out) else 'sha256:' + sha(cp.stdout + cp.stderr)
    ok = cp.returncode == 0 and out == expect and cp.stderr == ''
    return ok, 'expected=%s actual=%s exit=%d' % (expect, simple, cp.returncode)


def run_hook(tree, work, env, role, command, expect, hide):
    cmd = "loop-guard-run <<'LOOP'\n" + command + "\nLOOP"
    env = dict(env)
    env.update({'LOOP_GOAL': GOAL, 'LOOP_ROLE': role})
    payload = json.dumps({'tool_name': 'Bash', 'tool_input': {'command': cmd}, 'cwd': work})
    cp = subprocess.run([sys.executable, tree + '/hooks/readonly-guard.py'], input=payload,
                        capture_output=True, text=True, env=env, cwd=work)
    actual = 'other'
    detail = 'rc=%s out=%s err=%s' % (cp.returncode, sha(cp.stdout), sha(cp.stderr))
    if cp.returncode == 0 and cp.stdout == '' and cp.stderr == '':
        actual, detail = 'allow', ''
    elif cp.returncode == 0 and cp.stderr == '':
        try:
            h = json.loads(cp.stdout)['hookSpecificOutput']
            if h['permissionDecision'] == 'deny':
                reason = str(h.get('permissionDecisionReason', ''))
                if any(x and x in reason for x in hide):
                    reason = 'sha256:' + sha(reason)
                actual, detail = 'deny', reason[:70]
        except Exception:
            pass
    return actual == expect, 'expected=%s actual=%s%s' % (expect, actual, (' (' + detail + ')') if detail else '')


def main():
    tree, home, work = dirs_or_args()
    os.makedirs(work, exist_ok=True)
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    env = make_env(home, {'LOOP_PY': fwd(sys.executable), 'LOOP_NAMES_FILE': os.path.dirname(work) + '/' + NAMES_FILE},
                   ('LOOP_GOAL', 'JOURNAL_FILE'))
    hide = [fwd(os.path.expanduser('~')), home, work, tree]
    score = Score()
    for rid, kind, expect, arg in rows:
        if kind in ('count_full', 'count_minus'):
            ok, detail = run_count(tree, work, env, rid, expect, kind == 'count_minus')
        elif kind in ('hook_allow', 'hook_deny'):
            role, command = arg.split('|', 1)
            ok, detail = run_hook(tree, work, env, role, command, expect, hide)
        elif kind == 'phrase':
            ok, detail = run_phrase(tree, expect, arg)
        else:
            ok, detail = False, 'unknown kind ' + kind
        score.row(ok, rid, '%s' % (detail))
    return score.done(rows)


if __name__ == '__main__':
    sys.exit(main())
