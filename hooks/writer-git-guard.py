#!/usr/bin/env python3
"""writer-git-guard: PreToolUse hook for loop-writer (agent frontmatter, matcher Bash).

Second generation, 2026-10-20. The first generation resolved the command word through
four launcher prefixes; an independent review drove 31 shapes past it (sh -c, timeout,
xargs, if/while keywords, $'git', {git,}, $GIT, a copied binary). This version is
deliberately blunt, because the writer never has a legitimate reason to say "git":

  1. Any shlex token in any segment whose basename is `git` or starts with `git-`, or
     any inline script argument (-c/-e) that itself tokenises to such a word: DENY.
     A quoted grep pattern "git commit" is one token "git commit" (basename differs) and
     passes; a path /opt/x/.gitignore passes; the bare word git anywhere does not.
  2. Any inline interpreter or shell (sh -c, bash -c, eval, python -c, perl -e, node -e,
     python - <<EOF): DENY. The writer runs wrappers and scripts by path, never inline code.
  3. Any decoder (base64 -d, xxd -r, openssl enc -d) anywhere: DENY.
  4. A command word carrying $ ` { ? * [ or ANSI-C quoting $'...': DENY (unresolvable).
  5. cp/ln/install whose source basename is git: DENY (two-step binary copy). The general
     answer to "copy the binary" is OS level: run the writer under a uid that cannot read
     /usr/bin/git, or shadow git with a deny stub on PATH inside loop-guard-run.
  6. loop-scan without a FILE argument shells out to git diff: DENY for the writer.
  7. (KIT-02 C1) One allow set A, judged after the denials above. A command word outside A
     is DENIED. A is:
       - loop-guard-run itself (its heredoc opener and its terminator line are allowed
         segments; the body is what A judges), loop-journal (the step-log append), loop-scan on a file;
       - the surface wrappers named on `wrapper: loop-x loop-y` lines of the goal's
         writable.txt, which sit beside the absolute root lines (the path hook ignores them).
         Never a ticket, report or tripwire wrapper, listed or not; with no such line, none;
       - plain utilities: cat head tail wc ls sha256sum cmp diff od grep find stat printf echo
         sort cut sed (no in-place) awk cygpath uname date;
       - only with writable.txt present: cp mv rm touch under a listed root or the goal's
         evidence folder, mkdir under a listed root only.
     Every script is judged by the script clause alone, an allowlist of one shape. A bare
     script path (the command word, one word) must lie under the goal's evidence folder,
     under LOOP_HOME/scratch/<goal>/, or under a listed root, and only with writable.txt
     present. An interpreter run is exactly two words after the leading VAR=value
     assignments: an interpreter name from SCRIPT_INTERPRETERS, then one script path under
     those same roots. A third word, any flag or flag cluster, a +X option, a module run
     (-m) and an interpreter name outside the set (pythonw, python3.12) are denied. The path
     is judged only by its resolved prefix against the roots, never by its characters.
  8. (KIT-02 C1, ruling 7b) Any command holding $( , a backtick or a backslash is denied
     whatever else it holds, checked on the whole body before any segment is split.
     The goal is LOOP_GOAL, else the first line of LOOP_HOME/current_goal; with neither, or
     with no writable.txt, A has no file utilities, no wrappers and no script clause.
     Leading VAR=value assignments are skipped before the command word is judged. A
     redirection (2>&1, > file) is not part of the command word or its operands; sed with an
     in-place flag is denied.

Never echoes the command. Any Exception fails closed. Register with "onFailure": "block".
"""
import json
import os
import re
import shlex
import sys

REASON = "Writer role: git is the leader's. Ask the leader for any branch, commit or git read."
REASON_INLINE = 'Writer role: no inline interpreter or shell code (sh -c, eval, python -c). Run wrappers and script files by path.'
REASON_DECODER = 'Writer role: no decoders (base64 -d, xxd -r, openssl enc). Encoded commands are not judged.'
REASON_META = 'Writer role: a command word with $ ` { ? * [ or $\'...\' cannot be judged and is denied.'
REASON_COPY = 'Writer role: copying or linking the git binary is denied.'
REASON_SCAN = 'Writer role: loop-scan needs a FILE argument here; the range form runs git.'
REASON_LAUNCHER = ('Writer role: powershell, pwsh, cmd, wscript and cscript are denied as a class. '
                   'They reach git through an argument string this hook does not parse.')

