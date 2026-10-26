#!/usr/bin/env python3
"""Shared config for the loop-* tools. Values live in $LOOP_HOME/config.env (no secrets in it).
LOOP_HOME defaults to ~/.loop. Every key below is a placeholder until install.sh fills it.
"""
import os
import re


def strip_inline_comment(line):
    """Everything from the first '#' is documentation, not value.

    P06. loop_conf.load() used to keep it, so `ENGINE_RECORD_DIR=   # worktree of
    the record repo (...)` read back as that comment string: non-empty, not a
    directory, and STATE_FILE derived from it. loop_dispatch.conf() stripped it
    at the same time, so the two parsers disagreed on the same file. This is the
    one implementation both now call.
    """
    return line.split('#', 1)[0].strip()


DEFAULTS = {
    'LOOP_HOME': os.path.expanduser('~/.loop'),
    'ENGINE_RECORD_DIR': '',                 # the worktree for the record branch (RECORD_BRANCH); install fills it
    'RECORD_BRANCH': 'record',               # branch inside ENGINE_RECORD_DIR that carries state, journal, exports
    'STATE_FILE': '',                        # defaults to <ENGINE_RECORD_DIR>/docs/STATE.md
    'JOURNAL_FILE': '',                      # defaults to <ENGINE_RECORD_DIR>/docs/JOURNAL.md
    'EXPORT_DIR': '',                        # defaults to <ENGINE_RECORD_DIR>/exports
    'WRAPPERS': 'loop-guard-run loop-journal loop-scan loop-report loop-tripwire loop-ticket',
    'WRITABLE_TREES': '',                    # colon-separated git worktrees the leader may create task branches in
    'MAX_LEADERS': '1',                      # leaders running at once on this machine
    'SURFACES': '',                          # space-separated surface wrappers installed here (n8n sql react ...), empty = none
    'REPORT_SEND_CMD': '',                   # e.g. /path/send.sh --subject {subject} --file {file}; empty = report stays on disk
    'REPORT_MAX_LINES': '80',
    'STATE_MAX_LINES': '150',
}


# P24. A value read from config.env, or exported by a shell that did not expand it, can
# carry a literal leading tilde. Nothing expanded it, so `~/.loop/current_goal` was tested
# as a relative path and preflight printed "current_goal not set" while the file existed
# (GITHUB-01, 15:56:32Z). Path keys are expanded here, once, for every caller. A key that
# is not a path keeps its tilde.
PATH_KEYS = {'LOOP_HOME', 'ENGINE_RECORD_DIR', 'STATE_FILE', 'JOURNAL_FILE', 'EXPORT_DIR',
             'WRITABLE_TREES', 'LOOP_PY'}
PATH_SUFFIXES = ('_DIR', '_FILE', '_BIN', '_HOME', '_PATH')


def is_path_key(k):
    return k in PATH_KEYS or k.endswith(PATH_SUFFIXES)


def expand_tilde(v):
    """Expand a leading ~ or ~/..., and the same at the start of each element of a
    colon-separated list. A drive colon (C:/...) is followed by a slash, never a tilde,
    so it is never mistaken for a list element that needs expanding."""
    if not v or '~' not in v:
        return v
    home = os.path.expanduser('~').replace('\\', '/')
    return re.sub(r'(^|:)~(?=$|[/\\:])', lambda m: m.group(1) + home, v)


def load():
    c = dict(DEFAULTS)
    path = os.path.join(expand_tilde(os.environ.get('LOOP_HOME', DEFAULTS['LOOP_HOME'])), 'config.env')
    try:
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = strip_inline_comment(line)
                if line and '=' in line:
                    k, v = line.split('=', 1)
                    c[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    for k in list(c):
        if os.environ.get(k):
            c[k] = os.environ[k]
    for k in list(c):
        if is_path_key(k):
            c[k] = expand_tilde(c[k])
    er = c['ENGINE_RECORD_DIR']
    if er:
        c['STATE_FILE'] = c['STATE_FILE'] or os.path.join(er, 'docs', 'STATE.md')
        c['JOURNAL_FILE'] = c['JOURNAL_FILE'] or os.path.join(er, 'docs', 'JOURNAL.md')
        c['EXPORT_DIR'] = c['EXPORT_DIR'] or os.path.join(er, 'exports')
    return c


def read_named_key(path, name):
    """Return the value of one named key from a KEY=VALUE file. Never print it."""
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            s = line.strip()
            if s.startswith('export '):
                s = s[7:]
            if s.startswith(name + '='):
                return s.split('=', 1)[1].strip().strip('"').strip("'")
    raise KeyError(f'{name} not found in {path}')


def scratch(goal=None):
    c = load()
    d = os.path.join(c['LOOP_HOME'], 'scratch', goal or 'adhoc')
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d
