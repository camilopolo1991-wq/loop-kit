#!/usr/bin/env python3
"""loop-scan: secret and name scan with its own control. Exit 1 on any hit.

  loop-scan                      the staged diff (git diff --cached, added lines) of the current repo
  loop-scan --range A..B         the added lines of a commit range (use before a push: origin/<RECORD_BRANCH>..HEAD, default engine-record)
  loop-scan FILE [FILE ...]      whole files (a report before it is sent, an export before it is committed)

It first runs the same detector on a built-in control that must fire in every category.
If the control does not fire, the scan is broken and it exits 3.
KIT12A-01 S51: a second scanner, gitleaks (--redact, a rule set carried in this file and handed to it at run time
through GITLEAKS_CONFIG_TOML, never a file kept), runs over the same input; its own control must fire (else exit 3).
The binary is LOOP_GITLEAKS, else gitleaks on PATH. Not found or not runnable: gitleaks=UNKNOWN and exit 4, never a pass.
Prints counts per category and file:line locations only, never the matched text.
Bare UUIDs and sha256 digests are not hits: they were noise in every PB scan.
A line containing the token loop-scan:control is a deliberate test string and is skipped; the count of skipped lines is printed.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import loop_redact  # noqa: E402
from loop_redact import Redactor  # noqa: E402

# GATE-01 T05: loop_redact.py's api-key pattern needs a \b immediately before
# "api", which never holds after an underscore (e.g. SERVICE_API_KEY, or a
# lowercase service_api_key). Add a supplemental pattern here: it fires only
# when an underscore precedes "api", on top of (never in place of) the entries
# already in loop_redact.PATTERNS (19 at KIT12A-01, counted by len(PATTERNS)
# before this append; this entry is the 20th).
loop_redact.PATTERNS.append((
    re.compile(r'(?i)(?<=_)(api[_ -]?key\b["\']?\s*[:=]\s*["\']?)(?!\[[A-Z_]+\])[A-Za-z0-9_\-]{16,}'),
    r'\1[REDACTED]',
))

CONTROL = ('x-n8n-api-key: abcdefghijklmnop12345\n'  # loop-scan:control
           'token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJlMTIzNDU2\n'  # loop-scan:control
           'API_SECRET=zz9zzzzzzzzzzzzz\n')  # loop-scan:control


NAME_TAG = '[NAME]'  # the tag loop_redact.Redactor puts where a name was
REMOTE_TAG = '[GIT_REMOTE]'  # the tag loop_redact.PATTERNS put where a github remote was


def tag_path_re():
    """KIT-05 C8. A redactor tag (the name tag or the remote tag) adjacent to a path separator,
    on either side. Each tag is counted once. A home-shaped path holding the name tag is the
    path category's; main() counts a tag only on a line the path category did not match."""
    alts = '|'.join(re.escape(t) for t in (NAME_TAG, REMOTE_TAG))
    return re.compile(r'(?:(?<=[/\\])(?:%s)|(?:%s)(?=[/\\]))' % (alts, alts))


def tag_control_line():
    """The tag control line, built at run time from the tags and joined to separators here."""
    return 'masked ' + 'a' + '/' + NAME_TAG + '/x ' + 'b' + '/' + REMOTE_TAG + '/y\n'


def home_parent_parts():
    """(drive letter or '', [segments]) of the folder holding the home directory."""
    home = os.path.expanduser('~').replace('\\', '/').rstrip('/')
    parent = home.rpartition('/')[0]
    drive = ''
    if len(parent) >= 2 and parent[1] == ':':
        drive, parent = parent[0], parent[2:]
    return drive, [s for s in parent.split('/') if s]


def masked_home_re():
    """KIT-02 C3. The home path with its user segment already replaced by the name tag,
    in any spelling: drive letter with slash or backslash, or the /c/ form. None when the
    home has no parent folder to match."""
    drive, segs = home_parent_parts()
    if not drive and not segs:
        return None
    pre = '(?:%s:|/%s)' % (re.escape(drive), re.escape(drive)) if drive else ''
    body = ''.join('[/\\\\]+' + re.escape(s) for s in segs)
    return re.compile(r'(?<![\w])' + pre + body + r'[/\\]+' + re.escape(NAME_TAG), re.I)


def masked_home_line():
    """The path control line, built at run time from the home; never written out in the source."""
    drive, segs = home_parent_parts()
    if not drive and not segs:
        return None  # a home with no user segment to mask: no control line can be built
    return 'masked ' + (drive + ':' if drive else '') + ''.join('/' + s for s in segs) + '/' + NAME_TAG + '/x\n'


