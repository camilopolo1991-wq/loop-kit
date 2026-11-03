"""One library under the row runners (tests/rows/*/run.py): the helpers they used to copy, in one place.

A runner imports it by a path relative to its own file (not on the script folder being on the module path) and defines
none of the names defined here. Nothing here spawns a process or writes outside the folders a runner hands it.

The runners that call env_dirs are run as `python run.py`, with no positional argument, and read LOOP_TREE (the tree
under test), LOOP_ROWS_HOME and LOOP_WORK from the environment; given a positional argument or with one of the three
unset they print their usage line and exit 64.
"""
import hashlib
import json
import os
import sys
import time

SEP = ' ;; '


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def sha(s):
    """First twelve hex digits of the sha256 of a str (utf-8) or bytes."""
    if isinstance(s, str):
        s = s.encode('utf-8', 'replace')
    return hashlib.sha256(s).hexdigest()[:12]


def shafull(b):
    return hashlib.sha256(b).hexdigest()


def shatext(s):
    return shafull(s.encode('utf-8', 'replace'))


def load_rows(path, maxsplit=3):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', maxsplit)])
    return rows


def read_bytes(p):
    try:
        with open(p, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def text_of(tree, rel):
    data = read_bytes(tree + '/' + rel)
    if data is None:
        return None
    return data.decode('utf-8', 'replace').replace('\r', '')


def read_lines(ctx, rel):
    b = read_bytes(ctx['tree'] + '/' + rel)
    return None if b is None else b.decode('utf-8', 'replace').replace('\r\n', '\n').split('\n')


def write_text(path, text):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


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


def register(work, manifest, path):
    """Append path to the calling runner's manifest file under work (what clean_earlier removes next time)."""
    with open(work + '/' + manifest, 'a', encoding='utf-8') as fh:
        fh.write(path + '\n')


def clean_earlier(work, manifest, say=False):
    """Remove only what an earlier run of the calling runner wrote, as listed in its own manifest file under work;
    returns how many paths it removed (printed as the cleaned line when say is true)."""
    mf = work + '/' + manifest
    data = read_bytes(mf)
    n = 0
    if data is not None:
        for p in data.decode('utf-8', 'replace').split('\n'):
            p = p.strip()
            if p and fwd(p).startswith(work + '/') and fwd(p) != mf and os.path.exists(p):
                remove_path(p)
                n += 1
        os.remove(mf)
    if say:
        print('cleaned %d path(s) listed by an earlier run' % n)
    return n


def make_env(home, extra=None, drop=()):
    """The one environment builder: a copy of the environment with HOME and USERPROFILE at home, LOOP_HOME at home/.loop
    and PYTHONDONTWRITEBYTECODE=1; the names in drop removed, then the pairs in extra set."""
    env = dict(os.environ)
    env.update({'HOME': home, 'USERPROFILE': home, 'LOOP_HOME': home + '/.loop', 'PYTHONDONTWRITEBYTECODE': '1'})
    for k in drop:
        env.pop(k, None)
    if extra:
        env.update(extra)
    return env


def journal_file(work):
    """An empty fixture journal under work; returns its path."""
    jf = work + '/journal-fixture.log'
    write_text(jf, '')
    return jf


def fresh_home(work, tag):
    home = '%s/home-%s-%d' % (work, tag, time.time_ns())
    os.makedirs(home)
    return home


def run_phrase(tree, expect, arg, prefix=''):
    """arg is 'relative path|phrase'; the row passes when the phrase is found (or absent) as expect says. prefix is a
    format with one %s for the path, put before the detail."""
    rel, phrase = arg.split('|', 1)
    pre = prefix % rel if prefix else ''
    data = read_bytes(tree + '/' + rel)
    if data is None:
        return False, pre + 'expected=%s actual=unreadable' % expect
    actual = 'found' if phrase.encode('utf-8') in data else 'absent'
    return actual == expect, pre + 'expected=%s actual=%s file_sha=%s' % (expect, actual, sha(data))


def run_line_phrase(tree, expect, arg):
    """arg is 'relative path|line number|phrase'; the phrase is looked for on that line only."""
    rel, num, phrase = arg.split('|', 2)
    with open(tree + '/' + rel, 'rb') as fh:
        data = fh.read()
    found = phrase.encode('utf-8') in data.split(b'\n')[int(num) - 1]
    return found == (expect == 'found'), 'expected=%s actual=%s file=%s line=%s' % (
        expect, 'found' if found else 'absent', rel, num)


def row_phrase(ctx, rid, expect, arg):
    rel, phrase = arg.split('|', 1)
    text = text_of(ctx['tree'], rel)
    if text is None:
        return False, 'expected=found actual=file absent'
    ok = phrase in text
    return ok, 'expected=found actual=%s phrase_sha=%s' % ('found' if ok else 'not found', sha(phrase))


def row_linephrase(ctx, rid, expect, arg):
    rel, prefix, phrase = arg.split('|', 2)
    text = text_of(ctx['tree'], rel)
    if text is None:
        return False, 'expected=found actual=file absent'
    lines = [ln for ln in text.split('\n') if ln.startswith(prefix)]
    ok = any(phrase in ln for ln in lines)
    return ok, 'expected=found lines_with_prefix=%d actual=%s phrase_sha=%s' % (len(lines), 'found' if ok else 'not found', sha(phrase))


def row_phrases(ctx, rid, expect, arg):
    """arg is 'relative path|phrase ;; phrase ...'; every phrase must be in the file."""
    rel, phrases = arg.split('|', 1)
    data = read_bytes(ctx['tree'] + '/' + rel)
    if data is None:
        return False, 'expected=%s actual=file absent' % expect
    text = data.decode('utf-8', 'replace').replace('\r', '')
    wanted = phrases.split(SEP)
    missing = [i + 1 for i, ph in enumerate(wanted) if ph not in text]
    ok = not missing
    return ok, 'expected=found phrases=%d actual=%s missing=%s file_sha=%s' % (
        len(wanted), 'found' if ok else 'not found', ','.join(str(m) for m in missing) or 'none', sha(data))


def row_present(ctx, expect, arg):
    b = read_bytes(ctx['tree'] + '/' + arg)
    if b is None:
        return False, 'expected=%s present actual=absent' % arg
    return len(b) > 0, 'expected=%s present and not empty actual=%d bytes sha256=%s' % (arg, len(b), shafull(b))


def hook_class(cp, hide):
    """(allow, '') or (deny, the reason cut at 70 characters, a hidden one as its sha) or (other, rc and output shas)."""
    if cp.returncode == 0 and cp.stdout == '' and cp.stderr == '':
        return 'allow', ''
    if cp.returncode == 0 and cp.stderr == '':
        try:
            h = json.loads(cp.stdout)['hookSpecificOutput']
            if h['permissionDecision'] == 'deny':
                reason = str(h.get('permissionDecisionReason', ''))
                if any(x and x in reason for x in hide):
                    reason = 'sha256:' + sha(reason)
                return 'deny', reason[:70]
        except Exception:
            pass
    return 'other', 'rc=%s out=%s err=%s' % (cp.returncode, sha(cp.stdout), sha(cp.stderr))


def info_sha(pairs):
    """Print one info line per (label, path): the sha256 of the file, or absent."""
    for label, p in pairs:
        b = read_bytes(p)
        print('info sha256 %s %s' % (label, shafull(b) if b is not None else 'absent'))


def env_dirs(usage, argv=True):
    """(tree, home, work) from LOOP_TREE, LOOP_ROWS_HOME and LOOP_WORK, forward slashes, work created when absent.
    Prints usage and exits 64 when a positional argument is given (argv true) or one of the three is unset."""
    vals = [os.environ.get(k) for k in ('LOOP_TREE', 'LOOP_ROWS_HOME', 'LOOP_WORK')]
    if (argv and len(sys.argv) > 1) or not all(vals):
        print(usage)
        sys.exit(64)
    tree, home, work = [fwd(v) for v in vals]
    os.makedirs(work, exist_ok=True)
    return tree, home, work


def dirs_or_args():
    """The older runners: (tree, home, work) from three positional arguments, or from the environment when none is given.
    Prints usage and exits (64 for an unset environment, 2 for a wrong argument count) when they are unusable."""
    if len(sys.argv) == 1:
        vals = [os.environ.get(k) for k in ('LOOP_TREE', 'LOOP_ROWS_HOME', 'LOOP_WORK')]
        if not all(vals):
            print('usage: run.py <tree> <home> <work>   or   LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> run.py')
            sys.exit(64)
        sys.argv[1:] = vals
    if len(sys.argv) != 4:
        print('usage: run.py <tree> <home> <work>')
        sys.exit(2)
    return fwd(sys.argv[1]), fwd(sys.argv[2]), fwd(sys.argv[3])


class Score:
    """The counts of one runner: row() prints a PASS or FAIL line, done() prints the summary and gives the exit code."""

    def __init__(self):
        self.passed = self.failed = 0

    def row(self, ok, rid, detail):
        self.passed += ok
        self.failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))

    def done(self, rows):
        print('rows=%d pass=%d fail=%d' % (len(rows), self.passed, self.failed))
        return 1 if self.failed else 0


