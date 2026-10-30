#!/usr/bin/env python3
"""loop-skill-lint: judges every SKILL.md under a skills folder. STRUCT-01 C1.

Usage: loop-skill-lint [<skills folder>]     (LOOP_SKILLS_DIR names the folder when no argument is given)

Rules, each named in the verdict of the skill that breaks it:
  name           the frontmatter name equals the folder name (the SKILL.md's parent)
  name-chars     the name holds lowercase letters, digits and hyphens only
  description    the description is present and not empty
  desc-oneline   the description is one line
  desc-length    the description is under 1,024 characters
  size-lines     the file is under 200 lines
  size-bytes     the file is under 20,000 bytes
  refs-depth     a references/ folder is one level deep: no file below its first level
  refs-files     a references/ folder holds files only: no empty folder or other non-file entry at its first level
  refs-contents  a reference over 100 lines starts with a line that reads Contents
  cross-skill    no line holds a relative path into another skill's folder
  leak           no line holds a users-folder path, a home-folder path, a drive letter and colon followed by a
                 users folder, or a redactor tag (the shapes are built in leak_patterns)
TAG READING: a redactor tag is a leak only next to a path separator, as loop-scan counts it (K05-C8); the literal
reading (a tag anywhere) would fail the kit's own skills/loop-audit, which names the tags in prose, against the GOAL's
"the kit's seven skills exit 0". Rows S1-leak-tag and S1-leak-prose pin it. TAG_WORDS is the redactor's tag list,
checked against bin/loop_redact.py by row S1-tags-sync.
Every SKILL.md at any depth under the folder is judged; the name must equal the SKILL.md's parent folder name.
The leak scan runs first on its own control line, built here at run time from parts; the control must fire or the
lint says so and exits 1. Lines of SKILL.md and of every reference are scanned for cross-skill and leak.

Prints one line per skill (folder, lines, bytes, verdict), then one closing line with the counts of skills and of
broken rules (a rule broken by a skill counts once). Exit 0 when no rule is broken, 1 otherwise, 64 on usage.
"""
import os
import re
import sys

USAGE = 'usage: loop-skill-lint [<skills folder>]   (LOOP_SKILLS_DIR names the folder when no argument is given)'

MAX_DESC = 1024
MAX_LINES = 200
MAX_BYTES = 20000
REF_CONTENTS_OVER = 100
NAME_OK = re.compile(r'^[a-z0-9-]+$')
TAG_WORDS = ('NAME', 'GIT_REMOTE', 'SECRET', 'REDACTED', 'PRIVATE_KEY', 'JWT', 'JWT_PART', 'ANTHROPIC_KEY',
             'API_KEY', 'TELEGRAM_BOT_TOKEN', 'GITHUB_TOKEN', 'SLACK_TOKEN', 'SLACK_WEBHOOK')
CROSS = re.compile(r'(?:\.\.[/\\])+([A-Za-z0-9._-]+)[/\\]')


def leak_patterns():
    """The four leak shapes, built from parts so this file holds none of them whole."""
    users = '/' + 'Users' + '/'
    home = '/' + 'home' + '/'
    drive = re.compile(r'(?<![A-Za-z])[A-Za-z]:[/\\]+' + 'users' + r'[/\\]', re.I)
    # a redactor tag counts as a leak the way loop-scan counts it: next to a path separator, on either side. A tag
    # named in prose (a skill that tells a reviewer what to grep for) is not a leak.
    alts = '|'.join(re.escape(chr(91) + w + chr(93)) for w in TAG_WORDS)
    tag = re.compile(r'(?:(?<=[/\\])(?:%s)|(?:%s)(?=[/\\]))' % (alts, alts))
    return users, home, drive, tag


USERS, HOME, DRIVE, TAG = leak_patterns()


def leaks(line):
    return USERS in line or HOME in line or DRIVE.search(line) is not None or TAG.search(line) is not None


def control_lines():
    """The lint's own control: one line per leak shape; every one must be seen as a leak."""
    return [
        'control ' + USERS + 'x',
        'control ' + HOME + 'x',
        'control ' + 'C' + ':' + '/' + 'Users' + '/' + 'x',
        'control ' + 'a' + '/' + chr(91) + 'NAME' + chr(93) + '/x',
    ]


def control_fired():
    prose = 'control ' + chr(91) + 'NAME' + chr(93) + ' in prose'
    return all(leaks(l) for l in control_lines()) and not leaks('control a plain line') and not leaks(prose)


def read_text(path):
    with open(path, 'rb') as fh:
        raw = fh.read()
    return raw, raw.decode('utf-8', 'replace')


