#!/usr/bin/env python3
"""S01-C1 rows runner: bin/loop-skill-lint judges every SKILL.md under a skills folder, one rule at a time.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expectations in rows.txt, so a tree
without the tool prints FAIL on the rows that need it), LOOP_ROWS_HOME (the home every spawned process gets, with LOOP_HOME at
that home plus /.loop), LOOP_WORK (a work folder, created when absent; every fixture is written there at run time from the
row text), LOOP_PY (the interpreter the tool and the install resolve), LOOP_NAMES_FILE (passed through to the install).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
The tool is run as bash <tree>/bin/loop-skill-lint. The installed-tool row installs the tree into a fresh home under
LOOP_WORK by the install in the environment form (no positional argument) and compares the sha256 of the installed copy of
each of the two bin files with the tree's file. The runner removes at its start only what its own manifest file
(s01c1-manifest.txt in LOOP_WORK) lists from an earlier run. Every leak shape and the lint's control line are built here at
run time from parts, so no committed file holds one. Prints PASS or FAIL per row with expected and actual; a sha256 stands in
for output that could hold a path. Nothing is spawned in the background, nothing is killed, no timeout is set.
"""
import hashlib
import os
import re
import subprocess
import sys
import time

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> LOOP_PY=<python> LOOP_NAMES_FILE=<file> python run.py (no positional argument)'
MANIFEST = 's01c1-manifest.txt'
SK = 'good-skill'
DESC = 'description: A constructed one-line description.'
BIN_FILES = ('loop-skill-lint', 'loop_skill_lint.py')


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def sha(s):
    if isinstance(s, str):
        s = s.encode('utf-8', 'replace')
    return hashlib.sha256(s).hexdigest()[:12]


def shafull(b):
    return hashlib.sha256(b).hexdigest()


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', 3)])
    return rows


