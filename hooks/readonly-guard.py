#!/usr/bin/env python3
"""readonly-guard: PreToolUse hook for loop-scout and loop-reviewer (agent frontmatter).

Second generation, 2026-10-20. The first generation was a denylist of command words;
an independent review drove 37 bypass shapes through it in one sitting (python3 -c,
base64 | sh, cp, sed --in-place, 1> and &> redirects, $VAR targets, another goal's
evidence folder, quote-split words). This version resolves the real command word of
every segment with shlex after walking launcher prefixes, and denies by CLASS:

  * any inline interpreter (python/node/perl/ruby/php/awk system()/sh -c/heredoc script)
  * any decoder piped anywhere (base64 -d, xxd -r, openssl enc -d)
  * any file-changing utility (rm cp mv ln mkdir touch tar patch rsync chmod ...)
  * docker beyond ps/logs/images, psql, any wrapper write subcommand
  * git beyond a read-verb allowlist
  * sed/perl in-place in any flag spelling
  * curl/wget upload flags in any spelling
  * any redirect or tee target that is not /dev/null, &1, &2 or under THIS goal's
    evidence folder, and never a target containing $ ` ~ { (unresolvable at hook time)
  * Write/Edit anywhere but this goal's evidence folder, in the role's own subfolder
  * the writer's evidence subfolder is unreadable to both read-only roles

Config by env (set in the agent frontmatter command line or settings.json env):
  LOOP_HOME   default ~/.loop
  LOOP_GOAL   the dispatched goal id; when set, only that goal's evidence is writable
  LOOP_ROLE   scout | reviewer   (decides the evidence subfolder: T<nn>/ or T<nn>/review/)

Never echoes the command. Any Exception fails closed with the same deny JSON, exit 0.
Register with "onFailure": "block" and a timeout so a crash or hang also blocks.
"""
import json
import os
import re
import shlex
import sys

LOOP_HOME = os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop')


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
LOOP_ROLE = (os.environ.get('LOOP_ROLE') or 'scout').lower()
ROLE = LOOP_ROLE  # P21: run() narrows this from the payload's agent_type

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


def _is_abs(p):
    p = str(p or '')
    return p.startswith('/') or re.match(r'^[A-Za-z]:[\\/]', p) is not None


def effective_role(agent_type):
    """P21. Claude Code puts the agent name in the hook payload: measured, agent_type
    'loop-scout' for a session started with that agent. The auditor's frontmatter
    launches this guard with LOOP_ROLE=reviewer, so the environment alone cannot tell
    the auditor from a task reviewer, and the auditor could not write its own evidence.
    agent_type 'loop-auditor' makes the role auditor. An environment claim of auditor
    is honoured only when the payload carries no agent_type at all, and is otherwise
    read as reviewer, so a scout or reviewer cannot promote itself."""
    if agent_type == 'loop-auditor':
        return 'auditor'
    if agent_type and LOOP_ROLE == 'auditor':
        return 'reviewer'
    return LOOP_ROLE

_goal_part = re.escape(LOOP_GOAL) if LOOP_GOAL else r'[A-Za-z0-9][A-Za-z0-9._-]*'
EVIDENCE_RE = re.compile(r'^' + re.escape(_canon(LOOP_HOME)) + r'/goals/' + _goal_part + r'/evidence/', _RF)
WRITER_SUB_RE = re.compile(r'/goals/[^/]+/evidence/T[^/]*/writer(/|$)', _RF)
REVIEW_SUB_RE = re.compile(r'/goals/[^/]+/evidence/T[^/]*/review(/|$)', _RF)
# P21: the auditor writes only here, and no other role may write anywhere under AUDIT/
AUDIT_RE = re.compile(r'/goals/[^/]+/evidence/AUDIT(/|$)', _RF)
AUDIT_REVIEW_RE = re.compile(r'/goals/[^/]+/evidence/AUDIT/review/', _RF)

REASON_EVIDENCE = 'Read-only role: write only under $LOOP_HOME/goals/<this goal>/evidence/ (scout: T<nn>/, reviewer: T<nn>/review/, auditor: AUDIT/review/).'
REASON_LOOP_CONFIG = ('Read-only role: the loop config file is not readable by a role. '
                      'The loop-* wrappers read named keys from it in-process.')
