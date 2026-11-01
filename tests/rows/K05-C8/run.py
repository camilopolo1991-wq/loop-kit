#!/usr/bin/env python3
"""K05-C8 rows runner: bin/loop-scan reports a redactor tag (the name tag or the remote tag) inside a path as a hit under
its own category, tag; a home-shaped path holding the name tag stays under path; the scanner's own control line is
skipped; a tag in prose is not a hit. skills/loop-audit scout item 5 says the same and names the category.

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expectations in rows.txt, so a tree
without the change prints FAIL on the tag rows), LOOP_ROWS_HOME (the home the scan runs under), LOOP_WORK (a work
folder, created when absent; the fixtures are written there), LOOP_PY (the interpreter bin/loop-scan resolves),
LOOP_NAMES_FILE (the names file the scan checks, passed through).
Each tag is built at run time from its parts, so no committed file holds one. Output holds counts only, never a path.
Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import os
import re
import subprocess
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib import env_dirs, load_rows, make_env, row_phrase, sha, tally, write_text

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_PY=<python> LOOP_NAMES_FILE=<file> python run.py (no positional argument)'


def tag(word):
    """A redactor tag built from its parts: the bracket, the word, the bracket."""
    return chr(91) + word + chr(93)


def fixture_text(kind, home):
    name, remote = tag('NAME'), tag('GIT_REMOTE')
    if kind == 'nametag':
        return '# fixture: the name tag next to a path separator, not under the home\n' + 'data/' + name + '/notes.txt\n'
    if kind == 'remotetag':
        return '# fixture: the remote tag next to a path separator, not under the home\n' + 'mirror/' + remote + '/refs\n'
    if kind == 'homepath':
        parent = home.rpartition('/')[0]
        return ('# fixture: the name tag inside a home-shaped path; the path category counts it, so the tag category must not\n'
                + parent + '/' + name + '/x\n')
    if kind == 'controlline':
        marker = 'loop-scan:' + 'control'
        return '# fixture: a control line with its marker is skipped\n' + 'data/' + name + '/notes.txt  # ' + marker + '\n'
    return '# fixture: the tag in prose, not next to a separator\n' + 'the redactor writes ' + name + ' and ' + remote + ' where it masked a value\n'


def count(rx, out):
    m = re.search(rx, out)
    return int(m.group(1)) if m else -1


def row_scan(ctx, rid, expect, arg):
    fx = ctx['work'] + '/' + rid + '.txt'
    write_text(fx, fixture_text(arg, ctx['home']))
    cp = subprocess.run(['bash', ctx['tree'] + '/bin/loop-scan', fx], capture_output=True, text=True, env=ctx['env'], cwd=ctx['work'])
    out = (cp.stdout + cp.stderr).replace('\\', '/')
    got = {'rc': cp.returncode, 'hits': count(r'\bhits=(\d+)', out), 'tag': max(count(r'\btag=(\d+)', out), 0),
           'path': max(count(r'\bpath=(\d+)', out), 0), 'skipped': count(r'control_lines_skipped=(\d+)', out)}
    want = dict((k, int(v)) for k, v in (x.split('=') for x in expect.split(',')))
    ok = 'control=fired' in out and 'name_control=fired' in out
    for k, v in want.items():
        if k == 'at':
            ok = ok and ('hit at ' + fx + ':' + str(v)) in out
        else:
            ok = ok and got[k] == v
    return ok, 'expected=%s actual=rc=%d,hits=%d,tag=%d,path=%d,skipped=%d control_fired=%s out_sha=%s' % (
        expect, got['rc'], got['hits'], got['tag'], got['path'], got['skipped'], 'control=fired' in out, sha(out))


KINDS = {'scan': row_scan, 'phrase': row_phrase}


def main():
    tree, home, work = env_dirs(USAGE)
    env = make_env(home, drop=('LOOP_GOAL',))
    ctx = {'tree': tree, 'home': home, 'work': work, 'env': env}
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    return tally(rows, KINDS, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