def read_bytes(p):
    try:
        with open(p, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


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
        if p and fwd(p).startswith(work + '/') and fwd(p) != work + '/' + MANIFEST:
            remove_path(p)
            n += 1
    os.remove(mf)
    return n


def fresh_path(ctx, kind, tag):
    p = '%s/%s-%s-%d' % (ctx['work'], kind, tag, time.time_ns())
    with open(ctx['work'] + '/' + MANIFEST, 'a', encoding='utf-8') as fh:
        fh.write(p + '\n')
    return p


# ---- fixture text -------------------------------------------------------------------------------------------------

def doc(name=SK, desc=(DESC,), body=('# A constructed skill', 'A constructed body line.')):
    return ('\n'.join(['---', 'name: ' + name] + list(desc) + ['---'] + list(body)) + '\n').encode('utf-8')


def lines_exact(n):
    return doc(body=['text %d' % i for i in range(n - 4)])


def bytes_exact(n):
    body = ['x' * 150] * 120
    base = len(doc(body=body))
    return doc(body=body + ['y' * (n - base - 1)])


def ref(n, first):
    return ('\n'.join([first] + ['reference line %d' % i for i in range(n - 1)]) + '\n').encode('utf-8')


def leak_users():
    return 'see ' + '/' + 'Users' + '/' + 'x'


def leak_home():
    return 'see ' + '/' + 'home' + '/' + 'x'


def leak_drive(sep, word):
    return 'see ' + 'C' + ':' + sep + word + sep + 'x'


def leak_tag():
    return 'see ' + 'a' + '/' + chr(91) + 'NAME' + chr(93) + '/x'


def control_lines():
    """The lint's own control: one line per leak shape, built here the way the tool builds it."""
    return ['control ' + '/' + 'Users' + '/' + 'x', 'control ' + '/' + 'home' + '/' + 'x',
            'control ' + 'C' + ':' + '/' + 'Users' + '/' + 'x', 'control ' + 'a' + '/' + chr(91) + 'NAME' + chr(93) + '/x']


def with_line(line):
    return doc(body=['# A constructed skill', line])


def fixtures():
    """id -> {relative path: bytes}; a key ending in a slash is an empty folder."""
    s = SK + '/SKILL.md'
    r = SK + '/references/'
    return {
        'good': {s: doc()},
        'name': {s: doc(name='other-skill')},
        'namechars': {'Bad_Skill/SKILL.md': doc(name='Bad_Skill')},
        'nodesc': {s: doc(desc=())},
        'desconeline': {s: doc(desc=(DESC, '  and a second line of the description'))},
        'desc1024': {s: doc(desc=('description: ' + 'd' * 1024,))},
        'desc1023': {s: doc(desc=('description: ' + 'd' * 1023,))},
        'lines200': {s: lines_exact(200)},
        'lines199': {s: lines_exact(199)},
        'bytes20000': {s: bytes_exact(20000)},
        'bytes19999': {s: bytes_exact(19999)},
        'refsdepth': {s: doc(), r + 'sub/a.md': ref(5, 'A reference')},
        'refsfiles': {s: doc(), r + 'emptydir/': b''},
        'refsflat': {s: doc(), r + 'a.md': ref(5, 'A reference')},
        'refs101': {s: doc(), r + 'long.md': ref(101, 'A reference')},
        'refs100': {s: doc(), r + 'long.md': ref(100, 'A reference')},
        'refs101ok': {s: doc(), r + 'long.md': ref(101, '## Contents')},
        'cross': {s: with_line('See ../other-skill/SKILL.md for more.')},
        'crossown': {s: with_line('See ../' + SK + '/SKILL.md and ./references/a.md for more.')},
        'leakusers': {s: with_line(leak_users())},
        'leakhome': {s: with_line(leak_home())},
        'leakdrive': {s: with_line(leak_drive('/', 'Users'))},
        'leakdriveback': {s: with_line(leak_drive('\\', 'users'))},
        'leaktag': {s: with_line(leak_tag())},
        'leakref': {s: doc(), r + 'a.md': ('A reference\n' + leak_users() + '\n').encode('utf-8')},
        'leakcontrol': {s: doc(body=['# A constructed skill'] + control_lines())},
        'nested': {s: doc(), 'group/inner-skill/SKILL.md': doc(name='other-name')},
        'nestedok': {s: doc(), 'group/inner-skill/SKILL.md': doc(name='inner-skill')},
        'leakprose': {s: with_line('the redactor writes ' + chr(91) + 'NAME' + chr(93) + ' and ' + chr(91) + 'GIT_REMOTE' + chr(93) + ' in prose')},
        'leaknear': {s: with_line('the users folder, a home dir, ~/.loop/bin, C: alone, [x] and [name] in prose')},
    }


def write_fixture(ctx, fid):
    root = fresh_path(ctx, 'fx', fid)
    for rel, data in fixtures()[fid].items():
        p = root + '/' + rel
        if rel.endswith('/'):
            os.makedirs(p, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'wb') as fh:
                fh.write(data)
    return root


# ---- running the tool ---------------------------------------------------------------------------------------------

def tool_env(ctx, skills_dir=None):
    env = dict(ctx['env'])
    env.pop('LOOP_SKILLS_DIR', None)
    if skills_dir is not None:
        env['LOOP_SKILLS_DIR'] = skills_dir
    return env


def run_tool(ctx, args, skills_dir=None):
    cp = subprocess.run(['bash', ctx['tree'] + '/bin/loop-skill-lint'] + args, capture_output=True, text=True,
                        encoding='utf-8', errors='replace', env=tool_env(ctx, skills_dir), cwd=ctx['work'])
    return cp.returncode, (cp.stdout + cp.stderr).replace('\r', '')


def parse(out):
    got = {'skills': -1, 'broken': -1, 'rules': set(), 'lines': -1, 'bytes': -1, 'control': 'control=fired' in out}
    m = re.search(r'^loop-skill-lint: skills=(\d+) broken=(\d+) control=fired$', out, re.M)
    if m:
        got['skills'], got['broken'] = int(m.group(1)), int(m.group(2))
    nskill = 0
    for m in re.finditer(r'^skill=(\S+) lines=(\d+) bytes=(\d+) verdict=(ok|broken)(?: rules=(\S+))?$', out, re.M):
        if nskill == 0:
            got['lines'], got['bytes'] = int(m.group(2)), int(m.group(3))
        nskill += 1
        if m.group(5):
            got['rules'].update(m.group(5).split(','))
    got['skill_lines'] = nskill
    return got


def judge(rc, out, expect):
    got = parse(out)
    got['rc'] = rc
    ok = True
    for pair in expect.split(','):
        k, v = pair.split('=', 1)
        if k == 'rules':
            want = set() if v == 'none' else set(v.split('+'))
            ok = ok and got['rules'] == want
        else:
            ok = ok and got[k] == int(v)
    if rc in (0, 1):
        ok = ok and got['control'] and got['skills'] == got['skill_lines']
    shown = ','.join(sorted(got['rules'])) or 'none'
    return ok, 'expected=%s actual=rc=%d,skills=%d,broken=%d,lines=%d,bytes=%d,rules=%s control_fired=%s out_sha=%s' % (
        expect, rc, got['skills'], got['broken'], got['lines'], got['bytes'], shown.replace(',', '+'), got['control'], sha(out))


def row_kit(ctx, rid, expect, arg):
    rc, out = run_tool(ctx, [ctx['tree'] + '/' + arg])
    return judge(rc, out, expect)


def row_fx(ctx, rid, expect, arg):
    rc, out = run_tool(ctx, [write_fixture(ctx, arg)])
    return judge(rc, out, expect)


def row_env(ctx, rid, expect, arg):
    rc, out = run_tool(ctx, [], write_fixture(ctx, arg))
    return judge(rc, out, expect)


def row_argwins(ctx, rid, expect, arg):
    a, b = arg.split('|')
    rc, out = run_tool(ctx, [write_fixture(ctx, a)], write_fixture(ctx, b))
    return judge(rc, out, expect)


def row_none(ctx, rid, expect, arg):
    rc, out = run_tool(ctx, [])
    return judge(rc, out, expect)


def row_two(ctx, rid, expect, arg):
    rc, out = run_tool(ctx, [write_fixture(ctx, 'good'), write_fixture(ctx, 'good')])
    return judge(rc, out, expect)


def row_nodir(ctx, rid, expect, arg):
    rc, out = run_tool(ctx, [fresh_path(ctx, 'absent', arg)])
    return judge(rc, out, expect)


def row_nopy(ctx, rid, expect, arg):
    """LOOP_PY names a path that is no interpreter: the stub exits 3, a fourth exit beside 0, 1 and 64."""
    env = tool_env(ctx)
    env['LOOP_PY'] = fresh_path(ctx, 'nopython', arg)
    cp = subprocess.run(['bash', ctx['tree'] + '/bin/loop-skill-lint', write_fixture(ctx, 'good')], capture_output=True,
                        text=True, encoding='utf-8', errors='replace', env=env, cwd=ctx['work'])
    out = (cp.stdout + cp.stderr).replace('\r', '')
    want = int(expect.split('=')[1])
    said = 'LOOP_PY does not resolve' in out
    return cp.returncode == want and said, 'expected=%s and the message names LOOP_PY actual=rc=%d names_it=%s out_sha=%s' % (
        expect, cp.returncode, said, sha(out))


def tag_literals(text):
    return set(re.findall(r'\[([A-Z][A-Z_]*)\]', text))


def row_tagsync(ctx, rid, expect, arg):
    """The lint's TAG_WORDS equal the tag literals in the redactor module (the kit's one source of the tags)."""
    import ast
    lint = read_bytes(ctx['tree'] + '/bin/loop_skill_lint.py')
    src = read_bytes(ctx['tree'] + '/bin/loop_redact.py')
    if lint is None or src is None:
        return False, 'expected=lint words equal redactor tags actual=file absent lint=%s redactor=%s' % (lint is not None, src is not None)
    words = None
    for node in ast.parse(lint.decode('utf-8')).body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'TAG_WORDS' for t in node.targets):
            words = set(ast.literal_eval(node.value))
    want = tag_literals(src.decode('utf-8', 'replace'))
    ok = words is not None and words == want and len(want) >= 10
    return ok, 'expected=lint words equal redactor tags actual=lint=%s redactor=%d only_lint=%d only_redactor=%d' % (
        'absent' if words is None else len(words), len(want), len((words or set()) - want), len(want - (words or set())))


