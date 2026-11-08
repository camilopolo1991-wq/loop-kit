#!/usr/bin/env python3
"""loop-record-commit: the one locked way to commit in the record repository (KIT-10 C4 (b)).

  loop-record-commit <GOAL-ID> [(-F <message file> | -m <message>)]                  the step log and the state file
  loop-record-commit <GOAL-ID> (-F <message file> | -m <message>) [--] <path> ...    other record files, in the goal's worktree

With no path it commits docs/JOURNAL.md (the step log) and docs/STATE.md on the record branch's own work tree, the record repository
the config names (ENGINE_RECORD_DIR, which must be on the record branch), and nowhere else. The step-log tool appends there without
committing; this is where those lines land. Under the C3 lock (loop_steplog.append_lock on the step log, the same lock the step-log
tool takes) and the git index lock (a foreign holder is waited out, 4 tries of 0.25 s, counted as index_lock_retries=N): it stages
exactly those two paths by name (never -A): the step log as it is, the state file as a blob built from the committed text with only
<GOAL-ID>'s own section-5 subsection ("### <id>" between a "## 5" heading, followed by a space or a dot, and the next "## " heading or the
end of the file) taken from the work tree, written to the index and never to the work
tree, so another goal's uncommitted subsection stays uncommitted in the work tree. It scans the staged diff (loop_scan.py with no
argument), commits the index (the two paths) with the final-paragraph trailer "Goal: <GOAL-ID>", and scans the new commit range.
Nothing pending for the two paths is exit 0 and no commit. A state file whose work tree differs from the committed one anywhere
outside the "### " subsections of section 5 (a line outside section 5, the section-5 heading line, a line of section 5 before its first
subsection) is refused with one line that names the part, and nothing is committed.

KIT-11 C4 (b): with no path and the goal's record worktree ($LOOP_HOME/work/<GOAL-ID>/record) present it refuses (exit 3, one line
naming the cause, nothing committed): while a goal worktree exists the step log and STATE.md land only through loop-record-merge
<GOAL-ID>, which commits the pending lines itself (commit_pair) before the merge.

With paths it commits those files in $LOOP_HOME/work/<GOAL-ID>/record, the goal's worktree on the branch rec-<goal-id lower>, the
same lock and the same scans, and refuses either of the two files there (a goal's record branch carries no step-log or state change).

Exit codes: 0 committed (or nothing pending), 1 a scan hit, 2 not configured or bad input, 3 refused (state), 4 a repository command
or a scan failed, 5 the lock was not taken in time (the C3 bound, LOOP_STEPLOG_LOCK_WAIT_S), 64 usage.
"""
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import loop_steplog as sl  # noqa: E402
import loop_worktree as wt  # noqa: E402

USAGE = 'usage: loop-record-commit <GOAL-ID> [(-F <message file> | -m <message>)] [[--] <path> ...]  (no path: the step log and STATE.md on the record branch)'
TRIES = 4
POLL_S = 0.25
PAIR = (wt.STEP, wt.STATE)
ID_FIND = re.compile(r'(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9]{1,11}-\d{2,3}(?![A-Za-z0-9])')


def git_retry(args, cwd, inp=None, count=None):
    """wt.run, retried while the answer names an index lock held by someone else; count[0] counts the retries."""
    n = 0
    while True:
        rc, out, err = wt.run(args, cwd, inp)
        if rc != 0 and 'index.lock' in err and n < TRIES - 1:
            n += 1
            if count is not None:
                count[0] += 1
            time.sleep(POLL_S)
            continue
        return rc, out, err


def scan(cwd, args):
    """(hits, why): hits is the number the scanner printed, None when it could not run or printed none."""
    p = subprocess.run([sys.executable, HERE + '/loop_scan.py'] + args, cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL)
    text = p.stdout.decode('utf-8', 'replace')
    m = re.search(r'\bhits=(\d+)', text)
    if m and p.returncode in (0, 1):
        return int(m.group(1)), ''
    return None, 'the scanner exited %d (%s)' % (p.returncode, wt.first_line(text))


def with_trailer(msg, gid):
    msg = msg.replace('\r\n', '\n').rstrip('\n')
    last = msg.split('\n\n')[-1].split('\n')
    if 'Goal: ' + gid in last:
        return msg + '\n'
    return msg + '\n\nGoal: ' + gid + '\n'


