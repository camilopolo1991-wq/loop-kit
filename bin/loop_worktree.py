#!/usr/bin/env python3
"""loop-worktree: one worktree per running goal (KIT-10 C4 (a)).

  loop-worktree open <GOAL-ID>    create $LOOP_HOME/work/<GOAL-ID>/record, a worktree of the record repository (ENGINE_RECORD_DIR) on the
                                  branch rec-<goal-id lower>, cut from the record branch (RECORD_BRANCH) tip; and, when the GOAL's Authority
                                  names the kit, $LOOP_HOME/work/<GOAL-ID>/kit on the branch <goal-id lower>, cut from the kit's main branch
                                  (KIT_BRANCH, default main). Refuses (exit 3, nothing made) when either folder or either branch exists.
                                  Prints one line per worktree: "record <path>" and "kit <path>".
  loop-worktree close <GOAL-ID>   remove the goal's worktrees, only after the record branch rec-<goal-id lower> is merged into the record
                                  branch, and only when each is clean (an untracked *.lock file is not dirt). It never deletes a branch.

The kit is named by the GOAL, not by a flag: the "Authority:" paragraph of GOAL.md (from the line that starts with Authority: to the next
blank line or the next "Label:" line) holds the text ~/loop-kit (not followed by a letter, digit, underscore or dash). The kit repository is
KIT_DIR from the environment or config.env, else ~/loop-kit.

Exit codes: 0 done, 2 not configured or bad input, 3 refused (state), 4 a repository command failed, 64 usage.
The dispatcher calls ensure(): the same creation, but a worktree already there on its branch is reused and only the absent ones are made.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import loop_conf  # noqa: E402

ID_RE = re.compile(r'^[A-Za-z][A-Za-z0-9]{1,11}-\d{2,3}$')
KIT_NAMED = re.compile(r'~/loop-kit(?![A-Za-z0-9_-])')
USAGE = 'usage: loop-worktree open <GOAL-ID> | close <GOAL-ID>'
STEP, STATE = 'docs/JOURNAL.md', 'docs/STATE.md'      # the two files committed only on the record branch's own work tree


class Refused(Exception):
    def __init__(self, msg, code=3):
        Exception.__init__(self, msg)
        self.msg = msg
        self.code = code


def run(args, cwd, inp=None):
    """(returncode, stdout, stderr) of one repository command in cwd."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', LC_ALL='C')
    p = subprocess.run(['git'] + list(args), cwd=cwd, input=inp, capture_output=True, env=env)
    return p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')


def first_line(text):
    ls = [x for x in text.replace('\r', '').split('\n') if x.strip()]
    return ls[0][:160] if ls else 'no message'


def conf():
    return loop_conf.load()


def loop_home():
    return conf()['LOOP_HOME'].replace('\\', '/').rstrip('/')


def configured():
    return bool((conf().get('ENGINE_RECORD_DIR') or '').strip())


def work_dir():
    return loop_home() + '/work'


def lock_base():
    """The one lock the record helpers share with the step-log tool: the C3 append lock on the step log (this path + '.lock', beside
    the log in the record repository's docs folder, which is never committed)."""
    return record_repo() + '/' + STEP


def record_repo():
    er = (conf().get('ENGINE_RECORD_DIR') or '').strip()
    if not er:
        raise Refused('ENGINE_RECORD_DIR is not configured', 2)
    rc, out, err = run(['rev-parse', '--show-toplevel'], er)
    if rc != 0:
        raise Refused('ENGINE_RECORD_DIR is not a repository work tree (%s)' % first_line(err), 2)
    return er.replace('\\', '/')


def record_branch():
    return conf().get('RECORD_BRANCH') or 'record'


def kit_repo():
    c = conf()
    kd = os.environ.get('KIT_DIR') or c.get('KIT_DIR') or '~/loop-kit'
    kd = loop_conf.expand_tilde(kd)
    rc, out, err = run(['rev-parse', '--show-toplevel'], kd)
    if rc != 0:
        raise Refused('the kit repository (KIT_DIR, else ~/loop-kit) is not a repository work tree', 2)
    return kd.replace('\\', '/')


def kit_branch():
    return os.environ.get('KIT_BRANCH') or conf().get('KIT_BRANCH') or 'main'


def authority_text(gid):
    gm = '%s/goals/%s/GOAL.md' % (loop_home(), gid)
    try:
        lines = open(gm, encoding='utf-8', errors='replace').read().splitlines()
    except OSError:
        return ''
    out, on = [], False
    for ln in lines:
        if ln.startswith('Authority:'):
            on = True
            out.append(ln)
        elif on:
            if not ln.strip() or re.match(r'^[A-Z][A-Za-z ]{0,30}:', ln):
                break
            out.append(ln)
    return ' '.join(out).replace('\\', '/')


def names_kit(gid):
    return KIT_NAMED.search(authority_text(gid)) is not None


def paths(gid):
    base = '%s/%s' % (work_dir(), gid)
    return base + '/record', base + '/kit'


def branches(gid):
    return 'rec-' + gid.lower(), gid.lower()


