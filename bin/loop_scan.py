#!/usr/bin/env python3
"""loop-scan: secret and name scan with its own control. Exit 1 on any hit.

  loop-scan                      the staged diff (git diff --cached, added lines) of the current repo
  loop-scan --range A..B         the added lines of a commit range (use before a push: origin/<RECORD_BRANCH>..HEAD, default engine-record)
  loop-scan FILE [FILE ...]      whole files (a report before it is sent, an export before it is committed)

It first runs the same detector on a built-in control that must fire in every category.
If the control does not fire, the scan is broken and it exits 3.
Prints counts per category and file:line locations only, never the matched text.
Bare UUIDs and sha256 digests are not hits: they were noise in every PB scan.
A line containing the token loop-scan:control is a deliberate test string and is skipped; the count of skipped lines is printed.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import loop_redact  # noqa: E402
from loop_redact import Redactor  # noqa: E402

# GATE-01 T05: loop_redact.py's api-key pattern needs a \b immediately before
# "api", which never holds after an underscore (e.g. SERVICE_API_KEY, or a
# lowercase service_api_key). loop_redact.py itself is out of this task's
# surface, so add a supplemental pattern here instead: it fires only when an
# underscore precedes "api", on top of (never in place of) the 12 patterns
# already in loop_redact.PATTERNS.
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
       loop-scan FILE [FILE ...]  whole files"""


def resolve_repo():
    """P28. The repo whose diff is scanned: the current work tree, else the record
    repo from config. Run outside any repo, `git diff` errored, its stdout was
    empty, and the scan printed lines=0 hits=0 and exited 0: a false clean bill.
    Returns (path, 'cwd' | 'config') or (None, reason)."""
    p = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if p.returncode == 0 and p.stdout.strip():
        return p.stdout.strip(), 'cwd'
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
        name_control = 'fired' if r.names_re.search(' ' + r.names_list[-1] + ' ') else 'NOT FIRED'
        if name_control != 'fired':
            print('loop-scan: NAME CONTROL DID NOT FIRE - scanner broken')
            return 3
    units = []
    where = ''
    if not args or args[0] == '--range':
        repo, src = resolve_repo()
        if repo is None:
            print('loop-scan: ' + src + '. Exit 2, nothing was scanned.')
            return 2
        where = ' repo=%s (%s)' % (tilde_home(repo.replace('\\', '/')), src)
    if args and args[0] == '--range':
        if len(args) < 2:
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
    print(f'loop-scan: control=fired name_control={name_control} lines={len(units)} control_lines_skipped={skipped} hits={r.count} ' +
          ' '.join(f'{k}={v}' for k, v in sorted(r.by_kind.items())) + where)
    for l in locs[:50]:
        print('  hit at ' + l)
    return 1 if r.count else 0


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