def parse(argv):
    if not argv:
        return None
    gid, msg, rel, i = argv[0].upper(), None, [], 1
    while i < len(argv):
        a = argv[i]
        if a == '--':
            rel += argv[i + 1:]
            break
        if a in ('-F', '-m'):
            if i + 1 >= len(argv):
                return None
            if a == '-F':
                try:
                    msg = open(argv[i + 1], encoding='utf-8').read()
                except OSError:
                    raise wt.Refused('the message file could not be read', 2)
            else:
                msg = argv[i + 1]
            i += 2
        else:
            rel.append(a)
            i += 1
    if msg is not None and not msg.strip():
        return None
    if rel and msg is None:
        return None
    return gid, msg, rel


def bad_path(p):
    q = p.replace('\\', '/')
    return os.path.isabs(q) or re.match(r'^[A-Za-z]:', q) is not None or '..' in q.split('/') or q.startswith('.git/') or q == '.git'


def is_pair(p):
    q = p.replace('\\', '/')
    while q.startswith('./'):
        q = q[2:]
    return q.lower() in [x.lower() for x in PAIR]


HEAD5 = re.compile(r'^## 5([. ]|$)')
HEAD2 = re.compile(r'^##( |$)')
PARTS = (('o', 'a line outside section 5'), ('h', 'the section-5 heading line'),
         ('p', 'a line of section 5 before its first ### subsection'))


def split_lines(text):
    """(lines, eol): the lines of text (each keeps its own carriage return) without the empty piece after a final newline, and whether
    the text ended in a newline. A missing final newline moves no line to another section."""
    ls = text.split('\n')
    eol = ls[-1] == ''
    return (ls[:-1] if eol else ls), eol


def classify(text):
    """The lines of a state file as (kind, key, line). Section 5 starts at a heading line "## 5" followed by a space or a dot (or ending
    there) and runs to the next "## " heading or the end of the file. Kinds: 'o' a line outside section 5, 'h' its heading line, 'p' a
    line of section 5 before its first "### " heading, 's' a line of a "### " subsection (key the goal id found in its heading, the
    heading text when it holds none)."""
    out, in5, key = [], False, None
    for ln in split_lines(text)[0]:
        s = ln.rstrip('\r')
        if HEAD5.match(s):
            in5, key = True, None
            out.append(('h', None, ln))
        elif HEAD2.match(s):
            in5, key = False, None
            out.append(('o', None, ln))
        elif not in5:
            out.append(('o', None, ln))
        else:
            if s.startswith('### '):
                m = ID_FIND.search(s[4:])
                key = m.group(0).upper() if m else s[4:].strip().upper()
            out.append(('s' if key is not None else 'p', key, ln))
    return out


def own_only(old, new, gid):
    """(text, why): the committed text with only gid's own section-5 subsection (its heading included) taken from the work-tree text.
    why is None and text set, or text None and why naming the parts that differ: a line outside section 5, the section-5 heading
    line, a line of section 5 before its first subsection. Another goal's subsection may differ: it stays as committed, which leaves
    the peer's edit uncommitted in the work tree."""
    o, n = classify(old), classify(new)
    bad = [label for kind, label in PARTS if [ln for k, _, ln in o if k == kind] != [ln for k, _, ln in n if k == kind]]
    if bad:
        return None, ' and '.join(bad)
    mine = [ln for kind, k, ln in n if kind == 's' and k == gid]
    has = any(kind == 's' and k == gid for kind, k, _ in o)
    nonblank5 = [i for i, (kind, _, ln) in enumerate(o) if kind in ('h', 'p', 's') and ln.strip()]
    after = nonblank5[-1] if nonblank5 else -1          # a subsection that is new goes after the last non-blank line of section 5
    out, put = [], False                                # (line, mine)
    for i, (kind, k, ln) in enumerate(o):
        if kind == 's' and k == gid:
            if not put:
                out += [(x, True) for x in mine]
                put = True
            continue
        out.append((ln, False))
        if i == after and not has:
            out += [(x, True) for x in mine]
            put = True
    eol = split_lines(new)[1] if out and out[-1][1] else split_lines(old)[1]
    return '\n'.join(x for x, _ in out) + ('\n' if eol and out else ''), None


