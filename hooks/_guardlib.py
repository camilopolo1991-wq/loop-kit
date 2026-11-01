"""_guardlib: the one library under the four loop hooks (KIT-06 C1).

The four hooks (pretool-guard, readonly-guard, writer-git-guard, writer-path-guard) keep their
policy tables and decisions. Everything they share lives here, once: the canonical-path
function, the absolute-path test, the forward-slash function, the current-goal reader, the
config-key reader, the output function and the shell parser (segment splitter, tokenizer,
assignment test, base-name function).

Each hook loads this file by a path relative to its own file, so the load does not rest on the
script folder being on the module path (the hooks run under an isolated interpreter).

Where the old copies differed, the difference is a parameter here, and the default is the
behaviour the hook that had the copy had. Nothing here loosens a denial.
"""
import json
import os
import re
import shlex
import sys

_MSYS_DRIVE = re.compile(r'^/([A-Za-z])(?=/|$)')
GOAL_RE = r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}'

# Windows executable suffixes stripped before classification. PATHEXT order, not exhaustive
# on purpose: only suffixes that make a token EXECUTABLE belong here, or a data file named
# foo.js starts classifying as the command foo.
WIN_EXEC_SUFFIXES = ('.exe', '.com', '.cmd', '.bat', '.ps1')


def fwd(s):
    """One separator convention for every rule: every backslash becomes a forward slash.

    The text is not normalised (no folding of .. or doubled separators), because the
    pretool hook applies it to whole command text as well as to paths."""
    return (s or '').replace('\\', '/')


def canon(path):
    """One spelling for every path a guard compares.

    On Windows the MSYS drive form (/c/...), backslashes and forward slashes all become
    X:/... before any comparison. normpath also folds .. segments, so a traversal out of an
    allowed folder is judged where it lands."""
    p = str(path or '').strip().replace('\\', '/')
    if os.name == 'nt':
        m = _MSYS_DRIVE.match(p)
        if m:
            p = m.group(1).upper() + ':' + p[2:]
    return os.path.normpath(p).replace('\\', '/')


def is_abs(p):
    """Absolute on either platform: a POSIX root or a drive letter, a colon and a separator.

    A value that is not a string raises, and every hook fails closed on an exception."""
    return bool(p) and (p.startswith('/') or re.match(r'^[A-Za-z]:[\\/]', p) is not None)


def fold(s):
    """Prefix comparisons are case-blind on Windows, where the filesystem is."""
    return s.lower() if os.name == 'nt' else s


def current_goal(loop_home, strict=False):
    """The dispatched goal id: LOOP_GOAL from the environment, else the first line of
    <loop_home>/current_goal, which the leader writes at goal start.

    strict=False (readonly-guard, writer-path-guard): an environment value is returned as
    it is (stripped, not pattern-checked), a file value must match the goal pattern, and any
    read error gives ''.
    strict=True (writer-git-guard): the first line is stripped, whichever source it came
    from must match the goal pattern, and only an OSError is read as no file; any other
    error propagates, so the hook fails closed."""
    g = os.environ.get('LOOP_GOAL') or ''
    if g and not strict:
        return g.strip()
    g = g.strip()
    if not g:
        try:
            with open(os.path.join(loop_home, 'current_goal'), encoding='utf-8') as fh:
                lines = fh.read().strip().splitlines()
                if strict:
                    g = lines[0].strip() if lines else ''
                else:
                    g = lines[0] if lines else ''
        except (OSError if strict else Exception):
            g = ''
    return g if re.fullmatch(GOAL_RE, g or '') else ''


def config_key(name, loop_home=None, default=''):
    """The value of one KEY=value line of <loop_home>/config.env, or default.

    Read by name in-process, never echoed. Blank lines and # lines are skipped, a leading
    `export ` is ignored, one pair of matching quotes around the value is removed. When the
    file is unreadable or the key is absent the default is returned."""
    home = loop_home or os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop')
    try:
        with open(os.path.join(home, 'config.env'), encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('export '):
                    line = line[7:].lstrip()
                key, sep, val = line.partition('=')
                if sep and key.strip() == name:
                    val = val.strip()
                    if len(val) >= 2 and val[0] == val[-1] and val[0] in '\'"':
                        val = val[1:-1]
                    return val
    except OSError:
        return default
    return default


def out(decision, reason=None, updated=None):
    """Print one hook decision as JSON on stdout and exit 0. It never echoes the command."""
    h = {'hookEventName': 'PreToolUse'}
    if decision:
        h['permissionDecision'] = decision
    if reason:
        h['permissionDecisionReason'] = reason
    if updated is not None:
        h['updatedInput'] = updated
    print(json.dumps({'hookSpecificOutput': h}))
    sys.exit(0)


def main(run_fn, fail_reason):
    """Run a hook's decision function. Any Exception, malformed input included, fails closed:
    the same deny JSON is printed and the process exits 0, never a stack trace on stderr with
    a nonzero exit. BaseException (KeyboardInterrupt, SystemExit, including the normal
    out()/sys.exit(0) path) is never caught here."""
    try:
        run_fn()
    except Exception:
        out('deny', fail_reason)


# ---------------------------------------------------------------- shell parser
def split_segments(cmd, redirects=False):
    """Split on top-level ; & | newline ( ) ` outside quotes. Linear scan.

    redirects=True (writer-git-guard) keeps a redirection (2>&1, &>f) inside its segment
    instead of reading its & as a command separator."""
    segments, buf = [], []
    in_s = in_d = False
    for idx, c in enumerate(cmd):
        if redirects and c == '&' and not in_s and not in_d and (
                (buf and buf[-1] in '<>') or cmd[idx + 1:idx + 2] == '>'):
            buf.append(c)
        elif in_s:
            buf.append(c)
            if c == "'":
                in_s = False
        elif in_d:
            buf.append(c)
            if c == '"':
                in_d = False
        elif c == "'":
            in_s = True
            buf.append(c)
        elif c == '"':
            in_d = True
            buf.append(c)
        elif c in ';&|\n()`':
            segments.append(''.join(buf))
            buf = []
        else:
            buf.append(c)
    segments.append(''.join(buf))
    return [s for s in segments if s.strip()]


def tokenize(seg, posix=True):
    try:
        return shlex.split(seg, posix=posix)
    except ValueError:
        return seg.split()


def is_assignment(tok):
    if '=' not in tok:
        return False
    head = tok.split('=', 1)[0]
    return bool(head) and (head[0].isalpha() or head[0] == '_') and all(c.isalnum() or c == '_' for c in head)


def base(tok):
    """Basename of a command token, separator- and suffix-normalised.

    A bare rsplit('/') is POSIX-only, and on Windows a backslash separator OR an
    executable suffix is INDEPENDENTLY enough to slip a denied verb past it. Lowercased
    because Windows command lookup is case-insensitive and every word class in the hooks is
    lowercase."""
    tok = tok.replace('\\', '/').rsplit('/', 1)[-1]
    # drive-relative spelling with no separator, e.g. C:rm
    tok = tok.rsplit(':', 1)[-1].lower()
    for suf in WIN_EXEC_SUFFIXES:
        if tok.endswith(suf) and len(tok) > len(suf):
            return tok[:-len(suf)]
    return tok
