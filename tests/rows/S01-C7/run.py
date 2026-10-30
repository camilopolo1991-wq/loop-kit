#!/usr/bin/env python3
"""S01-C7 rows runner: the README is short and holds what the card C7 names.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test), LOOP_ROWS_HOME (the rows home; HOME, USERPROFILE and LOOP_HOME of any child
would be this home and this home plus /.loop, and this runner starts no child), LOOP_WORK (a work folder, created when
absent), LOOP_PY and LOOP_NAMES_FILE (accepted, unused here).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.

Each README row applies one checker to README.md of the tree and prints PASS when the verdict equals the expected one
('holds'). Each control row writes a constructed bad README text under LOOP_WORK and applies the same checker to it; its
expected verdict is 'rejected', so a checker that cannot fail makes its control row FAIL. Every path the runner creates is
listed in s01c7-manifest.txt in LOOP_WORK; the next run removes only what that file lists. Prints PASS or FAIL per row, an
info line with the sha256 of the runner's own two files, then rows=N pass=N fail=N. Nothing is spawned and nothing is killed.
"""
import hashlib
import os
import re
import sys

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_PY=<python> LOOP_NAMES_FILE=<file> python run.py (no positional argument)'
MANIFEST = 's01c7-manifest.txt'
CONTROL_DIR = 's01c7-control'
FIGURE_RE = re.compile(r'^Kit files: ([0-9]+), counted by `([^`]+)`\.$')
START_FILES = ['AGENTS.md', 'docs/guides/install.md', 'docs/STATUS.md']
KIT_FOLDERS = ['agents', 'hooks', 'skills', 'bin', 'templates', 'tests']


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def shafull(b):
    return hashlib.sha256(b).hexdigest()


