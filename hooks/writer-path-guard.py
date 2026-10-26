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
import json
import os
import re
import sys

LOOP_HOME = os.path.normpath(os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop'))


def _current_goal():
    """LOOP_GOAL from the environment (the dispatcher sets it), else from
    $LOOP_HOME/current_goal, which the leader writes at goal start."""
    g = os.environ.get('LOOP_GOAL') or ''
    if g:
        return g.strip()
    try:
        with open(os.path.join(LOOP_HOME, 'current_goal'), encoding='utf-8') as fh:
            g = fh.read().strip().splitlines()[0] if fh else ''
    except Exception:
        g = ''
    return g if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', g or '') else ''


LOOP_GOAL = _current_goal()

_MSYS_DRIVE = re.compile(r'^/([A-Za-z])(?=/|$)')
_RF = re.I if os.name == 'nt' else 0


def _canon(path):
    """P21. One spelling for every path this guard compares.

    The auditor's evidence redirect to an absolute C:/... path was denied as not
    absolute, and the /c/... form that readlink gives under bash -lc never matched a
    C:/ prefix. On Windows the MSYS drive form, backslashes and forward slashes all
    become X:/... before any comparison. normpath also folds .. segments, so a
    traversal out of an allowed folder is judged where it lands.
    """
    p = str(path or '').strip().replace('\\', '/')
    if os.name == 'nt':
        m = _MSYS_DRIVE.match(p)
        if m:
            p = m.group(1).upper() + ':' + p[2:]
    return os.path.normpath(p).replace('\\', '/')


def _k(s):
    """Prefix comparisons are case-blind on Windows, where the filesystem is."""
    return s.lower() if os.name == 'nt' else s

ALWAYS_DENY = [
    (r'/\.git(/|$)', 'Writer role: never write inside .git. The leader owns git.'),
    (r'/\.claude(/|$)', 'Writer role: never write session settings, hooks or agents.'),
    (r'(^|/)CLAUDE\.md$', 'Writer role: the boot sector is not yours.'),
    (r'(^|/)\.env($|\.)', 'Writer role: never write a .env file.'),
    (r'(^|/)(JOURNAL|STATE)\.md$', 'Writer role: the journal and STATE.md are the leader\'s.'),
    (r'/tickets(/|$)', 'Writer role: tickets are the leader\'s.'),
    (r'(^|/)(summary|report|findings|analysis)\.md$', 'The harness refuses these names for subagent writes. Pick another name.'),
]


def out(reason):
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                                             'permissionDecision': 'deny',
                                             'permissionDecisionReason': reason}}))
    sys.exit(0)


def _fwd(path):
    """One separator convention for every comparison in this file.

    os.path.normpath and os.path.join emit BACKSLASHES on Windows, while this guard
    builds its prefixes by appending a literal '/'. The result is a mixed-separator
    string that no real path can start with, so every prefix test silently went False.
    """
    return os.path.normpath(path).replace('\\', '/')


def _is_abs(p):
    """Absolute on either platform. `p.startswith('/')` is POSIX-only, and a Windows
    absolute path begins `C:\\` or `C:/`, so the POSIX-only test rejected every real
    write on this host and the guard denied the writer role outright."""
    return bool(p) and (p.startswith('/') or re.match(r'^[A-Za-z]:[\\/]', p) is not None)


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


def run():
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


def main():
    try:
        run()
    except Exception:
        out('writer-path-guard hit an unexpected error, so it fails closed.')


if __name__ == '__main__':
    main()