INTERPRETERS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'fish', 'python', 'python2', 'python3', 'perl',
                'ruby', 'php', 'node', 'nodejs', 'lua', 'tclsh', 'awk', 'gawk', 'mawk', 'script',
                'su', 'runuser', 'busybox', 'eval', 'source', '.'}
SHELLS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'fish'}
DECODERS = {'base64', 'base32', 'xxd', 'uudecode'}
KEYWORDS = {'then', 'do', 'else', 'elif', 'if', 'while', 'until', '!', '{', '}', 'fi', 'done',
            'time', 'exec', 'command', 'sudo', 'env', 'nice', 'nohup', 'timeout', 'xargs',
            'stdbuf', 'setsid', 'flock', 'watch'}


def is_assignment(tok):
    if '=' not in tok:
        return False
    head = tok.split('=', 1)[0]
    return bool(head) and (head[0].isalpha() or head[0] == '_') and all(c.isalnum() or c == '_' for c in head)


def tokenize(seg, posix=True):
    try:
        return shlex.split(seg, posix=posix)
    except ValueError:
        return seg.split()


# Windows executable suffixes stripped before classification. PATHEXT order, not exhaustive
# on purpose: only suffixes that make a token EXECUTABLE belong here, or a data file named
# foo.js starts classifying as the command foo.
WIN_EXEC_SUFFIXES = ('.exe', '.com', '.cmd', '.bat', '.ps1')
# Read-only/writer roles have no business starting one of these. Each one reaches every
# denied verb through an argument string this hook does not parse, so the class is denied
# outright rather than walked like a POSIX launcher.
DENIED_LAUNCHERS = {'powershell', 'pwsh', 'cmd', 'wscript', 'cscript'}


def base(tok):
    """Basename of a command token, separator- and suffix-normalised.

    A bare rsplit('/') is POSIX-only, and on Windows a backslash separator OR an
    executable suffix is INDEPENDENTLY enough to slip a denied verb past it: measured,
    both `C:\\tools\\git commit` and `git.exe commit` were allowed while bare `git` was
    denied. Lowercased because Windows command lookup is case-insensitive and every word
    class in this file is lowercase.
    """
    tok = tok.replace('\\', '/').rsplit('/', 1)[-1]
    # drive-relative spelling with no separator, e.g. C:git
    tok = tok.rsplit(':', 1)[-1].lower()
    for suf in WIN_EXEC_SUFFIXES:
        if tok.endswith(suf) and len(tok) > len(suf):
            return tok[:-len(suf)]
    return tok


def is_git_word(tok):
    b = base(tok)
    return b == 'git' or b.startswith('git-')


def split_segments(cmd):
    segments, buf = [], []
    in_s = in_d = False
    for idx, c in enumerate(cmd):
        if c == '&' and not in_s and not in_d and (
                (buf and buf[-1] in '<>') or cmd[idx + 1:idx + 2] == '>'):
            buf.append(c)  # a redirection (2>&1, &>f), not a command separator
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