REASON_WRITER_SUB = 'Read-only role: the writer subfolder evidence/T<nn>/writer/ is not yours to read. Re-measure from the live system.'

# ---------------------------------------------------------------- word classes
FILE_CHANGE_WORDS = {
    'rm', 'mv', 'cp', 'ln', 'mkdir', 'rmdir', 'touch', 'truncate', 'dd', 'shred', 'install',
    'chmod', 'chown', 'chgrp', 'chattr', 'rsync', 'scp', 'sftp', 'tar', 'unzip', 'zip', 'gzip',
    'gunzip', 'bzip2', 'xz', 'zstd', 'patch', 'mkfifo', 'mknod', 'mktemp', 'rename', 'split',
    'csplit', 'sponge', 'dpkg', 'apt', 'apt-get', 'pip', 'pip3', 'npm', 'npx', 'yarn', 'pnpm',
    'make', 'cmake', 'systemctl', 'service', 'crontab', 'at', 'kill', 'pkill', 'killall',
    'mount', 'umount', 'mkfs', 'fdisk', 'parted', 'useradd', 'usermod', 'passwd', 'psql',
    'mysql', 'sqlite3', 'redis-cli', 'ssh',
    # Windows-native change verbs. cmd BUILTINS (del, erase, rd, move, copy, ren) never
    # appear as a binary on PATH, so a POSIX-only list leaves every one of them unguarded:
    # measured, `del C:\tmp\x` was allowed while `rm -rf` was denied.
    'del', 'erase', 'rd', 'move', 'copy', 'xcopy', 'robocopy', 'ren', 'mklink',
    'attrib', 'takeown', 'icacls', 'cacls', 'reg', 'regedit', 'fsutil', 'format',
    'diskpart', 'schtasks', 'sc', 'taskkill', 'net', 'bcdedit', 'cipher',
}
# Denied as a class, not walked like a POSIX launcher: each reaches every verb above
# through an argument string this hook does not parse.
DENIED_LAUNCHERS = {'powershell', 'pwsh', 'cmd', 'wscript', 'cscript'}
REASON_LAUNCHER = ('Read-only role: powershell, pwsh, cmd, wscript and cscript are denied as a '
                   'class. They reach every denied verb through an unparsed argument string.')
DECODER_WORDS = {'base64', 'base32', 'xxd', 'uudecode', 'openssl'}
INTERPRETER_WORDS = {
    'python', 'python2', 'python3', 'node', 'nodejs', 'perl', 'ruby', 'php', 'lua', 'tclsh',
    'sh', 'bash', 'zsh', 'dash', 'ksh', 'fish', 'eval', 'source', '.',
}
AWK_WORDS = {'awk', 'gawk', 'mawk', 'nawk'}
LAUNCHERS = {'sudo', 'command', 'exec', 'nice', 'nohup', 'time', 'stdbuf', 'setsid', 'flock',
             'watch', 'ionice', 'chrt', 'taskset', 'unbuffer', 'caffeinate', 'doas'}
LAUNCHER_VALUE_FLAGS = {
    'sudo': {'-u', '--user', '-g', '--group', '-p', '--prompt', '-r', '--role', '-t', '--type',
             '-C', '--close-from', '-h', '--host'},
    'nice': {'-n', '--adjustment'},
    'stdbuf': {'-i', '--input', '-o', '--output', '-e', '--error'},
    'flock': {'-w', '--wait', '--timeout', '-E', '--conflict-exit-code'},
    'watch': {'-n', '--interval'},
    'ionice': {'-c', '-n', '-p'},
    'chrt': {'-p'},
    'taskset': {'-c', '-p'},
    'exec': {'-a'},
}
ENV_VALUE_FLAGS = {'-u', '--unset', '-C', '--chdir'}
TIMEOUT_VALUE_FLAGS = {'-s', '--signal', '-k', '--kill-after'}
XARGS_VALUE_FLAGS = {'-n', '--max-args', '-L', '--max-lines', '-P', '--max-procs', '-s',
                     '--max-chars', '-I', '--replace', '-a', '--arg-file', '-d', '--delimiter', '-E'}
