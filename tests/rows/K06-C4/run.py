#!/usr/bin/env python3
"""K06-C4 rows runner: one home per rule in the kit's prose. Nine sentences S1 to S9 each have one home file; every other prose
file names the home instead of restating the sentence. Two lines were added to the Known context guidance of templates/GOAL.md.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the first three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k06c4-manifest.txt
  LOOP_PY, LOOP_NAMES_FILE   handed to the children (LOOP_PY defaults to the interpreter running this file)
The comparison tree is LOOP_MAIN, else the sibling folder wt-main of LOOP_TREE, else the first parent of "Merge kit-06" exported by
git from LOOP_TREE under LOOP_ROWS_HOME (exit 64 naming LOOP_MAIN when none is found).

The prose files are agents/, skills/, templates/, docs/guides/ (every file under them), README.md and AGENTS.md of the tree.
Rows (rows.txt, id :: kind :: expect :: arg):
  count     arg is a case-insensitive regular expression; it is found (some line holds it) in exactly one prose file and that file
            is the home named by expect. The regex matches a restatement of the rule, not a bare mention of a tool or file name.
  phrase    arg is 'relative path|phrase'; the phrase is found in the file (the row fails on a tree without the line)
  lines     the lines of the folders named in arg, together, are fewer under LOOP_TREE than under wt-main; both counts printed
  lint      arg is 'tool|target'; bash LOOP_TREE/bin/<tool> LOOP_TREE/<target> run with LOOP_TREE/bin as the working folder
            exits with the number in expect
  control   a scratch tree under LOOP_WORK holds a copy of the home file of sentence arg and a second scratch prose file with the
            phrase of that sentence pasted in; the logic of the count rows counts two files, which is printed as FAIL on a
            control line, and the row passes only when two files are counted and the unmodified copy alone counts one

Prints PASS or FAIL per row with expected and actual (file names are relative to the tree), then rows=N pass=P fail=F.
Nothing is spawned in the background and nothing is killed.
"""
import os
import re
import subprocess
import sys
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, find_base, fwd, info_sha, load_rows, make_env, read_bytes, register, row_phrase, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] '
         'python run.py (no positional argument; LOOP_MAIN, else the folder wt-main beside LOOP_TREE, else main found by git, is the comparison tree)')
MANIFEST = 'k06c4-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
PROSE_DIRS = ('agents', 'skills', 'templates', 'docs/guides')
PROSE_TOP = ('README.md', 'AGENTS.md')
# text pasted into the second scratch prose file of the control row, per sentence (it matches that sentence's regex)
PASTE = {'S1': 'one per hold and one per close'}


def prose_files(tree):
    """The prose files of a tree, relative paths with forward slashes, sorted; cache folders are left out."""
    out = [f for f in PROSE_TOP if os.path.isfile(tree + '/' + f)]
    for d in PROSE_DIRS:
        for root, dirs, files in os.walk(tree + '/' + d):
            dirs[:] = sorted(x for x in dirs if x != '__pycache__')
            for f in sorted(files):
                out.append(fwd(os.path.join(root, f))[len(tree) + 1:])
    return sorted(out)


def holding(tree, rx):
    """The prose files of tree with at least one line the regex matches (the logic of the count rows)."""
    pat = re.compile(rx, re.I)
    hit = []
    for rel in prose_files(tree):
        data = read_bytes(tree + '/' + rel)
        text = (data or b'').decode('utf-8', 'replace').replace('\r', '')
        if any(pat.search(ln) for ln in text.split('\n')):
            hit.append(rel)
    return hit


def line_total(tree, folders):
    n = 0
    for d in folders:
        for root, dirs, files in os.walk(tree + '/' + d):
            dirs[:] = [x for x in dirs if x != '__pycache__']
            for f in files:
                data = read_bytes(os.path.join(root, f)) or b''
                n += data.count(b'\n') + (1 if data and not data.endswith(b'\n') else 0)
    return n