def row_install(ctx, rid, expect, arg):
    home = fresh_path(ctx, 'home', 'inst')
    os.makedirs(home)
    env = dict(ctx['env'])
    env.update({'HOME': home, 'USERPROFILE': home, 'LOOP_HOME': home + '/.loop', 'LOOP_PY': ctx['py'],
                'LOOP_NAMES_FILE': ctx['names']})
    for k in ('LOOP_WITH_TESTS', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS',
              'LOOP_BACKUP_DIR', 'LOOP_GOAL', 'JOURNAL_FILE', 'LOOP_SKILLS_DIR'):
        env.pop(k, None)
    cp = subprocess.run(['bash', ctx['tree'] + '/install.sh'], capture_output=True, text=True, encoding='utf-8',
                        errors='replace', env=env, cwd=ctx['work'])
    same = 0
    shown = []
    for f in BIN_FILES:
        a = read_bytes(ctx['tree'] + '/bin/' + f)
        b = read_bytes(home + '/.loop/bin/' + f)
        shown.append('%s tree=%s home=%s' % (f, sha(a) if a is not None else 'absent', sha(b) if b is not None else 'absent'))
        same += (a is not None and a == b)
    ok = cp.returncode == 0 and same == len(BIN_FILES)
    return ok, 'expected=install exit 0, both tool files in the home bin with the tree hash actual=exit %d identical=%d of %d %s' % (
        cp.returncode, same, len(BIN_FILES), '; '.join(shown))


KINDS = {'kit': row_kit, 'fx': row_fx, 'env': row_env, 'argwins': row_argwins, 'none': row_none, 'two': row_two,
         'nodir': row_nodir, 'nopy': row_nopy, 'tagsync': row_tagsync, 'install': row_install}


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
    tree, home, work = fwd(tree_e), fwd(home_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    py = fwd(os.environ.get('LOOP_PY') or sys.executable)
    env = dict(os.environ)
    env.update({'HOME': home, 'USERPROFILE': home, 'LOOP_HOME': home + '/.loop', 'PYTHONDONTWRITEBYTECODE': '1', 'LOOP_PY': py})
    env.pop('LOOP_GOAL', None)
    cleaned = clean_earlier(work)
    print('cleaned %d path(s) listed by an earlier run' % cleaned)
    ctx = {'tree': tree, 'home': home, 'work': work, 'env': env, 'py': py, 'names': os.environ.get('LOOP_NAMES_FILE', '')}
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        fn = KINDS.get(kind)
        if fn is None:
            ok, detail = False, 'unknown kind ' + kind
        else:
            try:
                ok, detail = fn(ctx, rid, expect, arg)
            except Exception as exc:
                ok, detail = False, 'expected=row runs actual=error %s' % type(exc).__name__
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