SHELL_KEYWORDS = {'then', 'do', 'else', 'elif', 'if', 'while', 'until', '!', '{', '}', 'fi', 'done', 'esac'}

DOCKER_READ_SUBS = {'ps', 'logs', 'images', 'version', 'info', 'stats', 'top', 'port', 'diff', 'history'}
WRAPPER_WRITE = {
    'loop-sql': lambda rest: '--write' in rest,
    'loop-n8n': lambda rest: bool(rest) and rest[0] in {'put', 'set-node', 'export', 'activate', 'deactivate', 'delete'},
    'loop-ticket': lambda rest: bool(rest) and rest[0] in {'set', 'note', 'edit', 'field', 'start', 'new', 'import', 'migrate'},
    # P34. A read is --read or --check as the FIRST argument. The old test ('--read' anywhere)
    # denied --check, the auditor's instrument, and allowed a write whose line text held --read.
    'loop-journal': lambda rest: not (bool(rest) and rest[0] in {'--read', '--check'}),
    'graphify': lambda rest: bool(rest) and rest[0] in {'extract', 'update', 'export', 'install', 'uninstall', 'hook', 'watch', 'add', 'merge-graphs', 'clone', 'global', 'cluster-only', 'label', 'save-result', 'reflect', 'prs'},
    'graphify-mcp': lambda rest: True,
}

GIT_READ_VERBS = {
    'status', 'log', 'diff', 'show', 'rev-parse', 'ls-files', 'ls-tree', 'cat-file', 'blame',
    'describe', 'shortlog', 'grep', 'for-each-ref', 'rev-list', 'name-rev', 'show-ref',
    'count-objects', 'var', 'version', 'help', 'merge-base', 'diff-tree', 'diff-files',
    'diff-index', 'ls-remote', 'check-ignore', 'check-attr', 'whatchanged', 'reflog',
}
GIT_SUB_READ = {
    'stash': {'list', 'show'},
    'tag': {'-l', '--list', '-n', '--contains', '--points-at'},
    'worktree': {'list'},
    'submodule': {'status', 'summary'},
    'notes': {'list', 'show'},
    'remote': {'-v', '--verbose', 'show', 'get-url'},
    'branch': {'-a', '-r', '-v', '-vv', '-l', '--list', '--contains', '--merged', '--no-merged',
               '--all', '--remotes', '--verbose', '--show-current', '--points-at', '--sort'},
}
GIT_GLOBAL_VALUE_FLAGS = {'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--exec-path',
                          '--config-env', '--super-prefix'}

SQL_WRITE_RE = re.compile(r'\b(update|insert|delete|commit|alter|drop|create|truncate|grant|revoke|copy|vacuum|begin|set\s+transaction)\b', re.I)

CURL_LONG_UPLOAD = {'--data', '--data-raw', '--data-binary', '--data-urlencode', '--data-ascii',
                    '--json', '--form', '--form-string', '--upload-file', '--request'}
WGET_UPLOAD = {'--post-data', '--post-file', '--method', '--body-data', '--body-file'}

# ---------------------------------------------------------------- helpers
def out(reason):
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                                             'permissionDecision': 'deny',
                                             'permissionDecisionReason': reason}}))
    sys.exit(0)


def split_segments(cmd):
    """Split on top-level ; & | newline ( ) ` outside quotes. Linear scan."""
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


def skip_flags(toks, j, value_flags):
    while j < len(toks) and toks[j].startswith('-') and toks[j] != '-':
        j += 2 if toks[j] in value_flags else 1
    return j


WIN_EXEC_SUFFIXES = ('.exe', '.com', '.cmd', '.bat', '.ps1')