def judge_tokens(toks, depth=0):
    """Return a reason or None. Recurses into inline script arguments."""
    if depth > 5:
        return REASON_INLINE
    first = None
    for i, t in enumerate(toks):
        if is_assignment(t):
            continue
        if first is None:
            first = i
        if is_git_word(t):
            return REASON
        b = base(t).lower()
        if b in DENIED_LAUNCHERS:
            return REASON_LAUNCHER
        if b in DECODERS:
            return REASON_DECODER
        if b == 'openssl' and any(x in toks for x in ('enc', 'base64')):
            return REASON_DECODER
        if b == 'env':
            for j in range(i + 1, len(toks)):
                f = toks[j]
                if f in ('-S', '--split-string') and j + 1 < len(toks):
                    for s2 in split_segments(toks[j + 1]):
                        r = judge_tokens(tokenize(s2), depth + 1)
                        if r:
                            return r
                elif f.startswith('--split-string='):
                    for s2 in split_segments(f.split('=', 1)[1]):
                        r = judge_tokens(tokenize(s2), depth + 1)
                        if r:
                            return r
        if b in ('eval', 'source', '.'):
            for a in toks[i + 1:]:
                for s2 in split_segments(a):
                    r = judge_tokens(tokenize(s2), depth + 1)
                    if r:
                        return r
            return REASON_INLINE
        if b in INTERPRETERS:
            rest = toks[i + 1:]
            flags = [f for f in rest if f.startswith('-') and f != '--']
            inline = any(f in ('-c', '-e', '-E', '-', '--command') or
                         (not f.startswith('--') and len(f) > 1 and any(ch in f[1:] for ch in 'ceE'))
                         for f in flags)
            if b in SHELLS and not rest:
                return REASON_INLINE  # bare interactive shell
            if inline or ('<<' in ' '.join(rest)):
                # recurse into every string argument; a git word inside is a git call
                for a in rest:
                    if not a.startswith('-'):
                        for s in split_segments(a):
                            r = judge_tokens(tokenize(s), depth + 1)
                            if r:
                                return r
                return REASON_INLINE
            if b in ('awk', 'gawk', 'mawk') and any('system(' in a for a in rest):
                return REASON_INLINE
        if b in ('cp', 'ln', 'install', 'rsync') and any(is_git_word(a) for a in toks[i + 1:]):
            return REASON_COPY
        if b == 'loop-scan':
            rest = [a for a in toks[i + 1:] if not a.startswith('-')]
            if not rest or '--range' in toks:
                return REASON_SCAN
    return None


def judge_segment(seg):
    seg = seg.strip()
    if "$'" in seg:
        return REASON_META
    raw = seg.split()
    k = 0
    while k < len(raw) and is_assignment(raw[k]):
        k += 1
    while k < len(raw) and base(raw[k]).lower() in KEYWORDS:
        k += 1
    if k < len(raw) and any(ch in raw[k] for ch in '$`{?*['):
        return REASON_META
    r = judge_tokens(tokenize(seg))
    if r:
        return r
    # Backslash is shlex's escape character, so the POSIX pass above welds
    # `C:\tools\git` into `C:toolsgit` and never sees git. Re-judge the non-POSIX
    # tokenization. Union, not replacement: strictly more denials, never fewer.
    if '\\' in seg:
        return judge_tokens(tokenize(seg, posix=False))
    return None


# ---- KIT-02 C1: the allow set A and the script clause ---------------------------------

REASON_NOTA = ('Writer role: that command is not in the writer allow set. Use a wrapper listed '
               'in writable.txt, a script file under a listed root, or a plain read utility.')
REASON_FILEUTIL = ('Writer role: cp, mv, rm, touch and mkdir need writable.txt, and every path they '
                   'change must lie under a listed root (evidence too, except for mkdir).')
REASON_SCRIPT = ('Writer role: a script runs only with writable.txt present and its path under the goal '
                 'evidence folder, scratch/<goal>, or a listed root; an interpreter takes one script '
                 'path and nothing else (no flag, no third word).')
REASON_SUBST = ('Writer role: a command holding $( , a backtick or a backslash cannot be judged and '
                'is denied.')
REASON_FLAG = 'Writer role: sed with an in-place flag edits files and is denied.'

GOAL_RE = r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}'
SCRIPT_INTERPRETERS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'fish', 'python', 'python2', 'python3', 'py',
                       'perl', 'ruby', 'php', 'node', 'nodejs', 'lua', 'tclsh'}
PLAIN_UTILS = {'cat', 'head', 'tail', 'wc', 'ls', 'sha256sum', 'cmp', 'diff', 'od', 'grep', 'find',
               'stat', 'printf', 'echo', 'sort', 'cut', 'sed', 'awk', 'cygpath', 'uname', 'date'}
FILE_UTILS = {'cp', 'mv', 'rm', 'touch', 'mkdir'}
FIXED_WRAPPERS = {'loop-guard-run', 'loop-journal', 'loop-scan'}
OPENER = re.compile(r"^loop-guard-run\s+<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1$")
_MSYS_DRIVE = re.compile(r'^/([A-Za-z])(?=/|$)')


