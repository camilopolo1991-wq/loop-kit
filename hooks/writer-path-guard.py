#!/usr/bin/env python3
"""writer-path-guard: PreToolUse hook for loop-writer (matcher Write|Edit|MultiEdit|NotebookEdit).

Added 2026-10-20 after review finding: the writer had Write/Edit with no path guard and
could write .git/HEAD, other goals' evidence, the journal, STATE.md or tickets.

A writer may write only:
  * under $LOOP_HOME/goals/$LOOP_GOAL/evidence/T<nn>/writer/   (its own proof)
  * under any directory listed, one absolute path per line, in
    $LOOP_HOME/goals/$LOOP_GOAL/writable.txt  (the leader writes this file with the task
    branch worktree BEFORE dispatching the writer; it is the leader's gate, not prose)
Never, anywhere: a path containing /.git/, /.claude/, a CLAUDE.md, a .env, JOURNAL.md,
STATE.md, a tickets/ directory, or another goal's directory.

Without LOOP_GOAL set the guard denies every write: a writer with no goal has no scope.
Fails closed on any error. Register with "onFailure": "block".
"""
import functools
import json
import os
import re
import sys

# The shared library sits beside this file and is loaded by that path, so the load does not rest
# on the script folder being on the module path (the hook runs under an isolated interpreter).
# If it cannot be loaded the hook fails closed with the same deny JSON, exit 0.
try:
    _LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_guardlib.py')
    _g = type(sys)('_guardlib')
    _g.__file__ = _LIB
    with open(_LIB, encoding='utf-8') as _fh:
        exec(compile(_fh.read(), _LIB, 'exec'), _g.__dict__)
except Exception:
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
        'permissionDecisionReason': 'writer-path-guard could not load its library, so it fails closed.'}}))
    sys.exit(0)

# The shared shapes (bodies in _guardlib). This hook's output is always a deny.
_canon = _g.canon
_is_abs = _g.is_abs
_k = _g.fold
out = functools.partial(_g.out, 'deny')

LOOP_HOME = os.path.normpath(os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop'))

# LOOP_GOAL from the environment (the dispatcher sets it), else from $LOOP_HOME/current_goal,
# which the leader writes at goal start.
LOOP_GOAL = _g.current_goal(LOOP_HOME)

_RF = re.I if os.name == 'nt' else 0

ALWAYS_DENY = [
    (r'/\.git(/|$)', 'Writer role: never write inside .git. The leader owns git.'),
    (r'/\.claude(/|$)', 'Writer role: never write session settings, hooks or agents.'),
    (r'(^|/)CLAUDE\.md$', 'Writer role: the boot sector is not yours.'),
    (r'(^|/)\.env($|\.)', 'Writer role: never write a .env file.'),
    (r'(^|/)(JOURNAL|STATE)\.md$', 'Writer role: the journal and STATE.md are the leader\'s.'),
    (r'/tickets(/|$)', 'Writer role: tickets are the leader\'s.'),
    (r'(^|/)(summary|report|findings|analysis)\.md$', 'The harness refuses these names for subagent writes. Pick another name.'),
]


def allowed_roots():
    roots = []
    if LOOP_GOAL:
        roots.append(_canon(os.path.join(LOOP_HOME, 'goals', LOOP_GOAL, 'evidence')))
        wt = os.path.join(LOOP_HOME, 'goals', LOOP_GOAL, 'writable.txt')
        try:
            with open(wt, encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if _is_abs(line) and not line.startswith('#'):
                        roots.append(_canon(line))
        except FileNotFoundError:
            pass
    return roots


def run_writer_path():
    d = json.load(sys.stdin)
    tool = d.get('tool_name')
    if tool not in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        sys.exit(0)
    ti = d.get('tool_input') or {}
    fp = ti.get('file_path') or ti.get('notebook_path') or ''
    if not isinstance(fp, str) or not _is_abs(fp):
        out('Writer role: writes need an absolute path.')
    p = _canon(fp)
    for pat, why in ALWAYS_DENY:
        if re.search(pat, p, _RF):
            out(why)
    if not LOOP_GOAL:
        out('Writer role: LOOP_GOAL is not set, so no write has a scope. The leader sets it in the dispatch environment.')
    goals_root = _canon(os.path.join(LOOP_HOME, 'goals')) + '/'
    if _k(p).startswith(_k(goals_root)) and not _k(p).startswith(_k(goals_root + LOOP_GOAL + '/')):
        out('Writer role: that path belongs to another goal.')
    evidence = _canon(os.path.join(LOOP_HOME, 'goals', LOOP_GOAL, 'evidence')) + '/'
    if _k(p).startswith(_k(evidence)):
        if re.search(r'/evidence/T[^/]*/writer/', p + '/', _RF):
            sys.exit(0)
        out('Writer role: inside evidence you write only under T<nn>/writer/.')
    for root in allowed_roots()[1:]:
        if _k(p) == _k(root) or _k(p).startswith(_k(root) + '/'):
            sys.exit(0)
    out('Writer role: path is outside the task worktree listed in writable.txt and outside evidence/T<nn>/writer/.')


if __name__ == '__main__':
    _g.main(run_writer_path, 'writer-path-guard hit an unexpected error, so it fails closed.')
