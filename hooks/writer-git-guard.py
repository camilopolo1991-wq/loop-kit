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

Never echoes the command. Any Exception fails closed. Register with "onFailure": "block".
"""
import json
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
    for c in cmd:
        if in_s:
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
    cmd = cmd.replace('\\\n', ' ')
    for seg in split_segments(cmd):
        why = judge_segment(seg)
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
