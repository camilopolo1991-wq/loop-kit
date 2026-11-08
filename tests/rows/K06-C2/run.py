#!/usr/bin/env python3
"""K06-C2 rows runner: one test library under the row runners (tests/rows/_lib.py).

Environment (no positional argument; exit 64 with the usage line when one is given or one of the first three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home; written only with the base exported by git when no LOOP_MAIN and no wt-main beside LOOP_TREE is
                   there (the install row's child gets a fresh home under LOOP_WORK instead)
  LOOP_MAIN        optional: the comparison tree (else wt-main beside LOOP_TREE, else the first parent of "Merge kit-06" exported
                   by git from LOOP_TREE; exit 64 naming LOOP_MAIN when none is found)
  LOOP_WORK        the work folder; every fixture is written under it and listed in k06c2-manifest.txt
  LOOP_PY, LOOP_NAMES_FILE   handed to the install child (LOOP_PY defaults to the interpreter running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  count    no tests/rows/*/run.py under LOOP_TREE defines a name the library defines (ast, top level); the actual is the
           count (0 expected; every runner of wt-main defines some)
  install  an install with LOOP_WITH_TESTS=1 of LOOP_TREE into a fresh home under LOOP_WORK (HOME and USERPROFILE at it,
           LOOP_HOME at it plus /.loop) places the library under the home's tests/rows/, equal to the tree's
  lines    tests/rows under LOOP_TREE (without the folders named K06-C3 and later) holds at least expect fewer lines than the
           same count measured on the sibling folder wt-main at run time (arg is only a label, wt-main); the literal
           full-tree count on both trees and its difference are printed beside it, not judged

Prints PASS or FAIL per row with expected and actual (a sha256 stands in for the install output), then rows=N pass=P
fail=F. Nothing is spawned in the background and nothing is killed.
"""
import ast
import os
import re
import subprocess
import sys
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, find_base, fwd, info_sha, load_rows, make_env, read_bytes, register, sha, tally

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] '
         'python run.py (no positional argument)')
MANIFEST = 'k06c2-manifest.txt'
INSTALL_DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL',
                'JOURNAL_FILE', 'LOOP_GUARD_MODE')


def top_names(b):
    names = set()
    for node in ast.parse(b.decode('utf-8', 'replace')).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def row_count(ctx, rid, expect, arg):
    lib = top_names(read_bytes(ROWS + '/_lib.py'))
    bad = total = 0
    for d in sorted(os.listdir(ctx['tree'] + '/' + arg)):
        b = read_bytes('%s/%s/%s/run.py' % (ctx['tree'], arg, d))
        if b is not None:
            total += 1
            bad += bool(top_names(b) & lib)
    return str(bad) == expect, 'expected=%s actual=%d of %d runners define a library name' % (expect, bad, total)


def row_install(ctx, rid, expect, arg):
    home = ctx['work'] + '/fresh-home'
    register(ctx['work'], MANIFEST, home)
    os.makedirs(home)
    extra = {'LOOP_WITH_TESTS': '1', 'LOOP_PY': ctx['py']}
    if os.environ.get('LOOP_NAMES_FILE'):
        extra['LOOP_NAMES_FILE'] = os.environ['LOOP_NAMES_FILE']
    cp = subprocess.run(['bash', ctx['tree'] + '/install.sh'], capture_output=True, text=True, encoding='utf-8',
                        errors='replace', env=make_env(home, extra, INSTALL_DROP), cwd=ctx['work'])
    want = read_bytes(ctx['tree'] + '/tests/' + arg)
    got = read_bytes(home + '/.loop/tests/' + arg)
    ok = cp.returncode == 0 and want is not None and got == want
    return ok, 'expected=exit 0 and the library %s actual=exit %d, library %s, out sha256=%s' % (
        expect, cp.returncode, 'absent' if got is None else ('equal' if got == want else 'differs'), sha(cp.stdout + cp.stderr))


def later_folder(name):
    """K06-C3 and later folders (K06-C<n>, n of 3 or more): folders this goal adds after card C2."""
    m = re.match(r'^K06-C(\d+)$', name)
    return m is not None and int(m.group(1)) >= 3


def card_folder(name):
    """K06-C1 and K06-C2: the folders of this goal's cards up to C2, which the base does not hold."""
    return re.match(r'^K06-C[12]$', name) is not None


def top_folders(base):
    root0 = base + '/tests/rows'
    return set(d for d in os.listdir(root0) if os.path.isdir(root0 + '/' + d)) if os.path.isdir(root0) else set()


def count_lines(base, only_c2_population, keep=None):
    """Lines under base/tests/rows; with only_c2_population the folders named K06-C3 and later at the top are left out, and with
    keep (a set of folder names) the top folders outside keep that are not K06-C1 or K06-C2 are left out too (KIT-11 T08: the folders
    later goals added are not the population card C2 refactored)."""
    n = 0
    root0 = base + '/tests/rows'
    if not os.path.isdir(root0):
        return None
    for root, dirs, files in os.walk(root0):
        dirs[:] = [d for d in dirs if d != '__pycache__' and not (
            only_c2_population and root == root0 and (later_folder(d) or (keep is not None and d not in keep and not card_folder(d))))]
        n += sum((read_bytes(os.path.join(root, f)) or b'').count(b'\n') for f in files)
    return n


def row_lines(ctx, rid, expect, arg):
    """Judged: the population card C2 refactored (tests/rows without the folders named K06-C3 and later) against the same
    count measured on wt-main now. Printed, not judged: the literal full-tree count on both trees and its difference."""
    main_tree = ctx['main']
    n = count_lines(ctx['tree'], True, top_folders(main_tree))
    lit_here = count_lines(ctx['tree'], False)
    lit_main = count_lines(main_tree, False)
    pop_main = count_lines(main_tree, True)
    diff = 'n/a' if lit_main is None else str(lit_main - lit_here)
    fewer = 'n/a' if pop_main is None else str(pop_main - n)
    return pop_main is not None and pop_main - n >= int(expect), (
        'expected=at least %s fewer than the wt-main count measured now (%s) actual=%d lines under the tree without K06-C3 and later, %s fewer; '
        'literal full tree: here %s, wt-main %s (population without K06-C3 and later on wt-main %s), difference %s') % (
        expect, pop_main, n, fewer, lit_here, lit_main, pop_main, diff)


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    # KIT-11 T08: the comparison tree is LOOP_MAIN, else wt-main beside the tree, else the first parent of "Merge kit-06" exported by git
    main_tree = find_base(tree, home, 'kit-06')
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K06-C2/run.py', here + '/run.py'), ('tests/rows/K06-C2/rows.txt', here + '/rows.txt')))
    ctx = {'tree': tree, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable), 'main': main_tree}
    kinds = {'count': row_count, 'install': row_install, 'lines': row_lines}
    return tally(load_rows(here + '/rows.txt'), kinds, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
