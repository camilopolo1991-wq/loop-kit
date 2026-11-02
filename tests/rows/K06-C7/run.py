#!/usr/bin/env python3
"""K06-C7 rows runner: a loop home per seat (install.sh honours LOOP_HOME).

Environment (no positional argument; exit 64 with the usage line when one is given or one of the first three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home; checked for being set, never written (every home a row uses is a throwaway one under LOOP_WORK)
  LOOP_WORK        the work folder; every fixture and throwaway home is written under it and listed in k06c7-manifest.txt
  LOOP_PY, LOOP_NAMES_FILE   handed to the children (LOOP_PY defaults to the interpreter running this file)

Every child gets HOME and USERPROFILE at a throwaway home and LOOP_HOME at that home's .loop, or at the second home
(.loop-second, a non-default name) where a row says so, or unset in row b. Hook rows carry LOOP_GOAL, a fixture goal id.

Rows (rows.txt, id :: kind :: expect :: arg):
  install    arg second: install.sh of the tree, environment form, HOME at H and LOOP_HOME at H/.loop-second: exit 0, bin and
             templates placed there, goals/ and scratch/ made there, config.env there with its LOOP_HOME and ENGINE_RECORD_DIR lines
             naming that home, nothing under H/.loop, agents, hooks and skills under the Claude home of H.
             arg default: the same install with LOOP_HOME unset (HOME at H2): everything under H2/.loop and config.env keeping
             the ~/.loop spelling of today.
  hook       arg first-goals | outside | second-evidence: the writer's path hook from LOOP_TREE/hooks with LOOP_HOME at the second
             home; expect is the decision and, for a deny, the first word of the reason.
  preflight  loop_preflight.py from LOOP_TREE/bin run from the second home and from the default home of row b: the same set of
             line kinds (first words), and the state line ends OK in both.
  dispatch   loop_dispatch.py --dry-run from LOOP_TREE/bin with LOOP_HOME at the second home, a stand-in claude binary pinned by
             LOOP_CLAUDE_BIN (never launched by a dry run) and a fixture goal held with a ruling: its prompt line names a goal path
             under the second home.
  upgrade    the K05-C1 upgrade form (LOOP_UPGRADE=1, LOOP_BACKUP_DIR) run against the installed second home after one bin file is
             edited and one template removed: exit 0, both files back as installed, config.env equal as bytes, the edited file backed up,
             nothing under H/.loop.
  control    a scratch copy of the second home's config.env with its LOOP_HOME line pointed at H/.loop fails row a's config check;
             printed as FAIL on a control line; the row passes when the real file passes the check and the copy fails it.

Prints PASS or FAIL per row with expected and actual (a row whose actual could hold a home path prints a sha256 only), then
rows=N pass=P fail=F. Nothing is spawned in the background and nothing is killed. The real claude binary is never launched.
"""
import json
import os
import re
import subprocess
import sys
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, hook_class, info_sha, load_rows, make_env, read_bytes, register, remove_path, sha, shafull, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] '
         'python run.py (no positional argument)')
MANIFEST = 'k06c7-manifest.txt'
GOAL = 'FIXT-01'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS', 'LOOP_TRIPWIRE_TESTS_DIR', 'SURFACES', 'LOOP_CLAUDE_BIN', 'CLAUDE_BIN', 'MAX_LEADERS')
CNT = re.compile(r'^upgrade: replaced (\d+), added (\d+), unchanged (\d+), hooks skipped (\d+)$', re.M)
EDIT_BIN = 'bin/loop_conf.py'
CUT_TPL = 'templates/TRAPS.md'


def norm(p):
    p = str(p).replace('\\', '/')
    return p.lower() if os.name == 'nt' else p


def throwaway_home(ctx, name):
    home = ctx['work'] + '/' + name
    register(ctx['work'], MANIFEST, home)
    os.makedirs(home)
    return home


def run_install(ctx, home, loop_home, extra=None):
    """bash LOOP_TREE/install.sh, environment form, HOME and USERPROFILE at home; loop_home None leaves LOOP_HOME unset."""
    env = make_env(home, {'LOOP_PY': ctx['py']}, DROP + (('LOOP_HOME',) if loop_home is None else ()))
    if loop_home is not None:
        env['LOOP_HOME'] = loop_home
    if extra:
        env.update(extra)
    return subprocess.run(['bash', ctx['tree'] + '/install.sh'], capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env=env, cwd=ctx['work'])