def base(tok):
    """Basename of a command token, separator- and suffix-normalised.

    A bare rsplit('/') is POSIX-only, and on Windows a backslash separator OR an
    executable suffix is INDEPENDENTLY enough to slip a denied verb past it: measured,
    both `C:\\tools\\rm -rf` and `rm.exe -rf` were allowed while bare `rm` was denied.
    Lowercased because Windows command lookup is case-insensitive and every word class
    in this file is lowercase.
    """
    tok = tok.replace('\\', '/').rsplit('/', 1)[-1]
    # drive-relative spelling with no separator, e.g. C:rm
    tok = tok.rsplit(':', 1)[-1].lower()
    for suf in WIN_EXEC_SUFFIXES:
        if tok.endswith(suf) and len(tok) > len(suf):
            return tok[:-len(suf)]
    return tok


def resolve(toks, start, acc, depth=0):
    """Append (cmdword, rest_tokens) for every real command reachable from toks[start:],
    walking launchers, env, timeout, xargs, find -exec, and recursing into inline scripts
    of sh/bash/env -S. Depth-bounded. A raw token (before shlex) is not available here, so
    metacharacter checks happen on the segment text in check_segment()."""
    if depth > 6:
        acc.append(('__too_deep__', []))
        return
    i = start
    n = len(toks)
    while i < n and is_assignment(toks[i]):
        i += 1
    if i >= n:
        return
    while i < n:
        w = toks[i]
        b = base(w).lower()
        if b in SHELL_KEYWORDS:
            i += 1
            while i < n and is_assignment(toks[i]):
                i += 1
            continue
        if b in LAUNCHERS:
            i = skip_flags(toks, i + 1, LAUNCHER_VALUE_FLAGS.get(b, set()))
            while i < n and is_assignment(toks[i]):
                i += 1
            continue
        if b == 'env':
            j = i + 1
            while j < n and toks[j].startswith('-') and toks[j] != '-':
                f = toks[j]
                if f in ('-S', '--split-string') or f.startswith('--split-string='):
                    inner = f.split('=', 1)[1] if '=' in f else (toks[j + 1] if j + 1 < n else '')
                    for s in split_segments(inner):
                        resolve(tokenize(s), 0, acc, depth + 1)
                    return
                j += 2 if f in ENV_VALUE_FLAGS else 1
            while j < n and is_assignment(toks[j]):
                j += 1
            i = j
            continue
        if b == 'timeout':
            j = skip_flags(toks, i + 1, TIMEOUT_VALUE_FLAGS)
            j += 1  # DURATION
            i = j
            continue
        if b == 'xargs':
            j = skip_flags(toks, i + 1, XARGS_VALUE_FLAGS)
            if j >= n:
                acc.append(('xargs', []))  # bare xargs runs echo; harmless
                return
            i = j
            continue
        if b == 'find':
            # find ... -exec CMD ... ; or -execdir / -ok / -delete
            rest = toks[i + 1:]
            if '-delete' in rest:
                acc.append(('rm', rest))
            for k, t in enumerate(rest):
                if t in ('-exec', '-execdir', '-ok', '-okdir') and k + 1 < len(rest):
                    acc.append(('find', rest[:k]))  # C2: the find's own targets are judged too
                    resolve(rest, k + 1, acc, depth + 1)
                    return
            acc.append(('find', rest))
            return
        if b in ('sh', 'bash', 'zsh', 'dash', 'ksh'):
            j = i + 1
            saw_c = False
            while j < n and toks[j].startswith('-') and toks[j] != '-':
                f = toks[j]
                if f in ('-c', '--command') or (not f.startswith('--') and 'c' in f[1:]):
                    saw_c = True
                j += 1
            if saw_c and j < n:
                acc.append(('__inline__', [b]))
                for s in split_segments(toks[j]):
                    resolve(tokenize(s), 0, acc, depth + 1)
                return
            acc.append((b, toks[i + 1:]))
            return
        acc.append((b, toks[i + 1:]))
        return