# Built at import from the home. None when the home gives no user segment to mask.
PATH_CONTROL = masked_home_line()
CONTROL = CONTROL + (PATH_CONTROL or '')


def tilde_home(path):
    """KIT-04 C4. The path with the home (HOME, else USERPROFILE, forward-slash form, case-insensitive
    on the drive letter only) replaced by ~. A path outside the home is returned unchanged."""
    home = (os.environ.get('HOME') or os.environ.get('USERPROFILE') or '').replace('\\', '/').rstrip('/')
    if not home:
        return path
    head = path[:len(home)]
    if head[:1].lower() + head[1:] == home[:1].lower() + home[1:] and (len(path) == len(home) or path[len(home)] == '/'):
        return '~' + path[len(home):]
    return path


def hits(r, text):
    before = r.count
    r.redact(text)
    return r.count - before


USAGE = """usage: loop-scan [--help]
       loop-scan                the staged diff (git diff --cached, added lines)
       loop-scan --range A..B   the added lines of a commit range (RECORD_BRANCH default engine-record)
       loop-scan FILE [FILE ...]  whole files
       second scanner: gitleaks (LOOP_GITLEAKS, else PATH); summary field gitleaks=<n> or gitleaks=UNKNOWN
       exit: 0 clean, 1 a hit (either scanner), 2 usage or repo failure, 3 a control did not fire,
             4 gitleaks absent or unrunnable (gitleaks=UNKNOWN, never a pass; wins over 1)"""