def second_state(ctx):
    if 'second' not in ctx:
        h = throwaway_home(ctx, 'k06c7-home')
        ctx['second'] = {'H': h, 'loop': h + '/.loop-second', 'cp': run_install(ctx, h, h + '/.loop-second')}
    return ctx['second']


def default_state(ctx):
    if 'default' not in ctx:
        h = throwaway_home(ctx, 'k06c7-home-default')
        ctx['default'] = {'H': h, 'loop': h + '/.loop', 'cp': run_install(ctx, h, None)}
    return ctx['default']


def config_ok(cfg, path):
    """Row a's config check: one LOOP_HOME line and one ENGINE_RECORD_DIR line, naming path and path/record."""
    if cfg is None:
        return False
    lines = cfg.decode('utf-8', 'replace').replace('\r', '').split('\n')
    lh = [ln for ln in lines if ln.startswith('LOOP_HOME=')]
    er = [ln for ln in lines if ln.startswith('ENGINE_RECORD_DIR=')]
    return len(lh) == 1 and len(er) == 1 and norm(lh[0][len('LOOP_HOME='):]) == norm(path) and norm(er[0][len('ENGINE_RECORD_DIR='):]) == norm(path) + '/record'


def tilde_config_ok(cfg):
    if cfg is None:
        return False
    lines = cfg.decode('utf-8', 'replace').replace('\r', '').split('\n')
    return 'LOOP_HOME=~/.loop' in lines and 'ENGINE_RECORD_DIR=~/.loop/record' in lines


def nonempty_dir(p):
    return os.path.isdir(p) and len(os.listdir(p)) > 0


def row_install(ctx, rid, expect, arg):
    st = second_state(ctx) if arg == 'second' else default_state(ctx)
    loop, h, cp = st['loop'], st['H'], st['cp']
    cfg = read_bytes(loop + '/config.env')
    cfg_ok = config_ok(cfg, loop) if arg == 'second' else tilde_config_ok(cfg)
    other = h + '/.loop' if arg == 'second' else h + '/.loop-second'
    placed = os.path.isfile(loop + '/bin/loop-scan') and os.path.isfile(loop + '/templates/GOAL.md')
    made = os.path.isdir(loop + '/goals') and os.path.isdir(loop + '/scratch')
    shared = all(nonempty_dir(h + '/.claude/' + d) for d in ('agents', 'hooks', 'skills'))
    elsewhere = os.path.exists(other)
    ok = cp.returncode == 0 and placed and made and cfg_ok and not elsewhere and shared
    return ok, ('expected=exit 0, bin and templates placed, goals and scratch made, config.env LOOP_HOME and ENGINE_RECORD_DIR lines right for the %s, '
                'nothing under the other home, agents hooks and skills under the Claude home actual=exit %d, placed %s, made %s, config %s, other home %s, '
                'claude home %s, config.env sha256=%s, out sha256=%s') % (
        expect, cp.returncode, 'yes' if placed else 'no', 'yes' if made else 'no', 'right' if cfg_ok else 'wrong',
        'present' if elsewhere else 'absent', 'filled' if shared else 'missing', shafull(cfg or b'')[:12],
        shafull((cp.stdout + cp.stderr).encode('utf-8', 'replace'))[:12])


def row_hook(ctx, rid, expect, arg):
    st = second_state(ctx)
    h, second = st['H'], st['loop']
    paths = {'first-goals': h + '/.loop/goals/' + GOAL + '/evidence/T01/writer/probe.txt',
             'outside': h + '/elsewhere/probe.txt',
             'second-evidence': second + '/goals/' + GOAL + '/evidence/T01/writer/probe.txt'}
    want, _, want_word = expect.partition(' ')
    payload = json.dumps({'tool_name': 'Write', 'tool_input': {'file_path': paths[arg], 'content': 'x'}})
    env = make_env(h, {'LOOP_HOME': second, 'LOOP_GOAL': GOAL}, DROP)
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/hooks/writer-path-guard.py'], input=payload, capture_output=True, text=True,
                        encoding='utf-8', errors='replace', env=env, cwd=ctx['work'])
    cls, reason = hook_class(cp, [h, second])
    word = reason.split()[0] if reason.split() else ''
    ok = cls == want and (not want_word or word == want_word)
    return ok, 'expected=decision %s%s actual=decision %s, first word %s, exit %d' % (
        want, ', first word ' + want_word if want_word else '', cls, word or 'none', cp.returncode)