def count_lines(raw):
    return raw.count(b'\n') + (1 if raw and not raw.endswith(b'\n') else 0)


def frontmatter(lines):
    """The key lines between the first two --- lines, as (index in frontmatter, text), or None."""
    if not lines or lines[0].strip() != '---':
        return None
    out = []
    for l in lines[1:]:
        if l.strip() == '---':
            return out
        out.append(l)
    return None


def field(fm, key):
    """(value, next line or None) of a top-level key in the frontmatter, or (None, None)."""
    for i, l in enumerate(fm):
        m = re.match(r'^' + key + r':[ \t]*(.*)$', l)
        if m:
            nxt = fm[i + 1] if i + 1 < len(fm) else None
            return m.group(1).strip(), nxt
    return None, None


def unquote(v):
    if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
        return v[1:-1]
    return v


def judge(base, rel):
    """The broken rules of one skill (rel: its folder, relative to base, with forward slashes), its line count and its
    byte count. The folder name is the last segment of rel."""
    folder = rel.rsplit('/', 1)[-1]
    skill = os.path.join(base, rel, 'SKILL.md')
    raw, text = read_text(skill)
    lines = text.replace('\r', '').split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    n, nbytes = count_lines(raw), len(raw)
    broken = []
    fm = frontmatter(lines)
    name = desc = None
    if fm is not None:
        name, _ = field(fm, 'name')
        desc, nxt = field(fm, 'description')
    if name is None or unquote(name) != folder:
        broken.append('name')
    if name is None or not NAME_OK.match(unquote(name)):
        broken.append('name-chars')
    if desc is None or unquote(desc) == '':
        broken.append('description')
    else:
        if desc in ('>', '|', '>-', '|-', '>+', '|+') or (nxt is not None and nxt[:1] in (' ', '\t')):
            broken.append('desc-oneline')
        if len(unquote(desc)) >= MAX_DESC:
            broken.append('desc-length')
    if n >= MAX_LINES:
        broken.append('size-lines')
    if nbytes >= MAX_BYTES:
        broken.append('size-bytes')
    scan = [lines]
    refs = os.path.join(base, rel, 'references')
    if os.path.isdir(refs):
        deep = files = contents = False
        for entry in sorted(os.listdir(refs)):
            p = os.path.join(refs, entry)
            if os.path.isdir(p):
                inner = [x for _r, _d, fs in os.walk(p) for x in fs]
                if inner:
                    deep = True
                else:
                    files = True
            elif not os.path.isfile(p):
                files = True
            else:
                rraw, rtext = read_text(p)
                rl = rtext.replace('\r', '').split('\n')
                if rl and rl[-1] == '':
                    rl.pop()
                if count_lines(rraw) > REF_CONTENTS_OVER and (not rl or rl[0].strip().lstrip('#').strip() != 'Contents'):
                    contents = True
                scan.append(rl)
        if deep:
            broken.append('refs-depth')
        if files:
            broken.append('refs-files')
        if contents:
            broken.append('refs-contents')
    cross = leak = False
    for ls in scan:
        for l in ls:
            for m in CROSS.finditer(l):
                if m.group(1) not in (folder, 'references'):
                    cross = True
            if leaks(l):
                leak = True
    if cross:
        broken.append('cross-skill')
    if leak:
        broken.append('leak')
    return broken, n, nbytes


def main(argv):
    env = os.environ.get('LOOP_SKILLS_DIR')
    if len(argv) > 1:
        print(USAGE)
        return 64
    base = argv[0] if argv else env
    if not base:
        print(USAGE)
        return 64
    if not os.path.isdir(base):
        print('loop-skill-lint: not a folder: the skills folder named')
        print(USAGE)
        return 64
    if not control_fired():
        print('loop-skill-lint: LEAK CONTROL DID NOT FIRE - lint broken')
        return 1
    folders = []
    for root, dirs, files in os.walk(base):
        dirs.sort()
        if 'SKILL.md' in files and os.path.abspath(root) != os.path.abspath(base):
            folders.append(os.path.relpath(root, base).replace('\\', '/'))
    folders.sort()
    total = 0
    for f in folders:
        broken, n, nbytes = judge(base, f)
        total += len(broken)
        verdict = 'verdict=ok' if not broken else 'verdict=broken rules=' + ','.join(broken)
        print('skill=%s lines=%d bytes=%d %s' % (f, n, nbytes, verdict))
    print('loop-skill-lint: skills=%d broken=%d control=fired' % (len(folders), total))
    if not folders:
        print('loop-skill-lint: no SKILL.md found under the folder named')
        return 1
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