def interpreter_reason(word, rest, seg):
    if word == '__inline__':
        return 'Read-only role: no inline shell scripts (sh -c, bash -c, eval). Run commands directly.'
    if word == '__too_deep__':
        return 'Read-only role: command nesting too deep to judge.'
    if word in ('eval', 'source', '.'):
        return 'Read-only role: no eval or source.'
    if word in INTERPRETER_WORDS:
        # a script FILE under evidence or scratch may run; anything inline, stdin or heredoc may not
        flags = [t for t in rest if t.startswith('-')]
        if any(f in ('-c', '-e', '-E', '-r', '-') or (not f.startswith('--') and len(f) > 1 and any(ch in f[1:] for ch in 'ceE')) for f in flags):
            return 'Read-only role: no inline interpreter code (-c/-e). Write the script into evidence/ with the Write tool and run that file.'
        if '<<' in seg or ' - ' in (' ' + ' '.join(rest) + ' ') or not rest:
            return 'Read-only role: no interpreter script from stdin or heredoc. Write the script into evidence/ and run that file.'
        script = next((t for t in rest if not t.startswith('-')), '')
        p = os.path.normpath(script)
        if not (EVIDENCE_RE.match(_canon(script)) or _canon(script).startswith(_canon(LOOP_HOME) + '/scratch/') or p.startswith('/usr/') or p.startswith('/opt/')):
            return 'Read-only role: interpreter scripts run only from evidence/, scratch/, /usr or /opt paths.'
    if word in AWK_WORDS and ('system(' in seg or 'getline' in seg):
        return 'Read-only role: awk may not call system() or getline from a command.'
    return None


def git_reason(rest):
    """rest = tokens after the git word. Allow only read verbs."""
    j = 0
    while j < len(rest) and rest[j].startswith('-'):
        t = rest[j]
        if '=' in t:
            j += 1
        elif t in GIT_GLOBAL_VALUE_FLAGS:
            j += 2
        else:
            j += 1
    if j >= len(rest):
        return None
    verb = rest[j]
    args = rest[j + 1:]
    if verb in GIT_READ_VERBS:
        return None
    if verb in GIT_SUB_READ:
        allowed = GIT_SUB_READ[verb]
        if verb == 'branch':
            if all(a.split('=', 1)[0] in allowed for a in args):
                return None
            return 'Read-only role: git branch may only list.'
        if args and args[0] in allowed:
            return None
        return 'Read-only role: git %s may only read (%s).' % (verb, ', '.join(sorted(allowed)))
    return 'Read-only role: git read verbs only (status, log, diff, show, rev-parse, ls-files...).'


def curl_wget_reason(word, rest):
    if word == 'curl':
        for k, t in enumerate(rest):
            if t.startswith('--'):
                name = t.split('=', 1)[0]
                if name in CURL_LONG_UPLOAD:
                    if name == '--request':
                        val = t.split('=', 1)[1] if '=' in t else (rest[k + 1] if k + 1 < len(rest) else '')
                        if val.upper() in ('GET', 'HEAD'):
                            continue
                    return 'Read-only role: no write requests (curl upload flag).'
            elif t.startswith('-') and len(t) > 1:
                cluster = t[1:]
                if any(ch in cluster for ch in 'dFT'):
                    return 'Read-only role: no write requests (curl -d/-F/-T).'
                if 'X' in cluster:
                    val = cluster.split('X', 1)[1] or (rest[k + 1] if k + 1 < len(rest) else '')
                    if val.upper() not in ('GET', 'HEAD'):
                        return 'Read-only role: no write requests (curl -X).'
    if word == 'wget':
        for t in rest:
            if t.split('=', 1)[0] in WGET_UPLOAD:
                return 'Read-only role: no write requests (wget upload flag).'
    return None


def sed_perl_reason(word, rest):
    if word == 'sed':
        for t in rest:
            if t.startswith('--in-place') or (t.startswith('-') and not t.startswith('--') and 'i' in t[1:]):
                return 'Read-only role: no in-place edits (sed -i).'
    if word == 'perl':
        for t in rest:
            if t.startswith('-') and not t.startswith('--') and 'i' in t[1:]:
                return 'Read-only role: no in-place edits (perl -i).'
    return None


LISTING_WORDS = {'ls', 'find', 'tree', 'dir'}
REASON_LISTING = ('Read-only role: a listing under $LOOP_HOME/goals/ may target only the role\'s own '
                  'evidence folders (scout: this goal\'s evidence/T<nn>/ and below, not review/ or writer/; '
                  'reviewer: evidence/T<nn>/review/ and below; auditor: evidence/T<nn>/, '
                  'evidence/T<nn>/review/, evidence/AUDIT/ and below). The writer subfolder is never listed.')