def pre_run(ctx, home, loop):
    env = make_env(home, {'LOOP_HOME': loop, 'LOOP_PY': ctx['py']}, DROP)
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_preflight.py'], capture_output=True, text=True, encoding='utf-8',
                        errors='replace', env=env, cwd=ctx['work'])
    lines = [ln for ln in cp.stdout.replace('\r', '').split('\n') if ln and not ln[0].isspace()]
    kinds = sorted(set(ln.split()[0] for ln in lines))
    state = [ln for ln in lines if ln.split()[0] == 'state']
    return cp.returncode, kinds, len(state) == 1 and state[0].endswith(' OK'), cp.stdout


def row_preflight(ctx, rid, expect, arg):
    d, s = default_state(ctx), second_state(ctx)
    rc1, k1, s1, o1 = pre_run(ctx, d['H'], d['loop'])
    rc2, k2, s2, o2 = pre_run(ctx, s['H'], s['loop'])
    ok = rc1 == 0 and rc2 == 0 and k1 == k2 and len(k1) >= 8 and 'preflight' in k1 and s1 and s2
    return ok, 'expected=exit 0 from both homes, the same set of at least 8 line kinds, state line OK in both actual=exits %d and %d, kinds first home %d second home %d same %s (%s), state OK %s and %s' % (
        rc1, rc2, len(k1), len(k2), 'yes' if k1 == k2 else 'no', ','.join(k2), 'yes' if s1 else 'no', 'yes' if s2 else 'no')


def row_dispatch(ctx, rid, expect, arg):
    st = second_state(ctx)
    h, second = st['H'], st['loop']
    gd = second + '/goals/' + GOAL
    os.makedirs(gd, exist_ok=True)
    write_text(gd + '/GOAL.md', 'Fixture goal text for a dry run, long enough to be no stub. ' * 6 + '\n')
    write_text(gd + '/report.md', 'VERDICT: HELD\n')
    write_text(gd + '/RULING.md', 'fixture ruling\n')
    standin = ctx['work'] + '/k06c7-standin-claude'
    register(ctx['work'], MANIFEST, standin)
    write_text(standin, '#!/bin/sh\nexit 0\n')
    env = make_env(h, {'LOOP_HOME': second, 'LOOP_CLAUDE_BIN': standin, 'MAX_LEADERS': '99', 'LOOP_PY': ctx['py']}, DROP)
    env['LOOP_CLAUDE_BIN'] = standin
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_dispatch.py', GOAL, '--dry-run'], capture_output=True, text=True,
                        encoding='utf-8', errors='replace', env=env, cwd=ctx['work'])
    out = cp.stdout.replace('\r', '').replace('\\', '/')
    plines = [ln for ln in out.split('\n') if 'prompt:' in ln]
    want = norm(second + '/goals/' + GOAL + '/RULING.md')
    named = bool(plines) and want in norm(plines[0]) and (norm(h) + '/.loop/') not in norm(plines[0])
    ok = cp.returncode == 0 and named
    return ok, 'expected=exit 0 and a prompt line naming a goal path under the second home actual=exit %d, prompt line %s, names the second home goal path %s, line sha256=%s' % (
        cp.returncode, 'present' if plines else 'absent', 'yes' if named else 'no', shafull((plines[0] if plines else '').encode('utf-8', 'replace'))[:12])