def stage_state(rd, new_bytes, old, gid):
    """Stage docs/STATE.md as the committed text with only gid's own subsection from the work tree, by blob, the work tree untouched.
    Raises Refused when the work tree differs from the committed text outside section 5."""
    new = new_bytes.decode('utf-8', 'surrogateescape')
    text, why = own_only(old, new, gid)
    if why:
        raise wt.Refused('refused: docs/STATE.md differs from the committed file in %s; a leader edits only its own '
                         '### %s subsection of section 5; nothing was committed' % (why, gid))
    rc, out, err = wt.run(['ls-files', '-s', '--', wt.STATE], rd)
    mode = out.split()[0] if rc == 0 and out.strip() else '100644'
    rc, out, err = wt.run(['hash-object', '-w', '--path=' + wt.STATE, '--stdin'], rd, text.encode('utf-8', 'surrogateescape'))
    if rc != 0 or not re.fullmatch(r'[0-9a-f]{40,64}', out.strip()):
        raise wt.Refused('the state blob could not be written (%s)' % wt.first_line(err), 4)
    rc, out, err = wt.run(['update-index', '--cacheinfo', '%s,%s,%s' % (mode, out.strip(), wt.STATE)], rd)
    if rc != 0:
        raise wt.Refused('staging the state blob failed (%s)' % wt.first_line(err), 4)


def commit_pair(gid, msg, retries):
    """Commit the step log and the state file on the record repository's work tree. The lock is held by the caller. Returns the new
    short sha, or None when neither file has a pending change."""
    rd = wt.record_repo()
    rec = wt.record_branch()
    rc, out, err = wt.run(['symbolic-ref', '--short', 'HEAD'], rd)
    if rc != 0 or out.strip() != rec:
        raise wt.Refused('refused: the record repository work tree is not on the record branch %s' % rec)
    pair = [p for p in PAIR if os.path.exists(rd + '/' + p)]
    rc, out, err = wt.run(['status', '--porcelain', '--untracked-files=no', '--'] + pair, rd)
    if rc != 0:
        raise wt.Refused('status of the record work tree failed (%s)' % wt.first_line(err), 4)
    if not out.strip():
        return None
    rc, other, err = wt.run(['diff', '--cached', '--name-only'], rd)
    if rc != 0 or other.strip():
        raise wt.Refused('refused: the record repository index already holds staged changes; nothing was committed')
    rc, old, err = wt.run(['show', 'HEAD:' + wt.STATE], rd) if wt.STATE in pair else (1, '', '')
    try:
        if wt.STEP in pair:
            rc2, out, err = git_retry(['add', '--', wt.STEP], rd, count=retries)
            if rc2 != 0:
                raise wt.Refused('staging failed (%s)' % wt.first_line(err), 4)
        if wt.STATE in pair:
            if rc == 0:
                with open(rd + '/' + wt.STATE, 'rb') as f:
                    new_bytes = f.read()
                stage_state(rd, new_bytes, old, gid)
            else:
                rc2, out, err = git_retry(['add', '--', wt.STATE], rd, count=retries)
                if rc2 != 0:
                    raise wt.Refused('staging failed (%s)' % wt.first_line(err), 4)
    except wt.Refused:
        wt.run(['reset', '-q', '--'] + pair, rd)
        raise
    if wt.run(['diff', '--cached', '--quiet', '--'] + pair, rd)[0] == 0:
        return None
    pre, why = scan(rd, [])
    if pre is None or pre:
        wt.run(['reset', '-q', '--'] + pair, rd)
        if pre is None:
            raise wt.Refused('the pre-commit scan could not run: ' + why, 4)
        raise wt.Refused('the pre-commit scan hit %d time(s); the paths are unstaged and nothing was committed' % pre, 1)
    before = wt.run(['rev-parse', 'HEAD'], rd)[1].strip()
    # no path after the message: the commit takes the index, which holds the step log and the state blob staged above (a path would
    # make git take the work-tree file instead and bring a peer's uncommitted subsection in)
    rc, out, err = git_retry(['commit', '-q', '-F', '-'], rd, with_trailer(msg, gid).encode('utf-8'), retries)
    if rc != 0:
        wt.run(['reset', '-q', '--'] + pair, rd)
        raise wt.Refused('the commit failed (%s)' % wt.first_line(err + out), 4)
    after = wt.run(['rev-parse', 'HEAD'], rd)[1].strip()
    post, why = scan(rd, ['--range', before + '..' + after])
    if post is None:
        raise wt.Refused('committed %s but the range scan could not run: %s' % (after[:12], why), 4)
    if post:
        raise wt.Refused('committed %s but the range scan hit %d time(s); do not push it' % (after[:12], post), 1)
    return after[:12]