_GOALS_ROOT_RE = re.compile(r'^' + re.escape(_canon(LOOP_HOME)) + r'/goals(/|$)', _RF)
_HOME_CHILD_RE = re.compile(r'^' + re.escape(_canon(LOOP_HOME)) + r'/([^/]*)(/|$)', _RF)
_LIST_EVIDENCE_RE =re.compile(r'^' + re.escape(_canon(LOOP_HOME)) + r'/goals/' + _goal_part + r'/evidence/', _RF)


def listing_targets(word, rest):
    """C2. The path arguments of a listing command, as written. No disk access."""
    if word == 'find':
        j = 0
        while j < len(rest):
            if rest[j] in ('-H', '-L', '-P') or re.fullmatch(r'-O\d', rest[j]):
                j += 1
            elif rest[j] == '-D':
                j += 2
            else:
                break
        ts = []
        while j < len(rest) and not (rest[j].startswith('-') or rest[j] in ('(', '!', ',')):
            ts.append(rest[j])
            j += 1
        return ts
    ts, past = [], False
    for t in rest:
        if past:
            ts.append(t)
        elif t == '--':
            past = True
        elif t.startswith('-') and t != '-':
            continue
        else:
            ts.append(t)
    return ts


REASON_LISTING_UNRESOLVED = ('Read-only role: a listing target with $ or a backtick (other than a leading '
                             '~, $HOME, ${HOME}, $LOOP_HOME, ${LOOP_HOME}) cannot be judged and is denied.')
_LEAD_VAR_RE = re.compile(r'^(~|\$HOME|\$\{HOME\}|\$LOOP_HOME|\$\{LOOP_HOME\})(?=/|$)')


def _expand_listing_target(tgt):
    """C2 r3. Expand ONE leading ~, $HOME, ${HOME}, $LOOP_HOME or ${LOOP_HOME} to the home and
    loop home this hook already knows. Returns (target, None) or (None, reason). A leading ~
    followed by anything but / (a ~user form) and any other $ or backtick are unresolvable
    at hook time and fail closed. ~ elsewhere and { are literal characters."""
    m = _LEAD_VAR_RE.match(tgt)
    if m:
        tok = m.group(1)
        if tok in ('$LOOP_HOME', '${LOOP_HOME}'):
            lead = LOOP_HOME
        else:
            lead = os.environ.get('HOME') or os.path.expanduser('~')
        tgt = lead + tgt[m.end():]
    elif tgt.startswith('~'):
        return None, REASON_LISTING_UNRESOLVED
    if '$' in tgt or '`' in tgt:
        return None, REASON_LISTING_UNRESOLVED
    return tgt, None


def listing_target_reason(raw):
    """C2. Judge one listing target by its string. A target under $LOOP_HOME/goals/ is
    allowed only inside the role's own pattern. Outside the goals folder, relative, or
    absent: not judged here (the hook's other checks stand as before)."""
    tgt = strip_quotes(raw)
    if not tgt:
        return None
    tgt, why = _expand_listing_target(tgt)
    if why:
        return why
    if not _is_abs(tgt):
        return None
    p = _canon(tgt)
    special = '*?['  # the only wildcards inside a target; ~ (not leading) and { are literal
    hm = _HOME_CHILD_RE.match(p)
    if not hm:
        return None  # literal prefix is not the loop home: the verdict is the hook's as before
    if any(ch in hm.group(1) for ch in special):
        # the segment where "goals" belongs holds a wildcard: it could be the goals
        # folder and cannot be resolved here, so it is denied
        return REASON_LISTING
    if not _GOALS_ROOT_RE.match(p):
        return None
    if any(ch in p for ch in special):
        return REASON_LISTING  # below goals: could expand into review/ or writer/
    m = _LIST_EVIDENCE_RE.match(p)
    if not m:
        return REASON_LISTING
    segs = p[m.end():].split('/')
    low = [s.lower() if os.name == 'nt' else s for s in segs]
    # fold case the way the hook's other path checks do (_RF): same folder on Windows
    first, tail = low[0], low[1:]
    t_prefix, audit = ('t', 'audit') if os.name == 'nt' else ('T', 'AUDIT')
    if 'writer' in tail:
        return REASON_LISTING
    if ROLE == 'auditor':
        return None if (first == audit or first.startswith(t_prefix)) else REASON_LISTING
    if not first.startswith(t_prefix):
        return REASON_LISTING
    if ROLE == 'reviewer':
        return None if tail[:1] == ['review'] else REASON_LISTING
    return REASON_LISTING if 'review' in tail else None