def row_upgrade(ctx, rid, expect, arg):
    st = second_state(ctx)
    h, s = st['H'], st['loop']
    pb, pt, cfg0 = read_bytes(s + '/' + EDIT_BIN), read_bytes(s + '/' + CUT_TPL), read_bytes(s + '/config.env')
    if pb is None or pt is None or cfg0 is None:
        return False, 'expected=exit 0 actual=the second home is not installed (bin file %s, template %s, config.env %s)' % (
            'there' if pb is not None else 'absent', 'there' if pt is not None else 'absent', 'there' if cfg0 is not None else 'absent')
    edited = pb + b'\n# fixture edit\n'
    with open(s + '/' + EDIT_BIN, 'wb') as fh:
        fh.write(edited)
    remove_path(s + '/' + CUT_TPL)
    bk = ctx['work'] + '/k06c7-backup'
    register(ctx['work'], MANIFEST, bk)
    env = make_env(h, {'LOOP_PY': ctx['py'], 'LOOP_HOME': s, 'LOOP_UPGRADE': '1', 'LOOP_BACKUP_DIR': bk}, DROP)
    env.update({'LOOP_UPGRADE': '1', 'LOOP_BACKUP_DIR': bk})
    cp = subprocess.run(['bash', ctx['tree'] + '/install.sh'], capture_output=True, text=True, encoding='utf-8', errors='replace',
                        env=env, cwd=ctx['work'])
    m = CNT.search(cp.stdout.replace('\r', ''))
    counts = tuple(int(x) for x in m.groups()) if m else None
    back = read_bytes(bk + '/.loop/' + EDIT_BIN) == edited
    ok = (cp.returncode == 0 and counts is not None and counts[0] >= 1 and counts[1] >= 1 and read_bytes(s + '/' + EDIT_BIN) == pb
          and read_bytes(s + '/' + CUT_TPL) == pt and read_bytes(s + '/config.env') == cfg0 and back and not os.path.exists(h + '/.loop'))
    return ok, ('expected=exit 0, counts line with replaced and added at least 1, edited file and cut template back as installed, config.env equal as bytes, '
                'edited file in the backup, nothing under the first home actual=exit %d counts=%s, bin file %s, template %s, config.env %s, backup %s, first home %s, out sha256=%s') % (
        cp.returncode, counts, 'restored' if read_bytes(s + '/' + EDIT_BIN) == pb else 'not restored',
        'restored' if read_bytes(s + '/' + CUT_TPL) == pt else 'not restored', 'equal' if read_bytes(s + '/config.env') == cfg0 else 'changed',
        'holds it' if back else 'lacks it', 'present' if os.path.exists(h + '/.loop') else 'absent', shafull((cp.stdout + cp.stderr).encode('utf-8', 'replace'))[:12])


def row_control(ctx, rid, expect, arg):
    st = second_state(ctx)
    h, s = st['H'], st['loop']
    cfg = read_bytes(s + '/config.env')
    real_ok = config_ok(cfg, s)
    d = ctx['work'] + '/k06c7-control'
    register(ctx['work'], MANIFEST, d)
    os.makedirs(d)
    lines = (cfg or b'').decode('utf-8', 'replace').replace('\r', '').split('\n')
    changed = 0
    out = []
    for ln in lines:
        if ln.startswith('LOOP_HOME='):
            ln = 'LOOP_HOME=' + h + '/.loop'
            changed += 1
        out.append(ln)
    write_text(d + '/config.env', '\n'.join(out))
    copy_ok = config_ok(read_bytes(d + '/config.env'), s)
    print('%s control %s expected=config.env LOOP_HOME and ENGINE_RECORD_DIR lines naming the second home actual=%s (scratch copy of the second home config.env with its LOOP_HOME line pointed at the first home, %d line changed)' % (
        'PASS' if copy_ok else 'FAIL', 'g-control-config-check', 'right' if copy_ok else 'wrong', changed))
    ok = real_ok and not copy_ok and changed == 1
    return ok, 'expected=the real config.env passes row a\'s config check and the copy fails it actual=real %s, copy %s, %d line changed, controls=1' % (
        'passes' if real_ok else 'fails', 'passes' if copy_ok else 'fails', changed)


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K06-C7/run.py', here + '/run.py'), ('tests/rows/K06-C7/rows.txt', here + '/rows.txt')))
    rows = load_rows(here + '/rows.txt')
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    kinds = {'install': lambda r, e, a: row_install(ctx, r, e, a), 'hook': lambda r, e, a: row_hook(ctx, r, e, a),
             'preflight': lambda r, e, a: row_preflight(ctx, r, e, a), 'dispatch': lambda r, e, a: row_dispatch(ctx, r, e, a),
             'upgrade': lambda r, e, a: row_upgrade(ctx, r, e, a), 'control': lambda r, e, a: row_control(ctx, r, e, a)}
    return tally(rows, kinds, (), True)


if __name__ == '__main__':
    sys.exit(main())