def branch_exists(repo, b):
    return run(['rev-parse', '--verify', '-q', 'refs/heads/' + b], repo)[0] == 0


def wanted(gid):
    """The worktrees this goal needs: a list of (label, repository, base branch, goal branch, folder)."""
    rd = record_repo()
    rb, kb = branches(gid)
    rp, kp = paths(gid)
    items = [('record', rd, record_branch(), rb, rp)]
    if names_kit(gid):
        items.append(('kit', kit_repo(), kit_branch(), kb, kp))
    for label, repo, base, br, folder in items:
        if run(['rev-parse', '--verify', '-q', 'refs/heads/' + base], repo)[0] != 0:
            raise Refused('the %s base branch %s does not exist' % (label, base), 2)
    return items


def ensure(gid, strict=False):
    """Make the goal's worktrees. strict (the open command): refuse when a folder or a branch exists, before making anything.
    Otherwise (the dispatcher): reuse a folder that is a worktree on the goal branch, make the absent ones, refuse any other state.
    Returns (record folder, kit folder or None, labels made)."""
    if not ID_RE.match(gid):
        raise Refused('goal id must match %s' % ID_RE.pattern, 2)
    items = wanted(gid)
    todo = []
    for label, repo, base, br, folder in items:
        have_dir, have_br = os.path.exists(folder), branch_exists(repo, br)
        if strict and (have_dir or have_br):
            raise Refused('refused, nothing made: the %s %s already exists' % (label, 'folder' if have_dir else 'branch ' + br))
        if have_dir:
            rc, out, err = run(['symbolic-ref', '--short', 'HEAD'], folder)
            if rc != 0 or out.strip() != br:
                raise Refused('refused: the %s folder exists but is not a worktree on branch %s' % (label, br))
        elif have_br:
            raise Refused('refused: the %s branch %s exists with no worktree folder; it is never reused silently' % (label, br))
        else:
            todo.append((label, repo, base, br, folder))
    made = []
    for label, repo, base, br, folder in todo:
        os.makedirs(os.path.dirname(folder), exist_ok=True)
        rc, out, err = run(['worktree', 'add', '-q', '-b', br, folder, base], repo)
        if rc != 0:
            raise Refused('the %s worktree could not be made (%s); made so far: %s' % (label, first_line(err), ','.join(made) or 'none'), 4)
        made.append(label)
    rp, kp = paths(gid)
    return rp, (kp if len(items) > 1 else None), made


def dirt(folder):
    """Tracked or untracked changes in a worktree, an untracked *.lock file not counted."""
    rc, out, err = run(['status', '--porcelain'], folder)
    if rc != 0:
        raise Refused('status of a worktree failed (%s)' % first_line(err), 4)
    return [ln for ln in out.replace('\r', '').split('\n') if ln.strip() and not (ln.startswith('??') and ln.rstrip().endswith('.lock'))]


def close(gid):
    if not ID_RE.match(gid):
        raise Refused('goal id must match %s' % ID_RE.pattern, 2)
    rd = record_repo()
    rb, kb = branches(gid)
    rp, kp = paths(gid)
    if not branch_exists(rd, rb):
        raise Refused('refused: the record branch %s does not exist, so nothing proves it merged' % rb)
    if run(['merge-base', '--is-ancestor', 'refs/heads/' + rb, 'refs/heads/' + record_branch()], rd)[0] != 0:
        raise Refused('refused: the record branch %s is not merged into %s; run loop-record-merge %s first' % (rb, record_branch(), gid))
    targets = [(rd, rp, 'record')]
    if os.path.exists(kp):
        targets.append((kit_repo(), kp, 'kit'))
    for repo, folder, label in targets:
        if os.path.exists(folder) and dirt(folder):
            raise Refused('refused: the %s worktree holds uncommitted changes (%d path(s)); nothing removed' % (label, len(dirt(folder))))
    gone = []
    for repo, folder, label in targets:
        if not os.path.exists(folder):
            continue
        rc, out, err = run(['worktree', 'remove', '--force', folder], repo)
        if rc != 0:
            raise Refused('the %s worktree could not be removed (%s)' % (label, first_line(err)), 4)
        gone.append(label)
    for repo, folder, label in targets:
        run(['worktree', 'prune'], repo)
    base = os.path.dirname(rp)
    try:
        os.rmdir(base)
    except OSError:
        pass
    return gone, [rb] + ([kb] if len(targets) > 1 else [])


def main(argv):
    if len(argv) != 2 or argv[0] not in ('open', 'close'):
        print(USAGE)
        return 64
    gid = argv[1].upper()
    try:
        if argv[0] == 'open':
            rp, kp, made = ensure(gid, strict=True)
            print('record ' + rp)
            if kp:
                print('kit ' + kp)
            return 0
        gone, kept = close(gid)
        print('closed %s: removed worktree(s) %s; branches kept: %s' % (gid, ','.join(gone) or 'none', ','.join(kept)))
        return 0
    except Refused as e:
        print('loop-worktree: ' + e.msg)
        return e.code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
