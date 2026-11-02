#!/usr/bin/env python3
"""loop-inventory: print, from the tree this file sits in, the figures docs/STATUS.md states for the kit.

Usage: loop-inventory   (no argument; the tree is the folder above the bin/ folder this file is in)

It prints three sections of Markdown to stdout, as bytes with line feeds, and writes nothing anywhere else:
  ## The kit                          the lines in MANIFEST.txt, the command files under bin/, the hooks files
  ## Row folders and call forms       the folders under tests/rows/ and the ones that also take the tree as an argument
  ## Configuration keys                the keys of the DEFAULTS table in bin/loop_conf.py (read with ast, never imported)
Those three sections stand byte for byte in docs/STATUS.md; tests/rows/K06-C5/run.py compares them. The figures that
cannot be read from the tree alone (the skills, the commits on main) stay in STATUS.md as measured by hand.

A command file under bin/ is a file that is not a .py module, not a .pyc and not DESCRIPTION.md. A row folder is a folder
under tests/rows/ (what `find tests/rows -mindepth 1 -maxdepth 1 -type d` counts). A row folder has the positional form when
its run.py reads sys.argv[1] or calls dirs_or_args, imported from the library _lib.
"""
import ast
import os
import sys

sys.dont_write_bytecode = True

# What each key of the DEFAULTS table is. A key with no entry here is still printed, without a description.
KEY_TEXT = {
    'LOOP_HOME': 'the loop home, `~/.loop` by default.',
    'ENGINE_RECORD_DIR': 'the worktree of the record branch.',
    'RECORD_BRANCH': 'the branch inside that worktree which carries state, journal and exports.',
    'STATE_FILE': 'the state document, `docs/STATE.md` of the record worktree by default.',
    'JOURNAL_FILE': 'the append-only journal, `docs/JOURNAL.md` of the record worktree by default.',
    'EXPORT_DIR': 'the exports folder, `exports` of the record worktree by default.',
    'WRAPPERS': 'the space-separated wrappers the roles run commands through.',
    'WRITABLE_TREES': 'the colon-separated git worktrees the leader may create task branches in.',
    'MAX_LEADERS': 'how many leaders run at once, 1 by default.',
    'SURFACES': 'the space-separated surface wrappers installed here, empty for none.',
    'TRIPWIRE_NOISE': 'the name patterns at the top of the home whose changes the tripwire reports as noise.',
    'REPORT_SEND_CMD': 'the command that sends a report; empty leaves the report on disk.',
    'REPORT_MAX_LINES': 'the line limit of a report, 80 by default.',
    'STATE_MAX_LINES': 'the line limit of the state document, 150 by default.',
}


def read_bytes(p):
    try:
        with open(p, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def files_under(base, keep):
    """Sorted base names of the files under base (cache folders left out) that keep() accepts."""
    out = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if keep(f):
                out.append(f)
    return sorted(out)


def manifest_lines(tree):
    b = read_bytes(tree + '/MANIFEST.txt')
    return 0 if b is None else b.count(b'\n')


def bin_files(tree):
    return files_under(tree + '/bin', lambda f: not f.endswith('.py') and not f.endswith('.pyc'))


def hook_files(tree):
    return files_under(tree + '/hooks', lambda f: not f.endswith('.pyc'))


def row_folders(tree):
    base = tree + '/tests/rows'
    return sorted(d for d in os.listdir(base) if os.path.isdir(base + '/' + d)) if os.path.isdir(base) else []


def reads_argument(text):
    """Whether the runner source reads sys.argv[1] or calls dirs_or_args (an ast reading; a comment or a string is not a read)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == 'argv' \
                and isinstance(node.value.value, ast.Name) and node.value.value.id == 'sys':
            idx = node.slice
            if isinstance(idx, ast.Constant) and idx.value == 1:
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dirs_or_args':
            return True
    return False


def positional_folders(tree, folders):
    out = []
    for f in folders:
        b = read_bytes(tree + '/tests/rows/' + f + '/run.py')
        if b is not None and reads_argument(b.decode('utf-8', 'replace')):
            out.append(f)
    return out


def default_keys(tree):
    b = read_bytes(tree + '/bin/loop_conf.py')
    if b is None:
        return []
    for node in ast.walk(ast.parse(b.decode('utf-8', 'replace'))):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'DEFAULTS' for t in node.targets):
            if isinstance(node.value, ast.Dict):
                return [k.value for k in node.value.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    return []


def render(tree):
    """The text of the three sections for the tree, with line feeds only; every section ends with one blank line."""
    bins = bin_files(tree)
    cmds = [f for f in bins if f != 'DESCRIPTION.md']
    hooks = hook_files(tree)
    rows = row_folders(tree)
    pos = positional_folders(tree, rows)
    out = []
    out.append('## The kit\n')
    out.append('Lines in MANIFEST.txt:\n')
    out.append('```\n$ wc -l < MANIFEST.txt\n%d\n```\n' % manifest_lines(tree))
    out.append('Files under bin/ that are not modules (`.py`) or caches (`.pyc`):\n')
    out.append('```\n$ find bin -type f ! -name "*.py" ! -name "*.pyc" | wc -l\n%d\n```\n' % len(bins))
    out.append('Command files, those files less DESCRIPTION.md: %s\n' % ' '.join(cmds))
    out.append('Hooks files (caches left out):\n')
    out.append('```\n$ find hooks -type f ! -name "*.pyc" | wc -l\n%d\n```\n' % len(hooks))
    out.append('Hooks files: %s\n' % ' '.join(hooks))
    out.append('## Row folders and call forms\n')
    out.append('Row folders under tests/rows/:\n')
    out.append('```\n$ find tests/rows -mindepth 1 -maxdepth 1 -type d | wc -l\n%d\n```\n' % len(rows))
    out.append('Every row runner takes no argument and reads its environment. The folders on the second line below also take '
               'the tree, the home and the work folder as three arguments after the runner path, in that order, with the '
               'same fills.\n')
    out.append('Row folders: %s\nPositional form: %s\n' % (' '.join(rows), ' '.join(pos)))
    out.append('## Configuration keys\n')
    out.append('The keys of the DEFAULTS table in bin/loop_conf.py, each read from `$HOME/.loop/config.env`.\n')
    keys = default_keys(tree)
    out.append('\n'.join(('- %s: %s' % (k, KEY_TEXT[k])) if k in KEY_TEXT else ('- %s' % k) for k in keys) + '\n')
    return '\n'.join(out) + '\n'


def main():
    if len(sys.argv) > 1:
        sys.stderr.write('usage: loop-inventory   (no argument; the tree is the folder above this bin/ folder)\n')
        return 64
    tree = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\', '/')
    sys.stdout.buffer.write(render(tree).encode('utf-8'))
    sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