def commit_goal(gid, msg, rel, retries):
    """Commit rel in the goal's record worktree. The lock is held by the caller. Returns the new short sha."""
    for p in rel:
        if is_pair(p):
            raise wt.Refused('refused: docs/JOURNAL.md and docs/STATE.md are committed only on the record branch\'s own work tree, by '
                             'loop-record-commit %s with no path, never in a goal worktree; nothing was committed' % gid)
    folder = wt.paths(gid)[0]
    rb = wt.branches(gid)[0]
    if not os.path.isdir(folder):
        raise wt.Refused('refused: no record worktree for %s (run loop-worktree open %s)' % (gid, gid))
    rc, out, err = wt.run(['symbolic-ref', '--short', 'HEAD'], folder)
    if rc != 0 or out.strip() != rb:
        raise wt.Refused('refused: the record worktree of %s is not on branch %s' % (gid, rb))
    rc, out, err = git_retry(['add', '--'] + rel, folder, count=retries)
    if rc != 0:
        raise wt.Refused('staging failed (%s)' % wt.first_line(err), 4)
    if wt.run(['diff', '--cached', '--quiet', '--'] + rel, folder)[0] == 0:
        raise wt.Refused('refused: nothing is staged for those paths, so nothing was committed')
    pre, why = scan(folder, [])
    if pre is None or pre:
        wt.run(['reset', '-q', '--'] + rel, folder)
        if pre is None:
            raise wt.Refused('the pre-commit scan could not run: ' + why, 4)
        raise wt.Refused('the pre-commit scan hit %d time(s); the paths are unstaged and nothing was committed' % pre, 1)
    before = wt.run(['rev-parse', 'HEAD'], folder)[1].strip()
    rc, out, err = git_retry(['commit', '-q', '-F', '-', '--'] + rel, folder, with_trailer(msg, gid).encode('utf-8'), retries)
    if rc != 0:
        raise wt.Refused('the commit failed (%s)' % wt.first_line(err + out), 4)
    after = wt.run(['rev-parse', 'HEAD'], folder)[1].strip()
    post, why = scan(folder, ['--range', before + '..' + after])
    if post is None:
        raise wt.Refused('committed %s but the range scan could not run: %s' % (after[:12], why), 4)
    if post:
        raise wt.Refused('committed %s but the range scan hit %d time(s); do not push it' % (after[:12], post), 1)
    return after[:12]


def commit(gid, msg, rel):
    if not wt.ID_RE.match(gid):
        raise wt.Refused('goal id must match %s' % wt.ID_RE.pattern, 2)
    for p in rel:
        if bad_path(p):
            raise wt.Refused('a path must be relative to the record worktree and stay inside it: %s' % p, 2)
    retries = [0]
    if not rel and os.path.isdir(wt.paths(gid)[0]):
        # KIT-11 C4 (b): while the goal's record worktree exists the step log and STATE.md land only through loop-record-merge
        raise wt.Refused('refused: the record worktree work/%s/record exists, so the step log and STATE.md of %s land only through '
                         'loop-record-merge %s; nothing was committed' % (gid, gid, gid), 3)
    try:
        with sl.append_lock(wt.lock_base()):
            if rel:
                sha = commit_goal(gid, msg, rel, retries)
            else:
                sha = commit_pair(gid, msg or 'chore(record): step log and state lines', retries)
    except sl.LockFailure as e:
        print(sl.lock_failure_line('loop-record-commit', 'record', e))
        return sl.LOCK_EXIT
    if sha is None:
        print('loop-record-commit: nothing pending in docs/JOURNAL.md or docs/STATE.md; nothing committed')
        return 0
    print('loop-record-commit: committed %s sha=%s %s pre_scan_hits=0 range_scan_hits=0 index_lock_retries=%d' % (
        gid, sha, 'paths=%d' % len(rel) if rel else 'step_log_and_state', retries[0]))
    return 0


def main(argv):
    try:
        parsed = parse(argv)
        if parsed is None:
            print(USAGE)
            return 64
        return commit(*parsed)
    except wt.Refused as e:
        print('loop-record-commit: ' + e.msg)
        return e.code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
