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
    name_control = 'n/a (no names file)'
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
        where = ' repo=%s (%s)' % (repo.replace('\\', '/'), src)
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