def check_segment(seg):
    seg = seg.replace('\\\n', ' ')
    if re.search(r"\$'", seg):
        return 'Read-only role: ANSI-C quoting ($\'...\') is not judged and is denied.'
    acc = []
    resolve(tokenize(seg.strip()), 0, acc)
    # A Windows path separator IS shlex's escape character, so POSIX tokenization welds
    # `C:\tools\rm` into `C:toolsrm` and the verb disappears before any basename runs.
    # Judge the non-POSIX tokenization too and take the UNION: strictly more denials,
    # never fewer. Gated on a backslash being present so no POSIX-only segment changes
    # verdict, which keeps the pre-existing truth table intact.
    if '\\' in seg:
        extra = []
        resolve(tokenize(seg.strip(), posix=False), 0, extra)
        acc.extend([x for x in extra if x not in acc])
    # metacharacters in a command-word position cannot be resolved at hook time
    toks_raw = seg.strip().split()
    k = 0
    while k < len(toks_raw) and is_assignment(toks_raw[k]):
        k += 1
    if k < len(toks_raw):
        cw = toks_raw[k]
        if any(ch in cw for ch in '$`{?*[') and base(cw).lower() not in SHELL_KEYWORDS:
            return 'Read-only role: a command word with $ ` { ? * [ cannot be judged and is denied.'
    for word, rest in acc:
        if word in LISTING_WORDS:
            for t in listing_targets(word, rest):
                r = listing_target_reason(t)
                if r:
                    return r
        if word in ('xargs', 'find'):
            continue
        r = interpreter_reason(word, rest, seg)
        if r:
            return r
        if word in DENIED_LAUNCHERS:
            return REASON_LAUNCHER
        if word in FILE_CHANGE_WORDS:
            return 'Read-only role: no file or system changes (%s).' % word
        if word in DECODER_WORDS:
            if word == 'openssl' and not any(t in ('enc', 'base64') for t in rest):
                pass
            else:
                return 'Read-only role: no decoders (base64 -d, xxd -r, openssl enc). Encoded commands are not judged.'
        if word == 'docker':
            sub = next((t for t in rest if not t.startswith('-')), '')
            if sub not in DOCKER_READ_SUBS:
                return 'Read-only role: docker ps/logs/images/stats only. No exec, cp, run, restart.'
        if word == 'git' or word.startswith('git-'):
            if word.startswith('git-'):
                verb_rest = [word[4:]] + rest
            else:
                verb_rest = rest
            r = git_reason(verb_rest)
            if r:
                return r
        if word in WRAPPER_WRITE and WRAPPER_WRITE[word](rest):
            return 'Read-only role: %s write subcommands are the writer\'s.' % word
        if word == 'loop-sql' and SQL_WRITE_RE.search(' '.join(rest)):
            return 'Read-only role: SQL text with a write verb (UPDATE/INSERT/DELETE/COMMIT/DDL) is denied even without --write.'
        r = curl_wget_reason(word, rest)
        if r:
            return r
        r = sed_perl_reason(word, rest)
        if r:
            return r
        if word == 'tee':
            for t in rest:
                if t.startswith('-'):
                    continue
                r = target_reason(t)
                if r:
                    return r
    return None


_TARGET_TOKEN = r'("[^"]*"|\'[^\']*\'|[^\s;&|)]+)'
REDIRECT_RE = re.compile(r'(?:\d*|&)>{1,2}\|?\s*' + _TARGET_TOKEN)


