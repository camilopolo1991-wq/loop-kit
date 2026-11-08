#!/usr/bin/env python3
"""K11-C5 rows runner: install.sh --confine writes only under the given LOOP_HOME and refuses an unset or relative one.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the first three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: each row makes its own throwaway HOME under it (also USERPROFILE and the cwd of the child),
                   with LOOP_HOME and the temporary folder inside that HOME; the throwaway is removed when the row is done
  LOOP_WORK        the work folder; the before and after walk listings of each row are written to k11c5-walks/ under it
  LOOP_PY          handed to the child as the interpreter argument (defaults to the interpreter running this file)

Rows (rows.txt, id :: kind :: expect :: arg). Every row runs bash LOOP_TREE/install.sh <interpreter> [--confine] in a fresh
throwaway HOME; a walk of that HOME (every file, with the sha256 of its bytes) is taken before and after the run:
  confined   --confine, LOOP_HOME set to a folder inside the throwaway HOME: exit 0, at least one file written, and every
             written (new or changed) file lies under LOOP_HOME; the temporary folder is also inside the HOME, so a leftover
             there would be a written file outside LOOP_HOME and fail the row
  unset      the control: --confine with LOOP_HOME removed from the child environment (only there): exit 2, the refusal line
             names --confine, and the walk shows nothing written
  relative   --confine with a relative LOOP_HOME: exit 2, the refusal line names --confine, and the walk shows nothing
             written (the child's cwd is the throwaway HOME, so a wrongly accepted relative path would land inside the walk)
  control    the run without --confine into the same kind of throwaway HOME: exit 0 and at least one written file lies
             outside LOOP_HOME; the first of them are named by their path under the HOME

Prints PASS or FAIL per row with expected and actual, then rows=N pass=P fail=F. Nothing is spawned in the background and
nothing is killed.
"""
import hashlib
import os
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, remove_path, shafull, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] '
         'python run.py (no positional argument)')
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS', 'LOOP_PY')
REFUSAL = '--confine needs LOOP_HOME'


def walk(root):
    """{relative path: sha256 of the bytes} of every file under root, forward slashes."""
    out = {}
    for d, _dirs, files in os.walk(root):
        for f in files:
            p = fwd(os.path.join(d, f))
            out[p[len(root) + 1:]] = shafull(read_bytes(p) or b'')
    return out


def written(before, after):
    """The sorted relative paths in after that are new or changed against before."""
    return sorted(p for p, h in after.items() if before.get(p) != h)


def save_walk(ctx, rid, tag, listing):
    d = ctx['work'] + '/k11c5-walks'
    os.makedirs(d, exist_ok=True)
    write_text('%s/%s.%s.txt' % (d, rid, tag), ''.join('%s\t%s\n' % (p, listing[p]) for p in sorted(listing)))


def run_one(ctx, rid, confine, loop_home):
    """Run install.sh in a fresh throwaway HOME. loop_home: a str relative to the HOME to be made absolute ('abs:<rel>'),
    'rel:<text>' left as written, or None to remove LOOP_HOME from the child environment. Returns a result dict."""
    home = '%s/k11c5-%s-%d' % (ctx['home'], rid[:1], time.time_ns())
    os.makedirs(home)
    try:
        tmp = home + '/systmp'
        os.makedirs(tmp)
        extra = {'TMPDIR': tmp, 'TMP': tmp, 'TEMP': tmp}
        drop = list(DROP)
        if loop_home is None:
            drop.append('LOOP_HOME')
        elif loop_home.startswith('abs:'):
            lh = home + '/' + loop_home[4:]
            extra['LOOP_HOME'] = lh
        else:
            lh = loop_home[4:]
            extra['LOOP_HOME'] = lh
        env = make_env(home, extra, drop)
        lhome = extra.get('LOOP_HOME')
        before = walk(home)
        cmd = ['bash', ctx['tree'] + '/install.sh', ctx['py']] + (['--confine'] if confine else [])
        cp = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, cwd=home)
        after = walk(home)
        save_walk(ctx, rid, 'before', before)
        save_walk(ctx, rid, 'after', after)
        new = written(before, after)
        under = None
        if lhome is not None and lhome.startswith(home + '/'):
            prefix = lhome[len(home) + 1:] + '/'
            under = [p for p in new if p.startswith(prefix)]
        return {'rc': cp.returncode, 'err': cp.stderr, 'out': cp.stdout, 'new': new, 'under': under,
                'before': len(before), 'after': len(after), 'tmp_left': os.path.isdir(lhome + '/tmp') if lhome and os.path.isabs(lhome) else False}
    finally:
        remove_path(home)


def osha(r):
    return hashlib.sha256((r['out'] + r['err']).encode('utf-8', 'replace')).hexdigest()[:12]


def row_confined(ctx, rid, expect, arg):
    r = run_one(ctx, rid, True, 'abs:loop-confined')
    outside = [p for p in r['new'] if r['under'] is None or p not in r['under']]
    ok = r['rc'] == 0 and len(r['new']) > 0 and r['under'] is not None and not outside
    return ok, ('expected=exit 0, at least one file written, every written file under LOOP_HOME actual=exit %d, %d file(s) written '
                '(walk %d before, %d after), %d under LOOP_HOME, %d outside%s, out sha256=%s' % (
                    r['rc'], len(r['new']), r['before'], r['after'], len(r['under'] or []), len(outside),
                    (' first=' + ','.join(outside[:3])) if outside else '', osha(r)))


def row_refused(ctx, rid, expect, arg):
    r = run_one(ctx, rid, True, None if arg == 'unset' else 'rel:' + arg)
    ok = r['rc'] == 2 and REFUSAL in r['err'] and not r['new'] and r['before'] == r['after']
    return ok, ('expected=exit 2, the refusal line names --confine, nothing written actual=exit %d, refusal line %s, %d file(s) written '
                '(walk %d before, %d after), out sha256=%s' % (
                    r['rc'], 'present' if REFUSAL in r['err'] else 'absent', len(r['new']), r['before'], r['after'], osha(r)))


def row_control(ctx, rid, expect, arg):
    r = run_one(ctx, rid, False, 'abs:loop-confined')
    outside = [p for p in r['new'] if r['under'] is None or p not in r['under']]
    ok = r['rc'] == 0 and len(outside) > 0
    return ok, ('expected=exit 0 and at least one file written outside LOOP_HOME actual=exit %d, %d file(s) written, %d under LOOP_HOME, '
                '%d outside, first outside: %s, out sha256=%s' % (
                    r['rc'], len(r['new']), len(r['under'] or []), len(outside), ', '.join(outside[:3]) or 'none', osha(r)))


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    info_sha((('tests/rows/K11-C5/run.py', here + '/run.py'), ('tests/rows/K11-C5/rows.txt', here + '/rows.txt')))
    rows = load_rows(here + '/rows.txt')
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    kinds = {'confined': lambda r, e, a: row_confined(ctx, r, e, a), 'refused': lambda r, e, a: row_refused(ctx, r, e, a),
             'control': lambda r, e, a: row_control(ctx, r, e, a)}
    return tally(rows, kinds, (), True)


if __name__ == '__main__':
    sys.exit(main())