def row_count(ctx, rid, expect, arg):
    hit = holding(ctx['tree'], arg)
    ok = hit == [expect]
    return ok, 'expected=exactly one prose file, the home %s actual=%d file(s): %s' % (expect, len(hit), ' '.join(hit) or 'none')


def row_lines(ctx, rid, expect, arg):
    folders = arg.split()
    a = line_total(ctx['tree'], folders)
    b = line_total(ctx['main'], folders)
    return a < b, 'expected=lines of %s under the tree fewer than under wt-main actual=tree %d, wt-main %d' % ('+'.join(folders), a, b)


def row_lint(ctx, rid, expect, arg):
    tool, target = arg.split('|', 1)
    env = make_env(ctx['home'], {'LOOP_PY': ctx['py']}, DROP)
    cp = subprocess.run(['bash', ctx['tree'] + '/bin/' + tool, ctx['tree'] + '/' + target], capture_output=True, env=env,
                        cwd=ctx['tree'] + '/bin')
    return cp.returncode == int(expect), 'expected=exit %s from bin/%s on %s actual=exit %d' % (expect, tool, target, cp.returncode)


def row_control(ctx, rid, expect, arg):
    spec = [r for r in ctx['rows'] if r[1] == 'count' and r[0].startswith(arg + '-')]
    if not spec or arg not in PASTE:
        return False, 'expected=a count row and a paste text for %s actual=none' % arg
    home, rx = spec[0][2], spec[0][3]
    src = read_bytes(ctx['tree'] + '/' + home)
    if src is None:
        return False, 'expected=%s readable actual=absent' % home
    d = ctx['work'] + '/k06c4-control'
    register(ctx['work'], MANIFEST, d)
    text = src.decode('utf-8', 'replace').replace('\r', '')
    # the unmodified copy alone: one file holds the phrase
    os.makedirs(os.path.dirname(d + '/clean/' + home), exist_ok=True)
    write_text(d + '/clean/' + home, text)
    write_text(d + '/clean/README.md', '# scratch readme without the phrase\n')
    one = holding(d + '/clean', rx)
    # the control: the same copy, and the phrase pasted into a second scratch prose file
    os.makedirs(os.path.dirname(d + '/pasted/' + home), exist_ok=True)
    write_text(d + '/pasted/' + home, text)
    write_text(d + '/pasted/README.md', '# scratch readme\n' + PASTE[arg] + ' (pasted)\n')
    two = holding(d + '/pasted', rx)
    judged = two == [home]
    print('%s control %s expected=exactly one prose file actual=%d files: %s (scratch copy of %s with the %s phrase pasted into a second scratch prose file)' % (
        'PASS' if judged else 'FAIL', 'c-control-count', len(two), ' '.join(two), home, arg))
    ok = len(two) == int(expect) and one == [home]
    return ok, 'expected=pasted copy counts %s files, unmodified copy counts 1 actual=pasted %d, unmodified %d' % (expect, len(two), len(one))


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    # KIT-11 T08: the comparison tree is LOOP_MAIN, else wt-main beside the tree, else the first parent of "Merge kit-06" exported by git
    main_tree = find_base(tree, home, 'kit-06')
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K06-C4/run.py', here + '/run.py'), ('tests/rows/K06-C4/rows.txt', here + '/rows.txt')))
    rows = load_rows(here + '/rows.txt')
    ctx = {'tree': tree, 'main': main_tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable),
           'rows': rows}
    kinds = {'count': lambda r, e, a: row_count(ctx, r, e, a), 'lines': lambda r, e, a: row_lines(ctx, r, e, a),
             'lint': lambda r, e, a: row_lint(ctx, r, e, a), 'control': lambda r, e, a: row_control(ctx, r, e, a),
             'phrase': lambda r, e, a: row_phrase({'tree': tree}, r, e, a)}
    return tally(rows, kinds, (), True)


if __name__ == '__main__':
    sys.exit(main())