def strip_quotes(s):
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        return s[1:-1]
    return s


def _fwd(path):
    """Path with a single, forward-slash separator convention.

    os.path.normpath emits BACKSLASHES on Windows, and EVIDENCE_RE is built by appending
    a literal '/goals/.../evidence/' to a normpath'd LOOP_HOME. That produces a
    mixed-separator pattern which cannot match any real path, so role_may_write()
    returned False for every path and the guard failed CLOSED: scout and reviewer could
    not write their own evidence at all. Normalise both sides to '/' instead.
    """
    return os.path.normpath(path).replace('\\', '/')


def role_may_write(path):
    p = _canon(path)
    if not EVIDENCE_RE.match(p):
        return False
    if WRITER_SUB_RE.search(p):
        return False
    if ROLE == 'auditor':
        return bool(AUDIT_REVIEW_RE.search(p))
    if AUDIT_RE.search(p):
        return False
    if ROLE == 'reviewer':
        return bool(REVIEW_SUB_RE.search(p))
    return not REVIEW_SUB_RE.search(p)


def target_reason(raw_target):
    tgt = strip_quotes(raw_target)
    if tgt in ('/dev/null', '&1', '&2', '/dev/stderr', '/dev/stdout'):
        return None
    if any(ch in tgt for ch in '$`~{'):
        return 'Read-only role: a redirect target with $ ` ~ { cannot be judged and is denied.'
    if not _is_abs(tgt):
        return 'Read-only role: redirect targets must be absolute paths under this goal\'s evidence/.'
    if not role_may_write(tgt):
        return REASON_EVIDENCE
    return None


def redirect_reason(cmd):
    cmd = cmd.replace('\\\n', ' ')
    for m in REDIRECT_RE.finditer(cmd):
        r = target_reason(m.group(1))
        if r:
            return r
    return None


def is_loop_config(path):
    """P26. The loop config file, in any spelling: C:/, /c/, backslashes, case, a
    traversal that lands on it. Measured before this change: the Read tool reached
    it from a read-only role with no denial, while Bash was denied only because
    pretool-guard's .env rule happens to match the name."""
    if not path:
        return False
    p = _canon(path)
    want = _canon(os.path.join(LOOP_HOME, 'config.env'))
    return p.lower() == want.lower() if os.name == 'nt' else p == want


def mentions_writer_sub(text):
    return bool(WRITER_SUB_RE.search(text or ''))


def run():
    global ROLE
    d = json.load(sys.stdin)
    tool = d.get('tool_name')
    ROLE = effective_role(d.get('agent_type') or '')
    ti = d.get('tool_input') or {}
    if not isinstance(ti, dict):
        raise TypeError('tool_input is not a dict')
    if tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        fp = ti.get('file_path') or ti.get('notebook_path') or ''
        if not isinstance(fp, str) or not fp:
            out(REASON_EVIDENCE)
        if not role_may_write(fp):
            out(REASON_EVIDENCE)
        sys.exit(0)
    if tool == 'Read':
        fp = ti.get('file_path') or ''
        if mentions_writer_sub(str(fp)) or mentions_writer_sub(_canon(fp)):
            out(REASON_WRITER_SUB)
        if is_loop_config(fp):
            out(REASON_LOOP_CONFIG)
        sys.exit(0)
    if tool == 'Bash':
        cmd = ti.get('command') or ''
        if not isinstance(cmd, str):
            raise TypeError('command is not a string')
        cmd = cmd.replace('\\\n', ' ')
        if mentions_writer_sub(cmd) or mentions_writer_sub(cmd.replace('\\', '/')):
            out(REASON_WRITER_SUB)
        for seg in split_segments(cmd):
            why = check_segment(seg)
            if why:
                out(why)
        why = redirect_reason(cmd)
        if why:
            out(why)
        sys.exit(0)
    # Any other tool reaching this hook is outside its matcher: deny rather than guess.
    out('Read-only role: tool %s is not judged by this guard and is denied.' % tool)


def main():
    try:
        run()
    except Exception:
        out('readonly-guard hit an unexpected error, so it fails closed.')


if __name__ == '__main__':
    main()