def _k(s):
    return s.lower() if os.name == 'nt' else s


def _is_abs(p):
    return bool(p) and (p.startswith('/') or re.match(r'^[A-Za-z]:[\\/]', p) is not None)


def _canon(path):
    p = str(path or '').strip().replace('\\', '/')
    if os.name == 'nt':
        m = _MSYS_DRIVE.match(p)
        if m:
            p = m.group(1).upper() + ':' + p[2:]
    return os.path.normpath(p).replace('\\', '/')


def _real(p):
    r = os.path.realpath(p).replace('\\', '/')
    return r[4:] if r.startswith('//?/') else r


def under(p, bases):
    """Strictly under one of bases, by spelling AND after symlinks and junctions."""
    kp = _k(p)
    for b in bases:
        if kp.startswith(_k(b) + '/') and _k(_real(p)).startswith(_k(_real(b)) + '/'):
            return True
    return False


class Ctx(object):
    pass


def load_ctx(d):
    c = Ctx()
    c.home = _canon(os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop'))
    g = (os.environ.get('LOOP_GOAL') or '').strip()
    if not g:
        try:
            with open(os.path.join(c.home, 'current_goal'), encoding='utf-8') as fh:
                lines = fh.read().strip().splitlines()
                g = lines[0].strip() if lines else ''
        except OSError:
            g = ''
    if not re.fullmatch(GOAL_RE, g or ''):
        g = ''
    c.goal, c.full, c.roots, c.wrappers = g, False, [], set()
    c.evidence = c.scratch = None
    cwd = d.get('cwd')
    c.cwd = _canon(cwd) if isinstance(cwd, str) and _is_abs(cwd) else None
    if g:
        c.evidence = c.home + '/goals/' + g + '/evidence'
        c.scratch = c.home + '/scratch/' + g
        try:
            with open(c.home + '/goals/' + g + '/writable.txt', encoding='utf-8') as fh:
                text = fh.read()
        except FileNotFoundError:
            text = None
        if text is not None:
            c.full = True
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = re.match(r'(?i)^wrapper\s*:\s*(.*)$', line)
                if m:
                    for name in re.split(r'[\s,]+', m.group(1).strip()):
                        if (re.fullmatch(r'[A-Za-z0-9._-]+', name)
                                and not re.search(r'ticket|report|tripwire', name, re.I)):
                            c.wrappers.add(name)
                elif _is_abs(line):
                    c.roots.append(_canon(line))
    c.wbases = ([c.evidence] + c.roots) if c.full else []
    c.mbases = list(c.roots) if c.full else []
    c.sbases = ([c.evidence, c.scratch] + c.roots) if c.full else []
    return c


def opnd(tok, ctx):
    """Canonical absolute path of an operand, or None when it cannot be resolved."""
    if not tok or tok.startswith('~') or any(ch in tok for ch in '$`?*\n\r'):
        return None
    p = tok.strip().replace('\\', '/')
    if re.match(r'^[A-Za-z]:(?![\\/])', p):
        return None
    if not _is_abs(p):
        if not ctx.cwd:
            return None
        p = ctx.cwd + '/' + p
    return _canon(p)


def path_ok(tok, ctx, bases):
    p = opnd(tok, ctx)
    return p is not None and under(p, bases)


def script_ok(tok, ctx):
    if not ctx.full or tok is None or tok == '-':
        return REASON_SCRIPT
    return None if path_ok(tok, ctx, ctx.sbases) else REASON_SCRIPT


def interp_script_ok(args, ctx):
    """An interpreter run is one allowed shape: the interpreter name (already in the set),
    then exactly one script path. A flag or flag cluster (-x, --x, +x, --), a module run and a
    third word are not that shape and are denied; no flag table is consulted."""
    if len(args) != 1 or args[0][:1] in ('-', '+'):
        return REASON_SCRIPT
    return script_ok(args[0], ctx)


def strip_redirects(seg):
    """Return (segment without its redirections, [output targets]). Quote aware."""
    keep, targets = [], []
    i, n, q = 0, len(seg), None
    while i < n:
        c = seg[i]
        if q:
            keep.append(c)
            if c == '\\' and q == '"' and i + 1 < n:
                keep.append(seg[i + 1])
                i += 2
                continue
            if c == q:
                q = None
            i += 1
            continue
        if c == '\\' and i + 1 < n:
            keep.append(c)
            keep.append(seg[i + 1])
            i += 2
            continue
        if c in '\'"':
            q = c
            keep.append(c)
            i += 1
            continue
        if c in '<>' or (c == '&' and seg[i + 1:i + 2] == '>'):
            # a file descriptor number glued to the operator belongs to it
            k = len(keep)
            while k > 0 and keep[k - 1].isdigit():
                k -= 1
            if k == 0 or keep[k - 1].isspace():
                del keep[k:]
            j = i + (1 if c == '&' else 0)
            op = ''
            while j < n and seg[j] in '<>':
                op += seg[j]
                j += 1
            if op.endswith('>') and j < n and seg[j] == '|':
                j += 1
            if j < n and seg[j] == '&':
                j += 1
                m = re.match(r'\d+-?|-', seg[j:])
                if m:  # n>&m, n>&-: a descriptor duplicate, no file
                    i = j + m.end()
                    continue
            while j < n and seg[j] in ' \t':
                j += 1
            w, qq = [], None
            while j < n:
                ch = seg[j]
                if qq:
                    if ch == qq:
                        qq = None
                    else:
                        w.append(ch)
                elif ch in '\'"':
                    qq = ch
                elif ch in ' \t':
                    break
                elif ch == '\\' and j + 1 < n:
                    j += 1
                    w.append(seg[j])
                else:
                    w.append(ch)
                j += 1
            if '>' in op or c == '&':
                targets.append(''.join(w))
            keep.append(' ')
            i = j
            continue
        keep.append(c)
        i += 1
    return ''.join(keep), targets


def plain_check(name, args, ctx):
    flags = [a for a in args if a.startswith('-') and a != '-']
    if name == 'sed':
        for f in flags:
            if f.startswith('--in-place') or (not f.startswith('--') and 'i' in f[1:]):
                return REASON_FLAG
    elif name == 'awk':
        for i, a in enumerate(args):  # awk -f FILE runs a script: the script clause judges it
            if a == '-f' and i + 1 < len(args):
                if script_ok(args[i + 1], ctx):
                    return REASON_SCRIPT
            elif a.startswith('-f') and len(a) > 2 and not a.startswith('--'):
                if script_ok(a[2:], ctx):
                    return REASON_SCRIPT
    return None


def file_check(name, args, ctx):
    if not ctx.full:
        return REASON_FILEUTIL
    ops, target, dd, i = [], None, False, 0
    while i < len(args):
        a = args[i]
        if not dd and a == '--':
            dd = True
        elif not dd and a.startswith('-') and a != '-':
            if name in ('cp', 'mv') and a in ('-t', '--target-directory'):
                if i + 1 >= len(args):
                    return REASON_FILEUTIL
                target = args[i + 1]
                i += 1
            elif name in ('cp', 'mv') and a.startswith('--target-directory='):
                target = a.split('=', 1)[1]
            elif name in ('cp', 'mv') and not a.startswith('--') and 't' in a[1:]:
                return REASON_FILEUTIL
        else:
            ops.append(a)
        i += 1
    bases = ctx.mbases if name == 'mkdir' else ctx.wbases
    judged = list(ops)
    if name == 'cp':
        if target is None:
            if len(ops) < 2:
                return REASON_FILEUTIL
            judged = [ops[-1]]  # sources are only read; the destination is what changes
        else:
            judged = [target]
    elif name == 'mv' and target is not None:
        judged = ops + [target]
    if not judged:
        return REASON_FILEUTIL
    for t in judged:
        if not path_ok(t, ctx, bases):
            return REASON_FILEUTIL
    return None


def policy_tokens(toks, ctx):
    k = 0
    while k < len(toks) and is_assignment(toks[k]):
        k += 1
    if k >= len(toks):
        return None  # assignments only
    w, args = toks[k], toks[k + 1:]
    if base(w) in SCRIPT_INTERPRETERS:
        return interp_script_ok(args, ctx)
    if '/' in w or '\\' in w or ':' in w:
        return script_ok(w, ctx)  # a bare script: the script clause alone
    if w in PLAIN_UTILS:
        return plain_check(w, args, ctx)
    if w in FILE_UTILS:
        return file_check(w, args, ctx)
    if w in FIXED_WRAPPERS or w in ctx.wrappers:
        return None
    return REASON_NOTA


def judge_policy(seg, ctx):
    cleaned, _targets = strip_redirects(seg)  # redirections are not part of the command word or operands
    variants = [tokenize(cleaned)]
    if '\\' in cleaned:
        variants.append([x[1:-1] if len(x) > 1 and x[0] == x[-1] and x[0] in '\'"' else x
                         for x in tokenize(cleaned, posix=False)])
    for toks in variants:
        r = policy_tokens(toks, ctx)
        if r:
            return r
    return None


def strip_heredoc_data(cmd):
    """Blank the data lines (and the terminator) of every heredoc inside the body, so that the
    allow set judges commands and not data. The guarded wrapper's own heredoc is not touched.
    A heredoc is recognised only outside quotes, parentheses and backticks, and only when its
    terminator is present. Data of an unquoted heredoc that holds $( or a backtick is kept,
    because the shell would run it."""
    lines = cmd.split('\n')
    q, depth, bt, li = None, 0, False, 0
    while li < len(lines):
        line = lines[li]
        li += 1
        pend, i = [], 0
        while i < len(line):
            c = line[i]
            if q:
                if c == '\\' and q == '"':
                    i += 1
                elif c == q:
                    q = None
            elif c == '\\':
                i += 1
            elif c in '\'"':
                q = c
            elif c == '`':
                bt = not bt
            elif c == '(':
                depth += 1
            elif c == ')':
                depth = max(0, depth - 1)
            elif line.startswith('<<', i) and not line.startswith('<<<', i) and depth == 0 and not bt:
                m = re.match(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2", line[i:])
                if m:
                    if not OPENER.match(line.strip()):
                        pend.append((m.group(3), m.group(1) == '-', m.group(2) != ''))
                    i += m.end() - 1
                else:
                    i += 1
            i += 1
        if q is not None:
            continue
        for word, tabs, quoted in pend:
            j = li
            while j < len(lines):
                t = lines[j].rstrip('\r')
                if (t.lstrip('\t') if tabs else t) == word:
                    break
                j += 1
            if j >= len(lines):
                continue
            for k in range(li, j + 1):
                if k == j or quoted or not re.search(r'\$\(|`', lines[k]):
                    lines[k] = ''
            li = j + 1
    return '\n'.join(lines)


def out(reason):
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                                             'permissionDecision': 'deny',
                                             'permissionDecisionReason': reason}}))
    sys.exit(0)


def run():
    d = json.load(sys.stdin)
    if d.get('tool_name') != 'Bash':
        sys.exit(0)
    ti = d.get('tool_input') or {}
    cmd = ti.get('command') or ''
    if not isinstance(cmd, str):
        raise TypeError('command is not a string')
    if '$(' in cmd or '`' in cmd or '\\' in cmd:
        out(REASON_SUBST)  # ruling 7b: on the whole body, before any segment is split
    for seg in split_segments(cmd):
        why = judge_segment(seg)
        if why:
            out(why)
    ctx = load_ctx(d)
    delim = None
    for seg in split_segments(strip_heredoc_data(cmd)):
        s = seg.strip()
        m = OPENER.match(s)
        if m:  # the guarded heredoc wrapper line: an allowed segment
            delim = m.group(2)
            continue
        if delim is not None and s == delim:  # its terminator line
            delim = None
            continue
        why = judge_policy(seg, ctx)
        if why:
            out(why)
    sys.exit(0)


def main():
    try:
        run()
    except Exception:
        out('writer-git-guard hit an unexpected error, so it fails closed.')


if __name__ == '__main__':
    main()