def resolve_repo(cwd_only=False):
    """P28. The repo whose diff is scanned: the current work tree, else the record
    repo from config. Run outside any repo, `git diff` errored, its stdout was
    empty, and the scan printed lines=0 hits=0 and exited 0: a false clean bill.
    KIT-11 C9: with cwd_only (the bare call, no argument) there is no config fallback:
    a folder outside any repo is a refusal, never a scan of the record repo.
    Returns (path, 'cwd' | 'config') or (None, reason)."""
    p = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if p.returncode == 0 and p.stdout.strip():
        return p.stdout.strip(), 'cwd'
    if cwd_only:
        return None, 'the current folder is outside any git repository'
    try:
        import loop_conf
        er = (loop_conf.load().get('ENGINE_RECORD_DIR') or '').strip()
    except Exception as e:  # a config that cannot be read is not a clean scan
        return None, 'config unreadable: %s' % e
    if not er:
        return None, 'not inside a git work tree and ENGINE_RECORD_DIR is not set'
    q = subprocess.run(['git', '-C', er, 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if q.returncode != 0:
        return None, 'not inside a git work tree and ENGINE_RECORD_DIR=%s is not one either' % er
    return q.stdout.strip(), 'config'


def git_diff(repo, extra):
    """The diff text, or None when git itself failed. Never an empty string for a failure."""
    p = subprocess.run(['git', '-C', repo, 'diff', '-U0'] + extra, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        err = p.stderr.decode('utf-8', 'replace').strip().splitlines()
        print('loop-scan: git diff failed in %s, rc %d: %s' % (repo, p.returncode, err[0] if err else 'no message'))
        return None
    return p.stdout.decode('utf-8', 'replace')


class GitleaksUnknown(Exception):
    """The second scanner could not give a reading. The text is a fixed reason, never a path or a value."""


GL_COMMON = ['--redact', '--no-banner', '--log-level', 'error', '-f', 'json', '-r', '-', '--exit-code', '2']
GL_TIMEOUT = 300


def gitleaks_toml():
    """KIT12A-01 S51. The rule set handed to gitleaks at run time (GITLEAKS_CONFIG_TOML), built from
    loop_redact.KEYNAME_SUFFIXES: the gitleaks defaults on their own gave 0 on the planted shape. It extends the
    defaults, adds one key-name rule (a 20+ character value of the key alphabet; the allowlist on the secret drops a
    value with no digit, a value with no letter, a path-like value and a bare UUID, which is what the lookaheads do
    in loop_redact), and skips a line holding the control token like the pattern scan does. No file is kept."""
    rx = (r'(?i)\b[a-z0-9_]*(?:' + loop_redact.KEYNAME_ALT +
          r')["\']?[ \t]*[:=][ \t]*["\']?([A-Za-z0-9+/=_-]{20,})')
    q = json.dumps
    return '\n'.join([
        '[extend]', 'useDefault = true', '',
        '[[allowlists]]', 'regexTarget = "line"', 'regexes = [%s]' % q('loop-scan:control'), '',
        '[[rules]]', 'id = "loop-keyname-assignment"', 'description = "key-name assignment, long random value"',
        'regex = %s' % q(rx), 'secretGroup = 1', '',
        '[[rules.allowlists]]', 'regexTarget = "secret"',
        'regexes = [%s, %s, %s, %s]' % (q(r'^[^0-9]*$'), q(r'^[^A-Za-z]*$'), q(r'^/'),
                                        q(r'(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')), ''])


def gitleaks_bin():
    """LOOP_GITLEAKS when set (never a fallback to PATH then), else gitleaks on PATH. Raises GitleaksUnknown."""
    given = os.environ.get('LOOP_GITLEAKS', '').strip()
    if given:
        if not os.path.isfile(given):
            raise GitleaksUnknown('LOOP_GITLEAKS does not name a file')
        return given
    found = shutil.which('gitleaks')
    if not found:
        raise GitleaksUnknown('gitleaks not found (LOOP_GITLEAKS unset, not on PATH)')
    return found


def gitleaks_run(binpath, tail):
    """Run gitleaks with the carried rules; return [(file, line)] of its findings. Everything else in its report
    (the redacted match, the rule, the commit) is dropped here, in process. Raises GitleaksUnknown."""
    env = dict(os.environ)
    env.pop('GITLEAKS_CONFIG', None)  # --config and this variable would outrank the carried rule set
    env['GITLEAKS_CONFIG_TOML'] = gitleaks_toml()
    try:
        p = subprocess.run([binpath] + tail[:1] + GL_COMMON + tail[1:], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           stdin=subprocess.DEVNULL, env=env, timeout=GL_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        raise GitleaksUnknown('gitleaks could not be run')
    if p.returncode not in (0, 2):
        raise GitleaksUnknown('gitleaks exited %d' % p.returncode)
    try:
        report = json.loads(p.stdout.decode('utf-8', 'replace') or 'null')
    except ValueError:
        report = None
    if not isinstance(report, list):
        raise GitleaksUnknown('gitleaks gave no readable report')
    found = [(str(x.get('File', '')).replace('\\', '/'), int(x.get('StartLine') or 0)) for x in report if isinstance(x, dict)]
    if (p.returncode == 2) != bool(found):
        raise GitleaksUnknown('gitleaks exit code and report disagree')
    return found


def gitleaks_control(binpath):
    """The second scanner's own control: its rule set, run over a throwaway file whose one line is built here from
    parts, must report a finding. The file is deleted after the run. Raises GitleaksUnknown when gitleaks fails."""
    d = tempfile.mkdtemp(prefix='loop-scan-gl-')
    try:
        fx = os.path.join(d, 'control.txt')
        with open(fx, 'w', encoding='utf-8') as fh:
            fh.write('control_' + 'access_key' + '=' + 'zz9' + 'z' * 20 + '\n')
        return len(gitleaks_run(binpath, ['dir', fx])) >= 1
    finally:
        shutil.rmtree(d, ignore_errors=True)


def gitleaks_scan(mode, files, repo, rng):
    """(count, [file:line]) from gitleaks over the same input loop-scan scanned: the FILE arguments (files), the
    commit range (range) or the staged change (bare). Raises GitleaksUnknown. Not run by a test here for the range
    and bare modes (they need a repository)."""
    binpath = gitleaks_bin()
    if not gitleaks_control(binpath):
        return None, []
    locs = []
    if mode == 'files':
        for f in files:
            locs += [(f, ln) for _, ln in gitleaks_run(binpath, ['dir', f])]
    elif mode == 'range':
        locs = gitleaks_run(binpath, ['git', '--log-opts', rng, repo])
    else:
        locs = gitleaks_run(binpath, ['git', '--staged', repo])
    return len(locs), ['%s:%d' % x for x in locs]


def main():
    args = sys.argv[1:]
    if args and args[0] in ('--help', '-h'):
        print(USAGE)
        return 0
    r = Redactor()
    ctrl = Redactor()
    ctrl.redact(CONTROL)
    if ctrl.by_kind.get('pattern', 0) < 3:
        print('loop-scan: CONTROL DID NOT FIRE - scanner broken')
        return 3
    path_re = masked_home_re()
    # The path half of the control attests itself like the other categories: the scanner's own
    # path detection runs over the built-in CONTROL text and must find the masked line there.
    if path_re is None or not path_re.search(CONTROL):
        print('loop-scan: PATH CONTROL DID NOT FIRE - scanner broken')
        return 3
    tag_re = tag_path_re()
    if len(tag_re.findall(tag_control_line())) != 2:
        print('loop-scan: TAG CONTROL DID NOT FIRE - scanner broken')
        return 3
    name_control ='n/a (no names file)'
    if r.names_re is not None:
        ok = bool(r.names_re.search(' ' + r.names_list[-1] + ' '))
        # KIT12A-01 S78: second probe, the joined form (no separator) of the first two single-token entries
        # (distinct ignoring case, as the redactor builds its pairs). Fewer than two: the single probe, said so.
        singles = []
        for n in r.names_list:
            if len(n.split()) == 1 and all(n.casefold() != s.casefold() for s in singles):
                singles.append(n)
        if len(singles) >= 2:
            ok = ok and bool(r.names_re.search(' ' + singles[0] + singles[1] + ' '))
            name_control = 'fired' if ok else 'NOT FIRED'
        else:
            name_control = 'fired(single-probe,fewer-than-two-single-token-entries)' if ok else 'NOT FIRED'
        if not name_control.startswith('fired'):
            print('loop-scan: NAME CONTROL DID NOT FIRE - scanner broken')
            return 3
    units = []
    where = ''
    if not args or args[0] == '--range':
        repo, src = resolve_repo(cwd_only=not args)
        if repo is None:
            print('loop-scan: ' + src + '. Exit 2, nothing was scanned.')
            return 2
        where = ' repo=%s (%s)' % (tilde_home(repo.replace('\\', '/')), src)
    if args and args[0] == '--range':
        if len(args) < 2 or args[1].startswith('-'):
            print(USAGE)
            return 2
        diff = git_diff(repo, [args[1]])
        if diff is None:
            return 2
        units = parse_diff(diff)
    elif args:
        for f in args:
            with open(f, encoding='utf-8', errors='replace') as fh:
                for i, line in enumerate(fh, 1):
                    units.append((f, i, line))
    else:
        diff = git_diff(repo, ['--cached'])
        if diff is None:
            return 2
        units = parse_diff(diff)
    locs = []
    skipped = 0
    for f, i, line in units:
        if 'loop-scan:control' in line:
            skipped += 1
            continue
        n = hits(r, line)
        if path_re is not None:
            p = len(path_re.findall(line))
            if p:
                r._bump('path', p)
                n += p
        if not (path_re is not None and p):
            t = len(tag_re.findall(line))
            if t:
                r._bump('tag', t)
                n += t
        if n:
            locs.append(f'{f}:{i}')
    mode = 'range' if args and args[0] == '--range' else ('files' if args else 'bare')
    gl_n, gl_locs, gl_why = None, [], ''
    try:
        gl_n, gl_locs = gitleaks_scan(mode, args, repo if mode != 'files' else None, args[1] if mode == 'range' else None)
        if gl_n is None:
            print('loop-scan: GITLEAKS CONTROL DID NOT FIRE - scanner broken')
            return 3
    except GitleaksUnknown as e:
        gl_why = str(e)
    parts = ['loop-scan: control=fired name_control=%s lines=%d control_lines_skipped=%d hits=%d' % (
        name_control, len(units), skipped, r.count)]
    parts += ['%s=%d' % kv for kv in sorted(r.by_kind.items())]
    parts.append('gitleaks=' + ('UNKNOWN' if gl_n is None else str(gl_n)))
    print(' '.join(parts) + where)
    if gl_n is None:
        print('  gitleaks unavailable: ' + gl_why)
    for l in locs[:50]:
        print('  hit at ' + l)
    for l in gl_locs[:50]:
        print('  gitleaks hit at ' + l)
    if gl_n is None:
        return 4
    return 1 if (r.count or gl_n) else 0


def parse_diff(diff):
    units, f, ln = [], None, 0
    for line in diff.splitlines():
        if line.startswith('+++ '):
            f = line[6:] if line.startswith('+++ b/') else line[4:]
        elif line.startswith('@@'):
            m = re.search(r'\+(\d+)', line)
            ln = int(m.group(1)) if m else 0
        elif line.startswith('+') and not line.startswith('+++'):
            units.append((f, ln, line[1:]))
            ln += 1
    return units


if __name__ == '__main__':
    sys.exit(main())