def read_bytes(p):
    try:
        with open(p, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def read_text(p):
    b = read_bytes(p)
    return b.decode('utf-8', 'replace').replace('\r\n', '\n') if b is not None else None


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', 3)])
    return rows


def remove_path(p):
    if os.path.isdir(p):
        for root, dirs, files in os.walk(p, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                os.chmod(fp, 0o600)
                os.remove(fp)
            for d in dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(p)
    elif os.path.exists(p):
        os.chmod(p, 0o600)
        os.remove(p)


def clean_earlier(work):
    mf = work + '/' + MANIFEST
    data = read_bytes(mf)
    if data is None:
        return 0
    n = 0
    for p in data.decode('utf-8', 'replace').split('\n'):
        p = p.strip()
        if p and fwd(p).startswith(work + '/') and fwd(p) != work + '/' + MANIFEST and os.path.exists(p):
            remove_path(p)
            n += 1
    os.remove(mf)
    return n


def add_to_manifest(ctx, p):
    with open(ctx['work'] + '/' + MANIFEST, 'a', encoding='utf-8') as fh:
        fh.write(p + '\n')


# ---- helpers over the README text ----

def split_lines(text):
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return lines


def fenced_blocks(lines):
    """Each fenced block as its list of inner lines, in order."""
    out = []
    cur = None
    for ln in lines:
        if ln.startswith('```'):
            if cur is None:
                cur = []
            else:
                out.append(cur)
                cur = None
        elif cur is not None:
            cur.append(ln)
    return out


def outside_fences(lines):
    """(line number, line) for every line that is neither inside a fenced block nor a fence marker."""
    out = []
    inside = False
    for i, ln in enumerate(lines, 1):
        if ln.startswith('```'):
            inside = not inside
            continue
        if not inside:
            out.append((i, ln))
    return out


def cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def tables(lines):
    """Each table as (header cells, list of data-row cell lists). A table is a header line, a separator line, then rows."""
    out = []
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].startswith('|') and i + 1 < n and re.fullmatch(r'\|[-| :]+\|', lines[i + 1].strip()):
            head = cells(lines[i])
            j = i + 2
            rows = []
            while j < n and lines[j].startswith('|'):
                rows.append(cells(lines[j]))
                j += 1
            out.append((head, rows))
            i = j
        else:
            i += 1
    return out


def backticked(cell):
    m = re.fullmatch(r'`([^`]+)`', cell.strip())
    return m.group(1) if m else None


# ---- the checkers: each takes (ctx, text) and returns (ok, detail) ----

def chk_sentence(ctx, text):
    lines = split_lines(text)
    nb = [ln for ln in lines if ln.strip()]
    if len(nb) < 2 or not nb[0].startswith('# '):
        return False, 'no title line first'
    s = nb[1]
    if s.startswith(('```', '|', '#', '-')):
        return False, 'the line after the title is not a sentence'
    ends = len(re.findall(r'[.!?]', s))
    ok = s.count('.') == 1 and ends == 1 and s.endswith('.')
    return ok, 'periods=%d sentence ends=%d ends with a period=%s' % (s.count('.'), ends, s.endswith('.'))


def chk_block(ctx, text):
    blocks = fenced_blocks(split_lines(text))
    if not blocks:
        return False, 'no fenced block'
    b = blocks[0]
    if len(b) != 2:
        return False, 'first fenced block holds %d line(s)' % len(b)
    a, c = b
    env_ok = a.startswith('LOOP_PY=') and 'LOOP_WITH_TESTS=' in a and 'LOOP_UPGRADE' not in a and a.endswith('bash install.sh')
    up_ok = c.startswith('LOOP_PY=') and 'LOOP_UPGRADE=' in c and 'LOOP_BACKUP_DIR=' in c and c.endswith('bash install.sh')
    return env_ok and up_ok, 'lines=2 environment form=%s upgrade form=%s' % (env_ok, up_ok)


def chk_table(ctx, text):
    tabs = tables(split_lines(text))
    if not tabs:
        return False, 'no table'
    head, rows = tabs[0]
    head_ok = len(head) >= 2 and head[0].lower().startswith('without') and head[1].lower().startswith('with the')
    bad = []
    for i, r in enumerate(rows, 1):
        cmd = backticked(r[-1]) if r else None
        word = cmd.split()[0] if cmd and cmd.split() else ''
        found = bool(word) and (os.path.isfile(ctx['tree'] + '/bin/' + word) or os.path.isfile(ctx['tree'] + '/hooks/' + word))
        if not found:
            bad.append(str(i))
    ok = head_ok and len(rows) >= 4 and not bad
    return ok, 'header without/with=%s data rows=%d last cell not a bin or hooks command at row(s) %s' % (head_ok, len(rows), ','.join(bad) or 'none')


def chk_starthere(ctx, text):
    found = [ln for ln in split_lines(text) if ln.startswith('Start here')]
    if len(found) != 1:
        return False, 'Start here lines=%d' % len(found)
    names = re.findall(r'`([^`]+)`', found[0])
    ordered = names == START_FILES
    exist = all(os.path.isfile(ctx['tree'] + '/' + n) for n in names) and bool(names)
    return ordered and exist, 'named=%d in the order=%s all exist=%s' % (len(names), ordered, exist)


def manifest_count(ctx):
    b = read_bytes(ctx['tree'] + '/MANIFEST.txt')
    return None if b is None else b.count(b'\n')


def chk_figure(ctx, text):
    found = [FIGURE_RE.match(ln) for ln in split_lines(text) if ln.startswith('Kit files')]
    found = [m for m in found if m]
    if len(found) != 1:
        return False, 'figure lines=%d' % len(found)
    stated = int(found[0].group(1))
    cmd = found[0].group(2)
    want = manifest_count(ctx)
    return stated == want and cmd == 'wc -l < MANIFEST.txt', 'stated=%d MANIFEST.txt lines=%s command=%s' % (stated, want, cmd)


def chk_lines(ctx, text):
    n = text.count('\n') + (0 if text.endswith('\n') or not text else 1)
    return n < 80, 'lines=%d limit=under 80' % n


def chk_repotable(ctx, text):
    tabs = [t for t in tables(split_lines(text)) if [h.lower() for h in t[0]] == ['repository', 'installed at']]
    if len(tabs) != 1:
        return False, 'repository tables=%d' % len(tabs)
    install = read_text(ctx['tree'] + '/install.sh') or ''
    layout = {}
    for m in re.finditer(r'^#\s+([a-z]+)/\s+->\s+(\S+)', install, re.M):
        layout[m.group(1)] = m.group(2)
    rows = tabs[0][1]
    seen = []
    bad = []
    for r in rows:
        f = backticked(r[0]) if len(r) == 2 else None
        d = backticked(r[1].split(',')[0]) if len(r) == 2 else None
        name = f[:-1] if f and f.endswith('/') else None
        dest = None
        if d:
            dest = d.replace('$LOOP_HOME/', '.loop/', 1) if d.startswith('$LOOP_HOME/') else (d[2:] if d.startswith('~/') else None)
        if not name or not os.path.isdir(ctx['tree'] + '/' + name) or dest is None or layout.get(name) != dest:
            bad.append(name or '?')
        else:
            seen.append(name)
    ok = sorted(seen) == sorted(KIT_FOLDERS) and not bad
    return ok, 'folders mapped=%d of %d, wrong or missing %s' % (len(seen), len(KIT_FOLDERS), ','.join(bad) or 'none')


def chk_nofigure(ctx, text):
    hits = []
    for i, ln in outside_fences(split_lines(text)):
        if FIGURE_RE.match(ln):
            continue
        if re.search(r'\b[0-9]+\b', ln):
            hits.append(str(i))
    return not hits, 'lines holding a number besides the figure line: %s' % (','.join(hits) or 'none')


def chk_nodollar(ctx, text):
    hits = [str(i) for i, b in enumerate(fenced_blocks(split_lines(text)), 1) if b and b[0].startswith('$ ')]
    return not hits, 'fenced blocks starting with a dollar sign and a space: %s' % (','.join(hits) or 'none')


def chk_nohome(ctx, text):
    hits = [str(i) for i, ln in enumerate(split_lines(text), 1) if re.search(r'[A-Za-z]:[/\\]|/Users/|/home/|\$HOME', ln)]
    return not hits, 'lines holding a home path: %s' % (','.join(hits) or 'none')


CHECKERS = {
    'sentence': chk_sentence, 'block': chk_block, 'table': chk_table, 'starthere': chk_starthere, 'figure': chk_figure,
    'lines': chk_lines, 'repotable': chk_repotable, 'nofigure': chk_nofigure, 'nodollar': chk_nodollar, 'nohome': chk_nohome,
}

BAD = {
    'sentence': '# t\n\nOne thing. Another thing.\n',
    'block': '# t\n\n```\nbash install.sh\n```\n',
    'table': '| Without the kit | With the kit | Command |\n|---|---|---|\n| a | b | `agents/` |\n',
    'starthere': 'Start here: `docs/STATUS.md`, `AGENTS.md` and `docs/guides/install.md`.\n',
    'figure': 'Kit files: 0, counted by `wc -l < MANIFEST.txt`.\n',
    'lines': 'x\n' * 80,
    'repotable': '| Repository | Installed at |\n|---|---|\n| `bin/` | `$LOOP_HOME/wrong/` |\n',
    'nofigure': '# t\n\nthree 3 files\n',
    'nodollar': '# t\n\n```\n$ ls\n```\n',
    'nohome': '# t\n\nsee C:/Users/x/y\n',
}


# ---- rows ----

def row_readme(ctx, expect, arg):
    text = read_text(ctx['tree'] + '/README.md')
    if text is None:
        return False, 'expected=%s actual=README.md absent' % expect
    ok, detail = CHECKERS[arg](ctx, text)
    got = 'holds' if ok else 'fails'
    return got == expect, 'expected=%s actual=%s %s' % (expect, got, detail)


def row_control(ctx, expect, arg):
    d = ctx['work'] + '/' + CONTROL_DIR
    os.makedirs(d, exist_ok=True)
    add_to_manifest(ctx, d)
    p = d + '/' + arg + '.md'
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(BAD[arg])
    ok, detail = CHECKERS[arg](ctx, read_text(p))
    got = 'accepted' if ok else 'rejected'
    return got == expect, 'expected=%s actual=%s %s' % (expect, got, detail)


KINDS = {'readme': row_readme, 'control': row_control}


def main():
    if len(sys.argv) > 1:
        print(USAGE)
        return 64
    tree_e = os.environ.get('LOOP_TREE')
    home_e = os.environ.get('LOOP_ROWS_HOME')
    work_e = os.environ.get('LOOP_WORK')
    if not tree_e or not home_e or not work_e:
        print(USAGE)
        return 64
    tree, work = fwd(tree_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    cleaned = clean_earlier(work)
    print('cleaned %d path(s) listed by an earlier run' % cleaned)
    ctx = {'tree': tree, 'work': work, 'home': fwd(home_e)}
    here = os.path.dirname(os.path.abspath(__file__))
    for label, p in (('tests/rows/S01-C7/run.py', here + '/run.py'), ('tests/rows/S01-C7/rows.txt', here + '/rows.txt')):
        b = read_bytes(p)
        print('info sha256 %s %s' % (label, shafull(b) if b is not None else 'absent'))
    rows = load_rows(os.path.join(here, 'rows.txt'))
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        fn = KINDS.get(kind)
        if fn is None or arg not in CHECKERS:
            ok, detail = False, 'expected=row runs actual=unknown kind or checker'
        else:
            try:
                ok, detail = fn(ctx, expect, arg)
            except Exception as exc:
                ok, detail = False, 'expected=row runs actual=error %s' % type(exc).__name__
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