def tally(rows, kinds, pre=(), guard=False, rid=True):
    """Judge each row [rid, kind, expect, arg] by kinds[kind](*pre, rid, expect, arg); rid false leaves the id out and
    None leaves all three out. An unknown kind fails; with guard an exception fails the row. Returns the exit code."""
    score = Score()
    for r, kind, expect, arg in rows:
        fn = kinds.get(kind)
        a = () if rid is None else ((r, expect, arg) if rid else (expect, arg))
        if fn is None:
            ok, detail = False, 'unknown kind ' + kind
        else:
            try:
                ok, detail = fn(*pre, *a)
            except Exception as exc:
                if not guard:
                    raise
                ok, detail = False, 'expected=row runs actual=error %s' % type(exc).__name__
        score.row(ok, r, detail)
    return score.done(rows)


def safe(ctx, s):
    """s, or its sha256 when it holds one of the paths in ctx['hide']."""
    for h in ctx['hide']:
        if h and h in s:
            return 'sha256:' + shatext(s)[:12]
    return s


def emit(ctx, rid, ok, expected, actual):
    """Count and print one row of a runner that keeps its counts in ctx (rows, pass, fail, hide)."""
    ctx['rows'] += 1
    ctx['pass' if ok else 'fail'] += 1
    print('%s %s expected=%s actual=%s' % ('PASS' if ok else 'FAIL', rid, safe(ctx, expected), safe(ctx, actual)))
